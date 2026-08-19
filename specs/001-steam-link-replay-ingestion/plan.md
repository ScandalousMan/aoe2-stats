# Implementation Plan: Steam Account Linking and Automatic Replay Ingestion

**Branch**: `001-steam-link-replay-ingestion` | **Date**: 2026-08-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-steam-link-replay-ingestion/spec.md`

## Summary

Let a player prove they own a Steam account, resolve it to their AoE2 profile, and from then on
archive every replay they generate before the publisher deletes it. Presentation — ratings, match
history, match detail — comes along because it is cheap once the data is there, but it is not the
point. The point is that the archive exists.

The approach is deliberately unremarkable: a FastAPI application, a Postgres database, an
S3-compatible bucket, and one job that runs once a day. The interesting decisions are all about what
happens when something fails, because the cost of failure here is asymmetric — a display bug is an
annoyance, a missed capture window is permanent destruction of the user's history.

Three things fall out of that asymmetry and shape everything below: the capture queue lives in the
database rather than in a broker, so an interrupted run resumes rather than losing work; the queue
drains by nearest deadline rather than newest first, so a backlog sheds the replays we can still
re-fetch tomorrow rather than the ones expiring tonight; and the system's own liveness is checked
from outside itself, because a process that is not running cannot report that it is not running.

## Technical Context

**Language/Version**: Python 3.13 (Vercel supports 3.12/3.13/3.14; 3.13 has wheels for every
dependency we need). TypeScript 5 for the front end.

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic, psycopg 3, httpx,
boto3. Front end: Vite, React 19, TanStack Router and Query, Tailwind. `aoe2rec-py` is present for
capture-time validation only; the analysis engine it enables is out of scope here.

**Storage**: PostgreSQL for all relational state. S3-compatible object storage for replay blobs,
reached only through `packages/storage` so the provider is a configuration detail.

**Testing**: pytest with `pytest-asyncio` for the backend, Vitest and Testing Library for the front
end, Playwright for journeys and visual regression. Provider tests run against frozen real responses
in `packages/providers/fixtures/`; the network is unavailable in unit tests by construction.

**Target Platform**: Vercel Functions in region `cdg1`, plus a static front-end bundle. The same code
must run as a long-lived process on a Linux VPS without modification (constitution XII).

**Project Type**: Web service with a separate static front end, in a uv + pnpm monorepo.

**Performance Goals**: A capture cycle handles a day's matches for the closed beta inside a 300 s
function budget — roughly 5 s per replay, so about 50 per run with margin. Match history and ratings
respond in under 500 ms p95 from cached data. These are comfort targets; none of them is the reason
the system exists.

**Constraints**:

- Capture budget of **21 days** against a measured ~31-day retention window. This is the only
  latency number that matters.
- At most **1 request per second** to the replay endpoint, serially, with backoff. Its rate limits
  are undocumented, so we behave as a guest.
- 300 s maximum per function invocation; every unit of work must be interruptible and resumable.
- One cron firing per day, ±59 minutes, no delivery guarantee.
- All compute and storage regions in the EU.

**Scale/Scope**: Closed beta, on the order of 10 to 20 players. Roughly 2.7 GB of replays per active
player per year against a 10 GB free allowance. Around 12 database tables, 5 user stories, 45
functional requirements.

## Constitution Check

*GATE: must pass before Phase 0. Re-checked after Phase 1 design.*

| Principle | How this design satisfies it | Verdict |
| --- | --- | --- |
| **I. Capture outranks analysis** | Capture is user story P2, above all presentation. The queue drains by nearest deadline. `expired_total` is a severity-1 alert. Parsing is deliberately absent. | PASS |
| **II. Python backend** | FastAPI, SQLAlchemy, Alembic, Pydantic. The front end holds no business logic. | PASS |
| **III. DataProvider boundary** | Four providers — `relic`, `aoems`, `steam`, `companion`. `apps/*` and `packages/core` make no outbound calls. Unit tests use frozen fixtures. | PASS |
| **IV. Raw is sacred** | The zip is stored exactly as received with a sha256 recorded at capture. Every provider response is persisted verbatim as `raw_payload`. Nothing derived is authoritative. | PASS |
| **V. Pluggable parser** | Only capture-time validation is in scope, and it goes through the same engine interface the V2 worker will use, so no second integration point is created. | PASS |
| **VI. Tokens first** | Every front-end component is built from design-system tokens, from a product-designer spec, with a story. | PASS |
| **VII. Visual tests** | Diff-scoped visual regression on pull requests; full coverage nightly. | PASS |
| **VIII. No secrets in the clear** | Configuration entirely from environment variables. The cron endpoint requires a shared secret and returns 401 without it. Session cookies are opaque. | PASS |
| **IX. GDPR by design** | Point-of-view capture only; consent separate from account creation; export and erasure covering blobs; third-party objection; replay access logged; all regions EU. FR-045 additionally forbids inferring links between a user's accounts. | PASS |
| **X. Intellectual property** | No game asset anywhere. Disclaimer in README and footer. | PASS |
| **XI. English** | Every artifact in this feature is in English. | PASS |
| **XII. Portable by construction** | The ingester is a library exposing `run_once(budget_seconds)`; the cron handler and the worker loop are each about ten lines. No broker, no local filesystem state, all configuration from the environment. | PASS |

**No violations. Complexity Tracking is empty and stays empty.**

Two points deserve recording because they were live decisions rather than automatic consequences:

- **No queue broker.** Redis with a task queue is the reflex. It is rejected here because
  `replay_captures.status` with `FOR UPDATE SKIP LOCKED` gives the same safety with one less moving
  part, works identically on a serverless platform and on a VPS, and — the decisive property — makes
  the queue *inspectable*. When a replay is missing, the answer is a SQL query, not a broker's
  internal state.
- **FR-045 forbids using data we can technically obtain.** A third-party service publishes a mapping
  between a player's alternate accounts. Using it would improve coverage. It is refused because it is
  an unverifiable claim, and because acting on it would disclose alternate accounts their owners keep
  separate deliberately. The design must never make that inference, even privately.

## Project Structure

### Documentation (this feature)

```text
specs/001-steam-link-replay-ingestion/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── http-api.md
│   └── providers.md
├── checklists/
│   └── requirements.md
├── spec.md
└── tasks.md             # Created later by /speckit-tasks
```

### Source Code (repository root)

```text
api/
└── cron/ingest.py                 # Vercel cron entrypoint. Verifies the secret, calls
                                   # run_once(240), returns the report. Nothing else.

apps/
├── api/src/aoe2stats_api/
│   ├── app.py                     # `app` — the ASGI entrypoint Vercel loads
│   ├── settings.py  deps.py  security.py
│   └── routers/
│       ├── auth.py                # sign-in start, callback, sign-out, session
│       ├── profiles.py            # linked profiles, primary selection, unlink
│       ├── matches.py             # history, detail
│       ├── replays.py             # capture status, download, manual upload
│       ├── privacy.py             # consent, export, erasure, third-party objection
│       └── health.py
├── ingester/src/aoe2stats_ingester/
│   ├── run.py                     # run_once(budget_seconds) — the whole unit of work
│   ├── discover.py                # ratings refresh + match discovery + enqueue
│   ├── reconcile.py               # 25-day sweep for anything missed
│   ├── capture.py                 # claim, download, verify, store, mark
│   ├── budget.py                  # time budget, checked between items, never mid-item
│   ├── ratelimit.py               # token bucket + backoff
│   └── worker.py                  # [phase 2] loop calling run_once()
└── web/src/
    ├── routes/                    # sign-in, dashboard, matches, match detail, privacy
    └── features/{auth,profile,matches,replays,privacy}/

packages/
├── core/src/aoe2stats_core/       # entities, value objects, use cases. No I/O.
├── providers/src/aoe2stats_providers/
│   ├── base.py                    # Protocols, timeout/retry/rate-limit wrappers
│   ├── steam/                     # OpenID 2.0 verification
│   ├── relic/                     # profile resolution, ratings, match history
│   ├── aoems/                     # replay download
│   ├── companion/                 # enrichment, behind a circuit breaker
│   └── fixtures/                  # frozen real responses
└── storage/src/aoe2stats_storage/
    ├── models.py  repositories/   # SQLAlchemy
    └── objects.py                 # S3 client and key scheme

infra/migrations/                  # Alembic
tests/fixtures/replays/            # the committed reference replay
```

**Structure Decision**: The monorepo laid out in `docs/adr/0002-hosting.md`, with two additions this
feature forces. `api/cron/ingest.py` sits at the repository root because Vercel's routing requires
it — it is the one platform-shaped file in the tree, and it is kept to ten lines precisely so that
constitution XII is not quietly violated by a file that cannot be moved. And `packages/providers`
gains a `steam` provider, because Steam sign-in is an outbound call like any other and principle III
admits no exception for authentication.

`apps/parser` is **not** created by this feature. Capture-time validation calls the engine interface
directly; the worker, its queue and the analysis engine belong to V2.

## Complexity Tracking

No constitutional violations. Nothing to justify.
