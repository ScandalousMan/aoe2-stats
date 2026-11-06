# Implementation Plan: Match reconstruction

**Branch**: `plan/008-match-reconstruction` | **Date**: 2026-11-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-match-reconstruction/spec.md`

## Summary

Turn 006's canonical stream and knowledge base into one exact value per reconstructed datum, for
every participant: what they spent, the production they ordered per building, when each age-up
arrived, what they spent on military units, and later their population and Town Center idle time.
Each value names what settled every condition it depends on, an order that proves it or a written
rule, and a rule settles a published value only once the game's own playback has checked it.

**Phase 0 found that the recordings already contradict the spec's working hypothesis.** FR-003b
counts every recorded queue command as paid until measured. The measurement is in the repository:
the same technology is commanded twice, a fraction of a second apart, 25 times, and the game can
accept only one of each pair; and with every recorded order executed, the age-up model puts 10 of
the 22 committed age-ups after an order that proves the age was already reached. Publishing under
that hypothesis would publish values the recording refutes. So the plan opens with a gate, **G1**:
how to tell an executed command from a refused one, settled by owner readings of each age-up's queue
before any spending or arrival is published. If no observed fact can tell them apart, that is an
arbitration for the owner, not a licence to publish the hypothesis.

Three other findings change what is built.

**Most queue commands name several buildings, and the canonical stream keeps one.** Up to four in
five commands in one recording. Every per-building datum depends on it, so the vocabulary is
widened additively before anything is reconstructed, and how the game spreads a command over its
buildings is the second reading G1 needs.

**The knowledge base has no population and no unit class.** Population and the military share each
need a knowledge field that does not exist; both are added through 006's snapshot mechanism, from
lawful sources, and the membership of "military" is put to the owner because it is a definition.

**The age proof rule holds and is a free test of the knowledge base.** Of 3,241 orders, the only six
that require an age not yet clicked are one Sicilian unit the knowledge base dates one age too late.
The rule is adopted, the defect goes to 006's owner readings, and the check becomes permanent.

Population and idle time get no method in this plan, as FR-012 requires: the strategies are analysed
(research R5), each is a candidate, and their phase is filed behind the knowledge fields and the
readings it needs.

Full reasoning and every measurement: [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.13; TypeScript for the view phase only.

**Primary Dependencies**: No third-party dependency added. One new workspace package,
`aoe2stats-reconstruction`, depending on `aoe2stats-core` and `aoe2stats-knowledge`. It is declared
on `apps/analyzer`'s own manifest, not inherited from the workspace, because the deployed function
installs only what the analyzer declares (006 plan, Technical Context). The rules registry is TOML,
read with the standard library.

**Storage**: None new. The reconstruction is part of the published document, which already has an
identity-addressed key and a row pointing at it (006 data-model §8). No table, no column, no
migration. Rules, goldens and playback readings are files in the repository.

**Testing**: `uv run pytest` under `PYTEST_DISABLE_NETWORK=1`; `uv run mypy`; `uv run ruff`.
Golden reconstructions compared byte for byte, hand-built in the existing style (no snapshot
plugin). Playback-reading agreement asserted per reading. Synthetic order streams per civilisation
and per effect state (FR-020). The view phase adds Storybook stories and Playwright baselines in
both themes, CI-authoritative.

**Target Platform**: Vercel Hobby `cdg1` and the phase-2 VPS, unchanged: a library inside the
existing on-demand analysis function.

**Project Type**: Python library package in the existing uv workspace, consumed by one existing
application; one front-end component change.

**Performance Goals**: SC-008, no more than twice today's analysis time on the committed
recordings. No baseline exists today (research R14), so the first phase records one before any
reconstruction code lands. One pass over the stream; knowledge answers memoised per entity,
civilisation and settled state.

**Constraints**: 003's analysis memory ceiling binds the new code as it binds the stream: nothing is
retained past the fold but the reconstruction itself. The analysis function's existing duration
limit and budget are unchanged. No scheduled job, no network call, nothing on the capture path
(FR-023). FR-002: the stream and the knowledge base are the only inputs, so the match result on the
API's rows is not read even where it would help (research R8). No interval, midpoint or probability
anywhere in the published types (FR-008).

**Scale/Scope**: 5 user stories, 29 functional requirements, 10 success criteria. One new package,
three existing packages touched (`packages/core`, `packages/replay-engine`, `packages/knowledge`
through new snapshots) and one application (`apps/analyzer`), one front-end feature directory and
one design-system composite. Three committed recordings; 22 age-ups; 14 rules in the initial registry, 4 adopted at
entry (contracts/rules.md). Nine phases, two of them gates.

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design; the verdicts below are
the post-design ones. All twelve principles were walked from `.specify/memory/constitution.md`
itself, not from 006's table._

| #        | Principle | Verdict | How this feature satisfies it |
| -------- | --------- | ------- | ----------------------------- |
| **I**    | Capture Outranks Analysis | **PASS** | Nothing touches the ingester, the enqueue, the budget or the replay fetch. The reconstruction runs only inside an analysis a person asked for (FR-023), and the vocabulary widening changes the adapter's output, not what is fetched or kept. |
| **II**   | Python Backend | **PASS** | All reconstruction is Python. The view renders numbers and settlements it is given and computes none of them. |
| **III**  | All External Data Goes Through a DataProvider | **PASS**, by making no call | No outbound connection. New knowledge fields and tables are transcribed by hand from sources `docs/data-sources.md` §6 references, as 006's snapshots are; playback readings are a person reading the game, which extracts nothing from its files. |
| **IV**   | Raw Is Sacred, Derived Is Disposable | **PASS** | Recordings are read, never written. The reconstruction is derived and records what produced it: the package version and the rules digest in the identity (FR-021), so a change recomputes into a new object and the old one is kept (006 FR-042). The canonical goldens are regenerated, which is a derived artifact under the fixtures README's rules. |
| **V**    | Parsing Runs in an Isolated, Pluggable Engine | **PASS**, and the seam is used as designed | The reconstruction reads the canonical vocabulary and nothing engine-shaped. The two additions it needs (every producing building, the population limit) and the starting-attributes producer are made in the vocabulary and the adapter, so a second engine would target them too. The starting-attributes decoder reads header bytes, not the engine's output. |
| **VI**   | Tokens First | **PASS**, in the view phase | The modelled label and the settlement indicator are specified by the product designer first and built from design-system tokens only. |
| **VII**  | Visual Tests Are Mandatory | **PASS**, in the view phase | New or changed stories pass the visual reviewer and get baselines in both themes; the full-page baselines are captured from CI's render. |
| **VIII** | No Secrets in the Clear | **PASS** | No secret, no new environment variable. |
| **IX**   | GDPR by Design | **PASS** | No new personal data. The committed recordings are unchanged and already covered by the processing register's activity for committed reference recordings (006). A playback reading records who read it, which is the owner, under the same footing as 006's owner readings. Regions unchanged. |
| **X**    | Intellectual Property | **PASS**, with one obligation | New knowledge (population fields, the economic-unit list, starting objects) is transcribed from sources whose ruling `docs/data-sources.md` §6 already records, or from the owner's reading of the running game, whose ruling is "read and transcribe"; the game's data file stays rejected. A source not yet ruled is assessed in that section before anything is transcribed from it. |
| **XI**   | Documentation Is in English | **PASS** | Every artifact is English. |
| **XII**  | Portable by Construction | **PASS** | The rules registry and the economic-unit list are package data read through `importlib.resources`. No local state, no platform-specific code. |

**Post-design re-check.** No verdict changed between the first pass and the design. One obligation
was added to X when research R10 and R5 showed the knowledge base must grow; it is the same
discipline 006 follows, named so a task carries it.

## Project Structure

### Documentation (this feature)

```text
specs/008-match-reconstruction/
├── plan.md              # This file
├── research.md          # Phase 0 — R1..R14: the measurements and the decisions
├── data-model.md        # Phase 1 — orders, queue items, conditions, settlements, rules, values
├── quickstart.md        # Phase 1 — how to verify each phase
├── owner-readings.md    # What to read in the game, O1..O6; asks, never answers
├── contracts/
│   ├── reconstruction-document.md   # The `reconstructed` block, identity, validator rules 11..14
│   ├── rules.md                     # The proof and deduction registry and its initial set
│   ├── canonical-events-amendment.md# Every producing building; population limit; starting attributes
│   └── playback-readings.md         # Readings, goldens, and what the tests assert
├── checklists/
└── tasks.md             # /speckit-tasks — NOT created here
```

### Source Code (repository root)

```text
packages/reconstruction/                     # NEW PACKAGE — depends on core and knowledge only
├── pyproject.toml
├── src/aoe2stats_reconstruction/
│   ├── __init__.py                          # the package version; the identity component
│   ├── orders.py                            # one fold over the canonical stream into orders
│   ├── queues.py                            # per-building queue model; distribution; execution
│   ├── state.py                             # conditions settled per participant over the match
│   ├── settle.py                            # proof and deduction rules applied; settlements
│   ├── rules.py                             # registry loader, guarantees, view renderer
│   ├── rules.toml                           # THE registry
│   ├── RULES.md                             # generated view — never hand-edited
│   ├── starting.py                          # starting state from the decoded attributes and the lobby
│   ├── spending.py                          # resources spent, military share, production per building
│   ├── arrivals.py                          # modelled age-up arrivals
│   ├── invariants.py                        # the closed invariant set and the breach
│   └── document.py                          # the `reconstructed` block, untied deletions included
└── tests/                                   # synthetic streams per civilisation and effect state

packages/core/src/aoe2stats_core/
├── replay/events.py                         # `building_objects` on unit-queued (additive)
└── truth/
    ├── register.toml                        # new data; status moves; FR-003 method amendment
    ├── REGISTER.md                          # regenerated
    └── validate.py                          # rules 11..14

packages/replay-engine/src/aoe2stats_replay_engine/
├── canonical.py                             # every producing building; population limit; starting attributes
└── starting.py                              # NEW — the Tier A starting-attributes decoder

packages/knowledge/snapshots/                # new superseding snapshots: population fields, the
                                             # economic-unit list, starting objects, the age-requirement fix

apps/analyzer/
├── pyproject.toml                           # + aoe2stats-reconstruction, declared not inherited
└── src/aoe2stats_analyzer/
    ├── extract.py                           # document version 3; the reconstruction block; identity
    └── reproduce.py                         # accepts the installed reconstruction engine

apps/web/src/features/analysis/              # typed reading of `reconstructed`; mappers
packages/design-system/specs/                # the modelled-value spec, by the product designer first
packages/design-system/src/composites/AnalysisTimeline/   # modelled values beside observed ones

tests/fixtures/replays/
├── <recording>.canonical.json               # regenerated (unit-queued lines only)
├── <recording>.reconstruction.json          # NEW — golden reconstructions
└── <recording>.playback.toml                # NEW — the owner's readings

docs/
├── data-sources.md                          # §2: multi-building commands, refused commands kept,
│                                            # empty unit-id lists (research R13)
└── risks.md                                 # the reconstruction's rule risk, cross-referenced

pyproject.toml                               # workspace member; testpaths; mypy
.github/workflows/pr.yml                     # python filter gains the new package
```

**Structure Decision**: one new package, for the reason research R12 gives: the knowledge base never
decides which condition held, the analyzer is an application the golden and synthetic tests should
not need, and the rules registry with its view and drift gate belongs beside the code that obeys it,
as the register sits beside the validator. Everything that is a fact about the game (population
fields, the economic-unit list, starting objects, the corrected age requirement) goes into the
knowledge base through its own snapshot mechanism and nowhere else; everything that is a decision
about what a recording proves goes into the registry.

## Phases

Each is independently green and separately mergeable. `/speckit-implement` runs one phase at a time,
naming the task range and the stop condition. Two phases are gates: they end in a decision recorded
in the registry, and what follows them does not start until that decision is made.

| # | Phase | Stories | Why here |
| - | ----- | ------- | -------- |
| 1 | Evidence and vocabulary | — | The owner readings are the critical path and cost a person's time, so they are requested first (owner-readings.md is already written). In parallel: the vocabulary widening, the population limit, the analysis-time baseline SC-008 needs, the age-proof consistency test, the Sicilian age-requirement defect filed with 006, and the spec's wrong citation corrected. Nothing here publishes. |
| 2 | The reconstruction spine | US3, US5 | The package, the order fold, the rules registry and its view, settlements, the invariants, the identity's reconstruction component, the reproduce path, validator rules 11 to 14, and document version 3 with an empty `reconstructed` block. The starting-attributes decoder lands here because every price needs the starting age. |
| 3 | **Gate G1: executed or refused, and distribution** | — | Transcribes O1 and O2, writes D-EXEC-1 and D-DIST-1 from what they show, builds the queue model, and checks it against the 22 age-up queues. Ends adopted, or ends in the arbitration Complexity Tracking names, in which case phases 4 and 5 do not publish. |
| 4 | Age-up arrivals | US2 | First, because every price depends on the age in force (FR-010, US1 scenario 2). D-AGE-1 and D-HOUSE-0 are adopted against the age-up readings, D-WIN-1 on the owner's ruling; `age_requirement` joins the datum's required knowledge, so its gaps turn blocking. |
| 5 | Spending, military share, production per building | US1 | Needs the age timeline from phase 4, the economic-unit list, and the owner's rulings on D-TECH-1, D-CONTROL-1 and D-CANCEL-1. Ties deletions (O5) and applies the refund rule. Amends the spending method in the register (FR-003) in the same change that publishes it. |
| 6 | Correctness at scale | US3, US5 | The golden reconstructions of all three recordings agreeing with every reading, the synthetic stream for every civilisation and every effect state (FR-020), the per-rule settlement table (SC-009), the analysis-time check (SC-008), and byte-identical reproduction (SC-006). |
| 7 | The view | US4 | The product designer's spec, then the component, stories and baselines in both themes, then the mappers. Last of the published work because it only renders what phases 4 and 5 publish. |
| 8 | **Gate G2: population and idle time** | — | FR-001a and FR-012. The two population fields added to the knowledge base, the candidate rules of research R5 written, O6 requested and transcribed. Idle time by empty queue first (it needs only G1); population only if a candidate survives the readings. The two register entries are added as `planned` in the change that files this phase's tasks. |
| 9 | Closing | — | The research measurements moved into `docs/data-sources.md` §2 under tests, the risk register, the quickstart run end to end, and the lint over every feature. |

**What can run in parallel.** Phase 1's tasks are independent of each other. Phase 2 does not wait
for the readings. Phase 8's knowledge fields can be transcribed at any point after phase 1. Phases 3
to 7 are sequential.

**No migration.** Nothing here changes a table, so no deploy sequencing applies. A deploy of phases 4
and 5 makes every published analysis stale by identity (the reconstruction engine changes), and the
staleness test recomputes each on its next request, as it did for 006's knowledge versions.

## Complexity Tracking

No constitution violation. Five decisions depart from the spec's text or from the path of least
resistance; each is recorded so a reader does not take it for an oversight, and four of them need
the owner.

| Decision | Why | Alternative rejected because |
| -------- | --- | ---------------------------- |
| FR-003b's hypothesis is not adopted, even as a default | The recordings refute it (research R2): published, it gives arrivals the recording itself contradicts. **Needs the owner**: FR-003b should be amended to say the hypothesis is refuted and G1 replaces it. | Adopting it as written satisfies FR-003b's letter and breaks FR-019 and SC-001 on day one. |
| If G1 cannot tell executed from refused exactly, spending and arrivals are not published | The owner's rule allows one exact value or nothing; a refusal for want of resources depends on income, which is `blocked` (research R2). **Needs the owner** if it happens: accept a narrower datum, or keep it unpublished. | Publishing a figure "under a named hypothesis" that the recording contradicts is the estimate-wearing-a-disguise the spec's US3 forbids. |
| 006's canonical vocabulary is widened by this feature | Per-building data need every producing building (research R1). | Reading the engine below the seam re-couples the reconstruction to one engine (006 FR-015). |
| The economic-unit list is a proposal, not a decision | What "military" covers (Monks, Missionaries, transports) is a definition the code cannot settle (research R10). **Needs the owner.** | Deriving it from production buildings silently decides the same question. |
| D-TECH-1, D-CONTROL-1, D-CANCEL-1 and D-WIN-1 enter as candidates | Each settles a condition no order proves and no clarification covers (research R7 to R9); FR-007 requires a ruling or evidence. **Needs the owner's rulings.** | Adopting them on this plan's say-so is the unwritten assumption the owner's rule forbids. |
