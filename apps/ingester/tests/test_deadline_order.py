"""Integration test for quickstart scenario 5 (T045): under budget pressure, the capture drain
must shed the replays we could still fetch tomorrow, never the ones expiring tonight.

Targets `aoe2stats_ingester.capture` (T055), which does not exist yet — the whole module import is
therefore inside the test body and the test itself is `xfail(strict=True)` until T055 lands.

**The contract this test commits to**, since neither `data-model.md` nor `tasks.md` names a class:
a `DrainStage` in `capture.py` satisfying `run.py`'s `Stage` protocol (`name` + `async def
__call__(self, budget) -> Mapping`), constructed from a `session_factory`, a `ReplayProvider`
(`contracts/providers.md`), an `ObjectStore` (`aoe2stats_storage.objects`), a `ReplayValidator`
(`aoe2stats_core.replay.validation`) and an `AlertSink` (`aoe2stats_core.alerting`) — the same five
dependencies data-model.md's write-ordering paragraph and T055's task text name. This is inferred,
not read off an existing signature, and is expected to need adjusting once T055 actually lands.

**Why the budget must gate one claim at a time, not one upfront batch.** Quickstart scenario 4
requires that a budget which runs out mid-backlog leaves the untouched rows `pending` and **none**
`downloading` — data-model.md's claiming query flips a row straight to `downloading` the moment it
is claimed, so a stage that claimed everything eligible before checking the budget would strand the
rows it never got to in `downloading`, not `pending`. The only reading consistent with scenario 4 is
that the drain claims and fully processes one capture per budget-checked iteration, the same
between-items-never-mid-item rule `budget.py` and `run.py` already apply one level up. This test
exploits exactly that: a fake `ReplayProvider.fetch_replay` advances a shared fake clock by a fixed
cost on every call, so the number of captures that fit inside a `Budget(seconds=2.0)` is pinned at
exactly two, deterministically, with no real wall-clock timing involved (the same trick
`test_run.py`'s `RecordingStage` and `test_budget.py`'s `FakeClock` already use).

**Why the four seeded captures defeat every ordering *except* the correct one.** They are inserted
far, near, far, near. Insertion order and its reverse each pick a set containing one near- and one
far-deadline capture; only "ordered by `capture_deadline_at` ascending" — the one line data-model.md
calls "the single most consequential line in the schema" — picks the two near-deadline captures and
leaves both far-deadline ones untouched, which is exactly what this test asserts.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_storage.models import AoeProfile, CaptureSource, CaptureStatus, Match, ReplayCapture

# Chosen so ascending insertion order (far, near, far, near) and its reverse both disagree with the
# deadline-ordered outcome this test asserts — see the module docstring.
_GAME_FAR_FIRST = 900_001
_GAME_NEAR_FIRST = 900_002
_GAME_FAR_SECOND = 900_003
_GAME_NEAR_SECOND = 900_004

_PROFILE_FAR_FIRST = 800_001
_PROFILE_NEAR_FIRST = 800_002
_PROFILE_FAR_SECOND = 800_003
_PROFILE_NEAR_SECOND = 800_004

_NEAR_PROFILE_IDS = {_PROFILE_NEAR_FIRST, _PROFILE_NEAR_SECOND}
_FAR_PROFILE_IDS = {_PROFILE_FAR_FIRST, _PROFILE_FAR_SECOND}


class _FakeClock:
    """A settable stand-in for `aoe2stats_ingester.budget.monotonic` — `test_budget.py`'s and
    `test_run.py`'s own convention, reused here so the drain's budget checks are deterministic.
    """

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class _CostlyReplayProvider:
    """A fake `ReplayProvider` (`contracts/providers.md`) that always succeeds, and whose
    `fetch_replay` advances the shared fake clock by a fixed cost every time it is called — the
    mechanism that pins "half the queue" to an exact, deterministic count of two.
    """

    def __init__(self, clock: _FakeClock, *, cost_seconds: float) -> None:
        self._clock = clock
        self._cost_seconds = cost_seconds
        self.calls: list[tuple[int, int]] = []

    async def fetch_replay(self, game_id: int, profile_id: int) -> Any:
        from aoe2stats_providers.base import ReplayBlob

        self.calls.append((game_id, profile_id))
        self._clock.advance(self._cost_seconds)
        return ReplayBlob(
            content=b"fake replay bytes",
            filename=f"{game_id}_{profile_id}.aoe2record",
            content_type="application/octet-stream",
        )


class _FakeValidator:
    """A fake `ReplayValidator` (`aoe2stats_core.replay.validation`) that always accepts."""

    def validate(self, zip_bytes: bytes) -> Any:
        from aoe2stats_core.replay.validation import ReplayValidationResult

        return ReplayValidationResult(
            inner_filename="game.aoe2record",
            inner_bytes=len(zip_bytes),
            engine_name="fake-engine",
            engine_version="0.0.0",
        )


class _FakeS3Client:
    """The minimal `S3Client` surface `ObjectStore` calls: `test_objects.py`'s own convention,
    reused here rather than reaching for a real bucket.
    """

    def __init__(self) -> None:
        self.put_calls: list[dict[str, Any]] = []

    def put_object(self, **kwargs: Any) -> None:
        self.put_calls.append(kwargs)

    def delete_object(self, **kwargs: Any) -> None:  # pragma: no cover - unused by this scenario
        raise NotImplementedError

    def generate_presigned_url(
        self, client_method: str, **kwargs: Any
    ) -> str:  # pragma: no cover - unused
        raise NotImplementedError

    def get_paginator(self, operation_name: str) -> Any:  # pragma: no cover - unused
        raise NotImplementedError


class _FakeAlertSink:
    """A fake `AlertSink` (`aoe2stats_core.alerting`). Scenario 5 is a clean run — every capture
    succeeds — so the assertion that matters is that nothing was ever written here.
    """

    def __init__(self) -> None:
        self.written: list[tuple[str, int]] = []

    async def write(
        self,
        *,
        kind: str,
        severity: int,
        detail: Any,
        ingest_run_id: uuid.UUID | None,
    ) -> Any:
        from aoe2stats_core.alerting import AlertRecord

        self.written.append((kind, severity))
        return AlertRecord(
            id=uuid.uuid4(),
            kind=kind,
            severity=severity,
            detail=detail,
            raised_at=datetime.now(UTC),
            ingest_run_id=ingest_run_id,
            acknowledged_at=None,
        )

    async def unacknowledged_severity_one(self) -> list[Any]:  # pragma: no cover - unused
        return []


async def _seed_pending_capture(
    session: AsyncSession,
    *,
    game_id: int,
    profile_id: int,
    completed_at: datetime,
    capture_deadline_at: datetime,
) -> None:
    session.add(AoeProfile(profile_id=profile_id, alias=f"player-{profile_id}"))
    session.add(
        Match(
            game_id=game_id,
            leaderboard_id=3,
            completed_at=completed_at,
            source="relic",
            raw_payload={},
        )
    )
    await session.flush()
    session.add(
        ReplayCapture(
            game_id=game_id,
            profile_id=profile_id,
            status=CaptureStatus.PENDING,
            capture_deadline_at=capture_deadline_at,
            source=CaptureSource.AUTOMATIC,
        )
    )
    await session.commit()


async def test_drain_stores_the_near_deadline_captures_when_the_budget_covers_only_half(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import aoe2stats_ingester.budget as budget_module
    from aoe2stats_ingester.budget import Budget
    from aoe2stats_ingester.capture import DrainStage
    from aoe2stats_storage.objects import ObjectStore, ObjectStoreConfig

    now = datetime.now(UTC)
    completed_at = now - timedelta(days=3)

    # Seeded far, near, far, near — see the module docstring on why this order is chosen.
    await _seed_pending_capture(
        db_session,
        game_id=_GAME_FAR_FIRST,
        profile_id=_PROFILE_FAR_FIRST,
        completed_at=completed_at,
        capture_deadline_at=now + timedelta(days=18),
    )
    await _seed_pending_capture(
        db_session,
        game_id=_GAME_NEAR_FIRST,
        profile_id=_PROFILE_NEAR_FIRST,
        completed_at=completed_at,
        capture_deadline_at=now + timedelta(days=2),
    )
    await _seed_pending_capture(
        db_session,
        game_id=_GAME_FAR_SECOND,
        profile_id=_PROFILE_FAR_SECOND,
        completed_at=completed_at,
        capture_deadline_at=now + timedelta(days=18),
    )
    await _seed_pending_capture(
        db_session,
        game_id=_GAME_NEAR_SECOND,
        profile_id=_PROFILE_NEAR_SECOND,
        completed_at=completed_at,
        capture_deadline_at=now + timedelta(days=2),
    )

    clock = _FakeClock()
    monkeypatch.setattr(budget_module, "monotonic", clock)
    provider = _CostlyReplayProvider(clock, cost_seconds=1.0)
    validator = _FakeValidator()
    alert_sink = _FakeAlertSink()
    object_store = ObjectStore(
        ObjectStoreConfig(
            endpoint_url="https://example.eu.r2.cloudflarestorage.com",
            bucket="aoe2-stats-replays-test",
            access_key_id="AKIAEXAMPLE",
            secret_access_key="shh",
            region="auto",
        ),
        client=_FakeS3Client(),
    )

    stage = DrainStage(
        session_factory=session_factory,
        replay_provider=provider,
        object_store=object_store,
        validator=validator,
        alert_sink=alert_sink,
    )

    # Exactly two 1-second downloads fit: t=0 (not expired) processes one, t=1 (not expired)
    # processes a second, t=2 is exactly the deadline (`Budget.expired` at `monotonic() >=
    # deadline`, per `test_budget.py`) and the third is never even claimed.
    budget = Budget(seconds=2.0)
    await stage(budget)

    db_session.expire_all()
    rows = (await db_session.execute(select(ReplayCapture))).scalars().all()
    by_profile = {row.profile_id: row for row in rows}
    assert set(by_profile) == _NEAR_PROFILE_IDS | _FAR_PROFILE_IDS

    for profile_id in _NEAR_PROFILE_IDS:
        row = by_profile[profile_id]
        assert row.status == CaptureStatus.STORED, (
            f"near-deadline capture for profile {profile_id} must be the one stored under budget "
            f"pressure, got {row.status!r}"
        )
        assert row.stored_at is not None
        assert row.object_key is not None
        assert row.zip_sha256 is not None

    for profile_id in _FAR_PROFILE_IDS:
        row = by_profile[profile_id]
        assert row.status == CaptureStatus.PENDING, (
            f"far-deadline capture for profile {profile_id} must be shed under budget pressure, "
            f"not touched, got {row.status!r}"
        )
        assert row.claimed_at is None, "a far-deadline capture must never be claimed at all"

    # The provider was only ever asked for the near-deadline replays, in some order between the
    # two of them — never for a far-deadline one.
    assert {profile_id for _game_id, profile_id in provider.calls} == _NEAR_PROFILE_IDS
    assert len(provider.calls) == 2

    # A clean run under budget pressure is not a failure: nothing here should have alerted.
    assert alert_sink.written == []
