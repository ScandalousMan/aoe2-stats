"""T768: the civilisation effects of `aoe2techtree-185872-civilisations-32`, the fourth build 185872
snapshot, which supersedes the third (`-20`) and models thirty-two civilisations.

Six kinds of claim, none of them a restatement of `test_effects.py`, `test_bullet_coverage.py`,
`test_effects_185872_civilisations.py` or `test_effects_185872_civilisations_20.py` (which keep the
earlier snapshots' records, pinned):

- **Nothing is dropped.** Every bullet of the thirty-two civilisations' strings in the pack this
  snapshot is derived from, `aoe2techtree-3bb43b1`, is an `[[effect]]` row's `source_text` or is in
  one of two closed registries below, each entry a real bullet. Set difference and exact count, so a
  failure names the bullet. The registries name bullets that cannot be a row: a class of unit the
  pack does not enumerate on a field this knowledge base does not carry (`effects.Effect` requires
  a non-empty explicit selector), and Khmer's removal of building prerequisites, a field the
  knowledge base does not carry at all (research.md D3), which is listed in the header of
  `effects.toml` and never written as a row.
- **Nothing dangles.** Every row's `source_key` and `source_text` are the pack's own, every selector
  entry exists in this snapshot's `rules.json`, every researched condition names a technology of it,
  and the `[[civilisation_id]]` table names every civilisation of the pack once.
- **The twenty civilisations of the third snapshot are carried.** Same build, same pack revision,
  same strings: every row of the third snapshot is in this one, parsed key for key, and so are its
  `rules.json`, `aliases.toml`, `disagreements.toml` and raw-id table, byte for byte.
- **The values come out as the strings say**, one case per kind of row, each with the contrast case
  that must not apply, every expectation derived from the pack's own baseline and the bullet's
  arithmetic and not read back from the file under test.
- **What is refused is refused for a stated reason**, and the reason is checked against the
  owner's sheet (`specs/006-replay-analysis-foundations/owner-readings.md`).
- **A team row reaches the other civilisations' queries.** The Huns', Portuguese and Ethiopians'
  team rows touch entities every civilisation asks about, so those queries now need
  `Context.team`; the cases below pass it.
"""

from __future__ import annotations

import json
import math
import tomllib
from collections.abc import Mapping
from importlib import resources
from pathlib import Path

import pytest

from aoe2stats_knowledge import effects, gaps, query, snapshot

_PACKAGE = "aoe2stats_knowledge"
_PACK = "aoe2techtree-3bb43b1"
_DIRECTORY = "aoe2techtree-185872-civilisations-32"
_THIRD_DIRECTORY = "aoe2techtree-185872-civilisations-20"
_BUILD = 185872
_THIRD_DIGEST = "sha256:a4f213b6e84f90ee88a916929a136165c3979f214a191556877669dd0a92b4db"
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
}

#: Batch B (T768), in the order `tasks.md` files it.
_BATCH_B = (
    "Huns",
    "Koreans",
    "Italians",
    "Hindustanis",
    "Incas",
    "Magyars",
    "Portuguese",
    "Ethiopians",
    "Berbers",
    "Khmer",
    "Malay",
    "Burmese",
)

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
    "Huns": (
        "Do not need houses, but start with -100 wood",
        "Atheism (Enemy Relics generate -50% resources; Wonder and Relic victory takes +100 years)",
    ),
    "Koreans": ("Stone miners work +20% faster",),
    "Italians": (),
    "Hindustanis": ("Gunpowder Units +1 melee/+1 pierce armor",),
    "Incas": ("Team Bonus: Start with a free Llama",),
    "Magyars": ("Recurve Bow (Mounted Archers +1 attack, +1 range)",),
    "Portuguese": (
        "Foragers generate wood in addition to food",
        "Ships +10/15/20% HP in Feudal/Castle/Imperial Age",
        "Arquebus (Gunpowder Units fire more accurately at moving targets)",
    ),
    "Ethiopians": (
        "Receive +100 gold and +100 food when advancing to the next Age",
        "Foot Archers attack +18% faster",
    ),
    "Berbers": (
        "Ships move +10% faster",
        "Maghrebi Camels (Camel Units regenerate 15 HP per minute)",
    ),
    "Khmer": (
        # Research D3: the knowledge base carries no prerequisites field, so this bonus has no row
        # and is listed in the header of `effects.toml` instead.
        "No buildings required to advance to the next Age or to unlock other buildings",
        "Farmers don't require Mills or Town Centers to drop off food",
    ),
    "Malay": (),
    "Burmese": (
        "Infantry +1/+2/+3 attack in Feudal/Castle/Imperial Age",
        "Manipur Cavalry (Cavalry +4 attack vs. Ranged Soldiers)",
        "Team Bonus: Relics visible on the map at the start of the game",
    ),
}

#: A real entity whose baseline already answers the bullet, so a row would assert nothing.
_ENTITY_REPRESENTED_BUT_NEEDS_NO_EFFECT_ROW: Mapping[str, tuple[str, ...]] = {
    "Persians": ("Can build Caravanserai in Imperial Age",),
    "Hindustanis": ("Can build Caravanserai in Imperial Age",),
    "Portuguese": ("Can build Feitoria in Imperial Age",),
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


def test_the_bullets_of_the_thirty_two_civilisations_number_two_hundred_and_twenty_two() -> None:
    """A guard on the reader: a changed pack string that silently shifted the count would move
    every assertion above together. The twenty of the third snapshot are 140; batch B's twelve are
    82."""
    assert sum(len(_bullets_for(key)) for key in _HELP_STRING_ID.values()) == 222
    assert sum(len(_bullets_for(_HELP_STRING_ID[name])) for name in _BATCH_B) == 82


def test_khmers_prerequisite_bullet_is_listed_in_the_header_and_is_never_a_row() -> None:
    """Research D3: the knowledge base carries no prerequisites field, so the bonus that removes
    building prerequisites has no row; it is a header bullet and a registry entry."""
    bullet = "No buildings required to advance to the next Age or to unlock other buildings"
    text = _snapshot_root().joinpath("effects.toml").read_text(encoding="utf-8")
    header = text[: text.index("[[effect]]")]
    flattened = " ".join(line.lstrip("# ").strip() for line in header.splitlines())
    assert bullet in flattened
    assert bullet in _NO_SELECTOR_BULLETS["Khmer"]
    assert bullet in _bullets_for(_HELP_STRING_ID["Khmer"])
    assert all("prerequisite" not in e.field and bullet != e.source_text for e in _effects())


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
        if effect.condition == "controlled":  # pragma: no cover - none in batches A and B
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
        ("Huns", "483", "produced_at"),
        ("Italians", "499", "cost"),
        ("Magyars", "514", "cost"),
        ("Portuguese", "1404", "production_time"),
        ("Malay", "624", "available_to"),
        ("Malay", "625", "cost"),
    }
    names = {
        tech: " ".join(str(technologies[tech]["name"]).replace("<br>", " ").split())
        for _, tech, _ in conditional
    }
    assert names["483"] == "Marauders"
    assert names["499"] == "Silk Road"
    assert names["514"] == "Corvinian Army"
    assert names["624"] == "Thalassocracy"
    assert names["625"] == "Forced Levy"
    assert names["1404"] == "Circum- navigation"


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
    assert current.supersedes == _THIRD_DIGEST
    assert current.normaliser_version == 2
    assert current.validation is not None
    assert current.validation.performed_at == "2026-10-22"
    assert current.validation.details["not_checked"].strip()
    assert current.validation.details["release_notes"]["url"].endswith("-update-185872/")


def test_every_row_of_batch_b_says_it_was_read_by_this_task() -> None:
    for effect in _effects():
        if effect.civilisation in _BATCH_B:
            assert "T768" in effect.validated_by, (effect.civilisation, effect.source_text)
            assert effect.source_key in effect.validated_by


# ------------------------------------------------------------ the twenty are carried unchanged


def _row_key(effect: effects.Effect) -> tuple[str, str, str, tuple[tuple[str, str], ...]]:
    return (
        effect.civilisation,
        effect.source_text,
        effect.field,
        tuple((entry.kind, entry.id) for entry in effect.selector),
    )


def test_every_row_of_the_third_snapshot_is_carried_unchanged() -> None:
    """Same build, same pack revision, same strings: a row is carried, not re-derived (Phase 8's
    transcription rule). Compared as parsed rows, every field including `validated_by`, and in
    the same order."""
    new = _effects()
    old = _effects(_THIRD_DIRECTORY)
    assert new[: len(old)] == old
    new_by_key = {_row_key(e): e for e in new}
    for row in old:
        assert new_by_key[_row_key(row)] == row, ("changed", row.civilisation, row.source_text)


def test_the_rows_beyond_the_twenty_are_batch_bs_and_only_batch_bs() -> None:
    old = _effects(_THIRD_DIRECTORY)
    added = _effects()[len(old) :]
    assert added
    assert {e.civilisation for e in added} == set(_BATCH_B)
    assert {e.civilisation for e in old}.isdisjoint(_BATCH_B)


def test_the_rules_the_aliases_the_disagreements_and_the_raw_ids_are_the_thirds() -> None:
    for name in ("rules.json", "aliases.toml", "disagreements.toml"):
        assert (
            _snapshot_root().joinpath(name).read_bytes()
            == _snapshot_root(_THIRD_DIRECTORY).joinpath(name).read_bytes()
        ), name
    assert dict(effects.civilisation_id_names(_DIRECTORY)) == dict(
        effects.civilisation_id_names(_THIRD_DIRECTORY)
    )
    assert effects._civilisation_ids(_DIRECTORY) == effects._civilisation_ids(_THIRD_DIRECTORY)


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


def _team(*civilisations: str) -> effects.Context:
    return effects.Context(team=frozenset(civilisations))


def test_huns_cavalry_archers_cost_less_from_the_castle_age() -> None:
    archer = _entity("unit", 39)
    assert _baseline("unit", 39, "cost") == {"gold": 60, "wood": 40}
    for age, factor in ((3, 0.9), (4, 0.8)):
        assert _value(
            query.cost(archer, civilisation="Huns", context=effects.Context(age=age))
        ) == {
            "gold": _half_up(60 * factor),
            "wood": _half_up(40 * factor),
        }
    # Contrast: the Feudal Age, another unit and another civilisation answer the baseline.
    assert _value(query.cost(archer, civilisation="Huns", context=effects.Context(age=2))) == {
        "gold": 60,
        "wood": 40,
    }
    assert _value(
        query.cost(_entity("unit", 4), civilisation="Huns", context=effects.Context(age=4))
    ) == {"gold": 45, "wood": 25}
    assert _value(query.cost(archer, civilisation="Franks")) == {"gold": 60, "wood": 40}
    with pytest.raises(effects.ContextRequired):
        query.cost(archer, civilisation="Huns")


def test_huns_marauders_add_the_stable_to_the_tarkans_and_their_team_trains_faster_there() -> None:
    tarkan = _entity("unit", 755)
    with pytest.raises(effects.ContextRequired):
        query.produced_at(tarkan, civilisation="Huns")
    before = query.produced_at(
        tarkan, civilisation="Huns", context=effects.Context(researched=frozenset())
    )
    after = query.produced_at(
        tarkan, civilisation="Huns", context=effects.Context(researched=frozenset({"483"}))
    )
    assert [ref.id for ref in _value(before)] == ["82"]  # type: ignore[attr-defined]
    assert [ref.id for ref in _value(after)] == ["82", "101"]  # type: ignore[attr-defined]
    # Contrast: no other civilisation gains the Stable.
    assert [ref.id for ref in _value(query.produced_at(tarkan, civilisation="Franks"))] == ["82"]  # type: ignore[attr-defined]
    knight = _entity("unit", 38)
    assert _baseline("unit", 38, "training_time") == 30
    assert _value(
        query.production_time(knight, civilisation="Mongols", context=_team("Mongols", "Huns"))
    ) == pytest.approx(30 / 1.2)
    assert _value(
        query.production_time(knight, civilisation="Huns", context=_team("Huns"))
    ) == pytest.approx(30 / 1.2)
    assert (
        _value(query.production_time(knight, civilisation="Mongols", context=_team("Mongols")))
        == 30
    )
    with pytest.raises(effects.ContextRequired):
        query.production_time(knight, civilisation="Mongols")


def test_koreans_pay_half_the_wood_for_ranged_soldiers_and_infantry_less_for_ships() -> None:
    wood = {
        4: ({"gold": 45, "wood": 25}, {"gold": 45, "wood": _half_up(25 * 0.5)}),  # Archer
        93: ({"food": 35, "wood": 25}, {"food": 35, "wood": _half_up(25 * 0.5)}),  # Spearman
        827: ({"gold": 60, "wood": 200}, {"gold": 60, "wood": 100}),  # War Wagon: update 87863
        831: ({"gold": 130, "wood": 190}, {"gold": 130, "wood": 152}),  # Turtle Ship: update 169123
    }
    for unit, (base, expected) in wood.items():
        assert _baseline("unit", unit, "cost") == base
        assert _value(query.cost(_entity("unit", unit), civilisation="Koreans")) == expected
        assert _value(query.cost(_entity("unit", unit), civilisation="Franks")) == base
    # A unit with no wood is not touched, and a Knight is neither Infantry nor a Ranged Soldier.
    assert _value(query.cost(_entity("unit", 74), civilisation="Koreans")) == {
        "food": 50,
        "gold": 20,
    }
    assert _value(query.cost(_entity("unit", 38), civilisation="Koreans")) == {
        "food": 60,
        "gold": 75,
    }


def test_koreans_archer_armor_and_tower_upgrades_are_free_and_the_rest_is_not() -> None:
    free = {211: {"food": 0}, 212: {"food": 0, "gold": 0}, 140: {"food": 0, "wood": 0}}
    alone = _team("Koreans")
    for tech, cost in free.items():
        assert _value(query.cost(_entity("technology", tech), civilisation="Koreans")) == cost
        assert (
            _value(
                query.production_time(
                    _entity("technology", tech), civilisation="Koreans", context=alone
                )
            )
            == 0
        )
    # Contrast: Arrowslits changes what a tower does and does not upgrade one; Franks pay the base.
    assert _value(query.cost(_entity("technology", 608), civilisation="Koreans")) == {
        "food": 250,
        "wood": 250,
    }
    assert _value(query.cost(_entity("technology", 211), civilisation="Franks")) == {"food": 100}


def test_italians_advance_for_less_and_pay_less_for_dock_university_and_gunpowder() -> None:
    for age_tech, factor in ((101, 0.85), (102, 0.85), (103, 0.85)):
        base = _baseline("technology", age_tech, "cost")
        assert _value(query.cost(_entity("technology", age_tech), civilisation="Italians")) == {
            resource: _half_up(amount * factor)  # type: ignore[attr-defined]
            for resource, amount in base.items()  # type: ignore[attr-defined]
        }
    assert _value(query.cost(_entity("technology", 102), civilisation="Franks")) == {
        "food": 800,
        "gold": 200,
    }
    # A Dock technology (Gillnets) and a University technology (Masonry), 25% less, half up.
    assert _value(query.cost(_entity("technology", 65), civilisation="Italians")) == {
        "food": 75,
        "wood": _half_up(125 * 0.75),
    }
    assert _value(query.cost(_entity("technology", 50), civilisation="Italians")) == {
        "food": _half_up(150 * 0.75),
        "wood": _half_up(175 * 0.75),
    }
    assert _value(query.cost(_entity("technology", 50), civilisation="Franks")) == {
        "food": 150,
        "wood": 175,
    }
    assert _value(query.cost(_entity("unit", 5), civilisation="Italians")) == {
        "food": 36,
        "gold": 40,
    }
    assert _value(query.cost(_entity("unit", 36), civilisation="Italians")) == {
        "gold": 180,
        "wood": 180,
    }
    assert _value(query.cost(_entity("unit", 13), civilisation="Italians")) == {"wood": 64}


def test_italians_silk_road_halves_the_trade_carts_and_their_team_trains_the_condottiero() -> None:
    cart = _entity("unit", 128)
    researched = effects.Context(researched=frozenset({"499"}))
    assert _value(query.cost(cart, civilisation="Italians", context=researched)) == {
        "gold": 25,
        "wood": 50,
    }
    assert _value(
        query.cost(cart, civilisation="Italians", context=effects.Context(researched=frozenset()))
    ) == {"gold": 50, "wood": 100}
    with pytest.raises(effects.ContextRequired):
        query.cost(cart, civilisation="Italians")
    condottiero = _entity("unit", 882)
    assert _baseline("unit", 882, "age_requirement") == 4
    assert (
        _value(
            query.available_to(
                condottiero, civilisation="Franks", context=_team("Franks", "Italians")
            )
        )
        is True
    )
    assert (
        _value(query.available_to(condottiero, civilisation="Franks", context=_team("Franks")))
        is False
    )
    assert (
        _value(query.available_to(condottiero, civilisation="Italians", context=_team("Italians")))
        is True
    )
    with pytest.raises(effects.ContextRequired):
        query.available_to(condottiero, civilisation="Franks")


def test_hindustanis_villagers_cost_less_by_age_and_the_caravanserai_is_the_baseline() -> None:
    villager = _entity("unit", 83)
    for age, factor in ((1, 0.92), (2, 0.87), (3, 0.82), (4, 0.77)):
        assert _value(
            query.cost(villager, civilisation="Hindustanis", context=effects.Context(age=age))
        ) == {"food": _half_up(50 * factor)}
    assert _value(query.cost(villager, civilisation="Franks")) == {"food": 50}
    caravanserai = _entity("building", 1754)
    assert _baseline("building", 1754, "age_requirement") == 4
    assert _value(query.age_requirement(caravanserai, civilisation="Hindustanis")) == 4
    assert _value(query.available_to(caravanserai, civilisation="Hindustanis")) is True
    assert _value(query.available_to(caravanserai, civilisation="Slavs")) is False


def test_incas_buildings_cost_less_stone_and_their_military_units_less_food_by_age() -> None:
    assert _value(query.cost(_entity("building", 109), civilisation="Incas")) == {
        "stone": _half_up(100 * 0.85),
        "wood": 275,
    }
    assert _value(query.cost(_entity("building", 82), civilisation="Incas")) == {
        "stone": _half_up(650 * 0.85),
        "wood": 0,
    }
    assert _value(query.cost(_entity("building", 12), civilisation="Incas")) == {"wood": 175}
    for age, factor in ((1, 0.85), (2, 0.8), (3, 0.75), (4, 0.7)):
        context = effects.Context(age=age)
        assert _value(query.cost(_entity("unit", 74), civilisation="Incas", context=context)) == {
            "food": _half_up(50 * factor),
            "gold": 20,
        }
        # Update 107882 states the Skirmisher's food: 21 in the Feudal Age at 15%, so 25 * 0.85.
        assert _value(query.cost(_entity("unit", 7), civilisation="Incas", context=context)) == {
            "food": _half_up(25 * factor),
            "wood": 35,
        }
    # Contrast: a Villager is not a Military Unit, a warship and the Monk cost no food, and
    # another civilisation pays the baseline.
    now = effects.Context(age=3)
    assert _value(query.cost(_entity("unit", 83), civilisation="Incas", context=now)) == {
        "food": 50
    }
    assert _value(query.cost(_entity("unit", 125), civilisation="Incas", context=now)) == {
        "food": 0,
        "gold": 100,
    }
    assert _value(query.cost(_entity("unit", 74), civilisation="Franks")) == {
        "food": 50,
        "gold": 20,
    }


def test_magyars_scouts_cost_less_melee_upgrades_are_free_and_the_huszar_cost_is_refused() -> None:
    assert _value(query.cost(_entity("unit", 448), civilisation="Magyars")) == {
        "food": _half_up(80 * 0.85)
    }
    assert _value(query.cost(_entity("unit", 448), civilisation="Franks")) == {"food": 80}
    free = {67: {"food": 0}, 68: {"food": 0, "gold": 0}, 75: {"food": 0, "gold": 0}}
    for tech, cost in free.items():
        assert _value(query.cost(_entity("technology", tech), civilisation="Magyars")) == cost
        assert (
            _value(
                query.production_time(
                    _entity("technology", tech), civilisation="Magyars", context=_team("Magyars")
                )
            )
            == 0
        )
    # Contrast: a ranged attack upgrade is not a melee one.
    assert _value(query.cost(_entity("technology", 199), civilisation="Magyars")) == {
        "food": 100,
        "gold": 50,
    }
    for huszar in (869, 871):
        _refused(query.cost(_entity("unit", huszar), civilisation="Magyars"), "Magyars")
    assert _value(query.cost(_entity("unit", 869), civilisation="Franks")) == {
        "food": 35,
        "gold": 45,
    }


def test_the_magyars_team_trains_mounted_archers_faster_and_not_cavalry_archers_alone() -> None:
    allied = _team("Franks", "Magyars")
    assert _baseline("unit", 39, "training_time") == 37
    assert _value(
        query.production_time(_entity("unit", 39), civilisation="Franks", context=allied)
    ) == pytest.approx(37 / 1.25)
    # The Mounted Crossbowman, the Camel Archer and the War Wagon are Mounted Archers in the pack.
    for unit in (2700, 1007, 827):
        base = _baseline("unit", unit, "training_time")
        assert _value(
            query.production_time(_entity("unit", unit), civilisation="Franks", context=allied)
        ) == pytest.approx(base / 1.25)  # type: ignore[operator]
    # Contrast: the Genitour is a Mounted Skirmisher and the Knight is not an archer.
    assert _value(
        query.production_time(_entity("unit", 1010), civilisation="Franks", context=allied)
    ) == _baseline("unit", 1010, "training_time")
    assert (
        _value(
            query.production_time(
                _entity("unit", 39), civilisation="Franks", context=_team("Franks")
            )
        )
        == 37
    )


def test_portuguese_units_cost_less_gold_and_their_ships_train_faster_once_circumnavigated() -> (
    None
):
    for unit, base in ((4, {"gold": 45, "wood": 25}), (38, {"food": 60, "gold": 75})):
        assert _baseline("unit", unit, "cost") == base
        assert _value(query.cost(_entity("unit", unit), civilisation="Portuguese")) == {
            resource: (_half_up(amount * 0.8) if resource == "gold" else amount)
            for resource, amount in base.items()
        }
    # A Villager has no gold, and another civilisation pays the baseline.
    assert _value(query.cost(_entity("unit", 83), civilisation="Portuguese")) == {"food": 50}
    assert _value(query.cost(_entity("unit", 4), civilisation="Franks")) == {"gold": 45, "wood": 25}
    galley = _entity("unit", 539)
    assert _baseline("unit", 539, "training_time") == 45
    done = effects.Context(researched=frozenset({"1404"}), team=frozenset({"Portuguese"}))
    assert _value(query.production_time(galley, civilisation="Portuguese", context=done)) == (
        pytest.approx(45 / 1.33)
    )
    assert (
        _value(
            query.production_time(
                galley,
                civilisation="Portuguese",
                context=effects.Context(researched=frozenset(), team=frozenset({"Portuguese"})),
            )
        )
        == 45
    )


def test_the_portuguese_team_researches_faster_except_the_age_advances() -> None:
    loom = _entity("technology", 22)
    assert _baseline("technology", 22, "research_time") == 25
    assert _value(
        query.production_time(loom, civilisation="Franks", context=_team("Franks", "Portuguese"))
    ) == pytest.approx(25 / 1.25)
    assert _value(query.production_time(loom, civilisation="Franks", context=_team("Franks"))) == 25
    for age_tech in (101, 102, 103):  # update 73855: "(excluding Age Up)"
        assert _value(
            query.production_time(
                _entity("technology", age_tech),
                civilisation="Franks",
                context=_team("Franks", "Portuguese"),
            )
        ) == _baseline("technology", age_tech, "research_time")
    with pytest.raises(effects.ContextRequired):
        query.production_time(loom, civilisation="Franks")
    feitoria = _entity("building", 1021)
    assert _value(query.available_to(feitoria, civilisation="Portuguese")) is True
    assert _value(query.age_requirement(feitoria, civilisation="Portuguese")) == 4
    assert _value(query.available_to(feitoria, civilisation="Franks")) is False


def test_ethiopians_pikeman_upgrade_is_free_and_their_team_builds_outposts_without_stone() -> None:
    assert _value(query.cost(_entity("technology", 197), civilisation="Ethiopians")) == {
        "food": 0,
        "gold": 0,
    }
    assert (
        _value(
            query.production_time(
                _entity("technology", 197), civilisation="Ethiopians", context=_team("Ethiopians")
            )
        )
        == 0
    )
    assert _value(query.cost(_entity("technology", 197), civilisation="Franks")) == {
        "food": 160,
        "gold": 90,
    }
    outpost = _entity("building", 598)
    assert _baseline("building", 598, "cost") == {"stone": 5, "wood": 25}
    assert _value(
        query.cost(outpost, civilisation="Franks", context=_team("Franks", "Ethiopians"))
    ) == {"stone": 0, "wood": 25}
    assert _value(query.cost(outpost, civilisation="Franks", context=_team("Franks"))) == {
        "stone": 5,
        "wood": 25,
    }
    with pytest.raises(effects.ContextRequired):
        query.cost(outpost, civilisation="Franks")


def test_berbers_stable_units_cost_less_and_their_team_trains_the_genitour() -> None:
    camel = _entity("unit", 329)
    assert _baseline("unit", 329, "cost") == {"food": 55, "gold": 60}
    for age, factor in ((3, 0.85), (4, 0.8)):
        assert _value(
            query.cost(camel, civilisation="Berbers", context=effects.Context(age=age))
        ) == {"food": _half_up(55 * factor), "gold": _half_up(60 * factor)}
    assert _value(query.cost(camel, civilisation="Berbers", context=effects.Context(age=2))) == {
        "food": 55,
        "gold": 60,
    }
    assert _value(query.cost(camel, civilisation="Franks")) == {"food": 55, "gold": 60}
    for entity in (_entity("unit", 1010), _entity("unit", 1012), _entity("technology", 599)):
        assert (
            _value(
                query.available_to(
                    entity, civilisation="Franks", context=_team("Franks", "Berbers")
                )
            )
            is True
        )
        assert (
            _value(query.available_to(entity, civilisation="Franks", context=_team("Franks")))
            is False
        )
    assert _baseline("unit", 1010, "age_requirement") == 3


def test_kasbah_is_refused_for_the_berbers_castle_and_for_nothing_else() -> None:
    """The one bonus of batch B the effect model cannot express (it needs `researched` and `team`
    together). The refusal is scoped to the Berbers' own tree; an ally's Castle is not refused."""
    for entity in (
        _entity("unit", 331),
        _entity("unit", 1007),
        _entity("technology", 578),
        _entity("technology", 579),
    ):
        _refused(
            query.production_time(entity, civilisation="Berbers", context=_team("Berbers")),
            "Berbers",
        )
    # Contrast: a Castle unit the Berbers cannot train, and another civilisation's Castle.
    assert _value(
        query.production_time(_entity("unit", 8), civilisation="Berbers", context=_team("Berbers"))
    ) == _baseline("unit", 8, "training_time")
    assert _value(
        query.production_time(_entity("unit", 1007), civilisation="Franks", context=_team("Franks"))
    ) == _baseline("unit", 1007, "training_time")


def test_khmer_bonuses_touch_no_carried_field_so_every_khmer_row_is_a_refusal_row() -> None:
    rows = [e for e in _effects() if e.civilisation == "Khmer"]
    assert rows
    assert all(e.modelled == "no" for e in rows)
    elephant = _entity("unit", 1132)
    assert _value(query.cost(elephant, civilisation="Khmer")) == {"food": 100, "gold": 70}
    assert _value(query.age_requirement(elephant, civilisation="Khmer")) == 3


def test_malay_advance_faster_and_their_infantry_armor_and_fish_traps_follow_the_bullets() -> None:
    alone = _team("Malay")
    for age_tech in (101, 102, 103):
        base = _baseline("technology", age_tech, "research_time")
        assert _value(
            query.production_time(_entity("technology", age_tech), civilisation="Malay")
        ) == pytest.approx(base / 1.66)  # type: ignore[operator]
    free = {74: {"food": 0}, 76: {"food": 0, "gold": 0}, 77: {"food": 0, "gold": 0}}
    for tech, cost in free.items():
        assert _value(query.cost(_entity("technology", tech), civilisation="Malay")) == cost
        assert (
            _value(
                query.production_time(
                    _entity("technology", tech), civilisation="Malay", context=alone
                )
            )
            == 0
        )
    elephant = _entity("unit", 1132)
    for age, factor in ((3, 0.75), (4, 0.65)):
        assert _value(
            query.cost(elephant, civilisation="Malay", context=effects.Context(age=age))
        ) == {"food": _half_up(100 * factor), "gold": _half_up(70 * factor)}
    assert _value(query.cost(_entity("building", 199), civilisation="Malay")) == {"wood": 67}
    assert _value(query.cost(_entity("building", 199), civilisation="Franks")) == {"wood": 100}


def test_malay_thalassocracy_replaces_the_dock_with_the_harbor() -> None:
    dock, harbor = _entity("building", 45), _entity("building", 1189)
    before = effects.Context(researched=frozenset())
    after = effects.Context(researched=frozenset({"624"}))
    assert _value(query.available_to(dock, civilisation="Malay", context=before)) is True
    assert _value(query.available_to(dock, civilisation="Malay", context=after)) is False
    assert _value(query.available_to(harbor, civilisation="Malay", context=after)) is True
    # The pack's Malay tree lists the Harbor, so before the technology the answer is the pack's.
    assert _value(query.available_to(harbor, civilisation="Malay", context=before)) is True
    # Contrast: another civilisation keeps its Dock, and has no Harbor.
    assert _value(query.available_to(dock, civilisation="Franks")) is True
    assert _value(query.available_to(harbor, civilisation="Franks")) is False
    with pytest.raises(effects.ContextRequired):
        query.available_to(dock, civilisation="Malay")


def test_forced_levy_is_refused_for_the_militia_line_of_the_malay_only() -> None:
    for unit in (74, 75, 77, 473, 567):
        _refused(query.cost(_entity("unit", unit), civilisation="Malay"), "Malay")
    assert _value(query.cost(_entity("unit", 74), civilisation="Franks")) == {
        "food": 50,
        "gold": 20,
    }


def test_burmese_lumber_camp_technologies_are_free_and_monastery_technologies_cost_half() -> None:
    for tech, cost in ((202, {"food": 0, "wood": 0}), (203, {"food": 0, "wood": 0})):
        assert _value(query.cost(_entity("technology", tech), civilisation="Burmese")) == cost
        assert (
            _value(
                query.production_time(
                    _entity("technology", tech), civilisation="Burmese", context=_team("Burmese")
                )
            )
            == 0
        )
    assert _value(query.cost(_entity("technology", 45), civilisation="Burmese")) == {
        "food": _half_up(550 * 0.5),
        "gold": _half_up(750 * 0.5),
    }
    assert _value(query.cost(_entity("technology", 45), civilisation="Franks")) == {
        "food": 550,
        "gold": 750,
    }
    assert _value(query.cost(_entity("technology", 202), civilisation="Franks")) == {
        "food": 100,
        "wood": 50,
    }


# ------------------------------------------------------------------- the owner's open rows


def test_every_refused_reason_is_a_sentence_and_no_refusal_is_silent() -> None:
    for effect in _effects():
        if effect.modelled == "no":
            assert effect.reason and len(effect.reason) > 40, (
                effect.civilisation,
                effect.source_text,
            )


def test_the_three_refusals_of_batch_b_that_touch_a_carried_field_are_open_owner_rows() -> None:
    """A refusal on cost, production time, age, produced-at or availability blocks, and FR-022b
    wants each one enumerated in the owner's sheet. Batch B has three, and no other."""
    carried = {"cost", "production_time", "age_requirement", "produced_at", "available_to"}
    refusals = {
        (e.civilisation, e.field)
        for e in _effects()
        if e.civilisation in _BATCH_B and e.modelled == "no" and e.field in carried
    }
    assert refusals == {
        ("Magyars", "cost"),
        ("Malay", "cost"),
        ("Berbers", "production_time"),
    }
    sheet = _OWNER_READINGS.read_text(encoding="utf-8")
    assert "Corvinian Army" in sheet
    assert "Forced Levy" in sheet
    assert "Kasbah" in sheet
    for civilisation, _ in refusals:
        assert f"| 185872 | {civilisation} |" in sheet, civilisation
