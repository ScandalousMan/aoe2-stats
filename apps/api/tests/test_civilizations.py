"""Unit tests for `aoe2stats_api.civilizations` (T070c, corrected T070g, guarded whole T070h,
extended 45-60 T070i).

T070c's table named ids 1-13 confidently and wrongly (module docstring). The table now holds two
different kinds of claim, over two disjoint id ranges, and the tests keep them separate rather than
blurring them into one assertion:

- Ids 0-44 are **derived** from one alphabetical ordering rule, itself established by measurement.
  `test_table_matches_the_fixture_derived_join` re-runs the join that established that rule —
  `packages/providers/fixtures/relic/get_recent_match_history.json` against
  `packages/providers/fixtures/companion/matches.json`, on `(match id, profile id)` — and checks it
  against the table. This is **measurement**: 21 of the range's 45 entries, the only ones this
  repository holds captured evidence for. `test_table_matches_the_alphabetical_ordering_rule`
  re-derives all 45 entries from the rule those 21 measured pairs establish — the 45-name roster,
  sorted, `Indians` at its original spelling — and asserts ids 0-44 of the table against that
  derivation, entry for entry, and only that range: it stays authoritative over 0-44 rather than
  being loosened to accommodate ids 45 and up, which follow no rule at all.
- Ids 45-60 are **individually transcribed**, in release order, following no rule.
  `test_table_matches_the_transcribed_ids_forty_five_to_sixty` asserts the literal expected pairs.
  This is **not** measurement in the sense the fixture join above is, and it is **not** a rule
  applied the way 0-44's ordering is: these fourteen pairs rest on a cross-check against a
  community reference dataset (module docstring, T070i) and are asserted as the plain facts they
  were read to be.

Ids 56, 57 and anything above 60 are covered by neither of the above and never appear in
`KNOWN_CIVILISATION_NAMES` — see `test_falls_back_for_the_deliberate_gap_and_beyond_sixty` and the
module docstring.
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
# under test, is the one thing a reader checking this test has to agree with. Ids 45 and up
# (Achaemenids, Athenians, Spartans, Shu, Wu, Wei, Jurchens, Khitans, Macedonians, Thracians, Puru,
# Muisca, Mapuche, Tupi) are deliberately absent from this roster: they are not derived from any
# ordering rule at all, and this test only ever checks ids 0-44 against what it produces — see
# `test_table_matches_the_transcribed_ids_forty_five_to_sixty` for the other range.
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
    """Guards the 24 of ids 0-44's 45 entries `test_table_matches_the_fixture_derived_join` has no
    fixture evidence for (module docstring's "How ids 0-44 below were actually established").

    Scoped to 0-44 deliberately, and only to 0-44: ids 45 and up (T070i) follow no ordering rule at
    all — they are individually transcribed, in release order — so folding them into this
    derivation would either be wrong (they don't sort where the roster would place them) or would
    silently stop this test from being a real check of the rule. Loosening this assertion to
    "accommodate" ids 45-60 is exactly the failure mode this test exists to prevent; those ids get
    their own assertion below instead.

    That test measures 21 `civilization_id -> civName` pairs from two frozen, independently
    captured fixtures — real evidence, but only for the ids those fixtures' matches happened to
    use. It cannot see the other 24: before this test existed, changing
    `KNOWN_CIVILISATION_NAMES[12]` from `"Cumans"` to `"Turks"` left the whole suite green, because
    id 12 was not among the 21.

    This test does not add more measurement — there is no more captured evidence to add. It
    instead checks that every one of ids 0-44's 45 entries, measured or not, is what the *one rule*
    the 21 measured pairs established would produce: the zero-based alphabetical position of each
    name in `_ROSTER_AT_ORIGINAL_SPELLING`, with id 21 displayed under its current name rather than
    the one it sorts by. `test_table_matches_the_fixture_derived_join` is what establishes that
    this rule is the right one to apply; this test is what applies it to the ids that test cannot
    reach. A single wrong entry anywhere in 0-44 — inside the measured 21 or outside them — fails
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

    # Scoped to ids 0-44 only: the table also carries ids 45-60 (T070i), which are transcribed,
    # not derived, and are guarded by test_table_matches_the_transcribed_ids_forty_five_to_sixty
    # instead. Comparing against the full table here would either fail spuriously on entries this
    # rule was never meant to produce, or — worse — invite loosening the rule to fit them.
    table_zero_to_forty_four = {
        civ_id: name for civ_id, name in KNOWN_CIVILISATION_NAMES.items() if civ_id <= 44
    }
    assert len(table_zero_to_forty_four) == 45, (
        "expected exactly 45 entries in the table's 0-44 range"
    )
    assert derived_table == table_zero_to_forty_four


# Ids 45-60 (T070i) rest on no rule the way 0-44 do: they are individually transcribed, in release
# order, from a cross-check against SiegeEngineers/aoc-reference-data's `data/datasets/100.json`
# (module docstring's "Ids 45-60" section). That source carries no licence, so it is read and
# transcribed here, never vendored — this literal dict is the fact this test asserts, not a
# generalisation the way `_ROSTER_AT_ORIGINAL_SPELLING` above is. Ids 56 and 57 are deliberately
# absent: they are missing from the reference too, and are covered instead by
# `test_falls_back_for_the_deliberate_gap_and_beyond_sixty`.
_TRANSCRIBED_FORTY_FIVE_TO_SIXTY = {
    45: "Achaemenids",
    46: "Athenians",
    47: "Spartans",
    48: "Shu",
    49: "Wu",
    50: "Wei",
    51: "Jurchens",
    52: "Khitans",
    53: "Macedonians",
    54: "Thracians",
    55: "Puru",
    58: "Muisca",
    59: "Mapuche",
    60: "Tupi",
}


def test_table_matches_the_transcribed_ids_forty_five_to_sixty() -> None:
    """Asserts the fourteen literal id-name pairs T070i added, ids 45-60 minus the deliberate gap
    at 56/57 (module docstring). This is a transcription check, not a rule or a measurement: there
    is no ordering rule over this range the way there is for 0-44, and this repository's own
    fixtures never reach these ids either. The expected value here is exactly what was read from
    the cross-check source, asserted as fact.
    """
    assert len(_TRANSCRIBED_FORTY_FIVE_TO_SIXTY) == 14

    table_forty_five_to_sixty = {
        civ_id: name for civ_id, name in KNOWN_CIVILISATION_NAMES.items() if 45 <= civ_id <= 60
    }
    assert table_forty_five_to_sixty == _TRANSCRIBED_FORTY_FIVE_TO_SIXTY


def test_names_a_known_civilisation_id() -> None:
    assert civilisation_name(1) == "Aztecs"


def test_names_id_zero() -> None:
    """Id 0 is a real civilisation (Armenians), not an unset/sentinel value — the fallback path
    (`test_falls_back_for_the_deliberate_gap_and_beyond_sixty`) does not reach it."""
    assert civilisation_name(0) == "Armenians"


def test_id_twenty_one_displays_the_current_name_not_the_one_it_was_derived_from() -> None:
    """Module docstring: id 21 sorts where "Indians" alphabetises, but displays as "Hindustanis",
    the name the game uses today."""
    assert civilisation_name(21) == "Hindustanis"


def test_names_a_transcribed_id_in_the_forty_five_to_sixty_range() -> None:
    """Spot-checks the lookup function against the transcribed range, not just the table
    (module docstring's "Ids 45-60" section, T070i)."""
    assert civilisation_name(48) == "Shu"
    assert civilisation_name(60) == "Tupi"


def test_falls_back_for_the_deliberate_gap_and_beyond_sixty() -> None:
    """Three different reasons an id renders as "Civilisation <id>" instead of a guessed name
    (module docstring):

    - 56 and 57: deliberately absent, missing from the T070i cross-check source too, not filled in
      by guessing what sits between Puru (55) and Muisca (58).
    - 61: past the highest transcribed id, exactly the same shape T070c's original mistake was
      about — no guessing past the last id this repository has evidence for.
    - a large, arbitrary id: never in range for any civilisation this game has released.
    """
    assert civilisation_name(56) == "Civilisation 56"
    assert civilisation_name(57) == "Civilisation 57"
    assert civilisation_name(61) == "Civilisation 61"
    assert civilisation_name(999) == "Civilisation 999"


def test_none_stays_none() -> None:
    """A participant with no recorded civilisation is not itself a guess to paper over — `None`
    in, `None` out (module docstring)."""
    assert civilisation_name(None) is None
