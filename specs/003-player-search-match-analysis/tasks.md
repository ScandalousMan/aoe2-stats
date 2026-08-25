---
description: 'Task list for player search, favourites and on-demand match analysis'
---

# Tasks: Player Search, Favourites and On-Demand Match Analysis

**Input**: Design documents from `/specs/003-player-search-match-analysis/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included and mandatory. The eleven live scenarios in [quickstart.md](./quickstart.md) — scenario 3 is retired — are the
source, and every test task names the scenario it encodes. A test task is done when the test exists
**and fails for the right reason**, carrying `@pytest.mark.xfail(strict=True, reason="<id> not
implemented yet")` with the module under test imported *inside* the test body; the implementing task
removes the marker, which `strict=True` forces rather than merely permits.

**Organization**: grouped by user story. US1, US2, US3 and US5 are independent of each other once the
foundation is in. US4 depends on US2 for the page it lives on, and on a gate outside this feature —
see below.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel — different files, no dependency on an incomplete task
- **[Story]**: US1..US5, mapping to the user stories in [spec.md](./spec.md)
- Every task names its exact file path

## Path Conventions

Per [plan.md](./plan.md): `api/`, `apps/{api,analyzer,web}/`,
`packages/{core,providers,replay-engine,storage,design-system}/`, `infra/migrations/`,
`scripts/checks/`, `docs/`, `tests/fixtures/replays/`.

## Numbering starts at T301, deliberately

001 reaches T108 and 002 runs T201 to T215. Ids resolve **across** features since T202, so they have
to be unique across features. This feature's artifacts cite 001's T067, T090, T091, T092 and T070c by
bare number, and 002's T210, because the judgment behind each is why a decision here went the way it
did. A disjoint range costs nothing and removes the ambiguity permanently.

## The gate that is not a task in this file

**001's T090, T091 and T092 — export, erasure and the third-party objection route — land before
Phase 7 (US4) retains its first third-party recording.** Decided 2026-08-23; `spec.md`'s Assumptions
and [research.md](./research.md) R14 carry the reason. FR-033 creates a new category of personal data
and constitution IX requires export and erasure from the MVP, so retaining a stranger's recording
while no erasure route exists breaks the principle for the duration.

They are not repeated here because they belong to another feature and duplicating them would make
"who owed this" unanswerable. Phase 7 states the gate; T382 walks it.

FR-017 and FR-046 are *implemented* by those three tasks and *verified* by T382. What this feature
owes is that they know about its tables, which [data-model.md](./data-model.md) states per table and
001's T090 and T091 now name explicitly — a decision recorded in both files rather than remembered in
one.

**001's T100 — the free-tier watch — lands before T378 extends it.** `scripts/checks/free_tier_watch.py`
does not exist and `.github/workflows/nightly.yml` carries the job commented out behind
`TODO(feature-1): enable once T100 lands`. T378 says "extend" and there is nothing to extend yet. This
is the second gate outside this file, and it is cheaper than the first: it blocks one polish task, not
a user story. SC-009's total-cap monitoring and the plan's "cap set below the allowance so capture
keeps headroom" both read out of it.

## Scenario coverage map

| quickstart scenario | Story | Task(s) that encode it |
| --- | --- | --- |
| 1 — Search degrades honestly | US1 | T314, T317, T381 |
| 2 — Nothing leaks an account link | US1 | T312, T381 |
| 3 — *retired: no hidden signal exists (T301a)* | — | — |
| 4 — Any player's profile and history | US1, US2 | T317, T325 |
| 5 — The match page is complete at any age | US2 | T324, T333 |
| 6 — Downloads, per point of view | US3 | T335, T343 |
| 7 — The analysis runs once, and says what it found | US4 | T364, T381 |
| 8 — Everything that can go wrong with an analysis | US4 | T364, T381 |
| 9 — Capture always wins | US4 | T358, T381 |
| 10 — Recomputation without the source | US4 | T364 |
| 11 — Favourites, and what they must not cause | US5 | T344, T345, T381 |
| 12 — Data rights cover what this feature added | US4, US5 | T382 |

T333, T343, T381 and T382 are the human walks; everything else is an automated test. This map is
derived from each task's own "encoding quickstart scenario N" clause and must stay derived from it —
`spec_lint.py` checks that every id here exists, never that it is the right one.

---

## Phase 1: Setup

**Purpose**: the two things every later phase assumes exist, plus the one measurement Phase 3 rests
on and nobody has taken.

- [x] T301 Add this feature's ten configuration keys to `.env.example`, **each carrying its tuned default value and a comment saying what it governs and where the number comes from** — and read them in `apps/api/src/aoe2stats_api/settings.py`, extending `apps/api/tests/test_settings.py` with a case per key — and `apps/api/tests/conftest.py`, whose required-environment drift guard (T015b) asserts at import time that its key set equals `.env.example`'s, so adding a key here without adding it there turns the whole API suite red before a single test runs: `FAVOURITES_MAX_PER_USER`, `PLAYER_SEARCH_CACHE_TTL_SECONDS`, `PLAYER_SEARCH_MAX_PER_USER_PER_MINUTE`, `REPLAY_DOWNLOAD_MAX_PER_USER_PER_MINUTE`, `ANALYSIS_MAX_REQUESTS_PER_USER_PER_DAY`, `ANALYSIS_MAX_SOURCE_REQUESTS_PER_DAY`, `ANALYSIS_RETENTION_CAP_BYTES`, `ANALYSIS_RUN_BUDGET_SECONDS`, `ANALYSIS_LEASE_SECONDS`, `ANALYSIS_MAX_RAW_BYTES`. No key restates a measurement — the retention window, the capture budget and the replay sizes stay in `docs/data-sources.md`, and `obtainable_until` is derived from them (FR-024), and `ANALYSIS_MAX_RAW_BYTES` is a budget derived from R3's measured amplification rather than a restatement of it. **Until this task lands, `scripts/checks/spec_lint.py` reports ten `env-declared` failures for this feature and that is the expected state, not a defect**: the artifacts name the keys and `.env.example` does not carry them yet. This is the one task that closes all ten, so it goes first.

**Two corrections to how this task was first written, both settled 2026-08-23 by reading the file and the linter rather than the prose.** *They carry values, not blanks*: constitution VIII's "`.env.example` without values" is about secrets, and this file already reads it that way — `CRON_SECRET`, `STEAM_API_KEY` and the S3 credentials are blank while every key in `Ingestion tuning` carries its tuned number with the reasoning above it. All ten of these are tuning, none is a secret. A blank would also *disable a check*: `spec_lint.py`'s `literals` check reads each behavioural key's value and skips any that is not a digit, so a valueless `ANALYSIS_MAX_RAW_BYTES` would silently stop anyone from being caught hard-coding 24 MB.

*They need a section the linter recognises*: `spec_lint.py` decides "behavioural" by one literal section header, `Ingestion tuning`, and these keys do not belong under it — none of them tunes ingestion. Add them under their own `# --- Search, favourites and analysis tuning ---` header **and widen that check in the same task** to treat any `# ---` section whose header ends in `tuning` as behavioural, with a case in `scripts/checks/tests/`. The two halves ship together on purpose: landing the keys without the widening leaves ten keys that `env-consumed` and `literals` both stop seeing, with nothing anywhere saying so — which is the exact shape of gap this repository keeps writing tasks to close
- [x] T301a [P] Measure whether `GET https://data.aoe2companion.com/api/profiles?search=` carries a hidden-profile signal at all — which field, which values mean hidden, and how to find such a profile in order to fixture it — and record the answer in `docs/data-sources.md` §3's measured record row. FR-004c, `aoe_profiles.hidden_observed_at`, [contracts/providers.md](./contracts/providers.md)'s drop-and-report clause, T311's second fixture and T312's and T314's assertions all rest on this field, and §3's measured record list — `profileId`, `name`, `country`, `games`, `drops`, `clan`, `avatarhash`, `verified`, `platform`, social links — does not contain it. [research.md](./research.md) R11 says this source's properties are "settled and measured"; this is the one that is not. **If no such signal exists, stop and amend FR-004c rather than implementing around it**: honouring a flag the source does not send is a test that passes against a fixture we invented, which is the failure `docs/` exists to make impossible. Blocks T311, T312 and T314. **Outcome, 2026-08-23: no signal exists** — `hidden` is null in 200 of 200 records, typed `any`, written by no setting and read by no consumer in the source's own client. Recorded in `docs/data-sources.md` §3; FR-004c retired; the three blocked tasks lost that assertion rather than gaining it
- [x] T302 Create the `apps/analyzer` workspace member: `apps/analyzer/pyproject.toml` modelled on `apps/ingester/pyproject.toml`, an empty `apps/analyzer/src/aoe2stats_analyzer/__init__.py`, an `apps/analyzer/tests/` directory, registration in the root `pyproject.toml` workspace members and `uv.lock` refreshed. **Declare `aoe2stats-replay-engine` as a dependency here, and make `apps/analyzer` the only application that *extracts* with it.** It is not the only one that declares it, and it must not try to be: `apps/api/pyproject.toml` already declares it deliberately, because `apps/api` depends on `apps/ingester` for the local cron trigger route and the ingester needs the engine for its capture-time validator. Do not remove that declaration — it is load-bearing and 001 reasoned it out.

What constitution V actually buys here is that **importing the ASGI app never loads a C extension**, and the dependency graph cannot state that: a declared dependency says nothing about when it is imported. 001 enforces it where it is provable — a lazy, function-scope import (`apps/api/src/aoe2stats_api/ingest_stages.py`, with its own comment) plus `apps/api/tests/test_engine_isolation.py` (T018c), which asserts it **in a subprocess** because an in-process check has two documented ways to lie. Extend that test to the boundary this feature adds: importing `aoe2stats_api.app` must not pull in `aoe2stats_analyzer` either. No logic in this task beyond the test extension

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the schema, the two mechanisms every route needs, and the one existing test that this
feature's first route would otherwise turn red for a reason the test is right about.

**⚠️ CRITICAL**: no user story work begins until this phase is complete.

- [x] T303 [P] Write the model tests for this feature's schema in `packages/storage/tests/test_models.py`, each `@pytest.mark.xfail(strict=True, reason="T304 not implemented yet")`, importing the models inside the test body: `favourites` idempotent under its composite primary key; `profile_search_cache` keyed on the normalised query; `match_analyses` unique on `game_id` **and asserted to reject a second row for the same match**, which is the whole of FR-031 and FR-038; `retained_recordings` unique on `(game_id, profile_id)`; `rate_limit_counters` on its three-column key; `aoe_profiles.alias_observed_at` and no `hidden_observed_at` (T301a retired FR-004c; a column nothing can set must not be created); and `replay_access_log`'s check constraint accepting exactly one of `replay_capture_id` / `retained_recording_id` and **rejecting both-set and neither-set**. The constraint's two negative cases are the task: a nullable pair without them is a row that can mean nothing, and an access log whose rows can mean nothing reads as evidence while being none
- [x] T304 Add the five new models and the two widened ones to `packages/storage/src/aoe2stats_storage/models.py` per [data-model.md](./data-model.md), and remove T303's markers. Add `analysis_cap_reached` to `AlertKind` (severity 2) and nothing else — a per-match parse failure is an expected outcome of R3's memory bound, not an incident, and must not become an alert kind
- [x] T305 **Lands in the same commit as T304 — the two are never separately green.** `tests/db.py` builds the test schema by running the real migrations, never `Base.metadata.create_all`, so T304's models without this migration mean every database-touching test errors on a missing relation (191 of them, measured 2026-08-23). That is not a defect in T304 and must not be chased in the models or the harness; it is what `CLAUDE.md` means by "the smallest set of tasks that was ever simultaneously green". Write the single Alembic migration in `infra/migrations/` for everything T304 added, and confirm `uv run alembic check` reports no drift. One migration, not five: [data-model.md](./data-model.md) says so, and a partially-applied schema is the one state none of the later phases can recover from
- [x] T306 [P] Write the fixed-window rate-limit tests in `apps/api/tests/test_rate_limits.py`, `xfail(strict=True, reason="T307 not implemented yet")`: a counter increments per `(user_id, bucket, window)`, a window boundary resets it, exceeding the bound returns the remaining seconds, and two users never share a window. Add the case that matters on this platform: **two separate calls with no shared process still see the same count**, because an in-memory counter would pass every other assertion here and count nothing in production (R10)
- [x] T307 Implement `apps/api/src/aoe2stats_api/ratelimit.py` — fixed windows, upsert-incremented, rows older than the longest window pruned opportunistically on write so the table stays bounded without a job (FR-044) — and remove T306's markers
- [x] T308 [P] Write the response-header tests in `apps/api/tests/test_no_index_headers.py`, `xfail(strict=True, reason="T309 not implemented yet")`: every route this feature adds answers `X-Robots-Tag: noindex, nofollow` and `Cache-Control: private`, and 001's existing routes are unchanged. Parameterise over the route table rather than listing routes by hand, so a route added later without the header fails this test instead of quietly shipping
- [x] T309 Implement the header middleware in `apps/api/src/aoe2stats_api/app.py` and remove T308's markers. It is middleware and not a per-route decorator for the reason T308 tests: FR-010 must hold for the route somebody forgets
- [x] T310 Rewrite `apps/api/tests/test_no_public_directory.py` against FR-008a, and record in its docstring what replaced the old reading and why. 001's FR-038 said no endpoint returns an arbitrary profile's history; this feature supersedes it and narrows it to constitution IX's actual line — never *publicly indexed*. **Keep live** the assertions that survive: `GET /api/matches?profile_id=` and `GET /api/profiles/{profile_id}/ratings` stay owner-scoped, because `/api/profiles/*` means "mine" and `/api/players/*` means "anyone" — that split is what keeps the blast radius to one route. **Replace** the `/api/matches/{game_id}` assertion with the four properties from [contracts/http-api.md](./contracts/http-api.md): no anonymous reach, no indexing, no account-link disclosure on any profile (FR-009, 001 FR-045), ownership still deciding a user's own archived replay. The new assertions carry `xfail(strict=True)`, **one marker per property and never one for the file**, naming T319 (the players routes), T327 (the match-detail widening), T328 (any profile's history) and T337 (the download route, where ownership still decides a user's own archive). Not T339: that task writes a component spec and can make no assertion here pass. Never delete this file — it is the only executable statement of a constitutional property, and a decision that retires a rule has to leave its reason where the next reader will find it

**Checkpoint**: schema, rate limits, headers and the superseded-rule test are in. Stories can start.

---

## Phase 3: User Story 1 — Find any player and see where they stand (Priority: P1) 🎯 MVP

**Goal**: type a name, pick a player, land on their profile with their standing on every ladder.

**Independent Test**: search a known active player by name, open the top result, and confirm the
ratings match the official leaderboard for that player.

### Tests and fixtures for User Story 1

- [x] T311 [P] [US1] Freeze a real search response as a fixture in `packages/providers/fixtures/companion_profiles_search.json`, captured from `GET https://data.aoe2companion.com/api/profiles?search=` for a common substring. **Keep `steamId`, `shared` and `sharedHistory` in the fixture exactly as the source sends them** — T312 asserts they never come out the other side, and a sanitised fixture would make that test pass while proving nothing. Add a second fixture for an empty result. **No hidden-profile fixture**: T301a measured the source and found no hidden signal, so such a fixture could only be one we invented, which is the thing that would make T312 pass while proving nothing
- [x] T312 [P] [US1] Write the provider tests in `packages/providers/tests/test_companion.py`, `xfail(strict=True, reason="T313 not implemented yet")`, encoding quickstart scenario 2: `search_players` returns only the five contract fields; the account-linking fields are absent from the returned objects **and from the dataclass definition itself**, asserted by field introspection so a later refactor that adds one fails here (FR-004b); a 403, a 5xx and a malformed body each yield an empty page and **never raise** (FR-003's precondition); and the circuit breaker is the same instance `enrich_matches` uses, asserted by tripping it through one method and observing the other
- [x] T313 [US1] Implement `search_players` plus `PlayerSearchResult` and `PlayerSearchPage` per [contracts/providers.md](./contracts/providers.md), in `packages/providers/src/aoe2stats_providers/companion/provider.py` and `packages/providers/src/aoe2stats_providers/base.py`, and remove T312's markers. Reuse the existing token bucket and breaker rather than adding new ones — two breakers would each see half the failures and neither would trip
- [x] T314 [P] [US1] Write the search-service tests in `apps/api/tests/test_player_search.py`, with markers split by implementing task and never one reason for the file — the cache, the normalisation and the `degraded` signal carry `xfail(strict=True, reason="T315 not implemented yet")`, and the three fallback cases carry `reason="T316 not implemented yet"` — encoding quickstart scenario 1: a repeated query hits the cache and produces one `provider_calls` row, not two (FR-004e); query normalisation collapses case, whitespace and Unicode form; with the source unavailable the fallback searches `aoe_profiles` and returns `degraded: true` (FR-004d); the fallback orders most-played first, like the source does; the fallback withholds no profile on privacy grounds, because there is no signal to withhold on (T301a retired FR-004c); and **a write past the TTL removes stale rows**, asserted by seeding an expired entry and counting rows after an unrelated query — the cache is the one table here that grows with the variety of what people search rather than with how often, and nothing else bounds it
- [x] T315 [US1] Implement the search service in `apps/api/src/aoe2stats_api/search.py`: query normalisation, `profile_search_cache` read and write with the configured TTL, deletion of entries past that TTL opportunistically on write so the table stays bounded without a job (FR-044), and the `degraded` signal derived from the provider's breaker state rather than from an exception, and remove T314's T315-reasoned markers. `strict=True` turns the tree red here if they stay, and the `SubagentStop` gate refuses that hand-back
- [x] T316 [US1] Implement the local fallback over `aoe_profiles` in the same module, and remove T314's T316-reasoned markers. It introduces no source and no request — `aoe_profiles` already holds every participant of every match this service has seen, populated by 001's discovery
- [x] T317 [P] [US1] Write the route tests in `apps/api/tests/test_players_routes.py`, `xfail(strict=True, reason="T319 not implemented yet")`, encoding quickstart scenarios 1 and 4: `GET /api/players/search` finds a player by display name with no numeric identifier known (FR-001) and distinguishes found / found-nothing / degraded and **asserts the second and third are distinguishable from the response alone**, which is FR-003 and the thing a client branching on `results.length` gets wrong; the per-user rate limit answers `rate_limited` with `retry_after` (FR-005), so search cannot enumerate the source at volume through this service; `GET /api/players/{profile_id}` returns rating, rank, wins and losses per ladder (FR-006) and answers `200` with empty ladder data for a never-ranked player and `404` for a hidden one and for an unknown one; and `GET /api/players/{profile_id}/ratings` returns history where snapshots exist. Every case asserts the `X-Robots-Tag` header (FR-010)

### Implementation for User Story 1

- [x] T318 [P] [US1] Write the component specs for the search box, the search result row and the third-party profile header in `packages/design-system/specs/`, carrying country and current standing per result so near-identical names stay tellable apart (FR-002), and including the three empty states the interface must keep distinguishable — no query yet, no match, and search degraded — since T317 only proves the API distinguishes them and constitution VI wants the interface to as well
- [x] T319 [US1] Implement `apps/api/src/aoe2stats_api/routers/players.py` with the three routes, registered in `app.py`, and remove T317's markers and the matching ones T310 left. Name the leaderboards with the existing `leaderboards.py` mapping and the civilisations with `civilizations.py`, exactly as 001's routes do (T033a, T070c) — this feature adds no naming of its own
- [x] T320 [P] [US1] Build `SearchBox` and `PlayerResultRow` from tokens in `packages/design-system/src/components/`, each with its `*.stories.tsx` and `*.test.tsx`, covering the three empty states
- [x] T321 [US1] Extend `packages/design-system/src/components/ProfileSummary/` to present a third party's profile through the same component the user's own profile uses, with stories for both. FR-008 forbids a second, divergent presentation, and the way to not build one is to not create a second component
- [x] T322 [US1] Wire the search and the profile in `apps/web/src/features/search/` and `apps/web/src/features/players/`, with `apps/web/src/routes/search.tsx` and `apps/web/src/routes/players.$profileId.tsx`, and add both to `apps/web/public/robots.txt` as disallowed (FR-010)
- [x] T323 [US1] Run `visual-reviewer` locally, then `pnpm test:visual --changed` over the stories T320 and T321 added, updating baselines in `packages/design-system/__screenshots__/` only where the change is intended (constitution VII)

**Checkpoint**: a user can find any player by name and read their standing. This is the MVP.

---

## Phase 4: User Story 2 — Read any match without the recorded game (Priority: P2)

> **⚠️ Gate, added 2026-08-23 after Phase 3's review: T384 lands before the first route in this phase.**
> `app.py`'s no-index middleware matches a hand-maintained list of path prefixes, and
> `test_no_index_headers.py` asserts that any route *outside* that list must **not** carry the header.
> So a new route is not merely unprotected by default — the suite actively ratifies it. T327, T328,
> T337, T346 and T368 each add one. Five chances to forget a constitution IX property, with the test
> agreeing every time. Inverting the default costs one task now and gets more expensive every phase.

**Goal**: any player's match history, and a match page complete for a match of any age.

**Independent Test**: open a match from a third party's history older than the retention window and
confirm the page is complete and correct, with both CTAs correctly shown as unavailable.

### Tests for User Story 2

- [x] T324 [P] [US2] Extend `apps/api/tests/test_match_detail.py` with the widening, `xfail(strict=True, reason="T327 not implemented yet")`, encoding quickstart scenario 5: any signed-in caller reads any match this service holds, with every participant's team, civilisation, result and rating change plus map, ladder, version, start time and duration (FR-018); the whole page renders from stored match data and never from a recording, so it is complete for a match of any age (FR-019); a match the caller played themselves also carries their own replay's archival state (FR-022); the response is identical whichever participant's history it was reached from, asserted by comparing two responses rather than by inspecting fields; one `matches` row exists for a match reachable from two histories (FR-021); an unnameable civilisation or map yields the raw identifier and a null name, never a guess (FR-020). **Keep the existing ownership assertions for `GET /api/matches?profile_id=` untouched** — that route stays owner-scoped and this task must not widen it
- [x] T325 [P] [US2] Write the history-route tests in `apps/api/tests/test_players_history.py`, `xfail(strict=True, reason="T328 not implemented yet")`, encoding quickstart scenario 4: `GET /api/players/{profile_id}/matches` returns newest first with opponent, map, civilisation, result, rating change and duration (FR-007); a player with no matches yields a clear empty state rather than an error; and the row shape is the one `GET /api/matches` already returns, asserted against it rather than restated
- [x] T326 [P] [US2] Write the verbatim-persistence test in `apps/api/tests/test_third_party_history.py`, `xfail(strict=True, reason="T328 not implemented yet")`: reading a third party's history persists the provider's response into `matches.raw_payload` **unmodified**, exactly as 001 does for a user's own (FR-011, constitution III). Assert the stored payload is **structurally equal to the source's per-match object, with no field dropped, renamed, reordered away or coerced** — walked recursively rather than spot-checked, and compared against the fixture's own match object rather than the whole response body. Byte equality is not the claim available here, and asking for it would force the implementer to weaken something: `matches.raw_payload` is `JSONB`, which normalises key order, whitespace and numeric form on write, and the fixture is a multi-match response while the column holds one match (`RawMatch.raw_payload`). 001's own equivalent is `test_shared_match.py`'s dict comparison, for the same reason. What must be caught is a *transformation* — after 31 days there is nothing left to re-fetch and correct it from

### Implementation for User Story 2

- [x] T327 [US2] Remove the ownership scope from `get_match_detail` in `apps/api/src/aoe2stats_api/routers/matches.py`, leaving `list_matches` owner-scoped, and remove T324's markers and the matching one T310 left. There is no `?from_profile_id=` parameter and none may be added: a parameter that could change the presentation is one that eventually will (FR-021)
- [x] T328 [US2] Implement `GET /api/players/{profile_id}/matches` in `apps/api/src/aoe2stats_api/routers/players.py`, persisting the source response verbatim, and remove T325's and T326's markers and the matching one T310 left
- [ ] T329 [P] [US2] Write the component specs for the full participant table and the third-party history list in `packages/design-system/specs/`, including how an unnamed identifier is shown so it reads as unresolved rather than as a name
- [ ] T330 [US2] Extend `packages/design-system/src/components/MatchDetailPanel/` to present every participant with team, civilisation, result and rating change, with stories covering a 1v1, an eight-player game, and a match carrying an unnameable identifier
- [ ] T331 [US2] Wire the history and the widened match page in `apps/web/src/features/players/` and `apps/web/src/features/matches/`, with `apps/web/src/routes/players.$profileId.matches.tsx`, and widen `apps/web/src/routes/matches.$gameId.tsx` to any match
- [ ] T332 [US2] Run `visual-reviewer` locally, then `pnpm test:visual --changed` over the stories T330 added, updating baselines in `packages/design-system/__screenshots__/`
- [ ] T333 [US2] Walk scenario 5 of `specs/003-player-search-match-analysis/quickstart.md` by hand against a real match older than 31 days, and record the outcome in the pull request. This is US2's independent test and the one thing no fixture proves: that the page is complete when everything else about that match is gone, with no field left blank or wrong for 100% of the matches in that profile's history (SC-003)

**Checkpoint**: any player's matches are readable, at any age, without a recording.

---

## Phase 5: User Story 3 — Get the recorded game, from any point of view (Priority: P3)

**Goal**: one download per participant, each stating plainly whether it is still obtainable.

**Independent Test**: open a recent third-party match, download two different participants' points of
view, and confirm both open in the game and show it from the expected player's side.

### Tests for User Story 3

- [ ] T334 [P] [US3] Write the availability-derivation tests in `apps/api/tests/test_replay_availability.py`, `xfail(strict=True, reason="T336 not implemented yet")`: the four FR-025 states derive from the match's completion time, a `replay_captures` row and a recorded 404, per the table in [research.md](./research.md) R8; **a `retained_recordings` row is not an input and must be asserted not to be** — R8 decides that a recording retained because somebody analysed the match is not an archive the caller may download, so a match whose only copy is retained renders as `expired` with an analysis available, and an implementation that "helpfully" offers it redistributes a third party's recording with no legal basis; `obtainable_until` derives from the measured window in `docs/data-sources.md` and appears in no constant of ours; and — the assertion this task exists for — **deriving availability issues no outbound request at all**, asserted against the provider call sink. `HEAD` answers `405` and `Range` is ignored, so a probe is a full download, and probing on render would be browsing-driven bulk reading of third-party recordings
- [ ] T335 [P] [US3] Write the download-route tests in `apps/api/tests/test_replay_download.py`, with markers split by implementing task — "one download is offered per participant point of view" is the match-detail `replay` object and carries `xfail(strict=True, reason="T338 not implemented yet")`, every other case here carries `reason="T337 not implemented yet"` — encoding quickstart scenario 6: one download is offered per participant point of view (FR-023); an `archived` point of view is served from the archive with a `replay_access_log` row (FR-026, FR-029); an `obtainable` one is streamed and **stores nothing** — zero new objects and zero `retained_recordings` rows, asserted rather than assumed (FR-027); `expired` and `never_recorded` answer `404` with distinguishable codes; the per-user rate limit applies and a source 403 or 429 stops the request and raises a `rate_limited` alert rather than being retried through (FR-028, 001 FR-021); and a point of view offered as obtainable that 404s at fetch time answers `expired_since_page_load`, distinct from `never_recorded`, and records the outcome so the page is right next time

### Implementation for User Story 3

- [ ] T336 [US3] Implement the derivation in `apps/api/src/aoe2stats_api/availability.py` and remove T334's markers. It is a pure function over rows and a clock — no provider, no I/O — which is what makes T334's no-request assertion structural rather than incidental
- [ ] T337 [US3] Implement `GET /api/matches/{game_id}/replay/{profile_id}` in `apps/api/src/aoe2stats_api/routers/replays.py` with its four behaviours, its rate limit and its access log, and remove T335's T337-reasoned markers and the matching marker T310 left (ownership still decides a user's own archived replay). On a throttling or refusal signal from the source, stop and raise 001's existing `rate_limited` alert — this is FR-028's second half and no other task carries it, and it reuses 001's `AlertKind` so T304's "add `analysis_cap_reached` and nothing else" is unaffected
- [ ] T338 [US3] Wire the per-participant `replay` object into the match-detail response in `apps/api/src/aoe2stats_api/routers/matches.py`, with `download_path` and `obtainable_until` **null** for the two unobtainable states, and remove T335's T338-reasoned marker. The nulls are the requirement: FR-025 forbids presenting an unobtainable download as an action that then fails, and a null path is what makes rendering one impossible rather than discouraged
- [ ] T339 [P] [US3] Write the component spec for the per-point-of-view availability list in `packages/design-system/specs/`, covering all four states and the remaining-time countdown, and stating how `expired` differs visually from `never_recorded` — FR-025 wants the difference visible, not merely present in the payload
- [ ] T340 [US3] Build the component in `packages/design-system/src/components/`, reusing `packages/design-system/src/components/CaptureStateBadge/countdown.ts` rather than writing a second countdown, with stories for all four states and for a match hours from its boundary
- [ ] T341 [US3] Wire the downloads into the match page in `apps/web/src/features/replays/`
- [ ] T342 [US3] Run `visual-reviewer` locally, then `pnpm test:visual --changed` over the stories T340 added, updating baselines in `packages/design-system/__screenshots__/`
- [ ] T343 [US3] Walk scenario 6, points 2 and 4, of `specs/003-player-search-match-analysis/quickstart.md` by hand — two points of view opened in AgeII:DE, and a match you played whose own point of view is archived while the others have expired — and record the outcome in the pull request. Confirm that the availability stated for every point of view matches what the source actually answers at that moment (SC-004), and that obtaining any one of them takes at most two actions from the match page (SC-005)

**Checkpoint**: every participant's recording is reachable while it exists, and honestly described when it is not.

---

## Phase 6: User Story 5 — Keep the players I care about close (Priority: P5)

**Goal**: mark any player as a favourite and find them again from one list.

**Independent Test**: favourite two players, sign out and back in, confirm both are listed with their
current standing and reachable in one click.

> Placed before US4 despite its lower priority. It depends only on Phase 2 and on US1's profile page,
> it is the cheapest thing in the feature, and US4 is blocked on a gate outside it. Shipping it here
> costs nothing and stops the queue idling behind another feature's work.

### Tests for User Story 5

- [ ] T344 [P] [US5] Write the favourites route tests in `apps/api/tests/test_favourites.py`, `xfail(strict=True, reason="T346 not implemented yet")`, encoding quickstart scenario 11: `PUT` twice is one row and two `200`s and `DELETE` is idempotent, so a player can be marked and unmarked (FR-013); the list carries each player's current standing and links to their profile in one step (FR-014); the per-user bound answers `favourites_limit_reached` (FR-016); an unauthenticated call answers `sign_in_required` (US5 scenario 5); and one user never sees another's favourites (FR-015). Add the assertion that has no route to test: **grep the router module for any aggregate over `profile_id`** and fail if one exists — "how many people follow this player" is a question this system must not be able to answer, and the only way to test an absence is to test for it
- [ ] T345 [P] [US5] Write the no-capture test in `apps/ingester/tests/test_favourite_no_capture.py`, `xfail(strict=True, reason="T346 not implemented yet")`: favouriting a player enqueues no capture, ingests nothing and archives nothing, asserted across a full `run_once` after the favourite exists (FR-012, US5 scenario 4). Capture remains what 001 defines it as — the consenting user's own point of view — and a favourite is a bookmark

### Implementation for User Story 5

- [ ] T346 [US5] Implement `apps/api/src/aoe2stats_api/routers/favourites.py` with `GET`, `PUT` and `DELETE`, registered in `app.py`, and remove T344's and T345's markers
- [ ] T347 [P] [US5] Write the component specs for the favourite toggle and the favourites list in `packages/design-system/specs/`, including the signed-out state that prompts sign-in without losing the user's place
- [ ] T348 [US5] Build the toggle and the list from tokens in `packages/design-system/src/components/`, with stories including the at-the-bound and signed-out states
- [ ] T349 [US5] Wire favourites in `apps/web/src/features/favourites/`, with `apps/web/src/routes/favourites.tsx` and the toggle on the profile page, returning the user where they were after a sign-in prompt
- [ ] T350 [US5] Run `visual-reviewer` locally, then `pnpm test:visual --changed` over the stories T348 added, updating baselines in `packages/design-system/__screenshots__/`

**Checkpoint**: US1, US2, US3 and US5 are complete. The product is useful without any analysis at all.

---

## Phase 7: User Story 4 — Analyse a game, once (Priority: P4)

**Goal**: one match, parsed once, its facts published to everyone who opens it, and its recording kept
so the conclusion can always be re-derived.

**Independent Test**: analyse a recent match, confirm the result appears; open the same match as a
different user and confirm the analysis is shown immediately and was not recomputed.

> **⚠️ Gate**: 001's T090, T091 and T092 — export, erasure and the third-party objection route — land
> before T361 retains the first third-party recording. Everything up to T360 retains nothing and may
> proceed while they are in flight. See "The gate that is not a task in this file" above.

### The engine, and what it may be asked

- [ ] T351 [P] [US4] Write the extraction-Protocol tests in `packages/core/tests/test_replay_analysis.py`, `xfail(strict=True, reason="T352 not implemented yet")`: `MatchTimeline` and `ParticipantTimeline` carry exactly the fields in [contracts/analysis.md](./contracts/analysis.md), asserted by field introspection. The negative half is the task: **no field named for resources, and none named `villagers` or `villagers_trained`** (FR-043b). The value object is where the misreading would enter, and a field that does not exist cannot be populated by a well-meaning later change
- [ ] T352 [US4] Define the `ReplayExtractor` Protocol and its value objects in `packages/core/src/aoe2stats_core/replay/analysis.py`, beside the existing `ReplayValidator`, importing no engine, and remove T351's markers (constitution V)
- [ ] T353 [P] [US4] Write the `Build`-decoder tests in `packages/replay-engine/tests/test_aoe2rec.py` against the committed reference replay, `xfail(strict=True, reason="T354 not implemented yet")`: the 326 `Build` actions decode to a `player_id` and a building identifier each. R4 measured that the pinned wheel returns `{"action_length": 36, "data": [...]}` with **no `player_id` field at all**, contradicting ADR-0001's reading — the decoding is this repository's job, and the byte offsets are what this test pins
- [ ] T354 [US4] Implement the `Build` decoder in `packages/replay-engine/src/aoe2stats_replay_engine/aoe2rec.py` and remove T353's markers. It lives behind the Protocol, not in `apps/analyzer`: it is knowledge about one engine's output format, and constitution V wants that knowledge swappable with the engine
- [ ] T355 [US4] Implement `extract()` in the same module, satisfying `ReplayExtractor`, and generate the golden timeline at `tests/fixtures/replays/AgeIIDE_Replay_500546441.timeline.json`. Reuse the existing `_well_formed_member` / `_read_bounded` extraction-safety path rather than repeating it — two copies of a safety check is one copy that falls behind. Collapse a research command repeated by a double-click to its first occurrence per `(player_id, technology_type)`, which R5 measured happening five times in this one game, and name the age-up field `age_up_commands` (FR-043c)
- [ ] T356 [P] [US4] Write the golden-extraction test in `packages/replay-engine/tests/test_extract.py`: the committed replay extracts to the committed timeline, byte-for-byte. This is the assertion ADR-0001 was written about — a game patch silently broke parsing for months because nothing asserted the shape of the answer — and a version bump that moves one age-up by 208 ms must show as a diff and be explained, never absorbed
- [ ] T357 [P] [US4] Write the memory-ceiling test in `packages/replay-engine/tests/test_extract_limits.py`: a recording whose raw size exceeds `ANALYSIS_MAX_RAW_BYTES` is refused **before** it is parsed — the key T301 declares and R3 derives, not `_MAX_INNER_BYTES`, which is a zip-bomb guard about a different threat and ~9× too permissive to protect memory, and `extract()` never returns the operation stream, asserted by field introspection on the return type. R3 measured ~631 MB resident for a 6.9 MB 1v1 against a 2 GB ceiling; an eight-player game carries roughly three times the operations, so this is the path that will run first in production

### The analyzer

- [ ] T358 [P] [US4] Write the admission-gate tests in `apps/analyzer/tests/test_admission.py`, `xfail(strict=True, reason="T359 not implemented yet")`, encoding quickstart scenario 9: an analysis fetch is refused while any unstored capture sits inside its deadline danger window, so analysis never consumes the request budget, quota or execution window capture depends on (FR-039); analysis draws on its own daily source allowance counted from `provider_calls` and exhausting it never touches capture's; and at `ANALYSIS_RETENTION_CAP_BYTES` a new analysis is refused with `analysis_cap_reached` while capture is unaffected (FR-047). Three gates, asserted independently, because they fail in different directions — the window, the source's patience, and the allowance (R7)
- [ ] T359 [US4] Implement `apps/analyzer/src/aoe2stats_analyzer/admission.py` and remove T358's markers. Each gate is a condition over rows this system already keeps, so it can be read in production with a SQL query — constitution I is a tie-break rule, and one that lives only in prose is decided by whoever wrote the code last
- [ ] T360 [P] [US4] Write the claim and lease tests in `apps/analyzer/tests/test_claim.py`, `xfail(strict=True, reason="T361 not implemented yet")`: a claim is exclusive under `FOR UPDATE SKIP LOCKED`; an expired lease is re-claimable; a second asker arriving under a live lease joins the existing row and starts no second parse (FR-038); and **nothing sweeps an expired lease** — asserted by running the ingester's `run_once` over an abandoned analysis and confirming it is untouched (FR-044)
- [ ] T361 [US4] Implement `apps/analyzer/src/aoe2stats_analyzer/claim.py` and remove T360's markers. `running` means *a lease was taken recently*, never *work is happening now* — R6 explains why the platform forces that reading, and every transition must be written against it
- [ ] T362 [P] [US4] Write the retention tests in `apps/analyzer/tests/test_retain.py`, `xfail(strict=True, reason="T363 not implemented yet")`: the recording is stored byte-for-byte with a sha256 recorded at retention and verified on retrieval; the object key uses the retained-recording prefix and **never** resolves to `replay_object_key`'s, asserted for the same `(game_id, profile_id)` (FR-048, R9); and a retained recording is never deleted by a recompute, a parser change, the cap being reached, **an erasure, or a third-party objection** (constitution IX 3.0.0, amended 2026-08-24 — the last two used to delete it and now pseudonymise the identifiers instead). **Cover the own-match case explicitly**: analysing a match whose point of view this service already holds as a `replay_captures` row still writes a `retained_recordings` row and a second object under the retention prefix, and erasing that user deletes the capture while the retained copy and the published analysis stand. That is the contrast case, not a repetition of the third-party one — see `data-model.md`'s `retained_recordings` section for why the two objects are not redundant
- [ ] T363 [US4] Implement `apps/analyzer/src/aoe2stats_analyzer/retain.py` and the retained-recording key function in `packages/storage/src/aoe2stats_storage/objects.py`, and remove T362's markers. A separate prefix, because the free-tier watch and any bulk copy operate by prefix with no database to join against. **Retain for an own match too** — reading 001's capture and retaining nothing is the optimisation that looks right in every surrounding line and leaves a published analysis unrecomputable the first time its point of view erases (`data-model.md`, decided 2026-08-24)
- [ ] T364 [P] [US4] Write the `run_once` tests in `apps/analyzer/tests/test_run.py`, `xfail(strict=True, reason="T365 not implemented yet")`, encoding quickstart scenarios 7, 8 and 10: a match is fetched and parsed exactly once however many users ask (SC-006); the stored row records which point of view it came from and which parser version produced it (FR-032); a parse failure leaves the API and the ingester untouched and the match visibly failed rather than analysed (SC-013); an interrupted run leaves no unclaimable row and the next request resumes it (FR-037); an unparsable recording goes to `failed` with its full error on the **first** attempt and does not retry, because a parse is deterministic and a second attempt is a second identical failure that costs a fetch (FR-036); a match whose recordings expired and was never analysed is `unavailable`, not an action (FR-034); and a published analysis recomputes from the retained bytes with **zero** calls to the source, however old the match (FR-041, SC-009a) — **triggered by a second `run_once` for that match after the engine version changes, and by nothing else**: assert that no sweep, no cron and no timer produces it (FR-044), and that the same call against a published row that is *not* stale re-parses nothing (SC-006); and every read of a retained recording leaves a `replay_access_log` row with `retained_recording_id` set and `replay_capture_id` null, on the first analysis and on each recompute, so a third party's recording is never opened without a trace (FR-029)
- [ ] T365 [US4] Implement `apps/analyzer/src/aoe2stats_analyzer/run.py` and `extract.py` — `run_once(budget_seconds)`, knowing nothing about its caller — and remove T364's markers. it writes a `replay_access_log` row carrying `retained_recording_id` for every read of a retained recording, first analysis and recompute alike, **before** any engine is loaded (FR-029, and the decision in [data-model.md](./data-model.md)); `extract.py` orchestrates through the Protocol and imports no engine; `apps/analyzer` is the only application that *extracts* with `packages/replay-engine`, which is not the same as the only one that declares it — see T302 for why `apps/api` declares it too and must keep doing so
- [ ] T366 [US4] Add `api/analyze.py` — ten lines, session-authenticated, calling `run_once()` — and its `maxDuration: 300` entry in `vercel.json`. **No `CRON_SECRET`**: this is not a cron endpoint and must not become one. It adds no cron entry, so the number of scheduled jobs after this feature equals the number before it (SC-010, FR-044). It is resolved by the filesystem before the `/api/(.*)` rewrite, the way `api/cron/ingest.py` already is; extend `scripts/checks/spa-routing.mjs` to assert that resolution for this path too, so the ordering is checked rather than assumed

### The API and the interface

- [ ] T367 [P] [US4] Write the analysis API tests in `apps/api/tests/test_analysis_routes.py`, `xfail(strict=True, reason="T368 not implemented yet")`: a user can request the analysis of a match whose recording is obtainable and sees a result for every participant (FR-030); the `analysis` object appears on the match-detail response in each of its seven states, so a user can tell whether a match can still be analysed and until when without contacting support (SC-011); it carries `stale: true` for a published analysis whose `parser_version` differs from the running engine and `false` otherwise, computed on read and never a column (FR-041); `GET /api/matches/{game_id}/analysis` answers `404` in every state but `published`; the per-user request limit applies (FR-040); and `absent` versus `unavailable` versus `refused` are distinguishable from the payload alone, since each leads the interface somewhere different
- [ ] T368 [US4] Implement `apps/api/src/aoe2stats_api/routers/analysis.py` and wire the `analysis` object into the match-detail response in `apps/api/src/aoe2stats_api/routers/matches.py`, and remove T367's markers. The API reads state and never performs work — the work is `api/analyze.py`, in its own process, which is how constitution V's isolation is obtained here (FR-042)
- [ ] T369 [US4] Add retention of analysed third-party recordings to `docs/privacy/processing-register.md` as its own processing activity, with its own legal basis, retention, safeguards and balancing test, in this same change (FR-045, constitution IX). It is **not** activity 3: that one is the consenting user's own point of view under explicit consent, this one is an already-public recording retained because a person deliberately asked for that match to be analysed. A row that misdescribes which is which is a breach in the direction the register itself warns about. In the same change, correct **activity 5** ("Logging access to archived replay files"): its data-subject column claims "a replay is only ever opened by the user who owns the capture, per the download endpoint's ownership check", which stops being the whole truth once `replay_access_log` carries `retained_recording_id`. Those rows are `apps/analyzer`'s system reads of a third party's recording and never downloads (R8) — say so, because an activity that misdescribes who is read about is the failure the register itself warns against, and `CLAUDE.md` requires `docs/` to be true today
- [ ] T370 [P] [US4] Write the component specs for the analysis timeline, its progress state and its three failure states in `packages/design-system/specs/`. State what a *stale* published analysis looks like — the facts stay on the page and the recompute is offered beside them, never a warning that hides the result (FR-041) — how an unnamed technology or unit identifier is presented (FR-043a) and how an age-up time is labelled so it reads as **ordered** and not reached (FR-043c) — the wording is the requirement here, and it is decided in the spec, not in the component
- [ ] T371 [US4] Build the analysis components from tokens in `packages/design-system/src/components/`, with stories for published, published-and-stale, running, failed, unavailable and refused
- [ ] T372 [US4] Wire the analysis into the match page in `apps/web/src/features/analysis/`, including leaving and returning to a running analysis (FR-035) and offering the recompute only while the match-detail response reports `stale: true` (FR-041)
- [ ] T373 [US4] Run `visual-reviewer` locally, then `pnpm test:visual --changed` over the stories T371 added, updating baselines in `packages/design-system/__screenshots__/`

**Checkpoint**: every story is complete.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [x] T374 [P] Correct `docs/adr/0001-replay-parser.md` on two measured points, keeping the decision and its date intact and adding a dated correction note: `Build` is **not** decoded by the pinned wheel, which contradicts "Build plus Research plus the Sync clock is everything the V2 engine needs" — true of the information, false of the shape; and the parser's type table carries an `Achievements` post-game block that the reference recording does not contain. An ADR under `docs/` must be true today (`CLAUDE.md`), and both facts change what the next person tries first
- [x] T375 [P] Add the extraction discipline to `.claude/skills/replay-parsing/SKILL.md` — the memory bound rather than the time bound, the undecoded `Build`, the duplicated research command, and the command-log-not-state-log rule that decides what may be published — pointing at `docs/` for every number and restating none of them
- [x] T376 [P] Record the open question in `docs/data-sources.md` §2: whether any current-patch ranked recording carries an `Achievements` post-game block, measured across several recordings and several game modes. One negative sample proves nothing, and the answer decides whether the derivation feature simulates or reads
- [x] T377 [P] Update the verification checklist in `docs/risks.md` with this feature's **four** new failure modes: retention growth against the cap, a parse that exceeds memory, a search source that answers from a residential connection but not from the platform's egress addresses, and **a search source that answers `200` with a drifted body shape** — measured during Phase 3's review, where a renamed envelope key and, separately, a renamed field inside every record each turned a live source into a permanent `degraded: false, results: []`. Both are guarded in code now (T313's parser raises on either), so the failure mode this records is the *silent* one: the guard degrades honestly but tells nobody, and until T385a lands nothing watches that endpoint's shape
- [ ] T378 Extend the free-tier watch in `scripts/checks/free_tier_watch.py` — **created by 001's T100, which lands first; if it has not, this task is blocked and does not create it**, because a second watch is the double-counting FR-048 forbids arriving through the monitor — to count the retained-recording prefix **separately** from 001's capture prefix, and to warn at 70 % of the analysis cap as well as of the bucket allowance. Counting them together would misstate both, which is the failure FR-048 exists to prevent, arriving through the monitor rather than through a query
- [x] T379 [P] Run `uv run ruff format .`, `uv run ruff check --fix .` and `uv run mypy` clean across every workspace member including the new `apps/analyzer`, and `uv run alembic check` reporting no drift
- [x] T380 Run `uv run python scripts/checks/spec_lint.py --feature specs/003-player-search-match-analysis` clean, and fix what it reports in the artifacts rather than in the linter
- [ ] T381 Walk scenarios 1, 2, 7, 8, 9, 10 and 11 of `specs/003-player-search-match-analysis/quickstart.md` end to end against a real deployment with a real second profile, and record each outcome in the pull request. Time the type-a-name-to-reading-ratings path (SC-001) and the share of searches that surface a player who exists from a partial, wrongly-cased fragment (SC-002); time a ranked 1v1 analysis from request to result (SC-007). Those three are verified here or nowhere. Scenario 9 is the one that matters most and is the one most likely to fail in production: `expired_total` must stay at 0 while search, browsing and analysis are all in use (SC-008, constitution I)
- [ ] T382 Walk scenario 12 of `specs/003-player-search-match-analysis/quickstart.md` once 001's T090 to T092 have landed, and record the outcome in the pull request: export carries favourites and requested analyses; erasure removes favourites and clears `requested_by_user_id` while the analyses themselves stand; and a third-party objection removes a retained recording and withdraws the analyses derived from it (FR-017, FR-046, SC-012)

---

## Phase 9: Phase 3 review follow-ups

Added 2026-08-23, after US1 merged. Three review rounds on Phase 3 found three blockers that are
fixed and committed; what remains is recorded here rather than in the pull request, because a
follow-up that lives only in a merged PR thread is one nobody reads again.

Ordering matters for exactly one of these: **T384 is a gate on Phase 4** and is repeated there.

- [x] T383 [US1] Give `/search` an entry point in `apps/web/src/routes/__root.tsx` (or the dashboard, whichever the existing navigation makes correct), and confirm the profile page reaches search back. Phase 3's checkpoint claims "a user can find any player by name — this is the MVP", and SC-001 times the type-a-name-to-reading-ratings path; both are false while the page is reachable only by typing a URL. T322 added the routes and no navigation, and no task in Phase 3 owned the entry point — this is that gap, surfacing as a product gap rather than a code one
- [x] T384 Invert the default in `apps/api/src/aoe2stats_api/app.py`'s no-index middleware: header **every** `/api/*` response and allowlist the handful of 001 routes that must stay bare, then rewrite `apps/api/tests/test_no_index_headers.py`'s `test_non_feature_route_headers_are_unchanged` against the new default. Today the middleware matches a hand-maintained prefix list and that test asserts any route *outside* it must not carry the header — so a new route is not merely unprotected, the suite ratifies it. T308's stated goal was "a route added later without the header fails this test instead of quietly shipping"; what it delivered is "a route added later **under one of four prefixes**". **This lands before T327**, the first of five later route tasks (T327, T328, T337, T346, T368), because each one is another chance to forget a constitution IX property with the test agreeing
- [x] T385 [P] [US1] Fix three correctness defects in `apps/api/src/aoe2stats_api/search.py`, each with the test that catches it: `contains()` defaults to `autoescape=False`, so `%` and `_` in a user query are LIKE wildcards and `q=%` returns the most-played profiles this service knows — a directory listing reached through a search box, which is the shape FR-008a exists to prevent; the query is normalised with Python `casefold()` + NFC but matched with SQL `lower()` and no normalisation, so a decomposed alias is unreachable by a precomposed query and the docstring's claim that Unicode form collapses is true of the cache key and false of the match; and nothing enforces `_FALLBACK_CACHE_TTL_SECONDS < PLAYER_SEARCH_CACHE_TTL_SECONDS`, so an operator setting the configured TTL below 30 s silently inverts "deliberately much shorter"
- [x] T385a [P] Extend `scripts/checks/contract_sources.py` to cover `GET https://data.aoe2companion.com/api/profiles?search=` — the envelope carries `profiles` as a list, and each record carries `profileId` and `name` — so the nightly run fails when the source's shape drifts. It currently covers the companion *match* feed only. This is the highest-value item in this phase: Phase 3's review found two ways a drifted `200` turned the live source into a permanent `degraded: false, results: []`, and both are guarded in the parser now, but the guard degrades honestly **and tells nobody**. `CLAUDE.md` makes the nightly contract test the mechanism that keeps `docs/` true; §3's measured record list is exactly the claim going unwatched. Feeds T377
- [x] T386 [P] Add an index on `profile_search_cache.fetched_at` in `infra/migrations/`. The opportunistic prune is a `DELETE ... WHERE fetched_at < threshold` across the whole table on every successful cache write, and the table has no index on that column — so the mechanism that exists to bound the table degrades linearly with the thing it bounds
- [x] T387 [P] Record the invariant the BL-2 fix rests on, as a comment at the `provider.search_players()` call site in `apps/api/src/aoe2stats_api/search.py`: **no `await` may be introduced between that call returning and `last_call_failed()` being read.** The signal is last-write-wins on a process-lifetime breaker; it is per-call only because the read happens in the same synchronous continuation as the write. That holds today and nothing tests it, which makes it exactly the kind of invariant a later refactor breaks silently
- [x] T388 [P] Cleanups, none load-bearing: `ProfileSummary`'s `searchHref` still defaults to `/players`, which is not a route (a second consumer gets a dead link; `PlayerProfileContainer` overrides it); the dead xfail-reason constants survive in `packages/providers/tests/test_{steam,aoems,relic_profile}.py` now their tasks have landed; `PlayerResultRow` uses a raw `<a href>` inside a TanStack Router SPA, forcing a full document load per result click (`MatchRow` sets the same precedent, so change both or neither); `SearchContainer.test.tsx`'s two fetch-counting tests use real timers with a 900 ms sleep and are the slowest in the web suite; and once the rate-limit countdown reaches zero the region reads "Try again in 0s." until the user edits the text
- [x] T389 [P] Make `test_search_rate_limits_per_user_and_answers_retry_after` in `apps/api/tests/test_players_routes.py` deterministic. Observed failing once in six full-workspace runs on 2026-08-23 and passing alone and in three consecutive repeats after, so it is a real intermittent, not a change. `ratelimit.py` uses epoch-aligned fixed windows: a test that spends its calls near a boundary has the counter reset underneath it and sees no limit where it asserted one. Pin the clock rather than widening the assertion — a rate-limit test that tolerates the limit not firing is testing nothing. This is the shape of flake that gets re-run until green and then believed

---

## Phase 10: The deploy contract

Added 2026-08-23, after a production outage. Not a review finding: `https://aoe2-stats.com/api/me`
answered `500 internal_error` with an empty `detail` on every request, and so did every other
`/api/*` route, because the ten configuration keys T302 declared were never set on the deployment
target. `Settings()` raised while FastAPI resolved each route's dependencies, before any route body
ran. No code was wrong.

The class matters more than the instance. This repository checks its own internal coherence
thoroughly — `spec_lint.py` holds `.env.example` against the feature artifacts, `alembic check`
holds the models against the migrations, `built-css.mjs` and `spa-routing.mjs` hold the build
against the platform's own resolution order — and **nothing ever held any of it against the
environment the code actually runs in**. Every feature that declares a required key or ships a
migration re-arms the same trap. It has now fired three times: T014e (two missing environment
variables and a misnamed one, in one evening), T106 (`csrf_states` applied to Neon by hand, without
which every sign-in would have answered 500), and this one.

T390, T391 and T393 are done and committed. T392 is the open half and is the same task 001's T106
has carried unclosed since 2026-08-21 — recorded here as well because 003 is the feature that ships
a migration through the gap it names.

- [x] T390 Answer `configuration_invalid` 503 from **every** route, not only `/api/health`. `settings.py` gains `ConfigurationError` and `missing_or_invalid_keys()` (moved from `apps/api/src/aoe2stats_api/routers/health.py`, which was its only caller while it was the only route that named the fault); `get_settings()` raises the first instead of `pydantic.ValidationError`; `app.py` handles it ahead of its generic `Exception` handler. `apps/api/tests/test_configuration_envelope.py` is the specification: the reported outage reproduced on `/api/me`, `/api/me` and `/api/health` reporting the *same* keys for the same broken environment, no configuration *value* in the envelope (constitution VIII), the healthy contrast case still answering 200, and — the case the obvious fix gets wrong — a `pydantic.ValidationError` raised inside a route body still answering `internal_error` 500, because `parse_strict` raises exactly that for a drifted third-party payload and a source contract violation is not a configuration fault. Verified failing against the pre-fix tree: three of the six fail, `/api/me` raising `ConfigurationError` uncaught
- [x] T391 Fail the **build** on a missing key rather than every request after it. `scripts/checks/config-preflight.mjs`, invoked from `vercel.json`'s `buildCommand` ahead of the web build, asserts every alias `settings.py` declares is set and non-empty in the build environment. This is the only check in the tree with a view of both the repository and the deployment target, which is why it runs there and not in CI. Its own failure mode is silence — a pattern that stops matching a field would keep passing while covering fewer keys — so it first holds its extracted list against `.env.example`'s in both directions and fails on any disagreement; that half runs on every pull request as the `config` job in `pr.yml` (`--contract`). `BETA_ALLOWLIST_STEAM_IDS` is the one key allowed to be present and empty, per `settings.py`'s own comment; an empty `CRON_SECRET` is the defect T018b closed and must never read as set
- [x] T393 Ask the running deployment whether it serves. `scripts/checks/production-health.mjs` asserts `/api/health` **and** `GET /api/me` both answer 200 — the second is not redundant: it is the front end's bootstrap call and the exact request that reported this outage, and a route can break in ways a probe route does not. Run from `.github/workflows/smoke.yml` on every push to `main`, after a settle window and requiring two spaced confirmations so a 200 served by the deployment on its way out cannot pass it; and again nightly, as a `production-smoke` job in `nightly.yml` feeding the existing failure-issue `report`. `/` is a static CDN response and answers 200 through every one of these faults, which is why an uptime check on the site itself never noticed
- [x] T392 Give the deploy a migration step, or a runbook that names one, and declare Neon's direct-endpoint connection string alongside the pooled one in `.env.example`. **This is 001's T106, unclosed since 2026-08-21**, and it is the half of the deploy contract T390, T391 and T393 do not cover: nothing in the pipeline runs `alembic upgrade head` against production, `1f9879367c9d` was shipped by the 003 merge, and the pooled connection string `.env.example` documents is the wrong one for Alembic — Neon's pooler does not give DDL the session semantics it needs. Close it in one place, not two: whichever file it lands in, the other one references it. **`1f9879367c9d` was applied to Neon by hand on 2026-08-23**, through the direct endpoint, to end the outage — the same manual step T106 records for `csrf_states`, which is the evidence that this task is the fix and applying the migration was not. `alembic check` against production reports no drift; the database is at head and the pipeline still cannot put it there
- [x] T394 Make a missing migration *visible* to T393. `/api/health`'s database probe is `SELECT 1`, which succeeds against a schema missing every column a migration would have added — so a deploy that ships an unapplied migration passes the smoke check and then fails on the first route that reads a widened table. Compare `alembic_version.version_num` against the head revision the deployed tree carries, and report a distinct code (`schema_out_of_date`) rather than folding it into `database_unavailable`: they call for different actions from whoever reads it. Depends on nothing in T392, and does not replace it — one makes the fault visible, the other stops it happening. Built as `aoe2stats_storage.revision.EXPECTED_SCHEMA_REVISION`, a constant compiled into the package rather than a read of `infra/migrations/versions` at runtime: nothing guarantees those files are in the deployed function bundle (`vercel.json` declares no `includeFiles`) and constitution XII rules out depending on them. A restated value is only safe because it is guarded — `test_schema_revision.py` holds it against Alembic's own head on every run, and the route reports `schema_revision` in its healthy body so the value is visible without a failure. The probe asks `to_regclass` before reading `alembic_version`, because a statement that raises inside a transaction poisons it for everything after: a database that has never been migrated at all is `schema_out_of_date` with `found: null`, not some later fault. Three route tests, two of them against the real throwaway database at a real revision — the fake session agrees with the build by construction and proves nothing about the schema, which its own docstring now says
- [x] T395 Record the deploy contract where it outlives this feature: the failure mode in `docs/risks.md`'s verification checklist beside T377's four, and in `docs/adr/0002-hosting.md` under what the platform forbids in the code — the platform gives no "deploy hook" the repository can gate on, so a deploy cannot be *blocked* from here and the build command is the only place a check runs before traffic reaches the function. Reference `scripts/checks/` for the mechanism and restate no key list: `.env.example` is its one home (`CLAUDE.md`, never copy a measurement between files)

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)** — no dependencies. Blocks everything.
- **Phase 2 (Foundational)** — depends on Phase 1. Blocks every story. T310 in particular blocks T327:
  widening `/api/matches/{game_id}` before the superseded-rule test is rewritten turns the tree red.
- **Phase 3 (US1, P1)** — depends on Phase 2. The MVP.
- **Phase 4 (US2, P2)** — depends on Phase 2. Independent of US1 in the API; the web route T331 adds
  is reached from US1's profile page, so ship US1 first for a coherent demo.
- **Phase 5 (US3, P3)** — depends on Phase 4 for the page its downloads live on.
- **Phase 6 (US5, P5)** — depends on Phase 2 and, for its toggle, on US1's profile page.
- **Phase 7 (US4, P4)** — depends on Phase 4, and on **001's T090–T092** before T363 retains anything.
- **Phase 8 (Polish)** — T374 to T377 depend on Phase 7's measurements; T382 depends on the gate.
- **Phase 9 (Phase 3 follow-ups)** — added after US1 merged. Everything in it depends only on Phase 3,
  so it can run whenever there is room, with one exception that is not free to defer: **T384 gates
  Phase 4** and is repeated in that phase's header. T385a feeds T377.

### Within a story

Tests before implementation, always, and the `xfail` marker comes off in the implementing task.
Models before services, services before routes, component specs before components, components before
web wiring, visual review last.

### Parallel opportunities

Honest [P] markers, not decorative ones. Two tasks writing the same file are never both [P], which is
why the route tests are split across files by concern rather than by story.

- **Phase 2**: T303, T306 and T308 are a genuine three-way batch — three test files, three areas.
  T310 is [P] with all of them.
- **Phase 3**: T301a is done and unblocked these — it measured the hidden signal, found none, and
  FR-004c was retired, so T311, T312 and T314 lost that assertion rather than gaining it. T311 and
  T312 are sequential (T312 reads T311's fixture). T314 and T317 are [P] with
  each other and with T318.
- **Phase 4**: T324, T325 and T326 are a three-way batch — three separate test files.
- **Phase 7**: T351, T353, T358, T360, T362 and T364 are [P] across six files, and the largest batch
  in this feature. T356 and T357 are [P] with each other once T355 lands.
- **Across phases**: Phase 6 (US5) is [P] with the whole of Phase 7 — no shared file — which is why it
  is placed where it is.

---

## Implementation Strategy

### MVP

Phase 1, Phase 2, Phase 3. At that point a user can find any player and read their standing, which
already replaces looking an opponent up on the official leaderboard site. Stop and walk quickstart
scenario 1 with the search source deliberately unreachable before building further — if the degraded
path does not work, everything after it rests on a source `docs/data-sources.md` records as
unverified from the platform's egress addresses.

### Incremental delivery

1. Phases 1 and 2 → schema, limits, headers, the superseded rule rewritten. Commit.
2. Phase 3 (US1) → the MVP. Commit and demo.
3. Phase 4 (US2) → any match readable at any age. Commit and demo.
4. Phase 5 (US3) → the recorded game, per point of view. Commit and demo.
5. Phase 6 (US5) → favourites. Commit. The product is now useful with no analysis at all.
6. Phase 7 (US4) → analysis, once 001's US5 has landed. Commit per task.
7. Phase 8 → the documentation corrections, the monitors, and the two human walks.

Stopping after step 5 is a legitimate release. That is the ordering constitution I asks for, arriving
as a delivery plan rather than as an intention.

---

## Phase 11: Constitution IX 3.0.0 alignment

Added 2026-08-24. The constitution was amended mid-feature — IX to 3.0.0 (a retained recording is
never deleted; every field the AoE2 DE APIs serve is treated as public) and IV to 3.0.1 (its deletion
exception written against the *basis* rather than the file). `/speckit-analyze` found eight CRITICAL
and five HIGH inconsistencies; the documents are corrected and committed. **What remains is the code
that still enforces the retired rule**, and it is recorded here rather than in a review thread.

The whole phase is US1's search path. It depends on nothing in Phases 4 to 7 and can run whenever
there is room — but **it lands before T381**, which walks a quickstart scenario 2 now rewritten
against the new behaviour.

- [x] T396 [P] [US1] Carry the source's Steam claim through the provider, in
  `packages/providers/src/aoe2stats_providers/base.py` and
  `packages/providers/src/aoe2stats_providers/companion/provider.py`. `PlayerSearchResult` gains
  `unverified_steam_id: str | None`, read from the record's `steamId`. The field name is the
  requirement and not a comment on it (`specs/003-player-search-match-analysis/contracts/providers.md`): a consumer who never opened the
  contract must not be able to read the claim as a fact. `shared`, `sharedHistory` and
  `linkedProfiles` stay unread — each for a reason that survives the amendment and is written in that same
  contract, not as a residue of FR-004b
- [x] T397 [US1] **Invert** `test_search_players_returns_only_the_five_contract_fields` and the
  `_ACCOUNT_LINKING_FIELDS` set in `packages/providers/tests/test_companion.py`. These pass today and
  **ratify the rule the amendment removed** — the same shape as T384's finding, one layer down.
  Dispatch this one against its failure: **the hand-back must carry the output of the test failing
  before the fix**, because a test written beside the change it verifies passes for the wrong reason
  and that is the normal result, not the unlucky one (`CLAUDE.md`, remediating a review finding).
  Assert both halves and do not let the second slide: the field **is** carried and equals the
  source's value, **and** `shared`, `shared_history`, `linked_profiles` are still absent from the
  dataclass by introspection
- [x] T398 [US1] Surface `unverified_steam_id` through `GET /api/players/search?q=` in
  `apps/api/src/aoe2stats_api/search.py` and `apps/api/src/aoe2stats_api/routers/players.py`, and
  store it in `profile_search_cache.results` — six contract fields now, not five. It is `null` on the
  degraded fallback (FR-004d), which reads `aoe_profiles` and has no such claim; a client must read
  `null` as "not known here" and never as "no Steam account" (this feature's `contracts/` http-api document). Update
  `apps/api/tests/test_players_routes.py`, whose comment at the cached-shape assertion still names the
  fields "a verbatim provider body would additionally carry"
- [x] T399 [P] [US1] Write the component spec for how an unverified claim is labelled, in
  `packages/design-system/specs/`, then build it and wire it into the result row. The wording is the
  requirement and it is decided here, not in the component — the same discipline FR-043a set for an
  unnameable identifier. **No affordance may be built on the field**: no "same player", no merge, no
  navigation asserting two profiles are one person (001 FR-045's remaining half, which the amendment
  did not touch). A test asserting the *absence* of that affordance is the one worth writing, and it
  is the kind an implementer weakens into something that passes
- [x] T400 Amend 001's FR-045 in `specs/001-steam-link-replay-ingestion/spec.md` to carve carriage
  out from action, with a dated note rather than a rewrite. Its two justifications have separated:
  the privacy half was decided against on 2026-08-24, the accuracy half — "they are unverifiable" —
  stands and is now the whole of the requirement. Leaving FR-045 as written makes 001 and 003
  contradict each other on a field both now describe

## Notes

- Commit at the granularity `CLAUDE.md` sets: the smallest set of tasks that was ever simultaneously
  green, with the `[x]` in this file riding in the same commit as the work that earned it. Commit
  when a task hands back, **before** dispatching the next one — a batch launched over an uncommitted
  predecessor absorbs it permanently.
- Every task above is one `implementer` invocation.
- Every `[P]` dispatch tells the agent: **do not modify a file outside your task's named paths.** If
  the shared gate fails because of a sibling's file, report it and hand back. `CLAUDE.md` records what
  this cost in 001's Phase 3 — four files of rework — and Phase 7's six-way batch is the largest
  exposure in this feature.
- The `xfail(strict=True)` markers are not a formality and `pytest.importorskip` is not a substitute.
  A skipped test reports green while proving nothing. `CLAUDE.md` records that six of seven agents in
  001's test batch reached for `importorskip` under gate pressure; that is a property of the squeeze,
  not of the agents. Dispatch against it.
- Several tests above assert an **absence** — no resource field, no favourite aggregate, no outbound
  request, no sweep. These are the ones an implementer is most likely to weaken into something that
  passes, because an absence has no happy path to demonstrate. Each one names why it exists.
