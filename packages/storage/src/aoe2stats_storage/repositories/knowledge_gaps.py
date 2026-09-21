"""`KnowledgeGapsRepository` — the read side of FR-039's aggregate (T652).

`analysis_knowledge_gaps` **is** the aggregate report
(`specs/006-replay-analysis-foundations/contracts/knowledge-base.md`, "Gaps"/"Aggregate";
`specs/006-replay-analysis-foundations/data-model.md` §7). There is no per-run counter to read
instead — the analyzer has no run, no counters and no logger to attach one to, unlike
`apps/ingester`'s `IngestRun.quarantined_total`, which is one column on a per-run table fed by a
multi-stage aggregator. A pattern of gaps introduced by a game patch is made visible the other way:
one flat row per gap (`models.AnalysisKnowledgeGap`), and this one grouped query over them.

`gap_rate` is the single repository function T652's own task text calls for — "one repository
function grouping by build, cause and severity over a window" — and `scripts/checks/
knowledge_gap_rate.py` is the one script that calls it and prints what it returns.

**Dead code until T663.** `analysis_knowledge_gaps` does not exist in any applied migration yet —
T663 adds it, in the same single additive revision that adds `match_analyses.identity_digest`. This
module, and the script that calls it, are real and tested against the table `Base.metadata`
already knows about (see `packages/storage/tests/repositories/test_knowledge_gaps.py`, which
creates the table directly rather than through Alembic — precisely because no migration exists yet
to create it through), but nothing in this feature's production call graph — `apps/analyzer`, a
cron entry, a router — invokes either before T663's revision is actually applied. Wiring the script
into `.github/workflows/nightly.yml` is T663's job too, not this module's: a nightly job against a
table that does not exist would fail for the whole gap between the two phases.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select

from ..models import AnalysisGapCause, AnalysisGapSeverity, AnalysisKnowledgeGap
from .base import Repository


@dataclass(frozen=True, slots=True)
class GapRateRow:
    """One `(build, cause, severity)` group and the count of gap rows recorded for it, over
    whatever window `gap_rate` was asked for — the row shape the aggregate report is built from."""

    build: int
    cause: AnalysisGapCause
    severity: AnalysisGapSeverity
    count: int


class KnowledgeGapsRepository(Repository):
    """Read-only queries over `analysis_knowledge_gaps`. Nothing here writes a row: T662 owns
    inserting the gap rows the coverage pass produces, and is a separate task from this one."""

    async def gap_rate(
        self, *, window_start: datetime, window_end: datetime
    ) -> Sequence[GapRateRow]:
        """FR-039's aggregate: the count of `analysis_knowledge_gaps` rows recorded in
        `[window_start, window_end)`, grouped by `build`, `cause` and `severity` — so that a
        pattern of gaps a game patch introduced is visible as a rate over the window, rather than
        discovered one analysis at a time. Ordered by `build`, then `cause`, then `severity`, so
        two calls against the same data always report the groups in the same order.

        `window_start`/`window_end` are plain bounds, not a lookback duration: the caller (T652's
        own check script here, T663's nightly wiring later) decides what "a window" means for its
        own run, the same division of labour `capture_audit.py`'s own windowed queries already use
        (`expired_total(session, *, window_start)`, called with `now - timedelta(days=...)`).
        """
        result = await self.session.execute(
            select(
                AnalysisKnowledgeGap.build,
                AnalysisKnowledgeGap.cause,
                AnalysisKnowledgeGap.severity,
                func.count().label("count"),
            )
            .where(
                AnalysisKnowledgeGap.recorded_at >= window_start,
                AnalysisKnowledgeGap.recorded_at < window_end,
            )
            .group_by(
                AnalysisKnowledgeGap.build,
                AnalysisKnowledgeGap.cause,
                AnalysisKnowledgeGap.severity,
            )
            .order_by(
                AnalysisKnowledgeGap.build,
                AnalysisKnowledgeGap.cause,
                AnalysisKnowledgeGap.severity,
            )
        )
        return [
            GapRateRow(build=build, cause=cause, severity=severity, count=count)
            for build, cause, severity, count in result.all()
        ]
