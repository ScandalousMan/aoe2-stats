"""The golden-extraction test (T356, ADR-0001): the committed replay extracts to the committed
timeline, byte-for-byte.

This is the assertion ADR-0001 was written about: a game patch silently broke parsing for months
because nothing asserted the shape of the answer. Serializing `MatchTimeline` the same way T355
generated the fixture — `dataclasses.asdict`, then `json.dumps(..., indent=2, sort_keys=False)`,
plus the trailing newline the fixture was committed with — and comparing the resulting text
against the committed file's own bytes means a version bump that moves one age-up by 208 ms, or
any other change to the extracted shape, shows up as a diff instead of being silently absorbed.

A failure here is a real signal, not something to fix by regenerating the fixture: regenerating it
to make this test pass again is exactly the silent absorption ADR-0001 exists to prevent.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from aoe2stats_replay_engine.aoe2rec import _MAX_INNER_BYTES, Aoe2RecExtractor

_FIXTURES = Path(__file__).resolve().parents[3] / "tests/fixtures/replays"
REFERENCE_REPLAY = _FIXTURES / "AgeIIDE_Replay_500546441.zip"
GOLDEN_TIMELINE = _FIXTURES / "AgeIIDE_Replay_500546441.timeline.json"


@pytest.fixture
def extractor() -> Aoe2RecExtractor:
    # `_MAX_INNER_BYTES` (the shared zip-bomb guard's ceiling) is comfortably above the reference
    # replay's ~6.9 MB, and reused here rather than inventing a second arbitrary constant: this
    # test is not exercising `max_raw_bytes` itself, only `extract()`'s output shape.
    return Aoe2RecExtractor(max_raw_bytes=_MAX_INNER_BYTES)


def test_the_committed_replay_extracts_to_the_committed_timeline_byte_for_byte(
    extractor: Aoe2RecExtractor,
) -> None:
    zip_bytes = REFERENCE_REPLAY.read_bytes()

    timeline = extractor.extract(zip_bytes)

    # Same serialization T355 used to generate the fixture: `dataclasses.asdict`, then
    # `json.dumps(..., indent=2, sort_keys=False)` — dataclass field declaration order, not
    # alphabetical — plus the trailing newline the committed file itself carries.

    serialized = json.dumps(asdict(timeline), indent=2, sort_keys=False) + "\n"

    assert serialized == GOLDEN_TIMELINE.read_text()
