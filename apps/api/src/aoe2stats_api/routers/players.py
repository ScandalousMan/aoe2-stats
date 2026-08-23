"""The players router (T319): `GET /api/players/search`, `GET /api/players/{profile_id}`,
`GET /api/players/{profile_id}/ratings`. `contracts/http-api.md`'s "Players" section and
`apps/api/tests/test_players_routes.py` (T317) are ground truth for every shape below.

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
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api import security
from aoe2stats_api.deps import SessionDep, SettingsDep
from aoe2stats_api.errors import APIError
from aoe2stats_api.leaderboards import leaderboard_name
from aoe2stats_api.ratelimit import check_and_increment
from aoe2stats_api.search import search_players as run_search
from aoe2stats_providers.base import ProviderCallRecord
from aoe2stats_providers.companion.provider import CompanionEnrichmentProvider
from aoe2stats_providers.wiring import (
    CircuitBreaker,
    build_async_client_resources,
    build_companion_breaker,
)
from aoe2stats_storage.models import AoeProfile, ProviderCall
from aoe2stats_storage.models import Session as SessionRow
from aoe2stats_storage.repositories.ratings import RatingsRepository

router = APIRouter(tags=["players"])

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

    return {
        "results": [
            {
                "profile_id": result.profile_id,
                "alias": result.alias,
                "country": result.country,
                "games_played": result.games_played,
                "clan": result.clan,
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
    only for a `profile_id` this service has never itself observed (module docstring)."""
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
