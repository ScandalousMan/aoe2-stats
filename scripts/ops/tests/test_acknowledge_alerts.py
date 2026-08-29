"""Tests for `scripts/ops/acknowledge_alerts.py`, the by-hand acknowledgement tool for `alerts`
rows — the tooling gap `scripts/checks/alert_audit.py` fails the nightly build over: nothing else
in this repository ever writes `acknowledged_at` outside a test.

Follows `scripts/checks/tests/test_alert_audit.py`'s own pattern: a throwaway Postgres database
(`tests/db.py`, T015), seeded directly through `Alert` rows rather than through any application
code path, because this script reads and writes that table from *outside* the application, exactly
as an operator running it against production would.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.db import clean_database, database_url, engine, session_factory

from aoe2stats_storage.models import Alert, AlertKind

# See scripts/checks/tests/test_cron_liveness.py for why these are re-exported this way.
__all__ = ["clean_database", "database_url", "engine", "session_factory"]

from scripts.ops.acknowledge_alerts import (
    AcknowledgeFilters,
    FilterError,
    acknowledge,
    build_arg_parser,
    parse_filters,
)

_OUTAGE_DAY = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
_OTHER_DAY = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)


async def _seed_alert(
    session_factory: async_sessionmaker,
    *,
    kind: AlertKind,
    severity: int = 1,
    raised_at: datetime,
    acknowledged_at: datetime | None = None,
) -> uuid.UUID:
    alert_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(
            Alert(
                id=alert_id,
                kind=kind,
                severity=severity,
                detail={"note": "test"},
                raised_at=raised_at,
                acknowledged_at=acknowledged_at,
            )
        )
        await session.commit()
    return alert_id


async def _fetch(session_factory: async_sessionmaker, alert_id: uuid.UUID) -> Alert:
    async with session_factory() as session:
        result = await session.execute(select(Alert).where(Alert.id == alert_id))
        row = result.scalars().one()
        return row


def _filters(**overrides: object) -> AcknowledgeFilters:
    defaults: dict[str, object] = {
        "kind": AlertKind.EXPIRED_CAPTURE,
        "reason": "aoe.ms 301 outage, fixed in PR #17; investigated 2026-08-29",
        "apply": False,
        "since": _OUTAGE_DAY - timedelta(hours=1),
        "until": _OUTAGE_DAY + timedelta(hours=1),
    }
    defaults.update(overrides)
    return AcknowledgeFilters(**defaults)  # type: ignore[arg-type]


# --- dry-run writes nothing --------------------------------------------------------------------


async def test_dry_run_writes_nothing(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
) -> None:
    alert_id = await _seed_alert(
        session_factory, kind=AlertKind.EXPIRED_CAPTURE, raised_at=_OUTAGE_DAY
    )

    report = await acknowledge(session_factory, _filters(apply=False))

    assert report.applied is False
    assert [row.id for row in report.pending] == [alert_id]

    row = await _fetch(session_factory, alert_id)
    assert row.acknowledged_at is None, "a dry run must never write acknowledged_at"


# --- applying stamps only matching rows ----------------------------------------------------------


async def test_apply_stamps_only_matching_rows_and_leaves_the_rest_untouched(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
) -> None:
    matching_1 = await _seed_alert(
        session_factory, kind=AlertKind.EXPIRED_CAPTURE, raised_at=_OUTAGE_DAY
    )
    matching_2 = await _seed_alert(
        session_factory,
        kind=AlertKind.EXPIRED_CAPTURE,
        raised_at=_OUTAGE_DAY + timedelta(minutes=30),
    )
    # Noise that must survive untouched: another kind, same day.
    other_kind = await _seed_alert(
        session_factory, kind=AlertKind.DEADLINE_BREACH, raised_at=_OUTAGE_DAY
    )
    # Noise that must survive untouched: same kind, another date outside the range.
    other_date = await _seed_alert(
        session_factory, kind=AlertKind.EXPIRED_CAPTURE, raised_at=_OTHER_DAY
    )

    report = await acknowledge(session_factory, _filters(apply=True))

    assert report.applied is True
    assert {row.id for row in report.pending} == {matching_1, matching_2}

    acknowledged_1 = await _fetch(session_factory, matching_1)
    acknowledged_2 = await _fetch(session_factory, matching_2)
    assert acknowledged_1.acknowledged_at is not None
    assert acknowledged_2.acknowledged_at is not None

    untouched_kind = await _fetch(session_factory, other_kind)
    untouched_date = await _fetch(session_factory, other_date)
    assert untouched_kind.acknowledged_at is None, "a different kind must never be acknowledged"
    assert untouched_date.acknowledged_at is None, "a row outside the range must never be touched"


# --- already-acknowledged rows are idempotent ----------------------------------------------------


async def test_already_acknowledged_row_keeps_its_original_timestamp(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
) -> None:
    original_timestamp = _OUTAGE_DAY - timedelta(days=1)
    alert_id = await _seed_alert(
        session_factory,
        kind=AlertKind.EXPIRED_CAPTURE,
        raised_at=_OUTAGE_DAY,
        acknowledged_at=original_timestamp,
    )

    report = await acknowledge(session_factory, _filters(apply=True))

    assert report.pending == ()
    assert [row.id for row in report.already_acknowledged] == [alert_id]

    row = await _fetch(session_factory, alert_id)
    assert row.acknowledged_at == original_timestamp, (
        "an already-acknowledged row must never be re-stamped"
    )


async def test_running_apply_twice_is_safe(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
) -> None:
    alert_id = await _seed_alert(
        session_factory, kind=AlertKind.EXPIRED_CAPTURE, raised_at=_OUTAGE_DAY
    )

    first = await acknowledge(session_factory, _filters(apply=True))
    assert [row.id for row in first.pending] == [alert_id]
    first_timestamp = (await _fetch(session_factory, alert_id)).acknowledged_at

    second = await acknowledge(session_factory, _filters(apply=True))
    assert second.pending == ()
    assert [row.id for row in second.already_acknowledged] == [alert_id]

    second_timestamp = (await _fetch(session_factory, alert_id)).acknowledged_at
    assert second_timestamp == first_timestamp, "re-running apply must not move the timestamp"


# --- refusals: no database needed, pure argument validation ---------------------------------------


def _parsed(argv: list[str]) -> object:
    parser = build_arg_parser()
    return parser.parse_args(argv)


def test_missing_reason_is_refused() -> None:
    args = _parsed(
        [
            "--kind",
            "expired_capture",
            "--since",
            "2026-08-28T00:00:00+00:00",
            "--until",
            "2026-08-29T00:00:00+00:00",
            "--reason",
            "   ",
        ]
    )
    try:
        parse_filters(args)
    except FilterError as exc:
        assert "reason" in str(exc)
    else:
        raise AssertionError("a blank --reason must be refused")


def test_kind_alone_with_no_range_or_ids_is_refused() -> None:
    """The invocation that would mean 'acknowledge every row of this kind, ever' — exactly the
    blanket acknowledgement this tool must never allow."""
    args = _parsed(["--kind", "expired_capture", "--reason", "investigated"])
    try:
        parse_filters(args)
    except FilterError as exc:
        assert "everything" in str(exc)
    else:
        raise AssertionError("a bare --kind with no id list and no bounded range must be refused")


def test_open_ended_range_is_refused() -> None:
    """--since with no --until is still unbounded on one side — the same 'everything' shape,
    just half-written."""
    args = _parsed(
        [
            "--kind",
            "expired_capture",
            "--since",
            "2026-08-28T00:00:00+00:00",
            "--reason",
            "investigated",
        ]
    )
    try:
        parse_filters(args)
    except FilterError:
        pass
    else:
        raise AssertionError("an open-ended range must be refused")


def test_ids_and_range_together_are_refused() -> None:
    args = _parsed(
        [
            "--kind",
            "expired_capture",
            "--id",
            str(uuid.uuid4()),
            "--since",
            "2026-08-28T00:00:00+00:00",
            "--until",
            "2026-08-29T00:00:00+00:00",
            "--reason",
            "investigated",
        ]
    )
    try:
        parse_filters(args)
    except FilterError:
        pass
    else:
        raise AssertionError("--id combined with --since/--until must be refused")


def test_explicit_ids_alone_are_accepted() -> None:
    """The other valid narrow shape: no range at all, but an explicit id list."""
    an_id = uuid.uuid4()
    args = _parsed(["--kind", "expired_capture", "--id", str(an_id), "--reason", "investigated"])
    filters = parse_filters(args)
    assert filters.ids == (an_id,)
    assert filters.since is None
    assert filters.until is None
