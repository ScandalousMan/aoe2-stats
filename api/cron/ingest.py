"""The Vercel cron entrypoint (T018). `maxDuration: 300` is set for this file in `vercel.json`
(T014c) — the 300 s ceiling `docs/adr/0002-hosting.md` measured.

`api/index.py` (T014c) is the *only* other platform-shaped file in the tree; Vercel's filesystem
routing gives this file precedence over that one's `/api/(.*)` rewrite, so the two never compete
for `/api/cron/ingest` and the request path keeps its own, shorter, limit.

Vercel Cron Jobs invoke a scheduled function with **GET**, attaching `Authorization: Bearer
$CRON_SECRET` itself — the quickstart's manual `curl -X POST` and the phase-2 worker loop use
`POST` instead, so this route accepts both. Deliberately not importing and not imported by
`apps/api/src/aoe2stats_api/routers/cron.py` — the FastAPI route those two callers use instead: an
HTTP hop between the two would put the cycle in whichever one has no extended duration
(ADR-0002). The secret check (`_authorized` below) is duplicated there rather than shared, which
is the price constitution XII's "two thin entrypoints" asks this feature to pay.
"""

from __future__ import annotations

import hmac

from pydantic import SecretStr
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from aoe2stats_api.settings import get_settings
from aoe2stats_ingester.run import run_once


def _authorized(authorization: str | None, secret: SecretStr) -> bool:
    """True only for an exact `Bearer <secret>` match against a non-empty configured secret.

    Kept independent of Settings' `min_length=32` constraint on purpose: this handler must
    refuse an empty secret outright rather than trust that whatever built its `Settings`
    validated it first. Comparison is done on bytes, not `str` — `hmac.compare_digest` raises
    `TypeError` on a non-ASCII `str`, and an `Authorization` header is attacker-controlled
    input.
    """
    secret_value = secret.get_secret_value()
    if not secret_value or authorization is None:
        return False
    expected = f"Bearer {secret_value}".encode()
    provided = authorization.encode()
    return hmac.compare_digest(provided, expected)


async def _ingest(request: Request) -> JSONResponse:
    settings = get_settings()
    authorization = request.headers.get("Authorization")
    if not _authorized(authorization, settings.cron_secret):
        return JSONResponse(
            {
                "error": {
                    "code": "unauthorized",
                    "message": "A valid CRON_SECRET bearer token is required.",
                    "detail": {},
                }
            },
            status_code=401,
        )

    report = await run_once(settings.ingest_run_budget_seconds, trigger="cron")
    return JSONResponse(report.to_dict())


app = Starlette(routes=[Route("/api/cron/ingest", _ingest, methods=["GET", "POST"])])
