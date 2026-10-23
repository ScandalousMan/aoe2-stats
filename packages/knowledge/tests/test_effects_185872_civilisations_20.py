"""T767: the civilisation effects of `aoe2techtree-185872-civilisations-20`, the third build 185872
snapshot, which supersedes the second and models twenty civilisations.

**Since T768 this snapshot is no longer the one the build resolves to**: the fourth,
`aoe2techtree-185872-civilisations-32`, supersedes it (`test_effects_185872_civilisations_32.py`).
This file keeps the third snapshot's own record, so every query below runs with that snapshot
pinned (`snapshot.pinned_snapshot`, SC-005): what it answered when it was current is what it still
answers.

Five kinds of claim, none of them a restatement of `test_effects.py`, `test_bullet_coverage.py` or
`test_effects_185872_civilisations.py` (which keeps the second snapshot's record, pinned):

- **Nothing is dropped.** Every bullet of the twenty civilisations' strings in the pack this
  snapshot is derived from, `aoe2techtree-3bb43b1`, is an `[[effect]]` row's `source_text` or is in
  one of two closed registries below, each entry a real bullet. Set difference and exact count, so a
  failure names the bullet. The registries name bullets that cannot be a row: a class of unit the
  pack does not enumerate on a field this knowledge base does not carry (`effects.Effect` requires a
  non-empty explicit selector).
- **Nothing dangles.** Every row's `source_key` and `source_text` are the pack's own, every selector
  entry exists in this snapshot's `rules.json`, every researched condition names a technology of it,
  and the `[[civilisation_id]]` table names every civilisation of the pack once.
- **The eight civilisations of T746 are carried.** A row of the second snapshot is read from the
  same strings of the same pack revision (same build), so it is carried unchanged: every row of the
  second snapshot is in this one, parsed key for key, except the four sources T767 took again
  (FR-022c: Kamandaran, Detinets, the Fortifications bonus and the Donjon bullet, each below).
- **The values come out as the strings say**, one case per kind of row, each with the contrast case
  that must not apply, every expectation derived from the pack's own baseline and the bullet's
  arithmetic and not read back from the file under test.
- **What is refused is refused for a stated reason**, and the reason is checked against the
  owner's sheet (`specs/006-replay-analysis-foundations/owner-readings.md`).
"""

from __future__ import annotations

import json
import math
import tomllib
from collections.abc import Iterator, Mapping
from importlib import resources

import pytest

from aoe2stats_knowledge import effects, gaps, query, snapshot

_PACKAGE = "aoe2stats_knowledge"
_PACK = "aoe2techtree-3bb43b1"
_DIRECTORY = "aoe2techtree-185872-civilisations-20"
_SECOND_DIRECTORY = "aoe2techtree-185872-civilisations"
_BUILD = 185872

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
}

#: Bullets with no row: a class the pack does not enumerate, on a field this knowledge base does
#: not carry. Each is reviewed against the header comment of `effects.toml`, which lists the same.
_NO_SELECTOR_BULLETS: Mapping[str, tuple[str, ...]] = {
    "Franks": ("Foragers work +15% faster", "Mounted Units +20% HP starting in Feudal Age"),
    "Teutons": (
        "Infantry and Mounted Units +1/+2 melee armor in Castle/Imperial Age",
        "Ironclad (Siege Weapons +4 melee armor)",
        "Team Bonus: Units more resistant to conversion",
    ),
    "Persians": ("Start with +50 wood and +50 food",),
    "Saracens": (
        "Camel Units +25% HP",
        "Team Bonus: Foot Archers and Skirmishers +2 attack vs. buildings",
    ),
    "Malians": ("Farimba (Cavalry +5 attack)",),
    "Tatars": (
        "Livestock animals last +50% longer",
        "Units deal +25% damage when fighting from higher elevation",
        "Team Bonus: Mounted Archers +2 line of sight",
    ),
    "Slavs": (
        "Farmers work +15% faster",
        "Druzhina (Infantry deals trample damage)",
        "Team Bonus: Military buildings (except Castles) provide +5 population space",
    ),
    "Sicilians": (
        "Start with +100 stone",
        "Farm upgrades provide +125% additional food",
        "Soldiers receive -40% bonus damage",
    ),
    "Britons": (
        "Shepherds work +25% faster",
        "Foot Archers +1/+2 range in Castle/Imperial Age",
    ),
    "Goths": (
        "Hunters carry +15; hunted animals last +20% longer",
        "Infantry +1/+2/+3 attack vs. buildings in Feudal/Castle/Imperial Age",
        "+10 population space in Imperial Age",
    ),
    "Japanese": ("Infantry attacks +33% faster starting in Feudal Age",),
    "Chinese": ("Start with +3 Villagers, but -50 wood and -200 food",),
    "Byzantines": ("Buildings +10/20/30/40% HP in Dark/Feudal/Castle/Imperial Age",),
    "Turks": (
        "Gold miners work +25% faster",
        "Gunpowder Units +25% HP",
        "Sipahi (Mounted Archers +20 HP)",
    ),
    "Vikings": (
        "Infantry +20% HP starting in Feudal Age",
        "Chieftains (Infantry +5 attack vs. Cavalry, +4 vs. Camel Units)",
    ),
    "Mongols": (
        "Hunters work +40% faster",
        "Nomads (Lost Houses do not decrease population space)",
    ),
    "Celts": (
        "Lumberjacks work +15% faster",
        "Livestock animals within Celt unit line of sight cannot be stolen",
        "Infantry moves +5/10/15/20% faster in Dark/Feudal/Castle/Imperial Age",
        "Siege Weapons attack +25% faster",
        "Furor Celtica (Siege Weapons +40% HP)",
    ),
    "Spanish": (
        "Builders work +30% faster",
        "Receive +20 gold for each technology researched",
        "Gunpowder Units attack +18% faster",
    ),
    "Aztecs": (
        "Start with +50 gold",
        "Garland Wars (Infantry +4 attack)",
        "Team Bonus: Relics generate +33% gold",
    ),
    "Mayans": (
        "Start with +1 Villager, but -50 food",
        "Resources last +15% longer",
    ),
}

#: A real entity whose baseline already answers the bullet, so a row would assert nothing.
_ENTITY_REPRESENTED_BUT_NEEDS_NO_EFFECT_ROW: Mapping[str, tuple[str, ...]] = {
    "Persians": ("Can build Caravanserai in Imperial Age",),
}

#: The four sources T767 took again and so changed from the second snapshot's rows (FR-022c).
_RETAKEN_SOURCES: frozenset[tuple[str, str]] = frozenset(
    {
        ("Persians", "Kamandaran (Archer-line gold cost replaced by additional wood cost)"),
        (
            "Sicilians",
            "Fortifications built +50% faster; Town Centers built +100% faster",
        ),
        ("Sicilians", "Can build Donjon in Dark Age, replaces Watch Tower-line"),
    }
)


@pytest.fixture(autouse=True)
def _pin_the_third_snapshot() -> Iterator[None]:
    """The build resolves to a newer snapshot now; this file is about the third, found by its
    directory, which is a label and so only ever used to find the identity to pin."""
    (third,) = (s for s in snapshot.load_all_snapshots() if s.directory == _DIRECTORY)
    with snapshot.pinned_snapshot(third):
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


# ------------------------------------------------------------------------------ nothing is dropped


def test_every_registry_entry_is_a_real_bullet_of_the_second_pack() -> None:
    for civilisation, help_string_id in _HELP_STRING_ID.items():
        bullets = _bullets_for(help_string_id)
        registered = _NO_SELECTOR_BULLETS[
            civilisation
        ] + _ENTITY_REPRESENTED_BUT_NEEDS_NO_EFFECT_ROW.get(civilisation, ())
        for entry in registered:
            assert entry in bullets, (
                f"{civilisation}: {entry!r} is not a bullet of {help_string_id}"
            )


def test_every_bullet_is_a_row_or_a_registry_entry_exactly_once() -> None:
    for civilisation, help_string_id in _HELP_STRING_ID.items():
        bullets = _bullets_for(help_string_id)
        row_texts = {e.source_text for e in _effects() if e.civilisation == civilisation}
        registered = set(_NO_SELECTOR_BULLETS[civilisation]) | set(
            _ENTITY_REPRESENTED_BUT_NEEDS_NO_EFFECT_ROW.get(civilisation, ())
        )
        assert not row_texts & registered, f"{civilisation}: both a row and a registry entry"
        assert set(bullets) - (row_texts | registered) == set(), f"{civilisation}: dropped"
        assert (row_texts | registered) - set(bullets) == set(), f"{civilisation}: invented"
        assert len(row_texts | registered) == len(bullets)


def test_the_bullets_of_the_twenty_civilisations_number_one_hundred_and_forty() -> None:
    """A guard on the reader: a changed pack string that silently shifted the count would move
    every assertion above together. The eight of T746 are 57; the twelve of batch A are 83."""
    assert sum(len(_bullets_for(key)) for key in _HELP_STRING_ID.values()) == 140


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
        if effect.condition == "researched":
            assert effect.condition_technology in rules["technology"], effect.source_text
        if effect.condition == "controlled":  # pragma: no cover - none in batch A
            for entry in effect.condition_entities or ():
                assert entry.id in rules[entry.kind]


def test_a_researched_condition_is_the_technology_the_bullet_names() -> None:
    technologies = _rules()["technology"]
    conditional = {
        (e.civilisation, e.condition_technology, e.field)
        for e in _effects()
        if e.condition == "researched"
    }
    assert conditional == {
        ("Franks", "1496", "cost"),
        ("Franks", "493", "production_time"),
        ("Persians", "488", "cost"),
        ("Slavs", "455", "cost"),
        ("Goths", "16", "produced_at"),
        ("Goths", "457", "production_time"),
    }
    names = {tech: technologies[tech]["name"] for _, tech, _ in conditional}
    assert names["16"] == "Anarchy"
    assert names["457"] == "Perfusion"
    assert names["488"] == "Kamandaran"
    assert names["455"] == "Detinets"


def test_civilisations_modelled_is_the_set_the_effects_name() -> None:
    text = _snapshot_root().joinpath("snapshot.toml").read_text(encoding="utf-8")
    modelled = tomllib.loads(text)["snapshot"]["civilisations_modelled"]
    assert sorted(modelled) == sorted(_HELP_STRING_ID)
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
    assert current.normaliser_version == 2
    assert current.validation is not None
    assert current.validation.performed_at == "2026-10-22"
    assert current.validation.details["not_checked"].strip()
    assert current.validation.details["release_notes"]["url"].endswith("-update-185872/")


# ------------------------------------------------------------ the eight are carried unchanged


def _row_key(effect: effects.Effect) -> tuple[str, str, str, tuple[tuple[str, str], ...]]:
    return (
        effect.civilisation,
        effect.source_text,
        effect.field,
        tuple((entry.kind, entry.id) for entry in effect.selector),
    )


def test_every_row_of_the_second_snapshot_is_carried_unchanged_except_the_retaken_sources() -> None:
    """Same build, same pack revision, same strings: a row is carried, not re-derived (Phase 8's
    transcription rule). Compared as parsed rows, every field including `validated_by`."""
    new_by_key = {_row_key(e): e for e in _effects()}
    for old in _effects(_SECOND_DIRECTORY):
        if (old.civilisation, old.source_text) in _RETAKEN_SOURCES:
            continue
        assert _row_key(old) in new_by_key, ("not carried", old.civilisation, old.source_text)
        assert new_by_key[_row_key(old)] == old, ("changed", old.civilisation, old.source_text)


def test_the_retaken_sources_are_the_only_rows_that_differ() -> None:
    old_keys = {_row_key(e) for e in _effects(_SECOND_DIRECTORY)}
    changed = {
        (e.civilisation, e.source_text)
        for e in _effects()
        if _row_key(e) not in old_keys and e.civilisation in _carried_civilisations()
    }
    assert changed <= _RETAKEN_SOURCES


def _carried_civilisations() -> frozenset[str]:
    return frozenset(e.civilisation for e in _effects(_SECOND_DIRECTORY))


def test_the_raw_ids_of_the_eight_carried_civilisations_are_unchanged() -> None:
    old = effects.civilisation_id_names(_SECOND_DIRECTORY)
    new = effects.civilisation_id_names(_DIRECTORY)
    assert {raw_id: new[raw_id] for raw_id in old} == dict(old)


# --------------------------------------------------------------------------------- the values


def _entity(kind: str, entity_id: int) -> query.EntityRef:
    return query.EntityRef(kind=kind, id=str(entity_id), build=_BUILD)


def _value(result: object) -> object:
    assert not isinstance(result, gaps.KnowledgeGap), f"gap: {result!r}"
    return result.value  # type: ignore[attr-defined]


def _baseline(kind: str, entity_id: int, key: str) -> object:
    return _rules()[kind][str(entity_id)][key]


def _refused(result: object, civilisation: str) -> None:
    assert isinstance(result, gaps.KnowledgeGap), f"expected a refusal, got {result!r}"
    assert result.cause == "effect-not-modelled"
    assert result.civilisation == civilisation
    assert result.detail


def test_britons_town_centers_cost_half_the_wood_from_the_castle_age() -> None:
    base = {"stone": 100, "wood": 275}
    assert _baseline("building", 109, "cost") == base
    assert _value(
        query.cost(_entity("building", 109), civilisation="Britons", context=effects.Context(age=3))
    ) == {
        "stone": 100,
        "wood": _half_up(275 * 0.5),
    }
    assert _value(
        query.cost(_entity("building", 109), civilisation="Britons", context=effects.Context(age=4))
    ) == {
        "stone": 100,
        "wood": 138,
    }
    # Contrast: before the Castle Age, and for another civilisation, the plain baseline.
    assert (
        _value(
            query.cost(
                _entity("building", 109), civilisation="Britons", context=effects.Context(age=2)
            )
        )
        == base
    )
    assert _value(query.cost(_entity("building", 109), civilisation="Franks")) == base
    with pytest.raises(effects.ContextRequired):
        query.cost(_entity("building", 109), civilisation="Britons")


def test_a_team_work_speed_bonus_reaches_the_owners_allies_and_not_their_opponents() -> None:
    """Britons' Archery Ranges (+10%), Goths' Barracks (+20%) and Celts' Siege Workshops (+20%)."""
    crossbowman, militia, ram = _entity("unit", 24), _entity("unit", 74), _entity("unit", 1258)
    assert _baseline("unit", 24, "training_time") == 27
    allied = effects.Context(team=frozenset({"Franks", "Britons"}))
    alone = effects.Context(team=frozenset({"Franks"}))
    assert _value(
        query.production_time(crossbowman, civilisation="Franks", context=allied)
    ) == pytest.approx(27 / 1.1)
    assert _value(
        query.production_time(crossbowman, civilisation="Britons", context=allied)
    ) == pytest.approx(27 / 1.1)
    assert _value(query.production_time(crossbowman, civilisation="Franks", context=alone)) == 27
    goths = effects.Context(team=frozenset({"Goths", "Teutons"}))
    assert _value(
        query.production_time(militia, civilisation="Teutons", context=goths)
    ) == pytest.approx(21 / 1.2)
    celts = effects.Context(team=frozenset({"Celts", "Franks"}))
    assert _value(
        query.production_time(ram, civilisation="Franks", context=celts)
    ) == pytest.approx(36 / 1.2)
    with pytest.raises(effects.ContextRequired):
        query.production_time(crossbowman, civilisation="Franks")


def test_goths_loom_is_instant_and_their_infantry_cost_less_by_age() -> None:
    assert _value(query.production_time(_entity("technology", 22), civilisation="Goths")) == 0
    assert _value(query.production_time(_entity("technology", 22), civilisation="Franks")) == 25
    militia = _entity("unit", 74)
    for age, factor in ((1, 0.85), (2, 0.80), (3, 0.75), (4, 0.70)):
        assert _value(
            query.cost(militia, civilisation="Goths", context=effects.Context(age=age))
        ) == {"food": _half_up(50 * factor), "gold": _half_up(20 * factor)}
    # Contrast: a unit the pack does not call Infantry, and another civilisation.
    archer = _entity("unit", 4)
    assert _value(query.cost(archer, civilisation="Goths")) == {"gold": 45, "wood": 25}
    assert _value(query.cost(militia, civilisation="Franks")) == {"food": 50, "gold": 20}


def test_goths_anarchy_adds_the_barracks_to_the_huskarls_and_perfusion_speeds_it() -> None:
    huskarl = _entity("unit", 41)
    with pytest.raises(effects.ContextRequired):
        query.produced_at(huskarl, civilisation="Goths")
    before = query.produced_at(
        huskarl, civilisation="Goths", context=effects.Context(researched=frozenset())
    )
    after = query.produced_at(
        huskarl, civilisation="Goths", context=effects.Context(researched=frozenset({"16"}))
    )
    assert [ref.id for ref in _value(before)] == ["82"]  # type: ignore[attr-defined]
    assert [ref.id for ref in _value(after)] == ["82", "12"]  # type: ignore[attr-defined]
    # Contrast: no other civilisation gains the Barracks.
    assert [ref.id for ref in _value(query.produced_at(huskarl, civilisation="Franks"))] == ["82"]  # type: ignore[attr-defined]
    militia = _entity("unit", 74)
    team = frozenset({"Goths"})
    plain = effects.Context(team=team, researched=frozenset())
    perfused = effects.Context(team=team, researched=frozenset({"457"}))
    assert _value(
        query.production_time(militia, civilisation="Goths", context=plain)
    ) == pytest.approx(21 / 1.2)
    assert _value(
        query.production_time(militia, civilisation="Goths", context=perfused)
    ) == pytest.approx(21 / 2.0 / 1.2)


def test_japanese_economic_buildings_cost_half() -> None:
    for building, base_wood in ((68, 100), (562, 100), (584, 100)):
        assert _baseline("building", building, "cost") == {"wood": base_wood}
        assert _value(query.cost(_entity("building", building), civilisation="Japanese")) == {
            "wood": 50
        }
        assert _value(query.cost(_entity("building", building), civilisation="Franks")) == {
            "wood": base_wood
        }


def test_chinese_technologies_cost_less_by_age_but_the_age_advances_are_refused() -> None:
    forging = _entity("technology", 67)
    assert _baseline("technology", 67, "cost") == {"food": 150}
    for age, factor in ((2, 0.95), (3, 0.90), (4, 0.85)):
        assert _value(
            query.cost(forging, civilisation="Chinese", context=effects.Context(age=age))
        ) == {"food": _half_up(150 * factor)}
    assert _value(query.cost(forging, civilisation="Chinese", context=effects.Context(age=1))) == {
        "food": 150
    }
    # The Feudal Age is researched in the Dark Age, where the table has no entry: baseline.
    assert _value(
        query.cost(
            _entity("technology", 101), civilisation="Chinese", context=effects.Context(age=1)
        )
    ) == {"food": 500}
    # The Castle and Imperial Age advances: whether the discount reaches them is not stated.
    for age_up in (102, 103):
        _refused(query.cost(_entity("technology", age_up), civilisation="Chinese"), "Chinese")
    # Contrast: another civilisation pays the baseline for the same technology.
    assert _value(query.cost(_entity("technology", 102), civilisation="Franks")) == _baseline(
        "technology", 102, "cost"
    )


def test_byzantine_discounts_and_free_technologies() -> None:
    assert _value(query.cost(_entity("unit", 329), civilisation="Byzantines")) == {
        "food": _half_up(55 * 0.75),
        "gold": _half_up(60 * 0.75),
    }
    assert _value(query.cost(_entity("unit", 7), civilisation="Byzantines")) == {
        "food": _half_up(25 * 0.75),
        "wood": _half_up(35 * 0.75),
    }
    assert _value(query.cost(_entity("unit", 93), civilisation="Byzantines")) == {
        "food": _half_up(35 * 0.75),
        "wood": _half_up(25 * 0.75),
    }
    assert _value(query.cost(_entity("unit", 329), civilisation="Franks")) == {
        "food": 55,
        "gold": 60,
    }
    for tech in (8, 280):
        assert (
            _value(query.production_time(_entity("technology", tech), civilisation="Byzantines"))
            == 0
        )
    assert _value(query.cost(_entity("technology", 8), civilisation="Byzantines")) == {"food": 0}
    assert _value(query.cost(_entity("technology", 103), civilisation="Byzantines")) == {
        "food": _half_up(1000 * 0.67),
        "gold": _half_up(800 * 0.67),
    }
    assert _value(query.cost(_entity("technology", 103), civilisation="Franks")) == {
        "food": 1000,
        "gold": 800,
    }


def test_turks_chemistry_and_the_scout_cavalry_upgrades_are_free() -> None:
    # A University technology also meets Malians' team row, which needs the team to decide.
    alone = effects.Context(team=frozenset({"Turks"}))
    for tech in (47, 254, 428):
        cost = _value(query.cost(_entity("technology", tech), civilisation="Turks"))
        assert set(cost.values()) == {0}  # type: ignore[attr-defined]
        assert (
            _value(
                query.production_time(
                    _entity("technology", tech), civilisation="Turks", context=alone
                )
            )
            == 0
        )
    assert _value(query.cost(_entity("technology", 47), civilisation="Franks")) == {
        "food": 300,
        "gold": 200,
    }


def test_a_gunpowder_team_bonus_speeds_the_units_the_pack_calls_gunpowder_units() -> None:
    cannoneer = _entity("unit", 5)
    allied = effects.Context(team=frozenset({"Franks", "Turks"}))
    assert _value(
        query.production_time(cannoneer, civilisation="Franks", context=allied)
    ) == pytest.approx(34 / 1.25)
    assert (
        _value(
            query.production_time(
                cannoneer,
                civilisation="Franks",
                context=effects.Context(team=frozenset({"Franks"})),
            )
        )
        == 34
    )


def test_the_gunner_units_and_the_candidate_gunpowder_technologies_are_refused_for_the_turks() -> (
    None
):
    """The pack calls the Janissary a Foot Gunner and says only Hand Cannoneer, Cannon Galleon,
    Bombard Cannon and Bombard Tower are Gunpowder Units by name; it never says the Janissary is
    one. Nor does it say which technologies "Gunpowder technologies" names."""
    for unit in (46, 557):
        _refused(query.production_time(_entity("unit", unit), civilisation="Turks"), "Turks")
    for tech in (10, 64, 369, 376):
        _refused(query.cost(_entity("technology", tech), civilisation="Turks"), "Turks")
    # Contrast: another civilisation's Janissary-less queries are not refused by this row.
    assert _value(query.cost(_entity("technology", 64), civilisation="Franks")) == _baseline(
        "technology", 64, "cost"
    )


def test_vikings_warships_cost_less_by_age_and_their_docks_are_cheaper_for_the_team() -> None:
    longship = _entity("unit", 250)
    assert _baseline("unit", 250, "cost") == {"gold": 50, "wood": 100}
    for age, factor in ((2, 0.90), (3, 0.85), (4, 0.80)):
        assert _value(
            query.cost(longship, civilisation="Vikings", context=effects.Context(age=age))
        ) == {
            "gold": _half_up(50 * factor),
            "wood": _half_up(100 * factor),
        }
    # A transport ship is not a Warship in the pack's words.
    vikings_alone = effects.Context(team=frozenset({"Vikings"}))
    assert _value(
        query.cost(_entity("unit", 545), civilisation="Vikings", context=vikings_alone)
    ) == {"wood": 125}
    dock = _entity("building", 45)
    assert _value(
        query.cost(
            dock,
            civilisation="Franks",
            context=effects.Context(team=frozenset({"Franks", "Vikings"})),
        )
    ) == {"wood": _half_up(150 * 0.85)}
    assert _value(
        query.cost(dock, civilisation="Franks", context=effects.Context(team=frozenset({"Franks"})))
    ) == {"wood": 150}
    for tech in (213, 249):
        assert (
            _value(query.production_time(_entity("technology", tech), civilisation="Vikings")) == 0
        )
        assert set(
            _value(query.cost(_entity("technology", tech), civilisation="Vikings")).values()
        ) == {0}  # type: ignore[attr-defined]


def test_spanish_blacksmith_upgrades_cost_no_gold() -> None:
    iron_casting = _entity("technology", 68)
    assert _baseline("technology", 68, "cost") == {"food": 220, "gold": 120}
    assert _value(query.cost(iron_casting, civilisation="Spanish")) == {"food": 220, "gold": 0}
    assert _value(query.cost(_entity("technology", 67), civilisation="Spanish")) == {"food": 150}
    assert _value(query.cost(iron_casting, civilisation="Franks")) == {"food": 220, "gold": 120}


def test_mayan_foot_archers_cost_less_by_age_and_their_walls_are_cheaper_for_the_team() -> None:
    archer = _entity("unit", 4)
    for age, factor in ((2, 0.90), (3, 0.80), (4, 0.70)):
        assert _value(
            query.cost(archer, civilisation="Mayans", context=effects.Context(age=age))
        ) == {
            "gold": _half_up(45 * factor),
            "wood": _half_up(25 * factor),
        }
    assert _value(query.cost(archer, civilisation="Mayans", context=effects.Context(age=1))) == {
        "gold": 45,
        "wood": 25,
    }
    wall = _entity("building", 117)
    assert _value(
        query.cost(wall, civilisation="Mayans", context=effects.Context(team=frozenset({"Mayans"})))
    ) == {"stone": _half_up(5 * 0.5)}
    assert _value(
        query.cost(
            _entity("building", 72),
            civilisation="Franks",
            context=effects.Context(team=frozenset({"Franks", "Mayans"})),
        )
    ) == {"wood": _half_up(3 * 0.5)}


def test_aztec_military_units_train_faster_but_the_ships_and_monks_are_refused() -> None:
    assert _baseline("unit", 74, "training_time") == 21
    team = effects.Context(team=frozenset({"Aztecs"}))
    assert _value(
        query.production_time(_entity("unit", 74), civilisation="Aztecs", context=team)
    ) == pytest.approx(21 / 1.15)
    assert _value(
        query.production_time(_entity("unit", 279), civilisation="Aztecs", context=team)
    ) == pytest.approx(30 / 1.15)
    # The Villager is not a Military Unit in any reading.
    assert (
        _value(query.production_time(_entity("unit", 83), civilisation="Aztecs", context=team))
        == 25
    )
    # Whether ships and Monks are Military Units the pack does not say.
    for unit in (21, 539, 125):
        _refused(query.production_time(_entity("unit", unit), civilisation="Aztecs"), "Aztecs")


def test_a_civilisation_whose_bonuses_touch_no_carried_field_answers_the_baseline() -> None:
    """Mongols have no bonus on cost, time, age or production site: every bullet is on a field this
    knowledge base does not carry, so a Knight is the baseline and no query is refused."""
    knight = _entity("unit", 38)
    assert _value(query.cost(knight, civilisation="Mongols")) == {"food": 60, "gold": 75}
    assert _value(query.production_time(knight, civilisation="Mongols")) == 30


# ------------------------------------------------------------- the four sources taken again


def test_kamandaran_replaces_the_archer_lines_gold_with_a_wood_cost_the_publisher_states() -> None:
    """Update 34699: "Increased the cost of Archer units after researching the Kamandaran
    technology from 50 to 60 wood"; update 162286: "Kamandaran. Effect improved from Archer-line
    costs 60 wood -> 50 wood". Read as the cost the line has once researched: 50 wood, no gold."""
    researched = effects.Context(researched=frozenset({"488"}))
    unresearched = effects.Context(researched=frozenset())
    for archer in (4, 24, 492):
        assert _value(
            query.cost(_entity("unit", archer), civilisation="Persians", context=researched)
        ) == {
            "gold": 0,
            "wood": 50,
        }
        assert _value(
            query.cost(_entity("unit", archer), civilisation="Persians", context=unresearched)
        ) == {
            "gold": 45,
            "wood": 25,
        }
        with pytest.raises(effects.ContextRequired):
            query.cost(_entity("unit", archer), civilisation="Persians")
    assert _value(query.cost(_entity("unit", 4), civilisation="Franks")) == {"gold": 45, "wood": 25}


def test_detinets_stays_refused_because_no_source_states_the_wood() -> None:
    """Update 61321 repeats the pack's sentence ("Replaces 40% of Castles' and Towers' stone cost
    with wood") and no later note changes or sizes it."""
    for building in (79, 82, 234, 235):
        _refused(query.cost(_entity("building", building), civilisation="Slavs"), "Slavs")
    assert _value(query.cost(_entity("building", 82), civilisation="Saracens")) == {
        "stone": 650,
        "wood": 0,
    }


def test_the_donjon_and_the_castle_are_built_half_again_as_fast_by_the_sicilians() -> None:
    """Update 111772: "Donjon base construction time increased from 90 seconds -> 125 seconds
    (83 seconds after civilization bonus)"; update 81058 names the Castle at 50%."""
    assert _baseline("building", 1665, "construction_time") == 125
    assert _value(
        query.production_time(_entity("building", 1665), civilisation="Sicilians")
    ) == pytest.approx(125 / 1.5)
    assert (
        round(_value(query.production_time(_entity("building", 1665), civilisation="Sicilians")))
        == 83
    )  # type: ignore[arg-type]
    assert _value(
        query.production_time(_entity("building", 82), civilisation="Sicilians")
    ) == pytest.approx(200 / 1.5)
    assert _value(query.production_time(_entity("building", 1665), civilisation="Franks")) == 125
    assert _value(query.production_time(_entity("building", 82), civilisation="Franks")) == 200


def test_the_fortifications_the_notes_never_name_are_still_refused_for_the_sicilians() -> None:
    for building in (79, 234, 235, 236, 1251):
        _refused(
            query.production_time(_entity("building", building), civilisation="Sicilians"),
            "Sicilians",
        )
    assert _value(
        query.production_time(_entity("building", 236), civilisation="Franks")
    ) == _baseline("building", 236, "construction_time")


def test_the_donjon_replaces_the_watch_tower_line_for_the_sicilians() -> None:
    """The bullet is a row now (T763): the line's availability is set false, the Donjon's true."""
    for tower in (79, 234, 235):
        assert (
            _value(query.available_to(_entity("building", tower), civilisation="Sicilians"))
            is False
        )
    assert _value(query.available_to(_entity("building", 79), civilisation="Franks")) is True
    assert _value(query.available_to(_entity("building", 1665), civilisation="Sicilians")) is True
    assert _value(query.available_to(_entity("building", 1665), civilisation="Franks")) is False
    donjon_rows = [e for e in _effects() if e.source_text.startswith("Can build Donjon")]
    assert {(e.field, e.operand) for e in donjon_rows} == {
        ("available_to", False),
        ("available_to", True),
    }
    assert all(e.modelled == "yes" for e in donjon_rows)


# ------------------------------------------------------------------- the owner's open rows


def test_every_refused_reason_is_a_sentence_and_no_refusal_is_silent() -> None:
    for effect in _effects():
        if effect.modelled == "no":
            assert effect.reason and len(effect.reason) > 40, (
                effect.civilisation,
                effect.source_text,
            )
