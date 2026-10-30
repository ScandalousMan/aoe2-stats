"""T746 / T767 / T768 / T769 / T770 / SC-005: an analysis published under a superseded knowledge
snapshot still reproduces.

A promoted snapshot is never edited (FR-025), so build 185872's civilisations were modelled in a
second snapshot that names the digest it supersedes (T746), twelve more in a third (T767) and
twelve more in a fourth (T768). Resolution by build now answers the fourth; the analyses published
before it name the first, the second or the third, and `reproduce` must still rebuild exactly those
bytes from the identity they recorded - not the current snapshot's answer (FR-038).

The "published" analysis is built with the superseded snapshot pinned, which is what the build
resolved to when it was published. The contrast cases prove the snapshots genuinely differ for this
recording, so the equality below is not a vacuous one.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from aoe2stats_analyzer.extract import build_document, compared_body
from aoe2stats_analyzer.reproduce import ReproductionRefused, reproduce
from aoe2stats_core.truth.identity import AnalysisIdentity
from aoe2stats_knowledge import snapshot
from aoe2stats_replay_engine.aoe2rec import Aoe2RecExtractor
from aoe2stats_storage.objects import ObjectNotFound

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURE_ZIP = _REPO_ROOT / "tests" / "fixtures" / "replays" / "AgeIIDE_Replay_511523321.zip"
_GAME_ID = 511_523_321
_KEY = f"retained-recordings/{_GAME_ID}/5632575.zip"
_BUILD = 185872
_MAX_RAW_BYTES = 25_165_824  # `.env.example`'s ANALYSIS_MAX_RAW_BYTES
_FIRST_DIGEST = "sha256:1c77d7cb5034b48dcb15641370512854a222d5f7d40baaa6129fb1b1c56fca5a"
_SECOND_DIGEST = "sha256:becd35a158dafb72c304aeb07bae66347b4442f62d209d8cedb23d0c1f34f004"
_THIRD_DIGEST = "sha256:a4f213b6e84f90ee88a916929a136165c3979f214a191556877669dd0a92b4db"
_FOURTH_DIGEST = "sha256:c24448836cade9ff724ac32935a52280a447df7278cb8cfe3f7cecd58dbf37ae"
_FIFTH_DIGEST = "sha256:93d084ea8886b4c2d98f67a7f02524f107ffab3c3bcb29142389ceac226dc263"
_SUPERSEDED_DIGESTS = (_FIRST_DIGEST, _SECOND_DIGEST, _THIRD_DIGEST, _FOURTH_DIGEST, _FIFTH_DIGEST)


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


class _Store:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects

    async def get(self, key: str) -> bytes:
        if key not in self.objects:
            raise ObjectNotFound(key)
        return self.objects[key]


def _build(extractor: Aoe2RecExtractor, zip_bytes: bytes) -> dict[str, Any]:
    return build_document(
        extractor,
        zip_bytes,
        game_id=_GAME_ID,
        object_key=_KEY,
        zip_sha256=hashlib.sha256(zip_bytes).hexdigest(),
        extracted_at=datetime(2026, 10, 8, 12, 0, tzinfo=UTC),
    )


def _snapshot_by_digest(digest: str) -> snapshot.Snapshot:
    (found,) = (s for s in snapshot.load_all_snapshots() if s.identity.digest == digest)
    return found


def _first_snapshot() -> snapshot.Snapshot:
    return _snapshot_by_digest(_FIRST_DIGEST)


@pytest.fixture(scope="module")
def zip_bytes() -> bytes:
    return _FIXTURE_ZIP.read_bytes()


@pytest.fixture(scope="module")
def extractor() -> Aoe2RecExtractor:
    return Aoe2RecExtractor(max_raw_bytes=_MAX_RAW_BYTES)


@pytest.mark.parametrize(
    "superseded_digest", _SUPERSEDED_DIGESTS, ids=["first", "second", "third", "fourth", "fifth"]
)
async def test_an_analysis_published_under_a_superseded_snapshot_reproduces_byte_for_byte(
    superseded_digest: str, zip_bytes: bytes, extractor: Aoe2RecExtractor
) -> None:
    with snapshot.pinned_snapshot(_snapshot_by_digest(superseded_digest)):
        published = _build(extractor, zip_bytes)
    identity = AnalysisIdentity.from_block(published["identity"])
    assert identity.knowledge["digest"] == superseded_digest
    current = snapshot.snapshot_for(_BUILD)
    assert isinstance(current, snapshot.Snapshot)
    assert current.identity.digest not in _SUPERSEDED_DIGESTS, (
        "the build must have moved on to a newer one"
    )

    reproduced = await reproduce(
        identity, object_store=_Store({_KEY: zip_bytes}), extractor=extractor
    )

    assert json.loads(reproduced)["identity"] == published["identity"]
    assert compared_body(json.loads(reproduced)) == compared_body(published)


async def test_the_build_now_resolves_to_another_snapshot_so_the_equality_is_not_vacuous(
    zip_bytes: bytes, extractor: Aoe2RecExtractor
) -> None:
    """Without the pin the same recording is analysed under the superseding snapshot: another
    identity, and the civilisation gaps the first one reported are gone."""
    with snapshot.pinned_snapshot(_first_snapshot()):
        published = _build(extractor, zip_bytes)
    current = _build(extractor, zip_bytes)

    assert published["identity"]["knowledge"]["digest"] == _FIRST_DIGEST
    assert current["identity"]["knowledge"]["digest"] != _FIRST_DIGEST
    assert current["identity"]["digest"] != published["identity"]["digest"]
    first_causes = {g["cause"] for g in published["knowledge_gaps"]}
    current_causes = [g["cause"] for g in current["knowledge_gaps"]]
    assert "civilisation-not-modelled" in first_causes
    assert "civilisation-not-modelled" not in current_causes


async def test_the_second_snapshot_reported_a_gate_gap_the_third_closes(
    zip_bytes: bytes, extractor: Aoe2RecExtractor
) -> None:
    """T767: the recording places building 490, which the pack does not name. Under the second
    snapshot that is an `entity-absent` gap for the Sicilians; the third carries the alias
    (FR-022d) that makes it the pack's Gate, so the same recording reports no `entity-absent` gap
    for it."""
    with snapshot.pinned_snapshot(_snapshot_by_digest(_SECOND_DIGEST)):
        published = _build(extractor, zip_bytes)
    current = _build(extractor, zip_bytes)

    def gate_gaps(document: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            gap
            for gap in document["knowledge_gaps"]
            if gap["entity"] == {"kind": "building", "id": "490"}
        ]

    assert gate_gaps(published), "the second snapshot must report building 490 as a gap"
    assert {gap["cause"] for gap in gate_gaps(published)} == {"entity-absent"}
    assert "entity-absent" not in {gap["cause"] for gap in gate_gaps(current)}


async def test_an_identity_naming_neither_snapshot_is_still_refused(
    zip_bytes: bytes, extractor: Aoe2RecExtractor
) -> None:
    """Contrast: keeping the superseded snapshot installed does not make any digest reproducible."""
    with snapshot.pinned_snapshot(_first_snapshot()):
        published = _build(extractor, zip_bytes)
    identity = AnalysisIdentity.from_block(published["identity"])
    stranger = replace(identity, knowledge={**identity.knowledge, "digest": "sha256:" + "0" * 64})

    with pytest.raises(ReproductionRefused, match="is installed with digest"):
        await reproduce(stranger, object_store=_Store({_KEY: zip_bytes}), extractor=extractor)
