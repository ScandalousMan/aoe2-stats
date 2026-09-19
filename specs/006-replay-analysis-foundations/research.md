# Phase 0 — Research: Replay-analysis foundations

**Date**: 2026-09-19 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Three threads ran in parallel — a time-boxed spike on the starting state, a survey of external
knowledge sources and their licences, and an audit of this repository — and every claim a decision
below rests on was re-run by hand before being written here. Where a thread overstated, the
correction is recorded beside the finding rather than silently applied.

This document owns the measurements it states. Anything about the outside world that must stay true
after this feature merges is moved to `docs/data-sources.md` by a named task, and this file then
becomes its historical record, not its home.

## What the spec claimed, and what the measurements say

| Spec claim | Verdict | Evidence |
| --- | --- | --- |
| The starting state is not exposed by any parser that works on the current build | **True of the parsers, false of the file.** | The pinned wheel returns the initial section as three scalars and stops. The decompressed header nevertheless contains each player's attribute array at an anchor that can be found without a grammar — see D1. |
| The secondary engine fails on this build at the initial-state section | **Not reproducible from this repository.** | `mgz` is in no lockfile and behind no adapter. It is installed ephemerally by the nightly canary (`.github/workflows/nightly.yml`, `scripts/checks/parser_canary.py`) and nowhere else. `docs/risks.md` already carries "the engine interface allows selecting mgz by configuration" as an unchecked item. |
| `SKILL.md` and ADR-0001 name a path that was never created (FR-046) | **Confirmed.** | Both name a parser application directory; the applications that exist are `apps/analyzer`, `apps/api`, `apps/ingester`, `apps/web`. |
| `SKILL.md` wrongly says placement carries no player identifier (FR-047) | **Confirmed, and a test already says so.** | `packages/replay-engine/tests/test_aoe2rec.py` pins the opposite across every placement in the fixture and names both documents in its module docstring. |
| The dependency record may be empty (FR-044) | **Confirmed: it is always empty.** | `apps/analyzer/src/aoe2stats_analyzer/extract.py` publishes `"deps": {}` as a literal. The `engine_deps` column exists and nothing fills it. |
| The repository has no versioned reference-data pattern | **Confirmed, and 002's own register was never written.** | The only structured game knowledge is three identifier-to-name tables under `apps/api/src/aoe2stats_api/`. `docs/reference-data.md`, 002's deliverable, does not exist; 002's licence rulings survive only in its frozen tasks and in a module docstring. |
| No network in tests needs building (SC-006) | **Already exists.** | `tests/conftest.py` blocks every non-loopback socket under `PYTEST_DISABLE_NETWORK=1`, workspace-wide. This feature asserts against it. |

**One collision the spec does not mention.** `match_analyses` is one row per match, the published
document lives at one object key per match, and a recompute overwrites it. FR-042 forbids destroying
an existing analysis. D9 resolves it without touching 003's primary key.

## D1 — The starting state: present in the bytes, reachable in two tiers of very different cost

**Decision.** The starting state is re-classified from *unreadable* to **decodable by a
repository-local decoder, not yet built**. This feature records that in the register, reserves the
vocabulary for it (FR-020), and corrects the documents that say otherwise. The decoder itself is the
first work item of feature 007, where its only consumer lives.

**What was measured**, against the committed fixture, with nothing installed:

- The header inflates to a little over four megabytes. The initial section's three scalars occur at
  exactly one offset, and the first player block's name string follows within a few dozen bytes.
- Each human participant's name string recurs once deeper in the header, and a short fixed distance
  after it sits a float array whose first four values are the standard food, wood, stone and gold
  start in the engine's own resource order. The run occurs exactly twice in the fixture — once per
  human participant — and nowhere else. The two arrays are identical except at one index, which is
  consistent with a civilisation or handicap multiplier.
- Block arithmetic fits one per-tile grid of a fixed record width per player, plus a small attribute
  region; the Gaia block carries roughly eight hundred kilobytes more, which is its object table.
- The lobby presets — starting-resources preset, starting age, map size, resolved map — are already
  named fields in the pinned wheel's output and are not credited anywhere today.

**Tier A — per-player starting attributes.** Anchored on a self-verifying string, fixed layout
after the anchor, the same empirical sweep that produced the placement decoder. Two to three tasks,
golden-tested against committed fixtures.

**Tier B — starting objects and the map's resource geometry.** The Gaia object table is
variable-length and variant-typed across roughly ten record kinds, and one community maintainer
measured a single record kind growing by twenty-four bytes between two save versions. This is a
grammar, not an offset, and it carries a standing per-patch cost. Eight to twelve tasks. It should
be ported from an existing open grammar, not derived from zero.

**The three routes.**

| Route | Verdict | Why |
| --- | --- | --- |
| 1. A fork of the secondary engine | **Reference, not dependency.** | The one fork that parses this save version end to end (`CliveUnger/aoc-mgz`, MIT) has a single maintainer, one star, no release, and has been silent since 2026-08-01. None of the open upstream pull requests ADR-0001 names fixes the initial section — the ADR's fork fallback would not have delivered it. Its object grammar is the map for Tier B. |
| 2. The fast alternative | **Dead for objects.** | `mgz-fast` gates on save versions below this build's and skips the attribute block it would need. The crate behind the pinned wheel has no object structure at any version, with an issue open on exactly that since March. |
| 3. A repository-local decoder | **Chosen.** | Keeps principle V's swappability, adds no runtime dependency, and Tier A needs no grammar at all. |

**Alternatives rejected.** Taking the fork as a runtime dependency trades a six-month outage risk
for a smaller one carried by one person. Building Tier A inside this feature was rejected because a
decoder with no consumer can only be golden-tested against the value everyone already expects, which
proves the anchor and not the semantics; 007 consumes it on day one.

**What this does to feature 007's scope.** The income side is in scope: its initial condition is
Tier A plus the knowledge base. Start positions and the small starting object set are in scope at
medium confidence. The map's resource geometry, and with it exploration, vision and map control,
stay deferred — but as *decodable at a stated cost*, which is a different register entry from
*not determinable*, and the register is the one place that distinction has to be right.

**Unsettled, and what settles it.** Whether the fork and the fast parser actually walk *this*
fixture's object table was not run, because it needs a throwaway environment. It is one short
script, and its assertion must be on object count and coordinate range, since the fast parser's scan
returns an empty list rather than raising. It belongs to 007's Phase 0, not here.

## D2 — The second reference recording is committed, as served

**Decision.** Commit it, under the same rules as the first: the zip the source served, byte for
byte, with its checksum and provenance in `tests/fixtures/replays/README.md`.

**Rationale.** `docs/data-sources.md` §2 states its own bar for closing the open question: more than
one recording, across at minimum ranked 1v1 and ranked team games. The two measured recordings are
exactly that bar. But the second is in neither checkout — it was supplied in session and never
persisted — so FR-045 would move a section from *not known* to *settled* on a measurement nobody can
re-run, which is the precise failure the filing rule in `CLAUDE.md` exists to prevent. A fact in
`docs/` is trustworthy only because a test asserts it, and a test cannot assert a file that is not
there.

The two conditions the spec asked to be settled:

- **Repackaging.** Not needed if the served zip is re-fetched while the source still holds it, and
  the source's window is finite. If only an extracted recording can be recovered, it is committed
  repackaged and the README says in so many words that the bytes and the checksum are this
  repository's and not the source's. Verbatim is strongly preferred; a documented repackaging is
  still better than an unrepeatable measurement.
- **Principle IX.** Not a new obstacle. The first fixture already names two real players and is
  retained on the already-public basis. The second adds two more on the same basis, recorded in the
  processing register in the same change.

**If the file cannot be recovered at all**, FR-045 is satisfied in its narrower honest form: §2
records two measurements, names which one is reproducible from a committed fixture, and keeps the
question marked as corroborated-but-not-re-runnable rather than settled. The task is written to
take either branch.

**Alternative rejected.** Leaving it out and citing the session. A citation to a conversation is
not evidence anyone can check.

## D3 — Knowledge sources: one vendorable primary, and no lawful independent second dataset

**Decision.** Vendor `SiegeEngineers/aoe2techtree` (MIT) as the primary pack, pinned by commit.
Cross-validate by **hand transcription from the publisher's own per-build patch notes**. Do not
vendor a second dataset in this feature.

| Source | Carries | Licence | Ruling |
| --- | --- | --- | --- |
| aoe2techtree — data file, per-civilisation trees, English strings | Costs, training and research times, age, producing building, upgrade edges and availability per civilisation; bonuses **as prose only** | MIT | **Copy in** |
| halfon | Costs and combat attributes for a wider object set; **no times, no ages, no civilisation dimension** | MIT | Deferred — see below |
| aoc-reference-data | Names only | **None** | Read and transcribe only (002's ruling, re-verified) |
| aoe2companion's data module | aoe2techtree verbatim in a wrapper | **None** | Rejected |
| The game's own data file, via genieutils | Everything, per civilisation, per build | Publisher's | **Rejected** — the usage rules' first prohibition bars the extraction, it needs a game install, and it engages the EU database right |
| Fandom wiki | Prose tables | CC BY-SA 3.0; terms forbid automated access | One human, one number, with provenance |
| Publisher patch notes | Exact per-build deltas | All rights reserved | Read and transcribe only — **this is the FR-030 validation source** |
| aoe2de_patcher build list | Every build number with its date | GPL-2.0 | Reference only; the list is transcribed, the file is not copied |
| aoestats | Match data | — | Rejected — not rules |

**halfon is not an independent source.** Both it and aoe2techtree are generated by the same library
reading the same game data file. Their unit costs agree everywhere except in how a zero is
serialised; that agreement measures serialisation and cannot detect a misreading of the underlying
file. halfon also carries no times at all. Pairing the two would satisfy the letter of FR-028 and
FR-030 and none of their purpose, so it is not done. halfon stays a documented fallback for an
entity aoe2techtree omits, to be vendored by the task that first needs it.

**How a pack arrives.** A person checks out the source at the pinned commit; a network-free import
script reads that local checkout and writes the pack. This is `scripts/ops/sync_map_thumbnails.py`'s
discipline, and it satisfies FR-032 by construction: nothing in the build, the tests or the running
system fetches anything, so no provider is needed because no call is made.

**002's unwritten register.** The source assessments FR-029 requires land in `docs/data-sources.md`
as a new section, which also finally gives 002's licence rulings a living home.

## D4 — No source can answer "what did this cost on build N"; a snapshot is carried forward with evidence

**Decision.** A snapshot names the build it **describes**, separately from the source revision it
was **imported from**. Where the source has no revision for a build, a snapshot for that build may
be created by *carry-forward*: the nearest earlier import, plus a recorded, dated, human reading of
the publisher's notes for every intervening build stating that none changed a field the pack
carries. A carry-forward is a validation (FR-030, FR-034) and produces a new snapshot identity. It is
never inferred at query time, which is what FR-027 forbids.

**Why this is forced.** Neither dataset carries a build or version key, a tag or a release. The
build lives in commit-message prose, which yields a recoverable but derived build-to-commit map
covering roughly a quarter of the real builds. The committed fixture's build is **newer than the
newest revision the source has implemented**, with two further builds unimplemented in between.
Without carry-forward, the only committed reference recording cannot be analysed at all and FR-022a
is unreachable.

**Its honest limit.** The fixture's own build has no publisher page; its notes are read from a
secondary listing and recorded as such with the date. The attestation's weakness is stated in the
snapshot's validation record, not hidden.

**Alternative rejected.** Mapping a recording to the nearest snapshot at query time. It is the
silent substitution FR-027 and FR-038 both prohibit, moved from a value to a version.

## D5 — Civilisation bonuses are hand-modelled, civilisation by civilisation, and an unmodelled civilisation is a gap

**Decision.** Bonuses that modify a cost or a time are modelled as structured effects, transcribed
by hand from the English strings that ship in the MIT pack, each carrying the verbatim sentence it
was transcribed from, the transcriber's reading of its scope, and its validation. The first snapshot
models every civilisation that appears in a committed reference recording. For any other
civilisation, a civilisation-qualified cost or time query records a gap and returns nothing.

**Why this is forced, not chosen.** No lawful, vendorable source carries civilisation-specific
values: aoe2techtree exports the baseline civilisation only, and its per-civilisation metadata is
empty. In the one committed recording **both players trained units their civilisation discounts** —
a Byzantine pikeman, Korean archers and crossbowmen. Returning the baseline is exactly what FR-023
forbids. FR-022a requires zero blocking gaps on that recording, FR-038 forbids a default, and FR-031
permits human transcription with provenance. Read together they leave one path, and it is the one
the fourth clarification already chose: cover what the reference recordings need, and let everything
else surface as a gap.

**The conservative rule, stated once.** For a civilisation whose bonus set is not modelled, the
knowledge base cannot know *which* fields a bonus touches, so it refuses **every**
civilisation-qualified cost and time for that civilisation. Coverage therefore grows by whole
civilisations, and the aggregate gap report (FR-039) is the backlog.

**What stays out of the effect model.** Team bonuses, age-gated bonuses whose gate the recording
cannot place, and anything conditional on state are recorded as *modelled: no* with the reason; they
keep their fields gapped. A bonus is never half-applied.

## D6 — The register is TOML inside the package that enforces it

**Decision.** `packages/core/src/aoe2stats_core/truth/register.toml` is the single source. The
readable view is generated beside it, and a test fails when regenerating it would change a byte.

**Rationale.** TOML parses with the standard library, so `packages/core` keeps its zero-dependency
rule. The precedent is `scripts/checks/asset_packs.py`, which already holds a per-pack source of
truth and fails when `docs/asset-packs.md` drifts. The view is filed with the package and not under
`docs/`, because its subject is this product's own data, and the filing rule sends a fact about a
package to live beside what recomputes it. Every measurement an entry relies on is a reference into
`docs/data-sources.md`, never a restatement (SC-013).

**Alternatives rejected.** YAML adds a dependency to the one package that has none. A Python module
as the source makes the register code, which SC-012 rules out by asking that a reader need none.

## D7 — Gap severity is computed from the register, never assigned by hand

**Decision.** A gap is **blocking** when at least one register entry that is not itself marked
blocked or non-determinable declares, in its required knowledge, the field the gap names. Otherwise
it is **informational**.

**Why this needed deciding.** FR-037 defines blocking as "a publishable value depends on it". Nothing
this feature publishes depends on a cost — reconstruction is 007. Read naively, every gap in 006
would be informational and SC-007a would pass vacuously. But FR-005 already requires the register to
cover what 007 intends to publish, and FR-002 requires each entry to state the knowledge it needs. So
the dependency graph exists as data, and severity falls out of it mechanically. This also makes
SC-007a a real test on day one: the coverage pass asks, for every entity and civilisation in the
canonical stream, for every field some register entry requires.

## D8 — The tiered document is additive: a provenance sidecar keyed by datum

**Decision.** The published document moves to the next schema version by **adding** blocks —
`identity`, `provenance`, `inferred`, `knowledge_gaps` — and leaves every existing field at its
existing path. `provenance` maps each register datum to its tier and method; the validator asserts
that every leaf value in the document resolves to exactly one datum with an entry.

**Rationale.** `apps/web/src/features/analysis/api.ts` validates the document's shape strictly, and
this feature has no user-interface scope. Wrapping each value in an object would break the reader for
no gain. A sidecar inside the same document is still "tier as data, not as documentation" (FR-007),
and completeness is enforced, which is what makes it a property of the datum and not a convention.
Inferred and predicted values live only under `inferred` and are structurally unable to occupy an
observed path, which is FR-011 by construction, with the validator as the second lock.

**Alternative rejected.** A value-wrapper shape `{value, tier, method}` at every leaf. Cleaner in
isolation, and a breaking change to a consumer this feature does not own.

## D9 — Analysis identity addresses the object; 003's row points at the current one

**Decision.** The identity is the tuple FR-040 lists, with a digest over its canonical
serialisation. The published object's key carries that digest. `match_analyses` keeps `game_id` as
its primary key — that key is 003's double-click dedupe and is not this feature's to change — and its
existing `result_key` column names the current document. Earlier documents stay in the object store
under their own keys and remain resolvable by identity. No migration.

Reconstruction and analytics versions are part of the identity from the start and carry an explicit
*not applicable* marker until 007 ships, so the tuple's shape never changes (FR-040, and the reason
US6 is specified now).

**The dependency record (FR-044)** is populated from installed distribution metadata for the engine
and its declared requirements, inside the adapter, and an empty record fails validation.

**Byte identity (SC-004).** The document's one wall-clock field is excluded from the identity and
from the comparison by moving under a clearly separated envelope; everything inside the compared
body is a pure function of the identity. Serialisation is canonical: sorted keys where order carries
no meaning, stream order where it does, fixed float formatting.

## D10 — Canonical events sit on the existing seam, as a second protocol beside the first

**Decision.** The vocabulary is pure types in `packages/core/src/aoe2stats_core/replay/events.py`.
The adapter in `packages/replay-engine` gains a second entry point that yields canonical events from
the same single pass the existing extractor makes. The existing `MatchTimeline` extractor is then
re-expressed as a fold over that stream, and the committed golden timeline must come back
byte-identical — the only available proof that the new stream loses nothing the old path read.

**Memory (FR-021).** The stream is a generator over the wheel's operations; the adapter never
materialises the operation list, and the existing memory-ceiling test is extended to the new entry
point. Whether the stream is *persisted* is settled here as **no**: it is recomputable from the
retained recording by a versioned tool, which is principle IV's definition of disposable, and 007
consumes it in-process.

**Undecoded commands (FR-019)** become an event of kind *undecoded* carrying the engine's own
operation kind as an opaque label and the payload length — never the payload's shape, which would be
an engine-specific field (FR-017).

**The group-silence observable (FR-013)** is computed here, as the one inferred datum this feature
ships. Its confidence basis is the ratio of commands naming the group before the silence to the
length of the silence, banded into the closed levels; the banding thresholds live in the register
entry's method, and its non-claim is a required field of the datum, not a comment.

## Principle V, read exactly

The constitution says both engines sit "behind one interface". They do not: one engine has an
adapter, the other is a nightly canary. That gap predates this feature and is already an open item in
`docs/risks.md`. This feature does not close it and does not widen it — the canonical vocabulary is
what a second adapter would target, which makes closing it cheaper. FR-046's correction to ADR-0001
states what exists and leaves the open item where it is.

## What remains unknown

- Whether either external parser walks this fixture's object table (D1) — 007's Phase 0.
- The meaning of most indices in the per-player attribute array beyond the first four — 007.
- Whether the second recording can still be re-fetched as served (D2) — only the person who supplied
  it knows, and the source's window is closing.
- Whether any current-patch recording from an unranked or custom game carries the post-game block.
  §2 called that "ideal", not required; FR-045 records it as still unmeasured.
- The true volume of civilisation bonuses that resist the effect model (D5). The two fixture
  civilisations are tractable; the rest are sized by the gap report, not guessed here.
