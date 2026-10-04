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

**Link status is a `WHERE` clause, not a branch (FR-013, FR-042); objection is a second, narrower
one that only capture consults (constitution IX 4.0.0).** Archival now rests on legitimate interest,
not consent: a linked profile whose user has not answered any question is ingested in full,
archival included. `_linked_profile_ids()` is the *only* place this module decides whose profiles
exist for a cycle's discovery and rating refresh — every profile with `profile_links.unlinked_at
IS NULL`, no other condition. `_archiving_profile_ids()` narrows that same set by one more
condition, `users.archival_objected_at IS NOT NULL` excluded, and it is consulted nowhere but the
capture-enqueue membership test in `__call__`'s participant loop: a linked user's Art. 21 objection
stops further capture of their own recordings and nothing upstream of it — their matches are still
discovered and their ratings are still refreshed on every cycle, exactly as an unobjected user's
are. Collapsing "objected" into "unlinked" — dropping discovery or the rating refresh for an
objecting user — reinstates the retired opt-in gate under `archival_objected_at`'s name; that is
the fault this split exists to prevent, not merely a stricter query. `unlinked_at IS NOT NULL`
remains the one exclusion that reaches every step, because an unlinked profile is not a linked
user's own point of view for anyone to attribute a recording to. FR-042 is `_linked_profile_ids()`'s
other half: every linked profile a user holds is selected, not only the one `is_primary` marks,
because `profile_links.unlinked_at IS NULL` is the only per-link condition, and nothing here also
filters on `is_primary`.

**Every write below is an upsert, never a plain `INSERT`.** A discovery cycle runs daily against
profiles whose match history and roster keep changing, and the same match is very often discovered
twice in one cycle — once through each of two consenting players who shared it (`test_shared_match.
py`) — long before the 25-day reconciliation sweep (T054) would otherwise notice a duplicate.
`ON CONFLICT DO UPDATE` on `matches.game_id` keeps the row current (constitution IV: `raw_payload`
is the provider's response, unmodified, replaced wholesale rather than merged field by field, since
merging would silently keep a stale value the provider has since corrected); since T413,
`ON CONFLICT DO UPDATE` also refreshes `match_players`' own Relic-derived columns on a repeat
sighting of the same participant, for the same reason (see `upsert_match_players`'s own docstring
for the one column deliberately excluded from that refresh); `ON CONFLICT DO NOTHING` on
`replay_captures`' composite key makes the same `(game_id, profile_id)` capture a no-op rather than
an error on a repeat sighting — which is also what keeps `capture_deadline_at` "computed once on
insert, never recomputed" true across
however many times the same match is rediscovered.

**One lock order, three statements (T459).** Every batch is written through
`persist_matches_and_profiles` — `matches` ascending by `game_id`, then `aoe_profiles` ascending by
`profile_id`, then `match_players` ascending by `(game_id, profile_id)`, one multi-row statement
per table — and the capture enqueue follows, in the same `(game_id, profile_id)` order. See the
notes above `touch_aoe_profiles` for why: the API's on-view refreshes write the same rows in the
same transaction shape, and two writers locking the same rows in different orders deadlock.
**T459a**: the API's companion colour fills ride the same call (`colour_fills`), so the
`match_players` rows they touch are locked in the same ascending pass as the batch's own.

**`aoe_profiles.alias` on a third party this stage meets for the first time.** Every player in
`RawMatch.player_profile_ids` gets an `aoe_profiles` row — data-model.md: "holds third parties too"
— but neither `RawMatch` nor `LeaderboardSnapshot` (`packages/providers/src/aoe2stats_providers/
base.py`) carries a display name for anyone but the profile a caller already resolved at sign-in
time (`ProfileRef`, sign-in only, T027). A profile this stage inserts for the first time therefore
gets a placeholder alias (`str(profile_id)`) rather than inventing one — this stage itself never
passes `persist_matches_and_profiles` (below) an identity row, so every sighting it drives still
writes and re-touches only that placeholder, exactly as before T452. `touch_aoe_profiles` itself
accepts a real `alias`/`country` for the caller that does have one (T453's on-view identity refresh)
— and, since `alias` is "the last one observed, not a history" (`models.py`), a real alias a prior
sighting established is never clobbered back down to the placeholder by a later sighting that has
none: writing over a real alias with a placeholder would be a regression, not a refresh, and that
holds however many times this stage's own placeholder-only calls run afterwards. The one field
every sighting updates regardless — new row, old row, real alias or none — is `last_seen_at`.

Not wired into `run.py`'s `DEFAULT_STAGES` here: that tuple is assembled by whichever task first
holds a real `session_factory`, `MatchHistoryProvider` and `ProfileProvider` to construct this
class with, which is T059's job (`run.py`'s own module docstring), not this one's.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable, Iterator, Mapping, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import (
    BigInteger,
    SmallInteger,
    Text,
    case,
    cast,
    column,
    func,
    select,
    text,
    tuple_,
    update,
    values,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_ingester.budget import Budget, iter_within_budget
from aoe2stats_providers.base import MatchHistoryProvider, ProfileProvider, RawMatch, RawProfile
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
from aoe2stats_storage.repositories.matches import project_match_player
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
#: Public (no leading underscore): the API's on-view refresh (`GET /api/players/{profile_id}/
#: matches`, `apps/api/src/aoe2stats_api/routers/players.py`) persists through the same
#: `persist_matches_and_profiles` below, which stamps this value, so a match discovered by either
#: path carries one source name; a test seeding a stored match reads it from here for the same
#: reason.
MATCH_SOURCE = "relic"


def _chunk(items: Sequence[int], size: int) -> Iterator[Sequence[int]]:
    """Split `items` into consecutive slices of at most `size`, preserving order."""
    for start in range(0, len(items), size):
        yield items[start : start + size]


# --- Persistence, shared with `apps/api`'s on-demand routes (T328, T453, T459) ------------------
#
# Module-level, not `DiscoverStage` methods, precisely so they can be called without constructing
# a whole stage (its consenting-profile query, its rating refresh, its capture enqueue — none of
# which `GET /api/players/{profile_id}/matches` wants: FR-012 forbids that route from beginning
# capture for a third party at all). `DiscoverStage`, `ReconcileStage` and the API's on-view
# refreshes all persist through `persist_matches_and_profiles` below — one persistence path, per
# `CLAUDE.md`'s "reuse what exists".
#
# **T459: one global lock order, and a bounded number of statements.** Every transaction that
# writes `matches`, `aoe_profiles` and `match_players` writes them table by table — `matches`
# ascending by `game_id`, then `aoe_profiles` ascending by `profile_id`, then `match_players`
# ascending by `(game_id, profile_id)` — and never goes back to an earlier table or a lower key.
# Row locks are held to commit, so two transactions that lock the same rows in different orders can
# wait on each other forever (production, 2026-10-04: `DeadlockDetected` in `touch_aoe_profile`
# between the two player-page requests, and between an API request and a discovery cycle). A single
# global order makes a cycle impossible.
#
# Each table is written with **one multi-row `INSERT ... ON CONFLICT` statement** (split only past
# `_BULK_ROW_LIMIT` rows, to stay under the driver's bind-parameter ceiling), its rows sorted per
# the order above: Postgres takes a multi-row insert's row locks in `VALUES` order. The same
# change is what makes the work bounded — a 177-match, 770-player, 400-profile response is three
# statements, not ~2,100 sequential round trips that no serverless request can finish.

#: Rows per bulk statement. `match_players` binds 8 columns and `matches` 9 per row; psycopg's
#: ceiling is 65,535 bind parameters per statement, so 5,000 rows stays well inside it. A batch
#: larger than this is split into consecutive, still-ascending chunks.
_BULK_ROW_LIMIT = 5_000

#: SQLSTATEs the on-view refresh degrades on (`savepoint_tolerating_lock_conflicts`): a deadlock
#: (`40P01`), a serialisation failure (`40001`) and a lock wait that outlived `lock_timeout`
#: (`55P03`). Nothing broader.
LOCK_CONFLICT_SQLSTATES = frozenset({"40P01", "40001", "55P03"})

#: How long an on-view refresh will wait for a row lock another transaction holds before it gives
#: up and lets the route answer from storage. Well inside the 10-second limit of the platform the
#: API runs on (ADR 0002), so a refresh blocked behind a stuck transaction degrades instead of
#: timing the request out.
ON_VIEW_LOCK_TIMEOUT_MS = 3_000


def _chunks[T](rows: Sequence[T]) -> Iterator[Sequence[T]]:
    for start in range(0, len(rows), _BULK_ROW_LIMIT):
        yield rows[start : start + _BULK_ROW_LIMIT]


def _is_real_alias(profile_id: int, alias: str | None) -> bool:
    return alias is not None and alias != str(profile_id)


def merge_sightings(
    participant_profile_ids: Iterable[int], identities: Iterable[RawProfile]
) -> dict[int, RawProfile]:
    """Deduplicate every sighting of every profile in one transaction into one entry per
    `profile_id`, merging what the sources know: a real alias (and the country that arrived with
    it) from any source wins over the numeric-id placeholder, and a source with no real alias never
    erases one another source supplied. A bare participant sighting carries neither.
    """
    merged: dict[int, RawProfile] = {
        profile_id: RawProfile(profile_id=profile_id) for profile_id in participant_profile_ids
    }
    for identity in identities:
        current = merged.get(identity.profile_id, RawProfile(profile_id=identity.profile_id))
        if _is_real_alias(identity.profile_id, identity.alias):
            merged[identity.profile_id] = RawProfile(
                profile_id=identity.profile_id, alias=identity.alias, country=identity.country
            )
        elif not _is_real_alias(current.profile_id, current.alias) and (
            identity.country is not None
        ):
            merged[identity.profile_id] = RawProfile(
                profile_id=identity.profile_id, alias=None, country=identity.country
            )
        else:
            merged[identity.profile_id] = current
    return merged


async def touch_aoe_profiles(session: AsyncSession, sightings: Iterable[RawProfile]) -> None:
    """Ensure an `aoe_profiles` row exists for every sighting and record that it was seen just now
    — one multi-row `INSERT ... ON CONFLICT`, rows ascending by `profile_id` (module notes above).
    Sightings of the same profile are merged first (`merge_sightings`).

    Semantics are `touch_aoe_profile`'s, expressed row by row inside the one statement (its
    docstring is the contract). On insert a real `alias` is stored, else the `str(profile_id)`
    placeholder, and `country` is whatever was given. **On conflict**, a real alias — one that is
    not the placeholder — overwrites the stored alias and country together; a sighting without one
    changes neither, so a discovery cycle can never clobber a real name back down to the numeric id.
    `last_seen_at` moves on every sighting. The "is this alias real" test runs in SQL against
    `excluded` (`excluded.alias <> excluded.profile_id::text`), so one statement serves a batch
    that mixes both kinds — splitting it in two would break the single ascending order.
    """
    merged = merge_sightings((), sightings)
    now = datetime.now(UTC)
    rows: list[dict[str, Any]] = []
    for profile_id in sorted(merged):
        sighting = merged[profile_id]
        real = _is_real_alias(profile_id, sighting.alias)
        rows.append(
            {
                "profile_id": profile_id,
                "alias": sighting.alias if real else str(profile_id),
                "country": sighting.country,
                "first_seen_at": now,
                "last_seen_at": now,
            }
        )
    for chunk in _chunks(rows):
        insert = pg_insert(AoeProfile).values(list(chunk))
        excluded = insert.excluded
        incoming_is_real = excluded.alias != cast(excluded.profile_id, Text)
        await session.execute(
            insert.on_conflict_do_update(
                index_elements=[AoeProfile.profile_id],
                set_={
                    "alias": case((incoming_is_real, excluded.alias), else_=AoeProfile.alias),
                    "country": case((incoming_is_real, excluded.country), else_=AoeProfile.country),
                    "last_seen_at": excluded.last_seen_at,
                },
            )
        )


async def touch_aoe_profile(
    session: AsyncSession,
    profile_id: int,
    *,
    alias: str | None = None,
    country: str | None = None,
) -> None:
    """Ensure an `aoe_profiles` row exists for `profile_id` and record that it was seen just now.

    A one-profile call into `touch_aoe_profiles` — the single definition of the semantics below.
    Callers with more than one profile must use `touch_aoe_profiles` or
    `persist_matches_and_profiles`, never a loop over this: a loop is one round trip per row and
    takes its locks in the caller's order (T459).

    `alias`/`country` are optional (T452, FR-007 partial): a caller with neither still gets the
    `str(profile_id)` placeholder on insert, exactly as before.

    **On insert**, a real `alias` is stored when given; when it is not, `alias` falls back to the
    `str(profile_id)` placeholder, and `country` is whatever was given (`None` when it was not,
    matching the placeholder's own "nothing real known yet" case).

    **On conflict** (an existing row), the direction matters more than the write: a real `alias` —
    given, and not itself equal to the `str(profile_id)` placeholder — overwrites whatever the row
    already held (the numeric-id placeholder, or an out-of-date real name) and `country` is set
    alongside it. But when `alias` is absent, or is itself the placeholder, **nothing about the
    stored alias or country changes** — a plain discovery cycle re-touching a profile it has no
    newer name for must never clobber a real alias a prior sighting (T453's on-view refresh)
    already established back down to the numeric id. `last_seen_at` moves on every sighting
    regardless, insert or conflict, real alias or none.
    """
    await touch_aoe_profiles(
        session, [RawProfile(profile_id=profile_id, alias=alias, country=country)]
    )


async def upsert_matches(session: AsyncSession, raw_matches: Iterable[RawMatch]) -> None:
    """`ON CONFLICT DO UPDATE` on `matches.game_id`, one multi-row statement, rows ascending by
    `game_id`: a match discovered again (the shared-match case, or simply re-polled the next day
    before its replay is captured) gets its row replaced wholesale with the freshest response,
    `raw_payload` included — never merged field by field, which could otherwise keep a value the
    provider has since corrected. A `game_id` repeated in the input keeps its last occurrence.
    """
    by_game = {raw_match.game_id: raw_match for raw_match in raw_matches}
    rows = [
        {
            "game_id": raw_match.game_id,
            "leaderboard_id": raw_match.leaderboard_id,
            "map_name": raw_match.map_name,
            "patch": raw_match.patch,
            "started_at": raw_match.started_at,
            "completed_at": raw_match.completed_at,
            "duration_seconds": raw_match.duration_seconds,
            "source": MATCH_SOURCE,
            "raw_payload": raw_match.raw_payload,
        }
        for _, raw_match in sorted(by_game.items())
    ]
    for chunk in _chunks(rows):
        insert = pg_insert(Match).values(list(chunk))
        await session.execute(
            insert.on_conflict_do_update(
                index_elements=[Match.game_id],
                set_={key: insert.excluded[key] for key in rows[0] if key != "game_id"},
            )
        )


async def upsert_match_players(
    session: AsyncSession, pairs: Iterable[tuple[RawMatch, int]]
) -> None:
    """`ON CONFLICT DO UPDATE` on the `(game_id, profile_id)` primary key (T413, research.md D1),
    one multi-row statement, rows ascending by `(game_id, profile_id)`: this stage knows a
    player's civilisation, team, rating, rating movement and result — every one of them already
    sitting, unread, in `raw_match.raw_payload`, the exact `matches.raw_payload` the same
    transaction just wrote via `upsert_matches` — and refreshes them on every repeat sighting
    rather than leaving them null after the row's first insert.
    `aoe2stats_storage.repositories.matches.project_match_player` (T413) is the one place that
    mapping is written; this function calls it rather than restating it. A repeated
    `(game_id, profile_id)` keeps its last occurrence.

    **`color_id` is the sixth column, since T411 (2026-09-04), and it is written differently.**
    The colour was in Relic's response all along — `slotinfo[].metaData.ScenarioPlayerIndex`,
    decoded by `project_match_player`'s `_slot_colour_id` — so this stage writes it from the same
    payload as the other five. Unlike them it is set with `COALESCE(excluded.color_id,
    match_players.color_id)`: a projection that could not read the blob yields `None`, and `None`
    here means "unknown", never "no colour" — it must not erase a colour an earlier sighting (or
    the companion fallback) already stored. A non-`None`
    projection wins outright: Relic is the primary source, and the colour of a finished match
    never changes.
    """
    latest: dict[tuple[int, int], RawMatch] = {}
    for raw_match, profile_id in pairs:
        latest[(raw_match.game_id, profile_id)] = raw_match
    rows: list[dict[str, Any]] = []
    for (game_id, profile_id), raw_match in sorted(latest.items()):
        projected = project_match_player(raw_match.raw_payload, profile_id)
        rows.append(
            {
                "game_id": game_id,
                "profile_id": profile_id,
                "civ_id": projected.civ_id,
                "team_id": projected.team_id,
                "rating": projected.rating,
                "rating_diff": projected.rating_diff,
                "result": projected.result,
                "color_id": projected.color_id,
            }
        )
    for chunk in _chunks(rows):
        insert = pg_insert(MatchPlayer).values(list(chunk))
        excluded = insert.excluded
        await session.execute(
            insert.on_conflict_do_update(
                index_elements=[MatchPlayer.game_id, MatchPlayer.profile_id],
                set_={
                    "civ_id": excluded.civ_id,
                    "team_id": excluded.team_id,
                    "rating": excluded.rating,
                    "rating_diff": excluded.rating_diff,
                    "result": excluded.result,
                    "color_id": func.coalesce(excluded.color_id, MatchPlayer.color_id),
                },
            )
        )


async def lock_match_players(session: AsyncSession, keys: Iterable[tuple[int, int]]) -> None:
    """T459a: take the row locks on every *existing* `match_players` row named by `keys`, in one
    ascending `(game_id, profile_id)` pass — `SELECT ... ORDER BY game_id, profile_id FOR UPDATE`,
    whose lock order is the sorted order (Postgres sorts, then locks). A key with no row is simply
    absent from the result. This is what lets a caller write rows it did not fetch from the
    provider (the companion colour fills) in the same ascending sequence as the batch: the pass
    covers the union, so no row of either is first locked below one already held.
    """
    for chunk in _chunks(sorted(set(keys))):
        await session.execute(
            select(MatchPlayer.game_id, MatchPlayer.profile_id)
            .where(tuple_(MatchPlayer.game_id, MatchPlayer.profile_id).in_(list(chunk)))
            .order_by(MatchPlayer.game_id, MatchPlayer.profile_id)
            .with_for_update()
        )


async def fill_missing_colours(session: AsyncSession, fills: Mapping[tuple[int, int], int]) -> None:
    """T459a: write companion's `color_id` for each `(game_id, profile_id)` in `fills` — **only
    where the stored colour is `NULL`**, never replacing one (`routers/matches.py::
    fetch_colour_fills`'s docstring for the precedence). One `UPDATE ... FROM (VALUES ...)`
    per `_BULK_ROW_LIMIT` keys; a key with no `match_players` row updates nothing. It takes no
    lock of its own that `lock_match_players` has not already taken: callers lock first, through
    `persist_matches_and_profiles`.
    """
    rows = sorted(fills.items())
    for chunk in _chunks(rows):
        fill = values(
            column("game_id", BigInteger),
            column("profile_id", BigInteger),
            column("color_id", SmallInteger),
            name="fill",
        ).data([(game_id, profile_id, colour) for (game_id, profile_id), colour in chunk])
        await session.execute(
            update(MatchPlayer)
            .where(
                MatchPlayer.game_id == fill.c.game_id,
                MatchPlayer.profile_id == fill.c.profile_id,
                MatchPlayer.color_id.is_(None),
            )
            .values(color_id=fill.c.color_id)
            .execution_options(synchronize_session=False)
        )


async def persist_matches_and_profiles(
    session: AsyncSession,
    raw_matches: Sequence[RawMatch],
    identities: Iterable[RawProfile] = (),
    colour_fills: Mapping[tuple[int, int], int] | None = None,
) -> list[tuple[RawMatch, int]]:
    """T459: the one place a batch of raw matches and identity rows is written, in the global lock
    order (module notes above): `matches` ascending by `game_id`, then `aoe_profiles` ascending by
    `profile_id` — deduplicated, every participant of every match plus every identity row, a real
    alias/country merged in from whichever source carries one (`merge_sightings`) — then
    `match_players` ascending by `(game_id, profile_id)`. Three statements for any batch size.

    **T459a, `colour_fills`.** Companion's colours, keyed `(game_id, profile_id)`, are written by
    this call too, because they are `match_players` writes and the invariant is per transaction,
    not per helper. When any are given, the `match_players` phase is: one ascending lock pass over
    the union of the batch's keys and the fills' keys (`lock_match_players`), then the batch's
    upsert, then the fills (`fill_missing_colours`, `NULL` colours only) — two statements more,
    whatever the number of fills. The fills' rows may include stored rows below the batch's keys
    (the stored page of a profile whose history was just refetched); the pass is what keeps those
    from being locked after higher ones. A new `match_players` row is only inserted for a game this
    same transaction has just upserted into `matches`, so two writers of one new key meet on
    `matches` first and no cycle forms.

    Nothing in the caller's transaction may write an earlier table or a lower key afterwards; a
    caller that needs more rows (a capture enqueue, a rating snapshot) writes them after this
    returns, and only rows whose parents this call already locked.

    Returns the `(raw_match, profile_id)` pairs written to `match_players`, ascending by
    `(game_id, profile_id)`, so a caller that goes on to enqueue captures does so in the same order.
    """
    await upsert_matches(session, raw_matches)
    by_game = {raw_match.game_id: raw_match for raw_match in raw_matches}
    participants = [
        profile_id for raw_match in by_game.values() for profile_id in raw_match.player_profile_ids
    ]
    await touch_aoe_profiles(session, merge_sightings(participants, identities).values())
    pairs = sorted(
        {
            (game_id, profile_id): (raw_match, profile_id)
            for game_id, raw_match in by_game.items()
            for profile_id in raw_match.player_profile_ids
        }.items()
    )
    ordered = [pair for _, pair in pairs]
    if colour_fills:
        await lock_match_players(session, {*(key for key, _ in pairs), *colour_fills})
    await upsert_match_players(session, ordered)
    if colour_fills:
        await fill_missing_colours(session, colour_fills)
    return ordered


@asynccontextmanager
async def savepoint_tolerating_lock_conflicts(session: AsyncSession) -> AsyncIterator[None]:
    """T459, FR-017: run an on-view refresh's persistence inside a savepoint that gives up
    quietly when the database reports a lock conflict — a deadlock (`40P01`), a serialisation
    failure (`40001`) or a lock wait past `ON_VIEW_LOCK_TIMEOUT_MS` (`55P03`). The savepoint is
    rolled back, nothing the block wrote survives, the surrounding request transaction is intact,
    and the caller answers from storage — the same silent degrade a source failure already gets.
    Every other database error propagates.

    `lock_timeout` is set `LOCAL` inside the savepoint (so it reverts with it) and restored to its
    previous value when the block succeeds, so the rest of the request — its reads, and whatever a
    caller does after the block — is not subject to a timeout it never asked for.
    """
    try:
        async with session.begin_nested():
            previous = (
                await session.execute(text("SELECT current_setting('lock_timeout')"))
            ).scalar_one()
            await session.execute(
                text("SELECT set_config('lock_timeout', :value, true)"),
                {"value": f"{ON_VIEW_LOCK_TIMEOUT_MS}ms"},
            )
            yield
            await session.execute(
                text("SELECT set_config('lock_timeout', :value, true)"), {"value": previous}
            )
    except DBAPIError as exc:
        if getattr(exc.orig, "sqlstate", None) not in LOCK_CONFLICT_SQLSTATES:
            raise


class DiscoverStage:
    """A `Stage` (`aoe2stats_ingester.run.Stage`): ratings refresh, match discovery, upsert and
    capture enqueue, over every linked user's every linked profile.

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
        profile_ids = await self._linked_profile_ids()
        # A plain `set` for O(1) membership below: which profiles a discovered match's participants
        # belong to (and therefore get a `replay_captures` row) is checked against the *whole*
        # cycle's archiving set — every linked profile minus one whose user has objected
        # (constitution IX 4.0.0) — not against whichever batch happened to trigger the fetch: two
        # profiles sharing a match can land in different batches (`test_shared_match.py`).
        archiving_profile_ids = set(await self._archiving_profile_ids())

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
                written = await persist_matches_and_profiles(session, raw_matches)
                matches_discovered += len(raw_matches)
                for raw_match, player_profile_id in written:
                    if player_profile_id in archiving_profile_ids:
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

    async def _linked_profile_ids(self) -> list[int]:
        """FR-013/FR-042: every profile still actively linked (`profile_links.unlinked_at IS
        NULL`), no other condition — the set that drives match discovery and the rating refresh
        (constitution IX 4.0.0: archival rests on legitimate interest, not consent, so a linked
        profile whose user has not answered any question is ingested in full). `unlinked_at IS NOT
        NULL` is the one exclusion that survives the amendment, and it must stay total: an
        unlinked profile is not a linked user's own point of view for anyone to attribute a
        recording to.
        """
        async with self._session_factory() as session:
            statement = (
                select(ProfileLink.profile_id).where(ProfileLink.unlinked_at.is_(None)).distinct()
            )
            result = await session.execute(statement)
            return [row[0] for row in result.all()]

    async def _archiving_profile_ids(self) -> list[int]:
        """The narrower set `_linked_profile_ids()` selects, minus any profile whose user has
        exercised the Art. 21 right to object (`users.archival_objected_at IS NOT NULL`) —
        consulted nowhere but the capture-enqueue membership test in `__call__`'s participant
        loop. An objecting user is still a linked user in every other respect: their matches are
        still discovered and their ratings are still refreshed by `_linked_profile_ids()` above,
        only their own further capture stops. "Objected" and "unlinked" are deliberately two
        different conditions on two different queries here, never one collapsed into the other.
        """
        async with self._session_factory() as session:
            statement = (
                select(ProfileLink.profile_id)
                .join(User, User.id == ProfileLink.user_id)
                .where(ProfileLink.unlinked_at.is_(None))
                .where(User.archival_objected_at.is_(None))
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
