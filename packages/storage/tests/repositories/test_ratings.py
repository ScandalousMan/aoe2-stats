"""Integration tests for `aoe2stats_storage.repositories.ratings.RatingsRepository` (T033).

Unlike `test_base.py`, this suite runs real queries — `record_snapshot`'s whole job is what a
plain `INSERT` does against the schema (the composite primary key, the foreign key to
`aoe_profiles`), which a fake session cannot exercise honestly. It therefore uses the T015
throwaway-database harness (`tests/db.py`) the same way `apps/api/tests` and `apps/ingester/tests`
do: every fixture below is imported, never redefined, from the one module that implements the
create/migrate/drop lifecycle. This file has no `conftest.py` of its own — importing the fixtures
directly into this module is enough for pytest to find them for the tests in it, and a
`packages/storage`-wide conftest is unnecessary machinery no other test here needs yet.

Skips locally when no Postgres is reachable, fails in CI when it should have been (see
`tests/db.py`'s own docstring for why the two are not held to the same standard).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from tests.db import clean_database, database_url, db_session, engine, session_factory

from aoe2stats_storage.models import AoeProfile, RatingSnapshot
from aoe2stats_storage.repositories.ratings import RatingsRepository

# Re-exported so ruff sees these names used, exactly as `apps/ingester/tests/conftest.py` does:
# pytest discovers a fixture imported into a module exactly as if it had been defined there.
__all__ = ["clean_database", "database_url", "db_session", "engine", "session_factory"]

_LEADERBOARD_1V1_RM = 3


async def _seed_profile(session: AsyncSession, profile_id: int) -> None:
    session.add(AoeProfile(profile_id=profile_id, alias=f"player-{profile_id}"))
    await session.flush()


async def test_record_snapshot_appends_a_row_with_the_given_fields(
    db_session: AsyncSession,
) -> None:
    await _seed_profile(db_session, profile_id=101)
    repository = RatingsRepository(db_session)
    captured_at = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)

    snapshot = await repository.record_snapshot(
        profile_id=101,
        leaderboard_id=_LEADERBOARD_1V1_RM,
        rating=1500,
        rank=42,
        wins=10,
        losses=5,
        streak=3,
        highest_rating=1550,
        captured_at=captured_at,
    )

    assert snapshot.profile_id == 101
    assert snapshot.leaderboard_id == _LEADERBOARD_1V1_RM
    assert snapshot.rating == 1500
    assert snapshot.captured_at == captured_at

    rows = (
        (await db_session.execute(select(RatingSnapshot).where(RatingSnapshot.profile_id == 101)))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].rank == 42
    assert rows[0].wins == 10
    assert rows[0].losses == 5
    assert rows[0].streak == 3
    assert rows[0].highest_rating == 1550


async def test_record_snapshot_defaults_captured_at_to_now(db_session: AsyncSession) -> None:
    await _seed_profile(db_session, profile_id=102)
    repository = RatingsRepository(db_session)
    before = datetime.now(UTC)

    snapshot = await repository.record_snapshot(
        profile_id=102, leaderboard_id=_LEADERBOARD_1V1_RM, rating=1200
    )

    after = datetime.now(UTC)
    assert before <= snapshot.captured_at <= after


async def test_repeated_resolution_with_an_unchanged_rating_still_appends_a_row(
    db_session: AsyncSession,
) -> None:
    """The design decision this repository encodes: an observation is recorded even when it
    repeats the previous one, because a skipped write would make "checked, no change" and "never
    checked" indistinguishable to anything reading the series back later.
    """
    await _seed_profile(db_session, profile_id=103)
    repository = RatingsRepository(db_session)
    first_check = datetime(2026, 8, 18, 9, 0, tzinfo=UTC)
    second_check = first_check + timedelta(days=1)

    await repository.record_snapshot(
        profile_id=103, leaderboard_id=_LEADERBOARD_1V1_RM, rating=1600, captured_at=first_check
    )
    await repository.record_snapshot(
        profile_id=103, leaderboard_id=_LEADERBOARD_1V1_RM, rating=1600, captured_at=second_check
    )

    rows = (
        (await db_session.execute(select(RatingSnapshot).where(RatingSnapshot.profile_id == 103)))
        .scalars()
        .all()
    )
    assert {row.captured_at for row in rows} == {first_check, second_check}
    assert all(row.rating == 1600 for row in rows)


async def test_record_snapshot_is_independent_per_leaderboard(db_session: AsyncSession) -> None:
    await _seed_profile(db_session, profile_id=104)
    repository = RatingsRepository(db_session)
    captured_at = datetime(2026, 8, 19, 8, 0, tzinfo=UTC)

    await repository.record_snapshot(
        profile_id=104, leaderboard_id=3, rating=1400, captured_at=captured_at
    )
    await repository.record_snapshot(
        profile_id=104, leaderboard_id=4, rating=1700, captured_at=captured_at
    )

    rows = (
        (await db_session.execute(select(RatingSnapshot).where(RatingSnapshot.profile_id == 104)))
        .scalars()
        .all()
    )
    assert {(row.leaderboard_id, row.rating) for row in rows} == {(3, 1400), (4, 1700)}


async def test_the_same_observation_recorded_twice_at_the_same_instant_violates_the_primary_key(
    db_session: AsyncSession,
) -> None:
    """`(profile_id, leaderboard_id, captured_at)` is the primary key (T007): this repository
    never deduplicates on the caller's behalf, so two calls that genuinely share the same instant
    collide at the database rather than silently overwriting one another.
    """
    await _seed_profile(db_session, profile_id=105)
    repository = RatingsRepository(db_session)
    captured_at = datetime(2026, 8, 20, 10, 0, tzinfo=UTC)

    await repository.record_snapshot(
        profile_id=105, leaderboard_id=_LEADERBOARD_1V1_RM, rating=1000, captured_at=captured_at
    )
    with pytest.raises(IntegrityError):
        await repository.record_snapshot(
            profile_id=105,
            leaderboard_id=_LEADERBOARD_1V1_RM,
            rating=1010,
            captured_at=captured_at,
        )
    # A failed flush leaves the session's transaction unusable until rolled back — the same rule
    # `session_scope` (base.py) applies at the unit-of-work boundary applies here too, since the
    # `db_session` fixture's own teardown still needs a session it can commit.
    await db_session.rollback()
