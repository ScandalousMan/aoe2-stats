"""Unit tests for `aoe2stats_api.civilizations` (T070c, corrected T070g).

T070c's table named ids 1-13 confidently and wrongly (module docstring). This suite no longer
takes the table on trust: `test_table_matches_the_fixture_derived_join` re-runs the join that
established it — `packages/providers/fixtures/relic/get_recent_match_history.json` against
`packages/providers/fixtures/companion/matches.json`, on `(match id, profile id)` — every time the
suite runs, so a table edited back toward T070c's error, or drifted any other way, fails loudly
instead of being trusted again by accident.
"""

from __future__ import annotations

import json
from pathlib import Path

from aoe2stats_api.civilizations import civilisation_name

_FIXTURES = Path(__file__).resolve().parents[3] / "packages" / "providers" / "fixtures"
_RELIC_MATCH_HISTORY = json.loads(
    (_FIXTURES / "relic" / "get_recent_match_history.json").read_text()
)
_COMPANION_MATCHES = json.loads((_FIXTURES / "companion" / "matches.json").read_text())

# The companion source spells this civilisation "Inca" (singular) where the game itself, and this
# module's table, use "Incas". Normalising that away silently would risk masking a genuine
# mismatch on some other name, so it is spelled out once, here, as the one known exception.
_COMPANION_SPELLING_EXCEPTIONS = {"Inca": "Incas"}


def _civilization_id_by_match_and_profile() -> dict[tuple[int, int], int]:
    """Relic's `getRecentMatchHistory` fixture: one `civilization_id` per `(match id, profile
    id)`, never a name (`docs/data-sources.md` §1)."""
    pairs: dict[tuple[int, int], int] = {}
    for match in _RELIC_MATCH_HISTORY["matchHistoryStats"]:
        match_id = match["id"]
        for member in match["matchhistorymember"]:
            pairs[(match_id, member["profile_id"])] = member["civilization_id"]
    return pairs


def _civilization_name_by_match_and_profile() -> dict[tuple[int, int], str]:
    """The companion fixture: one `civName` per `(match id, profile id)`, the same key Relic's
    `matchHistoryStats[].id` / `matchhistorymember[].profile_id` carries, sourced from
    `matches[].teams[].players[].profileId`."""
    names: dict[tuple[int, int], str] = {}
    for match in _COMPANION_MATCHES["matches"]:
        match_id = match["matchId"]
        for team in match["teams"]:
            for player in team["players"]:
                names[(match_id, player["profileId"])] = player["civName"]
    return names


def test_table_matches_the_fixture_derived_join() -> None:
    """Re-derives the mapping from the two frozen fixtures independently of the table under test,
    then asserts every civilisation id the join recovers agrees with `civilisation_name`.

    Guards explicitly against a vacuous pass: T015a and T038b were both a test that asserted
    nothing because it silently found nothing. If the fixtures stop overlapping, or overlap on
    fewer ids than today, this fails on the count assertion rather than passing over an empty set.
    """
    civ_ids = _civilization_id_by_match_and_profile()
    civ_names = _civilization_name_by_match_and_profile()

    overlapping_keys = civ_ids.keys() & civ_names.keys()
    assert overlapping_keys, "the two fixtures no longer share a single (match, profile) pair"

    recovered: dict[int, str] = {}
    conflicts: list[tuple[int, str, str]] = []
    for key in overlapping_keys:
        civ_id = civ_ids[key]
        civ_name = _COMPANION_SPELLING_EXCEPTIONS.get(civ_names[key], civ_names[key])
        if civ_id in recovered and recovered[civ_id] != civ_name:
            conflicts.append((civ_id, recovered[civ_id], civ_name))
        recovered[civ_id] = civ_name

    assert not conflicts, f"the fixtures disagree with themselves on a civilisation id: {conflicts}"

    # 21 distinct ids today (three recur across two different matches and agree both times, per
    # the module docstring). A number lower than this — not just zero — means the fixtures still
    # overlap but cover less ground than the derivation was checked against.
    assert len(recovered) >= 21, (
        f"only recovered {len(recovered)} civilisation ids from the fixture join, expected >= 21 "
        "— the fixtures may have changed under this test"
    )

    mismatches = {
        civ_id: (expected_name, civilisation_name(civ_id))
        for civ_id, expected_name in recovered.items()
        if civilisation_name(civ_id) != expected_name
    }
    assert not mismatches, (
        f"KNOWN_CIVILISATION_NAMES disagrees with the fixture-derived join: {mismatches}"
    )


def test_names_a_known_civilisation_id() -> None:
    assert civilisation_name(1) == "Aztecs"


def test_names_id_zero() -> None:
    """Id 0 is a real civilisation (Armenians), not an unset/sentinel value — the fallback path
    (`test_falls_back_to_civilisation_id_for_an_unrecognised_id`) only starts at 45."""
    assert civilisation_name(0) == "Armenians"


def test_id_twenty_one_displays_the_current_name_not_the_one_it_was_derived_from() -> None:
    """Module docstring: id 21 sorts where "Indians" alphabetises, but displays as "Hindustanis",
    the name the game uses today."""
    assert civilisation_name(21) == "Hindustanis"


def test_falls_back_to_civilisation_id_for_an_unrecognised_id() -> None:
    """An id this table does not carry — every civilisation added since the 45-name roster this
    table's derivation was checked against (Jurchens, Khitans, Mapuche, Muisca, Shu, Tupi, Wei,
    Wu) — renders as "Civilisation <id>", never a guessed name (module docstring)."""
    assert civilisation_name(45) == "Civilisation 45"
    assert civilisation_name(999) == "Civilisation 999"


def test_none_stays_none() -> None:
    """A participant with no recorded civilisation is not itself a guess to paper over — `None`
    in, `None` out (module docstring)."""
    assert civilisation_name(None) is None
