# Implementation Plan: Player Search, Favourites and On-Demand Match Analysis

**Branch**: `003-player-search-match-analysis` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/003-player-search-match-analysis/spec.md`

## Summary

Open the product to players who are not the signed-in user: find them by name, follow them, read any
match they played, take the recorded game from any point of view, and — once per match, ever — have
that game parsed and its facts published.

Three decisions carry the whole design, and none of them is about the happy path.

**Presentation generalises rather than duplicates.** 001 built profile, ratings, match history and
match detail scoped to the signed-in user's own linked profiles. This feature widens the scope of
those exact routes to any `profile_id` and adds the authorisation difference on top, rather than
growing a second, parallel presentation that would drift (FR-008, FR-021). Most of US1 and US2 is a
subtraction of ownership checks, not new code.

**Analysis is a request-triggered library, not a job.** FR-044 forbids a scheduled job and a
background sweep, and the platform gives no way to keep working after a response is returned. So
analysis is the ingester's own shape applied to a different unit of work: a library exposing
`run_once(budget_seconds)`, a database row that *is* the queue, a lease that expires, and two thin
entrypoints — one Vercel function reached by a person clicking, and a phase-2 worker loop. Nothing
resumes an interrupted analysis on a timer; the next person who opens that match resumes it. That is
a consequence of FR-044 rather than a compromise around it, and it is why the state machine has to
be honest about `running` meaning "someone was working on this recently", not "work is happening".

**What the recording *states* is narrower than what it *implies*, and this feature ships only the
first.** Phase 0 parsed the committed reference replay and measured it. The command log gives build
and training orders, age-up commands, technologies, unit counts and APM, per participant, from a
single point of view — the spec's central assumption, now verified rather than assumed. Resources and
villager count are not in it: a `.aoe2record` records what a player ordered, never what the game did
in response. They are **reconstructible** from the command stream, and that reconstruction is its own
feature — it needs training durations that vary by civilisation, cancellation handling, and an honest
accuracy claim for the one thing the log can never carry, which is what combat destroyed.
[research.md](./research.md) R1 records the measurement, the shape of the reconstruction, and the one
open question that could shortcut part of it. FR-043 needs a spec amendment, not a workaround.

## Technical Context

**Language/Version**: Python 3.13, TypeScript 5. Unchanged from 001.

**Primary Dependencies**: as 001, plus `aoe2rec-py` promoted from capture-time validation to full
extraction — the same pinned `0.1.21` wheel, in the same isolated package, through a second Protocol.
No new third-party dependency in either language.

**Storage**: PostgreSQL for favourites, analyses, retained recordings, search cache and rate-limit
counters. The same S3-compatible bucket for retained recordings, under a key prefix that keeps them
separable from 001's captures by inspection alone (FR-048).

**Testing**: as 001. The analysis extractor is tested against `tests/fixtures/replays/`'s committed
reference replay, which is the only replay this repository may rely on — the expected timeline is
committed beside it as a golden file so a parser upgrade shows as a diff rather than as a silence.

**Target Platform**: Vercel Functions in `cdg1` plus the static bundle; the same code as a long-lived
process on a VPS (constitution XII).

**Project Type**: Web service with a static front end, in the existing uv + pnpm monorepo.

**Performance Goals**: search results in under 1 s p95 from cache, under 3 s cold. A ranked 1v1
analysed within 60 s of the request (SC-007) — measured at 0.58 s of parse against a 300 s budget,
so the target is dominated by fetching 0.87 MB and by the round trips around it, not by parsing.

**Constraints**:

- **Memory, not time, is what bounds a parse.** The reference 1v1 peaks at ~631 MB resident against
  Vercel's 2 GB, because 484 542 operations are materialised as Python objects. An eight-player game
  is roughly three times the operations. This is the constraint that decides whether a match can be
  analysed at all, and the one that forces FR-036's visible failure to be a real code path rather
  than a formality. See [research.md](./research.md) R3.
- `api/index.py` runs with `maxDuration: 10`. Analysis cannot live behind it and needs its own
  function entry, at 300 s.
- Capture's request budget, its quota and the free storage allowance are reserved before analysis
  sees any of them (FR-039, constitution I).
- One recording is retained per analysis, at ~0.87 MB for a 1v1 and ~2.5 MB for an eight-player
  game, against a 10 GB allowance shared with 001's archive.
- The player-name search source is degradable by design and unverified from the platform's egress
  addresses (`docs/data-sources.md` §3). Nothing but search may depend on it.

**Scale/Scope**: the same closed beta. 5 new tables, 2 extended, 5 user stories, 61 functional
requirements, 1 new application, 1 new provider method, 1 new Vercel function.

## Constitution Check

*GATE: must pass before Phase 0. Re-checked after Phase 1 design — see the note below the table.*

| Principle | How this design satisfies it | Verdict |
| --- | --- | --- |
| **I. Capture outranks analysis** | Analysis is the lowest-priority story, and the ordering is enforced in code rather than intended: an analysis fetch is refused while any capture sits inside its deadline danger window, analysis draws on its own smaller aoe.ms budget beneath capture's, and FR-047's storage cap is set below the allowance so capture keeps headroom it never has to compete for. `expired_total` staying at 0 is SC-008 and is asserted while the feature is in use. | PASS |
| **II. Python backend** | The analyzer is a Python library. The front end gains routes and components and no logic. | PASS |
| **III. DataProvider boundary** | `PlayerSearchProvider` is added to `packages/providers/src/aoe2stats_providers/companion`; recorded games are fetched through 001's existing `aoems` `ReplayProvider`. `apps/analyzer` opens no connection of its own. The search response is *recoverable* — it can be re-queried at any time — so it is cached, not persisted verbatim; a third party's match history is irrecoverable and is persisted verbatim exactly as a user's own (FR-011). | PASS |
| **IV. Raw is sacred** | FR-033 is principle IV applied to a source that destroys its own evidence: the analysed recording is stored byte-for-byte with a checksum and never deleted except on erasure, and every analysis records the parser name and version that produced it, so any published analysis can be recomputed without the source (FR-041, SC-009a). | PASS |
| **V. Pluggable parser** | Extraction is a second Protocol in `packages/core/src/aoe2stats_core/replay/`, implemented in `packages/replay-engine` beside the validator, so `aoc-mgz` can implement it without touching a caller. The API still never loads an engine: analysis runs in its own function, in its own process, and its failure cannot reach the API or the ingester (FR-042). An unparsable recording is quarantined with its full error (FR-036). | PASS |
| **VI. Tokens first** | Every new component comes from a `product-designer` spec and is built from tokens with a story. | PASS |
| **VII. Visual tests** | Diff-scoped Playwright regression on the stories this feature adds. | PASS |
| **VIII. No secrets in the clear** | All new configuration is environment variables with an entry in `.env.example` and no value. No new cron endpoint, so no new shared secret. The analysis function is reachable by a signed-in user and by nobody else. | PASS |
| **IX. GDPR by design** | Constitution IX at 2.0.0 is what makes FR-033 lawful, and it attaches three conditions: FR-045 registers the retention as its own processing purpose with its own legal basis, FR-046 puts it inside erasure and the third-party objection route, FR-047 caps and rate-limits it. FR-012 keeps automatic capture untouched — nothing is captured because a player was searched, viewed or favourited. FR-010 keeps third-party profiles out of any index. Regions unchanged. | PASS |
| **X. Intellectual property** | No game asset. The recorded game is served from the publisher's own source or from this service's archive of it; nothing is redistributed commercially. | PASS |
| **XI. English** | Every artifact here is English. | PASS |
| **XII. Portable by construction** | `apps/analyzer` exposes `run_once(budget_seconds)` and knows nothing about its caller. Its two entrypoints are a ~10-line Vercel function and a ~10-line worker loop, exactly as the ingester's are. No broker, no filesystem state, storage through `packages/storage`. | PASS |

**No violations. Complexity Tracking is empty and stays empty.**

Four points were live decisions rather than automatic consequences, and are recorded because a later
reader would otherwise have to re-derive them from the diff:

- **The queue is claimed by whoever asks, not by a sweeper.** FR-044 forbids a background sweep, and
  the ingester's daily cron may not be widened to collect abandoned analyses — that would be a sweep
  wearing a cron's clothes. So an analysis abandoned mid-parse is resumed by the next person who
  opens that match, and by nothing else. A match nobody returns to stays unanalysed forever, which is
  correct: nobody is waiting for it.
- **`api/analyze.py` is a third platform-shaped file, and it earns its place twice.** It exists
  because `api/index.py` is capped at 10 s, and it is *also* how constitution V's isolation is
  obtained for free — a separate function is a separate process with its own bundle, so a parser
  crash cannot reach the API even in principle. Like the other two it stays under ten lines.
- **Retained recordings get their own table, not a flag on `replay_captures`.** FR-048 asks that the
  two never blur. A boolean on the existing table would make every existing query silently ambiguous
  and every count silently wrong; a separate table makes a query that mixes them impossible to write
  by accident.
- **Search is cached but not persisted verbatim, and the difference is principle III's own.** A name
  search can be re-run at any time, so a stored copy is a second thing to keep honest for no gain.
  A third party's *match history*, read to render their profile, is irrecoverable and is persisted
  verbatim — which FR-011 states plainly is an act with consequences, and why the third-party
  objection route has to cover it.

**Post-design re-check (after Phase 1)**: verdicts unchanged, with three things design surfaced.

**001's FR-038 is superseded by this feature, and the test that asserts it is rewritten rather than
deleted** (decided 2026-08-23; `spec.md` FR-008a records it). 001 stated the property as "there is no endpoint that takes an arbitrary
`profile_id` and returns its history" and built `apps/api/tests/test_no_public_directory.py` (T067,
green today) to hold it across every route. FR-006, FR-007 and FR-008 add exactly those endpoints, so
that reading cannot survive — but it was always stricter than the constitution it was serving.
Constitution IX forbids third-party players being **publicly indexed**, and reachable by a signed-in
beta user is not that. [contracts/http-api.md](./contracts/http-api.md) states the four properties
that replace it — no anonymous reach, no indexing, no account-link disclosure, and ownership still
deciding a user's own archive — and the rewrite is a task in this feature that names what replaced
the old reading. Deleting the file would remove the only executable statement of a constitutional
property; leaving it would turn the suite red for a reason the suite is right about.

**`replay_access_log` could not describe a retained recording.** It FKs to `replay_captures`, so
FR-029's access trail needed either a second log or a widened one.
[data-model.md](./data-model.md) widens the existing table with a nullable second reference and a
check constraint that exactly one is set, because two access logs would be the same blurring FR-048
forbids, one level down: an audit that reads one of them reports a clean trail for a file nobody
checked.

**001's US5 is a prerequisite of US4 here, and of nothing else** (decided 2026-08-23). Export,
erasure and the third-party objection route are T090 to T092, still open, with `routers/privacy.py`
implementing consent and nothing else. FR-033 creates a new category of personal data and
constitution IX requires export and erasure from the MVP, so those three tasks land **before this
feature retains its first third-party recording**. Everything here that retains nothing — search,
profiles, match pages, downloads, favourites — is unaffected and proceeds in parallel. This feature
still builds its own half, and `data-model.md` states per table what erasure must do to it, so the
001 tasks have something to implement against rather than something to remember.

### Configuration this feature introduces

All behavioural, all from the environment, all with a valueless entry in `.env.example`
(constitution VIII):

| Key | Governs |
| --- | --- |
| `FAVOURITES_MAX_PER_USER` | FR-016's bound |
| `PLAYER_SEARCH_CACHE_TTL_SECONDS` | FR-004e |
| `PLAYER_SEARCH_MAX_PER_USER_PER_MINUTE` | FR-005 |
| `REPLAY_DOWNLOAD_MAX_PER_USER_PER_MINUTE` | FR-028 |
| `ANALYSIS_MAX_REQUESTS_PER_USER_PER_DAY` | FR-040 |
| `ANALYSIS_MAX_SOURCE_REQUESTS_PER_DAY` | R7's budget gate — analysis's allowance, below capture's |
| `ANALYSIS_RETENTION_CAP_BYTES` | FR-047's total, set below the free allowance so capture keeps headroom |
| `ANALYSIS_RUN_BUDGET_SECONDS` | the interruptible unit of work, as `INGEST_RUN_BUDGET_SECONDS` is |
| `ANALYSIS_LEASE_SECONDS` | how long a claim survives an invocation that died (R6) |

No key restates a measurement. The retention window, the capture budget and the replay sizes stay
where they are measured, and `obtainable_until` is derived from them (FR-024).

## Project Structure

### Documentation (this feature)

```text
specs/003-player-search-match-analysis/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── http-api.md      # only what this feature adds or widens
│   ├── providers.md     # PlayerSearchProvider, and what the existing ones are asked for
│   └── analysis.md      # the extraction Protocol and the shape of a published analysis
├── checklists/
├── spec.md
└── tasks.md             # Created later by /speckit-tasks
```

### Source Code (repository root)

```text
api/
└── analyze.py                     # Vercel function, maxDuration 300. ~10 lines: authenticates the
                                   # caller, calls run_once(). Not a cron and not reachable by one.
                                   # Resolved by the filesystem before the /api/(.*) rewrite, the
                                   # same way api/cron/ingest.py already is.

apps/
├── analyzer/src/aoe2stats_analyzer/
│   ├── run.py                     # run_once(budget_seconds) — claim, fetch, retain, extract, publish
│   ├── admission.py               # the FR-039 gate: capture's deadlines, budgets and storage first
│   ├── claim.py                   # lease acquisition and expiry; FOR UPDATE SKIP LOCKED, as 001
│   ├── retain.py                  # checksum, store, record — FR-033's byte-for-byte half
│   ├── extract.py                 # engine Protocol -> published analysis; no engine import here
│   └── worker.py                  # [phase 2] loop calling run_once()
├── api/src/aoe2stats_api/routers/
│   ├── players.py                 # search, any profile, any profile's ratings and history
│   ├── favourites.py              # list, mark, unmark
│   ├── matches.py                 # widened: /matches/{game_id} loses its ownership scope
│   ├── replays.py                 # widened: per-participant availability and download
│   └── analysis.py                # request, state and result. Never the work itself
└── web/src/
    ├── routes/                    # search, players.$profileId, players.$profileId.matches,
    │                              # favourites; matches.$gameId gains both CTAs
    └── features/{search,players,favourites,analysis}/

packages/
├── core/src/aoe2stats_core/replay/
│   └── analysis.py                # the extraction Protocol and its value objects. No engine.
├── replay-engine/src/aoe2stats_replay_engine/
│   └── aoe2rec.py                 # gains extract(); the Build decoder R4 describes lives here,
                                   # beside the parser whose gap it closes
├── providers/src/aoe2stats_providers/companion/
│   └── provider.py                # gains search_profiles, behind the same circuit breaker,
                                   # stripping the account-linking fields at the boundary (FR-004b)
└── design-system/                 # search box and result row, favourite toggle, participant table,
                                   # per-point-of-view availability list, analysis timeline and
                                   # its progress state — specs first, then components with stories

infra/migrations/                  # one migration: 5 tables, 2 widened
tests/fixtures/replays/            # gains the golden extraction of the committed reference replay
```

**Structure Decision**: the 001 monorepo, with one new application and one new platform-shaped file.
`apps/analyzer` is created here rather than the `apps/parser` 001 deliberately did not create,
because the unit of work is different from what that name implied: this is not a parse queue over
the archive, it is one match, on request, with retention attached. It sits beside `apps/ingester`
and shares its shape — a library with `run_once(budget_seconds)`, a database-backed queue, a lease,
and two thin entrypoints — so that constitution XII holds without a second pattern to learn.

No new package is created. Extraction goes into `packages/replay-engine`, beside the validator that
already loads the same engine, because a second package would give the engine a second place to be
imported from and constitution V's containment is exactly the property that must not have two homes.

## Complexity Tracking

No constitutional violations. Nothing to justify.
