"""Where a value may be written, by construction (T656, FR-011).

The validator is the second lock and has its own suite; these tests are about the first: building a
document that puts a conclusion in a measurement's field, or a measurement in the conclusions'
block, is refused before there is a document to validate.
"""

from __future__ import annotations

from typing import Any

import pytest

from aoe2stats_core.truth.confidence import Confidence, ConfidenceLevel
from aoe2stats_core.truth.placement import (
    InferredInstances,
    TierPlacementError,
    inferred_block,
    require_outside_inferred,
)
from aoe2stats_core.truth.provenance import Method, Provenance
from aoe2stats_core.truth.tiers import Tier

_METHOD = Method("test.method", "1")
_NON_CLAIM = "not a casualty count"


def _inferred(non_claim: str | None = _NON_CLAIM) -> Provenance:
    return Provenance(
        "participant.group_silence_episodes",
        Tier.INFERRED,
        _METHOD,
        ("participant.civ_id",),
        Confidence(ConfidenceLevel.LOW, "basis"),
        non_claim,
    )


def _instance(**changes: Any) -> dict[str, Any]:
    instance: dict[str, Any] = {
        "participant": 1,
        "confidence": {"level": "low", "basis": "silence lasted 200 s"},
        "non_claim": _NON_CLAIM,
    }
    instance.update(changes)
    return instance


@pytest.mark.parametrize("tier", [Tier.OBSERVED, Tier.DECODED, Tier.RECONSTRUCTED, Tier.DERIVED])
def test_a_measured_tier_may_be_placed_at_an_ordinary_path(tier: Tier) -> None:
    require_outside_inferred("participant.civ_id", tier)


@pytest.mark.parametrize("tier", [Tier.INFERRED, Tier.PREDICTED])
def test_a_conclusion_may_not_be_placed_at_an_ordinary_path(tier: Tier) -> None:
    with pytest.raises(TierPlacementError, match="only under inferred"):
        require_outside_inferred("participant.coaching_note", tier)


@pytest.mark.parametrize("tier", [Tier.OBSERVED, Tier.DECODED, Tier.RECONSTRUCTED, Tier.DERIVED])
def test_a_measurement_may_not_be_placed_inside_inferred(tier: Tier) -> None:
    provenance = Provenance("participant.pace", tier, _METHOD, ("participant.civ_id",))
    with pytest.raises(TierPlacementError, match="only inferred or predicted"):
        InferredInstances(provenance, (_instance(),))


def test_the_block_holds_the_instances_under_their_datum_id() -> None:
    group = InferredInstances(_inferred(), (_instance(), _instance(participant=2)))

    block = inferred_block([group])

    assert list(block) == ["participant.group_silence_episodes"]
    assert [i["participant"] for i in block["participant.group_silence_episodes"]] == [1, 2]


def test_a_datum_with_no_instance_is_absent_not_an_empty_list() -> None:
    assert inferred_block([InferredInstances(_inferred(), ())]) == {}


@pytest.mark.parametrize(
    "bad",
    [
        {"confidence": None},
        {"confidence": {"level": "certain", "basis": "b"}},
        {"confidence": {"level": 0.9, "basis": "b"}},
        {"confidence": {"level": "low", "basis": "  "}},
        {"non_claim": None},
        {"non_claim": "something else"},
    ],
    ids=["no-confidence", "open-level", "numeric-level", "blank-basis", "no-non-claim", "other"],
)
def test_an_instance_missing_what_the_datum_requires_is_refused(bad: dict[str, Any]) -> None:
    with pytest.raises(TierPlacementError):
        InferredInstances(_inferred(), (_instance(**bad),))


def test_a_datum_with_no_declared_non_claim_needs_none() -> None:
    InferredInstances(_inferred(non_claim=None), (_instance(non_claim=None),))
