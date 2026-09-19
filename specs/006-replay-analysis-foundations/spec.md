# Feature Specification: Replay-analysis foundations — truth tiers, canonical events, versioned game knowledge

**Feature Branch**: `006-replay-analysis-engine`

**Created**: 2026-09-19

**Status**: Draft

**Input**: User description: a deterministic AoE2 DE replay-analysis and coaching engine, to be
designed and specified before any significant implementation — repository audit, empirical
investigation of a reference replay, external knowledge-source research, a gap analysis, an
architecture for canonical events, deterministic state, versioned knowledge, provenance, confidence
and reproducibility, then the appropriate Spec-Kit artifacts.

## Context

The long-term goal is a coaching engine that rests on a deterministic reconstruction of a game:
replay → canonical events → time-indexed state → economy/military/map analytics → strategic state →
expected trajectory → actual versus expected → coaching. The engine must never launch the game to
learn what happened, and must never present an invented value as a measured one.

Feature 003 already owns the analysis **pipeline** — request, fetch, parse once, retain byte-for-byte,
recompute on a version change, isolation, rate limits, legal basis — and stops deliberately at the
edge of this feature:

> **FR-043b**: The analysis MUST publish only what is read from the recording, and MUST NOT publish a
> quantity it reconstructed. … **That derivation is deferred to its own feature**, because it needs
> training durations that vary by civilisation, cancellation handling, and a stated accuracy claim
> for the one thing the log can never carry — what combat destroyed.

This is that feature, and its first half. It builds the **foundations** on which a reconstruction can
stand: what is knowable at all, a vocabulary for saying so, versioned game rules to reason with, and
a provenance spine that keeps a reconstruction from ever being mistaken for an observation. The
reconstruction engine itself — the time-indexed state, the invariants, the golden fixtures — is
feature 007, specified separately once this is clarified.

These foundations ship as **working, tested code, not as documents alone**: the register, the
truth-tier and provenance types, the canonical event vocabulary with an adapter that produces it, the
queryable knowledge base, the gap machinery and the validators. Every requirement below worded as
something the system MUST do is enforced by something that executes. The code stops where
reconstruction begins.

It does **not** re-specify any part of 003's pipeline. Where the two meet, 003 stands.

### What the reference replays actually proved

Two current-patch recordings were parsed directly during specification: the committed fixture
`tests/fixtures/replays/AgeIIDE_Replay_500546441.zip` (ranked 1v1) and a second recording supplied
for this mission (ranked 2v2, same game build). The measurements are recorded in
`docs/data-sources.md` and `specs/003-player-search-match-analysis/research.md`; this section states
only the consequences they force, not the numbers themselves.

- **A recording carries no outcome events of any kind.** The operation stream is `Sync`, `Viewlock`,
  `Chat`, `PostGame` and `Action`; the action vocabulary is entirely player intent — placement,
  queueing, research, movement, interaction, market, explicit deletion, resignation. There is no
  damage event, no death event, no completion event, no resource tick. Everything past "the player
  pressed a button" is reconstruction, and must be labelled as such.
- **Neither recording carries an `Achievements` post-game block.** `docs/data-sources.md` §2 records
  this as an open question and forbids building on either assumption until it is measured; it is now
  measured, across two recordings and two dates, and both say the same thing. The consequence is
  severe and load-bearing for everything below: **there is no in-replay ground truth** for units
  lost, resources collected, or final score — and therefore no anchor against which a resource
  reconstruction could be validated from the recording alone.
- **The starting state of the game is not exposed by any parser that works on the current build.**
  The primary engine returns the initial-state section as three scalar fields and stops; the
  secondary engine fails on this build at precisely that section, which is what ADR-0001 measured
  when it demoted it. Starting resources, starting objects, starting positions and the map's
  resource geometry — gold, stone, berries, huntables, forest — are consequently unreadable today.
  This blocks the income side of economy, and all of exploration, vision, information and map
  control, at the source rather than at the design. See **Important unresolved decisions**.
- **Terrain and elevation are fully readable**, tile by tile, for the whole map. Object placement on
  that terrain is not.
- **Duplicate commands are real, not theoretical.** A double-click issues the same command twice a
  fraction of a second apart, including on age-ups. The first-occurrence collapse the
  `replay-parsing` skill mandates fires in both recordings.

### Why unit loss is recorded as non-determinable

The mission's stated MVP goal was to determine as reliably as possible how many units each player
lost and when. It cannot be done from a recording, and the spec says so rather than approximating it.

A candidate heuristic was proposed in session — treat a unit as lost if it takes damage and then
performs no further action — and was measured against the 2v2 recording before being accepted or
rejected. It fails on both of its preconditions. Damage is not observable at all, so the first
clause can never be evaluated. And units do not act in the log; players issue commands that *mention*
unit identifiers, usually in multi-unit selections, so a unit leaves the log the moment its owner
stops including it in a selection — alive or dead. Applied with a several-minute silence window, the
rule declares the great majority of every player's units lost, which no game resembles; and it is
equally blind the other way, because a villager sent to a gather point and never individually
re-selected carries no identifier in the log at any point and can be neither counted nor declared
lost.

The underlying intuition survives, re-typed. "A group is commanded intensively and then goes
permanently silent" is a genuine observable — it is simply not a casualty count. It is retained at
the **inferred** tier under an honest name, as an engagement signal, carrying an explicit non-claim.

## Clarifications

### Session 2026-09-19

- Q: Starting state (resources, objects, positions, the resource map) is unreachable with any working
  parser today. How should this feature handle it? → A: Spike, then decide. This feature covers what
  is provably readable; the initial-state model is specified as a named deferred dependency with
  nothing invented in its place, plus a time-boxed research task evaluating the three real routes.
  Its outcome gates the income, spatial and vision tier — as evidence, never as a guess.
- Q: Military losses have no observable signal. How should the spec say so? → A: Record unit loss as
  non-determinable with its evidence, publish no loss figure, and state the one condition that would
  change the answer.
- Q: A heuristic was proposed — a unit that takes damage and then performs no further action is lost.
  Does it hold? → A: No; it was measured against the reference recording and refuted on both
  preconditions. It is re-typed to an inferred engagement observable, *loss of control over a group*,
  with a stated confidence and an explicit non-claim that it is not a casualty count. Explicit
  deletion and market transactions stay observed and exact.
- Q: How should the mission be cut into features? → A: Two. This feature is the versioned knowledge
  base, the canonical event model and the truth-tier and provenance spine. Feature 007 is the
  deterministic reconstruction, its invariants and its golden fixtures.
- Q: When this feature is merged, what has shipped — written artifacts only, or running code that
  enforces the rules? → A: Foundations in code. The register, the truth-tier and provenance types, the
  canonical event vocabulary with a working adapter, a queryable versioned knowledge base, the gap
  machinery and the validators that reject a mis-tiered value all ship as working, tested code. The
  code stops at the reconstruction boundary, which is feature 007.
- Q: Should the determinability register be a machine-readable file, a human-written document, or
  both? → A: A machine-readable register is the single source of truth, living with the package that
  enforces it. The human-readable view is generated from it, and a test asserts the two never diverge.
- Q: What form does a confidence take on an inferred or predicted value? → A: A closed, ordered set of
  named levels, and each value also states the basis for its level. No numeric probability is
  published until a calibration source exists, because a recording carries nothing to calibrate
  against and an uncalibrated number would be an invented value presented as a measured one.
- Q: How much of the game must the first knowledge snapshot cover for this feature to be done? → A:
  Whatever the committed reference recordings need. Every entity and civilisation those recordings
  reference is covered with zero blocking gaps; the rest of what the source provides is imported but
  validated only to the extent the recorded sampling states, and remaining holes surface as gaps.
- Q: What severity levels can a knowledge gap carry, and what does each do to publication? → A: Two,
  and the set is closed. Blocking — at least one publishable value depends on the missing knowledge,
  and every dependent value is withheld. Informational — no currently published value depends on it,
  nothing is withheld, and the gap only counts toward the aggregate rate. There is no level under
  which a value is published despite a missing input.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Know what can and cannot be known (Priority: P1)

Anyone building on this engine — the next feature, the next contributor, the next agent — can read a
single register that says, for every datum the product wants, whether it is read directly from the
recording, decoded from a payload, reconstructed by replaying the rules, derived from state,
inferred, or simply not determinable; and for the last case, why, and what would change the answer.

**Why this priority**: it is the precondition for everything else being honest. Every silent
assumption this project could make lives in the gap between what a recording appears to offer and
what it actually carries, and two of those gaps — the missing post-game statistics block and the
unreadable starting state — were found only by measuring. Without the register, the next person
rediscovers them by shipping a wrong number.

**Independent Test**: pick any datum the product intends to show a player, look it up in the
register, and confirm the register names its tier, its source, its dependencies and how it would be
validated — or states plainly that it cannot be known and why.

**Acceptance Scenarios**:

1. **Given** the register, **When** a reader looks up a datum the recording carries directly, **Then**
   they find its tier, the field it is read from, and the check that proves it is still there.
2. **Given** the register, **When** a reader looks up unit loss, **Then** they find it recorded as
   non-determinable, with the evidence, the impact on the analytics that wanted it, and the single
   condition that would change the answer.
3. **Given** a datum that depends on the unreadable starting state, **When** a reader looks it up,
   **Then** they find it blocked on a named dependency rather than offered with a caveat.

---

### User Story 2 - Ask the game's rules a question, for a stated patch and civilisation (Priority: P1)

The engine can ask what a unit costs, how long it takes to train, what a technology requires, when it
becomes available, and how a civilisation's bonuses change any of that — and get an answer that is
pinned to a specific version of the game and a specific version of the imported knowledge.

**Why this priority**: it is the other half of the foundation. A reconstruction is the command log
plus the rules; without versioned rules there is no reconstruction, only arithmetic on guesses. It is
also the half this repository has never had — the only structured game knowledge that exists today is
three hand-maintained identifier-to-name tables.

**Independent Test**: ask the knowledge base for a known unit's cost and training time on a named
game build for a named civilisation, and confirm the answer matches the game, carries its source, and
is reproducible from the committed snapshot without any network access.

**Acceptance Scenarios**:

1. **Given** a knowledge snapshot, **When** the engine asks for a unit's cost and training time for a
   stated civilisation, **Then** it receives the civilisation-adjusted value together with the
   snapshot identity that produced it.
2. **Given** two different knowledge snapshots, **When** the same question is asked of each, **Then**
   each answers from its own contents and neither is silently upgraded to the other.
3. **Given** a running test suite, **When** the knowledge base is queried, **Then** no network call is
   made, by the tests or by anything they exercise.

---

### User Story 3 - Every number says where it came from (Priority: P1)

Every published value carries its tier in the truth hierarchy, the method that produced it, and —
where the tier admits doubt — a confidence. A reader can always tell an observation from a
reconstruction, and a reconstruction from an interpretation.

**Why this priority**: it is what stops the product from lying as it grows. The moment coaching sits
on top of reconstruction, the temptation is to let a confident-sounding inference occupy the same
field as a measured fact. Making the tier a property of the datum, rather than a paragraph in a
document, is the only version of this rule that survives contact with a schema.

**Independent Test**: take any published analysis document and confirm that no value appears without
a tier, and that a value at the inferred or predicted tier also carries a confidence.

**Acceptance Scenarios**:

1. **Given** a published analysis, **When** any value is inspected, **Then** it carries its tier and
   the method that produced it.
2. **Given** a value produced by interpretation or prediction, **When** it is inspected, **Then** it
   also carries a confidence, and its wording does not present it as measured.
3. **Given** an attempt to publish a coaching conclusion into a field typed as observed or
   reconstructed, **When** the document is validated, **Then** it is rejected.

---

### User Story 4 - One event vocabulary, whichever parser is running (Priority: P2)

The engine consumes a stable, engine-independent stream of canonical events. When the parser changes
— and it has changed once already — the adapter changes and nothing above it does.

**Why this priority**: the pluggable engine is constitutional, and the reason is a lived one: a game
patch broke the previous primary parser and left it broken for six months, which also killed one of
the community data sources this project had counted on. Everything built on the raw shape of one
wheel's output inherits that risk.

**Independent Test**: produce the canonical event stream for the reference recording, then confirm
that the vocabulary contains no field whose name or shape is specific to the running engine.

**Acceptance Scenarios**:

1. **Given** a recording, **When** the canonical stream is produced, **Then** every event carries a
   match-clock time, the participant it belongs to, its kind, and its tier.
2. **Given** a command the game issues twice because the player double-clicked, **When** the stream is
   produced, **Then** it appears once.
3. **Given** a command whose meaning the current engine does not decode, **When** the stream is
   produced, **Then** it is represented as an undecoded event of known kind rather than dropped
   silently or guessed at.

---

### User Story 5 - A missing rule stops the analysis instead of corrupting it (Priority: P2)

When the knowledge base lacks something a reconstruction needs — a research time for a technology on
a given patch, a civilisation's modification of a cost — the engine records a knowledge gap, explains
what the gap prevents, and refuses to produce the affected value rather than substituting a plausible
one.

**Why this priority**: an engine that quietly fills its own holes is worse than one that stops,
because the hole becomes invisible the moment it is filled. This is the mechanism that makes the rest
of the truth hierarchy enforceable rather than aspirational.

**Independent Test**: remove a required field from a knowledge snapshot, run an analysis that needs
it, and confirm the affected value is absent and a gap is recorded with its impact and severity —
and that unaffected values are still produced.

**Acceptance Scenarios**:

1. **Given** a knowledge snapshot missing a field a reconstruction needs, **When** the analysis runs,
   **Then** a gap is recorded naming the entity, the field, the game build and the affected
   civilisation, with its impact and severity.
2. **Given** a gap of blocking severity, **When** the analysis runs, **Then** the values that depend on
   it are not published at all, and the values that do not depend on it still are.
3. **Given** a recorded gap, **When** a maintainer reads it, **Then** it says what it prevents, not
   merely that something is missing.

---

### User Story 6 - An analysis stays reproducible after everything underneath it moves (Priority: P3)

An analysis produced today can be reproduced exactly tomorrow, after the parser has been upgraded,
the game has been patched and the knowledge base has been refreshed. New versions produce new
analyses; they never destroy or silently rewrite old ones.

**Why this priority**: it is the property that makes the whole edifice trustworthy over time, but it
only becomes observable once there is more than one version of anything. It is specified now because
retrofitting identity onto published artifacts is far harder than designing it in.

**Independent Test**: produce an analysis, record its full identity, refresh the knowledge base to a
new snapshot, reproduce the analysis from the original identity, and confirm the two are identical.

**Acceptance Scenarios**:

1. **Given** the same recording, parser version, knowledge version and engine version, **When** the
   analysis is produced twice, **Then** the two results are identical.
2. **Given** a refreshed knowledge base, **When** an older analysis is reproduced from its recorded
   identity, **Then** it reproduces exactly and the newer snapshot is not substituted.
3. **Given** a new knowledge version, **When** it is published, **Then** the previous version remains
   available and every analysis that names it remains reproducible.

### Edge Cases

- What happens when a recording is from a game build the knowledge base has no snapshot for? The
  build is not silently mapped to the nearest snapshot; it is a gap of blocking severity.
- What happens when an imported source changes a value for a patch that has already shipped analyses?
  A new snapshot is created; existing analyses keep naming the old one and keep reproducing.
- What happens when the two knowledge sources disagree about the same field? The disagreement is
  recorded rather than resolved by precedence alone, and the field carries which source it came from.
- What happens when a command carries an identifier the knowledge base cannot name? It degrades to
  the bare identifier — a confident wrong name is worse than a bare id (002, 003 FR-043a).
- What happens when a player resigns, or the recording ends mid-production? Events after the
  participant's exit are not attributed to them, and an unfinished production is not counted as
  completed.
- What happens when a participant is an observer or an absent slot? They yield no participant
  timeline rather than an empty one that reads as a player who did nothing.

## Requirements *(mandatory)*

### The determinability register

- **FR-001**: The project MUST maintain a register that classifies every datum the product intends to
  publish into exactly one of: observed, decoded, reconstructed, derived, inferred, predicted, or
  non-determinable.
- **FR-002**: Each register entry MUST state its source, the algorithm or decoding that produces it,
  the knowledge it requires, what it depends on, and how it is validated.
- **FR-003**: Each non-determinable entry MUST state why it cannot be known, what it costs the
  analytics that wanted it, whether an approximation exists, and whether that approximation is
  acceptable — and MUST NOT leave the last question unanswered.
- **FR-004**: The register MUST record unit loss as non-determinable, citing the absence of any damage
  or death event and the absence of a post-game statistics block in both measured recordings
  (`docs/data-sources.md` §2, session 2026-09-19), and MUST name the single condition that would
  change the answer.
- **FR-005**: The register MUST cover every datum this feature and feature 007 intend to publish, and
  MUST mark as blocked — not as approximate — every datum that depends on the unreadable starting
  state.
- **FR-006**: A datum MUST NOT be published by any part of the system unless it has a register entry,
  and an automated check MUST fail when a publishable field has none.
- **FR-006a**: The register MUST exist as a single machine-readable source of truth, kept with the
  package that enforces it. The human-readable view MUST be generated from that source, never
  maintained by hand, and an automated check MUST fail when the two diverge.

### The truth hierarchy, materialised

- **FR-007**: Every published value MUST carry its tier as data, not as documentation.
- **FR-008**: The tiers MUST be ordered and closed: observed, decoded, reconstructed, derived,
  inferred, predicted. A value MUST NOT carry a tier stronger than the weakest input it was computed
  from.
- **FR-009**: Every published value MUST carry the method that produced it, in a form that lets a
  reader recompute it.
- **FR-010**: Every value at the inferred or predicted tier MUST carry a confidence, and MUST be named
  and worded so it cannot be read as a measurement.
- **FR-010a**: A confidence MUST be one of a closed, ordered set of named levels, and MUST state the
  basis for its level — the evidence that placed it there. A numeric probability MUST NOT be published
  as a confidence until a calibration source exists and is recorded in the register; a recording
  carries no outcome against which one could be calibrated.
- **FR-011**: A value produced by the coaching or expected-trajectory layer MUST NOT be writable into
  a field typed observed, decoded or reconstructed. Validation MUST reject a document that does so.
- **FR-012**: The naming discipline established by 003 MUST hold across the whole vocabulary: a name
  MUST state what was measured, never what a reader would like it to mean — `age_up_commands` rather
  than `age_up_times`, `villagers_ordered` rather than `villagers` (003 FR-043b).
- **FR-013**: The *loss of control over a group* observable MUST be published only at the inferred
  tier, MUST carry a confidence, and MUST carry an explicit statement that it is not a casualty count
  (session 2026-09-19).
- **FR-014**: Explicit deletions and market transactions MUST be published at the observed tier and
  MUST NOT be blended into any inferred quantity.

### The canonical event model

- **FR-015**: The system MUST define an engine-independent canonical event vocabulary, and everything
  above the adapter MUST consume only that vocabulary (constitution V).
- **FR-016**: Every canonical event MUST carry a match-clock time, the participant it is attributed
  to, its kind, and its tier.
- **FR-017**: The canonical vocabulary MUST NOT contain a field whose name, shape or offset is
  specific to any one engine's output.
- **FR-018**: A command the game emitted more than once for a single player action MUST appear once in
  the canonical stream, collapsed to its first occurrence.
- **FR-019**: A command the running engine does not decode MUST be represented as an undecoded event
  of known kind, never dropped silently and never guessed at.
- **FR-020**: The canonical event model MUST accommodate events that the current engine cannot yet
  produce — those depending on the starting state — without requiring the vocabulary to be redesigned
  when they become available.
- **FR-021**: Producing the canonical stream MUST NOT retain the raw operation stream, honouring the
  memory bound that `specs/003-player-search-match-analysis/contracts/analysis.md` already makes part
  of the extraction contract.

### The versioned knowledge base

- **FR-022**: The system MUST provide a knowledge base covering, at minimum: units, buildings,
  technologies, their costs, their training, construction and research times, their age requirements
  and prerequisites, civilisations, and the civilisation bonuses that modify any of the above.
- **FR-022a**: The first knowledge snapshot MUST cover every entity and every civilisation referenced
  by each committed reference recording, such that analysing those recordings records no gap of
  blocking severity. Beyond that set, what the source provides MAY be imported without exhaustive
  validation, provided the validation actually performed is recorded (FR-030) and any absent field
  surfaces as a gap rather than as a value. Exhaustive coverage of the game is not a completion
  condition of this feature.
- **FR-023**: Every knowledge answer MUST be qualified by game build and by civilisation where the
  game qualifies it, and MUST NOT return a generic value where a civilisation-specific one exists.
- **FR-024**: A knowledge snapshot MUST have an identity composed of its source, that source's own
  version, the game build it describes, and a digest of its contents.
- **FR-025**: Publishing a new knowledge snapshot MUST NOT modify or remove any existing one.
- **FR-026**: The knowledge base MUST be queryable without any network access, including from the test
  suite (constitution III, 002 FR-011).
- **FR-027**: A recording whose game build has no snapshot MUST NOT be silently analysed against the
  nearest available snapshot; the absence MUST be recorded as a gap.
- **FR-028**: Where two sources disagree on a field, the knowledge base MUST record the disagreement
  and MUST carry which source the stored value came from.

### Knowledge sources and their licences

- **FR-029**: Every knowledge source MUST be documented with its scope, its reliability, its update
  mechanism, its version identifier, its coverage and its known limitations, and the date that
  assessment was made (002).
- **FR-030**: A source MUST NOT be treated as authoritative without validation against the game or
  against a second source; the validation performed MUST be recorded.
- **FR-031**: Only a source whose licence permits it MAY be vendored into this repository. A source
  with no licence MUST NOT be vendored, MUST NOT be fetched at build or test time, and MAY only be
  consulted by a human whose transcription is recorded with its provenance (002 research).
- **FR-032**: Nothing in the running system, its build, or its tests may fetch a knowledge source
  (002 FR-011). Any refresh MUST happen outside the request path and MUST go through
  `packages/providers` (constitution III).
- **FR-033**: A vendored knowledge pack MUST carry its licence record in the repository, in the form
  the existing asset-pack check already enforces (constitution X).
- **FR-034**: Refreshing a source MUST follow the sequence: source change, new snapshot, validation,
  new knowledge version — and MUST NOT promote an unvalidated snapshot.

### Knowledge gaps

- **FR-035**: The system MUST record a knowledge gap naming the entity, the field, the game build and
  the affected civilisation whenever a required piece of knowledge is absent.
- **FR-036**: A gap MUST state what it prevents, not merely that something is missing.
- **FR-037**: A gap MUST carry a severity drawn from a closed set of exactly two levels. A **blocking**
  gap is one on which at least one publishable value depends; it MUST prevent publication of every
  value that depends on it while leaving independent values unaffected. An **informational** gap is
  one on which no currently published value depends; it withholds nothing and counts only toward the
  aggregate report (FR-039). No severity MAY permit a value to be published while an input it depends
  on is missing (FR-038).
- **FR-038**: The system MUST NOT substitute a default, an average or a neighbouring value for missing
  knowledge under any circumstances.
- **FR-039**: Gaps MUST be reportable in aggregate, so that a pattern of gaps introduced by a game
  patch is visible as a rate rather than discovered one analysis at a time — the discipline the
  `replay-parsing` skill already applies to quarantine.

### Reproducibility and versioning

- **FR-040**: A published analysis MUST be identified by its recording, its parser name and version,
  its parser dependencies, its knowledge version, its reconstruction engine version and its analytics
  version (constitution IV).
- **FR-041**: Identical inputs across all of those identities MUST produce an identical result.
- **FR-042**: A new parser, patch, knowledge version or analytics version MUST produce a new analysis
  and MUST NOT destroy or rewrite an existing one.
- **FR-043**: An analysis MUST be reproducible from its recorded identity and the retained recording
  alone, reaching no external source (003 FR-041).
- **FR-044**: The parser dependency record that the `replay-parsing` skill requires MUST actually be
  populated; a published analysis MUST NOT record an empty dependency set while claiming to identify
  its engine.

### Corrections owed to existing documents

- **FR-045**: `docs/data-sources.md` §2 MUST be updated to record that the post-game statistics block
  is absent from current-patch ranked recordings, corroborated across more than one recording and
  more than one date, replacing the open question it states today.
- **FR-046**: `.claude/skills/replay-parsing/SKILL.md` and `docs/adr/0001-replay-parser.md` MUST be
  corrected to name the paths that exist — the adapter at
  `packages/replay-engine/src/aoe2stats_replay_engine/aoe2rec.py` and the protocols at
  `packages/core/src/aoe2stats_core/replay/` — in place of a path that was never created.
- **FR-047**: `.claude/skills/replay-parsing/SKILL.md` MUST be corrected where it states that the
  placement command carries no player identifier; the pinned engine does supply it, as
  `packages/replay-engine/tests/test_aoe2rec.py` measures, and only the building identifier requires
  decoding.

### Boundaries with feature 003

- **FR-048**: This feature MUST NOT re-specify 003's pipeline — request, fetch, parse-once, retention,
  recompute, isolation, rate limiting or legal basis. Where they meet, 003 stands.
- **FR-049**: This feature MUST NOT add a scheduled job to the request path, and MUST NOT let its work
  consume the budget that replay capture depends on (003 FR-039, FR-044, constitution I).

### Key Entities

- **Determinability entry**: one record in the machine-readable register, classifying one datum — its
  tier, source, algorithm, required knowledge, dependencies, validation strategy, and for a
  non-determinable datum the reason, impact, possible approximation and whether that approximation is
  acceptable.
- **Truth tier**: the closed, ordered vocabulary observed → decoded → reconstructed → derived →
  inferred → predicted, carried by every published value.
- **Provenance**: the tier, the method, the inputs and the versions that produced one value.
- **Confidence**: the qualification attached to any value at the inferred or predicted tier — one of a
  closed, ordered set of named levels, together with the basis for that level. Never a bare number.
- **Canonical event**: one engine-independent occurrence — match-clock time, participant, kind,
  payload, tier.
- **Knowledge snapshot**: one immutable, validated body of game rules, identified by source, source
  version, game build and content digest.
- **Knowledge gap**: one absent required field — entity, field, game build, civilisation, impact, and
  a severity that is either blocking or informational.
- **Analysis identity**: the full tuple that makes a published analysis reproducible.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every datum the product intends to publish has a register entry: the count of publishable
  data without one is zero.
- **SC-002**: No published value lacks a tier, no value at the inferred or predicted tier lacks a
  confidence, and no confidence lacks its basis or falls outside the closed set of levels: all three
  counts are zero.
- **SC-003**: A document that places a coaching conclusion in a field typed observed, decoded or
  reconstructed is rejected by validation, every time it is attempted.
- **SC-004**: The same recording analysed twice with identical versions yields a byte-identical
  result.
- **SC-005**: An analysis recorded before a knowledge refresh reproduces exactly after it, with the
  older snapshot still resolvable.
- **SC-006**: The test suite makes no network call while exercising the knowledge base: the count of
  outbound requests is zero.
- **SC-007**: Removing a required field from a snapshot causes the dependent values to be withheld and
  a gap to be recorded, while every independent value is still produced.
- **SC-007a**: Analysing each committed reference recording against the first knowledge snapshot
  records zero gaps of blocking severity.
- **SC-008**: No value is ever published with a substituted default in place of missing knowledge: the
  count of substitutions is zero, by construction rather than by inspection.
- **SC-009**: The canonical event stream for a reference recording contains no field specific to the
  running engine.
- **SC-010**: A command the game emitted twice for one player action appears once in the canonical
  stream.
- **SC-011**: No published analysis claims to identify its engine while recording an empty dependency
  set.
- **SC-012**: A reader of the register can answer "can this be known, and how would I check?" for any
  publishable datum without reading code.
- **SC-013**: No number measured in this specification is restated anywhere else in the repository;
  each lives in exactly one home and is referenced from the others.

## Assumptions

- **A recording is a command log, not a state log, and this feature treats that as permanent.** The
  measured absence of outcome events is a property of the format, not of the parser, so no future
  engine upgrade is assumed to supply them. If one ever does, the register is where that changes
  first.
- **The absence of a post-game statistics block is now corroborated, not assumed.** Two current-patch
  recordings, from different dates and different match sizes, agree. This meets the bar the
  constitution sets for treating a measured property as settled, and FR-045 moves it into
  `docs/data-sources.md`, which remains its only home. This specification restates no measurement;
  where a quantity matters it is referenced from the document that owns it.
- **The starting state is assumed unreadable until proven otherwise**, and everything depending on it
  is blocked rather than approximated. See **Important unresolved decisions** — this is the one
  assumption designed to be overturned, and the mechanism for overturning it is specified.
- **Feature 003's pipeline is assumed correct and in place.** This feature consumes retained
  recordings and the parse-once discipline; it does not re-litigate them. Its published output is
  expected to arrive as a new document version under 003's existing versioning seam, which that
  feature's contract already anticipates.
- **The repository has no versioned reference-data pattern to extend.** Feature 002 deliberately
  shipped no schema and remains largely unimplemented; what it does supply, and what is treated as
  binding here, is its licence rulings and its per-entry provenance discipline. The versioning
  precedent being extended is the constitutional one — tool version recorded on every derived
  artifact, fully recomputable from the raw.
- **Only one game title is in scope.** Age of Empires II: Definitive Edition, current and future
  builds. Historical analyses must survive future patches, which is why knowledge is versioned by
  build rather than tracked to a single current state.
- **Coaching is assumed to be built strictly above this layer and never beneath it.** No requirement
  here may be satisfied by a value that a coaching model produced, and FR-011 makes that enforceable
  rather than advisory.

## Out of Scope

- The deterministic reconstruction itself — the time-indexed state, the resource decomposition, the
  age-up model, the reconstruction invariants and the golden fixtures. That is feature 007.
- Every analytics layer: economy, military, exploration, information, map control, advantage timeline.
- Strategic inference: phases, transitions, pressure models, opportunity detection.
- Coaching: expected trajectory, actual versus expected, empirical calibration, recommendations.
- Any combat simulation. The engine does not reproduce pathfinding, targeting or damage resolution.
- Any single combined advantage score. The dimensions stay separate until there is a defensible way
  to combine them.
- The empirical high-level-game corpus. The community source that would supply it has published
  nothing since the breakage recorded in `docs/data-sources.md` §4.
- Anything requiring the starting state, for as long as it remains unreadable.
- Re-specifying feature 003's pipeline.

## Important unresolved decisions

**Whether the starting state can be read at all.** Everything in the income side of economy, and all
of exploration, vision, information and map control, depends on it. Three routes exist and exactly one
question needs answering before feature 007 can be scoped honestly:

1. A community fork of the secondary engine carrying the unmerged fixes named in ADR-0001.
2. The alternative fast implementation ADR-0001 already lists as a fallback.
3. A repository-local byte-level decoder for that section, in the same mould as the placement decoder
   this repository already derived empirically and golden-tested.

This is a time-boxed research task, resolved at `/speckit-plan` and reported in `research.md`. Until it
reports, nothing that depends on the starting state is specified, approximated or promised. Its
outcome decides whether feature 007 covers the spatial and income tier or stops at the spending side.

**Whether the second reference recording becomes a committed fixture.** It is the only available 2v2
and the only current-patch corroboration of FR-045, which argues for committing it. Two conditions
must be settled rather than assumed: the repository admits only zipped recordings under its fixtures
directory, so the file would have to be repackaged, meaning the committed bytes are ours rather than
the ones the source served — unlike the existing fixture, whose value rests partly on being verbatim;
and constitution IX governs retaining a recording naming real players. Decided at `/speckit-plan`.

## Risks

- **A game patch changes the rules the knowledge base encodes, and historical analyses drift.**
  Mitigated by versioning knowledge per build and retaining every snapshot; the residual risk is a
  patch that changes a rule without changing anything the snapshot identity can see.
- **A game patch breaks the parser again.** This has happened, it cost six months, and it is already
  in the risk register. The canonical event model is the insulation; its value is only realised if
  nothing above the adapter reaches around it.
- **The memory envelope.** Parsing a single recording already consumes a large fraction of the
  available headroom, and feature 007's reconstruction sits on top of that, not beside it. The
  existing raw-size refusal is a memory bound, not a zip-bomb guard, and it was sized against parsing
  alone. Feature 007 must re-derive it rather than inherit it.
- **The knowledge sources are community-maintained and may stop.** One source this project counted on
  has already gone silent. Mitigated by vendoring what the licence permits, so a snapshot survives its
  source's disappearance.
- **Scope pressure from the coaching goal.** The product vision reaches far past what a recording can
  support, and the pull will be to fill gaps with plausible inference. FR-011, FR-038 and the register
  exist specifically to make that visible when it is attempted.
