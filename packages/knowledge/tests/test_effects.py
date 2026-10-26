"""T644: `effects.py` — structured civilisation effects (research.md D5, data-model.md §6).

Contract: [contracts/knowledge-base.md](../../../specs/006-replay-analysis-foundations/contracts/
knowledge-base.md), "Civilisation qualification" steps 2-3. Research:
[research.md](../../../specs/006-replay-analysis-foundations/research.md) **D5**.

Two kinds of test live here, deliberately kept apart:

- **Pure logic**, against synthetic `Effect`/TOML text with no packaged-file I/O at all: parsing
  `effects.toml`, the closed operation set, the `modelled = "no"` shell (a reason required, an
  operation/operand forbidden), matching an effect to an entity/field/civilisation, applying an
  operation (including round-half-up on a fractional resource amount), and the "never
  half-applied" invariant when a modelled and an unmodelled effect both match the same query.
- **Integration**, against the two real, committed snapshots' real, hand-transcribed
  `effects.toml` (`aoe2techtree-180059`, `aoe2techtree-177723-test`): the
  same two real facts `packages/knowledge/tests/test_query.py` encodes (Saracens' Market -100
  wood, Malians' Dock -15% wood — T652m; Byzantines' Pikeman -25% and Koreans' Crossbowman -50%
  wood before Byzantines and Koreans were found to be in neither committed recording at all),
  proven here directly through `effects.apply` rather than through `query.py` — this is
  deliberate: `query.py`'s own discount tests stayed `xfail` until T645 populated
  `civilisations_modelled`, but `effects.py`'s own correctness never depended on T645 at all, and
  this file is what proves that independently.

**T645** added the four civilisations the second committed recording needs (research.md D11) —
Franks, Persians, Teutons and, at the time, Gurjaras — with the same two-kind treatment: a real
cost/age-requirement adjustment proven against the committed `effects.toml`, and one
conditional/team-wide "not modelled" refusal each. **T652m** (2026-09-23) found Gurjaras was never
in either committed recording, along with Byzantines and Koreans, and replaced all three with the
recordings' real civilisations — Saracens, Malians (recording 1) and Tatars (recording 2, the
fourth of Franks/Persians/Teutons/Tatars). `packages/knowledge/snapshots/aoe2techtree-180059/
effects.toml`'s own header comment carries the full identification method and provenance; this
file does not restate it.
"""

from __future__ import annotations

import pytest

from aoe2stats_knowledge import effects, query
from aoe2stats_knowledge.gaps import KnowledgeGap

# --------------------------------------------------------------------------------- parsing

_MINIMAL_MODELLED_EFFECT = """\
[[effect]]
civilisation = "Byzantines"
source_key = "120156"
source_text = "Camel Riders, Skirmishers and Spearman-line cost -25%"
modelled = "yes"
field = "cost"
operation = "multiply"
operand = { food = 0.75, wood = 0.75 }
selector = [{ kind = "unit", id = "358" }]
validated_by = "re-read on 2026-09-20"
"""

_MINIMAL_NOT_MODELLED_EFFECT = """\
[[effect]]
civilisation = "Byzantines"
source_key = "120156"
source_text = "Buildings +10/20/30/40% HP in Dark/Feudal/Castle/Imperial Age"
modelled = "no"
reason = "age-gated: the recording cannot place which age applies"
field = "hp"
selector = [{ kind = "building", id = "12" }]
validated_by = "re-read on 2026-09-20"
"""


def test_parse_effects_toml_reads_a_modelled_effect() -> None:
    (effect,) = effects.parse_effects_toml(_MINIMAL_MODELLED_EFFECT)
    assert effect.civilisation == "Byzantines"
    assert effect.source_key == "120156"
    assert "Spearman-line" in effect.source_text
    assert effect.modelled == "yes"
    assert effect.field == "cost"
    assert effect.operation == "multiply"
    assert effect.operand == {"food": 0.75, "wood": 0.75}
    assert effect.selector == (effects.SelectorEntry(kind="unit", id="358"),)
    assert effect.reason is None


def test_parse_effects_toml_reads_a_not_modelled_effect_with_its_reason() -> None:
    (effect,) = effects.parse_effects_toml(_MINIMAL_NOT_MODELLED_EFFECT)
    assert effect.modelled == "no"
    assert effect.reason == "age-gated: the recording cannot place which age applies"
    assert effect.operation is None
    assert effect.operand is None


def test_parse_effects_toml_preserves_file_order() -> None:
    text = _MINIMAL_MODELLED_EFFECT + "\n" + _MINIMAL_NOT_MODELLED_EFFECT
    parsed = effects.parse_effects_toml(text)
    assert [effect.field for effect in parsed] == ["cost", "hp"]


def test_parse_effects_toml_of_no_effects_is_the_empty_tuple() -> None:
    assert effects.parse_effects_toml("# no effects yet\n") == ()


@pytest.mark.parametrize(
    "field_to_drop",
    ["civilisation", "source_key", "source_text", "field", "selector", "validated_by"],
)
def test_parse_effects_toml_rejects_a_missing_required_field(field_to_drop: str) -> None:
    lines = [
        line for line in _MINIMAL_MODELLED_EFFECT.splitlines() if not line.startswith(field_to_drop)
    ]
    with pytest.raises(effects.EffectsError):
        effects.parse_effects_toml("\n".join(lines) + "\n")


def test_parse_effects_toml_rejects_an_empty_selector() -> None:
    text = _MINIMAL_MODELLED_EFFECT.replace(
        'selector = [{ kind = "unit", id = "358" }]', "selector = []"
    )
    with pytest.raises(effects.EffectsError):
        effects.parse_effects_toml(text)


def test_parse_effects_toml_rejects_an_unclosed_operation() -> None:
    text = _MINIMAL_MODELLED_EFFECT.replace('operation = "multiply"', 'operation = "halve"')
    with pytest.raises(effects.EffectsError):
        effects.parse_effects_toml(text)


def test_parse_effects_toml_rejects_modelled_value_outside_the_closed_pair() -> None:
    text = _MINIMAL_MODELLED_EFFECT.replace('modelled = "yes"', 'modelled = "partially"')
    with pytest.raises(effects.EffectsError):
        effects.parse_effects_toml(text)


def test_parse_effects_toml_rejects_a_not_modelled_effect_missing_its_reason() -> None:
    lines = [
        line for line in _MINIMAL_NOT_MODELLED_EFFECT.splitlines() if not line.startswith("reason")
    ]
    with pytest.raises(effects.EffectsError):
        effects.parse_effects_toml("\n".join(lines) + "\n")


def test_parse_effects_toml_rejects_a_not_modelled_effect_carrying_an_operation() -> None:
    """research.md D5: "a bonus is never half-applied" — enforced at parse time, not only when
    applying: a `modelled = "no"` effect that also carries an `operation` is malformed data, not a
    valid effect this package merely chooses not to apply."""
    text = _MINIMAL_NOT_MODELLED_EFFECT + 'operation = "multiply"\noperand = { food = 0.5 }\n'
    with pytest.raises(effects.EffectsError):
        effects.parse_effects_toml(text)


def test_parse_effects_toml_rejects_a_modelled_yes_effect_missing_its_operand() -> None:
    lines = [
        line for line in _MINIMAL_MODELLED_EFFECT.splitlines() if not line.startswith("operand")
    ]
    with pytest.raises(effects.EffectsError):
        effects.parse_effects_toml("\n".join(lines) + "\n")


def test_parse_effects_toml_rejects_malformed_toml() -> None:
    with pytest.raises(effects.EffectsError):
        effects.parse_effects_toml("this is not [ valid toml")


# ----------------------------------------------------------------- T652r: numeric parse guards

_MINIMAL_FASTER_EFFECT = """\
[[effect]]
civilisation = "Franks"
source_key = "998"
source_text = "synthetic: a 'works X% faster' bonus, T652r"
modelled = "yes"
field = "production_time"
operation = "faster"
operand = 0.40
selector = [{ kind = "unit", id = "1" }]
validated_by = "synthetic fixture, T652r"
"""


def test_faster_is_its_own_operation_distinct_from_multiply() -> None:
    """T652r: "works X% faster" no longer overloads `multiply` — `multiply` means a literal
    factor on every field it touches, and a time bonus's own divide-by-(1+X) semantics get their
    own name, `faster`."""
    (effect,) = effects.parse_effects_toml(_MINIMAL_FASTER_EFFECT)
    assert effect.operation == "faster"
    assert "faster" in effects.OPERATIONS


@pytest.mark.parametrize("operand", [-1, -1.0, -2, -1.5])
def test_parse_effects_toml_rejects_a_faster_operand_at_or_below_negative_one(
    operand: float,
) -> None:
    """T652r: a 'faster' operand divides the baseline by `1 + operand` — `operand = -1` divides
    by zero, and anything below that produces a negative time. Both are values the game cannot
    produce, so parsing must refuse rather than let `apply` raise or silently invert a time
    later."""
    text = _MINIMAL_FASTER_EFFECT.replace("operand = 0.40", f"operand = {operand}")
    with pytest.raises(effects.EffectsError):
        effects.parse_effects_toml(text)


def test_parse_effects_toml_accepts_a_faster_operand_above_negative_one() -> None:
    """The contrast case the guard above needs: an operand just above the forbidden boundary
    (never reached by a committed effect, but a legitimate value in principle) must still parse."""
    text = _MINIMAL_FASTER_EFFECT.replace("operand = 0.40", "operand = -0.99")
    (effect,) = effects.parse_effects_toml(text)
    assert effect.operand == -0.99


def test_parse_effects_toml_rejects_a_faster_operand_below_negative_one_in_an_age_table() -> None:
    """The same guard, reached through a `condition = "age"` operand table (Persians' Town
    Center/Dock row's own shape) instead of a bare number — the parse-time walk must not stop at
    the table's outer level."""
    text = (
        _MINIMAL_FASTER_EFFECT.replace("operand = 0.40", 'operand = { "1" = -1.0 }')
        + 'condition = "age"\n'
    )
    with pytest.raises(effects.EffectsError):
        effects.parse_effects_toml(text)


@pytest.mark.parametrize("operand", [-0.1, -1])
def test_parse_effects_toml_rejects_a_negative_cost_multiply_operand(operand: float) -> None:
    """T652r: a negative `multiply` operand on a cost flips its sign — the game never prices
    anything negatively, so parsing must refuse rather than let a query silently answer a
    negative cost."""
    text = _MINIMAL_MODELLED_EFFECT.replace(
        "operand = { food = 0.75, wood = 0.75 }", f"operand = {{ wood = {operand} }}"
    )
    with pytest.raises(effects.EffectsError):
        effects.parse_effects_toml(text)


def test_parse_effects_toml_rejects_a_negative_cost_multiply_operand_in_an_age_table() -> None:
    """The same guard, reached through a `condition = "age"` operand table (Franks' Castle
    discount's own shape: an age table of per-resource mappings) instead of a bare resource
    mapping — the parse-time walk must reach every nesting level."""
    text = (
        _MINIMAL_MODELLED_EFFECT.replace(
            "operand = { food = 0.75, wood = 0.75 }", 'operand = { "3" = { stone = -0.15 } }'
        )
        + 'condition = "age"\n'
    )
    with pytest.raises(effects.EffectsError):
        effects.parse_effects_toml(text)


_MINIMAL_COST_SET_EFFECT = """\
[[effect]]
civilisation = "Franks"
source_key = "998"
source_text = "synthetic: a 'set' cost effect, T652r"
modelled = "yes"
field = "cost"
operation = "set"
operand = { wood = 0 }
selector = [{ kind = "building", id = "1" }]
validated_by = "synthetic fixture, T652r"
"""


def test_parse_effects_toml_rejects_a_non_whole_cost_set_operand() -> None:
    """T652r: `_apply_scalar`'s `set` branch truncates a fractional operand with `int()` for
    `age_requirement`, and `_apply_mapping`'s does the same for `cost` — a transcription that
    puts a fractional amount into a 'set' cost is a defect the game cannot represent, and must be
    refused at parse time rather than silently truncated later."""
    text = _MINIMAL_COST_SET_EFFECT.replace("operand = { wood = 0 }", "operand = { wood = 12.5 }")
    with pytest.raises(effects.EffectsError):
        effects.parse_effects_toml(text)


def test_parse_effects_toml_accepts_a_whole_cost_set_operand() -> None:
    (effect,) = effects.parse_effects_toml(_MINIMAL_COST_SET_EFFECT)
    assert effect.operand == {"wood": 0}


_MINIMAL_AGE_REQUIREMENT_SET_EFFECT = """\
[[effect]]
civilisation = "Franks"
source_key = "998"
source_text = "synthetic: a 'set' age_requirement effect, T652r"
modelled = "yes"
field = "age_requirement"
operation = "set"
operand = 3
selector = [{ kind = "technology", id = "1" }]
validated_by = "synthetic fixture, T652r"
"""


def test_parse_effects_toml_rejects_a_non_whole_age_requirement_set_operand() -> None:
    text = _MINIMAL_AGE_REQUIREMENT_SET_EFFECT.replace("operand = 3", "operand = 3.5")
    with pytest.raises(effects.EffectsError):
        effects.parse_effects_toml(text)


def test_parse_effects_toml_accepts_a_whole_age_requirement_set_operand() -> None:
    (effect,) = effects.parse_effects_toml(_MINIMAL_AGE_REQUIREMENT_SET_EFFECT)
    assert effect.operand == 3


def test_parse_effects_toml_rejects_a_faster_operation_on_a_field_other_than_production_time() -> (
    None
):
    """T652z: `"faster"` carries "works X% faster"'s divide-by-(1+X) semantics, which only make
    sense for a time — applying it to a `"cost"` used to parse and only fail later, at the first
    query, with `_apply_mapping`'s own "unreachable" `AssertionError` (there is no mapping-shaped
    `faster` branch at all). Rejected at parse time instead, like every other operand/field
    mismatch this module already refuses."""
    text = _MINIMAL_FASTER_EFFECT.replace('field = "production_time"', 'field = "cost"')
    with pytest.raises(effects.EffectsError):
        effects.parse_effects_toml(text)


# --------------------------------------------------------------------------------- matching


def test_effects_for_matches_civilisation_field_and_selector_together() -> None:
    text = _MINIMAL_MODELLED_EFFECT
    parsed = effects.parse_effects_toml(text)
    matches = [
        effect
        for effect in parsed
        if effect.civilisation == "Byzantines"
        and effect.field == "cost"
        and any(entry.kind == "unit" and entry.id == "358" for entry in effect.selector)
    ]
    assert matches == list(parsed)


def test_an_effect_for_a_different_civilisation_does_not_match() -> None:
    (effect,) = effects.parse_effects_toml(_MINIMAL_MODELLED_EFFECT)
    assert effect.civilisation != "Koreans"


def test_an_effect_for_a_different_entity_id_does_not_match() -> None:
    (effect,) = effects.parse_effects_toml(_MINIMAL_MODELLED_EFFECT)
    assert not any(entry.id == "999" for entry in effect.selector)


# ------------------------------------------------------------------------ pure application


def test_apply_matched_with_no_matches_returns_the_baseline_value_and_no_effects() -> None:
    value, applied = effects.apply_matched(
        (),
        civilisation="Franks",
        kind="unit",
        id="358",
        field="cost",
        value={"food": 35, "wood": 25},
    )
    assert value == {"food": 35, "wood": 25}
    assert applied == ()


def test_apply_matched_applies_a_multiply_operation_on_a_cost_with_round_half_up() -> None:
    (effect,) = effects.parse_effects_toml(_MINIMAL_MODELLED_EFFECT)
    value, applied = effects.apply_matched(
        (effect,),
        civilisation="Byzantines",
        kind="unit",
        id="358",
        field="cost",
        value={"food": 35, "wood": 25},
    )
    # 35 * 0.75 = 26.25 -> 26; 25 * 0.75 = 18.75 -> 19 (round half up, never banker's rounding).
    assert value == {"food": 26, "wood": 19}
    assert applied == (effect,)


def test_apply_matched_applies_a_faster_operation_on_a_time() -> None:
    """T652r: `faster` divides the baseline by `1 + operand`, distinct from `multiply` — a
    synthetic, file-free counterpart to the real Chivalry/Town Center/University rows below,
    proving the mechanism directly against `apply_matched`."""
    (effect,) = effects.parse_effects_toml(_MINIMAL_FASTER_EFFECT)
    value, applied = effects.apply_matched(
        (effect,),
        civilisation="Franks",
        kind="unit",
        id="1",
        field="production_time",
        value=25,
    )
    assert value == pytest.approx(25 / 1.40)
    assert applied == (effect,)


def test_apply_matched_applies_a_multiply_operation_on_a_time_without_rounding() -> None:
    """T652z, data-model.md §6's rounding row: a time keeps its fraction whatever the operation —
    `multiply` must not round it the way a cost's `multiply` does. The contrast case is
    `test_apply_matched_applies_a_multiply_operation_on_a_cost_with_round_half_up` above, which
    still rounds a cost half up; this is the same operation on the other kind of field."""
    text = _MINIMAL_FASTER_EFFECT.replace('operation = "faster"', 'operation = "multiply"').replace(
        "operand = 0.40", "operand = 0.9"
    )
    (effect,) = effects.parse_effects_toml(text)
    value, applied = effects.apply_matched(
        (effect,),
        civilisation="Franks",
        kind="unit",
        id="1",
        field="production_time",
        value=25,
    )
    # 25 * 0.9 = 22.5 exactly — round-half-up would answer 23, which is not the game's own value.
    assert value == 22.5
    assert applied == (effect,)


def test_apply_matched_applies_an_add_operation_on_a_time_without_rounding() -> None:
    """T652z: the `add` counterpart of the `multiply` test above — a time keeps its fraction on
    this path too."""
    text = _MINIMAL_FASTER_EFFECT.replace('operation = "faster"', 'operation = "add"').replace(
        "operand = 0.40", "operand = 0.4"
    )
    (effect,) = effects.parse_effects_toml(text)
    value, applied = effects.apply_matched(
        (effect,),
        civilisation="Franks",
        kind="unit",
        id="1",
        field="production_time",
        value=25,
    )
    assert value == 25.4
    assert applied == (effect,)


def test_apply_matched_only_touches_resources_the_operand_names() -> None:
    """A per-resource operand — Koreans' wood-only discount — must leave every other resource of
    the same cost untouched, even when it lands on a rounding boundary that could tempt a
    round-everything implementation."""
    text = _MINIMAL_MODELLED_EFFECT.replace(
        "operand = { food = 0.75, wood = 0.75 }", "operand = { wood = 0.5 }"
    )
    (effect,) = effects.parse_effects_toml(text)
    value, _applied = effects.apply_matched(
        (effect,),
        civilisation="Byzantines",
        kind="unit",
        id="358",
        field="cost",
        value={"gold": 45, "wood": 25},
    )
    assert value == {"gold": 45, "wood": 13}


def test_apply_matched_ignores_an_operand_resource_the_entity_does_not_have() -> None:
    text = _MINIMAL_MODELLED_EFFECT.replace(
        "operand = { food = 0.75, wood = 0.75 }", "operand = { food = 0.75, gold = 0.75 }"
    )
    (effect,) = effects.parse_effects_toml(text)
    value, _applied = effects.apply_matched(
        (effect,),
        civilisation="Byzantines",
        kind="unit",
        id="358",
        field="cost",
        value={"food": 35, "wood": 25},
    )
    assert value == {"food": 26, "wood": 25}


def test_apply_matched_applies_matching_effects_in_file_order() -> None:
    first = effects.Effect(
        civilisation="Byzantines",
        source_key="1",
        source_text="first",
        modelled="yes",
        selector=(effects.SelectorEntry(kind="unit", id="1"),),
        field="cost",
        validated_by="x",
        operation="multiply",
        operand={"food": 0.5},
    )
    second = effects.Effect(
        civilisation="Byzantines",
        source_key="2",
        source_text="second",
        modelled="yes",
        selector=(effects.SelectorEntry(kind="unit", id="1"),),
        field="cost",
        validated_by="x",
        operation="add",
        operand={"food": 10},
    )
    value, applied = effects.apply_matched(
        (first, second),
        civilisation="Byzantines",
        kind="unit",
        id="1",
        field="cost",
        value={"food": 100},
    )
    # (100 * 0.5) + 10 = 60, only correct if `first` is applied before `second`.
    assert value == {"food": 60}
    assert applied == (first, second)


def test_apply_matched_a_not_modelled_effect_refuses_with_its_reason() -> None:
    (effect,) = effects.parse_effects_toml(_MINIMAL_NOT_MODELLED_EFFECT)
    result = effects.apply_matched(
        (effect,), civilisation="Byzantines", kind="building", id="12", field="hp", value=None
    )
    assert isinstance(result, effects.EffectNotModelled)
    assert result.cause == "effect-not-modelled"
    assert result.reason == effect.reason


def test_apply_matched_never_half_applies_a_bonus() -> None:
    """research.md D5: "a bonus is never half-applied". A modelled effect and an unmodelled effect
    both matching the same civilisation/entity/field must refuse entirely — the modelled match must
    **not** be applied just because it happens to be present alongside the refusal."""
    (modelled,) = effects.parse_effects_toml(_MINIMAL_MODELLED_EFFECT)
    not_modelled_text = _MINIMAL_NOT_MODELLED_EFFECT.replace(
        'field = "hp"', 'field = "cost"'
    ).replace(
        'selector = [{ kind = "building", id = "12" }]',
        'selector = [{ kind = "unit", id = "358" }]',
    )
    (not_modelled,) = effects.parse_effects_toml(not_modelled_text)

    result = effects.apply_matched(
        (modelled, not_modelled),
        civilisation="Byzantines",
        kind="unit",
        id="358",
        field="cost",
        value={"food": 35, "wood": 25},
    )

    assert isinstance(result, effects.EffectNotModelled)
    assert not hasattr(result, "value")


# ---------------------------------------------------------------- integration: real snapshots

_PROMOTED_DIRECTORY = "aoe2techtree-180059"
_PROMOTED_177723_DIRECTORY = "aoe2techtree-177723-test"


@pytest.mark.parametrize("directory", [_PROMOTED_DIRECTORY, _PROMOTED_177723_DIRECTORY])
def test_the_real_saracens_market_discount_applies_through_the_committed_effects_toml(
    directory: str,
) -> None:
    """The exact real fact `test_query.py` encodes, proven here directly against `effects.py`
    without going through `query.py`/`civilisations_modelled` at all (T645 is not a dependency of
    this test) — over **both** committed promoted snapshots, since both carry the same real,
    hand-transcribed `effects.toml` content (their sibling `snapshot.toml` files record why: the
    same pack revision, unchanged across every build between them). Saracens replaces the
    previously committed, wrong Byzantines (T652m: Byzantines is in neither committed recording)."""
    result = effects.apply(
        directory,
        civilisation="Saracens",
        kind="building",
        id="84",
        field="cost",
        value={"wood": 175},
    )
    assert not isinstance(result, effects.EffectNotModelled)
    value, applied = result
    assert value == {"wood": 75}
    assert len(applied) == 1
    assert applied[0].source_text == "Market trading fee only 5%; Markets cost -100 wood"
    assert applied[0].modelled == "yes"


@pytest.mark.parametrize("directory", [_PROMOTED_DIRECTORY, _PROMOTED_177723_DIRECTORY])
def test_the_real_malians_dock_discount_applies_through_the_committed_effects_toml(
    directory: str,
) -> None:
    """Malians replaces the previously committed, wrong Koreans (T652m: Koreans is in neither
    committed recording). `150 * 0.85 = 127.5`, a real rounding boundary resolved by round-half-up
    to 128."""
    result = effects.apply(
        directory,
        civilisation="Malians",
        kind="building",
        id="45",
        field="cost",
        value={"wood": 150},
    )
    assert not isinstance(result, effects.EffectNotModelled)
    value, applied = result
    assert value == {"wood": 128}
    assert len(applied) == 1
    assert applied[0].source_text == "Buildings cost -15% wood"


@pytest.mark.parametrize("directory", [_PROMOTED_DIRECTORY, _PROMOTED_177723_DIRECTORY])
def test_the_real_malians_bombard_tower_cost_is_never_discounted(directory: str) -> None:
    """T652p (e): the Malians "Buildings cost -15% wood" selector wrongly included building 236
    (Bombard Tower) — Malians' own tree file (`MALIANS.json`) marks it `node_status:
    "NotAvailable"`, the only such entry among the 28 buildings the selector originally named, so
    this civilisation cannot construct a Bombard Tower at all and discounting a cost it can never
    pay was wrong. Removed from the selector in both promoted `effects.toml` files; this proves
    the discount no longer applies, and querying still answers the plain, undiscounted baseline
    cost (`rules.json`'s own entry for building 236) with no effect touching it."""
    result = effects.apply(
        directory,
        civilisation="Malians",
        kind="building",
        id="236",
        field="cost",
        value={"gold": 100, "stone": 125, "wood": 0},
    )
    assert not isinstance(result, effects.EffectNotModelled)
    value, applied = result
    assert value == {"gold": 100, "stone": 125, "wood": 0}
    assert applied == (), "no Malians effect should touch a building this civilisation cannot build"


def test_the_real_malians_barracks_pierce_armor_bonus_is_not_modelled() -> None:
    """The age-gated bonus this task's "not modelled" rule requires be recorded rather than
    silently dropped (research.md D5) — proven here against the real, committed `effects.toml`.
    Malians replaces the previously committed, wrong Byzantines (T652m)."""
    result = effects.apply(
        _PROMOTED_DIRECTORY,
        civilisation="Malians",
        kind="building",
        id="12",
        field="pierce_armor",
        value=None,
    )
    assert isinstance(result, effects.EffectNotModelled)
    assert "age" in result.reason.lower()


def test_the_real_britons_pikeman_query_matches_no_effect_at_all() -> None:
    """Britons is deliberately never modelled in either committed `effects.toml` (see
    `test_query.py`'s module docstring — Franks held this role until T645 found it genuinely
    trained in the second committed recording and moved the role to Britons instead) — at the
    `effects.py` layer alone, with no `civilisations_modelled` gate involved, a Britons query for
    Pikeman's cost simply matches nothing and returns the baseline unmodified. The refusal for an
    unmodelled *civilisation* is `query.py`'s job (research.md D5's conservative rule), not this
    module's — this test pins down that `effects.py` itself has no knowledge of Britons to
    accidentally leak a discount from."""
    result = effects.apply(
        _PROMOTED_DIRECTORY,
        civilisation="Britons",
        kind="unit",
        id="358",
        field="cost",
        value={"food": 35, "wood": 25},
    )
    assert not isinstance(result, effects.EffectNotModelled)
    value, applied = result
    assert value == {"food": 35, "wood": 25}
    assert applied == ()


# --------------------------------------------------- T645: the second recording's civilisations


@pytest.mark.parametrize("directory", [_PROMOTED_DIRECTORY, _PROMOTED_177723_DIRECTORY])
def test_the_real_franks_mill_technology_discount_applies_through_the_committed_effects_toml(
    directory: str,
) -> None:
    """Franks: "Mill technologies free" — Crop Rotation's real cost, `{food: 250, wood: 250}`, made
    free by the civilisation bonus, not by a coincidental baseline of zero."""
    result = effects.apply(
        directory,
        civilisation="Franks",
        kind="technology",
        id="12",
        field="cost",
        value={"food": 250, "wood": 250},
    )
    assert not isinstance(result, effects.EffectNotModelled)
    value, applied = result
    assert value == {"food": 0, "wood": 0}
    assert len(applied) == 1
    assert applied[0].source_text == "Mill technologies free"
    assert applied[0].modelled == "yes"


# ------------------------------------- T652o: "free" grants a technology, never merely prices it


@pytest.mark.parametrize(
    ("civilisation", "technology_id", "baseline_time"),
    [
        ("Franks", "12", 70),  # Crop Rotation, "Mill technologies free"
        ("Teutons", "322", 35),  # Murder Holes, "Murder Holes, Herbal Medicine free"
        ("Tatars", "437", 45),  # Thumb Ring, "Thumb Ring, Parthian Tactics free"
    ],
)
def test_a_free_technology_also_drives_production_time_to_zero(
    civilisation: str, technology_id: str, baseline_time: int
) -> None:
    """T652o (mid-task correction, repository owner): a technology a civilisation bonus makes
    "free" is granted automatically on reaching its own baseline age_requirement, never manually
    researched — so the cost being zero is only half the bonus; the player also spends no
    research time at all. Cost-only was itself the FR-038 half-applied substitution research.md D5
    forbids, the same shape the third review found in Malians' University bonus.

    T652u remediation: technology 322 (Murder Holes, Teutons' own case here) is also one of
    Malians' University Team Bonus's selector entries, so this query now needs `context.team` at
    all (defect 1) — a solo team (`{civilisation}`, no Malians ally) is what "does this civilisation
    have an ally" means when the test itself does not claim one, and is enough to let Malians'
    effect structurally match without ever applying (Malians is not in the solo team)."""
    result = effects.apply(
        _PROMOTED_DIRECTORY,
        civilisation=civilisation,
        kind="technology",
        id=technology_id,
        field="production_time",
        value=baseline_time,
        context=effects.Context(team=frozenset({civilisation})),
    )
    assert not isinstance(result, effects.EffectNotModelled)
    value, applied = result
    assert value == 0
    assert len(applied) == 1
    assert applied[0].modelled == "yes"
    assert applied[0].field == "production_time"


@pytest.mark.parametrize(
    ("civilisation", "technology_id", "baseline_time"),
    [
        ("Teutons", "12", 70),  # Crop Rotation is Franks-only, not Teutons'
        ("Persians", "437", 45),  # Thumb Ring is Tatars-only, not Persians'
        ("Franks", "322", 35),  # Murder Holes is Teutons-only, not Franks'
    ],
)
def test_a_free_technology_grant_does_not_leak_to_a_different_civilisation(
    civilisation: str, technology_id: str, baseline_time: int
) -> None:
    """The mirror of the parametrized test above: a civilisation this file does not grant the
    technology to free must still answer the real, un-adjusted baseline research time — proving
    the new `production_time = 0` effects are matched by civilisation, not merely by technology
    id. Solo `context.team` for the same T652u reason as above (technology 322, Franks' own case
    here, is also in Malians' University selector)."""
    result = effects.apply(
        _PROMOTED_DIRECTORY,
        civilisation=civilisation,
        kind="technology",
        id=technology_id,
        field="production_time",
        value=baseline_time,
        context=effects.Context(team=frozenset({civilisation})),
    )
    assert not isinstance(result, effects.EffectNotModelled)
    value, applied = result
    assert value == baseline_time
    assert applied == ()


#: T652u (2026-09-28, repository owner's arbitration of the fourth review): "Villager time is
#: equal to standard villager time * bonus multiplier" — a conditional bonus is a rule, and is
#: modelled. The four tests below replace the pre-T652u "is not modelled" tests for the same four
#: rows (Malians' University Team Bonus, Franks' Chivalry, Persians' Town Center/Dock work speed):
#: each is now `modelled = "yes"` with a `condition`, so the real assertion is the adjusted value
#: under the right `effects.Context`, the contrast case where the condition does not hold (the
#: baseline stands, unadjusted — not a gap), and that reaching the effect with no `Context` at all
#: still raises `effects.ContextRequired`, exactly as omitting `civilisation` would.


@pytest.mark.parametrize(
    ("age", "expected"),
    [
        (1, 25 / 1.05),  # Dark Age: +5% faster
        (2, 25 / 1.10),  # Feudal Age: +10% faster
        (3, 25 / 1.15),  # Castle Age: +15% faster
        (4, 25 / 1.20),  # Imperial Age: +20% faster
    ],
)
def test_the_real_persians_town_center_work_speed_bonus_applies_by_age(
    age: int, expected: float
) -> None:
    """T652u: "Town Centers and Docks ... work +5/10/15/20% faster in Dark/Feudal/Castle/Imperial
    Age" is `condition = "age"` now, not a categorical refusal — the Villager (unit 83), trained at
    the Town Center, is the real target the row's selector points at (T652q). Every age carries a
    discount here (unlike Franks' Castle below), so all four ages produce a real, adjusted, still-
    fractional value — "a time keeps its fraction" (data-model.md §6's amended rounding row)."""
    result = effects.apply(
        _PROMOTED_DIRECTORY,
        civilisation="Persians",
        kind="unit",
        id="83",
        field="production_time",
        value=25,
        context=effects.Context(age=age),
    )
    assert not isinstance(result, effects.EffectNotModelled)
    value, applied = result
    assert value == pytest.approx(expected)
    assert len(applied) == 1
    assert applied[0].source_text.startswith("Town Centers and Docks")


def test_the_real_teutons_villager_production_time_is_the_baseline_control() -> None:
    """The control half of the fix above: Teutons carries no Town-Center/Dock work-speed bonus at
    all, so the same query — same unit, same field, every age — must answer the plain, unadjusted
    baseline of 25 rather than refuse or divide, proving the Persians adjustment above is this
    civilisation's own effect and not `effects.apply` adjusting every civilisation regardless of
    selector. `age` is deliberately ignored here — the contrast case: something the bonus must not
    touch — because Teutons carries no age-conditioned effect on this entity/field at all."""
    for age in (1, 2, 3, 4):
        result = effects.apply(
            _PROMOTED_DIRECTORY,
            civilisation="Teutons",
            kind="unit",
            id="83",
            field="production_time",
            value=25,
            context=effects.Context(age=age),
        )
        assert not isinstance(result, effects.EffectNotModelled)
        value, applied = result
        assert value == 25, f"age {age}: Teutons' Villager must stay the plain baseline"
        assert applied == ()


def test_the_real_persians_town_center_work_speed_bonus_raises_with_no_context() -> None:
    """T652u: reaching a modelled conditional effect without the input that decides it raises —
    the same query as the parametrized test above, with no `context` at all."""
    with pytest.raises(effects.ContextRequired):
        effects.apply(
            _PROMOTED_DIRECTORY,
            civilisation="Persians",
            kind="unit",
            id="83",
            field="production_time",
            value=25,
        )


def test_an_unconditional_effect_with_no_context_does_not_raise() -> None:
    """The contrast case T652u's own contract text asks for directly: "a query whose matching
    effects are unconditional ignores it" — Teutons' Farm discount (`operation = "multiply"`,
    `condition` absent) carries no condition at all, so calling `effects.apply` with no `context`
    must not raise, unlike the conditional query above."""
    result = effects.apply(
        _PROMOTED_DIRECTORY,
        civilisation="Teutons",
        kind="building",
        id="50",
        field="cost",
        value={"wood": 60},
    )
    assert not isinstance(result, effects.EffectNotModelled)
    value, applied = result
    assert value == {"wood": 36}
    assert applied


@pytest.mark.parametrize(
    ("researched", "expected_divisor"),
    [
        (frozenset(), 1.0),  # Chivalry not yet researched: the baseline stands, unadjusted
        (frozenset({"493"}), 1.40),  # Chivalry (technology 493) researched: 40% faster
    ],
)
def test_the_real_franks_chivalry_bonus_before_and_after_research(
    researched: frozenset[str], expected_divisor: float
) -> None:
    """T652u: "Chivalry (Stables work +40% faster)" is `condition = "researched"` now,
    `condition_technology = "493"` — before Chivalry is researched, the baseline (30) stands,
    unadjusted (not a gap: a conditional effect that is modelled is complete knowledge); after, the
    Knight (unit 38)'s training time divides by 1.40."""
    result = effects.apply(
        _PROMOTED_DIRECTORY,
        civilisation="Franks",
        kind="unit",
        id="38",
        field="production_time",
        value=30,
        context=effects.Context(researched=researched),
    )
    assert not isinstance(result, effects.EffectNotModelled)
    value, applied = result
    assert value == pytest.approx(30 / expected_divisor)
    assert len(applied) == (1 if researched else 0)


def test_the_real_franks_chivalry_bonus_raises_with_no_context() -> None:
    """The same "no context raises" shape as Persians' age-conditioned row above, for a
    `condition = "researched"` effect instead."""
    with pytest.raises(effects.ContextRequired):
        effects.apply(
            _PROMOTED_DIRECTORY,
            civilisation="Franks",
            kind="unit",
            id="38",
            field="production_time",
            value=30,
        )


@pytest.mark.parametrize(
    ("civilisation", "team", "expected_divisor"),
    [
        ("Malians", frozenset({"Malians"}), 1.80),  # the owner's own query
        ("Franks", frozenset({"Malians", "Franks"}), 1.80),  # a Malians ally
        ("Teutons", frozenset({"Teutons"}), 1.0),  # an opponent: the baseline stands
    ],
)
def test_the_real_malians_university_team_bonus_applies_by_team(
    civilisation: str, team: frozenset[str], expected_divisor: float
) -> None:
    """T652u: "Universities work +80% faster" is `condition = "team"` now, `Malians` the effect's
    own owner — it matches every civilisation on the owner's team (contracts/knowledge-base.md,
    "Civilisation qualification" step 3), the owner included, and never an opponent's own
    University research (the contrast case: something the bonus must not touch)."""
    result = effects.apply(
        _PROMOTED_DIRECTORY,
        civilisation=civilisation,
        kind="technology",
        id="47",
        field="production_time",
        value=100,
        context=effects.Context(team=team),
    )
    assert not isinstance(result, effects.EffectNotModelled)
    value, applied = result
    assert value == pytest.approx(100 / expected_divisor)
    assert len(applied) == (1 if expected_divisor != 1.0 else 0)


@pytest.mark.parametrize("civilisation", ["Malians", "Franks", "Teutons"])
def test_the_real_malians_university_team_bonus_raises_for_any_civilisation_with_no_context(
    civilisation: str,
) -> None:
    """T652u remediation (two defects the coordinator measured against the working tree):
    **defect 1** — "a team effect must raise for every civilisation when no team is given, not
    only for its owner." Masonry (technology 50) is one of Malians' University Team Bonus's own
    selector entries; its `production_time`, for *any* civilisation, genuinely depends on whether
    that civilisation has a Malians ally (a team-composition fact only the caller can supply), so
    calling `effects.apply` with no `context` at all must raise `ContextRequired` whether the
    civilisation asked about owns the bonus (Malians) or not (Franks, Teutons) — answering the
    plain baseline for a non-owner without ever being told there is no Malians ally is exactly the
    silent substitution FR-038 and contracts/knowledge-base.md forbid ("a query that reaches a
    conditional effect without the input that decides it raises")."""
    with pytest.raises(effects.ContextRequired):
        effects.apply(
            _PROMOTED_DIRECTORY,
            civilisation=civilisation,
            kind="technology",
            id="50",
            field="production_time",
            value=50,
        )


def test_an_entity_and_field_no_team_effect_touches_answers_with_no_context() -> None:
    """The contrast case defect 1's own fix must not break: an entity and field no *team* effect
    touches at all — Franks' "Mill technologies free" (`condition` absent, `civilisation ==
    "Franks"` only) — still answers with no `context`, exactly as before. Technology 12 (Crop
    Rotation) is not in Malians' University selector, so nothing here reaches a team-conditioned
    effect regardless of civilisation."""
    result = effects.apply(
        _PROMOTED_DIRECTORY,
        civilisation="Franks",
        kind="technology",
        id="12",
        field="production_time",
        value=70,
    )
    assert not isinstance(result, effects.EffectNotModelled)
    value, applied = result
    assert value == 0
    assert applied


# ------------------------------------------------------------------------------------- T652w


@pytest.mark.parametrize(
    ("technology_id", "baseline", "civilisation", "team", "expected_divisor"),
    [
        # Franks-ally 377 (Siege Engineers, 45s baseline) — absent from Malians' own tree, so the
        # pre-T652w selector (restricted to Malians' own tree) matched nothing for any ally at all.
        ("377", 45, "Franks", frozenset({"Malians", "Franks"}), 1.80),
        # Franks-opponent: the same civilisation, the same technology, no Malians ally — the
        # contrast the fifth review asked for. The baseline must stand.
        ("377", 45, "Franks", frozenset({"Franks"}), 1.0),
        # A second ally, a second technology, neither Franks (Teutons can research Bombard Tower,
        # 64, per the fifth review's own table) — proving the fix is the selector's shape, not one
        # hand-picked entity.
        ("64", 60, "Teutons", frozenset({"Malians", "Teutons"}), 1.80),
    ],
)
def test_the_real_malians_university_team_bonus_reaches_every_ally_technology(
    technology_id: str,
    baseline: int,
    civilisation: str,
    team: frozenset[str],
    expected_divisor: float,
) -> None:
    """T652w, the fifth review's blocker: T652q restricted this row's selector to what Malians'
    own tree offers, which was the right restriction while the row refused for Malians alone; T652u
    then turned it into a `condition = "team"` effect that applies to every ally, and nobody
    re-derived the selector. Measured before the fix: 377 (Siege Engineers) answered 45s with no
    effect for any ally at all, not 25 — Malians' own tree does not offer 377, but Franks' does,
    and an ally's own tree — never the bonus owner's — decides what that ally can research
    (`available_to`)."""
    result = effects.apply(
        _PROMOTED_DIRECTORY,
        civilisation=civilisation,
        kind="technology",
        id=technology_id,
        field="production_time",
        value=baseline,
        context=effects.Context(team=team),
    )
    assert not isinstance(result, effects.EffectNotModelled)
    value, applied = result
    assert value == pytest.approx(baseline / expected_divisor)
    assert len(applied) == (1 if expected_divisor != 1.0 else 0)


def test_context_team_omitting_the_queried_civilisation_raises() -> None:
    """T652w: `Context.team` is documented as "the civilisations on the player's team, the
    player's own included" (contracts/knowledge-base.md) — a `team` that leaves the queried
    civilisation out of its own team is not a legitimate "no Malians ally" answer, it is malformed
    input, the same way a negative `add` operand or an out-of-range `age` is (see the age test
    below). Measured before this fix: Malians querying Chemistry (technology 47) with
    `team={"Franks"}` — omitting Malians itself — silently answered the plain baseline, 100s, as
    though Malians had no ally, rather than raising. `ValueError`, not `ContextRequired`:
    `ContextRequired` means the caller left a piece of `Context` out entirely; here a `team` was
    supplied, and it is simply not a coherent one."""
    with pytest.raises(ValueError):
        effects.apply(
            _PROMOTED_DIRECTORY,
            civilisation="Malians",
            kind="technology",
            id="47",
            field="production_time",
            value=100,
            context=effects.Context(team=frozenset({"Franks"})),
        )


def test_context_age_outside_the_valid_range_raises() -> None:
    """T652w: `Context.age` is the pack's own age numbering, 1 (Dark) to 4 (Imperial) — there is no
    fifth age. Measured before this fix: Franks' Castle cost (age-conditioned, tables for Castle
    and Imperial only) at `age=5` silently answered the plain baseline, 650 stone, the same way an
    age genuinely absent from the effect's own table does (age 1 or 2, before the discount starts)
    — but age 5 is not a legitimate absent key, it is not a game age at all, and conflating the two
    hides a caller defect behind a value that looks like a real "no discount yet" answer."""
    with pytest.raises(ValueError):
        effects.apply(
            _PROMOTED_DIRECTORY,
            civilisation="Franks",
            kind="building",
            id="82",
            field="cost",
            value={"stone": 650},
            context=effects.Context(age=5),
        )


def test_context_age_as_a_bool_raises() -> None:
    """**T652x, item (3).** `bool` is a subclass of `int` in Python, so `True == 1` and `True in
    {1, 2, 3, 4}` — `Context(age=True)` passed the `_VALID_AGES` membership check the test above
    guards, and then `str(True)` produced `"True"`, a key absent from every effect's own age table,
    so it silently answered the plain baseline rather than raising. Measured before this fix:
    Persians' Villager (unit 83, `condition = "age"`, a discount at every one of the pack's four
    ages) at `Context(age=True)` answered 25, the unadjusted baseline, exactly as though age were
    genuinely absent from the table — indistinguishable from a real "no discount yet" answer, the
    same conflation `test_context_age_outside_the_valid_range_raises` above already forbids for
    `age=5`. A caller who passes `True` almost certainly meant it as a flag, not as `1`, and either
    way it is not one of the pack's four ages."""
    with pytest.raises(ValueError):
        effects.apply(
            _PROMOTED_DIRECTORY,
            civilisation="Persians",
            kind="unit",
            id="83",
            field="production_time",
            value=25,
            context=effects.Context(age=True),
        )


def test_context_researched_and_team_do_not_share_the_bool_hole() -> None:
    """**T652x, item (3), the sweep.** `Context.age` compares by *value* against a `frozenset[int]`
    (`context.age not in _VALID_AGES`), which is exactly where `bool`'s `int` subclassing hides —
    `True == 1`. `Context.researched` and `Context.team` are never compared by value against a
    civilisation or technology id; they are only ever asked "is this string a member" (`in
    context.researched`, `in context.team`), and a bare `True`/`False` is not iterable at all, so
    Python itself raises before this package's own logic runs — confirmed directly, so this is a
    positive assertion of the current, already-correct behaviour, not a fix: passing a bare `bool`
    where a `frozenset[str]` belongs must never be mistaken for a silently-accepted baseline answer
    the way `age=True` was."""
    with pytest.raises(TypeError):
        effects.apply(
            _PROMOTED_DIRECTORY,
            civilisation="Franks",
            kind="unit",
            id="38",
            field="production_time",
            value=30,
            context=effects.Context(researched=True),  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError):
        effects.apply(
            _PROMOTED_DIRECTORY,
            civilisation="Malians",
            kind="technology",
            id="47",
            field="production_time",
            value=100,
            context=effects.Context(team=True),  # type: ignore[arg-type]
        )


def test_context_valid_team_and_age_still_answer() -> None:
    """The contrast the two tests above both need: a `Context` that is not malformed must still
    answer, not raise — `test_the_real_malians_university_team_bonus_applies_by_team` and
    `test_the_real_persians_town_center_work_speed_bonus_applies_by_age` already prove this for a
    team and an age respectively; this is the direct, side-by-side contrast for the two malformed
    inputs above, so a future change to either check cannot pass by breaking the valid case
    instead."""
    team_result = effects.apply(
        _PROMOTED_DIRECTORY,
        civilisation="Malians",
        kind="technology",
        id="47",
        field="production_time",
        value=100,
        context=effects.Context(team=frozenset({"Malians", "Franks"})),
    )
    assert not isinstance(team_result, effects.EffectNotModelled)
    team_value, _ = team_result
    assert team_value == pytest.approx(100 / 1.80)

    age_result = effects.apply(
        _PROMOTED_DIRECTORY,
        civilisation="Franks",
        kind="building",
        id="82",
        field="cost",
        value={"stone": 650},
        context=effects.Context(age=3),
    )
    assert not isinstance(age_result, effects.EffectNotModelled)
    age_value, _ = age_result
    assert age_value == {"stone": 553}


def test_the_real_persians_parthian_tactics_age_requirement_applies() -> None:
    """Persians: "Parthian Tactics available in Castle Age" lowers the technology's own baseline
    age requirement (4, Imperial — the same numbering unit 358 "Pikeman" = 3 and unit 359
    "Halberdier" = 4 confirm elsewhere) to 3 (Castle)."""
    result = effects.apply(
        _PROMOTED_DIRECTORY,
        civilisation="Persians",
        kind="technology",
        id="436",
        field="age_requirement",
        value=4,
    )
    assert not isinstance(result, effects.EffectNotModelled)
    value, applied = result
    assert value == 3
    assert applied[0].source_text == "Parthian Tactics available in Castle Age"


def test_the_real_teutons_farm_discount_applies() -> None:
    """Teutons: "Farms cost -40%" on the Farm's real, single-resource cost (`{wood: 60}`)."""
    result = effects.apply(
        _PROMOTED_DIRECTORY,
        civilisation="Teutons",
        kind="building",
        id="50",
        field="cost",
        value={"wood": 60},
    )
    assert not isinstance(result, effects.EffectNotModelled)
    value, applied = result
    assert value == {"wood": 36}
    assert applied[0].source_text == "Farms cost -40%"


def test_the_real_persians_kamandaran_bonus_is_not_modelled() -> None:
    """Persians' "Kamandaran" is a Castle unique technology, conditional on being researched — a
    rule this package could model since T652u (research.md D5, amended) — but the bullet never
    states the wood amount the discounted gold cost is replaced by, and no other vendored field
    carries it either, so an Archer's cost stays refused rather than silently adjusted (a wrong
    rule) or silently left baseline (the FR-038 substitution this whole feature exists to forbid).
    """
    result = effects.apply(
        _PROMOTED_DIRECTORY,
        civilisation="Persians",
        kind="unit",
        id="4",
        field="cost",
        value={"gold": 45, "wood": 25},
    )
    assert isinstance(result, effects.EffectNotModelled)
    assert "kamandaran" in result.reason.lower() or "unique technology" in result.reason.lower()


def test_the_real_tatars_town_center_sheep_bonus_is_not_modelled() -> None:
    """Tatars' "New Town Centers spawn 2 Sheep starting in Castle Age" is age-gated, and touches
    spawning a Sheep — no Sheep, Deer or Boar entity exists anywhere in this pack's `rules.json`
    at all — so it is refused rather than silently applied to the Town Center (T652m: Tatars
    replaces the previously committed, wrong Persians for this recording's fourth participant)."""
    result = effects.apply(
        _PROMOTED_DIRECTORY,
        civilisation="Tatars",
        kind="building",
        id="621",
        field="sheep_spawn",
        value=None,
    )
    assert isinstance(result, effects.EffectNotModelled)
    assert "age" in result.reason.lower()


# ------------------------------------------------------------------------------------- T652p (d)


_MINIMAL_SET_SCALAR_EFFECT = """\
[[effect]]
civilisation = "Franks"
source_key = "999"
source_text = "synthetic: a scalar field set to a whole number"
modelled = "yes"
field = "age_requirement"
operation = "set"
operand = 3
selector = [{ kind = "technology", id = "1" }]
validated_by = "synthetic fixture, T652p"
"""


def test_a_set_scalar_effect_returns_an_int_not_a_float() -> None:
    """T652p (d): data-model.md §6's rounding row stated the half-up convention as if it covered
    every operation; it is true of `multiply` and `add` only. `set` is a direct replacement with
    nothing to round, but a `set` against `age_requirement` — the field this test exercises — must
    still be typed as an int, that field being one this package always answers as a whole age
    number. (`production_time` is a `set` field too, but **T652u** stopped forcing it to an int: a
    time keeps its fraction, so this claim is deliberately scoped to `age_requirement` alone —
    see `test_the_real_franks_free_technology_effect_answers_zero` below for the `production_time`
    contrast.) Before the fix, `_apply_scalar`'s `set` branch returned the raw float `operand`
    unconverted."""
    (effect,) = effects.parse_effects_toml(_MINIMAL_SET_SCALAR_EFFECT)
    value, applied = effects.apply_matched(
        (effect,),
        civilisation="Franks",
        kind="technology",
        id="1",
        field="age_requirement",
        value=4,
    )
    assert value == 3
    assert isinstance(value, int), f"a 'set' scalar effect must answer an int, got {type(value)!r}"
    assert applied == (effect,)


def test_the_real_persians_age_requirement_effect_answers_an_int_not_a_float() -> None:
    """T652p (d), against the real committed snapshot rather than a synthetic fixture: Persians'
    pre-existing `age_requirement` discount goes through `_apply_scalar`'s `set` branch, so it must
    answer an int. Confirmed directly before that fix: it answered a float (`3.0`).

    T652q correction (the fourth review, item 6): the previous version of this test asserted only
    `isinstance(value, int)`, which passes just as well on the un-adjusted `baseline` — the
    `baseline` value passed in is already an int, so a regression that made `apply` return it
    untouched would still pass. This now asserts the real, adjusted value and that an effect was
    actually applied, not merely that whichever value came back happens to be an int."""
    result = effects.apply(
        _PROMOTED_DIRECTORY,
        civilisation="Persians",
        kind="technology",
        id="436",
        field="age_requirement",
        value=4,
    )
    assert not isinstance(result, effects.EffectNotModelled)
    value, applied = result
    assert isinstance(value, int), f"age_requirement must answer an int, got {type(value)!r}"
    assert value == 3
    assert applied, "an effect must actually have been applied, not merely a same-typed baseline"


def test_the_real_franks_free_technology_effect_answers_zero() -> None:
    """T652u: under the amended rounding row a **time** keeps its fraction, so a free technology's
    `production_time` is no longer asserted to be an `int` specifically — `_apply_scalar`'s `set`
    branch stops forcing a float `operand` to `int` for `production_time` (data-model.md §6:
    "`set` replaces the value with the operand", nothing more, and `0` has no fraction to keep
    either way). What still matters is the real, adjusted value (`0`, not the un-adjusted baseline
    `70`) and that an effect was actually applied, not merely a same-typed baseline slipping
    through — the same regression T652q's own correction above guards against."""
    result = effects.apply(
        _PROMOTED_DIRECTORY,
        civilisation="Franks",
        kind="technology",
        id="12",
        field="production_time",
        value=70,
    )
    assert not isinstance(result, effects.EffectNotModelled)
    value, applied = result
    assert value == 0
    assert applied, "an effect must actually have been applied, not merely a same-typed baseline"


# ------------------------------------------------------------------------------------- T652p (f)


_MINIMAL_ADD_MAPPING_EFFECT_TEMPLATE = """\
[[effect]]
civilisation = "Franks"
source_key = "998"
source_text = "synthetic: an add effect on a cost, T652p (f)"
modelled = "yes"
field = "cost"
operation = "add"
operand = {{ wood = {operand} }}
selector = [{{ kind = "building", id = "1" }}]
validated_by = "synthetic fixture, T652p"
"""


def test_an_add_that_would_drive_a_resource_negative_raises() -> None:
    """T652p (f): unreachable by any committed effect today (the one real `add` effect, Saracens'
    Market discount, never drives a resource below zero), but `add` is live data (that same
    Saracens discount — the free-technology model T652o added uses `set`, never `add`), and the
    invariant — a cost never goes negative — was previously unasserted."""
    (effect,) = effects.parse_effects_toml(_MINIMAL_ADD_MAPPING_EFFECT_TEMPLATE.format(operand=-30))
    with pytest.raises(effects.EffectsError, match="negative"):
        effects.apply_matched(
            (effect,),
            civilisation="Franks",
            kind="building",
            id="1",
            field="cost",
            value={"wood": 25},
        )


def test_an_add_that_lands_exactly_at_zero_does_not_raise() -> None:
    """The contrast case the guard above needs: zero is a valid cost (a free technology genuinely
    costs nothing), so landing exactly on it must not raise — only a result strictly below zero is
    a defect."""
    (effect,) = effects.parse_effects_toml(_MINIMAL_ADD_MAPPING_EFFECT_TEMPLATE.format(operand=-25))
    value, applied = effects.apply_matched(
        (effect,),
        civilisation="Franks",
        kind="building",
        id="1",
        field="cost",
        value={"wood": 25},
    )
    assert value == {"wood": 0}
    assert applied == (effect,)


_MINIMAL_ADD_SCALAR_EFFECT_TEMPLATE = """\
[[effect]]
civilisation = "Franks"
source_key = "998"
source_text = "synthetic: an add effect on a scalar field, T652r"
modelled = "yes"
field = "age_requirement"
operation = "add"
operand = {operand}
selector = [{{ kind = "technology", id = "1" }}]
validated_by = "synthetic fixture, T652r"
"""


def test_a_scalar_add_that_would_drive_a_field_negative_raises() -> None:
    """T652r: `_apply_mapping`'s 'add' branch already refused a cost below zero (T652p (f)); the
    scalar path (`_apply_scalar`) previously did not — "a scalar `add` ... go[es] below zero
    unguarded." No committed effect reaches this today, but the invariant must hold wherever
    `add` is live, not only on the mapping half."""
    (effect,) = effects.parse_effects_toml(_MINIMAL_ADD_SCALAR_EFFECT_TEMPLATE.format(operand=-5))
    with pytest.raises(effects.EffectsError, match="negative"):
        effects.apply_matched(
            (effect,),
            civilisation="Franks",
            kind="technology",
            id="1",
            field="age_requirement",
            value=3,
        )


def test_a_scalar_add_that_lands_exactly_at_zero_does_not_raise() -> None:
    (effect,) = effects.parse_effects_toml(_MINIMAL_ADD_SCALAR_EFFECT_TEMPLATE.format(operand=-3))
    value, applied = effects.apply_matched(
        (effect,),
        civilisation="Franks",
        kind="technology",
        id="1",
        field="age_requirement",
        value=3,
    )
    assert value == 0
    assert applied == (effect,)


# ------------------------------------------------------------ T652x, item (2): the refusal sweep

#: **T652x, item (2).** The literal phrasing the fifth review's nine still used to justify a
#: refusal by its own condition ("so the combat bonus only applies once it has been researched",
#: "so the range bonus only applies once it has been ...", one per unique-technology row) — amended
#: research.md D5 does not admit this anymore: a conditional bonus is a rule now (T652u), so being
#: conditional on research is never, by itself, a reason to refuse. This is a narrow, literal
#: regression guard for the exact defect signature the fifth review found, not a general prover: a
#: differently-worded future violation (e.g. "the bonus needs Chivalry to have been studied first")
#: would not trip it. A broader word-list (banning "conditional", "researched", "age-gated", ...
#: anywhere in a reason) was rejected as genuinely brittle — Kamandaran's own reason legitimately
#: uses this same vocabulary (its refusal really is about a missing wood amount, not the condition,
#: research.md D5's own stated exception), and the eight rows T652w already fixed legitimately say
#: "conditional on research no longer disqualifies a bonus by itself", which contains "researched"
#: and "conditional" too. The one thing every one of those legitimate uses shares, and the nine
#: defective rows did not, is `effect.condition`: Kamandaran's own effect record carries
#: `condition = "researched"` (T652x's own re-derivation below checks the *record*, not the prose,
#: for that), and the fixed eight only ever use the vocabulary to say the condition no longer
#: matters. So the check is structural where it can be (an effect that frames its own refusal as
#: conditional, by this literal phrase, must actually carry a registered `condition`), not a
#: vocabulary ban.
_JUSTIFIES_REFUSAL_BY_CONDITION_PHRASE = "only applies once it has been"


@pytest.mark.parametrize("directory", [_PROMOTED_DIRECTORY, _PROMOTED_177723_DIRECTORY])
def test_no_refusal_reason_justifies_itself_by_an_unregistered_condition(directory: str) -> None:
    """**T652x, item (2), the sweep.** Every `modelled = "no"` effect whose `reason` uses the fifth
    review's defect phrase must actually carry a registered `condition` — otherwise the refusal is
    blaming a condition amended research.md D5 says can no longer justify a refusal by itself, and
    the row must instead say only that its field is not carried (T652w did this for eight rows,
    T652x for the nine the fifth review found)."""
    offenders = [
        effect
        for effect in effects._effects(directory)
        if effect.modelled == "no"
        and not effect.conditions
        and effect.reason is not None
        and _JUSTIFIES_REFUSAL_BY_CONDITION_PHRASE in effect.reason
    ]
    assert not offenders, (
        f"{directory}: {len(offenders)} modelled=no row(s) still justify their own refusal by a "
        "condition with no registered effect.condition to back it, amended research.md D5's own "
        "fault: "
        f"{[(e.civilisation, e.source_text) for e in offenders]!r}"
    )


# ------------------------------------------------------------ T762: condition = "controlled"

_TC_AND_CASTLE = frozenset(
    {effects.SelectorEntry("building", "109"), effects.SelectorEntry("building", "82")}
)
_BARRACKS = frozenset({effects.SelectorEntry("building", "12")})


def _controlled_effect_toml(
    *,
    operand: str = "{ 1 = 0.95, 2 = 0.90, 3 = 0.85, 4 = 0.80 }",
    condition_entities: str | None = (
        '[{ kind = "building", id = "109" }, { kind = "building", id = "82" }]'
    ),
    selector: str = '[{ kind = "unit", id = "74" }]',
    field: str = "cost_factor",
    operation: str = "multiply",
    condition: str = "controlled",
) -> str:
    """A synthetic `controlled` effect: the operand is a table keyed by a count of the entities
    `condition_entities` names (Saxons' Foot Soldiers shape, without transcribing Saxons)."""
    entities_line = (
        f"condition_entities = {condition_entities}\n" if condition_entities is not None else ""
    )
    return f"""\
[[effect]]
civilisation = "Synthetic"
source_key = "0"
source_text = "Foot Soldiers cost -5% per Town Center or Castle controlled (maximum -20%)"
modelled = "yes"
field = "{field}"
operation = "{operation}"
operand = {operand}
condition = "{condition}"
{entities_line}selector = {selector}
validated_by = "synthetic"
"""


def _apply_controlled(effect: effects.Effect, controlled: object, *, value: object = 100) -> object:
    result = effects.apply_matched(
        (effect,),
        civilisation="Synthetic",
        kind="unit",
        id="74",
        field="cost_factor",
        value=value,
        context=None if controlled is None else effects.Context(controlled=controlled),  # type: ignore[arg-type]
    )
    assert not isinstance(result, effects.EffectNotModelled)
    return result


def test_controlled_is_a_registered_condition() -> None:
    assert "controlled" in effects.CONDITIONS


def test_a_controlled_effect_parses_its_entities_as_a_set_of_selector_entries() -> None:
    (effect,) = effects.parse_effects_toml(_controlled_effect_toml())
    assert effect.conditions == ("controlled",)
    assert frozenset(effect.condition_entities) == _TC_AND_CASTLE


@pytest.mark.parametrize(
    ("count", "expected_value", "expected_applied"),
    [
        (0, 100, 0),  # below the lowest key (1): the effect does not apply
        (1, 95, 1),
        (4, 80, 1),
        (5, 80, 1),  # above the highest key: the highest key's operand, the stated maximum
        (40, 80, 1),
    ],
)
def test_a_controlled_table_keyed_one_to_four_at_counts_around_its_edges(
    count: int, expected_value: float, expected_applied: int
) -> None:
    (effect,) = effects.parse_effects_toml(_controlled_effect_toml())
    value, applied = _apply_controlled(effect, {_TC_AND_CASTLE: count})  # type: ignore[misc]
    assert value == expected_value
    assert len(applied) == expected_applied


def test_a_controlled_sparse_table_takes_the_highest_key_not_above_the_count() -> None:
    """The rule between keys: the highest key not above the count — the same rule that makes a
    count above the highest key take that key's operand, applied between keys."""
    (effect,) = effects.parse_effects_toml(_controlled_effect_toml(operand="{ 1 = 0.9, 3 = 0.5 }"))
    results = {
        count: _apply_controlled(effect, {_TC_AND_CASTLE: count})[0]  # type: ignore[index]
        for count in (0, 1, 2, 3, 4)
    }
    assert results == {0: 100, 1: 90, 2: 90, 3: 50, 4: 50}


def test_a_controlled_table_may_start_at_zero() -> None:
    (effect,) = effects.parse_effects_toml(_controlled_effect_toml(operand="{ 0 = 0.5, 2 = 0.25 }"))
    assert _apply_controlled(effect, {_TC_AND_CASTLE: 0})[0] == 50  # type: ignore[index]


def test_a_controlled_effect_with_a_cost_mapping_operand() -> None:
    (effect,) = effects.parse_effects_toml(
        _controlled_effect_toml(
            operand="{ 1 = { food = 0.95 }, 2 = { food = 0.90 } }", field="cost_factor"
        )
    )
    value, _applied = _apply_controlled(
        effect, {_TC_AND_CASTLE: 2}, value={"food": 100, "gold": 40}
    )  # type: ignore[misc]
    assert value == {"food": 90, "gold": 40}


def test_a_controlled_effect_raises_without_a_context() -> None:
    (effect,) = effects.parse_effects_toml(_controlled_effect_toml())
    with pytest.raises(effects.ContextRequired):
        _apply_controlled(effect, None)


def test_a_controlled_effect_raises_when_the_context_carries_no_counts() -> None:
    (effect,) = effects.parse_effects_toml(_controlled_effect_toml())
    result_context = effects.Context(age=2)
    with pytest.raises(effects.ContextRequired):
        effects.apply_matched(
            (effect,),
            civilisation="Synthetic",
            kind="unit",
            id="74",
            field="cost_factor",
            value=100,
            context=result_context,
        )


def test_a_count_for_other_entities_does_not_answer_this_effect() -> None:
    """Two `controlled` effects on different entity sets must not be fed one count: a count the
    caller stated for the Barracks says nothing about the Town Centers and Castles."""
    (effect,) = effects.parse_effects_toml(_controlled_effect_toml())
    with pytest.raises(effects.ContextRequired) as raised:
        _apply_controlled(effect, {_BARRACKS: 3})
    assert "109" in str(raised.value)
    assert "82" in str(raised.value)


def test_two_controlled_effects_on_different_entity_sets_each_read_their_own_count() -> None:
    (first,) = effects.parse_effects_toml(_controlled_effect_toml())
    (second,) = effects.parse_effects_toml(
        _controlled_effect_toml(
            operand="{ 1 = 0.5 }", condition_entities='[{ kind = "building", id = "12" }]'
        )
    )
    value, applied = effects.apply_matched(
        (first, second),
        civilisation="Synthetic",
        kind="unit",
        id="74",
        field="cost_factor",
        value=100,
        context=effects.Context(controlled={_TC_AND_CASTLE: 2, _BARRACKS: 7}),
    )
    assert value == 45  # 100 * 0.90 = 90, then 90 * 0.5
    assert applied == (first, second)


def test_the_order_condition_entities_are_written_in_does_not_matter() -> None:
    (effect,) = effects.parse_effects_toml(
        _controlled_effect_toml(
            condition_entities=(
                '[{ kind = "building", id = "82" }, { kind = "building", id = "109" }]'
            )
        )
    )
    assert _apply_controlled(effect, {_TC_AND_CASTLE: 1})[0] == 95  # type: ignore[index]


@pytest.mark.parametrize("count", [-1, True, 2.0, "2", None])
def test_a_malformed_count_is_a_value_error_not_context_required(count: object) -> None:
    (effect,) = effects.parse_effects_toml(_controlled_effect_toml())
    with pytest.raises(ValueError, match="count"):
        _apply_controlled(effect, {_TC_AND_CASTLE: count})


def test_an_unrelated_effect_on_the_same_entity_answers_without_any_count() -> None:
    """The contrast case: only reaching a `controlled` effect needs a count. An unconditional
    effect on the same entity and field answers with no context at all — and the same entity with
    a `controlled` effect added beside it raises, so the count is asked for by that effect alone."""
    (plain,) = effects.parse_effects_toml(_MINIMAL_MODELLED_EFFECT)
    (gated,) = effects.parse_effects_toml(
        _controlled_effect_toml(field="cost", selector='[{ kind = "unit", id = "358" }]')
    )
    query = {
        "civilisation": "Byzantines",
        "kind": "unit",
        "id": "358",
        "field": "cost",
        "value": {"food": 35, "wood": 25},
    }
    answered = effects.apply_matched((plain,), **query)  # type: ignore[arg-type]
    assert not isinstance(answered, effects.EffectNotModelled)
    assert answered[0] == {"food": 26, "wood": 19}
    assert answered[1] == (plain,)
    with pytest.raises(effects.ContextRequired):
        effects.apply_matched((plain, gated), **query)  # type: ignore[arg-type]


def test_a_not_modelled_controlled_effect_still_refuses_without_a_count() -> None:
    text = """\
[[effect]]
civilisation = "Synthetic"
source_key = "0"
source_text = "a bonus whose amount the source never states"
modelled = "no"
reason = "the amount is not stated"
field = "cost_factor"
condition = "controlled"
condition_entities = [{ kind = "building", id = "109" }]
selector = [{ kind = "unit", id = "74" }]
validated_by = "synthetic"
"""
    (effect,) = effects.parse_effects_toml(text)
    result = effects.apply_matched(
        (effect,),
        civilisation="Synthetic",
        kind="unit",
        id="74",
        field="cost_factor",
        value=100,
    )
    assert isinstance(result, effects.EffectNotModelled)


# parse-time refusals


def test_parse_rejects_a_controlled_effect_without_condition_entities() -> None:
    with pytest.raises(effects.EffectsError, match="condition_entities"):
        effects.parse_effects_toml(_controlled_effect_toml(condition_entities=None))


def test_parse_rejects_a_controlled_effect_with_empty_condition_entities() -> None:
    with pytest.raises(effects.EffectsError, match="condition_entities"):
        effects.parse_effects_toml(_controlled_effect_toml(condition_entities="[]"))


def test_parse_rejects_condition_entities_on_a_condition_that_does_not_use_them() -> None:
    with pytest.raises(effects.EffectsError, match="condition_entities"):
        effects.parse_effects_toml(_controlled_effect_toml(operand="{ 2 = 0.9 }", condition="age"))


def test_parse_rejects_a_duplicated_condition_entity() -> None:
    with pytest.raises(effects.EffectsError, match="condition_entities"):
        effects.parse_effects_toml(
            _controlled_effect_toml(
                condition_entities='[{ kind = "building", id = "109" }, '
                '{ kind = "building", id = "109" }]'
            )
        )


@pytest.mark.parametrize(
    "operand",
    [
        "{}",  # an empty table
        "0.9",  # not a table
        '{ "-1" = 0.9 }',  # a negative key
        "{ one = 0.9 }",  # a non-integer key
        '{ "1.5" = 0.9 }',  # a fractional key
        '{ "01" = 0.9 }',  # a non-canonical key ("01" and "1" would both be count 1)
        '{ 1 = "cheap" }',  # a non-numeric operand
        "{ 1 = true }",  # a bool is not a number
        "{ 1 = {} }",  # an empty cost mapping
        '{ 1 = { food = "cheap" } }',  # a non-numeric leaf inside a cost mapping
    ],
)
def test_parse_rejects_a_malformed_controlled_table(operand: str) -> None:
    with pytest.raises(effects.EffectsError, match="operand"):
        effects.parse_effects_toml(_controlled_effect_toml(operand=operand))


def test_the_existing_numeric_guards_walk_a_controlled_table() -> None:
    with pytest.raises(effects.EffectsError):
        effects.parse_effects_toml(
            _controlled_effect_toml(operand="{ 1 = { food = -0.5 } }", field="cost")
        )


# ------------------------------------------------- T764: produced_at, an effect adds a building

_HUSKARL = "41"
_BARRACKS_ID = "12"
_CASTLE_ID = "82"
_STABLE_ID = "101"


def _produced_at_effect_toml(
    *,
    operand: str = f'"{_BARRACKS_ID}"',
    operation: str = "add",
    condition_lines: str = "",
    civilisation: str = "Synthetic",
    selector: str = f'[{{ kind = "unit", id = "{_HUSKARL}" }}]',
    modelled: str = "yes",
) -> str:
    """A synthetic effect that adds a producing building (the Goths' Anarchy shape, without
    transcribing Goths): the operand is the building's identifier, the operation is `add`."""
    body = (
        f'operation = "{operation}"\noperand = {operand}\n'
        if modelled == "yes"
        else 'reason = "synthetic"\n'
    )
    return f"""\
[[effect]]
civilisation = "{civilisation}"
source_key = "0"
source_text = "Huskarls can be trained at Barracks"
modelled = "{modelled}"
field = "produced_at"
{body}{condition_lines}selector = {selector}
validated_by = "synthetic"
"""


def _produced_at(
    toml_text: str,
    *,
    baseline: tuple[str, ...] = (_CASTLE_ID,),
    context: effects.Context | None = None,
    civilisation: str = "Synthetic",
) -> tuple[str, ...]:
    result = effects.apply_matched(
        effects.parse_effects_toml(toml_text),
        civilisation=civilisation,
        kind="unit",
        id=_HUSKARL,
        field="produced_at",
        value=baseline,
        context=context,
    )
    assert not isinstance(result, effects.EffectNotModelled)
    value, _applied = result
    assert isinstance(value, tuple)
    return value


def test_an_unconditional_effect_adds_a_producing_building_after_the_packs_own() -> None:
    assert _produced_at(_produced_at_effect_toml()) == (_CASTLE_ID, _BARRACKS_ID)


@pytest.mark.parametrize(
    ("researched", "expected"),
    [
        (frozenset(), (_CASTLE_ID,)),  # Anarchy not yet researched: the pack's building alone
        (frozenset({"457"}), (_CASTLE_ID, _BARRACKS_ID)),  # researched: the addition follows
    ],
)
def test_a_researched_addition_applies_only_after_its_technology(
    researched: frozenset[str], expected: tuple[str, ...]
) -> None:
    text = _produced_at_effect_toml(
        condition_lines='condition = "researched"\ncondition_technology = "457"\n'
    )
    assert _produced_at(text, context=effects.Context(researched=researched)) == expected


def test_a_researched_addition_raises_without_a_context() -> None:
    text = _produced_at_effect_toml(
        condition_lines='condition = "researched"\ncondition_technology = "457"\n'
    )
    with pytest.raises(effects.ContextRequired):
        _produced_at(text)


def test_the_packs_building_stays_first_and_additions_follow_in_file_order() -> None:
    text = _produced_at_effect_toml(operand='"101"') + _produced_at_effect_toml(operand='"12"')
    assert _produced_at(text) == (_CASTLE_ID, "101", "12")


def test_an_entity_the_pack_places_nowhere_gains_the_added_building_alone() -> None:
    assert _produced_at(_produced_at_effect_toml(), baseline=()) == (_BARRACKS_ID,)


def test_an_addition_works_with_an_age_condition() -> None:
    text = _produced_at_effect_toml(operand='{ 3 = "12" }', condition_lines='condition = "age"\n')
    assert _produced_at(text, context=effects.Context(age=2)) == (_CASTLE_ID,)
    assert _produced_at(text, context=effects.Context(age=3)) == (_CASTLE_ID, _BARRACKS_ID)


def test_an_addition_works_with_a_controlled_condition() -> None:
    text = _produced_at_effect_toml(
        operand='{ 1 = "12" }',
        condition_lines='condition = "controlled"\n'
        'condition_entities = [{ kind = "building", id = "109" }]\n',
    )
    key = frozenset({effects.SelectorEntry("building", "109")})
    assert _produced_at(text, context=effects.Context(controlled={key: 0})) == (_CASTLE_ID,)
    assert _produced_at(text, context=effects.Context(controlled={key: 1})) == (
        _CASTLE_ID,
        _BARRACKS_ID,
    )


def test_an_addition_works_with_a_team_condition() -> None:
    text = _produced_at_effect_toml(condition_lines='condition = "team"\n')
    allied = effects.Context(team=frozenset({"Synthetic", "Franks"}))
    alone = effects.Context(team=frozenset({"Franks"}))
    assert _produced_at(text, context=allied, civilisation="Franks") == (
        _CASTLE_ID,
        _BARRACKS_ID,
    )
    assert _produced_at(text, context=alone, civilisation="Franks") == (_CASTLE_ID,)


def test_an_addition_of_the_packs_own_building_does_not_duplicate_it() -> None:
    assert _produced_at(_produced_at_effect_toml(operand='"82"')) == (_CASTLE_ID,)


def test_two_additions_of_one_building_answer_it_once() -> None:
    text = _produced_at_effect_toml() + _produced_at_effect_toml()
    assert _produced_at(text) == (_CASTLE_ID, _BARRACKS_ID)


def test_an_entity_no_effect_touches_answers_the_packs_building_alone() -> None:
    result = effects.apply_matched(
        (),
        civilisation="Synthetic",
        kind="unit",
        id=_HUSKARL,
        field="produced_at",
        value=(_CASTLE_ID,),
    )
    assert result == ((_CASTLE_ID,), ())


def test_an_addition_for_one_civilisation_does_not_reach_another(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parsed = effects.parse_effects_toml(_produced_at_effect_toml(civilisation="Goths"))
    monkeypatch.setattr(effects, "_effects", lambda _directory: parsed)

    def answer(civilisation: str) -> object:
        return effects.apply(
            "any",
            civilisation=civilisation,
            kind="unit",
            id=_HUSKARL,
            field="produced_at",
            value=(_CASTLE_ID,),
        )

    assert answer("Goths") == ((_CASTLE_ID, _BARRACKS_ID), parsed)
    assert answer("Franks") == ((_CASTLE_ID,), ())


def test_an_addition_does_not_reach_an_entity_its_selector_does_not_name() -> None:
    result = effects.apply_matched(
        (),  # what effects_for returns for another unit: the selector names only the Huskarl
        civilisation="Synthetic",
        kind="unit",
        id="999",
        field="produced_at",
        value=(_STABLE_ID,),
    )
    assert result == ((_STABLE_ID,), ())


def test_a_not_modelled_produced_at_effect_still_refuses() -> None:
    (effect,) = effects.parse_effects_toml(_produced_at_effect_toml(modelled="no"))
    result = effects.apply_matched(
        (effect,),
        civilisation="Synthetic",
        kind="unit",
        id=_HUSKARL,
        field="produced_at",
        value=(_CASTLE_ID,),
    )
    assert isinstance(result, effects.EffectNotModelled)


def test_the_applied_effect_is_listed_even_when_it_added_nothing_new() -> None:
    (effect,) = effects.parse_effects_toml(_produced_at_effect_toml(operand='"82"'))
    result = effects.apply_matched(
        (effect,),
        civilisation="Synthetic",
        kind="unit",
        id=_HUSKARL,
        field="produced_at",
        value=(_CASTLE_ID,),
    )
    assert result == ((_CASTLE_ID,), (effect,))


# parse-time refusals


@pytest.mark.parametrize("operation", ["set", "multiply", "faster"])
def test_parse_rejects_every_operation_on_produced_at_but_add(operation: str) -> None:
    with pytest.raises(effects.EffectsError, match="produced_at"):
        effects.parse_effects_toml(_produced_at_effect_toml(operation=operation))


@pytest.mark.parametrize(
    "operand",
    [
        "12",  # a bare number: rules.json keys are strings
        "true",
        '""',  # blank
        '"Barracks"',  # a name, not an identifier
        '"012"',  # not the one canonical spelling of an identifier
        '"-12"',
        '"12.0"',
        '["12", "101"]',  # one building per effect
        '{ food = "12" }',  # a table on an effect with no table-valued condition
        "{}",
    ],
)
def test_parse_rejects_a_produced_at_operand_that_is_not_one_building_identifier(
    operand: str,
) -> None:
    with pytest.raises(effects.EffectsError, match="operand"):
        effects.parse_effects_toml(_produced_at_effect_toml(operand=operand))


@pytest.mark.parametrize(
    ("operand", "condition_lines"),
    [
        ("{ 2 = 12 }", 'condition = "age"\n'),
        ('{ 2 = "Barracks" }', 'condition = "age"\n'),
        ('{ 2 = { food = "12" } }', 'condition = "age"\n'),
        (
            "{ 1 = 12 }",
            'condition = "controlled"\ncondition_entities = [{ kind = "building", id = "109" }]\n',
        ),
    ],
)
def test_parse_rejects_a_malformed_produced_at_table_leaf(
    operand: str, condition_lines: str
) -> None:
    with pytest.raises(effects.EffectsError, match="operand"):
        effects.parse_effects_toml(
            _produced_at_effect_toml(operand=operand, condition_lines=condition_lines)
        )


def test_parse_accepts_a_produced_at_age_table_of_identifiers() -> None:
    (effect,) = effects.parse_effects_toml(
        _produced_at_effect_toml(
            operand='{ 3 = "12", 4 = "101" }', condition_lines='condition = "age"\n'
        )
    )
    assert effect.operand == {"3": "12", "4": "101"}


def test_a_numeric_field_still_refuses_a_string_operand_at_application() -> None:
    """Contrast: only `produced_at` takes a building identifier; a cost still needs a number."""
    text = _produced_at_effect_toml().replace('field = "produced_at"', 'field = "cost"')
    (effect,) = effects.parse_effects_toml(text)
    with pytest.raises(effects.EffectsError):
        effects.apply_matched(
            (effect,),
            civilisation="Synthetic",
            kind="unit",
            id=_HUSKARL,
            field="cost",
            value={"food": 50},
        )


# ------------------------------------------------ T763: available_to, an effect sets a boolean

_STABLE = "101"
_DONJON_LINE_SELECTOR = f'[{{ kind = "building", id = "{_STABLE}" }}]'


def _availability_effect_toml(
    *,
    operand: str = "false",
    operation: str = "set",
    condition_lines: str = "",
    civilisation: str = "Synthetic",
    modelled: str = "yes",
) -> str:
    """A synthetic effect that makes an entity available or not (the Sicilians' Donjon, Folwark or
    Harbors shape, without transcribing a civilisation): the operation is `set`, the operand a
    boolean."""
    body = (
        f'operation = "{operation}"\noperand = {operand}\n'
        if modelled == "yes"
        else 'reason = "synthetic"\n'
    )
    return f"""\
[[effect]]
civilisation = "{civilisation}"
source_key = "0"
source_text = "Can build Donjon in Dark Age, replaces Watch Tower-line"
modelled = "{modelled}"
field = "available_to"
{body}{condition_lines}selector = {_DONJON_LINE_SELECTOR}
validated_by = "synthetic"
"""


def _availability(
    toml_text: str,
    *,
    baseline: bool = True,
    context: effects.Context | None = None,
    civilisation: str = "Synthetic",
) -> object:
    result = effects.apply_matched(
        effects.parse_effects_toml(toml_text),
        civilisation=civilisation,
        kind="building",
        id=_STABLE,
        field="available_to",
        value=baseline,
        context=context,
    )
    assert not isinstance(result, effects.EffectNotModelled)
    value, _applied = result
    return value


def test_an_unconditional_false_removes_an_entity_the_tree_offers() -> None:
    assert _availability(_availability_effect_toml(operand="false"), baseline=True) is False


def test_an_unconditional_true_adds_an_entity_the_tree_does_not_offer() -> None:
    assert _availability(_availability_effect_toml(operand="true"), baseline=False) is True


def test_a_boolean_result_is_a_bool_not_an_integer() -> None:
    """`set` on a number returns `int(operand)`; availability must not go through that path, or the
    answer would be `1` and `0`, equal to `True` and `False` and not them."""
    assert type(_availability(_availability_effect_toml(operand="true"), baseline=False)) is bool


_RESEARCHED_THALASSOCRACY = 'condition = "researched"\ncondition_technology = "1230"\n'


@pytest.mark.parametrize(
    ("researched", "expected"),
    [(frozenset(), True), (frozenset({"1230"}), False)],
    ids=["before the technology", "after the technology"],
)
def test_a_researched_false_applies_only_once_its_technology_is(
    researched: frozenset[str], expected: bool
) -> None:
    text = _availability_effect_toml(operand="false", condition_lines=_RESEARCHED_THALASSOCRACY)
    context = effects.Context(researched=researched)
    assert _availability(text, baseline=True, context=context) is expected


def test_a_researched_availability_effect_raises_without_a_context() -> None:
    text = _availability_effect_toml(operand="false", condition_lines=_RESEARCHED_THALASSOCRACY)
    with pytest.raises(effects.ContextRequired):
        _availability(text)


@pytest.mark.parametrize(("age", "expected"), [(1, True), (2, False), (3, False)])
def test_an_age_conditioned_true_holds_at_the_ages_its_table_names(
    age: int, expected: bool
) -> None:
    text = _availability_effect_toml(operand="{ 1 = true }", condition_lines='condition = "age"\n')
    assert _availability(text, baseline=False, context=effects.Context(age=age)) is expected


def test_an_age_table_may_state_both_booleans() -> None:
    text = _availability_effect_toml(
        operand="{ 1 = true, 3 = false }", condition_lines='condition = "age"\n'
    )
    assert _availability(text, baseline=False, context=effects.Context(age=1)) is True
    assert _availability(text, baseline=True, context=effects.Context(age=3)) is False


def test_a_controlled_availability_table_reads_the_count() -> None:
    entities = '[{ kind = "building", id = "109" }]'
    text = _availability_effect_toml(
        operand="{ 1 = true }",
        condition_lines=f'condition = "controlled"\ncondition_entities = {entities}\n',
    )
    key = frozenset({effects.SelectorEntry(kind="building", id="109")})
    assert (
        _availability(text, baseline=False, context=effects.Context(controlled={key: 0})) is False
    )
    assert _availability(text, baseline=False, context=effects.Context(controlled={key: 2})) is True


def test_a_team_availability_effect_reaches_a_teammate() -> None:
    text = _availability_effect_toml(operand="true", condition_lines='condition = "team"\n')
    allied = effects.Context(team=frozenset({"Synthetic", "Franks"}))
    assert _availability(text, baseline=False, context=allied, civilisation="Franks") is True


def test_a_not_modelled_availability_effect_still_refuses() -> None:
    (effect,) = effects.parse_effects_toml(_availability_effect_toml(modelled="no"))
    result = effects.apply_matched(
        (effect,),
        civilisation="Synthetic",
        kind="building",
        id=_STABLE,
        field="available_to",
        value=True,
    )
    assert isinstance(result, effects.EffectNotModelled)


@pytest.mark.parametrize(
    "operand",
    ["1", "0", "1.0", '"true"', '"yes"', "[true]", "{}", "{ a = true }"],
)
def test_parse_rejects_a_non_boolean_availability_operand(operand: str) -> None:
    with pytest.raises(effects.EffectsError, match="available_to"):
        effects.parse_effects_toml(_availability_effect_toml(operand=operand))


@pytest.mark.parametrize("operation", ["add", "multiply", "faster"])
def test_parse_rejects_every_operation_on_available_to_but_set(operation: str) -> None:
    with pytest.raises(effects.EffectsError, match="available_to"):
        effects.parse_effects_toml(_availability_effect_toml(operation=operation))


@pytest.mark.parametrize(
    ("operand", "condition_lines"),
    [
        ("{ 1 = 1 }", 'condition = "age"\n'),
        ('{ 1 = "true" }', 'condition = "age"\n'),
        ("{ 1 = { x = true } }", 'condition = "age"\n'),
        (
            "{ 1 = 1 }",
            'condition = "controlled"\ncondition_entities = [{ kind = "building", id = "109" }]\n',
        ),
        (
            "{ 1 = 1.5 }",
            'condition = "controlled"\ncondition_entities = [{ kind = "building", id = "109" }]\n',
        ),
    ],
)
def test_parse_rejects_a_non_boolean_availability_table_value(
    operand: str, condition_lines: str
) -> None:
    with pytest.raises(effects.EffectsError):
        effects.parse_effects_toml(
            _availability_effect_toml(operand=operand, condition_lines=condition_lines)
        )


def test_parse_rejects_a_boolean_where_the_field_is_numeric() -> None:
    """Contrast: the boolean rule is `available_to`'s alone; a cost 'set' still needs a number."""
    text = _availability_effect_toml(operand="true").replace(
        'field = "available_to"', 'field = "cost"'
    )
    (effect,) = effects.parse_effects_toml(text)
    with pytest.raises(effects.EffectsError):
        effects.apply_matched(
            (effect,),
            civilisation="Synthetic",
            kind="building",
            id=_STABLE,
            field="cost",
            value={"food": 50},
        )


# ----------------------------------------------- T780: age_requirement takes the match state
#
# `age_requirement` took no `context`, so a bonus that moves an age with the match state (the
# Cumans' additional Town Center, "in Feudal Age" once a count of Town Centers is controlled) could
# only be refused. These go through the query surface, not `apply_matched`: the parse and the
# application of a `controlled` table were already proven for every field above; what T780 adds is
# that the query lets the state in, reaches the effect with it, and refuses an unmodelled teammate
# first.

_AGE_BUILD = 180059  # a promoted snapshot that models Franks
_PIKEMAN = "358"  # baseline age_requirement 3 in that snapshot
_TOWN_CENTER_ONLY = frozenset({effects.SelectorEntry("building", "109")})


def _age_requirement_controlled_toml(*, civilisation: str = "Franks") -> str:
    return f"""\
[[effect]]
civilisation = "{civilisation}"
source_key = "0"
source_text = "synthetic: the age moves with the Town Centers controlled"
modelled = "yes"
field = "age_requirement"
operation = "set"
operand = {{ 0 = 4, 2 = 2 }}
condition = "controlled"
condition_entities = [{{ kind = "building", id = "109" }}]
selector = [{{ kind = "unit", id = "{_PIKEMAN}" }}]
validated_by = "synthetic"
"""


@pytest.fixture
def synthetic_age_requirement(monkeypatch: pytest.MonkeyPatch) -> None:
    parsed = effects.parse_effects_toml(_age_requirement_controlled_toml())
    monkeypatch.setattr(effects, "_effects", lambda _directory: parsed)


def _pikeman() -> query.EntityRef:
    return query.EntityRef(kind="unit", id=_PIKEMAN, build=_AGE_BUILD)


@pytest.mark.parametrize(("count", "expected"), [(0, 4), (1, 4), (2, 2)])
def test_a_controlled_age_requirement_reads_the_count_it_is_given(
    synthetic_age_requirement: None, count: int, expected: int
) -> None:
    """The table is keyed "0" and "2": a count between the keys takes the lower one, a count at the
    highest key takes it. The baseline is 3, so no count answers it by coincidence."""
    answer = query.age_requirement(
        _pikeman(),
        civilisation="Franks",
        context=query.Context(controlled={_TOWN_CENTER_ONLY: count}),
    )
    assert not isinstance(answer, KnowledgeGap)
    assert answer.value == expected
    assert isinstance(answer.value, int)
    assert len(answer.effects) == 1


@pytest.mark.parametrize(
    "context",
    [None, query.Context(), query.Context(team=frozenset({"Franks"}))],
    ids=["no context", "empty context", "a team and no count"],
)
def test_a_controlled_age_requirement_raises_without_a_count(
    synthetic_age_requirement: None, context: query.Context | None
) -> None:
    with pytest.raises(effects.ContextRequired):
        query.age_requirement(_pikeman(), civilisation="Franks", context=context)


def test_a_count_for_other_entities_does_not_answer_a_controlled_age_requirement(
    synthetic_age_requirement: None,
) -> None:
    with pytest.raises(effects.ContextRequired):
        query.age_requirement(
            _pikeman(),
            civilisation="Franks",
            context=query.Context(controlled={_BARRACKS: 2}),
        )


def test_an_unmodelled_teammate_refuses_age_requirement_and_is_named() -> None:
    """Step 1 of "Civilisation qualification" reaches `age_requirement` as it reaches `cost`: an
    unmodelled civilisation in `context.team` makes the answer unknown, whatever effect touches the
    entity, and the gap names the teammate. Britons is not modelled in that snapshot."""
    answer = query.age_requirement(
        _pikeman(),
        civilisation="Franks",
        context=query.Context(team=frozenset({"Franks", "Britons"})),
    )
    assert isinstance(answer, KnowledgeGap)
    assert answer.cause == "civilisation-not-modelled"
    assert answer.field == "age_requirement"
    assert answer.civilisation == "Britons"


def test_age_requirement_answers_as_before_where_no_conditional_effect_applies() -> None:
    answer = query.age_requirement(_pikeman(), civilisation="Franks")
    assert not isinstance(answer, KnowledgeGap)
    assert answer.value == 3
    assert answer.effects == ()
    with_team = query.age_requirement(
        _pikeman(),
        civilisation="Franks",
        context=query.Context(team=frozenset({"Franks", "Teutons"})),
    )
    assert not isinstance(with_team, KnowledgeGap)
    assert with_team.value == 3


def test_the_coverage_pass_hands_context_to_age_requirement() -> None:
    from aoe2stats_knowledge import coverage

    assert "age_requirement" in coverage._CONTEXT_AWARE_FIELDS


# ------------------------------------------------- T781: more than one condition on one effect


def _multi_condition_toml(
    condition: str = '["researched", "team"]',
    *,
    operand: str = "0.8",
    technology: str | None = '"kasbah"',
    entities: bool = False,
) -> str:
    """A synthetic Kasbah-shaped effect: Castles work faster once the owner has researched a
    technology, for the owner's whole team."""
    lines = [
        "[[effect]]",
        'civilisation = "Owner"',
        'source_key = "0"',
        'source_text = "Team Castles work faster once the owner researches the technology"',
        'modelled = "yes"',
        'field = "production_time"',
        'operation = "multiply"',
        f"operand = {operand}",
        f"condition = {condition}",
    ]
    if technology is not None:
        lines.append(f"condition_technology = {technology}")
    if entities:
        lines.append(
            'condition_entities = [{ kind = "building", id = "109" }]',
        )
    lines += ['selector = [{ kind = "building", id = "82" }]', 'validated_by = "synthetic"', ""]
    return "\n".join(lines)


def _apply_multi(
    effect: effects.Effect, civilisation: str, context: effects.Context | None
) -> tuple[object, bool]:
    result = effects.apply_matched(
        (effect,),
        civilisation=civilisation,
        kind="building",
        id="82",
        field="production_time",
        value=100,
        context=context,
    )
    assert not isinstance(result, effects.EffectNotModelled)
    return result


def test_a_researched_and_team_effect_applies_to_a_teammate_whose_team_researched_it() -> None:
    (effect,) = effects.parse_effects_toml(_multi_condition_toml())
    team = frozenset({"Owner", "Mate"})
    reached = _apply_multi(
        effect, "Mate", effects.Context(team=team, team_researched=frozenset({"kasbah"}))
    )
    assert reached[0] == 80  # type: ignore[index]
    not_reached = _apply_multi(
        effect, "Mate", effects.Context(team=team, team_researched=frozenset({"other"}))
    )
    assert not_reached[0] == 100  # type: ignore[index]


def test_a_researched_and_team_effect_reads_team_researched_not_researched() -> None:
    """The technology belongs to the owner, not to the teammate queried, so the teammate's own
    `researched` set neither grants nor withholds it."""
    (effect,) = effects.parse_effects_toml(_multi_condition_toml())
    team = frozenset({"Owner", "Mate"})
    only_own = effects.Context(
        team=team, researched=frozenset({"other"}), team_researched=frozenset({"other"})
    )
    assert _apply_multi(effect, "Mate", only_own)[0] == 100  # type: ignore[index]
    only_team = effects.Context(
        team=team, researched=frozenset(), team_researched=frozenset({"kasbah"})
    )
    assert _apply_multi(effect, "Mate", only_team)[0] == 80  # type: ignore[index]


def test_a_researched_and_team_effect_does_not_reach_a_civilisation_off_the_owners_team() -> None:
    (effect,) = effects.parse_effects_toml(_multi_condition_toml())
    context = effects.Context(team=frozenset({"Stranger"}), team_researched=frozenset({"kasbah"}))
    assert _apply_multi(effect, "Stranger", context)[0] == 100  # type: ignore[index]


def test_a_researched_and_team_effect_raises_without_team_researched() -> None:
    (effect,) = effects.parse_effects_toml(_multi_condition_toml())
    with pytest.raises(effects.ContextRequired):
        _apply_multi(
            effect,
            "Mate",
            effects.Context(team=frozenset({"Owner", "Mate"}), researched=frozenset({"kasbah"})),
        )
    with pytest.raises(effects.ContextRequired):
        _apply_multi(effect, "Mate", None)


def test_a_researched_and_team_effect_raises_without_team_even_with_team_researched() -> None:
    (effect,) = effects.parse_effects_toml(_multi_condition_toml())
    with pytest.raises(effects.ContextRequired):
        _apply_multi(effect, "Mate", effects.Context(team_researched=frozenset({"kasbah"})))


def test_a_list_does_not_stop_at_the_first_condition_that_fails() -> None:
    """A query that reaches the effect without the input any one name needs raises, even when
    another name has already said no."""
    (effect,) = effects.parse_effects_toml(
        _multi_condition_toml('["age", "researched"]', operand="{ 1 = 0.5 }")
    )
    with pytest.raises(effects.ContextRequired):
        _apply_multi(effect, "Owner", effects.Context(age=2))


def test_an_age_and_researched_effect_needs_both_to_hold() -> None:
    (effect,) = effects.parse_effects_toml(
        _multi_condition_toml('["age", "researched"]', operand="{ 2 = 0.5 }")
    )
    held = effects.Context(age=2, researched=frozenset({"kasbah"}))
    assert _apply_multi(effect, "Owner", held)[0] == 50  # type: ignore[index]
    wrong_age = effects.Context(age=3, researched=frozenset({"kasbah"}))
    assert _apply_multi(effect, "Owner", wrong_age)[0] == 100  # type: ignore[index]
    not_researched = effects.Context(age=2, researched=frozenset())
    assert _apply_multi(effect, "Owner", not_researched)[0] == 100  # type: ignore[index]


def test_a_one_name_list_parses_to_the_same_effect_as_the_bare_name() -> None:
    (as_list,) = effects.parse_effects_toml(_multi_condition_toml('["researched"]'))
    (as_name,) = effects.parse_effects_toml(_multi_condition_toml('"researched"'))
    assert as_list == as_name
    assert as_name.conditions == ("researched",)


@pytest.mark.parametrize(
    ("condition", "technology", "entities", "reason"),
    [
        ("[]", None, False, "empty list"),
        ('["researched", "researched"]', '"kasbah"', False, "twice"),
        ('["age", "controlled"]', None, True, 'both "age" and "controlled"'),
        ('["team", "age"]', None, False, '"researched" alone'),
        ('["team", "controlled"]', None, True, '"researched" alone'),
        ('["team", "researched", "age"]', '"kasbah"', False, '"researched" alone'),
        ('["researched", "nonsense"]', '"kasbah"', False, "'nonsense'"),
        ('["researched", 3]', '"kasbah"', False, "3"),
        ("3", None, False, "string or a list"),
    ],
)
def test_a_condition_list_is_refused_at_parse_time(
    condition: str, technology: str | None, entities: bool, reason: str
) -> None:
    operand = "{ 1 = 0.5 }" if "age" in condition or "controlled" in condition else "0.8"
    with pytest.raises(effects.EffectsError, match=reason):
        effects.parse_effects_toml(
            _multi_condition_toml(
                condition, operand=operand, technology=technology, entities=entities
            )
        )


def test_condition_technology_is_still_required_for_researched_inside_a_list() -> None:
    with pytest.raises(effects.EffectsError):
        effects.parse_effects_toml(_multi_condition_toml(technology=None))
    with pytest.raises(effects.EffectsError):
        effects.parse_effects_toml(_multi_condition_toml('["team"]', technology='"kasbah"'))


# ------------------------------------------ remediation of PR #192: the review's six findings


def _age_effect_toml(
    operand: str, *, condition: str | None = None, operation: str = "set", entities: bool = False
) -> str:
    lines = [
        "[[effect]]",
        'civilisation = "Franks"',
        'source_key = "0"',
        'source_text = "synthetic: the age a unit requires"',
        'modelled = "yes"',
        'field = "age_requirement"',
        f'operation = "{operation}"',
        f"operand = {operand}",
    ]
    if condition is not None:
        lines.append(f"condition = {condition}")
    if entities:
        lines.append('condition_entities = [{ kind = "building", id = "109" }]')
    lines += [
        f'selector = [{{ kind = "unit", id = "{_PIKEMAN}" }}]',
        'validated_by = "synthetic"',
        "",
    ]
    return "\n".join(lines)


@pytest.mark.parametrize(
    ("operand", "condition", "entities"),
    [
        ("{ 0 = { food = 2 } }", '"controlled"', True),
        ("{ 0 = 9 }", '"controlled"', True),
        ("{ 0 = -3 }", '"controlled"', True),
        ("{ 0 = 0 }", '"controlled"', True),
        ("{ 0 = 2.5 }", '"controlled"', True),
        ("{ 0 = true }", '"controlled"', True),
        ("{ 2 = { food = 1 } }", '"age"', False),
        ("{ 2 = 9 }", '"age"', False),
        ("{ 2 = false }", '"age"', False),
        ("9", None, False),
        ("0", None, False),
        ("-1", None, False),
        ("true", None, False),
    ],
)
def test_an_age_requirement_value_must_be_a_whole_age_in_the_packs_range(
    operand: str, condition: str | None, entities: bool
) -> None:
    """Every value an `age_requirement` effect can answer is an age, 1 to 4: never a table, never a
    boolean, never a number outside the pack's ages, at the scalar `set` and in a table value."""
    with pytest.raises(effects.EffectsError):
        effects.parse_effects_toml(
            _age_effect_toml(operand, condition=condition, entities=entities)
        )


@pytest.mark.parametrize(
    ("operand", "condition", "entities"),
    [
        ("3", None, False),
        ("{ 0 = 4, 2 = 2 }", '"controlled"', True),
        ("{ 2 = 1, 3 = 4 }", '"age"', False),
    ],
)
def test_a_valid_age_requirement_value_still_parses(
    operand: str, condition: str | None, entities: bool
) -> None:
    (effect,) = effects.parse_effects_toml(
        _age_effect_toml(operand, condition=condition, entities=entities)
    )
    assert effect.operand is not None


def test_a_controlled_age_requirement_table_with_a_table_value_never_reaches_a_query() -> None:
    """It used to parse and raise `EffectsError` at query time; now it never parses."""
    with pytest.raises(effects.EffectsError, match="age"):
        effects.parse_effects_toml(
            _age_effect_toml("{ 0 = { food = 2 } }", condition='"controlled"', entities=True)
        )


def test_a_researched_and_team_effect_refuses_a_researched_the_team_set_does_not_hold() -> None:
    """`team_researched` includes the player's own: a `researched` it does not contain is a
    malformed input, as a `team` that omits the queried civilisation is."""
    (effect,) = effects.parse_effects_toml(_multi_condition_toml())
    team = frozenset({"Owner", "Mate"})
    with pytest.raises(ValueError, match="team_researched"):
        _apply_multi(
            effect,
            "Mate",
            effects.Context(
                team=team, researched=frozenset({"a"}), team_researched=frozenset({"b"})
            ),
        )


def test_a_researched_subset_of_team_researched_still_neither_grants_nor_withholds() -> None:
    (effect,) = effects.parse_effects_toml(_multi_condition_toml())
    team = frozenset({"Owner", "Mate"})
    own_included = effects.Context(
        team=team, researched=frozenset({"a"}), team_researched=frozenset({"a", "kasbah"})
    )
    assert _apply_multi(effect, "Mate", own_included)[0] == 80  # type: ignore[index]
    without = effects.Context(
        team=team, researched=frozenset({"kasbah"}), team_researched=frozenset({"kasbah", "x"})
    )
    assert _apply_multi(effect, "Mate", without)[0] == 80  # type: ignore[index]


def test_a_list_with_controlled_and_researched_parses_when_both_inputs_are_named() -> None:
    (effect,) = effects.parse_effects_toml(
        _multi_condition_toml('["controlled", "researched"]', operand="{ 1 = 0.5 }", entities=True)
    )
    assert effect.conditions == ("researched", "controlled")
    assert effect.condition_technology == "kasbah"


def test_condition_entities_is_required_by_controlled_inside_a_list() -> None:
    with pytest.raises(effects.EffectsError, match="condition_entities"):
        effects.parse_effects_toml(
            _multi_condition_toml('["controlled", "researched"]', operand="{ 1 = 0.5 }")
        )


def test_condition_entities_is_refused_without_controlled_inside_a_list() -> None:
    with pytest.raises(effects.EffectsError, match="condition_entities"):
        effects.parse_effects_toml(
            _multi_condition_toml('["age", "researched"]', operand="{ 1 = 0.5 }", entities=True)
        )


def test_the_order_a_condition_list_is_written_in_does_not_matter() -> None:
    """The names are stored in the vocabulary's documented order (age, researched, team,
    controlled), so both spellings are one effect and one error precedence."""
    (first,) = effects.parse_effects_toml(_multi_condition_toml('["team", "researched"]'))
    (second,) = effects.parse_effects_toml(_multi_condition_toml('["researched", "team"]'))
    assert first == second
    assert first.conditions == ("researched", "team")
    # `team` omits the queried civilisation (ValueError) while `team_researched` is absent
    # (ContextRequired): the same bad context gives the same error in either spelling.
    bad = effects.Context(team=frozenset({"Stranger"}))
    raised = []
    for effect in (first, second):
        with pytest.raises(Exception) as caught:
            _apply_multi(effect, "Mate", bad)
        raised.append((type(caught.value), str(caught.value)))
    assert raised[0] == raised[1]
    assert raised[0][0] is effects.ContextRequired
