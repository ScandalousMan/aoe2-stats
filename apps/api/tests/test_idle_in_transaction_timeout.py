"""T459b — a request whose function was killed mid-transaction must not hold its row locks forever.

**The defect.** Vercel kills the function at `maxDuration` (10 s for `api/index.py`) without
closing its database connection cleanly: the transaction can stay open on the server, *idle*, with
every row lock it took, and nothing on the server ends it. The next request waits behind those
locks (and, with T459's `lock_timeout`, degrades), but the ingester's own transactions have no
`lock_timeout` and wait on it indefinitely - discovery, and with it capture enqueueing, is the
constitution I exposure.

**The fix under test.** `deps.get_session` - the API's request unit of work - sets
`idle_in_transaction_session_timeout` transaction-locally (`set_config(..., true)`, i.e. `SET
LOCAL`) at the start of every transaction, from `REQUEST_IDLE_IN_TRANSACTION_TIMEOUT_SECONDS`. The
server then terminates a transaction left idle past that value and releases its locks.

**What each test proves.**

- `test_a_transaction_left_idle_is_terminated_and_its_lock_released` drives the real
  `deps.get_session` against real Postgres with the value set to one second: a request transaction
  takes a row lock and goes idle (the stand-in for a killed function: its connection is alive and
  silent, exactly what the server sees), a second connection waits on that row and is granted it
  once the server terminates the first. Pre-fix the second connection waits out its own
  `lock_timeout` instead.
- `test_a_request_transaction_carries_the_configured_timeout` reads the setting from inside a
  request served by the real app.
- `test_the_setting_does_not_outlive_its_transaction` shows it is transaction-local: a later
  transaction on the same session sees it applied afresh and a connection outside any request does
  not see it (the Neon pooler hands a different backend to each transaction, so a session-level
  value would leak to another client).
- `test_a_unit_of_work_without_a_timeout_is_left_alone` pins that the ingester's long cron
  transactions, which open `session_scope` with no timeout, keep the server's own default.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterator
from contextlib import asynccontextmanager
from datetime import timedelta

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_api import deps
from aoe2stats_api.app import create_app
from aoe2stats_api.deps import SessionDep
from aoe2stats_api.settings import get_settings
from aoe2stats_storage.repositories.base import session_scope

_KEY = "REQUEST_IDLE_IN_TRANSACTION_TIMEOUT_SECONDS"

pytestmark = [pytest.mark.usefixtures("environment")]


@pytest.fixture
def _real_unit_of_work(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: async_sessionmaker[AsyncSession],
) -> Iterator[None]:
    """Point `deps.get_session` - the real request unit of work, not the `client` fixture's
    override of it - at the throwaway database."""
    monkeypatch.setattr(deps, "get_session_factory", lambda: session_factory)
    yield
    get_settings.cache_clear()


def _configure(monkeypatch: pytest.MonkeyPatch, seconds: int) -> None:
    monkeypatch.setenv(_KEY, str(seconds))
    get_settings.cache_clear()


async def test_a_transaction_left_idle_is_terminated_and_its_lock_released(
    monkeypatch: pytest.MonkeyPatch,
    clean_database: None,
    session_factory: async_sessionmaker[AsyncSession],
    _real_unit_of_work: None,
) -> None:
    _configure(monkeypatch, 1)
    table = "t459b_idle_probe"
    async with session_factory() as setup:
        await setup.execute(text(f"CREATE TABLE {table} (id integer PRIMARY KEY)"))
        await setup.execute(text(f"INSERT INTO {table} VALUES (1)"))
        await setup.commit()
    try:
        holder_has_the_lock = asyncio.Event()
        waiter_outcome: dict[str, float | BaseException] = {}

        async def holder() -> None:
            async with asynccontextmanager(deps.get_session)() as session:
                await session.execute(text(f"SELECT id FROM {table} WHERE id = 1 FOR UPDATE"))
                holder_has_the_lock.set()
                # Idle: the connection is open and silent, as a killed function's is. Long
                # enough for a one-second timeout, short enough to keep the test fast.
                await asyncio.sleep(2.5)
                with pytest.raises(DBAPIError) as terminated:
                    await session.execute(text("SELECT 1"))
                assert getattr(terminated.value.orig, "sqlstate", None) == "25P03"
                await session.rollback()

        async def waiter() -> None:
            await holder_has_the_lock.wait()
            started = time.monotonic()
            async with session_scope(session_factory) as session:
                # A bound well above the timeout and well below the holder's sleep, so an
                # unbounded holder shows up as `LockNotAvailable` rather than a hung test.
                await session.execute(text("SET LOCAL lock_timeout = '4s'"))
                try:
                    await session.execute(text(f"SELECT id FROM {table} WHERE id = 1 FOR UPDATE"))
                except BaseException as exc:
                    waiter_outcome["error"] = exc
                    raise
            waiter_outcome["waited"] = time.monotonic() - started

        await asyncio.gather(holder(), waiter())
        assert "error" not in waiter_outcome
        waited = waiter_outcome["waited"]
        assert isinstance(waited, float)
        assert waited < 3.0
    finally:
        async with session_factory() as cleanup:
            await cleanup.execute(text(f"DROP TABLE IF EXISTS {table}"))
            await cleanup.commit()


async def test_a_request_transaction_carries_the_configured_timeout(
    monkeypatch: pytest.MonkeyPatch,
    clean_database: None,
    _real_unit_of_work: None,
) -> None:
    _configure(monkeypatch, 7)
    app = create_app()
    probe = APIRouter()

    @probe.get("/api/_t459b/idle-timeout")
    async def read_setting(session: SessionDep) -> dict[str, str]:
        value = (
            await session.execute(
                text("SELECT current_setting('idle_in_transaction_session_timeout')")
            )
        ).scalar_one()
        return {"value": value}

    app.include_router(probe)
    with TestClient(app, base_url="https://testserver") as test_client:
        response = test_client.get("/api/_t459b/idle-timeout")
    assert response.status_code == 200
    assert response.json() == {"value": "7s"}


async def test_the_setting_does_not_outlive_its_transaction(
    monkeypatch: pytest.MonkeyPatch,
    clean_database: None,
    session_factory: async_sessionmaker[AsyncSession],
    _real_unit_of_work: None,
) -> None:
    _configure(monkeypatch, 9)
    query = text("SELECT current_setting('idle_in_transaction_session_timeout')")
    async with session_factory() as outside:
        baseline = (await outside.execute(query)).scalar_one()
    async with asynccontextmanager(deps.get_session)() as session:
        first = (await session.execute(query)).scalar_one()
        await session.commit()
        # A second transaction on the same session: the hook runs at every transaction begin,
        # so a route that commits mid-request does not lose the bound.
        second = (await session.execute(query)).scalar_one()
    async with session_factory() as outside:
        after = (await outside.execute(query)).scalar_one()
    assert (first, second) == ("9s", "9s")
    assert after == baseline
    assert baseline != "9s"


async def test_a_unit_of_work_without_a_timeout_is_left_alone(
    clean_database: None,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    query = text("SELECT current_setting('idle_in_transaction_session_timeout')")
    async with session_factory() as plain:
        baseline = (await plain.execute(query)).scalar_one()
    async with session_scope(session_factory) as session:
        assert (await session.execute(query)).scalar_one() == baseline
    async with session_scope(
        session_factory, idle_in_transaction_timeout=timedelta(seconds=4)
    ) as s:
        assert (await s.execute(query)).scalar_one() == "4s"
