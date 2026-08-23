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
queries do not become repeated calls against a source that is degradable by design." Only a cache
miss looks at `provider.is_degraded()`, and that check happens *before* the provider is ever called
— `contracts/providers.md`'s "Failure" section is explicit that `search_players` never raises, so a
`degraded` signal read off an exception cannot exist; it has to come from state the provider can be
asked about ahead of time, exactly as `test_player_search.py`'s `_FakeSearchProvider.is_degraded()`
models it. `CompanionEnrichmentProvider` (`packages/providers/.../companion/provider.py`) does not
expose an `is_degraded()` accessor yet — T313 landed reusing `enrich_matches`'s breaker instance
without one. Wiring this service into the real search route (T319) is where that accessor needs to
be added to the real provider; `_SearchProvider` below is this module's own boundary, not a change
to `PlayerSearchProvider` (`contracts/providers.md`), so nothing here forces that change early.

**`source` is how a cached row remembers which path answered it.** A row written from a genuine
provider call carries `source="companion"`; a row written from the fallback carries
`source="aoe_profiles"`, for the same reason and written by the same `_write_cache` call. Reading
`degraded` back off that column on a cache hit — rather than re-asking the provider — is the same
convention `test_players_routes.py` (T317) already seeded directly: `source="companion"` reads as
`degraded: false`, anything else as `degraded: true`.

**Opportunistic TTL pruning happens on write, never on read and never on a schedule (FR-044).**
Every call that writes a fresh row first deletes every row — not only this query's own — whose
`fetched_at` has fallen behind `ttl_seconds`, the same discipline `ratelimit.py` applies to
`rate_limit_counters` and for the same reason: this table has nothing else bounding it, because a
per-user rate limit caps *how often* someone searches, not the *variety* of what has ever been
searched.

**`ttl_seconds` and `limit` are explicit parameters, not a call into `get_settings()` in here** —
identical to `check_and_increment`'s `window_seconds` in `ratelimit.py`. This function stays a pure
function of its inputs; the router (T319) is where `PLAYER_SEARCH_CACHE_TTL_SECONDS` gets read once
and passed in. `now` is explicit for the same reason it is there too: deterministic TTL boundaries
under test, never a race against the real clock.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_providers.base import PlayerSearchPage, PlayerSearchResult
from aoe2stats_storage.models import AoeProfile, MatchPlayer, ProfileSearchCache

# `contracts/http-api.md`: "`search` returns `{"results": [...], "degraded": bool, "reason": null
# | "..."}`" and names this exact string for the one non-null reason a successful search body ever
# carries.
_SEARCH_SOURCE_UNAVAILABLE_REASON = "search_source_unavailable"

# `profile_search_cache.source` for a row answered by the real provider. Any other value reads back
# as `degraded: true` — see the module docstring's note on `test_players_routes.py`'s convention.
_COMPANION_SOURCE = "companion"

# `profile_search_cache.source` for a row answered by T316's local fallback over `aoe_profiles`
# instead — `data-model.md`'s own name for what FR-004d's fallback searches, and the value
# `test_players_routes.py` (T317) already seeds directly to exercise the "degraded" reading of a
# cache hit.
_FALLBACK_SOURCE = "aoe_profiles"


class _SearchProvider(Protocol):
    """What this service needs from whatever provider it is given: `PlayerSearchProvider`
    (`contracts/providers.md`) plus `is_degraded()` — this module's own extension of that contract,
    designed by `test_player_search.py`'s `_FakeSearchProvider` and not yet grown on
    `CompanionEnrichmentProvider` itself (see the module docstring)."""

    def is_degraded(self) -> bool: ...

    async def search_players(self, query: str, *, limit: int) -> PlayerSearchPage: ...


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
    provider: _SearchProvider,
    query: str,
    *,
    limit: int,
    ttl_seconds: int,
    now: datetime | None = None,
) -> SearchOutcome:
    """Cache-first, breaker-checked, never an exception — see the module docstring for why each of
    those three is in that order. `_local_fallback_results` below is T316's local fallback over
    `aoe_profiles`; this function's own shape does not change under that.
    """
    moment = now if now is not None else datetime.now(UTC)
    query_normalised = normalise_query(query)

    cached = await _read_fresh_cache(session, query_normalised, ttl_seconds=ttl_seconds, now=moment)
    if cached is not None:
        return cached

    if provider.is_degraded():
        results = await _local_fallback_results(session, query_normalised, limit=limit)
        await _write_cache(
            session,
            query_normalised,
            results,
            source=_FALLBACK_SOURCE,
            ttl_seconds=ttl_seconds,
            now=moment,
        )
        return SearchOutcome(
            results=results, degraded=True, reason=_SEARCH_SOURCE_UNAVAILABLE_REASON
        )

    page = await provider.search_players(query, limit=limit)
    await _write_cache(
        session,
        query_normalised,
        page.results,
        source=_COMPANION_SOURCE,
        ttl_seconds=ttl_seconds,
        now=moment,
    )
    return SearchOutcome(results=page.results, degraded=False, reason=None)


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


async def _read_fresh_cache(
    session: AsyncSession, query_normalised: str, *, ttl_seconds: int, now: datetime
) -> SearchOutcome | None:
    """`None` on a miss — no row, or a row older than `ttl_seconds` — so the caller re-fetches
    exactly as if nothing were cached. A hit reads `degraded` off `source` rather than re-asking the
    provider (module docstring)."""
    row = await session.get(ProfileSearchCache, query_normalised)
    if row is None:
        return None
    if row.fetched_at < now - timedelta(seconds=ttl_seconds):
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
    now: datetime,
) -> None:
    """Replace `query_normalised`'s row (or insert it, on a first ask) and, in the same call,
    delete every row across the whole table past `ttl_seconds` — the opportunistic pruning FR-044
    requires in place of a job (module docstring). Not scoped to `query_normalised`'s own row:
    unlike `rate_limit_counters`'s `(user_id, bucket)` scoping in `ratelimit.py`, nothing else
    bounds the *variety* of queries this table accumulates, so every stale row is disposable on
    every write, not only this one's own predecessor.
    """
    threshold = now - timedelta(seconds=ttl_seconds)
    await session.execute(
        delete(ProfileSearchCache).where(ProfileSearchCache.fetched_at < threshold)
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
