"""Async engine, session factory and repository base for `aoe2stats_storage`.

Research §4 (`specs/001-steam-link-replay-ingestion/research.md`) settles two decisions this
module exists to encode once, rather than let every caller rediscover them:

- Every process this code runs in — a Vercel function today, a long-lived worker on the phase-2
  VPS tomorrow — connects through Neon's *pooled* connection string. Each invocation is short-lived
  and has nothing to amortise, so this module adds no client-side pool of its own (`NullPool`);
  SQLAlchemy's own pooling against the *direct* (non-pooled) endpoint is, in research's words,
  "the documented way to run out of connections on this platform", and pooling is left to the
  platform in front of `DATABASE_URL` instead.
- A transaction pooler hands a different backend connection to every transaction. A server-side
  prepared statement cached against one backend can silently be replayed against another, which
  looks like data corruption rather than a configuration mistake. `psycopg` 3's own
  `prepare_threshold` connect parameter is set to `None` so no statement is ever prepared
  server-side — switched off explicitly here, rather than discovered in production.

The connection string itself is never read from this module. Constitution XII puts `DATABASE_URL`
behind `apps/api/src/aoe2stats_api/settings.py`, and `packages/storage` must not import an
application package to reach it (plan.md's package boundary: storage is a library, not a
consumer of `apps/api`). Every entry point below therefore takes the DSN as a plain string,
resolved once by whichever caller already holds a `Settings` instance — the FastAPI dependency
wiring (T014) and the ingester's `run_once()` (T059) each build their own engine from it.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

# `psycopg` 3's own escape hatch for pgbouncer-style transaction pooling (research §4): `None`
# disables automatic server-side statement preparation outright, rather than merely raising the
# threshold at which it would kick in. Module-level and public so a test can assert the decision
# directly instead of reaching into `create_async_engine`'s call.
PSYCOPG_CONNECT_ARGS: dict[str, object] = {"prepare_threshold": None}


def build_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    """Build the one `AsyncEngine` a process should hold for its lifetime.

    `database_url` is expected to already carry the `postgresql+psycopg://` scheme — SQLAlchemy's
    dialect for `psycopg` 3, which supports async natively — and to be Neon's pooled endpoint per
    `.env.example`. `NullPool` and `PSYCOPG_CONNECT_ARGS` are what let this engine sit safely in
    front of that pooler; see the module docstring for why each one is here.
    """
    return create_async_engine(
        database_url,
        echo=echo,
        poolclass=NullPool,
        connect_args=PSYCOPG_CONNECT_ARGS,
    )


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Build the `async_sessionmaker` every repository and FastAPI dependency shares.

    `expire_on_commit=False`: a value read after a unit of work commits — a freshly inserted row's
    generated id, for instance — must stay readable without an implicit re-fetch. Triggering one
    would spend a round trip against the same pooled connection this module otherwise goes out of
    its way not to waste (see `build_engine`).
    """
    return async_sessionmaker(bind=engine, expire_on_commit=False)


@asynccontextmanager
async def session_scope(
    session_factory: Callable[[], AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """One unit of work over one session: commit on success, roll back and re-raise on failure.

    Shaped as an async context manager so it composes identically as a FastAPI dependency and as
    the unit of work the ingester's `run_once()` (T059) opens once per cycle — the caller decides
    how often a "unit of work" happens; this only decides what one looks like. The session itself
    is always closed on the way out, since `AsyncSession.__aexit__` does that regardless of which
    branch below ran.
    """
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


class Repository:
    """Base class every repository in `aoe2stats_storage.repositories` subclasses.

    Deliberately thin: a repository is a wrapper around one `AsyncSession` that names its queries
    after the domain rather than after SQL. Every constraint this schema actually leans on — the
    claim query's `FOR UPDATE SKIP LOCKED`, the `(game_id, profile_id)` dedup, the partial indexes
    in `models.py` — belongs to the repository that issues that query, not to this base. The one
    thing every repository shares is exactly the one thing kept here: the session it runs against.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
