"""Integration tests for `POST /api/privacy/consent` (T025) — FR-034, FR-035.

`FR-034`: consent for replay ingestion is obtained separately from account creation, and the
moment it is given is recorded. `FR-035`: a user can withdraw it later, after which no further
replays of theirs are captured. `data-model.md`'s `users` table carries both timestamps —
`ingest_consent_at` and `ingest_consent_withdrawn_at` — and its own comment on the second one
("Kept after withdrawal; erasure is a separate act") is asserted here directly: withdrawing must
never clear the grant timestamp, only add the withdrawal one.

**Written before `apps/api/src/aoe2stats_api/routers/privacy.py` exists (T032):** every test below
is `@pytest.mark.xfail(strict=True, ...)` until that router exists. Each test calls
`_require_privacy_router()` first, which imports `aoe2stats_api.routers.privacy` at test-call time
rather than at module scope — the same idiom `packages/providers/tests/test_steam.py` and
`test_relic_profile.py` (T019, T020) use for their own test-first modules, and for the identical
reason given there: a module-scope `ModuleNotFoundError` would abort the *entire* workspace suite's
collection rather than failing one test. Deferred to test-call time, the same
`ModuleNotFoundError` instead fails just that one test call, which `strict=True` xfail turns into
an expected, green result — and turns red again, forcing the marker's removal, the moment T032
makes the import succeed. This module defines the contract T032 must satisfy, not a bug to work
around; once T032 (and the session plumbing T028/T029 give it) lands, every assertion below runs
for real.

Two things this file assumes ahead of that work, because nothing today pins them down:

- **The session cookie's name.** `research.md` §3 settles on an opaque session identifier in a
  signed cookie but never names it. `SESSION_COOKIE_NAME` below is this suite's working
  assumption — chosen to mirror `sessions.id`, the column the value round-trips to — and the one
  place to change if T028 lands on something else.
- **The request body.** The contract (`contracts/http-api.md`) says only "grant or withdraw", not
  the shape. A `{"granted": bool}` body is the natural reading and is what T032 is expected to
  accept.

Because T028/T029 (sign-in, sessions) do not exist either, "signed in" here means seeded directly:
a `users` row and a `sessions` row inserted through `db_session` and committed before the request,
exactly as `conftest.py`'s docstring anticipates ("where it needs to seed or inspect rows
directly, `db_session` alongside it"). The explicit commit matters — `client`'s own requests run
through a *different* connection to the same throwaway database (`conftest.py`'s `_get_session`
override), so a row only `add()`-ed and never committed is invisible to them.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_storage.models import Session as SessionRow
from aoe2stats_storage.models import User

# Every test in this file is expected to fail for exactly one reason — T032 does not exist yet —
# until it does. `strict=True` is what makes that honest: the moment T032 lands and a test starts
# passing, `strict=True` turns the *run* red instead of letting a stale xfail hide it, which is the
# whole point of marking these tests failing rather than skipping them. Do not drop `strict=True`.
XFAIL_REASON = "POST /api/privacy/consent is implemented by T032, not this test-first task (T025)"

# Assumed pending T028 — see the module docstring.
SESSION_COOKIE_NAME = "session_id"


def _require_privacy_router() -> None:
    """Imports `aoe2stats_api.routers.privacy` at test-call time, never at module scope: this is
    where the not-yet-existent T032 module is meant to raise `ModuleNotFoundError` — inside the
    test call, where `strict=True` xfail turns it into an expected failure, not during collection,
    where it would abort the whole workspace suite.
    """
    import aoe2stats_api.routers.privacy  # noqa: F401


async def _seed_signed_in_user(
    db_session: AsyncSession, *, consented: bool = False
) -> tuple[uuid.UUID, str]:
    """Insert a `users` row (allowlisted, so nothing else about the account blocks the request)
    and a `sessions` row for it, commit, and return `(user_id, session_id)`."""
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
    return user.id, session_id


async def _reload_user(db_session: AsyncSession, user_id: uuid.UUID) -> User:
    result = await db_session.execute(select(User).where(User.id == user_id))
    return result.scalar_one()


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON)
async def test_declining_consent_leaves_the_account_usable(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-034 / US5 scenario 3: consent is a separate, explicit choice a user can decline while
    continuing to use the rest of the account. Declining must not error, must not grant consent,
    and the same session must still answer a second call afterwards — nothing about the account
    breaks or is torn down because the user said no."""
    _require_privacy_router()
    user_id, session_id = await _seed_signed_in_user(db_session)
    client.cookies.set(SESSION_COOKIE_NAME, session_id)

    first = client.post("/api/privacy/consent", json={"granted": False})
    second = client.post("/api/privacy/consent", json={"granted": False})

    assert first.status_code == 200
    assert second.status_code == 200

    stored = await _reload_user(db_session, user_id)
    assert stored.ingest_consent_at is None
    assert stored.ingest_consent_withdrawn_at is None
    assert stored.allowlisted_at is not None  # the rest of the account is untouched


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON)
async def test_granting_consent_records_ingest_consent_at(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-034: granting consent is recorded with a timestamp."""
    _require_privacy_router()
    user_id, session_id = await _seed_signed_in_user(db_session)
    client.cookies.set(SESSION_COOKIE_NAME, session_id)
    before = datetime.now(UTC)

    response = client.post("/api/privacy/consent", json={"granted": True})

    assert response.status_code == 200

    stored = await _reload_user(db_session, user_id)
    assert stored.ingest_consent_at is not None
    assert stored.ingest_consent_at >= before
    assert stored.ingest_consent_withdrawn_at is None


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON)
async def test_withdrawing_consent_sets_withdrawn_at_and_keeps_consent_at(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-035, and `data-model.md`'s comment on `ingest_consent_withdrawn_at`: withdrawal is
    recorded on top of the original grant, which is kept — erasure is a separate act, and a
    withdrawn-but-still-present `ingest_consent_at` is what lets the two be told apart later."""
    _require_privacy_router()
    user_id, session_id = await _seed_signed_in_user(db_session, consented=True)
    client.cookies.set(SESSION_COOKIE_NAME, session_id)
    before_withdrawal = datetime.now(UTC)

    response = client.post("/api/privacy/consent", json={"granted": False})

    assert response.status_code == 200

    stored = await _reload_user(db_session, user_id)
    assert stored.ingest_consent_at is not None
    assert stored.ingest_consent_withdrawn_at is not None
    assert stored.ingest_consent_withdrawn_at >= before_withdrawal


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON)
def test_consent_requires_a_signed_in_session(client: TestClient) -> None:
    """The Privacy section of `contracts/http-api.md` names exactly one unauthenticated route,
    `/api/privacy/object`, precisely because objecting is by definition not something a user does
    — everything else in that section, `/api/privacy/consent` included, is behind the session
    cookie like the rest of the API. An anonymous caller must not be able to grant or withdraw
    consent for anyone."""
    _require_privacy_router()
    response = client.post("/api/privacy/consent", json={"granted": True})

    assert response.status_code == 401
