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

**`GET /api/privacy/erase` and `POST /api/privacy/erase` (T091).** `contracts/http-api.md`:
"Requires an explicit confirmation token from a prior GET. Irreversible (FR-037)." The `GET`
mints a short-lived, HMAC-signed `confirmation_token` bound to the caller's own user id and does
nothing else; the `POST` verifies it and then, and only then, erases the account — every read and
every write, `packages/core`'s `aoe2stats_core.privacy.erasure.pseudonymise_profile` again holding
only the pure pseudonymisation plan (that module's own docstring), the same split `export.py`
draws. `erase_account`'s own docstring carries what is deleted, what is cleared with its row kept,
and what is pseudonymised in place.

**`POST /api/privacy/object` (T092).** `contracts/http-api.md`: "the one unauthenticated write in
the system" — the person objecting is by definition not a user, so there is no session cookie to
require and none is asked for. Two properties follow, both asserted by `apps/api/tests/
test_third_party_objection.py` (T088): reachable with no session at all, and rate limited, because
the absence of a session is exactly what makes an unthrottled version of this route a
denial-of-service vector against the data (nothing about *who* is calling stops a scripted flood
the way a per-user bucket would for every other write in this API). `_check_objection_rate_limit`
below therefore counts recent rows in `data_requests` itself rather than keying a limit to a
caller this route has no identity for — the fixed-window counter `ratelimit.py`'s
`check_and_increment` gives every other route does not fit here at all: `rate_limit_counters.
user_id` is a `NOT NULL` foreign key into `users`, and this route's caller is, by construction,
never a row in that table.

**Records rather than acts** — `data-model.md`'s `data_requests` section and the contract both say
it: this call writes one row, `kind = third_party_objection`, `subject_profile_id` set to the
profile named, `subject_user_id` null (the objector is not a user, `requested_at` set,
`completed_at` null), and pseudonymises nothing itself. FR-039's "MUST pseudonymise their
identifiers on request" is carried out later, by a person, through `resolve_third_party_objection`
below — the deferred second caller data-model.md already named for `_pseudonymise_profile_ids`
("the same mechanism FR-039 gives third parties"), T091's `POST /api/privacy/erase` being the
first. `resolve_third_party_objection` is deliberately not wired to any route: an endpoint that
pseudonymised a named profile on an unauthenticated call would be the identical denial-of-service
vector the rate limit above exists to close, only worse, since it would act rather than merely
record. `docs/privacy/processing-register.md`'s handling-procedure section names who runs it and
within what delay.
"""

from __future__ import annotations

import asyncio
import math
import os
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from aoe2stats_api import security
from aoe2stats_api.deps import ObjectStoreDep, SessionDep, SettingsDep
from aoe2stats_api.errors import APIError
from aoe2stats_core.privacy.erasure import pseudonymise_profile
from aoe2stats_core.privacy.export import ExportBundle, build_export_archive
from aoe2stats_ingester import discover
from aoe2stats_storage.models import (
    AoeProfile,
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
from aoe2stats_storage.objects import ObjectStore, replay_object_key

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

    # T426: `avatar_hash` sits beside `alias`/`country` on the account's own linked profiles —
    # same public-source, legitimate-interest basis (constitution IX, research.md D6) — so it is
    # exported alongside `profile_links` rather than left out of an archive that already names
    # this profile at all. One query for every owned profile id, keyed for the dict-comprehension
    # below rather than a per-link lookup.
    avatar_hashes_by_profile: dict[int, str | None] = {}
    if profile_ids:
        owned_profiles = (
            (
                await db_session.execute(
                    select(AoeProfile).where(AoeProfile.profile_id.in_(profile_ids))
                )
            )
            .scalars()
            .all()
        )
        avatar_hashes_by_profile = {
            profile.profile_id: profile.avatar_hash for profile in owned_profiles
        }

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
                "avatar_hash": avatar_hashes_by_profile.get(link.profile_id),
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


# --- POST /api/privacy/erase, and the GET that mints its confirmation token (T091) --------------


class ErasureConfirmationRequest(BaseModel):
    confirmation_token: str


#: The Steam OpenID CSRF `state` (`security.py`'s own `CSRF_STATE_TTL`) is the codebase's own
#: precedent for "how long does a confirmation value stay good": minutes, not hours, because the
#: round trip it bridges — one `GET`, then one deliberate `POST` — is a single sitting, never a
#: bookmark to come back to later.
_ERASURE_CONFIRMATION_TTL = timedelta(minutes=10)

#: Separates the two halves of the signed confirmation-token payload (`<user_id>|<issued_at>`).
#: Never `:`: `datetime.isoformat()` on a timezone-aware value already contains colons of its own
#: (the offset, `+00:00`), so splitting on the *last* `:` would cut the timestamp apart instead of
#: the payload in two. Neither a UUID's hyphens nor an ISO 8601 timestamp ever contains `|`.
_ERASURE_TOKEN_SEPARATOR = "|"


def _issue_erasure_confirmation_token(
    *, user_id: uuid.UUID, secret: str, now: datetime | None = None
) -> str:
    """A short-lived, HMAC-signed token binding one confirmation to one caller — reuses
    `security._sign`, the same primitive the session and CSRF-state cookies are already signed
    with, rather than a new table purely to hold a value that only ever needs to prove it was
    minted here, for this user, recently. Self-verifying, so `GET /api/privacy/erase` needs no
    write of its own — unlike `csrf_states`, which a state minted *before any session exists*
    cannot avoid (`security.py`'s own docstring), a confirmation token minted for an already
    signed-in caller has a `user_id` to bind itself to instead."""
    moment = now or datetime.now(UTC)
    payload = f"{user_id}{_ERASURE_TOKEN_SEPARATOR}{moment.isoformat()}"
    return security._sign(payload, secret)


def _verify_erasure_confirmation_token(
    token: str, *, user_id: uuid.UUID, secret: str, now: datetime | None = None
) -> bool:
    """Whether `token` is a confirmation this exact caller was handed by a prior `GET`, minted
    within `_ERASURE_CONFIRMATION_TTL`. Rejects a tampered signature, a token minted for a
    different `user_id` (so one caller's own `GET` can never confirm another caller's erasure),
    a malformed payload, and one that has simply expired — all identically, since none of those
    distinctions is this caller's to learn (the same undifferentiated rejection `security._unsign`
    already gives a tampered session cookie)."""
    payload = security._unsign(token, secret)
    if payload is None:
        return False
    raw_user_id, separator, raw_issued_at = payload.rpartition(_ERASURE_TOKEN_SEPARATOR)
    if not separator or raw_user_id != str(user_id):
        return False
    try:
        issued_at = datetime.fromisoformat(raw_issued_at)
    except ValueError:
        return False
    moment = now or datetime.now(UTC)
    return timedelta(0) <= moment - issued_at <= _ERASURE_CONFIRMATION_TTL


def _erasure_confirmation_invalid() -> APIError:
    return APIError(
        status_code=403,
        code="confirmation_token_invalid",
        message="That confirmation token is invalid, was not issued to you, or has expired. "
        "Request a fresh one from GET /api/privacy/erase.",
    )


@router.get("/privacy/erase")
async def start_erasure(
    request: Request, db_session: SessionDep, settings: SettingsDep
) -> dict[str, Any]:
    """`contracts/http-api.md`: "Requires an explicit confirmation token from a prior GET."
    Mints that token and nothing else — no row is written, nothing about the account changes; the
    explicit step FR-037 requires is this call existing at all, distinct from the irreversible one
    below."""
    secret = settings.app_secret_key.get_secret_value()
    session_row = _require_session(await _current_session_row(request, db_session, secret))
    token = _issue_erasure_confirmation_token(user_id=session_row.user_id, secret=secret)
    return {"confirmation_token": token}


async def _pseudonymise_profile_ids(
    db_session: AsyncSession, profile_ids: Sequence[int]
) -> list[tuple[int, int]]:
    """Returns the `(game_id, profile_id)` pairs of the `match_players` rows it retargets, as they
    were under the originals (T730: erasure deletes the objects under those keys). They are read
    under the step-1 locks below, so a concurrent insert cannot add one between the read and the
    retarget. A caller that has no use for them ignores the return value.

    The I/O half of `aoe2stats_core.privacy.erasure.pseudonymise_profile`, which computes only
    the plan (that module's own docstring), run over every id in `profile_ids` in one transaction:
    insert the placeholder `aoe_profiles` row each `profile_id`'s `match_players` rows are about
    to be retargeted onto (idempotent — a second call over the same `profile_id` finds it already
    there), retarget them, and mask the original row's own `alias`/`country` in place, since it
    usually survives this untouched otherwise (a `favourites` row someone else holds naming it, a
    `rating_snapshots` row) and leaving its identifying columns as they were would leave exactly
    the trace this exists to close.

    **T459e: row locks are taken in the global order, all of them before any write.** The order
    is the global one, defined in the module notes above `touch_aoe_profiles` in
    `apps/ingester/src/aoe2stats_ingester/discover.py`; a row lock is held to commit, so a writer
    that reaches an earlier table or a lower key after a later one can wait on a discovery batch
    that waits on it. This function writes no `matches` row. It takes:

    1. every `aoe_profiles` key it writes or references — each original and each placeholder —
       one key at a time in ascending order across **all** of `profile_ids`, not per profile: a
       placeholder is `-abs(profile_id)`, lower than its own original and, for positive ids, than
       every other original, so a loop that finished one profile before starting the next would
       step back. An existing row is locked `FOR NO KEY UPDATE` (the strength of the `UPDATE` that
       follows); a missing placeholder is inserted at that point in the sequence, which is its
       lock.
    2. every `match_players` row of the originals, in one ascending pass through
       `discover.lock_match_players`. The keys come from a plain read taken after step 1.
       `persist_matches_and_profiles` upserts a participant's `aoe_profiles` row before it writes
       that participant's `match_players` row, and that upsert waits on the lock step 1 holds, so a
       batch using it cannot add a row for an original between the read and the writes below.

    The writes that follow touch only rows already held. `UPDATE match_players SET profile_id`
    moves each held `(game_id, original)` to `(game_id, placeholder)`;
    `persist_matches_and_profiles` would reach that new key only after upserting the
    placeholder's `aoe_profiles` row, which step 1 holds.

    **T426: `avatar_hash` needs no pseudonym.** Unlike `alias`/`country`, which must survive as
    plausible values (`pseudonymise_profile`'s own plan computes a masked pair for exactly that
    reason), a Steam avatar hash has no "plausible masked value" to compute — it identifies a
    Steam account, not a display name, so the only closing move is to null it, on both the
    placeholder row and the original one, directly here rather than growing
    `packages/core`'s `PseudonymisationPlan` for a field that needs no computation at all."""
    plans = {profile_id: pseudonymise_profile(profile_id) for profile_id in profile_ids}
    if not plans:
        return []
    placeholders = {plan.pseudonymous_profile_id: plan for plan in plans.values()}

    originals: list[AoeProfile] = []
    for key in sorted({*plans, *placeholders}):
        row = (
            await db_session.execute(
                select(AoeProfile)
                .where(AoeProfile.profile_id == key)
                .with_for_update(key_share=True)
            )
        ).scalar_one_or_none()
        if row is not None:
            if key in plans:
                originals.append(row)
        elif key in placeholders:
            placeholder = placeholders[key]
            db_session.add(
                AoeProfile(
                    profile_id=key,
                    alias=placeholder.alias,
                    country=placeholder.country,
                    avatar_hash=None,
                )
            )
            await db_session.flush()

    held = (
        await db_session.execute(
            select(MatchPlayer.game_id, MatchPlayer.profile_id).where(
                MatchPlayer.profile_id.in_(list(plans))
            )
        )
    ).all()
    pairs = [(game_id, owner) for game_id, owner in held]
    await discover.lock_match_players(db_session, pairs)

    for profile_id, plan in plans.items():
        await db_session.execute(
            update(MatchPlayer)
            .where(MatchPlayer.profile_id == profile_id)
            .values(profile_id=plan.pseudonymous_profile_id)
        )

    for original_profile in originals:
        plan = plans[original_profile.profile_id]
        original_profile.alias = plan.alias
        original_profile.country = plan.country
        original_profile.avatar_hash = None

    return pairs


#: How many `DeleteObject` requests `_delete_objects` keeps in flight. `asyncio.to_thread`
#: runs each on the default executor, so the effective width is the smaller of this and that pool's
#: size, `min(32, cpu_count + 4)`: at least 5 on any host. 10 is botocore's default connection pool
#: (`max_pool_connections`, which `ObjectStore`'s client keeps), so a wave never outnumbers the
#: connections: a wider one would queue or open connections and make the wave count optimistic.
_ERASURE_DELETE_CONCURRENCY = 10


def _erasure_delete_width() -> int:
    """How many `DeleteObject` requests actually run at once: the smaller of
    `_ERASURE_DELETE_CONCURRENCY` and the default thread pool `asyncio.to_thread` runs them on,
    `min(32, cpu_count + 4)` (Python 3.13's `ThreadPoolExecutor` default, which reads
    `os.process_cpu_count`), so at least 5 on any host."""
    pool = min(32, (os.process_cpu_count() or 1) + 4)
    return min(_ERASURE_DELETE_CONCURRENCY, pool)


def _erasure_delete_waves(*, unnamed: int, named: int) -> int:
    """How many rounds of concurrent `DeleteObject` requests erasing `unnamed` then `named` keys
    takes. The two passes run one after the other, so each rounds up on its own."""
    width = _erasure_delete_width()
    return math.ceil(unnamed / width) + math.ceil(named / width)


#: The most waves (`_erasure_delete_waves`) erasure accepts; past it, `erase_account` refuses
#: before the first `DeleteObject`. 37 is the docstring's worst case: N = 177 pairs, the largest
#: measured history, at C = 5, one key unnamed and 176 named, so 1 + 36 waves. At 200 ms per
#: `DeleteObject` that is about 7.4 s of the function's 10 s `maxDuration`, leaving the rest for
#: the database work. The 200 ms is an assumption, not a measurement: neither the R2 latency
#: from `cdg1` nor how many keys an account accumulates across windows has been measured. A
#: wrong guess must not be found out by a kill during the named pass, which rolls the database
#: back with originals already deleted, so the budget is checked first and the cost of a wrong
#: guess is a refusal, never a loss. Raising it needs a measured latency, or a different design.
_ERASURE_WAVE_BUDGET = 37


def _independent_session(db_session: AsyncSession) -> AsyncSession:
    """A session bound to the same engine as `db_session`, independent of its transaction; what
    `routers/replays.py`'s `_audit_session` is, kept local so no router imports another's private
    name. Anything written through it before a `raise APIError(...)` survives the rollback
    `deps.py`'s `session_scope` performs on `db_session`."""
    bind = db_session.get_bind()
    assert isinstance(bind, Engine), f"expected an Engine bind, got {type(bind)}"
    return AsyncSession(bind=AsyncEngine(bind))


async def _refuse_erasure_too_large(
    db_session: AsyncSession, *, user_id: uuid.UUID, keys: int, waves: int
) -> APIError:
    """Records the refusal as a pending `data_requests` row of kind `erasure`
    (`completed_at` NULL) on an independent session, and returns the error to raise. One pending
    row per account: a retry updates the existing uncompleted row's `outcome` and `requested_at`
    instead of inserting another. No alert: severity 1 is reserved (constitution I) and a new
    alert kind needs a migration."""
    outcome = f"refused: {keys} keys need {waves} waves, budget {_ERASURE_WAVE_BUDGET}"
    async with _independent_session(db_session) as audit_session:
        pending = (
            (
                await audit_session.execute(
                    select(DataRequest)
                    .where(
                        DataRequest.kind == DataRequestKind.ERASURE,
                        DataRequest.subject_user_id == user_id,
                        DataRequest.completed_at.is_(None),
                    )
                    .order_by(DataRequest.requested_at)
                    .limit(1)
                    .with_for_update()
                )
            )
            .scalars()
            .first()
        )
        if pending is None:
            audit_session.add(
                DataRequest(kind=DataRequestKind.ERASURE, subject_user_id=user_id, outcome=outcome)
            )
        else:
            pending.outcome = outcome
            pending.requested_at = datetime.now(UTC)
        await audit_session.commit()
    return APIError(
        status_code=503,
        code="erasure_too_large",
        message="Your account could not be erased: its stored replays cannot all be deleted "
        "within this service's time limit. Nothing was erased or deleted, and your account is "
        "unchanged. Your request has been recorded.",
        detail={"waves": waves, "budget": _ERASURE_WAVE_BUDGET},
    )


async def _delete_objects(object_store: ObjectStore, keys: Sequence[str]) -> None:
    """Delete every key in `keys`, concurrently, at most `_ERASURE_DELETE_CONCURRENCY` in flight
    (T730). `ObjectStore.delete` succeeds on a key that holds nothing, so a key whose object never
    existed costs one cheap request, not a lookup first. Used for the keys no row names, then for
    the keys rows name (`erase_account`)."""
    gate = asyncio.Semaphore(_ERASURE_DELETE_CONCURRENCY)

    async def delete_one(key: str) -> None:
        async with gate:
            await object_store.delete(key)

    await asyncio.gather(*(delete_one(key) for key in keys))


@router.post("/privacy/erase")
async def erase_account(
    body: ErasureConfirmationRequest,
    request: Request,
    db_session: SessionDep,
    settings: SettingsDep,
    object_store: ObjectStoreDep,
) -> dict[str, Any]:
    """FR-037, SC-008: irreversible erasure of the caller's own account, confirmed by a token only
    `GET /api/privacy/erase` could have minted for this exact caller.

    **Deleted**: the user row itself, every Steam identity, every session, every profile link,
    every `rate_limit_counters` and `favourites` row — all by the database's own `ondelete`
    actions on `users.id`, fired the moment the `DELETE FROM users` below runs, not by this
    function walking each table itself (`packages/storage/.../models.py`'s own comments on each of
    those foreign keys name the same cascade). The one thing no foreign key can reach into is the
    object store: every `replay_captures` row naming one of this user's own profiles is deleted
    here, its blob deleted from `object_store` first — quickstart scenario 10 point 2's "verified
    by listing the bucket, not by trusting a success response" is a claim about the bucket, and
    only an explicit `object_store.delete` earns it. Deleting each capture row cascades its own
    `replay_access_log` rows (`ondelete="CASCADE"` on `replay_capture_id`) regardless of who made
    the access; deleting the user cascades every `replay_access_log` row this user made as an
    *accessor* of anyone else's capture, by the identical mechanism on `user_id` — both are the
    schema's own design (`ReplayAccessLog`'s class docstring), not something this function decides.

    **Cleared, row retained**: `match_analyses.requested_by_user_id` and
    `retained_recordings.requested_by_user_id` — `ondelete="SET NULL"` on both, fired by the same
    `DELETE FROM users`. Neither row nor, for `retained_recordings`, its object is ever touched
    here: a published analysis must stay recomputable (constitution IV), and deleting a retained
    recording is T092's objection route on the person it depicts, never this one on whoever merely
    asked for it.

    **Pseudonymised in place, row and match retained**: every `match_players` row naming one of
    this user's own profiles, via `_pseudonymise_profile_ids` — `matches` itself carries no
    `profile_id` column to touch (`packages/storage/.../models.py`'s `Match`), so nothing about it
    changes at all; it describes a game other people also played.

    **The accountability record**: one `data_requests` row of kind `erasure`, inserted before
    anything else so it exists to record what is about to happen, `subject_user_id` set to this
    user for exactly as long as the row survives it — the same `ondelete="SET NULL"` nulls it the
    moment the user is deleted, which is what lets SC-008's own requirement (verifiably resolved
    even once the subject is gone) point at something once this call returns.

    **Objects no row names (T730), then the named blobs.** An upload whose row write failed after
    its object write leaves an object under `replay_object_key(game_id, profile_id)` that no
    `object_key` names, with or without a `replay_captures` row for the pair. The pairs are those
    of `match_players` for the user's profiles (returned by `_pseudonymise_profile_ids`, as they
    were before it retargets them) and of `replay_captures`. One `DeleteObject` goes to each such
    key that no row names, **first**; then one to each key a row names. A function killed at the
    limit, or a `DeleteObject` error partway through a pass, rolls the database back (after the
    idle-in-transaction timeout for a kill), and what that leaves depends on the pass: during the
    unnamed pass only objects no row names are gone, so no row points at a missing original; during
    the named pass the rolled-back rows still name objects already deleted - originals gone while
    the account survives - narrowed to that pass. A retry repeats the idempotent deletes.

    **Duration.** Erasure's route runs in `api/index.py`, whose limit is `maxDuration: 10` in
    `vercel.json` (`api/cron/ingest.py` and `api/analyze.py` are separate functions). Both passes
    delete concurrently through `_delete_objects`, at most C in flight, C being the smaller of
    `_ERASURE_DELETE_CONCURRENCY` and the default thread pool (at least 5). With U unnamed and K
    named keys, U + K <= N pairs, the deletes take ceil(U / C) + ceil(K / C) waves: at most 37 for
    N = 177 at C = 5, about 7.4 s at 200 ms per `DeleteObject`, so the condition is one
    `DeleteObject` well under ~200 ms. That is the condition, not a measurement. The largest
    measured history is 177 matches for one profile in one Relic window
    (`specs/004-visual-parity/tasks.md`, the 2026-10-04 amendment above T459); how many
    `match_players` rows a profile accumulates across many windows, and the latency of an R2
    `DeleteObject` from `cdg1`, are not measured. **Past the bound, erasure refuses before it
    deletes anything.** After both key sets are known and before the first `DeleteObject`, the
    waves are counted (`_erasure_delete_waves`); over `_ERASURE_WAVE_BUDGET` the route answers 503
    `erasure_too_large`, the database transaction rolls back, and one `data_requests` row of kind
    `erasure` with `completed_at` NULL and the outcome `refused: ...` is written through an
    independent session so the rollback does not take it. A refused account stays whole and is
    recorded; a kill mid-pass, which would have deleted originals the account's rows still name, is
    never risked. It fails every retry identically (the set is re-read each time), and lifting the
    refusal needs a measured bound or a different design.
    """
    secret = settings.app_secret_key.get_secret_value()
    session_row = _require_session(await _current_session_row(request, db_session, secret))
    user = await db_session.get(User, session_row.user_id)
    if user is None:
        raise APIError(
            status_code=401, code="not_authenticated", message="Sign in to erase your account."
        )
    user_id = user.id

    if not _verify_erasure_confirmation_token(
        body.confirmation_token, user_id=user_id, secret=secret
    ):
        raise _erasure_confirmation_invalid()

    profile_ids = await _owned_profile_ids(db_session, user_id=user_id)

    data_request = DataRequest(kind=DataRequestKind.ERASURE, subject_user_id=user_id)
    db_session.add(data_request)
    await db_session.flush()

    if profile_ids:
        played = await _pseudonymise_profile_ids(db_session, profile_ids)

        # After the pseudonymisation, never before: `replay_captures` is the fourth table in the
        # global lock order (the notes above `touch_aoe_profiles` in
        # `apps/ingester/src/aoe2stats_ingester/discover.py`), and `DiscoverStage` writes
        # `aoe_profiles`, `match_players`, then `replay_captures`. A delete that ran first held a
        # capture row while waiting on `aoe_profiles`, and a discovery batch inserting that same
        # `(game_id, profile_id)` waited on the delete: a deadlock that aborts discovery. The
        # rows are locked in ascending `(game_id, profile_id)` order, then the blobs and rows go.
        captures = list(
            (
                await db_session.execute(
                    select(ReplayCapture)
                    .where(ReplayCapture.profile_id.in_(profile_ids))
                    .order_by(ReplayCapture.game_id, ReplayCapture.profile_id)
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        named_keys = {c.object_key for c in captures if c.object_key is not None}
        pairs = [*played, *((capture.game_id, capture.profile_id) for capture in captures)]
        unnamed_keys = {replay_object_key(game_id, owner) for game_id, owner in pairs} - named_keys
        # Before any `DeleteObject` (docstring, "Duration"): an erasure that cannot fit is
        # refused whole, since a kill in the named pass is irreversible.
        waves = _erasure_delete_waves(unnamed=len(unnamed_keys), named=len(named_keys))
        if waves > _ERASURE_WAVE_BUDGET:
            raise await _refuse_erasure_too_large(
                db_session,
                user_id=user_id,
                keys=len(unnamed_keys) + len(named_keys),
                waves=waves,
            )
        # The unnamed pass first (docstring): a kill in the slow pass must not leave rows naming
        # objects already deleted.
        await _delete_objects(object_store, sorted(unnamed_keys))
        await _delete_objects(object_store, sorted(named_keys))
        await db_session.execute(
            delete(ReplayCapture).where(ReplayCapture.profile_id.in_(profile_ids))
        )

    data_request.completed_at = datetime.now(UTC)
    data_request.outcome = "account erased"

    await db_session.execute(delete(User).where(User.id == user_id))

    return {"status": "erased"}


# --- POST /api/privacy/object, and the deferred resolution it hands to a human (T092) -----------


class ThirdPartyObjectionRequest(BaseModel):
    profile_id: int


#: This route's own rate limit, counted against `data_requests` itself rather than through
#: `ratelimit.py`'s `check_and_increment` (module docstring): there is no caller identity here to
#: key a per-user bucket on, so the limit this route carries bounds the route as a whole, in the
#: one window below, rather than any one caller. Sized the same order of magnitude as the sibling
#: per-user buckets (`PLAYER_SEARCH_MAX_PER_USER_PER_MINUTE=20`, `.env.example`) — a literal here,
#: not a `Settings` field, for the same reason `_ERASURE_CONFIRMATION_TTL` above is one: it tunes
#: this module's own internal behaviour rather than something an operator needs to change per
#: deployment.
_OBJECTION_RATE_LIMIT = 20
_OBJECTION_RATE_LIMIT_WINDOW = timedelta(minutes=1)


def _objection_rate_limited() -> APIError:
    return APIError(
        status_code=429,
        code="rate_limited",
        message="Too many objections. Try again shortly.",
        detail={"retry_after": int(_OBJECTION_RATE_LIMIT_WINDOW.total_seconds())},
    )


async def _check_objection_rate_limit(db_session: AsyncSession, *, now: datetime) -> None:
    """Raises `_objection_rate_limited()` once this route has already recorded
    `_OBJECTION_RATE_LIMIT` objections within `_OBJECTION_RATE_LIMIT_WINDOW` of `now` — a plain
    `COUNT` over `data_requests`, which is itself the durable, database-backed state this needs
    (constitution XII: no shared process between two invocations on this platform, so nothing
    module-scoped would count anything in production). Reading before writing, exactly like
    `check_and_increment`'s own contract, so a caller past the limit never gets a row recorded for
    a request this route is refusing anyway."""
    window_start = now - _OBJECTION_RATE_LIMIT_WINDOW
    recent = await db_session.execute(
        select(func.count())
        .select_from(DataRequest)
        .where(
            DataRequest.kind == DataRequestKind.THIRD_PARTY_OBJECTION,
            DataRequest.requested_at >= window_start,
        )
    )
    if recent.scalar_one() >= _OBJECTION_RATE_LIMIT:
        raise _objection_rate_limited()


@router.post("/privacy/object", status_code=202)
async def object_to_processing(
    body: ThirdPartyObjectionRequest, db_session: SessionDep
) -> dict[str, Any]:
    """FR-039: a non-user appearing in an archived match objects. Unauthenticated by design
    (module docstring) — no session is read or required. Records one `data_requests` row for a
    human to resolve later (`resolve_third_party_objection` below) and pseudonymises nothing
    itself: an endpoint that pseudonymised `body.profile_id` on this call would let anyone
    silently rewrite `match_players` for any profile they name, which is the exact
    denial-of-service surface `apps/api/tests/test_third_party_objection.py` (T088) asserts this
    route does not open.

    `data_requests.subject_profile_id` carries a foreign key into `aoe_profiles`
    (`packages/storage/.../models.py`), so `discover.touch_aoe_profile` — the identical idempotent
    upsert `apps/ingester`'s own discovery already runs the first time any match participant is
    seen — runs here first: in the ordinary case the objecting profile already has a row, from
    appearing in the match this objection is about, and this is a no-op beyond its own
    `last_seen_at` touch; for a `profile_id` this service has never itself observed, it creates
    the same placeholder row first contact would have, rather than this route rejecting or
    silently dropping an objection over a fact ingestion has simply not reached yet.
    """
    now = datetime.now(UTC)
    await _check_objection_rate_limit(db_session, now=now)

    await discover.touch_aoe_profile(db_session, body.profile_id)

    data_request = DataRequest(
        kind=DataRequestKind.THIRD_PARTY_OBJECTION,
        subject_profile_id=body.profile_id,
    )
    db_session.add(data_request)
    await db_session.flush()

    return {"id": str(data_request.id), "status": "recorded"}


async def resolve_third_party_objection(
    db_session: AsyncSession, data_request_id: uuid.UUID
) -> DataRequest:
    """FR-039's second half, carried out — the instrument `POST /api/privacy/object` above
    deliberately defers to a person rather than exercising itself (module docstring). Not a
    route: reachable only by calling this function directly, against a session of the caller's
    own (an admin shell, a one-off operational script) — never through any unauthenticated path,
    which is the exact denial-of-service vector `_check_objection_rate_limit` above and T088's
    test both exist to keep this route from being. `docs/privacy/processing-register.md`'s
    handling-procedure section names who runs it and within what delay.

    Pseudonymises the objection's own `subject_profile_id` through `_pseudonymise_profile_ids` —
    the identical instrument `POST /api/privacy/erase` (T091) already calls over a departing
    user's own linked profiles (`data-model.md`: "the same mechanism FR-039 gives third
    parties") — then marks this row resolved, which is this procedure's own trace.

    Raises `ValueError` for a `data_request_id` that does not name an unresolved third-party
    objection with a profile to act on: an operator's mistake here should fail loudly rather than
    silently no-op or resolve the wrong row.
    """
    data_request = await db_session.get(DataRequest, data_request_id)
    if data_request is None or data_request.kind is not DataRequestKind.THIRD_PARTY_OBJECTION:
        raise ValueError(f"No third-party objection request found for id {data_request_id}.")
    if data_request.subject_profile_id is None:
        raise ValueError(f"Data request {data_request_id} names no profile to pseudonymise.")
    if data_request.completed_at is not None:
        raise ValueError(f"Data request {data_request_id} was already resolved.")

    await _pseudonymise_profile_ids(db_session, [data_request.subject_profile_id])

    data_request.completed_at = datetime.now(UTC)
    data_request.outcome = f"pseudonymised profile {data_request.subject_profile_id}"
    return data_request
