"""Where a value may be written in a published document (FR-011), by construction.

The validator (``validate.py``) is the second lock: it rejects a document that has already been
built wrongly. This module is the first, so that building it wrongly is not expressible. There are
exactly two ways to place a datum, and each refuses the other's tier:

- :func:`require_outside_inferred` is called by whatever writes a value at an ordinary document
  path. It refuses a datum at ``inferred`` or ``predicted``, so a coaching conclusion cannot occupy
  a field typed observed, decoded, reconstructed or derived.
- :class:`InferredInstances` is the only carrier of the ``inferred`` block's contents, and
  :func:`inferred_block` the only function that produces the block. The carrier refuses a
  provenance stronger than ``inferred``, an instance with no confidence in the closed level set,
  and an instance that drops the non-claim its provenance names.

Standard library plus the sibling truth modules, so ``packages/core`` keeps its zero-dependency
rule.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from aoe2stats_core.truth.confidence import ConfidenceLevel
from aoe2stats_core.truth.provenance import Provenance
from aoe2stats_core.truth.tiers import Tier

__all__ = ["InferredInstances", "TierPlacementError", "inferred_block", "require_outside_inferred"]

_LEVELS = frozenset(level.value for level in ConfidenceLevel)


class TierPlacementError(ValueError):
    """A datum was offered a place its tier does not permit (FR-011)."""


def require_outside_inferred(datum: str, tier: Tier) -> None:
    """Refuse to place ``datum`` at an ordinary document path when its tier is inferred or weaker.

    A value that is a conclusion, not a measurement, lives under ``inferred`` and nowhere else.
    """
    if tier >= Tier.INFERRED:
        raise TierPlacementError(
            f"{datum!r} is {tier.value}: it may be published only under inferred, never at an "
            "ordinary document path (FR-011)"
        )


@dataclass(frozen=True, slots=True)
class InferredInstances:
    """The instances of one inferred datum, with the provenance that justifies placing them.

    Checked at construction, so a block assembled from these cannot carry a stronger tier, a
    missing confidence or a dropped non-claim.
    """

    provenance: Provenance
    instances: tuple[Mapping[str, Any], ...]

    def __post_init__(self) -> None:
        datum = self.provenance.datum
        if self.provenance.tier < Tier.INFERRED:
            raise TierPlacementError(
                f"{datum!r} is {self.provenance.tier.value}: only inferred or predicted data may "
                "be placed inside inferred (FR-011)"
            )
        object.__setattr__(self, "instances", tuple(self.instances))
        for position, instance in enumerate(self.instances):
            where = f"{datum!r} instance {position}"
            confidence = instance.get("confidence")
            if not isinstance(confidence, Mapping):
                raise TierPlacementError(f"{where} carries no confidence (FR-010)")
            if confidence.get("level") not in _LEVELS:
                raise TierPlacementError(
                    f"{where} has a confidence level outside {sorted(_LEVELS)}"
                )
            basis = confidence.get("basis")
            if not isinstance(basis, str) or not basis.strip():
                raise TierPlacementError(f"{where} has an empty confidence basis (FR-010a)")
            non_claim = self.provenance.non_claim
            if non_claim is not None and instance.get("non_claim") != non_claim:
                raise TierPlacementError(f"{where} does not carry the non-claim of its datum")


def inferred_block(groups: Iterable[InferredInstances]) -> dict[str, list[Mapping[str, Any]]]:
    """The ``inferred`` block: datum id to its instances. A datum with no instance is absent, as
    an empty list would read as "nothing found", which no recording can say."""
    block: dict[str, list[Mapping[str, Any]]] = {}
    for group in groups:
        if group.instances:
            block.setdefault(group.provenance.datum, []).extend(group.instances)
    return block
