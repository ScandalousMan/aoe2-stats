"""`POST /api/cron/ingest` — the local and phase-2-VPS caller of `run_once()`.

`contracts/http-api.md`: "In production Vercel routes `/api/cron/ingest` to `api/cron/ingest.py`,
which holds the 300 s duration the cycle needs; the FastAPI route of the same path is the local
and phase-2-VPS caller. Both are ten lines around `run_once()`. Neither calls the other."

This route exists for the quickstart's local trigger (`curl -X POST localhost:8000/api/cron/ingest
-H "Authorization: Bearer $CRON_SECRET"`) and, unchanged, for the phase-2 worker loop that will
call it over a real network the same way — and for nothing else. It does not import `api/cron/
ingest.py`, and is not imported by it: an HTTP hop between the two would put the cycle in whichever
one has no extended duration (ADR-0002, T018). The two-line secret check below is duplicated there
rather than shared, which is the price constitution XII's "two thin entrypoints" asks this feature
to pay.
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Header

from aoe2stats_api.deps import SettingsDep
from aoe2stats_api.errors import APIError
from aoe2stats_ingester.run import run_once

router = APIRouter(tags=["cron"])


@router.post("/cron/ingest")
async def ingest(
    settings: SettingsDep,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    expected = f"Bearer {settings.cron_secret.get_secret_value()}"
    if authorization is None or not secrets.compare_digest(authorization, expected):
        raise APIError(
            status_code=401,
            code="unauthorized",
            message="A valid CRON_SECRET bearer token is required.",
        )

    report = await run_once(settings.ingest_run_budget_seconds, trigger="local")
    return report.to_dict()
