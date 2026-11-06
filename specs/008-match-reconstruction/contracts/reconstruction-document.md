# Contract — the reconstruction in the published analysis document

**Covers**: FR-001, FR-001a, FR-003, FR-008, FR-014 to FR-017, FR-021, FR-022, SC-002, SC-005 to
SC-007 | **Model**: [data-model.md](../data-model.md) §5, §7, §8 | **Research**: R2, R12

This amends 006's document (`specs/006-replay-analysis-foundations/contracts/analysis-document.md`)
through the same versioning seam, and only additively. It re-specifies nothing about requesting,
fetching, retaining or naming an analysis.

## Shape

`schema_version` becomes 3. One block is added, `reconstructed`, and the identity's
`reconstruction_engine` slot is filled. Every field of version 2 stays at its path with its type.

```json
{
  "schema_version": 3,
  "identity": {
    "reconstruction_engine": "aoe2stats-reconstruction@1+rules:sha256:…",
    "…": "… unchanged …"
  },
  "reconstructed": {
    "reconstruction.resources_spent": [
      { "participant": 1, "resource": "wood", "value": 0,
        "settled_by": [ { "condition": "age", "at_ms": 0, "by": "rule", "rule": "D-AGE-1",
                          "orders": [0], "facts": { "computed_arrival_ms": 0 } } ],
        "effects": [ { "civilisation": "…", "source_key": "…" } ] }
    ],
    "reconstruction.age_up_modelled_arrival_ms": [
      { "participant": 1, "age": 2, "reached": true, "value": 0, "settled_by": [ "…" ], "effects": [] }
    ],
    "reconstruction.untied_deletions": [
      { "participant": 1, "order": 0, "could_change": "reconstruction.resources_spent",
        "candidates": [ { "placement": 0, "refund": { "wood": 0 } } ] }
    ]
  },
  "provenance": { "reconstruction.resources_spent": { "tier": "reconstructed", "method": "…", "inputs": [] } }
}
```

- **One value per instance.** `value` is an integer. The block's types admit no pair, range, list of
  alternatives, float share or probability, so SC-002 is a property of the schema and a test asserts
  it by walking every instance type (as 006 asserts the knowledge base's union by introspection).
- **`reached`** appears on the age-up datum only. An age-up counted not reached publishes its
  computed arrival as `value` with `reached: false`, so the reader sees what the rule decided and on
  what; every order after it is priced at the previous age.
- **`settled_by`** is the data-model's Settlement list. Every rule id resolves to an adopted rule of
  the registry shipped with the reconstruction version the identity names.
- **`effects`** are the knowledge base's applied effects, by civilisation and source key, so the
  reader can find each in the snapshot the identity names.
- **`reconstruction.untied_deletions`** is FR-003a's report: a deletion no adopted rule ties to one
  placement, the datum it could have changed, and the refund each candidate placement would have
  given. It is a datum with a register entry of its own, at `reconstructed`, so it sits inside the
  block like every other. Its instances carry no `value` and no `settled_by`: they report what was
  not settled, which is why rule 13 checks each datum against its own declared shape.
- **A value withheld by a knowledge gap** is absent, and 006's `knowledge_gaps` says why (FR-009,
  006 FR-037). A value is never withheld for uncertainty (SC-003).

## Identity and version (FR-021, FR-022)

`reconstruction_engine` is the package's version and the digest of its rules registry. A change to
a rule's status or statement, an invariant, or the arithmetic changes one of the two, so the
identity digest changes, the staleness test recomputes, and the old document stays at its own key
(006 FR-042). The reproduce path stops refusing every non-`not-applicable` value and refuses only one
whose engine is not the installed one, naming what differs (006 contract, Reproduction).

## Validation — new rules beside 006's ten

Run before the object is written, like the first ten.

| # | Rule | Requirement |
| - | ---- | ----------- |
| 11 | Every datum inside `reconstructed` is a `published` register entry at `reconstructed` or `derived`; no such datum appears anywhere else, and no datum of another tier appears inside it. | FR-014, FR-015 |
| 12 | Every `settled_by` entry names a rule that exists in the registry the identity's engine names, with status `adopted`, and of the family its `by` states. | FR-006, FR-007, SC-005 |
| 13 | Every instance carries exactly its datum's declared keys, and every `value` is an integer. | FR-008, SC-002, FR-003a |
| 14 | `reconstruction_engine` is not `not-applicable` when `reconstructed` is present, and is `not-applicable` when it is absent. | FR-021 |

Rule 11 is tested the way 006 tested rule 6: a reconstructed value placed at an observed path, and
an observed value placed inside `reconstructed`, each rejected.

## Invariants (FR-017, SC-007)

The reconstruction checks the data-model's closed invariant set on its own output before the
document is built. A breach raises; the analyzer's existing barrier turns it into a refusal with the
breach as the message (a first analysis fails, a recompute keeps the prior document). A test plants
one breach per invariant in a synthetic stream and asserts nothing is published.

## The reader

`apps/web/src/features/analysis/api.ts` accepts version 3 structurally, as it accepted version 2.
US4's view reads `reconstructed` through new typed assertions, renders each value labelled as
modelled, and shows whether each condition was proven or settled by a rule. That rendering needs a
design-system spec first (constitution VI) and is planned in its own phase.
