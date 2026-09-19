# Contract — canonical events

**Covers**: FR-013 to FR-021, SC-009, SC-010 | **Model**: [data-model.md](../data-model.md) §5 |
**Research**: D10

## The seam

```text
packages/core      aoe2stats_core.replay.events     the vocabulary + CanonicalEventSource protocol
packages/replay-engine  aoe2stats_replay_engine.canonical   the one implementation
```

```python
class CanonicalEventSource(Protocol):
    engine_name: str
    engine_version: str
    engine_dependencies: Mapping[str, str]          # non-empty — FR-044

    def events(self, zip_bytes: bytes) -> Iterator[CanonicalEvent]: ...
```

Everything above the adapter imports `aoe2stats_core.replay.events` and nothing else (FR-015). The
pinned wheel is imported in `packages/replay-engine` only, as today.

## The vocabulary

Closed. Each kind has one typed payload. Tier is per kind and fixed.

| Kind                  | Tier       | Payload                                                     | Produced now |
| --------------------- | ---------- | ----------------------------------------------------------- | ------------ |
| `match-started`       | observed   | build, map, lobby presets, participants and their civilisations | yes      |
| `building-placed`     | decoded    | building id, position                                       | yes          |
| `unit-queued`         | observed   | unit id, producing building object, count                   | yes          |
| `research-queued`     | observed   | technology id, researching building object                  | yes          |
| `units-commanded`     | observed   | command class, unit object ids, optional target             | yes          |
| `market-transaction`  | observed   | direction, resource, amount                                 | yes          |
| `object-deleted`      | observed   | object id                                                   | yes          |
| `chat`                | observed   | channel — **not the text**                                  | yes          |
| `participant-resigned`| observed   | —                                                           | yes          |
| `match-ended`         | observed   | final match-clock time                                      | yes          |
| `undecoded`           | observed   | opaque operation label, payload length                      | yes          |
| `starting-attributes` | decoded    | per-participant attribute values                            | **declared only** |
| `starting-object`     | decoded    | object id, class, position, owner                           | **declared only** |

**`building-placed` is `decoded`**, not observed: the building identifier is read from a payload by
this repository's own decoder. The participant on the same event comes from a named field and would
be observed alone; the event takes the weaker tier, which is the weakest-input rule applied to an
event.

**`chat` carries no text.** The text is personal data this feature has no use for, and its absence
here keeps principle IX out of the vocabulary entirely.

**The two declared-only kinds** satisfy FR-020: their types exist, the register marks their data
`blocked`, and a test asserts the adapter emits neither — so the day a producer lands, that test is
what changes, and no type does.

## Adapter obligations

1. **One pass, nothing retained** (FR-021). `events` is a generator over the wheel's operations. The
   existing memory-ceiling test is extended to this entry point and must hold at the same bound.
2. **First-occurrence collapse** (FR-018). Per kind, keyed on the fields that identify one player
   action; the window and keys are the ones the `replay-parsing` skill already mandates. SC-010 is
   asserted on the fixture's doubled age-up command.
3. **No silent drop** (FR-019). Any operation the adapter does not map becomes `undecoded`. A test
   asserts that the count of emitted events plus the count of operation kinds deliberately excluded
   — sync and view-lock, which are consumed for the clock and carry no intent — equals the
   operation count the wheel reports.
4. **Exit discipline.** No event is attributed to a participant after their `participant-resigned`.
5. **No participant timeline for an observer or an empty slot** — they are absent from
   `match-started`, not present and silent.
6. **Dependencies populated.** `engine_dependencies` is read from installed distribution metadata
   for the engine and each requirement it declares. Empty is a construction error.

## Engine independence (SC-009)

A test walks every payload type's field names and asserts none appears in a deny-list built from
the wheel's own output keys, and that no payload carries a raw byte sequence, an offset or a length
other than `undecoded`'s. The deny-list is generated from the fixture's parse, so it tracks the
wheel and is not maintained by hand.

## The proof that nothing was lost

The existing timeline extractor is re-expressed as a fold over `events`. The committed golden
timeline must come back **byte-identical**. This is the only available evidence that the canonical
stream carries everything the old path read, and it is available only in the phase that introduces
the stream — so that phase changes nothing else on that path.

A second golden file, the canonical stream for the fixture, is committed under the same
regeneration rules the fixtures README already states for the timeline.

## The group-silence observable (FR-013)

Computed in `packages/replay-engine`, from `units-commanded` events only.

- **Datum**: `participant.group_control_lost` — a set of unit objects commanded together repeatedly,
  then never named again before the participant's exit.
- **Tier**: `inferred`. Structurally published under the document's `inferred` block only.
- **Confidence**: level banded from how intensively the group was commanded before the silence and
  how long the silence lasted relative to the remaining match; `basis` states both figures for the
  instance. The bands live in the register entry's method.
- **Non-claim**, verbatim on every instance: *not a casualty count — a group can fall silent
  because it was garrisoned, left idle or simply not re-selected*.
- It consumes no deletion and no market event, and is never summed with either (FR-014).
