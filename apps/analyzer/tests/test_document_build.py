"""The version 2 document `build_document` publishes (T655, US3, FR-007 to FR-011, FR-040, FR-044).

Built from the committed reference recording and the real adapter, so every assertion below is
about what production would write. Validation is not exercised here beyond the one expected failure
at the bottom: running it before the write is T656's, and the validator's own rules have their own
suite (`packages/core/tests/test_validate.py`, `test_document_validation.py`).
"""

from __future__ import annotations

import dataclasses
import json
import re
import subprocess
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from aoe2stats_analyzer.extract import (
    ANALYTICS_VERSION,
    SCHEMA_VERSION,
    _method_for,
    build_document,
    validate_document,
)
from aoe2stats_core.replay.events import CanonicalEvent, EventKind, MatchStartedPayload
from aoe2stats_core.truth.identity import NOT_APPLICABLE, AnalysisIdentity
from aoe2stats_core.truth.register import REGISTER
from aoe2stats_core.truth.tiers import Tier
from aoe2stats_replay_engine.aoe2rec import Aoe2RecExtractor

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURE_ZIP = _REPO_ROOT / "tests" / "fixtures" / "replays" / "AgeIIDE_Replay_500546441.zip"
_FIXTURE_TIMELINE = _FIXTURE_ZIP.with_suffix(".timeline.json")
_GAME_ID = 500_546_441
_OBJECT_KEY = f"retained-recordings/{_GAME_ID}/196240.zip"
_SHA256 = "ab" * 32
_MAX_RAW_BYTES = 25_165_824  # `.env.example`'s ANALYSIS_MAX_RAW_BYTES
_EXTRACTED_AT = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)
_SILENCE = "participant.group_silence_episodes"

#: The fields of the version 1 document, each of which must stay where it was (additive only).
_VERSION_1_PATHS = (
    "game_id",
    "point_of_view_profile_id",
    "world_time_ms",
    "engine",
    "source_recording",
    "extracted_at",
    "participants",
)


class _Wrapped:
    """The real extractor, with one thing changed per test."""

    def __init__(
        self,
        inner: Aoe2RecExtractor,
        *,
        build: int | None = None,
        dependencies: dict[str, str] | None = None,
    ) -> None:
        self._inner = inner
        self._build = build
        self.engine_name = inner.engine_name
        self.engine_version = inner.engine_version
        self.engine_dependencies = (
            inner.engine_dependencies if dependencies is None else dependencies
        )

    def extract(self, zip_bytes: bytes) -> Any:
        return self._inner.extract(zip_bytes)

    def events(self, zip_bytes: bytes) -> Iterator[CanonicalEvent]:
        for event in self._inner.events(zip_bytes):
            if self._build is not None and event.kind is EventKind.MATCH_STARTED:
                assert isinstance(event.payload, MatchStartedPayload)
                event = dataclasses.replace(
                    event, payload=dataclasses.replace(event.payload, build=self._build)
                )
            yield event


def _build(extractor: Any) -> dict[str, Any]:
    return build_document(
        extractor,
        _FIXTURE_ZIP.read_bytes(),
        game_id=_GAME_ID,
        object_key=_OBJECT_KEY,
        zip_sha256=_SHA256,
        extracted_at=_EXTRACTED_AT,
    )


@pytest.fixture(scope="module")
def extractor() -> Aoe2RecExtractor:
    return Aoe2RecExtractor(max_raw_bytes=_MAX_RAW_BYTES)


@pytest.fixture(scope="module")
def document(extractor: Aoe2RecExtractor) -> dict[str, Any]:
    return _build(extractor)


# --- additive only ------------------------------------------------------------------------------


def test_the_document_is_the_next_schema_version_with_the_four_blocks_added(
    document: dict[str, Any],
) -> None:
    assert document["schema_version"] == SCHEMA_VERSION == 2
    for block in ("identity", "provenance", "inferred", "knowledge_gaps", "envelope"):
        assert block in document


def test_every_version_1_field_is_still_at_its_path(document: dict[str, Any]) -> None:
    for path in _VERSION_1_PATHS:
        assert path in document, path
    assert set(document["engine"]) == {"name", "version", "deps"}
    assert set(document["source_recording"]) == {"object_key", "sha256"}
    assert document["game_id"] == _GAME_ID
    assert document["source_recording"] == {"object_key": _OBJECT_KEY, "sha256": _SHA256}


def test_the_participants_are_exactly_what_the_timeline_carried(
    document: dict[str, Any], extractor: Aoe2RecExtractor
) -> None:
    timeline = extractor.extract(_FIXTURE_ZIP.read_bytes())
    participants = document["participants"]

    assert [p["profile_id"] for p in participants] == [p.profile_id for p in timeline.participants]
    assert [p["age_up_commands"] for p in participants] == [
        {str(key): value for key, value in p.age_up_commands.items()} for p in timeline.participants
    ]
    assert document["world_time_ms"] == timeline.world_time_ms


def test_the_committed_golden_timeline_is_still_reproduced_field_for_field(
    document: dict[str, Any],
) -> None:
    golden = json.loads(_FIXTURE_TIMELINE.read_text(encoding="utf-8"))
    for key, value in golden.items():
        if key in document:
            assert document[key] == value, key


def test_the_document_is_json_native_so_the_validator_sees_what_the_reader_parses(
    document: dict[str, Any],
) -> None:
    assert json.loads(json.dumps(document)) == document


def test_the_wall_clock_time_is_under_the_envelope_and_at_its_legacy_path(
    document: dict[str, Any],
) -> None:
    assert document["envelope"] == {"extracted_at": _EXTRACTED_AT.isoformat()}
    assert document["extracted_at"] == document["envelope"]["extracted_at"]


# --- FR-044: the dependency record -------------------------------------------------------------


def test_the_dependency_record_is_populated_and_is_the_one_the_adapter_built(
    document: dict[str, Any], extractor: Aoe2RecExtractor
) -> None:
    assert document["engine"]["deps"]
    assert document["engine"]["deps"] == dict(extractor.engine_dependencies)
    assert document["identity"]["parser_dependencies"] == document["engine"]["deps"]


def test_an_empty_dependency_record_is_not_built(extractor: Aoe2RecExtractor) -> None:
    with pytest.raises(ValueError, match="dependenc"):
        _build(_Wrapped(extractor, dependencies={}))


# --- FR-040: identity ---------------------------------------------------------------------------


def test_the_identity_names_every_component_and_its_digest_recomputes(
    document: dict[str, Any], extractor: Aoe2RecExtractor
) -> None:
    identity = document["identity"]

    assert identity["recording"] == {"object_key": _OBJECT_KEY, "sha256": _SHA256}
    assert identity["parser"] == {
        "name": extractor.engine_name,
        "version": extractor.engine_version,
    }
    assert identity["reconstruction_engine"] == NOT_APPLICABLE
    assert identity["analytics"] == ANALYTICS_VERSION
    assert identity["analytics"] != NOT_APPLICABLE
    assert AnalysisIdentity.from_block(identity).digest == identity["digest"]


def test_the_identity_names_the_snapshot_of_the_recordings_build(document: dict[str, Any]) -> None:
    knowledge = document["identity"]["knowledge"]

    assert set(knowledge) == {"source", "source_version", "describes_build", "digest"}
    assert knowledge["describes_build"] == 180059  # the fixture's build (fixtures README)


def test_a_build_with_no_snapshot_is_recorded_and_gapped_not_substituted(
    extractor: Aoe2RecExtractor,
) -> None:
    """FR-027: the absence is an explicit record in the identity and one blocking gap, and the
    nearest snapshot is not used in its place."""
    document = _build(_Wrapped(extractor, build=1))

    assert document["identity"]["knowledge"] == {"absent": "no-snapshot-for-build", "build": 1}
    assert [gap["cause"] for gap in document["knowledge_gaps"]] == ["no-snapshot-for-build"]
    gap = document["knowledge_gaps"][0]
    assert gap["severity"] == "blocking"
    assert gap["build"] == 1
    assert gap["entity"] is None
    assert gap["prevents"]


def test_a_changed_knowledge_component_changes_the_digest(
    document: dict[str, Any], extractor: Aoe2RecExtractor
) -> None:
    other = _build(_Wrapped(extractor, build=1))

    assert other["identity"]["digest"] != document["identity"]["digest"]


# --- FR-007, FR-009: every value says where it came from ----------------------------------------


def test_every_provenance_entry_carries_its_register_tier_a_method_and_known_inputs(
    document: dict[str, Any],
) -> None:
    provenance = document["provenance"]
    assert provenance

    for datum, entry in provenance.items():
        register_entry = REGISTER[datum]
        assert register_entry.status == "published" or datum == _SILENCE
        assert register_entry.tier is not None
        assert entry["tier"] == register_entry.tier.value
        assert re.fullmatch(r"[a-z][a-z0-9_.-]*@\d+(\.\d+)*", entry["method"]), entry["method"]
        assert all(source in REGISTER.entries for source in entry["inputs"])
        assert not entry["inputs"] or entry["tier"] != Tier.OBSERVED.value


def test_every_published_datum_the_document_carries_has_a_provenance_entry(
    document: dict[str, Any],
) -> None:
    carried = {
        "game_id": "match.game_id",
        "point_of_view_profile_id": "match.point_of_view_profile_id",
        "world_time_ms": "match.world_time_ms",
    }
    for key, datum in carried.items():
        assert key in document
        assert datum in document["provenance"], datum
    for datum in (
        "engine.name",
        "engine.version",
        "engine.dependencies",
        "source_recording.object_key",
        "source_recording.sha256",
        "participant.civ_id",
        "participant.age_up_commands",
        "participant.villagers_ordered",
        "participant.actions_per_minute",
    ):
        assert datum in document["provenance"], datum


def test_a_datum_decoded_by_this_repository_is_not_claimed_as_observed(
    document: dict[str, Any],
) -> None:
    assert document["provenance"]["participant.villagers_ordered"]["tier"] == "decoded"
    assert document["provenance"]["participant.age_up_commands"]["tier"] == "observed"


def test_every_published_register_path_resolves_to_a_method() -> None:
    """A datum the register publishes at a document path but no method covers fails here, at the
    change that publishes it, instead of at an analysis (FR-009)."""
    for entry in REGISTER:
        if entry.status == "published" and entry.path is not None:
            if entry.id.startswith("document."):
                continue  # `schema_version` is exempt from the validator and carries no entry
            assert _method_for(entry.id)


def test_a_published_datum_with_no_assigned_method_is_refused() -> None:
    with pytest.raises(ValueError, match="no method"):
        _method_for("coaching.advice")


# --- FR-010, FR-011, FR-013: the inferred block -------------------------------------------------


def test_the_only_inferred_datum_is_group_silence_and_it_is_not_outside_the_inferred_block(
    document: dict[str, Any],
) -> None:
    assert set(document["inferred"]) == {_SILENCE}
    assert _SILENCE not in json.dumps(
        {key: value for key, value in document.items() if key not in ("inferred", "provenance")}
    )
    assert document["provenance"][_SILENCE]["tier"] == "inferred"
    assert document["provenance"][_SILENCE]["method"] in ANALYTICS_VERSION


def test_every_inferred_instance_carries_a_confidence_and_the_registers_non_claim(
    document: dict[str, Any],
) -> None:
    instances = document["inferred"][_SILENCE]
    assert instances, "the fixture is expected to produce episodes; an empty block proves nothing"
    non_claim = REGISTER[_SILENCE].non_claim

    for instance in instances:
        assert instance["confidence"]["level"] in {"low", "medium"}  # never high: the blind spot
        assert instance["confidence"]["basis"].strip()
        assert not isinstance(instance["confidence"]["level"], (int, float))
        assert instance["non_claim"] == non_claim
        assert "casualty" in instance["non_claim"]


def test_no_inferred_field_is_named_like_a_loss(document: dict[str, Any]) -> None:
    """FR-010, FR-012: a name states what was measured. Nothing here may read as a death or a
    loss count."""
    banned = ("lost", "loss", "dead", "death", "killed", "casualt", "surviv")
    for instance in document["inferred"][_SILENCE]:
        for field in instance:
            assert not any(word in field for word in banned), field


def test_a_stream_with_no_episode_publishes_no_inferred_instance_and_no_provenance_for_it(
    extractor: Aoe2RecExtractor,
) -> None:
    class _NoEpisodes(_Wrapped):
        def events(self, zip_bytes: bytes) -> Iterator[CanonicalEvent]:
            return (
                event
                for event in super().events(zip_bytes)
                if event.kind is not EventKind.UNITS_COMMANDED
            )

    document = _build(_NoEpisodes(extractor))

    assert document["inferred"] == {}
    assert _SILENCE not in document["provenance"]


# --- FR-035: gaps -------------------------------------------------------------------------------


def test_each_gap_carries_the_fields_the_contract_names(document: dict[str, Any]) -> None:
    for gap in document["knowledge_gaps"]:
        assert set(gap) == {
            "entity",
            "field",
            "build",
            "civilisation",
            "cause",
            "prevents",
            "severity",
        }
        assert gap["severity"] in {"blocking", "informational"}
        assert (gap["severity"] == "blocking") == bool(gap["prevents"])


# --- boundaries ---------------------------------------------------------------------------------


def test_the_builder_never_loads_the_parser() -> None:
    """Importing `aoe2stats_analyzer.extract` is how `api/analyze.py` reaches it on every request;
    the parser wheel stays behind the composition root's own lazy import (constitution V)."""
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys\n"
            "import aoe2stats_analyzer.extract\n"
            "assert 'aoe2rec_py' not in sys.modules, 'the parser wheel was imported'\n"
            "print('ok')\n",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "ok"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "T656: the validator looks register paths up exactly, but the register publishes wildcard "
        "paths (`engine.deps.*`, `participants[].age_up_commands.*`), and the group-silence entry "
        "is still planned in the packaged register"
    ),
)
def test_a_real_document_passes_the_real_register(document: dict[str, Any]) -> None:
    validate_document(document)
