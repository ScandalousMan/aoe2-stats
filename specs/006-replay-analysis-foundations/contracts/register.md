# Contract — the determinability register

**Covers**: FR-001 to FR-006a, FR-012, SC-001, SC-012, SC-013 | **Model**:
[data-model.md](../data-model.md) §4

## The file

`packages/core/src/aoe2stats_core/truth/register.toml` — one table per datum, keyed by its id. It is
the only place a classification is written. Field rules are in the data model; this contract states
what the loader, the view and the gate guarantee.

```toml
[datum."participant.age_up_commands"]
classification = "observed"
status = "published"
source = "research commands naming an age technology, per participant"
method = "first-occurrence collapse; match-clock time of the command"
requires_knowledge = []
depends_on = []
validation = "packages/replay-engine/tests — golden timeline"
evidence = "specs/003-player-search-match-analysis/research.md R4"

[datum."participant.units_lost"]
classification = "non-determinable"
status = "blocked"
blocked_on = "an outcome event in the recording format"
reason = "the recording carries no damage, death or completion event, and no post-game statistics block"
impact = "no casualty count, no army value over time, no trade evaluation"
approximation = "group silence, published separately as an inferred engagement signal"
approximation_acceptable = "no"
would_change_if = "a recording format that carries outcome events, or a post-game statistics block"
evidence = "docs/data-sources.md §2"
```

## What the loader guarantees

Loading fails — the package does not import — when any of these holds:

1. An id is duplicated, or does not follow the naming discipline's shape.
2. `classification` or `status` is outside its closed set.
3. A `non-determinable` entry omits any of its five mandatory fields, or gives
   `approximation_acceptable` a value other than `yes` or `no` (FR-003).
4. A `blocked` entry omits `blocked_on` (FR-005).
5. `depends_on` names an id that does not exist, or the graph has a cycle.
6. An entry's tier is stronger than the weakest tier among its `depends_on` (FR-008).
7. An `inferred` or `predicted` entry has a `published` status and no confidence method stated.
8. `evidence` is empty. An entry may not rest on nothing.

## Entries this feature must contain

- Every leaf of the document version 003 publishes today, at `observed` or `decoded`.
- Every canonical event kind's payload fields.
- `participant.units_lost`, as above (FR-004).
- Explicit deletions and market transactions, at `decoded` (FR-014).
- The group-silence datum, at `inferred`, with its `non_claim` (FR-013).
- Every datum feature 007 intends to publish, at `planned` or `blocked`, each with its
  `requires_knowledge` — this is what makes gap severity computable (FR-005, research D7).
- The starting-state data, as `decoded` and `blocked`, with `blocked_on` naming the decoder.

## The generated view

`packages/core/src/aoe2stats_core/truth/REGISTER.md`, rendered by the loader's own module, grouped by
classification, with the non-determinable entries first and in full. It carries a header saying it is
generated and from what.

**Drift gate.** A test renders the view in memory and compares it byte for byte with the committed
file. A difference fails the suite and prints the command that regenerates it (FR-006a).

**SC-012** is the view's acceptance test, by hand: pick a datum, find it in the view without opening
a Python file, and read off whether it can be known and how that is checked.

## The publication gate

`validate.py` walks a document. Every leaf value must resolve, by its path, to exactly one datum whose
status is `published`. A leaf that resolves to none, to a `planned` or `blocked` datum, or to two,
fails validation (FR-006, SC-001). The mapping from path to datum is part of the register entry, so a
new published field without an entry cannot pass — there is no allow-list to forget to update.

## What it must never do

- Restate a measurement. `evidence` is a reference (SC-013).
- Be edited to make a failing validation pass without the change that earns the new status.
