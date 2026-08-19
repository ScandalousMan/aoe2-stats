# aoe2-stats

Age of Empires II: DE stats and match analysis. Steam to Relic profile linking, stats, match
history, and automatic replay archival.

**Project law is `.specify/memory/constitution.md`. When in doubt, it decides.**

## Stack

- Backend: Python 3.13, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, uv workspace
- Front end: Vite + React 19 + TypeScript + TanStack Router/Query + Tailwind, Storybook, Playwright
- Parsing: `aoe2rec-py` (primary), `aoc-mgz` (secondary) — see the `replay-parsing` skill
- Phase 1 hosting: Vercel Hobby (region `cdg1`) + Neon (EU) + Cloudflare R2 (EU). 0 EUR/month
- Phase 2 hosting: OVH VPS + Docker Compose + OVH Object Storage

## Hard rules

- No external network call outside `packages/providers`.
- Original replay zips are never modified and never deleted.
- No hard-coded style values: design-system tokens only.
- No secrets in the repository. All configuration from environment variables.
- Nothing may depend on running specifically on Vercel or specifically on a VPS.
- All compute and storage regions are EU.
- English only, everywhere.

## Why the architecture looks like this

The Microsoft replay retention window is about 31 days. An uncaptured replay is lost forever, so
ingestion and raw archival ship in the MVP while parsing and analysis wait for V2.

- `docs/data-sources.md` — every external source, measured, with its traps
- `docs/adr/0001-replay-parser.md` — why aoe2rec-py replaced aoc-mgz
- `docs/adr/0002-hosting.md` — why Vercel Hobby works, and what it forbids in the code
- `docs/risks.md` — the risk register and the verification checklist

## Workflow

Spec-Driven Development with Spec-Kit: `speckit-specify` -> `speckit-clarify` -> `speckit-plan` ->
`speckit-tasks` -> `speckit-analyze` -> `speckit-implement`.
One task in `tasks.md` is one unit of work for the `implementer` agent.

## Model routing

- **Opus**: constitution, specify, plan, reviews (`reviewer`), `product-designer`
- **Sonnet**: implementation (`implementer`), `visual-reviewer`, session lead
- **Haiku**: `researcher`, triage, mechanical tasks

## Commands

- `uv run pytest` / `uv run ruff format .` / `uv run ruff check --fix .` / `uv run mypy`
- `pnpm --filter web dev` / `pnpm --filter design-system storybook`
- `pnpm test:visual` (Playwright, affected stories)
- `vercel dev` (local emulation of the function and cron routes)
