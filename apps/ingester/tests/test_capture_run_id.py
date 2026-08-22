"""Integration test for T059c: the alerts `CaptureDrain` raises during a real `run_once` cycle
must carry that cycle's own `ingest_run_id`, not `None`.

T059 opens the `ingest_runs` row before any stage runs specifically because "every `alerts` row
carries `ingest_run_id`, and four of the five producers fire during the drain ... or immediately
after it: a row that did not exist yet would leave them orphaned" (`run.py`'s own module
docstring). Three of those four producers live in `capture.py` — `rate_limited`
(`drain_with_rate_limit_guard`), `validation_failed` (`_quarantine`) and `expired_capture`
(`_classify_not_found`) — and, before T059c, every one of them wrote `ingest_run_id=None`
regardless: `Stage.__call__` took only a `Budget`, and `CaptureDrain`'s constructor had no run-id
parameter, so the row T059 opened specifically to avoid orphaning these alerts orphaned them
anyway.

This file exercises `CaptureDrain` the same way production actually runs it — as a `Stage` handed
to `run_once`, never called directly — so it is `run_once`'s own binding of the run id onto the
stage (`RunScoped.bind_run`, `run.py`) that is under test, not `CaptureDrain`'s internal
classification logic, which `test_quarantine.py` and `test_failure_classification.py` already
cover in isolation.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_core.replay.validation import MalformedArchiveError, ReplayValidationResult
from aoe2stats_providers.base import NotFound, ReplayBlob
from aoe2stats_storage.models import (
    Alert,
    AlertKind,
    AoeProfile,
    CaptureSource,
    CaptureStatus,
    IngestRun,
    Match,
    ReplayCapture,
)
from aoe2stats_storage.objects import ObjectStore, ObjectStoreConfig

_GRACE_HOURS = 72


class _FakeReplayProvider:
    """One scripted `ReplayBlob`/`NotFound` per `(game_id, profile_id)`, in the same shape
    `test_quarantine.py`'s `_FakeReplayProvider` and `test_failure_classification.py`'s
    `ScriptedReplayProvider` already use — kept local rather than imported from either, since
    neither module exports it for reuse (both name it as their own test-local fixture).
    """

    def __init__(self, responses: dict[tuple[int, int], ReplayBlob | NotFound]) -> None:
        self._responses = responses
        self.calls: list[tuple[int, int]] = []

    async def fetch_replay(self, game_id: int, profile_id: int) -> ReplayBlob | NotFound:
        key = (game_id, profile_id)
        self.calls.append(key)
        return self._responses[key]


class _FakeS3Client:
    """The same structural `S3Client` fake `test_quarantine.py` uses, kept local for the same
    reason as `_FakeReplayProvider` above."""

    def __init__(self) -> None:
        self.puts: dict[str, bytes] = {}

    def put_object(self, **kwargs: Any) -> Any:
        self.puts[kwargs["Key"]] = kwargs["Body"]
        return {}

    def delete_object(self, **kwargs: Any) -> Any:
        self.puts.pop(kwargs["Key"], None)
        return {}

    def generate_presigned_url(self, client_method: str, **kwargs: Any) -> Any:
        return f"https://fake-object-store.example/{kwargs['Params']['Key']}?signed=1"

    def get_paginator(self, operation_name: str) -> Any:
        raise NotImplementedError("not exercised by this test")


def _object_store() -> ObjectStore:
    return ObjectStore(
        ObjectStoreConfig(
            endpoint_url="https://fake-object-store.example",
            bucket="aoe2-replays-test",
            access_key_id="test",
            secret_access_key="test",
            region="eu",
        ),
        client=_FakeS3Client(),
    )


class _MalformedValidator:
    """Rejects every archive as not well-formed, exactly like `test_quarantine.py`'s own fixture
    of the same name — the outcome this test needs is `quarantined`, never the exact rejection
    reason.
    """

    def validate(self, zip_bytes: bytes) -> ReplayValidationResult:
        raise MalformedArchiveError("not a zip: missing local file header")


async def _seed_capture(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    game_id: int,
    profile_id: int,
    completed_at: datetime,
    capture_deadline_at: datetime | None = None,
) -> uuid.UUID:
    capture_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(AoeProfile(profile_id=profile_id, alias=f"player-{profile_id}", country="FR"))
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
                profile_id=profile_id,
                status=CaptureStatus.PENDING,
                capture_deadline_at=capture_deadline_at or completed_at + timedelta(days=21),
                source=CaptureSource.AUTOMATIC,
            )
        )
        await session.commit()
    return capture_id


async def _alerts_of_kind(
    session_factory: async_sessionmaker[AsyncSession], kind: AlertKind
) -> list[Alert]:
    async with session_factory() as session:
        result = await session.execute(select(Alert).where(Alert.kind == kind))
        return list(result.scalars().all())


async def _newest_ingest_run(session_factory: async_sessionmaker[AsyncSession]) -> IngestRun:
    async with session_factory() as session:
        result = await session.execute(select(IngestRun).order_by(IngestRun.started_at.desc()))
        row = result.scalars().first()
    assert row is not None, "run_once must have opened an ingest_runs row"
    return row


async def test_quarantine_during_a_real_run_carries_that_runs_ingest_run_id(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    from aoe2stats_ingester.capture import CaptureDrain
    from aoe2stats_ingester.run import run_once

    game_id, profile_id = 950_101, 296_101
    await _seed_capture(
        session_factory,
        game_id=game_id,
        profile_id=profile_id,
        completed_at=datetime.now(UTC) - timedelta(hours=3),
    )

    blob = ReplayBlob(
        content=b"not a well-formed replay archive at all",
        filename="AgeIIDE_Replay_950101.aoe2record",
        content_type="application/zip",
    )
    drain = CaptureDrain(
        session_factory=session_factory,
        replay_provider=_FakeReplayProvider({(game_id, profile_id): blob}),
        object_store=_object_store(),
        validator=_MalformedValidator(),
        validation_timeout_seconds=5.0,
    )

    report = await run_once(30, trigger="test", stages=(drain,), session_factory=session_factory)

    alerts = await _alerts_of_kind(session_factory, AlertKind.VALIDATION_FAILED)
    assert len(alerts) == 1
    assert alerts[0].ingest_run_id == report.ingest_run_id, (
        "a `validation_failed` alert raised by the drain during a real run_once cycle must carry "
        "that cycle's own ingest_run_id (T059c) — not None, which orphans it in exactly the "
        "column ingest_runs was opened early to prevent"
    )

    ingest_run = await _newest_ingest_run(session_factory)
    assert alerts[0].ingest_run_id == ingest_run.id


async def test_expired_capture_during_a_real_run_carries_that_runs_ingest_run_id(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    from aoe2stats_ingester.capture import CaptureDrain
    from aoe2stats_ingester.run import run_once

    game_id, profile_id = 950_102, 296_102
    completed_at = datetime.now(UTC) - timedelta(days=40)
    await _seed_capture(
        session_factory,
        game_id=game_id,
        profile_id=profile_id,
        completed_at=completed_at,
    )

    drain = CaptureDrain(
        session_factory=session_factory,
        replay_provider=_FakeReplayProvider({(game_id, profile_id): NotFound()}),
        replay_publication_grace_hours=_GRACE_HOURS,
    )

    report = await run_once(30, trigger="test", stages=(drain,), session_factory=session_factory)

    alerts = await _alerts_of_kind(session_factory, AlertKind.EXPIRED_CAPTURE)
    assert len(alerts) == 1
    assert alerts[0].ingest_run_id == report.ingest_run_id, (
        "an `expired_capture` alert raised by the drain during a real run_once cycle must carry "
        "that cycle's own ingest_run_id (T059c), the same fix as the quarantine case above"
    )

    ingest_run = await _newest_ingest_run(session_factory)
    assert alerts[0].ingest_run_id == ingest_run.id


async def test_a_capture_drain_never_bound_to_a_run_still_writes_none_exactly_as_before(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Every already-landed test file (`test_quarantine.py`, `test_failure_classification.py`, ...)
    constructs `CaptureDrain` directly and calls it without ever going through `run_once` — T059c
    must not change what those callers get. `bind_run` is never called here, on purpose.
    """
    from aoe2stats_ingester.budget import Budget
    from aoe2stats_ingester.capture import CaptureDrain

    game_id, profile_id = 950_103, 296_103
    completed_at = datetime.now(UTC) - timedelta(days=40)
    await _seed_capture(
        session_factory,
        game_id=game_id,
        profile_id=profile_id,
        completed_at=completed_at,
    )

    drain = CaptureDrain(
        session_factory=session_factory,
        replay_provider=_FakeReplayProvider({(game_id, profile_id): NotFound()}),
        replay_publication_grace_hours=_GRACE_HOURS,
    )

    await drain(Budget(seconds=30))

    alerts = await _alerts_of_kind(session_factory, AlertKind.EXPIRED_CAPTURE)
    assert len(alerts) == 1
    assert alerts[0].ingest_run_id is None, (
        "a CaptureDrain never bound to a run (called directly, never through run_once) must keep "
        "writing ingest_run_id=None exactly as it did before T059c"
    )
