#!/usr/bin/env python3
"""Nightly cron-liveness check (T061, quickstart scenario 11, FR-024, SC-007).

The phase-1 stack has no always-on process (`docs/adr/0002-hosting.md`): a Vercel cron that stops
firing has no other way to announce it has stopped, so this is checked from outside. `run_once`
(T059) inserts an `ingest_runs` row *before* any work starts — see that module's own docstring — so
"the newest row's `started_at` is recent" is a fact this script can read without ever running inside
the ingester itself.

SC-007 fixes the budget at 30 hours directly; unlike `CAPTURE_BUDGET_DAYS` (`capture_audit.py`),
there is no environment variable behind this number to read instead — `data-model.md`'s own
`ingest_runs` section and this file's test (`tests/test_cron_liveness.py`, T048) both state "30
hours" as the number SC-007 sets, not a knob a deployment can tune.

**T061b — the second signal.** `run.py`'s own module docstring names two signals this check is
meant to read: "the row's absence means nothing ran at all, its open `finished_at` means something
did and did not finish." Until this task only the first was read: a cron that fires on schedule and
dies in a stage every single cycle (T050a's exact symptom — one malformed provider entry, for
instance) writes a fresh `started_at` every night and this check printed OK and exited 0 for as
long as the failure lasted, which is SC-007's own failure mode arriving through the front door.
`is_stalled` below is the fix: a newest row that is still open (`finished_at is None`) and has been
open for longer than a completed run could plausibly need is failed on its own terms, independently
of how recent `started_at` is.

Usage:  uv run scripts/checks/cron_liveness.py
Exit:   0 if the newest `ingest_runs` row started within the last 30 hours *and*, if still open, has
        not been open for implausibly long given `INGEST_RUN_BUDGET_SECONDS`; 1 otherwise (including
        "no row has ever been recorded").
"""

from __future__ import annotations

import asyncio
import enum
import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_storage.models import IngestRun
from aoe2stats_storage.repositories.base import build_engine, build_session_factory

#: SC-007: a cron that has stopped firing must be detected within this many hours of the last run
#: that actually started. Quickstart scenario 11 and `tests/test_cron_liveness.py` (T048) both
#: exercise this exact number: a run backdated by 31 hours — one hour past this budget — must fail.
LIVENESS_BUDGET_HOURS = 30

_DATABASE_URL_ENV = "DATABASE_URL"

_INGEST_RUN_BUDGET_SECONDS_ENV = "INGEST_RUN_BUDGET_SECONDS"

#: `.env.example`'s own default. `Settings.ingest_run_budget_seconds` (`apps/api/src/
#: aoe2stats_api/settings.py`) has no default of its own — it is a required field there — but this
#: script is not `apps/api` and reads the environment directly, the same way it already reads
#: `DATABASE_URL`; unlike that one, a missing `INGEST_RUN_BUDGET_SECONDS` should not make the check
#: refuse to run, so it falls back to the value every `.env.example` deployment starts from.
_DEFAULT_INGEST_RUN_BUDGET_SECONDS = 240.0

#: `run_once`'s own docstring (`apps/ingester/src/aoe2stats_ingester/run.py`): "a stage that starts
#: late in the budget can still overrun it slightly ... the price of never leaving a claim, a
#: download or an upload half-done." A run still inside `INGEST_RUN_BUDGET_SECONDS` is simply in
#: progress and is evidence of nothing; a bare equality would fail it the instant the budget ticks
#: over even though `iter_within_budget` (`budget.py`) never interrupts mid-item. Doubling the
#: budget before an open row counts as stalled gives room for exactly one such late-started item to
#: finish without being mistaken for a dead run, while staying two orders of magnitude below
#: `LIVENESS_BUDGET_HOURS` so a run that really did die in a stage is still caught the same night
#: rather than only after 30 h have passed.
_STALLED_RUN_BUDGET_MULTIPLIER = 2


class LivenessStatus(enum.Enum):
    """The three states `check_liveness` can find the newest `ingest_runs` row in.

    Not a bare pass/fail: `LIVE` is the only passing state, but the two failing ones send an
    operator to different places (T061b) — `STALE` means the cron has stopped firing, or every row
    has been lost; `STALLED` means it is firing on schedule but every run is dying before it
    finishes. `_run()` below is the one place that turns a member of this enum into an exit code
    and a message.
    """

    LIVE = "live"
    STALE = "stale"
    STALLED = "stalled"


def is_live(started_at: datetime | None, *, now: datetime) -> bool:
    """True when `started_at` is within `LIVENESS_BUDGET_HOURS` of `now`.

    `None` — no run has ever been recorded — is never live: `data-model.md`'s own words, "the
    absence of a row is the signal," and the first cycle in a fresh environment must show up as a
    genuine failure rather than an exception a caller has to remember to special-case.
    """
    if started_at is None:
        return False
    return now - started_at <= timedelta(hours=LIVENESS_BUDGET_HOURS)


def is_stalled(
    started_at: datetime,
    finished_at: datetime | None,
    *,
    now: datetime,
    run_budget_seconds: float,
) -> bool:
    """True when the newest row is still open and has already been open for longer than a
    completed cycle could plausibly need — T061b's second signal.

    Never true for a closed row (`finished_at` set): a run that finished, however long ago, already
    answered the question this function exists for. That is deliberate rather than an oversight —
    `is_live` above is the separate, 30-hour question of whether the cron is still firing at all,
    and a row that finished cleanly a while back says nothing about tonight's cycle either way; it
    is `check_liveness` below, reading `started_at` through `is_live`, that catches a cron gone
    quiet entirely.
    """
    if finished_at is not None:
        return False
    threshold = timedelta(seconds=run_budget_seconds * _STALLED_RUN_BUDGET_MULTIPLIER)
    return now - started_at > threshold


async def check_liveness(
    session: AsyncSession, *, now: datetime, run_budget_seconds: float
) -> LivenessStatus:
    """Read the newest `ingest_runs` row by `started_at` and classify it into a `LivenessStatus`.

    `is_live` is checked before `is_stalled`, not after: a row already past `LIVENESS_BUDGET_HOURS`
    is unambiguously "the cron stopped firing" regardless of whether it ever closed, and that is
    the pre-existing `STALE` classification (and message) this task leaves untouched. `is_stalled`
    only ever gets a say once `is_live` has already passed — a row recent enough by `started_at`
    that the old, `started_at`-only check would have called it healthy, but that has nonetheless
    sat open for multiples of its own `run_budget_seconds`. That is T061b's actual case: a cron
    that fires on schedule (so `started_at` looks fine every night) and dies in a stage every
    cycle, which the pre-existing check alone could never catch.

    Only the newest row ever decides the outcome, unchanged by this task: a stale row sitting
    alongside a fresh one, or a fresh one sitting alongside a stale one, never changes it —
    `data-model.md`'s own words, "only the single newest row's own age decides it." An older row
    that completed fine is no exception: it says nothing about *tonight's* cycle, and a live system
    re-proves itself every run, not once. A newest row that is itself open and stalled is a real
    failure even if an older row closed cleanly.
    """
    result = await session.execute(
        select(IngestRun.started_at, IngestRun.finished_at)
        .order_by(IngestRun.started_at.desc())
        .limit(1)
    )
    row = result.first()
    if row is None:
        return LivenessStatus.STALE

    started_at, finished_at = row
    if not is_live(started_at, now=now):
        return LivenessStatus.STALE
    if is_stalled(started_at, finished_at, now=now, run_budget_seconds=run_budget_seconds):
        return LivenessStatus.STALLED
    return LivenessStatus.LIVE


def _read_run_budget_seconds() -> float:
    """`INGEST_RUN_BUDGET_SECONDS`, read the way this script already reads `DATABASE_URL` — from
    the environment directly, not from `Settings` (`apps/api`, which `scripts/checks` cannot
    import; `capture_audit.py`'s `_CAPTURE_BUDGET_DAYS_ENV` reads the same way). Falls back to
    `_DEFAULT_INGEST_RUN_BUDGET_SECONDS` rather than refusing to run, since — unlike `DATABASE_URL`
    — a missing value here still has a sane number behind it.
    """
    raw = os.environ.get(_INGEST_RUN_BUDGET_SECONDS_ENV)
    if raw is None:
        return _DEFAULT_INGEST_RUN_BUDGET_SECONDS
    return float(raw)


async def _run() -> int:
    database_url = os.environ.get(_DATABASE_URL_ENV)
    if not database_url:
        print(f"cron-liveness: {_DATABASE_URL_ENV} is not set; nothing to check against.")
        return 1

    run_budget_seconds = _read_run_budget_seconds()
    session_factory = build_session_factory(build_engine(database_url))
    now = datetime.now(UTC)
    async with session_factory() as session:
        status = await check_liveness(session, now=now, run_budget_seconds=run_budget_seconds)

    if status is LivenessStatus.LIVE:
        print(
            f"cron-liveness: OK — the newest ingest_runs row started within "
            f"{LIVENESS_BUDGET_HOURS} h."
        )
        return 0

    if status is LivenessStatus.STALLED:
        stall_threshold = run_budget_seconds * _STALLED_RUN_BUDGET_MULTIPLIER
        print(
            "cron-liveness: FAIL — the newest ingest_runs row is still open (no finished_at) and "
            f"has been for longer than {stall_threshold:.0f}s "
            f"(INGEST_RUN_BUDGET_SECONDS={run_budget_seconds:.0f} x "
            f"{_STALLED_RUN_BUDGET_MULTIPLIER}). The cron fires and every run dies before it "
            "finishes — see T050a for the ordinary way this happens (one malformed provider "
            "entry killing an entire cycle) and run.py's module docstring for why the row is left "
            "open rather than never written."
        )
        return 1

    print(
        f"cron-liveness: FAIL — no ingest_runs row has started within the last "
        f"{LIVENESS_BUDGET_HOURS} h (SC-007). The cron has stopped firing, or every row has been "
        "lost. See docs/adr/0002-hosting.md for the failure mode this check exists for."
    )
    return 1


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
