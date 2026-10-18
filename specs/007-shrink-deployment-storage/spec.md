# Feature Specification: Shrink what each production deployment stores

**Feature Branch**: `007-shrink-deployment-storage`

**Created**: 2026-10-18

**Status**: Draft

**Input**: User description: shrink what each production deployment stores on the phase-1 host, so
the project stays well under the Hobby plan's 10 GB Functions Storage allowance — function bundles
that carry only what runs, no stored deployment for a commit that changes nothing shipped, no
unused installer in production, the CLI-upload hole for local agent worktrees closed, and an open
question on merging the three functions. Deleting old deployments and setting the retention policy
are done by hand in the host's dashboard and are out of scope.

## Context

Functions Storage on the Hobby plan is shared by every project on the team and capped at 10 GB.
Going over it can block new deployments and makes the host delete retained deployments at once,
which removes the rollback targets this project relies on after a bad deploy. Since the host's
2026-09-16 retention change keeps only the three most recent production deployments, the project's
footprint is driven by two things this feature controls: **how much each deployment stores**, and
**how many deployments are stored**.

An investigation on 2026-10-18 measured a local working copy and produced estimates of where the
bytes go. Those estimates are not restated here. The plan re-measures them, and every figure —
storage per function and per deployment before and after, and the share of past deployments that
shipped nothing — lives in `docs/adr/0002-hosting.md` alone. What the investigation established
qualitatively, and what this spec builds on:

- Each production deployment ships three Python functions, and the host's Python runtime copies
  almost every repository file into each one. Most of that content — documentation, specs, test
  fixtures, design-system and game-asset sources, the knowledge packs' repository copy, the built
  web app — is never read by any function at runtime.
- The workspace packages are installed as real wheels, so the knowledge packs ship twice per
  function: once inside the installed package, once as repository files.
- No function reads a repository-relative path at runtime; packaged data resolves relative to its
  installed package. The plan re-verifies this claim before anything relies on it.
- An installer package (`pip`) is installed in production only because the primary replay parser
  declares it as a dependency.
- A noticeable share of recent production deployments changed nothing that ships, yet each stored
  three full functions.
- `.vercelignore` does not exclude `.claude/`, which holds local agent worktrees. Only a CLI upload
  from a working copy is affected, but it is an open hole.

`docs/adr/0002-hosting.md` already records the previous round of this work (#120: only `main`
deploys, and the upload carries no test artifact and no secret). This feature continues it from the
upload into the function bundles.

## Clarifications

### Session 2026-10-18

- Q: How many functions should each production deployment hold? → A: Two. `api/index.py` keeps the
  short request limit; the analysis endpoint and the ingestion run share one long-running function.
- Q: What does the Ignored Build Step currently set in the host dashboard do? → A: The host's
  "Only build production" preset: every build whose target environment is not production is
  canceled.

## User Scenarios & Testing _(mandatory)_

The actor throughout is the **maintainer** who merges to `main` and owns the production deployment.
Visitors are affected only indirectly: the site must keep answering exactly as before, and the
rollback targets that protect them must survive.

### User Story 1 - Each function stores only what it runs (Priority: P1)

The maintainer merges a change to `main`. The resulting production deployment's functions contain
the function entrypoints and their installed dependencies, and nothing else from the repository.
Every route, the analysis endpoint and the daily ingestion run behave exactly as before.

**Why this priority**: it shrinks every deployment, including every future one, without changing
how often the project deploys. It is the largest lever that does not depend on the open function
merge question, and it is the one whose failure mode — a function missing a file it reads — is
worst, so it must be proven first.

**Independent Test**: build a copy that holds only what the trimmed bundle will contain, import all
remaining entrypoints from it and exercise each one's module-scope imports (the dry-run shape #120
used), before any production deploy. After the first production deploy, the smoke workflow passes,
a manual analysis request succeeds and a manual trigger of the ingestion run succeeds.

**Acceptance Scenarios**:

1. **Given** the trimmed bundle definition, **When** every remaining entrypoint is imported from a
   copy holding only the bundle's contents, **Then** every import succeeds with no missing module
   and no missing data file.
2. **Given** a production deployment built with the trimmed bundles, **When** its function file
   listing is inspected, **Then** it contains no documentation, spec, test fixture, design-system
   source, game-asset source, built web app or repository copy of packaged data.
3. **Given** that deployment, **When** the smoke workflow runs, an analysis is requested by hand and
   the ingestion run is triggered by hand, **Then** all three succeed.
4. **Given** the deployment before and after this change, **When** the maintainer reads Functions
   Storage per deployment, **Then** both values are recorded with the date in
   `docs/adr/0002-hosting.md` and the after value is lower.

---

### User Story 2 - A commit that ships nothing stores nothing (Priority: P2)

The maintainer merges a commit to `main` that touches only documentation, specs, tests, task files
or visual-test material. The host cancels that production build, nothing is stored, and the
previous deployment keeps serving. A commit that touches anything that ships still deploys in full.

**Why this priority**: it removes whole deployments rather than bytes inside them, and it also stops
a docs-only merge from evicting a real rollback target out of the three retained slots. It ranks
below Story 1 because a wrong skip is a silent production fault, so it carries more risk per byte
saved and needs its own offline proof.

**Independent Test**: an automated test runs the skip decision offline against real commit ranges
from this repository's history and asserts each verdict; no network, no host. After merge, a
docs-only commit on `main` produces a canceled deployment and a commit touching `uv.lock` produces a
full one.

**Acceptance Scenarios**:

1. **Given** a push to `main` whose changes all fall inside the paths declared as never shipped,
   **When** the host evaluates the build, **Then** the build is canceled and no deployment is
   stored.
2. **Given** a push to `main` that touches any path not declared as never shipped — including a path
   that did not exist when the rule was written — **When** the host evaluates the build, **Then** it
   deploys.
3. **Given** a push touching any of the always-deploy paths listed in FR-008, **When** the host
   evaluates the build, **Then** it deploys, whatever else the push contains.
4. **Given** the skip decision cannot be reached — its comparison base is unknown or absent from the
   history, the history is too shallow, or the decision itself errors or times out — **When** the
   host evaluates the build, **Then** it deploys.
5. **Given** a commit that changed shipped code whose production build failed or was canceled,
   followed by a docs-only commit, **When** the host evaluates the docs-only commit, **Then** it
   deploys, because the shipped change is not yet live.
6. **Given** a build whose target environment is not production, **When** the host evaluates it,
   **Then** it is canceled whatever it changes, as the dashboard's "Only build production" setting
   does today.

---

### User Story 3 - No installer in production (Priority: P3)

The production functions no longer contain the `pip` installer, and the replay parser still loads
and parses exactly as before.

**Why this priority**: a small, self-contained saving per function, conditional on a fact that must
be verified first: that the parser never imports `pip` at runtime.

**Independent Test**: inspect the installed parser package — its Python sources and its native
module — for any runtime use of `pip`; then run the full test suite and the parser's reference
recordings in an environment where `pip` is absent.

**Acceptance Scenarios**:

1. **Given** the installed parser package, **When** it is searched for any runtime reference to
   `pip`, **Then** none is found, or this story is dropped and the reason recorded.
2. **Given** an environment resolved with this feature's dependency configuration, **When** its
   installed packages are listed, **Then** `pip` is absent.
3. **Given** that environment, **When** the full test suite and the reference-recording parses run,
   **Then** all pass.

---

### User Story 4 - A CLI upload cannot carry local agent worktrees (Priority: P3)

A maintainer who deploys from a working copy with the host's CLI uploads none of `.claude/`.

**Why this priority**: it closes a hole rather than saving bytes in the normal Git-driven path,
which never sees untracked worktrees.

**Independent Test**: a dry-run CLI deploy from a working copy that contains `.claude/worktrees/`
lists all of `.claude/` as ignored and drops no other file compared with a dry run before the
change.

**Acceptance Scenarios**:

1. **Given** a working copy with local agent worktrees, **When** a dry-run CLI deploy lists its
   upload, **Then** nothing under `.claude/` is uploaded.
2. **Given** the same dry run before and after the change, **When** the two file lists are
   compared, **Then** the only difference is `.claude/`.

---

### User Story 5 - Two functions per deployment instead of three (Priority: P3)

Each production deployment stores two functions: the API function serving ordinary requests under
the short request limit, and one long-running function serving both the analysis endpoint and the
ingestion run.

**Why this priority**: once Stories 1 and 3 are done, most of what remains per function is the
shared dependency set, stored once per function — so the function count multiplies everything
left. Merging the two long-running entrypoints removes one stored copy without giving ordinary
requests the long-running limit, which would let any anonymous request spend that much of the
plan's monthly compute allowance (FR-012).

**Independent Test**: the same copy-only import test as Story 1 over the two remaining entrypoints,
plus a request to the analysis endpoint and a trigger of the ingestion run through the merged
function, plus the time-limit behaviour of an ordinary API request.

**Acceptance Scenarios**:

1. **Given** the two-function layout, **When** the analysis endpoint is called and the ingestion
   run is triggered, **Then** each answers as it did before the merge, with the same
   authentication, and both run under the long-running limit.
2. **Given** the two-function layout, **When** an ordinary API request exceeds the short request
   limit, **Then** it is cut off at that limit and not at the long-running limit.
3. **Given** the scheduled daily trigger of the ingestion run, **When** it fires after the merge,
   **Then** it reaches the long-running function, never the API function.

---

### Edge Cases

- **A function reads a repository file only on a rare path.** An import test proves module-scope
  reads only. The plan must also search every runtime package and entrypoint for file reads that are
  not import-time — packaged data loaded on first use, templates, migrations, schema files — and the
  first-deploy acceptance exercises the analysis and ingestion paths by hand, not only `/api/health`.
- **Dependency installation needs a file the bundle excludes.** The workspace packages are built into
  wheels from their repository sources at deploy time. If excluding repository content took effect
  before installation, installation itself would break. The plan must establish when the exclusion
  applies relative to dependency installation, and prove it on the copy-only dry run.
- **The static web build needs content the functions do not.** The web build reads design-system
  tokens, game assets and `.env.example`. Excluding them from the functions must not exclude them
  from the build; the two are separate and the plan proves the build output is unchanged.
- **The skip decision compares against the wrong base.** Comparing a commit with its parent would
  skip a docs-only commit that follows a failed or canceled deploy of real code, leaving that code
  never deployed. The comparison base is the last commit actually deployed to production; when that
  base is unknown, deploy (Story 2, scenarios 4 and 5).
- **A push carries several commits.** The decision covers every change between the comparison base
  and the pushed commit, not only the last commit.
- **A rename or deletion crosses the boundary.** A file moved from a never-shipped path into a
  shipped one, or a shipped file deleted, counts as touching a shipped path.
- **The skip rule changes itself.** A commit that edits the rule or its list of never-shipped paths
  always deploys, wherever the rule lives.
- **A migration lands with no code change.** `/api/health` reports the deployed build's expected
  schema revision, so a commit under `infra/migrations/` always deploys, and the expand → deploy →
  contract order in the `git-workflow` skill is unaffected.
- **A skipped commit and the smoke workflow.** `smoke.yml` runs on every push to `main`. On a
  skipped commit it probes the previous deployment, which is still the live one and still correct;
  it must keep passing and must not be read as proof that the skipped commit deployed.
- **A canceled deployment and the retention slots.** If a canceled deployment occupied one of the
  three retained production slots, skipping would evict real rollback targets instead of protecting
  them. The plan verifies how the host counts a canceled deployment before relying on Story 2.
- **A long-running route lands on the short function.** Today the ingestion path reaches its own
  file before the catch-all API rewrite applies. After the merge, both long-running routes must
  still resolve to the long-running function ahead of that rewrite; a route that fell through to the
  API function would be cut off at the short limit mid-run. Story 5's scenarios test each route.
- **The daily deployment quota.** A canceled build may still count against the host's daily
  deployment quota. This feature does not claim to save quota; it saves storage.
- **A manual redeploy.** The maintainer must still be able to force a production deployment of a
  skipped commit when they deliberately want one.
- **A branch that predates the rule.** The host reads the build-skip rule from the pushed commit,
  so a branch cut before this feature merged is still governed by the dashboard's "Only build
  production" setting. Removing that setting from the dashboard would let such a branch build a
  preview again (FR-011).
- **Branch pushes.** Only `main` deploys today (`git.deploymentEnabled`); the skip rule must not
  change that, and must not make any branch deploy.
- **A future parser release imports `pip`.** The test suite runs without `pip` installed, so a parser
  upgrade that starts importing it fails CI rather than production.
- **The `pip` exclusion leaks into development.** The dependency configuration is workspace-wide;
  removing `pip` must not break any development tool or script that runs through the workspace
  environment. Scripts run with their own ad-hoc dependencies are unaffected.

## Requirements _(mandatory)_

### Functional Requirements

**Function bundles (Story 1)**

- **FR-001**: Each production function MUST contain only its entrypoint file under `api/` and the
  dependencies installed for it. Repository content that no function reads at runtime MUST be
  excluded from every function.
- **FR-002**: The exclusion MUST be expressed as a list of excluded repository content, so that new
  application code added under a runtime package is never excluded by default. If the plan finds a
  list of included content safer for a specific function, it argues that in the plan.
- **FR-003**: Before the first production deploy, the plan MUST prove FR-001 with an import of every
  remaining entrypoint from a copy that holds only what the bundle will contain, and MUST record
  the search for non-import-time runtime file reads (Edge Cases).
- **FR-004**: The trimmed bundles MUST NOT change the static web build's output.
- **FR-005**: `scripts/checks/api_entrypoint_deps.py` MUST still pass for every remaining entrypoint.

**Build skip (Story 2)**

- **FR-006**: A production build MUST be skipped when, and only when, every change between the last
  commit deployed to production and the pushed commit falls inside a declared list of never-shipped
  paths.
- **FR-007**: The rule MUST fail safe. Any path not in the never-shipped list, any unknown or missing
  comparison base, any history too shallow to compare, and any error or timeout in the decision MUST
  result in a deploy.
- **FR-008**: The rule MUST always deploy a change touching any of: `infra/migrations/`, any
  `pyproject.toml`, `uv.lock`, any `package.json`, `pnpm-lock.yaml`, `vercel.json`,
  `.vercelignore`, `.env.example`, `scripts/checks/config-preflight.mjs`, `api/`, application source
  under `apps/` or `packages/`, the web app, and the skip rule's own definition. A never-shipped
  entry that would match one of these paths is a defect the test in FR-009 MUST catch.
- **FR-009**: An automated test MUST run the skip decision offline against real commit ranges from
  this repository's history and assert the expected verdict for each, including at least: a
  docs-only commit, a spec-only commit, a test-only commit, a visual-baseline commit, a commit
  touching `uv.lock`, a migration commit, a mixed commit, a rename across the boundary, a docs-only
  commit that follows an undeployed code commit, and a non-production build of a commit that would
  otherwise deploy.
- **FR-010**: The rule MUST NOT make any branch other than `main` deploy, and MUST NOT prevent a
  deliberate manual production redeploy.
- **FR-011**: The new rule MUST carry the existing Ignored Build Step's behaviour — the host's
  "Only build production" preset in the project settings — before its path decision: a build whose
  target environment is not production is canceled whatever it changes, and only a production
  build goes on to FR-006. When the target environment cannot be read, FR-007 applies and the build
  proceeds. The dashboard setting MUST stay in place, because a branch whose commits predate the
  new rule is still governed by it. `docs/adr/0002-hosting.md` records which of the two governs
  which commit.

**Function layout (Story 5)**

- **FR-012**: Each production deployment MUST hold exactly two functions: `api/index.py`, which
  keeps the short request limit and stays a thin re-export around the application factory, and one
  long-running function that serves both the analysis endpoint and the ingestion run under the
  long-running limit. Both routes MUST keep their public paths, methods and authentication, and the
  scheduled ingestion trigger MUST reach the long-running function. The ingestion handler MUST keep
  its thin-entrypoint shape around `run_once` (constitution XII). The merge MUST stay under `api/`
  and in `vercel.json`; the layout and its reason are recorded in `docs/adr/0002-hosting.md`.

**Installer (Story 3)**

- **FR-013**: `pip` MUST NOT be installed in production, provided the installed parser package is
  shown never to import it at runtime. The verification MUST inspect the installed package that
  production receives, not its documentation.
- **FR-014**: The test suite MUST run in an environment without `pip`, so a future parser release
  that imports it fails CI.

**Upload (Story 4)**

- **FR-015**: `.vercelignore` MUST exclude `.claude/`, and a dry-run CLI upload MUST show no other
  file dropped.

**Scope and records**

- **FR-016**: Every change MUST stay within the deployment files — `vercel.json`, `.vercelignore`,
  the root `pyproject.toml` and its dependency configuration, `uv.lock`, any script the skip rule
  needs and its test, and the entrypoints under `api/` for FR-012 — and MUST NOT change any
  executable line of application code under `apps/` or `packages/`. Tests, checks and comments that
  name a moved or deleted entrypoint MUST follow it, so that no test goes red and no comment names
  a file that no longer exists. *(Amended 2026-10-18 by `/speckit-plan`: as first written, this
  forbade those edits too, which the deleted cron entrypoint makes impossible.)*
- **FR-017**: `docs/adr/0002-hosting.md` MUST record, with dates: storage per function and per
  production deployment before and after, the number of deployments skipped once the rule is live,
  and, as the next step if storage climbs again, replacing the current S3 client with a lighter one
  behind `packages/storage`. This spec, the plan and any skill reference those figures and never
  copy them.

### Key Entities

- **Production deployment**: one build of `main` that the host stores and may retain as a rollback
  target; holds the static site and one stored copy of each function.
- **Function bundle**: what the host stores for one function in one deployment — its entrypoint, its
  installed dependencies, and whatever repository content is not excluded.
- **Never-shipped path list**: the declared repository paths whose changes cannot affect the
  deployed site or functions; the only input that can make a build skip.
- **Comparison base**: the last commit actually deployed to production; the skip decision compares
  the pushed commit against it.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: A production deployment after this feature contains zero repository files from the
  excluded categories in any function, verified by inspecting its function file listings.
- **SC-002**: Storage per production deployment is lower after the change than before, both values
  recorded with the date in `docs/adr/0002-hosting.md`, and the measured after value is within 20%
  of the value the plan predicts from its re-measurement.
- **SC-003**: The offline skip test agrees with the expected verdict on 100% of its commit ranges,
  with zero shipped commits classified as skippable.
- **SC-004**: After merge, a docs-only commit on `main` produces a canceled deployment, and a commit
  touching `uv.lock` produces a full deployment.
- **SC-005**: After the first production deploy, the smoke workflow passes, a manual analysis
  request succeeds and a manual trigger of the ingestion run succeeds — zero regressions in the
  three entrypoints' behaviour.
- **SC-006**: Over the 30 days after the rule goes live, no commit that touched a shipped path was
  skipped, checked against the production deployment list.

## Assumptions

- The figures in the feature description are estimates from a local working copy; a Git-triggered
  deployment clones tracked files only, so the plan re-measures from a Git-shaped copy and the ADR
  holds the result.
- The host offers a per-function exclusion setting and a build-skip command declared in
  `vercel.json`; the feature description names them (`excludeFiles`, `ignoreCommand`). The plan
  confirms each against the host's current documentation, including when the exclusion applies
  relative to dependency installation.
- A dependency override whose marker never matches is the likely way to keep `pip` out of the
  resolution; the plan confirms it with the resolver in use. A preliminary search of the locally
  installed parser package found no reference to `pip`; the plan repeats it on the Linux build
  production installs.
- Deleting old deployments and setting the retention policy are done by hand in the dashboard and
  are out of scope, as is replacing the S3 client (recorded in the ADR as the next step, FR-017).
- The host's deployment-count quota is unaffected by this feature and is not a goal of it.
- Configuration stays portable (constitution XII): every change is a deployment-file setting the
  phase-2 host simply ignores, and no application code learns which host it runs on.
