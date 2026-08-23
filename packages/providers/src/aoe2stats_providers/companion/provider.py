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

**`search_players` (T313, `PlayerSearchProvider`).** `GET /api/profiles?search={name}`
(`docs/data-sources.md` §3's "Profile search behaviour"), against the exact same `_breaker` and
token bucket `enrich_matches` uses — not a second instance of either, since a search storm and an
enrichment storm are the same source under the same protection
(`contracts/providers.md`). Behaves exactly like `enrich_matches` on every failure path (never
raises; a 403 is not rate limiting; a non-200 or a malformed body opens the breaker one step
further; a genuine 200, whatever it contains, closes it). The parser keeps only `profileId`,
`name`, `country`, `games` and `clan` (FR-004b — see `PlayerSearchResult` in `base.py` for what is
deliberately not there) and coerces `games` from the string the source sends it as
(`docs/data-sources.md` §3) into the `int | None` the contract promises.
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
    PlayerSearchPage,
    PlayerSearchResult,
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

    def is_degraded(self) -> bool:
        """Whether this source is currently known to be down, read off the same `_breaker`
        `enrich_matches` and `search_players` already consult before ever reaching the transport
        (module docstring) — no second breaker, no exception. `apps/api/src/aoe2stats_api/
        search.py`'s `_SearchProvider` Protocol requires exactly this method (T315's own module
        docstring: "wiring this service into the real search route (T319) is where that accessor
        needs to be added to the real provider"); this is that wiring's other half, kept on the
        provider itself rather than duplicated in `apps/api`, since the breaker it reports is
        this instance's own private state.
        """
        return not self._breaker.allow()

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

    async def search_players(self, query: str, *, limit: int) -> PlayerSearchPage:
        if not self._breaker.allow():
            return PlayerSearchPage(results=(), has_more=False)

        try:
            response = await self._request(
                "GET",
                f"{self._base_url}/profiles",
                endpoint="profiles",
                params={"search": query},
                # Same reasoning as `enrich_matches` (module docstring): a 403 here is documented,
                # expected bot-protection noise, not throttling.
                treat_403_as_rate_limited=False,
            )
        except ProviderError:
            self._breaker.record_failure()
            return PlayerSearchPage(results=(), has_more=False)

        if response.status_code != 200:
            self._breaker.record_failure()
            return PlayerSearchPage(results=(), has_more=False)

        try:
            body: Any = response.json()
        except ValueError:
            self._breaker.record_failure()
            return PlayerSearchPage(results=(), has_more=False)

        self._breaker.record_success()
        return _parse_search_page(body, limit=limit)


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


def _parse_search_page(body: Any, *, limit: int) -> PlayerSearchPage:
    """Build a `PlayerSearchPage` from a genuine `?search=` response
    (`docs/data-sources.md` §3), keeping only `PlayerSearchResult`'s five contract fields
    (FR-004b) and never the source's account-linking fields.

    `limit` is enforced here rather than on the wire: the contract only documents
    `?search={name}`, no page-size parameter, so truncating the parsed list is the one
    behaviour this method can promise regardless of what the source actually honours — the
    same "filter the response, not just the request" posture `_parse_matches` takes with
    `game_ids`. A truncation counts as "more" exactly like the source's own `hasMore` does.
    """
    if not isinstance(body, dict):
        return PlayerSearchPage(results=(), has_more=False)

    profiles = body.get("profiles")
    if not isinstance(profiles, list):
        return PlayerSearchPage(results=(), has_more=False)

    results: list[PlayerSearchResult] = []
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        result = _parse_search_result(profile)
        if result is not None:
            results.append(result)

    truncated = len(results) > limit
    if truncated:
        results = results[:limit]

    has_more = bool(body.get("hasMore")) or truncated
    return PlayerSearchPage(results=tuple(results), has_more=has_more)


def _parse_search_result(profile: dict[str, Any]) -> PlayerSearchResult | None:
    """One `profiles[]` entry, reduced to `profileId`, `name`, `country`, `games` and `clan` —
    and nothing else (FR-004b): `steamId`, `shared`, `sharedHistory` and `linkedProfiles` are
    never read, the same posture `_parse_matches` takes with `linkedProfiles` (module docstring).
    A malformed entry (missing or mistyped `profileId`/`name`) is dropped rather than failing the
    whole page — this provider degrades, it does not raise (module docstring).
    """
    profile_id = profile.get("profileId")
    alias = profile.get("name")
    if not isinstance(profile_id, int) or not isinstance(alias, str):
        return None

    country = profile.get("country")
    if not isinstance(country, str):
        country = None

    clan = profile.get("clan")
    if not isinstance(clan, str):
        clan = None

    return PlayerSearchResult(
        profile_id=profile_id,
        alias=alias,
        country=country,
        games_played=_parse_games_played(profile.get("games")),
        clan=clan,
    )


def _parse_games_played(value: Any) -> int | None:
    """The source sends `games` as a string (e.g. `"10665"`), never the `int` the contract
    promises (`docs/data-sources.md` §3, T313's task note) — this is the one coercion this
    module performs, not silent elsewhere: an unparseable or wrong-typed value becomes `None`
    rather than a raised error, matching `MatchEnrichment`'s "every field is optional" posture
    for this same degrade-not-raise provider.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None
