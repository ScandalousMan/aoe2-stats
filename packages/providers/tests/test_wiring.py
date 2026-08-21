"""`aoe2stats_providers.wiring` — the process-wide `httpx.Client`/`httpx.AsyncClient` resource
builders that let `apps/api` construct a provider without ever importing `httpx` itself
(`tests/architecture/test_import_graph.py`'s constitution-III guard; `contracts/providers.md`:
"apps/* ... never [depends] on ... an HTTP client").
"""

from __future__ import annotations

import httpx

from aoe2stats_providers.base import SyncTokenBucket, TokenBucket
from aoe2stats_providers.wiring import build_async_client_resources, build_sync_client_resources


def test_build_sync_client_resources_returns_a_client_and_a_rate_limiter() -> None:
    client, rate_limiter = build_sync_client_resources(5.0)

    assert isinstance(client, httpx.Client)
    assert isinstance(rate_limiter, SyncTokenBucket)

    client.close()


async def test_build_async_client_resources_returns_a_client_and_a_rate_limiter() -> None:
    client, rate_limiter = build_async_client_resources(5.0)

    assert isinstance(client, httpx.AsyncClient)
    assert isinstance(rate_limiter, TokenBucket)

    await client.aclose()
