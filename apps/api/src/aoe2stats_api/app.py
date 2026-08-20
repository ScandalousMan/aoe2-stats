"""The FastAPI application — the ASGI entrypoint `api/index.py` re-exports on Vercel (T014c).

Two things this module owns and nothing else: the exception handlers that make the single error
envelope from `contracts/http-api.md` true of *every* response — not only the ones a router built
by hand with `APIError`, but an unmatched route, a validation failure, or a genuinely unexpected
exception too — and the router registration.

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
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from aoe2stats_api.errors import APIError, error_response
from aoe2stats_api.routers import cron, health

logger = logging.getLogger("aoe2stats_api")


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

    return app


app = create_app()
