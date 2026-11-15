"""The timing harness SC-008 and SC-015 are measured with (T909), built before any reconstruction
code exists.

No timing is committed and no figure appears here: a duration taken on one machine cannot be
compared on another (research R14). The baseline of a comparison is therefore the **same run's own
path without the new code**, timed beside the path with it, over the same recordings.

**API for T950 and T975** (import as ``from tests.test_analysis_time import ...``):

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

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aoe2stats_analyzer.extract import build_document
from aoe2stats_replay_engine.aoe2rec import Aoe2RecExtractor

_REPO_ROOT = Path(__file__).resolve().parents[3]
RECORDINGS: tuple[Path, ...] = tuple(
    sorted((_REPO_ROOT / "tests" / "fixtures" / "replays").glob("*.zip"))
)

#: SC-008 and SC-015: analysis may take at most this multiple of the same run's path without the
#: new code. A requirement, not a measurement.
BOUND = 2.0
#: Repeats per side; the fastest is kept, since noise only ever adds time.
REPEATS = 3

_MAX_RAW_BYTES = 25_165_824  # `.env.example`'s ANALYSIS_MAX_RAW_BYTES
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


class _FakeClock:
    """A clock that advances only when an analysis says how long it took."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def path(self, cost: float) -> Analyse:
        def analyse(_recording: Path) -> None:
            self.now += cost

        return analyse


def test_the_recordings_are_found() -> None:
    """A glob over a moved directory times nothing and passes; refuse that."""
    assert len(RECORDINGS) >= 2, RECORDINGS


def test_a_path_over_the_bound_is_reported_by_recording() -> None:
    clock = _FakeClock()
    results = compare_analysis_time(
        clock.path(1.0), clock.path(BOUND * 1.5), [Path("a.zip")], clock=clock
    )
    assert results[0].ratio == pytest.approx(BOUND * 1.5)
    assert not results[0].within()
    with pytest.raises(AssertionError, match=r"a\.zip"):
        assert_within_bound(results)


def test_a_path_at_the_bound_passes() -> None:
    clock = _FakeClock()
    results = compare_analysis_time(
        clock.path(1.0), clock.path(BOUND), [Path("a.zip")], clock=clock
    )
    assert_within_bound(results)


def test_both_paths_run_on_every_recording_every_repeat_alternating() -> None:
    calls: list[tuple[str, str]] = []

    def tag(name: str) -> Analyse:
        return lambda recording: calls.append((name, recording.name))

    compare_analysis_time(tag("without"), tag("with"), [Path("a.zip"), Path("b.zip")], repeats=2)
    assert calls == [
        ("without", "a.zip"),
        ("with", "a.zip"),
        ("without", "a.zip"),
        ("with", "a.zip"),
        ("without", "b.zip"),
        ("with", "b.zip"),
        ("without", "b.zip"),
        ("with", "b.zip"),
    ]


def test_the_fastest_repeat_is_kept() -> None:
    clock = _FakeClock()
    costs = iter([5.0, 2.0, 9.0])

    def varying(_recording: Path) -> None:
        clock.now += next(costs)

    results = compare_analysis_time(
        varying, clock.path(1.0), [Path("a.zip")], repeats=3, clock=clock
    )
    assert results[0].without_seconds == 2.0


def test_a_comparison_over_nothing_is_refused() -> None:
    with pytest.raises(ValueError, match="no recording"):
        compare_analysis_time(analyse_today, analyse_today, [])


def test_today_s_path_is_timed_on_every_committed_recording() -> None:
    """Today's path against itself in one run: proves the harness drives the real analysis over
    every committed recording. The ratio is not asserted; two identical paths differ only by
    noise, and that is not a property worth a flaky gate."""
    results = compare_analysis_time(analyse_today, analyse_today, repeats=1)
    assert [r.recording for r in results] == list(RECORDINGS)
    assert all(r.without_seconds > 0 and r.with_seconds > 0 for r in results)
