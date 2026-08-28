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


# --- follow_redirects (2026-08-28 incident) --------------------------------------------------
#
# `aoe.ms/replay/` moved permanently behind a 301 to `api.ageofempires.com` (`docs/data-sources.md`
# §2) while `httpx`'s own default (`follow_redirects=False`) reached production unchanged: every
# capture read the 301 itself as an unnamed status and raised `ProviderUnavailable`, forever, rather
# than following it to the 200 the source still answers with. These two assertions target that
# default directly, at the exact call this project's shared client is built from — see
# `AoemsReplayProvider.fetch_replay` in `test_aoems.py` for the behavioural regression test this
# setting exists to fix.


def test_build_sync_client_resources_follows_redirects() -> None:
    client, _ = build_sync_client_resources(5.0)

    assert client.follow_redirects is True

    client.close()


async def test_build_async_client_resources_follows_redirects() -> None:
    client, _ = build_async_client_resources(5.0)

    assert client.follow_redirects is True

    await client.aclose()
