"""replay fetch misses

Revision ID: b7cc0beaab35
Revises: 5c5f5e0b607d
Create Date: 2026-08-29 00:00:00.000000

T337's own table, not named in `specs/003-player-search-match-analysis/data-model.md`'s "five new
tables" — added while implementing FR-025's boundary race (`research.md` R8) after finding that the
tempting alternative, a row in `replay_captures`, is unsafe to write for a third-party point of
view: 001's automatic capture pipeline claims from that table with no ownership filter at all
(`apps/ingester/.../capture.py::_claim_batch`), so a `pending` row would have the pipeline fetch
and store a third party's recording as a direct consequence of a download click (forbidden by
FR-012 and FR-027), and any terminal status would permanently block the real capture that pipeline
owes that profile's owner if they later link their account (`discover.py`'s `_enqueue_capture`,
`ON CONFLICT DO NOTHING`). See `ReplayFetchMiss`'s own docstring in
`packages/storage/src/aoe2stats_storage/models.py` for the full reasoning. This is reported in the
implementation's hand-back for `data-model.md` to be amended by hand alongside it, per this
repository's own rule that spec-kit artifacts are never left to drift from the code they describe.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7cc0beaab35"
down_revision: str | None = "5c5f5e0b607d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "replay_fetch_misses",
        sa.Column("game_id", sa.BigInteger(), nullable=False),
        sa.Column("profile_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "observed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["game_id"], ["matches.game_id"]),
        sa.ForeignKeyConstraint(["profile_id"], ["aoe_profiles.profile_id"]),
        sa.PrimaryKeyConstraint("game_id", "profile_id"),
    )


def downgrade() -> None:
    op.drop_table("replay_fetch_misses")
