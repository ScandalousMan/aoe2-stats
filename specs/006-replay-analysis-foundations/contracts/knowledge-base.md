# Contract — the versioned knowledge base

**Covers**: FR-022 to FR-039, SC-005 to SC-008 | **Model**: [data-model.md](../data-model.md) §6, §7
| **Research**: D3, D4, D5, D7

## On disk

```text
packages/knowledge/
├── packs/<name>/              one vendored pack per pinned revision: source files at one commit
│                              + MANIFEST.json + LICENCE.md
└── snapshots/<label>/         one directory per snapshot, written once — under a size budget
    ├── snapshot.toml          identity, validation record, civilisations modelled, `supersedes`
    ├── rules.json             normalised entities — the queryable body
    ├── effects.toml           hand-transcribed civilisation effects
    ├── aliases.toml           optional: identifiers the pack does not name (FR-022d)
    └── disagreements.toml     source disagreements (FR-028)
```

Both trees are package data, read through `importlib.resources`. Nothing reads a filesystem path and
nothing opens a socket (FR-026, SC-006).

**The directory name is a label, never an identity and never parsed.** Identity is the four fields in
`snapshot.toml` (FR-024), and resolution is exact-match on `describes_build` among the promoted snapshots no
other snapshot supersedes (below) and nothing else — so no code reads the directory name and a rename breaks nothing. The earlier
wording here said `<identity>/`, which was never what the directories carry and which no reader could
have acted on: two promoted snapshots of this pack share a digest by construction and differ only in
`describes_build`, so a name built from the identity would be four fields long and still not be what
resolution uses.

What the label owes is honesty, and that is a real obligation because **FR-025 makes it permanent the
moment an analysis names the snapshot**. A label MUST NOT describe a promoted, production snapshot as
a fixture or a stub, and MUST carry the build it describes, so that a gap row, an object key or a
directory listing is readable without opening `snapshot.toml`. A snapshot that exists only to
exercise the loader is a test artifact and says so in its label.

**A pack is raw; a snapshot is derived from it and says so.** `scripts/ops/import_knowledge_pack.py`
reads a local checkout of the source at a stated commit and writes the pack. A second, pure step
normalises a pack into `rules.json`. Neither step touches the network; the script's header carries
the same warning `scripts/ops/sync_map_thumbnails.py` does, and states that automating the download
is the moment a provider becomes mandatory (FR-032).

**Several packs, one per pinned revision; a newer one goes beside, never over.** A promoted snapshot
is immutable (FR-025) and must stay re-derivable from the pack it was imported from, so a newer
source revision is vendored in a new directory next to the existing ones and the older pack is never
replaced. A snapshot finds the pack it was derived from by `source_version`, the `commit` that
pack's `MANIFEST.json` pins, not by a directory name: the normaliser takes the pack's name as a
required argument and the re-derivation test resolves it from each snapshot's `source_version`.
`scripts/checks/pinned_source_commit.py` refuses a pack directory with no `MANIFEST.json`, two packs
pinning one commit, and a pack no snapshot's `source_version` names.

**The format check will reach the pack, and must not.** The workspace's `format:check` globs every
JSON file under `packages/` and ignores only what `.gitignore` names — a `.prettierignore` is not
read, because the script passes its own ignore path. A vendored data file would therefore fail the
pull-request check until someone "fixes" it by reformatting, which rewrites vendored bytes and
invalidates every digest taken over them. The change that adds the pack narrows both format globs in
`package.json` to exclude `packages/knowledge/packs` and `packages/knowledge/snapshots`, and a test
asserts a pack file's bytes match the checksum recorded at import.

## Identity and immutability

Identity is `source`, `source_version`, `describes_build`, `digest` (FR-024). On load the digest is
recomputed over `rules.json` and `effects.toml`, and over `aliases.toml` when the snapshot has one;
a mismatch refuses to load. A snapshot with no `aliases.toml` keeps exactly the digest it was
recorded with, so adding the file to the format re-recorded nothing: the digest of a snapshot that
has one is a different computation, not a new field. Adding `aliases.toml` to a directory recorded
without it changes the digest and is refused like any other edit. A test walks every committed
snapshot directory and fails if any file's digest differs from its recorded one — which is how
FR-025's "never modified" is asserted and not merely asked for.

## Promotion (FR-034)

`source change` → `new pack revision` → `new snapshot, unvalidated` → `validation recorded` →
`promoted`. Only a promoted snapshot is resolvable by build. `snapshot.toml` carries a
`promoted = true` that the loader honours, and a validation record that may not be empty when it is
set.

**Carry-forward** (research D4) is one kind of validation. Its record lists every build between the
source revision's build and `describes_build`, and for each: the notes consulted, where they were
read, the date, and the reading — _no field this pack carries changed_, or the fields that did. A
build with no entry in that list makes the snapshot unpromotable.

**Supersession (T746)** is how a promoted snapshot is corrected or extended when it may not be
edited (FR-025). The newer snapshot of the **same build** carries `supersedes`, in its `[snapshot]`
table: the digest of the one it replaces. The loader refuses, with `SnapshotError`, a `supersedes`
that is not a digest, that names no installed snapshot, that names one of another build or one that
is not promoted, that matches more than one installed snapshot of the build, or that sits in a
snapshot which is itself not promoted (an unpromoted snapshot never resolves, so it could not
replace a promoted one); a snapshot named by two others (the build would keep two current
snapshots); and a cycle, including a snapshot naming itself (every member would be superseded and
the build would read as `no-snapshot-for-build` while promoted snapshots exist). A chain is allowed:
each link is superseded by the next and the last is current. The superseded snapshot is not
demoted, edited or deleted: it stays promoted, digest-verified on every load and found by its full
identity, so an analysis published under it is reproduced from it (SC-005, FR-043). It names the
build by `describes_build` as it always did, which is why `supersedes` names a digest and the
loader checks the build matches.

## Resolution by build (FR-027)

```python
def snapshot_for(build: int) -> Snapshot | KnowledgeGap
```

Exact match on `describes_build` among the promoted snapshots that no other snapshot supersedes, or
a gap with cause `no-snapshot-for-build`. There is no nearest, no latest, no fallback parameter. A
superseded snapshot is skipped here and nowhere else: it is still the snapshot its own identity
names. Two such current snapshots for one build raise `SnapshotError` rather than resolve to either;
that is what `supersedes` exists to prevent, and `verify_installed_snapshots` checks it once for
every build, ahead of any request.

## The query surface

```python
def cost(entity, *, civilisation, context=None) -> Answer[Cost] | KnowledgeGap
def production_time(entity, *, civilisation, context=None) -> Answer[Duration] | KnowledgeGap
def age_requirement(entity, *, civilisation) -> Answer[Age] | KnowledgeGap
def prerequisites(entity, *, civilisation) -> Answer[Sequence[EntityRef]] | KnowledgeGap
def produced_at(entity, *, civilisation) -> Answer[EntityRef] | KnowledgeGap
def available_to(entity, *, civilisation) -> Answer[bool] | KnowledgeGap
def name(entity) -> Answer[str] | KnowledgeGap
```

- `prerequisites` answers a gap with cause `field-absent` for every entity the snapshot names: the
  one lawful source carries display links, not the game's prerequisites (research.md D3, T652y).
  The signature stays, so a future source changes no caller.
- `civilisation` is **keyword-only and required** on every rule query. There is no way to ask for a
  generic value, so there is no way to be handed one (FR-023).
- `context` is the match state a conditional effect needs: the age, the technologies researched,
  the civilisations on the player's team, the player's own included, and how many of a set of
  entities the player controls. A query whose matching effects are unconditional ignores it. A
  query that reaches a conditional effect without the input that decides it **raises**, as omitting
  `civilisation` does: the caller asked for a value only the match can fix, and neither the baseline
  nor a guessed age is an answer.
- **The controlled count is keyed by the entities counted** (FR-022e). `Context.controlled` maps a
  set of entity references, each a kind and an identifier, to the number of them the player
  controls, summed over the set: "Town Center or Castle controlled" is one entry whose key is both
  buildings. A `controlled` effect reads the entry whose key equals its own `condition_entities`
  exactly, in any order. A count stated for another set never answers it, so two such effects on
  different sets are never fed one number; an effect whose set has no entry **raises**, and the
  message names the entities it needs. A count that is not a non-negative whole number is a
  `ValueError`, a `bool` included. Which entities count as controlled at the moment of the query is
  the caller's decision, never the knowledge base's. The effect takes the operand of the highest key
  not above the count: above the highest key that key's operand (a stated maximum), between two keys
  the lower one, below the lowest key nothing, and the effect does not apply.
- `Answer` carries the value, the snapshot identity, the source the stored value came from, and the
  effects applied, in order (US2 scenario 1).
- The union has **no third branch**. No function in the package returns a bare value, accepts a
  default, or catches a gap and continues. SC-008's "by construction" is this signature, and a test
  asserts by introspection that every public query returns the union.

## Civilisation qualification (research D5)

In order, for a rule query qualified by civilisation _c_:

1. _c_ not in `civilisations_modelled` → gap, cause `civilisation-not-modelled`. Every cost and time
   for _c_ refuses, because which fields a bonus touches is exactly what is not known. The same
   holds for any civilisation in `context.team`: a teammate's team bonus touches _c_, so an
   unmodelled teammate refuses every cost and time for _c_, and the gap names the teammate.
2. An effect for _c_ touches this entity and field and is `modelled = no` → gap, cause
   `effect-not-modelled`.
3. Otherwise apply each matching effect whose condition holds in `context`, in file order, and
   return the adjusted value with the effects listed. A team effect matches every civilisation on
   the owner's team, not the owner alone.

A conditional effect that is modelled is complete knowledge, so the coverage pass does not report it
as a gap. The pass supplies no age, research or controlled-count state, so it treats a query that
raises for want of one as modelled. **T652v**: the pass does supply each participant's real team,
read from the recording's own header — every ally's civilisation, the participant's own included,
never a guess — so a team-conditioned effect is applied for real rather than merely treated as
modelled, and an unmodelled ally is what gaps every cost and time query for that ally's teammates
(step 1, above), not only the query naming the unmodelled civilisation directly.

`name` is not civilisation-qualified and an unresolvable identifier degrades to the bare identifier
at the presentation boundary, as 003 FR-043a already requires — it never gaps an analysis.

An identifier the pack does not name but the snapshot aliases (below) is resolved first, so
`name` answers the target's name and every step above reads the target's record and selects the
target's effects. A gap raised after that still names the identifier the caller asked for.

## Entity resolution

A unit identifier may live in the source's unit table or its upgrade table; four technology
identifiers in the committed fixture do. The normaliser merges both into one keyed space and records
which table each came from. A test asserts every entity referenced by every committed reference
recording resolves.

**An identifier the pack does not name resolves through an alias (FR-022d).** A snapshot may carry
`aliases.toml`, one `[[alias]]` table per identifier, with six keys, all required and all
non-blank strings: `kind` (`unit`, `building` or `technology`), `id` (the identifier a recording
carries), `target` (an identifier of the same kind that `rules.json` names), `source_name` (the
referenced source's name for `id`, verbatim), `source` (which source, and where in it) and
`read_on` (the date it was read). The file holds nothing but `[[alias]]` tables, and a file with
none is valid.

The loader refuses, with `SnapshotError`, every other shape rather than accepting it silently: a
`target` that `rules.json` does not name under the alias's kind (so an alias never chains through
another); an `id` that `rules.json` already names (so the pack's own entity is never shadowed and a
named identifier is never reported as aliased); a second alias for one `kind` and `id`; a missing,
blank or non-string key; a key outside the six; a `kind` outside the three; and any table but
`alias`.

Resolution reads `rules.json` first and the aliases only for an identifier it does not name. Every
rule query and `name` then answer from the target's record, and **`Answer.alias`** is the alias
that was followed (its `kind`, `id`, `target`, `source_name`, `source` and `read_on`), or `None`
for an identifier `rules.json` names. An identifier with no alias stays `entity-absent`, as before.
An alias is transcribed from a source `docs/data-sources.md` §6 references, never inferred
(FR-022d).

## Gaps

- **Severity is computed** (research D7): the gap's `prevents` is the set of register data whose
  `requires_knowledge` names its field; non-empty means `blocking`.
- **The coverage pass** (`coverage.py`) takes a canonical stream, collects every entity and every
  participant civilisation, and asks for every field any register datum requires. Its output is the
  gap list the document publishes. **SC-007a** is this pass over each committed recording returning
  no blocking gap outside **FR-022b**'s enumerated list — the closed set of blockers that the one
  lawful vendored source cannot close, each held by a strict expectation so that closing one turns
  the suite red rather than passing silently. A blocker not on that list is a transcription defect
  and is fixed, never enumerated.
- **SC-007**: a test deletes one field from an in-memory copy of a snapshot, runs the pass, and
  asserts that exactly the dependent data are withheld, a gap names the entity, field, build and
  civilisation, and every other datum is unchanged.
- **Aggregate** (FR-039): gaps are written to `analysis_knowledge_gaps`, and the table **is** the
  aggregate. The report is a grouped count by build, cause and severity over a window, exposed as
  one repository function and printed by one check script. The analyzer has no run, no counters and
  no summary to attach a line to — the ingester's quarantine counter is a column on a per-run table
  the analyzer has no equivalent of — and none is invented for this.

## Licence gate (FR-031, FR-033)

Each pack's `packs/<name>/LICENCE.md` (there are several, one per pinned revision) carries the five
fields `scripts/checks/asset_packs.py` enforces, named exactly as it matches them: `Source`, `Licence`, `Permitted usage`, `Ruling`, `Checked`. The
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

Sources ruled _read and transcribe only_ appear in no pack. A value transcribed from one is an
effect or a disagreement entry carrying the sentence read, where, by whom and when.

## Source assessments (FR-029, FR-030)

Land in `docs/data-sources.md` as a new section, one subsection per source assessed in research D3,
with the date. That section is the living home; research D3 is its record of origin.
