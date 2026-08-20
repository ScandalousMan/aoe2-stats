"""The throwaway-database harness (T015): one Postgres database per test session, migrated to
`head` through the real Alembic migrations and dropped when the session ends.

This module is the one place that machinery lives. `apps/api/tests/conftest.py` and
`apps/ingester/tests/conftest.py` each import the fixtures below rather than redefining them —
pytest registers an imported fixture exactly as if it were declared in the importing module, which
is what lets both directories share one implementation while still scoping it to only the two
directories that need a database (`packages/core`'s or `packages/providers`' unit tests, which
never touch one, must neither pay for this machinery nor be skipped by it).

It sits beside `tests/conftest.py` (T004, the network-blocking autouse fixture) rather than inside
`packages/storage`, for the same reason that module is already here and not inside any workspace
member: this is test-only infrastructure applying across app boundaries, not application code.
That distinction also matters for `infra/migrations/env.py`'s own comment on `alembic` living in
the root dev toolchain and "never imported by application code" — this module imports it, but it
is a test harness, not `apps/*` or `packages/*` source.

**Skips locally, fails in CI, when no database is reachable.** `.github/workflows/pr.yml`'s
`python` job now runs a Postgres service (T015a) at the same credentials this module falls back
to, so a developer who has that Postgres running locally needs to set nothing, and CI has it every
time. A `pytest.skip` there would prove nothing — it is exactly what let every integration test
from T021 on skip silently on every pull request until T015a's CI service was added — so this
module fails hard instead when `CI` is set (the convention GitHub Actions and every other major CI
runner exports), and only skips outside CI, where a contributor may legitimately not have Postgres
running. Reachability is checked once per session against `TEST_DATABASE_URL`, or that same local
default.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from aoe2stats_storage.models import Base
from aoe2stats_storage.repositories.base import (
    build_engine,
    build_session_factory,
    session_scope,
)

#: Overridable per environment. Falls back to the exact credentials both `.github/workflows/
#: pr.yml` jobs run Postgres 16 against (the `migrations` job, and — since T015a — the `python`
#: job too), so nothing extra needs setting in either.
TEST_DATABASE_URL_ENV = "TEST_DATABASE_URL"
_DEFAULT_ADMIN_DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/postgres"
_CONNECT_TIMEOUT_SECONDS = 2

#: Set by GitHub Actions (and every other major CI runner) on every job. Distinguishes "no
#: Postgres reachable because a contributor's machine legitimately has none running" — fine to
#: skip — from "no Postgres reachable in a CI job that is supposed to have one" — never fine to
#: skip, because a skip there is indistinguishable from a pass and is exactly what let T015's
#: harness go unexercised from T021 onward until T015a gave the `python` job a service.
_CI_ENV = "CI"

_SKIP_REASON = (
    "No Postgres reachable for the integration-test harness (T015, tests/db.py). Set "
    f"{TEST_DATABASE_URL_ENV} to an admin connection string, or run one locally at the default "
    "this module falls back to (postgresql://postgres:postgres@localhost:5432/postgres) — the "
    "same credentials .github/workflows/pr.yml's `python` and `migrations` jobs both use."
)

_CI_FAILURE_REASON = (
    "No Postgres reachable for the integration-test harness (T015, tests/db.py), and CI is set "
    "— .github/workflows/pr.yml's `python` job runs a Postgres service (T015a) precisely so this "
    "never happens there. Failing instead of skipping: a skip here would silently report every "
    "integration test from T021 onward as passed without having run, which is the gap T015a "
    "closed. If you are seeing this in CI, the service itself is the thing to investigate."
)


def _admin_database_url() -> str:
    return os.environ.get(TEST_DATABASE_URL_ENV, _DEFAULT_ADMIN_DATABASE_URL)


def _psycopg_dsn(url: str) -> str:
    """`psycopg.connect` speaks libpq connection strings, not SQLAlchemy's `+psycopg` dialect."""
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def _database_reachable(url: str) -> bool:
    try:
        with psycopg.connect(_psycopg_dsn(url), connect_timeout=_CONNECT_TIMEOUT_SECONDS):
            return True
    except psycopg.OperationalError:
        return False


def _with_database(url: str, name: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{name}", parts.query, parts.fragment))


def _repo_root() -> Path:
    """`tests/db.py` lives one directory below the repository root — the same root
    `alembic.ini` (T008) and `infra/migrations/` sit at."""
    return Path(__file__).resolve().parent.parent


def _alembic_config() -> Config:
    root = _repo_root()
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "infra" / "migrations"))
    return config


def _migrate_to_head(database_url: str) -> None:
    """Run the real migrations (T008) against `database_url`, never `Base.metadata.create_all`:
    an integration test should run against the schema that actually ships, not a shortcut of it.

    `infra/migrations/env.py` reads `DATABASE_URL` from the environment by design (constitution
    VIII: no connection string lives in `alembic.ini`), so this is set for the duration of the
    call and restored immediately after — never left behind for anything else in the process to
    read by accident.
    """
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        command.upgrade(_alembic_config(), "head")
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


def _drop_database(admin_dsn: str, name: str) -> None:
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        # A stale connection (a test that leaked one, a crashed previous run) blocks DROP
        # DATABASE outright rather than merely slowing it down — terminate first.
        conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (name,),
        )
        conn.execute(f'DROP DATABASE IF EXISTS "{name}"')


@contextmanager
def _throwaway_database() -> Iterator[str | None]:
    """Create a uniquely named database, migrate it to `head`, yield its connection string, then
    drop it. Yields `None` instead of raising when nothing is reachable at `_admin_database_url()`
    — turning that into a `pytest.skip` is the caller fixture's job, not this context manager's,
    so this module stays importable (and testable) without pytest itself.
    """
    admin_url = _admin_database_url()
    if not _database_reachable(admin_url):
        yield None
        return

    name = f"aoe2stats_test_{uuid.uuid4().hex[:12]}"
    admin_dsn = _psycopg_dsn(admin_url)
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')

    database_url = _with_database(admin_url, name)
    try:
        _migrate_to_head(database_url)
        yield database_url
    finally:
        _drop_database(admin_dsn, name)


# --- pytest fixtures --------------------------------------------------------------------------
# Imported into `apps/api/tests/conftest.py` and `apps/ingester/tests/conftest.py`, never used
# directly from here (this module is not itself collected as a conftest).


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """The throwaway database's connection string, migrated to `head`; created once for the
    whole test session and dropped when it ends. Every fixture below — and any Phase 3+ test
    that builds its own engine or its own `Stage` (T018's shape) against a plain DSN — starts
    here.

    Unreachable is a hard failure under `CI` (T015a) and a skip everywhere else — see
    `_CI_FAILURE_REASON` and `_SKIP_REASON` above for why the two environments are not held to
    the same standard here.
    """
    with _throwaway_database() as url:
        if url is None:
            if os.environ.get(_CI_ENV):
                pytest.fail(_CI_FAILURE_REASON)
            pytest.skip(_SKIP_REASON)
        yield url


@pytest.fixture(scope="session")
def engine(database_url: str) -> Iterator[AsyncEngine]:
    """The one `AsyncEngine` the session shares, built exactly as `apps/api/src/aoe2stats_api/
    deps.py` builds its own (`build_engine`, T009) — same `NullPool`, same disabled server-side
    prepared statements — so a test exercises the identical connection behaviour production does.
    """
    built = build_engine(database_url)
    try:
        yield built
    finally:
        # Fixture teardown here is synchronous; no event loop is running at this point (every
        # function-scoped async test has already closed its own), so a fresh one for the one
        # `await` this needs is exactly what `asyncio.run` is for.
        asyncio.run(built.dispose())


@pytest.fixture(scope="session")
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return build_session_factory(engine)


@pytest.fixture
async def clean_database(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[None]:
    """Truncate every table before the test runs.

    One physical database serves the whole session — creating a fresh one per test would dwarf
    the cost of the tests themselves — so this is what keeps one test's rows from leaking into
    the next. Truncating *before* rather than after means a test that crashes mid-way still hands
    the next one a clean start, and the final test's leftovers are moot: the whole database is
    dropped when the session ends (`database_url` above).
    """
    tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    if tables:
        async with session_factory() as session:
            await session.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))
            await session.commit()
    yield


@pytest.fixture
async def db_session(
    clean_database: None,
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """One unit of work against the already-clean throwaway database: commit on success, roll
    back and re-raise on failure — `session_scope` (T009), the same rule `apps/api/src/
    aoe2stats_api/deps.py`'s `get_session` applies to every request.
    """
    async with session_scope(session_factory) as session:
        yield session
