"""initial schema

Revision ID: 4fdc4873ab6c
Revises:
Create Date: 2026-08-19 22:49:05.030978

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "4fdc4873ab6c"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The four Postgres ENUM types from `aoe2stats_storage.models`. Declared once here, with
# `create_type=False` on every column that uses them, so this migration controls their lifecycle
# explicitly instead of leaving it to whichever `create_table`/`drop_table` call happens to touch
# them first — autogenerate's default (`create_type=True` implicitly, dropped only as a side
# effect of the *last* table using it) makes `downgrade()` leave the type behind whenever a type is
# shared by more than one table, or is dropped in an order autogenerate did not anticipate. Each
# type is created once in `upgrade()` and dropped once in `downgrade()`, after every table that
# uses it is gone — the exact asymmetry `upgrade() -> downgrade() -> upgrade()` exists to catch.
alert_kind = postgresql.ENUM(
    "rate_limited",
    "deadline_breach",
    "expired_capture",
    "validation_failed",
    "free_tier",
    name="alert_kind",
    create_type=False,
)
data_request_kind = postgresql.ENUM(
    "export",
    "erasure",
    "third_party_objection",
    name="data_request_kind",
    create_type=False,
)
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
replay_capture_source = postgresql.ENUM(
    "automatic",
    "manual",
    name="replay_capture_source",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    alert_kind.create(bind, checkfirst=True)
    data_request_kind.create(bind, checkfirst=True)
    replay_capture_status.create(bind, checkfirst=True)
    replay_capture_source.create(bind, checkfirst=True)

    op.create_table(
        "aoe_profiles",
        sa.Column("profile_id", sa.BigInteger(), nullable=False),
        sa.Column("alias", sa.Text(), nullable=False),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("profile_id"),
    )
    op.create_table(
        "ingest_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("budget_seconds", sa.Integer(), nullable=False),
        sa.Column("profiles_polled", sa.Integer(), nullable=False),
        sa.Column("matches_discovered", sa.Integer(), nullable=False),
        sa.Column("captures_attempted", sa.Integer(), nullable=False),
        sa.Column("stored_total", sa.Integer(), nullable=False),
        sa.Column("failed_total", sa.Integer(), nullable=False),
        sa.Column("unavailable_total", sa.Integer(), nullable=False),
        sa.Column("expired_total", sa.Integer(), nullable=False),
        sa.Column("quarantined_total", sa.Integer(), nullable=False),
        sa.Column("alerts_raised", sa.Integer(), nullable=False),
        sa.Column("backlog_remaining", sa.Integer(), nullable=False),
        sa.Column("capture_lag_p50_seconds", sa.Integer(), nullable=True),
        sa.Column("capture_lag_p95_seconds", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "matches",
        sa.Column("game_id", sa.BigInteger(), nullable=False),
        sa.Column("leaderboard_id", sa.Integer(), nullable=False),
        sa.Column("map_name", sa.Text(), nullable=True),
        sa.Column("patch", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("game_id"),
    )
    op.create_index(op.f("ix_matches_completed_at"), "matches", ["completed_at"], unique=False)
    op.create_table(
        "provider_calls",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "called_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("rate_limited", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("allowlisted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingest_consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingest_consent_withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "alerts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("kind", alert_kind, nullable=False),
        sa.Column("severity", sa.SmallInteger(), nullable=False),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "raised_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ingest_run_id", sa.UUID(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("severity IN (1, 2)", name="ck_alerts_severity_range"),
        sa.ForeignKeyConstraint(
            ["ingest_run_id"],
            ["ingest_runs.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "data_requests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("kind", data_request_kind, nullable=False),
        sa.Column("subject_user_id", sa.UUID(), nullable=True),
        sa.Column("subject_profile_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["subject_profile_id"],
            ["aoe_profiles.profile_id"],
        ),
        sa.ForeignKeyConstraint(["subject_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "match_players",
        sa.Column("game_id", sa.BigInteger(), nullable=False),
        sa.Column("profile_id", sa.BigInteger(), nullable=False),
        sa.Column("team_id", sa.SmallInteger(), nullable=True),
        sa.Column("civ_id", sa.SmallInteger(), nullable=True),
        sa.Column("color_id", sa.SmallInteger(), nullable=True),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("rating_diff", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["matches.game_id"],
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["aoe_profiles.profile_id"],
        ),
        sa.PrimaryKeyConstraint("game_id", "profile_id"),
    )
    op.create_table(
        "rating_snapshots",
        sa.Column("profile_id", sa.BigInteger(), nullable=False),
        sa.Column("leaderboard_id", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("wins", sa.Integer(), nullable=True),
        sa.Column("losses", sa.Integer(), nullable=True),
        sa.Column("streak", sa.Integer(), nullable=True),
        sa.Column("highest_rating", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["aoe_profiles.profile_id"],
        ),
        sa.PrimaryKeyConstraint("profile_id", "leaderboard_id", "captured_at"),
    )
    op.create_table(
        "replay_captures",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("game_id", sa.BigInteger(), nullable=False),
        sa.Column("profile_id", sa.BigInteger(), nullable=False),
        sa.Column("status", replay_capture_status, nullable=False),
        sa.Column("capture_deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("stored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("object_key", sa.Text(), nullable=True),
        sa.Column("zip_bytes", sa.BigInteger(), nullable=True),
        sa.Column("zip_sha256", sa.Text(), nullable=True),
        sa.Column("inner_filename", sa.Text(), nullable=True),
        sa.Column("inner_bytes", sa.BigInteger(), nullable=True),
        sa.Column("source", replay_capture_source, nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("validated_by", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["matches.game_id"],
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["aoe_profiles.profile_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("game_id", "profile_id", name="uq_replay_captures_game_id_profile_id"),
    )
    op.create_index(
        "ix_replay_captures_claim_order",
        "replay_captures",
        ["status", "next_attempt_at", "capture_deadline_at"],
        unique=False,
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)
    op.create_table(
        "steam_identities",
        sa.Column("steam_id64", sa.Text(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_sign_in_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("steam_id64"),
    )
    op.create_index(
        op.f("ix_steam_identities_user_id"), "steam_identities", ["user_id"], unique=False
    )
    op.create_table(
        "profile_links",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("profile_id", sa.BigInteger(), nullable=False),
        sa.Column("steam_id64", sa.Text(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column(
            "linked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("unlinked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("backfill_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["aoe_profiles.profile_id"],
        ),
        sa.ForeignKeyConstraint(
            ["steam_id64"], ["steam_identities.steam_id64"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_profile_links_profile_id"), "profile_links", ["profile_id"], unique=False
    )
    op.create_index(
        "ix_profile_links_profile_id_active",
        "profile_links",
        ["profile_id"],
        unique=True,
        postgresql_where=sa.text("unlinked_at IS NULL"),
    )
    op.create_index(op.f("ix_profile_links_user_id"), "profile_links", ["user_id"], unique=False)
    op.create_index(
        "ix_profile_links_user_id_primary",
        "profile_links",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_primary AND unlinked_at IS NULL"),
    )
    op.create_table(
        "replay_access_log",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("replay_capture_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "accessed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["replay_capture_id"], ["replay_captures.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_replay_access_log_replay_capture_id"),
        "replay_access_log",
        ["replay_capture_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_replay_access_log_user_id"), "replay_access_log", ["user_id"], unique=False
    )
    op.create_table(
        "replay_parses",
        sa.Column("replay_capture_id", sa.UUID(), nullable=False),
        sa.Column("parser_name", sa.Text(), nullable=False),
        sa.Column("parser_version", sa.Text(), nullable=False),
        sa.Column("engine_deps", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("error_class", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("output_key", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["replay_capture_id"], ["replay_captures.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("replay_capture_id", "parser_name", "parser_version"),
    )


def downgrade() -> None:
    op.drop_table("replay_parses")
    op.drop_index(op.f("ix_replay_access_log_user_id"), table_name="replay_access_log")
    op.drop_index(op.f("ix_replay_access_log_replay_capture_id"), table_name="replay_access_log")
    op.drop_table("replay_access_log")
    op.drop_index(
        "ix_profile_links_user_id_primary",
        table_name="profile_links",
        postgresql_where=sa.text("is_primary AND unlinked_at IS NULL"),
    )
    op.drop_index(op.f("ix_profile_links_user_id"), table_name="profile_links")
    op.drop_index(
        "ix_profile_links_profile_id_active",
        table_name="profile_links",
        postgresql_where=sa.text("unlinked_at IS NULL"),
    )
    op.drop_index(op.f("ix_profile_links_profile_id"), table_name="profile_links")
    op.drop_table("profile_links")
    op.drop_index(op.f("ix_steam_identities_user_id"), table_name="steam_identities")
    op.drop_table("steam_identities")
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_table("sessions")
    op.drop_index("ix_replay_captures_claim_order", table_name="replay_captures")
    op.drop_table("replay_captures")
    op.drop_table("rating_snapshots")
    op.drop_table("match_players")
    op.drop_table("data_requests")
    op.drop_table("alerts")
    op.drop_table("users")
    op.drop_table("provider_calls")
    op.drop_index(op.f("ix_matches_completed_at"), table_name="matches")
    op.drop_table("matches")
    op.drop_table("ingest_runs")
    op.drop_table("aoe_profiles")

    # Every table using these types is gone as of the line above — see the module docstring for
    # why they are not left to `drop_table`'s implicit, order-dependent cleanup.
    bind = op.get_bind()
    replay_capture_source.drop(bind, checkfirst=True)
    replay_capture_status.drop(bind, checkfirst=True)
    data_request_kind.drop(bind, checkfirst=True)
    alert_kind.drop(bind, checkfirst=True)
