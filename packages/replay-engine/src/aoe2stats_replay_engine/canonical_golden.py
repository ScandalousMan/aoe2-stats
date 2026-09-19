"""Deterministic serialisation of the canonical stream, and the one way to regenerate its goldens.

The goldens live beside the recordings as `<recording>.canonical.json` (T629). Nothing here runs
implicitly: the golden test only *reads* them, and they are rewritten only by running

    uv run python -m aoe2stats_replay_engine.canonical_golden

which regenerates one file per committed recording. Regenerate only on an engine upgrade or a
deliberate logic change, never by hand, and read and explain every diff (see the fixtures README).

Format: a JSON object `{"format": 1, "recording": ..., "event_count": ..., "events": [...]}` with
exactly one event per line, so a diff names the events that moved. Each event is
`{"clock_ms", "kind", "participant", "payload"}` in that order, the payload's keys in dataclass
declaration order, `kind` as the contract's kebab-case name. The tier is derived from the kind and
not written. The vocabulary carries no message text and participants are slot numbers, so neither
can reach the file.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path

from aoe2stats_core.replay.events import CanonicalEvent
from aoe2stats_replay_engine.aoe2rec import _parse_or_raise, _read_member_bytes
from aoe2stats_replay_engine.canonical import canonical_events

FORMAT = 1
FIXTURES = Path(__file__).resolve().parents[4] / "tests/fixtures/replays"


def _event_line(event: CanonicalEvent) -> str:
    record = {
        "clock_ms": event.clock_ms,
        "kind": event.kind.value,
        "participant": event.participant,
        "payload": None if event.payload is None else asdict(event.payload),
    }
    return json.dumps(record, separators=(",", ":"), sort_keys=False)


def serialise(recording: str, events: Iterable[CanonicalEvent]) -> str:
    lines = [_event_line(event) for event in events]
    head = json.dumps(
        {"format": FORMAT, "recording": recording, "event_count": len(lines)},
        separators=(",", ":"),
    )
    # `head` ends with "}"; the events array is opened inside the same object.
    body = ",\n".join(lines)
    return f'{head[:-1]},"events":[\n{body}\n]}}\n'


def live_serialisation(zip_path: Path) -> str:
    _, data = _read_member_bytes(zip_path.read_bytes())
    return serialise(zip_path.stem, canonical_events(_parse_or_raise(data)))


def golden_path(zip_path: Path) -> Path:
    return zip_path.with_suffix(".canonical.json")


def recordings() -> list[Path]:
    return sorted(FIXTURES.glob("AgeIIDE_Replay_*.zip"))


def main() -> None:
    for zip_path in recordings():
        target = golden_path(zip_path)
        target.write_text(live_serialisation(zip_path))
        print(f"wrote {target}")


if __name__ == "__main__":
    main()
