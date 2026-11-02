#!/usr/bin/env python3
"""Nightly civilisation-coverage check (T210, FR-013 to FR-016, quickstart scenarios 1 to 4).

Reports every civilisation identifier present in stored `match_players` rows that the mapping
(`aoe2stats_api.civilizations.civilisation_name`) cannot name. Contract:
`specs/002-reference-data-sources/contracts/civ-coverage-check.md`.

**The lookup never returns `None` for an unknown id.** It returns the fallback string
`Civilisation <id>`, so "the mapping cannot name this" is recognised by that exact shape, not by
a `None` check (which would report nothing forever).

Reads `DATABASE_URL` and, from `match_players`, only the distinct non-null `civ_id` values with a
row count each: no `profile_id`, alias or `game_id` is ever selected or printed (constitution IX;
the report lands in a public-by-default GitHub issue). Opens no network connection (FR-014).

Usage:  uv run scripts/checks/civ_coverage.py
Exit:   0 if at least one row was examined and every identifier is named; 1 if an identifier cannot
        be named, or if nothing could be examined (FR-015). The two failures print different text.
"""

from __future__ import annotations

import asyncio
import enum
import os

from sqlalchemy import func, select

from aoe2stats_api.civilizations import civilisation_name
from aoe2stats_storage.models import MatchPlayer
from aoe2stats_storage.repositories.base import build_engine, build_session_factory

_DATABASE_URL_ENV = "DATABASE_URL"

#: Identifiers never to be reported, each mapped to its reason (FR-016). Ships EMPTY on purpose.
#: An entry belongs here only when an id can never be named by any source (a modded value, a test
#: artefact). Ids 56 and 57 are unknown, not unnameable: a match arriving with one is the evidence
#: that would make it nameable, so pre-silencing them would discard the only signal this check
#: exists to produce.
DELIBERATELY_EXCLUDED_CIV_IDS: dict[int, str] = {}


class CoverageStatus(enum.Enum):
    """Not a bare pass/fail: the two failures send a maintainer to different places."""

    COVERED = "covered"
    GAP = "gap"
    NOTHING_EXAMINED = "nothing_examined"


def is_named(civ_id: int) -> bool:
    """False when the mapping answers with its documented `Civilisation <id>` fallback."""
    return civilisation_name(civ_id) != f"Civilisation {civ_id}"


def classify(counts: dict[int, int]) -> tuple[CoverageStatus, dict[int, int]]:
    """Return the status and the unnamed, non-excluded `{civ_id: row_count}` gaps."""
    if not counts:
        return CoverageStatus.NOTHING_EXAMINED, {}
    gaps = {
        civ_id: count
        for civ_id, count in sorted(counts.items())
        if civ_id not in DELIBERATELY_EXCLUDED_CIV_IDS and not is_named(civ_id)
    }
    return (CoverageStatus.GAP if gaps else CoverageStatus.COVERED), gaps


async def _run() -> int:
    database_url = os.environ.get(_DATABASE_URL_ENV)
    if not database_url:
        print(f"civ-coverage: {_DATABASE_URL_ENV} is not set; nothing to check against.")
        return 1

    engine = build_engine(database_url)
    try:
        session_factory = build_session_factory(engine)
        async with session_factory() as session:
            result = await session.execute(
                select(MatchPlayer.civ_id, func.count())
                .where(MatchPlayer.civ_id.is_not(None))
                .group_by(MatchPlayer.civ_id)
            )
            counts = {int(civ_id): int(count) for civ_id, count in result.all()}
    finally:
        await engine.dispose()

    status, gaps = classify(counts)

    if status is CoverageStatus.COVERED:
        print(f"civ-coverage: OK — all {len(counts)} civilisation identifiers present are named.")
        return 0

    if status is CoverageStatus.NOTHING_EXAMINED:
        print(
            "civ-coverage: FAIL — no match_players row carrying a civ_id was examined, so "
            "coverage is unknown (FR-015). Check the database connection and whether match data "
            "is being ingested (see cron-liveness)."
        )
        return 1

    print(
        f"civ-coverage: FAIL — {len(gaps)} civilisation identifier(s) in stored match data "
        "cannot be named by the mapping (aoe2stats_api/civilizations.py):"
    )
    for civ_id, count in gaps.items():
        print(f"  civ_id {civ_id}: {count} match_players rows")
    return 1


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
