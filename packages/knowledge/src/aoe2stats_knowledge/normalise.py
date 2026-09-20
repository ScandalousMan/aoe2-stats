"""T640: the normaliser producing `rules.json` from a vendored knowledge pack (FR-022, FR-028).

Contract: [contracts/knowledge-base.md](../../../../specs/006-replay-analysis-foundations/
contracts/knowledge-base.md), "Entity resolution" and "On disk". Data model: [data-model.md](
../../../../specs/006-replay-analysis-foundations/data-model.md) §6.

**The pack's own shape, read empirically rather than assumed** (`packages/knowledge/packs/
aoe2techtree/`, the vendored `SiegeEngineers/aoe2techtree` format):

- `data.json`'s `data.Unit`, `data.Building` and `data.Tech` tables carry combat stats, `Cost` and
  a time (`TrainTime` for a unit or a building, `ResearchTime` for a technology), keyed by the
  entity's own numeric id — but **no name, no age requirement, no producing building, no
  prerequisite**. Those four live only in the 53 per-civilisation `trees/<CIV>.json` files.
- `data.json`'s fourth table, `data.unit_upgrades`, is keyed by a *unit* id already present in the
  `Unit` table (the unit being upgraded) and carries the *technology* that performs that upgrade —
  its own `Cost`, `ResearchTime`, `internal_name` and, in its `ID` field, **the technology's own
  numeric id**. That id is frequently absent from the `Tech` table entirely: of this pack revision's
  115 `unit_upgrades` entries, 102 name a technology id the `Tech` table has never heard of. This is
  the contract's "a unit identifier may live in the source's unit table or its upgrade table" —
  read plainly, a *technology* identifier that may live in the base `Tech` table or in
  `unit_upgrades`'s `ID` field, merged here into one keyed technology space with `table_origin`
  recording which (`"tech"`, `"unit_upgrades"`, or `"tech+unit_upgrades"` for the two ids, 34 and
  35, this revision's `Tech` table and `unit_upgrades` both name — checked for consistency below).
  Of the two committed reference recordings (`tests/fixtures/replays/`), the first names four
  technologies this way: 98 (Elite Skirmisher), 100 (Crossbow), 209 (Cavalier), 237 (Arbalest) —
  the "four technology identifiers" the contract counts. `test_the_four_unit_upgrades_only_
  technology_ids_from_the_contract_are_exactly_these` in the test suite pins this down against the
  real, committed pack rather than trusting the number on faith.
- A `unit_upgrades` entry's own technology id is *not* the id its per-civilisation tree entries use
  as `node_id` — the trees key that upgrade by the *unit* id being upgraded (e.g. node id 6 for
  "Elite Skirmisher", not 98), with `use_type: "Unit"` and `node_type: "UnitUpgrade"`. Reading a
  `unit_upgrades`-only technology's age, producing building, prerequisite and name therefore looks
  up the tree entry for its *owning unit's* id, not its own — `_technology_tree_lookup_key` is
  where this indirection lives, and every one of this revision's 102 unit-upgrade-only technologies
  resolves through it (proven in the test suite, not merely assumed).
- Age, producing building, prerequisite and name are read from **every** per-civilisation tree that
  carries an entity's node id, then reduced to one civilisation-neutral baseline by majority vote
  (`_majority`), because civilisations legitimately disagree with each other here: Burgundians'
  well-attested "most Blacksmith, Barracks, Archery Range and Stable technologies become available
  one age earlier" bonus, and a matching pattern for Armenian infantry technologies, both show up as
  a lone civilisation's tree reporting an `age_id` one lower than every other civilisation's tree
  for the same, otherwise-shared technology. That is real civilisation-specific game data — exactly
  what a hand-transcribed effect (T644) exists to model — not an error in the pack, so it is not
  treated as an FR-028 disagreement here: recording it as one would misfile a bonus as a data defect
  and would flood `disagreements.toml` with every civilisation's legitimate variation. FR-028's
  disagreement check in this module is narrower and different in kind: it compares the pack's own
  two *tables* for a technology found in both (`Tech` and `unit_upgrades`), which claim to describe
  the exact same civilisation-neutral fact (a cost, a research time) rather than two different
    civilisations' realities. For this pack revision the two ids the tables share (34, 35) agree
  completely — checked, not assumed — so `disagreements.toml` is empty; the writer is proven against
  a synthetic, injected conflict in the test suite instead (`test_disagreements_toml_text_renders_a_
  synthetic_conflict`), so the mechanism is exercised even though nothing in this vendored source
  currently trips it.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from importlib import resources
from typing import Any, Final

#: The package this module's data is anchored to — see `snapshot.py`'s module docstring for why
#: `importlib.resources` and never a bare filesystem path.
_PACKAGE: Final[str] = "aoe2stats_knowledge"

#: The one pack this feature vendors (research.md D3: no lawful independent second dataset).
_PACK_NAME: Final[str] = "aoe2techtree"

#: `Cost` dict keys, as the pack spells them, to the lower-case resource names `rules.json` uses.
#: Fixed order: a cost is rendered with its resources always in this order, never dict-insertion
#: order, so two runs over identical data produce byte-identical output.
_RESOURCE_ORDER: Final[tuple[str, ...]] = ("Food", "Wood", "Gold", "Stone")

#: A per-civilisation tree's `use_type` field to this module's entity-kind vocabulary. `None` (the
#: "Common"/decorative entries the trees also carry) is deliberately absent, so such an entry is
#: skipped rather than mis-filed under an arbitrary kind.
_USE_TYPE_KIND: Final[Mapping[str, str]] = {
    "Unit": "unit",
    "Tech": "technology",
    "Building": "building",
}

#: A tree entry's `link_node_type` (the *kind* of the node a prerequisite link points at) to this
#: module's entity-kind vocabulary. Every value seen across the committed pack's 53 trees is listed
#: (`test_every_link_node_type_in_the_real_pack_is_mapped` asserts none is silently dropped).
_LINK_NODE_KIND: Final[Mapping[str, str]] = {
    "Unit": "unit",
    "UnitUpgrade": "unit",
    "UniqueUnit": "unit",
    "RegionalUnit": "unit",
    "Research": "technology",
    "BuildingTech": "building",
    "BuildingNonTech": "building",
    "UniqueBuilding": "building",
}


@dataclass(frozen=True, slots=True)
class Disagreement:
    """One FR-028 disagreement: the vendored pack's own two tables describe the same
    civilisation-neutral fact differently. `readings` carries a short, human-readable rendering of
    each table's value, keyed by the table's own name (`"tech"`, `"unit_upgrades"`); `stored`
    identifies which one `rules.json` carries and why."""

    entity_kind: str
    entity_id: str
    field: str
    stored_source: str
    reason: str
    readings: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class NormalisedPack:
    """The normaliser's output: `entities["unit" | "building" | "technology"][id]` and any
    FR-028 disagreements found while building it."""

    entities: Mapping[str, Mapping[str, Mapping[str, Any]]]
    civilisations: tuple[str, ...]
    disagreements: tuple[Disagreement, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class _TreeReading:
    """One per-civilisation tree's account of one entity's civilisation-neutral facts."""

    civilisation: str
    age_id: int | None
    produced_at: int | None
    prerequisite: tuple[str, int] | None
    name: str | None


def _pack_root() -> resources.abc.Traversable:
    """The packaged pack root, resolved through `importlib.resources` alone — the same mechanism
    `snapshot.py` uses for `snapshots/`, extended here to `packs/` (see this package's
    `pyproject.toml` `force-include` and the `packs` symlink beside `snapshots`)."""
    return resources.files(_PACKAGE).joinpath("packs").joinpath(_PACK_NAME)


def _load_pack_json(relative_path: str) -> Any:
    return json.loads(_pack_root().joinpath(relative_path).read_text(encoding="utf-8"))


def _civilisation_names() -> tuple[str, ...]:
    """Every civilisation the pack's top-level `civs` table names, sorted — the "civilisations"
    this normaliser is asked to carry (FR-022). Not wired into a query surface here: which
    civilisations are *modelled* (their bonuses hand-transcribed) is T645's concern, not this
    normaliser's; this list is simply what the pack itself contains."""
    data = _load_pack_json("data.json")
    return tuple(sorted(data["civs"].keys()))


def _tree_filenames() -> tuple[str, ...]:
    """The `trees/*.json` filenames actually committed, sorted — never a bare filesystem walk."""
    trees_dir = _pack_root().joinpath("trees")
    return tuple(
        sorted(entry.name for entry in trees_dir.iterdir() if entry.name.endswith(".json"))
    )


def _resolve_name(entry: Mapping[str, Any], strings: Mapping[str, str]) -> str | None:
    """A tree entry's display name: the English string for its `name_string_id` if the pack's
    `strings.en.json` carries one, falling back to the entry's own `name` field (present on every
    entry observed in this pack revision) and finally to `None` — never a fabricated name."""
    string_id = entry.get("name_string_id")
    if string_id is not None:
        text = strings.get(str(string_id))
        if text:
            return text
    name = entry.get("name")
    return name if isinstance(name, str) and name else None


def _reading_from_building_entry(
    civilisation: str, entry: Mapping[str, Any], strings: Mapping[str, str]
) -> _TreeReading:
    upgraded_from = entry.get("building_upgraded_from_id")
    prerequisite = ("building", upgraded_from) if upgraded_from not in (None, -1) else None
    return _TreeReading(
        civilisation=civilisation,
        age_id=entry.get("age_id"),
        produced_at=None,
        prerequisite=prerequisite,
        name=_resolve_name(entry, strings),
    )


def _reading_from_units_techs_entry(
    civilisation: str, entry: Mapping[str, Any], strings: Mapping[str, str]
) -> _TreeReading:
    link_id = entry.get("link_id")
    link_kind = _LINK_NODE_KIND.get(entry.get("link_node_type", ""))
    prerequisite = (link_kind, link_id) if link_id is not None and link_kind is not None else None
    return _TreeReading(
        civilisation=civilisation,
        age_id=entry.get("age_id"),
        produced_at=entry.get("building_id"),
        prerequisite=prerequisite,
        name=_resolve_name(entry, strings),
    )


def _collect_tree_readings(
    tree_by_civilisation: Mapping[str, Mapping[str, Any]], strings: Mapping[str, str]
) -> dict[tuple[str, int], list[_TreeReading]]:
    """Every civilisation's account of every entity it carries, keyed by `(kind, node_id)`.

    A building's node id is its own `building_id`; a unit's or technology's is its `node_id` in
    the tree's `units_techs` array. Both `buildings` (top-level) and `units_techs` entries with
    `use_type: "Building"` contribute building readings — this pack revision carries two building
    ids (199, 1189) only through the latter, so reading only the former would silently drop them.
    """
    readings: dict[tuple[str, int], list[_TreeReading]] = defaultdict(list)
    for civilisation, tree in tree_by_civilisation.items():
        for entry in tree.get("buildings", []):
            key = ("building", entry["building_id"])
            readings[key].append(_reading_from_building_entry(civilisation, entry, strings))
        for entry in tree.get("units_techs", []):
            kind = _USE_TYPE_KIND.get(entry.get("use_type", ""))
            if kind is None:
                continue
            key = (kind, entry["node_id"])
            readings[key].append(_reading_from_units_techs_entry(civilisation, entry, strings))
    return readings


def _majority(values: Iterable[Any]) -> Any:
    """The most common non-`None` value, ties broken by which value was encountered first — the
    caller always passes values in a fixed, sorted-civilisation order, so this is deterministic
    across runs. `None` when every value is `None` (the field is absent from every reading)."""
    ordered = [value for value in values if value is not None]
    if not ordered:
        return None
    counts = Counter(ordered)
    highest = max(counts.values())
    for value in ordered:
        if counts[value] == highest:
            return value
    raise AssertionError("unreachable: ordered is non-empty")  # pragma: no cover


def _majority_reading(
    readings: Sequence[_TreeReading],
) -> tuple[int | None, int | None, tuple[str, int] | None, str | None]:
    return (
        _majority(reading.age_id for reading in readings),
        _majority(reading.produced_at for reading in readings),
        _majority(reading.prerequisite for reading in readings),
        _majority(reading.name for reading in readings),
    )


def _cost(raw_cost: Mapping[str, Any]) -> dict[str, int]:
    return {
        _RESOURCE_ORDER[index].lower(): raw_cost[resource]
        for index, resource in enumerate(_RESOURCE_ORDER)
        if resource in raw_cost
    }


def _entity_ref(node_id: int | None, kind: str) -> dict[str, str] | None:
    return {"kind": kind, "id": str(node_id)} if node_id is not None else None


def _prerequisites(prerequisite: tuple[str, int] | None) -> list[dict[str, str]]:
    if prerequisite is None:
        return []
    kind, node_id = prerequisite
    return [{"kind": kind, "id": str(node_id)}]


def _entity(
    *,
    name: str | None,
    cost: Mapping[str, int],
    time_field: str,
    time_value: Any,
    age_requirement: int | None,
    produced_at: dict[str, str] | None,
    prerequisites: list[dict[str, str]],
    table_origin: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "cost": dict(cost),
        time_field: time_value,
        "age_requirement": age_requirement,
        "produced_at": produced_at,
        "prerequisites": prerequisites,
        "table_origin": table_origin,
    }


def _technology_tree_lookup_key(
    technology_id: int, owning_unit_of_technology: Mapping[int, int]
) -> tuple[str, int]:
    """Where a technology's age/producing-building/prerequisite/name reading lives in the tree
    files: its own id under `"technology"` if the base `Tech` table names it, or its owning unit's
    id under `"unit"` if it is a `unit_upgrades`-only technology — the indirection this module's
    docstring describes, because the trees never use the upgrade technology's own id as a node id.
    """
    owning_unit = owning_unit_of_technology.get(technology_id)
    if owning_unit is not None:
        return ("unit", owning_unit)
    return ("technology", technology_id)


def normalise_pack_data(
    data: Mapping[str, Any],
    strings: Mapping[str, str],
    tree_by_civilisation: Mapping[str, Mapping[str, Any]],
) -> NormalisedPack:
    """The pure normaliser: every argument already parsed from JSON, so this is exercised with
    small, synthetic fixtures in the test suite as well as with the real, committed pack (through
    `normalise_pack`, which is the only caller that reads `importlib.resources`)."""
    table = data["data"]
    civilisations = tuple(sorted(data["civs"].keys()))
    tree_readings = _collect_tree_readings(tree_by_civilisation, strings)

    units: dict[str, dict[str, Any]] = {}
    for unit_id, raw in table["Unit"].items():
        age, produced_at, prerequisite, name = _majority_reading(
            tree_readings.get(("unit", int(unit_id)), ())
        )
        units[unit_id] = _entity(
            name=name,
            cost=_cost(raw.get("Cost", {})),
            time_field="training_time",
            time_value=raw.get("TrainTime"),
            age_requirement=age,
            produced_at=_entity_ref(produced_at, "building"),
            prerequisites=_prerequisites(prerequisite),
            table_origin="unit",
        )

    buildings: dict[str, dict[str, Any]] = {}
    for building_id, raw in table["Building"].items():
        age, _produced_at, prerequisite, name = _majority_reading(
            tree_readings.get(("building", int(building_id)), ())
        )
        buildings[building_id] = _entity(
            name=name,
            cost=_cost(raw.get("Cost", {})),
            time_field="construction_time",
            time_value=raw.get("TrainTime"),
            age_requirement=age,
            produced_at=None,
            prerequisites=_prerequisites(prerequisite),
            table_origin="building",
        )

    owning_unit_of_technology = {
        raw["ID"]: int(unit_id) for unit_id, raw in table["unit_upgrades"].items()
    }

    technologies: dict[str, dict[str, Any]] = {}
    for technology_id, raw in table["Tech"].items():
        lookup_kind, lookup_id = _technology_tree_lookup_key(
            int(technology_id), owning_unit_of_technology
        )
        age, produced_at, prerequisite, name = _majority_reading(
            tree_readings.get((lookup_kind, lookup_id), ())
        )
        entity = _entity(
            name=name,
            cost=_cost(raw.get("Cost", {})),
            time_field="research_time",
            time_value=raw.get("ResearchTime"),
            age_requirement=age,
            produced_at=_entity_ref(produced_at, "building"),
            prerequisites=_prerequisites(prerequisite),
            table_origin="tech",
        )
        entity["upgrades_unit"] = None
        technologies[technology_id] = entity

    disagreements: list[Disagreement] = []
    for unit_id, raw in table["unit_upgrades"].items():
        technology_id = str(raw["ID"])
        cost = _cost(raw.get("Cost", {}))
        research_time = raw.get("ResearchTime")
        if technology_id in technologies:
            existing = technologies[technology_id]
            if existing["cost"] != cost or existing["research_time"] != research_time:
                disagreements.append(
                    Disagreement(
                        entity_kind="technology",
                        entity_id=technology_id,
                        field="cost/research_time",
                        stored_source="tech",
                        reason=(
                            "the base Tech table and the unit_upgrades table both name this "
                            "technology id and disagree on cost or research time; the Tech "
                            "table's own value is kept, as the table this pack's other "
                            "technologies are keyed from"
                        ),
                        readings={
                            "tech": (
                                f"cost={existing['cost']!r}, "
                                f"research_time={existing['research_time']!r}"
                            ),
                            "unit_upgrades": f"cost={cost!r}, research_time={research_time!r}",
                        },
                    )
                )
            existing["table_origin"] = "tech+unit_upgrades"
            existing["upgrades_unit"] = unit_id
            continue
        lookup_kind, lookup_id = _technology_tree_lookup_key(
            int(technology_id), owning_unit_of_technology
        )
        age, produced_at, prerequisite, tree_name = _majority_reading(
            tree_readings.get((lookup_kind, lookup_id), ())
        )
        entity = _entity(
            name=tree_name or raw.get("internal_name"),
            cost=cost,
            time_field="research_time",
            time_value=research_time,
            age_requirement=age,
            produced_at=_entity_ref(produced_at, "building"),
            prerequisites=_prerequisites(prerequisite),
            table_origin="unit_upgrades",
        )
        entity["upgrades_unit"] = unit_id
        technologies[technology_id] = entity

    return NormalisedPack(
        entities={"unit": units, "building": buildings, "technology": technologies},
        civilisations=civilisations,
        disagreements=tuple(disagreements),
    )


def normalise_pack() -> NormalisedPack:
    """Normalise the real, committed `packages/knowledge/packs/aoe2techtree/` pack, read entirely
    through `importlib.resources` (FR-026, SC-006: nothing here opens a socket or a filesystem
    path)."""
    data = _load_pack_json("data.json")
    strings = _load_pack_json("strings.en.json")
    tree_by_civilisation = {
        filename.removesuffix(".json"): _load_pack_json(f"trees/{filename}")
        for filename in _tree_filenames()
    }
    return normalise_pack_data(data, strings, tree_by_civilisation)


def rules_json_bytes(pack: NormalisedPack) -> bytes:
    """`rules.json`'s canonical bytes: sorted keys and a fixed indent, so re-running the
    normaliser over unchanged pack data reproduces the exact committed bytes, digest included."""
    document = {"entities": pack.entities, "civilisations": list(pack.civilisations)}
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


_NO_DISAGREEMENTS_TOML = """\
# Source disagreements (FR-028).
#
# This normaliser checks the one place the vendored pack itself carries two readings of the same
# civilisation-neutral fact: a technology id named by both the base Tech table and the
# unit_upgrades table (ids 34 and 35 in this pack revision, "War Galley" and its neighbour) is
# compared field by field. Both agree completely in this revision, so there is nothing to record
# here — "checked, found consistent", not "not checked".
#
# Per-civilisation tree files are a different kind of reading and are deliberately not compared
# here: where they disagree (e.g. Burgundians' and Armenians' well-attested early-technology
# bonuses showing up as a lone civilisation's tree naming an earlier age than every other
# civilisation's tree for the same technology), that is genuine civilisation-specific game data —
# exactly what a hand-transcribed effect (T644) exists to model — not an error in the pack. Filing
# it here would misfile a bonus as a data defect. rules.json takes the cross-civilisation majority
# as its civilisation-neutral baseline instead, silently.
#
# The writer that would populate this file (aoe2stats_knowledge.normalise.disagreements_toml_text)
# is exercised against a synthetic, injected conflict in
# packages/knowledge/tests/test_normalise.py, so the mechanism is proven working even though
# nothing in this one vendored source currently trips it.
"""


def disagreements_toml_text(disagreements: Sequence[Disagreement]) -> str:
    """FR-028's `disagreements.toml` content. Empty (bar an explanatory comment) when
    `disagreements` is empty — see `_NO_DISAGREEMENTS_TOML` and this module's docstring for why
    none has arisen from this pack revision's own cross-check."""
    if not disagreements:
        return _NO_DISAGREEMENTS_TOML
    lines: list[str] = []
    for disagreement in disagreements:
        lines.append("[[disagreement]]")
        lines.append(f"entity_kind = {json.dumps(disagreement.entity_kind)}")
        lines.append(f"entity_id = {json.dumps(disagreement.entity_id)}")
        lines.append(f"field = {json.dumps(disagreement.field)}")
        lines.append(f"stored_source = {json.dumps(disagreement.stored_source)}")
        lines.append(f"reason = {json.dumps(disagreement.reason)}")
        lines.append("")
        lines.append("[disagreement.readings]")
        for source, rendering in disagreement.readings.items():
            lines.append(f"{source} = {json.dumps(rendering)}")
        lines.append("")
    return "\n".join(lines) + "\n"
