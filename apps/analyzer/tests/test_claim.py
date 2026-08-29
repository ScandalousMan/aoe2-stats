"""Claim and lease tests for `apps/analyzer/src/aoe2stats_analyzer/claim.py` (T360), which does
not exist yet — every test below imports it *inside* its own body, never at module scope, so a
missing module is a per-test `xfail`, not a collection error that takes the whole workspace suite
down (`.claude/skills` / CLAUDE.md's "test-first tasks" note, and the exact shape `apps/ingester/
tests/test_interruption.py` already uses for the same reason).

**The contract this file assumes**, for whoever lands T361 — `data-model.md`'s `match_analyses`
section and R6/R12 of `research.md` name the shape but not a function signature, so this is the one
this suite exercises and T361 must match:

- A `match_analyses` row already exists for the `game_id` under test (creating it — R12's "created
  by whoever asks first" — is a separate concern, presumably T359's admission gate or a sibling
  helper; this file seeds the row directly with `MatchAnalysis` where a test needs one already
  `queued` or already `running`, and only asks `claim.py` to *claim* it).
- `claim_for_analysis(session_factory, *, game_id, point_of_view_profile_id,
  requested_by_user_id, lease_seconds, now) -> ClaimOutcome` is the one entry point: it opens its
  own session, claims with `SELECT ... FOR UPDATE SKIP LOCKED` exactly as `apps/ingester/src/
  aoe2stats_ingester/capture.py`'s `_claim_batch` already does for `replay_captures` (R12: "The
  claim mechanism is 001's, deliberately unchanged"), and commits before returning.
- `ClaimOutcome` carries at least `claimed: bool`, `state: MatchAnalysisState`, `attempts: int`,
  `claimed_at: datetime | None` and `lease_expires_at: datetime | None` — enough to tell a caller
  whether it won the lease or is joining someone else's.
- `claimed=True` means this call took (or re-took) the lease: `state` becomes `running`,
  `claimed_at=now`, `lease_expires_at=now + lease_seconds`, `attempts` incremented by one — whether
  the row was freshly `queued` or `running` under an already-expired lease (R6: `running` means *a
  lease was taken recently*, never *work is happening now*, so an expired one is claimable in fact
  regardless of its name).
- `claimed=False` means the row is `running` under a lease that has **not** expired: someone else
  is doing the work, or recently was, and this call must not touch `claimed_at`, `lease_expires_at`
  or `attempts` — it only reports the row as it stands, which is what "joins the existing row and
  starts no second parse" (FR-038) means in practice.

The exclusivity test below never actually calls `claim_for_analysis` twice at once — a real race
would be non-deterministic to assert against. It instead holds the row locked with a plain
`SELECT ... FOR UPDATE` (no `SKIP LOCKED`) from one session, exactly as a real concurrent claim
attempt would leave it mid-transaction, and then calls the real `claim_for_analysis` from a second,
independent connection while that lock is still held — the deterministic way to prove
`claim_for_analysis` itself never blocks waiting for the row (which `SKIP LOCKED` guarantees by
definition) and never claims a row someone else already has locked.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.db import clean_database, database_url, db_session, engine, session_factory

from aoe2stats_storage.models import Match, MatchAnalysis, MatchAnalysisState

# Re-exported so ruff sees these names used: pytest discovers a fixture imported into a test
# module exactly as if it had been defined there (see `apps/ingester/tests/conftest.py`'s own
# docstring on this, and `apps/ingester/tests/test_interruption.py`'s identical re-export).
__all__ = ["clean_database", "database_url", "db_session", "engine", "session_factory"]

_GAME_ID = 900_000_001
_POV_PROFILE_ID = 12_345_678
_INGESTER_SRC = Path(__file__).resolve().parents[2] / "ingester" / "src" / "aoe2stats_ingester"


async def _seed_match(session: AsyncSession, *, game_id: int, completed_at: datetime) -> None:
    session.add(
        Match(
            game_id=game_id,
            leaderboard_id=3,
            map_name="Arabia",
            patch="af1",
            started_at=completed_at - timedelta(minutes=30),
            completed_at=completed_at,
            duration_seconds=1800,
            source="relic",
            raw_payload={"matchHistoryId": game_id},
        )
    )
    await session.commit()


async def _seed_match_analysis(
    session: AsyncSession,
    *,
    game_id: int,
    state: MatchAnalysisState,
    requested_at: datetime,
    claimed_at: datetime | None = None,
    lease_expires_at: datetime | None = None,
    attempts: int = 0,
) -> None:
    session.add(
        MatchAnalysis(
            game_id=game_id,
            state=state,
            point_of_view_profile_id=_POV_PROFILE_ID,
            requested_at=requested_at,
            claimed_at=claimed_at,
            lease_expires_at=lease_expires_at,
            attempts=attempts,
        )
    )
    await session.commit()


@pytest.mark.xfail(strict=True, reason="T361 not implemented yet")
async def test_claim_is_exclusive_under_for_update_skip_locked(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    from aoe2stats_analyzer.claim import claim_for_analysis

    now = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)
    async with session_factory() as setup_session:
        await _seed_match(setup_session, game_id=_GAME_ID, completed_at=now - timedelta(days=1))
        await _seed_match_analysis(
            setup_session, game_id=_GAME_ID, state=MatchAnalysisState.QUEUED, requested_at=now
        )

    # Hold the row locked from an independent connection, exactly as a genuine concurrent claim
    # attempt's own uncommitted transaction would — without ever calling `claim_for_analysis`
    # itself here, so the lock is held regardless of what that function's own internals look like.
    lock_holder = session_factory()
    try:
        locked = await lock_holder.execute(
            select(MatchAnalysis.game_id).where(MatchAnalysis.game_id == _GAME_ID).with_for_update()
        )
        assert locked.scalar_one() == _GAME_ID  # the lock is confirmed held before proceeding

        # A real claim attempt against the still-locked row must not block and must not win it —
        # `SKIP LOCKED` is what makes both true at once.
        outcome_while_locked = await claim_for_analysis(
            session_factory,
            game_id=_GAME_ID,
            point_of_view_profile_id=_POV_PROFILE_ID,
            requested_by_user_id=None,
            lease_seconds=60,
            now=now,
        )
        assert outcome_while_locked.claimed is False
    finally:
        await lock_holder.rollback()
        await lock_holder.close()

    # The lock is released now — the same row is claimable, and by exactly one caller.
    outcome_after_release = await claim_for_analysis(
        session_factory,
        game_id=_GAME_ID,
        point_of_view_profile_id=_POV_PROFILE_ID,
        requested_by_user_id=None,
        lease_seconds=60,
        now=now,
    )
    assert outcome_after_release.claimed is True
    assert outcome_after_release.state == MatchAnalysisState.RUNNING
    assert outcome_after_release.attempts == 1


@pytest.mark.xfail(strict=True, reason="T361 not implemented yet")
async def test_an_expired_lease_is_reclaimable(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    from aoe2stats_analyzer.claim import claim_for_analysis

    requested_at = datetime(2026, 8, 29, 8, 0, tzinfo=UTC)
    abandoned_claimed_at = requested_at
    abandoned_lease_expires_at = requested_at + timedelta(seconds=60)
    now = abandoned_lease_expires_at + timedelta(minutes=10)  # well past the lease

    async with session_factory() as setup_session:
        await _seed_match(
            setup_session, game_id=_GAME_ID, completed_at=requested_at - timedelta(days=1)
        )
        await _seed_match_analysis(
            setup_session,
            game_id=_GAME_ID,
            state=MatchAnalysisState.RUNNING,
            requested_at=requested_at,
            claimed_at=abandoned_claimed_at,
            lease_expires_at=abandoned_lease_expires_at,
            attempts=1,
        )

    outcome = await claim_for_analysis(
        session_factory,
        game_id=_GAME_ID,
        point_of_view_profile_id=_POV_PROFILE_ID,
        requested_by_user_id=None,
        lease_seconds=60,
        now=now,
    )

    assert outcome.claimed is True
    assert outcome.state == MatchAnalysisState.RUNNING
    assert outcome.claimed_at == now
    assert outcome.lease_expires_at == now + timedelta(seconds=60)
    # Bounds the retry of a transient failure (data-model.md) — a reclaim is a new attempt, not a
    # continuation of the abandoned one.
    assert outcome.attempts == 2


@pytest.mark.xfail(strict=True, reason="T361 not implemented yet")
async def test_a_second_asker_under_a_live_lease_joins_the_row_and_starts_no_second_parse(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    from aoe2stats_analyzer.claim import claim_for_analysis

    now = datetime(2026, 8, 29, 9, 0, tzinfo=UTC)
    async with session_factory() as setup_session:
        await _seed_match(setup_session, game_id=_GAME_ID, completed_at=now - timedelta(days=2))
        await _seed_match_analysis(
            setup_session, game_id=_GAME_ID, state=MatchAnalysisState.QUEUED, requested_at=now
        )

    first_asker = await claim_for_analysis(
        session_factory,
        game_id=_GAME_ID,
        point_of_view_profile_id=_POV_PROFILE_ID,
        requested_by_user_id=None,
        lease_seconds=300,
        now=now,
    )
    assert first_asker.claimed is True
    assert first_asker.attempts == 1

    # The second asker arrives seconds later, well inside the first asker's still-live lease.
    second_asker = await claim_for_analysis(
        session_factory,
        game_id=_GAME_ID,
        point_of_view_profile_id=_POV_PROFILE_ID,
        requested_by_user_id=None,
        lease_seconds=300,
        now=now + timedelta(seconds=5),
    )

    assert second_asker.claimed is False
    assert second_asker.state == MatchAnalysisState.RUNNING
    # Joining the existing row, not starting a second parse: nothing about the lease or the
    # attempt counter moved for the second asker's arrival.
    assert second_asker.attempts == first_asker.attempts
    assert second_asker.claimed_at == first_asker.claimed_at
    assert second_asker.lease_expires_at == first_asker.lease_expires_at


@pytest.mark.xfail(strict=True, reason="T361 not implemented yet")
async def test_nothing_sweeps_an_expired_lease(
    session_factory: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
    clean_database: None,
) -> None:
    """FR-044: no cron, no sweep, ever collects an abandoned analysis — the next *viewer's
    request* is the only thing that reclaims it (R6). This is exercised two ways: running the
    ingester's actual shared entrypoint over the abandoned row and confirming it is byte-for-byte
    untouched, and confirming the ingester's own source tree carries no reference to
    `match_analyses` at all — the second is what catches a future sweep added as a stage nobody
    wired into this particular call, which the first alone could not.
    """
    from aoe2stats_analyzer.claim import claim_for_analysis
    from aoe2stats_ingester.run import run_once

    # A lease claimed and then abandoned: whoever held it never came back, and its lease expired
    # long ago (`lease_seconds=1`, `now` far in the past relative to "today").
    abandon_at = datetime(2020, 1, 1, tzinfo=UTC)
    async with session_factory() as setup_session:
        await _seed_match(
            setup_session, game_id=_GAME_ID, completed_at=abandon_at - timedelta(days=1)
        )
    seeded = await claim_for_analysis(
        session_factory,
        game_id=_GAME_ID,
        point_of_view_profile_id=_POV_PROFILE_ID,
        requested_by_user_id=None,
        lease_seconds=1,
        now=abandon_at,
    )
    assert seeded.claimed is True  # sanity: the fixture really is an abandoned, expired lease

    before = (
        await db_session.execute(select(MatchAnalysis).where(MatchAnalysis.game_id == _GAME_ID))
    ).scalar_one()
    before_snapshot = (
        before.state,
        before.claimed_at,
        before.lease_expires_at,
        before.attempts,
        before.finished_at,
        before.result_key,
        before.error_class,
    )

    await run_once(60, trigger="test", session_factory=session_factory)

    after = (
        await db_session.execute(select(MatchAnalysis).where(MatchAnalysis.game_id == _GAME_ID))
    ).scalar_one()
    after_snapshot = (
        after.state,
        after.claimed_at,
        after.lease_expires_at,
        after.attempts,
        after.finished_at,
        after.result_key,
        after.error_class,
    )
    assert after_snapshot == before_snapshot


def test_the_ingester_source_carries_no_reference_to_match_analyses() -> None:
    """A cheaper, permanent companion to the `run_once` assertion above: FR-044 is a claim about
    every future cycle, not only the one this test drives, and `run_once`'s default `stages=()`
    would pass the assertion above trivially even if a real production stage somewhere swept
    expired leases. Grepping the ingester's own source tree is the only way to test an absence
    that a single call cannot observe — the same idiom `apps/api/tests/test_favourites.py` (T344)
    uses to prove no aggregate over `profile_id` exists.

    Not marked `xfail`: this is true today (there is no `aoe2stats_analyzer` reference anywhere
    under `apps/ingester/src`, because that package does not exist as a runtime dependency of
    the ingester) and must stay true after T361 lands — a real regression, not a stand-in for a
    missing module.
    """
    forbidden = ("match_analyses", "MatchAnalysis", "aoe2stats_analyzer")
    offending: dict[str, list[str]] = {}
    for path in sorted(_INGESTER_SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        hits = [needle for needle in forbidden if needle in text]
        if hits:
            offending[str(path.relative_to(_INGESTER_SRC))] = hits

    assert offending == {}, (
        "the ingester's own source tree must never reference match_analyses/MatchAnalysis/"
        f"aoe2stats_analyzer (FR-044 — no sweep, ever): {offending}"
    )
