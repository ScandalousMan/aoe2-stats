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
    user = User(allowlisted_at=now, ingest_consent_at=now)
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    return user


async def _seed_profile(db_session: AsyncSession, *, profile_id: int, alias: str) -> None:
    db_session.add(
        AoeProfile(profile_id=profile_id, alias=alias, alias_observed_at=datetime.now(UTC))
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
