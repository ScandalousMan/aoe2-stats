"""Read the per-player state checkpoints an AoE2 DE recording carries every N syncs.

Research prototype for feature 009 (`specs/009-native-simulation-feasibility/`). It is not part of
the application: nothing under `apps/` or `packages/` imports it, it depends on the standard
library only, and constitution III's provider rule does not apply to it because it opens no
connection and ships in no deployment.

What it reads. A `.aoe2record` chapter is a header (`u32 header_end`, `u32 next_chapter`, then the
raw-deflate world save) followed by operations. Operation 2 is a sync: `u32 dt`. When the four bytes
after `dt` are zero they are a marker and the game has appended a state checkpoint: eight lanes of
eleven `u32` words, one lane per lobby slot (unused lanes are all zero), then the `u32` world time
in milliseconds. The game writes one every `checksum_interval` syncs (the first word of the pregame
operation; 500 on every recording seen).

Word semantics are published by `librematch/genie` (`crates/engine/genie-core/src/world/
checkpoint.rs`, AGPL-3.0-only; read as a specification, no code copied): word 0 sleeping objects,
word 1 the four resource stocks summed after truncation to integers, word 2 sum of master ids, word
3 sum of object states, word 4 sum of amounts held, word 5 always zero, word 6 live object count,
word 7 sum of positions times 100, word 8 player id, word 9 action terms, word 10 sum of object
ids. Of these, this project has corroborated word 8 (lane + 1 on every checkpoint) and word 1 (the
first checkpoint of seven of eight players equals the header's starting stocks minus the costs
queued before it); the others are carried as published and not verified (the tests say which).

Provenance of what it emits (009's vocabulary): every word is `ENGINE_STATE`, a value the game's
own simulation computed during the recorded match and stored in the recording, exact as an
integer. Any fact derived from a word (a creation, a death, a spend) is not emitted here and would
be `INFERRED` or `DETERMINISTIC_DERIVATION`, never `ENGINE_STATE`.

Two time bases are emitted per checkpoint: `world_time_ms`, the game's own stamp inside the block,
and `clock_ms`, the sum of the sync increments before the checkpoint's own sync (feature 008's
clock). They differ by the current sync's increment.

Usage:

    uv run python scripts/research/009-native-simulation/checkpoints.py [--series] \\
        tests/fixtures/replays/AgeIIDE_Replay_511523321.zip [more .zip or .aoe2record ...]

Prints one JSON array with one object per recording: counts, each player's first and last
checkpoint, and with `--series` every checkpoint. Zips are read in memory; the committed fixtures
are never modified or extracted beside themselves.
"""

from __future__ import annotations

import io
import json
import struct
import sys
import zipfile
import zlib
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

LANES = 8
WORDS = 11
CHECKPOINT_WORDS = LANES * WORDS + 1
OP_COMMAND, OP_SYNC, OP_VIEW, OP_CHAT, OP_PREGAME_OR_TRIGGER, OP_END = 1, 2, 3, 4, 5, 6
PROVENANCE = "ENGINE_STATE"


@dataclass(frozen=True)
class Checkpoint:
    """One lane of one checkpoint: the game's own state sample for one player."""

    recording: str
    lane: int
    world_time_ms: int
    clock_ms: int
    player_id: int
    sleeping: int
    resource_sum: int
    live_count: int
    words: tuple[int, ...]
    provenance: str = PROVENANCE


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
    """Walk the first chapter's operations: (kind, clock_ms before the operation, payload)."""
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
                yield ("checkpoint", clock, (words, dt))
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
    for kind, clock, payload in operations(data):
        if kind == "sync":
            syncs += 1
        elif kind == "command":
            commands += 1
        elif kind == "pregame":
            interval = payload[0]  # type: ignore[index]
        elif kind == "checkpoint":
            checkpoints += 1
            words: tuple[int, ...] = payload[0]  # type: ignore[index]
            world_time = words[LANES * WORDS]
            for lane in range(LANES):
                lane_words = tuple(words[lane * WORDS : (lane + 1) * WORDS])
                if not any(lane_words):
                    continue
                players.setdefault(lane_words[8], []).append(
                    Checkpoint(
                        recording=path.name,
                        lane=lane,
                        world_time_ms=world_time,
                        clock_ms=clock,
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
    header_end = _u32(data, 0)
    try:
        head = zlib.decompressobj(-15).decompress(data[8:header_end], 64)
    except zlib.error:
        return None
    marker = head.find(b"VER ")
    if marker < 0 or len(head) < marker + 8 + 4 + 8:
        return None
    return _u32(head, marker + 8 + 4 + 4)


def summary(reading: Reading, series: bool = False) -> dict[str, object]:
    """A JSON-friendly view: counts, each player's first and last checkpoint, and with `series`
    every checkpoint of every player."""
    players: dict[str, object] = {}
    for pid, checkpoints in sorted(reading.players.items()):
        entry: dict[str, object] = {
            "count": len(checkpoints),
            "first": asdict(checkpoints[0]),
            "last": asdict(checkpoints[-1]),
        }
        if series:
            entry["series"] = [asdict(c) for c in checkpoints]
        players[str(pid)] = entry
    return {
        "recording": reading.recording,
        "build": reading.build,
        "checksum_interval": reading.checksum_interval,
        "syncs": reading.syncs,
        "commands": reading.commands,
        "checkpoints": reading.checkpoints,
        "players": players,
    }


def main(argv: list[str]) -> int:
    series = "--series" in argv
    paths = [a for a in argv if a != "--series"]
    if not paths:
        print(__doc__, file=sys.stderr)
        return 2
    print(json.dumps([summary(read(Path(p)), series=series) for p in paths], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
