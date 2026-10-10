#!/usr/bin/env python3
"""Re-validate captures that ended `quarantined` because the replay engine could not parse them
(T673, feature 006 Phase 7).

**The gap this closes.** `aoe2rec-py` 0.1.21 panicked on recordings of game build 185872, so those
captures were stored, checksummed and then marked `quarantined` with their object kept
(constitution IV). T672 pinned 0.1.24, which reads them. This command gives each such row a second
validation from the bytes already committed. **Urgent:** the source holds a recording for about 31
days; once a recording is older than that, an analysis of its match has no fallback source, and
the retained copy is the only one. Oldest recording first, so the ones nearest that window go first.

**What it does, per row** (`CaptureDrain.revalidate_quarantined`, `apps/ingester/src/
aoe2stats_ingester/capture.py`, which owns the selection and says exactly why): read the committed
object back, check it against the row's own `zip_sha256`, run it through the same containment
barrier the capture path uses, and mark the row `stored` (with `validated_by`, `inner_filename`,
`inner_bytes`, exactly as a normal capture) or leave it `quarantined` with the new error.

**What it never does.** It never downloads: the replay provider handed to the drain here raises if
it is ever called. It never writes, replaces or deletes an object: only `get` is called on the
store. It never reopens an integrity quarantine (`reclaim could not read back ...`, `reclaim
checksum mismatch ...`), a timeout or a `MalformedArchiveError`: the selection is the engine's own
failure text and nothing else. A row whose object is missing or no longer matches its `zip_sha256`
is left exactly as it was. It raises no `validation_failed` alert; the row raised one when it was
first quarantined.

**Dry run first.** `--dry-run` lists the selection (game, profile, recording date) without reading
a byte of any object or writing a row.

**Bounded and resumable.** At most `--limit` rows per run (default 25: a validation can take up to
its 30 s wall-clock cap, and this runs from a terminal). When more remain, the report prints the
`--after` value that continues from the last row examined. A row that fails again is still a
candidate, so a bare re-run would revisit it first; `--after` is what moves past it.

`--after` is one value, `<timestamp>,<capture id>`: the recording's completion time (ISO 8601, with
an offset) and the capture's UUID, which together are the ordering key. The id is not optional:
two tracked profiles can have captured the same match, so several captures share one completion
time, and a run cut between them would lose the rest if only the timestamp were kept. A timestamp
without an id is refused (exit 1), never read as "after everything at that time". Copy the printed
value exactly.

**Idempotent.** Run it twice: a row that is `stored` is no longer selected, and a row that fails
again is rewritten with the same content.

**Environment** (nothing is read from a dotenv file: `.env.local` in this repository points at the
*production* Neon database, and the operator must name the target on the command line). The
object-store values are the ones `.env.example` documents, under the same names the application
uses; none is ever printed.

- `DATABASE_URL`: Neon's **pooled** endpoint (no DDL, so not the direct one the migration runbook
  reserves for Alembic).
- `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_REGION`: read
  access to the replay bucket is enough. Not needed with `--dry-run`.

Usage:
    uv run python scripts/ops/revalidate_quarantined.py --dry-run
    uv run python scripts/ops/revalidate_quarantined.py --limit 25
    uv run python scripts/ops/revalidate_quarantined.py --limit 25 \\
        --after 2026-09-30T12:00:00+00:00,3f2b8c1e-5a4d-4e6f-9a0b-1c2d3e4f5a6b

Exit: 0 when the run completed, whatever it found; 1 when the invocation is refused (a missing
environment variable, an `--after` that is not `<timestamp with offset>,<capture id>`, a
`--limit` below 1).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_core.replay.validation import ReplayValidator
from aoe2stats_ingester.capture import CaptureDrain, RevalidationCursor, RevalidationReport
from aoe2stats_providers.base import NotFound, ReplayBlob
from aoe2stats_storage.objects import ObjectStore, ObjectStoreConfig
from aoe2stats_storage.repositories.base import build_engine, build_session_factory

_DATABASE_URL_ENV = "DATABASE_URL"
_OBJECT_STORE_ENVS = (
    "S3_ENDPOINT_URL",
    "S3_BUCKET",
    "S3_ACCESS_KEY_ID",
    "S3_SECRET_ACCESS_KEY",
    "S3_REGION",
)
_DEFAULT_LIMIT = 25
_REASON_WIDTH = 160


class RefusedDownloadError(RuntimeError):
    """Raised if anything asks this command to download a replay. It never should."""


class _NoReplayProvider:
    """The `ReplayProvider` this command hands the drain: a re-validation never downloads, so the
    one thing it must be unable to do is reach the source."""

    async def fetch_replay(self, game_id: int, profile_id: int) -> ReplayBlob | NotFound:
        raise RefusedDownloadError(
            "revalidate_quarantined never downloads; the committed object is the only input"
        )


async def revalidate(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    object_store: ObjectStore | None,
    validator: ReplayValidator | None,
    limit: int,
    after: RevalidationCursor | None = None,
    dry_run: bool = False,
) -> RevalidationReport:
    """Run `CaptureDrain.revalidate_quarantined` with a provider that refuses every call."""
    drain = CaptureDrain(
        session_factory=session_factory,
        replay_provider=_NoReplayProvider(),
        object_store=object_store,
        validator=validator,
    )
    return await drain.revalidate_quarantined(limit=limit, after=after, dry_run=dry_run)


def object_store_from_environment(environ: Mapping[str, str]) -> ObjectStore:
    """The replay bucket, from the application's own variable names; `ValueError` names the
    missing ones (never their values)."""
    missing = [name for name in _OBJECT_STORE_ENVS if not environ.get(name)]
    if missing:
        raise ValueError(f"not set: {', '.join(missing)}")
    return ObjectStore(
        ObjectStoreConfig(
            endpoint_url=environ["S3_ENDPOINT_URL"],
            bucket=environ["S3_BUCKET"],
            access_key_id=environ["S3_ACCESS_KEY_ID"],
            secret_access_key=environ["S3_SECRET_ACCESS_KEY"],
            region=environ["S3_REGION"],
        )
    )


_CURSOR_SHAPE = "<timestamp with offset>,<capture id>"


def _cursor(text: str) -> RevalidationCursor:
    """`--after`: `<ISO 8601 timestamp with offset>,<capture id>`, the report's own `cursor`.
    Anything else is refused; in particular a bare timestamp, which would compare on time alone."""
    timestamp_text, comma, id_text = text.rpartition(",")
    if not comma:
        raise argparse.ArgumentTypeError(
            f"{text!r} is not {_CURSOR_SHAPE}; the capture id is required (several captures can "
            "share one recording time), copy the value the previous run printed"
        )
    try:
        parsed = datetime.fromisoformat(timestamp_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"not an ISO 8601 timestamp: {timestamp_text!r} (expected {_CURSOR_SHAPE})"
        ) from exc
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError(
            f"{timestamp_text!r} has no time zone; write it with an offset, "
            "e.g. 2026-09-30T12:00:00+00:00"
        )
    try:
        capture_id = uuid.UUID(id_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"not a capture id: {id_text!r} (expected {_CURSOR_SHAPE})"
        ) from exc
    return parsed.astimezone(UTC), capture_id


def build_arg_parser(*, exit_on_error: bool = True) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        exit_on_error=exit_on_error,
        description=(
            "Re-validate captures quarantined by an engine failure, from the committed object. "
            "Never downloads, never modifies or deletes an object. "
            "See scripts/ops/revalidate_quarantined.py's own module docstring."
        ),
        epilog=(
            "Environment: DATABASE_URL (Neon pooled endpoint); with a real run also "
            "S3_ENDPOINT_URL, S3_BUCKET, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, S3_REGION. "
            "No dotenv file is read."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="list the selection without reading any object or writing any row",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=_DEFAULT_LIMIT,
        help=f"most rows to examine this run (default {_DEFAULT_LIMIT}, minimum 1)",
    )
    parser.add_argument(
        "--after",
        type=_cursor,
        metavar="TIMESTAMP,CAPTURE_ID",
        default=None,
        help="resume after this row: the recording's ISO 8601 completion time (with offset), a "
        "comma, and the capture id; copy the value the previous run printed. "
        "A timestamp alone is refused",
    )
    return parser


def _one_line(reason: str | None) -> str:
    """A reason on one printable ASCII line: an engine panic text carries terminal escape codes
    and a backtrace, which must not reach a terminal."""
    flat = ascii(" ".join((reason or "").split()))[1:-1]
    return flat if len(flat) <= _REASON_WIDTH else flat[: _REASON_WIDTH - 3] + "..."


def format_report(report: RevalidationReport, *, dry_run: bool) -> list[str]:
    lines = [
        f"{o.outcome:<18} game {o.game_id} profile {o.profile_id} "
        f"recorded {o.completed_at.isoformat()}" + (f"  {_one_line(o.reason)}" if o.reason else "")
        for o in report.outcomes
    ]
    counts: dict[str, int] = {}
    for outcome in report.outcomes:
        counts[outcome.outcome] = counts.get(outcome.outcome, 0) + 1
    summary = ", ".join(f"{name}={count}" for name, count in sorted(counts.items())) or "nothing"
    lines.append(f"revalidate-quarantined: {len(report.outcomes)} row(s) examined ({summary}).")
    cursor = report.cursor
    if report.truncated and cursor is not None:
        lines.append(
            "revalidate-quarantined: more candidates remain; continue with "
            f"--after {cursor[0].isoformat()},{cursor[1]}"
        )
    if dry_run:
        lines.append("revalidate-quarantined: dry run, nothing was read or written.")
    return lines


async def _run(argv: list[str] | None, environ: Mapping[str, str]) -> int:
    try:
        args = build_arg_parser(exit_on_error=False).parse_args(argv)
    except argparse.ArgumentError as exc:
        print(f"revalidate-quarantined: {exc}", file=sys.stderr)
        return 1
    if args.limit < 1:
        print("revalidate-quarantined: --limit must be at least 1.", file=sys.stderr)
        return 1
    database_url = environ.get(_DATABASE_URL_ENV)
    if not database_url:
        print(f"revalidate-quarantined: {_DATABASE_URL_ENV} is not set.", file=sys.stderr)
        return 1

    object_store: ObjectStore | None = None
    validator: ReplayValidator | None = None
    if not args.dry_run:
        try:
            object_store = object_store_from_environment(environ)
        except ValueError as exc:
            print(f"revalidate-quarantined: {exc}", file=sys.stderr)
            return 1
        # Imported here: the engine is heavy and a dry run never needs it.
        from aoe2stats_replay_engine.aoe2rec import Aoe2RecValidator

        validator = Aoe2RecValidator()

    engine = build_engine(database_url)
    try:
        report = await revalidate(
            build_session_factory(engine),
            object_store=object_store,
            validator=validator,
            limit=args.limit,
            after=args.after,
            dry_run=args.dry_run,
        )
    finally:
        await engine.dispose()
    for line in format_report(report, dry_run=args.dry_run):
        print(line)
    return 0


def main(argv: list[str] | None = None, environ: Mapping[str, str] | None = None) -> int:
    return asyncio.run(_run(argv, os.environ if environ is None else environ))


if __name__ == "__main__":
    raise SystemExit(main())
