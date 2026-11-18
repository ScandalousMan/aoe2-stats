"""Conditions, settlements and reconstructed values (data-model sections 4, 5 and 7).

Every published number is one integer and every condition has exactly one value: the types admit
no interval, no set, no alternative and no probability (FR-008, SC-002). Scalars are strict, so a
float, a pair or a bool where an integer belongs is refused rather than coerced.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    StrictBool,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from aoe2stats_reconstruction.rules import SETTLES

ConditionKind = Literal["age", "researched", "team", "team_researched", "controlled", "executed"]
SettledBy = Literal["proof", "rule"]


class _Record(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Settlement(_Record):
    """What settled one condition (data-model section 5; FR-006, FR-007, FR-014).

    `condition` and `at_ms` name the condition answered (its `kind` and the moment it was asked at).
    `condition` is closed over every value a rule's `settles` can take (data-model section 5), which
    is wider than the six condition kinds: rules also settle `alive`, `refund`, `cancellation`,
    `tie`, `distribution`, `winner` and `housing`.
    `rule` is a rule id; whether it resolves to an adopted rule of the family `by` states is
    checked by `settle.resolve_rule`, which needs the registry.
    """

    condition: StrictStr
    at_ms: StrictInt
    by: SettledBy
    rule: StrictStr
    orders: tuple[StrictInt, ...]
    facts: Mapping[StrictStr, StrictBool | StrictInt | StrictStr]

    @field_validator("condition")
    @classmethod
    def _condition_is_something_a_rule_settles(cls, value: str) -> str:
        if value not in SETTLES:
            raise ValueError(f"{value!r} is not a value a rule settles: {sorted(SETTLES)}")
        return value


class Condition(_Record):
    """One match-state question at one order (data-model section 4; FR-005).

    `value` is exactly one boolean or integer; `at_ms` is one integer, never a window.
    """

    kind: ConditionKind
    subject: StrictInt | StrictStr
    at_ms: StrictInt
    value: StrictBool | StrictInt
    settled_by: Settlement

    @model_validator(mode="after")
    def _settlement_answers_this_condition(self) -> Condition:
        if self.settled_by.condition != self.kind or self.settled_by.at_ms != self.at_ms:
            raise ValueError(
                f"settlement answers {self.settled_by.condition!r} at {self.settled_by.at_ms}, "
                f"not {self.kind!r} at {self.at_ms}"
            )
        return self


class EffectRef(_Record):
    """An applied knowledge-base effect, by civilisation and source key."""

    civilisation: StrictStr
    source_key: StrictStr


class _ReconstructedValue(_Record):
    """The fields every published number shares (data-model section 7).

    The datum is the key of the block the instance sits in, so it is not a field here. Each datum
    adds its own declared keys in a subclass, so an instance serialises to exactly the shape
    rule 13 declares for its datum.
    """

    participant: StrictInt
    value: StrictInt
    settled_by: tuple[Settlement, ...]
    effects: tuple[EffectRef, ...]


class ResourceSpent(_ReconstructedValue):
    """An instance of `reconstruction.resources_spent`: one resource, one participant."""

    resource: StrictStr


class AgeUpModelledArrival(_ReconstructedValue):
    """An instance of `reconstruction.age_up_modelled_arrival_ms`.

    A not-reached age-up publishes its computed arrival as `value` with `reached` false.
    """

    age: StrictInt
    reached: StrictBool
