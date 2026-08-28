"""archival objection (expand)

Revision ID: ad6ae8d59519
Revises: b23f76b4e1fb
Create Date: 2026-08-26 00:00:00.000000

Constitution IX 4.0.0 retires the opt-in consent gate: ingestion and archival now rest on
legitimate interest (Art. 6-1-f), and a mandatory right to object (Art. 21) replaces it. The two
timestamps that recorded consent's history — `ingest_consent_at` (the grant) and
`ingest_consent_withdrawn_at` (a later withdrawal) — give way to one: `archival_objected_at`. Null
means archiving; set means the user has objected. There is no third state to record: "never
consented" and "consented, then withdrew" were a distinction 4.0.0 removes the legal weight of,
because there is no grant left to have a history of.

**The migration rule, stated once and applied by `op.execute` below:** a user with a live
withdrawal (`ingest_consent_withdrawn_at IS NOT NULL`) carries that timestamp forward as their
objection — they had actively opted out under the old gate, and 4.0.0's right to object is the
same act under its correct legal basis, so the moment they exercised it is preserved. Every other
user — including every one who granted consent and never withdrew, and every one who never
answered the question at all — becomes `archival_objected_at IS NULL`, which is now "archiving".
This is deliberate and is the one behaviour change 4.0.0 requires: a linked profile that has
answered nothing is no longer excluded from anything.

**This is the expand half of an expand/contract pair, split for exactly one reason: a migration
that both adds the new column and drops the two old ones in a single revision cannot be applied
safely relative to a code deploy in either order — the old code still reads the old columns until
its replacement is live, and the new code reads a column that does not exist until this migration
has run.** This revision only adds `archival_objected_at` and backfills it; `ingest_consent_at`
and `ingest_consent_withdrawn_at` are left in place, untouched, so the still-deployed old code
(`apps/api/src/aoe2stats_api/routers/auth.py`, `apps/ingester/src/aoe2stats_ingester/discover.py`)
keeps working unmodified against this schema. The companion contract migration
(`down_revision = "ad6ae8d59519"`) drops the two old columns once the new code is confirmed live —
see that file, and `docs/runbooks/database-migrations.md`, for the sequencing.

**The `schema_out_of_date` window this opens, and why it is expected.** Between this migration
being applied and the deploy that carries the new code reaching production, the database's
`alembic_version` is ahead of the `EXPECTED_SCHEMA_REVISION` compiled into the still-deployed old
tree (`packages/storage/src/aoe2stats_storage/revision.py`). `/api/health` (T394) will report
`schema_out_of_date` for that window — this is the check doing its job, not a fault: every route
still serves, because expand only adds a column, and nothing yet reads it. The window should last
no longer than the deploy itself; if `schema_out_of_date` is still showing once the new code is
confirmed live, that is the actual fault to investigate, not this window.

**Why this revision id and `down_revision` are unchanged even though the migration's shape
changed.** This migration has never been applied to any real database — only to throwaway
containers and CI — so restructuring what it does is free, and keeping the id stable keeps every
existing reference to `ad6ae8d59519` (git history, `revision.py`'s prior value, this docstring's
own cross-references) meaningful.

001's T106/T392 apply: this migration must be applied to Neon through the direct endpoint, not the
pooled one (`docs/runbooks/database-migrations.md`) — never through this repository's CI, which
only ever runs it against the throwaway database `.github/workflows/pr.yml` creates and drops.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ad6ae8d59519"
down_revision: str | None = "b23f76b4e1fb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("archival_objected_at", sa.DateTime(timezone=True)))
    op.execute(
        "UPDATE users SET archival_objected_at = ingest_consent_withdrawn_at "
        "WHERE ingest_consent_withdrawn_at IS NOT NULL"
    )


def downgrade() -> None:
    # The old columns were never touched by this revision's upgrade() — only the new column needs
    # undoing here. No data loss: `ingest_consent_at` and `ingest_consent_withdrawn_at` still hold
    # whatever they held before upgrade() ran.
    op.drop_column("users", "archival_objected_at")
