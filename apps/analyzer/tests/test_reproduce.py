"""Tests for `aoe2stats_analyzer.reproduce` (T658, FR-043, FR-042, FR-038).

`test_reproducibility.py` (T660) holds the SC-004 and SC-005 scenarios through `run_once`. This
file is the refusal surface: every way an identity cannot be reproduced here is a test that names
the reason, because the only honest outcomes are *identical* or *cannot reproduce here because ...*,
and a refusal that does not say what differs is the silent rewrite FR-042 forbids in another shape.

Every refusal is raised **before** the recording is parsed except the two that can only be known
after (a rebuild carrying another identity); none of them needs a database.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import socket
from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

import pytest

from aoe2stats_analyzer.extract import ANALYTICS_VERSION, build_document, compared_body
from aoe2stats_analyzer.reproduce import ReproductionRefused, reproduce
from aoe2stats_core.truth.identity import AnalysisIdentity
from aoe2stats_knowledge import snapshot
from aoe2stats_replay_engine.aoe2rec import Aoe2RecExtractor

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURE_ZIP = _REPO_ROOT / "tests" / "fixtures" / "replays" / "AgeIIDE_Replay_500546441.zip"
_GAME_ID = 500_546_441
_KEY = f"retained-recordings/{_GAME_ID}/196240.zip"
_MAX_RAW_BYTES = 25_165_824
_REAL_SNAPSHOT_DIRECTORY = "aoe2techtree-180059"


@pytest.fixture(autouse=True)
def _clear_snapshot_resolution_caches() -> Iterator[None]:
    for cache in (
        snapshot.load_all_snapshots,
        snapshot.load_resolvable_snapshots,
        snapshot.snapshot_for,
    ):
        cache.cache_clear()
    yield
    for cache in (
        snapshot.load_all_snapshots,
        snapshot.load_resolvable_snapshots,
        snapshot.snapshot_for,
    ):
        cache.cache_clear()


class _ReadOnlyStore:
    """Only `get`: a `put` or `delete` is an `AttributeError`, so a write cannot happen quietly.
    Records every key read."""

    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = dict(objects)
        self.reads: list[str] = []

    async def get(self, key: str) -> bytes:
        self.reads.append(key)
        return self.objects[key]


class _RecordingStore(_ReadOnlyStore):
    """The same, with the write half present, so a test can prove none of it is called."""

    def __init__(self, objects: dict[str, bytes]) -> None:
        super().__init__(objects)
        self.writes: list[str] = []

    async def put(self, key: str, body: bytes, *, content_type: str = "") -> None:
        self.writes.append(key)

    async def delete(self, key: str) -> None:
        self.writes.append(key)


@dataclass(frozen=True, slots=True)
class _Original:
    extractor: Aoe2RecExtractor
    document: dict[str, Any]
    identity: AnalysisIdentity
    zip_bytes: bytes

    def store(self) -> _RecordingStore:
        return _RecordingStore({_KEY: self.zip_bytes})


@pytest.fixture(scope="module")
def original() -> _Original:
    """One real analysis of the committed recording, built once for the module."""
    zip_bytes = _FIXTURE_ZIP.read_bytes()
    extractor = Aoe2RecExtractor(max_raw_bytes=_MAX_RAW_BYTES)
    document = build_document(
        extractor,
        zip_bytes,
        game_id=_GAME_ID,
        object_key=_KEY,
        zip_sha256=hashlib.sha256(zip_bytes).hexdigest(),
        extracted_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    return _Original(
        extractor=extractor,
        document=document,
        identity=AnalysisIdentity.from_block(document["identity"]),
        zip_bytes=zip_bytes,
    )


def _refusal(exc_info: pytest.ExceptionInfo[ReproductionRefused]) -> str:
    message = str(exc_info.value)
    assert message.startswith("cannot reproduce here because: ")
    return message


# --- The matching identity, and what reproduction may not do -----------------------------------


async def test_the_matching_identity_reproduces_a_body_equal_to_the_originals(
    original: _Original,
) -> None:
    reproduced = await reproduce(
        original.identity, object_store=original.store(), extractor=original.extractor
    )

    assert compared_body(json.loads(reproduced)) == compared_body(original.document)
    assert json.loads(reproduced)["identity"] == original.document["identity"]


async def test_reproduction_reaches_no_network_and_writes_nothing(
    original: _Original, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("reproduce() attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    store = original.store()

    await reproduce(original.identity, object_store=store, extractor=original.extractor)

    assert store.reads == [_KEY]
    assert store.writes == []
    assert store.objects == {_KEY: original.zip_bytes}


async def test_a_store_that_can_only_read_is_enough(original: _Original) -> None:
    store = _ReadOnlyStore({_KEY: original.zip_bytes})

    await reproduce(original.identity, object_store=store, extractor=original.extractor)

    assert not hasattr(store, "put")


# --- Refusals about the installed code ---------------------------------------------------------


async def test_a_different_parser_version_is_refused_and_named(original: _Original) -> None:
    identity = replace(original.identity, parser_version="0.0.1")
    store = original.store()

    with pytest.raises(ReproductionRefused) as exc_info:
        await reproduce(identity, object_store=store, extractor=original.extractor)

    message = _refusal(exc_info)
    assert "0.0.1" in message
    assert original.extractor.engine_version in message
    assert store.reads == [], "a refusal about the installed code must not touch the store"


async def test_a_different_parser_name_is_refused_and_named(original: _Original) -> None:
    identity = replace(original.identity, parser_name="some-other-parser")

    with pytest.raises(ReproductionRefused) as exc_info:
        await reproduce(identity, object_store=original.store(), extractor=original.extractor)

    message = _refusal(exc_info)
    assert "some-other-parser" in message
    assert original.extractor.engine_name in message


async def test_one_dependency_at_another_version_is_refused_and_named(original: _Original) -> None:
    name = sorted(original.identity.parser_dependencies)[0]
    recorded = {**original.identity.parser_dependencies, name: "0.0.0+elsewhere"}
    identity = replace(original.identity, parser_dependencies=recorded)

    with pytest.raises(ReproductionRefused) as exc_info:
        await reproduce(identity, object_store=original.store(), extractor=original.extractor)

    message = _refusal(exc_info)
    assert name in message
    assert "0.0.0+elsewhere" in message
    assert original.extractor.engine_dependencies[name] in message
    assert len(exc_info.value.reasons) == 1, "only the one dependency differs"


async def test_a_dependency_the_identity_names_but_is_not_installed_is_refused(
    original: _Original,
) -> None:
    recorded = {**original.identity.parser_dependencies, "a-package-nobody-installed": "1.2.3"}
    identity = replace(original.identity, parser_dependencies=recorded)

    with pytest.raises(ReproductionRefused) as exc_info:
        await reproduce(identity, object_store=original.store(), extractor=original.extractor)

    message = _refusal(exc_info)
    assert "a-package-nobody-installed" in message
    assert "not installed here" in message


async def test_a_dependency_installed_but_absent_from_the_identity_is_refused(
    original: _Original,
) -> None:
    name = sorted(original.identity.parser_dependencies)[0]
    recorded = {k: v for k, v in original.identity.parser_dependencies.items() if k != name}
    assert recorded, "the contrast needs the record to stay non-empty (FR-044)"
    identity = replace(original.identity, parser_dependencies=recorded)

    with pytest.raises(ReproductionRefused) as exc_info:
        await reproduce(identity, object_store=original.store(), extractor=original.extractor)

    message = _refusal(exc_info)
    assert name in message
    assert "does not name it" in message


async def test_a_different_analytics_version_is_refused_not_rebuilt_under_the_old_name(
    original: _Original,
) -> None:
    """The decision (module docstring): the installed analytics code is the only one there is, so
    reproducing under an older analytics version would be the new code under the old name."""
    identity = replace(original.identity, analytics="coverage@0+older")
    assert identity.analytics != ANALYTICS_VERSION

    with pytest.raises(ReproductionRefused) as exc_info:
        await reproduce(identity, object_store=original.store(), extractor=original.extractor)

    message = _refusal(exc_info)
    assert "coverage@0+older" in message
    assert ANALYTICS_VERSION in message


async def test_every_difference_is_named_not_only_the_first(original: _Original) -> None:
    identity = replace(original.identity, parser_version="0.0.1", analytics="coverage@0+older")

    with pytest.raises(ReproductionRefused) as exc_info:
        await reproduce(identity, object_store=original.store(), extractor=original.extractor)

    assert len(exc_info.value.reasons) == 2


# --- Refusals about the named snapshot ---------------------------------------------------------


def _with_knowledge(original: _Original, **changes: Any) -> AnalysisIdentity:
    return replace(original.identity, knowledge={**original.identity.knowledge, **changes})


async def test_a_snapshot_that_is_not_installed_is_refused_and_named(original: _Original) -> None:
    identity = _with_knowledge(original, source_version="a-revision-nobody-packaged")
    store = original.store()

    with pytest.raises(ReproductionRefused) as exc_info:
        await reproduce(identity, object_store=store, extractor=original.extractor)

    message = _refusal(exc_info)
    assert "a-revision-nobody-packaged" in message
    assert "is not installed" in message
    assert store.reads == []


async def test_a_snapshot_installed_with_another_digest_is_refused_and_both_are_named(
    original: _Original,
) -> None:
    named_digest = "sha256:" + "0" * 64
    identity = _with_knowledge(original, digest=named_digest)

    with pytest.raises(ReproductionRefused) as exc_info:
        await reproduce(identity, object_store=original.store(), extractor=original.extractor)

    message = _refusal(exc_info)
    assert named_digest in message
    assert original.identity.knowledge["digest"] in message
    assert "is installed with digest" in message


async def test_a_packaged_snapshot_that_no_longer_matches_its_own_digest_is_refused(
    original: _Original, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "snapshots"
    shutil.copytree(
        Path(str(snapshot._snapshots_root())) / _REAL_SNAPSHOT_DIRECTORY,
        root / _REAL_SNAPSHOT_DIRECTORY,
    )
    rules = root / _REAL_SNAPSHOT_DIRECTORY / "rules.json"
    rules.write_bytes(rules.read_bytes() + b" ")
    monkeypatch.setattr(snapshot, "_snapshots_root", lambda: root)

    with pytest.raises(ReproductionRefused) as exc_info:
        await reproduce(
            original.identity, object_store=original.store(), extractor=original.extractor
        )

    assert "fails its own verification" in _refusal(exc_info)


async def test_a_demoted_snapshot_is_still_resolvable_by_the_identity_that_names_it(
    original: _Original, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The contrast to the refusals above: not being promoted is not being absent (SC-005). The
    named snapshot is demoted in place (its digest covers only rules.json and effects.toml), and the
    identity naming it still reproduces."""
    root = tmp_path / "snapshots"
    shutil.copytree(
        Path(str(snapshot._snapshots_root())) / _REAL_SNAPSHOT_DIRECTORY,
        root / _REAL_SNAPSHOT_DIRECTORY,
    )
    identity_file = root / _REAL_SNAPSHOT_DIRECTORY / snapshot.IDENTITY_FILENAME
    text = identity_file.read_text(encoding="utf-8")
    assert "promoted = true" in text
    identity_file.write_text(text.replace("promoted = true", "promoted = false"), encoding="utf-8")
    monkeypatch.setattr(snapshot, "_snapshots_root", lambda: root)

    reproduced = await reproduce(
        original.identity, object_store=original.store(), extractor=original.extractor
    )

    assert compared_body(json.loads(reproduced)) == compared_body(original.document)


async def test_an_identity_recording_no_snapshot_is_refused_once_one_is_promoted(
    original: _Original,
) -> None:
    """The one refusal that needs the rebuild: an identity whose knowledge is the explicit absence
    of a snapshot for the build, reproduced where a snapshot for it is now promoted, would carry
    that snapshot - another identity. The rebuild's own digest is what says so."""
    build = original.identity.knowledge["describes_build"]
    identity = replace(
        original.identity, knowledge={"absent": "no-snapshot-for-build", "build": build}
    )

    with pytest.raises(ReproductionRefused) as exc_info:
        await reproduce(identity, object_store=original.store(), extractor=original.extractor)

    message = _refusal(exc_info)
    assert "carries a different identity" in message
    assert "knowledge" in message


# --- Refusals about the recording --------------------------------------------------------------


async def test_a_recording_with_another_checksum_is_refused_and_both_are_named(
    original: _Original,
) -> None:
    tampered = original.zip_bytes + b"\x00"
    store = _RecordingStore({_KEY: tampered})

    with pytest.raises(ReproductionRefused) as exc_info:
        await reproduce(original.identity, object_store=store, extractor=original.extractor)

    message = _refusal(exc_info)
    assert hashlib.sha256(tampered).hexdigest() in message
    assert original.identity.recording["sha256"] in message
    assert store.writes == []


async def test_a_recording_missing_from_the_store_is_refused_and_its_key_named(
    original: _Original,
) -> None:
    store = _RecordingStore({})

    with pytest.raises(ReproductionRefused) as exc_info:
        await reproduce(original.identity, object_store=store, extractor=original.extractor)

    assert _KEY in _refusal(exc_info)


async def test_a_store_outage_is_not_a_refusal(original: _Original) -> None:
    class _Down:
        async def get(self, key: str) -> bytes:
            raise ConnectionError("the store is unreachable")

    with pytest.raises(ConnectionError):
        await reproduce(original.identity, object_store=_Down(), extractor=original.extractor)


async def test_a_store_reporting_no_such_key_is_a_refusal(original: _Original) -> None:
    class _NoSuchKey(Exception):
        response: ClassVar[dict[str, Any]] = {"Error": {"Code": "NoSuchKey"}}

    class _Empty:
        async def get(self, key: str) -> bytes:
            raise _NoSuchKey(key)

    with pytest.raises(ReproductionRefused) as exc_info:
        await reproduce(original.identity, object_store=_Empty(), extractor=original.extractor)

    assert _KEY in _refusal(exc_info)


async def test_an_identity_recording_no_checksum_is_refused(original: _Original) -> None:
    identity = replace(original.identity, recording={"object_key": _KEY})

    with pytest.raises(ReproductionRefused) as exc_info:
        await reproduce(identity, object_store=original.store(), extractor=original.extractor)

    assert "sha256" in _refusal(exc_info)


async def test_a_key_that_is_not_a_retained_recording_key_needs_a_game_id(
    original: _Original,
) -> None:
    key = "somewhere/else.zip"
    identity = replace(
        original.identity,
        recording={"object_key": key, "sha256": original.identity.recording["sha256"]},
    )
    store = _RecordingStore({key: original.zip_bytes})

    with pytest.raises(ReproductionRefused) as exc_info:
        await reproduce(identity, object_store=store, extractor=original.extractor)
    assert "match id cannot be read" in _refusal(exc_info)

    reproduced = await reproduce(
        identity, object_store=store, extractor=original.extractor, game_id=_GAME_ID
    )
    assert json.loads(reproduced)["game_id"] == _GAME_ID
