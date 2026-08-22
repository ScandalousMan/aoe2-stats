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

**T015b** consolidates what four agents wrote independently in one parallel batch, once each
believing it was the only one adding it: `_FakeObjectStore` existed byte-for-byte or near enough
in this file, `test_cron.py`, `test_health.py` and `test_index_entrypoint.py`; `_FakeSession` in
three of those; and the 18-key `REQUIRED_ENV` dict plus its autouse `_environment` fixture
existed byte-identically in `test_cron.py` and `test_cron_ingest_entrypoint.py`. Every one of
those lives here now, as fixtures — never a bare `import conftest` from a sibling test module:
`apps/api/tests` and `apps/ingester/tests` both hold a file literally named `conftest.py`, and
under pytest's default "prepend" import mode a plain `import conftest` resolves to whichever of
the two was imported *last* in the session, not the one in the importing file's own directory —
confirmed by running exactly that import from both directories in one session before writing this
comment. Fixture lookup is pytest's own directory-scoped mechanism, not the `sys.modules` cache
namespace clash a bare import goes through, which is why every name below is requested as a
fixture parameter rather than imported.

The `environment` fixture is deliberately **not** autouse here: `test_health.py`,
`test_index_entrypoint.py` and `test_settings.py` build their environment (or none at all, in
`test_index_entrypoint.py`'s and `test_engine_isolation.py`'s case) their own way, and an
autouse fixture in this file would apply to all of them whether they asked for it or not.
`test_cron.py` and `test_cron_ingest_entrypoint.py` opt in explicitly with
`pytestmark = pytest.mark.usefixtures("environment")`.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.db import clean_database, database_url, db_session, engine, session_factory

from aoe2stats_api.app import create_app
from aoe2stats_api.deps import get_object_store, get_session
from aoe2stats_api.settings import get_settings
from aoe2stats_storage.repositories.base import session_scope

# Re-exported so ruff sees these names used: pytest discovers a fixture imported into a conftest
# module exactly as if it had been defined here, which is the whole point of keeping their one
# implementation in `tests/db.py` instead of duplicating it per directory.
__all__ = ["clean_database", "database_url", "db_session", "engine", "session_factory"]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_EXAMPLE = _REPO_ROOT / ".env.example"

# Every entrypoint test that needs a full environment needs exactly this set of values — not
# defaults `.env.example` could supply, since most of its values are deliberately blank (secrets)
# or tuned for production (`INGEST_RUN_BUDGET_SECONDS=240` vs. the 5 s a fast test wants). What
# *can* and must agree with `.env.example` is the **set of keys**: the assertion right below reads
# that file the same way `scripts/checks/publication_delay.py` reads `REPLAY_PUBLICATION_GRACE_
# HOURS` from it, so a key added to or removed from `.env.example` fails this suite immediately
# instead of the settings surface quietly drifting one test file at a time (T015b).
REQUIRED_ENV: dict[str, str] = {
    "DATABASE_URL": "postgresql+psycopg://user:password@host/dbname?sslmode=require",
    "S3_ENDPOINT_URL": "https://account.eu.r2.cloudflarestorage.com",
    "S3_BUCKET": "aoe2-stats-replays",
    "S3_ACCESS_KEY_ID": "test-access-key",
    "S3_SECRET_ACCESS_KEY": "test-secret-key",
    "S3_REGION": "auto",
    "APP_ENV": "development",
    "APP_SECRET_KEY": "test-app-secret",
    "PUBLIC_BASE_URL": "http://localhost:5173",
    "CRON_SECRET": "not-a-real-secret-not-a-real-secret",
    "STEAM_API_KEY": "test-steam-api-key",
    "BETA_ALLOWLIST_STEAM_IDS": "",
    "CAPTURE_BUDGET_DAYS": "21",
    "REPLAY_PUBLICATION_GRACE_HOURS": "72",
    "AOEMS_MAX_REQUESTS_PER_SECOND": "1",
    "INGEST_RUN_BUDGET_SECONDS": "5",
    "INGEST_MAX_CAPTURES_PER_USER_PER_RUN": "20",
    "INGEST_QUOTA_EXEMPT_DAYS": "7",
}


def _env_example_keys(env_example_path: Path = _ENV_EXAMPLE) -> set[str]:
    """Every variable name `.env.example` declares on its own `KEY=` line, comments excluded."""
    text = env_example_path.read_text(encoding="utf-8")
    return set(re.findall(r"^([A-Z][A-Z0-9_]*)=", text, re.MULTILINE))


_missing_from_fixture = _env_example_keys() - set(REQUIRED_ENV)
_missing_from_env_example = set(REQUIRED_ENV) - _env_example_keys()
if _missing_from_fixture or _missing_from_env_example:
    raise AssertionError(
        "apps/api/tests/conftest.py's REQUIRED_ENV has drifted from .env.example: "
        f"declared in .env.example but not in REQUIRED_ENV: {sorted(_missing_from_fixture)}; "
        f"in REQUIRED_ENV but not declared in .env.example: {sorted(_missing_from_env_example)}"
    )


@pytest.fixture
def required_env() -> dict[str, str]:
    """The 18-key environment `test_cron.py` and `test_cron_ingest_entrypoint.py` both need,
    checked against `.env.example` above at import time rather than only where it is used."""
    return REQUIRED_ENV


@pytest.fixture
def environment(monkeypatch: pytest.MonkeyPatch, required_env: dict[str, str]) -> Iterator[None]:
    """Set every `required_env` key and clear the cached `Settings`, both before and after —
    requested explicitly per module (`pytestmark = pytest.mark.usefixtures("environment")`),
    never autouse here, so files that build their own environment are unaffected."""
    for key, value in required_env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class _FakeSession:
    """Stands in for `AsyncSession`: every route this harness fakes a session for only calls
    `execute`. `fails=True` raises the way a real outage would, for `test_health.py`'s checks;
    every other caller takes the default and never sees the exception path."""

    def __init__(self, *, fails: bool = False) -> None:
        self._fails = fails

    async def execute(self, _statement: object) -> None:
        if self._fails:
            raise RuntimeError("simulated database outage")


class _FakeObjectStore:
    """Stands in for `ObjectStore` (T010): no test built on this harness reaches for a real
    bucket yet, and constitution III's unit tests never touch the network — `list_keys` is the
    one method `GET /api/health` calls today. `fails=True` raises the way a real outage would,
    for `test_health.py`'s checks; every other caller takes the default and gets an empty list.

    `signed_get_url` (T066) never touches the network either: it deterministically encodes `key`
    and `expires_in` into the returned string, so a test can assert on the redirect target alone
    without needing the same instance the route handler received — the `client` fixture builds a
    fresh one per request through a bare lambda, so nothing can be asserted on shared state here.
    """

    def __init__(self, *, fails: bool = False) -> None:
        self._fails = fails

    async def list_keys(self, prefix: str = "") -> list[str]:
        if self._fails:
            raise RuntimeError("simulated object store outage")
        return []

    async def signed_get_url(self, key: str, *, expires_in: int = 300) -> str:
        if self._fails:
            raise RuntimeError("simulated object store outage")
        return f"https://fake-object-store.example/signed/{key}?expires_in={expires_in}"


@pytest.fixture
def fake_session_class() -> type[_FakeSession]:
    return _FakeSession


@pytest.fixture
def fake_object_store_class() -> type[_FakeObjectStore]:
    return _FakeObjectStore


@pytest.fixture
def client(
    clean_database: None,
    session_factory: async_sessionmaker[AsyncSession],
) -> Iterator[TestClient]:
    """A `TestClient` over a fresh `create_app()`, its `get_session` dependency pointed at the
    real throwaway database and its `get_object_store` dependency faked out. `clean_database` is
    requested (and ignored) purely to order the truncation before the app is ever exercised.

    `base_url="https://testserver"` (T015c): every cookie `security.py` sets carries
    `secure=True` (constitution VIII), and a cookie jar never sends a secure cookie back over
    plain HTTP. `TestClient`'s default `base_url` is `http://testserver`, so without this every
    session and CSRF-state cookie a router sets would silently vanish before the next request in
    the same test — a defect in the harness, not in the routers it drives, and not one to fix by
    weakening `secure=True`.
    """
    app = create_app()

    async def _get_session() -> AsyncIterator[AsyncSession]:
        async with session_scope(session_factory) as session:
            yield session

    app.dependency_overrides[get_session] = _get_session
    app.dependency_overrides[get_object_store] = lambda: _FakeObjectStore()

    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client
