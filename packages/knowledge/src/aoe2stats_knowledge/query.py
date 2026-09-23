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

**Six civilisations are modelled today; every other one still gaps.** research.md D5's
conservative rule: a civilisation whose bonus set is not modelled refuses every
civilisation-qualified cost and time, because which fields its bonuses touch is exactly what is
not known. T645 populated `civilisations_modelled` on both promoted fixtures
(`aoe2techtree-180059`, `aoe2techtree-177723-test`); T652m (2026-09-23) corrected that table to
the six civilisations actually in the two committed recordings — Franks, Teutons, Persians,
Saracens, Malians, Tatars — so a query naming one of those six now proceeds past step 1
into real effect application (T644, below). A civilisation outside that set still gaps at the same
check, and that remains the correct, honest behaviour research.md D5 requires, not a shortcut:
returning a baseline value for an unmodelled civilisation would be exactly the FR-038 substitution
this feature exists to forbid. There is no `raise NotImplementedError` guarding the step past that
check, and there does not need to be one: once T644 and T645 both landed, falling past "is this
civilisation modelled" runs straight into `_field_present` and `effects.apply` — the real
implementation — so there is no unimplemented branch left for a guard to catch.

**Two return branches, never a third.** Every public function below returns `Answer[X]` or a
`gaps.KnowledgeGap` — never a bare value, never a default parameter, never a caught-and-continued
gap. **T647** implemented `gaps.KnowledgeGap`, the full FR-035 to FR-037 record (entity, field,
build, civilisation, closed `cause`, computed `prevents`/`severity`); this module's `KnowledgeGap`
is that real type, imported directly, not a local alias over several interim shapes. The interim
`EntityAbsent`/`CivilisationNotModelled`/`EffectNotModelled` values this module used to define are
gone — every branch below that used to construct one now constructs `gaps.KnowledgeGap` directly,
naming its `cause` exactly as those interim types did (`"entity-absent"`,
`"civilisation-not-modelled"`, `"effect-not-modelled"`), so nothing that only inspected `.cause`
observes a difference.

**T644 (`effects.py`) now implements effect application** (contracts/knowledge-base.md,
"Civilisation qualification" steps 2-3): once a civilisation is modelled (step 1),
`_raw_value_for_field` reads the entity's own baseline value out of its resolved `rules.json`
record, and `effects.apply` finds every matching effect in that snapshot's `effects.toml`,
refusing with `EffectNotModelled` if any match is `modelled = "no"` (never applying a modelled
match alongside one that is not — "a bonus is never half-applied", research.md D5), and otherwise
returning the adjusted value with the effects applied, in file order. **T645 has since populated
`civilisations_modelled` and `effects.toml`** on both promoted fixtures, exactly as this wiring was
built to receive without this module changing again: a query naming one of the six modelled
civilisations now returns a real, effect-adjusted `Answer`; a query naming any other civilisation
still gaps at step 1, per research.md D5.

**Threading a build through a query.** The contract's shorthand signatures
(`cost(entity, *, civilisation)`) have no separate `build` parameter. `EntityRef` carries `kind`,
`id` **and** `build` — a unit id is not meaningful without naming which build's rules it resolves
under — so `entity.build` is what every query resolves a snapshot from
(`snapshot.snapshot_for`, FR-027). This matches `packages/knowledge/tests/test_query.py` (T646)'s
own real call sites, written before this module existed.

**T652b: the field-presence check and the `rules_overrides` seam.** Before this task,
`_raw_value_for_field` defaulted rather than gapped when a query-level field's own `rules.json` key
was absent from a resolved entity's record (`record.get("cost", {})`) — a narrower, pre-existing
behaviour data-model.md §7's `field-absent` cause named as its closed-set member with "no producer
yet". `_field_present`, checked in `_civilisation_qualified` immediately after the civilisation is
confirmed modelled and before `_raw_value_for_field` ever reads a default in its place, is that
producer: an entity whose own record genuinely lacks a field — never a legitimate `None`/`[]` value,
which every real, committed entity record still carries as an explicit key (`normalise.py`'s
`_entity`) — now gaps with `cause="field-absent"` instead of silently answering with a fabricated
default (exactly the FR-038 substitution this whole feature exists to forbid).

`rules_overrides`, a context manager, is the seam a caller — today, only `coverage.py`'s own
`rules_overrides` parameter and `test_coverage.py`'s SC-007 — may use to substitute an in-memory
`rules.json` mapping for one build, in place of the real, packaged one `_rules(directory)` reads,
without touching the packaged fixture on disk (FR-025) or `query.py` inventing a second,
parallel snapshot-construction path. Every other resolution step — is the build promoted at all,
is the civilisation modelled, which effects apply — still reads the real, packaged snapshot
(`snapshot.snapshot_for`, `_civilisations_modelled`, `effects.apply`): the override only ever
stands in for the parsed `rules.json` body. Left un-entered — every real, production call's case —
`_resolve_entity` reads `_rules(directory)` exactly as it always has.

Giving `query.py` this seam, rather than leaving `coverage.py` to reimplement
`_civilisation_qualified`'s whole step order and its own field-presence check on top of privately
imported internals, is what lets `coverage.coverage` call these six public functions directly
(T652b) — the point being that SC-008's "by construction rather than by inspection" then actually
governs the gap list `coverage.coverage` publishes, not only the seven functions
`test_structure.py` sweeps directly.
"""

from __future__ import annotations

import contextlib
import functools
import json
import tomllib
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from importlib import resources
from typing import Any, Final

from aoe2stats_knowledge import effects, snapshot
from aoe2stats_knowledge.gaps import KnowledgeGap
from aoe2stats_knowledge.snapshot import Snapshot, SnapshotIdentity

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
    it, in order (`effects.Effect`, T644) — empty when no effect touched this query: either the
    civilisation asked for is not one of the six T645 named as modelled, or it is one of the six
    but no effect in that snapshot's `effects.toml` matches this entity/field.
    """

    value: T
    snapshot_identity: SnapshotIdentity
    source: str
    effects: Sequence[Any] = field(default_factory=tuple)


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


#: T652b's test-only substitute for `_rules(directory)`, keyed by build — never read outside
#: `_rules_for`, and never set outside the `rules_overrides` context manager below. `None` (its
#: value for every real, production call) means "read the real, packaged rules.json".
_rules_override: Mapping[int, Mapping[str, Any]] | None = None


@contextlib.contextmanager
def rules_overrides(overrides: Mapping[int, Mapping[str, Any]]) -> Iterator[None]:
    """T652b's own seam (module docstring): while this context manager is active, `_resolve_entity`
    reads `overrides[entity.build]` in place of the real, packaged `rules.json` for any build
    `overrides` names — every other resolution step (`snapshot.snapshot_for`,
    `_civilisations_modelled`, `effects.apply`) still reads the real, packaged snapshot.

    Test-only: no production caller in this repository ever calls this (`coverage.py`'s own
    `rules_overrides` parameter and `test_coverage.py`'s SC-007 are the only two callers). Restores
    the previous override (`None`, for every real call) on exit even if the body raises, so a test
    that fails inside the `with` block cannot leak its override into the next test.
    """
    global _rules_override
    previous = _rules_override
    _rules_override = overrides
    try:
        yield
    finally:
        _rules_override = previous


def _rules_for(build: int, directory: str) -> Mapping[str, Any]:
    """`_rules(directory)`, unless `rules_overrides` is active and names `build` — see that
    function's docstring. `directory` alone cannot answer this: two different builds can resolve to
    two different directories, and the override is keyed by build, not by directory."""
    if _rules_override is not None and build in _rules_override:
        return _rules_override[build]
    return _rules(directory)


def _field_present(record: Mapping[str, Any], field_name: str) -> bool:
    """T652b: whether `record` (one resolved `rules.json` entity) carries the key a query-level
    field reads from at all — checked *before* `_raw_value_for_field` reads it, so a field a
    `rules_overrides` mutation genuinely deleted is reported as missing (`cause="field-absent"`)
    rather than silently read back as `_raw_value_for_field`'s own default (`{}`, `[]`, `None`).
    `available_to` has no stored field of its own at all (`_raw_value_for_field`'s own docstring:
    resolving the entity already proves the baseline pack carries it), so it is never reported
    absent.
    """
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


def _resolve_entity(
    entity: EntityRef, *, civilisation: str, field_name: str
) -> tuple[Snapshot, Mapping[str, Any]] | KnowledgeGap:
    """`entity.build` to a promoted snapshot (`snapshot.snapshot_for`, FR-027), then `entity.id`
    within that snapshot's `rules.json` under `entity.kind` — the two steps every query in this
    module shares, whether or not it goes on to be civilisation-qualified.

    `civilisation` and `field_name` are not used to resolve anything here — they are threaded
    through only so a `"entity-absent"` gap (data-model.md §7) can name the full FR-035 shape (the
    field the caller actually asked for, and the civilisation the query was qualified by), rather
    than the bare `kind`/`id`/`build` the interim `EntityAbsent` used to carry before T647.
    """
    resolved = snapshot.snapshot_for(entity.build)
    if isinstance(resolved, KnowledgeGap):
        return resolved
    kind_table = (
        _rules_for(entity.build, resolved.directory).get("entities", {}).get(entity.kind, {})
    )
    record = kind_table.get(entity.id)
    if record is None:
        return KnowledgeGap(
            cause="entity-absent",
            build=entity.build,
            entity_kind=entity.kind,
            entity_id=entity.id,
            field=field_name,
            civilisation=civilisation,
        )
    return resolved, record


def _raw_value_for_field(record: Mapping[str, Any], field_name: str) -> Any:
    """The baseline value `record` (one resolved `rules.json` entity) carries for one
    query-level field name, before any civilisation effect is applied. `field_name` is the
    vocabulary this module's own public functions pass (`"cost"`, `"production_time"`, ...) — not
    necessarily `rules.json`'s own field name, since `production_time` reads whichever of
    `_TIME_FIELDS` the entity actually carries (a unit's `training_time`, a building's
    `construction_time`, a technology's `research_time`) and `available_to` has no stored field of
    its own at all: resolving the entity in the first place already proves the baseline pack
    carries it, so the baseline answer is `True` pending an effect that says otherwise.
    """
    if field_name == "cost":
        return record.get("cost", {})
    if field_name == "production_time":
        for time_field in _TIME_FIELDS:
            if time_field in record:
                return record[time_field]
        return None
    if field_name == "age_requirement":
        return record.get("age_requirement")
    if field_name == "prerequisites":
        return record.get("prerequisites", [])
    if field_name == "produced_at":
        return record.get("produced_at")
    if field_name == "available_to":
        return True
    raise AssertionError(f"unreachable: unknown field_name {field_name!r}")  # pragma: no cover


def _civilisation_qualified(
    entity: EntityRef, *, civilisation: str, field_name: str
) -> Answer[Any] | KnowledgeGap:
    """The shared body of every civilisation-qualified query (contracts/knowledge-base.md,
    "Civilisation qualification", steps 1-3): resolve the entity, refuse unless `civilisation` is
    in the resolved snapshot's `civilisations_modelled` (step 1, research.md D5's conservative
    rule — never the baseline, FR-038), then apply every matching, modelled effect from that
    snapshot's `effects.toml` (steps 2-3, `effects.apply` — T644) and return the adjusted value.

    **Both promoted fixtures now name six civilisations modelled** (T645/T652m: Franks, Teutons,
    Persians, Saracens, Malians, Tatars) — a call naming one of those six proceeds to steps 2-3 and
    returns a real, effect-adjusted `Answer`; a call naming any other civilisation still gaps at
    step 1, which remains the correct, honest state research.md D5 requires, not a shortcut this
    function takes.
    """
    resolved = _resolve_entity(entity, civilisation=civilisation, field_name=field_name)
    if not isinstance(resolved, tuple):
        return resolved
    snap, record = resolved
    if civilisation not in _civilisations_modelled(snap.directory):
        return KnowledgeGap(
            cause="civilisation-not-modelled",
            build=entity.build,
            entity_kind=entity.kind,
            entity_id=entity.id,
            field=field_name,
            civilisation=civilisation,
        )
    if not _field_present(record, field_name):
        return KnowledgeGap(
            cause="field-absent",
            build=entity.build,
            entity_kind=entity.kind,
            entity_id=entity.id,
            field=field_name,
            civilisation=civilisation,
        )
    baseline = _raw_value_for_field(record, field_name)
    applied = effects.apply(
        snap.directory,
        civilisation=civilisation,
        kind=entity.kind,
        id=entity.id,
        field=field_name,
        value=baseline,
    )
    if isinstance(applied, effects.EffectNotModelled):
        return KnowledgeGap(
            cause="effect-not-modelled",
            build=entity.build,
            entity_kind=entity.kind,
            entity_id=entity.id,
            field=field_name,
            civilisation=civilisation,
            detail=applied.reason,
        )
    value, applied_effects = applied
    return Answer(
        value=value,
        snapshot_identity=snap.identity,
        source=record["table_origin"],
        effects=applied_effects,
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
    qualification": "it never gaps an analysis". A build with no promoted snapshot still gaps, with
    `cause="no-snapshot-for-build"` (the only cause this function can actually produce): there is
    no snapshot to even attempt a lookup against.
    """
    resolved = snapshot.snapshot_for(entity.build)
    if isinstance(resolved, KnowledgeGap):
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
