"""T648: the coverage pass over a canonical stream (FR-038; contracts/knowledge-base.md, "Gaps";
research.md **D7**; data-model.md §7 "Knowledge gap").

**What this module does, exactly.** `coverage()` walks a canonical event stream once, collects
every entity a participant referenced (a unit trained, a building placed, a technology researched)
together with that participant's civilisation, and — for every field any *live* register datum
requires (`register.toml`'s closed `requires_knowledge` vocabulary, minus `line_of_sight`, which
belongs to a different reconstruction domain and is `gaps.py`'s own concern; see below) — calls
`query.py`'s matching civilisation-qualified **public** function directly to ask whether that
(entity, civilisation) pair resolves (T652b: previously this module re-resolved the snapshot and
the entity, and re-checked civilisation modelling, itself, through privately imported internals —
see "Calling the query surface, not reimplementing it" below for why that changed). Every refusal
becomes one `gaps.KnowledgeGap` in the returned sequence; every resolution contributes nothing to
it. **FR-038** is enforced by construction, not by a check anywhere in this module: there is no
branch here that catches a gap and substitutes a value, a default, an average or a neighbouring
answer for it — a query either resolves for real or its refusal is recorded, and the loop moves on
to the next field.

**The six fields this pass asks about, and why exactly these six.** `packages/core/src/
aoe2stats_core/truth/register.toml`'s `requires_knowledge` vocabulary is, read directly (there is
no third field this repository's register ever names): `cost`, `production_time`, `produced_at`,
`age_requirement`, `prerequisites`, `available_to` and `line_of_sight`. The first six are exactly
`query.py`'s civilisation-qualified query surface (`cost`, `production_time`, `age_requirement`,
`prerequisites`, `produced_at`, `available_to` — `query.py`'s own module docstring). `line_of_sight`
names no query this package exposes at all: it belongs to map control and exploration, blocked on
the unread starting state (research.md D1), which is feature 007's territory, not this package's —
`gaps.py`'s own `test_gaps.py` already exercises `line_of_sight`'s severity computation directly,
so this pass does not have to ask about it to make that field's severity real. `query.py`'s seventh
public function, `name()`, is not civilisation-qualified at all (the one exception the contract
carves out explicitly) and never gaps for a reason this pass could usefully collect, so it is out
of scope for gap collection too.

**Entities collected, and from which event kind.** A canonical stream's three "a participant
referenced this entity" event kinds each name one `rules.json` entity kind directly:
`unit-queued` (`UnitQueuedPayload.unit_id`) is a unit, `building-placed`
(`BuildingPlacedPayload.building_id`) is a building, `research-queued`
(`ResearchQueuedPayload.technology_id`) is a technology. `match-started`
(`MatchStartedPayload.participants`, one `ParticipantEntry` per seated slot) is where a
participant's own raw, engine-native civilisation integer is read (`ParticipantEntry.civilisation`
— "the game's integer civilisation identifier, never a name: naming is the knowledge base's job,
not the adapter's", `events.py`'s own comment) and where the build every entity in the stream
resolves against is read (`MatchStartedPayload.build`) — a canonical stream carries exactly one
match and therefore one build; every entity collected resolves against it.

**Civilisation-name resolution — `civilisation_names`, and the real default it stands in for.**
`query.py`'s six query-surface functions require a civilisation **name** string
(`"Byzantines"`, ...), never the replay's raw integer — but nothing else in this repository
translates that integer into a name, because until this task nothing needed to (T629a: "naming is
the knowledge base's job, not the adapter's"; `query.py`'s own docstring, verified directly against
this pack: `aoe2techtree`'s `data.json` civilisation entries carry no numeric id in any form, and
the replay header decodes no name from one either). `civilisation_names`, keyword-only and
optional, is the seam a caller may use to supply that translation directly (SC-007's synthetic
test, whose one participant's raw id is deliberately not a real replay value at all). Left `None`
— every real, production caller's case — `_DEFAULT_CIVILISATION_NAMES` below is used instead: the
real, measured translation this task had to establish, because SC-007a runs `coverage()` over both
committed recordings with no override at all.

**How `_DEFAULT_CIVILISATION_NAMES` was actually measured, not guessed.** The replay's own raw
civilisation integer is, empirically, a third numbering space unrelated to either one already used
elsewhere in this repository — not Relic's `civilization_id` (`apps/api/src/aoe2stats_api/
civilizations.py`), and not `aoe2techtree`'s own alphabetical ordering. `snapshots/
aoe2techtree-180059/effects.toml`'s own T645 header comment already proved this for the
second committed recording by direct measurement: raw id 4 trains unit 25 ("Teutonic Knight",
Teutons' unique unit, held by no other civilisation in `data.json`), while raw id 4 in both other
numbering schemes names "Bohemians". This module's table extends that same measurement — reading
each committed golden canonical stream's own `match-started` payload and `unit-queued`/
`research-queued` entities directly, cross-checked against `packages/knowledge/packs/
aoe2techtree/data.json`'s per-civilisation `Unit`/`Tech` arrays and, where `data.json`'s flattened
membership needed a second opinion, the per-civilisation tree files' own `node_status`
(`ResearchedCompleted` vs `NotAvailable`) — for the two raw ids T645 did not itself resolve to a
slot (both committed recordings' first fixture, and the second fixture's remaining two slots):

  - **`AgeIIDE_Replay_500546441.zip` (raw ids 9 and 26).** Neither participant trains or researches
    a unique unit or technology of either civilisation research.md D5 already named for this
    recording (Byzantines, Koreans), so entity-exclusivity alone (T645's method for the second
    recording) is silent here. The discriminator instead comes from each civilisation's own,
    already-divergent **tech-tree availability**, read directly from `trees/BYZANTINES.json` and
    `trees/KOREANS.json`: participant 1 (raw id 9) researches technology 377 ("Siege Engineers"),
    `node_status = "ResearchedCompleted"` in `KOREANS.json` and `"NotAvailable"` in
    `BYZANTINES.json` — only a Korean player could have researched it. Participant 2 (raw id 26)
    researches technology 80 ("Plate Barding Armor"), `"ResearchedCompleted"` in `BYZANTINES.json`
    and `"NotAvailable"` in `KOREANS.json` — only a Byzantine player could have researched it. The
    two readings agree with each other (one participant per civilisation, no overlap) and with
    research.md D5's "both players trained units their civilisation discounts": raw id 9 is
    therefore **Koreans**, raw id 26 is **Byzantines**.
  - **`AgeIIDE_Replay_504695319.zip` (raw ids 2, 8, 4, 33).** `effects.toml`'s T645 comment already
    fixes two of the four by slot: slot 1 (raw id 2) is **Franks** (unit 281, "Throwing Axeman";
    technology 83, "Bearded Axe" — both exclusively Franks' in `data.json`) and slot 3 (raw id 4)
    is **Teutons** (unit 25, "Teutonic Knight"; technology 489, "Ironclad" — both exclusively
    Teutons'). It names Persians and Gurjaras as the recording's other two civilisations without
    committing either to slot 2 or slot 4, because T645's own deliverable was the snapshot's
    *civilisation set*, not a slot table — this task is the first that needs the slot-level split,
    and had to measure it directly, including the one genuine complication `effects.toml` had
    already flagged in prose ("one 'Camel Scout' production run ... attributed to ... a
    Persians-castle participant"): read directly against the golden canonical stream, participant 2
    (raw id 8) is recorded training unit 1755 ("Camel Scout") **27 times across five distinct
    Stable objects** spanning the match (`data.json`: id 1755 is owned by Gurjaras alone, of all
    sixty-one civilisations in the pack — the same exclusivity test T645 used) — evidence far too
    voluminous and sustained to be the stray, single-event misattribution `effects.toml`'s prose
    describes, so participant 2 is **Gurjaras**. The same participant's canonical stream also
    carries a smaller cluster of Persians-exclusive activity (technology 488 "Kamandaran", unit 239
    "War Elephant", unit 38 "Knight" — the last of these both `ResearchedCompleted` for Persians
    and, tellingly, `NotAvailable` for Gurjaras in `trees/GURJARAS.json`, which cannot train a
    Knight at all — a genuine, mechanically impossible combination for one real civilisation to
    have produced itself), all issued from a single Castle object (20802): this is read as the
    documented adapter/wheel misattribution research.md D11 already records for this exact
    recording ("an action kind the wheel does not name at all"), not as evidence Gurjaras is wrong.
    Participant 4 (raw id 33) trains unit 39 ("Cavalry Archer", `ResearchedCompleted` for Persians
    and `NotAvailable` for Gurjaras in the same two tree files) and researches technology 687
    ("Silk Armor", exclusively Tatars' — the single, uncorroborated anomaly `effects.toml` already
    dismisses: "not corroborated by any second signal, unlike every civilisation actually modelled
    below"). With Tatars excluded on that same, already-recorded basis, and Gurjaras fixed to
    participant 2 above, participant 4 is **Persians** by elimination as well as by its own
    Persians-available, Gurjaras-unavailable unit — raw id 8 is therefore **Gurjaras**, raw id 33
    is **Persians**.

A raw id this table does not name (any civilisation this package has not modelled, per
`snapshot.toml`'s `civilisations_modelled`) resolves to a placeholder that can never collide with a
real, modelled name (`f"unknown-civilisation-{raw_id}"`), so every query for it refuses at
`query.py`'s own "is this civilisation modelled" step (`cause="civilisation-not-modelled"`) rather
than this module ever guessing a name a wrong guess could make look confidently, silently wrong.

**Calling the query surface, not reimplementing it (T652b).** Before this task, this module
re-resolved a build's snapshot, looked its entity up in `rules.json` and re-checked whether the
civilisation was modelled itself, through `query.py`'s privately imported internals
(`_civilisations_modelled`, `_raw_value_for_field`, `_rules`) — restating
`query._civilisation_qualified`'s whole step order in this module's own `_gap_for`, and duplicating
`query._TIME_FIELDS` under a second name. SC-008's "by construction rather than by inspection" is a
claim that the answer-or-gap union `query.py`'s six public functions return is the *only* route to
a value or a gap in this package; a pass that produced the published gap list some other way was
not taking it, no matter how faithfully it mirrored the same steps. This module now builds one
`query.EntityRef` per (entity, build) pair and calls `query.cost`, `query.production_time`,
`query.age_requirement`, `query.prerequisites`, `query.produced_at` and `query.available_to`
directly — `_QUERY_SURFACE_FUNCTIONS` below — collecting whichever of the two-branch union's gap
branch each call returns. `rules_overrides` (SC-007's own seam) is threaded through as
`query.rules_overrides`, a context manager `query.py` itself now exposes for exactly this purpose,
rather than a second, parallel field-lookup path in this module.

**Resolving the build once, not once per (entity, field) pair (T652b).** `snapshot.snapshot_for`
is not re-called by this module for each of the (potentially many) query calls it makes: the build
named in the stream's own `match-started` event is resolved exactly once, before any entity is
even considered, specifically so a build with no promoted snapshot at all is reported as **one**
`gaps.KnowledgeGap(cause="no-snapshot-for-build")`, never one per (entity, field) pair asked about
it (every one of those would be identical — `gaps.py`'s `_WHOLE_BUILD_CAUSES` names no entity,
field or civilisation at all, so nothing distinguishes them — and `analysis_knowledge_gaps`' own
unique index, `(identity_digest, entity_kind, entity_id, field, coalesce(civilisation_id, ''))`,
would then reject every one after the first as a duplicate insert). This is checked, and the single
gap returned, whether or not the stream references any entity at all: FR-027's "the absence MUST
be recorded as a gap" does not depend on what, if anything, was trained — only on the build itself
being unresolvable. A stream that names no build at all (`_NO_BUILD_KNOWN` below) is the same
ignorance wearing different clothes and is reported identically, for the same reason.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Final

from aoe2stats_core.replay.events import (
    BuildingPlacedPayload,
    CanonicalEvent,
    EventKind,
    MatchStartedPayload,
    ResearchQueuedPayload,
    UnitQueuedPayload,
)
from aoe2stats_knowledge import gaps, query, snapshot

#: T652b (a): a stream whose `match-started` event carries no build at all (`MatchStartedPayload.
#: build: int | None` allows this, distinct from a real build integer with no promoted snapshot,
#: which `snapshot.snapshot_for` already reports) still has nothing honest to check any entity
#: against, so it is reported the same way. `gaps.KnowledgeGap.build` is a required `int` with no
#: default, so this module needs a real int to hand it even here; `-1` is never a real Age II DE
#: build number (every one in this repository, and every real replay header, is positive) and, in
#: particular, is never `packages/knowledge/snapshots/aoe2techtree-test-stub`'s own deliberately
#: fake `describes_build = 0` — so this sentinel cannot be mistaken for, or collide with, any real
#: or placeholder build a future snapshot might describe.
_NO_BUILD_KNOWN: Final[int] = -1

#: `query.py`'s six civilisation-qualified public functions, called directly (T652b) rather than
#: reimplemented — `register.toml`'s `requires_knowledge` vocabulary minus `line_of_sight` (this
#: module's own docstring explains why: a different reconstruction domain, already exercised
#: directly by `gaps.py`'s own tests). The field name is kept alongside each function only for this
#: tuple's own readability; nothing in `coverage()` reads it back out.
_QUERY_SURFACE_FUNCTIONS: Final[tuple[tuple[str, Any], ...]] = (
    ("cost", query.cost),
    ("production_time", query.production_time),
    ("age_requirement", query.age_requirement),
    ("prerequisites", query.prerequisites),
    ("produced_at", query.produced_at),
    ("available_to", query.available_to),
)

#: research.md D11 / `effects.toml`'s T645 header comment; this module's own docstring records the
#: measurement in full, including the one recording whose split T645 itself left unresolved.
_DEFAULT_CIVILISATION_NAMES: Final[Mapping[int, str]] = {
    2: "Franks",
    4: "Teutons",
    8: "Gurjaras",
    9: "Koreans",
    26: "Byzantines",
    33: "Persians",
}


def _civilisation_name_for(raw_id: int, civilisation_names: Mapping[int, str] | None) -> str:
    if civilisation_names is not None and raw_id in civilisation_names:
        return civilisation_names[raw_id]
    if raw_id in _DEFAULT_CIVILISATION_NAMES:
        return _DEFAULT_CIVILISATION_NAMES[raw_id]
    # Never a guess: a name shaped so it can never collide with a real, modelled civilisation name,
    # so every query for it refuses at query.py's own "is this civilisation modelled" step
    # (FR-038 — no default, no nearest, no fabricated identity).
    return f"unknown-civilisation-{raw_id}"


def coverage(
    events: Iterable[CanonicalEvent],
    *,
    civilisation_names: Mapping[int, str] | None = None,
    rules_overrides: Mapping[int, Mapping[str, Any]] | None = None,
) -> Sequence[gaps.KnowledgeGap]:
    """Walk `events` once, collect every entity a participant referenced and every participant's
    civilisation, and ask, for every one of `query.py`'s six query-surface fields, whether that
    (entity, civilisation) pair resolves. The return value is the gap list alone — every resolved
    value is simply not reported, never returned alongside the gaps (contracts/knowledge-base.md:
    "Its output is the gap list the document publishes"). See this module's docstring for the field
    vocabulary, the civilisation-name resolution, why the build is resolved exactly once, and the
    `rules_overrides` seam.
    """
    build: int | None = None
    raw_civilisation_by_slot: dict[int, int] = {}
    entities_by_slot: dict[int, set[tuple[str, str]]] = {}

    for event in events:
        if event.kind is EventKind.MATCH_STARTED and isinstance(event.payload, MatchStartedPayload):
            if event.payload.build is not None:
                build = event.payload.build
            for participant in event.payload.participants:
                raw_civilisation_by_slot[participant.slot] = participant.civilisation
            continue

        slot = event.participant
        if slot is None:
            continue

        payload = event.payload
        entity: tuple[str, str] | None = None
        if event.kind is EventKind.UNIT_QUEUED and isinstance(payload, UnitQueuedPayload):
            entity = ("unit", str(payload.unit_id))
        elif event.kind is EventKind.BUILDING_PLACED and isinstance(payload, BuildingPlacedPayload):
            entity = ("building", str(payload.building_id))
        elif event.kind is EventKind.RESEARCH_QUEUED and isinstance(payload, ResearchQueuedPayload):
            entity = ("technology", str(payload.technology_id))

        if entity is not None:
            entities_by_slot.setdefault(slot, set()).add(entity)

    if build is None:
        # (a): no build at all was ever named in the stream — see _NO_BUILD_KNOWN's own docstring.
        return (gaps.KnowledgeGap(cause="no-snapshot-for-build", build=_NO_BUILD_KNOWN),)

    resolved = snapshot.snapshot_for(build)
    if isinstance(resolved, gaps.KnowledgeGap):
        # (b): resolved exactly once for the whole stream, before any entity loop, so an
        # unresolvable build is reported once — never once per (entity, field) pair — and reported
        # whether or not the stream references any entity at all (module docstring).
        return (resolved,)

    result: list[gaps.KnowledgeGap] = []
    override_context = (
        query.rules_overrides(rules_overrides)
        if rules_overrides is not None
        else contextlib.nullcontext()
    )
    with override_context:
        for slot in sorted(entities_by_slot):
            raw_civilisation = raw_civilisation_by_slot.get(slot)
            if raw_civilisation is None:
                # A participant with no seated civilisation at all (never seen in `match-started`)
                # — nothing to qualify a query by, so this participant's entities are skipped
                # rather than qualified by a fabricated civilisation.
                continue
            civilisation = _civilisation_name_for(raw_civilisation, civilisation_names)
            for entity_kind, entity_id in sorted(entities_by_slot[slot]):
                entity_ref = query.EntityRef(kind=entity_kind, id=entity_id, build=build)
                for _field_name, query_function in _QUERY_SURFACE_FUNCTIONS:
                    answer_or_gap = query_function(entity_ref, civilisation=civilisation)
                    if isinstance(answer_or_gap, gaps.KnowledgeGap):
                        result.append(answer_or_gap)

    return tuple(result)
