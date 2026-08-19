"""Alembic environment for the schema in `packages/storage/src/aoe2stats_storage/models.py`.

Configuration comes exclusively from the `DATABASE_URL` environment variable (constitution VIII,
XII): there is no connection string in `alembic.ini`, no local filesystem state, and the same
migration runs unchanged against Neon in phase 1 and self-hosted Postgres in phase 2. This module
is a tool invoked by a human or CI, not application code, so it is exempt from constitution III's
provider boundary — but it still never hard-codes a secret.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from aoe2stats_storage.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Alembic reads the connection string exclusively from the "
            "environment (constitution VIII) — there is no default and none belongs in "
            "alembic.ini."
        )
    return url


def run_migrations_offline() -> None:
    """Emit SQL against a URL without opening a database connection."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Connect and run migrations against a live database."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
