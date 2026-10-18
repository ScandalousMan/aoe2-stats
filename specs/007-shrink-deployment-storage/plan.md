# Implementation Plan: Shrink what each production deployment stores

**Branch**: `007-shrink-deployment-storage` | **Date**: 2026-10-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/007-shrink-deployment-storage/spec.md`

## Summary

Four changes to the deployment files and one move inside `api/`. No executable line of application
code changes.

1. **Function bundles carry only `api/`** (Story 1). Each function entry in `vercel.json` gets one
   `excludeFiles` brace-glob covering every top-level repository entry except `api` (research R1).
   The builder applies it after installing dependencies, so it cannot break the install. Application
   code reaches a function only through its installed wheel, never through the repository copy, so
   nothing a function runs is lost. A guard test keeps the list exhaustive, and a bundle-shaped dry
   run (R8) imports both entrypoints from a copy holding only `api/` before anything reaches
   production.
2. **A build-skip rule** (Story 2): `ignoreCommand` runs `scripts/deploy/ignore-build.mjs`. It
   cancels a non-production build first (the dashboard's "Only build production", FR-011). It then
   cancels a production build only when every path changed since the last successful deployment is
   on a declared never-shipped list. Any doubt builds. It is covered by recorded-history fixtures
   and a throwaway-repository test (R3, R4).
3. **No `pip` in production** (Story 3): a uv override with a never-true marker, verified against
   the Linux wheel the host installs (R5).
4. **`.claude/` out of a CLI upload** (Story 4): one `.vercelignore` line (R9).
5. **Two functions** (Story 5): `api/analyze.py` also serves `/api/cron/ingest`, reached through a
   rewrite ahead of the catch-all; `api/cron/ingest.py` is deleted; `api/index.py` keeps its 10 s
   limit (R6).

The local estimate predicts a per-deployment storage ratio of 0.40 after to before (research §0).
SC-002 holds when the measured ratio is within 20% of it. The measured values live in
`docs/adr/0002-hosting.md` only.

## Technical Context

**Language/Version**: Python 3.13 (entrypoints under `api/`, the dry-run test); Node 20+ (the
skip rule and its test, same as the other `scripts/checks/*.mjs` modules); JSON (`vercel.json`);
TOML (root `pyproject.toml`).

**Primary Dependencies**: no new dependency. The skip rule uses Node's standard library only
(`node:child_process`, `node:test`), because it runs before any install. Starlette, already
installed, serves the merged entrypoint. uv's `override-dependencies` setting drops `pip`.

**Storage**: N/A. No table, no migration, no object-store change.

**Testing**: `uv run pytest` (the bundle dry run in `tests/architecture`, the entrypoint tests in
`apps/api/tests`, `scripts/checks/tests`); `node --test` for the skip rule, added to `pr.yml` beside
the other `node --test` suites; `node scripts/checks/spa-routing.mjs` for routing order; manual
production checks in `quickstart.md`.

**Target Platform**: the phase-1 host's Python runtime and build image (Linux x86-64, region
`cdg1`). Every change is a deployment-file setting the phase-2 host ignores.

**Project Type**: web application (static front end and Python functions). This feature touches
only its deployment layer.

**Performance Goals**: none new. Cold start may improve slightly with smaller bundles; not claimed.

**Constraints**:

- Changes stay inside the deployment files, `api/`, the skip rule and its test, the checks and
  tests that follow a moved entrypoint, `pr.yml`, and `docs/` (FR-016, as amended below).
- The skip rule makes no network call (constitution III) and fails toward building (FR-007).
- `api/index.py` stays a thin re-export with its short limit (FR-012).
- `scripts/checks/api_entrypoint_deps.py` passes for both remaining entrypoints (FR-005).
- No measurement is copied out of `docs/adr/0002-hosting.md`, except this plan's planning-time
  estimate, which is a different measurement with its own date (research §0).

**Scale/Scope**: about ten files changed, two added (`scripts/deploy/ignore-build.mjs` and its
test), one deleted (`api/cron/ingest.py`).

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design. The verdicts below are
the post-design ones. All twelve principles were walked from `.specify/memory/constitution.md`
itself, not from a previous feature's table._

| #        | Principle                                     | Verdict                       | How this feature satisfies it                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| -------- | --------------------------------------------- | ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **I**    | Capture Outranks Analysis                     | **PASS, with one obligation** | Story 5 moves the cron route, so this feature touches the capture path's entrance. It does not touch its logic. The obligation: the daily ingestion run must keep its long limit and must not fall through to the 10 s function, or a capture run is cut mid-download. The routing check (`spa-routing.mjs`), the dry run's route probe, the manual trigger after the first deploy (quickstart §5) and the next scheduled run all guard it, and the ADR records the run that confirmed it. Everything else here favours capture: smaller deployments keep the project clear of the storage cap that would block deploying a capture fix. |
| **II**   | Python Backend                                | **PASS**                      | The functions stay Python. The skip rule is Node because it runs in the build image before any install. It is deployment tooling like `config-preflight.mjs` and holds no business logic.                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| **III**  | All External Data Goes Through a DataProvider | **PASS, by making no call**   | The skip rule reads environment variables and runs one local `git diff`. It never fetches, never deepens the clone, and never calls the host's API (research R3). No provider is touched.                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| **IV**   | Raw Is Sacred, Derived Is Disposable          | **N/A**                       | No recording, no derived artifact, no object-store path changes.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| **V**    | Parsing Runs in an Isolated, Pluggable Engine | **PASS**                      | The parser's only change is losing an installer it never imports, checked against the native module of the wheel production installs (R5). The reference-recording parses run in an environment without `pip`.                                                                                                                                                                                                                                                                                                                                                                                                                           |
| **VI**   | Tokens First                                  | **N/A**                       | No component, no style.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| **VII**  | Visual Tests Are Mandatory                    | **N/A**                       | No component is created or modified. The static build's output is unchanged (FR-004). Visual baselines stay where they are; a commit touching only them now stores no deployment.                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| **VIII** | No Secrets in the Clear                       | **PASS**                      | No secret, no new environment variable. The cron route keeps its bearer-secret check, moved verbatim. The skip rule reads only non-secret system variables and logs commit ids and paths, never the environment. `.vercelignore` keeps excluding `.env*`.                                                                                                                                                                                                                                                                                                                                                                                |
| **IX**   | GDPR by Design                                | **PASS**                      | No personal data is processed or moved. The region stays `cdg1`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| **X**    | Intellectual Property                         | **PASS**                      | The knowledge packs' licence records still ship inside the knowledge wheel, beside the packs. Only the duplicate repository copy leaves the functions. Nothing is removed from the repository.                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| **XI**   | Documentation Is in English                   | **PASS**                      | Every artifact is English.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| **XII**  | Portable by Construction                      | **PASS**                      | Every change is in `vercel.json`, `.vercelignore`, uv configuration or `api/`, the platform-shaped layer the phase-2 host does not read. No application module learns which host it runs on. The ingester keeps exactly two thin entrypoints: the cron handler, now one route of `api/analyze.py`, and `worker.py`. `run_once(budget_seconds)` is untouched.                                                                                                                                                                                                                                                                             |

**Post-design re-check.** One verdict gained an obligation: I. Before R6 settled where the cron
route lives, the merge looked like a pure deployment concern. It is the entrance to capture, and
the plan now treats a wrong route as a capture fault.

**FR-016 amended by hand (2026-10-18).** As written, FR-016 forbade any edit under `apps/`. But
moving the cron route deletes `api/cron/ingest.py`, which `apps/api/tests/test_cron_ingest_entrypoint.py`
imports and about ten comments name. Leaving them would ship a red test and documentation that lies.
FR-016 now forbids changing any _executable_ line under `apps/` or `packages/`, and permits the test
and comment edits that follow a moved entrypoint. R6 chose the name that minimises those edits.

## Project Structure

### Documentation (this feature)

```text
specs/007-shrink-deployment-storage/
├── plan.md              # This file
├── research.md          # Phase 0: host behaviour, local estimate, decisions R1–R10
├── data-model.md        # Phase 1: bundle, path lists, skip decision, history fixture
├── quickstart.md        # Phase 1: dry runs and production acceptance
├── contracts/
│   ├── function-layout.md   # Which function serves which route, at which limit
│   └── build-skip-rule.md   # The skip rule's inputs, verdicts and exit codes
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
vercel.json                       # functions: two entries, excludeFiles; ignoreCommand; one new rewrite
.vercelignore                     # + .claude/
pyproject.toml                    # [tool.uv] override-dependencies for pip
uv.lock                           # regenerated: one marker on aoe2rec-py's pip edge
api/
├── index.py                      # docstring only: the cron path now reaches api/analyze.py by rewrite
├── analyze.py                    # + the ingestion route, moved verbatim
└── cron/ingest.py                # deleted
scripts/
├── deploy/
│   ├── ignore-build.mjs          # new: the skip rule and its two path lists
│   └── ignore-build.test.mjs     # new: recorded-history fixtures + throwaway-repo cases
└── checks/
    ├── spa-routing.mjs           # the cron path resolves by rewrite to api/analyze, ahead of /api/(.*)
    ├── config-preflight.mjs      # unchanged in behaviour (still reads api/analyze.py's maxDuration)
    └── tests/test_vercel_bundle.py   # new: excludeFiles identical per function and exhaustive
tests/architecture/
└── test_deployment_install.py    # becomes the bundle-shaped dry run (R8)
apps/api/tests/
└── test_cron_ingest_entrypoint.py    # imports the route from api.analyze
.github/workflows/pr.yml          # + node --test for the skip rule; path filters include scripts/deploy
docs/adr/0002-hosting.md          # new section (R10), amended "Only main deploys"
```

**Structure Decision.** A new `scripts/deploy/` directory holds the skip rule, because it is neither
a CI check (`scripts/checks/`) nor an operator tool (`scripts/ops/`). It is something the host runs
during a deployment. The always-deploy list covers the whole directory, so editing the rule always
deploys. The `excludeFiles` value is written exhaustively rather than as "known heavy directories":
FR-002 asks for an excluded list so that new application code is never dropped by default, and R1
shows application code never reaches a function through the repository copy at all, so excluding
every top-level entry but `api` has no such failure mode. The guard test in `test_vercel_bundle.py`
keeps the list honest when a new top-level entry appears.

## Phases

The order follows risk, and each phase is green on its own:

1. **Measure before.** Read the current production deployment's function sizes and the project's
   Functions Storage, and record them in the ADR with the deployment id. This happens before
   anything merges (R7).
2. **`pip` and `.claude/`** (Stories 3 and 4). Small and independent; one commit each.
3. **Two functions** (Story 5): move the route, add the rewrite, and update the tests and checks
   that name the deleted file. It goes before Story 1, so the dry run is written once, against the
   final layout.
4. **Trimmed bundles** (Story 1): the `excludeFiles` value, its guard test, and the bundle-shaped
   dry run.
5. **Skip rule** (Story 2): the module, its tests, `ignoreCommand`, and the `pr.yml` step. This lands
   last, so the merge that ships Stories 1, 3, 4 and 5 is a full deploy that the smoke workflow and
   the manual checks can observe. A skip rule merged in the same push would also deploy (it touches
   `vercel.json`), but keeping it last makes the first skip a separate, readable event.
6. **Measure after and accept.** Quickstart §5–§6, then the ADR section (R10).

## Complexity Tracking

No constitution violation to justify. One deliberate spec amendment, FR-016, is recorded under the
Constitution Check above.
