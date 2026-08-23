"""`GET /api/health` — liveness plus database and object-store reachability.

`contracts/http-api.md`'s Operations table: no authentication, "Liveness plus database and
object-store reachability". A process that answers HTTP at all is already "alive" in the
narrowest sense; what this route actually earns its place by checking is whether the two things
every other route depends on — Postgres, the S3-compatible bucket — are reachable *from this
process, right now*, which a bare 200 with no body would not tell an external monitor.

Each check is cheap on purpose: `SELECT 1` for the database, one read of `alembic_version`
against the revision this build was compiled with (T394, `aoe2stats_storage.revision`), and a
`list_keys` call scoped to a prefix no real replay object will ever match for the bucket, so this
route never pays to list the archive it is only trying to reach. Every failure answers through
the single error envelope (`errors.py`) rather than the default framework rendering of an
unhandled exception, so a caller of this route gets the same `{"error": {"code", "message",
"detail"}}` shape as every other route.

**T014e.** Three production faults in one evening — two missing environment variables, a
misnamed one, an endpoint carrying a bucket path — each cost a round trip through the deployment
platform's own logs to identify, because `detail` was always `{}` and nothing was logged. This
module now names the *failure class* in both places: in `detail`, for the operator looking at the
response, and in the process log, for the deploy platform's own log viewer. What it never names,
in either place, is a configuration *value*: this route is unauthenticated (`contracts/
http-api.md`), so `S3_ENDPOINT_URL` and `SignatureDoesNotMatch` belong in the response — they are
the key name and the error class, both diagnosis a caller cannot already know — while the
credential, host or connection string that produced them stays out of it, in the response and in
the log alike. `_failure_class` below is the one function allowed to look inside an exception, and
it is deliberately narrow: a `botocore` `ClientError`'s `response["Error"]["Code"]` (e.g.
`SignatureDoesNotMatch`, `NoSuchBucket`) is itself just a class name assigned by S3's own error
taxonomy, never the request that produced it; everything else falls back to the bare Python
exception type name.

**T390 — this route is no longer the only one that answers.** `app.py` now handles
`ConfigurationError` (`settings.py`) for the whole application, so every route reports the same
`configuration_invalid` 503 naming the same keys, and the local key-extraction helper that used
to live here moved to `settings.py` beside the exception. What stays here is the *ordering* below
and only that: without a `Settings` dependency of its own, resolved first, a broken configuration
on this route would surface as whichever of the two probes happened to fail first — most likely
`database_unavailable`, which names the wrong fault for an operator reading it. The paragraph
that follows is why that ordering was needed in the first place, and it still holds.

**Why `Settings` is resolved as its own explicit, first dependency.** `get_session` and
`get_object_store` (`deps.py`) each call `get_settings()` *internally*, as a plain function call,
never as a `Depends()` sub-dependency FastAPI's solver can see — so when `Settings()` itself fails
to build (a required environment variable missing or malformed), the `ValidationError` surfaces
while FastAPI is resolving `session`/`object_store` for the route, before this function's body
ever runs, and reaches only `app.py`'s generic `Exception` handler: a bare `internal_error` with
an empty `detail`, the very first fault of the evening this task exists to close. Declaring
`_settings` as its own dependency, first in the parameter list, puts a `try/except` around exactly
that call, ahead of the other two: FastAPI resolves a path operation's direct dependencies in
signature order, so a `Settings` failure is caught and answered with the missing/invalid key
*names* (`pydantic`'s `loc` is the alias the environment variable is read under, e.g.
`S3_SECRET_ACCESS_KEY` — never the `input` dict `ValidationError.errors()` also carries, which
holds every other field's value, secrets included, and is never touched here) before either probe
below gets a chance to fail on the same missing configuration for a second, less specific reason.

**Why a failing probe does not raise an alert.** `raise_alert` (`packages/core/.../alerting.py`)
writes into a fixed, five-member `AlertKind` enum backed by a Postgres CHECK/enum constraint
(`models.py`) — `rate_limited`, `deadline_breach`, `expired_capture`, `validation_failed`,
`free_tier` — every one of them a *capture-loss* event the nightly severity-1 audit exists to
catch (constitution I). A reachability probe on an unauthenticated, externally-pollable endpoint
is a different kind of fact, and forcing it into that enum would need a schema change this task
does not own. It would also be self-defeating for the database probe specifically: writing an
alert *is* a database write, so the one outage this endpoint would most want to report is the one
in which it cannot. And unlike an ingest run, which fires at most once a day, `/api/health` may be
polled every few seconds by an uptime monitor — one real outage would flood `alerts` with
duplicate rows for a single incident, with nothing here to deduplicate them, which is exactly what
would make the severity-1 audit (T061) stop being a signal. The existing external channels — an
uptime check against this very endpoint, and the cron-liveness check SC-007 already asks for — are
the correct place for "is this reachable", not the ledger that means "a replay is at risk".
"""

from __future__ import annotations

import logging
from typing import Annotated

from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends
from sqlalchemy import text

from aoe2stats_api.deps import ObjectStoreDep, SessionDep
from aoe2stats_api.errors import APIError
from aoe2stats_api.settings import ConfigurationError, Settings, get_settings
from aoe2stats_storage.revision import EXPECTED_SCHEMA_REVISION

logger = logging.getLogger("aoe2stats_api")

router = APIRouter(tags=["health"])

#: Scoped so the reachability probe never matches a real archived replay (`objects.py`'s
#: `replays/{game_id}/{profile_id}.zip` scheme never produces a key under this prefix).
_HEALTHCHECK_PROBE_PREFIX = "__healthcheck__/"


def _failure_class(exc: Exception) -> str:
    """The one fact this route names about *why* a probe failed: its class, never its value.

    A `botocore` `ClientError` carries S3's own error code in `response["Error"]["Code"]` —
    `SignatureDoesNotMatch`, `NoSuchBucket`, `AccessDenied`, `NoSuchKey`... — which is diagnosis
    an operator can act on without a configuration value ever appearing (`ClientError.response`
    also carries an `Error.Message`, which is not read here: S3 error messages sometimes echo
    back the request, e.g. a bucket or key name, and this route draws the line at the *code*).
    Anything else — a connection refused, a DNS failure, a driver-level outage — falls back to
    the bare exception type name, which is exactly what a `SELECT 1` failure gives us.
    """
    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code")
        if code:
            return str(code)
    return type(exc).__name__


async def _resolve_settings() -> Settings:
    """`Settings`, resolved as its own dependency so a build failure is caught here first.

    See the module docstring's "Why `Settings` is resolved..." section for why this exists as a
    separate dependency rather than a plain call inside the route body.
    """
    try:
        return get_settings()
    except ConfigurationError as exc:
        logger.error(
            "Settings failed to build for /api/health: missing or invalid keys %s", exc.keys
        )
        raise APIError(
            status_code=503,
            code="configuration_invalid",
            message="The application configuration is invalid.",
            detail={"missing_or_invalid_keys": exc.keys},
        ) from exc


_SettingsProbeDep = Annotated[Settings, Depends(_resolve_settings)]


@router.get("/health")
async def health(
    _settings: _SettingsProbeDep, session: SessionDep, object_store: ObjectStoreDep
) -> dict[str, str]:
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        failure_class = _failure_class(exc)
        logger.exception("Database health probe failed: %s", failure_class)
        raise APIError(
            status_code=503,
            code="database_unavailable",
            message="The database could not be reached.",
            detail={"error_class": failure_class},
        ) from exc

    # T394: reachable is not the same as correct. `SELECT 1` above succeeds against a database
    # whose schema is several migrations behind the code querying it — which is precisely the
    # 2026-08-23 outage, where `1f9879367c9d` was merged and never applied: this route answered
    # `ok`, and every signed-in `GET /api/me` answered 500 on `aoe_profiles.alias_observed_at`.
    #
    # `to_regclass` rather than querying `alembic_version` and catching the failure: a statement
    # that raises inside a transaction poisons it for everything after, and this route's session
    # is `get_session`'s real request-scoped one. Asking whether the relation exists is a question
    # Postgres answers with NULL instead of an error.
    #
    # Its own code, not `database_unavailable`: those two call for different actions from whoever
    # reads them — one is "the database is down", the other is "run the migration" — and folding
    # them together would send an operator to Neon's status page for a deploy step nobody ran.
    # Both revisions are named in `detail`: an Alembic revision is an identifier of a file in this
    # repository, never a credential or a value (constitution VIII).
    relation = (
        (await session.execute(text("SELECT to_regclass('public.alembic_version')")))
        .scalars()
        .first()
    )
    found = (
        (await session.execute(text("SELECT version_num FROM alembic_version"))).scalars().first()
        if relation is not None
        else None
    )
    if found != EXPECTED_SCHEMA_REVISION:
        logger.error(
            "Schema revision mismatch: this build expects %s, the database is at %s",
            EXPECTED_SCHEMA_REVISION,
            found,
        )
        raise APIError(
            status_code=503,
            code="schema_out_of_date",
            message="The database schema does not match this build.",
            detail={"expected": EXPECTED_SCHEMA_REVISION, "found": found},
        )

    try:
        await object_store.list_keys(prefix=_HEALTHCHECK_PROBE_PREFIX)
    except Exception as exc:
        failure_class = _failure_class(exc)
        logger.exception("Object store health probe failed: %s", failure_class)
        raise APIError(
            status_code=503,
            code="object_store_unavailable",
            message="The object store could not be reached.",
            detail={"error_class": failure_class},
        ) from exc

    return {
        "status": "ok",
        "database": "ok",
        "object_store": "ok",
        "schema_revision": EXPECTED_SCHEMA_REVISION,
    }
