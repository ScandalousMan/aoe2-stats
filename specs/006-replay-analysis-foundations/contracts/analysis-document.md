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
    "participant.group_silence_episodes": [
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
| 8 | No datum is present that a gap in `knowledge_gaps` withholds, **whatever the gap's `severity`**: the gap's field is named in the datum's `requires_knowledge`, or the datum is in the gap's `prevents`, or the gap is whole-build and the datum needs any knowledge. A gap on a field a present datum requires cannot honestly be informational, so the label is not trusted (T666k). | FR-037 |
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
- **A recompute has to be triggered.** Today a published row is stale only when the parser's name or
  version differs, so a new knowledge or analytics version would never recompute at all. The
  staleness test becomes a comparison of the stored identity digest with the current one.
- The row's `engine_deps` column, which exists and which nothing has ever written, is written with
  the same record the document carries.
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

## Names are served beside the document (T709)

The stored document carries identifiers only, and stays that way: its bytes are what the identity
digest and the object key vouch for (FR-042), so no name is ever written into it. The names are
served by `GET /api/matches/{game_id}/analysis` as one more top-level key, `knowledge_names`,
appended after the stored object, whose bytes are unchanged and are a prefix of the body up to the
closing brace. A reader that ignores unknown keys, as the web reader does, is unaffected.

```json
"knowledge_names": {
  "snapshot": { "describes_build": 0, "digest": "…" },
  "technology": { "101": "Feudal Age" },
  "unit": { "83": "Villager" },
  "building": { "70": "House" },
  "provenance": {
    "names.snapshot.describes_build": { "tier": "derived", "method": "knowledge-snapshot.name@2", "inputs": [] },
    "names.snapshot.digest": { "tier": "derived", "method": "knowledge-snapshot.name@2", "inputs": [] },
    "names.technology": { "tier": "derived", "method": "knowledge-snapshot.name@2", "inputs": ["participant.researches.technology_id", "participant.age_up_commands"] },
    "names.unit": { "tier": "derived", "method": "knowledge-snapshot.name@2", "inputs": ["participant.trainings.unit_id"] },
    "names.building": { "tier": "derived", "method": "knowledge-snapshot.name@2", "inputs": ["participant.builds.building_id"] }
  }
}
```

- **The snapshot is the one the document's own identity names**, matched on `source`,
  `source_version`, `describes_build` and `digest` among the packaged snapshots, a demoted one
  included. Never the snapshot promoted for the build now, never the nearest build's (FR-027,
  FR-038). `snapshot` records which one answered.
- **An id the snapshot does not name is absent from its kind's record**, and the page shows the
  identifier (003 FR-043a). Nothing is substituted.
- **A name is the snapshot's, cleaned of the source's line-break markup.** The vendored value is
  `"Town<br>\nCenter"`; the label served is `"Town Center"`. One rule: a hyphen directly after a
  letter, followed by a break (a line-break tag or whitespace) and then a lower-case letter, joins
  the word (`Circum-<br>\nnavigation` is `Circumnavigation`); the same hyphen followed by a break
  and then any other character keeps the hyphen and drops the break with no space
  (`Man-at-<br>\nArms` is `Man-at-Arms`); a hyphen not directly after a letter is left alone
  (`Foo - bar` stays); every other break becomes one space (`Double-Bit<br>\nAxe` is
  `Double-Bit Axe`), whitespace collapses and the label is trimmed. A label with no letter or
  digit left is not served, and its id is left out like an unresolved one. The snapshot is not
  edited, and the method is `knowledge-snapshot.name@2`.
- **No block at all** when the identity names no snapshot (`absent`), names one that is not
  installed or is installed under another digest, or when the document has no `identity` (version
  1). The body is then the stored bytes exactly.
- **It never fails the read.** A fault resolving names is logged and the stored bytes are served.
- **Resolved on the request path, by decision (2026-10-17, T709a).** The lookup runs when the
  document is served, in `apps/analyzer`'s `names.py`, not when it is analysed: writing names into
  the document would change its bytes and its identity digest (FR-042). It is a read of package
  data - no fetch, no recording parse, no engine, no capture-budget name - and the boundary test
  holds it to that, granting it eight named symbols (seven of `aoe2stats_knowledge`, and the register itself, which
  the block's provenance reads) and no other import of the knowledge or truth packages (plan.md, Constraints).
- **The served leaves are published data (FR-006, FR-007).** Each has a register entry, in
  `register.toml`: `names.snapshot.describes_build`, `names.snapshot.digest`, `names.technology`,
  `names.unit` and `names.building`, tier `derived`, requiring the knowledge field `name`, the
  snapshot as source. Their paths are `knowledge_names.*`, the three kinds being wildcards over the
  stringified id. Rule 1 above is checked over the served bytes as well as the stored body
  (`apps/analyzer/tests/test_names.py`), so a field added to the block with no entry fails.
- **The block carries its tier as data (FR-007, FR-009), in a `provenance` map of its own.** Keyed by
  the same register ids as the stored one, each entry is `{tier, method, inputs}` in the stored
  provenance's shape, for exactly the data the block holds: the two `snapshot` fields always, and a
  kind's datum only when at least one name of that kind resolved (an empty record is not a value).
  The tier and inputs are read from the register entry and the method is the one the analyzer's
  methods table assigns the `names.` family; nothing is typed again. The stored document's own
  `provenance` is not extended and not changed: it is part of the bytes the digest vouches for. The
  validator reads a document's top-level `provenance`, so the check presents the block as the
  document it is the provenance of (its data under `knowledge_names`, its map as `provenance`) and
  asks rules 1 to 4 of it over the served bytes: every leaf has a datum, every datum present has an
  entry and every entry's key is present, each tier equals the register's, each entry names a
  method. Rules 8 to 10 stay the stored body's.
- **The reader accepts the block only beside the identity it came from.** The web reader ignores a
  `knowledge_names` block whose `snapshot` (`describes_build`, `digest`) is not the one the
  document's own `identity.knowledge` names, and every id then renders unresolved, as it did
  before names were served. The page shows no tier, so the reader does not read the block's
  `provenance`: a block with the key is accepted as before, and a block whose `provenance` is
  malformed still renders its names, because a defect in an annotation does not make a name wrong
  (the opposite choice from a malformed `snapshot` or kind record, which reads as no names).
