# 009 research prototype: the recording's own state checkpoints

Feature 009 (`specs/009-native-simulation-feasibility/`) asked whether the actual simulated state
of a match can be recovered from a `.aoe2record`. The engine routes it investigated need a running
Windows game or a reimplementation (`docs/research/native-simulation-feasibility.md`). This
prototype is the one experiment the development machine could run end to end: it reads the state
samples the game's own simulation writes **into the recording** every 500 syncs, which neither
`aoe2rec-py` nor `aoc-mgz` decodes.

It is research code. Nothing under `apps/` or `packages/` imports it; it depends on the standard
library only; it opens no connection, so constitution III's provider rule does not apply to it; it
never modifies or extracts the committed fixtures beside themselves.

## What it demonstrates

On the three committed reference recordings (`tests/fixtures/replays/README.md`), every 500th sync
carries, for every lobby slot, eleven 32-bit words the game computed from its live state. Word 8 is
the player id (lane + 1, every checkpoint). Word 1 is the four resource stocks summed: the first
checkpoint of seven of eight players equals the header's starting stocks minus the villagers and
houses queued before it, to the unit; the eighth is 33 higher and unexplained. The other words'
semantics are published by `librematch/genie` and are **not** corroborated here; in particular
word 6 ("live object count") decreases three times before any combat is possible, so it is not a
creation-minus-death counter. The tests hold every number the documents quote.

Each emitted observation carries the recording, the lane, both time bases (the block's own
`world_time_ms` and the sum of sync increments `clock_ms`, which differ by the checkpoint sync's own
increment), the raw words, and the provenance `ENGINE_STATE`. `sample-output.json` is the reader's
`--series` output on the build 185872 recording, and a test asserts it is byte-for-byte what the
reader prints.

## Run

```bash
uv run python scripts/research/009-native-simulation/checkpoints.py --series tests/fixtures/replays/AgeIIDE_Replay_511523321.zip
```

```bash
uv run pytest -q scripts/research/009-native-simulation/tests
```

## Known limitations

- Sums and counts only: no per-object value, no per-resource stock, no event. Nothing about a
  single unit, building or technology can be read from a checkpoint.
- One sample per 500 syncs: 6.5 s of game time in the build 185872 recording throughout, 6.5 s in
  the other 1v1 with 61 longer gaps up to 12.0 s, 6.5 to 15.3 s in the 2v2 (median 14.0 s), because
  a sync's length varies with the match.
- The reader walks the first chapter only and stops at the end operation; a recording with several
  chapters is not handled; a recording of a build other than 180059 and 185872 has not been read.
- The build is read at the offset the three fixtures share; another header layout returns `null`.
- This tests the reader and the recordings, not replay determinism (spec FR-013): no simulation
  was run.
- Not a replacement for the engine: it anchors a reconstruction, it does not produce one.
