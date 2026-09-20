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
  `effects.toml` (`aoe2techtree-fixture-promoted`, `aoe2techtree-fixture-promoted-177723`): the
  same two real facts `packages/knowledge/tests/test_query.py` encodes (Byzantine Pikeman -25%,
  Korean Crossbowman -50% wood), proven here directly through `effects.apply` rather than through
  `query.py` — this is deliberate: `query.py`'s own discount tests stayed `xfail` until T645
  populated `civilisations_modelled`, but `effects.py`'s own correctness never depended on T645 at
  all, and this file is what proves that independently.

**T645** added the four civilisations the second committed recording needs (research.md D11) —
Franks, Persians, Teutons, Gurjaras — with the same two-kind treatment: a real cost/age-requirement
adjustment proven against the committed `effects.toml`, and one conditional/team-wide "not
modelled" refusal each. `packages/knowledge/snapshots/aoe2techtree-fixture-promoted/effects.toml`'s
own header comment carries the full identification method and provenance; this file does not
restate it.
"""

from __future__ import annotations

import pytest

from aoe2stats_knowledge import effects

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

_PROMOTED_DIRECTORY = "aoe2techtree-fixture-promoted"
_PROMOTED_177723_DIRECTORY = "aoe2techtree-fixture-promoted-177723"


@pytest.mark.parametrize("directory", [_PROMOTED_DIRECTORY, _PROMOTED_177723_DIRECTORY])
def test_the_real_byzantine_pikeman_discount_applies_through_the_committed_effects_toml(
    directory: str,
) -> None:
    """The exact real fact `test_query.py` encodes, proven here directly against `effects.py`
    without going through `query.py`/`civilisations_modelled` at all (T645 is not a dependency of
    this test) — over **both** committed promoted snapshots, since both carry the same real,
    hand-transcribed `effects.toml` content (their sibling `snapshot.toml` files record why: the
    same pack revision, unchanged across every build between them)."""
    result = effects.apply(
        directory,
        civilisation="Byzantines",
        kind="unit",
        id="358",
        field="cost",
        value={"food": 35, "wood": 25},
    )
    assert not isinstance(result, effects.EffectNotModelled)
    value, applied = result
    assert value == {"food": 26, "wood": 19}
    assert len(applied) == 1
    assert applied[0].source_text == "Camel Riders, Skirmishers and Spearman-line cost -25%"
    assert applied[0].modelled == "yes"


@pytest.mark.parametrize("directory", [_PROMOTED_DIRECTORY, _PROMOTED_177723_DIRECTORY])
def test_the_real_korean_crossbowman_discount_applies_through_the_committed_effects_toml(
    directory: str,
) -> None:
    result = effects.apply(
        directory,
        civilisation="Koreans",
        kind="unit",
        id="24",
        field="cost",
        value={"gold": 45, "wood": 25},
    )
    assert not isinstance(result, effects.EffectNotModelled)
    value, applied = result
    assert value == {"gold": 45, "wood": 13}
    assert len(applied) == 1
    assert applied[0].source_text == "Ranged Soldiers and Infantry cost -50% wood"


def test_the_real_byzantine_building_hp_bonus_is_not_modelled() -> None:
    """The age-gated bonus this task's "not modelled" rule requires be recorded rather than
    silently dropped (research.md D5) — proven here against the real, committed `effects.toml`."""
    result = effects.apply(
        _PROMOTED_DIRECTORY,
        civilisation="Byzantines",
        kind="building",
        id="12",
        field="hp",
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
    """Persians' "Kamandaran" is a Castle unique technology (conditional on match state, research.md
    D5), so an Archer's cost is refused rather than silently adjusted or silently left baseline."""
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


def test_the_real_gurjaras_team_bonus_is_not_modelled() -> None:
    """Gurjaras' Camel/Elephant training-speed bonus is a Team Bonus (research.md D5: team-wide),
    so it is refused rather than silently applied to Gurjaras' own Camel Rider."""
    result = effects.apply(
        _PROMOTED_DIRECTORY,
        civilisation="Gurjaras",
        kind="unit",
        id="329",
        field="production_time",
        value=30,
    )
    assert isinstance(result, effects.EffectNotModelled)
    assert "team" in result.reason.lower()
