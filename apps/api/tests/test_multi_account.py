"""Integration test for quickstart scenario 9 (T023): several Steam accounts, one aoe2-stats
account.

Sign in as A, add B through `GET /api/auth/steam/start?link=1`, and confirm

- both profiles end up under A's single account, exactly one of them primary, and both structurally
  eligible for ingestion (FR-007, FR-042, FR-043);
- nobody other than A can learn, through any endpoint this service exposes, that A and B are the
  same person (FR-045); and
- a Steam identity a *different* aoe2-stats account already holds is refused with
  `profile_already_linked` rather than silently reassigned (spec.md's edge case; contracts/
  http-api.md).

**Current failure mode, and why it is the right one.** The auth router (T029) and the backfill
stamp it applies on link (T031a) now exist, but `routers/profiles.py` (T031) does not —
`create_app()` (`app.py`) wires only `health`, `cron` and `auth` — so every request below to
`/api/profiles*` still 404s through the framework's own catch-all `HTTPException` handler,
rendered through the single error envelope as `code: "not_found"`. `_begin_link`'s first assertion
is what turns that into an honest failure — a real one, not a skip: `tests/db.py`'s own docstring
is explicit that a skip here "would silently report every integration test... as passed without
having run" (T015a), which is exactly what let this class of test skip silently until that task
closed the gap, and every sibling file in this batch (`test_auth_flow.py`, `test_allowlist.py`,
`test_unlink.py`, `test_consent.py`) asserts directly against the real throwaway database for the
same reason. T031 is what turns this failure into the behaviour asserted here; this file is not
expected to change once it lands, only to stop failing.

**How Steam and Relic are stood in for.** Following the same convention T021's `test_auth_flow.py`
established for this batch: interception happens at `httpx.Client.send` / `httpx.AsyncClient.send`
— the one boundary every provider is built on (`packages/providers/src/aoe2stats_providers/
base.py`) — rather than at any dependency name internal to the router or the two concrete providers
(`SteamAuthProvider`, T026; `ProfileProvider`, T027), none of which exist yet to name.
`_FakeUpstream` answers Relic's `getPersonalStat` shape (docs/data-sources.md) for invented
personas this scenario needs beyond the two real, frozen fixtures T021 uses, and always reports
Steam's assertion valid: forging or replaying that assertion is T021's and T019's concern, not
this file's.

**The session cookie**, for the accounts this file only needs to already exist (A before B is
linked, the rival account, D) rather than to sign in through: a `sessions` row inserted directly
and handed to the client as a cookie, matching `test_unlink.py`'s (T024) and `test_consent.py`'s
(T025) same `SESSION_COOKIE_NAME` working assumption — not yet fixed by T028, and the one place to
update in all three files together if it lands on something else.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api import security
from aoe2stats_api.settings import get_settings
from aoe2stats_storage.models import AoeProfile, ProfileLink, SteamIdentity, User
from aoe2stats_storage.models import Session as UserSession

pytestmark = [pytest.mark.usefixtures("environment")]

#: See the module docstring. Not yet fixed by T028; shared with test_unlink.py and test_consent.py.
SESSION_COOKIE_NAME = "session_id"

_START_PATH = "/api/auth/steam/start"
_CALLBACK_PATH = "/api/auth/steam/callback"

# Four Steam64 ids (17 digits, the real `7656119...` prefix), all distinct so a substring match in
# the fake upstream below can never confuse two of them.
STEAM_ID_A = "76561198000000011"
STEAM_ID_B = "76561198000000012"
STEAM_ID_D = "76561198000000013"
STEAM_ID_TAKEN = "76561198000000019"

PROFILE_ID_A = 700_011
PROFILE_ID_B = 700_012
PROFILE_ID_D = 700_013
PROFILE_ID_TAKEN = 700_019

_STEAM_CHECK_AUTH_VALID = "ns:http://specs.openid.net/auth/2.0\nis_valid:true"


# --- The fake upstream: the httpx transport boundary every provider is built on -----------------


class _FakeUpstream:
    """Answers Steam's `check_authentication` and Relic's `getPersonalStat` for every persona
    this file configures, reached at `httpx.Client.send` / `httpx.AsyncClient.send`.

    Steam verification always succeeds: whether a forged or replayed assertion is rejected is
    T019's and T021's concern, not FR-007/FR-045's. `personal_stat_response` returns the full
    known catalogue regardless of which `profile_names` were actually requested — a deliberate
    simplification, since a fake returning a superset of real, correctly shaped entries is
    indistinguishable to a caller from one that filtered them, and parsing Relic's own
    `profile_names=["/steam/<id>"]` encoding precisely is not what this file is testing.
    """

    def __init__(self) -> None:
        self.personas: dict[str, ProfileRefLike] = {}
        self.check_authentication_calls = 0
        self.resolve_profile_calls = 0

    def add_persona(self, steam_id64: str, profile_id: int, alias: str, country: str) -> None:
        self.personas[steam_id64] = ProfileRefLike(steam_id64, profile_id, alias, country)

    def steam_response(self, request: httpx.Request) -> httpx.Response:
        self.check_authentication_calls += 1
        return httpx.Response(200, text=_STEAM_CHECK_AUTH_VALID, request=request)

    def relic_response(self, request: httpx.Request) -> httpx.Response:
        self.resolve_profile_calls += 1
        member_groups = [
            {
                "id": persona.profile_id,
                "type": 1,
                "name": "",
                "members": [
                    {
                        "profile_id": persona.profile_id,
                        "name": f"/steam/{persona.steam_id64}",
                        "alias": persona.alias,
                        "country": persona.country,
                        "personal_statgroup_id": persona.profile_id,
                        "clanlist_name": "",
                        "leaderboardregion_id": 0,
                        "level": 1,
                        "xp": 0,
                    }
                ],
            }
            for persona in self.personas.values()
        ]
        leaderboard_stats = [
            {
                "statgroup_id": persona.profile_id,
                "leaderboard_id": 3,
                "rating": 1000,
                "rank": -1,
                "ranklevel": 0,
                "ranktotal": 0,
                "regionrank": -1,
                "regionranktotal": 0,
                "wins": 0,
                "losses": 0,
                "streak": 0,
                "drops": 0,
                "disputes": 0,
                "highestrank": 0,
                "highestranklevel": 0,
                "highestrating": 1000,
                "lastmatchdate": 0,
            }
            for persona in self.personas.values()
        ]
        # `code: 0` is Relic's "resolved" outcome (docs/data-sources.md; `RelicProfileProvider.
        # resolve_profile` treats anything else, `1` included, as "no such profile" and returns
        # `None` — the value this fake originally carried, which silently made every `resolve_
        # profile` call in this file answer `no_aoe2_profile` regardless of the persona.
        body = {
            "result": {"code": 0, "message": "OK"},
            "statGroups": member_groups,
            "leaderboardStats": leaderboard_stats,
        }
        return httpx.Response(200, json=body, request=request)


class ProfileRefLike:
    """Just enough of `ProfileRef` (packages/providers/src/aoe2stats_providers/base.py) for
    `_FakeUpstream` to build a Relic-shaped response from — not the DTO itself, since the real
    provider is what is responsible for producing one, and does not exist yet (T027)."""

    def __init__(self, steam_id64: str, profile_id: int, alias: str, country: str) -> None:
        self.steam_id64 = steam_id64
        self.profile_id = profile_id
        self.alias = alias
        self.country = country


@pytest.fixture
def fake_upstream(monkeypatch: pytest.MonkeyPatch) -> _FakeUpstream:
    fake = _FakeUpstream()
    original_sync_send = httpx.Client.send

    def sync_send(self: httpx.Client, request: httpx.Request, **kwargs: object) -> httpx.Response:
        if request.url.host == "steamcommunity.com":
            return fake.steam_response(request)
        return original_sync_send(self, request, **kwargs)  # type: ignore[no-any-return]

    async def async_send(
        self: httpx.AsyncClient, request: httpx.Request, **kwargs: object
    ) -> httpx.Response:
        if request.url.host != "aoe-api.worldsedgelink.com":
            raise AssertionError(f"unexpected outbound request to {request.url}")
        return fake.relic_response(request)

    monkeypatch.setattr(httpx.Client, "send", sync_send)
    monkeypatch.setattr(httpx.AsyncClient, "send", async_send)
    return fake


@pytest.fixture(autouse=True)
def _allowlist_every_persona(environment: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """`conftest.py`'s `REQUIRED_ENV` ships `BETA_ALLOWLIST_STEAM_IDS` empty (T022 owns that
    rejection); this file admits every persona it uses so an allowlist 403 never masquerades as
    the outcome under test."""
    monkeypatch.setenv(
        "BETA_ALLOWLIST_STEAM_IDS", ",".join([STEAM_ID_A, STEAM_ID_B, STEAM_ID_D, STEAM_ID_TAKEN])
    )
    get_settings.cache_clear()


# --- Seeding an already-signed-in account, without going through the flow under test -------------


async def _seed_linked_account(
    db_session: AsyncSession,
    *,
    steam_id64: str,
    profile_id: int,
    alias: str,
    country: str,
) -> User:
    now = datetime.now(UTC)
    user = User(id=uuid.uuid4(), created_at=now, allowlisted_at=now)
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        SteamIdentity(steam_id64=steam_id64, user_id=user.id, verified_at=now, last_sign_in_at=now)
    )
    db_session.add(AoeProfile(profile_id=profile_id, alias=alias, country=country))
    await db_session.flush()
    db_session.add(
        ProfileLink(
            id=uuid.uuid4(),
            user_id=user.id,
            profile_id=profile_id,
            steam_id64=steam_id64,
            is_primary=True,
            linked_at=now,
            backfill_requested_at=now,
        )
    )
    await db_session.commit()
    return user


async def _sign_in_as(client: TestClient, db_session: AsyncSession, user: User) -> None:
    """Insert a `sessions` row directly and hand the client its cookie — see the module docstring:
    there is no auth router yet (T029) to sign in through for an account that must simply already
    exist when a test begins.

    Signed exactly as `security.issue_session_cookie` signs a real one (`<sessions.id>.<hmac-
    sha256 signature>`, `security.py`) — `security.read_session_id` rejects anything else before a
    query is ever issued, which an unsigned raw `session_id` — this helper's original form —
    always was.
    """
    session_id = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    db_session.add(
        UserSession(
            id=session_id, user_id=user.id, created_at=now, expires_at=now + timedelta(days=30)
        )
    )
    await db_session.commit()
    secret = get_settings().app_secret_key.get_secret_value()
    client.cookies.set(SESSION_COOKIE_NAME, security._sign(session_id, secret))


# --- The flow actually under test: linking a second Steam account --------------------------------


def _begin_link(client: TestClient) -> tuple[str, dict[str, str]]:
    """`GET /api/auth/steam/start?link=1`, returning the exact `openid.return_to` Steam would echo
    back and its own query parameters — the CSRF `state` this feature embeds there (research.md
    §2) is only known once the server has issued it, so it is read back rather than invented."""
    response = client.get(f"{_START_PATH}?link=1", follow_redirects=False)
    assert response.status_code == 302, (
        "GET /api/auth/steam/start?link=1 did not redirect to Steam — the auth router (T029) is "
        f"not registered yet. Got {response.status_code}: {response.text}"
    )
    location = response.headers["location"]
    parsed = urlsplit(location)
    assert parsed.hostname == "steamcommunity.com", f"expected a redirect to Steam, got {location}"
    start_params = dict(parse_qsl(parsed.query))
    return_to = start_params["openid.return_to"]
    return_to_query = dict(parse_qsl(urlsplit(return_to).query))
    return return_to, return_to_query


def _callback_params(steam_id64: str, return_to: str) -> dict[str, str]:
    """A syntactically well-formed OpenID 2.0 `id_res` assertion (research.md §2): `claimed_id`
    matching `https://steamcommunity.com/openid/id/<17 digits>`."""
    identity = f"https://steamcommunity.com/openid/id/{steam_id64}"
    return {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "id_res",
        "openid.op_endpoint": "https://steamcommunity.com/openid/login",
        "openid.claimed_id": identity,
        "openid.identity": identity,
        "openid.return_to": return_to,
        "openid.response_nonce": f"2026-08-20T12:00:00Z{steam_id64}",
        "openid.assoc_handle": "1234567890",
        "openid.signed": (
            "signed,op_endpoint,claimed_id,identity,return_to,response_nonce,assoc_handle"
        ),
        "openid.sig": "dGVzdC1zaWduYXR1cmUtdmFsdWU=",
    }


def _link_account(client: TestClient, steam_id64: str) -> httpx.Response:
    """Drive one full `?link=1` begin-then-callback round trip for `steam_id64`, adding it to
    whichever account the client is currently signed in as. Returns the callback's own response,
    without following redirects."""
    return_to, return_to_query = _begin_link(client)
    params = {**return_to_query, **_callback_params(steam_id64, return_to)}
    return client.get(_CALLBACK_PATH, params=params, follow_redirects=False)


# --- Response-shape helpers, resilient to exactly where a field is nested ------------------------


def _error_code(response: httpx.Response) -> str | None:
    """The product-meaningful `code` a failed request reports, in whichever of the two documented
    shapes it takes: the standard JSON error envelope, or a redirect carrying `?error=<code>`."""
    if response.is_redirect:
        query = dict(parse_qsl(urlsplit(response.headers.get("location", "")).query))
        return query.get("error") or query.get("code")
    try:
        body = response.json()
    except ValueError:
        return None
    error = body.get("error") if isinstance(body, dict) else None
    return error.get("code") if isinstance(error, dict) else None


def _contains_value(payload: Any, needle: Any) -> bool:
    """Whether `needle` appears anywhere in a JSON-decoded body, at any depth, as a value —
    resilient to exactly which key a response nests a profile id under."""
    if payload == needle:
        return True
    if isinstance(payload, dict):
        return any(_contains_value(value, needle) for value in payload.values())
    if isinstance(payload, list):
        return any(_contains_value(item, needle) for item in payload)
    return False


def _count_values_for_key(payload: Any, key: str, value: Any) -> int:
    """How many times `key` appears anywhere in `payload` holding exactly `value` — used to check
    "exactly one primary" without assuming where in the response shape `is_primary` sits."""
    count = 0
    if isinstance(payload, dict):
        for k, v in payload.items():
            if k == key and v == value:
                count += 1
            count += _count_values_for_key(v, key, value)
    elif isinstance(payload, list):
        for item in payload:
            count += _count_values_for_key(item, key, value)
    return count


async def _profile_links_for_user(
    db_session: AsyncSession, user_id: uuid.UUID
) -> list[ProfileLink]:
    result = await db_session.execute(select(ProfileLink).where(ProfileLink.user_id == user_id))
    return list(result.scalars().all())


# --- Scenario 9 ------------------------------------------------------------------------------


async def test_linking_second_steam_account_puts_both_profiles_under_one_account(
    client: TestClient,
    db_session: AsyncSession,
    fake_upstream: _FakeUpstream,
) -> None:
    """Sign in as A, link B, and confirm both land under A's single account with exactly one
    primary, both structurally eligible for ingestion (FR-007, FR-042, FR-043)."""
    fake_upstream.add_persona(STEAM_ID_A, PROFILE_ID_A, "PlayerA", "FR")
    fake_upstream.add_persona(STEAM_ID_B, PROFILE_ID_B, "PlayerB", "FR")

    user_a = await _seed_linked_account(
        db_session, steam_id64=STEAM_ID_A, profile_id=PROFILE_ID_A, alias="PlayerA", country="FR"
    )
    await _sign_in_as(client, db_session, user_a)

    link_response = _link_account(client, STEAM_ID_B)
    assert link_response.is_redirect, (
        f"linking B to A's account failed: {link_response.status_code} {link_response.text}"
    )
    assert fake_upstream.check_authentication_calls == 1, (
        "linking a second account must still perform check_authentication (FR-001) — nothing "
        "may be added to an account without proving the sign-in"
    )

    me_body = client.get("/api/me").json()
    assert me_body.get("authenticated") is True
    assert _contains_value(me_body, PROFILE_ID_A)
    assert _contains_value(me_body, PROFILE_ID_B)
    assert _count_values_for_key(me_body, "is_primary", True) == 1

    profiles_body = client.get("/api/profiles").json()
    assert _contains_value(profiles_body, PROFILE_ID_A)
    assert _contains_value(profiles_body, PROFILE_ID_B)
    assert _count_values_for_key(profiles_body, "is_primary", True) == 1

    # Verified by inspection, not by trusting the response (the discipline T087 also applies to
    # erasure): both links belong to A, both are active, and the one T031a itself just created
    # (B's) carries the flag that queues its 31-day backfill — "both eligible for ingestion" made
    # concrete at the row level, not merely echoed back in JSON.
    links = await _profile_links_for_user(db_session, user_a.id)
    active_links = {link.profile_id: link for link in links if link.unlinked_at is None}
    assert set(active_links) == {PROFILE_ID_A, PROFILE_ID_B}, (
        "both profiles must belong to the same, single account (FR-007)"
    )
    assert sum(1 for link in active_links.values() if link.is_primary) == 1, (
        "exactly one profile must be primary (FR-043)"
    )
    assert active_links[PROFILE_ID_B].backfill_requested_at is not None, (
        "linking B must queue its 31-day backfill (T031a) — otherwise it is not actually "
        "eligible for ingestion (FR-042) whatever the API response claims"
    )


async def test_linked_accounts_are_never_revealed_to_another_caller(
    client: TestClient,
    db_session: AsyncSession,
    fake_upstream: _FakeUpstream,
) -> None:
    """FR-045: nobody other than the account holder may learn, through anything this service
    exposes, that A and B are the same person."""
    fake_upstream.add_persona(STEAM_ID_A, PROFILE_ID_A, "PlayerA", "FR")
    fake_upstream.add_persona(STEAM_ID_B, PROFILE_ID_B, "PlayerB", "FR")

    user_a = await _seed_linked_account(
        db_session, steam_id64=STEAM_ID_A, profile_id=PROFILE_ID_A, alias="PlayerA", country="FR"
    )
    await _sign_in_as(client, db_session, user_a)
    assert _link_account(client, STEAM_ID_B).is_redirect

    # A third, unrelated account: D has never met A or B.
    user_d = await _seed_linked_account(
        db_session, steam_id64=STEAM_ID_D, profile_id=PROFILE_ID_D, alias="PlayerD", country="DE"
    )
    client.cookies.clear()
    await _sign_in_as(client, db_session, user_d)

    me_body = client.get("/api/me").json()
    assert me_body.get("authenticated") is True
    assert not _contains_value(me_body, PROFILE_ID_A), "D's own /api/me must not mention A"
    assert not _contains_value(me_body, PROFILE_ID_B), "D's own /api/me must not mention B"

    profiles_body = client.get("/api/profiles").json()
    assert not _contains_value(profiles_body, PROFILE_ID_A)
    assert not _contains_value(profiles_body, PROFILE_ID_B)

    # D reaching for a profile that is not theirs must be refused, not answered with a hint of
    # who it actually belongs to.
    unlink_as_d = client.delete(f"/api/profiles/{PROFILE_ID_B}")
    assert unlink_as_d.status_code in (403, 404), (
        f"D was able to act on B's profile link: {unlink_as_d.status_code} {unlink_as_d.text}"
    )
    assert not _contains_value(unlink_as_d.json(), PROFILE_ID_A)

    primary_as_d = client.post(f"/api/profiles/{PROFILE_ID_B}/primary")
    assert primary_as_d.status_code in (403, 404)
    assert not _contains_value(primary_as_d.json(), PROFILE_ID_A)


async def test_linking_a_steam_identity_already_owned_by_another_account_is_refused(
    client: TestClient,
    db_session: AsyncSession,
    fake_upstream: _FakeUpstream,
) -> None:
    """A Steam identity another aoe2-stats account already holds must be refused with
    `profile_already_linked`, not silently reassigned (spec.md edge case; contracts/http-api.md)."""
    fake_upstream.add_persona(STEAM_ID_A, PROFILE_ID_A, "PlayerA", "FR")
    # The identity A is about to reach for already belongs to a rival account — same Steam
    # account, so necessarily the same AoE2 profile (spec.md: "one Steam account maps to exactly
    # one AoE2 profile").
    fake_upstream.add_persona(STEAM_ID_TAKEN, PROFILE_ID_TAKEN, "RivalAlias", "BE")

    rival = await _seed_linked_account(
        db_session,
        steam_id64=STEAM_ID_TAKEN,
        profile_id=PROFILE_ID_TAKEN,
        alias="RivalAlias",
        country="BE",
    )

    user_a = await _seed_linked_account(
        db_session, steam_id64=STEAM_ID_A, profile_id=PROFILE_ID_A, alias="PlayerA", country="FR"
    )
    await _sign_in_as(client, db_session, user_a)

    conflict_response = _link_account(client, STEAM_ID_TAKEN)
    assert _error_code(conflict_response) == "profile_already_linked", (
        f"expected profile_already_linked, got {conflict_response.status_code} "
        f"{conflict_response.text}"
    )
    assert not conflict_response.is_success

    # The rival account must be untouched, and A must not have acquired the rival's identity.
    rival_links = await _profile_links_for_user(db_session, rival.id)
    assert {link.profile_id for link in rival_links if link.unlinked_at is None} == {
        PROFILE_ID_TAKEN
    }
    a_links = await _profile_links_for_user(db_session, user_a.id)
    assert PROFILE_ID_TAKEN not in {link.profile_id for link in a_links if link.unlinked_at is None}
