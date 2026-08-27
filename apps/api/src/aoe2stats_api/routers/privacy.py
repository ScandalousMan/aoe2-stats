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
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api import security
from aoe2stats_api.deps import SessionDep, SettingsDep
from aoe2stats_api.errors import APIError
from aoe2stats_storage.models import Session as SessionRow
from aoe2stats_storage.models import User

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
