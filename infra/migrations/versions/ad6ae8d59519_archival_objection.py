"""archival objection

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

This is the one task in this phase that changes stored data, and it is irreversible in the sense
that matters: `downgrade()` can reconstruct a schema with both old columns, but it cannot tell
"never consented" apart from "consented and never withdrew" again — that evidence lived only in
`ingest_consent_at` having a value, and this migration does not attempt to fabricate it. The
`downgrade()` below reconstructs the columns and repopulates `ingest_consent_withdrawn_at` from
`archival_objected_at` (the one direction that is lossless); `ingest_consent_at` comes back NULL
for everyone, which is honestly the best this migration can do, not a claim that the original value
is recovered.

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
    op.drop_column("users", "archival_objected_at")
