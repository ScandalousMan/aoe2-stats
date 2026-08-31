"""T424: the match-row half of the widened API contract (`contracts/http-api.md`, `quickstart.md`
scenario 4). The profile half (`avatar_hash`, T426) is added to
`apps/api/tests/test_players_routes.py` instead — that file already owns
`GET /api/players/{profile_id}` — so this file's own `xfail` reason is `"T425 not implemented yet"`
throughout, never `"T426 not implemented yet"`; the two reasons are never mixed in one file.

**What T425 must make true**, per `contracts/http-api.md`'s `GET /api/matches` /
`GET /api/players/{profile_id}/matches` section: `match_row_json`
(`apps/api/src/aoe2stats_api/routers/matches.py:426`) gains `rating`, `team_id`, `color_id` and a
`participants[]` sibling to the existing `opponents[]`; each participant carries `civ_name`
whenever `civ_id` is present (FR-001, so the client never formats a bare id itself) and `country`
(feeds the opponent flag); `result` is `"win"`, `"loss"` or `null`, and `null` is **not** a loss
(FR-004). Every assertion below is therefore an `xfail(strict=True, reason="T425 not implemented
yet")`: today's `match_row_json` carries none of these keys, so each test fails on a `KeyError`
reading a key that does not exist yet — the right reason, per this repository's test-first
convention (`test_matches_list.py`'s own module docstring sets the same precedent for T070).

**Why `GET /api/matches` and not `GET /api/players/{profile_id}/matches` is exercised below.**
`match_row_json` is imported across `routers/matches.py` and `routers/players.py` precisely so the
two routes cannot drift — `apps/api/tests/test_players_history.py`'s own
`test_players_history_row_shape_matches_get_matches_row_shape` asserts that identity directly, and
this file does not restate it: widening `match_row_json` here widens both call sites at once, and
that existing test is what proves it stays true. It is left unmodified and must still pass
unmarked after this file's tests are added — confirmed by running it, not by a second copy of it
here (this file's own module docstring, and the task text it implements, are explicit that the
identity assertion is what makes this widening safe, not a fact to re-derive).

**Harness** follows `test_players_history.py`'s conventions byte for byte where they overlap:
`client`/`db_session`/`environment` from `conftest.py`, a `sessions` row inserted directly and
signed exactly as `security.issue_session_cookie` would. Seed helpers are this file's own copies
rather than an import from a sibling test file — the same "duplicate rather than share one"
convention `routers/players.py`'s own module docstring applies to its session-resolution helpers,
extended here because a `[P]` batch shares one working tree and an import across sibling test files
would couple this file's outcome to a concurrently-written one.

**The negative that binds every route** (constitution VI, `contracts/http-api.md`'s field-semantics
table): no response may carry a colour hex, an icon URL or a flag URL — colours are design-system
tokens and asset URLs are resolved client-side from the pack, so a URL on the wire would bypass the
pack's coverage check as well as the token boundary. `test_no_response_carries_a_colour_hex_icon_
url_or_flag_url` below is parameterised over a small route table (`GET /api/matches`,
`GET /api/players/{profile_id}/matches`, `GET /api/matches/{game_id}`,
`GET /api/players/{profile_id}`) rather than spot-checked on one, and is **not** an `xfail`: none of
today's responses carry a hex or a URL either (the fields simply do not exist yet), so this is a
regression guard that must hold both before and after T425/T426 land, not a property only the
widened shape introduces.
"""

from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api import security
from aoe2stats_api.civilizations import civilisation_name
from aoe2stats_api.settings import get_settings
from aoe2stats_storage.models import (
    AoeProfile,
    Match,
    MatchPlayer,
    ProfileLink,
    SteamIdentity,
    User,
)
from aoe2stats_storage.models import Session as UserSession

pytestmark = [pytest.mark.usefixtures("environment")]

#: See `test_replay_status.py`'s module docstring — this suite's working assumption for the
#: session cookie's name, not yet fixed by a contract document beyond T028's own implementation.
SESSION_COOKIE_NAME = "session_id"

_CALLER_PROFILE_ID = 622_444_001
_OPPONENT_PROFILE_ID = 622_444_002


async def _seed_linked_profile(
    db_session: AsyncSession,
    *,
    profile_id: int = _CALLER_PROFILE_ID,
    steam_id64: str = "76561197960287950",
) -> User:
    """A user with one verified Steam identity and one active `profile_links` row for
    `profile_id` — mirrors `test_matches_list.py`'s and `test_players_history.py`'s helper of the
    same name and shape."""
    now = datetime.now(UTC)
    user = User(allowlisted_at=now)
    db_session.add(user)
    await db_session.flush()

    db_session.add(
        SteamIdentity(steam_id64=steam_id64, user_id=user.id, verified_at=now, last_sign_in_at=now)
    )
    db_session.add(AoeProfile(profile_id=profile_id, alias="Caller", country="fr"))
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
    """Insert a `sessions` row directly and hand the client its signed cookie — mirrors this
    repository's other API test files' own `_sign_in` helper."""
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


async def _seed_profile(
    db_session: AsyncSession, *, profile_id: int, alias: str, country: str | None
) -> None:
    db_session.add(AoeProfile(profile_id=profile_id, alias=alias, country=country))


async def _seed_match(
    db_session: AsyncSession,
    *,
    game_id: int,
    completed_at: datetime,
    map_name: str = "Arabia",
    leaderboard_id: int = 3,
    duration_seconds: int = 1800,
) -> None:
    db_session.add(
        Match(
            game_id=game_id,
            leaderboard_id=leaderboard_id,
            map_name=map_name,
            started_at=completed_at - timedelta(seconds=duration_seconds),
            completed_at=completed_at,
            duration_seconds=duration_seconds,
            source="relic",
            raw_payload={"game_id": game_id},
        )
    )


async def _seed_match_player(
    db_session: AsyncSession,
    *,
    game_id: int,
    profile_id: int,
    team_id: int | None,
    civ_id: int | None,
    color_id: int | None,
    result: str | None,
    rating: int | None,
    rating_diff: int | None,
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


async def _seed_match_and_two_participants(
    db_session: AsyncSession,
    *,
    game_id: int,
    completed_at: datetime,
    caller_civ_id: int = 10,
    caller_color_id: int = 4,
    caller_result: str | None = "win",
    caller_rating: int = 1512,
    caller_rating_diff: int = 16,
    opponent_civ_id: int = 777,
    opponent_color_id: int | None = 2,
    opponent_result: str | None = "loss",
    opponent_country: str | None = "be",
) -> None:
    """One match, the caller's own `match_players` row and one opponent's, on opposite teams —
    mirrors `test_players_history.py`'s `_seed_full_match`/`_seed_match_players` pair, generalised
    with the extra columns (`color_id`, absolute `rating`) this feature starts writing. Default
    civ ids are deliberately one covered by `KNOWN_CIVILISATION_NAMES` (`10`, "Cumans" —
    `test_matches_list.py`'s own precedent) and one outside it (`777`), so a single seed exercises
    FR-001's "never absent" rule for both the known-name and the fallback-label case at once."""
    await _seed_profile(
        db_session, profile_id=_OPPONENT_PROFILE_ID, alias="Opponent", country=opponent_country
    )
    await _seed_match(db_session, game_id=game_id, completed_at=completed_at)
    await _seed_match_player(
        db_session,
        game_id=game_id,
        profile_id=_CALLER_PROFILE_ID,
        team_id=1,
        civ_id=caller_civ_id,
        color_id=caller_color_id,
        result=caller_result,
        rating=caller_rating,
        rating_diff=caller_rating_diff,
    )
    await _seed_match_player(
        db_session,
        game_id=game_id,
        profile_id=_OPPONENT_PROFILE_ID,
        team_id=2,
        civ_id=opponent_civ_id,
        color_id=opponent_color_id,
        result=opponent_result,
        rating=1480,
        rating_diff=-caller_rating_diff if caller_rating_diff is not None else None,
    )
    await db_session.commit()


def _participant_by_profile_id(row: dict[str, Any], profile_id: int) -> dict[str, Any]:
    matches = [p for p in row["participants"] if p["profile_id"] == profile_id]
    assert len(matches) == 1, (
        f"expected exactly one participant for profile_id={profile_id} in {row['participants']!r}"
    )
    return matches[0]


# --- GET /api/matches — rating, team_id, color_id (contracts/http-api.md, T425) ------------------


@pytest.mark.xfail(strict=True, reason="T425 not implemented yet")
async def test_match_row_carries_rating_team_id_and_color_id(
    client: TestClient, db_session: AsyncSession
) -> None:
    """`contracts/http-api.md`: the caller's own `rating` (after the match), `team_id` and
    `color_id` widen the list row — previously only match detail carried an absolute rating."""
    caller = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, caller)
    game_id = 8_001
    await _seed_match_and_two_participants(
        db_session,
        game_id=game_id,
        completed_at=datetime.now(UTC),
        caller_color_id=4,
        caller_rating=1512,
    )

    response = client.get(f"/api/matches?profile_id={_CALLER_PROFILE_ID}")
    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"
    row = response.json()["matches"][0]

    assert row["rating"] == 1512, "the viewer's rating after the match (FR-005)"
    assert row["team_id"] == 1, "which side the viewer was on"
    assert row["color_id"] == 4, "FR-003"


# --- GET /api/matches — participants[] (contracts/http-api.md, FR-001, T425) ---------------------


@pytest.mark.xfail(strict=True, reason="T425 not implemented yet")
async def test_match_row_participants_include_every_player_with_civ_name_whenever_civ_id_present(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-001: `participants[]` carries **all** participants, the viewer included, and `civ_name`
    is never absent when `civ_id` is present — a known id resolves to its real name, an unknown one
    to feature 002's `"Civilisation {id}"` fallback, but never a bare integer the client would have
    to format itself."""
    caller = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, caller)
    game_id = 8_002
    await _seed_match_and_two_participants(
        db_session,
        game_id=game_id,
        completed_at=datetime.now(UTC),
        caller_civ_id=10,
        opponent_civ_id=777,
    )

    response = client.get(f"/api/matches?profile_id={_CALLER_PROFILE_ID}")
    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"
    row = response.json()["matches"][0]

    participant_ids = {p["profile_id"] for p in row["participants"]}
    assert participant_ids == {_CALLER_PROFILE_ID, _OPPONENT_PROFILE_ID}, (
        "participants[] carries every player, the viewer included, not only what opponents "
        f"already carries. Got {row['participants']!r}"
    )

    caller_participant = _participant_by_profile_id(row, _CALLER_PROFILE_ID)
    assert caller_participant["civ_id"] == 10
    assert caller_participant["civ_name"] == civilisation_name(10)
    assert caller_participant["civ_name"] not in (None, ""), (
        "a covered civ_id must resolve to a real name, never a blank"
    )

    opponent_participant = _participant_by_profile_id(row, _OPPONENT_PROFILE_ID)
    assert opponent_participant["civ_id"] == 777
    assert opponent_participant["civ_name"] == civilisation_name(777)
    assert opponent_participant["civ_name"] == "Civilisation 777", (
        "an id outside the mapping still resolves to a readable label, never a bare civ_id "
        f"(FR-010). Got {opponent_participant['civ_name']!r}"
    )


@pytest.mark.xfail(strict=True, reason="T425 not implemented yet")
async def test_match_row_participant_country_feeds_the_opponent_flag(
    client: TestClient, db_session: AsyncSession
) -> None:
    """`contracts/http-api.md`'s `participants[]` table: `country` is new on this shape and feeds
    the opponent flag; `null` when unknown."""
    caller = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, caller)
    game_id = 8_003
    await _seed_match_and_two_participants(
        db_session,
        game_id=game_id,
        completed_at=datetime.now(UTC),
        opponent_country="be",
    )

    response = client.get(f"/api/matches?profile_id={_CALLER_PROFILE_ID}")
    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"
    row = response.json()["matches"][0]

    opponent_participant = _participant_by_profile_id(row, _OPPONENT_PROFILE_ID)
    assert opponent_participant["country"] == "be"

    caller_participant = _participant_by_profile_id(row, _CALLER_PROFILE_ID)
    assert caller_participant["country"] == "fr"


@pytest.mark.xfail(strict=True, reason="T425 not implemented yet")
async def test_match_row_participant_null_result_is_not_a_loss(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-004: `result` is `"win"`, `"loss"` or `null`, and `null` is the neutral "not known"
    state — asserted here as the property that actually matters: a `null` result is never coerced
    into `"loss"`, and must not equal it under any read."""
    caller = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, caller)
    game_id = 8_004
    await _seed_match_and_two_participants(
        db_session,
        game_id=game_id,
        completed_at=datetime.now(UTC),
        caller_result="win",
        opponent_result=None,
    )

    response = client.get(f"/api/matches?profile_id={_CALLER_PROFILE_ID}")
    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"
    row = response.json()["matches"][0]

    opponent_participant = _participant_by_profile_id(row, _OPPONENT_PROFILE_ID)
    assert opponent_participant["result"] is None, (
        f"a result this service does not know must stay null, never a default. Got "
        f"{opponent_participant['result']!r}"
    )
    assert opponent_participant["result"] != "loss", (
        "the assertion FR-004 exists for: a null result must never read as a loss"
    )

    caller_participant = _participant_by_profile_id(row, _CALLER_PROFILE_ID)
    assert caller_participant["result"] == "win"


# --- The negative that binds every route (constitution VI) ---------------------------------------

_HEX_COLOUR_PATTERN = re.compile(r"#[0-9a-fA-F]{6}\b")
_URL_PATTERN = re.compile(r"https?://")


@pytest.mark.parametrize(
    "route_name",
    [
        "GET /api/matches",
        "GET /api/players/{profile_id}/matches",
        "GET /api/matches/{game_id}",
        "GET /api/players/{profile_id}",
    ],
)
async def test_no_response_carries_a_colour_hex_icon_url_or_flag_url(
    client: TestClient, db_session: AsyncSession, route_name: str
) -> None:
    """Constitution VI, `contracts/http-api.md`'s field-semantics table: no response carries a
    colour hex, an icon URL or a flag URL — colours are design-system tokens and asset URLs are
    resolved client-side from the pack (`packages/game-assets`), never handed to the client by the
    API. **Not** an `xfail`: today's responses carry none of these fields at all (the widened
    `color_id` and `avatar_hash` do not exist yet), so this must hold before T425/T426 land and
    stay holding afterwards — it is the regression guard the widening is checked against, not a
    property the widening introduces. Parameterised over the route table rather than spot-checked
    on one route, per the task text this file implements."""
    caller = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, caller)
    game_id = 8_005
    await _seed_match_and_two_participants(
        db_session,
        game_id=game_id,
        completed_at=datetime.now(UTC),
    )

    path_by_route_name = {
        "GET /api/matches": f"/api/matches?profile_id={_CALLER_PROFILE_ID}",
        "GET /api/players/{profile_id}/matches": f"/api/players/{_CALLER_PROFILE_ID}/matches",
        "GET /api/matches/{game_id}": f"/api/matches/{game_id}",
        "GET /api/players/{profile_id}": f"/api/players/{_CALLER_PROFILE_ID}",
    }
    response = client.get(path_by_route_name[route_name])
    assert response.status_code == 200, (
        f"{route_name} must answer for the seeded data. Got {response.status_code}: {response.text}"
    )

    body_text = response.text
    assert not _HEX_COLOUR_PATTERN.search(body_text), (
        f"{route_name} must never carry a colour hex — colours are design-system tokens "
        f"(constitution VI). Got {body_text}"
    )
    assert not _URL_PATTERN.search(body_text), (
        f"{route_name} must never carry an icon or flag URL — asset URLs are resolved "
        f"client-side from the pack, and a URL on the wire would bypass its coverage check. "
        f"Got {body_text}"
    )
