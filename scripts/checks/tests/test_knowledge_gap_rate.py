"""Tests for the FR-039 aggregate gap report (T652).

`render_report` is pure — no database, no network — so it is tested directly against synthetic
`GapRateRow` values, the same split `publication_delay.py`'s own `render_summary` uses for its
report. `_run`'s only branch worth a test with no database at all is the one every other check
script here shares (`alert_audit.py`, `capture_audit.py`): `DATABASE_URL` unset.

No test here runs the script against a real `analysis_knowledge_gaps` table — that table does not
exist behind any applied migration yet (T663), and `KnowledgeGapsRepository.gap_rate` itself is
already exercised against one, created directly from the ORM model, by
`packages/storage/tests/repositories/test_knowledge_gaps.py`. Testing the same query a second time
here, through the script, would only prove the wiring, and `_run`'s DATABASE_URL branch below
already does that for the one thing this module adds on top of the repository call.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aoe2stats_storage.models import AnalysisGapCause, AnalysisGapSeverity
from aoe2stats_storage.repositories.knowledge_gaps import GapRateRow


def test_render_report_names_the_window_and_every_group() -> None:
    from scripts.checks.knowledge_gap_rate import render_report

    window_start = datetime(2026, 9, 1, tzinfo=UTC)
    window_end = datetime(2026, 10, 1, tzinfo=UTC)
    rows = [
        GapRateRow(
            build=101,
            cause=AnalysisGapCause.FIELD_ABSENT,
            severity=AnalysisGapSeverity.BLOCKING,
            count=2,
        ),
        GapRateRow(
            build=101,
            cause=AnalysisGapCause.CIVILISATION_NOT_MODELLED,
            severity=AnalysisGapSeverity.INFORMATIONAL,
            count=1,
        ),
    ]

    report = render_report(rows, window_start=window_start, window_end=window_end)

    assert window_start.isoformat() in report
    assert window_end.isoformat() in report
    assert "total gaps: 3" in report
    assert "build=101 cause=field-absent severity=blocking count=2" in report
    assert "build=101 cause=civilisation-not-modelled severity=informational count=1" in report


def test_render_report_says_so_when_nothing_was_recorded() -> None:
    from scripts.checks.knowledge_gap_rate import render_report

    window_start = datetime(2026, 9, 1, tzinfo=UTC)
    window_end = datetime(2026, 10, 1, tzinfo=UTC)

    report = render_report([], window_start=window_start, window_end=window_end)

    assert "no gap recorded in this window" in report


async def test_run_fails_when_database_url_is_not_set(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts.checks.knowledge_gap_rate import _run

    monkeypatch.delenv("DATABASE_URL", raising=False)

    exit_code = await _run(window_days=30)

    assert exit_code == 1
