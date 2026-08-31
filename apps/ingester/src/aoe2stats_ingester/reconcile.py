"""`ReconcileStage` (T054): the second of the three stages `run.py` drains in order.

This is the mechanism the 21-day `CAPTURE_BUDGET_DAYS` is sized around (research.md §6). Discovery
(`discover.py`, T053) runs daily and enqueues a capture the moment a match is first seen; this
stage exists for everything discovery, for whatever reason, did not: the "25-day reconciliation
sweep" the edge case in spec.md names ("the match discovery source is unreachable for several days:
capture must catch up automatically, and the 21-day budget must absorb the outage without loss"),
and the "31-day backfill" a fresh link asks for via `profile_links.backfill_requested_at` (T031a,
FR-015).

**Both are the same mechanism, not two code paths.** `MatchHistoryProvider.recent_matches`
(`contracts/providers.md`) takes no window argument — it answers with whatever the source itself
considers "recent" for a profile, which is why a stale profile with weeks of untouched history and
a freshly linked profile asking for its first 31 days go through the exact same call: this stage
re-polls **every** linked profile (`DiscoverStage._linked_profile_ids`, FR-013/FR-042's condition,
unchanged by constitution IX 4.0.0 — link status alone, no objection clause) every cycle, upserts
whatever comes back the same way discovery would have, and — the one thing that is specific to a
profile carrying `backfill_requested_at` — clears that flag once, and only once, its window has
actually been swept.

**Reuse, not a second copy.** `discover.py` (T053, widened by 003's T328) already owns the
upsert logic this stage needs verbatim — the module-level `upsert_match` (FR-012, `ON CONFLICT DO
UPDATE` on `matches.game_id`), `touch_aoe_profile` and `upsert_match_player`, called directly
here exactly as `DiscoverStage.__call__` calls them for its own cycle, so a change to how a match
is upserted is made once, in one module, and both stages (and 003's `GET /api/players/{profile_id}/
matches`) pick it up. `_enqueue_capture` (FR-014, FR-018, the same `capture_deadline_at =
completed_at + capture_budget_days` computed once on insert) stays a `DiscoverStage` instance
method — it is not shared with 003's route, which FR-012 forbids from enqueueing a capture for a
third party at all — so this stage still holds its own `DiscoverStage` instance (constructed with
`profile_provider=None`, since reconciliation never refreshes `rating_snapshots`, only matches and
captures) for that method and for `_linked_profile_ids`/`_archiving_profile_ids`, and calls all
three directly rather than restating them. Mirroring `DiscoverStage.__call__` itself
(constitution IX 4.0.0): every linked profile is re-polled and upserted regardless of objection,
and only the capture-enqueue membership check below is narrowed to `_archiving_profile_ids` —
objection reaches capture and nothing upstream of it here either.

**A provider failure is not swallowed (FR-013, FR-024).** `test_reconcile.py`'s outage scenario is
explicit: three consecutive cycles that cannot reach the discovery source must each raise
`ProviderUnavailable` out of `__call__` rather than reporting an empty, honest-looking success —
that propagation, one level up in `run.py`, is what leaves `ingest_runs.finished_at` null instead of
a cycle that quietly did nothing. Nothing is written for a batch whose provider call failed: the
call happens before any session is opened for that batch, so a batch that never returns leaves no
half-written `matches` or `replay_captures` row behind it.

**`backfill_requested_at` is cleared only once its own batch has committed (FR-015).** Profile ids
are walked in the same `iter_within_budget`-gated batches discovery uses, and the flag for every
profile in a batch is cleared in the *same* `session_scope` commit as that batch's matches and
captures — never before the provider call for that batch has succeeded, and never for a batch the
budget never got around to. An interrupted cycle therefore leaves every not-yet-swept profile's flag
exactly as it was, so the next cycle repeats that profile's window instead of silently skipping it,
which is the one property FR-015 asks for by name.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from sqlalchemy import CursorResult, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_ingester.budget import Budget, iter_within_budget
from aoe2stats_ingester.discover import (
    _DISCOVERY_BATCH_SIZE,
    DiscoverStage,
    _chunk,
    touch_aoe_profile,
    upsert_match,
    upsert_match_player,
)
from aoe2stats_providers.base import MatchHistoryProvider
from aoe2stats_storage.models import ProfileLink
from aoe2stats_storage.repositories.base import session_scope


class ReconcileStage:
    """A `Stage` (`aoe2stats_ingester.run.Stage`): the 25-day reconciliation sweep and the 31-day
    backfill, over every linked user's every linked profile. See the module docstring for why
    the two are the same pass rather than two code paths.
    """

    name = "reconcile"

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        match_history_provider: MatchHistoryProvider,
        capture_budget_days: int,
        batch_size: int = _DISCOVERY_BATCH_SIZE,
    ) -> None:
        self._session_factory = session_factory
        self._match_history_provider = match_history_provider
        self._capture_budget_days = capture_budget_days
        self._batch_size = batch_size
        # See the module docstring: reused for its upsert/enqueue helpers and its linked/archiving
        # profile queries, never for its own `__call__` — that method's batching/reporting shape is
        # discovery's, not reconciliation's (no rating refresh, no swallowed provider failure).
        self._discover = DiscoverStage(
            session_factory=session_factory,
            match_history_provider=match_history_provider,
            capture_budget_days=capture_budget_days,
            batch_size=batch_size,
        )

    async def __call__(self, budget: Budget) -> Mapping[str, Any]:
        profile_ids = await self._discover._linked_profile_ids()
        # Same rule, same reason, as `DiscoverStage.__call__`'s own `archiving_profile_ids`
        # (`discover.py`, constitution IX 4.0.0): whether a discovered match's participant gets a
        # `replay_captures` row is checked against the *whole* cycle's archiving set — every linked
        # profile minus one whose user has objected — never against whichever batch happened to
        # trigger the fetch. Two profiles sharing a match can land in different batches
        # (`test_shared_match.py`), and here the two batches can even disagree about whether the
        # match is "recent" at all — a source that answers per profile can return it for one
        # participant's batch and not the other's, once it has aged out of that other participant's
        # own recent-history window (T054b). This sweep exists to catch what discovery missed
        # (FR-015); scoping the check to the batch would silently drop exactly the case it exists
        # for.
        archiving_profile_ids = set(await self._discover._archiving_profile_ids())

        profiles_polled = 0
        matches_discovered = 0
        captures_enqueued = 0
        backfills_cleared = 0

        for batch in iter_within_budget(list(_chunk(profile_ids, self._batch_size)), budget):
            profiles_polled += len(batch)

            # Deliberately uncaught: see the module docstring. A source unreachable for this batch
            # must fail the whole cycle, not be absorbed into a report that looks like success.
            raw_matches = await self._match_history_provider.recent_matches(batch)

            async with session_scope(self._session_factory) as session:
                for raw_match in raw_matches:
                    await upsert_match(session, raw_match)
                    matches_discovered += 1
                    for player_profile_id in raw_match.player_profile_ids:
                        await touch_aoe_profile(session, player_profile_id)
                        await upsert_match_player(session, raw_match, player_profile_id)
                        if player_profile_id in archiving_profile_ids:
                            enqueued = await self._discover._enqueue_capture(
                                session, raw_match, player_profile_id
                            )
                            if enqueued:
                                captures_enqueued += 1

                # FR-015: cleared in the same commit as this batch's matches and captures, and only
                # for the profiles this batch actually swept — see the module docstring.
                backfills_cleared += await self._clear_backfill_flags(session, batch)

        return {
            "profiles_polled": profiles_polled,
            "matches_discovered": matches_discovered,
            "captures_enqueued": captures_enqueued,
            "backfills_cleared": backfills_cleared,
        }

    async def _clear_backfill_flags(self, session: AsyncSession, profile_ids: Sequence[int]) -> int:
        """Clear `backfill_requested_at` on every still-active link among `profile_ids` that
        carries it. Scoped to `unlinked_at IS NULL` so a link unlinked between requesting the
        backfill and this sweep running does not have a stale flag revived by some later relink of
        the same profile (the partial unique index in `models.py` lets that relink reuse the row).
        """
        statement = (
            update(ProfileLink)
            .where(ProfileLink.profile_id.in_(profile_ids))
            .where(ProfileLink.unlinked_at.is_(None))
            .where(ProfileLink.backfill_requested_at.is_not(None))
            .values(backfill_requested_at=None)
        )
        result = cast(CursorResult[Any], await session.execute(statement))
        return result.rowcount or 0
