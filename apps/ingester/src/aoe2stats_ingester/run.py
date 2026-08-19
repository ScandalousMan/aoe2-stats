"""`run_once(budget_seconds)` — the whole unit of ingestion work (ADR-0002, constitution XII).

This is the one function the two entrypoints share, and the only thing they share: the Vercel cron
handler (`api/cron/ingest.py`) and the local/phase-2-VPS trigger (`apps/api/src/aoe2stats_api/
routers/cron.py`) each call `run_once()` directly, each pass it `Settings.ingest_run_budget_seconds`
(the environment variable `INGEST_RUN_BUDGET_SECONDS`), and neither calls the other — an HTTP hop
between the two would put the cycle in the entrypoint that has no extended duration. Passing the
same setting down from both callers is what keeps the platform's 300 s function ceiling and the
budget this code actually honours from becoming two numbers maintained apart: there is exactly one
place (`.env.example`) that number is written down.

**T018 ships the skeleton only.** The actual stages — discovery (T053), the 25-day reconciliation
sweep and 31-day backfill (T054), and the capture drain (T055, completed by T059) — are Phase 4
work; this module is the shape they plug into, not their implementation. `DEFAULT_STAGES` starts
empty and each of those tasks appends its stage to it in the order plan.md names them (discover,
reconcile, drain), so a cycle run today does real, honest nothing rather than a placeholder
pretending to be one. T059 also adds what this skeleton deliberately does not: the `ingest_runs`
row opened before any work and closed after, and the counters (`capture_lag_p50_seconds`, ...)
FR-024 needs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from aoe2stats_ingester.budget import Budget


@runtime_checkable
class Stage(Protocol):
    """One phase of a cycle: discovery, reconciliation, the capture drain.

    Called with the run's `Budget` so it can walk its own queue through `iter_within_budget`
    (`budget.py`); returns a small mapping of counters that `run_once` files under the stage's
    `name` in the report. A stage decides for itself when to stop honouring the budget inside its
    own loop — `run_once` only ever decides whether to *start* the next stage, the same
    between-items-never-mid-item rule applied one level up (see this module's and `budget.py`'s
    docstrings).
    """

    name: str

    async def __call__(self, budget: Budget) -> Mapping[str, Any]: ...


#: Populated by later tasks as each stage lands — T053 (discovery), T054 (reconciliation), T055/
#: T059 (the capture drain) — in that order. Empty here is deliberate, not an oversight: see the
#: module docstring on why T018 builds only the shape.
DEFAULT_STAGES: tuple[Stage, ...] = ()


@dataclass(frozen=True, slots=True)
class RunReport:
    """What one call to `run_once` produced.

    Not yet the `ingest_runs` row itself — T059 persists a version of this to storage and adds the
    FR-024 counters an `ingest_runs` row carries. This is the in-process shape that extends into,
    and the shape both entrypoints render directly as their HTTP response today.
    """

    trigger: str
    budget_seconds: float
    started_at: datetime
    finished_at: datetime
    stages_completed: tuple[str, ...]
    stopped_early: bool
    stage_reports: Mapping[str, Mapping[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        """The JSON-serialisable form the two entrypoints render as their run report."""
        return {
            "trigger": self.trigger,
            "budget_seconds": self.budget_seconds,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "stages_completed": list(self.stages_completed),
            "stopped_early": self.stopped_early,
            "stage_reports": {name: dict(report) for name, report in self.stage_reports.items()},
        }


async def run_once(
    budget_seconds: float,
    *,
    trigger: str = "cron",
    stages: Sequence[Stage] = DEFAULT_STAGES,
) -> RunReport:
    """Run one ingest cycle, honouring `budget_seconds` between stages and never mid-stage.

    `budget_seconds` is always `Settings.ingest_run_budget_seconds` in production. `trigger`
    records which entrypoint asked for the cycle (`"cron"` for the Vercel schedule, `"local"` for
    the quickstart trigger, `"worker"` for the phase-2 loop) — T059 carries it onto the
    `ingest_runs` row; this skeleton only carries it onto the report.

    Each stage is only ever *started* while budget remains; once one is running it is never
    interrupted mid-stage, exactly as `iter_within_budget` never interrupts mid-item within one.
    A stage that starts late in the budget can still overrun it slightly — that is the price of
    never leaving a claim, a download or an upload half-done, and is why the reclaim path (T055)
    exists for the one row a hard process kill can still catch.
    """
    started_at = datetime.now(UTC)
    budget = Budget(seconds=budget_seconds)

    stages_completed: list[str] = []
    stage_reports: dict[str, Mapping[str, Any]] = {}
    stopped_early = False

    for stage in stages:
        if budget.expired:
            stopped_early = True
            break
        stage_reports[stage.name] = await stage(budget)
        stages_completed.append(stage.name)

    finished_at = datetime.now(UTC)
    return RunReport(
        trigger=trigger,
        budget_seconds=budget_seconds,
        started_at=started_at,
        finished_at=finished_at,
        stages_completed=tuple(stages_completed),
        stopped_early=stopped_early,
        stage_reports=stage_reports,
    )
