"""Tests for `aoe2stats_analyzer.run.run_once` — quickstart scenarios 7, 8 and 10.

**T365 (`apps/analyzer/src/aoe2stats_analyzer/run.py`) does not exist yet.** Per this project's
test-first discipline (`CLAUDE.md` "Test-first tasks and the green-tree gate"), every test below is
marked `@pytest.mark.xfail(strict=True, reason="T365 not implemented yet")` and imports
`aoe2stats_analyzer.run` inside its own body, never at module scope — a module-scope import of a
module that does not exist yet is a collection error that fails the whole file, not one test.
`strict=True` is what forces T365 to remove each marker rather than leaving a stale one that would
hide a regression the moment the module lands wrong.

**Assumed interface**, reconstructed from `plan.md`'s Source Code tree, `research.md` R6/R7/R12,
`contracts/analysis.md` and `contracts/http-api.md`'s `POST /api/analyze` section, and
`data-model.md`'s `match_analyses`/`retained_recordings`/`replay_access_log` sections — in the same
spirit `apps/ingester/tests/test_idempotency.py` already committed to for a sibling not-yet-built
module, and for the same reason: a test-first task has to commit to *something* to be a real test at
all, and only the properties named in T364's own task text (SC-006, FR-032, SC-013, FR-037, FR-036,
FR-034, FR-041, SC-009a, FR-044, FR-029) are load-bearing, not this file's specific keyword names.

- `run_once(game_id, budget_seconds, requested_by_user_id, *, session_factory, replay_provider,
  extractor, object_store)` is one match, on one request — `contracts/http-api.md`: "Body
  `{"game_id": ...}`. Claims and runs." `requested_by_user_id` is required at call time even though
  `match_analyses.requested_by_user_id` is nullable (erasure clears it later): `replay_access_log.
  user_id` is `NOT NULL` (`data-model.md`, "the read is user-triggered"), so every call that reads a
  retained recording needs a real user to attribute that read to.
- `replay_provider` satisfies `aoe2stats_providers.base.ReplayProvider`
  (`fetch_replay(game_id, profile_id) -> ReplayBlob | NotFound`), the same Protocol 001 already uses
  for a download (`contracts/providers.md`). The fakes below are bare test doubles, not
  `AoemsReplayProvider` — a `provider_calls` row per fetch is that concrete adapter's own job
  (`AsyncBaseProvider._request`'s `call_sink`, already wired for every other provider in this
  codebase), so "fetched at most once" is asserted on the fake's own call log here, exactly the
  substitution `test_idempotency.py` already made for the identical property in the ingester's
  suite.
- `extractor` satisfies the not-yet-defined `ReplayExtractor` Protocol (T352,
  `packages/core/tests/test_replay_analysis.py` already pins `MatchTimeline`'s and
  `ParticipantTimeline`'s exact field sets): `extract(zip_bytes) -> MatchTimeline`, raising
  `EngineParseError` (already implemented, `aoe2stats_core.replay.validation`) on a recording it
  cannot parse. It also exposes `engine_name`/`engine_version` so `run_once` can compare a stored
  `parser_version` against "the engine currently running" — `contracts/http-api.md`'s definition of
  `stale` — without a second constructor argument for it.
- `object_store` satisfies the async subset of `aoe2stats_storage.objects.ObjectStore` used
  elsewhere in this codebase's tests (`put`, `get`).
- `run_once` never raises on an ordinary outcome — a parse failure, an expired match, a cap refusal
  — because `api/analyze.py` is meant to build the same `analysis` response object whichever state
  results (`contracts/http-api.md`). Every assertion below therefore reads the row back from
  `match_analyses` / `retained_recordings` / `replay_access_log` directly rather than trusting a
  return value, the same way `test_idempotency.py` reads `replay_captures` back.

If T365 lands with a different shape, this file is what gets updated — not evidence that the
assumption above was wrong to make.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_core.replay.validation import EngineParseError
from aoe2stats_providers.base import NotFound, ReplayBlob
from aoe2stats_storage.models import (
    AoeProfile,
    Match,
    MatchAnalysis,
    MatchAnalysisState,
    MatchPlayer,
    ReplayAccessLog,
    RetainedRecording,
    User,
)
from aoe2stats_storage.repositories.base import session_scope

# `session_factory` and `clean_database` below come from `apps/analyzer/tests/conftest.py`
# (T362's own addition, re-exporting `tests/db.py`'s harness exactly as `apps/api/tests/conftest.py`
# and `apps/ingester/tests/conftest.py` already do) — not imported directly here, which would
# collide with this file's own `session_factory`/`clean_database` parameter names under ruff's
# F811, per that conftest's own docstring.

_BUDGET_SECONDS = 300  # api/analyze.py's own maxDuration (contracts/http-api.md)

# Comfortably beyond any measured retention window (`docs/data-sources.md` §2) without restating
# the figure itself — the point of this constant is "unambiguously expired", not a governed budget.
_FAR_PAST_DAYS = 120

_ENGINE_NAME = "aoe2rec-py"
_ENGINE_VERSION_1 = "0.1.21"  # contracts/analysis.md's pinned wheel
_ENGINE_VERSION_2 = "0.1.22"  # a later parser version, for the recompute tests


# --- Value objects matching contracts/analysis.md's `MatchTimeline` -------------------------------
# `packages/core/src/aoe2stats_core/replay/analysis.py` does not exist yet either (T352), so these
# are local stand-ins carrying the exact field set `packages/core/tests/test_replay_analysis.py`
# already pins — not an import of the real thing, which would make this file fail to collect for a
# second, unrelated reason.


@dataclass(frozen=True, slots=True)
class _FakeParticipantTimeline:
    profile_id: int
    player_number: int
    civ_id: int
    resolved_team_id: int
    builds: tuple = ()
    trainings: tuple = ()
    researches: tuple = ()
    age_up_commands: dict = field(default_factory=dict)
    villagers_ordered: int = 0
    actions: int = 0
    actions_per_minute: float = 0.0
    resigned_at_ms: int | None = None


@dataclass(frozen=True, slots=True)
class _FakeMatchTimeline:
    engine_name: str
    engine_version: str
    point_of_view_profile_id: int
    world_time_ms: int
    participants: tuple = ()


@dataclass(frozen=True, slots=True)
class _FetchCall:
    game_id: int
    profile_id: int


class _FakeReplayProvider:
    """Answers any participant of the seeded match with the same blob — this file does not assume
    which participant `run_once` tries first, only that it tries at most one (SC-006). Raises
    `AssertionError` past `max_calls`, a canary rather than a passive counter, the same technique
    `test_idempotency.py`'s `_FakeReplayEngine` uses for "this must never run again"."""

    def __init__(self, blob: ReplayBlob, *, max_calls: int | None = None) -> None:
        self._blob = blob
        self._max_calls = max_calls
        self.calls: list[_FetchCall] = []

    async def fetch_replay(self, game_id: int, profile_id: int) -> ReplayBlob | NotFound:
        if self._max_calls is not None and len(self.calls) >= self._max_calls:
            raise AssertionError(
                f"fetch_replay called a {len(self.calls) + 1}th time; SC-006 bounds it to "
                f"{self._max_calls} for this scenario"
            )
        self.calls.append(_FetchCall(game_id=game_id, profile_id=profile_id))
        return self._blob


class _RefusingReplayProvider:
    """Used wherever the source must never be called at all: an expired-and-never-analysed match
    (FR-034, "never as an action that fails") and a recompute from retained bytes (FR-041, SC-009a).
    """

    async def fetch_replay(self, game_id: int, profile_id: int) -> ReplayBlob | NotFound:
        raise AssertionError(
            f"fetch_replay({game_id}, {profile_id}) called when no fetch should ever be attempted"
        )


class _FakeObjectStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.put_calls: list[str] = []
        self.get_calls: list[str] = []

    async def put(self, key: str, body: bytes, *, content_type: str = "application/zip") -> None:
        self.objects[key] = body
        self.put_calls.append(key)

    async def get(self, key: str) -> bytes:
        self.get_calls.append(key)
        return self.objects[key]


class _FakeExtractor:
    """`extract()` raises past `max_calls`, the same canary shape as `_FakeReplayProvider` — FR-036
    and FR-041/SC-006 both depend on `run_once` never calling this a second time when it must not.
    """

    def __init__(
        self,
        *,
        engine_name: str = _ENGINE_NAME,
        engine_version: str = _ENGINE_VERSION_1,
        point_of_view_profile_id: int,
        raises: Exception | None = None,
        max_calls: int | None = None,
    ) -> None:
        self.engine_name = engine_name
        self.engine_version = engine_version
        self._point_of_view_profile_id = point_of_view_profile_id
        self._raises = raises
        self._max_calls = max_calls
        self.calls: list[bytes] = []

    def extract(self, zip_bytes: bytes) -> _FakeMatchTimeline:
        if self._max_calls is not None and len(self.calls) >= self._max_calls:
            raise AssertionError(
                f"extract() called a {len(self.calls) + 1}th time; this scenario bounds it to "
                f"{self._max_calls}"
            )
        self.calls.append(zip_bytes)
        if self._raises is not None:
            raise self._raises
        return _FakeMatchTimeline(
            engine_name=self.engine_name,
            engine_version=self.engine_version,
            point_of_view_profile_id=self._point_of_view_profile_id,
            world_time_ms=1_200_000,
        )


async def _seed_user(session_factory: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    user_id = uuid.uuid4()
    async with session_scope(session_factory) as session:
        session.add(User(id=user_id))
    return user_id


async def _seed_match(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    game_id: int,
    completed_at: datetime,
    profile_ids: Sequence[int],
) -> None:
    async with session_scope(session_factory) as session:
        for profile_id in profile_ids:
            session.add(AoeProfile(profile_id=profile_id, alias=f"Player {profile_id}"))
        session.add(
            Match(
                game_id=game_id,
                leaderboard_id=3,
                completed_at=completed_at,
                duration_seconds=1800,
                source="relic",
                raw_payload={},
            )
        )
        for index, profile_id in enumerate(profile_ids):
            session.add(
                MatchPlayer(
                    game_id=game_id,
                    profile_id=profile_id,
                    team_id=index,
                    civ_id=1,
                    color_id=index,
                    result="win" if index == 0 else "loss",
                )
            )


async def _get_analysis(
    session_factory: async_sessionmaker[AsyncSession], game_id: int
) -> MatchAnalysis | None:
    async with session_scope(session_factory) as session:
        return await session.get(MatchAnalysis, game_id)


async def _get_retained_recording(
    session_factory: async_sessionmaker[AsyncSession], game_id: int, profile_id: int
) -> RetainedRecording | None:
    async with session_scope(session_factory) as session:
        result = await session.execute(
            select(RetainedRecording).where(
                RetainedRecording.game_id == game_id, RetainedRecording.profile_id == profile_id
            )
        )
        return result.scalar_one_or_none()


async def _access_log_rows(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[ReplayAccessLog]:
    async with session_scope(session_factory) as session:
        result = await session.execute(select(ReplayAccessLog))
        return list(result.scalars().all())


async def _run_ingester_once(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """The isolation probe `test_claim.py` (T360) is already documented to use for FR-044: running
    001's real, already-implemented `run_once` over the same database and confirming it neither
    raises nor touches anything `apps/analyzer` owns. Imported at module scope, unlike
    `aoe2stats_analyzer.run` — `aoe2stats_ingester.run` already exists and is fully green."""
    from aoe2stats_ingester.run import run_once as ingester_run_once

    await ingester_run_once(60, trigger="test", stages=[], session_factory=session_factory)


# --- Scenario 7.5 / SC-006 --------------------------------------------------------------------


@pytest.mark.xfail(strict=True, reason="T365 not implemented yet")
async def test_a_match_is_fetched_and_parsed_at_most_once_however_many_users_ask(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Quickstart 7.5: "Open the same match as a different user. Expect the analysis immediately,
    and **one** row [fetch/parse] for that recording across both requests" (FR-031, SC-006)."""
    from aoe2stats_analyzer.run import run_once

    game_id = 500_546_441
    profile_a, profile_b = 196_240, 196_241
    await _seed_match(
        session_factory,
        game_id=game_id,
        completed_at=datetime.now(UTC) - timedelta(days=1),
        profile_ids=[profile_a, profile_b],
    )
    requester = await _seed_user(session_factory)
    second_viewer = await _seed_user(session_factory)
    provider = _FakeReplayProvider(
        ReplayBlob(content=b"replay bytes", filename="r.zip", content_type="application/zip"),
        max_calls=1,
    )
    extractor = _FakeExtractor(point_of_view_profile_id=profile_a, max_calls=1)
    store = _FakeObjectStore()

    await run_once(
        game_id,
        _BUDGET_SECONDS,
        requester,
        session_factory=session_factory,
        replay_provider=provider,
        extractor=extractor,
        object_store=store,
    )
    # A second, different user opens the same match — this must not fetch or parse again.
    await run_once(
        game_id,
        _BUDGET_SECONDS,
        second_viewer,
        session_factory=session_factory,
        replay_provider=provider,
        extractor=extractor,
        object_store=store,
    )

    assert len(provider.calls) == 1
    assert len(extractor.calls) == 1
    analysis = await _get_analysis(session_factory, game_id)
    assert analysis is not None
    assert analysis.state == MatchAnalysisState.PUBLISHED
    assert analysis.result_key is not None


# --- Scenario 7.6 / FR-032 ----------------------------------------------------------------------


@pytest.mark.xfail(strict=True, reason="T365 not implemented yet")
async def test_the_stored_row_records_the_point_of_view_and_the_parser_version(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Quickstart 7.6: "Confirm `match_analyses` records the point of view and the parser version
    (FR-032), and that `retained_recordings` holds exactly one row with a checksum (FR-033)."""
    from aoe2stats_analyzer.run import run_once

    game_id = 500_546_442
    profile_a, profile_b = 300_001, 300_002
    await _seed_match(
        session_factory,
        game_id=game_id,
        completed_at=datetime.now(UTC) - timedelta(days=1),
        profile_ids=[profile_a, profile_b],
    )
    requester = await _seed_user(session_factory)
    raw_bytes = b"raw replay bytes for FR-032"
    provider = _FakeReplayProvider(
        ReplayBlob(content=raw_bytes, filename="r.zip", content_type="application/zip")
    )
    extractor = _FakeExtractor(point_of_view_profile_id=profile_a, engine_version=_ENGINE_VERSION_1)
    store = _FakeObjectStore()

    await run_once(
        game_id,
        _BUDGET_SECONDS,
        requester,
        session_factory=session_factory,
        replay_provider=provider,
        extractor=extractor,
        object_store=store,
    )

    analysis = await _get_analysis(session_factory, game_id)
    assert analysis is not None
    assert analysis.state == MatchAnalysisState.PUBLISHED
    assert analysis.point_of_view_profile_id == profile_a
    assert analysis.parser_name == _ENGINE_NAME
    assert analysis.parser_version == _ENGINE_VERSION_1

    retained = await _get_retained_recording(session_factory, game_id, profile_a)
    assert retained is not None
    assert retained.zip_sha256 == hashlib.sha256(raw_bytes).hexdigest()
    assert retained.zip_bytes == len(raw_bytes)


# --- Scenario 8.6 / SC-013 -----------------------------------------------------------------------


@pytest.mark.xfail(strict=True, reason="T365 not implemented yet")
async def test_a_parse_failure_leaves_the_api_and_the_ingester_untouched(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Quickstart 8.6: "While a parse is failing, confirm the API answers normally and the
    ingester's next run is unaffected" (FR-042, SC-013). `run_once` itself must not raise — a
    parser crash is contained and recorded as `failed`, never propagated to whatever process called
    it — and the ingester's own, already-implemented `run_once` must be able to run immediately
    afterward without seeing anything wrong."""
    from aoe2stats_analyzer.run import run_once

    game_id = 500_546_443
    profile_a, profile_b = 300_003, 300_004
    await _seed_match(
        session_factory,
        game_id=game_id,
        completed_at=datetime.now(UTC) - timedelta(days=1),
        profile_ids=[profile_a, profile_b],
    )
    requester = await _seed_user(session_factory)
    provider = _FakeReplayProvider(
        ReplayBlob(content=b"corrupted", filename="r.zip", content_type="application/zip")
    )
    extractor = _FakeExtractor(
        point_of_view_profile_id=profile_a,
        raises=EngineParseError("aoe2rec-py could not parse this recording"),
    )
    store = _FakeObjectStore()

    # Must not raise: the caller (api/analyze.py, in its own process) still gets a normal response.
    await run_once(
        game_id,
        _BUDGET_SECONDS,
        requester,
        session_factory=session_factory,
        replay_provider=provider,
        extractor=extractor,
        object_store=store,
    )

    analysis = await _get_analysis(session_factory, game_id)
    assert analysis is not None
    assert analysis.state == MatchAnalysisState.FAILED
    assert analysis.result_key is None

    # The ingester's own run, on the same database, is unaffected — the isolation FR-042 requires.
    await _run_ingester_once(session_factory)


# --- Scenario 8.2 / FR-037 -----------------------------------------------------------------------


@pytest.mark.xfail(strict=True, reason="T365 not implemented yet")
async def test_an_interrupted_run_leaves_no_unclaimable_row_and_the_next_request_resumes_it(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Quickstart 8.2: "Kill the function mid-parse. Expect no row stuck in an unclaimable state;
    expect the *next person to open that match* to resume it" (FR-037, FR-044). Simulated by seeding
    a `running` row whose lease already expired — the shape a crashed invocation leaves behind
    (`data-model.md`'s `running` state, R6) — and confirming the very next call finishes the job
    rather than reporting it stuck."""
    from aoe2stats_analyzer.run import run_once

    game_id = 500_546_444
    profile_a, profile_b = 300_005, 300_006
    await _seed_match(
        session_factory,
        game_id=game_id,
        completed_at=datetime.now(UTC) - timedelta(days=1),
        profile_ids=[profile_a, profile_b],
    )
    abandoned_by = await _seed_user(session_factory)
    resumer = await _seed_user(session_factory)
    now = datetime.now(UTC)
    async with session_scope(session_factory) as session:
        session.add(
            MatchAnalysis(
                game_id=game_id,
                state=MatchAnalysisState.RUNNING,
                point_of_view_profile_id=profile_a,
                requested_by_user_id=abandoned_by,
                requested_at=now - timedelta(minutes=10),
                claimed_at=now - timedelta(minutes=10),
                lease_expires_at=now - timedelta(minutes=5),  # already expired: a dead invocation
                attempts=1,
            )
        )

    provider = _FakeReplayProvider(
        ReplayBlob(content=b"resumed bytes", filename="r.zip", content_type="application/zip")
    )
    extractor = _FakeExtractor(point_of_view_profile_id=profile_a)
    store = _FakeObjectStore()

    await run_once(
        game_id,
        _BUDGET_SECONDS,
        resumer,
        session_factory=session_factory,
        replay_provider=provider,
        extractor=extractor,
        object_store=store,
    )

    analysis = await _get_analysis(session_factory, game_id)
    assert analysis is not None
    # Resumed to completion, not left stuck at `running` with a dead lease.
    assert analysis.state == MatchAnalysisState.PUBLISHED
    assert analysis.result_key is not None


# --- Scenario 8.3 / FR-036 -----------------------------------------------------------------------


@pytest.mark.xfail(strict=True, reason="T365 not implemented yet")
async def test_an_unparsable_recording_fails_on_the_first_attempt_and_is_never_retried(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """FR-036: "record[s] a failed analysis with its reason... never a silent failure", and the
    `match_analyses` docstring's own rule: "A recording that fails to parse does not retry at all:
    it goes to `failed` on the first attempt with its full error... because a parse is deterministic
    and a second attempt is a second identical failure that costs a fetch." Asked for twice, this
    must fetch and parse **once**, not twice — `_FakeReplayProvider`/`_FakeExtractor`'s
    `max_calls=1` turn a retry into a hard failure rather than a silently-passing assertion."""
    from aoe2stats_analyzer.run import run_once

    game_id = 500_546_445
    profile_a, profile_b = 300_007, 300_008
    await _seed_match(
        session_factory,
        game_id=game_id,
        completed_at=datetime.now(UTC) - timedelta(days=1),
        profile_ids=[profile_a, profile_b],
    )
    requester = await _seed_user(session_factory)
    second_asker = await _seed_user(session_factory)
    provider = _FakeReplayProvider(
        ReplayBlob(content=b"corrupted", filename="r.zip", content_type="application/zip"),
        max_calls=1,
    )
    extractor = _FakeExtractor(
        point_of_view_profile_id=profile_a,
        raises=EngineParseError("the archive is well-formed but the engine rejected it"),
        max_calls=1,
    )
    store = _FakeObjectStore()

    await run_once(
        game_id,
        _BUDGET_SECONDS,
        requester,
        session_factory=session_factory,
        replay_provider=provider,
        extractor=extractor,
        object_store=store,
    )
    first = await _get_analysis(session_factory, game_id)
    assert first is not None
    assert first.state == MatchAnalysisState.FAILED
    assert first.error_class == "EngineParseError"
    assert first.error_message
    first_error_message = first.error_message

    # A second person opens the same match. The `max_calls=1` fakes above raise `AssertionError`
    # if `run_once` fetches or parses again — this call must be a no-op against the failed row.
    await run_once(
        game_id,
        _BUDGET_SECONDS,
        second_asker,
        session_factory=session_factory,
        replay_provider=provider,
        extractor=extractor,
        object_store=store,
    )

    second = await _get_analysis(session_factory, game_id)
    assert second is not None
    assert second.state == MatchAnalysisState.FAILED
    assert second.error_message == first_error_message
    assert len(provider.calls) == 1
    assert len(extractor.calls) == 1


# --- Scenario 8.5 / FR-034 -----------------------------------------------------------------------


@pytest.mark.xfail(strict=True, reason="T365 not implemented yet")
async def test_a_never_analysed_match_past_the_window_is_unavailable_not_an_action(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Quickstart 8.5: "Request an analysis of the >31-day-old match. Expect permanent
    unavailability with a reason, and no button" (FR-034). R8: availability is *derived*, never
    probed — the source must not be asked at all for a match this old that was never analysed, so
    `_RefusingReplayProvider` and an extractor bounded to zero calls turn a stray fetch or parse
    into a hard failure rather than a silently-passing assertion."""
    from aoe2stats_analyzer.run import run_once

    game_id = 474_746_656  # quickstart.md's own fixture for this exact scenario
    profile_a, profile_b = 300_009, 300_010
    await _seed_match(
        session_factory,
        game_id=game_id,
        completed_at=datetime.now(UTC) - timedelta(days=_FAR_PAST_DAYS),
        profile_ids=[profile_a, profile_b],
    )
    requester = await _seed_user(session_factory)
    provider = _RefusingReplayProvider()
    extractor = _FakeExtractor(point_of_view_profile_id=profile_a, max_calls=0)
    store = _FakeObjectStore()

    await run_once(
        game_id,
        _BUDGET_SECONDS,
        requester,
        session_factory=session_factory,
        replay_provider=provider,
        extractor=extractor,
        object_store=store,
    )

    analysis = await _get_analysis(session_factory, game_id)
    assert analysis is not None
    assert analysis.state == MatchAnalysisState.UNAVAILABLE
    assert analysis.result_key is None
    assert not store.put_calls


# --- Scenario 10 / FR-041, SC-009a, FR-044, SC-006 -----------------------------------------------


@pytest.mark.xfail(strict=True, reason="T365 not implemented yet")
async def test_recompute_after_an_engine_change_reaches_the_source_zero_times_and_only_on_request(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Scenario 10: "Change the parser version... recompute by asking for it the same way a first
    analysis is asked for — `POST /api/analyze`. Confirm nothing on a timer did it first (FR-044)...
    Expect it to succeed from this service's own retained bytes... with **zero** calls to the
    source" (FR-041, SC-009a). Also SC-006's own "1 again after a parser version change, and 1
    only": a third call against the now-current, non-stale row must re-parse nothing either.

    The match predates any retention window (the seeded `completed_at` mirrors quickstart's own
    >31-day fixture) — recomputing from retained bytes is the only way this can ever succeed, so a
    stray call to the source here is exactly the failure FR-041 exists to make impossible.
    """
    from aoe2stats_analyzer.run import run_once

    game_id = 474_746_656
    profile_a, profile_b = 300_011, 300_012
    completed_at = datetime.now(UTC) - timedelta(days=_FAR_PAST_DAYS)
    await _seed_match(
        session_factory,
        game_id=game_id,
        completed_at=completed_at,
        profile_ids=[profile_a, profile_b],
    )
    original_requester = await _seed_user(session_factory)
    recomputer = await _seed_user(session_factory)

    retained_bytes = b"already-retained recording bytes, the source no longer serves this match"
    object_key = f"retained-recordings/{game_id}/{profile_a}.zip"
    store = _FakeObjectStore()
    store.objects[object_key] = retained_bytes
    now = datetime.now(UTC)
    async with session_scope(session_factory) as session:
        session.add(
            RetainedRecording(
                id=uuid.uuid4(),
                game_id=game_id,
                profile_id=profile_a,
                object_key=object_key,
                zip_bytes=len(retained_bytes),
                zip_sha256=hashlib.sha256(retained_bytes).hexdigest(),
                retained_at=now - timedelta(days=1),
                requested_by_user_id=original_requester,
            )
        )
        session.add(
            MatchAnalysis(
                game_id=game_id,
                state=MatchAnalysisState.PUBLISHED,
                point_of_view_profile_id=profile_a,
                parser_name=_ENGINE_NAME,
                parser_version=_ENGINE_VERSION_1,
                requested_by_user_id=original_requester,
                requested_at=now - timedelta(days=1),
                claimed_at=now - timedelta(days=1),
                finished_at=now - timedelta(days=1),
                attempts=1,
                result_key=f"analyses/{game_id}.json",
            )
        )

    # The engine has moved on: this is "the engine currently running" for the recompute call.
    refusing_provider = _RefusingReplayProvider()
    upgraded_extractor = _FakeExtractor(
        point_of_view_profile_id=profile_a, engine_version=_ENGINE_VERSION_2, max_calls=1
    )

    await run_once(
        game_id,
        _BUDGET_SECONDS,
        recomputer,
        session_factory=session_factory,
        replay_provider=refusing_provider,
        extractor=upgraded_extractor,
        object_store=store,
    )

    recomputed = await _get_analysis(session_factory, game_id)
    assert recomputed is not None
    assert recomputed.state == MatchAnalysisState.PUBLISHED
    assert recomputed.parser_version == _ENGINE_VERSION_2
    assert object_key in store.get_calls
    # No new retention: the recompute reads what is already there, it does not fetch a second copy.
    still_one_retained_row = await _get_retained_recording(session_factory, game_id, profile_a)
    assert still_one_retained_row is not None
    assert still_one_retained_row.zip_sha256 == hashlib.sha256(retained_bytes).hexdigest()

    # "By nothing else": the ingester's own, already-implemented run touches nothing here.
    version_before_sweep = recomputed.parser_version
    await _run_ingester_once(session_factory)
    untouched = await _get_analysis(session_factory, game_id)
    assert untouched is not None
    assert untouched.parser_version == version_before_sweep

    # A third call, now that the row is published and not stale against the same engine version,
    # re-parses nothing (SC-006).
    await run_once(
        game_id,
        _BUDGET_SECONDS,
        recomputer,
        session_factory=session_factory,
        replay_provider=refusing_provider,
        extractor=upgraded_extractor,
        object_store=store,
    )
    assert len(upgraded_extractor.calls) == 1
    final = await _get_analysis(session_factory, game_id)
    assert final is not None
    assert final.result_key == recomputed.result_key


# --- FR-029 ---------------------------------------------------------------------------------------


@pytest.mark.xfail(strict=True, reason="T365 not implemented yet")
async def test_every_read_of_a_retained_recording_is_logged_on_first_analysis_and_on_recompute(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """FR-029: "System MUST log every access to a recorded game this service holds — both the ones
    it serves... and the ones it only reads, which is what analysis and recomputation do." Every
    such row carries `retained_recording_id` and a null `replay_capture_id` (`data-model.md`'s check
    constraint), on the first analysis and on each later recompute — never merely the first."""
    from aoe2stats_analyzer.run import run_once

    game_id = 500_546_446
    profile_a, profile_b = 300_013, 300_014
    await _seed_match(
        session_factory,
        game_id=game_id,
        completed_at=datetime.now(UTC) - timedelta(days=1),
        profile_ids=[profile_a, profile_b],
    )
    first_requester = await _seed_user(session_factory)
    second_requester = await _seed_user(session_factory)
    raw_bytes = b"raw replay bytes for the access-log trail"
    provider = _FakeReplayProvider(
        ReplayBlob(content=raw_bytes, filename="r.zip", content_type="application/zip")
    )
    store = _FakeObjectStore()

    await run_once(
        game_id,
        _BUDGET_SECONDS,
        first_requester,
        session_factory=session_factory,
        replay_provider=provider,
        extractor=_FakeExtractor(
            point_of_view_profile_id=profile_a, engine_version=_ENGINE_VERSION_1
        ),
        object_store=store,
    )

    after_first = await _access_log_rows(session_factory)
    assert len(after_first) == 1
    first_row = after_first[0]
    assert first_row.replay_capture_id is None
    assert first_row.retained_recording_id is not None
    assert first_row.purpose != "download"

    retained = await _get_retained_recording(session_factory, game_id, profile_a)
    assert retained is not None
    assert first_row.retained_recording_id == retained.id

    # A recompute, triggered by a later engine version, is a second read of the same recording.
    await run_once(
        game_id,
        _BUDGET_SECONDS,
        second_requester,
        session_factory=session_factory,
        replay_provider=_RefusingReplayProvider(),
        extractor=_FakeExtractor(
            point_of_view_profile_id=profile_a, engine_version=_ENGINE_VERSION_2, max_calls=1
        ),
        object_store=store,
    )

    after_recompute = await _access_log_rows(session_factory)
    assert len(after_recompute) == 2
    second_row = next(row for row in after_recompute if row.id != first_row.id)
    assert second_row.replay_capture_id is None
    assert second_row.retained_recording_id == retained.id
    assert second_row.purpose != "download"
