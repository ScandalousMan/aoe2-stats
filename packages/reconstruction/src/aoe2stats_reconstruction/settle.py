"""Resolve a settlement's rule against the registry (data-model section 5; FR-006, FR-007)."""

from __future__ import annotations

from aoe2stats_reconstruction.rules import Rule, RuleError, Rules
from aoe2stats_reconstruction.state import Settlement

_FAMILY = {"proof": "proof", "rule": "deduction"}


def resolve_rule(settlement: Settlement, registry: Rules) -> Rule:
    """Return the adopted rule a settlement names; raise `RuleError` on any mismatch.

    A proof names a proof rule, a rule names a deduction rule, and only an adopted rule settles a
    published value.
    """
    if settlement.rule not in registry:
        raise RuleError(f"{settlement.rule}: not in the rules registry")
    rule = registry[settlement.rule]
    family = _FAMILY[settlement.by]
    if rule.family != family:
        raise RuleError(f"{rule.id}: a settlement by {settlement.by!r} needs a {family} rule")
    if rule.status != "adopted":
        raise RuleError(f"{rule.id}: status is {rule.status!r}; only an adopted rule settles")
    return rule
