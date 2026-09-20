"""T643: the query surface (FR-023, SC-008).

Contract: [contracts/knowledge-base.md](../../../../specs/006-replay-analysis-foundations/
contracts/knowledge-base.md), "The query surface" and "Civilisation qualification". Research:
[research.md](../../../../specs/006-replay-analysis-foundations/research.md) **D5**. Data model:
[data-model.md](../../../../specs/006-replay-analysis-foundations/data-model.md) §6, §7.

**`civilisation` is keyword-only and required on every rule query** (`cost`, `production_time`,
`age_requirement`, `prerequisites`, `produced_at`, `available_to`) — Python's `*` syntax before the
parameter enforces this at the language level, so there is no way to ask for a generic value and
therefore no way to be handed one (FR-023). `name` is the one exception the contract carves out
explicitly: it is not civilisation-qualified at all.

**Every civilisation-qualified query currently gaps.** research.md D5's conservative rule: a
civilisation whose bonus set is not modelled refuses every civilisation-qualified cost and time,
because which fields its bonuses touch is exactly what is not known. No snapshot committed today
declares any civilisation modelled (`civilisations_modelled` is `[]` on both promoted fixtures —
T645 has not run), so every call into `_civilisation_qualified` gaps at that check. This is the
correct, honest behaviour for this task alone, not a shortcut: returning a baseline value here
would be exactly the FR-038 substitution this feature exists to forbid. `_civilisation_qualified`
raises `NotImplementedError` if it is ever reached past that check with no snapshot committed today
able to trigger it, precisely so that a future change adding a civilisation to
`civilisations_modelled` (T645) *before* effect application exists (T644) fails loudly instead of
silently answering with the un-adjusted baseline.

**Two return branches, never a third.** Every public function below returns `Answer[X]` or a
`KnowledgeGap` member — never a bare value, never a default parameter, never a caught-and-continued
gap. `KnowledgeGap` is a **type alias**, not the full record FR-035 to FR-037 describe (entity,
field, `prevents`, computed `severity`) — see `snapshot.NoSnapshotForBuild`'s own docstring for the
precedent this follows. `EntityAbsent` and `CivilisationNotModelled` are this task's own interim
gap values, for the same reason: **T647**, when it implements `gaps.py`'s full `KnowledgeGap`, must
fold all of these interim shapes into it rather than leaving several parallel gap vocabularies in
the package.

**Threading a build through a query.** The contract's shorthand signatures
(`cost(entity, *, civilisation)`) have no separate `build` parameter. `EntityRef` carries `kind`,
`id` **and** `build` — a unit id is not meaningful without naming which build's rules it resolves
under — so `entity.build` is what every query resolves a snapshot from
(`snapshot.snapshot_for`, FR-027). This matches `packages/knowledge/tests/test_query.py` (T646)'s
own real call sites, written before this module existed.
"""

from __future__ import annotations

import functools
import json
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from importlib import resources
from typing import Any, Final

from aoe2stats_knowledge import snapshot
from aoe2stats_knowledge.snapshot import NoSnapshotForBuild, Snapshot, SnapshotIdentity

#: The package this module's data is anchored to — the same anchor `snapshot.py` and
#: `normalise.py` use, so a snapshot is resolved identically from a wheel or an editable checkout.
_PACKAGE: Final[str] = "aoe2stats_knowledge"

#: `rules.json`'s own field name for a unit's/building's/technology's production duration — one of
#: these is present on every entity record `normalise.py`'s `_entity` produces.
_TIME_FIELDS: Final[tuple[str, ...]] = ("training_time", "construction_time", "research_time")

#: `name()`'s `.source` when an identifier degrades to the bare id (003 FR-043a) — there is no
#: stored source to report, because nothing was found.
_UNRESOLVED_SOURCE: Final[str] = "unresolved"


@dataclass(frozen=True, slots=True)
class EntityRef:
    """One entity identifier, qualified by the game build it is meaningful under. `kind` is one of
    `rules.json`'s three entity kinds (`"unit"`, `"building"`, `"technology"`); `id` is the
    entity's own identifier exactly as `rules.json` keys it (a numeric id, spelled as a string).
    """

    kind: str
    id: str
    build: int


@dataclass(frozen=True, slots=True)
class Answer[T]:
    """One resolved knowledge value (contracts/knowledge-base.md, "The query surface"): the value
    itself, the identity of the snapshot that produced it (US2 scenario 1), the source table it
    was read from (`rules.json`'s own `table_origin`), and every civilisation effect applied to
    it, in order — always empty for now, because no effect module exists yet to apply one (T644).
    """

    value: T
    snapshot_identity: SnapshotIdentity
    source: str
    effects: Sequence[Any] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class EntityAbsent:
    """`entity.id` is not present in the resolved snapshot's `rules.json` under `entity.kind` at
    all — a genuinely unknown identifier, distinct from an unmodelled civilisation (data-model.md
    §7's closed cause `entity-absent`). **Interim** — see this module's docstring; T647 must fold
    this into the full `KnowledgeGap`.
    """

    kind: str
    id: str
    build: int
    cause: str = "entity-absent"


@dataclass(frozen=True, slots=True)
class CivilisationNotModelled:
    """research.md D5's conservative rule: `civilisation` is not in the resolved snapshot's
    `civilisations_modelled`, so which fields its bonuses touch is not known and every
    civilisation-qualified cost or time for it refuses (data-model.md §7's closed cause
    `civilisation-not-modelled`). **Interim** — see `EntityAbsent`.
    """

    civilisation: str
    kind: str
    id: str
    field: str
    build: int
    cause: str = "civilisation-not-modelled"


#: Every civilisation-qualified query's gap union, until T647 replaces this name with the full
#: `KnowledgeGap` record (entity, field, build, civilisation, computed `prevents`/`severity` —
#: data-model.md §7). Kept as one name so a function's `-> Answer[X] | KnowledgeGap` reads exactly
#: as contracts/knowledge-base.md spells it, and so T647 can retarget this alias without touching
#: any query function's signature.
KnowledgeGap = NoSnapshotForBuild | EntityAbsent | CivilisationNotModelled


@functools.cache
def _rules(directory: str) -> Mapping[str, Any]:
    """`rules.json`'s parsed content for one packaged snapshot directory, read directly through
    `importlib.resources` (FR-026, SC-006: nothing here opens a socket or a bare filesystem path).

    `Snapshot` (`snapshot.py`) does not carry the parsed rules body itself as of this task — see
    that module's docstring, "T640 extends this dataclass with the normalised rules body it
    carries", which has not happened yet — so this reads the packaged file independently rather
    than waiting on that extension. Cached per directory: a snapshot directory is immutable once
    committed (FR-025), so re-reading it can never observe a different answer.
    """
    root = resources.files(_PACKAGE).joinpath("snapshots").joinpath(directory)
    parsed: Mapping[str, Any] = json.loads(root.joinpath("rules.json").read_text(encoding="utf-8"))
    return parsed


@functools.cache
def _civilisations_modelled(directory: str) -> frozenset[str]:
    """`snapshot.toml`'s `[snapshot].civilisations_modelled` for one packaged snapshot directory
    (data-model.md §6) — read directly for the same reason `_rules` is: `Snapshot` does not carry
    this field itself yet either.
    """
    root = resources.files(_PACKAGE).joinpath("snapshots").joinpath(directory)
    data = tomllib.loads(root.joinpath("snapshot.toml").read_text(encoding="utf-8"))
    table = data.get("snapshot", {})
    modelled = table.get("civilisations_modelled", [])
    return frozenset(modelled)


def _resolve_entity(
    entity: EntityRef,
) -> tuple[Snapshot, Mapping[str, Any]] | NoSnapshotForBuild | EntityAbsent:
    """`entity.build` to a promoted snapshot (`snapshot.snapshot_for`, FR-027), then `entity.id`
    within that snapshot's `rules.json` under `entity.kind` — the two steps every query in this
    module shares, whether or not it goes on to be civilisation-qualified.
    """
    resolved = snapshot.snapshot_for(entity.build)
    if isinstance(resolved, NoSnapshotForBuild):
        return resolved
    kind_table = _rules(resolved.directory).get("entities", {}).get(entity.kind, {})
    record = kind_table.get(entity.id)
    if record is None:
        return EntityAbsent(kind=entity.kind, id=entity.id, build=entity.build)
    return resolved, record


def _civilisation_qualified(
    entity: EntityRef, *, civilisation: str, field_name: str
) -> Answer[Any] | KnowledgeGap:
    """The shared body of every civilisation-qualified query (contracts/knowledge-base.md,
    "Civilisation qualification", steps 1-3): resolve the entity, then refuse unless
    `civilisation` is in the resolved snapshot's `civilisations_modelled` (research.md D5's
    conservative rule — never the baseline, FR-038).

    Step 3 — apply each matching effect, in order, and return the adjusted value — is T644's job.
    No snapshot committed today models any civilisation, so every call through this function gaps
    at the check above; that is the correct, honest state of this task, not a shortcut (see this
    module's docstring). The `NotImplementedError` below exists only so that a future change
    adding a civilisation to some snapshot's `civilisations_modelled` (T645) before effect
    application exists (T644) fails loudly rather than silently returning the un-adjusted
    baseline — which would be exactly the substitution FR-038 forbids.
    """
    resolved = _resolve_entity(entity)
    if not isinstance(resolved, tuple):
        return resolved
    snap, _record = resolved
    if civilisation not in _civilisations_modelled(snap.directory):
        return CivilisationNotModelled(
            civilisation=civilisation,
            kind=entity.kind,
            id=entity.id,
            field=field_name,
            build=entity.build,
        )
    raise NotImplementedError(  # pragma: no cover - unreachable while nothing is modelled today
        "T644 (effects.py) must implement effect application: "
        f"{civilisation!r} is modelled for {entity.kind}:{entity.id} but nothing applies its "
        f"effects to {field_name!r} yet"
    )


def cost(entity: EntityRef, *, civilisation: str) -> Answer[Mapping[str, int]] | KnowledgeGap:
    """`entity`'s cost, adjusted for `civilisation` — never the baseline (FR-023: `civilisation`
    is keyword-only and required, so there is no way to ask for, or be handed, a generic value).
    """
    return _civilisation_qualified(entity, civilisation=civilisation, field_name="cost")


def production_time(entity: EntityRef, *, civilisation: str) -> Answer[int] | KnowledgeGap:
    """Training time (a unit), construction time (a building) or research time (a technology), in
    the whole in-game time units `rules.json` itself carries.
    """
    return _civilisation_qualified(entity, civilisation=civilisation, field_name="production_time")


def age_requirement(entity: EntityRef, *, civilisation: str) -> Answer[int] | KnowledgeGap:
    """The age id `entity` requires, adjusted for a civilisation whose bonus moves it (research.md
    D5: e.g. Burgundians' and Armenians' early-technology bonuses)."""
    return _civilisation_qualified(entity, civilisation=civilisation, field_name="age_requirement")


def prerequisites(
    entity: EntityRef, *, civilisation: str
) -> Answer[Sequence[EntityRef]] | KnowledgeGap:
    """The entities `entity` requires before it can be built, trained or researched."""
    return _civilisation_qualified(entity, civilisation=civilisation, field_name="prerequisites")


def produced_at(entity: EntityRef, *, civilisation: str) -> Answer[EntityRef] | KnowledgeGap:
    """The building `entity` is trained or researched at."""
    return _civilisation_qualified(entity, civilisation=civilisation, field_name="produced_at")


def available_to(entity: EntityRef, *, civilisation: str) -> Answer[bool] | KnowledgeGap:
    """Whether `civilisation` can build, train or research `entity` at all.

    Civilisation-qualified for the same reason cost and time are (research.md D5): which units,
    buildings and technologies a civilisation has access to is itself a per-civilisation fact that
    `rules.json`'s flattened, cross-civilisation baseline does not carry on its own, so this
    refuses under the identical conservative rule rather than guessing from the baseline entity's
    mere presence.
    """
    return _civilisation_qualified(entity, civilisation=civilisation, field_name="available_to")


def name(entity: EntityRef) -> Answer[str] | KnowledgeGap:
    """`entity`'s display name — the one query in this surface that is **not**
    civilisation-qualified. An identifier the resolved snapshot does not recognise degrades to the
    bare identifier at the presentation boundary (003 FR-043a: "a confident wrong name is worse
    than a bare id") rather than gapping — contracts/knowledge-base.md, "Civilisation
    qualification": "it never gaps an analysis". A build with no promoted snapshot still gaps
    (`NoSnapshotForBuild`, the only member of `KnowledgeGap` this function can actually produce):
    there is no snapshot to even attempt a lookup against.
    """
    resolved = snapshot.snapshot_for(entity.build)
    if isinstance(resolved, NoSnapshotForBuild):
        return resolved
    kind_table = _rules(resolved.directory).get("entities", {}).get(entity.kind, {})
    record = kind_table.get(entity.id)
    display_name = record.get("name") if record is not None else None
    if not display_name:
        return Answer(
            value=entity.id,
            snapshot_identity=resolved.identity,
            source=_UNRESOLVED_SOURCE,
            effects=(),
        )
    return Answer(
        value=display_name,
        snapshot_identity=resolved.identity,
        source=record["table_origin"],
        effects=(),
    )
