"""Tests for the document validator (T619), written first as T620.

API chosen here, which T619 must implement in ``aoe2stats_core.truth.validate``:

- ``validate(document, register) -> None``. ``document`` is the published analysis as a mapping;
  ``register`` maps a datum id to an entry exposing ``path`` (``str | None``: the document path
  that carries it, dict keys joined by ``.`` and every list index collapsed to ``[]``, e.g.
  ``participants[].age_up_commands[]``; ``None`` for a datum that only lives under ``inferred``),
  ``tier`` (``Tier``), ``status`` (``"published"``, ``"planned"`` or ``"blocked"``), ``non_claim``
  (``str | None``) and ``requires_knowledge`` (``tuple[str, ...]``, keys of the form
  ``"<entity kind>.<field>"``, matched against ``knowledge_gaps`` entries). Injecting the register
  keeps the validator testable before the loader (T615) exists; production passes the loaded one.
- Raises ``DocumentInvalid`` (a ``ValueError``) carrying ``rules``, a ``frozenset[int]`` of the
  contract rule numbers (1 to 10) that were violated, and a message naming each violation. It
  reports every violated rule, not only the first.
- ``identity_digest(identity) -> str``: the digest of an identity mapping over every field except
  ``digest`` itself; rule 10 compares ``identity["digest"]`` against it.
- Leaves outside rule 1 are the wall-clock set (``envelope``, ``extracted_at``) and the blocks
  ``identity``, ``provenance``, ``knowledge_gaps``; the ``inferred`` block is checked per rules
  5 to 7 instead, its instances being keyed by datum id.
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
            "participants[].army_cost", Tier.DERIVED, requires_knowledge=("unit.cost",)
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


def _gap(severity: str, kind: str = "unit", field: str = "cost") -> dict[str, Any]:
    return {
        "entity": {"kind": kind, "id": 0},
        "field": field,
        "build": 1,
        "civilisation": 0,
        "cause": "field-absent",
        "prevents": ["participant.army_cost"],
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


def test_an_informational_or_unrelated_gap_withholds_nothing() -> None:
    from aoe2stats_core.truth.validate import validate

    doc = _with_army_cost()
    doc["knowledge_gaps"] = [_gap("informational"), _gap("blocking", "building", "cost")]
    validate(doc, _register())


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
