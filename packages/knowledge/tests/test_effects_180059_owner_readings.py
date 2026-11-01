"""T774: the third build 180059 snapshot, `aoe2techtree-180059-owner-readings`, which carries the
owner's readings that T772 closed on build 185872 back to build 180059 and supersedes the second
(`aoe2techtree-180059-civilisations-53`, T773).

Six kinds of claim, none of them a restatement of `test_effects.py`, of the second snapshot's record
(`test_effects_180059_civilisations_53.py`) or of the source snapshot's
(`test_effects_185872_owner_readings.py`):

- **The chain.** The build resolves to this snapshot, which names the second's digest, is promoted
  and digest-verified; the second and the first stay loadable by identity, and the second still
  answers its own refusals (SC-005).
- **Nothing else moved.** `rules.json`, `aliases.toml`, `disagreements.toml` and the raw-id table
  are the second's, byte for byte, and every row of the second is here unchanged but the ones the
  readings replace, in place.
- **The carry is T773's rule, recomputed.** A refusal of the second snapshot that T772 closed on
  build 185872 is replaced by the rows that closed it if and only if the three conditions hold for
  the refusal and for each closing row (the bullet byte-identical in both packs, every identifier
  the same with the same name, no change in the build 185872 release notes or in the entities'
  data), recomputed from both packs by the second snapshot's own test; a row that fails one stays
  a refusal. Each carried row is the source row but for an appended `validated_by`.
- **The five rows not carried are named**, and each still answers `effect-not-modelled` for every
  entity it selects.
- **The values come out as the readings say** on build 180059's own baseline, each with its
  contrast case, and equal what the source snapshot answers for the same entity and context.
- **The sheet** names the carry and holds an open row for exactly the five rows not carried.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from pathlib import Path

import pytest

# The second snapshot's test holds the carry rule's recomputation (the notes table and the three
# conditions); this file reuses it rather than restating a 190-line table.
from test_effects_180059_civilisations_53 import (  # type: ignore[import-not-found]
    _NOT_IN_THIS_PACK,
    _row_failures,
    _rows,
    _snapshot_root,
    _toml,
)

from aoe2stats_knowledge import effects, gaps, query, snapshot

_DIRECTORY = "aoe2techtree-180059-owner-readings"
_SECOND_DIRECTORY = "aoe2techtree-180059-civilisations-53"
_FIRST_DIRECTORY = "aoe2techtree-180059"
_SIXTH_DIRECTORY = "aoe2techtree-185872-civilisations-56"
_SOURCE_DIRECTORY = "aoe2techtree-185872-owner-readings"
_BUILD = 180059
_SECOND_DIGEST = "sha256:343f2f003b12107619003d63eb9f1530d3515674c7a946e70e3e1141c2a96e1d"
_FIRST_DIGEST = "sha256:6167f0b69be56d7a33803d29a060b9f29f34c917073eb970ccccc1c206c6b81a"
_SOURCE_DIGEST = "sha256:45417481c2e078e22805d4d7c2365818dea34225634ecd22e52e8b48958d328c"
_OWNER_READINGS = (
    Path(__file__).resolve().parents[3]
    / "specs"
    / "006-replay-analysis-foundations"
    / "owner-readings.md"
)

#: The fields this knowledge base carries; a refusal on one is a blocking or informational gap.
_CARRIED = frozenset({"cost", "production_time", "age_requirement", "produced_at", "available_to"})

#: The bonuses whose refusal this snapshot closes, by (civilisation, field). The Chinese one is
#: closed without a row: the owner's answer was no.
_REACHED = frozenset(
    {
        ("Slavs", "cost"),
        ("Sicilians", "production_time"),
        ("Chinese", "cost"),
        ("Turks", "cost"),
        ("Vietnamese", "cost"),
        ("Vietnamese", "production_time"),
        ("Burgundians", "cost"),
        ("Burgundians", "age_requirement"),
        ("Bohemians", "cost"),
        ("Jurchens", "cost"),
        ("Jurchens", "production_time"),
    }
)

#: The five bonuses the three conditions do not reach, by (civilisation, field): each stays an open
#: row of the sheet for build 180059. Each row fails the third condition.
_NOT_REACHED = frozenset(
    {
        ("Turks", "production_time"),
        ("Aztecs", "production_time"),
        ("Magyars", "cost"),
        ("Malay", "cost"),
        ("Gurjaras", "production_time"),
    }
)

_CARRIED_MARK = "Carried to build 180059 by T774"
_RECARRIED_MARK = "Re-carried to build 180059 by T774"
_AMENDED_MARK = "Amended by T774"


def _rules() -> dict[str, dict[str, dict[str, object]]]:
    import json

    parsed: dict[str, dict[str, dict[str, object]]] = json.loads(
        _snapshot_root(_DIRECTORY).joinpath("rules.json").read_text(encoding="utf-8")
    )["entities"]
    return parsed


def _half_up(value: float) -> int:
    return math.floor(value + 0.5)


def _entity(kind: str, entity_id: int | str, build: int = _BUILD) -> query.EntityRef:
    return query.EntityRef(kind=kind, id=str(entity_id), build=build)


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


def _key(row: Mapping[str, object]) -> tuple[str, str, str]:
    return (str(row["civilisation"]), str(row["source_text"]), str(row["field"]))


def _without_validation(row: Mapping[str, object]) -> dict[str, object]:
    return {k: v for k, v in row.items() if k != "validated_by"}


def _old() -> list[dict[str, object]]:
    return _rows(_SECOND_DIRECTORY)


def _new() -> list[dict[str, object]]:
    return _rows(_DIRECTORY)


def _removed() -> list[dict[str, object]]:
    new = _new()
    return [row for row in _old() if row not in new]


def _added() -> list[dict[str, object]]:
    old = _old()
    return [row for row in _new() if row not in old]


# ---------------------------------------------------------------------------------- the chain


def test_the_build_resolves_to_the_third_snapshot_and_the_chain_validates() -> None:
    resolved = snapshot.snapshot_for(_BUILD)
    assert isinstance(resolved, snapshot.Snapshot)
    assert resolved.directory == _DIRECTORY
    assert resolved.promoted
    assert resolved.supersedes == _SECOND_DIGEST
    assert resolved.identity.describes_build == _BUILD
    by_digest = {s.identity.digest: s for s in snapshot.load_all_snapshots()}
    second = by_digest[_SECOND_DIGEST]
    assert second.directory == _SECOND_DIRECTORY
    assert second.supersedes == _FIRST_DIGEST
    first = by_digest[_FIRST_DIGEST]
    assert first.directory == _FIRST_DIRECTORY
    assert resolved.identity.digest not in (_SECOND_DIGEST, _FIRST_DIGEST)
    assert resolved.identity.source_version == second.identity.source_version
    assert resolved.identity.digest != _SOURCE_DIGEST


def test_the_recorded_digest_is_the_one_the_files_compute() -> None:
    root = _snapshot_root(_DIRECTORY)
    recorded = snapshot.snapshot_for(_BUILD)
    assert isinstance(recorded, snapshot.Snapshot)
    assert recorded.identity.digest == snapshot.compute_digest(
        root.joinpath("rules.json").read_bytes(),
        root.joinpath("effects.toml").read_bytes(),
        root.joinpath("aliases.toml").read_bytes(),
    )


def test_the_second_snapshot_still_answers_its_refusals_by_identity() -> None:
    """SC-005: pinned by identity, the second still refuses the Slavs' Detinets and the Chinese Age
    advances, which the third closes."""
    by_digest = {s.identity.digest: s for s in snapshot.load_all_snapshots()}
    second = by_digest[_SECOND_DIGEST]
    detinets = _ctx("Slavs", researched=frozenset({"455"}))
    with snapshot.pinned_snapshot(second):
        refused = query.cost(_entity("building", 82), civilisation="Slavs", context=detinets)
    assert isinstance(refused, gaps.KnowledgeGap)
    assert refused.cause == "effect-not-modelled"
    now = query.cost(_entity("building", 82), civilisation="Slavs", context=detinets)
    assert not isinstance(now, gaps.KnowledgeGap), f"gap: {now!r}"


def test_the_rules_the_aliases_and_the_disagreements_are_the_seconds_byte_for_byte() -> None:
    second = _snapshot_root(_SECOND_DIRECTORY)
    third = _snapshot_root(_DIRECTORY)
    for name in ("rules.json", "aliases.toml", "disagreements.toml"):
        assert third.joinpath(name).read_bytes() == second.joinpath(name).read_bytes(), name


def test_the_raw_id_table_and_the_civilisations_modelled_are_the_seconds() -> None:
    assert (
        _toml(_DIRECTORY, "effects.toml")["civilisation_id"]
        == _toml(_SECOND_DIRECTORY, "effects.toml")["civilisation_id"]
    )
    new = snapshot.snapshot_for(_BUILD)
    old = {s.identity.digest: s for s in snapshot.load_all_snapshots()}[_SECOND_DIGEST]
    assert isinstance(new, snapshot.Snapshot)
    text = _snapshot_root(_DIRECTORY).joinpath("snapshot.toml").read_text(encoding="utf-8")
    old_text = _snapshot_root(_SECOND_DIRECTORY).joinpath("snapshot.toml").read_text("utf-8")
    pattern = re.compile(r"^civilisations_modelled = .*$", re.MULTILINE)
    match, old_match = pattern.search(text), pattern.search(old_text)
    assert match and old_match and match.group(0) == old_match.group(0)
    assert new.identity.describes_build == old.identity.describes_build == _BUILD


# ------------------------------------------------------------------------- nothing else moved


def test_every_row_of_the_second_snapshot_is_here_unchanged_and_in_order_but_the_replaced() -> None:
    old, new = _old(), _new()
    assert [r for r in new if r in old] == [r for r in old if r in new]
    removed, added = _removed(), _added()
    assert len(old) == 298
    # Twelve rows replaced by twenty-six; one refusal gone; one carried-over row gains a sentence.
    assert (len(removed), len(added)) == (14, 27)
    assert len(new) == len(old) - len(removed) + len(added) == 311


def test_every_removed_row_is_a_closed_refusal_a_row_t772_amended_or_the_chinese_row() -> None:
    removed = _removed()
    refusals = [r for r in removed if r["modelled"] == "no"]
    assert len(refusals) == 11
    assert {(r["civilisation"], r["field"]) for r in refusals} == _REACHED
    others = [r for r in removed if r["modelled"] == "yes"]
    assert sorted((r["civilisation"], r["field"], len(r["selector"])) for r in others) == [  # type: ignore[arg-type]
        ("Chinese", "cost", 294),
        ("Jurchens", "cost", 12),
        ("Jurchens", "production_time", 12),
    ]


def test_every_added_row_is_a_source_row_with_the_carry_named_or_the_amended_chinese_row() -> None:
    source = _rows(_SOURCE_DIRECTORY)
    removed = _removed()
    carried = 0
    for row in _added():
        validated = str(row["validated_by"])
        if _AMENDED_MARK in validated:
            (old,) = [r for r in removed if _without_validation(r) == _without_validation(row)]
            assert row["civilisation"] == "Chinese"
            assert validated.startswith(str(old["validated_by"]))
            assert _SOURCE_DIGEST in validated
            assert "technologies 102, 103" in validated
            assert "not a game reading" in validated
            continue
        matches = [
            s
            for s in source
            if _without_validation(s) == _without_validation(row)
            and validated.startswith(str(s["validated_by"]))
        ]
        assert len(matches) >= 1, (row["civilisation"], row["source_text"])
        assert _SOURCE_DIGEST in validated
        assert validated.count("T774") >= 1
        assert _CARRIED_MARK in validated or _RECARRIED_MARK in validated
        if _CARRIED_MARK in validated:
            # The reading is attributed to build 185872, and is no game reading.
            assert "not a game reading" in validated
            assert "arbitration of 2026-10-31" in validated
        carried += 1
    assert carried == 26


# ------------------------------------------------------------------ the carry rule, recomputed


def _closed_by_t772() -> list[dict[str, object]]:
    """The refusals of the sixth snapshot on a carried field that the seventh does not hold as they
    were, for the civilisations of this pack: what T772 closed."""
    sixth = _rows(_SIXTH_DIRECTORY)
    source = _rows(_SOURCE_DIRECTORY)
    return [
        r
        for r in sixth
        if r["modelled"] == "no"
        and r["field"] in _CARRIED
        and r["civilisation"] not in _NOT_IN_THIS_PACK
        and r not in source
    ]


def _counterpart(row: Mapping[str, object]) -> dict[str, object]:
    """The second snapshot's refusal for the source's: the same bullet and field."""
    (found,) = [
        r
        for r in _old()
        if _key(r) == _key(row) and r["modelled"] == "no" and r["field"] in _CARRIED
    ]
    return found


def _replacements(refusal: Mapping[str, object]) -> list[dict[str, object]]:
    """The rows that closed the refusal: the source rows of its bullet and field that the sixth
    snapshot did not have, leaving out a row the sixth had and T772 only amended (a sentence in its
    `validated_by`)."""
    sixth, source = _rows(_SIXTH_DIRECTORY), _rows(_SOURCE_DIRECTORY)
    before = [_without_validation(r) for r in sixth]
    return [s for s in source if _key(s) == _key(refusal) and _without_validation(s) not in before]


def test_t772_closed_sixteen_refusals_in_this_pack_and_the_five_not_reached_are_the_rest() -> None:
    closed = _closed_by_t772()
    groups = {(str(r["civilisation"]), str(r["field"])) for r in closed}
    assert groups == _REACHED | _NOT_REACHED
    assert len(groups) == 16
    assert not _REACHED & _NOT_REACHED


def test_a_refusal_is_replaced_exactly_when_the_three_conditions_hold_for_it_and_its_rows() -> None:
    """The decision is recomputed from both packs and the notes table, never read from the file:
    the second snapshot's refusal leaves the third if every row that closed it passes (and the
    refusal itself passes), and stays, identical, if any row fails."""
    new = _new()
    reached: set[tuple[str, str]] = set()
    for refusal in _closed_by_t772():
        mine = _counterpart(refusal)
        replacements = _replacements(refusal)
        passes = _row_failures(refusal, mine).carried and all(
            _row_failures(s, mine).carried for s in replacements
        )
        group = (str(refusal["civilisation"]), str(refusal["field"]))
        if passes:
            reached.add(group)
            assert mine not in new, group
            for s in replacements:
                assert any(
                    _without_validation(r) == _without_validation(s) and r in _added() for r in new
                ), group
        else:
            assert mine in new, group
            assert not any(
                _without_validation(r) == _without_validation(s) for s in replacements for r in new
            ), group
    assert reached == _REACHED


def test_each_refusal_left_open_fails_the_third_condition_and_only_it() -> None:
    new = _new()
    for civilisation, field in sorted(_NOT_REACHED):
        (refusal,) = [
            r for r in _closed_by_t772() if (r["civilisation"], r["field"]) == (civilisation, field)
        ]
        mine = _counterpart(refusal)
        assert mine in new
        failures = _row_failures(refusal, mine)
        assert not failures.carried
        conditions = failures.conditions
        assert conditions["bullet is byte-identical"], (civilisation, field)
        assert conditions["identifiers resolve to the same"], (civilisation, field)
        assert not conditions["release notes name no change"], (civilisation, field)
        assert "Not carried from the build 185872 snapshot" in str(mine["validated_by"])


def test_the_selectors_the_readings_widen_are_in_this_pack_and_in_no_note_line() -> None:
    """The nine identifiers T772 added to a selector (the Bombard Tower, the Sicilians' walls, gates
    and palisades, four Jurchens technologies) are each in this pack under the source snapshot's
    name, with the source snapshot's data, so a reading that names them reaches this build."""
    widened = {
        "building": ("236", "117", "487", "72", "792"),
        "technology": ("50", "51", "54", "321"),
    }
    here, there = _rules(), _source_rules()
    for kind, identifiers in widened.items():
        for identifier in identifiers:
            assert identifier in here[kind], (kind, identifier)
            assert here[kind][identifier] == there[kind][identifier], (kind, identifier)


def _source_rules() -> dict[str, dict[str, dict[str, object]]]:
    import json

    parsed: dict[str, dict[str, dict[str, object]]] = json.loads(
        _snapshot_root(_SOURCE_DIRECTORY).joinpath("rules.json").read_text(encoding="utf-8")
    )["entities"]
    return parsed


def test_the_updates_the_readings_cite_are_carried_from_the_update_not_from_build_185872() -> None:
    rows = {_key(r): r for r in _added() if _CARRIED_MARK in str(r["validated_by"])}
    sicilians = [r for r in rows.values() if r["civilisation"] == "Sicilians"]
    (sicilians_row,) = sicilians
    assert "carried from update 111772" in str(sicilians_row["validated_by"])
    assert "only which entities the bonus reaches is attributed to build 185872" in str(
        sicilians_row["validated_by"]
    )
    (turks_row,) = [r for r in rows.values() if r["civilisation"] == "Turks"]
    assert "carried from update 47820" in str(turks_row["validated_by"])
    for other in rows.values():
        if other["civilisation"] not in ("Sicilians", "Turks"):
            assert "carried from update" not in str(other["validated_by"])


# ----------------------------------------------------------------------------- the open rows


def test_the_five_rows_not_carried_still_refuse_every_entity_they_select() -> None:
    contexts = {
        "Turks": _ctx("Turks"),
        "Aztecs": _ctx("Aztecs"),
        "Magyars": _ctx("Magyars", researched=frozenset({"514"})),
        "Malay": _ctx("Malay", researched=frozenset({"625"})),
        "Gurjaras": _ctx("Gurjaras"),
    }
    for civilisation, field in sorted(_NOT_REACHED):
        (refusal,) = [
            r
            for r in _new()
            if r["civilisation"] == civilisation
            and r["field"] == field
            and r["modelled"] == "no"
            and "Not carried from the build 185872 snapshot" in str(r["validated_by"])
        ]
        for entry in refusal["selector"]:  # type: ignore[attr-defined]
            kind, identifier = entry["kind"], entry["id"]
            function = query.cost if field == "cost" else query.production_time
            got = function(  # type: ignore[operator]
                _entity(kind, identifier), civilisation=civilisation, context=contexts[civilisation]
            )
            assert isinstance(got, gaps.KnowledgeGap), (civilisation, kind, identifier)
            assert got.cause == "effect-not-modelled"
            assert got.severity == gaps.BLOCKING


# --------------------------------------------------------------------------------- the values


def test_detinets_moves_forty_percent_of_the_stone_to_wood_and_reaches_the_bombard_tower() -> None:
    owner = {
        82: {"wood": 260, "stone": 390},
        79: {"wood": 85, "stone": 75},
        234: {"wood": 85, "stone": 75},
        235: {"wood": 85, "stone": 75},
        236: {"wood": 50, "stone": 75, "gold": 100},
    }
    detinets = _ctx("Slavs", researched=frozenset({"455"}))
    for building, reading in owner.items():
        base = _baseline("building", building, "cost")
        stone = base["stone"]  # type: ignore[index]
        moved = _half_up(stone * 0.4)
        derived = {**base, "stone": stone - moved, "wood": base["wood"] + moved}  # type: ignore[dict-item,operator]
        assert {k: v for k, v in derived.items() if k in reading} == reading, building
        assert _cost("building", building, "Slavs", detinets) == derived
        assert _cost("building", building, "Slavs", _ctx("Slavs")) == base
        assert _cost("building", building, "Mongols", _ctx("Mongols")) == base
    with pytest.raises(effects.ContextRequired):
        query.cost(_entity("building", 236), civilisation="Slavs")


def test_the_sicilians_fortifications_include_walls_gates_palisades_and_the_tower_line() -> None:
    for building in (79, 234, 235, 236, 117, 487, 72, 792, 82, 1665):
        base = _baseline("building", building, "construction_time")
        assert _time("building", building, "Sicilians", _ctx("Sicilians")) == pytest.approx(
            base / 1.5  # type: ignore[operator]
        ), building
        assert _time("building", building, "Franks", _ctx("Franks")) == base
    # Not the Dock; the Krepost is not named, so it answers the baseline wherever the pack has it.
    for building in (45, 1251):
        if str(building) in _rules()["building"]:
            assert _time("building", building, "Sicilians", _ctx("Sicilians")) == _baseline(
                "building", building, "construction_time"
            )


def test_the_chinese_discount_does_not_reach_the_age_advances() -> None:
    for age_advance, age in ((102, 2), (103, 3)):
        base = _baseline("technology", age_advance, "cost")
        for at in range(age, 5):
            assert _cost("technology", age_advance, "Chinese", _ctx("Chinese", age=at)) == base
    base = _baseline("technology", 199, "cost")
    assert _cost("technology", 199, "Chinese", _ctx("Chinese", age=3)) == {
        resource: _half_up(amount * 0.9)  # type: ignore[operator]
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
    assert _baseline("technology", 64, "cost") == {"food": 800, "wood": 400}
    assert _baseline("technology", 376, "cost") == {"gold": 500, "wood": 525}
    for technology in (10, 369):
        assert _cost("technology", technology, "Turks", _ctx("Turks")) == _baseline(
            "technology", technology, "cost"
        )
    # Cannon Galleon (scrapped in update 47820) is no technology of this pack either.
    names = {
        str(rec["name"]).replace("<br>\n", " ")
        for rec in _rules()["technology"].values()
        if rec["name"]
    }
    assert "Cannon Galleon" not in names


def test_the_vietnamese_economic_upgrades_cost_no_wood_and_research_twice_as_fast() -> None:
    for technology in (213, 249, 65, 906):
        base = _baseline("technology", technology, "cost")
        assert _cost("technology", technology, "Vietnamese", _ctx("Vietnamese")) == {
            **base,  # type: ignore[dict-item]
            "wood": 0,
        }
        assert _cost("technology", technology, "Franks", _ctx("Franks")) == base
    for technology in (213, 249, 65, 906, 15, 48):
        base_time = _baseline("technology", technology, "research_time")
        assert _time("technology", technology, "Vietnamese", _ctx("Vietnamese")) == (
            pytest.approx(base_time / 2)  # type: ignore[operator]
        )
    for technology in (22, 17, 23):
        assert _time("technology", technology, "Vietnamese", _ctx("Vietnamese")) == _baseline(
            "technology", technology, "research_time"
        )


def test_the_burgundian_economic_upgrades_cost_forty_percent_less_food_and_come_a_age_earlier() -> (
    None
):
    for technology, age in {213: 1, 906: 1, 249: 2, 65: 2, 48: 2, 15: 3}.items():
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
    for technology in (17, 23):
        assert _cost("technology", technology, "Burgundians", _ctx("Burgundians")) == _baseline(
            "technology", technology, "cost"
        )


def test_hussite_reforms_replaces_the_gold_of_the_monk_and_each_monastery_technology() -> None:
    reformed = _ctx("Bohemians", researched=frozenset({"785"}))
    members = [("unit", 125)] + [
        ("technology", t) for t in (45, 46, 230, 231, 233, 252, 316, 319, 438, 439, 441)
    ]
    for kind, entity in members:
        base = _baseline(kind, entity, "cost")
        food, gold = base["food"], base["gold"]  # type: ignore[index]
        assert _cost(kind, entity, "Bohemians", reformed) == {"food": food + gold, "gold": 0}
        assert _cost(kind, entity, "Bohemians", _ctx("Bohemians")) == base
        assert _cost(kind, entity, "Franks", _ctx("Franks")) == base
    assert _cost("unit", 125, "Bohemians", reformed) == {"food": 100, "gold": 0}
    assert _cost("technology", 233, "Bohemians", reformed) == {"food": 120, "gold": 0}


def test_the_jurchens_list_is_the_owners_complete_list() -> None:
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


_FUNCTIONS = {
    "cost": query.cost,
    "production_time": query.production_time,
    "age_requirement": query.age_requirement,
}


def test_every_entity_a_carried_row_selects_answers_what_build_185872_answers() -> None:
    """The carry's own claim, asked of the library: for each entity a carried row selects, the
    answer under build 180059's snapshot equals the answer under build 185872's for the same
    civilisation, field and context, at every age and with the owner's team and technologies."""
    asked = 0
    for row in _added():
        if row["modelled"] != "yes" or _AMENDED_MARK in str(row["validated_by"]):
            continue
        civilisation, field = str(row["civilisation"]), str(row["field"])
        researched = frozenset(
            {str(row["condition_technology"])} if row.get("condition_technology") else ()
        )
        for entry in row["selector"]:  # type: ignore[attr-defined]
            kind, identifier = entry["kind"], entry["id"]
            for age in (1, 2, 3, 4):
                context = _ctx(civilisation, researched=researched, age=age)
                here = _FUNCTIONS[field](  # type: ignore[operator]
                    _entity(kind, identifier, _BUILD), civilisation=civilisation, context=context
                )
                there = _FUNCTIONS[field](  # type: ignore[operator]
                    _entity(kind, identifier, 185872), civilisation=civilisation, context=context
                )
                assert not isinstance(here, gaps.KnowledgeGap), (civilisation, kind, identifier)
                assert here.value == there.value, (civilisation, field, kind, identifier, age)  # type: ignore[attr-defined]
                asked += 1
    assert asked > 300


# ----------------------------------------------------------------------------------- the record


def test_the_validation_record_names_the_carry_and_what_was_not_checked() -> None:
    resolved = snapshot.snapshot_for(_BUILD)
    assert isinstance(resolved, snapshot.Snapshot)
    assert resolved.validation is not None
    record = resolved.validation
    assert record.performed_at == "2026-11-01"
    assert "AI agent" in record.performed_by
    assert "T774" in record.checked_against
    assert _SOURCE_DIGEST in record.checked_against
    not_checked = record.details["not_checked"]
    assert "T774" in not_checked
    assert "not a game reading" in not_checked or "compared with the game" in not_checked
    for name in ("Turks", "Aztecs", "Magyars", "Malay", "Gurjaras"):
        assert name in not_checked, name


# ---------------------------------------------------------------------------------- the sheet


def test_the_sheet_holds_an_open_row_for_exactly_the_five_rows_not_carried() -> None:
    sheet = _OWNER_READINGS.read_text(encoding="utf-8")
    assert "T774" in sheet
    assert _DIRECTORY in sheet
    section = sheet[sheet.index("## Open values") : sheet.index("## Validation sample")]
    rows = [line for line in section.splitlines() if line.startswith("| 180059 |")]
    found = set()
    for line in rows:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        # Open: the four answer columns are empty.
        assert not any(cells[-4:]), line[:80]
        found.add((cells[1], cells[3]))
    assert found == _NOT_REACHED
