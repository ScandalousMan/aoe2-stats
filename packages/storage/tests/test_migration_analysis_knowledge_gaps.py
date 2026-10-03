"""The 006 revision (`53375d9435fc`, T663): `analysis_knowledge_gaps` and the two nullable
`match_analyses` columns `identity_digest` and `recording_build` (T666b), tested through the real
Alembic migrations against a throwaway database of this module's own.

A database of its own, not the session-wide one `tests/db.py` shares: this module runs
`downgrade -1`, which would pull the schema out from under every other integration test in the
session. `_throwaway_database` migrates a fresh one to head and drops it afterwards, so nothing
here can reach anything but a database this test created — never `DATABASE_URL` from the
environment, which on a developer machine is production.

Three claims, in the order the revision's own docstring makes them:

- the schema at head is what data-model.md §7 and §8 name — the non-nullable `build` T652b's `-1`
  sentinel relies on, the one nullable identity column, the nullable digest and recording build on
  003's table;
- the unique index delivers "a reproduced analysis records nothing twice", including for the NULL
  civilisation a plain constraint would let through;
- the revision is reversible, and `alembic check` finds no drift between it and `models.py`.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import psycopg
import pytest
from alembic import command
from tests.db import (
    _CI_ENV,
    _CI_FAILURE_REASON,
    _SKIP_REASON,
    _psycopg_dsn,
    _throwaway_database,
    alembic_config,
)

REVISION = "53375d9435fc"
PARENT_REVISION = "4e9cc77b853e"


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


def _columns(url: str, table: str) -> dict[str, tuple[str, str]]:
    """`{column: (data_type, is_nullable)}` straight from the catalogue."""
    with psycopg.connect(_psycopg_dsn(url)) as conn:
        rows = conn.execute(
            "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = %s",
            (table,),
        ).fetchall()
    return {name: (data_type, nullable) for name, data_type, nullable in rows}


def _scalar(url: str, sql: str) -> object:
    with psycopg.connect(_psycopg_dsn(url)) as conn:
        row = conn.execute(sql).fetchone()
    assert row is not None
    return row[0]


def test_the_table_has_exactly_the_columns_data_model_names(migrated_url: str) -> None:
    columns = _columns(migrated_url, "analysis_knowledge_gaps")

    assert columns == {
        "id": ("bigint", "NO"),
        "game_id": ("bigint", "NO"),
        "identity_digest": ("text", "NO"),
        "build": ("integer", "NO"),
        "entity_kind": ("text", "NO"),
        "entity_id": ("text", "NO"),
        "field": ("text", "NO"),
        "civilisation_id": ("text", "YES"),
        "cause": ("USER-DEFINED", "NO"),
        "severity": ("USER-DEFINED", "NO"),
        "recorded_at": ("timestamp with time zone", "NO"),
    }


def test_the_identity_digest_is_a_nullable_text_column_on_match_analyses(
    migrated_url: str,
) -> None:
    assert _columns(migrated_url, "match_analyses")["identity_digest"] == ("text", "YES")


def test_the_recording_build_is_a_nullable_integer_column_on_match_analyses(
    migrated_url: str,
) -> None:
    """T666b: beside the digest, nullable and unbackfilled - a NULL on either reads as stale."""
    assert _columns(migrated_url, "match_analyses")["recording_build"] == ("integer", "YES")


def test_a_gap_naming_no_build_is_recorded_with_the_minus_one_sentinel(
    migrated_url: str,
) -> None:
    """T652b: `build` is not nullable, so the sentinel is the only honest answer — and it must
    actually be storable."""
    with psycopg.connect(_psycopg_dsn(migrated_url), autocommit=True) as conn:
        _seed_match(conn, 1)
        _insert_gap(conn, game_id=1, build=-1)
        with pytest.raises(psycopg.errors.NotNullViolation):
            conn.execute(
                "INSERT INTO analysis_knowledge_gaps (game_id, identity_digest, build, "
                "entity_kind, entity_id, field, cause, severity) "
                "VALUES (1, 'd', NULL, 'unit', '1', 'hp', 'entity-absent', 'blocking')"
            )


def test_the_same_gap_under_the_same_identity_is_recorded_once_even_with_no_civilisation(
    migrated_url: str,
) -> None:
    with psycopg.connect(_psycopg_dsn(migrated_url), autocommit=True) as conn:
        _seed_match(conn, 1)
        _insert_gap(conn, game_id=1, build=180059)
        with pytest.raises(psycopg.errors.UniqueViolation):
            _insert_gap(conn, game_id=1, build=180059)


def test_a_different_identity_or_civilisation_is_a_different_gap(migrated_url: str) -> None:
    with psycopg.connect(_psycopg_dsn(migrated_url), autocommit=True) as conn:
        _seed_match(conn, 1)
        _insert_gap(conn, game_id=1, build=180059)
        _insert_gap(conn, game_id=1, build=180059, identity_digest="other")
        _insert_gap(conn, game_id=1, build=180059, civilisation_id="britons")

    assert _scalar(migrated_url, "SELECT count(*) FROM analysis_knowledge_gaps") == 3


def test_the_revision_downgrades_cleanly_and_upgrades_again(migrated_url: str) -> None:
    _alembic(migrated_url, "downgrade", PARENT_REVISION)

    assert _columns(migrated_url, "analysis_knowledge_gaps") == {}
    assert "identity_digest" not in _columns(migrated_url, "match_analyses")
    assert "recording_build" not in _columns(migrated_url, "match_analyses")
    assert (
        _scalar(
            migrated_url,
            "SELECT count(*) FROM pg_type WHERE typname IN "
            "('analysis_gap_cause', 'analysis_gap_severity')",
        )
        == 0
    )

    _alembic(migrated_url, "upgrade", "head")

    assert "identity_digest" in _columns(migrated_url, "match_analyses")
    assert "recording_build" in _columns(migrated_url, "match_analyses")
    assert "build" in _columns(migrated_url, "analysis_knowledge_gaps")
    assert _scalar(migrated_url, "SELECT version_num FROM alembic_version") == REVISION


def test_the_models_and_the_migrations_agree_at_head(migrated_url: str) -> None:
    """`alembic check` — the same drift detection `pr.yml`'s `migrations` job runs — raises when
    `models.py` and the revisions differ."""
    _alembic(migrated_url, "check")


def _seed_match(conn: psycopg.Connection, game_id: int) -> None:
    conn.execute(
        "INSERT INTO matches (game_id, leaderboard_id, completed_at, source, raw_payload) "
        "VALUES (%s, 3, now(), 'relic', '{}'::jsonb)",
        (game_id,),
    )


def _insert_gap(
    conn: psycopg.Connection,
    *,
    game_id: int,
    build: int,
    identity_digest: str = "digest",
    civilisation_id: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO analysis_knowledge_gaps (game_id, identity_digest, build, entity_kind, "
        "entity_id, field, civilisation_id, cause, severity) "
        "VALUES (%s, %s, %s, 'unit', '1', 'hp', %s, 'entity-absent', 'blocking')",
        (game_id, identity_digest, build, civilisation_id),
    )
