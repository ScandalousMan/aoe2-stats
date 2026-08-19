"""The `DataProvider` boundary: constitution III in code.

Everything a concrete provider (`steam/`, `relic/`, `aoems/`, `companion/`) needs and nothing a
concrete provider is allowed to skip:

- an explicit timeout, never a default that means "forever";
- retry with backoff on the transient failures (timeout, connection error, 5xx) — never on a 429
  or an unexpected 403, which are not transient and are raised immediately (skill
  `aoe2-data-sources`: "It does not skip one item and continue.");
- a token bucket every request passes through before it is sent;
- the honest, identifying `User-Agent`;
- a `provider_calls` row for every attempt, success or failure;
- the typed errors `ProviderUnavailable`, `ProviderRateLimited`, `ProviderContractViolation`, and
  strict Pydantic validation so a field of an unexpected type never becomes a coerced value.

What this module deliberately does **not** do: persist a raw response anywhere. `provider_calls`
(see `packages/storage/src/aoe2stats_storage/models.py::ProviderCall`) holds no body — a generic
raw-response store would be a third copy of data that already has a home, with no reader and a
GDPR surface nobody asked for (FR-012). Instead, the DTOs below carry the untransformed payload
all the way to the caller unmodified: `RawMatch.raw_payload` is the exact `matches.raw_payload`
column value, `ReplayBlob.content` is the exact bytes the object store keys. Each *calling*
provider names its own column or object key; this module only promises never to lose or coerce a
byte before that hand-off happens.

`SteamAuthProvider` is the one synchronous contract (`contracts/providers.md`): the OpenID 2.0
round trip runs inline in the callback route rather than through the async ingest path, so it gets
its own synchronous request helper (`SyncBaseProvider`) built from the same primitives —
`RetryPolicy`, `SyncTokenBucket`, the same error classification — as the async one
(`AsyncBaseProvider`) that every other provider uses.
"""

from __future__ import annotations

import asyncio
import random
import threading
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

# --- The one honest identity every outbound request carries -------------------------------------

PROVIDER_USER_AGENT = "aoe2-stats/0.1 (+https://github.com/ScandalousMan/aoe2-stats)"

# The Steam-verified 64-bit identifier. A type alias, not a `NewType`: providers.md's signatures
# read `SteamId64 | None`, and every caller already holds a plain `str` from an HTTP response —
# wrapping it would only add friction with nothing else keyed on the difference.
type SteamId64 = str


# --- Typed errors — providers.md: "never returns a partially-parsed object" ---------------------


class ProviderError(Exception):
    """Base for every error a provider raises. Never returned — a `DataProvider` either returns a
    complete, validated value or raises one of these three.
    """

    def __init__(
        self, message: str, *, provider: str, endpoint: str, status_code: int | None = None
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.endpoint = endpoint
        self.status_code = status_code


class ProviderUnavailable(ProviderError):
    """The source itself is unhealthy: a 5xx, or a timeout/connection failure that outlived the
    retry budget. Recoverable on a later run; the caller should not treat this as a permanent
    outcome for the item being fetched.
    """


class ProviderRateLimited(ProviderError):
    """A 429, or an unexpected 403. Raised on the first occurrence, never retried within the call:
    skill `aoe2-data-sources` — this stops the whole ingest run, not just the one item, because
    the capture budget is 21 days and there is always tomorrow.
    """

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        endpoint: str,
        status_code: int | None = None,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(message, provider=provider, endpoint=endpoint, status_code=status_code)
        self.retry_after_seconds = retry_after_seconds


class ProviderContractViolation(ProviderError):
    """The response parsed, but not into the shape the contract promises. Strict Pydantic
    validation raises this instead of silently coercing a field — "silent coercion is how wrong
    data becomes permanent" (skill `aoe2-data-sources`).
    """


# --- Strict DTOs — the vocabulary the Protocols below share -------------------------------------
# `strict=True` + `extra="forbid"` is what turns an unexpected type or an unexpected field into a
# `ValidationError` a caller turns into `ProviderContractViolation` (see `parse_strict` below)
# rather than a silently coerced value.


class StrictProviderModel(BaseModel):
    """Shared Pydantic config for every provider DTO. Frozen: a validated response is a fact about
    a moment in time, not something later code should mutate in place.
    """

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class ProfileRef(StrictProviderModel):
    """`ProfileProvider.resolve_profile` — the AoE2 profile a Steam account resolves to.

    Enough to upsert `aoe_profiles`: `alias` is required there (never null), so it is required
    here too rather than deferred to a caller that has nowhere else to get it.
    """

    profile_id: int
    alias: str
    country: str | None = None


class LeaderboardSnapshot(StrictProviderModel):
    """One leaderboard's standing from `ProfileProvider.personal_stats`, feeding a
    `rating_snapshots` row.
    """

    profile_id: int
    leaderboard_id: int
    rating: int
    rank: int | None = None
    wins: int | None = None
    losses: int | None = None
    streak: int | None = None
    highest_rating: int | None = None
    last_match_at: datetime | None = None


class RawMatch(StrictProviderModel):
    """`MatchHistoryProvider.recent_matches` — the parsed fields a `matches` row needs, *and* the
    untouched payload (`raw_payload`) constitution IV and FR-012 require verbatim, because a
    match leaves the "recent" window and can never be fetched back (`docs/data-sources.md`).
    """

    game_id: int
    leaderboard_id: int
    map_name: str | None = None
    patch: str | None = None
    started_at: datetime | None = None
    completed_at: datetime
    duration_seconds: int | None = None
    player_profile_ids: tuple[int, ...]
    raw_payload: dict[str, Any]


class ReplayBlob(StrictProviderModel):
    """`ReplayProvider.fetch_replay` on 200 — bytes, filename and content type, and nothing
    interpreted. `content` is stored and checksummed by the caller before validation ever runs
    (FR-026): a validation failure must never discard it.
    """

    content: bytes
    filename: str
    content_type: str


class NotFound(StrictProviderModel):
    """`ReplayProvider.fetch_replay` on 404 — the observed wire condition and nothing more. This
    provider holds no `completed_at` and cannot know whether the match is too young, expired, or
    genuinely never recorded; that three-way read belongs to the caller (`contracts/providers.md`).
    """

    http_status: int = 404


class MatchEnrichment(StrictProviderModel):
    """`EnrichmentProvider.enrich_matches` — normalized display data only. Every field is
    optional: aoe2companion is the one provider whose failure is not an error, and a missing key
    here is normal, not a contract violation.
    """

    game_id: int
    map_display_name: str | None = None
    game_mode: str | None = None
    game_speed: str | None = None
    civilizations: dict[int, str] | None = None


def parse_strict[ModelT: BaseModel](
    model: type[ModelT], data: Any, *, provider: str, endpoint: str
) -> ModelT:
    """Validate `data` against `model`, turning a `ValidationError` into `ProviderContractViolation`
    instead of letting Pydantic's coercion (outside `strict` mode) or a raw exception leak through.
    """
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise ProviderContractViolation(
            f"unexpected shape from {provider} at {endpoint}: {exc}",
            provider=provider,
            endpoint=endpoint,
        ) from exc


# --- The five `DataProvider` contracts (`contracts/providers.md`) -------------------------------


@runtime_checkable
class SteamAuthProvider(Protocol):
    """OpenID 2.0 against Steam. `verify` never raises for an invalid assertion — it returns
    `None` — so a caller cannot mistake an exception path for success (research.md §2).
    """

    def begin(self, return_to: str, state: str) -> str: ...
    def verify(self, callback_params: Mapping[str, str]) -> SteamId64 | None: ...


@runtime_checkable
class ProfileProvider(Protocol):
    """Relic profile resolution and current standing. `resolve_profile` returning `None` is an
    ordinary outcome (FR-003, no AoE2 profile), never an error.
    """

    async def resolve_profile(self, steam_id64: str) -> ProfileRef | None: ...
    async def personal_stats(self, profile_ids: Sequence[int]) -> list[LeaderboardSnapshot]: ...


@runtime_checkable
class MatchHistoryProvider(Protocol):
    """Relic match discovery, batched up to 10 profiles per call."""

    async def recent_matches(self, profile_ids: Sequence[int]) -> list[RawMatch]: ...


@runtime_checkable
class ReplayProvider(Protocol):
    """`aoe.ms` replay download. Reports the wire condition, never an interpretation of it — see
    the three-way 404 reading owned by the caller in `contracts/providers.md`.
    """

    async def fetch_replay(self, game_id: int, profile_id: int) -> ReplayBlob | NotFound: ...


@runtime_checkable
class EnrichmentProvider(Protocol):
    """aoe2companion, behind a circuit breaker. The only provider whose failure is not an error;
    `linkedProfiles` is not to be consumed at all (FR-045) and does not appear on `MatchEnrichment`.
    """

    async def enrich_matches(self, game_ids: Sequence[int]) -> dict[int, MatchEnrichment]: ...


# --- Retry with backoff ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Exponential backoff with jitter, for the transient failures only (timeout, connection
    error, 5xx). A 429 or an unexpected 403 never reaches this — see `AsyncBaseProvider._request`.
    """

    max_attempts: int = 3
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 8.0
    jitter_seconds: float = 0.25

    def delay_seconds(self, attempt: int) -> float:
        """`attempt` is 0-indexed: the wait *before* the (attempt + 2)th try.

        `float(2**attempt)` rather than a bare `2**attempt`: `int.__pow__` types as `Any` in
        typeshed (the exponent's sign is not known statically), which would otherwise make this
        whole expression — and the function's declared `float` return — silently `Any` too.
        """
        exponential = min(self.base_delay_seconds * float(2**attempt), self.max_delay_seconds)
        return exponential + random.uniform(0, self.jitter_seconds)


# --- Token bucket ---------------------------------------------------------------------------------
# Shared refill algorithm, two front ends: `TokenBucket` (async, `asyncio.sleep`) for every
# provider except Steam, and `SyncTokenBucket` (`threading.Lock`, `time.sleep`) for the
# synchronous `SteamAuthProvider`. "Passes through a token bucket before every request" admits no
# exception.


def _reserve(
    *, tokens: float, capacity: float, rate_per_second: float, elapsed: float
) -> tuple[float, float]:
    """Refill `tokens` by `elapsed` seconds at `rate_per_second`, then reserve one.

    Returns `(tokens_after, wait_seconds)`: the new token count, and how long the caller must wait
    (0 when a token was immediately available) before it may proceed.
    """
    tokens = min(capacity, tokens + elapsed * rate_per_second)
    if tokens >= 1:
        return tokens - 1, 0.0
    wait = (1 - tokens) / rate_per_second
    return 0.0, wait


class TokenBucket:
    """Async token bucket limiting a provider to `rate_per_second` requests, on average, with
    bursts up to `capacity`.
    """

    def __init__(
        self,
        rate_per_second: float,
        *,
        capacity: float | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if rate_per_second <= 0:
            raise ValueError("rate_per_second must be positive")
        self._rate = rate_per_second
        self._capacity = capacity if capacity is not None else max(rate_per_second, 1.0)
        self._tokens = self._capacity
        self._clock = clock
        self._updated_at = clock()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = self._clock()
            elapsed = now - self._updated_at
            self._updated_at = now
            self._tokens, wait = _reserve(
                tokens=self._tokens,
                capacity=self._capacity,
                rate_per_second=self._rate,
                elapsed=elapsed,
            )
        if wait > 0:
            await asyncio.sleep(wait)


class SyncTokenBucket:
    """The synchronous twin of `TokenBucket`, for `SteamAuthProvider`."""

    def __init__(
        self,
        rate_per_second: float,
        *,
        capacity: float | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if rate_per_second <= 0:
            raise ValueError("rate_per_second must be positive")
        self._rate = rate_per_second
        self._capacity = capacity if capacity is not None else max(rate_per_second, 1.0)
        self._tokens = self._capacity
        self._clock = clock
        self._updated_at = clock()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            now = self._clock()
            elapsed = now - self._updated_at
            self._updated_at = now
            self._tokens, wait = _reserve(
                tokens=self._tokens,
                capacity=self._capacity,
                rate_per_second=self._rate,
                elapsed=elapsed,
            )
        if wait > 0:
            time.sleep(wait)


# --- `provider_calls` — recorded, never bodied (FR-012) ------------------------------------------


@dataclass(frozen=True, slots=True)
class ProviderCallRecord:
    """Everything a `provider_calls` row holds. No response body: see the module docstring."""

    provider: str
    endpoint: str
    status_code: int | None
    duration_ms: int
    rate_limited: bool
    called_at: datetime


# The actual write lands wherever the caller wires persistence (a storage repository, most likely,
# once T009 exists) — this module only guarantees the record is assembled and handed over for
# every attempt. Injected rather than imported so `packages/providers` never depends on
# `packages/storage`; the DataProvider boundary is about outbound calls, not the schema behind it.
AsyncProviderCallSink = Callable[[ProviderCallRecord], Awaitable[None]]
SyncProviderCallSink = Callable[[ProviderCallRecord], None]


def _is_rate_limited(status_code: int, *, treat_403_as_rate_limited: bool) -> bool:
    return status_code == 429 or (treat_403_as_rate_limited and status_code == 403)


def _parse_retry_after(value: str | None) -> float | None:
    """`Retry-After` as delay-seconds. HTTP-date form is rare on these APIs and not worth chasing —
    a rate-limited run stops entirely (skill `aoe2-data-sources`), so a missing hint changes
    nothing about what the caller does next.
    """
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


# --- The shared request machinery, async and sync ------------------------------------------------


class AsyncBaseProvider:
    """Shared machinery for every async provider (`ProfileProvider`, `MatchHistoryProvider`,
    `ReplayProvider`, `EnrichmentProvider`): explicit timeout, the token bucket, retry with
    backoff on transient failures, immediate `ProviderRateLimited` on 429/403, a `provider_calls`
    record for every attempt, and the honest `User-Agent`.

    Not an `abc.ABC`: it declares no abstract method, only shared, concrete machinery. A concrete
    provider composes it (subclasses it and calls `_request`) rather than being forced to
    implement anything this base class does not itself define.

    `_request` returns the raw `httpx.Response` untouched — no JSON parsing, no status-based
    branching beyond the shared classification above — so the concrete provider decides how to
    read a 200 or a 404 (`ReplayProvider`'s 404 is data; nothing else's is) without this base class
    guessing on its behalf.
    """

    def __init__(
        self,
        *,
        provider: str,
        client: httpx.AsyncClient,
        timeout_seconds: float,
        rate_limiter: TokenBucket,
        call_sink: AsyncProviderCallSink | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self._provider = provider
        self._client = client
        self._timeout = httpx.Timeout(timeout_seconds)
        self._rate_limiter = rate_limiter
        self._call_sink = call_sink
        self._retry_policy = retry_policy or RetryPolicy()

    async def _request(
        self,
        method: str,
        url: str,
        *,
        endpoint: str,
        params: Mapping[str, Any] | None = None,
        json_body: Any | None = None,
        treat_403_as_rate_limited: bool = True,
    ) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self._retry_policy.max_attempts):
            await self._rate_limiter.acquire()
            started = time.monotonic()
            try:
                response = await self._client.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    timeout=self._timeout,
                    headers={"User-Agent": PROVIDER_USER_AGENT},
                )
            except httpx.TimeoutException as exc:
                await self._record(endpoint, None, started, rate_limited=False)
                last_error = exc
                if attempt + 1 >= self._retry_policy.max_attempts:
                    raise ProviderUnavailable(
                        f"{self._provider} timed out calling {endpoint}",
                        provider=self._provider,
                        endpoint=endpoint,
                    ) from exc
                await asyncio.sleep(self._retry_policy.delay_seconds(attempt))
                continue
            except httpx.HTTPError as exc:
                await self._record(endpoint, None, started, rate_limited=False)
                last_error = exc
                if attempt + 1 >= self._retry_policy.max_attempts:
                    raise ProviderUnavailable(
                        f"{self._provider} connection error calling {endpoint}: {exc}",
                        provider=self._provider,
                        endpoint=endpoint,
                    ) from exc
                await asyncio.sleep(self._retry_policy.delay_seconds(attempt))
                continue

            status_code = response.status_code
            rate_limited = _is_rate_limited(
                status_code, treat_403_as_rate_limited=treat_403_as_rate_limited
            )
            await self._record(endpoint, status_code, started, rate_limited=rate_limited)

            if rate_limited:
                raise ProviderRateLimited(
                    f"{self._provider} rate limited on {endpoint} ({status_code})",
                    provider=self._provider,
                    endpoint=endpoint,
                    status_code=status_code,
                    retry_after_seconds=_parse_retry_after(response.headers.get("Retry-After")),
                )
            if status_code >= 500:
                last_error = ProviderUnavailable(
                    f"{self._provider} returned {status_code} from {endpoint}",
                    provider=self._provider,
                    endpoint=endpoint,
                    status_code=status_code,
                )
                if attempt + 1 >= self._retry_policy.max_attempts:
                    raise last_error
                await asyncio.sleep(self._retry_policy.delay_seconds(attempt))
                continue

            return response

        # Unreachable: the loop above always returns or raises on its last iteration. Kept for
        # mypy (strict) and as a defensive backstop rather than a silent `None`.
        raise ProviderUnavailable(
            f"{self._provider} exhausted retries calling {endpoint}",
            provider=self._provider,
            endpoint=endpoint,
        ) from last_error

    async def _record(
        self, endpoint: str, status_code: int | None, started_at: float, *, rate_limited: bool
    ) -> None:
        if self._call_sink is None:
            return
        duration_ms = int((time.monotonic() - started_at) * 1000)
        await self._call_sink(
            ProviderCallRecord(
                provider=self._provider,
                endpoint=endpoint,
                status_code=status_code,
                duration_ms=duration_ms,
                rate_limited=rate_limited,
                called_at=datetime.now(UTC),
            )
        )


class SyncBaseProvider:
    """The synchronous twin of `AsyncBaseProvider`, built for `SteamAuthProvider` alone: the same
    timeout, retry, rate-limiting and `provider_calls` obligations, without requiring an event
    loop around the one authentication route that needs them. Not an `abc.ABC`, for the same
    reason as its async twin.
    """

    def __init__(
        self,
        *,
        provider: str,
        client: httpx.Client,
        timeout_seconds: float,
        rate_limiter: SyncTokenBucket,
        call_sink: SyncProviderCallSink | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self._provider = provider
        self._client = client
        self._timeout = httpx.Timeout(timeout_seconds)
        self._rate_limiter = rate_limiter
        self._call_sink = call_sink
        self._retry_policy = retry_policy or RetryPolicy()

    def _request(
        self,
        method: str,
        url: str,
        *,
        endpoint: str,
        params: Mapping[str, Any] | None = None,
        json_body: Any | None = None,
        treat_403_as_rate_limited: bool = True,
    ) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self._retry_policy.max_attempts):
            self._rate_limiter.acquire()
            started = time.monotonic()
            try:
                response = self._client.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    timeout=self._timeout,
                    headers={"User-Agent": PROVIDER_USER_AGENT},
                )
            except httpx.TimeoutException as exc:
                self._record(endpoint, None, started, rate_limited=False)
                last_error = exc
                if attempt + 1 >= self._retry_policy.max_attempts:
                    raise ProviderUnavailable(
                        f"{self._provider} timed out calling {endpoint}",
                        provider=self._provider,
                        endpoint=endpoint,
                    ) from exc
                time.sleep(self._retry_policy.delay_seconds(attempt))
                continue
            except httpx.HTTPError as exc:
                self._record(endpoint, None, started, rate_limited=False)
                last_error = exc
                if attempt + 1 >= self._retry_policy.max_attempts:
                    raise ProviderUnavailable(
                        f"{self._provider} connection error calling {endpoint}: {exc}",
                        provider=self._provider,
                        endpoint=endpoint,
                    ) from exc
                time.sleep(self._retry_policy.delay_seconds(attempt))
                continue

            status_code = response.status_code
            rate_limited = _is_rate_limited(
                status_code, treat_403_as_rate_limited=treat_403_as_rate_limited
            )
            self._record(endpoint, status_code, started, rate_limited=rate_limited)

            if rate_limited:
                raise ProviderRateLimited(
                    f"{self._provider} rate limited on {endpoint} ({status_code})",
                    provider=self._provider,
                    endpoint=endpoint,
                    status_code=status_code,
                    retry_after_seconds=_parse_retry_after(response.headers.get("Retry-After")),
                )
            if status_code >= 500:
                last_error = ProviderUnavailable(
                    f"{self._provider} returned {status_code} from {endpoint}",
                    provider=self._provider,
                    endpoint=endpoint,
                    status_code=status_code,
                )
                if attempt + 1 >= self._retry_policy.max_attempts:
                    raise last_error
                time.sleep(self._retry_policy.delay_seconds(attempt))
                continue

            return response

        raise ProviderUnavailable(
            f"{self._provider} exhausted retries calling {endpoint}",
            provider=self._provider,
            endpoint=endpoint,
        ) from last_error

    def _record(
        self, endpoint: str, status_code: int | None, started_at: float, *, rate_limited: bool
    ) -> None:
        if self._call_sink is None:
            return
        duration_ms = int((time.monotonic() - started_at) * 1000)
        self._call_sink(
            ProviderCallRecord(
                provider=self._provider,
                endpoint=endpoint,
                status_code=status_code,
                duration_ms=duration_ms,
                rate_limited=rate_limited,
                called_at=datetime.now(UTC),
            )
        )
