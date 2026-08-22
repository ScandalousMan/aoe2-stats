"""`CompanionEnrichmentProvider` (T051) — `EnrichmentProvider` against `data.aoe2companion.com`.

`docs/data-sources.md` §3 and `contracts/providers.md`'s `EnrichmentProvider` section are ground
truth. This is "the only provider whose failure is not an error": `enrich_matches` never raises —
a 403 (documented, expected bot-protection noise), a full outage (5xx exhausting the shared retry
budget), and a malformed body all collapse to the caller getting nothing back, exactly like an
empty result would look. Nothing here uses `_request`'s default `treat_403_as_rate_limited=True`
(`base.py`): a 403 from this source is not throttling, so it must not raise `ProviderRateLimited`
the way every other provider's unexpected 403 would.

**Circuit breaker.** `docs/data-sources.md` §3: "single-maintainer project, ... no announced rate
limits, `/api` root returns 403 ... behind a cache and a circuit breaker." `_CircuitBreaker` below
counts consecutive failures (non-200 responses or a raised `ProviderError`) and, once
`_FAILURE_THRESHOLD` is reached, stops issuing requests at all for `_OPEN_SECONDS` — a genuine
outage or a persistent block must not keep re-spending this provider's retry budget on every single
`enrich_matches` call forever. A success (a 200, whatever it contains) resets the counter and
closes the breaker immediately: an intermittent 403 that clears on the next try must not leave the
breaker degraded.

**FR-045.** `linkedProfiles` is not read anywhere below, deliberately: the parsing here only ever
looks up `matchId`, `mapName`, `gameModeName`, `speedName`, `teams`, `players`, `profileId` and
`civName` — the fields `MatchEnrichment` actually carries. `linkedProfiles` does not appear on
`MatchEnrichment` either (`base.py`), so there is nowhere for it to leak to even by accident.

**The endpoint.** `docs/data-sources.md` §3 only documents `GET /api/matches?profile_ids=a,b`
(filtered by *profile*, not by match) — this provider's `game_ids` filter on the request itself is
therefore best-effort and unverified against the live API (nightly contract tests, not this unit
suite, are what would catch a drift here). Filtering the *response* down to the requested
`game_ids` happens unconditionally in this module regardless of what the server actually honoured,
so a server that ignores the filter and returns unrelated matches never leaks them to the caller.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from typing import Any

import httpx

from aoe2stats_providers.base import (
    AsyncBaseProvider,
    AsyncProviderCallSink,
    MatchEnrichment,
    ProviderContractViolation,
    ProviderError,
    RetryPolicy,
    TokenBucket,
    parse_strict,
)

COMPANION_BASE_URL = "https://data.aoe2companion.com/api"

# Consecutive failures (non-200 response, or a raised `ProviderError`) before the breaker opens.
_FAILURE_THRESHOLD = 3

# How long the breaker stays open once it trips, before it lets one more request through.
_OPEN_SECONDS = 30.0


class _CircuitBreaker:
    """Consecutive-failure circuit breaker, closed by default. Not shared machinery in `base.py`:
    `EnrichmentProvider` is the only `DataProvider` this application asks to survive an outage
    silently (see the module docstring), so nothing else needs one.
    """

    def __init__(
        self,
        *,
        failure_threshold: int,
        open_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._open_seconds = open_seconds
        self._clock = clock
        self._consecutive_failures = 0
        self._opened_until: float | None = None

    def allow(self) -> bool:
        """Whether a call may reach the transport right now. Once the cooldown has elapsed this
        allows a single probe through rather than staying open forever; that probe's own outcome
        (`record_success`/`record_failure`) decides whether the breaker actually closes again.
        """
        if self._opened_until is None:
            return True
        return self._clock() >= self._opened_until

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self._opened_until = None

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._failure_threshold:
            self._opened_until = self._clock() + self._open_seconds


class CompanionEnrichmentProvider(AsyncBaseProvider):
    """`EnrichmentProvider` (`contracts/providers.md`) against aoe2companion. `enrich_matches`
    never raises — see the module docstring.
    """

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        timeout_seconds: float,
        rate_limiter: TokenBucket,
        call_sink: AsyncProviderCallSink | None = None,
        retry_policy: RetryPolicy | None = None,
        base_url: str = COMPANION_BASE_URL,
    ) -> None:
        super().__init__(
            provider="companion",
            client=client,
            timeout_seconds=timeout_seconds,
            rate_limiter=rate_limiter,
            call_sink=call_sink,
            retry_policy=retry_policy,
        )
        self._base_url = base_url
        self._breaker = _CircuitBreaker(
            failure_threshold=_FAILURE_THRESHOLD, open_seconds=_OPEN_SECONDS
        )

    async def enrich_matches(self, game_ids: Sequence[int]) -> dict[int, MatchEnrichment]:
        if not game_ids:
            return {}
        if not self._breaker.allow():
            return {}

        try:
            response = await self._request(
                "GET",
                f"{self._base_url}/matches",
                endpoint="matches",
                params={"matchIds": ",".join(str(game_id) for game_id in game_ids)},
                # A 403 here is documented, expected bot-protection noise (module docstring), not
                # throttling — `_request`'s default would otherwise raise `ProviderRateLimited`.
                treat_403_as_rate_limited=False,
            )
        except ProviderError:
            self._breaker.record_failure()
            return {}

        if response.status_code != 200:
            # Any non-200 (a 403 that `_request` did not raise on above, a 404, ...) is the same
            # "nothing to enrich with" outcome as a raised `ProviderError` — no exception, and the
            # circuit breaker treats it identically to one.
            self._breaker.record_failure()
            return {}

        try:
            body: Any = response.json()
        except ValueError:
            self._breaker.record_failure()
            return {}

        self._breaker.record_success()
        return _parse_matches(body, game_ids, provider=self._provider)


def _parse_matches(
    body: Any, game_ids: Sequence[int], *, provider: str
) -> dict[int, MatchEnrichment]:
    """Build `{game_id: MatchEnrichment}` from a genuine `matches` response, keeping only the
    entries the caller actually asked for (see the module docstring's note on the endpoint's
    filter being best-effort) and never reading `linkedProfiles` (FR-045).
    """
    requested = set(game_ids)
    result: dict[int, MatchEnrichment] = {}
    if not isinstance(body, dict):
        return result

    for match in body.get("matches") or []:
        if not isinstance(match, dict):
            continue
        match_id = match.get("matchId")
        if match_id not in requested:
            continue

        civilizations: dict[int, str] = {}
        for team in match.get("teams") or []:
            if not isinstance(team, dict):
                continue
            for player in team.get("players") or []:
                if not isinstance(player, dict):
                    continue
                profile_id = player.get("profileId")
                civ_name = player.get("civName")
                if isinstance(profile_id, int) and isinstance(civ_name, str):
                    civilizations[profile_id] = civ_name

        fields = {
            "game_id": match_id,
            "map_display_name": match.get("mapName"),
            "game_mode": match.get("gameModeName"),
            "game_speed": match.get("speedName"),
            "civilizations": civilizations or None,
        }
        try:
            enrichment = parse_strict(
                MatchEnrichment, fields, provider=provider, endpoint="matches"
            )
        except ProviderContractViolation:
            # One malformed entry does not throw away the rest of a batch — this provider's
            # failure is degradation, not an all-or-nothing exception (module docstring).
            continue
        result[match_id] = enrichment

    return result
