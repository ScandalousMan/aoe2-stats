"""The starting state of data-model section 3 (FR-026, research R4).

Per participant: the decoded stockpiles, the starting age, the starting objects and the population
limit. **None is the gap**: an age-dependent value that is not confirmed is never a guess.

- `resources` are the `starting-attributes` event's values, published as decoded. A participant
  with no such event (an AI, or one the decoder skipped) has `resources=None`: a gap.
- `age` comes from the lobby's starting-age preset through `CONFIRMED_AGE_PRESETS`, which holds
  only what owner reading O4 has confirmed (empty until it is answered; this module never answers
  an owner reading). An unconfirmed preset gaps `age` and `objects`.
- `objects` come from `Snapshot.starting_objects_for`. A non-empty `open` answer is a gap, never a
  default, and a bonus row alone is never a full starting set: the answer is used only when the
  snapshot carries the table, the preset is confirmed, nothing is open for the pair, a `baseline`
  row applies, and every stated row applies unconditionally. The result is the baseline plus the
  matching bonus rows.
- `population_limit` is the lobby's, independent of the age preset.

The lobby-and-civilisation derivation of the stockpiles (`derive_starting_resources`) is a
cross-check, never a fallback. The knowledge base states no lobby preset's stockpile, so the
derivation is a gap (`None`) for every participant until a source states it, and a gap is not
compared: it breaches nothing and confirms nothing.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Final

from aoe2stats_knowledge import effects
from aoe2stats_knowledge.gaps import KnowledgeGap
from aoe2stats_knowledge.snapshot import Snapshot, snapshot_for

RESOURCES: Final[tuple[str, ...]] = ("food", "wood", "stone", "gold")

#: Lobby starting-age preset id (as `match-started` carries it) to the age 1 to 4, confirmed by
#: owner reading O4. Empty until O4 is answered.
CONFIRMED_AGE_PRESETS: Final[Mapping[str, int]] = {}

#: A derivation of the stockpiles per slot; `None` for a slot is a gap.
Derivation = Mapping[int, Mapping[str, int] | None]


@dataclass(frozen=True, slots=True)
class StartingState:
    """One participant's starting state (data-model section 3); `None` is a gap."""

    resources: Mapping[str, int] | None
    age: int | None
    objects: Mapping[str, int] | None
    population_limit: int


def _events(canonical: Mapping[str, Any], kind: str) -> list[Mapping[str, Any]]:
    return [event for event in canonical["events"] if event["kind"] == kind]


def _match_started(canonical: Mapping[str, Any]) -> Mapping[str, Any]:
    started = _events(canonical, "match-started")
    if len(started) != 1:
        raise ValueError(f"expected exactly one match-started event, found {len(started)}")
    payload: Mapping[str, Any] = started[0]["payload"]
    return payload


def _decoded_resources(canonical: Mapping[str, Any]) -> dict[int, dict[str, int]]:
    return {
        int(event["participant"]): {
            name: int(event["payload"]["values"][name]) for name in RESOURCES
        }
        for event in _events(canonical, "starting-attributes")
    }


def _resolve_snapshot(build: object) -> Snapshot | None:
    if not isinstance(build, int):
        return None
    resolved = snapshot_for(build)
    return None if isinstance(resolved, KnowledgeGap) else resolved


def _objects(
    snapshot: Snapshot | None, civilisation: str | None, preset: str, confirmed: bool
) -> dict[str, int] | None:
    if (
        snapshot is None
        or civilisation is None
        or not confirmed
        or not snapshot.has_starting_objects
    ):
        return None
    answer = snapshot.starting_objects_for(civilisation, preset)
    if answer.open or not answer.has_baseline:
        return None
    if any(row.applies != "always" for row in answer.added):
        return None
    counts: dict[str, int] = {}
    for row in answer.added:
        counts[row.object] = counts.get(row.object, 0) + row.count
    return counts


def starting_states(
    canonical: Mapping[str, Any],
    *,
    confirmed_age_presets: Mapping[str, int] | None = None,
    snapshot: Snapshot | None = None,
) -> dict[int, StartingState]:
    """The starting state of each participant slot of `canonical`.

    `confirmed_age_presets` stands for owner reading O4 (default `CONFIRMED_AGE_PRESETS`);
    `snapshot` overrides the build's resolved snapshot (default `snapshot_for(build)`).
    """
    started = _match_started(canonical)
    presets = CONFIRMED_AGE_PRESETS if confirmed_age_presets is None else confirmed_age_presets
    lobby = started["lobby_presets"]
    age_preset = str(lobby["starting_age_id"])
    age = presets.get(age_preset)
    resolved = snapshot if snapshot is not None else _resolve_snapshot(started.get("build"))
    names = effects.civilisation_id_names(resolved.directory) if resolved is not None else {}
    decoded = _decoded_resources(canonical)
    limit = int(lobby["population_limit"])
    states: dict[int, StartingState] = {}
    for participant in started["participants"]:
        slot = int(participant["slot"])
        states[slot] = StartingState(
            resources=decoded.get(slot),
            age=age,
            objects=_objects(
                resolved, names.get(int(participant["civilisation"])), age_preset, age is not None
            ),
            population_limit=limit,
        )
    return states


def derive_starting_resources(canonical: Mapping[str, Any]) -> dict[int, dict[str, int] | None]:
    """The lobby-and-civilisation derivation of each slot's stockpiles; `None` is a gap.

    It reads the lobby's starting-resources preset and the participant's civilisation through the
    knowledge base. The knowledge base states no preset's stockpile and no civilisation's stockpile
    change as a number it can apply (the bonuses are text without an entity), so every slot is a
    gap today. No constant stands in for the missing statement.
    """
    started = _match_started(canonical)
    return {int(p["slot"]): None for p in started["participants"]}


def starting_resource_records(
    canonical: Mapping[str, Any],
    *,
    derivation: Callable[[Mapping[str, Any]], Derivation] = derive_starting_resources,
) -> list[dict[str, Any]]:
    """One `starting` record per participant and resource, for the `starting-resources-agree`
    check. A slot whose derivation is a gap yields no record, and a slot with no decoded
    `starting-attributes` event is never iterated: nothing is compared. `derivation`
    replaces the knowledge-base derivation (used to test the check)."""
    derived = derivation(canonical)
    records: list[dict[str, Any]] = []
    for slot, decoded in _decoded_resources(canonical).items():
        stated = derived.get(slot)
        if stated is None:
            continue
        for name in RESOURCES:
            records.append(
                {
                    "kind": "starting",
                    "participant": slot,
                    "resource": name,
                    "decoded": decoded[name],
                    "derived": stated[name],
                }
            )
    return records
