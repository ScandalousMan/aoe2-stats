"""Integration tests for `POST /api/privacy/consent` (T025/T032) — FR-034, FR-035.

`FR-034`: consent for replay ingestion is obtained separately from account creation, and the
moment it is given is recorded. `FR-035`: a user can withdraw it later, after which no further
replays of theirs are captured. `data-model.md`'s `users` table carries both timestamps —
`ingest_consent_at` and `ingest_consent_withdrawn_at` — and its own comment on the second one
("Kept after withdrawal; erasure is a separate act") is asserted here directly: withdrawing must
never clear the grant timestamp, only add the withdrawal one.

**T032 has implemented `aoe2stats_api.routers.privacy`.** This file was written test-first
(T025), with every test `@pytest.mark.xfail(strict=True, ...)` until that router existed; those
markers are gone now that it does, and every assertion below runs for real against it.

Two things this file assumed ahead of that work, now settled:

- **The session cookie's name** is `session_id` (`security.SESSION_COOKIE_NAME`, T028) — the
  `SESSION_COOKIE_NAME` constant below matches it.
- **The request body** is `{"granted": bool}`, confirmed by T032 and recorded in
  `contracts/http-api.md` alongside the other `/api/privacy/*` routes, not left living only here.

"Signed in" here means seeded directly: a `users` row and a `sessions` row inserted through
`db_session` and committed before the request, exactly as `conftest.py`'s docstring anticipates
("where it needs to seed or inspect rows directly, `db_session` alongside it"). The explicit
commit matters — `client`'s own requests run through a *different* connection to the same
throwaway database (`conftest.py`'s `_get_session` override), so a row only `add()`-ed and never
committed is invisible to them.

**`pytestmark` below (T032).** `client` (conftest.py) builds `create_app()`, and every route
resolves `SettingsDep` through `get_settings()`, which requires the full 18-key environment every
sibling integration-test module that drives `client` against a real router already requests the
same way (`test_unlink.py`, `test_multi_account.py`). Without it every request in this file would
fail on `Settings` validation before ever reaching `privacy.py`, regardless of what T032
implemented — a gap in this file's own fixtures, not part of the contract it specifies, so it is
corrected here rather than worked around.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api import security
from aoe2stats_api.settings import get_settings
from aoe2stats_storage.models import Session as SessionRow
from aoe2stats_storage.models import User

pytestmark = [pytest.mark.usefixtures("environment")]

SESSION_COOKIE_NAME = "session_id"


async def _seed_signed_in_user(
    client: TestClient, db_session: AsyncSession, *, consented: bool = False
) -> uuid.UUID:
    """Insert a `users` row (allowlisted, so nothing else about the account blocks the request)
    and a `sessions` row for it, commit, and hand `client` its cookie — signed exactly as
    `security.issue_session_cookie` signs a real one (`<sessions.id>.<hmac-sha256 signature>`,
    `security.py`): `security.read_session_id` rejects anything else before a query is ever
    issued, which an unsigned raw `session_id` — this helper's original form — always was. The
    same fix `test_unlink.py`'s `_sign_in` already applies for the identical reason."""
    now = datetime.now(UTC)
    user = User(
        id=uuid.uuid4(),
        created_at=now,
        allowlisted_at=now,
        ingest_consent_at=now if consented else None,
    )
    db_session.add(user)
    await db_session.flush()

    session_id = secrets.token_urlsafe(32)
    db_session.add(
        SessionRow(
            id=session_id,
            user_id=user.id,
            created_at=now,
            expires_at=now + timedelta(days=1),
        )
    )
    await db_session.commit()

    secret = get_settings().app_secret_key.get_secret_value()
    client.cookies.set(SESSION_COOKIE_NAME, security._sign(session_id, secret))
    return user.id


async def _reload_user(db_session: AsyncSession, user_id: uuid.UUID) -> User:
    result = await db_session.execute(select(User).where(User.id == user_id))
    return result.scalar_one()


async def test_declining_consent_leaves_the_account_usable(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-034 / US5 scenario 3: consent is a separate, explicit choice a user can decline while
    continuing to use the rest of the account. Declining must not error, must not grant consent,
    and the same session must still answer a second call afterwards — nothing about the account
    breaks or is torn down because the user said no."""
    user_id = await _seed_signed_in_user(client, db_session)

    first = client.post("/api/privacy/consent", json={"granted": False})
    second = client.post("/api/privacy/consent", json={"granted": False})

    assert first.status_code == 200
    assert second.status_code == 200

    stored = await _reload_user(db_session, user_id)
    assert stored.ingest_consent_at is None
    assert stored.ingest_consent_withdrawn_at is None
    assert stored.allowlisted_at is not None  # the rest of the account is untouched


async def test_granting_consent_records_ingest_consent_at(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-034: granting consent is recorded with a timestamp."""
    user_id = await _seed_signed_in_user(client, db_session)
    before = datetime.now(UTC)

    response = client.post("/api/privacy/consent", json={"granted": True})

    assert response.status_code == 200

    stored = await _reload_user(db_session, user_id)
    assert stored.ingest_consent_at is not None
    assert stored.ingest_consent_at >= before
    assert stored.ingest_consent_withdrawn_at is None


async def test_withdrawing_consent_sets_withdrawn_at_and_keeps_consent_at(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-035, and `data-model.md`'s comment on `ingest_consent_withdrawn_at`: withdrawal is
    recorded on top of the original grant, which is kept — erasure is a separate act, and a
    withdrawn-but-still-present `ingest_consent_at` is what lets the two be told apart later."""
    user_id = await _seed_signed_in_user(client, db_session, consented=True)
    before_withdrawal = datetime.now(UTC)

    response = client.post("/api/privacy/consent", json={"granted": False})

    assert response.status_code == 200

    stored = await _reload_user(db_session, user_id)
    assert stored.ingest_consent_at is not None
    assert stored.ingest_consent_withdrawn_at is not None
    assert stored.ingest_consent_withdrawn_at >= before_withdrawal


def test_consent_requires_a_signed_in_session(client: TestClient) -> None:
    """The Privacy section of `contracts/http-api.md` names exactly one unauthenticated route,
    `/api/privacy/object`, precisely because objecting is by definition not something a user does
    — everything else in that section, `/api/privacy/consent` included, is behind the session
    cookie like the rest of the API. An anonymous caller must not be able to grant or withdraw
    consent for anyone."""
    response = client.post("/api/privacy/consent", json={"granted": True})

    assert response.status_code == 401
