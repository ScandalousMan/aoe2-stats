"""T326 — verbatim persistence for `GET /api/players/{profile_id}/matches`, implemented by T328.
`spec.md` FR-011: "System MUST preserve verbatim any source response it obtains that
`docs/data-sources.md` classifies as irrecoverable — third-party match history above all — exactly
as it does for a user's own (constitution III, 001 FR-012)." Constitution III: "Verbatim persistence
of the raw response is owed to every source of irrecoverable data... A source that can be re-queried
at any time is exempt." Relic's `getRecentMatchHistory` is exactly that irrecoverable source
(`docs/data-sources.md` §1: "a match leaves the 'recent' window and cannot be fetched back"), and it
is the same endpoint and the same `MatchHistoryProvider.recent_matches` (`packages/providers/src/
aoe2stats_providers/relic/matches.py`) that 001's own ingester already reads for a *consenting*
user's own history. `contracts/http-api.md`'s "Players" table names `GET /api/players/{profile_id}/
matches` as reading "the same row shape `GET /api/matches` already returns" — nothing in this
feature invents a second source or a second persistence path for the same fact.

**This test's one claim: the entry that reaches this router's caller lands in `matches.raw_payload`
unmodified.** Not byte-for-byte — `raw_payload` is `JSONB`, which the module docstring above (and
this file's own comparator) accounts for by walking the *parsed* structure rather than the wire
bytes — but structurally identical at every level: no key dropped, no key renamed, no list element
reordered away, and no value's type silently coerced (an int becoming a string, for instance).
001's own equivalent, cited by this task's text, is `apps/ingester/tests/test_shared_match.py`'s
`assert match_row.raw_payload == raw_match.raw_payload` — a bare `==`, which *does* already walk a
nested dict/list structure recursively in Python. This file goes one step further and makes that
walk explicit (`_assert_structurally_equal` below), for two reasons specific to this task: the
fixture below is a **multi-match** response (`matchHistoryStats` carries two entries, mirroring the
real `getRecentMatchHistory` shape `docs/data-sources.md` §1 measures) while `matches.raw_payload`
holds **one** match — so the comparison must be against the fixture's own matched entry, never the
whole response body, and a route that accidentally persisted the wrong entry (or the whole body)
must fail loudly rather than pass on a partial, coincidental match — and a bare `==` would not, on
its own, distinguish "value coerced to a different but `==`-equal-looking type" from "value
unchanged" in every case (`1 == 1.0` is `True` in Python; a stricter walk is what this task's text
("coerced") asks for and a plain `==` alone would not visibly prove).

**Harness conventions** mirror `test_players_routes.py` (T317) — `client`/`db_session`/
`environment` from `conftest.py`, the `_sign_in` cookie helper, and the same
`httpx.AsyncClient.send`-interception boundary `test_two_requests_through_the_real_provider_share_
the_circuit_breaker_state` and `test_auth_flow.py`'s `fake_upstream` already use for a router that
builds its provider privately (`_build_search_provider`/`_build_relic_provider`) rather than through
a FastAPI `Depends()` this file could override. `RelicMatchHistoryProvider` is the only
`MatchHistoryProvider` implementation in this codebase (`packages/providers/src/
aoe2stats_providers/relic/matches.py`) and the only one `docs/data-sources.md` §1 documents for
match history at all, so intercepting its one upstream host (`aoe-api.worldsedgelink.com`) is the
one seam through which a real, unmodified `GET /api/players/{profile_id}/matches` call can be driven
end to end without reaching into `routers/players.py`'s own private `_build_match_history_provider`
by name.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api import security
from aoe2stats_api.settings import get_settings
from aoe2stats_storage.models import AoeProfile, Match, User
from aoe2stats_storage.models import Session as UserSession

pytestmark = [pytest.mark.usefixtures("environment")]

#: See `test_players_routes.py`'s own module — this suite's working assumption for the session
#: cookie's name, not yet fixed by a contract document beyond T028's own implementation.
SESSION_COOKIE_NAME = "session_id"

# Relic's one documented match-history endpoint (`docs/data-sources.md` §1), and the only host
# `RelicMatchHistoryProvider` ever calls (`packages/providers/src/aoe2stats_providers/relic/
# matches.py`) — the same host `test_auth_flow.py`'s `fake_upstream` and `test_players_routes.py`'s
# breaker test already intercept for Relic and for companion respectively.
_RELIC_HOST = "aoe-api.worldsedgelink.com"
_RECENT_MATCH_HISTORY_PATH = "getRecentMatchHistory"

# T450: `GET /api/players/{profile_id}/matches` now also calls `enrich_colours`
# (`routers/matches.py`) for the page it just persisted, batched over its own `game_ids` — the
# freshly-upserted `match_players` rows below carry no `color_id` yet, so that call is genuinely
# attempted, not skipped. This file's own `fake_send` therefore has to answer this host too, the
# same "documented, expected bot-protection noise" `companion/provider.py`'s module docstring and
# `apps/api/tests/conftest.py`'s own `_default_companion_degraded` autouse fixture already treat as
# ordinary degradation — this test's own `monkeypatch.setattr` on `httpx.AsyncClient.send` replaces
# that fixture's default outright rather than composing with it, so the substitute has to repeat it.
_COMPANION_HOST = "data.aoe2companion.com"

_THIRD_PARTY_PROFILE_ID = 901_300_100
_OPPONENT_PROFILE_ID = 901_300_200
_TARGET_GAME_ID = 850_300_111
_OTHER_GAME_ID = 850_300_222

_MATCH_STARTED_AT = datetime(2026, 8, 20, 11, 30, 0, tzinfo=UTC)
_MATCH_COMPLETED_AT = datetime(2026, 8, 20, 12, 5, 0, tzinfo=UTC)


# --- The structural comparator this file's own claim rests on ------------------------------------


def _assert_structurally_equal(actual: object, expected: object, *, path: str = "$") -> None:
    """Recursively asserts `actual` is structurally identical to `expected`: same dict keys (order
    aside — a `dict` carries no meaningful order once round-tripped through `JSONB`), same list
    length *and order*, and same value **and same type** at every leaf. `path` names exactly where
    a mismatch was found, so a failure reads as "a field was dropped/renamed/reordered/coerced at
    this location" rather than as an opaque top-level diff.

    Deliberately not byte or text equality (module docstring: `matches.raw_payload` is `JSONB`,
    which normalises key order, whitespace and numeric form on write) — this walks the *parsed*
    Python structure a caller of this column actually reads, which is the claim FR-011 makes.
    """
    if isinstance(expected, dict):
        assert isinstance(actual, dict), f"{path}: expected a dict, got {type(actual).__name__}"
        missing = set(expected) - set(actual)
        extra = set(actual) - set(expected)
        assert not missing and not extra, (
            f"{path}: key set differs — dropped {sorted(missing)!r}, "
            f"renamed/added {sorted(extra)!r}"
        )
        for key, expected_value in expected.items():
            _assert_structurally_equal(actual[key], expected_value, path=f"{path}.{key}")
    elif isinstance(expected, list):
        assert isinstance(actual, list), f"{path}: expected a list, got {type(actual).__name__}"
        assert len(actual) == len(expected), (
            f"{path}: length differs — expected {len(expected)}, got {len(actual)}"
        )
        for index, (actual_item, expected_item) in enumerate(zip(actual, expected, strict=True)):
            _assert_structurally_equal(actual_item, expected_item, path=f"{path}[{index}]")
    else:
        # `type(actual) is type(expected)` first, deliberately, and not folded into the `==` line
        # below: `1 == 1.0` and `True == 1` are both `True` in Python, which would let an int
        # silently become a bool or a float pass a bare `==` walk. Checked before value equality
        # so a coercion is reported as a type mismatch, not misread as a value mismatch.
        assert type(actual) is type(expected), (
            f"{path}: type coerced — expected {type(expected).__name__} ({expected!r}), "
            f"got {type(actual).__name__} ({actual!r})"
        )
        assert actual == expected, f"{path}: value differs — expected {expected!r}, got {actual!r}"


def test_assert_structurally_equal_detects_dropped_renamed_reordered_and_coerced_fields() -> None:
    """A guard on the comparator itself, not on T328. While this file's own `xfail(strict=True)`
    marker was still in place — before T328 implemented the route — the one call to
    `_assert_structurally_equal` in `test_reading_a_third_partys_history_...` below never actually
    ran against a real persisted row yet: a comparator that silently degenerated into a no-op
    would have left that test passing as an `xfail` for a reason unrelated to the comparison it
    exists to prove, invisible because the suite stayed green (`CLAUDE.md`'s remediation section
    names exactly this shape of residue for a fix-and-test pair; the same risk applies to a
    test-first comparator no implementation has exercised yet). This test needs no database and no
    client and is never itself `xfail`: it proves, unconditionally, that the comparator catches
    each of the four failure modes the task text names — a dropped field, a renamed field, a
    reordered list element and a coerced type — and that it accepts an unmodified structure.
    """
    reference: dict[str, Any] = {
        "id": 1,
        "name": "Arabia",
        "members": [{"profile_id": 10}, {"profile_id": 20}],
    }

    # Positive control: an unmodified deep copy passes. Without this, a comparator that always
    # raised would make every one of the `pytest.raises` checks below pass for the wrong reason.
    _assert_structurally_equal(
        {"id": 1, "name": "Arabia", "members": [{"profile_id": 10}, {"profile_id": 20}]},
        reference,
    )

    dropped = {"id": 1, "members": [{"profile_id": 10}, {"profile_id": 20}]}
    with pytest.raises(AssertionError, match="dropped"):
        _assert_structurally_equal(dropped, reference)

    renamed = {"id": 1, "label": "Arabia", "members": [{"profile_id": 10}, {"profile_id": 20}]}
    with pytest.raises(AssertionError, match="renamed"):
        _assert_structurally_equal(renamed, reference)

    reordered = {
        "id": 1,
        "name": "Arabia",
        "members": [{"profile_id": 20}, {"profile_id": 10}],
    }
    with pytest.raises(AssertionError):
        _assert_structurally_equal(reordered, reference)

    coerced = {
        "id": "1",
        "name": "Arabia",
        "members": [{"profile_id": 10}, {"profile_id": 20}],
    }
    with pytest.raises(AssertionError, match="coerced"):
        _assert_structurally_equal(coerced, reference)


# --- Fixture: a multi-match `getRecentMatchHistory` response, mirroring `docs/data-sources.md` §1 -


def _target_match_history_entry() -> dict[str, Any]:
    """One `matchHistoryStats` entry — the match this test's route call is expected to persist.
    Deliberately deep (a nested `matchhistorymember` list of dicts, one of which nests a further
    dict with its own list) so that a comparator which only checked the top level, or only a few
    named fields, could not pass this file's claim by accident."""
    return {
        "id": _TARGET_GAME_ID,
        "matchtype_id": 3,
        "mapname": "Arabia",
        "maptype": 9,
        "patch": "101.101",
        "startgametime": int(_MATCH_STARTED_AT.timestamp()),
        "completiontime": int(_MATCH_COMPLETED_AT.timestamp()),
        "description": "Ranked 1v1",
        "avgrating": None,
        "matchhistorymember": [
            {
                "profile_id": _THIRD_PARTY_PROFILE_ID,
                "civilization_id": 5,
                "teamid": 1,
                "outcome": 1,
                "outcometype": 2,
                "oldrating": 1500,
                "newrating": 1520,
                "slot": 1,
                "slottype": "1",
                "matchhistorymapinfo": {"id": 9, "name": "Arabia", "tags": ["land", "1v1"]},
            },
            {
                "profile_id": _OPPONENT_PROFILE_ID,
                "civilization_id": 12,
                "teamid": 2,
                "outcome": 2,
                "outcometype": 3,
                "oldrating": 1510,
                "newrating": 1490,
                "slot": 2,
                "slottype": "1",
                "matchhistorymapinfo": {"id": 9, "name": "Arabia", "tags": ["land", "1v1"]},
            },
        ],
        "options": {
            "resources": "Standard",
            "victorytype_id": 0,
            "startingage": 2,
            "difficulty_ai": None,
        },
    }


def _other_match_history_entry() -> dict[str, Any]:
    """A second, distinct `matchHistoryStats` entry — present purely so the response this test's
    fake upstream answers is a genuine multi-match response (task text: "the fixture is a
    multi-match response while the column holds one match"), never a response shaped to contain
    exactly one match by construction."""
    other_started_at = _MATCH_STARTED_AT - timedelta(days=1)
    other_completed_at = _MATCH_COMPLETED_AT - timedelta(days=1)
    return {
        "id": _OTHER_GAME_ID,
        "matchtype_id": 4,
        "mapname": "Black Forest",
        "maptype": 21,
        "patch": "101.101",
        "startgametime": int(other_started_at.timestamp()),
        "completiontime": int(other_completed_at.timestamp()),
        "description": "Ranked Team",
        "avgrating": 1600,
        "matchhistorymember": [
            {
                "profile_id": _THIRD_PARTY_PROFILE_ID,
                "civilization_id": 30,
                "teamid": 1,
                "outcome": 2,
                "outcometype": 3,
                "oldrating": 1600,
                "newrating": 1580,
                "slot": 1,
                "slottype": "1",
                "matchhistorymapinfo": {"id": 21, "name": "Black Forest", "tags": ["closed"]},
            }
        ],
        "options": {
            "resources": "Standard",
            "victorytype_id": 1,
            "startingage": 1,
            "difficulty_ai": None,
        },
    }


class _FakeRelicMatchHistoryUpstream:
    """Answers every `getRecentMatchHistory` call with the same fixed, multi-match body — enough
    to drive one real `GET /api/players/{profile_id}/matches` call end to end through whichever
    private factory T328 builds its `MatchHistoryProvider` with, the same way `test_players_routes.
    py`'s `_FailingCompanionUpstream` and `test_auth_flow.py`'s `fake_upstream` already stand in
    for their own provider's one upstream host."""

    def __init__(self, body: dict[str, Any]) -> None:
        self._body = body
        self.request_count = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.request_count += 1
        return httpx.Response(200, json=self._body)


# --- Seeding helpers, mirroring `test_players_routes.py` byte for byte where they overlap --------


async def _seed_user(db_session: AsyncSession) -> User:
    now = datetime.now(UTC)
    user = User(allowlisted_at=now)
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    return user


async def _seed_profile(
    db_session: AsyncSession, *, profile_id: int, alias: str, country: str | None = None
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


# --- T326 itself -----------------------------------------------------------------------------


async def test_reading_a_third_partys_history_persists_the_matched_entry_verbatim(
    client: TestClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-011, constitution III. A signed-in caller reads a third party's match history — the
    caller has no `profile_links` row for `_THIRD_PARTY_PROFILE_ID` anywhere in this test, so this
    is genuinely someone else's history, not the caller's own. The fake upstream answers a
    two-match `matchHistoryStats` response; `matches.raw_payload` for `_TARGET_GAME_ID` afterwards
    must be structurally identical to that response's own matching entry — the whole entry, not a
    spot-checked subset, and not the response body it was drawn from.
    """
    caller = await _seed_user(db_session)
    await _sign_in(client, db_session, caller)
    await _seed_profile(db_session, profile_id=_THIRD_PARTY_PROFILE_ID, alias="ThirdPartyHistory")

    target_entry = _target_match_history_entry()
    other_entry = _other_match_history_entry()
    upstream_body = {"matchHistoryStats": [target_entry, other_entry]}
    fake = _FakeRelicMatchHistoryUpstream(upstream_body)

    async def fake_send(
        self: httpx.AsyncClient, request: httpx.Request, **kwargs: object
    ) -> httpx.Response:
        if request.url.host == _COMPANION_HOST:
            # T450's own colour-enrichment call, not this test's own claim (module docstring's
            # new note above) — degraded here exactly as `conftest.py`'s autouse fixture already
            # degrades it everywhere else in this suite, so `matches.raw_payload`'s verbatim
            # persistence is proven independent of whatever the companion answers.
            return httpx.Response(403, request=request)
        if request.url.host != _RELIC_HOST:
            raise AssertionError(f"unexpected outbound request to {request.url}")
        assert _RECENT_MATCH_HISTORY_PATH in request.url.path, (
            f"expected a call to {_RECENT_MATCH_HISTORY_PATH}, got {request.url}"
        )
        return fake(request)

    monkeypatch.setattr(httpx.AsyncClient, "send", fake_send)

    response = client.get(f"/api/players/{_THIRD_PARTY_PROFILE_ID}/matches")
    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    stored = (
        await db_session.execute(select(Match).where(Match.game_id == _TARGET_GAME_ID))
    ).scalar_one_or_none()
    assert stored is not None, (
        f"reading {_THIRD_PARTY_PROFILE_ID}'s history must persist a `matches` row for "
        f"{_TARGET_GAME_ID} (FR-011), exactly as 001's own ingester does for a consenting user's "
        "own history"
    )

    # The whole point of a multi-match fixture (module docstring): the persisted payload must be
    # the *matched* entry, not the whole response body it was drawn from — `matches.raw_payload`
    # holds one match (`RawMatch.raw_payload`), the fixture answers two.
    assert stored.raw_payload != upstream_body, (
        "matches.raw_payload must hold the one matched entry, never the whole multi-match "
        "getRecentMatchHistory response it was drawn from"
    )
    assert stored.raw_payload != other_entry, (
        f"the {_TARGET_GAME_ID} row must not have been persisted from the *other* match in the "
        "same response — the wrong entry landing in the right row would be exactly as much a "
        "verbatim-persistence failure as a dropped field within the right one"
    )

    _assert_structurally_equal(stored.raw_payload, target_entry)


# --- T453: the shared on-view identity refresh, FR-007/FR-008a/FR-017 ---------------------------
#
# `_refresh_profile_identity` (`routers/players.py`) is the helper both this route and `GET
# /api/players/{profile_id}` now trigger on every view: it persists the real alias/country Relic's
# `getRecentMatchHistory` identity block (`profiles[]`, T451's `recent_profiles`) carries — for
# every profile the block names, not only the one being viewed — through T452's widened
# `discover.touch_aoe_profile`, and then resolves the avatar hash via exactly one companion search
# keyed on the alias it just established. Two independent, separately-degrading steps (that
# function's own docstring); the tests below exercise each in turn, plus the contrast T453's task
# text calls out explicitly: no *stale*, previously-stored alias may ever stand in for one this
# call did not itself establish.


def _identity_entry(*, profile_id: int, alias: str | None, country: str | None) -> dict[str, Any]:
    """One `profiles[]` entry — Relic's identity block, the shape `RelicMatchHistoryProvider.
    recent_profiles` reads off the same `getRecentMatchHistory` response `matchHistoryStats` rides
    alongside (`packages/providers/src/aoe2stats_providers/relic/matches.py`)."""
    return {"profile_id": profile_id, "alias": alias, "country": country}


#: aoe2companion's search endpoint (`CompanionEnrichmentProvider.search_players`,
#: `companion/provider.py`) — distinct from `enrich_matches`'s own `/api/matches`
#: (`test_match_colour_enrichment.py`'s `_CompanionUpstream`), which no test in this file exercises.
_COMPANION_SEARCH_PATH_SUFFIX = "/profiles"


def _companion_search_body(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {"profiles": entries}


def _companion_search_entry(
    *, profile_id: int, alias: str, avatar_hash: str | None, country: str | None = None
) -> dict[str, Any]:
    """One `/profiles?search=` entry (`companion/provider.py`'s `_parse_search_result`):
    `profileId`, `name`, `country`, `avatarhash` — the wire names, not `PlayerSearchResult`'s own.
    """
    return {"profileId": profile_id, "name": alias, "country": country, "avatarhash": avatar_hash}


class _FakeCompanionSearchUpstream:
    """Stands in for aoe2companion's `/profiles` search endpoint — the one `_refresh_profile_
    identity` reaches for the avatar hash, keyed on a `search=` query rather than a batch of game
    ids. `last_query` records the parameter the route actually sent, so a test can prove the search
    was keyed on the *real* alias the identity refresh just established, not a stale or placeholder
    one."""

    def __init__(self, body: dict[str, Any]) -> None:
        self._body = body
        self.request_count = 0
        self.last_query: str | None = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.request_count += 1
        self.last_query = request.url.params.get("search")
        return httpx.Response(200, json=self._body)


class _RefusingCompanionUpstream:
    """Answers nothing: any request reaching it fails the test outright. Used for the "no real
    alias established this call" contrast below, where `_refresh_profile_identity` must skip the
    companion search entirely — a request count of zero is not, on its own, distinguishable from
    "the test forgot to check"; this makes the skip a hard failure instead of a silent pass."""

    def __call__(self, request: httpx.Request) -> httpx.Response:
        raise AssertionError(
            f"companion must never be reached when this call established no real alias for the "
            f"subject — got a request to {request.url}"
        )


_IDENTITY_SUMMARY_SUBJECT_PROFILE_ID = 901_301_200
_IDENTITY_SUMMARY_OPPONENT_PROFILE_ID = 901_301_300
_IDENTITY_MATCHES_SUBJECT_PROFILE_ID = 901_301_400
_IDENTITY_MATCHES_OPPONENT_PROFILE_ID = 901_301_500
_AVATAR_SUBJECT_PROFILE_ID = 901_301_600
_AVATAR_NAMESAKE_PROFILE_ID = 901_301_601
_DEGRADED_RELIC_SUBJECT_PROFILE_ID = 901_301_700
_DEGRADED_COMPANION_SUBJECT_PROFILE_ID = 901_301_800
_NO_FRESH_ALIAS_SUBJECT_PROFILE_ID = 901_301_900


async def test_viewing_a_third_partys_summary_persists_real_alias_for_every_profile_named(
    client: TestClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T453, FR-007/FR-017: `GET /api/players/{profile_id}` — the summary route, which used to make
    no provider call at all (T419/T426, reversed by T453) — now runs `_refresh_profile_identity`
    before answering. A subject still carrying the numeric-id placeholder (`touch_aoe_profile`'s
    own "on insert" case) gets its real alias/country from Relic's identity block, and an opponent
    the same response names for free gets its own `aoe_profiles` row too — the widened
    `touch_aoe_profile` call this task's text asks for, not only a coincidental update of the one
    row already seeded.
    """
    caller = await _seed_user(db_session)
    await _sign_in(client, db_session, caller)
    await _seed_profile(
        db_session,
        profile_id=_IDENTITY_SUMMARY_SUBJECT_PROFILE_ID,
        alias=str(_IDENTITY_SUMMARY_SUBJECT_PROFILE_ID),
    )

    identity_body = {
        "matchHistoryStats": [],
        "profiles": [
            _identity_entry(
                profile_id=_IDENTITY_SUMMARY_SUBJECT_PROFILE_ID,
                alias="RealSubjectAlias",
                country="FR",
            ),
            _identity_entry(
                profile_id=_IDENTITY_SUMMARY_OPPONENT_PROFILE_ID,
                alias="RealOpponentAlias",
                country="DE",
            ),
        ],
    }
    fake = _FakeRelicMatchHistoryUpstream(identity_body)

    async def fake_send(
        self: httpx.AsyncClient, request: httpx.Request, **kwargs: object
    ) -> httpx.Response:
        if request.url.host == _COMPANION_HOST:
            # The avatar-hash half of `_refresh_profile_identity` is this file's own separate
            # test below — degraded here so this test's own claim stands independent of it.
            return httpx.Response(403, request=request)
        if request.url.host != _RELIC_HOST:
            raise AssertionError(f"unexpected outbound request to {request.url}")
        return fake(request)

    monkeypatch.setattr(httpx.AsyncClient, "send", fake_send)

    response = client.get(f"/api/players/{_IDENTITY_SUMMARY_SUBJECT_PROFILE_ID}")
    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    body = response.json()
    assert body["alias"] == "RealSubjectAlias", (
        "the on-view identity refresh must replace the numeric-id placeholder with the real alias "
        f"Relic's identity block just carried. Got {body['alias']!r}"
    )
    assert body["country"] == "FR"

    opponent = await db_session.get(AoeProfile, _IDENTITY_SUMMARY_OPPONENT_PROFILE_ID)
    assert opponent is not None, (
        "an opponent named in the same identity block must get its own `aoe_profiles` row, "
        "without a call of its own (T453's task text)"
    )
    assert opponent.alias == "RealOpponentAlias"
    assert opponent.country == "DE"


async def test_viewing_a_third_partys_match_history_also_persists_real_alias_and_country(
    client: TestClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T453's twin of the summary-route test above, through `GET /api/players/{profile_id}/
    matches` — the route that already reads `matchHistoryStats` live
    (`test_reading_a_third_partys_history_persists_the_matched_entry_verbatim` above); this test's
    own claim is the `profiles[]` half of the identical response, which `_refresh_profile_identity`
    reads alongside it."""
    caller = await _seed_user(db_session)
    await _sign_in(client, db_session, caller)
    await _seed_profile(
        db_session,
        profile_id=_IDENTITY_MATCHES_SUBJECT_PROFILE_ID,
        alias=str(_IDENTITY_MATCHES_SUBJECT_PROFILE_ID),
    )

    upstream_body = {
        "matchHistoryStats": [],
        "profiles": [
            _identity_entry(
                profile_id=_IDENTITY_MATCHES_SUBJECT_PROFILE_ID,
                alias="RealMatchesSubjectAlias",
                country="BE",
            ),
            _identity_entry(
                profile_id=_IDENTITY_MATCHES_OPPONENT_PROFILE_ID,
                alias="RealMatchesOpponentAlias",
                country="NL",
            ),
        ],
    }
    fake = _FakeRelicMatchHistoryUpstream(upstream_body)

    async def fake_send(
        self: httpx.AsyncClient, request: httpx.Request, **kwargs: object
    ) -> httpx.Response:
        if request.url.host == _COMPANION_HOST:
            return httpx.Response(403, request=request)
        if request.url.host != _RELIC_HOST:
            raise AssertionError(f"unexpected outbound request to {request.url}")
        return fake(request)

    monkeypatch.setattr(httpx.AsyncClient, "send", fake_send)

    response = client.get(f"/api/players/{_IDENTITY_MATCHES_SUBJECT_PROFILE_ID}/matches")
    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    subject = await db_session.get(AoeProfile, _IDENTITY_MATCHES_SUBJECT_PROFILE_ID)
    assert subject is not None
    assert subject.alias == "RealMatchesSubjectAlias", (
        f"Got {subject.alias!r}, expected the real alias from Relic's identity block"
    )
    assert subject.country == "BE"

    opponent = await db_session.get(AoeProfile, _IDENTITY_MATCHES_OPPONENT_PROFILE_ID)
    assert opponent is not None, (
        "an opponent named in the same identity block must get its own `aoe_profiles` row too, "
        "on the matches route exactly as on the summary route"
    )
    assert opponent.alias == "RealMatchesOpponentAlias"
    assert opponent.country == "NL"


async def test_a_freshly_established_alias_resolves_the_avatar_hash_via_one_companion_search(
    client: TestClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T453, FR-008a/FR-017: once the identity refresh has just established a real alias for the
    viewed profile — this same call, never a previously stored one (the contrast test below) — it
    resolves the avatar hash with exactly one companion search keyed on that alias, keeping only
    the `PlayerSearchResult` whose own `profile_id` matches the subject: a name search can answer
    more than one player, and the fixture below deliberately includes a same-name namesake with a
    different `profile_id` to prove the filter, not merely that *a* hash landed somewhere. The
    route then serves that hash straight from `aoe_profiles`.
    """
    caller = await _seed_user(db_session)
    await _sign_in(client, db_session, caller)
    await _seed_profile(
        db_session, profile_id=_AVATAR_SUBJECT_PROFILE_ID, alias=str(_AVATAR_SUBJECT_PROFILE_ID)
    )

    identity_body = {
        "matchHistoryStats": [],
        "profiles": [
            _identity_entry(
                profile_id=_AVATAR_SUBJECT_PROFILE_ID, alias="AvatarRealAlias", country="FR"
            )
        ],
    }
    relic_fake = _FakeRelicMatchHistoryUpstream(identity_body)
    companion_fake = _FakeCompanionSearchUpstream(
        _companion_search_body(
            [
                _companion_search_entry(
                    profile_id=_AVATAR_SUBJECT_PROFILE_ID,
                    alias="AvatarRealAlias",
                    avatar_hash="subjecthash",
                ),
                _companion_search_entry(
                    profile_id=_AVATAR_NAMESAKE_PROFILE_ID,
                    alias="AvatarRealAlias",
                    avatar_hash="namesakehash",
                ),
            ]
        )
    )

    async def fake_send(
        self: httpx.AsyncClient, request: httpx.Request, **kwargs: object
    ) -> httpx.Response:
        if request.url.host == _RELIC_HOST:
            return relic_fake(request)
        if request.url.host == _COMPANION_HOST:
            assert request.url.path.endswith(_COMPANION_SEARCH_PATH_SUFFIX), (
                f"expected the search endpoint, got {request.url}"
            )
            return companion_fake(request)
        raise AssertionError(f"unexpected outbound request to {request.url}")

    monkeypatch.setattr(httpx.AsyncClient, "send", fake_send)

    response = client.get(f"/api/players/{_AVATAR_SUBJECT_PROFILE_ID}")
    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"

    assert companion_fake.request_count == 1, (
        "the avatar hash must be resolved with exactly one companion search call, keyed on the "
        f"alias the identity refresh just established. Got {companion_fake.request_count}"
    )
    assert companion_fake.last_query == "AvatarRealAlias", (
        "the search must be keyed on the real alias just established this call, not the "
        f"placeholder it replaced. Got {companion_fake.last_query!r}"
    )

    body = response.json()
    assert body["avatar_hash"] == "subjecthash", (
        "the route must serve the hash from the matched `PlayerSearchResult`, read back from "
        f"`aoe_profiles`. Got {body['avatar_hash']!r}"
    )

    namesake = await db_session.get(AoeProfile, _AVATAR_NAMESAKE_PROFILE_ID)
    assert namesake is None or namesake.avatar_hash != "namesakehash", (
        "only the search result whose own profile_id matches the subject may be persisted — a "
        "same-name namesake's hash must never land on an unrelated profile"
    )


async def test_a_failing_relic_identity_source_leaves_the_view_answering_from_storage(
    client: TestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-017's degrade discipline, the Relic half: "a source that is unavailable degrades to
    whatever the service already holds; it MUST NOT fail the view." A Relic call that fails
    outright (never a `200`) is `_refresh_profile_identity`'s own deliberately broad catch (that
    function's docstring) — the view must still answer `200` from whatever `aoe_profiles` already
    carries, unmoved.
    """
    caller = await _seed_user(db_session)
    await _sign_in(client, db_session, caller)
    await _seed_profile(
        db_session,
        profile_id=_DEGRADED_RELIC_SUBJECT_PROFILE_ID,
        alias="AlreadyStoredRealAlias",
        country="ES",
    )

    async def fake_send(
        self: httpx.AsyncClient, request: httpx.Request, **kwargs: object
    ) -> httpx.Response:
        if request.url.host == _COMPANION_HOST:
            return httpx.Response(403, request=request)
        if request.url.host != _RELIC_HOST:
            raise AssertionError(f"unexpected outbound request to {request.url}")
        return httpx.Response(503, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "send", fake_send)

    response = client.get(f"/api/players/{_DEGRADED_RELIC_SUBJECT_PROFILE_ID}")
    assert response.status_code == 200, (
        f"a failing Relic source must never fail the view (FR-017). Got {response.status_code}: "
        f"{response.text}"
    )
    body = response.json()
    assert body["alias"] == "AlreadyStoredRealAlias", (
        f"a failed identity fetch must leave whatever this service already held untouched. Got "
        f"{body['alias']!r}"
    )
    assert body["country"] == "ES"


async def test_a_failing_companion_search_leaves_the_view_answering_from_storage_without_a_hash(
    client: TestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-017's degrade discipline, the companion half: Relic succeeds and establishes a real alias
    this same call, but companion's own search fails — the view must still answer `200`, with the
    freshly-established alias persisted (the two steps degrade independently — `_refresh_profile_
    identity`'s own docstring), and `avatar_hash` stays `None` rather than the view failing.
    """
    caller = await _seed_user(db_session)
    await _sign_in(client, db_session, caller)
    await _seed_profile(
        db_session,
        profile_id=_DEGRADED_COMPANION_SUBJECT_PROFILE_ID,
        alias=str(_DEGRADED_COMPANION_SUBJECT_PROFILE_ID),
    )

    identity_body = {
        "matchHistoryStats": [],
        "profiles": [
            _identity_entry(
                profile_id=_DEGRADED_COMPANION_SUBJECT_PROFILE_ID,
                alias="CompanionDegradedAlias",
                country="IT",
            )
        ],
    }
    relic_fake = _FakeRelicMatchHistoryUpstream(identity_body)

    async def fake_send(
        self: httpx.AsyncClient, request: httpx.Request, **kwargs: object
    ) -> httpx.Response:
        if request.url.host == _RELIC_HOST:
            return relic_fake(request)
        if request.url.host == _COMPANION_HOST:
            return httpx.Response(403, request=request)
        raise AssertionError(f"unexpected outbound request to {request.url}")

    monkeypatch.setattr(httpx.AsyncClient, "send", fake_send)

    response = client.get(f"/api/players/{_DEGRADED_COMPANION_SUBJECT_PROFILE_ID}")
    assert response.status_code == 200, (
        f"a failing companion source must never fail the view (FR-017). Got "
        f"{response.status_code}: {response.text}"
    )
    body = response.json()
    assert body["alias"] == "CompanionDegradedAlias", (
        "Relic's own half of the refresh degrades independently of companion's — the real alias "
        f"it just established must still land. Got {body['alias']!r}"
    )
    assert body["avatar_hash"] is None


async def test_no_real_alias_established_this_call_skips_the_companion_search_entirely(
    client: TestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The contrast case T453's task text calls out explicitly: "reaching for a stale, previously-
    stored alias instead would search on a name this call never itself verified." A profile that
    already carries a real alias from an earlier view, but whose *this-call* Relic identity fetch
    names nothing for it (an empty `profiles[]`), must not have companion searched at all — the
    fake below raises if it is ever reached, proving the skip rather than merely leaving its call
    count unchecked.
    """
    caller = await _seed_user(db_session)
    await _sign_in(client, db_session, caller)
    await _seed_profile(
        db_session,
        profile_id=_NO_FRESH_ALIAS_SUBJECT_PROFILE_ID,
        alias="AlreadyRealFromEarlierView",
        country="PT",
    )

    identity_body: dict[str, Any] = {"matchHistoryStats": [], "profiles": []}
    relic_fake = _FakeRelicMatchHistoryUpstream(identity_body)
    refusing_companion = _RefusingCompanionUpstream()

    async def fake_send(
        self: httpx.AsyncClient, request: httpx.Request, **kwargs: object
    ) -> httpx.Response:
        if request.url.host == _RELIC_HOST:
            return relic_fake(request)
        if request.url.host == _COMPANION_HOST:
            return refusing_companion(request)
        raise AssertionError(f"unexpected outbound request to {request.url}")

    monkeypatch.setattr(httpx.AsyncClient, "send", fake_send)

    response = client.get(f"/api/players/{_NO_FRESH_ALIAS_SUBJECT_PROFILE_ID}")
    assert response.status_code == 200, f"Got {response.status_code}: {response.text}"
    body = response.json()
    assert body["alias"] == "AlreadyRealFromEarlierView", (
        "an empty identity response must never clobber a real alias already stored (T452's own "
        f"'never clobber' direction). Got {body['alias']!r}"
    )
