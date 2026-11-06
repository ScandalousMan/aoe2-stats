# Contract — playback readings and golden reconstructions

**Covers**: FR-018, FR-019, FR-012, FR-026, SC-001, SC-009, SC-010 | **Model**:
[data-model.md](../data-model.md) §9, §10

## Three files, three roles

| File | Role | Written by |
| ---- | ---- | ---------- |
| `specs/008-match-reconstruction/owner-readings.md` | What to read, where and when in which recording, and why. Asks; holds no answer. | This feature's tasks |
| `tests/fixtures/replays/<recording>.playback.toml` | What was read. The one place each reading's value is written. | Transcribed from the owner's answer |
| `tests/fixtures/replays/<recording>.reconstruction.json` | The hand-built expected reconstruction (FR-018). | By hand, from orders and the knowledge base |

A value is never copied from the playback file into a golden or a rule. The golden carries the
reconstructed value; the test reads both and compares.

## What the tests assert

1. **Every golden reproduces.** The analysis of each committed recording yields its golden block,
   byte for byte.
2. **Every reading agrees** (SC-001, SC-010). For each reading whose quantity corresponds to a
   reconstructed datum, the reconstructed value equals the read value. A reading marked
   `unreadable` asserts nothing and is reported.
3. **Every rule carries what it settled** (SC-009). The test reports, per adopted rule, how many
   conditions it settled across the committed recordings and how many a proof settled instead, and
   the golden files record that table, so a rule that carries much is visible as a number.
4. **Readings are well-formed.** Every reading names a request in the owner-readings file, a build
   the fixtures README lists for that recording, a reader and a date.

## Units of time

The game shows match time as minutes and seconds; the stream counts milliseconds of match clock
(006 data-model §5). A reading is recorded as the game shows it and converted by the test to
the second the game would display, under the display rule (truncation or rounding) that the first
readings establish and the test states once. This is the game's resolution, not a tolerance: a
reconstructed time the game would display as a different second than the reading is a mismatch.

## Owner-reading requests

Each request names: the recording, the participant, the match time to pause at, what to select, the
exact value to read, and which rule or golden it checks. A request that cannot be answered in the
game is answered `unreadable` with where it was looked for, and its consumer stays a candidate.
