"""What produced one published value (FR-009), and the confidence rule at construction (FR-010).

A provenance is bound to one register datum. Its method is an identifier plus a version, never a
sentence: a reader must be able to look the algorithm up and recompute the value.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from aoe2stats_core.truth.confidence import Confidence, check_confidence_allowed
from aoe2stats_core.truth.tiers import Tier

_METHOD_ID = re.compile(r"[a-z][a-z0-9_]*(?:[.-][a-z0-9_]+)*")
_VERSION = re.compile(r"\d+(?:\.\d+)*(?:[-+][0-9A-Za-z.-]+)?")


@dataclass(frozen=True, slots=True)
class Method:
    """An algorithm named so it can be recomputed: a dotted identifier and a version."""

    id: str
    version: str

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not _METHOD_ID.fullmatch(self.id):
            raise ValueError(f"method id must be a lowercase dotted identifier, got {self.id!r}")
        if not isinstance(self.version, str) or not _VERSION.fullmatch(self.version):
            raise ValueError(f"method version must look like '1' or '1.2.0', got {self.version!r}")


@dataclass(frozen=True, slots=True)
class Provenance:
    """The tier, method, inputs, confidence and non-claim of one value of one register datum."""

    datum: str
    tier: Tier
    method: Method
    inputs: tuple[str, ...] = ()
    confidence: Confidence | None = None
    non_claim: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.datum, str) or not self.datum.strip():
            raise ValueError("provenance must be bound to a register datum id")
        if not isinstance(self.tier, Tier):
            raise TypeError("tier must be a Tier")
        if not isinstance(self.method, Method):
            raise TypeError("method must be a Method (identifier and version), not free text")
        if isinstance(self.inputs, str) or not all(
            isinstance(i, str) and i.strip() for i in self.inputs
        ):
            raise TypeError("inputs must be a sequence of non-blank datum ids")
        object.__setattr__(self, "inputs", tuple(self.inputs))
        if not self.inputs and self.tier is not Tier.OBSERVED:
            raise ValueError(
                f"a {self.tier.value} value must name its inputs; only observed may not"
            )
        if self.non_claim is not None and (
            not isinstance(self.non_claim, str) or not self.non_claim.strip()
        ):
            raise ValueError("non_claim, when present, must be a non-empty statement")
        if self.tier >= Tier.INFERRED and self.confidence is None:
            raise ValueError(f"a {self.tier.value} value must carry a confidence")
        if self.confidence is not None:
            check_confidence_allowed(self.tier, self.confidence)
