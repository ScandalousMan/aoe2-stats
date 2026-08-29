"""Integration test for `POST /api/privacy/export` and `GET /api/privacy/export/{id}` (T086),
implemented at **T090** (`packages/core/src/aoe2stats_core/privacy/export.py` and
`apps/api/src/aoe2stats_api/routers/privacy.py`) — none of that exists yet.

Covers quickstart.md scenario 10 point 1 and FR-036: "Users MUST be able to export all their
personal data, match records and archived replays." `contracts/http-api.md`'s "Privacy" table:
`POST /api/privacy/export` "Starts an export; returns a job reference", `GET
/api/privacy/export/{id}` "Status, then a signed URL to the archive." T090's own task text
additionally names two of 003's tables the archive must carry — `favourites` (the profile ids and
the dates) and the analyses the user requested (match ids and dates) — and two it must not:
`profile_search_cache` and `rate_limit_counters`, neither of which is keyed to a user
(`specs/003-player-search-match-analysis/data-model.md`: the first is a cache of a re-runnable
public search, the second is rate-limiting bookkeeping, and both "shed their own rows" on a
schedule that has nothing to do with any one person's export).

**Every test below is `xfail(strict=True, reason="T090 not implemented yet")`.** Neither the route
nor `packages/core/src/aoe2stats_core/privacy/export.py` exists today, so every request below
resolves to the app's own framework 404 (wrapped by `app.py`'s `HTTPException` handler into
`{"error": {"code": "not_found", ...}}`) rather than anything this file asks for — the assertions
fail for that reason, not by coincidence. Nothing here imports `aoe2stats_core.privacy.export` at
all, module scope or otherwise: every assertion below is driven through `client`, the one seam
that already exists (`privacy.py`'s router is real, only these two routes are missing from it), so
there is no not-yet-existent module to import in the first place — unlike a sibling test that
reaches for `packages/core/.../erasure.py` directly.

**The exact archive shape below is this file's own proposal, not a shape fixed by
`contracts/http-api.md` or `data-model.md`.** Neither document goes further than "an archive
assembled from the records and the blobs" (T090's task text) and "a signed URL to the archive"
(contracts/http-api.md). What follows is a concrete, defensible reading of both — a zip archive
with one JSON document per table plus a `replays/` prefix mirroring
`aoe2stats_storage.objects.replay_object_key`'s own `replays/{game_id}/{profile_id}.zip` scheme —
written here so T090 has a contract to implement against rather than reinventing one. Since every
assertion below is unreachable today (the route 404s before any of them run), pinning a shape here
costs nothing this session and saves T090 from guessing the whole of the archive layout from
prose alone.

Follows `test_replay_download.py`'s harness conventions: `client`/`db_session` against the real
throwaway database (`conftest.py`), a `sessions` row inserted directly and signed exactly as
`security.issue_session_cookie` would, and `pytestmark`'s `environment` fixture for the full
settings surface every router built on `SettingsDep` requires. The object store double below is
local to this file, not `conftest.py`'s shared `_FakeObjectStore` (which implements only
`list_keys`/`signed_get_url`) — mirrors `test_replay_download.py`'s own `_TrackingObjectStore`,
widened with a `get` that actually answers pre-seeded bytes, which this file needs both to seed a
replay blob as if a real capture had stored it and to read back whatever T090's own `put` writes
for the assembled archive.
"""

from __future__ import annotations

import io
import json
import secrets
import zipfile
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api import security
from aoe2stats_api.deps import get_object_store
from aoe2stats_api.settings import get_settings
from aoe2stats_storage.models import (
    AoeProfile,
    CaptureSource,
    CaptureStatus,
    Favourite,
    Match,
    MatchAnalysis,
    MatchAnalysisState,
    MatchPlayer,
    ProfileLink,
    ProfileSearchCache,
    RateLimitCounter,
    ReplayCapture,
    SteamIdentity,
    User,
)
from aoe2stats_storage.models import Session as UserSession
from aoe2stats_storage.objects import replay_object_key

pytestmark = [pytest.mark.usefixtures("environment")]

#: See `test_replay_download.py`'s module docstring — this suite's working assumption, not yet
#: fixed by a contract document beyond T028's own implementation.
SESSION_COOKIE_NAME = "session_id"

#: Must match `conftest.py`'s `_FakeObjectStore.signed_get_url` exactly — a hand-built bucket URL
#: would never produce this prefix, which is the whole point of asserting the export's download
#: link goes through the object store's own signer rather than a bucket URL built by hand.
_FAKE_SIGNED_PREFIX = "https://fake-object-store.example/signed/"

_OWNER_PROFILE_ID = 700_100_001
_OPPONENT_PROFILE_ID = 700_100_002
_FAVOURITE_PROFILE_ID = 700_100_003
_GAME_ID = 700_200_001
_ANALYSIS_GAME_ID = 700_200_002
_STEAM_ID64 = "76561197960287960"

_REPLAY_BYTES = b"FAKE-AOE2RECORD-ZIP-BYTES-FOR-T086-EXPORT"


class _RecordingObjectStore:
    """A `get_object_store` override that actually holds bytes, unlike `conftest.py`'s shared
    `_FakeObjectStore` (which implements only `list_keys`/`signed_get_url`) — mirrors
    `test_replay_download.py`'s own `_TrackingObjectStore`, widened with a working `get` so this
    file can both seed a replay blob as if it had already been captured and read back whatever the
    export job writes for the assembled archive, all without a real bucket."""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}
        self.put_calls: list[str] = []

    def seed(self, key: str, body: bytes) -> None:
        self._objects[key] = body

    async def list_keys(self, prefix: str = "") -> list[str]:
        return [key for key in self._objects if key.startswith(prefix)]

    async def signed_get_url(
        self, key: str, *, expires_in: int = 300, filename: str | None = None
    ) -> str:
        url = f"{_FAKE_SIGNED_PREFIX}{key}?expires_in={expires_in}"
        if filename is not None:
            url += f"&filename={filename}"
        return url

    async def put(self, key: str, body: bytes, *, content_type: str = "application/zip") -> None:
        self._objects[key] = body
        self.put_calls.append(key)

    async def get(self, key: str) -> bytes:
        return self._objects[key]

    async def delete(self, key: str) -> None:
        self._objects.pop(key, None)


def _decode_signed_url(location: str) -> tuple[str, int]:
    """The `(key, expires_in)` pair `_RecordingObjectStore.signed_get_url` encoded — mirrors
    `test_replay_download.py`'s `_decode_signed_url`."""
    assert location.startswith(_FAKE_SIGNED_PREFIX), (
        "the export's download link must go through ObjectStore.signed_get_url, never a "
        f"hand-built bucket URL (bucket never public): got {location!r}"
    )
    remainder = location[len(_FAKE_SIGNED_PREFIX) :]
    split = urlsplit(f"//host/{remainder}")
    key = split.path.removeprefix("/")
    query = parse_qs(split.query)
    expires_in = int(query["expires_in"][0])
    return key, expires_in


async def _seed_full_export_subject(db_session: AsyncSession) -> User:
    """Everything scenario 10 point 1 says the export must carry, for one user:

    - an account (`users`) with one verified Steam identity (`steam_identities`) and one active
      profile link (`profile_links`), FR-036's "personal data";
    - a match the linked profile played, against a third-party opponent (`matches`,
      `match_players`), FR-036's "match records" — the opponent's own row must **not** leak into
      the export beyond what already describes the shared match;
    - one already-archived replay capture from the linked profile's own point of view
      (`replay_captures`, `stored`), FR-036's "archived replays" — its bytes are seeded into the
      object store by the caller, since this helper only writes the database row;
    - one favourite (`favourites`) and one requested analysis (`match_analyses`,
      `requested_by_user_id` set) — the two 003 tables T090's task text names explicitly;
    - one `profile_search_cache` row and one `rate_limit_counters` row, keyed to nothing about this
      export subject beyond incidentally sharing their `user_id` in the rate-limit row — the two
      tables T090's task text says are excluded, seeded here so their *absence* from the archive is
      an assertion against a real row, not merely a row that was never written.
    """
    now = datetime.now(UTC)
    user = User(allowlisted_at=now)
    db_session.add(user)
    await db_session.flush()

    db_session.add(
        SteamIdentity(steam_id64=_STEAM_ID64, user_id=user.id, verified_at=now, last_sign_in_at=now)
    )
    db_session.add(AoeProfile(profile_id=_OWNER_PROFILE_ID, alias="ExportOwner", country="FR"))
    db_session.add(AoeProfile(profile_id=_OPPONENT_PROFILE_ID, alias="Opponent", country="DE"))
    db_session.add(AoeProfile(profile_id=_FAVOURITE_PROFILE_ID, alias="Favourite", country="BE"))
    await db_session.flush()

    db_session.add(
        ProfileLink(
            user_id=user.id,
            profile_id=_OWNER_PROFILE_ID,
            steam_id64=_STEAM_ID64,
            is_primary=True,
            linked_at=now,
        )
    )

    db_session.add(
        Match(
            game_id=_GAME_ID,
            leaderboard_id=3,
            completed_at=now - timedelta(days=2),
            source="relic",
            raw_payload={},
        )
    )
    db_session.add(
        MatchPlayer(
            game_id=_GAME_ID,
            profile_id=_OWNER_PROFILE_ID,
            team_id=1,
            civ_id=1,
            color_id=1,
            result="win",
            rating=1500,
            rating_diff=10,
        )
    )
    db_session.add(
        MatchPlayer(
            game_id=_GAME_ID,
            profile_id=_OPPONENT_PROFILE_ID,
            team_id=2,
            civ_id=2,
            color_id=2,
            result="loss",
            rating=1490,
            rating_diff=-10,
        )
    )

    object_key = replay_object_key(_GAME_ID, _OWNER_PROFILE_ID)
    db_session.add(
        ReplayCapture(
            game_id=_GAME_ID,
            profile_id=_OWNER_PROFILE_ID,
            status=CaptureStatus.STORED,
            capture_deadline_at=now + timedelta(days=19),
            first_seen_at=now - timedelta(days=2),
            stored_at=now - timedelta(days=1),
            object_key=object_key,
            zip_bytes=len(_REPLAY_BYTES),
            zip_sha256="b" * 64,
            inner_filename="replay.aoe2record",
            inner_bytes=len(_REPLAY_BYTES),
            source=CaptureSource.AUTOMATIC,
        )
    )

    db_session.add(Favourite(user_id=user.id, profile_id=_FAVOURITE_PROFILE_ID, created_at=now))

    db_session.add(
        Match(
            game_id=_ANALYSIS_GAME_ID,
            leaderboard_id=3,
            completed_at=now - timedelta(days=5),
            source="relic",
            raw_payload={},
        )
    )
    db_session.add(
        MatchAnalysis(
            game_id=_ANALYSIS_GAME_ID,
            state=MatchAnalysisState.PUBLISHED,
            point_of_view_profile_id=_OWNER_PROFILE_ID,
            requested_by_user_id=user.id,
            requested_at=now - timedelta(days=5),
        )
    )

    # Excluded tables (T090's task text): neither is keyed to a user in a way an export could
    # reach, and both must be absent from the archive even though rows for them exist.
    db_session.add(
        ProfileSearchCache(
            query_normalised="exportowner",
            results=[{"profile_id": _OWNER_PROFILE_ID, "alias": "ExportOwner"}],
            fetched_at=now,
            source="companion",
        )
    )
    db_session.add(
        RateLimitCounter(
            user_id=user.id, bucket="search", window_start=now.replace(microsecond=0), count=1
        )
    )

    await db_session.commit()
    return user


async def _sign_in(client: TestClient, db_session: AsyncSession, user: User) -> None:
    """Insert a `sessions` row directly and hand the client its signed cookie — mirrors
    `test_replay_download.py`'s own `_sign_in`."""
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


@pytest.mark.xfail(strict=True, reason="T090 not implemented yet")
def test_export_requires_authentication(client: TestClient) -> None:
    """No session cookie at all: `401 not_authenticated`, never a job reference — mirrors every
    other `/api/privacy/*` route's own discipline (`test_archival_objection.py`,
    `test_replay_download.py`)."""
    response = client.post("/api/privacy/export")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


@pytest.mark.xfail(strict=True, reason="T090 not implemented yet")
async def test_export_archive_contains_records_and_replay_blobs_but_excludes_caches(
    client: TestClient, db_session: AsyncSession
) -> None:
    """Quickstart scenario 10 point 1, FR-036: "Export. Expect account, identities, links, match
    records **and the replay blobs**." Plus T090's own task text: `favourites` (profile ids and
    dates) and the analyses the user requested (match ids and dates) are carried;
    `profile_search_cache` and `rate_limit_counters` are not, because neither is the user's own
    data (data-model.md: the first is a re-runnable public-search cache, the second is
    rate-limiting bookkeeping — neither has an owner an export could name).

    Verified by actually assembling and opening the archive the signed URL points at, through the
    same object-store double the router itself would `put` the finished export into and `get` the
    seeded replay blob back out of — never by trusting a 200 response on its own (T086's own
    instruction).
    """
    user = await _seed_full_export_subject(db_session)
    await _sign_in(client, db_session, user)

    store = _RecordingObjectStore()
    store.seed(replay_object_key(_GAME_ID, _OWNER_PROFILE_ID), _REPLAY_BYTES)
    client.app.dependency_overrides[get_object_store] = lambda: store  # type: ignore[attr-defined]

    start_response = client.post("/api/privacy/export")
    assert start_response.status_code == 202, (
        f"Got {start_response.status_code}: {start_response.text}"
    )
    job_id = start_response.json()["id"]

    status_response = None
    for _ in range(5):
        status_response = client.get(f"/api/privacy/export/{job_id}")
        assert status_response.status_code == 200, (
            f"Got {status_response.status_code}: {status_response.text}"
        )
        if status_response.json().get("status") == "completed":
            break
    assert status_response is not None
    body = status_response.json()
    assert body["status"] == "completed", (
        "the export must reach a terminal, downloadable state within a handful of polls for a "
        "dataset this small"
    )

    download_url = body["download_url"]
    key, expires_in = _decode_signed_url(download_url)
    assert 1 <= expires_in <= 900, (
        "the archive link must be a short-lived signed URL, not a bucket URL"
    )

    archive_bytes = await store.get(key)
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        names = set(archive.namelist())

        account = json.loads(archive.read("account.json"))
        assert account["id"] == str(user.id)

        identities = json.loads(archive.read("steam_identities.json"))
        assert {identity["steam_id64"] for identity in identities} == {_STEAM_ID64}

        links = json.loads(archive.read("profile_links.json"))
        assert {link["profile_id"] for link in links} == {_OWNER_PROFILE_ID}

        matches = json.loads(archive.read("matches.json"))
        assert {match["game_id"] for match in matches} >= {_GAME_ID}

        match_players = json.loads(archive.read("match_players.json"))
        assert any(
            row["game_id"] == _GAME_ID and row["profile_id"] == _OWNER_PROFILE_ID
            for row in match_players
        ), "the user's own participation row must be exported"

        favourites = json.loads(archive.read("favourites.json"))
        assert favourites == [
            {
                "profile_id": _FAVOURITE_PROFILE_ID,
                "created_at": favourites[0]["created_at"],
            }
        ], "favourites: the profile ids and the dates (data-model.md)"

        requested_analyses = json.loads(archive.read("requested_analyses.json"))
        assert requested_analyses == [
            {
                "game_id": _ANALYSIS_GAME_ID,
                "requested_at": requested_analyses[0]["requested_at"],
            }
        ], "the analyses the user requested: match ids and dates (data-model.md)"

        #: `replay_object_key`'s own scheme (`replays/{game_id}/{profile_id}.zip`) doubles as the
        #: archive's own entry name — one prefix to remember, not two.
        replay_entry_name = replay_object_key(_GAME_ID, _OWNER_PROFILE_ID)
        assert replay_entry_name in names, f"archive entries: {sorted(names)}"
        assert archive.read(replay_entry_name) == _REPLAY_BYTES, (
            "the replay blob content must be the exact bytes captured, not a placeholder"
        )

        assert "profile_search_cache.json" not in names, (
            "profile_search_cache is not the user's data and must never appear in an export"
        )
        assert "rate_limit_counters.json" not in names, (
            "rate_limit_counters is rate-limiting bookkeeping, not the user's data, and must "
            "never appear in an export"
        )
        for name in names:
            assert "search_cache" not in name and "rate_limit" not in name, (
                f"unexpected excluded-table content leaked into the archive under {name!r}"
            )
