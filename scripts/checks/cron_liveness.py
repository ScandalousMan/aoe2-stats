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

Usage:  uv run scripts/checks/cron_liveness.py
Exit:   0 if the newest `ingest_runs` row started within the last 30 hours, 1 otherwise (including
        "no row has ever been recorded").
"""

from __future__ import annotations

import asyncio
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


def is_live(started_at: datetime | None, *, now: datetime) -> bool:
    """True when `started_at` is within `LIVENESS_BUDGET_HOURS` of `now`.

    `None` — no run has ever been recorded — is never live: `data-model.md`'s own words, "the
    absence of a row is the signal," and the first cycle in a fresh environment must show up as a
    genuine failure rather than an exception a caller has to remember to special-case.
    """
    if started_at is None:
        return False
    return now - started_at <= timedelta(hours=LIVENESS_BUDGET_HOURS)


async def check_liveness(session: AsyncSession, *, now: datetime) -> bool:
    """Read the newest `ingest_runs` row by `started_at` and apply `is_live` to it.

    An empty table reads as `None`, exactly what `is_live` already treats as not live — a stale row
    sitting alongside a fresh one, or a fresh one sitting alongside a stale one, never changes the
    outcome: only the single newest row's own age decides it.
    """
    result = await session.execute(
        select(IngestRun.started_at).order_by(IngestRun.started_at.desc()).limit(1)
    )
    started_at = result.scalar_one_or_none()
    return is_live(started_at, now=now)


async def _run() -> int:
    database_url = os.environ.get(_DATABASE_URL_ENV)
    if not database_url:
        print(f"cron-liveness: {_DATABASE_URL_ENV} is not set; nothing to check against.")
        return 1

    session_factory = build_session_factory(build_engine(database_url))
    now = datetime.now(UTC)
    async with session_factory() as session:
        live = await check_liveness(session, now=now)

    if live:
        print(
            f"cron-liveness: OK — the newest ingest_runs row started within "
            f"{LIVENESS_BUDGET_HOURS} h."
        )
        return 0

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
