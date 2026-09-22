"""SC-009: the canonical vocabulary carries no field specific to the running engine (T630, FR-017).

The deny-list is **generated**, never hand-maintained: every dict key that appears anywhere in the
raw parsed structure of every committed recording, collected recursively. It has to be generated
from both recordings and not one — the two expose different action kinds (`test_canonical.py`'s own
`test_the_action_kind_the_wheel_cannot_name_is_emitted_undecoded`), so a deny-list built from either
alone is blind to the other's keys. A hand-maintained list tracks what someone remembered; this one
tracks what the wheel actually emits, so it changes when the wheel does.

This file is self-contained, in this repository's convention for the tests in this directory (see
`test_canonical.py` vs `test_canonical_golden.py`, `test_extract.py` vs `test_extract_limits.py`):
it duplicates the small fixture-parsing setup rather than importing it from a sibling test module.
"""

from __future__ import annotations

import dataclasses
import typing
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import cast

import pytest

from aoe2stats_core.replay.events import CanonicalEvent, Payload, UndecodedPayload
from aoe2stats_replay_engine.aoe2rec import Aoe2RecExtractor, _parse_or_raise, _read_member_bytes

# T652e: the deny-list generation (below) needs the raw parsed structure, which has no seam of its
# own — `_read_member_bytes`/`_parse_or_raise` are the adapter's own parse, reused here rather than
# duplicated. The emitted-payload sweep (`test_no_emitted_payload_carries_a_raw_byte_sequence`)
# does have a seam, and goes through it (`canonical_stream`, via `Aoe2RecExtractor(...).events()`)
# rather than around it with `canonical_events(parsed)` directly (contracts/canonical-events.md).
_FIXTURES = Path(__file__).resolve().parents[3] / "tests/fixtures/replays"
_RECORDINGS = sorted(_FIXTURES.glob("AgeIIDE_Replay_*.zip"))

# Generous relative to both committed recordings' extracted size, the same value and rationale as
# `packages/replay-engine/tests/test_extract_limits.py`'s own fixture-local ceiling — never
# `ANALYSIS_MAX_RAW_BYTES` itself.
_FIXTURE_MAX_RAW_BYTES = 50_000_000

_Parsed = Mapping[str, object]


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
    extractor = Aoe2RecExtractor(max_raw_bytes=_FIXTURE_MAX_RAW_BYTES)
    return list(extractor.events(recording_path.read_bytes()))


def _collect_keys(value: object, keys: set[str]) -> None:
    """Every dict key reachable from `value`, walked recursively through dicts, lists and tuples."""
    if isinstance(value, Mapping):
        for key, inner in value.items():
            keys.add(cast(str, key))
            _collect_keys(inner, keys)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _collect_keys(item, keys)


def _wheel_keys(path: Path) -> frozenset[str]:
    keys: set[str] = set()
    _collect_keys(_parse(path), keys)
    return frozenset(keys)


def _wheel_deny_list() -> frozenset[str]:
    """Every dict key the wheel's own output carries, over every committed recording."""
    assert len(_RECORDINGS) >= 2, "the deny-list needs both committed recordings"
    keys: set[str] = set()
    for path in _RECORDINGS:
        keys |= _wheel_keys(path)
    return frozenset(keys)


def _payload_field_names() -> Mapping[str, frozenset[str]]:
    """Every payload type's own field names, keyed by the type's own name.

    `typing.get_args(Payload)` walks the closed union in `events.py`, so a payload kind added there
    — including the two declared-only kinds, which have no producer yet — is covered without this
    test needing to be told about it.
    """
    return {
        payload_type.__name__: frozenset(f.name for f in dataclasses.fields(payload_type))
        for payload_type in typing.get_args(Payload)
    }


# The names the generated deny-list and the canonical vocabulary share, and why each is a plain
# domain concept both the wheel and this feature would name the same way — not a field whose name,
# shape or offset is specific to the wheel's own output (FR-017):
#
# - `build`: the game's own patch build number, read unchanged from the header into
#   `MatchStartedPayload.build` (T629a). Every reader of this file calls this field the same thing;
#   it is a fact about the game, not a wheel-internal label.
# - `unit_id`, `building_type`: `contracts/canonical-events.md` names both explicitly as domain
#   concepts carried beside the decoded building/unit objects — "a Town Center is 109" — kept
#   because the old timeline published them, not copied because the wheel happens to use the name.
# - `building_id`: `BuildingPlacedPayload.building_id` is the building *type* identifier this
#   repository decodes empirically from raw bytes (`_BUILD_ID_OFFSET`). The wheel's own
#   `building_id` fields (`Research`, `Order`) name a *different* thing, a producing/target
#   building's object id. The two share only the English words for the same real-world object, a
#   building, not a shape or an offset.
#
# `MarketTransactionPayload.steps` (T652d) does not appear here: the wheel's own queueing count is
# `amount`, which `UnitQueuedPayload`/`UnitUnqueuedPayload` already avoid by publishing `count`,
# and the wheel names nothing `steps`, so the rename introduces no collision to allow.
_ALLOWED_OVERLAP: frozenset[str] = frozenset({"build", "unit_id", "building_type", "building_id"})

# A field name that would betray a raw byte layout even without carrying a `bytes` value. Excludes
# `UndecodedPayload.payload_length`, which FR-019 requires and FR-017 explicitly carves out.
_OFFSET_OR_LENGTH_MARKERS = ("offset", "length")


def test_the_committed_recordings_are_found() -> None:
    assert len(_RECORDINGS) >= 2


def test_the_deny_list_generation_needs_both_recordings() -> None:
    """The two recordings expose different action kinds, so the deny-list built from one alone is
    smaller than the one built from both — proving the generation is doing real work and is not
    trivially satisfied by either recording alone."""
    per_recording = [_wheel_keys(path) for path in _RECORDINGS]
    union = frozenset().union(*per_recording)

    assert _wheel_deny_list() == union
    assert any(keys != union for keys in per_recording)


def test_no_canonical_payload_field_name_is_wheel_shaped() -> None:
    deny_list = _wheel_deny_list()
    for payload_name, field_names in _payload_field_names().items():
        leaked = (field_names & deny_list) - _ALLOWED_OVERLAP
        assert not leaked, f"{payload_name} carries a wheel-shaped field name: {sorted(leaked)}"


def test_the_allowed_overlap_names_only_names_that_actually_overlap() -> None:
    """The exception list is not stale and not over-broad: it names exactly the field names that
    are both in some payload type and in the generated deny-list."""
    deny_list = _wheel_deny_list()
    every_field_name: set[str] = set()
    for field_names in _payload_field_names().values():
        every_field_name |= field_names

    assert (every_field_name & deny_list) == _ALLOWED_OVERLAP


def test_no_payload_type_declares_a_byte_offset_or_length_field_other_than_undecodeds() -> None:
    for payload_type in typing.get_args(Payload):
        for f in dataclasses.fields(payload_type):
            if payload_type is UndecodedPayload and f.name == "payload_length":
                continue
            lowered = f.name.lower()
            assert not any(marker in lowered for marker in _OFFSET_OR_LENGTH_MARKERS), (
                f"{payload_type.__name__}.{f.name} looks like a byte offset or length"
            )


def test_no_payload_type_declares_a_raw_byte_sequence_field() -> None:
    for payload_type in typing.get_args(Payload):
        hints = typing.get_type_hints(payload_type)
        for f in dataclasses.fields(payload_type):
            hint = hints[f.name]
            assert hint not in (bytes, bytearray), (
                f"{payload_type.__name__}.{f.name} is a byte type"
            )


def _values(node: object) -> Iterator[object]:
    """Every leaf value reachable from `node`, walking dataclasses, tuples and lists."""
    if dataclasses.is_dataclass(node) and not isinstance(node, type):
        for f in dataclasses.fields(node):
            yield from _values(getattr(node, f.name))
    elif isinstance(node, (tuple, list)):
        for item in node:
            yield from _values(item)
    else:
        yield node


def test_no_emitted_payload_carries_a_raw_byte_sequence(
    canonical_stream: list[CanonicalEvent],
) -> None:
    """The structural check above is defence in depth; this walks what the adapter actually
    produces over a real recording, so a value smuggled past the type declaration is still
    caught. Driven through `Aoe2RecExtractor.events()` (T652e), not `canonical_events(parsed)`
    directly, so this is evidence about the seam callers actually use."""
    checked = 0
    for event in canonical_stream:
        for value in _values(event.payload):
            assert not isinstance(value, (bytes, bytearray))
            checked += 1
    assert checked > 0
