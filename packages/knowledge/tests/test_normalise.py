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
import shutil
import tomllib
from pathlib import Path
from typing import Any

import pytest

from aoe2stats_knowledge.normalise import (
    FIRST_NORMALISER_VERSION,
    NORMALISER_VERSIONS,
    Disagreement,
    NormalisedPack,
    disagreements_toml_text,
    normalise_pack,
    normalise_pack_data,
    rules_json_bytes,
)
from aoe2stats_knowledge.snapshot import load_resolvable_snapshots

#: The two vendored packs by directory name (`packs/<name>/MANIFEST.json` pins each one's commit).
_FIRST_PACK = "aoe2techtree"
_SECOND_PACK = "aoe2techtree-3bb43b1"

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
    """98's own id never appears as a tree node id; its age/building are read from the tree entry
    for unit 4 (its owning unit) instead — the indirection `normalise.py`'s docstring names as
    `_technology_tree_lookup_key`."""
    pack = _normalise_minimal(
        franks_units_techs=[_unit_node(4, age_id=3, building_id=87)],
    )
    technology = pack.entities["technology"]["98"]
    assert technology["age_requirement"] == 3
    assert technology["produced_at"] == {"kind": "building", "id": "87"}


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
    pack = normalise_pack(_FIRST_PACK)
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
    pack = normalise_pack(_FIRST_PACK)
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
    pack = normalise_pack(_FIRST_PACK)
    unresolved_units = {i for i in unit_ids if str(i) not in pack.entities["unit"]}
    unresolved_technologies = {
        i for i in technology_ids if str(i) not in pack.entities["technology"]
    }
    assert unresolved_units == set()
    assert unresolved_technologies == set()


#: `building-placed` events name two object ids the vendored `aoe2techtree` pack carries nowhere
#: at all — not in the base `Building` table, not in any per-civilisation tree, not anywhere else
#: in the pack (confirmed by inspection, not assumed). This is a genuine, faithful gap in the
#: vendored source — exactly what T647's `KnowledgeGap` machinery represents at the query layer —
#: not a defect in this normaliser's merge logic, which is why it is named explicitly here rather
#: than silently excluded from the assertion below. **Corrected 2026-10-18 (T761):** an earlier
#: version of this note called both ids age-upgraded visual variants of one tech-tree tile; that
#: was never measured. A referenced source, `aoc-reference-data`'s `objects` (read 2026-10-18,
#: `docs/data-sources.md` §6), names both "Gate", and FR-022d closes them with a transcribed alias
#: in a snapshot's `aliases.toml`, vendoring nothing. The set below stays as the strict statement of
#: what the pack names until T767's snapshot carries those aliases.
_BUILDING_IDS_ABSENT_FROM_THE_VENDORED_PACK: frozenset[int] = frozenset({490, 673})


def test_every_building_referenced_by_a_committed_recording_resolves_or_is_a_named_pack_gap() -> (
    None
):
    """The building counterpart of the test above, with the one honest exception: two building
    identifiers the second recording names have no data anywhere in the vendored pack at all. The
    assertion still fails if that set of names ever grows or shrinks unexpectedly, so a change
    here is a signal, not a silent pass."""
    _unit_ids, _technology_ids, building_ids = _entity_ids_referenced_by_golden_streams()
    pack = normalise_pack(_FIRST_PACK)
    unresolved_buildings = {i for i in building_ids if str(i) not in pack.entities["building"]}
    assert unresolved_buildings == _BUILDING_IDS_ABSENT_FROM_THE_VENDORED_PACK


_SNAPSHOTS_ROOT = Path(__file__).resolve().parents[1] / "snapshots"
_PACKS_ROOT = Path(__file__).resolve().parents[1] / "packs"

#: Every promoted snapshot the loader finds under `snapshots/` (T707a: found, never listed by hand,
#: so a snapshot promoted later is re-derived and checked without anyone registering it here).
#: `contracts/knowledge-base.md`'s "Entity resolution" is not only about what a committed
#: recording's canonical stream names directly, but about every entity `rules.json` itself names.
#: The unpromoted `aoe2techtree-test-stub` is excepted by the loader itself: its `rules.json` is a
#: hand-written stub, not normalised output.
_PROMOTED_SNAPSHOT_DIRECTORIES: tuple[str, ...] = tuple(
    snapshot.directory for snapshot in load_resolvable_snapshots()
)


def test_no_entity_in_either_promoted_snapshot_carries_prerequisites() -> None:
    """T652y: `rules.json` does not carry `prerequisites` at all. The pack's own tree `link_id`/
    `link_node_type` is the tech-tree screen's display link, not a rule of the game — Hand
    Cannoneer links to node 6 in Bohemians' tree alone, where the game requires Chemistry in
    every civilisation (research.md D3) — so T652t's kind-resolution machinery over that link is
    gone, and no entity in either committed, promoted `rules.json` file (not a fresh
    normalisation — the committed bytes themselves, the same file `query.py` actually reads)
    carries the key at all."""
    for directory in _PROMOTED_SNAPSHOT_DIRECTORIES:
        document = json.loads(
            (
                Path(__file__).resolve().parents[1] / "snapshots" / directory / "rules.json"
            ).read_text(encoding="utf-8")
        )
        entities = document["entities"]
        carrying = [
            (entity_kind, entity_id)
            for entity_kind, table in entities.items()
            for entity_id, entity in table.items()
            if "prerequisites" in entity
        ]
        assert carrying == [], f"{directory}: entities still carrying prerequisites {carrying}"


# ------------------------------------------------------------------------------- rules.json bytes


def test_rules_json_bytes_is_deterministic_across_runs() -> None:
    pack = normalise_pack(_FIRST_PACK)
    assert rules_json_bytes(pack) == rules_json_bytes(pack)


def test_rules_json_bytes_is_valid_json_ending_in_one_newline() -> None:
    pack = normalise_pack(_FIRST_PACK)
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


def _pack_directory_pinned_at(commit: str) -> str:
    """The `packs/` directory whose `MANIFEST.json` pins `commit` - how a snapshot finds the pack
    it was imported from, by its `source_version` and nothing else."""
    matches = [
        manifest.parent.name
        for manifest in sorted(_PACKS_ROOT.glob("*/MANIFEST.json"))
        if json.loads(manifest.read_text(encoding="utf-8"))["commit"] == commit
    ]
    assert len(matches) == 1, f"{commit} must be pinned by exactly one vendored pack: {matches}"
    return matches[0]


def _rederived_rules_json(snapshot_directory: Path) -> bytes:
    """`rules.json` as the normaliser produces it from the pack the snapshot's own `snapshot.toml`
    names, under the normaliser version it names (T763; absent means the first): the pack is found
    from `[snapshot].source_version` through each pack's `MANIFEST.json`, never from a table kept
    here, and the version is read from the file, never assumed."""
    table = tomllib.loads((snapshot_directory / "snapshot.toml").read_text("utf-8"))["snapshot"]
    version = table.get("normaliser_version", FIRST_NORMALISER_VERSION)
    pack = normalise_pack(_pack_directory_pinned_at(table["source_version"]), version=version)
    return rules_json_bytes(pack)


def test_the_promoted_snapshots_are_found_not_listed() -> None:
    """The parametrisation below is only as good as what the loader finds: the two builds of the
    first revision, the second revision's, and not the unpromoted stub."""
    assert set(_PROMOTED_SNAPSHOT_DIRECTORIES) >= {
        "aoe2techtree-177723-test",
        "aoe2techtree-180059",
        "aoe2techtree-185872",
    }
    assert "aoe2techtree-test-stub" not in _PROMOTED_SNAPSHOT_DIRECTORIES


@pytest.mark.parametrize("snapshot_directory", _PROMOTED_SNAPSHOT_DIRECTORIES)
def test_every_promoted_snapshots_rules_json_matches_a_fresh_normalisation(
    snapshot_directory: str,
) -> None:
    """The `rules.json` a snapshot commits is not hand-edited output: re-running the normaliser
    over the real, unpatched pack *the snapshot names* reproduces it byte for byte. A newer
    revision is vendored beside the first (T707), so each snapshot is re-derived from the pack its
    own `source_version` pins, and a failure here means the committed file has drifted from what
    the normaliser now produces (see `tests/fixtures/replays/README.md`'s golden discipline for the
    same principle applied to the canonical stream)."""
    root = _SNAPSHOTS_ROOT / snapshot_directory
    assert (root / "rules.json").read_bytes() == _rederived_rules_json(root)


def test_a_snapshot_naming_one_packs_commit_but_derived_from_another_is_caught(
    tmp_path: Path,
) -> None:
    """T707a plant: build 185872's `rules.json` is derived from pack `aoe2techtree-3bb43b1`. Point
    its `source_version` at the first pack's commit instead (a copy in `tmp_path`, the committed
    snapshot untouched) and the re-derivation is from the *other* pack, so it no longer reproduces
    the committed bytes - the test above would fail for exactly this."""
    copy = tmp_path / "aoe2techtree-185872"
    shutil.copytree(_SNAPSHOTS_ROOT / "aoe2techtree-185872", copy)
    first_pack_commit = json.loads((_PACKS_ROOT / "aoe2techtree" / "MANIFEST.json").read_text())[
        "commit"
    ]
    toml_path = copy / "snapshot.toml"
    text = toml_path.read_text(encoding="utf-8")
    toml_path.write_text(
        text.replace(
            "3bb43b1439eef88dfe7fe892d7f7dc41ac9dd76f",
            first_pack_commit,
        ),
        encoding="utf-8",
    )
    assert first_pack_commit in toml_path.read_text(encoding="utf-8")

    assert (copy / "rules.json").read_bytes() != _rederived_rules_json(copy)


def test_the_two_vendored_revisions_describe_different_data() -> None:
    """The reason a second pack sits beside the first: re-deriving 180059 from the newer revision
    would not reproduce its committed `rules.json`, so replacing the pack would have orphaned it."""
    assert rules_json_bytes(normalise_pack(_FIRST_PACK)) != rules_json_bytes(
        normalise_pack(_SECOND_PACK)
    )


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


# ---------------------------------------------------- T763: the normaliser's second version

#: Technology ids the pack's `unit_upgrades` table keys under more than one unit, measured
#: 2026-10-19 in both vendored revisions. The first-version normaliser keeps one owning unit per
#: technology (the last), which is why the membership rule must collect every key.
_MULTI_KEYED_UPGRADE_TECHNOLOGIES = {2, 34, 35, 197, 365, 429, 678, 753}


def _trees(pack_name: str) -> dict[str, dict[str, list[str]]]:
    pack = normalise_pack(pack_name, version=2)
    document = json.loads(rules_json_bytes(pack))
    trees: dict[str, dict[str, list[str]]] = document["civilisations"]
    return trees


def test_the_normaliser_has_two_versions_and_the_first_is_the_default() -> None:
    assert NORMALISER_VERSIONS == (1, 2)
    assert FIRST_NORMALISER_VERSION == 1
    default = json.loads(rules_json_bytes(normalise_pack(_FIRST_PACK)))
    explicit = json.loads(rules_json_bytes(normalise_pack(_FIRST_PACK, version=1)))
    assert default == explicit
    assert isinstance(default["civilisations"], list)


@pytest.mark.parametrize("version", [0, 3, True, "2"])
def test_the_normaliser_refuses_a_version_it_does_not_have(version: Any) -> None:
    with pytest.raises(ValueError, match="version"):
        normalise_pack(_FIRST_PACK, version=version)


@pytest.mark.parametrize("pack_name", [_FIRST_PACK, _SECOND_PACK])
def test_version_two_changes_the_civilisations_and_nothing_else(pack_name: str) -> None:
    first = json.loads(rules_json_bytes(normalise_pack(pack_name, version=1)))
    second = json.loads(rules_json_bytes(normalise_pack(pack_name, version=2)))
    assert set(first) == set(second) == {"entities", "civilisations"}
    assert first["entities"] == second["entities"]
    assert sorted(second["civilisations"]) == first["civilisations"]


def test_version_two_is_deterministic_and_lists_are_sorted_numerically() -> None:
    pack = normalise_pack(_FIRST_PACK, version=2)
    assert rules_json_bytes(pack) == rules_json_bytes(normalise_pack(_FIRST_PACK, version=2))
    for tree in _trees(_FIRST_PACK).values():
        assert set(tree) == {"unit", "building", "technology"}
        for ids in tree.values():
            assert ids == [str(i) for i in sorted(int(i) for i in ids)]
            assert len(ids) == len(set(ids))


def test_the_multi_keyed_upgrade_technologies_are_exactly_these_in_both_packs() -> None:
    for pack_name in (_FIRST_PACK, _SECOND_PACK):
        data = json.loads(
            (_PACKS_ROOT / pack_name / "data.json").read_text(encoding="utf-8"),
        )
        keyed: dict[int, set[str]] = {}
        for unit_id, raw in data["data"]["unit_upgrades"].items():
            keyed.setdefault(raw["ID"], set()).add(unit_id)
        multi = {technology for technology, units in keyed.items() if len(units) > 1}
        assert multi == _MULTI_KEYED_UPGRADE_TECHNOLOGIES, pack_name


def test_a_technology_keyed_under_two_units_is_a_member_through_either() -> None:
    """Technology 197 (Pikeman) is keyed under units 358 and 1787, and 429 (Halberdier) under 359
    and 1788. The first-version normaliser's owner table keeps the last key, 1787 and 1788, which
    Franks, Teutons and Tatars do not have; a last-wins reading would drop both from their trees.
    """
    trees = _trees(_FIRST_PACK)
    last_wins = normalise_pack(_FIRST_PACK).entities["technology"]
    assert last_wins["197"]["upgrades_unit"] == "1787"
    for civilisation in ("Franks", "Teutons", "Tatars"):
        assert "1787" not in trees[civilisation]["unit"], civilisation
        assert "358" in trees[civilisation]["unit"], civilisation
        assert "197" in trees[civilisation]["technology"], civilisation
        assert "429" in trees[civilisation]["technology"], civilisation


@pytest.mark.parametrize("technology", ["98", "100", "222"])
def test_an_upgrade_technology_is_placed_by_the_unit_the_pack_keys_it_under(
    technology: str,
) -> None:
    """Measured 2026-10-18 on match 511523321: technologies 98, 100 and 222 were ordered and are in
    neither participant's `Tech` list (the pack's civilisation tables list the unit, not the
    technology that upgrades it). `unit_upgrades` keys them under units 6, 24 and 75."""
    data = json.loads((_PACKS_ROOT / _SECOND_PACK / "data.json").read_text(encoding="utf-8"))
    trees = _trees(_SECOND_PACK)
    for civilisation in ("Slavs", "Sicilians"):
        assert int(technology) not in data["civs"][civilisation]["Tech"]
        assert technology in trees[civilisation]["technology"]


def test_an_upgrade_technology_whose_keyed_unit_is_not_in_the_tree_is_not_a_member() -> None:
    """Contrast: Elite Skirmisher (98) is keyed under unit 6, which the Turks' tree lacks, and the
    Turks' `Tech` list does not name 98 either."""
    data = json.loads((_PACKS_ROOT / _FIRST_PACK / "data.json").read_text(encoding="utf-8"))
    trees = _trees(_FIRST_PACK)
    assert 6 not in data["civs"]["Turks"]["Unit"]
    assert 98 not in data["civs"]["Turks"]["Tech"]
    assert "6" not in trees["Turks"]["unit"]
    assert "98" not in trees["Turks"]["technology"]
    assert "6" in trees["Franks"]["unit"]
    assert "98" in trees["Franks"]["technology"]


def test_a_tree_lists_what_the_packs_civilisation_table_lists() -> None:
    data = json.loads((_PACKS_ROOT / _FIRST_PACK / "data.json").read_text(encoding="utf-8"))
    trees = _trees(_FIRST_PACK)
    for civilisation, table in data["civs"].items():
        assert trees[civilisation]["unit"] == [str(i) for i in sorted(table["Unit"])]
        assert trees[civilisation]["building"] == [str(i) for i in sorted(table["Building"])]
        assert set(map(str, table["Tech"])) <= set(trees[civilisation]["technology"])


def test_every_installed_snapshot_re_derives_under_the_version_it_names() -> None:
    """Every installed snapshot, found by the loader and not listed here, re-derives byte for byte
    under the version its `snapshot.toml` names, and the version is read, not assumed: today every
    one names none, so each is first-version."""
    assert _PROMOTED_SNAPSHOT_DIRECTORIES
    for directory in _PROMOTED_SNAPSHOT_DIRECTORIES:
        root = _SNAPSHOTS_ROOT / directory
        table = tomllib.loads((root / "snapshot.toml").read_text("utf-8"))["snapshot"]
        assert table.get("normaliser_version", FIRST_NORMALISER_VERSION) in NORMALISER_VERSIONS
        assert (root / "rules.json").read_bytes() == _rederived_rules_json(root), directory


def test_the_re_derivation_is_made_under_the_version_a_snapshot_names(tmp_path: Path) -> None:
    """Plant: a copy of an installed snapshot that names version 2 no longer re-derives to its
    first-version bytes, so the version in `snapshot.toml` is what decides."""
    copy = tmp_path / "aoe2techtree-180059"
    shutil.copytree(_SNAPSHOTS_ROOT / "aoe2techtree-180059", copy)
    text = (copy / "snapshot.toml").read_text(encoding="utf-8")
    (copy / "snapshot.toml").write_text(
        text.replace("[snapshot]\n", "[snapshot]\nnormaliser_version = 2\n", 1), encoding="utf-8"
    )
    assert (copy / "rules.json").read_bytes() != _rederived_rules_json(copy)
