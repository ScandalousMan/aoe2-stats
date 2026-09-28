"""Qualitative confidence with a mandatory basis (FR-010a).

A number is not accepted in any form. A recording carries no outcome against which a probability
could be calibrated, and an uncalibrated number is an invented value wearing a measured one's
clothes. The level set is closed and ordered; the basis is required and non-blank.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import total_ordering
from typing import Any

from aoe2stats_core.truth.tiers import Tier


@total_ordering
class ConfidenceLevel(Enum):
    """How much a claim can be trusted, weakest first."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def _rank(self) -> int:
        return list(type(self)).index(self)

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, ConfidenceLevel):
            return NotImplemented
        return self._rank < other._rank


@dataclass(frozen=True, slots=True)
class Confidence:
    """A confidence level and the reason for it, constructed together."""

    level: ConfidenceLevel
    basis: str

    def __post_init__(self) -> None:
        if not isinstance(self.level, ConfidenceLevel):
            raise TypeError("confidence level must be a ConfidenceLevel; numbers are not accepted")
        if not isinstance(self.basis, str):
            raise TypeError("confidence basis must be a string")
        if not self.basis.strip():
            raise ValueError("confidence basis must be a non-empty explanation")


def check_confidence_allowed(tier: Tier, confidence: Confidence) -> None:
    """Refuse a confidence attached to a value stronger than ``Tier.INFERRED``.

    Observed through derived values are exact given their inputs; a confidence on them would
    misstate what they are.
    """
    if not isinstance(confidence, Confidence):
        raise TypeError("confidence must be a Confidence")
    if tier < Tier.INFERRED:
        raise ValueError(f"a {tier.value} value carries no confidence; only inferred or weaker")
