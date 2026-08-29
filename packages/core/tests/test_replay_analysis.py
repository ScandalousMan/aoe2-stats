"""The extraction-Protocol value objects: shape only, per
`specs/003-player-search-match-analysis/contracts/analysis.md`'s `MatchTimeline` and
`ParticipantTimeline`.

`aoe2stats_core.replay.analysis` does not exist until T352 lands, so every test below imports it
inside its own body rather than at module scope — a module-scope import of a module that does not
exist yet is a collection error that takes the whole workspace suite down, not one failing test —
and carries `@pytest.mark.xfail(strict=True, reason="T352 not implemented yet")`. `strict=True` is
what forces T352 to remove each marker rather than leaving a stale one that would hide a
regression.

Field introspection, not construction: what is asserted is the *shape* of the dataclass, via
`dataclasses.fields`, so a field that should not exist cannot be smuggled past a test that only
ever constructs instances and reads the fields it already expects.

The negative half is the point (FR-043b, contract's "Every name in there is load-bearing"): a
`.aoe2record` is a command log, not a state log, so resources and villager population are
recoverable only by partial re-simulation — a separate, later feature. `MatchTimeline` and
`ParticipantTimeline` must carry no field named for a resource and no field named `villagers` or
`villagers_trained`; the correct field, `villagers_ordered`, counts training *commands* net of
observed cancellations, which is a different quantity from a population and the contract insists
the name say so. A field that does not exist cannot be populated by a well-meaning later change —
this is a test for an absence, so it has to test for the absence directly rather than merely fail
to test for the presence.
"""

from __future__ import annotations

import dataclasses

import pytest

# The exact field sets from contracts/analysis.md. Listed here, not derived from the module under
# test, so a change to the contract and a change to the implementation are two edits that this
# file makes visible as two different failures rather than one silent agreement.
_MATCH_TIMELINE_FIELDS = {
    "engine_name",
    "engine_version",
    "point_of_view_profile_id",
    "world_time_ms",
    "participants",
}

_PARTICIPANT_TIMELINE_FIELDS = {
    "profile_id",
    "player_number",
    "civ_id",
    "resolved_team_id",
    "builds",
    "trainings",
    "researches",
    "age_up_commands",
    "villagers_ordered",
    "actions",
    "actions_per_minute",
    "resigned_at_ms",
}

# Substrings that would name a resource or a reconstructed quantity — checked case-insensitively
# against every field name, not just matched against a short list of exact names, because the
# misreading FR-043b exists to prevent is a synonym away at all times ("gold_collected",
# "stone_stockpile", "wood_gathered" would each pass an exact-name check and fail this one).
_FORBIDDEN_SUBSTRINGS = ("wood", "food", "gold", "stone", "resource", "population")

# The two names the contract calls out by name: forbidden regardless of the substring check above,
# because neither contains a resource word and both are exactly the misreading FR-043b is about.
_FORBIDDEN_EXACT_NAMES = {"villagers", "villagers_trained"}


def _field_names(cls: type) -> set[str]:
    return {f.name for f in dataclasses.fields(cls)}


@pytest.mark.xfail(strict=True, reason="T352 not implemented yet")
def test_match_timeline_carries_exactly_the_contract_fields() -> None:
    from aoe2stats_core.replay.analysis import MatchTimeline

    assert _field_names(MatchTimeline) == _MATCH_TIMELINE_FIELDS


@pytest.mark.xfail(strict=True, reason="T352 not implemented yet")
def test_participant_timeline_carries_exactly_the_contract_fields() -> None:
    from aoe2stats_core.replay.analysis import ParticipantTimeline

    assert _field_names(ParticipantTimeline) == _PARTICIPANT_TIMELINE_FIELDS


@pytest.mark.xfail(strict=True, reason="T352 not implemented yet")
def test_match_timeline_has_no_field_named_for_a_resource_or_a_reconstructed_quantity() -> None:
    from aoe2stats_core.replay.analysis import MatchTimeline

    names = _field_names(MatchTimeline)
    for name in names:
        lowered = name.lower()
        for forbidden in _FORBIDDEN_SUBSTRINGS:
            assert forbidden not in lowered, (
                f"MatchTimeline.{name} names a resource or reconstructed quantity (FR-043b)"
            )
    assert names.isdisjoint(_FORBIDDEN_EXACT_NAMES)


@pytest.mark.xfail(strict=True, reason="T352 not implemented yet")
def test_participant_timeline_has_no_field_named_for_a_resource() -> None:
    """FR-043b: 'No resources, anywhere, and no reconstructed quantity of any kind.' A
    `.aoe2record` is a command log, not a state log — resources are recoverable only by partial
    re-simulation, a separate feature this one must not anticipate by naming a field for it."""
    from aoe2stats_core.replay.analysis import ParticipantTimeline

    names = _field_names(ParticipantTimeline)
    for name in names:
        lowered = name.lower()
        for forbidden in _FORBIDDEN_SUBSTRINGS:
            assert forbidden not in lowered, (
                f"ParticipantTimeline.{name} names a resource or reconstructed quantity (FR-043b)"
            )


@pytest.mark.xfail(strict=True, reason="T352 not implemented yet")
def test_participant_timeline_has_no_villagers_or_villagers_trained_field() -> None:
    """FR-043b, in the contract's own words: '"villagers_ordered", not "villagers".' The field
    that exists counts training *commands* net of observed cancellations — what the player ordered
    and did not cancel — never a population. Naming it `villagers` or `villagers_trained` is the
    misreading this test exists to make structurally impossible: a field that does not exist
    cannot be populated by a well-meaning later change, however the name is spelled."""
    from aoe2stats_core.replay.analysis import ParticipantTimeline

    names = _field_names(ParticipantTimeline)
    assert names.isdisjoint(_FORBIDDEN_EXACT_NAMES)
    # The correct field is present and is the only villager-related name this dataclass carries.
    assert "villagers_ordered" in names
    villager_named = {n for n in names if "villager" in n.lower()}
    assert villager_named == {"villagers_ordered"}


@pytest.mark.xfail(strict=True, reason="T352 not implemented yet")
def test_both_value_objects_are_frozen() -> None:
    """Immutable, like `ReplayValidationResult` beside it — a published analysis is a fact about
    one parse, not a value a caller should be able to mutate after the fact."""
    from aoe2stats_core.replay.analysis import MatchTimeline, ParticipantTimeline

    assert dataclasses.is_dataclass(MatchTimeline)
    assert dataclasses.is_dataclass(ParticipantTimeline)

    match_params = MatchTimeline.__dataclass_params__  # type: ignore[attr-defined]
    participant_params = ParticipantTimeline.__dataclass_params__  # type: ignore[attr-defined]
    assert match_params.frozen
    assert participant_params.frozen
