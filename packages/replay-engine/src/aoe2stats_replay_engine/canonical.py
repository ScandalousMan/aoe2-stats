"""The canonical event stream: the pinned wheel's operations, mapped one pass, no copy (T625).

`canonical_events` is a generator over the `operations` the wheel has already materialised. That
materialisation is where R3's resident memory comes from and nothing here can remove it (FR-021);
what this module guarantees is that it adds no second copy: each operation is read where it sits,
turned into at most one `CanonicalEvent`, and yielded. The only state carried across operations is
the clock and two small sets that implement the first-occurrence rules below — never events.

The clock
---------
Every event's time is one clock, accumulated from the `time_increment` of each `Sync` operation.
Only actions carry a time of their own; chat and the post-game block carry none. Measured against
both committed recordings, the accumulated clock equals every action's own `world_time` and equals
the post-game `WorldTime` exactly (asserted in `tests/test_canonical.py`, since nothing else
verifies it). `Viewlock` operations are camera positions and are excluded because they carry no
intent — not because they feed the clock, which they do not.

Collapse (FR-018)
-----------------
Only the idempotent kinds collapse, each to its first occurrence over the whole match, no window:
research (an age-up is a research of technology 101/102/103, so it is the same rule) and
resignation. Queueing, placement and movement never collapse: the first recording's unit-queue
commands reduce to a few dozen distinct tuples, and collapsing them would erase the villager count.

Exit discipline
---------------
Nothing is attributed to a participant after their `participant-resigned`. An action whose
`player_id` names no seated participant yields no event at all — never an event with a silent or
invented participant.

What is not mapped yet
----------------------
Undecoded actions (T626), market and deletion (T626a) and chat (T626b) are routed through
`_unmapped_action` / `_unmapped_operation`, the two seams those tasks fill. Until then those
operation kinds yield nothing — a known gap, not a decision that they carry no information.
"""

from __future__ import annotations

import struct
from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import cast

from aoe2stats_core.replay.events import (
    BuildingPlacedPayload,
    CanonicalEvent,
    EventKind,
    MatchEndedPayload,
    Position,
    ResearchQueuedPayload,
    UnitQueuedPayload,
    UnitsCommandedPayload,
)
from aoe2stats_core.replay.validation import EngineParseError

# `Build.data[4:12]` is the placement position, two little-endian 32-bit floats in tiles. Found
# empirically, like the building identifier at `[12:16]` in `aoe2rec.decode_build_action`: every
# placement in both committed recordings falls inside the map's own dimensions, and the first one
# (12.0, 69.0) lies beside the same player's first movement command (17.8, 73.3). Pinned by
# `tests/test_canonical.py`.
_BUILD_POSITION_OFFSET = 4
_BUILD_POSITION_STRUCT = struct.Struct("<ff")
_BUILD_ID_OFFSET = 12
_BUILD_ID_STRUCT = struct.Struct("<I")

_MOVE = "move"
_INTERACT = "interact"
_ORDER = "order"

_Payload = Mapping[str, object]


class _Exits:
    """The two first-occurrence rules and the exit rule, as the only cross-operation state."""

    def __init__(self) -> None:
        self._researched: set[tuple[int, int]] = set()
        self._resigned: set[int] = set()

    def has_exited(self, participant: int) -> bool:
        return participant in self._resigned

    def first_research(self, participant: int, technology_id: int) -> bool:
        key = (participant, technology_id)
        if key in self._researched:
            return False
        self._researched.add(key)
        return True

    def first_resignation(self, participant: int) -> bool:
        if participant in self._resigned:
            return False
        self._resigned.add(participant)
        return True


def _ints(value: object) -> tuple[int, ...]:
    return tuple(cast(Sequence[int], value))


def _building_placed(clock: int, player: int, payload: _Payload, _: _Exits) -> CanonicalEvent:
    data = bytes(cast(Sequence[int], payload["data"]))
    x, y = _BUILD_POSITION_STRUCT.unpack_from(data, _BUILD_POSITION_OFFSET)
    (building_id,) = _BUILD_ID_STRUCT.unpack_from(data, _BUILD_ID_OFFSET)
    return CanonicalEvent(
        clock_ms=clock,
        kind=EventKind.BUILDING_PLACED,
        participant=player,
        payload=BuildingPlacedPayload(building_id=building_id, position=Position(x=x, y=y)),
    )


def _unit_queued(clock: int, player: int, payload: _Payload, _: _Exits) -> CanonicalEvent | None:
    # One command is one event. A command may name several producing buildings; the payload
    # carries one `building_object`, so the first one the wheel lists is kept and the rest are
    # not represented — a known narrowing of the vocabulary, reported at hand-back.
    building_objects = _ints(payload["building_ids"])
    if not building_objects:
        return None
    return CanonicalEvent(
        clock_ms=clock,
        kind=EventKind.UNIT_QUEUED,
        participant=player,
        payload=UnitQueuedPayload(
            unit_id=cast(int, payload["unit_id"]),
            building_object=building_objects[0],
            count=cast(int, payload["amount"]),
        ),
    )


def _research_queued(
    clock: int, player: int, payload: _Payload, state: _Exits
) -> CanonicalEvent | None:
    technology_id = cast(int, payload["technology_type"])
    if not state.first_research(player, technology_id):
        return None
    return CanonicalEvent(
        clock_ms=clock,
        kind=EventKind.RESEARCH_QUEUED,
        participant=player,
        payload=ResearchQueuedPayload(
            technology_id=technology_id, building_object=cast(int, payload["building_id"])
        ),
    )


def _resigned(clock: int, player: int, _: _Payload, state: _Exits) -> CanonicalEvent | None:
    if not state.first_resignation(player):
        return None
    return CanonicalEvent(clock_ms=clock, kind=EventKind.PARTICIPANT_RESIGNED, participant=player)


def _commanded(
    clock: int, player: int, command_class: str, unit_objects: object, target: int | Position | None
) -> CanonicalEvent:
    return CanonicalEvent(
        clock_ms=clock,
        kind=EventKind.UNITS_COMMANDED,
        participant=player,
        payload=UnitsCommandedPayload(
            command_class=command_class, unit_objects=_ints(unit_objects), target=target
        ),
    )


def _move(clock: int, player: int, payload: _Payload, _: _Exits) -> CanonicalEvent:
    target = Position(x=cast(float, payload["x"]), y=cast(float, payload["y"]))
    return _commanded(clock, player, _MOVE, payload["unit_ids"], target)


def _interact(clock: int, player: int, payload: _Payload, _: _Exits) -> CanonicalEvent:
    return _commanded(
        clock, player, _INTERACT, payload["unit_ids"], cast(int, payload["target_id"])
    )


def _order(clock: int, player: int, payload: _Payload, _: _Exits) -> CanonicalEvent:
    # `building_id` is -1 when the order names no building: no target then, never a stand-in.
    building = cast(int, payload["building_id"])
    return _commanded(
        clock, player, _ORDER, payload["object_ids"], building if building >= 0 else None
    )


_ActionMapper = Callable[[int, int, _Payload, _Exits], CanonicalEvent | None]

# Keyed by the wheel's own action label. Anything absent goes to `_unmapped_action`.
_ACTION_MAPPERS: Mapping[str, _ActionMapper] = {
    "Build": _building_placed,
    "DeQueue": _unit_queued,
    "Research": _research_queued,
    "Resign": _resigned,
    "Move": _move,
    "Interact": _interact,
    "Order": _order,
}


def _unmapped_action(
    clock: int, player: int, label: str, payload: _Payload, state: _Exits
) -> CanonicalEvent | None:
    """The seam T626 fills with the `undecoded` event (and market, deletion, empty-id commands).

    Returns nothing today. That is a gap in this task's scope, not a claim the action is empty.
    """
    return None


def _unmapped_operation(kind: str, operation: _Payload) -> CanonicalEvent | None:
    """The seam T626b fills for `Chat`. `Sync`, `Viewlock` and `PostGame` never reach it."""
    return None


def _match_ended(clock: int, operation: _Payload) -> CanonicalEvent:
    blocks = cast(Sequence[Mapping[str, object]], operation["blocks"])
    for block in blocks:
        if "WorldTime" in block:
            world_time = cast(Mapping[str, object], block["WorldTime"])
            return CanonicalEvent(
                clock_ms=clock,
                kind=EventKind.MATCH_ENDED,
                payload=MatchEndedPayload(final_clock_ms=cast(int, world_time["world_time"])),
            )
    raise EngineParseError("PostGame block carries no WorldTime entry")


def _seated(parsed: Mapping[str, object]) -> frozenset[int]:
    """The participants: the slots the wheel lists in the game settings, by `player_number`.

    An action naming any other id belongs to no participant and yields no event.
    """
    zheader = cast(Mapping[str, object], parsed["zheader"])
    settings = cast(Mapping[str, object], zheader["game_settings"])
    players = cast(Sequence[Mapping[str, object]], settings["players"])
    return frozenset(cast(int, player["player_number"]) for player in players)


def canonical_events(parsed: Mapping[str, object]) -> Iterator[CanonicalEvent]:
    """Yield the canonical events of one parsed replay, in stream order, in one pass."""
    seated = _seated(parsed)
    state = _Exits()
    clock = 0
    operations = cast(Sequence[Mapping[str, object]], parsed["operations"])
    for operation in operations:
        kind = next(iter(operation))
        body = cast(_Payload, operation[kind])
        event: CanonicalEvent | None
        if kind == "Sync":
            clock += cast(int, body["time_increment"])
            continue
        if kind == "Viewlock":
            continue
        if kind == "PostGame":
            yield _match_ended(clock, body)
            continue
        if kind != "Action":
            event = _unmapped_operation(kind, body)
        else:
            action_data = cast(Mapping[str, _Payload], body["action_data"])
            label, payload = next(iter(action_data.items()))
            player = cast(int, payload["player_id"])
            if player not in seated or state.has_exited(player):
                continue
            mapper = _ACTION_MAPPERS.get(label)
            if mapper is None:
                event = _unmapped_action(clock, player, label, payload, state)
            else:
                event = mapper(clock, player, payload, state)
        if event is not None:
            yield event
