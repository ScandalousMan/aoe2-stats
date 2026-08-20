"""The integration-test harness (T015) for `apps/ingester/tests`: the same throwaway Postgres
database `apps/api/tests/conftest.py` builds, imported from the one place its lifecycle is
implemented (`tests/db.py`) rather than duplicated here.

Deliberately independent of `aoe2stats_ingester.run` and `.budget`: T018, landing at the same time
as this task, defines `run_once(budget_seconds, stages=...)` and the `Stage` protocol it drains,
but names no database of its own — each stage decides how it reaches one, and T053/T054/T055
(Phase 4) are what actually build one against `database_url`/`session_factory`. A test for any of
those wires its own `Stage` against the fixtures below and hands it to `run_once`; this module only
owns the database underneath that, exactly as it does for `apps/api/tests`.
"""

from __future__ import annotations

from tests.db import clean_database, database_url, db_session, engine, session_factory

# Re-exported so ruff sees these names used: pytest discovers a fixture imported into a conftest
# module exactly as if it had been defined here, which is the whole point of keeping their one
# implementation in `tests/db.py` instead of duplicating it per directory.
__all__ = ["clean_database", "database_url", "db_session", "engine", "session_factory"]
