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
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated

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
