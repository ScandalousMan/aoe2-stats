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
commits read) is not restated here; it lives in `docs/data-sources.md` §6. Where a source's licence
was already recorded with its date in `docs/asset-packs.md`, the entry names that record instead of
copying the date, and only a source recorded nowhere else carries its observation here. The ruling vocabulary is two words. **Copy in**
means the source's files may be placed in this repository under the grant recorded. **Read and
transcribe only** means a person reads it and writes the facts they learned into this repository by
hand; the source's files are never copied here and nothing fetches them.

### aoe2techtree (`SiegeEngineers/aoe2techtree`)

- **Holds**: unit, building and technology costs, training, construction and research times, age
  requirements, and which entities each civilisation can build or research, as structured data
  (`data/data.json` and one tree file per civilisation). What it does not cover is in
  `docs/data-sources.md` §6.
- **Question it answers**: "what does this entity cost or require, and which civilisations have it?"
  It is also where a new civilisation first appears as a tree file, but it does not key civilisations
  by Relic's `civilization_id`.
- **Licence status**: MIT on the repository's code and data; the images are a separate grant,
  recorded per pack in `docs/asset-packs.md`.
- **Ruling**: **copy in** for the data, as the vendored packs under `packages/knowledge/packs/`. The
  images are a separate matter and are governed by `docs/asset-packs.md` and each pack's `LICENCE.md`.
- **Observed**: the dates are in `docs/asset-packs.md` "Knowledge packs", on the Checked line.

### aoc-reference-data (`SiegeEngineers/aoc-reference-data`)

- **Holds**: identifiers mapped to display names only: civilisations, maps, technologies, terrain
  and objects, in a Definitive Edition dataset. No costs, times, ages or bonuses.
- **Question it answers**: "what is this identifier called?", for a replay-space id or an object
  name. It does not answer anything about Relic's `civilization_id`, which is a different id space
  (`docs/data-sources.md` §1, "Two civilisation id spaces exist").
- **Licence status**: none.
- **Ruling**: **read and transcribe only.** A repository with no licence grants no right to copy, so
  its files are never copied here. The transcription that has already happened put the id and name
  pairs into `apps/api/src/aoe2stats_api/civilizations.py`; the source file itself was never copied
  into this repository. This is the reason the distinction exists in feature 002's spec.
- **Observed**: the dates are in `docs/asset-packs.md` "Rejected sources" and in the
  `aoc-reference-data` entry of `docs/data-sources.md` §6, under Assessed.

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
     others. -->

### Civilisation mapping

Relic's match history carries a civilisation as a bare integer and never a name. The table that turns
that integer into a name is derived from outside sources and checked against this repository's own
captured fixtures.

**Where it lives.** In exactly one place: `apps/api/src/aoe2stats_api/civilizations.py`. Its module
docstring is the record of the table, the id ranges, the derivation rule and the evidence behind each
range, and `docs/data-sources.md` §1 records the measurement and the two id spaces that must not be
confused. This file does not repeat any of that and no other file may hold a second copy of the
table; a front-end component, a seed script or a document that needs a name asks the module (FR-004).
A fact stated in two places will be wrong in one of them.

**How a derivation is checked.** A derivation is checked against two fixtures this repository
captured and froze, never trusted because a source says so. Relic's match-history fixture numbers a
civilisation, the enrichment source's matches fixture names the same real matches, and joining the two
on match and profile yields id-to-name pairs that neither source gave alone. The executable form of
that check is `apps/api/tests/test_civilizations.py`, and it does the following:

- `test_table_matches_the_fixture_derived_join` re-runs the join and compares every pair it recovers
  with the table. This is the measurement.
- `test_table_matches_the_alphabetical_ordering_rule` compares the entries the join cannot reach with
  what the ordering rule, established by the measured pairs, would produce. It adds no evidence; it
  checks that unmeasured entries are consistent with the rule.
- `test_table_matches_the_transcribed_ids_forty_five_to_sixty` and
  `test_names_the_three_civilisations_measured_after_sixty` assert the entries that follow no rule as
  literal facts, so editing one is a visible change.
- `test_the_three_newest_ids_never_use_the_fallback` fails if a hole opens inside the named range or
  a new id appears without a test.

**A join that recovers nothing is a failure, not a pass.** An assertion over an empty set holds for
any table. `test_table_matches_the_fixture_derived_join` therefore fails when the two fixtures share
no match and profile pair, and again when the join recovers fewer distinct ids than the derivation was
checked against. If the fixtures are replaced or re-captured and the join comes back thin, that is a
red test to investigate, never a green one to keep (FR-006).

**What remains uncovered.** Each of these is a decision, not an oversight (FR-008):

- **Ids inside the named range that no source names.** They are left out of the table on purpose
  and stay on the fallback. The module docstring lists them and the test file asserts them, in
  `test_falls_back_for_the_deliberate_gap_and_beyond_sixty_three`.
- **Every id above the highest named id.** No source names them, so none is in the table.
- **The civilisations the ordering rule cannot reach.** They were added after the roster the rule
  sorts, so the rule says nothing about them and is not extended to cover them. They are in the table
  only as transcribed entries, and the fixture join reaches only some of them; the module docstring
  records which and how many, and the test file asserts them as literals.

**The answer for an id no source names** is to leave it on the fallback, which renders as
"Civilisation <id>", the same shape the leaderboard lookup uses. Never interpolate from its
neighbours and never fill it with a plausible name or a plausible order; an earlier table did exactly
that, and the module docstring records how it failed. An id moves off the fallback only when a source names it
and a fixture or a second source corroborates it, in the same change that adds the test that asserts
it.

## Renames

<!-- A rename changes the displayed name and never the numeric id. Filled by T208. -->

## Precedence

<!-- Which source wins when two disagree, and why. Filled by a later task. -->

## Known gaps

<!-- What no source covers, stated as a decision rather than an absence. Filled by a later task. -->
