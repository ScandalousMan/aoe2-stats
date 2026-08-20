"""Tests for `aoe2stats_core.alerting`: shape only, no engine, no database — see the module
docstring and `test_replay_validation.py`, which this file mirrors. `FakeAlertSink` is the minimal
shape an `AlertSink` adapter must have; the concrete one is a storage repository, tested where it
lives once one exists.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import pytest

from aoe2stats_core.alerting import (
    AlertRecord,
    AlertSink,
    find_unacknowledged_severity_one_alerts,
    raise_alert,
)


class FakeAlertSink:
    """An in-memory `AlertSink` — no session, no SQL, exactly what the Protocol asks for."""

    def __init__(self) -> None:
        self.rows: list[AlertRecord] = []

    async def write(
        self,
        *,
        kind: str,
        severity: int,
        detail: Mapping[str, Any] | None,
        ingest_run_id: uuid.UUID | None,
    ) -> AlertRecord:
        record = AlertRecord(
            id=uuid.uuid4(),
            kind=kind,
            severity=severity,
            detail=detail,
            raised_at=datetime.now(UTC),
            ingest_run_id=ingest_run_id,
            acknowledged_at=None,
        )
        self.rows.append(record)
        return record

    async def unacknowledged_severity_one(self) -> Sequence[AlertRecord]:
        return [row for row in self.rows if row.severity == 1 and row.acknowledged_at is None]


def _record(**overrides: Any) -> AlertRecord:
    defaults: dict[str, Any] = {
        "id": uuid.uuid4(),
        "kind": "expired_capture",
        "severity": 1,
        "detail": None,
        "raised_at": datetime.now(UTC),
        "ingest_run_id": None,
        "acknowledged_at": None,
    }
    defaults.update(overrides)
    return AlertRecord(**defaults)


def test_a_conforming_sink_satisfies_the_protocol_structurally() -> None:
    # runtime_checkable Protocol conformance is duck typing on method presence, not a subclass
    # relationship — the same reason T013's ReplayValidator test checks this way.
    assert isinstance(FakeAlertSink(), AlertSink)


def test_a_class_missing_the_query_method_does_not_satisfy_the_protocol() -> None:
    class _WriteOnlySink:
        async def write(
            self,
            *,
            kind: str,
            severity: int,
            detail: Mapping[str, Any] | None,
            ingest_run_id: uuid.UUID | None,
        ) -> AlertRecord:
            raise NotImplementedError

    assert not isinstance(_WriteOnlySink(), AlertSink)


async def test_raise_alert_writes_through_the_sink_and_returns_the_record() -> None:
    sink = FakeAlertSink()
    run_id = uuid.uuid4()

    record = await raise_alert(sink, "expired_capture", 1, {"game_id": 42}, run_id=run_id)

    assert sink.rows == [record]
    assert record.kind == "expired_capture"
    assert record.severity == 1
    assert record.detail == {"game_id": 42}
    assert record.ingest_run_id == run_id
    assert record.acknowledged_at is None


async def test_raise_alert_defaults_detail_and_run_id_to_none() -> None:
    sink = FakeAlertSink()

    record = await raise_alert(sink, "rate_limited", 2)

    assert record.detail is None
    assert record.ingest_run_id is None


@pytest.mark.parametrize("severity", [0, 3, -1, 100])
async def test_raise_alert_rejects_a_severity_outside_one_or_two(severity: int) -> None:
    sink = FakeAlertSink()

    with pytest.raises(ValueError, match="severity"):
        await raise_alert(sink, "rate_limited", severity)

    # The rejected call never reaches the sink: an invalid severity must not produce a row that
    # only the database's own check constraint would catch.
    assert sink.rows == []


async def test_find_unacknowledged_severity_one_alerts_excludes_severity_two() -> None:
    sink = FakeAlertSink()
    await raise_alert(sink, "rate_limited", 2)
    severity_one = await raise_alert(sink, "expired_capture", 1)

    found = await find_unacknowledged_severity_one_alerts(sink)

    assert found == [severity_one]


async def test_find_unacknowledged_severity_one_alerts_excludes_acknowledged_rows() -> None:
    sink = FakeAlertSink()
    await raise_alert(sink, "expired_capture", 1)
    sink.rows[0] = _record(
        id=sink.rows[0].id,
        kind=sink.rows[0].kind,
        severity=1,
        raised_at=sink.rows[0].raised_at,
        acknowledged_at=datetime.now(UTC),
    )

    found = await find_unacknowledged_severity_one_alerts(sink)

    assert found == []


def test_the_alert_record_is_frozen() -> None:
    record = _record()
    with pytest.raises(AttributeError):
        record.severity = 2  # type: ignore[misc]
