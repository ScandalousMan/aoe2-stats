"""T673: re-validate the captures that ended `quarantined` because the engine could not parse them.

Context (feature 006, Phase 7): `aoe2rec-py` 0.1.21 panicked on the one recording measured as game
build 185872 (`docs/risks.md`); a capture the engine cannot parse ends `quarantined` with the object
kept (constitution IV). 0.1.24 reads that recording (T672); `CaptureDrain.revalidate_quarantined`
reads each committed object back, checks it against the row's own `zip_sha256`, and runs it through
the same containment barrier the capture path uses.

What every test below pins, with its contrast case (the boundary and the thing just across it):

- **Selection is the engine's own failure text, never an integrity quarantine.** The text is read
  from what `_validate_with_barrier` actually writes (`test_the_text_the_barrier_writes_is_what_
  the_selection_matches`), not from a copy of it here. Across the boundary: `reclaim could not read
  back ...` and `reclaim checksum mismatch ...` (integrity), `validation exceeded the ...s
  wall-clock cap` (a timeout says nothing about the bytes) and `MalformedArchiveError: ...` (this
  repository's own archive rule, which a newer engine cannot change) are never reopened.
- **Read-only against the world.** The replay provider records zero calls; the object store sees
  `get` and nothing else (no `put`, no `delete`).
- **A row whose object no longer matches `zip_sha256` is left exactly as it was.** Not stored, not
  re-quarantined, not given a new error.
- **No alert.** A row that stays quarantined already raised its `validation_failed`; this is a
  maintenance read, not a capture outcome.
- **Ordered, bounded, resumable.** Oldest recording first (an ordering, nothing more), at most
  `limit` rows, resumable with `after`, the full `(completed_at, id)` cursor; a second run rewrites
  a row only with the engine's verdict.
- **Only a capture with an active, non-objecting owner is taken (T673b),** at selection and again
  in each guarded write's own `WHERE`: the stored write and the quarantine write are tested
  separately. A row a write refuses is an outcome of its own, `ownership_changed`.
- **A database error on a write stops the run at that row** and returns the report so far.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_core.replay.validation import (
    EngineParseError,
    MalformedArchiveError,
    ReplayValidationResult,
)
from aoe2stats_ingester.budget import Budget
from aoe2stats_providers.base import ReplayBlob
from aoe2stats_storage.models import (
    Alert,
    AoeProfile,
    CaptureSource,
    CaptureStatus,
    Match,
    ProfileLink,
    ReplayCapture,
    SteamIdentity,
    User,
)
from aoe2stats_storage.objects import ObjectNotFound, replay_object_key

_GOOD = b"good-recording-bytes"
_BAD = b"bad-recording-bytes"

_ENGINE_VERSION = "0.1.24"

#: What `_validate_with_barrier` wrote for a 0.1.21 panic, per `apps/analyzer/tests/
#: test_engine_panic.py`'s measured class name: `<ClassName>: <text>`.
_PANIC_REASON = "PanicException: called `Result::unwrap()` on an `Err` value: \n 0: bad magic"
_PARSE_REASON = "EngineParseError: aoe2rec-py rejected the replay: bad magic at 0x7f376"

_MISSING_OBJECT_REASON = (
    "reclaim could not read back 'replays/1/2.zip' from the object store: ObjectNotFound: x"
)
_MISMATCH_REASON = (
    "reclaim checksum mismatch for 'replays/1/2.zip': row records aa, object store holds bb"
)
_TIMEOUT_REASON = "validation exceeded the 30.0s wall-clock cap"
_MALFORMED_REASON = "MalformedArchiveError: not a zip archive: File is not a zip file"

_SHARED_AT = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


# --- Fakes -----------------------------------------------------------------------------------


class _RecordingObjectStore:
    """The `_ObjectPut` Protocol (`capture.py`), recording every call. `put` and `delete` are
    present so that a regression that reaches for them is a recorded failure, not an
    `AttributeError` the drain might swallow."""

    def __init__(self, objects: dict[str, bytes] | None = None) -> None:
        self.objects: dict[str, bytes] = dict(objects or {})
        self.gets: list[str] = []
        self.puts: list[str] = []
        self.deletes: list[str] = []

    async def get(self, key: str) -> bytes:
        self.gets.append(key)
        if key not in self.objects:
            raise ObjectNotFound(key)
        return self.objects[key]

    async def put(self, key: str, body: bytes, *, content_type: str = "") -> None:
        self.puts.append(key)
        self.objects[key] = body

    async def delete(self, key: str) -> None:
        self.deletes.append(key)
        self.objects.pop(key, None)


class _RecordingReplayProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[int, int]] = []

    async def fetch_replay(self, game_id: int, profile_id: int) -> ReplayBlob:
        self.calls.append((game_id, profile_id))
        raise AssertionError("a re-validation must never download")


class _Validator:
    """Opens `_GOOD`, rejects everything else the way the engine does; counts its calls."""

    def __init__(self, *, reject_with: Exception | None = None) -> None:
        self.calls = 0
        self._reject_with = reject_with

    def validate(self, zip_bytes: bytes) -> ReplayValidationResult:
        self.calls += 1
        if self._reject_with is not None:
            raise self._reject_with
        if zip_bytes != _GOOD:
            raise EngineParseError("aoe2rec-py rejected the replay: bad magic")
        return ReplayValidationResult(
            inner_filename="AgeIIDE_Replay_1.aoe2record",
            inner_bytes=4242,
            engine_name="aoe2rec-py",
            engine_version=_ENGINE_VERSION,
        )


class _AlertSink:
    def __init__(self) -> None:
        self.written: list[Any] = []

    async def write(self, **kwargs: Any) -> Any:
        self.written.append(kwargs)
        raise AssertionError("a re-validation raises no alert")

    async def unacknowledged_severity_one(self) -> list[Any]:
        return []


def _drain(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    store: _RecordingObjectStore,
    provider: _RecordingReplayProvider,
    validator: _Validator,
    sink: _AlertSink | None = None,
) -> Any:
    from aoe2stats_ingester.capture import CaptureDrain

    return CaptureDrain(
        session_factory=session_factory,
        replay_provider=provider,  # type: ignore[arg-type]
        object_store=store,
        validator=validator,
        alert_sink=sink or _AlertSink(),  # type: ignore[arg-type]
        validation_timeout_seconds=5.0,
    )


# --- Seeding ---------------------------------------------------------------------------------


async def _seed(
    db_session: AsyncSession,
    store: _RecordingObjectStore,
    *,
    game_id: int,
    status: CaptureStatus = CaptureStatus.QUARANTINED,
    last_error: str | None = _PANIC_REASON,
    completed_at: datetime | None = None,
    content: bytes = _GOOD,
    stored_object: bytes | None = _GOOD,
    recorded_sha256: bytes | None = None,
    with_object_key: bool = True,
    sha256_null: bool = False,
    linked: bool = True,
) -> uuid.UUID:
    """One capture row plus, when `stored_object` is not None, the object under its key.

    `recorded_sha256` is the content the *row* believes it holds (default: `content`), so a test
    can make the object drift from the row's own record. `sha256_null` keeps `object_key` and
    clears the checksum. `linked` gives the profile an active link whose user has not objected,
    which a capture needs to be selected (T673b); pass `False` to seed the link by hand."""
    profile_id = game_id + 1_000_000
    completed_at = completed_at or (datetime.now(UTC) - timedelta(days=5))
    key = replay_object_key(game_id, profile_id)
    if stored_object is not None:
        store.objects[key] = stored_object
    db_session.add(AoeProfile(profile_id=profile_id, alias=f"p-{profile_id}", country="FR"))
    db_session.add(
        Match(
            game_id=game_id,
            leaderboard_id=3,
            completed_at=completed_at,
            source="relic",
            raw_payload={},
        )
    )
    capture_id = uuid.uuid4()
    db_session.add(
        ReplayCapture(
            id=capture_id,
            game_id=game_id,
            profile_id=profile_id,
            status=status,
            capture_deadline_at=completed_at + timedelta(days=21),
            source=CaptureSource.AUTOMATIC,
            object_key=key if with_object_key else None,
            zip_bytes=len(content),
            zip_sha256=hashlib.sha256(recorded_sha256 or content).hexdigest()
            if with_object_key and not sha256_null
            else None,
            last_error=last_error,
            attempts=1,
        )
    )
    await db_session.commit()
    if linked:
        await _link_profile(db_session, profile_id, objected=False)
    return capture_id


async def _row(db_session: AsyncSession, capture_id: uuid.UUID) -> ReplayCapture:
    db_session.expire_all()
    row = await db_session.get(ReplayCapture, capture_id)
    assert row is not None
    return row


def _snapshot(row: ReplayCapture) -> tuple[Any, ...]:
    return (
        row.status,
        row.last_error,
        row.stored_at,
        row.validated_by,
        row.inner_filename,
        row.inner_bytes,
        row.http_status,
        row.object_key,
        row.zip_sha256,
        row.zip_bytes,
        row.attempts,
    )


# --- (a) now validates -> stored, as the normal path stores it (but `stored_at` is now) -------


@pytest.mark.parametrize("reason", [_PANIC_REASON, _PARSE_REASON])
async def test_an_engine_failure_row_whose_object_now_validates_ends_stored_like_the_normal_path(
    reason: str,
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    store = _RecordingObjectStore()
    provider = _RecordingReplayProvider()
    capture_id = await _seed(db_session, store, game_id=700_001, last_error=reason)
    before = await _row(db_session, capture_id)
    key, sha, size = before.object_key, before.zip_sha256, before.zip_bytes

    # The normal path, for the same bytes, on a sibling row: the reference for "exactly as".
    normal_id = await _seed(
        db_session,
        store,
        game_id=700_002,
        status=CaptureStatus.PENDING,
        last_error=None,
        with_object_key=False,
        stored_object=None,
    )
    normal_provider = _RecordingReplayProvider()

    async def _fetch(game_id: int, profile_id: int) -> ReplayBlob:
        return ReplayBlob(content=_GOOD, filename="x", content_type="application/zip")

    normal_provider.fetch_replay = _fetch  # type: ignore[method-assign]
    await _drain(
        session_factory,
        store=_RecordingObjectStore(),
        provider=normal_provider,
        validator=_Validator(),
    )(Budget(seconds=30))
    normal = await _row(db_session, normal_id)
    assert normal.status == CaptureStatus.STORED
    normal_values = (normal.validated_by, normal.inner_filename, normal.inner_bytes)

    report = await _drain(
        session_factory, store=store, provider=provider, validator=_Validator()
    ).revalidate_quarantined(limit=10)

    row = await _row(db_session, capture_id)
    assert row.status == CaptureStatus.STORED
    assert row.last_error is None
    assert row.stored_at is not None
    assert row.http_status == 200
    # `validated_by` and the inner fields are set as the normal path sets them; `stored_at` is the
    # time of this re-validation, so it is not compared with the sibling's.
    assert row.validated_by == normal_values[0] == f"aoe2rec-py@{_ENGINE_VERSION}"
    assert (row.inner_filename, row.inner_bytes) == normal_values[1:]
    # The row's own record of the object is untouched.
    assert (row.object_key, row.zip_sha256, row.zip_bytes) == (key, sha, size)
    assert [o.outcome for o in report.outcomes] == ["stored"]


# --- (b) still fails -> quarantined with the NEW error, no alert -----------------------------


async def test_an_engine_failure_row_that_still_fails_stays_quarantined_with_the_new_error(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    store = _RecordingObjectStore()
    capture_id = await _seed(db_session, store, game_id=700_010, last_error=_PANIC_REASON)
    sink = _AlertSink()

    report = await _drain(
        session_factory,
        store=store,
        provider=_RecordingReplayProvider(),
        validator=_Validator(reject_with=EngineParseError("aoe2rec-py found no recording chapter")),
        sink=sink,
    ).revalidate_quarantined(limit=10)

    row = await _row(db_session, capture_id)
    assert row.status == CaptureStatus.QUARANTINED
    assert row.last_error == "EngineParseError: aoe2rec-py found no recording chapter"
    assert row.stored_at is None
    assert row.validated_by is None
    assert [o.outcome for o in report.outcomes] == ["still_quarantined"]
    # Decision (T673): no `validation_failed` alert, neither for a changed nor an unchanged reason.
    assert sink.written == []
    assert (await db_session.scalar(select(func.count()).select_from(Alert))) == 0


async def test_a_row_that_fails_with_an_unchanged_reason_is_rewritten_without_an_alert(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    store = _RecordingObjectStore()
    capture_id = await _seed(db_session, store, game_id=700_011, last_error=_PARSE_REASON)
    sink = _AlertSink()

    await _drain(
        session_factory,
        store=store,
        provider=_RecordingReplayProvider(),
        validator=_Validator(
            reject_with=EngineParseError("aoe2rec-py rejected the replay: bad magic at 0x7f376")
        ),
        sink=sink,
    ).revalidate_quarantined(limit=10)

    row = await _row(db_session, capture_id)
    assert row.status == CaptureStatus.QUARANTINED
    assert row.last_error == _PARSE_REASON
    assert sink.written == []


# --- (c), (d), (e) and the other texts: never selected ---------------------------------------


@pytest.mark.parametrize(
    "reason",
    [
        pytest.param(_MISSING_OBJECT_REASON, id="integrity-missing-object"),
        pytest.param(_MISMATCH_REASON, id="integrity-checksum-mismatch"),
        pytest.param(_TIMEOUT_REASON, id="timeout"),
        pytest.param(_MALFORMED_REASON, id="malformed-archive"),
        pytest.param(None, id="no-reason"),
        pytest.param("", id="empty-reason"),
        pytest.param("something else entirely", id="unknown-text"),
        # A reason that merely *contains* an engine class name is not the engine's own text.
        pytest.param("reclaim could not read back x: EngineParseError: y", id="embedded-class"),
        pytest.param("xPanicException: z", id="prefix-lookalike"),
    ],
)
async def test_a_quarantine_that_is_not_the_engines_own_failure_is_never_selected(
    reason: str | None,
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    store = _RecordingObjectStore()
    # The object is intact and WOULD validate: only the selection can keep it out.
    capture_id = await _seed(db_session, store, game_id=700_020, last_error=reason)
    before = _snapshot(await _row(db_session, capture_id))
    validator = _Validator()

    report = await _drain(
        session_factory, store=store, provider=_RecordingReplayProvider(), validator=validator
    ).revalidate_quarantined(limit=10)

    assert report.outcomes == ()
    assert validator.calls == 0
    assert store.gets == []
    assert _snapshot(await _row(db_session, capture_id)) == before


async def test_a_missing_object_quarantine_is_not_reopened_even_if_the_object_reappears(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """(c) in its real shape: the row was quarantined because the object was missing, and the
    key now resolves. It still stays quarantined: that is evidence for a human (data-model.md)."""
    store = _RecordingObjectStore()
    capture_id = await _seed(
        db_session, store, game_id=700_021, last_error=_MISSING_OBJECT_REASON, stored_object=_GOOD
    )

    report = await _drain(
        session_factory, store=store, provider=_RecordingReplayProvider(), validator=_Validator()
    ).revalidate_quarantined(limit=10)

    assert report.outcomes == ()
    row = await _row(db_session, capture_id)
    assert row.status == CaptureStatus.QUARANTINED
    assert row.last_error == _MISSING_OBJECT_REASON


async def test_the_text_the_barrier_writes_is_what_the_selection_matches(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The selection must follow the barrier, not a copy of its output: take the reasons straight
    from `_validate_with_barrier` for the three engine-side failure shapes."""
    from aoe2stats_ingester.capture import _validate_with_barrier

    class PanicException(BaseException):
        pass

    class _Raises:
        def __init__(self, exc: BaseException) -> None:
            self._exc = exc

        def validate(self, zip_bytes: bytes) -> ReplayValidationResult:
            raise self._exc

    selected: dict[str, str] = {}
    not_selected: dict[str, str] = {}
    for label, exc, bucket in (
        ("panic", PanicException("called `Result::unwrap()`"), selected),
        ("empty-panic", PanicException(), selected),
        ("parse", EngineParseError("aoe2rec-py rejected the replay: x"), selected),
        ("malformed", MalformedArchiveError("not a zip archive"), not_selected),
    ):
        _, reason = await _validate_with_barrier(_Raises(exc), b"x", timeout_seconds=5.0)  # type: ignore[arg-type]
        assert reason
        bucket[label] = reason
    _, timeout_reason = await _validate_with_barrier(
        _SlowValidator(),
        b"x",
        timeout_seconds=0.05,  # type: ignore[arg-type]
    )
    assert timeout_reason
    not_selected["timeout"] = timeout_reason

    store = _RecordingObjectStore()
    ids: dict[str, uuid.UUID] = {}
    for offset, (label, reason) in enumerate({**selected, **not_selected}.items()):
        ids[label] = await _seed(db_session, store, game_id=700_030 + offset, last_error=reason)

    report = await _drain(
        session_factory, store=store, provider=_RecordingReplayProvider(), validator=_Validator()
    ).revalidate_quarantined(limit=50)

    assert {o.capture_id for o in report.outcomes} == {ids[label] for label in selected}


class _SlowValidator:
    def validate(self, zip_bytes: bytes) -> ReplayValidationResult:
        import time

        time.sleep(0.5)
        raise AssertionError("the cap must win")


# --- (f) read-only against the world ---------------------------------------------------------


async def test_a_revalidation_never_downloads_and_the_object_store_sees_only_get(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    store = _RecordingObjectStore()
    provider = _RecordingReplayProvider()
    await _seed(db_session, store, game_id=700_040)  # validates -> stored
    await _seed(db_session, store, game_id=700_041, content=_BAD, stored_object=_BAD)  # fails again
    await _seed(db_session, store, game_id=700_042, stored_object=None)  # object missing
    await _seed(db_session, store, game_id=700_043, stored_object=b"drifted")  # sha mismatch
    objects_before = dict(store.objects)

    report = await _drain(
        session_factory, store=store, provider=provider, validator=_Validator()
    ).revalidate_quarantined(limit=10)

    assert len(report.outcomes) == 4
    assert provider.calls == []
    assert store.puts == []
    assert store.deletes == []
    assert len(store.gets) == 4
    assert store.objects == objects_before


# --- (g) the object no longer matches the row's own checksum ---------------------------------


async def test_an_object_that_no_longer_matches_the_rows_checksum_is_left_alone(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    store = _RecordingObjectStore()
    # The row recorded `_BAD`'s hash; the store now holds bytes that WOULD validate. They are not
    # the bytes the row vouches for, so they must not be marked stored on the row's behalf.
    capture_id = await _seed(
        db_session,
        store,
        game_id=700_050,
        content=_BAD,
        stored_object=_GOOD,
    )
    before = _snapshot(await _row(db_session, capture_id))
    validator = _Validator()

    report = await _drain(
        session_factory, store=store, provider=_RecordingReplayProvider(), validator=validator
    ).revalidate_quarantined(limit=10)

    assert [o.outcome for o in report.outcomes] == ["integrity_failure"]
    assert "checksum" in (report.outcomes[0].reason or "")
    assert validator.calls == 0
    assert _snapshot(await _row(db_session, capture_id)) == before


async def test_an_engine_failure_row_whose_object_is_missing_is_left_alone_not_requarantined(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    store = _RecordingObjectStore()
    capture_id = await _seed(db_session, store, game_id=700_051, stored_object=None)
    before = _snapshot(await _row(db_session, capture_id))

    report = await _drain(
        session_factory, store=store, provider=_RecordingReplayProvider(), validator=_Validator()
    ).revalidate_quarantined(limit=10)

    assert [o.outcome for o in report.outcomes] == ["integrity_failure"]
    assert _snapshot(await _row(db_session, capture_id)) == before


# --- (h) other statuses, and rows with no object, are untouched ------------------------------


@pytest.mark.parametrize(
    "status",
    [
        CaptureStatus.STORED,
        CaptureStatus.EXPIRED,
        CaptureStatus.DOWNLOADING,
        CaptureStatus.PENDING,
        CaptureStatus.FAILED,
        CaptureStatus.UNAVAILABLE,
    ],
)
async def test_a_row_in_another_status_is_untouched_even_with_an_engine_failure_text(
    status: CaptureStatus,
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    store = _RecordingObjectStore()
    other = await _seed(db_session, store, game_id=700_060, status=status, last_error=_PANIC_REASON)
    quarantined = await _seed(db_session, store, game_id=700_061)  # the contrast: selected
    before = _snapshot(await _row(db_session, other))

    report = await _drain(
        session_factory, store=store, provider=_RecordingReplayProvider(), validator=_Validator()
    ).revalidate_quarantined(limit=10)

    assert [o.capture_id for o in report.outcomes] == [quarantined]
    assert _snapshot(await _row(db_session, other)) == before
    assert (await _row(db_session, quarantined)).status == CaptureStatus.STORED


async def test_a_quarantined_row_with_no_committed_object_is_not_selected(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    store = _RecordingObjectStore()
    capture_id = await _seed(
        db_session, store, game_id=700_062, with_object_key=False, stored_object=None
    )
    before = _snapshot(await _row(db_session, capture_id))

    report = await _drain(
        session_factory, store=store, provider=_RecordingReplayProvider(), validator=_Validator()
    ).revalidate_quarantined(limit=10)

    assert report.outcomes == ()
    assert _snapshot(await _row(db_session, capture_id)) == before


# --- ordering, bound, resumption, repeat runs, dry run ---------------------------------------


async def test_the_selection_is_oldest_recording_first_bounded_and_resumable(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    store = _RecordingObjectStore()
    now = datetime.now(UTC)
    # Seeded out of order, so neither insertion order nor game id can explain the result.
    ages = {700_070: 3, 700_071: 20, 700_072: 9, 700_073: 14, 700_074: 1}
    ids = {
        game_id: await _seed(
            db_session, store, game_id=game_id, completed_at=now - timedelta(days=days)
        )
        for game_id, days in ages.items()
    }
    expected = [ids[g] for g in sorted(ages, key=lambda g: -ages[g])]  # oldest first
    drain = _drain(
        session_factory, store=store, provider=_RecordingReplayProvider(), validator=_Validator()
    )

    first = await drain.revalidate_quarantined(limit=2, dry_run=True)
    assert [o.capture_id for o in first.outcomes] == expected[:2]
    assert first.truncated is True
    # Each field of the cursor names the last row examined, not merely "something".
    last_game = sorted(ages, key=lambda g: -ages[g])[1]
    assert first.last_capture_id == expected[1]
    assert first.last_completed_at == now - timedelta(days=ages[last_game])
    assert first.cursor == (now - timedelta(days=ages[last_game]), expected[1])

    # Resume from the cursor the report names: the next two, then the last one, then nothing.
    second = await drain.revalidate_quarantined(limit=2, dry_run=True, after=first.cursor)
    assert [o.capture_id for o in second.outcomes] == expected[2:4]
    assert second.truncated is True
    assert second.cursor == (
        now - timedelta(days=ages[sorted(ages, key=lambda g: -ages[g])[3]]),
        expected[3],
    )
    third = await drain.revalidate_quarantined(limit=2, dry_run=True, after=second.cursor)
    assert [o.capture_id for o in third.outcomes] == expected[4:]
    assert third.truncated is False

    # A real run with exactly enough room is not "truncated".
    full = await drain.revalidate_quarantined(limit=5)
    assert [o.capture_id for o in full.outcomes] == expected
    assert full.truncated is False


async def test_a_limit_below_one_is_refused(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    drain = _drain(
        session_factory,
        store=_RecordingObjectStore(),
        provider=_RecordingReplayProvider(),
        validator=_Validator(),
    )
    with pytest.raises(ValueError, match="limit"):
        await drain.revalidate_quarantined(limit=0)


async def test_a_second_run_changes_nothing(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    store = _RecordingObjectStore()
    fixed = await _seed(db_session, store, game_id=700_080)
    still_bad = await _seed(db_session, store, game_id=700_081, content=_BAD, stored_object=_BAD)
    drain = _drain(
        session_factory, store=store, provider=_RecordingReplayProvider(), validator=_Validator()
    )

    first = await drain.revalidate_quarantined(limit=10)
    assert sorted(o.outcome for o in first.outcomes) == ["still_quarantined", "stored"]
    after_first = {c: _snapshot(await _row(db_session, c)) for c in (fixed, still_bad)}

    second = await drain.revalidate_quarantined(limit=10)

    # The stored row is no longer a candidate; the still-failing one is re-read and ends in the
    # identical state (same reason, so the same row content).
    assert [o.capture_id for o in second.outcomes] == [still_bad]
    assert {c: _snapshot(await _row(db_session, c)) for c in (fixed, still_bad)} == after_first


async def test_a_dry_run_selects_without_reading_validating_or_writing(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    store = _RecordingObjectStore()
    capture_id = await _seed(db_session, store, game_id=700_090)
    before = _snapshot(await _row(db_session, capture_id))
    validator = _Validator()

    report = await _drain(
        session_factory, store=store, provider=_RecordingReplayProvider(), validator=validator
    ).revalidate_quarantined(limit=10, dry_run=True)

    assert [o.outcome for o in report.outcomes] == ["selected"]
    assert validator.calls == 0
    assert store.gets == []
    assert _snapshot(await _row(db_session, capture_id)) == before


async def test_a_row_that_changed_between_selection_and_write_is_not_overwritten(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The write is guarded on the row still being `quarantined`: a concurrent maintainer that
    already stored it must not be overwritten (nor given a stale quarantine)."""
    store = _RecordingObjectStore()
    capture_id = await _seed(db_session, store, game_id=700_095)

    class _FlipsTheRowDuringValidation(_Validator):
        def validate(self, zip_bytes: bytes) -> ReplayValidationResult:
            import asyncio

            async def _flip() -> None:
                async with session_factory() as session:
                    row = await session.get(ReplayCapture, capture_id)
                    assert row is not None
                    row.status = CaptureStatus.STORED
                    row.validated_by = "someone-else@1"
                    await session.commit()

            # The barrier runs this in a worker thread, so a private loop is safe here.
            asyncio.run(_flip())
            return super().validate(zip_bytes)

    report = await _drain(
        session_factory,
        store=store,
        provider=_RecordingReplayProvider(),
        validator=_FlipsTheRowDuringValidation(),
    ).revalidate_quarantined(limit=10)

    row = await _row(db_session, capture_id)
    assert row.validated_by == "someone-else@1"
    assert [o.outcome for o in report.outcomes] == ["changed_elsewhere"]


async def _seed_shared_match(
    db_session: AsyncSession,
    store: _RecordingObjectStore,
    *,
    game_id: int,
    capture_ids: list[uuid.UUID],
    completed_at: datetime,
    last_error: str = _PARSE_REASON,
    content: bytes = _BAD,
    linked: bool = True,
) -> None:
    """One match, several tracked profiles: one engine-failure quarantined capture per id in
    `capture_ids`, all carrying the match's single `completed_at` (`uq_replay_captures_game_id_
    profile_id` allows this; `test_shared_match.py`). The ids are given, never `uuid4()`, so the
    `(completed_at, id)` tie order is deterministic."""
    db_session.add(
        Match(
            game_id=game_id,
            leaderboard_id=3,
            completed_at=completed_at,
            source="relic",
            raw_payload={},
        )
    )
    for index, capture_id in enumerate(capture_ids):
        profile_id = game_id * 100 + index
        key = replay_object_key(game_id, profile_id)
        store.objects[key] = content
        db_session.add(AoeProfile(profile_id=profile_id, alias=f"p-{profile_id}", country="FR"))
        await db_session.flush()
        db_session.add(
            ReplayCapture(
                id=capture_id,
                game_id=game_id,
                profile_id=profile_id,
                status=CaptureStatus.QUARANTINED,
                capture_deadline_at=completed_at + timedelta(days=21),
                source=CaptureSource.AUTOMATIC,
                object_key=key,
                zip_bytes=len(content),
                zip_sha256=hashlib.sha256(content).hexdigest(),
                last_error=last_error,
                attempts=1,
            )
        )
    await db_session.commit()
    if linked:
        for index in range(len(capture_ids)):
            await _link_profile(db_session, game_id * 100 + index, objected=False)


def _id(n: int) -> uuid.UUID:
    return uuid.UUID(int=n)


def _cursor(report: Any) -> Any:
    return report.cursor


async def _page_through(drain: Any, *, limit: int) -> tuple[list[list[uuid.UUID]], Any]:
    """Follow the report's own cursor until it stops saying `truncated`, the documented
    procedure. Returns the ids examined on each page and the last report."""
    pages: list[list[uuid.UUID]] = []
    after = None
    for _ in range(20):
        report = await drain.revalidate_quarantined(limit=limit, after=after, dry_run=True)
        pages.append([o.capture_id for o in report.outcomes])
        if not report.truncated:
            return pages, report
        after = _cursor(report)
    raise AssertionError("paging did not terminate")


async def test_three_captures_of_one_match_are_each_examined_once_when_paging_by_one(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    store = _RecordingObjectStore()
    ids = [_id(3), _id(1), _id(2)]
    await _seed_shared_match(
        db_session, store, game_id=700_100, capture_ids=ids, completed_at=_SHARED_AT
    )
    drain = _drain(
        session_factory, store=store, provider=_RecordingReplayProvider(), validator=_Validator()
    )

    pages, last = await _page_through(drain, limit=1)

    assert pages == [[_id(1)], [_id(2)], [_id(3)]]
    assert last.truncated is False


async def test_a_cut_inside_a_shared_timestamp_loses_no_row_when_a_later_match_follows(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    store = _RecordingObjectStore()
    await _seed_shared_match(
        db_session,
        store,
        game_id=700_101,
        capture_ids=[_id(30), _id(10), _id(20)],
        completed_at=_SHARED_AT,
    )
    await _seed_shared_match(
        db_session,
        store,
        game_id=700_102,
        capture_ids=[_id(5), _id(6)],
        completed_at=_SHARED_AT + timedelta(hours=1),
    )
    await _seed_shared_match(
        db_session,
        store,
        game_id=700_103,
        capture_ids=[_id(1)],
        completed_at=_SHARED_AT - timedelta(hours=1),
    )
    drain = _drain(
        session_factory, store=store, provider=_RecordingReplayProvider(), validator=_Validator()
    )

    pages, last = await _page_through(drain, limit=2)

    # (completed_at, id) order; the cut after two rows falls inside the shared timestamp.
    assert [i for page in pages for i in page] == [
        _id(1),
        _id(10),
        _id(20),
        _id(30),
        _id(5),
        _id(6),
    ]
    assert pages == [[_id(1), _id(10)], [_id(20), _id(30)], [_id(5), _id(6)]]
    assert last.truncated is False


async def test_the_cursor_names_the_last_examined_row(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    store = _RecordingObjectStore()
    await _seed_shared_match(
        db_session,
        store,
        game_id=700_104,
        capture_ids=[_id(2), _id(1)],
        completed_at=_SHARED_AT,
    )
    report = await _drain(
        session_factory, store=store, provider=_RecordingReplayProvider(), validator=_Validator()
    ).revalidate_quarantined(limit=1, dry_run=True)

    assert report.last_completed_at == _SHARED_AT
    assert report.last_capture_id == _id(1)
    assert report.cursor == (_SHARED_AT, _id(1))


async def test_a_later_recording_with_a_smaller_id_is_still_returned(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The id only breaks ties; it is not a filter of its own."""
    store = _RecordingObjectStore()
    await _seed_shared_match(
        db_session,
        store,
        game_id=700_105,
        capture_ids=[_id(1)],
        completed_at=_SHARED_AT + timedelta(minutes=1),
    )
    report = await _drain(
        session_factory, store=store, provider=_RecordingReplayProvider(), validator=_Validator()
    ).revalidate_quarantined(limit=10, dry_run=True, after=(_SHARED_AT, _id(999)))

    assert [o.capture_id for o in report.outcomes] == [_id(1)]


async def test_a_row_at_the_cursors_timestamp_with_a_smaller_or_equal_id_is_not_returned_again(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    store = _RecordingObjectStore()
    await _seed_shared_match(
        db_session,
        store,
        game_id=700_106,
        capture_ids=[_id(5), _id(7), _id(9)],
        completed_at=_SHARED_AT,
    )
    report = await _drain(
        session_factory, store=store, provider=_RecordingReplayProvider(), validator=_Validator()
    ).revalidate_quarantined(limit=10, dry_run=True, after=(_SHARED_AT, _id(7)))

    # 5 and 7 were already examined (the cursor is exclusive); 9 was not.
    assert [o.capture_id for o in report.outcomes] == [_id(9)]


# === T673a: remediation of #129's review ======================================================
#
# Every test below was written and run red against the T673 code before its fix. The level each
# one pins is named in its docstring: the selection query, the write guards, or the entry point.


class _TransportDown(Exception):
    """Stands in for any store error that is neither a missing key nor a bad checksum: an outage,
    a denied request, a missing bucket (`ObjectNotFound`'s own docstring says all of them
    propagate as themselves)."""


class _FlakyObjectStore(_RecordingObjectStore):
    def __init__(self, objects: dict[str, bytes], *, fail_on: str) -> None:
        super().__init__(objects)
        self._fail_on = fail_on

    async def get(self, key: str) -> bytes:
        if key == self._fail_on:
            self.gets.append(key)
            raise _TransportDown("endpoint unreachable")
        return await super().get(key)


class _FailsWith(_Validator):
    """Always fails with `exc`; for the failures the barrier folds into a reason text."""


class _SleepsPastTheCap(_Validator):
    def validate(self, zip_bytes: bytes) -> ReplayValidationResult:
        import time

        self.calls += 1
        time.sleep(0.5)
        raise AssertionError("the cap must win")


def _short_cap_drain(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    store: _RecordingObjectStore,
    validator: Any,
) -> Any:
    from aoe2stats_ingester.capture import CaptureDrain

    return CaptureDrain(
        session_factory=session_factory,
        replay_provider=_RecordingReplayProvider(),  # type: ignore[arg-type]
        object_store=store,
        validator=validator,
        alert_sink=_AlertSink(),  # type: ignore[arg-type]
        validation_timeout_seconds=0.05,
    )


# --- Eviction (level: the write guards) ------------------------------------------------------


async def test_a_validation_that_times_out_leaves_the_row_untouched_and_it_is_offered_again(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Level: the write. A timeout says nothing about the bytes; writing its text into
    `last_error` would move the row out of the selection for good."""
    store = _RecordingObjectStore()
    capture_id = await _seed(db_session, store, game_id=710_001, last_error=_PANIC_REASON)
    before = _snapshot(await _row(db_session, capture_id))
    drain = _short_cap_drain(session_factory, store=store, validator=_SleepsPastTheCap())

    first = await drain.revalidate_quarantined(limit=10)

    assert _snapshot(await _row(db_session, capture_id)) == before
    assert [o.outcome for o in first.outcomes] == ["inconclusive"]
    assert "wall-clock cap" in (first.outcomes[0].reason or "")

    # The next run, with an engine that is not slow, offers the same row again and stores it.
    second = await _drain(
        session_factory, store=store, provider=_RecordingReplayProvider(), validator=_Validator()
    ).revalidate_quarantined(limit=10)
    assert [o.capture_id for o in second.outcomes] == [capture_id]
    assert (await _row(db_session, capture_id)).status == CaptureStatus.STORED


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(MalformedArchiveError("not a zip archive"), id="malformed-archive"),
        pytest.param(ValueError("not the engine's wrapper"), id="foreign-exception-class"),
    ],
)
async def test_a_failure_outside_the_engines_verdict_leaves_the_row_untouched(
    error: Exception,
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Level: the write. Any class `_engine_failure_reason` would not select next time is
    reported, not written."""
    store = _RecordingObjectStore()
    capture_id = await _seed(db_session, store, game_id=710_002, last_error=_PARSE_REASON)
    before = _snapshot(await _row(db_session, capture_id))

    report = await _drain(
        session_factory,
        store=store,
        provider=_RecordingReplayProvider(),
        validator=_FailsWith(reject_with=error),
    ).revalidate_quarantined(limit=10)

    assert _snapshot(await _row(db_session, capture_id)) == before
    assert [o.outcome for o in report.outcomes] == ["inconclusive"]
    assert (report.outcomes[0].reason or "").startswith(type(error).__name__)


async def test_a_panic_text_is_a_new_engine_verdict_and_is_written(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Contrast for the two above: the same write, for a reason the selection still matches."""

    class PanicException(BaseException):
        pass

    store = _RecordingObjectStore()
    capture_id = await _seed(db_session, store, game_id=710_003, last_error=_PARSE_REASON)

    report = await _drain(
        session_factory,
        store=store,
        provider=_RecordingReplayProvider(),
        validator=_FailsWith(reject_with=PanicException("a new panic")),  # type: ignore[arg-type]
    ).revalidate_quarantined(limit=10)

    row = await _row(db_session, capture_id)
    assert row.last_error == "PanicException: a new panic"
    assert [o.outcome for o in report.outcomes] == ["still_quarantined"]


# --- Objection (level: the selection query) --------------------------------------------------


async def _link_profile(
    db_session: AsyncSession,
    profile_id: int,
    *,
    objected: bool,
    unlinked: bool = False,
    second_user: bool = False,
) -> uuid.UUID:
    """A user (with a Steam identity) linked to `profile_id`; returns the user's id.
    `second_user` gives the identity a different Steam id, for a profile linked twice over time
    (the first link ended with `unlinked=True`)."""
    now = datetime.now(UTC)
    user_id = uuid.uuid4()
    steam_id64 = f"{'76561199' if second_user else '76561198'}{profile_id:010d}"
    db_session.add(
        User(
            id=user_id,
            created_at=now,
            allowlisted_at=now,
            archival_objected_at=now if objected else None,
        )
    )
    db_session.add(
        SteamIdentity(steam_id64=steam_id64, user_id=user_id, verified_at=now, last_sign_in_at=now)
    )
    await db_session.flush()
    db_session.add(
        ProfileLink(
            id=uuid.uuid4(),
            user_id=user_id,
            profile_id=profile_id,
            steam_id64=steam_id64,
            is_primary=True,
            linked_at=now,
            unlinked_at=now if unlinked else None,
        )
    )
    await db_session.commit()
    return user_id


async def test_an_objecting_users_capture_is_not_selected_but_another_profile_of_the_match_is(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Level: the selection query (constitution IX; 001's quarantined-is-not-archived). Four
    tracked profiles captured one match. Only a profile with an active link whose user has not
    objected is taken: an active objector is out, an objector who has since unlinked is out (their
    profile has no active link), a profile with no link at all is out, and a profile relinked by a
    second user who has not objected is in, as is the plain consenting one."""
    store = _RecordingObjectStore()
    await _seed_shared_match(
        db_session,
        store,
        game_id=710_100,
        capture_ids=[_id(1), _id(2), _id(3), _id(4), _id(5)],
        completed_at=_SHARED_AT,
        content=_GOOD,
        linked=False,
    )
    objecting, consenting, unlinked_objector, _never_linked, relinked = (
        710_100 * 100 + i for i in range(5)
    )
    await _link_profile(db_session, objecting, objected=True)
    await _link_profile(db_session, consenting, objected=False)
    await _link_profile(db_session, unlinked_objector, objected=True, unlinked=True)
    # The objector unlinked and a second user, who has not objected, took the profile over.
    await _link_profile(db_session, relinked, objected=True, unlinked=True)
    await _link_profile(db_session, relinked, objected=False, second_user=True)
    out = {i: _snapshot(await _row(db_session, _id(i))) for i in (1, 3, 4)}
    validator = _Validator()

    report = await _drain(
        session_factory, store=store, provider=_RecordingReplayProvider(), validator=validator
    ).revalidate_quarantined(limit=10)

    assert {o.capture_id for o in report.outcomes} == {_id(2), _id(5)}
    assert validator.calls == 2
    for index, snapshot in out.items():
        assert _snapshot(await _row(db_session, _id(index))) == snapshot
    assert (await _row(db_session, _id(2))).status == CaptureStatus.STORED
    assert (await _row(db_session, _id(5))).status == CaptureStatus.STORED


async def test_an_objecting_users_capture_is_not_offered_by_a_dry_run_either(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    store = _RecordingObjectStore()
    await _seed_shared_match(
        db_session,
        store,
        game_id=710_101,
        capture_ids=[_id(1)],
        completed_at=_SHARED_AT,
        linked=False,
    )
    await _link_profile(db_session, 710_101 * 100, objected=True)

    report = await _drain(
        session_factory, store=store, provider=_RecordingReplayProvider(), validator=_Validator()
    ).revalidate_quarantined(limit=10, dry_run=True)

    assert report.outcomes == ()


def test_the_claim_keeps_its_own_predicate_and_the_revalidation_uses_the_archiving_set() -> None:
    """Level: the code. The claim still excludes a *found* objection (`_objecting_owner_exists`;
    T673b does not change the claim path), while the re-validation's selection and both of its
    guarded writes use `_owner_is_archiving`, which is `discover.archiving_links`'s set."""
    import inspect

    from aoe2stats_ingester import capture

    assert "_objecting_owner_exists()" in inspect.getsource(capture.CaptureDrain._claim_batch)
    assert "_owner_is_archiving" not in inspect.getsource(capture.CaptureDrain._claim_batch)
    assert "archiving_links()" in inspect.getsource(capture._owner_is_archiving)
    assert "_owner_is_archiving()" in inspect.getsource(capture._revalidation_selection)
    assert "_owner_is_archiving()" in inspect.getsource(capture.CaptureDrain._mark_stored)
    assert "_owner_is_archiving()" in inspect.getsource(capture.CaptureDrain._mark_quarantined)


# --- Guard (level: the write guards) ---------------------------------------------------------


class _StoresTheRowThenFails(_Validator):
    """Another writer stores the row while this validation runs; this validation then fails."""

    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], capture_id: uuid.UUID
    ) -> None:
        super().__init__()
        self._session_factory = session_factory
        self._capture_id = capture_id

    def validate(self, zip_bytes: bytes) -> ReplayValidationResult:
        import asyncio

        async def _flip() -> None:
            async with self._session_factory() as session:
                row = await session.get(ReplayCapture, self._capture_id)
                assert row is not None
                row.status = CaptureStatus.STORED
                row.last_error = None
                row.validated_by = "someone-else@1"
                await session.commit()

        asyncio.run(_flip())  # the barrier runs this in a worker thread: a private loop is safe
        raise EngineParseError("aoe2rec-py rejected the replay: still bad")


async def test_a_failing_validation_does_not_quarantine_a_row_another_writer_stored(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Level: the quarantine write's status guard. The existing test exercises the stored write
    only; dropping this guard passed every test."""
    store = _RecordingObjectStore()
    capture_id = await _seed(db_session, store, game_id=710_200)

    report = await _drain(
        session_factory,
        store=store,
        provider=_RecordingReplayProvider(),
        validator=_StoresTheRowThenFails(session_factory, capture_id),
    ).revalidate_quarantined(limit=10)

    row = await _row(db_session, capture_id)
    assert row.status == CaptureStatus.STORED
    assert row.validated_by == "someone-else@1"
    assert row.last_error is None
    assert [o.outcome for o in report.outcomes] == ["changed_elsewhere"]


# --- Integrity versus transport (level: the read-back) ---------------------------------------


async def test_a_store_error_that_is_not_an_integrity_outcome_aborts_the_run_with_no_write(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Level: the read-back. Only a missing object and a checksum mismatch are per-row. Anything
    else says nothing about the row, so the run stops: the row is untouched and the rows after it
    are not examined."""
    first_store = _RecordingObjectStore()
    now = datetime.now(UTC)
    ok = await _seed(db_session, first_store, game_id=710_300, completed_at=now - timedelta(days=9))
    down = await _seed(
        db_session, first_store, game_id=710_301, completed_at=now - timedelta(days=8)
    )
    later = await _seed(
        db_session, first_store, game_id=710_302, completed_at=now - timedelta(days=7)
    )
    store = _FlakyObjectStore(first_store.objects, fail_on=replay_object_key(710_301, 1_710_301))
    before_down = _snapshot(await _row(db_session, down))
    before_later = _snapshot(await _row(db_session, later))

    report = await _drain(
        session_factory, store=store, provider=_RecordingReplayProvider(), validator=_Validator()
    ).revalidate_quarantined(limit=10)

    assert store.gets == [
        replay_object_key(710_300, 1_710_300),
        replay_object_key(710_301, 1_710_301),
    ]
    assert _snapshot(await _row(db_session, down)) == before_down
    assert _snapshot(await _row(db_session, later)) == before_later
    assert (await _row(db_session, ok)).status == CaptureStatus.STORED
    assert [o.capture_id for o in report.outcomes] == [ok]
    assert report.aborted_by == "_TransportDown"


async def test_a_missing_object_and_a_checksum_mismatch_stay_per_row_and_the_run_goes_on(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Contrast: the two integrity outcomes are reported, name their row, and do not abort."""
    store = _RecordingObjectStore()
    now = datetime.now(UTC)
    missing = await _seed(
        db_session,
        store,
        game_id=710_310,
        stored_object=None,
        completed_at=now - timedelta(days=9),
    )
    drifted = await _seed(
        db_session,
        store,
        game_id=710_311,
        stored_object=b"drifted",
        completed_at=now - timedelta(days=8),
    )
    fine = await _seed(db_session, store, game_id=710_312, completed_at=now - timedelta(days=7))

    report = await _drain(
        session_factory, store=store, provider=_RecordingReplayProvider(), validator=_Validator()
    ).revalidate_quarantined(limit=10)

    assert report.aborted_by is None
    assert {o.capture_id: o.outcome for o in report.outcomes} == {
        missing: "integrity_failure",
        drifted: "integrity_failure",
        fine: "stored",
    }


# --- The dry run counts what it does not select (level: the entry point's report) ------------


async def test_a_dry_run_counts_the_quarantined_rows_outside_the_selection_by_reason_class(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    store = _RecordingObjectStore()
    seeded: list[tuple[int, dict[str, Any]]] = [
        (710_400, {}),  # selected: not counted
        (710_401, {"last_error": _PANIC_REASON, "with_object_key": False, "stored_object": None}),
        (710_402, {"last_error": _MISSING_OBJECT_REASON}),
        (710_403, {"last_error": _MISSING_OBJECT_REASON}),
        (710_404, {"last_error": _MISMATCH_REASON}),
        (710_405, {"last_error": _TIMEOUT_REASON}),
        (710_406, {"last_error": _MALFORMED_REASON}),
        (710_407, {"last_error": None}),
        (710_408, {"last_error": "something else entirely, with 'quoted values'"}),
        (710_409, {"last_error": "OtherClass: some text"}),
        (710_412, {"last_error": "ValueError: not an engine class"}),
        (710_410, {"status": CaptureStatus.STORED, "last_error": None}),  # not quarantined
    ]
    for game_id, kwargs in seeded:
        await _seed(db_session, store, game_id=game_id, **kwargs)
    # A selected-by-text row whose owner has objected is outside the selection too.
    await _seed(db_session, store, game_id=710_411, linked=False)
    await _link_profile(db_session, 710_411 + 1_000_000, objected=True)
    before = {
        c: _snapshot(await _row(db_session, c))
        for c in (await db_session.scalars(select(ReplayCapture.id))).all()
    }

    report = await _drain(
        session_factory, store=store, provider=_RecordingReplayProvider(), validator=_Validator()
    ).revalidate_quarantined(limit=10, dry_run=True)

    assert [o.game_id for o in report.outcomes] == [710_400]
    assert report.unselected_by_reason is not None
    assert dict(report.unselected_by_reason) == {
        "PanicException (no committed object)": 1,
        "PanicException (archival objected)": 1,
        "reclaim could not read back": 2,
        "reclaim checksum mismatch": 1,
        "wall-clock cap": 1,
        "MalformedArchiveError": 1,
        "no reason recorded": 1,
        "other": 2,  # free text, and an identifier that is not a class name (`OtherClass`)
        "ValueError": 1,
    }
    # Counts only: no object key and no free text from any reason reaches the report.
    rendered = repr(report.unselected_by_reason)
    assert "replays/" not in rendered
    assert "quoted" not in rendered
    assert await db_session.scalar(select(func.count()).select_from(Alert)) == 0
    assert {
        c: _snapshot(await _row(db_session, c))
        for c in (await db_session.scalars(select(ReplayCapture.id))).all()
    } == before


async def test_a_real_run_does_not_count_unselected_rows(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    store = _RecordingObjectStore()
    await _seed(db_session, store, game_id=710_420, last_error=_TIMEOUT_REASON)

    report = await _drain(
        session_factory, store=store, provider=_RecordingReplayProvider(), validator=_Validator()
    ).revalidate_quarantined(limit=10)

    assert report.unselected_by_reason is None


# === T673b: remediation of #129's second review ================================================
#
# Each test names its level: the selection query, a guarded write (the stored write or the
# quarantine write, which are separate statements with separate guards), or the report.


async def _object_to_archival(
    session_factory: async_sessionmaker[AsyncSession], profile_id: int
) -> None:
    """The profile's active owner records an Art. 21 objection (`users.archival_objected_at`)."""
    async with session_factory() as session:
        await session.execute(
            update(User)
            .where(
                User.id.in_(
                    select(ProfileLink.user_id).where(
                        ProfileLink.profile_id == profile_id, ProfileLink.unlinked_at.is_(None)
                    )
                )
            )
            .values(archival_objected_at=datetime.now(UTC))
        )
        await session.commit()


async def _unlink(session_factory: async_sessionmaker[AsyncSession], profile_id: int) -> None:
    """The profile's active owner unlinks it (`profile_links.unlinked_at`)."""
    async with session_factory() as session:
        await session.execute(
            update(ProfileLink)
            .where(ProfileLink.profile_id == profile_id, ProfileLink.unlinked_at.is_(None))
            .values(unlinked_at=datetime.now(UTC))
        )
        await session.commit()


class _ChangesOwnershipDuringValidation(_Validator):
    """While the bytes of one chosen row are being validated, that row's owner objects (or
    unlinks); every other row validates untouched. `fails` makes every validation end in an
    engine verdict instead of a result."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        victim_bytes: bytes,
        victim_profile_id: int,
        event: str,
        fails: bool,
    ) -> None:
        super().__init__()
        self._session_factory = session_factory
        self._victim_bytes = victim_bytes
        self._victim_profile_id = victim_profile_id
        self._event = event
        self._fails = fails

    def validate(self, zip_bytes: bytes) -> ReplayValidationResult:
        import asyncio

        self.calls += 1
        if zip_bytes == self._victim_bytes:
            # The barrier runs this in a worker thread, so a private loop is safe here.
            change = _object_to_archival if self._event == "objects" else _unlink
            asyncio.run(change(self._session_factory, self._victim_profile_id))
        if self._fails:
            raise EngineParseError("aoe2rec-py rejected the replay: still bad")
        return ReplayValidationResult(
            inner_filename="AgeIIDE_Replay_1.aoe2record",
            inner_bytes=4242,
            engine_name="aoe2rec-py",
            engine_version=_ENGINE_VERSION,
        )


_VICTIM = b"recording-of-the-user-who-changes-their-mind"
_BYSTANDER = b"recording-of-a-user-who-does-not"


@pytest.mark.parametrize("event", ["objects", "unlinks"])
@pytest.mark.parametrize("fails", [False, True], ids=["stored-write", "quarantine-write"])
async def test_a_user_who_objects_or_unlinks_during_validation_is_not_written_but_the_page_goes_on(
    event: str,
    fails: bool,
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Level: the guarded write, both statements. `fails=False` drives the stored write (the
    validation succeeds), `fails=True` the quarantine write (it ends in an engine verdict). The
    ownership was checked when the page was selected; it must hold again at the write. Contrast,
    on the same page: the row whose owner did not change is written."""
    store = _RecordingObjectStore()
    now = datetime.now(UTC)
    victim = await _seed(
        db_session,
        store,
        game_id=720_001,
        content=_VICTIM,
        stored_object=_VICTIM,
        completed_at=now - timedelta(days=9),
    )
    bystander = await _seed(
        db_session,
        store,
        game_id=720_002,
        content=_BYSTANDER,
        stored_object=_BYSTANDER,
        completed_at=now - timedelta(days=8),
    )
    victim_before = _snapshot(await _row(db_session, victim))
    validator = _ChangesOwnershipDuringValidation(
        session_factory,
        victim_bytes=_VICTIM,
        victim_profile_id=720_001 + 1_000_000,
        event=event,
        fails=fails,
    )

    report = await _drain(
        session_factory, store=store, provider=_RecordingReplayProvider(), validator=validator
    ).revalidate_quarantined(limit=10)

    assert validator.calls == 2
    # The refused row is an outcome of its own, and nothing about it was written.
    assert {o.capture_id: o.outcome for o in report.outcomes} == {
        victim: "ownership_changed",
        bystander: "still_quarantined" if fails else "stored",
    }
    assert _snapshot(await _row(db_session, victim)) == victim_before
    written = await _row(db_session, bystander)
    assert written.status == (CaptureStatus.QUARANTINED if fails else CaptureStatus.STORED)
    if fails:
        assert written.last_error == "EngineParseError: aoe2rec-py rejected the replay: still bad"
    else:
        assert written.validated_by == f"aoe2rec-py@{_ENGINE_VERSION}"


async def test_a_profile_with_no_active_link_is_counted_under_its_own_label_and_not_selected(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Level: the selection and the dry run's report. A profile nobody holds is not taken (the
    row and its object stay as they are); the dry run counts it under its own label, apart from
    an objector's. Contrast: an engine-failure row with a consenting owner is selected."""
    store = _RecordingObjectStore()
    now = datetime.now(UTC)
    await _seed(db_session, store, game_id=720_100, completed_at=now - timedelta(days=9))
    orphan = await _seed(
        db_session, store, game_id=720_101, linked=False, completed_at=now - timedelta(days=8)
    )
    left = await _seed(
        db_session, store, game_id=720_102, linked=False, completed_at=now - timedelta(days=7)
    )
    await _link_profile(db_session, 720_102 + 1_000_000, objected=True, unlinked=True)
    objector = await _seed(
        db_session, store, game_id=720_103, linked=False, completed_at=now - timedelta(days=6)
    )
    await _link_profile(db_session, 720_103 + 1_000_000, objected=True)
    before = {c: _snapshot(await _row(db_session, c)) for c in (orphan, left, objector)}

    report = await _drain(
        session_factory, store=store, provider=_RecordingReplayProvider(), validator=_Validator()
    ).revalidate_quarantined(limit=10, dry_run=True)

    assert [o.game_id for o in report.outcomes] == [720_100]
    assert report.unselected_by_reason is not None
    assert dict(report.unselected_by_reason) == {
        "PanicException (no active link)": 2,
        "PanicException (archival objected)": 1,
    }
    assert {c: _snapshot(await _row(db_session, c)) for c in before} == before
    assert store.gets == []


async def test_a_row_whose_object_key_is_set_but_checksum_is_null_is_not_selected(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Level: the selection's checksum clause on its own (the earlier test nulls both columns, so
    dropping this clause alone passed). Contrast: the same row with its checksum is selected."""
    store = _RecordingObjectStore()
    now = datetime.now(UTC)
    no_checksum = await _seed(
        db_session, store, game_id=720_200, sha256_null=True, completed_at=now - timedelta(days=9)
    )
    with_checksum = await _seed(
        db_session, store, game_id=720_201, completed_at=now - timedelta(days=8)
    )
    before = _snapshot(await _row(db_session, no_checksum))

    report = await _drain(
        session_factory, store=store, provider=_RecordingReplayProvider(), validator=_Validator()
    ).revalidate_quarantined(limit=10)

    assert [o.capture_id for o in report.outcomes] == [with_checksum]
    assert _snapshot(await _row(db_session, no_checksum)) == before


# --- A database error on one row's write (level: the report) ---------------------------------


@pytest.mark.parametrize("fails", [False, True], ids=["stored-write", "quarantine-write"])
async def test_a_write_that_fails_on_the_nth_row_stops_there_and_returns_the_report_so_far(
    fails: bool,
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Level: the report. Rows written before the failure are no longer selected, so a report
    discarded with the exception would lose their count for good. The run stops at the failing
    row, names the error's class (never its text), and the rows after it are not examined."""
    from sqlalchemy.exc import OperationalError

    from aoe2stats_ingester.capture import CaptureDrain

    store = _RecordingObjectStore()
    now = datetime.now(UTC)
    ids = [
        await _seed(
            db_session,
            store,
            game_id=720_300 + n,
            content=_GOOD if not fails else _BAD,
            stored_object=_GOOD if not fails else _BAD,
            completed_at=now - timedelta(days=9 - n),
        )
        for n in range(4)
    ]
    method = "_mark_quarantined" if fails else "_mark_stored"
    real = getattr(CaptureDrain, method)
    calls = {"n": 0}

    async def _third_write_fails(self: Any, *args: Any, **kwargs: Any) -> bool:
        calls["n"] += 1
        if calls["n"] == 3:
            raise OperationalError("UPDATE secret_table SET x = 'secret-value'", {}, Exception("x"))
        return await real(self, *args, **kwargs)  # type: ignore[no-any-return]

    monkeypatch.setattr(CaptureDrain, method, _third_write_fails)
    before_failed = _snapshot(await _row(db_session, ids[2]))
    before_after = _snapshot(await _row(db_session, ids[3]))
    validator = _Validator()

    report = await _drain(
        session_factory, store=store, provider=_RecordingReplayProvider(), validator=validator
    ).revalidate_quarantined(limit=10)

    written = "still_quarantined" if fails else "stored"
    assert [(o.capture_id, o.outcome) for o in report.outcomes] == [
        (ids[0], written),
        (ids[1], written),
    ]
    assert report.write_failed_by == "OperationalError"
    assert report.aborted_by is None
    assert "secret" not in repr(report)
    assert report.cursor is not None and report.cursor[1] == ids[1]
    assert validator.calls == 3  # the fourth row was never examined
    assert _snapshot(await _row(db_session, ids[2])) == before_failed
    assert _snapshot(await _row(db_session, ids[3])) == before_after
    # The first two were written for real; the count of them is what the report preserves.
    if not fails:
        assert (await _row(db_session, ids[0])).status == CaptureStatus.STORED
        assert (await _row(db_session, ids[1])).status == CaptureStatus.STORED


# --- Reason labels (level: the dry run's grouping) -------------------------------------------


@pytest.mark.parametrize(
    ("head", "label"),
    [
        pytest.param("ValueError: x", "ValueError", id="class-ending-in-Error-keeps-its-label"),
        pytest.param("pyo3_runtime.PanicException: x", "pyo3_runtime.PanicException", id="dotted"),
        pytest.param("SomethingException", "SomethingException", id="bare-class-name"),
        pytest.param("SecretProject12345: x", "other", id="identifier-not-a-class-name"),
        pytest.param("hunter2", "other", id="bare-identifier"),
        pytest.param("OtherClass: some text", "other", id="class-like-without-the-suffix"),
        pytest.param("Error handling: x", "other", id="not-an-identifier"),
    ],
)
def test_a_reason_label_is_a_closed_vocabulary(head: str, label: str) -> None:
    from aoe2stats_ingester.capture import _reason_class

    assert _reason_class(head, has_object=True, objecting=False, archiving=True) == label
