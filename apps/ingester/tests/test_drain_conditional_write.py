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
import time
import uuid
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import Update, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.links import link_profile

import aoe2stats_ingester.capture as capture_module
from aoe2stats_core.replay.validation import EngineParseError, ReplayValidationResult
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
    AlertKind,
    AoeProfile,
    CaptureSource,
    CaptureStatus,
    Match,
    ProfileLink,
    ReplayCapture,
)
from aoe2stats_storage.objects import (
    REPLAY_CONTENT_TYPE,
    ObjectNotFound,
    ObjectWriteConflict,
    replay_object_key,
)
from aoe2stats_storage.repositories.captures import CapturesRepository

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
    drain's write), `after_write` once `put_if_absent` has written (something happening to the row
    between the object write and the metadata commit). `vanish_on_get` models an object deleted
    between the existence answer and the read-back; `conflict_keys` are keys whose conditional
    write meets a concurrent one (HTTP 409). User metadata is kept per key, as the real store does.
    """

    def __init__(
        self,
        objects: dict[str, bytes] | None = None,
        metadata: dict[str, dict[str, str]] | None = None,
    ) -> None:
        self.objects: dict[str, bytes] = dict(objects or {})
        self.metadata: dict[str, dict[str, str]] = dict(metadata or {})
        self.put_calls: list[tuple[str, bytes]] = []
        self.put_if_absent_calls: list[tuple[str, bytes]] = []
        self.before_write: Callable[[], Awaitable[None]] | None = None
        self.after_write: Callable[[], Awaitable[None]] | None = None
        self.vanish_on_get = False
        self.conflict_keys: set[str] = set()

    async def _hook(self) -> None:
        if self.before_write is not None:
            hook, self.before_write = self.before_write, None
            await hook()

    async def put(self, key: str, body: bytes, *, content_type: str = REPLAY_CONTENT_TYPE) -> None:
        await self._hook()
        self.put_calls.append((key, body))
        self.objects[key] = body

    async def put_if_absent(
        self,
        key: str,
        body: bytes,
        *,
        content_type: str = REPLAY_CONTENT_TYPE,
        metadata: Mapping[str, str] | None = None,
    ) -> bool:
        await self._hook()
        self.put_if_absent_calls.append((key, body))
        if key in self.conflict_keys:
            raise ObjectWriteConflict(key)
        if key in self.objects:
            return False
        self.objects[key] = body
        self.metadata[key] = dict(metadata or {})
        if self.after_write is not None:
            hook, self.after_write = self.after_write, None
            await hook()
        return True

    async def get(self, key: str) -> bytes:
        if self.vanish_on_get or key not in self.objects:
            raise ObjectNotFound(key)
        return self.objects[key]

    async def get_with_metadata(self, key: str) -> tuple[bytes, Mapping[str, str]]:
        return await self.get(key), dict(self.metadata.get(key, {}))


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


class _RejectingValidator:
    def validate(self, zip_bytes: bytes) -> ReplayValidationResult:
        raise EngineParseError("the engine rejected the replay")


class _HangingValidator:
    def validate(self, zip_bytes: bytes) -> ReplayValidationResult:
        time.sleep(1.0)
        raise AssertionError("must never return: the wall-clock cap must win the race")


def _blob(content: bytes = _DOWNLOADED) -> ReplayBlob:
    return ReplayBlob(content=content, filename=f"{_GAME_ID}.zip", content_type=REPLAY_CONTENT_TYPE)


async def _seed(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    attempts: int = 0,
    age: timedelta = timedelta(days=1),
    game_id: int = _GAME_ID,
) -> uuid.UUID:
    completed_at = datetime.now(UTC) - age
    capture_id = uuid.uuid4()
    async with session_factory() as session:
        first = await session.get(AoeProfile, _PROFILE_ID) is None
        if first:
            session.add(AoeProfile(profile_id=_PROFILE_ID, alias="Conditional Writer"))
        session.add(
            Match(
                game_id=game_id,
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
                game_id=game_id,
                profile_id=_PROFILE_ID,
                capture_deadline_at=completed_at + timedelta(days=_CAPTURE_BUDGET_DAYS),
                attempts=attempts,
                source=CaptureSource.AUTOMATIC,
            )
        )
        if first:
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


# --- The metadata commit never names an object over another one --------------------------------


async def test_an_upload_stored_row_naming_an_object_is_not_rewritten_by_the_commit(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """An upload with the download's own bytes lands first: the drain finds the key held, the
    bytes equal, and its commit must leave the row naming what the upload recorded."""
    capture_id = await _seed(session_factory)
    store = _HookedObjectStore()
    snapshot: dict[str, Any] = {}

    async def upload_then_snapshot() -> None:
        await _land_upload(session_factory, capture_id, store, _DOWNLOADED)
        snapshot.update(await _row(session_factory, capture_id))

    store.before_write = upload_then_snapshot
    await _run(_drain(session_factory, _Provider(_blob()), store))

    assert snapshot["object_key"] == _KEY
    assert await _row(session_factory, capture_id) == snapshot


async def test_a_row_that_already_names_an_object_is_not_renamed_by_the_commit(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Whatever the row's status: another drain reclaimed the stale claim and committed its own
    object first, so the row is still `downloading` but already names one."""
    capture_id = await _seed(session_factory)
    store = _HookedObjectStore({_KEY: _DOWNLOADED})
    snapshot: dict[str, Any] = {}

    async def another_drain_commits() -> None:
        async with session_factory() as session:
            await session.execute(
                update(ReplayCapture)
                .where(ReplayCapture.id == capture_id)
                .values(object_key=_KEY, zip_bytes=1, zip_sha256="f" * 64)
            )
            await session.commit()
        snapshot.update(await _row(session_factory, capture_id))

    store.before_write = another_drain_commits
    await _run(_drain(session_factory, _Provider(_blob()), store))

    assert snapshot["zip_sha256"] == "f" * 64
    assert (await _row(session_factory, capture_id))["zip_sha256"] == "f" * 64


async def test_a_row_withdrawn_after_the_object_write_ends_withdrawn_naming_the_object(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """The claim goes stale and the sweep withdraws the row while the first drain is still between
    its object write and its commit. The object must not be left under the key with no row
    naming it (erasure deletes only what a row names; every later upload is refused)."""
    capture_id = await _seed(session_factory, age=timedelta(days=22))
    store = _HookedObjectStore()
    drain = _drain(session_factory, _Provider(_blob()), store)

    async def stale_and_withdrawn() -> None:
        async with session_factory() as session:
            await session.execute(
                update(ReplayCapture)
                .where(ReplayCapture.id == capture_id)
                .values(claimed_at=datetime.now(UTC) - timedelta(hours=1))
            )
            await session.execute(
                update(ProfileLink).values(unlinked_at=datetime.now(UTC) - timedelta(minutes=1))
            )
            await session.commit()
        assert await drain.withdraw_refused_near_deadline(now=datetime.now(UTC)) == 1

    store.after_write = stale_and_withdrawn
    report = await _run(drain)

    row = await _row(session_factory, capture_id)
    assert row["status"] == CaptureStatus.WITHDRAWN
    assert row["object_key"] == _KEY
    assert row["zip_sha256"] == _sha(_DOWNLOADED)
    assert row["zip_bytes"] == len(_DOWNLOADED)
    assert store.objects[_KEY] == _DOWNLOADED
    assert report["stored_total"] == 0


async def test_a_row_reverted_to_pending_by_another_drain_names_the_object_and_resumes(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    capture_id = await _seed(session_factory)
    store = _HookedObjectStore()
    provider = _Provider(_blob())
    drain = _drain(session_factory, provider, store)

    async def reverted() -> None:
        async with session_factory() as session:
            await session.execute(
                update(ReplayCapture)
                .where(ReplayCapture.id == capture_id)
                .values(status=CaptureStatus.PENDING, claimed_at=None)
            )
            await session.commit()

    store.after_write = reverted
    await _run(drain)

    row = await _row(session_factory, capture_id)
    assert row["status"] == CaptureStatus.PENDING
    assert row["object_key"] == _KEY
    assert row["zip_sha256"] == _sha(_DOWNLOADED)

    # A later claim resumes at validation: nothing is downloaded or written again.
    await _run(drain)

    row = await _row(session_factory, capture_id)
    assert row["status"] == CaptureStatus.STORED
    assert row["validated_by"] == "fake-engine@0.0.0"
    assert provider.calls == 1
    assert store.put_if_absent_calls == [(_KEY, _DOWNLOADED)]


# --- A row another drain ended while this drain was past its claim (T740) ----------------------
#
# The level under test is the `stored` mark after the blob metadata commit, not the claim: the claim
# went stale, a second drain reclaimed the row and ended it, and the first drain's object write,
# metadata commit and mark still land.


async def _end_row(
    session_factory: async_sessionmaker[AsyncSession],
    capture_id: uuid.UUID,
    status: CaptureStatus,
    **extra: Any,
) -> None:
    """What a second drain leaves when it ends the row: a terminal status and its last error."""
    async with session_factory() as session:
        await session.execute(
            update(ReplayCapture)
            .where(ReplayCapture.id == capture_id)
            .values(status=status, claimed_at=None, last_error="ended by another drain", **extra)
        )
        await session.commit()


@pytest.mark.parametrize(
    "ended",
    [CaptureStatus.EXPIRED, CaptureStatus.FAILED, CaptureStatus.UNAVAILABLE],
    ids=["expired", "failed", "unavailable"],
)
async def test_a_row_another_drain_ended_before_the_metadata_commit_ends_stored(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    ended: CaptureStatus,
) -> None:
    capture_id = await _seed(session_factory)
    store = _HookedObjectStore()

    async def another_drain_ends_the_row() -> None:
        await _end_row(session_factory, capture_id, ended)

    store.after_write = another_drain_ends_the_row
    report = await _run(_drain(session_factory, _Provider(_blob()), store))

    row = await _row(session_factory, capture_id)
    assert row["status"] == CaptureStatus.STORED
    assert row["validated_by"] == "fake-engine@0.0.0"
    assert row["object_key"] == _KEY
    assert row["zip_sha256"] == _sha(_DOWNLOADED)
    assert row["last_error"] is None
    assert row["http_status"] == 200
    assert report["stored_total"] == 1


@pytest.mark.parametrize(
    "ended",
    [CaptureStatus.EXPIRED, CaptureStatus.FAILED, CaptureStatus.UNAVAILABLE],
    ids=["expired", "failed", "unavailable"],
)
async def test_a_row_another_drain_ended_during_validation_ends_stored(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
    ended: CaptureStatus,
) -> None:
    """The same, with the row ended between the metadata commit and the mark."""
    capture_id = await _seed(session_factory)
    store = _HookedObjectStore()

    async def barrier(
        validator: Any, zip_bytes: bytes, *, timeout_seconds: float
    ) -> tuple[ReplayValidationResult | None, str | None]:
        assert (await _row(session_factory, capture_id))["object_key"] == _KEY
        await _end_row(session_factory, capture_id, ended)
        return validator.validate(zip_bytes), None

    monkeypatch.setattr(capture_module, "_validate_with_barrier", barrier)

    report = await _run(_drain(session_factory, _Provider(_blob()), store))

    row = await _row(session_factory, capture_id)
    assert row["status"] == CaptureStatus.STORED
    assert row["validated_by"] == "fake-engine@0.0.0"
    assert row["object_key"] == _KEY
    assert report["stored_total"] == 1


@pytest.mark.parametrize(
    "ended",
    [CaptureStatus.EXPIRED, CaptureStatus.FAILED, CaptureStatus.UNAVAILABLE],
    ids=["expired", "failed", "unavailable"],
)
async def test_a_resumed_reclaim_whose_row_another_drain_ended_ends_stored(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
    ended: CaptureStatus,
) -> None:
    """The resume path passes the row's own committed key to the same mark."""
    capture_id = await _seed(session_factory)
    store = _HookedObjectStore({_KEY: _DOWNLOADED})
    async with session_factory() as session:
        await session.execute(
            update(ReplayCapture)
            .where(ReplayCapture.id == capture_id)
            .values(
                status=CaptureStatus.DOWNLOADING,
                claimed_at=datetime.now(UTC) - timedelta(hours=1),
                object_key=_KEY,
                zip_bytes=len(_DOWNLOADED),
                zip_sha256=_sha(_DOWNLOADED),
            )
        )
        await session.commit()

    async def barrier(
        validator: Any, zip_bytes: bytes, *, timeout_seconds: float
    ) -> tuple[ReplayValidationResult | None, str | None]:
        await _end_row(session_factory, capture_id, ended)
        return validator.validate(zip_bytes), None

    monkeypatch.setattr(capture_module, "_validate_with_barrier", barrier)

    provider = _Provider(_blob())
    report = await _run(_drain(session_factory, provider, store))

    row = await _row(session_factory, capture_id)
    assert provider.calls == 0
    assert row["status"] == CaptureStatus.STORED
    assert row["validated_by"] == "fake-engine@0.0.0"
    assert row["object_key"] == _KEY
    assert report["stored_total"] == 1


async def test_a_withdrawn_row_stays_withdrawn_and_names_the_object_after_the_mark(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """`withdrawn` is a refusal made on purpose, not an outcome of an attempt: a late write never
    reverses it, in either place the row can be withdrawn."""
    capture_id = await _seed(session_factory)
    store = _HookedObjectStore()

    async def withdrawn() -> None:
        await _end_row(session_factory, capture_id, CaptureStatus.WITHDRAWN)

    store.after_write = withdrawn
    report = await _run(_drain(session_factory, _Provider(_blob()), store))

    row = await _row(session_factory, capture_id)
    assert row["status"] == CaptureStatus.WITHDRAWN
    assert row["object_key"] == _KEY
    assert row["validated_by"] is None
    assert row["last_error"] == "ended by another drain"
    assert report["stored_total"] == 0


async def test_a_row_withdrawn_between_the_commit_and_the_mark_stays_withdrawn(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture_id = await _seed(session_factory)
    store = _HookedObjectStore()
    snapshot: dict[str, Any] = {}

    async def barrier(
        validator: Any, zip_bytes: bytes, *, timeout_seconds: float
    ) -> tuple[ReplayValidationResult | None, str | None]:
        await _end_row(session_factory, capture_id, CaptureStatus.WITHDRAWN)
        snapshot.update(await _row(session_factory, capture_id))
        return validator.validate(zip_bytes), None

    monkeypatch.setattr(capture_module, "_validate_with_barrier", barrier)

    report = await _run(_drain(session_factory, _Provider(_blob()), store))

    assert snapshot["object_key"] == _KEY
    assert await _row(session_factory, capture_id) == snapshot
    assert snapshot["status"] == CaptureStatus.WITHDRAWN
    assert report["stored_total"] == 0


@pytest.mark.parametrize(
    "ended",
    [CaptureStatus.EXPIRED, CaptureStatus.FAILED, CaptureStatus.UNAVAILABLE],
    ids=["expired", "failed", "unavailable"],
)
async def test_a_row_naming_another_key_than_the_drains_is_not_marked(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
    ended: CaptureStatus,
) -> None:
    """Exercises the defensive guard on the key equality, not an ordering guarantee: no writer
    produces a row naming another key (`replay_object_key` is one key per pair), but a row ended
    while naming one is never marked by a drain whose own key is not the one it names."""
    capture_id = await _seed(session_factory)
    store = _HookedObjectStore()
    snapshot: dict[str, Any] = {}
    other_key = "replays/someone-elses-object.zip"

    async def barrier(
        validator: Any, zip_bytes: bytes, *, timeout_seconds: float
    ) -> tuple[ReplayValidationResult | None, str | None]:
        await _end_row(session_factory, capture_id, ended, object_key=other_key)
        snapshot.update(await _row(session_factory, capture_id))
        return validator.validate(zip_bytes), None

    monkeypatch.setattr(capture_module, "_validate_with_barrier", barrier)

    report = await _run(_drain(session_factory, _Provider(_blob()), store))

    assert snapshot["status"] == ended
    assert snapshot["object_key"] == other_key
    assert await _row(session_factory, capture_id) == snapshot
    assert report["stored_total"] == 0


async def test_a_quarantined_row_naming_the_drains_key_is_not_rewritten_by_the_mark(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A resumer quarantined the row while this drain was validating the same bytes: `quarantined`
    is not one of the statuses the drain's `stored` mark widens to (`_ENDED_BY_ANOTHER_DRAIN`), so
    this drain's successful validation leaves the row byte-for-byte as it is and counts nothing."""
    capture_id = await _seed(session_factory)
    store = _HookedObjectStore()
    snapshot: dict[str, Any] = {}

    async def barrier(
        validator: Any, zip_bytes: bytes, *, timeout_seconds: float
    ) -> tuple[ReplayValidationResult | None, str | None]:
        assert (await _row(session_factory, capture_id))["object_key"] == _KEY
        await _end_row(session_factory, capture_id, CaptureStatus.QUARANTINED)
        snapshot.update(await _row(session_factory, capture_id))
        return validator.validate(zip_bytes), None

    monkeypatch.setattr(capture_module, "_validate_with_barrier", barrier)

    report = await _run(_drain(session_factory, _Provider(_blob()), store))

    assert snapshot["status"] == CaptureStatus.QUARANTINED
    assert snapshot["object_key"] == _KEY
    assert await _row(session_factory, capture_id) == snapshot
    assert report["stored_total"] == 0


async def test_a_stored_row_naming_the_drains_own_key_is_not_rewritten_by_the_mark(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture_id = await _seed(session_factory)
    store = _HookedObjectStore()
    snapshot: dict[str, Any] = {}

    async def barrier(
        validator: Any, zip_bytes: bytes, *, timeout_seconds: float
    ) -> tuple[ReplayValidationResult | None, str | None]:
        # Overwrites the drain's own naming with an upload's, under the same key.
        await _land_upload(session_factory, capture_id, store)
        snapshot.update(await _row(session_factory, capture_id))
        return validator.validate(zip_bytes), None

    monkeypatch.setattr(capture_module, "_validate_with_barrier", barrier)

    report = await _run(_drain(session_factory, _Provider(_blob()), store))

    assert snapshot["status"] == CaptureStatus.STORED
    assert snapshot["object_key"] == _KEY
    assert await _row(session_factory, capture_id) == snapshot
    assert report["stored_total"] == 0


# --- The same, for the `quarantined` mark after a failed validation (T747) ---------------------
#
# The drain's other late write. Its metadata commit has named its object (T728); validation fails
# (an engine error, the wall-clock cap, or on a resumed reclaim a missing object or a checksum
# mismatch); a second drain ended the row meanwhile. Both places reach `_quarantine`:
# `_process_one` (key it wrote) and `_resume_reclaim` (key read from the row).

_ENDED = [CaptureStatus.EXPIRED, CaptureStatus.FAILED, CaptureStatus.UNAVAILABLE]
_ENDED_IDS = ["expired", "failed", "unavailable"]
_ENGINE_REASON = "EngineParseError: nope"

#: (path, failure): where the failure arises and what it is. The two integrity failures exist only
#: on the resumed reclaim.
_FAILURES = [
    ("process", "engine"),
    ("reclaim", "engine"),
    ("reclaim", "missing"),
    ("reclaim", "mismatch"),
]
_FAILURE_IDS = ["process-engine", "reclaim-engine", "reclaim-missing", "reclaim-mismatch"]


_End = Callable[
    [async_sessionmaker[AsyncSession], uuid.UUID, "_HookedObjectStore"], Awaitable[None]
]


class _LateFailure:
    """What `_late_failure` observed: the report, the store, and the row right after `end` ran."""

    def __init__(
        self,
        capture_id: uuid.UUID,
        report: Any,
        store: _HookedObjectStore,
        snapshot: dict[str, Any],
    ) -> None:
        self.capture_id = capture_id
        self.report = report
        self.store = store
        self.snapshot = snapshot


async def _late_failure(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    *,
    path: str,
    failure: str,
    end: _End,
) -> _LateFailure:
    """Run one drain over a row whose validation fails, with `end` run (and the row snapshotted)
    at the last moment before the failure is decided: inside the barrier for an engine failure,
    inside the read-back for a missing or mismatching object."""
    capture_id = await _seed(session_factory)
    snapshot: dict[str, Any] = {}
    if path == "reclaim":
        objects = (
            {}
            if failure == "missing"
            else {_KEY: _UPLOADED if failure == "mismatch" else _DOWNLOADED}
        )
        store = _HookedObjectStore(objects)
        async with session_factory() as session:
            await session.execute(
                update(ReplayCapture)
                .where(ReplayCapture.id == capture_id)
                .values(
                    status=CaptureStatus.DOWNLOADING,
                    claimed_at=datetime.now(UTC) - timedelta(hours=1),
                    object_key=_KEY,
                    zip_bytes=len(_DOWNLOADED),
                    zip_sha256=_sha(_DOWNLOADED),
                )
            )
            await session.commit()
    else:
        store = _HookedObjectStore()

    async def ended() -> None:
        await end(session_factory, capture_id, store)
        snapshot.update(await _row(session_factory, capture_id))

    if failure == "engine":

        async def barrier(
            validator: Any, zip_bytes: bytes, *, timeout_seconds: float
        ) -> tuple[ReplayValidationResult | None, str | None]:
            await ended()
            return None, _ENGINE_REASON

        monkeypatch.setattr(capture_module, "_validate_with_barrier", barrier)
    else:
        original = CaptureDrain._read_back_verified

        async def read_back(self: CaptureDrain, *args: Any, **kwargs: Any) -> Any:
            await ended()
            return await original(self, *args, **kwargs)

        monkeypatch.setattr(CaptureDrain, "_read_back_verified", read_back)

    provider = _Provider(_blob())
    report = await _run(_drain(session_factory, provider, store))
    assert provider.calls == (0 if path == "reclaim" else 1)
    return _LateFailure(capture_id, report, store, snapshot)


def _ending(status: CaptureStatus, **extra: Any) -> _End:
    async def end(
        factory: async_sessionmaker[AsyncSession], capture_id: uuid.UUID, store: _HookedObjectStore
    ) -> None:
        await _end_row(factory, capture_id, status, **extra)

    return end


def _expected_reason(failure: str, last_error: str) -> None:
    if failure == "engine":
        assert last_error == _ENGINE_REASON
    elif failure == "missing":
        assert last_error.startswith(capture_module._READ_BACK_REASON_PREFIX)
    else:
        assert last_error.startswith(capture_module._CHECKSUM_REASON_PREFIX)


@pytest.mark.parametrize("ended", _ENDED, ids=_ENDED_IDS)
@pytest.mark.parametrize(("path", "failure"), _FAILURES, ids=_FAILURE_IDS)
async def test_a_failed_validation_over_a_row_another_drain_ended_quarantines_it_and_alerts(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
    ended: CaptureStatus,
    path: str,
    failure: str,
) -> None:
    """The row ends `quarantined` naming the drain's object with the drain's reason, counts
    `quarantined_total`, and raises the severity-2 `validation_failed` alert."""
    outcome = await _late_failure(
        session_factory, monkeypatch, path=path, failure=failure, end=_ending(ended)
    )

    assert outcome.snapshot["status"] == ended  # the other drain really ended it first
    row = await _row(session_factory, outcome.capture_id)
    assert row["status"] == CaptureStatus.QUARANTINED
    _expected_reason(failure, row["last_error"])
    assert row["object_key"] == _KEY
    assert row["zip_sha256"] == _sha(_DOWNLOADED)
    assert row["validated_by"] is None
    assert outcome.report["quarantined_total"] == 1
    assert outcome.report["stored_total"] == 0
    alerts = await _alerts(session_factory)
    assert [(a.kind, a.severity) for a in alerts] == [("validation_failed", 2)]
    assert alerts[0].detail is not None
    assert alerts[0].detail["capture_id"] == str(outcome.capture_id)
    assert alerts[0].detail["reason"] == row["last_error"]


@pytest.mark.parametrize(("path", "failure"), _FAILURES, ids=_FAILURE_IDS)
async def test_an_expired_row_quarantined_late_keeps_its_expired_capture_alert(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    failure: str,
) -> None:
    """The other drain's severity-1 `expired_capture` alert stays until acknowledged; the
    `validation_failed` alert is raised beside it."""

    async def end(
        factory: async_sessionmaker[AsyncSession], capture_id: uuid.UUID, store: _HookedObjectStore
    ) -> None:
        await _end_row(factory, capture_id, CaptureStatus.EXPIRED)
        async with factory() as session:
            session.add(
                AlertModel(
                    kind=AlertKind.EXPIRED_CAPTURE,
                    severity=1,
                    detail={"capture_id": str(capture_id)},
                )
            )
            await session.commit()

    outcome = await _late_failure(session_factory, monkeypatch, path=path, failure=failure, end=end)

    assert (await _row(session_factory, outcome.capture_id))["status"] == CaptureStatus.QUARANTINED
    alerts = await _alerts(session_factory)
    assert sorted((a.kind, a.severity) for a in alerts) == [
        ("expired_capture", 1),
        ("validation_failed", 2),
    ]
    assert all(a.acknowledged_at is None for a in alerts)
    assert outcome.report["quarantined_total"] == 1


@pytest.mark.parametrize("ended", _ENDED, ids=_ENDED_IDS)
async def test_the_wall_clock_cap_over_a_row_another_drain_ended_quarantines_it_and_alerts(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    ended: CaptureStatus,
) -> None:
    """The real barrier, not a patched one: the engine hangs past the cap while the row is ended
    between the object write and the metadata commit."""
    capture_id = await _seed(session_factory)
    store = _HookedObjectStore()

    async def another_drain_ends_the_row() -> None:
        await _end_row(session_factory, capture_id, ended)

    store.after_write = another_drain_ends_the_row
    drain = CaptureDrain(
        session_factory=session_factory,
        replay_provider=_Provider(_blob()),
        object_store=store,
        validator=_HangingValidator(),
        capture_budget_days=_CAPTURE_BUDGET_DAYS,
        replay_publication_grace_hours=_GRACE_HOURS,
        validation_timeout_seconds=0.05,
    )

    report = await _run(drain)

    row = await _row(session_factory, capture_id)
    assert row["status"] == CaptureStatus.QUARANTINED
    assert row["last_error"].startswith(capture_module._CAP_REASON_PREFIX)
    assert row["object_key"] == _KEY
    assert report["quarantined_total"] == 1
    assert [(a.kind, a.severity) for a in await _alerts(session_factory)] == [
        ("validation_failed", 2)
    ]


async def test_a_real_engine_error_over_a_row_another_drain_ended_quarantines_it(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """The real barrier folding a real `EngineParseError`, with the row ended before the commit."""
    capture_id = await _seed(session_factory)
    store = _HookedObjectStore()

    async def another_drain_ends_the_row() -> None:
        await _end_row(session_factory, capture_id, CaptureStatus.FAILED)

    store.after_write = another_drain_ends_the_row
    drain = CaptureDrain(
        session_factory=session_factory,
        replay_provider=_Provider(_blob()),
        object_store=store,
        validator=_RejectingValidator(),
        capture_budget_days=_CAPTURE_BUDGET_DAYS,
        replay_publication_grace_hours=_GRACE_HOURS,
    )

    report = await _run(drain)

    row = await _row(session_factory, capture_id)
    assert row["status"] == CaptureStatus.QUARANTINED
    assert row["last_error"] == "EngineParseError: the engine rejected the replay"
    assert report["quarantined_total"] == 1
    assert [a.kind for a in await _alerts(session_factory)] == ["validation_failed"]


# Contrast: every one of these stays exactly as it was before T747.


@pytest.mark.parametrize(("path", "failure"), _FAILURES, ids=_FAILURE_IDS)
async def test_a_failed_validation_over_a_withdrawn_row_leaves_it_withdrawn_and_silent(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    failure: str,
) -> None:
    """`withdrawn` is a refusal made on purpose; a late failure never reverses it."""
    outcome = await _late_failure(
        session_factory,
        monkeypatch,
        path=path,
        failure=failure,
        end=_ending(CaptureStatus.WITHDRAWN),
    )

    assert outcome.snapshot["status"] == CaptureStatus.WITHDRAWN
    assert outcome.snapshot["object_key"] == _KEY
    assert await _row(session_factory, outcome.capture_id) == outcome.snapshot
    assert outcome.report["quarantined_total"] == 0
    assert await _alerts(session_factory) == []


@pytest.mark.parametrize("ended", _ENDED, ids=_ENDED_IDS)
@pytest.mark.parametrize(("path", "failure"), _FAILURES, ids=_FAILURE_IDS)
async def test_a_failed_validation_over_a_row_naming_another_key_marks_nothing(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
    ended: CaptureStatus,
    path: str,
    failure: str,
) -> None:
    """The defensive guard on the key equality, as for the `stored` mark."""
    other_key = "replays/someone-elses-object.zip"
    outcome = await _late_failure(
        session_factory,
        monkeypatch,
        path=path,
        failure=failure,
        end=_ending(ended, object_key=other_key),
    )

    assert outcome.snapshot["status"] == ended
    assert outcome.snapshot["object_key"] == other_key
    assert await _row(session_factory, outcome.capture_id) == outcome.snapshot
    assert outcome.report["quarantined_total"] == 0
    assert await _alerts(session_factory) == []


@pytest.mark.parametrize("path", ["process", "reclaim"])
async def test_a_failed_validation_over_a_stored_row_does_not_rewrite_it(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    async def end(
        factory: async_sessionmaker[AsyncSession], capture_id: uuid.UUID, store: _HookedObjectStore
    ) -> None:
        await _land_upload(factory, capture_id, store, _DOWNLOADED)

    outcome = await _late_failure(
        session_factory, monkeypatch, path=path, failure="engine", end=end
    )

    assert outcome.snapshot["status"] == CaptureStatus.STORED
    assert outcome.snapshot["object_key"] == _KEY
    assert await _row(session_factory, outcome.capture_id) == outcome.snapshot
    assert outcome.report["quarantined_total"] == 0
    assert await _alerts(session_factory) == []


@pytest.mark.parametrize("path", ["process", "reclaim"])
async def test_a_failed_validation_over_an_already_quarantined_row_is_not_rewritten_or_repeated(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    """Another drain's quarantine, with its own reason, stands: no overwrite, no second alert."""
    outcome = await _late_failure(
        session_factory,
        monkeypatch,
        path=path,
        failure="engine",
        end=_ending(CaptureStatus.QUARANTINED),
    )

    assert outcome.snapshot["status"] == CaptureStatus.QUARANTINED
    assert outcome.snapshot["last_error"] == "ended by another drain"
    assert await _row(session_factory, outcome.capture_id) == outcome.snapshot
    assert outcome.report["quarantined_total"] == 0
    assert await _alerts(session_factory) == []


@pytest.mark.parametrize(("path", "failure"), _FAILURES, ids=_FAILURE_IDS)
async def test_a_failed_validation_over_a_downloading_row_quarantines_it_as_before(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    failure: str,
) -> None:
    async def end(
        factory: async_sessionmaker[AsyncSession], capture_id: uuid.UUID, store: _HookedObjectStore
    ) -> None:
        return None

    outcome = await _late_failure(session_factory, monkeypatch, path=path, failure=failure, end=end)

    assert outcome.snapshot["status"] == CaptureStatus.DOWNLOADING
    row = await _row(session_factory, outcome.capture_id)
    assert row["status"] == CaptureStatus.QUARANTINED
    _expected_reason(failure, row["last_error"])
    assert outcome.report["quarantined_total"] == 1
    assert [(a.kind, a.severity) for a in await _alerts(session_factory)] == [
        ("validation_failed", 2)
    ]


# --- The drain recognises its own object --------------------------------------------------------


class _Killed(BaseException):
    """The process dying between the object write and the metadata commit."""


async def test_a_retry_after_a_kill_adopts_the_drains_own_object_whatever_the_new_download(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture_id = await _seed(session_factory)
    store = _HookedObjectStore()

    async def killed(*args: Any, **kwargs: Any) -> bool:
        raise _Killed

    with monkeypatch.context() as patched:
        patched.setattr(CaptureDrain, "_commit_blob_metadata", killed)
        with pytest.raises(_Killed):
            await _run(_drain(session_factory, _Provider(_blob()), store))
    assert store.objects[_KEY] == _DOWNLOADED
    first = await _row(session_factory, capture_id)
    assert first["status"] == CaptureStatus.DOWNLOADING
    assert first["object_key"] is None

    # The claim goes stale; the source now returns different bytes for the same replay.
    async with session_factory() as session:
        await session.execute(
            update(ReplayCapture)
            .where(ReplayCapture.id == capture_id)
            .values(claimed_at=datetime.now(UTC) - timedelta(hours=1))
        )
        await session.commit()
    report = await _run(_drain(session_factory, _Provider(_blob(_UPLOADED)), store))

    row = await _row(session_factory, capture_id)
    assert row["status"] == CaptureStatus.STORED
    assert row["source"] == CaptureSource.AUTOMATIC
    assert row["object_key"] == _KEY
    assert row["zip_sha256"] == _sha(_DOWNLOADED)
    assert row["zip_bytes"] == len(_DOWNLOADED)
    assert row["inner_bytes"] == len(_DOWNLOADED) * 2  # the held bytes were the ones validated
    assert store.objects[_KEY] == _DOWNLOADED
    assert report["stored_total"] == 1


@pytest.mark.parametrize("marker", [{}, {"source": "manual"}], ids=["none", "other-source"])
async def test_a_held_object_without_the_drains_marker_and_another_hash_is_handed_back(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None, marker: dict[str, str]
) -> None:
    capture_id = await _seed(session_factory)
    store = _HookedObjectStore({_KEY: _UPLOADED}, {_KEY: marker})

    await _run(_drain(session_factory, _Provider(_blob()), store))

    row = await _row(session_factory, capture_id)
    assert row["status"] == CaptureStatus.PENDING
    assert row["object_key"] is None
    assert row["zip_sha256"] is None
    assert "different object" in row["last_error"]
    assert store.objects[_KEY] == _UPLOADED


async def test_the_drain_marks_its_own_object(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    await _seed(session_factory)
    store = _HookedObjectStore()

    await _run(_drain(session_factory, _Provider(_blob()), store))

    assert store.metadata[_KEY] == {"source": "automatic"}


# --- A concurrent conditional write ---------------------------------------------------------------


async def test_a_concurrent_write_hands_the_claim_back_without_an_attempt_and_the_run_goes_on(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    other_game = _GAME_ID + 1
    contended = await _seed(
        session_factory, age=timedelta(days=3)
    )  # earliest deadline: claimed first
    other = await _seed(session_factory, game_id=other_game)
    store = _HookedObjectStore()
    store.conflict_keys.add(_KEY)

    report = await _run(_drain(session_factory, _Provider(_blob()), store))

    row = await _row(session_factory, contended)
    assert row["status"] == CaptureStatus.PENDING
    assert row["attempts"] == 0
    assert row["object_key"] is None
    assert row["zip_sha256"] is None
    assert row["claimed_at"] is None
    assert _KEY not in store.objects
    # The run did not stop: the next capture was drained.
    assert (await _row(session_factory, other))["status"] == CaptureStatus.STORED
    assert report["stored_total"] == 1


# --- The real upload write, interleaved with the drain ------------------------------------------


async def _upload_with_a_drain_between_its_load_and_its_write(
    session_factory: async_sessionmaker[AsyncSession],
    store: _HookedObjectStore,
    between: Callable[[], Awaitable[None]],
) -> None:
    """`upload_replay`'s sequence (`routers/replays.py`): load the row, `put_if_absent`, then
    `CapturesRepository.record_manual_upload`; the drain runs once after the repository has loaded
    the row and before it writes."""
    async with session_factory() as session:
        existing = await session.scalar(
            select(ReplayCapture).where(
                ReplayCapture.game_id == _GAME_ID, ReplayCapture.profile_id == _PROFILE_ID
            )
        )
        assert existing is not None and existing.object_key is None
        assert await store.put_if_absent(_KEY, _UPLOADED, content_type=REPLAY_CONTENT_TYPE)

        original_execute, original_flush = session.execute, session.flush
        fired = False

        async def run_between() -> None:
            nonlocal fired
            if not fired:
                fired = True
                await between()

        async def execute(statement: Any, *args: Any, **kwargs: Any) -> Any:
            if isinstance(statement, Update):
                await run_between()
            return await original_execute(statement, *args, **kwargs)

        async def flush(*args: Any, **kwargs: Any) -> None:
            await run_between()
            await original_flush(*args, **kwargs)

        # The repository has loaded the row by the time either of its writes starts.
        session.execute = execute  # type: ignore[method-assign]
        session.flush = flush  # type: ignore[method-assign]
        await CapturesRepository(session).record_manual_upload(
            game_id=_GAME_ID,
            profile_id=_PROFILE_ID,
            object_key=_KEY,
            zip_bytes=len(_UPLOADED),
            zip_sha256=_sha(_UPLOADED),
            inner_filename="MP Replay v101.101 @2026.10.16 130000 (1).aoe2record",
            inner_bytes=4096,
            validated_by="uploader-engine@9.9.9",
            match_completed_at=datetime.now(UTC) - timedelta(days=1),
            capture_budget_days=_CAPTURE_BUDGET_DAYS,
        )
        await session.commit()


@pytest.mark.parametrize(
    ("attempts", "drain_outcome"), [(0, CaptureStatus.PENDING), (2, CaptureStatus.FAILED)]
)
async def test_the_real_upload_write_wins_over_a_drain_that_ran_between_its_load_and_its_write(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    attempts: int,
    drain_outcome: CaptureStatus,
) -> None:
    capture_id = await _seed(session_factory, attempts=attempts)
    store = _HookedObjectStore()
    snapshot: dict[str, Any] = {}

    drain = _drain(session_factory, _Provider(_blob()), store, max_attempts=3)

    async def drain_and_snapshot() -> None:
        await _run(drain)
        snapshot.update(await _row(session_factory, capture_id))

    await _upload_with_a_drain_between_its_load_and_its_write(
        session_factory, store, drain_and_snapshot
    )

    # The drain really did hand the row back / fail it before the upload wrote.
    assert snapshot["status"] == drain_outcome
    assert "different object" in snapshot["last_error"]

    row = await _row(session_factory, capture_id)
    assert row["status"] == CaptureStatus.STORED
    assert row["source"] == CaptureSource.MANUAL
    assert row["last_error"] is None
    assert row["object_key"] == _KEY
    assert row["zip_sha256"] == _sha(_UPLOADED)
    assert row["validated_by"] == "uploader-engine@9.9.9"
    assert store.objects[_KEY] == _UPLOADED
