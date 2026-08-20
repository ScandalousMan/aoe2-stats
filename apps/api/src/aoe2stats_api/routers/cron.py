"""`POST /api/cron/ingest` — the local and phase-2-VPS caller of `run_once()`.

`contracts/http-api.md`: "In production Vercel routes `/api/cron/ingest` to `api/cron/ingest.py`,
which holds the 300 s duration the cycle needs; the FastAPI route of the same path is the local
and phase-2-VPS caller. Both are ten lines around `run_once()`. Neither calls the other."

This route exists for the quickstart's local trigger (`curl -X POST localhost:8000/api/cron/ingest
-H "Authorization: Bearer $CRON_SECRET"`) and, unchanged, for the phase-2 worker loop that will
call it over a real network the same way — and for nothing else. Nothing schedules this route, so
it stays `POST`-only; `api/cron/ingest.py` also accepts `GET`, because that is how Vercel Cron
actually invokes a scheduled function. It does not import `api/cron/ingest.py`, and is not
imported by it: an HTTP hop between the two would put the cycle in whichever one has no extended
duration (ADR-0002, T018). The secret check (`_authorized` below) is duplicated there rather than
shared, which is the price constitution XII's "two thin entrypoints" asks this feature to pay.

**T018c — `run_once` is imported inside `ingest()`, not at module scope.** `apps/api` depends on
`apps/ingester` (`apps/api/pyproject.toml`) so this route can call `run_once()` at all, and from
T055 onward `apps/ingester` depends on `packages/replay-engine` for its capture stage — which
means importing `aoe2stats_ingester.run` will eventually pull in `aoe2rec_py`, a PyO3 extension
documented as able to raise `BaseException` panics. A module-scope import here would put that
chain on the path of `import aoe2stats_api.app`, which every cold start of the API function walks
— including the ones that only ever serve `GET /api/health` — contradicting plan.md's
constitution-V row ("The API never loads an engine") and constitution V's "a parser crash affects
neither the API nor the ingester". Deferring the import to the one handler that actually calls
`run_once()` means the engine loads only when this specific route is invoked — which is the local
trigger, deliberately allowed to run a full cycle — and never merely because the app was imported.
The alternative considered was making `apps/ingester`'s stage list build lazily instead (a builder
function rather than a module-level tuple in `run.py`); that would also help, but it would not by
itself stop *this* file from importing `aoe2stats_ingester.run` at module scope, which is enough on
its own to defeat the point — so the fix belongs here, at the one place the API actually reaches
into the ingester.
"""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Header
from pydantic import SecretStr

from aoe2stats_api.deps import SettingsDep
from aoe2stats_api.errors import APIError

router = APIRouter(tags=["cron"])


def _authorized(authorization: str | None, secret: SecretStr) -> bool:
    """True only for an exact `Bearer <secret>` match against a non-empty configured secret.

    Settings enforces `min_length=32` on `cron_secret`, but this check does not lean on that
    alone: a settings object built any other way (a test, a future refactor) must not be able
    to turn an empty secret into an endpoint that accepts a bare "Bearer " prefix. Comparison
    is done on bytes, not `str` — `hmac.compare_digest` raises `TypeError` on a non-ASCII
    `str`, and an `Authorization` header is attacker-controlled input, not a value this code
    gets to assume is ASCII.
    """
    secret_value = secret.get_secret_value()
    if not secret_value or authorization is None:
        return False
    expected = f"Bearer {secret_value}".encode()
    provided = authorization.encode()
    return hmac.compare_digest(provided, expected)


@router.post("/cron/ingest")
async def ingest(
    settings: SettingsDep,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    if not _authorized(authorization, settings.cron_secret):
        raise APIError(
            status_code=401,
            code="unauthorized",
            message="A valid CRON_SECRET bearer token is required.",
        )

    # Imported here, not at module scope — see this module's docstring (T018c).
    from aoe2stats_ingester.run import run_once

    report = await run_once(settings.ingest_run_budget_seconds, trigger="local")
    return report.to_dict()
