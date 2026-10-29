# Reference data sources

These are sources a **maintainer** consults on the occasions the game changes: a new civilisation, a
rename, a rebalance. Nothing in the running system, its build or its tests ever fetches them. They
are read by a person, and what a person learns from them is transcribed into this repository by hand
(FR-011).

That is what separates them from the sources the providers actually call. The product's own calls,
and the measured properties of what they return, are in [`data-sources.md`](./data-sources.md). This
file records what a human reads; that one records what the product calls (FR-012).

## Source inventory

Three sources, each entry giving what it holds and the question it answers, its licence status and the
ruling that follows from it, and the date that status was observed. A licence status is an
observation on a date, not a permanent property: a repository can add or change a licence at any
time, so re-observe before relying on a row. The measured detail of each source (counts, id spaces,
commits read) is not restated here; it lives in `docs/data-sources.md` §6, and the licence record of
the vendored packs lives in `docs/asset-packs.md`. The ruling vocabulary is two words. **Copy in**
means the source's files may be placed in this repository under the grant recorded. **Read and
transcribe only** means a person reads it and writes the facts they learned into this repository by
hand; the source's files are never copied here and nothing fetches them.

### aoe2techtree (`SiegeEngineers/aoe2techtree`)

- **Holds**: unit, building and technology costs, training, construction and research times, age
  requirements, and which entities each civilisation can build or research, as structured data
  (`data/data.json` and one tree file per civilisation). Civilisation bonuses are present only as
  English prose, and combat attributes are absent.
- **Question it answers**: "what does this entity cost or require, and which civilisations have it?"
  It is also where a new civilisation first appears as a tree file, but it does not key civilisations
  by Relic's `civilization_id`.
- **Licence status**: MIT on the repository's code and data. The `img/` directory is carved out of
  that licence by its own `img/README` and is covered only by the game publisher's content usage
  rules (`docs/asset-packs.md` records this per pack).
- **Ruling**: **copy in** for the data, as the vendored packs under `packages/knowledge/packs/`. The
  images are a separate matter and are governed by `docs/asset-packs.md` and each pack's `LICENCE.md`.
- **Observed**: 2026-09-20, the day the first pack was vendored (`docs/asset-packs.md` "Knowledge
  packs", Checked), and 2026-10-08 for the second pinned commit.

### aoc-reference-data (`SiegeEngineers/aoc-reference-data`)

- **Holds**: identifiers mapped to display names only: civilisations, maps, technologies, terrain
  and objects, in a Definitive Edition dataset keyed to the replay's civilisation id space. No costs,
  times, ages or bonuses.
- **Question it answers**: "what is this identifier called?", for a replay-space id or an object
  name. It does not answer anything about Relic's `civilization_id`, which is a different id space
  (`docs/data-sources.md` §1, "Two civilisation id spaces exist").
- **Licence status**: none. The repository carries no `LICENSE` file and GitHub reports
  `license: None`.
- **Ruling**: **read and transcribe only.** A repository with no licence grants no right to copy, so
  its files are never copied here. The transcription that has already happened put the id and name
  pairs into `apps/api/src/aoe2stats_api/civilizations.py`; the source file itself was never copied
  into this repository. This is the reason the distinction exists in feature 002's spec.
- **Observed**: 2026-08-30 (`docs/asset-packs.md` "Rejected sources", licence "None found"), and
  re-verified 2026-09-19 (feature 002 research.md).

### aoe2-apis

- **Holds**: a catalogue of the public and community Age of Empires II: DE data APIs: the game
  client's own backend, live lobbies, aggregators, replay parsers and libraries, each with example
  requests and notes on what it can and cannot do (`README.md`, `apis.yaml`, `docs/`, `examples/`).
  It describes itself as unofficial: every interface it lists is reverse-engineered and can change
  without notice.
- **Question it answers**: "which external API answers this question, and what is known about it?"
  It is a map for finding a source, not an identifier table.
- **Licence status**: MIT. The repository's root `LICENSE` file reads "Copyright (c) 2026
  ustacode", and GitHub reports `mit`. Repository: `ustacode/aoe2-apis`.
- **Ruling**: **copy in** is permitted, with the MIT notice. What it says about an endpoint is a
  lead, not a fact for this repository: before anything depends on it, it is measured and recorded
  in `docs/data-sources.md`, which stays the single home for measured properties of the APIs the
  product calls.
- **Observed**: 2026-10-29, against the latest commit at that date, `8fad62c` (committed
  2026-07-10).

## Re-derivation procedure

<!-- One subsection per identifier whose display values are derived from outside sources. Each
     subsection answers the same questions, in this order:
       1. Where the mapping lives (exactly one place).
       2. How a derivation is checked against captured fixtures.
       3. What remains uncovered, and the answer for an id no source names.
     Add a new identifier as a sibling `###` subsection beside the first; do not restructure the
     others. Filled by T206. -->

### Civilisation mapping

<!-- Worked example. Filled by T206. -->

## Renames

<!-- A rename changes the displayed name and never the numeric id. Filled by T208. -->

## Precedence

<!-- Which source wins when two disagree, and why. Filled by a later task. -->

## Known gaps

<!-- What no source covers, stated as a decision rather than an absence. Filled by a later task. -->
