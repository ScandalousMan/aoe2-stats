"""The player-search service (T315, T316): query normalisation, the `profile_search_cache`
read/write path, the `degraded` signal, and the local fallback over `aoe_profiles`.
`apps/api/tests/test_player_search.py` (T314) is this module's specification, exactly the
relationship `ratelimit.py`'s own docstring describes for `test_rate_limits.py`; the cache,
normalisation and the structural half of `degraded` are T315's, and the fallback's own content —
which profiles it returns, in what order, and that it withholds none of them — is T316's, in
`_local_fallback_results` below. It introduces no source and no request of its own: `aoe_profiles`
already holds every participant of every match this service has seen, populated by 001's discovery,
so the fallback is a read against a table this service already keeps, never a new external call.

**Cache-first, then the breaker, never an exception.** `search_players` checks
`profile_search_cache` before it asks anything else: a fresh row answers the query without caring
whether the source is currently up, which is the whole point of FR-004e — "repeated and common
queries do not become repeated calls against a source that is degradable by design." A cache miss
looks at `provider.is_degraded()` *before* the provider is ever called — `contracts/providers.md`'s
"Failure" section is explicit that `search_players` never raises, so a `degraded` signal read off
an exception cannot exist; it has to come from state the provider can be asked about ahead of time,
exactly as `test_player_search.py`'s `_FakeSearchProvider.is_degraded()` models it, and exactly what
`is_degraded()` now is on `PlayerSearchProvider` itself (`contracts/providers.md`,
`packages/providers/.../base.py`) — this module depends on that Protocol, not on a private
extension of it, so there is no boundary of its own left to declare here.

**BL-2 remediation: `is_degraded()` alone is checked again after a genuine call, but it is not
enough on its own.** A total outage still answers `search_players` with an empty page rather than
raising (the same "Failure" section), and if that very call is what tripped the breaker — or found
it still open on a post-cooldown probe — reading `is_degraded()` only beforehand would miss it.
But `is_degraded()` only ever reads "is the breaker open", which a consecutive-failure breaker
holds `False` through the first `_FAILURE_THRESHOLD - 1` failures of every outage
(`companion/provider.py`) — the round-2 review reproduced this by execution: the first two failing
calls of an outage read `is_degraded() == False` both before and after, and were cached as a
confident `source="companion"` answer, served back as "no such player" for the rest of the TTL and
beyond. `provider.last_call_failed()` (`PlayerSearchProvider`, `base.py`) is the signal that closes
that gap: `True` after any failed call, independent of the breaker's own threshold. `search_players`
below checks `is_degraded() or last_call_failed()` after the call, never `is_degraded()` alone.

**`source` is how a cached row remembers which path answered it (BL-3 re-take).** A row written
from a real, confident answer carries `source="companion"` (`_COMPANION_SOURCE`); a row written
from the fallback carries `source="aoe_profiles"` (`_FALLBACK_SOURCE`). The round-1 remediation
had stopped writing the fallback's answer to the cache at all, on the premise that
`_local_fallback_results` was "a plain, cheap read" not worth protecting further — the round-2
review measured that premise false: it is an unfiltered aggregate (`count(*) ... group by
profile_id`) over the whole `match_players` table, joined to `aoe_profiles`, recomputed on *every*
degraded request, up to the per-user rate limit, precisely while the source is down, against a
0.5 GB Neon instance. Caching the fallback's own answer is worth doing after all, under a
deliberately short TTL (`_FALLBACK_CACHE_TTL_SECONDS`, a small fraction of the live `ttl_seconds`):
short enough that the "outage would outlive itself" risk the round-1 remediation was right to worry
about stays bounded to that TTL rather than the full `PLAYER_SEARCH_CACHE_TTL_SECONDS`, while
still turning a burst of repeat queries against a down source into one aggregate per
`fallback_ttl_seconds`, not one per request. Reading `degraded` back off a cache hit's `source`
column — rather than re-asking the provider — stays the convention `test_players_routes.py` (T317)
already seeded directly: `source="companion"` reads as `degraded: false`, any other value
(including a row from before this remediation, or one seeded directly by a test) as
`degraded: true`.

**Opportunistic TTL pruning happens on write, never on read and never on a schedule (FR-044), and
is now TTL-aware per row's own `source`.** Every call that writes a fresh row first deletes every
row — not only this query's own — whose `fetched_at` has fallen behind *its own* TTL: `ttl_seconds`
for a `"companion"` row, `fallback_ttl_seconds` for any other. A single, uniform threshold would
either prune fresh fallback rows too eagerly (if set to the short TTL) or let a stale fallback row
outlive its own, deliberately short protection window (if set to the long one) — see `ratelimit.py`
for the identical discipline applied to `rate_limit_counters`, minus the per-row TTL split this
table's two kinds of row now need.

**`ttl_seconds`, `fallback_ttl_seconds` and `limit` are explicit parameters, not a call into
`get_settings()` in here** — identical to `check_and_increment`'s `window_seconds` in
`ratelimit.py`. This function stays a pure function of its inputs; the router (T319) is where
`PLAYER_SEARCH_CACHE_TTL_SECONDS` gets read once and passed in as `ttl_seconds`.
`fallback_ttl_seconds` is not settings-driven at all, deliberately: it is a fixed, protective
constant (`_FALLBACK_CACHE_TTL_SECONDS`) rather than an operator-tunable knob, on the same footing
as `companion/provider.py`'s own `_FAILURE_THRESHOLD` — nothing about it should need to change
per-deployment, so it stays a literal here rather than growing an `.env.example` entry with no
real use for one. `now` is explicit for the same reason it is in `ratelimit.py` — deterministic TTL
boundaries under test, never a race against the real clock.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_providers.base import PlayerSearchProvider, PlayerSearchResult
from aoe2stats_storage.models import AoeProfile, MatchPlayer, ProfileSearchCache

# `contracts/http-api.md`: "`search` returns `{"results": [...], "degraded": bool, "reason": null
# | "..."}`" and names this exact string for the one non-null reason a successful search body ever
# carries.
_SEARCH_SOURCE_UNAVAILABLE_REASON = "search_source_unavailable"

# `profile_search_cache.source` for a row answered by the real provider. Any other value reads back
# as `degraded: true` — see the module docstring's note on `test_players_routes.py`'s convention.
_COMPANION_SOURCE = "companion"

# `data-model.md`'s own name for what FR-004d's fallback searches over — written to
# `profile_search_cache.source` for a fallback answer (BL-3 re-take, module docstring), and read
# back as `degraded: true` exactly like any other non-companion value, including a row seeded
# directly by a test (`test_players_routes.py`, T317) or one left over from before this remediation.
_FALLBACK_SOURCE = "aoe_profiles"

# The TTL a fallback row is cached under — deliberately much shorter than the caller's own
# `ttl_seconds` (module docstring's "BL-3 re-take"): short enough that a query cached mid-outage
# self-heals quickly once the source recovers, long enough to turn a burst of identical repeat
# queries against a down source into one `_local_fallback_results` aggregate per window rather than
# one per request.
_FALLBACK_CACHE_TTL_SECONDS = 30


@dataclass(frozen=True)
class SearchOutcome:
    """`search_players`'s return shape: the results this call is answering with, whether they are
    reduced (`degraded`), and — only when `degraded` is `True` — the one `reason` string
    `contracts/http-api.md` names for it."""

    results: Sequence[PlayerSearchResult]
    degraded: bool
    reason: str | None


def normalise_query(query: str) -> str:
    """The key `profile_search_cache.query_normalised` is keyed on (data-model.md). Case, internal
    whitespace and Unicode form all collapse: two spellings of the same visible name — one
    precomposed, one built from a base letter plus a combining mark — must produce the same key, or
    a search for one form would never hit a cache warmed by the other."""
    collapsed = " ".join(query.split())
    return unicodedata.normalize("NFC", collapsed).casefold()


async def search_players(
    session: AsyncSession,
    provider: PlayerSearchProvider,
    query: str,
    *,
    limit: int,
    ttl_seconds: int,
    fallback_ttl_seconds: int = _FALLBACK_CACHE_TTL_SECONDS,
    now: datetime | None = None,
) -> SearchOutcome:
    """Cache-first, breaker-checked, never an exception — see the module docstring for why each of
    those three is in that order. `_local_fallback_results` below is T316's local fallback over
    `aoe_profiles`; this function's own shape does not change under that.
    """
    moment = now if now is not None else datetime.now(UTC)
    query_normalised = normalise_query(query)

    cached = await _read_fresh_cache(
        session,
        query_normalised,
        ttl_seconds=ttl_seconds,
        fallback_ttl_seconds=fallback_ttl_seconds,
        now=moment,
    )
    if cached is not None:
        return cached

    if provider.is_degraded():
        return await _degraded_outcome(
            session,
            query_normalised,
            limit=limit,
            ttl_seconds=ttl_seconds,
            fallback_ttl_seconds=fallback_ttl_seconds,
            now=moment,
        )

    page = await provider.search_players(query, limit=limit)
    if provider.is_degraded() or provider.last_call_failed():
        # B1/BL-2 remediation: `search_players` never raises (`contracts/providers.md`'s
        # "Failure"), so a failed call comes back exactly like a genuine, confident answer would:
        # an empty (or otherwise unverifiable) `page`. `is_degraded()` alone only catches the call
        # that pushes the breaker's own consecutive-failure count past its threshold (or a
        # post-cooldown probe that fails again) — it stays `False` through the first
        # `_FAILURE_THRESHOLD - 1` failures of every outage, which `last_call_failed()`
        # (`PlayerSearchProvider`, `packages/providers/.../base.py`) is what exists to catch:
        # `True` for any failed call, independent of the threshold. Checking `is_degraded()` alone
        # here, as the round-1 remediation did, cached the first two failures of every outage as a
        # confident `source="companion"` answer — the module docstring's BL-2 note.
        return await _degraded_outcome(
            session,
            query_normalised,
            limit=limit,
            ttl_seconds=ttl_seconds,
            fallback_ttl_seconds=fallback_ttl_seconds,
            now=moment,
        )

    await _write_cache(
        session,
        query_normalised,
        page.results,
        source=_COMPANION_SOURCE,
        ttl_seconds=ttl_seconds,
        fallback_ttl_seconds=fallback_ttl_seconds,
        now=moment,
    )
    return SearchOutcome(results=page.results, degraded=False, reason=None)


async def _degraded_outcome(
    session: AsyncSession,
    query_normalised: str,
    *,
    limit: int,
    ttl_seconds: int,
    fallback_ttl_seconds: int,
    now: datetime,
) -> SearchOutcome:
    """FR-004d's fallback outcome, reached whenever the source is (or has just been found to be)
    unavailable — before the call, when the breaker was already open, or immediately after one,
    when the call itself is what opened it, found it still open, or simply failed without tripping
    it yet (see `search_players` above).

    **Written to `profile_search_cache` under `_FALLBACK_SOURCE`, at `fallback_ttl_seconds` (BL-3
    re-take of the round-1 M1 decision — module docstring).** Round 1 stopped caching a fallback
    answer at all, on the premise that `_local_fallback_results` was cheap enough not to need it;
    the round-2 review measured that premise false — it is an unfiltered aggregate over
    `match_players`, recomputed on every degraded request. Caching it under a short TTL bounds that
    cost without reintroducing the staleness risk round 1 was right to avoid at the *long* TTL.
    """
    results = await _local_fallback_results(session, query_normalised, limit=limit)
    await _write_cache(
        session,
        query_normalised,
        results,
        source=_FALLBACK_SOURCE,
        ttl_seconds=ttl_seconds,
        fallback_ttl_seconds=fallback_ttl_seconds,
        now=now,
    )
    return SearchOutcome(results=results, degraded=True, reason=_SEARCH_SOURCE_UNAVAILABLE_REASON)


async def _local_fallback_results(
    session: AsyncSession, query_normalised: str, *, limit: int
) -> Sequence[PlayerSearchResult]:
    """T316's own body: matching `aoe_profiles` case-insensitively and on substring (FR-004a,
    reused deliberately from the source's own behaviour), ordered most-played first, withholding
    nothing (T301a retired FR-004c — there is no signal left to withhold on).

    `aoe_profiles` carries no games-played column of its own (T318's spec note); "most-played" is
    derived here, once, from a `match_players` count grouped per profile and left-joined so a
    profile with no recorded matches still sorts in — last, at zero, rather than dropped. This
    introduces no source and no request: `aoe_profiles` is already populated by 001's discovery of
    every participant of every match this service has seen, and this is a read against it alone.
    """
    games_played_by_profile = (
        select(
            MatchPlayer.profile_id.label("profile_id"),
            func.count().label("games_played"),
        )
        .group_by(MatchPlayer.profile_id)
        .subquery()
    )
    games_played = func.coalesce(games_played_by_profile.c.games_played, 0)

    stmt = (
        select(AoeProfile, games_played.label("games_played"))
        .outerjoin(
            games_played_by_profile,
            games_played_by_profile.c.profile_id == AoeProfile.profile_id,
        )
        .where(func.lower(AoeProfile.alias).contains(query_normalised))
        .order_by(games_played.desc(), AoeProfile.profile_id)
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    return [
        PlayerSearchResult(
            profile_id=profile.profile_id,
            alias=profile.alias,
            country=profile.country,
            games_played=games_played_value,
            clan=None,
        )
        for profile, games_played_value in rows
    ]


def _ttl_for_source(source: str, *, ttl_seconds: int, fallback_ttl_seconds: int) -> int:
    """The TTL that applies to a `profile_search_cache` row, keyed on its own `source` (module
    docstring's "Opportunistic TTL pruning" note): `ttl_seconds` for a confident `"companion"`
    answer, `fallback_ttl_seconds` — deliberately shorter — for anything else, including a row from
    before this remediation or one seeded directly by a test."""
    return ttl_seconds if source == _COMPANION_SOURCE else fallback_ttl_seconds


async def _read_fresh_cache(
    session: AsyncSession,
    query_normalised: str,
    *,
    ttl_seconds: int,
    fallback_ttl_seconds: int,
    now: datetime,
) -> SearchOutcome | None:
    """`None` on a miss — no row, or a row older than its own TTL (`_ttl_for_source`) — so the
    caller re-fetches exactly as if nothing were cached. A hit reads `degraded` off `source` rather
    than re-asking the provider (module docstring)."""
    row = await session.get(ProfileSearchCache, query_normalised)
    if row is None:
        return None
    ttl = _ttl_for_source(
        row.source, ttl_seconds=ttl_seconds, fallback_ttl_seconds=fallback_ttl_seconds
    )
    if row.fetched_at < now - timedelta(seconds=ttl):
        return None

    degraded = row.source != _COMPANION_SOURCE
    return SearchOutcome(
        results=[_result_from_json(record) for record in row.results],
        degraded=degraded,
        reason=_SEARCH_SOURCE_UNAVAILABLE_REASON if degraded else None,
    )


async def _write_cache(
    session: AsyncSession,
    query_normalised: str,
    results: Sequence[PlayerSearchResult],
    *,
    source: str,
    ttl_seconds: int,
    fallback_ttl_seconds: int,
    now: datetime,
) -> None:
    """Replace `query_normalised`'s row (or insert it, on a first ask) and, in the same call,
    delete every row across the whole table past *its own* TTL (`_ttl_for_source`) — the
    opportunistic pruning FR-044 requires in place of a job (module docstring). Not scoped to
    `query_normalised`'s own row: unlike `rate_limit_counters`'s `(user_id, bucket)` scoping in
    `ratelimit.py`, nothing else bounds the *variety* of queries this table accumulates, so every
    stale row is disposable on every write, not only this one's own predecessor. Two conditions,
    not one: a `"companion"` row is stale past `ttl_seconds`, any other row past the much shorter
    `fallback_ttl_seconds` — a single, uniform threshold would either prune fresh fallback rows too
    eagerly or let a stale one outlive its own deliberately short protection window.
    """
    await session.execute(
        delete(ProfileSearchCache).where(
            or_(
                and_(
                    ProfileSearchCache.source == _COMPANION_SOURCE,
                    ProfileSearchCache.fetched_at < now - timedelta(seconds=ttl_seconds),
                ),
                and_(
                    ProfileSearchCache.source != _COMPANION_SOURCE,
                    ProfileSearchCache.fetched_at < now - timedelta(seconds=fallback_ttl_seconds),
                ),
            )
        )
    )

    serialised = [_result_to_json(result) for result in results]
    upsert = (
        pg_insert(ProfileSearchCache)
        .values(
            query_normalised=query_normalised,
            results=serialised,
            fetched_at=now,
            source=source,
        )
        .on_conflict_do_update(
            index_elements=[ProfileSearchCache.query_normalised],
            set_={"results": serialised, "fetched_at": now, "source": source},
        )
    )
    await session.execute(upsert)


def _result_to_json(result: PlayerSearchResult) -> dict[str, Any]:
    """`profile_search_cache.results` holds only the fields `PlayerSearchResult` carries
    (data-model.md) — never a verbatim copy of the provider's response, which would additionally
    store the account-linking claim FR-004b keeps out of this system."""
    return {
        "profile_id": result.profile_id,
        "alias": result.alias,
        "country": result.country,
        "games_played": result.games_played,
        "clan": result.clan,
    }


def _result_from_json(record: dict[str, Any]) -> PlayerSearchResult:
    return PlayerSearchResult(
        profile_id=record["profile_id"],
        alias=record["alias"],
        country=record.get("country"),
        games_played=record.get("games_played"),
        clan=record.get("clan"),
    )
