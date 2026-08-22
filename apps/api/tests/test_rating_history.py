"""Integration test for `GET /api/profiles/{profile_id}/ratings` (T068) — `contracts/http-api.md`'s
"Rating history from snapshots", the route T072's own task text names as satisfying FR-009: "System
MUST record a rating snapshot over time so rating history can be shown."

Follows `test_replay_status.py`'s harness conventions, itself following `test_unlink.py`'s: `client`
/ `db_session` against the real throwaway database (`conftest.py`), a `sessions` row inserted
directly and signed exactly as `security.issue_session_cookie` would — there is no reason to route
through the auth flow just to prove a session exists — and `pytestmark`'s `environment` fixture for
the full settings surface every router built on `SettingsDep` requires.

**Written before the route exists (T072).** `apps/api/src/aoe2stats_api/routers/profiles.py`
already exists — `GET /api/profiles`, `POST .../primary` and `DELETE /api/profiles/{profile_id}`
are all implemented (T031) — so there is no not-yet-existent *module* for a test-call-time import to
defer, unlike the provider tests and the very first US1 router tests, which predated their whole
router file. What does not yet exist is the *route*: `/api/profiles/{profile_id}/ratings` is
unregistered, so every request below 404s with FastAPI's own "not found" body today, for a reason
that has nothing to do with the assertions that follow it. Every test is marked
`@pytest.mark.xfail(strict=True, reason=XFAIL_REASON)` per this project's test-first convention
(CLAUDE.md, "Test-first tasks and the green-tree gate") until T072 adds the route — `strict=True` is
what turns the marker into a claim that must keep being true: the run goes red, forcing the marker's
removal, the moment T072 makes a test start passing for real.

**The response shape is this suite's working assumption, not yet pinned down by any contract
document beyond "Rating history from snapshots".** `GET /api/profiles` (`profiles.py`'s
`_latest_ratings_by_profile`) already answers *one* row per `(profile_id, leaderboard_id)` — the
most recent — with the field names `leaderboard_id`, `leaderboard_name`, `rating`, `rank`, `wins`,
`losses`, `streak`, `highest_rating`, `captured_at`. This endpoint answers the **history**, not just
the latest point, so the assumption here is the same per-entry shape, unfiltered across every
leaderboard the profile has played, as a flat list under `"ratings"` ordered chronologically
(`captured_at` ascending, `leaderboard_id` ascending as a tiebreaker) — the order a chart reads
left to right, and the one T072 is expected to produce reusing `profiles.py`'s existing field
names rather than inventing new ones for the same data. This is the one place to change if T072
lands on a different shape (e.g. grouped per leaderboard).

**FR-038 / FR-045 — one error, indistinguishable causes.** `T067`'s own task text names this route
as the second one in this phase, alongside `GET /api/matches`, that takes a `profile_id` the caller
may not own: "a rating curve for an arbitrary player is a public directory of players just as much
as a match list is." This file asserts the same three-case 404 `profiles.py`'s and `replays.py`'s
own `_owned_active_link` / `_profile_not_found` convention already establishes elsewhere in this
router (T067 is the dedicated cross-route test for this; this file's coverage of it is not a
substitute, only confirmation that the ratings route follows the same discipline as its siblings).
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api import security
from aoe2stats_api.settings import get_settings
from aoe2stats_storage.models import AoeProfile, ProfileLink, RatingSnapshot, SteamIdentity, User
from aoe2stats_storage.models import Session as UserSession

pytestmark = [pytest.mark.usefixtures("environment")]

# Every test in this file is expected to fail for exactly one reason — the route T072 adds does
# not exist yet — until it does. `strict=True` is what makes that honest: the moment T072 lands
# and a test starts passing, `strict=True` turns the *run* red instead of letting a stale xfail
# hide it, which is the whole point of marking these tests failing rather than skipping them. Do
# not drop `strict=True`.
XFAIL_REASON = (
    "GET /api/profiles/{profile_id}/ratings is implemented by T072, not this test-first task (T068)"
)

#: See `test_replay_status.py`'s module docstring — this suite's working assumption, not yet
#: fixed by a contract document beyond T028's own implementation.
SESSION_COOKIE_NAME = "session_id"

#: `profiles.py`'s and `replays.py`'s own `_profile_not_found()` message, asserted verbatim below
#: to tell the real ownership check apart from an accident: today, with the route unregistered,
#: `app.py`'s generic `HTTPException` handler answers an unmatched path with `code="not_found"`
#: too (`_http_status_error_code(404)` renders the phrase "Not Found" the same way), which would
#: make a bare `code == "not_found"` assertion XPASS for the wrong reason before T072 exists. The
#: message text differs — Starlette's own 404 carries "Not Found" — so asserting it keeps these
#: tests honestly red until the real ownership check runs.
_NOT_FOUND_MESSAGE = "No linked profile was found for that id."

_PROFILE_ID = 555111333
_OTHER_PROFILE_ID = 555111444


async def _seed_linked_profile(
    db_session: AsyncSession,
    *,
    profile_id: int = _PROFILE_ID,
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
    db_session.add(AoeProfile(profile_id=profile_id, alias="TestPlayer", country="FR"))
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


async def _seed_snapshot(
    db_session: AsyncSession,
    *,
    profile_id: int,
    leaderboard_id: int,
    captured_at: datetime,
    rating: int,
    rank: int | None = None,
    wins: int | None = None,
    losses: int | None = None,
    streak: int | None = None,
    highest_rating: int | None = None,
) -> None:
    db_session.add(
        RatingSnapshot(
            profile_id=profile_id,
            leaderboard_id=leaderboard_id,
            captured_at=captured_at,
            rating=rating,
            rank=rank,
            wins=wins,
            losses=losses,
            streak=streak,
            highest_rating=highest_rating,
        )
    )


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON)
async def test_ratings_requires_authentication(client: TestClient) -> None:
    """No session cookie at all: 401, never a leak of whether `profile_id` exists."""
    response = client.get(f"/api/profiles/{_PROFILE_ID}/ratings")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON)
async def test_ratings_unknown_profile_returns_not_found(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-045, case 1: a `profile_id` that names no link at all."""
    user = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)

    response = client.get(f"/api/profiles/{_PROFILE_ID + 999}/ratings")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert response.json()["error"]["message"] == _NOT_FOUND_MESSAGE


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON)
async def test_ratings_other_users_profile_returns_the_identical_not_found(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-045, case 2: a `profile_id` that is actively linked, but to a different account, must
    answer the same 404 as an unknown one — never a 403 that confirms the profile exists, and
    never the rating curve itself, which would be exactly the "public directory of players" T067
    and this module's docstring both name."""
    await _seed_linked_profile(db_session, profile_id=_PROFILE_ID)
    other_user = User(allowlisted_at=datetime.now(UTC), ingest_consent_at=datetime.now(UTC))
    db_session.add(other_user)
    await db_session.commit()
    await _sign_in(client, db_session, other_user)

    response = client.get(f"/api/profiles/{_PROFILE_ID}/ratings")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert response.json()["error"]["message"] == _NOT_FOUND_MESSAGE


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON)
async def test_ratings_unlinked_profile_returns_the_identical_not_found(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-045, case 3: a `profile_id` this very account once linked and then unlinked must also
    answer 404, not a stale success — `unlinked_at` is what `_owned_active_link` filters on
    elsewhere in this router (T031b's own convention)."""
    user = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)
    unlink_response = client.delete(f"/api/profiles/{_PROFILE_ID}?confirm=true")
    assert unlink_response.status_code == 200

    response = client.get(f"/api/profiles/{_PROFILE_ID}/ratings")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert response.json()["error"]["message"] == _NOT_FOUND_MESSAGE


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON)
async def test_ratings_profile_with_no_snapshots_returns_an_empty_curve(
    client: TestClient, db_session: AsyncSession
) -> None:
    """A profile with no `rating_snapshots` rows at all — a freshly linked profile before the
    first discovery cycle has run — gets an empty list rather than a 404 or an error: the profile
    itself is real and owned, the history is simply not there yet."""
    user = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)

    response = client.get(f"/api/profiles/{_PROFILE_ID}/ratings")

    assert response.status_code == 200
    assert response.json()["ratings"] == []


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON)
async def test_ratings_returns_the_curve_ordered_chronologically(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-009: every snapshot for the caller's own profile comes back, across every leaderboard it
    has played, oldest first — the order a rating curve is drawn in — and each entry carries the
    full set of fields `rating_snapshots` records (data-model.md), plus the served
    `leaderboard_name` `GET /api/profiles` already names (T033a). A snapshot belonging to a
    *different* profile is never mixed in, even one the same account also owns."""
    user = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)
    now = datetime.now(UTC)

    # Two observations on leaderboard 3 (1v1 Random Map), three days apart, plus one on
    # leaderboard 13 (1v1 Empire Wars) in between — chronological order must interleave them by
    # `captured_at`, not group them by leaderboard.
    await _seed_snapshot(
        db_session,
        profile_id=_PROFILE_ID,
        leaderboard_id=3,
        captured_at=now - timedelta(days=3),
        rating=1500,
        rank=100,
        wins=10,
        losses=5,
        streak=2,
        highest_rating=1520,
    )
    await _seed_snapshot(
        db_session,
        profile_id=_PROFILE_ID,
        leaderboard_id=13,
        captured_at=now - timedelta(days=2),
        rating=1200,
        rank=None,
        wins=1,
        losses=0,
        streak=1,
        highest_rating=1200,
    )
    await _seed_snapshot(
        db_session,
        profile_id=_PROFILE_ID,
        leaderboard_id=3,
        captured_at=now - timedelta(days=1),
        rating=1518,
        rank=95,
        wins=11,
        losses=5,
        streak=3,
        highest_rating=1520,
    )

    # A second, otherwise-unlinked profile's own history must never leak into the response, even
    # though nothing about the request names it.
    db_session.add(AoeProfile(profile_id=_OTHER_PROFILE_ID, alias="Someone Else", country="FR"))
    await db_session.flush()
    await _seed_snapshot(
        db_session,
        profile_id=_OTHER_PROFILE_ID,
        leaderboard_id=3,
        captured_at=now - timedelta(days=1, hours=12),
        rating=2000,
    )
    await db_session.commit()

    response = client.get(f"/api/profiles/{_PROFILE_ID}/ratings")

    assert response.status_code == 200
    ratings = response.json()["ratings"]
    assert len(ratings) == 3, (
        "the other profile's own snapshot must not leak in, even though nothing about the "
        "request names it"
    )
    assert [entry["leaderboard_id"] for entry in ratings] == [3, 13, 3]
    assert [entry["rating"] for entry in ratings] == [1500, 1200, 1518]

    first, second, third = ratings
    assert first["leaderboard_name"] == "1v1 Random Map"
    assert first["rank"] == 100
    assert first["wins"] == 10
    assert first["losses"] == 5
    assert first["streak"] == 2
    assert first["highest_rating"] == 1520
    assert first["captured_at"] == (now - timedelta(days=3)).isoformat()

    assert second["leaderboard_name"] == "1v1 Empire Wars"
    assert second["rank"] is None

    assert third["captured_at"] == (now - timedelta(days=1)).isoformat()
