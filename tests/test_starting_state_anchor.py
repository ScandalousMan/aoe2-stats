"""The starting-state anchor in the committed reference recordings (T668).

Evidence for `docs/data-sources.md` §2, "Settled: each human player's starting resources sit at a
self-verifying anchor in the decompressed header". Parameterised over every `*.zip` under
`tests/fixtures/replays/`, never over named files, so a further recording is covered the moment it
is committed.

What is measured here, and only this:

- The header is the raw-deflate stream at `raw[8:header_len]`, where `header_len` is the first
  little-endian u32 of the recording.
- Each human player's name, as the pinned engine reports it, occurs in the inflated header framed
  as `u16 LE (byte length + 1)`, the UTF-8 name, then one NUL byte. That framing is the anchor's
  self-verification: the bytes at the anchor are the name the engine reported, not a pattern that
  merely looks right. The framed form occurs exactly once per human player.
- Seven bytes after the end of the name begins an array of little-endian float32 values. Its first
  four are the player's food, wood, stone and gold at the start, each a finite, non-negative
  integer.

What is NOT claimed: what any later field is, what the six bytes between the NUL and the array
are, why two players in the committed set start with different values, or anything about the
object table. The tests below only read the four resources.
"""

from __future__ import annotations

import io
import math
import struct
import zipfile
import zlib
from pathlib import Path
from typing import Any

import pytest
from aoe2rec_py import aoe2rec_py as _native
from tests.test_reference_recordings import ARCHIVES, FIXTURES, README, _recorded_checksum

# `player_type` as the pinned engine reports it. It is the only value present in the committed
# recordings; what the other values mean is not evidenced here, so other slots are not examined.
HUMAN_PLAYER_TYPE = 2

# Bytes between the end of the name string and the first float: the NUL terminator, then six
# bytes that are identical in every player of every committed recording and are not interpreted.
BYTES_NAME_END_TO_RESOURCES = 7
RESOURCE_COUNT = 4  # food, wood, stone, gold, in the engine's own order

Resources = tuple[float, float, float, float]


def inflate_header(raw: bytes) -> bytes:
    """The decompressed header: raw deflate of `raw[8:header_len]`."""
    (header_len,) = struct.unpack_from("<I", raw, 0)
    return zlib.decompress(raw[8:header_len], -15)


def framed_name(name: str) -> bytes:
    """The anchor's self-verifying frame: `u16 LE (len + 1)`, UTF-8 name, NUL."""
    encoded = name.encode("utf-8")
    return struct.pack("<H", len(encoded) + 1) + encoded + b"\x00"


def find_anchors(header: bytes, name: str) -> list[int]:
    """Offsets of the first resource float of every framed occurrence of `name` in `header`."""
    frame = framed_name(name)
    offsets: list[int] = []
    start = 0
    while (hit := header.find(frame, start)) >= 0:
        name_end = hit + len(frame) - 1  # the NUL is the byte after the name
        offsets.append(name_end + BYTES_NAME_END_TO_RESOURCES)
        start = hit + 1
    return offsets


def read_resources(header: bytes, offset: int) -> Resources:
    food, wood, stone, gold = struct.unpack_from(f"<{RESOURCE_COUNT}f", header, offset)
    return food, wood, stone, gold


def is_integral_non_negative(values: tuple[float, ...]) -> bool:
    return all(math.isfinite(v) and v >= 0 and v == int(v) for v in values)


def _read_recording(archive: Path) -> bytes:
    with zipfile.ZipFile(io.BytesIO(archive.read_bytes())) as zf:
        (member,) = zf.namelist()
        return zf.read(member)


def _human_names(raw: bytes) -> list[str]:
    (chapter,) = _native.parse_rec(raw)["chapters"]
    players: list[dict[str, Any]] = chapter["zheader"]["game_settings"]["players"]
    return [p["name"] for p in players if p["player_type"] == HUMAN_PLAYER_TYPE]


@pytest.fixture(scope="module")
def recordings() -> dict[str, tuple[bytes, list[str]]]:
    """Each archive is inflated and parsed once per session: its header and its human names."""
    out: dict[str, tuple[bytes, list[str]]] = {}
    for archive in ARCHIVES:
        raw = _read_recording(archive)
        out[archive.name] = (inflate_header(raw), _human_names(raw))
    return out


def test_the_fixture_directory_still_holds_the_known_recordings() -> None:
    assert len(ARCHIVES) >= 2, f"expected at least two reference recordings under {FIXTURES}"


@pytest.mark.parametrize("archive", ARCHIVES, ids=lambda path: path.name)
def test_the_archive_has_a_recorded_checksum(archive: Path) -> None:
    # The checksum itself is asserted by test_reference_recordings.py; here an archive that the
    # README does not describe fails rather than being measured without provenance.
    assert _recorded_checksum(archive.name) is not None, (
        f"{archive.name} has no recorded SHA-256 in {README.name}"
    )


@pytest.mark.parametrize("archive", ARCHIVES, ids=lambda path: path.name)
def test_every_human_player_has_exactly_one_anchor(
    archive: Path, recordings: dict[str, tuple[bytes, list[str]]]
) -> None:
    header, names = recordings[archive.name]

    assert names, f"{archive.name}: the engine reports no human player; nothing was measured"
    for name in names:
        anchors = find_anchors(header, name)
        assert len(anchors) == 1, f"{archive.name}: {name!r} has {len(anchors)} anchors, want 1"
        # The anchor is the deepest occurrence of the name, not one of the shallower ones.
        assert anchors[0] > header.rfind(name.encode("utf-8")), (
            f"{archive.name}: {name!r} anchor is not at the deepest occurrence of the name"
        )


@pytest.mark.parametrize("archive", ARCHIVES, ids=lambda path: path.name)
def test_the_anchor_count_equals_the_human_player_count(
    archive: Path, recordings: dict[str, tuple[bytes, list[str]]]
) -> None:
    header, names = recordings[archive.name]

    total = sum(len(find_anchors(header, name)) for name in names)

    assert total == len(names) == len(set(names)), f"{archive.name}: {total} anchors, {names}"


@pytest.mark.parametrize("archive", ARCHIVES, ids=lambda path: path.name)
def test_the_first_four_floats_are_finite_non_negative_integers(
    archive: Path, recordings: dict[str, tuple[bytes, list[str]]]
) -> None:
    header, names = recordings[archive.name]

    for name in names:
        (anchor,) = find_anchors(header, name)
        resources = read_resources(header, anchor)
        assert is_integral_non_negative(resources), f"{archive.name}: {name!r}: {resources}"


def test_a_non_ascii_name_is_among_the_anchored_players(
    recordings: dict[str, tuple[bytes, list[str]]],
) -> None:
    # Guards the UTF-8 framing: the length prefix counts bytes, not characters.
    non_ascii = [n for _, names in recordings.values() for n in names if not n.isascii()]

    assert non_ascii, (
        "no committed recording has a non-ASCII player name; UTF-8 framing is unmeasured"
    )


# --- The test can fail: planted absences on scratch copies of the bytes -------------------------


@pytest.fixture(scope="module")
def sample(recordings: dict[str, tuple[bytes, list[str]]]) -> tuple[bytes, str]:
    header, names = recordings[ARCHIVES[0].name]
    return header, names[0]


def test_corrupting_the_terminator_removes_the_anchor(sample: tuple[bytes, str]) -> None:
    header, name = sample
    (anchor,) = find_anchors(header, name)
    nul_at = anchor - BYTES_NAME_END_TO_RESOURCES
    assert header[nul_at] == 0
    corrupted = header[:nul_at] + b"\x01" + header[nul_at + 1 :]

    assert find_anchors(corrupted, name) == []


def test_a_second_framed_copy_makes_the_anchor_ambiguous(sample: tuple[bytes, str]) -> None:
    header, name = sample

    assert len(find_anchors(header + framed_name(name) + bytes(32), name)) == 2


def test_a_length_prefix_that_does_not_count_the_terminator_is_not_an_anchor(
    sample: tuple[bytes, str],
) -> None:
    header, name = sample
    (anchor,) = find_anchors(header, name)
    prefix_at = anchor - BYTES_NAME_END_TO_RESOURCES - len(name.encode("utf-8")) - 2
    wrong = struct.pack("<H", len(name.encode("utf-8")))
    corrupted = header[:prefix_at] + wrong + header[prefix_at + 2 :]

    assert find_anchors(corrupted, name) == []


@pytest.mark.parametrize(
    "bad",
    [float("nan"), float("inf"), -1.0, 100.5],
    ids=["nan", "inf", "negative", "fractional"],
)
def test_a_resource_that_is_not_a_non_negative_integer_is_rejected(
    sample: tuple[bytes, str], bad: float
) -> None:
    header, name = sample
    (anchor,) = find_anchors(header, name)
    corrupted = header[:anchor] + struct.pack("<f", bad) + header[anchor + 4 :]

    assert not is_integral_non_negative(read_resources(corrupted, anchor))
    assert is_integral_non_negative(read_resources(header, anchor))
