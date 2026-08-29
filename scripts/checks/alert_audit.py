#!/usr/bin/env python3
"""Nightly alert audit (T061): fails on any unacknowledged severity-1 `alerts` row.

Alerting in this feature is pulled, never pushed (`packages/core/src/aoe2stats_core/alerting.py`'s
own module docstring): nothing in phase 1 is always-on, so an alert cannot page anyone from inside
a process that may not be running. The ingester writes an `alerts` row through `raise_alert`; this
script — run nightly, alongside `cron_liveness.py` and `capture_audit.py` — is the only thing that
turns that row into something a human sees, through `.github/workflows/nightly.yml`'s `report` job
opening an issue on any failure here.

Severity is not decoration (`data-model.md`'s `alerts` section): severity 1 is reserved for the two
kinds meaning a replay is gone or is about to be — `deadline_breach` (T059a) and `expired_capture`
(T056) — so this script fails only on those, never on a severity-2 row (`rate_limited`,
`validation_failed`, `free_tier`), which costs a cycle against a budget measured in days and must
not stop the check that watches for actual loss.

**Why this overlaps `capture_audit.py` by design** (T061's own task text): this script never reads
`replay_captures`, and `capture_audit.py` never reads `alerts`. This script catches an alert nobody
acknowledged; `capture_audit.py`'s deadline check catches the underlying breach even when the
ingester never ran at all to raise the alert in the first place — the reason T059a's alert exists is
also the reason this audit exists to make sure it was seen. Neither subsumes the other.

**This script is now the durable half of constitution I's zero-loss guarantee.** `capture_audit.py`
windowed its own `expired_total` assertion (2026-08-29, after 56 historical, already-investigated
expirations from the `aoe.ms` 301 outage made a lifetime sum permanently non-zero and therefore
useless as an alarm — see that module's own docstring for the incident): it now only answers "is
anything being lost *right now*", over a trailing few days, and recovers on its own once a loss ages
out of that window. That is a genuine weakening on its own, and this script is the mitigation, not
an afterthought to it: `EXPIRED_CAPTURE` (T056) is severity 1, this script fails on *any*
unacknowledged severity-1 row with no window at all, and constitution I permits acknowledging "only
after investigating, never before" — so an expiry stays visible here, and this check stays red,
until a human has actually looked at it, however long ago it happened. `capture_audit.py` answers
"is anything being lost right now"; this script answers "has every loss been **investigated**", and
only a human acting on it, never the passage of time, clears that.

Uses `aoe2stats_core.alerting.find_unacknowledged_severity_one_alerts` — the exact same read the
ingester's own producers (T052/T055/T056/T059a/T100) would use if any of them ever needed to check
their own work — rather than a second, independently written query, so "unacknowledged severity-1"
means exactly one thing across the whole codebase.

Usage:  uv run scripts/checks/alert_audit.py
Exit:   0 if there is no unacknowledged severity-1 row, 1 otherwise.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_core.alerting import AlertRecord, find_unacknowledged_severity_one_alerts
from aoe2stats_storage.models import Alert as AlertRow
from aoe2stats_storage.repositories.base import build_engine, build_session_factory

_DATABASE_URL_ENV = "DATABASE_URL"


class _ReadOnlyAlertSink:
    """Satisfies `aoe2stats_core.alerting.AlertSink`'s full shape, but only ever exercises its
    read half.

    `find_unacknowledged_severity_one_alerts` only ever calls `unacknowledged_severity_one`
    at runtime, so this class's actual runtime contract is the read side alone — unlike
    `apps/ingester/src/aoe2stats_ingester/run.py`'s `_AlertSink` and `capture.py`'s
    `_DatabaseAlertSink`, each of which is a real producer and needs both halves for real (this
    script never raises an alert, only reads them, and is not imported from either of those two
    internal, underscore-prefixed classes because `scripts/checks` is deliberately outside the uv
    workspace (plan.md) and does not reach into `apps/ingester`'s internals).

    `write` still has to exist below (T061a): `AlertSink` is a `Protocol`, and
    `find_unacknowledged_severity_one_alerts` is typed to take the whole of it, not a narrower
    read-only protocol — mypy strict checks structural conformance against the full shape a
    parameter declares, regardless of which members a caller actually invokes, so leaving `write`
    out fails `[arg-type]` even though nothing here ever reaches it. It raises rather than writing
    a real row: a `write` that could plausibly run and silently diverge from `raise_alert`'s own
    validation would be worse than one that fails loudly the moment something starts calling it.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def write(
        self,
        *,
        kind: str,
        severity: int,
        detail: Mapping[str, Any] | None,
        ingest_run_id: uuid.UUID | None,
    ) -> AlertRecord:
        raise NotImplementedError(
            "alert_audit.py only ever reads alerts; see the class docstring for why this exists "
            "at all."
        )

    async def unacknowledged_severity_one(self) -> Sequence[AlertRecord]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(AlertRow).where(AlertRow.severity == 1, AlertRow.acknowledged_at.is_(None))
            )
            rows = result.scalars().all()
        return [
            AlertRecord(
                id=row.id,
                kind=row.kind,
                severity=row.severity,
                detail=row.detail,
                raised_at=row.raised_at,
                ingest_run_id=row.ingest_run_id,
                acknowledged_at=row.acknowledged_at,
            )
            for row in rows
        ]


def _format_detail(detail: Mapping[str, Any] | None) -> str:
    return "no detail" if not detail else str(dict(detail))


async def _run() -> int:
    database_url = os.environ.get(_DATABASE_URL_ENV)
    if not database_url:
        print(f"alert-audit: {_DATABASE_URL_ENV} is not set; nothing to check against.")
        return 1

    session_factory = build_session_factory(build_engine(database_url))
    sink = _ReadOnlyAlertSink(session_factory)
    unacknowledged = await find_unacknowledged_severity_one_alerts(sink)

    if not unacknowledged:
        print("alert-audit: OK — no unacknowledged severity-1 alert.")
        return 0

    print(
        f"alert-audit: FAIL — {len(unacknowledged)} unacknowledged severity-1 alert(s). "
        "Constitution I: acknowledge only after investigating, never before."
    )
    for alert in unacknowledged:
        print(
            f"  - {alert.raised_at.isoformat()} {alert.kind} (id={alert.id}, "
            f"ingest_run_id={alert.ingest_run_id}): {_format_detail(alert.detail)}"
        )
    return 1


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
