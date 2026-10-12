"""The 006 revision `19b5ac9aa12c` (T721): `replay_capture_status` gains `withdrawn`, tested through
the real Alembic migrations against a throwaway database of this module's own.

A database of its own, not the session-wide one `tests/db.py` shares: this module runs
`downgrade`, which would pull the schema out from under every other integration test in the
session. `_throwaway_database` migrates a fresh one to head and drops it afterwards, so nothing here
can reach anything but a database this test created - never `DATABASE_URL` from the environment,
which on a developer machine is production.

Four claims, in the order the revision's own docstring makes them:

- the labels of the database type at head are exactly `CaptureStatus`'s values, so the model and the
  schema cannot name different vocabularies;
- the revision is additive and reversible: downgraded to its parent the type has the seven earlier
  labels and a row of an earlier status survives, upgraded again it has `withdrawn`;
- a downgrade with a `withdrawn` row present fails and leaves the revision applied, rather than
  rewriting the row to another status;
- `alembic check` finds no drift between `models.py` and the revisions.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import psycopg
import pytest
import sqlalchemy as sa
from alembic import command
from tests.db import (
    _CI_ENV,
    _CI_FAILURE_REASON,
    _SKIP_REASON,
    _psycopg_dsn,
    _throwaway_database,
    alembic_config,
)

from aoe2stats_storage.models import CaptureStatus

REVISION = "19b5ac9aa12c"
PARENT_REVISION = "53375d9435fc"

_EARLIER_LABELS = {
    "pending",
    "downloading",
    "stored",
    "unavailable",
    "expired",
    "quarantined",
    "failed",
}


@pytest.fixture
def migrated_url() -> Iterator[str]:
    """A fresh database at head. Function-scoped: each test may move it."""
    with _throwaway_database() as url:
        if url is None:
            if os.environ.get(_CI_ENV):
                pytest.fail(_CI_FAILURE_REASON)
            pytest.skip(_SKIP_REASON)
        yield url


def _alembic(url: str, run: str, target: str | None = None) -> None:
    """Run one Alembic command against `url` only for the duration of the call, the way
    `tests.db._migrate_to_head` does: `infra/migrations/env.py` reads `DATABASE_URL`."""
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    try:
        config = alembic_config()
        if run == "upgrade":
            assert target is not None
            command.upgrade(config, target)
        elif run == "downgrade":
            assert target is not None
            command.downgrade(config, target)
        else:
            command.check(config)
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


def _labels(url: str) -> set[str]:
    with psycopg.connect(_psycopg_dsn(url)) as conn:
        rows = conn.execute(
            "SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
            "WHERE t.typname = 'replay_capture_status'"
        ).fetchall()
    return {label for (label,) in rows}


def _scalar(url: str, sql: str) -> object:
    with psycopg.connect(_psycopg_dsn(url)) as conn:
        row = conn.execute(sql).fetchone()
    assert row is not None
    return row[0]


def _seed_capture(conn: psycopg.Connection, *, game_id: int, status: str) -> None:
    conn.execute(
        "INSERT INTO aoe_profiles (profile_id, alias, country) VALUES (%s, 'w', 'FR') "
        "ON CONFLICT DO NOTHING",
        (game_id,),
    )
    conn.execute(
        "INSERT INTO matches (game_id, leaderboard_id, completed_at, source, raw_payload) "
        "VALUES (%s, 3, now(), 'relic', '{}'::jsonb)",
        (game_id,),
    )
    conn.execute(
        "INSERT INTO replay_captures (id, game_id, profile_id, status, capture_deadline_at, "
        "attempts, source) VALUES (gen_random_uuid(), %s, %s, %s, now(), 0, 'automatic')",
        (game_id, game_id, status),
    )


def test_the_database_type_at_head_has_exactly_the_models_values(migrated_url: str) -> None:
    assert _labels(migrated_url) == {status.value for status in CaptureStatus}
    assert "withdrawn" in _labels(migrated_url)


def test_the_revision_downgrades_to_the_seven_earlier_labels_and_upgrades_again(
    migrated_url: str,
) -> None:
    with psycopg.connect(_psycopg_dsn(migrated_url), autocommit=True) as conn:
        _seed_capture(conn, game_id=1, status="pending")

    _alembic(migrated_url, "downgrade", PARENT_REVISION)

    assert _labels(migrated_url) == _EARLIER_LABELS
    assert _scalar(migrated_url, "SELECT version_num FROM alembic_version") == PARENT_REVISION
    assert _scalar(migrated_url, "SELECT status::text FROM replay_captures") == "pending"
    with psycopg.connect(_psycopg_dsn(migrated_url), autocommit=True) as conn:
        _seed_capture(conn, game_id=2, status="stored")
        with pytest.raises(psycopg.errors.InvalidTextRepresentation):
            _seed_capture(conn, game_id=3, status="withdrawn")

    _alembic(migrated_url, "upgrade", REVISION)

    assert _labels(migrated_url) == _EARLIER_LABELS | {"withdrawn"}
    assert _scalar(migrated_url, "SELECT version_num FROM alembic_version") == REVISION
    with psycopg.connect(_psycopg_dsn(migrated_url), autocommit=True) as conn:
        _seed_capture(conn, game_id=4, status="withdrawn")
    assert _scalar(migrated_url, "SELECT count(*) FROM replay_captures") == 3


def test_a_downgrade_with_a_withdrawn_row_fails_and_leaves_the_revision_applied(
    migrated_url: str,
) -> None:
    with psycopg.connect(_psycopg_dsn(migrated_url), autocommit=True) as conn:
        _seed_capture(conn, game_id=1, status="withdrawn")

    with pytest.raises(sa.exc.DBAPIError):
        _alembic(migrated_url, "downgrade", PARENT_REVISION)

    assert _scalar(migrated_url, "SELECT version_num FROM alembic_version") == REVISION
    assert _labels(migrated_url) == _EARLIER_LABELS | {"withdrawn"}
    assert _scalar(migrated_url, "SELECT status::text FROM replay_captures") == "withdrawn"


def test_the_models_and_the_migrations_agree_at_head(migrated_url: str) -> None:
    """`alembic check` - the drift detection `pr.yml`'s `migrations` job runs - raises when
    `models.py` and the revisions differ. That `EXPECTED_SCHEMA_REVISION` equals head is held by
    `apps/api/tests/test_schema_revision.py`."""
    _alembic(migrated_url, "check")
