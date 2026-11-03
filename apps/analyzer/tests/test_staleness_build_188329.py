"""T835: an analysis published under the absence record for build 188329 is stale once the build's
snapshot is installed (`aoe2stats_analyzer.staleness.is_stale`, FR-042).

Production analysed match 517988141 (build 188329) before any snapshot existed and recorded
`no-snapshot-for-build`. The identity digest names the absence record then; once
`aoe2techtree-188329-civilisations-56` is installed, the digest an analysis would carry names the
snapshot instead, so the stored one differs and the row recomputes on the next request. The cases
need no database: the row and the retained recording are transient model instances, and the
digest is the one `AnalysisIdentity` computes, with the same record `extract._knowledge_record`
writes for an absence.

The contrasts keep the test honest: an absence record for a build still without a snapshot stays
fresh, and a row published under the snapshot itself is fresh.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from aoe2stats_analyzer import extract, staleness
from aoe2stats_core.truth.identity import AnalysisIdentity
from aoe2stats_knowledge.snapshot import Snapshot, snapshot_for
from aoe2stats_storage.models import MatchAnalysis, MatchAnalysisState, RetainedRecording

_BUILD = 188329
_BUILD_WITHOUT_A_SNAPSHOT = 999_999
_NOW = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
_RECORDING = {"object_key": "recordings/517988141", "sha256": "ab" * 32}


@dataclass(frozen=True)
class _Engine:
    engine_name: str = "aoe2rec-py"
    engine_version: str = "1.0.0"
    engine_dependencies: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if self.engine_dependencies is None:
            object.__setattr__(self, "engine_dependencies", {"aoe2rec-py": "1.0.0"})


def _digest(knowledge: dict[str, Any]) -> str:
    engine = _Engine()
    assert engine.engine_dependencies is not None
    return AnalysisIdentity(
        recording=_RECORDING,
        parser_name=engine.engine_name,
        parser_version=engine.engine_version,
        parser_dependencies=engine.engine_dependencies,
        knowledge=knowledge,
        analytics=extract.ANALYTICS_VERSION,
    ).digest


def _published(digest: str, build: int) -> MatchAnalysis:
    return MatchAnalysis(
        game_id=517_988_141,
        state=MatchAnalysisState.PUBLISHED,
        point_of_view_profile_id=1,
        identity_digest=digest,
        recording_build=build,
        lease_expires_at=None,
    )


def _retained() -> RetainedRecording:
    return RetainedRecording(
        game_id=517_988_141,
        profile_id=1,
        object_key=_RECORDING["object_key"],
        zip_bytes=1,
        zip_sha256=_RECORDING["sha256"],
    )


def _stale(row: MatchAnalysis) -> bool:
    return staleness.is_stale(row, _retained(), engine=_Engine(), now=_NOW)


def test_build_188329_has_an_installed_snapshot() -> None:
    resolved = snapshot_for(_BUILD)
    assert isinstance(resolved, Snapshot)
    assert resolved.directory == "aoe2techtree-188329-civilisations-56"


def test_an_analysis_published_under_the_absence_record_for_188329_is_stale() -> None:
    absent = {"absent": "no-snapshot-for-build", "build": _BUILD}
    row = _published(_digest(absent), _BUILD)

    assert _stale(row) is True


def test_an_analysis_published_under_the_snapshot_is_fresh() -> None:
    resolved = snapshot_for(_BUILD)
    assert isinstance(resolved, Snapshot)
    row = _published(_digest(extract._knowledge_record(resolved)), _BUILD)

    assert _stale(row) is False


def test_an_absence_record_for_a_build_still_without_a_snapshot_stays_fresh() -> None:
    absent = {"absent": "no-snapshot-for-build", "build": _BUILD_WITHOUT_A_SNAPSHOT}
    row = _published(_digest(absent), _BUILD_WITHOUT_A_SNAPSHOT)

    assert _stale(row) is False
