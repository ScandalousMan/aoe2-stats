"""T770: the civilisation effects of `aoe2techtree-185872-civilisations-56`, the sixth and last
build 185872 snapshot of Phase 8: it supersedes the fifth (`-44`) and models fifty-six
civilisations, every civilisation of the vendored pack.

Seven kinds of claim, none of them a restatement of `test_effects.py`, `test_bullet_coverage.py` or
the earlier snapshots' records (`test_effects_185872_civilisations*.py`, which keep those snapshots'
claims, pinned to them):

- **Nothing is dropped.** Every bullet of the twelve new civilisations' strings is an `[[effect]]`
  row's `source_text` or is in one closed registry, each entry a real bullet.
- **Nothing dangles.** Every row's `source_key` and `source_text` are the pack's own, every selector
  and condition entity exists in this snapshot's `rules.json`, and `civilisations_modelled` is the
  whole pack.
- **The forty-four are carried, with named exceptions.** Every row of the fifth snapshot is here, in
  place, byte for byte as a parsed row, but the Cumans' additional Town Center, Cuman Mercenaries
  and the Berbers' Kasbah, which the fifth refused because the effect model could not say them
  (T780, T781) and this one models, and the `validated_by` of the Persians' Kamandaran, amended.
  `rules.json`, `aliases.toml`, `disagreements.toml` and the raw-id table are the fifth's, byte for
  byte.
- **The values come out as the strings say**, one case per kind of row, each with the contrast case
  that must not apply, every expectation derived from the pack's own baseline and the bullet's
  arithmetic and not read back from the file under test.
- **The three replaced refusals are rows**, each answering with the state its condition needs and
  raising without it.
- **What is refused is refused for a stated reason**, and the reason is checked against the
  owner's sheet (`specs/006-replay-analysis-foundations/owner-readings.md`).
- **The validation sample is the snapshot's own answer.** One row per civilisation of the pack in
  the sheet's "Validation sample"; each is recomputed here through the public query surface from
  the entity, the age and the technologies the row states.
"""

from __future__ import annotations

import dataclasses
import functools
import json
import math
import re
import tomllib
from collections.abc import Mapping
from importlib import resources
from pathlib import Path

import pytest

from aoe2stats_knowledge import effects, gaps, query, snapshot

_PACKAGE = "aoe2stats_knowledge"
_PACK = "aoe2techtree-3bb43b1"
_DIRECTORY = "aoe2techtree-185872-civilisations-56"
_FIFTH_DIRECTORY = "aoe2techtree-185872-civilisations-44"
_BUILD = 185872
_FIFTH_DIGEST = "sha256:93d084ea8886b4c2d98f67a7f02524f107ffab3c3bcb29142389ceac226dc263"
_OWNER_READINGS = (
    Path(__file__).resolve().parents[3]
    / "specs"
    / "006-replay-analysis-foundations"
    / "owner-readings.md"
)

#: `strings.en.json`'s `help_string_id` for each modelled civilisation in the second pack.
_HELP_STRING_ID: Mapping[str, str] = {
    "Franks": "120151",
    "Teutons": "120153",
    "Persians": "120157",
    "Saracens": "120158",
    "Malians": "120175",
    "Tatars": "120182",
    "Slavs": "120172",
    "Sicilians": "120186",
    "Britons": "120150",
    "Goths": "120152",
    "Japanese": "120154",
    "Chinese": "120155",
    "Byzantines": "120156",
    "Turks": "120159",
    "Vikings": "120160",
    "Mongols": "120161",
    "Celts": "120162",
    "Spanish": "120163",
    "Aztecs": "120164",
    "Mayans": "120165",
    "Huns": "120166",
    "Koreans": "120167",
    "Italians": "120168",
    "Hindustanis": "120169",
    "Incas": "120170",
    "Magyars": "120171",
    "Portuguese": "120173",
    "Ethiopians": "120174",
    "Berbers": "120176",
    "Khmer": "120177",
    "Malay": "120178",
    "Burmese": "120179",
    "Vietnamese": "120180",
    "Bulgarians": "120181",
    "Cumans": "120183",
    "Lithuanians": "120184",
    "Burgundians": "120185",
    "Poles": "120187",
    "Bohemians": "120188",
    "Dravidians": "120189",
    "Bengalis": "120190",
    "Gurjaras": "120191",
    "Romans": "120192",
    "Armenians": "120193",
    "Georgians": "120194",
    "Shu": "120198",
    "Wu": "120199",
    "Wei": "120200",
    "Jurchens": "120201",
    "Khitans": "120202",
    "Muisca": "120206",
    "Mapuche": "120207",
    "Tupi": "120208",
    "Saxons": "120209",
    "Varangians": "120210",
    "Danes": "120211",
}

#: Batch D (T770), in the order `tasks.md` files it.
_BATCH_D = (
    "Georgians",
    "Shu",
    "Wu",
    "Wei",
    "Jurchens",
    "Khitans",
    "Muisca",
    "Mapuche",
    "Tupi",
    "Saxons",
    "Varangians",
    "Danes",
)

#: The Persians' Kamandaran, the one row carried with its `validated_by` amended (the fifth's
#: promised that the validation sample reads the Archer's cost after it; the sample does not).
_AMENDED = (
    "Persians",
    "Kamandaran (Archer-line gold cost replaced by additional wood cost)",
)

#: The three rows of the fifth snapshot this one replaces, by (civilisation, field).
_REPLACED = (
    ("Cumans", "age_requirement"),
    ("Cumans", "available_to"),
    ("Berbers", "production_time"),
)

#: Bullets with no row: a class the pack does not enumerate, on a field this knowledge base does not
#: carry, or a resource, a start condition or a victory rule no entity carries. Each is reviewed
#: against the header comment of `effects.toml`, which lists the same.
_NO_SELECTOR_BULLETS: Mapping[str, tuple[str, ...]] = {
    "Georgians": (
        "Start with a Mule Cart",
        "Units and buildings receive -15% damage when located on higher elevation",
        "Mounted Units regenerate 2/8/14 HP per minute in Feudal/Castle/Imperial Age",
        "Svan Towers (Fortifications +2 attack; Watch Tower-line deals pass through damage)",
        "Aznauri Cavalry (Mounted Units take -20% population space)",
        "Team Bonus: Building repairs cost -25%",
    ),
    "Shu": (
        "Lumberjacks generate food in addition to wood",
        "Siege Weapons and Siege Warships move +10/15% faster in Castle/Imperial Age",
        "Team Bonus: Foot Archers +2 line of sight",
    ),
    "Wu": (
        "Military production buildings and Docks provide +55 food when built",
        "Infantry regenerates 10/15/30 HP per minute in Feudal/Castle/Imperial Age",
    ),
    "Wei": (
        "Receive one free Villager for each economic upgrade researched",
        "Tuntian (Soldiers passively produce food)",
        "Ming Guang Armor (Mounted Units +4 melee armor)",
        "Team Bonus: Cavalry +2 attack vs. Siege Weapons",
    ),
    "Jurchens": (
        "Meat of hunted and livestock animals doesn't decay",
        "Mounted Units and Fire Lancers attack +25% faster starting in Feudal Age",
        "Units receive -50% friendly fire damage",
        "Fortified Bastions (Fortifications regenerate 500 HP per minute)",
        "Thunderclap Bombs (Rocket Carts, Grenadiers and Lou Chuans detonate when defeated; projectiles produce additional explosions)",  # noqa: E501
        "Team Bonus: Gunpowder Units +2 line of sight",
    ),
    "Khitans": (
        "Lamellar Armor (Infantry and Skirmishers reflect 25% melee damage back to the attacker)",
        "Ordo Cavalry (Cavalry regenerates HP in combat)",
        "Team Bonus: Infantry +2 attack vs. Ranged Soldiers",
    ),
    "Muisca": (
        "Champi Warriors and Archery Range Units +1/2/3 melee armor in Feudal/Castle/Imperial Age",
        "Team Bonus: Natural gold sources last +15% longer",
    ),
    "Mapuche": (
        "Foragers drop off +25% food",
        "Infantry, Slingers and Skirmishers +5/10/15 HP in Feudal/Castle/Imperial Age",
        "Mounted Units generate +3 gold when defeating military units",
        "Enemy Castles are revealed on the map",
        "Team Bonus: Spearman-line and Skirmishers +2 line of sight",
    ),
    "Tupi": (
        "Start with +25 of each resource",
        "Fallen units return 15% of their cost",
        "Curare (Foot Archers and Fortifications deal poison damage)",
        "Team Bonus: Towers and Castles provide +10 population space",
    ),
    "Saxons": (
        "Towers and Castles fire +100% base arrows starting in Castle Age",
        "Shield Wall (Infantry gain additional armor when massed)",
        "Team Bonus: Repairers work +25% faster",
    ),
    "Varangians": ("Shepherding, fishing, and hunting also generate gold",),
    "Danes": (
        "Loot 25% of the resource cost of each destroyed building",
        "Hamask (Infantry deal more damage as they lose HP)",
        "Northmen's Fury (Mangonel-line and Catapult Galleons +1 range; Siege Weapons and Siege Warships +40% attack vs buildings)",  # noqa: E501
        "Team Bonus: Siege Weapons +2 line of sight",
    ),
}


def _pack_root() -> resources.abc.Traversable:
    return resources.files(_PACKAGE).joinpath("packs").joinpath(_PACK)


def _snapshot_root(directory: str = _DIRECTORY) -> resources.abc.Traversable:
    return resources.files(_PACKAGE).joinpath("snapshots").joinpath(directory)


def _strings() -> Mapping[str, str]:
    return json.loads(_pack_root().joinpath("strings.en.json").read_text(encoding="utf-8"))


def _rules() -> dict[str, dict[str, dict[str, object]]]:
    parsed: dict[str, dict[str, dict[str, object]]] = json.loads(
        _snapshot_root().joinpath("rules.json").read_text(encoding="utf-8")
    )["entities"]
    return parsed


def _bullets_for(help_string_id: str) -> tuple[str, ...]:
    """Every bonus bullet of one civilisation's string, as `test_bullet_coverage.py` reads them:
    each top-level and "Unique Techs:" bullet (a mid-bullet line break rejoined) and the one line
    after "Team Bonus:", prefixed with that label. The unique units' names are not bonuses."""
    lines = [
        line.strip() for line in _strings()[help_string_id].replace("<br>\n", "<br>").split("<br>")
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


def _effects(directory: str = _DIRECTORY) -> tuple[effects.Effect, ...]:
    return effects._effects(directory)


def _half_up(value: float) -> int:
    return math.floor(value + 0.5)


def _at(kind: str, building: str) -> tuple[str, ...]:
    """Every entity of `kind` the pack's rules place at `building`, by number."""
    table = _rules()[kind]
    return tuple(
        sorted(
            (i for i, rec in table.items() if (rec.get("produced_at") or {}).get("id") == building),  # type: ignore[attr-defined]
            key=int,
        )
    )


# ------------------------------------------------------------------------------ nothing is dropped


def test_every_registry_entry_is_a_real_bullet_of_the_second_pack() -> None:
    for civilisation in _BATCH_D:
        bullets = _bullets_for(_HELP_STRING_ID[civilisation])
        for entry in _NO_SELECTOR_BULLETS[civilisation]:
            assert entry in bullets, f"{civilisation}: {entry!r} is not a bullet"


def test_every_bullet_is_a_row_or_a_registry_entry_exactly_once() -> None:
    for civilisation in _BATCH_D:
        bullets = _bullets_for(_HELP_STRING_ID[civilisation])
        row_texts = {e.source_text for e in _effects() if e.civilisation == civilisation}
        registered = set(_NO_SELECTOR_BULLETS[civilisation])
        assert not row_texts & registered, f"{civilisation}: both a row and a registry entry"
        assert set(bullets) - (row_texts | registered) == set(), f"{civilisation}: dropped"
        assert (row_texts | registered) - set(bullets) == set(), f"{civilisation}: invented"
        assert len(row_texts | registered) == len(bullets)


def test_the_bullets_of_the_fifty_six_civilisations_number_three_hundred_and_ninety_three() -> None:
    """A guard on the reader: a changed pack string that silently shifted the count would move
    every assertion above together. The forty-four of the fifth snapshot are 308; batch D's twelve
    are 85."""
    assert sum(len(_bullets_for(key)) for key in _HELP_STRING_ID.values()) == 393
    assert sum(len(_bullets_for(_HELP_STRING_ID[name])) for name in _BATCH_D) == 85


# ------------------------------------------------------------------------------- nothing dangles


def test_every_row_carries_the_packs_own_key_and_a_bullet_of_its_own_civilisation() -> None:
    for effect in _effects():
        assert effect.civilisation in _HELP_STRING_ID
        assert effect.source_key == _HELP_STRING_ID[effect.civilisation]
        assert effect.source_text in _bullets_for(effect.source_key), effect.source_text


def test_every_selector_entry_exists_in_this_snapshots_rules() -> None:
    rules = _rules()
    for effect in _effects():
        for entry in effect.selector:
            assert entry.id in rules[entry.kind], (effect.civilisation, effect.source_text, entry)


def test_every_condition_names_entities_and_technologies_of_this_snapshot() -> None:
    rules = _rules()
    for effect in _effects():
        if "researched" in effect.conditions:
            assert effect.condition_technology in rules["technology"], effect.source_text
        if "controlled" in effect.conditions:
            for entry in effect.condition_entities or ():
                assert entry.id in rules[entry.kind]


def test_the_conditional_rows_name_the_technologies_the_bullets_name() -> None:
    technologies = _rules()["technology"]
    conditional = {
        (e.civilisation, e.condition_technology, e.field, e.conditions)
        for e in _effects()
        if "researched" in e.conditions
        and (e.civilisation in _BATCH_D or e.civilisation in {"Cumans", "Berbers"})
        and (e.civilisation in _BATCH_D or (e.civilisation, e.field) in _REPLACED)
    }
    assert conditional == {
        ("Muisca", "1366", "production_time", ("researched",)),
        ("Mapuche", "1380", "cost", ("researched", "team")),
        ("Saxons", "1491", "production_time", ("researched",)),
        ("Cumans", "690", "available_to", ("researched", "team")),
        ("Berbers", "578", "production_time", ("researched", "team")),
    }
    names = {
        tech: " ".join(str(technologies[tech]["name"]).replace("<br>", " ").split())
        for _, tech, _, _ in conditional
    }
    assert names == {
        "1366": "Huaracas",
        "1380": "Butalmapu",
        "1491": "Clerical Recruitment",
        "690": "Cuman Mercenaries",
        "578": "Kasbah",
    }


def test_civilisations_modelled_is_the_whole_pack_and_the_set_the_effects_name() -> None:
    text = _snapshot_root().joinpath("snapshot.toml").read_text(encoding="utf-8")
    modelled = tomllib.loads(text)["snapshot"]["civilisations_modelled"]
    pack = set(
        json.loads(_snapshot_root().joinpath("rules.json").read_text("utf-8"))["civilisations"]
    )
    assert sorted(modelled) == sorted(_HELP_STRING_ID)
    assert set(modelled) == pack
    assert len(modelled) == 56
    assert {e.civilisation for e in _effects()} == set(modelled)


def test_the_raw_id_table_names_every_civilisation_of_the_pack_once() -> None:
    names = effects.civilisation_id_names(_DIRECTORY)
    pack = set(
        json.loads(_snapshot_root().joinpath("rules.json").read_text("utf-8"))["civilisations"]
    )
    assert sorted(names.values()) == sorted(pack)
    assert len(names) == 56


def test_the_validation_record_says_what_was_and_was_not_checked() -> None:
    current = snapshot.snapshot_for(_BUILD)
    assert isinstance(current, snapshot.Snapshot)
    assert current.directory == _DIRECTORY
    assert current.supersedes == _FIFTH_DIGEST
    assert current.normaliser_version == 2
    assert current.validation is not None
    assert current.validation.performed_at == "2026-10-26"
    assert current.validation.details["not_checked"].strip()
    assert current.validation.details["release_notes"]["url"].endswith("-update-185872/")


def test_every_row_of_batch_d_and_every_replaced_row_says_it_was_read_by_this_task() -> None:
    for effect in _effects():
        if effect.civilisation in _BATCH_D or (effect.civilisation, effect.field) in _REPLACED:
            if effect.civilisation in {"Cumans", "Berbers"} and "T770" not in effect.validated_by:
                continue  # a carried row of the Cumans or the Berbers, read by T769 or T768
            assert "T770" in effect.validated_by, (effect.civilisation, effect.source_text)
            assert effect.source_key in effect.validated_by


# ------------------------------------------------------- the forty-four are carried but three


def _row_key(effect: effects.Effect) -> tuple[str, str, str, tuple[tuple[str, str], ...]]:
    return (
        effect.civilisation,
        effect.source_text,
        effect.field,
        tuple((entry.kind, entry.id) for entry in effect.selector),
    )


def _replaced_positions(old: tuple[effects.Effect, ...]) -> list[int]:
    return [
        index
        for index, effect in enumerate(old)
        if (effect.civilisation, effect.field) in _REPLACED
        and effect.modelled == "no"
        and effect.source_text.startswith(("One additional", "Cuman Mercenaries", "Kasbah"))
    ]


def test_every_row_of_the_fifth_snapshot_is_carried_unchanged_but_the_named_exceptions() -> None:
    """Same build, same pack revision, same strings: a row is carried, not re-derived. Compared as
    parsed rows, every field including `validated_by`, and in the same order; the three refusals
    are in the same places and are rows now."""
    new = _effects()
    old = _effects(_FIFTH_DIRECTORY)
    replaced = _replaced_positions(old)
    assert len(replaced) == 3
    assert len(new) > len(old)
    for index, row in enumerate(old):
        if index in replaced:
            assert new[index] != row
            assert new[index].modelled == "yes", (row.civilisation, row.source_text)
            assert (new[index].civilisation, new[index].source_text, new[index].field) == (
                row.civilisation,
                row.source_text,
                row.field,
            )
        elif (row.civilisation, row.source_text) == _AMENDED:
            # The one carried row whose text was amended: it promised a reading the sample does
            # not make. Every parsed field but `validated_by` is the fifth's.
            assert dataclasses.replace(new[index], validated_by=row.validated_by) == row
            assert new[index].validated_by != row.validated_by
        else:
            assert new[index] == row, ("changed", row.civilisation, row.source_text)


def test_the_rows_beyond_the_fifth_are_batch_ds_and_only_batch_ds() -> None:
    old = _effects(_FIFTH_DIRECTORY)
    added = _effects()[len(old) :]
    assert added
    assert {e.civilisation for e in added} == set(_BATCH_D)
    assert {e.civilisation for e in old}.isdisjoint(_BATCH_D)


def test_the_rules_the_aliases_the_disagreements_and_the_raw_ids_are_the_fifths() -> None:
    for name in ("rules.json", "aliases.toml", "disagreements.toml"):
        assert (
            _snapshot_root().joinpath(name).read_bytes()
            == _snapshot_root(_FIFTH_DIRECTORY).joinpath(name).read_bytes()
        ), name
    assert dict(effects.civilisation_id_names(_DIRECTORY)) == dict(
        effects.civilisation_id_names(_FIFTH_DIRECTORY)
    )
    assert effects._civilisation_ids(_DIRECTORY) == effects._civilisation_ids(_FIFTH_DIRECTORY)


# --------------------------------------------------------------------------------- the values


def _entity(kind: str, entity_id: int | str) -> query.EntityRef:
    return query.EntityRef(kind=kind, id=str(entity_id), build=_BUILD)


def _value(result: object) -> object:
    assert not isinstance(result, gaps.KnowledgeGap), f"gap: {result!r}"
    return result.value  # type: ignore[attr-defined]


def _baseline(kind: str, entity_id: int | str, key: str) -> object:
    return _rules()[kind][str(entity_id)][key]


def _refused(result: object, civilisation: str) -> None:
    assert isinstance(result, gaps.KnowledgeGap), f"expected a refusal, got {result!r}"
    assert result.cause == "effect-not-modelled"
    assert result.civilisation == civilisation
    assert result.detail


def _alone(civilisation: str, **kwargs: object) -> effects.Context:
    """A context for a player with no ally: the team is the civilisation, nothing researched."""
    team = frozenset({civilisation})
    return effects.Context(team=team, team_researched=frozenset(), **kwargs)  # type: ignore[arg-type]


def _scaled(base: object, factor: float, resources: tuple[str, ...]) -> dict[str, int]:
    return {
        resource: (_half_up(amount * factor) if resource in resources else amount)
        for resource, amount in base.items()  # type: ignore[attr-defined]
    }


_ALL = ("food", "gold", "stone", "wood")


def test_shu_archery_range_and_archer_blacksmith_technologies_cost_a_quarter_less() -> None:
    members = (*_at("technology", "87"), "199", "200", "201", "211", "212", "219")
    for tech in members:
        base = _baseline("technology", tech, "cost")
        assert _value(query.cost(_entity("technology", tech), civilisation="Shu")) == _scaled(
            base, 0.75, _ALL
        )
        assert _value(query.cost(_entity("technology", tech), civilisation="Franks")) == base
    assert _value(query.cost(_entity("technology", 100), civilisation="Shu")) == {
        "food": _half_up(175 * 0.75),
        "gold": 75,
    }
    # Contrast: an infantry Blacksmith technology (Forging) and a Barracks one are not archery.
    assert _value(query.cost(_entity("technology", 67), civilisation="Shu")) == {"food": 150}
    assert _value(query.cost(_entity("technology", 215), civilisation="Shu")) == {"food": 100}


def test_wu_careening_and_dry_dock_are_free_and_their_team_builds_houses_faster() -> None:
    for tech in (374, 375):
        assert _value(query.cost(_entity("technology", tech), civilisation="Wu")) == {
            "food": 0,
            "gold": 0,
        }
        assert (
            _value(
                query.production_time(
                    _entity("technology", tech), civilisation="Wu", context=_alone("Wu")
                )
            )
            == 0
        )
        assert _value(query.cost(_entity("technology", tech), civilisation="Franks")) == (
            _baseline("technology", tech, "cost")
        )
    house = _entity("building", 70)
    base = _baseline("building", 70, "construction_time")
    allied = effects.Context(team=frozenset({"Franks", "Wu"}))
    assert _value(query.production_time(house, civilisation="Franks", context=allied)) == (
        pytest.approx(base / 2)  # type: ignore[operator]
    )
    assert (
        _value(
            query.production_time(
                house, civilisation="Franks", context=effects.Context(team=frozenset({"Franks"}))
            )
        )
        == base
    )
    with pytest.raises(effects.ContextRequired):
        query.production_time(house, civilisation="Franks")


def test_wei_traction_trebuchets_and_lou_chuans_cost_a_quarter_less() -> None:
    for unit in (1942, 1948):
        base = _baseline("unit", unit, "cost")
        assert _value(query.cost(_entity("unit", unit), civilisation="Wei")) == _scaled(
            base, 0.75, _ALL
        )
        assert _value(query.cost(_entity("unit", unit), civilisation="Franks")) == base
    assert _value(query.cost(_entity("unit", 1942), civilisation="Wei")) == {
        "gold": _half_up(210 * 0.75),
        "wood": _half_up(175 * 0.75),
    }


def test_jurchens_siege_and_fortification_upgrades_lose_wood_and_research_twice_as_fast() -> None:
    members = (*_at("technology", "49"), "194", "140", "63", "322")
    for tech in members:
        base = _baseline("technology", tech, "cost")
        assert _value(query.cost(_entity("technology", tech), civilisation="Jurchens")) == _scaled(
            base, 0.25, ("wood",)
        )
        assert _value(
            query.production_time(
                _entity("technology", tech), civilisation="Jurchens", context=_alone("Jurchens")
            )
        ) == pytest.approx(_baseline("technology", tech, "research_time") / 2)  # type: ignore[operator]
        assert _value(query.cost(_entity("technology", tech), civilisation="Franks")) == base
    # Murder Holes: update 177723 states the bonus reaches it; it costs no wood, so only its time
    # moves.
    assert _value(query.cost(_entity("technology", 322), civilisation="Jurchens")) == {
        "food": 200,
        "stone": 100,
    }
    assert _value(query.cost(_entity("technology", 63), civilisation="Jurchens")) == {
        "food": 500,
        "wood": _half_up(350 * 0.25),
    }
    # Siege Engineers comes a generation earlier; the unit-free technology sets no unit's age.
    assert _baseline("technology", 377, "age_requirement") == 4
    assert _value(query.age_requirement(_entity("technology", 377), civilisation="Jurchens")) == 3
    assert _value(query.age_requirement(_entity("technology", 377), civilisation="Franks")) == 4


def test_the_jurchens_unclassed_technologies_are_refused_to_the_jurchens_only() -> None:
    for tech in (377, 608, 379):
        _refused(query.cost(_entity("technology", tech), civilisation="Jurchens"), "Jurchens")
        _refused(
            query.production_time(
                _entity("technology", tech), civilisation="Jurchens", context=_alone("Jurchens")
            ),
            "Jurchens",
        )
        assert _value(query.cost(_entity("technology", tech), civilisation="Franks")) == _baseline(
            "technology", tech, "cost"
        )


def test_khitans_pastures_replace_farms_and_skirmishers_and_scouts_train_faster() -> None:
    assert _value(query.available_to(_entity("building", 50), civilisation="Khitans")) is False
    assert _value(query.available_to(_entity("building", 1889), civilisation="Khitans")) is True
    assert _value(query.available_to(_entity("building", 50), civilisation="Franks")) is True
    assert _value(query.available_to(_entity("building", 1889), civilisation="Franks")) is False
    alone = _alone("Khitans")
    for kind, ident in (
        ("unit", 7),
        ("unit", 6),
        ("unit", 93),
        ("unit", 448),
        ("technology", 98),
        ("technology", 254),
    ):
        base = _baseline(kind, ident, "training_time" if kind == "unit" else "research_time")
        assert _value(
            query.production_time(_entity(kind, ident), civilisation="Khitans", context=alone)
        ) == pytest.approx(base / 1.15)  # type: ignore[operator]
    # Contrast: a Knight is none of them.
    assert _value(
        query.production_time(_entity("unit", 38), civilisation="Khitans", context=alone)
    ) == _baseline("unit", 38, "training_time")
    for kind, ident in (("technology", 218), ("unit", 474)):
        assert _baseline(kind, ident, "age_requirement") == 4
        assert _value(query.age_requirement(_entity(kind, ident), civilisation="Khitans")) == 3
        assert _value(query.age_requirement(_entity(kind, ident), civilisation="Franks")) == 4
    assert _value(query.cost(_entity("technology", 218), civilisation="Khitans")) == {
        "food": 450,
        "gold": 250,
    }


def test_muisca_ages_settlements_free_technologies_and_huaracas() -> None:
    assert _value(query.cost(_entity("technology", 102), civilisation="Muisca")) == {
        "food": 800,
        "gold": 100,
    }
    assert _value(query.cost(_entity("technology", 103), civilisation="Muisca")) == {
        "food": 1000,
        "gold": 400,
    }
    assert _value(query.cost(_entity("technology", 101), civilisation="Muisca")) == {"food": 500}
    assert _value(query.cost(_entity("technology", 102), civilisation="Franks")) == {
        "food": 800,
        "gold": 200,
    }
    assert _value(query.cost(_entity("building", 2556), civilisation="Muisca")) == {
        "wood": _half_up(125 * 0.67)
    }
    for tech in (48, 15):
        assert _value(query.cost(_entity("technology", tech), civilisation="Muisca")) == {
            "food": 0,
            "gold": 0,
        }
    slinger = _entity("unit", 185)
    done = effects.Context(researched=frozenset({"1366"}), team=frozenset({"Muisca"}))
    none = effects.Context(researched=frozenset(), team=frozenset({"Muisca"}))
    base = _baseline("unit", 185, "training_time")
    assert _value(query.production_time(slinger, civilisation="Muisca", context=done)) == (
        pytest.approx(base / 1.5)  # type: ignore[operator]
    )
    assert _value(query.production_time(slinger, civilisation="Muisca", context=none)) == base
    with pytest.raises(effects.ContextRequired):
        query.production_time(slinger, civilisation="Muisca")


def test_mapuche_settlements_train_the_spearman_line_and_skirmishers() -> None:
    for unit in (93, 358, 359, 7, 6):
        produced = _value(query.produced_at(_entity("unit", unit), civilisation="Mapuche"))
        assert [b.id for b in produced] == [  # type: ignore[attr-defined]
            _baseline("unit", unit, "produced_at")["id"],  # type: ignore[index]
            "2556",
        ]
        other = _value(query.produced_at(_entity("unit", unit), civilisation="Franks"))
        assert [b.id for b in other] == [_baseline("unit", unit, "produced_at")["id"]]  # type: ignore[attr-defined,index]
    # Contrast: an Archer is not one of them.
    assert [
        b.id for b in _value(query.produced_at(_entity("unit", 4), civilisation="Mapuche"))
    ] == ["87"]  # type: ignore[attr-defined]


def test_butalmapu_discounts_the_castle_unique_units_of_the_whole_team() -> None:
    knight = _entity("unit", 25)  # Teutonic Knight, a Castle unique unit of another civilisation
    base = _baseline("unit", 25, "cost")
    team = frozenset({"Teutons", "Mapuche"})
    done = effects.Context(team=team, team_researched=frozenset({"1380"}))
    none = effects.Context(team=team, team_researched=frozenset())
    assert _value(query.cost(knight, civilisation="Teutons", context=done)) == _scaled(
        base, 0.85, _ALL
    )
    assert _value(query.cost(knight, civilisation="Teutons", context=none)) == base
    # The Mapuche's own Kona, and the Bolas Rider at the Archery Range.
    for unit in (2566, 2569):
        b = _baseline("unit", unit, "cost")
        assert _value(
            query.cost(_entity("unit", unit), civilisation="Mapuche", context=done)
        ) == _scaled(b, 0.85, _ALL)
    # Contrast: the Trebuchet and the Petard are not unique units, and a Knight is not a Castle
    # unit.
    for unit in (331, 440, 38):
        assert _value(query.cost(_entity("unit", unit), civilisation="Teutons", context=done)) == (
            _baseline("unit", unit, "cost")
        )
    with pytest.raises(effects.ContextRequired):
        query.cost(knight, civilisation="Teutons", context=effects.Context(team=team))
    with pytest.raises(effects.ContextRequired):
        query.cost(knight, civilisation="Teutons")


def test_tupi_archery_range_and_barracks_technologies_cost_half_the_food() -> None:
    for tech in _at("technology", "87") + _at("technology", "12"):
        base = _baseline("technology", tech, "cost")
        assert _value(query.cost(_entity("technology", tech), civilisation="Tupi")) == _scaled(
            base, 0.5, ("food",)
        )
        assert _value(query.cost(_entity("technology", tech), civilisation="Franks")) == base
    assert _value(query.cost(_entity("technology", 602), civilisation="Tupi")) == {
        "food": _half_up(75 * 0.5),
        "gold": 25,
    }
    # Contrast: a Blacksmith technology is neither.
    assert _value(query.cost(_entity("technology", 67), civilisation="Tupi")) == {"food": 150}


@pytest.mark.parametrize(
    ("count", "factor"), [(0, 1.0), (1, 0.95), (2, 0.9), (3, 0.85), (4, 0.8), (5, 0.8), (9, 0.8)]
)
def test_saxons_infantry_cost_five_percent_less_per_town_center_or_castle_to_a_maximum(
    count: int, factor: float
) -> None:
    counted = frozenset(effects.SelectorEntry("building", i) for i in ("71", "109", "621", "82"))
    context = effects.Context(controlled={counted: count}, team=frozenset({"Saxons"}))
    for unit in (74, 2703):
        base = _baseline("unit", unit, "cost")
        assert _value(
            query.cost(_entity("unit", unit), civilisation="Saxons", context=context)
        ) == (_scaled(base, factor, _ALL))
        assert _value(query.cost(_entity("unit", unit), civilisation="Franks")) == base
    with pytest.raises(effects.ContextRequired):
        query.cost(_entity("unit", 74), civilisation="Saxons")
    # A count stated for the Town Centers alone does not answer the question about both.
    only_tc = frozenset(effects.SelectorEntry("building", i) for i in ("71", "109", "621"))
    with pytest.raises(effects.ContextRequired):
        query.cost(
            _entity("unit", 74),
            civilisation="Saxons",
            context=effects.Context(controlled={only_tc: 4}),
        )


def test_saxons_ranged_foot_units_and_the_clerical_recruitment_monk() -> None:
    for unit in (4, 24, 492, 7, 6):
        _refused(query.cost(_entity("unit", unit), civilisation="Saxons"), "Saxons")
        assert _value(query.cost(_entity("unit", unit), civilisation="Franks")) == _baseline(
            "unit", unit, "cost"
        )
    monk = _entity("unit", 125)
    done = effects.Context(researched=frozenset({"1491"}), team=frozenset({"Saxons"}))
    none = effects.Context(researched=frozenset(), team=frozenset({"Saxons"}))
    assert _value(query.production_time(monk, civilisation="Saxons", context=done)) == (
        pytest.approx(51 / 1.33)
    )
    assert _value(query.production_time(monk, civilisation="Saxons", context=none)) == 51


def test_danes_barracks_and_siege_workshop_technologies_cost_two_thirds_less_gold() -> None:
    for tech in _at("technology", "12") + _at("technology", "49"):
        base = _baseline("technology", tech, "cost")
        assert _value(query.cost(_entity("technology", tech), civilisation="Danes")) == _scaled(
            base, 0.34, ("gold",)
        )
        assert _value(query.cost(_entity("technology", tech), civilisation="Franks")) == base
    assert _value(query.cost(_entity("technology", 207), civilisation="Danes")) == {
        "food": 150,
        "gold": _half_up(65 * 0.34),
    }
    # Contrast: a Monastery technology is neither.
    assert _value(query.cost(_entity("technology", 46), civilisation="Danes")) == {
        "food": 100,
        "gold": 200,
    }


def test_the_civilisations_whose_bonuses_touch_no_carried_value_answer_the_baseline() -> None:
    """Georgians and Varangians: every row is a refusal row or a registry entry; nothing here is a
    value this knowledge base carries, so a unit they train answers the pack's own cost."""
    for civilisation in ("Georgians", "Varangians"):
        rows = [e for e in _effects() if e.civilisation == civilisation]
        assert all(e.modelled == "no" for e in rows)
        assert {e.field for e in rows}.isdisjoint(
            {"cost", "production_time", "age_requirement", "produced_at", "available_to"}
        )
    # A Castle unique unit is also reached by the Mapuche's Butalmapu, a team row, so the query
    # states the team and that nothing was researched.
    assert _value(
        query.cost(_entity("unit", 1803), civilisation="Georgians", context=_alone("Georgians"))
    ) == {"food": 60, "gold": 45}
    assert _value(
        query.cost(_entity("unit", 2708), civilisation="Varangians", context=_alone("Varangians"))
    ) == {
        "food": 75,
        "gold": 55,
    }


# ------------------------------------------------------------ the three refusals that are rows now


def test_the_cumans_additional_town_center_is_a_feudal_age_building_until_two_are_controlled() -> (
    None
):
    counted = frozenset(effects.SelectorEntry("building", i) for i in ("71", "109", "621"))
    cases = {0: 2, 1: 2, 2: 3, 3: 3}
    assert _baseline("building", 621, "age_requirement") == 3
    for count, age in cases.items():
        context = effects.Context(controlled={counted: count})
        answer = query.age_requirement(
            _entity("building", 621), civilisation="Cumans", context=context
        )
        assert _value(answer) == age
        assert isinstance(_value(answer), int)
        # Contrast: every other civilisation answers the pack's age at every count.
        assert (
            _value(
                query.age_requirement(
                    _entity("building", 621), civilisation="Franks", context=context
                )
            )
            == 3
        )
    with pytest.raises(effects.ContextRequired):
        query.age_requirement(_entity("building", 621), civilisation="Cumans")
    # The other Town Centers are not touched.
    assert _value(query.age_requirement(_entity("building", 109), civilisation="Cumans")) == 1


def test_cuman_mercenaries_makes_the_free_elite_kipchak_available_to_the_whole_team() -> None:
    kipchak = _entity("unit", 1260)
    team = frozenset({"Cumans", "Franks"})
    done = effects.Context(team=team, team_researched=frozenset({"690"}))
    none = effects.Context(team=team, team_researched=frozenset())
    assert _value(query.available_to(kipchak, civilisation="Cumans", context=done)) is True
    assert _value(query.available_to(kipchak, civilisation="Franks", context=done)) is True
    assert _value(query.available_to(kipchak, civilisation="Franks", context=none)) is False
    # An ally of nobody on the Cumans' team never gets it.
    elsewhere = effects.Context(team=frozenset({"Franks"}), team_researched=frozenset({"690"}))
    assert _value(query.available_to(kipchak, civilisation="Franks", context=elsewhere)) is False
    with pytest.raises(effects.ContextRequired):
        query.available_to(kipchak, civilisation="Cumans", context=effects.Context(team=team))


def test_the_berbers_kasbah_speeds_up_the_castles_of_the_whole_team() -> None:
    team = frozenset({"Berbers", "Teutons"})
    done = effects.Context(team=team, team_researched=frozenset({"578"}))
    none = effects.Context(team=team, team_researched=frozenset())
    members = _at("unit", "82") + _at("technology", "82")
    assert len(members) == 118 + 168
    for kind, ident in (
        ("unit", "25"),
        ("unit", "1007"),
        ("technology", "315"),
        ("technology", "364"),
    ):
        base = _baseline(kind, ident, "training_time" if kind == "unit" else "research_time")
        for civilisation in ("Berbers", "Teutons"):
            assert _value(
                query.production_time(_entity(kind, ident), civilisation=civilisation, context=done)
            ) == pytest.approx(base / 1.25)  # type: ignore[operator]
            assert (
                _value(
                    query.production_time(
                        _entity(kind, ident), civilisation=civilisation, context=none
                    )
                )
                == base
            )
    # Contrast: a Barracks unit is not a Castle's.
    assert _value(
        query.production_time(_entity("unit", 74), civilisation="Teutons", context=done)
    ) == _baseline("unit", 74, "training_time")
    with pytest.raises(effects.ContextRequired):
        query.production_time(_entity("unit", 25), civilisation="Teutons")


# ------------------------------------------------------------------- the owner's open rows


def test_every_refused_reason_is_a_sentence_and_no_refusal_is_silent() -> None:
    for effect in _effects():
        if effect.modelled == "no":
            assert effect.reason and len(effect.reason) > 40, (
                effect.civilisation,
                effect.source_text,
            )


def test_the_blocking_refusals_of_batch_d_are_open_owner_rows_and_the_replaced_ones_are_gone() -> (
    None
):
    carried = {"cost", "production_time", "age_requirement", "produced_at", "available_to"}
    refusals = {
        (e.civilisation, e.field)
        for e in _effects()
        if e.civilisation in _BATCH_D and e.modelled == "no" and e.field in carried
    }
    assert refusals == {("Jurchens", "cost"), ("Jurchens", "production_time"), ("Saxons", "cost")}
    sheet = _OWNER_READINGS.read_text(encoding="utf-8")
    open_values = sheet[sheet.index("## Open values") : sheet.index("## Validation sample")]
    for civilisation, _ in refusals:
        assert f"| 185872 | {civilisation} |" in open_values, civilisation
    # The three refusals the effect model forced are modelled, so no row and no paragraph names
    # them.
    assert "| 185872 | Cumans |" not in open_values
    assert "| 185872 | Berbers |" not in open_values
    assert "Cuman Mercenaries" not in open_values
    assert "Kasbah" not in open_values
    assert not any(
        e.modelled == "no" and e.field in carried and e.civilisation in {"Cumans", "Berbers"}
        for e in _effects()
    )


# ------------------------------------------------------------------- the validation sample

_AGE_NUMBERS = {"Dark Age": 1, "Feudal Age": 2, "Castle Age": 3, "Imperial Age": 4}
_FUNCS = {
    "cost": query.cost,
    "production_time": query.production_time,
    "age_requirement": query.age_requirement,
    "available_to": query.available_to,
    "produced_at": query.produced_at,
}


def _sample_rows() -> list[list[str]]:
    sheet = _OWNER_READINGS.read_text(encoding="utf-8")
    section = sheet[sheet.index("## Validation sample") : sheet.index("## Production")]
    rows = [line for line in section.splitlines() if line.startswith("| ")]
    return [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in rows[2:]]


def test_the_validation_sample_has_one_row_per_civilisation_of_the_pack() -> None:
    rows = _sample_rows()
    pack = set(
        json.loads(_snapshot_root().joinpath("rules.json").read_text("utf-8"))["civilisations"]
    )
    assert sorted(row[0] for row in rows) == sorted(pack)
    assert len(rows) == 56
    for row in rows:
        assert len(row) == 7
        # T771 filled the last two columns: an independent reading for the two rows one was found
        # for, the declined-reading marker for every other row (spec Clarifications, Session
        # 2026-10-31; FR-030, amended), and the date either way.
        assert row[6] == "2026-10-31", row[0]
        if row[0] in _SAMPLE_READ:
            assert row[5] and not row[5].startswith("not read"), row[0]
        else:
            assert row[5] == _SAMPLE_DECLINED, row[0]


#: The validation-sample rows an independent source answered (T771), and the marker on the others.
_SAMPLE_READ = frozenset({"Teutons", "Vietnamese"})
_SAMPLE_DECLINED = (
    "not read: the owner declined in-game reading; T772 records the weaker form (FR-030, amended)"
)


def _sample_context(
    civilisation: str, entity: str, technologies: str, age: int | None
) -> effects.Context:
    """The context a sample row states: the technologies researched (by the owner and, for a team
    row, by the team), the owner alone on the team, the age when the row has one, and the count
    when the entity names it."""
    counted = re.search(r"with (\d+) Town Centers", entity)
    researched = frozenset(re.findall(r"\(technology (\d+)\)", technologies))
    fields: dict[str, object] = {
        "researched": researched,
        "team": frozenset({civilisation}),
        "team_researched": researched,
    }
    if counted:
        members = ("71", "109", "621", "82") if "Castles" in entity else ("71", "109", "621")
        fields["controlled"] = {
            frozenset(effects.SelectorEntry("building", i) for i in members): int(counted.group(1))
        }
    elif age is not None:
        fields["age"] = age
    return effects.Context(**fields)  # type: ignore[arg-type]


def _sample_answer(
    civilisation: str, kind: str, ident: str, field: str, context: effects.Context
) -> object:
    answer = _FUNCS[field](_entity(kind, ident), civilisation=civilisation, context=context)
    assert not isinstance(answer, gaps.KnowledgeGap), (civilisation, answer)
    got = answer.value
    if field == "produced_at":
        got = [b.id for b in got]  # type: ignore[attr-defined]
    return got


def test_every_row_of_the_validation_sample_is_what_the_snapshot_answers() -> None:
    for civilisation, entity, age, technologies, value, *_ in _sample_rows():
        match = re.search(r"\((unit|building|technology) (\d+)\)", entity)
        assert match, entity
        kind, ident = match.groups()
        field, rest = value.split(" ", 1)
        stated, _, remainder = rest.partition("; pack baseline ")
        expected = json.loads(stated)
        if age == "any":
            # "any" is a claim: the answer must be the same in each of the four ages.
            contexts = [
                _sample_context(civilisation, entity, technologies, a) for a in (1, 2, 3, 4)
            ]
        else:
            contexts = [_sample_context(civilisation, entity, technologies, _AGE_NUMBERS[age])]
        for context in contexts:
            got = _sample_answer(civilisation, kind, ident, field, context)
            if field == "production_time":
                assert got == pytest.approx(expected, abs=0.005), (civilisation, entity, context)
            else:
                assert got == expected, (civilisation, entity, context)
        baseline_text = remainder.split("; ")[0]
        rec = _rules()[kind][ident]
        if field == "cost":
            assert json.loads(baseline_text) == rec["cost"]
        elif field == "age_requirement":
            assert json.loads(baseline_text) == rec["age_requirement"]
        elif field == "production_time":
            time = rec.get("training_time", rec.get("research_time", rec.get("construction_time")))
            assert json.loads(baseline_text) == time
        if "no modelled bonus" in value:
            assert not _value_rows(civilisation), civilisation
        else:
            # The row is a bonus: the value differs from the pack's own.
            assert json.loads(baseline_text) != expected, (civilisation, entity)


# ------------------------------------------------------ the selection rule of the validation sample


def _value_rows(civilisation: str) -> list[effects.Effect]:
    """The civilisation's effects that can change a value this knowledge base carries: the modelled
    rows on a carried field, team rows included (a team bonus applies to its owner too)."""
    return [
        e
        for e in _effects()
        if e.civilisation == civilisation and e.modelled == "yes" and e.field in _FUNCS
    ]


def _sample_entity(entity: str) -> tuple[str, str]:
    match = re.search(r"\((unit|building|technology) (\d+)\)", entity)
    assert match, entity
    return match.group(1), match.group(2)


def test_every_sample_row_is_the_effect_that_changes_the_most_entities_team_rows_included() -> None:
    """T770: "each the effect that changes the most entities". An effect is one modelled row on a
    carried field; the entities it changes are its distinct selector entries. The sampled entity is
    inside the selector of a row whose field is the one the sample states, and no row of the
    civilisation has a larger selector. A civilisation with no such row is sampled at its baseline
    and says so."""
    tree = json.loads(_snapshot_root().joinpath("rules.json").read_text("utf-8"))
    problems: list[str] = []
    for civilisation, entity, _, _, value, *_ in _sample_rows():
        rows = _value_rows(civilisation)
        kind, ident = _sample_entity(entity)
        field = value.split(" ", 1)[0]
        if not rows:
            if "no modelled bonus" not in value:
                problems.append(f"{civilisation}: has no value-changing row and does not say so")
            continue
        if "no modelled bonus" in value:
            problems.append(f"{civilisation}: says it has no value-changing row but has some")
            continue
        largest = max(len(set(e.selector)) for e in rows)
        chosen = [
            e
            for e in rows
            if e.field == field
            and len(set(e.selector)) == largest
            and effects.SelectorEntry(kind, ident) in e.selector
        ]
        if not chosen:
            problems.append(f"{civilisation}: {entity} {field} is not in a selector of {largest}")
        # The player can read what the sample states: the entity is in the civilisation's tree.
        if ident not in tree["civilisations"][civilisation][kind]:
            problems.append(f"{civilisation}: {entity} is not in its tree")
    assert problems == []


def test_the_sample_text_states_no_exclusion_the_task_does_not() -> None:
    sheet = _OWNER_READINGS.read_text(encoding="utf-8")
    section = sheet[sheet.index("## Validation sample") : sheet.index("## Production")]
    assert "is not chosen" not in section
    assert "non-team" not in section


#: Where a row's text says the validation sample reads one of its inferences, the selector entries
#: that carry the inference. Reading any other entry of the selector reads the bonus, not the
#: inference.
_INFERENCE_ENTITIES: Mapping[tuple[str, str], frozenset[tuple[str, str]]] = {
    ("Shu", "Archery Unit technologies at the Archery Range and Blacksmith cost -25%"): frozenset(
        {("technology", "211"), ("technology", "212"), ("technology", "219")}
    ),
    ("Tupi", "Archery Range and Barracks upgrades cost -50% food"): frozenset(
        {("technology", "215"), ("technology", "602")}
    ),
    ("Danes", "Barracks and Siege Workshop upgrades cost -66% gold"): frozenset(
        {("technology", "215"), ("technology", "602")}
    ),
}

_EFFECTS_TOML = Path(__file__).resolve().parents[1] / "snapshots" / _DIRECTORY / "effects.toml"


def test_every_row_that_claims_the_sample_reads_it_has_a_sample_row_inside_the_inference() -> None:
    claimed = set()
    sample = [(row[0], _sample_entity(row[1])) for row in _sample_rows()]
    for effect in _effects():
        if not re.search(r"validation sample", effect.validated_by, re.IGNORECASE):
            continue
        key = (effect.civilisation, effect.source_text)
        claimed.add(key)
        assert key in _INFERENCE_ENTITIES, ("claims the sample reads it", key)
        assert any(
            civilisation == effect.civilisation
            and entity in _INFERENCE_ENTITIES[key]
            and effects.SelectorEntry(*entity) in effect.selector
            for civilisation, entity in sample
        ), ("no sample row reads the inference", key)
    # The registry is not stale: each of its rows still makes the claim it answers for.
    assert claimed == set(_INFERENCE_ENTITIES)


def test_the_header_lists_as_read_by_the_sample_only_inferences_a_sample_row_reads() -> None:
    header = "\n".join(
        line[1:].strip()
        for line in _EFFECTS_TOML.read_text("utf-8").splitlines()
        if line.startswith("#")
    )
    marker = "Inferences flagged in their rows and read by the validation sample:"
    assert marker in header
    paragraph = header[header.index(marker) :].split("\n\n")[0]
    named = {civilisation for civilisation in _BATCH_D if civilisation in paragraph}
    assert named == {civilisation for civilisation, _ in _INFERENCE_ENTITIES}, named
    # And the snapshot's own record makes no such claim.
    record = _snapshot_root().joinpath("snapshot.toml").read_text(encoding="utf-8")
    assert "validation sample" not in record


# ------------------------------------------------------------------------- the Jurchens' criterion

#: The one criterion that decides which technologies of the Jurchens' tree are "Siege and
#: Fortification upgrades" candidates, stated in the header of `effects.toml`: a technology the
#: Siege Workshop produces, or one whose help string (`LanguageNameId` + 21000 in `data.json`,
#: read from `strings.en.json`) names one of these words. The three Age advances are not
#: candidates: their help strings name the Castle and the Siege Workshop only as buildings the
#: player needs to advance.
_JURCHENS_WORDS = (
    "Siege Weapons",
    "Siege Warships",
    "Fortification",
    "Tower",
    "Castle",
    "Donjon",
    "Krepost",
    "Wall",
)
_AGE_ADVANCES = frozenset({"101", "102", "103"})
_SIEGE_WORKSHOP = "49"
_JURCHENS_BULLET = "Siege and Fortification upgrades cost -75% wood and research +100% faster"


@functools.cache
def _pack_data() -> dict[str, dict[str, dict[str, object]]]:
    parsed: dict[str, dict[str, dict[str, object]]] = json.loads(
        _pack_root().joinpath("data.json").read_text(encoding="utf-8")
    )["data"]
    return parsed


def _help_string(technology: str) -> str:
    data = _pack_data()
    record = data["Tech"].get(technology)
    if record is None:
        return ""  # a unit upgrade: the pack carries no help string of its own for it
    return _strings().get(str(record["LanguageNameId"] + 21000), "")  # type: ignore[call-overload]


def _jurchens_candidates() -> frozenset[str]:
    rules = _rules()
    document = json.loads(_snapshot_root().joinpath("rules.json").read_text("utf-8"))
    tree = document["civilisations"]["Jurchens"]["technology"]
    return frozenset(
        technology
        for technology in tree
        if technology not in _AGE_ADVANCES
        and (
            (rules["technology"][technology].get("produced_at") or {}).get("id") == _SIEGE_WORKSHOP  # type: ignore[attr-defined]
            or any(word in _help_string(technology) for word in _JURCHENS_WORDS)
        )
    )


def test_every_technology_the_jurchens_criterion_matches_is_modelled_or_refused_for_its_field() -> (
    None
):
    rules = _rules()["technology"]
    candidates = _jurchens_candidates()
    assert {"47", "93", "199", "322", "377", "996"} <= candidates, "the reader is broken"
    rows = [
        e for e in _effects() if e.civilisation == "Jurchens" and e.source_text == _JURCHENS_BULLET
    ]
    for field in ("cost", "production_time"):
        modelled = {
            s.id for e in rows if e.field == field and e.modelled == "yes" for s in e.selector
        }
        refused = {
            s.id for e in rows if e.field == field and e.modelled == "no" for s in e.selector
        }
        assert not modelled & refused, field
        # A cost row is needed only for a technology that costs wood: -75% wood leaves any other
        # cost as it is, whatever the game decides. A research-time row is needed for every match.
        required = {
            t
            for t in candidates
            if field == "production_time" or "wood" in rules[t]["cost"]  # type: ignore[operator]
        }
        assert required <= modelled | refused, (field, sorted(required - (modelled | refused)))
        # Nothing is refused that the criterion does not match or that the field does not need.
        assert refused <= required, (field, sorted(refused - required))
        assert (modelled & _jurchens_tree()) <= candidates, field


def _jurchens_tree() -> frozenset[str]:
    document = json.loads(_snapshot_root().joinpath("rules.json").read_text("utf-8"))
    return frozenset(document["civilisations"]["Jurchens"]["technology"])


def test_every_refused_jurchens_technology_is_an_open_owner_row_for_its_field() -> None:
    sheet = _OWNER_READINGS.read_text(encoding="utf-8")
    open_values = sheet[sheet.index("## Open values") : sheet.index("## Validation sample")]
    rows = [line for line in open_values.splitlines() if line.startswith("| 185872 | Jurchens |")]
    for effect in _effects():
        if effect.civilisation == "Jurchens" and effect.modelled == "no" and effect.field in _FUNCS:
            for entry in effect.selector:
                assert any(
                    f"| {effect.field} |" in row and f"({entry.id})" in row for row in rows
                ), (effect.field, entry.id)


# ----------------------------------------------------------- the wording of a refusal's reason

#: The sentence a refusal on a field this knowledge base does not carry uses: true of "heal rate",
#: false of a cost.
_UNCARRIED_TEMPLATE = "is a field this knowledge base does not carry"


def test_no_refusal_on_a_carried_field_says_the_field_is_not_carried() -> None:
    carried_refusals = [e for e in _effects() if e.modelled == "no" and e.field in _FUNCS]
    uncarried_refusals = [e for e in _effects() if e.modelled == "no" and e.field not in _FUNCS]
    assert carried_refusals and uncarried_refusals
    for effect in carried_refusals:
        assert _UNCARRIED_TEMPLATE not in (effect.reason or ""), (
            effect.civilisation,
            effect.field,
        )
        # It states the real unknown, and who can settle it (batch D's own rows).
        if effect.civilisation in _BATCH_D:
            assert "owner" in (effect.reason or ""), (effect.civilisation, effect.field)
    # Contrast: the wording is the one the uncarried fields use, so the check above is not empty.
    assert any(_UNCARRIED_TEMPLATE in (e.reason or "") for e in uncarried_refusals)


def test_the_gap_a_carried_field_refusal_raises_carries_its_real_reason() -> None:
    for technology in ("377", "93"):
        gap = query.cost(_entity("technology", technology), civilisation="Jurchens")
        assert isinstance(gap, gaps.KnowledgeGap)
        assert _UNCARRIED_TEMPLATE not in gap.detail
    gap = query.cost(_entity("unit", 4), civilisation="Saxons")
    assert isinstance(gap, gaps.KnowledgeGap)
    assert _UNCARRIED_TEMPLATE not in gap.detail


# --------------------------------------------------------- what the snapshot says of the Cumans


def test_the_cumans_town_center_count_is_not_restated_and_its_table_is_called_unvalidated() -> None:
    row = next(
        e
        for e in _effects()
        if e.civilisation == "Cumans"
        and e.field == "age_requirement"
        and e.source_text.startswith("One additional")
    )
    record = _snapshot_root().joinpath("snapshot.toml").read_text(encoding="utf-8")
    for text in (row.validated_by, record):
        # The measurement of the outside world lives in docs/data-sources.md, not here.
        assert not re.search(r"\b(seventeen|twenty)\b", text), text[:80]
        assert "data-sources.md" in text
    assert "unvalidated" in row.validated_by
    assert "unvalidated" in record
    # The outside-world measurement carries no claim about this repository's snapshot (CLAUDE.md:
    # never copy a measurement between homes, and never let it describe the code that reads it).
    docs = (Path(__file__).resolve().parents[3] / "docs" / "data-sources.md").read_text("utf-8")
    measured = docs[docs.index("names twenty identifiers exactly") :].split("\n\n")[0]
    assert "Cumans" not in measured
    assert "vendored pack" not in measured
