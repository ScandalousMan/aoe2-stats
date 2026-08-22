"""The replays router (T062): `GET /api/replays/status?profile_id=`.

`contracts/http-api.md`: "Counts per status, oldest pending, nearest deadline" — a dashboard-level
summary of one profile's capture backlog, distinct from the per-match archival state `GET
/api/matches` will carry per row (FR-027, T065's own note that this endpoint is the one exception
in US3 that reaches back into US2).

**Ownership follows `profiles.py`'s `_owned_active_link` convention, adapted to a query parameter.**
`profile_id` here names the profile whose backlog is being read rather than the one being mutated,
but FR-045's "one error, indistinguishable causes" applies just the same: a `profile_id` that names
no active link, an unlinked one, or one belonging to someone else all answer the identical 404 —
see `profiles.py`'s module docstring for why a differentiated answer would itself be the leak.
This module keeps its own copy of the session-resolution helpers rather than importing
`profiles.py`'s, matching `auth.py`'s, `privacy.py`'s and `profiles.py`'s own precedent: each
router in this feature is a self-contained file (`app.py`'s docstring — "never a change to this
module's structure").

**`oldest_pending` and `nearest_deadline` are both scoped to `status = 'pending'`.** `pending` is
the only status still racing the clock: `downloading` is a claim held for the duration of a single
run (data-model.md), and `stored`, `unavailable`, `expired`, `quarantined` and `failed` are all
terminal — read the state table's "Retried?" column. Ordering by `capture_deadline_at ASC` among
`pending` rows is exactly the claiming query's own `ORDER BY` (data-model.md: "the single most
consequential line in the schema"), so `nearest_deadline` names the row a run would claim first
under a backlog. `oldest_pending` orders by `first_seen_at ASC` instead — how long a capture has
sat undiscovered-but-known — which is a different question from "how soon does it expire" and is
not always the same row: a backfilled older match can be *discovered* later than a fresh one while
still carrying an earlier `capture_deadline_at`, or vice versa.

**Counts cover every `CaptureStatus` value, zero-filled.** A profile with, say, no `quarantined`
captures still gets `"quarantined": 0` rather than an absent key, so a client can read every field
without first checking it exists — the same reasoning `_status_counts` below applies is why
`profiles.py`'s rating list is built from a `dict.get(..., [])` rather than requiring the caller to
handle a missing leaderboard entry.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api import security
from aoe2stats_api.deps import SessionDep, SettingsDep
from aoe2stats_api.errors import APIError
from aoe2stats_storage.models import CaptureStatus, ProfileLink, ReplayCapture
from aoe2stats_storage.models import Session as SessionRow

router = APIRouter(tags=["replays"])


# --- Session resolution, the same discipline `auth.py`, `privacy.py` and `profiles.py` already
# establish (module docstring) -------------------------------------------------------------------


async def _current_session_row(
    request: Request, db_session: AsyncSession, secret: str
) -> SessionRow | None:
    """The caller's active `sessions` row, or `None` for a missing, tampered, expired or revoked
    cookie — mirrors `profiles.py`'s own helper of the same name and shape."""
    session_id = security.read_session_id(request.cookies.get(security.SESSION_COOKIE_NAME), secret)
    if session_id is None:
        return None
    return await security.get_active_session(db_session, session_id)


def _require_session(session_row: SessionRow | None) -> SessionRow:
    if session_row is None:
        raise APIError(
            status_code=401,
            code="not_authenticated",
            message="Sign in to view your replay capture status.",
        )
    return session_row


def _profile_not_found() -> APIError:
    """FR-045: the one answer for "no such active link", whatever the underlying reason — see the
    module docstring and `profiles.py`'s own `_profile_not_found`."""
    return APIError(
        status_code=404,
        code="not_found",
        message="No linked profile was found for that id.",
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


# --- GET /api/replays/status ----------------------------------------------------------------------


async def _status_counts(db_session: AsyncSession, profile_id: int) -> dict[str, int]:
    """Every `CaptureStatus` value, zero-filled (module docstring), for `profile_id`."""
    result = await db_session.execute(
        select(ReplayCapture.status, func.count())
        .where(ReplayCapture.profile_id == profile_id)
        .group_by(ReplayCapture.status)
    )
    counts = {status.value: 0 for status in CaptureStatus}
    for status, count in result.all():
        counts[status.value] = int(count)
    return counts


async def _oldest_pending(db_session: AsyncSession, profile_id: int) -> ReplayCapture | None:
    """The `pending` capture that has sat undiscovered-but-known longest, or `None` if there is
    none (module docstring)."""
    result = await db_session.execute(
        select(ReplayCapture)
        .where(
            ReplayCapture.profile_id == profile_id,
            ReplayCapture.status == CaptureStatus.PENDING,
        )
        .order_by(ReplayCapture.first_seen_at.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _nearest_deadline(db_session: AsyncSession, profile_id: int) -> ReplayCapture | None:
    """The `pending` capture the claiming query would fetch first under a backlog — the same
    `ORDER BY capture_deadline_at ASC` data-model.md fixes for that query (module docstring)."""
    result = await db_session.execute(
        select(ReplayCapture)
        .where(
            ReplayCapture.profile_id == profile_id,
            ReplayCapture.status == CaptureStatus.PENDING,
        )
        .order_by(ReplayCapture.capture_deadline_at.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _capture_summary(capture: ReplayCapture, *, with_first_seen_at: bool) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "game_id": capture.game_id,
        "capture_deadline_at": capture.capture_deadline_at.isoformat(),
    }
    if with_first_seen_at:
        summary["first_seen_at"] = capture.first_seen_at.isoformat()
    return summary


@router.get("/replays/status")
async def replay_status(
    profile_id: int, request: Request, db_session: SessionDep, settings: SettingsDep
) -> dict[str, Any]:
    """FR-027 / SC-010 support, at the profile level: counts per capture status, the oldest still
    pending, and the nearest deadline among those still pending (module docstring)."""
    secret = settings.app_secret_key.get_secret_value()
    session_row = _require_session(await _current_session_row(request, db_session, secret))
    await _owned_active_link(db_session, profile_id=profile_id, user_id=session_row.user_id)

    counts = await _status_counts(db_session, profile_id)
    oldest_pending = await _oldest_pending(db_session, profile_id)
    nearest_deadline = await _nearest_deadline(db_session, profile_id)

    return {
        "counts": counts,
        "oldest_pending": (
            _capture_summary(oldest_pending, with_first_seen_at=True)
            if oldest_pending is not None
            else None
        ),
        "nearest_deadline": (
            _capture_summary(nearest_deadline, with_first_seen_at=False)
            if nearest_deadline is not None
            else None
        ),
    }
