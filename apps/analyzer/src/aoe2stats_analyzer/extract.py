"""Extraction orchestration through the `ReplayExtractor` Protocol (T365).

Calls `.extract()` on whatever `ReplayExtractor` its caller (`run.py`) hands it, and turns the
result into the published-JSON shape `contracts/analysis.md` documents — nothing else. **No engine
import**: only `packages/core`'s Protocol and value objects (`aoe2stats_core.replay.analysis`,
T352) and the standard library.

`apps/analyzer` is the only application that ever calls `.extract()` on
`packages/replay-engine`'s adapter, and always through this Protocol, never the concrete class
(T354/T355's `Aoe2RecExtractor`) — `run.py`'s own caller (`api/analyze.py`, T366) constructs the
concrete extractor once, outside this module, and this file never imports
`aoe2stats_replay_engine` to do it. `apps/api` also *declares* the `aoe2stats-replay-engine`
dependency (T302), because it needs it transitively for the ingester's own capture-time validator
— that is not the same as importing it here, and T302's own task text is explicit that the
declaration is deliberate and must stay.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Any

from aoe2stats_core.replay.analysis import MatchTimeline, ReplayExtractor

#: `contracts/analysis.md`'s own published-document schema version — bumped only when the shape
#: of the JSON this module writes changes, never when `MatchTimeline` itself gains a field: the
#: `dataclasses.asdict` conversion in `published_document` below carries every field through by
#: name, so this module has no field list of its own to fall behind.
SCHEMA_VERSION = 1

__all__ = ["SCHEMA_VERSION", "extract_timeline", "published_document"]


def extract_timeline(extractor: ReplayExtractor, zip_bytes: bytes) -> MatchTimeline:
    """Run one recording through `extractor`, and nothing else.

    No retry, no fallback, no second engine: `extractor.extract` raises `EngineParseError` or
    `MalformedArchiveError` (`aoe2stats_core.replay.validation`, re-exported by
    `aoe2stats_core.replay.analysis`) on a recording it cannot process, and a parse is
    deterministic — a second attempt costs a second, identical failure and another fetch (FR-036,
    constitution V). `run.py` is the one that decides what a raised `ReplayValidationError` means
    for the `match_analyses` row; this function only raises it unchanged.
    """
    return extractor.extract(zip_bytes)


def published_document(
    timeline: MatchTimeline,
    *,
    game_id: int,
    object_key: str,
    zip_sha256: str,
    extracted_at: datetime,
) -> dict[str, Any]:
    """The JSON written to `match_analyses.result_key` (`contracts/analysis.md`): `MatchTimeline`
    serialised, plus the provenance that makes FR-041/SC-009a mechanical — which retained
    recording, checksum and all, produced this document, and when.

    `dataclasses.asdict` is what carries every `MatchTimeline`/`ParticipantTimeline` field through
    unchanged and by name: this function keeps no field list of its own to fall out of sync with
    `packages/core`'s value objects (or, in a test double, with whatever stands in for them, as
    long as it is shaped like a dataclass the same way).
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "game_id": game_id,
        "point_of_view_profile_id": timeline.point_of_view_profile_id,
        "world_time_ms": timeline.world_time_ms,
        "engine": {
            "name": timeline.engine_name,
            "version": timeline.engine_version,
            "deps": {},
        },
        "source_recording": {"object_key": object_key, "sha256": zip_sha256},
        "extracted_at": extracted_at.isoformat(),
        "participants": [dataclasses.asdict(participant) for participant in timeline.participants],
    }
