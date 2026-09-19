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

001 reaches T110, 002 runs T201–T215, 003 runs T301–T412, 004 runs T401–T458 and 005 runs T501–T599.
Ids resolve **across** features: `spec_lint.py`'s `task-refs` check treats an id as defined the
moment any feature's `tasks.md` says so. 003 and 004 already overlap at T401–T412, which is exactly
the ambiguity a disjoint range costs nothing to avoid.

## What every implementer must know before starting

**`.env.local` points at production.** No task here runs a migration, a backfill or a script against
it. Phase 5's revision goes through `docs/runbooks/database-migrations.md` and nowhere else.

**Never substitute a value for missing knowledge.** Not a default, not an average, not the
neighbouring build's, not the baseline civilisation's. If a task seems to require one, the task is
wrong — stop and say so. This is FR-038, and the whole feature exists because it is easy to break.

**Do not restate a measurement.** Every number measured during specification lives in
`docs/data-sources.md` or in [research.md](./research.md), and artifacts reference it (SC-013).

## Scenario coverage map

| quickstart section        | Phase | Story    | Task(s) that encode it   |
| ------------------------- | ----- | -------- | ------------------------ |
| Phase 1 — the fixture     | 1     | US1      | T603, T604               |
| Phase 1 — the corrections | 1     | US1      | T606, T607               |
| Phase 2 — the register    | 2     | US1, US3 | T614, T617, T621         |
| Phase 3 — canonical events| 3     | US4      | T626, T626a, T628, T630, T632 |
| Phase 4 — the knowledge base | 4  | US2, US5 | T641, T646, T649, T651   |
| Phase 5 — identity        | 5     | US3, US6 | T657, T660, T663, T665   |

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
- [ ] T605 [US1] **Only if T601 returned unrecoverable.** Take the narrow honest branch instead of
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

- [ ] T609 [P] [US3] Create `packages/core/src/aoe2stats_core/truth/tiers.py`: the closed, ordered
      tier set observed → decoded → reconstructed → derived → inferred → predicted (**FR-008**), as
      an enumeration with a total order, plus the weakest-input combinator that computes a result
      tier from its inputs' tiers. A caller must have **no way** to assert a tier stronger than its
      weakest input — that is a function signature, not a review note. `non-determinable` is
      deliberately **absent** from this enumeration: it is a register classification and nothing is
      ever published at it, which is why **FR-001** lists seven classifications and **FR-008** six
      tiers. Tiers with no producer in this feature exist from the start so that 007 adds no member
- [ ] T610 [P] [US3] Create `packages/core/src/aoe2stats_core/truth/confidence.py` (**FR-010a**): a
      closed, ordered level set and a mandatory non-empty basis, constructed together. A number is
      **not accepted in any form** — no float field, no numeric coercion, no optional escape hatch —
      because a recording carries no outcome against which a probability could be calibrated, and an
      uncalibrated number is an invented value wearing a measured one's clothes. An empty or
      whitespace basis fails construction
- [ ] T611 [P] [US3] Write `packages/core/tests/test_truth_types.py` covering T609 and T610 before
      either is implemented, `xfail(strict=True)`: the order is total; the combinator returns the
      weakest input; a confidence rejects a float, an integer, a numeric string and an empty basis;
      a confidence attached to a value at a tier above inferred is an error, because doubt advertised
      where the method admits none misleads in the other direction
- [ ] T612 [US3] Create `packages/core/src/aoe2stats_core/truth/provenance.py` (**FR-009**): tier,
      method identifier and version, inputs, optional confidence, optional non-claim, bound to one
      register datum. Confidence is **required** at inferred and predicted and **forbidden** below
      (**FR-010**), enforced at construction. The method must name an algorithm in a form a reader
      can recompute — a free-text sentence is not one, so the field is an identifier plus a version
- [ ] T613 [US1] Write `packages/core/src/aoe2stats_core/truth/register.toml` with the entry schema
      in [contracts/register.md](./contracts/register.md) and the entries that contract lists as
      mandatory (**FR-001**, **FR-002**). Every entry states its source, its method, the knowledge
      it requires, what it depends on and how it is validated, and its evidence is a **reference**
      into `docs/data-sources.md` or [research.md](./research.md) — never a restated number
      (**SC-013**). Include every leaf the published document carries today, at observed or decoded
- [ ] T614 [US1] Add to `register.toml` the entries the spec names individually. Unit loss as
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
- [ ] T615 [US1] Implement `packages/core/src/aoe2stats_core/truth/register.py`: the entry type and
      a loader that reads the TOML with the standard library, so `packages/core` keeps its
      zero-dependency rule. Loading **fails at import** on any of the eight refusals in
      [contracts/register.md](./contracts/register.md) — duplicate id, value outside a closed set, a
      non-determinable entry missing any of its five fields, a blocked entry with no named
      dependency, a dangling or cyclic dependency, a tier stronger than its weakest dependency, a
      published inferred entry with no confidence method, or empty evidence. Expose the dependency
      graph, which phase 4 reads to compute severity
- [ ] T616 [P] [US1] Write `packages/core/tests/test_register.py` before T615, `xfail(strict=True)`:
      one test per refusal, each **planting the defect itself** rather than asserting the happy
      path. A loader test that only loads the good file proves the file is good, not that the loader
      refuses anything — and the refusals are the whole product here
- [ ] T617 [US1] Implement the view renderer in `register.py` and commit its output as
      `packages/core/src/aoe2stats_core/truth/REGISTER.md` (**FR-006a**): grouped by classification,
      non-determinable entries first and in full, with a generated-file header naming its source.
      Add the drift test that renders in memory and compares byte for byte, failing with the
      regeneration command in its message. The file is filed **beside the package**, not under
      `docs/`, because its subject is this product's own data — `CLAUDE.md`'s filing rule sends a
      fact about a package to live next to what recomputes it
- [ ] T618 [US1] Verify **SC-012** by hand and record the result in the task hand-back: open
      `REGISTER.md`, look up unit loss, and confirm — **without opening a Python file** — that it
      says why it cannot be known, what that costs, that the approximation is not acceptable, and
      what would change the answer. If that read needs the source, the renderer is the defect
- [ ] T619 [US3] Implement `packages/core/src/aoe2stats_core/truth/validate.py` with the ten rules in
      [contracts/analysis-document.md](./contracts/analysis-document.md), against the document shape
      that exists today — the identity, inferred and gap blocks arrive in later phases and their
      rules are written now and exercised against hand-built documents. Rules 1 and 2 are
      **FR-006** and **FR-007**: every leaf resolves to exactly one published datum, and every datum
      present carries a provenance entry. Rule 5 is **FR-010**; rule 6 is **FR-011**
- [ ] T620 [P] [US3] Write `packages/core/tests/test_validate.py` before T619, `xfail(strict=True)`.
      **SC-003** is tested the way it is worded — a coaching-style conclusion placed in a field typed
      observed, decoded and reconstructed, rejected **each time it is attempted**, which is once per
      tier boundary and not once overall. **SC-001**: a document carrying a leaf with no register
      entry is rejected. **SC-002**: a document with a value missing its tier, and one with an
      inferred value missing its confidence or its basis, are both rejected
- [ ] T621 [US1] Verify the drift gate bites: edit one impact line in `register.toml`, run the
      suite, confirm the view test fails and prints the regeneration command, regenerate, confirm
      green, and leave the register as it was. A gate nobody has seen fail is a gate nobody knows
      the shape of
- [ ] T622 [P] [US3] Record the naming discipline in `packages/core/src/aoe2stats_core/truth/`'s
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

- [ ] T623 [P] [US4] Create `packages/core/src/aoe2stats_core/replay/events.py`: the closed event
      vocabulary and the source protocol in
      [contracts/canonical-events.md](./contracts/canonical-events.md). Every event carries a
      match-clock time, the participant it is attributed to, its kind and its tier (**FR-016**), and
      the protocol is what everything above the adapter imports (**FR-015**). `building-placed` is
      **decoded**, not observed — its building identifier comes from a payload this repository
      decodes, and the event takes its weakest input's tier. `chat` carries a channel and **no
      text**: the text is personal data this feature has no use for, and leaving it out of the
      vocabulary keeps constitution IX out of this seam entirely. Declare the two starting-state
      kinds **without a producer** (**FR-020**), so the day the decoder lands no type changes
- [ ] T624 [P] [US4] Write `packages/core/tests/test_events.py` before T623, `xfail(strict=True)`:
      every kind has a tier; an event without a participant is constructible only for the
      match-level kinds; the two declared-only kinds exist as types
- [ ] T625 [US4] Implement `packages/replay-engine/src/aoe2stats_replay_engine/canonical.py`: a
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
- [ ] T626 [US4] Represent every **action** the adapter does not decode as an `undecoded` event
      carrying the engine's own label and the payload length, never dropped and never guessed at
      (**FR-019**). Command kinds that arrive without decoded unit ids — formation, stance, patrol,
      stop and the rest — are emitted as `units-commanded` with an **empty** id list, never an
      inferred one. Add the conservation test over every committed recording: emitted events, plus
      sync and view-lock operations, equal the operation count the wheel reports. The second
      recording carries an action kind the wheel itself cannot name, so this rule has a live
      instance to assert on. A silent drop is the failure mode that cannot be found later, because
      nothing downstream knows to miss it
- [ ] T626a [US4] Write the market and deletion decoders in
      `packages/replay-engine/src/aoe2stats_replay_engine/canonical.py`, in the placement decoder's
      mould (**FR-014**). The wheel returns sell, buy and delete as raw byte payloads, so direction,
      resource, amount and the deleted object's id must be derived **empirically** — sweep the byte
      positions across every instance in every committed recording, cross-check against values that
      can be verified independently, and golden-test the result over all of them, exactly as the
      building identifier was found. These events are **decoded**, exact, and never blended into an
      inferred quantity. If a field cannot be pinned with confidence, emit the event without it and
      register the field as blocked — a guessed amount at the decoded tier is the precise lie this
      feature exists to prevent. Test first, `xfail(strict=True)`
- [ ] T626b [US4] Decode the chat channel in
      `packages/replay-engine/src/aoe2stats_replay_engine/canonical.py`. The channel sits inside the
      same JSON string as the message text, so the text cannot be avoided on the way to it: parse,
      keep the channel and the participant, and **discard the text at the adapter**. Assert that no
      message text appears in any canonical event, in either committed golden stream, or in any log
      line this module emits — the text is personal data this feature has no use for, and
      constitution IX is kept out of this seam by that assertion, not by intention. Chat carries no
      time of its own and takes T625's accumulated clock
- [ ] T627 [US4] Populate the engine dependency record inside the adapter (**FR-044**) from installed
      distribution metadata for the engine and each requirement it declares, and make an empty
      record a construction error. `apps/analyzer/src/aoe2stats_analyzer/extract.py` publishes an
      empty dependency map as a literal today, and the column to hold it has existed all along —
      this is the task that stops the document claiming to identify its engine while recording
      nothing (**SC-011** is asserted in phase 5, where the document carries it)
- [ ] T628 [US4] Re-express the existing timeline extractor in
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
- [ ] T629 [US4] Commit the canonical stream for each **committed** reference recording — one if T605
      was taken, two otherwise — as a golden file under
      `tests/fixtures/replays/`, following the regeneration discipline the README already states for
      the timeline: regenerate only on an engine upgrade or a deliberate logic change, never by hand,
      and read and explain every diff it produces
- [ ] T630 [P] [US4] Write the engine-independence test (**SC-009**): walk every payload type's field
      names and assert none appears in a deny-list **generated from the wheel's own output keys** across
      **every committed recording** — the two expose different action kinds, so a list built from one
      is blind to the other's keys — and that no payload carries a raw byte sequence, a byte offset or a length other
      than `undecoded`'s (**FR-017**). Generating the deny-list rather than writing it by hand is the
      point — a hand-maintained list tracks what someone remembered, and the wheel is what changes
- [ ] T631 [P] [US4] Write the collapse test (**SC-010**): the age-up command the fixture's player
      issued twice by double-clicking appears once in the canonical stream. Assert over every
      committed recording rather than one, and assert the inverse too: repeated unit-queue commands
      are **not** collapsed, because a test that only checks collapse cannot see over-collapse
- [ ] T632 [US4] Extend the existing input-size refusal test to the canonical entry point, **and add
      a real peak-memory measurement beside it**. The existing test is named for the memory ceiling
      and measures no memory: it asserts that an oversized input is refused, which says nothing
      about what an accepted input consumes. This feature puts three accumulators on that path — the
      stream's consumers, the group-silence state and the coverage pass — and the second recording's
      object-id space is several times the first's. Measure peak allocation over every committed
      recording through the full canonical path and record the ceiling the test asserts against,
      with its derivation, in the test itself. Also assert the declared-only kinds are never emitted
      (**FR-020**): that is what makes the reserved vocabulary honest — the day a producer lands,
      this test is what changes, and no type does
- [ ] T633 [US4] Implement `packages/replay-engine/src/aoe2stats_replay_engine/silence.py`: the
      group-control-lost observable, computed from commanded-unit events only, published at the
      **inferred** tier with a confidence whose basis states the command intensity and the silence
      length for that instance (**FR-013**). **State its blind spot in the datum's method**: only
      move, interact and order carry decoded unit ids; formation, stance, patrol and stop do not, so
      exactly the commands that park a military group are invisible and a parked group reads as
      silent. That blind spot caps the level the banding may assign, and the non-claim names it.
      Every instance carries the non-claim verbatim — it is not a casualty count. It consumes no
      deletion and no market event and is never summed with either (**FR-014**). Its banding lives
      in the register entry's method, so changing it is a register change with a regenerated view,
      not a constant edit. **This is the datum a reader is most likely to misread as a loss
      figure**, which is why the non-claim is a required field of the type and not a comment near it

**Checkpoint**: one vocabulary, no engine-shaped field, nothing dropped, and the golden timeline
proves nothing was lost.

---

## Phase 4: The knowledge base and its gaps (plan phase 4 — US2, US5)

**Purpose**: a versioned, immutable, offline body of game rules that refuses to answer what it does
not know.

**Independent test**: quickstart Phase 4. A discounted unit returns its civilisation-adjusted cost
with the effect applied; an unmodelled civilisation returns a gap; the coverage pass over every
committed recording reports no blocking gap.

**Story goal (US2)**: the engine can ask the rules a question for a stated build and civilisation.
**(US5)**: a missing rule stops the analysis instead of corrupting it.

- [ ] T634 [US2] Create `packages/knowledge/` as a workspace member — `pyproject.toml` depending on
      `aoe2stats-core` only — and register it in the root `pyproject.toml` workspace list, its
      `testpaths` and its mypy settings. **In the same change, narrow the two format globs in
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
- [ ] T635 [US2] Write `scripts/ops/import_knowledge_pack.py`: reads a **local checkout** of the
      source at a stated commit and writes `packages/knowledge/packs/aoe2techtree/`. It opens no
      socket, and its header carries the same warning `scripts/ops/sync_map_thumbnails.py` does,
      plus the statement that automating the download is the moment a provider becomes mandatory
      (**FR-032**). Nothing in the running system, the build or the tests fetches a knowledge source,
      and the way that is guaranteed here is that no code performs a fetch at all
- [ ] T636 [US2] Vendor the pack at a pinned commit with its `LICENCE.md`, whose five fields are
      named **exactly** as `scripts/checks/asset_packs.py` matches them — `Source`, `Licence`,
      `Permitted usage`, `Ruling`, `Checked` (**FR-033**); a field written any other way fails the
      gate as missing. The ruling leads with **COPY IN**, one of the two verdicts the gate
      recognises. Only a source whose licence permits it is vendored (**FR-031**): this one is MIT.
      Add a **third section** to `docs/asset-packs.md` for knowledge packs, as feature 005 added one
      for typefaces — the row does not belong in the game-assets table — and widen that document's
      opening scope sentence, which names game assets only. **State the residual risk once and do
      not borrow the wrong precedent**: the files are MIT, but their values were produced upstream
      by reading the game's data file, which the publisher's usage rules do not authorise. This
      repository already weighed that for this source — `docs/data-sources.md` §1 rules its data MIT
      and the risk register's R7 records the residual — so cite both and restate neither. The flags
      pack records no such risk because it has no game-derived content; this pack is not in that
      position
- [ ] T637 [US2] Extend the list of roots in `scripts/checks/asset_packs.py` and the `asset-packs`
      paths filter in `.github/workflows/pr.yml`. That list holds **(root, size budget) pairs**, not
      bare paths, so each new root needs its own named budget constant with its own stated
      justification, as the two existing roots have. Add **two**: `packages/knowledge/packs`, and
      `packages/knowledge/snapshots` — the snapshots root is append-only by design and ships inside
      the package, so it is the one that most needs a ceiling and had none. Size each budget from
      the measured payload with stated headroom. The check is scoped by root today, so until both
      are added it neither sees the new pack nor runs when it changes, and constitution X is
      enforced only where the gate looks. **Prove it bites**: drop one licence field, confirm the
      check names the pack, restore it
- [ ] T638 [US2] Implement `packages/knowledge/src/aoe2stats_knowledge/snapshot.py`: the identity —
      source, source version, described build, content digest (**FR-024**) — loaded through
      `importlib.resources` so it works identically from a serverless bundle and a virtual
      environment. The digest is recomputed on load and a mismatch **refuses to load**. Publishing a
      new snapshot never modifies or removes an existing one (**FR-025**), and a test walks every
      committed snapshot directory asserting each file matches its recorded digest — which is how
      immutability is asserted rather than merely requested
- [ ] T639 [US2] Implement the promotion sequence in `snapshot.py` (**FR-034**): source change, new
      pack revision, new unvalidated snapshot, recorded validation, promoted. Only a promoted
      snapshot is resolvable, and a promotion flag set with an empty validation record is refused.
      An unvalidated snapshot is never promoted, and no source is treated as authoritative without
      validation against the game or a second source, with the validation performed recorded
      (**FR-030**)
- [ ] T640 [US2] Implement the normaliser producing `rules.json` from a pack: units, buildings,
      technologies, their costs, their training, construction and research times, their age
      requirements and prerequisites, civilisations, and the civilisation bonuses that modify any of
      the above (**FR-022**). A unit identifier may live in the source's unit table or its upgrade
      table — four technology identifiers in the committed fixture do — so merge both into one keyed
      space and record which table each came from. Where the vendored pack and any second reading
      disagree on a field, record the disagreement and carry which source the stored value came from
      (**FR-028**) in `disagreements.toml`, rather than resolving it by precedence alone
- [ ] T641 [US2] Implement build resolution (**FR-027**): exact match on the described build among
      promoted snapshots, or a gap with the no-snapshot cause. There is **no nearest, no latest and
      no fallback parameter** — the function must not accept one, because an argument that exists
      will be passed. A recording from a build with no snapshot is a gap with its own severity, not
      an analysis against a neighbouring snapshot
- [ ] T642 [US2] Implement carry-forward in `snapshot.py` per [research.md](./research.md) **D4**:
      a snapshot may describe a build later than the revision it was imported from, only when its
      validation record lists **every** intervening build with the notes consulted, where they were
      read, the date, and the reading. A build missing from that list makes the snapshot
      unpromotable. This is forced, not chosen: no source carries a build key, and the committed
      fixture's build is newer than the newest revision the source has implemented, so without this
      the only committed recording cannot be analysed at all. Record the weakest link in the
      attestation — the fixture's own build has no publisher page and its notes come from a
      secondary listing — **in the validation record, not in a comment**
- [ ] T643 [US2] Implement `packages/knowledge/src/aoe2stats_knowledge/query.py` with the surface in
      [contracts/knowledge-base.md](./contracts/knowledge-base.md). `civilisation` is **keyword-only
      and required** on every rule query, so there is no way to ask for a generic value and therefore
      no way to be handed one (**FR-023**). Every answer carries the snapshot identity that produced
      it, the source the stored value came from, and the effects applied in order. The return type is
      a union of answer and gap with **no third branch** — no bare value, no default parameter, no
      caught-and-continued gap anywhere in the package. **SC-008**'s "by construction rather than by
      inspection" is this signature, and T650 asserts it by introspection
- [ ] T644 [US2] Implement `packages/knowledge/src/aoe2stats_knowledge/effects.py`: structured
      civilisation effects — the civilisation, the verbatim source sentence and its key, whether it
      is modelled, an explicit identifier list rather than a fuzzy class name, the field, a closed
      operation, the operand, and the second reading that validated it. Transcribed by hand from the
      English strings that ship in the MIT pack, which **FR-031** permits with its provenance
      recorded. A bonus that is team-wide, gated on an age the recording cannot place, or
      conditional on state is recorded as **not modelled** with its reason, and its fields stay
      gapped — a bonus is never half-applied
- [ ] T645 [US2] Model the civilisations that appear in the committed reference recordings, and only
      those (**FR-022a**) — **six** with both fixtures committed, two from the first and four from the
      second with none shared ([research.md](./research.md) **D11**); two if T605 was taken. Both players in the first fixture trained units their civilisation
      discounts, so this is not an optional refinement: without it the one committed recording
      produces blocking gaps on day one. Implement the conservative rule in `query.py` — a
      civilisation absent from the modelled set refuses **every** civilisation-qualified cost and
      time, because which fields its bonuses touch is precisely what is not known. Coverage grows by
      whole civilisations and the gap report is the backlog
- [ ] T646 [P] [US2] Write `packages/knowledge/tests/test_query.py` before T643–T645,
      `xfail(strict=True)`: a discounted unit returns its adjusted cost with the effect and its
      source sentence; the same unit for an unmodelled civilisation returns a gap and **never the
      baseline**; a build one higher than any snapshot describes returns a gap; asking without a
      civilisation is a type error. Two snapshots answer from their own contents and neither is
      silently upgraded to the other (**US2** scenario 2)
- [ ] T647 [US5] Implement `packages/knowledge/src/aoe2stats_knowledge/gaps.py`: the gap record with
      entity, field, build and affected civilisation (**FR-035**), a closed cause set, what it
      prevents by register datum id (**FR-036** — what it stops, not that something is missing), and
      a severity **computed** from the register's dependency graph, never supplied by a caller
      (**FR-037**). Blocking when at least one register datum that is not itself blocked requires the
      field; informational otherwise. [research.md](./research.md) **D7** is why this is computed:
      read naively, nothing this feature publishes depends on a cost, every gap would be
      informational, and **SC-007a** would pass vacuously
- [ ] T648 [US5] Implement `packages/knowledge/src/aoe2stats_knowledge/coverage.py`: take a canonical
      stream, collect every entity and every participant civilisation, and ask for every field any
      register datum requires. Its output is the gap list the document publishes. A blocking gap
      prevents publication of every value depending on it while leaving independent values
      untouched, and **no default, average or neighbouring value is ever substituted** (**FR-038**)
- [ ] T649 [P] [US5] Write `packages/knowledge/tests/test_coverage.py` before T648,
      `xfail(strict=True)`. **SC-007**: remove a required field from an in-memory copy of a snapshot,
      run the pass, and assert exactly the dependent values are withheld, a gap names the entity,
      field, build and civilisation, and every independent value is still produced. **SC-007a**: the
      pass over each committed recording reports zero blocking gaps. **FR-039**'s aggregate is
      asserted in T652
- [ ] T650 [P] [US5] Write the structural tests that make refusal a property of the code rather than
      a habit: introspect every public query in the package and assert its return type is the
      answer-or-gap union (**SC-008**); assert no module in `packages/knowledge` imports a network
      library; and assert the whole package's tests pass with the network blocked (**SC-006**,
      **FR-026**), which `tests/conftest.py` already enforces at the socket workspace-wide
- [ ] T651 [US2] Add the source assessments to `docs/data-sources.md` as a new section, one
      subsection per source assessed in [research.md](./research.md) **D3** (**FR-029**): scope,
      reliability, update mechanism, version identifier, coverage, known limitations and the date the
      assessment was made. Record the rejections and **why**, including that the two community
      datasets are one generation pipeline run twice and therefore cannot cross-validate each other,
      and that the game's own data file is barred by the publisher's usage rules. This section also
      finally gives feature 002's licence rulings a living home — 002's own register was never
      written, and they survive today only in a frozen task list and a module docstring
- [ ] T652 [US5] Add `analysis_knowledge_gaps` to `packages/storage/src/aoe2stats_storage/models.py`
      per [data-model.md](./data-model.md) §7. **The table is the aggregate** (**FR-039**): one
      repository function grouping by build, cause and severity over a window, and one check script
      under `scripts/checks/` that prints the rate. Do **not** mirror the ingester's quarantine
      counter — that is a column on a per-run table fed by a multi-stage aggregator, and the
      analyzer has no run, no counters and no logger to attach one to; inventing a run concept for
      this would be a second table the data model says this feature does not have. A pattern of gaps
      introduced by a game patch must be visible as a rate, not discovered one analysis at a time.
      The table holds no personal data: a participant is not a column

**Checkpoint**: the rules are queryable offline, versioned by build, refuse what they do not know,
and every refusal is counted.

---

## Phase 5: Identity and the published document (plan phase 5 — US3, US6)

**Purpose**: assemble the four foundations into one validated, reproducible, non-destructive
document. This is the only phase that changes what production publishes.

**Independent test**: quickstart Phase 5. Two analyses of the same fixture are byte-identical; an
older analysis reproduces exactly after a knowledge refresh.

**Story goal (US3)**: every number says where it came from. **(US6)**: an analysis stays reproducible
after everything underneath it moves.

- [ ] T653 [US6] Implement `packages/core/src/aoe2stats_core/truth/identity.py`: the tuple of
      recording, parser name and version, parser dependencies, knowledge version, reconstruction
      engine version and analytics version (**FR-040**), with a digest over its canonical
      serialisation. Reconstruction engine and analytics carry an explicit not-applicable marker
      until 007 ships, so the tuple's **shape never changes** — retrofitting identity onto published
      artifacts is far harder than designing it in, which is why US6 is specified now
- [ ] T654 [P] [US6] Write `packages/core/tests/test_identity.py` before T653, `xfail(strict=True)`:
      the digest is stable across processes and insensitive to field ordering; two identities
      differing in any one component produce different digests; an empty dependency record is
      refused (**FR-044**)
- [ ] T655 [US3] Extend `apps/analyzer/src/aoe2stats_analyzer/extract.py` to publish the next
      document version per
      [contracts/analysis-document.md](./contracts/analysis-document.md): **additive only**, every
      existing field at its existing path, four blocks added. Populate the dependency map from
      T627's record, replacing the empty literal, **and write the same record to the
      `match_analyses.engine_deps` column** — it has existed through two migrations and nothing has
      ever written it. Every published value carries its tier as data and
      the method that produced it (**FR-007**, **FR-009**), and a value at inferred or predicted
      carries a confidence and is worded so it cannot be read as a measurement (**FR-010**)
- [ ] T656 [US3] Place inferred and predicted data **structurally** under the inferred block alone,
      so a coaching conclusion cannot occupy a field typed observed, decoded or reconstructed
      (**FR-011**) by construction, with T619's validator as the second lock. Run the validator
      **before** the object is written: a failing document is not published and the analysis fails
      through 003's existing failure path
- [ ] T657 [US6] Make the published object's key carry the identity digest, and keep
      `match_analyses.result_key` pointing at the current document (**FR-042**). Today one object
      per match is overwritten on recompute, which destroys an existing analysis — a new parser,
      patch, knowledge version or analytics version must produce a **new** analysis and rewrite
      nothing. `match_analyses` keeps its primary key: that key is 003's double-click dedupe and is
      not this feature's to change (**FR-048** — where this feature and 003 meet, 003 stands)
- [ ] T657a [US6] Extend the staleness test in `apps/analyzer/src/aoe2stats_analyzer/run.py` so a
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
- [ ] T658 [US6] Implement reproduction from a recorded identity (**FR-043**): read the retained
      recording through `packages/storage`, verify its checksum, resolve the named snapshot from
      package data, reach **no external source**, and refuse — naming what is missing — when the
      installed parser version or dependencies differ from the identity. The refusal is deliberate:
      reproducing under a different parser and calling the result the same analysis is the silent
      rewrite **FR-042** forbids, so the honest outcomes are identical, or cannot reproduce here
      because
- [ ] T659 [US6] Make the compared body a pure function of the identity (**FR-041**): canonical
      serialisation with sorted keys where order carries no meaning, stream order where it does, one
      fixed float format, and the wall-clock field excluded from both the identity and the
      comparison. The legacy top-level extraction time stays at its current path for one version
      because the web reader requires it there, and it joins the excluded set
- [ ] T660 [P] [US6] Write `apps/analyzer/tests/test_reproducibility.py` before T657–T659,
      `xfail(strict=True)`. **SC-004**: the same recording analysed twice with identical versions
      yields a byte-identical result, with the second run **in a fresh process** so that dictionary
      ordering or a cached clock cannot pass by accident. **SC-005**: publish, record the identity,
      promote a second snapshot, recompute, then fetch by the first identity and confirm it
      reproduces exactly and the newer snapshot was not substituted — and that the previous version
      remains available
- [ ] T661 [P] [US3] Write `apps/analyzer/tests/test_document_validation.py`, `xfail(strict=True)`:
      a document whose dependency record is empty is rejected (**SC-011**); a document carrying a
      datum whose required knowledge intersects a blocking gap is rejected (**FR-037**); a document
      with no tier on a value is rejected (**SC-002**)
- [ ] T662 [US5] Write the gap rows from the coverage pass in
      `apps/analyzer/src/aoe2stats_analyzer/run.py`, keyed so a reproduced analysis records nothing
      twice, and publish the gap list in the document. When no snapshot matches the recording's
      build, the knowledge block records the absence explicitly and one blocking gap says so
      (**FR-027**)
- [ ] T663 [US6] Add the single additive migration — the `analysis_knowledge_gaps` table and the
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
      no task here runs a migration from a developer machine by any other route
- [ ] T664 [P] [US3] Add a test in `apps/web/src/features/analysis/` pinning that the reader parses a
      next-version document fixture with **no source change**. The reader already requires only the
      existing fields, accepts any numeric schema version and ignores unknown keys — this test is
      what stops a later edit quietly breaking that, and it is why the extraction time is duplicated
      rather than moved. No component changes; displaying a tier or a gap needs a design-system spec
      first and is a later feature's decision
- [ ] T665 [US6] Verify the phase end to end against quickstart Phase 5, including the post-deploy
      checks: the health endpoint answers **200** — read the status, not the revision field, which
      is the build's own compiled constant and is no evidence about the database — and one analysis
      requested by hand shows a populated dependency record, an identity digest and a gap list that
      is empty or explains itself
- [ ] T666 [P] [US3] Add the boundary guard test asserting this feature added no scheduled job, no
      request-path work and no code path that consumes the capture budget (**FR-049**), and that
      nothing here re-specifies 003's request, fetch, parse-once, retention, recompute, isolation,
      rate-limiting or legal-basis behaviour (**FR-048**). Constitution I is the reason: an analysis
      feature may not degrade capture, and the cheapest time to assert that is while the diff is
      still in hand

**Checkpoint**: every value carries its tier, every analysis carries its identity, and no version
destroys its predecessor.

---

## Phase 6: Closing (plan phase 6)

**Purpose**: the living documents that can only be written once the rest is true, the end-to-end
quickstart run, and the lint. `/speckit-implement` stops here when T670 exits 0.

- [ ] T667 [P] Update `docs/risks.md`: correct R3's fallback list, which names the fast alternative
      parser as a fallback although [research.md](./research.md) **D1** measured that it cannot open
      the current build; and add a row for the dependency class this feature creates —
      community-maintained knowledge sources that may stop, one of which already has, plus the
      standing hand-transcription of civilisation bonuses and patch notes. Add the
      verification-checklist line for T603's assertion under parsing. Tick no existing checklist
      item
- [ ] T668 [P] Record the starting-state finding in `docs/data-sources.md` §2, which is where a
      measured property of the outside world lives — not in the risk register: the initial-state
      section is present in the header, per-player starting attributes are reachable at a
      self-verifying anchor, and the object table sits behind a per-patch grammar. A living fact in
      `docs/` is trustworthy only because a test asserts it, so add a fixture test that finds the
      attribute anchor in every committed recording. This retires the claim that the section is
      unreadable **without** promising the decoder, which is 007's. [research.md](./research.md)
      **D1** then becomes the historical record and stops being the home
- [ ] T669 [P] Run the full quickstart end to end on a clean checkout and record any step whose
      stated expectation did not match what happened. A quickstart nobody has executed is a
      hypothesis
- [ ] T670 Run `uv run scripts/checks/spec_lint.py --feature specs/006-replay-analysis-foundations`
      and confirm it exits 0 — every requirement named by a task, every task reference defined,
      every path under a declared root. Then run the whole suite by exit code, not by reading the
      summary line

---

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
