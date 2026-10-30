"""T769: the civilisation effects of `aoe2techtree-185872-civilisations-44`, the fifth build 185872
snapshot, which supersedes the fourth (`-32`) and models forty-four civilisations.

**Since T770 this snapshot is no longer the one the build resolves to**: the sixth,
`aoe2techtree-185872-civilisations-56`, supersedes it (`test_effects_185872_civilisations_56.py`).
This file keeps the fifth snapshot's own record, so every query below runs with that snapshot
pinned (`snapshot.pinned_snapshot`, SC-005): what it answered when it was current is what it still
answers. The one claim about the owner's sheet that described this snapshot's refusals (the two
Cuman bonuses named under the table) is dropped, because T770 removed that paragraph with the
refusals themselves; nothing the snapshot answers changed.

Six kinds of claim, none of them a restatement of `test_effects.py`, `test_bullet_coverage.py` or
the earlier snapshots' records (`test_effects_185872_civilisations*.py`, which keep those snapshots'
claims, pinned to them):

- **Nothing is dropped.** Every bullet of the twelve new civilisations' strings in the pack this
  snapshot is derived from, `aoe2techtree-3bb43b1`, is an `[[effect]]` row's `source_text` or is in
  one of two closed registries below, each entry a real bullet. Set difference and exact count, so a
  failure names the bullet. The registries name bullets that cannot be a row: a class of unit the
  pack does not enumerate on a field this knowledge base does not carry (`effects.Effect` requires a
  non-empty explicit selector), a resource or a start condition no entity carries, and one bullet
  whose entity is real and whose baseline already answers it.
- **Nothing dangles.** Every row's `source_key` and `source_text` are the pack's own, every selector
  entry exists in this snapshot's `rules.json`, every researched condition names a technology of it,
  and the `[[civilisation_id]]` table names every civilisation of the pack once.
- **The thirty-two civilisations of the fourth snapshot are carried.** Same build, same pack
  revision, same strings: every row of the fourth snapshot is in this one, parsed key for key, and
  so are its `rules.json`, `aliases.toml`, `disagreements.toml` and raw-id table, byte for byte.
- **The values come out as the strings say**, one case per kind of row, each with the contrast case
  that must not apply, every expectation derived from the pack's own baseline and the bullet's
  arithmetic and not read back from the file under test.
- **What is refused is refused for a stated reason**, and the reason is checked against the
  owner's sheet (`specs/006-replay-analysis-foundations/owner-readings.md`): the economic upgrades
  the pack never classes, Hussite Reforms' food, the Camel and Elephant Units, the Legionary, and
  two bonuses the effect model cannot express (Cumans' additional Town Center, Cuman Mercenaries).
- **A team row reaches the other civilisations' queries.** Bulgarians', Lithuanians', Bohemians'
  and Vietnamese teams touch entities every civilisation asks about, so those queries need
  `Context.team`; the cases below pass it.
"""

from __future__ import annotations

import json
import math
import tomllib
from collections.abc import Iterator, Mapping
from importlib import resources
from pathlib import Path

import pytest

from aoe2stats_knowledge import effects, gaps, query, snapshot

_PACKAGE = "aoe2stats_knowledge"
_PACK = "aoe2techtree-3bb43b1"
_DIRECTORY = "aoe2techtree-185872-civilisations-44"
_FOURTH_DIRECTORY = "aoe2techtree-185872-civilisations-32"
_BUILD = 185872
_FOURTH_DIGEST = "sha256:c24448836cade9ff724ac32935a52280a447df7278cb8cfe3f7cecd58dbf37ae"
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
}

#: Batch C (T769), in the order `tasks.md` files it.
_BATCH_C = (
    "Vietnamese",
    "Bulgarians",
    "Cumans",
    "Lithuanians",
    "Burgundians",
    "Poles",
    "Bohemians",
    "Dravidians",
    "Bengalis",
    "Gurjaras",
    "Romans",
    "Armenians",
)

#: Bullets with no row: a class the pack does not enumerate, on a field this knowledge base does not
#: carry, or a resource, a start condition or a victory rule no entity carries. Each is reviewed
#: against the header comment of `effects.toml`, which lists the same.
_NO_SELECTOR_BULLETS: Mapping[str, tuple[str, ...]] = {
    "Vietnamese": (
        "Enemy Town Centers are revealed at the start of the game",
        "Foot Archers and Skirmishers +20% HP",
        "Paper Money (Lumberjacks slowly generate gold in addition to wood)",
    ),
    "Bulgarians": ("Stirrups (Cavalry attacks +33% faster)",),
    "Cumans": ("Mounted Units move +5/10/15% faster in Feudal/Castle/Imperial Age",),
    "Lithuanians": (),
    "Burgundians": (
        "Gunpowder Units +25% attack",
        "Burgundian Vineyards (Farmers slowly generate gold in addition to food)",
        "Team Bonus: Relics generate food in addition to gold",
    ),
    "Poles": ("Stone Miners generate gold in addition to stone",),
    "Bohemians": ("Wagenburg Tactics (Gunpowder Units move +10% faster)",),
    "Dravidians": (
        "Receive +200 wood when advancing to the next Age",
        "Medical Corps (Elephant Units regenerate 30 HP per minute)",
        "Wootz Steel (Infantry and Cavalry attacks ignore armor)",
    ),
    "Bengalis": (
        "Cavalry +2 attack vs. Skirmishers",
        "Elephant Units receive -25% bonus damage and are more resistant to conversion",
        "Ships regenerate 15 HP per minute",
    ),
    "Gurjaras": (
        "Start with 2 Forage Bushes",
        "Mounted Units deal +20/30/40% bonus damage in Feudal/Castle/Imperial Age",
    ),
    "Romans": (),
    "Armenians": ("Team Bonus: Infantry +2 line of sight",),
}

#: A real entity whose baseline already answers the bullet, so a row would assert nothing.
_ENTITY_REPRESENTED_BUT_NEEDS_NO_EFFECT_ROW: Mapping[str, tuple[str, ...]] = {
    "Bulgarians": ("Can build Krepost in Castle Age",),
}

#: The economic upgrades the pack and the notes settle: the technologies produced at the Mill, the
#: Lumber Camp and the Mining Camp.
_ECONOMIC_SETTLED = ("12", "13", "14", "1012", "1013", "1014", "202", "203", "221")
_MINING = ("55", "182", "278", "279")
#: The technologies the pack places at the Town Center, the Dock and the Market that a reader could
#: call economic, and no source classes.
_ECONOMIC_CANDIDATES_COST_WOOD = ("213", "249", "65", "906")
_ECONOMIC_CANDIDATES_TIME = ("22", "213", "249", "65", "906", "15", "17", "23", "48")
_ECONOMIC_CANDIDATES_FOOD_AND_AGE = ("213", "249", "65", "906", "15", "17", "23", "48")
_MONASTERY_TECHNOLOGIES = (
    "45",
    "46",
    "230",
    "231",
    "233",
    "252",
    "316",
    "319",
    "438",
    "439",
    "441",
)


@pytest.fixture(autouse=True)
def _pin_the_fifth_snapshot() -> Iterator[None]:
    """The build resolves to a newer snapshot now; this file is about the fifth, found by its
    directory, which is a label and so only ever used to find the identity to pin."""
    (fifth,) = (s for s in snapshot.load_all_snapshots() if s.directory == _DIRECTORY)
    with snapshot.pinned_snapshot(fifth):
        yield


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
    for civilisation in _BATCH_C:
        bullets = _bullets_for(_HELP_STRING_ID[civilisation])
        registered = _NO_SELECTOR_BULLETS[
            civilisation
        ] + _ENTITY_REPRESENTED_BUT_NEEDS_NO_EFFECT_ROW.get(civilisation, ())
        for entry in registered:
            assert entry in bullets, f"{civilisation}: {entry!r} is not a bullet"


def test_every_bullet_is_a_row_or_a_registry_entry_exactly_once() -> None:
    for civilisation in _BATCH_C:
        bullets = _bullets_for(_HELP_STRING_ID[civilisation])
        row_texts = {e.source_text for e in _effects() if e.civilisation == civilisation}
        registered = set(_NO_SELECTOR_BULLETS[civilisation]) | set(
            _ENTITY_REPRESENTED_BUT_NEEDS_NO_EFFECT_ROW.get(civilisation, ())
        )
        assert not row_texts & registered, f"{civilisation}: both a row and a registry entry"
        assert set(bullets) - (row_texts | registered) == set(), f"{civilisation}: dropped"
        assert (row_texts | registered) - set(bullets) == set(), f"{civilisation}: invented"
        assert len(row_texts | registered) == len(bullets)


def test_the_bullets_of_the_forty_four_civilisations_number_three_hundred_and_eight() -> None:
    """A guard on the reader: a changed pack string that silently shifted the count would move
    every assertion above together. The thirty-two of the fourth snapshot are 222; batch C's twelve
    are 86."""
    assert sum(len(_bullets_for(key)) for key in _HELP_STRING_ID.values()) == 308
    assert sum(len(_bullets_for(_HELP_STRING_ID[name])) for name in _BATCH_C) == 86


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
        if "controlled" in effect.conditions:  # pragma: no cover - none in batches A to C
            for entry in effect.condition_entities or ():
                assert entry.id in rules[entry.kind]


def test_the_researched_conditions_of_batch_c_are_the_technologies_the_bullets_name() -> None:
    technologies = _rules()["technology"]
    conditional = {
        (e.civilisation, e.condition_technology, e.field)
        for e in _effects()
        if "researched" in e.conditions and e.civilisation in _BATCH_C
    }
    assert conditional == {
        ("Cumans", "689", "production_time"),
        ("Poles", "782", "cost"),
        ("Bohemians", "785", "cost"),
        ("Gurjaras", "835", "cost"),
        ("Romans", "884", "production_time"),
    }
    names = {
        tech: " ".join(str(technologies[tech]["name"]).replace("<br>", " ").split())
        for _, tech, _ in conditional
    }
    assert names["689"] == "Steppe Husbandry"
    assert names["782"] == "Szlachta Privileges"
    assert names["785"] == "Hussite Reforms"
    assert names["835"] == "Kshatriyas"
    assert names["884"] == "Comitatenses"


def test_civilisations_modelled_is_the_set_the_effects_name() -> None:
    text = _snapshot_root().joinpath("snapshot.toml").read_text(encoding="utf-8")
    modelled = tomllib.loads(text)["snapshot"]["civilisations_modelled"]
    assert sorted(modelled) == sorted(_HELP_STRING_ID)
    assert len(modelled) == 44
    assert {e.civilisation for e in _effects()} == set(modelled)


def test_the_raw_id_table_names_every_civilisation_of_the_pack_once() -> None:
    names = effects.civilisation_id_names(_DIRECTORY)
    pack = set(
        json.loads(_snapshot_root().joinpath("rules.json").read_text("utf-8"))["civilisations"]
    )
    assert len(pack) == 56
    assert sorted(names.values()) == sorted(pack), "one entry per civilisation of the pack"
    assert len(names) == 56
    # Contrast: the six Chronicles civilisations `aoc-reference-data` also keys are not the pack's.
    assert {"Achaemenids", "Athenians", "Spartans", "Macedonians", "Thracians", "Puru"}.isdisjoint(
        names.values()
    )


def test_every_raw_id_entry_says_what_it_rests_on() -> None:
    for entry in effects._civilisation_ids(_DIRECTORY):
        assert "aoc-reference-data" in entry.validated_by, entry.civilisation
        assert "Corroboration:" in entry.validated_by, entry.civilisation


def test_the_validation_record_says_what_was_and_was_not_checked() -> None:
    current = snapshot.snapshot_for(_BUILD)
    assert isinstance(current, snapshot.Snapshot)
    assert current.directory == _DIRECTORY
    assert current.supersedes == _FOURTH_DIGEST
    assert current.normaliser_version == 2
    assert current.validation is not None
    assert current.validation.performed_at == "2026-10-23"
    assert current.validation.details["not_checked"].strip()
    assert current.validation.details["release_notes"]["url"].endswith("-update-185872/")


def test_every_row_of_batch_c_says_it_was_read_by_this_task() -> None:
    for effect in _effects():
        if effect.civilisation in _BATCH_C:
            assert "T769" in effect.validated_by, (effect.civilisation, effect.source_text)
            assert effect.source_key in effect.validated_by


# ------------------------------------------------------------ the thirty-two are carried unchanged


def _row_key(effect: effects.Effect) -> tuple[str, str, str, tuple[tuple[str, str], ...]]:
    return (
        effect.civilisation,
        effect.source_text,
        effect.field,
        tuple((entry.kind, entry.id) for entry in effect.selector),
    )


def test_every_row_of_the_fourth_snapshot_is_carried_unchanged() -> None:
    """Same build, same pack revision, same strings: a row is carried, not re-derived (Phase 8's
    transcription rule). Compared as parsed rows, every field including `validated_by`, and in
    the same order."""
    new = _effects()
    old = _effects(_FOURTH_DIRECTORY)
    assert new[: len(old)] == old
    new_by_key = {_row_key(e): e for e in new}
    for row in old:
        assert new_by_key[_row_key(row)] == row, ("changed", row.civilisation, row.source_text)


def test_the_rows_beyond_the_thirty_two_are_batch_cs_and_only_batch_cs() -> None:
    old = _effects(_FOURTH_DIRECTORY)
    added = _effects()[len(old) :]
    assert added
    assert {e.civilisation for e in added} == set(_BATCH_C)
    assert {e.civilisation for e in old}.isdisjoint(_BATCH_C)


def test_the_rules_the_aliases_the_disagreements_and_the_raw_ids_are_the_fourths() -> None:
    for name in ("rules.json", "aliases.toml", "disagreements.toml"):
        assert (
            _snapshot_root().joinpath(name).read_bytes()
            == _snapshot_root(_FOURTH_DIRECTORY).joinpath(name).read_bytes()
        ), name
    assert dict(effects.civilisation_id_names(_DIRECTORY)) == dict(
        effects.civilisation_id_names(_FOURTH_DIRECTORY)
    )
    assert effects._civilisation_ids(_DIRECTORY) == effects._civilisation_ids(_FOURTH_DIRECTORY)


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


def _team(*civilisations: str) -> effects.Context:
    return effects.Context(team=frozenset(civilisations))


def _scaled(base: object, factor: float, resources: tuple[str, ...]) -> dict[str, int]:
    """The baseline cost with `factor` applied, half up, to the named resources only."""
    return {
        resource: (_half_up(amount * factor) if resource in resources else amount)
        for resource, amount in base.items()  # type: ignore[attr-defined]
    }


def test_vietnamese_pay_no_wood_for_mill_and_camp_technologies_and_research_them_faster() -> None:
    settled = _ECONOMIC_SETTLED + _MINING
    assert set(settled) == set(_at("technology", "68")) | set(_at("technology", "562")) | set(
        _at("technology", "584")
    )
    alone = _team("Vietnamese")
    for tech in settled:
        base = _baseline("technology", tech, "cost")
        assert _value(query.cost(_entity("technology", tech), civilisation="Vietnamese")) == {
            resource: (0 if resource == "wood" else amount)
            for resource, amount in base.items()  # type: ignore[attr-defined]
        }
        assert _value(
            query.production_time(
                _entity("technology", tech), civilisation="Vietnamese", context=alone
            )
        ) == pytest.approx(_baseline("technology", tech, "research_time") / 2)  # type: ignore[operator]
        # Contrast: another civilisation pays the baseline (not the Franks, whose Mill technologies
        # are free).
        assert _value(query.cost(_entity("technology", tech), civilisation="Britons")) == base
    # Gold Mining: 100 food and 75 wood become 100 food and no wood.
    assert _value(query.cost(_entity("technology", 55), civilisation="Vietnamese")) == {
        "food": 100,
        "wood": 0,
    }
    # Contrast: a Blacksmith technology is not economic.
    assert _value(query.cost(_entity("technology", 199), civilisation="Vietnamese")) == {
        "food": 100,
        "gold": 50,
    }


def test_vietnamese_conscription_is_free_and_their_team_trains_the_imperial_skirmisher() -> None:
    assert _value(query.cost(_entity("technology", 315), civilisation="Vietnamese")) == {
        "food": 0,
        "gold": 0,
    }
    assert (
        _value(
            query.production_time(
                _entity("technology", 315), civilisation="Vietnamese", context=_team("Vietnamese")
            )
        )
        == 0
    )
    assert _value(query.cost(_entity("technology", 315), civilisation="Franks")) == {
        "food": 150,
        "gold": 150,
    }
    for entity in (_entity("technology", 655), _entity("unit", 1155)):
        assert (
            _value(
                query.available_to(
                    entity, civilisation="Franks", context=_team("Franks", "Vietnamese")
                )
            )
            is True
        )
        assert (
            _value(query.available_to(entity, civilisation="Franks", context=_team("Franks")))
            is False
        )
    assert _baseline("technology", 655, "age_requirement") == 4


def test_the_technologies_no_source_classes_as_economic_are_refused_to_the_vietnamese_only() -> (
    None
):
    for tech in _ECONOMIC_CANDIDATES_COST_WOOD:
        _refused(query.cost(_entity("technology", tech), civilisation="Vietnamese"), "Vietnamese")
        assert _value(query.cost(_entity("technology", tech), civilisation="Franks")) == _baseline(
            "technology", tech, "cost"
        )
    for tech in _ECONOMIC_CANDIDATES_TIME:
        _refused(
            query.production_time(
                _entity("technology", tech), civilisation="Vietnamese", context=_team("Vietnamese")
            ),
            "Vietnamese",
        )
    # Contrast: Loom's gold cost has no wood, so its cost is not in question.
    assert _value(query.cost(_entity("technology", 22), civilisation="Vietnamese")) == {"gold": 50}


def test_bulgarians_militia_upgrades_are_free_and_forge_and_siege_technologies_cost_half_food() -> (
    None
):
    for tech in (222, 207, 217, 264):
        base = _baseline("technology", tech, "cost")
        assert _value(query.cost(_entity("technology", tech), civilisation="Bulgarians")) == {
            "food": 0,
            "gold": 0,
        }
        assert (
            _value(query.cost(_entity("technology", tech), civilisation="Franks")) == base  # type: ignore[comparison-overlap]
        )
        assert (
            _value(
                query.production_time(
                    _entity("technology", tech),
                    civilisation="Bulgarians",
                    context=_team("Bulgarians"),
                )
            )
            == 0
        )
    for tech in _at("technology", "103") + _at("technology", "49"):
        base = _baseline("technology", tech, "cost")
        assert _value(
            query.cost(_entity("technology", tech), civilisation="Bulgarians")
        ) == _scaled(base, 0.5, ("food",))
    # Contrast: a Barracks technology (Squires) is untouched.
    assert _value(query.cost(_entity("technology", 215), civilisation="Bulgarians")) == {
        "food": 100
    }


def test_bulgarians_town_centers_cost_half_stone_and_their_team_forges_faster() -> None:
    assert _value(query.cost(_entity("building", 109), civilisation="Bulgarians")) == {
        "stone": 50,
        "wood": 275,
    }
    assert _value(query.cost(_entity("building", 109), civilisation="Franks")) == {
        "stone": 100,
        "wood": 275,
    }
    tech = _entity("technology", 67)  # Forging, produced at the Blacksmith
    base = _baseline("technology", 67, "research_time")
    assert _value(
        query.production_time(tech, civilisation="Franks", context=_team("Franks", "Bulgarians"))
    ) == pytest.approx(base / 1.8)  # type: ignore[operator]
    assert _value(query.production_time(tech, civilisation="Franks", context=_team("Franks"))) == (
        base
    )
    # The Krepost: the baseline already answers "Castle Age" and the Bulgarians' tree offers it.
    assert _value(query.age_requirement(_entity("building", 1251), civilisation="Bulgarians")) == 3
    assert _value(query.available_to(_entity("building", 1251), civilisation="Bulgarians")) is True
    assert _value(query.available_to(_entity("building", 1251), civilisation="Franks")) is False


def test_cumans_archery_ranges_and_stables_cost_75_less_wood() -> None:
    assert _value(query.cost(_entity("building", 87), civilisation="Cumans")) == {"wood": 100}
    assert _value(query.cost(_entity("building", 101), civilisation="Cumans")) == {"wood": 100}
    assert _value(query.cost(_entity("building", 87), civilisation="Franks")) == {"wood": 175}
    assert _value(query.cost(_entity("building", 12), civilisation="Cumans")) == {"wood": 175}


def test_cumans_siege_workshop_and_rams_come_a_generation_earlier() -> None:
    expected = {  # kind, id -> (baseline age, age for the Cumans)
        ("building", 49): (3, 2),  # Siege Workshop
        ("unit", 1258): (3, 2),  # Battering Ram
        ("unit", 422): (4, 3),  # Capped Ram
        ("technology", 96): (4, 3),  # Capped Ram, the upgrade
    }
    for (kind, entity_id), (baseline, earlier) in expected.items():
        assert _baseline(kind, entity_id, "age_requirement") == baseline
        assert _value(query.age_requirement(_entity(kind, entity_id), civilisation="Cumans")) == (
            earlier
        )
        assert _value(query.age_requirement(_entity(kind, entity_id), civilisation="Franks")) == (
            baseline
        )
    # Contrast: the Siege Ram stays an Imperial Age unit.
    assert _value(query.age_requirement(_entity("unit", 548), civilisation="Cumans")) == 4


def test_cumans_steppe_husbandry_doubles_the_training_speed_of_the_scouts_lancers_and_archers() -> (
    None
):
    # Team rows of the Huns and the Britons reach the Stable and the Archery Range for any
    # civilisation, so the query names the team as well.
    researched = effects.Context(researched=frozenset({"689"}), team=frozenset({"Cumans"}))
    none = effects.Context(researched=frozenset(), team=frozenset({"Cumans"}))
    for unit in (448, 546, 441, 1707, 1370, 1372, 39, 474):
        base = _baseline("unit", unit, "training_time")
        assert _value(
            query.production_time(_entity("unit", unit), civilisation="Cumans", context=researched)
        ) == pytest.approx(base / 2)  # type: ignore[operator]
        assert (
            _value(
                query.production_time(_entity("unit", unit), civilisation="Cumans", context=none)
            )
            == base
        )
    # Contrast: a Knight is none of them, and another civilisation is not sped.
    assert _value(
        query.production_time(_entity("unit", 38), civilisation="Cumans", context=researched)
    ) == _baseline("unit", 38, "training_time")
    with pytest.raises(effects.ContextRequired):
        query.production_time(_entity("unit", 39), civilisation="Cumans")


def test_the_cumans_additional_town_center_and_mercenaries_are_refused_to_the_cumans_only() -> None:
    """Two bonuses the snapshot refuses. The additional Town Center needs an age that depends on how
    many Town Centers are controlled: `age_requirement` takes `context` since T780, but the row is
    not written yet (T770). Cuman Mercenaries needs a researched technology and the owner's team
    together (T781)."""
    _refused(query.age_requirement(_entity("building", 621), civilisation="Cumans"), "Cumans")
    _refused(
        query.available_to(_entity("unit", 1260), civilisation="Cumans", context=_team("Cumans")),
        "Cumans",
    )
    # Contrast: the other Town Centers and every other civilisation answer the baseline.
    assert _value(query.age_requirement(_entity("building", 109), civilisation="Cumans")) == 1
    assert _value(query.age_requirement(_entity("building", 621), civilisation="Franks")) == 3


def test_lithuanians_team_works_the_monastery_faster() -> None:
    allied = _team("Franks", "Lithuanians")
    members = _at("technology", "104")
    assert members == _MONASTERY_TECHNOLOGIES
    for tech in members:
        base = _baseline("technology", tech, "research_time")
        assert _value(
            query.production_time(
                _entity("technology", tech), civilisation="Franks", context=allied
            )
        ) == pytest.approx(base / 1.2)  # type: ignore[operator]
    monk = _entity("unit", 125)
    assert _baseline("unit", 125, "training_time") == 51
    assert _value(query.production_time(monk, civilisation="Franks", context=allied)) == (
        pytest.approx(51 / 1.2)
    )
    assert _value(query.production_time(monk, civilisation="Franks", context=_team("Franks"))) == 51
    # Contrast: a Barracks unit is not a Monastery's.
    assert _value(
        query.production_time(_entity("unit", 74), civilisation="Franks", context=allied)
    ) == _baseline("unit", 74, "training_time")
    with pytest.raises(effects.ContextRequired):
        query.production_time(monk, civilisation="Franks")


def test_burgundians_economic_upgrades_come_an_age_earlier_and_cost_40_percent_less_food() -> None:
    settled = _ECONOMIC_SETTLED + _MINING
    for tech in settled:
        base = _baseline("technology", tech, "cost")
        assert _value(
            query.cost(_entity("technology", tech), civilisation="Burgundians")
        ) == _scaled(base, 0.6, ("food",))
        age = _baseline("technology", tech, "age_requirement")
        assert _value(
            query.age_requirement(_entity("technology", tech), civilisation="Burgundians")
        ) == (age - 1)  # type: ignore[operator]
        assert (
            _value(query.age_requirement(_entity("technology", tech), civilisation="Franks")) == age
        )
    # Horse Collar is a Feudal Age technology (75 food, 75 wood) and the Burgundians' is a Dark Age
    # one at 45 food.
    assert _baseline("technology", 14, "age_requirement") == 2
    assert _value(query.age_requirement(_entity("technology", 14), civilisation="Burgundians")) == 1
    assert _value(query.cost(_entity("technology", 14), civilisation="Burgundians")) == {
        "food": 45,
        "wood": 75,
    }


def test_burgundians_stable_technologies_cost_half_and_the_cavalier_comes_in_the_castle_age() -> (
    None
):
    for tech in _at("technology", "101"):
        base = _baseline("technology", tech, "cost")
        assert _value(
            query.cost(_entity("technology", tech), civilisation="Burgundians")
        ) == _scaled(base, 0.5, tuple(base))  # type: ignore[arg-type]
    for kind, entity_id in (("technology", 209), ("unit", 283)):
        assert _baseline(kind, entity_id, "age_requirement") == 4
        assert (
            _value(query.age_requirement(_entity(kind, entity_id), civilisation="Burgundians")) == 3
        )
        assert _value(query.age_requirement(_entity(kind, entity_id), civilisation="Franks")) == 4
    # Contrast: the Paladin stays Imperial.
    assert _value(query.age_requirement(_entity("unit", 569), civilisation="Burgundians")) == 4


def test_the_technologies_no_source_classes_as_economic_are_refused_to_the_burgundians_only() -> (
    None
):
    for tech in _ECONOMIC_CANDIDATES_FOOD_AND_AGE:
        _refused(query.cost(_entity("technology", tech), civilisation="Burgundians"), "Burgundians")
        _refused(
            query.age_requirement(_entity("technology", tech), civilisation="Burgundians"),
            "Burgundians",
        )
        assert _value(
            query.age_requirement(_entity("technology", tech), civilisation="Franks")
        ) == _baseline("technology", tech, "age_requirement")
    # Contrast: Loom is a Dark Age technology that costs gold only, so neither value is in question.
    assert _value(query.cost(_entity("technology", 22), civilisation="Burgundians")) == {"gold": 50}
    assert _value(query.age_requirement(_entity("technology", 22), civilisation="Burgundians")) == 1


def test_poles_replace_the_mill_cheapen_the_scouts_upgrades_and_szlachta_cheapens_the_knights() -> (
    None
):
    mill, folwark = _entity("building", 68), _entity("building", 1734)
    assert _value(query.available_to(mill, civilisation="Poles")) is False
    assert _value(query.available_to(folwark, civilisation="Poles")) is True
    assert _value(query.available_to(mill, civilisation="Franks")) is True
    assert _value(query.available_to(folwark, civilisation="Franks")) is False
    for tech in (435, 254, 428, 786):
        base = _baseline("technology", tech, "cost")
        assert _value(query.cost(_entity("technology", tech), civilisation="Poles")) == _scaled(
            base, 0.5, ("food",)
        )
        assert _value(query.cost(_entity("technology", tech), civilisation="Franks")) == base
    # Contrast: Husbandry is a Stable technology that is none of them.
    assert _value(query.cost(_entity("technology", 39), civilisation="Poles")) == {"food": 150}
    knight = _entity("unit", 38)
    done = effects.Context(researched=frozenset({"782"}))
    assert _value(query.cost(knight, civilisation="Poles", context=done)) == {
        "food": 60,
        "gold": _half_up(75 * 0.4),
    }
    assert _value(
        query.cost(knight, civilisation="Poles", context=effects.Context(researched=frozenset()))
    ) == {"food": 60, "gold": 75}
    with pytest.raises(effects.ContextRequired):
        query.cost(knight, civilisation="Poles")


def test_bohemians_mining_camp_technologies_are_free_and_forge_and_university_cost_100_less() -> (
    None
):
    for tech in _MINING:
        assert _value(query.cost(_entity("technology", tech), civilisation="Bohemians")) == {
            "food": 0,
            "wood": 0,
        }
        assert (
            _value(
                query.production_time(
                    _entity("technology", tech),
                    civilisation="Bohemians",
                    context=_team("Bohemians"),
                )
            )
            == 0
        )
    assert _value(query.cost(_entity("technology", 55), civilisation="Franks")) == {
        "food": 100,
        "wood": 75,
    }
    # 150 wood becomes 50, and the University's 200 becomes 100; the Monastery is untouched.
    assert _value(query.cost(_entity("building", 103), civilisation="Bohemians")) == {"wood": 50}
    assert _value(query.cost(_entity("building", 209), civilisation="Bohemians")) == {"wood": 100}
    assert _value(query.cost(_entity("building", 104), civilisation="Bohemians")) == {"wood": 175}
    assert _value(query.cost(_entity("building", 103), civilisation="Franks")) == {"wood": 150}


def test_bohemians_chemistry_and_the_hand_cannoneer_come_in_the_castle_age() -> None:
    for kind, entity_id in (("technology", 47), ("unit", 5)):
        assert _baseline(kind, entity_id, "age_requirement") == 4
        assert (
            _value(query.age_requirement(_entity(kind, entity_id), civilisation="Bohemians")) == 3
        )
        assert _value(query.age_requirement(_entity(kind, entity_id), civilisation="Franks")) == 4


def test_bohemians_team_works_the_market_faster() -> None:
    allied = _team("Franks", "Bohemians")
    for tech in _at("technology", "84"):
        base = _baseline("technology", tech, "research_time")
        assert _value(
            query.production_time(
                _entity("technology", tech), civilisation="Franks", context=allied
            )
        ) == pytest.approx(base / 1.8)  # type: ignore[operator]
    cart = _entity("unit", 128)
    assert _value(query.production_time(cart, civilisation="Franks", context=allied)) == (
        pytest.approx(_baseline("unit", 128, "training_time") / 1.8)  # type: ignore[operator]
    )
    assert _value(query.production_time(cart, civilisation="Franks", context=_team("Franks"))) == (
        _baseline("unit", 128, "training_time")
    )


def test_hussite_reforms_is_refused_for_the_monk_and_each_monastery_technology() -> None:
    """The food that replaces the gold is stated by no source: one refusal per entity, scoped to
    the Bohemians and to the technology being researched."""
    done = effects.Context(researched=frozenset({"785"}))
    for kind, entity_id in [("unit", "125")] + [("technology", t) for t in _MONASTERY_TECHNOLOGIES]:
        _refused(
            query.cost(_entity(kind, entity_id), civilisation="Bohemians", context=done),
            "Bohemians",
        )
        assert _value(query.cost(_entity(kind, entity_id), civilisation="Franks")) == _baseline(
            kind, entity_id, "cost"
        )
    # A refusal does not wait on the research: it gaps the cost for the Bohemians with or without
    # the technology, and without any context at all.
    for context in (effects.Context(researched=frozenset()), None):
        _refused(
            query.cost(_entity("unit", 125), civilisation="Bohemians", context=context),
            "Bohemians",
        )


def test_dravidians_barracks_technologies_cost_half_and_siege_weapons_a_third_less_wood() -> None:
    for tech in _at("technology", "12"):
        base = _baseline("technology", tech, "cost")
        assert _value(
            query.cost(_entity("technology", tech), civilisation="Dravidians")
        ) == _scaled(base, 0.5, tuple(base))  # type: ignore[arg-type]
    assert _value(query.cost(_entity("technology", 215), civilisation="Dravidians")) == {"food": 50}
    assert _value(query.cost(_entity("technology", 215), civilisation="Franks")) == {"food": 100}
    siege = (*_at("unit", "49"), "331", "440")
    assert "36" in siege and "1258" in siege
    for unit in siege:
        base = _baseline("unit", unit, "cost")
        assert _value(query.cost(_entity("unit", unit), civilisation="Dravidians")) == _scaled(
            base, 0.67, ("wood",)
        )
    # Mangonel: 135 gold and 160 wood. Trebuchet: 200 wood.
    assert _value(query.cost(_entity("unit", 280), civilisation="Dravidians")) == {
        "gold": 135,
        "wood": _half_up(160 * 0.67),
    }
    assert _value(query.cost(_entity("unit", 331), civilisation="Dravidians")) == {
        "gold": 200,
        "wood": 134,
    }
    # Contrast: a Hulk is no Siege Weapon, and another civilisation pays the baseline.
    assert _value(query.cost(_entity("unit", 2626), civilisation="Dravidians")) == {
        "gold": 35,
        "wood": 75,
    }
    assert _value(query.cost(_entity("unit", 280), civilisation="Franks")) == {
        "gold": 135,
        "wood": 160,
    }


def test_bengalis_bonuses_touch_no_carried_field_so_every_bengali_row_is_a_refusal_row() -> None:
    rows = [e for e in _effects() if e.civilisation == "Bengalis"]
    assert rows
    assert all(e.modelled == "no" for e in rows)
    ratha = _entity("unit", 1759)
    assert _value(query.cost(ratha, civilisation="Bengalis")) == {"gold": 60, "wood": 60}
    assert _value(query.production_time(ratha, civilisation="Bengalis")) == 24
    assert _value(query.age_requirement(ratha, civilisation="Bengalis")) == 3


def test_gurjaras_kshatriyas_cheapens_military_units_food_and_the_rest_is_the_baseline() -> None:
    done = effects.Context(researched=frozenset({"835"}))
    none = effects.Context(researched=frozenset())
    for unit, base in ((74, {"food": 50, "gold": 20}), (1741, {"food": 65, "gold": 30})):
        assert _baseline("unit", unit, "cost") == base
        assert _value(query.cost(_entity("unit", unit), civilisation="Gurjaras", context=done)) == {
            "food": _half_up(base["food"] * 0.75),
            "gold": base["gold"],
        }
        assert (
            _value(query.cost(_entity("unit", unit), civilisation="Gurjaras", context=none)) == base
        )
    # Contrast: a Villager is not a Military Unit, and another civilisation pays the baseline.
    assert _value(query.cost(_entity("unit", 83), civilisation="Gurjaras", context=done)) == {
        "food": 50
    }
    assert _value(query.cost(_entity("unit", 74), civilisation="Franks")) == {
        "food": 50,
        "gold": 20,
    }
    with pytest.raises(effects.ContextRequired):
        query.cost(_entity("unit", 74), civilisation="Gurjaras")


def test_the_camel_and_elephant_units_of_the_gurjaras_tree_are_refused_for_the_gurjaras_only() -> (
    None
):
    members = (329, 330, 873, 875, 1744, 1746, 1751, 1753, 1755)
    for unit in members:
        _refused(
            query.production_time(
                _entity("unit", unit), civilisation="Gurjaras", context=_team("Gurjaras")
            ),
            "Gurjaras",
        )
        assert _value(
            query.production_time(
                _entity("unit", unit), civilisation="Mongols", context=_team("Mongols")
            )
        ) == _baseline("unit", unit, "training_time")
    # Contrast: a Hussar is neither, and the Gurjaras' Chakram Thrower is Infantry.
    for unit in (441, 1741):
        assert _value(
            query.production_time(
                _entity("unit", unit), civilisation="Gurjaras", context=_team("Gurjaras")
            )
        ) == _baseline("unit", unit, "training_time")


def test_romans_scorpions_cost_half_the_gold() -> None:
    for unit in (279, 542):
        base = _baseline("unit", unit, "cost")
        assert _value(query.cost(_entity("unit", unit), civilisation="Romans")) == _scaled(
            base, 0.5, ("gold",)
        )
        assert _value(query.cost(_entity("unit", unit), civilisation="Franks")) == base
    assert _value(query.cost(_entity("unit", 279), civilisation="Romans")) == {
        "gold": _half_up(75 * 0.5),
        "wood": 75,
    }
    # Contrast: a Mangonel is not a Scorpion.
    assert _value(query.cost(_entity("unit", 280), civilisation="Romans")) == {
        "gold": 135,
        "wood": 160,
    }


def test_romans_comitatenses_trains_the_militia_line_the_knights_and_the_centurions_faster() -> (
    None
):
    done = effects.Context(researched=frozenset({"884"}), team=frozenset({"Romans"}))
    none = effects.Context(researched=frozenset(), team=frozenset({"Romans"}))
    for unit in (74, 75, 77, 473, 567, 1793, 38, 283, 569, 1790, 1792):
        base = _baseline("unit", unit, "training_time")
        assert _value(
            query.production_time(_entity("unit", unit), civilisation="Romans", context=done)
        ) == pytest.approx(base / 1.5)  # type: ignore[operator]
        assert (
            _value(
                query.production_time(_entity("unit", unit), civilisation="Romans", context=none)
            )
            == base
        )
    # Contrast: a Spearman is not in the line, and another civilisation is not sped.
    assert _value(
        query.production_time(_entity("unit", 93), civilisation="Romans", context=done)
    ) == _baseline("unit", 93, "training_time")
    assert _value(
        query.production_time(
            _entity("unit", 74),
            civilisation="Franks",
            context=effects.Context(researched=frozenset({"884"}), team=frozenset({"Franks"})),
        )
    ) == _baseline("unit", 74, "training_time")
    with pytest.raises(effects.ContextRequired):
        query.production_time(_entity("unit", 74), civilisation="Romans")
    # The Legionary "replaces Two-Handed Swordsman/Champion at the Barracks" (update 83607): it
    # is in the line, so it is sped, and not refused.
    assert _value(
        query.production_time(_entity("unit", 1793), civilisation="Romans", context=done)
    ) == pytest.approx(_baseline("unit", 1793, "training_time") / 1.5)  # type: ignore[operator]


def test_armenians_mule_carts_cost_a_quarter_less() -> None:
    cart = _entity("building", 1808)
    assert _baseline("building", 1808, "cost") == {"food": 20, "wood": 80}
    assert _value(query.cost(cart, civilisation="Armenians")) == {"food": 15, "wood": 60}
    assert _value(query.cost(cart, civilisation="Franks")) == {"food": 20, "wood": 80}


def test_armenians_spearman_and_militia_line_upgrades_come_an_age_earlier_but_not_man_at_arms() -> (
    None
):
    expected = {
        ("technology", 197): 2,  # Pikeman
        ("unit", 358): 2,
        ("technology", 207): 2,  # Long Swordsman
        ("unit", 77): 2,
        ("technology", 429): 3,  # Halberdier
        ("unit", 359): 3,
        ("technology", 217): 3,  # Two-Handed Swordsman
        ("unit", 473): 3,
        ("technology", 264): 3,  # Champion
        ("unit", 567): 3,
    }
    for (kind, entity_id), earlier in expected.items():
        baseline = _baseline(kind, entity_id, "age_requirement")
        assert baseline == earlier + 1, (kind, entity_id)
        assert (
            _value(query.age_requirement(_entity(kind, entity_id), civilisation="Armenians"))
            == earlier
        )
        assert (
            _value(query.age_requirement(_entity(kind, entity_id), civilisation="Franks"))
            == baseline
        )
    # Contrast: the Man-at-Arms upgrade and unit are excepted by the bullet.
    for kind, entity_id in (("technology", 222), ("unit", 75)):
        assert _value(
            query.age_requirement(_entity(kind, entity_id), civilisation="Armenians")
        ) == _baseline(kind, entity_id, "age_requirement")


# ------------------------------------------------------------------- the owner's open rows


def test_every_refused_reason_is_a_sentence_and_no_refusal_is_silent() -> None:
    for effect in _effects():
        if effect.modelled == "no":
            assert effect.reason and len(effect.reason) > 40, (
                effect.civilisation,
                effect.source_text,
            )


def test_the_blocking_refusals_of_batch_c_are_open_owner_rows_and_the_rest_are_informational() -> (
    None
):
    """A refusal on cost, production time, age, produced-at or availability gaps a carried field.
    FR-022b enumerates the blocking gaps in the owner's sheet; a refusal whose gap is informational
    is not an open row. Batch C has eight carried-field refusals: the Vietnamese's two, the
    Burgundians' two, the Bohemians', the Gurjaras' and the Cumans' two. The Cumans' two and the
    Burgundians' age refusal gap `age_requirement` and `available_to`, which no register datum
    requires, so they are informational."""
    carried = {"cost", "production_time", "age_requirement", "produced_at", "available_to"}
    refusals = {
        (e.civilisation, e.field)
        for e in _effects()
        if e.civilisation in _BATCH_C and e.modelled == "no" and e.field in carried
    }
    assert refusals == {
        ("Vietnamese", "cost"),
        ("Vietnamese", "production_time"),
        ("Burgundians", "cost"),
        ("Burgundians", "age_requirement"),
        ("Cumans", "age_requirement"),
        ("Cumans", "available_to"),
        ("Bohemians", "cost"),
        ("Gurjaras", "production_time"),
    }
    informational = {
        ("Burgundians", "age_requirement"),
        ("Cumans", "age_requirement"),
        ("Cumans", "available_to"),
    }
    sheet = _OWNER_READINGS.read_text(encoding="utf-8")
    for civilisation, _ in refusals - informational:
        assert f"| 185872 | {civilisation} |" in sheet, civilisation
    assert "| 185872 | Cumans |" not in sheet
    # One row per entity for Hussite Reforms, as tasks.md T769 asks: the Monk and 11 technologies.
    assert sheet.count("| 185872 | Bohemians |") == 12
    assert "Hussite Reforms" in sheet
