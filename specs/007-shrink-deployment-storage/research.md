# Research: Shrink what each production deployment stores

Phase 0 of `plan.md`. Each decision states what was chosen, why, and what was rejected. Host
behaviour comes from the host's documentation and the open-source Python builder
(`github.com/vercel/vercel`, `packages/python/src`, last change to that directory on 2026-09-08),
read on 2026-10-18; every claim cites its source. **The figures in §0 are planning-time local
estimates**, the basis of this plan's decisions and of SC-002's prediction. They are not the
feature's measurement: the before and after values from real deployments go to
`docs/adr/0002-hosting.md` (FR-017), and nothing here is copied there.

## 0. Planning-time local estimate (2026-10-18)

Method: `git archive HEAD` into an empty directory (the files a Git-triggered build clones), minus
what `.vercelignore` removes from the upload; production dependencies exported with
`uv export --frozen --no-dev --no-editable` and installed for `x86_64-manylinux_2_28` /
Python 3.13 into a target directory (the wheels the host's Linux build receives). "Zipped" is
`zip -9`, a stand-in for whatever compression the host applies.

| Content per function                             | Raw     | Zipped  |
| ------------------------------------------------ | ------- | ------- |
| Repository files the upload carries              | 41.8 MB | 12.9 MB |
| Built web app (`apps/web/dist`), if present (R1) | 13.7 MB | 6.2 MB  |
| Installed production dependencies, all           | 96.3 MB | 33.0 MB |
| — of which `pip`                                 | 6.3 MB  | 1.9 MB  |
| — of which the knowledge wheel                   | 14.1 MB | 1.0 MB  |

Of the repository files, `packages/knowledge` is 14.7 MB raw (13.1 MB of it `packs/`), and its
packs and snapshots also ship inside the knowledge wheel, so they are stored twice per function.

**Prediction for SC-002.** Before: three functions of about 152 MB raw / 52 MB zipped. After: three
functions holding only their entrypoints and the dependencies, `pip` included (R5), about 96 MB raw /
33 MB zipped each. The after-to-before ratio per deployment is **0.63** raw and **0.63** zipped. The
ratio is the prediction, because it holds whichever of the two the host measures (R7). If the
built web app turns out not to be in today's bundles (R1), the ratio becomes 0.70 raw and 0.72
zipped, still inside SC-002's band. SC-002 is met when the measured ratio is in **0.50–0.76**.
_(Amended twice on 2026-10-18: the first prediction, 0.40 in a band of 0.32–0.48, assumed two
functions, and Story 5 was dropped; the second, 0.59 in a band of 0.47–0.71, assumed `pip` removed,
and Story 3 was dropped.)_

**Deployments that shipped nothing.** Classifying `main`'s 51 first-parent commits since
2026-10-05 with the never-shipped list of R4 gives **25** that would have been skipped, against 14
in the feature description's estimate. The difference is test files, stories and Storybook
configuration, which the description's estimate counted as shipped (R4).

## R1. Excluding repository content from each function

**Decision.** Each function entry in `vercel.json` carries the same `excludeFiles` value: one
brace-glob string whose alternatives are **every top-level entry of the repository except `api`**,
each written as `<dir>/**` or an exact root file name. A guard test fails when a tracked top-level
entry is neither `api`, nor covered by an alternative, nor already dropped by the builder's own
excludes.

**Findings.**

- `excludeFiles` is applied by the Python builder as a glob `ignore` over the project, "relative
  to your project root"
  ([Python runtime docs](https://vercel.com/docs/functions/runtimes/python), "Controlling what gets
  bundled"; builder `packages/python/src/index.ts`, around the `glob('**', { ignore })` call).
- It must be a **string**: the validator rejects any other type (`packages/fs-detectors/src/
detect-builders.ts`). One `functions` entry applies per file (the first key equal to or matching
  the file name), so the value is **repeated in each entry**. A shared `api/**` key would not
  combine with them.
- **It filters the output file list only, after dependency installation.** The builder runs the
  install, then the build command, and only then the glob (builder `index.ts`, `build()`). Workspace
  members are built into wheels and installed before the filter runs, so excluding `apps/**` and
  `packages/**` cannot break installation. This settles the spec's "dependency installation needs a
  file the bundle excludes" edge case.
- Installed dependencies live in the builder's own virtual environment under `.vercel/`, which the
  builder always excludes from the glob, and are copied into the bundle separately. `excludeFiles`
  therefore cannot drop a dependency.
- Built-in excludes (builder `index.ts`): `.git`, `.gitignore`, `.vercel`, `.pnpm-store`,
  `**/node_modules`, `**/.venv`, `**/venv`, `**/__pycache__`, `**/.mypy_cache`, `**/.ruff_cache`,
  `**/public`, and every `pnpm-lock.yaml`, `yarn.lock` and `package-lock.json`. Glob runs with
  dotfiles included.
- The local CLI orders the static build before the Python builder, so `apps/web/dist` exists when
  the Python glob runs and lands in every function. Whether the platform orders builds the same
  way is not documented. Excluding `apps/**` removes it either way.
- No application module reaches a function through the repository copy. Workspace packages use
  a `src/` layout and are installed as wheels; the repository's `apps/*/src` and `packages/*/src`
  are never on the function's import path. A new module added to a runtime package ships inside its
  wheel whatever `excludeFiles` says. This is why excluding all of `apps/**` and `packages/**` does
  not hit FR-002's worry about new application code (see the Structure Decision in `plan.md`).
- Packaged data is read through `importlib.resources` from the installed package
  (`aoe2stats_knowledge.snapshot`, `.query`, `.effects`); no runtime module reads a repository path.

**Why this shape.** Every alternative is a whole directory or an exact file, never a nested
wildcard, so the guard test and the bundle dry run (R8) can reproduce the builder's matching exactly
with a prefix test, and no glob-dialect difference between node-glob and Python can make the two
disagree. The failure direction is benign: a new top-level entry nobody listed ships extra bytes
into the functions, never removes a file a function needs, and the guard test turns even that into a
red CI run.

**Rejected.**

- _Listing only the known-heavy directories_ (`packages/knowledge`, `tests/fixtures`, `docs`, …).
  It leaves every other repository file in, and the next heavy directory ships silently.
- _An include-style pattern such as `!(api)/**`._ It relies on extglob support inside the builder's
  `ignore` option, which is undocumented. The exhaustive brace list gets the same result with
  documented syntax.
- _`includeFiles`._ The Python builder never reads it (no reference in `packages/python/src`).

## R2. How dependencies reach each function

**Finding.** The builder installs with
`uv sync --active --no-dev --link-mode hardlink --frozen --no-editable` (plus a Linux
`--python-platform` off the build image) at the directory holding `uv.lock`, which is the repository
root (builder `uv.ts`, `install.ts`). Each `api/*.py` is a separate builder call, and **each
function gets its own full copy** of the installed dependencies, under `_vendor/`. The on-disk
virtual environment is reused between calls; the bundles are not. Whether the host deduplicates
identical files in Functions Storage is not documented.

**Consequence.** The function count multiplies everything R1 leaves behind, which is what made
FR-012 worth arbitrating. The builder also adds precompiled bytecode "as much as fits"
([changelog, 2026-07-21](https://vercel.com/changelog/python-function-bundles-now-include-precompiled-bytecode)).
That grows with the number of `.py` files bundled, so removing repository `.py` files shrinks it
too. Its exact size is not documented and is measured in the real deployment.

## R3. The build-skip rule

**Decision.** `ignoreCommand: "node scripts/deploy/ignore-build.mjs"`. A Node module with no
dependency beyond Node's standard library, so it runs in the build image before any install. It
implements the decision in `data-model.md` §4 and exits **0 to skip, 1 to build**.

**Findings.**

- Exit semantics: exit 1 continues the build, exit 0 ignores it
  ([vercel.json reference, `ignoreCommand`](https://vercel.com/docs/project-configuration/vercel-json#ignorecommand)).
  The host's knowledge-base guide says any code of 1 or more builds
  ([KB, updated 2026-10-16](https://vercel.com/kb/guide/how-do-i-use-the-ignored-build-step-field-on-vercel)).
  A crash (Node's uncaught-exception exit is 1, `git` failures are 128) therefore **builds**. The
  module also wraps its body in a catch-all that exits 1, so it does not rely on that reading alone.
  The step's timeout is not documented; a timeout that killed the step is assumed to build, and the
  rule does nothing slow (two environment reads and one local `git diff`).
- The vercel.json property **overrides** the dashboard's Ignored Build Step command (same
  reference). It runs when the deployment enters the building state, from the root directory, with
  system environment variables available
  ([project settings](https://vercel.com/docs/project-configuration/project-settings#ignored-build-step)).
- Inputs ([system environment variables](https://vercel.com/docs/environment-variables/system-environment-variables)):
  - `VERCEL_ENV`: the target environment, `production`, `preview` or `development`.
  - `VERCEL_GIT_COMMIT_SHA`: the commit being built.
  - `VERCEL_GIT_PREVIOUS_SHA`: "the last successful deployment for the project and branch". It is
    empty on a branch's first deployment, and is exposed only when an Ignored Build Step is
    configured. A canceled deployment is not successful, so the base stays on the last real build
    across a run of skipped commits, and Story 2's scenario 5 holds by construction. That inference
    is not stated in the docs; the offline test asserts the rule's side of it, and the first skip
    in production confirms the host's side (quickstart §4).
- **Clone depth is 10** ([builds](https://vercel.com/docs/builds)). When more than about nine
  commits have landed since the last successful build, the base is not in the clone, `git diff`
  fails, and the rule builds. The rule never deepens the clone: that would be a network call from
  the build, and FR-007 is satisfied without it.
- The dashboard preset "Only build production" is documented only as issuing a build when the
  target environment is production. Its equivalent is a check of `VERCEL_ENV` against
  `production`, which the rule performs first (FR-011). With `git.deploymentEnabled` limited to
  `main`, the production branch, it cancels nothing today; it is kept for the branches that predate
  the rule, which the dashboard setting still governs.

**Known risk, accepted.** A community thread reports `VERCEL_GIT_PREVIOUS_SHA` always empty for
some projects ([forum](https://community.vercel.com/t/vercel-git-previous-sha-is-always-empty/39835/5)).
If that holds here, the rule builds every time: safe, but Story 2 saves nothing. SC-004's
docs-only push detects it. The fallback is **not** to compare against the parent commit, which
would break scenario 5. It is to record the finding in the ADR and leave the rule in place, safe
and inert, until the host fixes the variable.

**Instant Rollback.** After a rollback in the dashboard, the host stops promoting new production
deployments until the rollback is undone. The skip decision therefore never decides what is live
during a rollback, and needs no special case.

**Rejected.**

- _A Python rule._ The build image is guaranteed to have Node (the build command already runs
  `node scripts/checks/config-preflight.mjs`). A Python interpreter at the ignore step is not
  documented.
- _Asking the host's API for the last production commit._ It needs a token in the build and a
  network call. The documented variable gives the same base.

## R4. The never-shipped list, and how the test proves it

**Decision.** These patterns, each with its reason kept next to it in the module:

| Pattern                                                                        | Why nothing shipped reads it                                                                             |
| ------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------- |
| `docs/**`, `specs/**`, `.specify/**`                                           | Prose and spec-kit artifacts                                                                             |
| `.claude/**`, `.github/**`                                                     | Agent configuration and CI workflows; neither is read by the build or a function                         |
| `tests/**`                                                                     | Root test suites, visual tests and fixtures                                                              |
| `apps/*/tests/**`, `packages/*/tests/**`                                       | Per-package tests; wheels package `src/` only, and the web build compiles `apps/web/src` only            |
| `**/*.test.ts`, `**/*.test.tsx`, `**/*.test.mjs`                               | Test files; the web build is type-checked with no emit and bundles only modules reachable from its entry |
| `**/*.stories.tsx`, `packages/design-system/.storybook/**`                     | Storybook only; nothing under `apps/web` imports a story or the Storybook configuration                  |
| `packages/design-system/__screenshots__/**`, `packages/design-system/specs/**` | Visual baselines (already out of the upload) and design specs                                            |
| `scripts/**`                                                                   | Development and CI tooling, with the two always-deploy exceptions below                                  |
| `README.md`, `CLAUDE.md`, `playwright.config.ts`                               | Root prose and visual-test configuration                                                                 |

The always-deploy list (FR-008) is checked first and includes `scripts/checks/config-preflight.mjs`
and `scripts/deploy/**`, the rule itself. That is what keeps `scripts/**` safe.

**Why test files and stories are in the list.** Neither reaches the build output or a function: the
web app's type-check emits nothing (`noEmit` in `apps/web/tsconfig.app.json`), Vite bundles only
modules reachable from the entry, and no module under `apps/web/src` imports a story or a test
(checked 2026-10-18). A test-only change that broke the type-check would surface on the next shipped
commit's build rather than its own. But `pr.yml` type-checks and builds every pull request, so the
change could not reach `main` broken in the first place. Without these patterns, half of the
skippable commits in §0 would deploy.

**Not in the list, on purpose.** `packages/design-system/src/**` apart from tests and stories,
`packages/design-system/tokens/**` apart from tests, and `packages/game-assets/**`: the web build
reads them. Root configuration such as `.tool-versions`, `.prettierrc.json`, `alembic.ini` and
`pnpm-workspace.yaml` is also left out; it is cheap to deploy for and uncertain to classify.
Anything not listed deploys.

**Test design.**

- _Recorded history fixtures_: the changed paths of real `main` ranges, captured once with
  `git diff --name-only --no-renames`, with the expected verdict. Recording the paths, rather than
  running `git diff` in the test, keeps the test independent of CI's shallow checkout. Initial
  ranges:
  - skip: a docs-only commit (`4513ac6c`), a tasks-only commit (`326bd130`), a tests-and-specs
    commit (`04970645`), a token-test commit (`e394735f`);
  - build: `uv.lock` (`4d99e5a0`), a migration (`754f022a`), root `package.json` and
    `pnpm-lock.yaml` (`b2899e2d`), `vercel.json` and `.vercelignore` (`67ecc12b`), `api/` together
    with docs (`40072fa7`);
  - build: a docs-only head over an undeployed code commit, base `27e2a806^`, head `04970645`.
- _A throwaway-repository test_ (`git init` in a temporary directory) for what recorded paths cannot
  show: an absent base, a base missing from a shallow clone, an empty base, a base equal to the pushed commit (a redeploy, which builds), a non-production target
  environment, a crash inside the rule, and **a rename across the boundary**. `main`'s history holds
  no cross-root rename and no baseline-only commit, so those two shapes are built synthetically.
  This is the one place FR-009's "real commit ranges" is met by a constructed range, and the test
  says so.
- _A verdict-integrity assertion_: a change to any always-deploy path builds, alone or beside a
  never-shipped path, and a non-test, non-story source path of each application package builds.
  _(Amended 2026-10-18 by `/speckit-analyze`: this first asserted that no never-shipped pattern
  matches an always-deploy path, which this section's own `scripts/**` entry contradicts.)_

## R5. Removing `pip`

**Withdrawn 2026-10-18 during `/speckit-implement`: Story 3 is dropped**, and the decision below is
not built. The finding about the wheel holds: re-checked for 0.1.24 against the glibc x86-64 wheel
`uv.lock` pins, which is tagged `manylinux_2_17`/`manylinux2014`, not the `manylinux_2_28` named
below. What this section missed is a consumer inside the repository: `read_engine_dependencies` in
`packages/replay-engine/src/aoe2stats_replay_engine/dependencies.py` records the installed version of every requirement the parser declares and refuses one that
is not installed, and the analyzer's staleness check compares that record with the stored one. With
the override applied the suite went red on exactly that refusal (spec Assumptions). Kept as the
record of what was decided and why it was reversed.

**Findings.**

- `aoe2rec-py` 0.1.24 declares `Requires-Dist: pip>=24.3.1`. Its Linux wheel
  (`aoe2rec_py.cpython-313-x86_64-linux-gnu.so`, `__init__.py`, `summary.py`) contains no reference
  to `pip`, neither in the Python files nor in the native module's strings (checked against the
  `manylinux_2_28` wheel the host installs, 2026-10-18).
- With `override-dependencies = ["pip ; sys_platform == 'never'"]` under `[tool.uv]` in the root
  `pyproject.toml`, `uv lock` keeps `pip` in the lock, with the marker `sys_platform == 'never'` on
  `aoe2rec-py`'s dependency edge. `uv sync --frozen --no-dev --no-editable` then installs no `pip`.
  `import aoe2rec_py` succeeds in that environment, and `importlib.util.find_spec("pip")` is `None`.
  The lock diff is that one edge.
- The development group (`ruff`, `mypy`, `pytest`, `alembic`, `pytest-asyncio`, `types-requests`,
  `Pillow`) needs no `pip`. uv environments are not seeded with `pip`, so CI's environment loses it
  too, and FR-014 holds by construction. The bundle dry run (R8) also asserts it.

**Decision.** The override above, committed together with the regenerated `uv.lock`.

**Rejected.** _Pinning an older `aoe2rec-py`_ gains nothing, since every release declares `pip`.
_Excluding `pip` with `excludeFiles`_ does not work, because installed dependencies are outside
its reach (R1).

## R6. Two functions: where the merged entrypoint lives

**Withdrawn 2026-10-18 by `/speckit-analyze`: Story 5 is dropped**, and nothing below is built. The
merged function would run the native parser in-process in the function that serves the ingestion
run, which constitution V rules out (plan, Constitution Check). Kept as the record of what was
decided and why it was reversed.

**Decision.** `api/analyze.py` becomes the long-running function and gains the ingestion route.
The ingestion handler moves into it unchanged: the secret check, then `run_once` with
`build_ingest_stages`. `api/cron/ingest.py` is deleted. `vercel.json` gains a rewrite from
`/api/cron/ingest` to `/api/analyze`, placed **before** the catch-all `/api/(.*)`, and drops the
`api/cron/ingest.py` function entry. The cron's `path` stays `/api/cron/ingest`.

**Findings.**

- Rewrites run after the filesystem, in array order, and the first match wins (builder
  `packages/routing-utils`; [vercel.json reference](https://vercel.com/docs/project-configuration/vercel-json)).
- A cron is an ordinary GET to the production URL at its `path`
  ([cron jobs](https://vercel.com/docs/cron-jobs)), so a rewrite applies. Cron requests do not
  follow redirects, so it must be a rewrite. That rewrites apply to cron requests is very likely
  but not stated; quickstart §5's manual trigger and the next scheduled run confirm it.
- The ASGI scope carries the original request path (the runtime builds it from the request payload),
  which is how `api/index.py` already serves every `/api/*` path through one rewrite. The merged
  Starlette app therefore declares `/api/analyze` and `/api/cron/ingest` exactly as today.

**Why `api/analyze.py` and not a new file.** About twenty comments and docstrings under `apps/` and
`scripts/` name `api/analyze.py`, against about ten that name `api/cron/ingest.py`. Keeping the
first name leaves the fewer references to repoint. A new name (`api/jobs.py`) reads better but would
send comment-only edits into thirty files of application code, which FR-016 exists to avoid.

**Constitution XII.** The ingester keeps two entrypoints: the cron handler, a short route function
that is now one of two routes in `api/analyze.py`, and `worker.py`. Neither gains logic.

**Rejected.**

- _A private module (`api/_ingest.py`) imported by a thin composer._ The underscore rule for
  non-function files under `api/` and the entrypoint's import path are both undocumented for the
  Python runtime, so an import between files under `api/` is a new failure mode for one saving.
- _Merging into `api/index.py`._ That is option (a), which the clarification rejected.

## R7. Measuring before and after

**Decision.** The maintainer reads, for the production deployment before the change and the first
one after it:

1. Deployment → Resources → Functions: each function's size.
2. Usage → Deployment Storage → Functions Storage → Projects: the project's total, with the date.

Both go into `docs/adr/0002-hosting.md` with the deployment ids (FR-017). The before value is read
**before** merging, because the old deployment may be gone by the time the change lands.

**Unknowns this method tolerates.** Whether the host counts raw or compressed bytes is not
documented, and neither is whether the Resources size is compressed. The prediction is a ratio for
that reason (§0). Deduplication across functions is also undocumented: if the host deduplicates
identical dependency files across the three functions, both values shrink and the measured ratio
can fall outside the band. The
ADR then records that as a finding rather than a miss.

## R8. The bundle dry run (FR-003)

**Decision.** Extend `tests/architecture/test_deployment_install.py`, which already builds a
deployment-shaped environment and imports the entrypoints, into a **bundle-shaped** check:

1. `uv sync --frozen --no-dev --no-editable` into a temporary environment: the builder's own flags
   (R2). Today's test runs an editable sync, which resolves workspace packages to the repository
   and so cannot detect a repository file the bundle lacks.
2. Copy into an empty directory exactly the tracked files `excludeFiles` keeps, computed from the
   value in `vercel.json`, which is `api/**` by construction (R1).
3. With that directory as the working directory and the environment's interpreter run in isolated
   mode:
   - import `api.index`, `api.analyze` and `api.cron.ingest`;
   - load every packaged knowledge snapshot through the package's own loader;
   - probe the two long-running entrypoints' routes unauthenticated, and assert each answers its documented
     refusal without touching a database.

It runs in `pr.yml`'s existing Python job, which already collects `tests/architecture`. This is the
#120-style dry run turned into a gate that keeps running, instead of a one-off. _(Amended
2026-10-18: a step asserting `pip` is not importable left with Story 3, R5.)_

**What only a real deployment confirms.** The host's own builder version, its bytecode fill, and
whether the trimmed functions boot in production. These are covered by quickstart §5 and
SC-005.

## R9. `.claude/` in a CLI upload

**Decision.** Add `.claude/` to `.vercelignore`, next to the existing development-artifact rules.
Verify with `vercel deploy --dry --json` before and after, from a working copy that has local
agent worktrees, and diff the file lists (FR-015). This is the same method as #120 and is run by the
maintainer, since it needs the CLI's login.

## R10. What the ADR records

`docs/adr/0002-hosting.md` gains one section, "Function bundles and build skips". It holds the
`excludeFiles` rule and why, why the layout stays at three functions (R6, withdrawn), the skip rule and its
fail-safe reading, the before and after storage figures with dates and deployment ids, the count of
skipped deployments after the first 30 days, and the next step if storage climbs again: replacing
the current S3 client with a lighter one behind `packages/storage`. The existing "Only `main`
deploys" bullet is amended to say that the dashboard setting governs branches that predate the rule.
