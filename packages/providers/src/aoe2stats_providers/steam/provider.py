"""`SteamAuthProvider`: Steam OpenID 2.0 sign-in, verified against Steam itself (T026).

research.md §2 is the ground truth this follows: redirect the browser to Steam's *pinned* OpenID
endpoint (`https://steamcommunity.com/openid/login`, never taken from the callback), then — on the
callback — POST every parameter Steam returned back to that same endpoint with `openid.mode`
replaced by `check_authentication`, and require the literal reply `is_valid:true`. Skipping that
round trip makes the callback trivially forgeable: anyone could construct `openid.mode=id_res`
parameters by hand and sign in as anyone. `openid.claimed_id` is then matched against the *exact*
expected pattern (never a substring — a value merely containing a well-formed id must not verify),
and `openid.return_to` is checked against this deployment's own configuration rather than trusted
because the request says so.

`verify()` never raises. Its signature is `SteamId64 | None` with no exception in it (`base.py`'s
`SteamAuthProvider` Protocol docstring): a malformed callback, a rejected assertion, and a Steam
outage all collapse to the same `None`, so a caller can never mistake an exception path — one it
forgot to catch, say — for a successful sign-in.

Built on `SyncBaseProvider` (`packages/providers/src/aoe2stats_providers/base.py`) for the
obligations every provider shares — explicit timeout, the token bucket, retry with backoff on
transient failures, the honest `User-Agent`, a `provider_calls` row per attempt. One obligation it
cannot satisfy through `SyncBaseProvider._request` as written: `check_authentication` is a
form-urlencoded POST body (`application/x-www-form-urlencoded`), and `_request` only offers a JSON
body. `_post_check_authentication` below is therefore a small, purpose-built sibling of `_request`
— same timeout, same token bucket, same retry policy, same `provider_calls` recording, reached
through the inherited attributes rather than duplicated configuration — that speaks form-encoding
instead of JSON and, per `verify`'s contract, swallows every failure into `None`/`False` rather than
raising.

CSRF `state`: `begin(return_to, state)` carries `state` as its own top-level query parameter on the
outbound Steam redirect, satisfying the Protocol's signature and giving an operator something to
grep for in a redirect log. Steam does not echo unrecognised parameters back, so this alone is not
what defends the callback — that is the router's job (T028/T029), binding `state` to the browser's
session server-side before redirecting and consuming it on return. Keeping `return_to` validation a
plain, exact comparison against one fixed, deployment-configured URL (rather than a prefix or
pattern match tolerant of a per-request query suffix) is what makes that split possible: a single
`SteamAuthProvider` is constructed once for the whole deployment, so its configured `return_to`
cannot vary per request, and folding `state` into it would have required exactly that.
"""

from __future__ import annotations

import re
import time
from collections.abc import Mapping
from urllib.parse import urlencode, urlparse

import httpx

from aoe2stats_providers.base import (
    PROVIDER_USER_AGENT,
    RetryPolicy,
    SteamId64,
    SyncBaseProvider,
    SyncProviderCallSink,
    SyncTokenBucket,
)

# Pinned, never taken from the callback (research.md §2: "The endpoint must be discovered or
# pinned to Steam's, never taken from the callback").
STEAM_OPENID_LOGIN_URL = "https://steamcommunity.com/openid/login"

_OPENID_NS = "http://specs.openid.net/auth/2.0"
_IDENTIFIER_SELECT = "http://specs.openid.net/auth/2.0/identifier_select"

# The exact shape `openid.claimed_id` must take — never matched as a substring, so
# "https://steamcommunity.com/openid/id/<17 digits><anything else>" or a value merely containing
# a well-formed id is rejected, not accepted.
_CLAIMED_ID_PATTERN = re.compile(r"\Ahttps://steamcommunity\.com/openid/id/(\d{17})\Z")

_CHECK_AUTHENTICATION_ENDPOINT = "openid/check_authentication"


def _is_rate_limited(status_code: int) -> bool:
    return status_code == 429 or status_code == 403


class SteamAuthProvider(SyncBaseProvider):
    """OpenID 2.0 against Steam (`contracts/providers.md`). The one synchronous `DataProvider`:
    the round trip runs inline in the callback route rather than through the async ingest path.
    """

    def __init__(
        self,
        *,
        client: httpx.Client,
        timeout_seconds: float,
        rate_limiter: SyncTokenBucket,
        return_to: str,
        retry_policy: RetryPolicy | None = None,
        call_sink: SyncProviderCallSink | None = None,
    ) -> None:
        super().__init__(
            provider="steam",
            client=client,
            timeout_seconds=timeout_seconds,
            rate_limiter=rate_limiter,
            call_sink=call_sink,
            retry_policy=retry_policy,
        )
        # This deployment's one true callback URL, fixed for the provider's lifetime. `verify`
        # checks every callback's `openid.return_to` against exactly this — never against
        # whatever a particular caller most recently passed to `begin` (see module docstring).
        self._configured_return_to = return_to

    def begin(self, return_to: str, state: str) -> str:
        """Build the redirect to Steam's `checkid_setup`, pointed at `return_to` (whatever the
        caller asks for; `verify` does not trust it — see the module docstring) and carrying
        `state` as its own query parameter for the router's CSRF binding to log and, later,
        recognise.
        """
        realm = f"{urlparse(return_to).scheme}://{urlparse(return_to).netloc}"
        params = {
            "openid.ns": _OPENID_NS,
            "openid.mode": "checkid_setup",
            "openid.claimed_id": _IDENTIFIER_SELECT,
            "openid.identity": _IDENTIFIER_SELECT,
            "openid.return_to": return_to,
            "openid.realm": realm,
            "state": state,
        }
        return f"{STEAM_OPENID_LOGIN_URL}?{urlencode(params)}"

    def verify(self, callback_params: Mapping[str, str]) -> SteamId64 | None:
        """`check_authentication` round trip, `claimed_id` pattern match, `return_to` check.
        Never raises: any failure — structurally invalid input, a rejected assertion, an
        unreachable Steam — resolves to `None`.
        """
        if callback_params.get("openid.mode") != "id_res":
            return None
        if callback_params.get("openid.return_to") != self._configured_return_to:
            return None

        claimed_id = callback_params.get("openid.claimed_id")
        if claimed_id is None:
            return None
        match = _CLAIMED_ID_PATTERN.match(claimed_id)
        if match is None:
            return None

        if not self._check_authentication(callback_params):
            return None

        # `openid.identity` and `openid.claimed_id` are two views of the same signed assertion
        # (OpenID 2.0 §11) and must agree. This check runs *after* the `check_authentication`
        # round trip above, not instead of it: FR-002 requires that round trip for every
        # assertion, and a tampered `claimed_id` is exactly the input it exists to catch — an
        # early return on shape alone would skip Steam for precisely that case. In the real flow
        # a mismatch also breaks the `check_authentication` signature and Steam rejects it
        # outright (`is_valid:false`), so this is defence in depth once the round trip has
        # already happened, not a substitute for it.
        if callback_params.get("openid.identity") != claimed_id:
            return None

        return match.group(1)

    def _check_authentication(self, callback_params: Mapping[str, str]) -> bool:
        """POST every callback parameter back to Steam with `openid.mode` replaced by
        `check_authentication` (research.md §2), and read the reply's `is_valid:` line.
        """
        body = {**callback_params, "openid.mode": "check_authentication"}
        response = self._post_check_authentication(body)
        if response is None:
            return False
        return _parse_is_valid(response.text)

    def _post_check_authentication(self, body: Mapping[str, str]) -> httpx.Response | None:
        """The form-encoded sibling of `SyncBaseProvider._request` this call needs (see the
        module docstring): same timeout, token bucket, retry policy and `provider_calls`
        recording, reached through the attributes the base class already set up, but a
        form-urlencoded body rather than JSON, and every failure swallowed into `None` rather than
        raised — `verify`'s contract admits no exception.
        """
        for attempt in range(self._retry_policy.max_attempts):
            self._rate_limiter.acquire()
            started = time.monotonic()
            try:
                response = self._client.request(
                    "POST",
                    STEAM_OPENID_LOGIN_URL,
                    data=dict(body),
                    timeout=self._timeout,
                    headers={"User-Agent": PROVIDER_USER_AGENT},
                )
            except httpx.HTTPError:
                self._record(_CHECK_AUTHENTICATION_ENDPOINT, None, started, rate_limited=False)
                if attempt + 1 >= self._retry_policy.max_attempts:
                    return None
                time.sleep(self._retry_policy.delay_seconds(attempt))
                continue

            status_code = response.status_code
            rate_limited = _is_rate_limited(status_code)
            self._record(
                _CHECK_AUTHENTICATION_ENDPOINT, status_code, started, rate_limited=rate_limited
            )

            if rate_limited:
                # `ProviderRateLimited` stops a whole ingest run elsewhere in this codebase; here
                # there is no run to stop, only one sign-in attempt to fail closed on.
                return None
            if status_code >= 500:
                if attempt + 1 >= self._retry_policy.max_attempts:
                    return None
                time.sleep(self._retry_policy.delay_seconds(attempt))
                continue

            return response

        return None


def _parse_is_valid(body: str) -> bool:
    """OpenID 2.0's direct response is line-oriented `key:value` pairs; `is_valid:true` is the
    one line that matters. A body that is not this wire format at all (no such line present)
    parses to `False`, never an exception.
    """
    return any(line.strip() == "is_valid:true" for line in body.splitlines())
