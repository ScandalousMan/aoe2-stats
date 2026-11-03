"""Tests for the nightly civilisation-coverage check (T209, quickstart scenarios 1 to 4).

FR-013 asks for a nightly signal when stored match data carries a civilisation identifier the
mapping cannot name; FR-015 makes examining nothing a failure rather than a pass; FR-016 allows a
deliberate, reviewable exclusion collection that ships empty. `civ_coverage.py` (T210) is the check.
It is exercised against the real throwaway database (`tests/db.py`, T015), the way the nightly
workflow runs it: `DATABASE_URL` in the environment, an integer exit status, text on stdout.

The tests import the module inside their bodies so a failure to import is a failure of that test.

Contract assumptions T210 must honour (contracts/civ-coverage-check.md):

- `main() -> int` reads `DATABASE_URL`, prints the report to stdout and returns the exit status.
  It calls `asyncio.run` itself, like `cron_liveness.main`, so tests run it in a worker thread.
- The deliberate-exclusion collection is a module attribute named `DELIBERATELY_EXCLUDED_CIV_IDS`
  (a mapping of id to reason, or a set; only membership is used). It ships empty; tests inject
  entries with `monkeypatch.setattr`.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from tests.db import clean_database, database_url, db_session, engine, session_factory

from aoe2stats_storage.models import AoeProfile, Match, MatchPlayer

# Re-exported so ruff sees these names used: pytest discovers a fixture imported into a test module
# exactly as if it had been defined here (same mechanism as test_cron_liveness.py).
__all__ = ["clean_database", "database_url", "db_session", "engine", "session_factory"]


# Ids 0 and 1 are named in the mapping (Armenians, Aztecs). 99 is far past the highest named id.
# 56 is absent from every source but is unknown rather than unnameable (FR-016). 77 stands in for
# an identifier that can never be named by any source, and is only ever excluded by injection.
_COVERED_IDS = (0, 1)
_UNNAMED_ID = 99
_UNKNOWN_BUT_NAMEABLE_ID = 56
_EXCLUDED_ID = 77

# Values distinctive enough that their appearance in output cannot be a coincidence of formatting.
_PROFILE_ID_BASE = 987_654_300
_ALIAS_PREFIX = "zq_distinctive_alias_"
_GAME_ID = 7_654_321_098_765

_REPO_ROOT = Path(__file__).resolve().parents[3]


async def _seed(session: AsyncSession, rows: Sequence[int | None]) -> list[int]:
    """One match, one profile and one `match_players` row per entry of `rows` (the entry is the
    row's `civ_id`). Returns the profile ids used."""
    session.add(
        Match(
            game_id=_GAME_ID,
            leaderboard_id=3,
            completed_at=datetime.now(UTC),
            source="test",
            raw_payload={},
        )
    )
    profile_ids = [_PROFILE_ID_BASE + index for index in range(len(rows))]
    for index, profile_id in enumerate(profile_ids):
        session.add(AoeProfile(profile_id=profile_id, alias=f"{_ALIAS_PREFIX}{index}"))
    await session.flush()
    for profile_id, civ_id in zip(profile_ids, rows, strict=True):
        session.add(MatchPlayer(game_id=_GAME_ID, profile_id=profile_id, civ_id=civ_id))
    await session.commit()
    return profile_ids


async def _run_check(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], url: str
) -> tuple[int, str]:
    from scripts.checks.civ_coverage import main

    monkeypatch.setenv("DATABASE_URL", url)
    capsys.readouterr()
    status = await asyncio.to_thread(main)
    return status, capsys.readouterr().out


async def test_unnamed_identifier_is_reported_with_its_row_count(
    db_session: AsyncSession,
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Scenario 1: the unnamed id on four rows, plus covered rows. Exit 1; the output names that id
    and the count 4 on the same line."""
    await _seed(db_session, [_UNNAMED_ID] * 4 + [0, 1])

    status, out = await _run_check(monkeypatch, capsys, database_url)

    assert status == 1
    assert any(str(_UNNAMED_ID) in line and "4" in line for line in out.splitlines()), out


async def test_output_carries_no_profile_id_alias_or_game_id(
    db_session: AsyncSession,
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The contract's privacy floor (constitution IX): a failing report must identify the
    civilisation and the row count and nobody and no match."""
    profile_ids = await _seed(db_session, [_UNNAMED_ID] * 3 + [0])

    status, out = await _run_check(monkeypatch, capsys, database_url)

    assert status == 1
    assert out.strip(), "the report must not be empty on a failure"
    for profile_id in profile_ids:
        assert str(profile_id) not in out
    assert _ALIAS_PREFIX not in out
    assert str(_GAME_ID) not in out
    assert database_url not in out


async def test_fully_covered_database_exits_zero_and_names_nothing(
    db_session: AsyncSession,
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Scenario 2: every `civ_id` is inside the mapping. Exit 0 and no identifier reported."""
    await _seed(db_session, [0, 0, 1, None])

    status, out = await _run_check(monkeypatch, capsys, database_url)

    assert status == 0
    assert "Civilisation" not in out
    assert str(_UNNAMED_ID) not in out


async def test_empty_database_fails_with_a_message_distinct_from_a_coverage_gap(
    db_session: AsyncSession,
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Scenario 3 (FR-015): nothing examined is a failure, and says so in words that differ from
    the coverage-gap message — a status code alone sends a maintainer to the wrong place."""
    status, empty_out = await _run_check(monkeypatch, capsys, database_url)
    assert status == 1
    assert empty_out.strip()

    await _seed(db_session, [_UNNAMED_ID])
    gap_status, gap_out = await _run_check(monkeypatch, capsys, database_url)
    assert gap_status == 1

    assert empty_out != gap_out
    assert str(_UNNAMED_ID) in gap_out
    assert str(_UNNAMED_ID) not in empty_out

    await db_session.execute(delete(MatchPlayer))
    await db_session.commit()
    status_again, empty_again = await _run_check(monkeypatch, capsys, database_url)
    assert status_again == 1
    assert empty_again == empty_out


async def test_rows_with_only_null_civ_ids_count_as_nothing_examined(
    db_session: AsyncSession,
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The task text reads the distinct non-null `civ_id` values: rows that carry none leave
    nothing to examine, so the check must not pass over them."""
    await _seed(db_session, [None, None])

    status, _ = await _run_check(monkeypatch, capsys, database_url)

    assert status == 1


async def test_excluded_identifier_is_not_reported(
    db_session: AsyncSession,
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Scenario 4, steps 1-2: an identifier in the deliberate-exclusion collection is silent."""
    import scripts.checks.civ_coverage as civ_coverage

    monkeypatch.setattr(
        civ_coverage,
        "DELIBERATELY_EXCLUDED_CIV_IDS",
        {_EXCLUDED_ID: "test artefact, can never be named"},
    )
    await _seed(db_session, [_EXCLUDED_ID] * 3 + [0])

    status, out = await _run_check(monkeypatch, capsys, database_url)

    assert status == 0
    assert str(_EXCLUDED_ID) not in out


async def test_unknown_identifier_is_still_reported_beside_an_excluded_one(
    db_session: AsyncSession,
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Scenario 4, steps 3-4: id 56 is unknown rather than unnameable, so excluding another id must
    not silence it."""
    import scripts.checks.civ_coverage as civ_coverage

    monkeypatch.setattr(
        civ_coverage,
        "DELIBERATELY_EXCLUDED_CIV_IDS",
        {_EXCLUDED_ID: "test artefact, can never be named"},
    )
    await _seed(db_session, [_EXCLUDED_ID] * 3 + [_UNKNOWN_BUT_NAMEABLE_ID] * 2)

    status, out = await _run_check(monkeypatch, capsys, database_url)

    assert status == 1
    assert any(str(_UNKNOWN_BUT_NAMEABLE_ID) in line and "2" in line for line in out.splitlines())
    assert str(_EXCLUDED_ID) not in out


def test_exclusion_collection_ships_empty() -> None:
    """FR-016: ids 56 and 57 in particular must not be pre-silenced."""
    from scripts.checks.civ_coverage import DELIBERATELY_EXCLUDED_CIV_IDS

    assert len(DELIBERATELY_EXCLUDED_CIV_IDS) == 0


def test_importing_the_check_does_not_load_fastapi() -> None:
    """Plan post-design re-check: the check imports `civilisation_name` from the API package, the
    feature's one layering irregularity, and this test bounds it. A fresh interpreter is used
    because other tests in this session may already have imported fastapi."""
    probe = (
        "import sys\n"
        "import scripts.checks.civ_coverage\n"
        "sys.exit(1 if 'fastapi' in sys.modules else 0)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
