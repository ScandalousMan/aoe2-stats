---
name: replay-parsing
description: How to parse .aoe2record files — which engine, the known bugs, quarantine and re-parse discipline. Load before any work on packages/replay-engine, apps/analyzer or capture-time validation.
---

# Parsing AoE2 DE replays

**The decision and its evidence live in
[`docs/adr/0001-replay-parser.md`](../../../docs/adr/0001-replay-parser.md): the head-to-head
measurements, version numbers, timings and alternatives considered. Read it once.** This file is the
working discipline.

## The rule

**`aoe2rec-py` is primary. `aoc-mgz` is secondary.** Only the primary sits behind a Protocol: its
adapter is `packages/replay-engine/src/aoe2stats_replay_engine/aoe2rec.py` and the Protocols are in
`packages/core/src/aoe2stats_core/replay/`. Never import `aoe2rec_py` outside that adapter. The
secondary has no adapter — the nightly canary installs it ephemerally — and giving both engines one
Protocol is an open gap (`docs/risks.md`), not something to assume.

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

**`Build` is half-decoded by the pinned wheel.** It comes back as
`{"player_id", "action_length", "data": [...]}`. The player identifier is supplied by the wheel, as
on every other action variant, and `packages/replay-engine/tests/test_aoe2rec.py` pins that across
every placement in the fixture — read it from the field, never from `data`. Only the **building
identifier** is undecoded: it lives in the raw `data` payload and decoding it is this repository's
job (`decode_build_action`), covered by a golden test. See
[`docs/adr/0001-replay-parser.md`](../../../docs/adr/0001-replay-parser.md) (the 2026-08-24
correction and its 2026-09-19 amendment) and R4 in
`specs/003-player-search-match-analysis/research.md` for what was measured.

**Collapse repeated commands to their first occurrence, on one key.** A double-click on an in-game
button issues the same command twice, milliseconds apart. `Aoe2RecExtractor` collapses `Research`
on `(player_id, technology_type)`, first occurrence over the whole match; age-ups are that same set
filtered to the three age technologies, not a second key. It also keeps only the first `Resign` per
player. There is **no time window** anywhere. Unit queueing (`DeQueue`) is deliberately not
collapsed. See R5 in `specs/003-player-search-match-analysis/research.md` and T355 in that
feature's `tasks.md` for the rule this was written against.

**The initial-state section is not empty, only unexposed.** The pinned wheel returns it as three
scalars and stops, but the decompressed header does contain each player's starting attributes,
findable by an anchor without a full grammar, and the lobby presets are already named fields in the
wheel's output. Do not conclude that the starting state is unreadable: the anchor and what was
measured are in `specs/006-replay-analysis-foundations/research.md` D1. A repository-local decoder
is planned for feature 007; none exists yet.

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
