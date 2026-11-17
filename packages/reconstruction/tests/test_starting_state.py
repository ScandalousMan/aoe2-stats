"""The starting state of data-model section 3 (FR-026), test first: T927 must make these pass.

Assumed API of `aoe2stats_reconstruction.starting` (T927 must provide it):

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
- `derive_starting_resources(canonical) -> dict[int, dict[str, int]]`: the lobby-and-civilisation
  derivation of the starting stockpiles per slot, through the knowledge base.
- `starting_resource_records(canonical) -> list[dict]`: one `starting` record per participant and
  resource (`participant`, `resource`, `decoded`, `derived`), the shape the
  `starting-resources-agree` check of `invariants.py` reads.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from aoe2stats_reconstruction.invariants import Invariant, InvariantBreach, check_invariants

_REPLAYS = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "replays"
_RECORDINGS = sorted(_REPLAYS.glob("*.canonical.json"))
_RESOURCES = ("food", "wood", "stone", "gold")
_XFAIL = pytest.mark.xfail(strict=True, reason="T927 not implemented yet")


def _load(path: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return document


def _events(document: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return [e for e in document["events"] if e["kind"] == kind]


def test_the_committed_recordings_are_found() -> None:
    assert len(_RECORDINGS) == 3


@_XFAIL
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
        assert state.objects is not None
        assert state.objects, "a confirmed preset has starting objects"
        assert all(
            isinstance(n, str) and isinstance(c, int) and c > 0 for n, c in state.objects.items()
        )


@_XFAIL
@pytest.mark.parametrize("path", _RECORDINGS, ids=lambda p: p.name)
def test_decoded_resources_agree_with_the_derivation(path: Path) -> None:
    from aoe2stats_reconstruction.starting import (
        derive_starting_resources,
        starting_resource_records,
    )

    document = _load(path)
    derived = derive_starting_resources(document)
    for event in _events(document, "starting-attributes"):
        values = event["payload"]["values"]
        assert {name: values[name] for name in _RESOURCES} == derived[event["participant"]]

    records = starting_resource_records(document)
    assert records
    assert {r["resource"] for r in records} == set(_RESOURCES)
    assert all(r["kind"] == "starting" and r["decoded"] == r["derived"] for r in records)
    assert check_invariants(records) is None


@_XFAIL
@pytest.mark.parametrize("path", _RECORDINGS, ids=lambda p: p.name)
def test_a_planted_disagreement_is_the_starting_resources_breach(path: Path) -> None:
    from aoe2stats_reconstruction.starting import starting_resource_records

    document = copy.deepcopy(_load(path))
    planted = _events(document, "starting-attributes")[0]
    slot = planted["participant"]
    original = planted["payload"]["values"]["wood"]
    planted["payload"]["values"]["wood"] = original + 1

    with pytest.raises(InvariantBreach) as raised:
        check_invariants(starting_resource_records(document))
    assert raised.value.invariant is Invariant.STARTING_RESOURCES_AGREE
    assert raised.value.participant == slot
    assert raised.value.datum == "wood"
    assert raised.value.value == original + 1


@_XFAIL
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
