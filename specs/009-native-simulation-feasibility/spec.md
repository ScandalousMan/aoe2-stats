# Feature Specification: Native AoE2 Simulation Extraction Feasibility

**Feature Branch**: `009-native-simulation-feasibility`

**Created**: 2026-11-08

**Status**: Draft

**Input**: User description: "Native AoE2 simulation extraction feasibility: a dedicated, isolated
technical feasibility spike (not a product feature) that investigates and experimentally validates
whether the actual simulated state of an Age of Empires II: DE match can be recovered from a
`.aoe2record` by running it through the game's own engine (the AoE2 DE gRPC interface documented
by LibreMatch, as used by CaptureAge), through the `librematch/genie` Rust engine, or through
another existing simulation route, instead of inferring it from the command log."

## What this feature is, and is not

This is a **technical feasibility spike**. It produces evidence and a recommendation; it ships no
product capability, changes no functional requirement of any other feature, and integrates nothing
into the running application. Its outcome is an informed architectural decision: whether the
platform's match analysis can rest on what the game's simulation actually did, instead of on what
the command log lets us infer.

The question it answers was put plainly by the repository owner on 2026-11-07: a tool such as
CaptureAge states with precision which building was built or destroyed, which technology was
researched or cancelled, which unit died, and the population at any instant, while this project's
reconstruction (feature 008) can only deduce those things from commands. Feature 006 measured that a
recording carries player intent and no outcomes (`docs/data-sources.md` §2 and 006's research);
CaptureAge gets its facts by riding on the game's own deterministic simulation. This spike
establishes whether that simulation, or a faithful substitute, is reachable by this project.

**Nothing in this spike may be read as a constraint inherited from the current parser
architecture.** The investigation treats the current command-based approach as one candidate
among several, and treats its documented limitations as claims to be re-examined, not as settled.

## User Scenarios & Testing _(mandatory)_

### User Story 1 - The owner decides the architecture on evidence (Priority: P1)

The repository owner needs to decide whether to keep building deterministic reconstruction from
the command log (feature 008), to re-found match analysis on the game's own simulation, or to do
neither. They open one report and one capability matrix, both in the repository, and find for each
gameplay fact they care about (unit creation and death, building placement, progress, completion
and destruction, technology research, completion and cancellation, population, resource stocks,
gathering and spending, production queues, age advancement) whether it is obtainable exactly, by
which route, with what evidence, under which limitations, and what it would cost to operate. The
report ends with one of five recommendations and a GO, CONDITIONAL GO or NO-GO decision, each
condition listed.

**Why this priority**: it is the whole point. Every other deliverable exists to make this decision
trustworthy. Without it, feature 008's spec cannot be amended or confirmed, and the roadmap stays
built on a premise the owner has challenged.

**Independent Test**: a reader who has not followed the investigation opens
`docs/research/native-simulation-feasibility.md` and
`docs/research/native-simulation-capability-matrix.md`, finds every important claim tied to a
source or an experiment, can tell for every gameplay fact whether it was demonstrated, documented
only, derived or unavailable, and finds a single explicit decision with its conditions.

**Acceptance Scenarios**:

1. **Given** the report and matrix are merged, **When** the owner reads the matrix row for "unit
   death", **Then** the row states availability, the approach that provides it, whether it is
   exact, how it is extracted, the evidence (experiment or source) and the limitations, and the
   provenance category is one of the six defined below.
2. **Given** a claim in the report that a capability exists, **When** the owner follows its
   reference, **Then** the reference is either a cited source or an experiment recorded in the
   repository, and the claim is labelled as documented or as demonstrated accordingly.
3. **Given** the report's conclusion, **When** the owner reads it, **Then** it names exactly one of
   A (official engine through gRPC), B (Genie), C (hybrid), D (command-based reconstruction for
   explicitly limited use cases) or E (no viable solution demonstrated), and exactly one of GO,
   CONDITIONAL GO or NO-GO, with every condition of a CONDITIONAL GO listed.
4. **Given** an approach that could not be exercised because the environment lacks what it needs,
   **When** the owner reads about it, **Then** the report names precisely what was blocked, states
   that no experiment ran, and gives the minimum setup that would unblock it; it never presents an
   unexecuted experiment as a result, and never presents an incomplete prototype as proof of
   impossibility.

---

### User Story 2 - An engineer reproduces the experiment (Priority: P2)

An engineer, later, wants to repeat or extend the experiment: run a real recording through the
chosen simulation route, extract timestamped observations, and compare them against an
independent reference. They find an isolated prototype with its setup and execution instructions,
sample output, known limitations and automated checks where possible, kept apart from the
production application; or, where the environment made the experiment impossible, an exact
description of the blocked step and the minimum environment that would unblock it.

**Why this priority**: evidence that cannot be reproduced is an opinion with a date on it. The
decision in story 1 is only as durable as the experiment behind it, and the game is patched
regularly, so the experiment will have to be re-run.

**Independent Test**: following the prototype's instructions on an environment that meets its
stated prerequisites processes at least one of the committed reference recordings and produces a
structured dataset in which every observation carries a timestamp and a provenance category; or,
where the prerequisites are unavailable, the instructions name the missing prerequisite exactly.

**Acceptance Scenarios**:

1. **Given** an environment meeting the prototype's prerequisites, **When** the engineer runs it
   on a committed reference recording, **Then** it emits a structured dataset of timestamped
   observations, each with a provenance category and the identity of the recording processed.
2. **Given** the same recording run twice, **When** the two datasets are compared, **Then** the
   report records whether event sequences, object identities, timestamps, resource values and the
   final state are identical, and explains every difference found.
3. **Given** an environment that lacks a prerequisite (for example, the game is not installed, or
   there is no Windows host), **When** the engineer reads the prototype's documentation, **Then**
   it names the prerequisite, the step it blocks, and the smallest setup that would supply it.

---

### User Story 3 - An independent reviewer checks the conclusions (Priority: P3)

Before the owner relies on the report, someone who did not write it challenges every unsupported
assumption and separates what was shown to work from what a document says. Their assessment is
recorded with the report.

**Why this priority**: the investigation is run by the same party whose earlier design the owner
challenged. A review that was not independent would inherit the same blind spots.

**Independent Test**: the report carries a reviewer's assessment that lists which claims were
verified against their evidence, which were downgraded (for example from demonstrated to
documented), and which remain unknown, and the body of the report reflects those outcomes.

**Acceptance Scenarios**:

1. **Given** a draft report, **When** the reviewer finds a capability stated as available without
   an experiment or a source, **Then** the final report either supplies the evidence or relabels
   the capability as documented, inferred or unknown.
2. **Given** the reviewer's assessment, **When** the owner reads the report, **Then** the
   assessment is present, dated, and distinguishes documented from demonstrated capabilities.

---

### Edge Cases

- The game cannot run on the developer's machine (the developer works on macOS; the game targets
  Windows), and no Windows host is available: the approach that needs the running game is
  documented as environmentally blocked, with the exact minimum setup, and the decision says so.
- An interface exists but exposes less than the full state (for example, snapshots without
  events, or events without ownership): the matrix records each fact separately and never lets the
  existence of the interface stand in for the availability of a fact.
- An engine reimplementation reads the recording format but does not simulate gameplay, or
  simulates gameplay for an older game build: the report lists the missing subsystems and the build
  gap rather than declaring the engine viable or non-viable on its description.
- The reference build (185872) is no longer the current game build: the report records which build
  is installed or available, which builds each interface supports, and every compatibility limit
  found, and does not assume compatibility from an older build.
- Two runs of the same recording differ: the difference is recorded and explained; the
  determinism criterion is reported as failed, not omitted.
- An event-based mechanism can lose events between observations or across a disconnection: the
  report says so and treats any extraction that silently loses events as not meeting the
  completeness requirement.
- A route is technically possible but barred by a licence, usage rules or terms of service: the
  legal bar and the technical finding are recorded separately, and neither is softened to fit the
  other.
- CaptureAge offers no export: it is used only as a visual reference where possible, and the
  report never relies on an assumed export API.

## Requirements _(mandatory)_

### Functional Requirements

**Investigation scope**

- **FR-001**: The investigation MUST assess three approaches: A, the official game engine reached
  through the gRPC interface documented by LibreMatch and its relationship to CaptureAge; B, the
  `librematch/genie` engine; C, any other existing route that provides actual simulation or
  access to actual game state. It MUST NOT spend effort cataloguing replay parsers that provide
  neither.
- **FR-002**: For approach A the report MUST answer, each labelled as documented, demonstrated,
  inferred or unknown: whether an external application can connect while the game replays a
  recording; whether that is possible without CaptureAge; whether playback can be started,
  controlled, paused, resumed, sought or restarted programmatically; what state is exposed; whether
  snapshots are complete or incremental; whether objects carry stable identities, ownership, type,
  position, health and lifecycle; whether unit creation and death, building placement, progress,
  completion and destruction, technology research, completion and cancellation, resource stocks and
  population at precise simulation times, gathering and actual expenditure, production queues, and
  events not represented by any command are observable; and whether the interface suffices to
  reconstruct a whole match.
- **FR-003**: For approach B the report MUST establish from the source code and tests, not from
  the project description alone: whether it loads `.aoe2record` files and for which builds; whether
  its simulation is deterministic; which mechanics are implemented and which commands or situations
  are unsupported; whether it reconstructs complete states and can expose snapshots or events;
  whether it runs headlessly; its performance on a full match; what supporting build 185872 would
  require; the maintenance cost of following game updates; and its licensing implications.
- **FR-004**: For every capability assessed under any approach, the report MUST classify it as
  directly exposed, reconstructable from successive snapshots, reconstructable from an event
  stream, requiring additional inference, or not available.
- **FR-005**: The investigation MUST verify the game build situation: whether build 185872 is
  still available, the exact build of any installed copy that is accessible, whether each
  investigated interface supports it, and every compatibility limit found.

**Environment and experiment**

- **FR-006**: The investigation MUST record the development environment assessed (operating
  system, hardware, whether the game is installed, whether a Windows environment is accessible,
  available builds, available recordings, relevant tooling) and MUST state whether native
  execution, a Windows machine or virtual machine, or remote Windows execution is required, and
  whether extraction could run on a machine separate from the application.
- **FR-007**: Where the required environment is available, the investigation MUST implement a
  minimal, isolated prototype that connects to or drives the simulation route, detects or initiates
  playback, receives state, decodes the relevant objects and events, stores timestamped
  observations and exports a structured dataset. The prototype MUST stay outside the production
  application and its packages, and MUST NOT become a production integration.
- **FR-008**: Where the required environment is unavailable, the investigation MUST document
  precisely which step is blocked and the minimum setup needed to continue, and MUST NOT report any
  experiment as executed.
- **FR-009**: Experiments MUST run on real recordings, never synthetic data. The corpus MUST hold
  between three and five recordings, preferring coverage of economic development, several age
  advancements, different civilisations, several building constructions, military production and
  combat, unit deaths, building destruction, technology research, technology cancellation where
  available, and different durations. For each recording the report MUST record its identity or
  checksum, game build, map, civilisations, player count, duration and the gameplay scenarios it
  covers.
- **FR-010**: The validation MUST cover these scenarios, each with its required evidence: unit
  creation (actual creation and timestamp); unit death (actual death and owner); building
  construction (placement, progress, completion); building destruction (object identity, owner,
  destruction); technology research (start, completion, cancellation); population (exact value at
  selected timestamps); resources (actual stocks at selected timestamps); gathering (actual stock
  changes and gathering information where exposed); production queues (actual queued and completed
  production); age advancement (actual transition and timestamp). For every test the report MUST
  record the expected observation, the extracted data, the source, the timestamp, whether the
  result is exact, and any ambiguity or missing information.
- **FR-011**: CaptureAge MAY be used as an independent visual reference; it MUST NOT be a required
  dependency and the report MUST NOT assume it exposes an export interface.

**Accuracy, determinism and completeness**

- **FR-012**: Every extracted field MUST carry one provenance category: `ENGINE_STATE` (read from a
  game-state snapshot), `ENGINE_EVENT` (reported by the simulation), `DETERMINISTIC_DERIVATION`
  (calculated exclusively from verified engine data), `COMMAND_LOG` (from the replay's command
  log), `INFERRED` (estimated or deduced) or `UNAVAILABLE` (cannot be established). An inferred
  value MUST NEVER be classified as an engine observation.
- **FR-013**: The same recording MUST be replayed more than once and the event sequences, state
  snapshots, object identities, timestamps, resource values and final state compared; the report
  MUST state whether the results are identical and explain every difference.
- **FR-014**: The report MUST establish the time resolution of each interface and MUST distinguish
  simulation ticks, game time, wall-clock time and playback time; it MUST NOT treat timestamps from
  different sources as interchangeable without showing they are.
- **FR-015**: The report MUST state whether each interface provides full snapshots, incremental
  updates, events that can be missed between observations, recovery after a disconnection, and a
  complete final state; an event-based mechanism that can silently lose events MUST be reported as
  such.

**Architecture, operations, licensing**

- **FR-016**: The report MUST evaluate, without committing to it, an architecture in which a
  replay execution adapter (the official engine, or an alternative) feeds a simulation extraction
  layer, which produces a normalised state and event model, persisted as match data, consumed by a
  deterministic analysis engine; the extraction layer SHOULD be independent of the simulation
  provider, and the possibility of running extraction on a machine separate from the application
  MUST be preserved.
- **FR-017**: The operational assessment MUST cover the replay execution lifecycle, error handling
  and retry, version compatibility, storage needs, extraction speed, processor and memory needs,
  parallelism, the cost of operating a Windows extraction machine, scalability for several users,
  and security and isolation, and MUST NOT introduce infrastructure the findings do not call for.
- **FR-018**: For every external dependency the report MUST record its licence, redistribution
  requirements, copyleft obligations, commercial-use restrictions, whether it needs game source or
  assets, whether it relies on undocumented interfaces, and whether a game update could change the
  interface. Technical risk and legal risk MUST be recorded separately. The investigation MUST NOT
  extract, redistribute or embed the publisher's game assets or executable code, and MUST NOT read
  an open-source licence on a reverse-engineering project as a grant of rights over the
  publisher's components.

**Governance**

- **FR-019**: Before any change, the investigation MUST inspect the constitution, the specifications
  that govern replay parsing, reconstruction and analysis (features 003, 006 and 008), the current
  implementation and tests, and MUST list every constraint that bears on the investigated routes
  (at least: external calls only through providers; portability across the two hosting phases; the
  non-commercial condition and the rejected extraction of the game's data file; parsing in an
  isolated, pluggable engine).
- **FR-020**: This spike MUST NOT rewrite any existing functional specification, remove or weaken
  any accuracy requirement to fit a technical limit, implement the target architecture, or make
  unrelated changes. Amendments to other features follow the decision; they are not part of it.
- **FR-021**: An independent reviewer MUST assess the findings before they are reported, challenging
  unsupported assumptions and distinguishing documented from demonstrated capabilities; the
  assessment MUST be recorded with the report.
- **FR-022**: The report MUST conclude with exactly one recommendation among A, B, C, D and E and
  exactly one decision among GO, CONDITIONAL GO and NO-GO. GO requires experimental evidence that
  the approach recovers a sufficiently complete and accurate state from real recordings;
  CONDITIONAL GO lists every condition; NO-GO requires that the approach cannot provide the
  information or cannot be operated reliably, and an incomplete prototype alone is never grounds
  for it.

### Key Entities

- **Approach**: one candidate route to actual game state (A, B, C and the baseline D), with its
  dependencies, environment needs and legal footing.
- **Capability**: one gameplay fact the platform wants (unit death, building completion, …) as
  assessed under one approach: availability class (FR-004), exactness, extraction method, evidence,
  limitations.
- **Observation**: one timestamped value extracted during an experiment, with its provenance
  category (FR-012), the recording it came from, its time base (FR-014) and its source (snapshot,
  event, command, inference).
- **Validation scenario**: one of the ten cases of FR-010 with its expected observation, extracted
  data, exactness verdict and ambiguities.
- **Corpus entry**: one real recording used in experiments, with identity or checksum, build, map,
  civilisations, player count, duration and the scenarios it covers.
- **Recommendation**: the final architectural choice and decision, with its conditions and the
  evidence that supports it.
- **Reviewer assessment**: the independent reviewer's record of verified, downgraded and unknown
  claims.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: At least one real recording has been processed end to end through the proposed
  approach, or the environmental blocker is documented to the point where a reader can name the
  single missing prerequisite and the setup that supplies it.
- **SC-002**: The extraction mechanism is demonstrated by a recorded run, not merely described;
  where it could not run, no row of the matrix claims a demonstrated capability for that route.
- **SC-003**: At least five of the ten validation scenarios of FR-010 have been validated
  experimentally, each with expected observation, extracted data, source, timestamp and an exactness
  verdict.
- **SC-004**: Every row of the capability matrix carries one availability class and one provenance
  category, and no row labels an inferred or derived value as an engine observation.
- **SC-005**: Replay determinism has been tested on at least one recording run at least twice, and
  the result (identical or not, with every difference explained) is in the report.
- **SC-006**: Build compatibility is recorded for build 185872 and for the build actually
  available, for every investigated interface.
- **SC-007**: Operational cost and every licensing and terms-of-service risk are recorded, legal
  and technical risks separately.
- **SC-008**: An independent reviewer's assessment is recorded with the report, and every claim it
  downgraded is relabelled in the final text.
- **SC-009**: The report ends with exactly one recommendation (A to E) and exactly one decision
  (GO, CONDITIONAL GO, NO-GO), with every condition listed, and a reader can trace each to its
  evidence.
- **SC-010**: Feature 008's planning can resume on the strength of the report alone: either its
  premise is confirmed, or the report states which of its requirements the decision affects, without
  this spike amending them itself.

## Assumptions

- The developer's machine is macOS on Apple silicon, without the game, without a Windows
  installation and without a Windows virtual machine; the game targets Windows. Until the owner
  states otherwise, no Windows host is assumed available, so the approach that needs the running
  game is expected to be environmentally blocked in this spike and documented under FR-008.
- The real recordings available are the three committed reference recordings
  (`tests/fixtures/replays/README.md`: a 1v1 and a 2v2 on build 180059, a 1v1 on build 185872).
  They are the corpus of FR-009; they are copied, never modified, and no extracted recording is
  committed beside them. A fourth or fifth recording is added only if the owner supplies one and it
  adds a scenario the three do not cover.
- The reference build stays 185872 unless the investigation finds that the installed or current
  build differs, in which case both are recorded.
- The research deliverables live under `docs/research/`, a new home, because their subject is the
  outside world (the game, its interfaces, third-party engines) and they must stay true after the
  feature is frozen; each carries its assessment date in the manner of `docs/data-sources.md`.
- The prototype, if any, lives under a dedicated research directory outside `apps/` and
  `packages/`, is excluded from the deployed build, and is not subject to constitution III's
  provider rule because it is not part of the application; the report says so explicitly.
- The constitution's rejection of extracting the game's own data file (`docs/data-sources.md` §6)
  stands during this spike: the investigation documents what a route would require without
  performing any extraction, and leaves any change of that ruling to a later amendment.
- Running the game client to feed a web service engages the publisher's and Steam's terms; the
  spike records what those terms say and the risk they create, and leaves the acceptance of that
  risk to the owner.
- This spike is isolated from feature 008: 008's branch and pull request stay as they are, and the
  decision this spike produces is what settles whether and how 008 is amended.
