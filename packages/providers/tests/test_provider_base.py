"""Tests for the shared provider machinery (`base.py`).

Every request goes through `httpx.MockTransport`: constitution III forbids the network in unit
tests, and `tests/conftest.py` blocks any real socket connection under `PYTEST_DISABLE_NETWORK=1`
regardless — `MockTransport` never opens one in the first place.

Retry delays use a tiny `RetryPolicy` (fractions of a millisecond) rather than mocking `time.sleep`
/ `asyncio.sleep`: it keeps the suite fast without patching stdlib functions that other code (and
pytest-asyncio itself) may also rely on. The token bucket tests are the one place a fake clock is
worth it, because they assert the *wait duration* the bucket computes.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from datetime import UTC, datetime

import httpx
import pytest
from pydantic import ValidationError

from aoe2stats_providers.base import (
    PROVIDER_USER_AGENT,
    AsyncBaseProvider,
    NotFound,
    ProviderCallRecord,
    ProviderContractViolation,
    ProviderError,
    ProviderRateLimited,
    ProviderUnavailable,
    ReplayBlob,
    RetryPolicy,
    SyncBaseProvider,
    SyncTokenBucket,
    TokenBucket,
    parse_strict,
)

FAST_RETRY = RetryPolicy(
    max_attempts=3, base_delay_seconds=0.001, max_delay_seconds=0.002, jitter_seconds=0.0
)


class _FakeClock:
    """A controllable clock for the token bucket tests: advances only when told to."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class _Recorder:
    """An `AsyncProviderCallSink` / `SyncProviderCallSink` double that just remembers calls."""

    def __init__(self) -> None:
        self.calls: list[ProviderCallRecord] = []

    async def async_sink(self, record: ProviderCallRecord) -> None:
        self.calls.append(record)

    def sync_sink(self, record: ProviderCallRecord) -> None:
        self.calls.append(record)


class _FakeAsyncProvider(AsyncBaseProvider):
    """The smallest possible concrete provider, so `_request` can be exercised directly."""

    async def call(self, url: str = "https://example.test/thing") -> httpx.Response:
        return await self._request("GET", url, endpoint="thing")


class _FakeSyncProvider(SyncBaseProvider):
    def call(self, url: str = "https://example.test/thing") -> httpx.Response:
        return self._request("GET", url, endpoint="thing")


def _async_provider(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    recorder: _Recorder | None = None,
    rate_per_second: float = 1000.0,
    retry_policy: RetryPolicy = FAST_RETRY,
) -> tuple[_FakeAsyncProvider, _Recorder]:
    recorder = recorder or _Recorder()
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = _FakeAsyncProvider(
        provider="fake",
        client=client,
        timeout_seconds=5.0,
        rate_limiter=TokenBucket(rate_per_second),
        call_sink=recorder.async_sink,
        retry_policy=retry_policy,
    )
    return provider, recorder


def _sync_provider(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    recorder: _Recorder | None = None,
    rate_per_second: float = 1000.0,
    retry_policy: RetryPolicy = FAST_RETRY,
) -> tuple[_FakeSyncProvider, _Recorder]:
    recorder = recorder or _Recorder()
    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = _FakeSyncProvider(
        provider="fake",
        client=client,
        timeout_seconds=5.0,
        rate_limiter=SyncTokenBucket(rate_per_second),
        call_sink=recorder.sync_sink,
        retry_policy=retry_policy,
    )
    return provider, recorder


# --- The honest User-Agent ------------------------------------------------------------------------


async def test_async_provider_sends_the_honest_user_agent() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["user_agent"] = request.headers["user-agent"]
        return httpx.Response(200, json={"ok": True})

    provider, _ = _async_provider(handler)
    await provider.call()

    assert seen["user_agent"] == PROVIDER_USER_AGENT


def test_sync_provider_sends_the_honest_user_agent() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["user_agent"] = request.headers["user-agent"]
        return httpx.Response(200, json={"ok": True})

    provider, _ = _sync_provider(handler)
    provider.call()

    assert seen["user_agent"] == PROVIDER_USER_AGENT


# --- Explicit timeout -------------------------------------------------------------------------


def test_timeout_is_explicit_never_a_silent_forever() -> None:
    provider, _ = _async_provider(lambda request: httpx.Response(200))
    assert provider._timeout == httpx.Timeout(5.0)


async def test_a_timeout_exhausting_retries_raises_provider_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("no reply", request=request)

    recorder = _Recorder()
    provider, _ = _async_provider(handler, recorder=recorder)

    with pytest.raises(ProviderUnavailable) as excinfo:
        await provider.call()

    assert excinfo.value.provider == "fake"
    assert excinfo.value.endpoint == "thing"
    # One `provider_calls` row per attempt, all with no status code — the wire never answered.
    assert len(recorder.calls) == FAST_RETRY.max_attempts
    assert all(call.status_code is None and not call.rate_limited for call in recorder.calls)


# --- Retry with backoff, transient failures only -----------------------------------------------


async def test_a_5xx_is_retried_and_a_later_success_is_returned() -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"ok": True})

    recorder = _Recorder()
    provider, _ = _async_provider(handler, recorder=recorder)

    response = await provider.call()

    assert response.status_code == 200
    assert len(attempts) == 2
    assert [call.status_code for call in recorder.calls] == [503, 200]
    assert not any(call.rate_limited for call in recorder.calls)


async def test_persistent_5xx_exhausts_retries_and_raises_provider_unavailable() -> None:
    recorder = _Recorder()
    provider, _ = _async_provider(lambda request: httpx.Response(502), recorder=recorder)

    with pytest.raises(ProviderUnavailable) as excinfo:
        await provider.call()

    assert excinfo.value.status_code == 502
    assert len(recorder.calls) == FAST_RETRY.max_attempts


async def test_a_connection_error_is_retried_like_a_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    recorder = _Recorder()
    provider, _ = _async_provider(handler, recorder=recorder)

    with pytest.raises(ProviderUnavailable):
        await provider.call()

    assert len(recorder.calls) == FAST_RETRY.max_attempts


# --- 429 / unexpected 403: never retried, stops the run immediately -----------------------------


async def test_429_raises_provider_rate_limited_without_retrying() -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(429, headers={"Retry-After": "30"})

    recorder = _Recorder()
    provider, _ = _async_provider(handler, recorder=recorder)

    with pytest.raises(ProviderRateLimited) as excinfo:
        await provider.call()

    assert len(attempts) == 1, "a 429 must never be retried within the call"
    assert len(recorder.calls) == 1
    assert recorder.calls[0].rate_limited is True
    assert excinfo.value.retry_after_seconds == 30.0


async def test_unexpected_403_is_treated_as_rate_limited_by_default() -> None:
    recorder = _Recorder()
    provider, _ = _async_provider(lambda request: httpx.Response(403), recorder=recorder)

    with pytest.raises(ProviderRateLimited):
        await provider.call()

    assert len(recorder.calls) == 1


async def test_403_can_be_opted_out_of_rate_limit_classification() -> None:
    """`EnrichmentProvider`'s 403 is normal operating noise (skill `aoe2-data-sources`), not a
    signal to stop the run — a concrete provider must be able to say so per request.
    """

    async def call_without_403_classification(
        provider: _FakeAsyncProvider,
    ) -> httpx.Response:
        return await provider._request(
            "GET",
            "https://example.test/thing",
            endpoint="thing",
            treat_403_as_rate_limited=False,
        )

    provider, recorder = _async_provider(lambda request: httpx.Response(403))

    response = await call_without_403_classification(provider)

    assert response.status_code == 403
    assert recorder.calls[0].rate_limited is False


# --- provider_calls: recorded, no body -----------------------------------------------------------


async def test_provider_call_record_carries_no_response_body() -> None:
    recorder = _Recorder()
    provider, _ = _async_provider(
        lambda request: httpx.Response(200, json={"secret": "not for provider_calls"}),
        recorder=recorder,
    )

    await provider.call()

    record = recorder.calls[0]
    assert record.provider == "fake"
    assert record.endpoint == "thing"
    assert record.status_code == 200
    assert record.duration_ms >= 0
    assert isinstance(record.called_at, datetime)
    assert record.called_at.tzinfo is UTC
    # `ProviderCallRecord` is a frozen dataclass with exactly these fields — nowhere to put a body.
    assert set(record.__dataclass_fields__) == {
        "provider",
        "endpoint",
        "status_code",
        "duration_ms",
        "rate_limited",
        "called_at",
    }


async def test_no_call_sink_means_no_recording_but_no_crash_either() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    provider = _FakeAsyncProvider(
        provider="fake",
        client=client,
        timeout_seconds=5.0,
        rate_limiter=TokenBucket(1000.0),
        call_sink=None,
    )
    response = await provider.call()
    assert response.status_code == 200


# --- The synchronous twin (SteamAuthProvider's machinery) --------------------------------------


def test_sync_provider_retries_and_records_like_the_async_one() -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) == 1:
            return httpx.Response(503)
        return httpx.Response(200)

    recorder = _Recorder()
    provider, _ = _sync_provider(handler, recorder=recorder)

    response = provider.call()

    assert response.status_code == 200
    assert [call.status_code for call in recorder.calls] == [503, 200]


def test_sync_provider_429_raises_immediately() -> None:
    recorder = _Recorder()
    provider, _ = _sync_provider(lambda request: httpx.Response(429), recorder=recorder)

    with pytest.raises(ProviderRateLimited):
        provider.call()

    assert len(recorder.calls) == 1


# --- Token bucket ------------------------------------------------------------------------------


async def test_token_bucket_lets_the_first_call_through_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr("aoe2stats_providers.base.asyncio.sleep", fake_sleep)

    clock = _FakeClock()
    bucket = TokenBucket(1.0, capacity=1.0, clock=clock)

    await bucket.acquire()

    assert slept == []


async def test_token_bucket_makes_a_second_immediate_call_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr("aoe2stats_providers.base.asyncio.sleep", fake_sleep)

    clock = _FakeClock()
    bucket = TokenBucket(1.0, capacity=1.0, clock=clock)

    await bucket.acquire()  # consumes the only token, no wait
    await bucket.acquire()  # the bucket is empty and the clock has not moved

    assert slept == [pytest.approx(1.0)]


async def test_token_bucket_refills_over_time(monkeypatch: pytest.MonkeyPatch) -> None:
    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr("aoe2stats_providers.base.asyncio.sleep", fake_sleep)

    clock = _FakeClock()
    bucket = TokenBucket(1.0, capacity=1.0, clock=clock)

    await bucket.acquire()
    clock.advance(1.0)  # a full second passes — one token is back
    await bucket.acquire()

    assert slept == []


def test_token_bucket_rejects_a_non_positive_rate() -> None:
    with pytest.raises(ValueError, match="positive"):
        TokenBucket(0)
    with pytest.raises(ValueError, match="positive"):
        SyncTokenBucket(-1)


def test_sync_token_bucket_makes_a_second_immediate_call_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slept: list[float] = []
    monkeypatch.setattr(
        "aoe2stats_providers.base.time.sleep", lambda seconds: slept.append(seconds)
    )

    clock = _FakeClock()
    bucket = SyncTokenBucket(1.0, capacity=1.0, clock=clock)

    bucket.acquire()
    bucket.acquire()

    assert slept == [pytest.approx(1.0)]


async def test_token_bucket_spaces_genuinely_concurrent_acquirers_by_the_rate_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The bug this guards against: `_reserve` used to clamp a shortfall to zero, so N concurrent
    `acquire()` calls — as `AsyncBaseProvider._request` issues, one per in-flight provider call —
    all computed the same wait from the same zeroed balance and fired together (measured: one
    request at t=0 and four simultaneously at t=1.0 s). Every other token-bucket test above calls
    `acquire()` sequentially, checking only the *second* call's wait, which is exactly why they
    passed against that broken implementation — a *third* sequential call already exposes it, but
    the review found this as a concurrency defect, so this test reproduces it that way:
    `asyncio.gather` launches five acquirers that all race for the lock at (real-clock) t≈0, the
    same shape as several ingest tasks calling `_request` around the same instant.

    `asyncio.sleep` is mocked to record without blocking, so the test stays fast; the concurrency
    under test is the five tasks' interleaved entry into `TokenBucket`'s critical section, not the
    real wall-clock wait afterward.
    """
    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr("aoe2stats_providers.base.asyncio.sleep", fake_sleep)

    bucket = TokenBucket(1.0, capacity=1.0)  # real clock: five acquisitions in near-zero elapsed

    await asyncio.gather(*(bucket.acquire() for _ in range(5)))

    # One caller proceeds immediately (no `sleep` call at all); the other four must be spaced
    # 1/rate apart against the advancing cursor, not all told to wait the same ~1 s.
    assert sorted(slept) == pytest.approx([1.0, 2.0, 3.0, 4.0], abs=0.05)


def test_sync_token_bucket_spaces_genuinely_concurrent_acquirers_by_the_rate_interval() -> None:
    """The threaded twin of the async proof above: real OS threads racing `SyncTokenBucket.acquire`
    under `SteamAuthProvider`'s synchronous path.
    """
    bucket = SyncTokenBucket(1.0, capacity=1.0)
    slept: list[float] = []
    slept_lock = threading.Lock()

    real_sleep = threading.Event().wait  # a real, interruptible wait — not `time.sleep(0)`

    def fake_sleep(seconds: float) -> None:
        with slept_lock:
            slept.append(seconds)
        real_sleep(min(seconds, 0.01))  # let other threads actually contend, without the real cost

    threads = [threading.Thread(target=bucket.acquire) for _ in range(5)]
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("aoe2stats_providers.base.time.sleep", fake_sleep)
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5.0)

    assert not any(thread.is_alive() for thread in threads)
    # One caller proceeds immediately (no `sleep` call at all); the other four must be spaced
    # 1/rate apart, not all told to wait the same ~1 s.
    assert sorted(slept) == pytest.approx([1.0, 2.0, 3.0, 4.0], abs=0.1)


# --- Typed errors --------------------------------------------------------------------------------


def test_typed_errors_carry_provider_endpoint_and_status_code() -> None:
    error = ProviderUnavailable("boom", provider="aoems", endpoint="fetch_replay", status_code=503)
    assert isinstance(error, ProviderError)
    assert error.provider == "aoems"
    assert error.endpoint == "fetch_replay"
    assert error.status_code == 503


def test_rate_limited_carries_retry_after() -> None:
    error = ProviderRateLimited(
        "slow down", provider="aoems", endpoint="fetch_replay", retry_after_seconds=12.0
    )
    assert error.retry_after_seconds == 12.0


# --- Strict validation: never a coerced value ----------------------------------------------------


def test_parse_strict_returns_a_validated_model_on_a_well_formed_response() -> None:
    blob = parse_strict(
        ReplayBlob,
        {
            "content": b"PK\x03\x04...",
            "filename": "AgeIIDE_Replay_1.zip",
            "content_type": "application/zip",
        },
        provider="aoems",
        endpoint="fetch_replay",
    )
    assert blob.filename == "AgeIIDE_Replay_1.zip"


def test_parse_strict_raises_contract_violation_never_a_coerced_value() -> None:
    with pytest.raises(ProviderContractViolation) as excinfo:
        parse_strict(
            ReplayBlob,
            # `content_type` as an int: strict mode must refuse to coerce it to a string.
            {"content": b"x", "filename": "a.zip", "content_type": 12345},
            provider="aoems",
            endpoint="fetch_replay",
        )
    assert excinfo.value.provider == "aoems"
    assert excinfo.value.endpoint == "fetch_replay"


def test_strict_dto_rejects_an_unexpected_extra_field() -> None:
    with pytest.raises(ValidationError):
        NotFound.model_validate({"http_status": 404, "reason": "invented by the caller"})
