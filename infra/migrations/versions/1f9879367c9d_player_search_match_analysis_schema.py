"""player search match analysis schema

Revision ID: 1f9879367c9d
Revises: 61d7bd9e3684
Create Date: 2026-08-23 14:42:56.326443

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "1f9879367c9d"
down_revision: str | None = "61d7bd9e3684"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# T304/T305: everything `specs/003-player-search-match-analysis/data-model.md` adds — five new
# tables, `aoe_profiles` gaining `alias_observed_at`, `replay_access_log` widened to point at
# either a `replay_captures` or a `retained_recordings` row, and `alert_kind` gaining
# `analysis_cap_reached`. One migration for all of it (data-model.md's own instruction): a
# partially-applied schema is the one state none of the later phases can recover from.

# New enum type for `match_analyses.state` — same pattern as the four existing types in
# `4fdc4873ab6c_initial_schema.py`: created once here with `create_type=False` on the column, so
# this migration controls its lifecycle explicitly rather than leaving it to whichever
# `create_table`/`drop_table` call happens to touch it first.
match_analysis_state = postgresql.ENUM(
    "queued",
    "running",
    "published",
    "failed",
    "unavailable",
    "refused",
    name="match_analysis_state",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    match_analysis_state.create(bind, checkfirst=True)

    # `AlertKind.ANALYSIS_CAP_REACHED` (models.py) — adding a value to an existing Postgres enum
    # type is not `op.add_column`. Since Postgres 12, `ALTER TYPE ... ADD VALUE` is allowed inside
    # a transaction block (only *using* the new value in that same transaction is still
    # forbidden), and constitution XII already fixes Postgres as the database on both phase-1 and
    # phase-2 hosting, so this runs unchanged under Alembic's default transactional DDL. `IF NOT
    # EXISTS` makes it safe to re-run.
    op.execute("ALTER TYPE alert_kind ADD VALUE IF NOT EXISTS 'analysis_cap_reached'")

    # `aoe_profiles` widened: `alias_observed_at` only. Deliberately no `hidden_observed_at` — see
    # the model docstring and data-model.md: FR-004c was retired on measurement (T301a) and a
    # column nothing can ever set must not be created.
    op.add_column(
        "aoe_profiles", sa.Column("alias_observed_at", sa.DateTime(timezone=True), nullable=True)
    )

    op.create_table(
        "profile_search_cache",
        sa.Column("query_normalised", sa.Text(), nullable=False),
        sa.Column("results", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("query_normalised"),
    )

    op.create_table(
        "favourites",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("profile_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["aoe_profiles.profile_id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "profile_id"),
    )

    op.create_table(
        "rate_limit_counters",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("bucket", sa.Text(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "bucket", "window_start"),
    )

    op.create_table(
        "match_analyses",
        sa.Column("game_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("state", match_analysis_state, nullable=False),
        sa.Column("point_of_view_profile_id", sa.BigInteger(), nullable=False),
        sa.Column("parser_name", sa.Text(), nullable=True),
        sa.Column("parser_version", sa.Text(), nullable=True),
        sa.Column("engine_deps", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("requested_by_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_class", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("result_key", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["game_id"], ["matches.game_id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("game_id"),
    )

    op.create_table(
        "retained_recordings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("game_id", sa.BigInteger(), nullable=False),
        sa.Column("profile_id", sa.BigInteger(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("zip_bytes", sa.BigInteger(), nullable=False),
        sa.Column("zip_sha256", sa.Text(), nullable=False),
        sa.Column(
            "retained_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("requested_by_user_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["game_id"], ["matches.game_id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
        sa.UniqueConstraint(
            "game_id", "profile_id", name="uq_retained_recordings_game_id_profile_id"
        ),
    )

    # `replay_access_log` widened: after this feature there are two kinds of archive a logged
    # access can point at — a user's own `replay_captures` row, or a third party's
    # `retained_recordings` row read only by `apps/analyzer`. Must run after `retained_recordings`
    # exists, for the new foreign key below.
    op.alter_column(
        "replay_access_log", "replay_capture_id", existing_type=sa.UUID(), nullable=True
    )
    op.add_column("replay_access_log", sa.Column("retained_recording_id", sa.UUID(), nullable=True))
    # No explicit constraint name: models.py's `ForeignKey(...)` on this column carries none
    # either, so both let Postgres assign its own default name — matching what `alembic check`
    # compares against.
    op.create_foreign_key(
        None,
        "replay_access_log",
        "retained_recordings",
        ["retained_recording_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_replay_access_log_retained_recording_id"),
        "replay_access_log",
        ["retained_recording_id"],
        unique=False,
    )
    # The exact predicate data-model.md pins down: Postgres's own null-counting function, not a
    # pair of `IS NULL` comparisons, so it reads as the requirement itself. Must be the same
    # string as the `CheckConstraint` in models.py's `ReplayAccessLog`, or `alembic check` reports
    # drift.
    op.create_check_constraint(
        "ck_replay_access_log_exactly_one_source",
        "replay_access_log",
        "num_nonnulls(replay_capture_id, retained_recording_id) = 1",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_replay_access_log_exactly_one_source", "replay_access_log", type_="check"
    )
    op.drop_index(
        op.f("ix_replay_access_log_retained_recording_id"), table_name="replay_access_log"
    )
    # Postgres's own default name for a nameless `ADD CONSTRAINT ... FOREIGN KEY` —
    # `<table>_<column>_fkey` — the same default the inline `create_foreign_key(None, ...)` call
    # above relied on.
    op.drop_constraint(
        "replay_access_log_retained_recording_id_fkey",
        "replay_access_log",
        type_="foreignkey",
    )
    op.drop_column("replay_access_log", "retained_recording_id")
    op.alter_column(
        "replay_access_log", "replay_capture_id", existing_type=sa.UUID(), nullable=False
    )

    op.drop_table("retained_recordings")
    op.drop_table("match_analyses")
    op.drop_table("rate_limit_counters")
    op.drop_table("favourites")
    op.drop_table("profile_search_cache")

    op.drop_column("aoe_profiles", "alias_observed_at")

    # Postgres has no `ALTER TYPE ... DROP VALUE`. The standard workaround — rename the type
    # aside, recreate it without the value, repoint every column that used it, drop the renamed
    # original — is only safe because `alerts` is the sole table on `alert_kind` and this database
    # is the throwaway/CI one `alembic upgrade head` / `downgrade -1` runs against with no rows to
    # lose.
    op.execute("ALTER TYPE alert_kind RENAME TO alert_kind_old")
    alert_kind = postgresql.ENUM(
        "rate_limited",
        "deadline_breach",
        "expired_capture",
        "validation_failed",
        "free_tier",
        name="alert_kind",
        create_type=False,
    )
    alert_kind.create(op.get_bind(), checkfirst=False)
    op.execute("ALTER TABLE alerts ALTER COLUMN kind TYPE alert_kind USING kind::text::alert_kind")
    op.execute("DROP TYPE alert_kind_old")

    match_analysis_state.drop(op.get_bind(), checkfirst=True)
