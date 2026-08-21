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
"""

from __future__ import annotations

import httpx

from aoe2stats_providers.base import SyncTokenBucket, TokenBucket


def build_sync_client_resources(rate_per_second: float) -> tuple[httpx.Client, SyncTokenBucket]:
    """One `httpx.Client` and one `SyncTokenBucket` at `rate_per_second`, for `SteamAuthProvider`
    or any other synchronous provider a caller builds against them. A fresh pair every call —
    callers that want a single process-wide pair (the common case) build one and hold onto it."""
    return httpx.Client(), SyncTokenBucket(rate_per_second)


def build_async_client_resources(rate_per_second: float) -> tuple[httpx.AsyncClient, TokenBucket]:
    """The asynchronous twin of `build_sync_client_resources`, for `RelicProfileProvider` and
    every other async provider."""
    return httpx.AsyncClient(), TokenBucket(rate_per_second)
