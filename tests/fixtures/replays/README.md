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

## `AgeIIDE_Replay_504695319.zip`

A ranked 2v2 team game (four players, two teams of two) played on **2026-09-06**, downloaded on
**2026-09-19** from `https://aoe.ms/replay/?gameId=504695319&profileId=2582827`, byte-for-byte as
served.

| Property       | Value                                                                                 |
| -------------- | ------------------------------------------------------------------------------------- |
| Game build     | 180059 (VER 9.4, version_major 68)                                                    |
| Zip size       | 1 145 403 bytes                                                                       |
| Extracted size | 4 039 881 bytes (ratio x3.5)                                                          |
| Members        | exactly one: `AgeIIDE_Replay_504695319.aoe2record`                                    |
| Point of view  | profile 2582827                                                                       |
| Operations     | 232 503 (`Sync` 113 348, `Viewlock` 113 348, `Action` 5 794, `Chat` 12, `PostGame` 1) |

**Why it is committed.** It adds a second match size to the reference set: a team game with four
participants, on the same game build as the first recording. Replays are purged from the official
servers after about 31 days, so this file cannot be re-downloaded either.

Do not modify it, do not re-zip it, do not commit an extracted `.aoe2record` beside it.

SHA-256: `915008aecf56bc9f7fc060b83c49a899383585d094e9c801e4583567a3dfe273`

## `AgeIIDE_Replay_511523321.zip`

A ranked 1v1 on Arabian Desert played on **2026-10-05**, downloaded the same day from
`https://aoe.ms/replay/?gameId=511523321&profileId=5632575` (which 301-redirects to
`api.ageofempires.com` `GetMatchReplay`), byte-for-byte as served.

| Property       | Value                                                                                                                                 |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Game build     | 185872 (VER 9.4, version_major 68)                                                                                                    |
| Zip size       | 861 726 bytes                                                                                                                         |
| Extracted size | 5 122 364 bytes (ratio x5.9)                                                                                                          |
| Members        | exactly one: `AgeIIDE_Replay_511523321.aoe2record`                                                                                    |
| Point of view  | profile 5632575, the profile the download was requested as (`zheader.replay.rec_player` 1, the first listed player's `player_number`) |
| Operations     | 349 253 (`Sync` 172 417, `Viewlock` 172 417, `Action` 4 402, `Chat` 15, `Pregame` 1, `PostGame` 1), in one chapter                    |

**Why it is committed.** It is the first recording on a game build the pinned parser of the time,
`aoe2rec-py` 0.1.21, could not read: that version panics on it, and 0.1.24 parses it in 0.22 s.
Replays are purged from the official servers after about 31 days, so this file cannot be
re-downloaded. It carries the 0.1.22+ result shape (one chapter, `Pregame` as the first operation)
and the first chat message on a channel other than 0 (one message, channel 1).

**The point of view is `zheader.replay.rec_player`, not `Pregame.rec_owner`.** `rec_player` is a
player number, matched against each player's `player_number`; on all three recordings it names the
profile the download was requested for (196240, 2582827, 5632575). `Pregame.rec_owner` is 1 in all
three: read as an index into the player list it named the recorder of the two build 180059
recordings only because both were recorded by player number 2 (index 1), and it names the opponent
here, where the recorder is player number 1 (index 0).

The operation counts of the two recordings above were measured with 0.1.21, which returned the
`Pregame` block as a separate `meta` key; 0.1.24 reports it as the first operation, so it counts
one more for each (484 543 and 232 504) with every other kind unchanged.

Do not modify it, do not re-zip it, do not commit an extracted `.aoe2record` beside it.

SHA-256: `7737906f6ea8534939a419196c46e716b4c06832b7ec089f36e1bea87acf5b0f`

## `AgeIIDE_Replay_500546441.timeline.json`

The golden `MatchTimeline` (T355, contracts/analysis.md): `Aoe2RecExtractor.extract()` run over
`AgeIIDE_Replay_500546441.zip`, `dataclasses.asdict` applied to the result,
`json.dumps(..., indent=2, sort_keys=False)`. Field order is therefore the dataclass declaration order in
`packages/core/src/aoe2stats_core/replay/analysis.py`, not alphabetical, and every list (`builds`,
`trainings`, `researches`) is in stream order — both deliberate, so a re-generation diffs cleanly
against this one rather than reordering for no reason.

Regenerate only when `aoe2rec-py` is upgraded or the extractor's own logic changes, and only by
re-running `extract()` — never hand-edited. Every diff this produces has to be read and explained
(ADR-0001's own failure mode: a parser upgrade that silently changed what was being read). Do not
regenerate it to make a failing test pass without first understanding why the output moved.

## `AgeIIDE_Replay_<id>.canonical.json` (one per recording)

The golden canonical event stream (T629): `Aoe2RecExtractor(...).events(zip_bytes)` — the public
`CanonicalEventSource` seam, not the adapter's internals — run over each committed zip, one file
beside each recording (`AgeIIDE_Replay_500546441.canonical.json`,
`AgeIIDE_Replay_504695319.canonical.json`, `AgeIIDE_Replay_511523321.canonical.json`). Serialised by `scripts/ops/canonical_golden.py`
(T652e; not shipped — a dev-only tool, moved out of `packages/replay-engine/src/` because that
directory ships in the deployed wheel): a JSON object with `format`, `recording`, `event_count`
and `events`, **one compact event per line** so a diff names the events that moved. Each event is
`clock_ms`, `kind` (kebab-case), `participant` (a slot number or null) and `payload` (dataclass
declaration order); the tier is derived from the kind and not written. There is no message text
(chat carries a channel only) and no name: participants are slot numbers.
`packages/replay-engine/tests/test_canonical_golden.py` compares the live stream to these files
byte for byte and reports the first differing line.

Regenerate only when `aoe2rec-py` is upgraded or the adapter's logic changes deliberately, only by
running `uv run python scripts/ops/canonical_golden.py`, never by hand and never from a test. Every
diff it produces has to be read and explained. Do not regenerate to make a failing test pass
without first understanding why the stream moved: a moved event means something was lost or
altered, which is the failure the golden exists to catch.
