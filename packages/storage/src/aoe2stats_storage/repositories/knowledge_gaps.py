"""`KnowledgeGapsRepository` — FR-039's aggregate (T652) and the write that feeds it (T662).

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

**The write (T662).** `record_gaps` inserts one row per gap the coverage pass reported, keyed by the
analysis's identity digest, and ignores a row the unique expression index already holds — so a
reproduced or re-run analysis, which carries the same digest and the same gaps, adds nothing, while
a different identity (a new snapshot, parser or analytics version) adds rows of its own and leaves
the earlier identity's untouched (FR-042). It does not commit: the caller writes the rows in the
transaction that publishes the document, so a publish that fails leaves no orphan gap rows.

**Applied by T663.** `analysis_knowledge_gaps` is created by T663's single additive revision
(`53375d9435fc`), which also adds `match_analyses.identity_digest` and wires the script into
`.github/workflows/nightly.yml`. Until that revision is applied to a database, this module and the
script fail with `UndefinedTable` there.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from ..models import AnalysisGapCause, AnalysisGapSeverity, AnalysisKnowledgeGap
from .base import Repository

#: `analysis_knowledge_gaps.build` for a gap whose stream named no build at all (T652b,
#: data-model.md §7). The column is not nullable and the cause set is closed, so a sentinel is the
#: only honest answer left; no real build is negative and the test stub's `describes_build = 0` is
#: not -1.
#: Readers that group by build (`scripts/checks/knowledge_gap_rate.py`) must label it, never
#: print it as a build.
NO_BUILD: Final = -1

#: The three non-nullable columns a whole-build gap (`no-snapshot-for-build`) has no value for,
#: because nothing about the build is known — not one entity or one field of it. A real entity kind
#: is a game object kind and a real field is a knowledge field name, so none of the three can
#: collide with a per-entity row, and the unique index keeps one such row per identity.
WHOLE_BUILD_ENTITY_KIND: Final = "build"
WHOLE_BUILD_ENTITY_ID: Final = "*"
WHOLE_BUILD_FIELD: Final = "*"


@dataclass(frozen=True, slots=True)
class GapToRecord:
    """One gap as `analysis_knowledge_gaps` stores it. `cause` and `severity` are the closed-set
    strings of data-model.md §7, already computed by the coverage pass and never decided here."""

    build: int
    entity_kind: str
    entity_id: str
    field: str
    civilisation_id: str | None
    cause: str
    severity: str


@dataclass(frozen=True, slots=True)
class GapRateRow:
    """One `(build, cause, severity)` group and the count of gap rows recorded for it, over
    whatever window `gap_rate` was asked for — the row shape the aggregate report is built from."""

    build: int
    cause: AnalysisGapCause
    severity: AnalysisGapSeverity
    count: int


class KnowledgeGapsRepository(Repository):
    """Queries over `analysis_knowledge_gaps`, and the one insert (`record_gaps`)."""

    async def record_gaps(
        self, *, game_id: int, identity_digest: str, gaps: Sequence[GapToRecord]
    ) -> int:
        """Insert `gaps` for the analysis `identity_digest` names; return how many rows were new.

        Insert-or-ignore against the unique expression index on `(identity_digest, entity_kind,
        entity_id, field, coalesce(civilisation_id, ''))`: a gap that identity already recorded is
        skipped, not an error. Adds to the caller's transaction and does not commit it.
        """
        if not gaps:
            return 0
        result = await self.session.execute(
            insert(AnalysisKnowledgeGap)
            .values(
                [
                    {
                        "game_id": game_id,
                        "identity_digest": identity_digest,
                        "build": gap.build,
                        "entity_kind": gap.entity_kind,
                        "entity_id": gap.entity_id,
                        "field": gap.field,
                        "civilisation_id": gap.civilisation_id,
                        "cause": AnalysisGapCause(gap.cause),
                        "severity": AnalysisGapSeverity(gap.severity),
                    }
                    for gap in gaps
                ]
            )
            .on_conflict_do_nothing()
            .returning(AnalysisKnowledgeGap.id)
        )
        return len(result.all())

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
