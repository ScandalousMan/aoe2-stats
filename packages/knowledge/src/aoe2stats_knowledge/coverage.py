"""T648: the coverage pass over a canonical stream (FR-038; contracts/knowledge-base.md, "Gaps";
research.md **D7**; data-model.md §7 "Knowledge gap").

**What this module does, exactly.** `coverage()` walks a canonical event stream once, collects
every entity a participant referenced (a unit trained, a building placed, a technology researched)
together with that participant's civilisation, and — for every field any *live* register datum
requires (`register.toml`'s closed `requires_knowledge` vocabulary, minus `line_of_sight`, which
belongs to a different reconstruction domain and is `gaps.py`'s own concern; see below) — asks
`query.py`'s matching civilisation-qualified function whether that (entity, civilisation) pair
resolves. Every refusal becomes one `gaps.KnowledgeGap` in the returned sequence; every resolution
contributes nothing to it. **FR-038** is enforced by construction, not by a check anywhere in this
module: there is no branch here that catches a gap and substitutes a value, a default, an average
or a neighbouring answer for it — a query either resolves for real or its refusal is recorded, and
the loop moves on to the next field.

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

**`rules_overrides` — the seam SC-007 needs, and why field-level resolution is reimplemented here
rather than delegated whole to `query.py`.** `query.py`'s six functions read a build's `rules.json`
through their own private, `functools.cache`d `_rules(directory)`, unconditionally from the
packaged snapshot — there is no parameter through which a caller could substitute a different rules
mapping, and this task may not add one (`query.py`'s core logic is out of scope for this task).
`rules_overrides`, keyed by build, is this module's own substitute: when present for the build an
entity resolves against, its mapping is read in `_rules(directory)`'s place for that entity's
lookup; every other resolution step — is the civilisation modelled, which effects apply — still
reads the real, packaged snapshot (`query._civilisations_modelled`, `effects.apply`), because
`rules_overrides` only ever stands in for the parsed `rules.json` body, never for `snapshot.toml`
or `effects.toml`. This is also why `field-absent` (data-model.md §7's fifth, previously
unproduced cause — `gaps.py`'s own docstring: "kept in the closed set because data-model.md already
closes it there ... rather than a name with no test") is produced here and not in `query.py`:
`query._raw_value_for_field` already defaults rather than gapping when a field key is absent from
an entity's own record (`record.get("cost", {})`), a narrower, pre-existing behaviour this task
does not change; this module checks presence itself, *before* reading the value, so a field a
caller's override genuinely deleted is reported as missing rather than silently read back as an
empty default — precisely the FR-038 substitution this whole pass exists to refuse.
"""

from __future__ import annotations

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
from aoe2stats_knowledge import effects, gaps, snapshot
from aoe2stats_knowledge.query import _civilisations_modelled, _raw_value_for_field, _rules

#: `register.toml`'s closed `requires_knowledge` vocabulary, minus `line_of_sight` (this module's
#: own docstring explains why: a different reconstruction domain, already exercised directly by
#: `gaps.py`'s own tests). Exactly `query.py`'s six civilisation-qualified query-surface fields.
_QUERY_SURFACE_FIELDS: Final[tuple[str, ...]] = (
    "cost",
    "production_time",
    "age_requirement",
    "prerequisites",
    "produced_at",
    "available_to",
)

#: `rules.json`'s own field name(s) a query-level field reads from an entity's record — the same
#: vocabulary `query._raw_value_for_field` reads, duplicated here only for the *presence* check
#: that function does not perform (see the module docstring's `rules_overrides` section for why
#: that check belongs to this module and not to `query.py`). `available_to` has no stored field of
#: its own at all: resolving the entity already proves the baseline pack carries it (the same
#: reasoning `query._raw_value_for_field` states for its own `available_to` branch), so it is
#: never reported absent.
_TIME_FIELDS: Final[tuple[str, ...]] = ("training_time", "construction_time", "research_time")


def _field_present(record: Mapping[str, Any], field_name: str) -> bool:
    if field_name == "cost":
        return "cost" in record
    if field_name == "production_time":
        return any(time_field in record for time_field in _TIME_FIELDS)
    if field_name == "age_requirement":
        return "age_requirement" in record
    if field_name == "prerequisites":
        return "prerequisites" in record
    if field_name == "produced_at":
        return "produced_at" in record
    if field_name == "available_to":
        return True
    raise AssertionError(f"unreachable: unknown field_name {field_name!r}")  # pragma: no cover


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


def _entity_record(
    *,
    build: int,
    directory: str,
    entity_kind: str,
    entity_id: str,
    rules_overrides: Mapping[int, Mapping[str, Any]] | None,
) -> Mapping[str, Any] | None:
    if rules_overrides is not None and build in rules_overrides:
        rules_mapping = rules_overrides[build]
    else:
        rules_mapping = _rules(directory)
    entities: Mapping[str, Any] = rules_mapping.get("entities", {})
    kind_table: Mapping[str, Any] = entities.get(entity_kind, {})
    record: Mapping[str, Any] | None = kind_table.get(entity_id)
    return record


def _gap_for(
    *,
    build: int,
    entity_kind: str,
    entity_id: str,
    field_name: str,
    civilisation: str,
    rules_overrides: Mapping[int, Mapping[str, Any]] | None,
) -> gaps.KnowledgeGap | None:
    """One (entity, field, civilisation) check: resolve the snapshot, the entity, the field's
    presence, whether the civilisation is modelled and, finally, effect application — returning
    the first `gaps.KnowledgeGap` any of those steps produces, or `None` once every step actually
    resolves. Mirrors `query.py`'s own `_civilisation_qualified` step order (contracts/
    knowledge-base.md, "Civilisation qualification") with one addition, the field-presence check,
    inserted ahead of the value read it guards (this module's own docstring explains why that
    check lives here and not in `query.py`).
    """
    resolved = snapshot.snapshot_for(build)
    if isinstance(resolved, gaps.KnowledgeGap):
        return resolved

    record = _entity_record(
        build=build,
        directory=resolved.directory,
        entity_kind=entity_kind,
        entity_id=entity_id,
        rules_overrides=rules_overrides,
    )
    if record is None:
        return gaps.KnowledgeGap(
            cause="entity-absent",
            build=build,
            entity_kind=entity_kind,
            entity_id=entity_id,
            field=field_name,
            civilisation=civilisation,
        )

    if civilisation not in _civilisations_modelled(resolved.directory):
        return gaps.KnowledgeGap(
            cause="civilisation-not-modelled",
            build=build,
            entity_kind=entity_kind,
            entity_id=entity_id,
            field=field_name,
            civilisation=civilisation,
        )

    if not _field_present(record, field_name):
        return gaps.KnowledgeGap(
            cause="field-absent",
            build=build,
            entity_kind=entity_kind,
            entity_id=entity_id,
            field=field_name,
            civilisation=civilisation,
        )

    baseline = _raw_value_for_field(record, field_name)
    applied = effects.apply(
        resolved.directory,
        civilisation=civilisation,
        kind=entity_kind,
        id=entity_id,
        field=field_name,
        value=baseline,
    )
    if isinstance(applied, effects.EffectNotModelled):
        return gaps.KnowledgeGap(
            cause="effect-not-modelled",
            build=build,
            entity_kind=entity_kind,
            entity_id=entity_id,
            field=field_name,
            civilisation=civilisation,
            detail=applied.reason,
        )
    return None


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
    vocabulary, the civilisation-name resolution and the `rules_overrides` seam.
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
        # Nothing about which build to resolve against is known — no entity in the stream can be
        # sensibly checked against anything, so there is nothing honest to report (never a guessed
        # build, FR-038's own spirit for the one input this pass cannot substitute for either).
        return ()

    result: list[gaps.KnowledgeGap] = []
    for slot in sorted(entities_by_slot):
        raw_civilisation = raw_civilisation_by_slot.get(slot)
        if raw_civilisation is None:
            # A participant with no seated civilisation at all (never seen in `match-started`) —
            # nothing to qualify a query by, so this participant's entities are skipped rather than
            # qualified by a fabricated civilisation.
            continue
        civilisation = _civilisation_name_for(raw_civilisation, civilisation_names)
        for entity_kind, entity_id in sorted(entities_by_slot[slot]):
            for field_name in _QUERY_SURFACE_FIELDS:
                gap = _gap_for(
                    build=build,
                    entity_kind=entity_kind,
                    entity_id=entity_id,
                    field_name=field_name,
                    civilisation=civilisation,
                    rules_overrides=rules_overrides,
                )
                if gap is not None:
                    result.append(gap)

    return tuple(result)
