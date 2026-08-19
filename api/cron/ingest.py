"""The Vercel cron entrypoint (T018). `maxDuration: 300` is set for this file in `vercel.json`
(T014c) — the 300 s ceiling `docs/adr/0002-hosting.md` measured.

`api/index.py` (T014c) is the *only* other platform-shaped file in the tree; Vercel's filesystem
routing gives this file precedence over that one's `/api/(.*)` rewrite, so the two never compete
for `/api/cron/ingest` and the request path keeps its own, shorter, limit.

Ten lines around `run_once()`, deliberately not importing and not imported by
`apps/api/src/aoe2stats_api/routers/cron.py` — the FastAPI route the quickstart's local trigger
and the phase-2 worker call instead: an HTTP hop between the two would put the cycle in whichever
one has no extended duration (ADR-0002). The two-line secret check below is duplicated there
rather than shared, which is the price constitution XII's "two thin entrypoints" asks this feature
to pay.
"""

from __future__ import annotations

import secrets

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from aoe2stats_api.settings import get_settings
from aoe2stats_ingester.run import run_once


async def _ingest(request: Request) -> JSONResponse:
    settings = get_settings()
    expected = f"Bearer {settings.cron_secret.get_secret_value()}"
    authorization = request.headers.get("Authorization")
    if authorization is None or not secrets.compare_digest(authorization, expected):
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


app = Starlette(routes=[Route("/api/cron/ingest", _ingest, methods=["POST"])])
