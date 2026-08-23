"""The FastAPI application — the ASGI entrypoint `api/index.py` re-exports on Vercel (T014c).

Three things this module owns and nothing else: the exception handlers that make the single error
envelope from `contracts/http-api.md` true of *every* response — not only the ones a router built
by hand with `APIError`, but an unmatched route, a validation failure, or a genuinely unexpected
exception too — the router registration, and the `X-Robots-Tag`/`Cache-Control` middleware (T309,
FR-010) that keeps 003's third-party pages out of a crawler or a shared cache regardless of which
of those routers answers.

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
from aoe2stats_api.routers import auth, cron, health, matches, players, privacy, profiles, replays
from aoe2stats_api.settings import ConfigurationError

logger = logging.getLogger("aoe2stats_api")

# The routes 003 adds — `players.py` (T319, registered below) and `favourites.py` (not registered
# yet; a later Phase 3 task adds it) — plus the two new per-participant `matches.py` sub-routes,
# `.../replay/{profile_id}`
# and `.../analysis`, and `GET /api/matches/{game_id}` itself. Matched against the *request path*,
# not a route template, which is what lets this hold for a route that is not registered yet at
# all: FR-010 must cover the 404 a crawler gets today exactly as it will the 200 or 401 the router
# answers once it exists (contracts/http-api.md, "Response headers on every route above" —
# "every route above" includes the "Matches, widened" table; constitution IX, never publicly
# indexed).
#
# `GET /api/matches/{game_id}` is 001's route, widened by this feature rather than added, and its
# *status code* still comes from 001's ownership scope until T327 removes it — but the header is
# this middleware's property regardless, same as every other route here, because the contract
# states it belongs to the response for every route, not only the ones this feature registers.
# T310's `test_match_detail_widening_carries_the_no_index_header` (`xfail(..., reason="T327 not
# implemented yet")`) only *asserts* the header for this route — it has no path back to this
# middleware, so the assertion staying `xfail` after T309 lands is expected: today it fails on the
# still-scoped 403/404 before it ever reaches the header check, and T327 removing that scope, not
# a change here, is what lets it reach the header assertion at all.
_NO_INDEX_PATH_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^/api/players(/.*)?$"),
    re.compile(r"^/api/favourites(/.*)?$"),
    re.compile(r"^/api/matches/[^/]+$"),
    re.compile(r"^/api/matches/[^/]+/replay/[^/]+$"),
    re.compile(r"^/api/matches/[^/]+/analysis$"),
)


class _NoIndexHeaderMiddleware:
    """ASGI middleware, not a per-route decorator: a decorator is a thing a new route in
    `players.py` or `favourites.py` can simply omit, and FR-010 has to hold for exactly that route
    someone forgets. Matching on `request.url.path` against `_NO_INDEX_PATH_PATTERNS` means the
    guarantee is already true of a route before its router is even registered — the plain 404
    `test_no_index_headers.py` exercises today answers the header exactly as the 200 will once
    Phase 3 registers the router underneath it.

    Plain ASGI rather than `BaseHTTPMiddleware`: this only ever adds two headers to whatever the
    app already answers, never reads or buffers the body, so there is nothing here that needs
    `BaseHTTPMiddleware`'s response-wrapping.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not any(
            pattern.match(scope["path"]) for pattern in _NO_INDEX_PATH_PATTERNS
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

    return app


app = create_app()
