# Phase 0 — Research: Match reconstruction

**Date**: 2026-11-06 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Three audits of this repository ran in parallel (the canonical stream and its adapter, the knowledge
base, the analyzer and the web reader), and every measurement below was then re-run by hand against
the three committed reference recordings and their canonical goldens. The scripts were throwaway;
each measurement states what it counted so that a task can turn it into a test.

This document owns the measurements it states until a named task moves the ones that describe the
outside world into `docs/data-sources.md` (R13). It restates nothing that file already holds.

## What the spec assumed, and what the recordings say

| Spec assumption | Verdict | Where |
| --------------- | ------- | ----- |
| Each order names its producing building (Edge Cases, FR-011) | **False of the canonical stream.** Most queue commands name several buildings and the stream keeps the first. | R1 |
| A recorded queue command can be counted as paid until measured (FR-003b) | **Contradicted by the recordings themselves**, before any playback reading. | R2 |
| A later order refused before an age proves the age (FR-006) | **Holds on 3,235 of 3,241 orders**; the six exceptions are one knowledge defect. | R3 |
| A later order can confirm a technology the way it confirms an age | **False.** Orders name the line's base unit after every upgrade. | R15 |
| The winning side is available to FR-010a | **Not in the stream**, and FR-002 forbids the one place it exists. A deduction rule settles it. | R8 |
| Spending on military units needs only `cost` (register) | **The knowledge base has no unit class.** | R10 |
| Population can be priced by the knowledge base (FR-001a) | **The knowledge base has no population field.** | R5 |
| The refuted death heuristic is recorded in `docs/data-sources.md` §2 (FR-012) | **Wrong citation.** It is recorded in 006's spec, User Story and Clarifications on the group-silence observable. | R5 |
| A unit cancellation can be attributed to a building (FR-011) | **No committed recording carries one**, so the rule is written and tested synthetically only. | R7 |

## R1 — Queue commands name several buildings, and the canonical stream keeps one

**Measured.** The pinned engine's queue action carries a list of producing buildings. Counted over
every queue action of each committed recording:

| Recording | Queue actions | Naming one building | Naming two to seven |
| --------- | ------------- | ------------------- | ------------------- |
| 500546441 | 899 | 173 | 726 |
| 504695319 | 810 | 545 | 265 |
| 511523321 | 410 | 187 | 223 |

The adapter emits one `unit-queued` per action carrying the first building only, a narrowing 006's
contract names as known (canonical-events contract, "Two additions") and which cost nothing then,
because no published datum read a building object. Every datum of this feature that is per building
does: ordered production time per building (FR-013), the queue ahead of an age-up (FR-010) and the
attribution of a cancellation (FR-011).

**Decision.** Widen the vocabulary, additively: `unit-queued` gains `building_objects`, every
producing building the command names, in the engine's order. `building_object` stays, equal to the
first, so 006's golden timeline and every existing consumer are untouched. The canonical goldens are
regenerated under the fixtures README's rules, and the register gains the field. This is 006's
vocabulary changed by 008, through the seam that vocabulary exists to provide; principle V is the
reason it is a type change in `packages/core` and not a re-parse in this feature.

**What stays unknown, and settles it.** How the game spreads a command's `amount` over the buildings
it names: one unit in each, the amount in each, or the amount spread over the buildings by some
rule. Spending changes by a factor of the building count between the first two readings, so this is
the first playback reading requested (owner reading O2). A simulation that distributes each unit to
the building that frees first changed none of the single-building contradictions in R2, so the
distribution is not what R2 is about.

**Alternatives rejected.** Reconstructing from the engine's output directly, below the canonical
seam: it re-couples this feature to one engine, which is what 006 FR-015 forbids.

## R2 — The recording holds commands the game refused

This is the finding that orders the plan. FR-003b lets a recorded queue command count as paid until
a measurement says otherwise. The repository already holds that measurement, in two forms.

**Direct evidence: a technology commanded twice.** A technology is researched once. In the three
recordings, 32 technologies are commanded exactly twice by the same participant. 25 pairs are less
than a second apart, nearly all two tenths of a second, and five pairs are age-ups (500546441 player
2's Feudal and Castle Age and player 1's Imperial Age; 504695319 player 2's Feudal and Imperial
Age). The game cannot have accepted both commands of a pair, so the recording keeps a command the
simulation refused. 006's first-occurrence collapse (006 FR-018) already discards the second of each
pair, which is right for a double click and not established for the 7 pairs more than a second apart
(500546441 player 1's technology 213, at 864 s and 1,590 s, is the widest): there, which of the two
the game accepted is not known, and if it was the second, the published click time is wrong.

**Indirect evidence: the queue model contradicts the recording's own proofs.** For each of the 22
age-ups in the committed recordings, the FR-010 model was computed with every recorded order ahead
of the age-up in its Town Center executed, production times from the knowledge base for the
participant's civilisation and team, and no housing pause (which could only make the arrival later).
Then the first later order the game refuses before the new age (R3) was found. In **10 of the 22**,
that proof comes before the modelled arrival, by 16 s to 593 s. The proof is the stronger fact: the
age was reached by then. So the model put work in the queue that was never there.

| Recording | Participant | Age | Modelled arrival is after the proof by |
| --------- | ----------- | --- | -------------------------------------- |
| 500546441 | 1 | Castle | 113 s |
| 500546441 | 1 | Imperial | 593 s |
| 500546441 | 2 | Castle | 164 s |
| 504695319 | 1 | Feudal | 157 s |
| 504695319 | 1 | Castle | 90 s |
| 504695319 | 4 | Feudal | 82 s |
| 504695319 | 4 | Castle | 63 s |
| 511523321 | 1 | Feudal | 16 s |
| 511523321 | 2 | Feudal | 23 s |
| 511523321 | 2 | Castle | 201 s |

One case shows the size. 504695319 player 1 commanded 26 Villagers at one Town Center before
clicking Feudal Age at 496 s; that building can produce at most about 20 in that time. Its Feudal Age
is proven by 641 s, which leaves room for less than one Villager ahead of it.

**Candidate causes**, none established: queue commands refused for want of resources or of queue
space, recorded as the research pairs show refused commands are; cancellations recorded in a form
the adapter does not decode (no committed recording carries a single cancellation action, and the
queue action has an unnamed field taking the values 1 to 4); production times the knowledge base
gets wrong. Housing is not a candidate: it lengthens the queue.

**Decision.**

1. FR-003b's hypothesis is **refuted and retired**, and the spec's FR-003b, Assumptions and
   unresolved decisions were amended in this plan's change to record the measurement. Published, it
   would give age-up arrivals that the recording refutes in 10 of 22 cases, which FR-019 makes a
   defect and SC-001 a failure; under the spec's own discipline (FR-012: a strategy already measured
   and refuted is not adopted), nothing else was possible.
2. Telling an executed command from a refused one becomes the first gate of this feature (G1 in the
   plan). Its inputs are owner readings O1 and O2: the Town Center queue at each age-up click, and
   what a command naming several buildings put in each.
3. Spending (US1) and arrivals (US2) are built behind that gate and published only through it.

**What this costs if the gate cannot be closed exactly.** A refusal for want of resources depends on
the stockpile, and the stockpile depends on income, which the register holds `blocked`. If the
readings show refusals that no observed fact distinguishes, then no exact rule exists for spending
or arrivals and the owner's rule cannot be met for them: that is an arbitration (the plan's
Complexity Tracking names it), not a reason to publish the hypothesis.

## R3 — The age proof rule holds, and found one knowledge defect

**Measured.** For each order in the three recordings, the knowledge base's `age_requirement` for
the participant's civilisation and team was compared with the participant's own age-up clicks. An
order that requires an age the participant has not yet clicked is impossible under FR-006's first
proof rule. Of 3,241 orders with an answer, 6 are: 511523321 player 2 (Sicilians) ordered unit
1658 six times, from 625 s, before clicking Castle Age at 1,130 s, and the knowledge base answers
Castle Age for it.

**Decision.** Two things, both kept:

- The rule is adopted as **P1** (contracts/rules.md), its evidence being this measurement and the
  game's own interface, which offers no command for an entity whose age has not been reached; owner
  reading O3 confirms the Sicilians case in the game.
- The disagreement is a knowledge defect, filed through 006's owner-readings mechanism and fixed by
  a superseding snapshot (006, T746), not worked around here. And the measurement becomes a
  permanent test over every committed recording, because it is a free cross-check of
  `age_requirement` that no other test performs. FR-020 makes `age_requirement` required, so this
  feature also adds it to the `requires_knowledge` of the age-up datum, which turns its gaps
  blocking (006 research D7).

## R4 — The starting state

**Measured** (006 research D1, and `docs/data-sources.md` §2, "Settled: each human player's
starting-attribute array…"): each human player's starting attributes sit at a self-verifying anchor,
and the first four values are read as the four stockpiles. The lobby carries the starting-resources
and starting-age presets, both read into `match-started`; the population limit is in the engine's
output and is not read. Every committed recording has the same presets.

**Decision.**

- **Starting resources** are decoded by the Tier A decoder 006 research D1 sized and left to this
  feature, emitted as the declared `starting-attributes` event, and published at `decoded`. FR-026's
  derivation from the lobby and civilisation is kept as a cross-check, never as a fallback: a
  disagreement is a defect.
- **Starting age** comes from the lobby preset. What each value of it means is read from a
  referenced source and confirmed by the owner (O4); until then a recording whose value is not the
  one confirmed gaps every age-dependent value.
- **Starting units and buildings** are not in the attribute array and the knowledge base has no such
  table. They are a new hand-transcribed knowledge table per build, civilisation and preset, read
  from a referenced source and verified by the owner (FR-026), added through 006's snapshot
  mechanism.
- **Population limit** is read from the lobby into `match-started`, beside the other presets.
- Attribute indices beyond the first four are not interpreted. A candidate meaning (current
  population, population headroom) is adopted only from a referenced source and an owner reading at
  0:00 of a committed recording.

The starting objects of the map (006 research D1, Tier B) stay out of scope (spec, Out of Scope).

## R5 — Population and Town Center idle time: what the recording can settle

FR-012 requires this analysis before any method is chosen. Its conclusion is that **no method is
chosen in this plan.** Two prerequisites are missing and every candidate needs a playback reading.

**Missing knowledge.** The knowledge base carries no population cost and no population space. Five
civilisation effects that touch population are recorded `modelled = no` for exactly that reason (the
Incas, Dravidians, Bengalis, Lithuanians and Saxons effects in the build 188329 snapshot). Both fields
must be added, from a lawful source, through 006's snapshot mechanism, before population can be
computed at all.

**Measured facts about what the stream carries.**

- Commands with unit ids: only move, interact and order (006 canonical-events contract). Even those
  carry an empty id list in a large share of cases: in 500546441, 3,032 of 5,272 moves and 510 of
  1,135 interacts. Why is not established; a reused selection is a candidate.
- Deletions: 82 across the three recordings. 60 delete an object no earlier event names; 20 delete an
  object the same participant had targeted with an interact; 2 delete an object earlier seen as a
  commanded unit or a producing building.
- Placements carry a building type and a position, no object id and no builders.

**Strategies, each a candidate until a playback reading checks it.**

| # | Strategy | Observed facts it uses | Settles | Status |
| - | -------- | ---------------------- | ------- | ------ |
| S1 | A unit commanded at a time is alive then | move, interact, order with ids | a lower bound on the living, never a death | adoptable as a proof (P3); bounds only |
| S2 | A deleted own unit dies at the deletion | `object-deleted` tied to a unit | deaths by deletion | candidate; needs the tie (R6) |
| S3 | A unit no longer commanded is dead | silence | deaths | **refuted** (006 spec, group-silence clarification); never adopted |
| S4 | Production completes at its modelled time unless housed | queue model, population, capacity | births | candidate; depends on R2's gate and on S5 |
| S5 | A house counts from its modelled completion | placement, interact targets on its foundation, construction time | capacity | candidate; the foundation's object id is known only when a builder targets it |
| S6 | An object id first commanded after a queue order is that order's unit | id first appearance, queue model | births at a proven time | candidate; ids are allocated to every object, not only units |
| S7 | A housing pause is the time a queue holds an item and the modelled population equals the capacity | S4 and S5 | idle by housing | candidate; inherits every error of S4 and S5 |
| S8 | Idle by empty queue is the time a building's modelled queue is empty | queue model | idle by empty queue | candidate; depends on R2's gate only |

**What follows.** S8 is the only candidate that needs neither deaths nor capacity, so Town Center
idle time by empty queue is reachable as soon as R2's gate closes. Population needs deaths, and the
recording carries no death except a deletion, so an exact population figure needs a rule that the
owner's readings at stated times confirm — and if no candidate survives those readings, that is an
arbitration (Complexity Tracking), because the spec requires an exact figure. FR-010 also reads idle
time ahead of an age-up, so the age-up arrivals carry a housing rule from the start: **D-HOUSE-0**,
no housing pause ahead of an age-up, a candidate that the 22 age-up readings check.

**Sequencing.** Population and idle time are filed as their own phase, after G1, with the two
knowledge fields and the readings O6 first. Their register entries are added as `planned` in the
change that files their tasks (FR-001a), not now.

**The spec's citation was wrong, and is corrected in this change.** FR-012 cited
`docs/data-sources.md` §2 for the refuted death heuristic; that section records the absence of a
post-game statistics block. The refutation is in 006's spec, in the group-silence user story and its
clarification, and in the group-silence register entry's non-claim, which FR-012 now cites.

## R6 — Tying a deletion to the building it removes

**Measured** (R5): 60 of 82 deletions name an object no earlier event names. A foundation deleted
before anyone works on it is exactly such an object, and it is the one deletion FR-003a refunds.

**Decision.** One proof rule and one deduction rule, both closed:

- **P2**: an object that a building-scoped order names (a queue or a research issued from it) is a
  building of the type that order states, standing at that time.
- **D-TIE-1** (candidate): a deleted object is the participant's most recent untied placement when
  the participant's own interact targeted it within a stated window after that placement and no
  other placement intervened. The window is fitted on the owner's reading of three deletions (O5)
  and not before.
- Every other deletion is reported, as FR-003a requires, with the candidate placements and the
  refund each would have given; the refund hypothesis (**D-REFUND-1**: a foundation deleted before
  construction began is refunded in full, anything else nothing) changes a published value only
  through a tied deletion.

## R7 — Cancellations

No committed recording carries a unit cancellation, and the adapter's cancellation payload layout is
unproven (006 canonical-events contract). The rule is written, because FR-011 forbids leaving one
unattributed: **D-CANCEL-1**, a cancellation of unit _u_ and count _n_ is attributed to the
participant's building with the most recently queued, not yet started, items of _u_, removing from
the end of its queue, and never more items than are unstarted there (FR-017). It is tested on
synthetic streams, and the rule's record says no recording has exercised it. It is not an
arbitration: what it lacks is a recording that carries one, so that the payload layout the adapter
guards (006 canonical-events contract) is proven and the rule can be checked. Owner reading O7 asks
for one. Until then the adapter emits no cancellation event, so the rule settles nothing, and the
reconstruction's limits say so. Research has no observed cancellation at all (spec, Edge Cases), and
R2 shows its consequence.

## R8 — The winning side

The stream carries resignations and the final clock, and no outcome (006 canonical-events contract;
`docs/data-sources.md` §2 on the post-game block). The match result exists on the API's match rows,
and FR-002 forbids that input.

**Decision.** **D-WIN-1**, adopted: the winning side is the one team none of whose members
resigned, when every member of every other team resigned before the match ended; otherwise no
winning side is established and FR-010a's winning-side clause does not apply. Its evidence is the
meaning of the command itself: a resignation is a defeat, and a match in which every member of every
other team is defeated is won by the team that remains. No ruling is needed for that. Its limit is
stated on the record: a match ended any other way (every building and unit destroyed, a disconnect)
establishes no winner, and the clause then does not apply. In the committed recordings it establishes
a winner in all three (the 2v2 ends with both members of one team resigning). The fixtures README
records no result, so the match rows' result is not used even to corroborate it (FR-002 would not
forbid that, but a corroboration read from production needs the owner).

**The attack clause of FR-010a** reads an interact command whose target is the researching
building's object, issued by a participant of another team. Interact is the only command class
whose target is an object; 46, 49 and 34 such commands target another participant's producing
building in the three recordings, so the clause is exercised. Commands that carry no target (attack
move, formation) are invisible to it, and the rule's record says so.

## R9 — Technologies and buildings controlled

Two kinds of condition have no observed completion and no rule in the spec beyond FR-007's
requirement that one exist.

- **A technology researched** (Kamandaran, Szlachta Privileges, Perfusion, and every unit upgrade,
  R15). The confirming order of FR-010 has no lawful analogue: it would need prerequisites, which
  the register holds `blocked` (FR-024), and R15 shows a unit upgrade leaves no trace in later
  orders either. Candidate **D-TECH-1**: an executed research counts researched from its modelled
  arrival, by the same queue model as an age-up, unless its participant resigned first. It needs
  the owner's ruling on its direction, because it has no confirming order at all: the age-up
  clarification chose "not reached unless confirmed", and applied to a technology that nothing can
  confirm, that reads "never researched", which would make Kamandaran never apply and every archer
  train at the Archer's time after Crossbowman. In the committed recordings the ruling decides the
  Persians' Kamandaran in 504695319 (researched at 36:01) and the training time of 665 units
  ordered after a line upgrade (R15).
- **Buildings controlled** (Saxons' discount per Town Center or Castle, the Cumans' second Town
  Center in the Feudal Age). **P2** proves a building standing at each order issued from it. Candidate
  **D-CONTROL-1**: a building counts controlled from the first order issued from it until the match
  ends, the starting Town Center from 0; destruction is unobservable, so a destroyed building keeps
  counting. It needs the owner's ruling, and its record names that blind spot.

## R10 — Military units

The register's method for the military share reads "units the knowledge base classes as military",
and the knowledge base has no class: selectors are explicit identifier lists, never class names.

**Decision.** The classification is a knowledge fact, so it goes into the knowledge base, as an
explicit list of economic units per build (every unit not on it is military), transcribed from a
referenced source. The list's membership is a definition, not a measurement: whether a Monk, a
Missionary or a transport ship counts as military is something the code cannot settle. The plan
proposes Villagers in all their forms, Fishing Ships, Trade Carts, Trade Cogs and Transport Ships as
the economic list, everything else military, and asks the owner to confirm it (an arbitration).

## R11 — Market transactions and other resource movements

Selling and buying at the Market moves resources and is reconstructable in principle (the price
moves deterministically with every player's transactions), but it is an exchange, not an order.
**Decision**: excluded from spending. The register's method says so, so a reader does not take the
figure for net resource flow. Tribute is not in the stream at all.

## R12 — The reconstruction is a package of its own, with its own version

**Decision.** A new workspace package, `packages/reconstruction`, depending on `aoe2stats-core` and
`aoe2stats-knowledge` only. It is pure: a canonical stream and a snapshot in, a reconstruction out.
Its version fills the identity's `reconstruction_engine` slot, which 006 reserved for it, and which
the reproduce path today refuses whenever it is not `not-applicable`.

- It is declared on `apps/analyzer`'s own manifest, because the deployed function installs only what
  the analyzer declares (006 plan, Technical Context, the 2026-09-04 fault).
- It cannot live in `apps/analyzer`: the rules registry and the invariants are library code that the
  golden and synthetic tests exercise without an application.
- It cannot live in `packages/knowledge`: the knowledge base never decides which condition held
  (spec, The owner's rule); this package does.

**Rules are data, like the register.** The closed sets of proof rules and deduction rules live in one
TOML file inside the package, loaded with the standard library, with a generated view and a drift
test exactly like the register's (006 research D6). A rule carries its evidence, the owner's ruling
where it rests on one, its playback readings, and a status; only an adopted rule may settle a
published value (contracts/rules.md).

## R15 — A queue order names the line's base unit, whatever has been upgraded

**Measured.** After a participant researches a unit upgrade, their later queue orders still carry
the base unit's identifier. 500546441 player 1 researched Crossbowman at 1,078 s and then ordered
unit 4, the Archer, 167 times, and unit 24, the Crossbowman, never; across the three recordings,
not one of the 24 upgrade researches is followed by an order of the upgraded unit, and no upgraded
unit is ordered before its upgrade. The recording names the button pressed, not the unit produced.

**Consequences.**

- There is no proof rule for an upgrade technology from later orders; a candidate "P4" was
  considered and is refuted by this measurement before being written. Every technology is settled by
  D-TECH-1 (R9).
- The production time of an order depends on the line's stage at that moment: an Archer trains in
  35 s, a Crossbowman in 27 s, and the order is the same. Across the three recordings 665 unit orders
  follow an upgrade that changes the training time (Archer to Crossbowman and Arbalester, Skirmisher
  to Elite Skirmisher, Cavalry Archer to Heavy Cavalry Archer). Costs do not change along those lines
  in these snapshots, so spending is untouched, but ordered production time, the queue ahead of an
  age-up and idle time all are.
- The knowledge base knows which unit a technology produces (`upgrades_unit`) and not which unit it
  upgrades from, so the line cannot be walked from an order's identifier. **A line table is a new
  knowledge fact**: per build, the base unit of each line and its stages in order, transcribed from a
  referenced source through 006's snapshot mechanism, like the population fields (R5) and the
  economic-unit list (R10). The reconstruction then prices and times an order at the stage every
  upgrade counted researched (D-TECH-1) by that moment selects.

## R13 — Where the new measurements live

The measurements in R1 (queue commands naming several buildings), R2 (refused commands kept in the
recording), R5 (empty unit-id lists, deletions naming unseen objects) and R15 (orders name the
line's base unit) describe the recording format, an outside-world subject, so a task moves each into `docs/data-sources.md` §2 under a test
that asserts it, and this file becomes their record of origin. The age-proof consistency of R3 is a
property of the knowledge base against the recordings, asserted by its test and recorded nowhere
else.

## R14 — Performance budget

SC-008 bounds the analysis at twice today's time, and **no baseline exists**: the repository measures
peak memory over the stream (`packages/replay-engine/tests/test_extract_limits.py`) and no elapsed
time. The first phase records the baseline over the committed recordings before any reconstruction
code lands, in a test that later phases must keep green. The reconstruction is one pass over the
stream plus a knowledge query per distinct (entity, civilisation, state), memoised; the memory
ceiling of 003's analysis contract binds it as it binds the stream.

## What remains unknown

- Which recorded commands the game executed (R2), and how a command naming several buildings
  distributes its amount (R1). Owner readings O1, O2.
- Whether any exact rule distinguishes a refused command from an executed one. If not, an
  arbitration (R2).
- The meaning of the lobby's starting-age values and of the attribute array past its fourth value
  (R4). Owner reading O4 and a referenced source.
- Whether any candidate population rule survives the readings (R5). Owner readings O6.
- Why so many move and interact commands carry no unit ids (R5).
