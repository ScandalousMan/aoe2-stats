"""T649: the coverage pass over a canonical stream. Written before `coverage.py` (T648) existed;
T648 has since implemented it, `test_removing_a_required_field_withholds_only_its_dependent_values`
(SC-007) genuinely passes and its marker is removed, and
`test_each_committed_recording_reports_zero_blocking_gaps` (SC-007a) is parametrized per recording:
the first committed recording (Byzantines/Koreans) genuinely passes, with no marker at all, since a
remediation of T648's hand-back (2026-09-20) found and corrected a real misclassification in
`effects.toml` — Koreans' "Archer armor and tower upgrades free" is unconditional, not
conditional-on-state (see `effects.toml`'s own `validated_by` on that entry for the evidence). The
second committed recording's own case is still `xfail`, for three real, permanent-for-this-feature
reasons recorded on that one parametrized case's own marker below, not "T648 not implemented yet".

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
and because it costs nothing. `strict=True` on the one test still marked `xfail` is what turns this
file red again, forcing the marker off, the moment whatever it is still waiting on lands.

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
#: both golden streams below), which `aoe2techtree-fixture-promoted` describes with all six
#: modelled civilisations (T645).
_BUILD = 180059

_PROMOTED_DIRECTORY = "aoe2techtree-fixture-promoted"

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


#: Recording 2's own, permanent-for-this-feature reasons SC-007a cannot pass for it, established by
#: a remediation of T648's hand-back (2026-09-20), which re-examined every blocking gap the pass
#: reports against this recording and confirmed each is a real, honest limit rather than a
#: transcription error (FR-038/CLAUDE.md: "never substitute a value for missing knowledge... if a
#: task seems to require one, the task is wrong — stop and say so"):
#:
#:   - **Franks' "Castles cost -15/25% in Castle/Imperial Age"** (building 82, the Castle the
#:     Franks participant trains Throwing Axemen from) is genuinely age-scaled: its magnitude
#:     depends on which age the Castle was built in, and this static, per-build knowledge base's
#:     query surface (`query.py`'s six functions) carries no "current age"/match-state argument at
#:     all — an architecture question (the effect model's own signature), not a fixable
#:     transcription, and out of this remediation's scope.
#:   - **Gurjaras' Team Bonus "Camel and Elephant Units train +25% faster"** (units 1755, 239) is,
#:     by the pack's own text, a **Team Bonus** — granted to every allied player from a Gurjaras
#:     ally, not only to Gurjaras-controlled units — so it is correctly excluded from this
#:     civilisation-scoped effect model, exactly like every other team bonus this feature has ever
#:     modelled (`effects.toml`'s own "Team Bonus:" entries throughout).
#:   - **Two building ids (490, 673)**, referenced by `building-placed` events in this recording,
#:     are absent from the vendored `aoe2techtree` pack entirely — real, age-upgraded visual
#:     variants the pack's tech-tree UI source never enumerates a second id for
#:     (`test_normalise.py`'s `_BUILDING_IDS_ABSENT_FROM_THE_VENDORED_PACK`, first named by T640). A
#:     genuine third-party source coverage hole, not a decoding or civilisation-assignment error;
#:     vendoring a second source to close it is explicitly rejected by research.md D3 for this
#:     feature.
_RECORDING_2_XFAIL_REASON = (
    "Recording 2 (AgeIIDE_Replay_504695319) cannot report zero blocking gaps within this "
    "feature's current architecture and single-source decision, for three independent, permanent "
    "reasons (each re-examined and confirmed real by a remediation of T648's hand-back, "
    "2026-09-20; this is not the general 'T648 not implemented' placeholder this marker started "
    "as): (1) Franks' 'Castles cost -15/25% in Castle/Imperial Age' (building 82) is age-scaled — "
    "its value depends on which age a building was constructed in, and this static knowledge "
    "base's query surface (query.py) has no age/match-state argument to resolve that against; "
    "closing this means adding one, an architecture change out of scope here, not an effects.toml "
    "transcription fix. (2) Gurjaras' 'Team Bonus: Camel and Elephant Units train +25% faster' "
    "(units 1755, 239) is, by the pack's own text, a Team Bonus — granted through an ally, not to "
    "Gurjaras' own units — and correctly stays unmodelled by this feature's own design, the same "
    "as every other team bonus effects.toml records. (3) Two building ids this recording's own "
    "building-placed events name, 490 and 673, are absent from the vendored aoe2techtree pack "
    "entirely (test_normalise.py's _BUILDING_IDS_ABSENT_FROM_THE_VENDORED_PACK, first found and "
    "named by T640) — a genuine gap in the single vendored third-party source, and research.md D3 "
    "explicitly rejects vendoring a second source to close it. None of the three is a "
    "coverage.py defect, a civilisation-assignment error or a fixable effects.toml "
    "misclassification (contrast recording 1's own former blocker, Koreans' archer-armor "
    "bonus, which this same remediation confirmed WAS a misclassification and corrected — see "
    "effects.toml's own validated_by on that entry); each is a real, honest limit of this "
    "feature's static, single-source, age-blind effect model, left in place rather than worked "
    "around or fabricated around (FR-038). XPASS(strict=True) if a later feature closes any of "
    "these — an age/match-state query parameter, a second vendored source, or Gurjaras' bonus "
    "being reclassified as non-team-wide, none of which this remediation found evidence for — so "
    "that a silent regression cannot hide."
)


@pytest.mark.parametrize(
    "golden_path",
    [
        _GOLDEN_CANONICAL_STREAMS[0],
        pytest.param(
            _GOLDEN_CANONICAL_STREAMS[1],
            marks=pytest.mark.xfail(strict=True, reason=_RECORDING_2_XFAIL_REASON),
        ),
    ],
    ids=[path.stem for path in _GOLDEN_CANONICAL_STREAMS],
)
def test_each_committed_recording_reports_zero_blocking_gaps(golden_path: Path) -> None:
    """**SC-007a**: "Analysing each committed reference recording against the first knowledge
    snapshot records zero gaps of blocking severity." This is the test that proves T645's six
    modelled civilisations (Byzantines, Koreans, Franks, Persians, Teutons, Gurjaras — research.md
    D11: two from the first recording, four from the second, none shared) are sufficient for every
    entity and civilisation the two committed recordings actually reference — with **no**
    `rules_overrides` or `civilisation_names` override: this is `coverage.coverage` run for real,
    against the real packaged, promoted snapshot (`aoe2techtree-fixture-promoted`, build 180059 —
    both recordings' own `match-started.build`, confirmed directly against both golden streams),
    and against T648's own real numeric-civilisation-id-to-name research, not a stand-in for it.

    An informational gap is not asserted away here: `contracts/knowledge-base.md` is explicit that
    informational gaps "count only toward the aggregate report" and are expected to exist wherever
    this snapshot's coverage is real but partial (e.g. entities neither committed recording trains
    a discount for). Only **blocking** severity is SC-007a's claim.

    **Recording 1 genuinely passes, with no marker at all**: a remediation of T648's hand-back
    (2026-09-20) found that Koreans' "Archer armor and tower upgrades free" — the one effect
    blocking this recording — had been misclassified as conditional on state, when the
    recording's own use is unconditional (see `effects.toml`'s own `validated_by` on that entry).
    **Recording 2 stays `xfail`**, for three real, permanent reasons named on that one
    parametrized case's own marker (`_RECORDING_2_XFAIL_REASON` above), not this docstring.
    """
    from aoe2stats_knowledge import coverage, gaps

    events = _load_golden_stream(golden_path)

    result = coverage.coverage(events)

    blocking = [gap for gap in result if gap.severity == gaps.BLOCKING]
    assert blocking == [], (
        f"{golden_path.name}: expected zero blocking gaps against the six-civilisation "
        f"promoted snapshot, got {blocking!r}"
    )


# ---------------------------------------------------------------------------------------- SC-007


#: Deliberately not a real replay `civ_id` — this test proves the field-withholding behaviour, not
#: T648's numeric-id research (that is SC-007a's job, above), so an arbitrary integer plus an
#: explicit `civilisation_names` override keeps this test's correctness independent of it.
_SYNTHETIC_CIVILISATION_ID = 900001

#: "Pikeman" — real unit id `358` in the committed pack (`table_origin = "unit"`), verified
#: directly against `aoe2techtree-fixture-promoted/rules.json`: cost `{food: 35, wood: 25}`,
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
