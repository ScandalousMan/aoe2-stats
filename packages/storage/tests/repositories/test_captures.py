"""Integration tests for `aoe2stats_storage.repositories.captures.CapturesRepository` (T081).

Same T015 throwaway-database harness `test_ratings.py` uses, imported rather than redefined (that
file's own module docstring explains why). Both branches `record_manual_upload` must cover live
here: no `replay_captures` row exists yet for `(game_id, profile_id)` (a match discovery never
enqueued, most likely because the caller linked their profile after the fact), and a row already
exists in a terminal, non-`stored` state (the rescue scenario `test_manual_upload.py`'s scenario
8.1 exercises end to end through the router — T080, not yet implemented).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.db import clean_database, database_url, db_session, engine, session_factory

from aoe2stats_storage.models import AoeProfile, CaptureSource, CaptureStatus, Match, ReplayCapture
from aoe2stats_storage.repositories.captures import CapturesRepository

# Re-exported so ruff sees these names used, exactly as `test_ratings.py` does: pytest discovers a
# fixture imported into a module exactly as if it had been defined there.
__all__ = ["clean_database", "database_url", "db_session", "engine", "session_factory"]

_LEADERBOARD_1V1_RM = 3
_CAPTURE_BUDGET_DAYS = 21


async def _seed_match_and_profile(
    session: AsyncSession, *, game_id: int, profile_id: int, completed_at: datetime
) -> None:
    session.add(AoeProfile(profile_id=profile_id, alias=f"player-{profile_id}"))
    session.add(
        Match(
            game_id=game_id,
            leaderboard_id=_LEADERBOARD_1V1_RM,
            completed_at=completed_at,
            source="relic",
            raw_payload={},
        )
    )
    await session.flush()


async def test_record_manual_upload_creates_a_row_when_none_existed(
    db_session: AsyncSession,
) -> None:
    """Discovery never enqueued a row for this pair — most likely the caller linked their profile
    after the match was already outside the automatic pipeline's own reach. `record_manual_upload`
    inserts one, `stored`, `source = 'manual'`, `capture_deadline_at` computed fresh from
    `match_completed_at` and `capture_budget_days`, the same two inputs `discover.py`'s
    `_enqueue_capture` uses for an automatic row."""
    completed_at = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
    await _seed_match_and_profile(
        db_session, game_id=500546441, profile_id=196240, completed_at=completed_at
    )
    repository = CapturesRepository(db_session)

    capture = await repository.record_manual_upload(
        game_id=500546441,
        profile_id=196240,
        object_key="replays/500546441/196240.zip",
        zip_bytes=123456,
        zip_sha256="b" * 64,
        inner_filename="AgeIIDE_Replay_500546441.aoe2record",
        inner_bytes=123000,
        validated_by="aoe2rec-py 0.1.21",
        match_completed_at=completed_at,
        capture_budget_days=_CAPTURE_BUDGET_DAYS,
    )

    assert capture.status == CaptureStatus.STORED
    assert capture.source == CaptureSource.MANUAL
    assert capture.object_key == "replays/500546441/196240.zip"
    assert capture.zip_bytes == 123456
    assert capture.zip_sha256 == "b" * 64
    assert capture.inner_filename == "AgeIIDE_Replay_500546441.aoe2record"
    assert capture.inner_bytes == 123000
    assert capture.validated_by == "aoe2rec-py 0.1.21"
    assert capture.http_status == 200
    assert capture.last_error is None
    assert capture.stored_at is not None
    assert capture.capture_deadline_at == completed_at + timedelta(days=_CAPTURE_BUDGET_DAYS)

    rows = (
        (
            await db_session.execute(
                select(ReplayCapture).where(
                    ReplayCapture.game_id == 500546441, ReplayCapture.profile_id == 196240
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1, "exactly one row for this (game_id, profile_id) pair, never a duplicate"


async def test_record_manual_upload_updates_an_existing_row_in_place(
    db_session: AsyncSession,
) -> None:
    """A rescue: the automatic pipeline already concluded `expired` for this pair, and the caller
    now supplies the bytes themselves (`test_manual_upload.py`'s scenario 8.1). The existing row is
    updated in place — never a second row — and its own `capture_deadline_at`, already fixed at
    insert time, is left untouched rather than extended by the rescue (module docstring)."""
    completed_at = datetime.now(UTC) - timedelta(days=40)
    original_deadline = completed_at + timedelta(days=_CAPTURE_BUDGET_DAYS)
    await _seed_match_and_profile(
        db_session, game_id=700200300, profile_id=900700300, completed_at=completed_at
    )
    db_session.add(
        ReplayCapture(
            game_id=700200300,
            profile_id=900700300,
            status=CaptureStatus.EXPIRED,
            capture_deadline_at=original_deadline,
            source=CaptureSource.AUTOMATIC,
            attempts=3,
        )
    )
    await db_session.commit()

    repository = CapturesRepository(db_session)
    capture = await repository.record_manual_upload(
        game_id=700200300,
        profile_id=900700300,
        object_key="replays/700200300/900700300.zip",
        zip_bytes=654321,
        zip_sha256="c" * 64,
        inner_filename="AgeIIDE_Replay_700200300.aoe2record",
        inner_bytes=654000,
        validated_by="aoe2rec-py 0.1.21",
        match_completed_at=completed_at,
        capture_budget_days=_CAPTURE_BUDGET_DAYS,
    )

    assert capture.status == CaptureStatus.STORED
    assert capture.source == CaptureSource.MANUAL
    assert capture.object_key == "replays/700200300/900700300.zip"
    assert capture.zip_sha256 == "c" * 64
    assert capture.validated_by == "aoe2rec-py 0.1.21"
    # The deadline this row was first created with survives the rescue, never recomputed.
    assert capture.capture_deadline_at == original_deadline
    # `attempts`, the automatic pipeline's own bookkeeping, is left as the prior row carried it —
    # this method never touches a column it has no manual-upload value for.
    assert capture.attempts == 3

    rows = (
        (
            await db_session.execute(
                select(ReplayCapture).where(
                    ReplayCapture.game_id == 700200300, ReplayCapture.profile_id == 900700300
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1, "the pre-existing row is updated in place, never duplicated"
