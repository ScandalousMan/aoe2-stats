"""T707: an analysis of a build 185872 recording is answered by a snapshot, and `query.name`
resolves the identifiers the document carries.

Match 511523321 (game build 185872, `tests/fixtures/replays/README.md`) was analysed in production
on 2026-10-08 with only a build 180059 snapshot installed, so the analysis named no knowledge
snapshot. Built here from the committed recording and the real adapter, exactly as
`test_document_build.py` does for the first recording. As of 2026-10-08 the stored document carried
identifiers only and the page showed them (T709): this file proves the snapshot can name them, not
that anything does.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from aoe2stats_analyzer.extract import build_document
from aoe2stats_knowledge import gaps, query
from aoe2stats_replay_engine.aoe2rec import Aoe2RecExtractor

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURE_ZIP = _REPO_ROOT / "tests" / "fixtures" / "replays" / "AgeIIDE_Replay_511523321.zip"
_BUILD = 185872
_MAX_RAW_BYTES = 25_165_824  # `.env.example`'s ANALYSIS_MAX_RAW_BYTES


@pytest.fixture(scope="module")
def document() -> dict[str, Any]:
    return build_document(
        Aoe2RecExtractor(max_raw_bytes=_MAX_RAW_BYTES),
        _FIXTURE_ZIP.read_bytes(),
        game_id=511_523_321,
        object_key="retained-recordings/511523321/1.zip",
        zip_sha256="ab" * 32,
        extracted_at=datetime(2026, 10, 8, 12, 0, tzinfo=UTC),
    )


def test_the_document_names_the_build_185872_snapshot_and_no_whole_build_gap(
    document: dict[str, Any],
) -> None:
    knowledge = document["identity"]["knowledge"]

    assert knowledge["describes_build"] == _BUILD
    assert knowledge["source_version"] == "3bb43b1439eef88dfe7fe892d7f7dc41ac9dd76f"
    assert [g for g in document["knowledge_gaps"] if g["cause"] == "no-snapshot-for-build"] == []


def test_every_age_up_and_building_the_recording_shows_resolves_to_a_name(
    document: dict[str, Any],
) -> None:
    build = document["identity"]["knowledge"]["describes_build"]
    participants = document["participants"]
    age_up_ids = {tech for p in participants for tech in p["age_up_commands"]}
    building_ids = {event["building_id"] for p in participants for event in p["builds"]}
    assert {"101", "102"} <= age_up_ids, "the recording is expected to reach the Castle Age"
    assert 70 in building_ids

    names: dict[tuple[str, str], str] = {}
    for kind, ids in (("technology", age_up_ids), ("building", {str(i) for i in building_ids})):
        for entity_id in ids:
            answer = query.name(query.EntityRef(kind=kind, id=entity_id, build=build))
            assert not isinstance(answer, gaps.KnowledgeGap), f"{kind} {entity_id}: {answer!r}"
            names[(kind, entity_id)] = answer.value

    assert names[("technology", "101")] == "Feudal Age"
    assert names[("technology", "102")] == "Castle Age"
    assert names[("building", "70")] == "House"
    unresolved = {key: value for key, value in names.items() if value == key[1]}
    # An id the pack carries nowhere (building 490, an age-upgraded visual variant) degrades to
    # the bare identifier, which is `name()`'s contract; nothing else may.
    assert set(unresolved) <= {("building", "490")}, unresolved
