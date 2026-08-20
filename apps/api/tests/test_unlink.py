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
second Steam account" flow `?link=1` covers (that is T023's scenario). Forging a real Steam OpenID
assertion is out of reach here regardless of the route existing: `SteamAuthProvider.verify` (T026)
is not written, so whatever request shape is sent below 404s the same way — the query parameters
are representative of the real wire format (`docs/data-sources.md`, `packages/providers/fixtures/
steam/`) rather than exact, since nothing yet parses them.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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

# Every test in this file is expected to fail for exactly one reason — the profiles and auth
# routers (T029, T031) do not exist yet — until they do. `strict=True` is what makes that honest:
# the moment those tasks land and a test starts passing, `strict=True` turns the *run* red instead
# of letting a stale xfail hide it, which is the whole point of marking these tests failing rather
# than skipping them. Do not drop `strict=True`.
pytestmark = [
    pytest.mark.usefixtures("environment"),
    pytest.mark.xfail(
        strict=True,
        reason=(
            "the profiles and auth routers (T029, T031) are not implemented yet, "
            "not this test-first task (T024)"
        ),
    ),
]

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
    user = User(allowlisted_at=now, ingest_consent_at=now)
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


async def _sign_in(client: TestClient, db_session: AsyncSession, user: User) -> None:
    """Insert a `sessions` row directly and hand the client its cookie — see the module docstring,
    point 1: there is no auth router yet (T029) to sign in through."""
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
    client.cookies.set(SESSION_COOKIE_NAME, session_id)


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


async def test_relink_after_unlink_creates_a_new_active_link(
    client: TestClient, db_session: AsyncSession
) -> None:
    """Edge case (spec.md): a user unlinks a profile and later relinks the same one. The partial
    unique index (`ix_profile_links_profile_id_active`, T007) exists exactly so this does not
    collide with the inactive row left behind by unlink — relinking must produce a *second*,
    active `profile_links` row rather than reviving the first."""
    user, _steam_identity, original_link = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)

    unlink_response = client.delete(f"/api/profiles/{_PROFILE_ID}?confirm=true")
    assert unlink_response.status_code == 200

    # Representative of the real wire format (docs/data-sources.md, packages/providers/fixtures/
    # steam/) rather than a valid signed assertion: no `SteamAuthProvider` exists yet to verify
    # one, and the route itself does not exist yet either, so this 404s regardless (see the
    # module docstring).
    callback_response = client.get(
        "/api/auth/steam/callback",
        params={
            "openid.ns": "http://specs.openid.net/auth/2.0",
            "openid.mode": "id_res",
            "openid.op_endpoint": "https://steamcommunity.com/openid/login",
            "openid.claimed_id": f"https://steamcommunity.com/openid/id/{_STEAM_ID64}",
            "openid.identity": f"https://steamcommunity.com/openid/id/{_STEAM_ID64}",
            "openid.return_to": "http://localhost:5173/api/auth/steam/callback",
            "openid.response_nonce": "2026-08-20T00:00:00Ztest-nonce",
            "openid.assoc_handle": "test-assoc-handle",
            "openid.signed": (
                "signed,op_endpoint,claimed_id,identity,return_to,response_nonce,assoc_handle"
            ),
            "openid.sig": "test-signature-not-real",
        },
        follow_redirects=False,
    )
    assert callback_response.status_code in (200, 302), (
        "a relink of the same profile must succeed through a returning sign-in"
    )

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
