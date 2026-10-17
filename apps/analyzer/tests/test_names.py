"""T709: names are served beside a stored analysis document, never written into it.

`names.with_names` takes the stored document's bytes and returns the bytes to serve: the stored
bytes untouched, with one block appended at the end of the top-level object. The block holds the
display name of each technology, unit and building id the document carries, resolved from the
snapshot the document's own identity names (FR-027, FR-025) and from no other.

Documents here are built by hand, not by the extractor, so the tests need no engine and each case
names exactly the identity it is about. Both promoted snapshots are used (builds 180059 and
185872); the second models no civilisation, which must not matter to a name (T707).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from aoe2stats_analyzer.canonical import canonical_bytes
from aoe2stats_analyzer.extract import build_document
from aoe2stats_analyzer.names import NAMES_KEY, with_names
from aoe2stats_knowledge.snapshot import load_all_snapshots
from aoe2stats_replay_engine.aoe2rec import Aoe2RecExtractor

_REPO_ROOT = Path(__file__).resolve().parents[3]
_REPLAYS = _REPO_ROOT / "tests" / "fixtures" / "replays"
_MAX_RAW_BYTES = 25_165_824  # `.env.example`'s ANALYSIS_MAX_RAW_BYTES
#: One committed recording per promoted build: (game id, build).
_RECORDINGS = ((500_546_441, 180059), (511_523_321, 185872))

_PROMOTED_BUILDS = (180059, 185872)

#: Neither promoted snapshot carries this building (the 185872 recording builds it: an
#: age-upgraded visual variant), so it must stay unresolved while its neighbours resolve.
_ID_OUTSIDE_THE_SNAPSHOT = 490


def _knowledge_identity(build: int) -> dict[str, Any]:
    (snapshot,) = (
        s for s in load_all_snapshots() if s.promoted and s.identity.describes_build == build
    )
    identity = snapshot.identity
    return {
        "source": identity.source,
        "source_version": identity.source_version,
        "describes_build": identity.describes_build,
        "digest": identity.digest,
    }


def _document(knowledge: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "game_id": 1,
        "identity": {"digest": "sha256:x", "knowledge": knowledge},
        "participants": [
            {
                "profile_id": 1,
                "age_up_commands": {"101": 600_000, "102": 1_200_000},
                "builds": [
                    {"building_id": 70, "world_time_ms": 1000},
                    {"building_id": _ID_OUTSIDE_THE_SNAPSHOT, "world_time_ms": 2000},
                ],
                "trainings": [
                    {"unit_id": 83, "amount": 1, "building_id": 109, "world_time_ms": 3000}
                ],
                "researches": [{"technology_id": 101, "world_time_ms": 600_000}],
            }
        ],
    }


def _stored(document: dict[str, Any]) -> bytes:
    return json.dumps(document, sort_keys=True, indent=1).encode("utf-8") + b"\n"


def _served_names(served: bytes) -> dict[str, Any]:
    names: dict[str, Any] = json.loads(served)[NAMES_KEY]
    return names


@pytest.mark.parametrize("build", _PROMOTED_BUILDS)
def test_each_promoted_build_names_feudal_age_castle_age_and_house(build: int) -> None:
    stored = _stored(_document(_knowledge_identity(build)))

    names = _served_names(with_names(stored))

    assert names["technology"]["101"] == "Feudal Age"
    assert names["technology"]["102"] == "Castle Age"
    assert names["building"]["70"] == "House"
    assert names["unit"]["83"] == "Villager"
    assert names["snapshot"] == {
        "describes_build": build,
        "digest": _knowledge_identity(build)["digest"],
    }


@pytest.mark.parametrize("build", _PROMOTED_BUILDS)
def test_an_id_outside_the_snapshot_is_left_out_while_its_neighbour_resolves(build: int) -> None:
    stored = _stored(_document(_knowledge_identity(build)))

    names = _served_names(with_names(stored))

    assert str(_ID_OUTSIDE_THE_SNAPSHOT) not in names["building"]
    assert names["building"]["70"] == "House"


@pytest.mark.parametrize("build", _PROMOTED_BUILDS)
def test_the_stored_bytes_are_the_prefix_of_what_is_served(build: int) -> None:
    """The names ride after the stored object, whose bytes are untouched: a digest taken over them
    before and after is the same, and the input is not mutated."""
    stored = _stored(_document(_knowledge_identity(build)))
    before = bytes(stored)

    served = with_names(stored)

    assert stored == before
    assert served != stored
    assert served.startswith(stored.rstrip()[:-1]), "the stored object is not a prefix"
    assert {k: v for k, v in json.loads(served).items() if k != NAMES_KEY} == json.loads(stored)


@pytest.mark.parametrize(
    "knowledge",
    [
        {"absent": "no-snapshot-for-build", "build": 999_999},
        {"absent": "no-snapshot-for-build", "build": -1},
    ],
    ids=["unknown-build", "stream-named-no-build"],
)
def test_a_document_whose_identity_names_no_snapshot_gets_no_names(
    knowledge: dict[str, Any],
) -> None:
    stored = _stored(_document(knowledge))

    assert with_names(stored) == stored


def test_a_snapshot_named_with_a_different_digest_is_not_substituted() -> None:
    """The identity names a snapshot exactly (source, version, build, digest). One installed under
    the same build with another digest is not the one named, and is not the nearest either."""
    knowledge = _knowledge_identity(180059) | {"digest": "sha256:" + "0" * 64}

    stored = _stored(_document(knowledge))

    assert with_names(stored) == stored


def test_a_build_that_has_a_snapshot_is_not_used_for_an_identity_naming_another_build() -> None:
    """A document naming a build with no snapshot gets nothing even though other builds have one:
    there is no nearest, no latest."""
    knowledge = _knowledge_identity(185872) | {"describes_build": 185_873}

    stored = _stored(_document(knowledge))

    assert with_names(stored) == stored


@pytest.mark.parametrize(
    "stored",
    [
        _stored({"schema_version": 1, "game_id": 1, "participants": []}),
        b"[]",
        b"not json",
        b"",
    ],
    ids=["version-1-document", "not-an-object", "not-json", "empty"],
)
def test_a_document_that_cannot_name_a_snapshot_is_served_as_stored(stored: bytes) -> None:
    assert with_names(stored) == stored


def test_a_document_carrying_the_names_key_already_is_served_as_stored() -> None:
    """Appending a second key of the same name would make the body ambiguous."""
    document = _document(_knowledge_identity(180059)) | {NAMES_KEY: {"technology": {}}}
    stored = _stored(document)

    assert with_names(stored) == stored


def test_a_document_with_no_ids_to_name_still_records_the_snapshot_and_names_nothing() -> None:
    document = _document(_knowledge_identity(180059))
    document["participants"] = []

    names = _served_names(with_names(_stored(document)))

    assert names["technology"] == {}
    assert names["unit"] == {}
    assert names["building"] == {}


@pytest.mark.parametrize(("game_id", "build"), _RECORDINGS, ids=["build-180059", "build-185872"])
def test_a_document_built_from_a_real_recording_is_named_by_its_own_snapshot(
    game_id: int, build: int
) -> None:
    """The document the extractor really writes, stored as `run.py` stores it: names resolve from
    the snapshot its identity names, the ids the recording shows resolve, and the stored bytes are
    still the prefix of what is served."""
    document = build_document(
        Aoe2RecExtractor(max_raw_bytes=_MAX_RAW_BYTES),
        (_REPLAYS / f"AgeIIDE_Replay_{game_id}.zip").read_bytes(),
        game_id=game_id,
        object_key=f"retained-recordings/{game_id}/1.zip",
        zip_sha256="ab" * 32,
        extracted_at=datetime(2026, 10, 17, 12, 0, tzinfo=UTC),
    )
    stored = canonical_bytes(document)

    served = with_names(stored)

    names = _served_names(served)
    assert names["snapshot"]["describes_build"] == build
    assert names["technology"]["101"] == "Feudal Age"
    assert names["building"]["70"] == "House"
    assert served.startswith(stored.rstrip()[:-1])
    # Every resolved name is one the document's ids asked for, and nothing else.
    ids = {
        "technology": {t for p in document["participants"] for t in p["age_up_commands"]}
        | {str(e["technology_id"]) for p in document["participants"] for e in p["researches"]},
        "building": {str(e["building_id"]) for p in document["participants"] for e in p["builds"]},
        "unit": {str(e["unit_id"]) for p in document["participants"] for e in p["trainings"]},
    }
    for kind, ids_of_kind in ids.items():
        assert set(names[kind]) <= ids_of_kind
