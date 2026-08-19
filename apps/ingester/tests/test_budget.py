"""Unit tests for `aoe2stats_ingester.budget`.

`Budget.__post_init__` and `.expired`/`.remaining_seconds` both call `monotonic()` at the module
level, so a fake clock is substituted with `monkeypatch.setattr(budget_module, "monotonic", ...)`
rather than sleeping in real time — these tests must stay deterministic and fast, and must run
with no network at all (constitution III; there is none to block here regardless).
"""

from __future__ import annotations

import aoe2stats_ingester.budget as budget_module
from aoe2stats_ingester.budget import Budget, iter_within_budget


class FakeClock:
    """A settable stand-in for `time.monotonic`."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_budget_is_not_expired_the_moment_it_is_created(monkeypatch) -> None:
    monkeypatch.setattr(budget_module, "monotonic", FakeClock())

    budget = Budget(seconds=10)

    assert not budget.expired
    assert budget.remaining_seconds == 10


def test_budget_expires_exactly_at_its_allowance(monkeypatch) -> None:
    clock = FakeClock()
    monkeypatch.setattr(budget_module, "monotonic", clock)
    budget = Budget(seconds=5)

    clock.advance(5)

    assert budget.expired
    assert budget.remaining_seconds == 0


def test_budget_remaining_seconds_never_goes_negative(monkeypatch) -> None:
    clock = FakeClock()
    monkeypatch.setattr(budget_module, "monotonic", clock)
    budget = Budget(seconds=1)

    clock.advance(100)

    assert budget.remaining_seconds == 0


def test_iter_within_budget_stops_between_items_not_mid_item(monkeypatch) -> None:
    """The rule plan.md states: checked between items, never mid-item.

    The whole allowance is consumed while the first item is "in flight" (simulated by advancing
    the clock only once the underlying generator resumes after its `yield`). The second item must
    never be produced: the check happens before it is requested, not partway through handling the
    first one.
    """
    clock = FakeClock()
    monkeypatch.setattr(budget_module, "monotonic", clock)
    budget = Budget(seconds=1)

    def items() -> object:
        yield "a"
        clock.advance(1)  # work done on "a" spends the whole budget
        yield "b"
        yield "c"

    seen = list(iter_within_budget(items(), budget))

    assert seen == ["a"]


def test_iter_within_budget_yields_nothing_from_an_already_expired_budget(monkeypatch) -> None:
    clock = FakeClock()
    monkeypatch.setattr(budget_module, "monotonic", clock)
    budget = Budget(seconds=1)
    clock.advance(1)

    seen = list(iter_within_budget(["a", "b"], budget))

    assert seen == []


def test_iter_within_budget_yields_everything_when_budget_is_ample(monkeypatch) -> None:
    monkeypatch.setattr(budget_module, "monotonic", FakeClock())
    budget = Budget(seconds=1000)

    seen = list(iter_within_budget(["a", "b", "c"], budget))

    assert seen == ["a", "b", "c"]
