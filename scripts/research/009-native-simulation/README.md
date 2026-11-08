# 009 research prototype: the recording's own state checkpoints

Feature 009 (`specs/009-native-simulation-feasibility/`) asked whether the actual simulated state
of a match can be recovered from a `.aoe2record`. The engine routes it investigated need a running
game or a reimplementation (`docs/research/native-simulation-feasibility.md`). This prototype is
the one experiment the development machine could run: it reads the state samples the game's own
simulation writes **into the recording** every 500 syncs, which neither `aoe2rec-py` nor `aoc-mgz`
decodes.

It is research code. Nothing under `apps/` or `packages/` imports it; it depends on the standard
library only; it never modifies or extracts the committed fixtures beside themselves.

## What it demonstrates

On the three committed reference recordings (`tests/fixtures/replays/README.md`), every 500th sync
carries, for every lobby slot, eleven 32-bit words the game computed from its live state: among
them the four resource stocks summed (word 1), the live object count (word 6) and the player id
(word 8). The layout and word semantics are published by `librematch/genie` and were read as a
specification; see the module docstring. The values are engine state, exact as integers, coarse in
time and shape. `sample-output.json` is the reader's output on the three fixtures; the test pins
the counts and the first checkpoint of every player.

## Run

```bash
uv run python scripts/research/009-native-simulation/checkpoints.py tests/fixtures/replays/AgeIIDE_Replay_511523321.zip
```

```bash
uv run pytest -q scripts/research/009-native-simulation/tests
```

## Known limitations

- Sums and counts only: no per-object value, no per-resource stock, no event. A death is visible
  only as a live-count decrease net of creations between two checkpoints.
- One sample per 500 syncs: 6.5 s of game time in the two 1v1 recordings, 6.5 to 15 s in the 2v2,
  because a sync's length varies with the match.
- The reader walks the first chapter only and stops at the end operation; a recording with several
  chapters is not handled.
- The build is read at the offset the three fixtures share; another header layout returns `null`.
- Not a replacement for the engine: it anchors a reconstruction, it does not produce one.
