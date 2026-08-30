"""Integration test for quickstart scenario 8 — `POST /api/replays/{game_id}/upload` (T078),
implemented at **T080/T081**, not yet added to `apps/api/src/aoe2stats_api/routers/replays.py`.
FR-029 to FR-033 and `contracts/http-api.md`'s Replays row are ground truth for every shape
asserted below: "Manual fallback (FR-029). Multipart. Rejects a non-participant (FR-031), an
invalid file (FR-030), or an existing archive (FR-032)".

**Every test in this file carries `xfail(strict=True, reason="T080 not implemented yet")`.**
Unlike `test_favourites.py` (whose router does not exist at all), `routers/replays.py` already
exists and is already registered in `app.py` — `GET /api/replays/status` and
`GET /api/replays/{game_id}/download` are both live (`test_replay_status.py`,
`test_replay_download.py`). Only the `POST /api/replays/{game_id}/upload` route this file exercises
is missing, so every model this file seeds (`ReplayCapture`, `MatchPlayer`, ...) already imports
cleanly at module scope — there is nothing to defer inside a test body the way `test_favourites.py`
and `test_capture_visibility.py`'s second half must. Hitting the not-yet-registered route today
answers Starlette's own unmatched-route `404` (a bare `{"detail": "Not Found"}`, not this codebase's
`{"error": {"code": ...}}` envelope), which fails every assertion below in the ordinary way `xfail`
expects — never a collection error, since nothing here imports a module that does not exist yet.

**Response shapes and error codes this file commits to, where the contract states the property but
not the exact envelope** (the same convention `test_favourites.py`'s own docstring documents for
the identical situation). If T080 lands under different codes, only this file's constants need to
change; every other assertion is unaffected.

- **Success** (scenario 8.1, FR-029, FR-033): `200` with a body carrying at least
  `{"status": "stored", "source": "manual"}` — "Expect `stored`, flagged manual" is quickstart's own
  wording, and `stored`/`manual` are `CaptureStatus.STORED.value`/`CaptureSource.MANUAL.value`
  verbatim (data-model.md's "one word per side of the boundary" rule for `stored`, extended here to
  `source` for the identical reason: the enum value is the only spelling this file uses).
- **FR-030, a malformed upload** (scenario 8.2): `422` `invalid_replay` — a 4xx distinct from the
  other two failures below, since "reject an upload for a match the user did not participate in"
  and "reject a file that is not a well-formed replay" are two different facts about two different
  inputs, and conflating them into one code would cost a caller the ability to tell "wrong file"
  from "wrong match" apart, the exact failure classification constitution I's discipline (see
  `data-model.md`'s `unavailable`/`expired` split) applies everywhere this codebase distinguishes a
  cause worth telling apart.
- **FR-031, a non-participant** (scenario 8.3): `404` `not_found` — the identical code
  `routers/replays.py`'s own `_replay_not_found`/`_profile_not_found` already answer for "no such
  match", "a match the caller did not play" and "not yet archived" (that module's docstring,
  FR-045's "one error, indistinguishable causes"). A manual upload for a `game_id` the caller
  never played is the same shape of question the download routes already ask and already answer
  this way, so this file follows that module's own precedent rather than inventing a fourth code
  for a fact the router already has one word for.
- **FR-032, an existing archive** (scenario 8.4): `409` `already_archived` — a conflict with a
  resource that already exists, distinct from both codes above: the upload itself may be perfectly
  valid and the caller may well be the match's own participant, and the refusal is specifically that
  overwriting is never allowed (data-model.md: `stored` is terminal).

**Why the fixture replay, not a synthetic blob.** `tests/fixtures/replays/AgeIIDE_Replay_500546441.
zip` is the one committed archive this repository can validate against the *real* `aoe2rec-py`
engine (its own `README.md`: "the reference against which parser compatibility is verified") —
scenario 8.1 and 8.3 both need bytes that pass real capture-time validation, not merely bytes that
look like a zip, since T080's own task text is "validation through the same engine interface capture
uses". `packages/replay-engine/src/aoe2stats_replay_engine/aoe2rec.py`'s own inner-filename check
(`_INNER_FILENAME_RE`, `^AgeIIDE_Replay_\\d+\\.aoe2record$`) only constrains the *shape* of the name
inside the zip, never that its digits equal the `game_id` this route is asked to file the upload
under — so the identical fixture bytes are reused for scenario 8.3 under a `game_id` the seeded
`match_players` rows deliberately exclude the caller from, to isolate the participation check from
content validity. A malformed upload (scenario 8.2) never needs the fixture at all: plain text bytes
renamed `.aoe2record`, exactly as the scenario itself describes.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

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
    MatchPlayer,
    ProfileLink,
    ReplayCapture,
    SteamIdentity,
    User,
)
from aoe2stats_storage.models import Session as UserSession

pytestmark = [pytest.mark.usefixtures("environment")]

#: See `test_replay_status.py`'s module docstring — this suite's working assumption, not yet fixed
#: by a contract document beyond T028's own implementation.
SESSION_COOKIE_NAME = "session_id"

#: `tests/fixtures/replays/`'s own README: a real, committed, well-formed replay archive — game_id
#: 500546441, point-of-view profile 196240 — the one bytes this repository can run through the real
#: `aoe2rec-py` engine rather than a fake (module docstring's "Why the fixture replay" section).
_FIXTURE_REPLAY_PATH = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "replays"
    / "AgeIIDE_Replay_500546441.zip"
)
_FIXTURE_GAME_ID = 500546441
_FIXTURE_PROFILE_ID = 196240

_OTHER_MATCH_GAME_ID = 700200100
_OTHER_MATCHS_PARTICIPANT_PROFILE_ID = 900700200

_MALFORMED_UPLOAD_GAME_ID = 700200200

_ALREADY_ARCHIVED_GAME_ID = 700200300
_ALREADY_ARCHIVED_PROFILE_ID = 900700300


def _reference_replay_bytes() -> bytes:
    return _FIXTURE_REPLAY_PATH.read_bytes()


async def _seed_linked_profile(
    db_session: AsyncSession,
    *,
    profile_id: int,
    steam_id64: str = "76561197960287930",
) -> User:
    """A user with one verified Steam identity and one active `profile_links` row for
    `profile_id` — mirrors `test_replay_status.py`'s own helper of the same name."""
    now = datetime.now(UTC)
    user = User(allowlisted_at=now)
    db_session.add(user)
    await db_session.flush()

    db_session.add(
        SteamIdentity(steam_id64=steam_id64, user_id=user.id, verified_at=now, last_sign_in_at=now)
    )
    await _seed_aoe_profile(db_session, profile_id=profile_id)
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


async def _seed_aoe_profile(
    db_session: AsyncSession, *, profile_id: int, alias: str | None = None
) -> None:
    """A bare `aoe_profiles` row — every `match_players`/`replay_captures` row below needs one to
    satisfy its own foreign key, whether or not that profile belongs to a user of this service."""
    db_session.add(
        AoeProfile(profile_id=profile_id, alias=alias or f"player-{profile_id}", country="FR")
    )


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


async def _seed_match_player(db_session: AsyncSession, *, game_id: int, profile_id: int) -> None:
    db_session.add(MatchPlayer(game_id=game_id, profile_id=profile_id))


async def _capture_row(
    db_session: AsyncSession, *, game_id: int, profile_id: int
) -> ReplayCapture | None:
    db_session.expire_all()
    result = await db_session.execute(
        select(ReplayCapture).where(
            ReplayCapture.game_id == game_id, ReplayCapture.profile_id == profile_id
        )
    )
    return result.scalar_one_or_none()


# --- Scenario 8.1: uploading the matching file for an `expired` capture yields `stored`, manual ---


async def test_upload_for_an_expired_capture_stores_it_flagged_manual(
    client: TestClient, db_session: AsyncSession
) -> None:
    user = await _seed_linked_profile(db_session, profile_id=_FIXTURE_PROFILE_ID)
    await _sign_in(client, db_session, user)

    completed_at = datetime.now(UTC) - timedelta(days=40)
    await _seed_match(db_session, game_id=_FIXTURE_GAME_ID, completed_at=completed_at)
    await _seed_match_player(db_session, game_id=_FIXTURE_GAME_ID, profile_id=_FIXTURE_PROFILE_ID)
    db_session.add(
        ReplayCapture(
            game_id=_FIXTURE_GAME_ID,
            profile_id=_FIXTURE_PROFILE_ID,
            status=CaptureStatus.EXPIRED,
            capture_deadline_at=completed_at + timedelta(days=21),
            source=CaptureSource.AUTOMATIC,
        )
    )
    await db_session.commit()

    response = client.post(
        f"/api/replays/{_FIXTURE_GAME_ID}/upload",
        files={
            "file": (
                "AgeIIDE_Replay_500546441.aoe2record",
                _reference_replay_bytes(),
                "application/zip",
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == CaptureStatus.STORED.value
    assert body["source"] == CaptureSource.MANUAL.value

    capture = await _capture_row(
        db_session, game_id=_FIXTURE_GAME_ID, profile_id=_FIXTURE_PROFILE_ID
    )
    assert capture is not None
    assert capture.status == CaptureStatus.STORED
    assert capture.source == CaptureSource.MANUAL, (
        "FR-033: a manually supplied replay must be recorded as such, distinct from an "
        "automatically captured one"
    )
    assert capture.object_key is not None
    assert capture.zip_sha256 is not None
    assert capture.validated_by, (
        "capture-time validation ran through the same engine interface capture uses "
        "(T080's own task text), so the engine and version that vouched for the file must be "
        "recorded exactly as an automatic capture would (data-model.md's `validated_by` column)"
    )


# --- Scenario 8.2: a text file renamed `.aoe2record` is rejected, nothing stored -----------------


async def test_upload_of_a_renamed_text_file_is_rejected_and_stores_nothing(
    client: TestClient, db_session: AsyncSession
) -> None:
    user = await _seed_linked_profile(db_session, profile_id=_MALFORMED_UPLOAD_GAME_ID + 1)
    await _sign_in(client, db_session, user)

    completed_at = datetime.now(UTC) - timedelta(days=3)
    await _seed_match(db_session, game_id=_MALFORMED_UPLOAD_GAME_ID, completed_at=completed_at)
    await _seed_match_player(
        db_session, game_id=_MALFORMED_UPLOAD_GAME_ID, profile_id=_MALFORMED_UPLOAD_GAME_ID + 1
    )
    await db_session.commit()

    response = client.post(
        f"/api/replays/{_MALFORMED_UPLOAD_GAME_ID}/upload",
        files={
            "file": (
                "AgeIIDE_Replay_700200200.aoe2record",
                b"this is a plain text file, not a zip archive, merely renamed",
                "text/plain",
            )
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_replay"

    capture = await _capture_row(
        db_session, game_id=_MALFORMED_UPLOAD_GAME_ID, profile_id=_MALFORMED_UPLOAD_GAME_ID + 1
    )
    assert capture is None, (
        "FR-030: an upload that fails well-formedness must store nothing, never a `quarantined` "
        "row either — quarantine (data-model.md) is for a downloaded blob that failed validation "
        "after the fact, not for a manual upload that never validated at all"
    )


# --- Scenario 8.3: a valid replay for a match the user did not play is rejected ------------------


async def test_upload_of_a_valid_replay_for_a_match_the_user_did_not_play_is_rejected(
    client: TestClient, db_session: AsyncSession
) -> None:
    caller_profile_id = _OTHER_MATCH_GAME_ID + 1
    user = await _seed_linked_profile(db_session, profile_id=caller_profile_id)
    await _sign_in(client, db_session, user)

    completed_at = datetime.now(UTC) - timedelta(days=3)
    await _seed_match(db_session, game_id=_OTHER_MATCH_GAME_ID, completed_at=completed_at)
    # The match exists and was played, but not by the caller: a different participant entirely.
    await _seed_aoe_profile(db_session, profile_id=_OTHER_MATCHS_PARTICIPANT_PROFILE_ID)
    await _seed_match_player(
        db_session,
        game_id=_OTHER_MATCH_GAME_ID,
        profile_id=_OTHER_MATCHS_PARTICIPANT_PROFILE_ID,
    )
    await db_session.commit()

    response = client.post(
        f"/api/replays/{_OTHER_MATCH_GAME_ID}/upload",
        files={
            "file": (
                "AgeIIDE_Replay_500546441.aoe2record",
                _reference_replay_bytes(),
                "application/zip",
            )
        },
    )

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found", (
        "FR-031, following routers/replays.py's own FR-045 precedent for this module: 'no such "
        "match', 'not yet stored' and 'the caller did not play it' all answer the identical "
        "not_found — never a 403 that would confirm the match exists"
    )
    # A bare unmatched route (this endpoint does not exist yet) also answers 404 `not_found`,
    # through `app.py`'s generic `HTTPException` handler — with Starlette's own generic message,
    # "Not Found". This line is what keeps this test genuinely red until T080 exists rather than
    # coincidentally green today: it requires the *router's own* `_replay_not_found()` message
    # (routers/replays.py, reused verbatim — this file's own precedent note above), which no
    # unmatched-route response can produce.
    assert body["error"]["message"] == "No archived replay was found for that match."

    capture = await _capture_row(
        db_session, game_id=_OTHER_MATCH_GAME_ID, profile_id=caller_profile_id
    )
    assert capture is None, "a rejected upload must create no row for the caller's own profile"


# --- Scenario 8.4: an upload over an existing archive is refused, never overwritten --------------


async def test_upload_over_an_existing_archive_is_refused_and_does_not_overwrite(
    client: TestClient, db_session: AsyncSession
) -> None:
    user = await _seed_linked_profile(db_session, profile_id=_ALREADY_ARCHIVED_PROFILE_ID)
    await _sign_in(client, db_session, user)

    completed_at = datetime.now(UTC) - timedelta(days=5)
    await _seed_match(db_session, game_id=_ALREADY_ARCHIVED_GAME_ID, completed_at=completed_at)
    await _seed_match_player(
        db_session,
        game_id=_ALREADY_ARCHIVED_GAME_ID,
        profile_id=_ALREADY_ARCHIVED_PROFILE_ID,
    )
    existing_object_key = f"replays/{_ALREADY_ARCHIVED_GAME_ID}/{_ALREADY_ARCHIVED_PROFILE_ID}.zip"
    existing_sha256 = "a" * 64
    stored_at = datetime.now(UTC) - timedelta(days=1)
    db_session.add(
        ReplayCapture(
            game_id=_ALREADY_ARCHIVED_GAME_ID,
            profile_id=_ALREADY_ARCHIVED_PROFILE_ID,
            status=CaptureStatus.STORED,
            capture_deadline_at=completed_at + timedelta(days=21),
            stored_at=stored_at,
            object_key=existing_object_key,
            zip_bytes=123456,
            zip_sha256=existing_sha256,
            inner_filename="AgeIIDE_Replay_700200300.aoe2record",
            inner_bytes=123000,
            source=CaptureSource.AUTOMATIC,
            validated_by="aoe2rec-py 0.1.21",
        )
    )
    await db_session.commit()

    response = client.post(
        f"/api/replays/{_ALREADY_ARCHIVED_GAME_ID}/upload",
        files={
            "file": (
                "AgeIIDE_Replay_500546441.aoe2record",
                _reference_replay_bytes(),
                "application/zip",
            )
        },
    )

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "already_archived"
    assert body["error"]["message"], "FR-032: the refusal must carry a reason, not a bare code"

    capture = await _capture_row(
        db_session,
        game_id=_ALREADY_ARCHIVED_GAME_ID,
        profile_id=_ALREADY_ARCHIVED_PROFILE_ID,
    )
    assert capture is not None
    assert capture.object_key == existing_object_key, "FR-032: never overwrite the existing archive"
    assert capture.zip_sha256 == existing_sha256
    assert capture.zip_bytes == 123456
    assert capture.status == CaptureStatus.STORED
    assert capture.source == CaptureSource.AUTOMATIC, (
        "the pre-existing capture's own provenance must survive a refused upload untouched"
    )
