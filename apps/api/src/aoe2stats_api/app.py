"""The FastAPI application — the ASGI entrypoint `api/index.py` re-exports on Vercel (T014c).

Three things this module owns and nothing else: the exception handlers that make the single error
envelope from `contracts/http-api.md` true of *every* response — not only the ones a router built
by hand with `APIError`, but an unmatched route, a validation failure, or a genuinely unexpected
exception too — the router registration, and the `X-Robots-Tag`/`Cache-Control` middleware (T309,
widened to a default-deny posture by T384, FR-010) that keeps every `/api/*` response out of a
crawler or a shared cache by default, regardless of which router answers it, with the handful of
routes named in `_BARE_API_PATH_PATTERNS` the only ones exempted.

Routers are wired with `app.include_router(<module>.router, prefix="/api")` and nothing more.
That is deliberate: this task (T014) ships only `health.py`, T018 adds `cron.py` — the local cron
trigger route — and every user-story phase after it adds a router of its own (`auth.py`,
`profiles.py`, `matches.py`, `replays.py`, `privacy.py`). Each one is a two-line addition here —
one import, one `include_router` call — and never a change to this module's structure.

**T018c**: `import aoe2stats_api.app` must never load the replay engine — constitution V's "the
API never loads an engine at all". `routers/cron.py` is the one router with a path down to it (via
`apps/ingester`, which will depend on `packages/replay-engine` from T055 onward), and it imports
`run_once` inside its handler rather than at module scope for exactly that reason; nothing in this
module or any router it registers may import `aoe2stats_ingester.run` — or anything beneath it —
at module scope. `apps/api/tests/test_engine_isolation.py` asserts this in a subprocess, since a
regression here would still leave `aoe2rec_py` out of *this* process's already-populated
`sys.modules` and pass silently in-process.
"""

from __future__ import annotations

import logging
import re
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from aoe2stats_api.errors import APIError, error_response
from aoe2stats_api.routers import (
    auth,
    cron,
    favourites,
    health,
    matches,
    players,
    privacy,
    profiles,
    replays,
)
from aoe2stats_api.settings import ConfigurationError

logger = logging.getLogger("aoe2stats_api")

# T384: the default is now deny-by-default for the crawler and the shared cache, not the other
# way round. Before this task the middleware matched a hand-maintained *inclusion* list — four
# path patterns naming 003's own routers — and every route outside it, 001's included, answered
# unheadered. `test_no_index_headers.py`'s own `test_non_feature_route_headers_are_unchanged`
# then asserted that absence, so a route added later under a fifth prefix was not merely
# unprotected, the suite actively ratified it (five later tasks — T327, T328, T337, T346, T368 —
# each add one). Inverting the default closes that permanently: every `/api/*` response now
# carries `X-Robots-Tag: noindex, nofollow` and `Cache-Control: private` unless its path matches
# `_BARE_API_PATH_PATTERNS` below, so a route registered under a router nobody named here still
# gets the header the moment it exists — the same "matched on the request path, not a route
# template" property T309 always had, now applied to the *exemption* instead of the inclusion.
#
# `_BARE_API_PATH_PATTERNS` is deliberately short: only a route that must legitimately stay
# reachable and cacheable by something outside this service belongs on it, and today that is
# `GET /api/health` alone. It is the one 001 route the contract itself singles out as
# unauthenticated (`specs/001-.../contracts/http-api.md`: "a health check above all, since
# `/api/health` is unauthenticated") and it carries no personal or third-party data by
# construction — the same contract forbids a configuration value or secret in its body. Its whole
# purpose is to be polled from outside this process (uptime monitors, `scripts/checks/
# production-health.mjs`, the platform's own health probing), which `noindex`/`private` exist to
# discourage. `/api/cron/ingest` is *not* on this list despite also being unauthenticated by
# session: constitution VIII states it "is never publicly invocable" — the opposite property —
# and its bearer-secret gate already answers 401 to anything that is not the scheduler, so the
# header only adds defence in depth there, same as every other 001 route now gets by default.
#
# `GET /api/matches/{game_id}` is 001's route, widened by this feature rather than added, and its
# *status code* still comes from 001's ownership scope until T327 removes it — but the header is
# no longer conditional on that removal at all: this route's path does not match
# `_BARE_API_PATH_PATTERNS`, so it now carries the header on the still-scoped 403/404 exactly as
# it will on the 200 T327 unlocks. T310's `test_match_detail_widening_carries_the_no_index_header`
# (`xfail(..., reason="T327 not implemented yet")`) keeps failing until T327 lands regardless,
# because its `status_code == 200` assertion runs first and 001's ownership scope still answers
# 403/404 — the header assertion beside it would already pass today, it is simply not what keeps
# that test red.
_BARE_API_PATH_PATTERNS: tuple[re.Pattern[str], ...] = (re.compile(r"^/api/health$"),)


def is_bare_api_path(path: str) -> bool:
    """`True` for the handful of `/api/*` paths `_NoIndexHeaderMiddleware` exempts from the
    header by design (see `_BARE_API_PATH_PATTERNS` above). Exposed rather than kept private so
    `test_no_index_headers.py` asserts against this single source of truth instead of maintaining
    a second, hand-written copy of the same list — exactly the duplication this task's own
    instructions warn against."""
    return any(pattern.match(path) for pattern in _BARE_API_PATH_PATTERNS)


class _NoIndexHeaderMiddleware:
    """ASGI middleware, not a per-route decorator: a decorator is a thing a new route in
    `players.py` or `favourites.py` can simply omit, and FR-010 has to hold for exactly that route
    someone forgets. Headers every `/api/*` request by default and consults
    `_BARE_API_PATH_PATTERNS` only for the handful of routes that must stay bare — the inverse of
    T309's original inclusion list (see the comment above `_BARE_API_PATH_PATTERNS`). Matching on
    `request.url.path` rather than a route template means the guarantee is already true of a route
    before its router is even registered — the plain 404 `test_no_index_headers.py` exercises
    today answers the header exactly as the 200 or 401 will once its router is registered.

    Plain ASGI rather than `BaseHTTPMiddleware`: this only ever adds two headers to whatever the
    app already answers, never reads or buffers the body, so there is nothing here that needs
    `BaseHTTPMiddleware`'s response-wrapping.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or not scope["path"].startswith("/api/")
            or is_bare_api_path(scope["path"])
        ):
            await self._app(scope, receive, send)
            return

        async def _send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers: list[tuple[bytes, bytes]] = list(message.get("headers", []))
                headers.append((b"x-robots-tag", b"noindex, nofollow"))
                headers.append((b"cache-control", b"private"))
                message = {**message, "headers": headers}
            await send(message)

        await self._app(scope, receive, _send_with_headers)


def _http_status_error_code(status_code: int) -> str:
    """A generic `code` for a plain `HTTPException` Starlette or FastAPI raised on its own.

    Every *domain* error a router raises deliberately (`no_aoe2_profile`, `not_allowlisted`, ...)
    goes through `APIError` with its own product-meaningful code instead of this function — this
    path only covers the framework-level cases nobody raises by hand, such as an unmatched route
    (404) or a disallowed method (405).
    """
    try:
        phrase = HTTPStatus(status_code).phrase
    except ValueError:
        return "http_error"
    return phrase.lower().replace(" ", "_").replace("-", "_")


def create_app() -> FastAPI:
    """Build the `FastAPI` instance. A function rather than only a module-level constant so a
    test can build a fresh app if it ever needs to, without reimporting the module."""
    app = FastAPI(title="aoe2-stats API")
    app.add_middleware(_NoIndexHeaderMiddleware)

    @app.exception_handler(APIError)
    async def _handle_api_error(_: Request, exc: APIError) -> object:
        return error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            detail=exc.detail,
        )

    @app.exception_handler(HTTPException)
    async def _handle_http_exception(_: Request, exc: HTTPException) -> object:
        detail: dict[str, object] = exc.detail if isinstance(exc.detail, dict) else {}
        message = exc.detail if isinstance(exc.detail, str) else "An error occurred."
        return error_response(
            status_code=exc.status_code,
            code=_http_status_error_code(exc.status_code),
            message=message,
            detail=detail,
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(_: Request, exc: RequestValidationError) -> object:
        return error_response(
            status_code=422,
            code="validation_error",
            message="The request could not be validated.",
            detail={"errors": exc.errors()},
        )

    @app.exception_handler(ConfigurationError)
    async def _handle_configuration_error(request: Request, exc: ConfigurationError) -> object:
        # T390. `Settings` fails to build while FastAPI resolves a route's dependencies —
        # `SessionDep` and `ObjectStoreDep` each call `get_settings()` internally (`deps.py`),
        # `SettingsDep` is that call — so this fires *before* any route body runs, for every
        # route at once. Until this handler existed the only route that said which keys were
        # wrong was `/api/health`, which resolves `Settings` inside its own `try` (T014e); every
        # other route fell through to `_handle_unexpected_error` below and answered
        # `internal_error` with an empty `detail`. That cost a production outage its diagnosis:
        # `GET /api/me` answered 500 saying nothing while `/api/health` already held the answer,
        # and nobody had reason to ask the second question after the first one.
        #
        # 503, not 500: the deployment cannot serve requests *as configured*, and an operator
        # fixing the environment fixes it — the same status and the same `configuration_invalid`
        # code `/api/health` has always used for this fault, so a caller sees one shape for one
        # cause on every route.
        #
        # `exc.keys` is alias names only, never values (see `ConfigurationError`). Naming them in
        # the response of an unauthenticated route is deliberate and matches `health.py`'s own
        # reasoning: a key *name* is diagnosis the caller cannot already have, while the value
        # behind it stays out of the response and out of this log line.
        logger.error(
            "Settings failed to build while handling %s %s: missing or invalid keys %s",
            request.method,
            request.url.path,
            exc.keys,
        )
        return error_response(
            status_code=503,
            code="configuration_invalid",
            message="The application configuration is invalid.",
            detail={"missing_or_invalid_keys": exc.keys},
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected_error(request: Request, exc: Exception) -> object:
        # Constitution VIII: never a secret in a log. Nothing about the request body or headers
        # is logged here, only the method and path, and the traceback logging captures whatever
        # the exception itself carries — the same discipline `raise_alert` callers owe (T014a).
        logger.exception("Unhandled error handling %s %s", request.method, request.url.path)
        return error_response(
            status_code=500,
            code="internal_error",
            message="An unexpected error occurred.",
        )

    app.include_router(health.router, prefix="/api")
    app.include_router(cron.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(profiles.router, prefix="/api")
    app.include_router(privacy.router, prefix="/api")
    app.include_router(replays.router, prefix="/api")
    app.include_router(matches.router, prefix="/api")
    app.include_router(players.router, prefix="/api")
    app.include_router(favourites.router, prefix="/api")

    return app


app = create_app()
