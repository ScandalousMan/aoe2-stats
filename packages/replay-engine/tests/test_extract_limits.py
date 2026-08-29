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
"""

from __future__ import annotations

import inspect
import io
import os
import zipfile
from dataclasses import fields

import pytest
from aoe2rec_py import aoe2rec_py as _native

from aoe2stats_core.replay.analysis import MatchTimeline, ParticipantTimeline
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
