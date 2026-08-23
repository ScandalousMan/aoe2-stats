# Contract: replay extraction and the published analysis

Two things: the Protocol an engine implements, and the shape of what gets published. They are
separate on purpose — the Protocol is what constitution V lets us swap, the published shape is what
FR-041 lets us recompute, and neither may leak the other's vocabulary.

## The Protocol

`packages/core/src/aoe2stats_core/replay/analysis.py`. Beside the existing `ReplayValidator`, in the
package the API imports, and holding **no engine import** — the same discipline 001 established and
for the same reason (constitution V).

```python
class ReplayExtractor(Protocol):
    def extract(self, zip_bytes: bytes) -> MatchTimeline: ...
```

`extract` performs the same well-formedness checks `validate` already performs before an engine sees
a byte — one member, the expected inner filename, a bounded chunked read against a hard ceiling — and
raises the same `MalformedArchiveError` and `EngineParseError`. It does not re-implement them: the
existing `_well_formed_member`/`_read_bounded` path in `packages/replay-engine` is shared, because
two copies of an extraction-safety check is one copy that will fall behind.

`aoe2rec-py` implements it in `packages/replay-engine/src/aoe2stats_replay_engine/aoe2rec.py`, beside
the validator that already loads the same engine. `aoc-mgz` may implement it later without any caller
learning about it — which is the property being bought, and the reason the `Build` decoder R4
describes lives on this side of the Protocol rather than in `apps/analyzer`.

### Memory is part of the contract

R3 measured ~631 MB resident for a 6.9 MB 1v1 against a 2 GB ceiling, because the engine materialises
every operation. `extract` therefore reduces as it goes and never returns the operation stream, and
an implementation that hands back the raw operations for a caller to walk is a wrong implementation
of this Protocol even though it type-checks.

`extract` raises `EngineParseError` on a recording it cannot process, and the caller quarantines with
the full error (FR-036, constitution V). It does not retry: a parse is deterministic, so a second
attempt is a second identical failure that costs another fetch.

## `MatchTimeline`

Engine-independent, identifier-based, and deliberately narrower than FR-043 asks for — R1 records
what was measured and why two of FR-043's clauses describe facts the artifact does not contain.

```python
@dataclass(frozen=True)
class MatchTimeline:
    engine_name: str
    engine_version: str
    point_of_view_profile_id: int
    world_time_ms: int                      # the PostGame WorldTime block: the match clock's end
    participants: Sequence[ParticipantTimeline]

@dataclass(frozen=True)
class ParticipantTimeline:
    profile_id: int
    player_number: int
    civ_id: int
    resolved_team_id: int
    builds: Sequence[BuildEvent]            # building_id + world_time_ms, in order
    trainings: Sequence[TrainingEvent]      # unit_id + amount + building_id + world_time_ms
    researches: Sequence[ResearchEvent]     # technology_id + world_time_ms, first occurrence only
    age_up_commands: Mapping[int, int]      # technology_id 101/102/103 -> world_time_ms
    villagers_ordered: int                  # training orders net of observed cancellations
    actions: int
    actions_per_minute: float
    resigned_at_ms: int | None
```

### Every name in there is load-bearing

- **`age_up_commands`, not `age_up_times`.** R5: a `Research` command is an order, not an arrival.
  The age is reached when the research completes, which needs a technology-duration table this
  repository does not hold. "Ordered Feudal Age at 6:41" is a fact; "reached Feudal Age at 6:41" is
  false by about two minutes, in the direction that flatters the player.
- **First occurrence only.** A double-click issues the same research command twice, 208 ms apart, and
  it is in the reference replay — a naive reading reports five age-ups in a two-player game.
- **`villagers_ordered`, not `villagers`.** FR-043b. This counts *commands*: `DeQueue` of unit 83,
  less the `Unqueue` cancellations the stream carries. It is not a population. A villager exists one
  training duration later, that duration varies by civilisation and game speed, and a villager lost to
  a raid produces no command from its owner. Naming it `villagers_trained` — or worse, `villagers` —
  is the misreading FR-043b exists to make impossible, and it is one refactor away at all times.
- **`technology_id`, `unit_id`, `building_id` — identifiers, not names.** R13 and FR-043a. Where
  reference data can name one it is named at the presentation boundary; where it cannot, the
  identifier is shown. Storing names here would freeze a guess into the published artifact, which is
  the one thing 002 exists to prevent.
- **No resources, anywhere, and no reconstructed quantity of any kind.** FR-043b. A `.aoe2record` is
  a command log, not a state log. Resources and villager population are recoverable only by partial
  re-simulation, which is a separate feature built after this one (R1) — and when it lands it adds a
  new `schema_version` and recomputes from the retained recordings, reaching no source.
- **`profile_id` on every participant.** From `zheader.game_settings.players`, which is what joins the
  parse to `match_players` without inference (R2).

### What is not in it, and stays out

No judgment, no ranking, no grade, no score, no benchmark, no advice. FR-043 is explicit and this
contract is where the temptation actually arrives: an `opening` field, a `feudal_uptime` percentile,
an "idle TC" count are each one line away and each is a conclusion this feature cannot justify. A
richer analysis is a later feature with its own specification.

## The published analysis

Written to the object store, addressed by `match_analyses.result_key`, served by
`GET /api/matches/{game_id}/analysis`. It is `MatchTimeline` serialised, plus the provenance that
makes FR-041 mechanical:

```json
{ "schema_version": 1,
  "game_id": 500546441,
  "point_of_view_profile_id": 196240,
  "engine": { "name": "aoe2rec-py", "version": "0.1.21", "deps": {...} },
  "source_recording": { "object_key": "...", "sha256": "..." },
  "extracted_at": "2026-08-23T10:00:00Z",
  "participants": [ ... ] }
```

`schema_version` exists because this document will be wrong eventually. A published analysis that
cannot say which shape it is in cannot be migrated or compared, and R5 and R13 both describe work
that will change this shape when it lands.

`source_recording` is FR-041 made checkable rather than promised: it names the retained bytes and
their checksum, so recomputing an analysis after a parser upgrade is a read from this service's own
store with a verification, and needs nothing from a source that deleted its copy a year ago
(SC-009a). Verifying the checksum on retrieval is part of that path, not an optional extra — an
unverified re-read would publish a second unfalsifiable conclusion, which is the failure the whole
retention decision exists to avoid.

`engine.deps` mirrors `replay_parses.engine_deps` from 001. Recording the version alone is enough to
detect a change and not always enough to explain one.

## The golden fixture

The extraction of `tests/fixtures/replays/AgeIIDE_Replay_500546441.zip` is committed beside it as the
expected `MatchTimeline`.

It is the only replay this repository may rely on, and it is what makes a parser upgrade show up as a
diff rather than as a silence — the failure mode ADR-0001 was written about, where a game patch
silently broke parsing for months and nobody noticed because nothing was asserting the shape of the
answer. A version bump that changes one age-up time by 208 ms is exactly the kind of change that has
to be seen and explained rather than absorbed.
