"""Projection unit tests for T412 — the fix for research.md's **D1**: `match_players.civ_id`,
`team_id`, `rating`, `rating_diff` and `result` have never been written (`upsert_match_player`
inserts only the primary key), even though every one of them is already sitting in
`matches.raw_payload`. This file is quickstart scenario 2's first half.

`aoe2stats_storage.repositories.matches` does not yet export a projection function — T413's task —
so every test below is `@pytest.mark.xfail(strict=True, reason="T413 not implemented yet")`
(CLAUDE.md's test-first convention, `apps/analyzer/tests/test_retain.py`'s own precedent for
writing the interface a sibling task must satisfy ahead of its own implementation) and imports the
not-yet-existent names **inside its own body**, never at module scope, so a `ModuleNotFoundError`
surfaces as the ordinary assertion-time failure `xfail` expects rather than a collection error that
would take the rest of `packages/storage/tests` down with it (`test_relic_matches.py`'s `_provider`
documents the identical reasoning).

## The contract this file defines for T413

`aoe2stats_storage.repositories.matches` gains:

- `ProjectedMatchPlayer` — a frozen dataclass carrying the five columns data-model.md's
  `match_players` table names: `civ_id: int | None`, `team_id: int | None`, `rating: int | None`,
  `rating_diff: int | None`, `result: str | None` (`"win"` / `"loss"` / `None`, never a third
  string — FR-004's neutral state, `data-model.md` §1).
- `project_match_player(raw_match: Mapping[str, Any], profile_id: int) -> ProjectedMatchPlayer` —
  pure, no I/O, no session: one entry of `matches.raw_payload` (a `matchHistoryStats[]` item, the
  shape `RawMatch.raw_payload` carries verbatim) plus the profile id `upsert_match_player`'s own
  call site (`DiscoverStage.__call__`, `apps/ingester/.../discover.py`) already loops over, in and
  a `MatchPlayer`-shaped result out. Rules, straight from data-model.md's `match_players` table:
    - `civ_id` <- `matchhistorymember[].civilization_id`, direct.
    - `team_id` <- `matchhistorymember[].teamid`, direct.
    - `rating` <- `matchhistorymember[].newrating`, the value *after* the match (FR-005).
    - `rating_diff` <- `newrating - oldrating`, signed, `NULL` — never `0` — the moment either
      side is absent: a `0` is a real, symmetric rating outcome and reads as "no change" to
      anyone downstream, while `NULL` is the only value that says "unknown".
    - `result` <- `matchhistorymember[].outcome`: `1` -> `"win"`, `0` -> `"loss"`, any other value
      (including a draw code this feature does not otherwise interpret) -> `None`, FR-004's
      neutral state, never silently coerced into `"loss"`.
- `MatchProjectionMismatch(ValueError)` — raised, not swallowed and not used to pick a side, the
  moment `civilization_id` / `teamid` / the mapped result disagrees between `matchhistorymember[]`
  and that same `profile_id`'s entry in `matchhistoryreportresults[]`. data-model.md is explicit
  that the second array is "the cross-check, not a second source": a silent tie-break here is
  exactly how a wrong civ would ship looking confident, and this exception is what stops that at
  the write, rather than at whichever pixel first looks wrong.

Every scenario below is built from
`packages/providers/fixtures/relic/get_recent_match_history.json` (a deep copy per test, mutated
locally — no test leaks state into another): its `matchHistoryStats[0]` (`game_id` 500615037)
already agrees, member for member, with its own `matchhistoryreportresults[]`, so the happy-path
tests use it untouched and the mismatch tests mutate exactly the one field under test.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

# `aoe2stats_storage.repositories.matches.ProjectedMatchPlayer` / `MatchProjectionMismatch` /
# `project_match_player` do not exist until T413 — see the module docstring's "contract this file
# defines for T413". Every reference to them below lives inside a test body, never at module scope
# (not even under `TYPE_CHECKING`, which would still need a real import to stay meaningful here),
# so a `ModuleNotFoundError` before T413 lands is the ordinary assertion-time failure `xfail`
# expects, not a collection-time failure for the whole file.

XFAIL_REASON = "T413 not implemented yet"

FIXTURES = Path(__file__).resolve().parents[2] / "providers" / "fixtures" / "relic"

# `matchHistoryStats[0]` (game 500615037): an 8-player team match whose `matchhistorymember[]`
# agrees with `matchhistoryreportresults[]` on every participant (measured against the fixture
# directly) — the clean base every happy-path test mutates from, if at all.
_LOSING_PROFILE_ID = 264353  # civ 28, team 1, outcome 0 (loss), old 1512 -> new 1498
_WINNING_PROFILE_ID = 196240  # civ 42, team 2, outcome 1 (win), old 1698 -> new 1704


def _load_raw_match(index: int = 0) -> dict[str, Any]:
    """One `matchHistoryStats[]` entry, deep-copied out of the fixture so a test mutating it can
    never leak that mutation into another test running against the same file."""
    body = json.loads((FIXTURES / "get_recent_match_history.json").read_text(encoding="utf-8"))
    return copy.deepcopy(body["matchHistoryStats"][index])


def _member(raw_match: dict[str, Any], profile_id: int) -> dict[str, Any]:
    return next(
        entry for entry in raw_match["matchhistorymember"] if entry["profile_id"] == profile_id
    )


def _report(raw_match: dict[str, Any], profile_id: int) -> dict[str, Any]:
    return next(
        entry
        for entry in raw_match["matchhistoryreportresults"]
        if entry["profile_id"] == profile_id
    )


# --- civ_id / team_id: direct from matchhistorymember --------------------------------------------


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON)
def test_civ_id_and_team_id_are_mapped_directly_from_the_fixture() -> None:
    from aoe2stats_storage.repositories.matches import project_match_player

    raw_match = _load_raw_match()
    member = _member(raw_match, _LOSING_PROFILE_ID)

    projected = project_match_player(raw_match, _LOSING_PROFILE_ID)

    assert projected.civ_id == member["civilization_id"] == 28
    assert projected.team_id == member["teamid"] == 1


# --- rating: newrating, the value after the match (FR-005) ---------------------------------------


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON)
def test_rating_is_newrating_not_oldrating() -> None:
    from aoe2stats_storage.repositories.matches import project_match_player

    raw_match = _load_raw_match()
    member = _member(raw_match, _WINNING_PROFILE_ID)
    assert member["oldrating"] != member["newrating"], "fixture must exercise a real rating move"

    projected = project_match_player(raw_match, _WINNING_PROFILE_ID)

    assert projected.rating == member["newrating"] == 1704
    assert projected.rating != member["oldrating"]


# --- rating_diff: signed newrating - oldrating, NULL (never 0) when either side is missing -------


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON)
def test_rating_diff_is_signed_newrating_minus_oldrating() -> None:
    from aoe2stats_storage.repositories.matches import project_match_player

    raw_match = _load_raw_match()

    losing = project_match_player(raw_match, _LOSING_PROFILE_ID)
    winning = project_match_player(raw_match, _WINNING_PROFILE_ID)

    assert losing.rating_diff == 1498 - 1512 == -14
    assert winning.rating_diff == 1704 - 1698 == 6


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON)
def test_rating_diff_is_null_not_zero_when_oldrating_is_missing() -> None:
    from aoe2stats_storage.repositories.matches import project_match_player

    raw_match = _load_raw_match()
    member = _member(raw_match, _LOSING_PROFILE_ID)
    del member["oldrating"]

    projected = project_match_player(raw_match, _LOSING_PROFILE_ID)

    assert projected.rating_diff is None, (
        "a missing side must project to NULL — a 0 here would read as a real, symmetric rating "
        "outcome rather than 'unknown'"
    )
    assert projected.rating_diff != 0


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON)
def test_rating_diff_is_null_not_zero_when_newrating_is_missing() -> None:
    from aoe2stats_storage.repositories.matches import project_match_player

    raw_match = _load_raw_match()
    member = _member(raw_match, _WINNING_PROFILE_ID)
    del member["newrating"]

    projected = project_match_player(raw_match, _WINNING_PROFILE_ID)

    assert projected.rating_diff is None
    assert projected.rating_diff != 0
    # FR-005 shows the post-match rating; with `newrating` itself missing there is none to show.
    assert projected.rating is None


# --- result: outcome 1 -> win, 0 -> loss, a third value -> NULL (FR-004's neutral state) ---------


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON)
def test_outcome_one_maps_to_win() -> None:
    from aoe2stats_storage.repositories.matches import project_match_player

    raw_match = _load_raw_match()
    assert _member(raw_match, _WINNING_PROFILE_ID)["outcome"] == 1

    projected = project_match_player(raw_match, _WINNING_PROFILE_ID)

    assert projected.result == "win"


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON)
def test_outcome_zero_maps_to_loss() -> None:
    from aoe2stats_storage.repositories.matches import project_match_player

    raw_match = _load_raw_match()
    assert _member(raw_match, _LOSING_PROFILE_ID)["outcome"] == 0

    projected = project_match_player(raw_match, _LOSING_PROFILE_ID)

    assert projected.result == "loss"


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON)
def test_a_third_outcome_value_maps_to_null_not_a_coerced_loss() -> None:
    """FR-004: a result that is neither win nor loss (a draw code, or anything else Relic might
    ever send) is its own neutral state, not silently folded into a loss. Both `outcome` and the
    cross-check's `resulttype` are set to the same third value here, deliberately: this test is
    about the `outcome` mapping alone, so the cross-check (its own tests, below) is kept in
    agreement rather than incidentally exercised.
    """
    from aoe2stats_storage.repositories.matches import project_match_player

    raw_match = _load_raw_match()
    _member(raw_match, _LOSING_PROFILE_ID)["outcome"] = 3
    _report(raw_match, _LOSING_PROFILE_ID)["resulttype"] = 3

    projected = project_match_player(raw_match, _LOSING_PROFILE_ID)

    assert projected.result is None
    assert projected.result != "loss"
    assert projected.result != "win"


# --- matchhistoryreportresults[] is a cross-check: a disagreement raises, never a tie-break ------


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON)
def test_a_civ_id_disagreement_with_report_results_raises() -> None:
    from aoe2stats_storage.repositories.matches import MatchProjectionMismatch, project_match_player

    raw_match = _load_raw_match()
    _report(raw_match, _LOSING_PROFILE_ID)["civilization_id"] = 99

    with pytest.raises(MatchProjectionMismatch):
        project_match_player(raw_match, _LOSING_PROFILE_ID)


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON)
def test_a_team_id_disagreement_with_report_results_raises() -> None:
    from aoe2stats_storage.repositories.matches import MatchProjectionMismatch, project_match_player

    raw_match = _load_raw_match()
    report = _report(raw_match, _LOSING_PROFILE_ID)
    assert report["teamid"] == 1
    report["teamid"] = 2

    with pytest.raises(MatchProjectionMismatch):
        project_match_player(raw_match, _LOSING_PROFILE_ID)


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON)
def test_a_result_disagreement_with_report_results_raises() -> None:
    """`matchhistorymember[].outcome` says loss (`0`); `matchhistoryreportresults[].resulttype` is
    flipped to `1` (win) for the same participant here — the two must agree, and a projection that
    silently trusted one over the other is exactly the "wrong civ ships looking confident" failure
    mode `data-model.md` calls out this cross-check to prevent.
    """
    from aoe2stats_storage.repositories.matches import MatchProjectionMismatch, project_match_player

    raw_match = _load_raw_match()
    assert _member(raw_match, _LOSING_PROFILE_ID)["outcome"] == 0
    report = _report(raw_match, _LOSING_PROFILE_ID)
    assert report["resulttype"] == 0
    report["resulttype"] = 1

    with pytest.raises(MatchProjectionMismatch):
        project_match_player(raw_match, _LOSING_PROFILE_ID)


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON)
def test_an_unmodified_fixture_entry_never_raises_the_cross_check() -> None:
    """The negative space of the four tests above: `matchHistoryStats[0]` agrees with its own
    `matchhistoryreportresults[]` for every participant, unmodified, so projecting every one of
    them must succeed — the cross-check is a guard against disagreement, not a blanket rejection
    of the array's mere presence.
    """
    from aoe2stats_storage.repositories.matches import project_match_player

    raw_match = _load_raw_match()
    profile_ids = [member["profile_id"] for member in raw_match["matchhistorymember"]]
    assert len(profile_ids) == 8

    for profile_id in profile_ids:
        project_match_player(raw_match, profile_id)  # must not raise
