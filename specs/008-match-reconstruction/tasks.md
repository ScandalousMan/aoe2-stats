---
description: 'Task list for match reconstruction — exact values behind two gates, and estimates at the inferred tier beside them'
---

# Tasks: Match reconstruction

**Input**: Design documents from `/specs/008-match-reconstruction/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md),
[owner-readings.md](./owner-readings.md)

**Tests**: Included and mandatory. The feature is Python apart from the two view steps, so the
green-tree gate applies in its usual form: a test task lands its test marked `xfail(strict=True)`,
never a skip, and the implementing task deletes the marker. Where a pair is never separately green
the task says so, and the two are one commit.

**Organization**: by the ten phases [plan.md](./plan.md) fixes, not by story priority. Two phases
are gates that end in a decision, and the plan's order is forced by them. **Phase 10 (US6, the
estimates) is numbered last and scheduled early: it starts as soon as phase 2 is merged and waits
on neither gate.** Story labels ride on each task.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel — different files, no dependency on an incomplete task
- **[Story]**: US1..US6, mapping to the user stories in [spec.md](./spec.md); evidence, gate and
  closing tasks serve no single story and carry none
- **Owner task** marks a task only the owner can do: a reading in the game, a ruling. An agent
  prepares everything around it and never answers it. Each says whether it asks for
  **information** or for an **arbitration**

## Numbering starts at T901, deliberately

The highest id any feature defines, on the remote's main branch, on every open pull request and on every
remote branch as of 2026-11-15, is T850. `spec_lint.py`'s `task-collisions` check fails on a new
collision, so this feature takes the first hundred nothing has reached.

## What every implementer must know before starting

**An estimate never feeds an exact value.** Nothing under
`packages/reconstruction/src/aoe2stats_reconstruction/` outside `estimates/` imports from
`estimates/` (FR-028). If a task on the exact path seems to need an estimate, the task is wrong:
stop and say so.

**The seen data are exact; the estimates are not.** `seen.py` lives outside `estimates/` and reads
commands only. The estimates read it; it reads no estimate. **No estimate reads an explicit
deletion** (FR-036; 006 FR-014).

**A candidate rule settles nothing.** Only a rule whose status is `adopted` in
`packages/reconstruction/src/aoe2stats_reconstruction/rules.toml` may settle a published
reconstructed value (contracts/rules.md). The interim policies of phase 10 are not rules.

**No interval, midpoint or probability in a reconstructed type** (FR-008). An estimate carries a
confidence level from 006's closed set, never a number.

**Do not restate a measurement.** Every number measured for this feature lives in
[research.md](./research.md) until phase 9 moves the outside-world ones into
`docs/data-sources.md`. No task, test name, comment or commit message copies one.

**Never answer an owner reading.** [owner-readings.md](./owner-readings.md) asks; the answer is
written once, in the recording's playback file, by the transcription task that names it.

**`.env.local` points at production.** No task here runs a migration or a script against it, and
none needs to. Every test runs with `PYTEST_DISABLE_NETWORK=1`.

**The canonical goldens are regenerated only by `scripts/ops/canonical_golden.py`**, under the
rules of `tests/fixtures/replays/README.md`, and never while another agent is writing in the same
tree.

## Scenario coverage map

| quickstart section                | Phase | Story    | Task(s) that encode it             |
| --------------------------------- | ----- | -------- | ---------------------------------- |
| Phase 1 — evidence and vocabulary | 1     | —        | T906, T908, T909, T910             |
| Phase 2 — the spine               | 2     | US3, US5 | T916, T918, T922, T926, T928, T930 |
| Phase 3 — gate G1                 | 3     | —        | T935, T936                         |
| Phase 4 — arrivals                | 4     | US2      | T938                               |
| Phase 5 — spending                | 5     | US1      | T944, T945                         |
| Phase 6 — at scale                | 6     | US3, US5 | T946, T947, T948, T950             |
| Phase 7 — the view                | 7     | US4      | T952, T953                         |
| Phase 8 — gate G2                 | 8     | —        | T958, T959                         |
| Phase 10 — estimates              | 10    | US6      | T966, T968, T970, T972, T975, T980 |
| Closing                           | 9     | —        | T962                               |

---

## Phase 1: Evidence and vocabulary (plan phase 1)

**Goal**: the owner has every request, the vocabulary carries what every later phase reads, and
the measurements that guard the plan are tests. Nothing here publishes.

**Independent test**: quickstart, Phase 1.

- [ ] T901 **Owner task (information).** Take readings O1 (the 22 age-up queues and arrival times)
      and O2 (three commands naming two Archery Ranges) of `specs/008-match-reconstruction/owner-readings.md`
      by playing each committed recording back in the game, and hand the answers over as written there:
      one line per request id, `unreadable` where the game does not show the value, with the build the
      game displayed. These two close gate G1; T933 transcribes them.
- [ ] T902 **Owner task (information).** Take readings O3 (the Sicilian unit), O4 (the starting
      state at 0:00 of each recording) and O5 (three deletions) of
      `specs/008-match-reconstruction/owner-readings.md`. T924 transcribes O3 and O4, T942 transcribes O5.
- [ ] T903 **Owner task (information).** Take readings O6.1 (the end-of-match military statistics)
      and O6.2 (population at the stated times) of `specs/008-match-reconstruction/owner-readings.md`.
      They measure the estimates of phase 10 and close no gate; T978 transcribes them.
- [ ] T904 **Owner task (information), optional.** Reading O7: name one of your recorded matches in
      which you cancel a queued unit, or play one as the request describes. Nothing waits on it; without
      it D-CANCEL-1 stays a candidate tested on synthetic streams only.
- [x] T905 [P] Test first, `xfail(strict=True)`: `unit-queued` carries `building_objects`, every
      producing building the command names in the engine's order, non-empty, whose first element equals
      `building_object`. Type test in `packages/core/tests/test_events.py`; adapter test over every
      committed recording in `packages/replay-engine/tests/test_canonical.py`
      (contracts/canonical-events-amendment.md, research R1).
- [x] T906 After T912a. Widen the vocabulary and the adapter, and delete T905's markers:
      `packages/core/src/aoe2stats_core/replay/events.py` and
      `packages/replay-engine/src/aoe2stats_replay_engine/canonical.py`. Regenerate the canonical
      goldens with `scripts/ops/canonical_golden.py`. Before regenerating, record beside the test a
      digest of each recording's `unit-queued` events as they are today; the test in
      `packages/replay-engine/tests/test_canonical_golden.py` removes `building_objects` from each
      regenerated `unit-queued` event and finds the same digest, so the comparison with the previous
      stream stays true after later tasks add other events. 006's golden
      timeline must compare byte-identical. The register datum `event.unit_queued.building_objects`
      already exists (T912a); this task adds nothing to the register (FR-002, FR-011, FR-013). Never separately green from T905's removal of its markers.
- [x] T907 After T906, which edits the same test file and adapter. Test first, `xfail(strict=True)`: `match-started` carries `population_limit` in
      `lobby_presets`, a decimal string read from the engine's lobby settings, for every committed
      recording, in `packages/replay-engine/tests/test_canonical.py`.
- [x] T908 Read the population limit in
      `packages/replay-engine/src/aoe2stats_replay_engine/canonical.py`, delete T907's marker, regenerate
      the canonical goldens, and name the new key in the method text of
      `event.match_started.lobby_presets` in `packages/core/src/aoe2stats_core/truth/register.toml`
      (research R4).
- [x] T909 [P] Build the timing harness SC-008 and SC-015 are measured with, before any
      reconstruction code exists: `apps/analyzer/tests/test_analysis_time.py` times the analysis of
      each committed recording along today's path through a comparison that later tasks (T950,
      T975) call with the reconstruction and the estimates on and off **in the same run**. No timing is
      committed: a figure taken on one machine cannot be compared on another, so research R14's
      baseline is the same run's own path without the new code. The comparison lives in
      `tests/analysis_time.py`, imported as `tests.analysis_time`, because a test module under
      `apps/analyzer/tests/` cannot be imported by another package's tests (review of pull request
      #232); T950 and T975 import it from there.
- [x] T910 [P] The age-proof consistency of research R3 as a permanent test in
      `packages/knowledge/tests/test_age_proof_consistency.py`: over every committed canonical golden,
      no order requires an age its participant has not yet clicked. The one known defect, the Sicilian
      unit, is held as a strict expected failure naming 006's task T851, so the suite turns red on the
      day the superseding snapshot fixes it.
- [x] T911 [P] The base-unit measurement of research R15 as a test in
      `packages/knowledge/tests/test_orders_name_base_unit.py`: across the committed goldens, no
      upgrade research is followed by an order of the upgraded unit.
- [x] T912 [P] File the Sicilian age-requirement defect through 006's mechanism: add the request to
      `specs/006-replay-analysis-foundations/owner-readings.md`, citing research R3 and this feature's
      reading O3, so that 006's T851 carries the fix. No value is written there. The build 185872
      sheet is closed and its test counts answered rows, so narrow that test to admit an open row only
      when it names its carrier task (owner's arbitration, 2026-11-15).
- [x] T912a Add to `packages/core/src/aoe2stats_core/truth/register.toml`, as `planned`, every datum
      this feature intends to publish and the register lacks, and regenerate the view (006 FR-005;
      FR-001a, FR-027): the exact population and the exact Town Center idle time at `reconstructed`;
      `event.unit_queued.building_objects`, `participant.units_seen` and
      `participant.producing_buildings_seen` at `observed`, the two seen data depending on the first;
      and the five estimates of contracts/estimates.md at `inferred`. The loader refuses a
      dependency on an id the register lacks, which is why the event datum is registered here and not
      by T906. Each `requires_knowledge` names only fields
      the knowledge base has today; T955 adds the population fields. This is the feature's first
      register change, so it lands before T906, and it adds nothing else.

---

## Phase 2: The reconstruction spine (plan phase 2 — US3, US5)

**Goal**: the package, the order fold, the rules registry, settlements, invariants, the identity
component, the reproduce path, validator rules 11 to 14, the starting state, and a version 3
document with an empty `reconstructed` block.

**Independent test**: quickstart, Phase 2.

- [x] T913 Create the package: `packages/reconstruction/pyproject.toml` (depends on
      `aoe2stats-core` and `aoe2stats-knowledge` only), `packages/reconstruction/src/aoe2stats_reconstruction/__init__.py`
      with the package version, the workspace member, test paths and mypy entry in the root
      `pyproject.toml`, the python path filter in `.github/workflows/pr.yml`, and the dependency
      declared on `apps/analyzer/pyproject.toml` itself, not inherited (research R12). A packaging test
      in `packages/reconstruction/tests/test_reconstruction_packaging.py` asserts the analyzer declares it
      (not `test_packaging.py`: that basename exists in `packages/knowledge/tests/` and two test
      modules sharing a basename abort collection in the one workspace session).
- [x] T914 [P] [US3] Test first, `xfail(strict=True)`, in `packages/reconstruction/tests/test_orders.py`:
      one fold over a canonical stream yields the orders of data-model §1, with every producing
      building, the source event index, and nothing attributed after a participant's resignation
      (FR-002, FR-017's `nothing-after-exit`).
- [ ] T915 [US3] Implement `packages/reconstruction/src/aoe2stats_reconstruction/orders.py` and
      delete T914's markers. The fold reads the canonical vocabulary only, never an engine shape
      (constitution V).
- [x] T916 [P] [US3] Test first, `xfail(strict=True)`, in `packages/reconstruction/tests/test_rules.py`:
      each of the seven loader guarantees of contracts/rules.md has a test that plants its violation
      and sees loading fail; the generated view equals the committed
      `packages/reconstruction/src/aoe2stats_reconstruction/RULES.md` byte for byte; every initial rule
      enters at the status the contract's table states.
- [ ] T917 [US3] Implement `packages/reconstruction/src/aoe2stats_reconstruction/rules.py`, write
      `packages/reconstruction/src/aoe2stats_reconstruction/rules.toml` with the initial set of
      contracts/rules.md (D-EXEC-1 and D-DIST-1 absent, since they are not yet written; P1 with an
      empty `readings` list, since no playback file holds its reading yet, on research R3's evidence),
      generate
      `RULES.md`, and delete T916's markers (FR-005, FR-006, FR-007, FR-007a). The registry is read
      through `importlib.resources` (constitution XII).
- [x] T918 [P] [US3] Test first, `xfail(strict=True)`, in
      `packages/reconstruction/tests/test_settlements.py`: a condition has exactly one value and a
      required settlement; a settlement resolves to an adopted rule of the family its `by` states; and,
      by walking every type of the published block, no field admits a pair, a range, a list of
      alternatives, a float share or a probability (FR-008, SC-002).
- [ ] T919 [US3] Implement the types of data-model §4, §5 and §7 in
      `packages/reconstruction/src/aoe2stats_reconstruction/state.py` and
      `packages/reconstruction/src/aoe2stats_reconstruction/settle.py`, and delete T918's markers
      (FR-014).
- [x] T920 [P] [US3] Test first, `xfail(strict=True)`, in
      `packages/reconstruction/tests/test_invariants.py`: one synthetic stream per invariant of
      data-model §8 breaks exactly that invariant, the breach names the invariant, the participant, the
      datum and the value, and nothing is published (FR-017, SC-007). The two invariants the population phase owns are declared with no check until T958 and T959 enable them.
- [ ] T921 [US3] Implement `packages/reconstruction/src/aoe2stats_reconstruction/invariants.py` and
      delete T920's markers.
- [ ] T922 [P] Test first, `xfail(strict=True)`, in `packages/replay-engine/tests/test_starting.py`:
      the Tier A decoder emits one `starting-attributes` event per human participant at clock 0 after
      `match-started`, holding `food`, `wood`, `stone` and `gold` only, golden-tested over every
      committed recording, with the planted absences `tests/test_starting_state_anchor.py` already
      exercises (contracts/canonical-events-amendment.md, research R4).
- [ ] T923 Implement `packages/replay-engine/src/aoe2stats_replay_engine/starting.py`, emit the
      event from `packages/replay-engine/src/aoe2stats_replay_engine/canonical.py`, regenerate the
      canonical goldens, change 006's test that the adapter emits neither declared-only kind for this
      kind only, move the register's two starting entries (the attributes and the resources) out of
      `blocked`, and delete T922's markers. `reconstruction.income_model` stays `blocked` (FR-024);
      its `blocked_on` names this decoder, so it is re-stated to what it still waits on, an income
      method that no feature specifies. The decoder reads the inflated header bytes, never the engine's output.
- [ ] T924 Transcribe readings O3 and O4 into each recording's playback file
      (`tests/fixtures/replays/<recording>.playback.toml`, contracts/playback-readings.md) once T902 is
      answered, add the O3 reading's id to P1's `readings` in the registry in that same change, and add
      the well-formedness test of that contract's assertion 4 in
      `packages/reconstruction/tests/test_playback_readings.py`. Until T902 is answered, land the test
      and the empty files only.
- [ ] T925 Add the starting-objects knowledge table through 006's snapshot mechanism, as a
      superseding snapshot under `packages/knowledge/snapshots/`: per build, civilisation and lobby
      preset, the units and buildings a participant starts with. Before transcribing, record the
      source's ruling in `docs/data-sources.md` §6 if that section does not already hold it
      (constitution X). Values the source leaves in doubt are requests added to
      `specs/008-match-reconstruction/owner-readings.md`, never guesses (FR-026).
- [ ] T926 [P] Test first, `xfail(strict=True)`, in
      `packages/reconstruction/tests/test_starting_state.py`: the starting state of data-model §3 for
      each committed recording; the decoded resources agree with the lobby-and-civilisation derivation
      and a planted disagreement is the `starting-resources-agree` breach; a starting-age preset whose
      meaning O4 has not confirmed gaps every age-dependent value and guesses nothing (FR-026).
- [ ] T927 Implement `packages/reconstruction/src/aoe2stats_reconstruction/starting.py` and delete
      T926's markers. Depends on T923 and T925.
- [ ] T928 [P] [US3] Test first, `xfail(strict=True)`, in `packages/core/tests/test_validate.py`:
      validator rules 11 to 14 of contracts/reconstruction-document.md each reject their planted
      violation, including a reconstructed value at an observed path and an observed value inside
      `reconstructed` (FR-015).
- [ ] T929 [US3] Implement rules 11 to 14 in `packages/core/src/aoe2stats_core/truth/validate.py`
      and delete T928's markers.
- [ ] T930 [P] [US5] Test first, `xfail(strict=True)`: in `apps/analyzer/tests/test_document_build.py`,
      a document from each committed recording is version 3, carries an empty `reconstructed` block,
      and its identity's `reconstruction_engine` names the installed package version and the registry
      digest; in `apps/analyzer/tests/test_reproduce.py`, reproducing a document from its identity
      yields identical bytes and reproducing one whose engine is not installed refuses and names what
      differs; in `apps/analyzer/tests/test_reproducibility.py`, two analyses are byte-identical outside
      the wall-clock set (FR-021, FR-022, SC-006).
- [ ] T931 [US5] Implement `packages/reconstruction/src/aoe2stats_reconstruction/document.py`,
      version 3 and the identity component in `apps/analyzer/src/aoe2stats_analyzer/extract.py`, and
      the reproduce path in `apps/analyzer/src/aoe2stats_analyzer/reproduce.py`; accept version 3
      structurally in `apps/web/src/features/analysis/api.ts` with its test; delete T930's markers.
      Never separately green from T929: a version 3 document must pass the validator the same commit
      ships.
- [ ] T932 [P] An architecture test in `tests/architecture/test_reconstruction_boundaries.py`: the
      reconstruction package opens no connection, registers no scheduled job, is imported by nothing on
      the capture path, and reads no input but the canonical stream and the knowledge base (FR-002,
      FR-023).

**Checkpoint**: phase 10 may start here. Phases 3 to 7 continue in order.

---

## Phase 3: Gate G1 — executed or refused, and distribution (plan phase 3)

**Goal**: a rule that tells an executed command from a refused one, and a rule that places a
command naming several buildings, each checked against the owner's readings. The phase ends
adopted, or in an arbitration.

**Independent test**: quickstart, Phase 3.

- [ ] T933 Transcribe readings O1 and O2 into each recording's playback file once T901 is answered,
      one table per reading with who read it, when and the build shown. No value is copied anywhere
      else.
- [ ] T934 Test first then implement, one commit: the queue mechanics of data-model §2 in
      `packages/reconstruction/src/aoe2stats_reconstruction/queues.py`, with the execution, the
      distribution and the state supplied by the caller as policies, and its invariants tested in
      `packages/reconstruction/tests/test_queues.py` on synthetic streams (items of one building never
      overlap; a start never precedes its enqueue; a cancellation removes unstarted items only). If
      T971 has already created the module, extend it and keep its tests green; the mechanics hold no
      policy of their own (research R17).
- [ ] T935 Write D-EXEC-1 and D-DIST-1 in
      `packages/reconstruction/src/aoe2stats_reconstruction/rules.toml` as candidates, from what the O1
      and O2 readings show and from observed facts only, and test in
      `packages/reconstruction/tests/test_playback_g1.py` that, for each of the 22 age-ups, the queue
      the model holds at the click equals the queue the owner read, and that each O2 command places its
      items where the model does (FR-003b). The `proof-not-contradicted` invariant must hold on all
      three recordings.
- [ ] T936 **Gate.** If T935's test passes, move D-EXEC-1 and D-DIST-1 to `adopted` with their
      readings listed, bump the reconstruction version, and regenerate `RULES.md`. If a reading cannot
      be matched by any rule written from observed facts, change nothing in the registry and hand the
      owner the **arbitration** plan.md's Complexity Tracking names, with the unmatched readings listed;
      phases 4 and 5 then publish nothing.

---

## Phase 4: Age-up arrivals (plan phase 4 — US2)

**Goal**: the modelled arrival of every age-up, one exact time, with what settled it.

**Independent test**: quickstart, Phase 4.

- [ ] T937 [US2] Add `age_requirement` to the `requires_knowledge` of
      `reconstruction.age_up_modelled_arrival_ms` in
      `packages/core/src/aoe2stats_core/truth/register.toml` and regenerate the view, so that its gaps
      turn blocking for this datum (research R3; 006 research D7). A test in
      `packages/knowledge/tests/test_gaps.py` asserts the severity change.
- [ ] T938 [US2] Test first, `xfail(strict=True)`, in
      `packages/reconstruction/tests/test_arrivals.py`: US2's five acceptance scenarios on synthetic
      streams; for each committed recording, every arrival equals the owner's O1 reading at the game's
      displayed second (contracts/playback-readings.md, Units of time), every age-up counted not
      reached is one the reading shows not reached, and every arrival's settlement names a confirming
      order or D-AGE-1's resignation clause (FR-010, FR-010a, FR-019, SC-001).
- [ ] T939 [US2] Implement `packages/reconstruction/src/aoe2stats_reconstruction/arrivals.py`;
      adopt D-AGE-1 and D-HOUSE-0 only if T938's readings agree, each with its readings listed and a
      version bump; write the arrivals into the golden reconstruction of each recording
      (`tests/fixtures/replays/<recording>.reconstruction.json`); move the datum from `planned` to
      `published` in the register in this same change (FR-001); keep the observed click and the
      modelled arrival as two data at two paths (FR-016). Delete T938's markers. If a reading
      disagrees, the rule is fixed or stays a candidate and nothing is published; a difference is never
      toleranced.

---

## Phase 5: Spending, military share, production per building (plan phase 5 — US1)

**Goal**: what each participant paid, by resource; the part spent on military units; the
production each building was ordered.

**Independent test**: quickstart, Phase 5.

- [ ] T940 [US1] Add the unit classes through 006's snapshot mechanism, as a superseding
      snapshot under `packages/knowledge/snapshots/`: one of `economic`, `military`, `neither` per unit
      per build, from a source whose ruling `docs/data-sources.md` §6 records and from the owner's
      ruling of 2026-11-06. A unit with no class is a gap that withholds the military share, tested in
      `packages/knowledge/tests/test_unit_classes.py` (FR-001b).
- [ ] T941 [US1] Add the line table through the same mechanism: per build, the base unit of
      each line and its stages in order (research R15), tested in
      `packages/knowledge/tests/test_unit_lines.py`.
- [ ] T942 [US1] Transcribe reading O5 into the playback files once T902 is answered, fit D-TIE-1's
      window on those three deletions and on nothing else, and test in
      `packages/reconstruction/tests/test_deletions.py` that every deletion is either tied by the rule
      or reported with its candidate placements and the refund each would have given (FR-003a,
      research R6).
- [ ] T943 **Owner task (arbitration).** D-CONTROL-1, deferred by the owner on 2026-11-10 until it
      is re-derived in the light of feature 009. When 009 is settled, an agent re-derives the rule's
      statement in `specs/008-match-reconstruction/research.md` R9, using the measurement research R16
      records for that day, and puts it to the owner. Until the owner's yes it stays a candidate, and
      every value that depends on buildings controlled is not published.
- [ ] T944 [US1] Test first, `xfail(strict=True)`, in `packages/reconstruction/tests/test_spending.py`:
      US1's four acceptance scenarios on synthetic streams; spending is what was ordered and executed,
      less cancellations, less the refunds D-REFUND-1 grants through a tied deletion (FR-003); a value
      is withheld only by a knowledge gap and never for uncertainty (FR-009, SC-003); a cancellation is
      attributed by D-CANCEL-1 on synthetic streams (FR-011); a technology counts researched only under
      D-TECH-1 with every observable obstacle shown absent (FR-007a); ordered production per building
      sums the knowledge base's time at the line stage in force (FR-013); market transactions are
      excluded (research R11); each committed recording reproduces its golden reconstruction.
- [ ] T945 [US1] Implement `packages/reconstruction/src/aoe2stats_reconstruction/spending.py` with
      the military share restricted to the `military` class, complete the golden reconstructions, and
      in the same change move `reconstruction.resources_spent`,
      `reconstruction.ordered_production_ms` and `reconstruction.ordered_army_cost` from `planned` to
      `published` and amend the spending method's text in the register to say what was paid (FR-001,
      FR-003). The income model, exploration coverage, the map-control model and the prerequisite order
      check stay `blocked`, asserted by a test in `packages/core/tests/test_register.py` (FR-024).
      Delete T944's markers. Depends on T936, T939, T940, T941 and T942; values that depend on
      buildings controlled wait on T943.

---

## Phase 6: Correctness at scale (plan phase 6 — US3, US5)

**Goal**: every golden agrees with every reading, every civilisation is exercised, and the cost
and the reproducibility are measured.

**Independent test**: quickstart, Phase 6.

- [ ] T946 [US3] Complete each recording's golden reconstruction by hand from its orders and the
      knowledge base, in the published block's shape (FR-018), and assert in
      `packages/reconstruction/tests/test_playback_readings.py` that every reading whose quantity
      corresponds to a reconstructed datum equals it (FR-019, SC-001), with an `unreadable` reading
      reported and asserting nothing.
- [ ] T947 [P] [US3] A synthetic order stream per civilisation of every promoted snapshot, in
      `packages/reconstruction/tests/test_synthetic_civilisations.py`, that prices and times every
      effect the civilisation has, each conditional one at each of its states (FR-020, SC-004). The
      test enumerates civilisations and effects from the snapshot, so a new one is covered or fails.
- [ ] T948 [P] [US3] The per-rule settlement table of SC-009: a test in
      `packages/reconstruction/tests/test_settlement_shares.py` computes, per adopted rule, how many
      conditions it settled across the committed recordings and how many a proof settled instead, and
      compares it with the table recorded beside each golden.
- [ ] T949 [P] [US3] A traceability test in
      `packages/reconstruction/tests/test_traceability.py`: for every reconstructed value of each
      committed recording, the settlements and effects it carries are enough to recompute it without
      reading code (SC-005, US3).
- [ ] T950 [P] [US5] The analysis time with the reconstruction is within twice the same run's path without it, through T909's harness, for each committed
      recording, asserted in `apps/analyzer/tests/test_analysis_time.py` (SC-008); a reconstruction
      version bump keeps the old analysis resolvable and reproducible, asserted in
      `apps/analyzer/tests/test_reproduce.py` (FR-022, SC-006).

---

## Phase 7: The view (plan phase 7 — US4)

**Goal**: each reconstructed value shown as modelled, apart from the observed ones.

**Independent test**: quickstart, Phase 7.

- [ ] T951 [US4] The `product-designer` agent specifies the modelled value and its settlement
      indicator in `packages/design-system/specs/analysis-timeline.md`, tokens only (constitution VI).
      Specs under that directory are cited by line number elsewhere: keep the line counts of the
      existing sections, or update every citation in the same change.
- [ ] T952 [US4] Build it in `packages/design-system/src/composites/AnalysisTimeline/index.tsx`
      with stories and unit tests beside it: each reconstructed number labelled as modelled, apart from
      the observed click; an age-up counted not reached says so; a value withheld by a knowledge gap
      says what is missing; whether each condition was proven by an order or settled by a rule is
      shown (FR-025). The `visual-reviewer` agent passes the stories in both themes; the baselines are
      captured from CI's render (constitution VII).
- [ ] T953 [US4] Read the `reconstructed` block through typed assertions in
      `apps/web/src/features/analysis/api.ts` and map it in
      `apps/web/src/features/analysis/mappers.ts`, with their tests. The view computes no value.

---

## Phase 8: Gate G2 — population and idle time, exact (plan phase 8)

**Goal**: FR-001a's two exact figures, if a candidate rule survives the readings. Phase 10's
estimates are published meanwhile and are not this phase's draft.

**Independent test**: quickstart, Phase 8.

- [ ] T954 Add the two population fields through 006's snapshot mechanism, as a superseding
      snapshot under `packages/knowledge/snapshots/`: the population a unit occupies and the population
      space a building gives, from a source whose ruling `docs/data-sources.md` §6 records, with the
      five civilisation effects research R5 names moved to `modelled` where the fields now allow it.
      Tested in `packages/knowledge/tests/test_population_fields.py`. It may run at any point after
      phase 1, and **phase 10 needs it before T972**.
- [ ] T955 Name the population fields T954 adds in the `requires_knowledge` of the planned entries
      that need them, in `packages/core/src/aoe2stats_core/truth/register.toml`, and regenerate the
      view: the exact population, `participant.estimated_living_population` and
      `participant.estimated_population_excess`. Their gaps are computed from that moment (FR-001a;
      006 FR-005). It lands with T954 if the gap machinery refuses a field name the knowledge base
      does not have.
- [ ] T956 Write the candidate rules of research R5 that are not refuted (S2, S4, S5, S6, S7, S8)
      into `packages/reconstruction/src/aoe2stats_reconstruction/rules.toml` as candidates, and add to
      `specs/008-match-reconstruction/owner-readings.md` the O6 requests each one needs beyond O6.1 and
      O6.2, each a value to read at a stated time. A strategy already refuted is not written (FR-012).
- [ ] T957 **Owner task (information).** Take the readings T956 adds.
- [ ] T958 Town Center idle time by empty queue, exact: test first then implement, in
      `packages/reconstruction/tests/test_idle_exact.py` and the queue model, checked against the
      readings (SC-010). Published, with its register entry moved to `published` and its invariant
      `idle-bounded` enabled, only if every reading agrees. Depends on T936.
- [ ] T959 Population, exact: adopted and published only if a candidate rule agrees with every
      reading (SC-010), with the invariant `population-non-negative` enabled. If none survives, change
      nothing, leave the entry `planned`, and hand the owner the **arbitration**: the spec requires an
      exact figure and no rule gives one.

---

## Phase 9: Closing (plan phase 9)

- [ ] T960 [P] Move the outside-world measurements of research R1, R2, R5, R15 and R16 into
      `docs/data-sources.md` §2, each under a test that asserts it over the committed recordings
      (research R13): commands naming several buildings, refused commands kept in the recording, empty
      unit-id lists and which command classes carry ids, deletions naming unseen objects, orders naming
      the base unit. `specs/008-match-reconstruction/research.md` stays their record of origin and is
      not edited to match.
- [ ] T961 [P] Record the reconstruction's rule risk and the estimates' reading risk in
      `docs/risks.md`, cross-referenced to the registry and to the register, and update
      `.claude/skills/replay-parsing/SKILL.md` where it says the starting-state decoder does not exist
      yet.
- [ ] T962 Run [quickstart.md](./quickstart.md) end to end and
      `uv run scripts/checks/spec_lint.py` over every feature, checked by exit code.

---

## Phase 10: Seen data and estimates (plan phase 10 — US6)

**Starts when phase 2 is merged. Waits on neither gate.** Needs T906, T908 and T912a from phase 1,
and T954 with T955 before T972.

**Goal**: two exact seen data per participant, and five estimates under the document's inferred
data, each with a confidence and a non-claim, computed by code the exact path never imports.

**Independent test**: quickstart, Phase 10.

- [ ] T963 [P] [US6] Test first, `xfail(strict=True)`, in
      `packages/reconstruction/tests/test_estimates_isolation.py`: walking the imports of every module
      of the package outside `estimates/`, none imports from `estimates/` (FR-028). The marker is
      strict against the sub-package not existing yet; T965 deletes it.
- [ ] T964 [P] [US6] Research, no code: establish what in the committed goldens could refute "object
      ids are allocated in increasing order of creation and never reused", run it, and record the
      outcome in `specs/008-match-reconstruction/research.md` R16; state whether any observed fact
      gives an object id a unit type; and state whether a building that produces nothing can be told
      from a unit when a command names it in its unit list. Where only the game can settle one, add
      the request to `specs/008-match-reconstruction/owner-readings.md`; T977 is where the owner takes
      it. No estimate may rest on any of the three until a test asserts it.
- [ ] T965 [US6] Create `packages/reconstruction/src/aoe2stats_reconstruction/estimates/` with the
      four interim policies of research R17 in
      `packages/reconstruction/src/aoe2stats_reconstruction/estimates/policies.py` (execution,
      distribution, state, occupancy), each a function with no knowledge of the registry, tested in
      `packages/reconstruction/tests/test_estimates_policies.py` on synthetic streams. The state
      policy reads the age-up item's modelled completion from the same queue model, never a second
      computation of it. Delete T963's marker.
- [ ] T966 [P] [US6] Test first, `xfail(strict=True)`, in
      `packages/reconstruction/tests/test_seen.py`, on synthetic streams: US6's scenario 1; an object
      id named in a unit list from which an order is issued is a building and never a unit; every
      building a command names is seen at that order; a unit another participant's commands name
      afterwards carries who and from when; nothing is seen after a resignation (FR-030).
- [ ] T967 [US6] Implement `packages/reconstruction/src/aoe2stats_reconstruction/seen.py`, outside
      `estimates/`, reading commands only, and delete T966's markers.
- [ ] T968 [P] [US6] Test first, `xfail(strict=True)`, in
      `packages/reconstruction/tests/test_estimates_losses.py`, on synthetic streams: US6's scenarios
      2, 3, 6 and 7; a loss is dated at the last enemy command after the owner's last sighting and
      before the owner's resignation, and a targeting after the resignation counts nothing; an object
      no enemy command targeted between its last sighting and the resignation is not lost; a unit
      another participant later names is not a loss; an `object-deleted` event changes no result,
      whatever it names (FR-032, FR-036).
- [ ] T969 [US6] Implement
      `packages/reconstruction/src/aoe2stats_reconstruction/estimates/losses.py` over the seen data
      and delete T968's markers.
- [ ] T970 [P] [US6] Test first, `xfail(strict=True)`, in
      `packages/reconstruction/tests/test_estimates_idle.py`: US6's scenario 5; a period lies inside
      the building's first-to-last-order interval and ends at the next order; the stretch after the
      last order is listed apart with what ended it and is in no period; a building estimated
      destroyed has nothing after that clock; a pause for want of housing is never produced (FR-035).
- [ ] T971 [US6] Implement
      `packages/reconstruction/src/aoe2stats_reconstruction/estimates/idle.py` over the queue mechanics
      and the interim policies, and delete T970's markers. If
      `packages/reconstruction/src/aoe2stats_reconstruction/queues.py` does not exist yet, create the
      queue mechanics here exactly as T934 describes them, with their tests, and T934 then extends
      them.
- [ ] T972 [P] [US6] Test first, `xfail(strict=True)`, in
      `packages/reconstruction/tests/test_estimates_population.py`: units enter from the starting
      state, from each queue item's modelled completion less cancellations, and from another
      participant at this one's first naming (FR-031); US6's scenario 4, the excess over the lobby's
      population limit published as its own estimate and removed, naming no object and no unit type
      (FR-033); an identified loss and a change of owner each remove one, an ordered unit enters for
      the population the knowledge base gives it; the living series is the value after each change
      and never passes the limit; a series that goes negative is withheld together with the excess,
      with its entry, and the document is still built (FR-034); a build whose knowledge carries no
      population withholds both through a knowledge gap and nothing else. Depends on T954 and T955.
- [ ] T973 [US6] Implement
      `packages/reconstruction/src/aoe2stats_reconstruction/estimates/population.py` and delete T972's
      markers.
- [ ] T974 [P] [US6] Test first, `xfail(strict=True)`: in `packages/core/tests/test_validate.py`,
      validator rules 15 and 16 of contracts/estimates.md each reject their planted violation, rule 14
      as amended holds, and `estimates_withheld` is outside the register like `knowledge_gaps`; in
      `packages/core/tests/test_register.py`, the register loader accepts the optional `calibration`
      key, the five estimate entries are `published` at `inferred`, each with a method carrying a
      version label and each interim policy in force, a confidence method, no `calibration` yet, and
      a non-claim that states a direction of error (FR-027, FR-029), and the two seen entries are
      `published` at `observed`; and `participant.units_lost` is still `non-determinable`, its
      approximation naming `participant.estimated_unit_losses`, with the existing assertion that its
      approximation is not acceptable changed to `yes` on the owner's ruling of 2026-11-15 (FR-039).
      No other assertion of 006 is weakened.
- [ ] T975 [US6] Publish the seven data, one commit with T974's implementation since a `published`
      register entry and the code that publishes it are never separately true: the seven entries
      moved to `published` and the amended `participant.units_lost` in
      `packages/core/src/aoe2stats_core/truth/register.toml` with the regenerated view; the
      `calibration` key in the register loader; rules 15 and 16, rule 14's amendment and
      `estimates_withheld` among the keys rule 1 exempts, in
      `packages/core/src/aoe2stats_core/truth/validate.py`;
      `packages/reconstruction/src/aoe2stats_reconstruction/estimates/document.py`; the seven data,
      each with its `provenance` entry, written by `apps/analyzer/src/aoe2stats_analyzer/extract.py`;
      `apps/web/src/features/analysis/api.ts` accepting them structurally, with its test, so no
      published document reaches a reader that rejects it; and the goldens of each committed recording
      (`tests/fixtures/replays/<recording>.seen-estimates.json`). Tests in
      `apps/analyzer/tests/test_estimates_document.py` assert: each golden reproduces byte for byte
      and twice over (FR-038); no estimate appears outside `inferred` or without a confidence and a
      non-claim, and every level is the lowest (SC-011); the `reconstructed` block and the seen data
      are byte-identical with the estimates switched off (SC-012); every participant has seen data,
      estimated losses and idle periods (SC-013); the analysis with the seven data takes no more than
      twice the same run's path without them, through T909's harness (SC-015). Add a dated bracket
      note to the unit-loss clarification of `specs/006-replay-analysis-foundations/spec.md` pointing
      at FR-039, and one to `specs/006-replay-analysis-foundations/contracts/analysis-document.md`
      saying `estimates_withheld` joins the keys rule 1 exempts, and one to the units-lost example of
      `specs/006-replay-analysis-foundations/contracts/register.md`, as those files' earlier dated
      notes do. Every non-claim is written from research R16's table and claims nothing beyond it.
- [ ] T976 [US6] Add to `specs/008-match-reconstruction/owner-readings.md`, under O6.3, a few
      stretches the golden estimates call idle and a few they call busy, each a Town Center to select
      at a stated time and its queue to read.
- [ ] T977 **Owner task (information).** Take the O6.3 readings T976 files, and any reading T964
      filed.
- [ ] T978 [US6] Transcribe readings O6.1 and O6.2 (T903), and those of T977 when taken, into the
      playback files, each with its `estimate_error` table (contracts/estimates.md) saying how the
      game's figure and the estimate differ in what they measure, and assert in
      `packages/reconstruction/tests/test_playback_readings.py` that every reading corresponding to an
      estimate has one and that its estimated value is what the analysis produces (FR-037, SC-014). The
      size of a difference fails nothing. Then name those readings as each estimate's `calibration` in
      the register, write in its confidence method what level the recorded error earns, and bump the
      reconstruction version.
- [ ] T979 [US6] The `product-designer` agent specifies the estimate label, the confidence
      indicator and how the non-claim is reached, in `packages/design-system/specs/estimate-value.md`,
      tokens only (constitution VI). An estimated loss is never worded as units lost.
- [ ] T980 [US6] Build it in `packages/design-system/src/composites/AnalysisTimeline/index.tsx`
      with stories and unit tests beside it, read the seven data through typed assertions in
      `apps/web/src/features/analysis/api.ts` and map them in
      `apps/web/src/features/analysis/mappers.ts`: each estimate apart from the observed and the
      modelled values, labelled as an estimate, its confidence shown and its non-claim reachable
      (FR-040). The `visual-reviewer` agent passes the stories in both themes; the baselines are
      captured from CI's render (constitution VII).
- [ ] T981 [US6] Each time a rule that replaces an interim policy is adopted (T936 for execution and
      distribution, T939 for the age in force), swap it into the estimates, change the method's
      version label in the register, bump the reconstruction version, regenerate the goldens, and
      record the errors again against the same readings (FR-031, FR-038). If T936 ends in an
      arbitration, the interim policies stay and this task is closed with that stated.

---

## Dependencies and execution order

- **Phase 1** tasks are independent of each other, except T912a first on the register, then T906
  after T905, then T907, then T908 (one test file, one adapter, one set of goldens, and the
  register after T912a). The owner
  tasks T901 to T904 are requested at once; the first two are the critical path.
- **Phase 2** waits on T906 and T908 only, never on a reading (T924 lands its test first).
- **Phases 3 to 7** are sequential, and phase 3 waits on T901.
- **Phase 8** waits on phase 3 for idle time; T954 and T955 can run right after phase 1.
- **Phase 10** starts after phase 2 and runs beside phases 3 to 7. Its tasks and theirs never run
  at the same time on a file both touch: the queue mechanics (whichever of T934 and T971 runs first
  creates them), the register and its view (T937, T939, T945 against T975, T978), the validator, the
  analyzer's document assembly, the playback files and their test (T946 against T978), and the
  timeline composite with the web reader's two modules (T952, T953 against T975, T980). T975 waits
  on T967, T969, T971 and T973. T978 waits on T903 and T975. T981 waits on T936.
- **Superseding knowledge snapshots are created one at a time**: T925, T940, T941 and T954 never run
  in parallel with each other.
- **Phase 9** closes the feature after everything it describes has landed.

## Parallel example: phase 10

```text
T963, T964 together (a test and a research note; different files)
then T965
then T966, T968, T970, T972 together (four test files)
then T967, T969, T971, T973 in that order (T969 reads what T967 builds; T973 reads the queue
  mechanics T971 may create)
then T974 and T975 as one commit
```

## Implementation strategy

1. **Request the readings first** (T901 to T903): they cost a person's time and gate the exact
   values.
2. **Phases 1 and 2**, which wait on nothing and publish nothing.
3. **Phase 10 next**, since it is the first thing a player sees and it waits on no reading: T963 to
   T975, then the view (T979, T980).
4. **Phases 3 to 7** as the readings arrive: G1, arrivals, spending, scale, the view.
5. **Phase 8** when G1 is closed; **T943** when feature 009 is settled.

`/speckit-implement` is run one phase at a time, naming the task range and the stop condition.
