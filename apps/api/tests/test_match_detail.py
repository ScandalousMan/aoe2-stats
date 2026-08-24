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

**T324 (003) — the widening.** `contracts/http-api.md`'s "Matches, widened" table removes the
ownership scope from this exact route (FR-018, FR-021): "Any match this service holds is readable
by any signed-in caller." T327 is the implementing task; every test added below carries
`@pytest.mark.xfail(strict=True, reason="T327 not implemented yet")` for the same reason the tests
above carry `reason="T070 not implemented yet"` — `matches.py` still gates `get_match_detail` on
`_owned_profile_ids` today, so a caller with no linked profile in a match still gets today's
`not_found`, and `_match_detail_json` does not yet carry a `patch` field at all (FR-018's "game
version" — see `_seed_match`'s own `patch` parameter and `test_matches_list.py`'s docstring, which
already names `patch` as the expected key for a reasonable implementation to add). Either alone is
enough to fail every test below today, for a real reason, regardless of whether the calling caller
happens to already own a participant in the match under test.

`test_no_public_directory.py`'s own `test_match_detail_widening_carries_the_no_index_header`
(FR-008a property 2) proves only that the `X-Robots-Tag` header survives the widening and names
`test_match_detail_widened_to_any_match_the_service_holds` below as "where the first is proven in
full" — this file's job is the response body, not the header, which is why none of the assertions
below re-check it.

**What `GET /api/matches?profile_id=` keeps.** T327 widens `get_match_detail` only. `list_matches`
— this file's sibling route, `GET /api/matches?profile_id=` — stays owner-scoped, and every
existing assertion above this note is untouched by this addition.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
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

# --- T324: the widening (FR-018 through FR-022) --------------------------------------------------

_STRANGER_CALLER_PROFILE_ID = 200_100_700
_STRANGER_MATCH_GAME_ID = 700_800_901
_STRANGER_MATCH_OPPONENT_A_PROFILE_ID = 200_100_800
_STRANGER_MATCH_OPPONENT_B_PROFILE_ID = 200_100_801

_OLD_MATCH_GAME_ID = 700_800_902
_OLD_MATCH_OPPONENT_A_PROFILE_ID = 200_100_810
_OLD_MATCH_OPPONENT_B_PROFILE_ID = 200_100_811

_FR022_GAME_ID = 700_800_904
_FR022_OTHER_PARTICIPANT_PROFILE_ID = 200_100_820

_SHARED_GAME_ID = 700_800_903
_SHARED_MATCH_PARTICIPANT_A_PROFILE_ID = 200_100_830
_SHARED_MATCH_PARTICIPANT_B_PROFILE_ID = 200_100_831
_SHARED_MATCH_STRANGER_PROFILE_ID = 200_100_832

_FR020_GAME_ID = 700_800_905
_FR020_PARTICIPANT_A_PROFILE_ID = 200_100_840
_FR020_PARTICIPANT_B_PROFILE_ID = 200_100_841


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


async def _seed_linked_user(
    db_session: AsyncSession, *, profile_id: int, alias: str, steam_id64: str
) -> User:
    """Like `_seed_linked_caller`, but with a caller-chosen `steam_id64` — T324's own tests need
    more than one signed-in user in the same test body (a second participant with their own
    capture, FR-022; a caller reached from a different history, FR-021), and `_seed_linked_caller`
    always uses the identical hardcoded `steam_id64`, which a second call in the same test would
    collide with on `steam_identities`' primary key."""
    user = await _seed_user(db_session)
    await _seed_profile(db_session, profile_id=profile_id, alias=alias)
    await _link_profile(
        db_session,
        user=user,
        profile_id=profile_id,
        steam_id64=steam_id64,
        is_primary=True,
    )
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
    map_name: str | None = "Arabia",
    duration_seconds: int = 2100,
    completed_at: datetime | None = None,
    patch: str | None = None,
) -> None:
    now = completed_at or datetime.now(UTC)
    db_session.add(
        Match(
            game_id=game_id,
            leaderboard_id=leaderboard_id,
            map_name=map_name,
            patch=patch,
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


# --- T324: the widening (FR-018 through FR-022, quickstart scenario 5) ---------------------------


@pytest.mark.xfail(strict=True, reason="T327 not implemented yet")
async def test_match_detail_widened_to_any_match_the_service_holds(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-018, FR-021: once T327 removes the ownership scope, `GET /api/matches/{game_id}`
    answers for a match the signed-in caller never played, and every FR-018 field is present for
    every participant — not only "does it 200", which
    `test_no_public_directory.py`'s own `test_match_detail_widening_carries_the_no_index_header`
    already checks and explicitly names this test as the place the body is proven in full.

    The caller here (`_STRANGER_CALLER_PROFILE_ID`) has no linked profile anywhere in
    `_STRANGER_MATCH_GAME_ID` — this is "any signed-in caller", not merely "a caller who owns a
    different linked profile than the one they are looking up".
    """
    caller = await _seed_linked_user(
        db_session,
        profile_id=_STRANGER_CALLER_PROFILE_ID,
        alias="StrangerCaller",
        steam_id64="76561197960287940",
    )
    await db_session.commit()
    await _sign_in(client, db_session, caller)

    await _seed_profile(
        db_session, profile_id=_STRANGER_MATCH_OPPONENT_A_PROFILE_ID, alias="StrangerOpponentA"
    )
    await _seed_profile(
        db_session, profile_id=_STRANGER_MATCH_OPPONENT_B_PROFILE_ID, alias="StrangerOpponentB"
    )
    completed_at = datetime.now(UTC)
    await _seed_match(
        db_session,
        game_id=_STRANGER_MATCH_GAME_ID,
        leaderboard_id=3,
        map_name="Arena",
        duration_seconds=1500,
        completed_at=completed_at,
        patch="101102",
    )
    await _seed_match_player(
        db_session,
        game_id=_STRANGER_MATCH_GAME_ID,
        profile_id=_STRANGER_MATCH_OPPONENT_A_PROFILE_ID,
        team_id=1,
        civ_id=5,
        color_id=1,
        result="win",
        rating=1450,
        rating_diff=11,
    )
    await _seed_match_player(
        db_session,
        game_id=_STRANGER_MATCH_GAME_ID,
        profile_id=_STRANGER_MATCH_OPPONENT_B_PROFILE_ID,
        team_id=2,
        civ_id=7,
        color_id=2,
        result="loss",
        rating=1439,
        rating_diff=-11,
    )
    await db_session.commit()

    response = client.get(f"/api/matches/{_STRANGER_MATCH_GAME_ID}")

    assert response.status_code == 200, (
        "FR-018/FR-021: any match this service holds must be readable by any signed-in caller, "
        f"not only one whose own linked profile took part in it. Got {response.status_code}: "
        f"{response.text}"
    )
    body = response.json()
    assert body["game_id"] == _STRANGER_MATCH_GAME_ID
    assert body["map_name"] == "Arena"
    assert body["leaderboard_id"] == 3
    assert body["leaderboard_name"] == "1v1 Random Map"
    assert body["duration_seconds"] == 1500
    assert body["completed_at"] == completed_at.isoformat()
    assert body["started_at"] == (completed_at - timedelta(seconds=1500)).isoformat()
    # FR-018's "game version" — `matches.patch`, the column the ingester already populates from
    # the source (`discover.py`'s `_upsert_match`) and which, until T327, no route has surfaced.
    assert body["patch"] == "101102"

    by_profile = _participants_by_profile_id(body)
    assert set(by_profile) == {
        _STRANGER_MATCH_OPPONENT_A_PROFILE_ID,
        _STRANGER_MATCH_OPPONENT_B_PROFILE_ID,
    }
    participant_a = by_profile[_STRANGER_MATCH_OPPONENT_A_PROFILE_ID]
    assert participant_a["team_id"] == 1
    assert participant_a["civ_id"] == 5
    assert participant_a["civ_name"] == "Britons"
    assert participant_a["result"] == "win"
    assert participant_a["rating_diff"] == 11
    participant_b = by_profile[_STRANGER_MATCH_OPPONENT_B_PROFILE_ID]
    assert participant_b["team_id"] == 2
    assert participant_b["civ_id"] == 7
    assert participant_b["result"] == "loss"
    assert participant_b["rating_diff"] == -11

    # FR-022's contrapositive: the caller took no part in this match, so there is no archival
    # state of their own to show, and none of the strangers' (there is none seeded) leaks in its
    # place.
    assert body["capture_status"] is None
    assert body["capture_deadline_at"] is None


@pytest.mark.xfail(strict=True, reason="T327 not implemented yet")
async def test_match_detail_renders_completely_for_a_match_older_than_the_retention_window(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-019: the page renders entirely from stored match data, never from the recording it
    describes, so it stays complete for a match of any age — proven with a match completed 45
    days ago (past the ~31-day retention window, `docs/data-sources.md` §2) that never acquired a
    `replay_captures` row for anyone. `matches.py`'s own module docstring already states this
    route is "read-only wrappers" around `MatchesRepository`, which touches no provider — there is
    nothing to fetch here in the first place, so what this test proves is that the *response*
    stays complete, not merely that no network call happens.
    """
    caller = await _seed_linked_user(
        db_session,
        profile_id=_STRANGER_CALLER_PROFILE_ID,
        alias="StrangerCaller",
        steam_id64="76561197960287941",
    )
    await db_session.commit()
    await _sign_in(client, db_session, caller)

    await _seed_profile(db_session, profile_id=_OLD_MATCH_OPPONENT_A_PROFILE_ID, alias="OldA")
    await _seed_profile(db_session, profile_id=_OLD_MATCH_OPPONENT_B_PROFILE_ID, alias="OldB")
    completed_at = datetime.now(UTC) - timedelta(days=45)
    await _seed_match(
        db_session,
        game_id=_OLD_MATCH_GAME_ID,
        map_name="Black Forest",
        duration_seconds=2400,
        completed_at=completed_at,
        patch="100100",
    )
    await _seed_match_player(
        db_session,
        game_id=_OLD_MATCH_GAME_ID,
        profile_id=_OLD_MATCH_OPPONENT_A_PROFILE_ID,
        team_id=1,
        civ_id=2,
        color_id=1,
        result="win",
        rating=1200,
        rating_diff=9,
    )
    await _seed_match_player(
        db_session,
        game_id=_OLD_MATCH_GAME_ID,
        profile_id=_OLD_MATCH_OPPONENT_B_PROFILE_ID,
        team_id=2,
        civ_id=3,
        color_id=2,
        result="loss",
        rating=1191,
        rating_diff=-9,
    )
    await db_session.commit()

    response = client.get(f"/api/matches/{_OLD_MATCH_GAME_ID}")

    assert response.status_code == 200, (
        "FR-019: a match must be complete regardless of its age, including one whose recording "
        f"expired long ago. Got {response.status_code}: {response.text}"
    )
    body = response.json()
    assert body["completed_at"] == completed_at.isoformat()
    assert body["map_name"] == "Black Forest"
    assert body["patch"] == "100100"

    by_profile = _participants_by_profile_id(body)
    assert set(by_profile) == {_OLD_MATCH_OPPONENT_A_PROFILE_ID, _OLD_MATCH_OPPONENT_B_PROFILE_ID}
    for participant in by_profile.values():
        assert participant["team_id"] is not None
        assert participant["civ_id"] is not None
        assert participant["result"] is not None
        assert participant["rating_diff"] is not None

    # Nobody ever captured a replay for this match: there is no archival state to report either,
    # never a stale or fabricated one.
    assert body["capture_status"] is None
    assert body["capture_deadline_at"] is None


@pytest.mark.xfail(strict=True, reason="T327 not implemented yet")
async def test_match_detail_carries_only_the_callers_own_replay_archival_state(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-022: a match the caller played themselves also carries the archival state of *their
    own* replay — never a co-participant's, even when one exists and disagrees. The caller's own
    capture is `stored`; a second, distinct signed-in user who also took part in this match has
    their own capture recorded as `quarantined`. If the widened route ever picked "any capture row
    for this match" instead of "the caller's own" (the two are joined on `owner_profile_ids` in
    `MatchesRepository.get_match_detail`, per that module's own docstring), this is the test that
    would catch it, because the two statuses disagree and only one of them is correct for this
    caller.
    """
    caller = await _seed_linked_caller(db_session)
    await _sign_in(client, db_session, caller)

    await _seed_linked_user(
        db_session,
        profile_id=_FR022_OTHER_PARTICIPANT_PROFILE_ID,
        alias="OtherParticipant",
        steam_id64="76561197960287942",
    )
    await db_session.commit()

    completed_at = datetime.now(UTC)
    await _seed_match(db_session, game_id=_FR022_GAME_ID, completed_at=completed_at, patch="101102")
    await _seed_match_player(
        db_session,
        game_id=_FR022_GAME_ID,
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
        game_id=_FR022_GAME_ID,
        profile_id=_FR022_OTHER_PARTICIPANT_PROFILE_ID,
        team_id=2,
        civ_id=2,
        color_id=2,
        result="loss",
        rating=1480,
        rating_diff=-18,
    )
    caller_deadline = completed_at + timedelta(days=21)
    await _seed_capture(
        db_session,
        game_id=_FR022_GAME_ID,
        profile_id=_CALLER_PROFILE_ID,
        status=CaptureStatus.STORED,
        capture_deadline_at=caller_deadline,
    )
    await _seed_capture(
        db_session,
        game_id=_FR022_GAME_ID,
        profile_id=_FR022_OTHER_PARTICIPANT_PROFILE_ID,
        status=CaptureStatus.QUARANTINED,
        capture_deadline_at=completed_at + timedelta(days=21),
    )
    await db_session.commit()

    response = client.get(f"/api/matches/{_FR022_GAME_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["patch"] == "101102"
    assert body["capture_status"] == CaptureStatus.STORED.value, (
        "FR-022: the caller's own replay archival state must be shown — never a co-participant's "
        f"instead. Got {body['capture_status']!r}."
    )
    assert body["capture_deadline_at"] == caller_deadline.isoformat()


@pytest.mark.xfail(strict=True, reason="T327 not implemented yet")
async def test_match_detail_is_identical_and_singular_whichever_history_it_is_reached_from(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-021: the same match, reached from either participant's history — or reached by a caller
    who took no part in it at all, since `GET /api/matches/{game_id}` names no `from_profile_id`
    and none may be added (`matches.py`'s own T327 note: "a parameter that could change the
    presentation is one that eventually will") — must present identically, and there must be
    exactly one `matches` row backing it.

    Neither seeded participant acquires a `replay_captures` row, so `capture_status` cannot differ
    between callers here, and the equality below is a genuine whole-body comparison rather than
    one that happens to hold only because a caller-specific field is coincidentally absent
    everywhere it is checked.
    """
    participant_a = await _seed_linked_user(
        db_session,
        profile_id=_SHARED_MATCH_PARTICIPANT_A_PROFILE_ID,
        alias="SharedA",
        steam_id64="76561197960287943",
    )
    participant_b = await _seed_linked_user(
        db_session,
        profile_id=_SHARED_MATCH_PARTICIPANT_B_PROFILE_ID,
        alias="SharedB",
        steam_id64="76561197960287944",
    )
    stranger = await _seed_linked_user(
        db_session,
        profile_id=_SHARED_MATCH_STRANGER_PROFILE_ID,
        alias="SharedStranger",
        steam_id64="76561197960287945",
    )
    await db_session.commit()

    await _seed_match(db_session, game_id=_SHARED_GAME_ID, patch="101102")
    await _seed_match_player(
        db_session,
        game_id=_SHARED_GAME_ID,
        profile_id=_SHARED_MATCH_PARTICIPANT_A_PROFILE_ID,
        team_id=1,
        civ_id=1,
        color_id=1,
        result="win",
        rating=1500,
        rating_diff=10,
    )
    await _seed_match_player(
        db_session,
        game_id=_SHARED_GAME_ID,
        profile_id=_SHARED_MATCH_PARTICIPANT_B_PROFILE_ID,
        team_id=2,
        civ_id=2,
        color_id=2,
        result="loss",
        rating=1490,
        rating_diff=-10,
    )
    await db_session.commit()

    await _sign_in(client, db_session, participant_a)
    response_from_a = client.get(f"/api/matches/{_SHARED_GAME_ID}")

    client.cookies.clear()
    await _sign_in(client, db_session, participant_b)
    response_from_b = client.get(f"/api/matches/{_SHARED_GAME_ID}")

    client.cookies.clear()
    await _sign_in(client, db_session, stranger)
    response_from_stranger = client.get(f"/api/matches/{_SHARED_GAME_ID}")

    assert response_from_a.status_code == 200
    assert response_from_stranger.status_code == 200, (
        "FR-018/FR-021: a caller who took no part in this match must still be able to read it, "
        f"and identically. Got {response_from_stranger.status_code}: {response_from_stranger.text}"
    )
    assert response_from_a.json() == response_from_b.json() == response_from_stranger.json(), (
        "FR-021: the match must present identically whichever history it was reached from."
    )

    count_result = await db_session.execute(
        select(func.count()).select_from(Match).where(Match.game_id == _SHARED_GAME_ID)
    )
    assert count_result.scalar_one() == 1, (
        "FR-021: a match reachable from two histories must still be exactly one `matches` row."
    )


@pytest.mark.xfail(strict=True, reason="T327 not implemented yet")
async def test_match_detail_shows_raw_identifiers_never_a_guess_for_the_unnamed(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-020 (002 FR-001 onward): an identifier this service's reference data cannot name is
    shown raw, never guessed.

    **Civilisation.** `civilisation_name` (`civilizations.py`, T070c/T070g) only names ids 0-44
    with confidence and falls back to `"Civilisation <id>"` for anything outside that range — the
    same "no guess" convention
    `test_match_detail_lists_every_participant_with_team_civ_result_and_rating_change` already
    exercises for an owned match. This asserts it survives unchanged for a match the caller merely
    reads: the widening touches only the ownership gate in `matches.py`, never this lookup.

    **Map.** There is no numeric map identifier in this schema with a name resolved from it —
    `matches.map_name` *is* the identifier, carried verbatim from the source
    (`relic/matches.py`'s own `entry.get("mapname")`), unlike civilisations which carry a bare id
    resolved server-side. So "no guess" for a map this service cannot name means: when the source
    gave none, `map_name` stays `null` rather than being defaulted to a fabricated label — asserted
    directly against `None` here, since there is no separate raw identifier to fall back to
    display instead.
    """
    caller = await _seed_linked_user(
        db_session,
        profile_id=_STRANGER_CALLER_PROFILE_ID,
        alias="StrangerCaller",
        steam_id64="76561197960287946",
    )
    await db_session.commit()
    await _sign_in(client, db_session, caller)

    await _seed_profile(db_session, profile_id=_FR020_PARTICIPANT_A_PROFILE_ID, alias="Fr020A")
    await _seed_profile(db_session, profile_id=_FR020_PARTICIPANT_B_PROFILE_ID, alias="Fr020B")
    await _seed_match(db_session, game_id=_FR020_GAME_ID, map_name=None, patch="101102")
    await _seed_match_player(
        db_session,
        game_id=_FR020_GAME_ID,
        profile_id=_FR020_PARTICIPANT_A_PROFILE_ID,
        team_id=1,
        civ_id=999,
        color_id=1,
        result="win",
        rating=1500,
        rating_diff=10,
    )
    await _seed_match_player(
        db_session,
        game_id=_FR020_GAME_ID,
        profile_id=_FR020_PARTICIPANT_B_PROFILE_ID,
        team_id=2,
        civ_id=1,
        color_id=2,
        result="loss",
        rating=1490,
        rating_diff=-10,
    )
    await db_session.commit()

    response = client.get(f"/api/matches/{_FR020_GAME_ID}")

    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"
    body = response.json()
    assert body["map_name"] is None, (
        "FR-020: a map the source gave no name for must stay null, never a fabricated guess."
    )

    by_profile = _participants_by_profile_id(body)
    unnamed = by_profile[_FR020_PARTICIPANT_A_PROFILE_ID]
    assert unnamed["civ_id"] == 999
    assert unnamed["civ_name"] == "Civilisation 999", (
        "FR-020: an unrecognised civilisation id must yield a label built from the raw "
        f"identifier, never a guessed name. Got {unnamed['civ_name']!r}."
    )
