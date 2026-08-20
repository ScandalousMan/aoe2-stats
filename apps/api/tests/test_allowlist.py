"""Integration test for the closed-beta allowlist (T022, FR-005).

FR-005: "System MUST restrict account creation to an allowlist during the closed beta, and MUST
tell a non-allowlisted visitor why they cannot proceed." `contracts/http-api.md` names the failure
code this produces — `not_allowlisted` — among `GET /api/auth/steam/callback`'s documented outcomes,
and `data-model.md`'s `users.allowlisted_at` records the opposite case ("Null means the closed beta
refuses them").

The allowlist can only be evaluated once a Steam id is known, which means it sits *after* Steam's
own verification in the callback handler and *before* anything is written for the visitor. That
ordering is the actual thing this test proves: not merely that the response carries the right error
code, but that no `users` or `steam_identities` row survives a rejected visitor. A `not_allowlisted`
response next to a freshly created account row would be a bug this assertion alone would catch and
a bare status-code check would not.

**T030a: this test now reaches the callback the way a real visitor does.** An earlier version
posted straight to `GET /api/auth/steam/callback` with no prior `/start` call, so it carried no
CSRF `state` cookie and could never reach the real, post-verification allowlist gate — which is
exactly why `auth.py` grew a second, CSRF-failure-only allowlist check that read `openid.
claimed_id` unverified off the query string. That check was an enumeration oracle over closed-beta
membership (T030a) and has been deleted; this test now completes a genuine `GET /api/auth/steam/
start` first, exactly as `test_auth_flow.py`'s `_begin_sign_in` does, so it carries a valid CSRF
`state` into the callback and exercises the one real allowlist gate that survives
`SteamAuthProvider.verify()`. Steam's own `check_authentication` endpoint is faked at the
`httpx.Client.send` boundary (`packages/providers/src/aoe2stats_providers/base.py`) with the
frozen fixture T012 captured, the same mechanism `test_auth_flow.py`'s `_FakeSteamAndRelic` uses —
network is unavailable here by construction otherwise (`tests/conftest.py`, T004; constitution
III). Relic is never reached: the allowlist gate raises before `resolve_profile` is ever called.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api.settings import get_settings
from aoe2stats_storage.models import SteamIdentity, User

# T030 landed: the auth router now enforces the allowlist, and this test passes for real. The
# `xfail(strict=True)` this module carried while T026-T030 were open is gone — see the module
# docstring's "Current failure mode" paragraph for the history, kept for context even though it no
# longer describes the present.
pytestmark = [pytest.mark.usefixtures("environment")]

_FIXTURES = Path(__file__).resolve().parents[3] / "packages" / "providers" / "fixtures"
_STEAM_CHECK_AUTH_VALID = (_FIXTURES / "steam" / "check_authentication_valid.txt").read_text()

_START_PATH = "/api/auth/steam/start"
_CALLBACK_PATH = "/api/auth/steam/callback"

#: A syntactically valid Steam64 id (18 digits, the `7656119` prefix real ones carry) that the
#: allowlist configured below deliberately excludes.
_NOT_ALLOWLISTED_STEAM_ID64 = "76561198000009999"

#: Two ids that *are* allowlisted, so the test exercises "a visitor absent from a real, non-empty
#: list" (FR-005's actual case) rather than "an allowlist so empty it refuses everyone", which
#: `required_env`'s default `BETA_ALLOWLIST_STEAM_IDS=""` already does for the wrong reason.
_ALLOWLISTED_STEAM_IDS = "76561198000000001,76561198000000002"


@pytest.fixture
def _allowlist_without_visitor(
    monkeypatch: pytest.MonkeyPatch,
    required_env: dict[str, str],
    environment: None,
) -> None:
    """Narrow `BETA_ALLOWLIST_STEAM_IDS` to ids that exclude `_NOT_ALLOWLISTED_STEAM_ID64`.

    Requests `environment` explicitly (beyond the module-level `usefixtures` marker) so this
    fixture's own `monkeypatch.setenv` is guaranteed to run *after* `environment`'s and so is not
    clobbered back to the empty default it sets.
    """
    assert _NOT_ALLOWLISTED_STEAM_ID64 not in _ALLOWLISTED_STEAM_IDS.split(",")
    assert required_env["BETA_ALLOWLIST_STEAM_IDS"] == "", (
        "required_env's default is asserted empty here only to document why this fixture "
        "overrides it — the empty default would refuse every visitor, including an allowlisted "
        "one, which is not the case FR-005 describes"
    )
    monkeypatch.setenv("BETA_ALLOWLIST_STEAM_IDS", _ALLOWLISTED_STEAM_IDS)
    get_settings.cache_clear()


def _begin_sign_in(client: TestClient) -> tuple[str, dict[str, str]]:
    """`GET /api/auth/steam/start`, returning the exact `openid.return_to` Steam would echo back
    and its own query parameters — the CSRF `state` a real visitor's browser carries into the
    callback (`test_auth_flow.py`'s helper of the same name; module docstring, T030a). Without
    this, a callback carries no valid `state` and never reaches the real, post-verification
    allowlist gate this test means to exercise.
    """
    response = client.get(_START_PATH, follow_redirects=False)
    assert response.status_code == 302, (
        f"GET /api/auth/steam/start did not redirect to Steam — got {response.status_code}: "
        f"{response.text}"
    )
    location = response.headers["location"]
    parsed = urlsplit(location)
    assert parsed.hostname == "steamcommunity.com", f"expected a redirect to Steam, got {location}"
    start_params = dict(parse_qsl(parsed.query))
    return_to = start_params["openid.return_to"]
    return_to_query = dict(parse_qsl(urlsplit(return_to).query))
    return return_to, return_to_query


def _callback_params(steam_id64: str, *, return_to: str) -> dict[str, str]:
    """A well-formed OpenID 2.0 `id_res` response naming `steam_id64` in `openid.claimed_id`, the
    field `SteamAuthProvider.verify` reads (`contracts/providers.md`), carrying the exact
    `return_to` this deployment's own `/start` minted (`_begin_sign_in`) so `verify()`'s
    `openid.return_to` check passes. The signature and nonce are placeholders: `fake_steam` below
    always answers `is_valid:true`, so nothing in this test relies on Steam actually validating
    them (see the module docstring).
    """
    claimed_id = f"https://steamcommunity.com/openid/id/{steam_id64}"
    return {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "id_res",
        "openid.op_endpoint": "https://steamcommunity.com/openid/login",
        "openid.claimed_id": claimed_id,
        "openid.identity": claimed_id,
        "openid.return_to": return_to,
        "openid.response_nonce": "2026-08-20T00:00:00Ztest-nonce",
        "openid.assoc_handle": "test-assoc-handle",
        "openid.signed": "op_endpoint,claimed_id,identity,return_to,response_nonce,assoc_handle",
        "openid.sig": "not-a-real-signature",
    }


@pytest.fixture
def fake_steam(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fakes Steam's `check_authentication` endpoint at the `httpx.Client.send` boundary
    (`packages/providers/src/aoe2stats_providers/base.py`), always answering `is_valid:true` for
    any request addressed to `steamcommunity.com` — the frozen fixture T012 captured. This test's
    callback carries a genuine CSRF state and a syntactically well-formed assertion (module
    docstring, T030a) and needs `SteamAuthProvider.verify()` to actually resolve a Steam id, so the
    real, post-verification allowlist gate is what gets exercised, not Steam's own verification
    (`test_auth_flow.py` covers that against the same fixture). Anything not addressed to Steam
    passes through untouched, in particular `TestClient`'s own traffic to the FastAPI app, which is
    itself an `httpx.Client` under the hood.
    """
    original_send = httpx.Client.send

    def _send(self: httpx.Client, request: httpx.Request, **kwargs: Any) -> httpx.Response:
        if request.url.host == "steamcommunity.com":
            return httpx.Response(200, text=_STEAM_CHECK_AUTH_VALID, request=request)
        return original_send(self, request, **kwargs)

    monkeypatch.setattr(httpx.Client, "send", _send)


async def test_non_allowlisted_visitor_is_refused_and_creates_no_account(
    client: TestClient,
    db_session: AsyncSession,
    _allowlist_without_visitor: None,
    fake_steam: None,
) -> None:
    return_to, return_to_query = _begin_sign_in(client)
    params = {
        **return_to_query,
        **_callback_params(_NOT_ALLOWLISTED_STEAM_ID64, return_to=return_to),
    }
    response = client.get(_CALLBACK_PATH, params=params, follow_redirects=False)

    body = response.json()
    # FR-005: told why, not merely refused — `message` is the explanation, `code` is what the
    # front end (T036) branches on.
    assert body["error"]["code"] == "not_allowlisted"
    assert body["error"]["message"]

    # No session was established: the bootstrap call sees this visitor exactly as it would see
    # someone who never attempted to sign in.
    me = client.get("/api/me")
    assert me.status_code == 200
    assert me.json() == {"authenticated": False}

    # The assertion FR-005 actually turns on: rejection precedes account creation. A
    # `not_allowlisted` body next to a freshly written `users` row would still pass every
    # assertion above while admitting the closed beta's first unwanted account.
    users = (await db_session.execute(select(User))).scalars().all()
    assert users == []
    steam_identities = (await db_session.execute(select(SteamIdentity))).scalars().all()
    assert steam_identities == []
