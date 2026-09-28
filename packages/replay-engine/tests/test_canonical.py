"""The canonical event stream (T625): clock, collapse, exit discipline, participants.

The real-recording tests run over every committed recording. The exit rule is also tested on a
synthetic stream, because neither recording shows a player resigning while the match runs on at
length (research.md D11).
"""

from __future__ import annotations

import dataclasses
import json
import logging
import struct
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import cast

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
    ResearchQueuedPayload,
    UndecodedPayload,
    UnitQueuedPayload,
    UnitsCommandedPayload,
    UnitUnqueuedPayload,
)
from aoe2stats_replay_engine.aoe2rec import Aoe2RecExtractor, _parse_or_raise, _read_member_bytes
from aoe2stats_replay_engine.canonical import Accounting, canonical_events

_FIXTURES = Path(__file__).resolve().parents[3] / "tests/fixtures/replays"
_RECORDINGS = sorted(_FIXTURES.glob("AgeIIDE_Replay_*.zip"))

# Generous relative to both committed recordings' extracted size, the same value and rationale as
# `packages/replay-engine/tests/test_extract_limits.py`'s own fixture-local ceiling — never
# `ANALYSIS_MAX_RAW_BYTES` itself (constitution V, XII).
_FIXTURE_MAX_RAW_BYTES = 50_000_000

_Parsed = Mapping[str, object]

# Both committed recordings are on this build (tests/fixtures/replays/README.md).
_FIXTURE_BUILD = 180059


def _parse(path: Path) -> _Parsed:
    _, data = _read_member_bytes(path.read_bytes())
    return _parse_or_raise(data)


def _canonical_stream(path: Path) -> list[CanonicalEvent]:
    """T652e: the real-recording canonical stream, through `Aoe2RecExtractor.events()` — the
    public seam (`contracts/canonical-events.md`) — never `canonical_events(parsed)` called
    directly against the raw dict `_parse` produces. `parsed` (below) stays: several tests here
    compare the canonical stream against the *raw* operations, which have no seam of their own."""
    extractor = Aoe2RecExtractor(max_raw_bytes=_FIXTURE_MAX_RAW_BYTES)
    return list(extractor.events(path.read_bytes()))


@pytest.fixture(scope="module", params=_RECORDINGS, ids=lambda p: p.stem)
def recording_path(request: pytest.FixtureRequest) -> Path:
    return cast(Path, request.param)


@pytest.fixture(scope="module")
def parsed(recording_path: Path) -> _Parsed:
    return _parse(recording_path)


@pytest.fixture(scope="module")
def canonical_stream(recording_path: Path) -> list[CanonicalEvent]:
    return _canonical_stream(recording_path)


def _operations(parsed: _Parsed) -> Sequence[Mapping[str, object]]:
    return cast(Sequence[Mapping[str, object]], parsed["operations"])


def _drop_match_started(events: Iterator[CanonicalEvent]) -> list[CanonicalEvent]:
    """Every event but the header-derived `match-started` lead (T629a).

    Most tests below are about what one operation becomes, not about the event every stream now
    opens with; this keeps them from having to know that on top of what they actually test.
    """
    return [e for e in events if e.kind is not EventKind.MATCH_STARTED]


def test_the_committed_recordings_are_found() -> None:
    assert len(_RECORDINGS) >= 2


def test_the_first_event_of_every_stream_is_match_started(
    parsed: _Parsed, canonical_stream: list[CanonicalEvent]
) -> None:
    """T629a: `match-started` comes from the header and corresponds to no operation (it is
    excluded from the conservation equation by name, not by a widened tolerance — see
    `test_conservation_every_operation_is_an_event_or_a_counted_category`). Its participants equal
    the seated slots and its build is the one the fixtures README records. `canonical_stream` is
    driven through `Aoe2RecExtractor.events()` (T652e), not `canonical_events(parsed)` directly."""
    zheader = cast(Mapping[str, object], parsed["zheader"])
    game_settings = cast(Mapping[str, object], zheader["game_settings"])
    raw_players = cast(Sequence[Mapping[str, object]], game_settings["players"])
    seated = {
        (cast(int, player["player_number"]), cast(int, player["civ_id"])) for player in raw_players
    }

    first = next(iter(canonical_stream))

    assert first.kind is EventKind.MATCH_STARTED
    assert first.clock_ms == 0
    assert first.participant is None
    assert isinstance(first.payload, MatchStartedPayload)
    assert {(p.slot, p.civilisation) for p in first.payload.participants} == seated
    assert first.payload.build == _FIXTURE_BUILD


# --- the clock ----------------------------------------------------------------------------------


def test_the_accumulated_clock_equals_every_actions_own_time(parsed: _Parsed) -> None:
    clock = 0
    checked = 0
    for operation in _operations(parsed):
        if "Sync" in operation:
            clock += cast(Mapping[str, int], operation["Sync"])["time_increment"]
        elif "Action" in operation:
            own = cast(Mapping[str, int], operation["Action"])["world_time"]
            assert own == clock
            checked += 1
    assert checked > 0


def test_the_accumulated_clock_equals_the_post_game_match_time(
    canonical_stream: list[CanonicalEvent],
) -> None:
    ended = [e for e in canonical_stream if e.kind is EventKind.MATCH_ENDED]

    assert len(ended) == 1
    payload = ended[0].payload
    assert isinstance(payload, MatchEndedPayload)
    assert ended[0].clock_ms == payload.final_clock_ms
    assert ended[0].participant is None


def test_event_times_never_go_backwards(canonical_stream: list[CanonicalEvent]) -> None:
    times = [e.clock_ms for e in canonical_stream]
    assert times == sorted(times)


def test_events_are_produced_lazily() -> None:
    assert isinstance(canonical_events({"operations": [], **_settings(1)}), Iterator)


# --- mapping over the real recordings -----------------------------------------------------------


def test_placement_positions_fall_inside_the_map(
    parsed: _Parsed, canonical_stream: list[CanonicalEvent]
) -> None:
    info = cast(Mapping[str, Mapping[str, int]], parsed["zheader"])["map_info"]
    placed = [e.payload for e in canonical_stream if e.kind is EventKind.BUILDING_PLACED]
    assert placed
    for payload in placed:
        assert isinstance(payload, BuildingPlacedPayload)
        assert 0 <= payload.position.x <= info["size_x"]
        assert 0 <= payload.position.y <= info["size_y"]


def _count(parsed: _Parsed, label: str) -> int:
    return sum(1 for _, found, _ in _timed_actions(parsed) if found == label)


def test_placement_count_equals_build_action_count(
    parsed: _Parsed, canonical_stream: list[CanonicalEvent]
) -> None:
    placed = sum(1 for e in canonical_stream if e.kind is EventKind.BUILDING_PLACED)
    assert placed == _count(parsed, "Build")


def test_queueing_and_movement_are_never_collapsed(
    parsed: _Parsed, canonical_stream: list[CanonicalEvent]
) -> None:
    kinds = Counter(e.kind for e in canonical_stream)
    assert kinds[EventKind.UNIT_QUEUED] == _count(parsed, "DeQueue")
    commanded = Counter(
        cast(UnitsCommandedPayload, e.payload).command_class
        for e in canonical_stream
        if e.kind is EventKind.UNITS_COMMANDED
    )
    assert commanded["move"] == _count(parsed, "Move")
    assert commanded["interact"] == _count(parsed, "Interact")
    assert commanded["order"] == _count(parsed, "Order")


def test_research_is_collapsed_to_its_first_occurrence_per_participant(
    parsed: _Parsed, canonical_stream: list[CanonicalEvent]
) -> None:
    raw: dict[tuple[int, int], int] = {}
    for clock, label, payload in _timed_actions(parsed):
        if label == "Research":
            raw.setdefault(
                (cast(int, payload["player_id"]), cast(int, payload["technology_type"])), clock
            )
    research = [e for e in canonical_stream if e.kind is EventKind.RESEARCH_QUEUED]
    seen = {
        (cast(int, e.participant), cast(ResearchQueuedPayload, e.payload).technology_id): e.clock_ms
        for e in research
    }
    assert seen == raw
    assert len(research) == len(raw)


def test_no_participant_is_attributed_after_their_resignation(
    canonical_stream: list[CanonicalEvent],
) -> None:
    resigned_at: dict[int, int] = {}
    for index, event in enumerate(canonical_stream):
        if event.kind is EventKind.PARTICIPANT_RESIGNED:
            assert event.participant is not None
            assert event.participant not in resigned_at
            resigned_at[event.participant] = index
    later_by_resigned = [
        e
        for i, e in enumerate(canonical_stream)
        if e.participant in resigned_at and i > resigned_at[cast(int, e.participant)]
    ]
    assert resigned_at
    assert later_by_resigned == []


def test_only_match_level_events_carry_no_participant(
    canonical_stream: list[CanonicalEvent],
) -> None:
    for event in canonical_stream:
        if event.participant is None:
            assert event.kind in (EventKind.MATCH_ENDED, EventKind.MATCH_STARTED)


def test_every_participant_is_a_seated_slot(
    parsed: _Parsed, canonical_stream: list[CanonicalEvent]
) -> None:
    settings = cast(Mapping[str, Mapping[str, Mapping[str, object]]], parsed)["zheader"]
    players = cast(Sequence[Mapping[str, int]], settings["game_settings"]["players"])
    seated = {p["player_number"] for p in players}
    assert {e.participant for e in canonical_stream} - {None} <= seated


def test_view_lock_and_sync_operations_yield_no_event(parsed: _Parsed) -> None:
    stream = {
        "zheader": parsed["zheader"],
        "operations": [op for op in _operations(parsed) if "Sync" in op or "Viewlock" in op],
    }
    assert _drop_match_started(canonical_events(stream)) == []


# --- synthetic streams --------------------------------------------------------------------------


def _settings(*numbers: int) -> dict[str, object]:
    # `civ_id`, `build`, `resolved_map_id` and the lobby preset fields exist only so
    # `_match_started` (T629a) has something to read on a synthetic stream: no test below asserts
    # on their values, they only need to be present and well-typed.
    return {
        "zheader": {
            "build": _FIXTURE_BUILD,
            "game_settings": {
                "resolved_map_id": 9,
                "starting_resources_id": 0,
                "starting_age_id": 2,
                "map_size": 120,
                "players": [{"player_number": n, "civ_id": n} for n in numbers],
            },
        }
    }


def _sync(ms: int) -> dict[str, object]:
    return {"Sync": {"time_increment": ms, "next": 0, "checksum": None}}


def _act(label: str, player: int, **fields: object) -> dict[str, object]:
    return {
        "Action": {
            "length": 0,
            "world_time": 0,
            "action_data": {label: {"player_id": player, "action_length": 0, **fields}},
        }
    }


def _chat(player: int, text: str, channel: int = 0) -> dict[str, object]:
    body = json.dumps({"player": player, "channel": channel, "message": text, "tauntNumber": 0})
    return {"Chat": {"padding": (255, 255, 255, 255), "text": body}}


def _research(player: int, technology: int = 101) -> dict[str, object]:
    return _act("Research", player, building_id=7, technology_type=technology)


def _move(player: int) -> dict[str, object]:
    return _act("Move", player, x=1.0, y=2.0, unit_ids=[11])


def _stream(*operations: dict[str, object], players: tuple[int, ...] = (1, 2)) -> _Parsed:
    return {**_settings(*players), "operations": list(operations)}


def test_exit_rule_on_a_synthetic_stream_where_the_match_runs_on() -> None:
    stream = _stream(
        _sync(100),
        _move(1),
        _sync(100),
        _act("Resign", 1, data=[0]),
        _sync(5000),
        _move(1),  # after the exit: not attributed
        _research(1, 102),  # after the exit: not attributed
        _move(2),  # the other participant plays on
        _sync(5000),
        _act("Resign", 1, data=[0]),  # a second resignation is not a second exit
        _move(2),
    )

    events = _drop_match_started(canonical_events(stream))

    by_player = [(e.participant, e.kind, e.clock_ms) for e in events]
    assert by_player == [
        (1, EventKind.UNITS_COMMANDED, 100),
        (1, EventKind.PARTICIPANT_RESIGNED, 200),
        (2, EventKind.UNITS_COMMANDED, 5200),
        (2, EventKind.UNITS_COMMANDED, 10200),
    ]


def test_an_action_from_an_unseated_slot_yields_no_participant_and_no_event() -> None:
    stream = _stream(_sync(10), _move(3), _move(0), _move(1), players=(1, 2))

    events = _drop_match_started(canonical_events(stream))

    assert [e.participant for e in events] == [1]


def test_the_seated_list_alone_decides_who_can_be_a_participant() -> None:
    stream = _stream(_move(3), players=(3,))
    assert [e.participant for e in _drop_match_started(canonical_events(stream))] == [3]


def test_repeated_research_collapses_but_a_different_technology_does_not() -> None:
    stream = _stream(
        _sync(100),
        _research(1, 101),
        _sync(208),
        _research(1, 101),  # the double-click: same participant, same technology
        _research(2, 101),  # another participant is independent
        _research(1, 102),
        _research(1, 101),  # far later still collapses: no window
    )

    got = [
        (e.participant, cast(ResearchQueuedPayload, e.payload).technology_id, e.clock_ms)
        for e in canonical_events(stream)
        if e.kind is EventKind.RESEARCH_QUEUED
    ]

    assert got == [(1, 101, 100), (2, 101, 308), (1, 102, 308)]


def test_resignation_collapses_to_the_first_occurrence_only() -> None:
    stream = _stream(_act("Resign", 1, data=[0]), _act("Resign", 1, data=[0]))
    kinds = [e.kind for e in _drop_match_started(canonical_events(stream))]
    assert kinds == [EventKind.PARTICIPANT_RESIGNED]


def test_queueing_repeated_identically_is_never_collapsed() -> None:
    queue = _act("DeQueue", 1, building_type=109, unit_id=83, amount=1, building_ids=[500, 501])
    stream = _stream(_sync(1), queue, _sync(1), queue, queue)

    events = _drop_match_started(canonical_events(stream))

    assert len(events) == 3
    payload = events[0].payload
    assert payload == UnitQueuedPayload(unit_id=83, building_type=109, building_object=500, count=1)


def test_a_movement_command_with_no_decoded_units_keeps_an_empty_list() -> None:
    stream = _stream(_act("Move", 1, x=1.0, y=2.0, unit_ids=[]))
    (event,) = _drop_match_started(canonical_events(stream))
    assert isinstance(event.payload, UnitsCommandedPayload)
    assert event.payload.unit_objects == ()


def test_an_order_naming_no_building_has_no_target() -> None:
    stream = _stream(_act("Order", 1, building_id=-1, object_ids=[9]))
    (event,) = _drop_match_started(canonical_events(stream))
    assert isinstance(event.payload, UnitsCommandedPayload)
    assert event.payload.target is None


def test_placement_decodes_position_and_building_from_the_raw_bytes() -> None:
    data = list(
        struct.pack("<I", 1) + struct.pack("<ff", 12.0, 69.0) + struct.pack("<I", 70) + bytes(4)
    )
    stream = _stream(_act("Build", 1, data=data))
    (event,) = _drop_match_started(canonical_events(stream))
    assert event.kind is EventKind.BUILDING_PLACED
    assert event.payload == BuildingPlacedPayload(
        building_id=70, position=cast(BuildingPlacedPayload, event.payload).position
    )
    assert (event.payload.position.x, event.payload.position.y) == (12.0, 69.0)  # type: ignore[union-attr]


# --- no silent drop (T626, FR-019) -------------------------------------------------------------


def test_conservation_every_operation_is_an_event_or_a_counted_category(parsed: _Parsed) -> None:
    """events + syncs + viewlocks + collapsed + after_exit + unseated + unknown_operation ==
    operations.

    The two left-hand counts the wheel reports come from the raw operation list; the rest come from
    the generator's own `Accounting`, so a new way to lose an operation has to be named to pass.
    `match-started` (T629a) comes from the header and corresponds to no operation: it is
    subtracted from the event count by name, never folded in by widening the equation's tolerance.
    Both committed recordings carry no operation kind the adapter lacks a case for, so
    `unknown_operation` is 0 here and is exercised on a fabricated stream instead (T652d).

    Stays on `canonical_events(parsed, accounting)` directly (T652e): `Accounting` is not part of
    `CanonicalEventSource.events()` — the public seam hands back only the event stream, never the
    side-channel this equation is evidence about — so there is no seam call this test could make
    instead without losing the thing it asserts on.
    """
    accounting = Accounting()
    events = list(canonical_events(parsed, accounting))
    match_started = sum(1 for e in events if e.kind is EventKind.MATCH_STARTED)
    operations = _operations(parsed)
    syncs = sum(1 for op in operations if "Sync" in op)
    viewlocks = sum(1 for op in operations if "Viewlock" in op)

    assert match_started == 1
    assert accounting.unknown_operation == 0
    assert (
        len(events)
        - match_started
        + syncs
        + viewlocks
        + accounting.collapsed
        + accounting.after_exit
        + accounting.unseated
        + accounting.unknown_operation
        == len(operations)
    )


def test_every_recorded_action_is_an_event_or_a_named_drop(parsed: _Parsed) -> None:
    # Same exception as the conservation test above (T652e): `Accounting` has no seam equivalent.
    # Chat has its own accounting (below); leave it out so `unseated` counts actions only.
    without_chat = {**parsed, "operations": [op for op in _operations(parsed) if "Chat" not in op]}
    accounting = Accounting()
    events = list(canonical_events(without_chat, accounting))
    actions = sum(1 for op in _operations(parsed) if "Action" in op)
    action_events = sum(
        1 for e in events if e.kind not in (EventKind.MATCH_ENDED, EventKind.MATCH_STARTED)
    )
    assert action_events + accounting.collapsed + accounting.after_exit + accounting.unseated == (
        actions
    )


def test_a_collapsed_research_is_counted_as_collapsed() -> None:
    accounting = Accounting()
    stream = _stream(_research(1, 101), _research(1, 101), _research(1, 102))
    assert len(_drop_match_started(canonical_events(stream, accounting))) == 2
    assert accounting == Accounting(collapsed=1)


def test_an_unfamiliar_top_level_operation_kind_is_counted_not_aborted() -> None:
    """FR-019: a top-level operation kind the adapter has no case for is a named accounting
    category, never an abort. Neither committed recording carries one — a future wheel upgrade or
    engine patch would be the first — so a golden cannot cover this and the stream is fabricated
    (T652d, docs/risks.md R3: the whole match must not stop analysing for one unfamiliar kind).
    """
    from aoe2stats_replay_engine.canonical import Accounting, canonical_events

    stream = _stream({"FutureCommand": {"whatever": 1}})
    accounting = Accounting()

    events = _drop_match_started(canonical_events(stream, accounting))

    assert events == []
    assert accounting == Accounting(unknown_operation=1)


def test_the_action_kind_the_wheel_cannot_name_is_emitted_undecoded() -> None:
    recordings = [_parse(path) for path in _RECORDINGS]
    streams = [_canonical_stream(path) for path in _RECORDINGS]
    named = [
        [
            (label, payload)
            for _, label, payload in _timed_actions(parsed_)
            if label.startswith("Unknown")
        ]
        for parsed_ in recordings
    ]
    assert any(named), "no committed recording carries an action the wheel cannot name"
    for stream, instances in zip(streams, named, strict=True):
        undecoded = [
            e.payload
            for e in stream
            if isinstance(e.payload, UndecodedPayload) and e.payload.operation.startswith("Unknown")
        ]
        expected = Counter((label, cast(int, p["action_length"])) for label, p in instances)
        assert Counter((u.operation, u.payload_length) for u in undecoded) == expected


def test_undecoded_carries_the_engines_label_and_the_payload_length(
    parsed: _Parsed, canonical_stream: list[CanonicalEvent]
) -> None:
    labels = {
        label
        for _, label, _ in _timed_actions(parsed)
        if label in ("Flare", "TownBell", "Transform")
    }
    got = {e.payload.operation for e in canonical_stream if isinstance(e.payload, UndecodedPayload)}
    assert labels <= got


def test_command_kinds_without_decoded_ids_are_commanded_with_an_empty_list(
    parsed: _Parsed, canonical_stream: list[CanonicalEvent]
) -> None:
    empty = Counter(
        cast(UnitsCommandedPayload, e.payload).command_class
        for e in canonical_stream
        if e.kind is EventKind.UNITS_COMMANDED
        and cast(UnitsCommandedPayload, e.payload).command_class
        not in ("move", "interact", "order")
    )
    assert empty["formation"] == _count(parsed, "Formation")
    assert empty["stance"] == _count(parsed, "Stance")
    assert empty["stop"] == _count(parsed, "Stop")
    for e in canonical_stream:
        if e.kind is EventKind.UNITS_COMMANDED:
            payload = cast(UnitsCommandedPayload, e.payload)
            if payload.command_class not in ("move", "interact", "order"):
                assert payload.unit_objects == ()
                assert payload.target is None


def test_a_game_command_is_undecoded_under_the_wheels_inner_name() -> None:
    stream = _stream(_act("Game", 1, game_command={"FarmUnqueue": {}}, action_length=16))
    (event,) = _drop_match_started(canonical_events(stream))
    assert event.payload == UndecodedPayload(operation="FarmUnqueue", payload_length=16)


def test_an_unmapped_action_from_an_exited_or_unseated_slot_is_counted_not_emitted() -> None:
    accounting = Accounting()
    stream = _stream(
        _act("Resign", 1, data=[0]),
        _act("Stop", 1, data=[0]),
        _act("Stop", 9, data=[0]),
        _act("Resign", 1, data=[0]),
        _chat(1, "hello"),  # after player 1's exit
        _chat(9, "hello"),  # names no seated slot
        players=(1, 2),
    )
    events = _drop_match_started(canonical_events(stream, accounting))
    assert [e.kind for e in events] == [EventKind.PARTICIPANT_RESIGNED]
    # The second resignation is after the first exit, so it is an after-exit action, not a collapse.
    assert accounting == Accounting(after_exit=3, unseated=2)


def test_a_queue_command_naming_no_building_is_undecoded_not_dropped() -> None:
    stream = _stream(
        _act(
            "DeQueue", 1, building_type=109, unit_id=83, amount=1, building_ids=[], action_length=6
        )
    )
    (event,) = _drop_match_started(canonical_events(stream))
    assert event.payload == UndecodedPayload(operation="DeQueue", payload_length=6)


def _timed_actions(parsed: _Parsed) -> Iterator[tuple[int, str, Mapping[str, object]]]:
    clock = 0
    for operation in _operations(parsed):
        if "Sync" in operation:
            clock += cast(Mapping[str, int], operation["Sync"])["time_increment"]
        elif "Action" in operation:
            data = cast(Mapping[str, Mapping[str, Mapping[str, object]]], operation["Action"])[
                "action_data"
            ]
            label, payload = next(iter(data.items()))
            yield clock, label, payload


# --- the market and deletion decoders (T626a, FR-014) -------------------------------------------
#
# Layout, found by sweeping every byte position of every Sell, Buy and Delete in both committed
# recordings (see canonical.py for the evidence):
#   Sell/Buy  8 bytes  <h resource> <h amount in market steps> <I market object id>
#   Delete    4 bytes  <I object id>
# Direction is the wheel's own label; it is not read from the payload.

_RESOURCE_NAMES = {0: "food", 1: "wood", 2: "stone"}

# Expected market transactions per recording: (direction, resource, step count).
_GOLDEN_MARKET: Mapping[str, Mapping[tuple[str, str, int], int]] = {
    "AgeIIDE_Replay_500546441": {
        ("buy", "food", 1): 18,
        ("buy", "stone", 1): 15,
        ("buy", "wood", 1): 6,
        ("sell", "food", 1): 7,
        ("sell", "food", 5): 1,
        ("sell", "stone", 1): 17,
        ("sell", "stone", 5): 1,
        ("sell", "wood", 1): 42,
    },
    "AgeIIDE_Replay_504695319": {
        ("buy", "food", 1): 7,
        ("buy", "wood", 1): 2,
        ("sell", "food", 1): 18,
        ("sell", "wood", 1): 74,
        ("sell", "wood", 5): 14,
    },
}
# Deletion golden: (count, sum of the object ids) — the ids themselves are checked one by one
# against the raw bytes below; the sum pins the whole list so a shifted field cannot match.
_GOLDEN_DELETES: Mapping[str, tuple[int, int]] = {
    "AgeIIDE_Replay_500546441": (43, 273252),
    "AgeIIDE_Replay_504695319": (16, 348476),
}


@pytest.fixture(scope="module")
def named(recording_path: Path, parsed: _Parsed) -> tuple[str, _Parsed]:
    return recording_path.stem, parsed


@pytest.fixture(scope="module")
def named_stream(
    recording_path: Path, canonical_stream: list[CanonicalEvent]
) -> tuple[str, list[CanonicalEvent]]:
    return recording_path.stem, canonical_stream


def _raw(parsed: _Parsed, *labels: str) -> list[tuple[int, str, int, bytes]]:
    return [
        (clock, label, cast(int, payload["player_id"]), bytes(cast(Sequence[int], payload["data"])))
        for clock, label, payload in _timed_actions(parsed)
        if label in labels
    ]


def test_every_market_transaction_is_decoded_exactly_and_matches_the_golden_counts(
    named: tuple[str, _Parsed], named_stream: tuple[str, list[CanonicalEvent]]
) -> None:
    name, parsed_ = named
    _, stream = named_stream
    events = [e for e in stream if e.kind is EventKind.MARKET_TRANSACTION]
    raw = _raw(parsed_, "Sell", "Buy")

    assert len(events) == len(raw) > 0
    for event, (clock, label, player, data) in zip(events, raw, strict=True):
        resource, steps, market = struct.unpack("<hhI", data)
        assert market > 0
        assert event.clock_ms == clock
        assert event.participant == player
        assert event.payload == MarketTransactionPayload(
            direction=label.lower(), resource=_RESOURCE_NAMES[resource], steps=steps
        )
    counts = Counter(
        (p.direction, p.resource, p.steps)
        for p in (cast(MarketTransactionPayload, e.payload) for e in events)
    )
    assert counts == _GOLDEN_MARKET[name]


def test_the_market_layout_holds_over_every_instance(named: tuple[str, _Parsed]) -> None:
    """The empirical basis of the decoder: the bytes the decoder ignores are always zero and the
    values it reads stay inside the small closed sets observed."""
    _, parsed_ = named
    for _, _, _, data in _raw(parsed_, "Sell", "Buy"):
        assert len(data) == 8
        assert data[1] == 0 and data[3] == 0
        assert data[0] in _RESOURCE_NAMES  # gold is the counter-currency, never the named side
        assert data[2] in (1, 5)  # a click and a shift-click


def test_a_market_object_that_is_deleted_is_deleted_after_its_last_transaction(
    named: tuple[str, _Parsed],
) -> None:
    """Cross-check of the market object id: where the market building is later deleted, the
    delete names the same id and comes after every transaction on it."""
    _, parsed_ = named
    last: dict[int, int] = {}
    for clock, _, _, data in _raw(parsed_, "Sell", "Buy"):
        last[struct.unpack("<hhI", data)[2]] = clock
    deleted = {struct.unpack("<I", data)[0]: clock for clock, _, _, data in _raw(parsed_, "Delete")}
    hits = {market: deleted[market] for market in last if market in deleted}
    for market, when in hits.items():
        assert when > last[market]
    # Recording-level evidence: recordings that show the pairing show it every time it can occur.
    assert hits or named[0] == "AgeIIDE_Replay_504695319"


def test_every_deletion_is_decoded_exactly_and_matches_the_golden(
    named: tuple[str, _Parsed], named_stream: tuple[str, list[CanonicalEvent]]
) -> None:
    name, parsed_ = named
    _, stream = named_stream
    events = [e for e in stream if e.kind is EventKind.OBJECT_DELETED]
    raw = _raw(parsed_, "Delete")

    assert len(events) == len(raw)
    for event, (clock, _, player, data) in zip(events, raw, strict=True):
        assert event.clock_ms == clock
        assert event.participant == player
        assert event.payload == ObjectDeletedPayload(object_id=struct.unpack("<I", data)[0])
    ids = [cast(ObjectDeletedPayload, e.payload).object_id for e in events]
    assert (len(ids), sum(ids)) == _GOLDEN_DELETES[name]


def test_a_deleted_object_id_is_never_named_by_a_later_command(named: tuple[str, _Parsed]) -> None:
    """Cross-check of the delete field: an id that the same recording named before the delete is
    not named again after it. Ids that were never named elsewhere are not asserted on."""
    _, parsed_ = named
    mentions: dict[int, list[int]] = {}
    for clock, label, payload in _timed_actions(parsed_):
        if label == "Delete":
            continue
        ids: list[int] = []
        for key in ("unit_ids", "object_ids", "building_ids"):
            ids += cast(Sequence[int], payload.get(key, ()))
        for key in ("target_id", "building_id"):
            value = cast(int, payload.get(key, -1))
            if value >= 0:
                ids.append(value)
        for object_id in ids:
            mentions.setdefault(object_id, []).append(clock)

    verified = 0
    for clock, _, _, data in _raw(parsed_, "Delete"):
        seen = mentions.get(struct.unpack("<I", data)[0], [])
        if any(when < clock for when in seen):
            verified += 1
            assert not any(when > clock + 2000 for when in seen)
    assert verified > 0


def test_a_market_command_is_exact_on_a_synthetic_stream() -> None:
    sell = _act("Sell", 1, data=list(struct.pack("<hhI", 1, 5, 4321)), action_length=8)
    buy = _act("Buy", 2, data=list(struct.pack("<hhI", 2, 1, 4321)), action_length=8)
    first, second = _drop_match_started(canonical_events(_stream(sell, buy)))
    assert first.payload == MarketTransactionPayload("sell", "wood", 5)
    assert second.payload == MarketTransactionPayload("buy", "stone", 1)
    assert first.tier.value == "decoded"


@pytest.mark.parametrize(
    "data",
    [
        list(struct.pack("<hhI", 3, 1, 9)),  # a resource code outside the closed set
        list(struct.pack("<hhI", 0, 0, 9)),  # no step count
        list(struct.pack("<hhI", 0, -1, 9)),  # a negative step count
        list(struct.pack("<hh", 0, 1)),  # short
        list(struct.pack("<hhIB", 0, 1, 9, 0)),  # long
    ],
)
def test_a_market_payload_that_does_not_fit_the_layout_is_undecoded_never_guessed(
    data: list[int],
) -> None:
    (event,) = _drop_match_started(
        canonical_events(_stream(_act("Sell", 1, data=data, action_length=len(data))))
    )
    assert event.kind is EventKind.UNDECODED
    assert event.payload == UndecodedPayload(operation="Sell", payload_length=len(data))


def test_a_delete_payload_that_does_not_fit_the_layout_is_undecoded_never_guessed() -> None:
    (event,) = _drop_match_started(
        canonical_events(_stream(_act("Delete", 1, data=[1, 2, 3], action_length=3)))
    )
    assert event.kind is EventKind.UNDECODED
    assert event.payload == UndecodedPayload(operation="Delete", payload_length=3)


def test_decoding_market_and_deletion_does_not_change_the_event_count(
    parsed: _Parsed, canonical_stream: list[CanonicalEvent]
) -> None:
    """Undecoded became decoded one for one: no operation gained or lost an event."""
    kinds = Counter(e.kind for e in canonical_stream)
    assert kinds[EventKind.MARKET_TRANSACTION] == _count(parsed, "Sell") + _count(parsed, "Buy")
    assert kinds[EventKind.OBJECT_DELETED] == _count(parsed, "Delete")
    labels = {
        cast(UndecodedPayload, e.payload).operation
        for e in canonical_stream
        if e.kind is EventKind.UNDECODED
    }
    assert not labels & {"Sell", "Buy", "Delete"}


# --- chat (T626b): the channel and the participant are kept, the text never is -----------------

_SECRET = "Zx9-distinctive-message-text"


def _chat_texts(parsed: _Parsed) -> set[str]:
    texts: set[str] = set()
    for operation in _operations(parsed):
        if "Chat" in operation:
            raw = cast(Mapping[str, str], operation["Chat"])["text"]
            texts.add(cast(str, json.loads(raw)["message"]))
    return texts


def _strings(value: object) -> Iterator[str]:
    """Every string held anywhere in an event, by walking its fields rather than its repr."""
    if isinstance(value, str):
        yield value
    elif dataclasses.is_dataclass(value) and not isinstance(value, type):
        for field in dataclasses.fields(value):
            yield from _strings(getattr(value, field.name))
    elif isinstance(value, (tuple, list)):
        for item in value:
            yield from _strings(item)


def _leaks(event: CanonicalEvent, texts: set[str]) -> bool:
    """A held string equal to a message, or containing one long enough to be no coincidence.

    Short messages ("1") are searched for by equality only: as a substring of a repr they would
    match any digit.
    """
    held = list(_strings(event))
    return any(
        text and (text in held or (len(text) >= 8 and any(text in item for item in held)))
        for text in texts
    )


def test_a_seated_participants_chat_is_an_event_with_channel_and_no_text() -> None:
    accounting = Accounting()
    stream = _stream(_sync(300), _chat(2, _SECRET, channel=3), players=(1, 2))
    (event,) = _drop_match_started(canonical_events(stream, accounting))
    assert event.kind is EventKind.CHAT
    assert event.participant == 2
    assert event.clock_ms == 300  # chat has no time of its own: it takes the accumulated clock
    assert event.payload == ChatPayload(channel="3")
    assert accounting == Accounting()
    assert _SECRET not in repr(event)


def test_chat_from_an_unseated_sender_or_after_exit_is_counted_not_emitted() -> None:
    accounting = Accounting()
    stream = _stream(_chat(7, _SECRET), _act("Resign", 1, data=[0]), _chat(1, _SECRET))
    events = _drop_match_started(canonical_events(stream, accounting))
    assert [e.kind for e in events] == [EventKind.PARTICIPANT_RESIGNED]
    assert accounting == Accounting(unseated=1, after_exit=1)


@pytest.mark.parametrize(
    "text",
    [
        "not json " + _SECRET,
        '{"player": 1, "message": "' + _SECRET + '"}',  # no channel
        '{"player": "1", "channel": 0, "message": "' + _SECRET + '"}',  # sender not an integer
        '{"player": 1, "channel": true, "message": "' + _SECRET + '"}',
        '["' + _SECRET + '"]',
        '{"player": 1, "channel": 0, "message": "' + _SECRET,  # truncated
        "",
    ],
)
def test_malformed_chat_is_counted_unseated_and_never_raises_or_leaks(
    text: str, caplog: pytest.LogCaptureFixture
) -> None:
    accounting = Accounting()
    stream = _stream(_sync(50), {"Chat": {"padding": (0,), "text": text}})
    with caplog.at_level(logging.DEBUG):
        events = _drop_match_started(canonical_events(stream, accounting))
    assert events == []
    assert accounting == Accounting(unseated=1)
    assert _SECRET not in caplog.text
    assert caplog.records == []


def test_no_chat_text_reaches_any_event_or_log_line_of_either_recording(
    parsed: _Parsed, recording_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Driven through `Aoe2RecExtractor.events()` (T652e) rather than the shared `canonical_stream`
    fixture: production must happen *inside* `caplog.at_level` below for `caplog.records` to be
    meaningful evidence, and a module-scoped fixture shared with every other test in this file may
    already have produced (and logged) before this test ran."""
    texts = _chat_texts(parsed)
    assert texts, "the recording carries no chat to protect"
    extractor = Aoe2RecExtractor(max_raw_bytes=_FIXTURE_MAX_RAW_BYTES)
    with caplog.at_level(logging.DEBUG):
        events = list(extractor.events(recording_path.read_bytes()))
    assert not any(_leaks(event, texts) for event in events)
    assert caplog.records == []
    chats = [e for e in events if e.kind is EventKind.CHAT]
    assert chats
    assert all(cast(ChatPayload, e.payload).channel == "0" for e in chats)


def test_no_chat_text_reaches_an_event_or_a_log_line_on_a_planted_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    stream = _stream(_chat(1, _SECRET), _chat(1, _SECRET, channel=2), _chat(8, _SECRET))
    with caplog.at_level(logging.DEBUG):
        events = _drop_match_started(canonical_events(stream))
    assert len(events) == 2
    assert not any(_leaks(event, {_SECRET}) for event in events)
    assert _SECRET not in caplog.text
    assert caplog.records == []


def test_a_top_level_cancellation_is_a_unit_unqueued_event() -> None:
    stream = _stream(_act("Unqueue", 1, unit_id=83, amount=2))
    (event,) = _drop_match_started(canonical_events(stream))
    assert event.kind is EventKind.UNIT_UNQUEUED
    assert event.payload == UnitUnqueuedPayload(unit_id=83, count=2)


def test_a_cancellation_whose_payload_lacks_the_two_fields_is_undecoded_never_guessed() -> None:
    stream = _stream(_act("Unqueue", 1, action_length=9), _act("FarmUnqueue", 1, unit_id=83))
    events = _drop_match_started(canonical_events(stream))
    assert [e.kind for e in events] == [EventKind.UNDECODED, EventKind.UNDECODED]


def test_raw_actions_count_before_collapse_and_before_the_exit_rule() -> None:
    accounting = Accounting()
    stream = _stream(
        _research(1), _research(1), _move(1), _act("Resign", 1), _move(1), _move(2), _move(9)
    )
    list(canonical_events(stream, accounting))
    # Player 9 is unseated: not counted. Player 1's collapsed and post-exit commands are.
    assert accounting.raw_actions == {1: 5, 2: 1}
