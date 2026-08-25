---
name: replay-parsing
description: How to parse .aoe2record files — which engine, the known bugs, quarantine and re-parse discipline. Load before any work on apps/parser or on capture-time validation.
---

# Parsing AoE2 DE replays

**The decision and its evidence live in
[`docs/adr/0001-replay-parser.md`](../../../docs/adr/0001-replay-parser.md): the head-to-head
measurements, version numbers, timings and alternatives considered. Read it once.** This file is the
working discipline.

## The rule

**`aoe2rec-py` is primary. `aoc-mgz` is secondary.** Both sit behind one Protocol in
`apps/parser/src/aoe2stats_parser/engines/`. Never import either directly outside its adapter.

That indirection is not architectural decoration: the primary parser has already changed once, when
a game patch broke `aoc-mgz` and left it broken for six months. Assume it will change again.

## Working with aoe2rec-py

```python
from aoe2rec_py import aoe2rec_py as native
rec = native.parse_rec(data)   # data: bytes
```

`rec["zheader"]["game_settings"]` holds the lobby and per-player setup. `rec["operations"]` is the
full event stream — `Sync`, `Viewlock`, `Action`, `Chat`, `PostGame`. Duration is the sum of
`Sync.time_increment`. `Build` plus `Research` plus that clock is what age-up times, opening
detection and idle-TC are computed from. `PostGame` carries per-player elo.

**Do not use the bundled `RecSummary` helper.** It raises `KeyError` on chat from a player id absent
from its players dict, which happens whenever a spectator talks. Call `parse_rec()` directly and
build our own summary; we want our own domain model anyway.

**The published wheel lags the Rust crate.** Saved-and-restored games may fail to parse until a new
wheel ships. Building from source with `maturin` is the fallback.

## Version discipline

Record `parser_name`, `parser_version` and `engine_deps` on every `replay_parses` row. Without it,
there is no way to know which replays need re-parsing after an upgrade — and re-parsing everything
each time is how a cheap operation becomes an expensive one.

## Quarantine

A replay that fails to parse:

1. stays **untouched** in object storage. Never deleted, never "repaired".
2. gets a `replay_parses` row with `status='quarantined'`, the exception class, the full message and
   the stack.
3. raises **no per-item alert**. Alert on the quarantine *rate*. One unparsable file is a curiosity;
   a rising fraction is a patch that broke the parser.
4. stays replayable. Quarantine is a state, not an ending.

## Re-parsing

`replay_parses` is unique on `(replay_capture_id, parser_name, parser_version)`. A new engine version
means enqueueing every `stored` capture and inserting new rows. Nothing existing is touched, no
migration is needed, and running two engines side by side costs nothing.

Order a bulk re-parse: quarantined first, then most recent, then the rest, rate-limited to the run's
time budget.

## Extraction safety

Extract **in memory or into an ephemeral tmpdir**, never beside the archived zip and never persisted
— serverless filesystems are ephemeral and read-only outside `/tmp`. Before extracting, assert a
single-member archive, a name matching `AgeIIDE_Replay_\d+\.aoe2record`, and a decompressed-size cap.
The normal ratio is about eight to one, so anything far above that is a zip bomb, not a replay.

## Extraction discipline

**Memory bound, not time bound.** Analysis work is refused above a raw-size ceiling derived from the
parser's measured memory amplification, not a time budget — see `ANALYSIS_MAX_RAW_BYTES` in
`specs/003-player-search-match-analysis/plan.md` and R3 in that feature's
[`research.md`](../../../specs/003-player-search-match-analysis/research.md). A recording that hits
the ceiling and is refused is an **expected outcome**, not an incident: it must not raise a per-item
alert or get retried on a timer. Only the refusal rate is worth watching.

**`Build` is not decoded by the pinned wheel.** It comes back as `{"action_length", "data": [...]}`
with no `player_id` field — the player id and building type are inside the raw `data` payload, and
decoding that is this repository's job, covered by a golden test. Do not treat `Build` as usable
as-delivered. See [`docs/adr/0001-replay-parser.md`](../../../docs/adr/0001-replay-parser.md) and R4
in `specs/003-player-search-match-analysis/research.md` for what was measured and why the ADR's
original claim about `Build` no longer holds.

**Collapse duplicated commands to their first occurrence.** A double-click on an in-game button
(age-up, research) issues the same command twice, milliseconds apart. Extraction must dedupe on
`(player_id, technology_type)` — or the equivalent key for the command in question — and keep the
first occurrence only, or a two-player game reports more age-ups than players. See R5 in
`specs/003-player-search-match-analysis/research.md` and T355 in that feature's `tasks.md` for the
rule this was written against.

**A `.aoe2record` is a command log, not a state log.** It records what a player told the game to do,
never the game's derived response — resources, population, units lost. Anything about _state_ is a
reconstruction from the command stream, not a reading, and must never be presented with the same
confidence as a value taken directly off an operation. Label reconstructions as such, or don't
publish them. See `specs/003-player-search-match-analysis/research.md` (the command-log-vs-state-log
distinction) and that feature's `spec.md` for the ruling this forced on FR-043.

## Checking whether parsing still works

```bash
uv run --with aoe2rec-py --with mgz scripts/checks/parser_canary.py
```

Runs against the committed reference fixture and reports every engine. It runs nightly. When it goes
red, a game patch broke something — update `docs/adr/0001-replay-parser.md` with what you find.
