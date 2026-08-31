#!/usr/bin/env python3
"""Backfill `match_players`' five Relic-derived columns from `matches.raw_payload` (T415).

**The gap this closes.** `upsert_match_player` (`apps/ingester/.../discover.py`) wrote only the
`(game_id, profile_id)` primary key until T413 gave it `civ_id`, `team_id`, `rating`,
`rating_diff` and `result` too — but that fix only reaches matches discovered *after* it ships.
Every row written before it carries those five columns `NULL`, which is US1's own acceptance test
("load a profile with known matches") failing on the first real profile it is pointed at. This
script is the one-time (and safely re-runnable) sweep over what is already on disk.

**Re-runnable by construction, not by a guard flag.** `backfill_match_players` re-derives its
candidate set from the current state of `match_players` on every call — a row this run just filled
is no longer a candidate the next time, and a row nothing has touched yet still is, whether that is
because the previous run never got to it or because it is new since. There is no "already ran"
marker to forget to check or to go stale.

**Reads `DATABASE_URL` from the environment, exactly like `acknowledge_alerts.py`: no
connection-string argument, no dotenv loading.** `.env.local` in this repository points at the
*production* Neon database (see that file's own comment) — a script that read it by default would
make "run the backfill" and "run it against production" the same act, silently. Loading a dotenv
file is deliberately absent here, not merely unused: the operator names the target explicitly, on
the command line, in the environment they choose to run this in.

**No provider call, ever (constitution IV).** Every byte the projection needs is already sitting in
`matches.raw_payload` — that is the whole reason a raw, unmodified copy of the provider's response
was kept. `packages/storage/src/aoe2stats_storage/repositories/matches.py`'s `project_match_player`
(T413) is applied directly here, never re-implemented: two copies of the same mapping is how the
two drift.

**`color_id` is never in this script's `SET` clause.** T413's own note: Relic's match history
response carries no such field, and T420's read-time enrichment is that column's only writer. A
Relic-only backfill that wrote `color_id` would overwrite a value that enrichment cached earlier
with `NULL`, on every re-run.

Usage (quickstart scenario 2):
    DATABASE_URL=postgresql+psycopg://... uv run python scripts/ops/backfill_match_players.py \\
        --dry-run
    DATABASE_URL=postgresql+psycopg://... uv run python scripts/ops/backfill_match_players.py

`--force` widens the candidate set to every `match_players` row with a parent `matches` row —
populated or not — and recomputes it from `raw_payload` regardless of what is already cached.
Without it, a row where all five columns are already non-`NULL` is left alone: a
partially-populated row (at least one of the five still `NULL`) is still filled in either way,
since it does not yet hold a complete, deliberately-cached answer to leave alone.

Exit: 0 whether or not anything needed writing; 1 if `DATABASE_URL` is not set.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_storage.models import Match, MatchPlayer
from aoe2stats_storage.repositories.base import build_engine, build_session_factory
from aoe2stats_storage.repositories.matches import project_match_player

_DATABASE_URL_ENV = "DATABASE_URL"


@dataclass(frozen=True, slots=True)
class BackfillReport:
    """What one run found and, if not a dry run, changed.

    A `match_players` row is a *candidate* this run when at least one of its five Relic-derived
    columns (`civ_id`, `team_id`, `result`, `rating`, `rating_diff` — never `color_id`, module
    docstring) is still `NULL`, unless `force=True` widens that to every row with a matching
    `matches.raw_payload`, populated or not.
    """

    candidates: int  # rows this run selected as needing a write
    updated: int  # rows actually written this run; always 0 when dry_run is True


def _candidate_statement(*, force: bool) -> Select[tuple[MatchPlayer, dict[str, Any]]]:
    stmt = select(MatchPlayer, Match.raw_payload).join(Match, Match.game_id == MatchPlayer.game_id)
    if force:
        return stmt
    return stmt.where(
        or_(
            MatchPlayer.civ_id.is_(None),
            MatchPlayer.team_id.is_(None),
            MatchPlayer.result.is_(None),
            MatchPlayer.rating.is_(None),
            MatchPlayer.rating_diff.is_(None),
        )
    )


async def backfill_match_players(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    dry_run: bool,
    force: bool = False,
) -> BackfillReport:
    """Select `match_players` rows (scoped by `force`, class docstring), apply T413's projection
    function to the parent `matches.raw_payload` — not a second copy of it — and, when `dry_run` is
    `False`, write the five columns. Issues no provider call: every byte it needs is already in
    `matches.raw_payload` (constitution IV). `dry_run=True` computes and reports the identical
    `candidates` count without executing a single `UPDATE`.
    """
    async with session_factory() as session:
        rows = (await session.execute(_candidate_statement(force=force))).all()
        candidates = len(rows)

        if dry_run:
            return BackfillReport(candidates=candidates, updated=0)

        updated = 0
        for player, raw_payload in rows:
            projected = project_match_player(raw_payload, player.profile_id)
            player.civ_id = projected.civ_id
            player.team_id = projected.team_id
            player.rating = projected.rating
            player.rating_diff = projected.rating_diff
            player.result = projected.result
            updated += 1

        if updated:
            await session.commit()

    return BackfillReport(candidates=candidates, updated=updated)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill match_players' five Relic-derived columns from matches.raw_payload. "
            "See scripts/ops/backfill_match_players.py's own module docstring."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report how many rows would be written, without writing anything",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="recompute every row, including ones already fully populated, not only NULL ones",
    )
    return parser


def _print_report(report: BackfillReport, *, dry_run: bool) -> None:
    verb = "Would update" if dry_run else "Updated"
    print(
        f"backfill-match-players: {report.candidates} candidate row(s); {verb} "
        f"{report.updated if not dry_run else report.candidates} row(s)."
    )
    if dry_run:
        print("backfill-match-players: dry run — pass without --dry-run to write.")


async def _run(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    database_url = os.environ.get(_DATABASE_URL_ENV)
    if not database_url:
        print(f"backfill-match-players: {_DATABASE_URL_ENV} is not set; nothing to back fill.")
        return 1

    session_factory = build_session_factory(build_engine(database_url))
    report = await backfill_match_players(session_factory, dry_run=args.dry_run, force=args.force)
    _print_report(report, dry_run=args.dry_run)
    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_run(argv))


if __name__ == "__main__":
    raise SystemExit(main())
