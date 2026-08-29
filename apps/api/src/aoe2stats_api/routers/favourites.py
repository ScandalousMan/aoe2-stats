"""The favourites router (T346): `GET /api/favourites`, `PUT /api/favourites/{profile_id}`,
`DELETE /api/favourites/{profile_id}`. `contracts/http-api.md`'s "Favourites" section,
`data-model.md`'s `favourites` section and `apps/api/tests/test_favourites.py` (T344) are ground
truth for every shape below.

**Idempotence is the composite primary key, not application logic** (FR-013, data-model.md):
`PUT` upserts through `ON CONFLICT DO NOTHING`, the same device `routers/auth.py` uses for
`steam_identities` and `profile_links` — marking the same profile twice inserts the same
`(user_id, profile_id)` pair twice, which the primary key turns into a no-op rather than a second
row or a conflict error. `DELETE` is a plain `DELETE ... WHERE`, which is idempotent by
construction: deleting a row that is already gone still matches zero rows and still answers `200`.

**FR-016's bound is checked before the insert, inside the same request** — a row count against
`favourites` for the caller, refused with `favourites_limit_reached` at `settings.
favourites_max_per_user` before a `PUT` for a *new* profile is attempted. A `PUT` that repeats an
already-favourited profile never reaches the count at all, so marking the same player twice never
trips the bound it would otherwise sit exactly on.

**FR-014: the list carries current standing, not just identity.** `_favourite_ratings` mirrors
`routers/players.py`'s own `_profile_ratings` byte for byte — the latest `rating_snapshots` row per
leaderboard a profile has played — duplicated rather than imported: this router follows the same
"self-contained file over a four-line cross-router import" convention `routers/players.py`'s own
module docstring states for its session-resolution helpers, and a private, underscore-prefixed
helper in another router is not a shape either module commits to keeping stable for the other.

**FR-015, and the one test in this file with no route to exercise.** There is no query anywhere in
this module that counts or groups `favourites` by `profile_id` — "how many people follow this
player" is a question this system must not be able to answer, because answering it would reveal to
a player that they are being followed. `_favourite_row_count` below aggregates over `user_id`
only, never `profile_id`, and `test_favourites_router_never_aggregates_over_profile_id`
(`test_favourites.py`) parses this module's own source to hold that absence in place.

**Session resolution answers `sign_in_required`, not `not_authenticated`.** `contracts/
http-api.md`: "An unauthenticated call answers `401` with `code: 'sign_in_required'`" — the code
this route's own `_require_session` raises differs from `routers/players.py`'s identically-shaped
helper on purpose, because the two contracts name two different codes for the same 401.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api import security
from aoe2stats_api.deps import SessionDep, SettingsDep
from aoe2stats_api.errors import APIError
from aoe2stats_api.leaderboards import leaderboard_name
from aoe2stats_storage.models import AoeProfile, Favourite
from aoe2stats_storage.models import Session as SessionRow
from aoe2stats_storage.repositories.ratings import RatingsRepository

router = APIRouter(tags=["favourites"])


# --- Session resolution, duplicated from `routers/players.py` per this module's own convention ---


async def _current_session_row(
    request: Request, db_session: AsyncSession, secret: str
) -> SessionRow | None:
    session_id = security.read_session_id(request.cookies.get(security.SESSION_COOKIE_NAME), secret)
    if session_id is None:
        return None
    return await security.get_active_session(db_session, session_id)


def _require_session(session_row: SessionRow | None) -> SessionRow:
    if session_row is None:
        raise APIError(
            status_code=401,
            code="sign_in_required",
            message="Sign in to manage your favourites.",
        )
    return session_row


def _profile_not_found() -> APIError:
    return APIError(
        status_code=404,
        code="not_found",
        message="This player has never been observed by this service.",
    )


async def _favourite_ratings(db_session: AsyncSession, profile_id: int) -> list[dict[str, Any]]:
    """The latest `rating_snapshots` row per leaderboard `profile_id` has played — the identical
    shape and derivation `routers/players.py`'s `_profile_ratings` returns for
    `GET /api/players/{profile_id}` (FR-014's "current standing"), reused here rather than
    restated as a second, drifting definition of the same fact.
    """
    snapshots = await RatingsRepository(db_session).history_for_profile(profile_id=profile_id)
    latest_by_leaderboard: dict[int, Any] = {}
    for snapshot in snapshots:
        latest_by_leaderboard[snapshot.leaderboard_id] = snapshot
    return [
        {
            "leaderboard_id": snapshot.leaderboard_id,
            "leaderboard_name": leaderboard_name(snapshot.leaderboard_id),
            "rating": snapshot.rating,
            "rank": snapshot.rank,
            "wins": snapshot.wins,
            "losses": snapshot.losses,
            "streak": snapshot.streak,
            "highest_rating": snapshot.highest_rating,
            "captured_at": snapshot.captured_at.isoformat(),
        }
        for snapshot in latest_by_leaderboard.values()
    ]


async def _favourite_row_count(db_session: AsyncSession, *, user_id: Any) -> int:
    """FR-016's bound check. Aggregates over `user_id` only — never `profile_id` — per this
    module's own docstring and `test_favourites_router_never_aggregates_over_profile_id`."""
    result = await db_session.scalar(
        select(func.count()).select_from(Favourite).where(Favourite.user_id == user_id)
    )
    return result or 0


# --- GET /api/favourites — FR-014, FR-015 --------------------------------------------------------


@router.get("/favourites")
async def list_favourites(
    request: Request, db_session: SessionDep, settings: SettingsDep
) -> dict[str, Any]:
    """FR-014: every entry the caller themselves marked — never another user's (FR-015) — with
    its current standing and its `profile_id`, sufficient for the client to reach
    `/api/players/{profile_id}` with no second lookup."""
    secret = settings.app_secret_key.get_secret_value()
    session_row = _require_session(await _current_session_row(request, db_session, secret))

    rows = (
        await db_session.scalars(
            select(Favourite)
            .where(Favourite.user_id == session_row.user_id)
            .order_by(Favourite.created_at)
        )
    ).all()

    entries: list[dict[str, Any]] = []
    for row in rows:
        profile = await db_session.get(AoeProfile, row.profile_id)
        entries.append(
            {
                "profile_id": row.profile_id,
                "alias": profile.alias if profile is not None else None,
                "country": profile.country if profile is not None else None,
                "ratings": await _favourite_ratings(db_session, row.profile_id),
            }
        )

    return {"favourites": entries}


# --- PUT /api/favourites/{profile_id} — FR-013, FR-016 -------------------------------------------


@router.put("/favourites/{profile_id}")
async def add_favourite(
    profile_id: int, request: Request, db_session: SessionDep, settings: SettingsDep
) -> dict[str, Any]:
    """FR-013: idempotent — marking the same profile twice is one row and two `200`s. FR-016: a
    *new* favourite past `settings.favourites_max_per_user` is refused with
    `favourites_limit_reached`; repeating an existing one never reaches that check."""
    secret = settings.app_secret_key.get_secret_value()
    session_row = _require_session(await _current_session_row(request, db_session, secret))

    profile = await db_session.get(AoeProfile, profile_id)
    if profile is None:
        raise _profile_not_found()

    already_favourited = await db_session.scalar(
        select(Favourite).where(
            Favourite.user_id == session_row.user_id, Favourite.profile_id == profile_id
        )
    )
    if already_favourited is None:
        row_count = await _favourite_row_count(db_session, user_id=session_row.user_id)
        if row_count >= settings.favourites_max_per_user:
            raise APIError(
                status_code=409,
                code="favourites_limit_reached",
                message="You have reached the maximum number of favourites.",
            )

        insert_favourite = (
            pg_insert(Favourite)
            .values(
                user_id=session_row.user_id,
                profile_id=profile_id,
                created_at=datetime.now(UTC),
            )
            .on_conflict_do_nothing()
        )
        await db_session.execute(insert_favourite)

    return {"profile_id": profile_id, "favourited": True}


# --- DELETE /api/favourites/{profile_id} — FR-013 -------------------------------------------------


@router.delete("/favourites/{profile_id}")
async def remove_favourite(
    profile_id: int, request: Request, db_session: SessionDep, settings: SettingsDep
) -> dict[str, Any]:
    """FR-013: idempotent — unmarking an already-unmarked profile still answers `200`, since a
    `DELETE ... WHERE` that matches zero rows is not an error."""
    secret = settings.app_secret_key.get_secret_value()
    session_row = _require_session(await _current_session_row(request, db_session, secret))

    await db_session.execute(
        delete(Favourite).where(
            Favourite.user_id == session_row.user_id, Favourite.profile_id == profile_id
        )
    )

    return {"profile_id": profile_id, "favourited": False}
