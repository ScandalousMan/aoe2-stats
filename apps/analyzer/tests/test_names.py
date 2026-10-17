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
import re
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any

import pytest
from tests.snapshot_refresh import (
    REAL_SNAPSHOT_DIRECTORY,
    clear_snapshot_resolution_caches,
    isolate_snapshot_root,
)

from aoe2stats_analyzer.canonical import canonical_bytes
from aoe2stats_analyzer.extract import _method_for, build_document
from aoe2stats_analyzer.names import NAMES_KEY, clean_label, with_names
from aoe2stats_core.truth.register import REGISTER
from aoe2stats_core.truth.validate import DocumentInvalid, present_data, validate
from aoe2stats_knowledge import snapshot as snapshot_module
from aoe2stats_knowledge.gaps import KnowledgeGap
from aoe2stats_knowledge.query import EntityRef
from aoe2stats_knowledge.query import name as query_name
from aoe2stats_knowledge.snapshot import load_all_snapshots, load_resolvable_snapshots
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


# --- FR-006: the served shape is published data, so every leaf of it has a register entry --------

_NAMES_DATA = frozenset(
    {
        "names.snapshot.describes_build",
        "names.snapshot.digest",
        "names.technology",
        "names.unit",
        "names.building",
    }
)


def _served_shape_violations(served: bytes) -> list[tuple[int, str]]:
    """Rules 1 to 4 of the document validator, run over the bytes that are served and not over the
    stored body: every leaf resolves to a published register datum (1), every datum present has a
    provenance entry and every provenance key is present (2), each tier is the register's (3) and
    each entry names a method (4).

    The validator reads a document's top-level `provenance`, and the served block carries its own
    one level down (`knowledge_names.provenance`, because the stored provenance is part of the bytes
    the digest vouches for and is not extended). The block is therefore presented as the document it
    is the provenance of: its data under `knowledge_names`, its map as `provenance`. Rules 8 to 10
    are the stored body's (it has the identity and the gaps)."""
    block = dict(json.loads(served)[NAMES_KEY])
    view: dict[str, Any] = {NAMES_KEY: block}
    if "provenance" in block:
        view["provenance"] = block.pop("provenance")
    try:
        validate(view, REGISTER.entries)
    except DocumentInvalid as exc:
        return [(rule, text) for rule, text in exc.violations if rule <= 4]
    return []


def _leaves_without_a_register_datum(served: bytes) -> list[str]:
    return [text for rule, text in _served_shape_violations(served) if rule == 1]


@pytest.mark.parametrize("build", _PROMOTED_BUILDS)
def test_every_leaf_of_a_served_block_resolves_to_a_published_register_datum(build: int) -> None:
    served = with_names(_stored(_document(_knowledge_identity(build))))

    assert _leaves_without_a_register_datum(served) == []
    assert present_data(json.loads(served), REGISTER.entries) >= _NAMES_DATA


def test_an_empty_kind_of_a_served_block_still_resolves_to_a_register_datum() -> None:
    """A document with no ids names nothing: three empty records, which are not values but must
    not read as an unregistered leaf either."""
    document = _document(_knowledge_identity(180059))
    document["participants"] = []

    served = with_names(_stored(document))

    assert _served_shape_violations(served) == []
    # Nothing is present of the three kinds, so none has a provenance entry either.
    assert set(json.loads(served)[NAMES_KEY]["provenance"]) == {
        "names.snapshot.describes_build",
        "names.snapshot.digest",
    }


@pytest.mark.parametrize(("game_id", "build"), _RECORDINGS, ids=["build-180059", "build-185872"])
def test_the_block_served_for_a_real_document_has_a_register_entry_for_every_leaf(
    game_id: int, build: int
) -> None:
    document = build_document(
        Aoe2RecExtractor(max_raw_bytes=_MAX_RAW_BYTES),
        (_REPLAYS / f"AgeIIDE_Replay_{game_id}.zip").read_bytes(),
        game_id=game_id,
        object_key=f"retained-recordings/{game_id}/1.zip",
        zip_sha256="ab" * 32,
        extracted_at=datetime(2026, 10, 17, 12, 0, tzinfo=UTC),
    )

    served = with_names(canonical_bytes(document))

    assert NAMES_KEY in json.loads(served)
    assert _served_shape_violations(served) == []


def test_a_served_leaf_with_no_register_entry_is_named_by_the_check() -> None:
    """The contrast: the check can fail. A block carrying a kind the register does not know is
    reported leaf by leaf, so a green run above is not a check that matches nothing."""
    served = json.loads(with_names(_stored(_document(_knowledge_identity(180059)))))
    served[NAMES_KEY]["civilisation"] = {"1": "Franks"}

    problems = _leaves_without_a_register_datum(json.dumps(served).encode("utf-8"))

    assert any("knowledge_names.civilisation.1" in problem for problem in problems), problems


# --- SC-005: a superseded snapshot stays answerable by the identity that names it ---------------


def test_names_resolve_from_a_snapshot_that_is_installed_but_not_promoted_for_its_build(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A knowledge refresh promotes a second snapshot and demotes the first, and a document the
    first one named must keep its names (SC-005, FR-027: the snapshot its identity names, never the
    one promoted now). The named snapshot is demoted in place - its digest covers `rules.json` and
    `effects.toml` only - so it is installed, matches the identity on all four fields, and is not
    promoted for its build: `snapshot_for` reports no snapshot for it at all.

    A `names.py` that read `load_resolvable_snapshots` instead of every installed snapshot would
    find nothing here and serve the stored bytes, which is what this asserts it does not."""
    root = isolate_snapshot_root(monkeypatch, tmp_path)
    identity_file = root / REAL_SNAPSHOT_DIRECTORY / snapshot_module.IDENTITY_FILENAME
    text = identity_file.read_text(encoding="utf-8")
    demoted, count = re.subn(r"^promoted = true", "promoted = false", text, flags=re.MULTILINE)
    assert count == 1
    identity_file.write_text(demoted, encoding="utf-8")
    clear_snapshot_resolution_caches()

    (installed,) = load_all_snapshots()
    assert not installed.promoted
    assert load_resolvable_snapshots() == ()
    assert isinstance(
        snapshot_module.snapshot_for(installed.identity.describes_build), KnowledgeGap
    )
    identity = installed.identity
    stored = _stored(
        _document(
            {
                "source": identity.source,
                "source_version": identity.source_version,
                "describes_build": identity.describes_build,
                "digest": identity.digest,
            }
        )
    )

    names = _served_names(with_names(stored))

    assert names["technology"]["101"] == "Feudal Age"
    assert names["building"]["70"] == "House"
    assert names["snapshot"] == {
        "describes_build": identity.describes_build,
        "digest": identity.digest,
    }


# --- FR-007: the served block carries its tier as data, in a provenance map of its own ------------


def _block_of(build: int = 180059) -> dict[str, Any]:
    return _served_names(with_names(_stored(_document(_knowledge_identity(build)))))


def _serve(block: dict[str, Any]) -> bytes:
    return json.dumps({NAMES_KEY: block}).encode("utf-8")


@pytest.mark.parametrize("build", _PROMOTED_BUILDS)
def test_the_block_carries_a_provenance_entry_for_every_datum_it_holds(build: int) -> None:
    provenance = _block_of(build)["provenance"]

    assert set(provenance) == _NAMES_DATA
    for datum, entry in provenance.items():
        register_entry = REGISTER[datum]
        assert entry == {
            "tier": "derived",
            "method": _method_for(datum),
            "inputs": list(register_entry.depends_on),
        }
        assert register_entry.tier is not None
        assert entry["tier"] == register_entry.tier.value


def test_the_provenance_is_read_from_the_register_and_the_methods_table_not_retyped() -> None:
    """The tier and inputs are the register's entry's and the method is the one `extract`'s
    `_METHODS` assigns the `names.` family: a change to either shows here, in the served block."""
    provenance = _block_of()["provenance"]

    for datum in _NAMES_DATA:
        assert provenance[datum]["method"] == _method_for(datum)
        assert provenance[datum]["tier"] == REGISTER[datum].classification
        assert provenance[datum]["inputs"] == list(REGISTER[datum].depends_on)


def test_a_provenance_entry_removed_from_the_block_is_named_by_rule_2() -> None:
    block = _block_of()
    del block["provenance"]["names.unit"]

    problems = _served_shape_violations(_serve(block))

    assert (2, "'names.unit' is present without a provenance entry") in problems


def test_a_block_tier_that_is_not_the_registers_is_named_by_rule_3() -> None:
    block = _block_of()
    block["provenance"]["names.technology"]["tier"] = "observed"

    problems = _served_shape_violations(_serve(block))

    assert any(rule == 3 and "'names.technology'" in text for rule, text in problems), problems


def test_a_provenance_key_for_a_path_the_block_lacks_is_named_by_rule_2() -> None:
    block = _block_of()
    block["unit"] = {}

    problems = _served_shape_violations(_serve(block))

    assert (2, "provenance names 'names.unit', which is not in the document") in problems


def test_a_block_with_no_provenance_at_all_is_named_by_rule_2() -> None:
    block = _block_of()
    del block["provenance"]

    problems = _served_shape_violations(_serve(block))

    assert {text for rule, text in problems if rule == 2} >= {
        f"{datum!r} is present without a provenance entry" for datum in sorted(_NAMES_DATA)
    }


def test_the_stored_documents_own_provenance_is_untouched_and_still_validates() -> None:
    """The contrast: the block's provenance is the block's. The stored document - its provenance
    included - is the same bytes it was, and validates as the extractor wrote it."""
    document = build_document(
        Aoe2RecExtractor(max_raw_bytes=_MAX_RAW_BYTES),
        (_REPLAYS / "AgeIIDE_Replay_500546441.zip").read_bytes(),
        game_id=500_546_441,
        object_key="retained-recordings/500546441/1.zip",
        zip_sha256="ab" * 32,
        extracted_at=datetime(2026, 10, 17, 12, 0, tzinfo=UTC),
    )
    stored = canonical_bytes(document)

    served = json.loads(with_names(stored))

    validate(json.loads(stored), REGISTER.entries)
    assert served["provenance"] == json.loads(stored)["provenance"]
    assert not any(datum.startswith("names.") for datum in json.loads(stored)["provenance"])
    assert {k: v for k, v in served.items() if k != NAMES_KEY} == json.loads(stored)


def test_the_contracts_example_block_is_complete_against_its_own_rules() -> None:
    """T709b: the example in `contracts/analysis-document.md` is a block the served-shape check
    accepts - a provenance entry for every datum it holds and none for a datum it lacks."""
    contract = (
        _REPO_ROOT
        / "specs"
        / "006-replay-analysis-foundations"
        / "contracts"
        / "analysis-document.md"
    ).read_text(encoding="utf-8")
    start = contract.index('"knowledge_names": {')
    example = contract[start : contract.index("```", start)]

    served = ("{" + example.strip() + "}").encode("utf-8")

    assert set(json.loads(served)[NAMES_KEY]["provenance"]) == _NAMES_DATA
    assert _served_shape_violations(served) == []


# --- the served label is the vendored name cleaned of its line-break markup ----------------------

_BUILD_WITH_MARKUP = 185872


def _document_naming(
    *,
    buildings: tuple[int, ...] = (),
    technologies: tuple[int, ...] = (),
    units: tuple[int, ...] = (),
) -> dict[str, Any]:
    document = _document(_knowledge_identity(_BUILD_WITH_MARKUP))
    (participant,) = document["participants"]
    participant["builds"] = [{"building_id": i, "world_time_ms": 1} for i in buildings]
    participant["researches"] = [{"technology_id": i, "world_time_ms": 1} for i in technologies]
    participant["trainings"] = [
        {"unit_id": i, "amount": 1, "building_id": 12, "world_time_ms": 1} for i in units
    ]
    participant["age_up_commands"] = {}
    return document


def test_a_vendored_name_with_markup_is_served_as_a_clean_label() -> None:
    """Building 109 is `"Town<br>\\nCenter"` in the snapshot, technology 1404
    `"Circum-<br>\\nnavigation"` and technology 454 `"Counter- weights"`; a compound's hyphen
    stays."""
    document = _document_naming(
        buildings=(109,), technologies=(1404, 454, 202, 217, 222), units=(473, 75)
    )

    names = _served_names(with_names(_stored(document)))

    assert names["building"]["109"] == "Town Center"
    assert names["technology"] == {
        "202": "Double-Bit Axe",
        "217": "Two-Handed Swordsman",
        "222": "Man-at-Arms",
        "454": "Counterweights",
        "1404": "Circumnavigation",
    }
    assert names["unit"] == {"473": "Two-Handed Swordsman", "75": "Man-at-Arms"}


def test_the_snapshot_itself_still_returns_the_vendored_name() -> None:
    """The cleaning is the block's: `query.name` and the frozen snapshot are untouched."""
    answer = query_name(EntityRef(kind="building", id="109", build=_BUILD_WITH_MARKUP))

    assert not isinstance(answer, KnowledgeGap)
    assert answer.value == "Town<br>\nCenter"


def test_no_label_served_for_a_real_recording_carries_markup() -> None:
    document = build_document(
        Aoe2RecExtractor(max_raw_bytes=_MAX_RAW_BYTES),
        (_REPLAYS / "AgeIIDE_Replay_511523321.zip").read_bytes(),
        game_id=511_523_321,
        object_key="retained-recordings/511523321/1.zip",
        zip_sha256="ab" * 32,
        extracted_at=datetime(2026, 10, 17, 12, 0, tzinfo=UTC),
    )

    names = _served_names(with_names(canonical_bytes(document)))

    assert names["technology"]["202"] == "Double-Bit Axe"
    labels = [
        label for kind in ("technology", "unit", "building") for label in names[kind].values()
    ]
    assert labels
    assert [label for label in labels if "<" in label or ">" in label] == []


def _every_vendored_name() -> list[tuple[str, str, str, str]]:
    """(snapshot directory, kind, id, name) for every entity of every installed snapshot."""
    found = []
    for snapshot in load_all_snapshots():
        rules = json.loads(
            resources.files("aoe2stats_knowledge")
            .joinpath("snapshots", snapshot.directory, "rules.json")
            .read_text(encoding="utf-8")
        )
        for kind, records in rules.get("entities", {}).items():
            for entity_id, record in records.items():
                if record.get("name"):
                    found.append((snapshot.directory, kind, entity_id, record["name"]))
    return found


def test_the_sweep_reaches_names_with_markup_in_more_than_one_snapshot() -> None:
    """The sweep below proves nothing over a table with no markup in it."""
    with_markup = {d for d, _, _, name in _every_vendored_name() if "<br" in name.lower()}

    assert len(with_markup) >= 2


def test_every_vendored_name_of_every_snapshot_cleans_to_a_plain_label() -> None:
    problems = []
    for directory, kind, entity_id, vendored in _every_vendored_name():
        label = clean_label(vendored)
        if (
            label is None
            or "<" in label
            or ">" in label
            or "- " in label
            or label != label.strip()
            or "  " in label
            or "\n" in label
        ):
            problems.append((directory, kind, entity_id, vendored, label))
    assert problems == []


@pytest.mark.parametrize("markup", ["<br>", " <br/> ", "-<br>", "<BR />", "", "  \n "])
def test_a_label_with_nothing_but_markup_is_left_out(markup: str) -> None:
    assert clean_label(markup) is None


@pytest.mark.parametrize(
    ("vendored", "label"),
    [
        ("Town<br>\nCenter", "Town Center"),
        ("Circum-<br>\nnavigation", "Circumnavigation"),
        ("Counter- weights", "Counterweights"),
        ("Double-Bit<br>\nAxe", "Double-Bit Axe"),
        ("Man-at-Arms", "Man-at-Arms"),
        ("Feudal Age", "Feudal Age"),
    ],
)
def test_clean_label_joins_word_wrap_hyphens_and_keeps_compounds(vendored: str, label: str) -> None:
    assert clean_label(vendored) == label
