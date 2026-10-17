"""Display names for the ids a stored analysis document carries, served beside it (T709).

**The problem.** The document stores identifiers only (an age-up is technology `101`, a house is
building `70`), and no stage maps an id to a name. The knowledge snapshots are that table
(`aoe2stats_knowledge.query.name`). The page needs names; the stored object must not change, because
its bytes are the thing the identity digest and the recorded object key vouch for (FR-042) and a
rewrite is exactly the silent one SC-005 forbids.

**What `with_names` does.** It takes the stored document's bytes and returns the bytes to serve: the
stored bytes unchanged, with one more top-level key (`NAMES_KEY`) appended before the closing brace.
The stored object is a prefix of the answer up to that brace, so a test can compare them byte for
byte, and nothing here writes to the object store.

**Which snapshot.** The one the document's own identity names, matched on all four of `source`,
`source_version`, `describes_build` and `digest` among every packaged snapshot, a demoted one
included (a superseded snapshot is never deleted, SC-005) - the same match `reproduce.py` makes. Not
the snapshot promoted for the build now, not the nearest build's, and no other (FR-027, FR-038). An
identity that names no snapshot (`{"absent": ...}`), names one that is not installed, or names one
installed under the same build with another digest, gets no names, and the bytes come back as they
were. A document with no `identity` (schema version 1), a body that is not a JSON object, and a body
that already carries `NAMES_KEY` are all returned as they were.

**An id the snapshot does not name stays unresolved.** It is left out of the block, and the page
renders the identifier as it did before (003 FR-043a: "a confident wrong name is worse than a bare
id"). Nothing is substituted for it. Resolution is `query.name`, so what counts as unresolved is
that function's own verdict (`query.UNRESOLVED_SOURCE`), not a second opinion kept here.

**On the API's request path, by decision (FR-049, T709a).** Names are resolved when the document is
served, not when it is analysed, and this module is request-path code
(`tests/architecture/test_feature_006_boundaries.py`'s `_REQUEST_PATH_CODE`). The API imports it
lazily, from the analysis route, and it is the second analyzer module the API may import. What it
adds to a request is a parse of the document, `functools.cache`d snapshot lookups and dictionary
reads from package data. Nothing is fetched, no recording or object is read beyond the document the
route already holds, no engine is loaded and none of the capture budget is touched
(`apps/api/tests/test_engine_isolation.py` runs it and asserts as much). The rule that keeps the
knowledge package off the request path is amended for this module alone: the guard grants it the
seven symbols imported above by name (six of the knowledge package and the truth `REGISTER`, which
the block's provenance reads), and any other import of either package from here fails it. The API
itself still imports no knowledge package; that import lives here, behind the same seam
`staleness.py` uses.

**The served leaves are published data (FR-006, FR-007).** The block's leaves have register entries
(`names.*` in `register.toml`, tier derived) and the block carries its own `provenance` (tier,
method and inputs per datum present, read from the register), both checked over the served bytes and
not only over the stored body (`apps/analyzer/tests/test_names.py`).
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any, Final

from aoe2stats_core.truth.register import REGISTER
from aoe2stats_knowledge import gaps, query
from aoe2stats_knowledge.snapshot import (
    Snapshot,
    SnapshotError,
    load_all_snapshots,
    pinned_snapshot,
)

__all__ = ["FAULT_ERRORS", "METHOD_ID", "METHOD_VERSION", "NAMES_KEY", "with_names"]

#: The top-level key the block is served under. Not a field of the stored document: it is absent
#: from every stored object, and a stored object that has it is served as it is.
NAMES_KEY: Final[str] = "knowledge_names"

#: The errors that mean an installed snapshot cannot be read or fails its own digest: a deployment
#: fault, which a caller logs under its own line and answers with the stored bytes. The same two
#: classes `extract.DEPLOYMENT_FAULT_ERRORS` names for knowledge, without importing the extractor.
FAULT_ERRORS: Final[tuple[type[Exception], ...]] = (SnapshotError, OSError)

#: The four fields a snapshot is named by in an identity's `knowledge` component.
_SNAPSHOT_FIELDS: Final[tuple[str, ...]] = ("source", "source_version", "describes_build", "digest")

#: The method behind every `names.` datum (FR-009), as `extract._METHODS` assigns it: that table
#: reads these two constants, so the method a block records and the one the register's publication
#: gate resolves are one value and not two spellings.
METHOD_ID: Final[str] = "knowledge-snapshot.name"
METHOD_VERSION: Final[str] = "1"

#: The register datum behind each kind's record, and behind the two fields of `snapshot`.
_KIND_DATUM: Final[Mapping[str, str]] = {
    "technology": "names.technology",
    "unit": "names.unit",
    "building": "names.building",
}
_SNAPSHOT_DATA: Final[tuple[str, ...]] = ("names.snapshot.describes_build", "names.snapshot.digest")

#: The entity kinds a page shows a name for, as `rules.json` keys them.
_KINDS: Final[tuple[str, ...]] = ("technology", "unit", "building")


def with_names(stored: bytes) -> bytes:
    """`stored` with the names block appended, or `stored` itself when there is nothing honest to
    add (module docstring). Never mutates its input, and never raises for a document it cannot
    read: a body that is not the object the analyzer wrote is the caller's to serve as it is.

    A deployment fault (an installed snapshot that cannot be loaded) does raise, as one of
    `FAULT_ERRORS`, which a caller should log and answer with the stored bytes.
    """
    document = _parse_object(stored)
    if document is None or NAMES_KEY in document:
        return stored
    snapshot = _named_snapshot(document)
    if snapshot is None:
        return stored
    block = _block(snapshot, document)
    body = stored.rstrip()
    separator = b"" if body[:-1].rstrip().endswith(b"{") else b","
    appended = json.dumps({NAMES_KEY: block}, sort_keys=True, ensure_ascii=False).encode("utf-8")
    # `appended` is `{"knowledge_names": {...}}`: drop its opening brace and keep the pair, so the
    # pair lands inside the stored object, ahead of the stored object's own closing brace.
    return body[:-1] + separator + appended[1:]


def _parse_object(stored: bytes) -> dict[str, Any] | None:
    """The stored bytes as a JSON object, or `None` for anything else (including bytes that are not
    UTF-8 JSON). `with_names` splices before the final closing brace, which only means something
    for an object."""
    try:
        parsed = json.loads(stored)
    except ValueError:
        return None
    if not isinstance(parsed, dict) or not stored.rstrip().endswith(b"}"):
        return None
    return parsed


def _named_snapshot(document: Mapping[str, Any]) -> Snapshot | None:
    """The installed snapshot the document's identity names, matched on all four fields, or `None`
    (module docstring). An identity that records the absence of a snapshot carries none of the four
    and names nothing."""
    identity = document.get("identity")
    knowledge = identity.get("knowledge") if isinstance(identity, Mapping) else None
    if not isinstance(knowledge, Mapping) or any(
        field not in knowledge for field in _SNAPSHOT_FIELDS
    ):
        return None
    for snapshot in load_all_snapshots():
        recorded = snapshot.identity
        if (
            recorded.source == knowledge["source"]
            and recorded.source_version == knowledge["source_version"]
            and recorded.describes_build == knowledge["describes_build"]
            and recorded.digest == knowledge["digest"]
        ):
            return snapshot
    return None


def _ids(document: Mapping[str, Any]) -> dict[str, set[str]]:
    """Every id the page shows, by entity kind, spelled as `rules.json` keys it (a string). Read
    defensively: a participant or event that is not the shape the analyzer writes contributes
    nothing, rather than failing a read for what is only decoration."""
    found: dict[str, set[str]] = {kind: set() for kind in _KINDS}
    participants = document.get("participants")
    for participant in participants if isinstance(participants, list) else ():
        if not isinstance(participant, Mapping):
            continue
        age_ups = participant.get("age_up_commands")
        if isinstance(age_ups, Mapping):
            found["technology"].update(str(key) for key in age_ups)
        _collect(found["technology"], participant.get("researches"), "technology_id")
        _collect(found["unit"], participant.get("trainings"), "unit_id")
        _collect(found["building"], participant.get("builds"), "building_id")
    return found


def _collect(into: set[str], events: Any, key: str) -> None:
    for event in events if isinstance(events, list) else ():
        if isinstance(event, Mapping) and isinstance(event.get(key), int):
            into.add(str(event[key]))


def _block(snapshot: Snapshot, document: Mapping[str, Any]) -> dict[str, Any]:
    """The names block: the snapshot that answered, and per kind the ids it names. The snapshot is
    pinned for the lookups so `query.name` reads it and no other, whether or not it is the one
    promoted for its build now."""
    build = snapshot.identity.describes_build
    resolved: dict[str, dict[str, str]] = {kind: {} for kind in _KINDS}
    with pinned_snapshot(snapshot):
        for kind, ids in _ids(document).items():
            for entity_id in _sorted_ids(ids):
                answer = query.name(query.EntityRef(kind=kind, id=entity_id, build=build))
                if (
                    isinstance(answer, gaps.KnowledgeGap)
                    or answer.source == query.UNRESOLVED_SOURCE
                ):
                    continue
                resolved[kind][entity_id] = answer.value
    return {
        "snapshot": {"describes_build": build, "digest": snapshot.identity.digest},
        **resolved,
        "provenance": _provenance(resolved),
    }


def _provenance(resolved: Mapping[str, Mapping[str, str]]) -> dict[str, dict[str, Any]]:
    """The block's own provenance (FR-007, FR-009), in the shape the stored document's uses: per
    datum present, its tier, its method and its inputs.

    Tier and inputs are the register's entry's, read here and never typed again; the method is the
    one `extract._METHODS` assigns the `names.` family. A kind with no resolved name leaves no leaf
    in the block, so its datum is not present and has no entry - the same reading of presence the
    validator makes (`apps/analyzer/tests/test_names.py` runs rules 1 to 4 over the served bytes).
    It lives in the block, not in the stored `provenance`, whose bytes the identity digest vouches
    for."""
    present = [*_SNAPSHOT_DATA, *(_KIND_DATUM[kind] for kind in _KINDS if resolved.get(kind))]
    provenance: dict[str, dict[str, Any]] = {}
    for datum in present:
        entry = REGISTER[datum]
        if entry.tier is None:
            raise ValueError(f"{datum} is non-determinable and cannot be served")
        provenance[datum] = {
            "tier": entry.tier.value,
            "method": f"{METHOD_ID}@{METHOD_VERSION}",
            "inputs": list(entry.depends_on),
        }
    return provenance


def _sorted_ids(ids: Iterable[str]) -> list[str]:
    return sorted(ids, key=lambda value: (len(value), value))
