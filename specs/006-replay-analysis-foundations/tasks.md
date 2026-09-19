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

**Organization**: grouped by the five phases [plan.md](./plan.md) fixes, not by story priority. The
ordering is forced three times over — the fixture has a closing window, the golden-timeline identity
proof exists only before anything else touches the parse path, and gap severity cannot be computed
before the register exists — and those constraints do not line up with P1/P2/P3. Story labels ride
on each task; a phase serving two stories says so.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel — different files, no dependency on an incomplete task
- **[Story]**: US1..US6, mapping to the user stories in [spec.md](./spec.md)
- Every task names its exact file path

## Path Conventions

Per [plan.md](./plan.md): `packages/core/src/aoe2stats_core/{truth,replay}/`,
`packages/replay-engine/`, `packages/knowledge/`, `packages/storage/`, `apps/analyzer/`,
`apps/web/src/features/analysis/`, `scripts/{ops,checks}/`, `tests/fixtures/replays/`,
`infra/migrations/versions/`, `docs/`, `.claude/skills/replay-parsing/`.

## Numbering starts at T601, deliberately

001 reaches T110, 002 runs T201–T215, 003 runs T301–T412, 004 runs T401–T458 and 005 runs T501–T596.
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
| Phase 3 — canonical events| 3     | US4      | T626, T628, T630, T632   |
| Phase 4 — the knowledge base | 4  | US2, US5 | T641, T646, T649, T651   |
| Phase 5 — identity        | 5     | US3, US6 | T657, T660, T663, T665   |

---

## Phase 1: Evidence and corrections (plan phase 1 — US1)

**Purpose**: secure the evidence before it expires, and stop three documents lying. Everything here
is true today and none of it depends on any other phase.

**Independent test**: quickstart Phase 1. Both committed archives match their recorded checksums and
neither carries a post-game statistics block; no document names a parser path that does not exist.

**Story goal (US1)**: a reader can trust what the repository says about what a recording contains.

- [ ] T601 [US1] **Recover the second reference recording, and do it first.** Constitution I is the
      reason this task leads a feature that otherwise never touches capture: the source purges
      recordings on a schedule this project does not control, so every other task in this list can
      be done tomorrow and this one cannot. Obtain the ranked team-game recording measured during
      specification, **preferring the archive exactly as the source served it** — the existing
      fixture's value rests partly on being verbatim, and `tests/fixtures/replays/README.md` says in
      so many words not to re-zip. Place it in `tests/fixtures/replays/`. Three outcomes are
      admissible and the next three tasks each handle one: the served archive (best), an extracted
      recording that must be repackaged (acceptable, and the repackaging is disclosed), or
      unrecoverable (T605). Do not proceed past T605 on an unrecorded outcome
- [ ] T602 [US1] Extend `tests/fixtures/replays/README.md` with the second recording's entry in the
      existing table's shape: match kind, date played, date downloaded, the download address, game
      build, archive size, extracted size, member count, point of view, operation counts, and its
      checksum. **If and only if the archive was repackaged**, state that plainly — that the bytes
      and therefore the checksum are this repository's and not the source's, and that the first
      fixture remains the verbatim one. A repackaged fixture is still evidence; a repackaged fixture
      presented as verbatim is not. Repeat the existing do-not-modify instruction for the new file
- [ ] T603 [P] [US1] Write `tests/test_reference_recordings.py`: for **every** archive under
      `tests/fixtures/replays/`, assert the recorded checksum matches, the archive holds exactly one
      recording, and the parsed post-game block list contains no statistics block. Parameterise over
      the directory rather than naming files, so a third recording added later is covered without
      anyone remembering to extend it. This is the test that lets `docs/data-sources.md` §2 stop
      being an open question, and it is why T601 comes first: the claim needs bytes anyone can
      re-measure, not a citation to a conversation
- [ ] T604 [US1] Rewrite `docs/data-sources.md` §2's open question as a settled finding (**FR-045**):
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
- [ ] T606 [P] [US1] Correct `.claude/skills/replay-parsing/SKILL.md` and
      `docs/adr/0001-replay-parser.md` to name the paths that exist (**FR-046**): the adapter at
      `packages/replay-engine/src/aoe2stats_replay_engine/aoe2rec.py` and the protocols at
      `packages/core/src/aoe2stats_core/replay/`, in place of the parser application directory
      neither document's path ever pointed at. In the same edit, correct ADR-0001's Decision section
      where it states that both engines sit behind one protocol: one engine has an adapter and the
      other is installed ephemerally by `scripts/checks/parser_canary.py` in the nightly workflow.
      **Do not claim to have closed that gap** — `docs/risks.md` carries it as an open item, it
      predates this feature, and the canonical event model is what makes closing it cheap later
- [ ] T607 [P] [US1] Correct `.claude/skills/replay-parsing/SKILL.md` where it states the placement
      command carries no player identifier (**FR-047**). The pinned wheel supplies it;
      `packages/replay-engine/tests/test_aoe2rec.py` pins that as a currently-passing fact across
      every placement in the fixture and names both this file and the ADR in its own docstring. Only
      the building identifier requires decoding. A skill that a test has been contradicting is worse
      than no skill: it is read by agents that will not check
- [ ] T608 [US1] Add the second recording's participants to `docs/privacy/processing-register.md`
      under the existing already-public retention basis, with its balancing test, matching the
      entry the first fixture already has. Constitution IX is not a new obstacle here and the entry
      must not imply it is — what is new is two more named players, on the same basis, in the same
      shape. Skip only if T605 was taken, in which case no recording was added

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
      open). Explicit deletions and market transactions at **observed** (**FR-014**). The
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
- [ ] T625 [US4] Implement `packages/replay-engine/src/aoe2stats_replay_engine/canonical.py`:
      a generator mapping the wheel's operations to canonical events in **one pass**, never
      materialising the operation list (**FR-021**). The memory ceiling in
      `specs/003-player-search-match-analysis/contracts/analysis.md` binds this entry point exactly
      as it binds the existing one, and it was sized against parsing alone — do not treat headroom
      as available because this path is new. First-occurrence collapse per kind (**FR-018**), using
      the keys the `replay-parsing` skill already mandates. Nothing is attributed to a participant
      after their exit, and an observer or empty slot yields no participant at all — not a silent one
- [ ] T626 [US4] Represent every operation the adapter does not decode as an `undecoded` event
      carrying the engine's own operation label and the payload length, never dropped and never
      guessed at (**FR-019**). Add the conservation test: emitted events plus the operation kinds
      deliberately consumed for the clock equal the operation count the wheel reports. A silent drop
      is the failure mode that cannot be found later, because nothing downstream knows to miss it
- [ ] T627 [US4] Populate the engine dependency record inside the adapter (**FR-044**) from installed
      distribution metadata for the engine and each requirement it declares, and make an empty
      record a construction error. `apps/analyzer/src/aoe2stats_analyzer/extract.py` publishes an
      empty dependency map as a literal today, and the column to hold it has existed all along —
      this is the task that stops the document claiming to identify its engine while recording
      nothing (**SC-011** is asserted in phase 5, where the document carries it)
- [ ] T628 [US4] Re-express the existing timeline extractor in
      `packages/replay-engine/src/aoe2stats_replay_engine/aoe2rec.py` as a fold over the canonical
      stream, and **prove the committed golden timeline comes back byte-identical**. `git status`
      shows `tests/fixtures/replays/AgeIIDE_Replay_500546441.timeline.json` untouched. Do **not**
      regenerate it to make a test pass: the fixtures README already carries that instruction and
      ADR-0001's own failure mode was a parser upgrade that silently changed what was being read. A
      diff here means the stream lost or altered something, which is the one thing this phase may
      not do
- [ ] T629 [US4] Commit the canonical stream for each reference recording as a golden file under
      `tests/fixtures/replays/`, following the regeneration discipline the README already states for
      the timeline: regenerate only on an engine upgrade or a deliberate logic change, never by hand,
      and read and explain every diff it produces
- [ ] T630 [P] [US4] Write the engine-independence test (**SC-009**): walk every payload type's field
      names and assert none appears in a deny-list **generated from the wheel's own output keys** for
      the fixture, and that no payload carries a raw byte sequence, a byte offset or a length other
      than `undecoded`'s (**FR-017**). Generating the deny-list rather than writing it by hand is the
      point — a hand-maintained list tracks what someone remembered, and the wheel is what changes
- [ ] T631 [P] [US4] Write the collapse test (**SC-010**): the age-up command the fixture's player
      issued twice by double-clicking appears once in the canonical stream. Both reference recordings
      carry real duplicates, so assert over every committed recording rather than one
- [ ] T632 [US4] Extend the existing memory-ceiling test to the canonical entry point at the same
      bound, and assert the declared-only kinds are never emitted (**FR-020**). That second
      assertion is what makes the reserved vocabulary honest: the day a producer lands, this test is
      what changes, and no type does
- [ ] T633 [US4] Implement `packages/replay-engine/src/aoe2stats_replay_engine/silence.py`: the
      group-control-lost observable, computed from commanded-unit events only, published at the
      **inferred** tier with a confidence whose basis states the command intensity and the silence
      length for that instance (**FR-013**). Every instance carries the non-claim verbatim — it is
      not a casualty count. It consumes no deletion and no market event and is never summed with
      either (**FR-014**). Its banding lives in the register entry's method, so changing it is a
      register change with a regenerated view, not a constant edit. **This is the datum a reader is
      most likely to misread as a loss figure**, which is why the non-claim is a required field of
      the type and not a comment near it

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
      trap is invisible until the pack lands, which is why it is disarmed in the task before
- [ ] T635 [US2] Write `scripts/ops/import_knowledge_pack.py`: reads a **local checkout** of the
      source at a stated commit and writes `packages/knowledge/packs/aoe2techtree/`. It opens no
      socket, and its header carries the same warning `scripts/ops/sync_map_thumbnails.py` does,
      plus the statement that automating the download is the moment a provider becomes mandatory
      (**FR-032**). Nothing in the running system, the build or the tests fetches a knowledge source,
      and the way that is guaranteed here is that no code performs a fetch at all
- [ ] T636 [US2] Vendor the pack at a pinned commit with its five-field `LICENCE.md` — source,
      licence, permitted usage, ruling, checked date — in the exact form
      `scripts/checks/asset_packs.py` already enforces (**FR-033**), and add its row to
      `docs/asset-packs.md`, which that check mirrors. Only a source whose licence permits it is
      vendored (**FR-031**): this one is MIT. Record the same residual risk the civilisation-icon
      pack's ruling already records, rather than restating it as new
- [ ] T637 [US2] Extend `scripts/checks/asset_packs.py`'s root list and the `asset-packs` paths
      filter in `.github/workflows/pr.yml` to `packages/knowledge/packs`. The check is hard-scoped
      to the game-assets root today, so until both are extended it neither sees the new pack nor runs
      when it changes, and constitution X is enforced only where the gate looks. **Prove it bites**:
      drop one licence field, confirm the check names the pack, restore it
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
      those (**FR-022a**). Both players in the first fixture trained units their civilisation
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
      per [data-model.md](./data-model.md) §7, with the aggregate report as one repository function
      grouping by build, cause and severity (**FR-039**) and one line in the analyzer's run summary,
      the shape the quarantine counter already has. A pattern of gaps introduced by a game patch must
      be visible as a rate, not discovered one analysis at a time. The table holds no personal data:
      a participant is not a column

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
      T627's record, replacing the empty literal. Every published value carries its tier as data and
      the method that produced it (**FR-007**, **FR-009**), and a value at inferred or predicted
      carries a confidence and is worded so it cannot be read as a measurement (**FR-010**)
- [ ] T656 [US3] Place inferred and predicted data **structurally** under the inferred block alone,
      so a coaching conclusion cannot occupy a field typed observed, decoded or reconstructed
      (**FR-011**) by construction, with T619's validator as the second lock. Run the validator
      **before** the object is written: a failing document is not published and the analysis fails
      through 003's existing failure path
- [ ] T657 [US6] Make the published object's key carry the identity digest, and keep
      `match_analyses.result_key` pointing at the current document (**FR-042**). Today one object per
      match is overwritten on recompute, which destroys an existing analysis — a new parser, patch,
      knowledge version or analytics version must produce a **new** analysis and rewrite nothing.
      `match_analyses` keeps its primary key: that key is 003's double-click dedupe and is not this
      feature's to change (**FR-048** — where this feature and 003 meet, 003 stands)
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
- [ ] T663 [US6] Add the expand-only migration for `analysis_knowledge_gaps` under
      `infra/migrations/versions/`. **It adds and drops nothing**, so it applies before the deploy
      per `docs/runbooks/database-migrations.md` — which is the only path, because `.env.local`
      points at production and no task here runs a migration from a developer machine. Bump the
      expected schema revision in the same change so the health endpoint reports it
- [ ] T664 [P] [US3] Add a test in `apps/web/src/features/analysis/` pinning that the reader parses a
      next-version document fixture with **no source change**. The reader already requires only the
      existing fields, accepts any numeric schema version and ignores unknown keys — this test is
      what stops a later edit quietly breaking that, and it is why the extraction time is duplicated
      rather than moved. No component changes; displaying a tier or a gap needs a design-system spec
      first and is a later feature's decision
- [ ] T665 [US6] Verify the phase end to end against quickstart Phase 5, including the post-deploy
      checks: the health endpoint reports the new schema revision, and one analysis requested by hand
      shows a populated dependency record, an identity digest and a gap list that is empty or
      explains itself
- [ ] T666 [P] [US3] Add the boundary guard test asserting this feature added no scheduled job, no
      request-path work and no code path that consumes the capture budget (**FR-049**), and that
      nothing here re-specifies 003's request, fetch, parse-once, retention, recompute, isolation,
      rate-limiting or legal-basis behaviour (**FR-048**). Constitution I is the reason: an analysis
      feature may not degrade capture, and the cheapest time to assert that is while the diff is
      still in hand

**Checkpoint**: every value carries its tier, every analysis carries its identity, and no version
destroys its predecessor.

---

## Phase 6: Polish and cross-cutting

- [ ] T667 [P] Add the starting-state finding to `docs/risks.md` under the existing parser risk: the
      section is present in the header and reachable in two tiers of very different cost, with the
      per-patch fragility of the object grammar recorded. This retires the assumption that it is
      unreadable **without** promising the decoder, which is 007's
- [ ] T668 [P] Correct `.claude/skills/replay-parsing/SKILL.md` to record what the initial-state
      section actually contains and what the pinned wheel exposes of it, so the next agent starts
      from the anchor rather than from the claim that nothing is there. Reference
      [research.md](./research.md) **D1**; restate no offset — the measurement has one home
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
alone. T634 is one commit with nothing else: it changes workspace membership and format globs, and a
half-applied version leaves the tree red in a way that looks like a formatting problem. T627 and
T655 are separate: T627 populates the record inside the adapter and is green alone; T655 publishes
it. **Before committing any removal or rename, grep for consumers.**

### Parallel opportunities

- T603, T606, T607 — three different files, no shared state.
- T609, T610 in one batch; T611 is their shared test and rides with them.
- T623, T624 with T630, T631 once the vocabulary exists.
- T646, T649, T650 — three test files in the same package.
- T654, T660, T661, T664, T666 — five test files across four packages.
- T667, T668, T669 — three documents.

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
