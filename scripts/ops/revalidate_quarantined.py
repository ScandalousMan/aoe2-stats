#!/usr/bin/env python3
"""Re-validate captures that ended `quarantined` because the replay engine could not parse them
(T673, feature 006 Phase 7).

**The gap this closes.** `aoe2rec-py` 0.1.21 panicked on the one recording measured as game build
185872 (`docs/risks.md`), so its capture was stored, checksummed and then marked `quarantined` with
the object kept (constitution IV); T672 pinned 0.1.24, which reads that recording. Whether any other
capture carries the engine's failure text is not measured: the dry run's report is how it becomes
so. This command gives each such row a second validation from the bytes already committed. It does
not read the source, and where the source's retention window sits is `docs/data-sources.md`'s to
say, not this file's.

**What it does, per row** (`CaptureDrain.revalidate_quarantined`, `apps/ingester/src/
aoe2stats_ingester/capture.py`, which owns the selection and says exactly why): read the committed
object back, check it against the row's own `zip_sha256`, run it through the same containment
barrier the capture path uses, and mark the row `stored` (with `validated_by`, `inner_filename` and
`inner_bytes` as a normal capture, and `stored_at` the time of this re-validation, not of the
original capture) or leave it `quarantined` with the new engine verdict.

**What it never does.** It never downloads: the replay provider handed to the drain here raises if
it is ever called. It never writes, replaces or deletes an object: only `get` is called on the
store. It never selects an integrity quarantine (`reclaim could not read back ...`, `reclaim
checksum mismatch ...`), a timeout or a `MalformedArchiveError`: the selection is the engine's own
failure text, and nothing else. It never selects a capture whose owner has objected to archival
(constitution IX): the same predicate the capture claim applies. It raises no `validation_failed`
alert; the row raised one when it was first quarantined.

**Outcomes** (one line per row): `stored`, `still_quarantined` (a new engine verdict, written),
`inconclusive` (validation failed for a reason that is not the engine's verdict, e.g. the
wall-clock cap: nothing is written, the reason is printed, and the row is selected again next run),
`integrity_failure` (the object is missing or no longer matches the row's `zip_sha256`: nothing is
written) and `changed_elsewhere` (another process moved the row first: nothing is written).

**Dry run first.** `--dry-run` lists the selection (game, profile, recording date) without reading
a byte of any object or writing a row, and counts the `quarantined` rows it does not select,
grouped by reason class (the exception class before the first colon, the reclaim texts, the
wall-clock cap; counts only, never a reason's text or an object key).

**Bounded and resumable.** At most `--limit` rows per run (default 25: a validation can take up to
its 30 s wall-clock cap, and this runs from a terminal). When more remain, the report prints the
`--after` value that continues from the last row examined; a bare re-run starts again from the
oldest selected row.

`--after` is one value, `<timestamp>,<capture id>`: the recording's completion time (ISO 8601, with
an offset) and the capture's UUID, which together are the ordering key. The id is not optional:
two tracked profiles can have captured the same match, so several captures share one completion
time, and a run cut between them would lose the rest if only the timestamp were kept. A timestamp
without an id is refused (exit 1), never read as "after everything at that time". Copy the printed
value exactly.

**Environment** (nothing is read from a dotenv file: `.env.local` in this repository points at the
*production* Neon database, and the operator must name the target on the command line).

- A dry run needs `DATABASE_URL` only: Neon's **pooled** endpoint (no DDL, so not the direct one
  the migration runbook reserves for Alembic).
- A real run builds the object store the way the application does, through
  `aoe2stats_api.settings.Settings`, so it needs the application's complete environment
  (`.env.example` names every key) and `Settings`' own validation applies, including its rejection
  of an `S3_ENDPOINT_URL` that carries a bucket path. A missing or invalid key is named, never its
  value. Read access to the replay bucket is enough. `docs/runbooks/revalidate-quarantined.md` is
  the procedure.

Usage:
    uv run python scripts/ops/revalidate_quarantined.py --dry-run
    uv run python scripts/ops/revalidate_quarantined.py --limit 25
    uv run python scripts/ops/revalidate_quarantined.py --limit 25 \\
        --after 2026-09-30T12:00:00+00:00,3f2b8c1e-5a4d-4e6f-9a0b-1c2d3e4f5a6b

Exit: 0 when the run completed and no row had an integrity failure; 1 when the invocation is
refused (a missing or invalid environment variable, an `--after` that is not `<timestamp with
offset>,<capture id>`, a `--limit` below 1), when a row's object was missing or did not match its
checksum (after the report is printed), or when the object store failed in any other way (the run
stops there, after the report, with that row unwritten).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from collections.abc import Callable, Mapping
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_api.settings import Settings, missing_or_invalid_keys
from aoe2stats_core.replay.validation import ReplayValidator
from aoe2stats_ingester.capture import CaptureDrain, RevalidationCursor, RevalidationReport
from aoe2stats_providers.base import NotFound, ReplayBlob
from aoe2stats_storage.objects import ObjectStore, ObjectStoreConfig
from aoe2stats_storage.repositories.base import build_engine, build_session_factory

_DATABASE_URL_ENV = "DATABASE_URL"
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


class SettingsError(Exception):
    """The application's `Settings` could not be built from the environment. `str(exc)` names the
    keys and nothing else: never a value."""


def settings_from_environment(environ: Mapping[str, str]) -> Settings:
    """The application's own `Settings`, validated as the application validates it. Raises
    `SettingsError` naming the missing or invalid keys (`missing_or_invalid_keys` reads aliases,
    never the input values, which carry credentials)."""
    try:
        return Settings(**dict(environ))  # type: ignore[arg-type]  # keyed by the env aliases
    except ValidationError as exc:
        keys = missing_or_invalid_keys(exc)
        raise SettingsError(
            "the application's settings are not valid; missing or invalid: " + ", ".join(keys)
        ) from exc


def object_store_from_settings(settings: Settings) -> ObjectStore:
    """The replay bucket, configured from validated `Settings` the way
    `aoe2stats_api.ingest_stages.build_ingest_stages` configures it."""
    return ObjectStore(
        ObjectStoreConfig(
            endpoint_url=settings.s3_endpoint_url,
            bucket=settings.s3_bucket,
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key.get_secret_value(),
            region=settings.s3_region,
        )
    )


def default_validator() -> ReplayValidator:
    # Imported here: the engine is heavy and a dry run never needs it.
    from aoe2stats_replay_engine.aoe2rec import Aoe2RecValidator

    return Aoe2RecValidator()


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
            "Environment: a dry run needs DATABASE_URL (Neon pooled endpoint); a real run needs "
            "the application's complete environment (.env.example), validated by its Settings. "
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
    if report.aborted_by is not None:
        lines.append(
            f"revalidate-quarantined: STOPPED: the object store failed with {report.aborted_by}. "
            "The row it failed on was not written and no later row was examined."
        )
    cursor = report.cursor
    if report.truncated and cursor is not None and report.aborted_by is None:
        lines.append(
            "revalidate-quarantined: more candidates remain; continue with "
            f"--after {cursor[0].isoformat()},{cursor[1]}"
        )
    if report.unselected_by_reason is not None:
        total = sum(count for _, count in report.unselected_by_reason)
        lines.append(
            f"revalidate-quarantined: {total} other quarantined row(s) are outside the selection "
            "and not re-validated, by reason class:"
        )
        lines.extend(f"  {count:>5}  {label}" for label, count in report.unselected_by_reason)
    if dry_run:
        lines.append("revalidate-quarantined: dry run, nothing was read or written.")
    return lines


def exit_code(report: RevalidationReport) -> int:
    """1 when the run found an integrity failure or the store failed; the report is already
    printed, because what was found is what the operator needs."""
    integrity = any(o.outcome == "integrity_failure" for o in report.outcomes)
    return 1 if integrity or report.aborted_by is not None else 0


async def _run(
    argv: list[str] | None,
    environ: Mapping[str, str],
    *,
    make_object_store: Callable[[Settings], ObjectStore] = object_store_from_settings,
    make_validator: Callable[[], ReplayValidator] = default_validator,
) -> int:
    try:
        args = build_arg_parser(exit_on_error=False).parse_args(argv)
    except argparse.ArgumentError as exc:
        print(f"revalidate-quarantined: {exc}", file=sys.stderr)
        return 1
    if args.limit < 1:
        print("revalidate-quarantined: --limit must be at least 1.", file=sys.stderr)
        return 1

    object_store: ObjectStore | None = None
    validator: ReplayValidator | None = None
    if args.dry_run:
        database_url = environ.get(_DATABASE_URL_ENV)
        if not database_url:
            print(f"revalidate-quarantined: {_DATABASE_URL_ENV} is not set.", file=sys.stderr)
            return 1
    else:
        try:
            settings = settings_from_environment(environ)
        except SettingsError as exc:
            print(f"revalidate-quarantined: {exc}", file=sys.stderr)
            return 1
        database_url = settings.database_url
        object_store = make_object_store(settings)
        validator = make_validator()

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
    return exit_code(report)


def main(
    argv: list[str] | None = None,
    environ: Mapping[str, str] | None = None,
    *,
    make_object_store: Callable[[Settings], ObjectStore] = object_store_from_settings,
    make_validator: Callable[[], ReplayValidator] = default_validator,
) -> int:
    """The entry point. The two `make_*` parameters are the seams a test replaces; nothing else
    about the run differs from the command line."""
    return asyncio.run(
        _run(
            argv,
            os.environ if environ is None else environ,
            make_object_store=make_object_store,
            make_validator=make_validator,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
