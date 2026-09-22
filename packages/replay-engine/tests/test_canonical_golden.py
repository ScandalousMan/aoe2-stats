"""The canonical stream of every committed recording equals its committed golden, byte for byte.

A failure here means the stream moved. Do not regenerate to make it pass: find out why it moved
(see `tests/fixtures/replays/README.md`). This test only reads the goldens; it never writes them.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import pytest
from scripts.ops.canonical_golden import (
    golden_path,
    live_serialisation,
    recordings,
)

_RECORDINGS = recordings()


def _first_difference(live: str, committed: str) -> str:
    live_lines, committed_lines = live.splitlines(), committed.splitlines()
    for number, (a, b) in enumerate(itertools.zip_longest(live_lines, committed_lines), start=1):
        if a != b:
            return f"line {number}:\n  live:      {a}\n  committed: {b}"
    return "no line differs (trailing newline)"


def test_every_committed_recording_has_a_golden() -> None:
    assert len(_RECORDINGS) >= 2
    for path in _RECORDINGS:
        assert golden_path(path).is_file(), f"{golden_path(path).name} is not committed"


@pytest.mark.parametrize("zip_path", _RECORDINGS, ids=lambda p: p.stem)
def test_the_live_stream_equals_the_committed_golden(zip_path: Path) -> None:
    live = live_serialisation(zip_path)
    committed = golden_path(zip_path).read_text()
    assert live == committed, (
        f"{golden_path(zip_path).name} differs from the live canonical stream, first at "
        f"{_first_difference(live, committed)}"
    )


@pytest.mark.parametrize("zip_path", _RECORDINGS, ids=lambda p: p.stem)
def test_the_golden_is_valid_json_and_carries_no_text_or_names(zip_path: Path) -> None:
    document = json.loads(golden_path(zip_path).read_text())
    events = document["events"]
    assert document["event_count"] == len(events)
    for event in events:
        assert list(event) == ["clock_ms", "kind", "participant", "payload"]
        assert event["participant"] is None or isinstance(event["participant"], int)
        if event["kind"] == "chat":
            assert list(event["payload"]) == ["channel"]
