"""The canonical stream of every committed recording equals its committed golden, byte for byte.

A failure here means the stream moved. Do not regenerate to make it pass: find out why it moved
(see `tests/fixtures/replays/README.md`). This test only reads the goldens; it never writes them.
"""

from __future__ import annotations

import hashlib
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
# sha256 of each recording's `unit-queued` golden lines as committed before T906 widened that
# payload; data recorded once, never recomputed from the current goldens.
_UNIT_QUEUED_DIGESTS = json.loads(
    (Path(__file__).parent / "unit_queued_digests.json").read_text(encoding="utf-8")
)["recordings"]


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


@pytest.mark.parametrize("zip_path", _RECORDINGS, ids=lambda p: p.stem)
def test_unit_queued_events_equal_the_previous_stream_without_building_objects(
    zip_path: Path,
) -> None:
    """The comparison with the stream before T906 stays true after later tasks add other events."""
    lines = []
    for line in live_serialisation(zip_path).splitlines():
        if '"kind":"unit-queued"' not in line:
            continue
        record = json.loads(line.rstrip(","))
        del record["payload"]["building_objects"]
        lines.append(json.dumps(record, separators=(",", ":"), sort_keys=False))
    expected = _UNIT_QUEUED_DIGESTS[zip_path.stem]
    assert hashlib.sha256("\n".join(lines).encode()).hexdigest() == expected["sha256"]


def _other_events_digest(serialisation: str) -> str:
    lines = []
    for line in serialisation.splitlines()[1:-1]:
        if '"kind":"unit-queued"' in line:
            continue
        record = json.loads(line.rstrip(","))
        if record["kind"] == "match-started":
            record["payload"]["lobby_presets"].pop("population_limit", None)
        lines.append(json.dumps(record, separators=(",", ":"), sort_keys=False))
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


@pytest.mark.parametrize("zip_path", _RECORDINGS, ids=lambda p: p.stem)
def test_every_other_event_equals_the_stream_before_t906(zip_path: Path) -> None:
    """T906 touched unit-queued lines only; every other line is pinned against c1f85aa7.

    Only `population_limit` (T908) is stripped from the match-started line.
    """
    committed = golden_path(zip_path).read_text()
    expected = _UNIT_QUEUED_DIGESTS[zip_path.stem]["other_events_sha256"]
    assert _other_events_digest(committed) == expected
