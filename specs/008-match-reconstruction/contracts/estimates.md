# Contract — the estimates in the published analysis document

**Covers**: FR-027 to FR-040, US6, SC-011 to SC-015 | **Model**: [data-model.md](../data-model.md)
§12 to §14 | **Research**: R16, R17

The estimates are new data at 006's `inferred` tier. They use the place, the confidence and the
validator rules 006 already has for that tier
(`specs/006-replay-analysis-foundations/contracts/analysis-document.md`), and add nothing to the
`reconstructed` block of [reconstruction-document.md](./reconstruction-document.md).

## Shape

Six data are added under the document's `inferred` key. Each has one instance per participant, so a
confidence and a non-claim are stated once per participant and not once per unit.

```json
{
  "inferred": {
    "participant.unit_seen_intervals": [
      { "participant": 1,
        "intervals": [ { "object": 0, "first_named_ms": 0, "last_named_ms": 0,
                         "left": "estimated-lost", "left_ms": 0 } ],
        "confidence": { "level": "low", "basis": "…" }, "non_claim": "…" }
    ],
    "participant.producing_building_seen_intervals": [
      { "participant": 1,
        "intervals": [ { "object": 0, "first_order_ms": 0, "last_order_ms": 0,
                         "left": "none", "unused_after_ms": 0 } ],
        "confidence": { "level": "low", "basis": "…" }, "non_claim": "…" }
    ],
    "participant.estimated_unit_losses": [
      { "participant": 1,
        "identified": [ { "object": 0, "at_ms": 0, "dated_by": 0, "last_named": 0 } ],
        "population_limit": [ { "at_ms": 0, "population": 0 } ],
        "confidence": { "level": "low", "basis": "…" }, "non_claim": "…" }
    ],
    "participant.estimated_buildings_destroyed": [
      { "participant": 1,
        "identified": [ { "object": 0, "at_ms": 0, "dated_by": 0, "last_order": 0 } ],
        "confidence": { "level": "low", "basis": "…" }, "non_claim": "…" }
    ],
    "participant.estimated_living_units": [
      { "participant": 1,
        "series": [ { "at_ms": 0, "population": 0 } ],
        "confidence": { "level": "low", "basis": "…" }, "non_claim": "…" }
    ],
    "participant.estimated_production_idle": [
      { "participant": 1,
        "periods": [ { "building": 0, "from_ms": 0, "to_ms": 0 } ],
        "confidence": { "level": "low", "basis": "…" }, "non_claim": "…" }
    ]
  }
}
```

- **`left`** is closed: `none`, `estimated-lost`, `deleted`, `changed-owner` for a unit; `none`,
  `estimated-destroyed` for a building. `left_ms` is present unless `left` is `none`.
- **`dated_by`, `last_named`, `last_order`** are indices into the canonical stream: the enemy
  command that dates the loss and the owner's last command or order before it, so a reader finds
  both (FR-032).
- **`population_limit`** entries are the unidentified losses of FR-033: a clock and the population
  in excess of the limit at that clock. They name no object and no unit type.
- **`population`** in the living series is the population the knowledge base says the estimated
  living units occupy (FR-034). The series holds the value after each change.
- **`unused_after_ms`** is the time between a building's last order and its estimated destruction,
  or otherwise its owner's exit or the end of the match. It is never part of a period (FR-035).
- **An estimate withheld** is absent, and the document says why in the place 006 already uses:
  `knowledge_gaps` when a knowledge field is missing, and a new sibling list `estimates_withheld`
  when one of FR-034's bounds broke, each entry naming the datum, the participant, the bound and the
  offending value. `estimates_withheld` is a report like `knowledge_gaps`, not a datum: it joins the
  keys 006's validator rule 1 leaves outside the register.

## Register entries

Each of the six is a register datum, classification `inferred`, added in the change that publishes
it (FR-027), with the fields 006's register requires of that tier:

| Field | What it holds |
| ----- | ------------- |
| `method` | The estimation method with a version label, precisely enough to recompute, including each interim policy in force (research R17). A changed method is a new label (FR-038). |
| `confidence_method` | How the level is assigned. `low` until playback readings have measured the estimate's error; the entry cites the recorded errors once they exist (FR-029, FR-037). `high` is not assignable while that calibration is absent. |
| `non_claim` | What the estimate is not, and the direction in which it errs, from research R16's table (FR-029). |
| `depends_on` | The observed, decoded or reconstructed data it reads. Never another estimate's datum unless that datum is listed. |

The `participant.units_lost` entry stays `non-determinable`. Its `approximation` names
`participant.estimated_unit_losses`, and its `approximation_acceptable` records the owner's ruling of
2026-11-15: accepted as a separately named `inferred` datum, never as the count (FR-039).

## Isolation (FR-028, SC-012)

1. The estimates are computed by a sub-package of the reconstruction package that no module
   producing a reconstructed or derived value imports. A test walks the package's imports and fails
   on one.
2. For each committed recording, the `reconstructed` block is byte-identical with the estimates
   computed and with them switched off.
3. An estimate may read the order fold, the queue mechanics, the knowledge base, adopted rules and
   reconstructed values. Nothing reads an estimate back.

## Validation

006's rules 5 and 6 already confine every `inferred` datum under `inferred` with a confidence, and
keep stronger tiers out. Two rules are added beside the reconstruction's:

| # | Rule | Requirement |
| - | ---- | ----------- |
| 15 | Every instance of an estimate datum carries a non-empty `non_claim`, and a confidence level no higher than its register entry's `confidence_method` allows. | FR-029, SC-011 |
| 16 | Every `estimates_withheld` entry names an estimate datum that is absent from `inferred` for that participant, and no estimate present breaks a bound of FR-034. | FR-034 |

## Golden and error files

| File | Role |
| ---- | ---- |
| `tests/fixtures/replays/<recording>.estimates.json` | The golden estimates of each committed recording, compared byte for byte. |
| `tests/fixtures/replays/<recording>.playback.toml` | Already the one place a reading is written. Each reading that corresponds to an estimate gains an `estimate_error` table: the estimate datum, the estimated value, and the difference. |

The test asserts that every such reading has its `estimate_error` and that the recorded estimated
value is what the analysis produces. It does not assert the size of the difference (FR-037,
SC-014).

## What it must never do

- Publish an estimate under a name, a label or a wording that reads as a count of units lost.
- Let a reconstructed value, a settlement or a rule cite an estimate.
- Refuse a document because an estimate broke a bound.
