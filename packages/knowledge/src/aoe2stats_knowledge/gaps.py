"""T647: the gap record and its severity computation (FR-035 to FR-037).

Contract: [contracts/knowledge-base.md](../../../../specs/006-replay-analysis-foundations/
contracts/knowledge-base.md), "Gaps". Data model:
[data-model.md](../../../../specs/006-replay-analysis-foundations/data-model.md) §7. Research:
[research.md](../../../../specs/006-replay-analysis-foundations/research.md) **D7**.

**This is the real `KnowledgeGap` FR-035 to FR-037 describe** — the type `snapshot.py`'s
`NoSnapshotForBuild` and `query.py`'s (now removed) `EntityAbsent`, `CivilisationNotModelled` and
`EffectNotModelled` were always interim stand-ins for, each flagged in its own docstring "T647
must fold this into `gaps.py`'s full `KnowledgeGap`". That reconciliation is done:
`snapshot.snapshot_for` and every branch of `query._civilisation_qualified` now construct
`KnowledgeGap` directly, and no second gap vocabulary remains in this package.

**FR-035** — a gap names an entity (`entity_kind`, `entity_id`), a `field`, a `build` and the
`civilisation` the query was qualified by, where there was one. Not every cause has all four: a
build with no promoted snapshot at all (`"no-snapshot-for-build"`) names no entity, field or
civilisation, because *nothing* about that build is known, not one field of it — see
`_WHOLE_BUILD_CAUSES` below.

**FR-036** — `prevents` is the set of register datum ids this gap actually stops, not a boolean.
Computed by `_prevented`, from the register's own `requires_knowledge`.

**FR-037, research.md D7** — `severity` is **computed**, never a constructor parameter: this
dataclass's `__init__` (see its generated signature) has no `severity` parameter at all, so there is
no call shape through which a caller could hand it one. It is `"blocking"` when at least one
register datum that is neither `blocked` nor `non-determinable` requires the field (D7's wording,
literally); `"informational"` otherwise. **Read naively** — "does anything in the register mention
this field at all" — every gap would agree with the computed reading today, for a coincidental
reason the task names: no `non-determinable` entry currently names any `requires_knowledge`.
`test_gaps.py` proves the two readings are not the same test by injecting a synthetic register where
they diverge, both on a `non-determinable` entry and on a merely `blocked` one (the real, committed
register already has one of those — `reconstruction.exploration_coverage` /
`reconstruction.map_control_model`, both blocked on the same unread starting state, are the only two
entries naming `line_of_sight`, so the naive reading calls it blocking and the computed reading does
not).

**The closed cause set** — data-model.md §7 names five: `no-snapshot-for-build`, `entity-absent`,
`field-absent`, `civilisation-not-modelled`, `effect-not-modelled`. The first four each have a real
producer today (`snapshot.snapshot_for`; `query._resolve_entity`; `query._civilisation_qualified`,
twice). `field-absent` — an entity resolves, but the specific field a query asked for is absent from
its own record — has none yet: every query-level field reader in `query._raw_value_for_field`
defaults rather than gapping (`record.get("cost", {})`), which is a pre-existing, narrower
behaviour this task does not change. `field-absent` is kept in the closed set because
data-model.md already closes it there, and exercised directly in `test_gaps.py` so the type is
provably ready for whichever future producer needs it, rather than a name with no test.
"""

from __future__ import annotations

from dataclasses import InitVar, dataclass
from dataclasses import field as _dc_field
from typing import Final

from aoe2stats_core.truth.register import NON_DETERMINABLE, REGISTER, Entry, Register

#: data-model.md §7's closed cause set, named exactly as the code that produces each one already
#: names them (`snapshot.py`, `query.py`).
CAUSES: Final[frozenset[str]] = frozenset(
    {
        "no-snapshot-for-build",
        "entity-absent",
        "field-absent",
        "civilisation-not-modelled",
        "effect-not-modelled",
    }
)

#: FR-037's closed, exactly-two-member severity set.
BLOCKING: Final[str] = "blocking"
INFORMATIONAL: Final[str] = "informational"
SEVERITIES: Final[frozenset[str]] = frozenset({BLOCKING, INFORMATIONAL})

#: Causes that name no single field — the whole build is unresolvable, so every field any register
#: datum could ever require is equally unknown, not just one of them (spec.md's edge case: "The
#: build is not silently mapped to the nearest available snapshot; it is a gap of blocking
#: severity" — a blanket rule that `_prevented`'s ``field_name is None`` branch below satisfies by
#: computation, over today's real register, rather than by a hard-coded exception to FR-037).
_WHOLE_BUILD_CAUSES: Final[frozenset[str]] = frozenset({"no-snapshot-for-build"})

#: Causes that are qualified by a civilisation that failed to answer — the two the query surface's
#: `_civilisation_qualified` step 1/step 2 refusals produce (contracts/knowledge-base.md,
#: "Civilisation qualification").
_CIVILISATION_QUALIFIED_CAUSES: Final[frozenset[str]] = frozenset(
    {"civilisation-not-modelled", "effect-not-modelled"}
)


class GapError(ValueError):
    """A `KnowledgeGap` was constructed with a shape its own closed rules forbid: an unknown
    `cause`, a whole-build cause naming an entity/field/civilisation it must not, or a
    per-field cause missing the entity/field it must name."""


def _prevented(register: Register, field_name: str | None) -> tuple[str, ...]:
    """FR-036: the register data this gap actually stops, by id.

    research.md **D7**: an entry counts only when it is neither `blocked` (by some other, named
    dependency — not this gap) nor `non-determinable` (permanently unanswerable regardless of
    knowledge) — such an entry was never going to be published from this field anyway, so a gap in
    the field is not what stops it. `field_name is None` (`_WHOLE_BUILD_CAUSES`) widens the test to
    "requires *any* knowledge at all", because there is no single field to check.

    Declaration order is preserved (`register.entries` is a `dict`, insertion-ordered from the TOML
    table), so `prevents` is deterministic and reproducible from the same register.
    """

    def _live(entry: Entry) -> bool:
        return entry.status != "blocked" and entry.classification != NON_DETERMINABLE

    if field_name is None:
        return tuple(entry.id for entry in register if entry.requires_knowledge and _live(entry))
    return tuple(
        entry.id for entry in register if field_name in entry.requires_knowledge and _live(entry)
    )


@dataclass(frozen=True, slots=True)
class KnowledgeGap:
    """One absent required piece of knowledge (FR-035 to FR-037; data-model.md §7).

    `prevents` and `severity` are **not constructor parameters** — `dataclasses.field(init=False)`
    below removes them from `__init__` entirely, so `inspect.signature(KnowledgeGap.__init__)` has
    no `severity` (or `prevents`) parameter for a caller to pass. Both are computed in
    `__post_init__` from `register` (an `InitVar`, defaulting to the packaged `REGISTER` and never
    stored on the instance), which is the one thing a caller may legitimately vary — the same way
    `query.py` varies which snapshot a query resolves against by `build`, never the answer itself.
    """

    cause: str
    build: int
    entity_kind: str | None = None
    entity_id: str | None = None
    field: str | None = None
    civilisation: str | None = None
    detail: str | None = None
    prevents: tuple[str, ...] = _dc_field(init=False)
    severity: str = _dc_field(init=False)
    register: InitVar[Register] = REGISTER

    def __post_init__(self, register: Register) -> None:
        if self.cause not in CAUSES:
            raise GapError(f"cause must be one of {sorted(CAUSES)}, got {self.cause!r}")
        if self.cause in _WHOLE_BUILD_CAUSES:
            if self.entity_kind is not None or self.entity_id is not None or self.field is not None:
                raise GapError(
                    f"{self.cause!r} names no entity or field — nothing about the build is known"
                )
            if self.civilisation is not None:
                raise GapError(f"{self.cause!r} names no civilisation")
        else:
            if self.entity_kind is None or self.entity_id is None or self.field is None:
                raise GapError(f"{self.cause!r} must name an entity_kind, entity_id and field")
            if self.cause in _CIVILISATION_QUALIFIED_CAUSES and self.civilisation is None:
                raise GapError(f"{self.cause!r} must name the civilisation that failed to answer")
        prevents = _prevented(register, self.field)
        object.__setattr__(self, "prevents", prevents)
        object.__setattr__(self, "severity", BLOCKING if prevents else INFORMATIONAL)
