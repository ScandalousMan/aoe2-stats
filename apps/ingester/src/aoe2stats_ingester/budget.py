"""The *time* budget for one ingest cycle (plan.md: "the time budget, checked between items and
never mid-item").

`Budget` is the one clock every stage `run.py` orchestrates shares. It answers a single question —
is there room left to start one more unit of work? — and nothing else: it does not know what a
"unit of work" is, only how much wall-clock time remains. `discover.py` (T053), `reconcile.py`
(T054) and `capture.py` (T055/T059) each decide for themselves what their own items are (a profile
to poll, a match to enqueue, a capture to claim and download) and use `iter_within_budget` below to
walk their own queue against this same clock.

This is deliberately not the fairness quota (`quota.py`, T058): that one bounds *how much of one
user's* work a run does; this one bounds *how long the run itself* may keep working, whoever it is
working for. `plan.md` keeps them in separate modules for exactly that reason.

`time.monotonic()` and not `datetime.now()`: nothing here needs to know what time it is, only how
much of the allowance is left, and a monotonic clock cannot be pushed backwards or forwards by a
system clock adjustment mid-run (NTP, DST, a suspended VM). Module-level `monotonic` is imported by
name rather than as `time.monotonic` throughout, so a test can substitute a fake clock with
`monkeypatch.setattr(aoe2stats_ingester.budget, "monotonic", fake_clock)` without touching the real
one.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from time import monotonic


@dataclass(slots=True)
class Budget:
    """A wall-clock allowance, started the instant it is constructed.

    `seconds` is always `INGEST_RUN_BUDGET_SECONDS` in production, passed down from
    `run_once(budget_seconds)` — see that module's docstring for why that value, and not a second
    number invented here, is the one both entrypoints and every stage ultimately honour.
    """

    seconds: float
    _deadline: float = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._deadline = monotonic() + self.seconds

    @property
    def remaining_seconds(self) -> float:
        """Never negative: a caller comparing this to a per-item cost should not have to clamp."""
        return max(0.0, self._deadline - monotonic())

    @property
    def expired(self) -> bool:
        return monotonic() >= self._deadline


def iter_within_budget[T](items: Iterable[T], budget: Budget) -> Iterator[T]:
    """Yield items from `items` one at a time, stopping *before* handing over the first one the
    budget has no room left for.

    The check happens strictly between items, never mid-item: once an item has been handed to the
    caller, this generator makes no further judgement about it, so a claim, a download or an
    upload already in flight always runs to completion rather than being cut off partway through
    (constitution XII; T044's interruption scenario is what a mid-item cut would break). This is
    the shape the discovery loop, the reconciliation sweep and the capture drain each plug into for
    their own queue — `run.py`'s stage loop applies the identical rule one level up, between
    stages rather than between items within one.
    """
    for item in items:
        if budget.expired:
            return
        yield item
