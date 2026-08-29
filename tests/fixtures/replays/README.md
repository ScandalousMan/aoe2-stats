# Reference replay fixtures

## `AgeIIDE_Replay_500546441.zip`

A ranked 1v1 played on **2026-08-19**, downloaded from
`https://aoe.ms/replay/?gameId=500546441&profileId=196240` the same day, byte-for-byte as served.

| Property       | Value                                                                                  |
| -------------- | -------------------------------------------------------------------------------------- |
| Game build     | 180059 (VER 9.4, version_major 68)                                                     |
| Zip size       | 871 503 bytes                                                                          |
| Extracted size | 6 909 299 bytes (ratio x7.9)                                                           |
| Members        | exactly one: `AgeIIDE_Replay_500546441.aoe2record`                                     |
| Point of view  | profile 196240                                                                         |
| Operations     | 484 542 (`Sync` 236 649, `Viewlock` 236 649, `Action` 11 214, `Chat` 29, `PostGame` 1) |

**Why it is committed.** Replays are purged from the official servers after about 31 days, so this
file cannot be re-downloaded. It is the reference against which parser compatibility is verified:
`aoe2rec-py` 0.1.21 parses it in 0.54 s, `aoc-mgz` 1.8.51 fails on it. See
`docs/adr/0001-replay-parser.md`.

Do not modify it, do not re-zip it, do not commit an extracted `.aoe2record` beside it.

SHA-256: `5cb3f074734f405032cf73f40cd1ccdb71ec1069f0a4829b3abaef6f6f211bbc`

## `AgeIIDE_Replay_500546441.timeline.json`

The golden `MatchTimeline` (T355, contracts/analysis.md): `Aoe2RecExtractor.extract()` run over the
zip above, `dataclasses.asdict` applied to the result, `json.dumps(..., indent=2, sort_keys=False)`.
Field order is therefore the dataclass declaration order in
`packages/core/src/aoe2stats_core/replay/analysis.py`, not alphabetical, and every list (`builds`,
`trainings`, `researches`) is in stream order — both deliberate, so a re-generation diffs cleanly
against this one rather than reordering for no reason.

Regenerate only when `aoe2rec-py` is upgraded or the extractor's own logic changes, and only by
re-running `extract()` — never hand-edited. Every diff this produces has to be read and explained
(ADR-0001's own failure mode: a parser upgrade that silently changed what was being read). Do not
regenerate it to make a failing test pass without first understanding why the output moved.
