"""T647: `gaps.py`'s `KnowledgeGap` and its severity computation (FR-035 to FR-037).

Contract: [contracts/knowledge-base.md](../../../specs/006-replay-analysis-foundations/contracts/
knowledge-base.md), "Gaps". Data model:
[data-model.md](../../../specs/006-replay-analysis-foundations/data-model.md) §7. Research:
[research.md](../../../specs/006-replay-analysis-foundations/research.md) **D7**.

**Why this file builds its own synthetic registers.** research.md D7's decision is "blocking when
at least one register datum that is neither `blocked` nor `non-determinable` requires the field".
The real, committed `register.toml` cannot exercise the `non-determinable` half of that rule today:
its one `non-determinable` entry, `participant.units_lost`, names no `requires_knowledge` at all
(nothing this feature publishes depends on unit loss), so a version of `gaps.py` that forgot to
filter `non-determinable` entries would still pass every test run only against the real register —
the two readings coincide there by accident of today's data, not because the exclusion is exercised.
This file injects a synthetic register where a `non-determinable` entry *does* name
`requires_knowledge`, so the naive reading ("does anything name this field") and the computed
reading (D7's actual rule) disagree, and asserts the computed one.

The real register *does* already exercise the `blocked` half: `reconstruction.exploration_coverage`
and `reconstruction.map_control_model` are the only two entries naming `line_of_sight`, and both are
`blocked` (on the unread starting state, research.md D1) — so a gap on `field="line_of_sight"`
against the real, committed register is `informational` under the computed reading and would be
`blocking` under the naive one. That real-data case is exercised directly below, alongside the
synthetic one, so this file proves the distinction two ways rather than only by construction.
"""

from __future__ import annotations

import inspect

import pytest

from aoe2stats_core.truth.register import REGISTER, Register, load_register_text
from aoe2stats_knowledge import gaps

# ------------------------------------------------------------------------- synthetic registers

_REQUIRED_FIELDS = 'source = "s"\nmethod = "m"\nvalidation = "v"\nevidence = "e"\n'


def _entry(datum_id: str, *, body: str) -> str:
    return f'[datum."{datum_id}"]\n{_REQUIRED_FIELDS}{body}\n'


def _register(*entries: str) -> Register:
    return load_register_text("\n".join(entries))


#: A register with exactly one live (published, reconstructed) entry requiring "cost", so a gap on
#: "cost" is unambiguously blocking, and no entry at all requiring "other_field", so a gap on it is
#: unambiguously informational.
_ONE_LIVE_ENTRY = _register(
    _entry(
        "reconstruction.spend",
        body=(
            'classification = "reconstructed"\nstatus = "planned"\n'
            'requires_knowledge = ["cost"]\ndepends_on = []\n'
        ),
    )
)

#: The naive-vs-computed distinguishing case D7 exists for: a `non-determinable` entry that *does*
#: name `requires_knowledge` — which cannot happen in the real, committed register today (see module
#: docstring) — must still be excluded from `prevents`, because a non-determinable datum was never
#: going to be published regardless of whether the knowledge existed.
_ND_REQUIRES_KNOWLEDGE = _register(
    _entry(
        "participant.synthetic_nd",
        body=(
            'classification = "non-determinable"\nstatus = "blocked"\n'
            'requires_knowledge = ["cost"]\ndepends_on = []\n'
            'blocked_on = "nothing real"\nreason = "r"\nimpact = "i"\n'
            'approximation = "a"\napproximation_acceptable = "no"\nwould_change_if = "w"\n'
        ),
    )
)

#: The second distinguishing case: an entry requiring the field that is merely `blocked` (by some
#: other, named dependency — not by this gap) must also be excluded.
_BLOCKED_REQUIRES_KNOWLEDGE = _register(
    _entry(
        "reconstruction.synthetic_blocked",
        body=(
            'classification = "reconstructed"\nstatus = "blocked"\n'
            'requires_knowledge = ["cost"]\ndepends_on = []\nblocked_on = "starting state"\n'
        ),
    )
)

#: An empty-but-valid register — no entry names any knowledge at all — so every gap against it,
#: whatever its cause, must be informational (the `no-snapshot-for-build` edge case included: it is
#: never hard-coded to `blocking`, only computed to be, given today's real register).
_EMPTY_REGISTER = _register(
    _entry(
        "document.synthetic",
        body=(
            'classification = "observed"\nstatus = "published"\n'
            "requires_knowledge = []\ndepends_on = []\n"
        ),
    )
)


# ---------------------------------------------------------------------------- the closed cause set


def test_the_cause_set_is_closed_and_matches_data_model_section_7() -> None:
    assert {
        "no-snapshot-for-build",
        "entity-absent",
        "field-absent",
        "civilisation-not-modelled",
        "effect-not-modelled",
    } == gaps.CAUSES


def test_an_unknown_cause_is_rejected() -> None:
    with pytest.raises(gaps.GapError, match="cause"):
        gaps.KnowledgeGap(cause="made-up-cause", build=1)


# ---------------------------------------------------------- severity is computed, never supplied


def test_the_constructor_has_no_severity_or_prevents_parameter() -> None:
    """FR-037: severity is computed, never supplied by a caller. Checked structurally — not by
    review, not by convention — the same discipline `snapshot.py`'s
    `test_snapshot_for_accepts_exactly_one_required_parameter` already applies to `snapshot_for`."""
    parameters = inspect.signature(gaps.KnowledgeGap.__init__).parameters
    assert "severity" not in parameters
    assert "prevents" not in parameters


def test_severity_is_one_of_the_closed_two_member_set() -> None:
    assert {"blocking", "informational"} == gaps.SEVERITIES


# ------------------------------------------------------------------- FR-036: prevents names ids


def test_prevents_names_the_actual_register_datum_ids_not_a_boolean() -> None:
    gap = gaps.KnowledgeGap(
        cause="entity-absent",
        build=1,
        entity_kind="unit",
        entity_id="1",
        field="cost",
        register=_ONE_LIVE_ENTRY,
    )
    assert gap.prevents == ("reconstruction.spend",)
    assert gap.severity == "blocking"


def test_prevents_is_empty_and_severity_informational_when_nothing_requires_the_field() -> None:
    gap = gaps.KnowledgeGap(
        cause="entity-absent",
        build=1,
        entity_kind="unit",
        entity_id="1",
        field="an_utterly_unrequired_field",
        register=_ONE_LIVE_ENTRY,
    )
    assert gap.prevents == ()
    assert gap.severity == "informational"


# --------------------------------------------- D7: computed differs from naive ("mentions field")


def test_a_non_determinable_entry_requiring_the_field_does_not_make_the_gap_blocking() -> None:
    """The naive reading — "does anything in the register name this field at all" — would call
    this blocking, since `participant.synthetic_nd` does name `requires_knowledge = ["cost"]`. The
    computed reading (D7) excludes it: a `non-determinable` datum was never publishable regardless
    of the knowledge, so a gap in that knowledge cannot be what prevents it."""
    naive_prevents_something = any(
        "cost" in entry.requires_knowledge for entry in _ND_REQUIRES_KNOWLEDGE
    )
    assert naive_prevents_something, (
        "the synthetic register must actually name the field (fixture check)"
    )

    gap = gaps.KnowledgeGap(
        cause="entity-absent",
        build=1,
        entity_kind="unit",
        entity_id="1",
        field="cost",
        register=_ND_REQUIRES_KNOWLEDGE,
    )

    assert gap.prevents == ()
    assert gap.severity == "informational"


def test_a_blocked_entry_requiring_the_field_does_not_make_the_gap_blocking() -> None:
    """Same distinction, on `blocked` rather than `non-determinable`: a datum blocked on some other,
    named dependency (not this gap) was already withheld before this gap existed."""
    gap = gaps.KnowledgeGap(
        cause="entity-absent",
        build=1,
        entity_kind="unit",
        entity_id="1",
        field="cost",
        register=_BLOCKED_REQUIRES_KNOWLEDGE,
    )

    assert gap.prevents == ()
    assert gap.severity == "informational"


def test_the_real_register_already_distinguishes_the_two_readings_on_line_of_sight() -> None:
    """Against the real, committed register: `reconstruction.exploration_coverage` and
    `reconstruction.map_control_model` are the only two entries naming `line_of_sight`
    (`requires_knowledge`), and both are `blocked` (research.md D1, the unread starting state). The
    naive reading calls a gap on this field blocking; the computed reading — the one this module
    implements — does not, because neither entry was ever going to be published from this field."""
    naming_line_of_sight = [
        entry.id for entry in REGISTER if "line_of_sight" in entry.requires_knowledge
    ]
    assert naming_line_of_sight, "fixture check: the real register must still name line_of_sight"
    assert all(REGISTER[entry_id].status == "blocked" for entry_id in naming_line_of_sight), (
        "fixture check: this test's whole point requires every naming entry to be blocked"
    )

    gap = gaps.KnowledgeGap(
        cause="entity-absent", build=1, entity_kind="unit", entity_id="1", field="line_of_sight"
    )

    assert gap.prevents == ()
    assert gap.severity == "informational"


def test_the_real_register_makes_a_cost_gap_blocking() -> None:
    """Contrast case, against the same real register: several `reconstructed`/`derived` entries at
    `status = "planned"` (not blocked, not non-determinable) name `cost` in `requires_knowledge`, so
    a gap on `field="cost"` is blocking against today's real register — SC-007a's "a real test on
    day one" (research.md D7)."""
    gap = gaps.KnowledgeGap(
        cause="entity-absent", build=1, entity_kind="unit", entity_id="1", field="cost"
    )

    assert gap.severity == "blocking"
    assert "reconstruction.resources_spent" in gap.prevents


# ------------------------------------------- the whole-build cause: no field, computed nonetheless


def test_no_snapshot_for_build_names_no_entity_field_or_civilisation() -> None:
    gap = gaps.KnowledgeGap(cause="no-snapshot-for-build", build=999999)

    assert gap.entity_kind is None
    assert gap.entity_id is None
    assert gap.field is None
    assert gap.civilisation is None


def test_no_snapshot_for_build_is_blocking_against_the_real_register() -> None:
    """spec.md's edge case: "The build is not silently mapped to the nearest available snapshot;
    it is a gap of blocking severity." Proven here as a *consequence* of computation against the
    real register (several `planned` reconstruction data require some knowledge, so an unresolvable
    build blocks all of them at once), not asserted as a hard-coded exception to FR-037."""
    gap = gaps.KnowledgeGap(cause="no-snapshot-for-build", build=999999)

    assert gap.severity == "blocking"
    assert gap.prevents  # non-empty: several planned data require some knowledge today


def test_no_snapshot_for_build_is_informational_against_a_register_that_needs_nothing() -> None:
    """The other half of the same proof: against a register where nothing at all requires any
    knowledge, the identical whole-build gap is informational — severity is computed from the
    register, not fixed to "blocking" for this cause by name."""
    gap = gaps.KnowledgeGap(cause="no-snapshot-for-build", build=999999, register=_EMPTY_REGISTER)

    assert gap.severity == "informational"
    assert gap.prevents == ()


def test_no_snapshot_for_build_naming_an_entity_is_rejected() -> None:
    with pytest.raises(gaps.GapError, match="no-snapshot-for-build"):
        gaps.KnowledgeGap(cause="no-snapshot-for-build", build=1, entity_kind="unit")


# ------------------------------------------------------------------- per-field causes are validated


def test_a_per_field_cause_must_name_an_entity_and_field() -> None:
    with pytest.raises(gaps.GapError, match="entity-absent"):
        gaps.KnowledgeGap(cause="entity-absent", build=1)


@pytest.mark.parametrize("cause", ["civilisation-not-modelled", "effect-not-modelled"])
def test_a_civilisation_qualified_cause_must_name_the_civilisation(cause: str) -> None:
    with pytest.raises(gaps.GapError, match=cause):
        gaps.KnowledgeGap(cause=cause, build=1, entity_kind="unit", entity_id="1", field="cost")


def test_field_absent_is_in_the_closed_set_and_computes_like_any_other_per_field_cause() -> None:
    """`field-absent` has no producer in this package yet (module docstring, `gaps.py`'s own
    docstring) but is part of data-model.md §7's closed set and must already behave like every
    other per-field cause."""
    gap = gaps.KnowledgeGap(
        cause="field-absent",
        build=1,
        entity_kind="unit",
        entity_id="1",
        field="cost",
        register=_ONE_LIVE_ENTRY,
    )

    assert gap.prevents == ("reconstruction.spend",)
    assert gap.severity == "blocking"


# ------------------------------------------------------------------------------ reconciliation


def test_snapshot_for_and_query_construct_the_real_knowledge_gap_not_a_second_vocabulary() -> None:
    """T647's reconciliation: `snapshot.snapshot_for` and `query.py`'s gap branches all construct
    `gaps.KnowledgeGap` directly — there is exactly one gap type in this package, not several
    parallel interim ones."""
    from aoe2stats_knowledge import query, snapshot

    assert not hasattr(snapshot, "NoSnapshotForBuild")
    assert not hasattr(query, "EntityAbsent")
    assert not hasattr(query, "CivilisationNotModelled")
    assert not hasattr(query, "EffectNotModelled")
    assert query.KnowledgeGap is gaps.KnowledgeGap
