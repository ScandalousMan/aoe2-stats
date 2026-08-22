"""Integration test for quickstart scenario 4 (T044): interruption loses nothing.

Targets `apps/ingester/src/aoe2stats_ingester/capture.py` (T055), which does not exist yet — see
`pytestmark` below. Every test imports `CaptureStage` from that module *inside* the test body
(never at module scope) so a missing module is a per-test `xfail`, not a collection error that
takes the whole workspace suite down (`.claude/skills` / CLAUDE.md's "test-first tasks" note).

**The contract this file assumes**, for whoever lands T055 — tasks.md names no constructor shape,
so this is the one this suite exercises and T055 must match:

- `CaptureStage` satisfies `aoe2stats_ingester.run.Stage` (`.name`, `async def __call__(self,
  budget)`), so it plugs into `run_once(budget_seconds, stages=[...])` (T018) exactly as
  `apps/ingester/tests/test_run.py`'s fakes do.
- Constructor keyword arguments: `session_factory`, `replay_provider` (a `ReplayProvider`,
  `packages/providers/src/aoe2stats_providers/base.py`), `object_store` (an `ObjectStore`,
  `packages/storage/src/aoe2stats_storage/objects.py`), `validator` (a `ReplayValidator`,
  `packages/core/src/aoe2stats_core/replay/validation.py`), `batch_size` (mirrors the `:batch`
  placeholder in data-model.md's claiming query) and `max_claim_age_seconds` (the reclaim
  threshold: "a claim older than the maximum function duration is stale and reclaimable").
- It claims with `FOR UPDATE SKIP LOCKED`, checks `budget` between claims and never mid-claim,
  reclaims stale `downloading` rows, resumes at validation (never re-downloads) when `zip_sha256`
  is already set, and — the one ordering `tasks.md`'s "The one ordering that is not negotiable"
  singles out — uploads the blob and commits it to the row *before* ever marking that row
  `stored` (FR-023, data-model.md's write ordering).

If T055 lands with a different shape, the fixtures below are what to adjust — the assertions are
the contract, the wiring around them is not.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.db import clean_database, database_url, db_session, engine, session_factory

import aoe2stats_ingester.budget as budget_module
from aoe2stats_core.replay.validation import MalformedArchiveError, ReplayValidationResult
from aoe2stats_ingester.run import run_once
from aoe2stats_providers.base import ReplayBlob
from aoe2stats_storage.models import AoeProfile, CaptureSource, CaptureStatus, Match, ReplayCapture
from aoe2stats_storage.objects import (
    REPLAY_CONTENT_TYPE,
    ObjectStore,
    ObjectStoreConfig,
    replay_object_key,
)

# Re-exported so ruff sees these names used: pytest discovers a fixture imported into a test
# module exactly as if it had been defined there (see `apps/ingester/tests/conftest.py`).
__all__ = ["clean_database", "database_url", "db_session", "engine", "session_factory"]

_LEADERBOARD_1V1_RM = 3
#: The platform's function ceiling `run.py`'s module docstring names — the value "the maximum
#: function duration" in data-model.md's `claimed_at` note refers to. Passed explicitly to
#: `CaptureStage` so this test never depends on whatever default the implementation might pick.
_MAX_CLAIM_AGE_SECONDS = 300


class FakeClock:
    """A settable stand-in for `time.monotonic` — the same shape `test_run.py` and
    `test_budget.py` already use, so `CaptureStage`'s own `Budget`/`iter_within_budget` usage
    (`budget.py`) can be driven deterministically instead of by real sleeps.
    """

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _replay_bytes(game_id: int, profile_id: int) -> bytes:
    """Deterministic per-capture content, so a test can tell one archived blob from another and
    recompute the checksum it expects `zip_sha256` to carry.
    """
    return f"replay-bytes-for-game-{game_id}-profile-{profile_id}".encode() * 50


def _parse_replay_key(key: str) -> tuple[int, int]:
    """The inverse of `replay_object_key` (`packages/storage/src/aoe2stats_storage/objects.py`):
    `"replays/{game_id}/{profile_id}.zip"` back to the ids that produced it.
    """
    _, game_id_str, profile_part = key.split("/")
    return int(game_id_str), int(profile_part.removesuffix(".zip"))


def _object_store_config() -> ObjectStoreConfig:
    return ObjectStoreConfig(
        endpoint_url="https://example.eu.r2.cloudflarestorage.com",
        bucket="aoe2-stats-replays-test",
        access_key_id="AKIAEXAMPLE",
        secret_access_key="shh",
        region="auto",
    )


class _FakeS3Client:
    """boto3-shaped enough for `ObjectStore` (`**kwargs`, exactly the `S3Client` Protocol in
    `packages/storage/src/aoe2stats_storage/objects.py`, mirroring `packages/storage/tests/
    test_objects.py`'s own fake), plus a durable `objects` dict a test can read back from —
    "retrievable" is checked against this, never against a `replay_captures` row's own claim
    about itself.
    """

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.put_calls: list[str] = []

    def put_object(self, **kwargs: Any) -> Any:
        key = kwargs["Key"]
        self.put_calls.append(key)
        self.objects[key] = kwargs["Body"]

    def get_object(self, **kwargs: Any) -> Any:
        key = kwargs["Key"]
        if key not in self.objects:
            raise KeyError(f"no object stored under {key!r}")
        return {"Body": io.BytesIO(self.objects[key])}

    def delete_object(self, **kwargs: Any) -> Any:
        self.objects.pop(kwargs["Key"], None)

    def generate_presigned_url(self, client_method: str, **kwargs: Any) -> Any:
        params = kwargs["Params"]
        return f"https://example.invalid/{params['Bucket']}/{params['Key']}?e={kwargs['ExpiresIn']}"

    def get_paginator(self, operation_name: str) -> Any:
        raise NotImplementedError("not exercised by this suite")


class _OrderCheckingObjectStore(ObjectStore):
    """Wraps a real `ObjectStore` to record, at the exact moment each upload happens, what
    `replay_captures.status` is *already committed* for that row — read through a session
    independent of whatever session `CaptureStage` itself holds open, so this observes the
    database's own view of the world rather than trusting a return value.

    This is what turns "no capture stored without a retrievable object" from a post-hoc count
    into a live ordering check: a mark-then-upload implementation would have already committed
    `status = 'stored'` by the time `put` is called for that capture's key, and only reading the
    database *during* the call, not after the whole run finishes, can catch that (tasks.md: "T055
    must implement upload-then-mark, never mark-then-upload... T044 exists to catch the reverse").
    """

    def __init__(
        self,
        config: ObjectStoreConfig,
        client: _FakeS3Client,
        session_factory: async_sessionmaker[AsyncSession],
        status_before_upload: dict[str, CaptureStatus],
    ) -> None:
        super().__init__(config, client=client)
        self._session_factory = session_factory
        self._status_before_upload = status_before_upload

    async def put(self, key: str, body: bytes, *, content_type: str = REPLAY_CONTENT_TYPE) -> None:
        game_id, profile_id = _parse_replay_key(key)
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    select(ReplayCapture).where(
                        ReplayCapture.game_id == game_id,
                        ReplayCapture.profile_id == profile_id,
                    )
                )
            ).scalar_one()
            self._status_before_upload[key] = row.status
        await super().put(key, body, content_type=content_type)


class _FakeReplayProvider:
    """A `ReplayProvider` (`packages/providers/src/aoe2stats_providers/base.py`) that always
    answers 200 with deterministic bytes per `(game_id, profile_id)`, and records every call so a
    test can assert a resumed-at-validation row issues none and a claim is never double-served.

    `clock`/`clock_advance_seconds` drive the deterministic budget test (`FakeClock`, above);
    `delay_seconds` drives real concurrency instead, where genuine overlap between two independent
    event loops' work is exactly what is under test and a fake clock cannot produce it.
    """

    def __init__(
        self,
        *,
        delay_seconds: float = 0.0,
        clock: FakeClock | None = None,
        clock_advance_seconds: float = 0.0,
    ) -> None:
        self._delay_seconds = delay_seconds
        self._clock = clock
        self._clock_advance_seconds = clock_advance_seconds
        self.calls: list[tuple[int, int]] = []

    async def fetch_replay(self, game_id: int, profile_id: int) -> ReplayBlob:
        self.calls.append((game_id, profile_id))
        if self._clock is not None:
            self._clock.advance(self._clock_advance_seconds)
        if self._delay_seconds:
            await asyncio.sleep(self._delay_seconds)
        return ReplayBlob(
            content=_replay_bytes(game_id, profile_id),
            filename=f"{game_id}.aoe2record",
            content_type="application/zip",
        )


class _FakeValidator:
    """A `ReplayValidator` (`packages/core/src/aoe2stats_core/replay/validation.py`) that always
    accepts: this suite is about claim/reclaim/upload ordering, not validation outcomes, so nothing
    here is ever `quarantined`.
    """

    def validate(self, zip_bytes: bytes) -> ReplayValidationResult:
        return ReplayValidationResult(
            inner_filename="game.aoe2record",
            inner_bytes=len(zip_bytes),
            engine_name="fake-engine",
            engine_version="0.0.0",
        )


class _AlwaysMalformedValidator:
    """A `ReplayValidator` that rejects every archive it is handed. Used only by the reclaim test
    that proves a stale `downloading` row is resumed *at validation*, not simply marked `stored`
    on the strength of a checksum already committed by a previous, now-dead run — the gap
    `apps/ingester/src/aoe2stats_ingester/capture.py`'s `_resume_reclaim` closes.
    """

    def validate(self, zip_bytes: bytes) -> ReplayValidationResult:
        raise MalformedArchiveError("not a zip: missing local file header")


async def _seed_pending_capture(
    session: AsyncSession,
    *,
    game_id: int,
    profile_id: int,
    completed_at: datetime,
    deadline_days: int = 21,
) -> None:
    session.add(AoeProfile(profile_id=profile_id, alias=f"player-{profile_id}"))
    session.add(
        Match(
            game_id=game_id,
            leaderboard_id=_LEADERBOARD_1V1_RM,
            completed_at=completed_at,
            source="relic",
            raw_payload={},
        )
    )
    session.add(
        ReplayCapture(
            game_id=game_id,
            profile_id=profile_id,
            status=CaptureStatus.PENDING,
            capture_deadline_at=completed_at + timedelta(days=deadline_days),
            source=CaptureSource.AUTOMATIC,
        )
    )


async def _mark_stale_downloading(
    session: AsyncSession,
    *,
    game_id: int,
    claimed_seconds_ago: float,
    object_key: str | None = None,
    zip_bytes: int | None = None,
    zip_sha256: str | None = None,
) -> None:
    """Simulate a run that claimed this capture and was killed before finishing — the state a
    process kill actually leaves, per quickstart scenario 4 step 3. Bypasses `CaptureStage`
    entirely: this is the state a *previous*, now-dead cycle left behind, not something this
    cycle's own claim query should ever produce.
    """
    await session.execute(
        update(ReplayCapture)
        .where(ReplayCapture.game_id == game_id)
        .values(
            status=CaptureStatus.DOWNLOADING,
            claimed_at=datetime.now(UTC) - timedelta(seconds=claimed_seconds_ago),
            attempts=1,
            object_key=object_key,
            zip_bytes=zip_bytes,
            zip_sha256=zip_sha256,
        )
    )


async def _capture_row(
    session_factory: async_sessionmaker[AsyncSession], game_id: int
) -> ReplayCapture:
    async with session_factory() as session:
        return (
            await session.execute(select(ReplayCapture).where(ReplayCapture.game_id == game_id))
        ).scalar_one()


async def _all_capture_rows(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[ReplayCapture]:
    async with session_factory() as session:
        return list((await session.execute(select(ReplayCapture))).scalars().all())


# --- scenario 4, step 1-2: a short budget stops cleanly, nothing left `downloading` --------------


async def test_a_short_budget_stops_cleanly_leaving_none_downloading(
    clean_database: None,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aoe2stats_ingester.capture import CaptureStage

    clock = FakeClock()
    monkeypatch.setattr(budget_module, "monotonic", clock)

    now = datetime.now(UTC)
    game_ids = list(range(90_001, 90_011))  # ten pending captures
    async with session_factory() as session:
        for offset, game_id in enumerate(game_ids):
            await _seed_pending_capture(
                session,
                game_id=game_id,
                profile_id=20_000 + offset,
                completed_at=now - timedelta(hours=1),
            )
        await session.commit()

    provider = _FakeReplayProvider(clock=clock, clock_advance_seconds=0.5)
    object_store = ObjectStore(_object_store_config(), client=_FakeS3Client())
    # batch_size=1: each claim is immediately followed by full processing, so a claim never
    # outlives the budget check that would otherwise leave it stranded in `downloading` — see the
    # module docstring's note on "checked between claims and never mid-claim".
    stage = CaptureStage(
        session_factory=session_factory,
        replay_provider=provider,
        object_store=object_store,
        validator=_FakeValidator(),
        batch_size=1,
        max_claim_age_seconds=_MAX_CLAIM_AGE_SECONDS,
    )

    await run_once(2, trigger="test", stages=[stage], session_factory=session_factory)

    rows = await _all_capture_rows(session_factory)
    statuses = [row.status for row in rows]
    assert CaptureStatus.DOWNLOADING not in statuses
    stored = statuses.count(CaptureStatus.STORED)
    pending = statuses.count(CaptureStatus.PENDING)
    # 0.5s per capture against a 2s budget: items starting at t=0, 0.5, 1.0, 1.5 all begin before
    # the deadline; the one that would start at t=2.0 does not (`budget.expired` at `>=`, exactly
    # `test_run.py`'s own boundary case for a stage that "would start... exactly at the deadline").
    assert stored == 4
    assert pending == 6
    assert stored + pending == len(game_ids)


# --- scenario 4, step 3-4: a killed process leaves `downloading`; the next cycle finishes it -----


async def test_a_stale_downloading_claim_without_bytes_is_reclaimed_and_completed(
    clean_database: None, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    from aoe2stats_ingester.capture import CaptureStage

    now = datetime.now(UTC)
    game_id, profile_id = 90_101, 30_001
    async with session_factory() as session:
        await _seed_pending_capture(
            session, game_id=game_id, profile_id=profile_id, completed_at=now - timedelta(hours=2)
        )
        await session.commit()
        # A previous run claimed this row and was killed before it ever committed any bytes.
        await _mark_stale_downloading(
            session, game_id=game_id, claimed_seconds_ago=_MAX_CLAIM_AGE_SECONDS * 3
        )
        await session.commit()

    provider = _FakeReplayProvider()
    fake_client = _FakeS3Client()
    stage = CaptureStage(
        session_factory=session_factory,
        replay_provider=provider,
        object_store=ObjectStore(_object_store_config(), client=fake_client),
        validator=_FakeValidator(),
        batch_size=10,
        max_claim_age_seconds=_MAX_CLAIM_AGE_SECONDS,
    )

    await run_once(30, trigger="test", stages=[stage], session_factory=session_factory)

    assert provider.calls == [(game_id, profile_id)]
    row = await _capture_row(session_factory, game_id)
    assert row.status == CaptureStatus.STORED
    content = _replay_bytes(game_id, profile_id)
    assert row.zip_sha256 == hashlib.sha256(content).hexdigest()
    assert fake_client.objects[replay_object_key(game_id, profile_id)] == content


# --- a stale claim that already carries the bytes resumes at validation, never re-fetches --------


async def test_a_stale_downloading_claim_with_bytes_already_committed_resumes_at_validation_only(
    clean_database: None, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    from aoe2stats_ingester.capture import CaptureStage

    now = datetime.now(UTC)
    game_id, profile_id = 90_201, 40_001
    content = _replay_bytes(game_id, profile_id)
    key = replay_object_key(game_id, profile_id)
    sha256 = hashlib.sha256(content).hexdigest()

    fake_client = _FakeS3Client()
    # The earlier, now-dead run's own upload — already durable before it was killed, which is
    # exactly what "upload before mark" makes survivable (FR-023, tasks.md).
    fake_client.objects[key] = content
    fake_client.put_calls.append(key)

    async with session_factory() as session:
        await _seed_pending_capture(
            session, game_id=game_id, profile_id=profile_id, completed_at=now - timedelta(hours=2)
        )
        await session.commit()
        await _mark_stale_downloading(
            session,
            game_id=game_id,
            claimed_seconds_ago=_MAX_CLAIM_AGE_SECONDS * 3,
            object_key=key,
            zip_bytes=len(content),
            zip_sha256=sha256,
        )
        await session.commit()

    provider = _FakeReplayProvider()
    stage = CaptureStage(
        session_factory=session_factory,
        replay_provider=provider,
        object_store=ObjectStore(_object_store_config(), client=fake_client),
        validator=_FakeValidator(),
        batch_size=10,
        max_claim_age_seconds=_MAX_CLAIM_AGE_SECONDS,
    )

    await run_once(30, trigger="test", stages=[stage], session_factory=session_factory)

    # No request to the replay endpoint at all: the row already carried `zip_sha256`.
    assert provider.calls == []
    # The blob was never re-uploaded either.
    assert fake_client.put_calls.count(key) == 1
    row = await _capture_row(session_factory, game_id)
    assert row.status == CaptureStatus.STORED
    assert row.zip_sha256 == sha256
    # Real validation ran — this is not merely a checksum-trusting mark — because only a run
    # through `_validate_with_barrier` ever sets `validated_by` (`_mark_stored`'s own contract).
    assert row.validated_by is not None


async def test_a_stale_downloading_claim_with_stored_bytes_failing_validation_is_quarantined(
    clean_database: None, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The reclaim path resumes *at validation*, it does not skip it: closes the gap left in
    T055's committed `capture.py`, where a stale `downloading` row carrying `zip_sha256` was
    marked `stored` outright, on the strength of a checksum a previous, now-dead run had already
    verified once and never re-checked. A malformed archive read back from the store must end
    `quarantined` (FR-026), exactly as it would if this were the first time it was ever validated.
    """
    from aoe2stats_ingester.capture import CaptureStage

    now = datetime.now(UTC)
    game_id, profile_id = 90_211, 40_011
    content = _replay_bytes(game_id, profile_id)
    key = replay_object_key(game_id, profile_id)
    sha256 = hashlib.sha256(content).hexdigest()

    fake_client = _FakeS3Client()
    # The earlier, now-dead run's own upload — already durable and already committed, exactly the
    # state a process kill between the metadata commit and validation leaves behind.
    fake_client.objects[key] = content
    fake_client.put_calls.append(key)

    async with session_factory() as session:
        await _seed_pending_capture(
            session, game_id=game_id, profile_id=profile_id, completed_at=now - timedelta(hours=2)
        )
        await session.commit()
        await _mark_stale_downloading(
            session,
            game_id=game_id,
            claimed_seconds_ago=_MAX_CLAIM_AGE_SECONDS * 3,
            object_key=key,
            zip_bytes=len(content),
            zip_sha256=sha256,
        )
        await session.commit()

    provider = _FakeReplayProvider()
    stage = CaptureStage(
        session_factory=session_factory,
        replay_provider=provider,
        object_store=ObjectStore(_object_store_config(), client=fake_client),
        validator=_AlwaysMalformedValidator(),
        batch_size=10,
        max_claim_age_seconds=_MAX_CLAIM_AGE_SECONDS,
    )

    await run_once(30, trigger="test", stages=[stage], session_factory=session_factory)

    # No re-download and no re-upload: the bytes were already durable.
    assert provider.calls == []
    assert fake_client.put_calls.count(key) == 1
    row = await _capture_row(session_factory, game_id)
    assert row.status == CaptureStatus.QUARANTINED
    assert row.status != CaptureStatus.STORED
    assert row.last_error is not None


# --- the one ordering that is not negotiable: upload before mark, never the reverse --------------


async def test_the_blob_is_durably_written_before_the_row_is_ever_marked_stored(
    clean_database: None, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    from aoe2stats_ingester.capture import CaptureStage

    now = datetime.now(UTC)
    game_id, profile_id = 90_301, 50_001
    async with session_factory() as session:
        await _seed_pending_capture(
            session, game_id=game_id, profile_id=profile_id, completed_at=now - timedelta(hours=1)
        )
        await session.commit()

    status_before_upload: dict[str, CaptureStatus] = {}
    fake_client = _FakeS3Client()
    object_store = _OrderCheckingObjectStore(
        _object_store_config(), fake_client, session_factory, status_before_upload
    )
    stage = CaptureStage(
        session_factory=session_factory,
        replay_provider=_FakeReplayProvider(),
        object_store=object_store,
        validator=_FakeValidator(),
        batch_size=10,
        max_claim_age_seconds=_MAX_CLAIM_AGE_SECONDS,
    )

    await run_once(30, trigger="test", stages=[stage], session_factory=session_factory)

    key = replay_object_key(game_id, profile_id)
    assert key in status_before_upload, "the upload never happened at all"
    # The row must not already say `stored` at the moment the blob is written — that is what a
    # mark-then-upload implementation would produce, and is the one thing this test exists to
    # catch (tasks.md: "T055 must implement upload-then-mark, never mark-then-upload").
    assert status_before_upload[key] != CaptureStatus.STORED

    row = await _capture_row(session_factory, game_id)
    assert row.status == CaptureStatus.STORED
    assert fake_client.objects[key] == _replay_bytes(game_id, profile_id)


# --- no blob written twice; no capture `stored` without a retrievable object ---------------------


async def test_every_stored_capture_has_exactly_one_matching_retrievable_object(
    clean_database: None, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    from aoe2stats_ingester.capture import CaptureStage

    now = datetime.now(UTC)
    seeds = [(90_401 + i, 60_001 + i) for i in range(5)]
    async with session_factory() as session:
        for game_id, profile_id in seeds:
            await _seed_pending_capture(
                session,
                game_id=game_id,
                profile_id=profile_id,
                completed_at=now - timedelta(hours=1),
            )
        await session.commit()

    fake_client = _FakeS3Client()
    stage = CaptureStage(
        session_factory=session_factory,
        replay_provider=_FakeReplayProvider(),
        object_store=ObjectStore(_object_store_config(), client=fake_client),
        validator=_FakeValidator(),
        batch_size=10,
        max_claim_age_seconds=_MAX_CLAIM_AGE_SECONDS,
    )

    await run_once(30, trigger="test", stages=[stage], session_factory=session_factory)

    rows = await _all_capture_rows(session_factory)
    assert all(row.status == CaptureStatus.STORED for row in rows)
    for game_id, profile_id in seeds:
        key = replay_object_key(game_id, profile_id)
        # Retrievable: the object is actually in the store, not merely claimed by the row.
        assert fake_client.objects[key] == _replay_bytes(game_id, profile_id)
        # Never written twice, even though nothing here crashed or retried.
        assert fake_client.put_calls.count(key) == 1


# --- two concurrent cycles claim disjoint captures and neither blocks on the other ---------------


async def test_two_concurrent_cycles_claim_disjoint_captures_and_neither_blocks_on_the_other(
    clean_database: None, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    from aoe2stats_ingester.capture import CaptureStage

    now = datetime.now(UTC)
    seeds = [(90_501 + i, 70_001 + i) for i in range(6)]
    async with session_factory() as session:
        for game_id, profile_id in seeds:
            await _seed_pending_capture(
                session,
                game_id=game_id,
                profile_id=profile_id,
                completed_at=now - timedelta(hours=1),
            )
        await session.commit()

    delay = 0.2  # real time: genuine overlap between two independent event-loop tasks is the point
    provider_a, provider_b = (
        _FakeReplayProvider(delay_seconds=delay),
        _FakeReplayProvider(delay_seconds=delay),
    )
    stage_a = CaptureStage(
        session_factory=session_factory,
        replay_provider=provider_a,
        object_store=ObjectStore(_object_store_config(), client=_FakeS3Client()),
        validator=_FakeValidator(),
        batch_size=3,
        max_claim_age_seconds=_MAX_CLAIM_AGE_SECONDS,
    )
    stage_b = CaptureStage(
        session_factory=session_factory,
        replay_provider=provider_b,
        object_store=ObjectStore(_object_store_config(), client=_FakeS3Client()),
        validator=_FakeValidator(),
        batch_size=3,
        max_claim_age_seconds=_MAX_CLAIM_AGE_SECONDS,
    )

    started = asyncio.get_event_loop().time()
    await asyncio.gather(
        run_once(30, trigger="cycle-a", stages=[stage_a], session_factory=session_factory),
        run_once(30, trigger="cycle-b", stages=[stage_b], session_factory=session_factory),
    )
    elapsed = asyncio.get_event_loop().time() - started

    all_calls = provider_a.calls + provider_b.calls
    assert sorted(all_calls) == sorted(seeds)
    # Disjoint: nothing appears in both logs, and nothing appears twice in the combined one — the
    # claim is never held twice, which is what `FOR UPDATE SKIP LOCKED` is there for.
    assert len(all_calls) == len(set(all_calls)) == len(seeds)
    assert provider_a.calls, "the concurrent cycle claimed nothing, which proves nothing here"
    assert provider_b.calls, "the concurrent cycle claimed nothing, which proves nothing here"
    # Neither blocked on the other: six items at `delay` each run fully sequentially would take
    # ~6 * delay; two cycles genuinely overlapping finish close to the slower one alone.
    assert elapsed < 5 * delay

    rows = await _all_capture_rows(session_factory)
    assert all(row.status == CaptureStatus.STORED for row in rows)


# --- a match finishing mid-cycle is picked up by the next cycle, never claimed twice --------------


async def test_a_capture_enqueued_mid_cycle_is_picked_up_by_the_next_cycle_with_no_double_claim(
    clean_database: None, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    from aoe2stats_ingester.capture import CaptureStage

    now = datetime.now(UTC)
    first_game_id, first_profile_id = 90_601, 80_001
    async with session_factory() as session:
        await _seed_pending_capture(
            session,
            game_id=first_game_id,
            profile_id=first_profile_id,
            completed_at=now - timedelta(hours=1),
        )
        await session.commit()

    provider = _FakeReplayProvider(delay_seconds=0.2)
    stage = CaptureStage(
        session_factory=session_factory,
        replay_provider=provider,
        object_store=ObjectStore(_object_store_config(), client=_FakeS3Client()),
        validator=_FakeValidator(),
        batch_size=1,
        max_claim_age_seconds=_MAX_CLAIM_AGE_SECONDS,
    )

    later_seeds = [(90_602, 80_002), (90_603, 80_003)]

    async def _enqueue_more_once_the_first_cycle_has_started() -> None:
        await asyncio.sleep(0.05)  # let cycle 1 claim before "two matches finish"
        async with session_factory() as session:
            for game_id, profile_id in later_seeds:
                await _seed_pending_capture(
                    session, game_id=game_id, profile_id=profile_id, completed_at=now
                )
            await session.commit()

    await asyncio.gather(
        run_once(30, trigger="cycle-1", stages=[stage], session_factory=session_factory),
        _enqueue_more_once_the_first_cycle_has_started(),
    )
    # Whatever cycle 1 did or did not see, cycle 2 discovers what remains `pending`.
    await run_once(30, trigger="cycle-2", stages=[stage], session_factory=session_factory)

    all_seeds = [(first_game_id, first_profile_id), *later_seeds]
    assert sorted(provider.calls) == sorted(all_seeds)
    assert len(provider.calls) == len(set(provider.calls))  # no capture claimed twice
    rows = await _all_capture_rows(session_factory)
    assert all(row.status == CaptureStatus.STORED for row in rows)
    assert {row.game_id for row in rows} == {game_id for game_id, _ in all_seeds}
