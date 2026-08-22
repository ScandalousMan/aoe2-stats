"""Integration test for `GET /api/replays/{game_id}/download` (T066), implemented at T071 —
`contracts/http-api.md`: "302 to a short-lived signed URL. Writes `replay_access_log` (FR-040)",
and "The bucket is never public. A download is always a freshly signed URL with a short expiry,
because a replay contains other players' gameplay and chat."

**Test-first (CLAUDE.md "Test-first tasks and the green-tree gate")**: T071 does not exist yet, so
every assertion below is written as if it did and is expected to fail today — `pytest.mark.xfail
(strict=True)` keeps the suite green until T071 lands and turns the marker off by making the test
pass. Nothing imported here is missing at module scope (the models, the router module and its
`GET /api/replays/status` sibling all already exist from T007/T062); only the download *route*
itself is absent, so no deferred import is needed — the redness comes from behaviour, not from a
collection error.

Follows `test_replay_status.py`'s harness conventions verbatim: `client`/`db_session` against the
real throwaway database (`conftest.py`), a `sessions` row inserted directly and signed exactly as
`security.issue_session_cookie` would, and `pytestmark`'s `environment` fixture for the full
18-key settings surface every router built on `SettingsDep` requires.

**Never a public bucket, proven rather than assumed.** `conftest.py`'s shared `_FakeObjectStore`
now carries a `signed_get_url` that deterministically encodes `key` and `expires_in` into the
returned string (T066): the redirect target can only carry that shape if the router asked the
object store to sign it, never if it built a bucket URL by hand. A raw `{endpoint}/{bucket}/{key}`
would not match `_FAKE_SIGNED_PREFIX` and would fail every assertion below.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api import security
from aoe2stats_api.settings import get_settings
from aoe2stats_storage.models import (
    AoeProfile,
    CaptureSource,
    CaptureStatus,
    Match,
    ProfileLink,
    ReplayAccessLog,
    ReplayCapture,
    SteamIdentity,
    User,
)
from aoe2stats_storage.models import Session as UserSession

pytestmark = [
    pytest.mark.usefixtures("environment"),
    pytest.mark.xfail(strict=True, reason="T071 not implemented yet"),
]

#: See `test_replay_status.py`'s module docstring — this suite's working assumption, not yet fixed
#: by a contract document beyond T028's own implementation.
SESSION_COOKIE_NAME = "session_id"

#: Must match `conftest.py`'s `_FakeObjectStore.signed_get_url` exactly (T066) — a hand-built
#: bucket URL from the router itself would never produce this prefix, which is the whole point.
_FAKE_SIGNED_PREFIX = "https://fake-object-store.example/signed/"

#: A short-lived signed URL, per `contracts/http-api.md`. `packages/storage/tests/test_objects.py`
#: fixes the same ceiling for `ObjectStore.signed_get_url`'s own default.
_MAX_SIGNED_URL_EXPIRES_IN_SECONDS = 900

_OWNER_PROFILE_ID = 555111333
_OTHER_PROFILE_ID = 555111444
_GAME_ID = 9001


async def _seed_linked_profile(
    db_session: AsyncSession,
    *,
    profile_id: int,
    steam_id64: str,
) -> User:
    """A user with one verified Steam identity and one active `profile_links` row for
    `profile_id` — mirrors `test_replay_status.py`'s helper of the same name."""
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
    `test_replay_status.py`'s own `_sign_in`."""
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


async def _seed_stored_capture(
    db_session: AsyncSession,
    *,
    game_id: int = _GAME_ID,
    profile_id: int,
    object_key: str,
) -> ReplayCapture:
    """A match with one already-archived (`stored`) capture from `profile_id`'s point of view —
    the only state a download can meaningfully serve."""
    now = datetime.now(UTC)
    db_session.add(
        Match(
            game_id=game_id,
            leaderboard_id=3,
            completed_at=now - timedelta(days=2),
            source="relic",
            raw_payload={},
        )
    )
    capture = ReplayCapture(
        game_id=game_id,
        profile_id=profile_id,
        status=CaptureStatus.STORED,
        capture_deadline_at=now + timedelta(days=19),
        first_seen_at=now - timedelta(days=2),
        stored_at=now - timedelta(days=1),
        object_key=object_key,
        zip_bytes=1024,
        zip_sha256="a" * 64,
        inner_filename="replay.aoe2record",
        inner_bytes=2048,
        source=CaptureSource.AUTOMATIC,
    )
    db_session.add(capture)
    await db_session.commit()
    await db_session.refresh(capture)
    return capture


def _decode_signed_url(location: str) -> tuple[str, int]:
    """The `(key, expires_in)` pair `_FakeObjectStore.signed_get_url` encoded into `location`."""
    assert location.startswith(_FAKE_SIGNED_PREFIX), (
        "the redirect must go through ObjectStore.signed_get_url, never a hand-built bucket URL "
        f"(bucket never public): got {location!r}"
    )
    remainder = location[len(_FAKE_SIGNED_PREFIX) :]
    split = urlsplit(f"//host/{remainder}")
    key = split.path.removeprefix("/")
    query = parse_qs(split.query)
    expires_in = int(query["expires_in"][0])
    return key, expires_in


async def test_replay_download_requires_authentication(client: TestClient) -> None:
    """No session cookie at all: 401, never a redirect to anything."""
    response = client.get(f"/api/replays/{_GAME_ID}/download", follow_redirects=False)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


async def test_replay_download_redirects_to_a_short_lived_signed_url_and_logs_access(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-028 and FR-040 together: the owner of the capture downloads it via a 302 to a freshly
    signed, short-expiry URL — never a bare bucket URL, i.e. the bucket is never public — and the
    access is recorded in `replay_access_log`."""
    owner = await _seed_linked_profile(
        db_session, profile_id=_OWNER_PROFILE_ID, steam_id64="76561197960287930"
    )
    await _sign_in(client, db_session, owner)
    object_key = f"replays/{_GAME_ID}/{_OWNER_PROFILE_ID}.zip"
    capture = await _seed_stored_capture(
        db_session, profile_id=_OWNER_PROFILE_ID, object_key=object_key
    )

    response = client.get(f"/api/replays/{_GAME_ID}/download", follow_redirects=False)

    assert response.status_code == 302
    location = response.headers["location"]
    key, expires_in = _decode_signed_url(location)
    assert key == object_key
    assert 1 <= expires_in <= _MAX_SIGNED_URL_EXPIRES_IN_SECONDS, (
        "a download must be a freshly signed URL with a short expiry (contracts/http-api.md)"
    )

    log_result = await db_session.execute(
        select(ReplayAccessLog).where(ReplayAccessLog.replay_capture_id == capture.id)
    )
    log_rows = log_result.scalars().all()
    assert len(log_rows) == 1, "FR-040: access to an archived replay file must be logged"
    assert log_rows[0].user_id == owner.id
    assert log_rows[0].purpose


async def test_replay_download_refuses_a_caller_who_did_not_play_the_match(
    client: TestClient, db_session: AsyncSession
) -> None:
    """A caller who did not play the match must be refused, even though the match itself, and its
    replay, both exist — and refusal must not leave a `replay_access_log` trace of the attempt.

    Interleaves a genuine owner download first: since the endpoint does not exist at all today,
    every request answers a framework 404 regardless of who asks, which would let this test's own
    negative assertion pass for the wrong reason. Asserting the owner's 302 first, in the same
    test, is what makes this red today for the right reason (the route is missing) rather than by
    coincidence (the framework's own 404 for an unmatched path already carries `not_found`).
    """
    owner = await _seed_linked_profile(
        db_session, profile_id=_OWNER_PROFILE_ID, steam_id64="76561197960287930"
    )
    object_key = f"replays/{_GAME_ID}/{_OWNER_PROFILE_ID}.zip"
    capture = await _seed_stored_capture(
        db_session, profile_id=_OWNER_PROFILE_ID, object_key=object_key
    )

    await _sign_in(client, db_session, owner)
    owner_response = client.get(f"/api/replays/{_GAME_ID}/download", follow_redirects=False)
    assert owner_response.status_code == 302, "the actual participant must be able to download it"

    outsider = await _seed_linked_profile(
        db_session, profile_id=_OTHER_PROFILE_ID, steam_id64="76561197960287931"
    )
    await _sign_in(client, db_session, outsider)

    outsider_response = client.get(f"/api/replays/{_GAME_ID}/download", follow_redirects=False)

    assert outsider_response.status_code == 404
    assert outsider_response.json()["error"]["code"] == "not_found"

    log_result = await db_session.execute(
        select(ReplayAccessLog).where(ReplayAccessLog.replay_capture_id == capture.id)
    )
    log_rows = log_result.scalars().all()
    assert len(log_rows) == 1, (
        "only the owner's successful download may be logged; a refusal is not an access"
    )
    assert log_rows[0].user_id == owner.id
