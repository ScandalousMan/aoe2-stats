"""Integration test for quickstart scenario 1 (T021): sign-in resolves profile and ratings with
no input; a replayed callback with identical parameters is rejected; a callback with one character
of `openid.claimed_id` altered is rejected; a Steam account that has never played AoE2 online
yields `no_aoe2_profile` and not a stack trace (FR-001, FR-002, FR-003).

**Why this fails right now, and on purpose.** Neither the auth router
(`apps/api/src/aoe2stats_api/routers/auth.py`, T029) nor the two concrete providers it calls
(`SteamAuthProvider`, T026; `ProfileProvider`, T027) exist yet — `apps/api/src/aoe2stats_api/
app.py` registers only `health` and `cron`. Every request below to `/api/auth/steam/*` therefore
404s before `_FakeSteamAndRelic` is ever reached, which is the "right reason" this test-first task
(tasks.md) asks for. Once T026, T028 and T029 land, the same assertions exercise the real flow end
to end with no network access (constitution III): the fake below intercepts at the one boundary
every provider is built on — `httpx.Client.send` / `httpx.AsyncClient.send`
(`packages/providers/src/aoe2stats_providers/base.py`) — using the exact frozen responses T012
captured (`packages/providers/fixtures/`), rather than any internal dependency name this test
would otherwise have to guess ahead of an implementation that does not exist yet.

**The replay and the tampered-`claimed_id` scenarios hinge on the same mechanism.**
`check_authentication` is a signature check over the *entire* callback parameter set, and Steam's
own reply is single-use (`packages/providers/fixtures/steam/README.md`). `_FakeSteamAndRelic`
below models exactly that: one specific parameter set is ever valid, and only once, rather than a
looser rule ("any second request fails") that could pass by accident without the router ever
calling `check_authentication` at all.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api.settings import get_settings
from aoe2stats_storage.models import ProfileLink, ProviderCall, SteamIdentity

_FIXTURES = Path(__file__).resolve().parents[3] / "packages" / "providers" / "fixtures"

_STEAM_CHECK_AUTH_VALID = (_FIXTURES / "steam" / "check_authentication_valid.txt").read_text()
_STEAM_CHECK_AUTH_INVALID = (_FIXTURES / "steam" / "check_authentication_invalid.txt").read_text()
_RELIC_PERSONAL_STAT = json.loads((_FIXTURES / "relic" / "get_personal_stat.json").read_text())
_RELIC_PERSONAL_STAT_UNREGISTERED = json.loads(
    (_FIXTURES / "relic" / "get_personal_stat_unregistered.json").read_text()
)

# docs/data-sources.md: "Verified: 76561197984749679 resolves to profile 196240" — the one
# steamid64/profile_id pair backed by a real, frozen response, not an invented one.
_HAPPY_STEAM_ID64 = "76561197984749679"
_HAPPY_PROFILE_ID = "196240"
_HAPPY_ALIAS = "Oni.TheViper"
_HAPPY_LEADERBOARD_RATING = "2704"  # leaderboard_id 3, from the same fixture

# A syntactically valid steamid64 (17 digits, the real `7656119...` Steam64 prefix) for an
# account `relic/get_personal_stat_unregistered.json` confirms owns no AoE2 profile at all. A
# distinct value from the happy persona so a substring match in the fake upstream below can never
# confuse the two.
_NO_PROFILE_STEAM_ID64 = "76561197960287930"

_START_PATH = "/api/auth/steam/start"
_CALLBACK_PATH = "/api/auth/steam/callback"


# --- The fake upstream: the httpx transport boundary every provider is built on -----------------


class _FakeSteamAndRelic:
    """Stands in for Steam's `check_authentication` endpoint and Relic's `getPersonalStat`,
    reached at `httpx.Client.send` / `httpx.AsyncClient.send` — the shared boundary every provider
    is built on (`packages/providers/src/aoe2stats_providers/base.py`), not any dependency name
    internal to the router or the concrete providers, none of which exist yet (T026, T028, T029).
    """

    def __init__(self) -> None:
        self._genuine: frozenset[tuple[str, str]] | None = None
        self._consumed: set[frozenset[tuple[str, str]]] = set()
        self.check_authentication_calls = 0
        self.resolve_profile_calls = 0
        # T029b: from the `relic_calls_before_failure`-th call onward (1-indexed, counting every
        # call to `getPersonalStat` — `resolve_profile` and `personal_stats` alike), answer
        # `relic_failure_mode` instead of a fixture. `None` (the default) never fails.
        self.relic_failure_mode: str | None = None
        self.relic_calls_before_failure: int | None = None

    def issue(self, params: dict[str, str]) -> None:
        """Record the one parameter set a real Steam login would have genuinely signed.

        `openid.mode` is excluded from the snapshot: the real `check_authentication` round trip
        resends every field of the original `id_res` assertion verbatim except that one, which is
        deliberately overwritten (research.md §2 — "POST every returned parameter back to Steam
        with `openid.mode` replaced by `check_authentication`"). Comparing it too would make even
        the genuine, first-use call fail to match itself.
        """
        self._genuine = _snapshot(params)

    def steam_response(self, request: httpx.Request) -> httpx.Response:
        self.check_authentication_calls += 1
        snapshot = _snapshot(_request_params(request))
        valid = snapshot == self._genuine and snapshot not in self._consumed
        if valid:
            self._consumed.add(snapshot)
        body = _STEAM_CHECK_AUTH_VALID if valid else _STEAM_CHECK_AUTH_INVALID
        return httpx.Response(200, text=body, request=request)

    def relic_response(self, request: httpx.Request) -> httpx.Response:
        self.resolve_profile_calls += 1
        if (
            self.relic_failure_mode is not None
            and self.relic_calls_before_failure is not None
            and self.resolve_profile_calls > self.relic_calls_before_failure
        ):
            if self.relic_failure_mode == "rate_limited":
                return httpx.Response(429, request=request)
            if self.relic_failure_mode == "server_error":
                return httpx.Response(500, request=request)
            if self.relic_failure_mode == "non_json":
                return httpx.Response(200, text="not a JSON body at all", request=request)
            raise AssertionError(f"unknown relic_failure_mode {self.relic_failure_mode!r}")
        haystack = request.url.query.decode() + (request.content or b"").decode(errors="ignore")
        if _NO_PROFILE_STEAM_ID64 in haystack:
            return httpx.Response(200, json=_RELIC_PERSONAL_STAT_UNREGISTERED, request=request)
        return httpx.Response(200, json=_RELIC_PERSONAL_STAT, request=request)


def _snapshot(params: dict[str, str]) -> frozenset[tuple[str, str]]:
    """`params`, minus `openid.mode` — see `_FakeSteamAndRelic.issue`."""
    return frozenset((key, value) for key, value in params.items() if key != "openid.mode")


def _request_params(request: httpx.Request) -> dict[str, str]:
    """Every `openid.*` field a `check_authentication` request carries, from the query string and,
    when present, an `x-www-form-urlencoded` body — merged rather than assumed to live in exactly
    one of the two, since T026 does not exist yet to say which shape it will use.
    """
    merged: dict[str, str] = dict(request.url.params)
    content = request.content
    if content:
        with contextlib.suppress(UnicodeDecodeError):
            merged.update(parse_qsl(content.decode()))
    return merged


@pytest.fixture
def fake_upstream(monkeypatch: pytest.MonkeyPatch) -> _FakeSteamAndRelic:
    """Intercept every outbound `httpx` call: Steam and Relic are answered from frozen fixtures;
    anything else (in particular `TestClient`'s own traffic to the FastAPI app, which is itself an
    `httpx.Client` under the hood) passes through to the real implementation untouched.
    """
    fake = _FakeSteamAndRelic()
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
def _allowlist_test_personas(environment: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """`conftest.py`'s `REQUIRED_ENV` ships `BETA_ALLOWLIST_STEAM_IDS` empty — T022 owns that
    rejection. This scenario needs both personas admitted, so an allowlist 403 never masquerades
    as a Steam-verification failure.
    """
    monkeypatch.setenv("BETA_ALLOWLIST_STEAM_IDS", f"{_HAPPY_STEAM_ID64},{_NO_PROFILE_STEAM_ID64}")
    get_settings.cache_clear()


# --- Helpers shared by every scenario -------------------------------------------------------------


def _begin_sign_in(client: TestClient) -> tuple[str, dict[str, str]]:
    """`GET /api/auth/steam/start`, returning the exact `openid.return_to` Steam would echo back
    and its own query parameters — the one part of a genuine callback this test cannot invent,
    since any CSRF `state` this feature embeds there (research.md §2, "tied to the browser
    session") is only known once the server has issued it.
    """
    response = client.get(_START_PATH, follow_redirects=False)
    assert response.status_code == 302, (
        "GET /api/auth/steam/start did not redirect to Steam — the auth router (T029) is not "
        f"registered yet. Got {response.status_code}: {response.text}"
    )
    location = response.headers["location"]
    parsed = urlsplit(location)
    assert parsed.hostname == "steamcommunity.com", f"expected a redirect to Steam, got {location}"
    start_params = dict(parse_qsl(parsed.query))
    return_to = start_params["openid.return_to"]
    return_to_query = dict(parse_qsl(urlsplit(return_to).query))
    return return_to, return_to_query


def _genuine_callback_params(steam_id64: str, return_to: str) -> dict[str, str]:
    """A syntactically well-formed OpenID 2.0 `id_res` assertion, shaped exactly as research.md
    §2 describes: `claimed_id` matching `https://steamcommunity.com/openid/id/<17 digits>`.
    """
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


def _error_code(response: httpx.Response) -> str | None:
    """The product-meaningful `code` a failed callback reports, in whichever of the two documented
    shapes it takes: the standard JSON error envelope (`contracts/http-api.md`), or a redirect to
    the front end carrying `?error=<code>`.
    """
    if response.is_redirect:
        query = dict(parse_qsl(urlsplit(response.headers.get("location", "")).query))
        return query.get("error")
    try:
        body = response.json()
    except ValueError:
        return None
    error = body.get("error")
    return error.get("code") if isinstance(error, dict) else None


def _sign_in(
    client: TestClient, fake_upstream: _FakeSteamAndRelic, steam_id64: str
) -> httpx.Response:
    """Drive one full begin-then-callback round trip for `steam_id64`, with a freshly issued,
    unused genuine assertion. Returns the callback's own response, without following redirects.
    """
    return_to, return_to_query = _begin_sign_in(client)
    genuine = _genuine_callback_params(steam_id64, return_to)
    fake_upstream.issue(genuine)
    return client.get(_CALLBACK_PATH, params={**return_to_query, **genuine}, follow_redirects=False)


# --- Scenario 1 --------------------------------------------------------------------------------


def test_sign_in_resolves_profile_and_ratings_with_no_input(
    client: TestClient, fake_upstream: _FakeSteamAndRelic
) -> None:
    callback = _sign_in(client, fake_upstream, _HAPPY_STEAM_ID64)

    assert callback.is_redirect, f"expected a redirect back into the app, got {callback.text}"
    assert fake_upstream.check_authentication_calls == 1, (
        "the callback must perform the check_authentication round trip (FR-001) — nothing may "
        "sign a caller in without it"
    )
    assert fake_upstream.resolve_profile_calls >= 1, (
        "the AoE2 profile must be resolved automatically, with no manual identifier entry (FR-002)"
    )

    me = client.get("/api/me")
    assert me.status_code == 200
    assert me.json()["authenticated"] is True

    profiles = client.get("/api/profiles")
    assert profiles.status_code == 200
    # No pinned response schema in contracts/http-api.md beyond "linked profiles with current
    # ratings per leaderboard" (FR-008) — asserted as substrings of the real frozen fixture rather
    # than against a shape this test would otherwise have to invent ahead of T031.
    assert _HAPPY_PROFILE_ID in profiles.text
    assert _HAPPY_ALIAS in profiles.text
    assert _HAPPY_LEADERBOARD_RATING in profiles.text


def test_replayed_callback_with_identical_parameters_is_rejected(
    client: TestClient, fake_upstream: _FakeSteamAndRelic
) -> None:
    return_to, return_to_query = _begin_sign_in(client)
    genuine = _genuine_callback_params(_HAPPY_STEAM_ID64, return_to)
    fake_upstream.issue(genuine)
    params = {**return_to_query, **genuine}

    first = client.get(_CALLBACK_PATH, params=params, follow_redirects=False)
    assert first.is_redirect and fake_upstream.check_authentication_calls == 1

    signout = client.post("/api/auth/signout")
    assert signout.status_code == 200

    replayed = client.get(_CALLBACK_PATH, params=params, follow_redirects=False)

    # Not asserted: that `check_authentication_calls` reaches 2. A router is free to reject a
    # replay either by asking Steam again (whose own nonce is single-use — `_FakeSteamAndRelic`
    # would answer `is_valid:false` a second time) or by invalidating its own CSRF `state` the
    # moment it is first consumed, before ever contacting Steam again — both are sound, and which
    # one T029 picks is not this test's business. What every implementation owes, and what this
    # scenario exists to catch, is the outcome: replaying the exact callback must never sign
    # anyone in (quickstart scenario 1 — "if a replayed callback signs you in,
    # check_authentication is not being performed").
    assert _error_code(replayed) == "steam_assertion_invalid"
    assert client.get("/api/me").json()["authenticated"] is False


def test_callback_with_tampered_claimed_id_is_rejected(
    client: TestClient, fake_upstream: _FakeSteamAndRelic
) -> None:
    return_to, return_to_query = _begin_sign_in(client)
    genuine = _genuine_callback_params(_HAPPY_STEAM_ID64, return_to)
    fake_upstream.issue(genuine)

    tampered = dict(genuine)
    last_digit = tampered["openid.claimed_id"][-1]
    tampered["openid.claimed_id"] = tampered["openid.claimed_id"][:-1] + (
        "1" if last_digit != "1" else "2"
    )

    response = client.get(
        _CALLBACK_PATH, params={**return_to_query, **tampered}, follow_redirects=False
    )

    assert fake_upstream.check_authentication_calls == 1, (
        "a tampered assertion must still be sent through check_authentication rather than "
        "rejected on shape alone — the signature check is what proves it was forged"
    )
    assert _error_code(response) == "steam_assertion_invalid"
    assert client.get("/api/me").json()["authenticated"] is False


def test_steam_account_with_no_aoe2_profile_yields_an_explanation_not_a_crash(
    client: TestClient, fake_upstream: _FakeSteamAndRelic
) -> None:
    response = _sign_in(client, fake_upstream, _NO_PROFILE_STEAM_ID64)

    assert response.status_code < 500, (
        "a Steam account with no AoE2 profile must yield an explanatory outcome (FR-003), not an "
        f"error state — got {response.status_code}: {response.text}"
    )
    assert "Traceback" not in response.text
    assert fake_upstream.resolve_profile_calls == 1
    assert _error_code(response) == "no_aoe2_profile"
    assert client.get("/api/me").json()["authenticated"] is False


# --- T029b: a Relic failure mid-callback -----------------------------------------------------


async def _relic_provider_calls(db_session: AsyncSession) -> list[ProviderCall]:
    result = await db_session.execute(select(ProviderCall).where(ProviderCall.provider == "relic"))
    return list(result.scalars().all())


async def test_relic_rate_limit_on_resolve_profile_redirects_with_provider_unavailable(
    client: TestClient, fake_upstream: _FakeSteamAndRelic, db_session: AsyncSession
) -> None:
    """A rate limit on the very first Relic call (`resolve_profile`) must answer the documented
    `provider_unavailable` redirect (contracts/http-api.md), never the raw internal-error body the
    catch-all in `app.py` would otherwise send to a browser mid-redirect from Steam — exactly what
    T030b already fixed for a rejected beta visitor, reintroduced here for a Relic outage.
    """
    fake_upstream.relic_failure_mode = "rate_limited"
    fake_upstream.relic_calls_before_failure = 0

    response = _sign_in(client, fake_upstream, _HAPPY_STEAM_ID64)

    assert response.status_code < 500, (
        f"a Relic rate limit must yield the documented redirect, not a raw error — "
        f"got {response.status_code}: {response.text}"
    )
    assert "Traceback" not in response.text
    assert _error_code(response) == "provider_unavailable"
    assert client.get("/api/me").json()["authenticated"] is False

    # Constitution III: "a provider_calls record of every call" — the failing call is not exempt,
    # and it is the one an operator most needs (T029b).
    relic_calls = await _relic_provider_calls(db_session)
    assert relic_calls, (
        "the failing Relic call must still be recorded in provider_calls, even though the "
        "sign-in it was part of never completes"
    )
    assert any(call.rate_limited for call in relic_calls)


async def test_relic_failure_on_personal_stats_rolls_back_the_link_but_records_the_call(
    client: TestClient, fake_upstream: _FakeSteamAndRelic, db_session: AsyncSession
) -> None:
    """`resolve_profile` (the first Relic call) succeeds, so by the time `personal_stats` (the
    second) fails, a `User`/`SteamIdentity`/`ProfileLink` row is already staged on the request's
    session. That staged work must be rolled back wholesale — a sign-in with no rating history is
    not a smaller version of success — and the failing call's `provider_calls` row must survive
    that rollback regardless (T029b).
    """
    fake_upstream.relic_failure_mode = "non_json"
    fake_upstream.relic_calls_before_failure = 1

    response = _sign_in(client, fake_upstream, _HAPPY_STEAM_ID64)

    assert response.status_code < 500, (
        f"a non-JSON Relic body must yield the documented redirect, not a raw error — "
        f"got {response.status_code}: {response.text}"
    )
    assert "Traceback" not in response.text
    assert _error_code(response) == "provider_unavailable"
    assert client.get("/api/me").json()["authenticated"] is False

    identity = await db_session.get(SteamIdentity, _HAPPY_STEAM_ID64)
    assert identity is None, (
        "a Relic failure after the identity row was staged must roll the whole attempt back — "
        "nothing may be left half-signed-in"
    )
    links = await db_session.execute(
        select(ProfileLink).where(ProfileLink.profile_id == int(_HAPPY_PROFILE_ID))
    )
    assert links.scalar_one_or_none() is None

    relic_calls = await _relic_provider_calls(db_session)
    assert len(relic_calls) >= 2, (
        "both the successful resolve_profile call and the failing personal_stats call must be "
        "recorded, despite the second call's own transaction rolling back"
    )
