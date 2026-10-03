"""Canonical serialisation of a published document (T659, FR-041, SC-004).

The SC-004 reference-recording tests (two runs, a fresh process) live in `test_reproducibility.py`;
these pin the individual rules on small documents, so a failure names the rule.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from aoe2stats_analyzer.canonical import WALL_CLOCK_FIELDS, canonical_bytes, compared_body
from aoe2stats_analyzer.extract import build_document
from aoe2stats_core.replay.analysis import MatchTimeline
from aoe2stats_core.truth.identity import AnalysisIdentity


def _document() -> dict[str, Any]:
    """Every top-level kind of field the version 2 document has, small enough to read."""
    return {
        "schema_version": 2,
        "envelope": {"extracted_at": "2026-10-03T12:00:00+00:00"},
        "game_id": 7,
        "engine": {"name": "e", "version": "1", "deps": {"b": "2", "a": "1"}},
        "extracted_at": "2026-10-03T12:00:00+00:00",
        "participants": [
            {
                "profile_id": 2,
                "builds": [{"building_id": 9, "world_time_ms": 30}],
                "age_up_commands": {"102": 5, "101": 3},
                "actions_per_minute": 12.5,
            },
            {"profile_id": 1, "builds": [], "age_up_commands": {}, "actions_per_minute": 0.0},
        ],
        "identity": {"digest": "d", "parser": {"version": "1", "name": "e"}},
        "inferred": {
            "participant.group_silence_episodes": [
                {"participant": 2, "from_ms": 9, "unit_objects": [30, 4, 200]},
                {"participant": 1, "from_ms": 5, "unit_objects": [8]},
            ]
        },
        "provenance": {"b.datum": {"inputs": ["z", "a"]}, "a.datum": {"inputs": []}},
        "knowledge_gaps": [
            {"field": "cost", "prevents": ["y.datum", "b.datum", "x.datum"]},
            {"field": "armour", "prevents": []},
        ],
    }


def _reversed_keys(value: Any) -> Any:
    """The same data with every mapping rebuilt in the opposite insertion order."""
    if isinstance(value, dict):
        return {key: _reversed_keys(value[key]) for key in reversed(list(value))}
    if isinstance(value, list):
        return [_reversed_keys(item) for item in value]
    return value


def test_dict_key_insertion_order_does_not_move_the_bytes() -> None:
    document = _document()

    assert canonical_bytes(_reversed_keys(document)) == canonical_bytes(document)
    assert compared_body(_reversed_keys(document)) == compared_body(document)


def test_keys_are_sorted_in_the_bytes() -> None:
    assert canonical_bytes({"b": 1, "a": {"d": 1, "c": 2}}) == b'{"a":{"c":2,"d":1},"b":1}'


def test_integer_keys_are_written_as_strings_and_collisions_are_refused() -> None:
    assert canonical_bytes({1: "a", 2: "b"}) == b'{"1":"a","2":"b"}'
    with pytest.raises(ValueError, match="serialise to '1'"):
        canonical_bytes({1: "a", "1": "b"})


@pytest.mark.parametrize(
    ("path", "get", "identify"),
    [
        ("participants", lambda d: d["participants"], lambda item: item["profile_id"]),
        (
            "participants[].builds",
            lambda d: d["participants"][0]["builds"],
            lambda item: item["building_id"],
        ),
        (
            "inferred episodes",
            lambda d: d["inferred"]["participant.group_silence_episodes"],
            lambda item: item["participant"],
        ),
    ],
)
def test_an_order_meaningful_list_keeps_its_order_and_reversing_it_changes_the_bytes(
    path: str, get: Any, identify: Any
) -> None:
    """The stream and the player order are what the adapter produced; a sort would be a bug."""
    document = _document()
    # Give the builds list two entries so reversing it is a real change.
    document["participants"][0]["builds"].append({"building_id": 1, "world_time_ms": 10})
    # The fixture lists are deliberately not in sorted order: 2 before 1, 9 before 1.
    before = [identify(item) for item in get(document)]
    assert before != sorted(before), path

    written = json.loads(canonical_bytes(document))
    assert [identify(item) for item in get(written)] == before, path

    reversed_document = _document()
    reversed_document["participants"][0]["builds"].append({"building_id": 1, "world_time_ms": 10})
    get(reversed_document).reverse()
    assert canonical_bytes(reversed_document) != canonical_bytes(document), path


def test_a_set_like_list_is_written_in_sorted_order_whatever_order_it_arrived_in() -> None:
    document = _document()
    shuffled = _document()
    shuffled["provenance"]["b.datum"]["inputs"].reverse()
    shuffled["inferred"]["participant.group_silence_episodes"][0]["unit_objects"].reverse()
    shuffled["knowledge_gaps"][0]["prevents"].reverse()
    shuffled["knowledge_gaps"].reverse()

    assert canonical_bytes(shuffled) == canonical_bytes(document)
    written = json.loads(canonical_bytes(document))
    assert written["provenance"]["b.datum"]["inputs"] == ["a", "z"]
    # Numeric, not textual: 200 sorts after 30, which a string sort would not do.
    episode = written["inferred"]["participant.group_silence_episodes"][0]
    assert episode["unit_objects"] == [4, 30, 200]
    assert written["knowledge_gaps"][1]["prevents"] == ["b.datum", "x.datum", "y.datum"]


def test_a_list_this_module_does_not_know_is_preserved_not_sorted() -> None:
    assert canonical_bytes({"future_field": [3, 1, 2]}) == b'{"future_field":[3,1,2]}'


def test_a_float_renders_identically_however_it_was_computed() -> None:
    """Decision: floats are rounded to six decimals and written by `repr`, so a value that differs
    only by how it was computed does not move the bytes. `0.1 + 0.2` is `0.30000000000000004`
    and would otherwise differ from `0.3`."""
    assert 0.1 + 0.2 != 0.3
    computed = {"actions_per_minute": 0.1 + 0.2}
    literal = {"actions_per_minute": 0.3}

    assert canonical_bytes(computed) == canonical_bytes(literal) == b'{"actions_per_minute":0.3}'
    assert canonical_bytes({"x": sum([0.1] * 10)}) == canonical_bytes({"x": 1.0})


def test_floats_keep_their_type_and_precision_where_it_is_real() -> None:
    assert canonical_bytes({"x": 2.0}) == b'{"x":2.0}'
    assert canonical_bytes({"x": 104.35660312995041}) == b'{"x":104.356603}'
    assert canonical_bytes({"x": 2}) == b'{"x":2}'
    # A genuinely different value stays different.
    assert canonical_bytes({"x": 0.3}) != canonical_bytes({"x": 0.300001})


def test_negative_zero_is_written_as_zero() -> None:
    assert canonical_bytes({"x": -0.0}) == canonical_bytes({"x": 0.0}) == b'{"x":0.0}'
    assert canonical_bytes({"x": -1e-9}) == b'{"x":0.0}'


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_a_float_with_no_json_spelling_is_refused(bad: float) -> None:
    with pytest.raises(ValueError, match="no JSON spelling"):
        canonical_bytes({"x": bad})


def test_the_output_is_compact_utf8_without_escaping_and_without_trailing_whitespace() -> None:
    written = canonical_bytes({"name": "Zoë", "list": [1, 2]})

    assert written == '{"list":[1,2],"name":"Zoë"}'.encode()
    assert written == written.strip()
    assert b", " not in written
    assert b": " not in written


def test_canonical_bytes_are_a_fixed_point_through_json() -> None:
    document = _document()
    once = canonical_bytes(document)

    assert canonical_bytes(json.loads(once)) == once


def test_the_excluded_set_is_exactly_envelope_and_extracted_at() -> None:
    assert {"envelope", "extracted_at"} == WALL_CLOCK_FIELDS
    document = _document()

    assert json.loads(compared_body(document)).keys() == document.keys() - {
        "envelope",
        "extracted_at",
    }


def test_changing_the_wall_clock_set_does_not_move_the_compared_body() -> None:
    document = _document()
    later = _document()
    later["envelope"]["extracted_at"] = "2030-01-01T00:00:00+00:00"
    later["extracted_at"] = "2030-01-01T00:00:00+00:00"

    assert canonical_bytes(later) != canonical_bytes(document)
    assert compared_body(later) == compared_body(document)


def test_a_change_to_any_other_top_level_field_changes_the_compared_body() -> None:
    """Not too wide: nothing outside the wall-clock set may be dropped from the comparison."""
    document = _document()
    baseline = compared_body(document)

    for field in document.keys() - WALL_CLOCK_FIELDS:
        changed = _document()
        changed[field] = {"changed": True}
        assert compared_body(changed) != baseline, field

    added = _document()
    added["a_new_top_level_field"] = 1
    assert compared_body(added) != baseline


def test_compared_body_does_not_mutate_the_document() -> None:
    document = _document()
    compared_body(document)

    assert document.keys() >= WALL_CLOCK_FIELDS
    assert document == _document()


def test_the_identity_digest_excludes_the_wall_clock() -> None:
    """FR-041: the digest is a function of the six components, and `AnalysisIdentity` has no place
    for a clock; two documents built at different times carry the same digest."""
    from pathlib import Path

    from aoe2stats_replay_engine.aoe2rec import Aoe2RecExtractor

    root = Path(__file__).resolve().parents[3]
    zip_bytes = (root / "tests/fixtures/replays/AgeIIDE_Replay_500546441.zip").read_bytes()
    extractor = Aoe2RecExtractor(max_raw_bytes=25_165_824)
    kwargs: dict[str, Any] = {"game_id": 1, "object_key": "k", "zip_sha256": "ab" * 32}

    early = build_document(
        extractor, zip_bytes, extracted_at=datetime(2020, 1, 1, tzinfo=UTC), **kwargs
    )
    late = build_document(
        extractor, zip_bytes, extracted_at=datetime(2030, 1, 1, tzinfo=UTC), **kwargs
    )

    assert early["extracted_at"] != late["extracted_at"]
    assert early["identity"] == late["identity"]
    assert early["identity"]["digest"] == AnalysisIdentity.from_block(early["identity"]).digest
    assert "extracted_at" not in json.dumps(early["identity"])
    assert compared_body(early) == compared_body(late)
    assert canonical_bytes(early) != canonical_bytes(late)


def test_the_set_like_paths_exist_in_a_real_document() -> None:
    """A renamed field would silently turn its sort off; the real document must still reach each
    set-like path this module names."""
    from pathlib import Path

    from aoe2stats_replay_engine.aoe2rec import Aoe2RecExtractor

    root = Path(__file__).resolve().parents[3]
    zip_bytes = (root / "tests/fixtures/replays/AgeIIDE_Replay_500546441.zip").read_bytes()
    document = build_document(
        Aoe2RecExtractor(max_raw_bytes=25_165_824),
        zip_bytes,
        game_id=1,
        object_key="k",
        zip_sha256="ab" * 32,
        extracted_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert any("inputs" in entry for entry in document["provenance"].values())
    assert document["knowledge_gaps"] and all("prevents" in g for g in document["knowledge_gaps"])
    assert document["inferred"]["participant.group_silence_episodes"][0]["unit_objects"]
    assert isinstance(document["participants"], list)
    assert MatchTimeline  # the timeline type the participants list is built from
