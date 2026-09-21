"""T640: the normaliser producing `rules.json` from the vendored `aoe2techtree` pack (FR-022,
FR-028).

Contract: [contracts/knowledge-base.md](../../../specs/006-replay-analysis-foundations/contracts/
knowledge-base.md), "Entity resolution". `normalise.py`'s module docstring explains the pack's own
shape and the design choices below in full; this file proves them against both small, synthetic
fixtures (fast, exact) and the real, committed pack and the two real, committed reference
recordings (`tests/fixtures/replays/`) — the latter is what "a test asserts every entity referenced
by every committed reference recording resolves" (the contract's own words) means in practice.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

import pytest

from aoe2stats_knowledge.normalise import (
    Disagreement,
    NormalisedPack,
    disagreements_toml_text,
    normalise_pack,
    normalise_pack_data,
    rules_json_bytes,
)

_FIXTURES_ROOT = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "replays"

# The two committed recordings' golden canonical streams (packages/replay-engine/tests/
# test_canonical_golden.py verifies these equal the live parse). Read directly rather than through
# aoe2stats_replay_engine: this package does not depend on the replay engine, only on the JSON
# these goldens already are.
_GOLDEN_CANONICAL_STREAMS = (
    _FIXTURES_ROOT / "AgeIIDE_Replay_500546441.canonical.json",
    _FIXTURES_ROOT / "AgeIIDE_Replay_504695319.canonical.json",
)


def _entity_ids_referenced_by_golden_streams() -> tuple[set[int], set[int], set[int]]:
    """Every unit, technology and building identifier a canonical event names, across every
    committed reference recording — the set the contract's entity-resolution test is about."""
    unit_ids: set[int] = set()
    technology_ids: set[int] = set()
    building_ids: set[int] = set()
    for path in _GOLDEN_CANONICAL_STREAMS:
        document = json.loads(path.read_text(encoding="utf-8"))
        for event in document["events"]:
            kind, payload = event["kind"], event["payload"]
            if kind in ("unit-queued", "unit-unqueued"):
                unit_ids.add(payload["unit_id"])
            elif kind == "research-queued":
                technology_ids.add(payload["technology_id"])
            elif kind == "building-placed":
                building_ids.add(payload["building_id"])
    return unit_ids, technology_ids, building_ids


# --------------------------------------------------------------------------- synthetic pack data
#
# A minimal, hand-built pack shaped exactly like the real `aoe2techtree` pack (same keys, same
# nesting) but with only the entities each test needs, so the merge/majority-vote/disagreement
# logic is exercised precisely rather than incidentally through the real pack's ~600 entities.


def _synthetic_civ_tree(
    *,
    units_techs: list[dict[str, Any]] | None = None,
    buildings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {"buildings": buildings or [], "units_techs": units_techs or []}


def _unit_node(
    node_id: int,
    *,
    age_id: int,
    building_id: int,
    link_id: int | None = None,
    link_node_type: str = "Unit",
    node_type: str = "Unit",
    name: str = "Some Unit",
) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "use_type": "Unit",
        "node_type": node_type,
        "age_id": age_id,
        "building_id": building_id,
        "link_id": link_id,
        "link_node_type": link_node_type,
        "name": name,
        "name_string_id": None,
    }


def _tech_node(
    node_id: int, *, age_id: int, building_id: int, name: str = "Some Tech"
) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "use_type": "Tech",
        "node_type": "Research",
        "age_id": age_id,
        "building_id": building_id,
        "link_id": None,
        "link_node_type": "BuildingTech",
        "name": name,
        "name_string_id": None,
    }


def _minimal_pack_data() -> dict[str, Any]:
    """One unit (id 4), one unit-upgrades-only technology upgrading it (id 4 -> tech 98), one
    plain Tech-table technology (id 34), and one building (id 87) — enough to exercise every merge
    path without the real pack's size."""
    return {
        "civs": {"Franks": {}, "Britons": {}},
        "data": {
            "Unit": {
                "4": {
                    "ID": 4,
                    "Cost": {"Wood": 25, "Gold": 45},
                    "TrainTime": 35,
                    "internal_name": "ARCHR",
                }
            },
            "Building": {"87": {"ID": 87, "Cost": {"Wood": 175}, "TrainTime": 50}},
            "Tech": {
                "34": {
                    "ID": 34,
                    "Cost": {"Gold": 100, "Wood": 150},
                    "ResearchTime": 50,
                    "internal_name": "War Galley",
                }
            },
            "unit_upgrades": {
                "4": {
                    "ID": 98,
                    "Cost": {"Wood": 230, "Gold": 130},
                    "ResearchTime": 50,
                    "internal_name": "Elite Skirmisher",
                }
            },
        },
    }


def _normalise_minimal(
    *,
    franks_units_techs: list[dict[str, Any]] | None = None,
    britons_units_techs: list[dict[str, Any]] | None = None,
    strings: dict[str, str] | None = None,
) -> NormalisedPack:
    data = _minimal_pack_data()
    trees = {
        "Franks": _synthetic_civ_tree(units_techs=franks_units_techs),
        "Britons": _synthetic_civ_tree(units_techs=britons_units_techs),
    }
    return normalise_pack_data(data, strings or {}, trees)


# --------------------------------------------------------------------------------- entity merge


def test_a_unit_upgrades_only_technology_resolves_with_its_table_origin_recorded() -> None:
    """Technology 98 lives only in `unit_upgrades` (keyed by unit id 4), never in the base `Tech`
    table — the contract's "may live in the source's unit table or its upgrade table"."""
    pack = _normalise_minimal(
        franks_units_techs=[_unit_node(4, age_id=3, building_id=87, node_type="UnitUpgrade")],
    )
    technology = pack.entities["technology"]["98"]
    assert technology["table_origin"] == "unit_upgrades"
    assert technology["upgrades_unit"] == "4"
    assert technology["cost"] == {"wood": 230, "gold": 130}
    assert technology["research_time"] == 50


def test_a_unit_upgrades_only_technology_reads_age_and_building_via_its_owning_units_node() -> None:
    """98's own id never appears as a tree node id; its age/building/prerequisite are read from
    the tree entry for unit 4 (its owning unit) instead — the indirection `normalise.py`'s
    docstring names as `_technology_tree_lookup_key`."""
    pack = _normalise_minimal(
        franks_units_techs=[
            _unit_node(4, age_id=3, building_id=87, link_id=7, link_node_type="Unit")
        ],
    )
    technology = pack.entities["technology"]["98"]
    assert technology["age_requirement"] == 3
    assert technology["produced_at"] == {"kind": "building", "id": "87"}
    assert technology["prerequisites"] == [{"kind": "unit", "id": "7"}]


def test_a_technology_present_in_both_tables_merges_without_duplication() -> None:
    """Id 34 is named by both the base Tech table and `unit_upgrades` (the pack's real ids 34/35
    case) with matching cost and research time: one technology entity, not two, its origin
    recording both tables."""
    data = _minimal_pack_data()
    data["data"]["unit_upgrades"]["999"] = {
        "ID": 34,
        "Cost": {"Gold": 100, "Wood": 150},
        "ResearchTime": 50,
        "internal_name": "War Galley",
    }
    pack = normalise_pack_data(data, {}, {"Franks": _synthetic_civ_tree()})
    assert len(pack.entities["technology"]) == 2  # 34 and 98, never a third "34-from-upgrades"
    technology = pack.entities["technology"]["34"]
    assert technology["table_origin"] == "tech+unit_upgrades"
    assert technology["upgrades_unit"] == "999"
    assert pack.disagreements == ()


def test_a_genuine_mismatch_between_tech_and_unit_upgrades_tables_is_a_disagreement() -> None:
    """The one place this module treats a difference as FR-028's disagreement rather than
    civilisation-specific data: the same technology id, named by both tables, with a *different*
    cost — the pack's own two tables contradicting each other about a single civilisation-neutral
    fact, not two civilisations legitimately differing."""
    data = _minimal_pack_data()
    data["data"]["unit_upgrades"]["999"] = {
        "ID": 34,
        "Cost": {"Gold": 999, "Wood": 150},  # disagrees with Tech's Gold: 100
        "ResearchTime": 50,
        "internal_name": "War Galley",
    }
    pack = normalise_pack_data(data, {}, {"Franks": _synthetic_civ_tree()})
    assert len(pack.disagreements) == 1
    disagreement = pack.disagreements[0]
    assert disagreement.entity_kind == "technology"
    assert disagreement.entity_id == "34"
    assert disagreement.stored_source == "tech"
    # The stored value is the Tech table's, not the disagreeing unit_upgrades reading.
    assert pack.entities["technology"]["34"]["cost"] == {"gold": 100, "wood": 150}


def test_the_real_committed_pack_has_no_tech_and_unit_upgrades_disagreement() -> None:
    """FR-028's own finding for this pack revision, stated as a test rather than only in a
    docstring: the two ids the real pack's Tech and unit_upgrades tables both name (34, 35) agree
    completely, so the real, committed `disagreements.toml` is empty."""
    pack = normalise_pack()
    assert pack.disagreements == ()


# ----------------------------------------------------------------------------------- majority vote


def test_age_requirement_is_the_cross_civilisation_majority_not_an_outlier() -> None:
    """A lone civilisation's tree reporting a different age for an otherwise-shared unit (the real
    pack's Burgundians/Armenians early-technology pattern `normalise.py` documents) does not move
    the stored baseline away from what every other civilisation agrees on."""
    pack = _normalise_minimal(
        franks_units_techs=[_unit_node(4, age_id=1, building_id=87)],
        britons_units_techs=[_unit_node(4, age_id=2, building_id=87)],
    )
    # Only two civilisations modelled here; extend the majority with a third agreeing with Franks.
    data = _minimal_pack_data()
    data["civs"]["Goths"] = {}
    trees = {
        "Franks": _synthetic_civ_tree(units_techs=[_unit_node(4, age_id=1, building_id=87)]),
        "Britons": _synthetic_civ_tree(units_techs=[_unit_node(4, age_id=2, building_id=87)]),
        "Goths": _synthetic_civ_tree(units_techs=[_unit_node(4, age_id=1, building_id=87)]),
    }
    pack = normalise_pack_data(data, {}, trees)
    assert pack.entities["unit"]["4"]["age_requirement"] == 1


def test_an_entity_absent_from_every_tree_gets_no_fabricated_name_or_age() -> None:
    """The real pack's own gap (7 units, 1 building carry cost/time data but no tree entry at
    all): faithfully represented as `None`, never invented."""
    pack = _normalise_minimal()  # no tree entries for unit 4 or building 87 at all
    unit = pack.entities["unit"]["4"]
    assert unit["name"] is None
    assert unit["age_requirement"] is None
    assert unit["produced_at"] is None
    assert unit["prerequisites"] == []


# ------------------------------------------------------------------------- the real, vendored pack


def test_the_four_unit_upgrades_only_technology_ids_from_the_contract_are_exactly_these() -> None:
    """The contract's own claim, pinned down against the real pack rather than trusted on faith:
    of the technology identifiers the *first* committed reference recording's canonical stream
    names, exactly four live only in `unit_upgrades`, never in the base `Tech` table — Elite
    Skirmisher (98), Crossbow (100), Cavalier (209) and Arbalest (237)."""
    document = json.loads(
        (_FIXTURES_ROOT / "AgeIIDE_Replay_500546441.canonical.json").read_text(encoding="utf-8")
    )
    technology_ids = {
        event["payload"]["technology_id"]
        for event in document["events"]
        if event["kind"] == "research-queued"
    }
    pack = normalise_pack()
    unit_upgrades_only = {
        technology_id
        for technology_id in technology_ids
        if pack.entities["technology"][str(technology_id)]["table_origin"] == "unit_upgrades"
    }
    assert unit_upgrades_only == {98, 100, 209, 237}


def test_every_unit_and_technology_referenced_by_a_committed_recording_resolves() -> None:
    """Contract, "Entity resolution": "a test asserts every entity referenced by every committed
    reference recording resolves" — units and technologies fully do, against the real pack."""
    unit_ids, technology_ids, _building_ids = _entity_ids_referenced_by_golden_streams()
    pack = normalise_pack()
    unresolved_units = {i for i in unit_ids if str(i) not in pack.entities["unit"]}
    unresolved_technologies = {
        i for i in technology_ids if str(i) not in pack.entities["technology"]
    }
    assert unresolved_units == set()
    assert unresolved_technologies == set()


#: `building-placed` events name two object ids the vendored `aoe2techtree` pack carries nowhere
#: at all — not in the base `Building` table, not in any per-civilisation tree, not anywhere else
#: in the pack (confirmed by inspection, not assumed). Both are age-upgraded visual variants: the
#: tech tree UI this pack was built from only needs one representative id per tech-tree tile, so a
#: building type whose in-game object id changes with the player's age (the same mechanic that
#: gives `Building` table id 12 its own internal name "Barracks Age1") has no id here for any age
#: past the one the tech tree displays. This is a genuine, faithful gap in the vendored source —
#: exactly what T647's `KnowledgeGap` machinery will represent at the query layer — not a defect in
#: this normaliser's merge logic, which is why it is named explicitly here rather than silently
#: excluded from the assertion below.
_BUILDING_IDS_ABSENT_FROM_THE_VENDORED_PACK: frozenset[int] = frozenset({490, 673})


def test_every_building_referenced_by_a_committed_recording_resolves_or_is_a_named_pack_gap() -> (
    None
):
    """The building counterpart of the test above, with the one honest exception: two building
    identifiers the second recording names have no data anywhere in the vendored pack at all. The
    assertion still fails if that set of names ever grows or shrinks unexpectedly, so a change
    here is a signal, not a silent pass."""
    _unit_ids, _technology_ids, building_ids = _entity_ids_referenced_by_golden_streams()
    pack = normalise_pack()
    unresolved_buildings = {i for i in building_ids if str(i) not in pack.entities["building"]}
    assert unresolved_buildings == _BUILDING_IDS_ABSENT_FROM_THE_VENDORED_PACK


# ------------------------------------------------------------------------------- rules.json bytes


def test_rules_json_bytes_is_deterministic_across_runs() -> None:
    pack = normalise_pack()
    assert rules_json_bytes(pack) == rules_json_bytes(pack)


def test_rules_json_bytes_is_valid_json_ending_in_one_newline() -> None:
    pack = normalise_pack()
    raw = rules_json_bytes(pack)
    assert raw.endswith(b"\n")
    assert not raw.endswith(b"\n\n")
    document = json.loads(raw)
    assert set(document) == {"entities", "civilisations"}
    assert set(document["entities"]) == {"unit", "building", "technology"}


# ---------------------------------------------------------------------------- disagreements.toml


def test_disagreements_toml_text_is_a_commented_explanation_when_there_are_none() -> None:
    text = disagreements_toml_text(())
    assert "FR-028" in text
    # A comment-only document is valid, empty TOML — never a parse error.
    assert tomllib.loads(text) == {}


def test_disagreements_toml_text_renders_a_synthetic_conflict() -> None:
    """The writer half of FR-028's mechanism, proven against an injected conflict since none
    arises from the real, committed pack on its own (see the test above)."""
    disagreement = Disagreement(
        entity_kind="technology",
        entity_id="34",
        field="cost",
        stored_source="tech",
        reason="synthetic, for the test",
        readings={"tech": "cost={'gold': 100}", "unit_upgrades": "cost={'gold': 999}"},
    )
    text = disagreements_toml_text((disagreement,))
    parsed = tomllib.loads(text)
    assert len(parsed["disagreement"]) == 1
    entry = parsed["disagreement"][0]
    assert entry["entity_kind"] == "technology"
    assert entry["entity_id"] == "34"
    assert entry["stored_source"] == "tech"
    assert entry["readings"]["tech"] == "cost={'gold': 100}"
    assert entry["readings"]["unit_upgrades"] == "cost={'gold': 999}"


# -------------------------------------------------------------- the committed promoted fixture


def test_the_committed_promoted_fixtures_rules_json_matches_a_fresh_normalisation() -> None:
    """The fixture `rules.json` T640 committed is not hand-edited output: re-running the
    normaliser over the real, unpatched pack reproduces it byte for byte. A failure here means the
    committed file has drifted from what the normaliser now produces (see `tests/fixtures/replays/
    README.md`'s golden discipline for the same principle applied to the canonical stream)."""
    committed = (
        Path(__file__).resolve().parents[1] / "snapshots" / "aoe2techtree-180059" / "rules.json"
    ).read_bytes()
    assert committed == rules_json_bytes(normalise_pack())


@pytest.mark.parametrize(
    "entity_kind,entity_id",
    [("unit", "4"), ("building", "12"), ("technology", "98"), ("technology", "34")],
)
def test_the_committed_promoted_fixture_carries_real_entities_not_the_old_stub(
    entity_kind: str, entity_id: str
) -> None:
    document = json.loads(
        (
            Path(__file__).resolve().parents[1] / "snapshots" / "aoe2techtree-180059" / "rules.json"
        ).read_text(encoding="utf-8")
    )
    assert entity_id in document["entities"][entity_kind]
