"""Tests for the document validator (T619), written first as T620.

API chosen here, which T619 must implement in ``aoe2stats_core.truth.validate``:

- ``validate(document, register) -> None``. ``document`` is the published analysis as a mapping;
  ``register`` maps a datum id to an entry exposing ``path`` (``str | None``: the document path
  that carries it, dict keys joined by ``.`` and every list index collapsed to ``[]``, e.g.
  ``participants[].age_up_commands[]``; ``None`` for a datum that only lives under ``inferred``),
  ``tier`` (``Tier``), ``status`` (``"published"``, ``"planned"`` or ``"blocked"``), ``non_claim``
  (``str | None``) and ``requires_knowledge`` (``tuple[str, ...]``, **bare field names** such as
  ``"cost"``, exactly as ``register.toml`` writes them; rule 8 matches them against a gap's bare
  ``field``, against the gap's ``prevents`` list of datum ids, and, for a whole-build gap, against
  any knowledge at all, and never reads the gap's ``severity``: T666k). Injecting the register
  keeps the validator testable before the loader (T615) exists; production passes the loaded one.
- Raises ``DocumentInvalid`` (a ``ValueError``) carrying ``rules``, a ``frozenset[int]`` of the
  contract rule numbers (1 to 10) that were violated, and a message naming each violation. It
  reports every violated rule, not only the first.
- ``identity_digest(identity) -> str``: the digest of an identity mapping over every field except
  ``digest`` itself; rule 10 compares ``identity["digest"]`` against it.
- Leaves outside rule 1 are the wall-clock set (``envelope``, ``extracted_at``) and the blocks
  ``identity``, ``provenance``, ``knowledge_gaps``; the ``inferred`` block is checked per rules
  5 to 7 instead, its instances being keyed by datum id. ``schema_version`` is not outside rule 1:
  it is a published datum and carries a provenance entry like any other (FR-007).
- A register path ending ``.*`` covers exactly one key of the mapping at its prefix, whose value is
  a scalar of the type the validator declares for that path (T656, T666a): a dependency name to a
  version string, an age-technology id to a command time in milliseconds. Nothing nested beneath the
  key, no other value type, and no wildcard path the validator does not declare is covered; an exact
  path is exact.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

import pytest

from aoe2stats_core.truth.tiers import Tier


@dataclass(frozen=True)
class Entry:
    path: str | None
    tier: Tier
    status: str = "published"
    non_claim: str | None = None
    requires_knowledge: tuple[str, ...] = ()


def _register() -> dict[str, Entry]:
    return {
        "document.schema_version": Entry("schema_version", Tier.OBSERVED),
        "match.game_id": Entry("game_id", Tier.OBSERVED),
        "participant.civ_id": Entry("participants[].civ_id", Tier.OBSERVED),
        "participant.age_up_commands": Entry("participants[].age_up_commands[]", Tier.OBSERVED),
        "participant.villagers_ordered": Entry("participants[].villagers_ordered", Tier.DECODED),
        "participant.build_count": Entry("participants[].build_count", Tier.RECONSTRUCTED),
        "participant.pace": Entry("participants[].pace", Tier.DERIVED),
        "participant.coaching_note": Entry("participants[].coaching_note", Tier.INFERRED),
        "participant.group_control_lost": Entry(
            None, Tier.INFERRED, non_claim="not a casualty count"
        ),
        "participant.army_cost": Entry(
            "participants[].army_cost", Tier.DERIVED, requires_knowledge=("cost",)
        ),
        "participant.planned_thing": Entry(
            "participants[].planned_thing", Tier.OBSERVED, "planned"
        ),
    }


def _prov(tier: str, inputs: list[str] | None = None) -> dict[str, Any]:
    return {"tier": tier, "method": "some-method@1", "inputs": inputs or []}


def _identity() -> dict[str, Any]:
    from aoe2stats_core.truth.validate import identity_digest

    identity: dict[str, Any] = {
        "recording": {"object_key": "k", "sha256": "ab"},
        "parser": {"name": "aoe2rec-py", "version": "1.0"},
        "parser_dependencies": {"aoe2rec-py": "1.0"},
        "knowledge": {"source": "s", "source_version": "1", "describes_build": 1, "digest": "d"},
        "reconstruction_engine": "not-applicable",
        "analytics": "a1",
    }
    identity["digest"] = identity_digest(identity)
    return identity


def _good() -> dict[str, Any]:
    return {
        "schema_version": 2,
        "envelope": {"extracted_at": "2026-01-01T00:00:00Z"},
        "extracted_at": "2026-01-01T00:00:00Z",
        "game_id": 7,
        "participants": [
            {"civ_id": 3, "age_up_commands": [100, 200], "villagers_ordered": 4, "pace": 2}
        ],
        "identity": _identity(),
        "provenance": {
            "document.schema_version": _prov("observed"),
            "match.game_id": _prov("observed"),
            "participant.civ_id": _prov("observed"),
            "participant.age_up_commands": _prov("observed"),
            "participant.villagers_ordered": _prov("decoded"),
            "participant.pace": _prov("derived", ["participant.civ_id"]),
            "participant.group_control_lost": {
                "tier": "inferred",
                "method": "group-silence@1",
                "inputs": ["participant.villagers_ordered"],
            },
        },
        "inferred": {
            "participant.group_control_lost": [
                {
                    "participant": 1,
                    "from_ms": 0,
                    "units": 2,
                    "confidence": {"level": "medium", "basis": "silence lasted 40 s"},
                    "non_claim": "not a casualty count",
                }
            ]
        },
        "knowledge_gaps": [],
    }


def _rejected(doc: dict[str, Any], *rules: int) -> None:
    from aoe2stats_core.truth.validate import DocumentInvalid, validate

    with pytest.raises(DocumentInvalid) as info:
        validate(doc, _register())
    assert set(rules) <= info.value.rules
    assert str(info.value)


def test_a_conforming_document_is_accepted() -> None:
    from aoe2stats_core.truth.validate import validate

    validate(_good(), _register())


def test_the_schema_version_is_a_published_datum_and_owes_a_provenance_entry() -> None:
    doc = _good()
    del doc["provenance"]["document.schema_version"]
    _rejected(doc, 2)


def test_the_wall_clock_set_is_exempt_from_the_register() -> None:
    from aoe2stats_core.truth.validate import validate

    doc = _good()
    doc["envelope"]["anything_at_all"] = "2026"
    validate(doc, _register())


# SC-001, rule 1


def test_a_leaf_with_no_register_entry_is_rejected() -> None:
    doc = _good()
    doc["participants"][0]["mystery_stat"] = 5
    _rejected(doc, 1)


def test_a_leaf_resolving_to_a_planned_datum_is_rejected() -> None:
    doc = _good()
    doc["participants"][0]["planned_thing"] = 5
    doc["provenance"]["participant.planned_thing"] = _prov("observed")
    _rejected(doc, 1)


def test_a_leaf_resolving_to_two_data_is_rejected() -> None:
    from aoe2stats_core.truth.validate import DocumentInvalid, validate

    register = _register()
    register["participant.civ_id_twin"] = Entry("participants[].civ_id", Tier.OBSERVED)
    with pytest.raises(DocumentInvalid) as info:
        validate(_good(), register)
    assert 1 in info.value.rules


# SC-002, rules 2 to 5


def test_a_datum_without_provenance_is_rejected() -> None:
    doc = _good()
    del doc["provenance"]["participant.civ_id"]
    _rejected(doc, 2)


def test_a_provenance_key_absent_from_the_document_is_rejected() -> None:
    doc = _good()
    doc["provenance"]["participant.build_count"] = _prov("reconstructed")
    _rejected(doc, 2)


def test_a_value_missing_its_tier_is_rejected() -> None:
    doc = _good()
    del doc["provenance"]["participant.civ_id"]["tier"]
    _rejected(doc, 3)


def test_a_tier_that_differs_from_the_register_is_rejected() -> None:
    doc = _good()
    doc["provenance"]["participant.civ_id"]["tier"] = "decoded"
    _rejected(doc, 3)


def test_a_tier_stronger_than_the_weakest_input_is_rejected() -> None:
    doc = _good()
    doc["provenance"]["participant.pace"]["inputs"] = ["participant.group_control_lost"]
    _rejected(doc, 3)


@pytest.mark.parametrize("bad", [None, "", "   "])
def test_an_entry_without_a_method_is_rejected(bad: str | None) -> None:
    doc = _good()
    doc["provenance"]["participant.civ_id"]["method"] = bad
    _rejected(doc, 4)


def test_an_entry_with_no_method_key_is_rejected() -> None:
    doc = _good()
    del doc["provenance"]["participant.civ_id"]["method"]
    _rejected(doc, 4)


def test_an_inferred_instance_missing_its_confidence_is_rejected() -> None:
    doc = _good()
    del doc["inferred"]["participant.group_control_lost"][0]["confidence"]
    _rejected(doc, 5)


@pytest.mark.parametrize("basis", ["", "   ", None])
def test_an_inferred_instance_with_an_empty_basis_is_rejected(basis: str | None) -> None:
    doc = _good()
    doc["inferred"]["participant.group_control_lost"][0]["confidence"]["basis"] = basis
    _rejected(doc, 5)


def test_an_inferred_instance_missing_its_basis_key_is_rejected() -> None:
    doc = _good()
    del doc["inferred"]["participant.group_control_lost"][0]["confidence"]["basis"]
    _rejected(doc, 5)


@pytest.mark.parametrize("level", ["certain", "", 0.9, 2, "0.9", None])
def test_a_confidence_level_outside_the_closed_set_is_rejected(level: object) -> None:
    doc = _good()
    doc["inferred"]["participant.group_control_lost"][0]["confidence"]["level"] = level
    _rejected(doc, 5)


def test_a_second_instance_is_checked_as_well_as_the_first() -> None:
    doc = _good()
    second = copy.deepcopy(doc["inferred"]["participant.group_control_lost"][0])
    del second["confidence"]
    doc["inferred"]["participant.group_control_lost"].append(second)
    _rejected(doc, 5)


# SC-003, rule 6: once per tier boundary, not once overall.

BOUNDARIES = [Tier.OBSERVED, Tier.DECODED, Tier.RECONSTRUCTED]


@pytest.mark.parametrize("claimed", BOUNDARIES, ids=lambda t: t.value)
def test_a_coaching_conclusion_typed_at_a_stronger_tier_is_rejected(claimed: Tier) -> None:
    """The coaching datum is inferred; it sits outside ``inferred`` and claims a stronger tier."""
    doc = _good()
    doc["participants"][0]["coaching_note"] = "player 1 should have walled earlier"
    doc["provenance"]["participant.coaching_note"] = _prov(claimed.value)
    _rejected(doc, 6)


@pytest.mark.parametrize("claimed", BOUNDARIES, ids=lambda t: t.value)
def test_a_coaching_conclusion_with_honest_tier_outside_inferred_is_rejected(
    claimed: Tier,
) -> None:
    """Even truthfully tiered, an inferred datum outside ``inferred`` fails: rule 6, first half."""
    doc = _good()
    doc["participants"][0]["coaching_note"] = "player 1 should have walled earlier"
    doc["provenance"]["participant.coaching_note"] = {
        "tier": "inferred",
        "method": "coach@1",
        "inputs": ["participant.civ_id"],
        "confidence": {"level": "low", "basis": f"boundary {claimed.value}"},
    }
    _rejected(doc, 6)


@pytest.mark.parametrize(
    "datum",
    [
        "participant.civ_id",
        "participant.villagers_ordered",
        "participant.build_count",
        "participant.pace",
    ],
)
def test_a_stronger_tier_datum_inside_inferred_is_rejected(datum: str) -> None:
    doc = _good()
    doc["inferred"][datum] = [
        {"confidence": {"level": "low", "basis": "b"}, "value": "player 1 should have walled"}
    ]
    _rejected(doc, 6)


def test_an_inferred_datum_is_accepted_only_under_inferred() -> None:
    from aoe2stats_core.truth.validate import validate

    validate(_good(), _register())


# Rule 7


def test_an_instance_missing_a_declared_non_claim_is_rejected() -> None:
    doc = _good()
    del doc["inferred"]["participant.group_control_lost"][0]["non_claim"]
    _rejected(doc, 7)


def test_a_non_claim_is_required_on_every_instance() -> None:
    doc = _good()
    second = copy.deepcopy(doc["inferred"]["participant.group_control_lost"][0])
    second["non_claim"] = ""
    doc["inferred"]["participant.group_control_lost"].append(second)
    _rejected(doc, 7)


# Rule 8


def _gap(
    severity: str,
    field: str | None = "cost",
    prevents: tuple[str, ...] = ("participant.army_cost",),
) -> dict[str, Any]:
    """A gap as the coverage pass records it: ``prevents`` names register data, never fields. With
    ``field=None`` it is the whole-build gap, which names no entity and no field."""
    return {
        "entity": None if field is None else {"kind": "unit", "id": 0},
        "field": field,
        "build": 1,
        "civilisation": None if field is None else 0,
        "cause": "no-snapshot-for-build" if field is None else "field-absent",
        "prevents": list(prevents) if severity == "blocking" else [],
        "severity": severity,
    }


def _with_army_cost() -> dict[str, Any]:
    doc = _good()
    doc["participants"][0]["army_cost"] = 10
    doc["provenance"]["participant.army_cost"] = _prov("derived", ["participant.civ_id"])
    return doc


def test_a_datum_depending_on_a_blocking_gap_is_rejected() -> None:
    doc = _with_army_cost()
    doc["knowledge_gaps"] = [_gap("blocking")]
    _rejected(doc, 8)


def test_a_gap_on_a_field_no_present_datum_requires_withholds_nothing() -> None:
    """Whatever the gap's severity or ``prevents`` say, rule 8 withholds only the data that need
    the gap's field (or, for a whole-build gap, any knowledge)."""
    from aoe2stats_core.truth.validate import validate

    doc = _with_army_cost()
    doc["knowledge_gaps"] = [
        _gap("informational", "production_time"),
        _gap("blocking", "production_time", ("participant.something_else",)),
        {**_gap("blocking", "production_time"), "prevents": []},
    ]
    validate(doc, _register())


def test_a_gap_mislabelled_informational_on_a_required_field_still_withholds() -> None:
    """The second lock must not lean on the first: the builder computes severity from ``prevents``,
    so a gap labelled informational on a field a present datum requires is a builder fault, and the
    validator refuses the datum from the register's own ``requires_knowledge``. FR-037 defines
    informational as "no currently published value depends on it"; a present datum is published,
    so no severity makes it safe."""
    doc = _with_army_cost()
    doc["knowledge_gaps"] = [_gap("informational", "cost")]
    _rejected(doc, 8)


def test_a_blocking_gap_with_an_empty_prevents_on_a_required_field_still_withholds() -> None:
    doc = _with_army_cost()
    doc["knowledge_gaps"] = [{**_gap("blocking", "cost"), "prevents": []}]
    _rejected(doc, 8)


def test_a_gap_missing_its_prevents_and_severity_on_a_required_field_still_withholds() -> None:
    doc = _with_army_cost()
    gap = _gap("blocking", "cost")
    del gap["prevents"], gap["severity"]
    doc["knowledge_gaps"] = [gap]
    _rejected(doc, 8)


def test_a_whole_build_gap_mislabelled_informational_still_withholds() -> None:
    doc = _with_army_cost()
    doc["knowledge_gaps"] = [_gap("informational", None, ())]
    _rejected(doc, 8)


def test_a_field_gap_withholds_only_the_data_that_need_that_field() -> None:
    from aoe2stats_core.truth.validate import DocumentInvalid, validate

    register = _register()
    register["participant.pace"] = Entry(
        "participants[].pace", Tier.DERIVED, requires_knowledge=("production_time",)
    )
    doc = _with_army_cost()  # pace is already in the document
    doc["knowledge_gaps"] = [_gap("informational", "production_time")]

    with pytest.raises(DocumentInvalid) as info:
        validate(doc, register)

    assert info.value.rules == frozenset({8})
    assert "participant.pace" in str(info.value)
    assert "participant.army_cost" not in str(info.value)


def test_rule_8_reads_the_gaps_prevents_not_a_kind_dot_field_key() -> None:
    """The bug's shape: ``requires_knowledge`` is bare field names and the old rule compared it to
    ``"<kind>.<field>"``, so no real gap could ever intersect it. Here the gap's field equals the
    datum's requirement exactly and ``prevents`` names the datum; the datum is refused."""
    doc = _with_army_cost()
    doc["knowledge_gaps"] = [_gap("blocking", "cost", ("participant.army_cost",))]
    _rejected(doc, 8)


def test_a_whole_build_gap_withholds_every_datum_that_needs_any_knowledge() -> None:
    """It names no entity and no field, so no field key could ever match it. It blocks the datum
    that needs knowledge even when its ``prevents`` list is empty, and no other."""
    from aoe2stats_core.truth.validate import validate

    doc = _with_army_cost()
    doc["knowledge_gaps"] = [_gap("blocking", None, ())]
    _rejected(doc, 8)

    unaffected = _good()  # no datum present needs knowledge
    unaffected["knowledge_gaps"] = [_gap("blocking", None, ())]
    validate(unaffected, _register())


# Rules 9 and 10


def test_empty_parser_dependencies_are_rejected() -> None:
    from aoe2stats_core.truth.validate import identity_digest

    doc = _good()
    doc["identity"]["parser_dependencies"] = {}
    doc["identity"]["digest"] = identity_digest(doc["identity"])
    _rejected(doc, 9)


def test_a_digest_that_does_not_recompute_is_rejected() -> None:
    doc = _good()
    doc["identity"]["digest"] = "0" * 64
    _rejected(doc, 10)


def test_a_changed_identity_field_breaks_the_digest() -> None:
    doc = _good()
    doc["identity"]["analytics"] = "a2"
    _rejected(doc, 10)


def test_the_digest_covers_every_field_but_itself() -> None:
    from aoe2stats_core.truth.validate import identity_digest

    identity = _identity()
    other = {**identity, "analytics": "a2"}
    assert identity_digest(identity) != identity_digest(other)
    assert identity_digest(identity) == identity_digest({**identity, "digest": "ignored"})


def test_a_document_without_identity_is_rejected() -> None:
    doc = _good()
    del doc["identity"]
    _rejected(doc, 9)


# Contrast cases for the boundaries


def test_every_violated_rule_is_reported_not_only_the_first() -> None:
    doc = _good()
    doc["participants"][0]["mystery_stat"] = 5
    doc["identity"]["digest"] = "0" * 64
    _rejected(doc, 1, 10)


def test_a_tier_equal_to_its_weakest_input_is_accepted() -> None:
    from aoe2stats_core.truth.validate import validate

    doc = _good()
    doc["provenance"]["participant.pace"]["inputs"] = ["participant.pace"]
    validate(doc, _register())


def test_an_inferred_key_with_no_register_entry_is_rejected() -> None:
    doc = _good()
    doc["inferred"]["participant.invented"] = [{"confidence": {"level": "low", "basis": "b"}}]
    _rejected(doc, 1)


def test_an_empty_list_leaf_still_resolves_to_its_datum() -> None:
    from aoe2stats_core.truth.validate import validate

    doc = _good()
    doc["participants"][0]["age_up_commands"] = []
    validate(doc, _register())


def test_a_blocking_gap_does_not_withhold_a_datum_that_is_absent() -> None:
    from aoe2stats_core.truth.validate import validate

    doc = _good()
    doc["knowledge_gaps"] = [_gap("blocking")]
    validate(doc, _register())


def test_a_datum_with_no_declared_non_claim_needs_none() -> None:
    from aoe2stats_core.truth.validate import validate

    register = _register()
    doc = _good()
    doc["provenance"]["participant.coaching_note"] = _prov("inferred", ["participant.civ_id"])
    doc["inferred"]["participant.coaching_note"] = [
        {"confidence": {"level": "high", "basis": "b"}, "value": "x"}
    ]
    validate(doc, register)


# Wildcard paths (T656): the register publishes `engine.deps.*` and
# `participants[].age_up_commands.*` for mappings whose keys are data. A `.*` path covers exactly
# one key of the mapping at its prefix, whose value is a scalar of the declared type (T666a); an
# exact path stays exact.


def _wild_register() -> dict[str, Entry]:
    register = _register()
    register["engine.dependencies"] = Entry("engine.deps.*", Tier.OBSERVED)
    register["participant.age_up_commands"] = Entry(
        "participants[].age_up_commands.*", Tier.OBSERVED
    )
    return register


def _wild_good() -> dict[str, Any]:
    doc = _good()
    doc["engine"] = {"deps": {"aoe2rec-py": "1.0", "zope.interface": "7.0"}}
    doc["participants"][0]["age_up_commands"] = {"101": 100, "102": 200}
    doc["provenance"]["engine.dependencies"] = _prov("observed")
    return doc


def _wild_rejected(doc: dict[str, Any], *rules: int, exact: bool = True) -> str:
    from aoe2stats_core.truth.validate import DocumentInvalid, validate

    with pytest.raises(DocumentInvalid) as info:
        validate(doc, _wild_register())
    if exact:
        assert info.value.rules == frozenset(rules)
    else:
        assert set(rules) <= info.value.rules
    return str(info.value)


def test_a_leaf_beneath_a_wildcard_path_is_accepted_and_the_datum_counts_as_present() -> None:
    from aoe2stats_core.truth.validate import validate

    validate(_wild_good(), _wild_register())  # keys with dots in them are still beneath the prefix

    doc = _wild_good()
    del doc["provenance"]["engine.dependencies"]
    _wild_rejected(doc, 2)  # present, so its provenance entry is owed


@pytest.mark.parametrize(
    "where, leaf",
    [
        ("engine", "depsX"),  # a sibling that merely shares the prefix's characters
        ("engine", "other"),  # a sibling under the same parent
        ("participants[0]", "age_up_commandsX"),
    ],
)
def test_a_leaf_at_a_sibling_of_a_wildcard_prefix_is_rejected(where: str, leaf: str) -> None:
    doc = _wild_good()
    target = doc["engine"] if where == "engine" else doc["participants"][0]
    target[leaf] = {"foo": 1} if leaf == "depsX" else 1

    message = _wild_rejected(doc, 1)

    assert leaf in message


def test_the_bare_prefix_does_not_satisfy_presence() -> None:
    """``engine.deps`` empty has no leaf beneath the wildcard: nothing is present, so a provenance
    entry for it names something not in the document (rule 2). The empty mapping itself is not a
    rule 1 violation — it carries no value, like an empty list whose elements are described further
    down — and the empty record is refused by rule 9 where it matters."""
    doc = _wild_good()
    doc["engine"]["deps"] = {}

    message = _wild_rejected(doc, 2)
    assert "engine.dependencies" in message

    del doc["provenance"]["engine.dependencies"]
    from aoe2stats_core.truth.validate import validate

    validate(doc, _wild_register())


def test_a_scalar_at_the_bare_prefix_is_rejected_not_taken_for_a_mapping() -> None:
    doc = _wild_good()
    doc["engine"]["deps"] = "1.0"

    _wild_rejected(doc, 1, 2, exact=False)


def test_an_exact_path_is_not_widened() -> None:
    doc = _wild_good()
    doc["game_id"] = {"nested": 7}
    doc["participants"][0]["civ_id"] = {"nested": 3}

    message = _wild_rejected(doc, 1, 2, exact=False)

    assert "game_id.nested" in message
    assert "participants[].civ_id.nested" in message


def test_two_wildcards_covering_one_leaf_are_ambiguous() -> None:
    register = _wild_register()
    register["engine.dependencies_twin"] = Entry("engine.deps.*", Tier.OBSERVED)
    from aoe2stats_core.truth.validate import DocumentInvalid, validate

    with pytest.raises(DocumentInvalid) as info:
        validate(_wild_good(), register)

    assert 1 in info.value.rules


def test_a_wildcard_does_not_resolve_planned_data() -> None:
    register = _wild_register()
    register["engine.dependencies"] = Entry("engine.deps.*", Tier.OBSERVED, "planned")
    from aoe2stats_core.truth.validate import DocumentInvalid, validate

    with pytest.raises(DocumentInvalid) as info:
        validate(_wild_good(), register)

    assert 1 in info.value.rules


# A wildcard covers one key with a scalar value (T666a, FR-011, SC-003). Without that, a prose
# verdict nested under a mapping whose keys are data passed as an observed value.


def _under(doc: dict[str, Any], where: str) -> dict[str, Any]:
    target: dict[str, Any] = (
        doc["engine"]["deps"] if where == "deps" else doc["participants"][0]["age_up_commands"]
    )
    return target


@pytest.mark.parametrize(
    "where, key, value",
    [
        ("deps", "verdict", {"player_1": "lost the fight"}),  # a nested mapping
        ("deps", "zope.interface", {"7": "ok"}),  # a real name, one level too deep
        ("deps", "verdict", ["lost the fight"]),  # a list
        ("deps", "aoe2rec-py", 1),  # a version is a string
        ("deps", "verdict", None),
        ("commands", "coaching_note", "should have walled earlier"),  # prose, not a time
        ("commands", "101", {"at": 1}),
        ("commands", "101", [100]),
        ("commands", "101", True),  # a bool is not a time
        ("commands", "101", None),
    ],
)
def test_a_wildcard_refuses_a_value_that_is_not_its_one_scalar(
    where: str, key: str, value: Any
) -> None:
    doc = _wild_good()
    _under(doc, where)[key] = value

    message = _wild_rejected(doc, 1)

    assert key in message


def test_a_wildcard_accepts_a_dependency_name_with_dots_and_each_declared_scalar() -> None:
    from aoe2stats_core.truth.validate import validate

    doc = _wild_good()
    _under(doc, "deps").update({"zope.interface": "7.0", "a.b.c": "1"})
    _under(doc, "commands").update({"103": 300})

    validate(doc, _wild_register())


def test_a_wildcard_path_the_validator_declares_no_type_for_covers_nothing() -> None:
    register = _wild_register()
    register["engine.undeclared_thing"] = Entry("engine.undeclared.*", Tier.OBSERVED)
    doc = _wild_good()
    doc["engine"]["undeclared"] = {"x": "1"}
    doc["provenance"]["engine.undeclared_thing"] = _prov("observed")
    from aoe2stats_core.truth.validate import DocumentInvalid, validate

    with pytest.raises(DocumentInvalid) as info:
        validate(doc, register)

    assert 1 in info.value.rules
    assert "engine.undeclared.x" in str(info.value)


# --- present_data: the validator's own reading of presence, for the provenance builder (T666e) ---


def _present(doc: dict[str, Any]) -> frozenset[str]:
    from aoe2stats_core.truth.validate import present_data

    return present_data(doc, _wild_register())


def test_present_data_names_the_data_a_wildcard_key_and_an_exact_leaf_carry() -> None:
    assert _present(_wild_good()) == {
        "document.schema_version",
        "engine.dependencies",
        "match.game_id",
        "participant.age_up_commands",
        "participant.civ_id",
        "participant.pace",
        "participant.villagers_ordered",
    }


@pytest.mark.parametrize(
    "mutate",
    [
        lambda doc: doc["engine"].__setitem__("deps", {"pkg": {"inner": "1.0"}}),  # nested
        lambda doc: doc["engine"].__setitem__("deps", {"pkg": 1}),  # wrong scalar type
        lambda doc: doc["engine"].__setitem__("deps", {}),  # an empty mapping is no value
    ],
)
def test_present_data_does_not_count_what_the_validator_does_not_resolve(mutate: Any) -> None:
    """The old string-prefix reading counted any leaf beneath ``engine.deps.`` as the datum; the
    validator's key-by-key walk does not, and ``present_data`` is the validator's."""
    doc = _wild_good()
    mutate(doc)

    assert "engine.dependencies" not in _present(doc)


def test_present_data_agrees_with_validate_about_rule_2() -> None:
    from aoe2stats_core.truth.validate import validate

    doc = _wild_good()
    present = _present(doc)
    validate(doc, _wild_register())  # every present datum has its entry, and no other has one
    # The provenance block also names the one inferred datum, which lives under `inferred`.
    assert set(doc["provenance"]) - present == {"participant.group_control_lost"}
