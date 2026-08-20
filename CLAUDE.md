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

## Where things are written down

Three homes, and the difference matters — putting something in the wrong one is how documentation
starts lying.

| Home | Holds | Lifetime |
| --- | --- | --- |
| `docs/` | **Facts and decisions that outlive any feature.** Measured properties of the outside world (`data-sources.md`), architecture decisions (`adr/`), the risk register. | Living. Must be true *today*; the nightly contract tests exist to keep it so. |
| `specs/NNN-*/` | **One change.** What that feature must do, its plan, its data model, its contracts. Written once, then a historical record of what was decided and why. | Frozen at merge. |
| `.claude/skills/` | **Judgment.** The rules, the traps, what not to do. Loaded into an agent's context on demand, so kept short. | Living, but points at `docs/` for every number. |

The test: *does this need updating when the world changes?* If yes it belongs in `docs/`. If it
describes one change, it belongs in `specs/`. If it tells someone how to behave, it belongs in a
skill.

**Never copy a measurement between them.** A number that exists in two files will be wrong in one of
them. Skills and specs reference `docs/`; they do not restate it. Repeating a *constraint* where it
governs a decision — the 21-day capture budget appears wherever something depends on it — is
different and correct.

## Workflow

Spec-Driven Development with Spec-Kit: `speckit-specify` -> `speckit-clarify` -> `speckit-plan` ->
`speckit-tasks` -> `speckit-analyze` -> `speckit-implement`.
One task in `tasks.md` is one unit of work for the `implementer` agent.

`/speckit-implement` is run **one phase at a time**, naming the task range and the stop condition.
Its own completion criteria otherwise push it through every phase in one context, which is how the
judgment in `tasks.md` gets flattened. Artifacts are amended by hand; `/speckit-plan` and
`/speckit-tasks` are never re-run over a file that already exists.

## Commits

The commit unit is **the smallest set of tasks that was ever simultaneously green**. Sequential
tasks are one commit each, as `tasks.md` asks. A parallel batch is one commit: agents sharing a
working tree interleave in the same files, and splitting that afterwards invents commits that never
existed as a working state and cannot be verified individually.

That granularity only exists at the moment it exists. Commit when a task hands back, *before*
dispatching the next one — a batch launched over an uncommitted predecessor absorbs it permanently,
and no amount of care afterwards gets it back.

Never commit a red tree. The `SubagentStop` gate proves each hand-back green on its own; the commit
re-proves it for the whole batch, because "each passed alone" and "they pass together" are different
claims — and the second is the one the next phase builds on.

The `[x]` in `tasks.md` rides in the same commit as the code that earned it. A checkbox committed on
its own is a claim with no evidence behind it, and it is the one lie this workflow cannot detect.

Messages follow the history already in the log: `type(scope): subject`, lowercase, imperative, no
trailing period. `feat(001):` for implementation work, alongside the existing `spec`, `plan`,
`tasks`, `constitution`, `docs`, `fix` and `chore`. The body lists the task ids the commit closes,
one per line, and any judgment a later reader would otherwise have to re-derive from the diff.

## Model routing

Automatic, not chosen per invocation. `.claude/settings.json` pins the session lead to Sonnet; each
skill and agent declares its own `model:` in frontmatter, which overrides for that turn only and
reverts afterwards. Changing routing means editing the frontmatter, never the model picker.

- **Opus**: constitution, specify, clarify, plan, tasks, analyze, converge, `reviewer`,
  `product-designer`
- **Sonnet**: implement (`implementer`), `visual-reviewer`, session lead
- **Haiku**: checklist, taskstoissues, `researcher`, triage, mechanical tasks

One task in `tasks.md` is one `implementer` invocation. `/speckit-implement` orchestrates and does
not write code itself: the `SubagentStop` hook matches `implementer` and refuses a hand-back on red
tests, so code written outside an agent never meets that gate.

## Commands

- `uv run pytest` / `uv run ruff format .` / `uv run ruff check --fix .` / `uv run mypy`
- `pnpm --filter web dev` / `pnpm --filter design-system storybook`
- `pnpm test:visual` (Playwright, affected stories)
- `vercel dev` (local emulation of the function and cron routes)
