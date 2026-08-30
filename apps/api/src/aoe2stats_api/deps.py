"""Dependency wiring for the FastAPI application: settings meet storage here and nowhere else.

`packages/storage` (T009, T010) deliberately knows nothing about `Settings`: `build_engine` takes
a bare `database_url: str`, `ObjectStore` takes an `ObjectStoreConfig` built from four plain
strings, so that package stays a library with no dependency on `apps/api` (plan.md's package
boundary). This module is the one place those two meet — every router depends on the `Annotated`
aliases at the bottom of this file, never on `Settings` or `packages.storage` directly, so a
future change to how the engine or the object store is constructed touches this file alone.

The engine, the session factory and the object store are each built once per process and cached
with `lru_cache`, the same pattern `settings.get_settings` already uses: a request should not pay
to rebuild a connection pool or a `boto3` client on every call. `get_session` is the one
generator-shaped dependency here — FastAPI closes over its `finally`/`yield` to guarantee
`session_scope`'s commit-or-rollback runs exactly once per request, whatever the route handler
does with the session.

**`ResponseCache` (T102).** Match history and ratings are read straight off Postgres on every
call — no external provider sits behind either (`routers/matches.py` and `routers/profiles.py`
both query `packages/storage` directly; ingestion already made the one provider call that
mattered, hours or days earlier). "The source" plan.md's "respond in under 500 ms p95 from cached
data" line means is therefore the database, not `packages/providers` — provider calls already
carry their own rate limiting and `provider_calls` record (constitution III), and are not doubled
by anything below.

What follows is a small in-process TTL cache, built with the same `lru_cache(maxsize=1)` singleton
pattern as `get_engine`/`get_object_store` above, so a repeat view of the same page — a reload, a
back-and-forth between the list and a detail route — answers from memory instead of re-running the
query. See `ResponseCache`'s own docstring for the full TTL/invalidation policy and why it lives in
process rather than behind a shared service.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Awaitable, Callable
from functools import lru_cache
from typing import Annotated, Any, cast

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from aoe2stats_api.settings import Settings, get_settings
from aoe2stats_storage.objects import ObjectStore, ObjectStoreConfig
from aoe2stats_storage.repositories.base import (
    build_engine,
    build_session_factory,
    session_scope,
)


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """The one `AsyncEngine` this process holds for its lifetime, built from `DATABASE_URL`."""
    return build_engine(get_settings().database_url)


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """The one `async_sessionmaker` every request shares, bound to `get_engine()`."""
    return build_session_factory(get_engine())


async def get_session() -> AsyncIterator[AsyncSession]:
    """One request, one unit of work: commit on success, roll back and re-raise on failure."""
    async with session_scope(get_session_factory()) as session:
        yield session


@lru_cache(maxsize=1)
def get_object_store() -> ObjectStore:
    """The one `ObjectStore` this process holds, built from the four `S3_*` settings."""
    settings = get_settings()
    config = ObjectStoreConfig(
        endpoint_url=settings.s3_endpoint_url,
        bucket=settings.s3_bucket,
        access_key_id=settings.s3_access_key_id,
        secret_access_key=settings.s3_secret_access_key.get_secret_value(),
        region=settings.s3_region,
    )
    return ObjectStore(config)


SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
ObjectStoreDep = Annotated[ObjectStore, Depends(get_object_store)]


# --- ResponseCache (T102) -------------------------------------------------------------------------

#: Sentinel distinguishing "no entry" from "an entry whose cached value is `None`" — `dict.get`'s
#: own `None` default would conflate the two, and a cached `None` is a legitimate value (an empty
#: rating history, for instance).
_MISSING: Any = object()

#: How long a cached response answers before the next request re-runs the query. Short enough that
#: nothing is ever stale "indefinitely" (T102's own task text) — a few tens of seconds, not
#: minutes — long enough to absorb the repeat views this cache exists for: a page reload, a
#: back-and-forth between the match list and a detail route, several components on one dashboard
#: page asking for the same profile's ratings within the same render. It is a fixed module
#: constant rather than an `.env.example` entry (the same judgement `search.py`'s own
#: `_FALLBACK_CACHE_TTL_SECONDS` makes for its protective TTL): nothing about "how long is a repeat
#: view" should need to change per deployment, and plan.md already names the 500 ms figure this
#: constant serves as a comfort target with "no check behind it".
_DEFAULT_TTL_SECONDS: float = 30.0

#: A cache key is a tuple of hashable, order-significant parts. Every caller below builds one that
#: already encodes every dimension its response varies on, ownership included — see
#: `routers/matches.py` and `routers/profiles.py` for why that matters (module docstring's own
#: cross-reference and the "Ownership and the cache key" paragraph in `ResponseCache` below).
CacheKey = tuple[Any, ...]


class ResponseCache:
    """A small in-process TTL cache for read responses that are expensive to recompute and safe to
    serve twice in a row — match history and ratings (T102), the two named in this task's text.

    **Why in-process, and not Redis or a database table.** Closed-beta scale — plan.md's own words
    for the exact number this task's text points at — does not need a cache shared across
    processes: a warm Vercel function instance answers a handful of requests from the same memory,
    and the phase-2 VPS process (constitution XII) answers many more from that same memory for as
    long as it runs. `packages/storage` already gives this project a database-table-backed cache
    for a genuinely external, degradable source (`search.py`'s `profile_search_cache`, from 003) —
    match history and ratings have no such source behind them at all (module docstring), so paying
    for a shared cache service, a new external dependency this project would then have to run, size
    and pay for, buys nothing a plain dict with a clock does not already give for free.

    **TTL is the policy for almost everything this cache holds, and that is a deliberate choice,
    not an oversight.** `_DEFAULT_TTL_SECONDS` bounds staleness to a few tens of seconds — the task
    text's own bar is "not indefinitely", which a bounded TTL satisfies by construction, without
    this module having to know about every write path that could make a cached response stale.
    The one exception is `routers/replays.py::upload_replay`: it runs in this same process, in the
    same request/response cycle a user is watching, and changes the very `capture_status` the
    match list and detail routes just cached — waiting out `_DEFAULT_TTL_SECONDS` for a user's own
    upload to appear in their own match history would be a worse experience than the cache not
    existing at all. That route calls `invalidate_prefix` on its own key namespace once the upload
    is recorded, rather than leaving it to the TTL. `routers/profiles.py`'s own primary-profile and
    unlink mutations do the same for `("profiles", "list", ...)`, for the identical reason: both
    are same-process writes a user can immediately act on again. The daily ingestion cycle
    (`apps/ingester`) is a *different* process — a separate function invocation with no memory in
    common with this one on Vercel, and even on the phase-2 VPS a separate long-lived process
    (constitution XII) — so nothing it writes needs an invalidation call here at all; the TTL alone
    bounds how long a newly-discovered match or rating can take to appear, and it already runs once
    a day, so thirty seconds is not the number anyone is waiting on.

    **Ownership and the cache key.** This cache does not itself enforce who may read what — it
    only ever answers with whatever its caller stored under the exact key its caller asks for. Every
    call site in this codebase resolves ownership against the database, uncached, *before* it ever
    touches this cache, and folds the caller's identity (or the already-ownership-checked resource
    id) into the key it reads and writes — see `routers/matches.py`'s `_owned_active_link` and
    `routers/profiles.py`'s own copy, both unchanged by this cache. A key that omitted that would
    let one caller's cached response answer a different caller's request; nothing here would notice.

    **Never caches a failure.** `cache_get_or_set` below only stores what `factory` returns — an
    exception propagates untouched and leaves no entry behind, so a transient validation error or a
    domain `APIError` (a `404`, a cursor that fails to decode) is never remembered as if it were the
    answer, and the very next request tries again from scratch.
    """

    def __init__(
        self,
        *,
        ttl_seconds: float = _DEFAULT_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        #: `time.monotonic` by default — never affected by a wall-clock adjustment, and the one
        #: `ResponseCacheDep` override this codebase's tests need is a fake `clock`, not a fake
        #: `time.sleep`, to move this cache's notion of "now" without a real wait.
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._entries: dict[CacheKey, tuple[float, Any]] = {}

    def get(self, key: CacheKey) -> Any:
        """The cached value for `key`, or the `_MISSING` sentinel on a miss — no entry at all, or
        one whose expiry has already passed, which is evicted here rather than left for a later
        write to find."""
        entry = self._entries.get(key)
        if entry is None:
            return _MISSING
        expires_at, value = entry
        if self._clock() >= expires_at:
            del self._entries[key]
            return _MISSING
        return value

    def set(self, key: CacheKey, value: Any, *, ttl_seconds: float | None = None) -> None:
        """Store `value` under `key`, fresh for `ttl_seconds` (`_DEFAULT_TTL_SECONDS` when
        omitted, the shape `search.py`'s own `ttl_seconds`/`fallback_ttl_seconds` pair already
        establishes for an explicit-parameter TTL rather than a hidden settings read)."""
        ttl = self._ttl_seconds if ttl_seconds is None else ttl_seconds
        self._entries[key] = (self._clock() + ttl, value)

    def invalidate_prefix(self, prefix: CacheKey) -> None:
        """Drop every entry whose key starts with `prefix` — the mechanism a same-process write
        uses to make its own effect visible immediately rather than waiting out the TTL (class
        docstring's "TTL is the policy for almost everything" paragraph). A key's own tuple
        ordering is what makes a prefix meaningful: `("matches", "list", profile_id, ...)` lets
        `invalidate_prefix(("matches", "list", profile_id))` drop every cursor/limit variant for
        that one profile without knowing which ones exist."""
        stale = [key for key in self._entries if key[: len(prefix)] == prefix]
        for key in stale:
            del self._entries[key]

    def clear(self) -> None:
        """Drop every entry. Used by `apps/api/tests/conftest.py`'s autouse test-isolation fixture,
        never by application code."""
        self._entries.clear()


async def cache_get_or_set[T](
    cache: ResponseCache, key: CacheKey, factory: Callable[[], Awaitable[T]]
) -> T:
    """`cache.get(key)` on a hit; otherwise await `factory()`, store what it returns under `key`,
    and return that. `factory` is a zero-argument async callable — a closure the caller builds
    around whatever it would otherwise have awaited unconditionally — so a cache hit costs exactly
    one dict lookup and never constructs the query or the response shaping around it at all.
    Generic in `_T` (`factory`'s own return type) rather than `Any`, so a caller under mypy strict
    (`pyproject.toml`) gets back the exact shape it awaited, not an unchecked one."""
    cached = cache.get(key)
    if cached is not _MISSING:
        return cast(T, cached)
    value = await factory()
    cache.set(key, value)
    return value


@lru_cache(maxsize=1)
def get_response_cache() -> ResponseCache:
    """The one `ResponseCache` this process holds for its lifetime — same `lru_cache(maxsize=1)`
    singleton pattern as `get_engine`/`get_session_factory`/`get_object_store` above.

    **Test isolation.** Unlike those three, this singleton's whole purpose is to answer a later
    call without re-running the query underneath it — which is exactly the behaviour that leaks
    across tests sharing one process if nothing resets it. `apps/api/tests/conftest.py`'s autouse
    `_reset_response_cache` fixture clears it before and after every test, the same discipline that
    file's own `_reset_companion_breaker` fixture already applies to `routers/players.py`'s
    process-lifetime circuit breaker, and for the identical reason: a process-wide cache is a
    defect exactly one test forgets to isolate away from, not a defect any one test introduces.
    """
    return ResponseCache()


ResponseCacheDep = Annotated[ResponseCache, Depends(get_response_cache)]
