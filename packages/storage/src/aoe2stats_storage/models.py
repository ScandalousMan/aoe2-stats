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
    """`alerts.kind` — five kinds, five producers, per data-model.md."""

    RATE_LIMITED = "rate_limited"
    DEADLINE_BREACH = "deadline_breach"
    EXPIRED_CAPTURE = "expired_capture"
    VALIDATION_FAILED = "validation_failed"
    FREE_TIER = "free_tier"


class DataRequestKind(enum.StrEnum):
    """`data_requests.kind`."""

    EXPORT = "export"
    ERASURE = "erasure"
    THIRD_PARTY_OBJECTION = "third_party_objection"


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
    # Null means capture nothing. Enforced in the query that selects work, not in a later branch.
    ingest_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Kept after withdrawal; erasure is a separate act.
    ingest_consent_withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

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
    """

    __tablename__ = "replay_access_log"

    id: Mapped[uuid.UUID] = _uuid_pk()
    replay_capture_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("replay_captures.id", ondelete="CASCADE"),
        nullable=False,
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
