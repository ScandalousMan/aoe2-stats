"""T746 / SC-005: an analysis published under a superseded knowledge snapshot still reproduces.

A promoted snapshot is never edited (FR-025), so build 185872's civilisations were modelled in a
second snapshot that names the digest it supersedes. Resolution by build now answers the second;
the analyses published before it name the first, and `reproduce` must still rebuild exactly those
bytes from the identity they recorded - not the current snapshot's answer (FR-038).

The "published" analysis is built with the first snapshot pinned, which is what the build resolved
to when it was published. The contrast cases prove the two snapshots genuinely differ for this
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


def _first_snapshot() -> snapshot.Snapshot:
    (first,) = (s for s in snapshot.load_all_snapshots() if s.identity.digest == _FIRST_DIGEST)
    return first


@pytest.fixture(scope="module")
def zip_bytes() -> bytes:
    return _FIXTURE_ZIP.read_bytes()


@pytest.fixture(scope="module")
def extractor() -> Aoe2RecExtractor:
    return Aoe2RecExtractor(max_raw_bytes=_MAX_RAW_BYTES)


async def test_an_analysis_published_under_the_superseded_snapshot_reproduces_byte_for_byte(
    zip_bytes: bytes, extractor: Aoe2RecExtractor
) -> None:
    with snapshot.pinned_snapshot(_first_snapshot()):
        published = _build(extractor, zip_bytes)
    identity = AnalysisIdentity.from_block(published["identity"])
    assert identity.knowledge["digest"] == _FIRST_DIGEST
    current = snapshot.snapshot_for(_BUILD)
    assert isinstance(current, snapshot.Snapshot)
    assert current.identity.digest != _FIRST_DIGEST, "the build must have moved on to a newer one"

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
