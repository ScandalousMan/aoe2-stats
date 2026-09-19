# Phase 1 — Data model: Replay-analysis foundations

**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

Eight entities. Seven are pure values with no storage of their own; one is a table. Every closed
vocabulary below is closed in code — an enumeration, not a string — and a value outside it fails at
construction, not at review.

No measurement is stated here. Where an entity depends on a measured property of a recording or of
a source, it references `docs/data-sources.md` or [research.md](./research.md).

## 1. Truth tier

The closed, ordered set carried by every published value (FR-007, FR-008).

| Order | Tier            | Means                                                                 |
| ----- | --------------- | --------------------------------------------------------------------- |
| 1     | `observed`      | Read from a named field of the recording, unchanged.                  |
| 2     | `decoded`       | Extracted from a payload by this repository's own decoding.           |
| 3     | `reconstructed` | Produced by replaying game rules over observed and decoded inputs.    |
| 4     | `derived`       | Computed from reconstructed state.                                    |
| 5     | `inferred`      | An interpretation. Always carries a confidence.                       |
| 6     | `predicted`     | A statement about what was expected. Always carries a confidence.     |

**Rules.**

- **Weakest input.** A value's tier is never stronger than the weakest tier among its inputs
  (FR-008). The combinator that builds a provenance from inputs computes this; a caller cannot
  assert a stronger one.
- `non-determinable` is **not a tier**. It is a register classification: nothing is ever published
  at it, so no value can carry it (FR-001 lists seven classifications, FR-008 six tiers, and the
  difference is this).
- Tiers 3, 4 and 6 have no producer in this feature. They exist now so that the vocabulary does not
  change when 007 arrives.

## 2. Confidence

Attached to every value at `inferred` or `predicted`, and to nothing else (FR-010, FR-010a).

| Field   | Type                          | Rule                                                                     |
| ------- | ----------------------------- | ------------------------------------------------------------------------ |
| `level` | closed, ordered: `low` < `medium` < `high` | Never a number. A numeric probability is rejected by the type. |
| `basis` | non-empty text                | The evidence that placed the value at this level, stated so a reader can check it. An empty or whitespace basis fails construction. |

A confidence on a value at tier 1 to 4 is an error, not a harmless extra: it would suggest doubt
where the method admits none.

## 3. Provenance

What produced one value (FR-009).

| Field        | Type                         | Rule                                                                 |
| ------------ | ---------------------------- | -------------------------------------------------------------------- |
| `datum`      | register datum id            | Must resolve to a register entry (FR-006).                           |
| `tier`       | Truth tier                   | Must equal the entry's tier, and obey the weakest-input rule.        |
| `method`     | method id + version          | Names the algorithm in a form a reader can recompute (FR-009).       |
| `inputs`     | list of datum ids            | Empty only at `observed`.                                            |
| `confidence` | Confidence, optional         | Required at tiers 5 and 6, forbidden elsewhere.                      |
| `non_claim`  | text, optional               | Required where the register entry declares one (FR-013).             |

## 4. Determinability entry

One record of `packages/core/src/aoe2stats_core/truth/register.toml` (FR-001 to FR-006a). Schema and
gate in [contracts/register.md](./contracts/register.md).

| Field                | Rule                                                                                   |
| -------------------- | -------------------------------------------------------------------------------------- |
| `id`                 | Unique, stable, dotted. States what was measured, never what it is hoped to mean (FR-012). |
| `classification`     | One of the six tiers, or `non-determinable`.                                           |
| `status`             | `published`, `planned` (a later feature publishes it), or `blocked`.                   |
| `source`             | The recording field, payload or upstream datum it comes from.                          |
| `method`             | The decoding or algorithm.                                                             |
| `requires_knowledge` | List of knowledge field references; drives gap severity (research D7).                 |
| `depends_on`         | Other datum ids. The graph must be acyclic.                                            |
| `validation`         | How it is checked — a test id or a named procedure.                                    |
| `evidence`           | Reference into `docs/data-sources.md` or a research record. Never a restated number.   |
| `blocked_on`         | Required when `status` is `blocked`: the named dependency (FR-005).                    |
| `non_claim`          | Required for the group-silence datum (FR-013); optional elsewhere.                     |

Only when `classification` is `non-determinable`, and then all four are mandatory (FR-003):

| Field                      | Rule                                                        |
| -------------------------- | ----------------------------------------------------------- |
| `reason`                   | Why it cannot be known.                                     |
| `impact`                   | What it costs the analytics that wanted it.                 |
| `approximation`            | Whether one exists, and what it is.                         |
| `approximation_acceptable` | `yes` or `no`. There is no third value and no omission.     |
| `would_change_if`          | The condition that would change the answer (FR-004).        |

**State.** `blocked` to `planned` to `published`, forward only, each move made by the change that
earns it. The starting-state data enter as `blocked`, with `blocked_on` naming the decoder research
D1 describes — not `non-determinable`, which research D1 showed to be the wrong claim.

## 5. Canonical event

One engine-independent occurrence (FR-015 to FR-020). Vocabulary in
[contracts/canonical-events.md](./contracts/canonical-events.md).

| Field         | Type                       | Rule                                                                  |
| ------------- | -------------------------- | --------------------------------------------------------------------- |
| `clock_ms`    | integer                    | Match clock, from the recording's own sync, never wall time.          |
| `participant` | participant slot, optional | Absent only for match-level events. Never an observer or empty slot.  |
| `kind`        | closed enumeration         | See the contract. Includes `undecoded`.                               |
| `tier`        | Truth tier                 | `observed` or `decoded` for everything this feature's adapter emits.  |
| `payload`     | one typed record per kind  | No field named, shaped or offset after an engine's output (FR-017).   |

**Rules.** A repeated command collapses to its first occurrence, keyed per kind (FR-018). Nothing is
attributed to a participant after their exit. An unfinished production is never emitted as complete.
Kinds that need the starting state are **declared and unproduced**, so adding their producer later
changes no type (FR-020).

## 6. Knowledge snapshot

One immutable body of rules (FR-022 to FR-028, FR-034). Surface in
[contracts/knowledge-base.md](./contracts/knowledge-base.md).

| Field           | Rule                                                                                      |
| --------------- | ----------------------------------------------------------------------------------------- |
| `source`        | Pack name.                                                                                |
| `source_version`| The pack's own revision — a commit, since the source publishes nothing else.              |
| `describes_build` | The game build the snapshot speaks for. **Distinct from** the build the source revision implemented (research D4). |
| `digest`        | Over the snapshot's canonical content. Verified on load; a mismatch refuses to load.      |
| `validation`    | What was checked, against what, by whom, when (FR-030). Includes any carry-forward attestation, build by build. |
| `civilisations_modelled` | The civilisations whose effects are modelled. All others refuse qualified queries (research D5). |

Identity is the first four fields together (FR-024). A snapshot directory is written once and never
edited (FR-025); a correction is a new snapshot.

**Civilisation effect** — one hand-transcribed bonus.

| Field          | Rule                                                                                  |
| -------------- | ------------------------------------------------------------------------------------- |
| `civilisation` | Identifier.                                                                           |
| `source_text`  | The verbatim sentence from the vendored strings, and its key.                         |
| `modelled`     | `yes` or `no`. `no` requires `reason`, and keeps the touched fields gapped.           |
| `selector`     | Which entities it touches — by explicit identifier list, never by a fuzzy class name. |
| `field`        | Which knowledge field it modifies.                                                    |
| `operation`    | Closed: `multiply`, `add`, `set`.                                                     |
| `operand`      | The amount, per resource where the field is a cost.                                   |
| `validated_by` | The second reading that confirmed it (FR-030).                                        |

**Source disagreement** (FR-028) — entity, field, build, each source's value, which one was stored,
and why.

## 7. Knowledge gap

One absent required field (FR-035 to FR-039).

| Field          | Rule                                                                                   |
| -------------- | -------------------------------------------------------------------------------------- |
| `entity`       | Kind and identifier.                                                                   |
| `field`        | The knowledge field that was asked for.                                                |
| `build`        | The recording's game build.                                                            |
| `civilisation` | The civilisation the query was qualified by, where it was.                             |
| `cause`        | Closed: `no-snapshot-for-build`, `entity-absent`, `field-absent`, `civilisation-not-modelled`, `effect-not-modelled`. |
| `prevents`     | The register data that need this field, by id — what the gap stops, not that it exists (FR-036). Computed. |
| `severity`     | `blocking` or `informational`. **Computed** from `prevents`: blocking when it is non-empty (research D7). Never supplied by a caller. |

A query that cannot answer returns a gap **in place of** a value. The return type has no third
branch, which is how SC-008's "by construction" is met: there is no code path on which a default
could be produced.

**Persistence** — `analysis_knowledge_gaps`, the feature's one table, for FR-039's aggregate report.

| Column            | Type        | Note                                                      |
| ----------------- | ----------- | --------------------------------------------------------- |
| `id`              | bigint, PK  |                                                           |
| `game_id`         | bigint, FK to `matches` | Indexed.                                      |
| `identity_digest` | text        | Which analysis recorded it.                               |
| `build`           | integer     | Indexed with `cause` — the per-patch rate is this query.  |
| `entity_kind`, `entity_id`, `field`, `civilisation_id` | | `civilisation_id` nullable.     |
| `cause`, `severity` | enumerations |                                                         |
| `recorded_at`     | timestamptz |                                                           |

Unique on (`identity_digest`, `entity_kind`, `entity_id`, `field`, `civilisation_id`), so a
reproduced analysis records nothing twice. It holds no personal data: a participant is not a column.

## 8. Analysis identity

The tuple that makes a published analysis reproducible (FR-040 to FR-044). Document shape in
[contracts/analysis-document.md](./contracts/analysis-document.md).

| Component                  | Source                                                                       |
| -------------------------- | ---------------------------------------------------------------------------- |
| `recording`                | Object key and checksum of the retained bytes (003's `source_recording`).    |
| `parser`                   | Name and version from the adapter.                                           |
| `parser_dependencies`      | Installed distribution versions of the engine's declared requirements. **Non-empty, or validation fails** (FR-044). |
| `knowledge`                | The snapshot identity, or an explicit record that no snapshot matched the build. |
| `reconstruction_engine`    | `not-applicable` until 007. Present from the start so the tuple never changes shape. |
| `analytics`                | This feature's own version for the coverage pass and the group-silence method. |

`digest` is computed over the canonical serialisation of the six. The published object's key carries
it; `match_analyses.result_key` names the current one; earlier objects are never deleted (research
D9). The wall-clock extraction time is **outside** the identity and outside the compared body.
