"""The closed invariant set of FR-017 (data-model section 8): one synthetic stream per invariant
breaks exactly that invariant, the breach names it, and nothing is published (SC-007).

Assumed API of `aoe2stats_reconstruction.invariants` (T921 must provide it):

- `Invariant`: a `StrEnum` with the nine members of data-model section 8.
- `CHECKS`: `Mapping[Invariant, Callable[[Sequence[Mapping[str, object]]], None] | None]`, one entry
  per invariant; `None` means declared with no check (the two population-owned ones).
- `InvariantBreach(Exception)`: attributes `invariant`, `participant`, `datum`, `value`; its
  message names all four.
- `check_invariants(stream) -> None`: runs every enabled check, raises the first breach, and
  returns nothing, so a caller that gets no return value has nothing to publish.

A stream is a sequence of plain records, each with a `kind`, a `participant` slot (an integer, as in
data-model section 1) and the fields of its datum. An order record has an `OrderKind` value as its
`kind` and the section 1 field `clock_ms`; a resignation is a `resign` record with `clock_ms`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pytest

_Stream = Sequence[Mapping[str, object]]

_ENABLED = [
    "spending-non-negative",
    "cancellation-bounded",
    "arrival-after-click",
    "nothing-after-exit",
    "military-within-total",
    "starting-resources-agree",
    "proof-not-contradicted",
]
_POPULATION_OWNED = ["population-non-negative", "idle-bounded"]

# invariant -> (stream that breaks exactly it, participant, datum, offending value)
_BREACHES: dict[str, tuple[_Stream, int, str, object]] = {
    "spending-non-negative": (
        [{"kind": "spend", "participant": 1, "resource": "wood", "amount": -50}],
        1,
        "wood",
        -50,
    ),
    "cancellation-bounded": (
        [
            {"kind": "queue", "participant": 1, "unstarted": 2},
            {"kind": "cancel", "participant": 1, "count": 5},
        ],
        1,
        "cancel",
        5,
    ),
    "arrival-after-click": (
        [
            {
                "kind": "age-up",
                "participant": 2,
                "click_at": 600,
                "arrival_at": 590,
            }
        ],
        2,
        "age-up",
        590,
    ),
    "nothing-after-exit": (
        [
            {"kind": "resign", "participant": 2, "clock_ms": 300},
            {"kind": "unit", "participant": 2, "clock_ms": 340, "count": 1},
        ],
        2,
        "order",
        340,
    ),
    "military-within-total": (
        [
            {
                "kind": "share",
                "participant": 1,
                "resource": "gold",
                "military": 120,
                "total": 100,
            }
        ],
        1,
        "gold",
        120,
    ),
    "starting-resources-agree": (
        [
            {
                "kind": "starting",
                "participant": 1,
                "resource": "food",
                "decoded": 250,
                "derived": 200,
            }
        ],
        1,
        "food",
        250,
    ),
    "proof-not-contradicted": (
        [
            {
                "kind": "contradiction",
                "participant": 1,
                "rule": "adopted-rule",
                "condition": "age-not-reached",
                "at": 450,
            }
        ],
        1,
        "age-not-reached",
        450,
    ),
}


def test_the_closed_set_has_exactly_the_nine_invariants() -> None:
    from aoe2stats_reconstruction.invariants import CHECKS, Invariant

    expected = set(_ENABLED) | set(_POPULATION_OWNED)
    assert {member.value for member in Invariant} == expected
    assert set(CHECKS) == set(Invariant)


@pytest.mark.parametrize("name", _POPULATION_OWNED)
def test_population_owned_invariants_are_declared_with_no_check(name: str) -> None:
    from aoe2stats_reconstruction.invariants import CHECKS, Invariant

    assert Invariant(name) in CHECKS
    assert CHECKS[Invariant(name)] is None


@pytest.mark.parametrize("name", _ENABLED)
def test_every_other_invariant_has_a_check(name: str) -> None:
    from aoe2stats_reconstruction.invariants import CHECKS, Invariant

    assert callable(CHECKS[Invariant(name)])


@pytest.mark.parametrize("name", _ENABLED)
def test_a_stream_breaking_one_invariant_names_it(name: str) -> None:
    from aoe2stats_reconstruction.invariants import Invariant, InvariantBreach, check_invariants

    stream, participant, datum, value = _BREACHES[name]
    with pytest.raises(InvariantBreach) as raised:
        check_invariants(stream)
    breach = raised.value
    assert breach.invariant == Invariant(name)
    assert breach.participant == participant
    assert breach.datum == datum
    assert breach.value == value
    message = str(breach)
    for part in (name, str(participant), datum, str(value)):
        assert part in message


@pytest.mark.parametrize("name", _ENABLED)
def test_a_breach_publishes_nothing(name: str) -> None:
    """The publish step sits after the check, so it is reached only if the check returned."""
    from aoe2stats_reconstruction.invariants import InvariantBreach, check_invariants

    stream, _participant, _datum, _value = _BREACHES[name]
    published: list[object] = []

    def publish() -> None:
        published.append(stream)

    with pytest.raises(InvariantBreach):
        check_invariants(stream)
        publish()
    assert published == []


def test_a_stream_breaking_nothing_passes() -> None:
    from aoe2stats_reconstruction.invariants import check_invariants

    stream: _Stream = [
        {"kind": "spend", "participant": 1, "resource": "wood", "amount": 50},
        {"kind": "queue", "participant": 1, "unstarted": 5},
        {"kind": "cancel", "participant": 1, "count": 2},
        {"kind": "age-up", "participant": 1, "click_at": 600, "arrival_at": 640},
    ]
    assert check_invariants(stream) is None
