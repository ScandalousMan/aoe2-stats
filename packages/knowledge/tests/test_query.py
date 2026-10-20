"""T646: the query surface (T643), civilisation effects (T644) and civilisation modelling (T645).
Written before any of the three existed, every discount/two-snapshot test below was
`xfail(strict=True)` for exactly that reason; T645 populated `civilisations_modelled` on both
promoted fixtures and all three markers were removed, since all three now pass for the real reason
they were written to prove, not by accident.

Contract: [contracts/knowledge-base.md](../../../specs/006-replay-analysis-foundations/contracts/
knowledge-base.md), "The query surface" and "Civilisation qualification". Research:
[research.md](../../../specs/006-replay-analysis-foundations/research.md) **D5** (civilisation
bonuses are hand-modelled, an unmodelled civilisation is a gap, never the baseline). Data model:
[data-model.md](../../../specs/006-replay-analysis-foundations/data-model.md) §6 ("Civilisation
effect") and §7 ("Knowledge gap"). Spec: **US2** scenario 2 ("two different knowledge snapshots
... each answers from its own contents and neither is silently upgraded to the other").

**Real facts this file's numbers are derived from, not invented** (verified directly against the
committed pack, `packages/knowledge/packs/aoe2techtree/`, and the committed promoted snapshot,
`packages/knowledge/snapshots/aoe2techtree-180059/rules.json`):

- Building id `84` is "Market" (`table_origin = "building"`), cost `{wood: 175}`.
- Saracens' bonus prose (`strings.en.json`, the string named by `civs.Saracens.help_string_id`,
  `120158`): "Market trading fee only 5%; Markets cost -100 wood" (T652m; Saracens is one of
  recording 1's two real civilisations, corrected from the previously committed, wrong
  Byzantines). Only the wood-cost clause is modelled: `175 - 100 = 75`, a whole number needing no
  rounding-convention decision.
- Building id `45` is "Dock" (`table_origin = "building"`), cost `{wood: 150}`.
- Malians' bonus prose (`civs.Malians.help_string_id`, `120175`, read directly from
  `strings.en.json`): "Buildings cost -15% wood" (T652m; Malians is recording 1's other real
  civilisation, corrected from the previously committed, wrong Koreans). The
  Dock is one of the 24 buildings this bonus names, so its cost is touched:
  `150 * 0.85 = 127.5`, which **does** land on a rounding boundary. This file states the
  convention explicitly rather than leaving it to whichever rounding `round()` happens to pick:
  **round half up** (`127.5 -> 128`), because that is the convention this repository's own
  docstrings already use when a display quantity is derived from a fraction (see e.g.
  `docs/data-sources.md`'s ratio figures).
- Unit id `358` is "Pikeman" (`table_origin = "unit"`), cost `{food: 35, wood: 25}`. Britons has
  no bonus that touches Pikeman's cost (`civs.Britons.help_string_id`, `120150`: shepherds, Town
  Center wood cost by age, Foot Archer range) — chosen deliberately so the "unmodelled
  civilisation" test cannot pass by coincidence: Britons' true Pikeman cost genuinely *is* the
  baseline, and the conservative rule (research D5) must still gap it, because which fields an
  unmodelled civilisation's bonuses touch is exactly what is not known. **Franks held this role
  until T645**: the second committed recording (`AgeIIDE_Replay_504695319.zip`) turned out to
  genuinely train Franks (research.md D11), so Franks is one of the six civilisations
  `civilisations_modelled` now names, and this file's "always unmodelled" example moved to Britons
  — confirmed absent from both committed recordings and confirmed, the same way, to have no bonus
  touching Pikeman's cost. Franks is otherwise used below wherever a test needs *some* modelled
  civilisation but is not itself proving a discount (build resolution, entity absence): none of
  Franks' own effects touch Pikeman's cost either, so this is a plain, unmodified baseline
  answer in those cases, not a second discount claim.

**Design decisions this file fixes, because `query.py`/`effects.py` do not exist yet to fix them
first** (T643/T644 must conform, not invent a different shape and leave this file unable to ever
pass):

- `EntityRef` carries **`kind`, `id` and `build`** — not just `kind`/`id`. The contract's
  `cost(entity, *, civilisation)` signature has no separate `build` parameter, and `civilisation`
  is the *only* keyword-only parameter FR-023 requires; the build a query is asked against has to
  live somewhere, and the entity reference is what that build is intrinsically a property of (you
  cannot name "unit 358" without also naming which build's rules "358" resolves under). `query.cost`
  is expected to resolve `entity.build` through `snapshot.snapshot_for` internally — this is the
  "wraps `snapshot_for`" the build-resolution test below exercises.
- A civilisation is passed as the **pack's own civilisation name string** (`"Byzantines"`,
  `"Britons"`), matching `normalise.py`'s `civilisations` list and `snapshot.toml`'s
  `civilisations_modelled` — never a numeric id (the numeric id a replay carries is a different,
  unrelated numbering space this feature's query surface has no reason to speak).
- `cost()`'s positive-path return (an `Answer`) carries `.value` (a plain
  `Mapping[str, int]`, resource name to amount — the same shape `rules.json`'s own `cost` field
  already uses), `.snapshot_identity` (the `SnapshotIdentity` of the snapshot that produced it),
  `.source` (the entity's `table_origin`, e.g. `"unit"`), and `.effects` (a sequence, empty when no
  effect matched).
- A gap return carries at least `.cause`, one of the closed set data-model.md §7 names
  (`"civilisation-not-modelled"`, `"no-snapshot-for-build"`, ...), and **never** a `.value`
  attribute — checked explicitly below (`not hasattr(result, "value")`), because a gap that
  happened to carry the baseline value under a different attribute name would defeat the point of
  this test as surely as returning it under `.value` would.
- `effects.Effect` carries `.civilisation`, `.source_text` (the verbatim sentence — data-model.md
  §6), `.modelled` (`"yes"`/`"no"`, spelled exactly as data-model.md §6 spells it) and `.field`.
  `.selector`/`.operation`/`.operand`/`.validated_by` are not asserted here — they are internal to
  *how* the adjusted value in `.value` was computed, and that computation is already proven by
  `.value` itself being correct, so asserting them a second time here would only make this file
  brittle against a reasonable implementation choice T644 has not made yet.

**Why a second promoted snapshot fixture was added**
(`packages/knowledge/snapshots/aoe2techtree-177723-test/`): US2 scenario 2 needs two
*different* promoted snapshots to prove neither query silently answers from the other's contents.
The only committed promoted snapshot before this task, `aoe2techtree-180059`, describes
build 180059 by carry-forward (T642) from source revision `b9d494df...`'s own last-implemented
build, 177723 — a build that same revision's `rules.json` already, directly, describes with no
carry-forward needed at all. The second fixture names exactly that build instead: same
`source_version`, byte-identical `rules.json` (re-derived independently via
`aoe2stats_knowledge.normalise.normalise_pack("aoe2techtree")` and confirmed to match, not
hand-copied data), different `describes_build`, and a `[validation]` record whose `method` is
`"source-implements-build"` rather than `"carry-forward"` — real, and simpler than a second
carry-forward record, because this build genuinely needs none. Its own real content therefore
cannot differ numerically from the first fixture's (nothing changed between 177723 and 180059 —
`aoe2techtree-180059`'s own carry-forward record already attests this for every
intervening build), so the assertion this file makes is not "the two answers differ" but "each
answer is tagged with *its own* snapshot's identity" — which is the actual claim US2 scenario 2
makes, and the one a bug that always resolved to whichever snapshot loads first would still fail.

**T645/T652m**: both promoted fixtures now carry `civilisations_modelled = ["Franks", "Teutons",
"Persians", "Saracens", "Malians", "Tatars"]` — all six the first knowledge snapshot models
(research.md D11: two from the first committed recording, four from the second, none shared),
added to **both** promoted fixtures' `snapshot.toml` identically, so the "two snapshots" test below
is no longer gapped. T645 first populated this list as `["Byzantines", "Koreans", "Franks",
"Persians", "Teutons", "Gurjaras"]`; T652m (2026-09-23) found the underlying raw-id-to-name table
wrong at four of six rows — Byzantines, Koreans and Gurjaras are in neither committed recording at
all — and corrected it to the list above (`effects.toml`'s own header comment carries the full
correction). `"Britons"` is deliberately *never* added to either list — it is this file's
unmodelled-civilisation case, and must stay unmodelled for that case to mean anything.
`"Franks"` held this role until T645 found, by reading the second committed recording's own trained
units and researched technologies against `data.json`'s per-civilisation tables (see
`effects.toml`'s own header comment for the full method), that Franks is genuinely one of the four
civilisations that recording needs — so Franks moved from "this file's placeholder" to "a really
modelled civilisation", and Britons took over the placeholder role instead. T652m's correction does
not disturb this: Britons remains confirmed absent from both committed recordings.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from aoe2stats_knowledge import effects, normalise, query, snapshot
from aoe2stats_knowledge.gaps import KnowledgeGap

#: Real unit id, "Pikeman" (`table_origin = "unit"`) — see this module's docstring for the
#: verification. Touched by no modelled civilisation's cost effect (Franks', Britons' — used
#: below wherever a test needs a real, generic entity and does not itself claim a discount).
_PIKEMAN_ID = "358"

#: Real building id, "Market" (`table_origin = "building"`) — see this module's docstring for the
#: verification. Touched by Saracens' real, modelled "Markets cost -100 wood" effect.
_MARKET_ID = "84"

#: Real building id, "Dock" (`table_origin = "building"`) — see this module's docstring for the
#: verification. Touched by Malians' real, modelled "Buildings cost -15% wood" effect.
_DOCK_ID = "45"

#: The build both committed reference recordings report (`tests/fixtures/replays/README.md`),
#: which `aoe2techtree-180059` describes by carry-forward (T642).
_CARRY_FORWARD_BUILD = 180059

#: The build `aoe2techtree-177723-test` (T646) describes directly, with no
#: carry-forward — the source revision's own last-implemented build.
_DIRECT_BUILD = 177723


def _one_build_higher_than_every_promoted_snapshot() -> int:
    """A build no committed, promoted snapshot describes — computed from whatever is actually
    committed rather than hard-coded, so a future fixture at a higher build cannot silently turn
    this into a build that *does* resolve."""
    resolvable = snapshot.load_resolvable_snapshots()
    assert resolvable, "no promoted snapshot is committed — this test proves nothing without one"
    return max(s.identity.describes_build for s in resolvable) + 1


# ----------------------------------------------------------------------- a discounted building


def test_a_discounted_building_returns_its_adjusted_cost_with_effect_and_source_sentence() -> None:
    """Saracens' Market: `{wood: 175}` minus 100 is `{wood: 75}` (see this module's docstring — a
    whole number needing no rounding-convention decision). The answer must carry the effect that
    produced the adjustment, and that effect must carry the verbatim sentence it was transcribed
    from (data-model.md §6, `source_text`)."""
    from aoe2stats_knowledge import effects, query

    entity = query.EntityRef(kind="building", id=_MARKET_ID, build=_CARRY_FORWARD_BUILD)

    answer = query.cost(entity, civilisation="Saracens")

    assert hasattr(answer, "value"), "a discounted, modelled civilisation must answer, not gap"
    assert answer.value == {"wood": 75}
    assert answer.snapshot_identity.describes_build == _CARRY_FORWARD_BUILD
    assert answer.source == "building"
    assert len(answer.effects) >= 1
    matching = [
        effect
        for effect in answer.effects
        if isinstance(effect, effects.Effect) and effect.civilisation == "Saracens"
    ]
    assert matching, "no Saracens effect was applied to the answer's own .effects"
    effect = matching[0]
    assert effect.field == "cost"
    assert effect.modelled == "yes"
    assert "Markets cost -100 wood" in effect.source_text


def test_a_second_discounted_building_for_a_second_modelled_civilisation_is_also_correct() -> None:
    """Malians' Dock: -15% wood only, on `{wood: 150}` — `150 * 0.85 = 127.5`, a real rounding
    boundary this file resolves by stating round-half-up explicitly (see module docstring):
    `{wood: 128}`. A second, independent real fact (T652m), not a restatement of the Saracens case
    above."""
    from aoe2stats_knowledge import effects, query

    entity = query.EntityRef(kind="building", id=_DOCK_ID, build=_CARRY_FORWARD_BUILD)

    answer = query.cost(entity, civilisation="Malians")

    assert hasattr(answer, "value")
    assert answer.value == {"wood": 128}
    matching = [
        effect
        for effect in answer.effects
        if isinstance(effect, effects.Effect) and effect.civilisation == "Malians"
    ]
    assert matching, "no Malians effect was applied to the answer's own .effects"
    effect = matching[0]
    assert effect.field == "cost"
    assert effect.modelled == "yes"
    assert "Buildings cost -15% wood" in effect.source_text


def test_malians_bombard_tower_cost_is_never_discounted() -> None:
    """T652p (e), at the query layer: Malians' "Buildings cost -15% wood" selector originally
    named building 236 (Bombard Tower), but Malians' own tree file (`MALIANS.json`) marks that
    building `node_status: "NotAvailable"` — this civilisation cannot construct one at all, so
    discounting a cost it can never pay was wrong. `packages/knowledge/tests/test_effects.py`
    proves the same fact one layer down, directly against `effects.apply`; this is the same
    regression through `query.cost`, the path a caller actually uses."""
    from aoe2stats_knowledge import query

    entity = query.EntityRef(kind="building", id="236", build=_CARRY_FORWARD_BUILD)

    answer = query.cost(entity, civilisation="Malians")

    assert hasattr(answer, "value"), "Malians is a modelled civilisation — must answer, not gap"
    assert answer.value == {"gold": 100, "stone": 125, "wood": 0}
    assert answer.effects == (), "no Malians effect should touch a building it cannot construct"


def test_franks_pikeman_cost_is_the_plain_unmodified_baseline() -> None:
    """T652p (c): the module docstring claims Franks/Pikeman is "a plain, unmodified baseline
    answer", and several tests in this file rely on that being true (`Franks` is used wherever a
    test needs *some* modelled civilisation without itself proving a discount) — but until now
    nothing actually asserted the value. A spurious Franks cost effect on Pikeman would have
    passed every test in this file; this is the control that would catch it."""
    from aoe2stats_knowledge import query

    entity = query.EntityRef(kind="unit", id=_PIKEMAN_ID, build=_CARRY_FORWARD_BUILD)

    result = query.cost(entity, civilisation="Franks")

    assert hasattr(result, "value"), (
        f"Franks is a modelled civilisation and Pikeman is a known entity — must answer, got "
        f"{result!r}"
    )
    assert result.value == {"food": 35, "wood": 25}
    assert result.effects == (), "no effect should have touched this baseline answer"


# ------------------------------------------------------------- an unmodelled civilisation gaps


def test_the_same_unit_for_an_unmodelled_civilisation_gaps_and_never_returns_the_baseline() -> None:
    """Britons has no bonus touching Pikeman's cost (module docstring), so Britons' *true* Pikeman
    cost genuinely is the baseline `{food: 35, wood: 25}` — and the conservative rule (research D5)
    must still refuse, because which fields an unmodelled civilisation's bonuses touch is exactly
    what is not known. This is the case the task text calls out by name: never the baseline, even
    when the baseline would coincidentally have been correct."""
    from aoe2stats_knowledge import query

    entity = query.EntityRef(kind="unit", id=_PIKEMAN_ID, build=_CARRY_FORWARD_BUILD)

    result = query.cost(entity, civilisation="Britons")

    assert not hasattr(result, "value"), (
        "an unmodelled civilisation must gap, never answer — even with a value equal to the "
        f"baseline: got {getattr(result, 'value', None)!r}"
    )
    assert result.cause == "civilisation-not-modelled"

    from aoe2stats_knowledge import gaps

    # T647: the gap query.py returns is the real FR-035 record, not an interim, two-field shape —
    # it names the entity, the field actually asked for and the civilisation that failed to
    # answer, and carries a computed severity/prevents rather than nothing at all.
    assert isinstance(result, gaps.KnowledgeGap)
    assert result.entity_kind == "unit"
    assert result.entity_id == _PIKEMAN_ID
    assert result.field == "cost"
    assert result.civilisation == "Britons"
    assert result.severity in gaps.SEVERITIES


# ------------------------------------------------------- T652u remediation, defect 2: a teammate


def test_a_teammate_outside_civilisations_modelled_gaps_naming_that_teammate() -> None:
    """T652u remediation, defect 2 (coordinator, measured against the working tree): "a teammate
    whose civilisation is not modelled makes the answer unknown." Franks is modelled and Pikeman's
    cost is untouched by any Franks effect (module docstring) — the query's *own* civilisation is
    never the issue here. Britons is not in `civilisations_modelled`, so which fields *its* bonuses
    touch is exactly what research.md D5's conservative rule says is unknown — and that rule
    applies to a teammate exactly as it does to the queried civilisation itself, because a team
    bonus of Britons' own could touch this same field and this package has no way to know.
    `context.team` naming Britons at all, regardless of whether any *known* effect touches this
    entity/field, is what must gap — the existing `civilisation-not-modelled` cause, naming the
    teammate, not a new cause."""
    from aoe2stats_knowledge import gaps, query

    entity = query.EntityRef(kind="unit", id=_PIKEMAN_ID, build=_CARRY_FORWARD_BUILD)

    result = query.cost(
        entity, civilisation="Franks", context=query.Context(team=frozenset({"Franks", "Britons"}))
    )

    assert not hasattr(result, "value"), (
        "a teammate outside civilisations_modelled must gap the whole query, even though the "
        f"queried civilisation (Franks) is itself modelled: got {getattr(result, 'value', None)!r}"
    )
    assert isinstance(result, gaps.KnowledgeGap)
    assert result.cause == "civilisation-not-modelled", (
        f"no new cause — the existing one research.md D5 already defines, got {result.cause!r}"
    )
    assert result.civilisation == "Britons", (
        "the gap must name the unmodelled teammate, not the queried civilisation (Franks, which "
        f"is modelled) — got {result.civilisation!r}"
    )


def test_a_team_of_only_modelled_civilisations_answers_normally() -> None:
    """The contrast case defect 2's own fix must not break: a `context.team` made only of
    civilisations `civilisations_modelled` already names must not gap — the same query as above,
    with Teutons (modelled) in place of Britons (not modelled)."""
    from aoe2stats_knowledge import query

    entity = query.EntityRef(kind="unit", id=_PIKEMAN_ID, build=_CARRY_FORWARD_BUILD)

    result = query.cost(
        entity, civilisation="Franks", context=query.Context(team=frozenset({"Franks", "Teutons"}))
    )

    assert hasattr(result, "value"), (
        f"a team of only modelled civilisations must still answer — got {result!r}"
    )
    assert result.value == {"food": 35, "wood": 25}


# --------------------------------------------------------------------- a build with no snapshot


def test_a_build_one_higher_than_every_snapshot_describes_gaps() -> None:
    """`snapshot_for`'s existing gap path (T641), exercised through the query layer once `cost()`
    wraps it (contracts/knowledge-base.md, "Resolution by build"): exact match only, no nearest."""
    from aoe2stats_knowledge import query

    too_high = _one_build_higher_than_every_promoted_snapshot()
    entity = query.EntityRef(kind="unit", id=_PIKEMAN_ID, build=too_high)

    result = query.cost(entity, civilisation="Franks")

    assert not hasattr(result, "value")
    assert result.cause == "no-snapshot-for-build"

    from aoe2stats_knowledge import gaps

    # A whole-build gap names no entity, field or civilisation — nothing about the build is known,
    # not one field of it (gaps.py's `_WHOLE_BUILD_CAUSES`).
    assert isinstance(result, gaps.KnowledgeGap)
    assert result.entity_kind is None
    assert result.entity_id is None
    assert result.field is None
    assert result.civilisation is None
    assert result.build == too_high


# ------------------------------------------------------------------------ civilisation is forced


def test_asking_without_a_civilisation_keyword_is_a_type_error() -> None:
    """FR-023: `civilisation` is keyword-only and required on every rule query, "so there is no way
    to ask for a generic value" — checked here as a property of the real function object's own
    calling convention, not by reading the signature."""
    from aoe2stats_knowledge import query

    entity = query.EntityRef(kind="unit", id=_PIKEMAN_ID, build=_CARRY_FORWARD_BUILD)

    with pytest.raises(TypeError):
        query.cost(entity)  # civilisation omitted entirely

    with pytest.raises(TypeError):
        query.cost(entity, "Franks")  # type: ignore[misc]  # civilisation passed positionally


# ------------------------------------------------------- two snapshots, two independent answers


def test_two_snapshots_answer_from_their_own_contents_and_neither_is_upgraded_to_the_other() -> (
    None
):
    """US2 scenario 2, against the two real, committed promoted snapshots
    (`aoe2techtree-180059`, build 180059; `aoe2techtree-177723-test`, build
    177723 — see module docstring for why a second fixture was added and why their content is
    identical). The claim under test is not that the two costs differ — nothing changed between
    these two builds, so they should not — but that each answer is tagged with *its own*
    snapshot's identity, never the other's: a bug that always resolved to whichever snapshot loads
    first would produce an identical wrong answer for one of these two calls, and this is the
    assertion that catches it."""
    from aoe2stats_knowledge import query

    entity_at_carry_forward_build = query.EntityRef(
        kind="unit", id=_PIKEMAN_ID, build=_CARRY_FORWARD_BUILD
    )
    entity_at_direct_build = query.EntityRef(kind="unit", id=_PIKEMAN_ID, build=_DIRECT_BUILD)

    answer_from_carry_forward_snapshot = query.cost(
        entity_at_carry_forward_build, civilisation="Franks"
    )
    answer_from_direct_snapshot = query.cost(entity_at_direct_build, civilisation="Franks")

    assert hasattr(answer_from_carry_forward_snapshot, "value")
    assert hasattr(answer_from_direct_snapshot, "value")
    assert (
        answer_from_carry_forward_snapshot.snapshot_identity.describes_build == _CARRY_FORWARD_BUILD
    )
    assert answer_from_direct_snapshot.snapshot_identity.describes_build == _DIRECT_BUILD
    assert (
        answer_from_carry_forward_snapshot.snapshot_identity
        != answer_from_direct_snapshot.snapshot_identity
    )
    # The real content is identical between these two builds (nothing changed — see docstring),
    # so the values themselves are expected to agree; it is the identity tagging above that proves
    # neither call was silently answered from the other snapshot.
    assert answer_from_carry_forward_snapshot.value == answer_from_direct_snapshot.value


# ------------------------------------------------------------- a genuinely unknown entity gaps


#: Not a real id in any table of the committed pack (verified above against the same promoted
#: snapshot `rules.json` this file's other real ids are checked against) — the "genuinely unknown
#: entity" case, distinct from an unmodelled civilisation: no civilisation could ever answer for an
#: id that is not in the snapshot at all (T643, added beyond T646's own six tests, since a real
#: query surface must not crash or silently return `None` on an unknown id).
_UNKNOWN_UNIT_ID = "999999999"


def test_an_entity_id_absent_from_the_snapshot_entirely_gaps_and_never_crashes() -> None:
    """`cost()` on an id that is in no table of the resolved snapshot at all must gap with
    `entity-absent` (data-model.md §7's closed cause set) rather than raising a `KeyError`/
    `AttributeError` or silently returning `None` dressed up as a value — this is true regardless
    of which civilisation is asked, including one that could in principle be modelled one day."""
    from aoe2stats_knowledge import query

    entity = query.EntityRef(kind="unit", id=_UNKNOWN_UNIT_ID, build=_CARRY_FORWARD_BUILD)

    result = query.cost(entity, civilisation="Franks")

    assert not hasattr(result, "value"), f"an unknown entity id must gap, got {result!r}"
    assert result.cause == "entity-absent"

    from aoe2stats_knowledge import gaps

    assert isinstance(result, gaps.KnowledgeGap)
    assert result.entity_kind == "unit"
    assert result.entity_id == _UNKNOWN_UNIT_ID
    assert result.field == "cost"
    assert result.civilisation == "Franks"


# ------------------------------------------------------------------------------- prerequisites()


def test_prerequisites_always_refuses_field_absent_for_a_named_entity() -> None:
    """T652y: `rules.json` carries no `prerequisites` field at all — the pack's own tree
    `link_id`/`link_node_type` is the tech-tree screen's display link, not a rule of the game
    (research.md D3), so `prerequisites()` gaps every entity the snapshot names, with the same
    `field-absent` cause `_field_present` already produces for any other missing field. The
    register's one entry that named this field, `reconstruction.prerequisite_order_check`, is
    `blocked` (T652y), so D7 computes this gap `informational`, never `blocking`."""
    from aoe2stats_knowledge import gaps, query

    entity = query.EntityRef(kind="unit", id=_PIKEMAN_ID, build=_CARRY_FORWARD_BUILD)

    result = query.prerequisites(entity, civilisation="Franks")

    assert not hasattr(result, "value"), f"prerequisites must always gap, got {result!r}"
    assert isinstance(result, gaps.KnowledgeGap)
    assert result.cause == "field-absent"
    assert result.entity_kind == "unit"
    assert result.entity_id == _PIKEMAN_ID
    assert result.field == "prerequisites"
    assert result.civilisation == "Franks"
    assert result.severity == "informational"


def test_prerequisites_still_answers_entity_absent_for_an_unknown_id() -> None:
    """The contrast the same task asks for: an id the snapshot does not name at all answers
    `entity-absent`, ahead of the field-presence check — `prerequisites` never masks a genuinely
    unknown entity behind the always-refusing `field-absent` cause."""
    from aoe2stats_knowledge import gaps, query

    entity = query.EntityRef(kind="unit", id=_UNKNOWN_UNIT_ID, build=_CARRY_FORWARD_BUILD)

    result = query.prerequisites(entity, civilisation="Franks")

    assert not hasattr(result, "value"), f"an unknown entity id must gap, got {result!r}"
    assert isinstance(result, gaps.KnowledgeGap)
    assert result.cause == "entity-absent"
    assert result.entity_id == _UNKNOWN_UNIT_ID


# ------------------------------------------------------------------------------------- name()


def test_name_is_not_civilisation_qualified_and_resolves_the_real_entity() -> None:
    """`name()` takes no `civilisation` keyword at all (contract: "Civilisation qualification",
    "`name` is not civilisation-qualified") and answers the real, stored name for a known id."""
    from aoe2stats_knowledge import query

    entity = query.EntityRef(kind="unit", id=_PIKEMAN_ID, build=_CARRY_FORWARD_BUILD)

    answer = query.name(entity)

    assert answer.value == "Pikeman"
    assert answer.source == "unit"
    assert answer.snapshot_identity.describes_build == _CARRY_FORWARD_BUILD


def test_name_degrades_to_the_bare_identifier_for_an_unknown_entity_instead_of_gapping() -> None:
    """003 FR-043a, quoted directly by the contract: "a confident wrong name is worse than a bare
    id" — an id `name()` cannot resolve degrades to the bare identifier string, and this is the one
    query in the surface that never gaps for that reason (contracts/knowledge-base.md,
    "Civilisation qualification": "it never gaps an analysis")."""
    from aoe2stats_knowledge import query

    entity = query.EntityRef(kind="unit", id=_UNKNOWN_UNIT_ID, build=_CARRY_FORWARD_BUILD)

    answer = query.name(entity)

    assert hasattr(answer, "value"), "an unresolvable identifier degrades, it never gaps"
    assert answer.value == _UNKNOWN_UNIT_ID


def test_name_still_gaps_when_the_build_itself_has_no_snapshot() -> None:
    """The "never gaps" rule is about an unresolvable *identifier* within a resolved snapshot —
    there is still no snapshot to even attempt a lookup against for a build nothing describes, so
    this is the one case `name()` does gap, with the same `no-snapshot-for-build` cause every other
    query uses for it."""
    from aoe2stats_knowledge import query

    too_high = _one_build_higher_than_every_promoted_snapshot()
    entity = query.EntityRef(kind="unit", id=_PIKEMAN_ID, build=too_high)

    result = query.name(entity)

    assert not hasattr(result, "value")
    assert result.cause == "no-snapshot-for-build"


# ------------------------------------------- T763: available_to answers the civilisation's tree
#
# A second-version `rules.json` carries, per civilisation, the units, buildings and technologies its
# tree offers (`normalise.py`), and `available_to` answers membership, then applies effects. A
# first-version `rules.json` carries no tree, so a first-version snapshot makes no membership claim
# and answers true for any entity that resolves, as it always has (contracts/knowledge-base.md,
# "Civilisation qualification"). The synthetic cases below install a throwaway snapshot; the
# recording cases derive second-version rules from the vendored pack and substitute them for one
# build with `query.rules_overrides`, so no installed snapshot is touched.

_AVAILABILITY_BUILD = 900_003
_VALIDATION = """
[validation]
method = "second-source"
checked_against = "a test"
performed_by = "a test author"
performed_at = "2026-01-01"
"""

#: Franks' tree offers the Militia (74), the Barracks (12) and technology 197; Goths' tree offers
#: the Huskarl (41) too. Unit 41 and technology 98 are in no Franks tree.
_TREES_RULES: dict[str, Any] = {
    "civilisations": {
        "Franks": {"unit": ["74"], "building": ["12"], "technology": ["197"]},
        "Goths": {"unit": ["41", "74"], "building": ["12"], "technology": ["197"]},
    },
    "entities": {
        "building": {
            "12": {"name": "Barracks", "produced_at": None, "table_origin": "building"},
            "101": {"name": "Stable", "produced_at": None, "table_origin": "building"},
        },
        "unit": {
            "41": {"name": "Huskarl", "produced_at": None, "table_origin": "unit"},
            "74": {"name": "Militia", "produced_at": None, "table_origin": "unit"},
        },
        "technology": {
            "98": {"name": "Elite Skirmisher", "produced_at": None, "table_origin": "tech"},
            "197": {"name": "Pikeman", "produced_at": None, "table_origin": "tech"},
        },
    },
}

#: The same entities with no tree at all: `civilisations` is the first version's list of names.
_NAMES_RULES: dict[str, Any] = {**_TREES_RULES, "civilisations": ["Franks", "Goths"]}


def _availability_effect(
    *, civilisation: str, entity: str, operand: str, condition: str = "", kind: str = "unit"
) -> str:
    return f"""
[[effect]]
civilisation = "{civilisation}"
source_key = "0"
source_text = "synthetic availability"
modelled = "yes"
field = "available_to"
operation = "set"
operand = {operand}
{condition}selector = [{{ kind = "{kind}", id = "{entity}" }}]
validated_by = "synthetic"
"""


class _ResourcesShim:
    def __init__(self, package_root: Path) -> None:
        self._package_root = package_root

    def files(self, _package: str) -> Path:
        return self._package_root


@pytest.fixture
def install_availability(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[..., str]:
    package_root = tmp_path / "pkg"
    snapshots = package_root / "snapshots"
    snapshots.mkdir(parents=True)
    monkeypatch.setattr(snapshot, "_snapshots_root", lambda: snapshots)
    shim = _ResourcesShim(package_root)
    for module in (snapshot, query, effects):
        monkeypatch.setattr(module, "resources", shim)

    def _install(
        rules: dict[str, Any] = _TREES_RULES,
        *,
        effects_toml: str = "# none\n",
        normaliser_version: object = None,
        aliases_toml: str | None = None,
        modelled: str = '["Franks", "Goths"]',
    ) -> str:
        directory = f"availability-{uuid.uuid4().hex[:8]}"
        target = snapshots / directory
        target.mkdir()
        rules_bytes = json.dumps(rules).encode("utf-8")
        effects_bytes = effects_toml.encode("utf-8")
        aliases_bytes = aliases_toml.encode("utf-8") if aliases_toml is not None else None
        (target / "rules.json").write_bytes(rules_bytes)
        (target / "effects.toml").write_bytes(effects_bytes)
        (target / "disagreements.toml").write_text("# none\n", encoding="utf-8")
        if aliases_bytes is not None:
            (target / "aliases.toml").write_bytes(aliases_bytes)
        digest = snapshot.compute_digest(rules_bytes, effects_bytes, aliases_bytes)
        version_line = (
            f"normaliser_version = {normaliser_version}\n" if normaliser_version is not None else ""
        )
        (target / "snapshot.toml").write_text(
            "[snapshot]\n"
            'source = "aoe2techtree"\n'
            'source_version = "deadbeef"\n'
            f"describes_build = {_AVAILABILITY_BUILD}\n"
            f'digest = "{digest}"\n'
            "promoted = true\n"
            f"civilisations_modelled = {modelled}\n"
            f"{version_line}" + _VALIDATION,
            encoding="utf-8",
        )
        return directory

    return _install


def _available(
    kind: str,
    entity_id: str,
    civilisation: str = "Franks",
    *,
    context: query.Context | None = None,
) -> Any:
    return query.available_to(
        query.EntityRef(kind=kind, id=entity_id, build=_AVAILABILITY_BUILD),
        civilisation=civilisation,
        context=context,
    )


def test_an_entity_inside_the_civilisations_tree_answers_true_with_no_effect(
    install_availability: Callable[..., str],
) -> None:
    install_availability(normaliser_version=2)

    answer = _available("unit", "74")

    assert not isinstance(answer, KnowledgeGap)
    assert answer.value is True
    assert answer.effects == ()


def test_an_entity_outside_the_civilisations_tree_answers_false(
    install_availability: Callable[..., str],
) -> None:
    install_availability(normaliser_version=2)

    franks = _available("unit", "41")
    goths = _available("unit", "41", "Goths")

    assert not isinstance(franks, KnowledgeGap)
    assert franks.value is False
    assert not isinstance(goths, KnowledgeGap)
    assert goths.value is True


def test_each_kind_is_read_from_its_own_list(install_availability: Callable[..., str]) -> None:
    """Unit 12 is not building 12: a building id is never answered by the unit list."""
    rules = json.loads(json.dumps(_TREES_RULES))
    rules["entities"]["unit"]["12"] = {"name": "x", "produced_at": None, "table_origin": "unit"}
    install_availability(rules, normaliser_version=2)

    assert _available("building", "12").value is True
    assert _available("unit", "12").value is False


def test_an_upgrade_technology_whose_keyed_unit_is_outside_the_tree_answers_false(
    install_availability: Callable[..., str],
) -> None:
    """Contrast to technology 197, which is in the tree: 98 is not."""
    install_availability(normaliser_version=2)

    assert _available("technology", "197").value is True
    assert _available("technology", "98").value is False


def test_an_unconditional_false_removes_an_entity_inside_the_tree(
    install_availability: Callable[..., str],
) -> None:
    toml = _availability_effect(civilisation="Franks", entity="74", operand="false")
    install_availability(effects_toml=toml, normaliser_version=2)

    answer = _available("unit", "74")

    assert not isinstance(answer, KnowledgeGap)
    assert answer.value is False
    assert [e.source_text for e in answer.effects] == ["synthetic availability"]
    assert _available("unit", "74", "Goths").value is True  # another civilisation is untouched


def test_an_unconditional_true_adds_an_entity_outside_the_tree(
    install_availability: Callable[..., str],
) -> None:
    toml = _availability_effect(civilisation="Franks", entity="41", operand="true")
    install_availability(effects_toml=toml, normaliser_version=2)

    assert _available("unit", "41").value is True


@pytest.mark.parametrize(
    ("researched", "expected"),
    [(frozenset(), True), (frozenset({"1230"}), False)],
    ids=["before the technology", "after the technology"],
)
def test_a_researched_false_answers_before_and_after_its_technology(
    install_availability: Callable[..., str], researched: frozenset[str], expected: bool
) -> None:
    condition = 'condition = "researched"\ncondition_technology = "1230"\n'
    toml = _availability_effect(
        civilisation="Franks", entity="74", operand="false", condition=condition
    )
    install_availability(effects_toml=toml, normaliser_version=2)

    answer = _available("unit", "74", context=query.Context(researched=researched))

    assert not isinstance(answer, KnowledgeGap)
    assert answer.value is expected


def test_a_researched_effect_raises_without_a_context(
    install_availability: Callable[..., str],
) -> None:
    condition = 'condition = "researched"\ncondition_technology = "1230"\n'
    toml = _availability_effect(
        civilisation="Franks", entity="74", operand="false", condition=condition
    )
    install_availability(effects_toml=toml, normaliser_version=2)

    with pytest.raises(effects.ContextRequired):
        _available("unit", "74")


@pytest.mark.parametrize(("age", "expected"), [(1, True), (2, False)])
def test_an_age_conditioned_true_answers_by_age(
    install_availability: Callable[..., str], age: int, expected: bool
) -> None:
    toml = _availability_effect(
        civilisation="Franks",
        entity="41",
        operand="{ 1 = true }",
        condition='condition = "age"\n',
    )
    install_availability(effects_toml=toml, normaliser_version=2)

    answer = _available("unit", "41", context=query.Context(age=age))

    assert not isinstance(answer, KnowledgeGap)
    assert answer.value is expected


def test_a_civilisation_the_trees_do_not_name_gaps_field_absent(
    install_availability: Callable[..., str],
) -> None:
    """A modelled civilisation with no tree in a second-version snapshot is a defect, and is a gap,
    never a default."""
    install_availability(normaliser_version=2, modelled='["Franks", "Goths", "Vikings"]')

    gap = _available("unit", "74", "Vikings")

    assert isinstance(gap, KnowledgeGap)
    assert gap.cause == "field-absent"
    assert gap.field == "available_to"


def test_an_aliased_identifier_is_read_through_its_targets_membership(
    install_availability: Callable[..., str],
) -> None:
    alias = (
        '[[alias]]\nkind = "unit"\nid = "490"\ntarget = "74"\nsource_name = "Militia"\n'
        'source = "a test"\nread_on = "2026-10-19"\n'
    )
    install_availability(normaliser_version=2, aliases_toml=alias)

    answer = _available("unit", "490")
    assert not isinstance(answer, KnowledgeGap)
    assert answer.value is True and answer.alias is not None
    other = _available("unit", "490", "Goths")
    assert other.value is True


def test_a_first_version_snapshot_makes_no_membership_claim(
    install_availability: Callable[..., str],
) -> None:
    """The trap: its `rules.json` carries no tree, so unit 41 (outside Franks' tree in the second
    version) still answers true, as every installed snapshot does. The snapshot's identity pins
    what it answers (SC-005); a published analysis must reproduce."""
    install_availability(_NAMES_RULES)  # no `normaliser_version`: the first

    assert _available("unit", "41").value is True
    assert _available("technology", "98").value is True


def test_an_effect_still_applies_over_a_first_version_snapshots_baseline(
    install_availability: Callable[..., str],
) -> None:
    toml = _availability_effect(civilisation="Franks", entity="74", operand="false")
    install_availability(_NAMES_RULES, effects_toml=toml)

    assert _available("unit", "74").value is False
    assert _available("unit", "41").value is True


def test_the_installed_snapshots_answer_true_for_an_entity_outside_the_tree() -> None:
    """Nothing green on an installed snapshot flips: Franks cannot train the Huskarl (41) in the
    pack's tree, and the installed (first-version) snapshot still answers true."""
    answer = query.available_to(
        query.EntityRef(kind="unit", id="41", build=180059), civilisation="Franks"
    )

    assert not isinstance(answer, KnowledgeGap)
    assert answer.value is True


# the loader checks that the version and the shape agree


@pytest.mark.parametrize("text", ["", "normaliser_version = 1\n"])
def test_a_snapshot_without_a_version_or_naming_the_first_is_first_version(text: str) -> None:
    toml = f'[snapshot]\nsource = "a"\n{text}'
    assert snapshot.parse_normaliser_version(toml) == 1


def test_a_snapshot_names_the_second_version() -> None:
    assert snapshot.parse_normaliser_version("[snapshot]\nnormaliser_version = 2\n") == 2


@pytest.mark.parametrize("value", ["0", "3", "true", '"2"', "1.0", "-1"])
def test_a_version_the_normaliser_does_not_have_is_refused(value: str) -> None:
    with pytest.raises(snapshot.SnapshotError, match="normaliser_version"):
        snapshot.parse_normaliser_version(f"[snapshot]\nnormaliser_version = {value}\n")


def test_the_loader_reads_the_version_a_snapshot_names(
    install_availability: Callable[..., str],
) -> None:
    second = install_availability(normaliser_version=2)
    first = install_availability(_NAMES_RULES)

    assert snapshot.load_snapshot(second).normaliser_version == 2
    assert snapshot.load_snapshot(first).normaliser_version == 1


def test_the_loader_refuses_a_second_version_snapshot_whose_civilisations_are_a_list(
    install_availability: Callable[..., str],
) -> None:
    directory = install_availability(_NAMES_RULES, normaliser_version=2)

    with pytest.raises(snapshot.SnapshotError, match="normaliser_version"):
        snapshot.load_snapshot(directory)


def test_the_loader_refuses_a_first_version_snapshot_whose_civilisations_are_trees(
    install_availability: Callable[..., str],
) -> None:
    directory = install_availability(_TREES_RULES)

    with pytest.raises(snapshot.SnapshotError, match="normaliser_version"):
        snapshot.load_snapshot(directory)


@pytest.mark.parametrize(
    "tree",
    [
        {"unit": ["74"], "building": ["12"]},  # a list missing
        {"unit": ["74"], "building": ["12"], "technology": [197]},  # an id that is not a string
        {"unit": ["74"], "building": ["12"], "technology": "197"},  # not a list
        {"unit": ["74"], "building": ["12"], "technology": [], "extra": []},  # another key
    ],
)
def test_the_loader_refuses_a_malformed_tree(
    install_availability: Callable[..., str], tree: dict[str, Any]
) -> None:
    rules = json.loads(json.dumps(_TREES_RULES))
    rules["civilisations"]["Franks"] = tree
    directory = install_availability(rules, normaliser_version=2)

    with pytest.raises(snapshot.SnapshotError, match="Franks"):
        snapshot.load_snapshot(directory)


# every entity a participant of a committed recording ordered

_FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "replays"
_PACKS = Path(__file__).resolve().parents[1] / "packs"


def _pack_pinned_at(commit: str) -> str:
    matches = [
        manifest.parent.name
        for manifest in sorted(_PACKS.glob("*/MANIFEST.json"))
        if json.loads(manifest.read_text(encoding="utf-8"))["commit"] == commit
    ]
    assert len(matches) == 1, f"{commit} must be pinned by exactly one vendored pack: {matches}"
    return matches[0]


def _derived_second_version_rules(commit: str) -> dict[str, Any]:
    pack = normalise.normalise_pack(_pack_pinned_at(commit), version=2)
    rules: dict[str, Any] = json.loads(normalise.rules_json_bytes(pack))
    return rules


def _ordered_by_participant(
    stream: Path, civilisation_names: dict[int, str]
) -> tuple[int, dict[str, set[tuple[str, str]]]]:
    """The build and, per participant civilisation name, every unit queued, building placed and
    technology researched in the recording's canonical stream."""
    events = json.loads(stream.read_text(encoding="utf-8"))["events"]
    build = 0
    civilisation_of_slot: dict[int, str] = {}
    ordered: dict[str, set[tuple[str, str]]] = {}
    for event in events:
        kind, payload, slot = event["kind"], event["payload"], event["participant"]
        if kind == "match-started":
            build = payload["build"]
            for entry in payload["participants"]:
                civilisation_of_slot[entry["slot"]] = civilisation_names[entry["civilisation"]]
            continue
        found: tuple[str, str] | None = None
        if kind == "unit-queued":
            found = ("unit", str(payload["unit_id"]))
        elif kind == "building-placed":
            found = ("building", str(payload["building_id"]))
        elif kind == "research-queued":
            found = ("technology", str(payload["technology_id"]))
        if found is not None and slot in civilisation_of_slot:
            ordered.setdefault(civilisation_of_slot[slot], set()).add(found)
    return build, ordered


_RECORDINGS = (
    "AgeIIDE_Replay_500546441",
    "AgeIIDE_Replay_504695319",
    "AgeIIDE_Replay_511523321",
)

#: What each recording's participants ordered that does not answer true, exactly, and why. A key is
#: `(civilisation, kind, id)`; the value is `False` for an answer and `"entity-absent"` for a gap.
#:
#: **(Persians, unit 1755) answers false, and that is the correct answer.** Recording 504695319's
#: slot 2 queues unit 1755 three times at a Stable. The repository owner's reading, in chat,
#: 2026-10-19: "persians have not camel scout, but they have Camel Rider and heavy camel". The pack
#: agrees: 1755 is in the Unit list of Gurjaras alone (`data.json`, both vendored revisions), and
#: the PERSIANS tree has no node 1755. `aoc-reference-data`'s `objects` names 1755 "Camel Scout"
#: (read 2026-10-18). A replay carries intent, never outcome: the order is one the game does not
#: allow, so it is not a defect in membership.
#:
#: **Buildings 490 (Franks, Sicilians) and 673 (Teutons) are `entity-absent` today**: the pack names
#: neither, and no installed snapshot carries an alias for them until T767's does. The expectation
#: is strict, not skipped: when a snapshot carries the alias, this entry fails and is deleted.
_EXPECTED_NOT_TRUE: dict[str, dict[tuple[str, str, str], object]] = {
    "AgeIIDE_Replay_500546441": {},
    "AgeIIDE_Replay_504695319": {
        ("Persians", "unit", "1755"): False,
        ("Franks", "building", "490"): "entity-absent",
        ("Teutons", "building", "673"): "entity-absent",
    },
    "AgeIIDE_Replay_511523321": {("Sicilians", "building", "490"): "entity-absent"},
}


@pytest.mark.parametrize("recording", _RECORDINGS)
def test_every_ordered_entity_answers_true_for_its_participants_civilisation(
    recording: str,
) -> None:
    """Under second-version rules derived in the test from the vendored pack the build's snapshot
    names (no network, no new installed snapshot), every unit queued, building placed and
    technology researched answers true for the civilisation of the participant who ordered it,
    except exactly `_EXPECTED_NOT_TRUE`. Technologies 98, 100 and 222 (match 511523321) and 197 and
    429 (504695319) are placed only by `unit_upgrades`, through every key."""
    stream = _FIXTURES / f"{recording}.canonical.json"
    build = json.loads(stream.read_text(encoding="utf-8"))["events"][0]["payload"]["build"]
    resolved = snapshot.snapshot_for(build)
    assert not isinstance(resolved, KnowledgeGap)
    names = effects.civilisation_id_names(resolved.directory)
    _build, ordered = _ordered_by_participant(stream, names)
    assert build == _build and ordered
    rules = _derived_second_version_rules(resolved.identity.source_version)

    not_true: dict[tuple[str, str, str], object] = {}
    checked = 0
    with query.rules_overrides({build: rules}):
        for civilisation, entities in ordered.items():
            for kind, entity_id in sorted(entities):
                answer = query.available_to(
                    query.EntityRef(kind=kind, id=entity_id, build=build),
                    civilisation=civilisation,
                )
                checked += 1
                if isinstance(answer, KnowledgeGap):
                    not_true[(civilisation, kind, entity_id)] = answer.cause
                elif answer.value is not True:
                    not_true[(civilisation, kind, entity_id)] = answer.value
    assert checked >= 50
    assert not_true == _EXPECTED_NOT_TRUE[recording]


def test_the_owners_contrast_for_the_camel_units() -> None:
    """Camel Rider (329) and Heavy Camel Rider (330) answer true for the Persians; Camel Scout
    (1755) answers false for them and is in the Gurjaras' tree. Read from the pack:
    `trees/PERSIANS.json` names node 329 "Camel Rider" and node 330 "Heavy Camel Rider", and
    `rules.json` names 329 and 330 the same (the strings carry a line break in 330's name).
    Gurjaras are modelled in no installed snapshot, so their side is read from the derived tree."""
    build = 180059
    resolved = snapshot.snapshot_for(build)
    assert not isinstance(resolved, KnowledgeGap)
    rules = _derived_second_version_rules(resolved.identity.source_version)
    with query.rules_overrides({build: rules}):
        for unit_id in ("329", "330"):
            answer = query.available_to(
                query.EntityRef(kind="unit", id=unit_id, build=build), civilisation="Persians"
            )
            assert not isinstance(answer, KnowledgeGap)
            assert answer.value is True
        scout = query.available_to(
            query.EntityRef(kind="unit", id="1755", build=build), civilisation="Persians"
        )
        assert not isinstance(scout, KnowledgeGap)
        assert scout.value is False
    assert "1755" in rules["civilisations"]["Gurjaras"]["unit"]
    assert "1755" not in rules["civilisations"]["Persians"]["unit"]
    assert {"329", "330"} <= set(rules["civilisations"]["Persians"]["unit"])
    assert "Camel Rider" in rules["entities"]["unit"]["329"]["name"]
    assert "Camel Rider" in rules["entities"]["unit"]["330"]["name"]
