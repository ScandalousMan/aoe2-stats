"""The timing harness SC-008 and SC-015 are measured with (T909), built before any reconstruction
code exists. Its tests are `apps/analyzer/tests/test_analysis_time.py`.

No timing is committed and no figure appears here: a duration taken on one machine cannot be
compared on another (research R14). The baseline of a comparison is therefore the **same run's own
path without the new code**, timed beside the path with it, over the same recordings.

**API for T950 and T975** (import as ``from tests.analysis_time import ...``): ``tests`` is the
repository-root namespace package, which the root `pythonpath = ["."]` makes importable from every
member's tests.

- ``analyse_today(recording: Path) -> object``: today's path, ``build_document`` over one committed
  recording. A later task builds its own callable for "with the reconstruction" or "with the
  estimates" by wrapping the same call with its option switched on.
- ``compare_analysis_time(without, with_, recordings=RECORDINGS, *, repeats=REPEATS,
  clock=time.perf_counter) -> list[TimingComparison]``: for each recording, times ``without`` and
  ``with_`` alternately (so drift in machine load hits both), keeps each side's fastest repeat, and
  returns one ``TimingComparison`` per recording.
- ``TimingComparison``: ``recording``, ``without_seconds``, ``with_seconds``, ``ratio``, and
  ``within(bound)``. ``BOUND`` is SC-008's and SC-015's factor; ``assert_within_bound(results,
  bound=BOUND)`` fails naming every recording over it.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from aoe2stats_analyzer.extract import build_document
from aoe2stats_replay_engine.aoe2rec import Aoe2RecExtractor

_REPO_ROOT = Path(__file__).resolve().parents[1]
RECORDINGS: tuple[Path, ...] = tuple(
    sorted((_REPO_ROOT / "tests" / "fixtures" / "replays").glob("*.zip"))
)

#: SC-008 and SC-015: analysis may take at most this multiple of the same run's path without the
#: new code. A requirement, not a measurement.
BOUND = 2.0
#: Repeats per side; the fastest is kept, since noise only ever adds time.
REPEATS = 3


def _max_raw_bytes() -> int:
    """The analysis size bound as configured: the environment's `ANALYSIS_MAX_RAW_BYTES` when set,
    else the value `.env.example` declares for it, so a changed setting is followed."""
    configured = os.environ.get("ANALYSIS_MAX_RAW_BYTES")
    if configured:
        return int(configured)
    for line in (_REPO_ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == "ANALYSIS_MAX_RAW_BYTES":
            return int(value.strip())
    raise RuntimeError(
        "ANALYSIS_MAX_RAW_BYTES is declared neither in the environment nor in .env.example"
    )


_MAX_RAW_BYTES = _max_raw_bytes()
_GAME_ID = 1
_OBJECT_KEY = "retained-recordings/timing/harness.zip"
_SHA256 = "ab" * 32
_EXTRACTED_AT = datetime(2026, 1, 1, tzinfo=UTC)

Analyse = Callable[[Path], object]
Clock = Callable[[], float]


@dataclass(frozen=True)
class TimingComparison:
    """One recording timed with and without the new code in the same run."""

    recording: Path
    without_seconds: float
    with_seconds: float

    @property
    def ratio(self) -> float:
        return self.with_seconds / self.without_seconds

    def within(self, bound: float = BOUND) -> bool:
        return self.with_seconds <= bound * self.without_seconds


def analyse_today(recording: Path) -> object:
    """Today's path: parse one recording and build the published document."""
    return build_document(
        Aoe2RecExtractor(max_raw_bytes=_MAX_RAW_BYTES),
        recording.read_bytes(),
        game_id=_GAME_ID,
        object_key=_OBJECT_KEY,
        zip_sha256=_SHA256,
        extracted_at=_EXTRACTED_AT,
    )


def _elapsed(analyse: Analyse, recording: Path, clock: Clock) -> float:
    started = clock()
    analyse(recording)
    return clock() - started


def compare_analysis_time(
    without: Analyse,
    with_: Analyse,
    recordings: Sequence[Path] = RECORDINGS,
    *,
    repeats: int = REPEATS,
    clock: Clock = time.perf_counter,
) -> list[TimingComparison]:
    """Time both paths over each recording in this run, alternating them within a repeat."""
    if not recordings:
        raise ValueError("no recording to time: a comparison over nothing proves nothing")
    if repeats < 1:
        raise ValueError("repeats must be at least 1")
    results: list[TimingComparison] = []
    for recording in recordings:
        base: list[float] = []
        candidate: list[float] = []
        for _ in range(repeats):
            base.append(_elapsed(without, recording, clock))
            candidate.append(_elapsed(with_, recording, clock))
        results.append(TimingComparison(recording, min(base), min(candidate)))
    return results


def assert_within_bound(results: Sequence[TimingComparison], *, bound: float = BOUND) -> None:
    over = [r for r in results if not r.within(bound)]
    assert not over, "; ".join(
        f"{r.recording.name}: {r.ratio:.2f}x against a bound of {bound:.2f}x" for r in over
    )
