"""erased recording keys

Revision ID: c3d41a7e92b5
Revises: 19b5ac9aa12c
Create Date: 2026-11-07 00:00:00.000000

T459s: one additive table, `erased_recording_keys`, holding the replay object keys an erasure
leaves for after its commit. See `ErasedRecordingKey` in
`packages/storage/src/aoe2stats_storage/models.py`. Apply it before the deploy that carries it: a
build that writes the table into a database without it fails the erasure's insert.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d41a7e92b5"
down_revision: str | None = "19b5ac9aa12c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "erased_recording_keys",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("erased_recording_keys")
