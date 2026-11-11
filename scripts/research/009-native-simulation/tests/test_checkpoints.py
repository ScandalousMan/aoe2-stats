"""The checkpoint reader against the three committed reference recordings (feature 009).

Measured 2026-11-08. These tests hold every number the research documents quote about the
checkpoints (`docs/research/native-simulation-feasibility.md` §6, `docs/data-sources.md` §2), so a
change here is a change to those claims and must be explained there. They test the reader and the
recordings; they do not test replay determinism (spec FR-013), which needs a simulation to run.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from itertools import pairwise
from pathlib import Path

import pytest
from aoe2rec_py import aoe2rec_py as native
from tests.test_starting_state_anchor import (
    HUMAN_PLAYER_TYPE,
    find_anchors,
    inflate_header,
    read_leading_values,
)

ROOT = Path(__file__).resolve().parents[4]
FIXTURES = ROOT / "tests" / "fixtures" / "replays"
HERE = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location("checkpoints", HERE / "checkpoints.py")
assert spec is not None and spec.loader is not None
checkpoints = importlib.util.module_from_spec(spec)
sys.modules["checkpoints"] = checkpoints
spec.loader.exec_module(checkpoints)

HOUSE = 70
VILLAGER_FOOD = 50
HOUSE_WOOD = 25

# recording id: build, syncs, commands, checkpoints, gap statistics in ms between consecutive
# checkpoints (count not equal to 6500, count above 7000, maximum, median), and per player id the
# first and last (world_time_ms, resource_sum, live_count).
RECORDINGS = {
    "500546441": {
        "build": 180059,
        "syncs": 236_649,
        "commands": 11_214,
        "checkpoints": 473,
        "gaps": (61, 43, 12_040, 6_500),
        "first": {1: (8_684, 500, 15), 2: (8_684, 508, 15)},
        "last": {1: (3_206_734, 655, 404), 2: (3_206_734, 1_420, 489)},
    },
    "504695319": {
        "build": 180059,
        "syncs": 113_348,
        "commands": 5_794,
        "checkpoints": 226,
        "gaps": (220, 220, 15_320, 14_000),
        "first": {
            1: (9_349, 450, 104),
            2: (9_349, 500, 100),
            3: (9_349, 450, 104),
            4: (9_349, 450, 105),
        },
        "last": {
            1: (3_106_358, 2_742, 294),
            2: (3_106_358, 4_772, 398),
            3: (3_106_358, 4_090, 326),
            4: (3_106_358, 8_695, 330),
        },
    },
    "511523321": {
        "build": 185872,
        "syncs": 172_417,
        "commands": 4_402,
        "checkpoints": 344,
        "gaps": (0, 0, 6_500, 6_500),
        "first": {1: (8_684, 550, 12), 2: (8_684, 650, 12)},
        "last": {1: (2_238_184, 1_980, 290), 2: (2_238_184, 2_706, 364)},
    },
}

# The one player whose first checkpoint the reconciliation below does not explain: word 1 is 508
# where the header's stocks minus the costs queued before it give 475. Unexplained on 2026-11-08.
UNEXPLAINED_FIRST_SUM = {("500546441", 2): 508}


def _fixture(recording_id: str) -> Path:
    return FIXTURES / f"AgeIIDE_Replay_{recording_id}.zip"


def _canonical(recording_id: str) -> list[dict]:
    path = FIXTURES / f"AgeIIDE_Replay_{recording_id}.canonical.json"
    return json.loads(path.read_text())["events"]


def _starting_stocks(raw: bytes) -> dict[int, tuple[int, int, int, int]]:
    """Each human player's four starting stocks from the header anchor settled by feature 006."""
    header = inflate_header(raw)
    (chapter,) = native.parse_rec(raw)["chapters"]
    out: dict[int, tuple[int, int, int, int]] = {}
    for player in chapter["zheader"]["game_settings"]["players"]:
        if player["player_type"] != HUMAN_PLAYER_TYPE:
            continue
        (offset,) = find_anchors(header, player["name"])
        values = read_leading_values(header, offset)
        out[player["player_number"]] = tuple(int(v) for v in values)  # type: ignore[assignment]
    return out


@pytest.mark.parametrize("recording_id", sorted(RECORDINGS))
def test_counts_builds_and_first_and_last_checkpoints(recording_id: str) -> None:
    expected = RECORDINGS[recording_id]
    reading = checkpoints.read(_fixture(recording_id))
    assert reading.build == expected["build"]
    assert reading.checksum_interval == 500
    assert (reading.syncs, reading.commands, reading.checkpoints) == (
        expected["syncs"],
        expected["commands"],
        expected["checkpoints"],
    )
    assert set(reading.players) == set(expected["first"])
    for player_id, series in reading.players.items():
        assert len(series) == expected["checkpoints"]
        first, last = series[0], series[-1]
        assert (first.world_time_ms, first.resource_sum, first.live_count) == expected["first"][
            player_id
        ]
        assert (last.world_time_ms, last.resource_sum, last.live_count) == expected["last"][
            player_id
        ]


@pytest.mark.parametrize("recording_id", sorted(RECORDINGS))
def test_lanes_follow_lobby_slots_and_word_5_is_never_written(recording_id: str) -> None:
    reading = checkpoints.read(_fixture(recording_id))
    for player_id, series in reading.players.items():
        assert all(c.player_id == player_id for c in series), "word 8 is the player id"
        assert all(c.lane == player_id - 1 for c in series), "lane = player id - 1"
        assert all(c.words[5] == 0 for c in series), "word 5 is never written by the engine"
        assert all(c.words[0] == 0 for c in series), "word 0 is 0 everywhere: unverifiable here"
        times = [c.world_time_ms for c in series]
        assert times == sorted(times) and len(set(times)) == len(times)


@pytest.mark.parametrize("recording_id", sorted(RECORDINGS))
def test_exactly_500_syncs_between_checkpoints_and_the_gap_statistics(recording_id: str) -> None:
    data = checkpoints.recording_bytes(_fixture(recording_id))
    syncs_since: int | None = None
    sync_gaps: set[int] = set()
    for kind, _clock, _payload in checkpoints.operations(data):
        if kind == "checkpoint":
            if syncs_since is not None:
                sync_gaps.add(syncs_since)
            syncs_since = 0
        elif kind == "sync" and syncs_since is not None:
            syncs_since += 1
    assert sync_gaps == {500}
    series = next(iter(checkpoints.read(_fixture(recording_id)).players.values()))
    gaps = [b.world_time_ms - a.world_time_ms for a, b in pairwise(series)]
    not_6500 = sum(1 for g in gaps if g != 6_500)
    above_7000 = sum(1 for g in gaps if g > 7_000)
    median = sorted(gaps)[len(gaps) // 2]
    assert (not_6500, above_7000, max(gaps), median) == RECORDINGS[recording_id]["gaps"]


@pytest.mark.parametrize("recording_id", sorted(RECORDINGS))
def test_the_two_time_bases_differ_by_the_checkpoint_syncs_own_increment(recording_id: str) -> None:
    data = checkpoints.recording_bytes(_fixture(recording_id))
    seen = 0
    for kind, clock, payload in checkpoints.operations(data):
        if kind == "checkpoint":
            words, dt = payload  # type: ignore[misc]
            assert words[checkpoints.LANES * checkpoints.WORDS] - clock == dt
            seen += 1
    assert seen == RECORDINGS[recording_id]["checkpoints"]


@pytest.mark.parametrize("recording_id", sorted(RECORDINGS))
def test_word_1_is_the_starting_stocks_minus_the_costs_queued_before_the_first_checkpoint(
    recording_id: str,
) -> None:
    """The FR-010 record for the resources scenario. Expected: the header's starting stocks (006's
    anchor) minus 50 food per villager queued and 25 wood per house placed before the first
    checkpoint's world time. Extracted: word 1 of that checkpoint. Source: ENGINE_STATE in the
    recording. Exact for seven of eight players; the eighth is recorded as unexplained."""
    path = _fixture(recording_id)
    raw = checkpoints.recording_bytes(path)
    stocks = _starting_stocks(raw)
    reading = checkpoints.read(path)
    events = _canonical(recording_id)
    for player_id, series in reading.players.items():
        first = series[0]
        early = [
            e
            for e in events
            if e["participant"] == player_id and e["clock_ms"] < first.world_time_ms
        ]
        villagers = sum(e["payload"].get("count", 1) for e in early if e["kind"] == "unit-queued")
        placed = [e["payload"]["building_id"] for e in early if e["kind"] == "building-placed"]
        assert set(placed) <= {HOUSE}, "only houses are placed before the first checkpoint"
        spending = {e["kind"] for e in early} & {"research-queued", "market-transaction"}
        assert not spending, f"unexpected early spending commands {spending}"
        expected = sum(stocks[player_id]) - VILLAGER_FOOD * villagers - HOUSE_WOOD * len(placed)
        if (recording_id, player_id) in UNEXPLAINED_FIRST_SUM:
            assert first.resource_sum == UNEXPLAINED_FIRST_SUM[recording_id, player_id]
            assert first.resource_sum != expected
        else:
            assert first.resource_sum == expected, (recording_id, player_id, stocks[player_id])


def test_word_6_is_not_a_creation_minus_death_counter() -> None:
    """Three live-count decreases happen before any combat is possible (under two minutes, with
    every army still a scout), so word 6 moves for reasons other than birth and death."""
    cases = {
        ("511523321", 2): (28_184, 34_684, 17, 16),
        ("504695319", 4): (35_349, 41_849, 106, 105),
        ("504695319", 1): (91_004, 105_004, 108, 107),
    }
    for (recording_id, player_id), (t0, t1, c0, c1) in cases.items():
        series = checkpoints.read(_fixture(recording_id)).players[player_id]
        by_time = {c.world_time_ms: c.live_count for c in series}
        assert (by_time[t0], by_time[t1]) == (c0, c1)


def test_sample_output_is_the_readers_output_on_the_185872_recording() -> None:
    """`sample-output.json` is valid JSON and is exactly what the reader prints with `--series`
    for the build 185872 recording, so every number in it is traceable to this run."""
    sample = json.loads((HERE / "sample-output.json").read_text())
    live = [checkpoints.summary(checkpoints.read(_fixture("511523321")), series=True)]
    assert sample == json.loads(json.dumps(live))
    observation = sample[0]["players"]["1"]["series"][0]
    assert {"recording", "world_time_ms", "clock_ms", "provenance", "words"} <= set(observation)
    assert observation["provenance"] == "ENGINE_STATE"


def test_the_reader_itself_is_deterministic() -> None:
    """A property of the reader, not of any simulation: FR-013's replay determinism is untested
    here because no simulation route was run."""
    path = _fixture("500546441")
    assert checkpoints.summary(checkpoints.read(path), series=True) == checkpoints.summary(
        checkpoints.read(path), series=True
    )
