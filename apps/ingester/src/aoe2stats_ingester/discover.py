"""`DiscoverStage` (T053): the first of the three stages `run.py` drains in order.

One cycle of discovery does three things, in this order, over the same set of profiles:

1. Refresh `rating_snapshots` for every consenting user's every linked profile (FR-009), through
   whatever `ProfileProvider` the caller injects.
2. Fetch recent matches for that same set of profiles through `MatchHistoryProvider.recent_matches`
   (FR-013), upserting `matches` and `match_players`.
3. Enqueue a `replay_captures` row for every one of *those* profiles that took part in a discovered
   match, with `capture_deadline_at = completed_at + CAPTURE_BUDGET_DAYS` computed once, on insert,
   from `capture_budget_days` — a plain constructor argument this stage never reads from a literal,
   so the run that lowers `CAPTURE_BUDGET_DAYS` changes every capture enqueued from that moment on
   (FR-014).

**Consent is a `WHERE` clause, not a branch (FR-013, FR-034, FR-035, FR-042).**
`_consenting_profile_ids` is the *only* place this module decides whose profiles exist for this
cycle: a user who never granted consent, or who granted it and then withdrew it, never appears in
the list it returns, so neither the rating refresh nor the match-history call nor the enqueue step
ever sees that user's profile at all — there is no later `if not consented: continue` for a new
code path to route around. The predicate is the two clauses data-model.md states —
`ingest_consent_at IS NOT NULL AND ingest_consent_withdrawn_at IS NULL` — never the first clause
alone: T032 deliberately never clears `ingest_consent_at` on withdrawal, keeping it as the record
of what was agreed and when, so a query that tests only that column would answer "consented"
forever from the first grant onward and FR-035's withdrawal would do nothing at all to ingestion
(T053a). FR-042 is the same query's other half: every linked profile a consenting user holds is
selected, not only the one `is_primary` marks, because `profile_links.unlinked_at IS NULL` is the
only per-link condition, and nothing here also filters on `is_primary`.

**Every write below is an upsert, never a plain `INSERT`.** A discovery cycle runs daily against
profiles whose match history and roster keep changing, and the same match is very often discovered
twice in one cycle — once through each of two consenting players who shared it (`test_shared_match.
py`) — long before the 25-day reconciliation sweep (T054) would otherwise notice a duplicate.
`ON CONFLICT DO UPDATE` on `matches.game_id` keeps the row current (constitution IV: `raw_payload`
is the provider's response, unmodified, replaced wholesale rather than merged field by field, since
merging would silently keep a stale value the provider has since corrected); `ON CONFLICT DO
NOTHING` on `match_players`' and `replay_captures`' composite keys makes a repeat discovery of the
same participant, or the same `(game_id, profile_id)` capture, a no-op rather than an error — which
is also what keeps `capture_deadline_at` "computed once on insert, never recomputed" true across
however many times the same match is rediscovered.

**`aoe_profiles.alias` on a third party this stage meets for the first time.** Every player in
`RawMatch.player_profile_ids` gets an `aoe_profiles` row — data-model.md: "holds third parties too"
— but neither `RawMatch` nor `LeaderboardSnapshot` (`packages/providers/src/aoe2stats_providers/
base.py`) carries a display name for anyone but the profile a caller already resolved at sign-in
time (`ProfileRef`, sign-in only, T027). A profile this stage inserts for the first time therefore
gets a placeholder alias (`str(profile_id)`) rather than inventing one — and, since `alias` is "the
last one observed, not a history" (`models.py`), an *existing* row's alias is left exactly as it
was: this stage has no newer observation to prefer over whatever sign-in last recorded, and writing
over a real alias with a placeholder would be a regression, not a refresh. The one field this stage
does update on every sighting, new row or old, is `last_seen_at`.

Not wired into `run.py`'s `DEFAULT_STAGES` here: that tuple is assembled by whichever task first
holds a real `session_factory`, `MatchHistoryProvider` and `ProfileProvider` to construct this
class with, which is T059's job (`run.py`'s own module docstring), not this one's.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_ingester.budget import Budget, iter_within_budget
from aoe2stats_providers.base import MatchHistoryProvider, ProfileProvider, RawMatch
from aoe2stats_storage.models import (
    AoeProfile,
    CaptureSource,
    CaptureStatus,
    Match,
    MatchPlayer,
    ProfileLink,
    ReplayCapture,
    User,
)
from aoe2stats_storage.repositories.base import session_scope
from aoe2stats_storage.repositories.ratings import RatingsRepository

#: `contracts/providers.md`: `MatchHistoryProvider.recent_matches` is "batched, up to 10 profiles
#: per call" and `ProfileProvider.personal_stats` "accepts up to 50 profiles per call". Both
#: providers already enforce their own ceiling internally (`RelicMatchHistoryProvider._chunk`,
#: `contracts/providers.md`'s note on `RelicProfileProvider`) — this stage's own chunking exists
#: for a different reason: it is the granularity `iter_within_budget` checks the run's time budget
#: at, between chunks and never mid-chunk (`budget.py`). Ten is the tighter of the two provider
#: ceilings, so one constant safely serves both loops below.
_DISCOVERY_BATCH_SIZE = 10

#: `matches.source` — every match this stage discovers came from the one `MatchHistoryProvider`
#: implementation wired up today (`packages/providers/src/aoe2stats_providers/relic/matches.py`).
_MATCH_SOURCE = "relic"


def _chunk(items: Sequence[int], size: int) -> Iterator[Sequence[int]]:
    """Split `items` into consecutive slices of at most `size`, preserving order."""
    for start in range(0, len(items), size):
        yield items[start : start + size]


class DiscoverStage:
    """A `Stage` (`aoe2stats_ingester.run.Stage`): ratings refresh, match discovery, upsert and
    capture enqueue, over every consenting user's every linked profile.

    `profile_provider` is optional: a caller that only wants match discovery — this repository's
    own `test_consent_gate.py` is exactly that caller — can omit it, and the rating-refresh step is
    skipped entirely rather than failing for want of a provider it was never given. Every other
    caller (including production, once T059 wires this stage up) supplies one so FR-009's rating
    history keeps accumulating alongside match discovery, not instead of it.
    """

    name = "discover"

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        match_history_provider: MatchHistoryProvider,
        capture_budget_days: int,
        profile_provider: ProfileProvider | None = None,
        batch_size: int = _DISCOVERY_BATCH_SIZE,
    ) -> None:
        self._session_factory = session_factory
        self._match_history_provider = match_history_provider
        self._profile_provider = profile_provider
        self._capture_budget_days = capture_budget_days
        self._batch_size = batch_size

    async def __call__(self, budget: Budget) -> Mapping[str, Any]:
        profile_ids = await self._consenting_profile_ids()
        # A plain `set` for O(1) membership below: which profiles a discovered match's participants
        # belong to (and therefore get a `replay_captures` row) is checked against the *whole*
        # cycle's consenting set, not against whichever batch happened to trigger the fetch — two
        # profiles sharing a match can land in different batches (`test_shared_match.py`).
        consenting_profile_ids = set(profile_ids)

        rating_snapshots_recorded = 0
        if self._profile_provider is not None:
            for batch in iter_within_budget(list(_chunk(profile_ids, self._batch_size)), budget):
                rating_snapshots_recorded += await self._refresh_ratings(batch)

        profiles_polled = 0
        matches_discovered = 0
        captures_enqueued = 0
        for batch in iter_within_budget(list(_chunk(profile_ids, self._batch_size)), budget):
            profiles_polled += len(batch)
            raw_matches = await self._match_history_provider.recent_matches(batch)
            if not raw_matches:
                continue
            async with session_scope(self._session_factory) as session:
                for raw_match in raw_matches:
                    await self._upsert_match(session, raw_match)
                    matches_discovered += 1
                    for player_profile_id in raw_match.player_profile_ids:
                        await self._touch_aoe_profile(session, player_profile_id)
                        await self._upsert_match_player(
                            session, raw_match.game_id, player_profile_id
                        )
                        if player_profile_id in consenting_profile_ids:
                            enqueued = await self._enqueue_capture(
                                session, raw_match, player_profile_id
                            )
                            if enqueued:
                                captures_enqueued += 1

        return {
            "profiles_polled": profiles_polled,
            "matches_discovered": matches_discovered,
            "captures_enqueued": captures_enqueued,
            "rating_snapshots_recorded": rating_snapshots_recorded,
        }

    async def _consenting_profile_ids(self) -> list[int]:
        """FR-013/FR-034/FR-035/FR-042 in one query: every profile still actively linked
        (`unlinked_at IS NULL`) to a user whose ingestion consent is granted **right now** —
        `ingest_consent_at IS NOT NULL AND ingest_consent_withdrawn_at IS NULL`, the two-clause
        predicate data-model.md states and contracts/http-api.md cites twice — the condition this
        whole module's docstring is about, expressed once, here, as the thing that selects work
        rather than as a filter applied to it afterwards. The first clause alone is not enough:
        `ingest_consent_at` is never cleared on withdrawal (T032), so it stays true forever from
        the first grant onward, and only the second clause makes a withdrawal (FR-035) actually
        stop a user's matches from being discovered and their captures from being enqueued.
        """
        async with self._session_factory() as session:
            statement = (
                select(ProfileLink.profile_id)
                .join(User, User.id == ProfileLink.user_id)
                .where(ProfileLink.unlinked_at.is_(None))
                .where(User.ingest_consent_at.is_not(None))
                .where(User.ingest_consent_withdrawn_at.is_(None))
                .distinct()
            )
            result = await session.execute(statement)
            return [row[0] for row in result.all()]

    async def _refresh_ratings(self, profile_ids: Sequence[int]) -> int:
        """FR-009: append one `rating_snapshots` row per profile/leaderboard this batch resolves.
        `RatingsRepository.record_snapshot` never skips an unchanged rating (see its own
        docstring), so this always appends exactly one row per snapshot the provider returns.
        """
        assert self._profile_provider is not None  # guarded by the caller
        snapshots = await self._profile_provider.personal_stats(profile_ids)
        if not snapshots:
            return 0
        async with session_scope(self._session_factory) as session:
            repository = RatingsRepository(session)
            for snapshot in snapshots:
                await repository.record_snapshot(
                    profile_id=snapshot.profile_id,
                    leaderboard_id=snapshot.leaderboard_id,
                    rating=snapshot.rating,
                    rank=snapshot.rank,
                    wins=snapshot.wins,
                    losses=snapshot.losses,
                    streak=snapshot.streak,
                    highest_rating=snapshot.highest_rating,
                    # `captured_at` is left to `record_snapshot`'s own default (`datetime.now(UTC)`)
                    # deliberately: it means "the moment this cycle observed the rating", not
                    # `snapshot.last_match_at` (when the player's *last match* happened) — the two
                    # are different facts, and the sign-in flow's own call
                    # (`apps/api/src/aoe2stats_api/routers/auth.py`) makes the same choice.
                )
        return len(snapshots)

    async def _touch_aoe_profile(self, session: AsyncSession, profile_id: int) -> None:
        """Ensure an `aoe_profiles` row exists for `profile_id` and record that it was seen just
        now. See the module docstring for why `alias` is only ever set on first insert here, never
        overwritten on an existing row.
        """
        now = datetime.now(UTC)
        statement = (
            pg_insert(AoeProfile)
            .values(
                profile_id=profile_id,
                alias=str(profile_id),
                first_seen_at=now,
                last_seen_at=now,
            )
            .on_conflict_do_update(
                index_elements=[AoeProfile.profile_id],
                set_={"last_seen_at": now},
            )
        )
        await session.execute(statement)

    async def _upsert_match(self, session: AsyncSession, raw_match: RawMatch) -> None:
        """`ON CONFLICT DO UPDATE` on `matches.game_id`: a match discovered again (the shared-match
        case, or simply re-polled the next day before its replay is captured) gets its row
        replaced wholesale with the freshest response, `raw_payload` included — never merged field
        by field, which could otherwise keep a value the provider has since corrected.
        """
        values: dict[str, Any] = {
            "game_id": raw_match.game_id,
            "leaderboard_id": raw_match.leaderboard_id,
            "map_name": raw_match.map_name,
            "patch": raw_match.patch,
            "started_at": raw_match.started_at,
            "completed_at": raw_match.completed_at,
            "duration_seconds": raw_match.duration_seconds,
            "source": _MATCH_SOURCE,
            "raw_payload": raw_match.raw_payload,
        }
        statement = (
            pg_insert(Match)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[Match.game_id],
                set_={key: value for key, value in values.items() if key != "game_id"},
            )
        )
        await session.execute(statement)

    async def _upsert_match_player(
        self, session: AsyncSession, game_id: int, profile_id: int
    ) -> None:
        """`ON CONFLICT DO NOTHING` on the `(game_id, profile_id)` primary key: this stage does
        not yet know a player's civ, team, colour or result (`MatchHistoryProvider.recent_matches`
        does not carry them — see `contracts/providers.md`), so there is nothing to refresh on a
        repeat sighting, only a row whose *existence* must be guaranteed.
        """
        statement = (
            pg_insert(MatchPlayer)
            .values(game_id=game_id, profile_id=profile_id)
            .on_conflict_do_nothing(index_elements=[MatchPlayer.game_id, MatchPlayer.profile_id])
        )
        await session.execute(statement)

    async def _enqueue_capture(
        self, session: AsyncSession, raw_match: RawMatch, profile_id: int
    ) -> bool:
        """Enqueue one `pending` `replay_captures` row for `(raw_match.game_id, profile_id)`, with
        `capture_deadline_at` computed once, here, from `self._capture_budget_days` — never
        restated as a literal, so `CAPTURE_BUDGET_DAYS` changes every capture enqueued from the
        moment it is lowered (FR-014).

        `ON CONFLICT DO NOTHING ... RETURNING` (the same idiom `apps/api/src/aoe2stats_api/
        routers/auth.py`'s race-handling inserts already use): a genuinely new row's id comes back
        and this returns `True`; a row that already exists for this pair — the shared-match case,
        or simply the same match rediscovered — reports no row and this returns `False`, leaving
        whatever the row already carries (its `status`, its already-computed `capture_deadline_at`)
        untouched.
        """
        deadline = raw_match.completed_at + timedelta(days=self._capture_budget_days)
        statement = (
            pg_insert(ReplayCapture)
            .values(
                game_id=raw_match.game_id,
                profile_id=profile_id,
                status=CaptureStatus.PENDING,
                capture_deadline_at=deadline,
                source=CaptureSource.AUTOMATIC,
            )
            .on_conflict_do_nothing(
                index_elements=[ReplayCapture.game_id, ReplayCapture.profile_id]
            )
            .returning(ReplayCapture.id)
        )
        result = await session.execute(statement)
        return result.scalar_one_or_none() is not None
