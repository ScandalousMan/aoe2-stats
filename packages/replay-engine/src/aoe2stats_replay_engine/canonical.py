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

No silent drop (FR-019) and the accounting
------------------------------------------
Every operation is exactly one of: a `Sync` (consumed for the clock), a `Viewlock` (a camera
position, no intent), an operation that yields one event, or an operation deliberately dropped for
one of three named reasons. `Accounting` counts each reason as it happens, so that

    events + syncs + viewlocks + collapsed + after_exit + unseated == operations

is an equation a test can check rather than an assurance:

- `collapsed`: a repeated research or resignation (FR-018);
- `after_exit`: an action by a participant who has already resigned;
- `unseated`: an action naming a `player_id` that is no seated slot;

Chat (T626b) is an operation like any other: it yields one `chat` event, or is counted as
`after_exit` / `unseated` by the participant its JSON names, exactly as an action would be.

Chat and the message text
-------------------------
A chat operation is one JSON string holding the sender, the channel and the message. The text
cannot be avoided on the way to the other two, so it is parsed and then discarded here: it is bound
to no name that outlives `_decode_chat`, appears in no event, no exception message and no log line
(this module logs nothing). A string that is not the expected JSON object is counted as
`unseated` (it names no seated participant, and `undecoded` requires one), never quoted. The
channel is the game's integer, carried as its decimal string; the recordings only ever show
channel 0 and the names of the others cannot be established from them, so none is invented.

Every action the adapter does not decode is emitted as `undecoded`, carrying the engine's own label
(for a `Game` command, the wheel's name for the inner command) and the payload length the wheel
reports — never dropped, never guessed at. Command kinds that name no decoded unit ids are
`units-commanded` with an empty id list. Market and deletion are decoded (T626a) from raw
payloads, and fall back to `undecoded` when a payload does not fit the layout found empirically.
"""

from __future__ import annotations

import json
import struct
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from aoe2stats_core.replay.events import (
    BuildingPlacedPayload,
    CanonicalEvent,
    ChatPayload,
    EventKind,
    MarketTransactionPayload,
    MatchEndedPayload,
    ObjectDeletedPayload,
    Position,
    ResearchQueuedPayload,
    UndecodedPayload,
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

# Market and deletion (T626a, FR-014). The wheel returns Sell, Buy and Delete as raw bytes; the
# layouts below were found by sweeping every byte position of every instance in both committed
# recordings (107 + 115 transactions, 59 deletions), not read from documentation:
#
#   Sell/Buy  8 bytes  `<h resource> <h amount> <I market object id>`
#   Delete    4 bytes  `<I object id>`
#
# What the sweep established, and how:
# - Byte 1 and byte 3 are zero in all 222 transactions; bytes 4..7 are a stable per-market id (five
#   distinct ones in the first recording, three in the second, each used by one player). Two of
#   those ids reappear as `Delete` payloads later, each after the market's last transaction — the
#   same object, so the position is the market's object id. Three more are named by the same
#   player's other commands, the rest by none (a market can go unnamed).
# - Delete has no other bytes. 18 of the 59 ids are named by the same recording's move, interact,
#   order, research or transaction commands *before* the delete and none is named more than two
#   seconds *after* it; no id is deleted twice; all lie inside the range of ids the recording
#   itself uses. That is what an object id does and what a random u32 would not.
# - Direction is the wheel's own action label (Sell / Buy), not a payload field.
# - Resource is only ever 0, 1 or 2 (gold never appears: it is the market's counter-currency), the
#   three tradeable resources in the game's attribute order food, wood, stone. The value set is
#   verified against the recordings; the *names* are the game's own enumeration, which the
#   recordings cannot confirm by themselves (aoc-mgz reads the same layout with the same names).
# - Amount is only ever 1 or 5: one click and one shift-click, counted in market steps. A step is
#   100 units of the resource, the game's fixed market step; that constant is not in the recording.
#
# A payload that does not fit (length, unknown resource code, non-positive amount) is emitted as
# `undecoded`, never decoded from a guess.
_MARKET_STRUCT = struct.Struct("<hhI")
_MARKET_RESOURCES: Mapping[int, str] = {0: "food", 1: "wood", 2: "stone"}
_MARKET_STEP = 100
_DELETE_STRUCT = struct.Struct("<I")

_MOVE = "move"
_INTERACT = "interact"
_ORDER = "order"

_Payload = Mapping[str, object]

# Command kinds that command units but whose unit ids the adapter does not decode. Each becomes
# `units-commanded` with an empty id list and no target. Deliberately absent: `Transform` (not
# established to be a unit command), `Sell`/`Buy`/`Delete` (decoded, T626a), `Flare`, `TownBell`,
# `Game` and anything the wheel cannot name, which stay `undecoded`.
_UNIT_COMMANDS: Mapping[str, str] = {
    "Formation": "formation",
    "Stance": "stance",
    "Patrol": "patrol",
    "Stop": "stop",
    "Gatherpoint": "gatherpoint",
    "Release": "release",
    "Wall": "wall",
    "Repair": "repair",
    "BackToWork": "back-to-work",
    "Autoscout": "autoscout",
    "DeAttackMove": "attack-move",
    "AttackGround": "attack-ground",
}


@dataclass(slots=True)
class Accounting:
    """Counts of the operations that yield no event, by reason. See the module docstring."""

    collapsed: int = 0
    after_exit: int = 0
    unseated: int = 0


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
        # No producing building to name: undecoded rather than dropped (FR-019).
        return _undecoded("DeQueue", clock, player, payload)
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


def _market(direction: str, label: str) -> _ActionMapper:
    def decode(clock: int, player: int, payload: _Payload, _: _Exits) -> CanonicalEvent:
        data = bytes(cast(Sequence[int], payload["data"]))
        if len(data) == _MARKET_STRUCT.size:
            resource, steps, _market_object = _MARKET_STRUCT.unpack(data)
            name = _MARKET_RESOURCES.get(resource)
            if name is not None and steps > 0:
                return CanonicalEvent(
                    clock_ms=clock,
                    kind=EventKind.MARKET_TRANSACTION,
                    participant=player,
                    payload=MarketTransactionPayload(
                        direction=direction, resource=name, amount=steps * _MARKET_STEP
                    ),
                )
        return _undecoded(label, clock, player, payload)

    return decode


def _deleted(clock: int, player: int, payload: _Payload, _: _Exits) -> CanonicalEvent:
    data = bytes(cast(Sequence[int], payload["data"]))
    if len(data) != _DELETE_STRUCT.size:
        return _undecoded("Delete", clock, player, payload)
    (object_id,) = _DELETE_STRUCT.unpack(data)
    return CanonicalEvent(
        clock_ms=clock,
        kind=EventKind.OBJECT_DELETED,
        participant=player,
        payload=ObjectDeletedPayload(object_id=object_id),
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
    "Sell": _market("sell", "Sell"),
    "Buy": _market("buy", "Buy"),
    "Delete": _deleted,
}


def _undecoded(label: str, clock: int, player: int, payload: _Payload) -> CanonicalEvent:
    return CanonicalEvent(
        clock_ms=clock,
        kind=EventKind.UNDECODED,
        participant=player,
        payload=UndecodedPayload(
            operation=label, payload_length=cast(int, payload["action_length"])
        ),
    )


def _unmapped_action(clock: int, player: int, label: str, payload: _Payload) -> CanonicalEvent:
    """Every action the adapter does not decode: never dropped, never guessed at (FR-019)."""
    command_class = _UNIT_COMMANDS.get(label)
    if command_class is not None:
        return _commanded(clock, player, command_class, (), None)
    if label == "Game":
        # The wheel's own name for the inner command (`FarmAutoqueue`, ...) is the engine's label.
        inner = cast(Mapping[str, object], payload["game_command"])
        label = next(iter(inner), label)
    return _undecoded(label, clock, player, payload)


def _decode_chat(body: _Payload) -> tuple[int, str] | None:
    """Parse a chat operation into `(sender, channel)`, discarding the message text.

    Returns None when the string is not the expected object. No exception raised here quotes the
    text: `json` errors are swallowed and nothing is logged.
    """
    try:
        fields = json.loads(cast(str, body["text"]))
    except ValueError:
        return None
    if not isinstance(fields, dict):
        return None
    sender, channel = fields.get("player"), fields.get("channel")
    for value in (sender, channel):
        if not isinstance(value, int) or isinstance(value, bool):
            return None
    return cast(int, sender), str(channel)


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


def canonical_events(
    parsed: Mapping[str, object], accounting: Accounting | None = None
) -> Iterator[CanonicalEvent]:
    """Yield the canonical events of one parsed replay, in stream order, in one pass.

    Pass an `Accounting` to have every deliberately dropped operation counted by reason.
    """
    tally = accounting if accounting is not None else Accounting()
    seated = _seated(parsed)
    state = _Exits()
    clock = 0
    operations = cast(Sequence[Mapping[str, object]], parsed["operations"])
    for operation in operations:
        kind = next(iter(operation))
        body = cast(_Payload, operation[kind])
        if kind == "Sync":
            clock += cast(int, body["time_increment"])
        elif kind == "Viewlock":
            continue
        elif kind == "PostGame":
            yield _match_ended(clock, body)
        elif kind == "Chat":
            decoded = _decode_chat(body)
            if decoded is None:
                # No sender can be read, so the chat names no seated participant.
                tally.unseated += 1
                continue
            sender, channel = decoded
            if sender not in seated:
                tally.unseated += 1
            elif state.has_exited(sender):
                tally.after_exit += 1
            else:
                yield CanonicalEvent(
                    clock_ms=clock,
                    kind=EventKind.CHAT,
                    participant=sender,
                    payload=ChatPayload(channel=channel),
                )
        elif kind == "Action":
            action_data = cast(Mapping[str, _Payload], body["action_data"])
            label, payload = next(iter(action_data.items()))
            player = cast(int, payload["player_id"])
            if player not in seated:
                tally.unseated += 1
                continue
            if state.has_exited(player):
                tally.after_exit += 1
                continue
            mapper = _ACTION_MAPPERS.get(label)
            event = (
                _unmapped_action(clock, player, label, payload)
                if mapper is None
                else mapper(clock, player, payload, state)
            )
            if event is None:
                tally.collapsed += 1
            else:
                yield event
        else:
            raise EngineParseError(f"operation kind {kind!r} is not one the adapter knows")
