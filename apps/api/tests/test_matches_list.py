"""Integration test for `GET /api/matches` (T063) — `contracts/http-api.md`'s "Newest first,
cursor paginated. Each row carries its capture status and `capture_deadline_at`" plus FR-010's own
list of what a row must show: opponent, map, civilisation, result, rating change and duration.

**Targets `aoe2stats_api.routers.matches` (T070) and `aoe2stats_storage.repositories.matches`
(T069), neither of which exists yet.** `matches.router` is not registered in `app.py`'s
`create_app()` (see that module's own docstring: each user-story phase adds its router as a two-
line change there, and US3's has not landed), so `GET /api/matches` today resolves to no route at
all and every test below fails on that 404 rather than on a real assertion — for the right reason,
per CLAUDE.md's test-first convention. Every test carries
`@pytest.mark.xfail(strict=True, reason="T070 not implemented yet")`. Nothing here needs to import
a not-yet-existing module directly — the whole surface is exercised through `client`, exactly as
`test_replay_status.py` (T062) exercises its own router — so there is no module-scope import to
guard against a collection error.

**The response shape asserted below is inferred, not read off an existing contract**, the same
position `test_deadline_order.py` (T045) was in for `DrainStage` before T055 landed, and is
expected to need adjusting once T070 actually lands:

- `{"matches": [...], "next_cursor": <opaque string> | null}` — a `matches` array plus an opaque
  cursor for the next page, `null` once there is no more.
- Each row: `game_id`, `started_at`, `completed_at` (ISO 8601), `map_name`, `leaderboard_id`,
  `duration_seconds`, `civilisation` (the caller's own `civ_id`), `result` (the caller's own),
  `rating_diff` (the caller's own rating change), `opponents` (every other participant: their
  `profile_id`, `alias`, `civ_id`), `capture_status` and `capture_deadline_at` — the latter two per
  the contract line quoted above, `data-model.md`'s `replay_captures` row for
  `(game_id, profile_id)`. Assertions below check this subset of keys with the values each test
  seeds, not the full dict, so a reasonable implementation is free to add further fields (`patch`,
  `source`, ...) without breaking this file.

**Harness**: follows `test_replay_status.py`'s conventions byte for byte — `client`/`db_session`
against the real throwaway database (`conftest.py`), a `sessions` row inserted directly and signed
exactly as `security.issue_session_cookie` would, and `pytestmark`'s `environment` fixture for the
full 18-key settings surface every router built on `SettingsDep` requires.

**Cursor pagination "stable across insertions"** is the property that distinguishes a cursor from
an `OFFSET`: a row inserted *above* an already-issued cursor (a newer match arriving between two
requests) must not shift what the next page returns, because an `OFFSET`-based scheme would shift
by exactly one and either duplicate or skip a row depending on which side of the insertion the
offset lands. `test_matches_list_cursor_pagination_is_stable_across_insertions` proves it by
fetching page one, inserting a *new, newer* match, then fetching page two with the cursor page one
returned: page two must be exactly what it would have been had the insertion never happened, and a
fresh page one (no cursor) must now lead with the new match.
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

#: See `test_replay_status.py`'s module docstring: this suite's working assumption for the
#: session cookie's name, not yet fixed by a contract document beyond T028's own implementation.
SESSION_COOKIE_NAME = "session_id"

_CALLER_PROFILE_ID = 611222333
_OPPONENT_PROFILE_ID = 611222444


async def _seed_linked_profile(
    db_session: AsyncSession,
    *,
    profile_id: int = _CALLER_PROFILE_ID,
    steam_id64: str = "76561197960287930",
) -> User:
    """A user with one verified Steam identity and one active `profile_links` row for
    `profile_id` — mirrors `test_replay_status.py`'s helper of the same name and shape."""
    now = datetime.now(UTC)
    user = User(allowlisted_at=now, ingest_consent_at=now)
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
    `test_replay_status.py`'s and `test_unlink.py`'s own `_sign_in` helper."""
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
    game_id: int,
    completed_at: datetime,
    map_name: str = "Arabia",
    leaderboard_id: int = 3,
    duration_seconds: int = 1800,
    started_at: datetime | None = None,
) -> None:
    db_session.add(
        Match(
            game_id=game_id,
            leaderboard_id=leaderboard_id,
            map_name=map_name,
            started_at=started_at or (completed_at - timedelta(seconds=duration_seconds)),
            completed_at=completed_at,
            duration_seconds=duration_seconds,
            source="relic",
            raw_payload={"game_id": game_id},
        )
    )


async def _seed_opponent_profile(
    db_session: AsyncSession, *, profile_id: int = _OPPONENT_PROFILE_ID, alias: str = "Opponent"
) -> None:
    db_session.add(AoeProfile(profile_id=profile_id, alias=alias, country="DE"))


async def _seed_match_players(
    db_session: AsyncSession,
    *,
    game_id: int,
    caller_profile_id: int = _CALLER_PROFILE_ID,
    caller_civ_id: int,
    caller_result: str,
    caller_rating_diff: int,
    opponent_profile_id: int = _OPPONENT_PROFILE_ID,
    opponent_civ_id: int = 2,
) -> None:
    db_session.add(
        MatchPlayer(
            game_id=game_id,
            profile_id=caller_profile_id,
            team_id=1,
            civ_id=caller_civ_id,
            result=caller_result,
            rating=1500,
            rating_diff=caller_rating_diff,
        )
    )
    db_session.add(
        MatchPlayer(
            game_id=game_id,
            profile_id=opponent_profile_id,
            team_id=2,
            civ_id=opponent_civ_id,
            result="loss" if caller_result == "win" else "win",
            rating=1480,
            rating_diff=-caller_rating_diff,
        )
    )


async def _seed_capture(
    db_session: AsyncSession,
    *,
    game_id: int,
    profile_id: int = _CALLER_PROFILE_ID,
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
    caller_civ_id: int = 1,
    caller_result: str = "win",
    caller_rating_diff: int = 18,
    map_name: str = "Arabia",
) -> None:
    """One match, both `match_players` rows, and a `stored` capture for the caller — the shape
    every happy-path test in this file needs."""
    await _seed_match(db_session, game_id=game_id, completed_at=completed_at, map_name=map_name)
    await _seed_match_players(
        db_session,
        game_id=game_id,
        caller_civ_id=caller_civ_id,
        caller_result=caller_result,
        caller_rating_diff=caller_rating_diff,
    )
    await _seed_capture(
        db_session, game_id=game_id, capture_deadline_at=completed_at + timedelta(days=21)
    )


@pytest.mark.xfail(strict=True, reason="T070 not implemented yet")
async def test_matches_list_requires_authentication(client: TestClient) -> None:
    """No session cookie at all: 401, the same shape every other router in this feature answers
    with (`test_replay_status.py`)."""
    response = client.get(f"/api/matches?profile_id={_CALLER_PROFILE_ID}")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


@pytest.mark.xfail(strict=True, reason="T070 not implemented yet")
async def test_matches_list_requires_profile_id_query_param(
    client: TestClient, db_session: AsyncSession
) -> None:
    """`profile_id` is required, mirroring `GET /api/replays/status`'s own contract."""
    user = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)

    response = client.get("/api/matches")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.xfail(strict=True, reason="T070 not implemented yet")
async def test_matches_list_newest_first_with_fr010_fields(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-010: matches newest first, each row carrying opponent, map, civilisation, result,
    rating change and duration — plus the contract line's capture status and deadline."""
    user = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)
    await _seed_opponent_profile(db_session)

    now = datetime.now(UTC)
    oldest_game_id = 2_001
    middle_game_id = 2_002
    newest_game_id = 2_003

    await _seed_full_match(
        db_session,
        game_id=oldest_game_id,
        completed_at=now - timedelta(days=3),
        caller_civ_id=10,
        caller_result="loss",
        caller_rating_diff=-14,
        map_name="Black Forest",
    )
    await _seed_full_match(
        db_session,
        game_id=middle_game_id,
        completed_at=now - timedelta(days=2),
        caller_civ_id=11,
        caller_result="win",
        caller_rating_diff=20,
        map_name="Arena",
    )
    await _seed_full_match(
        db_session,
        game_id=newest_game_id,
        completed_at=now - timedelta(days=1),
        caller_civ_id=12,
        caller_result="win",
        caller_rating_diff=16,
        map_name="Arabia",
    )
    await db_session.commit()

    response = client.get(f"/api/matches?profile_id={_CALLER_PROFILE_ID}")

    assert response.status_code == 200
    body = response.json()
    game_ids = [row["game_id"] for row in body["matches"]]
    assert game_ids == [newest_game_id, middle_game_id, oldest_game_id], (
        "newest first (FR-010): reverse-chronological by completed_at"
    )

    newest_row = body["matches"][0]
    assert newest_row["map_name"] == "Arabia"
    assert newest_row["civilisation"] == 12
    assert newest_row["result"] == "win"
    assert newest_row["rating_diff"] == 16
    assert newest_row["duration_seconds"] == 1800
    assert newest_row["capture_status"] == CaptureStatus.STORED.value
    assert "capture_deadline_at" in newest_row

    opponent_ids = {opponent["profile_id"] for opponent in newest_row["opponents"]}
    assert opponent_ids == {_OPPONENT_PROFILE_ID}, (
        "the caller's own row is never listed among their own opponents"
    )


@pytest.mark.xfail(strict=True, reason="T070 not implemented yet")
async def test_matches_list_respects_limit_and_returns_a_next_cursor(
    client: TestClient, db_session: AsyncSession
) -> None:
    """A page bounded by `limit` carries a `next_cursor` when more rows remain."""
    user = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)
    await _seed_opponent_profile(db_session)

    now = datetime.now(UTC)
    game_ids = [3_001, 3_002, 3_003]
    for offset, game_id in enumerate(game_ids):
        await _seed_full_match(
            db_session, game_id=game_id, completed_at=now - timedelta(days=offset)
        )
    await db_session.commit()

    response = client.get(f"/api/matches?profile_id={_CALLER_PROFILE_ID}&limit=2")

    assert response.status_code == 200
    body = response.json()
    assert len(body["matches"]) == 2
    assert body["matches"][0]["game_id"] == 3_001
    assert body["matches"][1]["game_id"] == 3_002
    assert body["next_cursor"] is not None


@pytest.mark.xfail(strict=True, reason="T070 not implemented yet")
async def test_matches_list_cursor_pagination_is_stable_across_insertions(
    client: TestClient, db_session: AsyncSession
) -> None:
    """A cursor, not an offset: a match inserted *above* an already-issued cursor must not shift
    what the next page returns (module docstring)."""
    user = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)
    await _seed_opponent_profile(db_session)

    now = datetime.now(UTC)
    # completed_at descending: 4_004 (newest) .. 4_001 (oldest), seeded oldest-first so insertion
    # order can never be mistaken for the ordering under test.
    for offset, game_id in ((3, 4_001), (2, 4_002), (1, 4_003), (0, 4_004)):
        await _seed_full_match(
            db_session, game_id=game_id, completed_at=now - timedelta(days=offset)
        )
    await db_session.commit()

    page_one = client.get(f"/api/matches?profile_id={_CALLER_PROFILE_ID}&limit=2")
    assert page_one.status_code == 200
    page_one_body = page_one.json()
    assert [row["game_id"] for row in page_one_body["matches"]] == [4_004, 4_003]
    cursor = page_one_body["next_cursor"]
    assert cursor is not None

    # A brand-new match, newer than everything already seen — the case that breaks OFFSET-based
    # pagination by shifting every subsequent page by one row.
    newest_game_id = 4_005
    await _seed_full_match(db_session, game_id=newest_game_id, completed_at=now + timedelta(days=1))
    await db_session.commit()

    page_two = client.get(f"/api/matches?profile_id={_CALLER_PROFILE_ID}&cursor={cursor}&limit=2")
    assert page_two.status_code == 200
    page_two_body = page_two.json()
    assert [row["game_id"] for row in page_two_body["matches"]] == [4_002, 4_001], (
        "the cursor is bound to game 4_003's position, so a newer insertion above it must not "
        "shift, duplicate or skip anything in this page (SC-006's dedup discipline extended to "
        "pagination itself)"
    )
    assert page_two_body["next_cursor"] is None, "exactly four matches remain after this page"

    # A fresh, cursor-less page one now leads with the new match.
    fresh_page_one = client.get(f"/api/matches?profile_id={_CALLER_PROFILE_ID}&limit=2")
    assert fresh_page_one.status_code == 200
    assert [row["game_id"] for row in fresh_page_one.json()["matches"]] == [
        newest_game_id,
        4_004,
    ]


@pytest.mark.xfail(strict=True, reason="T070 not implemented yet")
async def test_matches_list_empty_history_returns_empty_list_not_an_error(
    client: TestClient, db_session: AsyncSession
) -> None:
    """A linked profile with no matches at all: an empty list, never a broken or error response —
    the list-level analogue of Acceptance Scenario 5 (US3), whose detailed empty-state assertions
    belong to T065's `test_capture_visibility.py`."""
    user = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)

    response = client.get(f"/api/matches?profile_id={_CALLER_PROFILE_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["matches"] == []
    assert body["next_cursor"] is None
