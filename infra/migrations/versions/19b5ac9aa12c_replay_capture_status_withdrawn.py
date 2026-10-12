"""replay capture status withdrawn

Revision ID: 19b5ac9aa12c
Revises: 53375d9435fc
Create Date: 2026-10-12 00:00:00.000000

006-replay-analysis-foundations (T721): `replay_capture_status` gains one value, `withdrawn`, the
terminal status of a capture the claim refuses once its capture deadline is within the withdrawal
lead or past (`CaptureDrain.withdraw_refused_near_deadline`). Additive only: no column, no table,
no index, and no existing row is rewritten.

Apply it **before** the deploy that carries it: the same change bumps
`aoe2stats_storage.revision.EXPECTED_SCHEMA_REVISION`, so a database that lags the build answers
503 on `/api/health`, and a build that writes `withdrawn` into a database without the value fails
that write. Follow `docs/runbooks/database-migrations.md`.

`upgrade` is `ALTER TYPE ... ADD VALUE IF NOT EXISTS`, the form `1f9879367c9d` used for
`alert_kind`. `downgrade` follows that revision too: Postgres has no `DROP VALUE`, so it renames
the type aside, recreates it without the value, repoints `replay_captures.status` and drops the
renamed original. It does not rewrite a `withdrawn` row to another status: with one present the
repointing `ALTER` fails on the cast and the revision stays applied, which is the loud outcome. It
therefore runs only against a database holding no `withdrawn` row.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "19b5ac9aa12c"
down_revision: str | None = "53375d9435fc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Since Postgres 12, `ALTER TYPE ... ADD VALUE` is allowed inside a transaction block (only
    # *using* the new value in that same transaction is still forbidden), and constitution XII
    # fixes Postgres as the database on both hosting phases, so this runs unchanged under
    # Alembic's default transactional DDL. `IF NOT EXISTS` makes it safe to re-run.
    op.execute("ALTER TYPE replay_capture_status ADD VALUE IF NOT EXISTS 'withdrawn'")


def downgrade() -> None:
    # The rename-recreate-repoint-drop sequence `1f9879367c9d` uses for `alert_kind`.
    # `replay_captures.status` is the only column on this type.
    op.execute("ALTER TYPE replay_capture_status RENAME TO replay_capture_status_old")
    replay_capture_status = postgresql.ENUM(
        "pending",
        "downloading",
        "stored",
        "unavailable",
        "expired",
        "quarantined",
        "failed",
        name="replay_capture_status",
        create_type=False,
    )
    replay_capture_status.create(op.get_bind(), checkfirst=False)
    op.execute(
        "ALTER TABLE replay_captures ALTER COLUMN status TYPE replay_capture_status "
        "USING status::text::replay_capture_status"
    )
    op.execute("DROP TYPE replay_capture_status_old")
