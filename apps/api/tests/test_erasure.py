"""Integration test for quickstart scenario 10, points 2 and 3 (T087) — implemented at **T091**
(`packages/core/src/aoe2stats_core/privacy/erasure.py`) and its route, `POST /api/privacy/erase`
(`contracts/http-api.md`).

**Nothing this file exercises exists yet.** `routers/privacy.py` today holds only
`POST /api/privacy/archival-objection` (T032/T405); there is no `/api/privacy/erase` route at all,
so every request below answers a framework 404 with the generic envelope `app.py` builds for an
unmatched route. `packages/core/src/aoe2stats_core/privacy/erasure.py` (T091) does not exist
either — but this file never imports it: everything below drives the HTTP contract through
`client`, exactly as `test_replay_download.py` and `test_analysis_routes.py` do for their own
not-yet-built routes, so there is nothing missing to import at all. `xfail(strict=True,
reason="T091 not implemented yet")` marks every test below for that reason; the marker comes off
by itself the moment T091 makes an assertion here start passing (SubagentStop's own gate on a
"never separately green" pair aside, `pytest.mark.xfail` is what turns a genuine regression back
into a red run instead of a silently stale marker).

**The endpoint shape asserted below is a reading of the contract, not a restatement of one that
already exists.** `contracts/http-api.md`'s one row on this route reads: "Requires an explicit
confirmation token from a prior `GET`. Irreversible (FR-037)." There is no `GET` row for this path
in the table, and no schema is given anywhere for either call — the two-step, token-bearing shape
(`GET /api/privacy/erase` mints an opaque `confirmation_token`; `POST /api/privacy/erase` accepts
`{"confirmation_token": "..."}` and only then acts) is this test's own good-faith reading of that
one sentence, chosen because it is the one shape in this codebase's own vocabulary that matches
"a token from a prior GET" — the `CsrfState` row `security.py` already mints and consumes the same
way for the OpenID `state` parameter, never a bare `?confirm=true` repeat-the-same-call shape
(`routers/profiles.py`'s `DELETE /api/profiles/{profile_id}`, which the contract deliberately does
not use here: that one names no token and needs none, and the difference is exactly why the two
routes read differently). If T091 lands with different field names, this file's own assertions —
not the contract sentence above — are what a remediation task corrects.

**Verified by listing the bucket, not by trusting the response**, per quickstart scenario 10 point
2 and `ObjectStore.list_keys`'s own docstring ("Erasure is verified 'by listing the bucket, not by
trusting a success response'... this is that listing. It reads the bucket itself rather than the
database"). `_RecordingObjectStore` below is this file's own fake — never `conftest.py`'s shared
`_FakeObjectStore`, whose `list_keys` always answers `[]` and which has no `put`/`delete` at all
(`test_replay_download.py`'s `_TrackingObjectStore` docstring makes the identical point) — with a
real in-memory dict a test can seed before erasure and re-list after it, so "the blob is gone" is
asserted against the store's own state rather than against whatever the endpoint happened to
answer.

**003's tables**, per `specs/003-player-search-match-analysis/data-model.md` and T091's own task
text: `favourites` and `rate_limit_counters` are deleted with the user (both carry `user_id` as
part of their primary key, `ondelete="CASCADE"`); `match_analyses.requested_by_user_id` is cleared
while the row and its `state`/`result_key` are retained (`ondelete="SET NULL"` — the analysis is
derived from a public match record and is shown to every viewer, so it survives; who asked for it
does not); `retained_recordings` is **kept whole**, object and row both, because erasing the
requester removes a link and not a subject and a published analysis must stay recomputable
(constitution IV) — deleting a retained recording is T092's objection route, never this one.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api import security
from aoe2stats_api.deps import get_object_store
from aoe2stats_api.settings import get_settings
from aoe2stats_storage.models import (
    AoeProfile,
    CaptureSource,
    CaptureStatus,
    DataRequest,
    DataRequestKind,
    Favourite,
    Match,
    MatchAnalysis,
    MatchAnalysisState,
    MatchPlayer,
    ProfileLink,
    RateLimitCounter,
    ReplayAccessLog,
    ReplayCapture,
    RetainedRecording,
    SteamIdentity,
    User,
)
from aoe2stats_storage.models import Session as UserSession

pytestmark = [pytest.mark.usefixtures("environment")]

SESSION_COOKIE_NAME = "session_id"

_ERASE_PATH = "/api/privacy/erase"

#: Distinguishing, non-overlapping ids for each test's own seed data — `clean_database` truncates
#: between tests, but every test in this file constructs several rows sharing a `game_id`, so kept
#: apart the way `test_replay_download.py`'s own per-test constants are.
_OWNER_PROFILE_ID = 810_100_001
_BYSTANDER_PROFILE_ID = 810_100_002
_FAVOURITE_TARGET_PROFILE_ID = 810_100_003
_OTHER_USERS_PROFILE_ID = 810_100_004

_SHARED_MATCH_GAME_ID = 810_200_001
_ANALYSIS_GAME_ID = 810_200_002
_RETAINED_GAME_ID = 810_200_003
_BYSTANDER_MATCH_GAME_ID = 810_200_004


class _RecordingObjectStore:
    """A `get_object_store` override with a real in-memory bucket — `put`, `get`, `delete` and
    `list_keys` all read and write the same `dict`, unlike `conftest.py`'s shared
    `_FakeObjectStore` (T066), which implements only `list_keys` (always `[]`) and
    `signed_get_url`. Erasure has to be checked against a store that can actually hold something
    and actually lose it.
    """

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    async def put(self, key: str, body: bytes, *, content_type: str = "application/zip") -> None:
        self._objects[key] = body

    async def get(self, key: str) -> bytes:
        return self._objects[key]

    async def delete(self, key: str) -> None:
        self._objects.pop(key, None)

    async def list_keys(self, prefix: str = "") -> list[str]:
        return [key for key in self._objects if key.startswith(prefix)]

    async def signed_get_url(
        self, key: str, *, expires_in: int = 300, filename: str | None = None
    ) -> str:
        return f"https://fake-object-store.example/signed/{key}?expires_in={expires_in}"


def _install_recording_object_store(client: TestClient) -> _RecordingObjectStore:
    store = _RecordingObjectStore()
    client.app.dependency_overrides[get_object_store] = lambda: store  # type: ignore[attr-defined]
    return store


async def _seed_linked_user(
    db_session: AsyncSession, *, profile_id: int, steam_id64: str, alias: str = "Departing"
) -> User:
    """A user with one verified Steam identity, one `aoe_profiles` row and one active
    `profile_links` row — mirrors `test_replay_download.py`'s own `_seed_linked_profile`."""
    now = datetime.now(UTC)
    user = User(allowlisted_at=now)
    db_session.add(user)
    await db_session.flush()

    db_session.add(
        SteamIdentity(steam_id64=steam_id64, user_id=user.id, verified_at=now, last_sign_in_at=now)
    )
    db_session.add(AoeProfile(profile_id=profile_id, alias=alias, country="FR"))
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


async def _sign_in(client: TestClient, db_session: AsyncSession, user: User) -> str:
    """Insert a `sessions` row directly and hand the client its signed cookie — mirrors
    `test_replay_download.py`'s own `_sign_in`. Returns the raw (unsigned) session id, since the
    "refused on the very next request" assertion needs to look the row up by it."""
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
    return session_id


async def _seed_stored_capture(
    db_session: AsyncSession, *, game_id: int, profile_id: int, object_key: str
) -> ReplayCapture:
    now = datetime.now(UTC)
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


def _get_confirmation_token(client: TestClient) -> str:
    """The one call this whole file assumes exists ahead of T091: `GET /api/privacy/erase`
    mints an opaque, single-use `confirmation_token` (module docstring). Every test that reaches
    for it is asserting exactly that assumption alongside whatever it actually means to test —
    which is correct, since the assumption itself is part of the contract this test encodes."""
    response = client.get(_ERASE_PATH)
    assert response.status_code == 200, (
        f"GET {_ERASE_PATH} must answer a confirmation token (contracts/http-api.md: "
        f"'a prior GET'). Got {response.status_code}: {response.text}"
    )
    token = response.json().get("confirmation_token")
    assert isinstance(token, str) and token, (
        "GET /api/privacy/erase must answer a non-empty confirmation_token"
    )
    return token


# ================================================================================================
# Point 2, first half: an explicit confirmation token, not a bare POST
# ================================================================================================


@pytest.mark.xfail(strict=True, reason="T091 not implemented yet")
async def test_post_erase_without_any_token_is_refused_and_erases_nothing(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-037's "explicit confirmation step": a bare `POST /api/privacy/erase` with no token at
    all — nobody ever called the prior `GET` — must be refused, and the account must survive
    completely untouched."""
    user = await _seed_linked_user(
        db_session, profile_id=_OWNER_PROFILE_ID, steam_id64="76561197960280001"
    )
    await _sign_in(client, db_session, user)

    response = client.post(_ERASE_PATH, json={})

    assert response.status_code == 422, (
        f"a confirmation token is mandatory and this call supplied none; got "
        f"{response.status_code}: {response.text}"
    )

    survivor = await db_session.get(User, user.id)
    assert survivor is not None, "a refused erasure attempt must not touch the account"


@pytest.mark.xfail(strict=True, reason="T091 not implemented yet")
async def test_post_erase_with_a_tampered_token_is_refused_and_erases_nothing(
    client: TestClient, db_session: AsyncSession
) -> None:
    """The token from a genuine prior `GET` is not enough on its own to prove the token check is
    real — a guessed or tampered value must be refused identically."""
    user = await _seed_linked_user(
        db_session, profile_id=_OWNER_PROFILE_ID, steam_id64="76561197960280002"
    )
    await _sign_in(client, db_session, user)
    real_token = _get_confirmation_token(client)

    response = client.post(_ERASE_PATH, json={"confirmation_token": real_token + "-tampered"})

    assert response.status_code in (400, 403, 409), (
        f"a tampered confirmation token must be refused, not accepted; got "
        f"{response.status_code}: {response.text}"
    )

    survivor = await db_session.get(User, user.id)
    assert survivor is not None, "a refused erasure attempt must not touch the account"


# ================================================================================================
# Point 2, second half: what a genuine, confirmed erasure actually removes
# ================================================================================================


@pytest.mark.xfail(strict=True, reason="T091 not implemented yet")
async def test_confirmed_erasure_deletes_the_user_identities_sessions_and_links(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-037, SC-008: the confirmed call removes the user row itself, every Steam identity, every
    session and every profile link — not merely revokes or hides them."""
    user = await _seed_linked_user(
        db_session, profile_id=_OWNER_PROFILE_ID, steam_id64="76561197960280003"
    )
    await _sign_in(client, db_session, user)
    _install_recording_object_store(client)
    token = _get_confirmation_token(client)
    user_id = user.id

    response = client.post(_ERASE_PATH, json={"confirmation_token": token})
    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    assert await db_session.get(User, user_id) is None, "the user row itself must be gone"

    identity_count = (
        await db_session.execute(
            select(func.count()).select_from(SteamIdentity).where(SteamIdentity.user_id == user_id)
        )
    ).scalar_one()
    assert identity_count == 0, "every Steam identity must be gone"

    session_count = (
        await db_session.execute(
            select(func.count()).select_from(UserSession).where(UserSession.user_id == user_id)
        )
    ).scalar_one()
    assert session_count == 0, "every session row must be gone"

    link_count = (
        await db_session.execute(
            select(func.count()).select_from(ProfileLink).where(ProfileLink.user_id == user_id)
        )
    ).scalar_one()
    assert link_count == 0, "every profile link must be gone"


@pytest.mark.xfail(strict=True, reason="T091 not implemented yet")
async def test_confirmed_erasure_deletes_captures_and_verifies_the_blob_by_listing_the_bucket(
    client: TestClient, db_session: AsyncSession
) -> None:
    """Quickstart scenario 10 point 2, word for word: "verified by listing the bucket, not by
    trusting a success response." The capture row and the object it points at must both be gone —
    the object checked against `_RecordingObjectStore`'s own state, never against the response
    body alone."""
    user = await _seed_linked_user(
        db_session, profile_id=_OWNER_PROFILE_ID, steam_id64="76561197960280004"
    )
    await _sign_in(client, db_session, user)
    store = _install_recording_object_store(client)

    object_key = f"replays/{_SHARED_MATCH_GAME_ID}/{_OWNER_PROFILE_ID}.zip"
    db_session.add(
        Match(
            game_id=_SHARED_MATCH_GAME_ID,
            leaderboard_id=3,
            completed_at=datetime.now(UTC) - timedelta(days=2),
            source="relic",
            raw_payload={},
        )
    )
    await db_session.commit()
    capture = await _seed_stored_capture(
        db_session,
        game_id=_SHARED_MATCH_GAME_ID,
        profile_id=_OWNER_PROFILE_ID,
        object_key=object_key,
    )
    await store.put(object_key, b"FAKE-REPLAY-BYTES")
    assert object_key in await store.list_keys(), "the capture's own blob must exist before erasure"

    token = _get_confirmation_token(client)
    response = client.post(_ERASE_PATH, json={"confirmation_token": token})
    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    remaining_keys = await store.list_keys()
    assert object_key not in remaining_keys, (
        "the blob must be gone from the bucket itself, listed directly — not merely absent from "
        f"the response body. Bucket still holds: {remaining_keys}"
    )

    capture_after = await db_session.get(ReplayCapture, capture.id)
    assert capture_after is None, "the replay_captures row must be gone, not merely its blob"


@pytest.mark.xfail(strict=True, reason="T091 not implemented yet")
async def test_confirmed_erasure_deletes_replay_access_log_rows_for_the_erased_users_captures_only(
    client: TestClient, db_session: AsyncSession
) -> None:
    """data-model.md's `data_requests` section: "The access log goes with the captures it
    describes... It is not the accountability record for anyone else — nobody else's blob is
    reachable from these rows." A row logging *someone else's* access to the erased user's own
    capture must go too (the fact belongs to the departing user's capture, not to the accessor);
    a row logging access to a *different* user's own, unrelated capture must survive untouched."""
    owner = await _seed_linked_user(
        db_session, profile_id=_OWNER_PROFILE_ID, steam_id64="76561197960280005"
    )
    bystander = await _seed_linked_user(
        db_session,
        profile_id=_BYSTANDER_PROFILE_ID,
        steam_id64="76561197960280006",
        alias="Bystander",
    )

    db_session.add(
        Match(
            game_id=_SHARED_MATCH_GAME_ID,
            leaderboard_id=3,
            completed_at=datetime.now(UTC) - timedelta(days=2),
            source="relic",
            raw_payload={},
        )
    )
    db_session.add(
        Match(
            game_id=_BYSTANDER_MATCH_GAME_ID,
            leaderboard_id=3,
            completed_at=datetime.now(UTC) - timedelta(days=2),
            source="relic",
            raw_payload={},
        )
    )
    await db_session.commit()

    owners_capture = await _seed_stored_capture(
        db_session,
        game_id=_SHARED_MATCH_GAME_ID,
        profile_id=_OWNER_PROFILE_ID,
        object_key=f"replays/{_SHARED_MATCH_GAME_ID}/{_OWNER_PROFILE_ID}.zip",
    )
    bystanders_capture = await _seed_stored_capture(
        db_session,
        game_id=_BYSTANDER_MATCH_GAME_ID,
        profile_id=_BYSTANDER_PROFILE_ID,
        object_key=f"replays/{_BYSTANDER_MATCH_GAME_ID}/{_BYSTANDER_PROFILE_ID}.zip",
    )

    db_session.add_all(
        [
            # The owner's own download of their own capture.
            ReplayAccessLog(
                replay_capture_id=owners_capture.id,
                user_id=owner.id,
                accessed_at=datetime.now(UTC),
                purpose="download",
            ),
            # A different user reading the owner's own archived point of view (003's
            # per-participant download route) — still a fact about the owner's capture.
            ReplayAccessLog(
                replay_capture_id=owners_capture.id,
                user_id=bystander.id,
                accessed_at=datetime.now(UTC),
                purpose="download",
            ),
            # The bystander's own, wholly unrelated access to their own capture.
            ReplayAccessLog(
                replay_capture_id=bystanders_capture.id,
                user_id=bystander.id,
                accessed_at=datetime.now(UTC),
                purpose="download",
            ),
        ]
    )
    await db_session.commit()

    await _sign_in(client, db_session, owner)
    _install_recording_object_store(client)
    token = _get_confirmation_token(client)
    response = client.post(_ERASE_PATH, json={"confirmation_token": token})
    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    remaining_for_owners_capture = (
        await db_session.execute(
            select(func.count())
            .select_from(ReplayAccessLog)
            .where(ReplayAccessLog.replay_capture_id == owners_capture.id)
        )
    ).scalar_one()
    assert remaining_for_owners_capture == 0, (
        "every access-log row pointing at the erased user's own capture must be gone, "
        "regardless of who made the access"
    )

    remaining_for_bystanders_capture = (
        await db_session.execute(
            select(func.count())
            .select_from(ReplayAccessLog)
            .where(ReplayAccessLog.replay_capture_id == bystanders_capture.id)
        )
    ).scalar_one()
    assert remaining_for_bystanders_capture == 1, (
        "a different user's own, unrelated access-log row must never be touched by someone "
        "else's erasure"
    )


@pytest.mark.xfail(strict=True, reason="T091 not implemented yet")
async def test_erased_users_session_cookie_is_refused_on_the_very_next_request(
    client: TestClient, db_session: AsyncSession
) -> None:
    """T087's own wording: "the erased user's session cookie is refused on the very next
    request." The identical cookie the client already holds must fail `GET /api/me` — the
    contract's own signed-out shape, `200 {"authenticated": false}`, never a stale `true`."""
    user = await _seed_linked_user(
        db_session, profile_id=_OWNER_PROFILE_ID, steam_id64="76561197960280007"
    )
    await _sign_in(client, db_session, user)
    _install_recording_object_store(client)
    token = _get_confirmation_token(client)

    erase_response = client.post(_ERASE_PATH, json={"confirmation_token": token})
    assert erase_response.status_code == 200, (
        f"Got {erase_response.status_code}: {erase_response.text}"
    )

    me_response = client.get("/api/me")
    assert me_response.status_code == 200
    assert me_response.json() == {"authenticated": False}, (
        "the exact same session cookie must be refused on the very next request after erasure"
    )


# ================================================================================================
# Point 3: `matches` and `match_players` survive, with the departing user's `profile_id`
# pseudonymised in place — never deleted, per quickstart scenario 10 and data-model.md
# ================================================================================================


@pytest.mark.xfail(strict=True, reason="T091 not implemented yet")
async def test_confirmed_erasure_pseudonymises_the_profile_id_in_matches_and_match_players(
    client: TestClient, db_session: AsyncSession
) -> None:
    """Quickstart scenario 10 point 3: "matches and match_players survive, with the departing
    user's profile pseudonymised: those rows describe games other people also played." A shared
    match — one row the owner played, one the surviving opponent did — must keep both participant
    rows and the match itself, with only the owner's own `profile_id` value replaced."""
    owner = await _seed_linked_user(
        db_session, profile_id=_OWNER_PROFILE_ID, steam_id64="76561197960280008"
    )
    db_session.add(AoeProfile(profile_id=_OTHER_USERS_PROFILE_ID, alias="Opponent", country="DE"))
    db_session.add(
        Match(
            game_id=_SHARED_MATCH_GAME_ID,
            leaderboard_id=3,
            completed_at=datetime.now(UTC) - timedelta(days=2),
            source="relic",
            raw_payload={"matchHistoryId": _SHARED_MATCH_GAME_ID},
        )
    )
    await db_session.flush()
    db_session.add_all(
        [
            MatchPlayer(
                game_id=_SHARED_MATCH_GAME_ID,
                profile_id=_OWNER_PROFILE_ID,
                team_id=1,
                result="win",
            ),
            MatchPlayer(
                game_id=_SHARED_MATCH_GAME_ID,
                profile_id=_OTHER_USERS_PROFILE_ID,
                team_id=2,
                result="loss",
            ),
        ]
    )
    await db_session.commit()

    await _sign_in(client, db_session, owner)
    _install_recording_object_store(client)
    token = _get_confirmation_token(client)
    response = client.post(_ERASE_PATH, json={"confirmation_token": token})
    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    match_after = await db_session.get(Match, _SHARED_MATCH_GAME_ID)
    assert match_after is not None, (
        "the shared match must survive erasure — it describes a game another person also played"
    )

    remaining_players = (
        await db_session.execute(
            select(func.count())
            .select_from(MatchPlayer)
            .where(MatchPlayer.game_id == _SHARED_MATCH_GAME_ID)
        )
    ).scalar_one()
    assert remaining_players == 2, "both participant rows must survive — pseudonymised, not deleted"

    owner_still_present = (
        await db_session.execute(
            select(func.count())
            .select_from(MatchPlayer)
            .where(
                MatchPlayer.game_id == _SHARED_MATCH_GAME_ID,
                MatchPlayer.profile_id == _OWNER_PROFILE_ID,
            )
        )
    ).scalar_one()
    assert owner_still_present == 0, (
        "the departing user's own real profile_id must no longer appear in match_players — it "
        "is pseudonymised in place, not left as-is"
    )

    other_participant_untouched = (
        await db_session.execute(
            select(MatchPlayer).where(
                MatchPlayer.game_id == _SHARED_MATCH_GAME_ID,
                MatchPlayer.profile_id == _OTHER_USERS_PROFILE_ID,
            )
        )
    ).scalar_one_or_none()
    assert other_participant_untouched is not None, (
        "the surviving opponent's own row must be entirely untouched by someone else's erasure"
    )


# ================================================================================================
# 003's tables — named explicitly in T091's own task text
# ================================================================================================


@pytest.mark.xfail(strict=True, reason="T091 not implemented yet")
async def test_confirmed_erasure_deletes_favourites_and_rate_limit_counters(
    client: TestClient, db_session: AsyncSession
) -> None:
    """003 data-model.md: "`favourites`: deleted with the user" and "`rate_limit_counters`:
    deleted with the user." Neither is the user's *published* data — both are private, disposable
    state that has no reason to survive the account it belongs to."""
    user = await _seed_linked_user(
        db_session, profile_id=_OWNER_PROFILE_ID, steam_id64="76561197960280009"
    )
    db_session.add(
        AoeProfile(profile_id=_FAVOURITE_TARGET_PROFILE_ID, alias="Favourited", country="FR")
    )
    await db_session.flush()
    db_session.add(
        Favourite(
            user_id=user.id,
            profile_id=_FAVOURITE_TARGET_PROFILE_ID,
            created_at=datetime.now(UTC),
        )
    )
    window_start = datetime.now(UTC).replace(second=0, microsecond=0)
    db_session.add(
        RateLimitCounter(user_id=user.id, bucket="search", window_start=window_start, count=3)
    )
    await db_session.commit()

    await _sign_in(client, db_session, user)
    _install_recording_object_store(client)
    token = _get_confirmation_token(client)
    response = client.post(_ERASE_PATH, json={"confirmation_token": token})
    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    favourite_count = (
        await db_session.execute(
            select(func.count()).select_from(Favourite).where(Favourite.user_id == user.id)
        )
    ).scalar_one()
    assert favourite_count == 0, "favourites must be deleted with the user"

    counter_count = (
        await db_session.execute(
            select(func.count())
            .select_from(RateLimitCounter)
            .where(RateLimitCounter.user_id == user.id)
        )
    ).scalar_one()
    assert counter_count == 0, "rate_limit_counters must be deleted with the user"


@pytest.mark.xfail(strict=True, reason="T091 not implemented yet")
async def test_confirmed_erasure_clears_but_retains_match_analyses_requested_by_the_user(
    client: TestClient, db_session: AsyncSession
) -> None:
    """003 data-model.md: "`match_analyses`: `requested_by_user_id` cleared, row retained." The
    analysis itself is derived from a public match record and shown to every viewer — it is not
    the requester's personal data, so it survives with only the requester link removed."""
    user = await _seed_linked_user(
        db_session, profile_id=_OWNER_PROFILE_ID, steam_id64="76561197960280010"
    )
    db_session.add(AoeProfile(profile_id=_OTHER_USERS_PROFILE_ID, alias="POV", country="FR"))
    db_session.add(
        Match(
            game_id=_ANALYSIS_GAME_ID,
            leaderboard_id=3,
            completed_at=datetime.now(UTC) - timedelta(days=2),
            source="relic",
            raw_payload={},
        )
    )
    await db_session.flush()
    db_session.add(
        MatchAnalysis(
            game_id=_ANALYSIS_GAME_ID,
            state=MatchAnalysisState.PUBLISHED,
            point_of_view_profile_id=_OTHER_USERS_PROFILE_ID,
            parser_name="aoe2rec-py",
            parser_version="1.0.0",
            requested_by_user_id=user.id,
            requested_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            result_key=f"analyses/{_ANALYSIS_GAME_ID}/{_OTHER_USERS_PROFILE_ID}.json",
        )
    )
    await db_session.commit()

    await _sign_in(client, db_session, user)
    _install_recording_object_store(client)
    token = _get_confirmation_token(client)
    response = client.post(_ERASE_PATH, json={"confirmation_token": token})
    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    analysis_after = await db_session.get(MatchAnalysis, _ANALYSIS_GAME_ID)
    assert analysis_after is not None, "the published analysis row must be retained"
    assert analysis_after.state == MatchAnalysisState.PUBLISHED, (
        "erasing the requester must not change the analysis's own state"
    )
    assert analysis_after.result_key is not None, (
        "the published result must remain reachable after the requester is erased"
    )
    assert analysis_after.requested_by_user_id is None, (
        "who asked for the analysis is the requester's own data and must be cleared"
    )


@pytest.mark.xfail(strict=True, reason="T091 not implemented yet")
async def test_confirmed_erasure_keeps_retained_recordings_whole(
    client: TestClient, db_session: AsyncSession
) -> None:
    """003 data-model.md and T091's own task text: "`retained_recordings` kept, because erasing
    the requester removes a link and not a subject and a published analysis must stay
    recomputable (constitution IV)." Both the row and the object it points at must survive the
    requester's own erasure untouched — the contrast case against the capture object the test
    above proves *is* deleted."""
    user = await _seed_linked_user(
        db_session, profile_id=_OWNER_PROFILE_ID, steam_id64="76561197960280011"
    )
    db_session.add(
        Match(
            game_id=_RETAINED_GAME_ID,
            leaderboard_id=3,
            completed_at=datetime.now(UTC) - timedelta(days=400),
            source="relic",
            raw_payload={},
        )
    )
    await db_session.commit()

    retained_object_key = f"retained/{_RETAINED_GAME_ID}/{_OTHER_USERS_PROFILE_ID}"
    db_session.add(
        RetainedRecording(
            game_id=_RETAINED_GAME_ID,
            profile_id=_OTHER_USERS_PROFILE_ID,
            object_key=retained_object_key,
            zip_bytes=871_503,
            zip_sha256="b" * 64,
            requested_by_user_id=user.id,
        )
    )
    await db_session.commit()

    await _sign_in(client, db_session, user)
    store = _install_recording_object_store(client)
    await store.put(retained_object_key, b"FAKE-RETAINED-RECORDING-BYTES")

    token = _get_confirmation_token(client)
    response = client.post(_ERASE_PATH, json={"confirmation_token": token})
    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    retained_after = (
        await db_session.execute(
            select(RetainedRecording).where(RetainedRecording.object_key == retained_object_key)
        )
    ).scalar_one_or_none()
    assert retained_after is not None, (
        "the retained_recordings row must survive the requester's own erasure — a published "
        "analysis must stay recomputable (constitution IV)"
    )
    assert retained_after.requested_by_user_id is None, (
        "the requester link is cleared even though the recording itself is kept"
    )

    remaining_keys = await store.list_keys()
    assert retained_object_key in remaining_keys, (
        "the retained recording's own object must never be deleted by erasing the requester — "
        f"bucket holds: {remaining_keys}"
    )


# ================================================================================================
# The accountability record itself (data-model.md's `data_requests` section, SC-008)
# ================================================================================================


@pytest.mark.xfail(strict=True, reason="T091 not implemented yet")
async def test_confirmed_erasure_leaves_a_completed_data_request_with_the_subject_nulled(
    client: TestClient, db_session: AsyncSession
) -> None:
    """data-model.md: "this row is the accountability record for the erasure itself and must
    survive it" — `subject_user_id` is nulled (`ondelete="SET NULL"`), never cascaded, so SC-008's
    own requirement that the request be "verifiably resolved even once the subject is gone" has
    something to point at."""
    user = await _seed_linked_user(
        db_session, profile_id=_OWNER_PROFILE_ID, steam_id64="76561197960280012"
    )
    await _sign_in(client, db_session, user)
    _install_recording_object_store(client)
    token = _get_confirmation_token(client)

    response = client.post(_ERASE_PATH, json={"confirmation_token": token})
    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    erasure_requests = (
        (
            await db_session.execute(
                select(DataRequest).where(DataRequest.kind == DataRequestKind.ERASURE)
            )
        )
        .scalars()
        .all()
    )
    assert len(erasure_requests) == 1, (
        "the erasure must leave exactly one data_requests row of kind 'erasure' as its own trace"
    )
    request = erasure_requests[0]
    assert request.subject_user_id is None, (
        "the subject is gone by the time this row is read — it must be nulled, not left dangling "
        "or cascaded away with the user it once named"
    )
    assert request.completed_at is not None, (
        "SC-008: the request must be verifiably resolved, not merely opened"
    )
