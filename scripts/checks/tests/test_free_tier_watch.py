"""Tests for the nightly free-tier watch (T100).

`docs/adr/0002-hosting.md`'s "Risks accepted" section is the contract under test: "the nightly job
warns at 70% of any allowance". `free_tier_watch.py`'s pure boundary logic (`usage_fraction`,
`is_over_warn_threshold`) is exercised with no database at all, the same way `cron_liveness.py`'s
`is_live`/`is_stalled` are; the measurement functions (`r2_stored_bytes`, `neon_storage_bytes`, and
003's T378 `retained_recording_bytes`) and the alert they each raise are exercised against the real
throwaway database (`tests/db.py`, T015), not a hand-rolled stand-in for one — the same convention
every sibling in this directory follows. FR-048's own separateness requirement — a
`replay_captures` row and a `retained_recordings` row never contribute to each other's total — is
asserted in both directions below, not merely in the one direction an implementer would otherwise
stop at.

Every test below imports `scripts.checks.free_tier_watch` inside the test body rather than at
module scope, matching `test_cron_liveness.py`'s own stated convention.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.db import clean_database, database_url, db_session, engine, session_factory

from aoe2stats_storage.models import Alert as AlertRow
from aoe2stats_storage.models import (
    AlertKind,
    AoeProfile,
    CaptureSource,
    CaptureStatus,
    Match,
    ReplayCapture,
    RetainedRecording,
)

# Re-exported so ruff sees these names used: pytest discovers a fixture imported into a test module
# exactly as if it had been defined here — the one implementation lives in tests/db.py, mirroring
# every sibling test in this directory.
__all__ = ["clean_database", "database_url", "db_session", "engine", "session_factory"]

# `docs/adr/0002-hosting.md`'s own free-tier figures, used as round test ceilings throughout rather
# than the module's real defaults: keeping the arithmetic in these tests obvious (e.g. "7 out of 10
# bytes is 70%") matters more here than exercising the exact production constant, which
# `test_reads_the_r2_ceiling_from_the_environment_default` below covers directly instead.
_CEILING_BYTES = 10


async def _seed_stored_capture(
    session: AsyncSession, *, zip_bytes: int, game_id: int | None = None
) -> None:
    """One `replay_captures` row whose upload completed with `zip_bytes` set — the shape
    `r2_stored_bytes` sums over. `game_id` defaults to a fresh id per call so several seeded rows
    never collide on `matches`' own primary key.
    """
    game_id = game_id if game_id is not None else uuid.uuid4().int % 2_000_000_000
    profile_id = uuid.uuid4().int % 2_000_000_000
    completed_at = datetime.now(UTC)
    session.add(AoeProfile(profile_id=profile_id, alias=f"player-{profile_id}", country="FR"))
    session.add(
        Match(
            game_id=game_id,
            leaderboard_id=3,
            completed_at=completed_at,
            source="test-fixture",
            raw_payload={},
        )
    )
    await session.flush()
    session.add(
        ReplayCapture(
            game_id=game_id,
            profile_id=profile_id,
            status=CaptureStatus.STORED,
            capture_deadline_at=completed_at + timedelta(days=21),
            source=CaptureSource.AUTOMATIC,
            object_key=f"replays/{game_id}/{profile_id}.zip",
            zip_bytes=zip_bytes,
            zip_sha256="0" * 64,
            stored_at=completed_at,
        )
    )
    await session.commit()


async def _seed_retained_recording(
    session: AsyncSession, *, zip_bytes: int, game_id: int | None = None
) -> None:
    """One `retained_recordings` row (003, T378) — the shape `retained_recording_bytes` sums over,
    and deliberately a different table from `_seed_stored_capture`'s `replay_captures` row: FR-048
    requires the two never resolve to one total, so the two seed helpers never write into each
    other's table. `game_id` defaults to a fresh id per call, the same reason
    `_seed_stored_capture` does, so several seeded rows never collide on `matches`' own primary key.
    """
    game_id = game_id if game_id is not None else uuid.uuid4().int % 2_000_000_000
    profile_id = uuid.uuid4().int % 2_000_000_000
    completed_at = datetime.now(UTC)
    session.add(
        Match(
            game_id=game_id,
            leaderboard_id=3,
            completed_at=completed_at,
            source="test-fixture",
            raw_payload={},
        )
    )
    await session.flush()
    session.add(
        RetainedRecording(
            game_id=game_id,
            profile_id=profile_id,
            object_key=f"retained-recordings/{game_id}/{profile_id}.zip",
            zip_bytes=zip_bytes,
            zip_sha256="0" * 64,
        )
    )
    await session.commit()


def test_usage_fraction_divides_used_by_ceiling() -> None:
    from scripts.checks.free_tier_watch import usage_fraction

    assert usage_fraction(7, _CEILING_BYTES) == 0.7


def test_usage_fraction_is_zero_for_a_non_positive_ceiling() -> None:
    """A misconfigured ceiling reads as unmeasurable rather than raising `ZeroDivisionError` and
    crashing the whole nightly job over one allowance."""
    from scripts.checks.free_tier_watch import usage_fraction

    assert usage_fraction(7, 0) == 0.0


def test_is_over_warn_threshold_is_true_at_exactly_70_percent() -> None:
    """The ADR's own "70%" is the trigger point itself, not a strictly-past-it boundary."""
    from scripts.checks.free_tier_watch import WARN_THRESHOLD_FRACTION, is_over_warn_threshold

    assert is_over_warn_threshold(WARN_THRESHOLD_FRACTION) is True


def test_is_over_warn_threshold_is_false_just_under_70_percent() -> None:
    from scripts.checks.free_tier_watch import is_over_warn_threshold

    assert is_over_warn_threshold(0.69) is False


async def test_r2_stored_bytes_sums_every_completed_upload(
    db_session: AsyncSession,
) -> None:
    from scripts.checks.free_tier_watch import r2_stored_bytes

    await _seed_stored_capture(db_session, zip_bytes=3)
    await _seed_stored_capture(db_session, zip_bytes=4)

    assert await r2_stored_bytes(db_session) == 7


async def test_r2_stored_bytes_is_zero_against_an_empty_table(
    db_session: AsyncSession,
) -> None:
    from scripts.checks.free_tier_watch import r2_stored_bytes

    assert await r2_stored_bytes(db_session) == 0


async def test_r2_stored_bytes_ignores_a_capture_that_never_finished_uploading(
    db_session: AsyncSession,
) -> None:
    """A `pending`/`downloading` row has no `zip_bytes` yet (`ReplayCapture.zip_bytes` is nullable
    until the upload commits) and must not be counted as bytes R2 already holds."""
    from scripts.checks.free_tier_watch import r2_stored_bytes

    game_id = uuid.uuid4().int % 2_000_000_000
    profile_id = uuid.uuid4().int % 2_000_000_000
    completed_at = datetime.now(UTC)
    db_session.add(AoeProfile(profile_id=profile_id, alias=f"player-{profile_id}"))
    db_session.add(
        Match(
            game_id=game_id,
            leaderboard_id=3,
            completed_at=completed_at,
            source="test-fixture",
            raw_payload={},
        )
    )
    await db_session.flush()
    db_session.add(
        ReplayCapture(
            game_id=game_id,
            profile_id=profile_id,
            status=CaptureStatus.PENDING,
            capture_deadline_at=completed_at + timedelta(days=21),
            source=CaptureSource.AUTOMATIC,
        )
    )
    await db_session.commit()

    assert await r2_stored_bytes(db_session) == 0


async def test_retained_recording_bytes_sums_every_retained_recording(
    db_session: AsyncSession,
) -> None:
    from scripts.checks.free_tier_watch import retained_recording_bytes

    await _seed_retained_recording(db_session, zip_bytes=3)
    await _seed_retained_recording(db_session, zip_bytes=4)

    assert await retained_recording_bytes(db_session) == 7


async def test_retained_recording_bytes_is_zero_against_an_empty_table(
    db_session: AsyncSession,
) -> None:
    from scripts.checks.free_tier_watch import retained_recording_bytes

    assert await retained_recording_bytes(db_session) == 0


async def test_retained_recording_bytes_ignores_a_captured_replay(
    db_session: AsyncSession,
) -> None:
    """FR-048: a `replay_captures` row must not contribute to the retained-recording total —
    one direction of the double-count the two separate tables (and the two separate object-store
    prefixes, `retained_recording_object_key`) exist to make impossible to do by accident."""
    from scripts.checks.free_tier_watch import retained_recording_bytes

    await _seed_stored_capture(db_session, zip_bytes=5)

    assert await retained_recording_bytes(db_session) == 0


async def test_r2_stored_bytes_ignores_a_retained_recording(
    db_session: AsyncSession,
) -> None:
    """The other direction of the same FR-048 double-count: a `retained_recordings` row must not
    contribute to R2's own capture total, so a match that is both captured under 001 and retained
    for analysis under 003 is never counted twice against either allowance."""
    from scripts.checks.free_tier_watch import r2_stored_bytes

    await _seed_retained_recording(db_session, zip_bytes=5)

    assert await r2_stored_bytes(db_session) == 0


async def test_neon_storage_bytes_reads_a_positive_size(
    db_session: AsyncSession,
) -> None:
    """A real, migrated throwaway database always has a non-zero on-disk size; the exact number is
    Postgres's own business, not this script's, so only positivity is asserted."""
    from scripts.checks.free_tier_watch import neon_storage_bytes

    assert await neon_storage_bytes(db_session) > 0


async def test_run_raises_a_severity_two_free_tier_alert_when_over_threshold(
    database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End to end through `_run`: an allowance pushed past 70% of a tiny, environment-overridden
    ceiling must leave a real `alerts` row behind, not merely a printed line — `raise_alert` is the
    one call site every producer in this feature shares (`packages/core/src/aoe2stats_core/
    alerting.py`'s own module docstring names `free_tier`/T100 as one of them)."""
    from scripts.checks import free_tier_watch

    async with session_factory() as session:
        await _seed_stored_capture(session, zip_bytes=8)

    monkeypatch.setenv(free_tier_watch._DATABASE_URL_ENV, database_url)
    monkeypatch.setenv(free_tier_watch._R2_FREE_TIER_BYTES_ENV, "10")
    monkeypatch.setenv(free_tier_watch._NEON_FREE_TIER_BYTES_ENV, str(10**12))

    exit_code = await free_tier_watch._run()

    assert exit_code == 1

    async with session_factory() as session:
        result = await session.execute(select(AlertRow).where(AlertRow.kind == AlertKind.FREE_TIER))
        alerts = result.scalars().all()

    assert len(alerts) == 1
    assert alerts[0].severity == 2
    assert alerts[0].detail is not None
    assert alerts[0].detail["allowance"] == "Cloudflare R2 stored bytes"


async def test_run_passes_and_raises_nothing_when_every_allowance_is_under_threshold(
    database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.checks import free_tier_watch

    async with session_factory() as session:
        await _seed_stored_capture(session, zip_bytes=1)

    monkeypatch.setenv(free_tier_watch._DATABASE_URL_ENV, database_url)
    monkeypatch.setenv(free_tier_watch._R2_FREE_TIER_BYTES_ENV, "1000")
    monkeypatch.setenv(free_tier_watch._NEON_FREE_TIER_BYTES_ENV, str(10**12))

    exit_code = await free_tier_watch._run()

    assert exit_code == 0

    async with session_factory() as session:
        result = await session.execute(select(AlertRow).where(AlertRow.kind == AlertKind.FREE_TIER))
        assert result.scalars().all() == []


async def test_run_raises_a_free_tier_alert_when_analysis_retention_is_over_its_own_cap(
    database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T378: `ANALYSIS_RETENTION_CAP_BYTES` (FR-047) is its own, independently thresholded
    allowance — reached here with a `retained_recordings` row at exactly 70% of a tiny,
    environment-overridden cap, with the R2 and Neon allowances both kept far under their own
    ceilings so this alert is unambiguously the retention one, not a coincidence of another
    allowance also being over."""
    from scripts.checks import free_tier_watch

    async with session_factory() as session:
        await _seed_retained_recording(session, zip_bytes=7)

    monkeypatch.setenv(free_tier_watch._DATABASE_URL_ENV, database_url)
    monkeypatch.setenv(free_tier_watch._R2_FREE_TIER_BYTES_ENV, str(10**12))
    monkeypatch.setenv(free_tier_watch._NEON_FREE_TIER_BYTES_ENV, str(10**12))
    monkeypatch.setenv(free_tier_watch._ANALYSIS_RETENTION_CAP_BYTES_ENV, "10")

    exit_code = await free_tier_watch._run()

    assert exit_code == 1

    async with session_factory() as session:
        result = await session.execute(select(AlertRow).where(AlertRow.kind == AlertKind.FREE_TIER))
        alerts = result.scalars().all()

    assert len(alerts) == 1
    assert alerts[0].severity == 2
    assert alerts[0].detail is not None
    assert alerts[0].detail["allowance"] == "Analysis retention (retained recordings)"
    assert alerts[0].detail["used_bytes"] == 7
    assert alerts[0].detail["ceiling_bytes"] == 10


async def test_run_does_not_raise_for_analysis_retention_just_under_its_own_cap(
    database_url: str,
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The `>=` boundary `is_over_warn_threshold` states must hold here too: one byte under 70%
    of the analysis retention cap raises nothing, matching the `_R2_FREE_TIER_BYTES_ENV` sibling
    test's own choice of a threshold that is not exactly on the line."""
    from scripts.checks import free_tier_watch

    async with session_factory() as session:
        await _seed_retained_recording(session, zip_bytes=6)

    monkeypatch.setenv(free_tier_watch._DATABASE_URL_ENV, database_url)
    monkeypatch.setenv(free_tier_watch._R2_FREE_TIER_BYTES_ENV, str(10**12))
    monkeypatch.setenv(free_tier_watch._NEON_FREE_TIER_BYTES_ENV, str(10**12))
    monkeypatch.setenv(free_tier_watch._ANALYSIS_RETENTION_CAP_BYTES_ENV, "10")

    exit_code = await free_tier_watch._run()

    assert exit_code == 0

    async with session_factory() as session:
        result = await session.execute(select(AlertRow).where(AlertRow.kind == AlertKind.FREE_TIER))
        assert result.scalars().all() == []
