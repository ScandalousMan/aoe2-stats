"""The privacy router (T032, renamed by T405): `POST /api/privacy/archival-objection`.

Constitution IX 4.0.0 retired the opt-in consent gate: archival now rests on legitimate interest
(GDPR Art. 6-1-f), not consent, and is **on by default** for every linked profile — including one
that has never answered any question at all. What a user can still do is exercise the Art. 21 right
to object, which is what this route now records: `users.archival_objected_at`
(`packages/storage/.../models.py`, `data-model.md`) is a single nullable timestamp, null meaning
"archiving" and set meaning "objected, as of this moment". There is no longer a second, independent
fact to keep alongside it — the old two-timestamp pair (`ingest_consent_at`,
`ingest_consent_withdrawn_at`) recorded "never asked" apart from "asked and declined", a distinction
that only had legal weight under the retired opt-in gate. Under legitimate interest there is nothing
to have been asked, so that distinction is gone, and this module no longer reasons about it.

**Consent is separate from account creation, always** — the one piece of the old reasoning that
still holds, restated for the new column. Nothing about `not_allowlisted` (FR-005),
`no_aoe2_profile` (FR-003) or the rest of `auth.py`'s sign-in flow touches `archival_objected_at`
at all: a user exists, is allowlisted, and is already being archived (the default) with the
column still null.

**Objecting is idempotent, not cumulative.** A second `{"objected": true}` call leaves the original
`archival_objected_at` untouched rather than overwriting it with a later moment — the timestamp
records *when the objection was first made*, and moving it forward on every repeat call would
quietly rewrite that fact each time the front end happens to re-send the same choice.

**Resuming is the mirror action, not an error.** `{"objected": false}` clears
`archival_objected_at` back to `None`, which is what resumes archival: the ingester's own gate
(`apps/ingester/src/aoe2stats_ingester/discover.py`'s `_archiving_profile_ids`) reads
`archival_objected_at IS NULL` and starts matching this user again from the next cycle. Resuming on
an account that never objected in the first place is consequently a no-op that still answers 200:
there is nothing to clear, and the caller asking "please resume" is not an error just because
archival never stopped.

**Request body.** `{"objected": bool}` — deliberately not `{"granted": bool}` carried over from the
retired route: `granted` under the new model would mean its own negation (granting *not* to be
archived reads backwards), so the field name states the Art. 21 action directly instead of an
inverted consent flag. `true` objects, `false` resumes.

**This is a rename, not an addition.** `POST /api/privacy/consent` does not exist alongside this
route: the two-timestamp state it wrote to is gone from the data model, so leaving the old path
reachable would let a caller ask this router to write into columns that no longer exist.

**`POST /api/privacy/export` and `GET /api/privacy/export/{id}` (T090).** `contracts/
http-api.md`'s "Privacy" table: "Starts an export; returns a job reference" and "Status, then a
signed URL to the archive." Every read and every object-store call lives here, in this router —
`aoe2stats_core.privacy.export` holds only the pure assembly of already-fetched rows into one zip
(that module's own docstring), because `packages/core` may not import `aoe2stats_storage` or reach
the object store directly (plan.md's package boundary: "entities, value objects, use cases. No
I/O.").

The job runs to completion inside the `POST` itself — there is no queue, no worker and no second
process anywhere in this feature that could pick a `data_requests` row up later, and the platform
this API deploys to (`docs/adr/0002-hosting.md`) gives a request its own budget regardless. `GET
.../export/{id}` therefore only ever answers `"completed"` for a job this process created, but it
still polls a stored `data_requests` row rather than trusting the `POST` response alone: a future
asynchronous implementation changes nothing about what a caller reads from this second endpoint.

**What the archive carries, per FR-036 and T090's own task text**: the account, the caller's own
Steam identities, their own profile links (every one they have ever held, not only the active
ones — it is their own link history), the match records and the match-player rows for every match
one of those profiles played, and the `stored` replay blobs for those same profiles. Plus 003's two
tables its `data-model.md` names explicitly: `favourites` (the profile ids and the dates) and the
analyses the caller requested (`match_analyses.requested_by_user_id`, as match ids and dates).
`profile_search_cache` and `rate_limit_counters` are never read here at all — 003's `data-model.md`
gives the reason per table (neither is keyed to a user an export could name), and the surest way to
keep an excluded table out of an archive is to never query it in the first place.

**Ownership on the `GET`, the same `not_found` discipline every other route in this feature
uses** (`profiles.py`'s and `replays.py`'s own module docstrings): a job id that does not exist, or
exists for a different user, or names a different kind of `data_requests` row, all answer the
identical `404 not_found` — never a `403`, which would itself disclose that the id belongs to
someone.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api import security
from aoe2stats_api.deps import ObjectStoreDep, SessionDep, SettingsDep
from aoe2stats_api.errors import APIError
from aoe2stats_core.privacy.export import ExportBundle, build_export_archive
from aoe2stats_storage.models import (
    CaptureStatus,
    DataRequest,
    DataRequestKind,
    Favourite,
    Match,
    MatchAnalysis,
    MatchPlayer,
    ProfileLink,
    ReplayCapture,
    SteamIdentity,
    User,
)
from aoe2stats_storage.models import Session as SessionRow
from aoe2stats_storage.objects import ObjectStore

router = APIRouter(tags=["privacy"])


class ArchivalObjectionRequest(BaseModel):
    objected: bool


# --- Session resolution, the same discipline `auth.py` and `profiles.py` already establish -------


async def _current_session_row(
    request: Request, db_session: AsyncSession, secret: str
) -> SessionRow | None:
    """The caller's active `sessions` row, or `None` for a missing, tampered, expired or revoked
    cookie — mirrors `auth.py`'s and `profiles.py`'s own helper of the same name and shape."""
    session_id = security.read_session_id(request.cookies.get(security.SESSION_COOKIE_NAME), secret)
    if session_id is None:
        return None
    return await security.get_active_session(db_session, session_id)


def _require_session(session_row: SessionRow | None) -> SessionRow:
    if session_row is None:
        raise APIError(
            status_code=401,
            code="not_authenticated",
            message="Sign in to manage your archival objection.",
        )
    return session_row


# --- POST /api/privacy/archival-objection -----------------------------------------------------


@router.post("/privacy/archival-objection")
async def set_archival_objection(
    body: ArchivalObjectionRequest, request: Request, db_session: SessionDep, settings: SettingsDep
) -> dict[str, Any]:
    """FR-035: object to archival, recording when the objection was first made — or resume it by
    clearing that same timestamp (module docstring)."""
    secret = settings.app_secret_key.get_secret_value()
    session_row = _require_session(await _current_session_row(request, db_session, secret))

    user = await db_session.get(User, session_row.user_id)
    if user is None:
        raise APIError(
            status_code=401,
            code="not_authenticated",
            message="Sign in to manage your archival objection.",
        )

    now = datetime.now(UTC)
    if body.objected:
        # Idempotent, not cumulative (module docstring): set only the first time.
        if user.archival_objected_at is None:
            user.archival_objected_at = now
    else:
        # Resuming when there was never an objection is a no-op that still answers 200 (module
        # docstring): nothing to clear.
        user.archival_objected_at = None

    return {
        "archival_objected": user.archival_objected_at is not None,
        "archival_objected_at": user.archival_objected_at.isoformat()
        if user.archival_objected_at is not None
        else None,
    }


# --- POST /api/privacy/export and GET /api/privacy/export/{id} (T090) --------------------------


def _export_object_key(job_id: uuid.UUID) -> str:
    """The object-store key one export archive is written under — its own prefix, distinct from
    `replay_object_key`'s (`aoe2stats_storage.objects`), so an export can never collide with a
    captured replay however both schemes evolve."""
    return f"exports/{job_id}.zip"


def _export_not_found() -> APIError:
    """FR-045's own discipline, applied to a job id: a missing job, someone else's job, or a job
    of a different `kind` all answer the identical `not_found` (module docstring)."""
    return APIError(
        status_code=404,
        code="not_found",
        message="No export was found for that id.",
    )


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


async def _owned_profile_ids(db_session: AsyncSession, *, user_id: uuid.UUID) -> list[int]:
    """Every profile id `user_id` has ever linked, active or not — their own link history is
    their own data (module docstring's "every one they have ever held")."""
    result = await db_session.execute(
        select(ProfileLink.profile_id).where(ProfileLink.user_id == user_id)
    )
    return list(result.scalars().all())


async def _build_export_bundle(
    db_session: AsyncSession, object_store: ObjectStore, *, user: User
) -> ExportBundle:
    """Every read this export needs, run once against `db_session` and the object store, then
    folded into the `ExportBundle` `aoe2stats_core.privacy.export.build_export_archive` assembles
    into a zip (module docstring). `profile_search_cache` and `rate_limit_counters` are never
    queried here at all — the surest way to keep an excluded table out of an archive."""
    identities = list(
        (
            await db_session.execute(select(SteamIdentity).where(SteamIdentity.user_id == user.id))
        ).scalars()
    )
    links = list(
        (await db_session.execute(select(ProfileLink).where(ProfileLink.user_id == user.id)))
        .scalars()
        .all()
    )
    profile_ids = [link.profile_id for link in links]

    matches: list[Match] = []
    match_players: list[MatchPlayer] = []
    replay_blobs: dict[str, bytes] = {}
    if profile_ids:
        matches = list(
            (
                await db_session.execute(
                    select(Match).where(
                        Match.game_id.in_(
                            select(MatchPlayer.game_id).where(
                                MatchPlayer.profile_id.in_(profile_ids)
                            )
                        )
                    )
                )
            )
            .scalars()
            .all()
        )
        game_ids = [match.game_id for match in matches]

        if game_ids:
            match_players = list(
                (
                    await db_session.execute(
                        select(MatchPlayer).where(MatchPlayer.game_id.in_(game_ids))
                    )
                )
                .scalars()
                .all()
            )

        captures = list(
            (
                await db_session.execute(
                    select(ReplayCapture).where(
                        ReplayCapture.profile_id.in_(profile_ids),
                        ReplayCapture.status == CaptureStatus.STORED,
                    )
                )
            )
            .scalars()
            .all()
        )
        for capture in captures:
            if capture.object_key is None:
                continue
            replay_blobs[capture.object_key] = await object_store.get(capture.object_key)

    favourites = list(
        (await db_session.execute(select(Favourite).where(Favourite.user_id == user.id)))
        .scalars()
        .all()
    )
    requested_analyses = list(
        (
            await db_session.execute(
                select(MatchAnalysis).where(MatchAnalysis.requested_by_user_id == user.id)
            )
        )
        .scalars()
        .all()
    )

    return ExportBundle(
        account={
            "id": str(user.id),
            "created_at": _iso(user.created_at),
            "allowlisted_at": _iso(user.allowlisted_at),
            "archival_objected_at": _iso(user.archival_objected_at),
        },
        steam_identities=[
            {
                "steam_id64": identity.steam_id64,
                "verified_at": _iso(identity.verified_at),
                "last_sign_in_at": _iso(identity.last_sign_in_at),
            }
            for identity in identities
        ],
        profile_links=[
            {
                "profile_id": link.profile_id,
                "is_primary": link.is_primary,
                "linked_at": _iso(link.linked_at),
                "unlinked_at": _iso(link.unlinked_at),
            }
            for link in links
        ],
        matches=[
            {
                "game_id": match.game_id,
                "leaderboard_id": match.leaderboard_id,
                "map_name": match.map_name,
                "started_at": _iso(match.started_at),
                "completed_at": _iso(match.completed_at),
                "duration_seconds": match.duration_seconds,
                "source": match.source,
            }
            for match in matches
        ],
        match_players=[
            {
                "game_id": player.game_id,
                "profile_id": player.profile_id,
                "team_id": player.team_id,
                "civ_id": player.civ_id,
                "color_id": player.color_id,
                "result": player.result,
                "rating": player.rating,
                "rating_diff": player.rating_diff,
            }
            for player in match_players
        ],
        favourites=[
            {"profile_id": favourite.profile_id, "created_at": _iso(favourite.created_at)}
            for favourite in favourites
        ],
        requested_analyses=[
            {"game_id": analysis.game_id, "requested_at": _iso(analysis.requested_at)}
            for analysis in requested_analyses
        ],
        replay_blobs=replay_blobs,
    )


@router.post("/privacy/export", status_code=202)
async def start_export(
    request: Request, db_session: SessionDep, settings: SettingsDep, object_store: ObjectStoreDep
) -> dict[str, Any]:
    """FR-036: assemble the caller's export inline and return the `data_requests` row's id as the
    job reference `contracts/http-api.md` promises (module docstring). There is no queue for this
    to hand off to, so the archive is built and stored before this call returns."""
    secret = settings.app_secret_key.get_secret_value()
    session_row = _require_session(await _current_session_row(request, db_session, secret))
    user = await db_session.get(User, session_row.user_id)
    if user is None:
        raise APIError(
            status_code=401, code="not_authenticated", message="Sign in to export your data."
        )

    data_request = DataRequest(kind=DataRequestKind.EXPORT, subject_user_id=user.id)
    db_session.add(data_request)
    await db_session.flush()

    bundle = await _build_export_bundle(db_session, object_store, user=user)
    archive_bytes = build_export_archive(bundle)
    await object_store.put(_export_object_key(data_request.id), archive_bytes)

    data_request.completed_at = datetime.now(UTC)
    data_request.outcome = f"exported {len(archive_bytes)} bytes"

    return {"id": str(data_request.id), "status": "completed"}


@router.get("/privacy/export/{job_id}")
async def export_status(
    job_id: uuid.UUID,
    request: Request,
    db_session: SessionDep,
    settings: SettingsDep,
    object_store: ObjectStoreDep,
) -> dict[str, Any]:
    """`contracts/http-api.md`: "Status, then a signed URL to the archive." Ownership on the job
    id follows the same `not_found` discipline every other route in this feature uses (module
    docstring): a job that does not exist, belongs to someone else, or is not an export all answer
    identically."""
    secret = settings.app_secret_key.get_secret_value()
    session_row = _require_session(await _current_session_row(request, db_session, secret))

    data_request = await db_session.get(DataRequest, job_id)
    if (
        data_request is None
        or data_request.kind is not DataRequestKind.EXPORT
        or data_request.subject_user_id != session_row.user_id
    ):
        raise _export_not_found()

    if data_request.completed_at is None:
        return {"id": str(data_request.id), "status": "queued"}

    signed_url = await object_store.signed_get_url(
        _export_object_key(data_request.id),
        filename=f"aoe2-stats-export-{data_request.id}.zip",
    )
    return {
        "id": str(data_request.id),
        "status": "completed",
        "download_url": signed_url,
    }
