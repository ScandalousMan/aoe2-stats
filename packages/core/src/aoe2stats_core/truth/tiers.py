"""The closed, ordered truth-tier set (FR-008) and the weakest-input rule.

Declaration order is sort order: a larger tier is a weaker claim. ``non-determinable`` is
deliberately absent: it is a register classification, and nothing is ever published at it.
"""

from __future__ import annotations

from enum import Enum
from functools import total_ordering
from typing import Any


@total_ordering
class Tier(Enum):
    """How a value is known, strongest first."""

    OBSERVED = "observed"
    DECODED = "decoded"
    RECONSTRUCTED = "reconstructed"
    DERIVED = "derived"
    INFERRED = "inferred"
    PREDICTED = "predicted"

    @property
    def _rank(self) -> int:
        return list(type(self)).index(self)

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, Tier):
            return NotImplemented
        return self._rank < other._rank


def weakest(*tiers: Tier) -> Tier:
    """Return the tier of a result computed from inputs at ``tiers``.

    The result is never stronger than its weakest input, and this is the only way to compute it:
    there is no parameter through which a caller could assert a stronger tier.
    """
    if not tiers:
        raise ValueError("weakest() requires at least one input tier")
    return max(tiers)
