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
    "csrf_states",
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


def test_csrf_states_hold_no_user_reference_and_track_consumption() -> None:
    """T028b: the table exists solely so a `state` can be marked consumed and checked for expiry
    server-side — it is minted before any session or user exists, so it must carry neither."""
    columns = set(_table("csrf_states").columns.keys())
    assert columns == {"id", "created_at", "expires_at", "consumed_at"}
    for forbidden in ("user_id", "session_id"):
        assert forbidden not in columns


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


def test_alert_kind_enum_has_the_six_documented_producers() -> None:
    # 003's data-model.md adds `analysis_cap_reached` (T304) — the sixth kind, sixth producer.
    assert {k.value for k in models.AlertKind} == {
        "rate_limited",
        "deadline_breach",
        "expired_capture",
        "validation_failed",
        "free_tier",
        "analysis_cap_reached",
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


# --- 003: player search, favourites and on-demand match analysis (T303) -------------------------
#
# `specs/003-player-search-match-analysis/data-model.md` adds five tables and widens two existing
# ones (`aoe_profiles`, `replay_access_log`). T304 is what actually adds them to `models.py`; every
# test below therefore imports `aoe2stats_storage.models` inside its own body rather than relying
# on the module-level import above. The module itself already exists and already imports cleanly
# either way — what does not exist yet is each specific table or column reached for below, and
# reaching for a missing key in `Base.metadata.tables[...]` raises inside the test body, which is
# an ordinary assertion-time failure `xfail(strict=True)` reports as expected, never a
# collection-time error that would take the rest of this file down with it. `strict=True` is what
# forces T304 to remove each marker rather than leaving a stale one that would hide a regression.


def test_favourites_primary_key_is_the_composite_user_and_profile_id() -> None:
    """FR-013's idempotence is the primary key, not application logic: marking the same profile
    twice inserts the same `(user_id, profile_id)` pair twice, and a primary key is what turns the
    second insert into a rejection instead of a second row. A plain `unique=True` on `profile_id`
    alone would be wrong here too — one user favourites many profiles."""
    from aoe2stats_storage import models

    table = models.Base.metadata.tables["favourites"]
    assert {c.name for c in table.primary_key.columns} == {"user_id", "profile_id"}


def test_profile_search_cache_is_keyed_on_the_normalised_query() -> None:
    """FR-004e: one row per normalised query. The primary key on `query_normalised` alone is what
    makes a write past the TTL a replace rather than a second, stale row sitting alongside the
    fresh one."""
    from aoe2stats_storage import models

    table = models.Base.metadata.tables["profile_search_cache"]
    assert {c.name for c in table.primary_key.columns} == {"query_normalised"}


def test_match_analyses_primary_key_is_game_id_alone_and_rejects_a_second_row_per_match() -> None:
    """FR-031 and FR-038 in full: `game_id` is the *entire* primary key, not part of a composite
    one alongside `point_of_view_profile_id` or anything else. A single-column primary key rejects
    a second insert for a `game_id` already present outright — there is no combination of other
    column values that lets two rows describe the same match — which is exactly what makes
    concurrent askers share one piece of work (R12) instead of racing to create two."""
    from aoe2stats_storage import models

    table = models.Base.metadata.tables["match_analyses"]
    assert {c.name for c in table.primary_key.columns} == {"game_id"}


def test_retained_recordings_unique_on_game_id_and_profile_id() -> None:
    """FR-033: a match is retained once per point of view. Same shape as `replay_captures`' own
    dedup constraint above — a `UniqueConstraint` distinct from the table's own `id` primary key,
    because `id` alone would let the same `(game_id, profile_id)` pair retain twice under two
    different surrogate ids."""
    from aoe2stats_storage import models

    table = models.Base.metadata.tables["retained_recordings"]
    unique_constraints = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
    dedup = next(
        (
            c
            for c in unique_constraints
            if {col.name for col in c.columns} == {"game_id", "profile_id"}
        ),
        None,
    )
    assert dedup is not None, "(game_id, profile_id) unique constraint is missing"


def test_rate_limit_counters_primary_key_is_the_three_column_window_key() -> None:
    """R10: one row per `(user, bucket, window)`, incremented with an upsert. All three columns
    together are the key — dropping any one of them would let two windows, two buckets or two
    users collapse into the same counter, which is exactly the failure a database-backed limiter
    exists to avoid on a platform with no shared process (constitution XII)."""
    from aoe2stats_storage import models

    table = models.Base.metadata.tables["rate_limit_counters"]
    assert {c.name for c in table.primary_key.columns} == {"user_id", "bucket", "window_start"}


def test_aoe_profiles_gains_alias_observed_at_and_never_hidden_observed_at() -> None:
    """FR-004c was retired on measurement: T301a found no hidden-profile signal at all in the
    source (`docs/data-sources.md` §3), and data-model.md is explicit that a column nothing can
    ever set must not be created. `alias_observed_at` is the one column this feature actually adds
    to `aoe_profiles`; asserting that `hidden_observed_at` stays absent is the point of this test,
    not a formality — a nullable column with no writer is indistinguishable from a forgotten one to
    every later reader."""
    from aoe2stats_storage import models

    columns = set(models.Base.metadata.tables["aoe_profiles"].columns.keys())
    assert "alias_observed_at" in columns
    assert "hidden_observed_at" not in columns


def test_replay_access_log_check_constraint_accepts_exactly_one_source() -> None:
    """FR-029: after this feature there are two kinds of archive a logged access can point at
    (`replay_captures` and `retained_recordings`), and a row that points at neither or both is a
    row that can mean nothing (data-model.md's own words). The predicate is
    `num_nonnulls(replay_capture_id, retained_recording_id) = 1`, and its truth table is the whole
    of the two negative cases this test exists for:

    - neither set: `num_nonnulls` = 0, `0 = 1` is false -> the row is rejected
    - both set:    `num_nonnulls` = 2, `2 = 1` is false -> the row is rejected
    - exactly one: `num_nonnulls` = 1, `1 = 1` is true  -> the row is accepted

    This suite has no live database to actually insert the two rejected shapes against (module
    docstring above), so the predicate text itself is what is pinned down here: any other
    formulation — including a nullable pair with no constraint at all, which is what this table
    carried before this feature — fails this assertion.
    """
    from aoe2stats_storage import models

    table = models.Base.metadata.tables["replay_access_log"]
    check_expressions = {str(c.sqltext) for c in table.constraints if hasattr(c, "sqltext")}
    assert "num_nonnulls(replay_capture_id, retained_recording_id) = 1" in check_expressions

    assert table.columns["replay_capture_id"].nullable, (
        "replay_capture_id must widen to nullable — a row can now carry retained_recording_id "
        "instead"
    )
    retained_recording_id = table.columns["retained_recording_id"]
    assert retained_recording_id.nullable
    fk = next(iter(retained_recording_id.foreign_keys))
    assert fk.column.table.name == "retained_recordings"
    assert fk.column.name == "id"
