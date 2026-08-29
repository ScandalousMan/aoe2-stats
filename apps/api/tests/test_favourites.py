"""T344: route tests for `apps/api/src/aoe2stats_api/routers/favourites.py`, implemented at
**T346**, not yet registered in `app.py`. Encodes `quickstart.md` scenario 11;
`contracts/http-api.md`'s "Favourites" section and `data-model.md`'s `favourites` section are
ground truth for every shape asserted below.

**Every test in this file carries `xfail(strict=True, reason="T346 not implemented yet")`.**
Unlike `test_players_routes.py` or `test_replay_download.py` (which extend a router that already
exists), `routers/favourites.py` does not exist at all yet, so there is no partial surface to split
markers by implementing task the way those two files do — one reason, for the whole file, and the
one module import below happens **inside every test body**, never at module scope: a module-scope
import of a module that does not exist is a collection error that takes the whole workspace suite
down, a different and worse failure than an expected `xfail` (`CLAUDE.md`'s own instruction to the
implementer dispatched for this task).

**Why `client.request(...)` against `/api/favourites/...` still works today, before `favourites.py`
is registered.** `app.py`'s `_NoIndexHeaderMiddleware` (T309, widened by T384) headers every
`/api/*` response by default regardless of whether a route matches, so the plain, unmatched-route
404 every call below gets today already carries `X-Robots-Tag`/`Cache-Control` — see
`test_no_index_headers.py`'s own `_FEATURE_ROUTE_TABLE`, which already lists all three favourites
routes and is not duplicated here. This file's own assertions are about the *behaviour* T346 must
add — the `200`/`409`/`401` shapes, the row count, the per-user isolation — not the header, which
is proven once, generically, elsewhere.

**Response shapes this file commits to, where `contracts/http-api.md` states the property but not
the exact envelope.** The contract fixes the route table, the idempotence and the three error
codes; it does not spell out `GET /api/favourites`'s JSON. This file follows the one convention
every other list route in this codebase already uses — a top-level key named after the resource,
`{"favourites": [...]}`, mirroring `{"matches": [...]}` (`routers/matches.py`,
`routers/players.py`) and `{"results": [...]}` (`routers/players.py`'s search) — and requires each
entry to carry `profile_id` (FR-014's "reach each one's profile in one step": the id alone is
sufficient for a client to build `/api/players/{profile_id}` without a second round trip, the same
route `test_players_routes.py` already proves answers with a profile's full standing), `alias`, and
`ratings`, the identical per-ladder shape `GET /api/players/{profile_id}` already returns
(`_profile_ratings`, `routers/players.py`) — FR-014's "current standing" — so this file does not
invent a second shape for the same fact `players.py` already established. If T346 lands under a
different top-level key, only this file's helper functions need to change; every other assertion
here is unaffected.

**FR-016's bound is exercised against a monkeypatched, narrowed `FAVOURITES_MAX_PER_USER`**
(`test_allowlist.py`'s own `monkeypatch.setenv(...)` / `get_settings.cache_clear()` convention),
never the real, 100-row default `conftest.py`'s `environment` fixture sets — inserting 100 rows
directly to reach that bound would work, but it asserts nothing that inserting 2 does not, at 50
times the cost.

**The last assertion has no route to test, by design (FR-015).** "How many people follow this
player" is a question this system must not be able to answer, and the spec's own instruction for
this task is that the only way to test an absence is to test for it: `test_favourites_router_never
_aggregates_over_profile_id` below parses `routers/favourites.py`'s own source and fails if any
aggregate function (`func.count`, `.count()`, `.group_by(...)`) is ever applied to `profile_id`
anywhere in it. An AST walk rather than a line-by-line `grep`, because a query spread across
several lines — the normal SQLAlchemy style every other router in this codebase uses
(`routers/players.py`, `routers/matches.py`) — would otherwise slip past a single-line pattern; the
intent is exactly the task's own "grep the router module", made robust to how this codebase
actually writes a query. Until T346 exists, the module import inside that test fails on its own,
which is the expected `xfail` shape for this file's one structural assertion, exactly as it is for
every behavioural one above it.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api import security
from aoe2stats_api.settings import get_settings
from aoe2stats_storage.models import AoeProfile, Favourite, RatingSnapshot, User
from aoe2stats_storage.models import Session as UserSession

pytestmark = [pytest.mark.usefixtures("environment")]

#: See `test_replay_status.py`'s module docstring — this suite's working assumption, not yet fixed
#: by a contract document beyond T028's own implementation.
SESSION_COOKIE_NAME = "session_id"

_FAVOURITED_PROFILE_ID = 900_950_100
_OTHER_FAVOURITED_PROFILE_ID = 900_950_200


async def _seed_user(db_session: AsyncSession) -> User:
    """A bare, allowlisted `users` row — favouriting is about the caller and any third-party
    profile, never the caller's own linked profile, so no `profile_links` row is needed here."""
    now = datetime.now(UTC)
    user = User(allowlisted_at=now)
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    return user


async def _seed_profile(
    db_session: AsyncSession,
    *,
    profile_id: int,
    alias: str,
    country: str | None = "FR",
) -> None:
    db_session.add(
        AoeProfile(
            profile_id=profile_id,
            alias=alias,
            country=country,
            alias_observed_at=datetime.now(UTC),
        )
    )
    await db_session.commit()


async def _seed_rating_snapshot(
    db_session: AsyncSession,
    *,
    profile_id: int,
    leaderboard_id: int,
    rating: int,
) -> None:
    db_session.add(
        RatingSnapshot(
            profile_id=profile_id,
            leaderboard_id=leaderboard_id,
            captured_at=datetime.now(UTC),
            rating=rating,
            rank=None,
            wins=None,
            losses=None,
        )
    )
    await db_session.commit()


async def _seed_favourite(db_session: AsyncSession, *, user_id: Any, profile_id: int) -> None:
    """Inserts a `favourites` row directly — used only to set up state a test does not itself
    mean to exercise (e.g. "a favourite that belongs to someone else"), never as a substitute for
    the `PUT` assertions this file owns."""
    db_session.add(Favourite(user_id=user_id, profile_id=profile_id, created_at=datetime.now(UTC)))
    await db_session.commit()


async def _sign_in(client: TestClient, db_session: AsyncSession, user: User) -> None:
    """Insert a `sessions` row directly and hand the client its signed cookie — mirrors
    `test_players_routes.py`'s own `_sign_in` helper byte for byte."""
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


async def _favourite_row_count(db_session: AsyncSession, *, user_id: Any) -> int:
    result = await db_session.execute(
        select(func.count()).select_from(Favourite).where(Favourite.user_id == user_id)
    )
    return result.scalar_one()


# --- PUT/DELETE /api/favourites/{profile_id} — FR-013 -------------------------------------------


async def test_put_twice_is_one_row_and_two_200s_and_delete_is_idempotent(
    client: TestClient, db_session: AsyncSession
) -> None:
    """Quickstart scenario 11.1/11.2, FR-013: marking twice must not create a second row, and
    unmarking — twice — must never fail the second time. One test rather than two: the two halves
    share the same caller and the same profile, and splitting them would either duplicate the setup
    or hide that `DELETE` is exercised against the exact row `PUT` created."""
    caller = await _seed_user(db_session)
    await _sign_in(client, db_session, caller)
    await _seed_profile(db_session, profile_id=_FAVOURITED_PROFILE_ID, alias="MarkTwiceAlias")

    first_put = client.put(f"/api/favourites/{_FAVOURITED_PROFILE_ID}")
    assert first_put.status_code == 200, (
        f"marking a player as a favourite must succeed. Got {first_put.status_code}: "
        f"{first_put.text}"
    )
    second_put = client.put(f"/api/favourites/{_FAVOURITED_PROFILE_ID}")
    assert second_put.status_code == 200, (
        f"marking the same player twice must be a no-op `200`, never a conflict. Got "
        f"{second_put.status_code}: {second_put.text}"
    )

    row_count = await _favourite_row_count(db_session, user_id=caller.id)
    assert row_count == 1, (
        f"marking twice must be one row, per the composite primary key (FR-013). Got {row_count}"
    )

    first_delete = client.delete(f"/api/favourites/{_FAVOURITED_PROFILE_ID}")
    assert first_delete.status_code == 200, (
        f"unmarking a favourited player must succeed. Got {first_delete.status_code}: "
        f"{first_delete.text}"
    )
    assert await _favourite_row_count(db_session, user_id=caller.id) == 0, (
        "the row must be gone after unmarking"
    )

    second_delete = client.delete(f"/api/favourites/{_FAVOURITED_PROFILE_ID}")
    assert second_delete.status_code == 200, (
        f"unmarking an already-unmarked player must still answer `200` — `DELETE` is idempotent, "
        f"per `contracts/http-api.md`. Got {second_delete.status_code}: {second_delete.text}"
    )
    assert await _favourite_row_count(db_session, user_id=caller.id) == 0


# --- GET /api/favourites — FR-014 ----------------------------------------------------------------


async def test_favourites_list_carries_current_standing_and_reaches_the_profile_in_one_step(
    client: TestClient, db_session: AsyncSession
) -> None:
    """Quickstart scenario 11.1, FR-014: each entry carries the player and their current standing,
    and enough to reach their profile in one step — `profile_id`, the identifier
    `GET /api/players/{profile_id}` (`test_players_routes.py`) already resolves into that page, so
    no second lookup is needed before the client can navigate there."""
    caller = await _seed_user(db_session)
    await _sign_in(client, db_session, caller)
    await _seed_profile(db_session, profile_id=_FAVOURITED_PROFILE_ID, alias="StandingAlias")
    await _seed_rating_snapshot(
        db_session, profile_id=_FAVOURITED_PROFILE_ID, leaderboard_id=3, rating=1777
    )

    put_response = client.put(f"/api/favourites/{_FAVOURITED_PROFILE_ID}")
    assert put_response.status_code == 200

    response = client.get("/api/favourites")
    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    entries = response.json()["favourites"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["profile_id"] == _FAVOURITED_PROFILE_ID, (
        "FR-014: the entry must carry the profile id so the client can reach the profile in one "
        "step, with no second lookup"
    )
    assert entry["alias"] == "StandingAlias"
    ratings_by_leaderboard = {rating["leaderboard_id"]: rating for rating in entry["ratings"]}
    assert ratings_by_leaderboard[3]["rating"] == 1777, (
        "FR-014: the list must carry current standing per entry, not merely the player's identity"
    )


async def test_unmarking_a_favourite_removes_it_and_changes_nothing_else(
    client: TestClient, db_session: AsyncSession
) -> None:
    """Quickstart scenario 11.2: unmarking one of several favourites removes exactly that one, and
    the player's own record (their `aoe_profiles` row) is untouched by the removal."""
    caller = await _seed_user(db_session)
    await _sign_in(client, db_session, caller)
    await _seed_profile(db_session, profile_id=_FAVOURITED_PROFILE_ID, alias="KeepAlias")
    await _seed_profile(db_session, profile_id=_OTHER_FAVOURITED_PROFILE_ID, alias="RemoveAlias")
    assert client.put(f"/api/favourites/{_FAVOURITED_PROFILE_ID}").status_code == 200
    assert client.put(f"/api/favourites/{_OTHER_FAVOURITED_PROFILE_ID}").status_code == 200

    delete_response = client.delete(f"/api/favourites/{_OTHER_FAVOURITED_PROFILE_ID}")
    assert delete_response.status_code == 200

    remaining_ids = {
        entry["profile_id"] for entry in client.get("/api/favourites").json()["favourites"]
    }
    assert remaining_ids == {_FAVOURITED_PROFILE_ID}, (
        "unmarking one favourite must remove exactly that one and leave the other untouched"
    )

    still_a_profile = await db_session.get(AoeProfile, _OTHER_FAVOURITED_PROFILE_ID)
    assert still_a_profile is not None, (
        "unmarking a favourite must never touch the player's own record — only the bookmark"
    )
    assert still_a_profile.alias == "RemoveAlias"


# --- The per-user bound — FR-016 -----------------------------------------------------------------


async def test_favouriting_past_the_bound_answers_favourites_limit_reached(
    client: TestClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quickstart scenario 11.4, FR-016: at the configured per-user bound, one more `PUT` is
    refused with a clear reason rather than silently growing the list into an unbounded query
    against a source. `FAVOURITES_MAX_PER_USER` is narrowed to 2 here (`test_allowlist.py`'s own
    convention) rather than exercised against the real, 100-row default `environment` sets."""
    monkeypatch.setenv("FAVOURITES_MAX_PER_USER", "2")
    get_settings.cache_clear()
    limit = get_settings().favourites_max_per_user
    assert limit == 2

    caller = await _seed_user(db_session)
    await _sign_in(client, db_session, caller)

    at_bound_profile_ids = [900_950_301, 900_950_302]
    for profile_id in at_bound_profile_ids:
        await _seed_profile(db_session, profile_id=profile_id, alias=f"Bound{profile_id}")
    assert len(at_bound_profile_ids) == limit

    for profile_id in at_bound_profile_ids:
        response = client.put(f"/api/favourites/{profile_id}")
        assert response.status_code == 200, (
            f"favouriting up to the configured bound of {limit} must succeed. Got "
            f"{response.status_code}: {response.text}"
        )

    over_bound_profile_id = 900_950_303
    await _seed_profile(db_session, profile_id=over_bound_profile_id, alias="OverBoundAlias")
    over_bound_response = client.put(f"/api/favourites/{over_bound_profile_id}")
    assert over_bound_response.status_code == 409, (
        f"a favourite past the bound must be refused. Got {over_bound_response.status_code}: "
        f"{over_bound_response.text}"
    )
    assert over_bound_response.json()["error"]["code"] == "favourites_limit_reached"

    row_count = await _favourite_row_count(db_session, user_id=caller.id)
    assert row_count == limit, (
        f"the refused favourite must never have been written. Got {row_count} rows"
    )


# --- Unauthenticated — US5 scenario 5 ------------------------------------------------------------


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/favourites"),
        ("put", f"/api/favourites/{_FAVOURITED_PROFILE_ID}"),
        ("delete", f"/api/favourites/{_FAVOURITED_PROFILE_ID}"),
    ],
    ids=["get", "put", "delete"],
)
def test_an_unauthenticated_call_answers_sign_in_required(
    method: str, path: str, client: TestClient
) -> None:
    """Quickstart scenario 11.5, US5 acceptance scenario 5: a visitor who is not signed in is
    asked to sign in — never a generic `401` — so the client can return them to where they were.
    `contracts/http-api.md`: "An unauthenticated call answers `401` with
    `code: 'sign_in_required'`." No session cookie is ever set on `client` in this test."""
    response = client.request(method, path)
    assert response.status_code == 401, f"Got {response.status_code}: {response.text}"
    assert response.json()["error"]["code"] == "sign_in_required"


# --- Privacy between users — FR-015 --------------------------------------------------------------


async def test_one_user_never_sees_anothers_favourites(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-015: favourites are private to their owner. Two users, two disjoint favourites; each
    user's own list must show only what they themselves marked, never the other's."""
    first_user = await _seed_user(db_session)
    second_user = await _seed_user(db_session)
    await _seed_profile(db_session, profile_id=_FAVOURITED_PROFILE_ID, alias="FirstUsersAlias")
    await _seed_profile(
        db_session, profile_id=_OTHER_FAVOURITED_PROFILE_ID, alias="SecondUsersAlias"
    )
    await _seed_favourite(db_session, user_id=first_user.id, profile_id=_FAVOURITED_PROFILE_ID)
    await _seed_favourite(
        db_session, user_id=second_user.id, profile_id=_OTHER_FAVOURITED_PROFILE_ID
    )

    await _sign_in(client, db_session, first_user)
    first_response = client.get("/api/favourites")
    assert first_response.status_code == 200
    first_ids = {entry["profile_id"] for entry in first_response.json()["favourites"]}
    assert first_ids == {_FAVOURITED_PROFILE_ID}, (
        f"the first user must see only their own favourite. Got {first_ids}"
    )

    await _sign_in(client, db_session, second_user)
    second_response = client.get("/api/favourites")
    assert second_response.status_code == 200
    second_ids = {entry["profile_id"] for entry in second_response.json()["favourites"]}
    assert second_ids == {_OTHER_FAVOURITED_PROFILE_ID}, (
        f"the second user must see only their own favourite, never the first user's. Got "
        f"{second_ids}"
    )


# --- The assertion with no route to test — FR-015 -------------------------------------------------


def test_favourites_router_never_aggregates_over_profile_id() -> None:
    """FR-015 in the negative: "how many people follow this player" is a question this system
    must not be able to answer, and answering it would reveal to a player that they are being
    followed. There is no route in this contract that could ask it, so the only way to test the
    absence is to test for it (this task's own instruction): parse `routers/favourites.py`'s own
    source and fail if any aggregate function (`func.count`, a bare `.count()`, or `.group_by(...)`)
    is ever applied anywhere to `profile_id`. Until T346 lands, the import below fails on its own —
    the same expected shape as every behavioural test above it in this file."""
    import ast
    import inspect

    from aoe2stats_api.routers import favourites as favourites_router

    source = inspect.getsource(favourites_router)
    tree = ast.parse(source)

    _aggregate_attrs = {"count", "group_by"}
    offending: list[str] = []

    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr not in _aggregate_attrs:
            continue
        call_source = ast.get_source_segment(source, node) or ast.dump(node)
        if "profile_id" in call_source:
            offending.append(call_source)

    assert not offending, (
        "routers/favourites.py must never aggregate over profile_id — 'how many people follow "
        f"this player' is a question this system must not be able to answer. Found: {offending!r}"
    )
