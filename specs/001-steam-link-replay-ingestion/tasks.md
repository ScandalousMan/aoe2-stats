---
description: 'Task list for Steam account linking and automatic replay ingestion'
---

# Tasks: Steam Account Linking and Automatic Replay Ingestion

**Input**: Design documents from `/specs/001-steam-link-replay-ingestion/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included, and mandatory. Constitution VII requires visual tests for every UI component,
and the user story phases below place every test task _before_ the implementation tasks it covers.
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
`infra/migrations`, and the two platform-shaped files at `api/cron/ingest.py` and `api/index.py`.

## Scenario coverage map

| quickstart scenario                    | Story | Test task        |
| -------------------------------------- | ----- | ---------------- |
| 1 — Linking works and cannot be forged | US1   | T021             |
| 2 — Nothing happens without consent    | US2   | T042             |
| 3 — Backfill rescues the window        | US2   | T043             |
| 4 — Interruption loses nothing         | US2   | T044             |
| 5 — Deadline order under pressure      | US2   | T045             |
| 6 — Idempotency                        | US2   | T046             |
| 7 — Failure classification             | US2   | T047             |
| 8 — Manual upload                      | US4   | T078             |
| 9 — Multiple Steam accounts            | US1   | T023             |
| 10 — Data rights                       | US5   | T086, T087, T088 |
| 11 — Liveness reports absence          | US2   | T048             |

quickstart has no scenario for US3: match history is the one story whose data can be re-fetched at
any time, so its tests are derived from the acceptance scenarios in [spec.md](./spec.md) instead.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Turn a repository that currently holds only documents, CI and one reference replay into
a working uv + pnpm monorepo.

- [x] T001 Create the root `pyproject.toml` declaring the uv workspace members (`packages/core`, `packages/providers`, `packages/replay-engine`, `packages/storage`, `apps/api`, `apps/ingester`), Python 3.13, and the shared `ruff` and `mypy` (strict) configuration, in `pyproject.toml`
- [x] T002 [P] Create the six Python package skeletons with their own `pyproject.toml` and `src/` layout: `packages/core/`, `packages/providers/`, `packages/replay-engine/`, `packages/storage/`, `apps/api/`, `apps/ingester/`
- [x] T003 [P] Create the pnpm workspace — `package.json`, `pnpm-workspace.yaml` — plus the Vite + React 19 + TypeScript + TanStack Router/Query + Tailwind application in `apps/web/` and the Storybook package in `packages/design-system/`
- [x] T004 [P] Configure pytest in `pyproject.toml` — including `scripts/checks` in `testpaths`, since it is not a uv workspace member and T048's test would otherwise never be collected — and add the autouse fixture in `tests/conftest.py` that makes the network unavailable when `PYTEST_DISABLE_NETWORK=1`, so constitution III is enforced by the harness and not by discipline
- [x] T005 [P] Configure Playwright and the `test:visual` script for diff-scoped visual regression in `playwright.config.ts` and `package.json`
- [x] T006 [P] Implement typed settings loaded exclusively from environment variables, covering every key already declared in `.env.example`, in `apps/api/src/aoe2stats_api/settings.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The schema, the storage boundary, the provider boundary and the two entrypoints. Every
user story depends on all of it.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T007 Implement every SQLAlchemy model from [data-model.md](./data-model.md) — `users`, `steam_identities`, `aoe_profiles`, `profile_links`, `matches`, `match_players`, `rating_snapshots`, `replay_captures`, `replay_parses`, `ingest_runs`, `provider_calls`, `replay_access_log`, `data_requests`, `sessions`, `alerts` — including `replay_captures.claimed_at`, the `(game_id, profile_id)` unique constraint that _is_ deduplication, the partial unique index enforcing one primary profile per user, the partial unique index `UNIQUE (profile_links.profile_id) WHERE unlinked_at IS NULL` so an unlinked profile does not block its own relink, and `profile_links.backfill_requested_at`, which is how a link asks for a 31-day sweep it cannot perform itself (T031a, T054), in `packages/storage/src/aoe2stats_storage/models.py`
- [x] T007a [P] Reconcile the processing register with the schema this feature actually creates, in `docs/privacy/processing-register.md`: add every personal data category the models introduce that the register does not already carry — the replay access log and the rating time series among them — as constitution IX requires in the same change, and **check the existing rows still describe categories that are collected**. The register is wrong in both directions: an undeclared category is a breach, and a declared category that no longer exists misdescribes the processing to a reader who has no way to check. Walk the table in [data-model.md](./data-model.md) column by column rather than trusting what the register already says
- [x] T008 Initialise Alembic and write the initial migration for those models, verifying `upgrade head` then `downgrade -1` both succeed as the `migrations` job in `.github/workflows/pr.yml` demands, in `infra/migrations/` and `alembic.ini`
- [x] T009 [P] Implement the async engine, session factory and repository base — `psycopg` 3 against the pooled connection string with server-side prepared statements disabled per research §4 — in `packages/storage/src/aoe2stats_storage/repositories/base.py`
- [x] T010 [P] Implement the S3 object store — key scheme, put, signed get, delete, list — called from a worker thread so the sync `boto3` client never blocks the event loop, in `packages/storage/src/aoe2stats_storage/objects.py`
- [x] T011 [P] Implement the provider base from [contracts/providers.md](./contracts/providers.md): the Protocols, the explicit timeout, retry with backoff, the token bucket, verbatim raw-response persistence for irrecoverable sources only, into the column the calling provider names — there is no generic raw-response store and `provider_calls` deliberately holds no body (FR-012) — the `provider_calls` row, the honest `User-Agent`, and the typed errors `ProviderUnavailable` / `ProviderRateLimited` / `ProviderContractViolation`, in `packages/providers/src/aoe2stats_providers/base.py`
- [x] T012 [P] Capture frozen real responses for every provider used by this feature into `packages/providers/fixtures/`, extending `scripts/checks/contract_sources.py` to write them
- [x] T012a [P] Turn the publication-delay observation in `docs/data-sources.md` into a distribution, by extending `scripts/checks/contract_sources.py` to record on every nightly run the age of the probe profile's most recently completed match and whether its replay already answers 200. A non-blocking sample accumulated night after night, never a poll that waits for a 200: `contract_sources.py` is the nightly job and cannot sit on a request for hours. The file today holds a single observation — availability confirmed 33 minutes after match end — and one point is not a distribution. `REPLAY_PUBLICATION_GRACE_HOURS` is not sized on that delay in any case: it is sized on the **discovery cadence**, at least twice ~25 h, so that two polls always fall inside the grace and no single 404 can close a capture on its own (T056). What the samples decide is whether that floor also sits comfortably above the real publication delay — record them beside the retention window, and raise the grace if any sample exceeds it
- [x] T013 [P] Implement the pluggable replay engine **Protocol** in `packages/core/src/aoe2stats_core/replay/validation.py` and the `aoe2rec-py` adapter that satisfies it — well-formedness, inner filename, inner byte count, engine name and version, capture-time validation only — in `packages/replay-engine/src/aoe2stats_replay_engine/aoe2rec.py`. The adapter stays out of `core`, which the API imports, so the API never loads an engine at all. The ingester does load it, and contains it behind the barrier in T055 — between them that is what constitution V's "a parser crash affects neither the API nor the ingester" asks for
- [x] T014 Create the FastAPI application, the single error envelope `{"error": {"code", "message", "detail"}}` from [contracts/http-api.md](./contracts/http-api.md), the dependency wiring and `GET /api/health`, in `apps/api/src/aoe2stats_api/app.py`, `apps/api/src/aoe2stats_api/deps.py` and `apps/api/src/aoe2stats_api/routers/health.py`
- [x] T014a [P] Implement the alert sink — `raise_alert(kind, severity, detail, run_id)` writing an `alerts` row, and the query the nightly job uses to find unacknowledged severity-1 rows — in `packages/core/src/aoe2stats_core/alerting.py`
- [x] T014c Wire the deployment surface: `api/index.py` exposing the ASGI app from `apps/api` as the Vercel Python function, the `/api/(.*)` rewrite and the `maxDuration` for it, and the static build of `apps/web` — in `api/index.py` and `vercel.json`. Vercel's filesystem routing gives `api/cron/ingest.py` precedence over the rewrite, which is what keeps the cron on its own 300 s function while the request path keeps its own limit. Nothing in this task may be imported by application code: it is the second and last platform-shaped file in the tree (see T018)
- [x] T015 [P] Implement the integration-test harness that creates and drops a throwaway database per session, in `apps/api/tests/conftest.py` and `apps/ingester/tests/conftest.py`
- [x] T015a Give the `python` job a Postgres service so the T015 harness actually runs in CI, in `.github/workflows/pr.yml`. T015 skips rather than fails when no database is reachable, which was right for a job that had none — but every integration test from T021 onward is written against that harness, so as it stands the whole of Phase 3's test-first discipline would skip silently on every pull request and report green. A test that skips proves nothing. The `migrations` job already shows the service block to copy, and `tests/db.py` already falls back to exactly those credentials. Added by hand after Phase 2 closed: the gap only became visible once the harness and the CI file were read against each other
- [x] T016 [P] Define the design tokens — colour, spacing, radius, typography, elevation — the Tailwind preset that consumes them and the Storybook configuration, in `packages/design-system/tokens/` and `packages/design-system/.storybook/`
- [x] T017 [P] Build the web shell: router, query client, session bootstrap through `GET /api/me`, and the API client that branches on the error `code` and never on `message`, in `apps/web/src/main.tsx`, `apps/web/src/routes/__root.tsx` and `apps/web/src/lib/api.ts`
- [x] T017a Make the `web` job typecheck what the workspace actually builds, in `.github/workflows/pr.yml`. It runs `pnpm exec tsc --noEmit` from the repository root — a command in no package's scripts, against no root `tsconfig.json`, that nobody runs locally; under TypeScript 7 it fails outright and printed the compiler's help text on the first pull request. The real typecheck is per package (`tsr generate && tsc -b` for `apps/web`, which must run because TanStack's route tree is generated, not committed). Added by hand: the first CI run on this branch is what exposed it
- [x] T018 Implement the ingester entrypoint skeleton `run_once(budget_seconds)`, whose caller passes `INGEST_RUN_BUDGET_SECONDS` so that the platform's 300 s ceiling and the budget the code actually honours never become two numbers maintained apart, plus the time budget checked between items and never mid-item, and the cron handler that rejects a request without `CRON_SECRET` with 401. Both entrypoints call `run_once()` directly and neither delegates to the other (ADR-0002, constitution XII): `api/cron/ingest.py` is the deployed one and carries `maxDuration: 300`, while the FastAPI route exists for the local trigger quickstart documents and for nothing else. They do not compete for a Vercel path because filesystem routing gives the file precedence over the rewrite (T014c). The duplication is two lines of secret check, and it is the price of the constitution's "two thin entrypoints" rule — in `apps/ingester/src/aoe2stats_ingester/run.py`, `budget.py` and `api/cron/ingest.py`

**Checkpoint**: Schema migrates, the API answers `/api/health`, the cron endpoint 401s, Storybook runs.

### Phase 2 remediation (post-review)

Added by hand after the `reviewer` agent returned REJECT on `2de9252..fcf09b7`. Every one of these
is a defect in work already marked `[x]` above; they are listed here rather than edited into the
original task text so the record shows what was built, what was wrong with it, and when that was
found. Phase 3 does not start until this section is closed — all of it is foundational, and each
finding gets more expensive with every phase built on top of it.

- [x] T007b Stop `matches.game_id` and `aoe_profiles.profile_id` autoincrementing, in `packages/storage/src/aoe2stats_storage/models.py`, the initial migration, and `packages/storage/tests/test_models.py`. Both hold **Relic's** identifiers, not ours, but SQLAlchemy treats a lone integer primary key as autoincrement and both shipped as `BIGSERIAL` with a `nextval()` default. An insert that omits `game_id` therefore does not fail — it silently fabricates `1, 2, 3...`, a capture hangs off a phantom match, and the `(game_id, profile_id)` constraint that _is_ FR-018's deduplication cannot see the real row is a duplicate. This is the one schema error that produces wrong data instead of a loud failure. Assert `autoincrement is False` in the test, and drop the two sequences in the migration
- [x] T008a Add `uv run alembic check` to the `migrations` job in `.github/workflows/pr.yml`. Nothing today detects drift between `models.py` and the migrations: the job proves `upgrade`/`downgrade` run, and `test_models.py` asserts against `Base.metadata` only, so both pass while the two disagree. There is no drift right now — the point is that every later phase edits `models.py`
- [x] T011a Make `TokenBucket` and `SyncTokenBucket` actually limit concurrent callers, in `packages/providers/src/aoe2stats_providers/base.py`. `_reserve` clamps the balance to zero and returns a wait, so N concurrent acquirers all compute the same wait from the same zeroed state and all fire together: measured, five concurrent `acquire()` calls at 1 req/s produced one request at t=0 and **four simultaneously at t=1 s**. The docstring's promise of `rate_per_second` on average is false. Reserve against an advancing cursor — let the balance go negative, or hold a `next_available_at` — so N acquirers are spaced one over the rate apart. This is the sole mechanism behind FR-021 and constitution III's rate-limiting obligation, against `aoe.ms`, whose limit is undocumented. Add a **concurrency** test; the existing ones only call `acquire()` sequentially, which is why they pass
- [x] T012b Give the publication-delay samples a real home, and stop `docs/` describing a mechanism that does not exist — in `.github/workflows/nightly.yml`, `scripts/checks/contract_sources.py`, `scripts/checks/publication_delay.py`, `docs/data-sources.md` and `.env.example`. Three faults, one machinery: (a) the nightly job writes the sample into an ephemeral runner workspace with no commit step and `contents: read`, so the corpus cannot accumulate and holds one hand-committed line forever, while `docs/data-sources.md` asserts to the reader that it grows every night and that the summary block is machine-written — both false, and a `docs/` file must be true today; (b) `REPLAY_PUBLICATION_GRACE_HOURS` is hard-coded as `72` in `publication_delay.py` while also living in `.env.example`, and the generated prose asserts that number to the reader, so raising the grace leaves `docs/` stating something false about the running system. Store the corpus as a **chained GitHub Actions artifact** — each night downloads the previous corpus with the `gh` CLI and the workflow's built-in token, appends, and re-uploads the whole thing — so the watchtower needs no production credential, writes nothing to the repository, and still accumulates. `docs/data-sources.md` keeps the _conclusion_, written by a human when it moves, and says plainly where the raw samples live. The grace value is read from one place, never restated
- [x] T013a Bound decompression before trusting any header field, in `packages/replay-engine/src/aoe2stats_replay_engine/aoe2rec.py`. Both caps are computed from `member.file_size` and `member.compress_size` — values from the archive's own central directory, i.e. attacker-supplied — and `archive.read()` then inflates the whole member into memory _before_ the declared size is verified. An archive that under-declares `file_size` passes both caps and is inflated anyway. FR-030 sends user-uploaded files through this same validator (T081), so the input is not semi-trusted. Read through `archive.open(member)` with a hard cap and reject on overrun
- [ ] T018b Fix the cron endpoint's method and its secret, in `api/cron/ingest.py`, `apps/api/src/aoe2stats_api/routers/cron.py`, `apps/api/src/aoe2stats_api/settings.py`, `.env.example` and [contracts/http-api.md](./contracts/http-api.md). Two defects, both in the same authentication path: (a) Vercel Cron invokes the scheduled path with **GET**, attaching the bearer itself, but the platform handler is `methods=["POST"]` — the nightly cycle would 405 every night forever, and the only monitor that would notice is the `ingest_runs`-absence alert ADR-0002 calls the most important on this stack, still commented out in `nightly.yml`; the contract documents `POST`, so it is wrong too. (b) `CRON_SECRET` is a bare `SecretStr` with no minimum length and `.env.example` ships it **empty**, so `Authorization: Bearer ` authenticates and the endpoint is publicly invocable — verified, returns 200 — against constitution VIII's "never publicly invocable". Both entrypoints must refuse outright when the configured secret is empty rather than comparing against `"Bearer "`, and compare bytes so a non-ASCII header does not raise `TypeError` into a 500
- [ ] T018c Break the import path that will drag the replay engine into the API process, in `apps/api/src/aoe2stats_api/routers/cron.py`, `app.py` and `apps/api/pyproject.toml`. `apps/api` now depends on `apps/ingester` and imports `run_once` at module scope, so `import aoe2stats_api.app` pulls in `run.py` — whose the default stage tuple T055 will fill with a stage importing `packages/replay-engine`. At that moment the API transitively imports `aoe2rec_py`, a PyO3 extension documented as able to raise `BaseException` panics, contradicting plan.md's constitution-V row ("The API never loads an engine"), T013's own task text, and constitution V's "a parser crash affects neither the API nor the ingester" — and inflating the API function against a 500 MB ceiling. Nothing breaks today, which is exactly why it is cheap now and expensive at T055. Import lazily inside the handler or register stages through an explicit builder, and assert `aoe2rec_py` is absent from `sys.modules` after importing the app
- [ ] T015b Consolidate the duplicated test fixtures into `apps/api/tests/conftest.py`. The 18-key required-environment dict and its autouse `_environment` fixture exist byte-identically in `test_cron.py` and `test_cron_ingest_entrypoint.py`; `_FakeObjectStore` exists in four files and `_FakeSession` in three. `conftest.py` is the file whose whole purpose is shared fixtures and it was written in the same batch — four agents could not see each other's work, which is how the settings surface drifts from `.env.example` one test file at a time. Run this **after** T018b and T018c, which both change those same files

**Checkpoint**: the review's criticals and majors are closed, and the tree is green with the
concurrency and GET-cron tests that would have caught them.

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
- [ ] T021 [P] [US1] Integration test for quickstart scenario 1: sign-in resolves profile and ratings with no input; a replayed callback with identical parameters is **rejected**; a callback with one character of `openid.claimed_id` altered is rejected; a Steam account that has never played AoE2 online yields `no_aoe2_profile` and not a stack trace (FR-001, FR-002, FR-003) — in `apps/api/tests/test_auth_flow.py`
- [ ] T022 [P] [US1] Integration test for the closed-beta allowlist (FR-005): a non-allowlisted visitor gets `not_allowlisted` with an explanation and no account row is created, in `apps/api/tests/test_allowlist.py`
- [ ] T023 [P] [US1] Integration test for quickstart scenario 9: sign in as A, link B through `/api/auth/steam/start?link=1`, expect both profiles under one account with exactly one primary and both eligible for ingestion (FR-007); assert **no response of any endpoint** reveals that A and B are the same person (FR-045); assert `profile_already_linked` when B belongs to another account — in `apps/api/tests/test_multi_account.py`
- [ ] T024 [P] [US1] Integration test for unlink and relink (FR-004): the unlink response states what becomes of archived replays _before_ confirmation, ingestion stops for that profile, `unlinked_at` is set rather than the row deleted, and relinking the same profile works, in `apps/api/tests/test_unlink.py`
- [ ] T025 [P] [US1] Integration test for consent (FR-034, FR-035): consent is a separate call that can be declined while the rest of the account works, `ingest_consent_at` is recorded, withdrawal sets `ingest_consent_withdrawn_at`, in `apps/api/tests/test_consent.py`

### Implementation for User Story 1

- [ ] T026 [P] [US1] Implement `SteamAuthProvider.begin` and `.verify` — the OpenID 2.0 redirect, the mandatory `check_authentication` round trip against Steam's pinned endpoint, `claimed_id` pattern matching, `return_to` validation — in `packages/providers/src/aoe2stats_providers/steam/provider.py`
- [ ] T027 [P] [US1] Implement `ProfileProvider.resolve_profile` and `.personal_stats` against the Relic endpoints, persisting each raw response verbatim, in `packages/providers/src/aoe2stats_providers/relic/profile.py`
- [ ] T028 [US1] Implement server-side sessions — opaque identifier, `HttpOnly` + `Secure` + `SameSite=Lax` signed cookie, immediate server-side revocation, CSRF `state` tied to the browser session — in `apps/api/src/aoe2stats_api/security.py`
- [ ] T029 [US1] Implement the auth router: `GET /api/auth/steam/start` (with `?link=1` adding a second Steam account instead of replacing the session), `GET /api/auth/steam/callback`, `POST /api/auth/signout`, and `GET /api/me` returning 200 with `{"authenticated": false}` when signed out, in `apps/api/src/aoe2stats_api/routers/auth.py`
- [ ] T030 [US1] Enforce the allowlist at account creation and return `not_allowlisted` with its explanation, reading the allowlist from settings (`BETA_ALLOWLIST_STEAM_IDS`) and stamping `allowlisted_at` on first sign-in for a listed Steam id — without which the closed beta cannot admit its first user — in `apps/api/src/aoe2stats_api/routers/auth.py`
- [ ] T031 [US1] Implement the profiles router: `GET /api/profiles` with current rating, rank and win/loss per leaderboard (FR-008), `POST /api/profiles/{profile_id}/primary` (FR-043), `DELETE /api/profiles/{profile_id}` returning the consequences for archived replays before confirmation (FR-004), in `apps/api/src/aoe2stats_api/routers/profiles.py`
- [ ] T031a [US1] On a successful link, stamp `profile_links.backfill_requested_at` so the next cycle sweeps the preceding 31 days for that profile (FR-015, SC-003 — "queued within one ingestion cycle of linking"). The link itself enqueues nothing: `replay_captures` deadlines are computed from `matches.completed_at`, and no match exists for a profile that has never been polled. T054 consumes the flag — in `apps/api/src/aoe2stats_api/routers/auth.py`
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

- [ ] T039 [P] [US2] Contract test for `ReplayProvider` against frozen fixtures per [contracts/providers.md](./contracts/providers.md) — `ReplayBlob` on 200, `NotFound` on 404, `ProviderRateLimited` raised on 429 and on an unexpected 403, `ProviderUnavailable` raised on 5xx and on timeout — and assert the provider **does not classify** a 404: `NotFound` carries no reason, and the signature admits no `completed_at` from which one could be derived. The three-way reading is the caller's and is tested at T047 — in `packages/providers/tests/test_aoems.py`
- [ ] T040 [P] [US2] Contract test for `MatchHistoryProvider.recent_matches`: batching up to 10 profiles per call, and `RawMatch` carrying the untouched payload alongside the parsed fields, in `packages/providers/tests/test_relic_matches.py`
- [ ] T041 [P] [US2] Contract test for `EnrichmentProvider`: a 403 is expected noise, the circuit breaker opens, the application renders correctly with this provider returning nothing, and `linkedProfiles` is **never** read (FR-045), in `packages/providers/tests/test_companion.py`
- [ ] T042 [P] [US2] Integration test for quickstart scenario 2: a user who declined consent produces zero `replay_captures` rows and zero `provider_calls` rows against the replay endpoint after a cycle — asserting the consent condition is in the `WHERE` clause that selects work, by testing that no code path downstream can reach the provider — in `apps/ingester/tests/test_consent_gate.py`
- [ ] T043 [P] [US2] Integration test for quickstart scenario 3: after linking, cycles run until the backlog is empty; every match from the last 31 days still available is `stored`, anything older is `expired` and nothing else is, each blob is a single-member zip whose sha256 matches the recorded one, and captures cover **all** linked profiles and not only the primary (FR-042, SC-003, SC-005), in `apps/ingester/tests/test_backfill.py`
- [ ] T043a [P] [US2] Integration test for the shared-match case: two consenting users in one game produce exactly one `matches` row and two `replay_captures` rows with distinct `profile_id` and distinct `object_key`; neither user's download reaches the other's blob (FR-016), in `apps/ingester/tests/test_shared_match.py`
- [ ] T044 [P] [US2] Integration test for quickstart scenario 4: a cycle given a two-second budget against ten pending captures stops with some `stored`, the rest `pending` and **none** left `downloading`; a process killed mid-download leaves `downloading` rows that the next cycle reclaims and completes; a stale `downloading` row that already carries `zip_sha256` is resumed at validation and issues no request to the replay endpoint; no blob written twice; no capture `stored` without a retrievable object; and two cycles started concurrently against one queue claim disjoint sets of captures and neither blocks on the other — which is also what happens when two matches finish while a cycle is already running: the next cycle discovers them, and no claim is ever held twice — which is what `FOR UPDATE SKIP LOCKED` is there for (FR-022, FR-023, SC-009), in `apps/ingester/tests/test_interruption.py`
- [ ] T045 [P] [US2] Integration test for quickstart scenario 5: with pending captures whose deadlines are two days and eighteen days out and a budget that allows only half the queue, the **near-deadline** captures are the ones stored, in `apps/ingester/tests/test_deadline_order.py`
- [ ] T046 [P] [US2] Integration test for quickstart scenario 6: three further cycles over an archived capture create no row, change no `stored_at`, rewrite no object and issue no request to the replay endpoint for that match (FR-018, SC-006), in `apps/ingester/tests/test_idempotency.py`
- [ ] T047 [P] [US2] Integration test for quickstart scenario 7: a 404 for a match completed three hours ago leaves the capture `pending` and raises nothing; a 404 for a match completed four days ago yields `pending` on the first attempt and `unavailable` only on the second, with no alert either time; a 404 for a match completed forty days ago yields `expired` **and an alert**; a 429 stops the whole run and alerts; three 500s produce backoff then `failed` at the attempt limit. Every alert asserted here is an `alerts` row written through `raise_alert` (T014a); the one the third point expects is `expired_capture`, severity-1, raised by T056 at the moment of classification. It is **not** `deadline_breach`, which fires at the day-21 capture deadline and is tested by T047b — the two are different kinds with different timings, and asserting either one for the other hides a missing alert (FR-019, FR-020, FR-021), in `apps/ingester/tests/test_failure_classification.py`
- [ ] T047a [P] [US2] Integration test for the quarantine path: a downloaded blob that fails well-formedness validation is **still uploaded**, the row is `quarantined` with `last_error` set, the object is retrievable, and the capture counts in neither `stored_total` nor `expired_total`; an engine that raises and an engine that hangs past the wall-clock cap both yield `quarantined` with `last_error` and the run completes rather than failing (the containment barrier of T055) (FR-026, constitution IV and V), in `apps/ingester/tests/test_quarantine.py`
- [ ] T047b [P] [US2] Integration test for the deadline breach (FR-025): a capture still `pending` with `capture_deadline_at` in the past produces exactly one severity-1 `deadline_breach` row per run whatever the number of offending captures, carries their ids, and is **not** raised for a capture that is `stored`, `unavailable` or `quarantined`; the alert fires at the day-21 deadline and not at expiry, in `apps/ingester/tests/test_deadline_alert.py`
- [ ] T047c [P] [US2] Integration test for the fairness quota (FR-044): with `INGEST_MAX_CAPTURES_PER_USER_PER_RUN` reached, a further capture for that user is deferred — **unless** its `capture_deadline_at` is nearer than `INGEST_QUOTA_EXEMPT_DAYS`, in which case it runs anyway; the count is aggregated across all of one user's linked profiles and never applied per profile; and a second user's captures are unaffected by the first user's quota. The exemption is the whole point of the requirement: a cap that delays an expiring replay to serve a fresh one inverts the priority the system is built on — in `apps/ingester/tests/test_quota.py`
- [ ] T048 [P] [US2] Test for quickstart scenario 11: the liveness check passes against a fresh `ingest_runs` row and **fails** when that row is backdated by 31 hours (FR-024, SC-007), in `scripts/checks/tests/test_cron_liveness.py`

- [ ] T054a [P] [US2] Integration test for the 25-day reconciliation sweep and the outage it exists to absorb (spec.md edge case "the match discovery source is unreachable for several days"): with the match-history provider raising `ProviderUnavailable` for three consecutive cycles and matches completing throughout, the fourth cycle discovers **every** missed match and enqueues a capture for each, none of them past `CAPTURE_BUDGET_DAYS`; and a match that discovery skipped entirely — present at the source, absent from `matches` — is picked up by the sweep rather than waiting for a user to notice. T043 covers the 31-day backfill half of T054; this covers the 25-day half, which is the mechanism the whole capture budget is sized around and which nothing else exercises (FR-013, FR-014), in `apps/ingester/tests/test_reconcile.py`

### Implementation for User Story 2

- [ ] T049 [P] [US2] Implement `ReplayProvider.fetch_replay` against `aoe.ms`, a full in-memory download since the endpoint ignores `Range` and rejects `HEAD` (research §5), returning the taxonomy the contract defines, in `packages/providers/src/aoe2stats_providers/aoems/provider.py`
- [ ] T050 [P] [US2] Implement `MatchHistoryProvider.recent_matches`, batched ten profiles per call, persisting each raw response verbatim into `matches.raw_payload`, in `packages/providers/src/aoe2stats_providers/relic/matches.py`
- [ ] T051 [P] [US2] Implement `EnrichmentProvider.enrich_matches` behind a circuit breaker, treating every failure as normal and ignoring `linkedProfiles` entirely, in `packages/providers/src/aoe2stats_providers/companion/provider.py`
- [ ] T052 [US2] Implement the token bucket at `AOEMS_MAX_REQUESTS_PER_SECOND` against the replay endpoint, serially and with jitter as the `aoe2-data-sources` skill requires, the backoff policy, and the rule that `ProviderRateLimited` stops the entire run and raises a severity-**2** `rate_limited` alert through `raise_alert` (T014a) rather than skipping one capture. Severity 2 and not 1: being throttled costs a cycle, and against a budget measured in days there is always tomorrow — the nightly alert audit fails only on unacknowledged severity-1 rows, and a source that is merely being polite must not stop the CI that watches for actual loss, in `apps/ingester/src/aoe2stats_ingester/ratelimit.py`
- [ ] T053 [US2] Implement discovery: refresh ratings into `rating_snapshots`, fetch recent matches for every consenting user's every linked profile, upsert `matches` and `match_players` — the upsert is also what handles a player who has changed their in-game alias, `aoe_profiles.alias` being the last one observed and never a history — and enqueue `replay_captures` with `capture_deadline_at = completed_at + CAPTURE_BUDGET_DAYS` computed once on insert — read from settings, never restated as a literal, because the whole point of the budget is that it can be lowered in one place the day the retention window is observed to shrink (FR-014) — with consent expressed as a condition of the selecting query (FR-013, FR-042) — in `apps/ingester/src/aoe2stats_ingester/discover.py`
- [ ] T054 [US2] Implement the 25-day reconciliation sweep, and the 31-day backfill for every profile carrying `backfill_requested_at` (T031a) — clearing the flag only once the sweep has enqueued that profile's window, so an interrupted cycle repeats it rather than skipping it (FR-015), in `apps/ingester/src/aoe2stats_ingester/reconcile.py`
- [ ] T055 [US2] Implement capture: claim with `FOR UPDATE SKIP LOCKED` ordered by `capture_deadline_at` ascending, reclaim stale `downloading` rows older than the maximum function duration, download, upload the blob, verify the checksum, **commit `object_key`, `zip_bytes` and `zip_sha256` while the row is still `downloading`**, then validate through the engine interface behind the barrier below, **then** update the row to `stored` or `quarantined` (FR-017, FR-023, FR-026). The blob is uploaded before it is validated and is never discarded on a validation failure — after ~31 days the source has no replacement, so an unparsable capture is evidence, not garbage. A quarantine raises a severity-2 `validation_failed` alert through `raise_alert` (T014a), since nothing else would ever surface it. **Containment (constitution V):** the ingester runs the engine in-process, so an engine failure must not become the run's failure. Validation is called through a barrier that catches `BaseException` and enforces a wall-clock cap; either outcome is `quarantined` with `last_error`, never a failed run, and no exception leaves this module. The one failure the barrier cannot catch — a C-extension fault taking the process down — is survivable only because the bytes were committed one step earlier: the reclaim path resumes at validation for any stale `downloading` row that already carries `zip_sha256`, and never re-downloads a replay it already holds — in `apps/ingester/src/aoe2stats_ingester/capture.py`
- [ ] T056 [US2] Implement the three-way reading of a 404 in the caller from `matches.completed_at`, since the endpoint answers identically in all three cases: younger than `REPLAY_PUBLICATION_GRACE_HOURS` leaves the row `pending` for the next cycle; older than the grace but inside the retention window is `unavailable`, **and only after at least two attempts**; past the window is `expired` and raises a severity-1 `expired_capture` alert through `raise_alert` (T014a). The first branch is the one FR-019 was corrected for: without it a replay published a few hours late is recorded as never recorded, and expires. The two-attempt floor is what makes the grace mean what it says: at a daily cadence a single poll can fall on either side of it, so age alone would let one unlucky 404 close a capture that a second poll would have caught (T012a) — in `apps/ingester/src/aoe2stats_ingester/capture.py`
- [ ] T057 [US2] Implement bounded retries: `next_attempt_at` written on the row with increasing delay and a terminal `failed` status at the attempt limit, never an unbounded retry (FR-020), in `apps/ingester/src/aoe2stats_ingester/capture.py`
- [ ] T058 [US2] Enforce the ingestion quota per user aggregated across all their profiles, never per profile, exempting any capture nearer to its deadline than `INGEST_QUOTA_EXEMPT_DAYS` so the fairness cap can never delay an expiring replay (FR-044). It lives in its own module and **not** in `budget.py`, which `plan.md` defines as the _time_ budget — in `apps/ingester/src/aoe2stats_ingester/quota.py`
- [ ] T059 [US2] Complete `run_once(budget_seconds)`, defaulting to `INGEST_RUN_BUDGET_SECONDS`: **insert the `ingest_runs` row first**, carrying `started_at`, `trigger` and `budget_seconds` and nothing else; then discover, reconcile, drain; then close that same row with `finished_at` and every counter plus `capture_lag_p50_seconds` and `capture_lag_p95_seconds` (FR-024). The row is opened before any work rather than written after it because every alert carries `ingest_run_id`, and four of the five producers fire during the drain (T052, T055, T056) or immediately after it (T059a): a row that did not exist yet would leave them orphaned and `alerts_raised` permanently short. A run that dies leaves an open row with a null `finished_at`, which is a fact worth having rather than a row that was never written — in `apps/ingester/src/aoe2stats_ingester/run.py`
- [ ] T059a [US2] Raise the deadline-breach alert at the end of `run_once`, after the drain and against the still-open `ingest_runs` row T059 inserted at the start, so the alert carries a real `ingest_run_id` and is counted in that row's `alerts_raised`: one aggregate severity-1 `deadline_breach` through `raise_alert` (T014a) carrying the offending capture ids in `detail`, for every capture past `capture_deadline_at` that is neither `stored`, `unavailable` nor `quarantined` (FR-025). One row per run, never one per capture: a backlog would otherwise bury the alert it is supposed to raise. This fires at day 21 with ~10 days left to act, which is the whole difference from `expired_capture` — that one is a post-mortem — in `apps/ingester/src/aoe2stats_ingester/run.py`
- [ ] T060 [US2] Wire `POST /api/cron/ingest` to return 200 with the run report even when individual captures failed, reserving non-200 for a cycle that could not run at all. The logic lives in `run_once()`; this route is a ten-line caller like the cron file, not its authority (see T018) — in `apps/api/src/aoe2stats_api/routers/cron.py` and `api/cron/ingest.py`
- [ ] T061 [US2] Write the external checks and enable their jobs — the cron-liveness check failing past 30 hours, the capture audit asserting `expired_total == 0`, no capture pending beyond `CAPTURE_BUDGET_DAYS` (derived, never a second hard-coded threshold), and the SC-002 lag target — p95 of `stored_at - completed_at` under 48 h over the trailing seven days, computed over **newly discovered** captures only, excluding any whose `first_seen_at` is later than `completed_at + 48 h` since those were already old when we first saw them (backfill, or a cycle that did not run) and would otherwise make the measure report the recovery rather than the cadence — and the alert audit failing on any unacknowledged severity-1 row — in `scripts/checks/cron_liveness.py`, `scripts/checks/capture_audit.py`, `scripts/checks/alert_audit.py` and `.github/workflows/nightly.yml`. The capture audit and the alert audit overlap by design: the first catches a breach even if the ingester never ran to raise the alert, the second catches an alert nobody acknowledged. Neither subsumes the other, and the second is why T059a exists. **Every job added here must also be added to the `needs:` list of the existing `report` job in that workflow**, which currently reads `needs: [contracts, parser-canary]`: `report` is the step that opens the GitHub issue, and a job absent from its `needs` fails in silence. This feature's alerting is pull-based by design — the ingester writes an `alerts` row and this workflow is the only thing that turns it into something a human sees — so an unwired job means constitution I's severity-1 incident is raised into nothing at all (SC-001)
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

- [ ] T063 [P] [US3] Integration test for `GET /api/matches`: newest first, carrying opponent, map, civilisation, result, rating change and duration (FR-010), cursor pagination stable across insertions, in `apps/api/tests/test_matches_list.py`
- [ ] T064 [P] [US3] Integration test for `GET /api/matches/{game_id}`: every participant with team, civilisation, result and rating change (FR-011), in `apps/api/tests/test_match_detail.py`
- [ ] T065 [P] [US3] Integration test for the capture state shown per match (FR-027, SC-010): archived, pending with the time remaining before the window closes, lost, and **needs review** for a `quarantined` capture — four states, the same four the badge in T073 specifies. FR-026 puts a quarantined capture in neither the archived nor the lost column, so a test asserting only three leaves uncovered the one state a user cannot otherwise account for. Plus the empty state for a user with no matches, and the counts, oldest pending and nearest deadline returned by `GET /api/replays/status` (T062), in `apps/api/tests/test_capture_visibility.py`
- [ ] T066 [P] [US3] Integration test for `GET /api/replays/{game_id}/download`: a 302 to a short-lived signed URL (FR-028), a `replay_access_log` row written (FR-040), the bucket never public, and a caller who did not play the match refused, in `apps/api/tests/test_replay_download.py`
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

- [ ] T078 [P] [US4] Integration test for quickstart scenario 8, all four points: uploading the matching file for an `expired` capture yields `stored` flagged manual; a text file renamed `.aoe2record` is rejected with nothing stored; a valid replay for a match the user did not play is rejected; an upload over an existing archive is refused with a reason and does not overwrite (FR-029, FR-030, FR-031, FR-032, FR-033), in `apps/api/tests/test_manual_upload.py`
- [ ] T079 [P] [US4] Unit test for the validation engine against the committed reference replay in `tests/fixtures/replays/` and against truncated, empty and non-replay inputs, in `packages/replay-engine/tests/test_aoe2rec.py`. It sits with the adapter and not in `packages/core`, which holds only the Protocol (T013): a test importing the engine from `core`'s suite would put `replay-engine` in `core`'s dependency graph, which is the exact coupling the split exists to prevent

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
- [ ] T087 [P] [US5] Integration test for quickstart scenario 10 points 2 and 3: erasure requires an explicit confirmation token, removes the user, identities, sessions, links, captures, `replay_access_log` rows and blobs — **verified by listing the bucket, not by trusting the response** — and the erased user's session cookie is refused on the very next request, while `matches` and `match_players` survive with the departing user's `profile_id` pseudonymised (FR-037, FR-039, SC-008), in `apps/api/tests/test_erasure.py`
- [ ] T088 [P] [US5] Integration test for `POST /api/privacy/object`: unauthenticated by design, rate limited, and recording a request for a human rather than pseudonymising immediately (FR-039), in `apps/api/tests/test_third_party_objection.py`
- [ ] T089 [P] [US5] Integration test for the edge case where consent is withdrawn while captures are queued: no further download occurs for that user on the next cycle (FR-035), in `apps/ingester/tests/test_consent_withdrawal.py`

### Implementation for User Story 5

- [ ] T090 [US5] Implement the export job: a `data_requests` row, an archive assembled from the records and the blobs, and a signed URL from `GET /api/privacy/export/{id}`, in `apps/api/src/aoe2stats_api/routers/privacy.py` and `packages/core/src/aoe2stats_core/privacy/export.py`
- [ ] T091 [US5] Implement erasure: confirmation token from a prior `GET`, deletion of the user, identities, sessions, links, captures, their `replay_access_log` rows and the objects, and in-place pseudonymisation of the departing `profile_id` in `matches` and `match_players`, in `packages/core/src/aoe2stats_core/privacy/erasure.py`
- [ ] T092 [US5] Implement `POST /api/privacy/object` with its rate limit and its deferred, recorded resolution, in `apps/api/src/aoe2stats_api/routers/privacy.py`; and write the handling procedure the register's launch item asks for — where an objection lands, who resolves it, within what delay, and the `data_requests` row that is its trace — in `docs/privacy/processing-register.md`. The endpoint alone is half the obligation: `data_requests` already carries `requested_at`, `completed_at` and `outcome`, so what is missing is not a record but the sentence saying who acts on it and by when
- [ ] T093 [US5] Write the privacy notice copy and its component spec — what is collected, on what basis, for how long, how to exercise these rights (FR-041) — in `packages/design-system/specs/`. It is a design-system component and not page markup in `apps/web`, for the reason T098 gives about the footer: constitution VI admits no unstoried component, and these two are the only pieces of copy in the product carrying a legal obligation — neither should be the thing nothing screenshots. T095 builds it from this spec and T096 screenshots it, so the phase's spec-before-component-before-route order holds here as everywhere else
- [ ] T094 [P] [US5] Write the component specs for the privacy screens, including the erasure confirmation whose wording states plainly that it is irreversible, and **the third-party objection form** — the one screen in the product addressed to someone who is not a user and has no session, so it explains what was collected about them and why before it asks for anything (FR-039), in `packages/design-system/specs/`
- [ ] T095 [US5] Build the privacy route — consent state, export request and download, erasure with its confirmation — from tokens with stories, in `apps/web/src/routes/privacy.tsx` and `apps/web/src/features/privacy/`; and the privacy-notice component from T093's spec, in `packages/design-system/src/PrivacyNotice/` with its `*.stories.tsx`, composed by the route in `apps/web/src/routes/privacy-notice.tsx`; and the third-party objection form from T094's spec, on a route **outside the session** at `apps/web/src/routes/object.tsx`, reachable from the privacy notice and the footer. Without it FR-039's "a way to object" is an unauthenticated JSON endpoint, which is not a way for the person it exists for — and the register's balancing test cites that form as the safeguard carrying the legitimate-interest basis for processing third parties
- [ ] T096 [US5] Run `visual-reviewer` then `pnpm test:visual --changed` over the stories added by T095, per constitution VII, updating baselines in `packages/design-system/__screenshots__/`

**Checkpoint**: The service is legally offerable to someone other than its author.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T098 [P] Write the component spec for the site footer carrying the Microsoft Game Content Usage Rules disclaimer, then build it from tokens with its story, in `packages/design-system/specs/`, `packages/design-system/src/Footer/` and its `*.stories.tsx`. It lives in the design system and not in `apps/web`: constitution VI admits no unstoried component, and the disclaimer is the one piece of copy in the product with a legal obligation behind it (constitution X) — it should not be the only thing nothing screenshots
- [ ] T098a Mount the footer in the web shell created by T017 and confirm the same disclaimer in `README.md`, per constitution X, in `apps/web/src/routes/__root.tsx` and `README.md`
- [ ] T098b Run `visual-reviewer` locally then `pnpm test:visual --changed` over the story added by T098, per constitution VII, updating baselines in `packages/design-system/__screenshots__/`
- [ ] T099 [P] Update the verification checklist in `docs/risks.md` to point at the checks that now exist — cron liveness, capture audit, alert audit — without restating any measurement that lives in `docs/data-sources.md`. The three Ingestion lines that this feature's design had already made false — the 24-hour object, the enqueue-on-link, and R1's "pending > 48 h" alert threshold — were corrected during the analysis pass that produced this task, so what remains here is to tick what the new checks now establish and to leave every measurement where it lives. Tick, in the same pass, the launch items in `docs/privacy/processing-register.md` that this feature satisfies. Each item there names the tasks that deliver it, so tick against that list rather than re-deriving it here — a second copy of the mapping is a second thing to keep true. The two items marked out of scope stay open
- [ ] T100 [P] Add the free-tier watch that warns at 70% of any free allowance (R2 bytes, Neon storage, Vercel invocations), raising a severity-2 `free_tier` alert through `raise_alert` rather than only printing a warning, in `scripts/checks/free_tier_watch.py` and `.github/workflows/nightly.yml` — adding this job to the `needs:` list of that workflow's `report` job, without which it fails without opening anything (T061)
- [ ] T101 [P] Enable the full nightly visual regression job across every story in `.github/workflows/nightly.yml`, adding it to the `needs:` list of that workflow's `report` job so a red run opens an issue rather than failing in silence (T061)
- [ ] T102 Add response caching for match history and ratings so a repeat view does not re-query the source, in `apps/api/src/aoe2stats_api/deps.py`. plan.md's 500 ms p95 is a comfort target with no check behind it and stays that way: at closed-beta scale it is not the number worth building a measurement for
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
- **US3 (Phase 5)**: needs Foundational; reads what US2 writes, but its tests seed the database directly and therefore run without US2 — with one exception, T065, which also asserts the counts returned by `GET /api/replays/status` and so needs T062 to exist. T062 is the last task of US2 and the only one US3 reaches into; everything else in this phase is seeded
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
- T009 to T013 and T015 to T017 in Foundational, once T007 and T008 have landed; T012a alongside T012
- All test tasks within a story: T019–T025, T039–T048 and T054a, T063–T068, T078–T079, T086–T089
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
