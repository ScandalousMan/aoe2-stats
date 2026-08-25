"""index profile search cache fetched at

Revision ID: b23f76b4e1fb
Revises: 1f9879367c9d
Create Date: 2026-08-24 20:09:38.438757

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b23f76b4e1fb"
down_revision: str | None = "1f9879367c9d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# T386: `apps/api/src/aoe2stats_api/search.py`'s opportunistic prune runs a
# `DELETE ... WHERE fetched_at < threshold` against `profile_search_cache` on every successful
# cache write. Without an index on `fetched_at`, that `DELETE` is a full-table scan on every write
# — the mechanism that exists to bound the table's size degrades linearly with the thing it
# bounds. Same pattern as `matches.completed_at` (`4fdc4873ab6c_initial_schema.py`): `index=True`
# on the model column, mirrored here.


def upgrade() -> None:
    op.create_index(
        op.f("ix_profile_search_cache_fetched_at"),
        "profile_search_cache",
        ["fetched_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_profile_search_cache_fetched_at"), table_name="profile_search_cache")
