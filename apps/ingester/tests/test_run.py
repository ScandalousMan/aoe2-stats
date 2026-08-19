"""Unit tests for `aoe2stats_ingester.run.run_once` — the entrypoint skeleton T018 ships.

Real stages (`discover.py`, `reconcile.py`, `capture.py`) do not exist yet (Phase 4). These tests
exercise the orchestration shape with small fake `Stage`s instead, which is exactly the seam T053
onward plug into. No database, no network: `run_once` itself touches neither at this stage — see
its module docstring.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

import aoe2stats_ingester.budget as budget_module
from aoe2stats_ingester.budget import Budget
from aoe2stats_ingester.run import RunReport, run_once


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


async def test_run_once_with_no_stages_returns_an_empty_but_valid_report() -> None:
    report = await run_once(60, trigger="test")

    assert isinstance(report, RunReport)
    assert report.trigger == "test"
    assert report.budget_seconds == 60
    assert report.stages_completed == ()
    assert report.stage_reports == {}
    assert report.stopped_early is False
    assert isinstance(report.started_at, datetime)
    assert isinstance(report.finished_at, datetime)
    assert report.finished_at >= report.started_at


async def test_run_once_runs_every_stage_when_the_budget_comfortably_covers_all_of_them(
    monkeypatch,
) -> None:
    clock = FakeClock()
    monkeypatch.setattr(budget_module, "monotonic", clock)
    calls: list[str] = []
    stages = [
        RecordingStage("discover", clock, cost=1, calls=calls),
        RecordingStage("reconcile", clock, cost=1, calls=calls),
        RecordingStage("drain", clock, cost=1, calls=calls),
    ]

    report = await run_once(100, trigger="cron", stages=stages)

    assert calls == ["discover", "reconcile", "drain"]
    assert report.stages_completed == ("discover", "reconcile", "drain")
    assert report.stopped_early is False
    assert report.stage_reports == {
        "discover": {"cost": 1},
        "reconcile": {"cost": 1},
        "drain": {"cost": 1},
    }


async def test_run_once_stops_before_a_stage_the_budget_has_no_room_left_for(monkeypatch) -> None:
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

    report = await run_once(2, trigger="cron", stages=stages)

    # "discover" starts at t=0 (budget not yet expired), finishes at t=1.
    # "reconcile" starts at t=1 (still not expired: deadline is t=2), finishes at t=2.
    # "drain" would start at t=2, which is exactly the deadline: it never runs.
    assert calls == ["discover", "reconcile"]
    assert report.stages_completed == ("discover", "reconcile")
    assert report.stopped_early is True
    assert "drain" not in report.stage_reports


async def test_run_once_never_interrupts_a_stage_already_in_progress(monkeypatch) -> None:
    """A stage that overruns the budget while it is running is still allowed to finish and its
    result is still recorded — the budget only ever gates the *next* stage's start."""
    clock = FakeClock()
    monkeypatch.setattr(budget_module, "monotonic", clock)
    calls: list[str] = []
    # A single stage that costs far more than the whole budget.
    stages = [RecordingStage("drain", clock, cost=1000, calls=calls)]

    report = await run_once(1, trigger="cron", stages=stages)

    assert calls == ["drain"]
    assert report.stages_completed == ("drain",)
    assert report.stage_reports == {"drain": {"cost": 1000}}
    # Nothing was left to attempt afterwards, so the loop never re-checked the (now long-expired)
    # budget: with only one stage, "stopped early" would be a misleading label for this run.
    assert report.stopped_early is False


async def test_run_once_to_dict_is_json_serialisable_and_uses_iso_timestamps() -> None:
    import json

    report = await run_once(60, trigger="local")

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
