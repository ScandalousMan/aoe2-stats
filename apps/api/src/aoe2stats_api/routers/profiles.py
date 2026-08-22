"""The profiles router (T031): `GET /api/profiles`, `POST /api/profiles/{profile_id}/primary`,
`DELETE /api/profiles/{profile_id}`.

**FR-008 — `GET /api/profiles`** returns every profile the caller has *actively* linked
(`profile_links.unlinked_at IS NULL`, `auth.py`'s own discipline for `/api/me`), each carrying its
most recent standing on every leaderboard it has played. "Most recent" is read straight off
`rating_snapshots` — append-only, one row per observation (`ratings.py`) — by grouping on
`(profile_id, leaderboard_id)` and keeping the row whose `captured_at` is the group's maximum,
rather than a second "current rating" column that `RatingsRepository` would then have to keep in
lockstep with the history it already writes. Each entry also carries `leaderboard_name`
(`leaderboards.py`, T033a) — Relic's own `getPersonalStat` never names a ladder, only its id, so
this is the one place that does, and the front end reads the served name rather than
hand-maintaining its own copy.

**FR-043 — exactly one primary, and the others stay reachable.** `POST .../primary` moves the flag
with two `UPDATE`s in sequence rather than one: unset whatever is currently primary for this user,
then set the target — so the partial unique index `ix_profile_links_user_id_primary`
(`unlinked_at IS NULL AND is_primary`, `models.py`) is never asked to hold two rows true for the
same user even for the instant between statements. `GET /api/profiles` already answers the second
half of FR-043 on its own: it lists every active link, primary or not, so a non-primary profile is
never hidden — promoting it is not the only way to see that it exists and is being archived.

**Unlinking the primary link promotes another one.** `is_primary` is otherwise untouched by
`DELETE`, but a user with two links who unlinks the primary one must not end with zero: the partial
unique index enforces *at most* one primary per user, not *exactly* one, and nothing later can
recover from "none" — every new link's own `is_primary` is `not active_links` (`auth.py`), which is
already false once any active link remains. If the unlinked link was primary and another active
link survives, the oldest surviving one (by `linked_at`) is promoted in the same transaction as the
unlink itself, so the two writes commit or roll back together. If none survives there is nothing to
promote to, and `is_primary` is left as-is on the now-inactive row.

**FR-004 — the `DELETE` preview.** Unlinking never deletes a `profile_links` row (data-model.md:
"Set rather than deleted, so capture history stays explicable") and never touches the
`replay_captures` rows a profile already earned — those keep archiving nothing further only
because `unlinked_at` removes the link from the discovery query's `WHERE ... unlinked_at IS NULL`
(data-model.md), not because anything here reaches into `replay_captures` at all. This handler is
called once to preview (no `?confirm=true`) and again to act, both against the same path, matching
the sibling `/api/privacy/erase` pattern `contracts/http-api.md` already documents ("Requires an
explicit confirmation token from a prior `GET`"): the preview call states the consequence — the
archived replays already captured are *retained*, only future automatic capture stops — and leaves
`unlinked_at` untouched; only `?confirm=true` sets it.

**FR-045 — one error, indistinguishable causes.** `_owned_active_link` answers `not_found` (404)
identically whether `profile_id` names no active link at all, an active link somebody unlinked, or
an active link that belongs to a *different* account. Any of those three cases answering
differently — a 403 for "exists but is not yours", say — would itself be the leak: it would tell an
unrelated caller that the profile they guessed at belongs to *someone*, which is exactly the
inference FR-045 forbids making visible. The response body never repeats `profile_id` either, so
the one fact a caller already supplied in the URL is not echoed back dressed up as confirmation of
anything.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import Row, and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api import security
from aoe2stats_api.deps import SessionDep, SettingsDep
from aoe2stats_api.errors import APIError
from aoe2stats_api.leaderboards import leaderboard_name
from aoe2stats_storage.models import (
    AoeProfile,
    CaptureStatus,
    ProfileLink,
    RatingSnapshot,
    ReplayCapture,
)
from aoe2stats_storage.models import Session as SessionRow
from aoe2stats_storage.repositories.ratings import RatingsRepository

router = APIRouter(tags=["profiles"])


# --- Session resolution, the same discipline `auth.py` already establishes -----------------------


async def _current_session_row(
    request: Request, db_session: AsyncSession, secret: str
) -> SessionRow | None:
    """The caller's active `sessions` row, or `None` for a missing, tampered, expired or revoked
    cookie — mirrors `auth.py`'s own helper of the same name and shape."""
    session_id = security.read_session_id(request.cookies.get(security.SESSION_COOKIE_NAME), secret)
    if session_id is None:
        return None
    return await security.get_active_session(db_session, session_id)


def _require_session(session_row: SessionRow | None) -> SessionRow:
    if session_row is None:
        raise APIError(
            status_code=401,
            code="not_authenticated",
            message="Sign in to manage your linked profiles.",
        )
    return session_row


def _profile_not_found() -> APIError:
    """FR-045: the one answer for "no such active link", whatever the underlying reason — see the
    module docstring."""
    return APIError(
        status_code=404,
        code="not_found",
        message="No linked profile was found for that id.",
    )


async def _owned_active_link(
    db_session: AsyncSession, *, profile_id: int, user_id: uuid.UUID
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


# --- GET /api/profiles ------------------------------------------------------------------------


async def _active_links_with_profiles(
    db_session: AsyncSession, user_id: Any
) -> Sequence[Row[tuple[ProfileLink, AoeProfile]]]:
    result = await db_session.execute(
        select(ProfileLink, AoeProfile)
        .join(AoeProfile, ProfileLink.profile_id == AoeProfile.profile_id)
        .where(ProfileLink.user_id == user_id, ProfileLink.unlinked_at.is_(None))
        .order_by(ProfileLink.linked_at)
    )
    return result.all()


async def _latest_ratings_by_profile(
    db_session: AsyncSession, profile_ids: list[int]
) -> dict[int, list[dict[str, Any]]]:
    """The most recent `rating_snapshots` row per `(profile_id, leaderboard_id)` among
    `profile_ids` — one entry per leaderboard the profile has played (FR-008), read from the
    append-only history rather than a separately maintained "current" column (module docstring)."""
    if not profile_ids:
        return {}

    latest = (
        select(
            RatingSnapshot.profile_id,
            RatingSnapshot.leaderboard_id,
            func.max(RatingSnapshot.captured_at).label("captured_at"),
        )
        .where(RatingSnapshot.profile_id.in_(profile_ids))
        .group_by(RatingSnapshot.profile_id, RatingSnapshot.leaderboard_id)
        .subquery()
    )
    result = await db_session.execute(
        select(RatingSnapshot).join(
            latest,
            and_(
                RatingSnapshot.profile_id == latest.c.profile_id,
                RatingSnapshot.leaderboard_id == latest.c.leaderboard_id,
                RatingSnapshot.captured_at == latest.c.captured_at,
            ),
        )
    )

    by_profile: dict[int, list[dict[str, Any]]] = {}
    for snapshot in result.scalars().all():
        by_profile.setdefault(snapshot.profile_id, []).append(
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
        )
    return by_profile


@router.get("/profiles")
async def list_profiles(
    request: Request, db_session: SessionDep, settings: SettingsDep
) -> dict[str, Any]:
    """FR-008: the caller's linked profiles, each with its current rating, rank and win/loss
    record per leaderboard. FR-043's second half: every active link is listed, primary or not —
    the others stay reachable rather than hidden."""
    secret = settings.app_secret_key.get_secret_value()
    session_row = _require_session(await _current_session_row(request, db_session, secret))

    links = await _active_links_with_profiles(db_session, session_row.user_id)
    profile_ids = [profile.profile_id for _link, profile in links]
    ratings_by_profile = await _latest_ratings_by_profile(db_session, profile_ids)

    return {
        "profiles": [
            {
                "profile_id": profile.profile_id,
                "alias": profile.alias,
                "country": profile.country,
                "is_primary": link.is_primary,
                "linked_at": link.linked_at.isoformat(),
                "ratings": ratings_by_profile.get(profile.profile_id, []),
            }
            for link, profile in links
        ]
    }


# --- POST /api/profiles/{profile_id}/primary --------------------------------------------------


@router.post("/profiles/{profile_id}/primary")
async def set_primary_profile(
    profile_id: int, request: Request, db_session: SessionDep, settings: SettingsDep
) -> dict[str, Any]:
    """FR-043: designate `profile_id` as the caller's primary profile. Two sequential `UPDATE`s —
    unset whatever is currently primary, then set the target — so the partial unique index
    enforcing "exactly one primary per user" (module docstring) is never asked to hold two rows
    true at once."""
    secret = settings.app_secret_key.get_secret_value()
    session_row = _require_session(await _current_session_row(request, db_session, secret))
    link = await _owned_active_link(db_session, profile_id=profile_id, user_id=session_row.user_id)

    await db_session.execute(
        update(ProfileLink)
        .where(
            ProfileLink.user_id == session_row.user_id,
            ProfileLink.unlinked_at.is_(None),
            ProfileLink.is_primary.is_(True),
        )
        .values(is_primary=False)
    )
    await db_session.execute(
        update(ProfileLink).where(ProfileLink.id == link.id).values(is_primary=True)
    )

    return {"profile_id": profile_id, "is_primary": True}


# --- DELETE /api/profiles/{profile_id} ----------------------------------------------------------


async def _stored_replay_count(db_session: AsyncSession, profile_id: int) -> int:
    """How many of `profile_id`'s replays are `stored` (the enum value — "archived" is the
    user-facing label for the same state, data-model.md) — what the unlink preview states a
    consequence about."""
    count = await db_session.scalar(
        select(func.count())
        .select_from(ReplayCapture)
        .where(
            ReplayCapture.profile_id == profile_id,
            ReplayCapture.status == CaptureStatus.STORED,
        )
    )
    return int(count or 0)


@router.delete("/profiles/{profile_id}")
async def unlink_profile(
    profile_id: int, request: Request, db_session: SessionDep, settings: SettingsDep
) -> dict[str, Any]:
    """FR-004: preview the consequence for archived replays before the user confirms, then act
    only once `?confirm=true` is present. Unlinking sets `unlinked_at` and never deletes the row
    or touches a single `replay_captures` entry (module docstring)."""
    secret = settings.app_secret_key.get_secret_value()
    session_row = _require_session(await _current_session_row(request, db_session, secret))
    link = await _owned_active_link(db_session, profile_id=profile_id, user_id=session_row.user_id)

    stored_count = await _stored_replay_count(db_session, profile_id)
    archived_replays = {
        "retained": True,
        "count": stored_count,
        "message": (
            "Already-archived replays are kept and remain downloadable. Only future automatic "
            "capture for this profile stops."
        ),
    }

    if request.query_params.get("confirm") != "true":
        return {"confirmed": False, "archived_replays": archived_replays}

    now = datetime.now(UTC)
    await db_session.execute(
        update(ProfileLink).where(ProfileLink.id == link.id).values(unlinked_at=now)
    )

    if link.is_primary:
        # The invariant is "at most one primary", not "exactly one" — but nothing later can
        # recover from zero (module docstring), so promote the oldest surviving active link in
        # the same transaction as the unlink itself.
        oldest_survivor_id = await db_session.scalar(
            select(ProfileLink.id)
            .where(
                ProfileLink.user_id == session_row.user_id,
                ProfileLink.unlinked_at.is_(None),
                ProfileLink.id != link.id,
            )
            .order_by(ProfileLink.linked_at)
            .limit(1)
        )
        if oldest_survivor_id is not None:
            await db_session.execute(
                update(ProfileLink)
                .where(ProfileLink.id == oldest_survivor_id)
                .values(is_primary=True)
            )

    return {
        "confirmed": True,
        "unlinked_at": now.isoformat(),
        "archived_replays": archived_replays,
    }


# --- GET /api/profiles/{profile_id}/ratings -----------------------------------------------------


@router.get("/profiles/{profile_id}/ratings")
async def profile_rating_history(
    profile_id: int, request: Request, db_session: SessionDep, settings: SettingsDep
) -> dict[str, Any]:
    """FR-009: the rating curve from `rating_snapshots` for the caller's own `profile_id`, oldest
    first — the order a chart reads left to right — across every leaderboard it has played.

    Ownership follows the identical `_owned_active_link` / `_profile_not_found` discipline every
    other route in this router already applies (module docstring, FR-045): a `profile_id` naming
    no active link, an unlinked one, or one belonging to a different account all answer the same
    `not_found`, never a differentiated 403 that would itself be the "public directory of players"
    FR-038 forbids (T067). A profile the caller does own but with no snapshots yet — freshly
    linked, before the first discovery cycle — gets an empty list, not an error: the profile is
    real and owned, the history is simply not there yet.
    """
    secret = settings.app_secret_key.get_secret_value()
    session_row = _require_session(await _current_session_row(request, db_session, secret))
    await _owned_active_link(db_session, profile_id=profile_id, user_id=session_row.user_id)

    snapshots = await RatingsRepository(db_session).history_for_profile(profile_id=profile_id)

    return {
        "ratings": [
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
            for snapshot in snapshots
        ]
    }
