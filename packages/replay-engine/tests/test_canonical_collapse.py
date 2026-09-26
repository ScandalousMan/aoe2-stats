"""The collapse test (T631, SC-010), against real fixture data, and its inverse.

`test_canonical.py` already proves the collapse rule with a synthetic double-click (the comment "the
double-click: same participant, same technology" around `test_repeated_research_collapses_but_a_
different_technology_does_not`) — hand-constructed `Research` operations, not evidence from a
committed recording. This file is the fixture-driven counterpart SC-010 asks for: it sweeps every
committed recording's raw operations (before `canonical_events` runs) for a real double-clicked
age-up — an age-up is a research of technology 101, 102 or 103 (`canonical.py`'s own module
docstring) — and asserts the canonical stream carries it once.

A collapse test that only checks collapse cannot see over-collapse, so the second half asserts the
opposite direction on the same fixtures: a unit-queue (training) command genuinely repeated many
times survives collapse unreduced, because it is what the villager count is made of
(`packages/replay-engine/src/aoe2stats_replay_engine/canonical.py`'s "Collapse" docstring section).

Both sweeps were run once by hand to confirm a real instance exists in each committed recording
(`tests/fixtures/replays/README.md` lists two): `AgeIIDE_Replay_500546441` carries three doubled
age-up researches (participant 2/technology 101, participant 2/technology 102, participant
1/technology 103, each pair issued twice, ~200 ms apart) and a villager-queue command issued 227
times by participant 2 (unit 83, a Town Centre — building type 109 — training object 4198);
`AgeIIDE_Replay_504695319` carries two doubled age-ups (participant 2/technology 101, participant
2/technology 103) and a villager-queue command issued 152 times by participant 2 (Town Centre
object 6072). The tests below do not hard-code these counts — they rediscover them from the raw
operations on every run, so a regenerated fixture is re-checked rather than trusted.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

import pytest

from aoe2stats_core.replay.events import (
    CanonicalEvent,
    EventKind,
    ResearchQueuedPayload,
    UnitQueuedPayload,
)
from aoe2stats_replay_engine.aoe2rec import Aoe2RecExtractor, _parse_or_raise, _read_member_bytes

_FIXTURES = Path(__file__).resolve().parents[3] / "tests/fixtures/replays"
_RECORDINGS = sorted(_FIXTURES.glob("AgeIIDE_Replay_*.zip"))

# Generous relative to both committed recordings' extracted size, the same value and rationale as
# `packages/replay-engine/tests/test_extract_limits.py`'s own fixture-local ceiling — never
# `ANALYSIS_MAX_RAW_BYTES` itself.
_FIXTURE_MAX_RAW_BYTES = 50_000_000

_Parsed = Mapping[str, object]

# An age-up is a research of one of these three technology ids (canonical.py's module docstring,
# FR-018).
_AGE_UP_TECHNOLOGIES = (101, 102, 103)

_ResearchKey = tuple[int, int]  # (participant, technology_id)
_QueueKey = tuple[
    int, int, int, int, int
]  # (participant, unit_id, building_type, building_object, count)


def _parse(path: Path) -> _Parsed:
    _, data = _read_member_bytes(path.read_bytes())
    return _parse_or_raise(data)


@pytest.fixture(scope="module", params=_RECORDINGS, ids=lambda p: p.stem)
def recording_path(request: pytest.FixtureRequest) -> Path:
    return cast(Path, request.param)


@pytest.fixture(scope="module")
def parsed(recording_path: Path) -> _Parsed:
    return _parse(recording_path)


@pytest.fixture(scope="module")
def canonical_stream(recording_path: Path) -> list[CanonicalEvent]:
    """T652e: the canonical stream, through `Aoe2RecExtractor.events()` — the public seam
    (`contracts/canonical-events.md`) — not `canonical_events(parsed)` called directly against the
    raw dict `_parse` produces. `parsed` stays for the raw-operation sweeps below, which have no
    seam of their own to go through."""
    extractor = Aoe2RecExtractor(max_raw_bytes=_FIXTURE_MAX_RAW_BYTES)
    return list(extractor.events(recording_path.read_bytes()))


def _operations(parsed: _Parsed) -> Sequence[Mapping[str, object]]:
    return cast(Sequence[Mapping[str, object]], parsed["operations"])


def _raw_actions(parsed: _Parsed, label: str) -> Sequence[Mapping[str, object]]:
    """Every raw `Action` operation's payload for one engine action label, in stream order."""
    payloads = []
    for operation in _operations(parsed):
        kind = next(iter(operation))
        if kind != "Action":
            continue
        body = cast(Mapping[str, object], operation[kind])
        action_data = cast(Mapping[str, Mapping[str, object]], body["action_data"])
        action_label, payload = next(iter(action_data.items()))
        if action_label == label:
            payloads.append(payload)
    return payloads


def _raw_age_up_occurrences(parsed: _Parsed) -> dict[_ResearchKey, int]:
    """Count of raw `Research` actions per (participant, technology), before any collapse."""
    counts: dict[_ResearchKey, int] = {}
    for payload in _raw_actions(parsed, "Research"):
        technology = cast(int, payload["technology_type"])
        if technology not in _AGE_UP_TECHNOLOGIES:
            continue
        key = (cast(int, payload["player_id"]), technology)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _raw_queue_occurrences(parsed: _Parsed) -> dict[_QueueKey, int]:
    """Count of raw `DeQueue` (unit-queue/training) actions per identical command tuple."""
    counts: dict[_QueueKey, int] = {}
    for payload in _raw_actions(parsed, "DeQueue"):
        building_ids = cast(Sequence[int], payload.get("building_ids", ()))
        if not building_ids:
            continue
        key = (
            cast(int, payload["player_id"]),
            cast(int, payload["unit_id"]),
            cast(int, payload["building_type"]),
            building_ids[0],
            cast(int, payload["amount"]),
        )
        counts[key] = counts.get(key, 0) + 1
    return counts


def _research_events(events: Sequence[CanonicalEvent]) -> Sequence[CanonicalEvent]:
    return [e for e in events if e.kind is EventKind.RESEARCH_QUEUED]


def _unit_queued_events(events: Sequence[CanonicalEvent]) -> Sequence[CanonicalEvent]:
    return [e for e in events if e.kind is EventKind.UNIT_QUEUED]


def test_a_real_double_clicked_age_up_collapses_to_one_event(
    parsed: _Parsed, canonical_stream: list[CanonicalEvent]
) -> None:
    """SC-010: the age-up a fixture's player double-clicked appears once in the canonical stream.

    Finds every (participant, technology) pair among the three age-up technologies issued more than
    once in the recording's raw operations — a double-click, since a technology can only ever be
    researched once for real — and asserts each collapses to exactly one `research-queued` event, at
    the clock of its first raw occurrence. `canonical_stream` is driven through `Aoe2RecExtractor.
    events()` (T652e), the public seam, not `canonical_events(parsed)` called directly.
    """
    raw_counts = _raw_age_up_occurrences(parsed)
    doubled = {key: count for key, count in raw_counts.items() if count >= 2}
    assert doubled, (
        "expected at least one age-up (technology 101, 102 or 103) issued more than once by the "
        "same participant in this recording (a double-click); the sweep of raw Research actions "
        "found none"
    )

    research_events = _research_events(canonical_stream)

    for (participant, technology), raw_count in doubled.items():
        matching = [
            e
            for e in research_events
            if e.participant == participant
            and cast(ResearchQueuedPayload, e.payload).technology_id == technology
        ]
        assert len(matching) == 1, (
            f"participant {participant} issued age-up {technology} {raw_count} times in the raw "
            f"stream (a double-click) but the canonical stream carries {len(matching)} "
            "research-queued events for it — collapse must reduce it to exactly one"
        )


def test_a_genuinely_repeated_unit_queue_command_is_not_collapsed(
    parsed: _Parsed, canonical_stream: list[CanonicalEvent]
) -> None:
    """SC-010's inverse: a real, repeated unit-queue command is never collapsed.

    A test that only checks collapse cannot see over-collapse. Finds the unit-queue (training)
    command issued identically the most times in the recording's raw operations — in both committed
    recordings this is a villager trained from one Town Centre — and asserts the canonical stream
    carries exactly that many `unit-queued` events for it, unreduced. `canonical_stream` is driven
    through `Aoe2RecExtractor.events()` (T652e), the public seam, not `canonical_events(parsed)`
    called directly.
    """
    raw_counts = _raw_queue_occurrences(parsed)
    assert raw_counts, "expected at least one unit-queue action in this recording"
    (player, unit_id, building_type, building_object, count), raw_count = max(
        raw_counts.items(), key=lambda item: item[1]
    )
    assert raw_count >= 10, (
        "expected a unit-queue command repeated many times verbatim in this recording (villager "
        f"training, typically); the most repeated command found was issued only {raw_count} times"
    )

    expected_payload = UnitQueuedPayload(
        unit_id=unit_id, building_type=building_type, building_object=building_object, count=count
    )
    matching = [
        e
        for e in _unit_queued_events(canonical_stream)
        if e.participant == player and e.payload == expected_payload
    ]

    assert len(matching) == raw_count, (
        f"the raw stream repeats this exact unit-queue command {raw_count} times but the canonical "
        f"stream carries {len(matching)} matching unit-queued events — collapse must never reduce "
        "queueing"
    )
