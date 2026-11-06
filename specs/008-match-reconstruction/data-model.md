# Phase 1 — Data model: Match reconstruction

**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

Eleven entities. Ten are pure values computed per analysis and stored nowhere but in the published
document; one, the rule, is a record in a file shipped with the package. No table and no migration:
the published document already has an identity-addressed key, and 003's row already points at it
(006 data-model §8).

Every closed vocabulary below is closed in code, an enumeration and not a string. No measurement is
stated here; where an entity depends on one, it references [research.md](./research.md).

## 1. Order

A command the canonical stream attributes to a participant (spec, Key Entities). Built by one fold
over 006's stream, never by re-parsing.

| Field | Type | Rule |
| ----- | ---- | ---- |
| `participant` | slot | Never an observer; never after the participant's resignation (006 canonical-events, exit discipline). |
| `clock_ms` | integer | The event's match clock. |
| `kind` | closed: `unit`, `research`, `placement`, `cancellation`, `deletion` | One per source event kind. |
| `entity` | knowledge entity reference | Kind and identifier, in the recording's build. Absent for a deletion. |
| `count` | positive integer | Units only; 1 otherwise. |
| `buildings` | ordered tuple of object ids | Every producing building the command names (research R1). Empty for a placement or a deletion. |
| `object` | object id, optional | The deleted object, for a deletion. |
| `source_event` | index into the stream | So that a settlement can name the order that proved something, and a reader can find it. |

**Execution is not a field.** Whether the game executed an order is decided by an adopted rule
(gate G1, research R2), and recorded as a settlement (section 5) on the queue item it produces.

## 2. Queue item

One unit of work in one building's queue: the production of one unit, or one research.

| Field | Type | Rule |
| ----- | ---- | ---- |
| `order` | Order | The order it came from. A command naming several buildings yields items in the buildings the distribution rule places them in (research R1, owner reading O2). |
| `building` | object id | Exactly one. |
| `enqueued_ms` | integer | The order's clock. |
| `started_ms`, `finished_ms` | integer | Modelled. `started_ms` is the later of `enqueued_ms` and the previous item's `finished_ms`, plus any idle time the adopted rules place before it. |
| `duration_ms` | integer | The knowledge base's production time for the participant's civilisation, team and settled state at `started_ms`. |
| `executed` | Settlement | Whether the game executed the order (G1). An item not executed occupies no time and costs nothing. |

**State.** `enqueued` → `started` → `finished`, or `enqueued` → `cancelled` (an attributed
cancellation removes unstarted items only), or `enqueued` → `refused` (G1's rule). Forward only.

**Invariants** (FR-017, section 8): `started_ms ≥ enqueued_ms`; items of one building never overlap;
a cancellation never removes a started item and never more items than are unstarted.

## 3. Starting state

Per participant (FR-026, research R4).

| Field | Type | Tier | Rule |
| ----- | ---- | ---- | ---- |
| `resources` | food, wood, stone, gold | `decoded` | From the `starting-attributes` event (Tier A decoder). Cross-checked against the lobby preset and civilisation; a disagreement refuses the analysis as an invariant breach. |
| `age` | 1 to 4 | `observed` | From the lobby's starting-age preset, through a mapping confirmed by owner reading O4. An unconfirmed preset value is a knowledge gap, never a guess. |
| `objects` | units and buildings with counts | `reconstructed` | From the knowledge table of starting objects for the build, civilisation and preset (research R4). |
| `population_limit` | integer | `observed` | From the lobby. |

## 4. Condition

One match-state question an effect's price or time depends on, at one order (FR-005).

| Field | Type | Rule |
| ----- | ---- | ---- |
| `kind` | closed: `age`, `researched`, `team`, `team_researched`, `controlled`, `executed` | The first five are the knowledge base's own condition inputs (006 knowledge-base contract, `Context`); `executed` is G1's. |
| `subject` | per kind | The age asked about; the technology; the entity set counted; the order. |
| `at_ms` | integer | The moment the condition is asked at, never later (spec, Edge Cases: a proof after the order proves nothing about it alone). |
| `value` | per kind | Exactly one. There is no interval, no set and no probability (FR-008). |
| `settled_by` | Settlement | Required. |

**`team` needs no settlement beyond the header.** The team is observed in `match-started`; it is
settled by the header itself, recorded as proof **P0**, so every condition has a settlement and none
is special-cased.

## 5. Settlement

What settled one condition (US3, FR-006, FR-007, FR-014).

| Field | Type | Rule |
| ----- | ---- | ---- |
| `by` | closed: `proof`, `rule` | |
| `rule` | rule id | A proof names a proof rule (P-family), a rule names a deduction rule (D-family). It must resolve to an **adopted** rule (section 6). |
| `orders` | tuple of stream indices | The orders the rule used: the confirming order of an age, the order issued from a building, the resignation. Empty only for P0. |
| `facts` | mapping of named values | Every other input the rule used, named as the rule's record names them (the computed arrival, the resignation time, the attacking command's index). |

A settlement is data in the published document, so a reader recomputes the value without reading
code (SC-005).

## 6. Rule

A record of the closed rules registry (contracts/rules.md). Lives in
`packages/reconstruction/src/aoe2stats_reconstruction/rules.toml`, read through
`importlib.resources`.

| Field | Type | Rule |
| ----- | ---- | ---- |
| `id` | `P<n>` or `D-<NAME>-<n>` | Unique, stable. A changed rule is a new id; the old one is retired, never edited. |
| `family` | closed: `proof`, `deduction` | |
| `settles` | closed: the condition kinds of section 4, plus `refund`, `cancellation`, `tie`, `distribution`, `winner`, `housing` | What it can settle. |
| `statement` | text | The rule, precisely enough to recompute. |
| `evidence` | reference | Into this research, `docs/data-sources.md`, or a playback reading. Never a restated number. |
| `ruling` | reference, optional | The owner's ruling it rests on (spec Clarifications, or a later dated ruling). A deduction rule needs `ruling` or `evidence` that the game behaves that way (FR-007). |
| `readings` | list of reading ids | The playback readings that checked it (FR-019). |
| `status` | closed: `candidate`, `adopted`, `retired`, `refuted` | Only `adopted` settles a published value. |
| `limits` | text, optional | What the rule cannot see, stated (D-WIN-1's targetless commands, D-CONTROL-1's destructions). |

**State.** `candidate` → `adopted` (needs its evidence and, for a deduction, its ruling or its
readings) → `retired` (replaced by a new id). `candidate` → `refuted` when a reading disagrees. A
change of status of an adopted rule bumps the reconstruction version (FR-021).

## 7. Reconstructed value

One published number (spec, Key Entities).

| Field | Type | Rule |
| ----- | ---- | ---- |
| `datum` | register id | Must resolve to a `published` register entry at `reconstructed` or `derived` (FR-014). |
| `participant` | slot | |
| `key` | per datum | The resource, the building object, or the age. |
| `value` | integer | Milliseconds or resource units. One number; the type admits nothing else (FR-008, SC-002). |
| `settled_by` | tuple of Settlement | One per condition the value depends on, in the order the computation met them. |
| `effects` | tuple of effect references | The knowledge base's applied effects, from its answers (006 knowledge-base contract, `Answer.effects`). |

The snapshot identity is the document's (`identity.knowledge`), stated once, not per value.

**An untied deletion is reported, not valued.** FR-003a's report is its own datum,
`reconstruction.untied_deletions`, whose instances name the deletion, the datum it could have
changed and each candidate placement's refund, and carry no `value` (contracts/reconstruction-document.md).

**The observed click stays where 006 published it.** An age-up's modelled arrival is a separate
datum at a separate path (FR-016); nothing here writes into `participants[]`.

## 8. Invariant and invariant breach

The closed set of FR-017, held in `packages/reconstruction` as an enumeration with one check each.

| Invariant | Holds when |
| --------- | ---------- |
| `spending-non-negative` | every resource spent is ≥ 0 |
| `cancellation-bounded` | no cancellation removes more items than are unstarted |
| `population-non-negative` | every population figure is ≥ 0 (from the population phase) |
| `idle-bounded` | every idle time is ≥ 0, and idle plus production never exceeds the time the building existed (from the population phase) |
| `arrival-after-click` | no age-up arrives before its click |
| `nothing-after-exit` | no order is attributed after its participant resigned |
| `military-within-total` | the military share never exceeds the total, per resource |
| `starting-resources-agree` | the decoded starting resources equal the lobby-and-civilisation derivation |
| `proof-not-contradicted` | no adopted rule settles a condition that a proof contradicts (an age counted not reached at an order that proves it) |

A **breach** records the invariant, the participant, the datum and the offending value. A document
with a breach is not published; the analysis fails through 003's failure path with the breach as
its message, and a recompute keeps the prior document (006 data-model §8).

The last invariant is the one research R2 says this feature needs most: it is how the queue model
contradicting the recording's own proofs becomes a refusal rather than a published number.

## 9. Golden reconstruction

Per committed recording (FR-018). A file beside the recording:
`tests/fixtures/replays/<recording>.reconstruction.json`, written by hand from the orders and the
knowledge base, in the published block's shape (contracts/reconstruction-document.md), and compared
byte for byte with what the analysis produces. Regenerated only under the fixtures README's rules.

## 10. Playback reading

What a person read in the game, playing a committed recording back (FR-019). A file beside the
recording: `tests/fixtures/replays/<recording>.playback.toml`, one table per reading.

| Field | Rule |
| ----- | ---- |
| `id` | Stable, cited by rules and goldens. |
| `request` | The owner-reading request it answers (`specs/008-match-reconstruction/owner-readings.md`). |
| `participant`, `at` | Who and when in match time, as the game shows it. |
| `quantity` | What was read: an age-up arrival, a queue's contents, a stockpile, a population. |
| `value` | As read. `unreadable` is allowed and says where it was looked for. |
| `read_by`, `read_on`, `build_shown` | Who, when, and the build the game reported. |

A reading is the one place its value is written. The request list asks; this file answers; a test
asserts every reconstructed value with a reading equals it (SC-001, SC-010) and reports, per rule,
the share of conditions it settled (SC-009).

## 11. Town Center idle period

Deferred to the population phase (research R5). Declared here so the document's shape does not
change when it lands: a building, a start, an end, a cause from the closed set `empty-queue`,
`housed`, and the settlement of its cause.
