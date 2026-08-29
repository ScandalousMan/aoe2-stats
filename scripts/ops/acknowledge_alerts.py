#!/usr/bin/env python3
"""Acknowledge `alerts` rows by hand, after investigation — the tool constitution I's "acknowledge
only after investigating, never before" otherwise has no way to obey.

**The gap this closes.** `scripts/checks/alert_audit.py` fails the nightly on any unacknowledged
severity-1 `alerts` row, and nothing in this repository ever writes `acknowledged_at` — grep it:
the column is written only by tests. So today, acknowledging an alert means hand-writing an
`UPDATE` against production, with no record of what was acknowledged or why. This script is that
record, as far as the schema lets one exist (see "What is and is not auditable" below).

**Dry-run by default.** Invoking this script prints exactly which rows it would acknowledge — id,
kind, severity, `raised_at` — and writes nothing. Only `--apply` writes. A tool that acknowledges
production alerts on its default invocation is the wrong tool.

**Narrow by construction, on purpose.** `--kind` is always required, and one of `--id` (repeatable)
or a bounded `--since`/`--until` pair is also required — there is no flag combination that means
"acknowledge everything". A single `--kind` with an open-ended or missing range is refused for the
same reason: an unbounded range acknowledges every row of that kind ever raised, which is exactly
the blanket acknowledgement this tool exists to make impossible. Blanket-acknowledging is how a
real alert gets buried under an old, already-investigated one.

**Idempotent.** A row whose `acknowledged_at` is already set is left alone — its timestamp is
never overwritten — so re-running the same command twice (a retried CI step, an operator unsure
whether the first run went through) is safe.

**What is and is not auditable afterwards.** `alerts` has five columns besides its primary key —
`kind`, `severity`, `detail`, `raised_at`, `acknowledged_at`, `ingest_run_id` — and no column for a
reason. This script does not add one: `docs/runbooks/database-migrations.md` exists precisely
because a migration against production is a whole procedure, not a thing to add for a string
column a nightly script can live without, and the task that asked for this tool was explicit that
no migration ships with it. `--reason` is therefore mandatory but **not persisted** — it is printed
back at the end of a run so the operator can paste it into the pull request or the incident
runbook entry that this acknowledgement belongs to. What the database *does* retain afterwards is
`acknowledged_at` itself: that a human looked, and when. What it does not retain, from this script
alone, is *why* — that lives only wherever the operator pastes the printed reason, same as it does
today for every other production action this repository's runbooks describe by hand.

**Reads `DATABASE_URL` from the environment**, exactly like every other script under `scripts/`:
no connection-string argument, no dotenv loading. Unlike a schema migration, this script issues no
DDL and needs no session-level lock semantics, so it wants Neon's **pooled** endpoint — the same
value `.env.example` documents for the running application — never the direct one
`docs/runbooks/database-migrations.md` reserves for Alembic.

Usage (see `docs/runbooks/alert-acknowledgement.md` for the worked example):
    uv run scripts/ops/acknowledge_alerts.py --kind expired_capture \\
        --since 2026-08-28T00:00:00+00:00 --until 2026-08-29T00:00:00+00:00 \\
        --reason "aoe.ms 301 outage, fixed in PR #17; investigated 2026-08-29"
    uv run scripts/ops/acknowledge_alerts.py --kind expired_capture ... --apply --reason "..."

Exit: 0 whether or not any row matched or was written; 1 if the invocation itself is refused
(missing reason, missing/unbounded filters) or `DATABASE_URL` is not set.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_storage.models import Alert as AlertRow
from aoe2stats_storage.models import AlertKind
from aoe2stats_storage.repositories.base import build_engine, build_session_factory

_DATABASE_URL_ENV = "DATABASE_URL"

_VALID_SEVERITIES: tuple[int, int] = (1, 2)


class FilterError(ValueError):
    """Raised when the operator-supplied filters cannot be honoured: a blank reason, or a filter
    combination that would match every row of a kind instead of a deliberately narrow set. Always
    caught by `main()` and turned into a printed message plus exit code 1 — never a write."""


@dataclass(frozen=True, slots=True)
class AcknowledgeFilters:
    """Everything one invocation needs, already validated. `since`/`until` and `ids` are mutually
    exclusive by construction (`parse_filters` below never builds one instance holding both) —
    exactly one of them is ever set."""

    kind: AlertKind
    reason: str
    apply: bool
    severity: int | None = None
    since: datetime | None = None
    until: datetime | None = None
    ids: tuple[uuid.UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class AcknowledgeReport:
    """What one run found and, if `--apply` was given, changed. `pending` is what was (dry-run) or
    just was (apply) newly acknowledged; `already_acknowledged` is the idempotent skip list — rows
    that matched the filters but were left untouched because a previous run already stamped them."""

    pending: tuple[AlertRow, ...]
    already_acknowledged: tuple[AlertRow, ...]
    applied: bool


def _parse_datetime(value: str) -> datetime:
    """Accepts anything `datetime.fromisoformat` accepts (`2026-08-28` or a full timestamp). A
    value with no timezone is treated as UTC — every `alerts.raised_at` value is timezone-aware
    (`DateTime(timezone=True)`, `models.py`), and comparing a naive value against it raises rather
    than silently doing the wrong thing, so this is resolved once here instead of at the database.
    """
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Acknowledge alerts rows after investigation. Dry-run by default; pass --apply to "
            "write. See scripts/ops/acknowledge_alerts.py's own module docstring and "
            "docs/runbooks/alert-acknowledgement.md."
        )
    )
    parser.add_argument(
        "--kind",
        required=True,
        choices=[kind.value for kind in AlertKind],
        help="the single alert kind to acknowledge — required, never a list, never 'all'",
    )
    parser.add_argument(
        "--severity",
        type=int,
        choices=_VALID_SEVERITIES,
        default=None,
        help="optional further narrowing; alerts of any severity may be acknowledged",
    )
    parser.add_argument(
        "--since",
        default=None,
        help="ISO 8601 start of a bounded raised_at range (inclusive); requires --until",
    )
    parser.add_argument(
        "--until",
        default=None,
        help="ISO 8601 end of a bounded raised_at range (inclusive); requires --since",
    )
    parser.add_argument(
        "--id",
        dest="ids",
        action="append",
        default=[],
        metavar="ALERT_ID",
        help="an explicit alerts.id to acknowledge; repeatable. Mutually exclusive with "
        "--since/--until",
    )
    parser.add_argument(
        "--reason",
        required=True,
        help="mandatory written justification. NOT stored in the database (alerts has no column "
        "for it) — printed back for you to paste into the PR or the runbook entry",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write acknowledged_at. Without this flag, nothing changes",
    )
    return parser


def parse_filters(args: argparse.Namespace) -> AcknowledgeFilters:
    """Validate one parsed invocation into an `AcknowledgeFilters`, or raise `FilterError`. Kept
    separate from `build_arg_parser` so a test can exercise the refusal rules directly, without
    going through `argparse`'s own `SystemExit`."""
    reason = (args.reason or "").strip()
    if not reason:
        raise FilterError(
            "--reason is required and must not be blank: constitution I permits acknowledging "
            "only after investigating, never before, and this is the one place that investigation "
            "gets written down at all."
        )

    raw_ids: list[str] = list(args.ids or [])
    has_ids = bool(raw_ids)
    has_since = args.since is not None
    has_until = args.until is not None

    if has_ids and (has_since or has_until):
        raise FilterError("pass --id or --since/--until, not both.")

    if has_ids:
        try:
            ids = tuple(uuid.UUID(raw) for raw in raw_ids)
        except ValueError as exc:
            raise FilterError(f"--id values must be UUIDs: {exc}") from exc
        since = until = None
    else:
        if not (has_since and has_until):
            raise FilterError(
                "refusing to run without either an explicit --id list or a bounded "
                "--since/--until range: there is no invocation of this script that means "
                "'acknowledge everything' for a kind, and a --kind on its own, or with only one "
                "end of a range, is exactly that."
            )
        since = _parse_datetime(args.since)
        until = _parse_datetime(args.until)
        if since > until:
            raise FilterError(
                f"--since ({since.isoformat()}) is after --until ({until.isoformat()})"
            )
        ids = ()

    return AcknowledgeFilters(
        kind=AlertKind(args.kind),
        reason=reason,
        apply=bool(args.apply),
        severity=args.severity,
        since=since,
        until=until,
        ids=ids,
    )


async def find_matching_alerts(
    session_factory: async_sessionmaker[AsyncSession], filters: AcknowledgeFilters
) -> list[AlertRow]:
    """Every `alerts` row `filters` selects, acknowledged or not — callers split the two
    (`acknowledge` below) so an already-acknowledged row can be reported as skipped rather than
    silently vanishing from the output."""
    conditions = [AlertRow.kind == filters.kind]
    if filters.severity is not None:
        conditions.append(AlertRow.severity == filters.severity)
    if filters.ids:
        conditions.append(AlertRow.id.in_(filters.ids))
    else:
        assert filters.since is not None and filters.until is not None
        conditions.append(AlertRow.raised_at >= filters.since)
        conditions.append(AlertRow.raised_at <= filters.until)

    async with session_factory() as session:
        result = await session.execute(
            select(AlertRow).where(*conditions).order_by(AlertRow.raised_at)
        )
        return list(result.scalars().all())


async def acknowledge(
    session_factory: async_sessionmaker[AsyncSession], filters: AcknowledgeFilters
) -> AcknowledgeReport:
    """Find every matching row, then — only when `filters.apply` is set — stamp `acknowledged_at`
    on the ones that do not already carry one. An already-acknowledged row is never touched: this
    is what makes re-running the same command idempotent, per the module docstring.
    """
    matched = await find_matching_alerts(session_factory, filters)
    pending = [row for row in matched if row.acknowledged_at is None]
    already = [row for row in matched if row.acknowledged_at is not None]

    if filters.apply and pending:
        now = datetime.now(UTC)
        pending_ids = [row.id for row in pending]
        async with session_factory() as session:
            await session.execute(
                update(AlertRow)
                .where(AlertRow.id.in_(pending_ids), AlertRow.acknowledged_at.is_(None))
                .values(acknowledged_at=now)
            )
            await session.commit()
        for row in pending:
            row.acknowledged_at = now

    return AcknowledgeReport(
        pending=tuple(pending), already_acknowledged=tuple(already), applied=filters.apply
    )


def _format_row(row: AlertRow) -> str:
    return (
        f"  - id={row.id} kind={row.kind} severity={row.severity} "
        f"raised_at={row.raised_at.isoformat()}"
    )


def _print_report(report: AcknowledgeReport, filters: AcknowledgeFilters) -> None:
    verb = (
        "Acknowledged" if report.applied else "Would acknowledge (dry-run — pass --apply to write)"
    )
    if not report.pending:
        print("acknowledge-alerts: nothing to acknowledge (0 matching, unacknowledged row(s)).")
    else:
        print(f"acknowledge-alerts: {verb} {len(report.pending)} row(s):")
        for row in report.pending:
            print(_format_row(row))

    if report.already_acknowledged:
        print(
            f"acknowledge-alerts: {len(report.already_acknowledged)} matching row(s) already "
            "acknowledged — left untouched (idempotent):"
        )
        for row in report.already_acknowledged:
            print(_format_row(row))

    print()
    print(
        "Reason (paste this into the PR description or the incident runbook entry — the "
        "database does not retain it; alerts has no column for it):"
    )
    print(f"  {filters.reason}")


async def _run(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        filters = parse_filters(args)
    except FilterError as exc:
        print(f"acknowledge-alerts: refused — {exc}")
        return 1

    database_url = os.environ.get(_DATABASE_URL_ENV)
    if not database_url:
        print(
            f"acknowledge-alerts: {_DATABASE_URL_ENV} is not set; nothing to acknowledge against."
        )
        return 1

    session_factory = build_session_factory(build_engine(database_url))
    report = await acknowledge(session_factory, filters)
    _print_report(report, filters)
    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_run(argv))


if __name__ == "__main__":
    raise SystemExit(main())
