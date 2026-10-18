---
description: 'Task list for shrinking what each production deployment stores — trimmed bundles, a build-skip rule, no pip'
---

# Tasks: Shrink what each production deployment stores

**Input**: Design documents from `/specs/007-shrink-deployment-storage/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included and mandatory. FR-003, FR-009 and FR-014 each require an automated check, and
every other change here is a deployment setting whose failure mode is a production fault, so each
one lands with the test that would have caught it. Python tests follow the green-tree gate: a test
task lands its test marked `xfail(strict=True)` — never a skip — and the implementing task deletes
the marker. Node's test runner has no strict expected-failure, so the skip rule and its test land in
one task (T811).

**Organization**: by the five phases [plan.md](./plan.md) fixes, not by story priority, with the
dropped Story 5 kept as Phase 3's record. The plan orders by risk: the two small independent
stories first, then the bundle dry run (US1, P1), and the skip rule (US2, P2) last, so its first
skip in production is a separate, readable event. Story labels ride on each task.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel — different files, no dependency on an incomplete task
- **[Story]**: US1..US5, mapping to the user stories in [spec.md](./spec.md); setup, ADR and
  acceptance tasks serve no single story and carry none
- **Maintainer** marks a task only the maintainer can do: it needs the host's dashboard, the CLI's
  login or a production secret. An agent prepares everything around it and stops there

## Numbering starts at T801, deliberately

Each feature has numbered from its own hundred (006 from T601), but the T7xx hundred is already taken by
005 and 006 running past their ranges, and `spec_lint.py`'s `task-collisions` check fails on a new
collision. T801 is the first hundred no feature has reached.

## What every implementer must know before starting

**Nothing under `apps/` or `packages/` changes** (FR-016). If a task seems to need an edit there,
the task is wrong — stop and say so. **The three functions stay** (FR-012): Story 5 was dropped,
and no task merges, moves or deletes an entrypoint under `api/`.

**Do not restate a measurement.** The planning-time estimate lives in [research.md](./research.md)
§0; the real before and after figures live in `docs/adr/0002-hosting.md` alone (FR-017). No task,
commit message or comment copies either.

**`.env.local` points at production.** Nothing here needs it. No task runs a script against it.

**Every failure of the skip rule must build.** If a branch of the rule could cancel a build on
anything but a positive proof that nothing shipped changed, it is a defect (FR-007).

## Scenario coverage map

| quickstart section            | Phase | Story    | Task(s) that encode it |
| ----------------------------- | ----- | -------- | ---------------------- |
| §0 — record the before value  | 1     | —        | T801                   |
| §1 — offline gates            | 4–5   | all      | T807, T809, T810       |
| §2 — `pip` is gone            | 2     | US3      | T802                   |
| §3 — CLI upload               | 7     | US4      | T815                   |
| §4 — skip rule in production  | 7     | US2      | T817                   |
| §5 — the three functions answer | 7   | US1      | T816                   |
| §6 — the after value          | 7     | —        | T818, T819             |

---

## Phase 1: Before (plan phase 1)

**Purpose**: the before value can only be read while the current deployment still exists. Nothing in
this feature merges until it is recorded.

- [ ] T801 **Maintainer.** Record the before value (quickstart §0, research R7) in
      `docs/adr/0002-hosting.md`: for the current production deployment, each function's size from
      Deployment → Resources → Functions, and the project's figure from Usage → Deployment Storage →
      Functions Storage → Projects, with the date and the deployment id. Add them under a new
      section heading "Function bundles and build skips", holding only these figures for now; T812
      writes the rest of the section. This is the first half of **FR-017** and of **SC-002**. An
      agent opens the section and the empty table with the date and id columns; the maintainer fills
      the values. The PR does not merge with the table empty

**Checkpoint**: the ADR holds a dated before value with a deployment id.

---

## Phase 2: No installer, no `.claude/` (plan phase 2 — US3, US4)

**Purpose**: two small, independent savings. One commit each.

**Independent test**: quickstart §2, and `.vercelignore` names `.claude/`.

**Story goal (US3)**: production functions carry no `pip`, and the parser loads and parses as
before. **(US4)**: a CLI upload from a working copy carries nothing under `.claude/`.

- [ ] T802 [US3] **First, re-verify the premise, against the locked version** (**FR-013**). Read the
      `aoe2rec-py` version `uv.lock` pins, download its `manylinux_2_28` CPython 3.13 x86-64 wheel
      into an empty scratch directory (not the repository), and search every Python file and the
      native module's strings for `pip`. Research R5 did this for 0.1.24 on 2026-10-18; a different
      locked version means doing it again, not citing R5. **If any runtime reference is found, stop
      here**: Story 3 is dropped, and the reason is recorded in the spec's Assumptions and in the
      ADR section, per US3's first scenario. Otherwise: add
      `override-dependencies = ["pip ; sys_platform == 'never'"]` under `[tool.uv]` in the root
      `pyproject.toml`, with a comment above it saying what it does, why the marker never matches,
      which package declares `pip`, and that the installed wheel was checked and when. Regenerate
      `uv.lock` with `uv lock` and confirm the lock diff is the one marker on `aoe2rec-py`'s `pip`
      edge; any other change in the diff is a resolver surprise to report, not to commit. In the
      same task, add a test to `tests/architecture/test_deployment_install.py` asserting that `pip`
      is not importable in the environment the suite runs in (`importlib.util.find_spec`), so that
      **FR-014** is asserted, not true by construction: a parser release that starts requiring
      `pip` at runtime then fails CI. Run the whole suite, including
      `tests/test_reference_recordings.py`, in the re-synced environment (`uv sync --all-packages
    --dev` removes `pip` from it). Then run quickstart §2's export command and confirm its one line
- [ ] T803 [P] [US4] Add `.claude/` to `.vercelignore` (**FR-015**, research R9), as its own block
      with a comment in the file's existing style: local agent worktrees and agent configuration,
      never an input to the build or a function, and a CLI upload from a working copy does not apply
      `.gitignore`. Anchor it at the root (`/.claude/`). Do not touch any other line; the dry-run
      comparison that proves nothing else dropped is T815

**Checkpoint**: the lock carries the `pip` marker, the suite is green without `pip`, and
`.vercelignore` excludes `.claude/`.

---

## Phase 3: Two functions (US5) — dropped

**Dropped by `/speckit-analyze` on 2026-10-18** (spec Clarifications, plan Constitution Check): a
merged function would run the replay parser in the function that serves the ingestion run, which
constitution V rules out. The three ids are kept so no other id moves; nothing here was done.

- [x] T804 [US5] **Not taken: Story 5 dropped.** Was: repoint the cron entrypoint's tests to
      `api.analyze`, test-first
- [x] T805 [US5] **Not taken: Story 5 dropped.** Was: move the ingestion route into
      `api/analyze.py`, delete `api/cron/ingest.py`, and add a rewrite ahead of the catch-all
- [x] T806 [US5] **Not taken: Story 5 dropped.** Was: repoint the comments that named the deleted
      cron entrypoint

---

## Phase 4: Function bundles carry only `api/` (plan phase 3 — US1) 🎯 MVP

**Purpose**: the largest per-deployment saving, and the one whose failure — a function missing a
file it reads — is worst. Proven offline before any production deploy.

**Independent test**: quickstart §1's `uv run pytest -q`, which includes the guard
(`scripts/checks/tests/test_vercel_bundle.py`) and the bundle-shaped dry run
(`tests/architecture/test_deployment_install.py`).

**Story goal (US1)**: each function holds its entrypoint and its installed dependencies, and every
route behaves as before.

- [ ] T807 [US1] **Tests first.** Create `scripts/checks/tests/test_vercel_bundle.py`, reading the
      real `vercel.json` and `git ls-files`. Assert: exactly three `functions` entries,
      `api/index.py` at the short limit it has today and `api/analyze.py` and
      `api/cron/ingest.py` at the long one, so a later merge of the parser's function with the
      ingestion run fails here (**FR-012**, [contracts/function-layout.md](./contracts/function-layout.md) invariant 1); each entry carries an `excludeFiles` **string**, identical across
      entries (research R1); the string is one brace-glob whose alternatives are each an exact root
      file name or `<dir>/**`, nothing nested and no wildcard in a name; `api` is never an
      alternative; every tracked top-level entry is `api`, an alternative, or on the builder's own
      exclude list, kept as a constant in the test with research R1's source citation; and no
      alternative names an entry that is no longer tracked, so the list stays exact rather than
      only sufficient. Write the matching as small pure functions and give each a planted-defect
      test — a new top-level directory, a nested alternative, a list that covers `api`, an entry
      whose value differs — so the guard is proven to fire, not only to pass today. The assertions
      on today's `vercel.json` are `xfail(strict=True)` until T808. In the same task, add
      `vercel.json` to the `python` paths filter in `.github/workflows/pr.yml`: a pull request
      touching only `vercel.json` must run the Python job, which is where this guard and the dry
      run live. **FR-002**
- [ ] T808 [US1] **Write the `excludeFiles` value** into both entries in `vercel.json` (**FR-001**,
      **FR-002**, research R1), and remove T807's markers. Two checks first, both recorded in the
      commit body and in T812's ADR section. (1) Re-run the search for runtime file reads that are
      not import-time (**FR-003**, the spec's first edge case) over every package production
      installs — the root `pyproject.toml`'s dependencies and the workspace members they reach:
      paths built from `__file__` that climb out of the package, `Path.cwd()`, `os.getcwd()`,
      relative `open()`, and any read of `alembic.ini`, `infra/`, templates or schema files. Name
      the command and its result. Research R1 found none; a hit stops the task. (2) Confirm, in
      the Python builder's source at the version research R1 read, that nothing after the
      exclusion glob reads `pyproject.toml` or `uv.lock` from the bundle at runtime. If that
      cannot be confirmed, leave both out of the exclusion, record why — they weigh kilobytes, and
      a function that fails to boot is an outage no offline check sees — and let T807's guard carry
      the two as a named, reasoned exception. **FR-004**: build the web app with
      `pnpm --filter web build` before and after the change and compare a hash over every file
      under `apps/web/dist`; identical is the only acceptable result, and the commit body says so
- [ ] T809 [US1] **Turn the deployment-install test into the bundle-shaped dry run**
      (**FR-003**, **FR-005**, research R8) in `tests/architecture/test_deployment_install.py`.
      (1) `uv sync --frozen --no-dev --no-editable` into a temporary environment, the builder's own
      flags (research R2); the editable sync it runs today resolves workspace packages to the
      repository and cannot see a missing file. (2) Compute the kept tracked files from
      `vercel.json`'s `excludeFiles` value with the same whole-entry rule T807 asserts, assert the
      kept set is exactly the tracked files under `api/`, and copy them into an empty directory.
      (3) From that directory, run the environment's interpreter in isolated mode (`-I`), which
      drops the working directory from the import path, so put the copy's root on the path
      explicitly, as the runtime does: import `api.index`, `api.analyze` and `api.cron.ingest`; load every packaged
      knowledge snapshot through `aoe2stats_knowledge`'s own loader; assert `pip` is not
      importable; and probe the two long-running routes unauthenticated through each entrypoint's
      own ASGI app, asserting `/api/cron/ingest` answers `401` with `unauthorized` and `/api/analyze`
      answers its `401` session refusal — both before any database connection, with configuration
      supplied the way the existing entrypoint tests supply it. Then run
      `uv run scripts/checks/api_entrypoint_deps.py` and quickstart §1 in full. Keep the module
      docstring honest about what only a real deployment proves (research R8's last paragraph)

**Checkpoint**: the suite proves, offline, that a function holding only `api/` and its installed
dependencies imports, loads its data and answers both long routes.

---

## Phase 5: The build-skip rule (plan phase 4 — US2)

**Purpose**: a commit that changes nothing shipped stores no deployment, and never evicts a
rollback target.

**Independent test**: `node --test scripts/deploy/ignore-build.test.mjs`.

**Story goal (US2)**: a docs-, spec-, test- or baseline-only push to `main` is canceled; anything
that ships still deploys; every doubt deploys.

- [ ] T810 [US2] **Write the rule and its test together** in `scripts/deploy/ignore-build.mjs` and
      `scripts/deploy/ignore-build.test.mjs` (**FR-006**, **FR-007**, **FR-008**, **FR-009**,
      **FR-010**, **FR-011**, **SC-003**; [contracts/build-skip-rule.md](./contracts/build-skip-rule.md), `data-model.md` §2–§5,
      research R3 and R4). The module exports a pure decision over (target environment, base,
      head, changed paths) and a thin entry that reads the three host variables research R3 names,
      checks the base is present in the clone, runs one local
      `git diff --name-only --no-renames <base> <head>` (both sides of a rename, every commit in the
      range), prints exactly one contract output line, and exits per the contract's table. The
      decision order is `data-model.md` §4, verbatim. The whole entry is wrapped so that any
      exception exits 1. No dependency beyond Node's standard library: it runs before any install.
      **No network**: never `git fetch`, never deepen the clone, never call the host's API
      (constitution III). Glob matching is hand-written for the shapes the two lists use
      (`<dir>/**`, a single-segment `*`, a leading `**/`), because CI runs Node 20 and Node's own
      glob matcher is not stable there. Both lists are constants, each pattern with its one-line
      reason beside it: always-deploy is FR-008's concrete paths plus `scripts/deploy/**`, and
      **not** `apps/`, `packages/` or any `src/` directory — those hold their tests and stories, and
      checked first they would deploy every test-only change (FR-008, amended; `data-model.md`
      §3); never-shipped is research R4's table, and nothing else. The test covers, each as a named case:
      **recorded history** — research R4's ranges, with the changed paths captured once now with
      the same `git diff` flags and committed in the test file beside their commit ids and expected
      verdict, so the test needs no history in CI; the docs-only head over an undeployed code
      commit (base `27e2a806^`, head `04970645`) is one of them; **throwaway repository** cases,
      built in a temporary directory with `git init`, for what history cannot show — absent base,
      base not in a shallow clone, empty base, base equal to head (a redeploy builds), a
      non-production target (skips whatever changed), a target that cannot be read (builds), a
      rename from a never-shipped path into a shipped one, a path that matched no list (a new
      top-level directory builds), and a crash inside the rule (exit 1, not 0). Say in the test
      that the rename and baseline-only cases are constructed, not recorded, and why (research R4).
      Every `git commit` in the test passes its identity with `-c user.name=… -c user.email=…`:
      CI has no git identity, and a test that relies on one passes locally and fails there. Finally
      **verdict integrity** (FR-008, amended — overlap between the lists is expected, so the test
      asserts verdicts, not disjointness): for a representative path of every always-deploy
      entry, a change to it alone and beside `docs/risks.md` builds; and each of
      `apps/api/src/aoe2stats_api/app.py`, `apps/web/src/main.tsx`,
      `packages/design-system/tokens/color.json` and
      `packages/knowledge/src/aoe2stats_knowledge/snapshot.py` builds, while a `*.test.tsx`
      under `apps/web/src/` and a `*.stories.tsx` under `packages/design-system/src/` each skip. Run the test with
      `git config --global user.useConfigOnly true` set in a throwaway `HOME` to prove the identity
      point locally
- [ ] T810a [US2] **Before the rule ships, settle how the host counts a canceled deployment**
      against the retained production deployments (spec Edge Cases: "before relying on Story
      2"; the research did not settle it). Read the host's current documentation on deployment
      retention and on canceled deployments; if it does not say, the maintainer reads the
      project's Deployment Retention settings in the dashboard. Record the answer, its source and
      the date in `docs/adr/0002-hosting.md`. **If a canceled deployment takes a retained
      production slot, or the answer cannot be established, T811 does not land in this pull
      request**: Phase 5 moves to its own pull request, held until the answer is known. T810's
      module and test may still land, unwired
- [ ] T811 [US2] **Wire the rule in.** Only after T810a found that a canceled deployment takes
      no retained production slot. Add `"ignoreCommand": "node scripts/deploy/ignore-build.mjs"`
      to `vercel.json` (research R3). In `.github/workflows/pr.yml`, add
      `node --test scripts/deploy/ignore-build.test.mjs` to the `web` job beside the other
      `node --test` suites, with a one-line comment, and add `scripts/deploy/**` to the `web` paths
      filter (the existing `scripts/**` entry triggers only the Python job, the same gap the
      filter's T510 comment records). **Do not** add `scripts/` or `scripts/deploy/` to
      `.vercelignore`: the host runs the rule from the upload, and a rule missing from the upload
      fails the command, which builds — safe, and silently useless. Confirm the dashboard's Ignored
      Build Step is not removed or edited by anything in this change (**FR-011**: branches that
      predate the rule still need it)

**Checkpoint**: the rule exists, is tested offline, and is wired; CI runs its test.

---

## Phase 6: The record (plan phase 5, first half)

- [ ] T812 [P] Close out `docs/adr/0002-hosting.md`'s "Function bundles and build skips" section
      (research R10, **FR-011**, **FR-012**, **FR-017**): the `excludeFiles` rule and why it lists
      every top-level entry but `api`, with T808's two checks and their dates; why the layout
      stays at three functions — the parser never shares a function with the ingestion run
      (constitution V, Story 5 dropped); the skip rule, its
      fail-safe reading, the "Only build production" setting it carries, and **which governs which
      commit** — the rule for commits that contain it, the dashboard setting for branches cut
      before it; the known risk of an empty comparison base (research R3); the next step if storage
      climbs again, replacing the current S3 client with a lighter one behind `packages/storage`;
      and empty, dated rows for the after value and the 30-day skip count. Amend the "Only `main`
      deploys" bullet the same way. Then grep `docs/` and
      `.claude/skills/` for any statement this feature makes false — every push to `main`
      deploys, a function carries the repository, `pip` is installed in production — and correct
      each. No figure from research §0 is copied here
- [ ] T813 Verify scope and the whole tree (**FR-016**). `git diff --stat main...HEAD`: every path
      is a deployment file, `scripts/deploy/`, `scripts/checks/tests/test_vercel_bundle.py`,
      `tests/architecture/test_deployment_install.py`, `.github/workflows/pr.yml`, `docs/` or this
      feature's `specs/` directory. `git diff main...HEAD -- api apps packages` is empty. Then run, by exit code: `uv run pytest`, `uv run ruff format --check .`,
      `uv run ruff check .`, `uv run mypy`, `pnpm --filter web build`,
      `node scripts/checks/spa-routing.mjs`, `node --test scripts/deploy/ignore-build.test.mjs`,
      `uv run scripts/checks/api_entrypoint_deps.py`, `node scripts/checks/config-preflight.mjs
    --contract`, and `uv run scripts/checks/spec_lint.py` over **every** feature directory

**Checkpoint**: the pull request is ready, short of the maintainer's dry run.

---

## Phase 7: Acceptance (plan phase 5, second half — maintainer)

**Purpose**: what only the host, its CLI login or production can show. Each result is recorded in
the ADR section with its date.

- [ ] T814 [P] **Maintainer, before merging.** Read the current production deployment's function
      list (Deployment → Resources → Functions) and save the file listing of one function, for
      SC-001's comparison in T816. If T801 was done long enough ago that a newer deployment now
      serves production, repeat T801 for it
- [ ] T815 [P] [US4] **Maintainer, before merging.** Quickstart §3: `vercel deploy --dry
    --format=json` on `main` and on this branch, from a working copy with
      `.claude/worktrees/`, and diff the two lists (**FR-015**, US4's two scenarios). The only
      paths newly ignored are under `.claude/`. Record the result and the date in the ADR
- [ ] T816 [US1] **Maintainer, after the merge deploys.** Quickstart §5, all five steps:
      the smoke workflow, a real analysis request, a manual ingestion trigger with the production
      `CRON_SECRET` (never written to a file), the next scheduled 04:00 UTC run in the host's cron
      log and in the capture audit, and three functions listed. Read one function's file listing and
      confirm it holds none of the excluded categories (**SC-001**, US1 scenario 2). Zero
      regressions is **SC-005**. Record the run ids and dates in the ADR: the trimmed cron function
      must be seen to import and finish a real capture run (constitution I)
- [ ] T817 [US2] **Maintainer, after T816.** Quickstart §4: a `docs/`-only push to `main` shows
      Canceled with the `skip: nothing shipped …` line, and a `uv.lock` push deploys with
      `build: uv.lock …` (**SC-004**). **Confirm in production what T810a established from the
      documentation**: after the canceled deployment, the three retained production deployments
      are the same three as before it. If they are not, skipping evicts rollback targets: record
      it, and remove `ignoreCommand` from `vercel.json` in a follow-up. If the log shows an
      empty comparison base, record it per research R3's known risk and leave the rule in place.
      Then quickstart §4 step 3, which is not optional: a redeploy of the latest successful
      deployment builds, and the ADR records it as the way to force a deployment (**FR-010**)
- [ ] T818 **Maintainer, after T816.** Quickstart §6: read the after values the way T801 read the
      before ones, record them with the date, the deployment id and the per-deployment ratio to
      T801's (**SC-002**: the band is research §0's). A ratio outside the band is recorded as a
      finding with its likely cause — research R7 names host-side deduplication — not adjusted
- [ ] T819 **Maintainer, 30 days after the rule goes live.** Count the canceled production
      deployments in the host's deployment list, check each against its diff for a shipped path,
      and record the count and the result in the ADR (**SC-006**, **FR-017**)

---

## Dependencies & Execution Order

- **T801 first.** Its figure must exist before anything merges; nothing else waits on it.
- **Phase 2**: T802 and T803 are independent of each other and of everything after them.
- **Phase 3**: dropped; nothing to order.
- **Phase 4**: T807 → T808 → T809.
- **Phase 5** waits on nothing in Phases 2–4 in principle, but lands after them (plan phase 4) so
  the merge is a full deploy anyway. T810 → T810a → T811; T810a can hold T811 back (it says
  when). T811 edits
  `.github/workflows/pr.yml` and `vercel.json`, as T807 and T808 do, so none of the three share a
  parallel batch.
- **T812** after T808 (it records T808's checks); **T813** last before the pull request is
  marked ready.
- **Phase 7**: T814 and T815 before the merge; T816 → T817, T816 → T818; T819 thirty days on.

### User story dependencies

- **US3, US4**: independent.
- **US5**: dropped.
- **US1**: independent.
- **US2**: independent in code; ordered last by the plan.

## Parallel opportunities

- T802 ∥ T803: different files (`pyproject.toml` and `uv.lock` with a test file, against
  `.vercelignore`).
- T812 ∥ T814 ∥ T815: the ADR edit by an agent, two dashboard and CLI reads by the maintainer. The
  maintainer's findings join the ADR after T812.
- Nothing in Phases 4–5 is parallel: each task builds on the previous one's file or layout.

## Implementation strategy

**MVP is US1 (Phase 4)**, the largest per-deployment saving; with T801 it ships alone. Phase 2 is
independent and cheap, so the natural first increment is Phases 1, 2 and 4: before value, `pip`,
`.claude/`, trimmed bundles — every storage saving per deployment. Phase 5 adds the per-commit
saving, and could be a second pull request if the first must ship sooner; T801's value would then
also serve as Phase 5's before figure.

Commit per task, except where a task says it is one unit with another. `/speckit-implement` runs one
phase at a time; Phase 7 is the maintainer's, and an agent stops at T813.
