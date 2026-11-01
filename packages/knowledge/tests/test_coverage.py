"""T649: the coverage pass over a canonical stream. Written before `coverage.py` (T648) existed;
T648 has since implemented it, `test_removing_a_required_field_withholds_only_its_dependent_values`
(SC-007) genuinely passes and its marker is removed, and
`test_each_committed_recording_reports_zero_blocking_gaps` (SC-007a) is parametrized per recording.
**Recording 1's own blocking gaps are the empty set again (T652u, 2026-09-28, superseding T652o's
2026-09-23 one-blocker enumeration)**: the first committed recording (Saracens/Malians, T652m —
Byzantines/Koreans before it, both of which turned out to be in neither committed recording at
all) once had one real blocker, Malians' Team Bonus "Universities work +80% faster" — the third
review found it touched production_time and had been left un-transcribed, so T652o recorded it as
a categorical refusal. T652u (2026-09-28, the repository owner's arbitration of the fourth review,
"a conditional bonus is a rule, and is modelled") re-modelled it as `condition = "team"` instead,
which `coverage.py` treats as complete knowledge, not a gap, closing recording 1's blocker
entirely. The second committed recording's own case (T652c/T652m/T652o/T652q/T652u) asserts its
blocking gaps equal `_RECORDING_2_ENUMERATED_BLOCKING_GAPS`, FR-022b's closed, **one**-blocker
enumeration below — down from four: T652m removed a second of an original three, Gurjaras' team
bonus, after finding Gurjaras was never in this recording at all; T652u closed the other three
(Franks' Castle cost, Franks' Chivalry, Persians' Town Center/Dock work speed — all age-scaled or
researched-conditional, all re-modelled as conditional rules the same way recording 1's own
blocker was) the same way. What remains — the two building ids absent from the vendored pack
entirely — was never a civilisation bonus at all, so re-modelling a bonus's condition has nothing
to close there. This replaces a blanket `xfail(strict=True, reason=...)` a remediation of T648's
hand-back found insufficient — a `reason=` string asserts against nothing, and closing one of the
blockers left the assertion failing with the marker still holding, silencing exactly the signal
FR-022b exists to keep. Set equality catches both directions, on both recordings: a closed blocker
leaves an enumerated tuple unmatched, and a further blocker (a real transcription defect) leaves
an observed tuple unmatched.

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
`production_time`, `produced_at`, `age_requirement`, `prerequisites`, `available_to`,
`line_of_sight` and `name` (T709a, never gapped: it is the query that degrades to the bare
identifier). `line_of_sight` belongs to a different reconstruction domain (map control /
exploration, blocked on the unread starting state — feature 008's territory, research.md D1) and is
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
import dataclasses
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

#: The first two committed recordings report this build (`match-started.build`, verified directly
#: against both golden streams below), which `aoe2techtree-180059` describes with all six
#: modelled civilisations (T645). The third reports build 185872 (T746).
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
    _FIXTURES_ROOT / "AgeIIDE_Replay_511523321.canonical.json",
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
                ParticipantEntry(slot=p["slot"], civilisation=p["civilisation"], team=p.get("team"))
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
#: observed on the recording it is enumerated against that the blocker accounts for.
#:
#: **T652u (2026-09-28, repository owner's arbitration of the fourth review) closed every blocker
#: that was ever an age-gated, researched-conditional or team-wide bonus touching a carried field**
#: — "a conditional bonus is a rule, and is modelled" (research.md D5, amended). Franks' Castle
#: cost, Franks' Chivalry, Persians' Town Center/Dock work speed and Malians' University Team
#: Bonus are all `modelled = "yes"` now, each with a `condition`, and `coverage.py` treats a
#: modelled conditional effect reached with no match state as complete knowledge, not a gap
#: (`effects.ContextRequired`, caught directly in `coverage.coverage`'s own loop) — so none of
#: them appear in either recording's observed blocking gaps any more. **Recording 1's own blocker
#: (Malians' University Team Bonus) is gone entirely — it is the empty set again**, as it was
#: before the third review found the bonus untranscribed at all. **Recording 2 keeps exactly one
#: blocker**: the two building ids absent from the vendored pack, which no re-modelling can touch
#: at all — it is not a civilisation bonus, it is a hole in the one lawful vendored source
#: (research.md D3 rejects a second one).
@dataclass(frozen=True, slots=True)
class _RecordingBlocker:
    """One of FR-022b's enumerated blockers standing between a committed recording and SC-007a's
    zero-blocking-gaps claim (or, for recording 1 since T652u, once again the true empty set)."""

    name: str
    why_the_vendored_source_cannot_close_it: str
    what_would_close_it: str
    gap_tuples: tuple[tuple[str, str, str, str, str], ...]


#: FR-022b's closed list for recording 1: the empty tuple. T652o (2026-09-23) made this
#: recording's own Malians University Team Bonus a real blocker once the third review found it
#: touched production_time and had been left untranscribed; T652u (2026-09-28) closed it again —
#: "Universities work +80% faster" is `condition = "team"`, `modelled = "yes"` now, and (since
#: T652v) `coverage.coverage` supplies the team that decides it, so the bonus is applied for real,
#: not merely counted as modelled — recording 1's Malians participant researching four University
#: technologies (47, 50, 93, 140) is exactly as much complete knowledge as before the third review
#: found the transcription hole, just for a different reason: the bonus is a rule now, not an
#: unwritten refusal.
_RECORDING_1_BLOCKERS: tuple[_RecordingBlocker, ...] = ()

#: The flattened union of recording 1's blockers — the empty set, once again.
_RECORDING_1_ENUMERATED_BLOCKING_GAPS: frozenset[tuple[str, str, str, str, str]] = frozenset(
    gap_tuple for blocker in _RECORDING_1_BLOCKERS for gap_tuple in blocker.gap_tuples
)

#: **Recording 2 keeps no blocker (T773).** Two building ids (490, 673), referenced by
#: `building-placed` events in this recording, are absent from the vendored `aoe2techtree` pack
#: entirely (`test_normalise.py`'s `_BUILDING_IDS_ABSENT_FROM_THE_VENDORED_PACK`, first named by
#: T640): a coverage hole of the pack, not a decoding or civilisation-assignment error and not a
#: civilisation bonus. A referenced source, `aoc-reference-data`'s `objects` (read 2026-10-18 and
#: again 2026-10-28, `docs/data-sources.md` section 6), names both "Gate", and FR-022d closes them
#: with a transcribed alias in a snapshot's `aliases.toml`, vendoring nothing. T773's snapshot for
#: build 180059 (`aoe2techtree-180059-civilisations-53`) carries both aliases, so the blocker this
#: recording used to hold (six tuples: cost, produced_at and production_time of each, for the
#: civilisation the recording places it under, building 490 for Franks and 673 for Teutons) is
#: closed, as T767 closed building 490 for build 185872's recording 3. FR-022b's list is empty.
_RECORDING_2_BLOCKERS: tuple[_RecordingBlocker, ...] = ()

#: The flattened union of every blocker's `gap_tuples`: empty, which `test_each_committed_recording_
#: reports_zero_blocking_gaps` asserts by set equality against what the pass observes.
_RECORDING_2_ENUMERATED_BLOCKING_GAPS: frozenset[tuple[str, str, str, str, str]] = frozenset(
    gap_tuple for blocker in _RECORDING_2_BLOCKERS for gap_tuple in blocker.gap_tuples
)


#: **Recording 3 (match 511523321, build 185872, Slavs versus Sicilians) keeps no blocker (T772).**
#: T746 had three; T767 closed two (building 490, absent from the vendored pack, is the pack's Gate
#: through a transcribed alias, FR-022d; the Donjon's and the Castle's construction time under the
#: Sicilians' "Fortifications" are stated by the publisher's own notes, update 111772), and kept
#: one: the Slavs' Detinets, whose publisher's note (update 61321: "Replaces 40% of Castles' and
#: Towers' stone cost with wood") repeats the pack's string and states no wood amount. T772
#: closed it: the owner's reading of 2026-10-31 (owner-readings.md, from the Fandom Detinets page
#: read by ChatGPT for the owner, accepted unchecked; not a game reading) gives the Castle 260
#: wood and 390 stone, and `aoe2techtree-185872-owner-readings` models it as a researched-
#: conditional cost row, which `coverage.py` counts as complete knowledge (the recording does not
#: carry the researched set, and the knowledge base never decides it, FR-022e). FR-022b's list for
#: this recording is the empty set; the Sicilians' remaining Fortifications are held nowhere
#: either, being modelled.
_RECORDING_3_BLOCKERS: tuple[_RecordingBlocker, ...] = ()

#: The flattened union of recording 3's blockers: the empty set.
_RECORDING_3_ENUMERATED_BLOCKING_GAPS: frozenset[tuple[str, str, str, str, str]] = frozenset(
    gap_tuple for blocker in _RECORDING_3_BLOCKERS for gap_tuple in blocker.gap_tuples
)


@pytest.mark.parametrize(
    ("golden_path", "expected_blocking"),
    [
        (_GOLDEN_CANONICAL_STREAMS[0], _RECORDING_1_ENUMERATED_BLOCKING_GAPS),
        (_GOLDEN_CANONICAL_STREAMS[1], _RECORDING_2_ENUMERATED_BLOCKING_GAPS),
        (_GOLDEN_CANONICAL_STREAMS[2], _RECORDING_3_ENUMERATED_BLOCKING_GAPS),
    ],
    ids=[path.stem for path in _GOLDEN_CANONICAL_STREAMS],
)
def test_each_committed_recording_reports_zero_blocking_gaps(
    golden_path: Path, expected_blocking: frozenset[tuple[str, str, str, str, str]]
) -> None:
    """**SC-007a**: "Analysing each committed reference recording against the first knowledge
    snapshot records no gap of blocking severity outside FR-022b's enumerated list." This is the
    test that proves the six real modelled civilisations (Franks, Teutons, Persians, Saracens,
    Malians, Tatars — T652m; research.md D11: two from the first recording, four from the second,
    none shared) are sufficient for every entity and civilisation the two committed recordings
    actually reference — with **no** `rules_overrides` or `civilisation_names` override: this is
    `coverage.coverage` run for real, against the real packaged, promoted snapshot
    (`aoe2techtree-180059`, build 180059 — both recordings' own `match-started.build`, confirmed
    directly against both golden streams), and against T648's own real numeric-civilisation-id-
    to-name research, not a stand-in for it.

    An informational gap is not asserted away here: `contracts/knowledge-base.md` is explicit that
    informational gaps "count only toward the aggregate report" and are expected to exist wherever
    this snapshot's coverage is real but partial (e.g. entities neither committed recording trains
    a discount for). Only **blocking** severity is SC-007a's claim.

    **Recording 1 is zero again (T652u, 2026-09-28).** It plays Saracens versus Malians (T652m,
    corrected from the previously committed, wrong Byzantines/Koreans). Every one of Saracens' and
    Malians' other `modelled = "no"` effects still touches no query-surface field this recording's
    players actually reference (each such effect's `field` is untracked — `hp`, `attack`,
    `gold_dropoff_bonus`, `pierce_armor`, `fires_arrows_ungarrisoned` — so `coverage.py`'s six-field
    pass never matches one), and each civilisation's one modelled cost effect (Saracens' Market,
    Malians' buildings) still applies cleanly to every building either player places. Malians' Team
    Bonus "Universities work +80% faster" was a real blocker between T652o (2026-09-23, the third
    review's own finding that it touches production_time and had been left untranscribed) and
    T652u (2026-09-28, the repository owner's arbitration of the fourth review: "a conditional
    bonus is a rule, and is modelled") — it is `condition = "team"`, `modelled = "yes"` now, and
    (since T652v) `coverage.coverage` supplies the team that decides it, so the bonus is applied
    for real and is no gap (contracts/knowledge-base.md, "Civilisation qualification"). Recording
    1's Malians participant still researches four University technologies (47, 50, 93, 140); none
    of them gap any more.

    **Recording 2 asserts set equality against `_RECORDING_2_ENUMERATED_BLOCKING_GAPS`**
    (FR-022b), not `xfail`: the one real, permanent reason named by `_RECORDING_2_BLOCKERS` below
    (T652m removed a second, Gurjaras' team bonus, once Gurjaras was found to be in neither
    committed recording — the slot it used to be attributed to is Persians, which has no
    equivalent effect touching that slot's own entities; **T652u, 2026-09-28, closed the other
    three** — Franks' Castle cost, Franks' Chivalry and Persians' Town Center/Dock work speed, all
    age-scaled or researched-conditional bonuses T652o/T652q had found and enumerated as
    blockers, are re-modelled as conditional rules and close the same way recording 1's own
    blocker did) is data a set-equality assertion checks in both directions — a blocker closing
    leaves an enumerated tuple with no observed match, and an unenumerated blocking gap (a real
    transcription defect, per FR-022b) leaves an observed tuple with no enumerated match. Either
    failure names the mismatched tuple directly, so a stale entry or a further blocker cannot hide
    behind a single `reason=` string the way a marker would.

    The one blocker that remained after T652u — buildings 490 and 673, absent from the first
    snapshot's pack entirely — was never a civilisation bonus; T773's snapshot for build 180059
    closes it with two transcribed aliases (FR-022d), so recording 2's list is empty now.

    **Recording 3 (T746, T767, T772)** is the build 185872 recording, Slavs versus Sicilians. It
    resolves against the newest snapshot of the build's chain, `aoe2techtree-185872-owner-readings`
    (the first of the chain models no civilisation, so every civilisation-qualified query on this
    recording was a gap: 450 gaps, 225 of them blocking, before the second existed). T746 held three
    blockers, T767 closed two and kept the Slavs' Detinets, and T772 closed that one from the
    owner's reading, so its list is empty and is asserted by set equality exactly as recording 2's
    is.
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


def test_recording_3_resolves_to_the_snapshot_that_closed_its_last_blocker() -> None:
    """T772: the empty list above is a claim about the newest snapshot of build 185872's chain, so
    the test names it; a later snapshot of the build that is current instead fails here, and the
    list is re-measured against it rather than trusted."""
    from aoe2stats_knowledge import snapshot

    resolved = snapshot.snapshot_for(185872)
    assert isinstance(resolved, snapshot.Snapshot)
    assert resolved.directory == "aoe2techtree-185872-owner-readings"
    assert not _RECORDING_3_ENUMERATED_BLOCKING_GAPS


# ---------------------------------------------------------------------------------------- SC-007


#: Deliberately not a real replay `civ_id` — this test proves the field-withholding behaviour, not
#: T648's numeric-id research (that is SC-007a's job, above), so an arbitrary integer plus an
#: explicit `civilisation_names` override keeps this test's correctness independent of it.
_SYNTHETIC_CIVILISATION_ID = 900001

#: "Market" — real building id `84` in the committed pack (`table_origin = "building"`), verified
#: directly against `aoe2techtree-180059/rules.json`: cost `{wood: 175}`, and touched by
#: Saracens' real, modelled "Markets cost -100 wood" effect (`effects.toml`, T652m) — chosen so
#: the mutation below removes a field a real effect would otherwise have adjusted, not a field no
#: civilisation-qualified step ever reaches. (T652m: this role was `_PIKEMAN_ID` under the
#: removed Byzantines' "-25% Spearman-line" effect before Byzantines was found to be in neither
#: committed recording; none of the six real modelled civilisations' cost effects touch a unit,
#: only buildings and technologies, so the entity kind moved with it.)
_MARKET_ID = "84"

#: "Mill" — real building id `68`, cost `{wood: 100}`. Saracens' effect does not touch it at all
#: (its selector is the Market alone, building 84), so every one of its six query-surface fields
#: must still answer normally for Saracens once the Market's cost is withheld — the "every
#: independent value is still produced" half of SC-007, on a *different entity*.
_MILL_ID = "68"

#: T652p (b): a `unit_id` value for tests whose stream never resolves the entity at all (an
#: unresolvable build, or no build), so the value carried is never looked up — only ever passed
#: through unread. Deliberately not `_MARKET_ID`/`_MILL_ID`: those are building ids, and using a
#: building id as `unit_id=` reads as a (false) claim that 84/68 are unit ids. Matches
#: `test_query.py`'s own `_UNKNOWN_UNIT_ID` convention for a placeholder that is never a real id.
_UNRESOLVED_UNIT_ID_PLACEHOLDER = 999_999_999


def test_removing_a_required_field_withholds_only_its_dependent_values() -> None:
    """**SC-007**: "Removing a required field from a snapshot causes the dependent values to be
    withheld and a gap to be recorded, while every independent value is still produced." Also
    contracts/knowledge-base.md, "Gaps": "a test deletes one field from an in-memory copy of a
    snapshot, runs the pass, and asserts that exactly the dependent data are withheld, a gap names
    the entity, field, build and civilisation, and every other datum is unchanged."

    The mutation: an in-memory, deep copy of the real, committed, promoted snapshot's `rules.json`
    with the Market's (`84`) `cost` field deleted entirely — not zeroed, not replaced, absent, so
    the only correct response is a gap (FR-038 forbids substituting anything, including a stale
    `{}`, for a field that was asked for and is not there).

    The stream: one synthetic participant (an arbitrary, never-real civilisation id, resolved to
    the real, modelled "Saracens" only through this test's own `civilisation_names` override —
    see this module's docstring for why) who places both a Market and a Mill.

    `coverage.coverage`'s return is **the gap list alone** (contracts/knowledge-base.md: "Its
    output is the gap list the document publishes") — it does not also hand back the values that
    *did* resolve. So "every independent value is still produced" is proven the only way the
    return value can prove it: the gap list contains the Market's missing cost for Saracens, plus
    (T652y) one structural `prerequisites` gap per entity queried — `rules.json` carries no
    `prerequisites` field at all any more, so `_field_present` refuses it for every entity,
    independent of this mutation, the Mill's own untouched query included. Every other query the
    pass must have made — the Market's four other fields, and the Mill's other five — produced no
    gap at all, which is only possible if each one resolved to a real answer.
    """
    from aoe2stats_knowledge import coverage, gaps

    real_rules = _real_rules_for(_PROMOTED_DIRECTORY)
    mutated_rules = copy.deepcopy(real_rules)
    del mutated_rules["entities"]["building"][_MARKET_ID]["cost"]
    assert "cost" not in mutated_rules["entities"]["building"][_MARKET_ID]
    assert mutated_rules["entities"]["building"][_MILL_ID]["cost"] == {
        "wood": 100,
    }, "the Mill's own cost must be untouched by the Market's mutation"

    stream = [
        CanonicalEvent(
            clock_ms=0,
            kind=EventKind.MATCH_STARTED,
            payload=MatchStartedPayload(
                build=_BUILD,
                map_name="9",
                participants=(
                    ParticipantEntry(slot=1, civilisation=_SYNTHETIC_CIVILISATION_ID, team=None),
                ),
            ),
        ),
        CanonicalEvent(
            clock_ms=1_000,
            kind=EventKind.BUILDING_PLACED,
            participant=1,
            payload=BuildingPlacedPayload(
                building_id=int(_MARKET_ID), position=Position(x=10, y=10)
            ),
        ),
        CanonicalEvent(
            clock_ms=2_000,
            kind=EventKind.BUILDING_PLACED,
            participant=1,
            payload=BuildingPlacedPayload(building_id=int(_MILL_ID), position=Position(x=12, y=10)),
        ),
    ]

    result = coverage.coverage(
        stream,
        civilisation_names={_SYNTHETIC_CIVILISATION_ID: "Saracens"},
        rules_overrides={_BUILD: mutated_rules},
    )

    prerequisites_gaps = [g for g in result if g.field == "prerequisites"]
    other_gaps = [g for g in result if g.field != "prerequisites"]

    # T652y: `prerequisites` always refuses — see this test's own docstring — so both entities
    # queried (Market, Mill) gap it regardless of the mutation, `informational` (D7: the one
    # register entry that named the field is `blocked`), never the mutation's own signal.
    assert {(g.entity_id, g.severity) for g in prerequisites_gaps} == {
        (_MARKET_ID, "informational"),
        (_MILL_ID, "informational"),
    }, f"got {prerequisites_gaps!r}"

    assert len(other_gaps) == 1, (
        "exactly one non-structural gap is expected (the Market's withheld cost for Saracens); "
        f"every independent value — the Market's other four fields, and the Mill's other five — "
        f"must still resolve with no gap of its own. Got {other_gaps!r}"
    )
    (gap,) = other_gaps
    assert isinstance(gap, gaps.KnowledgeGap)
    assert gap.cause == "field-absent", (
        "the entity resolves and the civilisation is modelled — only the field itself is "
        f"missing, which data-model.md §7 names 'field-absent', not {gap.cause!r}"
    )
    assert gap.build == _BUILD
    assert gap.entity_kind == "building"
    assert gap.entity_id == _MARKET_ID
    assert gap.field == "cost"
    assert gap.civilisation == "Saracens"
    assert gap.severity == gaps.BLOCKING, (
        "reconstruction.resources_spent and reconstruction.ordered_army_cost both require "
        "'cost' and are neither blocked nor non-determinable (register.toml), so this gap must "
        "compute as blocking (research.md D7) — dependent values really are withheld"
    )


# ------------------------------------------------------------------------------------- T652k


def test_two_slots_on_one_civilisation_produce_no_duplicate_gaps() -> None:
    """T652k: `entities_by_slot` was keyed by **slot**, so `coverage()` emitted one gap per
    (slot, entity, field) — a query result depends only on `(entity, civilisation, build)`, never
    on which slot referenced the entity, so two seated participants sharing a civilisation (a
    mirror matchup, or any team game with two players on one civilisation) produced the same gap
    once per slot that referenced it. `analysis_knowledge_gaps`' own unique index —
    `(identity_digest, entity_kind, entity_id, field, coalesce(civilisation_id, ''))`,
    `packages/storage/src/aoe2stats_storage/models.py` — checks nothing about the slot at all, so
    every copy is equal on all five columns and T662's writer rejects the second insert of an
    identical row.

    Recording 2's own golden stream (`_load_golden_stream`, this module's own loader — no new
    fixture file) is forced onto this shape by `dataclasses.replace`-ing every seated
    participant's `civilisation` in its one `match-started` event down to the first participant's
    real value, leaving every other event (and therefore every entity referenced) untouched.
    Recording 2 seats four distinct, real civilisations before this mutation (module docstring),
    so the unmutated stream cannot exercise this at all — this is exactly why neither committed
    recording's own SC-007a assertion sees the defect.

    Asserts the **count**, not that a gap exists at all: "at least one gap" cannot see
    duplication, the same trap T652b's own duplicate-gap test had to avoid. The key compared is
    the unique index's own five columns minus `identity_digest` (constant across one `coverage()`
    call, so irrelevant to whether two gaps from the same call collide).
    """
    from aoe2stats_knowledge import coverage

    events = _load_golden_stream(_GOLDEN_CANONICAL_STREAMS[1])
    match_started_index = next(
        index for index, event in enumerate(events) if event.kind is EventKind.MATCH_STARTED
    )
    match_started = events[match_started_index]
    assert isinstance(match_started.payload, MatchStartedPayload)
    assert len(match_started.payload.participants) >= 2, (
        "recording 2 must seat at least two participants for this to force a shared civilisation"
    )
    forced_civilisation = match_started.payload.participants[0].civilisation
    forced_participants = tuple(
        dataclasses.replace(participant, civilisation=forced_civilisation)
        for participant in match_started.payload.participants
    )
    events[match_started_index] = dataclasses.replace(
        match_started,
        payload=dataclasses.replace(match_started.payload, participants=forced_participants),
    )

    result = coverage.coverage(events)

    def _unique_index_key(gap: object) -> tuple[str | None, str | None, str | None, str]:
        return (gap.entity_kind, gap.entity_id, gap.field, gap.civilisation or "")  # type: ignore[attr-defined]

    keys = [_unique_index_key(gap) for gap in result]
    assert result, (
        "expected at least one gap from this stream — an empty result passes the dedup check "
        "vacuously"
    )
    assert len(result) == len(set(keys)), (
        "forcing every participant onto one civilisation must not multiply an identical gap once "
        "per slot that referenced it — analysis_knowledge_gaps' own unique index "
        "(identity_digest, entity_kind, entity_id, field, coalesce(civilisation_id, '')) would "
        f"reject the second insert of any duplicate. Got {len(result)} gaps, {len(set(keys))} "
        f"distinct keys: {keys!r}"
    )


# ------------------------------------------------------------------------------------- T652v
#
# The recording's header carries each player's team (`ParticipantEntry.team`,
# `contracts/canonical-events.md`); this pass now supplies it as `query.Context.team`
# (`contracts/knowledge-base.md`, "Civilisation qualification" step 1 and "The query surface").
# Every test below builds its own small, synthetic `match-started` — real recordings' own teams
# are exercised by SC-007a (above) once the goldens carry `team`, but neither committed recording
# seats an unmodelled civilisation at all, so the unmodelled-teammate behaviour these tests are
# about has no real-recording instance to exercise it on.

#: Real raw civilisation ids from the promoted snapshot's own `[[civilisation_id]]` table
#: (`effects.toml`, T652g) — resolved with no override needed, exactly as SC-007a resolves them.
_FRANKS_RAW_ID = 2
_TEUTONS_RAW_ID = 4
_MALIANS_RAW_ID = 26

#: An arbitrary raw id no real civilisation ever carries (`test_query.py`'s own convention for a
#: synthetic id), resolved to "Saxons" — a real civilisation (added by build 185872) that no build
#: 180059 pack carries, so it is genuinely absent from `civilisations_modelled` (T773 models all 53
#: civilisations of that pack, which is why this was "Britons" until then) — only through this test
#: file's own `civilisation_names` override, the same seam `test_query.py`'s own
#: `test_a_teammate_outside_civilisations_modelled_gaps_naming_that_teammate` uses Saxons for.
_UNMODELLED_ALLY_RAW_ID = 900_101
_UNMODELLED_OPPONENT_RAW_ID = 900_102

#: "Siege Engineers" — real technology id `377`, `research_time = 45` in the committed pack.
#: Absent from Malians' own tech tree but present in Franks' (test_effects.py's own
#: `test_the_real_malians_university_team_bonus_reaches_every_ally_technology`), and one of the
#: selector entries Malians' "Universities work +80% faster" Team Bonus touches.
_SIEGE_ENGINEERS_ID = "377"

#: "Mill" — real building id `68`, cost `{wood: 100}` (module docstring above). No modelled
#: civilisation's effect touches it, and it is available to every civilisation, so it is this
#: section's "nothing at all should gap" building.
_TEST_TEAM_ALLIES = 10
_TEST_TEAM_OPPONENTS = 20


def _team_participant(slot: int, raw_civilisation: int, team: int | None) -> ParticipantEntry:
    return ParticipantEntry(slot=slot, civilisation=raw_civilisation, team=team)


def _team_match_started(*participants: ParticipantEntry) -> CanonicalEvent:
    return CanonicalEvent(
        clock_ms=0,
        kind=EventKind.MATCH_STARTED,
        payload=MatchStartedPayload(build=_BUILD, map_name="9", participants=participants),
    )


def _research_event(slot: int, technology_id: str, clock_ms: int = 1_000) -> CanonicalEvent:
    return CanonicalEvent(
        clock_ms=clock_ms,
        kind=EventKind.RESEARCH_QUEUED,
        participant=slot,
        payload=ResearchQueuedPayload(technology_id=int(technology_id), building_object=7),
    )


def _building_event(slot: int, building_id: str, clock_ms: int = 1_000) -> CanonicalEvent:
    return CanonicalEvent(
        clock_ms=clock_ms,
        kind=EventKind.BUILDING_PLACED,
        participant=slot,
        payload=BuildingPlacedPayload(building_id=int(building_id), position=Position(x=1, y=1)),
    )


@pytest.mark.parametrize(
    ("ally_raw_id", "ally_name", "expect_gap"),
    [
        (_TEUTONS_RAW_ID, "Teutons", False),  # the contrast: a modelled ally, no gap at all
        (_UNMODELLED_ALLY_RAW_ID, "Saxons", True),
    ],
)
def test_an_unmodelled_ally_gaps_every_cost_and_time_the_ally_modelled_answers(
    ally_raw_id: int, ally_name: str, expect_gap: bool
) -> None:
    """T652v: "make the coverage pass supply each participant's team as `Context.team`, so an
    unmodelled teammate gaps every cost and time for its allies" — contrast test, "the same stream
    with that ally modelled answers." Franks (slot 1) places a Mill (cost) and researches Siege
    Engineers (production_time); slot 2, on the same team, is either Teutons (modelled — the
    contrast, no gap at all) or an unmodelled civilisation (Saxons) — every one of Franks' cost
    and production_time queries must then gap, naming Saxons, cause `civilisation-not-modelled`,
    regardless of whether any real effect touches the Mill or Siege Engineers at all (step 1 fires
    before step 2/3 are ever reached)."""
    from aoe2stats_knowledge import coverage, gaps

    events = [
        _team_match_started(
            _team_participant(1, _FRANKS_RAW_ID, _TEST_TEAM_ALLIES),
            _team_participant(2, ally_raw_id, _TEST_TEAM_ALLIES),
        ),
        _building_event(1, _MILL_ID),
        _research_event(1, _SIEGE_ENGINEERS_ID),
    ]

    result = coverage.coverage(events, civilisation_names={_UNMODELLED_ALLY_RAW_ID: ally_name})

    franks_cost_and_time_gaps = [
        gap
        for gap in result
        if gap.field in ("cost", "production_time")
        and (gap.entity_kind, gap.entity_id) in {("building", _MILL_ID), ("technology", "377")}
    ]
    if not expect_gap:
        assert franks_cost_and_time_gaps == ([]), (
            f"a modelled ally must not gap Franks' own queries: {franks_cost_and_time_gaps!r}"
        )
        return

    assert len(franks_cost_and_time_gaps) == 4, (
        "both the Mill's and Siege Engineers' cost and production_time must all gap once Saxons "
        f"is an unmodelled ally, got {franks_cost_and_time_gaps!r}"
    )
    for gap in franks_cost_and_time_gaps:
        assert isinstance(gap, gaps.KnowledgeGap)
        assert gap.cause == "civilisation-not-modelled"
        assert gap.civilisation == "Saxons", (
            "the gap must name the unmodelled teammate, not Franks (which is itself modelled) — "
            f"got {gap.civilisation!r}"
        )


def test_two_allies_sharing_one_unmodelled_teammate_produce_one_gap_not_two() -> None:
    """T652v: "A gap naming an unmodelled teammate is the same row for every ally that raised it,
    so de-duplicate it against `analysis_knowledge_gaps`' unique index, as T652k did for slots."
    Franks (slot 1) and Teutons (slot 3) are both modelled and both on Saxons' (slot 2, unmodelled)
    team; both place a Mill (building 68), a real, shared, non-unique building both civilisations
    can build. Each of their two `cost` queries independently reaches "is every member of
    context.team modelled" and both name the same unmodelled teammate (Saxons) — the resulting
    `KnowledgeGap`s are equal on every column the unique index checks (`entity_kind`, `entity_id`,
    `field`, `civilisation`), even though they were raised by two different civilisations' own
    queries, so they must collapse to one row, not two."""
    from aoe2stats_knowledge import coverage

    events = [
        _team_match_started(
            _team_participant(1, _FRANKS_RAW_ID, _TEST_TEAM_ALLIES),
            _team_participant(2, _UNMODELLED_ALLY_RAW_ID, _TEST_TEAM_ALLIES),
            _team_participant(3, _TEUTONS_RAW_ID, _TEST_TEAM_ALLIES),
        ),
        _building_event(1, _MILL_ID),
        _building_event(3, _MILL_ID),
    ]

    result = coverage.coverage(events, civilisation_names={_UNMODELLED_ALLY_RAW_ID: "Saxons"})

    matching = [
        gap
        for gap in result
        if gap.entity_kind == "building"
        and gap.entity_id == _MILL_ID
        and gap.field == "cost"
        and gap.civilisation == "Saxons"
    ]
    assert len(matching) == 1, (
        "Franks' and Teutons' own, independent queries both name the same unmodelled teammate "
        f"(Saxons) for the same entity and field — expected exactly one row, got {matching!r}"
    )


def test_an_unmodelled_participant_does_not_gap_an_opposing_teams_queries() -> None:
    """T652v: "key it by civilisation and team" — an unmodelled civilisation on the *opposing*
    team must never leak into an unrelated team's own `context.team`. Franks (slot 1) is allied
    with Teutons (slot 2, modelled) on one team; an unmodelled civilisation (Saxons, slot 3) sits
    alone on the opposing team. If the pass ignored team boundaries and built `context.team` from
    every seated participant instead of only this participant's own team, Franks' and Teutons'
    queries would incorrectly gap, naming an opponent that is not their ally at all — this is the
    "not an opponent" half of "a team effect reaches an ally but not an opponent," at the coverage
    pass's own team-scoping, not at the effect layer (test_effects.py already covers the effect
    layer itself)."""
    from aoe2stats_knowledge import coverage

    events = [
        _team_match_started(
            _team_participant(1, _FRANKS_RAW_ID, _TEST_TEAM_ALLIES),
            _team_participant(2, _TEUTONS_RAW_ID, _TEST_TEAM_ALLIES),
            _team_participant(3, _UNMODELLED_OPPONENT_RAW_ID, _TEST_TEAM_OPPONENTS),
        ),
        _building_event(1, _MILL_ID),
        _building_event(2, _MILL_ID),
    ]

    result = coverage.coverage(
        events, civilisation_names={_UNMODELLED_OPPONENT_RAW_ID: "Byzantines"}
    )

    leaked = [gap for gap in result if gap.civilisation == "Byzantines" and gap.entity_id == "68"]
    assert leaked == [], (
        f"an unmodelled opponent must never gap an unrelated team's own queries — got {leaked!r}"
    )


#: A raw civilisation id no promoted snapshot's `[[civilisation_id]]` table carries (46 is the
#: Achaemenids, a Chronicles civilisation no pack has; it was 1 until T773 mapped the Britons for
#: build 180059), so the pass names it `unknown-civilisation-46` - an ally that is not modelled and
#: cannot be.
_UNMAPPED_RAW_ID = 46

#: Recording 2 seats Franks (slot 1) and Teutons (slot 3) on one team, Persians and Tatars on the
#: other.
_RECORDING_2_FRANKS_SLOT = 1
_RECORDING_2_TEUTONS_SLOT = 3


def _recording_2_franks_with_slot_3_as(raw_civilisation: int) -> list[CanonicalEvent]:
    """Recording 2's golden stream, as a test-local copy: slot 3's seat is given
    `raw_civilisation` and slot 3's own events are dropped, so that every query about the unmapped
    civilisation is one Franks' entities raised (slot 3 would otherwise raise its own, naming the
    same civilisation, and the two could not be told apart). The fixture file is never touched."""
    events = _load_golden_stream(_GOLDEN_CANONICAL_STREAMS[1])
    rebuilt: list[CanonicalEvent] = []
    for event in events:
        if event.participant == _RECORDING_2_TEUTONS_SLOT:
            continue
        if event.kind is EventKind.MATCH_STARTED:
            payload = event.payload
            assert isinstance(payload, MatchStartedPayload)
            seated = {participant.slot: participant for participant in payload.participants}
            assert seated[_RECORDING_2_FRANKS_SLOT].team == seated[_RECORDING_2_TEUTONS_SLOT].team
            event = dataclasses.replace(
                event,
                payload=dataclasses.replace(
                    payload,
                    participants=tuple(
                        dataclasses.replace(participant, civilisation=raw_civilisation)
                        if participant.slot == _RECORDING_2_TEUTONS_SLOT
                        else participant
                        for participant in payload.participants
                    ),
                ),
            )
        rebuilt.append(event)
    return rebuilt


def _franks_resolved_entities(events: list[CanonicalEvent]) -> set[tuple[str, str]]:
    """Every entity slot 1 (Franks) referenced. Building 490, which the pack does not name, is the
    Gate through a transcribed alias in build 180059's snapshot since T773 (FR-022d), so it answers
    like any other entity and is among them."""
    entities: set[tuple[str, str]] = set()
    for event in events:
        if event.participant != _RECORDING_2_FRANKS_SLOT:
            continue
        payload = event.payload
        if event.kind is EventKind.UNIT_QUEUED and isinstance(payload, UnitQueuedPayload):
            entities.add(("unit", str(payload.unit_id)))
        elif event.kind is EventKind.BUILDING_PLACED and isinstance(payload, BuildingPlacedPayload):
            entities.add(("building", str(payload.building_id)))
        elif event.kind is EventKind.RESEARCH_QUEUED and isinstance(payload, ResearchQueuedPayload):
            entities.add(("technology", str(payload.technology_id)))
    return entities


def test_an_unmodelled_ally_in_a_committed_recording_gaps_produced_at_and_available_to() -> None:
    """The coverage pass passes `team` to `produced_at` and `available_to` as it does to `cost` and
    `production_time` (T764, T763): an unknown teammate's team bonus could touch any field, so the
    refusal of contracts/knowledge-base.md ("Civilisation qualification", step 1) applies to every
    field that accepts a context. Recording 2's Teutons ally of Franks is given a raw civilisation
    id the snapshot does not map; every entity Franks referenced then gaps both fields, naming the
    unmodelled teammate, `produced_at` blocking and `available_to` informational (the register's
    severity, not this test's)."""
    from aoe2stats_knowledge import coverage, gaps

    events = _recording_2_franks_with_slot_3_as(_UNMAPPED_RAW_ID)
    expected = _franks_resolved_entities(events)
    assert expected, "Franks must reference entities the pack names, or this proves nothing"

    result = coverage.coverage(events)

    for field_name, severity in (
        ("produced_at", gaps.BLOCKING),
        ("available_to", "informational"),
        ("age_requirement", "informational"),
    ):
        refused = [
            gap
            for gap in result
            if gap.field == field_name and gap.civilisation == "unknown-civilisation-46"
        ]
        assert {(gap.entity_kind, gap.entity_id) for gap in refused} == expected, (
            f"{field_name}: every entity Franks referenced must gap once, naming the unmodelled "
            f"teammate; got {sorted((gap.entity_kind, gap.entity_id) for gap in refused)!r}"
        )
        assert {gap.cause for gap in refused} == {"civilisation-not-modelled"}
        assert {gap.severity for gap in refused} == {severity}, field_name


def test_the_same_recording_with_every_slot_modelled_has_no_such_gaps() -> None:
    """The contrast: the stream of the test above with slot 3 left as the Teutons it is. Franks'
    entities gap neither field: building 490, which the pack does not name, is the Gate through the
    snapshot's alias since T773, and answers like the rest."""
    from aoe2stats_knowledge import coverage

    events = _recording_2_franks_with_slot_3_as(_TEUTONS_RAW_ID)

    result = coverage.coverage(events)

    on_the_two_fields = [gap for gap in result if gap.field in ("produced_at", "available_to")]
    assert on_the_two_fields == [], on_the_two_fields
    assert not [gap for gap in result if gap.cause == "entity-absent"], "490 is the Gate now"


def test_ffa_or_unset_team_does_not_make_two_participants_allies() -> None:
    """T652v: "A free-for-all or unset team is its own value, never team 0 shared by strangers."
    Two participants each carry `team=None` (the adapter's own translation of the recording's "no
    team" sentinel, `contracts/canonical-events.md`) — Franks (modelled) and an unmodelled
    civilisation (Saxons). Both being `None` must never read as sharing a team: Franks' own
    queries must not gap on Saxons' account, and `_context_for`'s own "a participant with no team
    gets a team of itself alone" must hold even when a *different* participant, elsewhere in the
    same stream, also carries `None`."""
    from aoe2stats_knowledge import coverage

    events = [
        _team_match_started(
            _team_participant(1, _FRANKS_RAW_ID, None),
            _team_participant(2, _UNMODELLED_ALLY_RAW_ID, None),
        ),
        _building_event(1, _MILL_ID),
    ]

    result = coverage.coverage(events, civilisation_names={_UNMODELLED_ALLY_RAW_ID: "Saxons"})

    leaked = [gap for gap in result if gap.civilisation == "Saxons"]
    assert leaked == [], (
        "two participants who each individually carry team=None must never be read as allies of "
        f"one another — got {leaked!r}"
    )


def test_coverage_threads_each_participants_real_team_into_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T652v: "a Malians-ally team effect reaching an ally but not an opponent through the
    coverage pass" — `coverage.coverage`'s own gap-list output cannot distinguish "the effect
    applied" from "the effect structurally matched but did not apply" (both resolve with no gap,
    contracts/knowledge-base.md: "Its output is the gap list the document publishes"), so this
    spies on `effects.apply`'s own `context` argument — the exact value the coverage pass threads
    through `query.py` into the effect layer — rather than on `coverage.coverage`'s return value.
    Franks (slot 1) is Malians' (slot 2) ally; Teutons (slot 3) is the opponent, on the other team.
    All three research Siege Engineers (377), one of Malians' University Team Bonus's own selector
    entries (test_effects.py). Franks' own call must carry `context.team == {"Malians", "Franks"}`
    (the ally reached) and Teutons' own call must carry `context.team == {"Teutons"}` — Malians
    excluded, because Teutons is the opponent, not the ally."""
    from aoe2stats_knowledge import coverage, effects, query

    real_apply = effects.apply
    calls: list[tuple[str, query.Context | None]] = []

    def _spy(
        directory: str,
        *,
        civilisation: str,
        kind: str,
        id: str,
        field: str,
        value: object,
        context: query.Context | None = None,
    ) -> object:
        calls.append((civilisation, context))
        return real_apply(
            directory,
            civilisation=civilisation,
            kind=kind,
            id=id,
            field=field,
            value=value,
            context=context,
        )

    monkeypatch.setattr(effects, "apply", _spy)

    events = [
        _team_match_started(
            _team_participant(1, _FRANKS_RAW_ID, _TEST_TEAM_ALLIES),
            _team_participant(2, _MALIANS_RAW_ID, _TEST_TEAM_ALLIES),
            _team_participant(3, _TEUTONS_RAW_ID, _TEST_TEAM_OPPONENTS),
        ),
        _research_event(1, _SIEGE_ENGINEERS_ID),
        _research_event(3, _SIEGE_ENGINEERS_ID),
    ]

    coverage.coverage(events)

    franks_contexts = [context for civilisation, context in calls if civilisation == "Franks"]
    teutons_contexts = [context for civilisation, context in calls if civilisation == "Teutons"]
    assert any(
        context is not None and context.team == frozenset({"Malians", "Franks"})
        for context in franks_contexts
    ), f"Franks' own call must carry its real Malians ally: {franks_contexts!r}"
    assert any(
        context is not None and context.team == frozenset({"Teutons"})
        for context in teutons_contexts
    ), f"Teutons' own call must not carry Malians at all — it is the opponent: {teutons_contexts!r}"


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
                participants=(
                    ParticipantEntry(slot=1, civilisation=_SYNTHETIC_CIVILISATION_ID, team=None),
                ),
            ),
        ),
        CanonicalEvent(
            clock_ms=1_000,
            kind=EventKind.UNIT_QUEUED,
            participant=1,
            payload=UnitQueuedPayload(
                unit_id=_UNRESOLVED_UNIT_ID_PLACEHOLDER,
                building_type=12,
                building_object=5001,
                count=1,
            ),
        ),
    ]

    result = coverage.coverage(stream, civilisation_names={_SYNTHETIC_CIVILISATION_ID: "Franks"})

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
                participants=(
                    ParticipantEntry(slot=1, civilisation=_SYNTHETIC_CIVILISATION_ID, team=None),
                ),
            ),
        ),
        CanonicalEvent(
            clock_ms=1_000,
            kind=EventKind.UNIT_QUEUED,
            participant=1,
            payload=UnitQueuedPayload(
                unit_id=_UNRESOLVED_UNIT_ID_PLACEHOLDER,
                building_type=12,
                building_object=5001,
                count=1,
            ),
        ),
        CanonicalEvent(
            clock_ms=2_000,
            kind=EventKind.UNIT_QUEUED,
            participant=1,
            payload=UnitQueuedPayload(
                unit_id=_UNRESOLVED_UNIT_ID_PLACEHOLDER,
                building_type=87,
                building_object=5002,
                count=1,
            ),
        ),
    ]

    result = coverage.coverage(stream, civilisation_names={_SYNTHETIC_CIVILISATION_ID: "Franks"})

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
                participants=(
                    ParticipantEntry(slot=1, civilisation=_SYNTHETIC_CIVILISATION_ID, team=None),
                ),
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
