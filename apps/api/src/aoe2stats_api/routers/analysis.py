"""The analysis router (T368): `GET /api/matches/{game_id}/analysis`.

`contracts/http-api.md`'s "Analysis" section and `contracts/analysis.md`'s "The published
analysis" section are ground truth for this route's one job: serve the already-published analysis
document whole, straight from the object store, beside the names its identifiers resolve to, and
answer `404` in every other state.

**The envelope (T709).** The answer is `{"document": <the stored bytes>, "names": {...}}`. The
stored object carries ids and no names, and it is never modified: its digest is part of the
analysis identity, and a name added to it would change what the identity says it is. So the
`document` value is the stored bytes, spliced into the body as they are and never parsed back out
and re-serialised, and `names` is built beside it from the knowledge snapshot the document's own
`identity.knowledge` names (`aoe2stats_analyzer.names`, never the nearest snapshot, FR-027). An id
that snapshot does not name is `null`.
`apps/api/tests/test_analysis_routes.py` (T367) is this router's own specification.

**This router reads state and never performs analysis work (FR-042, constitution V).** The work
that claims a `match_analyses` row, fetches a recording and runs it through `packages/
replay-engine` is `api/analyze.py` (T366) — a separate Vercel function, not part of `create_app()`
at all (`contracts/http-api.md`: "`POST /api/analyze` ... A separate Vercel function, not the API
app"). Constitution V's isolation ("the API never loads an engine at all") is obtained here simply
by this module never importing anything below `packages/core`'s `ReplayValidator`/`ReplayExtractor`
Protocols: no `packages/replay-engine`, no `apps/analyzer`, and no engine-specific vocabulary at
all. `test_engine_isolation.py`'s subprocess check — importing `aoe2stats_api.app` must never load
`aoe2rec_py` — is what this discipline keeps green.

**`404` in every state but `published`, never a differentiated code per state.** `contracts/
http-api.md`'s own table: "The published analysis (FR-030). `404` in every state but `published`".
A caller asking for an analysis that is `absent`, `queued`, `running`, `failed`, `unavailable` or
`refused` gets the identical `not_found` this codebase already uses for "nothing to serve at this
address" elsewhere (`routers/matches.py`'s `_match_not_found`, `routers/replays.py`'s
`_replay_not_found`) — the seven-state detail a caller actually needs to act on (can this be
(re)requested, until when, why not) lives on the `analysis` summary object `routers/matches.py`
wires into match-detail (T368's other half), not on this route, which only ever answers "here is
the document" or "not yet".

**Session-checked, ownership-free**, the same posture `routers/matches.py`'s `GET /api/matches/
{game_id}` already settled on for a published analysis (data-model.md: "shown to everyone") — every
signed-in caller may read any match's published analysis, so this router carries no
`profile_links`/ownership query at all, only `_require_session`.

**Self-contained**, per this codebase's established convention (`routers/replays.py`'s,
`routers/favourites.py`'s own module docstrings): the session-resolution helpers below are a
duplicate of every other router's, not an import, and the one query this route makes
(`_published_analysis_row`) is its own — `routers/matches.py`'s wider seven-state `analysis` object
needs the identical row but computes its own summary from it independently, since the two routes
answer two different questions from the same table and share no response shape to keep in sync.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, NoReturn

from fastapi import APIRouter, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api import security
from aoe2stats_api.deps import ObjectStoreDep, SessionDep, SettingsDep
from aoe2stats_api.errors import APIError
from aoe2stats_storage.models import MatchAnalysis, MatchAnalysisState
from aoe2stats_storage.models import Session as SessionRow

router = APIRouter(tags=["analysis"])

logger = logging.getLogger("aoe2stats_api")


# --- Session resolution, the same discipline every other router in this feature establishes
# (module docstring) ------------------------------------------------------------------------------


async def _current_session_row(
    request: Request, db_session: AsyncSession, secret: str
) -> SessionRow | None:
    """The caller's active `sessions` row, or `None` for a missing, tampered, expired or revoked
    cookie — mirrors `routers/matches.py`'s own helper of the same name and shape."""
    session_id = security.read_session_id(request.cookies.get(security.SESSION_COOKIE_NAME), secret)
    if session_id is None:
        return None
    return await security.get_active_session(db_session, session_id)


def _require_session(session_row: SessionRow | None) -> SessionRow:
    if session_row is None:
        raise APIError(
            status_code=401,
            code="not_authenticated",
            message="Sign in to view this match's analysis.",
        )
    return session_row


# --- GET /api/matches/{game_id}/analysis ----------------------------------------------------------


def _analysis_not_found() -> APIError:
    """The one answer for "there is nothing to serve at this address yet" — whether `game_id`
    names no match at all, no `match_analyses` row, or a row in any state but `published`
    (module docstring's "404 in every state but published"). Never a differentiated code per
    state: that detail belongs to the `analysis` summary object on match-detail, not here."""
    return APIError(
        status_code=404,
        code="not_found",
        message="No published analysis was found for that match.",
    )


async def _published_analysis_row(
    db_session: AsyncSession, *, game_id: int
) -> MatchAnalysis | None:
    """`match_analyses`'s own primary key is `game_id` alone (data-model.md) — at most one row per
    match, ever, so this is the whole lookup."""
    result = await db_session.execute(select(MatchAnalysis).where(MatchAnalysis.game_id == game_id))
    return result.scalar_one_or_none()


def _unreadable_document(game_id: int, exc: Exception) -> NoReturn:
    """The stored object is not a strict-UTF-8, standard-JSON object. It is spliced into the
    response as it is, so serving it would answer a body no `JSON.parse` accepts: that is a stored
    object gone wrong, answered as one (`500`), not an analysis with its names missing. Logged as a
    defect, with the exception's class and never its text (it can quote the document)."""
    logger.error(
        "stored analysis for game_id=%s is not a readable JSON object: %s",
        game_id,
        type(exc).__name__,
    )
    raise APIError(
        status_code=500,
        code="internal_error",
        message="The stored analysis could not be read.",
    ) from exc


def _refuse_constant(constant: str) -> NoReturn:
    raise ValueError(f"{constant} is not a JSON value")


def _parse_stored_document(document: bytes, game_id: int) -> dict[str, Any]:
    """The stored bytes read strictly: UTF-8 (a byte-order mark fails), standard JSON (`NaN` and
    `Infinity` fail), an object at the top. Read-only: the bytes served are the ones passed in."""
    try:
        parsed = json.loads(document.decode("utf-8"), parse_constant=_refuse_constant)
    except ValueError as exc:  # UnicodeDecodeError and JSONDecodeError are ValueErrors
        _unreadable_document(game_id, exc)
    if not isinstance(parsed, dict):
        _unreadable_document(game_id, TypeError(type(parsed).__name__))
    return parsed


#: What the names table is when not even the ids can be listed: the analyzer's `names` module
#: failed to import. The page then shows every identifier as an identifier.
_NO_NAMES: dict[str, dict[str, str | None]] = {"technology": {}, "unit": {}, "building": {}}


def _names_for_stored_document(document: bytes, game_id: int) -> dict[str, dict[str, str | None]]:
    """The `names` table for `document`; **never raises past an unreadable document (T709).**

    Names are a courtesy beside the document, so nothing in resolving them may take the analysis
    down (FR-048, constitution V's spirit) - the posture `routers/matches.py`'s `_is_stale` takes
    for the same reason. A deployment fault (`FAULT_ERRORS`: an installed snapshot that cannot be
    loaded, whichever one - the unrelated test stub included) and any other error are both logged
    with their traceback, under different messages (an operator reads the first as "fix the
    deployment" and the second as "fix the code"), and answer the same envelope with every
    referenced id mapped to `null`.
    """
    parsed = _parse_stored_document(document, game_id)
    try:
        # Imported here, not at module scope: importing the app must load none of the analyzer
        # (`tests/architecture/test_feature_006_boundaries.py` allows exactly this import from
        # exactly this file). Inside the handler: an import-time failure is part of the
        # computation this function promises not to fail the page on.
        from aoe2stats_analyzer.names import FAULT_ERRORS, names_for_document, unresolved_names

        try:
            return names_for_document(parsed)
        except FAULT_ERRORS:
            logger.exception("names not resolved for game_id=%s: deployment fault", game_id)
        except Exception:
            logger.exception("names not resolved for game_id=%s: unexpected error", game_id)
        return unresolved_names(parsed)
    except Exception:
        logger.exception("names not resolved for game_id=%s: unexpected error", game_id)
        return _NO_NAMES


@router.get("/matches/{game_id}/analysis")
async def get_match_analysis(
    game_id: int,
    request: Request,
    db_session: SessionDep,
    settings: SettingsDep,
    object_store: ObjectStoreDep,
) -> Response:
    """FR-030: the published analysis document, read whole from the object store at `match_
    analyses.result_key` and embedded byte-for-byte in the `{"document", "names"}` envelope
    (module docstring) — never a redirect to a signed URL (`contracts/analysis.md`'s "The
    published document" note: this is this service's own derived JSON, meant for a direct
    `fetch().then(r => r.json())`, unlike a `.aoe2record` download). `404` for every state but
    `published` (module docstring)."""
    secret = settings.app_secret_key.get_secret_value()
    _require_session(await _current_session_row(request, db_session, secret))

    row = await _published_analysis_row(db_session, game_id=game_id)
    if row is None or row.state is not MatchAnalysisState.PUBLISHED or row.result_key is None:
        raise _analysis_not_found()

    document = await object_store.get(row.result_key)
    # Off the event loop (the stored object is parsed and the snapshot tree may be read on the
    # first call). Everything in it is blocking and CPU-bound, none of it awaits.
    names = await asyncio.to_thread(_names_for_stored_document, document, game_id)
    body = b'{"document":' + document + b',"names":' + json.dumps(names).encode("utf-8") + b"}"
    return Response(content=body, media_type="application/json")
