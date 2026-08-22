"""Integration test for FR-038 (T067): "System MUST NOT publicly expose or index the profiles of
people who are not users" — across every route in this phase that takes a `profile_id` (or a
`game_id` naming one) the caller may not own.

`contracts/http-api.md`'s Matches section states the property directly: "Only matches involving
one of the caller's linked profiles are reachable. There is no endpoint that takes an arbitrary
`profile_id` and returns its history: FR-038 forbids exposing non-users, and an endpoint that does
it 'just for logged-in users' is still a public directory of players." T067's own task text extends
that reading to `GET /api/profiles/{profile_id}/ratings` (T072): "a rating curve for an arbitrary
player is a public directory of players just as much as a match list is."

**This is the dedicated cross-route test the property deserves, not a substitute for each router's
own ownership tests.** `test_matches_list.py` (T063) never exercises a foreign `profile_id` at all;
`test_match_detail.py` (T064) and `test_rating_history.py` (T068) each already assert their own
route's FR-045 three-case `not_found` discipline (unknown, foreign, unlinked) in full. What belongs
here instead is the property itself, walked once across every route that could leak it in one
scenario, plus the one distinction none of those files draws explicitly: FR-038 says "people who
are not users" — a profile that has *never* been linked to any account at all, not only a profile
belonging to somebody else's account. `_NEVER_LINKED_PROFILE_ID` below is exactly that case:
present in `aoe_profiles`, `matches` and even `rating_snapshots` (a provenance that would not arise
from this feature's own ingestion path, which only ever resolves ratings for a linked profile, but
the route must refuse it on ownership grounds regardless of how the row came to exist) — never
linked, never owned by anyone.

**Written before the routes exist (T070, T072).** Neither `aoe2stats_api.routers.matches` nor
`GET /api/profiles/{profile_id}/ratings` exists yet: `app.py`'s `create_app()` does not register a
`matches` router at all (see that module's own docstring), and `profiles.py` registers only `GET
/api/profiles`, `POST .../primary` and `DELETE /api/profiles/{profile_id}` (T031). Every request
below therefore 404s today on Starlette's own unmatched-route path — which, by the coincidence
`_http_status_error_code` produces (`app.py`), already answers `{"error": {"code": "not_found"}}`,
the *same* shape the real ownership check will answer. A bare "foreign profile_id gets `not_found`"
assertion would therefore pass by accident today, proving nothing. Every test below pairs that
assertion with a **positive control** — the caller's own profile or match, asserted to answer `200`
with the real seeded data — which only a working T070/T072 can satisfy; that is what makes the
xfail genuine rather than a marker sitting over an assertion that was never really false. Per
CLAUDE.md's test-first convention, every test carries `@pytest.mark.xfail(strict=True, reason=...)`
naming the implementing task, so `strict=True` turns the run red the moment that task lands and a
test starts passing for real, forcing the marker off instead of letting a stale `xfail` hide a
regression.

**Harness and response-shape assumptions** follow the sibling files these routes share, byte for
byte where they overlap: `test_replay_status.py`'s `client`/`db_session`/`_sign_in` conventions;
`test_matches_list.py`'s `{"matches": [...]}` list shape and per-row `game_id`;
`test_match_detail.py`'s `{"game_id": ..., "participants": [...]}` shape with per-participant
`profile_id`; and `test_rating_history.py`'s `{"ratings": [...]}` shape with per-entry `rating`.
See each of those
modules for the reasoning behind the specific keys asserted here.
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
    Match,
    MatchPlayer,
    ProfileLink,
    RatingSnapshot,
    SteamIdentity,
    User,
)
from aoe2stats_storage.models import Session as UserSession

pytestmark = [pytest.mark.usefixtures("environment")]

# Two separate reasons: `GET /api/matches` and `GET /api/matches/{game_id}` both come from T070,
# `GET /api/profiles/{profile_id}/ratings` from T072. Do not drop `strict=True` on either — see
# the module docstring for why that matters here specifically.
XFAIL_REASON_MATCHES = "T070 not implemented yet"
XFAIL_REASON_RATINGS = "T072 not implemented yet"

#: See `test_replay_status.py`'s module docstring — this suite's working assumption, not yet fixed
#: by a contract document beyond T028's own implementation.
SESSION_COOKIE_NAME = "session_id"

# The caller: the only account signed in for every test below.
_CALLER_PROFILE_ID = 900_100_100
# A profile linked to a *different*, fully real account — FR-038's "somebody else's" case.
_OTHER_USER_PROFILE_ID = 900_100_200
# A profile that has never been linked to any account at all — FR-038's own wording, "people who
# are not users", read literally rather than as a synonym for "somebody else's account".
_NEVER_LINKED_PROFILE_ID = 900_100_300
# A third-party opponent, itself never linked, that appears alongside every profile above so each
# match has a real second participant.
_STRANGER_PROFILE_ID = 900_100_400

_CALLER_GAME_ID = 900_200_100
_OTHER_USER_GAME_ID = 900_200_200
_NEVER_LINKED_GAME_ID = 900_200_300


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
    db_session: AsyncSession, *, user: User, profile_id: int, steam_id64: str
) -> None:
    now = datetime.now(UTC)
    db_session.add(
        SteamIdentity(steam_id64=steam_id64, user_id=user.id, verified_at=now, last_sign_in_at=now)
    )
    # `profile_links.steam_id64` carries a raw column-level foreign key to `steam_identities.
    # steam_id64` with no ORM `relationship()` between the two mapped classes, so the unit of work
    # has no dependency to sort the two inserts by — flushing the identity first is what a bare
    # `commit()` afterwards cannot guarantee on its own (`test_replay_status.py`'s own
    # `_seed_linked_profile` does the same, for the same reason).
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


async def _seed_linked_caller(db_session: AsyncSession) -> User:
    """The caller: one verified Steam identity, one active `profile_links` row for
    `_CALLER_PROFILE_ID` — the ownership check every route below must accept."""
    user = await _seed_user(db_session)
    await _seed_profile(db_session, profile_id=_CALLER_PROFILE_ID, alias="CallerAlias")
    await _link_profile(
        db_session, user=user, profile_id=_CALLER_PROFILE_ID, steam_id64="76561197960287930"
    )
    await db_session.commit()
    return user


async def _seed_other_user(db_session: AsyncSession) -> None:
    """`_OTHER_USER_PROFILE_ID`: a fully real, separate account — FR-038's "somebody else's"
    case."""
    user = await _seed_user(db_session)
    await _seed_profile(db_session, profile_id=_OTHER_USER_PROFILE_ID, alias="OtherUserAlias")
    await _link_profile(
        db_session, user=user, profile_id=_OTHER_USER_PROFILE_ID, steam_id64="76561197960287931"
    )
    await db_session.commit()


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
    db_session: AsyncSession, *, game_id: int, completed_at: datetime, map_name: str = "Arabia"
) -> None:
    db_session.add(
        Match(
            game_id=game_id,
            leaderboard_id=3,
            map_name=map_name,
            started_at=completed_at - timedelta(seconds=1800),
            completed_at=completed_at,
            duration_seconds=1800,
            source="relic",
            raw_payload={"game_id": game_id},
        )
    )


async def _seed_match_player(
    db_session: AsyncSession,
    *,
    game_id: int,
    profile_id: int,
    team_id: int,
    civ_id: int,
    result: str,
    rating_diff: int,
) -> None:
    db_session.add(
        MatchPlayer(
            game_id=game_id,
            profile_id=profile_id,
            team_id=team_id,
            civ_id=civ_id,
            color_id=team_id,
            result=result,
            rating=1500,
            rating_diff=rating_diff,
        )
    )


async def _seed_match_with_stranger(
    db_session: AsyncSession, *, game_id: int, profile_id: int, completed_at: datetime
) -> None:
    """One match between `profile_id` and `_STRANGER_PROFILE_ID` — the shape every scenario below
    needs, whether the match belongs to the caller or to a profile the caller has not linked."""
    await _seed_match(db_session, game_id=game_id, completed_at=completed_at)
    await _seed_match_player(
        db_session,
        game_id=game_id,
        profile_id=profile_id,
        team_id=1,
        civ_id=5,
        result="win",
        rating_diff=15,
    )
    await _seed_match_player(
        db_session,
        game_id=game_id,
        profile_id=_STRANGER_PROFILE_ID,
        team_id=2,
        civ_id=10,
        result="loss",
        rating_diff=-15,
    )


async def _seed_scenario(db_session: AsyncSession) -> User:
    """The caller, another real user's profile, and a profile that has never been linked to
    anyone — one match each, none of them shared with the caller except the caller's own."""
    caller = await _seed_linked_caller(db_session)
    await _seed_other_user(db_session)
    await _seed_profile(db_session, profile_id=_NEVER_LINKED_PROFILE_ID, alias="NeverLinkedAlias")
    await _seed_profile(db_session, profile_id=_STRANGER_PROFILE_ID, alias="StrangerAlias")
    await db_session.flush()

    now = datetime.now(UTC)
    await _seed_match_with_stranger(
        db_session, game_id=_CALLER_GAME_ID, profile_id=_CALLER_PROFILE_ID, completed_at=now
    )
    await _seed_match_with_stranger(
        db_session,
        game_id=_OTHER_USER_GAME_ID,
        profile_id=_OTHER_USER_PROFILE_ID,
        completed_at=now,
    )
    await _seed_match_with_stranger(
        db_session,
        game_id=_NEVER_LINKED_GAME_ID,
        profile_id=_NEVER_LINKED_PROFILE_ID,
        completed_at=now,
    )
    await db_session.commit()
    return caller


async def test_matches_list_never_returns_the_history_of_a_profile_the_caller_has_not_linked(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-038, walked through `GET /api/matches?profile_id=`: an arbitrary `profile_id` — whether
    it belongs to a different real account or was never linked to anyone at all — must never yield
    that profile's matches, only the identical `not_found` `GET /api/replays/status` (T062) and
    every FR-045 route already answer for "no such active link, whatever the reason"."""
    caller = await _seed_scenario(db_session)
    await _sign_in(client, db_session, caller)

    # Positive control: the caller's own history must actually come back.
    own_response = client.get(f"/api/matches?profile_id={_CALLER_PROFILE_ID}")
    assert own_response.status_code == 200
    own_game_ids = [row["game_id"] for row in own_response.json()["matches"]]
    assert own_game_ids == [_CALLER_GAME_ID]

    other_user_response = client.get(f"/api/matches?profile_id={_OTHER_USER_PROFILE_ID}")
    assert other_user_response.status_code == 404
    assert other_user_response.json()["error"]["code"] == "not_found"
    assert str(_OTHER_USER_GAME_ID) not in other_user_response.text

    never_linked_response = client.get(f"/api/matches?profile_id={_NEVER_LINKED_PROFILE_ID}")
    assert never_linked_response.status_code == 404
    assert never_linked_response.json()["error"]["code"] == "not_found"
    assert str(_NEVER_LINKED_GAME_ID) not in never_linked_response.text


async def test_match_detail_never_reveals_a_match_the_caller_did_not_play(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-038, walked through `GET /api/matches/{game_id}`: a `game_id` naming a real match that
    does not involve any of the caller's linked profiles must answer the identical `not_found` a
    genuinely unknown `game_id` would — `test_match_detail.py` (T064) already proves this for "a
    match belonging to a different account"; this repeats it for "a match belonging to a profile
    nobody has ever linked", FR-038's own wording."""
    caller = await _seed_scenario(db_session)
    await _sign_in(client, db_session, caller)

    # Positive control: the caller's own match must actually come back.
    own_response = client.get(f"/api/matches/{_CALLER_GAME_ID}")
    assert own_response.status_code == 200
    own_body = own_response.json()
    assert own_body["game_id"] == _CALLER_GAME_ID
    own_participant_ids = {p["profile_id"] for p in own_body["participants"]}
    assert _CALLER_PROFILE_ID in own_participant_ids

    other_user_response = client.get(f"/api/matches/{_OTHER_USER_GAME_ID}")
    assert other_user_response.status_code == 404
    assert other_user_response.json()["error"]["code"] == "not_found"
    assert "OtherUserAlias" not in other_user_response.text

    never_linked_response = client.get(f"/api/matches/{_NEVER_LINKED_GAME_ID}")
    assert never_linked_response.status_code == 404
    assert never_linked_response.json()["error"]["code"] == "not_found"
    assert "NeverLinkedAlias" not in never_linked_response.text


async def test_ratings_never_returns_the_curve_of_a_profile_the_caller_has_not_linked(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-038, walked through `GET /api/profiles/{profile_id}/ratings`: the route T072 adds must
    never answer another profile's rating curve — a public directory of players just as much as a
    match list, per T067's own task text — whether that profile belongs to a different real
    account or has never been linked to anyone at all. `test_rating_history.py` (T068) already
    proves the general FR-045 three-case discipline for this route; this asserts the specific
    property this file is for, alongside the sibling match routes above."""
    caller = await _seed_scenario(db_session)
    await _sign_in(client, db_session, caller)

    now = datetime.now(UTC)
    caller_rating = 1611
    other_user_rating = 1873
    never_linked_rating = 1955
    db_session.add(
        RatingSnapshot(
            profile_id=_CALLER_PROFILE_ID,
            leaderboard_id=3,
            captured_at=now,
            rating=caller_rating,
        )
    )
    db_session.add(
        RatingSnapshot(
            profile_id=_OTHER_USER_PROFILE_ID,
            leaderboard_id=3,
            captured_at=now,
            rating=other_user_rating,
        )
    )
    # Present in `rating_snapshots` despite never having been linked to any account — a
    # provenance this feature's own ingestion never produces (module docstring), but the route
    # must refuse it on ownership grounds regardless of how the row came to exist.
    db_session.add(
        RatingSnapshot(
            profile_id=_NEVER_LINKED_PROFILE_ID,
            leaderboard_id=3,
            captured_at=now,
            rating=never_linked_rating,
        )
    )
    await db_session.commit()

    # Positive control: the caller's own curve must actually come back.
    own_response = client.get(f"/api/profiles/{_CALLER_PROFILE_ID}/ratings")
    assert own_response.status_code == 200
    own_ratings = own_response.json()["ratings"]
    assert [entry["rating"] for entry in own_ratings] == [caller_rating]

    other_user_response = client.get(f"/api/profiles/{_OTHER_USER_PROFILE_ID}/ratings")
    assert other_user_response.status_code == 404
    assert other_user_response.json()["error"]["code"] == "not_found"
    assert str(other_user_rating) not in other_user_response.text

    never_linked_response = client.get(f"/api/profiles/{_NEVER_LINKED_PROFILE_ID}/ratings")
    assert never_linked_response.status_code == 404
    assert never_linked_response.json()["error"]["code"] == "not_found"
    assert str(never_linked_rating) not in never_linked_response.text
