"""Integration tests for T102's `ResponseCache` (`aoe2stats_api.deps`), wired into `GET /api/
matches`, `GET /api/matches/{game_id}`, `GET /api/profiles` and `GET /api/profiles/{profile_id}/
ratings` — see those four routers' own module and function docstrings for exactly what each caches
and why.

**Policy under test, in one place.** T102's task text sets the bar as "does not re-query the
source" for a repeat view, and "not indefinitely" stale for anything a write could change. This
project answers both with a single mechanism per cached route: a short (`_DEFAULT_TTL_SECONDS =
30`, `deps.py`) in-process TTL bounds every cached response's age on its own, and the one same-
process write path that can change a cached response *inside a user's own request/response cycle*
— a manual replay upload (`routers/replays.py::upload_replay`), and a primary/unlink change on
`routers/profiles.py` — calls `cache.invalidate_prefix` explicitly rather than leaving that caller
to wait out the TTL. `apps/ingester`'s daily cycle is a *different* process (`ResponseCache`'s own
docstring) and needs no invalidation call from this codebase at all; the TTL alone bounds it.

**How "does not re-query the source" is proved without counting SQL statements.** Every "cache hit"
test below warms the cache with one request, then **mutates the underlying row directly through
`db_session`** — the same technique `test_matches_list.py`'s own pagination test uses to simulate a
write from outside the request under test — and makes the identical request again inside the TTL
window. The response still carries the *pre-mutation* value: if the route had re-run its query, the
mutated value would come back instead. This is a black-box proof that costs nothing to keep in sync
with a repository's own SQL, unlike a raw query-count assertion would.

**`test_matches_list_first_page_is_never_cached`** guards the one correctness bug found writing
this cache: caching `GET /api/matches`'s cursor-less first page broke
`test_matches_list.py::test_matches_list_cursor_pagination_is_stable_across_insertions`, because
that page's answer is defined as "whatever is newest right now" and legitimately changes the moment
a new match is discovered — unlike a page reached through an explicit `cursor`, which the
pagination scheme itself guarantees is stable under insertion (that test's own docstring). See
`routers/matches.py::list_matches`'s own docstring for the full reasoning; this file only asserts
the resulting behaviour.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api import security
from aoe2stats_api.deps import ResponseCache, get_response_cache
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

#: See `test_replay_status.py`'s and `test_matches_list.py`'s own module docstrings — this suite's
#: working assumption for the session cookie's name.
SESSION_COOKIE_NAME = "session_id"

_CALLER_PROFILE_ID = 651300100
_OPPONENT_PROFILE_ID = 651300200


async def _seed_linked_profile(
    db_session: AsyncSession,
    *,
    profile_id: int = _CALLER_PROFILE_ID,
    steam_id64: str = "76561197960287930",
) -> User:
    """A user with one verified Steam identity and one active `profile_links` row for
    `profile_id` — mirrors `test_matches_list.py`'s own helper of the same name and shape."""
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
    """Mirrors `test_matches_list.py`'s own `_sign_in`."""
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


async def _seed_match_players(
    db_session: AsyncSession,
    *,
    game_id: int,
    caller_profile_id: int = _CALLER_PROFILE_ID,
    opponent_profile_id: int | None = None,
) -> None:
    # A distinct opponent per match by default: `_seed_full_match` is called more than once in the
    # same test in several files below, and a shared opponent id would collide on `aoe_profiles`'
    # own primary key the second time.
    if opponent_profile_id is None:
        opponent_profile_id = _OPPONENT_PROFILE_ID + game_id
    db_session.add(AoeProfile(profile_id=opponent_profile_id, alias="Opponent", country="DE"))
    db_session.add(
        MatchPlayer(
            game_id=game_id,
            profile_id=caller_profile_id,
            team_id=1,
            civ_id=1,
            result="win",
            rating=1500,
            rating_diff=18,
        )
    )
    db_session.add(
        MatchPlayer(
            game_id=game_id,
            profile_id=opponent_profile_id,
            team_id=2,
            civ_id=2,
            result="loss",
            rating=1480,
            rating_diff=-18,
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
    map_name: str = "Arabia",
) -> None:
    await _seed_match(db_session, game_id=game_id, completed_at=completed_at, map_name=map_name)
    await _seed_match_players(db_session, game_id=game_id)
    await _seed_capture(
        db_session, game_id=game_id, capture_deadline_at=completed_at + timedelta(days=21)
    )


# --- GET /api/matches/{game_id}: cache hit avoids the database ---------------------------------


async def test_match_detail_repeat_view_is_served_from_cache_not_the_database(
    client: TestClient, db_session: AsyncSession
) -> None:
    """A second `GET` for the same match, inside the TTL, answers with the *first* response's data
    even after the underlying row changes — proving the second call never re-ran the query (module
    docstring)."""
    user = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)
    game_id = 800100100
    await _seed_full_match(db_session, game_id=game_id, completed_at=datetime.now(UTC))
    await db_session.commit()

    first = client.get(f"/api/matches/{game_id}")
    assert first.status_code == 200
    assert first.json()["map_name"] == "Arabia"

    await db_session.execute(
        update(Match).where(Match.game_id == game_id).values(map_name="Highland")
    )
    await db_session.commit()

    second = client.get(f"/api/matches/{game_id}")
    assert second.status_code == 200
    assert second.json()["map_name"] == "Arabia", (
        "a cache hit must answer from memory, never re-run the query — the mutated map_name would "
        "appear here if it had"
    )


async def test_match_detail_cache_expires_after_its_ttl(
    client: TestClient, db_session: AsyncSession
) -> None:
    """Past the TTL, the next request reads fresh — the "not indefinitely" half of T102's own task
    text, proved with a controllable clock rather than a real wait."""
    user = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)
    game_id = 800100200
    await _seed_full_match(db_session, game_id=game_id, completed_at=datetime.now(UTC))
    await db_session.commit()

    clock = {"now": 0.0}
    fake_cache = ResponseCache(ttl_seconds=5, clock=lambda: clock["now"])
    client.app.dependency_overrides[get_response_cache] = lambda: fake_cache
    try:
        first = client.get(f"/api/matches/{game_id}")
        assert first.status_code == 200
        assert first.json()["map_name"] == "Arabia"

        await db_session.execute(
            update(Match).where(Match.game_id == game_id).values(map_name="Highland")
        )
        await db_session.commit()

        # Still inside the TTL: the stale value.
        clock["now"] += 1
        still_cached = client.get(f"/api/matches/{game_id}")
        assert still_cached.json()["map_name"] == "Arabia"

        # Past the TTL: a fresh read.
        clock["now"] += 10
        after_ttl = client.get(f"/api/matches/{game_id}")
        assert after_ttl.json()["map_name"] == "Highland"
    finally:
        del client.app.dependency_overrides[get_response_cache]


# --- GET /api/matches: only a page reached through a cursor is cached --------------------------


async def test_matches_list_continuation_page_is_cached(
    client: TestClient, db_session: AsyncSession
) -> None:
    """A page fetched with an explicit `cursor` is cached — the repository's own pagination scheme
    already guarantees it cannot change under insertion (`routers/matches.py::list_matches`'s own
    docstring), which is what makes caching it safe."""
    user = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)
    now = datetime.now(UTC)
    await _seed_full_match(db_session, game_id=800200100, completed_at=now, map_name="Arabia")
    await _seed_full_match(
        db_session, game_id=800200099, completed_at=now - timedelta(days=1), map_name="Islands"
    )
    await db_session.commit()

    page_one = client.get(f"/api/matches?profile_id={_CALLER_PROFILE_ID}&limit=1")
    assert page_one.status_code == 200
    cursor = page_one.json()["next_cursor"]
    assert cursor is not None

    page_two = client.get(f"/api/matches?profile_id={_CALLER_PROFILE_ID}&cursor={cursor}&limit=1")
    assert page_two.status_code == 200
    assert page_two.json()["matches"][0]["map_name"] == "Islands"

    await db_session.execute(
        update(Match).where(Match.game_id == 800200099).values(map_name="Highland")
    )
    await db_session.commit()

    page_two_again = client.get(
        f"/api/matches?profile_id={_CALLER_PROFILE_ID}&cursor={cursor}&limit=1"
    )
    assert page_two_again.json()["matches"][0]["map_name"] == "Islands", (
        "a continuation page is cached and must answer from memory, never re-run the query"
    )


async def test_matches_list_first_page_is_never_cached(
    client: TestClient, db_session: AsyncSession
) -> None:
    """The regression this cache introduced and then closed: the cursor-less first page must
    always reflect the latest state, because its own answer legitimately changes when a new match
    is discovered (module docstring; `routers/matches.py::list_matches`'s own docstring)."""
    user = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)
    now = datetime.now(UTC)
    await _seed_full_match(db_session, game_id=800200200, completed_at=now)
    await db_session.commit()

    first = client.get(f"/api/matches?profile_id={_CALLER_PROFILE_ID}&limit=5")
    assert first.status_code == 200
    assert [row["game_id"] for row in first.json()["matches"]] == [800200200]

    # A brand-new, newer match, inserted directly — standing in for a discovery cycle landing
    # between two page-one views.
    await _seed_full_match(db_session, game_id=800200201, completed_at=now + timedelta(days=1))
    await db_session.commit()

    second = client.get(f"/api/matches?profile_id={_CALLER_PROFILE_ID}&limit=5")
    assert [row["game_id"] for row in second.json()["matches"]] == [800200201, 800200200], (
        "the first page must never be cached: a reload right after a new match is discovered must "
        "show it immediately"
    )


# --- GET /api/profiles/{profile_id}/ratings: cache hit avoids the database ---------------------


async def test_ratings_history_repeat_view_is_served_from_cache_not_the_database(
    client: TestClient, db_session: AsyncSession
) -> None:
    user = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)
    captured_at = datetime.now(UTC)
    db_session.add(
        RatingSnapshot(
            profile_id=_CALLER_PROFILE_ID,
            leaderboard_id=3,
            captured_at=captured_at,
            rating=1500,
            rank=100,
            wins=10,
            losses=5,
            streak=2,
            highest_rating=1550,
        )
    )
    await db_session.commit()

    first = client.get(f"/api/profiles/{_CALLER_PROFILE_ID}/ratings")
    assert first.status_code == 200
    assert first.json()["ratings"][0]["rating"] == 1500

    await db_session.execute(
        update(RatingSnapshot)
        .where(
            RatingSnapshot.profile_id == _CALLER_PROFILE_ID,
            RatingSnapshot.leaderboard_id == 3,
            RatingSnapshot.captured_at == captured_at,
        )
        .values(rating=1800)
    )
    await db_session.commit()

    second = client.get(f"/api/profiles/{_CALLER_PROFILE_ID}/ratings")
    assert second.json()["ratings"][0]["rating"] == 1500, (
        "a cache hit must answer from memory, never re-run the query — a rating this cache did not "
        "write can only change through a daily ingestion cycle, a different process entirely "
        "(ResponseCache's own docstring), so the TTL alone is the bound here"
    )


# --- Invalidation: a manual upload must not wait out the TTL -----------------------------------


async def test_manual_upload_invalidates_the_match_detail_cache(
    client: TestClient, db_session: AsyncSession
) -> None:
    """The invalidation policy under test: a same-process write (`upload_replay`) makes its own
    effect visible on the very next request, rather than leaving the caller to wait out
    `ResponseCache`'s TTL for their own upload to appear (module docstring)."""
    from pathlib import Path

    fixture_path = (
        Path(__file__).resolve().parents[3]
        / "tests"
        / "fixtures"
        / "replays"
        / "AgeIIDE_Replay_500546441.zip"
    )
    fixture_game_id = 500546441
    fixture_profile_id = 196240

    user = await _seed_linked_profile(db_session, profile_id=fixture_profile_id)
    await _sign_in(client, db_session, user)

    completed_at = datetime.now(UTC) - timedelta(days=40)
    await _seed_match(db_session, game_id=fixture_game_id, completed_at=completed_at)
    db_session.add(MatchPlayer(game_id=fixture_game_id, profile_id=fixture_profile_id))
    db_session.add(
        ReplayCapture(
            game_id=fixture_game_id,
            profile_id=fixture_profile_id,
            status=CaptureStatus.EXPIRED,
            capture_deadline_at=completed_at + timedelta(days=21),
            source=CaptureSource.AUTOMATIC,
        )
    )
    await db_session.commit()

    warmed = client.get(f"/api/matches/{fixture_game_id}")
    assert warmed.status_code == 200
    assert warmed.json()["capture_status"] == CaptureStatus.EXPIRED.value

    upload = client.post(
        f"/api/replays/{fixture_game_id}/upload",
        files={
            "file": (
                "AgeIIDE_Replay_500546441.aoe2record",
                fixture_path.read_bytes(),
                "application/zip",
            )
        },
    )
    assert upload.status_code == 200
    assert upload.json()["status"] == CaptureStatus.STORED.value

    after_upload = client.get(f"/api/matches/{fixture_game_id}")
    assert after_upload.json()["capture_status"] == CaptureStatus.STORED.value, (
        "invalidation, not the TTL, must make this visible immediately — the TTL alone (30s) far "
        "outlives this test"
    )


# --- Invalidation: a primary-profile change must not wait out the TTL --------------------------


async def test_set_primary_profile_invalidates_the_profiles_list_cache(
    client: TestClient, db_session: AsyncSession
) -> None:
    second_profile_id = _CALLER_PROFILE_ID + 1
    user = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)

    now = datetime.now(UTC)
    db_session.add(AoeProfile(profile_id=second_profile_id, alias="Alt", country="FR"))
    await db_session.flush()
    db_session.add(
        ProfileLink(
            user_id=user.id,
            profile_id=second_profile_id,
            steam_id64="76561197960287930",
            is_primary=False,
            linked_at=now,
        )
    )
    await db_session.commit()

    warmed = client.get("/api/profiles")
    assert warmed.status_code == 200
    primary_ids = {p["profile_id"] for p in warmed.json()["profiles"] if p["is_primary"]}
    assert primary_ids == {_CALLER_PROFILE_ID}

    promote = client.post(f"/api/profiles/{second_profile_id}/primary")
    assert promote.status_code == 200

    after_promote = client.get("/api/profiles")
    primary_ids_after = {
        p["profile_id"] for p in after_promote.json()["profiles"] if p["is_primary"]
    }
    assert primary_ids_after == {second_profile_id}, (
        "invalidation, not the TTL, must make the new primary visible immediately"
    )
