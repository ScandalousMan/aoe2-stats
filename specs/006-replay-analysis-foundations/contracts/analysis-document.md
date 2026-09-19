# Contract — the published analysis document, next version

**Covers**: FR-007 to FR-011, FR-040 to FR-044, SC-002 to SC-005, SC-011 | **Model**:
[data-model.md](../data-model.md) §3, §8 | **Research**: D8, D9

This amends the document defined in
`specs/003-player-search-match-analysis/contracts/analysis.md` through the versioning seam that
contract provides. It re-specifies nothing about how an analysis is requested, fetched, retained or
rate-limited (FR-048).

## Shape — additive only

Every field of the current version stays at its current path with its current type. Four blocks are
added and `schema_version` increments.

```json
{
  "schema_version": 2,
  "envelope": { "extracted_at": "…" },

  "game_id": 0, "point_of_view_profile_id": 0,
  "engine": { "name": "…", "version": "…", "deps": { "…": "…" } },
  "source_recording": { "object_key": "…", "sha256": "…" },
  "participants": [ "… unchanged …" ],

  "identity": {
    "digest": "…",
    "recording": { "object_key": "…", "sha256": "…" },
    "parser": { "name": "…", "version": "…" },
    "parser_dependencies": { "…": "…" },
    "knowledge": { "source": "…", "source_version": "…", "describes_build": 0, "digest": "…" },
    "reconstruction_engine": "not-applicable",
    "analytics": "…"
  },

  "provenance": {
    "participant.age_up_commands": { "tier": "observed", "method": "…", "inputs": [] }
  },

  "inferred": {
    "participant.group_control_lost": [
      { "participant": 1, "from_ms": 0, "units": 0,
        "confidence": { "level": "medium", "basis": "…" },
        "non_claim": "not a casualty count — …" }
    ]
  },

  "knowledge_gaps": [
    { "entity": { "kind": "unit", "id": 0 }, "field": "cost", "build": 0, "civilisation": 0,
      "cause": "civilisation-not-modelled", "prevents": ["…"], "severity": "blocking" }
  ]
}
```

`extracted_at` moves under `envelope` **and stays at its old path** for one version, because the web
reader validates shape strictly; the old path is removed by whichever later version the reader has
stopped requiring it in. `engine.deps` is kept and now populated; `identity.parser_dependencies`
is the same record.

When no snapshot matches the recording's build, `identity.knowledge` is
`{ "absent": "no-snapshot-for-build", "build": 0 }` and one blocking gap says so (FR-027).

## Validation — `aoe2stats_core.truth.validate`

Run by the analyzer **before** the object is written. A failing document is not published; the
analysis fails with the validator's message, through 003's existing failure path.

| # | Rule | Requirement |
| - | ---- | ----------- |
| 1 | Every leaf outside the wall-clock set, `identity`, `provenance` and `knowledge_gaps` resolves to exactly one `published` register datum. | FR-006, SC-001 |
| 2 | Every such datum present in the document has a `provenance` entry, and every `provenance` key is present in the document. | FR-007, SC-002 |
| 3 | Each entry's tier equals the register's, and is no stronger than its weakest input. | FR-008 |
| 4 | Each entry names a method. | FR-009 |
| 5 | A datum at `inferred` or `predicted` appears **only** under `inferred`, and each instance carries a confidence whose level is in the closed set and whose basis is non-empty. | FR-010, FR-010a, SC-002 |
| 6 | No datum at `inferred` or `predicted` appears at any path outside `inferred`; no datum at a stronger tier appears inside it. | FR-011, SC-003 |
| 7 | A datum whose register entry declares a non-claim carries it on every instance. | FR-013 |
| 8 | No datum is present whose `requires_knowledge` intersects a blocking gap in `knowledge_gaps`. | FR-037 |
| 9 | `identity.parser_dependencies` is non-empty. | FR-044, SC-011 |
| 10 | `identity.digest` recomputes from the other identity fields. | FR-040 |

Rule 6 is tested the way SC-003 words it: a document is built with a coaching-style conclusion
placed at an observed path, and validation must reject it — once per tier boundary, not once.

## Addressing and preservation (FR-042, SC-005)

- Object key: the current per-match prefix, then the identity digest. The exact layout is
  `packages/storage`'s to name; the contract is that **two different identities never share a key**
  and that a key, once written, is never written again.
- `match_analyses.result_key` names the current document. Its primary key is unchanged.
- A recompute under a new identity writes a new object and repoints the row. It deletes nothing.
- A read by identity resolves the older object directly. SC-005 is: publish, record the identity,
  promote a new snapshot, recompute, then fetch by the first identity and compare.

## Determinism (FR-041, SC-004)

Everything outside the **wall-clock set** — `envelope`, and the legacy top-level `extracted_at` kept
for the reader — is a pure function of the identity. Serialisation is canonical: keys
sorted where order carries no meaning, stream order kept where it does, one fixed float format,
UTF-8, no trailing whitespace. SC-004 compares the bytes of everything outside the wall-clock set across two
runs, and across a run in a fresh process, so that dictionary ordering or a cached clock cannot pass
by accident.

## Reproduction (FR-043)

```python
def reproduce(identity: AnalysisIdentity) -> bytes
```

Reads the retained recording through `packages/storage`, verifies its checksum, resolves the named
snapshot from package data, and refuses — naming what is missing — if the installed parser version
or dependencies differ from the identity. It reaches no external source, and a test runs it with the
network blocked.

The refusal is deliberate. Reproducing under a different parser and calling the result the same
analysis is the silent rewrite FR-042 forbids; the honest outcomes are *identical* or *cannot
reproduce here, because*.

## The reader

`apps/web/src/features/analysis/api.ts` already accepts this document unchanged: it requires the
existing fields, accepts any numeric `schema_version`, and ignores keys it does not know — and it
requires `extracted_at` at its current path, which is why that field is duplicated and not moved.
The only change there is a test pinning that a version 2 fixture parses. No component changes.
Displaying a tier or a gap is a later feature's decision and needs a design-system spec first.
