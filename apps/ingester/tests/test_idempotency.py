"""Integration test for quickstart scenario 6 (T046): idempotency of the capture drain.

> Note the `stored_at` and `zip_sha256` of an archived capture. Run three more cycles. Expect no
> new rows, no changed `stored_at`, no rewritten object, no request to the replay endpoint for
> that match. (FR-018, SC-006)

**T055 (`apps/ingester/src/aoe2stats_ingester/capture.py`) does not exist yet.** Per this
project's test-first discipline (CLAUDE.md "Test-first tasks and the green-tree gate"), every test
below is marked `xfail(strict=True, reason="T055 not implemented yet")`: the import of
`aoe2stats_ingester.capture` happens inside the test body, so collection never fails, and the
marker is expected to be removed the moment T055 makes this pass for real.

**Assumed interface**, reconstructed from what already exists rather than invented from nothing:

- `aoe2stats_ingester.run.Stage` (T018, already implemented and tested by `test_run.py`) is
  `name: str` plus `async def __call__(self, budget: Budget) -> Mapping[str, Any]`; `run.py`'s own
  docstring names the three stages `"discover"`, `"reconcile"`, `"drain"` in that order, so the
  capture stage is assumed to be a class — `CaptureDrain` here — satisfying that Protocol with
  `name = "drain"`.
- Every dependency the drain needs to talk to the outside world is assumed to be constructor
  injection, exactly like every other component in this codebase (`ObjectStore`, the provider
  base classes, `raise_alert`'s `AlertSink`): `session_factory` (the same
  `async_sessionmaker[AsyncSession]` `packages/storage/src/aoe2stats_storage/repositories/base.py`
  builds), a `ReplayProvider` (contracts/providers.md), an object store exposing `put` (the async
  subset of `aoe2stats_storage.objects.ObjectStore`), a `ReplayValidator`
  (`aoe2stats_core.replay.validation`), an `AlertSink` (`aoe2stats_core.alerting`), and the two
  tuning knobs this scenario's timing depends on (`capture_budget_days`,
  `replay_publication_grace_hours` — `.env.example`'s `CAPTURE_BUDGET_DAYS` /
  `REPLAY_PUBLICATION_GRACE_HOURS`).

If T055 lands with a different shape, this file is the thing to update, not evidence that the
assumption was wrong to make: a test-first task has to commit to *something* to be a real test at
all, and only `run.Stage` and the fake below's own Protocol conformance are load-bearing — every
other name here is a best-effort guess this task's own reasoning has to write down somewhere.

Deliberately **not** a no-op-passes-trivially test: alongside the already-`stored` capture the
scenario is about, `_seed` also inserts one ordinary `pending` capture for a *different* match by
the same profile, answered with a 404 every cycle. That second capture is what proves the drain
actually walked its queue and did real work each of the three cycles — a `CaptureDrain` that did
nothing at all would make every assertion about the archived capture pass by accident, and the
pending capture's growing call count is what rules that out.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_providers.base import NotFound
from aoe2stats_storage.models import AoeProfile, CaptureSource, CaptureStatus, Match, ReplayCapture
from aoe2stats_storage.repositories.base import session_scope

_PROFILE_ID = 424242
_ARCHIVED_GAME_ID = 900_001
_PENDING_GAME_ID = 900_002
_CAPTURE_BUDGET_DAYS = 21
_REPLAY_PUBLICATION_GRACE_HOURS = 72
_CYCLES = 3


@dataclass(frozen=True, slots=True)
class _FetchCall:
    game_id: int
    profile_id: int


class _FakeReplayProvider:
    """Records every call it receives and always answers 404. This test never needs a
    successful download: the point is that the *archived* capture's match must never reach this
    provider at all (FR-018), while the *pending* control capture's repeated 404s prove the drain
    genuinely visited the queue on every cycle rather than short-circuiting to nothing.
    """

    def __init__(self) -> None:
        self.calls: list[_FetchCall] = []

    async def fetch_replay(self, game_id: int, profile_id: int) -> NotFound:
        self.calls.append(_FetchCall(game_id=game_id, profile_id=profile_id))
        return NotFound(http_status=404)

    def calls_for(self, game_id: int) -> list[_FetchCall]:
        return [call for call in self.calls if call.game_id == game_id]


class _FakeObjectStore:
    """Records every write. The archived capture must never see one: rewriting an object that is
    already `stored` is exactly what SC-006 forbids, and the pending capture's 404 never reaches a
    download either, so this must stay empty for the whole test.
    """

    def __init__(self) -> None:
        self.put_calls: list[tuple[str, bytes]] = []

    async def put(self, key: str, body: bytes, *, content_type: str = "application/zip") -> None:
        self.put_calls.append((key, body))


class _FakeReplayEngine:
    """A canary, not a validator. Nothing in this test's traffic (two 404s) is ever a downloaded
    blob, so validation must never run; if it does, something re-fetched or re-validated a replay
    idempotency forbids touching at all.
    """

    def validate(self, zip_bytes: bytes) -> Any:
        raise AssertionError(
            "the replay engine must never run in a scenario where every provider response is a "
            "404 for an already-stored or still-pending capture"
        )


class _FakeAlertSink:
    """Records every alert. Both captures here are far too recent to be past their capture
    deadline or their retention window, so nothing should ever be raised.
    """

    def __init__(self) -> None:
        self.written: list[Mapping[str, Any]] = []

    async def write(
        self,
        *,
        kind: str,
        severity: int,
        detail: Mapping[str, Any] | None,
        ingest_run_id: uuid.UUID | None,
    ) -> Mapping[str, Any]:
        record = {"kind": kind, "severity": severity, "detail": detail}
        self.written.append(record)
        return record

    async def unacknowledged_severity_one(self) -> Sequence[Mapping[str, Any]]:
        return []


@dataclass(frozen=True, slots=True)
class _Seeded:
    archived_capture_id: uuid.UUID
    pending_capture_id: uuid.UUID
    stored_at: datetime
    object_key: str
    zip_sha256: str
    zip_bytes: int


async def _seed(session_factory: async_sessionmaker[AsyncSession]) -> _Seeded:
    """One already-`stored` capture (the subject of scenario 6) and one ordinary `pending`
    capture for a different match by the same profile, well inside the publication grace so a 404
    against it leaves it `pending` on every cycle rather than flipping to `unavailable`.
    """
    now = datetime.now(UTC)
    zip_sha256 = hashlib.sha256(b"already archived replay bytes").hexdigest()
    zip_bytes = 2048
    object_key = f"replays/{_ARCHIVED_GAME_ID}/{_PROFILE_ID}.zip"
    stored_at = now - timedelta(days=1)
    archived_completed_at = now - timedelta(days=2)
    pending_completed_at = now - timedelta(hours=1)
    archived_capture_id = uuid.uuid4()
    pending_capture_id = uuid.uuid4()

    async with session_scope(session_factory) as session:
        session.add(AoeProfile(profile_id=_PROFILE_ID, alias="Idempotent Player"))
        session.add(
            Match(
                game_id=_ARCHIVED_GAME_ID,
                leaderboard_id=3,
                completed_at=archived_completed_at,
                duration_seconds=1800,
                source="relic",
                raw_payload={},
            )
        )
        session.add(
            Match(
                game_id=_PENDING_GAME_ID,
                leaderboard_id=3,
                completed_at=pending_completed_at,
                duration_seconds=1500,
                source="relic",
                raw_payload={},
            )
        )
        session.add(
            ReplayCapture(
                id=archived_capture_id,
                game_id=_ARCHIVED_GAME_ID,
                profile_id=_PROFILE_ID,
                status=CaptureStatus.STORED,
                capture_deadline_at=archived_completed_at + timedelta(days=_CAPTURE_BUDGET_DAYS),
                attempts=1,
                next_attempt_at=now,
                first_seen_at=archived_completed_at,
                stored_at=stored_at,
                object_key=object_key,
                zip_bytes=zip_bytes,
                zip_sha256=zip_sha256,
                inner_filename="MP Replay v101.101 @2026.08.20 120000 (1).aoe2record",
                inner_bytes=4096,
                source=CaptureSource.AUTOMATIC,
                validated_by="aoe2rec-py@0.1.0",
            )
        )
        session.add(
            ReplayCapture(
                id=pending_capture_id,
                game_id=_PENDING_GAME_ID,
                profile_id=_PROFILE_ID,
                status=CaptureStatus.PENDING,
                capture_deadline_at=pending_completed_at + timedelta(days=_CAPTURE_BUDGET_DAYS),
                attempts=0,
                next_attempt_at=now - timedelta(minutes=1),
                first_seen_at=pending_completed_at,
                source=CaptureSource.AUTOMATIC,
            )
        )

    return _Seeded(
        archived_capture_id=archived_capture_id,
        pending_capture_id=pending_capture_id,
        stored_at=stored_at,
        object_key=object_key,
        zip_sha256=zip_sha256,
        zip_bytes=zip_bytes,
    )


async def _replay_capture_count(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_scope(session_factory) as session:
        result = await session.execute(select(func.count()).select_from(ReplayCapture))
        return result.scalar_one()


async def _fetch_capture(
    session_factory: async_sessionmaker[AsyncSession], capture_id: uuid.UUID
) -> ReplayCapture:
    async with session_scope(session_factory) as session:
        capture = await session.get(ReplayCapture, capture_id)
        assert capture is not None
        session.expunge(capture)
        return capture


async def test_three_further_cycles_over_an_archived_capture_change_nothing(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
) -> None:
    from aoe2stats_ingester.capture import CaptureDrain
    from aoe2stats_ingester.run import run_once

    seeded = await _seed(session_factory)
    replay_provider = _FakeReplayProvider()
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

    initial_capture_count = await _replay_capture_count(session_factory)
    assert initial_capture_count == 2  # the archived capture and its pending control, nothing else

    for cycle in range(1, _CYCLES + 1):
        report = await run_once(60, trigger="cron", stages=[drain])
        assert drain.name in report.stages_completed

        # FR-018 / SC-006: no duplicate row, ever, for the already-archived match.
        assert await _replay_capture_count(session_factory) == initial_capture_count

        archived = await _fetch_capture(session_factory, seeded.archived_capture_id)
        assert archived.status == CaptureStatus.STORED
        assert archived.stored_at == seeded.stored_at
        assert archived.object_key == seeded.object_key
        assert archived.zip_sha256 == seeded.zip_sha256
        assert archived.zip_bytes == seeded.zip_bytes

        # No request to the replay endpoint for that match — on any of the three cycles.
        assert replay_provider.calls_for(_ARCHIVED_GAME_ID) == []

        # No object was ever written — the archived blob was never touched, and the control
        # capture's 404 never reaches a download in the first place.
        assert object_store.put_calls == []

        # Nothing here is old enough to raise anything.
        assert alert_sink.written == []

        # The control capture proves the drain actually ran its real logic against the queue on
        # *this* cycle, rather than the whole run doing nothing at all.
        assert len(replay_provider.calls_for(_PENDING_GAME_ID)) == cycle
        pending = await _fetch_capture(session_factory, seeded.pending_capture_id)
        assert pending.status == CaptureStatus.PENDING
        assert pending.stored_at is None
        assert pending.object_key is None

    # Across all three further cycles combined: the replay endpoint was asked about the pending
    # control match exactly three times, and about the archived match not once.
    assert len(replay_provider.calls_for(_PENDING_GAME_ID)) == _CYCLES
    assert replay_provider.calls_for(_ARCHIVED_GAME_ID) == []
