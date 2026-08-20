"""Structural tests for `aoe2stats_storage.models`.

These assert against `Base.metadata` directly rather than against a live database. The `python` CI
job that runs `uv run pytest -q` has no Postgres service (only the `migrations` job does, against
`infra/migrations/`, T008) — so this suite is what proves the schema is *defined* as
`data-model.md` requires: every table, every column, and — the part a plain unit test would
otherwise miss entirely — the exact predicate of every partial index and constraint.
"""

from __future__ import annotations

from sqlalchemy import Index, Table, UniqueConstraint
from sqlalchemy.dialects import postgresql

from aoe2stats_storage import models
from aoe2stats_storage.models import Base

EXPECTED_TABLES = {
    "users",
    "steam_identities",
    "aoe_profiles",
    "profile_links",
    "matches",
    "match_players",
    "rating_snapshots",
    "replay_captures",
    "replay_parses",
    "ingest_runs",
    "provider_calls",
    "replay_access_log",
    "data_requests",
    "sessions",
    "alerts",
}


def _table(name: str) -> Table:
    return Base.metadata.tables[name]


def _index_where_sql(index: Index) -> str:
    where = index.dialect_options["postgresql"]["where"]
    assert where is not None, f"{index.name} has no partial-index predicate"
    return str(where.compile(dialect=postgresql.dialect()))


def test_every_entity_from_data_model_has_a_table() -> None:
    assert set(Base.metadata.tables) >= EXPECTED_TABLES


def test_users_carries_no_credential_columns() -> None:
    columns = set(_table("users").columns.keys())
    assert columns == {
        "id",
        "created_at",
        "allowlisted_at",
        "ingest_consent_at",
        "ingest_consent_withdrawn_at",
    }
    # FR-006: no password column, no email column, no reset token. A column that does not exist
    # cannot leak.
    for forbidden in ("password", "email", "reset_token"):
        assert forbidden not in columns


def test_sessions_hold_only_an_opaque_reference() -> None:
    columns = set(_table("sessions").columns.keys())
    assert columns == {"id", "user_id", "created_at", "expires_at", "revoked_at"}


def test_replay_captures_has_claimed_at_and_the_dedup_constraint() -> None:
    table = _table("replay_captures")
    assert "claimed_at" in table.columns

    unique_constraints = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
    dedup = next(
        (
            c
            for c in unique_constraints
            if {col.name for col in c.columns} == {"game_id", "profile_id"}
        ),
        None,
    )
    assert dedup is not None, (
        "(game_id, profile_id) unique constraint — this constraint is the dedup"
    )


def test_replay_captures_status_enum_matches_the_state_machine() -> None:
    values = set(models.CaptureStatus)
    assert {v.value for v in values} == {
        "pending",
        "downloading",
        "stored",
        "unavailable",
        "expired",
        "quarantined",
        "failed",
    }


def test_profile_links_partial_index_lets_an_unlinked_profile_relink() -> None:
    table = _table("profile_links")
    index = next(i for i in table.indexes if i.name == "ix_profile_links_profile_id_active")
    assert index.unique
    assert {c.name for c in index.columns} == {"profile_id"}
    assert _index_where_sql(index) == "unlinked_at IS NULL"


def test_profile_links_partial_index_enforces_one_primary_per_user() -> None:
    table = _table("profile_links")
    index = next(i for i in table.indexes if i.name == "ix_profile_links_user_id_primary")
    assert index.unique
    assert {c.name for c in index.columns} == {"user_id"}
    assert _index_where_sql(index) == "is_primary AND unlinked_at IS NULL"


def test_profile_links_backfill_requested_at_exists_and_is_nullable() -> None:
    column = _table("profile_links").columns["backfill_requested_at"]
    assert column.nullable


def test_alerts_severity_is_constrained_to_one_or_two() -> None:
    check_expressions = {
        str(c.sqltext) for c in _table("alerts").constraints if hasattr(c, "sqltext")
    }
    assert "severity IN (1, 2)" in check_expressions


def test_alert_kind_enum_has_the_five_documented_producers() -> None:
    assert {k.value for k in models.AlertKind} == {
        "rate_limited",
        "deadline_breach",
        "expired_capture",
        "validation_failed",
        "free_tier",
    }


def test_data_requests_erasure_leaves_the_row_but_nulls_the_subject() -> None:
    column = _table("data_requests").columns["subject_user_id"]
    assert column.nullable
    fk = next(iter(column.foreign_keys))
    assert fk.ondelete == "SET NULL"


def test_replay_access_log_goes_with_its_capture_on_erasure() -> None:
    columns = _table("replay_access_log").columns
    capture_fk = next(iter(columns["replay_capture_id"].foreign_keys))
    user_fk = next(iter(columns["user_id"].foreign_keys))
    assert capture_fk.ondelete == "CASCADE"
    assert user_fk.ondelete == "CASCADE"


def test_matches_raw_payload_is_not_nullable() -> None:
    # constitution IV: the provider's raw response is sacred and must always be present.
    assert not _table("matches").columns["raw_payload"].nullable


def test_externally_owned_ids_do_not_autoincrement() -> None:
    # `matches.game_id` and `aoe_profiles.profile_id` hold Relic's identifiers, not ours. A lone
    # integer primary key is autoincrement by SQLAlchemy default, which would let an insert that
    # omits the id silently fabricate one (1, 2, 3...) instead of failing loudly — and the
    # (game_id, profile_id) constraint that is FR-018's deduplication would then be unable to see
    # that the real row is a duplicate (T007b).
    assert _table("matches").columns["game_id"].autoincrement is False
    assert _table("aoe_profiles").columns["profile_id"].autoincrement is False


def test_erasure_cascades_from_users_to_identities_sessions_and_links() -> None:
    for table_name, fk_column in (
        ("steam_identities", "user_id"),
        ("sessions", "user_id"),
        ("profile_links", "user_id"),
    ):
        column = _table(table_name).columns[fk_column]
        fk = next(iter(column.foreign_keys))
        assert fk.ondelete == "CASCADE", f"{table_name}.{fk_column} must cascade on user erasure"
