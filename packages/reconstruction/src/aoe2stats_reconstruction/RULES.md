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

- status: adopted
- settles: refund
- statement: an unstarted foundation that is deleted is refunded in full; any other deleted building is refunded nothing
- evidence: the owner's ruling of spec Clarifications, Session 2026-11-03
- ruling: specs/008-match-reconstruction/spec.md Clarifications, Session 2026-11-03
- readings: none

### `D-WIN-1`

- status: adopted
- settles: winner
- statement: the winner is the team with no resignation, when every other team's members all resigned; otherwise there is no winner
- evidence: the meaning of the Resign command (research R8)
- readings: none
- limits: a match ended otherwise establishes no winner
