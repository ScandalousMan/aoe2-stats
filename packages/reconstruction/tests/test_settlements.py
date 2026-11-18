"""Settlements and the one-number rule (data-model §4, §5, §7; FR-008, SC-002).

The modules under test are imported inside each test body through `_mod`.
"""

from __future__ import annotations

import dataclasses
import importlib
import types
import typing
from collections.abc import Mapping
from decimal import Decimal
from fractions import Fraction
from typing import Any

PKG = "aoe2stats_reconstruction"

# Types that admit a range, a set of alternatives, or a non-integer quantity.
_FORBIDDEN_LEAVES: tuple[type, ...] = (float, Decimal, Fraction, complex, range, slice)
_FORBIDDEN_CONTAINERS: tuple[type, ...] = (list, set, frozenset, dict)
_FORBIDDEN_NAMES = (
    "probability",
    "confidence",
    "share",
    "ratio",
    "percent",
    "low",
    "high",
    "lower",
    "upper",
    "min",
    "max",
    "interval",
    "range",
    "alternatives",
    "candidates",
)


_SPENT = "reconstruction.resources_spent"
_AGE_UP = "reconstruction.age_up_modelled_arrival_ms"


def _VALUE_TYPES(state: Any) -> dict[str, Any]:
    """The published value type of each `reconstructed` datum that carries a value."""
    return {_SPENT: state.ResourceSpent, _AGE_UP: state.AgeUpModelledArrival}


def _mod(name: str) -> Any:
    return importlib.import_module(f"{PKG}.{name}")


def _settlement(state: Any, by: str, rule: str, **extra: Any) -> Any:
    fields: dict[str, Any] = {
        "condition": "age",
        "at_ms": 600_000,
        "orders": (3,),
        "facts": {},
    }
    fields.update(extra)
    return state.Settlement(by=by, rule=rule, **fields)


def _condition(state: Any, **overrides: Any) -> Any:
    fields: dict[str, Any] = {
        "kind": "age",
        "subject": 2,
        "at_ms": 600_000,
        "value": True,
        "settled_by": _settlement(state, "proof", "P1"),
    }
    fields.update(overrides)
    return state.Condition(**fields)


def _rejects(build: Any) -> bool:
    from pydantic import ValidationError

    try:
        build()
    except (ValidationError, TypeError, ValueError):
        return True
    return False


def test_condition_has_exactly_one_value_and_a_required_settlement() -> None:
    state = _mod("state")
    condition = _condition(state)
    assert condition.value is True
    assert condition.settled_by.rule == "P1"

    # No settlement: refused, none is special-cased (team too carries P0).
    fields = {"kind": "team", "subject": 1, "at_ms": 0, "value": 1}
    assert _rejects(lambda: state.Condition(**fields))
    assert _rejects(lambda: _condition(state, settled_by=None))
    team = _condition(
        state,
        kind="team",
        subject=1,
        at_ms=0,
        value=1,
        settled_by=state.Settlement(
            condition="team", at_ms=0, by="proof", rule="P0", orders=(), facts={}
        ),
    )
    assert team.settled_by.rule == "P0"

    # One value only: a pair, a list, a range, a float and a probability are all refused.
    for bad in ((1, 2), [1, 2], {1, 2}, range(1, 3), 0.5, {"p": 0.5}):
        assert _rejects(lambda bad=bad: _condition(state, value=bad)), bad

    # `at_ms` is one integer, never a window.
    assert _rejects(lambda: _condition(state, at_ms=(0, 10)))
    assert _rejects(lambda: _condition(state, at_ms=1.5))


def test_a_settlement_can_name_every_condition_a_rule_settles() -> None:
    state, rules = _mod("state"), _mod("rules")
    assert rules.RULES
    for rule in rules.RULES:
        by = "proof" if rule.family == "proof" else "rule"
        built = _settlement(state, by, rule.id, condition=rule.settles)
        assert built.condition == rule.settles, rule.id
    # A value no rule settles is still refused.
    assert _rejects(lambda: _settlement(state, "rule", "D-WIN-1", condition="nonsense"))
    assert _rejects(lambda: _settlement(state, "rule", "D-WIN-1", condition="Winner"))


def test_settlement_resolves_to_an_adopted_rule_of_the_family_its_by_states() -> None:
    state, settle, rules = _mod("state"), _mod("settle"), _mod("rules")
    registry = rules.RULES

    # Proof naming a proof rule, deduction naming a deduction rule: both adopted.
    proof = _settlement(state, "proof", "P1")
    assert settle.resolve_rule(proof, registry).id == "P1"
    deduction = _settlement(state, "rule", "D-TECH-1")
    assert settle.resolve_rule(deduction, registry).id == "D-TECH-1"

    # Wrong family for `by`, in both directions.
    assert _rejects(lambda: settle.resolve_rule(_settlement(state, "proof", "D-TECH-1"), registry))
    assert _rejects(lambda: settle.resolve_rule(_settlement(state, "rule", "P1"), registry))
    # A candidate rule (D-AGE-1 enters as candidate) settles nothing published.
    assert _rejects(lambda: settle.resolve_rule(_settlement(state, "rule", "D-AGE-1"), registry))
    # An id the registry does not hold.
    assert _rejects(lambda: settle.resolve_rule(_settlement(state, "rule", "D-NOPE-9"), registry))


def _unwrap(annotation: Any) -> list[Any]:
    """Every type an annotation can admit, containers kept as (origin, args) probes."""
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    if origin in (typing.Union, types.UnionType):
        out: list[Any] = []
        for arg in args:
            out.extend(_unwrap(arg))
        return out
    if origin is typing.Annotated:
        return _unwrap(args[0])
    if origin is typing.Literal:
        return [type(a) for a in args]
    return [annotation]


def _walk(root: type, seen: set[type], problems: list[str]) -> None:
    if root in seen:
        return
    seen.add(root)
    hints = typing.get_type_hints(root)
    assert hints, f"{root.__name__} declares no fields"
    for name, annotation in hints.items():
        where = f"{root.__name__}.{name}"
        if any(word == name or name.startswith(f"{word}_") for word in _FORBIDDEN_NAMES):
            problems.append(f"{where}: name suggests a range or a probability")
        _check(where, name, annotation, seen, problems, in_union=False)


def _check(
    where: str, field: str, annotation: Any, seen: set[type], problems: list[str], *, in_union: bool
) -> None:
    members = _unwrap(annotation)
    for member in members:
        origin = typing.get_origin(member) or member
        args = typing.get_args(member)
        if isinstance(origin, type) and issubclass(origin, _FORBIDDEN_LEAVES):
            problems.append(f"{where}: admits {origin.__name__}")
        elif origin is tuple:
            variadic = len(args) == 2 and args[1] is Ellipsis
            if not variadic:
                problems.append(f"{where}: fixed-length tuple admits a pair or a range")
            elif field == "value" or len(members) > 1:
                problems.append(f"{where}: a value or an alternative carries a sequence")
            for arg in args:
                if arg is not Ellipsis:
                    _check(where, field, arg, seen, problems, in_union=True)
        elif isinstance(origin, type) and issubclass(origin, Mapping):
            if field == "value" or len(members) > 1:
                problems.append(f"{where}: a value or an alternative carries a mapping")
            for arg in args:
                _check(where, field, arg, seen, problems, in_union=True)
        elif isinstance(origin, type) and issubclass(origin, _FORBIDDEN_CONTAINERS):
            problems.append(f"{where}: admits {origin.__name__}")
        elif isinstance(member, type) and hasattr(member, "model_fields"):
            _walk(member, seen, problems)


def test_no_published_field_admits_a_pair_range_alternatives_share_or_probability() -> None:
    state = _mod("state")
    roots = [state.Condition, state.Settlement, *_VALUE_TYPES(state).values()]
    problems: list[str] = []
    seen: set[type] = set()
    for root in roots:
        _walk(root, seen, problems)
    assert problems == []
    # The walk reached the nested record, not only the three roots.
    assert {t.__name__ for t in seen} >= {
        "Condition",
        "Settlement",
        "ResourceSpent",
        "AgeUpModelledArrival",
    }

    # A reconstructed value's `value` is exactly an integer, on every datum's type.
    for datum, model in _VALUE_TYPES(state).items():
        assert typing.get_type_hints(model)["value"] is int, datum


@dataclasses.dataclass(frozen=True)
class _Entry:
    path: str | None
    tier: Any
    status: str = "published"
    non_claim: str | None = None
    requires_knowledge: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class _RuleEntry:
    status: str
    family: str


def _version_3_document(state: Any, instances: dict[str, list[Any]]) -> dict[str, Any]:
    """A minimal version 3 document around `instances`, with the register and rules to match."""
    from aoe2stats_core.truth.validate import identity_digest

    identity: dict[str, Any] = {
        "recording": {"object_key": "k", "sha256": "ab"},
        "parser": {"name": "aoe2rec-py", "version": "1.0"},
        "parser_dependencies": {"aoe2rec-py": "1.0"},
        "knowledge": {"source": "s", "source_version": "1", "describes_build": 1, "digest": "d"},
        "reconstruction_engine": "aoe2stats-reconstruction@1+rules:sha256:abc",
        "analytics": "a1",
    }
    identity["digest"] = identity_digest(identity)
    provenance = {"document.schema_version": {"tier": "observed", "method": "m@1", "inputs": []}}
    for datum in instances:
        provenance[datum] = {"tier": "reconstructed", "method": "m@1", "inputs": []}
    return {
        "schema_version": 3,
        "identity": identity,
        "reconstructed": instances,
        "provenance": provenance,
        "knowledge_gaps": [],
    }


def _validate(document: dict[str, Any]) -> None:
    from aoe2stats_core.truth.tiers import Tier
    from aoe2stats_core.truth.validate import validate

    register = {"document.schema_version": _Entry("schema_version", Tier.OBSERVED)}
    for datum in (_SPENT, _AGE_UP):
        register[datum] = _Entry(None, Tier.RECONSTRUCTED)
    validate(document, register, rules={"D-AGE-1": _RuleEntry("adopted", "deduction")})


def _published_instances(state: Any) -> dict[str, list[dict[str, Any]]]:
    settlement = state.Settlement(
        condition="age", at_ms=0, by="rule", rule="D-AGE-1", orders=(0,), facts={"arrival": 0}
    )
    effect = state.EffectRef(civilisation="Britons", source_key="k")
    common: dict[str, Any] = {
        "participant": 1,
        "value": 10,
        "settled_by": (settlement,),
        "effects": (effect,),
    }
    spent = state.ResourceSpent(resource="wood", **common)
    age_up = state.AgeUpModelledArrival(age=2, reached=False, **common)
    return {
        _SPENT: [spent.model_dump(mode="json")],
        _AGE_UP: [age_up.model_dump(mode="json")],
    }


def test_each_published_value_type_serialises_to_the_instance_rule_13_declares() -> None:
    state = _mod("state")
    instances = _published_instances(state)

    # One instance per datum, serialised as published, passes the validator (rules 11 to 13).
    _validate(_version_3_document(state, instances))

    # A dumped settlement carries exactly the contract's key set.
    for block in instances.values():
        for settlement in block[0]["settled_by"]:
            assert set(settlement) == {"condition", "at_ms", "by", "rule", "orders", "facts"}

    # `datum` is the block's key, never a field of an instance.
    for block in instances.values():
        assert all("datum" not in instance for instance in block)

    # Contrast: the same instance with an extra `key` field is refused by rule 13.
    from aoe2stats_core.truth.validate import DocumentInvalid

    for datum in instances:
        planted = {datum: [{**instances[datum][0], "key": "wood"}]}
        try:
            _validate(_version_3_document(state, planted))
        except DocumentInvalid as exc:
            assert 13 in exc.rules, datum
        else:
            raise AssertionError(f"{datum}: an extra `key` was accepted")


def test_a_condition_whose_settlement_disagrees_with_its_kind_or_at_ms_is_refused() -> None:
    state = _mod("state")
    # Contrast: a settlement answering this very condition is accepted.
    assert _condition(state).settled_by.condition == "age"
    # Another kind, or another moment, is refused.
    other_kind = _settlement(state, "proof", "P1", condition="researched")
    assert _rejects(lambda: _condition(state, settled_by=other_kind))
    other_moment = _settlement(state, "proof", "P1", at_ms=1)
    assert _rejects(lambda: _condition(state, settled_by=other_moment))
    # A settlement carries both fields, and a kind outside the closed set is refused.
    assert _rejects(lambda: state.Settlement(by="proof", rule="P1", orders=(), facts={}))
    assert _rejects(lambda: _settlement(state, "proof", "P1", condition="nope"))
    assert _rejects(lambda: _settlement(state, "proof", "P1", at_ms=(0, 1)))
