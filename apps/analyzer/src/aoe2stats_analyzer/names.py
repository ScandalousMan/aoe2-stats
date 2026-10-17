"""The names a published analysis document's identifiers resolve to (T709).

**What it answers.** The stored document carries technology, unit and building ids and no names
(`contracts/analysis.md`). `GET /api/matches/{game_id}/analysis` serves it beside a `names` table
built here: for each id the document references, the display name the knowledge snapshot **the
document itself names** gives it, or `None`.

**Never the nearest snapshot (FR-027).** The snapshot is the one `identity.knowledge` names,
matched on all four identity fields by `aoe2stats_knowledge.query.name_in_snapshot`. It is not
resolved from the build, so a knowledge refresh that has since promoted a second snapshot for the
same build cannot change what an old analysis shows. A document with no `identity.knowledge`, with
the explicit `{"absent": ...}` record, with a malformed one, or naming an identity no loaded
snapshot has, resolves every id to `None`; so does an id its snapshot does not name (the query's
`source == "unresolved"` answer, which echoes the id back and is therefore never shown as a name).
`None` is the wire's "unresolved", and nothing in this module invents a name.

**The presentation boundary.** The knowledge query returns a name exactly as the pack vendored it;
this module is where it becomes a label (`clean_label`): the source's line-break markup is
collapsed, and a hyphen the source broke a word on is joined (`"Circum-<br>\\nnavigation"` is
`"Circumnavigation"`).

**Which ids.** The ones the page renders a name for: every participant's `age_up_commands` keys
and `researches[].technology_id` (technologies), `builds[].building_id` (buildings) and
`trainings[].unit_id` (units). A training's `building_id` is the producing building and the page
shows no name for it, so it is not looked up.

**Faults.** `names_for_document` lets a snapshot that cannot be loaded raise (`FAULT_ERRORS`); the
route that serves it logs and degrades to `unresolved_names`, so a deployment fault never takes the
analysis down for its labels.

**On the API's request path (FR-049).** The API imports this module lazily, from the analysis
route. What it adds to a request is a cached read of the installed snapshot tree: nothing is
fetched, nothing is parsed from a recording, no engine is loaded, and the capture budget is
untouched. It imports `aoe2stats_knowledge.query` and `.snapshot` and nothing of the analyzer's
own (not `extract.py`, so the builder and its dependencies stay unloaded), and reads the document
the route has already read; it does no analysis. `tests/architecture/
test_feature_006_boundaries.py` allows that one import from that one file.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from aoe2stats_knowledge import query
from aoe2stats_knowledge.snapshot import SnapshotError, SnapshotIdentity

#: The three kinds `rules.json` keys its entities by, in the order the wire lists them.
KINDS: tuple[str, ...] = ("technology", "unit", "building")

#: What `name_in_snapshot` can raise for a deployment fault: `load_all_snapshots` raises
#: `SnapshotError` for a snapshot that is malformed or fails its digest, and the filesystem's
#: `OSError` for a packaged file that is missing. A subset of `extract.DEPLOYMENT_FAULT_ERRORS`
#: (a test asserts it), spelled out here so this module need not import the builder to name it.
FAULT_ERRORS: tuple[type[Exception], ...] = (SnapshotError, OSError)

_IDENTITY_FIELDS = ("source", "source_version", "describes_build", "digest")

#: `query.name_in_snapshot`'s `Answer.source` for an id the snapshot does not name, whose value is
#: then the bare id.
_UNRESOLVED_SOURCE = "unresolved"

# A hyphen the source broke a word on: the break (a `<br>` or plain whitespace) after the hyphen
# and a lowercase continuation. "Circum-<br>\nnavigation" and "Counter- weights" are broken words;
# "Double-Bit<br>\nAxe" and "Man-at-Arms" carry a hyphen of their own, with no break after it.
_BROKEN_WORD = re.compile(r"-(?:\s*(?i:<br\s*/?>)\s*|\s+)(?=[a-z])")
_LINE_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)
_WHITESPACE = re.compile(r"\s+")


def clean_label(vendored: str) -> str | None:
    """A vendored name as a label: broken words joined, line breaks and runs of whitespace as one
    space, trimmed. `None` when nothing is left (decided after the collapse, not before)."""
    label = _BROKEN_WORD.sub("", vendored)
    label = _LINE_BREAK.sub(" ", label)
    label = _WHITESPACE.sub(" ", label).strip()
    return label or None


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


def _knowledge_identity(document: Mapping[str, Any]) -> SnapshotIdentity | None:
    """The identity `identity.knowledge` names, or `None` when it names no snapshot (absent,
    missing or malformed)."""
    identity = document.get("identity")
    knowledge = identity.get("knowledge") if isinstance(identity, Mapping) else None
    if not isinstance(knowledge, Mapping) or "absent" in knowledge:
        return None
    fields: dict[str, Any] = {key: knowledge.get(key) for key in _IDENTITY_FIELDS}
    try:
        return SnapshotIdentity(**fields)
    except SnapshotError:
        return None


def unresolved_names(document: Mapping[str, Any]) -> dict[str, dict[str, str | None]]:
    """The names table with every id the document references mapped to `None`."""
    ids = referenced_ids(document)
    return {kind: {str(entity_id): None for entity_id in sorted(ids[kind])} for kind in KINDS}


def _label(kind: str, entity_id: str, identity: SnapshotIdentity) -> str | None:
    answer = query.name_in_snapshot(kind, entity_id, identity)
    if not isinstance(answer, query.Answer) or answer.source == _UNRESOLVED_SOURCE:
        return None
    return clean_label(answer.value)


def names_for_document(document: Mapping[str, Any]) -> dict[str, dict[str, str | None]]:
    """`{"technology": {"<id>": label | None}, "unit": {...}, "building": {...}}` for exactly the
    ids `document` references; every kind is present, empty when nothing of that kind is. Raises
    `FAULT_ERRORS` when an installed snapshot cannot be loaded."""
    table = unresolved_names(document)
    identity = _knowledge_identity(document)
    if identity is None:
        return table
    for kind in KINDS:
        for entity_id in table[kind]:
            table[kind][entity_id] = _label(kind, entity_id, identity)
    return table
