"""Integration test for `GET /api/replays/{game_id}/download` (T066), implemented at T071 —
`contracts/http-api.md`: "302 to a short-lived signed URL. Writes `replay_access_log` (FR-040)",
and "The bucket is never public. A download is always a freshly signed URL with a short expiry,
because a replay contains other players' gameplay and chat."

Follows `test_replay_status.py`'s harness conventions verbatim: `client`/`db_session` against the
real throwaway database (`conftest.py`), a `sessions` row inserted directly and signed exactly as
`security.issue_session_cookie` would, and `pytestmark`'s `environment` fixture for the full
18-key settings surface every router built on `SettingsDep` requires.

**Never a public bucket, proven rather than assumed.** `conftest.py`'s shared `_FakeObjectStore`
now carries a `signed_get_url` that deterministically encodes `key` and `expires_in` into the
returned string (T066): the redirect target can only carry that shape if the router asked the
object store to sign it, never if it built a bucket URL by hand. A raw `{endpoint}/{bucket}/{key}`
would not match `_FAKE_SIGNED_PREFIX` and would fail every assertion below.

---

**T335 (003) below**: `GET /api/matches/{game_id}/replay/{profile_id}` — `contracts/http-api.md`'s
"Recorded games, per point of view" table, quickstart.md scenario 6, and the per-participant
`replay` object `GET /api/matches/{game_id}` gains alongside it. This is a *different* route from
001's `GET /api/replays/{game_id}/download` above: 001's route is the caller's own dashboard
download by `game_id` alone; this one is reachable for *any* participant's point of view of *any*
match, `profile_id` named explicitly, which is the whole of US3 (FR-023).

Two implementing tasks split this file's markers. `routers/replays.py` (already registered by
`app.py`) gains the new route at **T337**; `routers/matches.py`'s existing `GET /api/matches/
{game_id}` gains the per-participant `replay` object at **T338**, wiring `download_path` and
`obtainable_until` onto the response `test_match_detail.py` already exercises. Both tasks touch
code that exists today — `replays.py` and `matches.py` are real modules with real routes already —
so every test below calls through `client` exactly like the tests above it; nothing is imported
from either module at module scope or inside a test body, because there is nothing missing to
import, only a route and a response field not yet present. `xfail(strict=True, reason="T338 not
implemented yet")` marks the one test about the match-detail `replay` object; every other test
below carries `reason="T337 not implemented yet"` — see each test's own marker.

`obtainable_until` is asserted `null` throughout, never a date: FR-024 was amended 2026-08-29 —
the source's retention window is contradicted and unresolved (`research.md` R8) — so no promise
about a future date may be derived from a window that may not be the real one. That amendment is
independent of T337/T338 and is asserted here because SC-004 is explicitly not claimable while it
stands (R8's own words), which this file's assertions must not contradict by asserting a date.

`_T335_AOEMS_HOST`, `_FakeAoemsUpstream` and `_install_fake_aoems_upstream` mirror
`test_third_party_history.py`'s own `_RELIC_HOST`/`_FakeRelicMatchHistoryUpstream` seam — the
provider a router builds privately (`AoemsReplayProvider`, `packages/providers/src/
aoe2stats_providers/aoems/provider.py`) has no `Depends()` this file could override, so the one
seam through which a real, unmodified download call can be driven end to end is `httpx.AsyncClient.
send`, intercepted by host.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api import ratelimit, security
from aoe2stats_api.deps import get_object_store
from aoe2stats_api.settings import get_settings
from aoe2stats_storage.models import (
    Alert,
    AlertKind,
    AoeProfile,
    CaptureSource,
    CaptureStatus,
    Match,
    MatchPlayer,
    ProfileLink,
    ReplayAccessLog,
    ReplayCapture,
    ReplayFetchMiss,
    RetainedRecording,
    SteamIdentity,
    User,
)
from aoe2stats_storage.models import Session as UserSession

pytestmark = [pytest.mark.usefixtures("environment")]

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
    user = User(allowlisted_at=now)
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


# ================================================================================================
# T335 (003) — `GET /api/matches/{game_id}/replay/{profile_id}` and the match-detail `replay`
# object
# ================================================================================================

#: The one host `AoemsReplayProvider` ever calls (`packages/providers/src/aoe2stats_providers/
#: aoems/provider.py`'s own `AOEMS_BASE_URL`) — the interception seam below is keyed on it exactly
#: as `test_third_party_history.py`'s `_RELIC_HOST` keys its own.
_T335_AOEMS_HOST = "aoe.ms"

_T335_OWNER_PROFILE_ID = 850_200_001
_T335_PARTICIPANT_A_PROFILE_ID = 850_200_002
_T335_PARTICIPANT_B_PROFILE_ID = 850_200_003

_T335_MATCH_DETAIL_GAME_ID = 850_100_001
_T335_ARCHIVED_GAME_ID = 850_100_002
_T335_OBTAINABLE_GAME_ID = 850_100_003
_T335_EXPIRED_GAME_ID = 850_100_004
_T335_BOUNDARY_RACE_GAME_ID = 850_100_005
_T335_RATE_LIMIT_GAME_ID = 850_100_006
_T335_SOURCE_REFUSAL_GAME_ID_BASE = 850_100_100
#: Finding A remediation (rate limit rolled back on every refused path) — a clean refusal (no
#: outbound call) and the boundary-race refusal (a real outbound call) each get their own game,
#: so exhausting the limit on one never interferes with the other.
_T335_RATE_LIMIT_REFUSED_GAME_ID = 850_100_007
_T335_RATE_LIMIT_BOUNDARY_RACE_GAME_ID = 850_100_008
#: Finding B remediation (no participation check) — a match that exists, with a `profile_id` that
#: never played in it: one already known to `aoe_profiles` and one that is not known at all.
_T335_NON_PARTICIPANT_GAME_ID = 850_100_009
_T335_UNKNOWN_PROFILE_GAME_ID = 850_100_010

#: Finding B: a profile registered in `aoe_profiles` (the common case — every opponent ever
#: ingested lives there) but never a `match_players` row for the games above.
_T335_NON_PARTICIPANT_PROFILE_ID = 850_200_004
#: Finding B: a profile absent from `aoe_profiles` entirely — the FK-violation case.
_T335_UNKNOWN_PROFILE_ID = 850_200_005

#: The 2026-08-29 remediation below: a browser navigation that fails must answer a `303` back to
#: the match page, never the raw JSON body an API caller still gets — its own games, so exhausting
#: a rate-limit window or racing the boundary in one of these tests never interferes with another.
_T335_BROWSER_EXPIRED_GAME_ID = 850_100_011
_T335_BROWSER_RATE_LIMIT_GAME_ID = 850_100_012
_T335_BROWSER_BOUNDARY_RACE_GAME_ID = 850_100_013

#: L13 remediation: `_is_browser_navigation`'s `Accept: text/html` fallback (no `Sec-Fetch-Mode`
#: header at all) and the negative case that matters most — a same-origin `fetch` sends `Sec-Fetch-
#: Mode: cors`, never `navigate`, and must get JSON, not a redirect.
_T335_ACCEPT_HTML_FALLBACK_GAME_ID = 850_100_014
_T335_CORS_FETCH_GAME_ID = 850_100_015

#: FR-024, amended 2026-08-29 (`research.md` R8): a match old enough to be `expired` under either
#: the ~31-day rolling reading or the contradicted six-month epoch reading — the derivation stays
#: conservative under either, so a match this old renders `expired` whichever the open question
#: eventually settles.
_T335_DEFINITELY_EXPIRED_AGE = timedelta(days=400)

#: Comfortably inside every credible reading of the retention window.
_T335_DEFINITELY_OBTAINABLE_AGE = timedelta(days=2)


async def _seed_bare_user(db_session: AsyncSession) -> User:
    """A signed-in user with no linked profile at all. Downloading a third party's `obtainable`
    point of view needs no ownership of anything — US3's own independent test opens "a recent
    third-party match" as any signed-in user, never only a participant."""
    user = User(allowlisted_at=datetime.now(UTC))
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    return user


async def _seed_participant_profile(
    db_session: AsyncSession, *, profile_id: int, alias: str
) -> None:
    db_session.add(AoeProfile(profile_id=profile_id, alias=alias, country="FR"))


async def _seed_open_match(
    db_session: AsyncSession, *, game_id: int, completed_at: datetime
) -> None:
    """A bare `matches` row with no capture and no participant — callers add
    `_seed_participant_profile`/`MatchPlayer` rows on top as each test needs them."""
    db_session.add(
        Match(
            game_id=game_id,
            leaderboard_id=3,
            completed_at=completed_at,
            source="relic",
            raw_payload={},
        )
    )


async def _seed_match_player(db_session: AsyncSession, *, game_id: int, profile_id: int) -> None:
    """A bare `match_players` row for `(game_id, profile_id)` — Finding B remediation: the T337
    route now requires this row before it will derive any availability state at all, so every test
    below that exercises a real participant's point of view seeds it explicitly (`profile_id`
    itself must already exist in `aoe_profiles`, the FK `match_players.profile_id` carries)."""
    db_session.add(MatchPlayer(game_id=game_id, profile_id=profile_id))


class _FakeAoemsUpstream:
    """Answers every `GET https://aoe.ms/replay/?gameId=&profileId=` call with a fixed
    `httpx.Response`, counting how many times it was actually called — mirrors
    `test_third_party_history.py`'s own `_FakeRelicMatchHistoryUpstream`, the identical seam for a
    router that builds its provider privately rather than through a FastAPI `Depends()` this file
    could override."""

    def __init__(self, response: httpx.Response) -> None:
        self._response = response
        self.request_count = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.request_count += 1
        return self._response


def _install_fake_aoems_upstream(monkeypatch: pytest.MonkeyPatch, fake: _FakeAoemsUpstream) -> None:
    async def fake_send(
        self: httpx.AsyncClient, request: httpx.Request, **kwargs: object
    ) -> httpx.Response:
        if request.url.host != _T335_AOEMS_HOST:
            raise AssertionError(f"unexpected outbound request to {request.url}")
        return fake(request)

    monkeypatch.setattr(httpx.AsyncClient, "send", fake_send)


class _TrackingObjectStore:
    """A `get_object_store` override that records every `put`, unlike `conftest.py`'s shared
    `_FakeObjectStore` (T066), which implements only `list_keys` and `signed_get_url`. FR-027's
    "stores nothing" needs the write path observed, not merely absent by omission — a fake with no
    `put` at all would make a router that mistakenly calls it fail with a bare `AttributeError`
    instead of a assertion this file can name.
    """

    def __init__(self) -> None:
        self.put_calls: list[str] = []

    async def list_keys(self, prefix: str = "") -> list[str]:
        return list(self.put_calls)

    async def signed_get_url(self, key: str, *, expires_in: int = 300) -> str:
        return f"https://fake-object-store.example/signed/{key}?expires_in={expires_in}"

    async def put(self, key: str, body: bytes, *, content_type: str = "application/zip") -> None:
        self.put_calls.append(key)

    async def get(self, key: str) -> bytes:
        raise AssertionError(f"unexpected object-store read of {key!r} during a plain download")

    async def delete(self, key: str) -> None:
        raise AssertionError(f"unexpected object-store delete of {key!r} during a plain download")


def _freeze_rate_limit_clock(monkeypatch: pytest.MonkeyPatch, *, moment: datetime) -> None:
    """Pins the clock `ratelimit.check_and_increment` reads to a single, fixed `moment` for the
    rest of a test — mirrors `test_players_routes.py`'s own `_freeze_rate_limiter_clock` byte for
    byte (its own docstring explains why a real-time loop can otherwise race an epoch-aligned
    window boundary)."""

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> datetime:
            return moment if tz is None else moment.astimezone(tz)

    monkeypatch.setattr(ratelimit, "datetime", _FrozenDateTime)


async def test_match_detail_replay_object_offers_one_download_per_participant_point_of_view(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-023, quickstart scenario 6.1: `GET /api/matches/{game_id}` carries a per-participant
    `replay` object (`contracts/http-api.md`'s "Recorded games, per point of view" table) — one
    entry per participant, never more, never fewer. The caller's own archived point of view reads
    `archived`; a co-participant with no archive, in the same match still inside the retention
    window, reads `obtainable`. `obtainable_until` is `null` for every entry regardless of state —
    FR-024's 2026-08-29 amendment (module docstring): no date may be derived while the source's
    retention window is contradicted and unresolved (`research.md` R8).
    """
    game_id = _T335_MATCH_DETAIL_GAME_ID
    owner = await _seed_linked_profile(
        db_session, profile_id=_T335_OWNER_PROFILE_ID, steam_id64="76561197960287950"
    )
    await _seed_participant_profile(
        db_session, profile_id=_T335_PARTICIPANT_A_PROFILE_ID, alias="ParticipantA"
    )
    await _seed_participant_profile(
        db_session, profile_id=_T335_PARTICIPANT_B_PROFILE_ID, alias="ParticipantB"
    )
    await db_session.commit()

    object_key = f"replays/{game_id}/{_T335_OWNER_PROFILE_ID}.zip"
    await _seed_stored_capture(
        db_session, game_id=game_id, profile_id=_T335_OWNER_PROFILE_ID, object_key=object_key
    )

    for profile_id, team_id, result in (
        (_T335_OWNER_PROFILE_ID, 1, "win"),
        (_T335_PARTICIPANT_A_PROFILE_ID, 2, "loss"),
        (_T335_PARTICIPANT_B_PROFILE_ID, 2, "loss"),
    ):
        db_session.add(
            MatchPlayer(
                game_id=game_id,
                profile_id=profile_id,
                team_id=team_id,
                civ_id=1,
                color_id=1,
                result=result,
                rating=1500,
                rating_diff=10,
            )
        )
    await db_session.commit()

    await _sign_in(client, db_session, owner)
    response = client.get(f"/api/matches/{game_id}")
    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    participants = response.json()["participants"]
    assert len(participants) == 3
    replay_by_profile = {p["profile_id"]: p.get("replay") for p in participants}
    assert set(replay_by_profile) == {
        _T335_OWNER_PROFILE_ID,
        _T335_PARTICIPANT_A_PROFILE_ID,
        _T335_PARTICIPANT_B_PROFILE_ID,
    }, "FR-023: one download offered per participant point of view, never more, never fewer"

    for profile_id, replay in replay_by_profile.items():
        assert replay is not None, f"missing `replay` object for participant {profile_id}"
        assert replay["profile_id"] == profile_id
        assert replay["obtainable_until"] is None, (
            "FR-024, amended 2026-08-29: obtainable_until must be null while the retention "
            "window is unresolved (research.md R8), for every state"
        )

    owner_replay = replay_by_profile[_T335_OWNER_PROFILE_ID]
    assert owner_replay["availability"] == "archived"
    assert (
        owner_replay["download_path"] == f"/api/matches/{game_id}/replay/{_T335_OWNER_PROFILE_ID}"
    )

    for profile_id in (_T335_PARTICIPANT_A_PROFILE_ID, _T335_PARTICIPANT_B_PROFILE_ID):
        other_replay = replay_by_profile[profile_id]
        assert other_replay["availability"] == "obtainable"
        assert other_replay["download_path"] == f"/api/matches/{game_id}/replay/{profile_id}"


async def test_archived_point_of_view_is_served_from_the_archive_and_logs_access(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-026, FR-029, quickstart scenario 6.4: the caller's own archived point of view is served
    through this new, per-participant path exactly as 001's own `GET /api/replays/{game_id}/
    download` above is — a 302 to a freshly signed, short-expiry URL, never a bare bucket URL —
    and the access is logged. `replay_access_log` was widened by 003 to carry a nullable
    `retained_recording_id` alongside `replay_capture_id` (data-model.md); this row must set the
    first and leave the second null, since an archived download is never a read of a
    `retained_recordings` row (R8, R9)."""
    game_id = _T335_ARCHIVED_GAME_ID
    owner = await _seed_linked_profile(
        db_session, profile_id=_T335_OWNER_PROFILE_ID, steam_id64="76561197960287951"
    )
    await _sign_in(client, db_session, owner)
    object_key = f"replays/{game_id}/{_T335_OWNER_PROFILE_ID}.zip"
    capture = await _seed_stored_capture(
        db_session, game_id=game_id, profile_id=_T335_OWNER_PROFILE_ID, object_key=object_key
    )
    await _seed_match_player(db_session, game_id=game_id, profile_id=_T335_OWNER_PROFILE_ID)
    await db_session.commit()

    response = client.get(
        f"/api/matches/{game_id}/replay/{_T335_OWNER_PROFILE_ID}", follow_redirects=False
    )

    assert response.status_code == 302, f"Got {response.status_code}: {response.text}"
    key, expires_in = _decode_signed_url(response.headers["location"])
    assert key == object_key
    assert 1 <= expires_in <= _MAX_SIGNED_URL_EXPIRES_IN_SECONDS

    log_result = await db_session.execute(
        select(ReplayAccessLog).where(ReplayAccessLog.replay_capture_id == capture.id)
    )
    log_rows = log_result.scalars().all()
    assert len(log_rows) == 1, "FR-029: every access to an archived point of view must be logged"
    assert log_rows[0].user_id == owner.id
    assert log_rows[0].retained_recording_id is None, (
        "R9/FR-048: an archived download logs against replay_captures, never retained_recordings"
    )


async def test_obtainable_point_of_view_is_streamed_and_stores_nothing(
    client: TestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-023, FR-027, SC-009, quickstart scenario 6.3: a point of view this service has not
    archived is fetched from the source and streamed straight through to the caller. "Stores
    nothing" is asserted, not assumed: zero new object-store writes (via `_TrackingObjectStore`,
    substituted for `conftest.py`'s shared `_FakeObjectStore`, which cannot observe a `put` at
    all) and zero new `retained_recordings` rows — downloading is not analysing, and constitution
    IX permits retention only where a person deliberately asks for a match to be analysed
    (FR-033), which a download request is not.
    """
    game_id = _T335_OBTAINABLE_GAME_ID
    caller = await _seed_bare_user(db_session)
    await _sign_in(client, db_session, caller)
    await _seed_participant_profile(
        db_session, profile_id=_T335_PARTICIPANT_A_PROFILE_ID, alias="Obtainable"
    )
    await _seed_open_match(
        db_session,
        game_id=game_id,
        completed_at=datetime.now(UTC) - _T335_DEFINITELY_OBTAINABLE_AGE,
    )
    await _seed_match_player(db_session, game_id=game_id, profile_id=_T335_PARTICIPANT_A_PROFILE_ID)
    await db_session.commit()

    fake_bytes = b"FAKE-AOE2RECORD-ZIP-BYTES-FOR-T335"
    fake_upstream = _FakeAoemsUpstream(
        httpx.Response(
            200,
            content=fake_bytes,
            headers={
                "content-disposition": f"attachment; filename=AgeIIDE_Replay_{game_id}.zip",
                "content-type": "application/zip",
            },
        )
    )
    _install_fake_aoems_upstream(monkeypatch, fake_upstream)

    tracking_store = _TrackingObjectStore()
    # `client.app` is typed as a bare ASGI app by `starlette.testclient.TestClient` — the concrete
    # `FastAPI` instance `conftest.py`'s own `client` fixture builds always carries
    # `dependency_overrides`, which is why every other test in this suite family reaches for it
    # the same way (`test_configuration_envelope.py`, `test_index_entrypoint.py`).
    client.app.dependency_overrides[get_object_store] = lambda: tracking_store  # type: ignore[attr-defined]

    response = client.get(f"/api/matches/{game_id}/replay/{_T335_PARTICIPANT_A_PROFILE_ID}")

    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"
    assert response.content == fake_bytes

    assert tracking_store.put_calls == [], (
        "FR-027: downloading is not analysing — a recording obtained solely to serve a download "
        "must store zero new bytes"
    )

    retained_count = (
        await db_session.execute(
            select(func.count())
            .select_from(RetainedRecording)
            .where(RetainedRecording.game_id == game_id)
        )
    ).scalar_one()
    assert retained_count == 0, (
        "FR-027/SC-009: zero new retained_recordings rows for a plain download"
    )


async def test_expired_point_of_view_answers_404_with_a_distinguishing_code(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-025: a point of view whose match completed outside the retention window answers `404`
    with a `code` that names the reason as `expired` — distinct from `never_recorded`, proven
    alongside it below."""
    game_id = _T335_EXPIRED_GAME_ID
    caller = await _seed_bare_user(db_session)
    await _sign_in(client, db_session, caller)
    await _seed_participant_profile(
        db_session, profile_id=_T335_PARTICIPANT_A_PROFILE_ID, alias="ExpiredPointOfView"
    )
    await _seed_open_match(
        db_session, game_id=game_id, completed_at=datetime.now(UTC) - _T335_DEFINITELY_EXPIRED_AGE
    )
    await _seed_match_player(db_session, game_id=game_id, profile_id=_T335_PARTICIPANT_A_PROFILE_ID)
    await db_session.commit()

    response = client.get(f"/api/matches/{game_id}/replay/{_T335_PARTICIPANT_A_PROFILE_ID}")

    assert response.status_code == 404, f"Got {response.status_code}: {response.text}"
    assert response.json()["error"]["code"] == "expired"


async def test_obtainable_point_of_view_that_404s_at_fetch_time_becomes_never_recorded(
    client: TestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-025's own edge case, quickstart scenario 6 and `contracts/http-api.md`'s "boundary
    race" paragraph (`research.md` R8): a point of view offered as `obtainable` that answers 404
    at the source when actually fetched is `expired_since_page_load` — never conflated with
    `never_recorded`, which means the source never had it at all (R8's derivation table). The
    call also *records* the outcome, so the identical request the next moment answers
    `never_recorded` instead of repeating the same 404 as a fresh surprise: "That call also
    records the outcome, so the page is right the next time" (contracts/http-api.md). This is
    also this file's proof that `expired` (the window closed, tested above),
    `expired_since_page_load` (it closed between page load and click) and `never_recorded` (the
    source never had it) are three distinct codes, never any two of them conflated.
    """
    game_id = _T335_BOUNDARY_RACE_GAME_ID
    caller = await _seed_bare_user(db_session)
    await _sign_in(client, db_session, caller)
    await _seed_participant_profile(
        db_session, profile_id=_T335_PARTICIPANT_A_PROFILE_ID, alias="BoundaryRace"
    )
    await _seed_open_match(
        db_session,
        game_id=game_id,
        completed_at=datetime.now(UTC) - _T335_DEFINITELY_OBTAINABLE_AGE,
    )
    await _seed_match_player(db_session, game_id=game_id, profile_id=_T335_PARTICIPANT_A_PROFILE_ID)
    await db_session.commit()

    fake_upstream = _FakeAoemsUpstream(httpx.Response(404, text="Not Found"))
    _install_fake_aoems_upstream(monkeypatch, fake_upstream)

    first = client.get(f"/api/matches/{game_id}/replay/{_T335_PARTICIPANT_A_PROFILE_ID}")
    assert first.status_code == 404, f"Got {first.status_code}: {first.text}"
    first_code = first.json()["error"]["code"]
    assert first_code == "expired_since_page_load", (
        "a recording offered as obtainable that 404s at fetch time must say so, distinctly from "
        "never having been recorded at all"
    )

    second = client.get(f"/api/matches/{game_id}/replay/{_T335_PARTICIPANT_A_PROFILE_ID}")
    assert second.status_code == 404, f"Got {second.status_code}: {second.text}"
    second_code = second.json()["error"]["code"]
    assert second_code == "never_recorded", (
        "the first call's outcome must be recorded, so the identical request answers "
        "never_recorded rather than expired_since_page_load a second time"
    )
    assert second_code != first_code
    assert second_code != "expired", (
        "never_recorded (the source never had it) and expired (the window closed) are FR-025's "
        "two distinct unobtainable reasons and must never share a code"
    )


async def test_replay_download_rate_limit_applies_per_user(
    client: TestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-028's first half, R10: past `REPLAY_DOWNLOAD_MAX_PER_USER_PER_MINUTE`, the route
    answers `rate_limited` with a `retry_after` — the identical envelope
    `test_players_routes.py`'s own `test_search_rate_limits_per_user_and_answers_retry_after`
    proves for the `search` bucket, now proven for the `replay_download` bucket
    (data-model.md's `rate_limit_counters` section names both)."""
    game_id = _T335_RATE_LIMIT_GAME_ID
    owner = await _seed_linked_profile(
        db_session, profile_id=_T335_OWNER_PROFILE_ID, steam_id64="76561197960287952"
    )
    await _sign_in(client, db_session, owner)
    object_key = f"replays/{game_id}/{_T335_OWNER_PROFILE_ID}.zip"
    await _seed_stored_capture(
        db_session, game_id=game_id, profile_id=_T335_OWNER_PROFILE_ID, object_key=object_key
    )
    await _seed_match_player(db_session, game_id=game_id, profile_id=_T335_OWNER_PROFILE_ID)
    await db_session.commit()

    #: `REPLAY_DOWNLOAD_MAX_PER_USER_PER_MINUTE`'s own window (R10: a fixed window, per bucket).
    window_seconds = 60
    window_start = ratelimit._window_start(datetime.now(UTC), window_seconds)
    _freeze_rate_limit_clock(
        monkeypatch, moment=window_start + timedelta(seconds=window_seconds // 2)
    )

    limit = get_settings().replay_download_max_per_user_per_minute

    for attempt in range(limit):
        response = client.get(
            f"/api/matches/{game_id}/replay/{_T335_OWNER_PROFILE_ID}", follow_redirects=False
        )
        assert response.status_code == 302, (
            f"call {attempt + 1} of {limit} should still be within the limit. Got "
            f"{response.status_code}: {response.text}"
        )

    limited = client.get(
        f"/api/matches/{game_id}/replay/{_T335_OWNER_PROFILE_ID}", follow_redirects=False
    )
    assert limited.status_code == 429, (
        f"the call past the configured limit of {limit} must be refused. Got "
        f"{limited.status_code}: {limited.text}"
    )
    limited_body = limited.json()
    assert limited_body["error"]["code"] == "rate_limited"
    assert isinstance(limited_body["error"]["detail"].get("retry_after"), int)
    assert limited_body["error"]["detail"]["retry_after"] > 0


async def test_replay_download_rate_limit_applies_on_a_refused_path(
    client: TestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Finding A: the limit must be reached by a refusal too, not only by the `archived` success
    path `test_replay_download_rate_limit_applies_per_user` above proves. An `expired` point of
    view is the clean refusal case — it makes no outbound call at all — so a counter that only
    survives on a success path (`check_and_increment`'s own docstring: it "does not commit"; every
    refusal this route raises is an `APIError`, and `deps.py`'s `session_scope` rolls `db_session`'s
    whole transaction back the moment one propagates) would let this loop repeat `expired` forever
    and never reach `429`."""
    game_id = _T335_RATE_LIMIT_REFUSED_GAME_ID
    caller = await _seed_bare_user(db_session)
    await _sign_in(client, db_session, caller)
    await _seed_participant_profile(
        db_session, profile_id=_T335_PARTICIPANT_A_PROFILE_ID, alias="RateLimitRefused"
    )
    await _seed_open_match(
        db_session, game_id=game_id, completed_at=datetime.now(UTC) - _T335_DEFINITELY_EXPIRED_AGE
    )
    await _seed_match_player(db_session, game_id=game_id, profile_id=_T335_PARTICIPANT_A_PROFILE_ID)
    await db_session.commit()

    window_seconds = 60
    window_start = ratelimit._window_start(datetime.now(UTC), window_seconds)
    _freeze_rate_limit_clock(
        monkeypatch, moment=window_start + timedelta(seconds=window_seconds // 2)
    )

    limit = get_settings().replay_download_max_per_user_per_minute

    for attempt in range(limit):
        response = client.get(f"/api/matches/{game_id}/replay/{_T335_PARTICIPANT_A_PROFILE_ID}")
        assert response.status_code == 404, (
            f"call {attempt + 1} of {limit} should still be within the limit. Got "
            f"{response.status_code}: {response.text}"
        )
        assert response.json()["error"]["code"] == "expired"

    limited = client.get(f"/api/matches/{game_id}/replay/{_T335_PARTICIPANT_A_PROFILE_ID}")
    assert limited.status_code == 429, (
        f"the call past the configured limit of {limit} must be refused, even though every prior "
        f"call was itself a refusal. Got {limited.status_code}: {limited.text}"
    )
    assert limited.json()["error"]["code"] == "rate_limited"


async def test_boundary_race_path_still_consumes_the_rate_limit(
    client: TestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Finding A's deepest case: the boundary-race path makes a real outbound call to `aoe.ms`
    before answering 404 (`contracts/http-api.md`'s boundary-race paragraph) — that outbound call
    is exactly the "unmetered third-party traffic driven by user input" constitution I forbids if
    its own counter is then rolled back. Only the first call in this loop actually reaches the
    source (`_record_fetch_miss` makes every later call for the same pair answer `never_recorded`
    from the recorded row instead); every call, including that first one, must still count toward
    the limit."""
    game_id = _T335_RATE_LIMIT_BOUNDARY_RACE_GAME_ID
    caller = await _seed_bare_user(db_session)
    await _sign_in(client, db_session, caller)
    await _seed_participant_profile(
        db_session, profile_id=_T335_PARTICIPANT_A_PROFILE_ID, alias="RateLimitBoundaryRace"
    )
    await _seed_open_match(
        db_session,
        game_id=game_id,
        completed_at=datetime.now(UTC) - _T335_DEFINITELY_OBTAINABLE_AGE,
    )
    await _seed_match_player(db_session, game_id=game_id, profile_id=_T335_PARTICIPANT_A_PROFILE_ID)
    await db_session.commit()

    fake_upstream = _FakeAoemsUpstream(httpx.Response(404, text="Not Found"))
    _install_fake_aoems_upstream(monkeypatch, fake_upstream)

    window_seconds = 60
    window_start = ratelimit._window_start(datetime.now(UTC), window_seconds)
    _freeze_rate_limit_clock(
        monkeypatch, moment=window_start + timedelta(seconds=window_seconds // 2)
    )

    limit = get_settings().replay_download_max_per_user_per_minute

    for attempt in range(limit):
        response = client.get(f"/api/matches/{game_id}/replay/{_T335_PARTICIPANT_A_PROFILE_ID}")
        assert response.status_code == 404, (
            f"call {attempt + 1} of {limit} should still be within the limit. Got "
            f"{response.status_code}: {response.text}"
        )

    limited = client.get(f"/api/matches/{game_id}/replay/{_T335_PARTICIPANT_A_PROFILE_ID}")
    assert limited.status_code == 429, (
        f"the call past the configured limit of {limit} must be refused, even though the very "
        f"first of those calls made a real outbound call to the source. Got "
        f"{limited.status_code}: {limited.text}"
    )
    assert limited.json()["error"]["code"] == "rate_limited"
    assert fake_upstream.request_count == 1, (
        "only the first call actually reaches the source (later calls read the recorded fetch "
        "miss instead) — the rate limit still applies to every one of them regardless"
    )


@pytest.mark.parametrize("source_status", [403, 429])
async def test_source_refusal_stops_the_request_and_raises_a_rate_limited_alert(
    client: TestClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    source_status: int,
) -> None:
    """FR-028's second half, 001 FR-021: a throttling or refusal signal from the source (a 429,
    or an unexpected 403 — `AoemsReplayProvider`'s own module docstring: both are read the same
    way every other provider reads them) stops the request rather than being retried through —
    `AsyncBaseProvider._request` never retries either through its own backoff policy, only a 5xx
    or a timeout reaches it — and raises the identical severity-2 `rate_limited` alert 001's own
    ingester already raises for the same source (`AlertKind.RATE_LIMITED`; data-model.md's own
    "Alert vocabulary" section adds only `analysis_cap_reached` here, so this route must reuse
    the existing kind rather than invent a second one).
    """
    game_id = _T335_SOURCE_REFUSAL_GAME_ID_BASE + source_status
    caller = await _seed_bare_user(db_session)
    await _sign_in(client, db_session, caller)
    await _seed_participant_profile(
        db_session, profile_id=_T335_PARTICIPANT_A_PROFILE_ID, alias="SourceRefusal"
    )
    await _seed_open_match(
        db_session,
        game_id=game_id,
        completed_at=datetime.now(UTC) - _T335_DEFINITELY_OBTAINABLE_AGE,
    )
    await _seed_match_player(db_session, game_id=game_id, profile_id=_T335_PARTICIPANT_A_PROFILE_ID)
    await db_session.commit()

    alerts_before = (await db_session.execute(select(func.count()).select_from(Alert))).scalar_one()

    fake_upstream = _FakeAoemsUpstream(httpx.Response(source_status, text="refused"))
    _install_fake_aoems_upstream(monkeypatch, fake_upstream)

    response = client.get(f"/api/matches/{game_id}/replay/{_T335_PARTICIPANT_A_PROFILE_ID}")

    assert fake_upstream.request_count == 1, (
        f"a {source_status} from the source must stop the request rather than being retried "
        "through (FR-028)"
    )
    assert response.status_code == 429, f"Got {response.status_code}: {response.text}"
    assert response.json()["error"]["code"] == "rate_limited"

    alert_result = await db_session.execute(
        select(Alert).where(Alert.kind == AlertKind.RATE_LIMITED).order_by(Alert.raised_at.desc())
    )
    alert_row = alert_result.scalars().first()
    assert alert_row is not None, (
        "FR-028/001 FR-021: a source throttling or refusal signal must raise a rate_limited alert"
    )
    assert alert_row.severity == 2

    alerts_after = (await db_session.execute(select(func.count()).select_from(Alert))).scalar_one()
    assert alerts_after == alerts_before + 1, "exactly one alert per refused request"


async def test_replay_download_refuses_a_profile_id_that_never_played_the_match(
    client: TestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Finding B: FR-023 offers "one download per participant point of view" — `profile_id` is not
    a free parameter. A `profile_id` this service knows about (registered in `aoe_profiles`, the
    common case since that table holds every opponent ever ingested) but that never played
    `game_id` must answer `404 not_found`, exactly as an unknown `game_id` does, and — the part
    that matters — must never reach the source at all and must never write a `replay_fetch_misses`
    row: without the participation check, a recent match falls through to `obtainable` and this
    route fetches a pair `docs/data-sources.md` documents the source as never meaningfully
    answering for."""
    game_id = _T335_NON_PARTICIPANT_GAME_ID
    caller = await _seed_bare_user(db_session)
    await _sign_in(client, db_session, caller)
    await _seed_participant_profile(
        db_session, profile_id=_T335_NON_PARTICIPANT_PROFILE_ID, alias="NeverPlayedThisMatch"
    )
    await _seed_open_match(
        db_session,
        game_id=game_id,
        completed_at=datetime.now(UTC) - _T335_DEFINITELY_OBTAINABLE_AGE,
    )
    await db_session.commit()

    fake_upstream = _FakeAoemsUpstream(httpx.Response(200, content=b"should never be fetched"))
    _install_fake_aoems_upstream(monkeypatch, fake_upstream)

    response = client.get(f"/api/matches/{game_id}/replay/{_T335_NON_PARTICIPANT_PROFILE_ID}")

    assert response.status_code == 404, f"Got {response.status_code}: {response.text}"
    assert response.json()["error"]["code"] == "not_found"

    assert fake_upstream.request_count == 0, (
        "FR-023: a profile_id that never played this match must never reach the source at all"
    )

    misses_result = await db_session.execute(
        select(ReplayFetchMiss).where(
            ReplayFetchMiss.game_id == game_id,
            ReplayFetchMiss.profile_id == _T335_NON_PARTICIPANT_PROFILE_ID,
        )
    )
    assert misses_result.scalars().first() is None, (
        "a refusal for a non-participant is not a boundary-race 404 and must not be recorded as "
        "evidence of one"
    )


async def test_replay_download_refuses_a_profile_id_unknown_to_aoe_profiles(
    client: TestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Finding B's sharper case: a `profile_id` absent from `aoe_profiles` entirely must still
    answer `404 not_found`, never a `500`. Without the participation check, this pair falls through
    to `obtainable`, the source's 404 drives `_record_fetch_miss`, and that insert violates
    `replay_fetch_misses.profile_id`'s foreign key to `aoe_profiles` — the `IntegrityError` escapes
    the route's own handler and the caller gets a `500` where a `404` was intended
    (`infra/migrations/versions/b7cc0beaab35_replay_fetch_misses.py`)."""
    game_id = _T335_UNKNOWN_PROFILE_GAME_ID
    caller = await _seed_bare_user(db_session)
    await _sign_in(client, db_session, caller)
    await _seed_open_match(
        db_session,
        game_id=game_id,
        completed_at=datetime.now(UTC) - _T335_DEFINITELY_OBTAINABLE_AGE,
    )
    await db_session.commit()

    fake_upstream = _FakeAoemsUpstream(httpx.Response(404, text="Not Found"))
    _install_fake_aoems_upstream(monkeypatch, fake_upstream)

    response = client.get(f"/api/matches/{game_id}/replay/{_T335_UNKNOWN_PROFILE_ID}")

    assert response.status_code == 404, f"Got {response.status_code}: {response.text}"
    assert response.json()["error"]["code"] == "not_found"
    assert fake_upstream.request_count == 0, (
        "FR-023: a profile_id that never played this match must never reach the source at all, "
        "whether or not it is known to aoe_profiles"
    )


# ================================================================================================
# 2026-08-29 remediation — a failure of this route redirects a browser navigation back to the
# match page (`303`) instead of leaving it looking at a raw JSON error page, while an API caller
# keeps getting the identical JSON `404`/`429` these tests above already assert.
# `packages/design-system/specs/replay-availability.md` §5 and §10.
# ================================================================================================


def _browser_navigation_headers() -> dict[str, str]:
    """Mirrors a real `window.location.assign` navigation
    (`apps/web/src/features/replays/api.ts`'s `triggerReplayPointOfViewDownload`) closely enough
    for `routers/replays.py`'s `_is_browser_navigation` to read it as one: every current browser
    engine sets exactly this header on a top-level navigation, and every plain `client.get(...)`
    call in this file above never does — which is the whole of the contrast this suite proves."""
    return {"Sec-Fetch-Mode": "navigate"}


def _assert_absolute_match_page_redirect(location: str, *, game_id: int) -> None:
    """B2 remediation: the `303` this route answers a browser navigation with must be an absolute
    URL rooted at `settings.public_base_url`, never a relative `/matches/{game_id}` — a relative
    redirect from an API route lands on the API's own origin under this repository's own documented
    local topology (`.env.example`'s `PUBLIC_BASE_URL=http://localhost:5173`, a different origin
    from the API), and only ever worked in production because `vercel.json`'s rewrite collapses the
    two. `urlsplit(location).path == f"/matches/{game_id}"` alone (the three assertions this
    remediation replaces) passes for either shape, which is why the bug survived them."""
    public_base_url = get_settings().public_base_url
    assert location.startswith(f"{public_base_url}/matches/{game_id}?"), (
        f"expected an absolute redirect rooted at {public_base_url!r}, got {location!r}"
    )
    split = urlsplit(location)
    assert split.scheme and split.netloc, (
        f"the redirect must be absolute, never a relative /matches/{game_id} path: {location!r}"
    )


async def test_expired_point_of_view_redirects_a_browser_to_the_match_page_with_the_code(
    client: TestClient, db_session: AsyncSession
) -> None:
    """The remediation's own contrast case, in one test: a browser navigation to an `expired`
    point of view gets a `303` back to `/matches/{game_id}` carrying `replay_error=expired` and
    `replay_error_profile_id` — what `apps/web/src/features/replays/MatchDetailContainer.tsx`
    reads on load and renders as `replay-availability.md` §5's row-level alert — while the
    identical failure, asked for without the browser's own Fetch Metadata header, still answers
    the plain JSON `404` `test_expired_point_of_view_answers_404_with_a_distinguishing_code` above
    already proves: the fix must not change what an API caller receives.
    """
    game_id = _T335_BROWSER_EXPIRED_GAME_ID
    caller = await _seed_bare_user(db_session)
    await _sign_in(client, db_session, caller)
    await _seed_participant_profile(
        db_session, profile_id=_T335_PARTICIPANT_A_PROFILE_ID, alias="BrowserExpired"
    )
    await _seed_open_match(
        db_session, game_id=game_id, completed_at=datetime.now(UTC) - _T335_DEFINITELY_EXPIRED_AGE
    )
    await _seed_match_player(db_session, game_id=game_id, profile_id=_T335_PARTICIPANT_A_PROFILE_ID)
    await db_session.commit()

    browser_response = client.get(
        f"/api/matches/{game_id}/replay/{_T335_PARTICIPANT_A_PROFILE_ID}",
        headers=_browser_navigation_headers(),
        follow_redirects=False,
    )

    assert browser_response.status_code == 303, (
        f"Got {browser_response.status_code}: {browser_response.text}"
    )
    location = browser_response.headers["location"]
    _assert_absolute_match_page_redirect(location, game_id=game_id)
    split = urlsplit(location)
    assert split.path == f"/matches/{game_id}"
    query = parse_qs(split.query)
    assert query["replay_error"] == ["expired"]
    assert query["replay_error_profile_id"] == [str(_T335_PARTICIPANT_A_PROFILE_ID)]

    api_response = client.get(f"/api/matches/{game_id}/replay/{_T335_PARTICIPANT_A_PROFILE_ID}")
    assert api_response.status_code == 404, f"Got {api_response.status_code}: {api_response.text}"
    assert api_response.json()["error"]["code"] == "expired", (
        "an API caller (no browser Fetch Metadata header) must keep getting the JSON error this "
        "route always answered, unaffected by the redirect added for a browser navigation"
    )


async def test_rate_limited_download_redirects_a_browser_with_retry_after(
    client: TestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-028's `rate_limited` code, carried through the `303` with its own `retry_after` — the
    exact seconds `replay-availability.md` §5 requires ("never a rounded or invented figure"),
    never simply dropped because this path is a redirect rather than a JSON body."""
    game_id = _T335_BROWSER_RATE_LIMIT_GAME_ID
    owner = await _seed_linked_profile(
        db_session, profile_id=_T335_OWNER_PROFILE_ID, steam_id64="76561197960287953"
    )
    await _sign_in(client, db_session, owner)
    object_key = f"replays/{game_id}/{_T335_OWNER_PROFILE_ID}.zip"
    await _seed_stored_capture(
        db_session, game_id=game_id, profile_id=_T335_OWNER_PROFILE_ID, object_key=object_key
    )
    await _seed_match_player(db_session, game_id=game_id, profile_id=_T335_OWNER_PROFILE_ID)
    await db_session.commit()

    window_seconds = 60
    window_start = ratelimit._window_start(datetime.now(UTC), window_seconds)
    _freeze_rate_limit_clock(
        monkeypatch, moment=window_start + timedelta(seconds=window_seconds // 2)
    )

    limit = get_settings().replay_download_max_per_user_per_minute
    for attempt in range(limit):
        response = client.get(
            f"/api/matches/{game_id}/replay/{_T335_OWNER_PROFILE_ID}", follow_redirects=False
        )
        assert response.status_code == 302, (
            f"call {attempt + 1} of {limit} should still be within the limit. Got "
            f"{response.status_code}: {response.text}"
        )

    limited = client.get(
        f"/api/matches/{game_id}/replay/{_T335_OWNER_PROFILE_ID}",
        headers=_browser_navigation_headers(),
        follow_redirects=False,
    )

    assert limited.status_code == 303, f"Got {limited.status_code}: {limited.text}"
    location = limited.headers["location"]
    _assert_absolute_match_page_redirect(location, game_id=game_id)
    split = urlsplit(location)
    assert split.path == f"/matches/{game_id}"
    query = parse_qs(split.query)
    assert query["replay_error"] == ["rate_limited"]
    assert query["replay_error_profile_id"] == [str(_T335_OWNER_PROFILE_ID)]
    assert query["replay_error_retry_after"][0].isdigit()
    assert int(query["replay_error_retry_after"][0]) > 0


async def test_boundary_race_redirects_a_browser_with_the_distinguishing_code(
    client: TestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The boundary race (`expired_since_page_load`) reaches the browser through the identical
    redirect mechanism, carrying the one code that lets the client render §5's own boundary-race
    sentence — distinct from both the plain `expired` copy and `never_recorded`'s."""
    game_id = _T335_BROWSER_BOUNDARY_RACE_GAME_ID
    caller = await _seed_bare_user(db_session)
    await _sign_in(client, db_session, caller)
    await _seed_participant_profile(
        db_session, profile_id=_T335_PARTICIPANT_A_PROFILE_ID, alias="BrowserBoundaryRace"
    )
    await _seed_open_match(
        db_session,
        game_id=game_id,
        completed_at=datetime.now(UTC) - _T335_DEFINITELY_OBTAINABLE_AGE,
    )
    await _seed_match_player(db_session, game_id=game_id, profile_id=_T335_PARTICIPANT_A_PROFILE_ID)
    await db_session.commit()

    fake_upstream = _FakeAoemsUpstream(httpx.Response(404, text="Not Found"))
    _install_fake_aoems_upstream(monkeypatch, fake_upstream)

    response = client.get(
        f"/api/matches/{game_id}/replay/{_T335_PARTICIPANT_A_PROFILE_ID}",
        headers=_browser_navigation_headers(),
        follow_redirects=False,
    )

    assert response.status_code == 303, f"Got {response.status_code}: {response.text}"
    location = response.headers["location"]
    _assert_absolute_match_page_redirect(location, game_id=game_id)
    split = urlsplit(location)
    assert split.path == f"/matches/{game_id}"
    query = parse_qs(split.query)
    assert query["replay_error"] == ["expired_since_page_load"]
    assert query["replay_error_profile_id"] == [str(_T335_PARTICIPANT_A_PROFILE_ID)]


async def test_expired_point_of_view_with_accept_html_and_no_sec_fetch_mode_redirects(
    client: TestClient, db_session: AsyncSession
) -> None:
    """L13: `_is_browser_navigation`'s `Accept: text/html` fallback, exercised for real — a request
    that carries no `Sec-Fetch-Mode` header at all (a browser, or a network layer in front of one,
    that strips or predates the Fetch Metadata header) but still asks for `text/html` first, exactly
    as a plain navigation always does, must be treated as a browser navigation and get the `303`
    redirect, not the raw JSON body. The three tests above this remediation only ever exercised the
    primary `Sec-Fetch-Mode: navigate` signal or no headers at all; neither reaches this branch."""
    game_id = _T335_ACCEPT_HTML_FALLBACK_GAME_ID
    caller = await _seed_bare_user(db_session)
    await _sign_in(client, db_session, caller)
    await _seed_participant_profile(
        db_session, profile_id=_T335_PARTICIPANT_A_PROFILE_ID, alias="AcceptHtmlFallback"
    )
    await _seed_open_match(
        db_session, game_id=game_id, completed_at=datetime.now(UTC) - _T335_DEFINITELY_EXPIRED_AGE
    )
    await _seed_match_player(db_session, game_id=game_id, profile_id=_T335_PARTICIPANT_A_PROFILE_ID)
    await db_session.commit()

    response = client.get(
        f"/api/matches/{game_id}/replay/{_T335_PARTICIPANT_A_PROFILE_ID}",
        headers={"Accept": "text/html,application/xhtml+xml"},
        follow_redirects=False,
    )

    assert response.status_code == 303, f"Got {response.status_code}: {response.text}"
    location = response.headers["location"]
    _assert_absolute_match_page_redirect(location, game_id=game_id)
    split = urlsplit(location)
    assert split.path == f"/matches/{game_id}"
    query = parse_qs(split.query)
    assert query["replay_error"] == ["expired"]
    assert query["replay_error_profile_id"] == [str(_T335_PARTICIPANT_A_PROFILE_ID)]


async def test_expired_point_of_view_with_sec_fetch_mode_cors_answers_json_never_a_redirect(
    client: TestClient, db_session: AsyncSession
) -> None:
    """L13's negative case, the one that matters most: a same-origin `fetch()` call sends
    `Sec-Fetch-Mode: cors`, never `navigate` — the exact call `apps/web/src/lib/api.ts`'s
    `apiRequest` would make against this route if it ever did (it does not; this route is only ever
    reached by `window.location.assign`), and the shape any other legitimate `fetch`-based caller on
    the same origin would send. `_is_browser_navigation` must read this as *not* a browser
    navigation — the primary `Sec-Fetch-Mode` signal is present and answers the question directly,
    so the `Accept: text/html` fallback below it is never consulted — and this route must answer the
    plain JSON `404` an API caller gets, never the `303`."""
    game_id = _T335_CORS_FETCH_GAME_ID
    caller = await _seed_bare_user(db_session)
    await _sign_in(client, db_session, caller)
    await _seed_participant_profile(
        db_session, profile_id=_T335_PARTICIPANT_A_PROFILE_ID, alias="CorsFetch"
    )
    await _seed_open_match(
        db_session, game_id=game_id, completed_at=datetime.now(UTC) - _T335_DEFINITELY_EXPIRED_AGE
    )
    await _seed_match_player(db_session, game_id=game_id, profile_id=_T335_PARTICIPANT_A_PROFILE_ID)
    await db_session.commit()

    response = client.get(
        f"/api/matches/{game_id}/replay/{_T335_PARTICIPANT_A_PROFILE_ID}",
        headers={"Sec-Fetch-Mode": "cors", "Accept": "text/html"},
        follow_redirects=False,
    )

    assert response.status_code == 404, f"Got {response.status_code}: {response.text}"
    assert "location" not in response.headers
    assert response.json()["error"]["code"] == "expired"
