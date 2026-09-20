"""The analysis memory ceiling (T357, R3): `ANALYSIS_MAX_RAW_BYTES`, enforced on `extract()` only.

R3 measured ~631 MB resident for a 6.9 MB 1v1 replay against a 2 GB ceiling, because
`aoe2rec_py.parse_rec` materialises every operation as a Python object — memory scales with
operation count, and operation count scales with players and duration. An eight-player game carries
roughly three times the operations of the reference 1v1, which puts it close enough to the ceiling
that refusing an over-budget recording before it reaches the engine is a path that will run first in
production, not a theoretical guard.

This is deliberately **not** the same check as `_MAX_INNER_BYTES` (200 MB): that constant is a
zip-bomb guard shared with `Aoe2RecValidator.validate`, sized against a real replay's ~8:1
compression ratio, and it is ~9x too permissive to bound memory (R3's break-even is ~22 MB raw).
`max_raw_bytes` is a required, keyword-only constructor argument on `Aoe2RecExtractor` — never a
module constant here — because the number's home is `ANALYSIS_MAX_RAW_BYTES` in `.env.example`,
read by the eventual analyzer caller's settings (T365) and passed in; this package stays
config-agnostic and importable without app settings (constitution V).

Test payloads below use `os.urandom`, not a repeated byte, deliberately: a repeated byte compresses
at ratios well past the shared `_MAX_DECOMPRESSION_RATIO` zip-bomb cap (`_well_formed_member`'s own
check, measured here at ~91x for 1,000 repeated bytes), which would trip that check first and mask
the raw-size ceiling this file exists to pin. Incompressible content keeps the ratio near 1x, so the
only thing standing between these payloads and the engine is `max_raw_bytes`.

**T632** extends this file two ways. First, the refusal coverage above is `extract()`-only;
`events()` (T629b) shares `_parsed_or_refuse` with `extract()`, but it returns a generator
(`canonical_events` yields), which raises a real hazard: if the ceiling check happened *inside* the
generator body rather than in `events()`'s own function body, the refusal would not surface until
the first `next()` rather than on the call itself. The two `test_events_*_eagerly` tests below prove
which behavior this code actually has, by calling `extractor.events(zip_bytes)` directly and never
`next()`-ing the result — see each test's own docstring for what was found. Second, every refusal
test above proves only that an oversized input is rejected; it says nothing about what an *accepted*
input consumes once it reaches the engine and folds into canonical events. The tests in the "T632:
peak allocation" section below measure that with `tracemalloc`, over both committed recordings
driven fully through `events()`, and record the ceiling they assert against with its derivation
written out there — and assert FR-020's declared-only kinds are never emitted, alongside it.
"""

from __future__ import annotations

import inspect
import io
import os
import tracemalloc
import zipfile
from dataclasses import dataclass, fields
from pathlib import Path

import pytest
from aoe2rec_py import aoe2rec_py as _native

from aoe2stats_core.replay.analysis import MatchTimeline, ParticipantTimeline
from aoe2stats_core.replay.events import CanonicalEvent, EventKind
from aoe2stats_core.replay.validation import EngineParseError, MalformedArchiveError
from aoe2stats_replay_engine.aoe2rec import Aoe2RecExtractor

# `aoe2rec.py` itself binds this same module object as `_native` (`from aoe2rec_py import
# aoe2rec_py as _native`) — Python caches module imports, so monkeypatching an attribute on the
# `_native` imported here mutates the one `aoe2rec_py.aoe2rec_py` object both modules see, exactly
# as `tests/test_aoe2rec.py` already relies on for its own engine-crash tests. Importing it
# directly here, rather than reaching into `aoe2rec_module._native`, keeps this test file off a
# private attribute of another module.


def _zip_bytes(members: dict[str, bytes], compression: int = zipfile.ZIP_DEFLATED) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=compression) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def test_a_recording_over_the_configured_ceiling_is_refused_before_it_is_parsed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Well-formed on every axis `_well_formed_member` checks — one member, the expected inner
    # filename, comfortably under `_MAX_INNER_BYTES` and the decompression-ratio cap (incompressible
    # content, ~1x) — but its declared, uncompressed size (1,000 bytes) exceeds a deliberately tiny
    # `max_raw_bytes` (100), which is the only thing this test exercises.
    zip_bytes = _zip_bytes({"AgeIIDE_Replay_1.aoe2record": os.urandom(1_000)})
    extractor = Aoe2RecExtractor(max_raw_bytes=100)

    # The native engine must never be reached: if it were, this payload is not a real replay and
    # would raise a `pyo3_runtime.PanicException` (a bare `BaseException`) rather than the
    # `MalformedArchiveError` this test asserts. Patching it to fail hard on any call turns "the
    # parser was invoked" into an assertion failure rather than a fact this test would otherwise
    # have to infer indirectly from which exception type came back.
    def _must_not_be_called(data: bytes) -> object:
        raise AssertionError("the native engine must not be invoked past the raw-size ceiling")

    monkeypatch.setattr(_native, "parse_rec", _must_not_be_called)

    with pytest.raises(MalformedArchiveError, match="exceeds this analysis's 100-byte ceiling"):
        extractor.extract(zip_bytes)


def test_the_ceiling_is_the_declared_member_size_not_the_shared_zip_bomb_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A recording well under `_MAX_INNER_BYTES` (200 MB) and under the decompression-ratio cap can
    # still exceed a much tighter, analysis-specific `max_raw_bytes` — the two checks are
    # independent, and this one is not a restatement of the other with a smaller number.
    zip_bytes = _zip_bytes({"AgeIIDE_Replay_1.aoe2record": os.urandom(10_000)})
    extractor = Aoe2RecExtractor(max_raw_bytes=1_000)

    monkeypatch.setattr(
        _native,
        "parse_rec",
        lambda data: (_ for _ in ()).throw(AssertionError("must not reach the engine")),
    )

    with pytest.raises(MalformedArchiveError, match="10000 bytes exceeds"):
        extractor.extract(zip_bytes)


def test_a_recording_at_or_under_the_ceiling_reaches_the_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The inverse of the two refusals above: a payload at or under `max_raw_bytes` is not rejected
    # by this gate and does reach the native engine. The engine itself is stubbed to raise a plain
    # `Exception` with a distinguishing message, which `_parse_or_raise` wraps as
    # `EngineParseError` — the wrapped message surfacing here is the proof the stub, and therefore
    # the engine call site, was actually reached.
    zip_bytes = _zip_bytes({"AgeIIDE_Replay_1.aoe2record": os.urandom(1_000)})
    extractor = Aoe2RecExtractor(max_raw_bytes=1_000)

    def _stub_parse_rec(data: bytes) -> object:
        raise ValueError("stub reached: the raw-size gate let this payload through")

    monkeypatch.setattr(_native, "parse_rec", _stub_parse_rec)

    with pytest.raises(EngineParseError, match="stub reached"):
        extractor.extract(zip_bytes)


def test_events_over_the_configured_ceiling_is_refused_eagerly_not_lazily(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`events()` (T629b) shares `_parsed_or_refuse` with `extract()` — same ceiling, same
    exception. The hazard this test rules out: `events()` returns a generator (`canonical_events`
    yields), so *if* the ceiling check ran inside that generator's body rather than in
    `events()`'s own function body, calling `extractor.events(zip_bytes)` would not raise at
    all — it would hand back a suspended generator, and `MalformedArchiveError` would only
    surface on the first `next()`.

    Found: refusal is eager. Reading `Aoe2RecExtractor.events` in `aoe2rec.py` shows it is not
    itself a generator function (no `yield` in its own body) — it calls `self._parsed_or_refuse(
    zip_bytes)` synchronously, which raises before `events()` ever reaches its `return
    canonical_events(parsed)` line and constructs the generator. So the call below, which never
    calls `next()` on anything, is itself the proof: if `events()` returned a generator object
    instead of raising here, this test would fail with "DID NOT RAISE" and the hazard above would be
    real.
    """
    zip_bytes = _zip_bytes({"AgeIIDE_Replay_1.aoe2record": os.urandom(1_000)})
    extractor = Aoe2RecExtractor(max_raw_bytes=100)

    def _must_not_be_called(data: bytes) -> object:
        raise AssertionError("the native engine must not be invoked past the raw-size ceiling")

    monkeypatch.setattr(_native, "parse_rec", _must_not_be_called)

    with pytest.raises(MalformedArchiveError, match="exceeds this analysis's 100-byte ceiling"):
        extractor.events(zip_bytes)  # deliberately not `next(extractor.events(zip_bytes))`


def test_events_at_or_under_the_ceiling_reaches_the_engine_eagerly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The inverse of the refusal above, through `events()`: a payload at or under `max_raw_bytes`
    reaches the native engine, and reaches it eagerly. The stubbed engine's `ValueError`, wrapped as
    `EngineParseError` by `_parse_or_raise`, surfaces from the call to `events()` itself — again
    never `next()` — because `_parsed_or_refuse` (which calls the engine) runs entirely inside
    `events()`'s own function body, ahead of the `canonical_events(parsed)` call that constructs the
    generator it returns.
    """
    zip_bytes = _zip_bytes({"AgeIIDE_Replay_1.aoe2record": os.urandom(1_000)})
    extractor = Aoe2RecExtractor(max_raw_bytes=1_000)

    def _stub_parse_rec(data: bytes) -> object:
        raise ValueError("stub reached: the raw-size gate let this payload through")

    monkeypatch.setattr(_native, "parse_rec", _stub_parse_rec)

    with pytest.raises(EngineParseError, match="stub reached"):
        extractor.events(zip_bytes)  # deliberately not `next(extractor.events(zip_bytes))`


def test_extract_never_returns_the_operation_stream() -> None:
    # Field introspection on the return type, not on any one instance: neither `MatchTimeline` nor
    # `ParticipantTimeline` may carry a field that is the raw operation list, or anything named for
    # one — the Protocol's "reduces as it goes and never hands back the raw operation stream"
    # (contracts/analysis.md) is a property of the type `extract()` is declared to return, checked
    # here on the extractor's own return annotation and field set rather than only in
    # `packages/core`'s tests (T351), because this is the concrete adapter callers actually receive.
    return_annotation = inspect.signature(Aoe2RecExtractor.extract).return_annotation
    assert return_annotation is MatchTimeline or return_annotation == "MatchTimeline"

    match_timeline_fields = {f.name for f in fields(MatchTimeline)}
    participant_fields = {f.name for f in fields(ParticipantTimeline)}

    forbidden_substrings = ("operation", "raw_stream", "op_stream")
    for field_name in match_timeline_fields | participant_fields:
        lowered = field_name.lower()
        assert not any(bad in lowered for bad in forbidden_substrings), (
            f"{field_name!r} looks like it carries the raw operation stream"
        )

    # And every field on each type is one of the specific, narrow names the contract lists — not
    # merely absent of a forbidden substring, but exhaustively accounted for, so a field carrying
    # the operation stream under an unrelated name cannot slip in unnoticed either.
    allowed_participant_fields = {
        "profile_id",
        "player_number",
        "civ_id",
        "resolved_team_id",
        "builds",
        "trainings",
        "researches",
        "age_up_commands",
        "villagers_ordered",
        "actions",
        "actions_per_minute",
        "resigned_at_ms",
    }
    assert participant_fields == allowed_participant_fields

    allowed_match_fields = {
        "engine_name",
        "engine_version",
        "point_of_view_profile_id",
        "world_time_ms",
        "participants",
    }
    assert match_timeline_fields == allowed_match_fields


# --- T632: peak allocation over the full canonical path, and FR-020's declared-only kinds -------
#
# What this does and does not cover. `tracemalloc` traces Python-level allocations only.
# `aoe2rec_py` is a native (Rust/PyO3) extension; whatever *it* allocates internally while building
# the structure it hands back is invisible to `tracemalloc` unless and until it is materialised as
# Python objects — which, per this file's own module docstring and R3, is exactly what `parse_rec`
# does (every operation becomes a Python dict). So the number below is a good proxy for the
# Python-object cost this feature's own code is responsible for — the parsed operation structure,
# and the canonical events folded from it — but it is not total process RSS, and it does not
# capture any native-only working memory the wheel allocates and frees before returning.
#
# Derivation of the ceiling. Measured directly over both committed recordings, driving
# `Aoe2RecExtractor(max_raw_bytes=...).events()` to full consumption inside a `tracemalloc.start()`/
# `get_traced_memory()` region (three repeated runs each, stable to well under 1%):
#   - AgeIIDE_Replay_500546441.zip (484,542 raw operations, `tests/fixtures/replays/README.md`):
#     peak ~282 MB (295,482,129 to 295,786,301 bytes across runs)
#   - AgeIIDE_Replay_504695319.zip (232,503 raw operations): peak ~152 MB (159,841,749 to
#     159,845,213 bytes across runs)
# Peak allocation tracks raw operation count (R3: "memory scales with operation count"), not the
# object-id space the T632 task text names as "several times" larger in the second recording — a
# different axis (distinct object ids referenced across the match), irrelevant to this measurement.
# The higher of the two measured peaks, ~282 MB, is the basis for the ceiling below.
#
# Headroom: ~3.2x over the measured ~282 MB, landing on 900 MB. This mirrors this repository's own
# precedent for exactly this kind of number — `ANALYSIS_MAX_RAW_BYTES`'s 2 GB ceiling sits ~3.17x
# over R3's own measured 631 MB resident — rather than inventing a new ratio. The point of this much
# headroom is stability across machines, Python builds and allocator behavior, not a tight pin: a
# memory assertion that flakes on a slower box or a different malloc arena strategy is worse than a
# loose one that still catches a regression an order of magnitude off.
#
# This ceiling is a FLOOR, not the feature's final number. T633 adds the group-silence accumulator
# to this same path and T648 adds the knowledge-coverage pass; each re-runs this measurement with
# its own accumulator live and raises this constant with a new derivation written out the same way.
# Nothing here already budgets for either of them.
_PEAK_ALLOCATION_CEILING_BYTES = 900 * 1024 * 1024

# Generous relative to both committed recordings' extracted size (~6.9 MB and ~4.0 MB per
# `tests/fixtures/replays/README.md`). A fixture-test-local constant only — never
# `ANALYSIS_MAX_RAW_BYTES` itself, which this package never hard-codes (see module docstring).
_FIXTURE_MAX_RAW_BYTES = 50_000_000

_FIXTURES_ROOT = Path(__file__).resolve().parents[3] / "tests/fixtures/replays"
_COMMITTED_RECORDINGS = sorted(_FIXTURES_ROOT.glob("AgeIIDE_Replay_*.zip"))

# FR-020: these two kinds are declared in the closed vocabulary with no producer yet (T623) — see
# `packages/core/src/aoe2stats_core/replay/events.py` and `contracts/canonical-events.md`'s
# "declared only" column. The day a producer lands, this set is what changes; no event type does.
_DECLARED_ONLY_KINDS = frozenset({EventKind.STARTING_ATTRIBUTES, EventKind.STARTING_OBJECT})


@dataclass(frozen=True)
class _Measurement:
    events: list[CanonicalEvent]
    peak_bytes: int


@pytest.fixture(scope="module", params=_COMMITTED_RECORDINGS, ids=lambda p: p.stem)
def measurement(request: pytest.FixtureRequest) -> _Measurement:
    """Drive one committed recording through the full canonical path (`events()`, fully consumed),
    tracing peak Python allocation over the whole call. Module-scoped and parametrized so each
    recording is parsed and measured exactly once and shared between the two tests below, rather
    than reparsed per assertion."""
    zip_bytes = request.param.read_bytes()
    extractor = Aoe2RecExtractor(max_raw_bytes=_FIXTURE_MAX_RAW_BYTES)

    tracemalloc.start()
    try:
        events = list(extractor.events(zip_bytes))
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    return _Measurement(events=events, peak_bytes=peak)


def test_the_committed_recordings_are_found() -> None:
    assert len(_COMMITTED_RECORDINGS) >= 2


def test_peak_allocation_over_the_full_canonical_path_stays_under_the_measured_ceiling(
    measurement: _Measurement,
) -> None:
    assert measurement.events, "expected the canonical stream to yield at least one event"
    assert measurement.peak_bytes <= _PEAK_ALLOCATION_CEILING_BYTES, (
        f"peak Python allocation {measurement.peak_bytes} bytes "
        f"({measurement.peak_bytes / 1024 / 1024:.1f} MB) exceeds the "
        f"{_PEAK_ALLOCATION_CEILING_BYTES / 1024 / 1024:.0f} MB ceiling derived above — this "
        "ceiling is a floor for T633 and T648, not the feature's final number, but crossing it "
        "here without either of those accumulators on the path means either a real regression "
        "or that the derivation above needs redoing before those tasks build on it"
    )


def test_the_declared_only_kinds_are_never_emitted(measurement: _Measurement) -> None:
    """FR-020: `starting-attributes` and `starting-object` exist in the vocabulary with no producer.
    Asserting they are never emitted — rather than saying nothing about them — is what makes the
    reserved vocabulary honest: the day a producer for either lands, this test is what changes, and
    no event type does."""
    emitted_kinds = {event.kind for event in measurement.events}
    leaked = emitted_kinds & _DECLARED_ONLY_KINDS
    assert not leaked, f"declared-only kind(s) emitted with no producer implemented: {leaked}"
