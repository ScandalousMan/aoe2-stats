"""Conditions, settlements and reconstructed values (data-model sections 4, 5 and 7).

Every published number is one integer and every condition has exactly one value: the types admit
no interval, no set, no alternative and no probability (FR-008, SC-002). Scalars are strict, so a
float, a pair or a bool where an integer belongs is refused rather than coerced.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictBool, StrictInt, StrictStr

ConditionKind = Literal["age", "researched", "team", "team_researched", "controlled", "executed"]
SettledBy = Literal["proof", "rule"]


class _Record(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Settlement(_Record):
    """What settled one condition (data-model section 5; FR-006, FR-007, FR-014).

    `rule` is a rule id; whether it resolves to an adopted rule of the family `by` states is
    checked by `settle.resolve_rule`, which needs the registry.
    """

    by: SettledBy
    rule: StrictStr
    orders: tuple[StrictInt, ...]
    facts: Mapping[StrictStr, StrictBool | StrictInt | StrictStr]


class Condition(_Record):
    """One match-state question at one order (data-model section 4; FR-005).

    `value` is exactly one boolean or integer; `at_ms` is one integer, never a window.
    """

    kind: ConditionKind
    subject: StrictInt | StrictStr
    at_ms: StrictInt
    value: StrictBool | StrictInt
    settled_by: Settlement


class EffectRef(_Record):
    """An applied knowledge-base effect, by civilisation and source key."""

    civilisation: StrictStr
    source_key: StrictStr


class ReconstructedValue(_Record):
    """One published number (data-model section 7)."""

    datum: StrictStr
    participant: StrictInt
    key: StrictInt | StrictStr
    value: StrictInt
    settled_by: tuple[Settlement, ...]
    effects: tuple[EffectRef, ...]
