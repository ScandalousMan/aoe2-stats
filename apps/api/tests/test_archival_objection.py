"""Integration tests for `POST /api/privacy/archival-objection` (T025/T032, renamed by T405) —
FR-034, FR-035.

Constitution IX 4.0.0 retired the opt-in consent gate: archival now rests on legitimate interest
(GDPR Art. 6-1-f) and is **on by default**, so `FR-034` no longer names a grant to obtain. What
`FR-035` still gives a user is the Art. 21 right to object — this route records when that objection
was made, and lets it be withdrawn again to resume archival. `data-model.md`'s `users` table now
carries a single nullable `archival_objected_at`: `null` means archiving, whether because the user
has never answered any question or because they objected and later resumed; set means the user has
exercised the right to object, as of that moment.

**T405 renamed and inverted `POST /api/privacy/consent` into this route.** This file was
`test_consent.py`, asserting the retired two-timestamp grant/withdrawal scheme
(`ingest_consent_at`/`ingest_consent_withdrawn_at`); it is rewritten here against the inverted
default rather than left to ratify a rule the amendment removed.

Two things this file assumed ahead of T032's work, still true:

- **The session cookie's name** is `session_id` (`security.SESSION_COOKIE_NAME`, T028) — the
  `SESSION_COOKIE_NAME` constant below matches it.
- **The request body** is `{"objected": bool}` (T405), confirmed here and recorded in
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
    client: TestClient, db_session: AsyncSession, *, objected: bool = False
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
        archival_objected_at=now if objected else None,
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


async def test_a_user_who_has_answered_nothing_is_reported_as_not_objected(
    client: TestClient, db_session: AsyncSession
) -> None:
    """Constitution IX 4.0.0: archival is on by default. A user who has never called this route at
    all — no grant to give any more, nothing to answer — is reported as `archival_objected: false`
    both directly on the account and through `GET /api/me`, not `null` and not "unknown"."""
    user_id = await _seed_signed_in_user(client, db_session)

    stored = await _reload_user(db_session, user_id)
    assert stored.archival_objected_at is None

    me = client.get("/api/me")
    assert me.status_code == 200
    body = me.json()
    assert body["archival_objected"] is False
    assert body["archival_objected_at"] is None


async def test_objecting_records_archival_objected_at(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-035: objecting is recorded with a timestamp."""
    user_id = await _seed_signed_in_user(client, db_session)
    before = datetime.now(UTC)

    response = client.post("/api/privacy/archival-objection", json={"objected": True})

    assert response.status_code == 200
    body = response.json()
    assert body["archival_objected"] is True
    assert body["archival_objected_at"] is not None

    stored = await _reload_user(db_session, user_id)
    assert stored.archival_objected_at is not None
    assert stored.archival_objected_at >= before


async def test_objecting_twice_leaves_the_original_timestamp_untouched(
    client: TestClient, db_session: AsyncSession
) -> None:
    """Idempotent, not cumulative (module docstring): a second `{"objected": true}` call must not
    move `archival_objected_at` forward to a later moment — it records *when the objection was
    first made*."""
    user_id = await _seed_signed_in_user(client, db_session)

    first = client.post("/api/privacy/archival-objection", json={"objected": True})
    assert first.status_code == 200
    first_timestamp = (await _reload_user(db_session, user_id)).archival_objected_at
    assert first_timestamp is not None

    second = client.post("/api/privacy/archival-objection", json={"objected": True})
    assert second.status_code == 200

    stored = await _reload_user(db_session, user_id)
    assert stored.archival_objected_at == first_timestamp


async def test_resuming_clears_archival_objected_at_and_leaves_the_account_usable(
    client: TestClient, db_session: AsyncSession
) -> None:
    """A user who objected can change their mind (T406's "archiving, explicitly resumed" state):
    `{"objected": false}` clears the timestamp back to `null`, which is what resumes archival for
    the ingester's own gate (`archival_objected_at IS NULL`). The rest of the account is
    untouched."""
    user_id = await _seed_signed_in_user(client, db_session, objected=True)

    response = client.post("/api/privacy/archival-objection", json={"objected": False})

    assert response.status_code == 200
    body = response.json()
    assert body["archival_objected"] is False
    assert body["archival_objected_at"] is None

    stored = await _reload_user(db_session, user_id)
    assert stored.archival_objected_at is None
    assert stored.allowlisted_at is not None  # the rest of the account is untouched


async def test_resuming_with_no_prior_objection_is_a_no_op_not_an_error(
    client: TestClient, db_session: AsyncSession
) -> None:
    """`{"objected": false}` on an account that never objected in the first place — nothing to
    clear, and the caller asking "please resume" is not an error just because archival never
    stopped (module docstring)."""
    user_id = await _seed_signed_in_user(client, db_session)

    response = client.post("/api/privacy/archival-objection", json={"objected": False})

    assert response.status_code == 200
    stored = await _reload_user(db_session, user_id)
    assert stored.archival_objected_at is None
    assert stored.allowlisted_at is not None


async def test_objection_is_reported_on_a_subsequent_get_me(
    client: TestClient, db_session: AsyncSession
) -> None:
    """Exactly the scenario a page reload performs: `GET /api/me` must reflect an objection made
    through this route on the very next request, not stay "archiving" until told otherwise by some
    other means."""
    await _seed_signed_in_user(client, db_session)

    before_objection = client.get("/api/me")
    assert before_objection.status_code == 200
    assert before_objection.json()["archival_objected"] is False

    objection = client.post("/api/privacy/archival-objection", json={"objected": True})
    assert objection.status_code == 200

    after_objection = client.get("/api/me")
    assert after_objection.status_code == 200
    body = after_objection.json()
    assert body["archival_objected"] is True
    assert body["archival_objected_at"] is not None

    resume = client.post("/api/privacy/archival-objection", json={"objected": False})
    assert resume.status_code == 200

    after_resume = client.get("/api/me")
    assert after_resume.status_code == 200
    resumed_body = after_resume.json()
    assert resumed_body["archival_objected"] is False
    assert resumed_body["archival_objected_at"] is None


def test_archival_objection_requires_a_signed_in_session(client: TestClient) -> None:
    """The Privacy section of `contracts/http-api.md` names exactly one unauthenticated route,
    `/api/privacy/object`, precisely because objecting *on behalf of a third party* is by
    definition not something a user does — everything else in that section,
    `/api/privacy/archival-objection` included, is behind the session cookie like the rest of the
    API. An anonymous caller must not be able to object or resume archival for anyone."""
    response = client.post("/api/privacy/archival-objection", json={"objected": True})

    assert response.status_code == 401


def test_the_retired_consent_route_no_longer_exists(client: TestClient) -> None:
    """T405: this is a rename with an inverted meaning, not a new route beside the old one.
    `POST /api/privacy/consent` must not be reachable — the two-timestamp state it used to write
    into (`ingest_consent_at`/`ingest_consent_withdrawn_at`) no longer exists on `users`, so a
    caller reaching this path would otherwise be asking the API to place a user in a state the
    data model no longer has."""
    response = client.post("/api/privacy/consent", json={"granted": True})

    assert response.status_code == 404
