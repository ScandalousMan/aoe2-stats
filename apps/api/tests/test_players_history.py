"""T325: route tests for `GET /api/players/{profile_id}/matches`, encoding `quickstart.md`
scenario 4 ("Any player's profile and history") and FR-007. T328 has since implemented the route
in `apps/api/src/aoe2stats_api/routers/players.py` and removed every `xfail` marker this file
carried while it did not exist yet — the same discipline `test_matches_list.py` and
`test_players_routes.py` (both unmarked, their own implementing tasks having landed earlier)
already followed while they were in this same position.

**Scope, relative to this task's two siblings in the same `[P]` batch.** T324
(`test_match_detail.py`) owns the widened `GET /api/matches/{game_id}` (single match, every
participant). T326 (`test_third_party_history.py`) owns proving that reading a third party's
history persists the provider's response verbatim into `matches.raw_payload` (FR-011). This file
owns neither: it owns the **history list route** for *any* player, not only the caller's own —
FR-007's shape (newest first, opponent, map, civilisation, result, rating change, duration), the
empty-history case, and the one property the task text asks for by name: that this route's row
shape is not restated by hand here but asserted **against** what `GET /api/matches` already
returns for the identical underlying data.

**Why the row-shape comparison seeds a caller's own linked profile rather than an arbitrary third
party.** `GET /api/matches?profile_id=` (`routers/matches.py`, T070) is owner-scoped —
`_owned_active_link` — so it only ever answers for a profile the signed-in caller has linked. The
only profile both routes can be asked about in the same test is therefore the caller's own, so
`test_players_history_row_shape_matches_get_matches_row_shape` below seeds one linked profile and
its matches, then calls both routes for it and compares the rows directly, rather than restating
`GET /api/matches`'s fields as a second, hand-written expectation that could quietly drift from
the real one (this task's own text: "asserted against it rather than restated"). That the *new*
route must also answer for a profile the caller has **not** linked — the entire point of FR-008a —
is covered separately, by `test_players_history_returns_matches_newest_first_with_fr007_fields`
and `test_players_history_empty_history_returns_empty_state_not_error` below, both of which seed a
bare, unlinked `aoe_profiles` row.

**Harness** follows `test_matches_list.py` and `test_players_routes.py` byte for byte where they
overlap: `client`/`db_session`/`environment` from `conftest.py`, a `sessions` row inserted directly
and signed exactly as `security.issue_session_cookie` would. Seed helpers are this file's own
copies rather than an import from either sibling file — the same convention `routers/players.py`'s
own module docstring notes for its session-resolution helpers ("duplicate ... rather than share
one"), extended here to tests for the same reason: a `[P]` batch shares one working tree, and an
import across sibling test files would couple this file's outcome to a concurrently-written one.
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

#: See `test_replay_status.py`'s module docstring — this suite's working assumption for the
#: session cookie's name, not yet fixed by a contract document beyond T028's own implementation.
SESSION_COOKIE_NAME = "session_id"

_CALLER_PROFILE_ID = 611_333_001
_OPPONENT_PROFILE_ID = 611_333_002
_THIRD_PARTY_PROFILE_ID = 900_950_100


async def _seed_linked_profile(
    db_session: AsyncSession,
    *,
    profile_id: int = _CALLER_PROFILE_ID,
    steam_id64: str = "76561197960287940",
) -> User:
    """A user with one verified Steam identity and one active `profile_links` row for
    `profile_id` — mirrors `test_matches_list.py`'s helper of the same name and shape."""
    now = datetime.now(UTC)
    user = User(allowlisted_at=now)
    db_session.add(user)
    await db_session.flush()

    db_session.add(
        SteamIdentity(steam_id64=steam_id64, user_id=user.id, verified_at=now, last_sign_in_at=now)
    )
    db_session.add(AoeProfile(profile_id=profile_id, alias="Caller", country="FR"))
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
    `test_matches_list.py`'s and `test_players_routes.py`'s own `_sign_in` helper."""
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
    db_session: AsyncSession, *, profile_id: int, alias: str, country: str | None = "DE"
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


async def _seed_match_players(
    db_session: AsyncSession,
    *,
    game_id: int,
    subject_profile_id: int,
    subject_civ_id: int,
    subject_result: str,
    subject_rating_diff: int,
    opponent_profile_id: int = _OPPONENT_PROFILE_ID,
    opponent_civ_id: int = 2,
) -> None:
    """The player whose history is under test (`subject_profile_id`) plus one opponent on the
    other team — mirrors `test_matches_list.py`'s `_seed_match_players`, generalised past "the
    caller" since this route, unlike `GET /api/matches`, must also answer for a player who is not
    the signed-in caller (FR-008a)."""
    db_session.add(
        MatchPlayer(
            game_id=game_id,
            profile_id=subject_profile_id,
            team_id=1,
            civ_id=subject_civ_id,
            result=subject_result,
            rating=1500,
            rating_diff=subject_rating_diff,
        )
    )
    db_session.add(
        MatchPlayer(
            game_id=game_id,
            profile_id=opponent_profile_id,
            team_id=2,
            civ_id=opponent_civ_id,
            result="loss" if subject_result == "win" else "win",
            rating=1480,
            rating_diff=-subject_rating_diff,
        )
    )


async def _seed_capture(
    db_session: AsyncSession,
    *,
    game_id: int,
    profile_id: int,
    status: CaptureStatus = CaptureStatus.STORED,
    capture_deadline_at: datetime,
) -> None:
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


async def _seed_full_match(
    db_session: AsyncSession,
    *,
    game_id: int,
    completed_at: datetime,
    subject_profile_id: int,
    subject_civ_id: int = 1,
    subject_result: str = "win",
    subject_rating_diff: int = 18,
    map_name: str = "Arabia",
    leaderboard_id: int = 3,
    with_capture: bool = True,
) -> None:
    """One match, both `match_players` rows, and — for the caller's own profile only, mirroring
    `test_matches_list.py`'s `_seed_full_match` — a `stored` capture. `with_capture=False` is used
    for the third-party seed below: a capture row is keyed to the *caller* who discovered the
    match, and a bare third party the signed-in caller has never linked has no capture of their
    own to seed honestly here."""
    await _seed_match(
        db_session,
        game_id=game_id,
        completed_at=completed_at,
        map_name=map_name,
        leaderboard_id=leaderboard_id,
    )
    await _seed_match_players(
        db_session,
        game_id=game_id,
        subject_profile_id=subject_profile_id,
        subject_civ_id=subject_civ_id,
        subject_result=subject_result,
        subject_rating_diff=subject_rating_diff,
    )
    if with_capture:
        await _seed_capture(
            db_session,
            game_id=game_id,
            profile_id=subject_profile_id,
            capture_deadline_at=completed_at + timedelta(days=21),
        )


# --- GET /api/players/{profile_id}/matches — FR-007 -----------------------------------------------


async def test_players_history_returns_matches_newest_first_with_fr007_fields(
    client: TestClient, db_session: AsyncSession
) -> None:
    """Quickstart scenario 4.2 / FR-007: any player's matches, newest first, each row carrying
    opponent, map, civilisation, result, rating change and duration. Seeded for a third party the
    signed-in caller has never linked — the point of FR-008a — never through `GET /api/matches`'s
    own owner-scoped route, which could not answer this question at all."""
    caller = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, caller)
    await _seed_profile(
        db_session, profile_id=_THIRD_PARTY_PROFILE_ID, alias="ThirdPartySubject", country="BE"
    )
    await _seed_profile(db_session, profile_id=_OPPONENT_PROFILE_ID, alias="Opponent")

    now = datetime.now(UTC)
    oldest_game_id = 7_001
    middle_game_id = 7_002
    newest_game_id = 7_003

    await _seed_full_match(
        db_session,
        game_id=oldest_game_id,
        completed_at=now - timedelta(days=3),
        subject_profile_id=_THIRD_PARTY_PROFILE_ID,
        subject_civ_id=10,
        subject_result="loss",
        subject_rating_diff=-14,
        map_name="Black Forest",
        with_capture=False,
    )
    await _seed_full_match(
        db_session,
        game_id=middle_game_id,
        completed_at=now - timedelta(days=2),
        subject_profile_id=_THIRD_PARTY_PROFILE_ID,
        subject_civ_id=11,
        subject_result="win",
        subject_rating_diff=20,
        map_name="Arena",
        with_capture=False,
    )
    await _seed_full_match(
        db_session,
        game_id=newest_game_id,
        completed_at=now - timedelta(days=1),
        subject_profile_id=_THIRD_PARTY_PROFILE_ID,
        subject_civ_id=12,
        subject_result="win",
        subject_rating_diff=16,
        map_name="Arabia",
        with_capture=False,
    )
    await db_session.commit()

    response = client.get(f"/api/players/{_THIRD_PARTY_PROFILE_ID}/matches")

    assert response.status_code == 200, (
        f"a signed-in caller must be able to read any player's history (FR-008a). Got "
        f"{response.status_code}: {response.text}"
    )
    body = response.json()
    game_ids = [row["game_id"] for row in body["matches"]]
    assert game_ids == [newest_game_id, middle_game_id, oldest_game_id], (
        "newest first (FR-007): reverse-chronological by completed_at"
    )

    newest_row = body["matches"][0]
    assert newest_row["map_name"] == "Arabia"
    assert newest_row["civilisation"] == 12
    assert newest_row["result"] == "win"
    assert newest_row["rating_diff"] == 16
    assert newest_row["duration_seconds"] == 1800

    opponent_ids = {opponent["profile_id"] for opponent in newest_row["opponents"]}
    assert opponent_ids == {_OPPONENT_PROFILE_ID}, (
        "FR-007's 'opponent': the subject's own row is never listed among their own opponents"
    )


async def test_players_history_empty_history_returns_empty_state_not_error(
    client: TestClient, db_session: AsyncSession
) -> None:
    """US2 acceptance scenario 5, quickstart scenario 4 (via US1 scenario 5's sibling case): a
    player this service has observed but who has no matches at all gets a clear empty state — an
    empty list under `200` — never an error and never a 404, mirroring
    `test_matches_list.py`'s own `test_matches_list_empty_history_returns_empty_list_not_an_error`
    for the owner-scoped route."""
    caller = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, caller)
    no_matches_profile_id = 900_950_200
    await _seed_profile(db_session, profile_id=no_matches_profile_id, alias="NoMatchesAlias")
    await db_session.commit()

    response = client.get(f"/api/players/{no_matches_profile_id}/matches")

    assert response.status_code == 200, (
        f"a player with no matches must be a clear empty state, never an error. Got "
        f"{response.status_code}: {response.text}"
    )
    body = response.json()
    assert body["matches"] == []
    assert "next_cursor" in body, "the same envelope GET /api/matches answers with, empty or not"


async def test_players_history_row_shape_matches_get_matches_row_shape(
    client: TestClient, db_session: AsyncSession
) -> None:
    """The task's own text: "the row shape is the one `GET /api/matches` already returns, asserted
    against it rather than restated". Seeds one match for the *caller's own* linked profile — the
    only profile `GET /api/matches?profile_id=` (owner-scoped, T070) can answer for — then calls
    both routes for the identical underlying data and compares the rows directly, so this test can
    never drift from `GET /api/matches`'s real shape the way a second, hand-written list of
    expected keys could."""
    caller = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, caller)
    await _seed_profile(db_session, profile_id=_OPPONENT_PROFILE_ID, alias="Opponent")

    now = datetime.now(UTC)
    game_id = 7_100
    await _seed_full_match(
        db_session,
        game_id=game_id,
        completed_at=now,
        subject_profile_id=_CALLER_PROFILE_ID,
        subject_civ_id=15,
        subject_result="win",
        subject_rating_diff=22,
        map_name="Arena",
        with_capture=True,
    )
    await db_session.commit()

    reference_response = client.get(f"/api/matches?profile_id={_CALLER_PROFILE_ID}")
    assert reference_response.status_code == 200, (
        f"the reference route this test compares against must itself answer. Got "
        f"{reference_response.status_code}: {reference_response.text}"
    )
    reference_row = reference_response.json()["matches"][0]

    history_response = client.get(f"/api/players/{_CALLER_PROFILE_ID}/matches")
    assert history_response.status_code == 200, (
        f"Got {history_response.status_code}: {history_response.text}"
    )
    history_row = history_response.json()["matches"][0]

    assert history_row == reference_row, (
        "GET /api/players/{profile_id}/matches must serve the identical row shape and values "
        "GET /api/matches already returns for the same match and the same subject profile, "
        "never a second, independently-shaped presentation of the same facts (FR-008). "
        f"GET /api/matches row: {reference_row!r}\n"
        f"GET /api/players/.../matches row: {history_row!r}"
    )
