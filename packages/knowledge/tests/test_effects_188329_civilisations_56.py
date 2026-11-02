"""T835: `aoe2techtree-188329-civilisations-56`, the first snapshot of build 188329: a direct import
of the third pack (`packages/knowledge/packs/aoe2techtree-e56728e/`, aoe2techtree commit
e56728e76b7d), modelling all fifty-six civilisations.

Six kinds of claim, none a restatement of the build 185872 snapshots' records
(`test_effects_185872_owner_readings.py` and its predecessors):

- **Resolution.** Build 188329 resolves to this snapshot, and builds 185872 and 180059 resolve to
  the snapshots they resolved to before it. The snapshot names no superseded one: no snapshot of
  the build existed.
- **The derivation is reproducible, and its difference is the one the commit makes.** `rules.json`
  is what the current normaliser (version 2) derives from the third pack, byte for byte; against
  `aoe2techtree-185872-owner-readings/rules.json` it differs in the food cost of units 873 and 875
  and in nothing else. The third pack's `strings.en.json` and `trees/` are the second pack's.
- **The carry rule holds row by row** (Phase 9 of tasks.md: T773's three conditions, with the
  notes of build 188329 as the third). The first two conditions are recomputed here from both
  packs, never read back from the file under test; the third is the record
  `docs/data-sources.md` section 6 holds of the notes, held below as data. Every carried row is the
  source row but for an appended `validated_by` that names the source digest, and every row that is
  not carried fails at least one condition, which its `validated_by` names.
- **The twenty-one rows.** They are exactly the set the carry rule leaves out, by civilisation,
  and each says why. Two hold an owner answer the strings do not state and cite the owner's
  arbitration of 2026-11-02; the Saxons discount keeps the stated amount.
- **The disagreements** follow the Malay Forced Levy row, which is carried: the same five entries,
  each naming the third pack and each pack reading equal to the third pack's `rules.json`.
- **The validation record** is the second reading checked against the release notes, and states
  that the owner declined the game reading.
"""

from __future__ import annotations

import functools
import json
import re
import tomllib
from collections import Counter
from collections.abc import Mapping
from importlib import resources
from typing import Any

import pytest

from aoe2stats_knowledge import gaps, normalise, query, snapshot

_PACKAGE = "aoe2stats_knowledge"
_DIRECTORY = "aoe2techtree-188329-civilisations-56"
_SOURCE_DIRECTORY = "aoe2techtree-185872-owner-readings"
_SECOND_PACK = "aoe2techtree-3bb43b1"
_THIRD_PACK = "aoe2techtree-e56728e"
_THIRD_COMMIT = "e56728e76b7d08301fba7b18d5f16bc8554c109a"
_BUILD = 188329
_SOURCE_DIGEST = "sha256:45417481c2e078e22805d4d7c2365818dea34225634ecd22e52e8b48958d328c"

#: What build 188329's notes change, as `docs/data-sources.md` section 6 records it (read
#: 2026-11-02) and tasks.md's Phase 9 preamble lists the rows it leaves out. A row selecting one
#: of these units is not carried (condition three); technology 875 (Gambesons) is not one of them.
_UNITS_THE_NOTES_CHANGE = frozenset({"873", "875", "2550", "2569"})

#: `(civilisation, source_text, field, selector length)` of the twenty-one rows the carry rule
#: leaves out: the selector length tells the Saxons' two rows on one bullet apart.
_TRANSCRIBED: frozenset[tuple[str, str, str, int]] = frozenset(
    {
        (
            "Malians",
            "Barracks Units +1/+2/+3 pierce armor in Feudal/Castle/Imperial Age",
            "pierce_armor",
            -1,
        ),
        ("Britons", "Team Bonus: Archery Ranges work +10% faster", "production_time", -1),
        (
            "Goths",
            "Infantry costs -15/20/25/30% in Dark/Feudal/Castle/Imperial Age",
            "cost",
            -1,
        ),
        ("Goths", "Perfusion (Barracks work +100% faster)", "production_time", -1),
        ("Goths", "Team Bonus: Barracks work +20% faster", "production_time", -1),
        ("Aztecs", "Military Units train +15% faster", "production_time", 215),
        ("Koreans", "Ranged Soldiers and Infantry cost -50% wood", "cost", -1),
        (
            "Incas",
            "Military Units cost -15/20/25/30% food in Dark/Feudal/Castle/Imperial Age",
            "cost",
            -1,
        ),
        ("Magyars", "Team Bonus: Mounted Archers train +25% faster", "production_time", -1),
        ("Portuguese", "All units cost -20% gold", "cost", -1),
        (
            "Portuguese",
            "Circumnavigation (Sets the entire map to explored; Ships train +33% faster)",
            "production_time",
            -1,
        ),
        ("Dravidians", "Skirmishers and Elephant Archers attack +25% faster", "attack_rate", -1),
        ("Gurjaras", "Kshatriyas (Military Units cost -25% food)", "cost", -1),
        (
            "Gurjaras",
            "Frontier Guards (Camel Riders and Elephant Archers +4 melee armor)",
            "melee_armor",
            -1,
        ),
        (
            "Gurjaras",
            "Team Bonus: Camel and Elephant Units train +25% faster",
            "production_time",
            -1,
        ),
        (
            "Mapuche",
            "Malon (Bolas Riders, Slingers, and Skirmishers deal pass through damage)",
            "pass_through_damage",
            -1,
        ),
        (
            "Mapuche",
            "Butalmapu (Team Castle Unique Units and Bolas Riders cost -15%)",
            "cost",
            -1,
        ),
        (
            "Saxons",
            "Foot Soldiers cost -5% per Town Center or Castle controlled (maximum -20%)",
            "cost",
            80,
        ),
        (
            "Saxons",
            "Foot Soldiers cost -5% per Town Center or Castle controlled (maximum -20%)",
            "cost",
            5,
        ),
        (
            "Varangians",
            "Varangian Guards attack +25% faster and generate +50% gold",
            "attack_rate",
            2,
        ),
        (
            "Varangians",
            "Gothikon (Varangian Guards throw axes periodically)",
            "periodic_ranged_attack",
            2,
        ),
    }
)

#: The by-civilisation count the preamble states: 1 + 1 + 3 + 1 + 1 + 1 + 1 + 2 + 1 + 3 + 2 + 2 + 2.
_TRANSCRIBED_BY_CIVILISATION = {
    "Malians": 1,
    "Britons": 1,
    "Goths": 3,
    "Aztecs": 1,
    "Koreans": 1,
    "Incas": 1,
    "Magyars": 1,
    "Portuguese": 2,
    "Dravidians": 1,
    "Gurjaras": 3,
    "Mapuche": 2,
    "Saxons": 2,
    "Varangians": 2,
}


# ---------------------------------------------------------------------------------- the readers


def _root(*parts: str) -> resources.abc.Traversable:
    root = resources.files(_PACKAGE)
    for part in parts:
        root = root.joinpath(part)
    return root


@functools.cache
def _toml(directory: str, name: str) -> dict[str, Any]:
    return tomllib.loads(_root("snapshots", directory, name).read_text(encoding="utf-8"))


@functools.cache
def _rules(directory: str) -> dict[str, Any]:
    return json.loads(_root("snapshots", directory, "rules.json").read_text(encoding="utf-8"))


@functools.cache
def _strings(pack: str) -> Mapping[str, str]:
    return json.loads(_root("packs", pack, "strings.en.json").read_text(encoding="utf-8"))


def _rows(directory: str) -> list[dict[str, Any]]:
    return _toml(directory, "effects.toml")["effect"]


def _bullets_for(pack: str, help_string_id: str) -> tuple[str, ...]:
    """Every bonus bullet of one civilisation's string, as `test_bullet_coverage.py` reads them."""
    lines = [
        line.strip()
        for line in _strings(pack)[help_string_id].replace("<br>\n", "<br>").split("<br>")
    ]
    bullets: list[str] = []
    section = "top"
    for line in (line for line in lines if line):
        if line.startswith("<b>Unique Unit"):
            section = "skip"
        elif line.startswith("<b>Unique Tech"):
            section = "unique_techs"
        elif line.startswith("<b>Team Bonus"):
            section = "team_bonus_pending"
        elif section == "skip":
            continue
        elif line.startswith("•"):
            bullets.append(line.lstrip("•").strip())
        elif section == "team_bonus_pending":
            bullets.append(f"Team Bonus: {line}")
            section = "done"
        elif section in ("top", "unique_techs") and bullets:
            separator = "" if bullets[-1].endswith("/") else " "
            bullets[-1] = f"{bullets[-1]}{separator}{line}"
    return tuple(bullets)


def _refs(row: Mapping[str, Any]) -> list[tuple[str, str]]:
    found = [(s["kind"], s["id"]) for s in row["selector"]]
    found += [(s["kind"], s["id"]) for s in row.get("condition_entities", [])]
    if row.get("condition_technology"):
        found.append(("technology", row["condition_technology"]))
    return found


def _identity(row: Mapping[str, Any]) -> tuple[str, str, str, int]:
    return (row["civilisation"], row["source_text"], row["field"], len(row["selector"]))


def _matches(row: Mapping[str, Any], expected: tuple[str, str, str, int]) -> bool:
    civilisation, text, field, length = expected
    return (
        row["civilisation"] == civilisation
        and row["source_text"] == text
        and row["field"] == field
        and (length == -1 or len(row["selector"]) == length)
    )


def _is_transcribed(row: Mapping[str, Any]) -> bool:
    return any(_matches(row, expected) for expected in _TRANSCRIBED)


# ------------------------------------------------------------------------------- resolution


def test_build_188329_resolves_to_the_new_snapshot_and_the_others_resolve_as_before() -> None:
    resolved = snapshot.snapshot_for(_BUILD)
    assert isinstance(resolved, snapshot.Snapshot)
    assert resolved.directory == _DIRECTORY
    assert resolved.identity.describes_build == _BUILD
    assert resolved.identity.source_version == _THIRD_COMMIT
    assert resolved.supersedes is None, "no snapshot of build 188329 existed to supersede"
    for build, directory in (
        (185872, "aoe2techtree-185872-owner-readings"),
        (180059, "aoe2techtree-180059-owner-readings"),
    ):
        other = snapshot.snapshot_for(build)
        assert isinstance(other, snapshot.Snapshot)
        assert other.directory == directory


def test_the_snapshot_is_promoted_and_models_every_civilisation_of_the_third_pack() -> None:
    loaded = snapshot.load_snapshot(_DIRECTORY)
    table = _toml(_DIRECTORY, "snapshot.toml")["snapshot"]
    assert table["promoted"] is True
    assert table["normaliser_version"] == 2
    assert len(table["civilisations_modelled"]) == 56
    assert set(table["civilisations_modelled"]) == set(_rules(_DIRECTORY)["civilisations"])
    assert set(table["civilisations_modelled"]) == {
        row["civilisation"] for row in _rows(_DIRECTORY)
    }
    assert loaded.identity.digest == table["digest"]


def test_the_manifest_of_the_third_pack_names_the_commit_the_snapshot_names() -> None:
    manifest = json.loads(_root("packs", _THIRD_PACK, "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["commit"] == _THIRD_COMMIT


# ----------------------------------------------------------------------------- the derivation


def test_rules_json_is_what_the_current_normaliser_derives_from_the_third_pack() -> None:
    derived = normalise.rules_json_bytes(normalise.normalise_pack(_THIRD_PACK, version=2))
    assert _root("snapshots", _DIRECTORY, "rules.json").read_bytes() == derived


def test_rules_json_differs_from_build_185872s_in_the_food_cost_of_units_873_and_875_only() -> None:
    source, new = _rules(_SOURCE_DIRECTORY), _rules(_DIRECTORY)
    assert source["civilisations"] == new["civilisations"]
    assert set(source["entities"]) == set(new["entities"])
    changed: list[tuple[str, str]] = []
    for kind, table in source["entities"].items():
        assert set(table) == set(new["entities"][kind]), kind
        changed += [(kind, i) for i, record in table.items() if record != new["entities"][kind][i]]
    assert sorted(changed) == [("unit", "873"), ("unit", "875")]
    for identifier in ("873", "875"):
        before = source["entities"]["unit"][identifier]
        after = new["entities"]["unit"][identifier]
        assert before["cost"] == {"food": 60, "gold": 80}
        assert after["cost"] == {"food": 70, "gold": 80}
        assert {k: v for k, v in before.items() if k != "cost"} == {
            k: v for k, v in after.items() if k != "cost"
        }


def test_the_third_packs_strings_and_trees_are_the_second_packs() -> None:
    second, third = _root("packs", _SECOND_PACK), _root("packs", _THIRD_PACK)
    assert (
        second.joinpath("strings.en.json").read_bytes()
        == third.joinpath("strings.en.json").read_bytes()
    )
    second_trees = sorted(entry.name for entry in second.joinpath("trees").iterdir())
    third_trees = sorted(entry.name for entry in third.joinpath("trees").iterdir())
    assert second_trees == third_trees
    assert len(third_trees) == 56
    for name in third_trees:
        assert (
            second.joinpath("trees", name).read_bytes()
            == third.joinpath("trees", name).read_bytes()
        ), name


# ------------------------------------------------------------------------------- the carry rule


def _failing_conditions(row: Mapping[str, Any]) -> list[str]:
    """The carry rule's three conditions, recomputed from both packs and the notes' record."""
    failing: list[str] = []
    key, text = row["source_key"], row["source_text"]
    if not (
        text in _bullets_for(_SECOND_PACK, key)
        and text in _bullets_for(_THIRD_PACK, key)
        and _strings(_SECOND_PACK)[key] == _strings(_THIRD_PACK)[key]
    ):
        failing.append("bullet")
    source, new = _rules(_SOURCE_DIRECTORY)["entities"], _rules(_DIRECTORY)["entities"]
    for kind, identifier in _refs(row):
        if kind == "unit" and identifier in _UNITS_THE_NOTES_CHANGE:
            failing.append(f"notes:{kind}:{identifier}")
        if (
            identifier not in new[kind]
            or new[kind][identifier]["name"] != source[kind][identifier]["name"]
        ):
            failing.append(f"selector:{kind}:{identifier}")
    if row["civilisation"] == "Saxons" and "per Town Center or Castle" in text:
        failing.append("notes:saxons-discount")
    if (
        row["civilisation"] == "Varangians"
        and any(s["id"] in ("2703", "2704") for s in row["selector"])
        and text.startswith(("Varangian Guards attack", "Gothikon"))
    ):
        failing.append("notes:gothikon")
    if row["civilisation"] == "Portuguese" and text.startswith("Circumnavigation"):
        failing.append("notes:circumnavigation")
    return failing


def test_each_row_is_decided_on_its_own_and_the_twenty_one_are_the_rows_that_fail_a_condition() -> (
    None
):
    source_rows, new_rows = _rows(_SOURCE_DIRECTORY), _rows(_DIRECTORY)
    assert len(source_rows) == len(new_rows) == 323
    carried = transcribed = 0
    for source_row, new_row in zip(source_rows, new_rows, strict=True):
        failing = _failing_conditions(source_row)
        assert {k: v for k, v in source_row.items() if k != "validated_by"} == {
            k: v for k, v in new_row.items() if k != "validated_by"
        }
        if failing:
            transcribed += 1
            assert _is_transcribed(new_row), (_identity(new_row), failing)
            assert not new_row["validated_by"].startswith(source_row["validated_by"])
        else:
            carried += 1
            assert not _is_transcribed(new_row), _identity(new_row)
            assert new_row["validated_by"].startswith(source_row["validated_by"])
            assert "Carried to build 188329 by T835" in new_row["validated_by"]
            assert _SOURCE_DIGEST in new_row["validated_by"]
            assert f"key {source_row['source_key']}" in new_row["validated_by"]
    assert (carried, transcribed) == (302, 21)


def test_the_twenty_one_are_the_rows_the_preamble_names_by_civilisation() -> None:
    rows = [row for row in _rows(_DIRECTORY) if _is_transcribed(row)]
    assert len(rows) == 21
    assert Counter(row["civilisation"] for row in rows) == _TRANSCRIBED_BY_CIVILISATION


def test_a_transcribed_row_names_the_third_pack_the_notes_and_its_failing_condition() -> None:
    for row in _rows(_DIRECTORY):
        if not _is_transcribed(row):
            continue
        reading = row["validated_by"]
        assert "packages/knowledge/packs/aoe2techtree-e56728e/strings.en.json" in reading
        assert f"help_string_id {row['source_key']}" in reading
        assert "update-188329" in reading
        assert "read on 2026-11-02" in reading
        assert "Transcribed again, not carried" in reading
        assert _SOURCE_DIGEST in reading
        assert "the carry rule's third condition fails" in reading


def test_the_reason_each_transcribed_row_gives_is_the_one_its_selector_or_bullet_has() -> None:
    expectations = {
        "873": "unit 873 (Elephant Archer) and unit 875 (Elite Elephant Archer)",
        "2550": "unit 2550 (Champi Scout)",
        "2569": "unit 2569 (Bolas Rider)",
    }
    for row in _rows(_DIRECTORY):
        if not _is_transcribed(row):
            continue
        selected = {s["id"] for s in row["selector"] if s["kind"] == "unit"}
        for identifier, phrase in expectations.items():
            if identifier in selected or (identifier == "873" and "875" in selected):
                assert phrase in row["validated_by"], (_identity(row), identifier)
        if row["civilisation"] == "Saxons":
            assert "very minor adjustment" in row["validated_by"]
        if row["civilisation"] == "Varangians":
            assert "fix Gothikon" in row["validated_by"]
        if row["civilisation"] == "Portuguese" and row["source_text"].startswith("Circum"):
            assert "Circumnavigation reveals" in row["validated_by"]


def test_the_two_rows_that_hold_an_owner_answer_cite_the_arbitration_of_2026_11_02() -> None:
    owner_rows = [row for row in _rows(_DIRECTORY) if "Owner answer carried" in row["validated_by"]]
    assert {_identity(row)[0:3] for row in owner_rows} == {
        (
            "Gurjaras",
            "Team Bonus: Camel and Elephant Units train +25% faster",
            "production_time",
        ),
        (
            "Saxons",
            "Foot Soldiers cost -5% per Town Center or Castle controlled (maximum -20%)",
            "cost",
        ),
    }
    assert sorted(len(row["selector"]) for row in owner_rows) == [5, 7]
    for row in owner_rows:
        assert "Clarifications, Session 2026-11-02" in row["validated_by"]
        assert "not a game reading" in row["validated_by"]
        assert "Closed by T772" in row["validated_by"]


def test_the_saxons_discount_keeps_the_stated_amount_and_is_no_open_row() -> None:
    source = {
        len(row["selector"]): row
        for row in _rows(_SOURCE_DIRECTORY)
        if row["civilisation"] == "Saxons" and "per Town Center" in row["source_text"]
    }
    new = {
        len(row["selector"]): row
        for row in _rows(_DIRECTORY)
        if row["civilisation"] == "Saxons" and "per Town Center" in row["source_text"]
    }
    assert set(new) == {5, 80}
    for length, row in new.items():
        assert row["modelled"] == "yes"
        assert row["operand"] == source[length]["operand"]
        assert row["operand"]["4"] == {"food": 0.8, "gold": 0.8, "stone": 0.8, "wood": 0.8}
        assert "FR-022c" in row["validated_by"]
        assert "gives no number" in row["validated_by"]
        assert "It is not an open row" in row["validated_by"]


def test_the_four_bonuses_with_no_row_stay_without_one() -> None:
    texts = " ".join(row["source_text"] for row in _rows(_DIRECTORY))
    for bullet in (
        "Loot 25% of the resource cost of each destroyed building",
        "Fallen units return 15% of their cost",
        "Shepherding, fishing, and hunting also generate gold",
    ):
        assert bullet not in texts
    header = _root("snapshots", _DIRECTORY, "effects.toml").read_text(encoding="utf-8")
    for bullet in (
        "Loot 25% of the resource cost of each destroyed building",
        "Fallen units return 15% of their cost",
        "Shepherding, fishing, and hunting also generate gold",
    ):
        assert bullet in header


def test_no_row_is_open_so_no_row_refuses_a_field_the_knowledge_base_carries() -> None:
    carried_fields = {"cost", "production_time", "age_requirement", "produced_at", "available_to"}
    source = {
        (r["civilisation"], r["source_text"], r["field"], len(r["selector"]), r["modelled"])
        for r in _rows(_SOURCE_DIRECTORY)
    }
    new = {
        (r["civilisation"], r["source_text"], r["field"], len(r["selector"]), r["modelled"])
        for r in _rows(_DIRECTORY)
    }
    assert new == source, "no row changes what it models"
    for row in _rows(_DIRECTORY):
        if row["modelled"] == "no":
            assert row["field"] not in carried_fields, _identity(row)


def test_the_civilisation_id_table_is_the_source_snapshots() -> None:
    assert (
        _toml(_DIRECTORY, "effects.toml")["civilisation_id"]
        == _toml(_SOURCE_DIRECTORY, "effects.toml")["civilisation_id"]
    )


# ------------------------------------------------------------------ aliases and disagreements


def test_the_aliases_are_the_source_snapshots_and_all_resolve_in_this_rules_json() -> None:
    new = _toml(_DIRECTORY, "aliases.toml")["alias"]
    assert new == _toml(_SOURCE_DIRECTORY, "aliases.toml")["alias"]
    assert len(new) == 73
    entities = _rules(_DIRECTORY)["entities"]
    for alias in new:
        assert alias["id"] not in entities[alias["kind"]], alias
        assert alias["target"] in entities[alias["kind"]], alias
    assert {a["id"] for a in new if a["kind"] == "building"} >= {"490", "673"}
    loaded = snapshot.load_snapshot(_DIRECTORY)
    assert len(loaded.aliases) == 73


def test_the_five_disagreements_follow_the_malay_forced_levy_row_and_name_the_third_pack() -> None:
    forced_levy = [
        row
        for row in _rows(_DIRECTORY)
        if row["civilisation"] == "Malay" and row["source_text"].startswith("Forced Levy")
    ]
    assert len(forced_levy) == 1
    assert "Carried to build 188329 by T835" in forced_levy[0]["validated_by"]
    carried_units = {s["id"] for s in forced_levy[0]["selector"]}

    entries = _toml(_DIRECTORY, "disagreements.toml")["disagreement"]
    assert [e["entity_id"] for e in entries] == ["74", "75", "77", "473", "567"]
    assert {e["entity_id"] for e in entries} <= carried_units
    entities = _rules(_DIRECTORY)["entities"]["unit"]
    for entry in entries:
        assert entry["entity_kind"] == "unit"
        assert entry["field"] == "cost"
        assert "packages/knowledge/packs/aoe2techtree-e56728e" in entry["stored_source"]
        assert _SECOND_PACK not in entry["stored_source"]
        cost = entities[entry["entity_id"]]["cost"]
        match = re.search(r"costs the .+ (\d+) food and (\d+) gold", entry["stored_source"])
        assert match, entry["stored_source"]
        assert (int(match.group(1)), int(match.group(2))) == (cost["food"], cost["gold"])
        reading = re.match(
            r"cost food (\d+), gold (\d+); with Forced Levy, food (\d+), gold 0",
            entry["readings"]["pack"],
        )
        assert reading, entry["readings"]["pack"]
        assert (int(reading.group(1)), int(reading.group(2))) == (cost["food"], cost["gold"])
        assert int(reading.group(3)) == cost["food"] + cost["gold"]
        assert "80 food" in entry["readings"]["liquipedia"]


# ------------------------------------------------------------------------------ the validation


def test_the_validation_is_a_second_reading_against_the_notes_and_the_owner_declined_the_game() -> (
    None
):
    loaded = snapshot.load_snapshot(_DIRECTORY)
    assert loaded.validation is not None
    validation = loaded.validation
    assert validation.method == "second-reading-checked-against-release-notes"
    assert validation.performed_at == "2026-11-02"
    assert "update-188329" in validation.checked_against
    assert "2026-11-02" in validation.checked_against
    assert "rules.json compared entity by entity" in validation.checked_against.replace("\\\n", "")
    assert "units 873 and 875" in validation.checked_against
    assert "owner declined the game reading" in validation.checked_against
    assert "FR-030" in validation.checked_against
    assert "No value was compared with the game" in validation.details["not_checked"]
    notes = validation.details["release_notes"]
    assert notes["url"].endswith("-update-188329/")
    assert notes["read_on"] == "2026-11-02"
    assert "second_reading" not in validation.details


# ------------------------------------------------------------------------------- the values


def _ref(kind: str, identifier: str, build: int = _BUILD) -> query.EntityRef:
    return query.EntityRef(kind=kind, id=identifier, build=build)


def _cost(kind: str, identifier: str, civilisation: str, build: int = _BUILD) -> dict[str, int]:
    answer = query.cost(_ref(kind, identifier, build), civilisation=civilisation)
    assert not isinstance(answer, gaps.KnowledgeGap), answer
    return dict(answer.value)


def test_the_elephant_archer_costs_70_food_on_this_build_and_60_on_the_last() -> None:
    assert _cost("unit", "873", "Britons") == {"food": 70, "gold": 80}
    assert _cost("unit", "873", "Britons", build=185872) == {"food": 60, "gold": 80}


def test_a_transcribed_row_answers_over_the_new_cost() -> None:
    # Portuguese "All units cost -20% gold" is one of the twenty-one: 80 gold becomes 64.
    assert _cost("unit", "873", "Portuguese") == {"food": 70, "gold": 64}
    assert _cost("unit", "873", "Portuguese", build=185872) == {"food": 60, "gold": 64}


def test_a_carried_row_answers_as_it_did() -> None:
    # Franks "Mill technologies free" is carried.
    assert _cost("technology", "12", "Franks") == {"food": 0, "wood": 0}
    assert _cost("technology", "12", "Britons") == {"food": 250, "wood": 250}


def test_the_whole_pack_has_one_current_snapshot_per_build_and_this_is_the_newest() -> None:
    current = {s.identity.describes_build: s.directory for s in snapshot.load_current_snapshots()}
    assert current[_BUILD] == _DIRECTORY
    assert set(current) >= {185872, 180059, _BUILD}


@pytest.mark.parametrize(
    "name", ["rules.json", "effects.toml", "aliases.toml", "disagreements.toml"]
)
def test_every_file_of_the_snapshot_is_packaged(name: str) -> None:
    assert _root("snapshots", _DIRECTORY, name).is_file()
