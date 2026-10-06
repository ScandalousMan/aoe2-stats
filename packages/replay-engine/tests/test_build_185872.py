"""Game build 185872 and the `aoe2rec-py` 0.1.22+ result shape (T672, production incident).

The pinned 0.1.21 panicked on recordings from build 185872; 0.1.22 to 0.1.24 read them but return
`{"chapters": [chapter, ...]}` instead of one flat document, each chapter carrying `zheader` and
`operations`, and the old `meta` block is now the first operation, `{"Pregame": {...}}`. Two things
are tested here:

- the third committed recording (build 185872) extracts, validates and streams, against the
  numbers measured from the file itself; and
- the adapter's reading of the new shape, on synthetic parse results with the engine stubbed (the
  same technique as `test_extract_limits.py`): one chapter accepted, any other count refused with
  `EngineParseError` naming it, and a missing or misplaced `Pregame` refused with
  `EngineParseError` rather than a bare `KeyError` or `IndexError`.
"""

from __future__ import annotations

import io
import os
import zipfile
from collections.abc import Callable, Mapping
from importlib import metadata
from pathlib import Path

import pytest
from aoe2rec_py import aoe2rec_py as _native

from aoe2stats_core.replay.events import EventKind, MatchEndedPayload, MatchStartedPayload
from aoe2stats_core.replay.validation import EngineParseError
from aoe2stats_replay_engine.aoe2rec import (
    Aoe2RecExtractor,
    Aoe2RecValidator,
    _parse_or_raise,
    _read_member_bytes,
)
from aoe2stats_replay_engine.canonical import Accounting, canonical_events

_FIXTURES = Path(__file__).resolve().parents[3] / "tests/fixtures/replays"
BUILD_185872_REPLAY = _FIXTURES / "AgeIIDE_Replay_511523321.zip"

# Same fixture-local ceiling and rationale as `test_extract_limits.py`: never
# `ANALYSIS_MAX_RAW_BYTES` itself.
_FIXTURE_MAX_RAW_BYTES = 50_000_000


def _extractor() -> Aoe2RecExtractor:
    return Aoe2RecExtractor(max_raw_bytes=_FIXTURE_MAX_RAW_BYTES)


# --- the third committed recording ------------------------------------------------------------


def test_the_build_185872_recording_extracts() -> None:
    timeline = _extractor().extract(BUILD_185872_REPLAY.read_bytes())

    # `rec_owner` is 1 in this recording's `Pregame`, a zero-based index into the players, so the
    # point of view is the second listed player (R2), not the profile the download was requested
    # for (5632575, the first listed player) — measured from the file, recorded in the README.
    assert timeline.point_of_view_profile_id == 212721
    assert [p.profile_id for p in timeline.participants] == [5632575, 212721]
    assert [p.player_number for p in timeline.participants] == [1, 2]
    # The accumulated `Sync` clock and the post-game `WorldTime` agree, as on both older recordings.
    assert timeline.world_time_ms == 2_243_605
    assert timeline.engine_version == metadata.version("aoe2rec-py")
    assert all(p.actions > 0 for p in timeline.participants)


def test_the_build_185872_recording_streams_from_match_started_to_match_ended() -> None:
    events = list(_extractor().events(BUILD_185872_REPLAY.read_bytes()))

    first, last = events[0], events[-1]
    assert first.kind is EventKind.MATCH_STARTED
    assert isinstance(first.payload, MatchStartedPayload)
    assert first.payload.build == 185872
    assert last.kind is EventKind.MATCH_ENDED
    assert isinstance(last.payload, MatchEndedPayload)
    assert last.payload.final_clock_ms == 2_243_605


def test_the_build_185872_recording_validates() -> None:
    result = Aoe2RecValidator().validate(BUILD_185872_REPLAY.read_bytes())

    assert result.inner_filename == "AgeIIDE_Replay_511523321.aoe2record"
    assert result.inner_bytes == 5_122_364


def test_pregame_is_a_known_kind_not_an_unknown_one() -> None:
    _, data = _read_member_bytes(BUILD_185872_REPLAY.read_bytes())
    chapter = _parse_or_raise(data)
    accounting = Accounting()

    list(canonical_events(chapter, accounting))

    assert accounting.unknown_operation == 0


# --- the adapter's reading of the chapter shape, on synthetic parse results --------------------


def _zip_bytes() -> bytes:
    # Incompressible content, so the decompression-ratio cap never fires first.
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("AgeIIDE_Replay_1.aoe2record", os.urandom(1_000))
    return buffer.getvalue()


def _pregame(rec_owner: int = 0) -> dict[str, object]:
    return {
        "Pregame": {
            "checksum_interval": 500,
            "multiplayer": True,
            "rec_owner": rec_owner,
            "reveal_map": True,
            "use_sequence_numbers": False,
            "number_of_chapters": 0,
            "aok_or_de": False,
        }
    }


def _chapter(
    operations: list[dict[str, object]] | None = None, *, rec_owner: int = 0
) -> dict[str, object]:
    if operations is None:
        operations = [
            _pregame(rec_owner),
            {"Sync": {"time_increment": 1_000, "next": 0, "checksum": None}},
            {"PostGame": {"blocks": [{"WorldTime": {"length": 4, "world_time": 1_000}}]}},
        ]
    return {
        "header_end": 0,
        "header_len": 0,
        "next_chapter_address": 0,
        "zheader": {
            "build": 185872,
            "game_settings": {
                "resolved_map_id": 9,
                "starting_resources_id": 0,
                "starting_age_id": 2,
                "map_size": 120,
                "players": [
                    {
                        "player_number": n,
                        "profile_id": 1_000 + n,
                        "civ_id": n,
                        "resolved_team_id": n + 1,
                    }
                    for n in (1, 2)
                ],
            },
        },
        "operations": operations,
    }


def _stub(monkeypatch: pytest.MonkeyPatch, result: Mapping[str, object]) -> None:
    monkeypatch.setattr(_native, "parse_rec", lambda data: result)


_Entry = Callable[[Aoe2RecExtractor, bytes], object]


def _extract(extractor: Aoe2RecExtractor, zip_bytes: bytes) -> object:
    return extractor.extract(zip_bytes)


def _events(extractor: Aoe2RecExtractor, zip_bytes: bytes) -> object:
    return extractor.events(zip_bytes)


def test_a_single_chapter_is_accepted_and_its_pregame_names_the_point_of_view(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The contrast case for every refusal below: the same synthetic shape, one chapter.
    _stub(monkeypatch, {"chapters": [_chapter(rec_owner=1)]})

    timeline = _extractor().extract(_zip_bytes())

    # `players[1]` is profile 1002: the owner comes from `Pregame`, as a zero-based index.
    assert timeline.point_of_view_profile_id == 1_002
    assert timeline.world_time_ms == 1_000


def test_the_point_of_view_follows_the_pregame_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub(monkeypatch, {"chapters": [_chapter(rec_owner=0)]})

    assert _extractor().extract(_zip_bytes()).point_of_view_profile_id == 1_001


@pytest.mark.parametrize("entry", [_extract, _events], ids=["extract", "events"])
@pytest.mark.parametrize("count", [0, 2, 3])
def test_a_recording_with_any_other_chapter_count_is_refused_naming_the_count(
    monkeypatch: pytest.MonkeyPatch, entry: _Entry, count: int
) -> None:
    _stub(monkeypatch, {"chapters": [_chapter() for _ in range(count)]})

    with pytest.raises(EngineParseError, match=rf"{count} chapters"):
        entry(_extractor(), _zip_bytes())


@pytest.mark.parametrize("entry", [_extract, _events], ids=["extract", "events"])
def test_a_chapter_without_a_pregame_is_refused_not_a_key_error(
    monkeypatch: pytest.MonkeyPatch, entry: _Entry
) -> None:
    operations = _chapter()["operations"]
    assert isinstance(operations, list)
    _stub(monkeypatch, {"chapters": [_chapter(operations[1:])]})

    with pytest.raises(EngineParseError, match="Pregame"):
        entry(_extractor(), _zip_bytes())


@pytest.mark.parametrize("entry", [_extract, _events], ids=["extract", "events"])
def test_a_misplaced_pregame_is_refused(monkeypatch: pytest.MonkeyPatch, entry: _Entry) -> None:
    sync: dict[str, object] = {"Sync": {"time_increment": 1_000, "next": 0, "checksum": None}}
    _stub(monkeypatch, {"chapters": [_chapter([sync, _pregame()])]})

    with pytest.raises(EngineParseError, match="Pregame"):
        entry(_extractor(), _zip_bytes())


def test_an_empty_chapter_is_refused_not_an_index_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub(monkeypatch, {"chapters": [_chapter([])]})

    with pytest.raises(EngineParseError, match="Pregame"):
        _extractor().extract(_zip_bytes())


def test_the_pre_0_1_22_shape_is_refused_not_a_key_error(monkeypatch: pytest.MonkeyPatch) -> None:
    # A flat document with a `meta` block is what 0.1.21 returned; nothing here reads it any more.
    flat = {**_chapter(), "meta": {"rec_owner": 0}}
    _stub(monkeypatch, flat)

    with pytest.raises(EngineParseError, match="chapters"):
        _extractor().extract(_zip_bytes())


def test_pregame_yields_no_event_and_is_not_an_unknown_operation() -> None:
    accounting = Accounting()
    stream = {**_chapter(), "operations": [_pregame()]}

    events = [
        e for e in canonical_events(stream, accounting) if e.kind is not EventKind.MATCH_STARTED
    ]

    assert events == []
    assert accounting == Accounting()


def test_a_recording_owner_outside_the_players_is_refused_not_an_index_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub(monkeypatch, {"chapters": [_chapter(rec_owner=2)]})

    with pytest.raises(EngineParseError, match="recording owner 2"):
        _extractor().extract(_zip_bytes())
