---
name: replay-parsing
description: Parsing .aoe2record files — aoe2rec-py (primary) and aoc-mgz (secondary), compatibility state, known bugs, quarantine and re-parse strategy. Load before any work on apps/parser.
---

# Parsing AoE2 DE replays

## Which parser, and why — read this first

**`aoe2rec-py` is the primary parser. `aoc-mgz` is secondary.** This overrides any older project
note naming mgz as the parser.

Head-to-head on the same current-patch file (`AgeIIDE_Replay_500546441.aoe2record`, ranked 1v1
played 2026-08-19, build 180059 / VER 9.4 / version_major 68, 6.9 MB), measured 2026-08-19:

| Parser | Result |
| --- | --- |
| `aoc-mgz` 1.8.51 (PyPI, current) | FAILS — fast: `could not parse`; full/summary: `RuntimeError: invalid mgz file: expected 8 to 8, found 1 (parsing) -> de -> de -> players` |
| `aoe2rec-py` 0.1.21 (PyPI) | SUCCEEDS — 0.54 s, 484 542 operations |

`aoe2rec` (github.com/aoe2ct/aoe2rec) is a Rust parser by Stéphane Bisinger, MIT licensed, and
explicitly "largely an adaptation of aoc-mgz" — same lineage, faster release cadence. Its 0.7.0
release landed 4 days after the DLC that broke mgz. It is what aoe2companion uses, via the
`aoe2rec-js` WASM build.

## aoe2rec-py

Published on PyPI with prebuilt wheels for cp39-cp314 (including free-threaded), manylinux,
musllinux, macOS arm64 and Windows. `requires_python >=3.9`. The manylinux x86_64 wheel is about
445 KB, comfortably inside Vercel's 500 MB Python bundle limit.

```python
from aoe2rec_py import aoe2rec_py

rec = aoe2rec_py.parse_rec(data)  # data: bytes
```

Returned structure:

- `rec["zheader"]` — `game`, `version_major`, `build`, `timestamp`, `map_info`, `initial`,
  `ai_config`, `game_settings`.
- `rec["zheader"]["game_settings"]` — 60+ fields: `dlcs`, `selected_map_id`, `victory_type_id`,
  `speed`, `population_limit`, `ranked`, `lobby_name`, `strategic_numbers`, `rms_strings`, and
  `players[]` with `civ_id`, `color_id`, `resolved_team_id`, `dlc_id`.
- `rec["operations"]` — the full event stream. On the reference file: `Sync` 236 649,
  `Viewlock` 236 649, `Action` 11 214, `Chat` 29, `PostGame` 1.
- Action types observed: `Move`, `Formation`, `Interact`, `DeQueue`, `Gatherpoint`, `Stance`,
  `Build`, `Patrol`, `Order`, `Stop`, `Release`, `Research`, `Transform`, `Sell`, `Delete`,
  `Repair`, `Buy`, `BackToWork`, `Resign`.
- `PostGame` blocks carry per-player leaderboard `elo`.

Match duration is the sum of `Sync.time_increment`. `Build` plus `Research` plus the sync clock give
age-up times, opening detection and idle-TC. Action counts per `player_id` give eAPM.

**Do not use the bundled `RecSummary` convenience class.** It raises `KeyError` when a chat message
comes from a player id absent from its players dict (spectator chat in a 1v1) — reproduced on the
reference file. Call `parse_rec()` directly and build our own summary in
`apps/parser/src/aoe2stats_parser/summary.py`; we want our own domain model anyway.

**The published wheel lags the crate.** Wheel 0.1.21 dates from 2026-03-08 while the Rust crate is at
0.9.0 with multichapter support added 2026-08-02. Multichapter recs (saved and restored games) may
fail until a new wheel ships; the fallback is building from source with `maturin`.

## aoc-mgz — secondary

- master and PyPI are both **1.8.51**; the newest GitHub tag (1.8.26, 2024) is misleading.
- **Issue #138, open since 2026-02-20**: parsing broken since the 2026-02-17 Americas/Chieftains DLC
  (`mgz/fast/header.py:46 -> de_string() -> AssertionError`). PRs #139 and #142 fix the fast parser
  and are community-confirmed, but remain unmerged.
- The dependency is pinned `aocref>=2.0.35` while the current dataset needs 2.0.37.
- Still useful for **pre-2026-02 archives** and for cross-checking an uncertain field: its `summary`
  and `model` abstractions name some things aoe2rec does not yet.
- Active fork if needed: `AoEInsights/mgz-fast`.

```python
from mgz.model import parse_match   # high-level abstraction
from mgz.summary import Summary     # more raw data
```

## Engine interface

Both parsers live behind one Protocol in `apps/parser/src/aoe2stats_parser/engines/`. Adding,
swapping or running two engines side by side must never require touching the domain. The primary
parser has already changed once; assume it will change again.

## Version discipline

Pin all engine versions and record them on every `replay_parses` row: `parser_name`,
`parser_version`, and `engine_deps` (for mgz, `aocref`). Without this we can never tell which
replays need re-parsing after an upgrade.

## Quarantine

A replay that fails to parse:

1. stays **untouched** in object storage — never deleted, never "repaired";
2. produces a `replay_parses` row with `status='quarantined'`, the exception class, the full message
   and the stack;
3. raises no per-item alert — we alert on the quarantine **rate**, not on a single case;
4. stays replayable: quarantine is a state, not an ending.

## Re-parse strategy

`replay_parses` is unique on `(replay_capture_id, parser_name, parser_version)`. A new parser version
means enqueueing every `stored` capture and inserting new rows; nothing existing is touched. No
migration, no loss. Priority for a bulk re-parse: quarantined first, then most recent, then the rest,
rate-limited to fit the run's time budget.

## Extraction

The `.aoe2record` is extracted **in memory or into an ephemeral tmpdir**, never written next to the
archived zip and never persisted (serverless filesystems are ephemeral and read-only outside `/tmp`).
Before extracting, assert: single-member archive, name matching `AgeIIDE_Replay_\d+\.aoe2record`, and
a decompressed-size cap as a zip-bomb guard — the observed ratio is x7.9, so anything far above that
is suspect.
