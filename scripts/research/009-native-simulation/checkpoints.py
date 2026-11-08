"""Read the per-player state checkpoints an AoE2 DE recording carries every N syncs.

Research prototype for feature 009 (`specs/009-native-simulation-feasibility/`). It is not part of
the application: nothing under `apps/` or `packages/` imports it, and it depends on the standard
library only.

What it reads. A `.aoe2record` chapter is a header (`u32 header_end`, `u32 next_chapter`, then the
raw-deflate world save) followed by operations. Operation 2 is a sync: `u32 dt`. When the four bytes
after `dt` are zero they are a marker and the game has appended a state checkpoint: eight lanes of
eleven `u32` words, one lane per lobby slot (unused lanes are all zero), then the `u32` world time
in milliseconds. The game writes one every `checksum_interval` syncs (500 on every recording seen;
the interval is the second word of the pregame operation).

Word semantics, as published by `librematch/genie` (`crates/engine/genie-core/src/world/
checkpoint.rs`, GPL-3.0; read as a specification, no code copied): word 0 sleeping objects, word 1
the four resource stocks summed after truncation to integers, word 2 sum of master ids, word 3 sum
of object states, word 4 sum of amounts held, word 5 always zero, word 6 live object count, word 7
sum of positions times 100, word 8 player id, word 9 action terms, word 10 sum of object ids. This
prototype exposes words 0, 1, 6 and 8 and keeps the raw lane for the rest.

Provenance of what it emits: the checkpoint is written by the game's own simulation during the
recorded match, so each word is an engine-state sample stored in the recording (`ENGINE_STATE` in
009's vocabulary), exact as an integer, coarse in time (one per 500 syncs) and in shape (sums and
counts, never per-object values). Nothing here is inferred.

Usage:

    uv run python scripts/research/009-native-simulation/checkpoints.py \
        tests/fixtures/replays/AgeIIDE_Replay_511523321.zip [more .zip or .aoe2record ...]

Prints one JSON document per recording on stdout. Zips are read in memory; the committed fixtures
are never modified or extracted beside themselves.
"""

from __future__ import annotations

import io
import json
import struct
import sys
import zipfile
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

LANES = 8
WORDS = 11
CHECKPOINT_WORDS = LANES * WORDS + 1
OP_COMMAND, OP_SYNC, OP_VIEW, OP_CHAT, OP_PREGAME_OR_TRIGGER, OP_END = 1, 2, 3, 4, 5, 6


@dataclass(frozen=True)
class Checkpoint:
    """One lane of one checkpoint: the game's own state sample for one player."""

    world_time_ms: int
    player_id: int
    sleeping: int
    resource_sum: int
    live_count: int
    words: tuple[int, ...]


@dataclass(frozen=True)
class Reading:
    """What one recording yielded."""

    recording: str
    build: int | None
    checksum_interval: int | None
    syncs: int
    commands: int
    checkpoints: int
    players: dict[int, list[Checkpoint]]


class UnknownOperation(ValueError):
    """The body holds an operation code this reader does not know; the walk stops there."""


def recording_bytes(path: Path) -> bytes:
    """The raw recording, from a `.aoe2record` or from the single member of a `.zip`."""
    data = path.read_bytes()
    if path.suffix.lower() != ".zip":
        return data
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members = archive.namelist()
        if len(members) != 1:
            raise ValueError(f"{path}: expected exactly one member, found {len(members)}")
        return archive.read(members[0])


def _u32(data: bytes, pos: int) -> int:
    return int(struct.unpack_from("<I", data, pos)[0])


def operations(data: bytes) -> Iterator[tuple[str, int, object]]:
    """Walk the first chapter's operations: (kind, world_time_ms, payload)."""
    header_end, next_chapter = struct.unpack_from("<II", data, 0)
    end = len(data) if next_chapter == 0 else next_chapter
    pos = header_end
    clock = 0
    first = True
    while pos + 4 <= end:
        op = _u32(data, pos)
        pos += 4
        if op == OP_COMMAND:
            length = _u32(data, pos)
            pos += 4 + length + 4  # packet, then its world time
            yield ("command", clock, None)
        elif op == OP_SYNC:
            dt = _u32(data, pos)
            pos += 4
            if data[pos : pos + 4] == b"\0\0\0\0":
                pos += 4
                words = struct.unpack_from(f"<{CHECKPOINT_WORDS}I", data, pos)
                pos += CHECKPOINT_WORDS * 4
                yield ("checkpoint", clock, words)
            clock += dt
            yield ("sync", clock, dt)
        elif op == OP_VIEW:
            pos += 12
        elif op == OP_CHAT:
            length = _u32(data, pos + 4)
            pos += 8 + length
        elif op == OP_PREGAME_OR_TRIGGER:
            if first:
                yield ("pregame", clock, struct.unpack_from("<7I", data, pos))
                pos += 28
            else:
                pos += 8
        elif op == OP_END:
            return
        else:
            raise UnknownOperation(f"operation {op} at byte {pos - 4}")
        first = False


def read(path: Path) -> Reading:
    """Every checkpoint of the recording at `path`, grouped by player id."""
    data = recording_bytes(path)
    build = _build(data)
    interval: int | None = None
    syncs = commands = checkpoints = 0
    players: dict[int, list[Checkpoint]] = {}
    for kind, _clock, payload in operations(data):
        if kind == "sync":
            syncs += 1
        elif kind == "command":
            commands += 1
        elif kind == "pregame":
            interval = payload[0]  # type: ignore[index]
        elif kind == "checkpoint":
            checkpoints += 1
            words: tuple[int, ...] = payload  # type: ignore[assignment]
            world_time = words[LANES * WORDS]
            for lane in range(LANES):
                lane_words = words[lane * WORDS : (lane + 1) * WORDS]
                if not any(lane_words):
                    continue
                players.setdefault(lane_words[8], []).append(
                    Checkpoint(
                        world_time_ms=world_time,
                        player_id=lane_words[8],
                        sleeping=lane_words[0],
                        resource_sum=lane_words[1],
                        live_count=lane_words[6],
                        words=lane_words,
                    )
                )
    return Reading(
        recording=path.name,
        build=build,
        checksum_interval=interval,
        syncs=syncs,
        commands=commands,
        checkpoints=checkpoints,
        players=players,
    )


def _build(data: bytes) -> int | None:
    """The game build from the inflated start of the header, where every build 180059 and 185872
    recording puts it: the `VER 9.4\\0` string, the legacy f32 version (-1.0), one u32 of
    minor/major version, then the build as u32 (measured 2026-11-08 on the three fixtures)."""
    import zlib

    header_end = _u32(data, 0)
    try:
        head = zlib.decompressobj(-15).decompress(data[8:header_end], 64)
    except zlib.error:
        return None
    marker = head.find(b"VER ")
    if marker < 0 or len(head) < marker + 8 + 4 + 8:
        return None
    return int(_u32(head, marker + 8 + 4 + 4))


def summary(reading: Reading) -> dict[str, object]:
    """A compact JSON-friendly view: counts, and each player's first and last checkpoint."""
    return {
        "recording": reading.recording,
        "build": reading.build,
        "checksum_interval": reading.checksum_interval,
        "syncs": reading.syncs,
        "commands": reading.commands,
        "checkpoints": reading.checkpoints,
        "players": {
            str(pid): {
                "count": len(series),
                "first": _public(series[0]),
                "last": _public(series[-1]),
            }
            for pid, series in sorted(reading.players.items())
        },
    }


def _public(checkpoint: Checkpoint) -> dict[str, int]:
    fields = asdict(checkpoint)
    fields.pop("words")
    return fields


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    for arg in argv:
        print(json.dumps(summary(read(Path(arg))), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
