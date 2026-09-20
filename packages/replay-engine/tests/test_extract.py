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

The bottom of the file covers `events()` (T629b): the protocol binding
(`aoe2stats_core.replay.events.CanonicalEventSource`) that is the seam
`contracts/canonical-events.md` names, checked with the protocol's own `runtime_checkable`
`isinstance`, so a drifted signature fails here rather than surfacing as an `AttributeError`
somewhere above the adapter. `events()` shares `extract()`'s well-formedness and input-size
refusals — the same `_well_formed_member`/`max_raw_bytes` checks, the same parse — and then folds
the parsed replay into the canonical stream instead of a `MatchTimeline`, so its output is checked
against the same committed canonical golden `test_canonical_golden.py` already proves the stream
against, not a third, separately-maintained fixture.
"""

from __future__ import annotations

import inspect
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from aoe2stats_core.replay.events import CanonicalEvent, CanonicalEventSource
from aoe2stats_core.replay.validation import MalformedArchiveError
from aoe2stats_replay_engine.aoe2rec import _MAX_INNER_BYTES, ENGINE_NAME, Aoe2RecExtractor
from aoe2stats_replay_engine.canonical_golden import golden_path, serialise
from aoe2stats_replay_engine.dependencies import read_engine_dependencies

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


@pytest.mark.parametrize("dropped", ["building-placed", "unit-queued", "research-queued"])
def test_the_golden_comparison_fails_if_the_fold_loses_one_event(
    extractor: Aoe2RecExtractor, monkeypatch: pytest.MonkeyPatch, dropped: str
) -> None:
    """The golden proves nothing unless it can fail: drop one event and the output must differ."""
    from aoe2stats_replay_engine import aoe2rec
    from aoe2stats_replay_engine.canonical import canonical_events

    def lossy(parsed, accounting=None):  # type: ignore[no-untyped-def]
        skipped = False
        for event in canonical_events(parsed, accounting):
            if not skipped and event.kind.value == dropped:
                skipped = True
                continue
            yield event

    monkeypatch.setattr(aoe2rec, "canonical_events", lossy)

    timeline = extractor.extract(REFERENCE_REPLAY.read_bytes())

    serialized = json.dumps(asdict(timeline), indent=2, sort_keys=False) + "\n"
    assert serialized != GOLDEN_TIMELINE.read_text()


# --- `events()`, the protocol binding (T629b) ------------------------------------------------


def test_the_extractor_satisfies_the_canonical_event_source_protocol(
    extractor: Aoe2RecExtractor,
) -> None:
    assert isinstance(extractor, CanonicalEventSource)


def test_engine_dependencies_is_t627s_record_not_a_fourth_copy(
    extractor: Aoe2RecExtractor,
) -> None:
    expected = read_engine_dependencies(ENGINE_NAME).as_mapping()
    assert extractor.engine_dependencies == expected
    assert extractor.engine_dependencies  # non-empty, FR-044


def test_events_yields_the_same_stream_as_the_committed_canonical_golden(
    extractor: Aoe2RecExtractor,
) -> None:
    live = serialise(REFERENCE_REPLAY.stem, extractor.events(REFERENCE_REPLAY.read_bytes()))
    assert live == golden_path(REFERENCE_REPLAY).read_text()


def test_events_refuses_a_malformed_archive_the_same_way_extract_does(
    extractor: Aoe2RecExtractor,
) -> None:
    with pytest.raises(MalformedArchiveError, match="not a zip archive"):
        extractor.events(b"not a zip")


def test_events_refuses_an_oversized_recording_the_same_way_extract_does() -> None:
    tiny = Aoe2RecExtractor(max_raw_bytes=1)

    with pytest.raises(MalformedArchiveError, match="exceeds this analysis's 1-byte ceiling"):
        tiny.events(REFERENCE_REPLAY.read_bytes())


def test_events_return_annotation_never_names_the_operation_stream() -> None:
    # `events()` folds the wheel's operations into `CanonicalEvent`s and never hands the operation
    # list back — checked on the declared return type, as `test_extract_never_returns_the_
    # operation_stream` already checks `extract()`'s.
    return_annotation = inspect.signature(Aoe2RecExtractor.events).return_annotation
    assert return_annotation in (
        "Iterator[CanonicalEvent]",
        f"Iterator[{CanonicalEvent.__name__}]",
    )
