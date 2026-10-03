"""analysis knowledge gaps and identity digest

Revision ID: 53375d9435fc
Revises: 4e9cc77b853e
Create Date: 2026-10-03 00:00:00.000000

006-replay-analysis-foundations (T663): the feature's one additive revision, with nothing to
contract.

- `analysis_knowledge_gaps` — FR-039's aggregate, in full: one flat row per gap the coverage pass
  could not answer, grouped by build, cause and severity by `KnowledgeGapsRepository.gap_rate`. It
  holds no personal data: a participant is not a column (data-model.md §7).
  `build` is not nullable — a gap whose stream named no build carries `-1`, T652b's sentinel.
  Unique on `(identity_digest, entity_kind, entity_id, field, coalesce(civilisation_id, ''))`, an
  expression index rather than a plain constraint so that two rows with no civilisation collide
  (Postgres never treats two NULLs as equal) — that is what makes a reproduced analysis record
  nothing twice.
- `match_analyses.identity_digest` — nullable, no backfill. A row published before this feature has
  none, which the staleness test reads as stale and recomputes once (T657a, data-model.md §8).
  Nothing about 003's behaviour or its primary key changes (FR-048).
- `match_analyses.recording_build` — nullable integer, no backfill, beside the digest. The build the
  recording's own stream named (`-1` where it named none, data-model.md §7), written on publish, so
  the staleness test can compute the current digest from the row and never read the object store
  (T666b, SC-006). A row with it NULL reads as stale and recomputes once. Folded into this revision
  rather than a second one because this revision has not been applied anywhere but throwaway test
  databases.

Apply it **before** the deploy that carries it: the same change bumps
`aoe2stats_storage.revision.EXPECTED_SCHEMA_REVISION`, so a database that lags the build answers
503 on `/api/health` and fails the smoke workflow. Follow `docs/runbooks/database-migrations.md`.

`downgrade` drops both columns, the table and the two enum types this revision created; it is the
exact inverse, and loses the recorded gaps, digests and builds, which is acceptable for a throwaway
database and a deliberate act anywhere else.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "53375d9435fc"
down_revision: str | None = "4e9cc77b853e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Same pattern as `1f9879367c9d`'s `match_analysis_state`: the type is created and dropped
# explicitly here, and the column references it with `create_type=False`. Values restate
# `AnalysisGapCause` / `AnalysisGapSeverity` in models.py, which restate data-model.md §7.
analysis_gap_cause = postgresql.ENUM(
    "no-snapshot-for-build",
    "entity-absent",
    "field-absent",
    "civilisation-not-modelled",
    "effect-not-modelled",
    name="analysis_gap_cause",
    create_type=False,
)
analysis_gap_severity = postgresql.ENUM(
    "blocking",
    "informational",
    name="analysis_gap_severity",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    analysis_gap_cause.create(bind, checkfirst=True)
    analysis_gap_severity.create(bind, checkfirst=True)

    op.create_table(
        "analysis_knowledge_gaps",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("game_id", sa.BigInteger(), nullable=False),
        sa.Column("identity_digest", sa.Text(), nullable=False),
        sa.Column("build", sa.Integer(), nullable=False),
        sa.Column("entity_kind", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("field", sa.Text(), nullable=False),
        sa.Column("civilisation_id", sa.Text(), nullable=True),
        sa.Column("cause", analysis_gap_cause, nullable=False),
        sa.Column("severity", analysis_gap_severity, nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["game_id"], ["matches.game_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_analysis_knowledge_gaps_game_id"), "analysis_knowledge_gaps", ["game_id"]
    )
    op.create_index(
        "ix_analysis_knowledge_gaps_build_cause_severity",
        "analysis_knowledge_gaps",
        ["build", "cause", "severity"],
    )
    op.create_index(
        "uq_analysis_knowledge_gaps_identity_entity_field_civilisation",
        "analysis_knowledge_gaps",
        [
            "identity_digest",
            "entity_kind",
            "entity_id",
            "field",
            sa.text("coalesce(civilisation_id, '')"),
        ],
        unique=True,
    )

    op.add_column("match_analyses", sa.Column("identity_digest", sa.Text(), nullable=True))
    op.add_column("match_analyses", sa.Column("recording_build", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("match_analyses", "recording_build")
    op.drop_column("match_analyses", "identity_digest")

    op.drop_index(
        "uq_analysis_knowledge_gaps_identity_entity_field_civilisation",
        table_name="analysis_knowledge_gaps",
    )
    op.drop_index(
        "ix_analysis_knowledge_gaps_build_cause_severity",
        table_name="analysis_knowledge_gaps",
    )
    op.drop_index(op.f("ix_analysis_knowledge_gaps_game_id"), table_name="analysis_knowledge_gaps")
    op.drop_table("analysis_knowledge_gaps")

    bind = op.get_bind()
    analysis_gap_severity.drop(bind, checkfirst=True)
    analysis_gap_cause.drop(bind, checkfirst=True)
