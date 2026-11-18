"""The Tier A decoder of the starting attributes (008 research R4, 006 research D1).

It reads the inflated header bytes and never the engine's output, so it is independent of the
parser by construction. Each human player's attribute array sits at a self-verifying anchor: the
player's name framed as a little-endian 16-bit length (name bytes plus one), the name, a NUL, then a
fixed gap to an array of 32-bit floats. The first four are read as the four stockpiles; no later
index is interpreted (research R4).

The anchor is self-verifying because the framing must match exactly once. An absent anchor, a second
framed copy, a truncated array, or a value that is not a finite non-negative whole number is refused
with `EngineParseError`, never guessed at and never defaulted. The caller (`canonical.py`) treats
that refusal as a gap for the one participant: the starting attributes are an optional datum, and
their absence never refuses the recording (FR-009, FR-026).
"""

from __future__ import annotations

import math
import struct
import zlib
from collections.abc import Mapping
from typing import Final

from aoe2stats_core.replay.validation import EngineParseError

#: The four stockpiles, in the engine's attribute order. Nothing else is read from the array.
FIELDS: Final[tuple[str, ...]] = ("food", "wood", "stone", "gold")

# Bytes from the name's terminating NUL to the first float of the array.
_NAME_END_TO_ARRAY = 7
_VALUES = struct.Struct(f"<{len(FIELDS)}f")
_LENGTH_PREFIX = struct.Struct("<H")
_HEADER_LENGTH = struct.Struct("<I")
# Where the header's raw-deflate stream starts in the recording.
_HEADER_STREAM_OFFSET = 8
# A guard against a hostile stream, not a size the header is expected to approach.
_MAX_INFLATED_HEADER = 256 * 1024 * 1024


def inflate_header(raw: bytes) -> bytes:
    """The decompressed header: the raw-deflate stream at `raw[8:header_len]`."""
    if len(raw) < _HEADER_STREAM_OFFSET:
        raise EngineParseError("the recording is too short to hold a header")
    (header_len,) = _HEADER_LENGTH.unpack_from(raw, 0)
    if not _HEADER_STREAM_OFFSET <= header_len <= len(raw):
        raise EngineParseError("the recording's header length lies outside the recording")
    inflater = zlib.decompressobj(-15)
    try:
        header = inflater.decompress(raw[_HEADER_STREAM_OFFSET:header_len], _MAX_INFLATED_HEADER)
    except zlib.error as exc:
        raise EngineParseError("the recording's header does not inflate") from exc
    if inflater.unconsumed_tail:
        raise EngineParseError("the recording's inflated header exceeds the decoder's ceiling")
    return header


def decode_starting_attributes(header: bytes, name: str) -> Mapping[str, int]:
    """The four starting stockpiles of the human named `name`, read from the inflated `header`."""
    encoded = name.encode("utf-8")
    frame = _LENGTH_PREFIX.pack(len(encoded) + 1) + encoded + b"\x00"
    first = header.find(frame)
    if first < 0:
        raise EngineParseError("a participant's starting-attribute anchor is absent")
    if header.find(frame, first + 1) >= 0:
        raise EngineParseError("a participant's starting-attribute anchor is ambiguous")
    offset = first + len(frame) - 1 + _NAME_END_TO_ARRAY
    if offset + _VALUES.size > len(header):
        raise EngineParseError("a participant's starting-attribute array is truncated")
    raw_values = _VALUES.unpack_from(header, offset)
    for value in raw_values:
        if not math.isfinite(value) or value < 0 or value != math.floor(value):
            raise EngineParseError(
                "a participant's starting attribute is not a finite non-negative whole number"
            )
    return dict(zip(FIELDS, (int(value) for value in raw_values), strict=True))
