"""Unit tests for `aoe2stats_api.civilizations` (T070c, corrected T070g, guarded whole T070h).

T070c's table named ids 1-13 confidently and wrongly (module docstring). Two different tests now
guard the table, and they check two different claims — keeping them separate is the point, not an
oversight:

- `test_table_matches_the_fixture_derived_join` re-runs the join that established the table's
  ordering rule — `packages/providers/fixtures/relic/get_recent_match_history.json` against
  `packages/providers/fixtures/companion/matches.json`, on `(match id, profile id)` — and checks it
  against the table. This is **measurement**: 21 of the table's 45 entries, the only ones this
  repository holds captured evidence for, and it is only ever as strong as that overlap.
- `test_table_matches_the_alphabetical_ordering_rule` re-derives all 45 entries from the rule those
  21 measured pairs establish — the 45-name roster, sorted, `Indians` at its original spelling — and
  asserts the whole table against that derivation, entry for entry. This is **generalisation from
  the rule**, not a second measurement: it does not, and cannot, independently confirm the 24 ids
  the join above cannot reach. What it does guarantee is that every one of the 45 entries, reached
  by a fixture or not, is internally consistent with the one rule the measured 21 support. A table
  edited back toward T070c's error, or drifted any other way — inside the measured range or outside
  it — fails one or both of these tests instead of being trusted again by accident.

Ids 45 and above (the eight civilisations added since: Jurchens, Khitans, Mapuche, Muisca, Shu,
Tupi, Wei, Wu) are covered by neither test and never appear in `KNOWN_CIVILISATION_NAMES` — see
`test_falls_back_to_civilisation_id_for_an_unrecognised_id` and the module docstring.
"""

from __future__ import annotations

import json
from pathlib import Path

from aoe2stats_api.civilizations import KNOWN_CIVILISATION_NAMES, civilisation_name

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


# The 45-name roster `KNOWN_CIVILISATION_NAMES`' ordering rule sorts (module docstring): the base
# game plus every expansion up to and including Dynasties of India, spelled the way each
# civilisation was named when its id was assigned — in particular "Indians", not the later rename
# "Hindustanis" (see `_DISPLAY_NAME_OVERRIDES` below and
# `test_id_twenty_one_displays_the_current_name_not_the_one_it_was_derived_from`). Order here does
# not matter — the derivation below sorts it — but every name in it does: this list, not the table
# under test, is the one thing a reader checking this test has to agree with. The eight
# civilisations added since (Jurchens, Khitans, Mapuche, Muisca, Shu, Tupi, Wei, Wu) are
# deliberately absent; they sit outside this roster and outside the table, per the module
# docstring.
_ROSTER_AT_ORIGINAL_SPELLING = [
    "Armenians",
    "Aztecs",
    "Bengalis",
    "Berbers",
    "Bohemians",
    "Britons",
    "Bulgarians",
    "Burgundians",
    "Burmese",
    "Byzantines",
    "Celts",
    "Chinese",
    "Cumans",
    "Dravidians",
    "Ethiopians",
    "Franks",
    "Georgians",
    "Goths",
    "Gurjaras",
    "Huns",
    "Incas",
    "Indians",
    "Italians",
    "Japanese",
    "Khmer",
    "Koreans",
    "Lithuanians",
    "Magyars",
    "Malay",
    "Malians",
    "Mayans",
    "Mongols",
    "Persians",
    "Poles",
    "Portuguese",
    "Romans",
    "Saracens",
    "Sicilians",
    "Slavs",
    "Spanish",
    "Tatars",
    "Teutons",
    "Turks",
    "Vietnamese",
    "Vikings",
]

# Id 21 was assigned while this civilisation was still called "Indians" (that spelling is what
# fixes its position in the sorted roster, between "Incas" and "Italians"); the game has since
# renamed it "Hindustanis", and that is the name `KNOWN_CIVILISATION_NAMES` displays. Every other
# roster entry displays under the exact name it sorts by, so this is the only override.
_DISPLAY_NAME_OVERRIDES = {"Indians": "Hindustanis"}


def test_table_matches_the_alphabetical_ordering_rule() -> None:
    """Guards the 24 of the table's 45 entries `test_table_matches_the_fixture_derived_join` has
    no fixture evidence for (module docstring's "How ids 0-44 below were actually established").

    That test measures 21 `civilization_id -> civName` pairs from two frozen, independently
    captured fixtures — real evidence, but only for the ids those fixtures' matches happened to
    use. It cannot see the other 24: before this test existed, changing
    `KNOWN_CIVILISATION_NAMES[12]` from `"Cumans"` to `"Turks"` left the whole suite green, because
    id 12 was not among the 21.

    This test does not add more measurement — there is no more captured evidence to add. It
    instead checks that every one of the 45 entries, measured or not, is what the *one rule* the
    21 measured pairs established would produce: the zero-based alphabetical position of each name
    in `_ROSTER_AT_ORIGINAL_SPELLING`, with id 21 displayed under its current name rather than the
    one it sorts by. `test_table_matches_the_fixture_derived_join` is what establishes that this
    rule is the right one to apply; this test is what applies it to the ids that test cannot reach.
    A single wrong entry anywhere in the table — inside the measured 21 or outside them — fails
    this assertion.
    """
    assert len(_ROSTER_AT_ORIGINAL_SPELLING) == 45, (
        "the roster this test sorts no longer has 45 names — it must match the civilisation count "
        "the module docstring's derivation was checked against"
    )
    assert len(set(_ROSTER_AT_ORIGINAL_SPELLING)) == 45, "the roster has a duplicate name"

    derived_table = {
        civ_id: _DISPLAY_NAME_OVERRIDES.get(name, name)
        for civ_id, name in enumerate(sorted(_ROSTER_AT_ORIGINAL_SPELLING))
    }

    assert derived_table == KNOWN_CIVILISATION_NAMES


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
