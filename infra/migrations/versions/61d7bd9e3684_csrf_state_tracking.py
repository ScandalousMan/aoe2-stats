"""csrf state tracking

Revision ID: 61d7bd9e3684
Revises: 4fdc4873ab6c
Create Date: 2026-08-21 21:52:33.631290

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "61d7bd9e3684"
down_revision: str | None = "4fdc4873ab6c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # T028b: server-side tracking for the OAuth CSRF `state` — a row here is what lets
    # `security.verify_csrf_state` refuse a `state` already consumed or past its own expiry,
    # regardless of what the client's cookie still claims.
    op.create_table(
        "csrf_states",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("csrf_states")
