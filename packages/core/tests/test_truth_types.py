"""Tests for the truth-tier and confidence types (T609, T610), written first (T611).

Written before T609 and T610 existed, as strict xfails; each task removed its own markers when
it landed, so they now run as ordinary tests.

Names the implementers must use:

- ``aoe2stats_core.truth.tiers``: ``Tier`` (ordered enum, declaration order observed < decoded <
  reconstructed < derived < inferred < predicted, so a *larger* tier is a *weaker* claim) and
  ``weakest(*tiers) -> Tier`` (requires at least one input).
- ``aoe2stats_core.truth.confidence``: ``ConfidenceLevel`` (ordered enum LOW < MEDIUM < HIGH),
  ``Confidence(level, basis)`` and ``check_confidence_allowed(tier, confidence)`` raising
  ``ValueError`` when ``tier`` is stronger than ``Tier.INFERRED``.
"""

from __future__ import annotations

import itertools

import pytest

ORDER = ["OBSERVED", "DECODED", "RECONSTRUCTED", "DERIVED", "INFERRED", "PREDICTED"]


def test_tier_set_is_closed_and_ordered() -> None:
    from aoe2stats_core.truth.tiers import Tier

    assert [t.name for t in sorted(Tier)] == ORDER
    assert len(Tier) == 6
    assert "NON_DETERMINABLE" not in Tier.__members__


def test_tier_order_is_total() -> None:
    from aoe2stats_core.truth.tiers import Tier

    for a, b in itertools.product(Tier, repeat=2):
        assert (a < b) + (a == b) + (a > b) == 1
    for a, b, c in itertools.product(Tier, repeat=3):
        if a < b and b < c:
            assert a < c


def test_weakest_returns_the_weakest_input() -> None:
    from aoe2stats_core.truth.tiers import Tier, weakest

    assert weakest(Tier.OBSERVED, Tier.DERIVED, Tier.DECODED) is Tier.DERIVED
    assert weakest(Tier.INFERRED) is Tier.INFERRED
    for a, b in itertools.product(Tier, repeat=2):
        assert weakest(a, b) is max(a, b)


def test_weakest_refuses_no_input() -> None:
    from aoe2stats_core.truth.tiers import weakest

    with pytest.raises(ValueError):
        weakest()


def test_confidence_levels_are_closed_and_ordered() -> None:
    from aoe2stats_core.truth.confidence import ConfidenceLevel

    assert [lv.name for lv in sorted(ConfidenceLevel)] == ["LOW", "MEDIUM", "HIGH"]


def test_confidence_accepts_level_and_basis() -> None:
    from aoe2stats_core.truth.confidence import Confidence, ConfidenceLevel

    c = Confidence(ConfidenceLevel.MEDIUM, "matches the opening build order")
    assert c.level is ConfidenceLevel.MEDIUM
    assert c.basis == "matches the opening build order"


@pytest.mark.parametrize("bad", [0.9, 1, 0, "0.9", "90", "1"])
def test_confidence_rejects_any_numeric_level(bad: object) -> None:
    from aoe2stats_core.truth.confidence import Confidence

    with pytest.raises((TypeError, ValueError)):
        Confidence(bad, "some basis")  # type: ignore[arg-type]


@pytest.mark.parametrize("basis", ["", " ", "\t\n"])
def test_confidence_rejects_empty_basis(basis: str) -> None:
    from aoe2stats_core.truth.confidence import Confidence, ConfidenceLevel

    with pytest.raises(ValueError):
        Confidence(ConfidenceLevel.LOW, basis)


def test_confidence_has_no_numeric_field() -> None:
    from aoe2stats_core.truth.confidence import Confidence, ConfidenceLevel

    c = Confidence(ConfidenceLevel.HIGH, "basis")
    for value in vars(c).values() if hasattr(c, "__dict__") else []:
        assert not isinstance(value, (int, float)) or isinstance(value, ConfidenceLevel)


def test_confidence_above_inferred_is_an_error() -> None:
    from aoe2stats_core.truth.confidence import (
        Confidence,
        ConfidenceLevel,
        check_confidence_allowed,
    )
    from aoe2stats_core.truth.tiers import Tier

    c = Confidence(ConfidenceLevel.HIGH, "basis")
    for tier in (Tier.OBSERVED, Tier.DECODED, Tier.RECONSTRUCTED, Tier.DERIVED):
        with pytest.raises(ValueError):
            check_confidence_allowed(tier, c)
    for tier in (Tier.INFERRED, Tier.PREDICTED):
        check_confidence_allowed(tier, c)
