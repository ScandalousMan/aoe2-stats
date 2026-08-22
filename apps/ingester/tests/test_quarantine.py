"""Integration test for T047a — the quarantine path and T055's containment barrier.

`aoe2stats_ingester.capture` does not exist yet: `capture.py` is T055's task, listed as
`[ ]` in tasks.md at the time this file is written. Every test below is therefore
`@pytest.mark.xfail(strict=True, reason="T055 not implemented yet")`, per CLAUDE.md's
"Test-first tasks and the green-tree gate" — the import of the not-yet-existent module lives
*inside* each test body rather than at module scope, so a `ModuleNotFoundError` is an ordinary
assertion failure `xfail` expects rather than a collection error that would take the whole
workspace suite down (the same convention `packages/providers/tests/test_aoems.py` documents for
T039). `strict=True` is what turns the run red the moment T055 lands and a test starts passing,
which is what forces the marker off instead of letting it hide a regression.

Three things FR-026, constitution IV and constitution V ask for, all exercised here against the
real database (T015/T015a) and fakes for the object store, the replay provider and the validation
engine:

1. **The write ordering never discards a blob.** A downloaded replay that fails well-formedness
   validation is still uploaded to the object store *before* validation ever runs (data-model.md,
   T055's own task text) — after ~31 days the source holds no replacement, so an unparsable
   capture is evidence, not garbage (constitution IV). The row ends `quarantined` with
   `last_error` set, and — because `quarantined` is its own state, distinct from both `stored` and
   `expired` (data-model.md's state table) — the capture counts in neither `stored_total` nor
   `expired_total`.
2. **The containment barrier (constitution V) catches everything, not just ordinary exceptions.**
   `aoe2rec-py`'s PyO3 bridge can raise `pyo3_runtime.PanicException`, which inherits
   `BaseException` directly and not `Exception` (`packages/core/src/aoe2stats_core/replay/
   validation.py`'s own docstring) — a bare `except Exception` would let it through and take the
   whole run down with it. The fake validator below raises a bespoke `BaseException` subclass to
   prove the barrier is not merely catching what `ReplayValidator.validate` is documented to raise.
3. **The barrier enforces a wall-clock cap, not cooperative cancellation.** A native call that
   hangs cannot be asked nicely to stop; the barrier's timeout is what has to win the race. The
   fake validator below blocks for far longer than the configured cap, and the test asserts the
   drain call returns well before the hang would have finished on its own.
4. **The one exception the barrier must not contain (T055a).** `asyncio.CancelledError` inherits
   `BaseException` directly too, exactly like a native panic — but folding a cancelled *task* into
   `quarantined` terminally writes off a replay whose bytes are already durable to nothing more
   than a server restart (`apps/api/src/aoe2stats_api/routers/cron.py` runs `run_once` inside an
   ordinary request). `test_cancelling_the_run_mid_validation_leaves_the_capture_downloading_
   not_quarantined` below asserts the opposite of every scenario above: the row stays
   `downloading` with its `object_key` intact, no `validation_failed` alert is raised, and the
   `CancelledError` propagates out of the drain call rather than being swallowed.

In every case but the fourth, "the run completes rather than failing" is the point:
`CaptureDrain.__call__` itself must never raise, whatever the engine underneath it does. The
fourth is the deliberate exception to that rule — see this module's own containment paragraph and
`capture.py`'s module and `_validate_with_barrier` docstrings for why.

## The contract this test defines for T055

`capture.py` does not exist, so this file is also where the interface T055 must satisfy is
written down, the same way a test-first task always is in this workflow:

- `CaptureDrain(*, session_factory, object_store, replay_provider, validator, alert_sink,
  validation_timeout_seconds)` — a `Stage` (`aoe2stats_ingester.run.Stage`): an object whose
  `async def __call__(self, budget: Budget) -> Mapping[str, Any]` claims pending `replay_captures`
  rows and drains them. `alert_sink` exists because T055's own task text requires a quarantine to
  raise a severity-2 `validation_failed` alert through `raise_alert` (`packages/core/src/
  aoe2stats_core/alerting.py`) — this file does not assert on the alert itself (T055 owns it, this
  task does not name it), only supplies a sink so construction cannot fail for want of one.
- The returned mapping carries `ingest_runs`' own counter names — `stored_total`,
  `quarantined_total`, `expired_total`, and so on (data-model.md's `ingest_runs` section) — because
  T059 closes the `ingest_runs` row with "every counter" once discovery, reconciliation and drain
  have run; a stage report that already speaks that vocabulary is what lets T059 fold it in with
  no per-key translation, and it is also exactly the vocabulary T047a's own task text uses
  ("stored_total nor expired_total").
"""

from __future__ import annotations

import asyncio
import threading
import time
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_core.alerting import AlertRecord
from aoe2stats_core.replay.validation import MalformedArchiveError, ReplayValidationResult
from aoe2stats_ingester.budget import Budget
from aoe2stats_providers.base import ReplayBlob
from aoe2stats_storage.models import AoeProfile, CaptureSource, CaptureStatus, Match, ReplayCapture
from aoe2stats_storage.objects import ObjectStore, ObjectStoreConfig, replay_object_key

# --- Fakes -----------------------------------------------------------------------------------


class _FakeReplayProvider:
    """Stands in for `ReplayProvider.fetch_replay` (contracts/providers.md): always answers 200,
    never `NotFound` — the three-way 404 reading (T056) is not this test's concern. One blob per
    `game_id`, so a single drain call over several claimed captures can exercise several different
    validation failures in the same run without a validator that reads capture ids it is never
    given.
    """

    def __init__(self, blobs_by_game_id: dict[int, ReplayBlob]) -> None:
        self._blobs_by_game_id = blobs_by_game_id
        self.calls: list[tuple[int, int]] = []

    async def fetch_replay(self, game_id: int, profile_id: int) -> ReplayBlob:
        self.calls.append((game_id, profile_id))
        return self._blobs_by_game_id[game_id]


class _FakeS3Client:
    """Satisfies `aoe2stats_storage.objects.S3Client` structurally (that module's own Protocol,
    named exactly so a test can hand `ObjectStore` this much instead of a real `boto3` client).
    Records every `put_object` call so "the blob is still uploaded" and "the object is retrievable"
    can be asserted against the bytes actually held, not against a claim the row makes about
    itself.
    """

    def __init__(self) -> None:
        self.puts: dict[str, bytes] = {}

    def put_object(self, **kwargs: Any) -> Any:
        self.puts[kwargs["Key"]] = kwargs["Body"]
        return {}

    def delete_object(self, **kwargs: Any) -> Any:
        self.puts.pop(kwargs["Key"], None)
        return {}

    def generate_presigned_url(self, client_method: str, **kwargs: Any) -> Any:
        key = kwargs["Params"]["Key"]
        if key not in self.puts:
            raise AssertionError(f"signed a URL for {key!r}, which was never uploaded")
        return f"https://fake-object-store.example/{key}?signed=1"

    def get_paginator(self, operation_name: str) -> Any:
        raise NotImplementedError("not exercised by this test")


def _object_store(client: _FakeS3Client) -> ObjectStore:
    return ObjectStore(
        ObjectStoreConfig(
            endpoint_url="https://fake-object-store.example",
            bucket="aoe2-replays-test",
            access_key_id="test",
            secret_access_key="test",
            region="eu",
        ),
        client=client,
    )


class _FakeAlertSink:
    """Satisfies `AlertSink` (`packages/core/src/aoe2stats_core/alerting.py`) structurally, so
    `CaptureDrain` has somewhere to write the `validation_failed` alert T055's task text requires
    on every quarantine. Nothing in this file asserts on `records` — that alert belongs to T055,
    not to T047a's own assertions — this only has to exist so construction cannot fail.
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


class _MalformedValidator:
    """A `ReplayValidator` (`packages/core/.../validation.py`) that rejects every archive as not
    well-formed — an ordinary `Exception` subclass, the failure the Protocol itself documents."""

    def validate(self, zip_bytes: bytes) -> ReplayValidationResult:
        raise MalformedArchiveError("not a zip: missing local file header")


class _EnginePanic(BaseException):
    """Stands in for `pyo3_runtime.PanicException`. `validation.py`'s own docstring: a native
    engine that panics "inherits `BaseException` directly and not `Exception`" and is deliberately
    left unwrapped by the adapter — catching it is the containment barrier's job, and only its
    job. A bare `except Exception` in the barrier would let this one straight through.
    """


class _PanickingValidator:
    def validate(self, zip_bytes: bytes) -> ReplayValidationResult:
        raise _EnginePanic("simulated aoe2rec-py panic")


class _HangingValidator:
    """A `ReplayValidator` that blocks synchronously for `sleep_seconds`, standing in for a native
    call that has gotten stuck. Only a wall-clock cap — not cooperative cancellation, which a
    blocking native call cannot honour — can contain this, which is the whole point of the test
    that uses it.
    """

    def __init__(self, sleep_seconds: float) -> None:
        self._sleep_seconds = sleep_seconds

    def validate(self, zip_bytes: bytes) -> ReplayValidationResult:
        time.sleep(self._sleep_seconds)
        raise AssertionError("must never return: the wall-clock cap must win the race")


class _CancellableHangingValidator:
    """A `ReplayValidator` that blocks synchronously until told to stop, signalling
    `validate_started` the instant it begins — so a test can cancel the enclosing task only once
    validation is genuinely in flight inside `_validate_with_barrier`'s `asyncio.wait_for`, never
    before the barrier has even entered it.

    `validate_started` is a plain `threading.Event`, not `asyncio.Event`: `validate` runs in a
    worker thread (`asyncio.to_thread`, `_validate_with_barrier`), and only a threading primitive
    is safe to signal from there back to the event loop's own thread.
    """

    def __init__(self, validate_started: threading.Event, *, sleep_seconds: float) -> None:
        self._validate_started = validate_started
        self._sleep_seconds = sleep_seconds

    def validate(self, zip_bytes: bytes) -> ReplayValidationResult:
        self._validate_started.set()
        time.sleep(self._sleep_seconds)
        raise AssertionError("must never return: the test cancels the task before this")


class _MixedFailureValidator:
    """One engine standing in for three different real-world failure shapes at once, keyed by
    which blob it is handed (`validate` receives only bytes, never a capture id) — proving the
    barrier contains each independently within a single drain call, so one capture's failure mode
    never stops another's from being processed ("the run completes rather than failing").
    """

    def __init__(
        self, *, malformed: bytes, panic: bytes, hanging: bytes, hang_seconds: float
    ) -> None:
        self._malformed = malformed
        self._panic = panic
        self._hanging = hanging
        self._hang_seconds = hang_seconds

    def validate(self, zip_bytes: bytes) -> ReplayValidationResult:
        if zip_bytes == self._malformed:
            raise MalformedArchiveError("not a zip: missing local file header")
        if zip_bytes == self._panic:
            raise _EnginePanic("simulated aoe2rec-py panic")
        if zip_bytes == self._hanging:
            time.sleep(self._hang_seconds)
            raise AssertionError("must never return: the wall-clock cap must win the race")
        raise AssertionError(f"unexpected blob in this test: {zip_bytes!r}")


# --- Seeding -----------------------------------------------------------------------------------


async def _seed_pending_capture(
    db_session: AsyncSession,
    *,
    game_id: int,
    profile_id: int,
    completed_at: datetime | None = None,
) -> uuid.UUID:
    """Insert the `matches` / `aoe_profiles` / `replay_captures` rows a claimable, `pending`
    capture needs, and commit.

    The commit matters: `CaptureDrain` claims through its own session, opened from
    `session_factory`, and Postgres never shows one open transaction's uncommitted writes to
    another connection — `apps/api/tests/test_backfill_request.py` relies on the identical rule
    for the same reason.
    """
    completed_at = completed_at or (datetime.now(UTC) - timedelta(hours=3))
    db_session.add(AoeProfile(profile_id=profile_id, alias=f"player-{profile_id}", country="FR"))
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
            status=CaptureStatus.PENDING,
            capture_deadline_at=completed_at + timedelta(days=21),
            source=CaptureSource.AUTOMATIC,
        )
    )
    await db_session.commit()
    return capture_id


async def _reload_capture(db_session: AsyncSession, capture_id: uuid.UUID) -> ReplayCapture:
    """Force a fresh read from the database — `CaptureDrain` commits through a different session,
    and `expire_on_commit=False` (`repositories/base.py`) means the identity map otherwise keeps
    serving the row exactly as `db_session` last saw it, before the drain ever ran.
    """
    db_session.expire_all()
    capture = await db_session.get(ReplayCapture, capture_id)
    assert capture is not None
    return capture


# --- Tests -------------------------------------------------------------------------------------


async def test_malformed_replay_is_uploaded_before_validation_and_quarantined_with_last_error(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from aoe2stats_ingester.capture import CaptureDrain

    game_id, profile_id = 900_101, 196_101
    capture_id = await _seed_pending_capture(db_session, game_id=game_id, profile_id=profile_id)

    blob_content = b"this is not a well-formed replay archive at all"
    blob = ReplayBlob(
        content=blob_content,
        filename="AgeIIDE_Replay_900101.aoe2record",
        content_type="application/zip",
    )
    replay_provider = _FakeReplayProvider({game_id: blob})
    fake_client = _FakeS3Client()
    object_store = _object_store(fake_client)

    drain = CaptureDrain(
        session_factory=session_factory,
        object_store=object_store,
        replay_provider=replay_provider,
        validator=_MalformedValidator(),
        alert_sink=_FakeAlertSink(),
        validation_timeout_seconds=5.0,
    )

    report = await drain(Budget(seconds=30))

    expected_key = replay_object_key(game_id, profile_id)
    assert fake_client.puts.get(expected_key) == blob_content, (
        "FR-026: a validation failure must never discard the blob — it is uploaded before "
        "validation ever runs, so the object must exist under its normal key regardless of the "
        "outcome"
    )
    signed_url = await object_store.signed_get_url(expected_key)
    assert expected_key in signed_url, "the object must be retrievable, not merely written"

    capture = await _reload_capture(db_session, capture_id)
    assert capture.status == CaptureStatus.QUARANTINED
    assert capture.last_error, "the reason validation failed must be recorded, never dropped"
    assert capture.object_key == expected_key
    assert capture.zip_sha256 is not None, (
        "checksum and object_key are committed before validation runs (T055's write ordering), "
        "and a quarantine never rolls that back"
    )

    assert report["stored_total"] == 0, (
        "a quarantined capture counts in neither total (data-model.md's state table: quarantined "
        "is its own state, distinct from stored and from expired)"
    )
    assert report["expired_total"] == 0
    assert report["quarantined_total"] == 1


async def test_engine_raising_a_base_exception_is_contained_and_quarantines_the_capture(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from aoe2stats_ingester.capture import CaptureDrain

    game_id, profile_id = 900_102, 196_102
    capture_id = await _seed_pending_capture(db_session, game_id=game_id, profile_id=profile_id)

    blob = ReplayBlob(
        content=b"irrelevant bytes: the fake engine panics regardless of content",
        filename="AgeIIDE_Replay_900102.aoe2record",
        content_type="application/zip",
    )
    replay_provider = _FakeReplayProvider({game_id: blob})

    drain = CaptureDrain(
        session_factory=session_factory,
        object_store=_object_store(_FakeS3Client()),
        replay_provider=replay_provider,
        validator=_PanickingValidator(),
        alert_sink=_FakeAlertSink(),
        validation_timeout_seconds=5.0,
    )

    # The call itself must not raise: constitution V — "a parser crash affects neither the API nor
    # the ingester" — and T055's own text, "no exception leaves this module".
    report = await drain(Budget(seconds=30))

    capture = await _reload_capture(db_session, capture_id)
    assert capture.status == CaptureStatus.QUARANTINED
    assert capture.last_error, "a raw engine panic must still leave a diagnosable reason behind"
    assert report["stored_total"] == 0
    assert report["expired_total"] == 0
    assert report["quarantined_total"] == 1


async def test_engine_hanging_past_the_wall_clock_cap_is_contained_and_quarantines_the_capture(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from aoe2stats_ingester.capture import CaptureDrain

    game_id, profile_id = 900_103, 196_103
    capture_id = await _seed_pending_capture(db_session, game_id=game_id, profile_id=profile_id)

    blob = ReplayBlob(
        content=b"irrelevant bytes: the fake engine hangs regardless of content",
        filename="AgeIIDE_Replay_900103.aoe2record",
        content_type="application/zip",
    )
    replay_provider = _FakeReplayProvider({game_id: blob})

    # The cap is two orders of magnitude below the hang, so a barrier that actually enforces it
    # returns quickly; one that merely calls the engine and waits would take the full 2 seconds.
    timeout_seconds = 0.1
    hang_seconds = 2.0

    drain = CaptureDrain(
        session_factory=session_factory,
        object_store=_object_store(_FakeS3Client()),
        replay_provider=replay_provider,
        validator=_HangingValidator(sleep_seconds=hang_seconds),
        alert_sink=_FakeAlertSink(),
        validation_timeout_seconds=timeout_seconds,
    )

    started = time.monotonic()
    report = await drain(Budget(seconds=30))
    elapsed = time.monotonic() - started

    assert elapsed < hang_seconds, (
        f"the drain call took {elapsed:.3f}s against a {hang_seconds}s hang and a "
        f"{timeout_seconds}s cap: the wall-clock cap did not win the race, which means the "
        "barrier waited for the engine instead of containing it"
    )

    capture = await _reload_capture(db_session, capture_id)
    assert capture.status == CaptureStatus.QUARANTINED
    assert capture.last_error, "a timed-out validation must still leave a diagnosable reason behind"
    assert report["stored_total"] == 0
    assert report["expired_total"] == 0
    assert report["quarantined_total"] == 1


async def test_run_completes_when_every_capture_in_the_batch_fails_validation_differently(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The containment barrier isolates one capture's failure from the next: a malformed archive,
    a raw engine panic and a hung engine call, claimed and drained in the same run, all end
    `quarantined` — none of them aborts the run for the others ("the run completes rather than
    failing" is a property of the whole batch, not only of the last item processed).
    """
    from aoe2stats_ingester.capture import CaptureDrain

    malformed_ids = (900_201, 196_201)
    panic_ids = (900_202, 196_202)
    hanging_ids = (900_203, 196_203)

    malformed_capture_id = await _seed_pending_capture(
        db_session, game_id=malformed_ids[0], profile_id=malformed_ids[1]
    )
    panic_capture_id = await _seed_pending_capture(
        db_session, game_id=panic_ids[0], profile_id=panic_ids[1]
    )
    hanging_capture_id = await _seed_pending_capture(
        db_session, game_id=hanging_ids[0], profile_id=hanging_ids[1]
    )

    malformed_bytes = b"malformed-archive"
    panic_bytes = b"panics-on-validate"
    hanging_bytes = b"hangs-on-validate"
    hang_seconds = 2.0

    replay_provider = _FakeReplayProvider(
        {
            malformed_ids[0]: ReplayBlob(
                content=malformed_bytes,
                filename="AgeIIDE_Replay_900201.aoe2record",
                content_type="application/zip",
            ),
            panic_ids[0]: ReplayBlob(
                content=panic_bytes,
                filename="AgeIIDE_Replay_900202.aoe2record",
                content_type="application/zip",
            ),
            hanging_ids[0]: ReplayBlob(
                content=hanging_bytes,
                filename="AgeIIDE_Replay_900203.aoe2record",
                content_type="application/zip",
            ),
        }
    )

    drain = CaptureDrain(
        session_factory=session_factory,
        object_store=_object_store(_FakeS3Client()),
        replay_provider=replay_provider,
        validator=_MixedFailureValidator(
            malformed=malformed_bytes,
            panic=panic_bytes,
            hanging=hanging_bytes,
            hang_seconds=hang_seconds,
        ),
        alert_sink=_FakeAlertSink(),
        validation_timeout_seconds=0.1,
    )

    started = time.monotonic()
    report = await drain(Budget(seconds=30))
    elapsed = time.monotonic() - started

    assert elapsed < hang_seconds, (
        "the batch as a whole must not wait out the hang either: the cap applies per capture"
    )

    for capture_id in (malformed_capture_id, panic_capture_id, hanging_capture_id):
        capture = await _reload_capture(db_session, capture_id)
        assert capture.status == CaptureStatus.QUARANTINED, (
            f"capture {capture_id} did not reach quarantined — one failure mode in the batch "
            "must not prevent the others from being processed and classified"
        )
        assert capture.last_error

    assert report["stored_total"] == 0
    assert report["expired_total"] == 0
    assert report["quarantined_total"] == 3


async def test_cancelling_the_run_mid_validation_leaves_the_capture_downloading_not_quarantined(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """T055a: `asyncio.CancelledError` inherits `BaseException` directly, exactly as
    `pyo3_runtime.PanicException` does (the previous three tests), so a barrier that merely
    catches `BaseException` folds a *cancelled task* into the same `quarantined` outcome as a
    genuine engine panic. It must not: the blob is already durably committed
    (`_commit_blob_metadata`, `capture.py`'s own write-ordering paragraph) while the row is still
    `downloading` by the time validation ever starts, so a graceful shutdown or a restart
    cancelling mid-validation must leave the row exactly there — for the next cycle's reclaim to
    resume at validation — never terminally write off a replay whose bytes are already safe.

    The task running `drain(...)` is cancelled only once `validate()` has actually started (the
    `threading.Event` handshake below), so this exercises cancellation genuinely arriving inside
    `_validate_with_barrier`'s `asyncio.wait_for`, not before the barrier is ever entered.
    """
    from aoe2stats_ingester.capture import CaptureDrain

    game_id, profile_id = 900_104, 196_104
    capture_id = await _seed_pending_capture(db_session, game_id=game_id, profile_id=profile_id)

    blob_content = b"irrelevant bytes: cancellation happens before the engine ever finishes"
    blob = ReplayBlob(
        content=blob_content,
        filename="AgeIIDE_Replay_900104.aoe2record",
        content_type="application/zip",
    )
    replay_provider = _FakeReplayProvider({game_id: blob})
    fake_client = _FakeS3Client()
    object_store = _object_store(fake_client)
    alert_sink = _FakeAlertSink()

    # Long enough for the assertion below (elapsed well under it) to prove cancellation actually
    # short-circuited the wait rather than the engine simply finishing its own sleep first; short
    # enough that the abandoned thread (Python cannot kill a running thread — the module docstring
    # on the wall-clock cap says as much) does not stall the rest of the suite at interpreter exit.
    hang_seconds = 2.0
    validate_started = threading.Event()

    drain = CaptureDrain(
        session_factory=session_factory,
        object_store=object_store,
        replay_provider=replay_provider,
        validator=_CancellableHangingValidator(validate_started, sleep_seconds=hang_seconds),
        alert_sink=alert_sink,
        validation_timeout_seconds=30.0,
    )

    task = asyncio.ensure_future(drain(Budget(seconds=30)))
    # Cross-thread wait for the signal: `threading.Event.wait` blocks the calling thread, so it is
    # itself run off the event loop via `asyncio.to_thread` rather than stalling it.
    started_in_time = await asyncio.to_thread(validate_started.wait, hang_seconds)
    assert started_in_time, "validate() never started: nothing to cancel mid-validation"

    started_cancel_at = time.monotonic()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    elapsed = time.monotonic() - started_cancel_at

    assert elapsed < hang_seconds, (
        f"cancelling took {elapsed:.3f}s against a {hang_seconds}s engine sleep: cancellation "
        "must short-circuit the wait, not be masked behind the engine eventually finishing on "
        "its own"
    )

    expected_key = replay_object_key(game_id, profile_id)
    assert fake_client.puts.get(expected_key) == blob_content, (
        "the blob is durably committed before validation ever runs (write ordering); "
        "cancellation must not discard it"
    )

    capture = await _reload_capture(db_session, capture_id)
    assert capture.status == CaptureStatus.DOWNLOADING, (
        "a cancellation reaching the barrier mid-validation must leave the row exactly where the "
        "blob commit left it, not fold it into `quarantined` alongside a genuine engine panic "
        "(T055a)"
    )
    assert capture.object_key == expected_key
    assert capture.zip_sha256 is not None, (
        "the checksum committed before validation must survive the cancellation intact — this is "
        "what lets the next cycle's reclaim resume at validation instead of re-downloading"
    )

    assert alert_sink.records == [], (
        "cancellation is not a validation failure: no `validation_failed` alert must be raised"
    )
