"""Process-wide network resources: the one `httpx.Client`/`httpx.AsyncClient` pair a caller
outside this package shares across calls.

`contracts/http-api.md`'s sibling document, `contracts/providers.md`, opens with the rule this
module exists to make possible in code: "`apps/*` and `packages/core` depend on these Protocols
and never on a concrete provider, a URL **or an HTTP client**." `tests/architecture/
test_import_graph.py` enforces the network-boundary half of that (constitution III) by scanning
every file under `apps/*/src` and `packages/core/src` for a direct `httpx` import — so the one
place left to build the client object every synchronous or asynchronous provider's constructor
requires (`SteamAuthProvider(client=...)`, `RelicProfileProvider(client=...)`) is here, inside
`packages/providers`, where `httpx` is already the one place a network client is allowed to live.

Deliberately minimal: this module builds *resources*, never a provider. `SteamAuthProvider`,
`RelicProfileProvider` and every other concrete provider still take their `return_to`, `call_sink`
and other per-call arguments from whoever constructs them (`apps/api/src/aoe2stats_api/routers/
auth.py`, later the ingester) — splitting it this way is what lets the expensive, connection-
pooled objects (the client, the token bucket) be built once per process while the thin provider
wrapper around them stays cheap to rebuild per request, per `SteamAuthProvider`'s own module
docstring on why `return_to` cannot be a single process-wide constant.

**`build_companion_breaker` (MJ-3 remediation).** The process-lifetime `CircuitBreaker`
`CompanionEnrichmentProvider` requires (its constructor no longer defaults `breaker` to `None`,
`companion/provider.py`'s own module docstring) is the third such process-lifetime resource, beside
the client and the token bucket `build_async_client_resources` already builds here — it used to be
built directly in `apps/api/src/aoe2stats_api/routers/players.py`, which forced that module to
import `CircuitBreaker`/`build_circuit_breaker` from the concrete `companion` module instead of
from this one, the resource-wiring boundary that exists for exactly this. `CircuitBreaker` itself
stays defined in `companion/provider.py` — it is companion-specific machinery, not shared across
providers the way `TokenBucket` is — this module only re-exports the constructor a caller wiring a
`CompanionEnrichmentProvider` needs, alongside the client and rate limiter it already re-exports.
"""

from __future__ import annotations

import httpx

from aoe2stats_providers.base import SyncTokenBucket, TokenBucket
from aoe2stats_providers.companion.provider import CircuitBreaker, build_circuit_breaker

__all__ = [
    "CircuitBreaker",
    "build_async_client_resources",
    "build_companion_breaker",
    "build_sync_client_resources",
]


def build_sync_client_resources(rate_per_second: float) -> tuple[httpx.Client, SyncTokenBucket]:
    """One `httpx.Client` and one `SyncTokenBucket` at `rate_per_second`, for `SteamAuthProvider`
    or any other synchronous provider a caller builds against them. A fresh pair every call —
    callers that want a single process-wide pair (the common case) build one and hold onto it."""
    return httpx.Client(), SyncTokenBucket(rate_per_second)


def build_async_client_resources(rate_per_second: float) -> tuple[httpx.AsyncClient, TokenBucket]:
    """The asynchronous twin of `build_sync_client_resources`, for `RelicProfileProvider` and
    every other async provider."""
    return httpx.AsyncClient(), TokenBucket(rate_per_second)


def build_companion_breaker() -> CircuitBreaker:
    """A fresh, closed `CircuitBreaker` at `companion/provider.py`'s own threshold and cooldown —
    the resource a caller wiring a process-lifetime `CompanionEnrichmentProvider` builds once and
    passes to every request's own, otherwise disposable, provider instance (module docstring's
    "build_companion_breaker" note). A fresh pair every call, exactly like the two functions
    above — callers that want a single process-wide breaker build one and hold onto it.
    """
    return build_circuit_breaker()
