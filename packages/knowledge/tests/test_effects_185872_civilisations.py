"""T746: the civilisation effects of `aoe2techtree-185872-civilisations`, the second build 185872
snapshot, which supersedes the first and models eight civilisations.

Three kinds of claim, none of them a restatement of `test_effects.py` or `test_bullet_coverage.py`
(which are about the build 180059 snapshot and the first pack):

- **Nothing is dropped.** Every bullet of the eight civilisations' strings in the pack this
  snapshot is derived from, `aoe2techtree-3bb43b1`, is an `[[effect]]` row's `source_text` or is in
  one of two closed registries below, each entry a real bullet. Set difference and exact count, as
  the older file does, so a failure names the bullet.
- **Nothing dangles.** Every row's `source_key` and `source_text` are the pack's own, every selector
  entry exists in this snapshot's `rules.json`, every `[[civilisation_id]]` names a modelled
  civilisation and each modelled civilisation has exactly one, and raw ids 5, 10, 49 and 51 (out of
  scope) are named by nothing.
- **The values come out as the strings say**, one case per kind of row (unconditional, age,
  researched, team, free technology, refusal), each with the contrast case that must not apply.

The registries name bullets that cannot be a row: a class of unit the pack does not enumerate on a
field this knowledge base does not carry (`effects.Effect` requires a non-empty explicit selector).
"""

from __future__ import annotations

import json
import tomllib
from collections.abc import Mapping
from importlib import resources

import pytest

from aoe2stats_knowledge import effects, gaps, query, snapshot

_PACKAGE = "aoe2stats_knowledge"
_PACK = "aoe2techtree-3bb43b1"
_DIRECTORY = "aoe2techtree-185872-civilisations"
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
}

#: Raw replay civilisation ids this snapshot names (`[[civilisation_id]]`).
_RAW_IDS: Mapping[int, str] = {
    2: "Franks",
    4: "Teutons",
    8: "Persians",
    9: "Saracens",
    23: "Slavs",
    26: "Malians",
    33: "Tatars",
    37: "Sicilians",
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
}

#: A real entity whose baseline already answers the bullet, so a row would assert nothing.
_ENTITY_REPRESENTED_BUT_NEEDS_NO_EFFECT_ROW: Mapping[str, tuple[str, ...]] = {
    "Persians": ("Can build Caravanserai in Imperial Age",),
}


def _pack_root() -> resources.abc.Traversable:
    return resources.files(_PACKAGE).joinpath("packs").joinpath(_PACK)


def _snapshot_root() -> resources.abc.Traversable:
    return resources.files(_PACKAGE).joinpath("snapshots").joinpath(_DIRECTORY)


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


def _effects() -> tuple[effects.Effect, ...]:
    return effects._effects(_DIRECTORY)


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


def test_the_bullets_of_the_eight_civilisations_number_fifty_seven() -> None:
    """A guard on the reader: a changed pack string that silently shifted the count would move
    every assertion above together."""
    assert sum(len(_bullets_for(key)) for key in _HELP_STRING_ID.values()) == 57


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


def test_a_researched_condition_names_a_technology_of_this_snapshot() -> None:
    technologies = _rules()["technology"]
    conditional = [e for e in _effects() if e.condition == "researched"]
    assert {(e.civilisation, e.condition_technology) for e in conditional} == {
        ("Franks", "1496"),
        ("Franks", "493"),
        ("Persians", "488"),
        ("Slavs", "455"),
    }
    for effect in conditional:
        assert effect.condition_technology in technologies


def test_the_raw_id_table_names_exactly_the_eight_scoped_civilisations() -> None:
    names = effects.civilisation_id_names(_DIRECTORY)
    assert dict(names) == _RAW_IDS
    for out_of_scope in (5, 10, 49, 51):
        assert out_of_scope not in names


def test_civilisations_modelled_is_the_set_the_effects_and_the_id_table_name() -> None:
    text = _snapshot_root().joinpath("snapshot.toml").read_text(encoding="utf-8")
    modelled = tomllib.loads(text)["snapshot"]["civilisations_modelled"]
    assert sorted(modelled) == sorted(_RAW_IDS.values())
    assert {e.civilisation for e in _effects()} == set(modelled)


def test_the_validation_record_says_what_was_and_was_not_checked() -> None:
    current = snapshot.snapshot_for(_BUILD)
    assert isinstance(current, snapshot.Snapshot)
    assert current.directory == _DIRECTORY
    assert current.validation is not None
    assert current.validation.performed_at == "2026-10-18"
    assert current.validation.details["not_checked"].strip()
    assert current.validation.details["release_notes"]["url"].endswith("-update-185872/")


# --------------------------------------------------------------------------------- the values


def _entity(kind: str, entity_id: int) -> query.EntityRef:
    return query.EntityRef(kind=kind, id=str(entity_id), build=_BUILD)


def _value(result: object) -> object:
    assert not isinstance(result, gaps.KnowledgeGap), f"gap: {result!r}"
    return result.value  # type: ignore[attr-defined]


def test_an_unconditional_discount_applies_to_its_owner_and_to_nobody_else() -> None:
    assert _value(query.cost(_entity("building", 84), civilisation="Saracens")) == {"wood": 75}
    assert _value(query.cost(_entity("building", 50), civilisation="Teutons")) == {"wood": 36}
    assert _value(query.cost(_entity("building", 70), civilisation="Malians")) == {"wood": 21}
    # Contrast: the same entity for a civilisation without the bonus is the baseline.
    assert _value(query.cost(_entity("building", 84), civilisation="Franks")) == {"wood": 175}
    assert _value(query.cost(_entity("building", 50), civilisation="Slavs")) == {"wood": 60}


def test_siege_workshop_units_are_cheaper_for_the_slavs_only() -> None:
    assert _value(query.cost(_entity("unit", 1258), civilisation="Slavs")) == {
        "gold": 64,
        "wood": 136,
    }
    assert _value(query.cost(_entity("unit", 1258), civilisation="Franks")) == {
        "gold": 75,
        "wood": 160,
    }


def test_a_free_technology_costs_nothing_and_takes_no_time() -> None:
    for civilisation, technology, cost in (
        ("Slavs", 602, {"food": 0, "gold": 0}),
        ("Tatars", 437, {"food": 0, "wood": 0}),
        ("Franks", 14, {"food": 0, "wood": 0}),
        ("Teutons", 322, {"food": 0, "stone": 0}),
    ):
        assert (
            _value(query.cost(_entity("technology", technology), civilisation=civilisation)) == cost
        )
        # A University technology also meets Malians' team row, which needs the team to decide.
        alone = effects.Context(team=frozenset({civilisation}))
        assert (
            _value(
                query.production_time(
                    _entity("technology", technology), civilisation=civilisation, context=alone
                )
            )
            == 0
        )
    # Contrast: a civilisation without the bonus pays the baseline.
    assert _value(query.cost(_entity("technology", 602), civilisation="Franks")) != {
        "food": 0,
        "gold": 0,
    }


def test_a_set_age_requirement_moves_for_the_persians_alone() -> None:
    assert _value(query.age_requirement(_entity("technology", 436), civilisation="Persians")) == 3
    assert _value(query.age_requirement(_entity("technology", 436), civilisation="Tatars")) == 4


def test_an_age_conditional_effect_needs_the_age_and_applies_only_in_its_ages() -> None:
    castle = _entity("building", 82)
    with pytest.raises(effects.ContextRequired):
        query.cost(castle, civilisation="Franks")
    assert _value(query.cost(castle, civilisation="Franks", context=effects.Context(age=3))) == {
        "stone": 553,
        "wood": 0,
    }
    assert _value(query.cost(castle, civilisation="Franks", context=effects.Context(age=2))) == {
        "stone": 650,
        "wood": 0,
    }
    villager_dark = query.production_time(
        _entity("unit", 83), civilisation="Persians", context=effects.Context(age=1)
    )
    assert _value(villager_dark) == pytest.approx(25 / 1.05)


def test_a_researched_conditional_effect_applies_once_the_technology_is_researched() -> None:
    crossbowman = _entity("unit", 2700)
    researched = effects.Context(researched=frozenset({"1496"}))
    assert _value(query.cost(crossbowman, civilisation="Franks", context=researched)) == {
        "gold": 39,
        "wood": 40,
    }
    unresearched = effects.Context(researched=frozenset())
    assert _value(query.cost(crossbowman, civilisation="Franks", context=unresearched)) == {
        "gold": 65,
        "wood": 40,
    }


def test_a_team_effect_reaches_the_owners_allies_and_not_their_opponents() -> None:
    ship = _entity("unit", 545)
    allied = effects.Context(team=frozenset({"Franks", "Sicilians"}))
    alone = effects.Context(team=frozenset({"Franks"}))
    assert _value(query.cost(ship, civilisation="Franks", context=allied)) == {"wood": 63}
    assert _value(query.cost(ship, civilisation="Sicilians", context=allied)) == {"wood": 63}
    assert _value(query.cost(ship, civilisation="Franks", context=alone)) == {"wood": 125}
    with pytest.raises(effects.ContextRequired):
        query.cost(ship, civilisation="Franks")
    university = _entity("technology", 93)
    with_malians = effects.Context(team=frozenset({"Franks", "Malians"}))
    assert _value(
        query.production_time(university, civilisation="Franks", context=with_malians)
    ) == pytest.approx(60 / 1.8)


def test_a_sicilian_town_center_is_built_twice_as_fast() -> None:
    assert _value(query.production_time(_entity("building", 621), civilisation="Sicilians")) == 75
    assert _value(query.production_time(_entity("building", 621), civilisation="Franks")) == 150


@pytest.mark.parametrize(
    ("civilisation", "kind", "entity_id", "field"),
    [
        ("Slavs", "building", 82, "cost"),
        ("Persians", "unit", 4, "cost"),
        ("Sicilians", "building", 1665, "production_time"),
    ],
    ids=["detinets", "kamandaran", "fortifications"],
)
def test_a_bonus_the_pack_cannot_size_is_refused_and_never_answered_at_the_baseline(
    civilisation: str, kind: str, entity_id: int, field: str
) -> None:
    answer = getattr(query, field)(_entity(kind, entity_id), civilisation=civilisation)

    assert isinstance(answer, gaps.KnowledgeGap)
    assert answer.cause == "effect-not-modelled"
    assert answer.civilisation == civilisation
    assert answer.detail


def test_contrast_the_refused_entities_are_answered_for_a_civilisation_without_the_bonus() -> None:
    assert _value(query.cost(_entity("building", 82), civilisation="Saracens")) == {
        "stone": 650,
        "wood": 0,
    }
    assert _value(query.production_time(_entity("building", 1665), civilisation="Franks")) == 125
