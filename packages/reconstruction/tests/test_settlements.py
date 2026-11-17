"""Settlements and the one-number rule (data-model §4, §5, §7; FR-008, SC-002).

Test first: the modules under test (`state`, `settle`, `rules`) arrive with T919 and T917, so they
are imported inside each test body and every test is a strict xfail until T919 deletes the markers.
"""

from __future__ import annotations

import importlib
import types
import typing
from collections.abc import Mapping
from decimal import Decimal
from fractions import Fraction
from typing import Any

import pytest

PKG = "aoe2stats_reconstruction"
NOT_YET = pytest.mark.xfail(strict=True, reason="T919 not implemented yet")

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


def _mod(name: str) -> Any:
    return importlib.import_module(f"{PKG}.{name}")


def _settlement(state: Any, by: str, rule: str, **extra: Any) -> Any:
    return state.Settlement(by=by, rule=rule, orders=extra.pop("orders", (3,)), facts={}, **extra)


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


@NOT_YET
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
        settled_by=state.Settlement(by="proof", rule="P0", orders=(), facts={}),
    )
    assert team.settled_by.rule == "P0"

    # One value only: a pair, a list, a range, a float and a probability are all refused.
    for bad in ((1, 2), [1, 2], {1, 2}, range(1, 3), 0.5, {"p": 0.5}):
        assert _rejects(lambda bad=bad: _condition(state, value=bad)), bad

    # `at_ms` is one integer, never a window.
    assert _rejects(lambda: _condition(state, at_ms=(0, 10)))
    assert _rejects(lambda: _condition(state, at_ms=1.5))


@NOT_YET
def test_settlement_resolves_to_an_adopted_rule_of_the_family_its_by_states() -> None:
    state, settle, rules = _mod("state"), _mod("settle"), _mod("rules")
    registry = rules.load_rules()

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


@NOT_YET
def test_no_published_field_admits_a_pair_range_alternatives_share_or_probability() -> None:
    state = _mod("state")
    roots = [state.Condition, state.Settlement, state.ReconstructedValue]
    problems: list[str] = []
    seen: set[type] = set()
    for root in roots:
        _walk(root, seen, problems)
    assert problems == []
    # The walk reached the nested record, not only the three roots.
    assert {t.__name__ for t in seen} >= {"Condition", "Settlement", "ReconstructedValue"}

    # A reconstructed value's `value` is exactly an integer.
    assert typing.get_type_hints(state.ReconstructedValue)["value"] is int
