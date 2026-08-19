"""The alert sink: a use case, not a table write.

`core` holds this and no SQL, for the same reason it holds only the replay-engine Protocol in
`aoe2stats_core.replay.validation` and never an engine — this package's own `pyproject.toml`
declares zero dependencies, and `apps/api` imports `core`, so nothing here may reach for
`sqlalchemy` or `aoe2stats_storage` directly. The `alerts` table itself, its five `kind` values and
its severity check constraint live in `packages/storage/src/aoe2stats_storage/models.py` (T007);
this module only knows the shape of a use case that writes one row and reads some back, expressed
as a `Protocol` a storage repository satisfies structurally — exactly the split T013 already drew
between the validator Protocol and the `aoe2rec-py` adapter that implements it.

Per data-model.md's `alerts` section: five kinds (`rate_limited`, `deadline_breach`,
`expired_capture`, `validation_failed`, `free_tier`), severity 1 or 2, and the severity is not
decoration — the nightly alert audit (T061) fails the build only on an unacknowledged severity-1
row, because severity 1 is reserved for the two kinds that mean a replay is gone or is about to be
(constitution I). `raise_alert` enforces that `severity in (1, 2)` itself, mirroring the database's
own `ck_alerts_severity_range` check constraint (`models.py`) — the same rule stated once where the
use case decides it and once where the schema guarantees it can never be bypassed by a caller that
skips this module.

Alerting here is **pulled, never pushed** (plan.md): nothing in phase 1 is always-on, so nothing can
be paged from inside a process that may not be running. `raise_alert` only writes a row; turning an
unacknowledged severity-1 row into something a human sees is the nightly job's job (T061), and
`find_unacknowledged_severity_one_alerts` is the read side of that same contract — the query the
nightly job runs, expressed here as a Protocol method so this module still touches no SQL.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

#: The severities `alerts.severity` accepts (`ck_alerts_severity_range` in `models.py`). Kept as a
#: plain tuple rather than an `IntEnum`: the two numbers carry no vocabulary of their own beyond
#: what constitution I already assigns them, and a caller needs the plain integer to compare
#: against the database column with no extra step.
VALID_SEVERITIES: tuple[int, int] = (1, 2)


@dataclass(frozen=True, slots=True)
class AlertRecord:
    """One `alerts` row, exactly as a sink hands it back — never constructed by application code.

    Carries every column data-model.md's `alerts` section describes except `kind`'s and
    `severity`'s validation, which is `raise_alert`'s job before a record ever exists. `kind` stays
    a plain `str` here rather than an enum imported from `aoe2stats_storage`: the five values are
    that module's vocabulary (`AlertKind`, T007), and `aoe2stats_storage.models.AlertKind` members
    are themselves `str` (a `StrEnum`), so a caller that already holds one satisfies this dataclass
    with no conversion.
    """

    id: uuid.UUID
    kind: str
    severity: int
    detail: Mapping[str, Any] | None
    raised_at: datetime
    ingest_run_id: uuid.UUID | None
    acknowledged_at: datetime | None


@runtime_checkable
class AlertSink(Protocol):
    """Satisfied by the storage repository that actually holds the `alerts` table.

    Two methods, one per direction: `write` is the row `raise_alert` produces, and
    `unacknowledged_severity_one` is the read the nightly audit needs. Nothing about a session, a
    connection or SQL appears here — that is exactly what the concrete repository in
    `packages/storage` supplies, structurally, the same way `packages/replay-engine`'s adapter
    supplies `ReplayValidator` (T013) without `core` ever importing it.
    """

    async def write(
        self,
        *,
        kind: str,
        severity: int,
        detail: Mapping[str, Any] | None,
        ingest_run_id: uuid.UUID | None,
    ) -> AlertRecord:
        """Persist one `alerts` row and return it. Called only by `raise_alert`, never directly:
        that is what keeps severity validation in one place regardless of which sink is wired in.
        """
        ...

    async def unacknowledged_severity_one(self) -> Sequence[AlertRecord]:
        """Every `alerts` row with `severity = 1` and `acknowledged_at IS NULL`.

        The query the nightly alert audit (T061) runs to decide whether to fail the build —
        constitution I's severity-1 incident, raised into a row here, has to reach that job or it
        was raised into nothing at all.
        """
        ...


async def raise_alert(
    sink: AlertSink,
    kind: str,
    severity: int,
    detail: Mapping[str, Any] | None = None,
    *,
    run_id: uuid.UUID | None = None,
) -> AlertRecord:
    """Write one `alerts` row through `sink`, refusing a severity the schema would also refuse.

    This is the one call site every producer in this feature shares — T052's `rate_limited`, T055's
    `validation_failed`, T056's `expired_capture`, T059a's `deadline_breach`, and T100's
    `free_tier` — so that "an alert was raised" always means exactly "a row exists", never "a
    notification was attempted and maybe delivered". `sink` is a required parameter and not a
    module-level default: `core` has no I/O of its own to default it to, and a call site that
    forgets to pass one fails loudly at the type checker rather than silently dropping an alert.
    """
    if severity not in VALID_SEVERITIES:
        raise ValueError(
            f"alert severity must be one of {VALID_SEVERITIES}, got {severity!r} for kind {kind!r}"
        )
    return await sink.write(kind=kind, severity=severity, detail=detail, ingest_run_id=run_id)


async def find_unacknowledged_severity_one_alerts(sink: AlertSink) -> Sequence[AlertRecord]:
    """The nightly job's query, named for what it decides rather than for its `WHERE` clause.

    A thin pass-through today, kept as its own function rather than inlined at every call site: the
    nightly audit script (T061) reads intent from `find_unacknowledged_severity_one_alerts(sink)`
    the way it never could from `sink.unacknowledged_severity_one()` alone, and a second producer of
    the same query later has exactly one place to change.
    """
    return await sink.unacknowledged_severity_one()
