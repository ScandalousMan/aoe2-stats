"""Tests for the nightly alert audit (T061): fails on any unacknowledged severity-1 `alerts` row,
never on a severity-2 one, and never on a severity-1 row that has already been acknowledged.

See `alert_audit.py`'s own module docstring for why this deliberately overlaps `capture_audit.py`
rather than being folded into it: this script reads `alerts`, never `replay_captures`, and exists
to catch an alert nobody looked at, distinct from `capture_audit.py`'s own catch of a breach that
occurred without the ingester ever raising the alert at all (T059a).

`_ReadOnlyAlertSink` opens its own sessions from a `session_factory`, exactly as `run.py`'s own
`_AlertSink` does (`apps/ingester/tests/test_deadline_alert.py` is the sibling test exercising
that one) — so these tests take `session_factory` directly, seed through their own short-lived
session, and only then hand the same `session_factory` to the sink under test.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import async_sessionmaker
from tests.db import clean_database, database_url, engine, session_factory

from aoe2stats_storage.models import Alert, AlertKind

# See scripts/checks/tests/test_cron_liveness.py for why these are re-exported this way.
__all__ = ["clean_database", "database_url", "engine", "session_factory"]


async def _seed_alert(
    session_factory: async_sessionmaker,
    *,
    kind: AlertKind,
    severity: int,
    acknowledged: bool,
) -> None:
    async with session_factory() as session:
        session.add(
            Alert(
                kind=kind,
                severity=severity,
                detail={"note": "test"},
                acknowledged_at=datetime.now(UTC) if acknowledged else None,
            )
        )
        await session.commit()


async def test_passes_against_an_empty_alerts_table(
    session_factory: async_sessionmaker,
    clean_database: None,
) -> None:
    from scripts.checks.alert_audit import _ReadOnlyAlertSink

    from aoe2stats_core.alerting import find_unacknowledged_severity_one_alerts

    sink = _ReadOnlyAlertSink(session_factory)
    assert await find_unacknowledged_severity_one_alerts(sink) == []


async def test_finds_an_unacknowledged_severity_one_alert(
    session_factory: async_sessionmaker,
    clean_database: None,
) -> None:
    from scripts.checks.alert_audit import _ReadOnlyAlertSink

    from aoe2stats_core.alerting import find_unacknowledged_severity_one_alerts

    await _seed_alert(
        session_factory,
        kind=AlertKind.DEADLINE_BREACH,
        severity=1,
        acknowledged=False,
    )

    sink = _ReadOnlyAlertSink(session_factory)
    unacknowledged = await find_unacknowledged_severity_one_alerts(sink)

    assert [alert.kind for alert in unacknowledged] == [AlertKind.DEADLINE_BREACH.value]


async def test_ignores_an_already_acknowledged_severity_one_alert(
    session_factory: async_sessionmaker,
    clean_database: None,
) -> None:
    from scripts.checks.alert_audit import _ReadOnlyAlertSink

    from aoe2stats_core.alerting import find_unacknowledged_severity_one_alerts

    await _seed_alert(
        session_factory,
        kind=AlertKind.EXPIRED_CAPTURE,
        severity=1,
        acknowledged=True,
    )

    sink = _ReadOnlyAlertSink(session_factory)
    unacknowledged = await find_unacknowledged_severity_one_alerts(sink)

    assert unacknowledged == [], (
        "an alert a human already acknowledged must never fail the audit a second time"
    )


async def test_ignores_an_unacknowledged_severity_two_alert(
    session_factory: async_sessionmaker,
    clean_database: None,
) -> None:
    from scripts.checks.alert_audit import _ReadOnlyAlertSink

    from aoe2stats_core.alerting import find_unacknowledged_severity_one_alerts

    await _seed_alert(
        session_factory,
        kind=AlertKind.RATE_LIMITED,
        severity=2,
        acknowledged=False,
    )

    sink = _ReadOnlyAlertSink(session_factory)
    unacknowledged = await find_unacknowledged_severity_one_alerts(sink)

    assert unacknowledged == [], (
        "severity 2 costs a cycle against a budget measured in days and must never stop the "
        "check that watches for actual loss — only severity 1 does"
    )


async def test_finds_every_unacknowledged_severity_one_alert_not_only_the_first(
    session_factory: async_sessionmaker,
    clean_database: None,
) -> None:
    from scripts.checks.alert_audit import _ReadOnlyAlertSink

    from aoe2stats_core.alerting import find_unacknowledged_severity_one_alerts

    await _seed_alert(
        session_factory, kind=AlertKind.DEADLINE_BREACH, severity=1, acknowledged=False
    )
    await _seed_alert(
        session_factory, kind=AlertKind.EXPIRED_CAPTURE, severity=1, acknowledged=False
    )
    # Noise that must not be counted: acknowledged, and severity 2.
    await _seed_alert(
        session_factory, kind=AlertKind.DEADLINE_BREACH, severity=1, acknowledged=True
    )
    await _seed_alert(session_factory, kind=AlertKind.RATE_LIMITED, severity=2, acknowledged=False)

    sink = _ReadOnlyAlertSink(session_factory)
    unacknowledged = await find_unacknowledged_severity_one_alerts(sink)

    assert {alert.kind for alert in unacknowledged} == {
        AlertKind.DEADLINE_BREACH.value,
        AlertKind.EXPIRED_CAPTURE.value,
    }
    assert len(unacknowledged) == 2
