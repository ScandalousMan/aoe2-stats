"""T728: the drain's write to the object store is conditional, and its row writes only ever match a
row that is still `downloading`.

`CaptureDrain` writes a downloaded blob under `replay_object_key(game_id, profile_id)`, the key a
manual upload (`upload_replay`) writes the same pair to with `put_if_absent`. These tests pin what
the drain does when it is not the first writer: it writes nothing over an object that is there,
records that object only when it is the very bytes the download returned, and hands the row back as
a failed attempt otherwise; and a row an upload has marked `stored` is never rewritten by any write
the drain makes after its claim.

The object store here is an in-memory fake with the real store's `put_if_absent` / `get` contract
(`aoe2stats_storage.objects.ObjectStore`). A `before_write` hook runs at the start of every write,
which is how a test lets an upload land between the drain's claim and its write.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.links import link_profile

import aoe2stats_ingester.capture as capture_module
from aoe2stats_core.replay.validation import ReplayValidationResult
from aoe2stats_ingester.budget import Budget
from aoe2stats_ingester.capture import CaptureDrain
from aoe2stats_providers.base import (
    NotFound,
    ProviderRateLimited,
    ProviderUnavailable,
    ReplayBlob,
)
from aoe2stats_storage.models import (
    Alert as AlertModel,
)
from aoe2stats_storage.models import (
    AoeProfile,
    CaptureSource,
    CaptureStatus,
    Match,
    ReplayCapture,
)
from aoe2stats_storage.objects import REPLAY_CONTENT_TYPE, ObjectNotFound, replay_object_key

_GAME_ID = 910_001
_PROFILE_ID = 7_281
_KEY = replay_object_key(_GAME_ID, _PROFILE_ID)
_DOWNLOADED = b"the bytes the replay endpoint returned" * 20
_UPLOADED = b"the bytes a person uploaded by hand" * 20
_CAPTURE_BUDGET_DAYS = 21
_GRACE_HOURS = 72


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class _HookedObjectStore:
    """In-memory object store: `put` overwrites, `put_if_absent` does not, `get` raises
    `ObjectNotFound`. `before_write` runs first in either write (an upload landing just before the
    drain's write). `vanish_on_get` models an object deleted between the existence answer and the
    read-back."""

    def __init__(self, objects: dict[str, bytes] | None = None) -> None:
        self.objects: dict[str, bytes] = dict(objects or {})
        self.put_calls: list[tuple[str, bytes]] = []
        self.put_if_absent_calls: list[tuple[str, bytes]] = []
        self.before_write: Callable[[], Awaitable[None]] | None = None
        self.vanish_on_get = False

    async def _hook(self) -> None:
        if self.before_write is not None:
            hook, self.before_write = self.before_write, None
            await hook()

    async def put(self, key: str, body: bytes, *, content_type: str = REPLAY_CONTENT_TYPE) -> None:
        await self._hook()
        self.put_calls.append((key, body))
        self.objects[key] = body

    async def put_if_absent(
        self, key: str, body: bytes, *, content_type: str = REPLAY_CONTENT_TYPE
    ) -> bool:
        await self._hook()
        self.put_if_absent_calls.append((key, body))
        if key in self.objects:
            return False
        self.objects[key] = body
        return True

    async def get(self, key: str) -> bytes:
        if self.vanish_on_get or key not in self.objects:
            raise ObjectNotFound(key)
        return self.objects[key]


class _Provider:
    """Answers every fetch with `outcome` (returned, or raised if it is an exception).
    `on_fetch` runs first: an upload landing while the drain holds the claim."""

    def __init__(self, outcome: ReplayBlob | NotFound | Exception) -> None:
        self.outcome = outcome
        self.calls = 0
        self.on_fetch: Callable[[], Awaitable[None]] | None = None

    async def fetch_replay(self, game_id: int, profile_id: int) -> ReplayBlob | NotFound:
        self.calls += 1
        if self.on_fetch is not None:
            await self.on_fetch()
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class _Validator:
    def validate(self, zip_bytes: bytes) -> ReplayValidationResult:
        return ReplayValidationResult(
            inner_filename="MP Replay v101.101 @2026.10.16 120000 (1).aoe2record",
            inner_bytes=len(zip_bytes) * 2,
            engine_name="fake-engine",
            engine_version="0.0.0",
        )


def _blob(content: bytes = _DOWNLOADED) -> ReplayBlob:
    return ReplayBlob(content=content, filename=f"{_GAME_ID}.zip", content_type=REPLAY_CONTENT_TYPE)


async def _seed(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    attempts: int = 0,
    age: timedelta = timedelta(days=1),
) -> uuid.UUID:
    completed_at = datetime.now(UTC) - age
    capture_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(AoeProfile(profile_id=_PROFILE_ID, alias="Conditional Writer"))
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
                capture_deadline_at=completed_at + timedelta(days=_CAPTURE_BUDGET_DAYS),
                attempts=attempts,
                source=CaptureSource.AUTOMATIC,
            )
        )
        await link_profile(session, _PROFILE_ID)
        await session.commit()
    return capture_id


def _drain(
    session_factory: async_sessionmaker[AsyncSession],
    provider: _Provider,
    store: _HookedObjectStore,
    *,
    max_attempts: int = 3,
) -> CaptureDrain:
    return CaptureDrain(
        session_factory=session_factory,
        replay_provider=provider,
        object_store=store,
        validator=_Validator(),
        capture_budget_days=_CAPTURE_BUDGET_DAYS,
        replay_publication_grace_hours=_GRACE_HOURS,
        max_attempts=max_attempts,
    )


async def _run(drain: CaptureDrain) -> Any:
    return await drain(Budget(seconds=30))


async def _row(
    session_factory: async_sessionmaker[AsyncSession], capture_id: uuid.UUID
) -> dict[str, Any]:
    """Every column of the row, so "unchanged" means every one of them."""
    async with session_factory() as session:
        capture = await session.get(ReplayCapture, capture_id)
        assert capture is not None
        return {column.name: getattr(capture, column.name) for column in ReplayCapture.__table__.c}


async def _alerts(session_factory: async_sessionmaker[AsyncSession]) -> list[AlertModel]:
    async with session_factory() as session:
        return list((await session.execute(select(AlertModel))).scalars())


async def _land_upload(
    session_factory: async_sessionmaker[AsyncSession],
    capture_id: uuid.UUID,
    store: _HookedObjectStore,
    body: bytes = _UPLOADED,
) -> None:
    """What an accepted manual upload leaves: the object under the key, and the row `stored`,
    `manual`, naming that object (`record_manual_upload`)."""
    store.objects[_KEY] = body
    async with session_factory() as session:
        await session.execute(
            update(ReplayCapture)
            .where(ReplayCapture.id == capture_id)
            .values(
                status=CaptureStatus.STORED,
                source=CaptureSource.MANUAL,
                stored_at=datetime.now(UTC) - timedelta(seconds=1),
                object_key=_KEY,
                zip_bytes=len(body),
                zip_sha256=_sha(body),
                inner_filename="MP Replay v101.101 @2026.10.16 130000 (1).aoe2record",
                inner_bytes=4096,
                validated_by="uploader-engine@9.9.9",
                http_status=200,
                last_error=None,
            )
        )
        await session.commit()


# --- The upload lands between the claim and the write -------------------------------------------


@pytest.mark.parametrize("uploaded", [_UPLOADED, _DOWNLOADED], ids=["other-bytes", "same-bytes"])
async def test_an_upload_between_the_claim_and_the_write_is_left_exactly_as_it_is(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None, uploaded: bytes
) -> None:
    capture_id = await _seed(session_factory)
    store = _HookedObjectStore()
    store.before_write = lambda: _land_upload(session_factory, capture_id, store, uploaded)
    drain = _drain(session_factory, _Provider(_blob()), store)

    report = await _run(drain)

    assert store.objects[_KEY] == uploaded
    after = await _row(session_factory, capture_id)
    assert after["status"] == CaptureStatus.STORED
    assert after["source"] == CaptureSource.MANUAL
    assert after["object_key"] == _KEY
    assert after["zip_sha256"] == _sha(uploaded)
    assert after["attempts"] == 1
    assert after["validated_by"] == "uploader-engine@9.9.9"
    assert after["last_error"] is None
    assert report["stored_total"] == 0
    assert await _alerts(session_factory) == []


async def test_the_uploaded_row_is_byte_for_byte_unchanged_by_the_drain(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    capture_id = await _seed(session_factory)
    store = _HookedObjectStore()
    snapshot: dict[str, Any] = {}

    async def upload_then_snapshot() -> None:
        await _land_upload(session_factory, capture_id, store)
        snapshot.update(await _row(session_factory, capture_id))

    store.before_write = upload_then_snapshot
    await _run(_drain(session_factory, _Provider(_blob()), store))

    assert snapshot["status"] == CaptureStatus.STORED
    assert await _row(session_factory, capture_id) == snapshot
    assert store.objects[_KEY] == _UPLOADED


# --- The key already holds an object ------------------------------------------------------------


async def test_an_object_with_the_downloads_hash_is_validated_and_recorded_automatic(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    capture_id = await _seed(session_factory)
    store = _HookedObjectStore({_KEY: _DOWNLOADED})

    report = await _run(_drain(session_factory, _Provider(_blob()), store))

    assert store.put_calls == []
    assert store.objects[_KEY] == _DOWNLOADED
    row = await _row(session_factory, capture_id)
    assert row["status"] == CaptureStatus.STORED
    assert row["source"] == CaptureSource.AUTOMATIC
    assert row["object_key"] == _KEY
    assert row["zip_sha256"] == _sha(_DOWNLOADED)
    assert row["zip_bytes"] == len(_DOWNLOADED)
    assert row["validated_by"] == "fake-engine@0.0.0"
    assert row["http_status"] == 200
    assert report["stored_total"] == 1


async def test_an_object_with_another_hash_is_not_recorded_and_the_attempt_stands(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    capture_id = await _seed(session_factory)
    store = _HookedObjectStore({_KEY: _UPLOADED})
    before = datetime.now(UTC)

    report = await _run(_drain(session_factory, _Provider(_blob()), store, max_attempts=3))

    assert store.put_calls == []
    assert store.objects[_KEY] == _UPLOADED
    row = await _row(session_factory, capture_id)
    assert row["status"] == CaptureStatus.PENDING
    assert row["attempts"] == 1
    assert row["object_key"] is None
    assert row["zip_sha256"] is None
    assert row["zip_bytes"] is None
    assert row["validated_by"] is None
    assert row["claimed_at"] is None
    assert row["next_attempt_at"] > before
    assert "different object" in row["last_error"]
    assert report["stored_total"] == 0
    assert report["quarantined_total"] == 0
    assert await _alerts(session_factory) == []


async def test_an_object_with_another_hash_ends_failed_at_the_attempt_ceiling(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    capture_id = await _seed(session_factory, attempts=2)
    store = _HookedObjectStore({_KEY: _UPLOADED})

    report = await _run(_drain(session_factory, _Provider(_blob()), store, max_attempts=3))

    assert store.objects[_KEY] == _UPLOADED
    row = await _row(session_factory, capture_id)
    assert row["status"] == CaptureStatus.FAILED
    assert row["attempts"] == 3
    assert row["object_key"] is None
    assert row["zip_sha256"] is None
    assert "different object" in row["last_error"]
    assert report["failed_total"] == 1
    assert await _alerts(session_factory) == []


async def test_an_object_gone_at_the_read_back_is_a_failed_attempt_and_nothing_is_written(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    capture_id = await _seed(session_factory)
    store = _HookedObjectStore({_KEY: _UPLOADED})
    store.vanish_on_get = True

    await _run(_drain(session_factory, _Provider(_blob()), store))

    assert store.put_calls == []
    row = await _row(session_factory, capture_id)
    assert row["status"] == CaptureStatus.PENDING
    assert row["attempts"] == 1
    assert row["object_key"] is None
    assert row["zip_sha256"] is None
    assert "no longer" in row["last_error"]


# --- Contrast -----------------------------------------------------------------------------------


async def test_a_key_that_holds_nothing_is_written_and_recorded_as_before(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    capture_id = await _seed(session_factory)
    store = _HookedObjectStore()

    report = await _run(_drain(session_factory, _Provider(_blob()), store))

    assert store.objects[_KEY] == _DOWNLOADED
    # One write of the downloaded bytes, whichever call makes it.
    assert store.put_calls + store.put_if_absent_calls == [(_KEY, _DOWNLOADED)]
    row = await _row(session_factory, capture_id)
    assert row["status"] == CaptureStatus.STORED
    assert row["source"] == CaptureSource.AUTOMATIC
    assert row["object_key"] == _KEY
    assert row["zip_sha256"] == _sha(_DOWNLOADED)
    assert row["validated_by"] == "fake-engine@0.0.0"
    assert report["stored_total"] == 1


# --- Every other write after the claim ----------------------------------------------------------


def _unavailable() -> ProviderUnavailable:
    return ProviderUnavailable("boom", provider="aoems", endpoint="/replay/x", status_code=500)


def _rate_limited() -> ProviderRateLimited:
    return ProviderRateLimited("slow down", provider="aoems", endpoint="/replay/x")


#: (outcome of the fetch, seeded attempts, match age, max_attempts)
_FETCH_CASES = {
    "backoff": (_unavailable(), 0, timedelta(days=1), 3),
    "failed": (_unavailable(), 2, timedelta(days=1), 3),
    "revert-inside-grace": (NotFound(http_status=404), 0, timedelta(hours=1), 3),
    "unavailable": (NotFound(http_status=404), 1, timedelta(days=4), 3),
    "expired": (NotFound(http_status=404), 0, timedelta(days=40), 3),
    "rate-limited": (_rate_limited(), 0, timedelta(days=1), 3),
}


@pytest.mark.parametrize("case", list(_FETCH_CASES))
async def test_a_row_an_upload_marked_stored_during_the_fetch_is_not_rewritten(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None, case: str
) -> None:
    outcome, attempts, age, max_attempts = _FETCH_CASES[case]
    capture_id = await _seed(session_factory, attempts=attempts, age=age)
    store = _HookedObjectStore()
    provider = _Provider(outcome)
    snapshot: dict[str, Any] = {}

    async def upload_then_snapshot() -> None:
        await _land_upload(session_factory, capture_id, store)
        snapshot.update(await _row(session_factory, capture_id))

    provider.on_fetch = upload_then_snapshot
    drain = _drain(session_factory, provider, store, max_attempts=max_attempts)

    if isinstance(outcome, ProviderRateLimited):
        await _run(drain)
    else:
        report = await _run(drain)
        assert report["expired_total"] == 0
        assert report["unavailable_total"] == 0
        assert report["failed_total"] == 0

    assert snapshot["status"] == CaptureStatus.STORED
    assert await _row(session_factory, capture_id) == snapshot
    # Not an expired replay: the object is held, so no severity-1 alert may claim it is lost. The
    # rate limit's own alert is the one a 429 raises whatever the row is.
    assert [a.kind for a in await _alerts(session_factory) if a.kind != "rate_limited"] == []


@pytest.mark.parametrize("verdict", ["valid", "invalid"])
async def test_a_row_marked_stored_during_validation_is_not_rewritten(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
    verdict: str,
) -> None:
    capture_id = await _seed(session_factory)
    store = _HookedObjectStore()
    snapshot: dict[str, Any] = {}

    async def barrier(
        validator: Any, zip_bytes: bytes, *, timeout_seconds: float
    ) -> tuple[ReplayValidationResult | None, str | None]:
        await _land_upload(session_factory, capture_id, store)
        snapshot.update(await _row(session_factory, capture_id))
        if verdict == "valid":
            return validator.validate(zip_bytes), None
        return None, "EngineParseError: nope"

    monkeypatch.setattr(capture_module, "_validate_with_barrier", barrier)

    report = await _run(_drain(session_factory, _Provider(_blob()), store))

    assert await _row(session_factory, capture_id) == snapshot
    assert report["stored_total"] == 0
    assert report["quarantined_total"] == 0
    assert await _alerts(session_factory) == []


async def test_a_row_marked_stored_before_the_blob_metadata_commit_is_not_rewritten(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """The drain wins the object write (the key was empty) but an upload marks the row `stored`
    before the metadata commit: the commit must not name the drain's object on that row."""
    capture_id = await _seed(session_factory)
    store = _HookedObjectStore()
    snapshot: dict[str, Any] = {}

    async def mark_row_only() -> None:
        await _land_upload(session_factory, capture_id, store)
        store.objects.pop(_KEY)
        snapshot.update(await _row(session_factory, capture_id))

    store.before_write = mark_row_only
    await _run(_drain(session_factory, _Provider(_blob()), store))

    assert await _row(session_factory, capture_id) == snapshot
