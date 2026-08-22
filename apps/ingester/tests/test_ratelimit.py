"""Tests for `aoe2stats_ingester.ratelimit` (T052): the token bucket and backoff policy configured
for the `aoe.ms` replay endpoint, and the rule that `ProviderRateLimited` stops the whole drain and
raises a severity-2 `rate_limited` alert rather than skipping the one item it fired on.

No database and no network: `TokenBucket`/`RetryPolicy` are plain in-process objects (`base.py`),
and `AlertSink` is satisfied structurally by an in-memory fake — the same `FakeAlertSink` shape
`packages/core/tests/test_alerting.py` already uses for `raise_alert` itself.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import pytest

from aoe2stats_core.alerting import AlertRecord
from aoe2stats_ingester.ratelimit import (
    RATE_LIMITED_ALERT_KIND,
    RATE_LIMITED_ALERT_SEVERITY,
    build_aoems_rate_limiter,
    build_aoems_retry_policy,
    drain_with_rate_limit_guard,
    raise_rate_limited_alert,
)
from aoe2stats_providers.base import ProviderRateLimited, RetryPolicy, TokenBucket


class FakeAlertSink:
    """An in-memory `AlertSink` — no session, no SQL (mirrors `packages/core/tests/
    test_alerting.py`'s `FakeAlertSink`)."""

    def __init__(self) -> None:
        self.rows: list[AlertRecord] = []

    async def write(
        self,
        *,
        kind: str,
        severity: int,
        detail: Mapping[str, Any] | None,
        ingest_run_id: uuid.UUID | None,
    ) -> AlertRecord:
        record = AlertRecord(
            id=uuid.uuid4(),
            kind=kind,
            severity=severity,
            detail=detail,
            raised_at=datetime.now(UTC),
            ingest_run_id=ingest_run_id,
            acknowledged_at=None,
        )
        self.rows.append(record)
        return record

    async def unacknowledged_severity_one(self) -> Sequence[AlertRecord]:
        return [row for row in self.rows if row.severity == 1 and row.acknowledged_at is None]


def _rate_limited(endpoint: str = "replay") -> ProviderRateLimited:
    return ProviderRateLimited(
        "throttled",
        provider="aoems",
        endpoint=endpoint,
        status_code=429,
        retry_after_seconds=30.0,
    )


# --- build_aoems_rate_limiter -----------------------------------------------------------------


def test_build_aoems_rate_limiter_returns_a_token_bucket() -> None:
    bucket = build_aoems_rate_limiter(1.0)
    assert isinstance(bucket, TokenBucket)


async def test_build_aoems_rate_limiter_caps_the_burst_to_one_outstanding_request_at_any_rate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even at a generous configured rate, two acquisitions back to back are serialised: the
    second must wait, because the burst allowance is fixed at exactly one request regardless of
    `requests_per_second` — see the module docstring's `_SERIAL_CAPACITY` rationale. Were the
    capacity instead derived from the rate (`TokenBucket`'s own default,
    `max(rate_per_second, 1.0)`), a bucket built at `requests_per_second=5.0` would have room for
    five outstanding requests and the second `acquire()` below would return with no wait at all.
    """
    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr("aoe2stats_providers.base.asyncio.sleep", fake_sleep)

    bucket = build_aoems_rate_limiter(5.0)  # real clock: two acquisitions in near-zero elapsed

    await bucket.acquire()  # the single token is spent immediately, no wait
    await bucket.acquire()  # the bucket is now empty and the clock has barely moved

    assert slept == [pytest.approx(1.0 / 5.0, abs=0.05)]


def test_build_aoems_rate_limiter_rejects_a_non_positive_rate() -> None:
    with pytest.raises(ValueError, match="positive"):
        build_aoems_rate_limiter(0)


# --- build_aoems_retry_policy ------------------------------------------------------------------


def test_build_aoems_retry_policy_returns_a_retry_policy_with_jitter() -> None:
    policy = build_aoems_retry_policy()
    assert isinstance(policy, RetryPolicy)
    assert policy.jitter_seconds > 0
    assert policy.max_attempts >= 1


def test_build_aoems_retry_policy_delay_grows_with_the_attempt_number() -> None:
    policy = build_aoems_retry_policy()
    # jitter makes any single pair of samples noisy; compare the deterministic floor instead.
    assert policy.delay_seconds(1) - policy.jitter_seconds >= policy.delay_seconds(0)


# --- raise_rate_limited_alert -------------------------------------------------------------------


async def test_raise_rate_limited_alert_writes_a_severity_two_rate_limited_row() -> None:
    sink = FakeAlertSink()
    run_id = uuid.uuid4()
    error = _rate_limited("replay")

    await raise_rate_limited_alert(sink, error, run_id=run_id)

    assert len(sink.rows) == 1
    record = sink.rows[0]
    assert record.kind == RATE_LIMITED_ALERT_KIND == "rate_limited"
    assert record.severity == RATE_LIMITED_ALERT_SEVERITY == 2
    assert record.ingest_run_id == run_id
    assert record.detail == {
        "provider": "aoems",
        "endpoint": "replay",
        "status_code": 429,
        "retry_after_seconds": 30.0,
    }


async def test_raise_rate_limited_alert_never_severity_one() -> None:
    """Regardless of the offending error's own fields, the alert this module raises is always
    severity 2 — being throttled is never the incident the nightly severity-1 audit (T061) is
    built to catch.
    """
    sink = FakeAlertSink()
    await raise_rate_limited_alert(sink, _rate_limited(), run_id=None)
    assert sink.rows[0].severity != 1


# --- drain_with_rate_limit_guard ------------------------------------------------------------------


async def test_drain_processes_every_item_when_none_rate_limit() -> None:
    sink = FakeAlertSink()
    handled: list[int] = []

    async def handle(item: int) -> None:
        handled.append(item)

    stopped = await drain_with_rate_limit_guard([1, 2, 3], handle, sink=sink, run_id=None)

    assert handled == [1, 2, 3]
    assert stopped is False
    assert sink.rows == []


async def test_drain_stops_immediately_on_the_first_rate_limit_and_never_touches_later_items() -> (
    None
):
    sink = FakeAlertSink()
    handled: list[int] = []

    async def handle(item: int) -> None:
        handled.append(item)
        if item == 2:
            raise _rate_limited(f"replay-{item}")

    stopped = await drain_with_rate_limit_guard([1, 2, 3, 4], handle, sink=sink, run_id=None)

    # Item 3 and 4 were never even attempted — the run stopped, it did not skip the offending item.
    assert handled == [1, 2]
    assert stopped is True
    assert len(sink.rows) == 1
    assert sink.rows[0].kind == "rate_limited"
    assert sink.rows[0].severity == 2


async def test_drain_raises_exactly_one_alert_even_though_only_one_item_ever_fails() -> None:
    """A single offending item produces a single alert row — nothing about the guard should
    double-count or retry the alert itself.
    """
    sink = FakeAlertSink()

    async def handle(item: int) -> None:
        raise _rate_limited()

    await drain_with_rate_limit_guard([1], handle, sink=sink, run_id=None)

    assert len(sink.rows) == 1


async def test_drain_of_an_empty_iterable_does_nothing_and_reports_not_stopped() -> None:
    sink = FakeAlertSink()

    async def handle(item: int) -> None:
        raise AssertionError("must never be called for an empty iterable")

    stopped = await drain_with_rate_limit_guard([], handle, sink=sink, run_id=None)

    assert stopped is False
    assert sink.rows == []


async def test_drain_does_not_swallow_a_non_rate_limit_error() -> None:
    """Only `ProviderRateLimited` is this module's concern; any other exception (a bug, an
    unrelated `ProviderUnavailable`) must propagate exactly as raised, uncaught here — this guard
    is not a general-purpose error barrier.
    """
    sink = FakeAlertSink()

    async def handle(item: int) -> None:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        await drain_with_rate_limit_guard([1], handle, sink=sink, run_id=None)

    assert sink.rows == []


async def test_drain_runs_items_serially_never_concurrently() -> None:
    """Proves the `for` loop awaits each `handle_item` to completion before starting the next,
    rather than e.g. scheduling them all and racing — the "serially" half of the skill's rule,
    independent of the token bucket's own burst-of-one guarantee.
    """
    sink = FakeAlertSink()
    order: list[str] = []

    async def handle(item: int) -> None:
        order.append(f"start-{item}")
        order.append(f"end-{item}")

    await drain_with_rate_limit_guard([1, 2, 3], handle, sink=sink, run_id=None)

    assert order == ["start-1", "end-1", "start-2", "end-2", "start-3", "end-3"]
