"""The claim/lease mechanism for `match_analyses` (T361), R6/R12 and `data-model.md`'s
`match_analyses` section.

**`running` is a lease, not a liveness signal (R6).** A serverless invocation that dies mid-parse
leaves the row `running` with a `lease_expires_at` in the past; nothing on this platform is able to
notice that death and clean up after it (no `waitUntil`, no background sweep — FR-044). The only
honest reading of `running` is therefore "a lease was taken, and it may or may not still hold" —
never "work is happening right now". Every transition below is written against that reading: a
`running` row is claimable in fact the moment `lease_expires_at <= now`, regardless of how recently
it looked busy.

**Exclusivity is `SELECT ... FOR UPDATE SKIP LOCKED`**, exactly as `apps/ingester/src/
aoe2stats_ingester/capture.py`'s `_claim_batch` already does for `replay_captures` (R12: "the claim
mechanism is 001's, deliberately unchanged") — an inner `SELECT` picks the one eligible, unlocked
row and skips it entirely if another transaction already holds its lock, and an outer `UPDATE ...
WHERE game_id IN (<that SELECT>)` performs the claim atomically: a concurrent caller racing for the
same row either sees it disappear from the eligible set (locked) or never sees it become eligible in
the first place (still `running` under a live lease).

**`claim_for_analysis` creates the row it does not find** (R12: "created by whoever asks first" —
a claim is itself an ask, and the row's primary key on `game_id` alone is what makes this idempotent
even under a concurrent double-ask: `INSERT ... ON CONFLICT (game_id) DO NOTHING` either creates the
fresh `queued` row this call goes on to claim, or no-ops because another caller's insert (or the
admission gate's, elsewhere) already won that race, and either way the claim step right after reads
whatever row now exists).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_storage.models import MatchAnalysis, MatchAnalysisState


@dataclass(frozen=True)
class ClaimOutcome:
    """`claimed=True` means this call just took (or re-took) the lease: `state` is now `running`,
    `claimed_at`/`lease_expires_at`/`attempts` were all just moved. `claimed=False` means the row
    is `running` under a lease that has not yet expired — someone else is doing the work, or
    recently was — or was locked by a concurrent claim attempt still in flight; either way, this
    call touched nothing and reports the row exactly as it stood (FR-038: the second asker joins
    the existing row and starts no second parse)."""

    claimed: bool
    state: MatchAnalysisState
    attempts: int
    claimed_at: datetime | None
    lease_expires_at: datetime | None


async def claim_for_analysis(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    game_id: int,
    point_of_view_profile_id: int,
    requested_by_user_id: UUID | None,
    lease_seconds: int,
    now: datetime,
) -> ClaimOutcome:
    """Claim `match_analyses.game_id == game_id` for analysis, or report it as it stands if this
    call cannot win it.

    A row is eligible to be claimed when it is `queued`, or `running` under a lease that has
    already expired (`lease_expires_at <= now` — R6: an expired lease is claimable in fact
    regardless of its name). Winning the claim sets `state=running`, `claimed_at=now`,
    `lease_expires_at=now + lease_seconds`, and increments `attempts` by one — a re-claim of an
    abandoned lease is a new attempt, not a continuation of the one that was dropped
    (`data-model.md`'s retry bound). `point_of_view_profile_id` and `requested_by_user_id` are
    recorded against the caller now driving the work.

    Commits before returning either way, so the row a caller reads back (whether it won or not) is
    always the current, durable state.
    """
    eligible_game_ids = (
        select(MatchAnalysis.game_id)
        .where(
            MatchAnalysis.game_id == game_id,
            or_(
                MatchAnalysis.state == MatchAnalysisState.QUEUED,
                and_(
                    MatchAnalysis.state == MatchAnalysisState.RUNNING,
                    MatchAnalysis.lease_expires_at.is_not(None),
                    MatchAnalysis.lease_expires_at <= now,
                ),
            ),
        )
        .with_for_update(skip_locked=True)
    )

    statement = (
        update(MatchAnalysis)
        .where(MatchAnalysis.game_id.in_(eligible_game_ids))
        .values(
            state=MatchAnalysisState.RUNNING,
            point_of_view_profile_id=point_of_view_profile_id,
            requested_by_user_id=requested_by_user_id,
            claimed_at=now,
            lease_expires_at=now + timedelta(seconds=lease_seconds),
            attempts=MatchAnalysis.attempts + 1,
        )
        .returning(
            MatchAnalysis.state,
            MatchAnalysis.attempts,
            MatchAnalysis.claimed_at,
            MatchAnalysis.lease_expires_at,
        )
    )

    insert_if_missing = (
        pg_insert(MatchAnalysis)
        .values(
            game_id=game_id,
            state=MatchAnalysisState.QUEUED,
            point_of_view_profile_id=point_of_view_profile_id,
            requested_by_user_id=requested_by_user_id,
        )
        .on_conflict_do_nothing(index_elements=[MatchAnalysis.game_id])
    )

    async with session_factory() as session:
        await session.execute(insert_if_missing)
        result = await session.execute(statement)
        claimed_row = result.one_or_none()
        if claimed_row is not None:
            await session.commit()
            state, attempts, claimed_at, lease_expires_at = claimed_row
            return ClaimOutcome(
                claimed=True,
                state=state,
                attempts=attempts,
                claimed_at=claimed_at,
                lease_expires_at=lease_expires_at,
            )

        # Either the row is locked by another in-flight claim attempt (skipped, not selected —
        # this transaction never blocked on it and never touched it), or it is `running` under a
        # lease that has not expired. Either way this call won nothing; a plain, non-locking read
        # reports the row exactly as it currently stands (Postgres read-committed sees the last
        # *committed* values regardless of an uncommitted lock held elsewhere, and never blocks
        # behind one).
        current = await session.execute(
            select(
                MatchAnalysis.state,
                MatchAnalysis.attempts,
                MatchAnalysis.claimed_at,
                MatchAnalysis.lease_expires_at,
            ).where(MatchAnalysis.game_id == game_id)
        )
        row = current.one_or_none()
        await session.commit()
        if row is None:  # pragma: no cover - defensive: the insert above just guaranteed this row
            raise LookupError(f"no match_analyses row for game_id={game_id} after insert-or-claim")
        state, attempts, claimed_at, lease_expires_at = row
        return ClaimOutcome(
            claimed=False,
            state=state,
            attempts=attempts,
            claimed_at=claimed_at,
            lease_expires_at=lease_expires_at,
        )
