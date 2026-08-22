# Implementation Plan: Community Reference Data Sources

**Branch**: `002-reference-data-sources` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-reference-data-sources/spec.md`

## Summary

Two deliverables, one purpose. A new `docs/reference-data.md` records the three community
repositories this project consults when the game changes — what each holds, its licence and the date
that was checked, and the procedure for re-deriving and verifying the civilisation mapping. A new
nightly check, `scripts/checks/civ_coverage.py`, reads the match data already stored here and reports
any civilisation identifier the mapping cannot name.

The documentation answers _how_; the check answers _when_. Feature 001 proved both halves are needed:
the mapping was wrong for months of work and nobody knew, and the correction was only possible
because somebody thought to join two fixtures. Neither the knowledge nor the trigger existed.

## Technical Context

**Language/Version**: Python 3.13 for the check; Markdown for the documentation.

**Primary Dependencies**: none new. The check imports `aoe2stats_storage` for the models and reads
the civilisation table from `apps/api/src/aoe2stats_api/civilizations.py`, exactly as
`scripts/checks/capture_audit.py` already imports storage.

**Storage**: reads the existing Postgres database — `match_players.civ_id` — through the pooled
connection string the sibling checks already use. No schema change, no migration.

**Testing**: pytest, under `scripts/checks/tests/`, which T061a brought inside the `python` job's
path filter and under `ruff` and `mypy`.

**Target Platform**: GitHub Actions nightly, alongside `cron-liveness`, `capture-audit` and
`alert-audit`. Nothing platform-specific (constitution XII).

**Project Type**: documentation plus one auditing script. No application code, no UI, no endpoint.

**Performance Goals**: not applicable. One aggregate query per night over a beta-scale table.

**Constraints**: the check makes no network call of any kind, and in particular never fetches a
reference source (FR-014). Its output carries identifiers and counts only, never a profile id or an
alias (constitution IX — see the Constitution Check below, where this is a real constraint rather
than a formality).

**Scale/Scope**: 59 mapping entries today; one documentation file, one check, one workflow job, one
skill amendment.

## Constitution Check

_GATE: must pass before Phase 0. Re-checked after Phase 1 design._

| Principle                         | How this design satisfies it                                                                                                                                                                                                                                                                                                                                                             | Verdict |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- |
| **I. Capture outranks analysis**  | Touches neither capture nor its budget. The check is read-only and runs after the fact; a failure here costs a name on a screen, never a replay. It runs in the nightly workflow beside the capture audit rather than in the ingestion path, so it cannot slow or fail a cycle.                                                                                                          | PASS    |
| **II. Python backend**            | Python 3.13, in `scripts/checks/`, matching the four scripts already there.                                                                                                                                                                                                                                                                                                              | PASS    |
| **III. DataProvider boundary**    | The check opens no outbound connection. It reads the database and two in-repository modules. The three reference sources are consulted **by a human**, never by this code, at any time — that is FR-014 and it is the principle's plainest reading. No provider is added, because nothing here is a data source the product calls.                                                       | PASS    |
| **IV. Raw is sacred**             | Reads only. Writes nothing to the database and nothing to the object store.                                                                                                                                                                                                                                                                                                              | PASS    |
| **V. Pluggable parser**           | No engine involved. The check imports neither `packages/replay-engine` nor `aoe2rec_py`.                                                                                                                                                                                                                                                                                                 | PASS    |
| **VI. Tokens first**              | No component. The civilisation name reaches the interface through the existing API field, which already renders inside components built at T074.                                                                                                                                                                                                                                         | PASS    |
| **VII. Visual tests**             | No story changes, so nothing to screenshot. The badge and the row already have baselines from T077 and this feature does not alter them.                                                                                                                                                                                                                                                 | PASS    |
| **VIII. No secrets in the clear** | The check reads `DATABASE_URL` from the environment as its siblings do. It prints no configuration value, and its output names no credential.                                                                                                                                                                                                                                            | PASS    |
| **IX. GDPR by design**            | **A live constraint, not a formality.** The natural query — "which players used an unnamed civilisation" — would put profile ids in a report that lands in a public GitHub issue. The check therefore aggregates: it reports the identifier and how many rows carry it, and never a `profile_id`, an alias or a `game_id`. Recorded in the contract so it cannot be widened by accident. | PASS    |
| **X. Intellectual property**      | The feature's own subject. No dataset is vendored; `aoc-reference-data` carries no licence and is read and transcribed, never copied, and the documentation records that ruling with the date it was checked. No game asset is involved.                                                                                                                                                 | PASS    |
| **XI. English**                   | Every artifact here is in English.                                                                                                                                                                                                                                                                                                                                                       | PASS    |
| **XII. Portable by construction** | A plain script invoked by a workflow. No platform API, no Vercel or VPS dependency, and it neither imports nor is imported by `api/index.py` or `api/cron/ingest.py`.                                                                                                                                                                                                                    | PASS    |

**No violations. Complexity Tracking is empty and stays empty.**

Three decisions deserve recording, because each was a live choice rather than an automatic
consequence.

**The check reports through the nightly workflow, not through `raise_alert`.** Both mechanisms exist.
`raise_alert` writes an `alerts` row and belongs to the ingester, where a runtime event needs a
durable record carrying `ingest_run_id`. This is not a runtime event: it is an audit of the mapping's
coverage, it has no run to belong to, and its reader is a maintainer rather than an operator. It
therefore joins `capture_audit` and `alert_audit` as a nightly script whose non-zero exit opens an
issue — the mechanism FR-013 means by "the same mechanism by which this project already surfaces
problems". T061's lesson applies in full: **the job must be added to the `report` job's `needs:`
list**, which today reads `[contracts, parser-canary, cron-liveness, capture-audit, alert-audit]`. A
job absent from that list fails in silence, which for this feature would be the exact failure it
exists to prevent, one level up.

**Ids 56 and 57 are not pre-silenced.** They are absent from every source consulted so far, which
makes them unknown rather than unnameable. If a match ever arrives carrying civilisation 56, that
arrival is precisely the evidence that it exists and needs naming — silencing it in advance would
throw away the one signal the feature is built to catch. The deliberately-unnameable mechanism
(FR-016) therefore ships **empty**, with the reason written beside it.

**An empty examination fails.** FR-015 forbids reporting success over nothing, and this project has
met that failure repeatedly — T015a's skipped tests, T038b's empty baselines, T070h's untested
two-thirds of a table. The check distinguishes "every identifier is named" from "there were no
identifiers", and only the first is a pass. That does not add a false-alarm mode: a database with no
match rows at all is already a red `cron-liveness` for a louder reason.

## Post-Design Constitution Re-Check

_Re-evaluated after Phase 1. All twelve principles still PASS; the table above stands unamended._

Phase 1 surfaced one question the pre-design pass did not, and it is recorded here rather than
settled silently.

**The check imports a module from `apps/api`.** The mapping lives in
`apps/api/src/aoe2stats_api/civilizations.py`, and the check must read it through its public lookup
(FR-009 forbids a second copy). The three sibling checks import `aoe2stats_storage`, which is a
`packages/` member — importing from an `apps/` deployable is a direction `scripts/` has not taken
before.

It is accepted, for two reasons. The module is a leaf: it imports nothing but `__future__`, so
importing it executes no application code, builds no settings object and loads no framework. And the
alternative — moving the mapping into `packages/core` — would edit feature 001's code and tests to
serve a check that is meant to observe them, which trades a small layering irregularity for a real
change to working code.

The irregularity is bounded by a test rather than by intent: the check's test module asserts that
importing the check leaves `fastapi` absent from `sys.modules`, exactly as T018c's guard asserts for
`aoe2rec_py` after importing the API. If someone later moves the mapping, or the module stops being
a leaf, that assertion fails and the decision gets revisited on purpose instead of eroding.

**Nothing else changed.** No artifact in Phase 1 introduced a network call, a schema change, a
component, a story, a secret, or a platform dependency, so principles III, IV, VI, VII, VIII and XII
are untouched by the design as built. Constitution IX gained a concrete obligation rather than a
looser one: the contract now forbids the report from carrying a profile id, an alias or a game id,
which is stricter than the principle's floor and is the form a reviewer can check.

## Project Structure

### Documentation (this feature)

```text
specs/002-reference-data-sources/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── civ-coverage-check.md
├── checklists/
│   └── requirements.md  # Written by /speckit-specify, re-validated by /speckit-clarify
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
docs/
├── reference-data.md            # NEW — the three sources, their licences, the procedure
└── data-sources.md              # AMENDED — links to the above; keeps every runtime measurement

scripts/checks/
├── civ_coverage.py              # NEW — reports civilisation ids the mapping cannot name
└── tests/
    └── test_civ_coverage.py     # NEW

.github/workflows/
└── nightly.yml                  # AMENDED — new job, and it joins `report`'s `needs:` list

.claude/skills/aoe2-data-sources/
└── SKILL.md                     # AMENDED — when to consult the sources; points at docs

apps/api/src/aoe2stats_api/
└── civilizations.py             # READ ONLY here — the mapping stays its single home
```

**Structure Decision**: no new package and no new workspace member. The documentation joins `docs/`
as its own file rather than a section of `data-sources.md`, because that file records the sources the
providers actually call and mixing maintainer reference material into it would blur exactly the
distinction FR-012 asks to preserve; `data-sources.md` links to it instead. The check joins
`scripts/checks/`, which since T061a is formatted, linted, type-checked and tested like the rest of
the tree, so a new script there inherits every gate without special handling. The civilisation table
is not moved: it stays in `apps/api/src/aoe2stats_api/civilizations.py`, and both the documentation
and the check point at it rather than restating it (FR-009).

## Complexity Tracking

> No constitution violations. This table is intentionally empty.
