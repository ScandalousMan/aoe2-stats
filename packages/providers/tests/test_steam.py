"""Contract test for `SteamAuthProvider` (T019) against the frozen fixtures in
`packages/providers/fixtures/steam/` — the shared machinery this exercises is already proven by
`test_provider_base.py`; this file is about `SteamAuthProvider`'s own logic on top of it.

Written before `packages/providers/src/aoe2stats_providers/steam/provider.py` existed (T026), so
every test below carried `@pytest.mark.xfail(strict=True, ...)` until that adapter landed. T026 has
since landed and the markers are gone: `strict=True` is what forced their removal, by turning the
run red the moment the tests began to pass. The import of `aoe2stats_providers.steam.provider`
still lives inside `_provider()` (and the one test that builds a `SteamAuthProvider` directly)
rather than at module scope, which is worth keeping — a module-scope `ModuleNotFoundError` aborts
the *entire* workspace suite's collection rather than failing one test (`tool.pytest.
ini_options.testpaths` in the root `pyproject.toml` collects this file workspace-wide). This test
defines the contract T026 must satisfy, not a bug to work around.

What `contracts/providers.md` and research.md §2 require, each covered below:

- `check_authentication` returning `is_valid:true` resolves to the caller's Steam id
  (`check_authentication_valid.txt` — hand-written from the OpenID 2.0 wire format, never
  captured live; see `fixtures/steam/README.md`).
- `is_valid:false` (`check_authentication_invalid.txt` — a real, captured rejection) resolves to
  `None`.
- `openid.claimed_id` is matched against the exact expected pattern
  (`https://steamcommunity.com/openid/id/<17 digits>`), never by substring: a value that merely
  *contains* a well-formed id, or that carries extra trailing/leading characters, must not verify.
- `openid.return_to` is validated against the provider's own configuration, not merely echoed back
  — a callback claiming a different `return_to` than the one this deployment is configured for
  must not verify even when Steam itself says `is_valid:true`.
- `verify` never raises for an invalid assertion — malformed input, a Steam outage, or a rejected
  check all resolve to `None`, per the Protocol docstring in `base.py` ("so that a caller cannot
  mistake an exception path for success").

Every request goes through `httpx.MockTransport`, replaying the frozen fixture bytes rather than
touching the network — constitution III, and `tests/conftest.py`'s socket guard would refuse a
real connection regardless.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest

from aoe2stats_providers.base import RetryPolicy, SyncTokenBucket

if TYPE_CHECKING:
    # Type-checking only: mypy needs the name, but nothing here may import the module at
    # collection time — see `_provider()` below, where the real (runtime) import lives.
    from aoe2stats_providers.steam.provider import SteamAuthProvider

# Fractions of a millisecond, exactly like `test_provider_base.py`'s `FAST_RETRY`: keeps the one
# test below that exhausts retries (a simulated Steam outage) fast without patching `time.sleep`.
FAST_RETRY = RetryPolicy(
    max_attempts=3, base_delay_seconds=0.001, max_delay_seconds=0.002, jitter_seconds=0.0
)

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "steam"

VALID_ASSERTION = (_FIXTURES / "check_authentication_valid.txt").read_text(encoding="utf-8")
INVALID_ASSERTION = (_FIXTURES / "check_authentication_invalid.txt").read_text(encoding="utf-8")

RETURN_TO = "https://example.test/api/auth/steam/callback"
CLAIMED_ID = "https://steamcommunity.com/openid/id/76561197984749679"

# A realistic callback query string, shaped exactly like the one `contract_sources.py` POSTs back
# to Steam for `check_authentication` (research.md §2: "POST every returned parameter back to
# Steam ... with `openid.mode` replaced").
BASE_CALLBACK_PARAMS: dict[str, str] = {
    "openid.ns": "http://specs.openid.net/auth/2.0",
    "openid.mode": "id_res",
    "openid.op_endpoint": "https://steamcommunity.com/openid/login",
    "openid.claimed_id": CLAIMED_ID,
    "openid.identity": CLAIMED_ID,
    "openid.return_to": RETURN_TO,
    "openid.response_nonce": "2026-08-19T21:00:00Zcontract-test-probe",
    "openid.assoc_handle": "some-handle",
    "openid.signed": "signed,op_endpoint,claimed_id,identity,return_to,response_nonce,assoc_handle",
    "openid.sig": "not-a-real-signature",
}


def _callback_params(**overrides: str) -> dict[str, str]:
    return {**BASE_CALLBACK_PARAMS, **overrides}


def _provider(
    handler: Callable[[httpx.Request], httpx.Response], *, return_to: str = RETURN_TO
) -> SteamAuthProvider:
    """A `SteamAuthProvider` wired to `httpx.MockTransport`, never a live socket.

    Imports `SteamAuthProvider` here, at call time, rather than at module scope: this is the one
    place every test below (bar one) reaches the not-yet-existent T026 module through, so this is
    where the resulting `ModuleNotFoundError` is meant to surface — inside the test call, where
    `strict=True` xfail turns it into an expected failure, not during collection, where it would
    abort the whole workspace suite.
    """
    from aoe2stats_providers.steam.provider import SteamAuthProvider

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return SteamAuthProvider(
        client=client,
        timeout_seconds=5.0,
        rate_limiter=SyncTokenBucket(1000.0),
        return_to=return_to,
        retry_policy=FAST_RETRY,
    )


def _responds_with(body: str) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body)

    return handler


# --- `check_authentication` — is_valid:true / is_valid:false ------------------------------------


def test_a_valid_assertion_resolves_to_the_claimed_steam_id() -> None:
    provider = _provider(_responds_with(VALID_ASSERTION))

    steam_id = provider.verify(_callback_params())

    assert steam_id == "76561197984749679"


def test_check_authentication_is_posted_with_mode_replaced() -> None:
    """research.md §2: every returned parameter is POSTed back to Steam with `openid.mode`
    replaced by `check_authentication` — never the original `id_res`, which would just echo the
    callback back at Steam without ever asking it to confirm anything.
    """
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["body"] = request.content.decode()
        return httpx.Response(200, text=VALID_ASSERTION)

    provider = _provider(handler)

    provider.verify(_callback_params())

    assert seen["method"] == "POST"
    body = str(seen["body"])
    assert "openid.mode=check_authentication" in body
    assert "id_res" not in body


def test_a_rejected_assertion_from_a_never_issued_callback_resolves_to_none() -> None:
    """`check_authentication_invalid.txt`: a real, captured Steam rejection of a syntactically
    well-formed but never-issued assertion — the same rejection a replayed or forged callback
    produces (quickstart scenario 1).
    """
    provider = _provider(_responds_with(INVALID_ASSERTION))

    steam_id = provider.verify(_callback_params())

    assert steam_id is None


# --- `claimed_id` — exact pattern, never substring -----------------------------------------------


@pytest.mark.parametrize(
    "claimed_id",
    [
        # One character altered — quickstart scenario 1's tampering case.
        "https://steamcommunity.com/openid/id/76561197984749670",
        # A well-formed id embedded inside something larger: substring matching would wrongly
        # accept both of these.
        "https://steamcommunity.com/openid/id/76561197984749679/extra",
        "xhttps://steamcommunity.com/openid/id/76561197984749679",
        # Wrong digit count.
        "https://steamcommunity.com/openid/id/123",
        # Wrong host entirely.
        "https://attacker.example/openid/id/76561197984749679",
        # Not even a URL.
        "76561197984749679",
    ],
)
def test_claimed_id_must_match_the_exact_pattern_not_a_substring(claimed_id: str) -> None:
    provider = _provider(_responds_with(VALID_ASSERTION))

    steam_id = provider.verify(_callback_params(**{"openid.claimed_id": claimed_id}))

    assert steam_id is None


# --- `return_to` — validated against configuration, not merely echoed ---------------------------


def test_return_to_matching_configuration_is_accepted() -> None:
    provider = _provider(_responds_with(VALID_ASSERTION), return_to=RETURN_TO)

    steam_id = provider.verify(_callback_params(**{"openid.return_to": RETURN_TO}))

    assert steam_id == "76561197984749679"


def test_return_to_not_matching_configuration_is_rejected_even_when_steam_says_valid() -> None:
    """A callback asserting a different `return_to` than the one this deployment is configured
    for must never verify, even if Steam's own `check_authentication` says `is_valid:true` — the
    check is against *our* configuration (research.md §2), not a re-statement of what the
    request already claimed.
    """
    provider = _provider(_responds_with(VALID_ASSERTION), return_to=RETURN_TO)

    steam_id = provider.verify(
        _callback_params(**{"openid.return_to": "https://attacker.example/callback"})
    )

    assert steam_id is None


def test_return_to_is_configured_once_and_not_taken_from_begin() -> None:
    """`begin(return_to, state)` builds the outbound redirect; `verify` validates the callback
    against the provider's *own* configuration (the deployment's one true callback URL), not
    whatever a caller most recently passed to `begin` — two different callers racing `begin` must
    not be able to shift what `verify` accepts.
    """
    provider = _provider(_responds_with(VALID_ASSERTION), return_to=RETURN_TO)

    redirect_url = provider.begin(return_to="https://attacker.example/callback", state="a-state")

    assert "attacker.example" in redirect_url  # begin() does encode what it was asked to send
    # ... but verify() still only accepts the configured return_to, regardless of what begin() saw.
    steam_id = provider.verify(_callback_params(**{"openid.return_to": RETURN_TO}))
    assert steam_id == "76561197984749679"


# --- `verify` never raises for an invalid assertion ----------------------------------------------


def test_verify_returns_none_rather_than_raising_on_missing_parameters() -> None:
    provider = _provider(_responds_with(INVALID_ASSERTION))

    steam_id = provider.verify({})

    assert steam_id is None


def test_verify_returns_none_rather_than_raising_on_a_malformed_reply_body() -> None:
    """Neither `ns:` nor `is_valid:` present at all — not the shape OpenID 2.0 promises."""
    provider = _provider(_responds_with("not the openid wire format at all"))

    steam_id = provider.verify(_callback_params())

    assert steam_id is None


def test_verify_returns_none_when_steam_itself_is_unreachable() -> None:
    """A source outage is not the caller's problem to catch: `verify`'s signature is `SteamId64 |
    None`, with no exception in it, per `base.py`'s `SteamAuthProvider` Protocol docstring.
    """
    from aoe2stats_providers.steam.provider import SteamAuthProvider

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    provider = SteamAuthProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        timeout_seconds=5.0,
        rate_limiter=SyncTokenBucket(1000.0),
        return_to=RETURN_TO,
        retry_policy=FAST_RETRY,
    )

    steam_id = provider.verify(_callback_params())

    assert steam_id is None


def test_begin_returns_a_url_pointed_at_steams_pinned_openid_endpoint() -> None:
    provider = _provider(_responds_with(VALID_ASSERTION))

    redirect_url = provider.begin(return_to=RETURN_TO, state="csrf-state-value")

    assert redirect_url.startswith("https://steamcommunity.com/openid/login")
    assert "openid.mode=checkid_setup" in redirect_url
    assert "csrf-state-value" in redirect_url
