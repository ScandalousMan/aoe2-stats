"""Tests for the provenance type (T612): each rule has a case planting its defect."""

from __future__ import annotations

import pytest

from aoe2stats_core.truth.confidence import Confidence, ConfidenceLevel
from aoe2stats_core.truth.provenance import Method, Provenance
from aoe2stats_core.truth.tiers import Tier

M = Method("decode.age_up", "1.0.0")
C = Confidence(ConfidenceLevel.MEDIUM, "two independent signals agree")


def test_observed_needs_no_inputs_and_no_confidence() -> None:
    p = Provenance("participant.age_up_commands", Tier.OBSERVED, M)
    assert p.inputs == () and p.confidence is None and p.non_claim is None


def test_inferred_with_confidence_and_non_claim() -> None:
    p = Provenance(
        "participant.group_control_lost", Tier.INFERRED, M, ["a.b"], C, "not a casualty count"
    )
    assert p.inputs == ("a.b",)
    assert p.confidence is C


@pytest.mark.parametrize("tier", [Tier.INFERRED, Tier.PREDICTED])
def test_missing_confidence_at_inferred_or_predicted_is_refused(tier: Tier) -> None:
    with pytest.raises(ValueError, match="confidence"):
        Provenance("x.y", tier, M, ("a.b",))


@pytest.mark.parametrize("tier", [Tier.OBSERVED, Tier.DECODED, Tier.RECONSTRUCTED, Tier.DERIVED])
def test_confidence_below_inferred_is_refused(tier: Tier) -> None:
    with pytest.raises(ValueError, match="no confidence"):
        Provenance("x.y", tier, M, ("a.b",), C)


def test_numeric_confidence_is_refused() -> None:
    with pytest.raises(TypeError):
        Provenance("x.y", Tier.INFERRED, M, ("a.b",), 0.8)  # type: ignore[arg-type]


@pytest.mark.parametrize("tier", [Tier.DECODED, Tier.DERIVED, Tier.INFERRED])
def test_empty_inputs_only_at_observed(tier: Tier) -> None:
    with pytest.raises(ValueError, match="inputs"):
        Provenance("x.y", tier, M, (), C if tier >= Tier.INFERRED else None)


def test_free_text_method_is_refused() -> None:
    with pytest.raises(TypeError, match="Method"):
        Provenance("x.y", Tier.OBSERVED, "we counted the commands")  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", ["", "Count the commands", "Decode", "a..b", ".a", "a b"])
def test_method_id_must_be_an_identifier(bad: str) -> None:
    with pytest.raises(ValueError, match="identifier"):
        Method(bad, "1")


@pytest.mark.parametrize("bad", ["", "latest", "v1", "1.", "1 2"])
def test_method_version_must_be_a_version(bad: str) -> None:
    with pytest.raises(ValueError, match="version"):
        Method("decode.age_up", bad)


@pytest.mark.parametrize("bad", ["", "   "])
def test_blank_datum_is_refused(bad: str) -> None:
    with pytest.raises(ValueError, match="datum"):
        Provenance(bad, Tier.OBSERVED, M)


@pytest.mark.parametrize("bad", ["", "  "])
def test_blank_non_claim_is_refused(bad: str) -> None:
    with pytest.raises(ValueError, match="non_claim"):
        Provenance("x.y", Tier.OBSERVED, M, non_claim=bad)


def test_bare_string_inputs_are_refused() -> None:
    with pytest.raises(TypeError, match="inputs"):
        Provenance("x.y", Tier.DECODED, M, "a.b")  # type: ignore[arg-type]


def test_provenance_is_immutable() -> None:
    p = Provenance("x.y", Tier.OBSERVED, M)
    with pytest.raises(AttributeError):
        p.tier = Tier.DECODED  # type: ignore[misc]
