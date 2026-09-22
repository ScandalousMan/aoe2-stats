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
— every real, production caller's case — the resolved build's own snapshot is asked instead
(**T652g**, below), the real, measured translation this task had to establish, because SC-007a
runs `coverage()` over both committed recordings with no override at all.

**T652g: the translation lives in the snapshot, not in this module.** Before this task this
translation was `_DEFAULT_CIVILISATION_NAMES`, a module constant hard-coded here — unversioned,
undigested, absent from the register: not qualified by build (FR-023) and not covered by a
snapshot's digest (FR-024), so a future civilisation addition shifting the game's own numbering
would silently resolve a raw id to the **wrong modelled** civilisation, a confident wrong answer
`query.cost` would return with no gap, because the id was *in* the table and merely wrong — the
`unknown-civilisation-{raw_id}` fallback below only catches an id the table does not name at all.
The translation now lives in each snapshot's own `effects.toml`, as a `[[civilisation_id]]` entry
per raw id (`aoe2stats_knowledge.effects.civilisation_id_names`), covered by the same digest as
every other piece of civilisation knowledge that file carries. This module reads it from the one
snapshot the stream's own build already resolved to (`resolved.directory`, below) rather than
from a constant true of every build — how each mapping was actually measured, not guessed, is
recorded in full in that snapshot's own `effects.toml` header comment and in each entry's own
`validated_by`, not repeated here.

A raw id the resolved snapshot's table does not name (any civilisation this package has not
modelled, per `snapshot.toml`'s `civilisations_modelled`) resolves to a placeholder that can never
collide with a real, modelled name (`f"unknown-civilisation-{raw_id}"`), so every query for it
refuses at `query.py`'s own "is this civilisation modelled" step
(`cause="civilisation-not-modelled"`) rather than this module ever guessing a name a wrong guess
could make look confidently, silently wrong.

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
from aoe2stats_knowledge import effects, gaps, query, snapshot

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


def _civilisation_name_for(
    raw_id: int,
    civilisation_names: Mapping[int, str] | None,
    snapshot_civilisation_names: Mapping[int, str],
) -> str:
    """T652g: `civilisation_names` (the test-only override) first, then
    `snapshot_civilisation_names` — the resolved snapshot's own `[[civilisation_id]]` table
    (`effects.civilisation_id_names`), never a module constant true of every build."""
    if civilisation_names is not None and raw_id in civilisation_names:
        return civilisation_names[raw_id]
    if raw_id in snapshot_civilisation_names:
        return snapshot_civilisation_names[raw_id]
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

    # T652g: the raw-id-to-name translation lives in the resolved snapshot's own `effects.toml`
    # (`[[civilisation_id]]`), never a module constant true of every build — see this module's
    # docstring, "T652g: the translation lives in the snapshot, not in this module."
    snapshot_civilisation_names = effects.civilisation_id_names(resolved.directory)

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
            civilisation = _civilisation_name_for(
                raw_civilisation, civilisation_names, snapshot_civilisation_names
            )
            for entity_kind, entity_id in sorted(entities_by_slot[slot]):
                entity_ref = query.EntityRef(kind=entity_kind, id=entity_id, build=build)
                for _field_name, query_function in _QUERY_SURFACE_FUNCTIONS:
                    answer_or_gap = query_function(entity_ref, civilisation=civilisation)
                    if isinstance(answer_or_gap, gaps.KnowledgeGap):
                        result.append(answer_or_gap)

    return tuple(result)
