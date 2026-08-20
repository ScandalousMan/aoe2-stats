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

This test deliberately does **not** need `SteamAuthProvider.verify` to perform a genuine
`check_authentication` round trip. FR-005 gates on the allowlist once a steam id is known, not on
Steam's own verification (T019 and T021 cover that, against frozen fixtures); network is unavailable
here by construction anyway (`tests/conftest.py`, T004; constitution III). The callback params below
are a syntactically well-formed OpenID 2.0 `id_res` response naming a steam id that is deliberately
absent from the allowlist configured for this test.

**Current failure mode.** Nothing under `apps/api/src/aoe2stats_api/routers/auth.py` exists yet
(T026-T030 are all still open): `GET /api/auth/steam/callback` is an unmatched route, and `app.py`'s
own `HTTPException` handler answers it with the single error envelope carrying `code: "not_found"`.
The first assertion below is what turns that into an honest failure — `not_found` where
`not_allowlisted` is expected — rather than a `KeyError` on a body shaped some other way. This is
the right reason for this test to be red: the allowlist enforcement (T030), and indeed the whole
sign-in flow it depends on (T026-T029), have not been built yet.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api.settings import get_settings
from aoe2stats_storage.models import SteamIdentity, User

# Every test in this file is expected to fail for exactly one reason — the auth router (T026-T030)
# does not exist yet — until it does. `strict=True` is what makes that honest: the moment those
# tasks land and the test starts passing, `strict=True` turns the *run* red instead of letting a
# stale xfail hide it, which is the whole point of marking this test failing rather than skipping
# it. Do not drop `strict=True`.
pytestmark = [
    pytest.mark.usefixtures("environment"),
    pytest.mark.xfail(
        strict=True,
        reason=(
            "the auth router (T026-T030) is not implemented yet, not this test-first task (T022)"
        ),
    ),
]

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


def _callback_params(steam_id64: str, *, public_base_url: str) -> dict[str, str]:
    """A well-formed OpenID 2.0 `id_res` response naming `steam_id64` in `openid.claimed_id`, the
    field `SteamAuthProvider.verify` reads (`contracts/providers.md`). The signature and nonce are
    placeholders: nothing in this test relies on `check_authentication` actually validating them
    (see the module docstring).
    """
    claimed_id = f"https://steamcommunity.com/openid/id/{steam_id64}"
    return {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "id_res",
        "openid.op_endpoint": "https://steamcommunity.com/openid/login",
        "openid.claimed_id": claimed_id,
        "openid.identity": claimed_id,
        "openid.return_to": f"{public_base_url}/api/auth/steam/callback",
        "openid.response_nonce": "2026-08-20T00:00:00Ztest-nonce",
        "openid.assoc_handle": "test-assoc-handle",
        "openid.signed": "op_endpoint,claimed_id,identity,return_to,response_nonce,assoc_handle",
        "openid.sig": "not-a-real-signature",
    }


async def test_non_allowlisted_visitor_is_refused_and_creates_no_account(
    client: TestClient,
    db_session: AsyncSession,
    required_env: dict[str, str],
    _allowlist_without_visitor: None,
) -> None:
    response = client.get(
        "/api/auth/steam/callback",
        params=_callback_params(
            _NOT_ALLOWLISTED_STEAM_ID64, public_base_url=required_env["PUBLIC_BASE_URL"]
        ),
        follow_redirects=False,
    )

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
