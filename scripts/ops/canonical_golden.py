"""Deterministic serialisation of the canonical stream, and the one way to regenerate its goldens.

**Not shipped.** This used to live in `packages/replay-engine/src/aoe2stats_replay_engine/`, which
ships in the wheel deployed to Vercel and the VPS (constitution XII: portable by construction,
no local filesystem state). It computed a repository-relative `FIXTURES` path that exists in
neither deployment and `main()` wrote to it — dead code at best, a crash at worst, in production.
`scripts/ops/` is this repository's home for exactly this kind of dev-only tool (see
`sync_map_thumbnails.py`, `import_knowledge_pack.py`): never imported by application code, never
part of any built wheel, free to know where the repository root is.

The goldens live beside the recordings as `<recording>.canonical.json` (T629). Nothing here runs
implicitly: the golden test only *reads* them, and they are rewritten only by running

    uv run python scripts/ops/canonical_golden.py

which regenerates one file per committed recording. Regenerate only on an engine upgrade or a
deliberate logic change, never by hand, and read and explain every diff (see the fixtures README).

**Through the seam, not around it (constitution V, FR-015).** The stream comes from
`Aoe2RecExtractor(max_raw_bytes=...).events(zip_bytes)` — the public `CanonicalEventSource` entry
point `contracts/canonical-events.md` names — never from calling `canonical_events` directly with
bytes fished out by the adapter's own private `_read_member_bytes`/`_parse_or_raise`. Every
committed golden is therefore produced, and every golden test re-verified, through the same
well-formedness and `max_raw_bytes` refusals a real caller is bound by, not a bypass of them.
`_FIXTURE_MAX_RAW_BYTES` below is a tool-local constant sized the same way and for the same reason
`packages/replay-engine/tests/test_extract_limits.py`'s own fixture-local ceiling is: generous
relative to both committed recordings' extracted size, and never `ANALYSIS_MAX_RAW_BYTES` itself,
which is application configuration this tool has no business reading (constitution V, XII).

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
from aoe2stats_replay_engine.aoe2rec import Aoe2RecExtractor

FORMAT = 1
_REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = _REPO_ROOT / "tests/fixtures/replays"

# Generous relative to both committed recordings' extracted size (~6.9 MB and ~4.0 MB per
# `tests/fixtures/replays/README.md`) — the same rationale and the same value as
# `packages/replay-engine/tests/test_extract_limits.py`'s `_FIXTURE_MAX_RAW_BYTES`. A tool-local
# constant only, never `ANALYSIS_MAX_RAW_BYTES` itself, which this script has no business reading.
_FIXTURE_MAX_RAW_BYTES = 50_000_000


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
    extractor = Aoe2RecExtractor(max_raw_bytes=_FIXTURE_MAX_RAW_BYTES)
    return serialise(zip_path.stem, extractor.events(zip_path.read_bytes()))


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
