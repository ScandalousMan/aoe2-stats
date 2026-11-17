"""One fold over a canonical stream yields the orders of data-model section 1 (FR-002, FR-017's
`nothing-after-exit`). The fold's entry point is `fold_orders(events) -> tuple[Order, ...]`, in
`aoe2stats_reconstruction.orders`; T915 wrote it."""

from __future__ import annotations

import pytest

from aoe2stats_core.replay.events import (
    BuildingPlacedPayload,
    CanonicalEvent,
    ChatPayload,
    EventKind,
    MarketTransactionPayload,
    MatchEndedPayload,
    MatchStartedPayload,
    ObjectDeletedPayload,
    ParticipantEntry,
    Position,
    ResearchQueuedPayload,
    UndecodedPayload,
    UnitQueuedPayload,
    UnitsCommandedPayload,
    UnitUnqueuedPayload,
)

_BUILD = 99999
_ONE, _TWO = 1, 2


def _enum_value(member: object) -> object:
    return getattr(member, "value", member)


def _stream() -> list[CanonicalEvent]:
    """Index 0 is the match start; participant 1 resigns at index 9; 2 never does."""
    return [
        CanonicalEvent(
            0,
            EventKind.MATCH_STARTED,
            payload=MatchStartedPayload(
                build=_BUILD,
                map_name=None,
                participants=(
                    ParticipantEntry(slot=_ONE, civilisation=1, team=None),
                    ParticipantEntry(slot=_TWO, civilisation=2, team=None),
                ),
            ),
        ),
        CanonicalEvent(
            1000,
            EventKind.UNIT_QUEUED,
            _ONE,
            UnitQueuedPayload(
                unit_id=83,
                building_type=109,
                building_object=500,
                count=3,
                building_objects=(500, 501, 502),
            ),
        ),
        CanonicalEvent(
            2000, EventKind.RESEARCH_QUEUED, _ONE, ResearchQueuedPayload(202, building_object=500)
        ),
        CanonicalEvent(
            3000, EventKind.BUILDING_PLACED, _ONE, BuildingPlacedPayload(70, Position(10.0, 12.0))
        ),
        CanonicalEvent(4000, EventKind.UNIT_UNQUEUED, _ONE, UnitUnqueuedPayload(83, 1)),
        CanonicalEvent(5000, EventKind.OBJECT_DELETED, _ONE, ObjectDeletedPayload(777)),
        CanonicalEvent(6000, EventKind.UNITS_COMMANDED, _ONE, UnitsCommandedPayload("move", (1,))),
        CanonicalEvent(7000, EventKind.CHAT, _ONE, ChatPayload("all")),
        CanonicalEvent(
            8000, EventKind.MARKET_TRANSACTION, _ONE, MarketTransactionPayload("buy", "food", 1)
        ),
        CanonicalEvent(9000, EventKind.PARTICIPANT_RESIGNED, _ONE),
        CanonicalEvent(
            10000,
            EventKind.UNIT_QUEUED,
            _TWO,
            UnitQueuedPayload(
                unit_id=74, building_type=12, building_object=600, count=1, building_objects=(600,)
            ),
        ),
        CanonicalEvent(11000, EventKind.UNDECODED, _TWO, UndecodedPayload("x", 4)),
        CanonicalEvent(
            12000,
            EventKind.UNIT_QUEUED,
            _ONE,
            UnitQueuedPayload(
                unit_id=83, building_type=109, building_object=500, count=1, building_objects=(500,)
            ),
        ),
        CanonicalEvent(13000, EventKind.OBJECT_DELETED, _ONE, ObjectDeletedPayload(778)),
        CanonicalEvent(14000, EventKind.MATCH_ENDED, payload=MatchEndedPayload(14000)),
    ]


def test_one_fold_yields_one_order_per_ordering_event_kind() -> None:
    from aoe2stats_reconstruction.orders import fold_orders

    orders = fold_orders(_stream())

    assert [(o.participant, o.clock_ms, _enum_value(o.kind), o.source_event) for o in orders] == [
        (_ONE, 1000, "unit", 1),
        (_ONE, 2000, "research", 2),
        (_ONE, 3000, "placement", 3),
        (_ONE, 4000, "cancellation", 4),
        (_ONE, 5000, "deletion", 5),
        (_TWO, 10000, "unit", 10),
    ]


def test_a_unit_order_names_every_producing_building_and_its_count() -> None:
    from aoe2stats_reconstruction.orders import fold_orders

    unit = fold_orders(_stream())[0]

    assert unit.buildings == (500, 501, 502)
    assert unit.count == 3
    assert unit.entity is not None
    assert (unit.entity.kind, unit.entity.id, unit.entity.build) == ("unit", "83", _BUILD)


def test_research_placement_cancellation_and_deletion_shapes() -> None:
    from aoe2stats_reconstruction.orders import fold_orders

    research, placement, cancellation, deletion = fold_orders(_stream())[1:5]

    assert research.entity is not None
    assert (research.entity.kind, research.entity.id) == ("technology", "202")
    assert (research.count, research.buildings) == (1, (500,))

    assert placement.entity is not None
    assert (placement.entity.kind, placement.entity.id) == ("building", "70")
    assert (placement.count, placement.buildings) == (1, ())

    assert cancellation.entity is not None
    assert (cancellation.entity.kind, cancellation.entity.id) == ("unit", "83")

    assert deletion.entity is None
    assert deletion.object == 777
    assert (deletion.count, deletion.buildings) == (1, ())


def test_nothing_is_attributed_after_a_participants_resignation() -> None:
    from aoe2stats_reconstruction.orders import fold_orders

    orders = fold_orders(_stream())

    assert not [o for o in orders if o.participant == _ONE and o.clock_ms > 9000]
    assert {o.source_event for o in orders}.isdisjoint({12, 13})
    # The other participant's orders are untouched by the first one's exit.
    assert [o.source_event for o in orders if o.participant == _TWO] == [10]


def test_source_event_indexes_the_stream_and_the_fold_is_one_pass() -> None:
    from aoe2stats_reconstruction.orders import fold_orders

    stream = _stream()
    orders = fold_orders(iter(stream))

    for order in orders:
        assert stream[order.source_event].clock_ms == order.clock_ms
        assert stream[order.source_event].participant == order.participant
    assert [o.source_event for o in orders] == sorted(o.source_event for o in orders)


def _match_started(participants: tuple[ParticipantEntry, ...]) -> CanonicalEvent:
    return CanonicalEvent(
        0,
        EventKind.MATCH_STARTED,
        payload=MatchStartedPayload(build=_BUILD, map_name=None, participants=participants),
    )


def _queue(slot: int, clock_ms: int = 1000) -> CanonicalEvent:
    return CanonicalEvent(
        clock_ms,
        EventKind.UNIT_QUEUED,
        slot,
        UnitQueuedPayload(
            unit_id=83, building_type=109, building_object=500, count=1, building_objects=(500,)
        ),
    )


def test_a_cancellation_carries_the_count_its_payload_states() -> None:
    from aoe2stats_reconstruction.orders import fold_orders

    listed = (ParticipantEntry(slot=_ONE, civilisation=1, team=None),)
    events = [
        _match_started(listed),
        CanonicalEvent(1000, EventKind.UNIT_UNQUEUED, _ONE, UnitUnqueuedPayload(83, 5)),
        CanonicalEvent(2000, EventKind.UNIT_UNQUEUED, _ONE, UnitUnqueuedPayload(83, 1)),
    ]

    five, one = fold_orders(events)

    assert five.count == 5
    assert one.count == 1


def test_a_slot_the_match_start_does_not_list_yields_no_order() -> None:
    from aoe2stats_reconstruction.orders import fold_orders

    observer = 8
    listed = (ParticipantEntry(slot=_ONE, civilisation=1, team=None),)
    events = [
        _match_started(listed),
        _queue(observer, 1000),
        CanonicalEvent(1500, EventKind.OBJECT_DELETED, observer, ObjectDeletedPayload(9)),
        _queue(_ONE, 2000),
    ]

    orders = fold_orders(events)

    assert [(o.participant, o.source_event) for o in orders] == [(_ONE, 3)]


def test_an_empty_participant_list_yields_no_orders() -> None:
    """`MatchStartedPayload.participants` defaults to empty, so an empty list is a valid payload
    that lists nobody. No slot is listed, so none is a participant (data-model section 1: never
    an observer) and the fold yields no orders."""
    from aoe2stats_reconstruction.orders import fold_orders

    orders = fold_orders([_match_started(()), _queue(_ONE), _queue(_TWO, 2000)])

    assert orders == ()


def test_an_entity_named_before_any_build_is_known_raises() -> None:
    from aoe2stats_reconstruction.orders import fold_orders

    with pytest.raises(ValueError, match="before any match start"):
        fold_orders([_queue(_ONE)])
