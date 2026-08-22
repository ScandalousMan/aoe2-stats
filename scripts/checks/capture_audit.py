#!/usr/bin/env python3
"""Nightly capture audit (T061): three assertions over `replay_captures` and `ingest_runs`,
none of them redundant with the other two or with `alert_audit.py`.

- **`expired_total == 0`** (constitution I, `data-model.md`'s `ingest_runs` section: "expected to
  be permanently zero, and the nightly audit asserts exactly that"). Summed across every
  `ingest_runs` row ever closed, not only the newest: a single non-zero cycle, even a stale one, is
  a replay that was lost and stays a fact worth catching regardless of how long ago it happened.
- **No capture pending past its own deadline.** The same condition `apps/ingester/src/
  aoe2stats_ingester/run.py`'s `_raise_deadline_breach_alert` (T059a) raises `deadline_breach`
  against — every `replay_captures` row whose `capture_deadline_at` (`completed_at +
  CAPTURE_BUDGET_DAYS`, computed once at insert by `discover.py`) has passed, and whose `status` is
  none of `stored`/`unavailable`/`quarantined` — computed independently here, straight from the
  table, rather than by reading `alerts`. That independence is the entire point (see the module
  docstring's overlap note below): this assertion still catches the breach even if the ingester
  never ran a single cycle to raise the alert in the first place. `CAPTURE_BUDGET_DAYS` itself is
  never restated here as a literal — `capture_deadline_at` already carries it, computed once on
  insert, and the informational message below reads the same environment variable `Settings`
  does (`CAPTURE_BUDGET_DAYS`) rather than a second hard-coded threshold.
- **SC-002's lag target**: p95 of `stored_at - completed_at`, over the trailing seven days, under
  48 hours — computed over *newly discovered* captures only (`first_seen_at` inside the trailing
  window), excluding any whose `first_seen_at` lands more than 48 h after its own `completed_at`:
  those were already old the moment this system first saw them (a 31-day backfill, T031a, or a
  reconciliation sweep catching up after an outage, T054a) and folding them in would report how far
  back a rescue reached rather than how fast the day-to-day cadence is. `run.py`'s own
  `_capture_lag_seconds` (T059) computes the identical measure at a different scope (one run's
  `[started_at, finished_at]` window there, a trailing seven days here) with the identical
  exclusion and the identical nearest-rank percentile (`_nearest_rank`) — copied here rather than
  imported, since `scripts/checks` is deliberately outside the uv workspace (plan.md) and does not
  reach into `apps/ingester`'s internals; kept in sync by hand, and any change to one warrants
  checking the other.

**Why the capture audit and the alert audit overlap by design** (T061's own task text): this script
never reads `alerts` at all, and `alert_audit.py` never reads `replay_captures`. A `deadline_breach`
alert nobody acknowledged is `alert_audit.py`'s job (T059a is why that alert exists in the first
place); a breach that occurred without the ingester ever running to raise it is this script's job.
Neither subsumes the other.

Usage:  uv run scripts/checks/capture_audit.py
Exit:   0 if all three assertions hold, 1 otherwise (every failure is reported, not only the first).
"""

from __future__ import annotations

import asyncio
import math
import os
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_storage.models import CaptureStatus, IngestRun, Match, ReplayCapture
from aoe2stats_storage.repositories.base import build_engine, build_session_factory

_DATABASE_URL_ENV = "DATABASE_URL"
_CAPTURE_BUDGET_DAYS_ENV = "CAPTURE_BUDGET_DAYS"

#: SC-002 / `run.py`'s own `_NEWLY_DISCOVERED_LAG_WINDOW_HOURS`: both the backfill-exclusion
#: threshold and the SLA target this script asserts against are the same 48 h — see the module
#: docstring's third bullet for why that is one number doing two jobs, not a coincidence.
_SC002_TARGET_HOURS = 48

#: The trailing window SC-002's lag target is measured over — distinct from `run.py`'s own
#: per-run window, and this script's own scope alone.
_TRAILING_WINDOW_DAYS = 7

#: Mirrors `run.py`'s `_DEADLINE_BREACH_EXCLUDED_STATUSES` exactly: a capture in one of these
#: states has already been resolved one way or another and must never count as pending, however
#: far past its own `capture_deadline_at` it now sits.
_RESOLVED_STATUSES = (CaptureStatus.STORED, CaptureStatus.UNAVAILABLE, CaptureStatus.QUARANTINED)


def _nearest_rank(sorted_values: Sequence[int], fraction: float) -> int:
    """Verbatim copy of `run.py`'s own `_nearest_rank` — see this module's docstring for why it is
    copied rather than imported. The smallest value at or beyond the `ceil(fraction * n)`-th
    position (1-indexed) of an already-sorted, non-empty sequence.
    """
    rank = max(1, math.ceil(fraction * len(sorted_values)))
    return sorted_values[min(rank, len(sorted_values)) - 1]


async def expired_total(session: AsyncSession) -> int:
    """The sum of `ingest_runs.expired_total` across every row ever closed. `0` when the table is
    empty or every row's counter is `0` — `COALESCE` rather than a bare `SUM`, since Postgres
    returns `NULL` for a `SUM` over zero rows.
    """
    result = await session.execute(select(func.coalesce(func.sum(IngestRun.expired_total), 0)))
    return int(result.scalar_one())


async def captures_pending_past_deadline(
    session: AsyncSession, *, now: datetime
) -> list[ReplayCapture]:
    """Every `replay_captures` row whose `capture_deadline_at` has already passed `now` and whose
    `status` is not one of `_RESOLVED_STATUSES` — the same condition `run.py`'s
    `_raise_deadline_breach_alert` sweeps, computed independently against the table itself so this
    assertion holds even if the ingester never ran a cycle to raise that alert.
    """
    result = await session.execute(
        select(ReplayCapture).where(
            ReplayCapture.capture_deadline_at < now,
            ReplayCapture.status.not_in(_RESOLVED_STATUSES),
        )
    )
    return list(result.scalars().all())


async def capture_lag_p95_seconds(
    session: AsyncSession, *, window_start: datetime, window_end: datetime
) -> int | None:
    """SC-002's p95 lag, over captures newly discovered in `[window_start, window_end]` and
    already stored by the time this runs — `None` when there is nothing to measure. See the module
    docstring's third bullet for the exclusion this mirrors from `run.py`'s `_capture_lag_seconds`.
    """
    cutoff = timedelta(hours=_SC002_TARGET_HOURS)
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
        return None

    lags = sorted(
        int((stored_at - completed_at).total_seconds()) for stored_at, completed_at in rows
    )
    return _nearest_rank(lags, 0.95)


async def _run() -> int:
    database_url = os.environ.get(_DATABASE_URL_ENV)
    if not database_url:
        print(f"capture-audit: {_DATABASE_URL_ENV} is not set; nothing to check against.")
        return 1

    session_factory = build_session_factory(build_engine(database_url))
    now = datetime.now(UTC)
    window_start = now - timedelta(days=_TRAILING_WINDOW_DAYS)

    async with session_factory() as session:
        total_expired = await expired_total(session)
        overdue = await captures_pending_past_deadline(session, now=now)
        p95_seconds = await capture_lag_p95_seconds(
            session, window_start=window_start, window_end=now
        )

    ok = True

    if total_expired == 0:
        print("capture-audit: OK — expired_total is 0 across every ingest_runs row.")
    else:
        ok = False
        print(
            f"capture-audit: FAIL — expired_total sums to {total_expired} across ingest_runs. "
            "Constitution I: this is expected to be permanently zero. See docs/risks.md."
        )

    if not overdue:
        budget_days = os.environ.get(_CAPTURE_BUDGET_DAYS_ENV, "unset")
        print(
            f"capture-audit: OK — no capture is pending past its capture_deadline_at "
            f"(CAPTURE_BUDGET_DAYS={budget_days})."
        )
    else:
        ok = False
        offending_ids = ", ".join(str(capture.id) for capture in overdue)
        print(
            f"capture-audit: FAIL — {len(overdue)} capture(s) are past their capture_deadline_at "
            f"and still unresolved: {offending_ids}."
        )

    if p95_seconds is None:
        print(
            "capture-audit: OK — no newly discovered, stored capture in the trailing "
            f"{_TRAILING_WINDOW_DAYS} days to measure SC-002's lag against."
        )
    elif p95_seconds <= _SC002_TARGET_HOURS * 3600:
        print(
            f"capture-audit: OK — SC-002 p95 capture lag is {p95_seconds / 3600:.2f} h "
            f"(under {_SC002_TARGET_HOURS} h)."
        )
    else:
        ok = False
        print(
            f"capture-audit: FAIL — SC-002 p95 capture lag is {p95_seconds / 3600:.2f} h, over "
            f"the {_SC002_TARGET_HOURS} h target."
        )

    return 0 if ok else 1


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
