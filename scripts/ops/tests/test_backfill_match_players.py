"""Tests for `scripts/ops/backfill_match_players.py` (T414), encoding quickstart scenario 2's
second half — the "load-bearing scenario" against a real row, not the projection's own unit tests
(`packages/storage/tests/test_match_projection.py`, T412, which own `outcome` -> `result`,
`rating_diff` nulling and the `matchhistoryreportresults` cross-check raise; none of that is
re-proven here).

**`scripts/ops/backfill_match_players.py` does not exist yet.** Every test below is marked
`@pytest.mark.xfail(strict=True, reason="T415 not implemented yet")` and imports the module inside
its own body, never at module scope — a module-scope import of a module that does not exist yet is
a collection error that fails the whole file, not one test. `strict=True` is what forces T415 to
remove each marker rather than leaving a stale one that would hide a regression the moment the
script lands wrong. `T413's` projection function
(`packages/storage/src/aoe2stats_storage/repositories/matches.py`) does not exist yet either at the
time this file is written — a test below can therefore fail for either reason, and both collapse to
the same "T415 not implemented yet" in effect, since T415 depends on T413 to exist at all.

**Follows `scripts/ops/tests/test_acknowledge_alerts.py`'s own precedent**: the script lives in
`scripts/ops/`, so its tests do too (`scripts/ops/tests` is its own `testpaths` entry,
`pyproject.toml`), and this file seeds a real throwaway Postgres database directly through the
storage models (`tests/db.py`, T015) exactly the way `packages/storage/tests/repositories/
test_matches.py` seeds `Match`/`MatchPlayer`/`AoeProfile` — this script reads and writes those
tables from *outside* the application, exactly as an operator running it against production would.

**Interface this file assumes of `scripts/ops/backfill_match_players.py`, and T415 implements
exactly**, reconstructed from this task's own text and quickstart scenario 2
(`uv run python scripts/ops/backfill_match_players.py --dry-run`, `DATABASE_URL` from the
environment, no dotenv — `acknowledge_alerts.py`'s own convention):

    @dataclass(frozen=True, slots=True)
    class BackfillReport:
        A `match_players` row is a *candidate* this run when at least one of its five
        Relic-derived columns (`civ_id`, `team_id`, `result`, `rating`, `rating_diff` — never
        `color_id`, T413's own note: only the read-time enrichment T420 writes that column) is
        still `NULL`, unless `force=True` widens that to every row with a matching `matches.
        raw_payload`, populated or not.

        candidates: int  # rows this run selected as needing a write
        updated: int     # rows actually written this run; always 0 when dry_run is True

    async def backfill_match_players(
        session_factory: async_sessionmaker[AsyncSession],
        *,
        dry_run: bool,
        force: bool = False,
    ) -> BackfillReport:
        Selects `match_players` rows (scoped by `force` as above), applies T413's projection
        function to the parent `matches.raw_payload` — not a second copy of it — and, when
        `dry_run` is `False`, writes the five columns. Issues no provider call: every byte it
        needs is already in `matches.raw_payload` (constitution IV). `dry_run=True` computes and
        reports the identical `candidates` count without executing a single `UPDATE`.

    def build_arg_parser() -> argparse.ArgumentParser:
        `--dry-run` (`store_true`, default `False`) and `--force` (`store_true`, default `False`),
        the two flags quickstart scenario 2 and this task's own text name.

If T415 lands with a different shape, this file is what gets updated — not evidence that the
assumption above was wrong to make.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.db import clean_database, database_url, db_session, engine, session_factory

from aoe2stats_storage.models import AoeProfile, Match, MatchPlayer, ProviderCall

# See scripts/checks/tests/test_cron_liveness.py for why these are re-exported this way.
__all__ = ["clean_database", "database_url", "db_session", "engine", "session_factory"]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURE_PATH = (
    _REPO_ROOT / "packages" / "providers" / "fixtures" / "relic" / "get_recent_match_history.json"
)

# Both participants below are read straight from `matchHistoryStats[0]` of the fixture, the same
# one T412's projection tests are built against, so this file commits to no fixture data of its
# own. Verified by hand against the fixture at the time this file was written:
#
#   entry["id"] == 500615037, entry["matchtype_id"] == 0, entry["mapname"] == "my map"
#   member profile_id=264353: civilization_id=28, teamid=1, newrating=1498, oldrating=1512,
#       outcome=0  -> civ_id=28, team_id=1, rating=1498, rating_diff=-14, result="loss"
#   member profile_id=196240: civilization_id=42, teamid=2, newrating=1704, oldrating=1698,
#       outcome=1  -> civ_id=42, team_id=2, rating=1704, rating_diff=6,  result="win"
#
# Neither participant's `matchhistorymember` entry disagrees with its own
# `matchhistoryreportresults` entry (T412's own concern) — this file is not testing that raise.
_GAME_ID = 500615037
_PROFILE_LOSS = 264353
_PROFILE_WIN = 196240

_EXPECTED_LOSS = {
    "civ_id": 28,
    "team_id": 1,
    "result": "loss",
    "rating": 1498,
    "rating_diff": -14,
}
_EXPECTED_WIN = {
    "civ_id": 42,
    "team_id": 2,
    "result": "win",
    "rating": 1704,
    "rating_diff": 6,
}

# Deliberately not what the fixture would project — distinguishable from both `_EXPECTED_LOSS` and
# a fresh `NULL` row, so a test can tell "left alone" apart from "recomputed" apart from "never
# populated at all".
_WRONG_CACHED_VALUES = {
    "civ_id": 1,
    "team_id": 9,
    "result": "win",
    "rating": 1,
    "rating_diff": 1,
}


def _load_fixture_entry() -> dict[str, Any]:
    with _FIXTURE_PATH.open() as handle:
        body = json.load(handle)
    entry: dict[str, Any] = body["matchHistoryStats"][0]
    assert entry["id"] == _GAME_ID, "fixture's first entry moved — update this file's expectations"
    return entry


async def _seed_profile(session: AsyncSession, *, profile_id: int) -> None:
    session.add(AoeProfile(profile_id=profile_id, alias=str(profile_id)))
    await session.flush()


async def _seed_match(session: AsyncSession, *, entry: dict[str, Any]) -> None:
    session.add(
        Match(
            game_id=entry["id"],
            leaderboard_id=entry["matchtype_id"],
            map_name=entry["mapname"],
            completed_at=datetime.fromtimestamp(entry["completiontime"], tz=UTC),
            source="relic",
            raw_payload=entry,
        )
    )
    await session.flush()


async def _seed_match_player(
    session: AsyncSession,
    *,
    profile_id: int,
    civ_id: int | None = None,
    team_id: int | None = None,
    result: str | None = None,
    rating: int | None = None,
    rating_diff: int | None = None,
) -> None:
    session.add(
        MatchPlayer(
            game_id=_GAME_ID,
            profile_id=profile_id,
            civ_id=civ_id,
            team_id=team_id,
            result=result,
            rating=rating,
            rating_diff=rating_diff,
        )
    )
    await session.flush()


async def _fetch_match_player(session: AsyncSession, *, profile_id: int) -> MatchPlayer:
    result = await session.execute(
        select(MatchPlayer).where(
            MatchPlayer.game_id == _GAME_ID, MatchPlayer.profile_id == profile_id
        )
    )
    return result.scalars().one()


def _five_columns(row: MatchPlayer) -> dict[str, Any]:
    return {
        "civ_id": row.civ_id,
        "team_id": row.team_id,
        "result": row.result,
        "rating": row.rating,
        "rating_diff": row.rating_diff,
    }


async def _provider_call_count(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        result = await session.execute(select(func.count()).select_from(ProviderCall))
        return int(result.scalar_one())


async def _seed_two_unfilled_participants(session: AsyncSession) -> None:
    entry = _load_fixture_entry()
    await _seed_match(session, entry=entry)
    await _seed_profile(session, profile_id=_PROFILE_LOSS)
    await _seed_profile(session, profile_id=_PROFILE_WIN)
    await _seed_match_player(session, profile_id=_PROFILE_LOSS)
    await _seed_match_player(session, profile_id=_PROFILE_WIN)


# --- dry-run writes nothing ----------------------------------------------------------------------


async def test_dry_run_reports_a_count_and_writes_nothing(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
) -> None:
    from scripts.ops.backfill_match_players import backfill_match_players

    async with session_factory() as session:
        await _seed_two_unfilled_participants(session)
        await session.commit()

    async with session_factory() as session:
        before_loss = _five_columns(await _fetch_match_player(session, profile_id=_PROFILE_LOSS))
        before_win = _five_columns(await _fetch_match_player(session, profile_id=_PROFILE_WIN))

    report = await backfill_match_players(session_factory, dry_run=True)

    assert report.candidates == 2
    assert report.updated == 0, "a dry run must never write, whatever the printed count says"

    # The assertion this test exists for: compare the table before and after, not the report.
    async with session_factory() as session:
        after_loss = _five_columns(await _fetch_match_player(session, profile_id=_PROFILE_LOSS))
        after_win = _five_columns(await _fetch_match_player(session, profile_id=_PROFILE_WIN))
    assert after_loss == before_loss
    assert after_win == before_win
    assert all(value is None for value in after_loss.values())
    assert all(value is None for value in after_win.values())


# --- a real run fills the five columns from raw_payload -------------------------------------------


async def test_a_real_run_fills_the_columns_from_raw_payload_via_the_projection(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
) -> None:
    from scripts.ops.backfill_match_players import backfill_match_players

    async with session_factory() as session:
        await _seed_two_unfilled_participants(session)
        await session.commit()

    report = await backfill_match_players(session_factory, dry_run=False)

    assert report.candidates == 2
    assert report.updated == 2

    async with session_factory() as session:
        loss_row = await _fetch_match_player(session, profile_id=_PROFILE_LOSS)
        win_row = await _fetch_match_player(session, profile_id=_PROFILE_WIN)

    assert _five_columns(loss_row) == _EXPECTED_LOSS
    assert _five_columns(win_row) == _EXPECTED_WIN
    # `color_id` is never in this script's SET clause (T413's own note) — only the read-time
    # enrichment (T420) ever writes it, and a Relic-only backfill must not null out a colour
    # cached earlier by writing over a column it has no business touching.
    assert loss_row.color_id is None
    assert win_row.color_id is None


# --- a second run is a no-op ----------------------------------------------------------------------


async def test_a_second_run_reports_zero_rows_changed(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
) -> None:
    from scripts.ops.backfill_match_players import backfill_match_players

    async with session_factory() as session:
        await _seed_two_unfilled_participants(session)
        await session.commit()

    first = await backfill_match_players(session_factory, dry_run=False)
    assert first.updated == 2

    second = await backfill_match_players(session_factory, dry_run=False)
    assert second.candidates == 0
    assert second.updated == 0

    async with session_factory() as session:
        loss_row = await _fetch_match_player(session, profile_id=_PROFILE_LOSS)
        win_row = await _fetch_match_player(session, profile_id=_PROFILE_WIN)
    assert _five_columns(loss_row) == _EXPECTED_LOSS
    assert _five_columns(win_row) == _EXPECTED_WIN


# --- an already-populated row is left alone unless --force ----------------------------------------


async def test_an_already_populated_row_is_left_alone_without_force(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
) -> None:
    from scripts.ops.backfill_match_players import backfill_match_players

    entry = _load_fixture_entry()
    async with session_factory() as session:
        await _seed_match(session, entry=entry)
        await _seed_profile(session, profile_id=_PROFILE_LOSS)
        await _seed_match_player(session, profile_id=_PROFILE_LOSS, **_WRONG_CACHED_VALUES)
        await session.commit()

    report = await backfill_match_players(session_factory, dry_run=False, force=False)

    assert report.candidates == 0
    assert report.updated == 0

    async with session_factory() as session:
        row = await _fetch_match_player(session, profile_id=_PROFILE_LOSS)
    assert _five_columns(row) == _WRONG_CACHED_VALUES, (
        "a fully-populated row must never be recomputed without --force"
    )


async def test_force_recomputes_an_already_populated_row(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
) -> None:
    from scripts.ops.backfill_match_players import backfill_match_players

    entry = _load_fixture_entry()
    async with session_factory() as session:
        await _seed_match(session, entry=entry)
        await _seed_profile(session, profile_id=_PROFILE_LOSS)
        await _seed_match_player(session, profile_id=_PROFILE_LOSS, **_WRONG_CACHED_VALUES)
        await session.commit()

    report = await backfill_match_players(session_factory, dry_run=False, force=True)

    assert report.candidates == 1
    assert report.updated == 1

    async with session_factory() as session:
        row = await _fetch_match_player(session, profile_id=_PROFILE_LOSS)
    assert _five_columns(row) == _EXPECTED_LOSS


async def test_a_partially_populated_row_is_still_a_candidate_without_force(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
) -> None:
    """One column already correct, the other four still `NULL` — the row is not "already
    populated" as a whole, so it is filled the same as a fully-`NULL` one, no `--force` needed."""
    from scripts.ops.backfill_match_players import backfill_match_players

    entry = _load_fixture_entry()
    async with session_factory() as session:
        await _seed_match(session, entry=entry)
        await _seed_profile(session, profile_id=_PROFILE_LOSS)
        await _seed_match_player(session, profile_id=_PROFILE_LOSS, civ_id=_EXPECTED_LOSS["civ_id"])
        await session.commit()

    report = await backfill_match_players(session_factory, dry_run=False, force=False)

    assert report.candidates == 1
    assert report.updated == 1

    async with session_factory() as session:
        row = await _fetch_match_player(session, profile_id=_PROFILE_LOSS)
    assert _five_columns(row) == _EXPECTED_LOSS


# --- the run issues no outbound request at all --------------------------------------------------
#
# The assertion this task exists for. The bytes are already on disk under constitution IV; a
# backfill that re-fetches is a capture-path load for data this service already holds. Asserted
# against the real `provider_calls` sink (`ProviderCall`, `packages/storage/src/
# aoe2stats_storage/models.py`) — the same table `AsyncBaseProvider`/`SyncBaseProvider` write to on
# every attempt, success or failure — never a call counter this file invents, the same discipline
# `apps/api/tests/test_player_search.py` already applies to `search_players`.


async def test_the_run_issues_no_outbound_request_at_all(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
) -> None:
    from scripts.ops.backfill_match_players import backfill_match_players

    async with session_factory() as session:
        await _seed_two_unfilled_participants(session)
        await session.commit()

    assert await _provider_call_count(session_factory) == 0

    await backfill_match_players(session_factory, dry_run=False)

    assert await _provider_call_count(session_factory) == 0, (
        "a backfill that issues a provider call is re-fetching data already on disk in "
        "matches.raw_payload — constitution IV's whole point of keeping the raw"
    )


# --- the CLI names the two flags quickstart scenario 2 exercises ----------------------------------


def test_build_arg_parser_exposes_dry_run_and_force_flags() -> None:
    from scripts.ops.backfill_match_players import build_arg_parser

    parser = build_arg_parser()

    default_args = parser.parse_args([])
    assert default_args.dry_run is False
    assert default_args.force is False

    flagged_args = parser.parse_args(["--dry-run", "--force"])
    assert flagged_args.dry_run is True
    assert flagged_args.force is True
