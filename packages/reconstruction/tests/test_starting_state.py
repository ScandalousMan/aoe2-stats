"""The starting state of data-model section 3 (FR-026).

API of `aoe2stats_reconstruction.starting` (T927):

- `starting_states(canonical, *, confirmed_age_presets=None) -> dict[int, StartingState]`, keyed by
  participant slot. `canonical` is a parsed `*.canonical.json` document. `confirmed_age_presets`
  maps a lobby starting-age preset id (a string, as in `match-started`) to an age 1 to 4; it stands
  for owner reading O4 and defaults to the confirmed mapping the module ships (empty until O4 is
  answered).
- `StartingState` has `resources` (`{"food","wood","stone","gold"}` to int, the decoded values
  from the `starting-attributes` event), `age` (int 1 to 4, or `None` as a gap), `objects`
  (`{name: count}` with count a positive int, or `None` as a gap) and `population_limit` (int from
  the lobby preset, age-independent). `None` is the gap: an age-dependent value that is not
  confirmed is never a guess.
- `derive_starting_resources(canonical) -> dict[int, dict[str, int] | None]`: the
  lobby-and-civilisation derivation of the starting stockpiles per slot, through the knowledge
  base. The knowledge base states no preset's stockpile, so every slot is `None` (a gap) today.
- `starting_resource_records(canonical) -> list[dict]`: one `starting` record per participant and
  resource (`participant`, `resource`, `decoded`, `derived`), the shape the
  `starting-resources-agree` check of `invariants.py` reads. A slot whose derivation is a gap yields
  no record.

`starting_states` and `starting_resource_records` also accept `snapshot=` and `derivation=` seams
so the tests can state a table or a derivation the installed knowledge does not hold.
"""

from __future__ import annotations

import copy
import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest

from aoe2stats_knowledge.snapshot import (
    StartingObject,
    load_snapshot,
)
from aoe2stats_reconstruction.invariants import Invariant, InvariantBreach, check_invariants

_REPLAYS = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "replays"
_RECORDINGS = sorted(_REPLAYS.glob("*.canonical.json"))
_RESOURCES = ("food", "wood", "stone", "gold")


def _load(path: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return document


def _events(document: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return [e for e in document["events"] if e["kind"] == kind]


def _stated_derivation(document: dict[str, Any]) -> Any:
    """A derivation standing in for a knowledge base that states the stockpiles: it is computed
    from this document's unplanted decoded values, so it is the test's, not a constant."""
    stated = {
        e["participant"]: {n: e["payload"]["values"][n] for n in _RESOURCES}
        for e in _events(document, "starting-attributes")
    }
    return lambda _canonical: stated


def test_the_committed_recordings_are_found() -> None:
    assert len(_RECORDINGS) == 3


@pytest.mark.parametrize("path", _RECORDINGS, ids=lambda p: p.name)
def test_the_starting_state_of_each_recording(path: Path) -> None:
    from aoe2stats_reconstruction.starting import starting_states

    document = _load(path)
    started = _events(document, "match-started")[0]["payload"]
    slots = [p["slot"] for p in started["participants"]]
    # Preset 'confirmed' only for this test so that age-dependent values are asked for.
    preset = started["lobby_presets"]["starting_age_id"]
    states = starting_states(document, confirmed_age_presets={preset: 1})

    assert sorted(states) == sorted(slots)
    decoded = {
        e["participant"]: e["payload"]["values"] for e in _events(document, "starting-attributes")
    }
    for slot, state in states.items():
        assert state.resources == {name: decoded[slot][name] for name in _RESOURCES}
        assert state.age == 1
        assert state.population_limit == int(started["lobby_presets"]["population_limit"])
        # AMENDED (T927): T926 asserted a non-empty `objects` here, written before T925's table
        # existed. The table's baseline is an open owner request (O8.1) and FR-026 forbids a
        # default, so `objects` is a gap while the table has open rows or the build has no table.
        assert state.objects is None


@pytest.mark.parametrize("path", _RECORDINGS, ids=lambda p: p.name)
def test_the_derivation_is_a_gap_until_the_knowledge_base_states_a_stockpile(path: Path) -> None:
    from aoe2stats_reconstruction.starting import (
        derive_starting_resources,
        starting_resource_records,
    )

    document = _load(path)
    derived = derive_starting_resources(document)
    slots = {e["participant"] for e in _events(document, "starting-attributes")}
    # Not vacuous: every slot is named and each is an explicit gap, so nothing is "agreed".
    assert set(derived) == slots
    assert all(value is None for value in derived.values())
    assert starting_resource_records(document) == []


@pytest.mark.parametrize("path", _RECORDINGS, ids=lambda p: p.name)
def test_decoded_resources_agree_with_a_stated_derivation(path: Path) -> None:
    from aoe2stats_reconstruction.starting import starting_resource_records

    document = _load(path)
    records = starting_resource_records(document, derivation=_stated_derivation(document))
    assert records
    assert {r["resource"] for r in records} == set(_RESOURCES)
    assert all(r["kind"] == "starting" and r["decoded"] == r["derived"] for r in records)
    assert check_invariants(records) is None


@pytest.mark.parametrize("path", _RECORDINGS, ids=lambda p: p.name)
def test_a_planted_disagreement_is_the_starting_resources_breach(path: Path) -> None:
    from aoe2stats_reconstruction.starting import starting_resource_records

    original_document = _load(path)
    document = copy.deepcopy(original_document)
    planted = _events(document, "starting-attributes")[0]
    slot = planted["participant"]
    original = planted["payload"]["values"]["wood"]
    planted["payload"]["values"]["wood"] = original + 1

    with pytest.raises(InvariantBreach) as raised:
        check_invariants(
            starting_resource_records(document, derivation=_stated_derivation(original_document))
        )
    assert raised.value.invariant is Invariant.STARTING_RESOURCES_AGREE
    assert raised.value.participant == slot
    assert raised.value.datum == "wood"
    assert raised.value.value == original + 1


@pytest.mark.parametrize("path", _RECORDINGS, ids=lambda p: p.name)
def test_an_unconfirmed_age_preset_gaps_every_age_dependent_value(path: Path) -> None:
    from aoe2stats_reconstruction.starting import starting_states

    document = _load(path)
    started = _events(document, "match-started")[0]["payload"]
    states = starting_states(document, confirmed_age_presets={})

    assert sorted(states) == sorted(p["slot"] for p in started["participants"])
    for state in states.values():
        assert state.age is None
        assert state.objects is None
        # What does not depend on the age preset is still known, and never gapped by contagion.
        assert set(state.resources) == set(_RESOURCES)
        assert state.population_limit == int(started["lobby_presets"]["population_limit"])


def _table_snapshot(rows: tuple[StartingObject, ...], *, open_rows: bool) -> Any:
    """The starting-objects snapshot with its rows replaced: a synthetic table, never installed."""
    real = load_snapshot("aoe2techtree-188329-starting-objects")
    assert real.starting_objects_open, "the installed table still owes the owner its baseline"
    return dataclasses.replace(
        real,
        starting_objects=rows,
        starting_objects_open=real.starting_objects_open if open_rows else (),
    )


def _row(civilisation: str, count: int, *, role: str = "bonus") -> StartingObject:
    return StartingObject(
        civilisation=civilisation,
        role=role,
        preset="any",
        kind="unit",
        object="Villager",
        count=count,
        applies="always",
        source_key="synthetic",
        source_text="synthetic row, a test's own",
        read_on="2026-11-17",
        unit_id="83",
    )


def test_open_rows_gap_the_objects_even_when_the_age_preset_is_confirmed() -> None:
    from aoe2stats_reconstruction.starting import starting_states

    document = _load(_RECORDINGS[0])
    preset = _events(document, "match-started")[0]["payload"]["lobby_presets"]["starting_age_id"]
    names = _civilisation_names(document)
    rows = tuple(_row(name, 3) for name in names.values())
    snapshot = _table_snapshot(rows, open_rows=True)
    states = starting_states(document, confirmed_age_presets={preset: 1}, snapshot=snapshot)
    assert all(state.objects is None for state in states.values())


def test_a_bonus_only_table_with_no_open_rows_is_a_gap() -> None:
    from aoe2stats_reconstruction.starting import starting_states

    document = _load(_RECORDINGS[0])
    preset = _events(document, "match-started")[0]["payload"]["lobby_presets"]["starting_age_id"]
    names = _civilisation_names(document)
    snapshot = _table_snapshot(tuple(_row(name, 3) for name in names.values()), open_rows=False)
    states = starting_states(document, confirmed_age_presets={preset: 1}, snapshot=snapshot)
    # A bonus states what is added, never the full set: without a baseline it is a gap.
    assert all(state.objects is None for state in states.values())


def test_a_baseline_row_plus_a_bonus_row_gives_the_sum() -> None:
    from aoe2stats_reconstruction.starting import starting_states

    document = _load(_RECORDINGS[0])
    preset = _events(document, "match-started")[0]["payload"]["lobby_presets"]["starting_age_id"]
    names = _civilisation_names(document)
    rows = (_row("*", 3, role="baseline"), *(_row(name, 2) for name in names.values()))
    snapshot = _table_snapshot(rows, open_rows=False)
    states = starting_states(document, confirmed_age_presets={preset: 1}, snapshot=snapshot)
    assert all(state.objects == {"Villager": 5} for state in states.values())
    # An unconfirmed preset still gaps them, whatever the table says.
    gapped = starting_states(document, confirmed_age_presets={}, snapshot=snapshot)
    assert all(state.objects is None for state in gapped.values())
    # Open rows still gap them, baseline or not.
    open_snapshot = _table_snapshot(rows, open_rows=True)
    held = starting_states(document, confirmed_age_presets={preset: 1}, snapshot=open_snapshot)
    assert all(state.objects is None for state in held.values())


def _two_player_document(first: tuple[int, int], second: tuple[int, int]) -> dict[str, Any]:
    """The first recording with its two participants set to (civilisation id, team) pairs."""
    document = copy.deepcopy(_load(_RECORDINGS[0]))
    started = _events(document, "match-started")[0]["payload"]
    assert len(started["participants"]) == 2
    for participant, (civilisation, team) in zip(
        started["participants"], (first, second), strict=True
    ):
        participant["civilisation"] = civilisation
        participant["team"] = team
    return document


def _team_row_snapshot() -> Any:
    team_row = dataclasses.replace(_row("Incas", 1), object="Llama", applies="team")
    return _table_snapshot((_row("*", 3, role="baseline"), team_row), open_rows=False)


_FRANKS, _INCAS = 2, 21


def test_a_teammate_of_a_team_bonus_civilisation_is_a_gap() -> None:
    from aoe2stats_reconstruction.starting import starting_states

    document = _two_player_document((_INCAS, 2), (_FRANKS, 2))
    started = _events(document, "match-started")[0]["payload"]
    preset = started["lobby_presets"]["starting_age_id"]
    states = starting_states(
        document, confirmed_age_presets={preset: 1}, snapshot=_team_row_snapshot()
    )
    assert states[1].objects is None  # the Inca: its own row is not unconditional
    assert states[2].objects is None  # the Frank: the Inca's team row would reach it


def test_a_participant_on_a_team_without_a_team_bonus_civilisation_gets_the_baseline() -> None:
    from aoe2stats_reconstruction.starting import starting_states

    document = _two_player_document((_INCAS, 2), (_FRANKS, 3))
    started = _events(document, "match-started")[0]["payload"]
    preset = started["lobby_presets"]["starting_age_id"]
    states = starting_states(
        document, confirmed_age_presets={preset: 1}, snapshot=_team_row_snapshot()
    )
    assert states[1].objects is None
    assert states[2].objects == {"Villager": 3}


@pytest.mark.parametrize("path", _RECORDINGS, ids=lambda p: p.name)
def test_a_participant_without_a_starting_attributes_event_has_a_resource_gap(
    path: Path,
) -> None:
    from aoe2stats_reconstruction.starting import starting_resource_records, starting_states

    document = copy.deepcopy(_load(path))
    dropped = _events(document, "starting-attributes")[0]
    slot = dropped["participant"]
    document["events"].remove(dropped)
    started = _events(document, "match-started")[0]["payload"]
    assert slot in [p["slot"] for p in started["participants"]]

    states = starting_states(document)
    assert sorted(states) == sorted(p["slot"] for p in started["participants"])
    assert states[slot].resources is None
    for other, state in states.items():
        if other == slot:
            continue
        kept = next(
            e for e in _events(document, "starting-attributes") if e["participant"] == other
        )
        assert state.resources == {n: kept["payload"]["values"][n] for n in _RESOURCES}
    records = starting_resource_records(document, derivation=_full_derivation(document, slot))
    assert slot not in {r["participant"] for r in records}


def _full_derivation(document: dict[str, Any], missing: int) -> Any:
    """A derivation that states every participant, including the one with no decoded side."""
    started = _events(document, "match-started")[0]["payload"]
    stated = {p["slot"]: dict.fromkeys(_RESOURCES, 100) for p in started["participants"]}
    assert missing in stated
    return lambda _canonical: stated


def _civilisation_names(document: dict[str, Any]) -> dict[int, str]:
    from aoe2stats_knowledge import effects

    directory = "aoe2techtree-188329-starting-objects"
    raw = effects.civilisation_id_names(directory)
    participants = _events(document, "match-started")[0]["payload"]["participants"]
    return {p["slot"]: raw[p["civilisation"]] for p in participants}
