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
- the typed errors `ProviderUnavailable` (and its `ProviderMoved` subtype — see that class's own
  docstring), `ProviderRateLimited`, `ProviderContractViolation`, and strict Pydantic validation so
  a field of an unexpected type never becomes a coerced value.

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


class ProviderMoved(ProviderUnavailable):
    """A `ProviderUnavailable` subtype for the one failure shape that is not, in fact, "unhealthy":
    the endpoint itself has relocated, and the response proves it rather than merely timing out or
    5xx-ing. Two wire conditions raise this, both in `AsyncBaseProvider._request`/
    `SyncBaseProvider._request` below or in a concrete provider reading a status its own contract
    does not recognise as ordinary:

    - `httpx.TooManyRedirects` — the client (`wiring.py` sets `follow_redirects=True` on the one
      shared client every provider here is built from) tried to follow a redirect chain and gave
      up at its `max_redirects` ceiling. A genuine outage does not manifest as an endless chain of
      valid redirect responses; a host that has been reconfigured to bounce traffic somewhere new,
      possibly in a loop, does.
    - a residual 3xx a concrete provider reads directly off the response, for the cases
      `httpx.Response.has_redirect_location` does not cover even with `follow_redirects=True` — a
      3xx outside `{301, 302, 303, 307, 308}`, or one of those five with no `Location` header. See
      `aoems/provider.py::fetch_replay` for the one place this is currently read.

    Deliberately a subclass of `ProviderUnavailable`, not a sibling: every caller written before
    this class existed (`apps/ingester/src/aoe2stats_ingester/capture.py`'s
    `except ProviderUnavailable`) keeps its exact prior behaviour — bounded retry, then `failed` —
    for a case it never had a name for. A caller that wants to react differently (a human-facing
    alert distinct from an ordinary outage, say) can `except ProviderMoved` ahead of the parent
    without this module or any caller already written against `ProviderUnavailable` changing.
    `str(exc)` is written to say "moved"/"redirect" rather than "unavailable"/"error", since
    `last_error` is exactly what a human reviewing a stuck capture reads first (skill
    `aoe2-data-sources`; `capture.py`'s own module docstring on `failed_total`).
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


class EnrichedParticipant(StrictProviderModel):
    """One `teams[].players[]` entry from `EnrichmentProvider.enrich_matches` (data-model.md §2),
    keyed by `profile_id` on `MatchEnrichment.participants`. Only `color_id` is ever written to
    `match_players` — Relic has no colour, so companion is this field's sole source. The other four
    fields are carried so a disagreement with Relic's own `matchhistorymember[]`/
    `matchhistoryreportresults[]` is *visible*, never so they can overwrite it: Relic stays
    authoritative for `team_id`, `won` (`result`), `rating` and `rating_diff` wherever it serves
    them.

    `colorHex` is **deliberately not a field here**, and never will be: the hex belongs to the
    design system as a token (constitution VI), and a provider that could set a product colour
    would bypass the `-contrast` pairing those tokens exist to guarantee (constitution X's colour
    coming from a single, licensed vocabulary, not a third party's string).
    """

    color_id: int | None = None
    team_id: int | None = None
    won: bool | None = None
    rating: int | None = None
    rating_diff: int | None = None


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
    # keyed by `profile_id`, parsed from `teams[].players[]` (data-model.md §2). `None` when the
    # response carries no `teams`/`players` shape this provider can read, distinct from an empty
    # dict, which would claim "an empty match" rather than "nothing parsed".
    participants: dict[int, EnrichedParticipant] | None = None


@dataclass(frozen=True)
class PlayerSearchResult:
    """`PlayerSearchProvider.search_players` — one match from aoe2companion's `?search=` endpoint
    (`docs/data-sources.md` §3), reduced to the fields `contracts/providers.md`'s "The fields, and
    the one rule on them" names.

    A plain dataclass, not a `StrictProviderModel`: the enforcement this DTO exists for is the
    *absence* of a field, which is a property of the class definition itself, not of validation.
    `shared`, `shared_history` and `linked_profiles` have nowhere to be assigned here, deliberately
    — each for a reason `contracts/providers.md` records and that survives this field's addition,
    not a residue of the FR-004b strip that once covered all four of the source's account-linking
    fields alike.

    `unverified_steam_id` is the fifth: constitution IX at 3.0.0 (2026-08-24) treats every field
    the AoE2 DE APIs serve as public, which retired that strip for the source's `steamId` alone.
    Its name is the requirement, not a comment on it — it is `unverified_steam_id` and not
    `steam_id` so that a consumer who never opened `contracts/providers.md` cannot read an
    unverified third-party claim as a fact. A verified Steam sign-in (001 FR-006) is the only
    account link this project vouches for; this field MUST NOT be used to infer, suggest or act
    upon a relationship between profiles the user has not proven that way — no linking, no
    merging, no feature treating two profiles as one person on that basis (001 FR-045's remaining
    half).
    """

    profile_id: int
    alias: str
    country: str | None
    games_played: int | None
    clan: str | None
    # The source's own claim, carried unverified (constitution IX 3.0.0, see docstring above).
    # Never used to link or merge profiles.
    unverified_steam_id: str | None
    # The Steam avatar hash the record carries under `avatarhash` (data-model.md §2). A hash, never
    # a URL — nothing in `packages/providers` builds the Steam CDN URL from it (FR-008a, FR-015).
    avatar_hash: str | None = None


@dataclass(frozen=True)
class PlayerSearchPage:
    """`PlayerSearchProvider.search_players`'s return value: one page of `PlayerSearchResult`,
    plus whether the source reports more beyond it.
    """

    results: Sequence[PlayerSearchResult]
    has_more: bool


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


@runtime_checkable
class PlayerSearchProvider(Protocol):
    """Display-name search against aoe2companion, the only source that offers one (§1 of
    `docs/data-sources.md`). Implemented by `CompanionEnrichmentProvider`, sharing its circuit
    breaker and token bucket with `enrich_matches` rather than duplicating either
    (`contracts/providers.md`). `search_players` never raises: a 403, an outage or a malformed
    body all come back as an empty page, exactly like `enrich_matches`'s failure mode.

    `is_degraded()` is part of this contract, not a `CompanionEnrichmentProvider`-only extra: it
    is the one way a caller can tell "the source is currently known to be down" from "a genuine
    empty result" *before* ever calling `search_players` (`search_players` itself never raises, so
    there is no exception to read that signal off — `contracts/providers.md`'s "Failure" section).
    Read off the provider's own circuit breaker, with no side effect of its own.

    `last_call_failed()` is the second, distinct signal `contracts/providers.md`'s BL-2 remediation
    added: `is_degraded()` alone can only say "the breaker is open", which is false for the first
    calls of a fresh outage — a consecutive-failure breaker admits a sub-threshold window where
    every call so far has failed but the count has not yet reached `_FAILURE_THRESHOLD`
    (`companion/provider.py`). `is_degraded()` would read `False` through that whole window even
    though the call the caller just made did not succeed, and a caller that only checks
    `is_degraded()` after the call caches that failure as a confident, empty answer. `last_call_
    failed()` answers "did the call this provider instance just completed fail?", independent of
    whether the breaker's own threshold has tripped — a caller (`apps/api/src/aoe2stats_api/
    search.py`) must check both after every call it makes, not `is_degraded()` alone.
    """

    def is_degraded(self) -> bool: ...

    def last_call_failed(self) -> bool: ...

    async def search_players(self, query: str, *, limit: int) -> PlayerSearchPage: ...


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

    Only the ceiling is clamped — to `capacity`, the burst allowance. The floor is deliberately
    left to go negative: a negative balance is a debt, in seconds' worth of future refill, that the
    *next* reservation must additionally wait out. An earlier version clamped a shortfall to zero
    instead, which erased that debt — every caller that reserved while the bucket was empty then
    computed its wait from the *same* zeroed state and got the *same* answer, so N concurrent
    `acquire()` calls all fired together instead of `1 / rate_per_second` apart (measured: one
    request at t=0 and four simultaneously at t=1.0 s against `rate_per_second=1`). Each successive
    reservation now advances this cursor by exactly one more `1 / rate_per_second`, so N acquirers
    — however they are interleaved by the lock — are spaced that far apart, not merely of that
    magnitude.
    """
    tokens = min(capacity, tokens + elapsed * rate_per_second) - 1
    wait = -tokens / rate_per_second if tokens < 0 else 0.0
    return tokens, wait


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
            except httpx.TooManyRedirects as exc:
                # Not retried, unlike the timeout/connection branches below: a redirect chain
                # that outlives `max_redirects` is a property of how the source is now routed,
                # not a transient blip that a few hundred milliseconds of backoff fixes. See
                # `ProviderMoved`'s own docstring.
                await self._record(endpoint, None, started, rate_limited=False)
                raise ProviderMoved(
                    f"{self._provider} exceeded the redirect limit calling {endpoint}: {exc}",
                    provider=self._provider,
                    endpoint=endpoint,
                ) from exc
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
            except httpx.TooManyRedirects as exc:
                # The sync twin of the async branch above — see `ProviderMoved`'s own docstring
                # for why this is raised immediately rather than folded into the retry loop.
                self._record(endpoint, None, started, rate_limited=False)
                raise ProviderMoved(
                    f"{self._provider} exceeded the redirect limit calling {endpoint}: {exc}",
                    provider=self._provider,
                    endpoint=endpoint,
                ) from exc
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
