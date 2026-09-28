"""T652q: a selector's *shape* — re-derived from the packaged source data itself, never trusted
from `effects.toml`'s own prose or from a previous transcription's hand-picked list.

Contract: [contracts/knowledge-base.md](../../../specs/006-replay-analysis-foundations/contracts/
knowledge-base.md), "Civilisation qualification". Research:
[research.md](../../../specs/006-replay-analysis-foundations/research.md) **D5**. Data model:
[data-model.md](../../../specs/006-replay-analysis-foundations/data-model.md) §6.

**The fourth review's blocker.** Persians' "Town Centers and Docks ... work +5/10/15/20% faster"
and Franks' "Chivalry (Stables work +40% faster)" both used to name, in their `selector`, the
producing building(s) themselves — so `production_time(unit 83 "Villager", "Persians")` matched
nothing at all and silently answered Teutons' own baseline, 25. `test_bullet_coverage.py` could
not see this: it only proves a `[[effect]]` row *exists* for a bullet, never that the row's own
`selector` points at what the bullet actually adjusts. This file proves the second half: for every
row whose bullet is a "works faster" production-speed bonus, and for Malians' "-15% wood" cost
bonus, the row's `selector` equals *exactly* the set this module derives independently from
`rules.json`'s own `produced_at`/`cost` fields and the civilisation's own tree file — never a
count, never a subset check, because either direction of a mismatch (an entity the bonus should
touch but the selector omits, or one the selector names but the civilisation cannot actually
reach) is the same defect FR-038 forbids: answering, or refusing to answer, on an invented fact.

**The absent-from-tree rule (T652q's own decision, applied identically to every selector in this
file).** `packages/knowledge/packs/aoe2techtree/trees/<CIV>.json` does not grid *every* entity a
civilisation can reach — a technology whose own id the base `Tech` table never carries at all
(`table_origin` naming `unit_upgrades`; `normalise.py`'s own module docstring: "the trees never
use the upgrade technology's own id as a node id") is never listed under its own id in *any*
civilisation's tree, in the committed pack, so this module first redirects such a technology to
its `upgrades_unit`'s own tree entry instead — the exact indirection `normalise.py`'s own
`_technology_tree_lookup_key`
already uses for age/producing-building/prerequisite/name, applied here to availability too, not a
new invention. Once resolved to the correct lookup key: an entity is **offered** to a civilisation
when that civilisation's own tree carries an entry for it whose `node_status` is anything other
than `NotAvailable`. An entity absent from that tree under the correct key — no entry at all, not
even one marked `NotAvailable` — is **not offered**: proven wrong as a blanket "default available"
reading by Franks' own tree, which simply omits 16 units and 9 unit-upgrade technologies (via their
owning unit) that belong to other civilisations' own regional or unique cavalry lines entirely,
rather than marking each one `NotAvailable` one by one. A per-civilisation absence is exactly the
signal FR-038 says this package must never paper over with a guess.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from importlib import resources
from typing import Any

import pytest

from aoe2stats_knowledge import effects

_PACKAGE = "aoe2stats_knowledge"
_PACK_NAME = "aoe2techtree"

_PROMOTED_DIRECTORY = "aoe2techtree-180059"
_PROMOTED_177723_DIRECTORY = "aoe2techtree-177723-test"

#: `packages/knowledge/packs/aoe2techtree/trees/<STEM>.json`'s own filename stem for each
#: civilisation this file checks — the pack's own naming (all-caps, no diacritics), not this
#: package's display name.
_TREE_FILE_STEM: Mapping[str, str] = {
    "Franks": "FRANKS",
    "Persians": "PERSIANS",
    "Malians": "MALIANS",
}

#: A tree entry's own `id` field is `"<Kind>_<node_id>_<building_id>"` — the middle component is
#: the entity this entry actually describes; the *last* component is only which grid column it is
#: drawn under (a Farm tile carries `id = "Building_50_68"`: node id 50, drawn under the Mill
#: column, building id 68 — keying by the outer `building_id` field instead, as this pack's own
#: top-level `buildings` list otherwise invites, silently loses Farm's own entry to Mill's).
_TREE_ID_PREFIX_TO_KIND: Mapping[str, str] = {
    "Unit": "unit",
    "Tech": "technology",
    "Building": "building",
}


def _rules() -> Mapping[str, Any]:
    """The packaged `rules.json` both promoted snapshots share (byte-identical pack, T645's own
    carry-forward record) — read once through `importlib.resources` (constitution III, SC-006),
    never a bare filesystem path."""
    root = resources.files(_PACKAGE).joinpath("snapshots").joinpath(_PROMOTED_DIRECTORY)
    return json.loads(root.joinpath("rules.json").read_text(encoding="utf-8"))


def _tree_index(civilisation: str) -> Mapping[tuple[str, str], str]:
    """Every entity `packages/knowledge/packs/aoe2techtree/trees/<CIV>.json` names, keyed by
    `(kind, node_id)` — its own `id` field parsed the same way for both the top-level `buildings`
    list and `units_techs` (this module's own docstring: keying by `buildings`' outer
    `building_id` instead loses an entry silently)."""
    root = resources.files(_PACKAGE).joinpath("packs").joinpath(_PACK_NAME).joinpath("trees")
    stem = _TREE_FILE_STEM[civilisation]
    data = json.loads(root.joinpath(f"{stem}.json").read_text(encoding="utf-8"))
    index: dict[tuple[str, str], str] = {}
    for entry in (*data["buildings"], *data["units_techs"]):
        prefix, node_id, _building_id = entry["id"].split("_")
        kind = _TREE_ID_PREFIX_TO_KIND.get(prefix)
        if kind is None:
            continue  # pragma: no cover - every real entry's prefix is one of the three above
        # First occurrence wins: a `units_techs` entry and a `buildings` entry never name the
        # same (kind, node_id) pair in the committed pack (checked directly, both promoted
        # civilisations this file uses), so there is nothing to prefer between them in practice.
        index.setdefault((kind, node_id), entry["node_status"])
    return index


def _lookup_key(rules: Mapping[str, Any], kind: str, entity_id: str) -> tuple[str, str]:
    """Where `(kind, entity_id)`'s own availability actually lives in a tree file — its own id,
    unless it is a technology whose `rules.json` record carries a non-null `upgrades_unit` (a
    `unit_upgrades`-origin technology, never gridded under its own id anywhere), in which case the
    tree entry for that owning unit is read instead (this module's own docstring, "the absent-from-
    tree rule")."""
    if kind == "technology":
        owning_unit = rules["entities"]["technology"][entity_id].get("upgrades_unit")
        if owning_unit:
            return ("unit", owning_unit)
    return (kind, entity_id)


def _offered(
    rules: Mapping[str, Any], tree: Mapping[tuple[str, str], str], kind: str, entity_id: str
) -> bool:
    """Whether `civilisation`'s own tree (already resolved to `tree`) offers `(kind, entity_id)` —
    present under its correct lookup key with a `node_status` other than `NotAvailable`. Absent
    under that key at all answers `False` (this module's own docstring: absence is not a
    default)."""
    status = tree.get(_lookup_key(rules, kind, entity_id))
    return status is not None and status != "NotAvailable"


def _entities_produced_at(
    rules: Mapping[str, Any], building_ids: frozenset[str]
) -> list[tuple[str, str]]:
    """Every unit and technology `rules.json` lists as `produced_at` one of `building_ids` — the
    mechanical half of a production-speed selector, before civilisation restriction."""
    found: list[tuple[str, str]] = []
    for kind in ("unit", "technology"):
        for entity_id, record in rules["entities"][kind].items():
            produced_at = record.get("produced_at")
            if produced_at is not None and produced_at.get("id") in building_ids:
                found.append((kind, entity_id))
    return found


def _expected_production_speed_selector(
    civilisation: str, building_ids: tuple[str, ...], *, condition: str | None
) -> frozenset[tuple[str, str]]:
    """**T652w, the fifth review's blocker.** A `condition = "team"` row's selector is never
    restricted by its own owner's tree: the row applies to every civilisation on the owner's team
    (`effects.py`'s `_matches`), and each ally's own tree — not the owner's — decides what that
    ally can actually research (`available_to` already answers that; T652q's own tree restriction
    was correct while this row refused for Malians alone, and stopped being correct the moment
    T652u turned it into a team effect, because it then silently answered no effect at all for
    every ally whose own tree the owner's selector had excluded). Every other row's selector still
    restricts to `civilisation`'s own tree (the owner is the only civilisation the row can ever
    apply to), stated once, here, rather than re-derived per condition at each call site."""
    rules = _rules()
    candidates = _entities_produced_at(rules, frozenset(building_ids))
    if condition == "team":
        return frozenset(candidates)
    tree = _tree_index(civilisation)
    return frozenset(
        (kind, entity_id)
        for kind, entity_id in candidates
        if _offered(rules, tree, kind, entity_id)
    )


#: **T652q's own explicit table.** The buildings each production-speed bullet names, keyed by the
#: row's `(civilisation, source_key)` — never parsed from `source_text`'s own prose, so a future
#: prose edit (a corrected translation, a rephrasing) cannot silently widen or narrow what this
#: test checks. Hand-read once, against `strings.en.json`'s own bullets and `rules.json`'s own
#: building names, the same way every selector in `effects.toml` itself is hand-read (data-model.md
#: §6: "by explicit identifier list, never by a fuzzy class name").
_PRODUCTION_SPEED_ROWS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("Franks", "120151", ("101",)),  # Stable
    ("Persians", "120157", ("109", "621", "45")),  # Town Center (109, 621), Dock (45)
    ("Malians", "120175", ("209",)),  # University
)


def _production_speed_rows(directory: str) -> tuple[effects.Effect, ...]:
    """Every `[[effect]]` row in `directory`'s `effects.toml` whose `field` is `production_time`
    and whose `source_text` says a building "works" ... "faster" — the shape this module's own
    docstring names, computed structurally rather than copied from `_PRODUCTION_SPEED_ROWS` above,
    so `test_every_production_speed_row_is_in_the_table_above` (below) has something independent
    to check the table against."""
    return tuple(
        effect
        for effect in effects._effects(directory)
        if effect.field == "production_time" and "faster" in effect.source_text.lower()
    )


@pytest.mark.parametrize("directory", [_PROMOTED_DIRECTORY, _PROMOTED_177723_DIRECTORY])
def test_every_production_speed_row_is_in_the_table_above(directory: str) -> None:
    """The defect this file exists to catch is not only "a wrong selector" but "a new
    production-speed row this file's own table never learned about" — a seventh civilisation
    someday adding its own "X work faster" bonus must extend `_PRODUCTION_SPEED_ROWS`, or this
    test fails loudly rather than the shape test below silently checking nothing for it."""
    observed = frozenset((e.civilisation, e.source_key) for e in _production_speed_rows(directory))
    expected = frozenset(
        (civilisation, source_key) for civilisation, source_key, _ in _PRODUCTION_SPEED_ROWS
    )
    assert observed == expected, (
        f"{directory}: effects.toml names a production_time '...faster' row "
        f"_PRODUCTION_SPEED_ROWS does not: {observed - expected!r} (or the table names one "
        f"effects.toml no longer has: {expected - observed!r})"
    )


@pytest.mark.parametrize("directory", [_PROMOTED_DIRECTORY, _PROMOTED_177723_DIRECTORY])
@pytest.mark.parametrize(("civilisation", "source_key", "building_ids"), _PRODUCTION_SPEED_ROWS)
def test_production_speed_row_selector_equals_every_entity_produced_at_the_named_buildings(
    directory: str, civilisation: str, source_key: str, building_ids: tuple[str, ...]
) -> None:
    """**T652q, item (2).** Fails on the *shape* of the fourth review's blocker, not the one
    instance it named: for this row, the real `effects.toml` `selector` must equal — exactly, not
    merely overlap — every unit and technology `rules.json` lists as `produced_at` one of
    `building_ids`, restricted to what `civilisation`'s own tree offers (this module's own
    docstring, "the absent-from-tree rule"). A selector naming the building(s) themselves, or an
    entity a different civilisation alone can reach, or missing one this civilisation genuinely
    has, all fail this the same way: a set mismatch, named directly."""
    (effect,) = [
        e
        for e in _production_speed_rows(directory)
        if e.civilisation == civilisation and e.source_key == source_key
    ]
    observed = frozenset((entry.kind, entry.id) for entry in effect.selector)
    expected = _expected_production_speed_selector(
        civilisation, building_ids, condition=effect.condition
    )
    restriction = (
        "no owner-tree restriction (a team row)"
        if effect.condition == "team"
        else f"{civilisation}'s own tree"
    )
    assert observed == expected, (
        f"{directory}: {civilisation}/{source_key}'s selector does not equal every entity "
        f"produced_at {building_ids}, restricted to {restriction} — named but should not "
        f"be: {sorted(observed - expected)!r}; offered but not named: "
        f"{sorted(expected - observed)!r}"
    )


def _expected_wood_discount_selector(civilisation: str) -> frozenset[tuple[str, str]]:
    rules = _rules()
    tree = _tree_index(civilisation)
    selected: set[tuple[str, str]] = set()
    for building_id, record in rules["entities"]["building"].items():
        name = record.get("name")
        cost = record.get("cost") or {}
        if not name:
            # T652q: building id 71 carries no name, no age_requirement and no produced_at at
            # all — an internal/placeholder rules.json record, not a real, player-facing building
            # any bonus could ever touch, wood cost or not.
            continue
        if cost.get("wood", 0) <= 0:
            continue
        if _offered(rules, tree, "building", building_id):
            selected.add(("building", building_id))
    return frozenset(selected)


@pytest.mark.parametrize("directory", [_PROMOTED_DIRECTORY, _PROMOTED_177723_DIRECTORY])
def test_malians_wood_discount_selector_equals_every_wood_costed_building_the_tree_offers(
    directory: str,
) -> None:
    """**T652q, item (3).** Malians' "Buildings cost -15% wood" used to omit Fish Trap (199) —
    real, `ResearchedCompleted` for Malians, but listed in the tree's own `units_techs` list
    (`Building_199_45`, drawn under the Dock's column) rather than the top-level `buildings` list
    every other entry in the previous, hand-picked selector happened to come from — and to name
    four buildings (Castle 82, Stone Wall 117, Fortified Wall 155, Gate 487) with no wood cost at
    all, harmless only because `effects.py`'s own "multiply" semantics leave an absent or zero
    resource key untouched. This selector must equal, exactly, every building `rules.json` gives a
    real name and a positive wood cost that Malians' own tree offers — never a superset, never a
    subset."""
    (effect,) = [
        e
        for e in effects._effects(directory)
        if e.civilisation == "Malians" and e.source_text == "Buildings cost -15% wood"
    ]
    observed = frozenset((entry.kind, entry.id) for entry in effect.selector)
    expected = _expected_wood_discount_selector("Malians")
    assert observed == expected, (
        f"{directory}: Malians' -15%-wood selector does not equal every wood-costed building "
        f"the tree offers — named but should not be: {sorted(observed - expected)!r}; offered "
        f"but not named: {sorted(expected - observed)!r}"
    )
