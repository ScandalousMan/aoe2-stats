"""T419 — the colour-enrichment tests for T420 (`apps/api/src/aoe2stats_api/routers/matches.py`).
`quickstart.md` scenario 3, `data-model.md` §1 ("`color_id` alone, on the display path") and §6
(the one state transition), `research.md` **D2** are ground truth.

**Implemented by T420.** `routers/matches.py`'s `_enrich_colours` calls
`CompanionEnrichmentProvider.enrich_matches` from both `GET /api/matches` and
`GET /api/matches/{game_id}`, on the display path only. This suite drives it entirely through the
real routes and the real `match_players` table, the same boundary `test_players_routes.py`'s own
`_FailingCompanionUpstream` and `test_third_party_history.py`'s `_FakeRelicMatchHistoryUpstream`
already use for their own provider.

**Why "at most one companion call" alone would prove nothing.** Read literally, a ceiling of one
call per page is trivially satisfied by zero calls too. Every test below therefore also asserts a
*positive*: that the call actually happened (`fake.request_count == 1`, not `<= 1`) wherever the
design commits to one, never a bound that would already pass by never reaching the transport at
all.

**The assertion this file exists for** is
`test_a_degraded_companion_writes_nothing_and_never_nulls_a_cached_colour` below: seed a colour,
degrade the provider, read the row back, and confirm the seeded value survived untouched. It has no
happy path — a correct implementation and a buggy one that quietly writes `NULL` both leave the
*response* looking fine, so only the row itself proves the difference (`data-model.md` §1: "A
degraded companion writes nothing; it does not write `NULL`").

**Harness conventions** mirror `test_matches_list.py` (`_seed_linked_profile`, `_seed_match`,
`_sign_in`) and `test_players_routes.py` (`_FailingCompanionUpstream`, the `httpx.AsyncClient.send`
interception boundary) byte for byte where they overlap — `client`/`db_session`/`environment` from
`conftest.py`.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
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
    SteamIdentity,
    User,
)
from aoe2stats_storage.models import Session as UserSession

pytestmark = [pytest.mark.usefixtures("environment")]

#: See `test_replay_status.py`'s module docstring — this suite's working assumption for the
#: session cookie's name, not yet fixed by a contract document beyond T028's own implementation.
SESSION_COOKIE_NAME = "session_id"

#: `companion/provider.py`'s `COMPANION_BASE_URL` host — the one upstream this file ever expects a
#: request against. Any other host reaching `httpx.AsyncClient.send` below is a bug this test must
#: catch, not silently pass through.
_COMPANION_HOST = "data.aoe2companion.com"

_CALLER_PROFILE_ID = 941_400_100
_OPPONENT_PROFILE_ID = 941_400_200
_GAME_ID_ONE = 941_400_301
_GAME_ID_TWO = 941_400_302


# --- Seeding helpers, mirroring `test_matches_list.py`'s own byte for byte where they overlap ----


async def _seed_linked_profile(
    db_session: AsyncSession,
    *,
    profile_id: int = _CALLER_PROFILE_ID,
    steam_id64: str = "76561197960287931",
) -> User:
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


async def _seed_opponent_profile(
    db_session: AsyncSession, *, profile_id: int = _OPPONENT_PROFILE_ID
) -> None:
    db_session.add(AoeProfile(profile_id=profile_id, alias="Opponent", country="DE"))


async def _sign_in(client: TestClient, db_session: AsyncSession, user: User) -> None:
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


async def _seed_match(db_session: AsyncSession, *, game_id: int, completed_at: datetime) -> None:
    db_session.add(
        Match(
            game_id=game_id,
            leaderboard_id=3,
            map_name="Arabia",
            started_at=completed_at - timedelta(seconds=1800),
            completed_at=completed_at,
            duration_seconds=1800,
            source="relic",
            raw_payload={"game_id": game_id},
        )
    )


async def _seed_match_player(
    db_session: AsyncSession, *, game_id: int, profile_id: int, color_id: int | None = None
) -> None:
    db_session.add(
        MatchPlayer(
            game_id=game_id,
            profile_id=profile_id,
            team_id=1 if profile_id == _CALLER_PROFILE_ID else 2,
            civ_id=1,
            color_id=color_id,
            result="win" if profile_id == _CALLER_PROFILE_ID else "loss",
            rating=1500,
            rating_diff=18,
        )
    )


# --- The companion double, mirroring `test_players_routes.py`'s `_FailingCompanionUpstream` -----


def _companion_matches_body(entries: dict[int, dict[int, int]]) -> dict[str, Any]:
    """`entries`: `{game_id: {profile_id: color_id}}` -> the `/api/matches` response body
    `_parse_matches` (`companion/provider.py`) reads: `matches[].matchId` plus one `teams[].
    players[].profileId`/`color` pair per participant."""
    return {
        "matches": [
            {
                "matchId": game_id,
                "teams": [
                    {"players": [{"profileId": profile_id, "color": color_id}]}
                    for profile_id, color_id in colours.items()
                ],
            }
            for game_id, colours in entries.items()
        ]
    }


class _CompanionUpstream:
    """Stands in for `data.aoe2companion.com`'s `/api/matches` endpoint, reached at
    `httpx.AsyncClient.send` — the same boundary `test_players_routes.py`'s
    `_FailingCompanionUpstream` and `test_third_party_history.py`'s
    `_FakeRelicMatchHistoryUpstream` already use for their own provider. `degraded=True` answers
    every call `403` — companion's own "documented, expected bot-protection noise"
    (`companion/provider.py`'s module docstring) — and never `500`, so the retry loop never
    engages: one degraded call costs exactly one outbound request, keeping `request_count` a clean
    signal.
    """

    def __init__(self, body: dict[str, Any] | None = None, *, degraded: bool = False) -> None:
        self._body = body if body is not None else {"matches": []}
        self._degraded = degraded
        self.request_count = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.request_count += 1
        if self._degraded:
            return httpx.Response(403, request=request)
        return httpx.Response(200, json=self._body)


def _intercept_companion(monkeypatch: pytest.MonkeyPatch, fake: _CompanionUpstream) -> None:
    async def fake_send(
        self: httpx.AsyncClient, request: httpx.Request, **kwargs: object
    ) -> httpx.Response:
        if request.url.host != _COMPANION_HOST:
            raise AssertionError(f"unexpected outbound request to {request.url}")
        return fake(request)

    monkeypatch.setattr(httpx.AsyncClient, "send", fake_send)


# --- T419 itself -----------------------------------------------------------------------------


async def test_viewing_a_page_of_matches_makes_one_batched_companion_call_and_writes_colour(
    client: TestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scenario 3: a page carrying two matches must enrich colour in exactly one companion call,
    batched over the page's game ids, never one per match — and the colour that call returns must
    land in `match_players.color_id`, keyed `(game_id, profile_id)` (`data-model.md` §1). Ending
    with the property T419's task text closes on: `GET /api/players/{profile_id}` must still make
    no provider call whatsoever, so the companion call count must not move a second time when this
    same caller's own profile is opened right after — the property T426 must not quietly cost.
    """
    caller = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, caller)
    await _seed_opponent_profile(db_session)

    completed_at = datetime(2026, 8, 20, 12, 0, 0, tzinfo=UTC)
    await _seed_match(db_session, game_id=_GAME_ID_ONE, completed_at=completed_at)
    await _seed_match(
        db_session, game_id=_GAME_ID_TWO, completed_at=completed_at - timedelta(hours=1)
    )
    await _seed_match_player(db_session, game_id=_GAME_ID_ONE, profile_id=_CALLER_PROFILE_ID)
    await _seed_match_player(db_session, game_id=_GAME_ID_ONE, profile_id=_OPPONENT_PROFILE_ID)
    await _seed_match_player(db_session, game_id=_GAME_ID_TWO, profile_id=_CALLER_PROFILE_ID)
    await _seed_match_player(db_session, game_id=_GAME_ID_TWO, profile_id=_OPPONENT_PROFILE_ID)
    await db_session.commit()

    expected = {
        _GAME_ID_ONE: {_CALLER_PROFILE_ID: 3, _OPPONENT_PROFILE_ID: 6},
        _GAME_ID_TWO: {_CALLER_PROFILE_ID: 5, _OPPONENT_PROFILE_ID: 1},
    }
    fake = _CompanionUpstream(_companion_matches_body(expected))
    _intercept_companion(monkeypatch, fake)

    response = client.get("/api/matches", params={"profile_id": _CALLER_PROFILE_ID})
    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    assert fake.request_count == 1, (
        "a page carrying two matches must enrich colour in exactly one companion call, batched "
        f"over the page's game ids — never zero (colour would never arrive) and never one per "
        f"match (two, here). Got {fake.request_count} calls"
    )

    for game_id, colours in expected.items():
        for profile_id, expected_colour in colours.items():
            row = await db_session.get(MatchPlayer, (game_id, profile_id))
            assert row is not None
            assert row.color_id == expected_colour, (
                f"({game_id}, {profile_id})'s colour must be written from the batched companion "
                f"response. Got {row.color_id!r}, expected {expected_colour!r}"
            )

    # T419's closing property: viewing a page of matches must never make the profile route reach
    # a provider either — the companion call count must stay exactly where the matches page left
    # it.
    profile_response = client.get(f"/api/players/{_CALLER_PROFILE_ID}")
    assert profile_response.status_code == 200, (
        f"Got {profile_response.status_code}: {profile_response.text}"
    )
    assert fake.request_count == 1, (
        "GET /api/players/{profile_id} must make no provider call whatsoever — the companion "
        f"call count must stay at 1 (the matches page's own batched call). Got {fake.request_count}"
    )


async def test_a_degraded_companion_writes_nothing_and_never_nulls_a_cached_colour(
    client: TestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The assertion this file exists for (module docstring). One match, two participants: the
    caller's colour is already cached (`color_id=4`, as an earlier, successful view would have left
    it) and the opponent's is still missing — so the page is not yet fully coloured, and the read
    path must still attempt the batched companion call rather than skip it outright. That call is
    answered `403` (degraded). Reading `match_players` back afterwards must show the caller's
    seeded colour **untouched** — not overwritten with `NULL`, which a projection that
    unconditionally `SET`s `color_id` from a (now-empty) enrichment result would do — and the
    opponent's still missing, exactly as before: a degraded companion writes nothing, on either row.
    """
    caller = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, caller)
    await _seed_opponent_profile(db_session)

    completed_at = datetime(2026, 8, 20, 12, 0, 0, tzinfo=UTC)
    await _seed_match(db_session, game_id=_GAME_ID_ONE, completed_at=completed_at)
    await _seed_match_player(
        db_session, game_id=_GAME_ID_ONE, profile_id=_CALLER_PROFILE_ID, color_id=4
    )
    await _seed_match_player(
        db_session, game_id=_GAME_ID_ONE, profile_id=_OPPONENT_PROFILE_ID, color_id=None
    )
    await db_session.commit()

    fake = _CompanionUpstream(degraded=True)
    _intercept_companion(monkeypatch, fake)

    response = client.get("/api/matches", params={"profile_id": _CALLER_PROFILE_ID})
    assert response.status_code == 200, (
        f"a degraded companion must not itself fail the request. Got {response.status_code}: "
        f"{response.text}"
    )

    assert fake.request_count == 1, (
        "the page is not yet fully coloured (the opponent's colour is still missing), so the read "
        f"path must still have attempted the batched companion call. Got {fake.request_count}"
    )

    caller_row = await db_session.get(MatchPlayer, (_GAME_ID_ONE, _CALLER_PROFILE_ID))
    assert caller_row is not None
    assert caller_row.color_id == 4, (
        "a degraded companion writes nothing — it does not write `NULL` over a colour cached by an "
        f"earlier, successful view. Got {caller_row.color_id!r}, expected the seeded 4 untouched"
    )

    opponent_row = await db_session.get(MatchPlayer, (_GAME_ID_ONE, _OPPONENT_PROFILE_ID))
    assert opponent_row is not None
    assert opponent_row.color_id is None, (
        "a degraded companion supplies nothing for a participant whose colour was already "
        f"missing either — it must stay missing, not be set to any value. Got "
        f"{opponent_row.color_id!r}"
    )


async def test_a_second_view_of_the_same_matches_makes_no_companion_call(
    client: TestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Once a page's matches are fully coloured by one successful view, a second view of the exact
    same matches is a database read: `research.md` **D2**, "cached back into `match_players.
    color_id` so a second view of the same match is a database read." The first `GET /api/matches`
    above must cost one companion call (asserted the same way as the batching test above); a second,
    identical `GET /api/matches` right after must cost **zero** further calls.
    """
    caller = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, caller)
    await _seed_opponent_profile(db_session)

    completed_at = datetime(2026, 8, 20, 12, 0, 0, tzinfo=UTC)
    await _seed_match(db_session, game_id=_GAME_ID_ONE, completed_at=completed_at)
    await _seed_match_player(db_session, game_id=_GAME_ID_ONE, profile_id=_CALLER_PROFILE_ID)
    await _seed_match_player(db_session, game_id=_GAME_ID_ONE, profile_id=_OPPONENT_PROFILE_ID)
    await db_session.commit()

    expected = {_GAME_ID_ONE: {_CALLER_PROFILE_ID: 2, _OPPONENT_PROFILE_ID: 7}}
    fake = _CompanionUpstream(_companion_matches_body(expected))
    _intercept_companion(monkeypatch, fake)

    first = client.get("/api/matches", params={"profile_id": _CALLER_PROFILE_ID})
    assert first.status_code == 200, f"Got {first.status_code}: {first.text}"
    assert fake.request_count == 1, (
        f"the first view of an uncoloured page must make exactly one companion call. Got "
        f"{fake.request_count}"
    )

    second = client.get("/api/matches", params={"profile_id": _CALLER_PROFILE_ID})
    assert second.status_code == 200, f"Got {second.status_code}: {second.text}"
    assert fake.request_count == 1, (
        "a second view of the same, now fully-coloured matches must be a database read — no "
        f"further companion call. Got {fake.request_count} total calls after the second view"
    )
