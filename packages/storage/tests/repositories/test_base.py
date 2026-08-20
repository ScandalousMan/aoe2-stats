"""Unit tests for `aoe2stats_storage.repositories.base`.

Nothing here opens a real connection: the `python` CI job that runs `uv run pytest -q` has no
Postgres service (only the `migrations` job does, against `infra/migrations/`), and constitution
III's network-blocking fixture (`tests/conftest.py`) applies to this suite like every other. What
is asserted instead is the *decision* research §4 records — `NullPool`, `prepare_threshold=None`,
`expire_on_commit=False` — and the commit/rollback contract of `session_scope`, using a fake
session that never touches a socket.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlalchemy.pool import NullPool

from aoe2stats_storage.repositories import base


class _FakeAsyncSession:
    """The minimal shape `session_scope` needs: an async context manager with commit/rollback."""

    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        self.closed = False

    async def __aenter__(self) -> _FakeAsyncSession:
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        self.closed = True
        return False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


def test_build_engine_disables_server_side_prepared_statements_and_uses_null_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_create_async_engine(url: str, **kwargs: Any) -> MagicMock:
        captured["url"] = url
        captured.update(kwargs)
        return MagicMock(spec=AsyncEngine)

    monkeypatch.setattr(base, "create_async_engine", fake_create_async_engine)

    dsn = "postgresql+psycopg://user:password@host-pooler.neon.tech/dbname?sslmode=require"
    engine = base.build_engine(dsn)

    assert engine is not None
    assert captured["url"] == dsn
    assert captured["poolclass"] is NullPool
    # Research §4: a transaction pooler hands each transaction a different backend, so a cached
    # server-side prepared statement must never be created in the first place.
    assert captured["connect_args"] == {"prepare_threshold": None}


def test_build_engine_defaults_to_echo_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        base,
        "create_async_engine",
        lambda url, **kwargs: captured.update(kwargs) or MagicMock(spec=AsyncEngine),
    )

    base.build_engine("postgresql+psycopg://user:password@host/dbname")

    assert captured["echo"] is False


def test_psycopg_connect_args_is_the_single_source_for_the_decision() -> None:
    # Public and module-level so any future caller building its own engine (or a test asserting
    # the decision) reads it from one place rather than restating `{"prepare_threshold": None}`.
    assert base.PSYCOPG_CONNECT_ARGS == {"prepare_threshold": None}


def test_build_session_factory_binds_the_engine_and_disables_expire_on_commit() -> None:
    engine = MagicMock(spec=AsyncEngine)

    factory = base.build_session_factory(engine)

    assert isinstance(factory, async_sessionmaker)
    assert factory.kw["bind"] is engine
    assert factory.kw["expire_on_commit"] is False


def test_repository_holds_the_session_it_is_constructed_with() -> None:
    session = MagicMock()

    repository = base.Repository(session)

    assert repository.session is session


def test_session_scope_commits_and_closes_on_success() -> None:
    fake_session = _FakeAsyncSession()

    async def run() -> None:
        async with base.session_scope(lambda: fake_session) as session:
            assert session is fake_session
            assert not session.committed

    asyncio.run(run())

    assert fake_session.committed
    assert not fake_session.rolled_back
    assert fake_session.closed


def test_session_scope_rolls_back_and_reraises_on_failure() -> None:
    fake_session = _FakeAsyncSession()

    async def run() -> None:
        with pytest.raises(ValueError, match="boom"):
            async with base.session_scope(lambda: fake_session):
                raise ValueError("boom")

    asyncio.run(run())

    assert fake_session.rolled_back
    assert not fake_session.committed
    assert fake_session.closed
