# Contract — the seen data and the estimates in the published analysis document

**Covers**: FR-027 to FR-040, US6, SC-011 to SC-015 | **Model**: [data-model.md](../data-model.md)
§12 to §15 | **Research**: R16, R17

Seven data. Two are `observed`: exact facts about which objects the commands named. Five are
estimates at 006's `inferred` tier. The estimates use the place, the confidence and the validator
rules 006 already has for that tier
(`specs/006-replay-analysis-foundations/contracts/analysis-document.md`), and add nothing to the
`reconstructed` block of [reconstruction-document.md](./reconstruction-document.md).

## Shape

```json
{
  "participants": [
    { "…": "… unchanged …",
      "units_seen": [ { "object": 0, "first_named_ms": 0, "last_named_ms": 0,
                        "later_named_by": { "participant": 2, "from_ms": 0 } } ],
      "producing_buildings_seen": [ { "object": 0, "first_order_ms": 0, "last_order_ms": 0 } ] }
  ],
  "inferred": {
    "participant.estimated_unit_losses": [
      { "participant": 1,
        "losses": [ { "object": 0, "at_ms": 0, "dated_by": 0, "last_named": 0 } ],
        "confidence": { "level": "low", "basis": "…" }, "non_claim": "…" }
    ],
    "participant.estimated_buildings_destroyed": [
      { "participant": 1,
        "destroyed": [ { "object": 0, "at_ms": 0, "dated_by": 0, "last_order": 0 } ],
        "confidence": { "level": "low", "basis": "…" }, "non_claim": "…" }
    ],
    "participant.estimated_population_excess": [
      { "participant": 1,
        "excess": [ { "at_ms": 0, "population": 0 } ],
        "confidence": { "level": "low", "basis": "…" }, "non_claim": "…" }
    ],
    "participant.estimated_living_population": [
      { "participant": 1,
        "series": [ { "at_ms": 0, "population": 0 } ],
        "confidence": { "level": "low", "basis": "…" }, "non_claim": "…" }
    ],
    "participant.estimated_production_idle": [
      { "participant": 1,
        "periods": [ { "building": 0, "from_ms": 0, "to_ms": 0 } ],
        "after_last_order": [ { "building": 0, "from_ms": 0, "to_ms": 0, "ended_by": "match-end" } ],
        "confidence": { "level": "low", "basis": "…" }, "non_claim": "…" }
    ]
  },
  "estimates_withheld": [
    { "datum": "participant.estimated_living_population", "participant": 1, "bound": "non-negative",
      "at_ms": 0 }
  ],
  "provenance": {
    "participant.units_seen": { "tier": "observed", "method": "…", "inputs": [] },
    "participant.estimated_unit_losses": { "tier": "inferred", "method": "…", "inputs": [] }
  }
}
```

- **The two seen data** are the register data `participant.units_seen` and
  `participant.producing_buildings_seen`, at `observed`, published under each participant beside
  006's own participant data. A unit is an object id named in a unit list from which no order is
  issued as a building; a building is seen at every order that names it, every building of a
  command included (FR-030). `later_named_by` is present only when another participant's commands
  name the same unit afterwards.
- **Each estimate has one instance per participant**, so a confidence and a non-claim are stated
  once per participant and not once per unit.
- **`dated_by`, `last_named`, `last_order`** are indices into the canonical stream: the enemy
  command that dates the loss and the owner's last command or order before it (FR-032).
- **`excess`** entries are FR-033's: a clock and the population by which the living population
  would have passed the limit. They name no object and no unit type.
- **`series`** holds the estimated living population after each change (FR-034).
- **`after_last_order`** is the stretch from a building's last order to what ended it, from the
  closed set `estimated-destroyed`, `owner-exit`, `match-end`. It includes the production of the
  last items ordered and is never part of a period (FR-035).
- **Every one of the seven has a `provenance` entry**, as 006's rule 2 requires of any datum present.
- **An estimate withheld** is absent, and the document says why in the place 006 already uses for
  that: `knowledge_gaps` when a knowledge field is missing or a participant's starting units are
  unknown (which withholds its living population and population excess, FR-031), and the sibling list
  `estimates_withheld` when the living population went negative, which withholds it and the
  population excess together. An entry names the datum, the participant, the bound and the clock,
  and carries no value. `estimates_withheld` is a report like `knowledge_gaps`, not a datum: it
  joins the keys 006's validator rule 1 leaves outside the register, and the change that adds it
  adds a dated note to 006's document contract saying so.

## Register entries

All seven are in the register as `planned` from the feature's first register change (FR-027; 006
FR-005) and move to `published` in the change that publishes them. An estimate's entry carries what
006's register requires of the `inferred` tier, and one new optional key:

| Field | What it holds |
| ----- | ------------- |
| `method` | The estimation method with a version label, precisely enough to recompute, including each interim policy in force (research R17). A changed method is a new label (FR-038). |
| `confidence_method` | How the level is assigned, in prose, as for 006's group-silence entry. |
| `calibration` | New, optional: the playback readings that measured the estimate's error. Absent until they exist. |
| `non_claim` | What the estimate is not, and the direction in which it errs, from research R16's table (FR-029). |
| `depends_on` | The data it reads. The estimated unit losses depend on `participant.units_seen`; the living population on the estimated unit losses and the population excess. No estimate lists the deletion datum (FR-036). |

The `participant.units_lost` entry stays `non-determinable`. Its `approximation` names
`participant.estimated_unit_losses` and says it is a separately named `inferred` datum, never the
count; its `approximation_acceptable` becomes `yes`, on the owner's ruling of 2026-11-15 (FR-039).
The existing assertion that it is `no` changes in that same change and nowhere else.

## Isolation (FR-028, SC-012)

1. The estimates are computed by a sub-package of the reconstruction package that no module
   producing a datum at a stronger tier imports. The seen data are computed outside it. A
   test walks the package's imports and fails on one.
2. For each committed recording, the `reconstructed` block and the seen data are byte-identical
   with the estimates computed and with them switched off.
3. An estimate may read the order fold, the queue mechanics, the seen data, the knowledge base,
   adopted rules and reconstructed values. Nothing reads an estimate back.

## Validation

006's rules 5 and 6 already confine every `inferred` datum under `inferred` with a confidence, and
keep stronger tiers out. Two rules are added beside the reconstruction's:

| # | Rule | Requirement |
| - | ---- | ----------- |
| 15 | Every instance of an estimate datum carries a non-empty `non_claim`, and its confidence level is `low` when its register entry has no `calibration`. | FR-029, SC-011 |
| 16 | Every `estimates_withheld` entry names an estimate datum that is absent from `inferred` for that participant, and no living-population series present holds a negative value. | FR-034 |

## Golden and error files

| File | Role |
| ---- | ---- |
| `tests/fixtures/replays/<recording>.seen-estimates.json` | The golden seen data and estimates of each committed recording, compared byte for byte. |
| `tests/fixtures/replays/<recording>.playback.toml` | Already the one place a reading is written. Each reading that corresponds to an estimate gains an `estimate_error` table: the estimate datum, the estimated value, the difference, and how the game's figure and the estimate differ in what they measure. |

The test asserts that every such reading has its `estimate_error` and that the recorded estimated
value is what the analysis produces. It does not assert the size of the difference (FR-037,
SC-014).

## The reader

A document that carries the seven data must never reach a reader that rejects it: the change that
publishes them makes `apps/web/src/features/analysis/api.ts` accept them structurally, with a test.
The view of FR-040 comes later and reads them through typed assertions.

## What it must never do

- Publish an estimate whose name or label lacks the word that marks it as an estimate, or word an
  estimated loss as units lost.
- Let a value at a stronger tier, a settlement or a rule cite an estimate.
- Read an explicit deletion.
- Refuse a document because an estimate broke a bound.
