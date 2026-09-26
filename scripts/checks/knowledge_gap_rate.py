#!/usr/bin/env python3
"""FR-039's aggregate gap report, printed (T652).

`analysis_knowledge_gaps` **is** the aggregate (`specs/006-replay-analysis-foundations/
contracts/knowledge-base.md`, "Gaps"/"Aggregate") — there is no per-run quarantine-style counter
alongside it, because the analyzer has no run to attach one to. This script is the one place that
prints what the table already holds: a count of gaps recorded in a trailing window, grouped by
game build, cause and severity, so that a pattern of gaps a game patch introduced is visible as a
rate rather than discovered one analysis at a time.

This is a **report**, not a gate: unlike `alert_audit.py` and `capture_audit.py`, it never asserts
that the count should be zero — a non-zero rate of `informational` gaps is an expected, permanent
fact about the game (`docs/data-sources.md`'s own coverage measurements), not an incident. It
exits `1` only when it cannot even ask the question (`DATABASE_URL` unset), the same convention
`alert_audit.py`/`capture_audit.py` both use for that one case.

**Dead code until T663.** `analysis_knowledge_gaps` is not created by any applied migration yet —
T663 adds it. Running this script against a database at any revision before T663's would fail with
`UndefinedTable`, which is exactly why nothing calls this script yet: it is wired into
`.github/workflows/nightly.yml` by T663, not by this task (see `KnowledgeGapsRepository`'s own
module docstring for the fuller reasoning).

Usage:  uv run scripts/checks/knowledge_gap_rate.py [--window-days N]
Exit:   0 once the report has been printed (or nothing was ever reachable to ask); 1 only when
        DATABASE_URL is not set at all.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from datetime import UTC, datetime, timedelta

from aoe2stats_storage.repositories.base import build_engine, build_session_factory
from aoe2stats_storage.repositories.knowledge_gaps import GapRateRow, KnowledgeGapsRepository

_DATABASE_URL_ENV = "DATABASE_URL"

#: A month is long enough to show a slow-building pattern (a patch shipped a few weeks ago) without
#: the report growing unbounded the way a lifetime sum would — the same reasoning `capture_audit.py`
#: gives for windowing `expired_total` rather than summing forever.
_DEFAULT_WINDOW_DAYS = 30


def render_report(rows: list[GapRateRow], *, window_start: datetime, window_end: datetime) -> str:
    """The human-readable report `_run` prints — pulled out so a test can assert its shape
    without a database, the same split `publication_delay.py`'s own `render_summary` makes for
    its report."""
    header = (
        f"knowledge-gap-rate: {window_start.isoformat()} to {window_end.isoformat()} "
        f"({len(rows)} group(s))"
    )
    if not rows:
        return f"{header}\n  no gap recorded in this window."

    total = sum(row.count for row in rows)
    lines = [header, f"  total gaps: {total}"]
    for row in rows:
        lines.append(
            f"  build={row.build} cause={row.cause.value} severity={row.severity.value} "
            f"count={row.count}"
        )
    return "\n".join(lines)


async def _run(*, window_days: int) -> int:
    database_url = os.environ.get(_DATABASE_URL_ENV)
    if not database_url:
        print(f"knowledge-gap-rate: {_DATABASE_URL_ENV} is not set; nothing to report on.")
        return 1

    window_end = datetime.now(UTC)
    window_start = window_end - timedelta(days=window_days)

    session_factory = build_session_factory(build_engine(database_url))
    async with session_factory() as session:
        repository = KnowledgeGapsRepository(session)
        rows = list(await repository.gap_rate(window_start=window_start, window_end=window_end))

    print(render_report(rows, window_start=window_start, window_end=window_end))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--window-days",
        type=int,
        default=_DEFAULT_WINDOW_DAYS,
        help=f"trailing window in days (default: {_DEFAULT_WINDOW_DAYS})",
    )
    args = parser.parse_args()
    return asyncio.run(_run(window_days=args.window_days))


if __name__ == "__main__":
    raise SystemExit(main())
