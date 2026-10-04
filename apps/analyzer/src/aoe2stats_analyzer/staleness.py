"""Whether a published analysis is stale - the one function the analyzer and the API share (T666g).

**Why there is exactly one.** FR-042 makes the identity digest the test: a published row is stale
when the identity an analysis would carry now is not the one it was produced under. Two callers ask
that question. `run.py`'s `_is_stale` asks it to decide whether to recompute; `apps/api`'s match
detail asks it to decide whether the browser offers the Recompute button. A button that offers a
recompute the analyzer would then skip - or hides one it would run - is a defect, and two copies of
a condition drift. So both call `is_stale` below, and a test in `apps/api/tests` pins that their
answers are equal for the same row.

**What it does, and does not, do.** It reads nothing: the caller passes the `match_analyses` row,
the retained-recording row (already loaded - the identity's `recording` component is that row's
object key and checksum) and a description of the installed engine. The current digest comes from
`extract.current_identity_digest`, which resolves the knowledge snapshot for the row's recorded
build from package data. There is no object-store read and no parse, so a request on a fresh
published match costs two small row reads and a hash.

**On the API's request path (FR-049).** The API imports this module lazily, from one function in
`routers/matches.py`. What that adds to a request is cached, build-independent resolution -
`snapshot_for` is `functools.cache`d for the process's life and answers from the installed snapshot
tree - and the installed engine's version record, read from distribution metadata. It is not
request-path analysis work: nothing is fetched, nothing is parsed, no engine is loaded
(`aoe2rec_py` is never imported here, which `apps/api/tests/test_engine_isolation.py` asserts), and
it spends none of the capture budget. `tests/architecture/test_feature_006_boundaries.py` allows
that one import from that one file and refuses any other.

**It raises, and the caller decides what that means.** A snapshot that cannot be loaded, fails its
digest, or an empty dependency record is a deployment fault, not staleness (T666b). The analyzer
lets it propagate before any recompute; the API logs it and reports not stale rather than failing
the match page for a button.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from aoe2stats_analyzer.extract import EngineIdentity, current_identity_digest
from aoe2stats_replay_engine.dependencies import read_engine_dependencies
from aoe2stats_storage.models import MatchAnalysis, MatchAnalysisState, RetainedRecording

__all__ = ["InstalledEngine", "installed_engine", "is_stale", "retry_window_open"]


@dataclass(frozen=True)
class InstalledEngine:
    """The engine as the installed distributions describe it: what `Aoe2RecExtractor.__init__`
    reads, without importing the extractor or the native module behind it."""

    engine_name: str
    engine_version: str
    engine_dependencies: dict[str, str]


def installed_engine(engine_name: str) -> InstalledEngine:
    """The named engine's version and dependency record, built by the same function the extractor
    uses (`read_engine_dependencies`), so the two cannot describe different engines. Reads
    distribution metadata only; raises `EngineDependencyError` if a requirement is not installed."""
    record = read_engine_dependencies(engine_name)
    return InstalledEngine(
        engine_name=engine_name,
        engine_version=record.engine_version,
        engine_dependencies=record.as_mapping(),
    )


def retry_window_open(analysis: MatchAnalysis, *, now: datetime) -> bool:
    """T666c: a published row whose recompute was refused is left alone until `lease_expires_at`
    passes - a published row holds no lease, so the column carries that window. While it is open a
    recompute would be skipped, so the row is not offered one."""
    return (
        analysis.state is MatchAnalysisState.PUBLISHED
        and analysis.lease_expires_at is not None
        and analysis.lease_expires_at > now
    )


def is_stale(
    analysis: MatchAnalysis,
    retained: RetainedRecording | None,
    *,
    engine: EngineIdentity,
    now: datetime,
) -> bool:
    """True when a request for this match would recompute it (FR-042, T657a, T666b).

    - Not `published`: never stale; there is nothing to replace.
    - No retained-recording row: not stale. A recording that cannot be recomputed is not stale, and
      offering a recompute that can only fail is the wrong answer.
    - A retry window is open (`retry_window_open`): not stale; the recompute would be skipped.
    - No stored digest or no recorded build: stale. The row was published before either existed and
      recomputes once.
    - Otherwise stale exactly when the digest an analysis would carry now - computed from the
      retained recording's key and checksum, the row's recorded build and the engine - differs from
      the stored one. Any of parser, dependencies, knowledge or analytics can change it.
    """
    if analysis.state is not MatchAnalysisState.PUBLISHED or retained is None:
        return False
    if retry_window_open(analysis, now=now):
        return False
    if analysis.identity_digest is None or analysis.recording_build is None:
        return True
    current = current_identity_digest(
        engine,
        recording={"object_key": retained.object_key, "sha256": retained.zip_sha256},
        build=analysis.recording_build,
    )
    return current != analysis.identity_digest
