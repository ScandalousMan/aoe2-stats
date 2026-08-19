# ADR 0001 — Replay parser: aoe2rec-py primary, aoc-mgz secondary

- **Status**: accepted
- **Date**: 2026-08-19
- **Supersedes**: the initial project brief, which mandated `happyleavesaoc/aoc-mgz`

## Context

The V2 analysis engine needs to read `.aoe2record` files. The obvious choice was `aoc-mgz`, the
long-standing Python reference parser, and the project brief named it explicitly.

It does not work on current-patch replays. Since the 2026-02-17 Americas/Chieftains DLC, `aoc-mgz`
fails to parse; [issue #138](https://github.com/happyleavesaoc/aoc-mgz/issues/138) has been open
since 2026-02-20. PRs #139 and #142 fix the fast parser and are confirmed working by several users,
but remain unmerged: the maintainer has been undecided since 2026-03-16 about whether to also update
the full parser or drop it. The last comment on the thread is "pls merge", dated 2026-07-20.

The same breakage very likely killed `aoestats.io`, whose weekly dumps have contained zero matches
every week since 2026-02-08.

Meanwhile `aoe2companion` visibly keeps parsing recent games. Following that thread:
`denniske/replay-nodejs` (pushed 2026-03-10) is a vendored copy of the npm package `aoe2rec-js`
v0.1.22, which is the WASM build of [`aoe2ct/aoe2rec`](https://github.com/aoe2ct/aoe2rec) — a Rust
parser by Stéphane Bisinger, MIT licensed. That crate also publishes **`aoe2rec-py`**, a PyO3 binding
on PyPI with prebuilt wheels.

## Evidence

Both parsers were run on the same file, on the same machine, on 2026-08-19:
`AgeIIDE_Replay_500546441.aoe2record`, a ranked 1v1 played that day, build 180059 / VER 9.4 /
version_major 68, 6 909 299 bytes. The file is committed at
`tests/fixtures/replays/AgeIIDE_Replay_500546441.zip`.

| Parser | Version | Result |
| --- | --- | --- |
| `aoc-mgz` | 1.8.51 (PyPI, current) | **fails** — fast parser: `could not parse`; full and summary: `RuntimeError: invalid mgz file: expected 8 to 8, found 1 (parsing) -> de -> de -> players` |
| `aoe2rec-py` | 0.1.21 (PyPI) | **succeeds** — 0.54 s, 484 542 operations |

What `aoe2rec_py.parse_rec()` returned:

- `zheader.game_settings`: 60+ fields including `dlcs`, `selected_map_id`, `victory_type_id`,
  `speed`, `population_limit`, `ranked`, `strategic_numbers`, and `players[]` with `civ_id`,
  `color_id`, `resolved_team_id`
- `operations`: `Sync` 236 649, `Viewlock` 236 649, `Action` 11 214, `Chat` 29, `PostGame` 1
- actions: `Move` 5 272, `Formation` 1 239, `Interact` 1 135, `DeQueue` 899, `Gatherpoint` 630,
  `Stance` 517, **`Build` 326**, `Patrol` 287, `Order` 244, **`Research` 74**, plus `Sell`, `Buy`,
  `Delete`, `Repair`, `BackToWork`, `Resign`
- `PostGame` blocks carrying per-player leaderboard elo

`Build` plus `Research` plus the `Sync` clock is everything the V2 engine needs for age-up times,
opening detection, idle-TC and eAPM.

## Decision

**`aoe2rec-py` is the primary parser. `aoc-mgz` is kept as a secondary engine.**

Both sit behind one Protocol in `apps/parser/src/aoe2stats_parser/engines/`. `replay_parses` records
`parser_name`, `parser_version` and `engine_deps` on every row, and is unique on
`(replay_capture_id, parser_name, parser_version)`, so running both engines over the same archive
costs nothing and re-parsing after an upgrade is an insert rather than a migration.

The Python-backend constraint from the brief is unaffected: `aoe2rec-py` is an ordinary Python
import, not a subprocess. Wheels cover cp39 to cp314 on manylinux, musllinux, macOS arm64 and
Windows; the manylinux x86_64 wheel is ~445 KB, well inside Vercel's 500 MB Python bundle limit.

## Consequences

- V2 is **not** blocked. The analysis engine can be built against current-patch replays today.
- `aoc-mgz` remains useful for pre-2026-02 archives and for cross-checking fields that `aoe2rec` does
  not yet name.
- Two known defects to work around, both minor and documented in the `replay-parsing` skill:
  - the bundled `RecSummary` helper raises `KeyError` on spectator chat in a 1v1, so we call
    `parse_rec()` directly and build our own summary layer;
  - the published wheel (0.1.21, 2026-03-08) lags the Rust crate (0.9.0, plus multichapter support
    added 2026-08-02), so saved-and-restored games may fail until a new wheel ships. Fallback is
    building from source with `maturin`.
- A nightly canary parses recent replays with **both** engines and publishes both success rates. The
  failure mode we are guarding against — a game patch silently breaking parsing for months — is
  exactly what happened to aoestats.

## Alternatives considered

- **Wait for mgz PRs #139/#142 to merge.** Rejected: six months of inaction, and waiting would mean
  archiving replays we cannot verify.
- **Fork aoc-mgz with #142 applied.** Kept as a fallback, not as the default: it inherits the same
  maintenance gap.
- **`AoEInsights/mgz-fast`.** Kept as a fallback.
- **Call the `aoe2rec` Rust CLI as a subprocess.** Rejected: `aoe2rec-py` gives the same parser
  in-process with no serialization boundary and no binary to ship.
