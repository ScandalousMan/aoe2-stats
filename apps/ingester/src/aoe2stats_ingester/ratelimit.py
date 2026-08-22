"""The ingester-side rate-limiting policy for the `aoe.ms` replay endpoint (T052).

`packages/providers/src/aoe2stats_providers/base.py` already builds the machinery every provider
shares: `TokenBucket` (a token bucket every request passes through), `RetryPolicy` (exponential
backoff with jitter, for the transient failures only), and `AsyncBaseProvider._request`, which
raises `ProviderRateLimited` on a 429 or an unexpected 403 rather than retrying it. This module does
not duplicate any of that — it configures those primitives specifically for the replay endpoint, and
adds the one piece `base.py` deliberately leaves to a caller: what happens *after*
`ProviderRateLimited` is raised.

Per skill `aoe2-data-sources` ("At most 1 request per second to the replay endpoint, serially, with
jitter and backoff... A 429 or an unexpected 403 from a primary source stops the whole run and
alerts. It does not skip one item and continue.") and `contracts/providers.md`
("`ProviderRateLimited` stopping the entire run, rather than that one capture, is deliberate. The
budget is 21 days; there is always tomorrow."):

- `build_aoems_rate_limiter` — the token bucket at `AOEMS_MAX_REQUESTS_PER_SECOND`, capped to
  exactly one outstanding request regardless of the configured rate, which is what makes the calls
  serial rather than merely paced.
- `build_aoems_retry_policy` — the backoff-with-jitter policy for the transient failures
  (`AsyncBaseProvider._request` never retries a 429/403 through this policy; only timeouts,
  connection errors and 5xx reach it).
- `raise_rate_limited_alert` — the severity-2 `rate_limited` alert (`AlertKind.RATE_LIMITED` in
  `packages/storage/src/aoe2stats_storage/models.py`, named here as the plain string
  `"rate_limited"` rather than imported: `packages/core/src/aoe2stats_core/alerting.py`'s own
  `AlertSink.write` takes a plain `str`, `apps/ingester` needs no dependency on `aoe2stats_storage`
  merely to spell a string it hands to `raise_alert`, and `packages/core/tests/test_alerting.py`
  already establishes this as the pattern every alert producer follows). Severity 2 and not 1:
  being throttled costs a cycle, and against a 21-day capture budget there is always tomorrow — the
  nightly alert audit (T061) fails the build only on an unacknowledged severity-1 row, and a source
  that is merely being polite must not stop the CI that watches for actual loss.
- `drain_with_rate_limit_guard` — the reusable shape of "stop the whole run, not just the one
  item" itself: a plain, serial iteration that calls `handle_item` for each item in turn and, the
  moment one raises `ProviderRateLimited`, raises the alert above and returns immediately *without*
  advancing to the next item. `CaptureStage` (T055/T056, `capture.py`) is the caller this exists
  for — its own claim-fetch-classify-persist cycle hands each claimed capture to this function
  rather than writing its own catch-and-stop logic, so the rule that a rate limit interrupts the
  drain (never the one capture it fired on) lives in exactly one place.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Iterable, Mapping
from typing import Any

from aoe2stats_core.alerting import AlertSink, raise_alert
from aoe2stats_providers.base import ProviderRateLimited, RetryPolicy, TokenBucket

#: `alerts.kind` for this producer. See the module docstring for why this is a plain string rather
#: than `aoe2stats_storage.models.AlertKind.RATE_LIMITED` — the two are required to agree, and
#: `packages/storage/tests` is what keeps the enum's value pinned to this exact spelling.
RATE_LIMITED_ALERT_KIND = "rate_limited"

#: Severity 2, never 1 — see the module docstring's third bullet for why.
RATE_LIMITED_ALERT_SEVERITY = 2

#: The token bucket's burst allowance is fixed at exactly one outstanding request, independent of
#: whatever `AOEMS_MAX_REQUESTS_PER_SECOND` is configured to. `TokenBucket`'s own default capacity
#: (`max(rate_per_second, 1.0)`) already comes out to `1.0` at the documented rate of 1 req/s, but
#: deriving it from the rate would make "serially" a coincidence of today's number rather than a
#: standing rule: a future change to the configured rate must never silently relax the burst
#: ceiling along with the pace.
_SERIAL_CAPACITY = 1.0


def build_aoems_rate_limiter(requests_per_second: float) -> TokenBucket:
    """The token bucket every request to `aoe.ms`'s replay endpoint passes through
    (`AsyncBaseProvider._request`, `base.py`), configured from `AOEMS_MAX_REQUESTS_PER_SECOND`.

    Reuses `TokenBucket` rather than a second implementation: `AoemsReplayProvider` (T049) already
    takes a `rate_limiter: TokenBucket` constructor argument and passes every request through it
    before it is sent, so wiring the replay endpoint's policy is exactly this one call, made once
    per process and held onto by whichever caller constructs the provider (the same pattern
    `packages/providers/src/aoe2stats_providers/wiring.py` already uses for Steam and Relic).
    """
    return TokenBucket(requests_per_second, capacity=_SERIAL_CAPACITY)


def build_aoems_retry_policy() -> RetryPolicy:
    """The backoff-with-jitter policy for `aoe.ms`, for `AoemsReplayProvider`'s own
    `retry_policy` constructor argument.

    `RetryPolicy`'s defaults (`base.py`) already are exponential backoff with jitter, applied only
    to the transient failures a 429/403 never reaches — exactly what the skill asks for, so this is
    a thin, named factory rather than a second policy: a future aoe.ms-specific tuning (a slower
    ceiling, a wider jitter window) then has exactly one place to change, without every call site
    that wants "the aoe.ms backoff policy" needing to know what `RetryPolicy()`'s bare defaults
    happen to be today.
    """
    return RetryPolicy()


def _rate_limited_alert_detail(error: ProviderRateLimited) -> Mapping[str, Any]:
    return {
        "provider": error.provider,
        "endpoint": error.endpoint,
        "status_code": error.status_code,
        "retry_after_seconds": error.retry_after_seconds,
    }


async def raise_rate_limited_alert(
    sink: AlertSink,
    error: ProviderRateLimited,
    *,
    run_id: uuid.UUID | None,
) -> None:
    """Turn a caught `ProviderRateLimited` into the one severity-2 `rate_limited` alert row the
    skill and `contracts/providers.md` require, through `raise_alert` (T014a).

    Deliberately raises nothing back: this function's entire job is the side effect of the alert
    row existing. Whether iteration actually stops is `drain_with_rate_limit_guard`'s job (or, for
    a caller with its own loop, that caller's) — kept separate so a caller that already holds the
    exception and already knows it must stop is not forced to catch a second one this function
    would otherwise re-raise for no reason.
    """
    await raise_alert(
        sink,
        RATE_LIMITED_ALERT_KIND,
        RATE_LIMITED_ALERT_SEVERITY,
        _rate_limited_alert_detail(error),
        run_id=run_id,
    )


async def drain_with_rate_limit_guard[T](
    items: Iterable[T],
    handle_item: Callable[[T], Awaitable[None]],
    *,
    sink: AlertSink,
    run_id: uuid.UUID | None,
) -> bool:
    """Call `handle_item` for each of `items`, one at a time and never concurrently, until either
    every item has been handled or one raises `ProviderRateLimited` — at which point this stops
    immediately, alerts once, and returns without touching any further item.

    Returns `True` when a rate limit interrupted the drain, `False` when every item was handled (or
    `items` was empty). The caller (`CaptureStage`, T055/T056) uses the return value to decide
    whether its own `Stage.__call__` should report the run as having stopped early; it does not need
    to inspect `ProviderRateLimited` itself, since by the time this returns the alert has already
    been written and the exception has already been swallowed here — the rule is enforced once, in
    this one function, rather than re-implemented at every call site that drains a queue against
    this provider.

    Serial by construction: the `for` loop below awaits `handle_item` to completion before ever
    looking at the next item, exactly as `TokenBucket`'s fixed burst-of-one capacity keeps the
    underlying HTTP calls serial too (`build_aoems_rate_limiter`) — two independent guarantees of
    the same "serially" rule from the skill, neither able to compensate for a regression in the
    other.
    """
    for item in items:
        try:
            await handle_item(item)
        except ProviderRateLimited as error:
            await raise_rate_limited_alert(sink, error, run_id=run_id)
            return True
    return False
