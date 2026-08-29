"""The analysis router (T368): `GET /api/matches/{game_id}/analysis`.

`contracts/http-api.md`'s "Analysis" section and `contracts/analysis.md`'s "The published
analysis" section are ground truth for this route's one job: serve the already-published analysis
document whole, straight from the object store, and answer `404` in every other state.
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

from fastapi import APIRouter, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api import security
from aoe2stats_api.deps import ObjectStoreDep, SessionDep, SettingsDep
from aoe2stats_api.errors import APIError
from aoe2stats_storage.models import MatchAnalysis, MatchAnalysisState
from aoe2stats_storage.models import Session as SessionRow

router = APIRouter(tags=["analysis"])


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


@router.get("/matches/{game_id}/analysis")
async def get_match_analysis(
    game_id: int,
    request: Request,
    db_session: SessionDep,
    settings: SettingsDep,
    object_store: ObjectStoreDep,
) -> Response:
    """FR-030: the published analysis document, read whole from the object store at `match_
    analyses.result_key` and served verbatim — never a redirect to a signed URL (`contracts/
    analysis.md`'s "The published document" note: this is this service's own derived JSON, meant
    for a direct `fetch().then(r => r.json())`, unlike a `.aoe2record` download). `404` for every
    state but `published` (module docstring)."""
    secret = settings.app_secret_key.get_secret_value()
    _require_session(await _current_session_row(request, db_session, secret))

    row = await _published_analysis_row(db_session, game_id=game_id)
    if row is None or row.state is not MatchAnalysisState.PUBLISHED or row.result_key is None:
        raise _analysis_not_found()

    document = await object_store.get(row.result_key)
    return Response(content=document, media_type="application/json")
