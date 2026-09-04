"""The Vercel on-demand analysis entrypoint (T366). `maxDuration: 300` is set for this file in
`vercel.json` — the platform's per-execution budget `docs/adr/0002-hosting.md` measured, and the
exact number `apps/analyzer/src/aoe2stats_analyzer/run.py::run_once` threads into its own claim as
`lease_seconds` (that module's own docstring: "the same number `api/analyze.py`'s `maxDuration`
will carry").

`api/index.py` is capped at `maxDuration: 10` (`vercel.json`); a serverless function cannot keep
working after its response is returned, so the request that asks for the analysis has to be the
request that performs it (`contracts/http-api.md`, R6). `POST /api/analyze` is therefore resolved
by the filesystem before `api/index.py`'s own `/api/(.*)` rewrite, exactly as `api/cron/ingest.py`
already is — `scripts/checks/spa-routing.mjs` asserts the ordering for both rather than assuming it.

**Not a cron endpoint, and must never become one.** It carries no `CRON_SECRET`: it authenticates
the same session cookie every other route in this codebase does (`security.read_session_id`/
`get_active_session`, mirroring `routers/analysis.py`'s own `_current_session_row`/
`_require_session`), and it adds no entry to `vercel.json`'s `crons` array — the number of
scheduled jobs after this feature is exactly the number before it (SC-010, FR-044). Every call here
is a person, on one match, asking once.

**FR-040's per-user daily limit is enforced here**, against the real `analysis_request` bucket
(`aoe2stats_api.ratelimit.check_and_increment`, `ANALYSIS_MAX_REQUESTS_PER_USER_PER_DAY`) —
`apps/api/tests/test_analysis_routes.py`'s own module docstring names this file, not
`routers/analysis.py`, as where that half of FR-040 lives, since the router only ever reads state
(constitution V, that router's own docstring).

**FR-039/FR-047's three admission gates (R7) are applied here too, before `run_once` is ever
called.** `apps/analyzer/src/aoe2stats_analyzer/admission.py::check_admission` and
`apps/analyzer/src/aoe2stats_analyzer/run.py` both say, in their own words, that `run_once` "holds
no admission gate of its own ... a later caller applies it before ever reaching here" — this file
is that later caller, and the only one on the analysis path. Skipping this would leave constitution
I's tie-break (capture outranks analysis) and FR-047's retention cap unenforced anywhere in the
product, not merely untested. A blocked gate returns the refusal directly, carrying
`AdmissionOutcome.code` — `capture_deadline_contention`, `analysis_budget_exhausted` or
`analysis_cap_reached` — and never reaches `run_once` at all, so it never claims a row, never
fetches and never retains anything (R7's own three directions: the window, the source's patience,
the allowance).

**Thin by construction.** Every collaborator `run_once` needs — session factory, the real
`AoemsReplayProvider`, the real `Aoe2RecExtractor`, the object store — is composed once, from
`Settings` alone, by `aoe2stats_api.analyze_stages.build_analyze_dependencies`
(`apps/api/src/aoe2stats_api/analyze_stages.py`), mirroring the way both cron entrypoints call
`aoe2stats_api.ingest_stages.build_ingest_stages(settings)` and pass the result straight through.
The actual work — claiming the row, fetching or reusing the recording, parsing it, publishing or
recording why it failed — lives entirely inside `run_once`, in this one process, the same way
`api/cron/ingest.py` keeps every bit of ingestion's own work inside its own `run_once`.

**The response is the same `analysis` summary object `GET /api/matches/{game_id}` returns**
(`contracts/http-api.md`: "Its response is the same `analysis` object above") — `apps/web/src/
features/analysis/api.ts::requestAnalysis` validates the response against that exact shape. Built
by reusing `routers/matches.py`'s own `_analysis_row`/`_analysis_json` (T368) rather than a second
copy of the seven-state derivation, since a stale copy of that logic is exactly the drift `stale`
itself (FR-041) exists to catch, not invite.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from aoe2stats_analyzer.admission import check_admission
from aoe2stats_analyzer.run import run_once
from aoe2stats_api import ratelimit, security
from aoe2stats_api.analyze_stages import build_analyze_dependencies
from aoe2stats_api.errors import error_response
from aoe2stats_api.routers.matches import _analysis_json, _analysis_row
from aoe2stats_api.settings import get_settings
from aoe2stats_storage.repositories.base import session_scope

#: `AdmissionOutcome.code` (`admission.py`) -> the message this route answers with, carrying the
#: code itself unchanged in the envelope's own `code` field (R7: the three gates fail in three
#: different directions, and a caller needs to tell them apart, not just see "refused").
_ADMISSION_REFUSAL_MESSAGES = {
    "capture_deadline_contention": (
        "Analysis is paused while replay capture has unstored recordings inside their deadline "
        "window. Try again shortly."
    ),
    "analysis_budget_exhausted": (
        "Analysis has used its daily allowance of requests to the replay source. Try again later."
    ),
    "analysis_cap_reached": (
        "The retained-recording storage cap has been reached. This match may be analysed again "
        "later."
    ),
}

#: FR-040's own bucket (`data-model.md`'s `rate_limit_counters` section) and a real calendar day —
#: `apps/api/tests/test_analysis_routes.py::test_analysis_request_bucket_enforces_the_configured_
#: daily_cap` proves `ratelimit.check_and_increment` itself against these two exact values.
_RATE_LIMIT_BUCKET = "analysis_request"
_RATE_LIMIT_WINDOW_SECONDS = 24 * 60 * 60


def _unauthorized() -> JSONResponse:
    return error_response(
        status_code=401,
        code="not_authenticated",
        message="Sign in to request this match's analysis.",
    )


def _rate_limited(retry_after: int | None) -> JSONResponse:
    return error_response(
        status_code=429,
        code="rate_limited",
        message="The daily analysis request limit was reached.",
        detail={"retry_after": retry_after} if retry_after is not None else None,
    )


def _not_found() -> JSONResponse:
    return error_response(
        status_code=404,
        code="not_found",
        message="No such match.",
    )


def _invalid_body() -> JSONResponse:
    return error_response(
        status_code=400,
        code="invalid_request",
        message='Body must be {"game_id": <int>}.',
    )


def _admission_refused(code: str | None) -> JSONResponse:
    """`409`, matching this codebase's existing convention for a well-formed, authenticated
    request blocked by a system-wide bound rather than a per-caller rate — `PUT /api/favourites/
    {profile_id}`'s own `favourites_limit_reached` (`contracts/http-api.md`, FR-016) is the
    precedent: `429`/`rate_limited` means "you personally are calling too often", which is not
    what any of R7's three gates mean."""
    return error_response(
        status_code=409,
        code=code or "analysis_refused",
        message=_ADMISSION_REFUSAL_MESSAGES.get(
            code or "", "This match cannot be analysed right now."
        ),
    )


async def _analyze(request: Request) -> JSONResponse:
    settings = get_settings()

    # No cookie at all needs no database round trip to refuse — mirrors `routers/analysis.py`'s
    # own `_current_session_row` short-circuiting the identical way.
    secret = settings.app_secret_key.get_secret_value()
    session_id = security.read_session_id(request.cookies.get(security.SESSION_COOKIE_NAME), secret)
    if session_id is None:
        return _unauthorized()

    deps = build_analyze_dependencies(settings)

    async with session_scope(deps.session_factory) as session:
        session_row = await security.get_active_session(session, session_id)
        if session_row is None:
            return _unauthorized()

        outcome = await ratelimit.check_and_increment(
            session,
            user_id=session_row.user_id,
            bucket=_RATE_LIMIT_BUCKET,
            limit=settings.analysis_max_requests_per_user_per_day,
            window_seconds=_RATE_LIMIT_WINDOW_SECONDS,
        )
        if not outcome.allowed:
            return _rate_limited(outcome.retry_after)

        # R7/FR-039/FR-047: the three admission gates, applied before `run_once` is ever called
        # (module docstring). A blocked gate returns here, straight from the code
        # `check_admission` reports — `run_once` is never reached, so no row is claimed, nothing
        # is fetched and nothing is retained.
        admission = await check_admission(
            session,
            now=datetime.now(UTC),
            max_source_requests_per_day=settings.analysis_max_source_requests_per_day,
            retention_cap_bytes=settings.analysis_retention_cap_bytes,
        )
        if not admission.allowed:
            return _admission_refused(admission.code)

        requested_by_user_id = session_row.user_id

    try:
        body: Any = await request.json()
        game_id = int(body["game_id"])
    except (ValueError, KeyError, TypeError):
        return _invalid_body()

    try:
        await run_once(
            game_id,
            settings.analysis_run_budget_seconds,
            requested_by_user_id,
            session_factory=deps.session_factory,
            replay_provider=deps.replay_provider,
            extractor=deps.extractor,
            object_store=deps.object_store,
            capture_budget_days=settings.capture_budget_days,
        )
    except LookupError:
        return _not_found()

    async with deps.session_factory() as session:
        row = await _analysis_row(session, game_id=game_id)

    return JSONResponse(_analysis_json(game_id=game_id, row=row))


app = Starlette(routes=[Route("/api/analyze", _analyze, methods=["POST"])])
