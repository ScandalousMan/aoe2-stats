"""aoe profiles avatar hash

Revision ID: 4e9cc77b853e
Revises: b7cc0beaab35
Create Date: 2026-08-31 06:46:47.932804

004-visual-parity (T421): the Steam avatar hash aoe2companion reports (`avatarhash`), read at
display time to build `https://avatars.steamstatic.com/<hash>_full.jpg` client-side (FR-008a,
FR-015) — the URL itself is never stored, only the hash. Additive and nullable: nullable is the
ordinary case, not the error case — a profile never seen in a companion response has no hash, and
FR-008a's neutral placeholder is the correct render for it. No backfill and no lock of consequence.
See `AoeProfile.avatar_hash` in `packages/storage/src/aoe2stats_storage/models.py` and
data-model.md §1 for the full reasoning, and `docs/privacy/processing-register.md` for the
constitution IX basis this joins `alias`/`country` on.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4e9cc77b853e"
down_revision: str | None = "b7cc0beaab35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("aoe_profiles", sa.Column("avatar_hash", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("aoe_profiles", "avatar_hash")
