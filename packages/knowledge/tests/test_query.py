"""T646: the query surface (T643), civilisation effects (T644) and civilisation modelling (T645),
written before any of the three exist — every test below is `xfail(strict=True)` for exactly that
reason, and each names which of T643/T644/T645 removes its marker.

Contract: [contracts/knowledge-base.md](../../../specs/006-replay-analysis-foundations/contracts/
knowledge-base.md), "The query surface" and "Civilisation qualification". Research:
[research.md](../../../specs/006-replay-analysis-foundations/research.md) **D5** (civilisation
bonuses are hand-modelled, an unmodelled civilisation is a gap, never the baseline). Data model:
[data-model.md](../../../specs/006-replay-analysis-foundations/data-model.md) §6 ("Civilisation
effect") and §7 ("Knowledge gap"). Spec: **US2** scenario 2 ("two different knowledge snapshots
... each answers from its own contents and neither is silently upgraded to the other").

**Real facts this file's numbers are derived from, not invented** (verified directly against the
committed pack, `packages/knowledge/packs/aoe2techtree/`, and the committed promoted snapshot,
`packages/knowledge/snapshots/aoe2techtree-fixture-promoted/rules.json`):

- Unit id `358` is "Pikeman" (`table_origin = "unit"`), cost `{food: 35, wood: 25}`, and is present
  in both Byzantines' and Franks' unit lists (`data.json`'s `civs.Byzantines.Unit` /
  `civs.Franks.Unit`) — the same id resolves for both civilisations queried below.
- Byzantines' bonus prose (`strings.en.json`, the string named by `civs.Byzantines.help_string_id`,
  `120156`): "Camel Riders, Skirmishers and Spearman-line cost -25%". Pikeman is the Spearman
  line's second member, so this line touches its cost. -25% of `{food: 35, wood: 25}` is
  `{food: 26.25, wood: 18.75}` — neither value lands on a rounding boundary (`.5`), so
  round-half-up and Python's own banker's `round()` agree without needing to pin one down:
  `{food: 26, wood: 19}`.
- Unit id `24` is "Crossbowman" (`table_origin = "unit"`), cost `{gold: 45, wood: 25}`, present in
  both Koreans' and Byzantines' unit lists.
- Koreans' bonus prose (`civs.Koreans.help_string_id`, `120167`, read directly from
  `strings.en.json`): "Ranged Soldiers and Infantry cost -50% wood". Crossbowman is a Ranged
  Soldier, so only its wood
  cost is touched: `25 * 0.5 = 12.5`, which **does** land on a rounding boundary. This file states
  the convention explicitly rather than leaving it to whichever rounding `round()` happens to pick:
  **round half up** (`12.5 -> 13`), because that is the convention this repository's own docstrings
  already use when a display quantity is derived from a fraction (see e.g. `docs/data-sources.md`'s
  ratio figures) and it matches the community-known in-game value for a Korean Crossbowman
  (45 gold, 13 wood). T644 must apply this same convention, or this test's marker never comes off.
- Franks has no bonus that touches Pikeman's cost (`civs.Franks.help_string_id`, `120151`:
  foragers, free mill technologies, mounted-unit HP, Castle cost) — chosen deliberately so the
  "unmodelled civilisation" test cannot pass by coincidence: Franks' true Pikeman cost genuinely
  *is* the baseline, and the conservative rule (research D5) must still gap it, because which
  fields an unmodelled civilisation's bonuses touch is exactly what is not known.

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
  `"Franks"`), matching `normalise.py`'s `civilisations` list and `snapshot.toml`'s
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
(`packages/knowledge/snapshots/aoe2techtree-fixture-promoted-177723/`): US2 scenario 2 needs two
*different* promoted snapshots to prove neither query silently answers from the other's contents.
The only committed promoted snapshot before this task, `aoe2techtree-fixture-promoted`, describes
build 180059 by carry-forward (T642) from source revision `b9d494df...`'s own last-implemented
build, 177723 — a build that same revision's `rules.json` already, directly, describes with no
carry-forward needed at all. The second fixture names exactly that build instead: same
`source_version`, byte-identical `rules.json` (re-derived independently via
`aoe2stats_knowledge.normalise.normalise_pack()` and confirmed to match, not hand-copied data),
different `describes_build`, and a `[validation]` record whose `method` is
`"source-implements-build"` rather than `"carry-forward"` — real, and simpler than a second
carry-forward record, because this build genuinely needs none. Its own real content therefore
cannot differ numerically from the first fixture's (nothing changed between 177723 and 180059 —
`aoe2techtree-fixture-promoted`'s own carry-forward record already attests this for every
intervening build), so the assertion this file makes is not "the two answers differ" but "each
answer is tagged with *its own* snapshot's identity" — which is the actual claim US2 scenario 2
makes, and the one a bug that always resolved to whichever snapshot loads first would still fail.

**T645's own follow-up**: both promoted fixtures currently carry `civilisations_modelled = []`
(unchanged by this task, since T645 has not run). T645 must add `"Byzantines"` and `"Koreans"` to
**both** promoted fixtures' `snapshot.toml`, not only the pre-existing one, or the "two snapshots"
test below stays gapped for a reason this file does not intend to exercise. `"Franks"` is
deliberately *never* added to either — it is this file's unmodelled-civilisation case, and must
stay unmodelled for that case to mean anything.
"""

from __future__ import annotations

import pytest

from aoe2stats_knowledge import snapshot

#: Real unit id, "Pikeman" (`table_origin = "unit"`) — see this module's docstring for the
#: verification. Present in both Byzantines' and Franks' unit lists.
_PIKEMAN_ID = "358"

#: Real unit id, "Crossbowman" (`table_origin = "unit"`) — present in both Koreans' and
#: Byzantines' unit lists.
_CROSSBOWMAN_ID = "24"

#: The build both committed reference recordings report (`tests/fixtures/replays/README.md`),
#: which `aoe2techtree-fixture-promoted` describes by carry-forward (T642).
_CARRY_FORWARD_BUILD = 180059

#: The build `aoe2techtree-fixture-promoted-177723` (T646) describes directly, with no
#: carry-forward — the source revision's own last-implemented build.
_DIRECT_BUILD = 177723


def _one_build_higher_than_every_promoted_snapshot() -> int:
    """A build no committed, promoted snapshot describes — computed from whatever is actually
    committed rather than hard-coded, so a future fixture at a higher build cannot silently turn
    this into a build that *does* resolve."""
    resolvable = snapshot.load_resolvable_snapshots()
    assert resolvable, "no promoted snapshot is committed — this test proves nothing without one"
    return max(s.identity.describes_build for s in resolvable) + 1


# --------------------------------------------------------------------------- a discounted unit


@pytest.mark.xfail(
    strict=True,
    reason="T643 (query.cost/EntityRef), T644 (effects.py) and T645 (Byzantines modelled) "
    "not implemented yet",
)
def test_a_discounted_unit_returns_its_adjusted_cost_with_the_effect_and_its_source_sentence() -> (
    None
):
    """Byzantine Pikeman: -25% of `{food: 35, wood: 25}` is `{food: 26, wood: 19}` (see this
    module's docstring — neither value lands on a rounding boundary). The answer must carry the
    effect that produced the adjustment, and that effect must carry the verbatim sentence it was
    transcribed from (data-model.md §6, `source_text`)."""
    from aoe2stats_knowledge import effects, query

    entity = query.EntityRef(kind="unit", id=_PIKEMAN_ID, build=_CARRY_FORWARD_BUILD)

    answer = query.cost(entity, civilisation="Byzantines")

    assert hasattr(answer, "value"), "a discounted, modelled civilisation must answer, not gap"
    assert answer.value == {"food": 26, "wood": 19}
    assert answer.snapshot_identity.describes_build == _CARRY_FORWARD_BUILD
    assert answer.source == "unit"
    assert len(answer.effects) >= 1
    matching = [
        effect
        for effect in answer.effects
        if isinstance(effect, effects.Effect) and effect.civilisation == "Byzantines"
    ]
    assert matching, "no Byzantine effect was applied to the answer's own .effects"
    effect = matching[0]
    assert effect.field == "cost"
    assert effect.modelled == "yes"
    assert "Camel Riders, Skirmishers and Spearman-line cost -25%" in effect.source_text


@pytest.mark.xfail(
    strict=True,
    reason="T643 (query.cost/EntityRef), T644 (effects.py) and T645 (Koreans modelled) "
    "not implemented yet",
)
def test_a_second_discounted_unit_for_a_second_modelled_civilisation_is_also_correct() -> None:
    """Korean Crossbowman: -50% wood only, on `{gold: 45, wood: 25}` — `25 * 0.5 = 12.5`, a real
    rounding boundary this file resolves by stating round-half-up explicitly (see module
    docstring): `{gold: 45, wood: 13}`. A second, independent real fact from research.md D5 ("Korean
    archers and crossbowmen"), not a restatement of the Byzantine case above."""
    from aoe2stats_knowledge import effects, query

    entity = query.EntityRef(kind="unit", id=_CROSSBOWMAN_ID, build=_CARRY_FORWARD_BUILD)

    answer = query.cost(entity, civilisation="Koreans")

    assert hasattr(answer, "value")
    assert answer.value == {"gold": 45, "wood": 13}
    matching = [
        effect
        for effect in answer.effects
        if isinstance(effect, effects.Effect) and effect.civilisation == "Koreans"
    ]
    assert matching, "no Korean effect was applied to the answer's own .effects"
    effect = matching[0]
    assert effect.field == "cost"
    assert effect.modelled == "yes"
    assert "Ranged Soldiers and Infantry cost -50% wood" in effect.source_text


# ------------------------------------------------------------- an unmodelled civilisation gaps


def test_the_same_unit_for_an_unmodelled_civilisation_gaps_and_never_returns_the_baseline() -> None:
    """Franks has no bonus touching Pikeman's cost (module docstring), so Franks' *true* Pikeman
    cost genuinely is the baseline `{food: 35, wood: 25}` — and the conservative rule (research D5)
    must still refuse, because which fields an unmodelled civilisation's bonuses touch is exactly
    what is not known. This is the case the task text calls out by name: never the baseline, even
    when the baseline would coincidentally have been correct."""
    from aoe2stats_knowledge import query

    entity = query.EntityRef(kind="unit", id=_PIKEMAN_ID, build=_CARRY_FORWARD_BUILD)

    result = query.cost(entity, civilisation="Franks")

    assert not hasattr(result, "value"), (
        "an unmodelled civilisation must gap, never answer — even with a value equal to the "
        f"baseline: got {getattr(result, 'value', None)!r}"
    )
    assert result.cause == "civilisation-not-modelled"


# --------------------------------------------------------------------- a build with no snapshot


def test_a_build_one_higher_than_every_snapshot_describes_gaps() -> None:
    """`snapshot_for`'s existing gap path (T641), exercised through the query layer once `cost()`
    wraps it (contracts/knowledge-base.md, "Resolution by build"): exact match only, no nearest."""
    from aoe2stats_knowledge import query

    too_high = _one_build_higher_than_every_promoted_snapshot()
    entity = query.EntityRef(kind="unit", id=_PIKEMAN_ID, build=too_high)

    result = query.cost(entity, civilisation="Byzantines")

    assert not hasattr(result, "value")
    assert result.cause == "no-snapshot-for-build"


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
        query.cost(entity, "Byzantines")  # type: ignore[misc]  # civilisation passed positionally


# ------------------------------------------------------- two snapshots, two independent answers


@pytest.mark.xfail(
    strict=True,
    reason="T643 (query.cost/EntityRef), T644 (effects.py) and T645 (Byzantines modelled on both "
    "promoted fixtures) not implemented yet",
)
def test_two_snapshots_answer_from_their_own_contents_and_neither_is_upgraded_to_the_other() -> (
    None
):
    """US2 scenario 2, against the two real, committed promoted snapshots
    (`aoe2techtree-fixture-promoted`, build 180059; `aoe2techtree-fixture-promoted-177723`, build
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
        entity_at_carry_forward_build, civilisation="Byzantines"
    )
    answer_from_direct_snapshot = query.cost(entity_at_direct_build, civilisation="Byzantines")

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

    result = query.cost(entity, civilisation="Byzantines")

    assert not hasattr(result, "value"), f"an unknown entity id must gap, got {result!r}"
    assert result.cause == "entity-absent"


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
