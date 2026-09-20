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
| `unit-queued`         | observed   | unit id, building type, producing building object, count    | yes          |
| `unit-unqueued`       | observed   | unit id, count                                              | yes          |
| `research-queued`     | observed   | technology id, researching building object                  | yes          |
| `units-commanded`     | observed   | command class, unit object ids, optional target             | yes          |
| `market-transaction`  | decoded    | direction, resource, amount                                 | yes — needs a decoder |
| `object-deleted`      | decoded    | object id                                                   | yes — needs a decoder |
| `chat`                | decoded    | channel — **not the text**                                  | yes — needs a decoder |
| `participant-resigned`| observed   | —                                                           | yes          |
| `match-ended`         | observed   | final match-clock time                                      | yes          |
| `undecoded`           | observed   | opaque operation label, payload length                      | yes          |
| `starting-attributes` | decoded    | per-participant attribute values                            | **declared only** |
| `starting-object`     | decoded    | object id, class, position, owner                           | **declared only** |

**Two additions, each forced by the timeline golden (T628).** `unit-queued` carries the building
*type* beside the building object: the old timeline publishes each training's building type (a Town
Center is 109) and an object id cannot recover it; both are game concepts, not engine-shaped fields.
`unit-unqueued` (unit id, count) is the cancellation counterpart, which the old extractor netted
against `villagers_ordered`; it is emitted only for a top-level cancellation action whose payload
carries both an integer unit id and an integer amount, and any other shape stays `undecoded`, so
nothing is read from a payload whose layout no recording has shown. A command naming several
producing buildings is still one event carrying the first: the timeline never read a building object,
so nothing it published is lost, and the one-event-per-operation accounting is unchanged.

**`building-placed` is `decoded`**, not observed: the building identifier is read from a payload by
this repository's own decoder. The participant on the same event comes from a named field and would
be observed alone; the event takes the weaker tier, which is the weakest-input rule applied to an
event.

**Three kinds are decoded, and the wheel does not decode them.** Sell, buy and delete arrive as raw
byte payloads; each gets a small decoder of the placement decoder's kind, derived empirically and
golden-tested over every committed recording (FR-014). `units-commanded` carries unit ids for move,
interact and order only — the other command kinds arrive undecoded and are emitted with an empty id
list, never a guessed one.

**`chat` carries no text.** The channel sits inside the same JSON string as the message, so the text
cannot be avoided on the way to it; the rule is that it is discarded at the adapter and appears in no
event, no golden file and no log. The text is personal data this feature has no use for.

**The two declared-only kinds** satisfy FR-020: their types exist, the register marks their data
`blocked`, and a test asserts the adapter emits neither — so the day a producer lands, that test is
what changes, and no type does.

## Adapter obligations

1. **One pass, no copy, nothing retained past the fold** (FR-021). `events` is a generator over the
   operations the wheel has already materialised — that materialisation is the wheel's cost and is
   not removable here. The input-size refusal applies to this entry point as to the old one, **and a
   peak-memory measurement over every committed recording is added**, because the refusal test
   measures no consumption.
2. **First-occurrence collapse, idempotent kinds only** (FR-018). Research, age-up and resignation,
   over the whole match, no window — what the extractor does today. Queueing, placement and movement
   never collapse. SC-010 is asserted on the doubled age-up command.
3. **No silent drop** (FR-019). Any **action** the adapter does not map becomes `undecoded`. Sync is
   consumed for the clock; view-lock is a camera position and is excluded because it carries no
   intent. A test asserts that **every operation is an emitted event or is counted in a named
   category** — sync, view-lock, collapsed by obligation 2, attributed after an exit by obligation
   4, or naming no seated participant — so a new way to lose an operation has to be named to pass.
   `match-started` comes from the header and corresponds to no operation; it sits outside the
   count. The second recording carries an action kind the wheel itself cannot name, so
   this rule has a live instance.
4. **Exit discipline.** No event is attributed to a participant after their `participant-resigned`.
5. **No participant timeline for an observer or an empty slot** — they are absent from
   `match-started`, not present and silent.
6. **Dependencies populated.** `engine_dependencies` is read from installed distribution metadata
   for the engine and each requirement it declares. Empty is a construction error.

## Engine independence (SC-009)

A test walks every payload type's field names and asserts none appears in a deny-list built from
the wheel's own output keys, and that no payload carries a raw byte sequence, an offset or a length
other than `undecoded`'s. The deny-list is generated from the parse of **every committed recording**
— the two expose different action kinds — so it tracks the wheel and is not maintained by hand.

## The proof that nothing was lost

The existing timeline extractor is re-expressed as a fold over `events`. The committed golden
timeline must come back **byte-identical**. This is the only available evidence that the canonical
stream carries everything the old path read, and it is available only in the phase that introduces
the stream — so that phase changes nothing else on that path.

A second golden file, the canonical stream for the fixture, is committed under the same
regeneration rules the fixtures README already states for the timeline.

## The group-silence observable (FR-013)

Computed in `packages/replay-engine`, from `units-commanded` events only.

- **Datum**: `participant.group_silence_episodes` — a set of unit objects commanded together repeatedly,
  then never named again before the participant's exit.
- **Tier**: `inferred`. Structurally published under the document's `inferred` block only.
- **Confidence**: level banded from how intensively the group was commanded before the silence and
  how long the silence lasted relative to the remaining match; `basis` states both figures for the
  instance. The bands live in the register entry's method.
- **Non-claim**, verbatim on every instance: the register entry's own `non_claim`. It is not
  restated here — a sentence quoted in two files is verbatim in one of them.
- **Blind spot, stated in the method.** Only move, interact and order carry decoded unit ids. Formation,
  stance, patrol and stop do not, so exactly the commands that park a military group are invisible,
  and a parked group reads as silent. This caps the level the banding may assign.
- It consumes no deletion and no market event, and is never summed with either (FR-014).
