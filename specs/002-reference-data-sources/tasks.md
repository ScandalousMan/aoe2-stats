---
description: 'Task list for community reference data sources and the civilisation coverage check'
---

# Tasks: Community Reference Data Sources

**Input**: Design documents from `/specs/002-reference-data-sources/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included and mandatory for the check. The four runnable scenarios in
[quickstart.md](./quickstart.md) are the source for its tests, and each test task names the scenario
it encodes. The fifth scenario is documentation and is walked by a person, once — that is recorded
as its own task rather than left as an intention. A test task is done when the test exists **and
fails** for the right reason, carrying `@pytest.mark.xfail(strict=True)` so the gate stays green
without the test being weakened; the implementing task removes the marker, which `strict=True`
forces rather than merely permits.

**Organization**: Grouped by user story. The documentation stories (US1, US2, US3) all write into
one new file and are therefore strictly sequential; the check (US4) touches no file any of them
touch and runs beside them.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1..US4, mapping to the user stories in [spec.md](./spec.md)
- Every task names its exact file path

## Path Conventions

Per [plan.md](./plan.md): `docs/`, `scripts/checks/`, `.github/workflows/`,
`.claude/skills/aoe2-data-sources/`, and `apps/api/src/aoe2stats_api/civilizations.py` which is read
and never written by this feature.

## Numbering starts at T201, deliberately

Feature 001 reaches T110 and still has open tasks. This feature's artifacts already cite eleven of
001's ids by bare number — T015a, T018c, T038b, T059c, T061, T061a, T061b, T070h, T074, T077, T100 —
because the judgment behind each of them is why a decision here went the way it did.
Restarting from one would make a two-digit id mean two different things in one repository, in prose
that crosses between features on purpose. A disjoint range costs nothing and removes the ambiguity
permanently. It is also what makes T202 below safe: once task ids resolve across features, they have
to be unique across features.

## Scenario coverage map

| quickstart scenario                                          | Story | Test task |
| ------------------------------------------------------------ | ----- | --------- |
| 1 — A civilisation the mapping cannot name is reported        | US4   | T209      |
| 2 — A fully covered database is silent                        | US4   | T209      |
| 3 — Examining nothing is a failure, and says which failure    | US4   | T209      |
| 4 — An excluded identifier stays quiet, an unknown one does not | US4 | T209      |
| 5 — A maintainer extends the mapping from the docs alone      | US1   | T215      |

---

## Phase 1: Setup (Unblock a second feature)

**Purpose**: `scripts/checks/spec_lint.py` was written when this repository held one feature, and
four of its checks encode that assumption. They fail structurally on 002 — not because 002 is wrong,
but because the linter cannot express "defined by another feature". The CI loop in
`.github/workflows/pr.yml` runs it over every feature that has a `tasks.md`, so committing this file
turns the `specs` job red until Phase 1 lands. This phase is therefore first and blocking, and its
scope is exactly the four checks; nothing else about the linter changes.

Measured, not assumed: a probe copy of this feature carrying a one-line `tasks.md` produced 46
failures, of which 22 are structural — 11 `task-refs`, 1 `alert-kinds`, 6 `env-consumed`, 4
`register-commitments`. The remaining 24 are the ordinary `requirement-coverage` failures that a
real `tasks.md` closes by naming each identifier.

- [ ] T201 Write the tests for the four feature-001-shaped assumptions in `scripts/checks/spec_lint.py`, in a new `scripts/checks/tests/test_spec_lint.py`, each marked `@pytest.mark.xfail(strict=True, reason="T202 not implemented yet")` and each building its fixture feature directory under `tmp_path` rather than pointing at `specs/`, so the linter's own tests do not change meaning when a feature is added: (a) a feature whose artifacts reference a task id defined in a *different* feature's `tasks.md` passes `task-refs`, while an id defined in no feature at all still fails it; (b) a feature whose `data-model.md` declares no alert vocabulary passes `alert-kinds`, while a feature that *does* name an alert producer using a kind outside the vocabulary still fails it; (c) a behavioural configuration key consumed by a task in another feature passes `env-consumed`, while a key consumed by no task anywhere still fails it; (d) a processing-register launch item naming a task defined in another feature passes `register-commitments`, while an item naming an id defined nowhere still fails it. Import `spec_lint` inside each test body, not at module scope
- [ ] T202 Make those four checks resolve across features rather than within one, in `scripts/checks/spec_lint.py`, and remove the `xfail` markers T201 left: build the set of defined task ids by scanning the `tasks.md` of every feature directory under `specs/` and fail `task-refs` only on an id defined by none of them; read the alert vocabulary from whichever feature's `data-model.md` declares it, treat a feature that declares none as inapplicable with a note rather than a failure, and keep checking that producers named in *this* feature's tasks use a canonical kind; widen `env-consumed` and `register-commitments` the same way. The guard each check exists for must survive the widening — an id, a key or a kind that is genuinely defined nowhere still fails, and the negative half of every T201 test is what proves it. Record in the module docstring that this is a multi-feature repository, so the next check written here does not re-acquire the assumption

**Checkpoint**: `uv run scripts/checks/spec_lint.py --feature specs/002-reference-data-sources`
reports only `requirement-coverage` failures, which the phases below close. Feature 001 lints exactly
as it did before — verify that explicitly, since a widened check that stopped catching anything would
report the same clean result as a correct one.

---

## Phase 2: Foundational (The file both halves point at)

**Purpose**: create the home the three documentation stories write into and the link that keeps it
distinct from the runtime source catalogue. Blocking for US1, US2 and US3; US4 does not depend on it.

- [ ] T203 Create `docs/reference-data.md` with its framing and its section skeleton — a short opening that says these are sources a **maintainer** consults on the occasions the game changes, that nothing in the running system, its build or its tests ever fetches them (FR-011), and that this is what separates them from the sources the providers actually call (FR-012) — plus empty sections for the source inventory, the re-derivation procedure, renames, precedence and known gaps, so T204 through T211 fill a structure rather than each inventing one. Shape the procedure section for more than one identifier: the civilisation mapping is the worked example, and a second one must be addable beside it rather than requiring a rewrite
- [ ] T204 Link to `docs/reference-data.md` from `docs/data-sources.md`, close to the top where a reader deciding which document they want will see it, phrased so the difference is legible in one line — that file records what the product calls, the new one records what a human reads (FR-012). Do not move the civilisation derivation note out of the Relic section of `docs/data-sources.md`: it is a measured property of that endpoint's payload and belongs where it is

**Checkpoint**: the file exists with its sections, and a reader arriving at `docs/data-sources.md`
can find it.

---

## Phase 3: User Story 1 — A new civilisation appears and shows as a number (Priority: P1) 🎯 MVP

**Goal**: a maintainer facing an unnamed civilisation id knows which source answers the question,
what they may legally do with it, how to reach a name, and how to prove the name is right.

**Independent Test**: hand `docs/reference-data.md` to someone who did not work on feature 001, give
them an id the table does not name, and confirm they reach a verified name without asking its author.
That is quickstart scenario 5, and T215 performs it.

- [ ] T205 [US1] Write the source inventory in `docs/reference-data.md`: one entry each for aoe2techtree, SiegeEngineers/aoc-reference-data and aoe2-apis, recording what each holds and what question it answers, so a maintainer can pick one without opening all three (FR-001); each entry's licence status, and the ruling that follows from it — may its data be copied into this repository, or only read and transcribed (FR-002); and the date that status was observed, stated as an observation on a date rather than a permanent property (FR-003). No entry ships without all three, which is SC-002. `aoc-reference-data` carries no licence at all and is the reason this distinction is in the spec: record it as read-and-transcribe-only, and record that the transcription that has already happened put the pairs into `apps/api/src/aoe2stats_api/civilizations.py` as facts while the source file itself was never copied here
- [ ] T206 [US1] Write the re-derivation and verification procedure in `docs/reference-data.md`: where the mapping lives, and that it lives in exactly one place (FR-004); how a derivation is checked against this repository's own captured fixtures rather than trusted, naming `apps/api/tests/test_civilizations.py` as the executable form of that check, and stating plainly that a verification join recovering nothing is a failure and not a pass (FR-006); and what remains uncovered, so an absence reads as a decision — ids 56 and 57, everything above the highest named id, and the eight civilisations the ordering rule cannot reach (FR-008). State the answer for an id no source names: leave it on the fallback, never interpolate from its neighbours. SC-001 is the outcome this task is judged by
- [ ] T207 [US1] Verify by inspection that `docs/reference-data.md` restates no measurement that already lives elsewhere (FR-009, SC-003): it must name where the civilisation mapping lives and what guards it, and must not reproduce the table, the id ranges, the fixture pair counts or the derivation rule, all of which are recorded in the module's own docstring and in `docs/data-sources.md`. Walk every number and every name the file states and either delete it or confirm it is stated nowhere else — this is the one rule `CLAUDE.md` says the project cares most about, and the file being new is exactly when it is cheapest to enforce

**Checkpoint**: US1 is complete and testable on its own — the documentation answers the recurring
case without any of the later stories being written.

---

## Phase 4: User Story 2 — A civilisation is renamed and nothing may be renumbered (Priority: P2)

**Goal**: a maintainer handed a rename changes the displayed label and touches no id.

**Independent Test**: describe a hypothetical rename and confirm they change the label without
changing an id or a sort position. T215 asks exactly this as its trap question.

- [ ] T208 [US2] Write the rename section of `docs/reference-data.md` (FR-005, SC-004): a rename changes the displayed name and never the numeric id, and an id keeps the position the **original** spelling sorted into — re-deriving the ordering from current names alone silently shifts ids that were previously correct, which is a regression disguised as a tidy-up. Use the Indians-to-Hindustanis case as the worked example and point at the entry it produced rather than restating the entry, so a maintainer who meets that apparent mismatch understands it is the derivation working and does not "fix" it

**Checkpoint**: the trap that cost feature 001 a full round of rework is written down.

---

## Phase 5: User Story 4 — The mapping goes stale and says so itself (Priority: P2)

**Goal**: a civilisation identifier the mapping cannot name is reported by the project's own nightly
reporting, the first time it runs after the data carrying it arrives.

**Independent Test**: seed match data carrying an identifier outside the mapping, confirm the check
reports it with its row count, then remove it and confirm the check goes quiet.

**Independent of Phases 2 to 4**: this story shares no file with the documentation stories and can be
built beside them once Phase 1 is done.

### Tests for User Story 4 ⚠️

- [ ] T209 [P] [US4] Write `scripts/checks/tests/test_civ_coverage.py` encoding quickstart scenarios 1 to 4 against the throwaway database, importing the fixtures from `tests/db.py` exactly as `scripts/checks/tests/test_cron_liveness.py` does and re-exporting them so ruff sees them used; every test marked `@pytest.mark.xfail(strict=True, reason="T210 not implemented yet")` and importing `civ_coverage` inside the test body. Four scenarios, plus one guard: an identifier outside the mapping exits non-zero and its identifier and row count both appear in the output; a fully covered database exits zero and names nothing; a database with no `match_players` rows exits non-zero with a message **distinguishably different** from the first — assert the two messages differ rather than only that both fail, because a status code alone sends a maintainer to the wrong place; an identifier in the deliberate-exclusion collection is not reported while id 56, which is unknown rather than unnameable, still is. The guard is the contract's privacy floor: assert the output carries no profile id, no alias and no game id, using rows seeded with values distinctive enough that their absence means something. Add one more, per the plan's post-design re-check: importing `civ_coverage` leaves `fastapi` absent from `sys.modules`, which is what bounds this feature's one layering irregularity by a test rather than by intent
- [ ] T210 [US4] Implement `scripts/checks/civ_coverage.py` per [contracts/civ-coverage-check.md](./contracts/civ-coverage-check.md) and remove T209's `xfail` markers: read `DATABASE_URL` from the environment and the distinct non-null `match_players.civ_id` values with a row count each, and nothing else from that table (FR-014 forbids any network call; constitution IX forbids reading the columns that would identify a person). Decide "the mapping cannot name this" by calling `civilisation_name` from `apps/api/src/aoe2stats_api/civilizations.py` and recognising its documented fallback shape — **the lookup never returns `None` for an unknown id**, it returns `Civilisation <id>`, and an implementer expecting `None` will write a check that reports nothing forever. Follow `cron_liveness.py`'s shape: an entry point returning an integer, `raise SystemExit(main())`, and an enum rather than a bare pass/fail so the two failing outcomes carry different messages. Examining nothing is a failure and is reported as its own outcome (FR-015). Ship the deliberate-exclusion collection **empty** (FR-016), with the reason written beside it: ids 56 and 57 are unknown, not unnameable, and a match arriving with one is the evidence that would make it nameable, so pre-silencing them would discard the only signal this check exists to produce
- [ ] T211 [US4] Add the `civ-coverage` job to `.github/workflows/nightly.yml`, modelled on `alert-audit` — checkout, `setup-uv`, `uv run scripts/checks/civ_coverage.py`, `DATABASE_URL` from secrets — **and add it to the `report` job's `needs:` list**, which today names five jobs and must name six (FR-013, SC-007, SC-008). The `needs:` entry is the task, not a detail of it: T061 recorded that a job absent from that list fails in silence, and for this feature that would be the failure it was built to prevent, one level up. Add the matching line to the issue body's ordered checklist so the maintainer who opens it is told what a red `civ-coverage` means and where to go — `docs/reference-data.md` — and extend the comment above the database-backed jobs to cover four rather than three

**Checkpoint**: a civilisation the product cannot name now announces itself, and a covered database
stays silent.

---

## Phase 6: User Story 3 — Two sources disagree (Priority: P3)

**Goal**: a naming conflict is resolved from a written rule instead of being relitigated.

**Independent Test**: present a maintainer with two sources spelling a civilisation differently and
confirm they resolve it from the documentation alone.

- [ ] T212 [US3] Write the precedence section of `docs/reference-data.md` (FR-007, SC-005): the name the game itself displays wins over any community restatement, and captured evidence from the live source wins over any third-party statement about that source. Point at the divergence already in the table — the reference dataset writes "Maya" where the table keeps "Mayans" — as a decision that was checked rather than an oversight, without restating the entry itself (FR-009)

**Checkpoint**: all four stories are independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T213 [P] Add a short section to `.claude/skills/aoe2-data-sources/SKILL.md` on when to consult these three sources and what not to do, pointing at `docs/reference-data.md` for every specific and restating none of them (FR-010). Three sentences of judgment, in the register the existing "Traps that will cost you an afternoon" section already uses: a rename does not renumber; a confident wrong name is worse than a bare id, because nothing about it looks unverified; a source with no licence may be read and transcribed but never copied in. The skill carries the traps, the document carries the facts, and neither carries the other's half
- [ ] T214 [P] Verify this feature added reference material and no runtime dependency (SC-006): `uv run pytest` green with the network guard active, `uv run ruff format .`, `uv run ruff check --fix .` and `uv run mypy` clean over `scripts/checks/civ_coverage.py` and `scripts/checks/tests/test_civ_coverage.py`, and `uv run alembic check` reporting no drift — [data-model.md](./data-model.md) says any drift here means something in this feature went wrong rather than something in the schema. Confirm no import of a reference source exists anywhere in the tree
- [ ] T215 Walk scenario 5 of [quickstart.md](./quickstart.md) against the finished `docs/reference-data.md` with a person who did not work on feature 001, and record the outcome in the pull request (SC-001, SC-002, SC-004, SC-005). Six steps and then the trap question — *a civilisation has been renamed in-game, what changes?* — where the documentation has done its job only if the answer is "the displayed name, and no id and no sort position". If the reader stalls at any step, that step is a defect in the writing and is fixed before this task closes. This is the only test documentation has, and it is the reason the four documentation tasks above are not self-certifying

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)** — no dependencies, and blocks everything, because committing this file without
  it turns the `specs` job red for both features at once.
- **Phase 2 (Foundational)** — depends on Phase 1. Blocks US1, US2 and US3. Does **not** block US4.
- **Phase 3 (US1, P1)** — depends on Phase 2. The MVP.
- **Phase 4 (US2, P2)** and **Phase 6 (US3, P3)** — depend on Phase 2. Sequential with Phase 3 and
  with each other, because all three write into `docs/reference-data.md`.
- **Phase 5 (US4, P2)** — depends on Phase 1 only. Runs beside Phases 2 to 4.
- **Phase 7 (Polish)** — T213 and T214 depend on the stories they describe; T215 depends on Phases 2,
  3, 4 and 6 being complete, since it reads the finished document.

### Within Phase 5

T209 before T210 — the tests exist and fail first. T211 after T210, since a workflow job invoking a
script that does not exist is a red nightly that proves nothing.

### Parallel opportunities

Genuinely few, and the [P] markers say so honestly rather than decoratively. The documentation tasks
share one file and are marked sequential on purpose: `CLAUDE.md` records what a parallel batch does
to a shared file, and it cost four files of rework in feature 001's Phase 3.

- T209 is [P] against the whole of Phases 2, 3, 4 and 6 — different files entirely.
- T213 and T214 are [P] with each other.
- The one real batch: **T209 alongside T203/T204**, once Phase 1 is done.

---

## Implementation Strategy

### MVP

Phase 1, then Phase 2, then Phase 3. At that point a maintainer meeting an unnamed civilisation has
somewhere to go, which is the case that recurs on every expansion and the one this feature exists
for. Stop and walk T215 before deciding whether the rest is worth building — if the document fails
its reader there, the later sections are being added to something that does not work.

### Incremental delivery

1. Phase 1 → the repository can hold a second feature. Commit.
2. Phase 2 → the file exists and is findable. Commit.
3. Phase 3 (US1) → the MVP. Commit, and demo by handing it to a reader.
4. Phase 5 (US4) → the mapping now reports its own staleness. Commit.
5. Phases 4 and 6 (US2, US3) → the two remaining traps written down. One commit each.
6. Phase 7 → the skill, the verification pass, and the human walk.

Phase 5 can be pulled forward to any point after Phase 1. It is placed after Phase 3 here because
US1 is the P1 story and shipping it first is the point of an MVP, not because the check depends on
anything the documentation produces.

---

## Notes

- Commit at the granularity `CLAUDE.md` sets: one task, one commit, with the `[x]` in this file
  riding in the same commit as the work that earned it.
- Every task above is one `implementer` invocation. T202 and T210 are the two that touch real logic;
  the rest are prose, a workflow file, and one verification pass.
- The `xfail(strict=True)` markers in T201 and T209 are not a formality. A skipped test reports green
  while proving nothing, which is the exact fault this feature's own check exists to prevent, and
  `CLAUDE.md` records that six of seven agents in feature 001's test batch reached for
  `importorskip` under gate pressure. Expect the same instinct here and dispatch against it.
