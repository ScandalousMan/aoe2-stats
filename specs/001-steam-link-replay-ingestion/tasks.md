---
description: "Task list for Steam account linking and automatic replay ingestion"
---

# Tasks: Steam Account Linking and Automatic Replay Ingestion

**Input**: Design documents from `/specs/001-steam-link-replay-ingestion/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included, and mandatory. Constitution VII requires visual tests for every UI component,
and the user story phases below place every test task *before* the implementation tasks it covers.
The eleven scenarios in [quickstart.md](./quickstart.md) are the source for the integration tests;
each test task names the scenario it encodes. A test task is done when the test exists **and fails**
for the right reason.

**Organization**: Grouped by user story so each one can be implemented, tested and demonstrated on
its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1..US5, mapping to the user stories in [spec.md](./spec.md)
- Every task names its exact file path

## Path Conventions

Monorepo per [plan.md](./plan.md): `apps/api`, `apps/ingester`, `apps/web`, `packages/core`,
`packages/providers`, `packages/replay-engine`, `packages/storage`, `packages/design-system`,
`infra/migrations`, and the one platform-shaped file at `api/cron/ingest.py`.

## Scenario coverage map

| quickstart scenario | Story | Test task |
| --- | --- | --- |
| 1 — Linking works and cannot be forged | US1 | T021 |
| 2 — Nothing happens without consent | US2 | T042 |
| 3 — Backfill rescues the window | US2 | T043 |
| 4 — Interruption loses nothing | US2 | T044 |
| 5 — Deadline order under pressure | US2 | T045 |
| 6 — Idempotency | US2 | T046 |
| 7 — Failure classification | US2 | T047 |
| 8 — Manual upload | US4 | T078 |
| 9 — Multiple Steam accounts | US1 | T023 |
| 10 — Data rights | US5 | T086, T087, T088 |
| 11 — Liveness reports absence | US2 | T048 |

quickstart has no scenario for US3: match history is the one story whose data can be re-fetched at
any time, so its tests are derived from the acceptance scenarios in [spec.md](./spec.md) instead.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Turn a repository that currently holds only documents, CI and one reference replay into
a working uv + pnpm monorepo.

- [ ] T001 Create the root `pyproject.toml` declaring the uv workspace members (`packages/core`, `packages/providers`, `packages/replay-engine`, `packages/storage`, `apps/api`, `apps/ingester`), Python 3.13, and the shared `ruff` and `mypy` (strict) configuration, in `pyproject.toml`
- [ ] T002 [P] Create the six Python package skeletons with their own `pyproject.toml` and `src/` layout: `packages/core/`, `packages/providers/`, `packages/replay-engine/`, `packages/storage/`, `apps/api/`, `apps/ingester/`
- [ ] T003 [P] Create the pnpm workspace — `package.json`, `pnpm-workspace.yaml` — plus the Vite + React 19 + TypeScript + TanStack Router/Query + Tailwind application in `apps/web/` and the Storybook package in `packages/design-system/`
- [ ] T004 [P] Configure pytest in `pyproject.toml` — including `scripts/checks` in `testpaths`, since it is not a uv workspace member and T048's test would otherwise never be collected — and add the autouse fixture in `tests/conftest.py` that makes the network unavailable when `PYTEST_DISABLE_NETWORK=1`, so constitution III is enforced by the harness and not by discipline
- [ ] T005 [P] Configure Playwright and the `test:visual` script for diff-scoped visual regression in `playwright.config.ts` and `package.json`
- [ ] T006 [P] Implement typed settings loaded exclusively from environment variables, covering every key already declared in `.env.example`, in `apps/api/src/aoe2stats_api/settings.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The schema, the storage boundary, the provider boundary and the two entrypoints. Every
user story depends on all of it.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T007 Implement every SQLAlchemy model from [data-model.md](./data-model.md) — `users`, `steam_identities`, `aoe_profiles`, `profile_links`, `matches`, `match_players`, `rating_snapshots`, `replay_captures`, `replay_parses`, `ingest_runs`, `provider_calls`, `replay_access_log`, `data_requests`, `sessions`, `alerts` — including `replay_captures.claimed_at`, the `(game_id, profile_id)` unique constraint that *is* deduplication, the partial unique index enforcing one primary profile per user, and the partial unique index `UNIQUE (profile_links.profile_id) WHERE unlinked_at IS NULL` so an unlinked profile does not block its own relink, in `packages/storage/src/aoe2stats_storage/models.py`
- [ ] T007a [P] Add every personal data field introduced by this feature to the processing register, as constitution IX requires in the same change, in `docs/privacy/processing-register.md`
- [ ] T008 Initialise Alembic and write the initial migration for those models, verifying `upgrade head` then `downgrade -1` both succeed as the `migrations` job in `.github/workflows/pr.yml` demands, in `infra/migrations/` and `alembic.ini`
- [ ] T009 [P] Implement the async engine, session factory and repository base — `psycopg` 3 against the pooled connection string with server-side prepared statements disabled per research §4 — in `packages/storage/src/aoe2stats_storage/repositories/base.py`
- [ ] T010 [P] Implement the S3 object store — key scheme, put, signed get, delete, list — called from a worker thread so the sync `boto3` client never blocks the event loop, in `packages/storage/src/aoe2stats_storage/objects.py`
- [ ] T011 [P] Implement the provider base from [contracts/providers.md](./contracts/providers.md): the Protocols, the explicit timeout, retry with backoff, the token bucket, verbatim raw-response persistence, the `provider_calls` row, the honest `User-Agent`, and the typed errors `ProviderUnavailable` / `ProviderRateLimited` / `ProviderContractViolation`, in `packages/providers/src/aoe2stats_providers/base.py`
- [ ] T012 [P] Capture frozen real responses for every provider used by this feature into `packages/providers/fixtures/`, extending `scripts/checks/contract_sources.py` to write them
- [ ] T013 [P] Implement the pluggable replay engine **Protocol** in `packages/core/src/aoe2stats_core/replay/validation.py` and the `aoe2rec-py` adapter that satisfies it — well-formedness, inner filename, inner byte count, engine name and version, capture-time validation only — in `packages/replay-engine/src/aoe2stats_replay_engine/aoe2rec.py`. The adapter stays out of `core`, which the API imports: constitution V wants a parser crash to reach neither the API nor the ingester
- [ ] T014 Create the FastAPI application, the single error envelope `{"error": {"code", "message", "detail"}}` from [contracts/http-api.md](./contracts/http-api.md), the dependency wiring and `GET /api/health`, in `apps/api/src/aoe2stats_api/app.py`, `deps.py` and `routers/health.py`
- [ ] T014a [P] Implement the alert sink — `raise_alert(kind, severity, detail, run_id)` writing an `alerts` row, and the query the nightly job uses to find unacknowledged severity-1 rows — in `packages/core/src/aoe2stats_core/alerting.py`
- [ ] T015 [P] Implement the integration-test harness that creates and drops a throwaway database per session, in `apps/api/tests/conftest.py` and `apps/ingester/tests/conftest.py`
- [ ] T016 [P] Define the design tokens — colour, spacing, radius, typography, elevation — the Tailwind preset that consumes them and the Storybook configuration, in `packages/design-system/tokens/` and `packages/design-system/.storybook/`
- [ ] T017 [P] Build the web shell: router, query client, session bootstrap through `GET /api/me`, and the API client that branches on the error `code` and never on `message`, in `apps/web/src/main.tsx` and `apps/web/src/lib/api.ts`
- [ ] T018 Implement the ingester entrypoint skeleton `run_once(budget_seconds)` plus the time budget checked between items and never mid-item, and the cron handler that rejects a request without `CRON_SECRET` with 401. The FastAPI route is the authority; `api/cron/ingest.py` is a ten-line shim that delegates to it, so the two do not compete for the same Vercel path — in `apps/ingester/src/aoe2stats_ingester/run.py`, `budget.py` and `api/cron/ingest.py`

**Checkpoint**: Schema migrates, the API answers `/api/health`, the cron endpoint 401s, Storybook runs.

---

## Phase 3: User Story 1 - Link my Steam account and see who I am (Priority: P1) 🎯 MVP

**Goal**: A player signs in with Steam, the system proves the sign-in with Steam itself, resolves the
AoE2 profile, and shows their ratings. Several Steam accounts may be linked to one aoe2-stats
account, one of them primary. Consent to ingestion is asked here, separately and explicitly, because
this is the moment the user is told that Steam is the only key and that there is no recovery.

**Independent Test**: Sign in with a Steam account belonging to a player who has played ranked games
and confirm the correct profile and current ratings appear with nothing typed; replay the callback
and confirm rejection.

### Tests for User Story 1 ⚠️ Write first, watch them fail

- [ ] T019 [P] [US1] Contract test for `SteamAuthProvider` against frozen fixtures — `check_authentication` returning `is_valid:true` and `is_valid:false`, `claimed_id` matched against the exact pattern and not by substring, `return_to` validated against configuration, and `verify` returning `None` rather than raising on an invalid assertion — in `packages/providers/tests/test_steam.py`
- [ ] T020 [P] [US1] Contract test for `ProfileProvider` against frozen fixtures — `resolve_profile` returning a `ProfileRef`, `resolve_profile` returning `None` for a Steam account with no AoE2 profile, `personal_stats` batching up to 50 profiles, and a field of unexpected type raising `ProviderContractViolation` rather than being coerced — in `packages/providers/tests/test_relic_profile.py`
- [ ] T021 [P] [US1] Integration test for quickstart scenario 1: sign-in resolves profile and ratings with no input; a replayed callback with identical parameters is **rejected**; a callback with one character of `openid.claimed_id` altered is rejected; a Steam account that has never played AoE2 online yields `no_aoe2_profile` and not a stack trace — in `apps/api/tests/test_auth_flow.py`
- [ ] T022 [P] [US1] Integration test for the closed-beta allowlist (FR-005): a non-allowlisted visitor gets `not_allowlisted` with an explanation and no account row is created, in `apps/api/tests/test_allowlist.py`
- [ ] T023 [P] [US1] Integration test for quickstart scenario 9: sign in as A, link B through `/api/auth/steam/start?link=1`, expect both profiles under one account with exactly one primary and both eligible for ingestion; assert **no response of any endpoint** reveals that A and B are the same person (FR-045); assert `profile_already_linked` when B belongs to another account — in `apps/api/tests/test_multi_account.py`
- [ ] T024 [P] [US1] Integration test for unlink and relink (FR-004): the unlink response states what becomes of archived replays *before* confirmation, ingestion stops for that profile, `unlinked_at` is set rather than the row deleted, and relinking the same profile works, in `apps/api/tests/test_unlink.py`
- [ ] T025 [P] [US1] Integration test for consent (FR-034, FR-035): consent is a separate call that can be declined while the rest of the account works, `ingest_consent_at` is recorded, withdrawal sets `ingest_consent_withdrawn_at`, in `apps/api/tests/test_consent.py`

### Implementation for User Story 1

- [ ] T026 [P] [US1] Implement `SteamAuthProvider.begin` and `.verify` — the OpenID 2.0 redirect, the mandatory `check_authentication` round trip against Steam's pinned endpoint, `claimed_id` pattern matching, `return_to` validation — in `packages/providers/src/aoe2stats_providers/steam/provider.py`
- [ ] T027 [P] [US1] Implement `ProfileProvider.resolve_profile` and `.personal_stats` against the Relic endpoints, persisting each raw response verbatim, in `packages/providers/src/aoe2stats_providers/relic/profile.py`
- [ ] T028 [US1] Implement server-side sessions — opaque identifier, `HttpOnly` + `Secure` + `SameSite=Lax` signed cookie, immediate server-side revocation, CSRF `state` tied to the browser session — in `apps/api/src/aoe2stats_api/security.py`
- [ ] T029 [US1] Implement the auth router: `GET /api/auth/steam/start` (with `?link=1` adding a second Steam account instead of replacing the session), `GET /api/auth/steam/callback`, `POST /api/auth/signout`, and `GET /api/me` returning 200 with `{"authenticated": false}` when signed out, in `apps/api/src/aoe2stats_api/routers/auth.py`
- [ ] T030 [US1] Enforce the allowlist at account creation and return `not_allowlisted` with its explanation, reading the allowlist from settings (`BETA_ALLOWLIST_STEAM_IDS`) and stamping `allowlisted_at` on first sign-in for a listed Steam id — without which the closed beta cannot admit its first user — in `apps/api/src/aoe2stats_api/routers/auth.py`
- [ ] T031 [US1] Implement the profiles router: `GET /api/profiles` with current rating, rank and win/loss per leaderboard (FR-008), `POST /api/profiles/{profile_id}/primary` (FR-043), `DELETE /api/profiles/{profile_id}` returning the consequences for archived replays before confirmation (FR-004), in `apps/api/src/aoe2stats_api/routers/profiles.py`
- [ ] T031a [US1] On a successful link, enqueue the 31-day backfill synchronously — `replay_captures` rows with deadlines computed from `completed_at`, so the next cycle drains the most endangered first (FR-015) — in `apps/api/src/aoe2stats_api/routers/auth.py`
- [ ] T032 [US1] Implement `POST /api/privacy/consent` granting and withdrawing ingestion consent as a choice separate from account creation, in `apps/api/src/aoe2stats_api/routers/privacy.py`
- [ ] T033 [US1] Append a `rating_snapshots` row whenever ratings are resolved, so the history required by FR-009 starts accumulating from the first sign-in, in `packages/storage/src/aoe2stats_storage/repositories/ratings.py`
- [ ] T034 [P] [US1] Write the component specs for the sign-in screen, the consent step and the profile summary — including the plain statement that Steam is the only key and there is no recovery (FR-006) — in `packages/design-system/specs/`
- [ ] T035 [US1] Build the design-system components those specs call for, tokens only and each with a story, in `packages/design-system/src/` and their `*.stories.tsx`
- [ ] T036 [US1] Build the sign-in route with its `no_aoe2_profile`, `not_allowlisted` and `steam_assertion_invalid` states — an explanation and a retry, never an empty dashboard — in `apps/web/src/routes/sign-in.tsx` and `apps/web/src/features/auth/`
- [ ] T037 [US1] Build the dashboard header: ratings per leaderboard, the profile switcher that makes non-primary profiles reachable rather than hidden (FR-043), the unlink confirmation dialog and the consent step, in `apps/web/src/routes/dashboard.tsx` and `apps/web/src/features/profile/`
- [ ] T038 [US1] Run `visual-reviewer` locally then `pnpm test:visual --changed` over the stories added by T035, per constitution VII, updating baselines in `packages/design-system/__screenshots__/`

**Checkpoint**: A real Steam account signs in, is identified, sees its ratings, can link a second
account, and a replayed callback is refused. Demonstrable on its own.

---

## Phase 4: User Story 2 - Never lose another replay (Priority: P2)

**Goal**: The system discovers new matches for every linked profile and archives each replay well
inside the ~31-day window, resuming cleanly from any interruption, draining by nearest deadline, and
reporting its own absence.

**Independent Test**: Link an active player, run cycles until the backlog empties, and confirm every
match from the preceding 31 days whose replay is still available is `stored` and downloads
byte-for-byte identical.

### Tests for User Story 2 ⚠️ Write first, watch them fail

- [ ] T039 [P] [US2] Contract test for `ReplayProvider` covering the whole failure taxonomy in [contracts/providers.md](./contracts/providers.md) — `ReplayBlob`, `Unavailable(not_recorded)`, `Unavailable(expired)`, `ProviderRateLimited` on 429 and on an unexpected 403, `ProviderUnavailable` on 5xx and timeout — in `packages/providers/tests/test_aoems.py`
- [ ] T040 [P] [US2] Contract test for `MatchHistoryProvider.recent_matches`: batching up to 10 profiles per call, and `RawMatch` carrying the untouched payload alongside the parsed fields, in `packages/providers/tests/test_relic_matches.py`
- [ ] T041 [P] [US2] Contract test for `EnrichmentProvider`: a 403 is expected noise, the circuit breaker opens, the application renders correctly with this provider returning nothing, and `linkedProfiles` is **never** read (FR-045), in `packages/providers/tests/test_companion.py`
- [ ] T042 [P] [US2] Integration test for quickstart scenario 2: a user who declined consent produces zero `replay_captures` rows and zero `provider_calls` rows against the replay endpoint after a cycle — asserting the consent condition is in the `WHERE` clause that selects work, by testing that no code path downstream can reach the provider — in `apps/ingester/tests/test_consent_gate.py`
- [ ] T043 [P] [US2] Integration test for quickstart scenario 3: after linking, cycles run until the backlog is empty; every match from the last 31 days still available is `stored`, anything older is `expired` and nothing else is, each blob is a single-member zip whose sha256 matches the recorded one, and captures cover **all** linked profiles and not only the primary (FR-042, SC-003, SC-005), in `apps/ingester/tests/test_backfill.py`
- [ ] T043a [P] [US2] Integration test for the shared-match case: two consenting users in one game produce exactly one `matches` row and two `replay_captures` rows with distinct `profile_id` and distinct `object_key`; neither user's download reaches the other's blob (FR-016), in `apps/ingester/tests/test_shared_match.py`
- [ ] T044 [P] [US2] Integration test for quickstart scenario 4: a cycle given a two-second budget against ten pending captures stops with some `stored`, the rest `pending` and **none** left `downloading`; a process killed mid-download leaves `downloading` rows that the next cycle reclaims and completes; no blob written twice; no capture `stored` without a retrievable object (FR-022, FR-023, SC-009), in `apps/ingester/tests/test_interruption.py`
- [ ] T045 [P] [US2] Integration test for quickstart scenario 5: with pending captures whose deadlines are two days and eighteen days out and a budget that allows only half the queue, the **near-deadline** captures are the ones stored, in `apps/ingester/tests/test_deadline_order.py`
- [ ] T046 [P] [US2] Integration test for quickstart scenario 6: three further cycles over an archived capture create no row, change no `stored_at`, rewrite no object and issue no request to the replay endpoint for that match (FR-018, SC-006), in `apps/ingester/tests/test_idempotency.py`
- [ ] T047 [P] [US2] Integration test for quickstart scenario 7: a 404 for a match completed two days ago yields `unavailable` and no alert; a 404 for a match completed forty days ago yields `expired` **and an alert**; a 429 stops the whole run and alerts; three 500s produce backoff then `failed` at the attempt limit. Every alert asserted here is an `alerts` row written through `raise_alert` (T014a), and the `expired` one is raised at the day-21 capture deadline, not at expiry (FR-019, FR-020, FR-021, FR-025), in `apps/ingester/tests/test_failure_classification.py`
- [ ] T047a [P] [US2] Integration test for the quarantine path: a downloaded blob that fails well-formedness validation is **still uploaded**, the row is `quarantined` with `last_error` set, the object is retrievable, and the capture counts in neither `stored_total` nor `expired_total` (FR-026, constitution IV and V), in `apps/ingester/tests/test_quarantine.py`
- [ ] T048 [P] [US2] Test for quickstart scenario 11: the liveness check passes against a fresh `ingest_runs` row and **fails** when that row is backdated by 31 hours (FR-024, SC-007), in `scripts/checks/tests/test_cron_liveness.py`

### Implementation for User Story 2

- [ ] T049 [P] [US2] Implement `ReplayProvider.fetch_replay` against `aoe.ms`, a full in-memory download since the endpoint ignores `Range` and rejects `HEAD` (research §5), returning the taxonomy the contract defines, in `packages/providers/src/aoe2stats_providers/aoems/provider.py`
- [ ] T050 [P] [US2] Implement `MatchHistoryProvider.recent_matches`, batched ten profiles per call, persisting each raw response verbatim into `matches.raw_payload`, in `packages/providers/src/aoe2stats_providers/relic/matches.py`
- [ ] T051 [P] [US2] Implement `EnrichmentProvider.enrich_matches` behind a circuit breaker, treating every failure as normal and ignoring `linkedProfiles` entirely, in `packages/providers/src/aoe2stats_providers/companion/provider.py`
- [ ] T052 [US2] Implement the token bucket at one request per second to the replay endpoint, the backoff policy, and the rule that `ProviderRateLimited` stops the entire run and raises an alert through `raise_alert` (T014a) rather than skipping one capture, in `apps/ingester/src/aoe2stats_ingester/ratelimit.py`
- [ ] T053 [US2] Implement discovery: refresh ratings into `rating_snapshots`, fetch recent matches for every consenting user's every linked profile, upsert `matches` and `match_players`, and enqueue `replay_captures` with `capture_deadline_at = completed_at + 21 days` computed once on insert — with consent expressed as a condition of the selecting query (FR-013, FR-042) — in `apps/ingester/src/aoe2stats_ingester/discover.py`
- [ ] T054 [US2] Implement the 25-day reconciliation sweep and the immediate 31-day backfill triggered on linking (FR-015), in `apps/ingester/src/aoe2stats_ingester/reconcile.py`
- [ ] T055 [US2] Implement capture: claim with `FOR UPDATE SKIP LOCKED` ordered by `capture_deadline_at` ascending, reclaim stale `downloading` rows older than the maximum function duration, download, upload the blob, verify the checksum, validate through the engine interface, **then** update the row to `stored` or `quarantined` (FR-017, FR-023, FR-026). The blob is uploaded before it is validated and is never discarded on a validation failure — after ~31 days the source has no replacement, so an unparsable capture is evidence, not garbage. A quarantine raises a severity-2 `validation_failed` alert through `raise_alert` (T014a), since nothing else would ever surface it — in `apps/ingester/src/aoe2stats_ingester/capture.py`
- [ ] T056 [US2] Implement the `unavailable` versus `expired` decision in the caller from `matches.completed_at`, since the endpoint returns an identical 404 for both, and alert through `raise_alert` (T014a) on `expired` only, in `apps/ingester/src/aoe2stats_ingester/capture.py`
- [ ] T057 [US2] Implement bounded retries: `next_attempt_at` written on the row with increasing delay and a terminal `failed` status at the attempt limit, never an unbounded retry (FR-020), in `apps/ingester/src/aoe2stats_ingester/capture.py`
- [ ] T058 [US2] Enforce the ingestion quota per user aggregated across all their profiles, never per profile, exempting any capture nearer to its deadline than `INGEST_QUOTA_EXEMPT_DAYS` so the fairness cap can never delay an expiring replay (FR-044). It lives in its own module and **not** in `budget.py`, which `plan.md` defines as the *time* budget — in `apps/ingester/src/aoe2stats_ingester/quota.py`
- [ ] T059 [US2] Complete `run_once(budget_seconds)`: discover, reconcile, drain, then write the `ingest_runs` row with every counter plus `capture_lag_p50_seconds` and `capture_lag_p95_seconds` (FR-024), in `apps/ingester/src/aoe2stats_ingester/run.py`
- [ ] T060 [US2] Wire `POST /api/cron/ingest` to return 200 with the run report even when individual captures failed, reserving non-200 for a cycle that could not run at all. One implementation only: the FastAPI route holds the logic and `api/cron/ingest.py` stays a delegating shim (see T018) — in `apps/api/src/aoe2stats_api/routers/health.py` and `api/cron/ingest.py`
- [ ] T061 [US2] Write the external checks and enable their jobs — the cron-liveness check failing past 30 hours, the capture audit asserting `expired_total == 0` with no capture pending beyond `CAPTURE_BUDGET_DAYS` (derived, never a second hard-coded threshold), and the alert audit failing on any unacknowledged severity-1 row — in `scripts/checks/cron_liveness.py`, `scripts/checks/capture_audit.py`, `scripts/checks/alert_audit.py` and `.github/workflows/nightly.yml`
- [ ] T062 [US2] Implement `GET /api/replays/status?profile_id=` returning counts per status, the oldest pending and the nearest deadline, in `apps/api/src/aoe2stats_api/routers/replays.py`

**Checkpoint**: Replays are being archived automatically, an interrupted run resumes, and a cron that
stops firing is detected from outside the system.

---

## Phase 5: User Story 3 - Browse my match history (Priority: P3)

**Goal**: A reverse-chronological match list with the essentials, a detail view with every
participant, the archival state and remaining capture window per match, and a download.

**Independent Test**: With a linked account, open the history and confirm the last matches agree with
the official stats page and that each row's archival state reflects reality.

### Tests for User Story 3 ⚠️ Write first, watch them fail

- [ ] T063 [P] [US3] Integration test for `GET /api/matches`: newest first, carrying opponent, map, civilisation, result, rating change and duration, cursor pagination stable across insertions, in `apps/api/tests/test_matches_list.py`
- [ ] T064 [P] [US3] Integration test for `GET /api/matches/{game_id}`: every participant with team, civilisation, result and rating change, in `apps/api/tests/test_match_detail.py`
- [ ] T065 [P] [US3] Integration test for the capture state shown per match (FR-027, SC-010): archived, pending with the time remaining before the window closes, or lost; plus the empty state for a user with no matches, in `apps/api/tests/test_capture_visibility.py`
- [ ] T066 [P] [US3] Integration test for `GET /api/replays/{game_id}/download`: a 302 to a short-lived signed URL, a `replay_access_log` row written (FR-040), the bucket never public, and a caller who did not play the match refused, in `apps/api/tests/test_replay_download.py`
- [ ] T067 [P] [US3] Integration test that no endpoint returns the history of an arbitrary `profile_id` the caller has not linked (FR-038), in `apps/api/tests/test_no_public_directory.py`
- [ ] T068 [P] [US3] Integration test for `GET /api/profiles/{profile_id}/ratings` returning the rating curve from `rating_snapshots` (FR-009), in `apps/api/tests/test_rating_history.py`

### Implementation for User Story 3

- [ ] T069 [US3] Implement the match queries — reverse-chronological, cursor paginated, restricted to the caller's linked profiles, joined to capture status — in `packages/storage/src/aoe2stats_storage/repositories/matches.py`
- [ ] T070 [US3] Implement the matches router: list and detail per [contracts/http-api.md](./contracts/http-api.md), in `apps/api/src/aoe2stats_api/routers/matches.py`
- [ ] T071 [US3] Implement the replay download: freshly signed short-expiry URL, access log write, participation check, in `apps/api/src/aoe2stats_api/routers/replays.py`
- [ ] T072 [US3] Implement `GET /api/profiles/{profile_id}/ratings` over `rating_snapshots`, in `apps/api/src/aoe2stats_api/routers/profiles.py`
- [ ] T073 [P] [US3] Write the component specs for the match row, the match detail panel and the capture-state badge — the badge must distinguish four states: safe, still catchable with the time remaining to the day-21 capture deadline, lost, and needs review (quarantined) — in `packages/design-system/specs/`
- [ ] T074 [US3] Build those components from tokens, each with a story, in `packages/design-system/src/` and their `*.stories.tsx`
- [ ] T075 [US3] Build the match history route with its empty state, in `apps/web/src/routes/matches.tsx` and `apps/web/src/features/matches/`
- [ ] T076 [US3] Build the match detail route with the participant table and the replay download, in `apps/web/src/routes/matches.$gameId.tsx` and `apps/web/src/features/replays/`
- [ ] T077 [US3] Run `visual-reviewer` then `pnpm test:visual --changed` over the stories added by T074, per constitution VII, updating baselines in `packages/design-system/__screenshots__/`

**Checkpoint**: The product is usable day to day — history, detail, and an honest capture state per
match.

---

## Phase 6: User Story 4 - Rescue a replay the system could not get (Priority: P4)

**Goal**: When automatic capture failed, the user uploads the file from their own machine and it is
archived alongside the rest, flagged as manually supplied.

**Independent Test**: Take a match marked lost, upload the corresponding file from the game's saved
games folder, and confirm it is archived and attached to the right match.

### Tests for User Story 4 ⚠️ Write first, watch them fail

- [ ] T078 [P] [US4] Integration test for quickstart scenario 8, all four points: uploading the matching file for an `expired` capture yields `stored` flagged manual; a text file renamed `.aoe2record` is rejected with nothing stored; a valid replay for a match the user did not play is rejected; an upload over an existing archive is refused with a reason and does not overwrite (FR-029 to FR-033), in `apps/api/tests/test_manual_upload.py`
- [ ] T079 [P] [US4] Unit test for the validation engine against the committed reference replay in `tests/fixtures/replays/` and against truncated, empty and non-replay inputs, in `packages/core/tests/test_replay_validation.py`

### Implementation for User Story 4

- [ ] T080 [US4] Implement `POST /api/replays/{game_id}/upload`: multipart, participation check, validation through the same engine interface capture uses, refusal when an archive already exists, and the same write ordering — blob first, row second — in `apps/api/src/aoe2stats_api/routers/replays.py`
- [ ] T081 [US4] Create or update the `replay_captures` row with `source = 'manual'` and `validated_by` recorded, including the case where no capture row existed, in `packages/storage/src/aoe2stats_storage/repositories/captures.py`
- [ ] T082 [P] [US4] Write the component spec for the upload control and its rejection states, in `packages/design-system/specs/`
- [ ] T083 [US4] Build the upload component from tokens with its story, in `packages/design-system/src/` and its `*.stories.tsx`
- [ ] T084 [US4] Wire the upload into the match detail route, shown only where no archive exists, in `apps/web/src/features/replays/`
- [ ] T085 [US4] Run `visual-reviewer` then `pnpm test:visual --changed` over the stories added by T083, per constitution VII, updating baselines in `packages/design-system/__screenshots__/`

**Checkpoint**: The safety net works, and a manually supplied replay is distinguishable from a
captured one.

---

## Phase 7: User Story 5 - Control my data (Priority: P5)

**Goal**: Export everything including the blobs, erase everything including the blobs, and give a
non-user a way to object.

**Independent Test**: Export and confirm it contains the account, the links, the match records and
the archived replays; then erase and confirm nothing remains, in the records or in the bucket.

### Tests for User Story 5 ⚠️ Write first, watch them fail

- [ ] T086 [P] [US5] Integration test for quickstart scenario 10 point 1: the export contains the account, the Steam identities, the profile links, the match records **and the replay blobs** (FR-036), in `apps/api/tests/test_export.py`
- [ ] T087 [P] [US5] Integration test for quickstart scenario 10 points 2 and 3: erasure requires an explicit confirmation token, removes the user, identities, links, captures and blobs — **verified by listing the bucket, not by trusting the response** — while `matches` and `match_players` survive with the departing user's `profile_id` pseudonymised (FR-037, FR-039, SC-008), in `apps/api/tests/test_erasure.py`
- [ ] T088 [P] [US5] Integration test for `POST /api/privacy/object`: unauthenticated by design, rate limited, and recording a request for a human rather than pseudonymising immediately (FR-039), in `apps/api/tests/test_third_party_objection.py`
- [ ] T089 [P] [US5] Integration test for the edge case where consent is withdrawn while captures are queued: no further download occurs for that user on the next cycle (FR-035), in `apps/ingester/tests/test_consent_withdrawal.py`

### Implementation for User Story 5

- [ ] T090 [US5] Implement the export job: a `data_requests` row, an archive assembled from the records and the blobs, and a signed URL from `GET /api/privacy/export/{id}`, in `apps/api/src/aoe2stats_api/routers/privacy.py` and `packages/core/src/aoe2stats_core/privacy/export.py`
- [ ] T091 [US5] Implement erasure: confirmation token from a prior `GET`, deletion of the user, identities, links, captures and objects, and in-place pseudonymisation of the departing `profile_id` in `matches` and `match_players`, in `packages/core/src/aoe2stats_core/privacy/erasure.py`
- [ ] T092 [US5] Implement `POST /api/privacy/object` with its rate limit and its deferred, recorded resolution, in `apps/api/src/aoe2stats_api/routers/privacy.py`
- [ ] T093 [US5] Write the privacy notice — what is collected, on what basis, for how long, how to exercise these rights (FR-041) — in `apps/web/src/routes/privacy-notice.tsx`
- [ ] T094 [P] [US5] Write the component specs for the privacy screens, including the erasure confirmation whose wording states plainly that it is irreversible, in `packages/design-system/specs/`
- [ ] T095 [US5] Build the privacy route — consent state, export request and download, erasure with its confirmation — from tokens with stories, in `apps/web/src/routes/privacy.tsx` and `apps/web/src/features/privacy/`
- [ ] T096 [US5] Run `visual-reviewer` then `pnpm test:visual --changed` over the stories added by T095, per constitution VII, updating baselines in `packages/design-system/__screenshots__/`

**Checkpoint**: The service is legally offerable to someone other than its author.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T098 [P] Add the Microsoft Game Content Usage Rules disclaimer to the site footer and confirm it in `README.md`, per constitution X, in `apps/web/src/components/Footer.tsx`
- [ ] T099 [P] Update the verification checklist in `docs/risks.md` to point at the checks that now exist — cron liveness, capture audit — without restating any measurement that lives in `docs/data-sources.md`
- [ ] T100 [P] Add the free-tier watch that warns at 70% of any free allowance (R2 bytes, Neon storage, Vercel invocations) in `scripts/checks/free_tier_watch.py` and `.github/workflows/nightly.yml`
- [ ] T101 [P] Enable the full nightly visual regression job across every story in `.github/workflows/nightly.yml`
- [ ] T102 Add response caching so match history and ratings answer under 500 ms p95, in `apps/api/src/aoe2stats_api/deps.py`
- [ ] T103 [P] Audit logging for secrets in the clear and add structured logging with the run id, per constitution VIII, in `apps/api/src/aoe2stats_api/app.py` and `apps/ingester/src/aoe2stats_ingester/run.py`
- [ ] T104 [P] Run `uv run ruff format .`, `uv run ruff check --fix .` and `uv run mypy` clean across every workspace member declared in `pyproject.toml`
- [ ] T105 Walk `specs/001-steam-link-replay-ingestion/quickstart.md` by hand end to end, all eleven scenarios, against a real Steam account that has played online within the last week, recording the outcome of each in the pull request. Time the arrival-to-own-ratings path as one of the steps: SC-004's 60 seconds is verified here or nowhere

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: needs Setup — **blocks every user story**
- **US1 (Phase 3)**: needs Foundational
- **US2 (Phase 4)**: needs Foundational, and needs US1 in practice — there is nothing to ingest until a profile is linked and consent exists
- **US3 (Phase 5)**: needs Foundational; reads what US2 writes, but its tests seed the database directly and therefore run without US2
- **US4 (Phase 6)**: needs Foundational and the validation engine (T013); independent of US2
- **US5 (Phase 7)**: needs Foundational; erasure of blobs is testable with seeded captures, so it does not need US2
- **Polish (Phase 8)**: needs the stories it touches

### Within Each User Story

- Tests are written first and must fail before the implementation they cover
- Providers before the services that call them
- Models and repositories before routers
- Component specs before components, components before routes, routes before the visual run

### The one ordering that is not negotiable

Inside US2, T055 must implement upload-then-mark, never mark-then-upload. T044 exists to catch the
reverse. A capture row claiming a replay is safe when it is not is a lie the user cannot detect, and
it is the failure mode the whole architecture is arranged against.

### Parallel Opportunities

- T002 to T006 in Setup
- T009 to T013 and T015 to T017 in Foundational, once T007 and T008 have landed
- All test tasks within a story: T019–T025, T039–T048, T063–T068, T078–T079, T086–T089
- Provider implementations across stories: T026, T027, T049, T050, T051 touch different packages
- US3, US4 and US5 can be built by different people at the same time once Foundational is done

---

## Parallel Example: User Story 2 tests

```bash
# Every test below fails at the start of the phase, and that is the point.
Task: "Contract test for ReplayProvider taxonomy in packages/providers/tests/test_aoems.py"
Task: "Integration test for scenario 2 in apps/ingester/tests/test_consent_gate.py"
Task: "Integration test for scenario 3 in apps/ingester/tests/test_backfill.py"
Task: "Integration test for scenario 4 in apps/ingester/tests/test_interruption.py"
Task: "Integration test for scenario 5 in apps/ingester/tests/test_deadline_order.py"
Task: "Integration test for scenario 6 in apps/ingester/tests/test_idempotency.py"
Task: "Integration test for scenario 7 in apps/ingester/tests/test_failure_classification.py"
```

---

## Implementation Strategy

### MVP

Phases 1 to 3 — Setup, Foundational, US1. That is a service that identifies a player from their
Steam account and shows their ratings, with a forgery-proof sign-in.

It is worth being explicit that this MVP does **not** yet capture anything, and constitution I means
the gap between shipping US1 and shipping US2 is a period during which replays are being destroyed.
US2 should follow immediately; nothing in US3, US4 or US5 should be started before it.

### Incremental Delivery

1. Setup + Foundational
2. US1 — a player can be identified → demo
3. US2 — replays stop being lost → **this is the product**
4. US3 — the archive becomes browsable
5. US4 — the gaps can be filled by hand
6. US5 — the service can be offered to someone else

### Notes

- One task is one unit of work for the `implementer` agent
- Commit after each task
- Run `reviewer` before every merge; it rejects on spec and constitution grounds before quality
- Unit tests never touch the network — `PYTEST_DISABLE_NETWORK=1` makes that a fact rather than a rule
