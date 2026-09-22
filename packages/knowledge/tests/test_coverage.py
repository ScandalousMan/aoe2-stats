"""T649: the coverage pass over a canonical stream. Written before `coverage.py` (T648) existed;
T648 has since implemented it, `test_removing_a_required_field_withholds_only_its_dependent_values`
(SC-007) genuinely passes and its marker is removed, and
`test_each_committed_recording_reports_zero_blocking_gaps` (SC-007a) is parametrized per recording:
the first committed recording (Byzantines/Koreans) genuinely passes, asserting its blocking gaps
equal the empty set, since a remediation of T648's hand-back (2026-09-20) found and corrected a real
misclassification in `effects.toml` — Koreans' "Archer armor and tower upgrades free" is
unconditional, not conditional-on-state (see `effects.toml`'s own `validated_by` on that entry for
the evidence). The second committed recording's own case genuinely passes too (T652c): it asserts
its blocking gaps equal `_RECORDING_2_ENUMERATED_BLOCKING_GAPS`, FR-022b's closed, three-blocker
enumeration below, replacing a blanket `xfail(strict=True, reason=...)` a remediation of T648's
hand-back found insufficient — a `reason=` string asserts against nothing, and closing one of the
three blockers left the assertion failing with the marker still holding, silencing exactly the
signal FR-022b exists to keep. Set equality catches both directions: a closed blocker leaves an
enumerated tuple unmatched, and a fourth blocker (a real transcription defect) leaves an observed
tuple unmatched.

Contract: [contracts/knowledge-base.md](../../../specs/006-replay-analysis-foundations/contracts/
knowledge-base.md), "Gaps" — "The coverage pass (`coverage.py`) takes a canonical stream, collects
every entity and every participant civilisation, and asks for every field any register datum
requires. Its output is the gap list the document publishes." Research:
[research.md](../../../specs/006-replay-analysis-foundations/research.md) **D7** (severity is
computed from the register, not assigned by hand — exercised indirectly here through `gaps.py`,
which T647 already proved; this file only checks that a real, missing field produces a real gap).
Data model: [data-model.md](../../../specs/006-replay-analysis-foundations/data-model.md) §7
("Knowledge gap").

Every test below imports `aoe2stats_knowledge.coverage` **inside its own body**, never at module
scope — a module-scope import of a module that did not exist yet, when this file was written before
T648, would have been a collection error that took the whole workspace suite down with it
(`implementer-dispatch` skill); kept that way now that `coverage.py` exists, both for consistency
and because it costs nothing. No test in this file carries an `xfail` marker any more (T652c
removed the last one): every case is a genuine, unconditional pass, including recording 2's, whose
own set-equality assertion against FR-022b's enumeration is what now catches a stale entry or a
new, unenumerated blocker.

**Field vocabulary.** `register.toml`'s real `requires_knowledge` values are `cost`,
`production_time`, `produced_at`, `age_requirement`, `prerequisites`, `available_to` and
`line_of_sight`. `line_of_sight` belongs to a different reconstruction domain (map control /
exploration, blocked on the unread starting state — feature 007's territory, research.md D1) and is
not one of `query.py`'s six query-surface fields (`cost`, `production_time`, `age_requirement`,
`prerequisites`, `produced_at`, `available_to`). The coverage pass over *this* package's knowledge
base only asks the latter six; a `line_of_sight` gap is `gaps.py`'s own concern (already proven by
`test_gaps.py`), not this module's.

**The signature this file designs `coverage.py` (T648) against, and why.** The contract only fixes
`coverage.py`'s *behaviour* ("takes a canonical stream ... asks for every field any register datum
requires ... output is the gap list"), not its exact parameter list, and this task is explicitly
allowed to "design this test at the level of what `coverage.py`'s signature SHOULD support". The
shape this file assumes:

    def coverage(
        events: Iterable[CanonicalEvent],
        *,
        civilisation_names: Mapping[int, str] | None = None,
        rules_overrides: Mapping[int, Mapping[str, Any]] | None = None,
    ) -> Sequence[gaps.KnowledgeGap]: ...

- `events` is the real, engine-independent canonical stream (`aoe2stats_core.replay.events.
  CanonicalEvent`) — never the wheel's own output (FR-015), and never the JSON the goldens
  serialise to (that JSON is a test-only convenience for this package, which — per
  `test_normalise.py`'s own docstring — depends on `aoe2stats-core` only, never on
  `aoe2stats-replay-engine`; see `_load_golden_stream` below).
- `civilisation_names` is the seam this task adds for testability. A `match-started` participant
  carries only the game's raw integer civilisation identifier (T629a: "naming is the knowledge
  base's job, not the adapter's"), so `coverage.py` must translate that integer into one of the
  pack's own civilisation-name strings (`"Byzantines"`, ...) before it can call `query.cost` and
  its siblings, which require a name (FR-023). That translation table is real research T648 owes —
  the same kind of measurement T645 already did once, matching an unfamiliar recording's trained
  and researched entity ids against `data.json`'s per-civilisation tables to identify which of the
  six modelled civilisations it actually plays, since no vendored file carries the replay header's
  raw numeric id at all (verified directly: `packages/knowledge/packs/aoe2techtree/data.json`'s
  civ entries carry no numeric id in any form, and neither does the DE replay header decode one
  from a name). **SC-007a**, below, asks `coverage.coverage` to do exactly that translation for
  real, over both committed recordings, with no override — proving T648's own research is right is
  what makes that test meaningful. The **SC-007** synthetic test, which needs one specific,
  already-known-modelled civilisation attached to one specific, arbitrary participant, uses the
  override instead of leaning on that real research, so this file does not have to duplicate T648's
  measurement to become collectible.
- `rules_overrides`, keyed by game build, is the other seam the task text names directly — "an
  optional injected/overridden Snapshot or rules mapping". A `Snapshot` (`snapshot.py`) does not
  carry its own parsed `rules.json` body (`query.py`'s own docstring: "`Snapshot` does not carry
  the parsed rules body itself as of this task"), so overriding at the level of the parsed rules
  mapping — the same shape `query.py`'s private `_rules(directory)` already returns — is the
  narrowest seam that lets **SC-007** delete one field from an in-memory copy of a real, committed
  snapshot without touching the packaged fixture on disk (FR-025: a snapshot directory is never
  modified) and without `coverage.py` inventing a second, parallel snapshot-construction path.

Both seams are keyword-only and optional, defaulting to "use the real production table / the real
packaged snapshot" — a production caller never has to know either exists.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

import pytest

from aoe2stats_core.replay.events import (
    BuildingPlacedPayload,
    CanonicalEvent,
    ChatPayload,
    EventKind,
    MarketTransactionPayload,
    MatchEndedPayload,
    MatchStartedPayload,
    ObjectDeletedPayload,
    ParticipantEntry,
    Position,
    ResearchQueuedPayload,
    UndecodedPayload,
    UnitQueuedPayload,
    UnitsCommandedPayload,
    UnitUnqueuedPayload,
)

#: The package this module's packaged snapshot data is anchored to (same anchor `snapshot.py` and
#: `query.py` use) — read directly here only to build **SC-007**'s in-memory, mutated copy, never
#: to bypass `snapshot_for`'s own resolution for a real query.
_PACKAGE = "aoe2stats_knowledge"

#: Both committed recordings report this build (`match-started.build`, verified directly against
#: both golden streams below), which `aoe2techtree-180059` describes with all six
#: modelled civilisations (T645).
_BUILD = 180059

_PROMOTED_DIRECTORY = "aoe2techtree-180059"

_FIXTURES_ROOT = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "replays"

#: The two committed recordings' golden canonical streams (`packages/replay-engine/tests/
#: test_canonical_golden.py` verifies these equal the live parse of the committed `.aoe2record`
#: zips). Read directly as JSON and deserialised into real `CanonicalEvent` values below, rather
#: than by importing `aoe2stats_replay_engine` and parsing the zip: this package depends on
#: `aoe2stats-core` only (`test_normalise.py`'s own docstring; `pyproject.toml`), and the replay
#: engine is the adapter FR-015 keeps behind the canonical-event seam.
_GOLDEN_CANONICAL_STREAMS = (
    _FIXTURES_ROOT / "AgeIIDE_Replay_500546441.canonical.json",
    _FIXTURES_ROOT / "AgeIIDE_Replay_504695319.canonical.json",
)


# ------------------------------------------------------------------ golden JSON -> CanonicalEvent
#
# `canonical_golden.py`'s `serialise` writes one event per line as
# `{"clock_ms", "kind", "participant", "payload"}`, with `payload` being `dataclasses.asdict(...)`
# of whichever `Payload` subtype the kind carries (or `None`). This is the exact inverse: dispatch
# on `kind` and reconstruct the matching dataclass, so `coverage.coverage` receives the same typed
# values a real `CanonicalEventSource` would hand it, not a bag of JSON dicts.


def _target_from_json(raw: Any) -> int | Position | None:
    if raw is None or isinstance(raw, int):
        return raw
    return Position(x=raw["x"], y=raw["y"])


def _payload_from_json(kind: EventKind, raw: Mapping[str, Any] | None) -> Any:
    if raw is None:
        return None
    if kind is EventKind.MATCH_STARTED:
        return MatchStartedPayload(
            build=raw["build"],
            map_name=raw["map_name"],
            lobby_presets=dict(raw["lobby_presets"]),
            participants=tuple(
                ParticipantEntry(slot=p["slot"], civilisation=p["civilisation"])
                for p in raw["participants"]
            ),
        )
    if kind is EventKind.BUILDING_PLACED:
        return BuildingPlacedPayload(
            building_id=raw["building_id"], position=Position(**raw["position"])
        )
    if kind is EventKind.UNIT_QUEUED:
        return UnitQueuedPayload(**raw)
    if kind is EventKind.UNIT_UNQUEUED:
        return UnitUnqueuedPayload(**raw)
    if kind is EventKind.RESEARCH_QUEUED:
        return ResearchQueuedPayload(**raw)
    if kind is EventKind.UNITS_COMMANDED:
        return UnitsCommandedPayload(
            command_class=raw["command_class"],
            unit_objects=tuple(raw.get("unit_objects", ())),
            target=_target_from_json(raw.get("target")),
        )
    if kind is EventKind.MARKET_TRANSACTION:
        return MarketTransactionPayload(**raw)
    if kind is EventKind.OBJECT_DELETED:
        return ObjectDeletedPayload(**raw)
    if kind is EventKind.CHAT:
        return ChatPayload(**raw)
    if kind is EventKind.MATCH_ENDED:
        return MatchEndedPayload(**raw)
    if kind is EventKind.UNDECODED:
        return UndecodedPayload(**raw)
    raise AssertionError(  # pragma: no cover - both goldens are exhaustively covered above
        f"golden fixture carries an event kind this deserialiser does not know: {kind!r}"
    )


def _event_from_json(raw: Mapping[str, Any]) -> CanonicalEvent:
    kind = EventKind(raw["kind"])
    return CanonicalEvent(
        clock_ms=raw["clock_ms"],
        kind=kind,
        participant=raw["participant"],
        payload=_payload_from_json(kind, raw["payload"]),
    )


def _load_golden_stream(path: Path) -> list[CanonicalEvent]:
    document = json.loads(path.read_text(encoding="utf-8"))
    return [_event_from_json(raw) for raw in document["events"]]


def _real_rules_for(directory: str) -> dict[str, Any]:
    """The packaged `rules.json` for one committed snapshot directory, read the same way
    `query.py`'s private `_rules` does (`importlib.resources`, never a bare filesystem path) —
    used only to build **SC-007**'s in-memory, mutated copy; the packaged file itself is never
    written to (FR-025)."""
    root = resources.files(_PACKAGE).joinpath("snapshots").joinpath(directory)
    parsed: dict[str, Any] = json.loads(root.joinpath("rules.json").read_text(encoding="utf-8"))
    return parsed


# ------------------------------------------------------------------------------------- SC-007a


#: T652c: **FR-022b**'s enumeration, replacing the blanket `_RECORDING_2_XFAIL_REASON` marker a
#: remediation of T648's hand-back (2026-09-20) confirmed named three real, permanent-for-this-
#: feature reasons rather than "T648 not implemented yet". FR-022b requires "one entry per
#: blocker, naming the entity or effect, why the single vendored source cannot close it, and the
#: condition that would" — data, not prose a marker's `reason=` asserts against nothing.
#:
#: `gap_tuples` on each blocker is every `(entity_kind, entity_id, field, civilisation, cause)`
#: observed on recording 2 that the blocker accounts for; the module-level set below flattens all
#: three for the equality assertion the test makes.
@dataclass(frozen=True, slots=True)
class _RecordingTwoBlocker:
    """One of FR-022b's enumerated blockers standing between recording 2 and SC-007a's zero-
    blocking-gaps claim."""

    name: str
    why_the_vendored_source_cannot_close_it: str
    what_would_close_it: str
    gap_tuples: tuple[tuple[str, str, str, str, str], ...]


#: **Franks' "Castles cost -15/25% in Castle/Imperial Age"** (building 82, the Castle the Franks
#: participant trains Throwing Axemen from) is genuinely age-scaled: its magnitude depends on
#: which age the Castle was built in, and this static, per-build knowledge base's query surface
#: (`query.py`'s six functions) carries no "current age"/match-state argument at all — an
#: architecture question (the effect model's own signature), not a fixable transcription. **1
#: tuple.**
_FRANKS_CASTLE_COST_IS_AGE_SCALED = _RecordingTwoBlocker(
    name="Franks' Castle cost discount is age-scaled (building 82)",
    why_the_vendored_source_cannot_close_it=(
        "'Castles cost -15/25% in Castle/Imperial Age' depends on which age the Castle was "
        "built in, and query.py's six query-surface functions carry no age/match-state "
        "argument to resolve that against — an architecture question, not a transcription fix."
    ),
    what_would_close_it=(
        "adding an age/match-state argument to query.py's query surface, an architecture "
        "change out of scope for this feature."
    ),
    gap_tuples=(("building", "82", "cost", "Franks", "effect-not-modelled"),),
)

#: **Gurjaras' Team Bonus "Camel and Elephant Units train +25% faster"** (units 1755, 239) is, by
#: the pack's own text, a **Team Bonus** — granted to every allied player from a Gurjaras ally,
#: not only to Gurjaras-controlled units — so it is correctly excluded from this civilisation-
#: scoped effect model, exactly like every other team bonus this feature has ever modelled
#: (`effects.toml`'s own "Team Bonus:" entries throughout). **2 tuples.**
_GURJARAS_TRAINING_SPEED_BONUS_IS_A_TEAM_BONUS = _RecordingTwoBlocker(
    name="Gurjaras' camel/elephant training-speed bonus is a Team Bonus (units 1755, 239)",
    why_the_vendored_source_cannot_close_it=(
        "the pack's own text names it a Team Bonus, granted through an ally rather than to "
        "Gurjaras' own units, so it is correctly excluded from this civilisation-scoped effect "
        "model, the same as every other team bonus effects.toml records."
    ),
    what_would_close_it=(
        "the bonus being reclassified as non-team-wide by the vendored pack, which no evidence "
        "supports today."
    ),
    gap_tuples=(
        ("unit", "1755", "production_time", "Gurjaras", "effect-not-modelled"),
        ("unit", "239", "production_time", "Gurjaras", "effect-not-modelled"),
    ),
)

#: **Two building ids (490, 673)**, referenced by `building-placed` events in this recording, are
#: absent from the vendored `aoe2techtree` pack entirely — real, age-upgraded visual variants the
#: pack's tech-tree UI source never enumerates a second id for (`test_normalise.py`'s
#: `_BUILDING_IDS_ABSENT_FROM_THE_VENDORED_PACK`, first named by T640). A genuine third-party
#: source coverage hole, not a decoding or civilisation-assignment error; vendoring a second
#: source to close it is explicitly rejected by research.md D3 for this feature. Each id fails
#: all six of `query.py`'s query-surface fields, for the civilisation the recording actually
#: places it under — building 490 for Franks, 673 for Teutons. **12 tuples.**
_TWO_BUILDING_IDS_ARE_ABSENT_FROM_THE_VENDORED_PACK = _RecordingTwoBlocker(
    name="Buildings 490 and 673 are absent from the vendored aoe2techtree pack entirely",
    why_the_vendored_source_cannot_close_it=(
        "both ids are real, age-upgraded visual variants the pack's tech-tree UI source never "
        "enumerates a second id for (test_normalise.py's "
        "_BUILDING_IDS_ABSENT_FROM_THE_VENDORED_PACK, first found by T640); research.md D3 "
        "explicitly rejects vendoring a second source to close it."
    ),
    what_would_close_it=(
        "a second vendored source naming both ids, which research.md D3 rejects for this feature."
    ),
    gap_tuples=(
        ("building", "490", "age_requirement", "Franks", "entity-absent"),
        ("building", "490", "available_to", "Franks", "entity-absent"),
        ("building", "490", "cost", "Franks", "entity-absent"),
        ("building", "490", "prerequisites", "Franks", "entity-absent"),
        ("building", "490", "produced_at", "Franks", "entity-absent"),
        ("building", "490", "production_time", "Franks", "entity-absent"),
        ("building", "673", "age_requirement", "Teutons", "entity-absent"),
        ("building", "673", "available_to", "Teutons", "entity-absent"),
        ("building", "673", "cost", "Teutons", "entity-absent"),
        ("building", "673", "prerequisites", "Teutons", "entity-absent"),
        ("building", "673", "produced_at", "Teutons", "entity-absent"),
        ("building", "673", "production_time", "Teutons", "entity-absent"),
    ),
)

#: FR-022b's closed list: exactly the three blockers above, none other. Referenced by the test
#: below both for the flattened set-equality assertion and, in a failure message, by name.
_RECORDING_2_BLOCKERS: tuple[_RecordingTwoBlocker, ...] = (
    _FRANKS_CASTLE_COST_IS_AGE_SCALED,
    _GURJARAS_TRAINING_SPEED_BONUS_IS_A_TEAM_BONUS,
    _TWO_BUILDING_IDS_ARE_ABSENT_FROM_THE_VENDORED_PACK,
)

#: The flattened union of every blocker's `gap_tuples` — what recording 2's observed blocking
#: gaps must equal, exactly, for SC-007a to hold via FR-022b's exception. 1 + 2 + 12 = 15 tuples.
_RECORDING_2_ENUMERATED_BLOCKING_GAPS: frozenset[tuple[str, str, str, str, str]] = frozenset(
    gap_tuple for blocker in _RECORDING_2_BLOCKERS for gap_tuple in blocker.gap_tuples
)


@pytest.mark.parametrize(
    ("golden_path", "expected_blocking"),
    [
        (_GOLDEN_CANONICAL_STREAMS[0], frozenset()),
        (_GOLDEN_CANONICAL_STREAMS[1], _RECORDING_2_ENUMERATED_BLOCKING_GAPS),
    ],
    ids=[path.stem for path in _GOLDEN_CANONICAL_STREAMS],
)
def test_each_committed_recording_reports_zero_blocking_gaps(
    golden_path: Path, expected_blocking: frozenset[tuple[str, str, str, str, str]]
) -> None:
    """**SC-007a**: "Analysing each committed reference recording against the first knowledge
    snapshot records no gap of blocking severity outside FR-022b's enumerated list." This is the
    test that proves T645's six modelled civilisations (Byzantines, Koreans, Franks, Persians,
    Teutons, Gurjaras — research.md D11: two from the first recording, four from the second, none
    shared) are sufficient for every entity and civilisation the two committed recordings
    actually reference — with **no** `rules_overrides` or `civilisation_names` override: this is
    `coverage.coverage` run for real, against the real packaged, promoted snapshot
    (`aoe2techtree-180059`, build 180059 — both recordings' own `match-started.build`, confirmed
    directly against both golden streams), and against T648's own real numeric-civilisation-id-
    to-name research, not a stand-in for it.

    An informational gap is not asserted away here: `contracts/knowledge-base.md` is explicit that
    informational gaps "count only toward the aggregate report" and are expected to exist wherever
    this snapshot's coverage is real but partial (e.g. entities neither committed recording trains
    a discount for). Only **blocking** severity is SC-007a's claim.

    **Recording 1 genuinely passes, with no marker at all**: a remediation of T648's hand-back
    (2026-09-20) found that Koreans' "Archer armor and tower upgrades free" — the one effect
    blocking this recording — had been misclassified as conditional on state, when the
    recording's own use is unconditional (see `effects.toml`'s own `validated_by` on that entry),
    so its blocking gaps must equal the empty set, exactly.

    **Recording 2 asserts set equality against `_RECORDING_2_ENUMERATED_BLOCKING_GAPS`**
    (FR-022b), not `xfail`: the same three real, permanent reasons the former
    `_RECORDING_2_XFAIL_REASON` marker named are now `_RECORDING_2_BLOCKERS`, data a set-equality
    assertion checks in both directions — a blocker closing leaves an enumerated tuple with no
    observed match, and an unenumerated blocking gap (a real transcription defect, per FR-022b)
    leaves an observed tuple with no enumerated match. Either failure names the mismatched tuple
    directly, so a stale entry or a fourth blocker cannot hide behind a single `reason=` string
    the way the marker let them.
    """
    from aoe2stats_knowledge import coverage, gaps

    events = _load_golden_stream(golden_path)

    result = coverage.coverage(events)

    blocking = [gap for gap in result if gap.severity == gaps.BLOCKING]
    observed_blocking = frozenset(
        (gap.entity_kind, gap.entity_id, gap.field, gap.civilisation, gap.cause) for gap in blocking
    )
    missing_from_observed = expected_blocking - observed_blocking
    not_on_the_enumerated_list = observed_blocking - expected_blocking
    assert observed_blocking == expected_blocking, (
        f"{golden_path.name}: observed blocking gaps must equal FR-022b's enumerated list "
        f"exactly (SC-007a) — enumerated but not observed (a blocker may have closed): "
        f"{missing_from_observed!r}; observed but not enumerated (a real transcription defect "
        f"FR-022b requires be closed, not added to the list): {not_on_the_enumerated_list!r}"
    )


# ---------------------------------------------------------------------------------------- SC-007


#: Deliberately not a real replay `civ_id` — this test proves the field-withholding behaviour, not
#: T648's numeric-id research (that is SC-007a's job, above), so an arbitrary integer plus an
#: explicit `civilisation_names` override keeps this test's correctness independent of it.
_SYNTHETIC_CIVILISATION_ID = 900001

#: "Pikeman" — real unit id `358` in the committed pack (`table_origin = "unit"`), verified
#: directly against `aoe2techtree-180059/rules.json`: cost `{food: 35, wood: 25}`,
#: trained at the Barracks (building 12), and touched by Byzantines' real, modelled "-25%
#: Spearman-line" effect (`effects.toml`) — chosen so the mutation below removes a field a real
#: effect would otherwise have adjusted, not a field no civilisation-qualified step ever reaches.
_PIKEMAN_ID = "358"

#: "Crossbowman" — real unit id `24`, cost `{gold: 45, wood: 25}`, trained at the Archery Range
#: (building 87). Byzantines' effect does not touch it at all (its selector is Camel Rider/
#: Skirmisher/Spearman-line only), so every one of its six query-surface fields must still answer
#: normally for Byzantines once Pikeman's cost is withheld — the "every independent value is still
#: produced" half of SC-007, on a *different entity*.
_CROSSBOWMAN_ID = "24"


def test_removing_a_required_field_withholds_only_its_dependent_values() -> None:
    """**SC-007**: "Removing a required field from a snapshot causes the dependent values to be
    withheld and a gap to be recorded, while every independent value is still produced." Also
    contracts/knowledge-base.md, "Gaps": "a test deletes one field from an in-memory copy of a
    snapshot, runs the pass, and asserts that exactly the dependent data are withheld, a gap names
    the entity, field, build and civilisation, and every other datum is unchanged."

    The mutation: an in-memory, deep copy of the real, committed, promoted snapshot's `rules.json`
    with Pikeman's (`358`) `cost` field deleted entirely — not zeroed, not replaced, absent, so the
    only correct response is a gap (FR-038 forbids substituting anything, including a stale `{}`,
    for a field that was asked for and is not there).

    The stream: one synthetic participant (an arbitrary, never-real civilisation id, resolved to
    the real, modelled "Byzantines" only through this test's own `civilisation_names` override —
    see this module's docstring for why) who queues both Pikeman and Crossbowman.

    `coverage.coverage`'s return is **the gap list alone** (contracts/knowledge-base.md: "Its
    output is the gap list the document publishes") — it does not also hand back the values that
    *did* resolve. So "every independent value is still produced" is proven the only way the
    return value can prove it: the gap list contains **exactly one** entry, which is Pikeman's
    missing cost for Byzantines. Every other query the pass must have made — Pikeman's five other
    fields, and all six of Crossbowman's — produced no gap at all, which is only possible if each
    one resolved to a real answer.
    """
    from aoe2stats_knowledge import coverage, gaps

    real_rules = _real_rules_for(_PROMOTED_DIRECTORY)
    mutated_rules = copy.deepcopy(real_rules)
    del mutated_rules["entities"]["unit"][_PIKEMAN_ID]["cost"]
    assert "cost" not in mutated_rules["entities"]["unit"][_PIKEMAN_ID]
    assert mutated_rules["entities"]["unit"][_CROSSBOWMAN_ID]["cost"] == {
        "gold": 45,
        "wood": 25,
    }, "Crossbowman's own cost must be untouched by Pikeman's mutation"

    stream = [
        CanonicalEvent(
            clock_ms=0,
            kind=EventKind.MATCH_STARTED,
            payload=MatchStartedPayload(
                build=_BUILD,
                map_name="9",
                participants=(ParticipantEntry(slot=1, civilisation=_SYNTHETIC_CIVILISATION_ID),),
            ),
        ),
        CanonicalEvent(
            clock_ms=1_000,
            kind=EventKind.UNIT_QUEUED,
            participant=1,
            payload=UnitQueuedPayload(
                unit_id=int(_PIKEMAN_ID), building_type=12, building_object=5001, count=1
            ),
        ),
        CanonicalEvent(
            clock_ms=2_000,
            kind=EventKind.UNIT_QUEUED,
            participant=1,
            payload=UnitQueuedPayload(
                unit_id=int(_CROSSBOWMAN_ID), building_type=87, building_object=5002, count=1
            ),
        ),
    ]

    result = coverage.coverage(
        stream,
        civilisation_names={_SYNTHETIC_CIVILISATION_ID: "Byzantines"},
        rules_overrides={_BUILD: mutated_rules},
    )

    assert len(result) == 1, (
        "exactly one gap is expected (Pikeman's withheld cost for Byzantines); every independent "
        f"value — Pikeman's other five fields, and all six of Crossbowman's — must still resolve "
        f"with no gap of its own. Got {result!r}"
    )
    (gap,) = result
    assert isinstance(gap, gaps.KnowledgeGap)
    assert gap.cause == "field-absent", (
        "the entity resolves and the civilisation is modelled — only the field itself is "
        f"missing, which data-model.md §7 names 'field-absent', not {gap.cause!r}"
    )
    assert gap.build == _BUILD
    assert gap.entity_kind == "unit"
    assert gap.entity_id == _PIKEMAN_ID
    assert gap.field == "cost"
    assert gap.civilisation == "Byzantines"
    assert gap.severity == gaps.BLOCKING, (
        "reconstruction.resources_spent and reconstruction.ordered_army_cost both require "
        "'cost' and are neither blocked nor non-determinable (register.toml), so this gap must "
        "compute as blocking (research.md D7) — dependent values really are withheld"
    )


# ------------------------------------------------------------------------------------- T652b


def _one_build_higher_than_every_promoted_snapshot() -> int:
    """A build no committed, promoted snapshot describes — computed from whatever is actually
    committed rather than hard-coded, matching `test_query.py`'s own helper of the same name/intent
    so a future fixture at a higher build cannot silently turn this into a build that *does*
    resolve."""
    from aoe2stats_knowledge import snapshot

    resolvable = snapshot.load_resolvable_snapshots()
    assert resolvable, "no promoted snapshot is committed — this test proves nothing without one"
    return max(s.identity.describes_build for s in resolvable) + 1


def test_a_stream_with_no_build_at_all_records_a_blocking_gap() -> None:
    """(a): `coverage.py`'s own pre-fix behaviour was `if build is None: return ()` — a stream that
    never names a build (no `match-started` event at all, or one whose own `build` field is
    `None`, both real shapes `MatchStartedPayload.build: int | None` allows) reported *zero* gaps,
    so `validate.py`'s rule 8 saw no blocker at all and the document would have published every
    value unchecked. spec.md's own edge case ("a recording ... from a game build the knowledge base
    has no snapshot for ... is a gap of blocking severity") makes no exception for the build itself
    being unknown outright — `build is None` is the same ignorance wearing different clothes, per
    this task's own text, and must gap exactly like an unresolvable-but-known build does.
    """
    from aoe2stats_knowledge import coverage, gaps

    stream = [
        CanonicalEvent(
            clock_ms=0,
            kind=EventKind.MATCH_STARTED,
            payload=MatchStartedPayload(
                build=None,
                map_name="9",
                participants=(ParticipantEntry(slot=1, civilisation=_SYNTHETIC_CIVILISATION_ID),),
            ),
        ),
        CanonicalEvent(
            clock_ms=1_000,
            kind=EventKind.UNIT_QUEUED,
            participant=1,
            payload=UnitQueuedPayload(
                unit_id=int(_PIKEMAN_ID), building_type=12, building_object=5001, count=1
            ),
        ),
    ]

    result = coverage.coverage(
        stream, civilisation_names={_SYNTHETIC_CIVILISATION_ID: "Byzantines"}
    )

    assert len(result) == 1, (
        "a stream that names no build at all must still report one whole-stream gap, not zero, "
        f"got {result!r}"
    )
    (gap,) = result
    assert isinstance(gap, gaps.KnowledgeGap)
    assert gap.cause == "no-snapshot-for-build"
    assert gap.severity == gaps.BLOCKING


def test_an_unresolvable_build_reports_exactly_one_gap_not_one_per_entity_field_pair() -> None:
    """(b): `_gap_for` re-resolved `snapshot.snapshot_for(build)` per `(entity, field)` pair and
    returned the same `no-snapshot-for-build` gap each time — the task's own count is 612 of them
    on recording 1's real golden stream (confirmed directly: `load_all_snapshots` was called 612
    times over that stream's real entity/field product). `analysis_knowledge_gaps`' unique index is
    `(identity_digest, entity_kind, entity_id, field, coalesce(civilisation_id, ''))`, and every one
    of those duplicate gaps is equal across all five columns (a whole-build cause names no entity,
    field or civilisation at all — `gaps.py`'s `_WHOLE_BUILD_CAUSES`), so T662's writer would raise
    on the second insert. The fix resolves the snapshot once, before the entity loop, and emits
    exactly one gap regardless of how many (entity, field) pairs the stream would otherwise ask
    about — two entities here (Pikeman, Crossbowman) times six fields is twelve opportunities for
    the pre-fix code to duplicate; this test only needs more than one to prove deduplication, not
    the real 612.
    """
    from aoe2stats_knowledge import coverage, gaps

    unresolvable_build = _one_build_higher_than_every_promoted_snapshot()
    stream = [
        CanonicalEvent(
            clock_ms=0,
            kind=EventKind.MATCH_STARTED,
            payload=MatchStartedPayload(
                build=unresolvable_build,
                map_name="9",
                participants=(ParticipantEntry(slot=1, civilisation=_SYNTHETIC_CIVILISATION_ID),),
            ),
        ),
        CanonicalEvent(
            clock_ms=1_000,
            kind=EventKind.UNIT_QUEUED,
            participant=1,
            payload=UnitQueuedPayload(
                unit_id=int(_PIKEMAN_ID), building_type=12, building_object=5001, count=1
            ),
        ),
        CanonicalEvent(
            clock_ms=2_000,
            kind=EventKind.UNIT_QUEUED,
            participant=1,
            payload=UnitQueuedPayload(
                unit_id=int(_CROSSBOWMAN_ID), building_type=87, building_object=5002, count=1
            ),
        ),
    ]

    result = coverage.coverage(
        stream, civilisation_names={_SYNTHETIC_CIVILISATION_ID: "Byzantines"}
    )

    no_snapshot_gaps = [gap for gap in result if gap.cause == "no-snapshot-for-build"]
    assert len(no_snapshot_gaps) == 1, (
        "an unresolvable build must be reported exactly once, never once per (entity, field) pair "
        f"queried against it — got {len(no_snapshot_gaps)}: {no_snapshot_gaps!r}"
    )
    assert len(result) == 1, (
        f"no gap other than the single whole-build one is expected, got {result!r}"
    )
    (gap,) = result
    assert isinstance(gap, gaps.KnowledgeGap)
    assert gap.build == unresolvable_build
    assert gap.severity == gaps.BLOCKING


def test_an_unresolvable_build_with_no_entities_still_reports_one_gap() -> None:
    """(b), the other direction: the pre-fix loop only ever emitted a gap while iterating
    `entities_by_slot`, so a stream whose build is unresolvable but which names no entity at all
    (only a `match-started` event) returned zero gaps — FR-027's "the absence MUST be recorded as a
    gap" does not carve out an exception for an otherwise-empty stream; the build itself is what is
    unknown, independent of what, if anything, was trained."""
    from aoe2stats_knowledge import coverage, gaps

    unresolvable_build = _one_build_higher_than_every_promoted_snapshot()
    stream = [
        CanonicalEvent(
            clock_ms=0,
            kind=EventKind.MATCH_STARTED,
            payload=MatchStartedPayload(
                build=unresolvable_build,
                map_name="9",
                participants=(ParticipantEntry(slot=1, civilisation=_SYNTHETIC_CIVILISATION_ID),),
            ),
        ),
    ]

    result = coverage.coverage(stream)

    assert len(result) == 1, (
        "FR-027 requires a gap even when the stream references no entity at all — the build itself "
        f"is what failed to resolve, not any one entity's lookup. Got {result!r}"
    )
    (gap,) = result
    assert isinstance(gap, gaps.KnowledgeGap)
    assert gap.cause == "no-snapshot-for-build"
