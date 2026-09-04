"""Unit tests for `aoe2stats_api.match_types` (T410, defect fix).

`routers/matches.py`'s two serialisers named `matches.leaderboard_id` — which stores Relic's
`matchtype_id`, `getRecentMatchHistory`'s own id space — through `leaderboards.py`'s
`leaderboard_name`, the table for `getPersonalStat`'s *different* `leaderboard_id` space. A real
match with `matchtype_id 6` therefore rendered the "Leaderboard 6" fallback instead of "1v1 Random
Map". This module is the correct namer for `matchtype_id`; these tests guard it the same way
`test_civilizations.py` guards `civilizations.py` — a fixture-derived join wherever this
repository's own frozen fixtures happen to overlap on a nameable id, plus the table's own literal
values and its fallback.
"""

from __future__ import annotations

import json
from pathlib import Path

from aoe2stats_api.match_types import KNOWN_MATCH_TYPE_NAMES, match_type_name

_FIXTURES = Path(__file__).resolve().parents[3] / "packages" / "providers" / "fixtures"
_RELIC_MATCH_HISTORY = json.loads(
    (_FIXTURES / "relic" / "get_recent_match_history.json").read_text()
)
_COMPANION_MATCHES = json.loads((_FIXTURES / "companion" / "matches.json").read_text())


def _matchtype_id_by_match() -> dict[int, int]:
    """Relic's `getRecentMatchHistory` fixture: one `matchtype_id` per match id, never a name
    (this module's own docstring)."""
    return {
        match["id"]: match["matchtype_id"]
        for match in _RELIC_MATCH_HISTORY["matchHistoryStats"]
        if "matchtype_id" in match
    }


def _leaderboard_id_and_name_by_match() -> dict[int, tuple[int, str]]:
    """The companion fixture: one `(internalLeaderboardId, leaderboardName)` pair per match id —
    the same key Relic's `matchHistoryStats[].id` carries."""
    return {
        match["matchId"]: (match["internalLeaderboardId"], match["leaderboardName"])
        for match in _COMPANION_MATCHES["matches"]
        if "internalLeaderboardId" in match and "leaderboardName" in match
    }


def test_table_matches_the_fixture_derived_join() -> None:
    """Re-derives the mapping from the two frozen fixtures independently of the table under test,
    then asserts every `matchtype_id` the join recovers agrees with `match_type_name`.

    Guards explicitly against a vacuous pass, the same discipline `test_civilizations.py`'s own
    equivalent test carries: if the fixtures stop overlapping on a match id, this fails on the
    non-empty assertion rather than passing over an empty set.
    """
    matchtype_ids = _matchtype_id_by_match()
    companion_pairs = _leaderboard_id_and_name_by_match()

    overlapping_keys = matchtype_ids.keys() & companion_pairs.keys()
    assert overlapping_keys, "the two fixtures no longer share a single match id"

    recovered: dict[int, str] = {}
    conflicts: list[tuple[int, str, str]] = []
    for key in overlapping_keys:
        matchtype_id = matchtype_ids[key]
        internal_leaderboard_id, leaderboard_name_value = companion_pairs[key]
        assert matchtype_id == internal_leaderboard_id, (
            f"match {key}: Relic matchtype_id {matchtype_id} != companion "
            f"internalLeaderboardId {internal_leaderboard_id} — the two sources disagree on "
            "whether these ids are the same id space"
        )
        if matchtype_id in recovered and recovered[matchtype_id] != leaderboard_name_value:
            conflicts.append((matchtype_id, recovered[matchtype_id], leaderboard_name_value))
        recovered[matchtype_id] = leaderboard_name_value

    assert not conflicts, f"the fixtures disagree with themselves on a matchtype id: {conflicts}"

    mismatches = {
        matchtype_id: (expected_name, match_type_name(matchtype_id))
        for matchtype_id, expected_name in recovered.items()
        if match_type_name(matchtype_id) != expected_name
    }
    assert not mismatches, (
        f"KNOWN_MATCH_TYPE_NAMES disagrees with the fixture-derived join: {mismatches}"
    )


def test_table_holds_the_four_confirmed_pairs() -> None:
    assert KNOWN_MATCH_TYPE_NAMES == {
        0: "Unranked",
        6: "1v1 Random Map",
        7: "Team Random Map",
        9: "Team Random Map",
    }


def test_names_unranked() -> None:
    assert match_type_name(0) == "Unranked"


def test_names_one_v_one_random_map() -> None:
    assert match_type_name(6) == "1v1 Random Map"


def test_distinct_team_random_map_ids_share_one_name() -> None:
    """7 and 9 are distinct team sizes in this id space (module docstring) — both confirmed
    against companion's own `leaderboardName`, and both name the same thing."""
    assert match_type_name(7) == "Team Random Map"
    assert match_type_name(9) == "Team Random Map"


def test_falls_back_for_an_unrecognised_id() -> None:
    """An id this module cannot confidently name still renders — as "Leaderboard <id>", never a
    guessed name (FR-020), the identical fallback wording the match page showed before this fix."""
    assert match_type_name(999) == "Leaderboard 999"
