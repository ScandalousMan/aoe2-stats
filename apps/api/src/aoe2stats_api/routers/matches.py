"""The matches router (T070): `GET /api/matches` and `GET /api/matches/{game_id}`, per
`contracts/http-api.md`'s Matches table.

Both routes are read-only wrappers around `aoe2stats_storage.repositories.matches.
MatchesRepository` (T069), which already carries the query shape, the cursor discipline and the
"capture status travels intact" rule — see that module's own docstring for the reasoning behind
each. This router's job is narrower: resolve the session, prove ownership, translate the
repository's dataclasses into the JSON shape the contract fixes, and turn every failure into the
single error envelope.

**Civilisation names (T070c).** The repository's dataclasses carry only `civ_id` — Relic's own
`getRecentMatchHistory` never names one (`docs/data-sources.md` §1) — so every row and every
participant below also carries a `*_name` computed here, via `civilisation_name`
(`aoe2stats_api.civilizations`), the same shape `_latest_ratings_by_profile` (`profiles.py`)
already established for `leaderboard_name` (T033a): a hand-maintained id-to-name table for a
measured fact about the game has no business in a front-end component module, per `CLAUDE.md`'s
three-homes rule, so it is computed here and served, never re-derived by the client.
`packages/storage` cannot import from `apps/api` (the dependency runs the other way), which is
why this lookup lives at the router layer exactly like `leaderboard_name` did, rather than on the
repository's own dataclasses.

**Leaderboard names (T070f).** The same reasoning applies to `leaderboard_id`, and the same table
already exists — `aoe2stats_api.leaderboards.leaderboard_name`, the one `profiles.py` already reads
for `GET /api/profiles`. Both routes below carry a `leaderboard_name` alongside `leaderboard_id`
computed with that same helper, so the client reads the identical vocabulary from every route
rather than deriving a third copy of the mapping client-side.

**FR-045 / FR-038 — one error for `list_matches`, indistinguishable causes**, the same discipline
`replays.py`'s and `profiles.py`'s own `_owned_active_link`/`_profile_not_found` pair already
establish, and this module keeps its own copy of rather than importing (`replays.py`'s own module
docstring: "each router in this feature is a self-contained file"). `GET /api/matches?profile_id=`
names one profile explicitly, so ownership is exactly `_owned_active_link`'s existing shape: no
active link for that id, an unlinked one, or one belonging to a different account all answer the
identical `not_found`.

**`GET /api/matches/{game_id}` carries no ownership scope at all (T327, FR-018/FR-021).**
`contracts/http-api.md`'s "Matches, widened" table states it plainly: "Any match this service holds
is readable by any signed-in caller." The route still requires a session — `_require_session`, the
same as every other route in this file — but, unlike `list_matches`, proves nothing about which
profiles the caller controls before answering; `MatchesRepository.get_match_detail` (T327's own
docstring) now returns `None` for exactly one reason, "no such `game_id`", which this router still
turns into one `not_found` carrying a specific, human-meaningful message — never Starlette's bare
"Not Found" a framework-level 404 for the unmatched-route fallback would otherwise coincide with
(`test_match_detail.py`'s own note on why that distinction is asserted explicitly). There is no
`?from_profile_id=` parameter on this route and none may be added: a parameter that could change
the presentation is one that eventually will (FR-021), and `test_match_detail.py`'s own "identical
whichever history it is reached from" assertion is what a per-caller presentation would break.
`_owned_profile_ids` is still called here, but only to resolve FR-022's own archival state — never
to decide whether the caller may see the match at all.

**Capture state travels to the client unmodified.** Per `MatchesRepository`'s own docstring and
T073's note (quoted in `test_capture_visibility.py`), the collapse of `unavailable` / `expired` /
`failed` into the badge's single "lost" state, and of `pending` / `downloading` into "still
catchable", belongs to the design-system component (T073/T074), never to this router. Every row
below carries the raw `CaptureStatus` value verbatim, including all three statuses behind "lost"
and `quarantined`, which FR-026 keeps out of both the archived and the lost columns — both
`match_row_json` and `_match_detail_json` carry the identical `capture_status`/
`capture_deadline_at` pair (T070e, FR-027: per match, not only per list), so the client reads one
vocabulary from either route rather than two.

**Cursor validation.** `MatchesRepository._decode_cursor` raises `ValueError` for any cursor this
repository did not itself issue — malformed, tampered, or built for a different shape — which this
router turns into the same `422`/`validation_error` FastAPI's own query-parameter validation
already answers with for a missing `profile_id`, rather than letting it fall through to the
generic `internal_error` handler.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api import security
from aoe2stats_api.civilizations import civilisation_name
from aoe2stats_api.deps import SessionDep, SettingsDep
from aoe2stats_api.errors import APIError
from aoe2stats_api.leaderboards import leaderboard_name
from aoe2stats_storage.models import ProfileLink
from aoe2stats_storage.models import Session as SessionRow
from aoe2stats_storage.repositories.matches import (
    DEFAULT_PAGE_SIZE,
    MatchDetail,
    MatchesRepository,
    MatchListRow,
    Opponent,
)

router = APIRouter(tags=["matches"])


# --- Session resolution, the same discipline `auth.py`, `privacy.py`, `profiles.py` and
# `replays.py` already establish (module docstring) ----------------------------------------------


async def _current_session_row(
    request: Request, db_session: AsyncSession, secret: str
) -> SessionRow | None:
    """The caller's active `sessions` row, or `None` for a missing, tampered, expired or revoked
    cookie — mirrors `replays.py`'s own helper of the same name and shape."""
    session_id = security.read_session_id(request.cookies.get(security.SESSION_COOKIE_NAME), secret)
    if session_id is None:
        return None
    return await security.get_active_session(db_session, session_id)


def _require_session(session_row: SessionRow | None) -> SessionRow:
    if session_row is None:
        raise APIError(
            status_code=401,
            code="not_authenticated",
            message="Sign in to view your match history.",
        )
    return session_row


def _profile_not_found() -> APIError:
    """FR-045: the one answer for "no such active link", whatever the underlying reason — see the
    module docstring and `profiles.py`'s / `replays.py`'s own `_profile_not_found`."""
    return APIError(
        status_code=404,
        code="not_found",
        message="No linked profile was found for that id.",
    )


def _match_not_found() -> APIError:
    """The one answer `GET /api/matches/{game_id}` gives when `game_id` names no match at all
    (T327: since the ownership scope was removed, `MatchesRepository.get_match_detail` now returns
    `None` for that single reason only — see that method's own docstring). Deliberately specific —
    never the bare "Not Found" Starlette's own unmatched-route fallback answers, so this route's
    own domain `not_found` is distinguishable from a request that never reached a handler at all
    (`test_match_detail.py`'s own note on why that matters)."""
    return APIError(
        status_code=404,
        code="not_found",
        message="No match was found for that id.",
    )


async def _owned_active_link(
    db_session: AsyncSession, *, profile_id: int, user_id: Any
) -> ProfileLink:
    """The caller's own active `profile_links` row for `profile_id`, or the single `not_found`
    error FR-045 requires for every other case (module docstring)."""
    result = await db_session.execute(
        select(ProfileLink).where(
            ProfileLink.profile_id == profile_id, ProfileLink.unlinked_at.is_(None)
        )
    )
    link = result.scalar_one_or_none()
    if link is None or link.user_id != user_id:
        raise _profile_not_found()
    return link


async def _owned_profile_ids(db_session: AsyncSession, *, user_id: Any) -> list[int]:
    """Every profile id the caller has *actively* linked (FR-043: all of them, not only the
    primary). `GET /api/matches/{game_id}` (T327) no longer gates a match's visibility on this
    list — it exists only so `MatchesRepository.get_match_detail` can resolve FR-022's own
    archival state, never a co-participant's."""
    result = await db_session.execute(
        select(ProfileLink.profile_id).where(
            ProfileLink.user_id == user_id, ProfileLink.unlinked_at.is_(None)
        )
    )
    return list(result.scalars().all())


# --- Response shaping --------------------------------------------------------------------------


def _opponent_json(opponent: Opponent) -> dict[str, Any]:
    return {
        "profile_id": opponent.profile_id,
        "alias": opponent.alias,
        "civ_id": opponent.civ_id,
        "civ_name": civilisation_name(opponent.civ_id),
    }


def match_row_json(row: MatchListRow) -> dict[str, Any]:
    """Public (no leading underscore): `routers/players.py`'s `GET /api/players/{profile_id}/
    matches` (T328) imports this directly rather than restating it, so the two routes can never
    drift apart on the one shape `contracts/http-api.md` promises is identical — see
    `test_players_history.py`'s own row-shape-comparison test, the reason this function is
    exported at all."""
    return {
        "game_id": row.game_id,
        "started_at": row.started_at.isoformat() if row.started_at is not None else None,
        "completed_at": row.completed_at.isoformat(),
        "map_name": row.map_name,
        "leaderboard_id": row.leaderboard_id,
        "leaderboard_name": leaderboard_name(row.leaderboard_id),
        "duration_seconds": row.duration_seconds,
        "civilisation": row.civilisation,
        "civilisation_name": civilisation_name(row.civilisation),
        "result": row.result,
        "rating_diff": row.rating_diff,
        "opponents": [_opponent_json(opponent) for opponent in row.opponents],
        # Every raw `CaptureStatus` value, unmodified — the badge's collapse is a front-end
        # concern (module docstring).
        "capture_status": row.capture_status.value if row.capture_status is not None else None,
        "capture_deadline_at": (
            row.capture_deadline_at.isoformat() if row.capture_deadline_at is not None else None
        ),
    }


def _match_detail_json(detail: MatchDetail) -> dict[str, Any]:
    return {
        "game_id": detail.game_id,
        "started_at": detail.started_at.isoformat() if detail.started_at is not None else None,
        "completed_at": detail.completed_at.isoformat(),
        "map_name": detail.map_name,
        "leaderboard_id": detail.leaderboard_id,
        "leaderboard_name": leaderboard_name(detail.leaderboard_id),
        "duration_seconds": detail.duration_seconds,
        # FR-018's "game version" (T327) — `matches.patch` verbatim, never resolved to a name:
        # unlike `civ_id`/`leaderboard_id` there is no id-to-name table for it, so there is nothing
        # to look up here.
        "patch": detail.patch,
        "participants": [
            {
                "profile_id": participant.profile_id,
                "alias": participant.alias,
                "team_id": participant.team_id,
                "civ_id": participant.civ_id,
                "civ_name": civilisation_name(participant.civ_id),
                "color_id": participant.color_id,
                "result": participant.result,
                "rating": participant.rating,
                "rating_diff": participant.rating_diff,
            }
            for participant in detail.participants
        ],
        # T070e: the same two fields `match_row_json` already carries, unmodified — every raw
        # `CaptureStatus` value, the badge's collapse staying a front-end concern (module
        # docstring, "Capture state travels to the client unmodified").
        "capture_status": (
            detail.capture_status.value if detail.capture_status is not None else None
        ),
        "capture_deadline_at": (
            detail.capture_deadline_at.isoformat()
            if detail.capture_deadline_at is not None
            else None
        ),
    }


# --- GET /api/matches ----------------------------------------------------------------------------


@router.get("/matches")
async def list_matches(
    request: Request,
    db_session: SessionDep,
    settings: SettingsDep,
    profile_id: int,
    cursor: str | None = None,
    limit: int = Query(default=DEFAULT_PAGE_SIZE, gt=0),
) -> dict[str, Any]:
    """FR-010 / FR-027: `profile_id`'s matches, newest first, cursor paginated, each row carrying
    its capture status and deadline unmodified (module docstring)."""
    secret = settings.app_secret_key.get_secret_value()
    session_row = _require_session(await _current_session_row(request, db_session, secret))
    await _owned_active_link(db_session, profile_id=profile_id, user_id=session_row.user_id)

    repository = MatchesRepository(db_session)
    try:
        page = await repository.list_matches(profile_id=profile_id, cursor=cursor, limit=limit)
    except ValueError as exc:
        raise APIError(
            status_code=422,
            code="validation_error",
            message="The request could not be validated.",
            detail={"errors": [str(exc)]},
        ) from exc

    return {
        "matches": [match_row_json(row) for row in page.matches],
        "next_cursor": page.next_cursor,
    }


# --- GET /api/matches/{game_id} -------------------------------------------------------------------


@router.get("/matches/{game_id}")
async def get_match_detail(
    game_id: int, request: Request, db_session: SessionDep, settings: SettingsDep
) -> dict[str, Any]:
    """FR-018/FR-021 (T327): every participant of `game_id`, with team, civilisation, result and
    rating change, plus map, ladder, game version, start time and duration — readable by any
    signed-in caller, with no ownership scope at all (module docstring). `owner_profile_ids` is
    still resolved and still passed through, but only so `MatchesRepository.get_match_detail` can
    carry FR-022's own archival state and capture deadline for this match (T070e) when the caller
    played in it — it no longer decides whether `detail` comes back at all."""
    secret = settings.app_secret_key.get_secret_value()
    session_row = _require_session(await _current_session_row(request, db_session, secret))
    owner_profile_ids = await _owned_profile_ids(db_session, user_id=session_row.user_id)

    repository = MatchesRepository(db_session)
    detail = await repository.get_match_detail(game_id=game_id, owner_profile_ids=owner_profile_ids)
    if detail is None:
        raise _match_not_found()

    return _match_detail_json(detail)
