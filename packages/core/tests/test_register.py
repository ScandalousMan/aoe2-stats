"""The determinability register loader refuses each defect in contracts/register.md (T616).

Written before T615, so every test is ``xfail(strict=True)``: the body runs with every assertion
intact, and the run turns red the moment T615 makes one pass, forcing the marker off.

Each test PLANTS the defect in a small TOML string and asserts the loader refuses it. A test that
only loaded the good file would prove the file is good, not that the loader refuses anything.

API assumed here, which T615 (and T622's id check) must provide in
``aoe2stats_core.truth.register``:

- ``load_register_text(text: str) -> Register``: parse and validate register TOML text with the
  standard library. The packaged file is validated by the same function at import.
- ``RegisterError``: the single exception type every refusal raises. Its message names the offending
  id and the refusal, and contains the keyword each test matches on (case-insensitive):
  ``duplicate``, ``classification`` / ``status`` (closed set), ``approximation_acceptable`` or the
  missing field's name, ``blocked_on``, ``dangling`` / ``cycle``, ``tier``, ``confidence``,
  ``evidence``, ``id`` (naming discipline).
- Optional entry field ``confidence_method`` states the confidence method of an ``inferred`` or
  ``predicted`` entry (refusal 7); an empty or absent value on a published entry is refused.
- Tier strength follows ``aoe2stats_core.truth.tiers.Tier`` order; ``non-determinable`` and any
  entry whose dependency is ``non-determinable`` are not comparable and are not tested here.
- Naming discipline (T622 / refusal 1): an id is two or more dot-separated segments, each
  lowercase ``[a-z][a-z0-9_]*``. The banned-vocabulary half of T622 (times, built) is not tested
  here because the contract names no list; only the id shape is.
"""

from __future__ import annotations

import pytest

XFAIL = pytest.mark.xfail(strict=True, reason="T615 not implemented yet")

_ND_FIELDS = ("reason", "impact", "approximation", "approximation_acceptable", "would_change_if")


def _entry(
    id_: str = "participant.age_up_commands",
    *,
    classification: str = "observed",
    status: str = "published",
    depends_on: list[str] | None = None,
    evidence: str = "docs/data-sources.md",
    extra: str = "",
    omit: tuple[str, ...] = (),
) -> str:
    fields = {
        "classification": f'"{classification}"',
        "status": f'"{status}"',
        "source": '"a recording field"',
        "method": '"a decoding"',
        "requires_knowledge": "[]",
        "depends_on": "[" + ", ".join(f'"{d}"' for d in depends_on or []) + "]",
        "validation": '"a named procedure"',
        "evidence": f'"{evidence}"',
    }
    for key in omit:
        fields.pop(key, None)
    body = "\n".join(f"{k} = {v}" for k, v in fields.items())
    return f'[datum."{id_}"]\n{body}\n{extra}\n'


def _nd_entry(id_: str = "participant.units_lost", *, omit: str | None = None, **over: str) -> str:
    values = {
        "reason": "the recording carries no death event",
        "impact": "no casualty count",
        "approximation": "group silence",
        "approximation_acceptable": "no",
        "would_change_if": "a format with outcome events",
    }
    values.update(over)
    extra = "\n".join(f'{k} = "{v}"' for k, v in values.items() if k != omit)
    return _entry(
        id_,
        classification="non-determinable",
        status="blocked",
        extra=extra + '\nblocked_on = "an outcome event"',
    )


def _load(text: str):
    from aoe2stats_core.truth.register import load_register_text

    return load_register_text(text)


def _refused(text: str, keyword: str) -> None:
    from aoe2stats_core.truth.register import RegisterError

    with pytest.raises(RegisterError, match=f"(?i){keyword}"):
        _load(text)


@XFAIL
def test_contrast_a_well_formed_register_loads() -> None:
    """The contrast case: the refusals below are not the loader refusing everything."""
    register = _load(_entry() + _nd_entry())
    assert register is not None


@XFAIL
def test_refuses_a_duplicate_id() -> None:
    # A repeated table header is invalid TOML; the loader must still surface it as RegisterError.
    _refused(_entry() + _entry(), "duplicate")


@XFAIL
def test_refuses_a_classification_outside_the_closed_set() -> None:
    _refused(_entry(classification="guessed"), "classification")


@XFAIL
def test_refuses_a_status_outside_the_closed_set() -> None:
    _refused(_entry(status="shipped"), "status")


@XFAIL
@pytest.mark.parametrize("missing", _ND_FIELDS)
def test_refuses_a_non_determinable_entry_missing_any_of_its_five_fields(missing: str) -> None:
    _refused(_nd_entry(omit=missing), missing)


@XFAIL
@pytest.mark.parametrize("value", ["maybe", "", "true"])
def test_refuses_approximation_acceptable_other_than_yes_or_no(value: str) -> None:
    _refused(_nd_entry(approximation_acceptable=value), "approximation_acceptable")


@XFAIL
def test_refuses_a_blocked_entry_with_no_named_dependency() -> None:
    _refused(_entry(status="blocked"), "blocked_on")


@XFAIL
def test_refuses_a_blocked_entry_with_an_empty_blocked_on() -> None:
    _refused(_entry(status="blocked", extra='blocked_on = ""'), "blocked_on")


@XFAIL
def test_refuses_a_dangling_dependency() -> None:
    _refused(_entry(depends_on=["participant.does_not_exist"]), "dangling")


@XFAIL
def test_refuses_a_dependency_cycle() -> None:
    text = _entry("a.first", depends_on=["a.second"]) + _entry("a.second", depends_on=["a.first"])
    _refused(text, "cycle")


@XFAIL
def test_refuses_a_self_dependency() -> None:
    _refused(_entry("a.first", depends_on=["a.first"]), "cycle")


@XFAIL
def test_refuses_a_tier_stronger_than_the_weakest_dependency() -> None:
    text = _entry("a.base", classification="derived") + _entry(
        "a.top", classification="observed", depends_on=["a.base"]
    )
    _refused(text, "tier")


@XFAIL
def test_tier_is_judged_against_the_weakest_of_several_dependencies() -> None:
    text = (
        _entry("a.strong", classification="observed")
        + _entry("a.weak", classification="inferred", extra='confidence_method = "a method"')
        + _entry("a.top", classification="decoded", depends_on=["a.strong", "a.weak"])
    )
    _refused(text, "tier")


@XFAIL
def test_contrast_an_entry_as_weak_as_its_dependency_loads() -> None:
    text = _entry("a.base", classification="derived") + _entry(
        "a.top", classification="derived", depends_on=["a.base"]
    )
    assert _load(text) is not None


@XFAIL
@pytest.mark.parametrize("tier", ["inferred", "predicted"])
def test_refuses_a_published_weak_entry_with_no_confidence_method(tier: str) -> None:
    _refused(_entry(classification=tier), "confidence")


@XFAIL
def test_refuses_a_published_inferred_entry_with_an_empty_confidence_method() -> None:
    _refused(_entry(classification="inferred", extra='confidence_method = ""'), "confidence")


@XFAIL
def test_contrast_a_planned_inferred_entry_needs_no_confidence_method_yet() -> None:
    assert _load(_entry(classification="inferred", status="planned")) is not None


@XFAIL
def test_refuses_empty_evidence() -> None:
    _refused(_entry(evidence=""), "evidence")


@XFAIL
def test_refuses_missing_evidence() -> None:
    _refused(_entry(omit=("evidence",)), "evidence")


@XFAIL
@pytest.mark.parametrize(
    "bad_id",
    [
        "units_lost",  # one segment: no namespace
        "Participant.units_lost",  # uppercase
        "participant.units lost",  # whitespace
        "participant..units_lost",  # empty segment
        "participant.1units",  # segment starts with a digit
        "participant.units-lost",  # hyphen
    ],
)
def test_refuses_an_id_that_breaks_the_naming_shape(bad_id: str) -> None:
    _refused(_entry(bad_id), "id")
