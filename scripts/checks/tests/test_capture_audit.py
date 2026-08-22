"""Tests for the nightly capture audit (T061): `expired_total`, the deadline-breach mirror, and
SC-002's trailing-window p95 lag — see `capture_audit.py`'s own module docstring for why all three
live in one script and why the second overlaps `run.py`'s own `_raise_deadline_breach_alert` (T059a)
by design rather than reading `alerts` directly.

Every test below runs against the real throwaway database (`tests/db.py`, T015), seeding
`matches`/`replay_captures`/`ingest_runs` rows directly rather than through `run_once` — this
script reads those tables from outside the ingester, exactly as it will in production, so the tests
exercise that same outside read.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from tests.db import clean_database, database_url, db_session, engine, session_factory

from aoe2stats_storage.models import (
    AoeProfile,
    CaptureSource,
    CaptureStatus,
    IngestRun,
    Match,
    ReplayCapture,
)

# See scripts/checks/tests/test_cron_liveness.py for why these are re-exported this way.
__all__ = ["clean_database", "database_url", "db_session", "engine", "session_factory"]

_LEADERBOARD_ID = 3


async def _seed_capture(
    session: AsyncSession,
    *,
    game_id: int,
    status: CaptureStatus,
    completed_at: datetime,
    capture_deadline_at: datetime,
    first_seen_at: datetime | None = None,
    stored_at: datetime | None = None,
) -> uuid.UUID:
    """One `aoe_profiles` row, one `matches` row and one `replay_captures` row hung off both — the
    same shape `apps/ingester/tests/test_deadline_alert.py`'s own `_seed_capture` builds, reduced
    to only the columns this audit's own queries read. `profile_id` reuses `game_id`'s own value:
    the two are unrelated primary-key spaces, and reusing it keeps every capture's profile unique
    within a test with no separate counter to keep in sync."""
    capture_id = uuid.uuid4()
    session.add(AoeProfile(profile_id=game_id, alias=f"profile-{game_id}"))
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
            profile_id=game_id,
            status=status,
            capture_deadline_at=capture_deadline_at,
            source=CaptureSource.AUTOMATIC,
            first_seen_at=first_seen_at or completed_at,
            stored_at=stored_at,
        )
    )
    await session.commit()
    return capture_id


async def _seed_ingest_run(session: AsyncSession, *, expired_total: int) -> None:
    session.add(
        IngestRun(
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            trigger="test",
            budget_seconds=240,
            expired_total=expired_total,
        )
    )
    await session.commit()


# --- expired_total --------------------------------------------------------------------------------


async def test_expired_total_is_zero_against_an_empty_ingest_runs_table(
    db_session: AsyncSession,
) -> None:
    from scripts.checks.capture_audit import expired_total

    assert await expired_total(db_session) == 0


async def test_expired_total_sums_across_every_ingest_runs_row(db_session: AsyncSession) -> None:
    from scripts.checks.capture_audit import expired_total

    await _seed_ingest_run(db_session, expired_total=0)
    await _seed_ingest_run(db_session, expired_total=2)
    await _seed_ingest_run(db_session, expired_total=1)

    assert await expired_total(db_session) == 3, (
        "constitution I: a single non-zero cycle is a real loss and must not be shadowed by "
        "every other run's own zero — the audit sums across the whole table, not the newest row"
    )


# --- captures pending past their own capture_deadline_at ------------------------------------------


async def test_captures_pending_past_deadline_finds_an_unresolved_capture_past_its_own_deadline(
    db_session: AsyncSession,
) -> None:
    from scripts.checks.capture_audit import captures_pending_past_deadline

    now = datetime.now(UTC)
    offending_id = await _seed_capture(
        db_session,
        game_id=910_000_001,
        status=CaptureStatus.PENDING,
        completed_at=now - timedelta(days=22),
        capture_deadline_at=now - timedelta(hours=1),
    )

    overdue = await captures_pending_past_deadline(db_session, now=now)

    assert [capture.id for capture in overdue] == [offending_id]


async def test_captures_pending_past_deadline_excludes_stored_unavailable_and_quarantined(
    db_session: AsyncSession,
) -> None:
    from scripts.checks.capture_audit import captures_pending_past_deadline

    now = datetime.now(UTC)
    past_deadline = now - timedelta(hours=1)
    for index, status in enumerate(
        (CaptureStatus.STORED, CaptureStatus.UNAVAILABLE, CaptureStatus.QUARANTINED)
    ):
        await _seed_capture(
            db_session,
            game_id=911_000_001 + index,
            status=status,
            completed_at=now - timedelta(days=22),
            capture_deadline_at=past_deadline,
        )

    overdue = await captures_pending_past_deadline(db_session, now=now)

    assert overdue == [], (
        "a capture that is stored, unavailable or quarantined has already been resolved one way "
        "or another and must never count as pending, however far past its own capture_deadline_at "
        "it now sits — the same rule run.py's _raise_deadline_breach_alert applies (T059a)"
    )


async def test_captures_pending_past_deadline_ignores_a_capture_whose_deadline_has_not_arrived(
    db_session: AsyncSession,
) -> None:
    from scripts.checks.capture_audit import captures_pending_past_deadline

    now = datetime.now(UTC)
    await _seed_capture(
        db_session,
        game_id=912_000_001,
        status=CaptureStatus.PENDING,
        completed_at=now,
        capture_deadline_at=now + timedelta(days=1),
    )

    overdue = await captures_pending_past_deadline(db_session, now=now)

    assert overdue == []


# --- SC-002's trailing p95 lag ----------------------------------------------------------------


async def test_capture_lag_p95_seconds_is_none_when_nothing_to_measure(
    db_session: AsyncSession,
) -> None:
    from scripts.checks.capture_audit import capture_lag_p95_seconds

    now = datetime.now(UTC)
    result = await capture_lag_p95_seconds(
        db_session, window_start=now - timedelta(days=7), window_end=now
    )

    assert result is None


async def test_capture_lag_p95_seconds_computed_over_newly_discovered_stored_captures(
    db_session: AsyncSession,
) -> None:
    from scripts.checks.capture_audit import capture_lag_p95_seconds

    now = datetime.now(UTC)
    completed_at = now - timedelta(days=1)
    for index, lag_hours in enumerate((1, 2, 3, 4, 40)):
        await _seed_capture(
            db_session,
            game_id=920_000_001 + index,
            status=CaptureStatus.STORED,
            completed_at=completed_at,
            capture_deadline_at=completed_at + timedelta(days=21),
            first_seen_at=completed_at,
            stored_at=completed_at + timedelta(hours=lag_hours),
        )

    p95 = await capture_lag_p95_seconds(
        db_session, window_start=now - timedelta(days=7), window_end=now
    )

    assert p95 == 40 * 3600, "nearest-rank p95 over five samples is the largest one"


async def test_capture_lag_p95_seconds_excludes_captures_first_seen_more_than_48h_after_completion(
    db_session: AsyncSession,
) -> None:
    """The backfill/reconciliation-catch-up exclusion, verbatim from the module docstring: a
    capture first seen more than 48 h after its own match completed was already old the moment it
    was discovered, and must not drag SC-002's cadence measure toward "how far back a rescue
    reached"."""
    from scripts.checks.capture_audit import capture_lag_p95_seconds

    now = datetime.now(UTC)
    # Close enough to `now` that both captures' `first_seen_at` (up to 61 h after `completed_at`
    # below) still land inside the trailing seven-day window this call asks for.
    completed_at = now - timedelta(days=5)

    # A fast, ordinary capture: well inside the trailing window and the 48 h backfill cutoff.
    await _seed_capture(
        db_session,
        game_id=930_000_001,
        status=CaptureStatus.STORED,
        completed_at=completed_at,
        capture_deadline_at=completed_at + timedelta(days=21),
        first_seen_at=completed_at + timedelta(hours=1),
        stored_at=completed_at + timedelta(hours=2),
    )
    # A backfilled capture: first seen 60 h after its match completed (past the 48 h cutoff), with
    # a huge apparent lag that would otherwise dominate the p95 the audit is supposed to report.
    await _seed_capture(
        db_session,
        game_id=930_000_002,
        status=CaptureStatus.STORED,
        completed_at=completed_at,
        capture_deadline_at=completed_at + timedelta(days=21),
        first_seen_at=completed_at + timedelta(hours=60),
        stored_at=completed_at + timedelta(hours=61),
    )

    p95 = await capture_lag_p95_seconds(
        db_session, window_start=now - timedelta(days=7), window_end=now
    )

    assert p95 == 2 * 3600, (
        "the backfilled capture's 61 h lag must be excluded entirely, leaving only the ordinary "
        "capture's own 2 h lag to measure"
    )


async def test_capture_lag_p95_seconds_ignores_captures_outside_the_trailing_window(
    db_session: AsyncSession,
) -> None:
    from scripts.checks.capture_audit import capture_lag_p95_seconds

    now = datetime.now(UTC)
    old_completed_at = now - timedelta(days=30)
    await _seed_capture(
        db_session,
        game_id=940_000_001,
        status=CaptureStatus.STORED,
        completed_at=old_completed_at,
        capture_deadline_at=old_completed_at + timedelta(days=21),
        first_seen_at=old_completed_at,
        stored_at=old_completed_at + timedelta(hours=90),
    )

    p95 = await capture_lag_p95_seconds(
        db_session, window_start=now - timedelta(days=7), window_end=now
    )

    assert p95 is None, (
        "a capture first seen 30 days ago is outside the trailing seven-day window this call "
        "asked for and must not surface in it"
    )
