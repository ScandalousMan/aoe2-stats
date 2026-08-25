"""T394: `/api/health` fails when the deployed schema is behind the code querying it.

The gap this closes was measured, not imagined. On 2026-08-23 the 003 merge shipped
`1f9879367c9d` and nothing in the pipeline applied it. Every automated check in the repository
was green and stayed green: `/api/health`'s database probe is `SELECT 1`, which succeeds against
a schema missing every column the migration adds, and `GET /api/me` returns before touching the
database when the caller is signed out — so the smoke check T393 added would have passed too,
twice, while every signed-in request answered 500 on `aoe_profiles.alias_observed_at`.

Two claims, and the second one is what makes the first mean anything a year from now:

- the route compares the database's `alembic_version` against the revision *this build* expects,
  and answers a code of its own — `schema_out_of_date`, never `database_unavailable`: one says
  the database is down, the other says a deploy step was skipped, and an operator does different
  things about them;
- `EXPECTED_SCHEMA_REVISION` equals `infra/migrations`' actual head. It is a restated value, so
  it is a value that can go stale, and a stale one would make this route certify the wrong schema
  with total confidence. That test is not a formality: it is the only thing standing between a
  new migration and a health check that lies.
"""

from __future__ import annotations

import pytest
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from tests.db import alembic_config

from aoe2stats_storage.revision import EXPECTED_SCHEMA_REVISION

pytestmark = pytest.mark.usefixtures("environment")


def test_the_expected_revision_is_the_migrations_head() -> None:
    """Fails the moment a migration is added without updating the constant — which is the whole
    reason the constant is allowed to exist (`aoe2stats_storage/revision.py`)."""
    head = ScriptDirectory.from_config(alembic_config()).get_current_head()

    assert head == EXPECTED_SCHEMA_REVISION, (
        f"aoe2stats_storage.revision.EXPECTED_SCHEMA_REVISION is {EXPECTED_SCHEMA_REVISION!r} but "
        f"infra/migrations' head is {head!r}. Update the constant in the same commit as the "
        "migration: until you do, /api/health certifies a schema this build does not expect."
    )


async def test_health_is_ok_and_names_the_revision_when_the_schema_is_at_head(
    client: TestClient,
) -> None:
    """The positive case, against the real throwaway database `tests/db.py` migrated to head with
    the real migrations — not a fake that would agree with anything."""
    response = client.get("/api/health")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "status": "ok",
        "database": "ok",
        "object_store": "ok",
        "schema_revision": EXPECTED_SCHEMA_REVISION,
    }


async def test_health_reports_schema_out_of_date_when_the_database_is_behind(
    client: TestClient, db_session: AsyncSession
) -> None:
    """The outage, reproduced: a reachable database at the revision production was actually at
    (`61d7bd9e3684`, `csrf_state_tracking`) while the build expects the one the merge shipped."""
    await db_session.execute(text("UPDATE alembic_version SET version_num = '61d7bd9e3684'"))
    await db_session.commit()
    try:
        response = client.get("/api/health")
    finally:
        # Restored explicitly rather than left to `clean_database`, which truncates the tables the
        # tests write and never touches `alembic_version` — a database left at a stale revision
        # here would make every later test in the session run against a schema the harness
        # believes is at head.
        await db_session.execute(
            text("UPDATE alembic_version SET version_num = :head"),
            {"head": EXPECTED_SCHEMA_REVISION},
        )
        await db_session.commit()

    assert response.status_code == 503, response.text
    error = response.json()["error"]
    assert error["code"] == "schema_out_of_date"
    assert error["detail"] == {"expected": EXPECTED_SCHEMA_REVISION, "found": "61d7bd9e3684"}


async def test_health_reports_schema_out_of_date_when_nothing_has_ever_been_migrated(
    client: TestClient, db_session: AsyncSession
) -> None:
    """The contrast case one level down, and the one a naive implementation gets wrong: with no
    `alembic_version` relation at all, reading it raises — and a statement that raises inside a
    transaction poisons it for everything after, so a route that caught the failure and carried on
    would fail on its *next* query instead, reporting some other fault entirely. The route asks
    `to_regclass` first for exactly this case, and a database that has never been migrated is
    still `schema_out_of_date` with `found: null` rather than `database_unavailable`.
    """
    await db_session.execute(text("DROP TABLE alembic_version"))
    await db_session.commit()
    try:
        response = client.get("/api/health")
    finally:
        await db_session.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        )
        await db_session.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:head)"),
            {"head": EXPECTED_SCHEMA_REVISION},
        )
        await db_session.commit()

    assert response.status_code == 503, response.text
    error = response.json()["error"]
    assert error["code"] == "schema_out_of_date"
    assert error["detail"] == {"expected": EXPECTED_SCHEMA_REVISION, "found": None}
