"""SQLAlchemy models for every entity in `specs/001-steam-link-replay-ingestion/data-model.md`.

The governing rule is constitution IV and the header of that document: `replay_captures` plus the
stored blob are the truth, everything else is derived and disposable. Only two things here are
sacred — `ReplayCapture` and the blob it points at (`object_key`, reached through
`aoe2stats_storage.objects`). Every other table is a rebuildable cache of a provider response.

This module defines the schema only: `Base`, its `Table` objects and their constraints. Engine,
session factory and repositories are `packages/storage/src/aoe2stats_storage/repositories/base.py`
(T009); the initial Alembic migration derived from this metadata is `infra/migrations/` (T008).
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import (
    Enum as SqlEnum,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base shared by every table in this schema."""


def _uuid_pk() -> Any:
    """A `uuid` primary key generated application-side (no `pgcrypto` dependency)."""
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


# --- Enumerations, one per status/kind field the data model gives a fixed vocabulary ------------
# `native_enum=True` (the default) creates a Postgres `ENUM` type, and `values_callable` stores the
# lowercase `.value` strings from data-model.md rather than the Python member names.


class CaptureStatus(enum.StrEnum):
    """`replay_captures.status` — see the state machine in data-model.md."""

    PENDING = "pending"
    DOWNLOADING = "downloading"
    STORED = "stored"
    UNAVAILABLE = "unavailable"
    EXPIRED = "expired"
    QUARANTINED = "quarantined"
    FAILED = "failed"


class CaptureSource(enum.StrEnum):
    """`replay_captures.source` (FR-033): who initiated the capture."""

    AUTOMATIC = "automatic"
    MANUAL = "manual"


class AlertKind(enum.StrEnum):
    """`alerts.kind` — six kinds, six producers, per data-model.md.

    `ANALYSIS_CAP_REACHED` is 003's own addition (severity 2): FR-047's cap has been hit and new
    analyses are being refused — the designed behaviour, not an incident, but a product decision
    that has come due and that nobody finds out from a log line. No kind exists for a failed
    analysis: FR-036 requires the user to be told and the failure recorded on `match_analyses`
    itself, and a per-match parse failure is an expected outcome of R3's memory bound.
    """

    RATE_LIMITED = "rate_limited"
    DEADLINE_BREACH = "deadline_breach"
    EXPIRED_CAPTURE = "expired_capture"
    VALIDATION_FAILED = "validation_failed"
    FREE_TIER = "free_tier"
    ANALYSIS_CAP_REACHED = "analysis_cap_reached"


class DataRequestKind(enum.StrEnum):
    """`data_requests.kind`."""

    EXPORT = "export"
    ERASURE = "erasure"
    THIRD_PARTY_OBJECTION = "third_party_objection"


class MatchAnalysisState(enum.StrEnum):
    """`match_analyses.state` — see the six-state table in
    `specs/003-player-search-match-analysis/data-model.md`. `running` means a lease was taken
    recently, never that work is happening now (R6); `lease_expires_at` is what makes an expired
    lease claimable again."""

    QUEUED = "queued"
    RUNNING = "running"
    PUBLISHED = "published"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"
    REFUSED = "refused"


def _enum_column(kind: type[enum.Enum], name: str) -> Any:
    return SqlEnum(
        kind, name=name, native_enum=True, values_callable=lambda e: [m.value for m in e]
    )


# --- Identity -------------------------------------------------------------------------------------


class User(Base):
    """`users` — no password, no email, no reset token (FR-006). Steam is the sole credential."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Null means the closed beta refuses them (FR-005).
    allowlisted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Constitution IX 4.0.0: archival rests on legitimate interest, not consent. Null means
    # archiving (the default for every linked profile, including one that has never answered any
    # question); set means the user has exercised the Art. 21 right to object, and no further
    # recordings of theirs are captured from that moment on (FR-035). Enforced in the query that
    # selects work, not in a later branch.
    archival_objected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    steam_identities: Mapped[list[SteamIdentity]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    sessions: Mapped[list[Session]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    profile_links: Mapped[list[ProfileLink]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class SteamIdentity(Base):
    """`steam_identities` — one completed sign-in. A user may hold several (FR-007)."""

    __tablename__ = "steam_identities"

    # As returned by `openid.claimed_id`, digits only.
    steam_id64: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # The moment `check_authentication` returned valid. Never inferred.
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_sign_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped[User] = relationship(back_populates="steam_identities")


class Session(Base):
    """`sessions` — server-side revocation, so sign-out is real and not cookie theatre.

    No user data, no roles, no payload: FR-006 makes Steam the only key, which makes the session
    the only thing this service can actually revoke.
    """

    __tablename__ = "sessions"

    # Opaque, 256 bits of randomness. Never derived from anything about the user.
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="sessions")


class CsrfState(Base):
    """`csrf_states` — server-side tracking for the OAuth CSRF `state` value (T028b).

    Minted before any session exists (`security.issue_csrf_state_cookie`), so — unlike `Session`
    above — it cannot be tied to a `user_id`. It gets the same discipline anyway: a row here, not
    only a claim the client's own cookie makes, is what lets `security.verify_csrf_state` refuse a
    `state` that has already been consumed or has simply expired, regardless of whether the
    browser ever obeyed `clear_csrf_state_cookie` and actually dropped its copy.
    """

    __tablename__ = "csrf_states"

    # The raw (unsigned) `state` value `generate_csrf_state` mints — opaque, 256 bits, same
    # entropy floor as a session id.
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Set the moment a callback consumes this state; `None` until then. A second callback carrying
    # the same value — even one whose cookie still verifies — finds this already set and is
    # refused, which is the check the client's own cookie-clearing behaviour cannot be trusted to
    # enforce on its own.
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# --- Profiles and matches — caches. Everything here can be re-fetched. ---------------------------


class AoeProfile(Base):
    """`aoe_profiles` — holds third parties too: every opponent and teammate.

    Their presence is what makes the GDPR processing register non-trivial. `alias` is the last one
    observed, not a history: there is no reason to track someone's name changes.
    """

    __tablename__ = "aoe_profiles"

    # Relic's identifier, not ours: a lone integer primary key is autoincrement by SQLAlchemy
    # default, which would let an insert omitting `profile_id` silently fabricate one instead of
    # failing (T007b).
    profile_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    alias: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[str | None] = mapped_column(Text)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # 003: the moment `alias` above was last observed at the source — the honesty half of "this
    # player has since renamed". There is deliberately no `hidden_observed_at`: it was designed as
    # FR-004c's memory, T301a measured the source and found no hidden signal to remember
    # (`docs/data-sources.md` §3), and FR-004c was retired. A nullable column nothing can ever set
    # is worse than no column — see data-model.md.
    alias_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProfileLink(Base):
    """`profile_links` — the association between a user and one of their player profiles.

    Two partial unique indexes carry the invariants a plain unique constraint cannot express:

    - ``ix_profile_links_profile_id_active`` — a profile belongs to one account **at a time**, not
      one account forever. Scoping the uniqueness to ``unlinked_at IS NULL`` is what lets an
      unlinked profile be relinked instead of reporting ``profile_already_linked`` forever.
    - ``ix_profile_links_user_id_primary`` — exactly one *active* primary link per user. Scoping to
      ``unlinked_at IS NULL`` as well as ``is_primary`` means an unlinked profile's former primary
      status never blocks a user from choosing a new primary among the links that remain.
    """

    __tablename__ = "profile_links"
    __table_args__ = (
        Index(
            "ix_profile_links_profile_id_active",
            "profile_id",
            unique=True,
            postgresql_where=text("unlinked_at IS NULL"),
        ),
        Index(
            "ix_profile_links_user_id_primary",
            "user_id",
            unique=True,
            postgresql_where=text("is_primary AND unlinked_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Unique across the whole table only while active — see the partial index above, not a plain
    # column-level unique=True.
    profile_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("aoe_profiles.profile_id"), nullable=False, index=True
    )
    # The identity that proved it.
    steam_id64: Mapped[str] = mapped_column(
        Text, ForeignKey("steam_identities.steam_id64", ondelete="CASCADE"), nullable=False
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Set rather than deleted, so capture history stays explicable.
    unlinked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set at link time, cleared once the 31-day sweep has run for this profile (T031a, T054). The
    # link cannot enqueue captures itself: there are no `matches` rows for a profile nobody has ever
    # polled.
    backfill_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="profile_links")


class Match(Base):
    """`matches` — one row per match, shared between users.

    `raw_payload` is the provider's response, unmodified (constitution IV): it is what lets a
    misinterpreted field be corrected months later without re-fetching anything, which matters
    because after 31 days there may be nothing left to re-fetch from.
    """

    __tablename__ = "matches"

    # Relic's identifier, not ours: a lone integer primary key is autoincrement by SQLAlchemy
    # default, which would let an insert omitting `game_id` silently fabricate one instead of
    # failing, and the (game_id, profile_id) dedup constraint on `replay_captures` cannot see a
    # duplicate hung off a phantom match (T007b).
    game_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    leaderboard_id: Mapped[int] = mapped_column(Integer, nullable=False)
    map_name: Mapped[str | None] = mapped_column(Text)
    patch: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Every `replay_captures.capture_deadline_at` is computed from this; it must always be known.
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MatchPlayer(Base):
    """`match_players` — one player's part in one match."""

    __tablename__ = "match_players"

    game_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("matches.game_id"), primary_key=True
    )
    profile_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("aoe_profiles.profile_id"), primary_key=True
    )
    team_id: Mapped[int | None] = mapped_column(SmallInteger)
    civ_id: Mapped[int | None] = mapped_column(SmallInteger)
    color_id: Mapped[int | None] = mapped_column(SmallInteger)
    result: Mapped[str | None] = mapped_column(Text)
    rating: Mapped[int | None] = mapped_column(Integer)
    rating_diff: Mapped[int | None] = mapped_column(Integer)


class RatingSnapshot(Base):
    """`rating_snapshots` — append-only, one row per observation per cycle.

    Daily granularity is what a daily cron can honestly produce, and it is enough to draw a rating
    curve.
    """

    __tablename__ = "rating_snapshots"

    profile_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("aoe_profiles.profile_id"), primary_key=True
    )
    leaderboard_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    rank: Mapped[int | None] = mapped_column(Integer)
    wins: Mapped[int | None] = mapped_column(Integer)
    losses: Mapped[int | None] = mapped_column(Integer)
    streak: Mapped[int | None] = mapped_column(Integer)
    highest_rating: Mapped[int | None] = mapped_column(Integer)


# --- Capture — the sacred part ----------------------------------------------------------------


class ReplayCapture(Base):
    """`replay_captures` — the table the entire feature turns on.

    See the state machine, the claiming query and the write ordering in data-model.md; this class
    only carries the columns and the constraint that *is* deduplication (FR-018).
    """

    __tablename__ = "replay_captures"
    __table_args__ = (
        # This constraint is the deduplication: two beta users in the same game produce one
        # `matches` row and two `replay_captures` rows, never two for the same profile.
        UniqueConstraint("game_id", "profile_id", name="uq_replay_captures_game_id_profile_id"),
        # Mirrors the claiming query in data-model.md: `WHERE status = 'pending' AND
        # next_attempt_at <= now() ORDER BY capture_deadline_at ASC`.
        Index(
            "ix_replay_captures_claim_order",
            "status",
            "next_attempt_at",
            "capture_deadline_at",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    game_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("matches.game_id"), nullable=False)
    # Whose point of view.
    profile_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("aoe_profiles.profile_id"), nullable=False
    )
    status: Mapped[CaptureStatus] = mapped_column(
        _enum_column(CaptureStatus, "replay_capture_status"),
        nullable=False,
        default=CaptureStatus.PENDING,
    )
    # `completed_at + CAPTURE_BUDGET_DAYS`, read from settings. Computed on insert, never
    # recomputed, and never restated as a literal: the budget must be lowerable in one place the
    # day the window is observed to shrink.
    capture_deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Backoff lives here, not in a scheduler.
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Set when a run claims the row; a claim older than the maximum function duration is stale and
    # reclaimable.
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # `stored_at - completed_at` is the capture lag. Null until the blob is durable.
    stored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    object_key: Mapped[str | None] = mapped_column(Text)
    zip_bytes: Mapped[int | None] = mapped_column(BigInteger)
    zip_sha256: Mapped[str | None] = mapped_column(Text)
    inner_filename: Mapped[str | None] = mapped_column(Text)
    inner_bytes: Mapped[int | None] = mapped_column(BigInteger)
    source: Mapped[CaptureSource] = mapped_column(
        _enum_column(CaptureSource, "replay_capture_source"), nullable=False
    )
    # For diagnosis, never for control flow.
    http_status: Mapped[int | None] = mapped_column(Integer)
    last_error: Mapped[str | None] = mapped_column(Text)
    # Parser engine and version used at capture-time validation.
    validated_by: Mapped[str | None] = mapped_column(Text)


class ReplayParse(Base):
    """`replay_parses` — created now, populated in V2.

    Capture-time validation does not write here: `replay_captures.validated_by` already records
    the engine and version. An empty table is a cleaner V2 seam than one seeded with rows that mean
    something different from every row V2 will add.
    """

    __tablename__ = "replay_parses"

    replay_capture_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("replay_captures.id", ondelete="CASCADE"), primary_key=True
    )
    parser_name: Mapped[str] = mapped_column(Text, primary_key=True)
    parser_version: Mapped[str] = mapped_column(Text, primary_key=True)
    engine_deps: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str | None] = mapped_column(Text)
    error_class: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    output_key: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# --- Operations and rights --------------------------------------------------------------------


class IngestRun(Base):
    """`ingest_runs` — inserted when the run starts, closed at the end.

    Not written in one go at the end: every `alerts` row carries `ingest_run_id`, and four of the
    five producers fire during the drain or immediately after it, so a row that did not exist yet
    would orphan them. A run that dies leaves an open row with a null `finished_at`, which is itself
    a signal.

    The absence of a row at all is the bigger signal: the nightly job reads the newest one and fails
    if it is older than 30 hours.
    """

    __tablename__ = "ingest_runs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    budget_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    profiles_polled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    matches_discovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    captures_attempted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stored_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unavailable_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Named here because constitution I names it. Expected to be permanently zero; the nightly
    # audit asserts exactly that.
    expired_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quarantined_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    alerts_raised: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    backlog_remaining: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Over newly discovered captures only — including backfill would describe how far back a rescue
    # reached rather than how fast the cadence is, and SC-002 is a statement about the cadence.
    capture_lag_p50_seconds: Mapped[int | None] = mapped_column(Integer)
    capture_lag_p95_seconds: Mapped[int | None] = mapped_column(Integer)


class Alert(Base):
    """`alerts` — pulled, never pushed. Nothing in phase 1 is always-on.

    Severity is not decoration: the nightly audit fails only on an unacknowledged severity-1 row.
    """

    __tablename__ = "alerts"
    __table_args__ = (CheckConstraint("severity IN (1, 2)", name="ck_alerts_severity_range"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    kind: Mapped[AlertKind] = mapped_column(_enum_column(AlertKind, "alert_kind"), nullable=False)
    severity: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    raised_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ingest_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingest_runs.id")
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProviderCall(Base):
    """`provider_calls` — the evidence base for whether we are being a good guest to the sources.

    No response body: FR-012 exempts everything re-queryable, and the two irrecoverable sources
    have their own homes (`matches.raw_payload` and the object store). A generic body column here
    would be a third copy with no reader and a GDPR surface with no purpose.
    """

    __tablename__ = "provider_calls"

    id: Mapped[uuid.UUID] = _uuid_pk()
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    called_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    rate_limited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ReplayAccessLog(Base):
    """`replay_access_log` — required by FR-040. These files hold other people's gameplay and
    chat; who opened one is a fact worth keeping.

    Goes with the captures it describes on erasure: `ondelete="CASCADE"` on both foreign keys means
    the rows disappear together with either the capture or the user, matching the deletion order
    described in data-model.md's `data_requests` section.

    Widened by 003 (`specs/003-player-search-match-analysis/data-model.md`): after that feature
    there are two kinds of archive a logged access can point at — a user's own `replay_captures`
    row, served on request, or a third party's `retained_recordings` row, read only by
    `apps/analyzer`. `replay_capture_id` becomes nullable and `retained_recording_id` is added,
    nullable, so the check constraint below is what makes a row that means nothing impossible to
    insert rather than merely inadvisable — the alternative, a second access-log table, was
    rejected because an audit that reads one table reports a clean trail for rows nobody checked.
    """

    __tablename__ = "replay_access_log"
    __table_args__ = (
        # The exact predicate data-model.md pins down: Postgres's own null-counting function, not
        # a pair of `IS NULL` comparisons, so it reads as the requirement itself. T305's migration
        # must emit this same string.
        CheckConstraint(
            "num_nonnulls(replay_capture_id, retained_recording_id) = 1",
            name="ck_replay_access_log_exactly_one_source",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    # Nullable since 003: a row may instead carry `retained_recording_id`. See the check
    # constraint above for the invariant this alone cannot express.
    replay_capture_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("replay_captures.id", ondelete="CASCADE"),
        index=True,
    )
    # 003: a system read of a third party's already-public recording — never a download, and
    # never served to anyone (see `RetainedRecording` below and R8).
    retained_recording_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("retained_recordings.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    purpose: Mapped[str] = mapped_column(Text, nullable=False)


class DataRequest(Base):
    """`data_requests` — an export, erasure or third-party objection, and how it was resolved.

    `subject_user_id` is nulled rather than cascaded on erasure (`ondelete="SET NULL"`): this row
    is the accountability record for the erasure itself and must survive it, per SC-008 requiring
    the request be verifiably resolved even once the subject is gone.
    """

    __tablename__ = "data_requests"

    id: Mapped[uuid.UUID] = _uuid_pk()
    kind: Mapped[DataRequestKind] = mapped_column(
        _enum_column(DataRequestKind, "data_request_kind"), nullable=False
    )
    subject_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    subject_profile_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("aoe_profiles.profile_id")
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str | None] = mapped_column(Text)


# --- 003: player search, favourites and on-demand match analysis --------------------------------
# Five new tables, per `specs/003-player-search-match-analysis/data-model.md`. `aoe_profiles` and
# `replay_access_log` above are the two existing tables that feature widens.


class Favourite(Base):
    """`favourites` — one user's private mark on one player.

    The composite primary key *is* FR-013's idempotence: marking the same profile twice inserts
    the same `(user_id, profile_id)` pair twice, which a primary key turns into a rejection rather
    than a second row, and unmarking is a delete that cannot leave a duplicate behind.

    Private to its owner, always (FR-015): there is no query anywhere in this feature that counts
    favourites by `profile_id`, and none may be added here — "how many people follow this player"
    is a fact this system must not be able to answer. A row here never causes capture, ingestion or
    archival of anything (FR-012); the per-user count bound (FR-016) is enforced on insert, in the
    repository, not in this schema.
    """

    __tablename__ = "favourites"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    profile_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("aoe_profiles.profile_id"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProfileSearchCache(Base):
    """`profile_search_cache` — FR-004e. One row per normalised query.

    `query_normalised` (lowercased, whitespace-trimmed, Unicode-normalised) alone is the primary
    key, so a write past the TTL is a replace rather than a second, stale row sitting alongside the
    fresh one. `results` holds only the fields `PlayerSearchResult` carries — never a verbatim copy
    of the provider's response, which would additionally store the account-linking claim FR-004b
    exists to keep out of this system (see `contracts/providers.md`).

    Sheds its own rows: entries older than the configured TTL are deleted opportunistically on
    write (same reasoning as `rate_limit_counters` below), because FR-044 forbids a job that clears
    it on a timer and nothing here is keyed to a user for erasure to reach.
    """

    __tablename__ = "profile_search_cache"

    query_normalised: Mapped[str] = mapped_column(Text, primary_key=True)
    results: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    # `index=True` (T386): the opportunistic prune below is a `DELETE ... WHERE fetched_at <
    # threshold` run on every successful cache write, across the whole table — without an index
    # here that scan degrades linearly with the very thing the prune exists to bound.
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)


class MatchAnalysis(Base):
    """`match_analyses` — one row per match, ever.

    The primary key on `game_id` alone *is* FR-031 and FR-038, enforced by the database rather than
    a check in application code: it is what makes a double-click fetch the same recording once
    (R12), because there is no combination of other column values that lets a second row describe
    the same match.

    `state` never means "work is happening now" while `running` — R6 forces that distinction, and
    `lease_expires_at` is what makes it operational: a row whose lease has expired is `running` in
    name and claimable in fact. Nothing sweeps expired leases (FR-044); the next viewer's request
    takes it.

    `attempts` bounds retry of a *transient* failure only. A recording that fails to parse goes
    straight to `failed` on the first attempt, because a parse is deterministic and a second
    attempt is a second identical failure that costs a fetch (FR-036, constitution V).

    `result_key` points at the published analysis in the object store, not a `jsonb` column here —
    the analysis of a long game is large, read whole or not at all, and never queried by its
    contents (same shape as `replay_parses.output_key`).

    `requested_by_user_id` is nullable because erasure clears it while the row survives: the
    analysis is derived from a match's public record and shown to every viewer, so it is not the
    requester's personal data — who asked for it is.
    """

    __tablename__ = "match_analyses"

    game_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("matches.game_id"), primary_key=True, autoincrement=False
    )
    state: Mapped[MatchAnalysisState] = mapped_column(
        _enum_column(MatchAnalysisState, "match_analysis_state"),
        nullable=False,
        default=MatchAnalysisState.QUEUED,
    )
    point_of_view_profile_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    parser_name: Mapped[str | None] = mapped_column(Text)
    parser_version: Mapped[str | None] = mapped_column(Text)
    engine_deps: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # Cleared on erasure (`ondelete="SET NULL"`); the row and the published analysis survive it —
    # see the class docstring.
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_class: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    result_key: Mapped[str | None] = mapped_column(Text)


class RetainedRecording(Base):
    """`retained_recordings` — FR-033. A separate table from `replay_captures` on purpose (R9),
    so the two are never counted together — the schema is what makes counting them together
    impossible to do by accident.

    `object_key` uses its own prefix, distinct from `replay_object_key`, so the separation survives
    into the bucket where the free-tier watch and any bulk copy operate by prefix with no database
    to join against. `zip_sha256` is recorded at retention and verified on retrieval; the bytes are
    never modified.

    Erasure here is two different acts, and conflating them is what would break constitution IV:

    - erasure of the *requester* clears `requested_by_user_id` (`ondelete="SET NULL"`) and keeps
      the object and the row — the bytes are an already-public recording, not the requester's data,
      and deleting them would leave a published analysis nothing can recompute;
    - erasure or objection by a person *appearing in* the recording deletes the object and the row,
      and withdraws every analysis derived from it. That is the only route by which these bytes are
      ever deleted (FR-046, constitution IV).
    """

    __tablename__ = "retained_recordings"
    __table_args__ = (
        UniqueConstraint("game_id", "profile_id", name="uq_retained_recordings_game_id_profile_id"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    game_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("matches.game_id"), nullable=False)
    profile_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    zip_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    zip_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    retained_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


class RateLimitCounter(Base):
    """`rate_limit_counters` — R10. Fixed windows, one row per `(user, bucket, window)`,
    incremented with an upsert. Buckets: `search` (FR-005), `replay_download` (FR-028),
    `analysis_request` (FR-040).

    Database-backed rather than in-memory because there is no shared process on this platform
    (constitution XII): an in-memory counter would work on a VPS and silently count nothing on
    Vercel. Rows older than the longest window are disposable and pruned opportunistically on
    write — nothing sweeps them (FR-044).
    """

    __tablename__ = "rate_limit_counters"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    bucket: Mapped[str] = mapped_column(Text, primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
