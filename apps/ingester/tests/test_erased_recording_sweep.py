"""T459n, FR-037: an erased user's recording left behind by a dying writer is removed by the sweep.

Two sources of the same leftover: the drain killed between its `put_if_absent` and its cleanup
delete, and an erasure whose post-commit delete failed. In both, the erasure has committed: the
rows are gone and the placeholder `aoe_profiles` row `-profile_id` is committed. The sweep
(`aoe2stats_ingester.erased_recordings`) removes a replay key only when its profile's placeholder
exists (guard 3) and no capture row exists for its pair (guard 2); the key's shape is guard 1.
Each contrast test names the guard that keeps the object.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.links import link_profile

from aoe2stats_core.replay.validation import ReplayValidationResult
from aoe2stats_ingester import budget as budget_module
from aoe2stats_ingester import erased_recordings
from aoe2stats_ingester.budget import Budget
from aoe2stats_ingester.capture import CaptureDrain
from aoe2stats_ingester.erased_recordings import sweep_erased_recordings
from aoe2stats_providers.base import NotFound, ReplayBlob
from aoe2stats_storage.models import (
    AoeProfile,
    CaptureSource,
    CaptureStatus,
    Match,
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


async def _erase_in(session: AsyncSession, capture_id: uuid.UUID) -> None:
    """What `erase_account` commits for this pair: the row gone, the placeholder profile present."""
    await session.execute(delete(ReplayCapture).where(ReplayCapture.id == capture_id))
    session.add(AoeProfile(profile_id=-_PROFILE_ID, alias="Pseudonymised"))
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
) -> int:
    drain = _drain(session_factory, provider, store)
    return await sweep_erased_recordings(
        store,
        session_factory,
        pair_has_row=drain._pair_has_row,
        budget=budget or Budget(seconds=30),
    )


async def test_a_drain_killed_between_its_write_and_its_cleanup_leaves_nothing_after_the_next_cycle(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Requirement 1: the row is erased mid-download, the drain's cleanup delete dies, the object
    stays with no row; the next drain call's sweep removes it."""
    capture_id = await _seed(session_factory)
    store = _Store()
    provider = _Provider()

    async def erase() -> None:
        await _erase(session_factory, capture_id)

    provider.on_fetch = erase
    store.fail_delete = True
    with pytest.raises(ConnectionError):
        await _drain(session_factory, provider, store).__call__(Budget(seconds=30))
    assert _KEY in store.objects, "the kill must leave the object behind"

    store.fail_delete = False
    provider.on_fetch = None
    report = await _drain(session_factory, provider, store).__call__(Budget(seconds=30))

    assert store.objects == {}, f"the bucket still holds {sorted(store.objects)}"
    assert report["erased_recordings_deleted"] == 1


async def test_an_object_left_by_a_failed_post_commit_delete_is_removed(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Requirement 2: the erasure committed (row gone, placeholder present) and its pass-3 delete
    never ran; the object is removed by the sweep."""
    capture_id = await _seed(session_factory)
    await _erase(session_factory, capture_id)
    store = _Store({_KEY: _BYTES})

    report = await _drain(session_factory, _Provider(), store).__call__(Budget(seconds=30))

    assert report["erased_recordings_deleted"] == 1
    assert store.objects == {}


async def test_an_object_with_a_live_row_is_kept_by_guard_3(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Contrast, guard 3 (profile never pseudonymised): a live, non-erased row's object stays."""
    capture_id = await _seed(session_factory)
    async with session_factory() as session:
        row = await session.get(ReplayCapture, capture_id)
        assert row is not None
        row.object_key = _KEY
        row.status = CaptureStatus.STORED
        await session.commit()
    store = _Store({_KEY: _BYTES})

    assert await _sweep(session_factory, store, _Provider()) == 0
    assert store.objects == {_KEY: _BYTES}


async def test_an_object_whose_row_exists_is_kept_by_guard_2_even_with_a_placeholder(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Contrast, guard 2 (a row exists for the pair): the placeholder alone deletes nothing."""
    await _seed(session_factory)
    async with session_factory() as session:
        session.add(AoeProfile(profile_id=-_PROFILE_ID, alias="Pseudonymised"))
        await session.commit()
    store = _Store({_KEY: _BYTES})

    assert await _sweep(session_factory, store, _Provider()) == 0
    assert store.objects == {_KEY: _BYTES}


async def test_an_in_flight_drains_object_is_kept_while_its_row_does_not_name_it_yet(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Contrast, guards 2 and 3 both: another cycle's sweep runs after the drain's
    `put_if_absent` and before the row names the object. The row exists, so the object stays and
    the drain then stores it."""
    capture_id = await _seed(session_factory)
    store = _Store()
    provider = _Provider()
    swept: list[int] = []

    async def sweep_now() -> None:
        swept.append(await _sweep(session_factory, store, provider))

    store.after_write = sweep_now
    await _drain(session_factory, provider, store).__call__(Budget(seconds=30))

    assert swept == [0]
    assert store.objects == {_KEY: _BYTES}
    async with session_factory() as session:
        row = await session.get(ReplayCapture, capture_id)
        assert row is not None and row.status is CaptureStatus.STORED


async def test_a_rolled_back_erasures_original_is_kept_throughout_by_guard_3(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Contrast, guard 3 (the placeholder is uncommitted): the erasure has deleted the row and
    inserted the placeholder in its open transaction. The sweep, before and after the rollback,
    deletes nothing, and the row still names the original."""
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
        try:
            async with asyncio.timeout(5):
                assert await _sweep(session_factory, store, _Provider()) == 0
        except TimeoutError:
            pytest.fail("the sweep waited on the open erasure: guard 3 did not stop it first")
        await erasing.rollback()
    finally:
        await erasing.close()

    assert await _sweep(session_factory, store, _Provider()) == 0
    assert store.objects == {_KEY: _BYTES}
    async with session_factory() as session:
        row = await session.get(ReplayCapture, capture_id)
        assert row is not None and row.object_key == _KEY


async def test_an_object_with_no_row_of_a_user_who_never_erased_is_kept_by_guard_3(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Contrast, guard 3: a manual upload whose row write failed leaves an object with no row for
    a profile that was never pseudonymised. Constitution IV keeps it."""
    async with session_factory() as session:
        session.add(AoeProfile(profile_id=_PROFILE_ID, alias="Uploader"))
        await session.commit()
    store = _Store({_KEY: _BYTES})

    assert await _sweep(session_factory, store, _Provider()) == 0
    assert store.objects == {_KEY: _BYTES}


async def test_only_the_replay_key_shape_is_considered_by_guard_1(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Contrast, guard 1: another prefix, and a malformed name under `replays/`, are left alone
    even for a pseudonymised profile."""
    async with session_factory() as session:
        session.add(AoeProfile(profile_id=-_PROFILE_ID, alias="Pseudonymised"))
        await session.commit()
    others = {
        f"retained-recordings/{_GAME_ID}/{_PROFILE_ID}.zip": b"x",
        f"replays/{_GAME_ID}/{_PROFILE_ID}.zip.bak": b"x",
        f"replays/{_GAME_ID}/not-a-number.zip": b"x",
    }
    store = _Store(others)

    assert await _sweep(session_factory, store, _Provider()) == 0
    assert store.objects == others


async def test_a_failing_store_is_contained_and_the_log_carries_no_key(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The sweep never raises; its warning is the type name and a count, never the key."""
    # The test database's alembic run (`fileConfig`) disables loggers that already exist.
    monkeypatch.setattr(erased_recordings.logger, "disabled", False)
    capture_id = await _seed(session_factory)
    await _erase(session_factory, capture_id)
    store = _Store({_KEY: _BYTES})
    store.fail_delete = True

    with caplog.at_level(logging.INFO):
        assert await _sweep(session_factory, store, _Provider()) == 0

    text = "\n".join(record.getMessage() for record in caplog.records)
    assert "ConnectionError" in text
    assert str(_PROFILE_ID) not in text and _KEY not in text
    assert store.objects == {_KEY: _BYTES}


async def _leave_erased_objects(
    session_factory: async_sessionmaker[AsyncSession], count: int
) -> list[str]:
    """`count` committed-erasure leftovers: placeholder profile present, no row, object stored."""
    keys: list[str] = []
    async with session_factory() as session:
        for offset in range(count):
            profile_id = 8_000 + offset
            session.add(AoeProfile(profile_id=-profile_id, alias="Pseudonymised"))
            keys.append(replay_object_key(930_000 + offset, profile_id))
        await session.commit()
    return keys


async def test_a_sweep_given_an_expired_budget_lists_and_deletes_nothing(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Budget guard, outermost: no listing at all once the budget has expired."""
    keys = await _leave_erased_objects(session_factory, 2)
    store = _Store(dict.fromkeys(keys, _BYTES))

    assert await _sweep(session_factory, store, _Provider(), Budget(seconds=0)) == 0
    assert store.list_calls == 0
    assert store.deleted == []


async def test_a_budget_that_expires_mid_sweep_stops_the_deletes(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Budget guard, per key: the fake clock jumps past the budget after the first delete, so of
    three eligible leftovers exactly the first is deleted and the others remain."""
    clock = [1_000.0]
    monkeypatch.setattr(budget_module, "monotonic", lambda: clock[0])
    keys = await _leave_erased_objects(session_factory, 3)
    store = _Store(dict.fromkeys(keys, _BYTES))

    def expire() -> None:
        clock[0] += 11.0

    store.on_delete = expire
    assert await _sweep(session_factory, store, _Provider(), Budget(seconds=10)) == 1
    assert store.deleted == [keys[0]]
    assert sorted(store.objects) == keys[1:]


async def test_the_sweep_runs_before_the_first_claim_and_the_claim_loop_still_runs(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Order: with a live budget the leftover of another pair is deleted before the queued row's
    object is written, and the queued row is then stored."""
    capture_id = await _seed(session_factory)
    (leftover,) = await _leave_erased_objects(session_factory, 1)
    store = _Store({leftover: _BYTES})

    report = await _drain(session_factory, _Provider(), store).__call__(Budget(seconds=30))

    assert store.events.index("delete") < store.events.index("put")
    assert store.events[0] == "list"
    assert leftover not in store.objects
    assert report["erased_recordings_deleted"] == 1
    async with session_factory() as session:
        row = await session.get(ReplayCapture, capture_id)
        assert row is not None and row.status is CaptureStatus.STORED
