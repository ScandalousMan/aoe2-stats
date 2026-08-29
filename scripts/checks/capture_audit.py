#!/usr/bin/env python3
"""Nightly capture audit (T061): three assertions over `replay_captures` and `ingest_runs`,
none of them redundant with the other two or with `alert_audit.py`.

- **`expired_total` sums to `0` over a trailing window** (constitution I, `data-model.md`'s
  `ingest_runs` section: "expected to be permanently zero, and the nightly audit asserts exactly
  that"). Originally summed across every `ingest_runs` row ever closed, full stop. Changed
  2026-08-29: the `aoe.ms` 301 outage (fixed by PR #17) left a 78-item capture backlog, and when it
  drained on 2026-08-28 the source had already passed retention for 56 of those 78
  (`http_status = 404`, `last_error = "replay never became available at source before
  capture_deadline_at (404)"`; the other 22 stored fine on HTTP 200). Production now carries a
  permanent, historical 56 that a lifetime sum can never return to zero — the check went red and
  stays red regardless of whether capture is healthy today, which means it can never again report a
  *new* loss: red-to-red teaches nobody anything. Windowed to `_EXPIRED_CAPTURE_WINDOW_DAYS` (below)
  instead: a genuinely new expiry still fails the check, and an old, already-investigated one
  eventually ages out on its own rather than being carried forever.

  Filtered on `finished_at`, not `started_at`: `expired_total` is written exactly once, by
  `_close_ingest_run`, at the moment a run closes (`run.py`'s own module docstring draws the same
  distinction: "the row's absence means nothing ran at all, its open `finished_at` means something
  did and did not finish") — an open row's counter is not final yet, and `finished_at IS NULL`
  already drops it out of any `>=` window comparison with no separate clause needed. A long
  backlog-drain run — exactly what produced the 56 above — can `start` long before the window and
  still `finish` inside it; anchoring on `started_at` would drop the very run this change exists to
  keep visible.

  `_EXPIRED_CAPTURE_WINDOW_DAYS` is deliberately **not** `_TRAILING_WINDOW_DAYS` (SC-002's lag
  target, seven days, below), even though reusing it is tempting: the two answer different
  questions that happen to share the word "recent". SC-002 is a service-level cadence target,
  measured over newly discovered captures; this window asks "has anything been lost lately" and has
  nothing to do with lag. Sharing one constant would make a future retune of SC-002's target
  silently retune this incident window too. `_EXPIRED_CAPTURE_WINDOW_DAYS` is set to 3: this audit
  runs once a night (`.github/workflows/nightly.yml`, `cron: "0 3 * * *"`), so 3 days survives the
  workflow itself skipping a run or two — a GitHub Actions outage, a temporarily disabled
  schedule — without holding a stale, already-handled entry anywhere near as long as a full week.
- **No capture pending past its own deadline.** The same condition `apps/ingester/src/
  aoe2stats_ingester/run.py`'s `_raise_deadline_breach_alert` (T059a/T059b) raises `deadline_breach`
  against — every `replay_captures` row whose `capture_deadline_at` (`completed_at +
  CAPTURE_BUDGET_DAYS`, computed once at insert by `discover.py`) has passed, and whose `status` is
  none of `stored`/`unavailable`/`quarantined`/`expired`/`failed` (the last two are terminal — see
  `_RESOLVED_STATUSES`'s own comment — and were alerted once already, by `expired_capture` or by
  their own terminal counter) — computed independently here, straight from the table, rather than
  by reading `alerts`. That independence is the entire point (see the module docstring's overlap
  note below): this assertion still catches the breach even if the ingester never ran a single
  cycle to raise the alert in the first place. `CAPTURE_BUDGET_DAYS` itself is never restated here
  as a literal — `capture_deadline_at` already carries it, computed once on insert, and the
  informational message below reads the same environment variable `Settings` does
  (`CAPTURE_BUDGET_DAYS`) rather than a second hard-coded threshold.
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

That same division of labour is what makes the `expired_total` windowing above safe rather than
merely convenient. Constitution I's corollary says `expired_total` is expected to stay at zero
*permanently*, and moving this script's own check to a trailing window is a genuine weakening of
that guarantee: an expiry from eight days ago that nobody investigated would now silently age out of
`expired_total`'s check with nothing else here to catch it. The mitigation is not new, only newly
load-bearing: `EXPIRED_CAPTURE` (T056) is a severity-1 `alerts` row, and `alert_audit.py` fails on
*any* unacknowledged severity-1 row — with no window of its own. That row stays visible, and the
check that reads it stays red, until a human acknowledges it, and constitution I permits
acknowledging "only after investigating, never before". Put plainly, the two scripts now split
constitution I's guarantee cleanly in two: this script answers "is anything being lost **right
now**" and recovers on its own once a loss ages out of the window; `alert_audit.py` answers "has
every loss been **investigated**" and is durable — it clears only by a human acting on it, never by
the passage of time. Neither script owns both halves, and after this change the durable half of
constitution I's zero-loss guarantee lives in `alert_audit.py` alone.

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

#: The trailing window `expired_total` is summed over — a deliberately separate constant from
#: `_TRAILING_WINDOW_DAYS` above, not a reuse of it. See the module docstring's first bullet for
#: why the two must not share a number and why 3 (not 7) is the right size for this one.
_EXPIRED_CAPTURE_WINDOW_DAYS = 3

#: Mirrors `run.py`'s `_DEADLINE_BREACH_EXCLUDED_STATUSES` exactly (T059b keeps this comment true
#: after adding the two terminal statuses there — `EXPIRED` and `FAILED` — kept in sync by hand
#: since this script deliberately sits outside the uv workspace and does not import `run.py`): a
#: capture in one of these states has already been resolved one way or another and must never count
#: as pending, however far past its own `capture_deadline_at` it now sits.
_RESOLVED_STATUSES = (
    CaptureStatus.STORED,
    CaptureStatus.UNAVAILABLE,
    CaptureStatus.QUARANTINED,
    CaptureStatus.EXPIRED,
    CaptureStatus.FAILED,
)


def _nearest_rank(sorted_values: Sequence[int], fraction: float) -> int:
    """Verbatim copy of `run.py`'s own `_nearest_rank` — see this module's docstring for why it is
    copied rather than imported. The smallest value at or beyond the `ceil(fraction * n)`-th
    position (1-indexed) of an already-sorted, non-empty sequence.
    """
    rank = max(1, math.ceil(fraction * len(sorted_values)))
    return sorted_values[min(rank, len(sorted_values)) - 1]


async def expired_total(session: AsyncSession, *, window_start: datetime) -> int:
    """The sum of `ingest_runs.expired_total` across every row closed (`finished_at` non-null) at
    or after `window_start` — see the module docstring's first bullet for why this is windowed
    rather than lifetime, why `finished_at` rather than `started_at`, and why the boundary is
    inclusive (`>=`, matching `capture_lag_p95_seconds`'s own window bounds below). `0` when the
    table is empty, every row in the window has a `0` counter, or nothing closed in the window at
    all — `COALESCE` rather than a bare `SUM`, since Postgres returns `NULL` for a `SUM` over zero
    rows. `finished_at IS NULL` (a run still open) never matches `>= window_start`, so an
    unfinished run's not-yet-final counter is excluded without a separate clause.
    """
    result = await session.execute(
        select(func.coalesce(func.sum(IngestRun.expired_total), 0)).where(
            IngestRun.finished_at >= window_start
        )
    )
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
    lag_window_start = now - timedelta(days=_TRAILING_WINDOW_DAYS)
    expired_window_start = now - timedelta(days=_EXPIRED_CAPTURE_WINDOW_DAYS)

    async with session_factory() as session:
        total_expired = await expired_total(session, window_start=expired_window_start)
        overdue = await captures_pending_past_deadline(session, now=now)
        p95_seconds = await capture_lag_p95_seconds(
            session, window_start=lag_window_start, window_end=now
        )

    ok = True

    if total_expired == 0:
        print(
            "capture-audit: OK — expired_total is 0 over the trailing "
            f"{_EXPIRED_CAPTURE_WINDOW_DAYS} days of ingest_runs."
        )
    else:
        ok = False
        print(
            f"capture-audit: FAIL — expired_total sums to {total_expired} over the trailing "
            f"{_EXPIRED_CAPTURE_WINDOW_DAYS} days of ingest_runs. Constitution I: a lost replay is "
            "gone forever; see docs/risks.md. Any severity-1 EXPIRED_CAPTURE alert behind this "
            "stays visible in alert_audit.py until acknowledged, independently of this window."
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
