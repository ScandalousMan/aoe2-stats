"""T333 remediation — `GET /api/matches/{game_id}` (`routers/matches.py::get_match_detail`) leaves
two facts stale for a participant this service only ever met as a third party, found while walking
`specs/003-player-search-match-analysis/quickstart.md` scenario 5 by hand against production:

1. **The alias.** `get_match_detail` never triggers an on-view identity refresh at all, so a
   participant discovered only through someone else's history keeps the `str(profile_id)`
   placeholder `touch_aoe_profile` writes on first sight, forever — the real alias is available for
   free in Relic's `getRecentMatchHistory` `profiles[]` identity block
   (`RelicMatchHistoryProvider.recent_profiles`, T451), the same call `routers/players.py::
   _refresh_profile_identity` already makes for its own two routes.
2. **The colour.** `enrich_colours` (`matches.py`'s own `match_players.color_id` writer, T420) is
   wired into `list_matches` and `players.py::get_player_match_history` but was never called from
   `get_match_detail` at all, so a match viewed only through its detail route stayed uncoloured no
   matter how many times it was opened.

`matches.py`'s own module docstring — "Colour enrichment is now also on `get_match_detail`'s own
path" and "The on-view identity refresh" — is ground truth for the fix; this file drives it entirely
through the real route, the real `match_players`/`aoe_profiles` tables, and the same `httpx.
AsyncClient.send`-interception boundary `test_match_colour_enrichment.py` (`_CompanionUpstream`) and
`test_third_party_history.py` (`_FakeRelicMatchHistoryUpstream`) already use for their own provider.

**Harness conventions** mirror `test_match_detail.py`'s own seeding helpers
(`_seed_linked_caller`/`_seed_profile`/`_seed_match`/`_seed_match_player`/`_sign_in`) byte for byte
where they overlap, plus `test_match_colour_enrichment.py`'s companion double and `test_third_party_
history.py`'s Relic double for the two upstreams this fix newly reaches.

**Why the re-read matters, and why every reproduction test below asserts it on the *first* call.**
`enrich_colours`/`touch_aoe_profile` write straight to the database, never to the already-
materialised `MatchDetail` `get_match_detail` had already built before either ran — a fix that wrote
the row but skipped the re-read would still serialise the stale placeholder/`NULL` on the very
response a caller is looking at, and only a *second* view would show anything different. Every
reproduction assertion below is against the response body of the one and only request the test
makes, never a second request that would let a "fixes itself on reload" bug pass unnoticed.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
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

#: See `test_match_detail.py`'s own module docstring — this suite's working assumption for the
#: session cookie's name, not yet fixed by a contract document beyond T028's own implementation.
SESSION_COOKIE_NAME = "session_id"

#: `RelicMatchHistoryProvider`'s one host (`packages/providers/.../relic/matches.py`) —
#: `test_third_party_history.py`'s own `_RELIC_HOST`, duplicated here rather than imported (this
#: suite's own self-contained-file convention).
_RELIC_HOST = "aoe-api.worldsedgelink.com"

#: `CompanionEnrichmentProvider.enrich_matches`'s one host (`packages/providers/.../companion/
#: provider.py`) — `test_match_colour_enrichment.py`'s own `_COMPANION_HOST`, duplicated here.
_COMPANION_HOST = "data.aoe2companion.com"

_CALLER_PROFILE_ID = 951_500_100
_OPPONENT_PROFILE_ID = 951_500_200
_GAME_ID = 951_500_900


# --- Seeding helpers, mirroring `test_match_detail.py`'s own byte for byte where they overlap ----


async def _seed_profile(
    db_session: AsyncSession, *, profile_id: int, alias: str, country: str | None = "FR"
) -> None:
    db_session.add(AoeProfile(profile_id=profile_id, alias=alias, country=country))


async def _seed_linked_caller(
    db_session: AsyncSession, *, profile_id: int = _CALLER_PROFILE_ID
) -> User:
    now = datetime.now(UTC)
    user = User(allowlisted_at=now)
    db_session.add(user)
    await db_session.flush()
    await _seed_profile(db_session, profile_id=profile_id, alias="CallerAlias")
    db_session.add(
        SteamIdentity(
            steam_id64="76561197960287950", user_id=user.id, verified_at=now, last_sign_in_at=now
        )
    )
    await db_session.flush()
    db_session.add(
        ProfileLink(
            user_id=user.id,
            profile_id=profile_id,
            steam_id64="76561197960287950",
            is_primary=True,
            linked_at=now,
        )
    )
    await db_session.commit()
    return user


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


async def _seed_match(db_session: AsyncSession, *, game_id: int = _GAME_ID) -> None:
    now = datetime.now(UTC)
    db_session.add(
        Match(
            game_id=game_id,
            leaderboard_id=3,
            map_name="Arabia",
            started_at=now - timedelta(seconds=1800),
            completed_at=now,
            duration_seconds=1800,
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
    color_id: int | None,
    result: str = "win",
) -> None:
    db_session.add(
        MatchPlayer(
            game_id=game_id,
            profile_id=profile_id,
            team_id=team_id,
            civ_id=1,
            color_id=color_id,
            result=result,
            rating=1500,
            rating_diff=10,
        )
    )


def _participants_by_profile_id(body: dict[str, Any]) -> dict[int, dict[str, Any]]:
    participants = body["participants"]
    assert isinstance(participants, list)
    return {int(p["profile_id"]): p for p in participants}


# --- The Relic identity double, mirroring `test_third_party_history.py`'s own -------------------


class _RelicIdentityUpstream:
    """Stands in for `getRecentMatchHistory`'s identity block — one fixed body, and how many times
    it was actually reached (the budget-gate test's own claim)."""

    def __init__(self, body: dict[str, Any]) -> None:
        self._body = body
        self.request_count = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.request_count += 1
        return httpx.Response(200, json=self._body)


def _relic_identity_body(*entries: tuple[int, str, str | None]) -> dict[str, Any]:
    return {
        "matchHistoryStats": [],
        "profiles": [
            {"profile_id": profile_id, "alias": alias, "country": country}
            for profile_id, alias, country in entries
        ],
    }


class _RefusingRelicUpstream:
    """Any request reaching this fails the test outright — the budget-gate test's own hard
    failure, mirroring `test_third_party_history.py`'s `_RefusingCompanionUpstream`: a request
    count of zero left unchecked is not, on its own, distinguishable from "the test forgot to
    check"."""

    def __call__(self, request: httpx.Request) -> httpx.Response:
        raise AssertionError(
            f"recent_profiles must never be reached when every participant already has a real "
            f"alias — got a request to {request.url}"
        )


# --- The companion colour double, mirroring `test_match_colour_enrichment.py`'s own -------------


def _companion_matches_body(entries: dict[int, dict[int, int]]) -> dict[str, Any]:
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


class _CompanionMatchesUpstream:
    def __init__(self, body: dict[str, Any]) -> None:
        self._body = body
        self.request_count = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.request_count += 1
        return httpx.Response(200, json=self._body)


def _intercept(
    monkeypatch: pytest.MonkeyPatch,
    *,
    relic: Callable[[httpx.Request], httpx.Response] | None = None,
    companion: Callable[[httpx.Request], httpx.Response] | None = None,
    relic_status: int | None = None,
    companion_status: int | None = None,
) -> None:
    """Routes `httpx.AsyncClient.send` to `relic`/`companion` by host, or to a fixed status code
    for whichever side has no double at all — any other host raises. `relic_status`/
    `companion_status` are for the degrade tests, which need a *failing* response rather than a
    fake that hands back a body."""

    async def fake_send(
        self: httpx.AsyncClient, request: httpx.Request, **kwargs: object
    ) -> httpx.Response:
        if request.url.host == _RELIC_HOST:
            if relic is not None:
                return relic(request)
            if relic_status is not None:
                return httpx.Response(relic_status, request=request)
            raise AssertionError(f"unexpected outbound request to {request.url}")
        if request.url.host == _COMPANION_HOST:
            if companion is not None:
                return companion(request)
            if companion_status is not None:
                return httpx.Response(companion_status, request=request)
            raise AssertionError(f"unexpected outbound request to {request.url}")
        raise AssertionError(f"unexpected outbound request to {request.url}")

    monkeypatch.setattr(httpx.AsyncClient, "send", fake_send)


# --- Reproduction: alias ---------------------------------------------------------------------


async def test_match_detail_replaces_the_placeholder_alias_on_the_first_response(
    client: TestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The defect itself: an opponent this service met only as a third party keeps its numeric-id
    placeholder as `alias` on the match-detail page forever, since `get_match_detail` never
    triggered an identity refresh. Both participants already carry a real colour so `enrich_colours`
    is a no-op here — this test's own claim is the alias alone."""
    caller = await _seed_linked_caller(db_session)
    await _sign_in(client, db_session, caller)

    # The placeholder alias `touch_aoe_profile` writes "on insert" when it has never itself
    # observed a real one — exactly what a participant met only through discovery keeps forever
    # without this fix.
    await _seed_profile(
        db_session, profile_id=_OPPONENT_PROFILE_ID, alias=str(_OPPONENT_PROFILE_ID), country=None
    )
    await _seed_match(db_session)
    await _seed_match_player(db_session, profile_id=_CALLER_PROFILE_ID, team_id=1, color_id=1)
    await _seed_match_player(
        db_session, profile_id=_OPPONENT_PROFILE_ID, team_id=2, color_id=2, result="loss"
    )
    await db_session.commit()

    relic_fake = _RelicIdentityUpstream(
        _relic_identity_body((_OPPONENT_PROFILE_ID, "RealOpponentAlias", "DE"))
    )
    _intercept(monkeypatch, relic=relic_fake, companion_status=403)

    response = client.get(f"/api/matches/{_GAME_ID}")

    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"
    by_profile = _participants_by_profile_id(response.json())
    assert by_profile[_OPPONENT_PROFILE_ID]["alias"] == "RealOpponentAlias", (
        "the on-view identity refresh must replace the numeric-id placeholder with the real alias "
        f"Relic just carried, on this very (first, uncached) response. Got "
        f"{by_profile[_OPPONENT_PROFILE_ID]['alias']!r}"
    )
    assert by_profile[_OPPONENT_PROFILE_ID]["country"] == "DE"

    stored = await db_session.get(AoeProfile, _OPPONENT_PROFILE_ID)
    assert stored is not None
    assert stored.alias == "RealOpponentAlias", (
        "the refresh must also persist the real alias, not merely render it once"
    )


# --- Reproduction: colour ----------------------------------------------------------------------


async def test_match_detail_writes_and_serves_the_missing_colour_on_the_first_response(
    client: TestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The defect's second half: `match_players.color_id` stays `NULL` forever for a match viewed
    only through its detail route, since `get_match_detail` never called `enrich_colours` at all.
    Both participants already carry real aliases so no Relic call happens here — this test's own
    claim is the colour alone."""
    caller = await _seed_linked_caller(db_session)
    await _sign_in(client, db_session, caller)

    await _seed_profile(db_session, profile_id=_OPPONENT_PROFILE_ID, alias="OpponentAlias")
    await _seed_match(db_session)
    await _seed_match_player(db_session, profile_id=_CALLER_PROFILE_ID, team_id=1, color_id=None)
    await _seed_match_player(
        db_session, profile_id=_OPPONENT_PROFILE_ID, team_id=2, color_id=None, result="loss"
    )
    await db_session.commit()

    companion_fake = _CompanionMatchesUpstream(
        _companion_matches_body({_GAME_ID: {_CALLER_PROFILE_ID: 3, _OPPONENT_PROFILE_ID: 6}})
    )
    _intercept(monkeypatch, companion=companion_fake, relic_status=503)

    response = client.get(f"/api/matches/{_GAME_ID}")

    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"
    by_profile = _participants_by_profile_id(response.json())
    assert by_profile[_CALLER_PROFILE_ID]["color_id"] == 3, (
        "the missing colour must be enriched and served on this very (first, uncached) response. "
        f"Got {by_profile[_CALLER_PROFILE_ID]['color_id']!r}"
    )
    assert by_profile[_OPPONENT_PROFILE_ID]["color_id"] == 6

    row = await db_session.get(MatchPlayer, (_GAME_ID, _CALLER_PROFILE_ID))
    assert row is not None
    assert row.color_id == 3, "the refresh must also persist the colour, not merely render it once"


# --- Contrast / gate: alias, the budget boundary --------------------------------------------


async def test_match_detail_makes_zero_recent_profiles_calls_when_every_alias_is_already_real(
    client: TestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The budget boundary (constitution I): a match whose every participant already carries a
    real alias must reach Relic's `recent_profiles` **zero** times, not merely "at most" some
    number — `_RefusingRelicUpstream` turns any call into a hard failure, and `request_count == 0`
    below is the same claim made twice, once as a spy and once as a refusal."""
    caller = await _seed_linked_caller(db_session)
    await _sign_in(client, db_session, caller)

    await _seed_profile(db_session, profile_id=_OPPONENT_PROFILE_ID, alias="AlreadyRealAlias")
    await _seed_match(db_session)
    await _seed_match_player(db_session, profile_id=_CALLER_PROFILE_ID, team_id=1, color_id=1)
    await _seed_match_player(
        db_session, profile_id=_OPPONENT_PROFILE_ID, team_id=2, color_id=2, result="loss"
    )
    await db_session.commit()

    _intercept(monkeypatch, relic=_RefusingRelicUpstream(), companion_status=403)

    response = client.get(f"/api/matches/{_GAME_ID}")

    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"
    by_profile = _participants_by_profile_id(response.json())
    assert by_profile[_CALLER_PROFILE_ID]["alias"] == "CallerAlias"
    assert by_profile[_OPPONENT_PROFILE_ID]["alias"] == "AlreadyRealAlias"


# --- Degrade: both, never a 5xx and never a wiped real alias ---------------------------------


async def test_match_detail_degrades_to_the_placeholder_and_null_colour_never_a_5xx(
    client: TestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-017's degrade discipline, both halves at once: Relic fails outright (never a `200`) and
    companion is degraded (`403`, the ordinary "documented, expected bot-protection noise"). The
    route must still answer `200`, with the pre-existing placeholder alias and `NULL` colour left
    exactly as they were — never a 5xx, and never a real value silently wiped by a failed refresh
    that had nothing new to offer."""
    caller = await _seed_linked_caller(db_session)
    await _sign_in(client, db_session, caller)

    await _seed_profile(
        db_session, profile_id=_OPPONENT_PROFILE_ID, alias=str(_OPPONENT_PROFILE_ID), country=None
    )
    await _seed_match(db_session)
    await _seed_match_player(db_session, profile_id=_CALLER_PROFILE_ID, team_id=1, color_id=None)
    await _seed_match_player(
        db_session, profile_id=_OPPONENT_PROFILE_ID, team_id=2, color_id=None, result="loss"
    )
    await db_session.commit()

    _intercept(monkeypatch, relic_status=503, companion_status=403)

    response = client.get(f"/api/matches/{_GAME_ID}")

    assert response.status_code == 200, (
        f"a degraded Relic and a degraded companion must never fail the view (FR-017). Got "
        f"{response.status_code}: {response.text}"
    )
    by_profile = _participants_by_profile_id(response.json())
    assert by_profile[_OPPONENT_PROFILE_ID]["alias"] == str(_OPPONENT_PROFILE_ID), (
        "a failed identity refresh must leave the pre-existing placeholder exactly as it was, "
        f"never a partial or fabricated value. Got {by_profile[_OPPONENT_PROFILE_ID]['alias']!r}"
    )
    assert by_profile[_CALLER_PROFILE_ID]["color_id"] is None
    assert by_profile[_OPPONENT_PROFILE_ID]["color_id"] is None

    stored_profile = await db_session.get(AoeProfile, _OPPONENT_PROFILE_ID)
    assert stored_profile is not None
    assert stored_profile.alias == str(_OPPONENT_PROFILE_ID), (
        "the stored row itself must stay untouched too, not only the response"
    )
    stored_row = await db_session.get(MatchPlayer, (_GAME_ID, _CALLER_PROFILE_ID))
    assert stored_row is not None
    assert stored_row.color_id is None
