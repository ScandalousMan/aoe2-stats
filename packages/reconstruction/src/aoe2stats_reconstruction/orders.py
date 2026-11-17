"""One fold over a canonical stream yields the orders of data-model section 1 (FR-002).

The fold reads the canonical vocabulary only (constitution V): no engine shape, no re-parse.
Nothing is attributed to a participant after its resignation (FR-017, `nothing-after-exit`), and
nothing to a slot the match start does not list as a participant.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from aoe2stats_core.replay.events import (
    BuildingPlacedPayload,
    CanonicalEvent,
    EventKind,
    MatchStartedPayload,
    ObjectDeletedPayload,
    ResearchQueuedPayload,
    UnitQueuedPayload,
    UnitUnqueuedPayload,
)
from aoe2stats_knowledge.query import EntityRef


class OrderKind(Enum):
    """The closed set of order kinds: one per ordering source event kind."""

    UNIT = "unit"
    RESEARCH = "research"
    PLACEMENT = "placement"
    CANCELLATION = "cancellation"
    DELETION = "deletion"


@dataclass(frozen=True, slots=True)
class Order:
    """A command the canonical stream attributes to a participant (data-model section 1)."""

    participant: int
    clock_ms: int
    kind: OrderKind
    entity: EntityRef | None
    count: int
    buildings: tuple[int, ...]
    object: int | None
    source_event: int


def fold_orders(events: Iterable[CanonicalEvent]) -> tuple[Order, ...]:
    """Fold a canonical stream into its orders, in stream order, in a single pass."""
    build: int | None = None
    listed: frozenset[int] | None = None
    resigned: set[int] = set()
    orders: list[Order] = []

    def entity(kind: str, identifier: int) -> EntityRef:
        if build is None:
            raise ValueError("the stream names an entity before any match start carries a build")
        return EntityRef(kind, str(identifier), build)

    for index, event in enumerate(events):
        payload = event.payload
        if event.kind is EventKind.MATCH_STARTED and isinstance(payload, MatchStartedPayload):
            build = payload.build
            if payload.participants:
                listed = frozenset(p.slot for p in payload.participants)
            continue
        slot = event.participant
        if slot is None:
            continue
        if event.kind is EventKind.PARTICIPANT_RESIGNED:
            resigned.add(slot)
            continue
        if slot in resigned or (listed is not None and slot not in listed):
            continue

        order: Order | None = None
        if event.kind is EventKind.UNIT_QUEUED and isinstance(payload, UnitQueuedPayload):
            buildings = payload.building_objects or (payload.building_object,)
            order = Order(
                slot,
                event.clock_ms,
                OrderKind.UNIT,
                entity("unit", payload.unit_id),
                payload.count,
                tuple(buildings),
                None,
                index,
            )
        elif event.kind is EventKind.RESEARCH_QUEUED and isinstance(payload, ResearchQueuedPayload):
            order = Order(
                slot,
                event.clock_ms,
                OrderKind.RESEARCH,
                entity("technology", payload.technology_id),
                1,
                (payload.building_object,),
                None,
                index,
            )
        elif event.kind is EventKind.BUILDING_PLACED and isinstance(payload, BuildingPlacedPayload):
            order = Order(
                slot,
                event.clock_ms,
                OrderKind.PLACEMENT,
                entity("building", payload.building_id),
                1,
                (),
                None,
                index,
            )
        elif event.kind is EventKind.UNIT_UNQUEUED and isinstance(payload, UnitUnqueuedPayload):
            order = Order(
                slot,
                event.clock_ms,
                OrderKind.CANCELLATION,
                entity("unit", payload.unit_id),
                1,
                (),
                None,
                index,
            )
        elif event.kind is EventKind.OBJECT_DELETED and isinstance(payload, ObjectDeletedPayload):
            order = Order(
                slot, event.clock_ms, OrderKind.DELETION, None, 1, (), payload.object_id, index
            )
        if order is not None:
            orders.append(order)
    return tuple(orders)
