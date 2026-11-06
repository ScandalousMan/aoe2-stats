# Contract — the proof and deduction rules registry

**Covers**: FR-005 to FR-007, FR-010, FR-010a, FR-011, FR-012, FR-003a, FR-003b, US3 | **Model**:
[data-model.md](../data-model.md) §5, §6 | **Research**: R2 to R9

## The file

`packages/reconstruction/src/aoe2stats_reconstruction/rules.toml`, one table per rule keyed by its
id. It is the only place a rule is written. A generated view,
`packages/reconstruction/src/aoe2stats_reconstruction/RULES.md`, is rendered by the loader's own
module, and a test compares it byte for byte with the committed file, exactly as 006's register view
is gated.

```toml
[rule."P1"]
family = "proof"
settles = "age"
statement = "an order of an entity whose age requirement, for the participant's civilisation and team, is N proves that the participant had reached age N by the order's clock"
evidence = "specs/008-match-reconstruction/research.md R3"
readings = ["511523321.O3"]
status = "adopted"

[rule."D-AGE-1"]
family = "deduction"
settles = "age"
statement = "an age-up is reached at its computed arrival when a later order proves the new age (P1); without one it is not reached, unless FR-010a's resignation clause holds"
ruling = "specs/008-match-reconstruction/spec.md Clarifications, Session 2026-11-03"
readings = []
status = "candidate"
```

## What the loader guarantees

Loading fails, and the package does not import, when any of these holds:

1. An id is duplicated or outside the two id shapes.
2. `family`, `settles` or `status` is outside its closed set.
3. A deduction rule with status `adopted` has neither `ruling` nor `readings` nor an `evidence`
   that states the game's own definition of a command (D-WIN-1 rests on what resigning means).
4. Any rule with status `adopted` has an empty `evidence`.
5. A rule with status `refuted` has no reading in `readings`.
6. A `readings` entry names no reading in any committed `playback.toml`.
7. Two adopted rules settle the same condition kind with overlapping statements of applicability;
   each condition kind has exactly one adopted rule per case, so no value can be settled two ways.

## The initial set

Every rule this feature needs, with the status the plan expects it to enter at. Statuses move only
in the change that earns them (data-model §6).

| Id | Settles | Statement, short | Enters as | Earned by |
| -- | ------- | ---------------- | --------- | --------- |
| P0 | team | the header's team is the team | adopted | 006 canonical-events contract (team) |
| P1 | age | an order requiring age N proves age N | adopted | research R3; O3 |
| P2 | controlled | an order issued from a building proves it stands, of the type the order states | adopted | 006 canonical-events contract (producing building) |
| P3 | alive | a unit commanded with its id is alive then | adopted | research R5 S1 |
| D-AGE-1 | age | FR-010 and FR-010a, as clarified | candidate | the 22 age-up readings (O1) |
| D-HOUSE-0 | housing | no housing pause ahead of an age-up | candidate | the 22 age-up readings |
| D-EXEC-1 | executed | how a recorded order is told executed or refused | **not yet written** | gate G1: O1, O2 |
| D-DIST-1 | distribution | how a command naming several buildings places its items | **not yet written** | O2 |
| D-TECH-1 | researched | an executed research counts completed at its modelled arrival when no observable obstacle occurred: no resignation before it, no owner deletion of the building before it, no enemy command targeting the building between click and arrival unless a later order from it proves it stood (FR-007a) | adopted | the owner's ruling, spec Clarifications 2026-11-06; checked by readings |
| D-CONTROL-1 | controlled | a building counts at an order's time when an earlier order from it proves it stood and no enemy command targeted it since; after a targeting, from its next proof; the starting Town Center from 0 | candidate | the owner's yes to this application of FR-007a (research R9) |
| D-CANCEL-1 | cancellation | the building with the most recently queued unstarted items of that unit, from the end | candidate | a recording that carries a cancellation (O7); synthetic streams until then |
| D-TIE-1 | tie | a deletion is the latest untied placement its owner targeted within a window | candidate | O5 |
| D-REFUND-1 | refund | an unstarted foundation is refunded in full, anything else nothing | adopted | spec Clarifications, Session 2026-11-03 |
| D-WIN-1 | winner | the team with no resignation, when every other team's members all resigned; otherwise no winner | adopted | the meaning of the Resign command (research R8); limit: a match ended otherwise establishes no winner |

No proof rule for a technology exists: research R15 measured that later orders name the line's
base unit after every upgrade, so the candidate was refuted before being written, and the registry
holds no `P4`.

FR-003b's hypothesis is **not** in the set as a usable rule. Research R2 records it refuted by the
recordings themselves, so it could enter only as `refuted`, citing that evidence. D-EXEC-1 replaces
it once G1 closes.

## Every deduction demonstrates absence (FR-007a)

A deduction rule that counts a state as holding enumerates, in its `statement`, every obstacle the
recording could show and asserts each absent, and names in `limits` every obstacle the recording
cannot show. A rule that assumes a state without that enumeration, in either direction, is refused by
review; the loader cannot read prose, so this is a reviewer's gate, written here so it is applied.

## Adoption gate

A rule moves to `adopted` in a change that also: adds its readings to the playback files, or cites
the ruling; makes every golden reconstruction that depends on it agree with every reading; and bumps
the reconstruction version. A reading that disagrees with an adopted rule fails the suite (FR-019),
and the rule is fixed or retired, never toleranced.

## What it must never do

- Hold a rule that names a probability, a band or a confidence. Those belong to `inferred` (006),
  and nothing here publishes at that tier.
- Change an adopted rule in place. A new statement is a new id.
