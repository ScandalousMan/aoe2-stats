"""The Alembic revision this tree's models expect the database to be at.

**T394.** A restated value, which `CLAUDE.md` forbids for measurements and permits for a
constraint that governs a decision — and this one is guarded rather than trusted:
`apps/api/tests/test_schema_revision.py` asserts it equals `infra/migrations`' own head on every
run, so a migration added without touching this constant turns the suite red rather than shipping
a health check that certifies the wrong schema. That test is the reason this is a constant at all.

**Why a constant rather than a lookup.** Reading the head from `infra/migrations/versions` at
runtime would make the answer depend on those files being inside the deployed function bundle,
which nothing guarantees (`vercel.json` declares no `includeFiles`) and which constitution XII
rules out on principle: no local filesystem state. A string compiled into the package travels with
the code that expects it, which is exactly the claim `/api/health` needs to make — *this build*
expects *this revision* — and is true on a VPS and on a serverless function alike.

**What this is for.** `/api/health`'s database probe is `SELECT 1`, which succeeds against a
schema missing every column a migration would have added. On 2026-08-23 the 003 merge shipped
`1f9879367c9d` and nothing applied it: `/api/health` answered `ok`, `GET /api/me` answered 200
while signed out, and every signed-in request answered 500 on an undefined column. The whole
outage was invisible to every automated check in the repository. This constant is what lets the
health route say so.
"""

from __future__ import annotations

#: `uv run alembic heads`. Update in the same commit as the migration that moves it — the test
#: named above fails until you do.
#:
#: This is the **contract** half of the `ad6ae8d59519` / `5c5f5e0b607d` expand/contract pair
#: (`docs/runbooks/database-migrations.md`): the revision where `ingest_consent_at` and
#: `ingest_consent_withdrawn_at` are gone and `archival_objected_at` is the only column the code
#: in this tree reads. Production briefly sits at `ad6ae8d59519` (expand applied, contract not
#: yet) while this build's health check reports `schema_out_of_date` — expected, not a fault; see
#: that migration's docstring.
#:
#: `b7cc0beaab35` (T337) adds `replay_fetch_misses` — see that migration's own docstring and
#: `ReplayFetchMiss` in `models.py` for why FR-025's boundary race needed a table of its own
#: rather than a `replay_captures` row.
EXPECTED_SCHEMA_REVISION = "b7cc0beaab35"

__all__ = ["EXPECTED_SCHEMA_REVISION"]
