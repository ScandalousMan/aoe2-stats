"""Integration tests for `GET /api/replays/status?profile_id=` (T062) — `contracts/http-api.md`'s
"Counts per status, oldest pending, nearest deadline".

Follows `test_unlink.py`'s harness conventions: `client`/`db_session` against the real throwaway
database (`conftest.py`), a `sessions` row inserted directly and signed exactly as
`security.issue_session_cookie` would (there is no reason to route through the auth flow just to
prove a session exists), and `pytestmark`'s `environment` fixture for the full 18-key settings
surface every router built on `SettingsDep` requires.

Covers three things the task asks for:

- the happy path with a mix of every `CaptureStatus` value, asserting the zero-filled counts and
  that `oldest_pending` (`first_seen_at` order) and `nearest_deadline` (`capture_deadline_at`
  order) can name *different* rows — the module docstring's reasoning for why the two are computed
  separately rather than assumed to coincide;
- a profile with no captures at all, where both fields must be `null` rather than absent or an
  error;
- FR-045's "one error, indistinguishable causes": no session, an unknown `profile_id`, a
  `profile_id` linked to a different account, and a `profile_id` this account itself unlinked all
  answer with a single stable shape (401 for the first, the identical 404 `not_found` for the other
  three) — never a 403 that would leak which of the three applies.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api import security
from aoe2stats_api.settings import get_settings
from aoe2stats_storage.models import (
    AoeProfile,
    CaptureSource,
    CaptureStatus,
    Match,
    ProfileLink,
    ReplayCapture,
    SteamIdentity,
    User,
)
from aoe2stats_storage.models import Session as UserSession

pytestmark = [pytest.mark.usefixtures("environment")]

#: See `test_unlink.py`'s module docstring, point 1 — this suite's working assumption, not yet
#: fixed by a contract document beyond T028's own implementation.
SESSION_COOKIE_NAME = "session_id"

_PROFILE_ID = 555111222


async def _seed_linked_profile(
    db_session: AsyncSession,
    *,
    profile_id: int = _PROFILE_ID,
    steam_id64: str = "76561197960287930",
) -> User:
    """A user with one verified Steam identity and one active `profile_links` row for
    `profile_id` — the ownership `_owned_active_link` (`replays.py`) must accept."""
    now = datetime.now(UTC)
    user = User(allowlisted_at=now, ingest_consent_at=now)
    db_session.add(user)
    await db_session.flush()

    db_session.add(
        SteamIdentity(steam_id64=steam_id64, user_id=user.id, verified_at=now, last_sign_in_at=now)
    )
    db_session.add(AoeProfile(profile_id=profile_id, alias="TestPlayer", country="FR"))
    await db_session.flush()

    db_session.add(
        ProfileLink(
            user_id=user.id,
            profile_id=profile_id,
            steam_id64=steam_id64,
            is_primary=True,
            linked_at=now,
        )
    )
    await db_session.commit()
    return user


async def _sign_in(client: TestClient, db_session: AsyncSession, user: User) -> None:
    """Insert a `sessions` row directly and hand the client its signed cookie — mirrors
    `test_unlink.py`'s and `test_consent.py`'s own `_sign_in`/`_seed_signed_in_user` helper."""
    session_id = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    db_session.add(
        UserSession(
            id=session_id,
            user_id=user.id,
            created_at=now,
            expires_at=now + timedelta(days=30),
        )
    )
    await db_session.commit()
    secret = get_settings().app_secret_key.get_secret_value()
    client.cookies.set(SESSION_COOKIE_NAME, security._sign(session_id, secret))


async def _seed_match(db_session: AsyncSession, *, game_id: int, completed_at: datetime) -> None:
    db_session.add(
        Match(
            game_id=game_id,
            leaderboard_id=3,
            completed_at=completed_at,
            source="relic",
            raw_payload={},
        )
    )


async def _seed_capture(
    db_session: AsyncSession,
    *,
    game_id: int,
    profile_id: int,
    status: CaptureStatus,
    capture_deadline_at: datetime,
    first_seen_at: datetime,
    **extra: object,
) -> None:
    db_session.add(
        ReplayCapture(
            game_id=game_id,
            profile_id=profile_id,
            status=status,
            capture_deadline_at=capture_deadline_at,
            first_seen_at=first_seen_at,
            source=CaptureSource.AUTOMATIC,
            **extra,
        )
    )


async def test_replay_status_requires_authentication(client: TestClient) -> None:
    """No session cookie at all: 401, never a leak of whether `profile_id` exists."""
    response = client.get(f"/api/replays/status?profile_id={_PROFILE_ID}")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


async def test_replay_status_unknown_profile_returns_not_found(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-045, case 1: a `profile_id` that names no link at all."""
    user = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)

    response = client.get(f"/api/replays/status?profile_id={_PROFILE_ID + 999}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_replay_status_other_users_profile_returns_the_identical_not_found(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-045, case 2: a `profile_id` that is actively linked, but to a different account, must
    answer the same 404 as an unknown one — never a 403 that confirms the profile exists."""
    _owner = await _seed_linked_profile(db_session, profile_id=_PROFILE_ID)
    other_user = User(allowlisted_at=datetime.now(UTC), ingest_consent_at=datetime.now(UTC))
    db_session.add(other_user)
    await db_session.commit()
    await _sign_in(client, db_session, other_user)

    response = client.get(f"/api/replays/status?profile_id={_PROFILE_ID}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_replay_status_unlinked_profile_returns_the_identical_not_found(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-045, case 3: a `profile_id` this very account once linked and then unlinked must also
    answer 404, not a stale success — `unlinked_at` is what `_owned_active_link` filters on."""
    user = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)
    unlink_response = client.delete(f"/api/profiles/{_PROFILE_ID}?confirm=true")
    assert unlink_response.status_code == 200

    response = client.get(f"/api/replays/status?profile_id={_PROFILE_ID}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_replay_status_profile_with_no_captures(
    client: TestClient, db_session: AsyncSession
) -> None:
    """An empty backlog: every count is 0, and both `oldest_pending` and `nearest_deadline` are
    `null` rather than absent or an error."""
    user = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)

    response = client.get(f"/api/replays/status?profile_id={_PROFILE_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["counts"] == {status.value: 0 for status in CaptureStatus}
    assert body["oldest_pending"] is None
    assert body["nearest_deadline"] is None


async def test_replay_status_happy_path_mix_of_statuses(
    client: TestClient, db_session: AsyncSession
) -> None:
    """One capture per status, plus a second `pending` one, so that `oldest_pending`
    (`first_seen_at` order) and `nearest_deadline` (`capture_deadline_at` order) can be shown to
    name two *different* rows — the module docstring's reasoning for computing them separately."""
    user = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)
    now = datetime.now(UTC)

    # A pending capture discovered first but with a *later* deadline (an old-ish match found
    # early) — this is `oldest_pending`.
    older_seen_game_id = 1001
    await _seed_match(db_session, game_id=older_seen_game_id, completed_at=now - timedelta(days=5))
    await _seed_capture(
        db_session,
        game_id=older_seen_game_id,
        profile_id=_PROFILE_ID,
        status=CaptureStatus.PENDING,
        capture_deadline_at=now + timedelta(days=16),
        first_seen_at=now - timedelta(days=5),
    )

    # A pending capture discovered later but with a *nearer* deadline (a backfilled older match
    # discovered recently) — this is `nearest_deadline`.
    nearer_deadline_game_id = 1002
    await _seed_match(
        db_session, game_id=nearer_deadline_game_id, completed_at=now - timedelta(days=20)
    )
    await _seed_capture(
        db_session,
        game_id=nearer_deadline_game_id,
        profile_id=_PROFILE_ID,
        status=CaptureStatus.PENDING,
        capture_deadline_at=now + timedelta(days=1),
        first_seen_at=now - timedelta(days=1),
    )

    other_statuses = {
        CaptureStatus.DOWNLOADING: 1003,
        CaptureStatus.STORED: 1004,
        CaptureStatus.UNAVAILABLE: 1005,
        CaptureStatus.EXPIRED: 1006,
        CaptureStatus.QUARANTINED: 1007,
        CaptureStatus.FAILED: 1008,
    }
    for status, game_id in other_statuses.items():
        await _seed_match(db_session, game_id=game_id, completed_at=now - timedelta(days=10))
        await _seed_capture(
            db_session,
            game_id=game_id,
            profile_id=_PROFILE_ID,
            status=status,
            capture_deadline_at=now + timedelta(days=11),
            first_seen_at=now - timedelta(days=10),
        )
    await db_session.commit()

    response = client.get(f"/api/replays/status?profile_id={_PROFILE_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["counts"] == {
        "pending": 2,
        "downloading": 1,
        "stored": 1,
        "unavailable": 1,
        "expired": 1,
        "quarantined": 1,
        "failed": 1,
    }
    assert body["oldest_pending"]["game_id"] == older_seen_game_id
    assert body["nearest_deadline"]["game_id"] == nearer_deadline_game_id
    assert body["nearest_deadline"].get("first_seen_at") is None, (
        "nearest_deadline answers the deadline question, not the discovery one"
    )


async def test_replay_status_requires_profile_id_query_param(client: TestClient) -> None:
    """`profile_id` is a required query parameter: FastAPI's own validation envelope answers a
    missing one, before any session or ownership check runs."""
    response = client.get("/api/replays/status")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
