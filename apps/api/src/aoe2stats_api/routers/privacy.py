"""The privacy router (T032): `POST /api/privacy/consent`.

FR-034 / FR-035, and `data-model.md`'s `users` table: `ingest_consent_at` is set once, the first
time a user grants ingestion consent, and never cleared again — clearing it would destroy the
evidence that consent was ever given, which is the opposite of what constitution IX ("GDPR by
Design") asks for. Withdrawal is a second, independent timestamp, `ingest_consent_withdrawn_at`,
recorded *on top of* the grant rather than in place of it. This is what lets a later reader tell
"never consented" apart from "consented, then withdrew" — the two are different facts and this
table is the one place that keeps them that way.

**Consent is separate from account creation, always.** Nothing about `not_allowlisted` (FR-005),
`no_aoe2_profile` (FR-003) or the rest of `auth.py`'s sign-in flow touches this table at all — a
user exists, is allowlisted and can use every other part of the account with `ingest_consent_at`
still null. Declining here (`{"granted": false}` on an account that never consented) is
consequently a no-op that still answers 200: there is nothing to withdraw, and the caller asking
"please don't" is not an error just because there was nothing being done yet.

**Granting is idempotent, not cumulative.** A second `{"granted": true}` call leaves the original
`ingest_consent_at` untouched rather than overwriting it with a later moment — the timestamp
records *when consent was first given*, and moving it forward on every repeat call would quietly
rewrite that fact each time the front end happens to re-send the same choice. The ingester reads
`ingest_consent_at IS NOT NULL AND ingest_consent_withdrawn_at IS NULL` (data-model.md: "Enforced
in the query that selects work") — regranting after a withdrawal is exactly the case that must
clear `ingest_consent_withdrawn_at` again so that query starts matching, and this handler does
that by setting `ingest_consent_withdrawn_at` back to `None` on every `granted: true` call whether
or not it was already null.

**Request body.** `contracts/http-api.md` says only "grant or withdraw", not the shape; this
module settles it as `{"granted": bool}` — `apps/api/tests/test_consent.py` (T025)'s own working
assumption, confirmed here and now recorded in the contract alongside the other routes rather than
left to live only in a test file.
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


class ConsentRequest(BaseModel):
    granted: bool


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
            message="Sign in to manage your ingestion consent.",
        )
    return session_row


# --- POST /api/privacy/consent --------------------------------------------------------------------


@router.post("/privacy/consent")
async def set_consent(
    body: ConsentRequest, request: Request, db_session: SessionDep, settings: SettingsDep
) -> dict[str, Any]:
    """FR-034: grant ingestion consent, recording when it was first given. FR-035: withdraw it,
    which stops further capture without erasing the grant timestamp (module docstring)."""
    secret = settings.app_secret_key.get_secret_value()
    session_row = _require_session(await _current_session_row(request, db_session, secret))

    user = await db_session.get(User, session_row.user_id)
    if user is None:
        raise APIError(
            status_code=401,
            code="not_authenticated",
            message="Sign in to manage your ingestion consent.",
        )

    now = datetime.now(UTC)
    if body.granted:
        # Idempotent, not cumulative (module docstring): `ingest_consent_at` is set only the first
        # time, and a regrant clears any prior withdrawal so the ingester's own selection query
        # starts matching this user again.
        if user.ingest_consent_at is None:
            user.ingest_consent_at = now
        user.ingest_consent_withdrawn_at = None
    else:
        # Withdrawing when there was never a grant is a no-op that still answers 200 (module
        # docstring): there is nothing to withdraw, so `ingest_consent_withdrawn_at` stays null.
        if user.ingest_consent_at is not None:
            user.ingest_consent_withdrawn_at = now

    return {
        "ingest_consent_at": user.ingest_consent_at.isoformat()
        if user.ingest_consent_at is not None
        else None,
        "ingest_consent_withdrawn_at": user.ingest_consent_withdrawn_at.isoformat()
        if user.ingest_consent_withdrawn_at is not None
        else None,
    }
