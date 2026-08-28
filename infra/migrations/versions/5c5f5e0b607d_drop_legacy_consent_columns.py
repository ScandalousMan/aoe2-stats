"""archival objection (contract)

Revision ID: 5c5f5e0b607d
Revises: ad6ae8d59519
Create Date: 2026-08-28 21:45:39.180965

The contract half of the expand/contract pair `ad6ae8d59519` (expand) started. That migration
added `archival_objected_at` and backfilled it, leaving `ingest_consent_at` and
`ingest_consent_withdrawn_at` in place so the still-deployed old code kept working while the new
code shipped. This migration finishes the job: it drops those two columns and nothing else.

**Apply this only after the new code — the one reading `archival_objected_at`, never the two old
columns — is deployed and confirmed healthy** (`docs/runbooks/database-migrations.md`). Applying
it earlier reopens exactly the outage the split exists to avoid: the still-deployed old code would
read columns that no longer exist and every route touching `users` would fail.

This is the one step in the pair that is irreversible in the sense that matters: `downgrade()` can
recreate both columns, but it cannot tell "never consented" apart from "consented and never
withdrew" again — that evidence lived only in `ingest_consent_at` having a value, and this
migration does not attempt to fabricate it. `downgrade()` recreates the columns and repopulates
`ingest_consent_withdrawn_at` from `archival_objected_at` (the one direction that is lossless);
`ingest_consent_at` comes back NULL for everyone, which is honestly the best it can do, not a claim
that the original value is recovered.

001's T106/T392 apply here as they do for the expand half: apply to Neon through the direct
endpoint, never the pooled one, and never through this repository's CI, which only ever runs it
against the throwaway database `.github/workflows/pr.yml` creates and drops.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5c5f5e0b607d"
down_revision: str | None = "ad6ae8d59519"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("users", "ingest_consent_at")
    op.drop_column("users", "ingest_consent_withdrawn_at")


def downgrade() -> None:
    op.add_column("users", sa.Column("ingest_consent_at", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("ingest_consent_withdrawn_at", sa.DateTime(timezone=True)))
    # Lossless in one direction only: an objection is known to have been a withdrawal (that is
    # the only case that produced a value going forward). `ingest_consent_at` is not recoverable
    # — see the module docstring — and is left NULL rather than backfilled with a fabricated value.
    op.execute(
        "UPDATE users SET ingest_consent_withdrawn_at = archival_objected_at "
        "WHERE archival_objected_at IS NOT NULL"
    )
