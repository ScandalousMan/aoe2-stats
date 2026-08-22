"""Integration test for FR-025's deadline-breach alert, raised by `run_once` (T059a) after the
drain, against the still-open `ingest_runs` row `run_once` (T059) opened at the start of the same
cycle.

FR-025: "System MUST raise an alert when any replay passes its capture deadline unarchived. This
count is expected to be permanently zero. This alert fires at the **capture deadline** (day 21),
not at expiry (day ~31)." T059a's own task text is more specific still: one aggregate severity-1
`deadline_breach` row per run, carrying every offending capture's id in `detail`, for every capture
past `capture_deadline_at` that is neither `stored`, `unavailable` nor `quarantined` — "one row per
run, never one per capture: a backlog would otherwise bury the alert it is supposed to raise."

This is a different alert, with a different timing, from `expired_capture` (T056, tested by T047):
`expired_capture` is a post-mortem raised once the source's ~31-day retention has actually closed,
whereas `deadline_breach` fires at the internal 21-day budget with roughly ten days still left to
act. Asserting one for the other would hide a missing alert — see T047's own module docstring for
the same warning from the other direction.

**Why `run_once(..., session_factory=session_factory)`.** `run_once`'s own module docstring says
`budget_seconds`, `trigger` and `stages` are resolved once by whichever entrypoint calls it and
handed down explicitly, never re-read from the environment inside `run_once` itself — the same
discipline `packages/storage/src/aoe2stats_storage/repositories/base.py` names directly: "the
ingester's `run_once()` (T059) ... build[s] ... an engine from it [`DATABASE_URL`]" for its own
direct writes (the `ingest_runs` row this alert is counted against), distinct from whatever a
`Stage` does with its own session. `session_factory` is exactly the same injectable, DI-only seam
`DiscoverStage` already takes in `test_shared_match.py` (T053's own sibling test in this batch) —
the natural analogue for `run_once`'s own database access rather than a `Stage`'s. `stages=()`
isolates this test to that direct bookkeeping alone: discovery, reconciliation and the capture
drain (T053-T055) are irrelevant to whether the deadline sweep itself is correct, and none of them
exist yet at this point in the sequence in any case.

The module `aoe2stats_ingester.run` already exists (T018) — only the behaviour under test, T059a's
alert, does not. `run_once` is still imported inside each test body rather than at module scope,
matching this batch's convention (`test_shared_match.py`, `test_quota.py`): defensive against a
future T059/T059a implementation that makes importing `run.py` pull in modules that do not exist
yet either, and consistent rather than a special case for the one file in the batch whose target
module happens to predate its target behaviour.

Wrapped in `xfail(strict=True, reason="T059a not implemented yet")` per this project's test-first
convention (CLAUDE.md): every assertion below runs for real against the real throwaway database,
and today's `run_once` — `DEFAULT_STAGES` is still empty and T059/T059a have not landed — writes no
`ingest_runs` row and raises no alert at all, so the failure is real, not a stale marker.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from aoe2stats_storage.models import (
    Alert,
    AlertKind,
    AoeProfile,
    CaptureSource,
    CaptureStatus,
    IngestRun,
    Match,
    ReplayCapture,
)

_LEADERBOARD_ID = 3
#: Captures whose blob has actually been written, per data-model.md's write-ordering note: a
#: `quarantined` capture is still uploaded (FR-026), never discarded, so it carries the same
#: object columns a `stored` one does.
_HAS_BLOB = {CaptureStatus.STORED, CaptureStatus.QUARANTINED}


async def _seed_profile(session_factory: async_sessionmaker, profile_id: int, alias: str) -> None:
    async with session_factory() as session:
        session.add(AoeProfile(profile_id=profile_id, alias=alias, country="FR"))
        await session.commit()


async def _seed_capture(
    session_factory: async_sessionmaker,
    *,
    game_id: int,
    profile_id: int,
    status: CaptureStatus,
    capture_deadline_at: datetime,
    completed_at: datetime | None = None,
) -> uuid.UUID:
    """One `matches` row plus one `replay_captures` row hung off it, committed on their own
    connection so `run_once`'s own session (opened separately, against the same
    `session_factory`) actually sees this data rather than racing an uncommitted transaction — the
    same discipline `test_shared_match.py`'s `_seed_two_consenting_users_sharing_a_match` documents
    for `DiscoverStage`.

    `capture_deadline_at` is always passed explicitly rather than derived from `CAPTURE_BUDGET_DAYS`
    here: this test exercises the sweep that *reads* the column, not the arithmetic that computes it
    on insert (that is T053's `test_shared_match.py`).
    """
    if completed_at is None:
        completed_at = capture_deadline_at - timedelta(days=21)
    capture_id = uuid.uuid4()
    has_blob = status in _HAS_BLOB
    async with session_factory() as session:
        session.add(
            Match(
                game_id=game_id,
                leaderboard_id=_LEADERBOARD_ID,
                completed_at=completed_at,
                source="relic",
                raw_payload={"matchId": game_id},
            )
        )
        await session.flush()
        session.add(
            ReplayCapture(
                id=capture_id,
                game_id=game_id,
                profile_id=profile_id,
                status=status,
                capture_deadline_at=capture_deadline_at,
                source=CaptureSource.AUTOMATIC,
                object_key=f"replays/{game_id}/{profile_id}.zip" if has_blob else None,
                zip_bytes=123_456 if has_blob else None,
                zip_sha256=("0" * 64) if has_blob else None,
                stored_at=(
                    completed_at + timedelta(hours=1) if status == CaptureStatus.STORED else None
                ),
                last_error=(
                    "capture-time validation failed"
                    if status == CaptureStatus.QUARANTINED
                    else None
                ),
            )
        )
        await session.commit()
    return capture_id


async def _deadline_breach_alerts(session_factory: async_sessionmaker) -> list[Alert]:
    async with session_factory() as session:
        result = await session.execute(select(Alert).where(Alert.kind == AlertKind.DEADLINE_BREACH))
        return list(result.scalars().all())


@pytest.mark.xfail(strict=True, reason="T059a not implemented yet")
async def test_deadline_breach_produces_one_row_carrying_every_offending_capture_id(
    session_factory: async_sessionmaker,
    clean_database: None,
) -> None:
    from aoe2stats_ingester.run import run_once

    profile_id = 700_000_001
    await _seed_profile(session_factory, profile_id, "Offender")

    now = datetime.now(UTC)
    offending_ids: set[str] = set()
    # Three offending captures, not two: "whatever the number" (FR-025/T059a) is a claim about
    # aggregation, not about a fixed count.
    for index, game_id in enumerate((701_000_001, 701_000_002, 701_000_003)):
        capture_id = await _seed_capture(
            session_factory,
            game_id=game_id,
            profile_id=profile_id,
            status=CaptureStatus.PENDING,
            capture_deadline_at=now - timedelta(hours=1, minutes=index),
        )
        offending_ids.add(str(capture_id))

    # A pending capture whose deadline has not yet arrived must never be swept in.
    await _seed_capture(
        session_factory,
        game_id=701_000_099,
        profile_id=profile_id,
        status=CaptureStatus.PENDING,
        capture_deadline_at=now + timedelta(days=1),
    )

    await run_once(30, trigger="test", stages=(), session_factory=session_factory)

    alerts = await _deadline_breach_alerts(session_factory)
    assert len(alerts) == 1, (
        "FR-025/T059a: whatever the number of offending captures, one run raises exactly one "
        "aggregate `deadline_breach` row — never one per capture, which would bury the alert a "
        "backlog is supposed to surface."
    )
    alert = alerts[0]
    assert alert.severity == 1, (
        "the two kinds meaning a replay is gone or about to be are severity 1"
    )
    assert alert.detail is not None
    carried_ids = set(alert.detail.get("capture_ids", []))
    assert carried_ids == offending_ids, (
        "the single alert must carry every offending capture's id, not merely the first one found, "
        "and none belonging to the capture whose deadline has not yet arrived"
    )

    async with session_factory() as session:
        result = await session.execute(select(IngestRun).order_by(IngestRun.started_at.desc()))
        ingest_runs = list(result.scalars().all())
    assert ingest_runs, "run_once (T059) must open an `ingest_runs` row before doing any work"
    assert alert.ingest_run_id == ingest_runs[0].id, (
        "the alert must carry the real `ingest_run_id` of the run that raised it (T059a), so it is "
        "counted in that row's `alerts_raised` rather than left orphaned"
    )


@pytest.mark.xfail(strict=True, reason="T059a not implemented yet")
async def test_deadline_breach_is_not_raised_for_stored_unavailable_or_quarantined_captures(
    session_factory: async_sessionmaker,
    clean_database: None,
) -> None:
    from aoe2stats_ingester.run import run_once

    profile_id = 700_000_002
    await _seed_profile(session_factory, profile_id, "Archived")

    past_deadline = datetime.now(UTC) - timedelta(days=1)
    for game_id, status in (
        (702_000_001, CaptureStatus.STORED),
        (702_000_002, CaptureStatus.UNAVAILABLE),
        (702_000_003, CaptureStatus.QUARANTINED),
    ):
        await _seed_capture(
            session_factory,
            game_id=game_id,
            profile_id=profile_id,
            status=status,
            capture_deadline_at=past_deadline,
        )

    await run_once(30, trigger="test", stages=(), session_factory=session_factory)

    alerts = await _deadline_breach_alerts(session_factory)
    assert alerts == [], (
        "a capture that is `stored`, `unavailable` or `quarantined` has already been resolved one "
        "way or another and must never trigger `deadline_breach`, even with its deadline in the "
        "past (FR-025) — this is the entire reason the check reads `status`, not merely "
        "`capture_deadline_at`"
    )


@pytest.mark.xfail(strict=True, reason="T059a not implemented yet")
async def test_deadline_breach_fires_at_the_capture_deadline_and_not_before(
    session_factory: async_sessionmaker,
    clean_database: None,
) -> None:
    """The boundary itself, and the distinction from `expired_capture` (T056/T047) stated
    concretely: a capture one minute past its own `capture_deadline_at` is already breached, no
    matter how far that is from the source's ~31-day retention window, and a capture one minute
    short of its deadline is not breached yet. A check keyed to some expiry-style margin instead of
    `capture_deadline_at` itself would get either half of this wrong.
    """
    from aoe2stats_ingester.run import run_once

    profile_id = 700_000_003
    await _seed_profile(session_factory, profile_id, "Boundary")

    now = datetime.now(UTC)
    breached_id = await _seed_capture(
        session_factory,
        game_id=703_000_001,
        profile_id=profile_id,
        status=CaptureStatus.PENDING,
        capture_deadline_at=now - timedelta(minutes=1),
    )
    await _seed_capture(
        session_factory,
        game_id=703_000_002,
        profile_id=profile_id,
        status=CaptureStatus.PENDING,
        capture_deadline_at=now + timedelta(minutes=1),
    )

    await run_once(30, trigger="test", stages=(), session_factory=session_factory)

    alerts = await _deadline_breach_alerts(session_factory)
    assert len(alerts) == 1
    assert alerts[0].detail is not None
    assert set(alerts[0].detail.get("capture_ids", [])) == {str(breached_id)}, (
        "the alert fires the moment `capture_deadline_at` (day 21) has passed, for exactly the "
        "capture whose deadline actually has — the other capture, one minute short of its own "
        "deadline, must not be swept in early, and this alert must never wait for anything "
        "resembling the source's ~31-day retention expiry"
    )
