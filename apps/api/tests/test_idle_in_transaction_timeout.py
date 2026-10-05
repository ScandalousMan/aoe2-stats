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
  takes a row lock and goes idle for five seconds (the stand-in for a killed function: its
  connection is alive and silent, exactly what the server sees), and a second connection, whose
  own `lock_timeout` is three seconds, must be granted that row after about one second - before
  its own timeout and long before the holder's sleep ends. Without the timeout the holder keeps
  the lock for the whole sleep, so the second connection fails with `LockNotAvailable` at three
  seconds, and the holder's `SELECT 1` after the sleep succeeds instead of reporting `25P03`.
- `test_a_request_transaction_carries_the_configured_timeout` reads the setting from inside a
  request served by the real app.
- `test_the_setting_does_not_outlive_its_transaction` shows it is transaction-local: a later
  transaction on the same session sees it applied afresh and a connection outside any request does
  not see it (the Neon pooler hands a different backend to each transaction, so a session-level
  value would leak to another client).
- `test_a_savepoint_does_not_set_the_timeout_again` counts the statements that set it: one for the
  transaction, none for a savepoint opened inside it.
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
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from aoe2stats_api import deps
from aoe2stats_api.app import create_app
from aoe2stats_api.deps import SessionDep
from aoe2stats_api.settings import get_settings
from aoe2stats_storage.repositories.base import session_scope

_KEY = "REQUEST_IDLE_IN_TRANSACTION_TIMEOUT_SECONDS"

#: Seconds. Server timeout (the test sets 1) < waiter's `lock_timeout` < holder's idle sleep.
_WAITER_LOCK_TIMEOUT = 3
_HOLDER_IDLE_SECONDS = 5

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
                # Idle: the connection is open and silent, as a killed function's is. Longer
                # than the waiter's `lock_timeout`, so only the server ending this transaction
                # can let the waiter through in time.
                await asyncio.sleep(_HOLDER_IDLE_SECONDS)
                with pytest.raises(DBAPIError) as terminated:
                    await session.execute(text("SELECT 1"))
                assert getattr(terminated.value.orig, "sqlstate", None) == "25P03"
                await session.rollback()

        async def waiter() -> None:
            await holder_has_the_lock.wait()
            started = time.monotonic()
            async with session_scope(session_factory) as session:
                # Between the server's timeout and the holder's sleep: a holder nothing
                # terminates shows up as `LockNotAvailable` here rather than as a hung test.
                await session.execute(text(f"SET LOCAL lock_timeout = '{_WAITER_LOCK_TIMEOUT}s'"))
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
        assert waited < _WAITER_LOCK_TIMEOUT - 0.5, waited
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


async def test_a_savepoint_does_not_set_the_timeout_again(
    engine: AsyncEngine,
    clean_database: None,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    sent: list[str] = []

    def record(_conn: object, _cursor: object, statement: str, *_rest: object) -> None:
        if "set_config('idle_in_transaction_session_timeout'" in statement:
            sent.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", record)
    try:
        async with session_scope(
            session_factory, idle_in_transaction_timeout=timedelta(seconds=4)
        ) as session:
            await session.execute(text("SELECT 1"))
            async with session.begin_nested():
                await session.execute(text("SELECT 1"))
            async with session.begin_nested():
                await session.execute(text("SELECT 1"))
            value = (
                await session.execute(
                    text("SELECT current_setting('idle_in_transaction_session_timeout')")
                )
            ).scalar_one()
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", record)
    assert value == "4s"
    assert len(sent) == 1, sent
