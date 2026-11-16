"""Tests of the timing harness `tests/analysis_time.py` (T909); see its docstring for the API."""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.analysis_time import (
    BOUND,
    RECORDINGS,
    Analyse,
    analyse_today,
    assert_within_bound,
    compare_analysis_time,
)


def test_the_harness_imports_the_way_t950_and_t975_import_it() -> None:
    """`tests` is the repository-root namespace package; the harness must resolve through it."""
    import importlib

    module = importlib.import_module("tests.analysis_time")
    assert module.compare_analysis_time is compare_analysis_time


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
