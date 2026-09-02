"""The players router (T319, T328): `GET /api/players/search`, `GET /api/players/{profile_id}`,
`GET /api/players/{profile_id}/ratings`, `GET /api/players/{profile_id}/matches`.
`contracts/http-api.md`'s "Players" section, `apps/api/tests/test_players_routes.py` (T317) and
`apps/api/tests/test_players_history.py`/`test_third_party_history.py` (T325, T326) are ground
truth for every shape below.

**`GET /api/players/{profile_id}/matches` (T328, FR-007, FR-011, FR-012).** Unlike the other three
routes here, this one writes: `spec.md`'s own Assumptions state "a third party's match history is
read from the source on demand and is no deeper than the source provides" — so every call fetches
`profile_id`'s recent matches live from Relic and persists whatever comes back verbatim
(constitution III, FR-011), through the *exact* upsert path `aoe2stats_ingester.discover`'s
`DiscoverStage` already uses for a consenting user's own history (`upsert_match`,
`touch_aoe_profile`, `upsert_match_player`, called directly rather than through the whole stage,
which also refreshes ratings and enqueues captures system-wide — neither of which this route may
do: FR-012 forbids beginning capture for a third party at all). A source outage does not fail the
request: any failure of that fetch is swallowed and the route serves whatever this service already
knows, the same honesty discipline `search.py` applies for FR-004d — see
`_refresh_third_party_history`'s own docstring for why that catch is deliberately broader than
`ProviderError` alone. The response row shape is imported directly from `routers/matches.py`
(`match_row_json`) rather than restated, so the two routes can never drift on the one shape
`contracts/http-api.md` promises is identical.

**"Any profile" is the whole point, and "any profile" is exactly what does not change here.**
`routers/profiles.py`'s `/api/profiles/*` means "mine" and is ownership-scoped throughout
(`_owned_active_link`); this router's `/api/players/*` means "anyone" and never checks who the
caller is beyond "signed in" (FR-008a property 1). The two routers deliberately duplicate their
session-resolution helpers (`_current_session_row`, `_require_session`) rather than share
one — `routers/auth.py` and `routers/profiles.py` already establish that convention, and this
router follows it rather than inventing an import between two routers for four lines of code.

**No profile is withheld on privacy grounds** (FR-004c retired, T301a): `GET /api/players/
{profile_id}` and its `/ratings` sibling answer `200` for any profile this service has ever
observed — including a never-ranked one, with empty ladder data (`contracts/http-api.md`) — and
`404` only for a `profile_id` this service has no `aoe_profiles` row for at all. What keeps a
third party's page from being a public listing is FR-010 (`app.py`'s `_NoIndexHeaderMiddleware`,
T309) and the beta allowlist, not a per-profile flag.

**Search: cache-first, rate-limited per user, and wired to the real source here for the first
time.** `search.py` (T315, T316) is a pure function of its inputs — the cache TTL and the search
result limit are read from `settings` exactly once, in this module, and passed in; `search.py`
itself never calls `get_settings()`. `_build_search_provider` below is the wiring `search.py`'s
own module docstring names as deferred to this task, reusing the provider's own breaker rather
than adding a second one — a search storm and an enrichment storm are the same source under the
same protection (`contracts/providers.md`).

**The breaker outlives the request; the provider around it does not.** `_companion_breaker()`
below is held at module scope for the process's lifetime, exactly like `_COMPANION_HTTP_CLIENT`
and `_COMPANION_RATE_LIMITER` — a `CompanionEnrichmentProvider` rebuilt fresh per request (because
its `call_sink` closes over the request's own `db_session`, see `_companion_call_sink`) is handed
that *same* breaker every time via `CompanionEnrichmentProvider(breaker=...)`
(`packages/providers/.../companion/provider.py`), rather than growing a fresh, always-closed one
of its own on every request. Without this, `is_degraded()` could never observe an outage a
previous request had already recorded, and FR-004d's fallback branch would be unreachable in
production even though every unit test exercises it directly. `_companion_breaker()` is
`functools.lru_cache`d rather than a bare module global for the same reason `get_settings()` is:
so a test that deliberately trips it can reset it (`.cache_clear()`) afterwards without leaking
that state into an unrelated test — `apps/api/tests/conftest.py`'s own autouse fixture does this
automatically for every test in this suite now (MJ-4 remediation), so a test that reaches this
router only through `client` no longer has to remember to.

**MJ-3 remediation: the breaker is built through `aoe2stats_providers.wiring`, not through the
concrete `companion` module.** `build_companion_breaker()` (imported below alongside
`build_async_client_resources`) is the wiring-layer constructor for exactly this process-lifetime
resource, the same boundary `_COMPANION_HTTP_CLIENT`/`_COMPANION_RATE_LIMITER` already go through
— `CompanionEnrichmentProvider.__init__`'s `breaker` parameter is required, not optional, so there
is no default left that could silently reproduce this defect at a future call site the way an
omitted `breaker=None` used to (`companion/provider.py`'s own module docstring).

Unlike `_build_relic_provider` in `routers/auth.py`, this router's call sink writes straight onto
the request's own `db_session` rather than a separate short-lived one: `CompanionEnrichmentProvider`
never raises (`packages/providers/.../companion/provider.py`'s own module docstring — "the only
provider whose failure is not an error"), so there is no mid-request exception here that could
roll the request's transaction back and take an already-recorded `provider_calls` row with it, the
failure mode `_async_call_sink` in `auth.py` exists to avoid for Relic.

Rate limiting (FR-005) is the one thing `search.py` does not do: `check_and_increment`
(`ratelimit.py`, T307) is called here, in the `search` bucket, before the query ever reaches
`search.py` — a caller past the per-minute limit never even touches the cache, and the response
is the `rate_limited` envelope `contracts/http-api.md` names, carrying `retry_after`.
"""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, Query, Request
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from aoe2stats_api import security
from aoe2stats_api.deps import SessionDep, SettingsDep
from aoe2stats_api.errors import APIError
from aoe2stats_api.leaderboards import leaderboard_name
from aoe2stats_api.ratelimit import check_and_increment
from aoe2stats_api.routers.matches import enrich_colours, match_row_json
from aoe2stats_api.search import persist_avatar_hashes
from aoe2stats_api.search import search_players as run_search
from aoe2stats_ingester import discover
from aoe2stats_providers.base import ProviderCallRecord
from aoe2stats_providers.companion.provider import CompanionEnrichmentProvider
from aoe2stats_providers.relic.matches import RelicMatchHistoryProvider
from aoe2stats_providers.wiring import (
    CircuitBreaker,
    build_async_client_resources,
    build_companion_breaker,
)
from aoe2stats_storage.models import AoeProfile, ProviderCall
from aoe2stats_storage.models import Session as SessionRow
from aoe2stats_storage.repositories.matches import DEFAULT_PAGE_SIZE, MatchesRepository
from aoe2stats_storage.repositories.ratings import RatingsRepository

router = APIRouter(tags=["players"])

# Match-history traffic against Relic's own `getRecentMatchHistory` (T328) — the identical host,
# timeout and rate discipline `_build_relic_provider` already wires for `RelicProfileProvider` in
# `routers/auth.py`, duplicated here rather than imported: this router's own convention, stated in
# the module docstring, of a self-contained file over a four-line cross-router import.
_RELIC_RATE_PER_SECOND = 5.0
_RELIC_HTTP_CLIENT, _RELIC_RATE_LIMITER = build_async_client_resources(_RELIC_RATE_PER_SECOND)


def _relic_call_sink(db_session: AsyncSession) -> Callable[[ProviderCallRecord], Awaitable[None]]:
    """Writes a `provider_calls` row on its **own**, short-lived session — never queued onto
    `db_session` itself. Mirrors `routers/auth.py`'s `_async_call_sink` byte for byte, and is not
    `_companion_call_sink` above: Relic is a provider that *can* fail mid-request
    (`RelicMatchHistoryProvider.recent_matches`, unlike `CompanionEnrichmentProvider`, which never
    raises — module docstring), and `session_scope` (`deps.py`) rolls the whole request
    transaction back on any unhandled exception — a row added to `db_session` for the very call
    that raised would be rolled back with it, losing exactly the call an operator most needs
    recorded (constitution III)."""

    async def _sink(record: ProviderCallRecord) -> None:
        bind = db_session.get_bind()
        assert isinstance(bind, Engine), f"expected an Engine bind, got {type(bind)}"
        audit_engine = AsyncEngine(bind)
        async with AsyncSession(bind=audit_engine) as audit_session:
            audit_session.add(
                ProviderCall(
                    provider=record.provider,
                    endpoint=record.endpoint,
                    status_code=record.status_code,
                    duration_ms=record.duration_ms,
                    called_at=record.called_at,
                    rate_limited=record.rate_limited,
                )
            )
            await audit_session.commit()

    return _sink


def _build_match_history_provider(db_session: AsyncSession) -> RelicMatchHistoryProvider:
    return RelicMatchHistoryProvider(
        client=_RELIC_HTTP_CLIENT,
        timeout_seconds=_PROVIDER_TIMEOUT_SECONDS,
        rate_limiter=_RELIC_RATE_LIMITER,
        call_sink=_relic_call_sink(db_session),
    )


async def _refresh_third_party_history(db_session: AsyncSession, profile_id: int) -> None:
    """FR-007/FR-011, "read from the source on demand" (`spec.md`'s own Assumptions): fetch
    `profile_id`'s recent matches live from Relic and persist them through the exact upsert path
    `aoe2stats_ingester.discover.DiscoverStage` already uses for a consenting user's own history —
    `discover.upsert_match`/`discover.touch_aoe_profile`/`discover.upsert_match_player`, called
    directly rather than through a whole `DiscoverStage` (which also refreshes ratings system-wide
    and enqueues captures for every consenting profile it finds, neither of which this route may
    do: FR-012 forbids beginning capture for a third party at all, and this route touches only the
    one profile it was asked about).

    A source outage does not fail the request: any failure of this fetch is swallowed and the
    route falls back to whatever this service already knows about `profile_id`, the same honesty
    discipline `search.py` already applies for FR-004d. Deliberately broader than `ProviderError`
    alone: this call is the one place in the codebase where a live Relic fetch is *optional* —
    every other caller of `RelicMatchHistoryProvider`/`RelicProfileProvider` (the ingester, the
    sign-in flow) needs a failure to propagate, because there is a person or a process waiting on
    a real answer. This route already has one, drawn from storage a moment later regardless of
    whether the refresh above succeeded, so nothing here is lost by treating "the fetch could not
    be completed, for any reason" and "the fetch reported a provider failure" identically. This
    function never enqueues a `replay_captures` row.
    """
    provider = _build_match_history_provider(db_session)
    try:
        raw_matches = await provider.recent_matches([profile_id])
    except Exception:
        # See the docstring above: broader than `ProviderError` on purpose, because this fetch is
        # optional and its failure, however it is shaped, must never turn into a failed read.
        return

    for raw_match in raw_matches:
        await discover.upsert_match(db_session, raw_match)
        for player_profile_id in raw_match.player_profile_ids:
            await discover.touch_aoe_profile(db_session, player_profile_id)
            await discover.upsert_match_player(db_session, raw_match, player_profile_id)


# FR-005's own bucket name (`RateLimitCounter`'s docstring, `ratelimit.py`) and the fixed window
# "per minute" already names — a structural constant of what "per minute" means, not a tuning
# knob, so it stays a literal here exactly as `test_rate_limits.py`'s own `_WINDOW_SECONDS` does.
_SEARCH_RATE_LIMIT_BUCKET = "search"
_SEARCH_RATE_LIMIT_WINDOW_SECONDS = 60

# How many results one search page returns. No `.env.example` knob names this — `contracts/
# providers.md` documents `limit` as a parameter `search_players` enforces, never a number — so
# this is this router's own, generous-enough-for-a-name-search constant, the same footing
# `_PROVIDER_TIMEOUT_SECONDS` has in `routers/auth.py`.
_SEARCH_RESULT_LIMIT = 20

# Interactive search traffic, not the daily bulk cycle `AOEMS_MAX_REQUESTS_PER_SECOND` governs
# (`.env.example`) — mirrors `routers/auth.py`'s identical reasoning for Steam and Relic.
_PROVIDER_TIMEOUT_SECONDS = 10.0
_COMPANION_RATE_PER_SECOND = 5.0

# Built once per process, held for the lifetime of the process — the same discipline
# `routers/auth.py` applies to its own provider clients (module docstring there): the expensive
# resources (the connection pool, the token bucket) are shared across every request, and only a
# thin per-call sink is built fresh.
_COMPANION_HTTP_CLIENT, _COMPANION_RATE_LIMITER = build_async_client_resources(
    _COMPANION_RATE_PER_SECOND
)


@functools.lru_cache(maxsize=1)
def _companion_breaker() -> CircuitBreaker:
    """The one `CircuitBreaker` `_build_search_provider` hands to every request's own, otherwise
    disposable, `CompanionEnrichmentProvider` (module docstring's "The breaker outlives the
    request" note) — `lru_cache` rather than a bare module global, like `_COMPANION_HTTP_CLIENT`
    above, only so a test that deliberately trips it can reset it with `.cache_clear()` once it is
    done, the same device `get_settings()` uses for the identical reason.
    """
    return build_companion_breaker()


def _companion_call_sink(
    db_session: AsyncSession,
) -> Callable[[ProviderCallRecord], Awaitable[None]]:
    """Writes a `provider_calls` row directly onto the request's own `db_session` — safe here,
    unlike `routers/auth.py`'s `_async_call_sink` for Relic, because `CompanionEnrichmentProvider`
    never raises (module docstring): there is no exception this call could cause that would roll
    the request's transaction back and take the row with it."""

    async def _sink(record: ProviderCallRecord) -> None:
        db_session.add(
            ProviderCall(
                provider=record.provider,
                endpoint=record.endpoint,
                status_code=record.status_code,
                duration_ms=record.duration_ms,
                called_at=record.called_at,
                rate_limited=record.rate_limited,
            )
        )

    return _sink


def _build_search_provider(db_session: AsyncSession) -> CompanionEnrichmentProvider:
    return CompanionEnrichmentProvider(
        client=_COMPANION_HTTP_CLIENT,
        timeout_seconds=_PROVIDER_TIMEOUT_SECONDS,
        rate_limiter=_COMPANION_RATE_LIMITER,
        call_sink=_companion_call_sink(db_session),
        breaker=_companion_breaker(),
    )


# --- Session resolution, the same discipline `auth.py`/`profiles.py` already establish -----------


async def _current_session_row(
    request: Request, db_session: AsyncSession, secret: str
) -> SessionRow | None:
    session_id = security.read_session_id(request.cookies.get(security.SESSION_COOKIE_NAME), secret)
    if session_id is None:
        return None
    return await security.get_active_session(db_session, session_id)


def _require_session(session_row: SessionRow | None) -> SessionRow:
    if session_row is None:
        raise APIError(
            status_code=401,
            code="not_authenticated",
            message="Sign in to view a player's profile.",
        )
    return session_row


def _profile_not_found() -> APIError:
    """The one `404` these routes have left after FR-004c's retirement (module docstring): a
    `profile_id` this service has never itself observed."""
    return APIError(
        status_code=404,
        code="not_found",
        message="This player has never been observed by this service.",
    )


# --- GET /api/players/search — FR-001, FR-003, FR-004e, FR-005 ----------------------------------


@router.get("/players/search")
async def search_for_players(
    request: Request,
    db_session: SessionDep,
    settings: SettingsDep,
    q: str = Query(..., min_length=1),
) -> dict[str, Any]:
    """FR-001: find a player by display name. FR-005: rate limited per user, in the `search`
    bucket, before the query ever reaches `search.py`'s cache. FR-003: `degraded` and `reason`
    are passed straight through from `SearchOutcome`, never collapsed with `results`' own length.
    """
    secret = settings.app_secret_key.get_secret_value()
    session_row = _require_session(await _current_session_row(request, db_session, secret))

    rate_limit = await check_and_increment(
        db_session,
        user_id=session_row.user_id,
        bucket=_SEARCH_RATE_LIMIT_BUCKET,
        limit=settings.player_search_max_per_user_per_minute,
        window_seconds=_SEARCH_RATE_LIMIT_WINDOW_SECONDS,
    )
    if not rate_limit.allowed:
        raise APIError(
            status_code=429,
            code="rate_limited",
            message="Too many searches. Try again shortly.",
            detail={"retry_after": rate_limit.retry_after},
        )

    provider = _build_search_provider(db_session)
    outcome = await run_search(
        db_session,
        provider,
        q,
        limit=_SEARCH_RESULT_LIMIT,
        ttl_seconds=settings.player_search_cache_ttl_seconds,
    )

    if not outcome.degraded:
        # T426 (D6, research.md): this is the one call site in the codebase that ever holds a
        # genuine, non-degraded companion page — `search.py`'s own module docstring names it as
        # such. A degraded outcome's results are read from `aoe_profiles` itself (`search.py`'s
        # `_local_fallback_results`) and never carry a hash, so `persist_avatar_hashes` would be a
        # guaranteed no-op over them; skipping the call on that branch costs nothing and avoids an
        # unnecessary write on every degraded search.
        await persist_avatar_hashes(db_session, outcome.results)

    return {
        "results": [
            {
                "profile_id": result.profile_id,
                "alias": result.alias,
                "country": result.country,
                "games_played": result.games_played,
                "clan": result.clan,
                # The source's own claim, carried unverified since constitution IX 3.0.0
                # (2026-08-24) — `null` on the degraded fallback (`search.py`'s
                # `_local_fallback_results`), which reads `aoe_profiles` and has no such claim
                # (`contracts/http-api.md`'s search section).
                "unverified_steam_id": result.unverified_steam_id,
            }
            for result in outcome.results
        ],
        "degraded": outcome.degraded,
        "reason": outcome.reason,
    }


# --- GET /api/players/{profile_id} — FR-006, FR-008, FR-008a property 1 -------------------------


async def _profile_ratings(db_session: AsyncSession, profile_id: int) -> list[dict[str, Any]]:
    """The latest `rating_snapshots` row per leaderboard `profile_id` has played, in the same
    shape `routers/profiles.py` already serves for the caller's own profiles (FR-008), reusing
    `RatingsRepository.history_for_profile` rather than a second "latest per group" query: that
    history is already ordered oldest first, so the last occurrence per `leaderboard_id` while
    iterating it *is* the latest — no second SQL statement needed for a value this router's other
    route (`/ratings`) already fetches the same way.
    """
    snapshots = await RatingsRepository(db_session).history_for_profile(profile_id=profile_id)
    latest_by_leaderboard: dict[int, Any] = {}
    for snapshot in snapshots:
        latest_by_leaderboard[snapshot.leaderboard_id] = snapshot
    return [
        {
            "leaderboard_id": snapshot.leaderboard_id,
            "leaderboard_name": leaderboard_name(snapshot.leaderboard_id),
            "rating": snapshot.rating,
            "rank": snapshot.rank,
            "wins": snapshot.wins,
            "losses": snapshot.losses,
            "streak": snapshot.streak,
            "highest_rating": snapshot.highest_rating,
            "captured_at": snapshot.captured_at.isoformat(),
        }
        for snapshot in latest_by_leaderboard.values()
    ]


@router.get("/players/{profile_id}")
async def get_player_profile(
    profile_id: int, request: Request, db_session: SessionDep, settings: SettingsDep
) -> dict[str, Any]:
    """FR-006, FR-008a property 1: any profile this service has observed, never only the
    caller's own. `200` with empty ladder data for a never-ranked player (US1 scenario 5); `404`
    only for a `profile_id` this service has never itself observed (module docstring).

    **T426, `contracts/http-api.md`: `avatar_hash` is read straight off `aoe_profiles`, never
    fetched.** `null` is the ordinary case for a profile never seen in a companion response
    (`search.py`'s `persist_avatar_hashes` is the only writer), not an error — this route makes no
    provider call at all, and this field is why it can still answer the hash (D6, research.md)."""
    secret = settings.app_secret_key.get_secret_value()
    _require_session(await _current_session_row(request, db_session, secret))

    profile = await db_session.get(AoeProfile, profile_id)
    if profile is None:
        raise _profile_not_found()

    ratings = await _profile_ratings(db_session, profile_id)

    return {
        "profile_id": profile.profile_id,
        "alias": profile.alias,
        "country": profile.country,
        "avatar_hash": profile.avatar_hash,
        "alias_observed_at": profile.alias_observed_at.isoformat()
        if profile.alias_observed_at is not None
        else None,
        "ratings": ratings,
    }


# --- GET /api/players/{profile_id}/ratings — FR-006, FR-008a property 1 -------------------------


@router.get("/players/{profile_id}/ratings")
async def get_player_rating_history(
    profile_id: int, request: Request, db_session: SessionDep, settings: SettingsDep
) -> dict[str, Any]:
    """`contracts/http-api.md`: "Rating history, where snapshots exist" — for any profile, oldest
    first, the same order `routers/profiles.py`'s own `/ratings` route already answers in for the
    caller's own curve. A profile with no snapshots yet gets an empty list, not an error — the
    discipline `profiles.py` already applies, generalised here to any profile."""
    secret = settings.app_secret_key.get_secret_value()
    _require_session(await _current_session_row(request, db_session, secret))

    snapshots = await RatingsRepository(db_session).history_for_profile(profile_id=profile_id)

    return {
        "ratings": [
            {
                "leaderboard_id": snapshot.leaderboard_id,
                "leaderboard_name": leaderboard_name(snapshot.leaderboard_id),
                "rating": snapshot.rating,
                "rank": snapshot.rank,
                "wins": snapshot.wins,
                "losses": snapshot.losses,
                "streak": snapshot.streak,
                "highest_rating": snapshot.highest_rating,
                "captured_at": snapshot.captured_at.isoformat(),
            }
            for snapshot in snapshots
        ]
    }


# --- GET /api/players/{profile_id}/matches — FR-007, FR-008a property 1, FR-011, FR-012 ---------


@router.get("/players/{profile_id}/matches")
async def get_player_match_history(
    profile_id: int,
    request: Request,
    db_session: SessionDep,
    settings: SettingsDep,
    cursor: str | None = None,
    limit: int = Query(default=DEFAULT_PAGE_SIZE, gt=0),
) -> dict[str, Any]:
    """FR-007: any player's matches, newest first, with opponent, map, civilisation, result,
    rating change and duration per row — `contracts/http-api.md`'s "the same row shape
    `GET /api/matches` already returns", served here via `match_row_json` (module docstring) so
    the two routes can never present the same facts two different ways (FR-008).

    `_refresh_third_party_history` runs first, on every call: this route reads the source live
    (module docstring's "on demand" note) before answering from storage, so a player this service
    has never discovered through a consenting user's own history still gets a real answer rather
    than a permanently empty one. A player with no matches at all — after that refresh — gets an
    empty list under `200`, never an error (`test_players_history.py`'s own "not an error" case);
    `404` is reserved for a `profile_id` this service has never itself observed at all
    (`_profile_not_found`, the one remaining `404` module-wide).

    **Colour enrichment (T450, FR-003).** `enrich_colours` (`routers/matches.py`, imported above)
    is called here batched over this page's own `game_ids`, exactly as `GET /api/matches::
    list_matches` already calls it for the owner-scoped route — this route already reads the
    source live on every call (the paragraph above), so a batched companion call here crosses no
    boundary that route does not already cross. Before T450 this route never called it at all, so
    `color_id` stayed `NULL` for a profile viewed only through this route and every swatch
    rendered the neutral token even though `GET /api/matches` had already coloured the identical
    match — `enrich_colours`'s own degrade discipline (never writes `NULL`, at most one call per
    page, a no-op once every row is coloured) applies here unchanged, since both routes share the
    one implementation."""
    secret = settings.app_secret_key.get_secret_value()
    _require_session(await _current_session_row(request, db_session, secret))

    profile = await db_session.get(AoeProfile, profile_id)
    if profile is None:
        raise _profile_not_found()

    await _refresh_third_party_history(db_session, profile_id)

    repository = MatchesRepository(db_session)
    try:
        page = await repository.list_matches(profile_id=profile_id, cursor=cursor, limit=limit)
    except ValueError as exc:
        raise APIError(
            status_code=422,
            code="validation_error",
            message="The request could not be validated.",
            detail={"errors": [str(exc)]},
        ) from exc

    # T450: batched over this page's own game_ids, never one call per match — the same discipline
    # `routers/matches.py::list_matches` already applies, reused rather than duplicated (module
    # docstring's "Colour enrichment" note).
    await enrich_colours(db_session, [row.game_id for row in page.matches])

    return {
        "matches": [match_row_json(row) for row in page.matches],
        "next_cursor": page.next_cursor,
    }
