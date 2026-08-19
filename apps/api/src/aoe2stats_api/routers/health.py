"""`GET /api/health` — liveness plus database and object-store reachability.

`contracts/http-api.md`'s Operations table: no authentication, "Liveness plus database and
object-store reachability". A process that answers HTTP at all is already "alive" in the
narrowest sense; what this route actually earns its place by checking is whether the two things
every other route depends on — Postgres, the S3-compatible bucket — are reachable *from this
process, right now*, which a bare 200 with no body would not tell an external monitor.

Each check is cheap on purpose: `SELECT 1` for the database, and a `list_keys` call scoped to a
prefix no real replay object will ever match for the bucket, so this route never pays to list the
archive it is only trying to reach. Either failure answers through the single error envelope
(`errors.py`) rather than the default framework rendering of an unhandled exception, so a caller
of this route gets the same `{"error": {"code", "message", "detail"}}` shape as every other route.
"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from aoe2stats_api.deps import ObjectStoreDep, SessionDep
from aoe2stats_api.errors import APIError

router = APIRouter(tags=["health"])

#: Scoped so the reachability probe never matches a real archived replay (`objects.py`'s
#: `replays/{game_id}/{profile_id}.zip` scheme never produces a key under this prefix).
_HEALTHCHECK_PROBE_PREFIX = "__healthcheck__/"


@router.get("/health")
async def health(session: SessionDep, object_store: ObjectStoreDep) -> dict[str, str]:
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise APIError(
            status_code=503,
            code="database_unavailable",
            message="The database could not be reached.",
        ) from exc

    try:
        await object_store.list_keys(prefix=_HEALTHCHECK_PROBE_PREFIX)
    except Exception as exc:
        raise APIError(
            status_code=503,
            code="object_store_unavailable",
            message="The object store could not be reached.",
        ) from exc

    return {"status": "ok", "database": "ok", "object_store": "ok"}
