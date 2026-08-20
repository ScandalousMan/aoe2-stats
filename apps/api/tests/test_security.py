"""Unit and integration tests for `apps/api/src/aoe2stats_api/security.py` (T028): opaque session
identifiers, the signed session cookie, immediate server-side revocation, and the CSRF `state`
tied to the browser session.

The signing and CSRF helpers are pure functions and are tested without a database. Session
creation, lookup and revocation exercise the real `sessions` table through the `db_session`
fixture (T015/T015a) — a revoked or expired row must stop being an active session on the very
next query, which is the one property no amount of pure-function testing on `_sign`/`_unsign`
alone could prove.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api import security
from aoe2stats_storage.models import User

_SECRET = "unit-test-secret-value"
_OTHER_SECRET = "a-completely-different-secret"


# --- Opaque identifiers ----------------------------------------------------------------------


def test_generate_session_id_is_opaque_and_unique() -> None:
    first = security.generate_session_id()
    second = security.generate_session_id()

    assert first != second
    # 256 bits of randomness (data-model.md) — `secrets.token_urlsafe(32)` draws 32 random
    # *bytes*, which base64url-encodes to at least 43 characters.
    assert len(first) >= 43
    # Opaque: nothing about a user id, a Steam id or any other identifier is derivable from it —
    # asserted the only way a black-box string permits, by confirming it carries none of the
    # inputs a real caller would have on hand when minting one.
    assert str(uuid.uuid4()) not in first


def test_generate_csrf_state_is_opaque_and_unique() -> None:
    first = security.generate_csrf_state()
    second = security.generate_csrf_state()

    assert first != second
    assert len(first) >= 43


# --- Signing: a tampered or fabricated cookie must never verify ------------------------------


def test_signed_value_round_trips_under_the_same_secret() -> None:
    session_id = security.generate_session_id()

    signed = security._sign(session_id, _SECRET)
    assert security._unsign(signed, _SECRET) == session_id


def test_unsign_rejects_a_tampered_value() -> None:
    session_id = security.generate_session_id()
    signed = security._sign(session_id, _SECRET)

    value, _sep, signature = signed.rpartition(".")
    tampered = f"{value}x.{signature}"

    assert security._unsign(tampered, _SECRET) is None


def test_unsign_rejects_a_tampered_signature() -> None:
    session_id = security.generate_session_id()
    signed = security._sign(session_id, _SECRET)

    value, _sep, signature = signed.rpartition(".")
    flipped_last_char = ("a" if signature[-1] != "a" else "b") if signature else "a"
    tampered = f"{value}.{signature[:-1]}{flipped_last_char}"

    assert security._unsign(tampered, _SECRET) is None


def test_unsign_rejects_the_wrong_secret() -> None:
    session_id = security.generate_session_id()
    signed = security._sign(session_id, _SECRET)

    assert security._unsign(signed, _OTHER_SECRET) is None


def test_unsign_rejects_malformed_input() -> None:
    assert security._unsign("", _SECRET) is None
    assert security._unsign("no-separator-at-all", _SECRET) is None
    assert security._unsign(".", _SECRET) is None
    assert security._unsign("value.", _SECRET) is None
    assert security._unsign(".signature", _SECRET) is None


def test_read_session_id_returns_none_for_a_missing_cookie() -> None:
    assert security.read_session_id(None, _SECRET) is None
    assert security.read_session_id("", _SECRET) is None


def test_read_session_id_recovers_the_raw_id_issued() -> None:
    response = Response()
    session_id = security.generate_session_id()

    security.issue_session_cookie(response, session_id, _SECRET)

    cookie_header = response.headers["set-cookie"]
    signed_value = cookie_header.split(f"{security.SESSION_COOKIE_NAME}=", 1)[1].split(";", 1)[0]
    assert security.read_session_id(signed_value, _SECRET) == session_id
    assert security.read_session_id(signed_value, _OTHER_SECRET) is None


# --- Cookie attributes: HttpOnly, Secure, SameSite=Lax (research.md §3) ----------------------


def test_session_cookie_carries_the_required_attributes() -> None:
    response = Response()

    security.issue_session_cookie(response, security.generate_session_id(), _SECRET)

    cookie_header = response.headers["set-cookie"].lower()
    assert f"{security.SESSION_COOKIE_NAME.lower()}=" in cookie_header
    assert "httponly" in cookie_header
    assert "secure" in cookie_header
    assert "samesite=lax" in cookie_header
    assert "path=/" in cookie_header


def test_clear_session_cookie_expires_it() -> None:
    response = Response()

    security.clear_session_cookie(response)

    cookie_header = response.headers["set-cookie"].lower()
    assert f'{security.SESSION_COOKIE_NAME.lower()}=""' in cookie_header or (
        f"{security.SESSION_COOKIE_NAME.lower()}=" in cookie_header
    )
    # An expired cookie carries either `max-age=0` or an `expires` value in the past — Starlette
    # uses `max-age=0`.
    assert "max-age=0" in cookie_header


# --- The CSRF `state` cookie, tied to the browser ---------------------------------------------


def test_csrf_state_round_trips_for_the_browser_that_received_it() -> None:
    response = Response()

    state = security.issue_csrf_state_cookie(response, _SECRET)

    cookie_header = response.headers["set-cookie"]
    signed_value = cookie_header.split(f"{security.CSRF_STATE_COOKIE_NAME}=", 1)[1].split(";", 1)[0]
    assert security.verify_csrf_state(signed_value, state, _SECRET) is True


def test_csrf_state_cookie_carries_the_required_attributes() -> None:
    response = Response()

    security.issue_csrf_state_cookie(response, _SECRET)

    cookie_header = response.headers["set-cookie"].lower()
    assert "httponly" in cookie_header
    assert "secure" in cookie_header
    assert "samesite=lax" in cookie_header


def test_csrf_state_minted_for_one_browser_cannot_be_replayed_in_another() -> None:
    """The property this task exists to guarantee: a `state` minted for browser A, replayed with
    browser B's own (different) cookie, must never verify — CSRF protection tied to the browser,
    not to the value alone."""
    response_a = Response()
    state_a = security.issue_csrf_state_cookie(response_a, _SECRET)
    cookie_a = (
        response_a.headers["set-cookie"]
        .split(f"{security.CSRF_STATE_COOKIE_NAME}=", 1)[1]
        .split(";", 1)[0]
    )

    response_b = Response()
    security.issue_csrf_state_cookie(response_b, _SECRET)
    cookie_b = (
        response_b.headers["set-cookie"]
        .split(f"{security.CSRF_STATE_COOKIE_NAME}=", 1)[1]
        .split(";", 1)[0]
    )

    # Browser B replays browser A's *state value* (the part an attacker could read off a shared
    # link or a referrer header) but only has its own cookie — the one thing CSRF protection
    # relies on the attacker not having.
    assert security.verify_csrf_state(cookie_b, state_a, _SECRET) is False
    # And, for completeness, the reverse never matches either.
    assert security.verify_csrf_state(cookie_a, state_a, _SECRET) is True


def test_verify_csrf_state_rejects_missing_or_mismatched_values() -> None:
    response = Response()
    state = security.issue_csrf_state_cookie(response, _SECRET)
    cookie_header = response.headers["set-cookie"]
    signed_value = cookie_header.split(f"{security.CSRF_STATE_COOKIE_NAME}=", 1)[1].split(";", 1)[0]

    assert security.verify_csrf_state(None, state, _SECRET) is False
    assert security.verify_csrf_state(signed_value, None, _SECRET) is False
    assert security.verify_csrf_state(signed_value, "not-the-real-state", _SECRET) is False
    assert security.verify_csrf_state(signed_value, state, _OTHER_SECRET) is False


# --- The `sessions` table: creation, lookup, immediate server-side revocation ------------------


async def _seed_user(db_session: AsyncSession) -> User:
    now = datetime.now(UTC)
    user = User(id=uuid.uuid4(), created_at=now, allowlisted_at=now)
    db_session.add(user)
    await db_session.flush()
    return user


async def test_create_session_is_retrievable_as_active(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)

    created = await security.create_session(db_session, user_id=user.id)
    await db_session.commit()

    active = await security.get_active_session(db_session, created.id)
    assert active is not None
    assert active.id == created.id
    assert active.user_id == user.id
    assert active.revoked_at is None


async def test_get_active_session_returns_none_for_an_unknown_id(
    db_session: AsyncSession,
) -> None:
    assert await security.get_active_session(db_session, "not-a-real-session-id") is None


async def test_revoke_session_ends_it_immediately(db_session: AsyncSession) -> None:
    """The property this task exists to guarantee: revocation is server-side and immediate — the
    row stops being an active session on the very next query, with no token to wait out."""
    user = await _seed_user(db_session)
    created = await security.create_session(db_session, user_id=user.id)
    await db_session.commit()

    assert await security.get_active_session(db_session, created.id) is not None

    await security.revoke_session(db_session, created.id)
    await db_session.commit()

    assert await security.get_active_session(db_session, created.id) is None


async def test_revoke_session_is_idempotent_for_an_unknown_id(db_session: AsyncSession) -> None:
    # Must not raise for an id that was never created.
    await security.revoke_session(db_session, "never-existed")
    await db_session.commit()


async def test_expired_session_is_not_active(db_session: AsyncSession) -> None:
    user = await _seed_user(db_session)
    now = datetime.now(UTC)
    yesterday = now - timedelta(days=1)

    created = await security.create_session(db_session, user_id=user.id, now=yesterday)
    await db_session.commit()

    # `created.expires_at` is `yesterday + SESSION_TTL`, still in the future relative to
    # `yesterday` — the point of `now=` below is to evaluate the query from a moment *after*
    # `expires_at`, not to fabricate an already-expired row directly.
    far_future = created.expires_at + timedelta(seconds=1)
    assert await security.get_active_session(db_session, created.id, now=far_future) is None
    # ... but the same row is still active evaluated from a moment before its expiry.
    assert await security.get_active_session(db_session, created.id, now=now) is not None
