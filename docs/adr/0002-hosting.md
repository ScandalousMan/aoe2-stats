# ADR 0002 — Hosting: Vercel Hobby now, OVH VPS later

- **Status**: accepted
- **Date**: 2026-08-19

## Context

The project needs somewhere to run a React front end, a Python API, a daily ingestion job, a small
relational database, and a permanently growing archive of replay files. The domain is registered at
OVH. The priority for phase 1 is the lowest possible operational burden, not scale.

The original plan was an OVH VPS with Docker Compose (~8.49 EUR/month). The question raised was
whether Vercel Hobby could serve as a simpler starting point.

## The deciding constraint

Vercel Hobby restricts cron jobs to **once per day**, with ±59 minutes of scheduling imprecision.
More frequent expressions fail at deploy time. That looks fatal for an ingestion pipeline.

It is not, because of ADR-adjacent measurement: the replay retention window is several weeks long
(`docs/data-sources.md` §2 holds the current figure) and the internal capture budget is 18 days. A
daily job produces at most ~25 h of detection lag, leaving about 17 days of margin before the budget. Live stats and match history are read from
the Relic API per request, so nothing the user _sees_ is delayed — only archival is batched.

## Corrections to widely-cited limits

- The often-quoted **60 s** Hobby function limit applies only to projects created before April 2025
  without Fluid compute. With Fluid compute, the default for new projects, **Hobby allows 300 s** and
  2 GB / 1 vCPU. At roughly 5 s per replay (download, checksum, upload) that is ~50 replays per run.
- The Python runtime supports **3.12, 3.13 and 3.14**, has a first-class FastAPI preset, reads
  dependencies from `pyproject.toml` with `uv.lock`, and allows a **500 MB** bundle.
- Active CPU is billed only on real CPU time; I/O wait is not counted. The Hobby allowance of
  4 CPU-hours per month is ~26 000 replay parses at the measured 0.54 s each, so even V2 parsing fits.

## Decision

**Phase 1 — 0 EUR/month:**

| Layer          | Choice                                         | Free allowance                                 |
| -------------- | ---------------------------------------------- | ---------------------------------------------- |
| Front end      | Vercel Hobby, Vite + React static build        | 100 GB transfer                                |
| API            | Vercel Python Function, FastAPI, region `cdg1` | 1 M invocations                                |
| Ingestion      | Vercel Cron, once daily, `maxDuration: 300`    | —                                              |
| Database       | Neon free, EU region                           | 0.5 GB storage, 100 CU-hours/month             |
| Replay storage | **Cloudflare R2**, EU jurisdiction             | **10 GB, 1 M writes, 10 M reads, zero egress** |
| Domain         | registered at OVH, DNS pointed at Vercel       | —                                              |

Vercel Blob was rejected for replay storage: its Hobby allowance is about **1 GB**, roughly 660
replays. R2's 10 GB covers ~6 600 replays, about 3.5 years for a single heavy player.

**Phase 2 — OVH VPS**, triggered by any of: R2 exceeding 10 GB, Neon exceeding 0.5 GB, wanting
sub-hour capture lag, or more than ~20 active users. VPS-2 (6 vCore / 12 GB / 100 GB NVMe) is about
8.49 EUR excl. VAT per month, plus OVH Object Storage at 0.0119 EUR/GB/month with egress free since
2026-01-01. The daily cron then becomes a long-lived worker with 5-minute polling.

## Constraints this imposes on the code

Constitution principle XII exists because of this ADR. In particular:

- The ingester is a **library** exposing `run_once(budget_seconds)`. Its only two entrypoints are a
  ~10-line Vercel cron handler (`api/cron/ingest.py`) and a ~10-line worker loop (`worker.py`).
- **No queue broker in phase 1.** `replay_captures.status` is the queue, claimed with
  `SELECT ... FOR UPDATE SKIP LOCKED`. This works identically on Neon and on self-hosted Postgres and
  removes Redis from the phase-1 stack.
- Object storage is reached only through the S3 API behind `packages/storage`. Moving from R2 to OVH
  is four environment variables plus a bulk copy.
- No local filesystem state. Serverless filesystems are ephemeral and read-only outside `/tmp`.
- A run interrupted by its time budget must leave no row in `downloading` and resume cleanly.
- **No deploy hook.** The platform gives no step that runs after a deploy ships and before traffic
  reaches the function, so a bad deploy cannot be blocked from the repository's side. The build
  command (`buildCommand` in `vercel.json`) is therefore the only place left to run a check first —
  `scripts/checks/config-preflight.mjs` is that check today.
- **Only `main` deploys.** Hobby allows 100 deployments per rolling day, and a push to any branch
  creates one even when the project's Ignored Build Step (Vercel project settings, Git) cancels
  it at once. On 2026-10-04 two sessions pushing branches spent the quota and the production
  deploy of a fix was refused. `git.deploymentEnabled` in `vercel.json` turns deployments off for
  branches that contain it — Vercel reads it from the pushed commit, so an older branch still
  deploys until `main` is merged into it. Two mechanisms then decide whether a commit builds, and
  which one governs depends on the commit: for a commit that contains `ignoreCommand` in
  `vercel.json`, that command runs and the dashboard's Ignored Build Step does not; for a branch
  cut before it, the dashboard's Ignored Build Step ("Only build production") governs. See
  "Function bundles and build skips". Nothing in CI reads a preview (`smoke.yml` probes
  production after a push to `main`).
- **The upload carries no test artifact and no secret.** `.vercelignore` keeps visual-test
  baselines, the Storybook build, Playwright output, tool caches and `.claude/` (FR-015) out of
  every deployment, and
  `.env*` files (except `.env.example`, which `config-preflight.mjs` reads) out of a CLI upload,
  since the CLI does not apply `.gitignore`. Deployment storage had reached ~86.9 GB of 10 GB on 2026-10-04.

## Function bundles and build skips

Before value, for the production deployment serving traffic before any of feature 007 merged. A function's
size is read from Deployment → Resources → Functions; the project's figure is read from Usage →
Deployment Storage → Functions Storage → Projects. The maintainer fills the cells from the
dashboard, and the PR for feature 007 does not merge while any of them is empty.

| Measure                                     | Size    | Date read  | Deployment id                       |
| ------------------------------------------- | ------- | ---------- | ----------------------------------- |
| Function `api/index.py`                     | 68.3 MB | 2026-10-18 | `dpl_7cVtADCsXGsHs6iY7SwGJUYmVb7P` |
| Function `api/analyze.py`                   | 68.3 MB | 2026-10-18 | `dpl_7cVtADCsXGsHs6iY7SwGJUYmVb7P` |
| Function `api/cron/ingest.py`               | 68.3 MB | 2026-10-18 | `dpl_7cVtADCsXGsHs6iY7SwGJUYmVb7P` |
| Project: Functions Storage → Projects       | 7.33 GB | 2026-10-18 | —                                   |

The deployment is the production build of `63827989`. The project figure is every stored deployment
of `aoe2-stats` against the plan's 10 GB allowance; no other project on the account stores a
function, so it is also the account's total.

After value and skip count, empty until the maintainer reads them. T818 fills the after rows, in the
same way T801 read the before rows, and T819 fills the skip count.

| Measure                                     | Size | Date read | Deployment id | Filled by |
| ------------------------------------------- | ---- | --------- | ------------- | --------- |
| Function `api/index.py`                     |      |           |               | T818      |
| Function `api/analyze.py`                   |      |           |               | T818      |
| Function `api/cron/ingest.py`               |      |           |               | T818      |
| Project: Functions Storage → Projects       |      |           | —             | T818      |

| Measure                                              | Count | Date counted | Filled by |
| ---------------------------------------------------- | ----- | ------------ | --------- |
| Canceled production deployments, first 30 days live  |       |              | T819      |

### What a function carries

Each of the three functions (`api/index.py` under a 10 s limit, `api/analyze.py` and
`api/cron/ingest.py` under 300 s) carries the Python dependencies the builder installs plus the
repository files its `excludeFiles` entry does not remove. The same value is in all three entries of
`vercel.json`: a brace list of every top-level entry of the repository except `api`, which holds
the three entrypoints. Listing the top-level entries, not their contents, keeps the value short, and
`scripts/checks/tests/test_vercel_bundle.py` compares it with the tracked tree, so a new top-level
entry that is not listed fails the check. The builder's own excludes (`.gitignore`,
`pnpm-lock.yaml`) are not repeated in it. `pyproject.toml` and `uv.lock` are not in the list on
purpose.

Two checks decided that, run on 2026-10-19:

1. The production code reads no file by a path relative to the repository. Over the eight workspace
   members that production installs, plus `api/`, a search for `__file__`, the working directory and
   `.parent` finds nothing, and a search for file opens finds only reads of data packaged inside the
   installed wheels and reads of in-memory archives. Workspace members stay importable without
   `apps/` and `packages/` because the builder always installs them non-editable.
2. `pyproject.toml` and `uv.lock` are not confirmed safe to exclude. In the builder at
   `vercel/vercel` commit `c628be78` (package 13.0.1), a function whose bundle passes the builder's
   size threshold switches to an install at cold start, which runs `uv sync --frozen` in the bundle's
   project root and reads both files. Excluding them would be harmless below the threshold and would
   fail the boot the day a bundle crosses it, so they stay and the check refuses a list that names
   either.

`pnpm --filter web build` produced identical output before and after the exclusion (same checksum
over every file under `apps/web/dist`, same file count).

### Why there are three functions

The layout stays at three functions. The replay parser, which `api/analyze.py` runs in-process,
never shares a function with the ingestion run (constitution V), so `api/analyze.py` and
`api/cron/ingest.py` stay separate, and merging them was dropped from feature 007 (its Story 5).

### The build-skip rule

`ignoreCommand` in `vercel.json` runs `node scripts/deploy/ignore-build.mjs` before a deployment
builds. Exit 0 cancels the build and exit 1 builds. The rule uses Node's standard library only,
makes no network call, reads `VERCEL_ENV`, `VERCEL_GIT_COMMIT_SHA` and `VERCEL_GIT_PREVIOUS_SHA`,
and runs one local `git diff --name-only` between the last successful deployment's commit and the
pushed one. It decides in this order, and the first step that applies ends it:

1. A target environment that is readable and not `production` cancels the build, whatever it
   changes. This is the dashboard's "Only build production" preset carried into the rule.
2. A target environment, comparison base or pushed commit that is unreadable, a base or commit that
   is absent from the clone, or a `git diff` that fails, builds.
3. A diff with no changed path builds. The base is then the pushed commit, which is what a redeploy
   of the latest successful deployment looks like.
4. A changed path on the always-deploy list builds: migrations, dependency and lock files,
   `vercel.json`, `.vercelignore`, `.env.example`, `scripts/checks/config-preflight.mjs`, `api/**`
   and `scripts/deploy/**`.
5. A changed path that no never-shipped pattern matches builds. The never-shipped list covers
   prose, spec-kit and agent configuration, CI workflows, tests, stories and the visual baselines,
   and the rest of `scripts/`.
6. Otherwise the build is canceled.

The rule fails safe: every doubt builds, and so does an exception, because the entry point catches
everything and exits 1. The only cancellation that does not depend on a readable diff is step 1's,
and it applies only when the environment is readable. The rule never deepens the clone and never
asks the host's API. The clone is 10 commits deep, so a base more than about nine commits behind the
pushed commit is absent from it and the build goes ahead.
`VERCEL_GIT_PREVIOUS_SHA` is the last successful deployment of the branch, and a canceled
deployment is not successful, so across a run of canceled commits the base stays on the last
build. The rule's side of that is tested offline; the host's side is confirmed by the first skip in
production.

Known risk, accepted: a community report has `VERCEL_GIT_PREVIOUS_SHA` empty on some projects. If it
is empty here, the comparison base is unreadable, every production deployment builds and the rule saves
nothing. That is safe, and it shows as a docs-only push to `main` that still builds. The rule is
then left in place, and it is not changed to compare against the parent commit, which would build or
cancel by the last commit alone and lose the commits canceled before it.

**Which governs which commit.** For a commit that contains `ignoreCommand`, the property overrides
the dashboard's Ignored Build Step, so the rule governs and carries "Only build production" as its
step 1. For a branch cut before the rule, the pushed commit's `vercel.json` has no `ignoreCommand`
and the dashboard's Ignored Build Step governs. The dashboard setting therefore stays in place.

**The upload, checked on 2026-10-31.** `vercel deploy --dry --json` (Vercel CLI 64.5.0; the flag is
`--json`, and `--format=json` does not exist in this CLI) ran in two detached worktrees linked to the
project, one at `origin/main` `d27ce3fc` and one at this branch `0122b603`. Each was given the same
stand-in agent worktree under `.claude/worktrees/` (two files), because the CLI does not apply
`.gitignore` and a fresh worktree has no `.claude/worktrees/` of its own. It deploys nothing. 24 paths
in main's upload are absent from the branch's, every one under `.claude/`: 15 under `.claude/skills`,
5 under `.claude/agents`, the 2 stand-in files under `.claude/worktrees`, `.claude/launch.json` and
`.claude/settings.json`. No path outside `.claude/` dropped. The paths newly in the `ignored` list are
`.claude/agents`, `.claude/launch.json`, `.claude/settings.json`, `.claude/skills` and
`.claude/worktrees`, and none left it. The paths added are this branch's new files (the `scripts/deploy/`
rule and its test, `scripts/checks/tests/test_vercel_bundle.py` and the feature's specs) and an empty
`.claude` directory entry of size 0, which carries no file. `scripts/deploy/ignore-build.mjs` is
therefore in the upload, as `ignoreCommand` needs.

If storage climbs again, the next step is to replace the current S3 client with a lighter one
behind `packages/storage`. It is not part of feature 007.

`pip` stays installed in production (decided 2026-10-18, feature 007's Story 3 dropped). The replay
parser declares it and never imports it, but `read_engine_dependencies` in `packages/replay-engine/src/aoe2stats_replay_engine/dependencies.py` records the
installed version of every requirement the parser declares and refuses one that is not installed,
and the analyzer's staleness check compares that record with the one stored for each analysis.
Removing `pip` would fail every analysis, and recording it as skipped would make every published
analysis read as stale.

A canceled deployment does not evict a rollback target (read 2026-10-30 from the Vercel
documentation page "Deployment Retention", https://vercel.com/docs/deployment-retention, marked
last updated 2026-09-16). The page lists a Hobby default retention of 30 days for each of four
states: canceled, errored, pre-production and production. A deployment older than its retention
period is kept while any one of these holds: it is among the last 3 deployments created in the
project, it is among the last 3 production deployments in state Ready, or it has a production alias
assigned (the page adds alias cases that do not apply to production on `main`). A canceled
deployment is never in state Ready, so it cannot occupy one of the three Ready-production places
that keep this project's rollback targets. It can occupy one of the "last 3 created" places, but
that exception only keeps deployments and removes none, and the Ready-production exception is
evaluated independently of it. Skipping a build therefore does not evict a rollback target, and T811
may land in the pull request for feature 007. The page does not say in words that a canceled
deployment takes no retained place; the conclusion is derived from the exceptions being
alternatives and from the Ready condition, and T817 and T819 confirm it in production after the
first skip.

## The single-page fallback is a host requirement, not a Vercel setting

Every route the client-side router owns must resolve to `index.html` on a direct request — a
reload, a bookmark, a shared link, a browser restore — not only on an in-app navigation, which
never reaches the origin at all. On Vercel this is one rewrite entry in `vercel.json`, placed below
the `/api/(.*)` rewrite so the API keeps winning; `scripts/checks/spa-routing.mjs` asserts the
ordering holds. Phase 2's OVH reverse proxy does not read `vercel.json` and inherits none of this:
its own configuration needs the equivalent fallback (nginx's `try_files ... /index.html`, or
Caddy's `try_files`), or the same routes will 404 again on the new host, for the same reason.

## Regions: EU only

Vercel functions default to `iad1` (US East). Hobby allows changing the default region, so
**`cdg1` is mandatory**, with Neon in an EU region and the R2 bucket under EU jurisdiction. Given
that archived replays contain third-party players' in-game chat, this is a GDPR requirement, not a
preference. It is written into constitution principle IX.

## Risks accepted

- **A silently stopped cron is invisible** without an always-on process to notice. Mitigation: a
  nightly GitHub Actions job reads the most recent `ingest_runs` row and fails if it is older than
  30 h. This is the single most important monitor on this stack.
- **Free-tier ceilings** could stall ingestion silently. Mitigation: the nightly job warns at 70 % of
  any allowance, so the phase-2 move is planned rather than forced.
- **Cron imprecision** (±59 min, no delivery guarantee). Absorbed by the 18-day budget. Escape
  hatches, in order: 24 separate daily cron entries (allowed — 100 per project — though it leans on
  the letter of the limit), a GitHub Actions scheduled workflow, then Vercel Pro or phase 2.
- **Neon cold starts**: compute suspends after 5 minutes idle, so the daily cron always hits a cold
  database. Use the pooled connection string with a generous connect timeout; a few seconds against
  a 300 s budget is irrelevant.

## A note on terms

Vercel Hobby is limited to non-commercial personal use. This is not an additional constraint:
Microsoft's Game Content Usage Rules already forbid monetizing this project. Both would be breached
by the same decision, which makes it a product question rather than an infrastructure one.
