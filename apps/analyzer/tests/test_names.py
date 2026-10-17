"""T709: `names.names_for_document` - which ids it looks up, and what it does with a document that
names no snapshot. The route-level behaviour (the envelope, the bytes) is `apps/api/tests/
test_analysis_routes.py`'s; this file pins the id collection, which no HTTP test can enumerate."""

from __future__ import annotations

import functools
from typing import Any, NoReturn

import pytest

from aoe2stats_analyzer import names
from aoe2stats_knowledge import query
from aoe2stats_knowledge import snapshot as snapshot_module
from aoe2stats_knowledge.snapshot import Snapshot, SnapshotError, load_all_snapshots, snapshot_for


def _document(**participant: Any) -> dict[str, Any]:
    return {
        "identity": {"knowledge": _identity_of(185872)},
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


# --- The presentation boundary (T709): a vendored name becomes a label ----------------------------


def _identity_of(build: int) -> dict[str, Any]:
    resolved = snapshot_for(build)
    assert isinstance(resolved, Snapshot)
    identity = resolved.identity
    return {
        "source": identity.source,
        "source_version": identity.source_version,
        "describes_build": identity.describes_build,
        "digest": identity.digest,
    }


@pytest.mark.parametrize("build", [180059, 185872])
def test_technology_1404_is_circumnavigation(build: int) -> None:
    """The pack vendors "Circum-<br>\\nnavigation": a word the source broke across two lines, whose
    hyphen is the break's and not part of the name."""
    document = _document(researches=[{"technology_id": 1404, "world_time_ms": 1}])
    document["identity"]["knowledge"] = _identity_of(build)

    assert names.names_for_document(document)["technology"]["1404"] == "Circumnavigation"


def test_a_hyphen_the_source_did_not_break_on_stays() -> None:
    """The contrast: "Double-Bit<br>\\nAxe" and "Man-at-Arms" carry hyphens of their own, with no
    break after them, and a break after a word is a space."""
    assert names.clean_label("Double-Bit<br>\nAxe") == "Double-Bit Axe"
    assert names.clean_label("Man-at-Arms") == "Man-at-Arms"
    assert names.clean_label("Town<br>\nCenter") == "Town Center"
    assert names.clean_label("Counter- weights") == "Counterweights"


@pytest.mark.parametrize("vendored", ["", "   ", "<br>", "<br>\n<br>", " <br /> "])
def test_a_name_that_is_empty_after_the_collapse_is_none(vendored: str) -> None:
    """Emptiness is decided after the markup is gone, not before."""
    assert names.clean_label(vendored) is None


def test_every_vendored_name_of_every_loaded_snapshot_becomes_a_clean_label() -> None:
    """The sweep: no name in any shipped snapshot, of any entity kind, comes out with markup, a
    broken-word hyphen, stray whitespace or nothing at all."""
    swept = 0
    for loaded in load_all_snapshots():
        for kind in names.KINDS:
            for entity_id in _rules_entities(loaded.directory, kind):
                answer = query.name_in_snapshot(kind, entity_id, loaded.identity)
                assert isinstance(answer, query.Answer)
                if answer.source == "unresolved":
                    continue
                label = names.clean_label(answer.value)
                where = f"{loaded.directory} {kind} {entity_id}: {answer.value!r} -> {label!r}"
                assert label is not None, where
                assert "<" not in label and ">" not in label, where
                assert "- " not in label, where
                assert label == label.strip() and "  " not in label and "\n" not in label, where
                swept += 1
    assert swept > 1000, "the sweep found almost nothing; the walk is broken"


def _rules_entities(directory: str, kind: str) -> list[str]:
    import json
    from importlib import resources

    root = resources.files("aoe2stats_knowledge").joinpath("snapshots").joinpath(directory)
    rules = json.loads(root.joinpath("rules.json").read_text(encoding="utf-8"))
    return list(rules["entities"].get(kind, {}))


# --- Degradation (T709) ---------------------------------------------------------------------------


def test_a_snapshot_fault_raises_what_the_route_catches(monkeypatch: pytest.MonkeyPatch) -> None:
    @functools.cache  # the autouse fixture clears these caches by name around every test
    def broken() -> NoReturn:
        raise SnapshotError("a packaged snapshot fails its digest")

    document = _document(age_up_commands={"101": 1})
    monkeypatch.setattr(snapshot_module, "load_all_snapshots", broken)

    with pytest.raises(names.FAULT_ERRORS):
        names.names_for_document(document)
    assert names.unresolved_names(document)["technology"] == {"101": None}


def test_the_faults_the_lookup_can_raise_are_deployment_faults() -> None:
    """`FAULT_ERRORS` is spelled out in `names.py` so it need not import the builder; this is where
    it is held to the set the staleness flag already classifies faults by."""
    from aoe2stats_analyzer.extract import DEPLOYMENT_FAULT_ERRORS

    assert set(names.FAULT_ERRORS) <= set(DEPLOYMENT_FAULT_ERRORS)


def test_a_malformed_knowledge_identity_names_nothing() -> None:
    for knowledge in ({}, {"digest": "nope"}, {**_identity_of(185872), "describes_build": "x"}):
        document = _document(age_up_commands={"101": 1})
        document["identity"] = {"knowledge": knowledge}

        assert names.names_for_document(document)["technology"] == {"101": None}


def test_one_differing_identity_field_names_nothing_even_for_a_build_that_has_a_snapshot() -> None:
    document = _document(age_up_commands={"101": 1})
    document["identity"]["knowledge"] = {**_identity_of(185872), "source_version": "0" * 40}

    assert names.names_for_document(document)["technology"] == {"101": None}
