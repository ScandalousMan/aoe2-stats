# Implementation Plan: Replay-analysis foundations

**Branch**: `006-replay-analysis-engine` | **Date**: 2026-09-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-replay-analysis-foundations/spec.md`

## Summary

Build, as working and tested code, the four things a reconstruction has to stand on: a
machine-readable register of what can be known, a truth tier and provenance carried by every
published value, an engine-independent canonical event stream, and a versioned, offline,
immutable knowledge base that refuses to answer what it does not know. The code stops where
reconstruction begins; that is feature 007.

**Phase 0 confirmed the spec's corrections and overturned its central premise.** The starting state
is unreadable by every working *parser* and perfectly present in the *file*: each player's starting
attributes sit in the inflated header at an anchor that needs no grammar, and the map's object table
is there too, behind one. The datum moves from *unreadable* to *decodable, not yet built*, which is
a different register entry and changes what feature 007 may promise. The decoder is 007's first
task, not this feature's; here it gets a register entry, a reserved place in the vocabulary, and
corrected documents.

Three findings change the plan rather than only adding to it.

**No lawful source carries civilisation-specific values, and the one committed recording needs
them.** The vendorable dataset exports the baseline civilisation only. Both players in the reference
fixture trained units their civilisation discounts. FR-023 forbids the baseline, FR-038 forbids a
default, FR-022a demands zero blocking gaps on that recording — so bonuses are hand-modelled as
structured effects, civilisation by civilisation, from the prose that ships in the MIT pack, and a
civilisation not yet modelled answers nothing at all.

**No source is versioned by game build, and the fixture's build is newer than anything the source
has implemented.** A snapshot therefore names the build it describes separately from the revision it
was imported from, and may be *carried forward* to a later build only by a recorded human reading of
the publisher's notes for every build in between. That is a validation producing a new identity,
never a lookup falling back at query time.

**Today's storage destroys what FR-042 protects.** One row and one object per match, overwritten on
recompute. The published object's key gains the identity digest; 003's row keeps its primary key and
points at the current document. That change needs no migration; the gap table in phase 5 is the
feature's only one.

The two datasets that look like a primary and a cross-check are one pipeline run twice, so the
second source is the publisher's patch notes, transcribed by hand. And the second reference
recording is committed as served — if it can still be recovered; FR-045 is written to be honest in
either case.

Full reasoning and evidence: [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.13. No TypeScript source change: the web reader already accepts the
next document version structurally, and gains one test that pins it.

**Primary Dependencies**: None added at runtime. `packages/core` stays dependency-free — the
register is TOML, read with the standard library. The new `packages/knowledge` depends on
`aoe2stats-core` only. `aoe2rec-py` stays pinned where it is, inside `packages/replay-engine`.

**Storage**: Object store only, through `packages/storage`. The published analysis document gains
an identity-addressed key. One additive table, `analysis_knowledge_gaps`, for the aggregate gap
report — an expand-only migration with nothing to contract. Knowledge packs and the register are
files in the repository, shipped inside their packages.

**Testing**: `uv run pytest` across the workspace under `PYTEST_DISABLE_NETWORK=1`, which
`tests/conftest.py` already enforces at the socket. Golden tests against committed fixtures, written
by hand in the existing style — there is no snapshot plugin and none is added. `uv run mypy`, `uv
run ruff`. The existing licence-record check is extended to the knowledge pack's root; no new check is written.

**Target Platform**: Vercel Hobby `cdg1` (phase 1), OVH VPS (phase 2). Everything here is a library
imported by `apps/analyzer`; nothing is platform-aware.

**Project Type**: Python library packages inside the existing uv workspace, consumed by one existing
application.

**Performance Goals**: The canonical stream is produced in the same single pass the extractor
already makes, and the existing fixture-parse time must not regress by more than a small constant
factor. A knowledge query is an in-memory lookup after a one-time load of a snapshot measured in
single-digit megabytes.

**Constraints**: The memory ceiling in `specs/003-player-search-match-analysis/contracts/analysis.md`
binds the new entry point exactly as it binds the old one — the operation stream is never
materialised. No scheduled job, no request-path work, nothing that draws on the capture budget
(FR-049). No network at build, test or run time. No default, average or neighbouring value, ever.

**Scale/Scope**: 6 user stories, 52 functional requirements, 14 success criteria. One new package,
two existing packages extended, one application touched at two functions. One vendored pack of three
files, two hand-modelled civilisations in the first snapshot (four if the second fixture lands).
Three documents corrected. Five phases, each independently green.

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design — the verdicts below are
the post-design ones. All twelve principles were walked from
`.specify/memory/constitution.md` itself, not from a previous feature's table._

| #        | Principle                                     | Verdict                                       | How this feature satisfies it |
| -------- | --------------------------------------------- | --------------------------------------------- | ----------------------------- |
| **I**    | Capture Outranks Analysis                     | **PASS**                                      | Nothing here touches the ingester, the enqueue, the budget or the replay fetch. FR-049 forbids a scheduled job and forbids drawing on the capture budget, and the design has neither: every new code path is a library call inside an analysis a person asked for. One thing to hold — D2 has a closing window, and recovering the second recording is capture work, so it outranks every other task in this plan. |
| **II**   | Python Backend                                | **PASS**                                      | All logic is Python. The web reader gains no rule: the tier, the gaps and the identity are data it may later display and never computes. |
| **III**  | All External Data Goes Through a DataProvider | **PASS** — by making no call                  | No outbound connection is added anywhere. The knowledge pack is imported by a network-free script from a checkout a person made, the discipline `scripts/ops/sync_map_thumbnails.py` already follows, so there is no call for a provider to wrap. FR-032's "through `packages/providers`" binds the day someone automates a refresh; this plan does not, and says so. The rules data is re-obtainable at any time, so no verbatim response is owed. |
| **IV**   | Raw Is Sacred, Derived Is Disposable          | **PASS** — and one gap in it closes           | The recording is read and never written. Every derived artifact records what produced it: that is FR-040, and FR-044 repairs the one place the record is an empty literal today. FR-042's "never destroy" is stricter than this principle's "disposable" and is honoured by addressing, not by forbidding recomputation. If the second fixture must be repackaged (D2), the README says the bytes are ours — a fixture is not a retained capture, but the principle's honesty about checksums applies. |
| **V**    | Parsing Runs in an Isolated, Pluggable Engine | **PASS** — this feature is the principle's subject | The canonical vocabulary is the interface the principle asks for, stated in types with no engine-shaped field (FR-017). The pinned wheel stays imported in exactly one package. The principle's "both behind one interface" is unmet today and was before this feature — one engine has an adapter, the other is a canary — and it stays an open item in `docs/risks.md`; this feature makes closing it cheaper and does not claim to close it. |
| **VI**   | Tokens First                                  | **N/A**                                       | No component, no style. |
| **VII**  | Visual Tests Are Mandatory                    | **N/A**                                       | No component is created or modified. The published document changes additively and the reader's existing tests cover that it still parses. |
| **VIII** | No Secrets in the Clear                       | **PASS**                                      | No secret, no new environment variable. |
| **IX**   | GDPR by Design                                | **PASS, with one register entry owed**        | No new personal data is processed by the code. The second fixture (D2) names two more real players in a public match, retained on the already-public basis exactly as the first is; the processing register gains that entry in the same change. The group-silence observable is a property of a match, keyed to a participant slot the document already carries. All regions stay EU. |
| **X**    | Intellectual Property                         | **PASS, with one mandatory gate**             | The pack is MIT and lands with the five-field licence record; `scripts/checks/asset_packs.py` and its workflow path filter are extended to `packages/knowledge/packs/` in the same change, because the check is scoped by root and would otherwise neither see nor run on it. The game's own data file is rejected outright — the usage rules' first prohibition bars the extraction — and that rejection is recorded so it is not re-proposed. Non-commercial and the disclaimer are untouched. |
| **XI**   | Documentation Is in English                   | **PASS**                                      | Every artifact is English. The vendored strings file is the English locale only. |
| **XII**  | Portable by Construction                      | **PASS**                                      | Packs and the register are package data read through `importlib.resources`, not filesystem paths, so they load identically from a serverless bundle and a virtual environment. No local state is written. Objects go through `packages/storage`. |

**Post-design re-check**: one verdict gained an obligation. IX had none before Phase 0; D2 created
the processing-register entry. III moved from "PASS, via a provider" in the first draft to "PASS, by
making no call" once the map-thumbnail precedent was read — a provider wrapping a fetch nobody
automates would be code with no caller.

**One reading recorded rather than left implied.** FR-032 says a refresh "MUST go through
`packages/providers`". This plan satisfies it vacuously, by having no automated refresh. A future
change that scripts the download must add the provider at that moment, and the import script's
header says so, the same way the map-thumbnail script's does.

## Project Structure

### Documentation (this feature)

```text
specs/006-replay-analysis-foundations/
├── plan.md              # This file
├── research.md          # Phase 0 — D1..D10, the overturned premise, what remains unknown
├── data-model.md        # Phase 1 — tiers, provenance, events, snapshots, gaps, identity
├── quickstart.md        # Phase 1 — how to verify each phase
├── contracts/
│   ├── register.md            # The register's schema, its generated view, the publication gate
│   ├── canonical-events.md    # The vocabulary, the adapter's obligations, the golden stream
│   ├── knowledge-base.md      # Snapshot identity, the query surface, refusal, carry-forward
│   └── analysis-document.md   # The additive document version, identity, the validator
├── checklists/
└── tasks.md             # /speckit-tasks — NOT created here
```

### Source Code (repository root)

```text
packages/core/
└── src/aoe2stats_core/
    ├── truth/                         # NEW — pure types, no I/O, no dependency
    │   ├── tiers.py                   # the closed ordered tier set; weakest-input rule
    │   ├── confidence.py              # closed ordered levels + mandatory basis
    │   ├── provenance.py              # tier, method, inputs, versions for one value
    │   ├── identity.py                # the FR-040 tuple, canonical form, digest
    │   ├── register.py                # loader, entry type, dependency graph, view renderer
    │   ├── register.toml              # THE register — single source of truth
    │   ├── REGISTER.md                # generated view — never hand-edited
    │   └── validate.py                # the document validator: coverage, tier, confidence
    └── replay/
        ├── analysis.py                # existing protocol and timeline types — unchanged shape
        └── events.py                  # NEW — the canonical event vocabulary + stream protocol
packages/core/tests/                   # register drift, tier ordering, validator rejections

packages/replay-engine/
├── src/aoe2stats_replay_engine/
│   ├── aoe2rec.py                     # timeline re-expressed as a fold over the stream; deps record
│   ├── canonical.py                   # NEW — wheel operations -> canonical events, one pass
│   └── silence.py                     # NEW — the group-silence observable (inferred tier)
└── tests/                             # golden stream; golden timeline must stay byte-identical

packages/knowledge/                    # NEW PACKAGE — depends on aoe2stats-core only
├── pyproject.toml
├── src/aoe2stats_knowledge/
│   ├── snapshot.py                    # identity, immutable load, digest verification
│   ├── query.py                       # the query surface; answers carry their snapshot
│   ├── effects.py                     # structured civilisation effects and their application
│   ├── gaps.py                        # gap record; severity computed from the register
│   ├── coverage.py                    # the coverage pass over a canonical stream
│   └── sources.py                     # source disagreement records
├── packs/
│   └── aoe2techtree/                  # vendored at a pinned commit
│       ├── LICENCE.md                 # the five-field record the asset-pack check enforces
│       ├── data.json
│       ├── trees/
│       └── strings.en.json
├── snapshots/                         # one directory per snapshot identity — append-only
└── tests/

apps/analyzer/
└── src/aoe2stats_analyzer/
    ├── extract.py                     # additive document version; identity; provenance; gaps
    └── run.py                         # identity-addressed result key; gap rows
apps/analyzer/tests/

apps/web/
└── src/features/analysis/             # a test pinning that the next version parses; no code, no UI

packages/storage/
└── src/aoe2stats_storage/models.py    # + analysis_knowledge_gaps

infra/migrations/versions/             # one expand-only revision

scripts/
├── ops/
│   └── import_knowledge_pack.py       # NEW — network-free; reads a local checkout
└── checks/
    └── asset_packs.py                 # root list extended to packages/knowledge/packs

tests/fixtures/replays/
├── README.md                          # + the second recording's provenance
└── AgeIIDE_Replay_*.zip               # + the ranked team game, as served (D2)

docs/
├── data-sources.md                    # §2 open question closed (FR-045); + knowledge sources
├── adr/0001-replay-parser.md          # path and "both behind one Protocol" corrected (FR-046)
├── privacy/processing-register.md     # + the second fixture's entry
└── risks.md                           # R3 gains the starting-state finding

.claude/skills/replay-parsing/SKILL.md # path (FR-046), placement player id (FR-047), initial state
.github/workflows/pr.yml               # asset-packs path filter extended
pyproject.toml                         # workspace member; testpaths; mypy
package.json                           # format globs exclude vendored packs and snapshots
```

**Structure Decision**: One new package, because the knowledge base has a different lifetime and a
different licence surface from everything else — it carries vendored third-party data and grows by
hand transcription — and mixing that into `packages/core` would end core's zero-dependency,
zero-data rule. Everything that is pure type goes into `packages/core`, where the existing replay
protocol already lives and where the API can import it without pulling a parser. The register lives
in `packages/core` beside the validator that enforces it, which is what the second clarification
asked for. The audit proposed putting all six deliverables in the new package; that was not
followed, because it would make the API depend on a data package to read a tier.

## Phases

Five, in this order. Each is independently green and separately mergeable. `/speckit-implement` is
run one phase at a time, naming the task range and the stop condition.

| # | Phase                              | Stories   | Why here |
| - | ---------------------------------- | --------- | -------- |
| 1 | Evidence and corrections           | US1       | The second fixture has a closing window (D2), so it goes first and outranks everything. The three document corrections are cheap, true today, and stop the next reader being misled while the rest is built. |
| 2 | Truth types and the register       | US1, US3  | Everything else imports these. The register must exist before anything can be checked against it, and severity (D7) is computed from it. |
| 3 | Canonical events                   | US4       | Needs the tier type. Proven by the golden timeline coming back byte-identical through the new path — a proof available only before anything else changes that path. |
| 4 | The knowledge base and its gaps    | US2, US5  | Needs the register for severity and the canonical stream for the coverage pass. Carries the vendored pack, the two hand-modelled civilisations and the carry-forward to the fixture's build. |
| 5 | Identity and the published document| US3, US6  | Last, because it is the only phase that changes what production publishes, and it assembles all four foundations into one validated document. Carries the migration and FR-044. |

Phase 4 carries the one unknown this plan cannot size: how many bonuses of the fixture
civilisations resist the effect model (D5). The valve is the rule itself — a bonus that does not fit
is recorded as not modelled and its fields stay gapped — so the phase cannot be blocked by it, only
made to report a blocking gap that SC-007a then turns into a visible failure with a named cause.

Phase 5's migration is expand-only and is applied before the deploy per
`docs/runbooks/database-migrations.md`. The local environment file points at production, so no task
in this plan runs a migration from a developer machine; the runbook's sequence is the only path.

## Complexity Tracking

No constitution violation requires justification. Three decisions overrule a written suggestion or
the path of least resistance, and are recorded so a reader does not treat them as oversights.

| Decision | Why | Alternative rejected because |
| -------- | --- | ---------------------------- |
| A fifth workspace package | Vendored third-party data with its own licence record and a hand-transcription workflow does not belong in a package whose rule is no dependencies and no data. | Putting it in `packages/core` makes every importer of a tier type carry a megabyte of game data; putting it in `apps/analyzer` makes it unreachable from 007's library code and from the API's presentation boundary. |
| Hand-modelling civilisation bonuses | FR-023, FR-038 and FR-022a together leave no other lawful path (research D5). | Returning the baseline value is the exact substitution the feature exists to prevent; extracting from the game's data file is barred by the usage rules. |
| Not pairing the two community datasets as primary and cross-check | They are one generation pipeline run twice; their agreement cannot detect a misread (research D3). | It would satisfy FR-028 and FR-030 on paper and deceive the next reader about how validated the values are. |
