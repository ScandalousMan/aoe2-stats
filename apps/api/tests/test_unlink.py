"""Integration test for unlinking and relinking a profile (T024, FR-004).

Exercises `DELETE /api/profiles/{profile_id}` (T031) and, for relink, `GET /api/auth/steam/
callback` (T029) against the real throwaway database through the `client`/`db_session` harness
(T015/T015a). Neither router exists yet — `create_app()` (`app.py`) wires only `health` and
`cron` today — so every request below currently 404s through the framework's own catch-all
`HTTPException` handler. That 404 is the "right reason" this test fails: T031 and T029 are what
turn it into the behaviour asserted here, and this file is not expected to change once they land,
only to stop failing.

Two contract choices are assumed here because neither `contracts/http-api.md` nor `data-model.md`
pins them down further, and a test has to commit to *something* concrete to be executable. Both
are the most literal reading of FR-004 and of the sibling `/api/privacy/erase` pattern (T031's own
`http-api.md` row: "Requires an explicit confirmation token from a prior GET"):

1. **The session cookie.** `research.md` §3 fixes the shape (signed, `HttpOnly`, `Secure`,
   `SameSite=Lax`, opaque identifier, state in Postgres) but not the cookie's name or the "signed"
   encoding. `SESSION_COOKIE_NAME` below is this suite's working assumption — chosen to mirror
   `sessions.id`, the column the value round-trips to, and matching `test_consent.py`'s (T025) same
   assumption — and `_sign_in` is the one place to update if T028 lands on something else.
2. **Unlink is two calls against the same endpoint.** FR-004 requires the consequence for
   archived replays to be stated *before* the user confirms, which only a distinct step can do:
   `DELETE /api/profiles/{profile_id}` (no query string) is read as a **preview** — it must state
   the consequence and must not unlink — and `DELETE /api/profiles/{profile_id}?confirm=true` as
   the confirmed unlink. If T031 chooses a different shape (a separate `GET`, a request body), the
   two `client.delete(...)` calls below are what to change; the assertions about the resulting
   database state should not need to.

Relinking is exercised through the plain (non-`?link=1`) callback, because the Steam identity that
proves ownership of this profile already exists on the user from the initial link — relinking the
*same* profile is a returning sign-in (FR-002, spec.md Acceptance Scenario 2), not the "add a
second Steam account" flow `?link=1` covers (that is T023's scenario). `SteamAuthProvider.verify`
(T026) and the auth router (T029) are both implemented as of this task, so a genuine round trip
through `check_authentication` is exercised for real: `fake_relink_upstream` below intercepts at
the `httpx.Client.send` / `httpx.AsyncClient.send` boundary every provider is built on
(`packages/providers/src/aoe2stats_providers/base.py`), the same convention `test_auth_flow.py`
and `test_multi_account.py` already use, rather than a hand-built parameter set that could only
ever 404 or fail signature verification.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, urlsplit

import httpx
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
    ReplayCapture,
    SteamIdentity,
    User,
)
from aoe2stats_storage.models import Session as UserSession

pytestmark = [pytest.mark.usefixtures("environment")]

#: See the module docstring, point 1. Not yet fixed by T028.
SESSION_COOKIE_NAME = "session_id"

_PROFILE_ID = 111222333
_STEAM_ID64 = "76561197960287930"
_GAME_ID = 987654321


async def _seed_linked_profile(
    db_session: AsyncSession,
    *,
    profile_id: int = _PROFILE_ID,
    steam_id64: str = _STEAM_ID64,
) -> tuple[User, SteamIdentity, ProfileLink]:
    """A user with one consenting, allowlisted account and one active profile link."""
    now = datetime.now(UTC)
    user = User(allowlisted_at=now)
    db_session.add(user)
    await db_session.flush()

    steam_identity = SteamIdentity(
        steam_id64=steam_id64, user_id=user.id, verified_at=now, last_sign_in_at=now
    )
    db_session.add(steam_identity)
    db_session.add(AoeProfile(profile_id=profile_id, alias="TestPlayer", country="FR"))
    await db_session.flush()

    profile_link = ProfileLink(
        user_id=user.id,
        profile_id=profile_id,
        steam_id64=steam_id64,
        is_primary=True,
        linked_at=now,
    )
    db_session.add(profile_link)
    await db_session.commit()

    return user, steam_identity, profile_link


async def _add_active_link(
    db_session: AsyncSession,
    *,
    user: User,
    steam_id64: str,
    profile_id: int,
    linked_at: datetime,
    is_primary: bool = False,
) -> ProfileLink:
    """A second (non-primary, by default) active `profile_links` row on `user` — same identity is
    fine here, since `profile_links.steam_id64` carries no uniqueness of its own (module docstring
    point 2 concerns the endpoint shape, not this)."""
    db_session.add(AoeProfile(profile_id=profile_id, alias="SecondPlayer", country="DE"))
    await db_session.flush()
    link = ProfileLink(
        user_id=user.id,
        profile_id=profile_id,
        steam_id64=steam_id64,
        is_primary=is_primary,
        linked_at=linked_at,
    )
    db_session.add(link)
    await db_session.commit()
    return link


async def _sign_in(client: TestClient, db_session: AsyncSession, user: User) -> None:
    """Insert a `sessions` row directly and hand the client its cookie — see the module docstring,
    point 1: there is no auth router yet (T029) to sign in through.

    The cookie value must be signed exactly as `security.issue_session_cookie` signs a real one
    (`<sessions.id>.<hmac-sha256 signature>`, `security.py`): `security.read_session_id` rejects
    anything else before a query is ever issued, which an unsigned raw `session_id` — this
    helper's original form — always was.
    """
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


async def _seed_stored_replay(
    db_session: AsyncSession, *, game_id: int = _GAME_ID, profile_id: int = _PROFILE_ID
) -> None:
    """One already-archived replay for the linked profile, so the unlink response has something
    concrete to state a consequence about."""
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
    await db_session.flush()
    db_session.add(
        ReplayCapture(
            game_id=game_id,
            profile_id=profile_id,
            status=CaptureStatus.STORED,
            capture_deadline_at=now + timedelta(days=19),
            source=CaptureSource.AUTOMATIC,
            object_key=f"replays/{game_id}/{profile_id}.zip",
            zip_bytes=123_456,
            zip_sha256="0" * 64,
            stored_at=now - timedelta(days=1),
        )
    )
    await db_session.commit()


# --- The fake upstream for the relink test's real callback round trip ----------------------------
#
# `test_auth_flow.py`'s and `test_multi_account.py`'s convention: intercept at `httpx.Client.send`
# / `httpx.AsyncClient.send`, the one boundary every provider is built on (`packages/providers/
# src/aoe2stats_providers/base.py`), rather than any dependency name internal to the router.

_STEAM_CHECK_AUTH_VALID = "ns:http://specs.openid.net/auth/2.0\nis_valid:true"


def _begin_sign_in(client: TestClient) -> tuple[str, dict[str, str]]:
    """`GET /api/auth/steam/start`, returning the exact `openid.return_to` Steam would echo back
    and its own query parameters — the CSRF `state` this feature embeds there is only known once
    the server has issued it."""
    response = client.get("/api/auth/steam/start", follow_redirects=False)
    assert response.status_code == 302, (
        f"GET /api/auth/steam/start did not redirect to Steam: {response.status_code} "
        f"{response.text}"
    )
    location = response.headers["location"]
    parsed = urlsplit(location)
    assert parsed.hostname == "steamcommunity.com", f"expected a redirect to Steam, got {location}"
    start_params = dict(parse_qsl(parsed.query))
    return_to = start_params["openid.return_to"]
    return_to_query = dict(parse_qsl(urlsplit(return_to).query))
    return return_to, return_to_query


def _relink_callback_params(steam_id64: str, return_to: str) -> dict[str, str]:
    """A syntactically well-formed OpenID 2.0 `id_res` assertion for `steam_id64`."""
    identity = f"https://steamcommunity.com/openid/id/{steam_id64}"
    return {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "id_res",
        "openid.op_endpoint": "https://steamcommunity.com/openid/login",
        "openid.claimed_id": identity,
        "openid.identity": identity,
        "openid.return_to": return_to,
        "openid.response_nonce": f"2026-08-20T12:00:00Z{steam_id64}",
        "openid.assoc_handle": "1234567890",
        "openid.signed": (
            "signed,op_endpoint,claimed_id,identity,return_to,response_nonce,assoc_handle"
        ),
        "openid.sig": "dGVzdC1zaWduYXR1cmUtdmFsdWU=",
    }


@pytest.fixture
def fake_relink_upstream(monkeypatch: pytest.MonkeyPatch) -> None:
    """Steam always verifies, and Relic resolves `_STEAM_ID64` back to `_PROFILE_ID` — just enough
    of both wire shapes (`docs/data-sources.md`) for the relink test's callback to complete a
    genuine, successful returning sign-in rather than 404 or fail signature verification against a
    real network call."""
    member = {
        "profile_id": _PROFILE_ID,
        "name": f"/steam/{_STEAM_ID64}",
        "alias": "TestPlayer",
        "country": "FR",
        "personal_statgroup_id": _PROFILE_ID,
        "clanlist_name": "",
        "leaderboardregion_id": 0,
        "level": 1,
        "xp": 0,
    }
    personal_stat_body = {
        "result": {"code": 0, "message": "OK"},
        "statGroups": [{"id": _PROFILE_ID, "type": 1, "name": "", "members": [member]}],
        "leaderboardStats": [
            {
                "statgroup_id": _PROFILE_ID,
                "leaderboard_id": 3,
                "rating": 1000,
                "rank": -1,
                "ranklevel": 0,
                "ranktotal": 0,
                "regionrank": -1,
                "regionranktotal": 0,
                "wins": 0,
                "losses": 0,
                "streak": 0,
                "drops": 0,
                "disputes": 0,
                "highestrank": 0,
                "highestranklevel": 0,
                "highestrating": 1000,
                "lastmatchdate": 0,
            }
        ],
    }

    def sync_send(self: httpx.Client, request: httpx.Request, **kwargs: object) -> httpx.Response:
        if request.url.host == "steamcommunity.com":
            return httpx.Response(200, text=_STEAM_CHECK_AUTH_VALID, request=request)
        # `TestClient` itself is an `httpx.Client` under the hood — its own traffic to the FastAPI
        # app must pass through untouched, only Steam is faked (test_auth_flow.py's convention).
        return original_sync_send(self, request, **kwargs)  # type: ignore[no-any-return]

    async def async_send(
        self: httpx.AsyncClient, request: httpx.Request, **kwargs: object
    ) -> httpx.Response:
        if request.url.host != "aoe-api.worldsedgelink.com":
            raise AssertionError(f"unexpected outbound async request to {request.url}")
        return httpx.Response(200, json=personal_stat_body, request=request)

    original_sync_send = httpx.Client.send
    monkeypatch.setattr(httpx.Client, "send", sync_send)
    monkeypatch.setattr(httpx.AsyncClient, "send", async_send)


async def test_unlink_preview_states_replay_consequences_and_does_not_unlink(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-004: the response must state what becomes of archived replays *before* the user
    confirms — calling the endpoint without confirming must not touch `unlinked_at` at all."""
    user, _steam_identity, _link = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)
    await _seed_stored_replay(db_session)

    response = client.delete(f"/api/profiles/{_PROFILE_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body.get("confirmed") is False
    archived = body.get("archived_replays")
    assert archived is not None, "the preview must state what happens to archived replays"
    assert archived["retained"] is True
    assert archived["count"] == 1

    db_session.expire_all()
    stored_link = (
        await db_session.execute(select(ProfileLink).where(ProfileLink.profile_id == _PROFILE_ID))
    ).scalar_one()
    assert stored_link.unlinked_at is None

    stored_capture = (
        await db_session.execute(
            select(ReplayCapture).where(ReplayCapture.profile_id == _PROFILE_ID)
        )
    ).scalar_one()
    assert stored_capture.status == CaptureStatus.STORED


async def test_unlink_confirmed_sets_unlinked_at_without_deleting_the_row(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-004 / data-model.md: unlink sets `unlinked_at` rather than deleting the row, so capture
    history stays explicable, and it must not touch the replay already archived."""
    user, _steam_identity, link = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)
    await _seed_stored_replay(db_session)

    response = client.delete(f"/api/profiles/{_PROFILE_ID}?confirm=true")

    assert response.status_code == 200
    body = response.json()
    assert body.get("confirmed") is True
    assert body.get("unlinked_at") is not None

    db_session.expire_all()
    rows = (
        (await db_session.execute(select(ProfileLink).where(ProfileLink.profile_id == _PROFILE_ID)))
        .scalars()
        .all()
    )
    assert len(rows) == 1, "unlink must set a column, never delete the row"
    assert rows[0].id == link.id
    assert rows[0].unlinked_at is not None

    stored_capture = (
        await db_session.execute(
            select(ReplayCapture).where(ReplayCapture.profile_id == _PROFILE_ID)
        )
    ).scalar_one()
    assert stored_capture.status == CaptureStatus.STORED
    assert stored_capture.object_key is not None


async def test_unlink_confirmed_leaves_no_active_link_for_ingestion_to_select(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-013/FR-042's discovery query selects work through `profile_links.unlinked_at IS NULL`
    (data-model.md); unlinking must remove this profile from that set, which is how ingestion
    "stops" for it without a separate flag to keep in sync."""
    user, _steam_identity, _link = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)

    response = client.delete(f"/api/profiles/{_PROFILE_ID}?confirm=true")
    assert response.status_code == 200

    db_session.expire_all()
    active_links = (
        (
            await db_session.execute(
                select(ProfileLink).where(
                    ProfileLink.profile_id == _PROFILE_ID,
                    ProfileLink.unlinked_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    assert active_links == [], "no active link must remain for an unlinked profile"


async def test_unlink_confirmed_promotes_oldest_surviving_link_to_primary(
    client: TestClient, db_session: AsyncSession
) -> None:
    """T031b / data-model.md's "exactly one primary per user" and FR-043: a user with two active
    links who unlinks the primary one must not end with none — the surviving link is promoted in
    the same transaction, and it must be reachable through `GET /api/profiles`, not merely correct
    in the database."""
    second_profile_id = _PROFILE_ID + 1
    user, _steam_identity, primary_link = await _seed_linked_profile(db_session)
    second_link = await _add_active_link(
        db_session,
        user=user,
        steam_id64=_STEAM_ID64,
        profile_id=second_profile_id,
        linked_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    # Captured now, before `expire_all()` below — reading an id off an expired ORM instance
    # outside of an `await` triggers SQLAlchemy's async lazy-load with no greenlet to run it in.
    primary_link_id, second_link_id = primary_link.id, second_link.id
    await _sign_in(client, db_session, user)

    response = client.delete(f"/api/profiles/{_PROFILE_ID}?confirm=true")
    assert response.status_code == 200

    db_session.expire_all()
    unlinked = (
        await db_session.execute(select(ProfileLink).where(ProfileLink.id == primary_link_id))
    ).scalar_one()
    assert unlinked.unlinked_at is not None
    assert unlinked.is_primary is True, "unlink never rewrites the row it just deactivated"

    promoted = (
        await db_session.execute(select(ProfileLink).where(ProfileLink.id == second_link_id))
    ).scalar_one()
    assert promoted.unlinked_at is None
    assert promoted.is_primary is True, "the oldest surviving active link must become primary"

    profiles_response = client.get("/api/profiles")
    assert profiles_response.status_code == 200
    profiles = {p["profile_id"]: p for p in profiles_response.json()["profiles"]}
    assert second_profile_id in profiles, "the surviving profile must stay reachable"
    assert profiles[second_profile_id]["is_primary"] is True
    assert _PROFILE_ID not in profiles, "the unlinked profile must not be listed as active"


async def test_relink_after_unlink_creates_a_new_active_link(
    client: TestClient, db_session: AsyncSession, fake_relink_upstream: None
) -> None:
    """Edge case (spec.md): a user unlinks a profile and later relinks the same one. The partial
    unique index (`ix_profile_links_profile_id_active`, T007) exists exactly so this does not
    collide with the inactive row left behind by unlink — relinking must produce a *second*,
    active `profile_links` row rather than reviving the first."""
    user, _steam_identity, original_link = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)

    unlink_response = client.delete(f"/api/profiles/{_PROFILE_ID}?confirm=true")
    assert unlink_response.status_code == 200

    return_to, return_to_query = _begin_sign_in(client)
    params = {**return_to_query, **_relink_callback_params(_STEAM_ID64, return_to)}
    callback_response = client.get(
        "/api/auth/steam/callback", params=params, follow_redirects=False
    )
    assert callback_response.is_redirect, (
        f"a relink of the same profile must succeed through a returning sign-in: "
        f"{callback_response.status_code} {callback_response.text}"
    )
    redirect_query = dict(parse_qsl(urlsplit(callback_response.headers.get("location", "")).query))
    assert "error" not in redirect_query, f"relink callback failed: {redirect_query}"

    db_session.expire_all()
    links = (
        (await db_session.execute(select(ProfileLink).where(ProfileLink.profile_id == _PROFILE_ID)))
        .scalars()
        .all()
    )
    active = [row for row in links if row.unlinked_at is None]
    assert len(active) == 1, "relinking must produce exactly one active link for the profile"
    assert active[0].id != original_link.id, (
        "relink must insert a new row, never resurrect the unlinked one — capture history stays "
        "attached to the link that was active when it happened"
    )
    inactive = [row for row in links if row.id == original_link.id]
    assert inactive and inactive[0].unlinked_at is not None, (
        "the original unlink record must survive a relink"
    )
