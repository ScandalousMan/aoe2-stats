# Feature Specification: Match reconstruction — what each player ordered, spent and reached, proven from the recording

**Feature Branch**: `008-match-reconstruction`

**Created**: 2026-10-18

**Status**: Draft

**Input**: User description: "Feature 008 — deterministic reconstruction of a match from its
canonical event stream and the versioned knowledge base. The engine computes every reconstructed
result correctly for every civilisation. Where the recording proves the state at an order, the value
is exact; where it cannot, the published value is an interval whose two bounds the recording proves,
never a point estimate and never a gap."

## Context

Feature 006 built the foundations and stopped at the reconstruction boundary on purpose: the truth
tiers and their register, one canonical event vocabulary whichever parser runs, and a versioned
knowledge base that prices and times every unit, building and technology for a stated build and
civilisation. Its own specification names the reconstruction as the next feature and calls it 007.
That number now belongs to the deployment-storage feature, so the reconstruction is 008; 006's
task T777 renames the references.

Four data are written in the register as `planned` and wait for this feature: what each participant
spent, how much production time they ordered at each building, when each of their age-ups arrived
by the model, and what they spent on military units. Each one is priced or timed by the knowledge
base for the participant's civilisation and team, on the recording's build.

The owner's goal (2026-10-18) is that the engine computes these results **correctly, for every
civilisation**. 006's Phase 8 brings every civilisation to zero blocking gaps in the knowledge base.
This feature turns that knowledge into published values, and the hard part is not the arithmetic.

### A recording proves less than it seems to

A recording is a command log (006, Assumptions). It says that a player queued a unit, placed a
building or clicked an age-up. It never says that the building was finished, that the research
completed, that a building survived, or that production was not paused because the player ran out
of houses. Several published values depend on exactly those facts:

- **An age reached** decides every age-scaled bonus: a Goths infantry discount, a Persians Town
  Center speed, a Hindustanis Villager price. The age-up click is observed; its completion is not.
  A research order also has no observed cancellation (006, canonical events: only unit orders carry
  one), so a clicked age-up may never have completed.
- **A technology researched** decides every bonus conditioned on it: Kamandaran, Szlachta
  Privileges, Perfusion.
- **Buildings standing** decide Saxons' Foot Soldiers discount per Town Center or Castle
  controlled. Placements are observed; completions and destructions never are.
- **When production actually ran** decides an age-up's arrival: an age-up waits in its Town Center's
  queue behind every Villager ordered before it, and a queue stops while the player is housed.

The recording still proves a great deal. A later order the game refuses before an age proves that
age was reached by then. An order issued from a building proves that building stood at that moment.
A unit ordered at a building cannot have started before that building's earlier orders finished.

### The owner's rule (006 spec, Clarifications, Session 2026-10-18)

The knowledge base never decides which condition held; this feature does. **Where the recording
proves the state, the value is exact. Where it does not, the published value is an interval whose
two bounds the recording proves.** Never a point estimate where a proof is available, never a
silent assumption, and never a gap that a bounded answer could replace. An interval whose two bounds
coincide is an exact value and is published as one.

## Clarifications

_None yet. `/speckit-clarify` records its session here._

## User Scenarios & Testing _(mandatory)_

### User Story 1 - See what a player spent, priced for their own civilisation (Priority: P1)

A player opens the analysis of one of their matches and sees, for each participant, the resources
they spent by resource, and the part of it spent on military units, priced with every bonus their
civilisation and their team actually had at the moment of each order.

**Why this priority**: it is the first reconstructed number, it is what every later analysis builds
on, and it is the one the owner's goal names first: correct for every civilisation.

**Independent Test**: analyse a committed reference recording and compare each participant's
spending with the golden fixture, built by hand from the recording's orders and the knowledge base,
and checked against what the game itself reports when the recording is played to its end (FR-019).

**Acceptance Scenarios**:

1. **Given** a recording where a Malians player builds a Dock, **When** it is analysed, **Then** the
   Dock is priced with the Malians wood discount, and the spending names the effect applied.
2. **Given** a Goths player who orders infantry before and after clicking Feudal Age, **When** it is
   analysed, **Then** each order before the click is priced at the Dark Age discount, and each order
   after it is priced at the Feudal discount only if the recording proves Feudal was reached by then;
   otherwise that order's price is the interval between the two discounts.
3. **Given** a participant whose ally's team bonus lowers a cost, **When** it is analysed, **Then**
   the bonus is applied, because the team is read from the recording itself.
4. **Given** a participant who cancels queued units, **When** it is analysed, **Then** the
   cancelled units are subtracted from the spending.

---

### User Story 2 - See when each age-up arrived, and how sure that is (Priority: P1)

A player sees, for each participant, when each age-up was clicked (observed, already published by
006) and when it arrived by the model, as an exact time where the recording proves it and as an
earliest-to-latest window where it does not.

**Why this priority**: age-up timing is the single most-used figure in match review, and it is the
clearest case of the owner's rule: the click is observed, the arrival is reconstructed, and the two
must never be confused.

**Independent Test**: for each age-up in each committed recording, the window contains the arrival
time the game reports when the recording is played back (FR-019), and the window's earliest bound
is the click plus the queue ahead of it plus the research time for that civilisation.

**Acceptance Scenarios**:

1. **Given** an age-up clicked with nothing ahead of it in its Town Center, **When** it is analysed,
   **Then** the earliest arrival is the click plus that civilisation's research time, with every
   speed bonus that applies.
2. **Given** an age-up clicked behind three queued Villagers, **When** it is analysed, **Then** the
   earliest arrival is after those three Villagers' production times.
3. **Given** a later order the game refuses before the new age, **When** it is analysed, **Then**
   the latest arrival is no later than that order.
4. **Given** no later order proves the age was reached, **When** it is analysed, **Then** the
   publication says the age-up may not have completed, and still gives its earliest arrival.

---

### User Story 3 - Every reconstructed value says how it was proven (Priority: P2)

A reader of the analysis, or of the published document, can tell for any reconstructed value
whether it is exact or an interval, what proved each bound, and which knowledge snapshot and
effects priced it.

**Why this priority**: an interval nobody can audit is an estimate wearing a disguise. 006's
provenance spine already requires every value to carry where it came from; this extends it to the
proof of a bound.

**Independent Test**: for any reconstructed value in a published document, follow its provenance to
the orders that proved each bound and to the snapshot identity, and recompute the value by hand.

**Acceptance Scenarios**:

1. **Given** an interval-valued cost, **When** a reader inspects it, **Then** each bound names the
   condition assumed for it and the order or absence that leaves both possible.
2. **Given** an exact value that depended on a condition, **When** a reader inspects it, **Then** it
   names the order that proved the condition.

---

### User Story 4 - The view shows an interval as an interval (Priority: P2)

The match analysis view shows each reconstructed value next to the observed ones, writes an
interval as a range and an exact value as a number, and never rounds an interval into a single
figure.

**Why this priority**: the published document is correct without it, but the owner's goal is a
player seeing correct results. A range collapsed to its midpoint on screen would undo the rule at
the last step.

**Independent Test**: render the analysis of each committed recording and check that every interval
in the document appears as a range and every exact value as one number, in light and dark themes.

**Acceptance Scenarios**:

1. **Given** an age-up arrival window, **When** the view renders it, **Then** both bounds are shown
   and labelled as modelled, apart from the observed click.
2. **Given** a value withheld by a blocking knowledge gap, **When** the view renders it, **Then** it
   says what is missing, as 006 already does for gaps.

---

### User Story 5 - The same recording always reconstructs to the same result (Priority: P3)

An analysis recomputed with the same parser, knowledge snapshot and reconstruction version yields
the same bytes, and a new reconstruction version publishes a new analysis rather than overwriting
the old one.

**Why this priority**: 006 already guarantees it for everything it publishes (FR-040 to FR-043);
this feature must not be the first thing that breaks it.

**Independent Test**: analyse each committed recording twice and compare bytes; bump the
reconstruction version and confirm both analyses are kept and resolvable.

**Acceptance Scenarios**:

1. **Given** identical inputs, **When** analysed twice, **Then** the documents are byte-identical.
2. **Given** a new reconstruction version, **When** an old analysis is reproduced from its
   identity, **Then** it reproduces exactly.

### Edge Cases

- **A participant resigns.** Nothing is attributed after resignation (006, canonical events, exit
  discipline); spending stops there, and an age-up clicked before it may still arrive by the model.
- **Several Town Centers.** An age-up is queued in one named building; the queue ahead of it is that
  building's only, since each order names its producing building.
- **A cancellation that names no building.** A unit cancellation carries the unit and count but not
  the building (006, canonical events). Where more than one building could hold the cancelled units,
  the queue ahead of a later order is an interval over the possible buildings.
- **A research ordered twice.** Repeats collapse to the first occurrence (006, FR-018); a research
  re-ordered after a cancellation the recording cannot see is therefore indistinguishable from the
  first, and its arrival window says so.
- **A condition proven only after the order it prices.** A proof of an age at minute 12 proves
  nothing about an order at minute 10; each bound is proven at the time of the order it prices.
- **A recording whose build has no snapshot, or a civilisation with a blocking gap.** Every value
  that depends on the missing knowledge is withheld, every independent value is still produced
  (006, FR-037, FR-038).
- **A bonus whose state is never bounded by anything.** If no order can bound a condition from
  either side, both conditions are possible for the whole match, and the interval spans both
  answers; it is never narrowed by assumption.
- **A free or zero-cost order.** Priced at what the knowledge base answers, zero included; never
  skipped.

## Requirements _(mandatory)_

### What is reconstructed

- **FR-001**: The system MUST publish, for each participant of an analysed match, the four data the
  register holds as `planned` for this feature: resources spent by resource, ordered production
  time per producing building, the modelled arrival of each age-up, and resources spent on military
  units. Each MUST move from `planned` to `published` in the register in the same change that
  publishes it.
- **FR-002**: Every reconstructed value MUST be computed from the canonical event stream and the
  versioned knowledge base alone, for the recording's build, the participant's civilisation and the
  participant's team as the recording states them. No other input is admitted.
- **FR-003**: An order MUST be counted as a command, not a completion, as the register's methods
  already state: spending is what was ordered, less what the recording shows was cancelled.
- **FR-004**: Every cost and every time MUST be the knowledge base's answer with every effect whose
  condition held, and MUST name the effects applied (006, US2).

### Proving the state an effect depends on

- **FR-005**: For every order whose price or time depends on match state (an age, a technology, a
  team, a count of buildings controlled), the system MUST determine from the recording the set of
  states that are possible at the moment of that order, and MUST NOT assume one.
- **FR-006**: The system MUST treat as proof only what the recording establishes: an order the game
  refuses before an age or a technology proves that age or technology by the time of that order; an
  order issued from a building proves that building stood at that time; a placement proves at most
  that a building was ordered, never that it was finished or still stands; a click proves only that
  it was ordered. The set of proof rules is closed, written down, and each rule carries the evidence
  that the game behaves that way.
- **FR-007**: Where exactly one state is possible, the value MUST be exact. Where more than one is
  possible, the value MUST be an interval from the smallest to the largest answer over the possible
  states, and each bound MUST name the state it assumes and what proved that state possible.
- **FR-008**: The system MUST NOT publish a point estimate, a midpoint, a most-likely state or a
  probability for an interval-valued datum. An interval whose bounds coincide MUST be published as
  an exact value.
- **FR-009**: A value MUST NOT be withheld because its state is uncertain. It is withheld only when
  knowledge it depends on is missing (006, FR-037).

### Timing

- **FR-010**: The modelled arrival of an age-up MUST be bounded below by its click, plus the
  production of every order ahead of it in the same building, plus its research time for that
  civilisation and state; and bounded above by the earliest order that proves the new age, when one
  exists. When none exists, the publication MUST say the age-up may not have completed.
- **FR-011**: The production ahead of an order MUST be computed per producing building, from the
  orders the recording attributes to that building, less the cancellations that can be attributed to
  it; a cancellation that could belong to more than one building MUST widen the interval rather than
  be assigned to one.
- **FR-012**: The system MUST NOT model idle time it cannot observe — housing, an unpaid queue, a
  destroyed building — as zero. Such idle time can only delay an arrival, so it widens the upper bound
  and never moves the lower one.
- **FR-013**: Ordered production time per building MUST be the sum of the knowledge base's
  production time for each order attributed to that building, priced with the effects that held,
  and is a quantity of ordered work, not a timeline of when the building was busy.

### Truth tiers and provenance

- **FR-014**: Every reconstructed datum MUST be published at the `reconstructed` tier (the military
  share at `derived`, as the register already classifies it) and MUST carry 006's provenance: the
  snapshot identity, the effects applied, and, for every bound, the proof that supports it (US3).
- **FR-015**: A reconstructed value MUST NOT be placed in a field typed `observed` or `decoded`; 006's
  validator MUST reject the document if it is (006, SC-003).
- **FR-016**: The publication MUST keep the observed click and the modelled arrival of an age-up as
  two data, never one (003, FR-043b, as 006 quotes it: publish only what is read from the
  recording, and keep what is modelled apart).

### Correctness

- **FR-017**: The reconstruction MUST hold a closed set of invariants over every analysed match and
  refuse to publish a document that breaks one, recording which invariant broke. At least: no
  spending is negative; cancellations never exceed the orders they cancel; a lower bound never
  exceeds its upper bound; no age-up arrives before its click; no order is attributed after its
  participant resigned; the military share never exceeds the total.
- **FR-018**: Each committed reference recording MUST have a golden reconstruction, written by hand
  from its orders and the knowledge base, which the analysis reproduces exactly.
- **FR-019**: Each golden reconstruction MUST be validated against the game: a person plays the
  recording back in the game to its end and reads, for each participant, every figure the game
  reports that corresponds to a reconstructed datum (at least each age-up time), recorded with who,
  when and the build. Every reported value MUST fall inside the reconstructed interval or equal the exact value; a value
  outside it is a defect in a proof rule or in the knowledge base, never a tolerance.
- **FR-020**: For every civilisation of every build a promoted snapshot describes, the system MUST be
  tested to price and time a synthetic order stream that exercises every effect that civilisation
  has, including every conditional one at each of its states.

### Versioning and boundaries

- **FR-021**: The reconstruction MUST carry its own version in the analysis identity (006, FR-040),
  and a change to a proof rule, an invariant or the arithmetic MUST bump it.
- **FR-022**: Identical inputs MUST produce byte-identical documents, and an analysis published
  before a reconstruction or knowledge change MUST reproduce from its identity (006, FR-041, FR-043).
- **FR-023**: The reconstruction MUST run inside the existing on-demand analysis path and MUST NOT
  add a scheduled job, a network call, or work on the capture path (constitution I and III; 006,
  FR-049).
- **FR-024**: The data that depend on the starting state MUST stay `blocked` in the register: the
  income model, exploration coverage and the map-control model. The prerequisite order check MUST
  stay `blocked` on a lawful prerequisites source (006, research D3).

### Presentation

- **FR-025**: The match analysis view MUST show each reconstructed datum, writing an exact value as
  one number and an interval as both its bounds, labelled as modelled, using design-system tokens
  only and covered by visual tests in both themes (constitution VI, VII).

### Key Entities

- **Order**: a command the recording attributes to a participant at a match-clock time: a unit
  queued (with its producing building and count), a unit cancelled, a research or age-up queued
  (with its building), a building placed. Read from 006's canonical stream, never re-parsed.
- **State proof**: one fact the recording establishes at a time (an age reached by then, a
  technology researched by then, a building standing then), with the order that proves it and the
  proof rule that licenses it.
- **Possible-state set**: for one order, every combination of conditions the proofs leave open at
  its time; one member means exact, several mean an interval.
- **Reconstructed value**: an exact value or an interval of two bounds, each bound carrying the
  state assumed, the proofs used, the snapshot identity and the effects applied.
- **Invariant breach**: which invariant, for which participant and value, recorded when publication
  is refused.
- **Golden reconstruction**: per committed recording, the hand-built expected values and the
  person's reading of the game's own playback that validates them.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: For each committed reference recording, every value the game reports on playback
  (FR-019) lies inside its reconstructed interval or equals its exact value: zero values outside.
- **SC-002**: The count of published reconstructed values carrying a point estimate, a midpoint or a
  probability in place of an interval is zero.
- **SC-003**: The count of reconstructed values withheld for uncertainty alone, rather than for a
  missing piece of knowledge, is zero.
- **SC-004**: For every civilisation of every snapshotted build, the synthetic order streams of
  FR-020 price and time every effect at each of its states: zero civilisations untested.
- **SC-005**: Every published interval and exact value traces, without reading code, to the orders
  that proved it and the snapshot that priced it (US3).
- **SC-006**: The same recording analysed twice with identical versions yields byte-identical
  documents, and every analysis published before a version change still reproduces.
- **SC-007**: A document that breaks an invariant is never published: the count of published
  documents failing an invariant check is zero.
- **SC-008**: Analysing a recording takes no more than twice the time it takes today, measured on
  the committed recordings, so that the on-demand path stays within the hosting budget.
- **SC-009**: The width of every age-up arrival window on the committed recordings is measured and
  recorded with the golden reconstructions, so that a proof rule's value is visible as a number. No
  width is a target: a wide window is reported, never narrowed.

## Assumptions

- **006's Phase 8 lands first, or in parallel.** Until a civilisation is modelled, its values are
  withheld by the knowledge base's blocking gaps, which this feature honours and does not work
  around. This feature does not wait for Phase 8 to start; it waits for it to call itself done.
- **Resources are committed at the moment an order is accepted.** A recorded queue command is
  assumed to correspond to an accepted, paid order; whether the game records a command it then
  rejects for want of resources is not yet measured. See **Important unresolved decisions**.
- **The game's own playback is an authoritative oracle and lawful to read.** Watching a recording in
  the game reads what the game shows; it extracts nothing from the game's files (006, research D3,
  amended 2026-10-18).
- **The committed reference recordings are enough to start.** More may be committed under 006's
  register basis for committed recordings if a proof rule needs a case the three do not exercise.
- **Only the current scope of civilisations.** "Every civilisation" means what 006's Phase 8 means;
  the Chronicles civilisations follow 006's T776 arbitration.

## Out of Scope

- The starting-attributes and starting-object-table decoders (006, research D1 tiers A and B), and
  every datum blocked on them: income model, exploration coverage, map control.
- The prerequisite order check, blocked on a lawful source of the game's prerequisites.
- Any analytics, strategic inference or coaching built on these values.
- Combat simulation, losses, army value: losses stay non-determinable (006).
- Changes to capture, retention or the parse-once pipeline (003, constitution I).
- Re-specifying the knowledge base: 006 owns it, including Phase 8's coverage of every civilisation.

## Dependencies

- **006** — the canonical stream, the knowledge base and its query surface with `context`, the
  register and its validator, the analysis identity. Phase 8 (PR #179) supplies every civilisation
  and the `controlled` condition this feature resolves.
- **003** — the on-demand analysis path and its versioned document seam.

## Important unresolved decisions

- **Does a recorded queue command prove the order was paid?** If the game records a command it then
  refuses for want of resources, spending as "orders less cancellations" overstates, and FR-003's
  wording would need a proof rule of its own. It is measurable: the owner queues a unit without
  enough resources in a recorded game and reads the recording. Until measured, it is stated as an
  assumption, and the plan must not depend on either answer without the measurement.
- **Which orders the game refuses before an age.** FR-006's first proof rule needs, per build, which
  entities have an age requirement. That is 006's `age_requirement` field, informational until now
  because no published datum required it; this feature makes it required, so its gaps become
  blocking where they touch a proof (006, research D7).

- **Which spending figures the game's playback reports.** Its end-of-match statistics are known to
  report age-up times; whether any figure there equals resources spent, rather than resources
  gathered, is not established. Until it is, spending is validated by the hand-built goldens and the
  synthetic streams, and FR-019 validates the age-up windows.

## Risks

- **A proof rule that is not true of the game.** The rules are few and each carries evidence, and
  FR-019's playback readings exist to catch a wrong one; a single value outside its interval fails
  the suite.
- **Intervals too wide to be useful.** SC-009 measures it on the committed recordings; the answer to
  a wide interval is a new proof rule with evidence, never a narrower one by assumption.
- **The owner's playback readings are a dependency on a person.** They are few (one pass per
  committed recording) and are requested with the exact values to read.
