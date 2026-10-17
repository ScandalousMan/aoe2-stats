"""T709: `names.names_for_document` - which ids it looks up, and what it does with a document that
names no snapshot. The route-level behaviour (the envelope, the bytes) is `apps/api/tests/
test_analysis_routes.py`'s; this file pins the id collection, which no HTTP test can enumerate."""

from __future__ import annotations

from typing import Any

from aoe2stats_analyzer import names
from aoe2stats_knowledge.snapshot import Snapshot, snapshot_for


def _document(**participant: Any) -> dict[str, Any]:
    resolved = snapshot_for(185872)
    assert isinstance(resolved, Snapshot)
    return {
        "identity": {"knowledge": {"digest": resolved.identity.digest}},
        "participants": [
            {
                "age_up_commands": {},
                "builds": [],
                "trainings": [],
                "researches": [],
                **participant,
            }
        ],
    }


def test_the_ids_are_exactly_the_ones_the_page_renders() -> None:
    document = _document(
        age_up_commands={"101": 1, "102": 2},
        builds=[{"building_id": 70, "world_time_ms": 1}],
        # A training's `building_id` is the producer, which the page does not name.
        trainings=[{"unit_id": 83, "amount": 1, "building_id": 109, "world_time_ms": 1}],
        researches=[{"technology_id": 22, "world_time_ms": 1}],
    )

    assert names.referenced_ids(document) == {
        "technology": {101, 102, 22},
        "unit": {83},
        "building": {70},
    }
    resolved = names.names_for_document(document)
    assert "109" not in resolved["building"]
    assert resolved["technology"] == {"22": "Loom", "101": "Feudal Age", "102": "Castle Age"}


def test_an_id_two_participants_share_is_listed_once() -> None:
    document = _document(builds=[{"building_id": 70}, {"building_id": 70}])
    document["participants"].append(dict(document["participants"][0]))

    assert names.names_for_document(document)["building"] == {"70": "House"}


def test_a_document_without_a_knowledge_identity_names_nothing_but_lists_the_ids() -> None:
    document = _document(age_up_commands={"101": 1})
    del document["identity"]

    assert names.names_for_document(document) == {
        "technology": {"101": None},
        "unit": {},
        "building": {},
    }


def test_the_absent_record_names_nothing() -> None:
    document = _document(age_up_commands={"101": 1})
    document["identity"] = {"knowledge": {"absent": "no-snapshot-for-build", "build": 7}}

    assert names.names_for_document(document)["technology"] == {"101": None}
