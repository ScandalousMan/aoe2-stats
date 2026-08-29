"""Admission-gate tests for `apps/analyzer/src/aoe2stats_analyzer/admission.py` (T358), which does
not exist yet — every test below imports it *inside* its own body, never at module scope, so a
missing module is a per-test `xfail`, not a collection error that takes the whole workspace suite
down (the same discipline `apps/analyzer/tests/test_claim.py` and `apps/ingester/tests/
test_interruption.py` already use for the same reason).

**Why this exists**: quickstart scenario 9 ("Capture always wins") and FR-039 ("System MUST NOT let
analysis consume the request budget, the quota or the execution window that replay capture depends
on. Where the two compete, capture proceeds and analysis waits") are enforced, not merely intended,
by three independent gates `research.md` R7 names: a **deadline gate** (capture's own backlog), a
**budget gate** (analysis's own, smaller daily allowance of requests to the replay source) and a
**storage gate** (FR-047's retention cap). "Independent" is the point asserted three separate ways
below: each gate is read against its own rows, and none of the three ever mutates anything a
capture-side process reads to decide what it does next — exhausting one gate must never close
another, in either direction, and capture must never be starved by an analysis gate check colliding
with capture's own bookkeeping.

**The contract this file assumes**, for whoever lands T359 — R7 names the three gates but not a
function signature, so this is the one this suite exercises and T359 must match:

- `deadline_gate_admits(session, *, now) -> bool` — `False` while any `replay_captures` row is
  **unstored** (`status` in `{pending, downloading}`, never a resolved terminal status — the exact
  `_RESOLVED_STATUSES` shape `scripts/checks/capture_audit.py`'s `captures_pending_past_deadline`
  already uses, R7's own "the query is the same one the capture audit already uses") **and** its own
  `capture_deadline_at` has already passed `now`. `True` otherwise. A capture already resolved one
  way or another (`stored`, `unavailable`, `expired`, `quarantined`, `failed`) is out of contention
  regardless of how far past its own deadline it sits — there is nothing left for an analysis fetch
  to compete with.
- `budget_gate_admits(session, *, now, max_source_requests_per_day) -> bool` — `False` once the
  count of `provider_calls` rows for the replay source (`provider = "aoems"`,
  `packages/providers/src/aoe2stats_providers/aoems/provider.py`'s own `_ENDPOINT`) in the trailing
  day reaches `max_source_requests_per_day`. `True` below it. Scoped to `aoems` specifically — a
  `provider_calls` row from the unrelated search source (`companion`) never counts against this
  allowance — and scoped to the trailing day, not to the table's lifetime, matching
  `ANALYSIS_MAX_SOURCE_REQUESTS_PER_DAY`'s own name (`.env.example`).
- `storage_gate_admits(session, *, retention_cap_bytes) -> bool` — `False` once
  `SUM(retained_recordings.zip_bytes)` reaches `retention_cap_bytes`. `True` below it.
  `retained_recordings` only: `data-model.md`'s own words, "`ANALYSIS_RETENTION_CAP_BYTES` counts
  the retained copy only — the capture is 001's" — a `replay_captures` row's own `zip_bytes` must
  never be added to this sum, however large.
- `AdmissionOutcome(allowed: bool, code: str | None)` — a frozen dataclass, the same shape
  `apps/api/src/aoe2stats_api/ratelimit.py`'s `RateLimitOutcome` already uses for a gate-style
  check in this codebase. `code` is `None` when `allowed` is `True`.
- `check_admission(session, *, now, max_source_requests_per_day, retention_cap_bytes) ->
  AdmissionOutcome` — runs the three gates and reports the first one that blocks. FR-047's own
  wire vocabulary names exactly one of the three codes: the storage gate's refusal is
  `"analysis_cap_reached"` (already `AlertKind.ANALYSIS_CAP_REACHED`, T304) — the one string this
  file pins down, because it is the one the task text and `data-model.md`'s alert vocabulary
  section both name explicitly. The other two gates are not given a wire vocabulary by any artifact,
  so this file asserts their *behaviour* (which of `deadline_gate_admits`/`budget_gate_admits`
  return `False`) rather than inventing a string for either.

Every gate takes its threshold as an explicit parameter rather than reading `Settings` itself,
matching the discipline `apps/api/src/aoe2stats_api/ratelimit.py::check_and_increment` and
`apps/api/src/aoe2stats_api/search.py::search_players` already carry: a service function is a pure
function of its inputs, and whichever caller lands in a later task (`run.py`, `api/analyze.py`)
is where the environment gets read once and passed down. `now` is likewise explicit so no test here
races the real clock.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_storage.models import (
    AoeProfile,
    CaptureSource,
    CaptureStatus,
    Match,
    ProviderCall,
    ReplayCapture,
    RetainedRecording,
)

# `db_session` (and its siblings) come from `apps/analyzer/tests/conftest.py`, the one shared
# harness every Phase 7 `[P]` test file in this directory resolves against — see that module's own
# docstring for why importing them a second time into each test module (this file's own earlier
# shape) is not the convention here, unlike `apps/ingester/tests/conftest.py`'s per-directory
# re-export.

_LEADERBOARD_ID = 3
_AOEMS_PROVIDER = "aoems"
_AOEMS_ENDPOINT = "replay"
_ANALYSIS_CAP_REACHED_CODE = "analysis_cap_reached"

# Every `now` below is an offset from this fixed instant, exactly like `apps/api/tests/
# test_rate_limits.py`'s own `_WINDOW_ORIGIN` and `test_player_search.py`'s own `_NOW`: no test
# here races the real clock.
_NOW = datetime(2026, 1, 1, tzinfo=UTC)

#: The two "unstored" statuses R7's deadline gate exists to protect — a capture still in flight,
#: not yet resolved one way or another. Mirrors `scripts/checks/capture_audit.py`'s own
#: `_RESOLVED_STATUSES` by naming its complement directly rather than restating that tuple here.
_UNSTORED_STATUSES = (CaptureStatus.PENDING, CaptureStatus.DOWNLOADING)

#: Every terminal `replay_captures.status` — a capture already resolved, however it ended. A
#: deadline gate that still blocked on one of these would be protecting nothing: there is no
#: further capture-side work left to compete with.
_RESOLVED_STATUSES = (
    CaptureStatus.STORED,
    CaptureStatus.UNAVAILABLE,
    CaptureStatus.EXPIRED,
    CaptureStatus.QUARANTINED,
    CaptureStatus.FAILED,
)


async def _seed_match(db_session: AsyncSession, *, game_id: int, completed_at: datetime) -> None:
    db_session.add(
        Match(
            game_id=game_id,
            leaderboard_id=_LEADERBOARD_ID,
            completed_at=completed_at,
            source="relic",
            raw_payload={"matchId": game_id},
        )
    )
    await db_session.flush()


async def _seed_profile(
    db_session: AsyncSession, *, profile_id: int, alias: str = "Tester"
) -> None:
    db_session.add(AoeProfile(profile_id=profile_id, alias=alias))
    await db_session.flush()


async def _seed_capture(
    db_session: AsyncSession,
    *,
    game_id: int,
    profile_id: int,
    status: CaptureStatus,
    capture_deadline_at: datetime,
    zip_bytes: int | None = None,
) -> ReplayCapture:
    """One `matches` row plus one `replay_captures` row hung off it. `completed_at` is derived
    rather than passed in — this file exercises the gate that *reads* `capture_deadline_at`, never
    the arithmetic that computes it on insert (that is `apps/ingester/tests/test_shared_match.py`).
    """
    await _seed_match(
        db_session, game_id=game_id, completed_at=capture_deadline_at - timedelta(days=21)
    )
    await _seed_profile(db_session, profile_id=profile_id, alias=f"Profile{profile_id}")
    has_blob = zip_bytes is not None
    capture = ReplayCapture(
        game_id=game_id,
        profile_id=profile_id,
        status=status,
        capture_deadline_at=capture_deadline_at,
        source=CaptureSource.AUTOMATIC,
        object_key=f"replays/{game_id}/{profile_id}.zip" if has_blob else None,
        zip_bytes=zip_bytes,
        zip_sha256=("0" * 64) if has_blob else None,
    )
    db_session.add(capture)
    await db_session.flush()
    return capture


async def _refresh(db_session: AsyncSession, capture: ReplayCapture) -> ReplayCapture:
    await db_session.refresh(capture)
    return capture


async def _seed_provider_call(
    db_session: AsyncSession, *, called_at: datetime, provider: str = _AOEMS_PROVIDER
) -> None:
    db_session.add(ProviderCall(provider=provider, endpoint=_AOEMS_ENDPOINT, called_at=called_at))
    await db_session.flush()


async def _seed_retained_recording(
    db_session: AsyncSession, *, game_id: int, profile_id: int, zip_bytes: int
) -> None:
    await _seed_match(db_session, game_id=game_id, completed_at=_NOW - timedelta(days=5))
    db_session.add(
        RetainedRecording(
            game_id=game_id,
            profile_id=profile_id,
            object_key=f"retained/{game_id}/{profile_id}.zip",
            zip_bytes=zip_bytes,
            zip_sha256="1" * 64,
        )
    )
    await db_session.flush()


# --- Gate 1 — the deadline gate: capture's backlog (FR-039, R7) --------------------------------


@pytest.mark.parametrize("status", _UNSTORED_STATUSES)
async def test_deadline_gate_refuses_while_an_unstored_capture_is_past_its_deadline(
    db_session: AsyncSession,
    status: CaptureStatus,
) -> None:
    from aoe2stats_analyzer.admission import deadline_gate_admits

    await _seed_capture(
        db_session,
        game_id=920_000_001,
        profile_id=930_000_001,
        status=status,
        capture_deadline_at=_NOW - timedelta(hours=1),
    )

    assert await deadline_gate_admits(db_session, now=_NOW) is False


async def test_deadline_gate_admits_when_no_capture_is_past_its_own_deadline(
    db_session: AsyncSession,
) -> None:
    from aoe2stats_analyzer.admission import deadline_gate_admits

    await _seed_capture(
        db_session,
        game_id=920_000_002,
        profile_id=930_000_002,
        status=CaptureStatus.PENDING,
        capture_deadline_at=_NOW + timedelta(days=5),
    )

    assert await deadline_gate_admits(db_session, now=_NOW) is True


@pytest.mark.parametrize("status", _RESOLVED_STATUSES)
async def test_deadline_gate_ignores_a_capture_already_resolved_however_late(
    db_session: AsyncSession,
    status: CaptureStatus,
) -> None:
    """A capture that is `stored`, `unavailable`, `expired`, `quarantined` or `failed` is done —
    there is nothing left for an analysis fetch to compete with, however far past its own
    `capture_deadline_at` it sits. Only the two still-open statuses (`pending`, `downloading`) are
    "unstored" in the sense this gate protects.
    """
    from aoe2stats_analyzer.admission import deadline_gate_admits

    await _seed_capture(
        db_session,
        game_id=920_000_003,
        profile_id=930_000_003,
        status=status,
        capture_deadline_at=_NOW - timedelta(hours=1),
        zip_bytes=123_456 if status in {CaptureStatus.STORED, CaptureStatus.QUARANTINED} else None,
    )

    assert await deadline_gate_admits(db_session, now=_NOW) is True


# --- Gate 2 — the budget gate: analysis's own, smaller allowance (R7) ---------------------------


async def test_budget_gate_admits_below_the_daily_allowance(db_session: AsyncSession) -> None:
    from aoe2stats_analyzer.admission import budget_gate_admits

    for offset_minutes in (5, 10):
        await _seed_provider_call(db_session, called_at=_NOW - timedelta(minutes=offset_minutes))

    assert await budget_gate_admits(db_session, now=_NOW, max_source_requests_per_day=3) is True


async def test_budget_gate_refuses_once_the_daily_allowance_is_exhausted(
    db_session: AsyncSession,
) -> None:
    from aoe2stats_analyzer.admission import budget_gate_admits

    for offset_minutes in (5, 10, 15):
        await _seed_provider_call(db_session, called_at=_NOW - timedelta(minutes=offset_minutes))

    assert await budget_gate_admits(db_session, now=_NOW, max_source_requests_per_day=3) is False


async def test_budget_gate_counts_only_calls_to_the_replay_source(db_session: AsyncSession) -> None:
    """A `provider_calls` row from the unrelated search source (`companion`,
    `packages/providers/src/aoe2stats_providers/companion`) never counts against analysis's own
    `aoems` allowance — the two sources are rate-limited and budgeted independently.
    """
    from aoe2stats_analyzer.admission import budget_gate_admits

    for offset_minutes in (5, 10, 15):
        await _seed_provider_call(
            db_session, called_at=_NOW - timedelta(minutes=offset_minutes), provider="companion"
        )

    assert await budget_gate_admits(db_session, now=_NOW, max_source_requests_per_day=1) is True


async def test_budget_gate_excludes_calls_from_outside_the_daily_window(
    db_session: AsyncSession,
) -> None:
    """A `provider_calls` row that is unambiguously days old, under any reasonable reading of
    "daily" (a rolling trailing day or a calendar day), must never count against today's
    allowance — this is what "daily" means, not "ever".
    """
    from aoe2stats_analyzer.admission import budget_gate_admits

    await _seed_provider_call(db_session, called_at=_NOW - timedelta(days=3))
    await _seed_provider_call(db_session, called_at=_NOW - timedelta(minutes=5))

    assert await budget_gate_admits(db_session, now=_NOW, max_source_requests_per_day=2) is True


async def test_budget_gate_exhaustion_leaves_the_deadline_gate_unaffected(
    db_session: AsyncSession,
) -> None:
    """R7: "[the budget gate] defers analyses; it never touches capture's [gate]." Exhausting the
    source allowance must not make the deadline gate report a backlog that does not exist, and must
    not touch any `replay_captures` row's own columns.
    """
    from aoe2stats_analyzer.admission import budget_gate_admits, deadline_gate_admits

    capture = await _seed_capture(
        db_session,
        game_id=920_000_004,
        profile_id=930_000_004,
        status=CaptureStatus.PENDING,
        capture_deadline_at=_NOW + timedelta(days=5),
    )
    for offset_minutes in (5, 10, 15):
        await _seed_provider_call(db_session, called_at=_NOW - timedelta(minutes=offset_minutes))

    assert await budget_gate_admits(db_session, now=_NOW, max_source_requests_per_day=3) is False
    assert await deadline_gate_admits(db_session, now=_NOW) is True

    refreshed = await _refresh(db_session, capture)
    assert refreshed.status == CaptureStatus.PENDING
    assert refreshed.claimed_at is None
    assert refreshed.attempts == 0


# --- Gate 3 — the storage gate: FR-047's retention cap ------------------------------------------


async def test_storage_gate_admits_below_the_retention_cap(db_session: AsyncSession) -> None:
    from aoe2stats_analyzer.admission import storage_gate_admits

    await _seed_retained_recording(
        db_session, game_id=920_000_005, profile_id=930_000_005, zip_bytes=1_000_000
    )

    assert await storage_gate_admits(db_session, retention_cap_bytes=2_000_000) is True


async def test_storage_gate_refuses_at_the_retention_cap(db_session: AsyncSession) -> None:
    from aoe2stats_analyzer.admission import storage_gate_admits

    await _seed_retained_recording(
        db_session, game_id=920_000_006, profile_id=930_000_006, zip_bytes=1_500_000
    )
    await _seed_retained_recording(
        db_session, game_id=920_000_007, profile_id=930_000_007, zip_bytes=500_000
    )

    assert await storage_gate_admits(db_session, retention_cap_bytes=2_000_000) is False


async def test_storage_gate_counts_only_retained_recordings_never_a_capture(
    db_session: AsyncSession,
) -> None:
    """`data-model.md`: "`ANALYSIS_RETENTION_CAP_BYTES` counts the retained copy only — the
    capture is 001's and is already counted under 001's prefix." A `replay_captures` row's own
    `zip_bytes`, however large, must never be added to this sum, and capture must never be
    affected by the cap being reached.
    """
    from aoe2stats_analyzer.admission import storage_gate_admits

    capture = await _seed_capture(
        db_session,
        game_id=920_000_008,
        profile_id=930_000_008,
        status=CaptureStatus.STORED,
        capture_deadline_at=_NOW - timedelta(days=10),
        zip_bytes=10_000_000_000,
    )

    assert await storage_gate_admits(db_session, retention_cap_bytes=2_000_000) is True

    refreshed = await _refresh(db_session, capture)
    assert refreshed.status == CaptureStatus.STORED
    assert refreshed.zip_bytes == 10_000_000_000


# --- The combined entry point: FR-047's own wire code -------------------------------------------


async def test_check_admission_reports_analysis_cap_reached_at_the_retention_cap(
    db_session: AsyncSession,
) -> None:
    """The one refusal code an artifact actually names: FR-047 and `data-model.md`'s alert
    vocabulary section both say the storage gate's refusal is `analysis_cap_reached`
    (`AlertKind.ANALYSIS_CAP_REACHED`, T304) — this is the wire string `apps/api`'s analysis router
    (a later task) passes straight through, the same way `favourites_limit_reached` already does
    for `apps/api/src/aoe2stats_api/routers/favourites.py`.
    """
    from aoe2stats_analyzer.admission import check_admission

    await _seed_retained_recording(
        db_session, game_id=920_000_009, profile_id=930_000_009, zip_bytes=2_000_000
    )

    outcome = await check_admission(
        db_session,
        now=_NOW,
        max_source_requests_per_day=60,
        retention_cap_bytes=2_000_000,
    )

    assert outcome.allowed is False
    assert outcome.code == _ANALYSIS_CAP_REACHED_CODE


async def test_check_admission_admits_when_every_gate_is_open(db_session: AsyncSession) -> None:
    from aoe2stats_analyzer.admission import check_admission

    await _seed_capture(
        db_session,
        game_id=920_000_010,
        profile_id=930_000_010,
        status=CaptureStatus.PENDING,
        capture_deadline_at=_NOW + timedelta(days=5),
    )
    await _seed_provider_call(db_session, called_at=_NOW - timedelta(minutes=5))
    await _seed_retained_recording(
        db_session, game_id=920_000_011, profile_id=930_000_011, zip_bytes=1_000_000
    )

    outcome = await check_admission(
        db_session,
        now=_NOW,
        max_source_requests_per_day=60,
        retention_cap_bytes=2_000_000_000,
    )

    assert outcome.allowed is True
    assert outcome.code is None
