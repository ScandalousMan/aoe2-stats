"""T922: the Tier A decoder of the starting attributes (amendment contract, research R4).

Assumed API (T923, `aoe2stats_replay_engine.starting`):

    decode_starting_attributes(header: bytes, name: str) -> Mapping[str, float]

`header` is the inflated header, `name` a human player's name as the engine reports it. It returns
`{"food", "wood", "stone", "gold"}` and nothing else, and raises `EngineParseError` when the name's
anchor is absent, ambiguous, or its four values are not finite non-negative integers.

The expected values are read here, independently, with the anchor framing documented in
`tests/test_starting_state_anchor.py` (`u16 LE (len + 1)`, name, NUL, seven bytes, float32 array);
no number is copied. Every test is a strict expected failure until T923 lands.
"""

from __future__ import annotations

import io
import json
import struct
import zipfile
import zlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from aoe2rec_py import aoe2rec_py as _native
from scripts.ops.canonical_golden import golden_path, recordings

from aoe2stats_core.replay.validation import EngineParseError

_RECORDINGS = recordings()
_HUMAN_PLAYER_TYPE = 2
_NAME_END_TO_ARRAY = 7
_FIELDS = ("food", "wood", "stone", "gold")
_XFAIL = pytest.mark.xfail(strict=True, reason="T923 not implemented yet")


def _read(zip_path: Path) -> tuple[bytes, list[tuple[int, str]]]:
    with zipfile.ZipFile(io.BytesIO(zip_path.read_bytes())) as archive:
        (member,) = archive.namelist()
        raw = archive.read(member)
    (header_len,) = struct.unpack_from("<I", raw, 0)
    header = zlib.decompress(raw[8:header_len], -15)
    (chapter,) = _native.parse_rec(raw)["chapters"]
    players: list[dict[str, Any]] = chapter["zheader"]["game_settings"]["players"]
    humans = [
        (p["player_number"], p["name"]) for p in players if p["player_type"] == _HUMAN_PLAYER_TYPE
    ]
    return header, sorted(humans)


def _frame(name: str) -> bytes:
    encoded = name.encode("utf-8")
    return struct.pack("<H", len(encoded) + 1) + encoded + b"\x00"


def _expected(header: bytes, name: str) -> dict[str, float]:
    frame = _frame(name)
    assert header.count(frame) == 1
    offset = header.index(frame) + len(frame) - 1 + _NAME_END_TO_ARRAY
    return dict(zip(_FIELDS, struct.unpack_from("<4f", header, offset), strict=True))


def _golden_events(zip_path: Path) -> list[dict[str, Any]]:
    return json.loads(golden_path(zip_path).read_text())["events"]


def _starting(zip_path: Path) -> list[tuple[int, dict[str, Any]]]:
    return [
        (index, event)
        for index, event in enumerate(_golden_events(zip_path))
        if event["kind"] == "starting-attributes"
    ]


@_XFAIL
@pytest.mark.parametrize("zip_path", _RECORDINGS, ids=lambda p: p.stem)
def test_the_decoder_reads_the_four_stockpiles_of_every_human(zip_path: Path) -> None:
    from aoe2stats_replay_engine.starting import decode_starting_attributes

    header, humans = _read(zip_path)
    assert humans
    for _, name in humans:
        decoded: Mapping[str, float] = decode_starting_attributes(header, name)
        assert tuple(decoded) == _FIELDS
        assert dict(decoded) == _expected(header, name)


@_XFAIL
@pytest.mark.parametrize("zip_path", _RECORDINGS, ids=lambda p: p.stem)
def test_the_golden_holds_one_event_per_human_at_clock_zero_after_match_started(
    zip_path: Path,
) -> None:
    header, humans = _read(zip_path)
    events = _golden_events(zip_path)
    starting = _starting(zip_path)

    assert events[0]["kind"] == "match-started"
    assert [index for index, _ in starting] == list(range(1, 1 + len(humans)))
    assert [event["participant"] for _, event in starting] == [slot for slot, _ in humans]
    for (_, event), (_, name) in zip(starting, humans, strict=True):
        assert event["clock_ms"] == 0
        assert list(event["payload"]) == ["values"]
        assert list(event["payload"]["values"]) == list(_FIELDS)
        assert event["payload"]["values"] == _expected(header, name)


@_XFAIL
@pytest.mark.parametrize("zip_path", _RECORDINGS, ids=lambda p: p.stem)
def test_the_live_stream_emits_the_golden_starting_events(zip_path: Path) -> None:
    from scripts.ops.canonical_golden import live_serialisation

    live = [
        line
        for line in live_serialisation(zip_path).splitlines()
        if '"kind":"starting-attributes"' in line
    ]
    committed = [
        line
        for line in golden_path(zip_path).read_text().splitlines()
        if '"kind":"starting-attributes"' in line
    ]
    assert live
    assert live == committed


@_XFAIL
def test_a_corrupted_terminator_removes_the_anchor() -> None:
    from aoe2stats_replay_engine.starting import decode_starting_attributes

    header, humans = _read(_RECORDINGS[0])
    name = humans[0][1]
    nul_at = header.index(_frame(name)) + len(_frame(name)) - 1
    corrupted = header[:nul_at] + b"\x01" + header[nul_at + 1 :]
    with pytest.raises(EngineParseError):
        decode_starting_attributes(corrupted, name)


@_XFAIL
def test_a_second_framed_copy_makes_the_anchor_ambiguous() -> None:
    from aoe2stats_replay_engine.starting import decode_starting_attributes

    header, humans = _read(_RECORDINGS[0])
    name = humans[0][1]
    with pytest.raises(EngineParseError):
        decode_starting_attributes(header + _frame(name) + bytes(32), name)


@_XFAIL
def test_a_length_prefix_that_omits_the_terminator_is_not_an_anchor() -> None:
    from aoe2stats_replay_engine.starting import decode_starting_attributes

    header, humans = _read(_RECORDINGS[0])
    name = humans[0][1]
    prefix_at = header.index(_frame(name))
    wrong = struct.pack("<H", len(name.encode("utf-8")))
    corrupted = header[:prefix_at] + wrong + header[prefix_at + 2 :]
    with pytest.raises(EngineParseError):
        decode_starting_attributes(corrupted, name)


@_XFAIL
@pytest.mark.parametrize(
    "bad", [float("nan"), float("inf"), -1.0, 100.5], ids=["nan", "inf", "negative", "fractional"]
)
def test_a_value_that_is_not_a_non_negative_integer_is_refused(bad: float) -> None:
    from aoe2stats_replay_engine.starting import decode_starting_attributes

    header, humans = _read(_RECORDINGS[0])
    name = humans[0][1]
    anchor = header.index(_frame(name)) + len(_frame(name)) - 1 + _NAME_END_TO_ARRAY
    corrupted = header[:anchor] + struct.pack("<f", bad) + header[anchor + 4 :]
    with pytest.raises(EngineParseError):
        decode_starting_attributes(corrupted, name)
