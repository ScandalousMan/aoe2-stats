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

| Home              | Holds                                                                                                                                                               | Lifetime                                                                      |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `docs/`           | **Facts and decisions that outlive any feature.** Measured properties of the outside world (`data-sources.md`), architecture decisions (`adr/`), the risk register. | Living. Must be true _today_; the nightly contract tests exist to keep it so. |
| `specs/NNN-*/`    | **One change.** What that feature must do, its plan, its data model, its contracts. Written once, then a historical record of what was decided and why.             | Frozen at merge.                                                              |
| `.claude/skills/` | **Judgment.** The rules, the traps, what not to do. Loaded into an agent's context on demand, so kept short.                                                        | Living, but points at `docs/` for every number.                               |

The test: _does this need updating when the world changes?_ If yes it belongs in `docs/`. If it
describes one change, it belongs in `specs/`. If it tells someone how to behave, it belongs in a
skill.

**Never copy a measurement between them.** A number that exists in two files will be wrong in one of
them. Skills and specs reference `docs/`; they do not restate it. Repeating a _constraint_ where it
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

## Working autonomously

The default is to act. An interruption has to buy something an assistant cannot supply alone.

**Do git work without asking** — branch, commit, push, open and update the PR, rebase, resolve a
conflict. Load the `git-workflow` skill first; it carries the ordering and the checks.

**Interrupt for exactly three things, and say which one it is:**

| | Example |
| --- | --- |
| **Validation** — irreversible, outward-facing, or destroys evidence | force-pushing over someone else's work, dropping production data |
| **Information** — only the user has it | a credential, a value from a console, which of two real-world facts holds |
| **Arbitration** — the code cannot settle it | which design to keep, whether to accept a risk, what a requirement should say |

Anything else: decide it, and say what you decided. "Should I proceed?" is a delay with a question
mark on it.

**Never hand back a task because a step needs the user.** Do every part that does not depend on them,
then give the exact commands for the part that does — in order, with the one value they must supply
named. A request for information carries the steps to supply it.

**Retry once before calling something impossible.** A refused call sometimes succeeds in a simpler
shape.

### Say `/clear` and the next spec-kit command first

Both change what the user does next and are worthless once they have acted on something else, so
they lead the message.

- **`/clear`** when the next work shares nothing with what is above it — a finished phase, a pivot,
  a long session about to start something unrelated. Say it even if it ends the session. If the task
  at hand *needs* the session's history as evidence, say that and put the `/clear` after it.
- **The next spec-kit command** — `/speckit-analyze` before merging artifact changes,
  `/speckit-constitution` when an amendment's follow-ups land, `/speckit-implement` scoped to a
  phase. These carry model routing and gates that doing the work conversationally skips silently.

## Commits

The commit unit is **the smallest set of tasks that was ever simultaneously green**. Sequential tasks
are one commit each. A parallel batch is one commit: agents sharing a working tree interleave in the
same files, and splitting that afterwards invents commits that never existed as a working state.

That granularity only exists at the moment it exists. Commit when a task hands back, *before*
dispatching the next one — a batch launched over an uncommitted predecessor absorbs it permanently.

Never commit a red tree, and two ways that has actually failed (2026-08-27, both now gated by
`scripts/hooks/git-preflight.sh`):

- **Run the whole suite, not the failures the agent mentioned.** A hand-back names what the agent
  noticed; verifying only those inherits its blind spot. One reported a single out-of-scope failure;
  the commit went in with **96 tests red**.
- **`tasks.md` does not tell you the commit unit.** It says "never separately green" for the one pair
  it was written about and is silent elsewhere — which is not a claim the rest are green alone. Before
  committing a removal or rename, grep for its consumers; if they are not in the same commit, the unit
  is wrong.

The `[x]` in `tasks.md` rides in the same commit as the code that earned it. A checkbox committed
alone is a claim with no evidence behind it, and it is the one lie this workflow cannot detect.

Messages follow the log: `type(scope): subject`, lowercase, imperative, no trailing period. `feat`,
`spec`, `plan`, `tasks`, `constitution`, `docs`, `fix`, `chore`. The body lists the task ids closed,
one per line, and any judgment a later reader would otherwise re-derive from the diff.

Fetching, branch lifecycle, when to open the PR, and migration deploy sequencing are in the
`git-workflow` skill. Load it before any git action beyond reading status.

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

### Dispatching an implementer

Test-first tasks against the green-tree gate (`xfail(strict=True)`, never a skip), parallel `[P]`
batch rules, and how to remediate a review finding without the fix and its test drifting together
are in the `implementer-dispatch` skill. Load it before dispatching any implementer, inside
`/speckit-implement` or outside it.

## Commands

- `uv run pytest` / `uv run ruff format .` / `uv run ruff check --fix .` / `uv run mypy`
- `pnpm --filter web dev` / `pnpm --filter design-system storybook`
- `pnpm test:visual` (Playwright, affected stories)
- `vercel dev` (local emulation of the function and cron routes)
