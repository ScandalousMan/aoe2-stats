"""FR-008a (T310): the property this file asserts is no longer FR-038 as 001 wrote it. It is
superseded, narrowed rather than dropped, and this docstring exists to say to what.

**What 001's FR-038 actually was, and why it does not survive this feature.** 001 read
constitution IX as "no endpoint takes an arbitrary `profile_id` and returns its history" — a
third party's profile was unreachable even to a signed-in beta user, and the original version of
this file (T067) walked `GET /api/matches?profile_id=`, `GET /api/matches/{game_id}` and `GET
/api/profiles/{profile_id}/ratings`, asserting every foreign or never-linked `profile_id`
collapsed into the identical FR-045 `not_found`. This feature's entire purpose — player search,
any player's profile, any player's match history — is to add exactly the endpoints that reading
forbade, so that reading cannot survive it. But it was always stricter than the line it served:
constitution IX says a third party is never **publicly indexed**, and reachable by a signed-in,
allowlisted beta user is not the same thing as publicly indexed. `spec.md`'s FR-008a records the
supersession; `contracts/http-api.md`'s "The one thing this contract changes about 001" states the
four properties that replace it, verbatim, and are asserted below one test each.

**The naming split that keeps the blast radius to one route.** `/api/profiles/*` means "mine";
`/api/players/*` (this feature) means "anyone". `GET /api/matches?profile_id=` and `GET
/api/profiles/{profile_id}/ratings` both live under the "mine" name and **stay owner-scoped** —
the two tests below asserting them are unchanged from T067 and still pass today, live evidence
that the narrowing did not widen everything it touched. Only `GET /api/matches/{game_id}` — which
carries no profile in its own path and therefore no "mine" name to keep — is widened by this
feature (FR-018, FR-021, T327), and the four tests below replace the single T067 assertion that
used to cover it.

**The four properties, one test each — one still carrying its own `xfail` marker, never one for
the file; the first three need none anymore.** Per `contracts/http-api.md`:

1. no anonymous reach to any route this feature adds — asserted directly, no `xfail`, since T319
   landed and registered the three routes it covers: `GET /api/players/search`, `GET
   /api/players/{profile_id}`, `GET /api/players/{profile_id}/ratings`;
2. no indexing — `X-Robots-Tag: noindex, nofollow`, against `GET /api/matches/{game_id}` — asserted
   directly, no `xfail`, since T327 landed and removed that route's ownership scope: this route
   predates this feature and so falls outside `test_no_index_headers.py`'s (T308/T309) own
   parametrisation over "every route this feature adds" — the header on the widening is this
   file's property to prove, not that one's. `robots.txt`'s client-side disallow for the routes
   that render this page is a static front-end asset, `apps/web/public/robots.txt`, wired by
   T322/T331 outside this Python suite's reach, and is not re-asserted here;
3. no disclosure of a relationship between a player's accounts, on any profile (FR-009, 001
   FR-045 restated and unchanged) — asserted directly, no `xfail`, since T328 landed and
   registered `GET /api/players/{profile_id}/matches`;
4. ownership still deciding a user's own archived replay (`xfail(..., reason="T337 not
   implemented yet")`, against `GET /api/matches/{game_id}/replay/{profile_id}`, the route T337
   adds — the one place this feature's widening must stop dead: a captured replay still leaves
   this service only for the participant who owns the capture, whatever else about the match is
   now public).

Not T339: that task writes a design-system component spec and can make no assertion in this file
pass — a marker naming it would turn the tree red at a task with no way to fix it.

**Two dead constants removed in this pass.** `XFAIL_REASON_MATCHES` and `XFAIL_REASON_RATINGS`
named T070 and T072 for the two tests that stay live below; both tasks landed before this pass and
neither test ever carried an `xfail` marker referencing them (the plain comment above the two
constants said as much), so the constants had already stopped doing anything by the time this
docstring was last touched. Removed rather than left, because an unused reason constant sitting
beside four genuine ones invites a future reader to wonder which of the five is stale.

**Positive controls, kept where the collision risk that motivated them still exists.** The three
live tests below keep their positive controls (the caller's own data, asserted to come back for
real) exactly as T067 wrote them, because `GET /api/matches`, `GET /api/profiles/{profile_id}/
ratings` and now `GET /api/players/{profile_id}/matches` (T328) all already exist and a bare
"foreign profile_id gets `not_found`"-shaped assertion is indistinguishable from an accidental
pass only where a route's *existence* is not yet the thing under test. The one remaining `xfail`
test below (property 4) reaches for a route that does not exist at all yet —
`replays.py` carries no `/api/matches/{game_id}/replay/{profile_id}` route (T337) — so a
cross-account request already 404s on Starlette's own unmatched path rather than answering the
outcome the assertion asks for — a different result than the assertion asks for, which is what
makes that `xfail` genuine without needing a matching positive control. Property 4's own test
keeps a positive control anyway, because it names a *specific outcome* (a signed URL an owner
must actually receive) that a route's mere existence would not itself prove.

Properties 1, 2 and 3's tests need none of this. `players.py` is registered now (T319, T328), so
every anonymous request property 1 makes already answers the real `401` the assertion asks for
directly, without relying on a route's absence to manufacture a different status code. `matches.py`
carries no ownership scope on `GET /api/matches/{game_id}` now (T327), so property 2's requests
already answer the real `200` and header the assertion asks for directly; `GET /api/players/
{profile_id}/matches` is a real route now (T328), so property 3's request answers the real `200`
too — which is why none of the three carries an `xfail` any more.

**Harness and response-shape assumptions** follow the sibling files these routes share, byte for
byte where they overlap: `test_replay_status.py`'s `client`/`db_session`/`_sign_in` conventions;
`test_matches_list.py`'s `{"matches": [...]}` list shape and per-row `game_id`;
`test_match_detail.py`'s `{"game_id": ..., "participants": [...]}` shape with per-participant
`profile_id`; `test_rating_history.py`'s `{"ratings": [...]}` shape with per-entry `rating`; and
`test_replay_download.py`'s `_FakeObjectStore`-backed signed-URL convention (`conftest.py`'s
`client` fixture wires it in for every test in this directory, including this one). See each of
those modules for the reasoning behind the specific keys asserted here.
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
    RatingSnapshot,
    ReplayCapture,
    SteamIdentity,
    User,
)
from aoe2stats_storage.models import Session as UserSession

pytestmark = [pytest.mark.usefixtures("environment")]

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

# Property 3 (`test_a_profiles_history_never_discloses_its_owners_other_profiles`): two profiles
# under one account, each with its own match against its own, otherwise unrelated opponent, so a
# leak of either the sibling profile's id, its alias, its game or its opponent's alias is
# distinguishable from the profile actually asked about.
_MULTI_PROFILE_ONE_ID = 900_100_500
_MULTI_PROFILE_TWO_ID = 900_100_501
_MULTI_ALIAS_ONE = "MultiAccountAliasOne"
_MULTI_ALIAS_TWO = "MultiAccountAliasTwo"
_MULTI_OPPONENT_ONE_ID = 900_100_510
_MULTI_OPPONENT_TWO_ID = 900_100_511
_MULTI_OPPONENT_ALIAS_ONE = "MultiOpponentAliasOne"
_MULTI_OPPONENT_ALIAS_TWO = "MultiOpponentAliasTwo"
_MULTI_GAME_ONE_ID = 900_200_500
_MULTI_GAME_TWO_ID = 900_200_501

# Property 4 (`test_replay_download_ownership_survives_the_match_detail_widening`): a capture
# owned by one account, reached for by a second, unrelated one.
_REPLAY_OWNER_PROFILE_ID = 900_100_600
_REPLAY_STRANGER_PROFILE_ID = 900_100_601
_REPLAY_GAME_ID = 900_200_600


def _contains_value(payload: object, needle: object) -> bool:
    """Whether `needle` appears anywhere in a JSON-decoded body, at any depth, as a value —
    resilient to exactly which key a response nests a profile id or an alias under. Mirrors
    `test_multi_account.py`'s helper of the same name and shape, kept as this file's own copy
    per the module docstring's "each router in this feature is a self-contained file" convention
    applied to its tests."""
    if payload == needle:
        return True
    if isinstance(payload, dict):
        return any(_contains_value(value, needle) for value in payload.values())
    if isinstance(payload, list):
        return any(_contains_value(item, needle) for item in payload)
    return False


async def _seed_profile(
    db_session: AsyncSession, *, profile_id: int, alias: str, country: str | None = "FR"
) -> None:
    db_session.add(AoeProfile(profile_id=profile_id, alias=alias, country=country))


async def _seed_user(db_session: AsyncSession) -> User:
    now = datetime.now(UTC)
    user = User(allowlisted_at=now)
    db_session.add(user)
    await db_session.flush()
    return user


async def _link_profile(
    db_session: AsyncSession,
    *,
    user: User,
    profile_id: int,
    steam_id64: str,
    is_primary: bool = True,
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
            is_primary=is_primary,
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


async def test_players_routes_never_answer_without_a_session(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-008a property 1 (`contracts/http-api.md`): no route this feature adds is reachable
    anonymously. Walks the three routes T319 registers — `GET /api/players/search`, `GET
    /api/players/{profile_id}`, `GET /api/players/{profile_id}/ratings` — each of which must
    answer the identical `401 not_authenticated` `_require_session` already gives `GET /api/
    matches` and `GET /api/profiles/{profile_id}/ratings` (both asserted live above), never a
    smaller body or a degraded-but-200 response.

    No `xfail` marker: `players.py` is registered now (T319), so every request below already
    answers the real `401 not_authenticated` the assertion asks for directly, rather than relying
    on a route's absence to manufacture a different status code (module docstring). `GET
    /api/players/{profile_id}` and `GET /api/players/{profile_id}/ratings` carry a positive
    control anyway, since both are pure reads over already-seeded rows and cost nothing to check;
    `GET /api/players/search` does not, because a genuine positive control would have to either
    reach the real search source (forbidden outside `packages/providers`, CLAUDE.md) or stand up
    the provider-mocking harness `test_players_routes.py` (T317) already owns — duplicating that
    machinery here for a property this test can already prove without it would be the wrong
    trade.
    """
    caller = await _seed_scenario(db_session)

    anonymous_search = client.get("/api/players/search", params={"q": "Stranger"})
    assert anonymous_search.status_code == 401
    assert anonymous_search.json()["error"]["code"] == "not_authenticated"

    anonymous_profile = client.get(f"/api/players/{_STRANGER_PROFILE_ID}")
    assert anonymous_profile.status_code == 401
    assert anonymous_profile.json()["error"]["code"] == "not_authenticated"

    anonymous_ratings = client.get(f"/api/players/{_STRANGER_PROFILE_ID}/ratings")
    assert anonymous_ratings.status_code == 401
    assert anonymous_ratings.json()["error"]["code"] == "not_authenticated"

    # Positive control for the two routes it costs nothing to check: signed in, a real profile
    # this service has already observed must actually answer, proving the 401s above come from
    # the session check rather than from routes that still do not exist.
    await _sign_in(client, db_session, caller)

    profile_response = client.get(f"/api/players/{_STRANGER_PROFILE_ID}")
    assert profile_response.status_code == 200

    ratings_response = client.get(f"/api/players/{_STRANGER_PROFILE_ID}/ratings")
    assert ratings_response.status_code == 200


async def test_match_detail_widening_carries_the_no_index_header(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-008a property 2: now that T327 has removed the ownership scope from `get_match_detail`,
    `GET /api/matches/{game_id}` answers for a match the caller never played (FR-018, FR-021) — the
    one 001 route this feature widens rather than adds — and that response must carry `X-Robots-
    Tag: noindex, nofollow` (FR-010). `test_no_index_headers.py` (T308/T309) parametrises over
    "every route this feature adds"; this route predates the feature and is only widened, so it
    falls outside that parametrisation and the header on the widening is this file's property to
    prove instead. `robots.txt`'s client-side disallow for the route that renders this page is a
    static front-end asset (`apps/web/public/robots.txt`, T322/T331) outside this Python suite's
    reach, and is not re-asserted here — see the module docstring.

    Positive control kept deliberately: `200` alone would not distinguish "the ownership scope is
    gone" from "the header machinery also travelled with it", and this test is for the second of
    those, not the first (`test_match_detail_widened_to_any_match_the_service_holds` in
    `test_match_detail.py`, T324, is where the first is proven in full).
    """
    caller = await _seed_scenario(db_session)
    await _sign_in(client, db_session, caller)

    other_user_response = client.get(f"/api/matches/{_OTHER_USER_GAME_ID}")
    assert other_user_response.status_code == 200, (
        "FR-018/FR-021: the ownership scope must be gone from GET /api/matches/{game_id} — any "
        f"match this service holds is readable by any signed-in caller. Got "
        f"{other_user_response.status_code}: {other_user_response.text}"
    )
    assert other_user_response.headers.get("x-robots-tag") == "noindex, nofollow"

    never_linked_response = client.get(f"/api/matches/{_NEVER_LINKED_GAME_ID}")
    assert never_linked_response.status_code == 200
    assert never_linked_response.headers.get("x-robots-tag") == "noindex, nofollow"


async def test_a_profiles_history_never_discloses_its_owners_other_profiles(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-008a property 3 (FR-009, 001 FR-045 restated and unchanged): `GET /api/players/
    {profile_id}/matches` — the route T328 adds — must never let a caller learn, through anything
    it returns for one profile, that its owner has a second profile linked to the same account.
    `test_multi_account.py` (T023) already proves this for the account holder's own routes (`GET
    /api/me`, `GET /api/profiles`); this is the same property, for a route reachable by a caller
    who owns neither profile, walked through the one route this feature adds that could leak a
    link between two profiles it did not itself ask about.
    """
    owner = await _seed_user(db_session)
    await _seed_profile(db_session, profile_id=_MULTI_PROFILE_ONE_ID, alias=_MULTI_ALIAS_ONE)
    await _seed_profile(db_session, profile_id=_MULTI_PROFILE_TWO_ID, alias=_MULTI_ALIAS_TWO)
    await _seed_profile(
        db_session, profile_id=_MULTI_OPPONENT_ONE_ID, alias=_MULTI_OPPONENT_ALIAS_ONE
    )
    await _seed_profile(
        db_session, profile_id=_MULTI_OPPONENT_TWO_ID, alias=_MULTI_OPPONENT_ALIAS_TWO
    )
    await _link_profile(
        db_session, user=owner, profile_id=_MULTI_PROFILE_ONE_ID, steam_id64="76561197960287940"
    )
    # Not primary: `profile_links` allows exactly one primary row per user (`ix_profile_links_
    # user_id_primary`), and which of the two is primary is irrelevant to the property under
    # test — both must be equally undisclosed to a stranger regardless.
    await _link_profile(
        db_session,
        user=owner,
        profile_id=_MULTI_PROFILE_TWO_ID,
        steam_id64="76561197960287941",
        is_primary=False,
    )
    await db_session.flush()

    now = datetime.now(UTC)
    await _seed_match(db_session, game_id=_MULTI_GAME_ONE_ID, completed_at=now)
    await _seed_match_player(
        db_session,
        game_id=_MULTI_GAME_ONE_ID,
        profile_id=_MULTI_PROFILE_ONE_ID,
        team_id=1,
        civ_id=5,
        result="win",
        rating_diff=15,
    )
    await _seed_match_player(
        db_session,
        game_id=_MULTI_GAME_ONE_ID,
        profile_id=_MULTI_OPPONENT_ONE_ID,
        team_id=2,
        civ_id=10,
        result="loss",
        rating_diff=-15,
    )
    await _seed_match(db_session, game_id=_MULTI_GAME_TWO_ID, completed_at=now)
    await _seed_match_player(
        db_session,
        game_id=_MULTI_GAME_TWO_ID,
        profile_id=_MULTI_PROFILE_TWO_ID,
        team_id=1,
        civ_id=5,
        result="win",
        rating_diff=15,
    )
    await _seed_match_player(
        db_session,
        game_id=_MULTI_GAME_TWO_ID,
        profile_id=_MULTI_OPPONENT_TWO_ID,
        team_id=2,
        civ_id=10,
        result="loss",
        rating_diff=-15,
    )
    await db_session.commit()

    # A caller unrelated to either profile — proving the property for the general case FR-009
    # actually names: *any* caller, not only a rival account with something to gain from it.
    caller = await _seed_linked_caller(db_session)
    await _sign_in(client, db_session, caller)

    response = client.get(f"/api/players/{_MULTI_PROFILE_ONE_ID}/matches")
    assert response.status_code == 200, (
        f"GET /api/players/{{profile_id}}/matches must answer for any profile this service has "
        f"observed. Got {response.status_code}: {response.text}"
    )
    body = response.json()

    # Positive control: profile one's own match, against its own opponent, must actually come
    # back — otherwise the absence checks below would pass for having returned nothing at all.
    assert str(_MULTI_GAME_ONE_ID) in response.text
    assert _MULTI_OPPONENT_ALIAS_ONE in response.text

    assert not _contains_value(body, _MULTI_PROFILE_TWO_ID), (
        "the response for profile one must never name profile two, its owner's other profile"
    )
    assert _MULTI_ALIAS_TWO not in response.text
    assert str(_MULTI_GAME_TWO_ID) not in response.text
    assert _MULTI_OPPONENT_ALIAS_TWO not in response.text


async def test_replay_download_ownership_survives_the_match_detail_widening(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-008a property 4 (FR-026, FR-012): `GET /api/matches/{game_id}` is now open to any
    signed-in caller (T327), but `GET /api/matches/{game_id}/replay/{profile_id}` — the download
    route T337 adds — must not follow it there. FR-026 is explicit that `archived` is "the
    caller's own captured replay, and only that": a `replay_captures` row *the caller owns*,
    regardless of the match's age. This seeds a match old enough that the source can no longer
    supply it either, so the archive is the only copy that exists at all — a stranger reaching for
    it anyway must still be refused, exactly as `test_replay_download.py` (T071) already proves
    for 001's own `GET /api/replays/{game_id}/download`; this is the identical property, for the
    route this feature adds instead.

    Positive control kept deliberately, and load-bearing here specifically: without it, "the
    stranger is refused" would be indistinguishable from "the route does not exist yet, so nobody
    can download anything" — the same collision `test_replay_download.py`'s own equivalent test
    names as its reason for asserting the owner's download first, in the same test.
    """
    owner = await _seed_user(db_session)
    await _seed_profile(db_session, profile_id=_REPLAY_OWNER_PROFILE_ID, alias="ReplayOwnerAlias")
    await _link_profile(
        db_session, user=owner, profile_id=_REPLAY_OWNER_PROFILE_ID, steam_id64="76561197960287950"
    )
    stranger = await _seed_user(db_session)
    await _seed_profile(
        db_session, profile_id=_REPLAY_STRANGER_PROFILE_ID, alias="ReplayStrangerAlias"
    )
    await _link_profile(
        db_session,
        user=stranger,
        profile_id=_REPLAY_STRANGER_PROFILE_ID,
        steam_id64="76561197960287951",
    )
    await db_session.flush()

    now = datetime.now(UTC)
    # Well past the measured retention window (docs/data-sources.md §2): the archive is the only
    # copy of this replay that can possibly exist, which is what makes "ownership, not age" the
    # only thing left that can be gating the stranger's request below.
    await _seed_match(db_session, game_id=_REPLAY_GAME_ID, completed_at=now - timedelta(days=60))
    object_key = f"replays/{_REPLAY_GAME_ID}/{_REPLAY_OWNER_PROFILE_ID}.zip"
    db_session.add(
        ReplayCapture(
            game_id=_REPLAY_GAME_ID,
            profile_id=_REPLAY_OWNER_PROFILE_ID,
            status=CaptureStatus.STORED,
            capture_deadline_at=now - timedelta(days=41),
            first_seen_at=now - timedelta(days=60),
            stored_at=now - timedelta(days=59),
            object_key=object_key,
            zip_bytes=1024,
            zip_sha256="b" * 64,
            inner_filename="replay.aoe2record",
            inner_bytes=2048,
            source=CaptureSource.AUTOMATIC,
        )
    )
    await db_session.commit()

    download_path = f"/api/matches/{_REPLAY_GAME_ID}/replay/{_REPLAY_OWNER_PROFILE_ID}"

    await _sign_in(client, db_session, owner)
    owner_response = client.get(download_path, follow_redirects=False)
    assert owner_response.status_code == 302, (
        "the actual owner of the capture must still be able to download it (FR-026), regardless "
        f"of the match's age. Got {owner_response.status_code}: {owner_response.text}"
    )
    assert object_key in owner_response.headers.get("location", "")

    client.cookies.clear()
    await _sign_in(client, db_session, stranger)
    stranger_response = client.get(download_path, follow_redirects=False)

    assert stranger_response.status_code == 404, (
        "a caller who does not own the capture must be refused even though GET /api/matches/"
        f"{{game_id}} would now show them this match (T327). Got "
        f"{stranger_response.status_code}: {stranger_response.text}"
    )
    assert stranger_response.json()["error"]["code"] == "not_found", (
        "never a differentiated cause: FR-045's discipline applies here exactly as it does to "
        "every other ownership check in this codebase (replays.py's own module docstring)"
    )
    assert object_key not in stranger_response.text
    assert "location" not in stranger_response.headers


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
