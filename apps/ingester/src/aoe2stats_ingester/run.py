"""`run_once(budget_seconds)` — the whole unit of ingestion work (ADR-0002, constitution XII).

This is the one function the two entrypoints share, and the only thing they share: the Vercel cron
handler (`api/cron/ingest.py`) and the local/phase-2-VPS trigger (`apps/api/src/aoe2stats_api/
routers/cron.py`) each call `run_once()` directly, each pass it `Settings.ingest_run_budget_seconds`
(the environment variable `INGEST_RUN_BUDGET_SECONDS`), and neither calls the other — an HTTP hop
between the two would put the cycle in the entrypoint that has no extended duration. Passing the
same setting down from both callers is what keeps the platform's 300 s function ceiling and the
budget this code actually honours from becoming two numbers maintained apart: there is exactly one
place (`.env.example`) that number is written down.

**T059 — the `ingest_runs` row.** Every field on that row but `id` is either open-before or
closed-after, never written in one go (data-model.md's own `ingest_runs` section, quoted here
because it is this function's actual contract): the row is **inserted when the run starts**,
carrying `started_at`, `trigger` and `budget_seconds` and nothing else, *before* `stages` is ever
touched. It is opened this early, rather than assembled once at the end, because every `alerts` row
carries `ingest_run_id`, and four of the five producers fire during the drain (`ratelimit.py`'s
`rate_limited`, `capture.py`'s `validation_failed` and `expired_capture`) or immediately after it
(T059a's `deadline_breach`) — a row that did not exist yet would leave every one of them orphaned
and `alerts_raised` permanently short of the truth. `stages` then runs exactly as the T018 skeleton
always did: each one only ever *started* while budget remains, never interrupted mid-stage once
started. The row is **closed** once every stage that started has finished (or the loop stopped
early for want of budget) with `finished_at` and every counter `stage_reports` carries in
`ingest_runs`' own vocabulary (`_aggregate_counters`), plus `capture_lag_p50_seconds` and
`capture_lag_p95_seconds` (FR-024, `_capture_lag_seconds`).

**A run that dies leaves an open row.** Nothing here ever catches an exception a stage raises (a
`ReconcileStage` outage after three unreachable cycles, T054a, is the concrete case this is written
for) and closes the row anyway — that would be a row claiming a cycle finished when it did not, a
lie no dashboard reading `ingest_runs` could ever detect. The exception propagates out of
`run_once` exactly as it would have before this task, and the row it opened is left with a null
`finished_at` — "a fact worth having rather than a row that was never written" (data-model.md), and
the second of the two signals the nightly liveness check (T048, T061) reads: the row's absence
means nothing ran at all, its open `finished_at` means something did and did not finish.

**T059c — the id actually reaches the alerts it was opened for.** T059's own paragraph above states
the reason this row is opened early: four of the five alert producers fire during the drain or
immediately after it. Opening the row early is necessary but was not, on its own, sufficient —
`Stage.__call__` took only a `Budget`, and `CaptureDrain`'s constructor had no run-id parameter, so
`rate_limited`, `validation_failed` and `expired_capture` each wrote `ingest_run_id=None`
regardless. `RunScoped` (below) and `run_once`'s own loop closing this gap: any stage that
implements it has `bind_run(run_id)` called on it immediately before it runs, so a `CaptureDrain`
handed the same `run_id` this call's own `ingest_runs` row was opened with can carry it into every
alert it raises. `_raise_deadline_breach_alert`, the fourth producer, needed no such change — it
already closes over `run_id` directly, being a local function of this module rather than a stage.

**`session_factory` is the one thing about this function's own database access that is not handed
down from a `Settings` instance a caller already resolved**, unlike `budget_seconds`/`trigger`/
`stages` (see the paragraph above, and every one of those three names in the signature below).
A caller that wants this function's own writes to land against a database it controls — every
integration test in this package (`test_deadline_alert.py`, `test_run.py`) — passes
`session_factory=` explicitly, built exactly as `tests/db.py` builds one for the rest of this
package's tests. A caller that does not — both production entrypoints today, neither of which is
this task's to change — gets `_default_session_factory()`: an `AsyncEngine` built once, this call
only, straight from `DATABASE_URL` in `os.environ` (`packages/storage/src/aoe2stats_storage/
repositories/base.py`'s own docstring names this call out directly: "the ingester's `run_once()`
... build[s] ... an engine from it"). This is deliberate, not an oversight of the "never re-read a
setting from the environment inside `run_once`" rule stated above: that rule is about the three
values a caller already resolved through its own `Settings` and would otherwise resolve a second,
possibly-divergent way inside this function; the database connection this function's own direct
writes need is not one of those three, and `apps/ingester` cannot import `apps/api`'s `Settings` to
resolve it any other way (`test_backfill.py`'s own module docstring: `packages/storage` — and
everything beneath it, including this module — is a library `apps/api` depends on, not the
reverse). Building a fresh engine per call rather than holding one across calls is exactly what
`build_engine`'s own `NullPool` choice is for (research §4): every process this code runs in is
short-lived and connects through Neon's pooled endpoint, so there is nothing here to amortise.

**`DEFAULT_STAGES` staying `()` was never this module's fix to make — and, as of T060, it no
longer needs to be.** `DiscoverStage` (`discover.py`, T053), `ReconcileStage` (`reconcile.py`,
T054) and `CaptureDrain` (`capture.py`, T055-T058) cannot be constructed without a real
`MatchHistoryProvider`/`ProfileProvider`/`ReplayProvider`/`ObjectStore`/`ReplayValidator` and the
`Settings` values those need — and `Settings` lives in `apps/api`, which this package cannot import
(see the paragraph above) — so composition was always necessarily a caller's job, never this
module's. T060 is that caller: `apps/api/src/aoe2stats_api/ingest_stages.py`'s
`build_ingest_stages(settings)` builds all three from `Settings` alone, and both production
entrypoints (`apps/api/src/aoe2stats_api/routers/cron.py`, `api/cron/ingest.py`) now pass its
result as `stages=` — so `DEFAULT_STAGES` itself stays `()` (there is still no `Settings`-free way
to build a real stage, and there should not be one), but a production cycle run through either
entrypoint today discovers, reconciles and drains for real. `apps/api/tests/test_cron.py`'s and
`test_cron_ingest_entrypoint.py`'s `stages_completed` assertions now name the three real stages
rather than asserting `[]`, which is what caught this gap while it existed.
"""

from __future__ import annotations

import math
import os
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, runtime_checkable

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_core.alerting import AlertRecord, raise_alert
from aoe2stats_ingester.budget import Budget
from aoe2stats_storage.models import Alert as AlertRow
from aoe2stats_storage.models import CaptureStatus, IngestRun, Match, ReplayCapture
from aoe2stats_storage.repositories.base import build_engine, build_session_factory


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


@runtime_checkable
class RunScoped(Protocol):
    """A `Stage` that needs to know which `ingest_runs` row the current call belongs to, so any
    alert it raises inside `__call__` carries a real `ingest_run_id` instead of orphaning it
    (T059c). `run_once` below binds the id onto every stage that implements this, immediately
    before starting it.

    Deliberately **not** a widening of `Stage.__call__`'s own signature. `DiscoverStage`
    (`discover.py`, T053) and `ReconcileStage` (`reconcile.py`, T054) also implement `Stage` and
    raise no alerts today, so adding a `run_id` parameter to every stage's call signature would
    touch both files for a need neither of them has. `CaptureDrain` (`capture.py`, T055-T058) is
    the only stage this protocol exists for; `run_once` checks with `isinstance` rather than
    assuming every `Stage` satisfies it.

    Also deliberately **not** a constructor argument on `CaptureDrain`. `build_ingest_stages`
    (`apps/api/src/aoe2stats_api/ingest_stages.py`) is the one place production ever constructs a
    `CaptureDrain`, and nothing about that call site guarantees the instance is built fresh for
    every single run — a value fixed at construction would be correct for the first call handed to
    it and silently stale for every one after it, since the run id is necessarily per run. A method
    called once per run, right before `__call__`, is correct regardless of how long the instance
    that implements it lives.
    """

    def bind_run(self, run_id: uuid.UUID) -> None: ...


#: Empty today and not this task's to populate — see the module docstring's closing paragraph for
#: why: every real stage exists, but none of them can be constructed without settings and
#: providers only `apps/api` holds, and no caller through T062 hands any of that down to this
#: function. A caller that wants real work done builds its own stage instances and passes them as
#: `stages=`, exactly as this package's own integration tests do.
DEFAULT_STAGES: tuple[Stage, ...] = ()

#: `DATABASE_URL` (`.env.example`): read directly from the environment only when a caller does not
#: hand this function its own `session_factory` — see the module docstring's paragraph on why this
#: one value is the deliberate exception to "never re-read a setting from the environment inside
#: `run_once`".
_DATABASE_URL_ENV = "DATABASE_URL"

#: SC-002 (spec.md) / T061's own stated exclusion rule for the identical measure computed at a
#: different scope (a trailing seven days there, this one run here): a capture whose
#: `first_seen_at` lands more than this many hours after its match's `completed_at` was already
#: old the moment this system first saw it — a 31-day backfill (T031a), or a reconciliation sweep
#: catching up after an outage (T054a) — and folding it into this run's own lag counters would
#: report how far back a rescue reached rather than how fast the day-to-day cadence is
#: (data-model.md's `ingest_runs` section: "the lag counters are over newly discovered captures
#: only. Including backfill would make the number describe how far back a rescue reached rather
#: than how fast the cadence is").
_NEWLY_DISCOVERED_LAG_WINDOW_HOURS = 48

#: `ingest_runs`' own counter vocabulary that `stage_reports` fills in, summed across every stage
#: that reports a given key — `discover.py` and `reconcile.py` both report `profiles_polled` and
#: `matches_discovered` (a cycle running both counts both), while the rest (`captures_attempted`
#: through `backlog_remaining`) are `capture.py`'s drain alone. Any other key a stage report
#: carries (`captures_enqueued`, `rating_snapshots_recorded`, `backfills_cleared`, ...) has no
#: column on `ingest_runs` and is left in `RunReport.stage_reports` only, per-stage, uncollapsed —
#: `test_quarantine.py`'s own docstring is the reason this list exists at all: "a stage report that
#: already speaks that vocabulary is what lets T059 fold it in with no per-key translation."
_COUNTER_KEYS: tuple[str, ...] = (
    "profiles_polled",
    "matches_discovered",
    "captures_attempted",
    "stored_total",
    "failed_total",
    "unavailable_total",
    "expired_total",
    "quarantined_total",
    "alerts_raised",
    "backlog_remaining",
)


def _now() -> datetime:
    """The one place `run_once` reads the wall clock for its own `started_at`/`finished_at` (and,
    through them, the capture-lag window) — a thin wrapper for exactly one reason: a test can
    monkeypatch this name to control both timestamps precisely, the same way `test_run.py`'s
    existing `FakeClock` already controls `budget.py`'s `monotonic` for the time *budget*. Real
    production code never patches this; `datetime.now(UTC)` is exactly what it calls.
    """
    return datetime.now(UTC)


def _aggregate_counters(stage_reports: Mapping[str, Mapping[str, Any]]) -> dict[str, int]:
    """Sum `_COUNTER_KEYS` across every stage's report — see that constant's own docstring for why
    summing, rather than picking one stage's value, is correct: `profiles_polled` and
    `matches_discovered` are the only two keys more than one stage ever reports, and a cycle that
    ran both discovery and reconciliation really did poll/discover the total of what each did.
    A stage that never ran, or never reported a given key, contributes nothing (the default is 0,
    never a stage-shaped placeholder), so a cycle that stopped early before the drain ever started
    still closes its row with the counters the stages that *did* run actually produced.
    """
    totals = dict.fromkeys(_COUNTER_KEYS, 0)
    for report in stage_reports.values():
        for key in _COUNTER_KEYS:
            value = report.get(key)
            if isinstance(value, int):
                totals[key] += value
    return totals


def _nearest_rank(sorted_values: Sequence[int], fraction: float) -> int:
    """The nearest-rank percentile over an already-sorted, non-empty sequence: the smallest value
    at or beyond the `ceil(fraction * n)`-th position (1-indexed), clamped to at least the first
    and at most the last element. `fraction=0.5` is the median (`capture_lag_p50_seconds`),
    `fraction=0.95` is `capture_lag_p95_seconds` — the same statistic SC-002 and T061's own nightly
    check are stated in terms of, computed here over one run's own newly discovered captures rather
    than a trailing seven-day window.
    """
    rank = max(1, math.ceil(fraction * len(sorted_values)))
    return sorted_values[min(rank, len(sorted_values)) - 1]


async def _capture_lag_seconds(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    window_start: datetime,
    window_end: datetime,
) -> tuple[int | None, int | None]:
    """`(capture_lag_p50_seconds, capture_lag_p95_seconds)` over every capture this run newly
    discovered and has already stored — `None, None` when there is nothing to measure (no capture
    both first seen in `[window_start, window_end]` and `stored_at` non-null by the time this is
    called, `finished_at`, the overwhelmingly common case for a capture discovered the same cycle
    it is measured in).

    "Newly discovered" is `ReplayCapture.first_seen_at` falling inside this run's own
    `[started_at, finished_at]` window — the row did not exist before this cycle inserted it — with
    `_NEWLY_DISCOVERED_LAG_WINDOW_HOURS` excluding anything whose `first_seen_at` is later than its
    own `matches.completed_at` plus that many hours, the same exclusion T061's own trailing-window
    measure applies, and for the same reason: a row that old the moment it was first seen is a
    backfill or a reconciliation catch-up, not the day-to-day cadence SC-002 is a statement about
    (see `_NEWLY_DISCOVERED_LAG_WINDOW_HOURS`'s own docstring).
    """
    cutoff = timedelta(hours=_NEWLY_DISCOVERED_LAG_WINDOW_HOURS)
    async with session_factory() as session:
        result = await session.execute(
            select(ReplayCapture.stored_at, Match.completed_at)
            .join(Match, Match.game_id == ReplayCapture.game_id)
            .where(
                ReplayCapture.first_seen_at >= window_start,
                ReplayCapture.first_seen_at <= window_end,
                ReplayCapture.first_seen_at <= Match.completed_at + cutoff,
                ReplayCapture.stored_at.is_not(None),
            )
        )
        rows = result.all()

    if not rows:
        return None, None

    lags = sorted(
        int((stored_at - completed_at).total_seconds()) for stored_at, completed_at in rows
    )
    return _nearest_rank(lags, 0.50), _nearest_rank(lags, 0.95)


async def _open_ingest_run(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    run_id: uuid.UUID,
    started_at: datetime,
    trigger: str,
    budget_seconds: float,
) -> None:
    """Insert the `ingest_runs` row, carrying `started_at`, `trigger` and `budget_seconds` and
    nothing else — see the module docstring for why this happens before any stage ever runs.
    `budget_seconds` is stored as the column's own `Integer` type; `run_once`'s own parameter stays
    a `float` (matching `RunReport.budget_seconds` and `Budget`, both already `float`-typed), so
    the narrowing happens here, at the one write site, rather than at the signature.
    """
    async with session_factory() as session:
        session.add(
            IngestRun(
                id=run_id,
                started_at=started_at,
                trigger=trigger,
                budget_seconds=int(budget_seconds),
            )
        )
        await session.commit()


async def _close_ingest_run(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    run_id: uuid.UUID,
    finished_at: datetime,
    counters: Mapping[str, int],
    capture_lag_p50_seconds: int | None,
    capture_lag_p95_seconds: int | None,
) -> None:
    """Close the row `_open_ingest_run` inserted, with `finished_at` and every counter — see the
    module docstring for why this only ever runs once every stage that started has finished, never
    from a handler that also has to decide whether a stage raised.
    """
    async with session_factory() as session:
        await session.execute(
            update(IngestRun)
            .where(IngestRun.id == run_id)
            .values(
                finished_at=finished_at,
                capture_lag_p50_seconds=capture_lag_p50_seconds,
                capture_lag_p95_seconds=capture_lag_p95_seconds,
                **counters,
            )
        )
        await session.commit()


#: `alerts.kind` for T059a's aggregate sweep (`AlertKind.DEADLINE_BREACH` in
#: `packages/storage/src/aoe2stats_storage/models.py`), named as a plain string for the same reason
#: `capture.py`'s own alert-kind constants are: `AlertSink.write` (`aoe2stats_core.alerting`) takes
#: a plain `str`, so nothing here needs to import the enum merely to spell one of its members.
_DEADLINE_BREACH_ALERT_KIND = "deadline_breach"

#: Severity 1, never 2: `deadline_breach` is the second of the two kinds meaning a replay is gone or
#: is about to be (constitution I) — see this module's own docstring and `capture.py`'s
#: `EXPIRED_CAPTURE_ALERT_SEVERITY` for the sibling alert this one is deliberately not the same as.
_DEADLINE_BREACH_ALERT_SEVERITY = 1

#: `replay_captures.status` values a capture is already resolved under — `deadline_breach` must
#: never fire for one of these, however far past its own `capture_deadline_at` it now sits (FR-025,
#: T059a's own task text: "neither `stored`, `unavailable` nor `quarantined`").
#:
#: T059b adds `EXPIRED` and `FAILED`: both are terminal — nothing in this codebase ever moves a row
#: out of either — and both sit permanently past their own `capture_deadline_at` by construction (an
#: `expired` capture was already past its deadline by the time `_classify_not_found`, T056, closed
#: it that way; `failed` only follows exhausting `_MAX_ATTEMPTS`, T057). Leaving them out of this
#: tuple meant every cycle re-swept the same terminal loss forever and inserted a fresh severity-1
#: row for it every time — the row was never wrong, but a loss already reported once, by
#: `expired_capture` (T056) for `expired` or by the run's own `failed_total` counter for `failed`,
#: is not a second incident. `scripts/checks/capture_audit.py`'s `_RESOLVED_STATUSES` mirrors this
#: tuple exactly — see that constant's own comment — and must be kept in sync by hand for the same
#: reason `_nearest_rank` is: that script deliberately sits outside the uv workspace and does not
#: import this module.
_DEADLINE_BREACH_EXCLUDED_STATUSES = (
    CaptureStatus.STORED,
    CaptureStatus.UNAVAILABLE,
    CaptureStatus.QUARANTINED,
    CaptureStatus.EXPIRED,
    CaptureStatus.FAILED,
)


class _AlertSink:
    """The `AlertSink` (`aoe2stats_core.alerting`) this module's own `raise_alert` call writes
    through — structurally identical to `capture.py`'s own `_DatabaseAlertSink`, and deliberately
    not imported from there: `capture.py` also imports `aoe2stats_providers` at module scope for
    its `ReplayProvider` Protocol, a dependency this module has no other reason to carry and that
    `api/cron/ingest.py`'s own module-scope `from aoe2stats_ingester.run import run_once` would
    then drag into a plain `uv sync --no-dev` install (`tests/architecture/
    test_deployment_install.py`, T014d). This class's only job is the same one line
    `_DatabaseAlertSink.write` does — insert one `alerts` row through `session_factory` — so the
    duplication is a handful of lines, not a second implementation of any real behaviour.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def write(
        self,
        *,
        kind: str,
        severity: int,
        detail: Mapping[str, Any] | None,
        ingest_run_id: uuid.UUID | None,
    ) -> AlertRecord:
        row = AlertRow(
            id=uuid.uuid4(),
            kind=kind,
            severity=severity,
            detail=dict(detail) if detail is not None else None,
            ingest_run_id=ingest_run_id,
        )
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return AlertRecord(
                id=row.id,
                kind=row.kind,
                severity=row.severity,
                detail=row.detail,
                raised_at=row.raised_at,
                ingest_run_id=row.ingest_run_id,
                acknowledged_at=row.acknowledged_at,
            )

    async def unacknowledged_severity_one(self) -> list[AlertRecord]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(AlertRow).where(AlertRow.severity == 1, AlertRow.acknowledged_at.is_(None))
            )
            rows = result.scalars().all()
        return [
            AlertRecord(
                id=row.id,
                kind=row.kind,
                severity=row.severity,
                detail=row.detail,
                raised_at=row.raised_at,
                ingest_run_id=row.ingest_run_id,
                acknowledged_at=row.acknowledged_at,
            )
            for row in rows
        ]


async def _already_named_capture_ids(
    session_factory: async_sessionmaker[AsyncSession],
) -> set[str]:
    """T059b's suppression rule, its read half: the union of `capture_ids` carried by every
    unacknowledged `deadline_breach` row that already exists.

    Filtered to `acknowledged_at IS NULL` on purpose, and this is the whole rule: a capture named
    only by an *acknowledged* alert is not suppressed, because an operator acknowledging a `1`
    row is the explicit "seen, will follow up" signal FR-025 exists for — an unresolved breach must
    surface again the next cycle, not stay silent forever because someone once looked at it. A
    capture named only by an unacknowledged one is exactly the flood T059b closes: `capture_ids` is
    already the sweep's own record of what it raised for, so re-reading it here needs no new column
    and no new table.
    """
    async with session_factory() as session:
        result = await session.execute(
            select(AlertRow.detail).where(
                AlertRow.kind == _DEADLINE_BREACH_ALERT_KIND,
                AlertRow.acknowledged_at.is_(None),
            )
        )
        details = result.scalars().all()

    already_named: set[str] = set()
    for detail in details:
        if detail:
            already_named.update(detail.get("capture_ids", []))
    return already_named


async def _raise_deadline_breach_alert(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    run_id: uuid.UUID,
    deadline_reference: datetime,
) -> int:
    """FR-025/T059a: one aggregate severity-1 `deadline_breach` row, carrying every offending
    capture's id in `detail`, for every `replay_captures` row whose `capture_deadline_at` has
    already passed `deadline_reference` and whose `status` is none of
    `_DEADLINE_BREACH_EXCLUDED_STATUSES` — never one row per capture, which would bury the alert a
    backlog is supposed to surface (see the module docstring's T059a paragraph).

    This fires at the internal 21-day `capture_deadline_at`, not at the source's own ~31-day
    retention expiry `capture.py`'s `_classify_not_found` (T056) already raises `expired_capture`
    against — a different kind, at a different time, with roughly ten days still left to act by the
    time this one fires.

    **T059b — suppressed, not merely repeated.** The sweep above re-runs every cycle and, before
    this addition, inserted a fresh row for whatever it found every time, with no memory of what it
    had already raised. Two terminal statuses aside (`_DEADLINE_BREACH_EXCLUDED_STATUSES`), that is
    unbounded: acknowledging today's row is answered by tomorrow's, and `alert_audit.py`'s nightly
    gate can never be returned to green by any action short of deleting rows. The fix compares the
    current offending set against `_already_named_capture_ids` — every id already carried by an
    *unacknowledged* `deadline_breach` row — and raises nothing new when the current set is already
    a subset of that: nothing about this run's own findings is news. It still raises when the
    offending set has *grown* (a new capture past its own deadline is a new incident, whatever else
    is still open) and again once a human has acknowledged the prior alert and the breach is still
    unresolved (acknowledging removes it from `_already_named_capture_ids`'s query, by construction
    — see that function's own docstring). Both are the entire point of the alert; a suppression rule
    that swallowed either would be worse than the flood it replaces.

    Returns `1` if a new alert was raised, `0` if there was nothing to raise it for or everything
    found was already named by an unacknowledged alert — the amount `run_once` folds into its own
    still-open `ingest_runs` row's `alerts_raised`, so a suppressed run's counter says truthfully
    that this run raised nothing, never that it raised the alert it merely re-found.
    """
    async with session_factory() as session:
        result = await session.execute(
            select(ReplayCapture.id).where(
                ReplayCapture.capture_deadline_at < deadline_reference,
                ReplayCapture.status.not_in(_DEADLINE_BREACH_EXCLUDED_STATUSES),
            )
        )
        offending_ids = [row[0] for row in result.all()]

    if not offending_ids:
        return 0

    current_ids = {str(capture_id) for capture_id in offending_ids}
    already_named = await _already_named_capture_ids(session_factory)
    if current_ids <= already_named:
        return 0

    await raise_alert(
        _AlertSink(session_factory),
        _DEADLINE_BREACH_ALERT_KIND,
        _DEADLINE_BREACH_ALERT_SEVERITY,
        {"capture_ids": [str(capture_id) for capture_id in offending_ids]},
        run_id=run_id,
    )
    return 1


def _default_session_factory() -> async_sessionmaker[AsyncSession]:
    """`run_once`'s own database access when no caller supplies `session_factory` — see the module
    docstring's paragraph on why this is the one deliberate exception to reading a setting from the
    environment inside this function.
    """
    database_url = os.environ.get(_DATABASE_URL_ENV)
    if not database_url:
        raise RuntimeError(
            f"run_once() needs either session_factory= or {_DATABASE_URL_ENV} set in the "
            "environment to reach its own ingest_runs bookkeeping."
        )
    return build_session_factory(build_engine(database_url))


@dataclass(frozen=True, slots=True)
class RunReport:
    """What one call to `run_once` produced — the in-process shape both entrypoints render
    directly as their HTTP response, and a near-mirror of the `ingest_runs` row `run_once` itself
    opens and closes (`ingest_run_id` is that row's own primary key, so a caller — or a human
    reading a response body — can go straight from this report to the row FR-024 asks for).
    """

    trigger: str
    budget_seconds: float
    started_at: datetime
    finished_at: datetime
    stages_completed: tuple[str, ...]
    stopped_early: bool
    stage_reports: Mapping[str, Mapping[str, Any]]
    ingest_run_id: uuid.UUID

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
            "ingest_run_id": str(self.ingest_run_id),
        }


async def run_once(
    budget_seconds: float,
    *,
    trigger: str = "cron",
    stages: Sequence[Stage] = DEFAULT_STAGES,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> RunReport:
    """Run one ingest cycle, honouring `budget_seconds` between stages and never mid-stage.

    `budget_seconds` is always `Settings.ingest_run_budget_seconds` in production. `trigger`
    records which entrypoint asked for the cycle (`"cron"` for the Vercel schedule, `"local"` for
    the quickstart trigger, `"worker"` for the phase-2 loop). See the module docstring for
    `session_factory` (this function's own database access) and for why `stages` still defaults to
    empty in production today.

    Each stage is only ever *started* while budget remains; once one is running it is never
    interrupted mid-stage, exactly as `iter_within_budget` never interrupts mid-item within one.
    A stage that starts late in the budget can still overrun it slightly — that is the price of
    never leaving a claim, a download or an upload half-done, and is why the reclaim path (T055)
    exists for the one row a hard process kill can still catch.

    Nothing here catches an exception a stage raises: it propagates out of this call exactly as it
    would have before this task, leaving the `ingest_runs` row this call opened exactly as open as
    the module docstring describes — a fact worth having, never papered over with a `finished_at`
    the cycle never actually reached.
    """
    resolved_session_factory = session_factory or _default_session_factory()

    started_at = _now()
    budget = Budget(seconds=budget_seconds)
    run_id = uuid.uuid4()
    await _open_ingest_run(
        resolved_session_factory,
        run_id=run_id,
        started_at=started_at,
        trigger=trigger,
        budget_seconds=budget_seconds,
    )

    stages_completed: list[str] = []
    stage_reports: dict[str, Mapping[str, Any]] = {}
    stopped_early = False

    for stage in stages:
        if budget.expired:
            stopped_early = True
            break
        # T059c: bind this run's own id onto every stage that carries alerts of its own
        # (`RunScoped`, currently `CaptureDrain` alone) before it ever runs, so a `rate_limited`,
        # `validation_failed` or `expired_capture` alert raised inside this call lands with a real
        # `ingest_run_id` rather than the `None` every one of them used to be handed — see
        # `RunScoped`'s own docstring for why this is a per-call bind rather than a constructor
        # argument or a widening of `Stage.__call__` itself.
        if isinstance(stage, RunScoped):
            stage.bind_run(run_id)
        stage_reports[stage.name] = await stage(budget)
        stages_completed.append(stage.name)

    finished_at = _now()
    counters = _aggregate_counters(stage_reports)
    # T059a: the deadline sweep runs after the drain, against this same still-open row, so its
    # alert (if any) carries a real `ingest_run_id` and is counted in that row's `alerts_raised` —
    # see the module docstring's T059a paragraph and `_raise_deadline_breach_alert`'s own docstring.
    counters["alerts_raised"] += await _raise_deadline_breach_alert(
        resolved_session_factory, run_id=run_id, deadline_reference=finished_at
    )
    capture_lag_p50_seconds, capture_lag_p95_seconds = await _capture_lag_seconds(
        resolved_session_factory, window_start=started_at, window_end=finished_at
    )
    await _close_ingest_run(
        resolved_session_factory,
        run_id=run_id,
        finished_at=finished_at,
        counters=counters,
        capture_lag_p50_seconds=capture_lag_p50_seconds,
        capture_lag_p95_seconds=capture_lag_p95_seconds,
    )

    return RunReport(
        trigger=trigger,
        budget_seconds=budget_seconds,
        started_at=started_at,
        finished_at=finished_at,
        stages_completed=tuple(stages_completed),
        stopped_early=stopped_early,
        stage_reports=stage_reports,
        ingest_run_id=run_id,
    )
