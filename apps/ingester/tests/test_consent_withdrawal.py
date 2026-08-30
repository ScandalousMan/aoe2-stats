"""T089 — the edge case spec.md lists directly: "A user objects to replay archival while captures
are queued" (spec.md's Edge Cases section; FR-035).

**T089a (`apps/ingester/src/aoe2stats_ingester/capture.py`) does not exist yet.** Per this project's
test-first discipline (CLAUDE.md "Test-first tasks and the green-tree gate"), the test below is
marked `xfail(strict=True, reason="T089a not implemented yet")`. The import of
`aoe2stats_ingester.capture` happens inside the test body, per the same convention, so a missing
symbol is never a collection error that takes the whole `apps/ingester/tests` suite down — only this
one test's own xfail.

**Terminology note.** `tasks.md`'s own text for T089/T089a still says "consent is withdrawn" —
written before constitution IX's 4.0.0 amendment (2026-08-25, `specs/003-player-search-match-
analysis/tasks.md` Phase 12) retired the opt-in consent gate (`users.ingest_consent_at` /
`ingest_consent_withdrawn_at`) in favour of legitimate interest plus a mandatory right to object
(`users.archival_objected_at`, a single nullable timestamp — T403). The mechanism this test
exercises is the current one: a user exercises the Art. 21 right to object while one of their
captures is already `pending`. `specs/001-steam-link-replay-ingestion/data-model.md` names the
fault directly, in the claiming section: "The claim joins through `profile_links` to
`users` and applies the archival predicate above. It is checked **here as well as at discovery**,
and the second check is not redundant: discovery decides whose matches are _found_, the claim
decides whose bytes are _fetched_, and between the two sits a queue that can be days deep. A user
who objects with captures already `pending` is exactly the case FR-035 is about, and only this
clause answers it (T089a)."

**Why this is not T404's job.** T404 (`specs/003-player-search-match-analysis/tasks.md`) already
split `apps/ingester/src/aoe2stats_ingester/discover.py`'s gate into `_linked_profile_ids()` and
`_archiving_profile_ids()` — `apps/ingester/tests/test_capture_objection.py` (T402) is what proves
an objecting user gets no *new* capture enqueued. But a capture enqueued *before* the objection is
already sitting in `replay_captures` as `pending`, and `CaptureDrain._claim_batch`
(`apps/ingester/src/aoe2stats_ingester/capture.py`) claims strictly on `status = 'pending' AND
next_attempt_at <= now()` — no join to `profile_links` or `users` at all, confirmed by reading the
module as of this test's writing. Discovery's fix does nothing for a row that already exists.

**The fake provider is the assertion, not a helper around one** (the same shape
`test_consent_gate.py` and `test_capture_objection.py` use for their own "forbidden id" fakes):
`fetch_replay` raises immediately if it is ever asked about the objecting user's queued capture,
which is what proves the exclusion has to be a property of the claim query itself and not a branch
downstream of a provider call that has already happened. A non-objecting control user's own pending
capture is seeded alongside it and answered successfully, so a `CaptureDrain` that simply claimed
nothing at all this cycle cannot pass this test by accident — the control capture must actually
reach `stored` for the run to have done real work.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_providers.base import ReplayBlob
from aoe2stats_storage.models import (
    AoeProfile,
    CaptureSource,
    CaptureStatus,
    Match,
    ProfileLink,
    ReplayCapture,
    SteamIdentity,
    User,
)

_CAPTURE_BUDGET_DAYS = 21
_REPLAY_PUBLICATION_GRACE_HOURS = 72

#: The objecting user's profile and its already-queued capture, seeded `pending` before the
#: objection is recorded — the exact shape spec.md's edge case and data-model.md's claiming section
#: both describe.
_OBJECTING_PROFILE_ID = 220_000_001
_OBJECTING_GAME_ID = 920_000_001

#: A non-objecting control user, seeded so a `CaptureDrain` that claims nothing at all this cycle
#: cannot pass this test by accident.
_CONTROL_PROFILE_ID = 220_000_002
_CONTROL_GAME_ID = 920_000_002


class _ForbiddingReplayProvider:
    """Raises immediately if ever asked to fetch the objecting user's queued replay; answers any
    other request with a small, well-formed `ReplayBlob` so the control capture can run the whole
    store-and-validate path for real.
    """

    def __init__(self) -> None:
        self.fetched_game_ids: list[int] = []

    async def fetch_replay(self, game_id: int, profile_id: int) -> ReplayBlob:
        assert game_id != _OBJECTING_GAME_ID, (
            f"CaptureDrain fetched game_id={game_id} for profile_id={profile_id}, whose user had "
            "already objected to archival (users.archival_objected_at) before this capture was "
            "claimed. The claim query must apply the same archival predicate discovery does "
            "(data-model.md's claiming section) — an objection with captures already 'pending' "
            "must stop the very next claim from fetching them, not merely stop new ones from "
            "being enqueued."
        )
        self.fetched_game_ids.append(game_id)
        return ReplayBlob(
            content=b"a well-formed control replay",
            filename="MP Replay v101.101 @2026.08.29 120000 (1).aoe2record",
            content_type="application/zip",
        )


class _FakeObjectStore:
    def __init__(self) -> None:
        self.put_calls: list[tuple[str, bytes]] = []

    async def put(self, key: str, body: bytes, *, content_type: str = "application/zip") -> None:
        self.put_calls.append((key, body))

    async def get(self, key: str) -> bytes:  # pragma: no cover - no reclaim in this scenario
        raise AssertionError("no capture in this scenario is ever a reclaim")


class _FakeReplayEngine:
    """Always validates successfully — this test is not about validation, only about which
    captures the claim even reaches.
    """

    def validate(self, zip_bytes: bytes):
        from aoe2stats_core.replay.validation import ReplayValidationResult

        return ReplayValidationResult(
            inner_filename="MP Replay v101.101 @2026.08.29 120000 (1).aoe2record",
            inner_bytes=len(zip_bytes),
            engine_name="fake",
            engine_version="0.0.0",
        )


class _FakeAlertSink:
    def __init__(self) -> None:
        self.written: list[dict] = []

    async def write(self, *, kind, severity, detail, ingest_run_id):
        record = {"kind": kind, "severity": severity, "detail": detail}
        self.written.append(record)
        return record

    async def unacknowledged_severity_one(self):
        return []


async def _seed_linked_user(
    db_session: AsyncSession,
    *,
    profile_id: int,
    game_id: int,
    archival_objected: bool,
) -> uuid.UUID:
    """Insert a fully linked user with one `pending` `replay_captures` row already enqueued for
    their own point of view — the queue that sits between discovery and the claim (data-model.md's
    claiming section) — and, only for the objecting case, an `archival_objected_at` recorded
    *after* that row was already `pending`, exactly as an objection arriving mid-queue would.
    """
    now = datetime.now(UTC)
    completed_at = now - timedelta(hours=1)
    user_id = uuid.uuid4()
    steam_id64 = f"76561198{profile_id:010d}"

    db_session.add(
        User(
            id=user_id,
            created_at=now,
            allowlisted_at=now,
            archival_objected_at=now if archival_objected else None,
        )
    )
    db_session.add(
        SteamIdentity(
            steam_id64=steam_id64,
            user_id=user_id,
            verified_at=now,
            last_sign_in_at=now,
        )
    )
    # Flushed before `ProfileLink` is added: `ProfileLink.steam_id64` has a column-level
    # `ForeignKey` to `steam_identities` but no ORM `relationship()` connects the two classes, so
    # the unit of work's automatic dependency sort has no edge telling it `steam_identities` must
    # land first (the same gap `test_consent_gate.py` and `test_capture_objection.py` both
    # document and work around identically).
    await db_session.flush()
    db_session.add(
        AoeProfile(
            profile_id=profile_id,
            alias=f"player-{profile_id}",
            first_seen_at=now,
            last_seen_at=now,
        )
    )
    db_session.add(
        ProfileLink(
            id=uuid.uuid4(),
            user_id=user_id,
            profile_id=profile_id,
            steam_id64=steam_id64,
            is_primary=True,
            linked_at=now,
        )
    )
    db_session.add(
        Match(
            game_id=game_id,
            leaderboard_id=3,
            completed_at=completed_at,
            duration_seconds=1800,
            source="relic",
            raw_payload={},
        )
    )
    db_session.add(
        ReplayCapture(
            id=uuid.uuid4(),
            game_id=game_id,
            profile_id=profile_id,
            status=CaptureStatus.PENDING,
            capture_deadline_at=completed_at + timedelta(days=_CAPTURE_BUDGET_DAYS),
            attempts=0,
            next_attempt_at=now - timedelta(minutes=1),
            first_seen_at=completed_at,
            source=CaptureSource.AUTOMATIC,
        )
    )
    # Committed here, mid-test: the drain below opens its own session through `session_factory`, a
    # separate connection from `db_session` — an uncommitted insert on this one is invisible to
    # that one until this runs.
    await db_session.commit()
    return user_id


async def test_a_capture_queued_before_objection_is_not_downloaded_on_the_next_cycle(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The edge case, verbatim from spec.md: "A user objects to replay archival while captures are
    queued." A `replay_captures` row already `pending` for a user who has since recorded
    `archival_objected_at` must not be claimed and downloaded on the next drain cycle (FR-035) — the
    claim query, not merely the discovery query, must respect the objection.
    """
    from aoe2stats_ingester.budget import Budget
    from aoe2stats_ingester.capture import CaptureDrain

    await _seed_linked_user(
        db_session,
        profile_id=_OBJECTING_PROFILE_ID,
        game_id=_OBJECTING_GAME_ID,
        archival_objected=True,
    )
    await _seed_linked_user(
        db_session,
        profile_id=_CONTROL_PROFILE_ID,
        game_id=_CONTROL_GAME_ID,
        archival_objected=False,
    )

    replay_provider = _ForbiddingReplayProvider()
    object_store = _FakeObjectStore()
    engine = _FakeReplayEngine()
    alert_sink = _FakeAlertSink()

    drain = CaptureDrain(
        session_factory=session_factory,
        replay_provider=replay_provider,
        object_store=object_store,
        engine=engine,
        alert_sink=alert_sink,
        capture_budget_days=_CAPTURE_BUDGET_DAYS,
        replay_publication_grace_hours=_REPLAY_PUBLICATION_GRACE_HOURS,
    )
    assert drain.name == "drain"

    await drain(Budget(seconds=60))

    # The objecting user's queued capture must never have reached the provider at all — asserted
    # both as "the fake never raised" (implicit: the call above would already have failed) and
    # explicitly here, so a future change to the fake cannot silently weaken the assertion.
    assert _OBJECTING_GAME_ID not in replay_provider.fetched_game_ids

    async with session_factory() as session:
        objecting_capture = await session.scalar(
            select(ReplayCapture).where(ReplayCapture.game_id == _OBJECTING_GAME_ID)
        )
        assert objecting_capture is not None
        assert objecting_capture.status == CaptureStatus.PENDING, (
            "A capture already queued when its owner objects must be left exactly as queued, "
            "never claimed — withdrawal stops further capture (FR-035); erasure, not this, is "
            "what removes what was already captured (FR-037)."
        )
        assert objecting_capture.object_key is None
        assert objecting_capture.stored_at is None

        # The control capture is the proof this cycle did real work: a `CaptureDrain` that simply
        # claimed nothing at all this run would otherwise make the assertions above pass by
        # accident.
        control_capture = await session.scalar(
            select(ReplayCapture).where(ReplayCapture.game_id == _CONTROL_GAME_ID)
        )
        assert control_capture is not None
        assert control_capture.status == CaptureStatus.STORED
    assert replay_provider.fetched_game_ids == [_CONTROL_GAME_ID]
