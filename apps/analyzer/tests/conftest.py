"""The integration-test harness (T015) for `apps/analyzer/tests`: the same throwaway Postgres
database `apps/api/tests/conftest.py` and `apps/ingester/tests/conftest.py` build, imported from
the one place its lifecycle is implemented (`tests/db.py`) rather than duplicated here.

Not created by T302 (which only creates the `apps/analyzer/tests/` directory itself) or named by
any single Phase 7 task; added here because every one of Phase 7's `[P]` test files (T358, T360,
T362, T364) exercises `db_session` against real Postgres rows, exactly as `apps/api/tests` and
`apps/ingester/tests` already do, and pytest resolves a fixture only through a conftest ancestor or
the requesting module's own namespace — importing the fixtures straight into each test module
instead collides with that module's own `db_session: AsyncSession` parameter names under ruff's
F811 (verified while writing T362's `test_retain.py`). One shared `conftest.py`, identical in shape
to its two siblings, is the same boilerplate this workspace already uses twice; it carries no
judgment call specific to any one Phase 7 task.
"""

from __future__ import annotations

from tests.db import clean_database, database_url, db_session, engine, session_factory

# Re-exported so ruff sees these names used: pytest discovers a fixture imported into a conftest
# module exactly as if it had been defined here, which is the whole point of keeping their one
# implementation in `tests/db.py` instead of duplicating it per directory.
__all__ = ["clean_database", "database_url", "db_session", "engine", "session_factory"]
