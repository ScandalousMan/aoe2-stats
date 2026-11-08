"""T459n, T459s, FR-037: an erased user's recording left behind by a dying writer is removed by
the sweep, which reads the `erased_recording_keys` records the erasure writes.

Two sources of the same leftover: the drain killed between its `put_if_absent` and its cleanup
delete, and an erasure whose post-commit delete failed. The sweep deletes a recorded key only when
the key parses (guard 1), no capture row exists for its pair (guard 2) and no live link names its
profile (guard 3). A record is dropped once older than the drain's stale-claim bound, only after
being examined. Each contrast test names the guard that keeps the object.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.links import link_profile

from aoe2stats_core.replay.validation import ReplayValidationResult
from aoe2stats_ingester import budget as budget_module
from aoe2stats_ingester import discover, erased_recordings
from aoe2stats_ingester.budget import Budget
from aoe2stats_ingester.capture import CaptureDrain
from aoe2stats_ingester.erased_recordings import sweep_erased_recordings
from aoe2stats_providers.base import NotFound, ReplayBlob
from aoe2stats_storage.models import (
    AoeProfile,
    CaptureSource,
    CaptureStatus,
    ErasedRecordingKey,
    Match,
    ProfileLink,
    ReplayCapture,
)
from aoe2stats_storage.objects import REPLAY_CONTENT_TYPE, replay_object_key

_GAME_ID = 920_001
_PROFILE_ID = 7_391
_KEY = replay_object_key(_GAME_ID, _PROFILE_ID)
_BYTES = b"an erased user's recording" * 20


class _Store:
    """In-memory store with the real contract of the four calls the drain and the sweep make."""

    def __init__(self, objects: Mapping[str, bytes] | None = None) -> None:
        self.objects: dict[str, bytes] = dict(objects or {})
        self.metadata: dict[str, dict[str, str]] = {}
        self.deleted: list[str] = []
        self.fail_delete = False
        self.fail_list_with: Exception | None = None
        self.after_write: Callable[[], Awaitable[None]] | None = None
        self.on_delete: Callable[[], None] | None = None
        self.list_calls = 0
        self.events: list[str] = []

    async def put_if_absent(
        self,
        key: str,
        body: bytes,
        *,
        content_type: str = REPLAY_CONTENT_TYPE,
        metadata: Mapping[str, str] | None = None,
    ) -> bool:
        self.events.append("put")
        if key in self.objects:
            return False
        self.objects[key] = body
        self.metadata[key] = dict(metadata or {})
        if self.after_write is not None:
            hook, self.after_write = self.after_write, None
            await hook()
        return True

    async def get(self, key: str) -> bytes:
        return self.objects[key]

    async def get_with_metadata(self, key: str) -> tuple[bytes, Mapping[str, str]]:
        return self.objects[key], self.metadata.get(key, {})

    async def delete(self, key: str) -> None:
        if self.fail_delete:
            raise ConnectionError(f"https://bucket.example/{key} refused")
        self.deleted.append(key)
        self.events.append("delete")
        self.objects.pop(key, None)
        if self.on_delete is not None:
            self.on_delete()

    async def list_keys(self, prefix: str = "") -> list[str]:
        self.list_calls += 1
        self.events.append("list")
        if self.fail_list_with is not None:
            raise self.fail_list_with
        return sorted(k for k in self.objects if k.startswith(prefix))


class _Provider:
    def __init__(self) -> None:
        self.on_fetch: Callable[[], Awaitable[None]] | None = None

    async def fetch_replay(self, game_id: int, profile_id: int) -> ReplayBlob | NotFound:
        if self.on_fetch is not None:
            await self.on_fetch()
        return ReplayBlob(
            content=_BYTES, filename=f"{game_id}.zip", content_type=REPLAY_CONTENT_TYPE
        )


class _Validator:
    def validate(self, zip_bytes: bytes) -> ReplayValidationResult:
        return ReplayValidationResult(
            inner_filename="MP Replay v101.101 @2026.10.16 120000 (1).aoe2record",
            inner_bytes=len(zip_bytes) * 2,
            engine_name="fake-engine",
            engine_version="0.0.0",
        )


def _drain(session_factory: async_sessionmaker[AsyncSession], provider: _Provider, store: _Store):
    return CaptureDrain(
        session_factory=session_factory,
        replay_provider=provider,
        object_store=store,
        validator=_Validator(),
        capture_budget_days=21,
        replay_publication_grace_hours=72,
        max_attempts=3,
    )


_BUDGET_DAYS = 21


async def _seed(session_factory: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    completed_at = datetime.now(UTC) - timedelta(days=1)
    capture_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(AoeProfile(profile_id=_PROFILE_ID, alias="Sweep Subject"))
        session.add(
            Match(
                game_id=_GAME_ID,
                leaderboard_id=3,
                completed_at=completed_at,
                source="test-fixture",
                raw_payload={},
            )
        )
        await session.flush()
        session.add(
            ReplayCapture(
                id=capture_id,
                game_id=_GAME_ID,
                profile_id=_PROFILE_ID,
                capture_deadline_at=completed_at + timedelta(days=21),
                source=CaptureSource.AUTOMATIC,
            )
        )
        await link_profile(session, _PROFILE_ID)
        await session.commit()
    return capture_id


async def _record(
    session_factory: async_sessionmaker[AsyncSession],
    key: str = _KEY,
    *,
    age: timedelta = timedelta(0),
) -> None:
    async with session_factory() as session:
        session.add(ErasedRecordingKey(key=key, recorded_at=datetime.now(UTC) - age))
        await session.commit()


async def _records(session_factory: async_sessionmaker[AsyncSession]) -> list[str]:
    async with session_factory() as session:
        return sorted((await session.scalars(select(ErasedRecordingKey.key))).all())


async def _erase_in(session: AsyncSession, capture_id: uuid.UUID, *, record: bool = True) -> None:
    """What `erase_account` commits for this pair: the row and the link gone, the key recorded."""
    await session.execute(delete(ReplayCapture).where(ReplayCapture.id == capture_id))
    await session.execute(delete(ProfileLink).where(ProfileLink.profile_id == _PROFILE_ID))
    if record:
        session.add(ErasedRecordingKey(key=_KEY))
    await session.flush()


async def _erase(session_factory: async_sessionmaker[AsyncSession], capture_id: uuid.UUID) -> None:
    async with session_factory() as session:
        await _erase_in(session, capture_id)
        await session.commit()


async def _sweep(
    session_factory: async_sessionmaker[AsyncSession],
    store: _Store,
    provider: _Provider,
    budget: Budget | None = None,
    *,
    lock_timeout_ms: int = 2_000,
) -> int:
    return await sweep_erased_recordings(
        store,
        session_factory,
        budget=budget or Budget(seconds=30),
        record_max_age_days=_BUDGET_DAYS,
        lock_timeout_ms=lock_timeout_ms,
    )


async def _drain_call(
    session_factory: async_sessionmaker[AsyncSession], store: _Store, provider: _Provider
) -> dict[str, int]:
    return dict(await _drain(session_factory, provider, store).__call__(Budget(seconds=30)))


async def test_a_drain_killed_between_its_write_and_its_cleanup_leaves_nothing_after_the_next_cycle(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Requirement 1: the erasure commits mid-download (row and link gone, key recorded), the
    drain's cleanup delete dies, the object stays with no row; the next drain call removes it."""
    capture_id = await _seed(session_factory)
    store = _Store()
    provider = _Provider()

    async def erase() -> None:
        await _erase(session_factory, capture_id)

    provider.on_fetch = erase
    store.fail_delete = True
    with pytest.raises(ConnectionError):
        await _drain_call(session_factory, store, provider)
    assert _KEY in store.objects, "the kill must leave the object behind"

    store.fail_delete = False
    provider.on_fetch = None
    report = await _drain_call(session_factory, store, provider)

    assert store.objects == {}, f"the bucket still holds {sorted(store.objects)}"
    assert report["erased_recording_keys_swept"] == 1


async def test_an_object_left_by_a_failed_post_commit_delete_is_removed(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Requirement 2: the erasure committed (row gone, key recorded) and its pass-3 delete never
    ran; a drain call removes the object."""
    capture_id = await _seed(session_factory)
    await _erase(session_factory, capture_id)
    store = _Store({_KEY: _BYTES})

    report = await _drain_call(session_factory, store, _Provider())

    assert report["erased_recording_keys_swept"] == 1
    assert store.objects == {}


async def test_a_placeholder_planted_through_the_objection_path_deletes_nothing(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Guard 1 of the mechanism itself: only an erasure's record names a key. A never-erased
    user's rowless object whose profile has a planted `-P` placeholder (what
    `touch_aoe_profile` creates for any id) is not recorded, so it is kept."""
    async with session_factory() as session:
        await discover.touch_aoe_profile(session, -_PROFILE_ID)
        await session.commit()
    store = _Store({_KEY: _BYTES})

    assert await _sweep(session_factory, store, _Provider()) == 0
    assert store.objects == {_KEY: _BYTES}


async def test_a_recorded_key_whose_profile_is_linked_again_is_kept_by_guard_3(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Guard 3: a profile erased and linked again whose manual upload has written its object but
    not committed its row. The link is live, so the object stays and the (young) record stays."""
    async with session_factory() as session:
        session.add(AoeProfile(profile_id=_PROFILE_ID, alias="Relinked"))
        await session.flush()
        await link_profile(session, _PROFILE_ID)
        await session.commit()
    await _record(session_factory)
    store = _Store({_KEY: _BYTES})

    assert await _sweep(session_factory, store, _Provider()) == 0
    assert store.objects == {_KEY: _BYTES}
    assert await _records(session_factory) == [_KEY]


async def test_a_live_link_keeps_the_object_but_the_record_still_ages_out(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    async with session_factory() as session:
        session.add(AoeProfile(profile_id=_PROFILE_ID, alias="Relinked"))
        await session.flush()
        await link_profile(session, _PROFILE_ID)
        await session.commit()
    await _record(session_factory, age=timedelta(days=_BUDGET_DAYS + 1))
    store = _Store({_KEY: _BYTES})

    assert await _sweep(session_factory, store, _Provider()) == 0
    assert store.objects == {_KEY: _BYTES}
    assert await _records(session_factory) == []


async def test_an_object_whose_row_exists_is_kept_by_guard_2(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Guard 2 (a row exists for the pair; the in-flight drain's case): kept, though recorded.
    The link is removed so only the row holds the object."""
    await _seed(session_factory)
    async with session_factory() as session:
        await session.execute(delete(ProfileLink))
        await session.commit()
    await _record(session_factory)
    store = _Store({_KEY: _BYTES})

    assert await _sweep(session_factory, store, _Provider()) == 0
    assert store.objects == {_KEY: _BYTES}


async def test_an_in_flight_drains_object_is_kept_while_its_row_does_not_name_it_yet(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Guard 2: another sweep runs after the drain's `put_if_absent` and before the row names the
    object. The row exists, so the object stays and the drain then stores it."""
    capture_id = await _seed(session_factory)
    await _record(session_factory)
    store = _Store()
    provider = _Provider()
    swept: list[int] = []

    async def sweep_now() -> None:
        async with session_factory() as session:
            await session.execute(delete(ProfileLink))
            await session.commit()
        swept.append(await _sweep(session_factory, store, provider))

    store.after_write = sweep_now
    await _drain(session_factory, provider, store).__call__(Budget(seconds=30))

    assert swept == [0]
    assert store.objects == {_KEY: _BYTES}
    async with session_factory() as session:
        row = await session.get(ReplayCapture, capture_id)
        assert row is not None and row.status is CaptureStatus.STORED


async def test_a_rolled_back_erasures_original_is_kept_because_no_record_exists(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """The record is written in the erasure's transaction: while it is open, and after it rolls
    back, the sweep sees none and keeps the original, which the row still names."""
    capture_id = await _seed(session_factory)
    async with session_factory() as session:
        row = await session.get(ReplayCapture, capture_id)
        assert row is not None
        row.object_key = _KEY
        await session.commit()
    store = _Store({_KEY: _BYTES})
    erasing = session_factory()
    try:
        await _erase_in(erasing, capture_id)
        assert await _sweep(session_factory, store, _Provider()) == 0
        await erasing.rollback()
    finally:
        await erasing.close()

    assert await _sweep(session_factory, store, _Provider()) == 0
    assert store.objects == {_KEY: _BYTES}
    assert await _records(session_factory) == []


async def test_a_malformed_key_is_never_deleted_and_its_aged_record_is_dropped(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Guard 1: a key that is not `replays/{game}/{profile}.zip` is not deleted."""
    bad = {
        f"retained-recordings/{_GAME_ID}/{_PROFILE_ID}.zip",
        f"replays/{_GAME_ID}/{_PROFILE_ID}.zip.bak",
    }
    for key in bad:
        await _record(session_factory, key, age=timedelta(days=_BUDGET_DAYS + 1))
    store = _Store(dict.fromkeys(bad, b"x"))

    assert await _sweep(session_factory, store, _Provider()) == 0
    assert set(store.objects) == bad
    assert await _records(session_factory) == []


async def test_an_aged_record_is_dropped_after_its_delete_and_a_young_one_is_kept(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Aging: both objects are deleted; only the record older than the stale-claim bound goes."""
    old_key = replay_object_key(930_001, 8_001)
    young_key = replay_object_key(930_002, 8_002)
    await _record(session_factory, old_key, age=timedelta(days=_BUDGET_DAYS + 1))
    await _record(session_factory, young_key, age=timedelta(days=1))
    store = _Store({old_key: _BYTES, young_key: _BYTES})

    assert await _sweep(session_factory, store, _Provider()) == 2
    assert store.objects == {}
    assert await _records(session_factory) == [young_key]


async def test_a_lock_timeout_skips_the_key_and_keeps_the_record(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """The row read waits for a holder only up to `lock_timeout_ms`: an erasure session holds the
    row `FOR UPDATE`, the sweep skips the key, and the record stays even though it has aged."""
    capture_id = await _seed(session_factory)
    async with session_factory() as session:
        await session.execute(delete(ProfileLink))
        await session.commit()
    await _record(session_factory, age=timedelta(days=_BUDGET_DAYS + 1))
    store = _Store({_KEY: _BYTES})
    holder = session_factory()
    try:
        await holder.execute(
            select(ReplayCapture).where(ReplayCapture.id == capture_id).with_for_update()
        )
        try:
            async with asyncio.timeout(10):
                swept = await _sweep(session_factory, store, _Provider(), lock_timeout_ms=200)
        except TimeoutError:
            pytest.fail("the row read outwaited its lock_timeout")
        assert swept == 0
    finally:
        await holder.rollback()
        await holder.close()

    assert store.objects == {_KEY: _BYTES}
    assert await _records(session_factory) == [_KEY]


async def test_a_failing_store_is_contained_and_the_log_carries_no_key_and_no_exc_info(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The sweep never raises; its warning is the type name and a count, never the key, and no
    record carries `exc_info`. The failed record stays."""
    # The test database's alembic run (`fileConfig`) disables loggers that already exist.
    monkeypatch.setattr(erased_recordings.logger, "disabled", False)
    capture_id = await _seed(session_factory)
    await _erase(session_factory, capture_id)
    store = _Store({_KEY: _BYTES})
    store.fail_delete = True

    with caplog.at_level(logging.INFO):
        assert await _sweep(session_factory, store, _Provider()) == 1

    text_ = "\n".join(record.getMessage() for record in caplog.records)
    assert "ConnectionError" in text_
    assert str(_PROFILE_ID) not in text_ and _KEY not in text_
    assert caplog.records and all(record.exc_info is None for record in caplog.records)
    assert store.objects == {_KEY: _BYTES}
    assert await _records(session_factory) == [_KEY]


async def _leave_recorded_objects(
    session_factory: async_sessionmaker[AsyncSession], count: int
) -> list[str]:
    keys = [replay_object_key(930_000 + offset, 8_000 + offset) for offset in range(count)]
    for offset, key in enumerate(keys):
        await _record(session_factory, key, age=timedelta(seconds=count - offset))
    return keys


async def test_a_sweep_given_an_expired_budget_reads_and_deletes_nothing(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Budget guard, outermost: nothing is read or deleted once the budget has expired."""
    keys = await _leave_recorded_objects(session_factory, 2)
    store = _Store(dict.fromkeys(keys, _BYTES))

    assert await _sweep(session_factory, store, _Provider(), Budget(seconds=0)) == 0
    assert store.deleted == []
    assert await _records(session_factory) == sorted(keys)


async def test_a_budget_that_expires_mid_sweep_stops_the_deletes(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Budget guard, per record: the fake clock jumps past the budget after the first delete, so
    of three eligible leftovers exactly the oldest is deleted."""
    clock = [1_000.0]
    monkeypatch.setattr(budget_module, "monotonic", lambda: clock[0])
    keys = await _leave_recorded_objects(session_factory, 3)
    store = _Store(dict.fromkeys(keys, _BYTES))

    def expire() -> None:
        clock[0] += 11.0

    store.on_delete = expire
    assert await _sweep(session_factory, store, _Provider(), Budget(seconds=10)) == 1
    assert store.deleted == [keys[0]]
    assert sorted(store.objects) == sorted(keys[1:])


async def test_the_sweep_runs_before_the_first_claim_and_the_claim_loop_still_runs(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Order: the recorded leftover of another pair is deleted before the queued row's object is
    written, and the queued row is then stored."""
    capture_id = await _seed(session_factory)
    (leftover,) = await _leave_recorded_objects(session_factory, 1)
    store = _Store({leftover: _BYTES})

    report = await _drain_call(session_factory, store, _Provider())

    assert store.events.index("delete") < store.events.index("put")
    assert leftover not in store.objects
    assert report["erased_recording_keys_swept"] == 1
    async with session_factory() as session:
        row = await session.get(ReplayCapture, capture_id)
        assert row is not None and row.status is CaptureStatus.STORED


async def test_an_upload_landing_after_the_sweeps_checks_is_not_deleted(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Exclusion on the record, T459t (1): the erased pair's user links again and uploads while the
    sweep is between its checks and its object delete. The upload deletes the key's record before
    its put, which waits for the sweep holding the record; the sweep deletes the old object first
    and the upload's write follows, so the upload's replay is in the bucket at the end."""
    capture_id = await _seed(session_factory)
    await _erase(session_factory, capture_id)
    store = _Store({_KEY: _BYTES})
    uploaded = b"the relinked user's upload" * 20
    tasks: list[asyncio.Task[None]] = []

    async def upload() -> None:
        async with session_factory() as session:
            await link_profile(session, _PROFILE_ID, second_user=True)
            await session.commit()
        async with session_factory() as session:
            await session.execute(delete(ErasedRecordingKey).where(ErasedRecordingKey.key == _KEY))
            # T459u: the record's delete is uncommitted while the object is put.
            await store.put_if_absent(_KEY, uploaded)
            await session.commit()

    real_delete = store.delete

    async def delete_while_an_upload_runs(key: str) -> None:
        tasks.append(asyncio.create_task(upload()))
        # The upload runs inline unless the sweep's lock holds it back.
        await asyncio.wait(tasks, timeout=0.5)
        await real_delete(key)

    store.delete = delete_while_an_upload_runs  # type: ignore[method-assign]
    await _sweep(session_factory, store, _Provider())
    await asyncio.wait_for(tasks[0], timeout=10)

    assert store.objects == {_KEY: uploaded}
    assert await _records(session_factory) == []


async def test_records_kept_past_a_sweep_do_not_starve_a_new_one(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T459t (3): with two kept records already examined and a batch of two, a record added since
    is examined first, so its object is deleted."""
    monkeypatch.setattr(erased_recordings, "MAX_RECORDS_EXAMINED", 2)
    kept = ["replays/not-a-pair/1", "replays/not-a-pair/2"]
    for offset, key in enumerate(kept):
        await _record(session_factory, key, age=timedelta(days=2, seconds=-offset))
    store = _Store()
    assert await _sweep(session_factory, store, _Provider()) == 0
    async with session_factory() as session:
        assert (await session.scalars(select(ErasedRecordingKey.swept_at))).all()
        assert all(
            swept is not None
            for swept in await session.scalars(select(ErasedRecordingKey.swept_at))
        )

    await _record(session_factory, _KEY)
    store.objects[_KEY] = _BYTES

    assert await _sweep(session_factory, store, _Provider()) == 1
    assert store.objects == {}


async def _swept_at(session_factory: async_sessionmaker[AsyncSession]) -> dict[str, bool]:
    """Key -> whether the sweep has marked it examined."""
    async with session_factory() as session:
        rows = await session.execute(select(ErasedRecordingKey.key, ErasedRecordingKey.swept_at))
        return {key: swept_at is not None for key, swept_at in rows.all()}


async def test_a_failing_key_is_marked_examined_and_the_keys_behind_it_are_still_swept(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """T459u (3): the oldest key's delete always fails; the two healthy keys behind it are deleted
    on the same run, the failing key is marked examined and keeps its record."""
    keys = await _leave_recorded_objects(session_factory, 3)
    store = _Store(dict.fromkeys(keys, _BYTES))
    real_delete = store.delete

    async def delete_failing_on_the_first(key: str) -> None:
        if key == keys[0]:
            raise ConnectionError(f"https://bucket.example/{key} refused")
        await real_delete(key)

    store.delete = delete_failing_on_the_first  # type: ignore[method-assign]

    assert await _sweep(session_factory, store, _Provider()) == 3

    assert store.deleted == keys[1:]
    assert store.objects == {keys[0]: _BYTES}
    assert await _records(session_factory) == sorted(keys)
    assert await _swept_at(session_factory) == dict.fromkeys(keys, True)


async def test_a_lock_timeout_does_not_mark_the_key_examined(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """T459u (3), contrast: a lock timeout still skips the key without marking it, and the keys
    behind it are still handled."""
    capture_id = await _seed(session_factory)
    async with session_factory() as session:
        await session.execute(delete(ProfileLink))
        await session.commit()
    await _record(session_factory, _KEY, age=timedelta(seconds=30))
    other = replay_object_key(930_500, 8_500)
    await _record(session_factory, other)
    store = _Store({_KEY: _BYTES, other: _BYTES})
    holder = session_factory()
    try:
        await holder.execute(
            select(ReplayCapture).where(ReplayCapture.id == capture_id).with_for_update()
        )
        assert await _sweep(session_factory, store, _Provider(), lock_timeout_ms=200) == 1
    finally:
        await holder.rollback()
        await holder.close()

    assert store.deleted == [other]
    assert await _swept_at(session_factory) == {_KEY: False, other: True}


async def test_failing_deletes_count_toward_the_cap_and_the_return_value(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T459u (B2): a store whose delete always fails, with more records than the cap: one sweep
    call issues at most the cap's number of deletes and returns that number."""
    monkeypatch.setattr(erased_recordings, "MAX_KEYS_SWEPT", 2)
    keys = await _leave_recorded_objects(session_factory, 5)
    attempts: list[str] = []
    store = _Store(dict.fromkeys(keys, _BYTES))

    async def always_fail(key: str) -> None:
        attempts.append(key)
        raise ConnectionError(f"https://bucket.example/{key} refused")

    store.delete = always_fail  # type: ignore[method-assign]

    assert await _sweep(session_factory, store, _Provider()) == 2
    assert attempts == keys[:2]
    assert await _records(session_factory) == sorted(keys)
