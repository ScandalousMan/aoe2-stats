"""The closed invariant set of FR-017 (data-model section 8).

Each invariant has one check over a stream of plain records, each with a `kind`, a `participant`
(a slot, as in data-model section 1) and the fields of its datum. A check raises `InvariantBreach`
naming the invariant, the participant, the datum and the offending value. A document with a breach
is not published (SC-007): `check_invariants` returns nothing, so a caller that gets no return value
has nothing to publish.

The two population-owned invariants are declared with no check; the population phase enables them.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from enum import StrEnum

from aoe2stats_reconstruction.orders import OrderKind

Record = Mapping[str, object]
Stream = Sequence[Record]


class Invariant(StrEnum):
    """The closed set of invariants (data-model section 8)."""

    SPENDING_NON_NEGATIVE = "spending-non-negative"
    CANCELLATION_BOUNDED = "cancellation-bounded"
    POPULATION_NON_NEGATIVE = "population-non-negative"
    IDLE_BOUNDED = "idle-bounded"
    ARRIVAL_AFTER_CLICK = "arrival-after-click"
    NOTHING_AFTER_EXIT = "nothing-after-exit"
    MILITARY_WITHIN_TOTAL = "military-within-total"
    STARTING_RESOURCES_AGREE = "starting-resources-agree"
    PROOF_NOT_CONTRADICTED = "proof-not-contradicted"


class InvariantBreach(Exception):
    """A broken invariant: which one, for which participant, which datum, which value."""

    def __init__(
        self, invariant: Invariant, participant: object, datum: str, value: object
    ) -> None:
        self.invariant = invariant
        self.participant = participant
        self.datum = datum
        self.value = value
        super().__init__(
            f"invariant {invariant.value} broken: participant {participant}, "
            f"datum {datum}, value {value}"
        )


def _number(record: Record, field: str) -> float:
    value = record[field]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"field {field!r} of a {record.get('kind')!r} record is not a number")
    return value


def _spending_non_negative(stream: Stream) -> None:
    for record in stream:
        if record.get("kind") == "spend" and _number(record, "amount") < 0:
            raise InvariantBreach(
                Invariant.SPENDING_NON_NEGATIVE,
                record["participant"],
                str(record["resource"]),
                record["amount"],
            )


def _cancellation_bounded(stream: Stream) -> None:
    # A `queue` record states how many items the participant has unstarted at that point; a
    # `cancel` removes unstarted items only (data-model section 2), so it may remove at most that.
    unstarted: dict[object, float] = {}
    for record in stream:
        kind = record.get("kind")
        participant = record["participant"]
        if kind == "queue":
            unstarted[participant] = _number(record, "unstarted")
        elif kind == "cancel":
            count = _number(record, "count")
            available = unstarted.get(participant, 0)
            if count > available:
                raise InvariantBreach(
                    Invariant.CANCELLATION_BOUNDED, participant, "cancel", record["count"]
                )
            unstarted[participant] = available - count


def _arrival_after_click(stream: Stream) -> None:
    for record in stream:
        if record.get("kind") == "age-up" and _number(record, "arrival_at") < _number(
            record, "click_at"
        ):
            raise InvariantBreach(
                Invariant.ARRIVAL_AFTER_CLICK,
                record["participant"],
                "age-up",
                record["arrival_at"],
            )


def _nothing_after_exit(stream: Stream) -> None:
    # An order is any record of an `OrderKind` (data-model section 1); it carries `clock_ms`.
    order_kinds = {kind.value for kind in OrderKind}
    resigned: set[object] = set()
    for record in stream:
        kind = record.get("kind")
        participant = record["participant"]
        if kind == "resign":
            resigned.add(participant)
        elif kind in order_kinds and participant in resigned:
            raise InvariantBreach(
                Invariant.NOTHING_AFTER_EXIT, participant, "order", record["clock_ms"]
            )


def _military_within_total(stream: Stream) -> None:
    for record in stream:
        if record.get("kind") == "share" and _number(record, "military") > _number(record, "total"):
            raise InvariantBreach(
                Invariant.MILITARY_WITHIN_TOTAL,
                record["participant"],
                str(record["resource"]),
                record["military"],
            )


def _starting_resources_agree(stream: Stream) -> None:
    for record in stream:
        if record.get("kind") == "starting" and record["decoded"] != record["derived"]:
            raise InvariantBreach(
                Invariant.STARTING_RESOURCES_AGREE,
                record["participant"],
                str(record["resource"]),
                record["decoded"],
            )


def _proof_not_contradicted(stream: Stream) -> None:
    for record in stream:
        if record.get("kind") == "contradiction":
            raise InvariantBreach(
                Invariant.PROOF_NOT_CONTRADICTED,
                record["participant"],
                str(record["condition"]),
                record["at"],
            )


CHECKS: Mapping[Invariant, Callable[[Stream], None] | None] = {
    Invariant.SPENDING_NON_NEGATIVE: _spending_non_negative,
    Invariant.CANCELLATION_BOUNDED: _cancellation_bounded,
    Invariant.POPULATION_NON_NEGATIVE: None,
    Invariant.IDLE_BOUNDED: None,
    Invariant.ARRIVAL_AFTER_CLICK: _arrival_after_click,
    Invariant.NOTHING_AFTER_EXIT: _nothing_after_exit,
    Invariant.MILITARY_WITHIN_TOTAL: _military_within_total,
    Invariant.STARTING_RESOURCES_AGREE: _starting_resources_agree,
    Invariant.PROOF_NOT_CONTRADICTED: _proof_not_contradicted,
}


def check_invariants(stream: Stream) -> None:
    """Run every enabled check and raise the first breach; return nothing."""
    for check in CHECKS.values():
        if check is not None:
            check(stream)
