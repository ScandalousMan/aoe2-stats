"""The analyzer refuses to publish a document that breaks the contract (T661, US3).

Every test was ``xfail(strict=True)`` until its seam landed, and each imports the seam **inside its
own body**, so a missing symbol is a per-test expected failure and not a collection error. T655
defined ``validate_document`` and took the marker off every case that injects its own register; the
one case that reads the packaged register stays ``xfail`` until T656 promotes its datum. When a seam
lands the marker must come off in the same change: ``strict`` turns an unexpected pass into a
failure, which is how this file is kept honest.

**The seam this file assumes**, for whoever lands T655 and T656 (``contracts/analysis-document.md``
names the validator, ``aoe2stats_core.truth.validate``, which already exists, but not the analyzer
function that runs it before the object is written):

- ``aoe2stats_analyzer.extract.validate_document(document, register=None) -> None``. It is the one
  gate ``run.py`` calls **before** writing the object (T656). ``register`` defaults to the packaged
  ``aoe2stats_core.truth.register.REGISTER`` entries (a mapping of datum id to entry); a test passes
  a small one so each case isolates a single rule. It delegates to
  ``aoe2stats_core.truth.validate.validate`` and lets its ``DocumentInvalid`` propagate unchanged
  (``rules``: the contract rule numbers broken; the message names each violation), so 003's failure
  path records the validator's own message.

Which contract rule answers each case, as ``aoe2stats_core.truth.validate`` reports it today:

- empty dependency record: rule 9 (SC-011, FR-044);
- a datum whose ``requires_knowledge`` meets a ``blocking`` gap: rule 8 (FR-037);
- a value with no tier: rule 3 when its provenance entry lacks the tier, rule 2 when it has no
  provenance entry at all (SC-002, FR-007);
- an inferred datum whose register status is not ``published``: rule 1, message
  ``inferred datum '<id>' is not a published register datum``. T656 promotes
  ``participant.group_silence_episodes`` for exactly this reason.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

import pytest

from aoe2stats_core.truth.tiers import Tier
from aoe2stats_core.truth.validate import identity_digest

# T655 defined `validate_document`, so every case that injects its own register passes. The one
# left needs the *packaged* register to publish `participant.group_silence_episodes`, which T656
# promotes (and T656 wires the validator before the write): remove this marker with that change.
_PENDING = pytest.mark.xfail(strict=True, reason="T656 promotes the datum in the packaged register")


@dataclass(frozen=True)
class Entry:
    """The duck-typed register entry the validator reads."""

    path: str | None
    tier: Tier
    status: str = "published"
    non_claim: str | None = None
    requires_knowledge: tuple[str, ...] = ()


def _register(*, silence_status: str = "published") -> dict[str, Entry]:
    return {
        "participant.civ_id": Entry("participants[].civ_id", Tier.OBSERVED),
        "participant.army_cost": Entry(
            "participants[].army_cost", Tier.DERIVED, requires_knowledge=("unit.cost",)
        ),
        "participant.group_silence_episodes": Entry(
            None,
            Tier.INFERRED,
            status=silence_status,
            non_claim="not a casualty count",
        ),
    }


def _identity(parser_dependencies: dict[str, str] | None = None) -> dict[str, Any]:
    identity: dict[str, Any] = {
        "recording": {"object_key": "k", "sha256": "ab"},
        "parser": {"name": "aoe2rec-py", "version": "1.0"},
        "parser_dependencies": (
            {"aoe2rec-py": "1.0"} if parser_dependencies is None else parser_dependencies
        ),
        "knowledge": {"source": "s", "source_version": "1", "describes_build": 1, "digest": "d"},
        "reconstruction_engine": "not-applicable",
        "analytics": "a1",
    }
    # Recomputed, so a case that empties the dependency record trips rule 9 and nothing else.
    identity["digest"] = identity_digest(identity)
    return identity


def _document() -> dict[str, Any]:
    """A complete document: non-empty dependency record, every value tiered, no gap."""
    return {
        "schema_version": 2,
        "envelope": {"extracted_at": "2026-01-01T00:00:00Z"},
        "extracted_at": "2026-01-01T00:00:00Z",
        "participants": [{"civ_id": 3, "army_cost": 120}],
        "identity": _identity(),
        "provenance": {
            "participant.civ_id": {"tier": "observed", "method": "decode@1", "inputs": []},
            "participant.army_cost": {
                "tier": "derived",
                "method": "army-cost@1",
                "inputs": ["participant.civ_id"],
            },
            "participant.group_silence_episodes": {
                "tier": "inferred",
                "method": "group-silence.banding@1",
                "inputs": [],
            },
        },
        "inferred": {
            "participant.group_silence_episodes": [
                {
                    "participant": 1,
                    "from_ms": 0,
                    "units": 2,
                    "confidence": {"level": "medium", "basis": "silence lasted 200 s"},
                    "non_claim": "not a casualty count",
                }
            ]
        },
        "knowledge_gaps": [],
    }


def _gap(severity: str, *, kind: str = "unit", field: str = "cost") -> dict[str, Any]:
    return {
        "entity": {"kind": kind, "id": 0},
        "field": field,
        "build": 1,
        "civilisation": 0,
        "cause": "civilisation-not-modelled",
        "prevents": ["participant.army_cost"],
        "severity": severity,
    }


def _rejected(
    document: dict[str, Any], register: dict[str, Entry], *rules: int, exact: bool = True
) -> Any:  # DocumentInvalid, imported in the body
    from aoe2stats_analyzer.extract import validate_document
    from aoe2stats_core.truth.validate import DocumentInvalid

    with pytest.raises(DocumentInvalid) as info:
        validate_document(document, register=register)
    if exact:
        assert info.value.rules == frozenset(rules)
    else:
        assert frozenset(rules) <= info.value.rules
    assert str(info.value)
    return info.value


def _accepted(document: dict[str, Any], register: dict[str, Entry]) -> None:
    from aoe2stats_analyzer.extract import validate_document

    validate_document(document, register=register)


# --- the contrast case that fixes the boundary --------------------------------------------------


def test_a_complete_document_is_accepted() -> None:
    _accepted(_document(), _register())


# --- SC-011: an empty dependency record ---------------------------------------------------------


def test_a_document_whose_dependency_record_is_empty_is_rejected() -> None:
    document = _document()
    document["identity"] = _identity(parser_dependencies={})

    error = _rejected(document, _register(), 9)

    assert "parser_dependencies" in str(error)


# --- FR-037: a blocking gap withholds every dependent value -------------------------------------


def test_a_datum_whose_knowledge_meets_a_blocking_gap_is_rejected() -> None:
    document = _document()
    document["knowledge_gaps"] = [_gap("blocking")]

    error = _rejected(document, _register(), 8)

    assert "participant.army_cost" in str(error)


def test_a_datum_whose_knowledge_meets_only_an_informational_gap_is_accepted() -> None:
    document = _document()
    document["knowledge_gaps"] = [_gap("informational")]

    _accepted(document, _register())


def test_a_blocking_gap_on_knowledge_no_datum_needs_withholds_nothing() -> None:
    document = _document()
    document["knowledge_gaps"] = [_gap("blocking", kind="building", field="cost")]

    _accepted(document, _register())


# --- SC-002: no value without its tier ----------------------------------------------------------


def test_a_value_whose_provenance_carries_no_tier_is_rejected() -> None:
    document = _document()
    del document["provenance"]["participant.civ_id"]["tier"]

    error = _rejected(document, _register(), 3)

    assert "participant.civ_id" in str(error)


def test_a_value_with_no_provenance_entry_at_all_is_rejected() -> None:
    document = _document()
    del document["provenance"]["participant.civ_id"]

    error = _rejected(document, _register(), 2)

    assert "participant.civ_id" in str(error)


def test_an_inferred_value_with_no_tier_is_rejected() -> None:
    document = _document()
    del document["provenance"]["participant.group_silence_episodes"]["tier"]

    _rejected(document, _register(), 3)


# --- the register status gate, and why T656 promotes group_silence_episodes ---------------------


def test_an_inferred_datum_whose_register_status_is_not_published_is_rejected() -> None:
    document = _document()

    # Rule 2 follows from rule 1: the unpublished datum is not counted as present, so its
    # provenance entry names something "not in the document". Only rule 1 is the cause.
    error = _rejected(document, _register(silence_status="planned"), 1, exact=False)

    assert "participant.group_silence_episodes" in str(error)
    assert "not a published register datum" in str(error)


@_PENDING
def test_the_packaged_register_publishes_the_one_inferred_datum_this_feature_ships() -> None:
    """Against the real register, not an injected one: until T656 promotes the entry from planned
    to published, no document carrying ``participant.group_silence_episodes`` can pass."""
    from aoe2stats_analyzer.extract import validate_document

    document = {
        "schema_version": 2,
        "identity": _identity(),
        "provenance": {
            "participant.group_silence_episodes": copy.deepcopy(
                _document()["provenance"]["participant.group_silence_episodes"]
            )
        },
        "inferred": copy.deepcopy(_document()["inferred"]),
        "knowledge_gaps": [],
    }

    validate_document(document)
