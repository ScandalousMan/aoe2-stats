"""Integration test for `GET /api/matches/{game_id}` (T064) — `contracts/http-api.md`'s Matches
table: "All participants, teams, civs, results, rating changes", and FR-011: "System MUST provide
a match detail view listing every participant with their team, civilisation, result and rating
change."

`aoe2stats_api.routers.matches` does not exist yet — T070 is `[ ]` in `tasks.md` at the time this
file is written, and `app.py`'s own docstring lists `matches.py` among the routers "every
user-story phase after it adds", not yet registered by `create_app()`. Per CLAUDE.md's "Test-first
tasks and the green-tree gate", every test below is `@pytest.mark.xfail(strict=True, reason="T070
not implemented yet")`: with no `matches` router registered, `GET /api/matches/{game_id}` falls
through to Starlette's own unmatched-route 404, which this suite's assertions on the real response
shape naturally fail against — there is nothing to import at module scope that does not already
exist (unlike `apps/ingester/tests/test_quarantine.py`'s `CaptureDrain`), so no import-inside-body
workaround is needed here; the HTTP call itself is what does not yet behave as specified.
`strict=True` is what turns the run red the moment T070 lands and a test starts passing for real,
forcing the marker off instead of letting a stale `xfail` hide a regression.

Follows `test_replay_status.py`'s harness conventions: `client`/`db_session` against the real
throwaway database (`conftest.py`), a `sessions` row inserted directly and signed exactly as
`security.issue_session_cookie` would, and `pytestmark`'s `environment` fixture for the full
settings surface every router built on `SettingsDep` requires.

**Response shape.** Neither the contract nor data-model.md fixes a JSON key set for this route, so
this test derives one from the codebase's own established convention — `profiles.py`'s
`list_profiles` and `GET /api/replays/status` (`replays.py`) both echo SQLAlchemy column names
verbatim (`profile_id`, `alias`, `leaderboard_id`, ...), never a renamed or camelCased field. A
participant is therefore expected to carry `profile_id` and `alias` (there is no other way to say
*who* a participant is), plus the four FR-011 asks read off `match_players`' own columns:
`team_id`, `civ_id`, `result`, `rating_diff`. Assertions below check these keys are present with
the seeded values rather than asserting dict equality, so an implementation that also returns
`color_id` or `rating` is not penalised for doing more than the four FR-011 requires. T070c adds
one further key, `civ_name` — `civilisation_name` from `aoe2stats_api.civilizations`, the same
precedent `leaderboard_name` (T033a) set for a hand-maintained id-to-name table. T070f applies
that same precedent to the top-level `leaderboard_id` itself, which now carries a `leaderboard_name`
resolved with the identical helper `GET /api/profiles` already reads.

**Ownership.** The contract states plainly: "Only matches involving one of the caller's linked
profiles are reachable." Mirrors `replays.py`'s `_owned_active_link`/`_profile_not_found` FR-045
discipline: a `game_id` that does not exist and one that exists but does not involve any of the
caller's active links both answer the identical `not_found` — a differentiated answer would itself
leak which games exist. "One of the caller's linked profiles", not only the primary one (FR-043),
is exercised explicitly below.
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
    MatchPlayer,
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

_CALLER_PROFILE_ID = 200_100_300
_SECONDARY_PROFILE_ID = 200_100_301
_OPPONENT_PROFILE_ID = 200_100_400
_ALLY_PROFILE_ID = 200_100_500
_OTHER_OPPONENT_PROFILE_ID = 200_100_600

_GAME_ID = 700_800_900


async def _seed_profile(
    db_session: AsyncSession, *, profile_id: int, alias: str, country: str | None = "FR"
) -> None:
    db_session.add(AoeProfile(profile_id=profile_id, alias=alias, country=country))


async def _seed_user(db_session: AsyncSession) -> User:
    now = datetime.now(UTC)
    user = User(allowlisted_at=now, ingest_consent_at=now)
    db_session.add(user)
    await db_session.flush()
    return user


async def _link_profile(
    db_session: AsyncSession,
    *,
    user: User,
    profile_id: int,
    steam_id64: str,
    is_primary: bool,
) -> None:
    now = datetime.now(UTC)
    db_session.add(
        SteamIdentity(steam_id64=steam_id64, user_id=user.id, verified_at=now, last_sign_in_at=now)
    )
    # `profile_links.steam_id64` carries a raw column-level foreign key to `steam_identities.
    # steam_id64` with no ORM `relationship()` between the two mapped classes, so the unit of work
    # has no dependency to sort the two inserts by — flushing the identity first is what a bare
    # `commit()` afterwards cannot guarantee on its own (`test_no_public_directory.py`'s own
    # `_link_profile` does the same, for the same reason).
    await db_session.flush()
    db_session.add(
        ProfileLink(
            user_id=user.id,
            profile_id=profile_id,
            steam_id64=steam_id64,
            is_primary=is_primary,
            linked_at=now,
        )
    )


async def _seed_linked_caller(
    db_session: AsyncSession, *, profile_id: int = _CALLER_PROFILE_ID
) -> User:
    """A user with one verified Steam identity and one active `profile_links` row for
    `profile_id` — the ownership check T070 must accept."""
    user = await _seed_user(db_session)
    await _seed_profile(db_session, profile_id=profile_id, alias="CallerAlias")
    await _link_profile(
        db_session,
        user=user,
        profile_id=profile_id,
        steam_id64="76561197960287930",
        is_primary=True,
    )
    await db_session.commit()
    return user


async def _sign_in(client: TestClient, db_session: AsyncSession, user: User) -> None:
    """Insert a `sessions` row directly and hand the client its signed cookie — mirrors
    `test_replay_status.py`'s own `_sign_in` helper."""
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


async def _seed_match(
    db_session: AsyncSession,
    *,
    game_id: int = _GAME_ID,
    leaderboard_id: int = 3,
    map_name: str = "Arabia",
    duration_seconds: int = 2100,
    completed_at: datetime | None = None,
) -> None:
    now = completed_at or datetime.now(UTC)
    db_session.add(
        Match(
            game_id=game_id,
            leaderboard_id=leaderboard_id,
            map_name=map_name,
            started_at=now - timedelta(seconds=duration_seconds),
            completed_at=now,
            duration_seconds=duration_seconds,
            source="relic",
            raw_payload={"matchHistoryId": game_id},
        )
    )


async def _seed_match_player(
    db_session: AsyncSession,
    *,
    game_id: int = _GAME_ID,
    profile_id: int,
    team_id: int,
    civ_id: int,
    color_id: int,
    result: str,
    rating: int,
    rating_diff: int,
) -> None:
    db_session.add(
        MatchPlayer(
            game_id=game_id,
            profile_id=profile_id,
            team_id=team_id,
            civ_id=civ_id,
            color_id=color_id,
            result=result,
            rating=rating,
            rating_diff=rating_diff,
        )
    )


async def _seed_capture(
    db_session: AsyncSession,
    *,
    game_id: int = _GAME_ID,
    profile_id: int,
    status: CaptureStatus = CaptureStatus.STORED,
    capture_deadline_at: datetime,
) -> None:
    """Mirrors `test_matches_list.py`'s own `_seed_capture` — one `replay_captures` row, whose
    point of view is `profile_id` (`ReplayCapture`'s own docstring)."""
    db_session.add(
        ReplayCapture(
            game_id=game_id,
            profile_id=profile_id,
            status=status,
            capture_deadline_at=capture_deadline_at,
            first_seen_at=capture_deadline_at - timedelta(days=21),
            source=CaptureSource.AUTOMATIC,
        )
    )


def _participants_by_profile_id(body: dict[str, object]) -> dict[int, dict[str, object]]:
    participants = body["participants"]
    assert isinstance(participants, list)
    return {int(p["profile_id"]): p for p in participants}


async def test_match_detail_requires_authentication(client: TestClient) -> None:
    """No session cookie at all: 401, never a leak of whether `game_id` exists."""
    response = client.get(f"/api/matches/{_GAME_ID}")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


async def test_match_detail_unknown_game_id_returns_not_found(
    client: TestClient, db_session: AsyncSession
) -> None:
    user = await _seed_linked_caller(db_session)
    await _sign_in(client, db_session, user)

    response = client.get(f"/api/matches/{_GAME_ID + 1}")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    # `app.py`'s generic `HTTPException` fallback (an unmatched route, with no `matches` router
    # registered) *also* answers 404/"not_found" — `_http_status_error_code(404)` derives that
    # code from the status phrase alone, coincidentally the same string this route's own domain
    # `not_found` uses. Left unchecked, that coincidence lets this test pass before T070 exists,
    # which is exactly the "xfail hides a still-missing implementation" failure this suite's own
    # `xfail(strict=True)` exists to catch. The fallback's `message` is the bare phrase "Not
    # Found" (`starlette.exceptions.HTTPException`'s own default `detail`); every *deliberate*
    # `not_found` this codebase raises (`replays.py`'s and `profiles.py`'s own
    # `_profile_not_found`) instead carries a specific, human-meaningful sentence — this
    # assertion is what actually requires T070's route to exist and answer on purpose.
    assert body["error"]["message"] != "Not Found"


async def test_match_detail_match_not_involving_caller_returns_the_identical_not_found(
    client: TestClient, db_session: AsyncSession
) -> None:
    """A `game_id` that names a real match, but one none of the caller's linked profiles took
    part in, must answer the *same* `not_found` as an unknown one (contract: "Only matches
    involving one of the caller's linked profiles are reachable") — never a 403 confirming the
    match exists."""
    caller = await _seed_linked_caller(db_session)
    await _sign_in(client, db_session, caller)

    await _seed_profile(db_session, profile_id=_OPPONENT_PROFILE_ID, alias="SomeoneElse")
    await _seed_profile(db_session, profile_id=_OTHER_OPPONENT_PROFILE_ID, alias="AnotherOne")
    await _seed_match(db_session)
    await _seed_match_player(
        db_session,
        profile_id=_OPPONENT_PROFILE_ID,
        team_id=1,
        civ_id=10,
        color_id=1,
        result="win",
        rating=1500,
        rating_diff=12,
    )
    await _seed_match_player(
        db_session,
        profile_id=_OTHER_OPPONENT_PROFILE_ID,
        team_id=2,
        civ_id=20,
        color_id=2,
        result="loss",
        rating=1490,
        rating_diff=-12,
    )
    await db_session.commit()

    response = client.get(f"/api/matches/{_GAME_ID}")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    # See `test_match_detail_unknown_game_id_returns_not_found`'s identical assertion: without
    # this check, `app.py`'s generic unmatched-route fallback already answers 404/"not_found" on
    # its own, so this test would pass before T070's route exists at all.
    assert body["error"]["message"] != "Not Found"


async def test_match_detail_lists_every_participant_with_team_civ_result_and_rating_change(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-011's happy path: a 2v2 match, all four participants returned (caller, ally, and both
    third-party opponents who have never signed in — `aoe_profiles` holds them too), each carrying
    its own team, civilisation, result and rating change."""
    caller = await _seed_linked_caller(db_session)
    await _sign_in(client, db_session, caller)

    await _seed_profile(db_session, profile_id=_ALLY_PROFILE_ID, alias="AllyAlias")
    await _seed_profile(db_session, profile_id=_OPPONENT_PROFILE_ID, alias="OpponentAlias")
    await _seed_profile(db_session, profile_id=_OTHER_OPPONENT_PROFILE_ID, alias="OtherOpponent")
    await _seed_match(db_session, map_name="Arena", duration_seconds=1800)

    await _seed_match_player(
        db_session,
        profile_id=_CALLER_PROFILE_ID,
        team_id=1,
        civ_id=5,
        color_id=1,
        result="win",
        rating=1600,
        rating_diff=15,
    )
    await _seed_match_player(
        db_session,
        profile_id=_ALLY_PROFILE_ID,
        team_id=1,
        civ_id=7,
        color_id=2,
        result="win",
        rating=1550,
        rating_diff=14,
    )
    await _seed_match_player(
        db_session,
        profile_id=_OPPONENT_PROFILE_ID,
        team_id=2,
        civ_id=10,
        color_id=3,
        result="loss",
        rating=1500,
        rating_diff=-14,
    )
    await _seed_match_player(
        db_session,
        profile_id=_OTHER_OPPONENT_PROFILE_ID,
        team_id=2,
        civ_id=999,
        color_id=4,
        result="loss",
        rating=1490,
        rating_diff=-15,
    )
    await db_session.commit()

    response = client.get(f"/api/matches/{_GAME_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["game_id"] == _GAME_ID
    # T070f: `leaderboard_name` alongside `leaderboard_id`, the same `leaderboards.py` mapping
    # `GET /api/profiles` already reads — never re-derived by the client.
    assert body["leaderboard_id"] == 3
    assert body["leaderboard_name"] == "1v1 Random Map"

    by_profile = _participants_by_profile_id(body)
    assert set(by_profile) == {
        _CALLER_PROFILE_ID,
        _ALLY_PROFILE_ID,
        _OPPONENT_PROFILE_ID,
        _OTHER_OPPONENT_PROFILE_ID,
    }

    expected = {
        _CALLER_PROFILE_ID: {
            "alias": "CallerAlias",
            "team_id": 1,
            "civ_id": 5,
            # T070g: every participant is named, not only the caller — `civ_id=5` is Britons.
            "civ_name": "Britons",
            "result": "win",
            "rating_diff": 15,
        },
        _ALLY_PROFILE_ID: {
            "alias": "AllyAlias",
            "team_id": 1,
            "civ_id": 7,
            "civ_name": "Burgundians",
            "result": "win",
            "rating_diff": 14,
        },
        _OPPONENT_PROFILE_ID: {
            "alias": "OpponentAlias",
            "team_id": 2,
            "civ_id": 10,
            "civ_name": "Celts",
            "result": "loss",
            "rating_diff": -14,
        },
        _OTHER_OPPONENT_PROFILE_ID: {
            "alias": "OtherOpponent",
            "team_id": 2,
            "civ_id": 999,
            # `civilizations.py` (T070g) only names ids 0-44 with confidence (module docstring) —
            # an id outside that range falls back honestly rather than guessing.
            "civ_name": "Civilisation 999",
            "result": "loss",
            "rating_diff": -15,
        },
    }
    for profile_id, expected_fields in expected.items():
        participant = by_profile[profile_id]
        for key, value in expected_fields.items():
            assert participant[key] == value, (
                f"participant {profile_id}: expected {key}={value!r}, got {participant.get(key)!r}"
            )

    # The two teams stay distinguishable from each other, which is what FR-011's "team" is for.
    assert by_profile[_CALLER_PROFILE_ID]["team_id"] == by_profile[_ALLY_PROFILE_ID]["team_id"]
    assert (
        by_profile[_OPPONENT_PROFILE_ID]["team_id"]
        == by_profile[_OTHER_OPPONENT_PROFILE_ID]["team_id"]
    )
    assert by_profile[_CALLER_PROFILE_ID]["team_id"] != by_profile[_OPPONENT_PROFILE_ID]["team_id"]


async def test_match_detail_reachable_via_a_non_primary_linked_profile(
    client: TestClient, db_session: AsyncSession
) -> None:
    """Contract: "Only matches involving one of the caller's linked profiles are reachable" — not
    only the primary one (FR-043: the others stay reachable, not hidden). The caller links a
    second profile and the match involves *only* that second profile."""
    caller = await _seed_linked_caller(db_session, profile_id=_CALLER_PROFILE_ID)
    await _seed_profile(db_session, profile_id=_SECONDARY_PROFILE_ID, alias="SecondaryAlias")
    await _link_profile(
        db_session,
        user=caller,
        profile_id=_SECONDARY_PROFILE_ID,
        steam_id64="76561197960287931",
        is_primary=False,
    )
    await db_session.commit()
    await _sign_in(client, db_session, caller)

    await _seed_profile(db_session, profile_id=_OPPONENT_PROFILE_ID, alias="OpponentAlias")
    await _seed_match(db_session)
    await _seed_match_player(
        db_session,
        profile_id=_SECONDARY_PROFILE_ID,
        team_id=1,
        civ_id=3,
        color_id=1,
        result="win",
        rating=1300,
        rating_diff=10,
    )
    await _seed_match_player(
        db_session,
        profile_id=_OPPONENT_PROFILE_ID,
        team_id=2,
        civ_id=4,
        color_id=2,
        result="loss",
        rating=1290,
        rating_diff=-10,
    )
    await db_session.commit()

    response = client.get(f"/api/matches/{_GAME_ID}")

    assert response.status_code == 200
    by_profile = _participants_by_profile_id(response.json())
    assert set(by_profile) == {_SECONDARY_PROFILE_ID, _OPPONENT_PROFILE_ID}


async def test_match_detail_reports_a_stored_capture(
    client: TestClient, db_session: AsyncSession
) -> None:
    """T070e: `GET /api/matches/{game_id}` carries `capture_status`/`capture_deadline_at`, the
    same two fields the list route already carries (`test_matches_list.py`) — and this is the
    precondition `DownloadAction` gates the download control on (`mappers.ts`'s
    `toMatchDetailData`, `CaptureStateBadge`): a `stored` capture for the match must be reported as
    `stored` on *this* route, not only on the list, or the control's gate never fires."""
    caller = await _seed_linked_caller(db_session)
    await _sign_in(client, db_session, caller)

    await _seed_profile(db_session, profile_id=_OPPONENT_PROFILE_ID, alias="OpponentAlias")
    completed_at = datetime.now(UTC)
    await _seed_match(db_session, completed_at=completed_at)
    await _seed_match_player(
        db_session,
        profile_id=_CALLER_PROFILE_ID,
        team_id=1,
        civ_id=1,
        color_id=1,
        result="win",
        rating=1500,
        rating_diff=18,
    )
    await _seed_match_player(
        db_session,
        profile_id=_OPPONENT_PROFILE_ID,
        team_id=2,
        civ_id=2,
        color_id=2,
        result="loss",
        rating=1480,
        rating_diff=-18,
    )
    deadline = completed_at + timedelta(days=21)
    await _seed_capture(
        db_session,
        profile_id=_CALLER_PROFILE_ID,
        status=CaptureStatus.STORED,
        capture_deadline_at=deadline,
    )
    await db_session.commit()

    response = client.get(f"/api/matches/{_GAME_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["capture_status"] == CaptureStatus.STORED.value
    assert body["capture_deadline_at"] == deadline.isoformat()


async def test_match_detail_with_no_capture_row_still_resolves(
    client: TestClient, db_session: AsyncSession
) -> None:
    """A match that has not yet acquired a `replay_captures` row (discovery has not run, or has
    not reached this match yet) must still answer `200` with every participant — `None` for both
    capture fields, never a `404`: `MatchesRepository.get_match_detail`'s own `LEFT OUTER JOIN`
    (mirroring `list_matches`) is what keeps a missing capture row from being mistaken for a
    missing match."""
    caller = await _seed_linked_caller(db_session)
    await _sign_in(client, db_session, caller)

    await _seed_profile(db_session, profile_id=_OPPONENT_PROFILE_ID, alias="OpponentAlias")
    await _seed_match(db_session)
    await _seed_match_player(
        db_session,
        profile_id=_CALLER_PROFILE_ID,
        team_id=1,
        civ_id=1,
        color_id=1,
        result="win",
        rating=1500,
        rating_diff=18,
    )
    await _seed_match_player(
        db_session,
        profile_id=_OPPONENT_PROFILE_ID,
        team_id=2,
        civ_id=2,
        color_id=2,
        result="loss",
        rating=1480,
        rating_diff=-18,
    )
    await db_session.commit()

    response = client.get(f"/api/matches/{_GAME_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["capture_status"] is None
    assert body["capture_deadline_at"] is None
    assert set(_participants_by_profile_id(body)) == {_CALLER_PROFILE_ID, _OPPONENT_PROFILE_ID}
