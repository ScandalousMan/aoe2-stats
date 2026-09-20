# Contract — the versioned knowledge base

**Covers**: FR-022 to FR-039, SC-005 to SC-008 | **Model**: [data-model.md](../data-model.md) §6, §7
| **Research**: D3, D4, D5, D7

## On disk

```text
packages/knowledge/
├── packs/aoe2techtree/        vendored source files at one pinned commit + LICENCE.md
└── snapshots/<identity>/      one directory per snapshot, written once — under a size budget
    ├── snapshot.toml          identity, validation record, civilisations modelled
    ├── rules.json             normalised entities — the queryable body
    ├── effects.toml           hand-transcribed civilisation effects
    └── disagreements.toml     source disagreements (FR-028)
```

Both trees are package data, read through `importlib.resources`. Nothing reads a filesystem path and
nothing opens a socket (FR-026, SC-006).

**A pack is raw; a snapshot is derived from it and says so.** `scripts/ops/import_knowledge_pack.py`
reads a local checkout of the source at a stated commit and writes the pack. A second, pure step
normalises a pack into `rules.json`. Neither step touches the network; the script's header carries
the same warning `scripts/ops/sync_map_thumbnails.py` does, and states that automating the download
is the moment a provider becomes mandatory (FR-032).

**The format check will reach the pack, and must not.** The workspace's `format:check` globs every
JSON file under `packages/` and ignores only what `.gitignore` names — a `.prettierignore` is not
read, because the script passes its own ignore path. A vendored data file would therefore fail the
pull-request check until someone "fixes" it by reformatting, which rewrites vendored bytes and
invalidates every digest taken over them. The change that adds the pack narrows both format globs in
`package.json` to exclude `packages/knowledge/packs` and `packages/knowledge/snapshots`, and a test
asserts a pack file's bytes match the checksum recorded at import.

## Identity and immutability

Identity is `source`, `source_version`, `describes_build`, `digest` (FR-024). On load the digest is
recomputed over `rules.json` and `effects.toml`; a mismatch refuses to load. A test walks every
committed snapshot directory and fails if any file's digest differs from its recorded one — which is
how FR-025's "never modified" is asserted and not merely asked for.

## Promotion (FR-034)

`source change` → `new pack revision` → `new snapshot, unvalidated` → `validation recorded` →
`promoted`. Only a promoted snapshot is resolvable by build. `snapshot.toml` carries a
`promoted = true` that the loader honours, and a validation record that may not be empty when it is
set.

**Carry-forward** (research D4) is one kind of validation. Its record lists every build between the
source revision's build and `describes_build`, and for each: the notes consulted, where they were
read, the date, and the reading — *no field this pack carries changed*, or the fields that did. A
build with no entry in that list makes the snapshot unpromotable.

## Resolution by build (FR-027)

```python
def snapshot_for(build: int) -> Snapshot | KnowledgeGap
```

Exact match on `describes_build` among promoted snapshots, or a gap with cause
`no-snapshot-for-build`. There is no nearest, no latest, no fallback parameter.

## The query surface

```python
def cost(entity, *, civilisation) -> Answer[Cost] | KnowledgeGap
def production_time(entity, *, civilisation) -> Answer[Duration] | KnowledgeGap
def age_requirement(entity, *, civilisation) -> Answer[Age] | KnowledgeGap
def prerequisites(entity, *, civilisation) -> Answer[Sequence[EntityRef]] | KnowledgeGap
def produced_at(entity, *, civilisation) -> Answer[EntityRef] | KnowledgeGap
def available_to(entity, *, civilisation) -> Answer[bool] | KnowledgeGap
def name(entity) -> Answer[str] | KnowledgeGap
```

- `civilisation` is **keyword-only and required** on every rule query. There is no way to ask for a
  generic value, so there is no way to be handed one (FR-023).
- `Answer` carries the value, the snapshot identity, the source the stored value came from, and the
  effects applied, in order (US2 scenario 1).
- The union has **no third branch**. No function in the package returns a bare value, accepts a
  default, or catches a gap and continues. SC-008's "by construction" is this signature, and a test
  asserts by introspection that every public query returns the union.

## Civilisation qualification (research D5)

In order, for a rule query qualified by civilisation *c*:

1. *c* not in `civilisations_modelled` → gap, cause `civilisation-not-modelled`. Every cost and time
   for *c* refuses, because which fields a bonus touches is exactly what is not known.
2. An effect for *c* touches this entity and field and is `modelled = no` → gap, cause
   `effect-not-modelled`.
3. Otherwise apply each matching effect in file order and return the adjusted value with the effects
   listed.

`name` is not civilisation-qualified and an unresolvable identifier degrades to the bare identifier
at the presentation boundary, as 003 FR-043a already requires — it never gaps an analysis.

## Entity resolution

A unit identifier may live in the source's unit table or its upgrade table; four technology
identifiers in the committed fixture do. The normaliser merges both into one keyed space and records
which table each came from. A test asserts every entity referenced by every committed reference
recording resolves.

## Gaps

- **Severity is computed** (research D7): the gap's `prevents` is the set of register data whose
  `requires_knowledge` names its field; non-empty means `blocking`.
- **The coverage pass** (`coverage.py`) takes a canonical stream, collects every entity and every
  participant civilisation, and asks for every field any register datum requires. Its output is the
  gap list the document publishes. **SC-007a** is this pass over each committed recording returning
  no blocking gap.
- **SC-007**: a test deletes one field from an in-memory copy of a snapshot, runs the pass, and
  asserts that exactly the dependent data are withheld, a gap names the entity, field, build and
  civilisation, and every other datum is unchanged.
- **Aggregate** (FR-039): gaps are written to `analysis_knowledge_gaps`, and the table **is** the
  aggregate. The report is a grouped count by build, cause and severity over a window, exposed as
  one repository function and printed by one check script. The analyzer has no run, no counters and
  no summary to attach a line to — the ingester's quarantine counter is a column on a per-run table
  the analyzer has no equivalent of — and none is invented for this.

## Licence gate (FR-031, FR-033)

`packs/aoe2techtree/LICENCE.md` carries the five fields `scripts/checks/asset_packs.py` enforces,
named exactly as it matches them: `Source`, `Licence`, `Permitted usage`, `Ruling`, `Checked`. The
ruling leads with **COPY IN**, the one verdict besides READ ONLY the gate accepts once the change
that adds the roots has taught it to refuse a third — today it tests for READ ONLY alone.

That check scopes itself by a list of **(root, size budget) pairs**. Two pairs are added in the
change that adds the pack — `packages/knowledge/packs` and `packages/knowledge/snapshots`, each with
its own named budget constant and its own stated justification, as the two existing roots have. The
snapshots root is append-only by design and ships inside the package, so it is the one that needs a
ceiling most. The pull-request workflow's `asset-packs` path filter gains both. Until then the check
neither sees the pack nor runs when it changes.

`docs/asset-packs.md` gains a **third section** for knowledge packs, as feature 005 added one for
typefaces, and its opening scope sentence — which today names game assets only — is widened. The
row does not go in the game-assets table.

**Residual risk, stated once.** The files are MIT; the values in them were produced upstream by
reading the game's data file, which the publisher's usage rules do not authorise. This repository
already weighed that for this same source — `docs/data-sources.md` §1 rules its data MIT, and the
risk register's R7 records the residual — so the ruling cites both and restates neither. It is not
the flags pack's position, which has no game-derived content at all.

Sources ruled *read and transcribe only* appear in no pack. A value transcribed from one is an
effect or a disagreement entry carrying the sentence read, where, by whom and when.

## Source assessments (FR-029, FR-030)

Land in `docs/data-sources.md` as a new section, one subsection per source assessed in research D3,
with the date. That section is the living home; research D3 is its record of origin.
