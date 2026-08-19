# aoe2-stats Constitution

## Core Principles

### I. Capture Outranks Analysis (NON-NEGOTIABLE)
Microsoft's replay retention window is approximately 31 days (measured 2026-08-19). An uncaptured
replay is gone forever. Any trade-off between shipping an analysis feature and hardening capture
resolves in favour of capture. No PR may degrade the ingestion pipeline to serve a display feature.
Corollary: `expired_total` must stay at zero; any non-zero value is a severity-1 incident.

### II. Python Backend
FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, uv. Parsing and data analysis are Python. The front
end holds no business logic; it consumes the API.

### III. All External Data Goes Through a DataProvider
`apps/*` and `packages/core` never open an outbound connection. Every external source is a provider
in `packages/providers` with: explicit timeout, retry/backoff, rate limiting, a `provider_calls`
record of every call, and real fixtures for tests. Unit tests never touch the network; only nightly
contract tests do.

Verbatim persistence of the raw response is owed to every source of **irrecoverable data** — data
whose value cannot be obtained again once that source's window closes. A source that can be
re-queried at any time is exempt: a second copy of something still available is a second thing to
keep honest, for no gain. An authentication exchange is not a data source; what it proves is
recorded, its wire form is not. Which sources are irrecoverable is a measured fact and lives in
`docs/data-sources.md`. When it is unclear, the source is irrecoverable — principle I decides ties.

### IV. Raw Is Sacred, Derived Is Disposable
The original replay zip and its HTTP response are stored byte-for-byte with a checksum, never
modified, never deleted (except on a GDPR erasure request). Every derived artifact records the
version of the tool that produced it and must be fully recomputable from the raw. No migration may
ever be required to re-parse history.

### V. Parsing Runs in an Isolated, Pluggable Engine
The parser runs with its own pinned dependencies and no direct write access to application tables
outside its own. An unparsable replay goes to quarantine with the full error, never a silent
failure. A parser crash affects neither the API nor the ingester.
`aoe2rec-py` is primary, `aoc-mgz` secondary, both behind one interface. Being able to swap parsers
is a requirement, not an accident: the primary parser has changed once already.

### VI. Tokens First
No hard-coded colour, spacing, radius, typography or elevation value in a component. Everything
comes from `packages/design-system/tokens`. A component without a Storybook story does not exist.

### VII. Visual Tests Are Mandatory
Every UI component created or modified passes visual-reviewer locally, then Playwright visual
regression on its stories. CI is a court, not a factory: it tests only the stories the diff affects;
full coverage runs nightly.

### VIII. No Secrets in the Clear
Nothing sensitive in the repository, ever. Environment variables, `.env.example` without values,
GitHub Actions secrets and Vercel project environment variables only. No secret in logs, no key in a
URL. Cron endpoints are authenticated by a secret and are never publicly invocable.

### IX. GDPR by Design
We capture only the consenting user's point of view. Third-party players are processed only on the
basis of already-public data and are never publicly indexed. Consent for replay ingestion is
explicit and separate from account creation. Full export and erasure are available from the MVP,
storage objects included. Any new personal data is added to the processing register in the same PR.
**All compute and storage regions are EU.** Vercel functions run in `cdg1`, the database in an EU
region, the object store under EU jurisdiction. A PR that moves a region outside the EU is rejected.

### X. Intellectual Property
Strictly non-commercial. No game asset (icons, civilisation portraits, fonts, sounds, screenshots)
is copied into the repository: the design system evokes the visual language without reusing it. The
Microsoft "Game Content Usage Rules" disclaimer appears in the README and in the site footer.
The hosting plan carries the same constraint: monetizing this project would breach both Microsoft's
rules and Vercel's Hobby terms simultaneously.

### XI. Documentation Is in English
Repository, specs, ADRs, agent and skill definitions, code comments and commit messages are English.

### XII. Portable by Construction
The application must run unchanged on the phase-1 serverless stack and on a phase-2 VPS. Concretely:
all configuration comes from environment variables; no local filesystem state; object storage is
reached only through the S3 API behind `packages/storage`; the database is reached only through
`DATABASE_URL`; and the ingester is a library exposing `run_once(budget_seconds)` with a thin cron
handler and a thin worker loop as its only two entrypoints. Any code that can only run on Vercel, or
only on a VPS, is rejected.

## Technology Constraints

- Backend: Python 3.13, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, uv workspace.
- Front end: Vite + React 19 + TypeScript + TanStack Router/Query + Tailwind, Storybook, Playwright.
- Parsing: `aoe2rec-py` (primary), `aoc-mgz` (secondary).
- Phase 1 hosting: Vercel Hobby (region `cdg1`) + Neon (EU) + Cloudflare R2 (EU jurisdiction).
- Phase 2 hosting: OVH VPS + Docker Compose + OVH Object Storage.
- Data sources: Relic `aoe-api.worldsedgelink.com` (primary), `aoe.ms` (replays), aoe2companion
  (enrichment only, degradable), aoestats (V2 historical corpus only).

## Development Workflow

Spec-Driven Development with Spec-Kit: `speckit-specify` -> `speckit-clarify` -> `speckit-plan` ->
`speckit-tasks` -> `speckit-analyze` -> `speckit-implement`. One task in `tasks.md` is one unit of
work for the `implementer` agent. The `reviewer` agent runs before every merge and rejects any
non-compliant change regardless of technical quality.

## Governance

This constitution outranks every other convention in the repository. Amendments go through a
dedicated PR carrying their rationale, and bump the version below using semantic versioning:
MAJOR for removing or redefining a principle, MINOR for adding one or materially expanding guidance,
PATCH for clarifications that change no behaviour.

**Version**: 1.1.0 | **Ratified**: 2026-08-19 | **Last Amended**: 2026-08-19
