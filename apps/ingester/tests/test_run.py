"""Tests for `aoe2stats_ingester.run.run_once` — the entrypoint T018 shipped as a skeleton and
T059 completes with the `ingest_runs` row lifecycle FR-024 asks for.

The orchestration tests below (stage ordering, the budget gate between stages, never mid-stage)
predate T059 and still use small fake `Stage`s rather than the real ones — that shape is exactly
the seam T053 onward plug into, and asserting on it does not need a real `DiscoverStage`,
`ReconcileStage` or `CaptureDrain`. What T059 changes is that `run_once` now always touches the
real throwaway database (`tests/db.py`, T015) for its own `ingest_runs` bookkeeping, so every test
below passes `session_factory=` explicitly — the injectable seam the module docstring describes —
rather than letting `run_once` fall back to building its own engine from `DATABASE_URL`, which
would leave these tests dependent on an environment variable this file has no reason to set.

The T059-specific tests (`test_run_once_opens_the_ingest_runs_row_before_any_stage_runs` onward)
exercise the row lifecycle itself: opened before any stage runs, closed with every counter
`stage_reports` carries in `ingest_runs`' own vocabulary, left open (`finished_at` still null) when
a stage raises, and the two `capture_lag_*` percentiles computed over newly discovered, already
stored captures only.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import aoe2stats_ingester.budget as budget_module
import aoe2stats_ingester.run as run_module
from aoe2stats_ingester.budget import Budget
from aoe2stats_ingester.run import RunReport, run_once
from aoe2stats_providers.base import NotFound, ReplayBlob
from aoe2stats_storage.models import (
    AoeProfile,
    CaptureSource,
    CaptureStatus,
    IngestRun,
    Match,
    ReplayCapture,
)


@pytest.fixture(autouse=True)
def _reset_ingester_logger_disabled_state() -> Iterator[None]:
    """T103's own caplog assertions below share this file with `tests/db.py`'s session-scoped
    `database_url` fixture, which runs the real Alembic migrations the first time anything in this
    session needs the throwaway database — and `infra/migrations/env.py` calls `logging.config.
    fileConfig` on `alembic.ini` as a side effect of that (its own module docstring). `fileConfig`'s
    default `disable_existing_loggers=True` disables every logger that already existed at that
    moment and is not named in the ini — `run_module.logger` (created at import time, by this very
    file's own `import aoe2stats_ingester.run as run_module` above) among them. A disabled
    `Logger.info()`/`.error()` is a silent no-op (`logging.Logger.disabled` short-circuits
    `isEnabledFor`), so a caplog assertion below would otherwise pass or fail depending on which
    test in the session happened to trigger that first migration — an order-dependent heisenbug
    with nothing to do with `run_once`'s own logging. Reset before and after, the same discipline
    `apps/api/tests/conftest.py`'s own `_reset_companion_breaker` applies to a different
    process-lifetime leak; nothing here reaches outside this file's own `run_module.logger`.
    """
    run_module.logger.disabled = False
    yield
    run_module.logger.disabled = False


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class RecordingStage:
    """A `Stage` that logs its own call and advances the fake clock by a fixed cost."""

    def __init__(self, name: str, clock: FakeClock, cost: float, calls: list[str]) -> None:
        self.name = name
        self._clock = clock
        self._cost = cost
        self._calls = calls

    async def __call__(self, budget: Budget) -> Mapping[str, Any]:
        self._calls.append(self.name)
        self._clock.advance(self._cost)
        return {"cost": self._cost}


async def test_run_once_with_no_stages_returns_an_empty_but_valid_report(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    report = await run_once(60, trigger="test", session_factory=session_factory)

    assert isinstance(report, RunReport)
    assert report.trigger == "test"
    assert report.budget_seconds == 60
    assert report.stages_completed == ()
    assert report.stage_reports == {}
    assert report.stopped_early is False
    assert isinstance(report.started_at, datetime)
    assert isinstance(report.finished_at, datetime)
    assert report.finished_at >= report.started_at
    assert isinstance(report.ingest_run_id, uuid.UUID)


async def test_run_once_runs_every_stage_when_the_budget_comfortably_covers_all_of_them(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
) -> None:
    clock = FakeClock()
    monkeypatch.setattr(budget_module, "monotonic", clock)
    calls: list[str] = []
    stages = [
        RecordingStage("discover", clock, cost=1, calls=calls),
        RecordingStage("reconcile", clock, cost=1, calls=calls),
        RecordingStage("drain", clock, cost=1, calls=calls),
    ]

    report = await run_once(100, trigger="cron", stages=stages, session_factory=session_factory)

    assert calls == ["discover", "reconcile", "drain"]
    assert report.stages_completed == ("discover", "reconcile", "drain")
    assert report.stopped_early is False
    assert report.stage_reports == {
        "discover": {"cost": 1},
        "reconcile": {"cost": 1},
        "drain": {"cost": 1},
    }


async def test_run_once_stops_before_a_stage_the_budget_has_no_room_left_for(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
) -> None:
    """The budget is checked between stages, never mid-stage: a stage already running always
    finishes, but a stage that has not started yet, and would not fit, never starts."""
    clock = FakeClock()
    monkeypatch.setattr(budget_module, "monotonic", clock)
    calls: list[str] = []
    stages = [
        RecordingStage("discover", clock, cost=1, calls=calls),
        RecordingStage("reconcile", clock, cost=1, calls=calls),
        RecordingStage("drain", clock, cost=1, calls=calls),
    ]

    report = await run_once(2, trigger="cron", stages=stages, session_factory=session_factory)

    # "discover" starts at t=0 (budget not yet expired), finishes at t=1.
    # "reconcile" starts at t=1 (still not expired: deadline is t=2), finishes at t=2.
    # "drain" would start at t=2, which is exactly the deadline: it never runs.
    assert calls == ["discover", "reconcile"]
    assert report.stages_completed == ("discover", "reconcile")
    assert report.stopped_early is True
    assert "drain" not in report.stage_reports


async def test_run_once_never_interrupts_a_stage_already_in_progress(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
) -> None:
    """A stage that overruns the budget while it is running is still allowed to finish and its
    result is still recorded — the budget only ever gates the *next* stage's start."""
    clock = FakeClock()
    monkeypatch.setattr(budget_module, "monotonic", clock)
    calls: list[str] = []
    # A single stage that costs far more than the whole budget.
    stages = [RecordingStage("drain", clock, cost=1000, calls=calls)]

    report = await run_once(1, trigger="cron", stages=stages, session_factory=session_factory)

    assert calls == ["drain"]
    assert report.stages_completed == ("drain",)
    assert report.stage_reports == {"drain": {"cost": 1000}}
    # Nothing was left to attempt afterwards, so the loop never re-checked the (now long-expired)
    # budget: with only one stage, "stopped early" would be a misleading label for this run.
    assert report.stopped_early is False


async def test_run_once_to_dict_is_json_serialisable_and_uses_iso_timestamps(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    import json

    report = await run_once(60, trigger="local", session_factory=session_factory)

    payload = json.dumps(report.to_dict())
    decoded = json.loads(payload)

    assert decoded["trigger"] == "local"
    assert decoded["budget_seconds"] == 60
    # Round-trips through `datetime.fromisoformat` without raising.
    datetime.fromisoformat(decoded["started_at"])
    datetime.fromisoformat(decoded["finished_at"])
    assert decoded["stages_completed"] == []
    assert decoded["stopped_early"] is False
    assert decoded["stage_reports"] == {}
    # Round-trips through `uuid.UUID` without raising, and matches the row `run_once` opened.
    assert uuid.UUID(decoded["ingest_run_id"]) == report.ingest_run_id


# --- T059: the `ingest_runs` row lifecycle -----------------------------------------------------


async def _load_ingest_run(
    session_factory: async_sessionmaker[AsyncSession], run_id: uuid.UUID
) -> IngestRun:
    async with session_factory() as session:
        row = await session.get(IngestRun, run_id)
    assert row is not None, f"no ingest_runs row for {run_id}"
    return row


class _AssertingStage:
    """A `Stage` that queries the real `ingest_runs` table itself, mid-`run_once`, to prove the
    row `_open_ingest_run` inserts is visible to every stage that runs — not merely to `run_once`'s
    own later `_close_ingest_run` call — before any stage has done a single thing.
    """

    name = "probe"

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        expected_trigger: str,
        expected_budget_seconds: int,
        observations: list[IngestRun],
    ) -> None:
        self._session_factory = session_factory
        self._expected_trigger = expected_trigger
        self._expected_budget_seconds = expected_budget_seconds
        self._observations = observations

    async def __call__(self, budget: Budget) -> Mapping[str, Any]:
        async with self._session_factory() as session:
            result = await session.execute(select(IngestRun))
            rows = list(result.scalars().all())
        assert len(rows) == 1, "run_once (T059) must open exactly one ingest_runs row per call"
        row = rows[0]
        assert row.trigger == self._expected_trigger
        assert row.budget_seconds == self._expected_budget_seconds
        assert row.finished_at is None, (
            "the row must still be open while a stage is running — run_once closes it only after "
            "every stage that started has finished"
        )
        self._observations.append(row)
        return {}


async def test_run_once_opens_the_ingest_runs_row_before_any_stage_runs(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    observations: list[IngestRun] = []
    probe = _AssertingStage(
        session_factory,
        expected_trigger="cron",
        expected_budget_seconds=45,
        observations=observations,
    )

    report = await run_once(45, trigger="cron", stages=[probe], session_factory=session_factory)

    assert len(observations) == 1, "the probe stage must have run and observed the open row"
    assert observations[0].id == report.ingest_run_id


async def test_run_once_closes_the_ingest_runs_row_with_every_counter(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """`profiles_polled`/`matches_discovered` are the two keys more than one stage ever reports
    (`discover.py` and `reconcile.py` both report them); the drain-only keys below prove those are
    taken as-is rather than summed against a stage that never mentions them."""

    class _FakeDiscover:
        name = "discover"

        async def __call__(self, budget: Budget) -> Mapping[str, Any]:
            return {
                "profiles_polled": 3,
                "matches_discovered": 2,
                "captures_enqueued": 5,  # no ingest_runs column; must not appear on the row
            }

    class _FakeReconcile:
        name = "reconcile"

        async def __call__(self, budget: Budget) -> Mapping[str, Any]:
            return {"profiles_polled": 7, "matches_discovered": 1, "backfills_cleared": 2}

    class _FakeDrain:
        name = "drain"

        async def __call__(self, budget: Budget) -> Mapping[str, Any]:
            return {
                "captures_attempted": 4,
                "stored_total": 2,
                "quarantined_total": 1,
                "unavailable_total": 0,
                "expired_total": 0,
                "failed_total": 1,
                "alerts_raised": 2,
                "backlog_remaining": 9,
            }

    report = await run_once(
        60,
        trigger="cron",
        stages=[_FakeDiscover(), _FakeReconcile(), _FakeDrain()],
        session_factory=session_factory,
    )

    row = await _load_ingest_run(session_factory, report.ingest_run_id)
    assert row.finished_at is not None
    assert row.finished_at >= row.started_at
    # Summed across discover + reconcile, the only two stages that report either key.
    assert row.profiles_polled == 10
    assert row.matches_discovered == 3
    # Drain-only counters, taken as-is.
    assert row.captures_attempted == 4
    assert row.stored_total == 2
    assert row.quarantined_total == 1
    assert row.unavailable_total == 0
    assert row.expired_total == 0
    assert row.failed_total == 1
    assert row.alerts_raised == 2
    assert row.backlog_remaining == 9


async def test_run_once_leaves_the_row_open_when_a_stage_raises(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    class _ExplodingStage:
        name = "reconcile"

        async def __call__(self, budget: Budget) -> Mapping[str, Any]:
            raise RuntimeError("the discovery source is unreachable")

    ingest_run_ids_before = await _all_ingest_run_ids(session_factory)

    try:
        await run_once(
            30, trigger="cron", stages=[_ExplodingStage()], session_factory=session_factory
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("run_once must propagate a stage's exception, not swallow it")

    ingest_run_ids_after = await _all_ingest_run_ids(session_factory)
    new_ids = ingest_run_ids_after - ingest_run_ids_before
    assert len(new_ids) == 1, "the row opened before the stage ran must still exist"
    row = await _load_ingest_run(session_factory, new_ids.pop())
    assert row.finished_at is None, (
        "a run that dies leaves an open row with a null finished_at (data-model.md) — closing it "
        "here would be a row claiming a cycle finished when it did not"
    )
    # Nothing beyond what `_open_ingest_run` writes: every counter is still its column default.
    assert row.profiles_polled == 0
    assert row.stored_total == 0
    assert row.capture_lag_p50_seconds is None
    assert row.capture_lag_p95_seconds is None


async def _all_ingest_run_ids(session_factory: async_sessionmaker[AsyncSession]) -> set[uuid.UUID]:
    async with session_factory() as session:
        result = await session.execute(select(IngestRun.id))
        return set(result.scalars().all())


# --- T059: capture_lag_p50_seconds / capture_lag_p95_seconds -----------------------------------

_LEADERBOARD_ID = 3


async def _seed_capture_for_lag(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    game_id: int,
    profile_id: int,
    completed_at: datetime,
    first_seen_at: datetime,
    stored_at: datetime | None,
) -> None:
    async with session_factory() as session:
        session.add(AoeProfile(profile_id=profile_id, alias=str(profile_id)))
        session.add(
            Match(
                game_id=game_id,
                leaderboard_id=_LEADERBOARD_ID,
                completed_at=completed_at,
                source="relic",
                raw_payload={"matchId": game_id},
            )
        )
        await session.flush()
        session.add(
            ReplayCapture(
                game_id=game_id,
                profile_id=profile_id,
                status=CaptureStatus.STORED if stored_at else CaptureStatus.PENDING,
                capture_deadline_at=completed_at + timedelta(days=21),
                source=CaptureSource.AUTOMATIC,
                first_seen_at=first_seen_at,
                stored_at=stored_at,
                object_key=(f"replays/{game_id}/{profile_id}.zip" if stored_at else None),
                zip_bytes=123 if stored_at else None,
                zip_sha256=("0" * 64) if stored_at else None,
            )
        )
        await session.commit()


async def test_run_once_computes_capture_lag_over_newly_discovered_stored_captures_only(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
) -> None:
    """Four captures, three of which must never contribute to the lag percentiles: one first seen
    before this run's own window even started (already known work, not "newly discovered" by this
    cycle), one first seen well past its own match's `completed_at + 48h` (a backfill-shaped
    observation, excluded by `_NEWLY_DISCOVERED_LAG_WINDOW_HOURS` for the same reason T061's
    trailing-window measure excludes it), and one never stored at all (no lag to measure). Only the
    three ordinary ones, seeded with lags of 100 s, 200 s and 300 s, must produce the percentiles.
    """
    window_start = datetime(2026, 1, 1, tzinfo=UTC)
    window_end = window_start + timedelta(minutes=5)
    times = iter([window_start, window_end])
    monkeypatch.setattr(run_module, "_now", lambda: next(times))

    base_completed_at = window_start - timedelta(hours=1)
    # Three ordinary captures, newly discovered inside this run's own window, each already stored
    # — lags of 100 s, 200 s and 300 s.
    for index, lag_seconds in enumerate((300, 100, 200)):  # deliberately out of order
        completed_at = base_completed_at
        first_seen_at = window_start + timedelta(seconds=index + 1)
        await _seed_capture_for_lag(
            session_factory,
            game_id=800_000_001 + index,
            profile_id=900_000_001 + index,
            completed_at=completed_at,
            first_seen_at=first_seen_at,
            stored_at=completed_at + timedelta(seconds=lag_seconds),
        )

    # Excluded: first seen before this run's own window started — not newly discovered by it.
    await _seed_capture_for_lag(
        session_factory,
        game_id=800_000_101,
        profile_id=900_100_001,
        completed_at=base_completed_at,
        first_seen_at=window_start - timedelta(days=1),
        stored_at=base_completed_at + timedelta(seconds=999_999),
    )

    # Excluded: first seen long after its own match's completed_at + 48h — backfill-shaped.
    old_completed_at = window_start - timedelta(days=60)
    await _seed_capture_for_lag(
        session_factory,
        game_id=800_000_102,
        profile_id=900_100_002,
        completed_at=old_completed_at,
        first_seen_at=window_start + timedelta(seconds=1),
        stored_at=old_completed_at + timedelta(seconds=999_999),
    )

    # Excluded: newly discovered this run, but never stored — nothing to measure yet.
    await _seed_capture_for_lag(
        session_factory,
        game_id=800_000_103,
        profile_id=900_100_003,
        completed_at=base_completed_at,
        first_seen_at=window_start + timedelta(seconds=1),
        stored_at=None,
    )

    report = await run_once(60, trigger="cron", stages=[], session_factory=session_factory)

    row = await _load_ingest_run(session_factory, report.ingest_run_id)
    # Sorted lags: [100, 200, 300]. Nearest-rank p50 -> ceil(0.5*3)=2 -> index 1 -> 200.
    # Nearest-rank p95 -> ceil(0.95*3)=3 -> index 2 -> 300.
    assert row.capture_lag_p50_seconds == 200
    assert row.capture_lag_p95_seconds == 300


async def test_run_once_reports_no_capture_lag_when_nothing_was_newly_discovered_and_stored(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    report = await run_once(30, trigger="cron", stages=[], session_factory=session_factory)

    row = await _load_ingest_run(session_factory, report.ingest_run_id)
    assert row.capture_lag_p50_seconds is None
    assert row.capture_lag_p95_seconds is None


# --- T059: folding a real `CaptureDrain`'s report into the row ---------------------------------


class _NoOpReplayProvider:
    """A `ReplayProvider` this test never expects to be called: nothing is `pending`, so
    `CaptureDrain` never claims a row to fetch in the first place."""

    async def fetch_replay(self, game_id: int, profile_id: int) -> ReplayBlob | NotFound:
        raise AssertionError("no pending capture exists for the drain to claim in this test")


# --- T103: structured logging carries the run id and never a raw exception value --------------


async def test_run_once_logs_the_run_id_on_start_and_finish(
    caplog: pytest.LogCaptureFixture,
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
) -> None:
    """Both the start and the finish line name this call's own `ingest_runs` row id, so an
    operator reading the process log can go straight from either line to the row FR-024 asks for
    — the same correlation `test_run_once_opens_the_ingest_runs_row_before_any_stage_runs` proves
    at the database layer, asserted here at the log layer instead."""
    with caplog.at_level("INFO", logger="aoe2stats_ingester"):
        report = await run_once(60, trigger="cron", session_factory=session_factory)

    run_id_text = str(report.ingest_run_id)
    messages = [record.getMessage() for record in caplog.records]
    assert any(run_id_text in message and "started" in message for message in messages)
    assert any(run_id_text in message and "finished" in message for message in messages)


async def test_run_once_logs_the_run_id_and_failure_class_never_the_exception_message(
    caplog: pytest.LogCaptureFixture,
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
) -> None:
    """Constitution VIII: a stage's own exception message is not something `run_once` can vouch
    for — this simulates the concrete risk (a provider or database error echoing back a value the
    cycle handled) and asserts the failure line names the run id and the exception's *class*
    while never repeating the secret-shaped text the exception carried, mirroring
    `apps/api/tests/test_configuration_envelope.py`'s own "names keys and never values" assertion
    for the sibling handler this task also touches."""
    _leaked_looking_value = "S3_SECRET_ACCESS_KEY=cd1f9e7b2a6e4c0f9b7a3d5e8c1a2b3d"

    class _ExplodingStage:
        name = "drain"

        async def __call__(self, budget: Budget) -> Mapping[str, Any]:
            raise RuntimeError(f"upstream request failed: {_leaked_looking_value}")

    with caplog.at_level("ERROR", logger="aoe2stats_ingester"), pytest.raises(RuntimeError):
        await run_once(
            30, trigger="cron", stages=[_ExplodingStage()], session_factory=session_factory
        )

    failure_records = [record for record in caplog.records if record.levelname == "ERROR"]
    assert len(failure_records) == 1
    message = failure_records[0].getMessage()
    assert "RuntimeError" in message
    assert "failed" in message
    assert _leaked_looking_value not in message
    assert "upstream request failed" not in message


async def test_run_once_folds_a_real_capture_drains_report_into_the_row(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Not a fake `Stage` this time: a real `CaptureDrain` (T055-T058), constructed with the
    fairness-quota keywords `max_captures_per_user_per_run`/`quota_exempt_days` (FR-044) supplied
    together rather than left at the default `None` that leaves the quota inert (`capture.py`'s
    own module docstring on T058's gap) — the same wiring discipline `run_once` itself must apply
    wherever *it* ever constructs a collaborator. Nothing is `pending`, so this exercises the
    empty-backlog path end to end: the real drain's own `_ZERO_COUNTERS`-shaped report must fold
    into the row exactly as the fake-stage test above already proved the aggregation math does.
    """
    from aoe2stats_ingester.capture import CaptureDrain

    drain = CaptureDrain(
        session_factory=session_factory,
        replay_provider=_NoOpReplayProvider(),
        max_captures_per_user_per_run=20,
        quota_exempt_days=7,
    )
    assert drain.name == "drain"

    report = await run_once(30, trigger="cron", stages=[drain], session_factory=session_factory)

    assert report.stages_completed == ("drain",)
    row = await _load_ingest_run(session_factory, report.ingest_run_id)
    assert row.captures_attempted == 0
    assert row.stored_total == 0
    assert row.quarantined_total == 0
    assert row.unavailable_total == 0
    assert row.expired_total == 0
    assert row.failed_total == 0
    assert row.alerts_raised == 0
    assert row.backlog_remaining == 0
