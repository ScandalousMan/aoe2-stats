"""Integration test for quickstart scenario 3 (T043): "Backfill rescues the window".

Targets the reconciliation stage T054 ships in `aoe2stats_ingester.reconcile` — not implemented
yet at this point in the sequence, hence the module-level `pytestmark` below. Neither module it
needs (`aoe2stats_ingester.reconcile`, `aoe2stats_ingester.capture`) exists on disk yet; both are
imported *inside* the test body rather than at module scope, per this project's test-first
convention (CLAUDE.md: a module-scope import of a not-yet-existent module is a collection error
that takes the whole workspace suite down, not merely this file's tests).

The requirement under test (quickstart.md scenario 3; FR-013 to FR-019, FR-042; SC-003, SC-005):
once a profile carries `profile_links.backfill_requested_at` (T031a), repeated cycles must drain
the resulting backlog until every match discoverable for that window has settled into exactly one
of two terminal outcomes — `stored`, checksummed and byte-identical to what was fetched, or
`expired` — and this must hold across **every** profile the user has linked, not only the one
`is_primary=True` marks (FR-042). "Cycles run until the backlog is empty" is exercised literally
below: the first call to the capture stage is handed an already-exhausted `Budget`, proving no
progress happens without one, before a further loop with an ordinary budget is what actually drains
the queue — one call finishing everything by coincidence would not distinguish this from a design
that ignores the budget entirely.

**Where the `stored` / `expired` line actually falls.** `data-model.md`'s state machine defines
`expired` as "past the retention window before we got it", and `contracts/providers.md` assigns
that three-way reading of an identical 404 to the caller, since only the caller holds
`matches.completed_at`. Nothing in `settings.py` or `.env.example` names the *true* source
retention (~31 days) as a tunable — the one number that is configured, `CAPTURE_BUDGET_DAYS`
(21), is commented there as "we never let a capture get closer than this", i.e. a deliberately
tighter margin the system controls, chosen specifically so nothing about a capture is ever cutting
it close against the real, unmeasurable retention window. `capture_deadline_at =
completed_at + CAPTURE_BUDGET_DAYS` is therefore the only threshold the caller can classify a 404
against, and this is what this test asserts: a match whose deadline has already elapsed by the time
its 404 is read is `expired` on the spot (matching T047/quickstart scenario 7's "a match completed
forty days ago yields expired... on the first attempt", no two-attempt floor — that floor belongs
only to the `unavailable` branch, for a match still inside its own deadline).

**Assumed contract for `ReconcileStage`** (T054), since `aoe2stats_ingester.reconcile` does not
exist yet and this test is what defines it, following the shape T053's own sibling tests already
established for `DiscoverStage` (`test_consent_gate.py`, `test_shared_match.py`) and T054a's own
`test_reconcile.py` (the 25-day half of this same module) already confirms independently: a `Stage`
(`aoe2stats_ingester.run.Stage`) built directly against a `session_factory` and a
`MatchHistoryProvider`, with `capture_budget_days` passed as a plain value rather than read from a
`Settings` object — `apps/ingester` cannot depend on `apps/api`, which is the one place `Settings`
lives today (`apps/api` depends on `apps/ingester`, never the reverse: `apps/api/src/aoe2stats_api/
routers/cron.py`).

    class ReconcileStage:
        def __init__(
            self, *, session_factory, match_history_provider, capture_budget_days: int
        ) -> None: ...
        name: str  # "reconcile" — run.py's own docstring: "in that order (discover, reconcile,
                   # drain)"
        async def __call__(self, budget: Budget) -> Mapping[str, Any]: ...

**Assumed contract for the capture/drain stage** (T055, then T056): `test_quarantine.py` (T047a)
already landed in this same batch and settled the class name and most of the constructor —
`CaptureDrain(*, session_factory, object_store, replay_provider, validator, alert_sink,
validation_timeout_seconds)` — which this file reuses rather than inventing a second, incompatible
shape for the same not-yet-existent module. None of `test_quarantine.py`'s own scenarios ever
produce a 404 (its fake `ReplayProvider` always answers 200), so its contract has no reason to
carry the one extra value this test's `expired` case does need: `replay_publication_grace_hours`,
the input to T056's three-way 404 reading — a task in the same file, sequenced immediately after
T055, that `test_quarantine.py` does not exercise at all. This file adds it as one further
keyword-only constructor argument on the same class, on the expectation that T056's own
implementation threads it through exactly where T055 left the constructor, the same way `capture.py`
itself accumulates T055, T056 and T057 in one module per `plan.md`'s file layout.

    class CaptureDrain:
        def __init__(
            self,
            *,
            session_factory,
            object_store: ObjectStore,
            replay_provider: ReplayProvider,
            validator: ReplayValidator,
            alert_sink: AlertSink,
            validation_timeout_seconds: float,
            replay_publication_grace_hours: int,
        ) -> None: ...
        name: str  # "drain"
        async def __call__(self, budget: Budget) -> Mapping[str, Any]: ...

`validator` is `packages/core`'s pluggable `ReplayValidator` Protocol (T013), injected
directly rather than the real `aoe2rec-py` adapter: this test is about the backfill/capture
*pipeline*, not capture-time validation itself (T047a owns that), and a fake validator lets
the fixture blobs below be arbitrary well-formed zips instead of genuine AoE2 replay bytes.
`alert_sink` is `packages/core`'s `AlertSink` Protocol (`aoe2stats_core.alerting`); nothing
here asserts on what it recorded — the `expired_capture` alert T056's own task text requires
belongs to T047's scenario, not this one's — it only has to exist so construction cannot fail
for want of one, exactly as `test_quarantine.py` already established.
"""

from __future__ import annotations

import hashlib
import io
import uuid
import zipfile
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_core.alerting import AlertRecord
from aoe2stats_core.replay.validation import ReplayValidationResult
from aoe2stats_ingester.budget import Budget
from aoe2stats_providers.base import NotFound, RawMatch, ReplayBlob
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
from aoe2stats_storage.objects import ObjectStore, ObjectStoreConfig, replay_object_key

pytestmark = pytest.mark.xfail(strict=True, reason="T054 not implemented yet")

_CAPTURE_BUDGET_DAYS = 21
_REPLAY_PUBLICATION_GRACE_HOURS = 72

_PROFILE_PRIMARY = 197_000_301
_PROFILE_SECONDARY = 197_000_302

# Recent, available on both profiles: expect `stored`.
_GAME_PRIMARY_RECENT = 611_000_301
_GAME_SECONDARY_RECENT = 611_000_303
# Old enough that `capture_deadline_at` (`completed_at` + 21 days) has already elapsed by the time
# the backfill sweep runs, and never available at the source: expect `expired` (FR-019).
_GAME_PRIMARY_OLD = 611_000_302

_MAX_DRAIN_CYCLES = 5


# --- Fixture doubles ------------------------------------------------------------------------


def _make_replay_zip(inner_filename: str, payload: bytes) -> bytes:
    """A genuine, well-formed single-member zip — data-model.md and quickstart scenario 3 both
    require every archived replay to be exactly this shape."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w") as archive:
        archive.writestr(inner_filename, payload)
    return buffer.getvalue()


class _FakeMatchHistoryProvider:
    """A `MatchHistoryProvider` double (`contracts/providers.md`) keyed by profile id, so the two
    linked profiles below can be given genuinely different match histories — the shape a real
    backfill sweep must fan out over per profile, not merge into one shared list."""

    def __init__(self, matches_by_profile: dict[int, list[RawMatch]]) -> None:
        self._matches_by_profile = matches_by_profile
        self.calls: list[tuple[int, ...]] = []

    async def recent_matches(self, profile_ids: Sequence[int]) -> list[RawMatch]:
        self.calls.append(tuple(profile_ids))
        by_game_id: dict[int, RawMatch] = {}
        for profile_id in profile_ids:
            for raw_match in self._matches_by_profile.get(profile_id, []):
                by_game_id[raw_match.game_id] = raw_match
        return list(by_game_id.values())


class _FakeReplayProvider:
    """A `ReplayProvider` double (`contracts/providers.md`): returns the seeded blob for a known
    `(game_id, profile_id)` pair, `NotFound` for everything else — exactly the wire condition a
    replay that has aged out of the source's retention produces."""

    def __init__(self, blobs: dict[tuple[int, int], bytes]) -> None:
        self._blobs = blobs
        self.calls: list[tuple[int, int]] = []

    async def fetch_replay(self, game_id: int, profile_id: int) -> ReplayBlob | NotFound:
        self.calls.append((game_id, profile_id))
        content = self._blobs.get((game_id, profile_id))
        if content is None:
            return NotFound()
        return ReplayBlob(
            content=content,
            filename=f"MP Replay {game_id}.aoe2record.zip",
            content_type="application/zip",
        )


class _FakeS3Client:
    """Satisfies `aoe2stats_storage.objects.S3Client` in memory — no bucket, no network
    (constitution III)."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_object(self, **kwargs: Any) -> Any:
        self.objects[kwargs["Key"]] = kwargs["Body"]
        return {}

    def delete_object(self, **kwargs: Any) -> Any:
        self.objects.pop(kwargs["Key"], None)
        return {}

    def generate_presigned_url(self, client_method: str, **kwargs: Any) -> Any:
        params = kwargs.get("Params", {})
        return f"https://fake-object-store.example/{params.get('Key')}"

    def get_paginator(self, operation_name: str) -> Any:
        raise NotImplementedError("this test never lists the bucket")


class _FakeAlertSink:
    """Satisfies `AlertSink` (`packages/core/src/aoe2stats_core/alerting.py`), the same shape
    `test_quarantine.py` already established for `CaptureDrain`'s own `alert_sink` argument.
    Nothing here asserts on `records` — the `expired_capture` alert T056's task text requires
    belongs to T047's own scenario — this only exists so construction cannot fail for want of one.
    """

    def __init__(self) -> None:
        self.records: list[AlertRecord] = []

    async def write(
        self,
        *,
        kind: str,
        severity: int,
        detail: Mapping[str, Any] | None,
        ingest_run_id: uuid.UUID | None,
    ) -> AlertRecord:
        record = AlertRecord(
            id=uuid.uuid4(),
            kind=kind,
            severity=severity,
            detail=detail,
            raised_at=datetime.now(UTC),
            ingest_run_id=ingest_run_id,
            acknowledged_at=None,
        )
        self.records.append(record)
        return record

    async def unacknowledged_severity_one(self) -> list[AlertRecord]:
        return [r for r in self.records if r.severity == 1 and r.acknowledged_at is None]


class _FakeReplayValidator:
    """Satisfies `packages/core`'s `ReplayValidator` Protocol. Always accepts a well-formed
    single-member zip — capture-time validation of a genuinely malformed archive is T047a's own
    scenario, not this one's."""

    def validate(self, zip_bytes: bytes) -> ReplayValidationResult:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            names = archive.namelist()
        assert len(names) == 1, "fixture blob must itself be a single-member zip"
        return ReplayValidationResult(
            inner_filename=names[0],
            inner_bytes=len(zip_bytes),
            engine_name="fake-engine",
            engine_version="0.0.0-test",
        )


# --- Seeding ----------------------------------------------------------------------------------


async def _seed_user_with_two_linked_profiles(
    session_factory: async_sessionmaker[AsyncSession],
) -> uuid.UUID:
    """One consenting user, two linked `aoe_profiles` — a primary and a secondary — each carrying
    its own proven `steam_identities` row (FR-007) and its own `backfill_requested_at` stamp
    (T031a), exactly what a fresh multi-account link leaves behind for T054 to find."""
    now = datetime.now(UTC)
    user = User(id=uuid.uuid4(), ingest_consent_at=now - timedelta(days=1))

    steam_primary = SteamIdentity(
        steam_id64="76500000000000301",
        user_id=user.id,
        verified_at=now - timedelta(days=1),
        last_sign_in_at=now - timedelta(days=1),
    )
    steam_secondary = SteamIdentity(
        steam_id64="76500000000000302",
        user_id=user.id,
        verified_at=now - timedelta(hours=1),
        last_sign_in_at=now - timedelta(hours=1),
    )

    profile_primary = AoeProfile(profile_id=_PROFILE_PRIMARY, alias="PrimaryPlayer", country="FR")
    profile_secondary = AoeProfile(
        profile_id=_PROFILE_SECONDARY, alias="SecondaryPlayer", country="FR"
    )

    link_primary = ProfileLink(
        id=uuid.uuid4(),
        user_id=user.id,
        profile_id=_PROFILE_PRIMARY,
        steam_id64=steam_primary.steam_id64,
        is_primary=True,
        linked_at=now - timedelta(days=1),
        backfill_requested_at=now - timedelta(days=1),
    )
    link_secondary = ProfileLink(
        id=uuid.uuid4(),
        user_id=user.id,
        profile_id=_PROFILE_SECONDARY,
        steam_id64=steam_secondary.steam_id64,
        is_primary=False,
        linked_at=now - timedelta(hours=1),
        backfill_requested_at=now - timedelta(hours=1),
    )

    async with session_factory() as session:
        session.add_all(
            [
                user,
                steam_primary,
                steam_secondary,
                profile_primary,
                profile_secondary,
                link_primary,
                link_secondary,
            ]
        )
        await session.commit()

    return user.id


def _object_store() -> tuple[ObjectStore, _FakeS3Client]:
    fake_client = _FakeS3Client()
    config = ObjectStoreConfig(
        endpoint_url="https://fake-object-store.example",
        bucket="test-replays",
        access_key_id="fake",
        secret_access_key="fake",
        region="eu",
    )
    return ObjectStore(config, client=fake_client), fake_client


async def _backlog_size(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(ReplayCapture)
            .where(ReplayCapture.status.in_([CaptureStatus.PENDING, CaptureStatus.DOWNLOADING]))
        )
    assert count is not None
    return int(count)


# --- The test -----------------------------------------------------------------------------------


async def test_backfill_sweep_stores_or_expires_every_match_across_all_linked_profiles(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
) -> None:
    from aoe2stats_ingester.capture import CaptureDrain
    from aoe2stats_ingester.reconcile import ReconcileStage

    now = datetime.now(UTC)
    await _seed_user_with_two_linked_profiles(session_factory)

    # -- Match history: two profiles, three matches, one already past its own capture deadline. --
    recent_primary = RawMatch(
        game_id=_GAME_PRIMARY_RECENT,
        leaderboard_id=3,
        map_name="Arabia",
        patch="stable",
        started_at=now - timedelta(days=5, minutes=35),
        completed_at=now - timedelta(days=5),
        duration_seconds=1_800,
        player_profile_ids=(_PROFILE_PRIMARY,),
        raw_payload={"matchId": _GAME_PRIMARY_RECENT, "source": "test_backfill fixture"},
    )
    old_primary = RawMatch(
        game_id=_GAME_PRIMARY_OLD,
        leaderboard_id=3,
        map_name="Arena",
        patch="stable",
        started_at=now - timedelta(days=25, minutes=40),
        completed_at=now - timedelta(days=25),
        duration_seconds=2_200,
        player_profile_ids=(_PROFILE_PRIMARY,),
        raw_payload={"matchId": _GAME_PRIMARY_OLD, "source": "test_backfill fixture"},
    )
    recent_secondary = RawMatch(
        game_id=_GAME_SECONDARY_RECENT,
        leaderboard_id=3,
        map_name="Black Forest",
        patch="stable",
        started_at=now - timedelta(days=3, minutes=20),
        completed_at=now - timedelta(days=3),
        duration_seconds=1_500,
        player_profile_ids=(_PROFILE_SECONDARY,),
        raw_payload={"matchId": _GAME_SECONDARY_RECENT, "source": "test_backfill fixture"},
    )
    match_history_provider = _FakeMatchHistoryProvider(
        {
            _PROFILE_PRIMARY: [recent_primary, old_primary],
            _PROFILE_SECONDARY: [recent_secondary],
        }
    )

    reconcile_stage = ReconcileStage(
        session_factory=session_factory,
        match_history_provider=match_history_provider,
        capture_budget_days=_CAPTURE_BUDGET_DAYS,
    )
    await reconcile_stage(Budget(seconds=60))

    # Both profiles must have been swept — this is FR-042 at the reconcile step, before capture
    # ever runs: a sweep that only ever asked about the primary profile could never produce a
    # `replay_captures` row for the secondary one at all.
    requested_profile_ids = {pid for call in match_history_provider.calls for pid in call}
    assert requested_profile_ids == {_PROFILE_PRIMARY, _PROFILE_SECONDARY}

    async with session_factory() as session:
        matches = (
            (
                await session.execute(
                    select(Match).where(
                        Match.game_id.in_(
                            [_GAME_PRIMARY_RECENT, _GAME_PRIMARY_OLD, _GAME_SECONDARY_RECENT]
                        )
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(matches) == 3, "the sweep must upsert a `matches` row for every match it found"

        links = (await session.execute(select(ProfileLink))).scalars().all()
    assert len(links) == 2
    for link in links:
        assert link.backfill_requested_at is None, (
            "T054: the flag is cleared only once the sweep has enqueued that profile's window — "
            "a link still carrying it would look, to the next cycle, like it was never swept"
        )

    async with session_factory() as session:
        captures = (await session.execute(select(ReplayCapture))).scalars().all()
    assert len(captures) == 3, "one `replay_captures` row per discovered match per profile"
    by_game_id = {capture.game_id: capture for capture in captures}
    for game_id, raw_match in (
        (_GAME_PRIMARY_RECENT, recent_primary),
        (_GAME_PRIMARY_OLD, old_primary),
        (_GAME_SECONDARY_RECENT, recent_secondary),
    ):
        capture = by_game_id[game_id]
        assert capture.status == CaptureStatus.PENDING
        assert capture.source == CaptureSource.AUTOMATIC
        assert capture.capture_deadline_at == raw_match.completed_at + timedelta(
            days=_CAPTURE_BUDGET_DAYS
        )
        assert capture.profile_id == raw_match.player_profile_ids[0]
    # The old match's own deadline is already behind "now" — this is the row this test expects
    # `capture`/`drain` to classify `expired` below, on the strength of the state machine's own
    # definition rather than an assumption this test merely repeats.
    assert by_game_id[_GAME_PRIMARY_OLD].capture_deadline_at < now

    # -- Capture: only the two recent matches' replays are still fetchable at the source. --------
    replay_content = {
        (_GAME_PRIMARY_RECENT, _PROFILE_PRIMARY): _make_replay_zip(
            "MP Replay primary-recent.aoe2record", b"primary-recent-bytes"
        ),
        (_GAME_SECONDARY_RECENT, _PROFILE_SECONDARY): _make_replay_zip(
            "MP Replay secondary-recent.aoe2record", b"secondary-recent-bytes"
        ),
        # No entry for (_GAME_PRIMARY_OLD, _PROFILE_PRIMARY): the source has nothing left for it.
    }
    replay_provider = _FakeReplayProvider(replay_content)
    object_store, fake_s3 = _object_store()
    validator = _FakeReplayValidator()

    capture_stage = CaptureDrain(
        session_factory=session_factory,
        object_store=object_store,
        replay_provider=replay_provider,
        validator=validator,
        alert_sink=_FakeAlertSink(),
        validation_timeout_seconds=5.0,
        replay_publication_grace_hours=_REPLAY_PUBLICATION_GRACE_HOURS,
    )

    # A cycle with no time left makes no progress at all — proving "cycles run until the backlog
    # is empty" describes something the budget actually gates, not one generous call that happens
    # to finish everything regardless of it (`budget.py`'s own tested contract:
    # `iter_within_budget` "yields nothing from an already expired budget").
    await capture_stage(Budget(seconds=0))
    assert await _backlog_size(session_factory) == 3
    assert replay_provider.calls == [], "an exhausted budget must not reach the provider at all"

    # Now drain for real, across as many cycles as it takes.
    for _ in range(_MAX_DRAIN_CYCLES):
        if await _backlog_size(session_factory) == 0:
            break
        await capture_stage(Budget(seconds=60))
    else:
        pytest.fail(
            f"backlog still non-empty after {_MAX_DRAIN_CYCLES} cycles — the drain never "
            "converges (quickstart scenario 3: 'Repeat until the report shows an empty backlog')"
        )

    async with session_factory() as session:
        captures = (await session.execute(select(ReplayCapture))).scalars().all()
    by_game_id = {capture.game_id: capture for capture in captures}

    # -- Every match settled into exactly one of `stored` or `expired`, and nothing else. --------
    statuses = {capture.game_id: capture.status for capture in captures}
    assert statuses == {
        _GAME_PRIMARY_RECENT: CaptureStatus.STORED,
        _GAME_SECONDARY_RECENT: CaptureStatus.STORED,
        _GAME_PRIMARY_OLD: CaptureStatus.EXPIRED,
    }

    # -- Every stored capture: checksum verified, single-member zip, byte-identical in the store,
    # and addressed by the production key scheme so the two profiles' blobs can never collide.
    for (game_id, profile_id), content in replay_content.items():
        capture = by_game_id[game_id]
        assert capture.profile_id == profile_id
        assert capture.stored_at is not None
        assert capture.zip_bytes == len(content)
        assert capture.zip_sha256 == hashlib.sha256(content).hexdigest(), (
            "SC-005: every archived replay is retrievable and byte-for-byte identical to what "
            "was captured, verified by checksum"
        )
        expected_key = replay_object_key(game_id, profile_id)
        assert capture.object_key == expected_key
        stored_bytes = fake_s3.objects.get(expected_key)
        assert stored_bytes == content, "the blob in the object store must match what was fetched"
        with zipfile.ZipFile(io.BytesIO(stored_bytes)) as archive:
            assert len(archive.namelist()) == 1, (
                "quickstart scenario 3: 'each blob is a single-member zip'"
            )

    # -- The expired capture: no blob, no checksum, an honest failure recorded — never silently
    # dropped and never mistaken for `stored` or for `unavailable` (data-model.md: "expired counts
    # our failures, unavailable counts the game's").
    expired_capture = by_game_id[_GAME_PRIMARY_OLD]
    assert expired_capture.stored_at is None
    assert expired_capture.object_key is None
    assert expired_capture.zip_sha256 is None
    assert (_GAME_PRIMARY_OLD, _PROFILE_PRIMARY) in replay_provider.calls

    # -- FR-042: captures cover all linked profiles, not only the primary one. --------------------
    assert {capture.profile_id for capture in captures} == {_PROFILE_PRIMARY, _PROFILE_SECONDARY}
    secondary_capture = by_game_id[_GAME_SECONDARY_RECENT]
    assert secondary_capture.profile_id == _PROFILE_SECONDARY
    assert secondary_capture.status == CaptureStatus.STORED, (
        "FR-042: a non-primary linked profile's replays must be archived exactly like the "
        "primary's — never silently skipped because it is not the one shown by default"
    )
