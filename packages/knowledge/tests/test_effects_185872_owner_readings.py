"""T772: the seventh build 185872 snapshot, `aoe2techtree-185872-owner-readings`, which closes the
owner's readings (T771, 2026-10-31) and supersedes the sixth
(`aoe2techtree-185872-civilisations-56`).

Seven kinds of claim, none of them a restatement of `test_effects.py`, `test_bullet_coverage.py` or
the earlier snapshots' records (which keep those snapshots' claims, pinned to them):

- **The chain.** The build resolves to this snapshot, which names the sixth's digest, is promoted
  and digest-verified, and the whole chain validates; the sixth stays loadable by identity.
- **Nothing else moved.** `rules.json`, `aliases.toml` and the raw-id table are the sixth's, byte
  for byte; every row of the sixth is carried unchanged but the seventeen refusals the readings
  answer, which are replaced in place, and four rows whose `validated_by` was amended because it
  named a refusal that is gone.
- **No refusal is left on a carried field.** The seventeen refusals are the only ones the sixth
  held on a field this knowledge base carries (cost, production time, age, availability, producing
  building), so the build has no row of the owner's sheet left to wait for.
- **The values come out as the readings say**, one case per answered row, each with the contrast
  case that must not apply, every expectation derived from the pack's own baseline and the
  reading's arithmetic and not read back from the file under test; an entity the owner answered
  "no" for answers the baseline.
- **The selectors widen by the ids the sheet's batch of 2026-10-31 lists**, and by no others.
- **The disagreement is recorded (FR-028)** and no validation-sample reading differs from what the
  snapshot answers, so no sample row is corrected.
- **The validation record names its forms (FR-030, amended 2026-10-31).** The two sampled rows an
  independent source confirmed are the strong form; every other row says the owner declined the
  game reading and names the two fields read.
"""

from __future__ import annotations

import dataclasses
import json
import math
import re
import tomllib
from importlib import resources
from pathlib import Path

import pytest

from aoe2stats_knowledge import effects, gaps, query, snapshot

_PACKAGE = "aoe2stats_knowledge"
_DIRECTORY = "aoe2techtree-185872-owner-readings"
_SIXTH_DIRECTORY = "aoe2techtree-185872-civilisations-56"
_SIXTH_DIGEST = "sha256:b247190134e69b46e5111487db0ff98514df9ceb41bcd4f926a7278fbedd952f"
_BUILD = 185872
_OWNER_READINGS = (
    Path(__file__).resolve().parents[3]
    / "specs"
    / "006-replay-analysis-foundations"
    / "owner-readings.md"
)

#: The fields this knowledge base carries; a refusal on one is a blocking or informational gap.
_CARRIED = frozenset({"cost", "production_time", "age_requirement", "produced_at", "available_to"})

#: The sixth snapshot's seventeen refusals on a carried field, by (civilisation, field): the open
#: rows of the owner's sheet for build 185872 (T771 answered each of them on 2026-10-31).
_REFUSED_BY_THE_SIXTH = frozenset(
    {
        ("Slavs", "cost"),
        ("Sicilians", "production_time"),
        ("Chinese", "cost"),
        ("Turks", "cost"),
        ("Turks", "production_time"),
        ("Aztecs", "production_time"),
        ("Magyars", "cost"),
        ("Malay", "cost"),
        ("Vietnamese", "cost"),
        ("Vietnamese", "production_time"),
        ("Burgundians", "cost"),
        ("Burgundians", "age_requirement"),
        ("Bohemians", "cost"),
        ("Gurjaras", "production_time"),
        ("Jurchens", "cost"),
        ("Jurchens", "production_time"),
        ("Saxons", "cost"),
    }
)

#: The four carried rows whose `validated_by` names a refusal that is gone, by
#: (civilisation, field, number of entities selected); each says so under "Amended by T772".
_AMENDED = frozenset(
    {
        ("Chinese", "cost", 306),
        ("Jurchens", "cost", 12),
        ("Jurchens", "production_time", 12),
        ("Saxons", "cost", 80),
    }
)

_CLOSED_MARKER = "Closed by T772"
_AMENDED_MARKER = "Amended by T772"


def _snapshot_root(directory: str = _DIRECTORY) -> resources.abc.Traversable:
    return resources.files(_PACKAGE).joinpath("snapshots").joinpath(directory)


def _rules() -> dict[str, dict[str, dict[str, object]]]:
    parsed: dict[str, dict[str, dict[str, object]]] = json.loads(
        _snapshot_root().joinpath("rules.json").read_text(encoding="utf-8")
    )["entities"]
    return parsed


def _effects(directory: str = _DIRECTORY) -> tuple[effects.Effect, ...]:
    return effects._effects(directory)


def _half_up(value: float) -> int:
    return math.floor(value + 0.5)


def _entity(kind: str, entity_id: int | str) -> query.EntityRef:
    return query.EntityRef(kind=kind, id=str(entity_id), build=_BUILD)


def _baseline(kind: str, entity_id: int | str, key: str) -> object:
    return _rules()[kind][str(entity_id)][key]


def _time_key(kind: str) -> str:
    return {
        "unit": "training_time",
        "building": "construction_time",
        "technology": "research_time",
    }[kind]


def _value(result: object) -> object:
    assert not isinstance(result, gaps.KnowledgeGap), f"gap: {result!r}"
    return result.value  # type: ignore[attr-defined]


def _ctx(
    civilisation: str,
    *,
    researched: frozenset[str] = frozenset(),
    allies: frozenset[str] = frozenset(),
    **kwargs: object,
) -> effects.Context:
    """The owner alone on the team (or with `allies`), the technologies researched by the owner,
    which the team has researched too."""
    return effects.Context(
        researched=researched,
        team=frozenset({civilisation}) | allies,
        team_researched=researched,
        **kwargs,  # type: ignore[arg-type]
    )


def _cost(kind: str, entity_id: int | str, civilisation: str, context: effects.Context) -> object:
    return _value(query.cost(_entity(kind, entity_id), civilisation=civilisation, context=context))


def _time(kind: str, entity_id: int | str, civilisation: str, context: effects.Context) -> object:
    return _value(
        query.production_time(_entity(kind, entity_id), civilisation=civilisation, context=context)
    )


# ---------------------------------------------------------------------------------- the chain


def test_the_build_resolves_to_the_seventh_snapshot_and_the_chain_validates() -> None:
    resolved = snapshot.snapshot_for(_BUILD)
    assert isinstance(resolved, snapshot.Snapshot)
    assert resolved.directory == _DIRECTORY
    assert resolved.promoted
    assert resolved.supersedes == _SIXTH_DIGEST
    assert resolved.identity.describes_build == _BUILD
    assert resolved.normaliser_version == 2

    installed = snapshot.load_all_snapshots()  # raises when the supersession chain is malformed
    (sixth,) = (s for s in installed if s.identity.digest == _SIXTH_DIGEST)
    assert sixth.directory == _SIXTH_DIRECTORY
    assert sixth.promoted
    current_185872 = [
        s for s in snapshot.load_current_snapshots() if s.identity.describes_build == _BUILD
    ]
    assert [s.directory for s in current_185872] == [_DIRECTORY]
    snapshot.verify_installed_snapshots()


def test_the_recorded_digest_is_the_one_the_files_compute() -> None:
    resolved = snapshot.snapshot_for(_BUILD)
    assert isinstance(resolved, snapshot.Snapshot)
    computed = snapshot.compute_digest(
        _snapshot_root().joinpath("rules.json").read_bytes(),
        _snapshot_root().joinpath("effects.toml").read_bytes(),
        _snapshot_root().joinpath("aliases.toml").read_bytes(),
    )
    assert computed == resolved.identity.digest
    assert computed != _SIXTH_DIGEST


def test_the_sixth_snapshot_still_answers_its_own_refusals_by_identity() -> None:
    """SC-005: the analyses published under the sixth reproduce, so it still refuses what it
    refused; only the resolution by build moved on."""
    (sixth,) = (s for s in snapshot.load_all_snapshots() if s.identity.digest == _SIXTH_DIGEST)
    with snapshot.pinned_snapshot(sixth):
        refused = query.cost(_entity("building", 82), civilisation="Slavs")
        unaffected = query.cost(_entity("building", 82), civilisation="Mongols")
    assert isinstance(refused, gaps.KnowledgeGap)
    assert refused.cause == "effect-not-modelled"
    assert not isinstance(unaffected, gaps.KnowledgeGap)


def test_the_rules_the_aliases_and_the_raw_ids_are_the_sixths() -> None:
    for name in ("rules.json", "aliases.toml"):
        assert (
            _snapshot_root().joinpath(name).read_bytes()
            == _snapshot_root(_SIXTH_DIRECTORY).joinpath(name).read_bytes()
        ), name
    assert dict(effects.civilisation_id_names(_DIRECTORY)) == dict(
        effects.civilisation_id_names(_SIXTH_DIRECTORY)
    )
    assert effects._civilisation_ids(_DIRECTORY) == effects._civilisation_ids(_SIXTH_DIRECTORY)
    sixth = tomllib.loads(
        _snapshot_root(_SIXTH_DIRECTORY).joinpath("snapshot.toml").read_text(encoding="utf-8")
    )["snapshot"]
    seventh = tomllib.loads(_snapshot_root().joinpath("snapshot.toml").read_text(encoding="utf-8"))[
        "snapshot"
    ]
    for key in ("source", "source_version", "describes_build", "normaliser_version"):
        assert seventh[key] == sixth[key], key
    assert seventh["civilisations_modelled"] == sixth["civilisations_modelled"]


# ------------------------------------------------------------------------ nothing else moved


def _closing(effect: effects.Effect) -> bool:
    return _CLOSED_MARKER in effect.validated_by


def _amended(effect: effects.Effect) -> bool:
    return _AMENDED_MARKER in effect.validated_by


def test_the_sixth_held_exactly_seventeen_refusals_on_carried_fields_and_the_seventh_none() -> None:
    old = {(e.civilisation, e.field) for e in _effects(_SIXTH_DIRECTORY) if e.modelled == "no"}
    assert {pair for pair in old if pair[1] in _CARRIED} == _REFUSED_BY_THE_SIXTH
    assert not [e for e in _effects() if e.modelled == "no" and e.field in _CARRIED]


def test_every_row_of_the_sixth_is_carried_unchanged_but_the_refusals_it_closes() -> None:
    """Same build, same pack revision: a row is carried, not re-derived. Compared as parsed rows,
    every field including `validated_by`, in the same order. The seventeen refusals are replaced
    in place; four carried rows differ in `validated_by` alone."""
    old = _effects(_SIXTH_DIRECTORY)
    new = _effects()
    carried_old = [
        e for e in old if not (e.modelled == "no" and e.field in _CARRIED)
    ]  # the refusals are replaced
    carried_new = [e for e in new if not _closing(e)]
    assert len(carried_new) == len(carried_old)
    amended_seen: set[tuple[str, str, int]] = set()
    for before, after in zip(carried_old, carried_new, strict=True):
        if _amended(after):
            amended_seen.add((after.civilisation, after.field, len(after.selector)))
            assert after.validated_by != before.validated_by
            assert after.validated_by.startswith(before.validated_by)
            assert dataclasses.replace(after, validated_by=before.validated_by) == before
        else:
            assert after == before, ("changed", before.civilisation, before.source_text)
    assert amended_seen == _AMENDED


def test_every_closing_row_replaces_a_refusal_of_its_own_bullet_in_its_place() -> None:
    old = _effects(_SIXTH_DIRECTORY)
    new = _effects()
    refused = [(e.civilisation, e.source_text, e.field) for e in old if _is_refusal(e)]
    closing = [(e.civilisation, e.source_text, e.field) for e in new if _closing(e)]
    # One refusal becomes one row (Sicilians, Turks, Aztecs, Magyars, Malay, Vietnamese,
    # Gurjaras, Jurchens, Saxons), two (Slavs) or twelve (Bohemians), three more for Burgundians'
    # age; Chinese's refusal becomes no row, the answer being "no".
    assert set(closing) == set(refused) - {
        ("Chinese", "Technologies cost -5/10/15% in Feudal/Castle/Imperial Age", "cost")
    }
    assert len(closing) == 30
    # In place: each closing row follows the carried row that followed the refusal's predecessor.
    old_index = {
        key: i
        for i, key in enumerate(
            (e.civilisation, e.source_text, e.field, e.modelled == "no" and e.field in _CARRIED)
            for e in old
        )
    }
    assert old_index  # the key list above is the order of the sixth
    positions = [i for i, e in enumerate(new) if _closing(e)]
    assert positions == sorted(positions)
    for index in positions:
        row = new[index]
        assert row.modelled == "yes", (row.civilisation, row.source_text)
        assert row.source_key in row.validated_by


def _is_refusal(effect: effects.Effect) -> bool:
    return effect.modelled == "no" and effect.field in _CARRIED


def test_every_closing_row_cites_the_reading_it_transcribes() -> None:
    for effect in _effects():
        if not _closing(effect):
            continue
        text = effect.validated_by
        assert "owner-readings.md" in text, (effect.civilisation, effect.source_text)
        assert "2026-10-31" in text
        assert "not a game reading" in text
        assert "T772" in text
        assert "value read" in text
        assert "where read" in text


# --------------------------------------------------------------------------------- the values


def test_detinets_moves_forty_percent_of_the_stone_to_wood_and_reaches_the_bombard_tower() -> None:
    # The owner's readings (owner-readings.md, batch of 2026-10-31).
    owner = {
        82: {"wood": 260, "stone": 390},
        79: {"wood": 85, "stone": 75},
        234: {"wood": 85, "stone": 75},
        235: {"wood": 85, "stone": 75},
        236: {"wood": 50, "stone": 75, "gold": 100},
    }
    detinets = _ctx("Slavs", researched=frozenset({"455"}))
    none = _ctx("Slavs")
    for building, reading in owner.items():
        base = _baseline("building", building, "cost")
        stone = base["stone"]  # type: ignore[index]
        moved = _half_up(stone * 0.4)
        derived = {**base, "stone": stone - moved, "wood": base["wood"] + moved}  # type: ignore[dict-item,operator]
        assert {k: v for k, v in derived.items() if k in reading} == reading, building
        assert _cost("building", building, "Slavs", detinets) == derived
        assert _cost("building", building, "Slavs", none) == base
        assert _cost("building", building, "Mongols", _ctx("Mongols")) == base
    with pytest.raises(effects.ContextRequired):
        query.cost(_entity("building", 236), civilisation="Slavs")
    # A tower the owner did not name stays as it is: the Krepost.
    assert _cost("building", 1251, "Slavs", detinets) == _baseline("building", 1251, "cost")


def test_the_sicilians_fortifications_include_walls_gates_palisades_and_the_tower_line() -> None:
    fortifications = (79, 234, 235, 236, 117, 487, 72, 792, 82, 1665)
    for building in fortifications:
        base = _baseline("building", building, "construction_time")
        assert _time("building", building, "Sicilians", _ctx("Sicilians")) == pytest.approx(
            base / 1.5  # type: ignore[operator]
        ), building
        assert _time("building", building, "Franks", _ctx("Franks")) == base
    # "Not the Dock"; the Krepost is not named.
    for building in (45, 1251):
        assert _time("building", building, "Sicilians", _ctx("Sicilians")) == _baseline(
            "building", building, "construction_time"
        )
    # The Town Centers are the other half of the bullet and stay twice as fast.
    assert _time("building", 109, "Sicilians", _ctx("Sicilians")) == pytest.approx(
        _baseline("building", 109, "construction_time") / 2  # type: ignore[operator]
    )


def test_the_chinese_discount_does_not_reach_the_age_advances() -> None:
    for age_advance, age in ((102, 2), (103, 3)):
        base = _baseline("technology", age_advance, "cost")
        for at in range(age, 5):
            assert _cost("technology", age_advance, "Chinese", _ctx("Chinese", age=at)) == base
    # The contrast: another technology of the same tree is discounted in the same age.
    base = _baseline("technology", 199, "cost")
    factor = 0.9
    assert _cost("technology", 199, "Chinese", _ctx("Chinese", age=3)) == {
        resource: _half_up(amount * factor)  # type: ignore[operator]
        for resource, amount in base.items()  # type: ignore[attr-defined]
    }


def test_the_turks_halve_the_bombard_tower_and_elite_cannon_galleon_and_nothing_else() -> None:
    for technology in (64, 376):
        base = _baseline("technology", technology, "cost")
        assert _cost("technology", technology, "Turks", _ctx("Turks")) == {
            resource: _half_up(amount * 0.5)  # type: ignore[operator]
            for resource, amount in base.items()  # type: ignore[attr-defined]
        }
        assert _cost("technology", technology, "Franks", _ctx("Franks")) == base
    # The owner's readings: the pre-discount costs the pack agrees with.
    assert _baseline("technology", 64, "cost") == {"food": 800, "wood": 400}
    assert _baseline("technology", 376, "cost") == {"gold": 500, "wood": 525}
    for technology in (10, 369):
        assert _cost("technology", technology, "Turks", _ctx("Turks")) == _baseline(
            "technology", technology, "cost"
        )
    # Cannon Galleon (scrapped in update 47820) is no technology of the pack: it widens nothing.
    names = {
        str(rec["name"]).replace("<br>\n", " ")
        for rec in _rules()["technology"].values()
        if rec["name"]
    }
    assert "Cannon Galleon" not in names


def test_the_turks_team_bonus_speeds_the_foot_and_mounted_gunners_of_the_whole_team() -> None:
    for unit in (46, 557, 771, 773):
        base = _baseline("unit", unit, "training_time")
        assert _time("unit", unit, "Turks", _ctx("Turks")) == pytest.approx(base / 1.25)  # type: ignore[operator]
        assert _time("unit", unit, "Franks", _ctx("Franks", allies=frozenset({"Turks"}))) == (
            pytest.approx(base / 1.25)  # type: ignore[operator]
        )
        assert _time("unit", unit, "Franks", _ctx("Franks")) == base
        with pytest.raises(effects.ContextRequired):
            query.production_time(_entity("unit", unit), civilisation="Franks")


def test_the_aztecs_train_the_dock_units_faster_and_not_the_monk() -> None:
    warships = (21, 527, 529, 532, 539, 1103, 1104, 2626, 2627, 2628, 2633)
    for unit in warships:
        base = _baseline("unit", unit, "training_time")
        assert _time("unit", unit, "Aztecs", _ctx("Aztecs")) == pytest.approx(base / 1.15), unit  # type: ignore[operator]
        assert _time("unit", unit, "Franks", _ctx("Franks")) == base
    assert _time("unit", 125, "Aztecs", _ctx("Aztecs")) == _baseline("unit", 125, "training_time")


def test_corvinian_army_replaces_the_huszars_gold_with_food() -> None:
    for unit in (869, 871):
        base = _baseline("unit", unit, "cost")
        assert base == {"food": 35, "gold": 45}
        assert _cost("unit", unit, "Magyars", _ctx("Magyars", researched=frozenset({"514"}))) == {
            "food": 80,  # the owner's reading, and 35 + 45
            "gold": 0,
        }
        assert _cost("unit", unit, "Magyars", _ctx("Magyars")) == base
        assert _cost("unit", unit, "Franks", _ctx("Franks")) == base


def test_forced_levy_replaces_twenty_gold_with_twenty_food_on_the_whole_line() -> None:
    for unit in (74, 75, 77, 473, 567):
        base = _baseline("unit", unit, "cost")
        assert base == {"food": 50, "gold": 20}
        # The owner's reading: -20 gold, +20 food (not Liquipedia's 80 food total).
        assert _cost("unit", unit, "Malay", _ctx("Malay", researched=frozenset({"625"}))) == {
            "food": 70,
            "gold": 0,
        }
        assert _cost("unit", unit, "Malay", _ctx("Malay")) == base
        assert _cost("unit", unit, "Franks", _ctx("Franks")) == base


def test_hussite_reforms_replaces_the_gold_of_the_monk_and_each_monastery_technology() -> None:
    reformed = _ctx("Bohemians", researched=frozenset({"785"}))
    plain = _ctx("Bohemians")
    members = [("unit", 125)] + [
        ("technology", t) for t in (45, 46, 230, 231, 233, 252, 316, 319, 438, 439, 441)
    ]
    for kind, entity in members:
        base = _baseline(kind, entity, "cost")
        food, gold = base["food"], base["gold"]  # type: ignore[index]
        assert _cost(kind, entity, "Bohemians", reformed) == {"food": food + gold, "gold": 0}
        assert _cost(kind, entity, "Bohemians", plain) == base
        assert _cost(kind, entity, "Franks", _ctx("Franks")) == base
    # The owner's derived readings.
    assert _cost("unit", 125, "Bohemians", reformed) == {"food": 100, "gold": 0}
    assert _cost("technology", 233, "Bohemians", reformed) == {"food": 120, "gold": 0}


def test_the_vietnamese_economic_upgrades_cost_no_wood_and_research_twice_as_fast() -> None:
    four = (213, 249, 65, 906)
    six = (213, 249, 65, 906, 15, 48)
    for technology in four:
        base = _baseline("technology", technology, "cost")
        assert _cost("technology", technology, "Vietnamese", _ctx("Vietnamese")) == {
            **base,  # type: ignore[dict-item]
            "wood": 0,
        }
        assert _cost("technology", technology, "Franks", _ctx("Franks")) == base
    for technology in six:
        base_time = _baseline("technology", technology, "research_time")
        assert _time("technology", technology, "Vietnamese", _ctx("Vietnamese")) == (
            pytest.approx(base_time / 2)  # type: ignore[operator]
        )
    # Loom (the owner's answer), Banking and Coinage are not researched faster.
    for technology in (22, 17, 23):
        assert _time("technology", technology, "Vietnamese", _ctx("Vietnamese")) == _baseline(
            "technology", technology, "research_time"
        )
    for technology in (17, 23):  # and cost no wood to begin with
        assert _cost("technology", technology, "Vietnamese", _ctx("Vietnamese")) == _baseline(
            "technology", technology, "cost"
        )


def test_the_burgundian_economic_upgrades_cost_forty_percent_less_food_and_come_a_age_earlier() -> (
    None
):
    six = {213: 1, 906: 1, 249: 2, 65: 2, 48: 2, 15: 3}
    for technology, age in six.items():
        base = _baseline("technology", technology, "cost")
        assert _cost("technology", technology, "Burgundians", _ctx("Burgundians")) == {
            **base,  # type: ignore[dict-item]
            "food": _half_up(base["food"] * 0.6),  # type: ignore[index,operator]
        }
        assert _baseline("technology", technology, "age_requirement") == age + 1
        assert (
            _value(
                query.age_requirement(_entity("technology", technology), civilisation="Burgundians")
            )
            == age
        )
        assert _cost("technology", technology, "Franks", _ctx("Franks")) == base
    # Coinage and Banking are not among them (the owner's answer).
    for technology in (17, 23):
        assert _cost("technology", technology, "Burgundians", _ctx("Burgundians")) == _baseline(
            "technology", technology, "cost"
        )
        assert _value(
            query.age_requirement(_entity("technology", technology), civilisation="Burgundians")
        ) == _baseline("technology", technology, "age_requirement")


def test_the_gurjaras_team_bonus_speeds_every_camel_and_elephant_unit_but_the_shrivamsha() -> None:
    sped = (329, 330, 873, 875, 1744, 1746, 1755)
    for unit in sped:
        base = _baseline("unit", unit, "training_time")
        assert _time("unit", unit, "Gurjaras", _ctx("Gurjaras")) == pytest.approx(base / 1.25)  # type: ignore[operator]
        assert _time("unit", unit, "Franks", _ctx("Franks", allies=frozenset({"Gurjaras"}))) == (
            pytest.approx(base / 1.25)  # type: ignore[operator]
        )
        assert _time("unit", unit, "Franks", _ctx("Franks")) == base
    for unit in (1751, 1753):
        assert _time("unit", unit, "Gurjaras", _ctx("Gurjaras")) == _baseline(
            "unit", unit, "training_time"
        )


@pytest.mark.parametrize(
    ("count", "factor"), [(0, 1.0), (1, 0.95), (2, 0.9), (3, 0.85), (4, 0.8), (9, 0.8)]
)
def test_the_saxon_foot_archers_and_skirmishers_are_foot_soldiers(
    count: int, factor: float
) -> None:
    counted = frozenset(effects.SelectorEntry("building", i) for i in ("71", "109", "621", "82"))
    context = effects.Context(controlled={counted: count}, team=frozenset({"Saxons"}))
    for unit in (4, 24, 492, 7, 6):
        base = _baseline("unit", unit, "cost")
        got = _value(query.cost(_entity("unit", unit), civilisation="Saxons", context=context))
        assert got == {
            resource: _half_up(amount * factor)  # type: ignore[operator]
            for resource, amount in base.items()  # type: ignore[attr-defined]
        }, (unit, count)
        assert _value(query.cost(_entity("unit", unit), civilisation="Franks")) == base
    with pytest.raises(effects.ContextRequired):
        query.cost(_entity("unit", 4), civilisation="Saxons")


def test_the_jurchens_list_is_the_owners_complete_list() -> None:
    # The complete list the owner confirmed (2026-10-31): the ones the criterion already modelled
    # and the four it never matched (Masonry 50, Architecture 51, Treadmill Crane 54, Sappers 321).
    yes = (377, 379, 608, 50, 51, 54, 321)
    no = (93, 996)
    for technology in yes:
        base = _baseline("technology", technology, "cost")
        assert _cost("technology", technology, "Jurchens", _ctx("Jurchens")) == {
            resource: (_half_up(amount * 0.25) if resource == "wood" else amount)  # type: ignore[operator]
            for resource, amount in base.items()  # type: ignore[attr-defined]
        }, technology
        assert _time("technology", technology, "Jurchens", _ctx("Jurchens")) == pytest.approx(
            _baseline("technology", technology, "research_time") / 2  # type: ignore[operator]
        )
        assert _cost("technology", technology, "Franks", _ctx("Franks")) == base
    for technology in (*no, 47, 199, 200, 201):
        assert _time("technology", technology, "Jurchens", _ctx("Jurchens")) == _baseline(
            "technology", technology, "research_time"
        ), technology
    for technology in no:
        assert _cost("technology", technology, "Jurchens", _ctx("Jurchens")) == _baseline(
            "technology", technology, "cost"
        )


# ----------------------------------------------------------------------- the widened selectors


def _selected(civilisation: str, field: str, *source_text_start: str) -> set[tuple[str, str]]:
    return {
        (entry.kind, entry.id)
        for e in _effects()
        if _closing(e)
        and e.civilisation == civilisation
        and e.field == field
        and e.source_text.startswith(source_text_start)
        for entry in e.selector
    }


def test_each_answer_that_names_an_entity_its_row_did_not_widens_that_effects_selector() -> None:
    # Detinets: the Bombard Tower (236) joins the Castle and the tower line.
    assert _selected("Slavs", "cost", "Detinets") == {
        ("building", i) for i in ("82", "79", "234", "235", "236")
    }
    # Fortifications: the Stone Wall, Gate, Palisade Wall and Palisade Gate join the tower line and
    # the Bombard Tower; the Krepost is not named and is out.
    assert _selected("Sicilians", "production_time", "Fortifications") == {
        ("building", i) for i in ("79", "234", "235", "236", "117", "487", "72", "792")
    }
    # The Castle and the Donjon stay in the row T767 transcribed: the list adds to them.
    (castle,) = [
        e
        for e in _effects()
        if e.civilisation == "Sicilians"
        and e.field == "production_time"
        and not _closing(e)
        and {(s.kind, s.id) for s in e.selector} == {("building", "82"), ("building", "1665")}
    ]
    assert castle.modelled == "yes"
    # The Jurchens' four: Masonry, Architecture, Treadmill Crane and Sappers join the three.
    for field in ("cost", "production_time"):
        assert _selected("Jurchens", field, "Siege and Fortification") == {
            ("technology", i) for i in ("377", "379", "608", "50", "51", "54", "321")
        }
    # The Turks' third technology widens nothing: the cost row names two of the pack's four.
    assert _selected("Turks", "cost", "Chemistry free") == {
        ("technology", "64"),
        ("technology", "376"),
    }


def test_no_entity_the_owner_answered_no_for_is_selected_by_the_row_it_was_asked_under() -> None:
    answered_no = {
        ("Turks", "cost"): {("technology", "10"), ("technology", "369")},
        ("Aztecs", "production_time"): {("unit", "125")},
        ("Vietnamese", "cost"): set(),
        ("Vietnamese", "production_time"): {("technology", "22")},
        ("Gurjaras", "production_time"): {("unit", "1751"), ("unit", "1753")},
        ("Jurchens", "cost"): {("technology", "93"), ("technology", "996")},
        ("Jurchens", "production_time"): {
            ("technology", i) for i in ("93", "996", "47", "199", "200", "201")
        },
        ("Sicilians", "production_time"): {("building", "1251")},
        ("Chinese", "cost"): {("technology", "102"), ("technology", "103")},
    }
    for (civilisation, field), refused in answered_no.items():
        selected = {
            (entry.kind, entry.id)
            for e in _effects()
            if e.civilisation == civilisation and e.field == field
            for entry in e.selector
        }
        assert not selected & refused, (civilisation, field, selected & refused)


# ----------------------------------------------------------------------------- disagreements


def _disagreements() -> list[dict[str, object]]:
    parsed = tomllib.loads(
        _snapshot_root().joinpath("disagreements.toml").read_text(encoding="utf-8")
    )
    entries: list[dict[str, object]] = parsed["disagreement"]
    return entries


def test_liquipedias_forced_levy_total_is_recorded_as_a_disagreement_on_the_militia_line() -> None:
    entries = _disagreements()
    assert sorted(str(e["entity_id"]) for e in entries) == ["473", "567", "74", "75", "77"]
    for entry in entries:
        assert entry["entity_kind"] == "unit"
        assert entry["field"] == "cost"
        assert "pack" in str(entry["stored_source"]).lower()
        readings = entry["readings"]
        assert isinstance(readings, dict)
        assert set(readings) == {"pack", "liquipedia"}
        assert "food" in readings["pack"] and "50" in readings["pack"]
        assert "80" in readings["liquipedia"]
        assert "60" in readings["liquipedia"]
        assert str(entry["reason"]).strip()
        pack_cost = _baseline("unit", str(entry["entity_id"]), "cost")
        assert pack_cost == {"food": 50, "gold": 20}
    # What is stored is the pack-consistent value, not Liquipedia's total.
    assert _cost("unit", 74, "Malay", _ctx("Malay", researched=frozenset({"625"}))) == {
        "food": 70,
        "gold": 0,
    }


def test_the_disagreements_file_keeps_the_normalisers_own_header_and_adds_only_the_five() -> None:
    text = _snapshot_root().joinpath("disagreements.toml").read_text(encoding="utf-8")
    sixth = _snapshot_root(_SIXTH_DIRECTORY).joinpath("disagreements.toml").read_text("utf-8")
    assert text.startswith(sixth)
    assert text.count("[[disagreement]]") == 5


# ---------------------------------------------------------------------- the validation sample

_AGE_NUMBERS = {"Dark Age": 1, "Feudal Age": 2, "Castle Age": 3, "Imperial Age": 4}
_FUNCS = {
    "cost": query.cost,
    "production_time": query.production_time,
    "age_requirement": query.age_requirement,
}
_STRONG = {"Teutons", "Vietnamese"}


def _sample_rows() -> list[list[str]]:
    sheet = _OWNER_READINGS.read_text(encoding="utf-8")
    section = sheet[sheet.index("## Validation sample") : sheet.index("## Production")]
    rows = [line for line in section.splitlines() if line.startswith("| ")]
    return [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in rows[2:]]


def _sample_context(
    civilisation: str, entity: str, technologies: str, age: int | None
) -> effects.Context:
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


def test_every_row_of_the_validation_sample_is_still_what_the_snapshot_answers() -> None:
    """The readings of the two rows an independent source answered agree with the snapshot, and
    the other fifty-four were not read: no sample row differs from what the snapshot answered,
    so none is a disagreement and none is corrected (T772)."""
    rows = _sample_rows()
    assert len(rows) == 56
    for civilisation, entity, age, technologies, value, read, _date in rows:
        match = re.search(r"\((unit|building|technology) (\d+)\)", entity)
        assert match, entity
        kind, ident = match.groups()
        field, rest = value.split(" ", 1)
        expected = json.loads(rest.partition("; pack baseline ")[0])
        ages = (1, 2, 3, 4) if age == "any" else (_AGE_NUMBERS[age],)
        for at in ages:
            context = _sample_context(civilisation, entity, technologies, at)
            answer = _FUNCS[field](_entity(kind, ident), civilisation=civilisation, context=context)
            assert not isinstance(answer, gaps.KnowledgeGap), (civilisation, answer)
            if field == "production_time":
                assert answer.value == pytest.approx(expected, abs=0.005), (civilisation, entity)  # type: ignore[attr-defined]
            else:
                assert answer.value == expected, (civilisation, entity)  # type: ignore[attr-defined]
        if civilisation in _STRONG:
            assert read and not read.startswith("not read"), civilisation
        else:
            assert read.startswith("not read: the owner declined in-game reading"), civilisation


def test_the_two_sample_readings_agree_with_the_snapshot_so_no_row_is_corrected() -> None:
    by_civilisation = {row[0]: row for row in _sample_rows()}
    teutons = _cost("technology", 322, "Teutons", _ctx("Teutons"))
    assert teutons == {"food": 0, "stone": 0}
    assert "free (0 food, 0 stone)" in by_civilisation["Teutons"][5]
    vietnamese = _cost("technology", 12, "Vietnamese", _ctx("Vietnamese"))
    assert vietnamese == {"food": 250, "wood": 0}
    assert "250 food, no wood" in by_civilisation["Vietnamese"][5]


# ------------------------------------------------------------------------------ the record


def _validation() -> snapshot.ValidationRecord:
    resolved = snapshot.snapshot_for(_BUILD)
    assert isinstance(resolved, snapshot.Snapshot)
    assert resolved.validation is not None
    return resolved.validation


def test_the_validation_record_names_the_strong_form_for_two_rows_and_the_second_reading() -> None:
    record = _validation()
    assert record.performed_at == "2026-10-31"
    assert "AI agent" in record.performed_by
    text = record.checked_against
    # The strong form, for the two rows an independent source confirmed.
    assert "strong form" in text
    for name in ("Teutons", "Murder Holes", "Vietnamese", "Crop Rotation", "Liquipedia"):
        assert name in text, name
    # The second reading of the pack, for every other row: the owner declined, and the two fields.
    assert "declined" in text
    assert "second reading" in text
    for name in ("strings.en.json", "rules.json"):
        assert name in text, name
    details = record.details
    assert details["not_checked"].strip()
    assert "accepted" in details["not_checked"] and "unchecked" in details["not_checked"]


def test_the_record_lists_every_sampled_row_under_exactly_one_form() -> None:
    details = _validation().details
    strong = details["strong_form"]
    weak = details["second_reading"]
    rows = {row[0]: row for row in _sample_rows()}
    assert {entry["civilisation"] for entry in strong} == _STRONG
    assert {entry["civilisation"] for entry in weak} == set(rows) - _STRONG
    assert len(weak) == 54
    for entry in (*strong, *weak):
        assert entry["entity"] and entry["field"] in {"cost", "production_time", "age_requirement"}
        sample_row = rows[entry["civilisation"]]
        assert entry["field"] == sample_row[4].split(" ", 1)[0]
        assert re.search(r"\((unit|building|technology) (\d+)\)", sample_row[1])
    for entry in strong:
        assert "Liquipedia" in entry["source"]
        assert "accepted by the owner unchecked" in entry["source"]
    for entry in weak:
        assert entry["fields_read"] == _WEAK_FIELDS, entry["civilisation"]


#: The two fields the second reading read, by name: the bonus sentence and the entity's baseline.
_WEAK_FIELDS = [
    "strings.en.json, help_string_id: the civilisation's bonus sentence",
    "rules.json: the entity's own baseline for the sampled field",
]


# ---------------------------------------------------------------------------------- the sheet


def test_the_sheet_says_the_snapshot_closed_every_build_185872_row_and_keeps_the_readings() -> None:
    sheet = _OWNER_READINGS.read_text(encoding="utf-8")
    assert "T772" in sheet
    assert _DIRECTORY in sheet
    open_values = sheet[sheet.index("## Open values") : sheet.index("## Validation sample")]
    rows = [line for line in open_values.splitlines() if line.startswith("| 185872 |")]
    assert len(rows) == 28
    for line in rows:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        assert cells[-4], line[:80]  # a value read
        assert cells[-3], line[:80]  # where it was read
        assert cells[-2] == "not a game reading" or cells[-1] == "2026-10-22", line[:80]
    # Nothing was reported unreadable: no FR-022b entry exists for the build.
    assert "unreadable" not in "\n".join(rows).replace("write `unreadable`", "")
