"""T773: the civilisation effects of `aoe2techtree-180059-civilisations-53`, the second snapshot of
build 180059: it supersedes the first (`aoe2techtree-180059`, six civilisations) and models
fifty-three, every civilisation of the pack that build is derived from
(`packages/knowledge/packs/aoe2techtree/`).

Seven kinds of claim, none of them a restatement of `test_effects.py`, `test_bullet_coverage.py` or
the build 185872 snapshots' records (`test_effects_185872_civilisations*.py`):

- **Nothing is dropped.** Every bullet of the fifty-three civilisations' strings in the build 180059
  pack is an `[[effect]]` row's `source_text` or is in one closed registry, each a real bullet.
- **Nothing dangles.** Every row's `source_key` and `source_text` are the pack's own, every selector
  and condition entity exists in this snapshot's `rules.json`, `civilisations_modelled` is the
  whole pack, and the raw-id table names each civilisation once.
- **The carry rule holds row by row (T773).** A row is carried from
  `aoe2techtree-185872-civilisations-56` only where the bullet is byte-identical under the same key
  in both packs, every selector and condition identifier has the same name here and a class the pack
  defines by a producing building has the same members, and no selected entity is one the build
  185872 release notes name or one whose data differs between the two packs. The conditions are
  recomputed here from both packs, never read back from the file under test; every carried row is
  the source row but for an appended `validated_by` that names the source digest, and every row
  that is not carried fails at least one condition.
- **The derivation is reproducible.** `rules.json` and `disagreements.toml` are what the
  normaliser (version 2) derives from the pack, byte for byte; the snapshot names the pack's commit.
- **Resolution.** Build 180059 resolves to this snapshot, which names the first one's digest, and
  the first still loads by identity and answers its own bytes (SC-005).
- **The aliases** close the two building identifiers the second committed recording places that the
  pack does not name (490 and 673, both the Gate).
- **The values come out as the strings say**: carried and transcribed rows answer through the public
  query surface, each with its contrast case.
"""

from __future__ import annotations

import dataclasses
import functools
import json
import re
import tomllib
from collections.abc import Mapping
from importlib import resources

import pytest

from aoe2stats_knowledge import effects, gaps, normalise, query, snapshot

_PACKAGE = "aoe2stats_knowledge"
_PACK = "aoe2techtree"
_OTHER_PACK = "aoe2techtree-3bb43b1"
_DIRECTORY = "aoe2techtree-180059-civilisations-53"
_FIRST_DIRECTORY = "aoe2techtree-180059"
_SOURCE_DIRECTORY = "aoe2techtree-185872-civilisations-56"
_BUILD = 180059
_FIRST_DIGEST = "sha256:6167f0b69be56d7a33803d29a060b9f29f34c917073eb970ccccc1c206c6b81a"
_SOURCE_DIGEST = "sha256:b247190134e69b46e5111487db0ff98514df9ceb41bcd4f926a7278fbedd952f"
_CARRIED_MARK = "Carried to build 180059 by T773"
_NOT_CARRIED_MARK = "Not carried from the build 185872 snapshot"

#: The three civilisations of the build 185872 pack that the build 180059 pack does not have: the
#: Viking Sagas added them in build 185872.
_NOT_IN_THIS_PACK = ("Saxons", "Varangians", "Danes")

#: `strings.en.json`'s `help_string_id` for each of the fifty-three civilisations, the same key in
#: both packs.
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
}

#: Bullets with no row: a class the pack does not enumerate, on a field this knowledge base does not
#: carry, or a resource, a start condition or a victory rule no entity carries. They are the build
#: 185872 snapshots' registries (their tests hold them, bullet by bullet) but for four bullets this
#: pack words differently from the other: the Bohemians' Wagenburg Tactics (+15%), the Vietnamese's
#: Archery Range units, the Vikings' Chieftains (with the gold clause) and the Wu's +55 food
#: (without "when built"). The test named "..._registries_but_four" asserts it.
_NO_ROW_BULLETS: Mapping[str, tuple[str, ...]] = {
    "Franks": (
        "Foragers work +15% faster",
        "Mounted Units +20% HP starting in Feudal Age",
    ),
    "Teutons": (
        "Ironclad (Siege Weapons +4 melee armor)",
        "Team Bonus: Units more resistant to conversion",
    ),
    "Persians": (
        "Start with +50 wood and +50 food",
        "Can build Caravanserai in Imperial Age",
    ),
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
        "Chieftains (Infantry +5 attack vs. Cavalry, +4 vs. Camel Units; generate +5 gold when defeating Villagers, Trade Units and Monks)",  # noqa: E501
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
    "Hindustanis": (
        "Gunpowder Units +1 melee/+1 pierce armor",
        "Can build Caravanserai in Imperial Age",
    ),
    "Incas": ("Team Bonus: Start with a free Llama",),
    "Magyars": ("Recurve Bow (Mounted Archers +1 attack, +1 range)",),
    "Portuguese": (
        "Foragers generate wood in addition to food",
        "Can build Feitoria in Imperial Age",
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
        "No buildings required to advance to the next Age or to unlock other buildings",
        "Farmers don't require Mills or Town Centers to drop off food",
    ),
    "Burmese": (
        "Infantry +1/+2/+3 attack in Feudal/Castle/Imperial Age",
        "Manipur Cavalry (Cavalry +4 attack vs. Ranged Soldiers)",
        "Team Bonus: Relics visible on the map at the start of the game",
    ),
    "Vietnamese": (
        "Enemy Town Centers are revealed at the start of the game",
        "Archery Range units and Fire Lancers +20% HP",
        "Paper Money (Lumberjacks slowly generate gold in addition to wood)",
    ),
    "Bulgarians": (
        "Can build Krepost in Castle Age",
        "Stirrups (Cavalry attacks +33% faster)",
    ),
    "Cumans": ("Mounted Units move +5/10/15% faster in Feudal/Castle/Imperial Age",),
    "Burgundians": (
        "Gunpowder Units +25% attack",
        "Burgundian Vineyards (Farmers slowly generate gold in addition to food)",
        "Team Bonus: Relics generate food in addition to gold",
    ),
    "Poles": ("Stone Miners generate gold in addition to stone",),
    "Bohemians": ("Wagenburg Tactics (Gunpowder Units move +15% faster)",),
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
    "Armenians": ("Team Bonus: Infantry +2 line of sight",),
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
        "Military production buildings and Docks provide +55 food",
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
}

#: One line of build 185872's release notes (the Balance Changes section, fetched and read line by
#: line on 2026-10-28), the entities whose own data that line changes, and, for a "-line" note, the
#: tiers of the line. An entity is `(kind, identifier, name)`, the name checked against whichever
#: pack's `rules.json` has the entity.
#:
#: A line is a change to an entity only if it changes that entity's own data, or a bonus that
#: selects it. Read that way:
#:   - a "-line" note names every tier of the line, unless the note itself excludes one;
#:   - "(Elite)" before a unit, or "Elite" after its figures, puts the Elite unit in the entry;
#:     "(Elite unchanged)" leaves it out; a note that names a unit and says neither names the unit
#:     alone;
#:   - a note that changes a unit changes the unit, never the technology that upgrades to it, and a
#:     note that changes an upgrade's cost or time changes the technology, never the unit it makes;
#:   - a note that only grants or removes a civilisation's access to an entity changes none, and has
#:     no entry;
#:   - "Docks +5 garrison capacity civilization bonus removed" removes a Gurjaras bonus and does not
#:     change the Dock (building 45); the Vietnamese's and the Teutons' bonus rewords change unit
#:     bonuses and not buildings 87, 101 and 12: their entries are empty.
#: A row that selects one of the entities is not carried. The entities whose cost or time differs
#: between the two packs' `rules.json` are all here, but for the three the pack renames and two
#: units the notes name through their parents; a row selecting those is not carried either (the
#: carry test compares the data itself).
_Entity = tuple[str, str, str]


@dataclasses.dataclass(frozen=True)
class _Note:
    text: str
    entities: tuple[_Entity, ...]
    #: For a "-line" note, the line's tiers as written by hand from `rules.json`; empty otherwise.
    tiers: tuple[_Entity, ...] = ()


_RAMS: tuple[_Entity, ...] = (
    ("unit", "1258", "Battering Ram"),
    ("unit", "422", "Capped Ram"),
    ("unit", "548", "Siege Ram"),
)
_ARMORED_ELEPHANTS: tuple[_Entity, ...] = (
    ("unit", "1744", "Armored Elephant"),
    ("unit", "1746", "Siege Elephant"),
)
#: The note gives three values, 4/5/6 → 3/4/5, one for each of these three tiers.
_HULKS: tuple[_Entity, ...] = (
    ("unit", "2626", "Hulk"),
    ("unit", "2627", "War Hulk"),
    ("unit", "2628", "Carrack"),
)

_NOTES: tuple[_Note, ...] = (
    _Note(
        "Man-at-Arms bonus damage vs. Shock Infantry increased from +2 → +3.",
        (("unit", "75", "Man-at-Arms"),),
    ),
    _Note(
        "Long Swordsman bonus damage vs. Shock Infantry increased from +6 → +8.",
        (("unit", "77", "Long Swordsman"),),
    ),
    _Note(
        "Two-handed Swordsman bonus damage vs. Shock Infantry increased from +8 → +9.",
        (("unit", "473", "Two-Handed Swordsman"),),
    ),
    _Note(
        "Champion bonus damage vs. Shock Infantry increased from +8 → +9.",
        (("unit", "567", "Champion"),),
    ),
    _Note(
        "Eagle Scout train time reduced from 50 seconds → 46 seconds.",
        (("unit", "751", "Eagle Scout"),),
    ),
    _Note("Battering Ram-line line of sight increased from 3 → 5.", _RAMS, tiers=_RAMS),
    _Note(
        "Armored Elephant-line line of sight increased from 4 → 6.",
        _ARMORED_ELEPHANTS,
        tiers=_ARMORED_ELEPHANTS,
    ),
    _Note("Siege Tower line of sight reduced from 8 → 6.", (("unit", "1105", "Siege Tower"),)),
    _Note("Onager attack increased from 50 → 55.", (("unit", "550", "Onager"),)),
    _Note("Onager pierce armor increased from 7 → 8.", (("unit", "550", "Onager"),)),
    _Note(
        "Demolition Ship upgrade cost reduced from 50 wood 100 gold, 50 seconds → 25 wood 75 "
        "gold, 20 seconds.",
        (("technology", "905", "Demolition Ship"),),
    ),
    _Note("Hulk-line melee armor reduced from 4/5/6 → 3/4/5", _HULKS, tiers=_HULKS),
    _Note("Hulk HP reduced from 90 → 85.", (("unit", "2626", "Hulk"),)),
    _Note("War Hulk HP reduced from 115 → 110.", (("unit", "2627", "War Hulk"),)),
    _Note(
        "Lou Chuan bonus damage vs. Buildings reduced from +230 → +180.",
        (("unit", "1948", "Lou Chuan"),),
    ),
    _Note(
        "Fire Galley bonus damage vs. Buildings reduced from 1 → 0.",
        (("unit", "1103", "Fire Galley"),),
    ),
    _Note(
        "Fortified Church build time increased from 40 seconds → 50 seconds.",
        (("building", "1806", "Fortified Church"),),
    ),
    _Note(
        "Ratha train time increased from 20 seconds → 24 seconds (Elite unchanged).",
        (("unit", "1759", "Ratha"),),
    ),
    _Note(
        "(Elite) Hussite Wagon cost increased from 110 wood 70g → 110 wood 80 gold.",
        (("unit", "1704", "Hussite Wagon"), ("unit", "1706", "Elite Hussite Wagon")),
    ),
    _Note(
        "Wagenburg Tactics movement speed for Gunpowder Units effect reduced from 15% → 10%.",
        (("technology", "784", "Wagenburg Tactics"),),
    ),
    _Note(
        "Flemish Militia cost increased from 30 food 25 gold → 35 food 25 gold.",
        (("unit", "1699", "Flemish Militia"),),
    ),
    _Note(
        "Feudal Age Flemish Militia train time increased from 14 seconds → 16 seconds.",
        (("unit", "1699", "Flemish Militia"),),
    ),
    _Note(
        "(Elite) Cataphract bonus damage vs. Infantry increased from 9 → 13, Elite 12 → 18.",
        (("unit", "40", "Cataphract"), ("unit", "553", "Elite Cataphract")),
    ),
    _Note(
        "Logistica effect changed from Cataphracts deal trample damage, +6 vs. Infantry → "
        "Cataphracts and Varangian guards deal trample damage.",
        (("technology", "61", "Logistica"),),
    ),
    _Note(
        "(Elite) Throwing Axeman range increased from 3 → 5, Elite 4 → 6.",
        (("unit", "281", "Throwing Axeman"), ("unit", "531", "Elite Throwing Axeman")),
    ),
    _Note("Bearded Axe unique technology removed.", (("technology", "83", "Bearded Axe"),)),
    _Note(
        "NEW: Ordonnance Companies (Castle Age):",
        (("technology", "1496", "Ordonnance Companies"),),
    ),
    _Note("Docks +5 garrison capacity civilization bonus removed.", ()),
    _Note(
        "Atheism now applies Wonder and Relic victory timer increase only to enemy and neutral "
        "players.",
        (("technology", "21", "Atheism"),),
    ),
    _Note(
        "Atheism victory timer increase can now stack if the technology was researched more than "
        "once in the game.",
        (("technology", "21", "Atheism"),),
    ),
    _Note(
        "Atheism now applies the Relic income reduction effect also to the players neutral to the "
        "Hun player.",
        (("technology", "21", "Atheism"),),
    ),
    _Note(
        "Grenadier cost changed from 35 food 65 gold → 55 food 50 gold.",
        (("unit", "1911", "Grenadier"),),
    ),
    _Note(
        "Turtle Ship HP reduced from 275 → 260.",
        (("unit", "831", "Turtle Ship"),),
    ),
    _Note(
        "Magyar Huszar train time increased from 12 seconds → 18 seconds (Elite unchanged).",
        (("unit", "869", "Magyar Huszar"),),
    ),
    _Note(
        "(Elite) Bolas Rider cost increased from 45 wood 50 gold → 50 wood 55 gold.",
        (("unit", "2569", "Bolas Rider"), ("unit", "2571", "Elite Bolas Rider")),
    ),
    _Note(
        "Temple Guard attack reduced from 12 → 11 (Elite unchanged).",
        (("unit", "2586", "Temple Guard"),),
    ),
    _Note(
        "Organ Gun train time increased from 25 seconds → 28 seconds (Elite unchanged).",
        (("unit", "1001", "Organ Gun"),),
    ),
    _Note(
        "War Chariot cost increased from 65 food 90 gold → 75 food 90 gold.",
        (("unit", "1962", "War Chariot"),),
    ),
    _Note(
        "War Chariot train time increased from 28 → 32 seconds.",
        (("unit", "1962", "War Chariot"),),
    ),
    _Note(
        "(Elite) Conquistador cost increased from 70 food 60 gold → 75 food 60 gold.",
        (("unit", "771", "Conquistador"), ("unit", "773", "Elite Conquistador")),
    ),
    _Note(
        "Conquistador train time increased from 24 → 26 seconds (Elite unchanged).",
        (("unit", "771", "Conquistador"),),
    ),
    _Note(
        "Missionary cost increased from 100 gold → 30 food 100 gold.",
        (("unit", "775", "Missionary"),),
    ),
    _Note(
        "Stable and Barracks units +1/+2 melee armor in Castle/Imperial Age civilization bonus "
        "changed → Infantry and Mounted Units +1/+2 melee armor in Castle/Imperial Age.",
        (),
    ),
    _Note(
        "Elite Teutonic Knight melee armor reduced from 10 → 8 (unchanged with civilization "
        "bonus).",
        (("unit", "554", "Elite Teutonic Knight"),),
    ),
    _Note(
        "(Elite) Blackwood Archer cost increased from 35 wood 45 gold → 40 wood 45 gold.",
        (("unit", "2579", "Blackwood Archer"), ("unit", "2581", "Elite Blackwood Archer")),
    ),
    _Note(
        "Archery Range units and Fire Lancers +20% HP civilization bonus changed → Foot-Archers "
        "and Skirmishers +20% HP.",
        (),
    ),
    _Note(
        "(Elite) Rattan Archer base HP reduced from 40 → 35, Elite 45 → 40.",
        (("unit", "1129", "Rattan Archer"), ("unit", "1131", "Elite Rattan Archer")),
    ),
    _Note(
        "Elite Rattan upgrade reduced from 1000 food 750 gold → 800 food 750 gold",
        (("technology", "621", "Elite Rattan Archer"),),
    ),
    _Note(
        "Chieftains effect no longer generates gold when Infantry units defeat Villagers, Trade "
        "Units, and Monks.",
        (("technology", "463", "Chieftains"),),
    ),
    _Note(
        "Xianbei Raider cost increased from 65 wood 25 gold → 65 wood 35 gold.",
        (("unit", "1952", "Xianbei Raider"),),
    ),
)

#: What the notes' entries name, as the carry rule reads it.
_NAMED_BY_THE_NOTES: frozenset[tuple[str, str]] = frozenset(
    (kind, identifier) for note in _NOTES for kind, identifier, _ in note.entities
)


# ---------------------------------------------------------------------------------- the readers


def _pack_root(pack: str = _PACK) -> resources.abc.Traversable:
    return resources.files(_PACKAGE).joinpath("packs").joinpath(pack)


def _snapshot_root(directory: str = _DIRECTORY) -> resources.abc.Traversable:
    return resources.files(_PACKAGE).joinpath("snapshots").joinpath(directory)


@functools.cache
def _strings(pack: str) -> Mapping[str, str]:
    return json.loads(_pack_root(pack).joinpath("strings.en.json").read_text(encoding="utf-8"))


@functools.cache
def _rules(directory: str = _DIRECTORY) -> dict[str, dict[str, dict[str, object]]]:
    parsed: dict[str, dict[str, dict[str, object]]] = json.loads(
        _snapshot_root(directory).joinpath("rules.json").read_text(encoding="utf-8")
    )["entities"]
    return parsed


def _entity_name(directory: str, kind: str, entity_id: str) -> str:
    return re.sub(r"\s*<br>\s*", " ", str(_rules(directory)[kind][entity_id]["name"] or ""))


@functools.cache
def _toml(directory: str, name: str) -> dict[str, list[dict[str, object]]]:
    return tomllib.loads(_snapshot_root(directory).joinpath(name).read_text(encoding="utf-8"))


def _rows(directory: str = _DIRECTORY) -> list[dict[str, object]]:
    return _toml(directory, "effects.toml")["effect"]


def _bullets_for(pack: str, help_string_id: str) -> tuple[str, ...]:
    """Every bonus bullet of one civilisation's string, as `test_bullet_coverage.py` reads them:
    each top-level and "Unique Techs:" bullet (a mid-bullet line break rejoined) and the one line
    after "Team Bonus:", prefixed with that label. The unique units' names are not bonuses."""
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


def _refs(row: Mapping[str, object]) -> list[tuple[str, str]]:
    """Every entity a row selects or conditions on."""
    found = [(s["kind"], s["id"]) for s in row["selector"]]  # type: ignore[index, attr-defined]
    found += [(s["kind"], s["id"]) for s in row.get("condition_entities", [])]  # type: ignore[attr-defined, index]
    if row.get("condition_technology"):
        found.append(("technology", str(row["condition_technology"])))
    return found


def _at(directory: str, kind: str, building: str) -> frozenset[str]:
    return frozenset(
        i
        for i, rec in _rules(directory)[kind].items()
        if (rec.get("produced_at") or {}).get("id") == building  # type: ignore[attr-defined]
    )


def _data_differs(kind: str, entity_id: str) -> bool:
    """Whether the two packs' `rules.json` disagree on an entity both name (name, age, cost, time,
    producing building)."""
    here = _rules()[kind].get(entity_id)
    there = _rules(_SOURCE_DIRECTORY)[kind].get(entity_id)
    return here is not None and there is not None and here != there


@dataclasses.dataclass(frozen=True)
class _Failures:
    """What stops one row of the source snapshot from being carried, recomputed from both packs."""

    string_differs: bool
    absent: tuple[tuple[str, str], ...]
    renamed: tuple[tuple[str, str], ...]
    classes: tuple[tuple[str, str], ...]
    named: tuple[tuple[str, str], ...]
    differing: tuple[tuple[str, str], ...]

    @property
    def conditions(self) -> dict[str, bool]:
        return {
            "bullet is byte-identical": not self.string_differs,
            "identifiers resolve to the same": not (self.absent or self.renamed or self.classes),
            "release notes name no change": not (self.named or self.differing),
        }

    @property
    def carried(self) -> bool:
        return all(self.conditions.values())

    @property
    def ids(self) -> set[tuple[str, str]]:
        return set(self.absent) | set(self.renamed) | set(self.named) | set(self.differing)


def _row_failures(row: Mapping[str, object]) -> _Failures:
    """The three conditions of the carry rule for one row of the source snapshot, recomputed from
    both packs' strings and `rules.json` and from the notes set. Never read from the snapshot under
    test."""
    civilisation = str(row["civilisation"])
    text = str(row["source_text"])
    key = _HELP_STRING_ID[civilisation]
    string_differs = not (
        text in _bullets_for(_PACK, key) and text in _bullets_for(_OTHER_PACK, key)
    )
    refs = sorted(set(_refs(row)))
    absent = tuple((k, i) for k, i in refs if i not in _rules()[k])
    present = [(k, i) for k, i in refs if i in _rules()[k]]
    renamed = tuple(
        (k, i)
        for k, i in present
        if _entity_name(_DIRECTORY, k, i) != _entity_name(_SOURCE_DIRECTORY, k, i)
    )
    differing = tuple((k, i) for k, i in present if _data_differs(k, i))
    named = tuple((k, i) for k, i in present if (k, i) in _NAMED_BY_THE_NOTES)
    selected = {kind: {i for k, i in refs if k == kind} for kind in _rules()}
    changed_classes: set[tuple[str, str]] = set()
    for kind in _rules():
        buildings = {
            (_rules(_SOURCE_DIRECTORY)[kind].get(i, {}).get("produced_at") or {}).get("id")  # type: ignore[attr-defined]
            for i in selected[kind]
        } - {None}
        for building in buildings:
            whole = _at(_SOURCE_DIRECTORY, kind, str(building))
            if whole and whole <= selected[kind] and whole != _at(_DIRECTORY, kind, str(building)):
                changed_classes.add((kind, str(building)))
    return _Failures(
        string_differs=string_differs,
        absent=absent,
        renamed=renamed,
        classes=tuple(sorted(changed_classes)),
        named=named,
        differing=differing,
    )


def _pairs() -> list[tuple[dict[str, object], dict[str, object] | None]]:
    """Every row of the source snapshot whose civilisation this pack has, with the row of this
    snapshot that answers it (the same bullet under the text this pack gives it, the same position
    in the group), or `None` where this snapshot has no row for the bullet."""
    here = _groups(_rows())
    own_text = {(c, theirs): own for (c, own), theirs in _REWORDED.items()}
    pairs: list[tuple[dict[str, object], dict[str, object] | None]] = []
    for (civilisation, text), group in _groups(_rows(_SOURCE_DIRECTORY)).items():
        if civilisation in _NOT_IN_THIS_PACK:
            continue
        mine = here.get((civilisation, own_text.get((civilisation, text), text)), [])
        assert not mine or len(mine) == len(group), (civilisation, text)
        for position, row in enumerate(group):
            pairs.append((row, mine[position] if mine else None))
    return pairs


def _groups(rows: list[dict[str, object]]) -> dict[tuple[str, str], list[dict[str, object]]]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault((str(row["civilisation"]), str(row["source_text"])), []).append(row)
    return grouped


def _carried(row: Mapping[str, object]) -> bool:
    return _CARRIED_MARK in str(row["validated_by"])


def _transcribed(row: Mapping[str, object]) -> bool:
    return _NOT_CARRIED_MARK in str(row["validated_by"])


#: The three bullets of the build 180059 pack the build 185872 pack words differently, by the key
#: the transcribed row follows: this pack's text -> the other pack's.
_REWORDED = {
    (
        "Byzantines",
        "Logistica (Cataphracts deal trample damage, +6 attack vs. Infantry)",
    ): "Logistica (Cataphracts and Varangian Guards deal trample damage)",
    (
        "Mapuche",
        "Malon (Bolas Riders, Slingers and Skirmishers deal pass through damage)",
    ): "Malon (Bolas Riders, Slingers, and Skirmishers deal pass through damage)",
    (
        "Vikings",
        "Bogsveigar (Archer-line and Longboats +1 attack)",
    ): "Bogsveigar (Archer-line and Longships +1 attack)",
}

#: Two rows of the first snapshot of this build, carried byte for byte: bullets this pack has and
#: the build 185872 pack does not.
_FROM_THE_FIRST_SNAPSHOT = (
    ("Franks", "Bearded Axe (Throwing Axemen +2 range)"),
    ("Teutons", "Barracks and Stable Units +1/+2 melee armor in Castle/Imperial Age"),
)

#: The one row no earlier snapshot has: the build 185872 notes remove this bonus from the Gurjaras.
_NEW_ROW = ("Gurjaras", "Docks +5 garrison capacity")

#: Rows by fate, set by `_row_failures` (the data under test is not consulted).
CARRIED_ROWS = 232
TRANSCRIBED_ROWS = 63


# ----------------------------------------------------------------------- nothing is dropped


def test_every_registry_entry_is_a_real_bullet_of_this_pack() -> None:
    for civilisation, entries in _NO_ROW_BULLETS.items():
        bullets = _bullets_for(_PACK, _HELP_STRING_ID[civilisation])
        for entry in entries:
            assert entry in bullets, f"{civilisation}: {entry!r} is not a bullet"


def test_every_bullet_is_a_row_or_a_registry_entry_exactly_once() -> None:
    for civilisation, key in _HELP_STRING_ID.items():
        bullets = _bullets_for(_PACK, key)
        row_texts = {row["source_text"] for row in _rows() if row["civilisation"] == civilisation}
        registered = set(_NO_ROW_BULLETS.get(civilisation, ()))
        assert not row_texts & registered, f"{civilisation}: both a row and a registry entry"
        assert set(bullets) - (row_texts | registered) == set(), f"{civilisation}: dropped"
        assert (row_texts | registered) - set(bullets) == set(), f"{civilisation}: invented"
        assert len(row_texts | registered) == len(bullets)


def test_the_bullets_of_the_fifty_three_civilisations_number_three_hundred_and_seventy_three() -> (
    None
):
    """A guard on the reader: a changed pack string that silently shifted the count would move every
    assertion above together."""
    assert sum(len(_bullets_for(_PACK, key)) for key in _HELP_STRING_ID.values()) == 373
    assert sum(len(entries) for entries in _NO_ROW_BULLETS.values()) == 121
    assert len({(r["civilisation"], r["source_text"]) for r in _rows()}) == 252


def test_the_bullets_with_no_row_are_the_build_185872_registries_but_four() -> None:
    """A bullet with no row here has no row in the build 185872 snapshot either, unless this pack
    words it differently: then it is one of four, each a bullet that field-wise touches nothing the
    knowledge base carries."""
    source_texts = {(r["civilisation"], r["source_text"]) for r in _rows(_SOURCE_DIRECTORY)}
    reworded = {
        ("Bohemians", "Wagenburg Tactics (Gunpowder Units move +15% faster)"),
        ("Vietnamese", "Archery Range units and Fire Lancers +20% HP"),
        (
            "Vikings",
            "Chieftains (Infantry +5 attack vs. Cavalry, +4 vs. Camel Units; generate +5 gold when "
            "defeating Villagers, Trade Units and Monks)",
        ),
        ("Wu", "Military production buildings and Docks provide +55 food"),
    }
    for civilisation, entries in _NO_ROW_BULLETS.items():
        other = set(_bullets_for(_OTHER_PACK, _HELP_STRING_ID[civilisation]))
        for entry in entries:
            if (civilisation, entry) in reworded:
                assert entry not in other
            else:
                assert entry in other, (civilisation, entry)
                assert (civilisation, entry) not in source_texts, (civilisation, entry)
    assert reworded <= {(c, e) for c, es in _NO_ROW_BULLETS.items() for e in es}


# ----------------------------------------------------------------------- nothing dangles


def test_every_row_carries_the_packs_own_key_and_a_bullet_of_its_own_civilisation() -> None:
    for row in _rows():
        civilisation = str(row["civilisation"])
        assert civilisation in _HELP_STRING_ID
        assert row["source_key"] == _HELP_STRING_ID[civilisation]
        assert row["source_text"] in _bullets_for(_PACK, str(row["source_key"])), row["source_text"]


def test_every_selector_and_condition_entity_exists_in_this_snapshots_rules() -> None:
    for row in _rows():
        assert row["selector"], (row["civilisation"], row["source_text"])
        for kind, identifier in _refs(row):
            assert identifier in _rules()[kind], (
                row["civilisation"],
                row["source_text"],
                kind,
                identifier,
            )


def test_civilisations_modelled_is_the_whole_pack_and_the_set_the_effects_name() -> None:
    text = _snapshot_root().joinpath("snapshot.toml").read_text(encoding="utf-8")
    modelled = set(tomllib.loads(text)["snapshot"]["civilisations_modelled"])
    pack = set(query._rules(_DIRECTORY)["civilisations"])
    named = {str(row["civilisation"]) for row in _rows()}
    assert modelled == pack == set(_HELP_STRING_ID) == named
    assert len(modelled) == 53
    assert not modelled & set(_NOT_IN_THIS_PACK)


def test_the_raw_id_table_is_the_source_snapshots_for_the_fifty_three_and_names_each_once() -> None:
    here = _toml(_DIRECTORY, "effects.toml")["civilisation_id"]
    there = _toml(_SOURCE_DIRECTORY, "effects.toml")["civilisation_id"]
    assert [(e["raw_id"], e["civilisation"]) for e in here] == [
        (e["raw_id"], e["civilisation"])
        for e in there
        if e["civilisation"] not in _NOT_IN_THIS_PACK
    ]
    assert len({e["civilisation"] for e in here}) == 53
    assert {e["civilisation"] for e in here} == set(_HELP_STRING_ID)
    for entry in here:
        assert "9ee0fe29fa05f176575ce6e3befd21a116d27e12" in str(entry["validated_by"])


# ----------------------------------------------------------------------- the derivation


def test_rules_json_and_disagreements_are_what_the_normaliser_derives_from_this_pack() -> None:
    pack = normalise.normalise_pack(_PACK, version=2)
    assert _snapshot_root().joinpath("rules.json").read_bytes() == normalise.rules_json_bytes(pack)
    assert _snapshot_root().joinpath("disagreements.toml").read_text(
        encoding="utf-8"
    ) == normalise.disagreements_toml_text(pack.disagreements)


def test_the_snapshot_names_this_packs_commit_and_the_first_snapshots_digest() -> None:
    loaded = snapshot.load_snapshot(_DIRECTORY)
    manifest = json.loads(_pack_root().joinpath("MANIFEST.json").read_text(encoding="utf-8"))
    assert loaded.identity.source_version == manifest["commit"]
    assert loaded.identity.describes_build == _BUILD
    assert loaded.normaliser_version == 2
    assert loaded.promoted
    assert loaded.supersedes == _FIRST_DIGEST
    assert loaded.validation is not None
    assert "9ee0fe29fa05f176575ce6e3befd21a116d27e12" in loaded.validation.checked_against
    assert "185872" in loaded.validation.checked_against
    assert "not independent validation" in str(loaded.validation.details["not_checked"])
    assert "no notes read here" in str(loaded.validation.details["not_checked"])


# ----------------------------------------------------------------------- the carry rule


def test_a_row_is_carried_exactly_when_the_three_conditions_hold_for_that_row() -> None:
    """The rule is decided row by row, never bonus by bonus: every row of the source snapshot whose
    civilisation this pack has is carried here if and only if the bullet is byte-identical, every
    identifier it selects resolves to the same identifier, and none of them is one the notes name or
    one whose data differs. The decision is recomputed from both packs and the notes set."""
    carried = transcribed = 0
    for source, mine in _pairs():
        failures = _row_failures(source)
        label = (source["civilisation"], source["source_text"], source["field"])
        if mine is None:
            # Dropped: the bullet is not in this pack (Franks' Ordonnance Companies).
            assert failures.string_differs, label
            continue
        assert _carried(mine) != _transcribed(mine), label
        assert _carried(mine) == failures.carried, (label, failures)
        carried += failures.carried
        transcribed += not failures.carried
    assert (carried, transcribed) == (CARRIED_ROWS, TRANSCRIBED_ROWS)
    # The reworded bullets are transcribed under the text this pack gives.
    for (civilisation, own), theirs in _REWORDED.items():
        assert (civilisation, theirs) in {
            (r["civilisation"], r["source_text"]) for r in _rows(_SOURCE_DIRECTORY)
        }
        assert all(
            _transcribed(r) and _row_failures(source).string_differs
            for source, r in _pairs()
            if r is not None and r["civilisation"] == civilisation and r["source_text"] == own
        )


def test_a_bonus_with_one_passing_and_one_failing_row_has_one_carried_and_one_transcribed() -> None:
    """The contrast case: the decision is not the bonus's. Wherever the rows of one bullet differ in
    what they select, they differ in their fate too, and the row that passes alone is carried."""
    mixed = []
    for (civilisation, text), group in _groups(_rows(_SOURCE_DIRECTORY)).items():
        if civilisation in _NOT_IN_THIS_PACK:
            continue
        decisions = [_row_failures(row).carried for row in group]
        if any(decisions) and not all(decisions):
            fates = [_carried(r) for r in _groups(_rows())[(civilisation, text)]]
            assert fates == decisions, (civilisation, text)
            mixed.append((civilisation, text))
    assert mixed, "no bonus has a passing and a failing row"
    # The Chinese's Age-advance discount: the open row selects technologies 102 and 103 alone and
    # is carried, while the same bullet's other rows select classes the packs define differently.
    chinese = [
        r
        for r in _rows()
        if r["civilisation"] == "Chinese"
        and r["source_text"] == "Technologies cost -5/10/15% in Feudal/Castle/Imperial Age"
    ]
    assert [(_carried(r), r["selector"]) for r in chinese if r["modelled"] == "no"] == [
        (True, [{"kind": "technology", "id": "102"}, {"kind": "technology", "id": "103"}])
    ]
    assert any(not _carried(r) for r in chinese)


def test_the_rows_are_carried_transcribed_old_or_new_and_nothing_else() -> None:
    counts = {"carried": 0, "transcribed": 0, "first snapshot": 0, "new": 0}
    for row in _rows():
        own = (str(row["civilisation"]), str(row["source_text"]))
        if _carried(row):
            counts["carried"] += 1
        elif _transcribed(row):
            counts["transcribed"] += 1
        elif own in _FROM_THE_FIRST_SNAPSHOT:
            counts["first snapshot"] += 1
        else:
            assert own == _NEW_ROW, own
            counts["new"] += 1
    assert counts == {
        "carried": CARRIED_ROWS,
        "transcribed": TRANSCRIBED_ROWS,
        "first snapshot": 2,
        "new": 1,
    }


def test_every_carried_row_is_the_source_row_with_its_reading_kept_and_the_digest_named() -> None:
    for source, mine in _pairs():
        if mine is None or not _carried(mine):
            continue
        assert {k: v for k, v in mine.items() if k != "validated_by"} == {
            k: v for k, v in source.items() if k != "validated_by"
        }
        assert str(mine["validated_by"]).startswith(str(source["validated_by"]))
        assert _SOURCE_DIGEST in str(mine["validated_by"])
        assert "byte-identical" in str(mine["validated_by"])


def test_every_transcribed_row_keeps_the_figures_and_the_selector_re_resolved_for_this_pack() -> (
    None
):
    for source, mine in _pairs():
        if mine is None or not _transcribed(mine):
            continue
        label = (mine["civilisation"], mine["source_text"], mine["field"])
        for field in ("modelled", "field", "operation", "operand", "condition", "reason"):
            assert mine.get(field) == source.get(field), (label, field)
        assert mine.get("condition_entities") == source.get("condition_entities")
        assert mine.get("condition_technology") == source.get("condition_technology")
        pack_ids = {
            (s["kind"], s["id"]) for s in source["selector"] if s["id"] in _rules()[s["kind"]]
        }  # type: ignore[attr-defined, index]
        mine_ids = {(s["kind"], s["id"]) for s in mine["selector"]}  # type: ignore[attr-defined, index]
        assert pack_ids <= mine_ids, label
        # The one entity only this pack has is the Franks' Bearded Axe, in a class that takes
        # every technology the Castle produces or every technology but the age advances.
        assert mine_ids - pack_ids <= {("technology", "83")}, label
        assert _SOURCE_DIGEST in str(mine["validated_by"])


#: What a transcribed row's reason must say for each way its source row fails the carry rule, and
#: nothing it does not fail.
_REASON_MARKS = {
    "string_differs": "the bullet's string differs between the two packs",
    "absent": "absent from this pack's rules.json",
    "renamed": "is named differently in this pack",
    "classes": "produces there are not the same set",
    "named": "release notes name",
    "differing": "this pack's rules.json differs from build 185872's",
}
_ID_CITATION = re.compile(r"\b(unit|technology|building) (\d+)\b")


def _reason(validated_by: object) -> str:
    """The part of a transcribed row's `validated_by` that gives the reason it was not carried."""
    text = str(validated_by)
    start = text.index("Not carried from the build 185872 snapshot")
    return text[start : text.index("Every identifier the row selects that is not named above")]


def test_every_transcribed_row_names_its_own_failure_and_only_ids_the_row_selects() -> None:
    """The reason is the row's own, not its sibling rows': each way the row fails the rule is
    stated, no way it passes is, and every identifier cited is one the build 185872 row selects or
    conditions on (and, where this pack has it, one this row selects or conditions on too)."""
    checked = 0
    for source, mine in _pairs():
        if mine is None or not _transcribed(mine):
            continue
        checked += 1
        label = (mine["civilisation"], mine["source_text"], mine["field"])
        failures = _row_failures(source)
        assert not failures.carried, label
        reason = _reason(mine["validated_by"])
        for name, mark in _REASON_MARKS.items():
            stated = mark in reason
            failed = bool(getattr(failures, name))
            assert stated == failed, (label, name, reason)
        cited = {(k, i) for k, i in _ID_CITATION.findall(reason)}
        assert failures.ids <= cited, (label, failures.ids - cited)
        # Nothing is cited that is not a failure of this row: a note that names a neighbour of a
        # selected entity (its upgrade, its Elite unit) is not a reason to cite the entity.
        assert cited == failures.ids, (label, cited - failures.ids)
        assert cited <= set(_refs(source)) | set(_refs(mine)), (label, cited)
        for kind, identifier in cited:
            if identifier in _rules()[kind]:
                assert (kind, identifier) in _refs(mine), (label, kind, identifier)
    assert checked == TRANSCRIBED_ROWS


def test_the_two_rows_of_the_first_snapshot_are_carried_byte_for_byte() -> None:
    first = _groups(_rows(_FIRST_DIRECTORY))
    here = _groups(_rows())
    for own in _FROM_THE_FIRST_SNAPSHOT:
        assert own in here and own not in {
            (r["civilisation"], r["source_text"]) for r in _rows(_SOURCE_DIRECTORY)
        }
        for mine, theirs in zip(here[own], first[own], strict=True):
            assert {k: v for k, v in mine.items() if k != "validated_by"} == {
                k: v for k, v in theirs.items() if k != "validated_by"
            }
            assert str(mine["validated_by"]).startswith(str(theirs["validated_by"]))
            assert _FIRST_DIGEST in str(mine["validated_by"])


def test_no_row_of_a_civilisation_outside_this_pack_is_here() -> None:
    assert not {r["civilisation"] for r in _rows()} & set(_NOT_IN_THIS_PACK)
    for name in _NOT_IN_THIS_PACK:
        result = query.cost(_entity("building", 84), civilisation=name)
        assert isinstance(result, gaps.KnowledgeGap)
        assert result.cause == "civilisation-not-modelled"


def test_the_notes_set_contains_every_entity_whose_data_differs_between_the_packs() -> None:
    differing = {
        (kind, identifier)
        for kind in _rules()
        for identifier in _rules()[kind]
        if identifier in _rules(_SOURCE_DIRECTORY)[kind] and _data_differs(kind, identifier)
    }
    renamed_only = {("technology", "372"), ("unit", "250"), ("unit", "533")}
    assert len(differing) == 25
    assert differing - _NAMED_BY_THE_NOTES == renamed_only | {("unit", "1738"), ("unit", "1980")}


def _pack_entity_name(kind: str, identifier: str) -> str | None:
    """The name either pack's `rules.json` gives an entity, or `None` where neither has it."""
    for directory in (_DIRECTORY, _SOURCE_DIRECTORY):
        if identifier in _rules(directory)[kind]:
            return _entity_name(directory, kind, identifier).strip()
    return None


def test_every_entity_of_the_notes_table_is_a_real_entity_under_the_name_the_table_gives() -> None:
    for note in _NOTES:
        for kind, identifier, name in note.entities:
            assert _pack_entity_name(kind, identifier) == name, (note.text, kind, identifier)
    assert len({note.text for note in _NOTES}) == len(_NOTES)


def test_the_notes_that_change_no_entity_are_the_three_that_only_change_a_bonus_or_a_grant() -> (
    None
):
    assert [note.text for note in _NOTES if not note.entities] == [
        "Docks +5 garrison capacity civilization bonus removed.",
        "Stable and Barracks units +1/+2 melee armor in Castle/Imperial Age civilization bonus "
        "changed → Infantry and Mounted Units +1/+2 melee armor in Castle/Imperial Age.",
        "Archery Range units and Fire Lancers +20% HP civilization bonus changed → Foot-Archers "
        "and Skirmishers +20% HP.",
    ]


def test_every_line_note_names_every_tier_of_its_line() -> None:
    """A "-line" note changes every tier of the line, unless the note itself excludes one. The
    tiers are written by hand beside the entry, never found by name, and each is a real entity of
    a pack; the entry includes all of them. The Hulk-line note gives three values, one for each of
    the three tiers listed."""
    line_notes = [note for note in _NOTES if re.search(r"-line\b", note.text)]
    assert {note.text.split(" ")[0] for note in line_notes} == {"Battering", "Armored", "Hulk-line"}
    for note in _NOTES:
        assert bool(note.tiers) == (note in line_notes), note.text
    for note in line_notes:
        assert len(note.tiers) >= 2, note.text
        assert set(note.tiers) <= set(note.entities), note.text
        for kind, identifier, name in note.tiers:
            assert _pack_entity_name(kind, identifier) == name, (note.text, identifier)
            assert (kind, identifier) in _NAMED_BY_THE_NOTES, (note.text, identifier)
    by_text = {note.text.split(" ")[0]: note for note in line_notes}
    assert {i for _, i, _ in by_text["Battering"].tiers} == {"1258", "422", "548"}
    assert {i for _, i, _ in by_text["Armored"].tiers} == {"1744", "1746"}
    hulks = by_text["Hulk-line"]
    values = re.search(r"(\d+(?:/\d+)+) →", hulks.text)
    assert values is not None
    assert len(values.group(1).split("/")) == len(hulks.tiers) == 3
    assert {i for _, i, _ in hulks.tiers} == {"2626", "2627", "2628"}


def test_an_entity_named_only_as_an_upgrade_target_or_as_unchanged_is_not_in_the_set() -> None:
    """The contrast case: each pair is an entity a note names beside the entity it changes. The
    first is not in the set, the second is. Unit 527 is the unit the Demolition Ship upgrade (905)
    makes; technology 257 upgrades to the Onager (550) whose stats change; the militia upgrades
    (207, 217, 222, 264) are the technologies whose units (77, 473, 75, 567) deal more bonus
    damage; units 1003, 1761, 871, 2587 are Elite units a note says are unchanged; the other
    technologies are the upgrades of units whose stats or costs change, and none of the notes
    changes the upgrade itself (technology 621 and 905 are the two it does)."""
    contrast = {
        ("unit", "527"): ("technology", "905"),
        ("technology", "257"): ("unit", "550"),
        ("technology", "207"): ("unit", "77"),
        ("technology", "217"): ("unit", "473"),
        ("technology", "222"): ("unit", "75"),
        ("technology", "264"): ("unit", "567"),
        ("unit", "1003"): ("unit", "1001"),
        ("unit", "1761"): ("unit", "1759"),
        ("unit", "871"): ("unit", "869"),
        ("unit", "2587"): ("unit", "2586"),
        ("unit", "25"): ("unit", "554"),
        ("technology", "34"): ("unit", "2627"),
        ("technology", "361"): ("unit", "553"),
        ("technology", "363"): ("unit", "531"),
        ("technology", "364"): ("unit", "554"),
        ("technology", "448"): ("unit", "831"),
        ("technology", "472"): ("unit", "869"),
        ("technology", "563"): ("unit", "1001"),
        ("technology", "60"): ("unit", "773"),
        ("technology", "781"): ("unit", "1706"),
        ("technology", "828"): ("unit", "1759"),
        ("technology", "1378"): ("unit", "2571"),
        ("technology", "1389"): ("unit", "2581"),
        ("technology", "1401"): ("unit", "2586"),
        ("unit", "832"): ("unit", "831"),
    }
    for unchanged, changed in contrast.items():
        assert unchanged not in _NAMED_BY_THE_NOTES, unchanged
        assert changed in _NAMED_BY_THE_NOTES, changed
    for changed_technology in (("technology", "905"), ("technology", "621")):
        assert changed_technology in _NAMED_BY_THE_NOTES
    # The bonus technologies whose own effect a note rewrites are in.
    for kind_and_id in (("technology", i) for i in ("21", "61", "463", "784")):
        assert kind_and_id in _NAMED_BY_THE_NOTES


# ----------------------------------------------------------------------- the aliases


def test_the_second_committed_recordings_two_unnamed_buildings_are_the_gate() -> None:
    loaded = snapshot.load_snapshot(_DIRECTORY)
    assert len(loaded.aliases) == 71
    for identifier in ("490", "673"):
        assert identifier not in _rules()["building"]
        alias = loaded.alias_for("building", identifier)
        assert alias is not None
        assert alias.source_name == "Gate"
        assert _entity_name(_DIRECTORY, "building", alias.target) == "Gate"
    for alias in loaded.aliases:
        assert _entity_name(_DIRECTORY, alias.kind, alias.target) == re.sub(
            r"\s*\((up|down|hori|vert)\.\)$", "", alias.source_name
        )


# ----------------------------------------------------------------------- resolution


def test_the_build_resolves_to_the_second_snapshot_and_the_first_reproduces_by_identity() -> None:
    resolved = snapshot.snapshot_for(_BUILD)
    assert isinstance(resolved, snapshot.Snapshot)
    assert resolved.directory == _DIRECTORY
    assert resolved.supersedes == _FIRST_DIGEST

    first = snapshot.load_snapshot(_FIRST_DIRECTORY)
    assert first.identity.digest == _FIRST_DIGEST
    assert first.promoted
    assert first.aliases == ()
    first_text = _snapshot_root(_FIRST_DIRECTORY).joinpath("snapshot.toml").read_text("utf-8")
    assert set(tomllib.loads(first_text)["snapshot"]["civilisations_modelled"]) == {
        "Franks",
        "Teutons",
        "Persians",
        "Saracens",
        "Malians",
        "Tatars",
    }
    entity = query.EntityRef(kind="building", id="84", build=_BUILD)
    with snapshot.pinned_snapshot(first):
        modelled = query.cost(entity, civilisation="Saracens")
        unmodelled = query.cost(entity, civilisation="Vietnamese")
    assert not isinstance(modelled, gaps.KnowledgeGap), f"gap: {modelled!r}"
    assert modelled.snapshot_identity.digest == _FIRST_DIGEST
    assert isinstance(unmodelled, gaps.KnowledgeGap)
    assert unmodelled.cause == "civilisation-not-modelled"
    # The same query under the current snapshot is answered, by the second.
    now = query.cost(entity, civilisation="Vietnamese")
    assert not isinstance(now, gaps.KnowledgeGap), f"gap: {now!r}"
    assert now.snapshot_identity.digest == resolved.identity.digest


# ----------------------------------------------------------------------- the values


def _entity(kind: str, entity_id: int | str) -> query.EntityRef:
    return query.EntityRef(kind=kind, id=str(entity_id), build=_BUILD)


def _value(result: object) -> object:
    assert not isinstance(result, gaps.KnowledgeGap), f"gap: {result!r}"
    return result.value  # type: ignore[attr-defined]


def _baseline(kind: str, entity_id: int | str, key: str) -> object:
    return _rules()[kind][str(entity_id)][key]


def _half_up(value: float) -> int:
    return int(value + 0.5)


def test_a_carried_bonus_answers_as_the_strings_say() -> None:
    """Britons' Town Centers cost -50% wood starting in Castle Age: carried, so the answer is the
    source snapshot's, applied to this pack's own baseline."""
    town_center = _entity("building", 109)
    base = _baseline("building", 109, "cost")
    castle = effects.Context(age=3)
    feudal = effects.Context(age=2)
    got = _value(query.cost(town_center, civilisation="Britons", context=castle))
    assert got == {**base, "wood": _half_up(base["wood"] * 0.5)}  # type: ignore[index, operator]
    assert _value(query.cost(town_center, civilisation="Britons", context=feudal)) == base
    assert _value(query.cost(town_center, civilisation="Franks")) == base
    with pytest.raises(effects.ContextRequired):
        query.cost(town_center, civilisation="Britons")


def test_a_transcribed_class_is_this_packs_class_not_the_other_packs() -> None:
    """Portuguese units cost -20% gold, transcribed: every unit this pack names, and not the
    Mounted Crossbowmen (2700, 2701), which only the build 185872 pack names."""
    for unit in ("4", "250", "38"):
        base = _baseline("unit", unit, "cost")
        got = _value(query.cost(_entity("unit", unit), civilisation="Portuguese"))
        expected = {k: (_half_up(v * 0.8) if k == "gold" else v) for k, v in base.items()}  # type: ignore[attr-defined]
        assert got == expected, unit
    assert "2700" not in _rules()["unit"]
    absent = query.cost(_entity("unit", 2700), civilisation="Portuguese")
    assert isinstance(absent, gaps.KnowledgeGap)
    assert absent.cause == "entity-absent"
    assert _value(query.cost(_entity("unit", "4"), civilisation="Franks")) == _baseline(
        "unit", "4", "cost"
    )


def test_the_vikings_warships_discount_reaches_the_longboat_under_its_name_in_this_pack() -> None:
    assert _entity_name(_DIRECTORY, "unit", "250") == "Longboat"
    base = _baseline("unit", 250, "cost")
    feudal = effects.Context(age=2)
    got = _value(query.cost(_entity("unit", 250), civilisation="Vikings", context=feudal))
    assert got != base
    assert all(got[k] <= base[k] for k in base)  # type: ignore[index, attr-defined]
    assert _value(query.cost(_entity("unit", 250), civilisation="Franks")) == base


def test_the_bearded_axe_is_in_the_classes_that_take_every_castle_technology() -> None:
    """Technology 83 exists in this pack only (the build 185872 pack removed it), produced at the
    Castle: the Chinese's discount on technologies and the Berbers' Kasbah take it, as the
    source snapshot's rows take the Franks' Ordonnance Companies, which replaced it."""
    assert "83" in _at(_DIRECTORY, "technology", "82")
    base = _baseline("technology", 83, "cost")
    got = _value(
        query.cost(
            _entity("technology", 83), civilisation="Chinese", context=effects.Context(age=2)
        )
    )
    assert got == {k: _half_up(v * 0.95) for k, v in base.items()}  # type: ignore[attr-defined]
    team = frozenset({"Berbers", "Franks"})
    done = effects.Context(team=team, team_researched=frozenset({"578"}))
    time_base = _baseline("technology", 83, "research_time")
    assert _value(
        query.production_time(_entity("technology", 83), civilisation="Franks", context=done)
    ) == pytest.approx(time_base / 1.25)  # type: ignore[operator]


def test_the_gurjaras_docks_bonus_is_a_refused_field_with_a_stated_reason() -> None:
    rows = [r for r in _rows() if (r["civilisation"], r["source_text"]) == _NEW_ROW]
    assert len(rows) == 1
    assert rows[0]["modelled"] == "no"
    assert rows[0]["field"] == "garrison_capacity"
    assert rows[0]["selector"] == [{"kind": "building", "id": "45"}]
    assert len(str(rows[0]["reason"])) > 40


def test_the_persians_kamandaran_is_the_carried_total_not_the_first_snapshots_refusal() -> None:
    """The first snapshot refused the Kamandaran for want of an amount; the source snapshot reads
    it as a total of 50 wood, flagged as unvalidated, and the carry rule holds for it."""
    group = [
        r
        for r in _rows()
        if r["civilisation"] == "Persians" and str(r["source_text"]).startswith("Kamandaran")
    ]
    assert group
    assert all(_carried(r) for r in group)
    assert all(r["modelled"] == "yes" for r in group)
    first = [
        r
        for r in _rows(_FIRST_DIRECTORY)
        if r["civilisation"] == "Persians" and str(r["source_text"]).startswith("Kamandaran")
    ]
    assert first
    assert all(r["modelled"] == "no" for r in first)
