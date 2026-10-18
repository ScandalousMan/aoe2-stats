---
description: 'Task list for replay-analysis foundations — truth tiers, canonical events, versioned game knowledge'
---

# Tasks: Replay-analysis foundations

**Input**: Design documents from `/specs/006-replay-analysis-foundations/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included and mandatory. This feature is almost entirely Python, so the green-tree gate
applies in its usual form: a test task lands its test marked `xfail(strict=True)` — never a skip,
which passes silently when the behaviour appears by accident — and the implementing task deletes the
marker. A test and the task that turns it green may be separately committed only where the `xfail`
makes the tree green in between, and every task below says which of the two it is.

**Organization**: grouped by the five build phases and the closing phase [plan.md](./plan.md)
fixes, not by story priority. The ordering is forced three times over — the fixture has a closing window, the golden-timeline identity
proof exists only before anything else touches the parse path, and gap severity cannot be computed
before the register exists — and those constraints do not line up with P1/P2/P3. Story labels ride
on each task; a phase serving two stories says so.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel — different files, no dependency on an incomplete task
- **[Story]**: US1..US6, mapping to the user stories in [spec.md](./spec.md); the closing phase's
  tasks serve no single story and carry none
- Every task names its exact file path

## Path Conventions

Per [plan.md](./plan.md): `packages/core/src/aoe2stats_core/{truth,replay}/`,
`packages/replay-engine/`, `packages/knowledge/`, `packages/storage/`, `apps/analyzer/`,
`apps/web/src/features/analysis/`, `scripts/{ops,checks}/`, `tests/fixtures/replays/`,
`infra/migrations/versions/`, `docs/`, `.claude/skills/replay-parsing/`.

## Numbering starts at T601, deliberately

001 reaches T110, 002 runs T201–T215, 003 runs T301–T412, 004 runs T401–T458 and 005 runs T501–T597.
Ids resolve **across** features: `spec_lint.py`'s `task-refs` check treats an id as defined the
moment any feature's `tasks.md` says so. 003 and 004 already overlap at T401–T412, which is exactly
the ambiguity a disjoint range costs nothing to avoid.

**Amended 2026-10-11:** the range did not stay disjoint. 005 runs past T597, and ten ids are defined
by both this file and 005's: T671, T672, T673, T674, T706, T707, T708, T709, T710 and T713. None is
renumbered. The record, and the task that makes a further collision fail the lint (T720), are in
`specs/005-design-system-foundations/tasks.md`.

## What every implementer must know before starting

**`.env.local` points at production.** No task here runs a migration, a backfill or a script against
it. Phase 5's revision goes through `docs/runbooks/database-migrations.md` and nowhere else.

**Never substitute a value for missing knowledge.** Not a default, not an average, not the
neighbouring build's, not the baseline civilisation's. If a task seems to require one, the task is
wrong — stop and say so. This is FR-038, and the whole feature exists because it is easy to break.

**Do not restate a measurement.** Every number measured during specification lives in
`docs/data-sources.md` or in [research.md](./research.md), and artifacts reference it (SC-013).

## Scenario coverage map

| quickstart section           | Phase | Story    | Task(s) that encode it        |
| ---------------------------- | ----- | -------- | ----------------------------- |
| Phase 1 — the fixture        | 1     | US1      | T603, T604                    |
| Phase 1 — the corrections    | 1     | US1      | T606, T607                    |
| Phase 2 — the register       | 2     | US1, US3 | T614, T617, T621              |
| Phase 3 — canonical events   | 3     | US4      | T626, T626a, T628, T630, T632 |
| Phase 4 — the knowledge base | 4     | US2, US5 | T641, T646, T649, T651        |
| Phase 5 — identity           | 5     | US3, US6 | T657, T660, T663, T665        |

---

## Phase 1: Evidence and corrections (plan phase 1 — US1)

**Purpose**: secure the evidence before it expires, and stop the documents that describe the parser lying. Everything here
is true today and none of it depends on any other phase.

**Independent test**: quickstart Phase 1. Both committed archives match their recorded checksums and
neither carries a post-game statistics block; no document names a parser path that does not exist.

**Story goal (US1)**: a reader can trust what the repository says about what a recording contains.

- [x] T601 [US1] **Recover the second reference recording, and do it first.** Constitution I is the
      reason this task leads a feature that otherwise never touches capture: the source purges
      recordings on a schedule this project does not control, so every other task in this list can
      be done tomorrow and this one cannot. Obtain the ranked team-game recording measured during
      specification, **preferring the archive exactly as the source served it** — the existing
      fixture's value rests partly on being verbatim, and `tests/fixtures/replays/README.md` says in
      so many words not to re-zip. Place it in `tests/fixtures/replays/`. Three outcomes are
      admissible and the next three tasks each handle one: the served archive (best), an extracted
      recording that must be repackaged (acceptable, and the repackaging is disclosed), or
      unrecoverable (T605). Do not proceed past T605 on an unrecorded outcome
- [x] T602 [US1] Extend `tests/fixtures/replays/README.md` with the second recording's entry, **in
      the shape the first entry actually has**: a heading sentence carrying the match kind, the date
      played, the date downloaded and the download address; the six-row table — game build, zip
      size, extracted size, members, point of view, operations; and the checksum as a trailing line.
      **If and only if the archive was repackaged**, state that plainly — that the bytes and
      therefore the checksum are this repository's and not the source's, and that the first fixture
      remains the verbatim one — and **amend the README's do-not-re-zip rule with an explicit, named
      exception for this one file**. Repeating the rule beside a file that breaks it would leave the
      README prohibiting what it contains. A repackaged fixture is still evidence; a repackaged
      fixture presented as verbatim is not. The README's prohibition on committing an extracted
      recording beside an archive stands unchanged: the file lands as an archive or not at all
- [x] T603 [P] [US1] Write `tests/test_reference_recordings.py`: for **every** `*.zip` under
      `tests/fixtures/replays/` — the directory also holds a golden JSON file and a README — assert
      the recorded checksum matches, the archive holds exactly one recording, and the parsed post-game block list contains no statistics block. Parameterise over
      the directory rather than naming files, so a third recording added later is covered without
      anyone remembering to extend it. This is the test that lets `docs/data-sources.md` §2 stop
      being an open question, and it is why T601 comes first: the claim needs bytes anyone can
      re-measure, not a citation to a conversation
- [x] T604 [US1] Rewrite `docs/data-sources.md` §2's open question as a settled finding (**FR-045**):
      the post-game statistics block is absent from current-patch ranked recordings, corroborated
      across more than one recording, more than one date and more than one match size, asserted by
      T603. Keep the section's own account of what the answer decides — it is what makes the finding
      load-bearing rather than trivia — and update it to the settled reading: outcome-shaped facts
      are not in the recording, so nothing may be built on their being there. **Record what is still
      unmeasured**: §2 also asked for unranked and custom recordings, calls them ideal rather than
      required, and this feature has neither. Say so rather than letting "settled" read wider than
      the evidence
- [x] T605 [US1] **Not taken: T601 recovered the recording**, so T602 and T604 took the settled
      branch. Kept for the trail; nothing here was done.
      **Only if T601 returned unrecoverable.** Take the narrow honest branch instead of
      T604's: §2 records two measurements, names the one reproducible from a committed fixture,
      states that the second cannot be re-run and why, and stays marked corroborated rather than
      settled. **FR-045** is then satisfied in that narrower form and the spec's
      `## Important unresolved decisions` entry is amended to say which branch was taken. Do not
      soften this into a claim the repository cannot check — an unrepeatable measurement promoted to
      settled is the exact failure `CLAUDE.md`'s filing rule exists to prevent
- [x] T606 [P] [US1] Correct `.claude/skills/replay-parsing/SKILL.md` and
      `docs/adr/0001-replay-parser.md` to name the paths that exist (**FR-046**): the adapter at
      `packages/replay-engine/src/aoe2stats_replay_engine/aoe2rec.py` and the protocols at
      `packages/core/src/aoe2stats_core/replay/`, in place of the parser application directory that
      was never created. **The skill's frontmatter description names that directory too**, and the
      quickstart's grep expects no match anywhere in the file. In the same edit, correct every other
      claim in ADR-0001 that is false today, because `docs/` must be true today and a half-corrected
      ADR is still a lying one: that both engines sit behind one protocol — one has an adapter, the
      other is installed ephemerally by `scripts/checks/parser_canary.py` in the nightly workflow;
      that the canary parses recent replays and publishes success rates — it parses the one
      committed fixture and the secondary engine only reports; that the fast alternative is kept as
      a fallback — [research.md](./research.md) **D1** measured that it cannot open the current
      build, and `docs/risks.md` R3 repeats the same fallback and is corrected in T667; and its
      paragraph calling the post-game statistics block an open question, which T604 settles and
      which must not stay open in one living document while settled in another. **Do not claim to
      have closed the one-protocol gap** — `docs/risks.md` carries it as an open item, it predates
      this feature, and the canonical event model is what makes closing it cheap later. Also remove
      the phantom parser directory from the `python` paths filter in `.github/workflows/pr.yml` and
      add `apps/analyzer/**`, which is in no filter at all today — a pull request touching only the
      analyzer runs no Python job
- [x] T607 [P] [US1] Correct `.claude/skills/replay-parsing/SKILL.md` **and** the 2026-08-24
      correction note in `docs/adr/0001-replay-parser.md` where each states the placement command
      carries no player identifier (**FR-047**). The pinned wheel supplies it;
      `packages/replay-engine/tests/test_aoe2rec.py` pins that as a currently-passing fact across
      every placement in the fixture and names both documents in its own docstring. Only the
      building identifier requires decoding. In the same edit of the skill, correct its collapse
      rule to what is true — one key, for research, no window — and record what the initial-state
      section actually contains and what the pinned wheel exposes of it, referencing
      [research.md](./research.md) **D1** and restating no offset, so the next agent starts from the
      anchor and not from the claim that nothing is there. A skill that a test has been
      contradicting is worse than no skill: it is read by agents that will not check. T606 and T607
      both edit the skill and the ADR, so **they are not parallel with each other** despite the
      marker — run them as one unit
- [x] T608 [US1] Add a **new processing activity** to `docs/privacy/processing-register.md` for
      reference recordings of public matches committed to this repository, covering **every**
      committed recording — the first fixture included, which has never had an entry. **Do not reuse
      the on-demand retention activity**: its safeguards are that a recording is never served to
      anyone and is read only by the analyzer, and a file in a public repository meets neither. One
      row in the activities table in its eight-column shape, and a balancing-test section with the
      five headings every other one uses — interest pursued, necessity, impact on the data subject,
      safeguards, outcome. The test must state the real exposure and not soften it: participants'
      names and profile identifiers sit in the history of a public repository, reachable by no
      erasure or export endpoint, bounded by no expiry, and out of reach in any fork or clone
      already taken. State the necessity honestly too — a recording cannot be pseudonymised without
      destroying the bytes the parser tests exist to read. Cross-reference the register's existing
      open launch item about a committed provider fixture, which names this same class of exposure
      as weighed and not closed; this task does not close that item and must not claim to.
      Constitution IX requires new personal data to reach the register in the same change as the
      data, so this task and T601 are **one commit unit**. Skip only if T605 was taken — and even
      then write the activity for the first fixture, which is owed regardless

**Checkpoint**: the evidence is committed and re-measurable, and no document names a path that does
not exist.

---

## Phase 2: Truth types and the register (plan phase 2 — US1, US3)

**Purpose**: everything above imports these. The register must exist before anything can be checked
against it, and before gap severity can be computed from it.

**Independent test**: quickstart Phase 2. Every loader refusal has a test that plants the defect and
sees the refusal; a numeric confidence is unconstructible; editing the register and not regenerating
the view fails the suite.

**Story goal (US1)**: a reader can look up any datum and learn whether it can be known.
**(US3)**: a tier is a property of a value, enforced by a type rather than by a habit.

- [x] T609 [P] [US3] Create `packages/core/src/aoe2stats_core/truth/tiers.py`: the closed, ordered
      tier set observed → decoded → reconstructed → derived → inferred → predicted (**FR-008**), as
      an enumeration with a total order, plus the weakest-input combinator that computes a result
      tier from its inputs' tiers. A caller must have **no way** to assert a tier stronger than its
      weakest input — that is a function signature, not a review note. `non-determinable` is
      deliberately **absent** from this enumeration: it is a register classification and nothing is
      ever published at it, which is why **FR-001** lists seven classifications and **FR-008** six
      tiers. Tiers with no producer in this feature exist from the start so that 007 adds no member
- [x] T610 [P] [US3] Create `packages/core/src/aoe2stats_core/truth/confidence.py` (**FR-010a**): a
      closed, ordered level set and a mandatory non-empty basis, constructed together. A number is
      **not accepted in any form** — no float field, no numeric coercion, no optional escape hatch —
      because a recording carries no outcome against which a probability could be calibrated, and an
      uncalibrated number is an invented value wearing a measured one's clothes. An empty or
      whitespace basis fails construction
- [x] T611 [P] [US3] Write `packages/core/tests/test_truth_types.py` covering T609 and T610 before
      either is implemented, `xfail(strict=True)`: the order is total; the combinator returns the
      weakest input; a confidence rejects a float, an integer, a numeric string and an empty basis;
      a confidence attached to a value at a tier above inferred is an error, because doubt advertised
      where the method admits none misleads in the other direction
- [x] T612 [US3] Create `packages/core/src/aoe2stats_core/truth/provenance.py` (**FR-009**): tier,
      method identifier and version, inputs, optional confidence, optional non-claim, bound to one
      register datum. Confidence is **required** at inferred and predicted and **forbidden** below
      (**FR-010**), enforced at construction. The method must name an algorithm in a form a reader
      can recompute — a free-text sentence is not one, so the field is an identifier plus a version
- [x] T613 [US1] Write `packages/core/src/aoe2stats_core/truth/register.toml` with the entry schema
      in [contracts/register.md](./contracts/register.md) and the entries that contract lists as
      mandatory (**FR-001**, **FR-002**). Every entry states its source, its method, the knowledge
      it requires, what it depends on and how it is validated, and its evidence is a **reference**
      into `docs/data-sources.md` or [research.md](./research.md) — never a restated number
      (**SC-013**). Include every leaf the published document carries today, at observed or decoded
- [x] T614 [US1] Add to `register.toml` the entries the spec names individually. Unit loss as
      **non-determinable** (**FR-004**), citing the absence of any damage or death event and the
      absence of a post-game statistics block, with its reason, its impact on the analytics that
      wanted it, the approximation that exists, `approximation_acceptable = "no"`, and the single
      condition that would change the answer (**FR-003** — the last question is answered, not left
      open). Explicit deletions and market transactions at **decoded** (**FR-014**) — the wheel returns
      both as raw payloads, so observed would mis-tier them. The
      group-silence datum at **inferred** with its non-claim (**FR-013**). Every datum feature 007
      intends to publish, at planned or blocked, each carrying the knowledge it requires
      (**FR-005**) — that list is what makes gap severity computable in phase 4, so an entry with an
      empty requirement set had better mean it. The starting-state data are **blocked** on the named
      decoder, **not non-determinable**: [research.md](./research.md) **D1** measured them present
      in the file, and the register is the one place that distinction has to be right
- [x] T615 [US1] Implement `packages/core/src/aoe2stats_core/truth/register.py`: the entry type and
      a loader that reads the TOML with the standard library, so `packages/core` keeps its
      zero-dependency rule. Loading **fails at import** on any of the eight refusals in
      [contracts/register.md](./contracts/register.md) — duplicate id, value outside a closed set, a
      non-determinable entry missing any of its five fields, a blocked entry with no named
      dependency, a dangling or cyclic dependency, a tier stronger than its weakest dependency, a
      published inferred entry with no confidence method, or empty evidence. Expose the dependency
      graph, which phase 4 reads to compute severity
- [x] T616 [P] [US1] Write `packages/core/tests/test_register.py` before T615, `xfail(strict=True)`:
      one test per refusal, each **planting the defect itself** rather than asserting the happy
      path. A loader test that only loads the good file proves the file is good, not that the loader
      refuses anything — and the refusals are the whole product here
- [x] T617 [US1] Implement the view renderer in `register.py` and commit its output as
      `packages/core/src/aoe2stats_core/truth/REGISTER.md` (**FR-006a**): grouped by classification,
      non-determinable entries first and in full, with a generated-file header naming its source.
      Add the drift test that renders in memory and compares byte for byte, failing with the
      regeneration command in its message. The file is filed **beside the package**, not under
      `docs/`, because its subject is this product's own data — `CLAUDE.md`'s filing rule sends a
      fact about a package to live next to what recomputes it
- [x] T618 [US1] Verify **SC-012** by hand and record the result in the task hand-back: open
      `REGISTER.md`, look up unit loss, and confirm — **without opening a Python file** — that it
      says why it cannot be known, what that costs, that the approximation is not acceptable, and
      what would change the answer. If that read needs the source, the renderer is the defect.
      **Re-verified 2026-09-22 (T652i)**: `REGISTER.md`'s `## Non-determinable (1)` section, entry
      `participant.units_lost`, states all four without opening a Python file — why: "the operation
      stream is player intent only: it carries no damage event, no death event and no completion
      event, and the post-game operation carries no statistics block, so no field of the file
      states that any unit died"; cost: "no casualty count, no army value over time, no trade
      evaluation, and no military-strength dimension that needs either; the analytics that wanted
      them are not degraded, they are absent"; not acceptable: `approximation_acceptable: no`; what
      would change it: "a recording format that carries outcome events or a post-game statistics
      block"
- [x] T619 [US3] Implement `packages/core/src/aoe2stats_core/truth/validate.py` with the ten rules in
      [contracts/analysis-document.md](./contracts/analysis-document.md), against the document shape
      that exists today — the identity, inferred and gap blocks arrive in later phases and their
      rules are written now and exercised against hand-built documents. Rules 1 and 2 are
      **FR-006** and **FR-007**: every leaf resolves to exactly one published datum, and every datum
      present carries a provenance entry. Rule 5 is **FR-010**; rule 6 is **FR-011**
- [x] T620 [P] [US3] Write `packages/core/tests/test_validate.py` before T619, `xfail(strict=True)`.
      **SC-003** is tested the way it is worded — a coaching-style conclusion placed in a field typed
      observed, decoded and reconstructed, rejected **each time it is attempted**, which is once per
      tier boundary and not once overall. **SC-001**: a document carrying a leaf with no register
      entry is rejected. **SC-002**: a document with a value missing its tier, and one with an
      inferred value missing its confidence or its basis, are both rejected
- [x] T621 [US1] Verify the drift gate bites: edit one impact line in `register.toml`, run the
      suite, confirm the view test fails and prints the regeneration command, regenerate, confirm
      green, and leave the register as it was. A gate nobody has seen fail is a gate nobody knows
      the shape of. **Re-verified 2026-09-22 (T652i)**: edited `participant.units_lost`'s `impact`
      line in `register.toml`; `uv run pytest packages/core/tests/test_register_view.py -q` printed
      `AssertionError: REGISTER.md has drifted from register.toml. Regenerate it with: uv run
    python -m aoe2stats_core.truth.register` (1 failed, 3 passed); ran that exact command, reran
      the same test file and got `4 passed`; restored the edited line and regenerated again —
      `git diff --quiet` on both `register.toml` and `REGISTER.md` confirmed empty
- [x] T622 [P] [US3] Record the naming discipline in `packages/core/src/aoe2stats_core/truth/`'s
      module docstring and enforce it in T615's loader: a datum id states what was measured, never
      what a reader would like it to mean (**FR-012**) — commands rather than times, ordered rather
      than built. This is 003's **FR-043b** discipline applied to the whole vocabulary, and it is
      cheap to hold now and impossible to retrofit once ids are in published documents

**Checkpoint**: a tier is a type, a confidence cannot be a number, and the register is loadable,
readable and enforced.

---

## Phase 3: Canonical events (plan phase 3 — US4)

**Purpose**: put an engine-independent vocabulary on the existing seam, and prove it loses nothing.

**⚠️ This phase changes nothing else on the parse path.** The byte-identical golden timeline is the
only available evidence that the canonical stream carries everything the old path read, and it is
available only while nothing else on that path moves.

**Independent test**: quickstart Phase 3. The committed golden timeline is untouched in `git status`
after being produced through the new stream.

**Story goal (US4)**: when the parser changes, the adapter changes and nothing above it does.

- [x] T623 [P] [US4] Create `packages/core/src/aoe2stats_core/replay/events.py`: the closed event
      vocabulary and the source protocol in
      [contracts/canonical-events.md](./contracts/canonical-events.md). Every event carries a
      match-clock time, the participant it is attributed to, its kind and its tier (**FR-016**), and
      the protocol is what everything above the adapter imports (**FR-015**). `building-placed` is
      **decoded**, not observed — its building identifier comes from a payload this repository
      decodes, and the event takes its weakest input's tier. `chat` carries a channel and **no
      text**: the text is personal data this feature has no use for, and leaving it out of the
      vocabulary keeps constitution IX out of this seam entirely. Declare the two starting-state
      kinds **without a producer** (**FR-020**), so the day the decoder lands no type changes
- [x] T624 [P] [US4] Write `packages/core/tests/test_events.py` before T623, `xfail(strict=True)`:
      every kind has a tier; an event without a participant is constructible only for the
      match-level kinds; the two declared-only kinds exist as types
- [x] T625 [US4] Implement `packages/replay-engine/src/aoe2stats_replay_engine/canonical.py`: a
      generator mapping the wheel's operations to canonical events in **one pass, with no copy and
      nothing retained past the fold** (**FR-021**). Be exact about what that guarantees: the wheel
      has already materialised every operation before this code runs, which is where the resident
      memory R3 measured comes from and which nothing here can remove. **Every event's time comes
      from one clock accumulated from the sync operations' increments** — only actions carry a time
      of their own; chat and the post-game block carry none. That clock was checked against the
      first fixture and matches both the post-game match time and every action's own time exactly;
      assert both in a test, since nothing verifies it today. View-lock operations are camera
      positions and are excluded because they carry no intent — not because they feed the clock,
      which they do not. **Collapse only research, age-up and resignation**, first occurrence over
      the whole match, no window (**FR-018**) — what the extractor does today. **Never collapse
      queueing, placement or movement**: the first fixture's unit-queue commands reduce to a few
      dozen distinct tuples, and collapsing them erases the villager count. Nothing is attributed to
      a participant after their exit, and an observer or empty slot yields no participant at all —
      not a silent one. Neither committed recording shows a player resigning while the match runs on
      at length ([research.md](./research.md) **D11**), so test the exit rule on a synthetic stream
      as well
- [x] T626 [US4] Represent every **action** the adapter does not decode as an `undecoded` event
      carrying the engine's own label and the payload length, never dropped and never guessed at
      (**FR-019**). Command kinds that arrive without decoded unit ids — formation, stance, patrol,
      stop and the rest — are emitted as `units-commanded` with an **empty** id list, never an
      inferred one. Add the conservation test over every committed recording: every operation the
      wheel reports is an emitted event or is counted in a named drop category — sync, view-lock,
      collapsed, after-exit, unseated. Two terms cannot balance it, because **FR-018**'s collapse
      and the exit rule both remove operations by design. The second
      recording carries an action kind the wheel itself cannot name, so this rule has a live
      instance to assert on. A silent drop is the failure mode that cannot be found later, because
      nothing downstream knows to miss it
- [x] T626a [US4] Write the market and deletion decoders in
      `packages/replay-engine/src/aoe2stats_replay_engine/canonical.py`, in the placement decoder's
      mould (**FR-014**). The wheel returns sell, buy and delete as raw byte payloads, so direction,
      resource, amount and the deleted object's id must be derived **empirically** — sweep the byte
      positions across every instance in every committed recording, cross-check against values that
      can be verified independently, and golden-test the result over all of them, exactly as the
      building identifier was found. These events are **decoded**, exact, and never blended into an
      inferred quantity. If a field cannot be pinned with confidence, emit the event without it and
      register the field as blocked — a guessed amount at the decoded tier is the precise lie this
      feature exists to prevent. Test first, `xfail(strict=True)`
- [x] T626b [US4] Decode the chat channel in
      `packages/replay-engine/src/aoe2stats_replay_engine/canonical.py`. The channel sits inside the
      same JSON string as the message text, so the text cannot be avoided on the way to it: parse,
      keep the channel and the participant, and **discard the text at the adapter**. Assert that no
      message text appears in any canonical event, in either committed golden stream, or in any log
      line this module emits — the text is personal data this feature has no use for, and
      constitution IX is kept out of this seam by that assertion, not by intention. Chat carries no
      time of its own and takes T625's accumulated clock
- [x] T627 [US4] Populate the engine dependency record inside the adapter (**FR-044**) from installed
      distribution metadata for the engine and each requirement it declares, and make an empty
      record a construction error. `apps/analyzer/src/aoe2stats_analyzer/extract.py` publishes an
      empty dependency map as a literal today, and the column to hold it has existed all along —
      this is the task that stops the document claiming to identify its engine while recording
      nothing (**SC-011** is asserted in phase 5, where the document carries it)
- [x] T628 [US4] Re-express the existing timeline extractor in
      `packages/replay-engine/src/aoe2stats_replay_engine/aoe2rec.py` as a fold over the canonical
      stream, and **prove the committed golden timeline comes back byte-identical**. `git status`
      shows `tests/fixtures/replays/AgeIIDE_Replay_500546441.timeline.json` untouched. Three things
      will move it if handled naively, and each has been measured: the published `actions` figure is
      counted **before** collapse today, so the fold counts raw commands there or
      `actions_per_minute` shifts; unit-queue and placement commands are **not** collapsed today and
      must stay so; and research is the only command kind collapsed today, with resignation. The
      extractor makes **two** passes today — one to find the final match clock, one to reduce —
      while its module and class docstrings both claim one; the fold removes the first pass, and the
      docstrings are corrected in this task. Do **not** regenerate the golden file to make a test
      pass: the fixtures README already carries that instruction and ADR-0001's own failure mode was
      a parser upgrade that silently changed what was being read. A diff here means the stream lost
      or altered something, which is the one thing this phase may not do
- [x] T629 [US4] Commit the canonical stream for each **committed** reference recording — one if T605
      was taken, two otherwise — as a golden file under
      `tests/fixtures/replays/`, following the regeneration discipline the README already states for
      the timeline: regenerate only on an engine upgrade or a deliberate logic change, never by hand,
      and read and explain every diff it produces
- [x] T629a [US4] Emit `match-started` from the adapter in
      `packages/replay-engine/src/aoe2stats_replay_engine/canonical.py`, as the first event of every
      stream, at clock zero. [contracts/canonical-events.md](./contracts/canonical-events.md) lists
      it as produced and nothing produces it: neither committed golden carries one, and the four
      `event.match_started.*` register entries name a golden stream as their validation that does
      not contain them. **Phase 4 cannot start without it** — the coverage pass collects every
      participant's civilisation from the stream, every rule query requires one, and build
      resolution needs the build; the only other route to those three is the wheel's header, read
      from above the adapter, which **FR-015** forbids. Read the build, the resolved map, the lobby
      presets and the seated participants from the header fields the timeline fold already reads,
      unchanged (**FR-016**). Carry each civilisation as **the game's integer identifier, never a
      name** — naming is the knowledge base's job — and change `ParticipantEntry.civilisation` in
      `packages/core/src/aoe2stats_core/replay/events.py` to an integer to match: nothing
      constructs that type today, so the change is free now and costs a golden regeneration later.
      Observers and empty slots are absent, not present and silent. The event comes from the
      header and corresponds to **no operation**, so the conservation test subtracts it by name;
      do not let it pass by widening a tolerance. This is a deliberate logic change, so both
      canonical goldens are regenerated under the README's discipline — the expected diff is one
      event at the head of each file and its count, and anything else is a defect. **The timeline
      golden stays byte-identical**: the fold ignores the new kind. Test first,
      `xfail(strict=True)`: the first event of every committed recording's stream is
      `match-started`, its participants equal the seated slots, and its build equals the one
      `tests/fixtures/replays/README.md` records
- [x] T629b [US4] Bind the adapter to the protocol
      [contracts/canonical-events.md](./contracts/canonical-events.md) names as the seam
      (**FR-015**). The protocol has no implementation and no importer today: the stream's entry
      point takes an already-parsed recording, and the engine's name, version and dependency
      record live in three places. Give `Aoe2RecExtractor` in
      `packages/replay-engine/src/aoe2stats_replay_engine/aoe2rec.py` the dependency record from
      T627 and an `events` method taking the archive's bytes — the same well-formedness and
      input-size refusals as `extract`, then the parse, then the stream, never returning the
      operations. Assert the binding with the protocol's own runtime check, so a drifted signature
      fails a test and not a reader. **This is the entry point T632 extends the refusal test to**,
      and the one object T653, T655 and T658 read the parser's three identity components from.
      Test first, `xfail(strict=True)`
- [x] T630 [P] [US4] Write the engine-independence test (**SC-009**): walk every payload type's field
      names and assert none appears in a deny-list **generated from the wheel's own output keys** across
      **every committed recording** — the two expose different action kinds, so a list built from one
      is blind to the other's keys — and that no payload carries a raw byte sequence, a byte offset or a length other
      than `undecoded`'s (**FR-017**). Generating the deny-list rather than writing it by hand is the
      point — a hand-maintained list tracks what someone remembered, and the wheel is what changes
- [x] T631 [P] [US4] Write the collapse test (**SC-010**): the age-up command the fixture's player
      issued twice by double-clicking appears once in the canonical stream. Assert over every
      committed recording rather than one, and assert the inverse too: repeated unit-queue commands
      are **not** collapsed, because a test that only checks collapse cannot see over-collapse
- [x] T632 [US4] Extend the existing input-size refusal test to the canonical entry point T629b
      creates, **and add a real peak-memory measurement beside it**. The existing test is named for
      the memory ceiling and measures no memory: it asserts that an oversized input is refused,
      which says nothing about what an accepted input consumes. This feature puts three accumulators
      on that path — the stream's consumers, the group-silence state and the coverage pass — and
      the second recording's object-id space is several times the first's. **Only the first exists
      at this task**: T633 and T648 each re-run this measurement when they add theirs and raise the
      ceiling with the derivation, so a ceiling recorded here is a floor for two later tasks, not
      the feature's. Measure peak allocation over every committed recording through the full
      canonical path and record the ceiling the test asserts against, with its derivation, in the
      test itself. Also assert the declared-only kinds are never emitted
      (**FR-020**): that is what makes the reserved vocabulary honest — the day a producer lands,
      this test is what changes, and no type does
- [x] T633 [US4] Implement `packages/replay-engine/src/aoe2stats_replay_engine/silence.py`: the
      group-silence observable — register datum `participant.group_silence_episodes` — computed
      from commanded-unit events only, published at the
      **inferred** tier with a confidence whose basis states the command intensity and the silence
      length for that instance (**FR-013**). **State its blind spot in the datum's method**: only
      move, interact and order carry decoded unit ids; formation, stance, patrol and stop do not, so
      exactly the commands that park a military group are invisible and a parked group reads as
      silent. That blind spot caps the level the banding may assign, and the non-claim names it.
      Every instance carries the non-claim verbatim — it is not a casualty count. It consumes no
      deletion and no market event and is never summed with either (**FR-014**). Its banding lives
      in the register entry's method, so changing it is a register change with a regenerated view,
      not a constant edit. **This is the datum a reader is most likely to misread as a loss
      figure**, which is why the non-claim is a required field of the type and not a comment near it.
      Re-run T632's peak-memory measurement with this accumulator on the path and raise its ceiling
      with the new derivation. In the same register edit, add `event.unit_unqueued.unit_id` and
      `event.unit_unqueued.count` at observed and planned —
      [contracts/register.md](./contracts/register.md) requires every kind's payload fields and T614
      missed this one. Neither recording produces a cancellation, so its validation names the
      synthetic cancellation test, not a golden

**Checkpoint**: one vocabulary, no engine-shaped field, nothing dropped, and the golden timeline
proves nothing was lost.

---

## Phase 4: The knowledge base and its gaps (plan phase 4 — US2, US5)

**Purpose**: a versioned, immutable, offline body of game rules that refuses to answer what it does
not know.

**Independent test**: quickstart Phase 4. A discounted unit returns its civilisation-adjusted cost
with the effect applied; an unmodelled civilisation returns a gap; the coverage pass over every
committed recording reports no blocking gap outside **FR-022b**'s enumerated list, and every entry on
that list is held by a strict expectation.

**Story goal (US2)**: the engine can ask the rules a question for a stated build and civilisation.
**(US5)**: a missing rule stops the analysis instead of corrupting it.

- [x] T634 [US2] Create `packages/knowledge/` as a workspace member — `pyproject.toml` depending on
      `aoe2stats-core` only — and register it in the root `pyproject.toml` workspace list, its
      `testpaths`, its mypy settings and the `known-first-party` list under the ruff isort settings —
      the seven module names are enumerated there, and an eighth left out turns `ruff check` red on
      this task's own commit. **In the same change, narrow the two format globs in
      `package.json`** to exclude `packages/knowledge/packs` and `packages/knowledge/snapshots`. The
      workspace format script globs every JSON file under `packages/` and ignores only what
      `.gitignore` names — a `.prettierignore` is not consulted, because the script passes its own
      ignore path — so a vendored data file would fail the pull-request check until someone
      reformatted it, rewriting vendored bytes and invalidating every digest taken over them. This
      trap is invisible until the pack lands, which is why it is disarmed in the task before. **Also add
      `packages/knowledge/**` to the `python` paths filter in `.github/workflows/pr.yml`**: without it
      every later pull request touching only this package runs no Python job at all, the failure that
      file's own comments already record twice. Update the root `pyproject.toml` comment that counts
      the workspace members
- [x] T635 [US2] Write `scripts/ops/import_knowledge_pack.py`: reads a **local checkout** of the
      source at a stated commit and writes `packages/knowledge/packs/aoe2techtree/`. It opens no
      socket, and its header carries the same warning `scripts/ops/sync_map_thumbnails.py` does,
      plus the statement that automating the download is the moment a provider becomes mandatory
      (**FR-032**). Nothing in the running system, the build or the tests fetches a knowledge source,
      and the way that is guaranteed here is that no code performs a fetch at all
- [x] T636 [US2] Vendor the pack at a pinned commit with its `LICENCE.md`, whose five fields are
      named **exactly** as `scripts/checks/asset_packs.py` matches them — `Source`, `Licence`,
      `Permitted usage`, `Ruling`, `Checked` (**FR-033**); a field written any other way fails the
      gate as missing. The ruling leads with **COPY IN**, one of the two verdicts T637 makes the
      gate require. Only a source whose licence permits it is vendored (**FR-031**): this one is MIT.
      Add a **third section** to `docs/asset-packs.md` for knowledge packs, as feature 005 added one
      for typefaces — the row does not belong in the game-assets table — and widen that document's
      opening scope sentence, which names game assets only. **State the residual risk once and do
      not borrow the wrong precedent**: the files are MIT, but their values were produced upstream
      by reading the game's data file, which the publisher's usage rules do not authorise. This
      repository already weighed that for this source — `docs/data-sources.md` §1 rules its data MIT
      and the risk register's R7 records the residual — so cite both and restate neither. The flags
      pack records no such risk because it has no game-derived content; this pack is not in that
      position
- [x] T637 [US2] Extend the list of roots in `scripts/checks/asset_packs.py` and the `asset-packs`
      paths filter in `.github/workflows/pr.yml`. That list holds **(root, size budget) pairs**, not
      bare paths, so each new root needs its own named budget constant with its own stated
      justification, as the two existing roots have. Add **two**: `packages/knowledge/packs`, and
      `packages/knowledge/snapshots` — the snapshots root is append-only by design and ships inside
      the package, so it is the one that most needs a ceiling and had none. Size each budget from
      the measured payload with stated headroom. The check is scoped by root today, so until both
      are added it neither sees the new pack nor runs when it changes, and constitution X is
      enforced only where the gate looks. **Also make the gate refuse a ruling that leads with
      neither verdict**: today its enforcement is a substring test for READ ONLY, the COPY IN
      pattern is display-only, and any other string — a typo included — passes, so the two-verdict
      claim the artifacts make is true of its label and false of its gate. **Prove it bites,
      twice**: drop one licence field, confirm the check names the pack, restore it; then replace
      the ruling's verdict with a stray word, confirm the refusal, restore it
- [x] T638 [US2] Implement `packages/knowledge/src/aoe2stats_knowledge/snapshot.py`: the identity —
      source, source version, described build, content digest (**FR-024**) — loaded through
      `importlib.resources` so it works identically from a serverless bundle and a virtual
      environment. The digest is recomputed on load and a mismatch **refuses to load**. Publishing a
      new snapshot never modifies or removes an existing one (**FR-025**), and a test walks every
      committed snapshot directory asserting each file matches its recorded digest — which is how
      immutability is asserted rather than merely requested
- [x] T639 [US2] Implement the promotion sequence in `snapshot.py` (**FR-034**): source change, new
      pack revision, new unvalidated snapshot, recorded validation, promoted. Only a promoted
      snapshot is resolvable, and a promotion flag set with an empty validation record is refused.
      An unvalidated snapshot is never promoted, and no source is treated as authoritative without
      validation against the game or a second source, with the validation performed recorded
      (**FR-030**)
- [x] T640 [US2] Implement the normaliser producing `rules.json` from a pack: units, buildings,
      technologies, their costs, their training, construction and research times, their age
      requirements and prerequisites, civilisations, and the civilisation bonuses that modify any of
      the above (**FR-022**). A unit identifier may live in the source's unit table or its upgrade
      table — four technology identifiers in the committed fixture do — so merge both into one keyed
      space and record which table each came from. Where the vendored pack and any second reading
      disagree on a field, record the disagreement and carry which source the stored value came from
      (**FR-028**) in `disagreements.toml`, rather than resolving it by precedence alone
- [x] T641 [US2] Implement build resolution (**FR-027**): exact match on the described build among
      promoted snapshots, or a gap with the no-snapshot cause. There is **no nearest, no latest and
      no fallback parameter** — the function must not accept one, because an argument that exists
      will be passed. A recording from a build with no snapshot is a gap with its own severity, not
      an analysis against a neighbouring snapshot
- [x] T642 [US2] Implement carry-forward in `snapshot.py` per [research.md](./research.md) **D4**:
      a snapshot may describe a build later than the revision it was imported from, only when its
      validation record lists **every** intervening build with the notes consulted, where they were
      read, the date, and the reading. A build missing from that list makes the snapshot
      unpromotable. This is forced, not chosen: no source carries a build key, and the committed
      fixture's build is newer than the newest revision the source has implemented, so without this
      the only committed recording cannot be analysed at all. Record the weakest link in the
      attestation — the fixture's own build has no publisher page and its notes come from a
      secondary listing — **in the validation record, not in a comment**
- [x] T643 [US2] Implement `packages/knowledge/src/aoe2stats_knowledge/query.py` with the surface in
      [contracts/knowledge-base.md](./contracts/knowledge-base.md). `civilisation` is **keyword-only
      and required** on every rule query, so there is no way to ask for a generic value and therefore
      no way to be handed one (**FR-023**). Every answer carries the snapshot identity that produced
      it, the source the stored value came from, and the effects applied in order. The return type is
      a union of answer and gap with **no third branch** — no bare value, no default parameter, no
      caught-and-continued gap anywhere in the package. **SC-008**'s "by construction rather than by
      inspection" is this signature, and T650 asserts it by introspection
- [x] T644 [US2] Implement `packages/knowledge/src/aoe2stats_knowledge/effects.py`: structured
      civilisation effects — the civilisation, the verbatim source sentence and its key, whether it
      is modelled, an explicit identifier list rather than a fuzzy class name, the field, a closed
      operation, the operand, and the second reading that validated it. Transcribed by hand from the
      English strings that ship in the MIT pack, which **FR-031** permits with its provenance
      recorded. A bonus that is team-wide, gated on an age the recording cannot place, or
      conditional on state is recorded as **not modelled** with its reason, and its fields stay
      gapped — a bonus is never half-applied
- [x] T645 [US2] Model the civilisations that appear in the committed reference recordings, and only
      those (**FR-022a**) — **six** with both fixtures committed, two from the first and four from the
      second with none shared ([research.md](./research.md) **D11**); two if T605 was taken. Both players in the first fixture trained units their civilisation
      discounts, so this is not an optional refinement: without it the one committed recording
      produces blocking gaps on day one. Implement the conservative rule in `query.py` — a
      civilisation absent from the modelled set refuses **every** civilisation-qualified cost and
      time, because which fields its bonuses touch is precisely what is not known. Coverage grows by
      whole civilisations and the gap report is the backlog
- [x] T646 [P] [US2] Write `packages/knowledge/tests/test_query.py` before T643–T645,
      `xfail(strict=True)`: a discounted unit returns its adjusted cost with the effect and its
      source sentence; the same unit for an unmodelled civilisation returns a gap and **never the
      baseline**; a build one higher than any snapshot describes returns a gap; asking without a
      civilisation is a type error. Two snapshots answer from their own contents and neither is
      silently upgraded to the other (**US2** scenario 2)
- [x] T647 [US5] Implement `packages/knowledge/src/aoe2stats_knowledge/gaps.py`: the gap record with
      entity, field, build and affected civilisation (**FR-035**), a closed cause set, what it
      prevents by register datum id (**FR-036** — what it stops, not that something is missing), and
      a severity **computed** from the register's dependency graph, never supplied by a caller
      (**FR-037**). Blocking when at least one register datum that is neither blocked nor
      non-determinable requires the field, as **D7** words it; informational otherwise. The two
      readings agree today only because no non-determinable entry names any knowledge.
      [research.md](./research.md) **D7** is why this is computed:
      read naively, nothing this feature publishes depends on a cost, every gap would be
      informational, and **SC-007a** would pass vacuously
- [x] T648 [US5] Implement `packages/knowledge/src/aoe2stats_knowledge/coverage.py`: take a canonical
      stream, collect every entity and every participant civilisation, and ask for every field any
      register datum requires. Its output is the gap list the document publishes. A blocking gap
      prevents publication of every value depending on it while leaving independent values
      untouched, and **no default, average or neighbouring value is ever substituted** (**FR-038**).
      Re-run T632's peak-memory measurement with the coverage pass on the path — it is the last of
      the three accumulators that measurement names — and raise its ceiling with the new
      derivation. Implemented, tested and green: the peak-memory ceiling holds with the coverage
      pass live on the path (still 900 MB, re-derived — the accumulator does not move it).
      SC-007 (removing a required field) passes for real. **SC-007a passes for recording 1 and not
      for recording 2.** Recording 1's only blocker was Koreans' archer-armor techs (211/212/219),
      recorded `modelled = "no"` — a 2026-09-20 remediation of this hand-back re-measured it, found
      the recording's own use unconditional and the classification simply wrong, corrected
      `effects.toml`, and that case now carries no marker at all. Recording 2's three blockers are a
      different kind and this task cannot fix them inside its own editable scope: Franks' Castle
      cost discount (building 82) is age-scaled and `query.py` has no age argument to resolve it
      against; Gurjaras' camel/elephant bonus (units 1755, 239) is a team bonus by the pack's own
      text and correctly stays unmodelled; and two building ids (490, 673) are absent from the
      vendored pack entirely (Gate/wall-segment variants `aoe2techtree`'s own `data.json` never
      enumerates). See `test_coverage.py`'s own `xfail` marker on
      `test_each_committed_recording_reports_zero_blocking_gaps` for the full citation.
      **No follow-up task owns closing this, because none can**: `/speckit-analyze` (2026-09-21) found that each of recording 2's three blockers is a
      limit of the one lawful vendored source, not a hole in this feature's transcription, and the
      requirement was amended to match rather than a task written that would have to fail. That is
      **FR-022b** — the exception is a closed, enumerated list held by `test_coverage.py`'s own
      `xfail(strict=True)`, which turns red the day any entry is closed
- [x] T649 [P] [US5] Write `packages/knowledge/tests/test_coverage.py` before T648,
      `xfail(strict=True)`. **SC-007**: remove a required field from an in-memory copy of a snapshot,
      run the pass, and assert exactly the dependent values are withheld, a gap names the entity,
      field, build and civilisation, and every independent value is still produced. **SC-007a**: the
      pass over each committed recording reports zero blocking gaps outside **FR-022b**'s enumerated
      list, parametrized per recording so a recording that is clean stays clean. **FR-039**'s
      aggregate is asserted in T652
- [x] T650 [P] [US5] Write the structural tests that make refusal a property of the code rather than
      a habit: introspect every public query in the package and assert its return type is the
      answer-or-gap union (**SC-008**); assert no module in `packages/knowledge` imports a network
      library; and assert the whole package's tests pass with the network blocked (**SC-006**,
      **FR-026**), which `tests/conftest.py` already enforces at the socket workspace-wide
- [x] T651 [US2] Add the source assessments to `docs/data-sources.md` as a new section, one
      subsection per source assessed in [research.md](./research.md) **D3** (**FR-029**): scope,
      reliability, update mechanism, version identifier, coverage, known limitations and the date the
      assessment was made. Record the rejections and **why**, including that the two community
      datasets are one generation pipeline run twice and therefore cannot cross-validate each other,
      and that the game's own data file is barred by the publisher's usage rules. This section also
      finally gives feature 002's licence rulings a living home — 002's own register was never
      written, and they survive today only in a frozen task list and a module docstring
- [x] T652 [US5] Add `analysis_knowledge_gaps` to `packages/storage/src/aoe2stats_storage/models.py`
      per [data-model.md](./data-model.md) §7. **The table is the aggregate** (**FR-039**): one
      repository function grouping by build, cause and severity over a window, and one check script
      under `scripts/checks/` that prints the rate. Do **not** mirror the ingester's quarantine
      counter — that is a column on a per-run table fed by a multi-stage aggregator, and the
      analyzer has no run, no counters and no logger to attach one to; inventing a run concept for
      this would be a second table the data model says this feature does not have. A pattern of gaps
      introduced by a game patch must be visible as a rate, not discovered one analysis at a time.
      The table holds no personal data: a participant is not a column. **Two consequences of the
      migration living in T663 and not here, recorded rather than discovered**: this phase is green
      and mergeable — the revision test compares the expected revision to the migrations head, not
      the models to the database — but the repository function and the check script are dead code
      in production until T663's revision is applied, and nothing may call either before then.
      That is also why the script is wired into the nightly workflow by T663 and not by this task:
      a nightly job against a table that does not exist would fail for the whole gap between the
      two phases
- [x] T652a [US2] **Rename the committed snapshot directories to honest labels, before phase 5
      publishes anything that names one.** Three directories exist and the production one is called
      `aoe2techtree-fixture-promoted`: it is the promoted snapshot both committed recordings resolve
      against, it carries neither the build it describes (180059) nor anything distinguishing it
      from its sibling in a listing, and it calls itself a fixture. Its sibling
      `aoe2techtree-fixture-promoted-177723` is test infrastructure for `test_query.py`, and
      `aoe2techtree-fixture` is a `describes_build = 0` stub for T638's digest mechanism — both say
      so in their own headers and neither is production data.
      [contracts/knowledge-base.md](./contracts/knowledge-base.md)'s "On disk" section now states the
      rule this breaks: a label is never parsed, but it MUST NOT describe a promoted production
      snapshot as a fixture, and it MUST carry the build it describes, so a gap row or an object key
      is readable without opening `snapshot.toml`. **The window is this phase**: nothing has
      published yet, no analysis identity names a snapshot, and no object key carries one, so the
      rename costs 34 references across seven test and source files today and is impossible after
      T655 — **FR-025** makes a snapshot immutable the moment an analysis names it, and an operator
      reading a gap row is then stuck with the word _fixture_ for the life of the product. No digest
      changes: `compute_digest` hashes `rules.json` and `effects.toml`, never the directory name, and
      resolution is exact-match on `describes_build` among promoted snapshots, so nothing parses what
      is being renamed. Update the reference in `docs/data-sources.md` §6 in the same change — it is
      a living document and must be true today. **Where this rides**: phase 4's own pull request if
      it is still open, because these directories are files that pull request creates and renaming
      them there lands them on `main` under their final names with no rename in history; otherwise
      it heads phase 5, which is the last stop before T655 publishes

### Review remediation (pull request #90, `reviewer` REJECT 2026-09-21)

The pre-merge review rejected phases 2-4 on spec compliance. Every finding below was re-verified
against the code before being written down. **These block #90's merge**; T652a rides with them.
Three were arbitration and are decided, with the decision recorded in the task that carries it.

- [x] T652b [US2] **Put the coverage pass on `query.py`'s public seam, and fix what it reports when
      it knows nothing.** Four findings, one file pair, one commit. (a) `coverage.py:356` returns
      `()` when the stream carries no build, so `validate.py` rule 8 sees no blocker and the document
      publishes everything — the spec's own edge case says an unresolvable build is a gap of
      **blocking** severity, and `build is None` is the same ignorance. Emit it. (b) `_gap_for`
      re-resolves `snapshot_for(build)` per `(entity, field)` and returns the same
      `no-snapshot-for-build` gap each time — 612 of them on recording 1's stream. T662 would raise
      on the second insert: `analysis_knowledge_gaps`' unique index is
      `(identity_digest, entity_kind, entity_id, field, coalesce(civilisation_id, ''))` and all five
      are equal across those 612. Resolve the snapshot **once**, before the entity loop, emit exactly
      one gap, return — and emit it whether or not the stream references any entity, which is the
      other way **FR-027**'s gap currently goes unrecorded. (c) `coverage.py` imports
      `_civilisations_modelled`, `_raw_value_for_field` and `_rules` from `query.py`, restates
      `_civilisation_qualified`'s whole step order in `_gap_for`, and duplicates `_TIME_FIELDS`.
      **Give `query.py` the field-presence check and a rules-override seam and call its six public
      functions instead** — decided 2026-09-21 rather than left as duplication, because **SC-008**'s
      "by construction rather than by inspection" is a claim about the answer-or-gap union being the
      only route to a value, and the pass that actually produces the published gap list was not
      taking it; `test_structure.py:42-46` excludes `coverage.coverage` from its own sweep, so the
      guarantee was weaker than the test read. Remove that exclusion in this change. (d)
      `load_all_snapshots` / `load_resolvable_snapshots` / `snapshot_for` carry no `functools.cache`
      where `query._rules`, `query._civilisations_modelled` and `effects` all do, so one
      `coverage()` re-read and re-digested three snapshots 612 times — 1.47 s, linear in entities,
      inside the analyzer's function budget (**FR-049**, constitution I). Cache them. Test first for
      each of (a) and (b), `xfail(strict=True)`; **state in the hand-back what each test printed when
      run against the unfixed code** — a regression test that passed before the fix proves nothing
- [x] T652c [US5] **Replace SC-007a's blanket `xfail` with the enumeration FR-022b actually asks
      for.** Depends on T652b — both edit `test_coverage.py`. Today one
      `xfail(strict=True, reason=_RECORDING_2_XFAIL_REASON)` sits over a body asserting
      `blocking == []`, and a 26-line prose string stands in for the list. It fails **FR-022b** three
      ways: closing one of the three blockers leaves the assertion failing and the marker holding, so
      a stale entry is never signalled; the body never inspects _which_ gaps came back, so a fourth
      blocker from a real transcription defect — the thing FR-022b says MUST be closed and never
      enumerated — hides behind the same marker forever; and a `reason=` string is asserted against
      nothing. Replace it with a module-level tuple of **three** entries, each carrying
      `(entity_kind, entity_id, field, civilisation, cause)` plus why the single vendored source
      cannot close it and what would, and assert **set equality** between the observed blocking gaps
      and that tuple. That assertion fails in both directions, which is the whole point, and the test
      then passes for real with **no `xfail` at all**. Recording 1 keeps its unmarked, genuinely
      passing case
- [x] T652j [US2] **Correct `query.py`'s module docstring, which asserts the opposite of the data
      committed beside it, and delete the guard it promises that was never written.** Three blocks —
      `query.py:17-21`, `:45` and `:298` — say `civilisations_modelled` is `[]` on every promoted
      fixture and that "T645 has not run". T645 ran in this same pull request:
      `packages/knowledge/snapshots/aoe2techtree-180059/snapshot.toml` names six civilisations, and
      every one of the six queries answers for real — which is exactly what `test_coverage.py`'s
      SC-007a case now depends on. Worse, `:21` documents a fail-loud mechanism that does not exist:
      it says `_civilisation_qualified` "raises `NotImplementedError` if it is ever reached past
      that check", and there is no `raise NotImplementedError` in the file — the string occurs once,
      in that sentence. Either restore the guard or delete the promise; do not leave a reader
      relying on it. This is the first thing the next agent reads before touching the query surface,
      and it is the shape of defect this feature's whole register discipline exists to distrust — a
      claim with nothing behind it. Missed when the review's findings were grouped into T652b–T652i
      and added on 2026-09-22 once `test_query.py` and `test_effects.py` were found carrying the
      same stale "T645 has not run" prose; sweep those two docstrings in the same change
- [x] T652d [US4] **Stop an unfamiliar operation from losing the whole match, and stop the market
      decoder publishing a scaled value at the exact tier.** (a) `canonical.py:530` raises
      `EngineParseError` on an operation kind the adapter does not know, while an unknown _action_
      degrades to `undecoded` correctly. **FR-019** sanctions two outcomes and aborting is neither:
      the day a patch or a wheel upgrade adds one top-level kind, every replay in the corpus stops
      analysing — the exact failure the canonical model exists to insulate against (`docs/risks.md`
      R3). Emit `undecoded`, or add a named `unknown_operation` accounting term so the conservation
      test still balances; keep the raise for a _malformed_ operation, not an unfamiliar one. (b)
      `_MARKET_STEP = 100` multiplies a payload count into an amount published at **decoded**, which
      **FR-014** requires to be exact, while `register.toml:564` declares `requires_knowledge = []`
      although the entry's own method admits the constant is not in the recording. **Decided
      2026-09-21: publish the step count, not the amount.** The count is in the payload and is
      exact; the multiplication is knowledge-qualified and belongs in 007's reconstruction layer,
      where a versioned constant can gap. This keeps the decoded tier honestly exact and needs no
      snapshot change. Rename the register entry and the payload field to say what is carried
      (**FR-012**), and regenerate both canonical goldens under the README's discipline — the
      expected diff is the market events' one field, and anything else is a defect
- [x] T652e [US4] **Move the golden-regeneration tool out of the shipped package and put it on the
      seam.** `packages/replay-engine/src/aoe2stats_replay_engine/canonical_golden.py` is in `src/`,
      so it is in the wheel deployed to Vercel and the VPS, and it computes
      `Path(__file__).parents[4] / "tests/fixtures/replays"` — a repository-relative path that exists
      in neither, which constitution XII forbids. Move it under `scripts/ops/`. Worse, its
      `live_serialisation` imports two private adapter functions and calls `canonical_events`
      directly, bypassing `Aoe2RecExtractor.events()`, the `max_raw_bytes` ceiling and the
      `CanonicalEventSource` protocol T629b exists to establish — so **every committed canonical
      golden was produced through that bypass**, and `test_canonical_golden.py:40`,
      `test_canonical.py:36`, `test_canonical_collapse.py:41` and `test_canonical_independence.py:26`
      re-verify them the same way. The evidence for **FR-017**, **FR-018**, **FR-019**, **SC-009**
      and **SC-010** never flows through the interface those requirements are about;
      `test_extract.py`'s `isinstance` check proves the seam exists and nothing proves anything uses
      it. Drive the tool and all four tests through
      `Aoe2RecExtractor(max_raw_bytes=ANALYSIS_MAX_RAW_BYTES).events(zip_bytes)`. Depends on T652d —
      they share every one of those test files
- [x] T652f [US1] **Close the register's drift against the code and the contract it describes.** The
      `event.unit_queued.producing_building` entry says `method = "read unchanged"`;
      `canonical.py:222` keeps the first of several producing-building ids and discards the rest. The
      register is the one document whose job is to be right about how a datum is produced
      (**FR-002**), so state the narrowing. Separately,
      [contracts/canonical-events.md](./contracts/canonical-events.md) lists four `unit-queued`
      payload fields and `UnitQueuedPayload` carries four, while the register has three:
      `building_type` has no entry, and [contracts/register.md](./contracts/register.md) requires
      every kind's payload fields — under validator rule 1 that leaf resolves to nothing the moment
      it is published. Same shape for `StartingObjectPayload`'s four fields collapsed into one
      `event.starting_object.attributes`. Add the missing entries and regenerate `REGISTER.md`.
      Depends on T652d — both edit `register.toml`
- [x] T652g [US2] **Move the civilisation-id table into the snapshot, behind its digest.**
      `coverage.py:196` hard-codes `_DEFAULT_CIVILISATION_NAMES`, mapping replay civilisation
      integers to pack names. That is game knowledge: **FR-023** says every knowledge answer is
      qualified by build and **FR-024** says a snapshot's contents are covered by its digest, and
      this table is in neither — not in `rules.json`, not digested, not versioned, not in the
      register. The numbering shifts when civilisations are added, and when it does a raw id
      resolves to the **wrong modelled** civilisation and `cost` returns a confident wrong answer
      with no gap, which the `unknown-civilisation-{id}` fallback does not catch because the id is
      in the table and merely wrong. Put it in the snapshot and gap on an id the snapshot does not
      name. Depends on T652a and T652b
- [x] T652h **Gate the pinned source commit, which lives in five files and is asserted in none.**
      `b9d494df6921d4080df69b22f9dbb7a4d1dcd9f0` appears in `docs/data-sources.md` §6,
      `docs/asset-packs.md`, the pack's `LICENCE.md` and `MANIFEST.json`, and three `snapshot.toml`
      files; the measurements derived from it — last-implemented build, commit, date, the
      unimplemented builds — are restated in both `docs/data-sources.md` §6 and `snapshot.toml`.
      Only `source_version` is functional and the rest are prose copies. `CLAUDE.md` is explicit
      that a number in two files will be wrong in one, and that a living fact in `docs/` is
      trustworthy only because a test asserts it — there is no test. Add one check under
      `scripts/checks/` asserting all five agree, and wire it into the `python` job. Independent of
      every other task here
- [x] T652i **The documentation findings, which share no file with the code tasks.** (a)
      `docs/data-sources.md` lines 119, 547 and 559 carry list-continuation text at column 0, which
      terminates the bullet it belongs to. Line 119 is in §1's `slotinfo` decode — a section this
      feature does not touch, damaged by a Prettier reflow riding in on `69ada014`, which also
      flipped `*recent*` to `_recent_` at line 330. Repair the three bullets; a living document may
      not be left broken by scope creep. (b) `scripts/checks/asset_packs.py:56` justifies the
      snapshots budget as "a reasoned estimate, not a measurement, because the directory does not
      exist yet" — it exists and measures 544 KB, and T637 asked for the measured payload with
      stated headroom. Re-derive it. (c) **FR-030 was amended** 2026-09-21 to admit a second reading
      of the same source through a different field where no independent source exists, which is what
      `effects.toml`'s 16 `validated_by` fields actually do; make each of them name the two fields
      read and say no independent source was available, so the record distinguishes the weak form
      from the strong one. (d) T618 and T621 are marked `[x]` on verification claims with no artifact
      on disk. The mechanisms are real and pass; re-run both by hand and record what they printed

- [x] T652k [US5] **Dedupe the coverage pass by civilisation, not by slot — the duplicate-gap fix
      closed one cause and left its siblings.** T652b resolved the snapshot once so an unresolvable
      build emits one gap instead of 612, and the argument it was fixed on — that
      `analysis_knowledge_gaps`' unique index is
      `(identity_digest, entity_kind, entity_id, field, coalesce(civilisation_id, ''))`, so
      identical rows collide on T662's second insert — **was never carried to the other causes**.
      `coverage.py:236-251` keys `entities_by_slot` by **slot** and emits one gap per
      (slot, entity, field), so two seated participants on the same civilisation referencing the
      same entity emit N identical gaps. Reproduced against the real packaged snapshot by forcing
      recording 2's four slots onto one civilisation: **16 gaps, 13 distinct, `('building', '82',
    'cost', 'Franks')` four times**, every copy equal on all five index columns. Neither committed
      recording can see it — both seat four distinct civilisations — and a mirror matchup or any
      team game with two players on one civilisation is ordinary. A query result depends on
      `(entity, civilisation, build)` and never on the slot, so collect per civilisation name, or
      dedupe on the index's own key before returning. **Test it with two slots on one civilisation
      and assert `len(result) == len(set(...))`**, not merely that a gap exists — the defect is
      duplication and "at least one" cannot see it, which is the same trap T652b's own test had to
      avoid. **In the same change, close the guard that was supposed to prevent this class**:
      `packages/knowledge/tests/test_structure.py:224-256` walks for `ast.ImportFrom` with
      `module == "aoe2stats_knowledge.query"`, but `coverage.py:125` is
      `from aoe2stats_knowledge import ... query ...` and calls by attribute — so it forbids exactly
      the form T652b removed and cannot see the form T652b introduced. Writing
      `query._civilisation_qualified(...)` into `coverage.py` passes it today, while its docstring
      claims every gap came from the public functions. Walk `ast.Attribute` whose value is
      `Name(id="query")` and whose `attr` starts with `_`, and fail on any
- [x] T652l [US2] **SUPERSEDED by T652m, which carried both corrections.** Kept for the trail: it was dispatched, handed back, and reverted uncommitted when verifying it found the civilisation misidentification. **Correct two false measurements now frozen behind a snapshot digest.** Both live
      in `effects.toml`, in both promoted snapshots, which are byte-identical and must stay so.
      (a) The `[[civilisation_id]]` record for `raw_id = 33` claims participant 4 of recording 2
      _"researches technology 488 (Kamandaran)"_ and that 488 is `NotAvailable` for Gurjaras in
      `packages/knowledge/packs/aoe2techtree/trees/GURJARAS.json`. Measured against the committed golden: **participant 2 researches 488,
      not participant 4**; participant 4's exclusive research is **687**; and **488 has no node at
      all in that tree file** — absent, not `NotAvailable`. The file's own header comment 90 lines
      above already says both of those things, so the entry contradicts its own file. The mapping
      `33 → Persians` is **correct** and the elimination on unit 39 holds — strike only the false
      clause and leave the true observation. This matters more than an ordinary typo because T652i
      re-labelled this record **"Strong form (FR-030)"** without re-reading it, and a validation
      record that misstates what was read is the exact thing FR-030's amendment exists to prevent.
      (b) Two lines call `data.json` _"all sixty-one civilisations"_. It carries **53**, and
      `trees/` holds 53 files, and `docs/data-sources.md:497` says 53 for this same pinned commit —
      four occurrences of a wrong count, two inside `validated_by` strings. Recompute both
      snapshots' digests, update both `snapshot.toml`s, and confirm the two stay equal

- [x] T652m [US2] **BLOCKING — three of the six modelled civilisations are misidentified, and two
      of them are not in either match.** Confirmed 2026-09-23: the user named recording 2's match as
      Franks + Teutons versus Tatars + Persians. Identifying each participant from the pack's own
      tree files, using **technology nodes only** (`id` prefixed `Tech_`), reproduces that exactly —
      slot 1 Franks, slot 2 Persians via Persians-only `Tech_488` (Kamandaran), slot 3 Teutons,
      slot 4 Tatars via Tatars-only `Tech_687`. Four for four against ground truth, so the method is
      sound. Applied to recording 1 it narrows slot 2 to **Malians alone**, via Malians-exclusive
      `Tech_577` (Farimba), with Byzantines excluded outright.

      | raw id | register says | measured |
          | ------ | ------------- | -------- |
          | 2      | Franks        | Franks — agrees |
          | 4      | Teutons       | Teutons — agrees |
          | 9      | Koreans       | **Saracens** |
          | 8      | Gurjaras      | **Persians** |
          | 26     | Byzantines    | **Malians** |
          | 33     | Persians      | **Tatars** |

          **Four of the six were wrong.** Ids 9 and 26 were supplied by the user on 2026-09-23 from
          the SiegeEngineers aoc-reference-data dataset `docs/data-sources.md` §6 assesses, and both corroborate the
          independent tree measurement: 26 is what `Tech_577` (Farimba) pinned, and Saracens is among
          the 19 candidates id 9 narrowed to. **Take the mapping from that source, transcribed by hand
          with its provenance recorded — do not re-measure it.** `docs/data-sources.md` §6 has assessed
          it since 2026-08-30 and rules it read-and-transcribe-only, which is exactly what **FR-031**
          permits for a source with no licence. The hand-measurement this task exists to undo was work
          the repository's own referential had already done.

          **Byzantines and Gurjaras are in neither match.** Byzantines' Pikeman -25% is the flagship
          example in `packages/knowledge/tests/test_query.py` and in
          [quickstart.md](./quickstart.md), modelled for a civilisation no committed recording plays.
          Malians and Tatars are modelled nowhere.

          **Why the earlier identification went wrong, recorded so it is not repeated**: it rested on
          *unit* node ids, and **the pack's `node_id` space is not the game's unit id space**. The
          counterexample is in the data — recording 2's slot 2, now known to be Persians, trains unit id
          1755, which the pack lists as `Unit_1755_101`, Camel Scout, `ResearchedCompleted` for Gurjaras
          alone and absent from the Persians tree. Technology ids did hold, on all five participants
          that a unique technology pins. Treat unit-id exclusivity as unsound and technology-id
          exclusivity as sound until something measures otherwise; that distinction is a property of the
          vendored source and belongs in `docs/data-sources.md` §6.

          **Scope decided 2026-09-23: correct the identification *and* transcribe the three real
          civilisations.** Modelling only what is already written would leave ~846 blocking gaps — both
          of recording 1's players and one of recording 2's — and those are transcription gaps, which
          **FR-022b** says MUST be closed rather than enumerated. The bonus prose is in the vendored
          pack's English strings and is quoted in the dispatch; only one bonus per civilisation touches
          a cost or a time:

          | civilisation | the one cost/time bonus | selector |
          | ------------ | ----------------------- | -------- |
          | Saracens | "Market trading fee only 5%; Markets cost -100 wood" | building 84, wood -100, `add` |
          | Malians  | "Buildings cost -15% wood" | all 28 building ids, wood x0.85, `multiply` |
          | Tatars   | "Thumb Ring, Parthian Tactics free" | techs 437 and 436, cost `set` to zero |

          Everything else each of them carries — hit points, armour, attack, line of sight, livestock,
          trade fees, Town Centre sheep — touches no field this knowledge base answers and is recorded
          `modelled = "no"` with that as the reason, which is the same treatment the existing entries
          give a bonus out of scope. A bonus is never half-applied.

          **Scope of the correction**: the `[[civilisation_id]]` table; `civilisations_modelled` in both
          promoted snapshots; the effects transcribed for Byzantines and Gurjaras, which are dead and
          whose replacements for Malians and Tatars are not written; every example and test naming a
          Byzantine discount; and `_RECORDING_2_ENUMERATED_BLOCKING_GAPS`, whose Gurjaras entries name a
          civilisation not in the match. Also carry T652l's two uncontested corrections — the false
          participant-4/`Tech_488` clause and the four "sixty-one civilisations" for 53 — so
          `effects.toml`'s digest moves once. **Superseded framing, kept for the record:** T652l was written to correct a false clause in the
          `raw_id = 33` validation record and was **reverted uncommitted** when verifying it turned up
          something larger. The pack's own per-civilisation tree files, read with unit and tech nodes
          separated (the `id` field carries the kind: `Unit_239_82` vs `Tech_488_82` — conflating them
          gives wrong answers, which is how the first pass went astray), say:
          **slot 1 → Franks** and **slot 3 → Teutons**, both agreeing with the committed table; but
          **slot 4 narrows to Tatars alone**, via `Tech_687` which is Tatars-only and absent from the
          Persians tree — while the table says `raw_id = 33` is Persians. Persians-only `Tech_488`
          (Kamandaran) is researched by **slot 2**, not slot 4, which the record itself got backwards.
          **Slot 2 is outright contradictory**: it trains unit 1755 (Camel Scout, `ResearchedCompleted`
          for Gurjaras and absent from both the Persians and Tatars trees) *and* unit 38, which is
          `NotAvailable` for Gurjaras and available to both the others — no single civilisation trains
          both. So the evidence splits two-to-one against the committed `raw_id = 8 → Gurjaras`.
          **What must be settled before this is edited**: whether the pack's `node_id` space is the
          game's own unit and technology id space in every case, or only mostly — because if it is not,
          every exclusivity argument in `effects.toml`'s header, including the ones that look sound,
          rests on an unchecked assumption. Do not resolve this by picking the reading that preserves
          the current table. **What it reaches if wrong**: T645's six modelled civilisations, T652g's
          `[[civilisation_id]]` table, and SC-007a's 15-gap enumeration, which names Gurjaras twice and
          attributes a blocker to a civilisation that may not be in the match. Tatars is modelled
          nowhere. Carry T652l's two uncontested corrections into the same change rather than landing
          them separately — the false participant-4/`Tech_488` clause, and the four places calling
          `data.json` "all sixty-one civilisations" where it holds 53 — so `effects.toml`'s digest moves
          once, not twice

- [x] T652n **Two readings of the same file disagree, and one of them may be serving wrong names in
      production.** `docs/data-sources.md` §6 states that the aoc-reference-data dataset it names _"confirmed all
      45 civilisation ids this repository had already derived from two frozen provider fixtures"_ —
      ids where `apps/api/src/aoe2stats_api/civilizations.py` holds 9 = Byzantines and
      26 = Lithuanians. The same file read on 2026-09-23 gives **9 = Saracens** and
      **26 = Malians**, and the vendored tech trees independently pin 26 to Malians. At most one of
      those two readings of one file is right. Either the dataset is keyed to the replay's
      civilisation id space and not Relic's `civilization_id` — in which case §6's confirmation
      claim is false and the fixture-derived table was never corroborated at all — or
      `civilizations.py` is wrong, and every match page has been serving wrong civilisation names.
      **This is outside feature 006** and is filed here only because 006 found it; it reaches
      `apps/api`, so it outranks finishing this feature. Establish which space the dataset is keyed
      to before changing anything, and do not "fix" `civilizations.py` toward the replay space
      without evidence that Relic uses it — `civilizations.py`'s own header records that its first
      table was confidently wrong in exactly that way

- [x] T652o [US2] **Sweep every bonus of all six civilisations — the transcription silently dropped
      the ones that touch a tracked field, and recording 1's zero is hollow because of it.** The
      third review found Malians' Team Bonus _"Universities work +80% faster"_ dismissed in
      `effects.toml` as touching no tracked field. It touches `production_time`: a technology's
      production time **is** its research time, one of the six fields the coverage pass walks.
      Measured — Malians and Teutons both answer 100, 50, 60 and 30 for technologies 47, 50, 93 and
      140, and recording 1's Malians player researches **all four**. They are answered with the
      un-adjusted baseline, which is the **FR-038** substitution the conservative rule exists to
      forbid, and it is the reason SC-007a reports zero for recording 1: not because nothing blocks,
      but because a blocker was never written down. Three siblings, all verified the same way, all
      predating this remediation — fixing Malians alone leaves them, which is the one-of-N failure
      this project keeps repeating:
      Persians' _"Town Centers and Docks ... work +5/10/15/20% faster"_ (the work-faster half touches
      `production_time` at buildings 109, 621 and 45 — Persians' Villager answers 25, same as
      Teutons'); Teutons' _"Murder Holes, Herbal Medicine free"_, absent from the file **entirely**,
      so Teutons pays `{food:200, stone:100}` and `{food:0, gold:200}` for technologies 322 and 441
      that its own bonus makes free; and Franks' _"Chivalry (Stables work +40% faster)"_, likewise
      absent.
      **Do not fix only the four named.** Walk **every bullet** of all six civilisations' prose in
      the vendored `strings.en.json` — Franks 120151, Teutons 120153, Saracens 120158, Malians
      120175, Tatars 120182, Persians — including Unique Techs and Team Bonuses, and give each one
      an entry: `modelled = "yes"` with its selector, or `modelled = "no"` with a real reason and an
      explicit selector. **A bullet that appears in neither state is the defect**, so assert that
      too: a test that counts the bullets per civilisation and fails when the file accounts for
      fewer. That test is what stops this recurring; without it the next transcription drops
      something again and nothing notices.
      Then recompute what each recording reports. Recording 1 will no longer be zero — enumerate its
      blockers under **FR-022b** only where the blocker is a team-wide or age-gated bonus the model
      genuinely cannot place, never where it is something nobody transcribed. Update
      `test_coverage.py`, its docstrings and [quickstart.md](./quickstart.md), which all currently
      say recording 1 is clean. Recompute both digests; keep them equal
- [x] T652p **Close the review's smaller findings, three of which make a test prove less than it
      claims.** (a) `packages/knowledge/tests/test_coverage.py:569` asserts
      `len(result) == len(set(keys))`, which holds for an empty result — add `assert result` so the
      duplicate-gap regression cannot pass vacuously. (b) The same file at `:620`, `:669` and `:677`
      passes building ids as `unit_id`; harmless today because those tests never resolve the entity,
      but it now reads as a claim that 84 and 68 are units. (c)
      `packages/knowledge/tests/test_query.py:45-48` newly claims Franks/Pikeman returns "a plain,
      unmodified baseline" and **no test asserts it** — a spurious Franks cost effect would pass
      every test in the file. Add the control. (d) The rounding row I added to
      [data-model.md](./data-model.md) §6 is true of `multiply` only: `add` also rounds half up, but
      mapping `set` **truncates** with `int(...)`, and scalar `set` returns a float — so
      `age_requirement(436, "Persians")` answers `3.0`. State which operations the convention
      governs, or make them agree. (e) Malians' selector includes Bombard Tower `236`, which that
      civilisation's own tree marks `NotAvailable` — the discount asserts a cost for a building it
      cannot build. (f) `effects.py:431` has no guard against `add` driving a cost negative;
      unreachable today, but `add` is live data now and the invariant is unasserted

- [x] T652q **A "works faster" bonus was attached to the building instead of what it produces — the
      fourth review's blocker.** Persians' "Town Centers and Docks … work +5/10/15/20% faster"
      selects buildings 109, 621 and 45 themselves, so `production_time` of Persians' Villager (83)
      answers 25 — Teutons' baseline — and technologies 101, 102, 103, 213 and 249 answer theirs,
      silently; recording 2's Persians player trains and researches all six. Franks' Chivalry
      ("Stables work 40% faster") selects Stable units only, while Malians' University row already
      reads "work faster" as research time, so Stable technologies 209, 254 and 39 answer baseline
      too. `test_bullet_coverage.py` could not see it: it proves a row exists, not where it points.
      (1) Re-point both rows at every unit and technology whose `produced_at` is the named building,
      **restricted to what the civilisation's own tree offers** (`node_status` other than
      `NotAvailable`, in `packages/knowledge/packs/aoe2techtree/trees/`); apply the same restriction
      to Chivalry's Hussar (441) and Malians University's 64, 373, 377, 608, 909 and 910. (2) Add a
      test that fails on the shape, not the instance: for every production-speed row, the selector
      equals exactly that set. (3) Malians' "Buildings cost -15% wood" omits Fish Trap (199), which
      its tree offers; add a test that the selector equals every building the tree offers with
      wood in its cost. (4) Recompute both digests; keep both promoted files byte-identical.
      (5) Re-derive recording 2's enumerated blockers in `test_coverage.py` from what the pass
      emits — the building-621 tuple goes, the Persians and Franks entities above arrive — and
      replace `test_effects.py`'s building-621 test with Villager-refuses-for-Persians plus a
      Teutons control. (6) Same files, same commit: "Can build Caravanserai" is filed as having no
      representable entity, but 1754 is in `rules.json` — label it by what actually represents it;
      the stale "28-building" references; `effects.py`'s claim that `add` is live since T652o (the
      free-technology model uses `set`) and that `source_text` is byte-for-byte (five rows are
      not); the digest credited to T652o in `snapshot.toml`; and `test_effects.py`'s int-type test,
      which passes on the unadjusted baseline — assert the value and a non-empty `applied`
- [x] T652r **Numeric effects can still produce a value the game cannot.** A scalar `add` and a
      cost `multiply` with a negative operand go below zero unguarded; a time `multiply` divides by
      1 + X, so X = -1 divides by zero and X < -1 gives a negative time; a cost `set` truncates a
      fractional operand with `int()`. Reject, when `effects.toml` is parsed, a negative cost
      `multiply` operand, a time operand of -1 or below, and a non-whole cost or
      `age_requirement` `set` operand; guard `add` on both paths. Give "works X% faster" its own
      operation name, so that `multiply` means one thing on every field
      ([data-model.md](./data-model.md) §6, `operand` row). No committed effect reaches any of
      these; **lands before T655 publishes anything**
- [x] T652s **SUPERSEDED by T652u and T652w**, whose team condition makes a team effect match every civilisation on the owner's team. **A team bonus refuses only for its owner.** Malians' University row gaps
      `production_time` for Malians alone; an ally's University technologies still answer the
      baseline, the substitution research.md D5 forbids ("keep their fields gapped"). A rules query
      does not know a player's allies. Decide where the gap is raised — the coverage pass knows
      every seated civilisation, and gapping the field for every participant in a match that seats
      the owner never answers wrong — and record the decision in research.md D5 before building it.
      Neither committed recording triggers it; **lands before T655 publishes anything**
- [x] T652t **SUPERSEDED by T652y**, which stops carrying prerequisites at all. **Twenty prerequisite references in `rules.json` point at nothing.** Technology 436 lists
      `{kind: building, id: 437}`, but 437 is a technology, and 437 lists building 185. The fault is
      in `packages/knowledge/src/aoe2stats_knowledge/normalise.py`'s kind assignment, so
      `query.prerequisites` answers with entities that do not exist. Fix it there, regenerate
      both promoted snapshots' `rules.json` and digests — in place, which is still lawful because
      nothing has published a snapshot's identity yet (**FR-025** freezes it at T655) — and assert
      that every prerequisite resolves. **Lands before T655 publishes anything**

- [x] T652u **A conditional bonus is a rule, not a refusal** (fourth review M4, arbitrated
      2026-09-28: "Villager time is equal to standard villager time * bonus multiplier"). Amended
      [research.md](./research.md) **D5**, [data-model.md](./data-model.md) §6 (`condition`, and times
      keep their fraction) and [contracts/knowledge-base.md](./contracts/knowledge-base.md) ("The
      query surface", "Civilisation qualification") state the model; build it. (1) `effects.py`:
      parse the optional closed `condition` — `age` with an operand table by age, `researched`
      naming a technology, `team`; reject any other value. (2) `query.py`: `cost` and
      `production_time` take `context=` (age, researched technologies, the team's civilisations);
      apply only the effects whose condition holds; a team effect matches every civilisation on the
      owner's team; reaching a conditional effect without the input that decides it **raises**.
      Times keep their fraction and "works X% faster" divides by 1 + X; costs still round half up.
      (3) Re-model the five refusals that touch a carried field: Persians' Town Center and Dock
      (by age, 5/10/15/20%), Franks' Castles (-15/25% by age), Chivalry and Kamandaran (after the
      technology), Malians' University (team, 80%). Refusals on fields the pack does not carry stay.
      _Done for four: Kamandaran stays refused, because the source never states its wood amount
      ([research.md](./research.md) D5)._
      (4) `coverage.py` asks whether a field is modelled, not for its value, so a modelled
      conditional effect is no gap. Re-derive both recordings' enumerated blockers in
      `test_coverage.py` from what the pass then emits. (5) Tests, each shown failing first: Persians
      Villager 23.8/22.7/21.7/20.8 s by age, Teutons 25 in every age as the control; Chivalry
      before and after; a Malians ally's University research 80% faster, an opponent's not; a
      conditional effect with no context raises and an unconditional one does not. Recompute both
      digests; keep both promoted files byte-identical. **Blocks the merge of phases 2-4**
- [x] T652v **The event stream does not say who is on whose team.** A team effect (T652u) needs the
      player's team, and `match-started`'s participant entry carries a slot and a civilisation only.
      The recording's header carries each player's team: add it to
      [contracts/canonical-events.md](./contracts/canonical-events.md) and the participant entry,
      emit it from the adapter, and regenerate the golden streams with
      `scripts/ops/canonical_golden.py`. A free-for-all or unset team is its own value, never team 0
      shared by strangers. Then make the coverage pass supply each participant's team as
      `Context.team`, so an unmodelled teammate gaps every cost and time for its allies
      ([contracts/knowledge-base.md](./contracts/knowledge-base.md), "Civilisation qualification"
      step 1). Contrast test: the same stream with that ally modelled answers. The pass merges entities
      per civilisation (T652k), which cannot carry two teams: key it by civilisation and team. A gap
      naming an unmodelled teammate is the same row for every ally that raised it, so de-duplicate it
      against `analysis_knowledge_gaps`' unique index, as T652k did for slots. **Lands before T655
      publishes anything**

- [x] T652w **A team bonus reaches only what its owner can research — the fifth review's
      blocker.** T652q restricted Malians' University row to what Malians' own tree offers, which
      was right while the row refused for Malians alone; T652u then made it a `team` effect that
      applies to every ally, and nobody re-derived the selector. Measured with Malians on the team:
      Chemistry (47) answers 55.6 s for Franks, but Siege Engineers (377) answers **45 s with no
      effect** — it should be 25 — and Arrowslits (608) 25 where it should be 13.9; 64, 909 and 910
      the same. Every modelled ally can research at least one of the six. (1) A `team` row selects
      every technology produced at the named building, **with no owner-tree restriction**: each
      ally's own tree decides what that ally can research, and `available_to` already answers that.
      Change `test_selector_availability.py` to derive a team row that way, and add Franks-ally
      377 = 25 with Franks-opponent 377 = 45 as the contrast. (2) Validate `Context`: a supplied
      `team` that omits the queried civilisation, or an `age` outside 1-4, raises instead of
      answering the baseline — measured, Malians with `team={"Franks"}` answers 100 s, and Franks'
      Castle at age 5 answers 650. (3) Same files, same commit: `coverage.py`'s comments still quote
      contract wording 57a78a5b removed; `effects.py`'s `source_text` claim names five exceptions
      where there are six (Malians' pierce-armour row loses the pack's line break); `effects.toml`
      reasons that say a rules query cannot carry allies, age or match state contradict amended D5 —
      each such row is refused only because its field is not carried, and should say that alone;
      `snapshot.toml` says "five" re-modelled refusals and lists four; T652q's `validated_by`
      readings are dated 2026-09-26 but were made 2026-09-28; `query.production_time` is typed and
      documented as returning an integer and now returns a fraction. Recompute both digests and
      keep both promoted files byte-identical. **Blocks the merge of phases 2-4**

- [x] T652x **The fifth review's follow-ups, each small, all inside digested or validated content.**
      (1) Malians' University team row's `validated_by` lists who can research Siege Engineers (377)
      and omits Tatars, whose tree marks it `ResearchedCompleted`. (2) Nine refusal reasons
      (Citadels, Ironclad, Crenellations, Bimaristan, Counterweights, Tigui, Farimba, Silk Armor,
      Timurid Siegecraft) still justify themselves by a condition; amended research.md D5 does not
      admit that — each is refused because its field is not carried, and should say that alone, as
      T652w did for eight others. (3) `Context(age=True)` passes the age check and answers the
      baseline: reject a `bool`. (4) Malians' pierce-armour `source_text` drops the pack's line
      break, and [data-model.md](./data-model.md) §6 says `source_text` is verbatim: transcribe it
      exactly, or record the deviation in the row. Recompute both digests; keep both promoted files
      byte-identical. **Lands before T655 publishes anything**, since FR-025 freezes the snapshot
      then

- [x] T652y **The pack's tree links are not the game's prerequisites — the sixth review's H2,
      arbitrated 2026-09-28: do not carry them.** T652t made every `BuildingTech` link resolve to an
      entity that exists, but resolving is not being right: `link_id` is the tech-tree screen's
      display link ([research.md](./research.md) D3). Hand Cannoneer (5) answers technology 6, Drill,
      for every civilisation, from Bohemians' tree alone, where the game requires Chemistry; Thumb
      Ring answers Slinger; Arson answers Flemish Militia. (1)
      `packages/knowledge/src/aoe2stats_knowledge/normalise.py` stops emitting `prerequisites`:
      remove the link and `building_upgraded_from_id` readings, `_LINK_NODE_KIND` and T652t's
      resolver, so no entity in `rules.json` carries the key. (2)
      `packages/knowledge/src/aoe2stats_knowledge/query.py`: `prerequisites` keeps its signature and
      answers `field-absent` for every entity the snapshot names; `entity-absent` still answers for
      one it does not. (3) `packages/core/src/aoe2stats_core/truth/register.toml`:
      `reconstruction.prerequisite_order_check` becomes `blocked`, `blocked_on` naming a lawful source
      that states the game's prerequisites; regenerate `REGISTER.md`. By D7 the gap is then
      informational. (4) Regenerate both promoted snapshots' `rules.json` in place (lawful until T655,
      **FR-025**), recompute both digests, keep both promoted files byte-identical, and say why in
      each `snapshot.toml`. (5) `effects.toml`: the `validated_by` readings that resolved a unit line
      through `rules.json`'s prerequisite chain name a field that no longer exists; add one header
      note saying where that chain is re-verifiable now, and leave the dated readings as they are.
      (6) Tests, each shown failing first: no entity in either promoted `rules.json` carries
      `prerequisites`; `query.prerequisites` answers `field-absent` with severity `informational` for
      an entity the pack names, and `entity-absent` for one it does not (the contrast); replace
      T652t's resolution test, which asserted existence only; re-derive `test_coverage.py`'s
      enumerated blockers from what the pass emits. _Measured: the blocked entry was the only one
      requiring `age_requirement` and `available_to` too, so all three fields' gaps turn
      informational and buildings 490 and 673 keep 6 blocking tuples, not 12._ (7) `docs/data-sources.md` §6, aoe2techtree: Scope
      and Coverage stop claiming prerequisites, and Known limitations says what the links are.
      **Lands before T655 publishes anything**
- [x] T652z **The sixth review's follow-ups.** (1)
      `packages/knowledge/src/aoe2stats_knowledge/effects.py` checks each operand but not whether the
      operation fits the field: `faster` on a `cost` parses, then raises
      `AssertionError("unreachable")` at the first query; `multiply` or `add` on `production_time`
      parses and rounds a time to an integer, against [data-model.md](./data-model.md) §6's rounding
      row. Reject `faster` on any field but `production_time` at parse time, and make `multiply` and
      `add` keep a time's fraction. Tests, each shown failing first: `faster` on a cost refuses to
      load; a `multiply` and an `add` on a time answer the fraction; a cost `multiply` still rounds
      half up (the contrast). No committed effect reaches either, so no digest moves. (2)
      `packages/replay-engine/tests/test_canonical.py` computes its expected teams with the
      adapter's own formula, over two recordings that never carry the sentinel, so `canonical.py`'s
      `1 → None` branch is untested. Add a test over a synthetic header: `resolved_team_id = 1`
      gives `None`, two such participants are not allies of one another in the coverage pass, and
      real team ids pass through unchanged. Show it failing against the adapter with the translation
      removed. _Found on implementation: the sentinel alone was already tested
      synthetically (`test_a_participant_with_the_no_team_sentinel_reads_as_no_team_at_all`), which
      the review missed; the new test adds the case mixing the sentinel with real ids in one match._

**Checkpoint**: the rules are queryable offline, versioned by build, refuse what they do not know,
and every refusal is counted.

---

## Phase 5: Identity and the published document (plan phase 5 — US3, US6)

**Purpose**: assemble the four foundations into one validated, reproducible, non-destructive
document. This is the only phase that changes what production publishes. **T652a lands first if
phase 4's pull request merged without it**: T655 is the first thing to publish an analysis that
names a snapshot, and **FR-025** freezes the label at that moment.

**Independent test**: quickstart Phase 5. Two analyses of the same fixture are byte-identical; an
older analysis reproduces exactly after a knowledge refresh.

**Story goal (US3)**: every number says where it came from. **(US6)**: an analysis stays reproducible
after everything underneath it moves.

- [x] T653 [US6] Implement `packages/core/src/aoe2stats_core/truth/identity.py`: the tuple of
      recording, parser name and version, parser dependencies, knowledge version, reconstruction
      engine version and analytics version (**FR-040**), with a digest over its canonical
      serialisation. The reconstruction engine carries an explicit not-applicable marker until 007
      ships; **analytics does not** — it is this feature's own version for the coverage pass and
      the group-silence method ([data-model.md](./data-model.md) §8), and marking it not-applicable
      would let a banding change keep the same digest and never trigger T657a's recompute
      (**FR-042**). Both components exist from the start, so the tuple's **shape never changes** —
      retrofitting identity onto published artifacts is far harder than designing it in, which is
      why US6 is specified now
- [x] T654 [P] [US6] Write `packages/core/tests/test_identity.py` before T653, `xfail(strict=True)`:
      the digest is stable across processes and insensitive to field ordering; two identities
      differing in any one component produce different digests; an empty dependency record is
      refused (**FR-044**)
- [x] T655 [US3] Extend `apps/analyzer/src/aoe2stats_analyzer/extract.py` to publish the next
      document version per
      [contracts/analysis-document.md](./contracts/analysis-document.md): **additive only**, every
      existing field at its existing path, four blocks added. Populate the dependency map from
      T627's record, replacing the empty literal, **and write the same record to the
      `match_analyses.engine_deps` column** — it has existed through two migrations and nothing has
      ever written it. Every published value carries its tier as data and
      the method that produced it (**FR-007**, **FR-009**), and a value at inferred or predicted
      carries a confidence and is worded so it cannot be read as a measurement (**FR-010**).
      **Declare `aoe2stats-knowledge` in `apps/analyzer/pyproject.toml`'s `[project].dependencies`
      and its `[tool.uv.sources]` in this same change** — this is the first task that imports it
      from an application, and nothing declares it today. Workspace membership is not enough: that
      file's own header records a real 500 on 2026-09-04 in exactly this shape — a package every
      local `uv sync --all-packages` installed anyway, which the deployment manifest never named,
      so the deployed function was the first thing to find out. `scripts/checks/api_entrypoint_deps.py`
      cannot catch this one: it parses only the module-scope imports of files under `api/` and this
      import is one hop further down, inside `aoe2stats_analyzer`. Declaring it on the analyzer is
      what makes the root manifest's existing `aoe2stats-analyzer` entry pull it transitively
- [x] T656 [US3] Place inferred and predicted data **structurally** under the inferred block alone,
      so a coaching conclusion cannot occupy a field typed observed, decoded or reconstructed
      (**FR-011**) by construction, with T619's validator as the second lock. Run the validator
      **before** the object is written: a failing document is not published and the analysis fails
      through 003's existing failure path. **Promote `participant.group_silence_episodes` from
      planned to published in `packages/core/src/aoe2stats_core/truth/register.toml` in this same
      change**, and regenerate the view: the validator rejects an inferred datum whose register
      status is not published, so without the move no document carrying this feature's one
      inferred datum can pass. The move belongs here and not in T633 — a status is earned by the
      change that publishes, and until this task nothing does. The `event.*` entries stay planned:
      the stream is never persisted
- [x] T657 [US6] Make the published object's key carry the identity digest, and keep
      `match_analyses.result_key` pointing at the current document (**FR-042**). Today one object
      per match is overwritten on recompute, which destroys an existing analysis — a new parser,
      patch, knowledge version or analytics version must produce a **new** analysis and rewrite
      nothing. `match_analyses` keeps its primary key: that key is 003's double-click dedupe and is
      not this feature's to change (**FR-048** — where this feature and 003 meet, 003 stands)
- [x] T657a [US6] Extend the staleness test in `apps/analyzer/src/aoe2stats_analyzer/run.py` so a
      recompute is actually triggered (**FR-042**). Today a published row is stale only when the
      parser's name or version differs, so a new knowledge or analytics version returns early and
      never recomputes — the identity-addressed key in T657 would then preserve analyses that are
      never produced. Compare the stored identity digest with the current one. This is **not** a
      change to 003's request, dedupe or lease behaviour (**FR-048**): the same branch, the same
      recompute path, a wider condition. The stored digest lives in a new nullable `identity_digest`
      column on `match_analyses`, added by T663's single additive revision
      ([data-model.md](./data-model.md) §8). A row published before this feature has none, which
      reads as stale and recomputes once — the intended outcome. The object key already carries the
      digest, and parsing it back out of a key was rejected: a storage layout is not a record
- [x] T658 [US6] Implement reproduction from a recorded identity (**FR-043**): read the retained
      recording through `packages/storage`, verify its checksum, resolve the named snapshot from
      package data, reach **no external source**, and refuse — naming what is missing — when the
      installed parser version or dependencies differ from the identity. The refusal is deliberate:
      reproducing under a different parser and calling the result the same analysis is the silent
      rewrite **FR-042** forbids, so the honest outcomes are identical, or cannot reproduce here
      because
- [x] T659 [US6] Make the compared body a pure function of the identity (**FR-041**): canonical
      serialisation with sorted keys where order carries no meaning, stream order where it does, one
      fixed float format, and the wall-clock field excluded from both the identity and the
      comparison. The legacy top-level extraction time stays at its current path for one version
      because the web reader requires it there, and it joins the excluded set
- [x] T660 [P] [US6] Write `apps/analyzer/tests/test_reproducibility.py` before T657–T659,
      `xfail(strict=True)`. **SC-004**: the same recording analysed twice with identical versions
      yields a byte-identical result **outside the wall-clock set** — the envelope and the legacy
      top-level extraction time, which T659 excludes; a whole-document comparison fails on every
      run and proves nothing — with the second run **in a fresh process** so that dictionary
      ordering or a cached clock cannot pass by accident. **SC-005**: publish, record the identity,
      promote a second snapshot, recompute, then fetch by the first identity and confirm it
      reproduces exactly and the newer snapshot was not substituted — and that the previous version
      remains available
- [x] T661 [P] [US3] Write `apps/analyzer/tests/test_document_validation.py`, `xfail(strict=True)`:
      a document whose dependency record is empty is rejected (**SC-011**); a document carrying a
      datum whose required knowledge intersects a blocking gap is rejected (**FR-037**); a document
      with no tier on a value is rejected (**SC-002**)
- [x] T662 [US5] Write the gap rows from the coverage pass in
      `apps/analyzer/src/aoe2stats_analyzer/run.py`, keyed so a reproduced analysis records nothing
      twice, and publish the gap list in the document. When no snapshot matches the recording's
      build, the knowledge block records the absence explicitly and one blocking gap says so
      (**FR-027**). **A gap whose stream named no build carries `build = -1`** — T652b's sentinel,
      recorded in [data-model.md](./data-model.md) §7, forced by a non-nullable column and a closed
      cause set. FR-039's rate query groups by build, so decide here how that row reads to an
      operator and do not let `-1` appear in the report as though it were a game build
- [x] T663 [US6] Add the single additive migration — the `analysis_knowledge_gaps` table and the
      nullable `match_analyses.identity_digest` column T657a reads — under
      `infra/migrations/versions/`, following that directory's naming convention and chaining from
      its current head, and bump the expected schema revision in `packages/storage` in the same
      commit — a test asserts the two agree. **Apply it before the deploy, and know why**: the
      runbook permits before or immediately after for a lone additive revision, but this change also
      moves the expected revision, and the smoke workflow on every push to `main` would fail against
      a database that lags the build. The cost is real and is stated: between apply and deploy the
      health endpoint answers 503, so **merge and apply in one sitting**. Follow
      `docs/runbooks/database-migrations.md` exactly — the direct, unpooled endpoint; its single
      prompted command; and unsetting the variable afterwards. `.env.local` points at production and
      no task here runs a migration from a developer machine by any other route. **In the same
      change, wire T652's gap-rate script into `.github/workflows/nightly.yml`** beside the capture
      audit, reporting and never failing on a rate: **FR-039** asks for a pattern to be _visible_,
      and a script nobody schedules is a rate nobody sees. There is no threshold yet — the first
      patch that moves the rate is what sets one, and a job that fails on an unmeasured number
      would cry wolf from its first run
- [x] T664 [P] [US3] Add a test in `apps/web/src/features/analysis/` pinning that the reader parses a
      next-version document fixture with **no source change**. The reader already requires only the
      existing fields, accepts any numeric schema version and ignores unknown keys — this test is
      what stops a later edit quietly breaking that, and it is why the extraction time is duplicated
      rather than moved. No component changes; displaying a tier or a gap needs a design-system spec
      first and is a later feature's decision
- [x] T665 [US6] Verify the phase end to end against quickstart Phase 5, including the post-deploy
      checks: the health endpoint answers **200** — read the status, not the revision field, which
      is the build's own compiled constant and is no evidence about the database — and one analysis
      requested by hand shows a populated dependency record, an identity digest and a gap list that
      is empty or explains itself. Also confirm against the live object store that a second
      conditional put to an existing analysis key is refused (T666d relies on the store honouring
      if-none-match; it is tested only against a stub). **Verified 2026-10-18** by the user against
      production; the evidence is quickstart.md's run record, "After deploy" rows
- [x] T666 [P] [US3] Add the boundary guard test asserting this feature added no scheduled job, no
      request-path work and no code path that consumes the capture budget (**FR-049**), and that
      nothing here re-specifies 003's request, fetch, parse-once, retention, recompute, isolation,
      rate-limiting or legal-basis behaviour (**FR-048**). Constitution I is the reason: an analysis
      feature may not degrade capture, and the cheapest time to assert that is while the diff is
      still in hand

### Review remediation (pull request #109, `reviewer` REJECT 2026-10-03)

The pre-merge review rejected phase 5. Both HIGH findings were re-verified against the code before
being written down. **These block #109's merge and T665.** Two were arbitration and are decided
(2026-10-03); the decision is recorded in the task that carries it. T666a and T666b touch disjoint
files and may run as one parallel batch; the rest are sequential, in order.

- [x] T666a [P] [US3] **Make the validator's two locks hold against the real register.** (a) Rule 8
      in `packages/core/src/aoe2stats_core/truth/validate.py` builds its blocked set as
      `kind.field`, but `packages/core/src/aoe2stats_core/truth/register.toml` writes
      `requires_knowledge` as bare field names (`["cost"]`) and a whole-build gap adds `None.None`,
      so the sets never intersect and **FR-037** is unenforced the day a knowledge-dependent datum
      is published. Intersect the present data with the union of each blocking gap's `prevents`
      instead, which is already computed from the real register; a whole-build gap blocks every
      datum with a non-empty `requires_knowledge`. T661's test passes only because it injects a
      synthetic register in a format the real one never uses — rewrite it on the packaged register
      with a real gap from the coverage pass, and correct the format `packages/core/tests/test_validate.py`
      documents. (b) A wildcard register path accepts any key at any depth with any value, so a
      prose verdict nested under `engine.deps` or `participants[].age_up_commands` passes as
      observed data (**FR-011**, **SC-003**). Walk the structure so a wildcard covers exactly one
      key whose value is a scalar; dependency names contain dots, so not a string-prefix rule.
      Contrast cases: a real dependency name with dots is accepted; a nested mapping or a string
      verdict under either wildcard is refused
- [x] T666b [P] [US6] **Put the recording's build on the row and take the store off the staleness
      path.** Decided 2026-10-03: amend the unapplied revision `53375d9435fc` (T663) to add a
      nullable `match_analyses.recording_build` integer beside `identity_digest`, written on publish
      from the document's knowledge record (`-1` where the stream named none, as in
      [data-model.md](./data-model.md) §7), and amend §8 to say so. The staleness test in
      `apps/analyzer/src/aoe2stats_analyzer/run.py` then computes the current digest from the row
      alone — no object-store read, so a request on a fresh published match does the row read it
      did before this feature, and a store outage cannot turn it into a 500. A row with either column
      NULL reads as stale and recomputes once. **Errors computing the current digest propagate before
      any recompute** — a broken snapshot, a digest mismatch or an empty dependency record is a
      deployment fault, not staleness, and today `SnapshotError` (a `ValueError`) is swallowed as
      "stale" and costs a retained-recording read and a full parse on every click. Test it at that
      shape: a raising knowledge resolution leaves the extractor uncalled, no access-log row and the
      row unchanged. Bump nothing: the revision id stays
- [x] T666c [US6] **A failed recompute keeps the analysis it was replacing.** Decided 2026-10-03:
      **FR-042** wins over the literal reading of **FR-048** here, because 003's failure path was
      written for a first analysis and recomputes of this kind did not exist. On the recompute path
      only, a refused document, a placement error or a parse failure is logged and the row stays
      published on its previous key, digest and build; nothing is unpublished. A first analysis
      still fails through 003's path unchanged. In the same change, route the exception sources
      this phase added to the first-analysis path — knowledge loading, the canonical serialiser's
      refusal, a gap-row insert — through that failure path, so none leaves the row running for the
      lease to expire and the next request to fetch again. Contrast cases: a first analysis that
      fails still ends failed; a recompute that fails leaves the prior document served
- [x] T666d [US6] **Never write a published key twice.** contracts/analysis-document.md says a key,
      once written, is never written again; two concurrent stale requests (the recompute path holds
      no lease) or a budget expiring between the write and the publish still re-put the same key with
      a new wall clock. Add a conditional create to `packages/storage` — if-none-match on the object
      stores that support it, in both the production store and the test fakes — and when the key
      already exists, point the row at it without writing. Correct the two tests in
      `apps/analyzer/tests/test_run_once.py` that assert the overwrite as the desired outcome
- [x] T666e [US6] **Put the key layout where the contract says it lives, and close reproduction's
      gaps.** contracts/analysis-document.md names `packages/storage` as the owner of the key layout
      and a read-by-identity function; [plan.md](./plan.md) says `run.py` — the contract stands, and
      plan.md is amended to match. Move the layout out of `run.py`'s private helper and add the read.
      Stop the document builder importing storage repository types: the conversion to rows belongs
      on the run side. Replace `extract.py`'s re-implementation of the validator's leaf walk and
      exemption set with the validator's own, so the two cannot drift. In
      `apps/analyzer/src/aoe2stats_analyzer/reproduce.py`: cross-check a caller-supplied match id
      against the retained key, report a refused document as a refusal rather than a third outcome,
      and treat only the store's own not-found signal as a missing object
- [x] T666f **Small follow-ups from the same review.** Make the knowledge-refresh staleness test in
      `apps/analyzer/tests/test_run_once.py` promote a real second snapshot, as the reproducibility
      test does, instead of patching one resolver so the identity and the gaps disagree. Mark the
      gap-rate step in `.github/workflows/nightly.yml` continue-on-error, so a failing report cannot
      turn the capture audit red — constitution I outranks a report. Correct the stale docstring in
      `run.py` that still names the timeline extractor. The T664 fixture stays hand-written: it pins
      the reader against the contract, and generating it from the builder would pin the reader
      against whatever the builder happens to emit

### Review remediation, second round (pull request #109, `reviewer` REJECT 2026-10-04)

The re-review confirmed T666a–T666f hold against the defects they targeted and rejected on their
siblings. H-1 and M-1 were re-verified against the code before being written down. Two were
arbitration and are decided (2026-10-04); the decision is recorded in the task that carries it.
**These block #109's merge and T665.** T666g, T666k and T666l touch disjoint files and may run as one
parallel batch; T666h, T666i and T666j follow, in order — all three edit `run.py`.

- [x] T666g [P] [US6] **Let the product reach the recompute T657a made possible.** The API's `stale`
      flag in `apps/api/src/aoe2stats_api/routers/matches.py` still compares the parser version
      alone, and the web reader offers Recompute only when it is true, so a knowledge refresh or an
      analytics change never triggers anything outside a test (contracts/analysis-document.md: "a
      recompute has to be triggered"). Decided 2026-10-04: the API compares the identity digest,
      computed by **the same function** the analyzer's staleness test uses — one function, so the
      button and the recompute cannot disagree — from the row, the retained-recording row and the
      installed versions, with no object-store read and no parse. This needs the knowledge identity
      on the API's request path: amend `tests/architecture/test_feature_006_boundaries.py` to allow
      exactly that import and no other, and record in the test why it stays inside **FR-049** — a
      cached, build-independent resolution, not request-path work. While a kept-prior failure's
      retry window (T666c) is open the flag is false, so the button is not offered for a click that
      would do nothing. Contrast cases: parser change, knowledge refresh and analytics change each
      read stale; an identical identity does not; a row in its retry window does not; a row with no
      digest or no build does
- [x] T666h [US6] **Refuse a broken deployment before claiming anything.** Decided 2026-10-04,
      replacing T666c's handling of the case: a first analysis whose snapshot load fails today
      fetches from the source, retains, parses and then ends terminally failed, so a broken knowledge
      deploy spends capture's budget (constitution I) and leaves every match requested meanwhile
      permanently failed. Before `claim_for_analysis` in `apps/analyzer/src/aoe2stats_analyzer/run.py`,
      check what is independent of any recording and already cached: every installed snapshot loads
      and passes its digest check, no two promoted snapshots describe one build, and the extractor's
      dependency record is non-empty. A failure raises before any row is written or any byte fetched,
      and the next request after the fix proceeds normally. A snapshot fault that still surfaces after
      the check — one only a particular build can reach — keeps T666c's routing. The remaining shape
      the review named — a refused document caused by a code defect, which cannot be checked in
      advance — stays on 003's failure path, and this task says so in the code
- [x] T666i [US6] **Close the recompute path's two remaining unpublish and retry holes.** (a) A
      published row whose retained-recording row is gone reads as stale, recomputes and is marked
      unavailable, which unpublishes a served analysis (**FR-042**) — latent until 003's retention half
      lands. A recording that cannot be recomputed is not stale: serve the prior analysis and never
      unpublish it. (b) A retained object that fails its integrity check, or is missing from the
      store, on the recompute path propagates with no backoff, costing a full read and a 500 on every
      click; route the integrity failure through the keep-prior path with its retry window, and write
      the access-log row for every read of retained bytes before the integrity verdict, as **FR-029**
      requires. (c) `_publish` attributes a failure of the row update's flush to the gap rows; name
      the step that actually failed
- [x] T666j [US6] **Source the recompute retry window from configuration.** The window is a code
      default that the deployed entrypoint never threads, while the docstring says it is configured
      like the capture budget. Read it from the API's settings and pass it through the analyze
      entrypoint, with the variable declared wherever this repository declares environment keys
      (constitution XII), or correct the docstring if configuration is rejected — say which. The key
      is `ANALYSIS_RECOMPUTE_RETRY_SECONDS`, required like `CAPTURE_BUDGET_DAYS`, so the deployment
      environment must carry it before the merge that introduces it
- [x] T666k [P] [US3] **Two second locks that still lean on the first.** (a) Rule 8 in
      `packages/core/src/aoe2stats_core/truth/validate.py` reads each gap's `severity` and `prevents`
      from the document, so a gap the builder mislabels informational, or emits with an empty
      `prevents`, blocks nothing. Also block any present datum whose register `requires_knowledge`
      names the gap's field, whatever the gap says it prevents. (b)
      `apps/analyzer/src/aoe2stats_analyzer/reproduce.py` maps only `DocumentInvalid` to a refusal; a
      placement error and the canonical serialiser's refusal still escape as a third outcome
- [x] T666l [P] **Bring the written record level with the amended revision.** `plan.md`'s Storage and
      Summary paragraphs still describe one nullable column; name both. Correct the comment in
      `packages/storage/src/aoe2stats_storage/revision.py` and the `match_analyses` docstring in
      `packages/storage/src/aoe2stats_storage/models.py` to name `recording_build`. Record in
      [data-model.md](./data-model.md) §8 the meaning T666c gave the lease column on a published row
      — a retry window, not a claim — which the re-review made the condition of accepting it. Raise
      `packages/storage`'s boto3 floor to the first release whose object put accepts the if-none-match
      condition, which `put_if_absent` needs

- [x] T666m [US6] **Third review round (2026-10-04): one deployment-fault classification, and the
      last twins.** (a) The API's staleness read in
      `apps/api/src/aoe2stats_api/routers/matches.py` treats a deployment fault as not stale but
      catches only two exception classes, while the snapshot loader also raises an `OSError` for a
      missing packaged file — which `verify_deployment` already names — so a snapshot shipped
      without its rules file makes the match-detail page answer 500 for every analysed match
      (**FR-048**). Define the deployment-fault exception set once, beside `verify_deployment`, and
      use it in both places; test the match page with a snapshot file removed (200, not stale) and
      with a digest mismatch. (b) The same faults on the analyze endpoint's published path escape as
      a bare 500 the web client cannot parse: map them to the deployment fault inside the analyzer's
      staleness call. (c) The analyze endpoint builds its response without the retained-recording row,
      so its stale flag is false by construction; make that argument required and pass it. (d) Give
      003's failure writer the same refusal to touch a published row that T666i gave the unavailable
      writer — a lease overrun lets a second claimant refuse after the first published. (e) Record in
      `apps/analyzer/src/aoe2stats_analyzer/reproduce.py` that it reads retained bytes without logging
      and that any production caller must write the access-log row (003's **FR-029**); it has no
      caller today. The analysis rate-limit charge on a deployment-fault 500 stays as 003 charges
      every other early refusal

- [x] T666n [US6] **The closing review's four follow-ups (PASS on T666m, 2026-10-04).** (a) The
      keep-prior path's would-be digest in `apps/analyzer/src/aoe2stats_analyzer/run.py` still catches
      only a value error, so the empty-dependency and missing-file faults T666m reclassified would
      escape its warning after the row has committed; catch the deployment-fault set too. (b) 003's
      failure and unavailable writers read the row, check it is not published, then write, with no
      lock: a publish between the read and the commit is still unpublished. Make each write
      conditional on the row not being published, in the statement itself. (c) The match page's lazy
      import of the staleness module sits outside the handler that promises never to fail the page;
      move it inside. (d) The snapshot loader in
      `packages/knowledge/src/aoe2stats_knowledge/snapshot.py` decodes its descriptor before any
      check, so invalid UTF-8 surfaces as a bare decode error rather than a snapshot fault; wrap it

**Checkpoint**: every value carries its tier, every analysis carries its identity, and no version
destroys its predecessor.

---

## Phase 6: Closing (plan phase 6)

**Purpose**: the living documents that can only be written once the rest is true, the end-to-end
quickstart run, and the lint. `/speckit-implement` stops here when T670 exits 0.

- [x] T667 [P] Update `docs/risks.md`: correct R3's fallback list, which names the fast alternative
      parser as a fallback although [research.md](./research.md) **D1** measured that it cannot open
      the current build; and add a row for the dependency class this feature creates —
      community-maintained knowledge sources that may stop, one of which already has, plus the
      standing hand-transcription of civilisation bonuses and patch notes. Widen R7's mitigation,
      which names `packages/game-assets/` as the only root carrying a `LICENCE.md` and checked by
      `scripts/checks/asset_packs.py` — T637 added two, and `docs/` must be true today. Add the
      verification-checklist line for T603's assertion under parsing. Tick no existing checklist
      item
- [x] T668 [P] Record the starting-state finding in `docs/data-sources.md` §2, which is where a
      measured property of the outside world lives — not in the risk register: the initial-state
      section is present in the header, per-player starting attributes are reachable at a
      self-verifying anchor, and the object table sits behind a per-patch grammar. A living fact in
      `docs/` is trustworthy only because a test asserts it, so add a fixture test that finds the
      attribute anchor in every committed recording. This retires the claim that the section is
      unreadable **without** promising the decoder, which is 007's. [research.md](./research.md)
      **D1** then becomes the historical record and stops being the home
- [x] T669 [P] Run the full quickstart end to end on a clean checkout and record any step whose
      stated expectation did not match what happened. A quickstart nobody has executed is a
      hypothesis. **Recorded 2026-10-17** in [quickstart.md](./quickstart.md), "Run record (T669,
      2026-10-17)": three steps did not match and are corrected in place; the post-deploy read of
      one published analysis needs a signed-in session and was not run
- [x] T670 Run `uv run scripts/checks/spec_lint.py --feature specs/006-replay-analysis-foundations`
      and confirm it exits 0 — every requirement named by a task, every task reference defined,
      every path under a declared root. Then run the whole suite by exit code, not by reading the
      summary line

---

## Phase 7: Game build 185872 (filed 2026-10-05, production incident)

**Purpose**: `POST /api/analyze` answered 500 for match 511523321. The pinned `aoe2rec-py` 0.1.21
panics on fourteen of fifteen recordings sampled between 2026-09-27 and 2026-10-05 from two
profiles (match 511523321 is game build 185872), and that panic is a `BaseException` the analysis path never
contains: the request fails, the claimed row stays `running`, and once its lease lapses the next
request fetches the recording from the source again. `aoe2rec-py` 0.1.22 (2026-09-22) to 0.1.24
parse match 511523321 but changed the shape of what they return. Capture is not losing bytes: the blob
is committed before validation, so the same recordings end `quarantined` with their object kept.
T671 and T672 ship together; T673 follows once T672 is deployed. **Amended 2026-10-11:** that the
same recordings end `quarantined` was read from the code and never observed; `docs/risks.md`
carries what T673's dry run read.

- [x] T671 Contain a native engine panic on the analysis path, as `apps/ingester/src/
      aoe2stats_ingester/capture.py`'s `_validate_with_barrier` does on the capture path. A
      `BaseException` raised while the extractor builds the document ends a first analysis `failed`
      with its class and message recorded, and keeps the prior analysis on a recompute, through the
      existing `_refuse`; `asyncio.CancelledError`, `KeyboardInterrupt` and `SystemExit` still
      propagate. Test first against a stand-in `BaseException` subclass, as `apps/ingester/tests/
      test_quarantine.py` does, and show the test failing on the current tree: the request must
      not raise, the row must not stay `running`, and the source must be fetched once
- [x] T672 Upgrade `aoe2rec-py` to 0.1.24 and adapt `packages/replay-engine/`: the parse result is
      now a list of chapters, each carrying `zheader` and `operations`, and the former `meta` block
      is the first operation, of kind `Pregame`. Read the single chapter, take the recording owner
      from `Pregame`, and treat `Pregame` as a known kind in the canonical stream rather than an
      unknown one; refuse a recording with more than one chapter with `EngineParseError` rather
      than guessing how chapters join. Commit match 511523321's recording (build 185872) as a third
      fixture in `tests/fixtures/replays/` under that README's rules, and test that it extracts.
      The two committed build 180059 fixtures must yield byte-identical golden timelines and
      canonical streams; regenerate a golden only if it does not, and explain every diff. The
      engine version enters the identity digest, so published analyses recompute: say so in the
      commit body. Update every living statement of the pinned version in `docs/` and the
      replay-parsing skill; leave frozen `specs/` records alone
- [x] T672a Close #124's review (`reviewer` REJECT 2026-10-06). **Point of view:** the adapter
      takes the recorder from `rec_owner` as an index into `game_settings.players`, and that index
      is 1 in all three committed recordings: it named the recorder in the two build 180059
      fixtures by coincidence and names the wrong player in match 511523321's. Take it from
      `zheader.replay.rec_player`, a player number, matched against each player's
      `player_number`, which names the downloaded profile in all three; refuse a recording where no
      player carries it. Assert the downloaded profile (5632575) for the new fixture, keep the two
      older goldens unchanged, drop the refusals keyed on `rec_owner`, and correct the fixtures
      README, the replay-parsing skill and the canonical stream's comment. **Pregame:** refuse a
      chapter with more than one `Pregame`, and a `Pregame` anywhere but first, in both the adapter
      and the canonical stream. **Panic message:** a `BaseException` that is not an `Exception`
      is recorded as its class and a fixed sentence and its full text is logged, never shown:
      the measured `PanicException` text carries terminal escape codes, a backtrace and crate
      paths. Test with that measured text. Say in `_extract_and_publish`'s docstring that any
      exception in the barrier now ends a first analysis `failed`, where it used to propagate and
      be claimed again. **Docs:** `docs/risks.md` says only what is measured: new captures and
      analyses read build 185872, the quarantined backlog waits on T673 and is not counted; it
      does not restate the sample count kept in this phase's purpose
- [x] T674 Find the published analyses whose point of view was taken from the wrong player
      (T672a): every `match_analyses` row whose `point_of_view_profile_id` has no
      `retained_recordings` row for its match. Such a row cannot be recomputed, and its
      perspective is wrong. Count them first and report; correcting them is a separate decision.
      Reads production, so the user runs it or grants the read. **Counted 2026-10-18** by the user
      against production: one row matches, in state `unavailable`, and no `published` row does.
      An `unavailable` analysis never obtained its recording (003's data model), so nothing was
      published from it: the predicate matches it by its state, not by a wrong perspective. No
      published analysis needs correcting, and the correction decision does not arise
- [x] T672b Close #124's second review (`reviewer` REJECT 2026-10-06 on T672a; code findings
      closed, prose overclaims left). Cut to what was measured: `docs/risks.md`'s entry names the
      one recording measured as build 185872 and states capture quarantine as what the code
      implies, uncounted until T673; `_describe`'s docstring no longer says every recorded message
      is this package's own text (an `EngineParseError` quotes the engine's); the replay-parsing
      skill and the adapter's and canonical stream's comments cite the fixtures README for
      `rec_owner` instead of restating its measurement. Third review: `_describe` names no class as
      the only one quoting foreign text, and ADR 0001's amendment names the one recording measured
- [x] T673 Re-validate captures that ended `quarantined` because the engine could not parse them,
      once T672 is deployed: read the committed object, check it against the row's own `zip_sha256`,
      and run it through the capture barrier again, marking `stored` or leaving it `quarantined`
      with the new error. Never re-download, never modify or delete an object. Bound the selection
      to the engine's own failure text so an integrity quarantine (missing object, checksum
      mismatch) is never reopened. Urgent: 31 days after a recording, an analysis of its match has
      no source to fall back on. The earliest affected recording is not measured; the earliest
      sampled is from 2026-09-27, and 0.1.22 shipped on 2026-09-22. **Decided by the user
      2026-10-11:** a capture whose profile has no active link stays outside the selection, as T673b
      left it; re-validated rows may turn the nightly capture audit's lag assertion red, and that is
      ruled on for good once the dry run reports how many rows it would write; timeout quarantines
      stay outside the selection until the dry run reports their count. **Closed 2026-10-11 on the
      operator's dry run against production,** whose reading `docs/risks.md` carries; no real run
      followed and no capture was re-validated. Neither question left to the dry run's count had
      anything to rule on; both stay in `docs/runbooks/revalidate-quarantined.md`
- [x] T673a Close #129's review (`reviewer` REJECT 2026-10-10 on T673). The command is written and
      no capture has been re-validated, so T673 stays open until the operator run reports its count.
      **Eviction:** a re-validation that fails for a reason that is not the engine's verdict (the
      wall-clock cap, any class outside the selection) overwrites `last_error` with a text the
      selection no longer matches, and the row is never offered again. Write a new reason only when
      the selection would still match it; otherwise leave the row untouched and report the reason.
      Red first: a row whose validation times out once is selected again on the next run; contrast,
      a row that fails with a new engine error is rewritten. **Objection:** the selection
      re-validates a capture whose user has objected to archival since (constitution IX; 001's spec
      says a quarantined capture is not archived, so its carve-out for recordings already archived
      does not cover it). Apply the claim's own objection predicate, shared rather than copied, and
      test both sides: an objecting user's row is not selected, a non-objecting profile's row on the
      same match is. **Guard:** test the quarantine write's status guard with a failing validation
      while another writer stores the row; the existing test exercises the stored write only, and a
      mutation dropping the other guard passed every test. **Integrity versus transport:** only a
      missing object and a checksum mismatch are per-row outcomes; any other store error aborts the
      run non-zero with no write, and the store is configured through the application's own settings
      validation, not from raw environment values. An integrity failure found here ends the run
      non-zero after the report. **The dry run counts what it does not select:** `quarantined` rows
      outside the selection, grouped by reason class (the text before the first colon, the reclaim
      texts, the cap), counts only, no values. **Tests:** the command test named for a dry run
      asserts one; the cursor test asserts each field; one test drives the entry point through a
      successful dry run and a real run. **Prose, cut to what is measured:** one recording is
      measured as build 185872; "a row that fails again is still a candidate" and "idempotent" are
      claimed only as far as the eviction fix makes them true; the retention window is cited from
      `docs/data-sources.md`, never restated; oldest-first is an ordering and is not justified by
      the analysis path, which reads `retained_recordings` and the source and never a capture's
      object; "exactly as a normal capture" says that `stored_at` is the time of re-validation.
      Correct `apps/api/src/aoe2stats_api/ingest_stages.py`'s claim to be the one place a drain is
      built, and `packages/storage/src/aoe2stats_storage/models.py`'s comment that `last_error` is
      never control flow. **Runbook:** `docs/runbooks/` gains the operator procedure, with secrets
      read as `docs/runbooks/alert-acknowledgement.md` reads them, never inline on a command line.
      Left to the user, not decided here: whether re-validated rows may turn the nightly capture
      audit red (`scripts/checks/capture_audit.py` measures `stored_at` against the recording), and
      whether timeout quarantines are reopened (001's plan calls the cap an engine failure), which
      waits on the dry run's count
- [x] T673b Close #129's second review (`reviewer` REJECT 2026-10-10 on T673a; eviction, the
      quarantine guard, integrity versus transport and the two corrected claims are closed).
      **Objection at write time:** the objection is read once, when the page is selected, and both
      guarded writes filter on status alone, so a user who objects while a page is being validated
      still has their row marked `stored`. Put the ownership predicate in both guarded writes' own
      `WHERE` and report a row it refuses as an unwritten outcome of its own. Red first: a validator
      that records the objection mid-validation, once for a validation that succeeds and once for
      one that fails with an engine verdict; contrast, a non-objecting row of the same page is
      written. **An objector who has left:** the claim's predicate matches an active link only, so a
      capture whose objecting user has since unlinked the profile is selected, and the test that
      pins it speaks of a new owner while seeding none. Until the user rules on it, a capture is
      taken only when its profile has an active link whose user has not objected, at selection and
      again at write; a profile with no active link is not selected, and the dry run counts it under
      its own label. Not selecting loses nothing: the row and its object stay as they are. The claim
      path's own predicate is not changed here. Tests: an objector who unlinked is not selected; a
      profile relinked by a second user who has not objected is; a profile with no link is not, and
      is counted. **Partial report:** a database error on one row's write discards the report of the
      rows already written, which are no longer selected, so their count cannot be recovered. Stop
      at that row, return the report so far named as the store stop is, and exit non-zero; test with
      a write that fails on the Nth row. **Reason labels:** `_reason_class` returns any
      identifier-shaped head as its label. Make the label a closed vocabulary (a name ending in
      `Error` or `Exception`, the fixed labels, else `other`) and test a head that is an identifier
      and not a class name. **Tests:** the assertion that a stopped run prints no continuation runs
      on a truncated report with a cursor; the selection's checksum clause gets a row of its own,
      object key set and checksum null; the two command tests that expect a refused environment
      clear the ambient process environment first, and `settings_from_environment`'s docstring says
      the process environment is read as well as the mapping. **Prose, exact shapes only:** every
      sentence saying the command never selects or reopens an objector's capture says what the
      predicate checks and when it checks it; `_objecting_owner_exists` is not called the one
      definition of objecting while `archiving_links` in
      `apps/ingester/src/aoe2stats_ingester/discover.py` holds another; the script's docstring does
      not assert that a quarantined capture exists for the measured recording, which `docs/risks.md`
      gives as what the code implies; the ingester test module's docstring names one recording,
      drops "idempotence" and qualifies "exactly as the normal path" with `stored_at`; a dry run
      reads the database, reads no object and writes nothing. **Runbook:** the cron secret is
      length-checked, not checked for presence only; a bare re-run also offers `still_quarantined`
      rows again; a run exits non-zero for an integrity failure only when its page includes that
      row; the closing `unset` is a fenced block on one line and names the variable that held the
      pasted database URL; when every row is an integrity failure, check the bucket name first. Left
      to the user, not decided here: whether a capture whose profile has no active link, or whose
      objecting user has left, is ever re-validated; and the same gap in the claim path for a
      `pending` row, which predates this branch
- [x] T673c Close #129's third review (`reviewer` REJECT 2026-10-11 on T673b; no wrong write and no
      constitution finding. Verified and not to be re-checked: the ownership predicate at selection
      and in both writes, the refused-write outcome, the cursor on a stopped run, the schema's one
      active link per profile, and T713's premises). **The stop report says "written" for rows it
      only examined:** on a database stop `scripts/ops/revalidate_quarantined.py` prints that the
      rows listed above were written, and the report lists every row examined before the failure,
      whatever its outcome. Say "examined". Say that only a `stored` row leaves the selection
      wherever the opposite is written: `write_failed_by`'s comment, `revalidate_quarantined`'s
      docstring and the comment in its loop in `apps/ingester/src/aoe2stats_ingester/capture.py`,
      the script's docstring, `docs/runbooks/revalidate-quarantined.md`, and the docstrings of the
      two tests that fail a write. Drop "with that row unwritten" from the script: a commit that
      raises leaves the row's state unknown, and both tests replace the whole method, so they assert
      nothing about it. Give the runbook the step for a database stop that the store stop already
      has: re-run, the failing row is offered again if it is still `quarantined`, and the reported
      count may be short by that one row. Cut sentences; add no claim about the failing row's state.
      **An interrupted page:** only a store error and a database error keep the report, and an
      interrupt in the middle of a page prints nothing. Narrow every sentence about the partial
      report to those two cases, and have the runbook say an interrupted page loses its report. Do
      not catch a cancellation and do not widen the handler around the write. Left to the user, not
      decided here: printing each row as it is decided, so an interrupt keeps the rows already
      examined. **Object key clause:** the selection's `object_key` clause has no row of its own,
      the twin of T673b's checksum row, and removing the clause passes every test. Add a row with
      the object key null and the checksum set, not selected, beside a contrast row that is
      selected; `_seed` cannot build one today. Red against the clause removed, with the output in
      the hand-back. Do not change the predicate. **Ambient environment, a third test:**
      `test_a_missing_application_key_is_named_and_no_value_is_printed` in
      `scripts/ops/tests/test_revalidate_quarantined_command.py` reads the process environment and
      fails in a shell that exports the bucket key, which the runbook's first step does. Give it the
      fixture the two entry-point tests received, then check every other test in that module that
      expects a refused or missing key. Do not weaken the assertion. **Stale claim:**
      `_claim_batch`'s docstring says its predicate is shared with the re-validation's selection,
      which T673b ended; it is shared with the dry run's labelling only. **Reason labels:** the
      pattern `_reason_class` matches a head against admits dots, which no writer emits (the barrier
      writes a bare class name), so a dotted free-text head ending in `Error` is a label. Remove the
      dot, change the test that pins a dotted head to expect `other`, and reword the docstring to
      what holds: a label is a fixed label, an identifier ending in `Error` or `Exception`, or
      `other`. It does not say free text can never become a label. **"Never a whole reason":**
      `_count_unselected` reads the head of each reason up to a fixed length, which is the whole
      reason when it is short; say so in both places that claim otherwise. **Runbook, a hung
      engine:** after a wall-clock cap outcome the command prints its report and does not exit until
      the abandoned validation thread ends; one sentence
- [x] T673d Close #129's fourth review (`reviewer` REJECT 2026-10-11 on T673c; no wrong write, no
      data-safety and no constitution finding, and nothing on the dry-run path. Verified by mutation
      and not to be re-checked: every selection clause removed alone, all four branches of the text
      clause and of its Python twin, the status and ownership guards of both writes, the
      missing-object versus transport split, both loop handlers, the cursor, the exit code's three
      terms, and each sentence of T673c). **Evidence cut off:** `_one_line` in
      `scripts/ops/revalidate_quarantined.py` cuts every reason at a fixed width, so a checksum
      mismatch on an ordinary object key prints the checksum the row records and loses the one the
      store holds. `integrity_failure` and `inconclusive` write nothing, so their reason exists
      nowhere else. Print the reason whole for those two outcomes, still flattened to one ASCII
      line; keep the cut for `still_quarantined`. One test: a mismatch line for a key of realistic
      length carries both checksums. Contrast: a `still_quarantined` reason longer than the width is
      still cut. Red against the cut applied to every outcome. **Reclaim's words on a row no reclaim
      touched:** this command reports an `integrity_failure` with the texts the reclaim path stores
      (`reclaim could not read back`, `reclaim checksum mismatch`), which the runbook and the script
      say are never selected. Give `integrity_failure` a reason of its own that names the key and,
      on a mismatch, both checksums; it is printed and never stored. Leave the reclaim path, its
      stored texts and the constants `_reason_class` matches as they are. One test per integrity
      outcome: the reason starts with neither reclaim text. **The trailing boundary of the text
      clause:** only a leading lookalike has a row. Dropping the colon and space, or the space
      alone, from the prefix match in `_engine_failure_reason`, or matching the bare class name in
      `_is_engine_failure_reason`, passes every test in
      `apps/ingester/tests/test_revalidate_quarantined.py`. Add three never-selected rows: a longer
      class name with a colon (`PanicExceptionGroup: z`), a longer bare name (`EngineParseErrorX`),
      and the class with a colon and no space. Add one validator raising a class named
      `EngineParseErrorX`, which must end `inconclusive` with nothing written. Red against each of
      the three mutations, with the output in the hand-back. Do not change either predicate. **A
      stop does not name its row:** both stop lines say a row stopped the run and neither says
      which, selection is oldest first, and a row that fails the same way on every run keeps every
      later row out of reach. Carry the stopped row on the report and have each stop line print its
      game, its profile, its recording time and the `--after` value that starts past it. The runbook
      gains one sentence under each stop: if the same row stops two runs, pass that value and report
      the row. Two tests, one per stop: the line names the row, and a run given that value does not
      select the row and selects the one behind it. Contrast: a run that does not stop prints no
      such line. Catch nothing new and do not widen either handler. **Sentences wider than the
      code:** `inconclusive` is "selected again on the next run" in the runbook's table and in the
      script's docstring, which does not hold for a run given the printed `--after`, nor after the
      owner objects or unlinks; say the row stays in the selection. The runbook says a wrong bucket
      answers "no such object" for every key: read
      `packages/storage/src/aoe2stats_storage/objects.py` and narrow the sentence to the case that
      holds, a bucket that exists and that the token can read, and say that any other wrong bucket
      stops the run. The script's docstring says the report prints the `--after` value "when more
      remain"; say what a stopped run prints. `_reason_class`'s docstring counts three shapes of
      label and returns a fourth, the engine class with its reason in brackets. A dry run's summary
      line says rows were "examined" where it read no object; say "selected". **Three docstring
      claims with no row:** "tested in that order" in `_reason_class`, where swapping either
      adjacent pair of the three checks passes: add an engine row that is both objecting and without
      an object, labelled `(archival objected)`, and one both without an object and without an
      active link, labelled `(no committed object)`. "Matched at both ends" for the wall-clock cap:
      add a reason that starts with the cap's opening words and does not end with its closing words,
      counted as `other`. "A longer one is cut here" for the head `_count_unselected` reads: add a
      reason whose first colon lies past the head length behind an identifier ending in `Error`,
      counted as `other`. Red against each mutation, with the output in the hand-back. **Left as
      they are:** the names `write_failed_by` and `ownership_changed`, whose comments and runbook
      rows already say what was observed; a head such as `EngineParseError:x`, which no writer
      emits, counted under the bare class; and every store service error printing as one class name.
- [x] T673e Close #129's fifth review (`reviewer` REJECT 2026-10-11 on T673d; no wrong write, no
      data-safety and no constitution finding; sentences, comments and tests only, and no statement
      of `apps/ingester/src/aoe2stats_ingester/capture.py` or of
      `scripts/ops/revalidate_quarantined.py` changes outside a comment, a docstring or the
      `--limit` help text. Verified and not to be re-checked: both stop tests run the real command
      with the value read from the printed stop line, no path carries an integrity reason of this
      command to `last_error`, the reclaim path's two stored texts are character-identical to the
      main branch's, and a `still_quarantined` reason is written uncut). **A rule that misfires on
      its own paragraph's causes:** under each stop `docs/runbooks/revalidate-quarantined.md` says
      "If the same row stops two runs, pass that value and report the row", the sentence T673d
      prescribed. The store stop's listed causes (an outage, a denied request, a missing bucket) are
      not about the row and stop whichever row comes first, so an operator following the rule passes
      over one sound row per two runs and re-validates nothing; a database that refuses writes does
      the same. Replace the sentence in both paragraphs with what holds: passing that value starts
      the next run past the row; a store failure that is not about the row, or a database that
      refuses every write, is not passed by any `--after` value, because the next run stops again,
      at its first row for the store and at the first row it writes for the database, and the thing
      to fix is then the store (token, bucket, endpoint) or the database, followed by a re-run
      without `--after`. No advice to report a row, and nothing about what state the stopped row is
      in. **A test that asserts the opposite of what ships:**
      `test_a_stopped_run_names_the_error_class_prints_no_continuation_and_exits_non_zero` in
      `scripts/ops/tests/test_revalidate_quarantined_command.py` builds a stopped report with no
      stopped row, a shape the drain no longer returns, and asserts no line carries `--after`; its
      docstring says a stopped report prints no continuation because the operator has to deal with
      the stop first. Give its report a stopped row, assert that the "more candidates remain" line
      is absent, and reword the docstring to that. **A comment against its neighbours:**
      `stopped_row`'s comment says the report claims nothing about that row's state, while
      `aborted_by`'s comment and the store stop line say it was not written. Say the field claims
      nothing about its state. **Wrong bucket, the residue:** "Any other wrong bucket stops the run"
      is wider than `packages/storage/src/aoe2stats_storage/objects.py`, which also reads two
      generic not-found codes as a missing object. Say that a wrong bucket the store answers with a
      missing-bucket error or a denial stops the run, and that the other bucket answers "no such
      object" for every key it does not hold. **A test named for more than it asserts:**
      `test_the_reclaim_path_still_stores_its_own_integrity_texts` in
      `apps/ingester/tests/test_revalidate_quarantined.py` checks what the read-back helper returns
      by default, and stores nothing. Rename it and reword its docstring to that. A reclaim driven
      into a missing or drifted object has no test anywhere in the repository; that is older than
      this feature and is not closed here. **A shared recording time:** neither stop test seeds a
      second capture of the stopped match, so "selects the one behind it" is run only where the row
      behind has a later time. In one of the two, seed a second capture of the stopped match and
      assert the run given the printed value selects it. Red against a stopped row's cursor that
      keeps the time and takes the highest capture id, with the output in the hand-back.
      **"Examined" where a dry run read nothing:** the script's docstring and `--limit` help, the
      runbook's "One line per row examined" above a table that lists `selected`, and the two cursor
      comments on the report in `capture.py`. Reword each to hold for both kinds of run.
      `_WHOLE_REASON_OUTCOMES`'s comment also describes the two refused-write outcomes, whose
      reasons are short fixed texts; say the two it names carry what this run found.
      `revalidate_quarantined`'s docstring says an integrity reason "is printed"; the method prints
      nothing, so say it is reported and never stored. **Left as they are:**
      `only_integrity_is_per_row` choosing wording as well as control flow, and the empty branch of
      `_stopped_row_text`.
- [x] T673f Follow-ups from #129's sixth review (`reviewer` APPROVE 2026-10-11, on T673e's delta
      alone; none blocks the merge or the operator's run). Sentences and one assertion, no
      executable statement. **Re-running after a stop:** under both stops
      `docs/runbooks/revalidate-quarantined.md` says the fix is "followed by a re-run without
      `--after`". That is safe, and on any page after the first it starts again from the oldest row
      and re-validates every earlier row that did not end `stored`. Say to re-run the command that
      stopped, with the `--after` it was given if it was given one, and not the stop line's value.
      "The next run stops again" holds while the failure lasts; say so. **Three more places that say
      "printed":** the docstrings of the two helpers that build an `integrity_failure` reason in
      `apps/ingester/src/aoe2stats_ingester/capture.py`, and a comment in
      `apps/ingester/tests/test_revalidate_quarantined.py` above the read-back helper's test;
      nothing there prints. Say "reported". **A clause the stopped-run test does not assert:** its
      docstring in `scripts/ops/tests/test_revalidate_quarantined_command.py` says the stop line
      carries the `--after` value, and the test stays green with that text removed from both stop
      lines. Assert it there or cut the clause. **Two wordings:** `_WHOLE_REASON_OUTCOMES`'s comment
      reads as if only its two outcomes carried what the run found, where a `still_quarantined`
      reason does too; the distinction is that these two write nothing. The runbook says a database
      "refuses every write" nine lines after "a write was refused" in the other sense, a guard that
      matched no row; say "fails every write".
- [x] T673g Follow-ups from #132's review (`reviewer` APPROVE 2026-10-11 on T673f; none blocks the
      merge; the user chose the same day to close them in #132). Sentences only: no executable
      statement, no test. **Which command to re-run:** T673f's wording, "a re-run of the command
      that stopped", has two candidates once a second run has stopped. `after` is an exclusive
      comparison on a row's recording time and capture id, so the stop line's value excludes the
      stopped row. A run stopped at row A by a failure that is not about the row, re-run with that
      value, stops at its first row B; read at that second stop, the sentence yields the value
      that excludes A. Under both stops in `docs/runbooks/revalidate-quarantined.md`, name the
      command by what distinguishes it: the first command that failure stopped, with the `--after`
      that command was given, if any. **What that re-run repeats:** it starts where the stopped
      command started, so a row before the stop that is still selected is examined and listed
      again, and totals summed over both runs count it twice. Say so under both stops; read the
      selection for which outcomes leave it before naming the rows. **Four of a real run's
      outcomes write nothing; `selected`, the dry run's outcome, writes nothing either (amended
      2026-10-11 by T673h; the count of four was a real run's):** `_WHOLE_REASON_OUTCOMES`'s comment
      in `scripts/ops/revalidate_quarantined.py` opens "The two outcomes that write nothing", and
      `changed_elsewhere` and `ownership_changed` write nothing either. Its two are the ones that write nothing and whose reason carries what
      the run found; put both properties in the head. **Two more "Printed":** the comments above
      the two refused-write reason constants in `apps/ingester/src/aoe2stats_ingester/capture.py`
      say "Printed in the report", and that module prints nothing. Say "Reported"
- [x] T673h Follow-ups from #132's second review (`reviewer` APPROVE 2026-10-11 on T673g; none
      blocks the merge; filed by the user's decision the same day). The first two concern an
      operator, and #132 changed neither sentence. Its own branch and pull request. **The `--after`
      help after a stop:** the option's help and `_cursor`'s refusal text in
      `scripts/ops/revalidate_quarantined.py` both say "copy the value the previous run printed".
      After a stop, the only `--after` value the previous run printed is the stop line's, which
      excludes the stopped row, where `docs/runbooks/revalidate-quarantined.md` names the `--after`
      the first stopped command was given. Both texts are string literals, so this item is an
      executable change and not a sentence: reword both so that neither offers the previous run's
      value for the case of a stop, and name the runbook for that case. A test in
      `scripts/ops/tests/test_revalidate_quarantined_command.py` that quotes either text moves with
      it. **A stop at the last selected row:** under both stops the runbook says the next run stops
      again while the failure lasts. Read on 2026-10-11 and not verified by a test: when the stopped
      row is the last one selected, a run given the stop line's value selects no row, reports that
      it examined nothing and exits 0, with the failure still there. Pin that with a test of the
      command; it is expected to pass as written, so say in the hand-back what it was run against.
      Then qualify both sentences: the next run stops again if a row lies past the stopped one, and
      a run that examined nothing shows nothing about the failure. **The repeated rows:** T673g's
      sentence under both stops says totals summed "over both runs" count a repeated row twice, and
      that the row "is examined". Under the database stop a run in between can list `inconclusive`
      and `integrity_failure` rows before it stops, and the re-run lists those again when its page
      reaches them; and a row that enters the selection ahead of a repeated row can push it past
      `--limit`. Name the two runs as the command and its re-run, say the row is offered again, and
      say a row a run in between listed is listed again. **What separates the two whole-reason
      outcomes:** `_WHOLE_REASON_OUTCOMES`'s comment separates them from the refused-write pair by
      "carries what the run found", and the comment above the `changed_elsewhere` reason in
      `apps/ingester/src/aoe2stats_ingester/capture.py` calls that reason "what it observed". The
      difference is that a refused-write reason is one fixed text, the same for every row; say that.
      "Shorter than the cut" is asserted by no test: assert it or cut it. **T673g's count:** its
      entry and its commit say four outcomes write nothing, which counts a real run's; `selected`,
      the dry run's outcome, writes nothing either. Amend the entry to say four of a real run's
      outcomes, dated
- [x] T673i Close #133's review (`reviewer` REJECT 2026-10-11 on T673h; three findings the code
      contradicts, four that do not block; the user chose the same day to close all seven in #133).
      Same branch and pull request as T673h. **The database stop's condition is too wide:** under
      the database stop `docs/runbooks/revalidate-quarantined.md` says the next run stops again "if
      a row lies past the stopped one". `_revalidate_one` in
      `apps/ingester/src/aoe2stats_ingester/capture.py` returns `integrity_failure` and
      `inconclusive` before any write, and the loop in `revalidate_quarantined` breaks only on an
      exception, so a run whose rows past the stopped one all end without a write does not stop,
      prints no stop line, and exits 0 (or 1 if an `integrity_failure` is listed) with the failure
      still there. That is the twin of the empty-page case T673h pinned. Pin it with a test of the
      command: two rows past the stopped one, both ending without a write while every write fails,
      no stop line, and the exit code the listed outcomes give. Then say under the database stop
      that the next run stops again if a row past the stopped one reaches a write, and that a run
      whose rows all needed no write, like one that selected none, ends without a stop line with the
      failure still there. The store stop's condition stands: every row reads the store. **A run in
      between under the store stop:** the sentence "a row a run in between listed is listed again
      when the re-run's page reaches it" lacks "if it is still in the selection". A run in between
      lists a row only where the failure did not hold for it, and can then mark it `stored` or
      report it `changed_elsewhere` or `ownership_changed`; those leave the selection. Add the
      qualifier under the store stop; the database stop's sentence names only the two no-write
      outcomes and stands. **`_WHOLE_REASON_OUTCOMES`'s comment overclaims:** in
      `scripts/ops/revalidate_quarantined.py` it says the pair's reason "differs from row to row".
      An `inconclusive` from the wall-clock cap reports one fixed text, and so does an exception
      with no message; a `still_quarantined` reason can repeat an engine verdict. Say "can differ
      from row to row" for both; what always holds is that the refused-write pair's reason is one
      fixed text. **The module docstring's last instruction:** "Copy the printed value exactly" in
      the same module follows a paragraph that describes two printed values, the continuation's and
      the stop line's, so it still offers the stop line's value after a stop; `--help` sends the
      operator to that docstring. It is the last place that does: `git grep` on 2026-10-11 found no
      other. Reword it as the two literals were. **The runbook path breaks in `--help`:** argparse
      wraps on hyphens, so the rendered help prints `docs/runbooks/revalidate-` and `quarantined.md`
      on two lines, and the test in `scripts/ops/tests/test_revalidate_quarantined_command.py` reads
      the raw help text, not the rendered one. Make the path survive rendering (a
      `RawDescriptionHelpFormatter` or a non-breaking form) and have the test assert on
      `format_help()`; the test fails first against the wrapped path. **`_WHICH_VALUE`'s comment:**
      it says the stop line's value "is not what the runbook has an operator give after a stop". The
      runbook presents that value as the way past the stopped row, and names the first command's
      `--after` only for a failure that is not about the row. Say that. **The test's negative
      needle:** `"previous run printed" not in out` passes against "the last run printed". Assert
      the absence of the shape, not of one wording: no sentence in either text offers a run's
      printed value without naming the "more candidates remain" line
- [x] T673j Close #133's second review (`reviewer` REJECT 2026-10-11 on T673i's delta alone; two
      tests that stay green without the behaviour they are named for, one runbook sentence false in
      the runbook's own vocabulary, and four that do not block; closed in #133 as the user chose for
      T673i). **The no-write test patches one write of two:** `_every_write_fails` in
      `scripts/ops/tests/test_revalidate_quarantined_command.py` replaces
      `CaptureDrain._mark_stored` only, while its docstring says "every write failing";
      `_mark_quarantined`, the write a `still_quarantined` row takes, still succeeds. Measured: with
      `_revalidate_one`'s `inconclusive` branch made to call `_mark_quarantined` before returning,
      both parametrisations pass. Patch `_mark_quarantined` with the same raising function and the
      same counter, so that the counter at 1 means no write was reached; the plant above must then
      fail both parametrisations, and the hand-back quotes that failure. **The clause check is
      case-sensitive:** `_sentences_offering_a_printed_value_unqualified` searches
      `\bcopy\b|\bprint(?:ed|s)\b` without `re.IGNORECASE`, and the split at `. ` puts "Copy" at a
      clause's start, where it is never matched; measured, "resume here. Copy the stop line's value"
      returns no clause. Of the four parametrised offers, none exercises the `copy` arm without
      "printed", so a pattern of `printed` alone passes all four. Add `re.IGNORECASE`; add offers
      with "Copy" and no "printed", and one with "prints"; and narrow the test's name and docstring
      to what the check does: a clause, split at `;` or `. `, that says copy, printed or prints in
      any case without naming the "more candidates remain" line. The check does not find an offer
      worded with "output" or "shows", nor one joined to its qualifier by a comma; the docstring
      says neither that it does nor "whatever its wording". **"Wrote nothing":**
      `docs/runbooks/revalidate-quarantined.md` under the database stop says "A run that wrote
      nothing shows nothing about the failure". The paragraph's premise is a database that fails
      every write, under which the run that stops again also wrote nothing and shows the failure
      with a stop line; and the runbook's table and `capture.py` both use "writes nothing" for
      `changed_elsewhere` and `ownership_changed`, which reached the database. Say "A run that
      reached no write". **The database stop's twin of T673i's qualifier:** the same paragraph says
      the re-run "lists those again when its page reaches them" of the `inconclusive` and
      `integrity_failure` rows a run in between listed; an objection or an unlink takes such a row
      out of the selection. Add "if they are still in the selection", as the store stop's sentence
      has. **An exception with no message:** `_WHOLE_REASON_OUTCOMES`'s comment in
      `scripts/ops/revalidate_quarantined.py` says such an exception reports "one fixed text";
      `_validate_with_barrier` reports the bare class name, fixed per class and different between
      classes. Say "an exception of one class with no message reports its bare class name". **The
      width bound:** the rendered-help test's docstring says the help column is narrower than the
      path "below about 66 columns"; the reviewer measured the path whole at 65 and cut at 64, the
      help column being 26 narrower than the terminal and the path 39 characters. Measure it again,
      state the measured bound and the two numbers it follows from, and start the sweep at that
      bound rather than at 70. **Left unguarded, recorded here:** the module docstring's reworded
      last sentence has no regression test; the clause check pointed at the docstring flags its
      descriptive sentences about what the report prints, so a guard there would need a different
      check, and none is added
- [x] T713 Stop the claim from taking a capture whose profile has no active link (filed 2026-10-11
      from T673b; decided by the user the same day). `CaptureDrain._claim_batch` in
      `apps/ingester/src/aoe2stats_ingester/capture.py` excludes a row only when
      `_objecting_owner_exists` finds an active link whose user has objected, so a capture queued
      while a link stood is still fetched and stored after the user unlinks the profile, objector or
      not; 001's spec says automatic ingestion stops for a profile its user unlinks (US1, acceptance
      scenario 6). Claim a row only when its profile has an active link whose user has not objected:
      `_owner_is_archiving`, the predicate T673b gave the re-validation, so the claim and the
      re-validation share one definition. This reverses T089a's stated choice that only a found
      objection removes a row from the claim; correct `_claim_batch`'s docstring,
      `_objecting_owner_exists`'s, and `_owner_is_archiving`'s, which calls itself stricter than the
      claim. **Both arms:** the predicate applies to a `pending` row and to a stale `downloading`
      row taken again. **What a refused row becomes:** it is never fetched and the source drops the
      recording after its retention window (`docs/data-sources.md`), so this refusal cannot be
      undone, where T673b's can. Read what an objector's unclaimed row does today once its capture
      deadline passes: the deadline alert in `apps/ingester/src/aoe2stats_ingester/run.py` and the
      pending-past-deadline assertion in `scripts/checks/capture_audit.py` were read on 2026-10-11
      as filtering on status alone, which is not yet verified by a test. A row with no active link
      behaves as an objector's row does; if that is an alert or a red audit for a capture nobody may
      take, file it for the user and do not decide it here. **Red first:** a `pending` capture whose
      user unlinked after it was queued is not claimed; nor is one whose objecting user unlinked;
      nor is a stale `downloading` row in either case. Contrast: a profile relinked by a second user
      who has not objected is claimed, and a row with an active link whose user has not objected is
      claimed as before. **Fixtures:** `_claim_batch`'s docstring records that tests seed captures
      with no link rows at all. Count them before starting; each gains a link through a shared
      helper, the predicate gains no exception for them, and the predicate and every fixture it
      turns red are one commit. **Left to the user, not decided here:** a download already in flight
      when its user unlinks or objects, since the normal path's stored and quarantine writes carry
      no ownership guard, where T673b gave the re-validation's writes one. Its own branch and pull
      request, not #129
- [x] T713a Close #135's review (`reviewer` REJECT 2026-10-11 on T713; no wrong write and no
      constitution finding. Verified and not to be re-checked: `archiving_links` is exactly an
      active link whose user has not objected; the compiled claim gates both arms with it, an
      uncorrelated positive `IN`, lock and order unchanged; `_claim_batch` is the only writer of
      `downloading` and no path bypasses it; against the old predicate, which reads only the
      objection, 6 of the 14 claim tests fail and 8 pass; the six fixture helpers link no profile
      in a test about the absence of a link). **A third reader of the same condition:**
      `deadline_gate_admits` in `apps/analyzer/src/aoe2stats_analyzer/admission.py` refuses every
      analysis request while any `pending` or `downloading` row is past its capture deadline, and
      reads neither links nor objections, so one refused row past its deadline refuses
      `POST /api/analyze` for every user. T721 names two readers; add this one to its facts, and
      pin it in `apps/analyzer/tests/test_admission.py` as the other two are pinned: a
      characterization, for an objector's row and for an unlinked profile's row. **Three texts the
      claim made false:** `apps/api/src/aoe2stats_api/routers/replays.py` and `ReplayFetchMiss`'s
      docstring in `packages/storage/src/aoe2stats_storage/models.py` say the claim has no
      ownership filter and downloads any `pending` row for any profile;
      `apps/api/src/aoe2stats_api/routers/profiles.py` says an unlinked profile's rows archive
      nothing further only because discovery drops the link. Say what the claim does now. The
      conclusion each draws, that the download route writes no `replay_captures` row, is not
      reopened. **`_claim_batch`'s docstring on a refused row:** it says a refused row was never
      fetched, that the refusal cannot be undone and the capture is lost, that a relink makes the
      row claimable "while the window lasts", and that the gate only stops a capture that has
      fetched nothing. The stale `downloading` arm can hold a row with a committed object; the
      claim has no window clause; and the second and third of those contradict each other. State
      only: a refused row keeps its status and nothing is written to it; it is claimable again once
      its profile has an active link whose user has not objected; a row with no committed object
      is not fetched while it is refused, and the source keeps a recording for a bounded time
      (`docs/data-sources.md`); a row with a committed object keeps it. The same wording in the
      docstring of `apps/ingester/tests/test_claim_requires_active_link.py`, and "stays `pending`
      for good" in `apps/ingester/tests/test_deadline_alert.py`. **A uniqueness the tree does not
      have:** `tests/links.py` calls itself the one place a test gives a profile an owner and says
      every fixture seeding a capture to be claimed goes through it, and `_claim_batch`'s docstring
      repeats it; other test files build a `ProfileLink` themselves,
      `apps/ingester/tests/test_quota.py` among them. Claim only that the helper exists and which
      fixtures this change moved onto it. The other helpers are not migrated here. **A guard that
      cannot fail:** the source-inspection test in
      `apps/ingester/tests/test_revalidate_quarantined.py` looks for the call in
      `inspect.getsource`, which includes the docstring, and `_claim_batch`'s docstring spells the
      call. Read the code without its docstring, for the claim and for the three sibling assertions
      alike. Red first: with the call removed from `_claim_batch`'s body and its docstring
      unchanged, the guard fails. **Contrasts to add** to the claim tests: a profile relinked by a
      second user who has objected is refused; a stale `downloading` row holding a committed object
      is refused, keeps its object key and checksum, and is claimed once its profile has an active
      link whose user has not objected. Not added, recorded here: a relink by the same user.
      **T721's entry** gains, as facts: the third reader; that `expired` is written when a claimed
      row's fetch answers 404 past its capture deadline, with a severity-1 `expired_capture` alert,
      which is what a refused row relinked after its deadline meets if the source no longer has the
      recording; and that `backlog_remaining` on `ingest_runs` counts refused rows
- [x] T713b Close #135's second review (`reviewer` REJECT 2026-10-11 on T713a; delta-scoped, two
      sentences, no code and no test logic. Verified and not to be re-checked: the five blocking
      findings of the first review closed where they were cited, T721's amended facts, the two
      added contrasts, and the guard failing with the call removed from the body). **A fact in
      T713a's entry:** it records that none of the 14 claim tests passes against a predicate that
      reads only the link or only the objection. Measured on T713: against the old predicate,
      which reads only the objection, 6 of the 14 fail and 8 pass. Say that, and nothing about a
      predicate that reads only the link, which was not run. **A twin of the uniqueness claim:**
      the module docstring of `apps/ingester/tests/test_claim_requires_active_link.py` says the
      fixtures that claim give their profile a link through the shared helper;
      `apps/ingester/tests/test_quota.py` and `apps/ingester/tests/test_consent_withdrawal.py` seed
      captures a drain claims and build their own link rows. The parenthetical says only that the
      predicate has no exception for the absence of a link. **Loose, cut:** `ReplayFetchMiss`'s
      docstring in `packages/storage/src/aoe2stats_storage/models.py` says a `pending` row the
      claim takes is fetched on that cycle; a row the quota defers is claimed and handed back
      without a fetch. Drop the clause. **An id two features define:** the open decision was filed
      as T714, which `specs/005-design-system-foundations/tasks.md` also defines. It is T721 here,
      in this file and in the docstring of the admission characterization test
- [x] T721 Give a capture the claim refuses a terminal status once its capture deadline passes
      (filed 2026-10-11 from T713 as T714, an id 005's file also defines, and renumbered the same
      day; amended from #135's review; decided by the user 2026-10-12). Since T713 the claim takes
      a row only when its profile has an active link whose user has not objected, and a refused row
      keeps its status. Three readers filter on the deadline and the status and read neither links
      nor objections: `_raise_deadline_breach_alert` in
      `apps/ingester/src/aoe2stats_ingester/run.py`, `captures_pending_past_deadline` in
      `scripts/checks/capture_audit.py`, and `deadline_gate_admits` in
      `apps/analyzer/src/aoe2stats_analyzer/admission.py`. So a refused row past its deadline is
      carried by the severity-1 `deadline_breach` alert, fails the nightly capture audit, and makes
      the admission gate refuse `POST /api/analyze` for every user. **The status:** `withdrawn`, a
      new value of `CaptureStatus` and of the `replay_capture_status` type, added by one additive
      revision as `1f9879367c9d` added a value to `alert_kind`; the expected schema revision in
      `packages/storage/src/aoe2stats_storage/revision.py` moves with it. The claim never takes a
      `withdrawn` row. **The write:** one statement on `CaptureDrain` sets `withdrawn` on every row
      that is past its capture deadline, is `pending` (whatever its next attempt time) or a stale
      `downloading` row as the claim defines stale, and fails `_owner_is_archiving`. It writes the
      status and a fixed reason in `last_error`, and nothing else: an object key and checksum the
      row holds stay, and no object is read, written or deleted. It raises no alert and adds no
      column. `run_once` calls it once per cycle, after the stages and before the deadline sweep,
      on every stage that offers it, whether or not that stage ran, and with the instant the sweep
      then uses; the ingest cycles of `apps/api/src/aoe2stats_api/ingest_stages.py` always carry
      the drain. A cycle given no such stage withdraws nothing. **Not taken by
      the write:** a row not yet past its deadline, so a profile relinked before then is claimed as
      T713 left it; a `downloading` row that is not stale, the download in flight T713 left to the
      user; a row whose profile has an active link whose user has not objected, which stays for
      the deadline alert. **The readers:** `withdrawn` joins the resolved statuses of the deadline
      sweep and of the capture audit; the admission gate reads `pending` and `downloading` only and
      needs no change. A `withdrawn` row occupies its `(game_id, profile_id)` pair, so discovery
      queues no new capture for it after a relink. **Red first**, at the write: a `pending` row
      past its deadline is withdrawn when its user unlinked, when its user objected, and when its
      next attempt time has not come; a stale `downloading` row holding a committed object is
      withdrawn with its key and checksum unchanged. Contrasts, each left as it is: the same rows
      one hour before the deadline; a `downloading` row that is not stale; a row whose profile has
      an active link whose user has not objected; a row whose profile was relinked by a second user
      who has not objected; a `stored` row. At `run_once`: a cycle over a refused row past its
      deadline leaves it `withdrawn` and raises no `deadline_breach` for it, and still raises one
      for an owned `pending` row past its deadline in the same cycle. The three characterization
      tests of T713 and T713a become tests of the decision: each reader still counts a refused row
      that is still `pending`, and does not count it once `withdrawn`. **Every consumer of the
      status values:** grep them before starting; the match routes serialise the value as it is.
      What the interface shows for it is T722, not this task
- [x] T721a Close #135's review of T721 (`reviewer` REJECT 2026-10-12, one blocking finding; decided
      by the user the same day. Verified and not to be re-checked: the statement's selection, its
      races with the claim and with the re-validation, `run_once`'s order and shared instant, the
      revision and its downgrade, every other reader of the status, each new test failing for the
      reason it names, and the facts of T721's and T722's entries). **The window T721 left:** the
      write runs once per ingest cycle and took a row only past its deadline, and production runs
      one cycle a day (`vercel.json`), so a refused row stayed `pending` from its deadline to the
      next cycle: the admission gate refused `POST /api/analyze` for every user in that window, and
      the nightly capture audit, scheduled before the cycle, could fail once. **Decided:** the write
      takes a refused row a lead before its deadline. The lead is `INGEST_WITHDRAW_LEAD_HOURS`, a
      required key as the drain's other settings are, with no default, handed to `CaptureDrain` by
      `apps/api/src/aoe2stats_api/ingest_stages.py`. The selection becomes: the capture deadline is
      less than the lead away, or past. Nothing else in the statement changes, and no reader
      changes. The lead has to exceed the longest gap between two ingest cycles; the docstring says
      so and names where the schedule lives, without restating it. **What it costs:** a profile
      relinked inside the lead finds its row `withdrawn`; the claim takes a refused row only until
      the write has reached it. **What it does not close, state it:** a row whose profile loses its
      archiving owner inside the lead, and less than one cycle before the deadline, is still
      `pending` past its deadline until the next cycle. The admission gate and the audit count it
      until then; the deadline sweep never does, the next cycle's write reaching it first.
      **Red first:** a refused row whose deadline is one hour inside the lead is withdrawn; with a
      lead of zero it is not. Contrasts: one hour outside the lead, left as it is; an owned row
      inside the lead, left as it is; a row past its deadline, withdrawn as before. The earlier
      contrasts seeded one hour before the deadline move outside the lead. **Across the window:**
      after one cycle over a refused row whose deadline is inside the lead, the admission gate
      admits and the audit's assertion finds nothing at an instant after that deadline. **The
      setting:** a missing key refused, an override from the environment reaching the drain, and
      its declaration where the other ingest settings are declared. **Texts:** `_claim_batch`'s
      docstring says a refused row is claimable until its deadline passes; say until the write has
      withdrawn it. The fixed reason reads as if no link existed when the deadline passed; the
      write reads ownership when it runs, so say that. `CaptureStatus`'s docstring, the module
      paragraphs of `capture.py` and `run.py`, the audit's comment and the revision's docstring
      say the write acts once the deadline has passed; each says the lead. **A
      contrast that proves less than it names:** the other-status rows of the withdrawal tests
      carry no claim time, so a stale-claim clause that lost its status check would leave them
      untouched; give them an old one
- [x] T721b Close #135's review of T721a (`reviewer` REJECT 2026-10-12; text only, no code and no
      test logic at fault. Verified and not to be re-checked: the clause and its arithmetic, no
      wrong write beyond the stated cost, the window closed as decided, the setting and where it is
      declared, the tests, and T722's added fact). **The residual reaches two readers, not three:**
      the deadline sweep runs only inside a cycle, after the write and with its instant, and the
      write's deadline clause contains the sweep's, so a row that lost its owner inside the lead is
      withdrawn before the sweep reads it and raises no `deadline_breach`. Between cycles only the
      admission gate and the nightly audit read the table. Say so wherever the residual is stated:
      the module paragraph and the method's docstring in `capture.py`, the module paragraph and the
      comment on the excluded statuses in `run.py`, and T721a's entry; and wherever a text says
      "the readers" for it: the docstrings of the withdrawal tests and of the sweep test, and the
      setting's comment in `.env.example`. **Pin it:** in the residual test the second cycle runs at
      an instant after the deadline, and the row is withdrawn with no `deadline_breach` naming it.
      **Two facts in T721a's entry:** `packages/storage/src/aoe2stats_storage/revision.py` never
      said when the write acts and is not one of the texts to correct; the lead has no default, the
      key is required and `.env.example` declares its value. **A leftover:**
      `packages/storage/tests/test_models.py` still says the claim refuses a capture once its
      deadline has passed. **Stated a little wide, narrow it:** the cost names a relink inside the
      lead; a relink before the write has reached the row is still claimed, and a lifted objection
      meets the same rows as a relink
- [x] T722 Show a `withdrawn` capture in the interface (filed 2026-10-12 from T721). The match
      routes serialise `replay_captures.status` as it is, for the caller's own linked profiles, so
      an objector with an active link receives `withdrawn` for a match past its capture deadline.
      `packages/design-system/specs/capture-state-badge.md` and `CaptureStateBadge` name seven raw
      values collapsed into four states; an eighth falls to the component's unknown-status state, a
      neutral badge carrying the raw word. `apps/web/src/features/replays/uploadEligibility.ts`
      offers the manual upload for `unavailable`, `expired` and `failed` only, and withholds it from
      `quarantined` because that row's bytes are already stored. A `withdrawn` row can hold a
      committed object too: the upload route in `apps/api/src/aoe2stats_api/routers/replays.py`
      refuses a `stored` row only, and puts the uploaded bytes under the row's object key. The
      `product-designer` first: which of the four states `withdrawn` reads as, its wording, and
      whether the manual upload is offered. That spec's lines are cited by number; keep its line
      count. Its own branch and pull request, after #135
- [x] T722a Close #137's review of T722 (`reviewer` REJECT 2026-10-12. Verified and not to be
      re-checked: the label, the `neutral` variant and its pair in the contrast table, the
      sentence in `detail` only with its association, a known status never reaching the fallback,
      the tests' contrasts, and no cited line moved). **The sentence asserted the state at
      closure:** it said archival was not running when the capture window closed, and the write
      runs a lead before the deadline and reads ownership as it runs (T721a), so it was false for
      an objector reading before the deadline, beside a recording the page still offers from the
      source, and for an owner who relinked or lifted the objection before it. The sentence is
      now "Automatic capture ended for this match while archival was not running for this
      profile.": no deadline, no source, nothing about what the row holds, nothing to do or not
      to do. `packages/design-system/specs/capture-state-badge.md` §3, the component, its
      comments and the three test files that pin the sentence say so. **A sentence the change made
      false:** §4 said the variants differ only in the second line's phrasing and layout; for
      `withdrawn` its presence differs too. **The count gate:** three stories net and eighteen
      baseline files net; `scripts/checks/story-baselines.mjs` and the figure in
      `packages/design-system/specs/README.md` move with them. **The upload's reason:** withheld
      because the row may hold an object the upload would overwrite, on that reason alone;
      whether an objector's own upload is a capture is T723's, and no text here settles it.
      **A criterion that could not fail:** `MatchDetailPanel` renders no upload for any status, so
      its story's criterion claims the download only. **Two facts in the entries filed with
      T722:** a `quarantined` row names the key and may hold nothing under it; the claim has
      refused an objector's row since T089a, not T713
- [x] T723 Decide what the manual upload does to a row that holds an object (filed 2026-10-12 from
      T722). `upload_replay` in `apps/api/src/aoe2stats_api/routers/replays.py` refuses a `stored`
      row only, then writes with the object store's `put`, which overwrites, under the key an
      automatic capture uses for the pair; `record_manual_upload` then marks the row `stored`. A
      `quarantined` row names that key and the withdrawal write leaves `object_key` as it was, so
      a row of either status can hold an object there: a direct `POST` on one that does replaces
      the bytes. The interface withholds the upload for both statuses
      (`apps/web/src/features/replays/uploadEligibility.ts`) and is the only barrier. The route
      reads the caller's active link and not `archival_objected_at`. The match response does not
      say which rows hold an object, and T722 withheld the upload from every `withdrawn` row, so
      an owner who relinked or lifted the objection cannot supply the file for one. The interface
      withholds the upload from `pending` and `downloading` because the capture may still succeed
      on its own (`packages/design-system/specs/manual-upload.md`); for an objecting owner's
      `pending` row the claim refuses it, so that reason does not hold there (T724). To decide
      first, by the user: which rows the route refuses, and whether an objector's own upload is a
      capture constitution IX stops. **Decided (user, 2026-10-13).** **Rows refused:** the route
      refuses, 409, a row that is `stored` or that names an `object_key`, whatever its status, and
      it writes with the object store's `put_if_absent`, refusing the same way when the store
      answers that the key exists. A refusal writes nothing: no object, and no row created or
      changed. A row of any other status that names no `object_key` is accepted as before, a
      `withdrawn` one included. **An objector's upload is a capture the objection stops:** the route
      refuses a caller whose `archival_objected_at` is set, 409 with a code of its own, after the
      participation check and before the file is read, whatever the row; with the objection lifted
      the same request is accepted. **The interface** withholds `UploadControl` from an objecting
      caller for every status, on `archival_objected` of `GET /api/me`, which
      `apps/web/src/features/replays/MatchDetailContainer.tsx` holds (T724); the `product-designer`
      amends `packages/design-system/specs/manual-upload.md` first, keeping its line count (its
      lines are cited). **Tests, each red before:** a `quarantined` row naming a key, and a
      `withdrawn` row naming one, are refused with the stored bytes and the row unchanged; a pair
      with no row and an object under its key is refused and no row is created; an objector's upload
      for an `expired` row is refused and nothing is written; the match page of an objecting caller
      shows no upload for an `expired` row. **Contrasts:** a `withdrawn` row naming no key is stored
      `manual`; an `expired` row is stored as today; the request the objection refused is accepted
      once it is lifted; a caller who does not object still sees the upload for an `expired` row.
      **Left as it is:** the interface still withholds the upload from every `withdrawn` row (T727),
      and the automatic capture's own write (T728)
- [x] T723a Close #143's review of T723 (`reviewer` REJECT 2026-10-14, three blocking findings;
      verified and not to be re-checked: the route's order and codes against the decision, the web
      gate and its two tests, the citations and line counts, and that no other feature defines
      T726–T729). **The row-level refusal is untested:** with the `object_key` check removed from
      `upload_replay` the suite stays green, because the test seeds the store as well as the row and
      `put_if_absent` refuses in its place. A row naming a key with no object under it exists: the
      reclaim's integrity check quarantines one and keeps the key. Add that case, `quarantined` and
      `withdrawn`, the store empty: `409` `replay_held`, no store write, the row unchanged; shown
      red with the check removed. **Two sentences false:** the fake store's class docstring in
      `apps/api/tests/conftest.py` says each request gets a fresh one and nothing can be asserted on
      shared state, which the shared fixture this change added contradicts; and "`quarantined`
      (bytes are already stored)" in `packages/design-system/specs/manual-upload.md` §2 and
      `apps/web/src/features/replays/uploadEligibility.ts`, false for that same row. Also stale
      since T723: `ObjectStore.put_if_absent`'s docstring names the analysis document as its one use
- [x] T724 Decide what a `pending` capture reads for an objecting owner (filed 2026-10-12 from
      T722). `CaptureStateBadge` renders a `pending` row as "Still catchable" with "Captures
      automatically within N days" in `detail`; since T089a the claim refuses that row while the
      objection stands, and T721a's write withdraws it a lead before its deadline. Until then the
      sentence promises a capture that will not run. The match routes in
      `apps/api/src/aoe2stats_api/routers/matches.py` serialise the status as it is and do not
      read `archival_objected_at`. The `product-designer` first; the spec's lines are cited by
      number, keep its line count. **Decided (`product-designer`, 2026-10-13):** with the badge's
      `archivalObjected` input, a `pending` or `downloading` row renders as `withdrawn` does: "Not
      archived", `neutral`, the pill alone in `compact`, and in `detail` the one sentence "Archival
      is off for your account."; no countdown and no interval, whatever the deadline. Every other
      status ignores the input, and the upload and download gates did not move. **The signal** is
      `archival_objected` of `GET /api/me`, which
      `apps/web/src/features/matches/MatchHistoryContainer.tsx` and
      `apps/web/src/features/replays/MatchDetailContainer.tsx` already hold. The list route
      requires the caller's active link on the profile, the detail route carries a capture status
      for the caller's actively linked profiles only, and a profile has at most one active link:
      for a `pending` row and a stale `downloading` row those two pages show, the caller's
      objection is the claim's refusal (T724a has the `downloading` row it is not). **No
      field on the match routes:** `match_row_json` also serves
      `GET /api/players/{profile_id}/matches` for any profile, where the field would disclose
      another player's objection. `MatchList` does not forward the input with `subject="other"`.
      **The count gate:** three stories net and eighteen baseline files net;
      `scripts/checks/story-baselines.mjs` and the figure in
      `packages/design-system/specs/README.md` move with them. **Left as it is:** T726
- [x] T724a Close #140's review of T724 (`reviewer` REJECT 2026-10-13, three blocking findings,
      all text; no behaviour changed. Verified and not to be re-checked: the equivalence for a
      `pending` and a stale `downloading` row on both own-match pages, the forwarding and its
      `subject` gate, the tests' contrasts, the counts, and no cited line moved). **Two call
      sites disagree:** an objecting owner's `pending` row reads "Not archived" on their own list
      and match page and "Still catchable" on the third party's list of their own profile, so
      `packages/design-system/specs/capture-state-badge.md` no longer says no two call sites
      disagree: the badge alone maps a status and the input to a reading, and a third party's
      list withholds the input. **The input is passed for every match:**
      `apps/web/src/features/replays/MatchDetailContainer.tsx` passes it whoever played; the
      detail route joins a capture row for the caller's actively linked profiles only, so the
      status is `null` for any other match and the badge renders nothing. The spec and the two
      component comments say that, and a test pins it. **A `downloading` row claimed before the
      objection:** the claim refuses a `pending` row and a stale `downloading` row; a download
      already in flight is not stopped and can still end `stored`, and the client cannot tell
      the two apart. An objector's page loaded in that window reads "Not archived" and the row
      can read "Archived" on the next load. The spec says so and no longer says such a page
      reads "Still catchable" all along. **The session value is a cached one:** the `me` query
      is not refetched within its stale time, so an objection changed in another tab shows its
      old reading until a refetch. **Two tests that claimed more than they pin:** the third-party
      list test passes on `MatchList`'s gate alone, and the objecting fixture had no linked
      profile, a response the server cannot produce
- [x] T726 Decide what a third party's list shows for a capture the claim refuses (filed
      2026-10-13 from T724, as T725 in #140; renumbered the same day, because #139 gave that id
      to a task of 005). `GET /api/players/{profile_id}/matches` serialises the status as it is
      for any signed-in caller, and `MatchList` with `subject="other"` renders it without the
      caller's objection (`packages/design-system/specs/match-history.md` §11.3). A `pending` or
      stale `downloading` row the claim refuses reads "Still catchable" with its countdown there,
      to every viewer: an objector's row, and the row of a profile with no active link. The client
      holds no signal for another player's objection or link, and a field saying so would disclose
      it. For the owner who opens their own profile by that route the client does hold the signal
      (the profiles and `archival_objected` of `GET /api/me`) and nothing is disclosed; `MatchList`
      withholds the input there on `subject="other"` alone. To decide first, by the user: whether
      a third party's row carries a capture state at all, and if it does, what the server serves
      for a row the claim refuses. **Decided (user, 2026-10-13).** **A third party's row carries no
      capture state:** `GET /api/players/{profile_id}/matches` serves `capture_status` and
      `capture_deadline_at` as `null` unless the caller holds an active link on that profile, which
      is the rule the detail route already applies; the second question then has no case left. **The
      owner by that route** is served the state, and `MatchList` forwards the caller's objection
      when the profile viewed is one the caller is actively linked to, instead of withholding it on
      `subject="other"` alone. The `product-designer` amends
      `packages/design-system/specs/match-history.md` §11.3 and
      `packages/design-system/specs/capture-state-badge.md` first, keeping their line counts
- [x] T727 Offer the upload on a `withdrawn` row that holds no object (filed 2026-10-13 from
      T723). Since T723 the route accepts an upload for a `withdrawn` row that names no
      `object_key`, from a caller who does not object;
      `apps/web/src/features/replays/uploadEligibility.ts` still withholds `UploadControl` from
      every `withdrawn` row, because the match response does not say which rows hold an object.
      After T726, so that whatever the response gains is served for the caller's own capture only.
      The `product-designer` first: what the response carries, and what
      `packages/design-system/specs/manual-upload.md` says of the row. **Decided (`product-designer`,
      2026-10-17).** `GET /api/matches/{game_id}` alone serves `capture_object_held`, a boolean read
      from the row `capture_status` is read from, `true` when it names an `object_key`, and `null`
      exactly where `capture_status` is; the list routes do not carry it, as nothing there reads
      it. The interface offers `UploadControl` for a `withdrawn` row only when it is `false`, and
      withholds it for `true`, `null` or absent (`manual-upload.md` §2, `capture-state-badge.md`)
- [x] T728 Decide what the automatic capture's write does to a key that holds an object (filed
      2026-10-13 from T723). `CaptureDrain` in `apps/ingester/src/aoe2stats_ingester/capture.py`
      writes a downloaded blob with the object store's `put`, which overwrites, under the key a
      manual upload uses for the pair. T723 made the upload's write conditional; the drain's is not.
      The route does not refuse a `pending` or `downloading` row that names no key, so an upload
      accepted while a claim on the row is in flight is followed by the drain's write over it. Not
      measured: whether the drain's row writes that follow are refused on a row the upload has
      marked `stored`. To decide first, by the user: whether the route refuses a row a claim holds,
      or the drain's write becomes conditional, or both. **Decided (2026-10-16, by Claude on the
      user's delegation).** **The drain's write becomes conditional; the route is unchanged.** Read
      on the same day, closing what was not measured: the drain's row writes are not refused on a
      row the upload has marked `stored`, because `_commit_blob_metadata` and an unguarded
      `_mark_stored` match the row's id alone. `CaptureDrain` writes the downloaded blob with
      `put_if_absent`. When the key already holds an object, the drain writes nothing over it, and
      records that object only when its SHA-256 equals the download's: only then are the bytes the
      response the drain received, as the row's `source` and `http_status` say (FR-033, constitution
      IV), and the drain validates and marks the row as for its own write. When the hashes differ
      the object may be a manual upload: the drain writes no blob metadata and hands the row back as
      a failed attempt, as `_handle_provider_unavailable` does, so the bounded retry ends it
      `failed` unless the upload's own row write, or T730's retry of the same file, records it
      first. Every row write the drain makes after its claim matches the row only while it is still
      `downloading`, so a row an upload has marked `stored` is never rewritten. The route does not
      refuse a row a claim holds: with both writes conditional, the first object to land is the one
      kept, and a refusal there would only hand the uploader an error they can do nothing about.
      **Tests, each red before:** an upload landing between the drain's claim and its write leaves
      the uploaded bytes and the upload's row unchanged; an object under the key of a `downloading`
      row that names no key, with the download's hash, is validated and recorded `automatic`; with a
      different hash, the row names no key, its attempt stands, and the object is unchanged.
      **Contrast:** a key that holds nothing is written and recorded as today
      **Amended (2026-10-16, by Claude on the user's delegation, after #148's review).** The
      drain's own object is told apart from an upload by a marker, not by its hash: the drain
      writes its object with S3 user metadata naming the automatic capture, and when the key is
      held by an object carrying that marker, the drain adopts it whatever its hash, recording that
      object's own size and SHA-256, because a drain killed between its write and its row write
      would otherwise strand a real replay if the source's bytes are not stable across downloads,
      which is not measured. An object without the marker keeps the rule above. Objects written
      before the marker existed carry none, so a row stranded that way recovers through the
      equal-hash branch only. The blob metadata commit matches the row while it names no object,
      whatever its status, so a row withdrawn or reverted after the drain's write still names the
      drain's object and erasure reaches it. A 409 from the store (a concurrent conditional write
      in flight) hands the row back without counting an attempt instead of aborting the run
- [x] T729 Decide what an `expired` or `failed` capture reads for an objecting owner (filed
      2026-10-13 from T723). `CaptureStateBadge`'s `SecondaryLine` for both statuses ends "If you
      still have the file, you can upload it."
      (`packages/design-system/specs/capture-state-badge.md` §3). Since T723 an objecting caller is
      offered no `UploadControl` and the route refuses their upload, and the badge reads its
      `archivalObjected` input for a `pending` or `downloading` row only (T724), so an objecting
      owner reads that sentence with no upload under it. The `product-designer` first; the spec's
      lines are cited, keep its line count. **Decided (2026-10-16, by Claude on the user's
      delegation).** **With `archivalObjected`, `expired` and `failed` read their first sentence
      only.** The badge reads the input for those two statuses as well as for `pending` and
      `downloading`, and drops "If you still have the file, you can upload it.", because no upload
      is offered under it. Without the input both read as today. The `product-designer` amends §3
      within its current line count, and the quotation of that recourse in
      `packages/design-system/specs/manual-upload.md`, keeping that file's line count too (its lines
      are cited). **Tests, each red before:** an objecting owner's `expired` and `failed` rows show
      no upload sentence. **Contrast:** a caller who does not object still reads it
- [x] T730 Decide what an upload does when its row write fails after its object write (filed
      2026-10-14 from #143's review). Since T723 `upload_replay` writes the object with
      `put_if_absent` and then the row: if the row write or the request's commit fails after the
      object is written, the object stays under the key and no row names it, and every retry of the
      same upload is refused `replay_held`, which `UploadControl` shows as `failed` with "Try
      again". Account erasure in `apps/api/src/aoe2stats_api/routers/privacy.py` deletes the objects
      its rows name, so it does not delete that one. To decide first, by the user: what the route
      does with an object under the key that no row names. **Decided (2026-10-16, by Claude on the
      user's delegation).** **A retry of the same file completes the upload; nothing is deleted on
      the failure path.** When `put_if_absent` finds the key held and no row names an object for the
      pair, the route reads the object: if its SHA-256 equals the upload's, the route writes the row
      as for a fresh upload; otherwise it refuses `replay_held` as today. A compensating delete is
      refused, because the object is an original replay, which is never deleted. **Erasure:**
      `erase_account` also deletes every object under one of the erased user's pairs' keys that no
      row's `object_key` names, whether or not the pair has a row, so an orphan does not outlive its
      owner's erasure; that it fits the function's duration for the largest measured match history
      is shown before it is written. **Tests, each red before:** with the object written and the row
      write failed, a retry of the same bytes ends `stored`; erasure removes an object no row's
      `object_key` names, under one of the user's pairs that has a row and under one that has none.
      **Contrast:** a retry with different bytes is refused `replay_held` and nothing is written
- [x] T740 Decide what a drain's late write does to a row a concurrent drain ended (filed 2026-10-17
      from #148's second review, N1). Since T728 the blob metadata commit names the drain's object
      on a row that names none whatever its status, and the `stored` mark matches only a
      `downloading` row. When a drain's claim goes stale while it is still running, a second drain
      can reclaim the row and end it `expired`, `failed` or `unavailable`; the first drain's write
      and commit then land, and the row keeps that status while naming a replay that was never
      validated. No claim selects it, the upload route answers `replay_held`, and the `expired` case
      has already raised its severity-1 alert. Not reachable on Phase 1 hosting, where the claim's
      stale age equals the function's maximum duration; reachable on a host without that bound. To
      decide first: whether the drain's `stored` mark also matches those three statuses when the row
      names the drain's own key, keeping `withdrawn` excluded. **Decided (2026-10-18, by Claude, the
      user having asked for T740 to be implemented; amended the same day from #174's review).**
      **Yes: the drain's `stored` mark also matches `expired`, `failed` and `unavailable` when the
      row names the drain's key; `withdrawn` stays excluded and `quarantined` is not added.** The
      drain's write has already put the object under the key and named it (T728), and it validates
      the bytes before it marks; a row that ends `stored` with `validated_by` set is the true
      record, and the alternative leaves a row that names an original replay while reading as lost,
      which no claim selects and the upload route refuses as `replay_held`. `_mark_stored_by_drain`
      matches the row while it is `downloading`, as before, or while it is `expired`, `failed` or
      `unavailable` and `object_key` equals the key the drain wrote, adopted or, on a resumed
      reclaim, read from the row. That the bytes validated are the bytes the row names follows from
      ordering, not from that equality: in `_process_one` the mark runs only after the drain's own
      metadata commit named its object, which nothing clears, and a resumed reclaim re-hashes the
      object against the row's `zip_sha256` before it validates. The key is one per pair
      (`replay_object_key`), the same for the drain and an upload, so the equality cannot tell which
      writer named it; it is a guard against a row naming any other key, which no writer produces.
      `withdrawn` is a refusal made on purpose (`withdraw_refused_near_deadline`), not an outcome of
      an attempt, so a late write never reverses it; it still names the object, as T728 requires.
      `stored` already ends the row and `quarantined` is T673's re-validation, so neither is added,
      and T673's `_mark_stored` call is unchanged. Nothing the other drain recorded is retracted:
      its run keeps its `expired_total`, `failed_total` or `unavailable_total` while this drain's
      run counts `stored_total`, and in the `expired` case its `expired_capture` alert stays until
      acknowledged and `scripts/checks/capture_audit.py` fails over that run's window for a capture
      that is `stored`. That is the safe direction, a loss over-reported rather than hidden. **Not
      decided here:** the drain's other late write, its `quarantined` mark after a failed
      validation, still matches only `downloading` and leaves such a row naming an unvalidated
      object (T747). **Tests, each red before:** for each of `expired`, `failed` and `unavailable`,
      a row another drain ended while this drain was past its claim, then this drain's blob metadata
      commit and `stored` mark, ends `stored` with `validated_by` set and the drain's object named.
      **Contrast:** a `withdrawn` row stays `withdrawn` and names the object; a row naming another
      key than the drain's is not marked, the defensive guard above; a `stored` row is not
      rewritten; a `quarantined` row naming the drain's key is not rewritten and counts no
      `stored_total`
- [x] T741 Close what #155's review and #148's review (N4) left on T730 (filed 2026-10-17; #155
      merged at its first commit). **Erasure:** the keys no row names are deleted before the keys
      rows name, both passes concurrently under one bound, so a kill or a delete error during the
      first pass leaves no row naming a deleted original; the duration bound in `erase_account`'s
      docstring counts both passes. **Upload:** `record_manual_upload`'s update of an existing row
      also requires `object_key IS NULL` and a status other than `stored`, and `upload_replay`
      refuses `replay_held`, writing nothing, when that update matches no row, when the held object
      is gone before it is read, and when a twin upload's insert wins the pair's uniqueness. A held
      object with the upload's SHA-256 is adopted as `manual` even when the drain wrote it: refusing
      it under a terminal row, or a pair with no row, would leave it unnamed until erasure, and
      `manual` records only that the user supplied those bytes (FR-033). **Tests, each red
      before:** the drain adopting the object and marking the row `stored` between the route's read
      and its write leaves the row `automatic`; the drain having committed only its blob metadata
      is refused; the unnamed objects go before the named ones; the named deletes run concurrently.
      **Contrast:** a retry over an object no row names still ends `stored`, `manual`
- [x] T742 Refuse an erasure whose object deletes cannot fit the API function's limit (filed and
      decided 2026-10-17 by the user, the most conservative of the options after T741: refuse
      rather than bound the deletes or accept the risk). Neither how many keys an account's pairs
      accumulate nor an R2 `DeleteObject`'s latency is measured, and a kill during the named pass
      leaves rows naming originals already deleted. `erase_account` counts the waves of both passes
      at the real delete width before the first `DeleteObject`; over a budget of 37 waves (about
      7.4 s at an assumed 200 ms per delete) it answers `503` `erasure_too_large`, deletes nothing,
      rolls the erasure back, and records the request on a `data_requests` row of kind `erasure`
      left uncompleted, written through its own session. No alert kind is added: severity 1 is
      reserved by constitution I and a new kind is a migration. Lifting the refusal needs the
      largest account's key count measured, or a design that deletes outside the request. Measured
      once, 2026-10-17, read by the user in production: the largest account's erasure touches 79
      keys, at most 17 waves at the narrowest width, so no account is refused today; the count
      grows with every match an account plays.
      **Tests, each red before:** an account over the budget is refused with every object still
      listed, the account and its `match_players` unchanged, and the request recorded.
      **Contrast:** an account exactly at the budget is erased as before

- [x] T706 Unstick an analysis whose lease expired (filed 2026-10-08; decided by the user the same
      day). Match 511523321's row stayed `running` from the 2026-10-05 crash until a manual
      `POST`: `GET /api/matches/{game_id}` serves `running` without reading `lease_expires_at`,
      the match page polls while `running` and never sends the `POST` that would re-claim it, so
      003's "the next person to open the match takes it" was never implemented. The data model
      already defines `running` as a lease held and unexpired. **Server**: serve a `running` row
      whose lease has expired as `queued` in the `analysis` object. **Client**: on `queued`, the
      match page sends `POST /api/analyze` once per page view, not on every poll. **Limit**: a
      `POST` for a match whose analysis row exists in `queued` or `running` does not count
      against the per-user daily limit (FR-040): it re-claims or joins, it starts nothing new;
      every admission gate still applies. Tests, each red before: an expired-lease row is served
      `queued`, a live one `running`; the page sends exactly one `POST` across several `queued`
      polls and none while `running`; a re-claim or join leaves the counter unchanged while a
      first request still increments it. Update `packages/design-system/specs/analysis-timeline.md`
      §5 if it describes the polling, keeping that file's line count (its lines are cited)
- [x] T707 Promote a knowledge snapshot for build 185872. Knowledge snapshots existed for build
      180059 only (`packages/knowledge/snapshots/`). Delivered (amended 2026-10-08 after #126's
      review): the snapshot is promoted from aoe2techtree commit 3bb43b1, a direct import
      (research.md D3), vendored as a second pack beside the first; it models no civilisation, and
      names resolve through `query.name` for build 185872. An analysis still shows identifiers:
      putting names on the page is T709
- [x] T708 Give `AnalysisTimeline`'s event lists a text colour. In
      `packages/design-system/src/composites/AnalysisTimeline/index.tsx` only a resolved name
      carries `text-text-primary`; the surrounding text, the times and an unresolved identifier
      inherit no token, and in the dark theme they render dark on dark (seen in production on
      match 511523321, 2026-10-08). Set the list's colour from a design-system token, check the
      unresolved-identifier style against the contrast table, and record that no baseline can
      move: Storybook's preview wraps every story in the primary ink, so the stories never showed
      the defect (#126's visual job: 478 passed, none moved); the unit test is the guard (T710)
- [x] T709 Show names on the analysis page. Found closing T707 (2026-10-08): no stage maps an id to
      a name for any build — the stored document carries ids only, and
      `apps/web/src/features/analysis/mappers.ts` renders every technology, unit and building
      unresolved under 003's FR-043a ("until such a table ships"). The knowledge snapshots are that
      table. Resolve names from the snapshot the document's own identity names (never the nearest
      one, FR-027), serve them beside the stored document from `GET
      /api/matches/{game_id}/analysis` without changing the stored bytes or its digest, and render
      them; an id the snapshot does not name stays unresolved as today. Tests: a build 185872 and
      a build 180059 document each show Feudal Age, Castle Age and House; an id outside the
      snapshot stays unresolved; the stored object is byte-identical before and after
- [x] T709a Close #160's review (`reviewer` REJECT 2026-10-17 on T709). **Request path, decided by
      the user 2026-10-17**: names are resolved on the request path, and the rule says so rather
      than being stepped around. Amend `specs/006-replay-analysis-foundations/plan.md`'s "no
      request-path work" constraint and check 2 of
      `tests/architecture/test_feature_006_boundaries.py` with that decision: put
      `apps/analyzer/src/aoe2stats_analyzer/names.py` in `_REQUEST_PATH_CODE`, and grant it, and
      only it, the named `aoe2stats_knowledge` symbols it imports, so any other knowledge or truth
      import from it fails; drop the "for the reason `extract.py` is" justification and the test
      asserting `names.py` is outside the set. **Register, decided by the user the same day**: the
      served `knowledge_names` leaves are published data (FR-006, FR-007). Give them an entry in
      `packages/core/src/aoe2stats_core/truth/register.toml` (tier derived, requiring knowledge,
      the snapshot as source), regenerate `REGISTER.md` from it, and make the check that fails a
      publishable field with no entry reach the served shape, not only the stored body; amend
      `specs/006-replay-analysis-foundations/contracts/analysis-document.md`'s names section to
      say so. **Isolation**: a subprocess check, beside the staleness one in
      `apps/api/tests/test_engine_isolation.py`, that imports `aoe2stats_analyzer.names`, calls
      `with_names` on a named document and asserts no native engine, `aoe2stats_providers` or
      `aoe2stats_ingester` module is loaded. **Demoted snapshot**: a test whose identity names a
      snapshot that is installed but not promoted for its build and asserts names resolve from it
      (SC-005). **Prose made false by T709**: `apps/api/src/aoe2stats_api/routers/analysis.py`'s module docstring ("no
      `apps/analyzer`") and "served verbatim"; the boundary file's "exactly one module, from exactly
      one file" and "with one exception"; `test_engine_isolation.py`'s "the one exception"; the
      T709 sentence of `docs/data-sources.md` §6 dated under "Assessed 2026-10-08" (date it, keeping
      the section's line count). **Client**: `readKnowledgeNames` ignores a block whose snapshot
      does not match the document's `identity.knowledge`. **Plants, each red before**: a second
      knowledge import added to `names.py` fails check 2; a served `knowledge_names` leaf with no
      register entry fails the register check; a `names.py` that resolves through
      `load_resolvable_snapshots` fails the demoted-snapshot test; a `names.py` import that loads
      `aoe2stats_providers` fails the isolation check; a block whose snapshot digest differs from the
      identity's renders no name. **Contrast**: the T709 tests unchanged
- [x] T709b Close #160's re-review notes (`reviewer` APPROVE 2026-10-17 on T709a, three
      non-blocking notes, none live). **Grant by symbol, not module** (N1): two of the seven grants
      to `apps/analyzer/src/aoe2stats_analyzer/names.py` in
      `tests/architecture/test_feature_006_boundaries.py` are whole modules (`query`, `gaps`), which
      reach every attribute the guard's own comment refuses a plain `import` for. Import the
      symbols `names.py` uses by name (`query.name`, `query.EntityRef`, the unresolved-source constant,
      `gaps.KnowledgeGap`) and grant those instead, so every sentence that says "symbols" is
      true; correct the count wherever it is stated. **Dependency direction** (N2):
      `apps/analyzer/src/aoe2stats_analyzer/extract.py` imports the names method id and version
      from `names.py` at module scope, so the analysis path loads request-path code for two
      constants; move them to a module both already depend on. **Contract example** (N3): the
      names section of `specs/006-replay-analysis-foundations/contracts/analysis-document.md`
      shows a `provenance` covering two of the five data its block holds, against the rule it
      states; make the example complete. **Plants, each red before**: a `names.py` calling a
      `query` function it was not granted (for instance `query.cost`) fails check 2, which passes
      today. **Contrast**: the T709 and T709a tests unchanged
- [x] T709c Serve the snapshot names as labels, not as vendored markup (filed 2026-10-17 after
      #160 merged; ported from the superseded #159, then made precise after review). The vendored
      names carry the source's line-break markup (`"Town<br>\nCenter"`, `"Circum-<br>\nnavigation"`,
      `"Counter- weights"`; over 300 per snapshot), and `apps/analyzer/src/aoe2stats_analyzer/names.py`
      served them as stored, so the page printed `<br>` literally. Clean the label where the block
      is built, never in the frozen snapshot data; `query.name` keeps returning the vendored value.
      **The rule**: a hyphen directly after a letter, followed by a run of line-break tags and
      whitespace and then a lower-case letter (any Unicode lower-case letter), joins the word, the
      hyphen and the whole run going (`Circum-<br>\nnavigation` is `Circumnavigation`); the same
      hyphen followed by such a run and then any other character keeps the hyphen and drops the run
      with no space (`Man-at-<br>\nArms` is `Man-at-Arms`); a hyphen not directly after a letter is
      left alone (`Foo - bar` stays); every other break becomes one space, whitespace collapses,
      the label is trimmed; a label with no letter or digit left is
      not served, as an unresolved id is not. The served value changes, so the names method is
      `knowledge-snapshot.name@2` (not yet released when the rule was made precise, so it stays),
      and the rule is stated in the `method` text of `names.technology`, `names.unit` and
      `names.building` in `packages/core/src/aoe2stats_core/truth/register.toml` and in the
      contract's names section. **Tests, each red before**: building 109 is served as
      `Town Center` and a real recording's labels carry no markup; a sweep over every name in
      every snapshot finds no `<`, no hyphen-after-a-letter-then-space, no stray whitespace and no
      empty label; markup-only names (`<br>`, ` <br/> `, `-<br>`) are not served; `clean_label`
      cases on the deciding clause (`Man-at-<br>\nArms`, `Anti-<br>\nCavalry`, `Foo - bar`,
      doubled breaks, and the Unicode cases `Anti-<br>\nécole` and `Anti- Élite`) fail if the
      lower-case lookahead or the after-a-letter condition is removed. **Guards**: the set of names
      across every snapshot the join applies to equals
      exactly `{"Circum-<br>\nnavigation", "Counter- weights"}`, decided by the code's own
      `_unwrap` and not by a second pattern (a planted `Anti-<br>\nécole` fails it), and its
      message says a new entry needs a person to confirm it is a word-wrap and not a compound
      (`Anti-<br>\ncavalry`); a name that cleans to nothing is absent from the block, its kind's
      datum is absent from the block's
      `provenance`, and the served-shape rules 1 to 4 find no violation. **Contrast**: compound
      hyphens stay (`Double-Bit Axe`, `Two-Handed Swordsman`, `Man-at-Arms`), the same id with a
      normal name is served with its datum, and the snapshot itself still returns the vendored name
- [x] T707a Close #126's review (`reviewer` REJECT 2026-10-08 on T707). **Frozen prose first**:
      `packages/knowledge/snapshots/aoe2techtree-185872/effects.toml`'s header is covered by the
      digest and says the snapshot resolves the labels an analysis shows and a
      civilisation-neutral baseline; neither holds (T709; every rule query refuses an unmodelled
      civilisation). Reword it to what holds and recompute the digest (no analysis names this
      snapshot yet), and the same false cause in `snapshot.toml`'s header and both new test
      docstrings. **Validation record**: name the publisher's release date (2026-09-22) and the
      commit's authored (2026-09-11) and committed dates in `checked_against`, and add to
      `not_checked` that the data matching the released build was not verified and that no FR-030
      value validation was done. **Re-derivation**: parametrise the re-derivation test over every
      promoted snapshot the loader finds (the stub excepted), resolving its pack from
      `source_version` through each `MANIFEST.json`, rather than a hand-kept list. **Pack checks**:
      fail on a pack directory with no `MANIFEST.json`, on two packs pinning one commit, and on a
      pack no snapshot's `source_version` names; correct the budget comment, which claims to
      exclude a third copy it admits. **Docs**: `docs/data-sources.md` §6 says only what is true
      today (names resolve through the query, not on the page; the six modelled civilisations as
      T652m corrected them; 180059 is no longer the only fixtures' build), with the 2026-10-08
      assessment date on the second pack's claims; amend `specs/006-replay-analysis-foundations/contracts/knowledge-base.md`'s on-disk
      and licence-gate sections by hand: a newer revision goes beside, never over, and a pack is
      found by `source_version`. `normalise_pack`'s pack name has no default. Plants, each red
      before: a snapshot naming pack A's commit but derived from pack B; a pack directory without
      a manifest; a duplicate pin; an orphan pack. Third review (2026-10-09): the digest-covered
      header carried two clauses that turn false on deploy ("no published analysis names this
      snapshot", "no page shows a name"); both are cut and the digest recomputed, the same claim is
      dated in `snapshot.toml` and both test docstrings, and the contract says a snapshot finds its
      pack by `source_version` rather than that every lookup does
- [x] T710 Make the visual tests able to see a missing text token. Found closing T708
      (2026-10-08): `packages/design-system/.storybook/preview.tsx` wraps every story in
      `text-text-primary`, so a component whose text carries no token of its own renders correctly
      in every story and baseline, and wrong wherever the application does not supply that ink —
      `AnalysisTimeline`'s lists did, on the match page, in production. Either stop the preview
      supplying ink, so a story shows what the component itself declares, or add a check that
      refuses text without a token; decide which, list every component the change exposes, and
      say which baselines move.
      **Decided 2026-10-17 by Claude on the user's delegation: the preview stops supplying ink.**
      The decorator keeps `bg-background`, which the app's `Page` paints, and drops
      `text-text-primary`, which nothing in the app supplies (neither `RootLayout` nor `Page` sets
      a text colour), so a story renders the ink the app renders. A check was rejected: inheriting
      ink is a contract for some components (`civilisation-icon.md` §5; `country-flag.md`, "the
      name sets no colour of its own"), so it would need an allowlist and would have to follow a
      class through `cx()` and props; and four of the defects below carry `text-secondary`, a
      token-shaped class that generates no CSS, which a check for a present `text-*` class
      accepts (T743). **Limits**: the comparator judges change, not correctness, so a new story's
      first baseline takes whatever it renders; the browser's default black differs visibly from
      the token ink in the dark theme only; a short span can stay under `maxDiffPixelRatio`.
      **Exposed**, measured by rendering all 647 stories with the decorator's and the page's ink
      replaced by a sentinel colour and transitions off: 142 stories before (light theme, 375 and
      1280), none after (both themes, 375, 768 and 1280).
      Components lacking a token, given one: `MatchRow`'s unknown outcome, unknown team result
      and zero rating change and `MatchDetailPanel`'s unknown result (`text-secondary` to
      `text-text-secondary`); `MatchRow`'s card, whose civilisation name (`CivilisationIcon`
      inherits) and map name inherited no ink below `xl` (`text-text-primary` on the card's root);
      `MapThumbnail`'s resolved name (`text-text-primary`, `map-thumbnail.md` §5); `Panel`'s body
      and footer (`text-text-primary` and `text-text-secondary`, `structural-tier.md`'s `Panel`
      tokens). Their stories now supply the caller's ink: `CivilisationIcon` and `CountryFlag`,
      which inherit by contract, and `Tooltip`, whose trigger renders the caller's child. Story
      markup given ink: `Section`, `Badge`, `PlayerColourSwatch`, `CountryFlag`, the Foundations
      pages and the `Plants` and `ThemePlants` fixtures. The card's ink is what every reviewed
      baseline showed and what `match-history.md` §6 and §12.7 name; `civilisation-icon.md` §5
      and `match-history.md` §8 still put those names at `text-secondary` in a 375 meta line, and
      are amended to agree, each keeping its line count. `specs/README.md`'s citations of
      `Section` and `CivilisationIcon` story lines are repointed. A unit test fails if the
      preview's decorator markup carries a text colour again. **Baselines**: none moved. #161's
      visual job passed and its merge carries no baseline image: the ink each defect gained is a
      short span, which stays under `maxDiffPixelRatio` (the limits above); T743 refuses the
      undefined class behind four of them
- [x] T743 Refuse a class the design-system stylesheet does not define (filed 2026-10-17 from
      T710). `text-secondary` was the ink of an unknown or neutral fact in four places, three in
      `packages/design-system/src/composites/MatchRow/index.tsx` and one in
      `packages/design-system/src/composites/MatchDetailPanel/index.tsx`. Tailwind emits nothing for
      it (the colour role's utility is `text-text-secondary`), so the text took whatever ink
      surrounded it. `scripts/checks/token-scale.mjs` refuses raw values and never asks whether a
      class exists, and each unit test asserted `toContain('text-secondary')`, which
      `text-text-secondary` also satisfies. Fail the build on a class in the package's component
      source that the built stylesheet does not define, and replace substring class assertions in
      the package's tests with whole-class ones. Plant, red before: `text-secondary` in a
      component. Contrast: `text-text-secondary` and a variant-prefixed class such as
      `group-hover/row-link:underline` pass. `scripts/checks/built-css.mjs` already reads the built
      stylesheet.
      **Decided 2026-10-17 by Claude:** `scripts/checks/defined-classes.mjs` asks Tailwind's design
      system, compiled from `packages/design-system/tokens/tailwind.css` (the stylesheet the build
      compiles), rather than searching the built file: it needs no build and no selector escaping,
      and whether the build scans a file at all stays `built-css.mjs`'s question. A token of a
      string literal in component source is a hit when it parses as a utility that emits nothing,
      when an unknown variant precedes a utility that compiles or names a value, or when it starts
      with a prefix of the stylesheet's own `@utility` families (`type-`, `icon-`) and parses as
      nothing. Skipped: a bare functional root (`to`, `text`), an equality operand or `case` label,
      and a member of a closed set of string literals none of which compiles (`Tooltip`'s
      placement). An unknown root such as `txt-secondary`, and a bare root whose default the theme
      removed, pass. 336 class assertions
      in 36 test files are whole-class (`toHaveClass`); a single-class negative no longer forbids
      the class under a variant, as its substring did. A negative that forbade a family, and
      `Link`'s two whose test says "never", are a check over class tokens
- [x] T706a Close #127's review (`reviewer` REJECT 2026-10-08 on T706). **Lease shorter than the
      run**: the claim's lease is the run budget (240 s) while the function may run 300 s, so a
      live run reads expired for its last minute and T706's page now re-claims it: a second fetch,
      a second parse, two publishes. Claim with the lease length the configuration already
      declares for this (`.env.example`'s lease key, read by nothing today), and test that a
      run's lease never expires while its function may still be running. **Retries without a
      bound**: `attempts` is incremented and never read, so a recording that kills its
      invocation every time is re-claimed, uncounted, on every page view, each time fetching from
      the source. Enforce the bound 003's data model states: a claim that would exceed the
      configured maximum ends the row `failed` with a fixed reason instead, read from a new
      required setting, `ANALYSIS_MAX_ATTEMPTS` (no default, declared where every setting is,
      `.env.example` sizing it).
      Test the boundary. **Refused takeover**: when the page's automatic `POST` on `queued` is
      refused (admission 409, 401, network), the page keeps polling with no message; show the
      refusal and stop polling, with a test, and correct the comment that says it is read back
      through the polls. **Prose**: cut "starts nothing new", "never a free analysis",
      "over-counts, never under-counts" and "bounded" to what holds (a takeover re-fetches; the
      narrow overlap of a live run publishing before an uncounted request can recompute), and
      make the uncounted-path admission test exercise all three gates or name the one it proves
- [x] T706b Close #127's second review (`reviewer` REJECT 2026-10-09 on T706a; every earlier
      finding closed). **Honest copy for an exhausted row**: a row the attempts bound ends `failed`
      is shown "The recorded game could not be parsed", which is false when the attempts were spent
      on source throttles or outages that never fetched it. Give `AttemptsExhausted` its own copy in
      `AnalysisTimeline`'s failed state, keyed on the error class, that claims no parse; keep
      `packages/design-system/specs/analysis-timeline.md`'s line count (its lines are cited); correct
      `apps/api/src/aoe2stats_api/routers/matches.py`'s failed-reason docstring, which says a
      `failed` row carries the recording's own parse failure. Test that the exhausted copy shows and
      the parse sentence does not. **Polling after a refused takeover**: the page stops polling
      whenever a takeover was refused, whatever the state; stop only while the state is `queued`, so
      a row another viewer takes over (`running`) is polled again, and correct the comment that says
      the row stays `queued`. Test: refusal, then `running`, then polling resumes
- [x] T706c Close #127's third review (`reviewer` REJECT 2026-10-09 on T706b; every earlier finding
      closed). The web client now requires `analysis.error_class`, and the visual suite's match-page
      fixture (`tests/visual/fixtures/suite-scenarios.ts`, `analysisSummary()`) builds the object
      without it, so every stubbed match page renders its load-error branch and the PR's visual job
      is red. Add the field to that fixture and to every other analysis-object fixture under
      `tests/` and `apps/web`, and run the visual suite on the changed stories and routes, with no
      baseline moving. The exhausted copy says "several times", which a configured maximum of 1
      makes false: say it was interrupted and is not retried, with no count, keeping
      `packages/design-system/specs/analysis-timeline.md`'s line count
- [x] T746 Model civilisations for build 185872 in a second knowledge snapshot (filed 2026-10-18
      from T665). `packages/knowledge/snapshots/aoe2techtree-185872/` models none, on purpose (its
      `effects.toml` header): `civilisations_modelled` is empty and there is no `[[civilisation_id]]`
      table, so every civilisation-qualified query on a current-build recording is a gap. Measured
      in production on 2026-10-18: match 512927942's published analysis carries 1980 gaps, every
      one `civilisation-not-modelled`, over raw civilisation ids 2, 4, 5, 10, 49 and 51. Ordered
      army cost, resources spent, ordered production time and modelled age-up arrival are blocked
      for every participant. **To decide first, because the contract forbids both obvious routes**:
      FR-025 forbids editing the promoted snapshot, and `_promoted_snapshot_for` in
      `packages/knowledge/src/aoe2stats_knowledge/snapshot.py` raises `SnapshotError` when two
      promoted snapshots describe one build, so neither an in-place edit nor a second promoted
      snapshot can ship today. Recommended: the new snapshot names the digest it supersedes,
      resolution by build skips a superseded snapshot, and a superseded snapshot stays loadable by
      identity, so `reproduce` on an analysis published under it still returns that analysis's
      bytes (SC-005). Amend `specs/006-replay-analysis-foundations/contracts/knowledge-base.md`
      ("Promotion", "Resolution by build") by hand in the same change. **Scope**: the two
      civilisations the committed build 185872 recording seats (raw ids 23 and 37,
      `tests/fixtures/replays/AgeIIDE_Replay_511523321.canonical.json`), plus every civilisation
      `aoe2techtree-180059` models. Each is transcribed again from the
      `packages/knowledge/packs/aoe2techtree-3bb43b1/` pack's English strings and checked against
      build 185872's published notes, never copied from
      `packages/knowledge/snapshots/aoe2techtree-180059/effects.toml`. The raw-id table is taken
      again for this build from the source `docs/data-sources.md` §6 assesses, not carried from
      180059, because this build adds civilisations. An id that source does not name, or a bonus the
      notes change in a way the pack strings do not show, stops the task with a report; it is never
      guessed. Raw ids 5, 10, 49 and 51 are out of scope, and the aggregate gap report stays their
      backlog ([research.md](./research.md) **D5**). **Tests, each red first**:
      `test_each_committed_recording_reports_zero_blocking_gaps` in
      `packages/knowledge/tests/test_coverage.py`, parametrized over the third committed recording,
      `xfail(strict=True)` until the snapshot is promoted; build 185872 resolves to the new
      snapshot; an analysis identity naming the superseded snapshot still reproduces byte for byte;
      and `packages/knowledge/tests/test_knowledge_snapshot_185872.py`'s names still resolve.
      **Done 2026-10-18**: `packages/knowledge/snapshots/aoe2techtree-185872-civilisations/`
      supersedes the first by digest (`[snapshot].supersedes`) and models eight civilisations (raw
      ids 2, 4, 8, 9, 23, 26, 33, 37); the first is unchanged and reproduces by identity. The third
      recording keeps 5 blocking gaps, asserted by set equality as the second's are: building 490's
      three (the known hole), Slavs' Castle cost and Sicilians' Donjon production time. Those two
      bonuses are refused, not guessed: the pack strings name no wood amount for Detinets and no
      building list for "Fortifications". Build 185872 analyses published under the first snapshot
      read as stale and are recomputed under the second
- [x] T747 Decide what a drain's late `quarantined` mark does to a row a concurrent drain ended
      (filed 2026-10-18 from #174's review, B1). T740 widened the drain's `stored` mark only. When a
      drain's claim goes stale while it is still running, a second drain can end the row `expired`,
      `failed` or `unavailable`; the first drain's metadata commit then names its object on the row
      (T728), and when its validation fails (an engine error, the wall-clock cap, or on a resumed
      reclaim a missing object or a checksum mismatch) `_quarantine` matches nothing, because it is
      guarded on `downloading`, raises no `validation_failed` alert, and the row keeps the ended
      status while naming an object with `validated_by` null. No claim selects it, T673's
      re-validation selects only `quarantined`, and the upload route refuses it as `replay_held`.
      Both paths reach it: `_process_one` and `_resume_reclaim`. Not reachable on Phase 1 hosting,
      for the reason T740 gives. To decide first: whether the drain's `quarantined` mark also
      matches those three statuses when the row names the drain's key, keeping `withdrawn` excluded,
      and whether it then raises `validation_failed` over an `expired` row whose `expired_capture`
      alert is already raised. **Decided (2026-10-18, by Claude, the user having asked for T747 to
      be implemented).** **Yes to both: the drain's `quarantined` mark also matches `expired`,
      `failed` and `unavailable` when the row names the drain's key, and it then raises
      `validation_failed` as any quarantine does.** `withdrawn`, `stored`, `quarantined` and
      `pending` stay unmatched. This is T740's widening applied to the drain's other
      post-validation mark: `_quarantine` takes the key `_process_one` wrote or adopted, or the key
      `_resume_reclaim` read from the row, and `_mark_quarantined` gains the same
      `also_if_ended_naming` match as `_mark_stored`. T673's re-validation call leaves it unset. The
      row's status then records this drain's validation outcome rather than the other drain's ended
      attempt. The write replaces `status` and `last_error` only; the other drain's alert and its
      run's counter stay, so over an `expired` row its `expired_capture` alert stays beside the new
      `validation_failed` alert. **Tests, each red before:** for each of `expired`, `failed` and
      `unavailable`, a row another drain ended while this drain was past its claim ends
      `quarantined` with the drain's reason and one `validation_failed` alert, through
      `_process_one` (an engine error, the wall-clock cap) and `_resume_reclaim` (an engine error,
      a missing object, a checksum mismatch); over `expired`, both alerts are present.
      **Contrast:** a `withdrawn` row, a `pending` row, a row naming another key, a `stored` row and
      an already-`quarantined` row are not rewritten and raise no alert
- [x] T749 Recapture the baselines T710's ink fix left under the comparator's tolerance (filed
      2026-10-18 from #172's baseline regeneration). T710 gave `MatchRow`'s unknown outcome, unknown
      team result and zero rating change and `MatchDetailPanel`'s unknown result
      `text-text-secondary` in place of `text-secondary`, which generates no CSS, and recorded that
      no baseline moved: the ink each gained stays under `maxDiffPixelRatio`. The committed
      baselines of those stories therefore still show the inherited `text-primary` ink, and a
      regression back to it passes the comparator. Measured 2026-10-18 by
      `scripts/checks/baseline-regeneration-diff.mjs` in `baselines.yml` run 39114001064: 36
      captures moved by 511 to 4,160 pixels, every width and theme of
      `composite-matchrow--null-result`, `composite-matchrow--unknown-outcome`,
      `composite-matchrow--list-all-outcomes-unknown`, `composite-matchrow--eight-player-match`,
      `composite-matchdetailpanel--null-result` and `composite-matchdetailpanel--mixed-result`.
      **Done** when those 36 baselines are recaptured on CI and the regeneration commit keeps no
      other capture that this cause does not explain. **Done 2026-10-18**: `baselines.yml` run
      39119237720 moved exactly those 36 beyond noise; its other 119 rewrites, all at or under
      100px, are reverted

---

## Phase 8: Every civilisation (filed 2026-10-18, owner's arbitration)

**Purpose**: the knowledge base answers every cost, time, producing building, age requirement and
availability, for every civilisation the tool supports, on every build a promoted snapshot
describes, with no blocking gap (FR-022a, amended; spec Clarifications, Session 2026-10-18). After
T746 the current build models eight civilisations and build 180059 six. What closes the rest:
FR-022c's source rule, an alias table for identifiers the pack does not name (FR-022d), extensions
to the effect model so that substitutions, unlocks and match-state conditions are rules rather than
refusals (FR-022e), an availability that reads each civilisation's own tree, and transcription in
batches of twelve civilisations, each batch a snapshot that supersedes the previous one
(`specs/006-replay-analysis-foundations/contracts/knowledge-base.md`, "Supersession"), so
production gains each batch as it is promoted. A value no source an agent may read states goes to
the owner's sheet, [owner-readings.md](./owner-readings.md), and a later snapshot closes it; it is
never guessed.

**Numbering**: Phase 8 starts at T760. 005's open branch already uses the ids just above T749, and
007 numbers its tasks in the eight-hundreds; the gap is there so that neither collides with this
phase.

**What every Phase 8 implementer must know**:

- **Transcription follows T746**: every new row from the English strings of the pack the snapshot
  derives from, checked against the release notes of the build it describes, each selector resolved
  from that snapshot's `rules.json` and recorded in `validated_by`. A row of an earlier snapshot of
  the **same build and the same pack revision** is carried byte for byte, because it was read from
  the same strings; a row of another build or pack is read to learn the file's shape, never copied,
  except under T773's carry rule.
- **A class name is resolved, never guessed.** "Infantry", "Gunpowder Units", "Warships" and the
  like are not keys of `rules.json`. Members come from what the pack's strings state, or from where
  the pack says an entity is produced, and the list and what it was read from go in `validated_by`.
  A member the pack does not settle goes to the owner's sheet, and its row stays `modelled = "no"`
  until the answer lands.
- **An unstated amount follows FR-022c, in order**: the pack's strings (a technology's own help text
  sometimes sizes what the civilisation text does not); the publisher's notes for any build, which
  an agent may read; then the owner's sheet. The Fandom wiki is the owner's to read, never an
  agent's (`docs/data-sources.md` §6).
- **Done means T765's test passes for the civilisation without its `xfail`**, with every blocking
  gap it keeps being an open row of the owner's sheet, enumerated under FR-022b.
- **A batch snapshot's label states the build and how many civilisations it models** —
  `aoe2techtree-185872-civilisations-20` — so that the chain reads in order without opening
  `snapshot.toml`.

- [ ] T760 [P] [US2] Record FR-022c's sources in `docs/data-sources.md` §6, the living home of a
      source's scope. **`aoc-reference-data`**: its "Scope" names civilisations only; widen it to
      the `objects` table (identifier to display name for units and buildings), read 2026-10-18 in
      its Definitive Edition dataset (dataset 100), first read for the gate family. Correct "Coverage" ("it carries no
      Relic ids at all"): each `civilizations` entry carries an inner `id`, and on 2026-10-18 it
      agreed with every identifier `apps/api/src/aoe2stats_api/civilizations.py` holds, differing
      only in spelling one name (Maya, Mayans); record that agreement as what was measured, not as a
      statement of what the field means, which the source does not document. Reconcile §1, "Ids
      45-60 (T070i)", in the same change: its 2026-09-27 comparison ("46 Achaemenids where the table
      has 45") read the dataset's keys, which are the replay space, not the inner `id`; say so, and
      say which of its eleven unmeasured ids the inner `id` now corroborates. The licence ruling is
      unchanged. **A new subsection, "The running game, read by a person"**, in the section's seven
      headings: scope (the cost or time a tooltip shows for a stated civilisation), reliability
      (FR-030's strong form), update mechanism (a person, after each patch), version identifier (the
      build the game reports), coverage (the current build only), known limitations (one value at a
      time, no history, read by the owner), ruling (read and transcribe, recording who, when and
      where in the game). **Fandom**: its ruling gains that an agent may not read it. **halfon**:
      its "Ruling" gains that buildings 490 and 673 did not make it needed (research D3, amended).
      Docs only; no test
- [ ] T761 [US2] Resolve an entity identifier the pack does not name through a transcribed alias
      (FR-022d). A snapshot may carry `aliases.toml`, one `[[alias]]` per identifier: `kind`, `id`,
      `target` (an identifier of the same kind that `rules.json` names), `source_name` (the
      referenced source's name for it, verbatim), `source` and `read_on`. The loader refuses, with
      `SnapshotError`, an alias whose target `rules.json` does not name, an alias whose own `id`
      `rules.json` names, and two aliases for one identifier. The digest covers the file when it is
      present, and a snapshot without one keeps the digest it has, so every installed snapshot still
      verifies. Every rule query and `name` follow an alias to its target, and `Answer` says that it
      did. Amend `specs/006-replay-analysis-foundations/contracts/knowledge-base.md` ("On disk",
      "Identity and immutability", "Entity resolution") and
      `specs/006-replay-analysis-foundations/data-model.md` §6 by hand in the same change. **Red
      first** in `packages/knowledge/tests/test_aliases.py`, against an in-memory snapshot: building
      490 answers building 487's cost through an alias, and each refusal above. No promoted snapshot
      carries the file yet; T767's is the first. In the same change, correct what
      `packages/knowledge/tests/test_coverage.py` and `packages/knowledge/tests/test_normalise.py`
      say about 490 and 673 ("age-upgraded visual variants"; closable only by a second vendored
      source): a referenced source names both "Gate", and FR-022d closes them without vendoring
      anything. Their strict expectations stay until T767's snapshot closes them
- [ ] T762 [US2] Add the condition `controlled` to the effect model (FR-022e). The operand is a
      table keyed by a count; the count is how many of the entities `condition_entities` names the
      player controls, supplied by the caller in the query's `context`. A count above the table's
      highest key takes that key's operand, which is how a stated maximum is written; a count below
      its lowest key means the effect does not apply. A query that reaches a modelled `controlled`
      effect without the count raises `ContextRequired`, as `age` does, and the coverage pass treats
      that as modelled. Its first users are Saxons' Foot Soldiers discount and Cumans' additional
      Town Center in the Feudal Age; a bonus that does not fit it stops the batch with a report and
      does not widen it there. Amend `specs/006-replay-analysis-foundations/data-model.md` §6's
      `condition` row and `specs/006-replay-analysis-foundations/contracts/knowledge-base.md` ("The
      query surface") by hand in the same change. **Red first** in
      `packages/knowledge/tests/test_effects.py`: a synthetic effect at counts 0, 1, 4 and 5 against
      a table keyed 1 to 4; the raise without a count; a parse-time refusal of a `controlled` effect
      with no `condition_entities`
- [ ] T763 [US2] Answer `available_to` from the civilisation's own tree, and let an effect change
      it. Today it answers true for any entity that resolves, for every modelled civilisation
      (`packages/knowledge/src/aoe2stats_knowledge/query.py`, `_field_present`), although the pack
      carries each civilisation's tree and the normaliser drops it: `rules.json`'s `civilisations`
      is a list of names. The normaliser writes each civilisation's units, buildings and technologies
      from the `Unit`, `Building` and `Tech` lists of the pack's `data.json` `civs`, and
      `available_to` answers membership. Those lists name an upgraded unit, not the technology that
      produces it: measured 2026-10-18 on match 511523321, technologies 98, 100 and 222 were ordered
      and are in neither participant's `Tech` list. An upgrade technology is a member when the unit
      the pack's `unit_upgrades` table keys it under (its `ID` field) is; an ordered entity that
      membership still cannot place stops the task with a report. A change to the normaliser's
      output must not change an installed snapshot's re-derivation: the normaliser gains a version,
      `snapshot.toml` names the one a snapshot was derived with (absent means the first), and the
      re-derivation test derives each snapshot under the version it names. An effect may then set
      `available_to` (operation `set`, operand `true` or `false`, with any condition), so that a
      substitution, an unlock and a removal are rows: Sicilians' Donjon bullet, refused by T746 for
      want of exactly this, Folwark for Mill, Pastures for Farms, Harbors for Docks once
      Thalassocracy is researched. Amend data-model.md §6 (`field`, `operand`) and
      contracts/knowledge-base.md ("The query surface", "Civilisation qualification"), both under
      `specs/006-replay-analysis-foundations/`, by hand in the same change. **Red first** in
      `packages/knowledge/tests/test_query.py` and `packages/knowledge/tests/test_effects.py`: an
      entity outside a civilisation's tree answers false; an unconditional `false`; a
      `researched`-conditioned `false` before and after its technology; an `age`-conditioned `true`;
      a parse-time refusal of a non-boolean operand; every entity a participant of a committed
      recording ordered answers true for that participant's civilisation (building 490 through T761's
      alias once a snapshot carries it); and every installed snapshot still re-derives byte for
      byte
- [ ] T764 [US2] Let `produced_at` answer every building an entity is produced at, and let an effect
      add one: Goths' Anarchy (Huskarls at the Barracks), Huns' Marauders (Tarkans at the Stable),
      Italians' Condottiero at the Barracks, Mapuche Settlements training Spearmen and Skirmishers.
      The answer becomes an ordered sequence, the pack's building first. **Before changing the
      type, grep every consumer of `produced_at`** (the coverage pass, the register's
      `requires_knowledge`, the analysis document) and change each in the same commit. Amend
      data-model.md §6 and contracts/knowledge-base.md ("The query surface"), both under
      `specs/006-replay-analysis-foundations/`, by hand in the same change. **Red first** in
      `packages/knowledge/tests/test_effects.py`: an unconditional addition, a
      `researched`-conditioned addition before and after, and the pack's building staying first
- [ ] T765 [US2] Write the whole-pack coverage test (SC-007b) in
      `packages/knowledge/tests/test_whole_pack_coverage.py`. For each build's current snapshot
      (resolution by build, so a superseded one is skipped), parametrized by civilisation: every
      civilisation the snapshot's `rules.json` lists, every entity it names or aliases, every field
      a register datum requires, through the public query surface with no context, so that a
      conditional effect counts as modelled exactly as the coverage pass counts it. The blocking gaps
      for a civilisation must equal, as a set, that civilisation's open rows in
      [owner-readings.md](./owner-readings.md), held in the test as literal tuples that each batch
      edits by hand. Each civilisation not yet modelled is `xfail(strict=True)`, listed by name, and
      the batch that models it deletes its entry. Lands after T761 to T764, green, with every
      unmodelled civilisation of both builds marked. A civilisation the application's table names and
      no pack carries (the six Chronicles civilisations) is outside the test until T776 decides, and
      its docstring says so. If the run takes longer than 30 seconds, cache
      each snapshot's rules once per session; never sample entities
- [ ] T766 [P] [US2] Add Saxons, Varangians and Danes to
      `apps/api/src/aoe2stats_api/civilizations.py`: today their matches show the
      "Civilisation <id>" fallback. Their Relic identifiers were measured on 2026-09-27 by the
      Relic and aoe2companion join `docs/data-sources.md` §1 records (61 Saxons, 62 Varangians,
      63 Danes, recorded there as known-absent and "filed separately", which never happened), and
      `aoc-reference-data`'s `civilizations` inner `id` corroborates all three (FR-022c, read again
      by this task; T760 records that field's agreement with the table). Record both in the module
      docstring beside T070i's, and correct the docstring where it says that source corroborates
      nothing in this table. **Red first** in `apps/api/tests/`: each of the three resolves to its
      name
- [ ] T767 [US2] Model batch A on build 185872 in `aoe2techtree-185872-civilisations-20`, which
      supersedes `aoe2techtree-185872-civilisations`: Britons, Goths, Japanese, Chinese,
      Byzantines, Turks, Vikings, Mongols, Celts, Spanish, Aztecs and Mayans, with T746's eight
      carried. `rules.json` is derived again under T763's normaliser. The snapshot carries the first
      `aliases.toml` (T761): every identifier `aoc-reference-data`'s `objects` table names exactly as
      a pack entity, with or without an orientation qualifier in parentheses (each "Gate" to the
      pack's Gate, each "Palisade Gate" to its Palisade Gate), read again by this task. A differently
      named one (Fortified Gate, Sea Gate, City Gate, Paifang Gate, Trowulan Gate) is not aliased by
      name; if a committed recording carries one, it goes to the owner's sheet. Its `[[civilisation_id]]`
      table names every civilisation of the pack, from `aoc-reference-data`'s `civilizations` keys,
      each entry with what corroborates it, as T746's do. T746's four refused rows are taken again
      under FR-022c and the extended model: Sicilians' Donjon availability becomes a row (T763); the
      Detinets wood, Kamandaran and the Sicilians' "Fortifications" list are searched in the
      publisher's notes for every build since each bonus appeared, and each one still unstated
      stays an open row of [owner-readings.md](./owner-readings.md). **Tests, each red first**: T765
      passes for the twenty civilisations without their `xfail`; build 185872 resolves to the new
      snapshot and the superseded one reproduces by identity (SC-005); the third committed
      recording's strict blocker set in `packages/knowledge/tests/test_coverage.py` loses building
      490's three tuples, by set equality; its Detinets and "Fortifications" blockers (building 82's
      cost, building 1665's production time) stay unless the publisher's notes settle them. The
      Donjon's availability is informational and was never on that set
- [ ] T768 [US2] Model batch B on build 185872 in `aoe2techtree-185872-civilisations-32`, which
      supersedes T767's snapshot: Huns, Koreans, Italians, Hindustanis, Incas, Magyars, Portuguese,
      Ethiopians, Berbers, Khmer, Malay and Burmese. Magyars' Corvinian Army and Malay's Forced
      Levy replace a gold cost with "additional" food the strings do not size: FR-022c's order, then
      the owner's sheet. Khmer's bonus removes building prerequisites, a field the knowledge base
      does not carry (research D3); it is listed in the file's header as a bullet with no row, never
      written as a row. **Tests**: as T767's, for thirty-two civilisations
- [ ] T769 [US2] Model batch C on build 185872 in `aoe2techtree-185872-civilisations-44`, which
      supersedes T768's snapshot: Vietnamese, Bulgarians, Cumans, Lithuanians, Burgundians, Poles,
      Bohemians, Dravidians, Bengalis, Gurjaras, Romans and Armenians. Bohemians' Hussite Reforms
      replace a gold cost with a food cost the strings do not size, for the Monk and each Monastery
      technology: FR-022c's order, then the owner's sheet, one row per entity. "Available one age
      earlier" is an `age_requirement` row, never a reading of the tree's display links (research
      D3). **Tests**: as T767's, for forty-four civilisations
- [ ] T770 [US2] Model batch D on build 185872 in `aoe2techtree-185872-civilisations-56`, which
      supersedes T769's snapshot: Georgians, Shu, Wu, Wei, Jurchens, Khitans, Muisca, Mapuche, Tupi,
      Saxons, Varangians and Danes. Saxons' Foot Soldiers discount is a `controlled` row (T762).
      Then write the validation sample in [owner-readings.md](./owner-readings.md), "Validation
      sample": one value per civilisation of the pack, each the effect that changes the most
      entities, stated as the civilisation, the entity, the age, the technologies researched, and the
      value this snapshot answers, for the owner to read in the game. **Tests**: as T767's, for every
      civilisation of the pack; T765 then has no `xfail` left for build 185872
- [ ] T771 [US2] **Owner task (information).** Read each open row of
      [owner-readings.md](./owner-readings.md), "Open values", and each row of its "Validation
      sample", in the running game on the current build (a tooltip in a solo game or the scenario
      editor) or, for a value the game does not display, the Fandom wiki. Write, per row, the value
      read, where it was read, the build the game reported, and the date. Rows can be answered as
      they appear; each batch adds its own
- [ ] T772 [US2] Close the owner's readings on build 185872 in a snapshot that supersedes the last
      batch's: each open row becomes a modelled row whose `validated_by` cites the reading, and
      each validation-sample reading that differs from what the snapshot answered is recorded as a
      disagreement (FR-028), stored as the game's value (FR-022c), and its row corrected.
      The snapshot's `[validation]` names the strong form for each sampled row and the second
      reading for every other row. Promote once every row for build 185872 is answered or reported
      unreadable by the owner; a row reported unreadable becomes an FR-022b entry, held in T765 and
      in `packages/knowledge/tests/test_coverage.py` with where the owner looked. A reading that
      arrives after promotion waits for the next snapshot. **Tests**: T765's tuples for build 185872
      equal the FR-022b entries, by set equality, and are empty when there are none; the same holds
      for the third committed recording's blocker set
- [ ] T773 [US2] Model build 180059 in a snapshot that supersedes `aoe2techtree-180059`, every
      civilisation of that build's pack, `rules.json` derived again under T763's normaliser. **The
      carry rule**: a row of T770's snapshot is carried to build 180059 only where the
      bullet's string is byte-identical under the same key in both packs, every selector resolves to
      the same identifiers in build 180059's `rules.json`, and build 185872's release notes name no
      change to that bonus or to an entity it selects; each carried row's `validated_by` says so and
      names the source snapshot's digest. Every other row is transcribed from build 180059's pack
      strings. The aliases and the civilisation table are read again for this pack. Depends on T770,
      not on the owner's readings: T774 carries those back.
      **Tests**: T765 passes for build 180059 without `xfail`; the second committed recording's
      blocker set loses buildings 490 and 673 by set equality; build 180059 resolves to the new
      snapshot and the superseded one reproduces by identity
- [ ] T774 [US2] Close build 180059's open rows in a snapshot that supersedes T773's. Each
      reading T772 closed is carried back only under T773's three conditions, under research D4's
      discipline in reverse; a value it cannot reach stays an open row for build 180059, answered or
      reported unreadable as T772's are. Depends on T772 and T773. **Tests**: T765's tuples for
      build 180059 and the second committed recording's blocker set equal their FR-022b entries, by
      set equality, and are empty when there are none
- [ ] T775 [US2] **Owner task (verification).** After each promotion is deployed, read the
      aggregate gap report for that build: the `knowledge_gap_rate.py` step of `nightly.yml`'s
      `capture-audit` job, or
      `uv run scripts/checks/knowledge_gap_rate.py --window-days 1` against production. Record in
      [owner-readings.md](./owner-readings.md), "Production", the date and the count of blocking
      gaps per build. Once T772 and T774 are deployed, the count for
      builds 180059 and 185872 equals the FR-022b
      entries those builds keep, zero when there are none, for every analysis recomputed since
- [ ] T776 [US2] **Owner task (arbitration).** Decide whether the six Chronicles civilisations
      `apps/api/src/aoe2stats_api/civilizations.py` names are in scope. No vendored pack carries
      their trees, so including them means choosing a source for every entity they can build, under
      FR-022c. The decision is recorded in [spec.md](./spec.md), Clarifications, Session
      2026-10-18, and the tasks it needs are filed here
- [ ] T777 [P] Renumber the reconstruction from feature 007 to feature 008 everywhere it is named:
      007 is now the deployment-storage feature (`specs/007-shrink-deployment-storage/`, open as PR
      #176). `git grep -n -i 'feature 007'` lists the sites, among them
      `packages/core/src/aoe2stats_core/truth/register.toml`, whose readable view is regenerated
      with `uv run python -m aoe2stats_core.truth.register`, [spec.md](./spec.md),
      [plan.md](./plan.md), [research.md](./research.md),
      `specs/006-replay-analysis-foundations/contracts/register.md`, `docs/risks.md`,
      `docs/adr/0001-replay-parser.md` and `.claude/skills/replay-parsing/SKILL.md`. A Clarifications
      answer stays as it was spoken, followed by a bracketed note. **Test**: the register's view test
      passes, and `git grep -i 'feature 007'` names no reconstruction outside a dated note
- [ ] T778 Close Phase 8: update `docs/data-sources.md` §6, aoe2techtree's "Coverage", and
      `docs/risks.md`'s hand-transcription row to the coverage that now holds; run
      `uv run scripts/checks/spec_lint.py --feature specs/006-replay-analysis-foundations` and
      confirm it exits 0; then run the whole suite by exit code

## Dependencies and execution order

### Phase dependencies

- **Phase 1** depends on nothing and leads because its evidence expires. It is separately mergeable
  and should merge on its own.
- **Phase 2** depends on nothing in phase 1 in code, but T614's register entries cite T604's
  corrected section, so phase 1 lands first.
- **Phase 3** depends on phase 2 for the tier type only.
- **Phase 4** depends on phase 2 for the register's dependency graph (severity) and on phase 3 for
  the canonical stream (coverage).
- **Phase 5** depends on all four.
- **Phase 6** depends on phase 5.
- **Phase 8** depends on phase 7's T746 (the superseding snapshot and its chain). Inside it: T761
  to T764 before T765; T765 before T767; the batches T767 to T770 in order, because each
  supersedes the last; T772 after T771's answers for build 185872; T773 after T770; T774 after
  T772 and T773. T760, T766 and T777 depend on nothing in the phase.

### Within phases

Test tasks precede their implementers throughout. Where a test lands `xfail(strict=True)`, the two
may be separate commits. Where a task says the marker is deleted in the same change, they are one.

### Commit units

The smallest set of tasks that was ever simultaneously green. T609/T610 with T611 are one commit —
the test is written first and the marker comes off in the same change, so neither half is green
alone. T601, T602 and T608 are one commit: constitution IX puts new personal data and its register
entry in the same change. T634 is one commit with nothing else: it changes workspace membership and format globs, and a
half-applied version leaves the tree red in a way that looks like a formatting problem. T627 and
T655 are separate: T627 populates the record inside the adapter and is green alone; T655 publishes
it. **Before committing any removal or rename, grep for consumers.**

### Parallel opportunities

- T603 alongside the T606/T607 unit — T606 and T607 share two files and run as one.
- T609, T610 in one batch; T611 is their shared test and rides with them.
- T623, T624 with T630, T631 once the vocabulary exists.
- T646, T649, T650 — three test files in the same package.
- T654, T660, T661, T664, T666 — five test files across four packages.
- T667, T668, T669 — two different documents and a quickstart run.

A parallel batch is **one commit**: agents sharing a working tree interleave in the same files, and
splitting that afterwards invents commits that never existed as a working state.

---

## Implementation strategy

**Phase 1 first, alone, today.** It is small, it is true now, and its evidence expires. Merge it
before phase 2 starts.

**Then phases 2 through 5 in order**, one `/speckit-implement` invocation per phase, naming the task
range and the stop condition. Each phase is independently green and separately mergeable. Phase 4 is
the largest and carries the one unknown this plan could not size — how many bonuses of the fixture
civilisations resist the effect model — with the valve built in: a bonus that does not fit is
recorded as not modelled and its fields stay gapped, so the phase reports a blocking gap with a
named cause rather than stalling.

**Do not compress phase 3 into another phase.** Its proof is available only while nothing else on
the parse path moves.
