# The proof and deduction rules

<!-- GENERATED FILE. Do not edit. -->

This file is generated from `rules.toml`, the only place a rule is written. Regenerate it with `uv run python -m aoe2stats_reconstruction.rules`; a test fails when the two diverge.

## Proofs (4)

### `P0`

- status: adopted
- settles: team
- statement: the team the header records for a participant is that participant's team
- evidence: 006 canonical-events contract (team)
- readings: none

### `P1`

- status: adopted
- settles: age
- statement: an order of an entity whose age requirement, for the participant's civilisation and team, is N proves that the participant had reached age N by the order's clock
- evidence: specs/008-match-reconstruction/research.md R3
- readings: none

### `P2`

- status: adopted
- settles: controlled
- statement: an order issued from a building proves that the building stands at the order's time, and is of the type the order states
- evidence: 006 canonical-events contract (producing building)
- readings: none

### `P3`

- status: adopted
- settles: alive
- statement: a unit commanded with its id is alive at the command's time
- evidence: specs/008-match-reconstruction/research.md R5, S1
- readings: none

## Deductions (8)

### `D-AGE-1`

- status: candidate
- settles: age
- statement: an age-up is reached at its computed arrival when a later order proves the new age (P1); without one it is not reached, unless FR-010a's resignation clause holds
- ruling: specs/008-match-reconstruction/spec.md Clarifications, Session 2026-11-03
- readings: none

### `D-HOUSE-0`

- status: candidate
- settles: housing
- statement: no housing pause precedes an age-up
- evidence: the age-up readings (owner reading O1)
- readings: none

### `D-TECH-1`

- status: adopted
- settles: researched
- statement: an executed research counts completed at its modelled arrival when no observable obstacle occurred: no resignation of its owner before the arrival, no deletion of the building by its owner before the arrival, and no enemy command targeting the building between the click and the arrival, unless a later order from that building proves it stood (FR-007a)
- evidence: the owner's ruling of spec Clarifications, Session 2026-11-06
- ruling: specs/008-match-reconstruction/spec.md Clarifications, Session 2026-11-06
- readings: none
- limits: an obstacle the recording cannot show: a destruction of the building by a fight, which the recording carries no outcome of

### `D-CONTROL-1`

- status: candidate
- settles: controlled
- statement: a building counts as controlled at an order's time when an earlier order from it proves it stood (P2) and no enemy command has targeted it since; after a targeting, from its next proof; the starting Town Center from time 0
- ruling: owner, 2026-11-10, re-derived in the light of feature 009's findings; then the owner's acceptance of this application of FR-007a (research R9)
- readings: none
- limits: a destruction of the building that no command shows

### `D-CANCEL-1`

- status: candidate
- settles: cancellation
- statement: a cancellation of a unit applies to the building with the most recently queued unstarted items of that unit, taking them from the end of its queue
- evidence: synthetic streams until a recording carries a cancellation (owner reading O7)
- readings: none

### `D-TIE-1`

- status: candidate
- settles: tie
- statement: a deletion is the latest untied placement its owner targeted within a window
- evidence: owner reading O5
- readings: none

### `D-REFUND-1`

- status: candidate
- settles: refund
- statement: a deletion tied to its placement (D-TIE-1) is refunded in full when no villager command named that foundation between its placement and its deletion, which is read as construction never having begun; when one did, or when the deleted building is any other than a foundation, it is refunded nothing. A command counts as a villager command only when every unit it names is shown by the recording to be a villager, and as naming the foundation when its target is the foundation's object
- evidence: the owner's rulings of spec Clarifications, Sessions 2026-11-03 and 2026-11-18
- ruling: specs/008-match-reconstruction/spec.md Clarifications, Sessions 2026-11-03 (the hypothesis) and 2026-11-18 (the observable)
- readings: none
- limits: the recording cannot show that a command came from a villager (no produced unit carries a class, and a starting object has no producer, so no unit is shown to be a villager), nor that a deleted building was still a foundation, so the rule cannot yet be computed from a recording (T983, open owner arbitration); and builders sent by the placement command itself, whose work this observable misses, so such a foundation counts as unstarted and is refunded

### `D-WIN-1`

- status: adopted
- settles: winner
- statement: the winner is the team with no resignation, when every other team's members all resigned; otherwise there is no winner
- evidence: the meaning of the Resign command (research R8)
- readings: none
- limits: a match ended otherwise establishes no winner; commands that name no object (a move or an interact with an empty unit list) show neither a team's survival nor its loss, so they are never read as either
