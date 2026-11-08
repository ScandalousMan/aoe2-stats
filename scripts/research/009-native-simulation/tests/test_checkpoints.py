"""The checkpoint reader against the three committed reference recordings (feature 009).

Measured 2026-11-08; the expected values are what the recordings hold, read twice. They are the
evidence behind `docs/research/native-simulation-feasibility.md` ("The recording's own state
checkpoints"), so a change here is a change to that report's claims and must be explained there.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
FIXTURES = ROOT / "tests" / "fixtures" / "replays"
MODULE_PATH = Path(__file__).resolve().parents[1] / "checkpoints.py"

spec = importlib.util.spec_from_file_location("checkpoints", MODULE_PATH)
assert spec is not None and spec.loader is not None
checkpoints = importlib.util.module_from_spec(spec)
sys.modules["checkpoints"] = checkpoints
spec.loader.exec_module(checkpoints)

RECORDINGS = {
    # recording id: (build, syncs, commands, checkpoints,
    #                {player id: (first resource sum, first live count)})
    "500546441": (180059, 236_649, 11_214, 473, {1: (500, 15), 2: (508, 15)}),
    "504695319": (
        180059,
        113_348,
        5_794,
        226,
        {1: (450, 104), 2: (500, 100), 3: (450, 104), 4: (450, 105)},
    ),
    "511523321": (185872, 172_417, 4_402, 344, {1: (550, 12), 2: (650, 12)}),
}


@pytest.mark.parametrize("recording_id", sorted(RECORDINGS))
def test_every_recording_carries_one_checkpoint_per_500_syncs(recording_id: str) -> None:
    build, syncs, commands, count, firsts = RECORDINGS[recording_id]
    reading = checkpoints.read(FIXTURES / f"AgeIIDE_Replay_{recording_id}.zip")
    assert reading.build == build
    assert reading.checksum_interval == 500
    assert (reading.syncs, reading.commands, reading.checkpoints) == (syncs, commands, count)
    # One lane per lobby slot, every checkpoint, player id in word 8.
    assert set(reading.players) == set(firsts)
    for player_id, series in reading.players.items():
        assert len(series) == count
        assert all(c.player_id == player_id for c in series)
        times = [c.world_time_ms for c in series]
        assert times == sorted(times) and len(set(times)) == len(times)
        assert all(c.words[5] == 0 for c in series), "word 5 is never written by the engine"
        assert (series[0].resource_sum, series[0].live_count) == firsts[player_id]


def test_the_sync_count_between_checkpoints_is_the_declared_interval() -> None:
    data = checkpoints.recording_bytes(FIXTURES / "AgeIIDE_Replay_511523321.zip")
    syncs_since = None
    gaps = set()
    for kind, _clock, _payload in checkpoints.operations(data):
        if kind == "checkpoint":
            if syncs_since is not None:
                gaps.add(syncs_since)
            syncs_since = 0
        elif kind == "sync" and syncs_since is not None:
            syncs_since += 1
    assert gaps == {500}


def test_reading_is_deterministic() -> None:
    path = FIXTURES / "AgeIIDE_Replay_500546441.zip"
    first = json.dumps(checkpoints.summary(checkpoints.read(path)), sort_keys=True)
    second = json.dumps(checkpoints.summary(checkpoints.read(path)), sort_keys=True)
    assert first == second
    assert [c.words for c in checkpoints.read(path).players[1]] == [
        c.words for c in checkpoints.read(path).players[1]
    ]
