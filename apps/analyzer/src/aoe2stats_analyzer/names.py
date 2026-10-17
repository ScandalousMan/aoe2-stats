"""The names a published analysis document's identifiers resolve to (T709).

**What it answers.** The stored document carries technology, unit and building ids and no names
(`contracts/analysis.md`). `GET /api/matches/{game_id}/analysis` serves it beside a `names` table
built here: for each id the document references, the display name the knowledge snapshot **the
document itself names** gives it, or `None`.

**Never the nearest snapshot (FR-027).** The snapshot is the one whose digest equals
`identity.knowledge.digest`, matched exactly against the loaded snapshots
(`aoe2stats_knowledge.labels`). It is not resolved from the build, so a knowledge refresh that has
since promoted a second snapshot for the same build cannot change what an old analysis shows. A
document with no `identity.knowledge`, with the explicit `{"absent": ...}` record, or naming a
digest no loaded snapshot has, resolves every id to `None`; so does an id its snapshot does not
name. `None` is the wire's "unresolved", and nothing in this module invents a name.

**Which ids.** Exactly the ones the page renders: every participant's `age_up_commands` keys
and `researches[].technology_id` (technologies), `builds[].building_id` (buildings) and
`trainings[].unit_id` (units). A training's `building_id` is the producing building and the page
shows no name for it, so it is not looked up.

**On the API's request path (FR-049).** The API imports this module lazily, from the analysis
route. Like `staleness.py`, what it adds to a request is a cached read of the installed snapshot
tree: nothing is fetched, nothing is parsed from a recording, no engine is loaded (importing this
module loads neither `aoe2rec_py` nor `extract.py`), and the capture budget is untouched. It reads
the document the route has already read; it does no analysis. `tests/architecture/
test_feature_006_boundaries.py` allows that one import from that one file.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from aoe2stats_knowledge.labels import label_in_snapshot

#: The three kinds `rules.json` keys its entities by, in the order the wire lists them.
KINDS: tuple[str, ...] = ("technology", "unit", "building")


def _ids(values: Iterable[Any]) -> set[int]:
    return {value for value in values if isinstance(value, int) and not isinstance(value, bool)}


def _participants(document: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    participants = document.get("participants")
    if not isinstance(participants, list):
        return []
    return [entry for entry in participants if isinstance(entry, Mapping)]


def _list_of_mappings(participant: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    events = participant.get(key)
    if not isinstance(events, list):
        return []
    return [event for event in events if isinstance(event, Mapping)]


def referenced_ids(document: Mapping[str, Any]) -> dict[str, set[int]]:
    """Every id the document references, by entity kind (module docstring, "Which ids")."""
    technologies: set[int] = set()
    units: set[int] = set()
    buildings: set[int] = set()
    for participant in _participants(document):
        age_ups = participant.get("age_up_commands")
        if isinstance(age_ups, Mapping):
            for key in age_ups:
                if isinstance(key, str) and key.isdecimal():
                    technologies.add(int(key))
        technologies |= _ids(
            event.get("technology_id") for event in _list_of_mappings(participant, "researches")
        )
        units |= _ids(event.get("unit_id") for event in _list_of_mappings(participant, "trainings"))
        buildings |= _ids(
            event.get("building_id") for event in _list_of_mappings(participant, "builds")
        )
    return {"technology": technologies, "unit": units, "building": buildings}


def _knowledge_digest(document: Mapping[str, Any]) -> str | None:
    """The digest `identity.knowledge` names, or `None` when it names no snapshot."""
    identity = document.get("identity")
    knowledge = identity.get("knowledge") if isinstance(identity, Mapping) else None
    digest = knowledge.get("digest") if isinstance(knowledge, Mapping) else None
    return digest if isinstance(digest, str) else None


def names_for_document(document: Mapping[str, Any]) -> dict[str, dict[str, str | None]]:
    """`{"technology": {"<id>": name | None}, "unit": {...}, "building": {...}}` for exactly the
    ids `document` references; every kind is present, empty when nothing of that kind is."""
    digest = _knowledge_digest(document)
    ids = referenced_ids(document)
    return {
        kind: {
            str(entity_id): (
                label_in_snapshot(digest, kind, str(entity_id)) if digest is not None else None
            )
            for entity_id in sorted(ids[kind])
        }
        for kind in KINDS
    }
