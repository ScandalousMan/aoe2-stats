"""The integration-test harness (T015) for `apps/api/tests`: a throwaway Postgres database, real
migrations, and a `TestClient` wired to it.

The database lifecycle itself — create, migrate to `head`, drop — is not implemented here: it
lives once in `tests/db.py`, shared with `apps/ingester/tests/conftest.py`, and is only imported
into this module so pytest scopes it to this directory. `packages/core`'s and `packages/
providers`' unit tests, which never touch a database, must neither pay for this machinery nor be
skipped by it — a plain per-directory `conftest.py` is what keeps that true; a global fixture in
the already-registered `tests/conftest.py` plugin (T004) would not.

`client` is the one thing this module adds beyond what `tests/db.py` already exports: a FastAPI
app built with `create_app()` (T014) whose `get_session` dependency is overridden to run against
the real throwaway database through `session_scope` — the identical commit-or-rollback discipline
production requests get — rather than `test_health.py`'s and `test_cron.py`'s fakes. Every Phase
3+ integration test (T021 onward) is expected to ask for `client` (and, where it needs to seed or
inspect rows directly, `db_session` alongside it) rather than building its own app.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.db import clean_database, database_url, db_session, engine, session_factory

from aoe2stats_api.app import create_app
from aoe2stats_api.deps import get_object_store, get_session
from aoe2stats_storage.repositories.base import session_scope

# Re-exported so ruff sees these names used: pytest discovers a fixture imported into a conftest
# module exactly as if it had been defined here, which is the whole point of keeping their one
# implementation in `tests/db.py` instead of duplicating it per directory.
__all__ = ["clean_database", "database_url", "db_session", "engine", "session_factory"]


class _FakeObjectStore:
    """Stands in for `ObjectStore` (T010): no test built on this harness reaches for a real
    bucket yet, and constitution III's unit tests never touch the network — `list_keys` is the
    one method `GET /api/health` calls, and the one a future replay-download test can override
    with a richer fake of its own without this harness forcing a real S3 endpoint on everyone."""

    async def list_keys(self, prefix: str = "") -> list[str]:
        return []


@pytest.fixture
def client(
    clean_database: None,
    session_factory: async_sessionmaker[AsyncSession],
) -> Iterator[TestClient]:
    """A `TestClient` over a fresh `create_app()`, its `get_session` dependency pointed at the
    real throwaway database and its `get_object_store` dependency faked out. `clean_database` is
    requested (and ignored) purely to order the truncation before the app is ever exercised."""
    app = create_app()

    async def _get_session() -> AsyncIterator[AsyncSession]:
        async with session_scope(session_factory) as session:
            yield session

    app.dependency_overrides[get_session] = _get_session
    app.dependency_overrides[get_object_store] = lambda: _FakeObjectStore()

    with TestClient(app) as test_client:
        yield test_client
