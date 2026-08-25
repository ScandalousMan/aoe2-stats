"""`CompanionEnrichmentProvider` (T051) — `EnrichmentProvider` against `data.aoe2companion.com`.

`docs/data-sources.md` §3 and `contracts/providers.md`'s `EnrichmentProvider` section are ground
truth. This is "the only provider whose failure is not an error": `enrich_matches` never raises —
a 403 (documented, expected bot-protection noise), a full outage (5xx exhausting the shared retry
budget), and a malformed body all collapse to the caller getting nothing back, exactly like an
empty result would look. Nothing here uses `_request`'s default `treat_403_as_rate_limited=True`
(`base.py`): a 403 from this source is not throttling, so it must not raise `ProviderRateLimited`
the way every other provider's unexpected 403 would.

**Circuit breaker.** `docs/data-sources.md` §3: "single-maintainer project, ... no announced rate
limits, `/api` root returns 403 ... behind a cache and a circuit breaker." `CircuitBreaker` below
counts consecutive failures (non-200 responses or a raised `ProviderError`) and, once
`_FAILURE_THRESHOLD` is reached, stops issuing requests at all for `_OPEN_SECONDS` — a genuine
outage or a persistent block must not keep re-spending this provider's retry budget on every single
`enrich_matches` call forever. A success (a 200, whatever it contains) resets the counter and
closes the breaker immediately: an intermittent 403 that clears on the next try must not leave the
breaker degraded.

**Breaker lifetime is the caller's decision, not this class's — and `breaker` is required, not
optional (MJ-3 remediation).** An earlier version defaulted `breaker` to `None` and silently built
a fresh one (`build_circuit_breaker()` below) when omitted; that default is exactly how the next
call site reproduces B1 by omission, with no test able to see it — a provider rebuilt every request
around its own, always-closed breaker can never let `is_degraded()` observe an outage the previous
request just recorded. Every caller now constructs the breaker itself, explicitly, and hands it in:
`apps/api/src/aoe2stats_api/routers/players.py`'s `_build_search_provider` does this through
`aoe2stats_providers.wiring.build_companion_breaker()`, for the same reason it holds
`_COMPANION_HTTP_CLIENT`/`_COMPANION_RATE_LIMITER` at module scope rather than rebuilding them too;
a short-lived provider built once and used once, e.g. in a unit test, still calls
`build_circuit_breaker()` below itself rather than relying on a default that no longer exists.

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
(`contracts/providers.md`). Behaves like `enrich_matches` on every failure path that reaches the
transport (never raises; a 403 is not rate limiting; a non-200 opens the breaker one step further),
but a genuine 200 does **not**, by itself, close it (BL-1 remediation). `_parse_search_page` below
distinguishes a body that parses into the contracted `{"profiles": [...]}` shape — closes the
breaker, whatever the list contains, including empty — from one that does not, at either level —
an envelope-level drift (a renamed key, a wrapped list, a bare `[]`), or a record-level one
(BL-5: `profiles` is real and non-empty, but every entry's own `profileId`/`name` has been renamed,
so nothing survives `_parse_search_result`) — both treated exactly like a non-200:
`record_failure()`, an empty page returned, never an exception. Recording success *before* that
distinction existed meant a single-maintainer API renaming a field, at either level, would
permanently answer every search `degraded: false, results: []` — FR-003's exact prohibition — with
nothing to self-correct it, because the breaker never saw a failure. The parser keeps
`profileId`, `name`, `country`, `games`, `clan` and, since constitution IX 3.0.0 (2026-08-24),
`steamId` — carried as `PlayerSearchResult.unverified_steam_id`, never as `steam_id`
(see `PlayerSearchResult` in `base.py` for the name and what is still deliberately not there:
`shared`, `sharedHistory`, `linkedProfiles`) — and coerces `games` from the string the source
sends it as (`docs/data-sources.md` §3) into the `int | None` the contract promises.

**`last_call_failed()` (BL-2 remediation).** `is_degraded()` alone only ever answers "is the
breaker open", which stays `False` through the first `_FAILURE_THRESHOLD - 1` failures of a fresh
outage — a real gap: `apps/api/src/aoe2stats_api/search.py` used to read `is_degraded()` alone
after a call and cache the first two failures of every outage as a confident "no such player" for
the full TTL. `last_call_failed()` (`base.py`'s `PlayerSearchProvider`) is read straight off the
same `_breaker`'s own last recorded outcome — `True` after any `record_failure()`, `False` after
any `record_success()` — regardless of whether that failure also tripped the threshold, so a caller
that checks it after every `search_players` call catches the sub-threshold window `is_degraded()`
alone cannot see.
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


class CircuitBreaker:
    """Consecutive-failure circuit breaker, closed by default. Not shared machinery in `base.py`:
    `EnrichmentProvider` is the only `DataProvider` this application asks to survive an outage
    silently (see the module docstring), so nothing else needs one. Public (not `_CircuitBreaker`)
    because a caller that wants breaker state to outlive one `CompanionEnrichmentProvider`
    instance — see the module docstring's "Breaker lifetime" note — needs the type name to hold
    one itself; `build_circuit_breaker()` below is the constructor most such callers actually want.
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
        # BL-2 remediation: `_consecutive_failures >= _failure_threshold` (what `allow()` reads)
        # cannot express "the call that was just made failed" during the sub-threshold window —
        # the first `_failure_threshold - 1` failures of a fresh outage leave this `False` too,
        # by design, so this tracks the *last* recorded outcome on its own, independent of the
        # threshold. `last_call_failed()` below is this field's only reader.
        self._last_call_failed = False

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
        self._last_call_failed = False

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        self._last_call_failed = True
        if self._consecutive_failures >= self._failure_threshold:
            self._opened_until = self._clock() + self._open_seconds

    def last_call_failed(self) -> bool:
        """Whether the most recent `record_success`/`record_failure` call was a failure — the
        signal `is_degraded()` (`allow()`) cannot give during the sub-threshold window (module
        docstring's "BL-2 remediation" note). `False` before either has ever been called: nothing
        has failed yet, which is the same posture a freshly-closed breaker already takes.
        """
        return self._last_call_failed


def build_circuit_breaker() -> CircuitBreaker:
    """A fresh, closed `CircuitBreaker` at this module's own `_FAILURE_THRESHOLD`/`_OPEN_SECONDS`
    — the constructor a caller that wants to hold one for the process's lifetime should use
    (module docstring's "Breaker lifetime" note), rather than reaching for the two private
    constants itself.
    """
    return CircuitBreaker(failure_threshold=_FAILURE_THRESHOLD, open_seconds=_OPEN_SECONDS)


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
        breaker: CircuitBreaker,
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
        # Required, not defaulted (module docstring's "Breaker lifetime" note, MJ-3 remediation):
        # a caller shares one breaker across many short-lived `CompanionEnrichmentProvider`
        # instances by constructing it once (`build_circuit_breaker()`) and passing it in every
        # time, never by relying on this class to build one silently when omitted.
        self._breaker = breaker

    def is_degraded(self) -> bool:
        """Whether this source is currently known to be down, read off the same `_breaker`
        `enrich_matches` and `search_players` already consult before ever reaching the transport
        (module docstring) — no second breaker, no exception. Part of `PlayerSearchProvider`
        itself (`contracts/providers.md`, `packages/providers/.../base.py`), not a private
        extension `apps/api` reaches past the contract for: `apps/api/src/aoe2stats_api/search.py`
        depends on the Protocol, never on this concrete class.
        """
        return not self._breaker.allow()

    def last_call_failed(self) -> bool:
        """Whether the `search_players` call this provider instance most recently completed
        failed — `True` through the sub-threshold window `is_degraded()` cannot see (module
        docstring's "BL-2 remediation" note, `base.py`'s `PlayerSearchProvider`).
        """
        return self._breaker.last_call_failed()

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

        try:
            page = _parse_search_page(body, limit=limit)
        except _MalformedSearchResponse:
            # BL-1 remediation: a 200 that does not parse into `{"profiles": [...]}` — a renamed
            # key, a wrapped list, a bare `[]` — is a source drift, not a genuine zero-result
            # answer, and must not be recorded as (or look like) one. Recording success here, as
            # the code used to, is exactly how FR-003 inverted forever the moment the source's
            # shape drifted: every search would answer `degraded: false, results: []` with nothing
            # to self-correct it, because the breaker never saw a failure.
            self._breaker.record_failure()
            return PlayerSearchPage(results=(), has_more=False)

        self._breaker.record_success()
        return page


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


class _MalformedSearchResponse(Exception):
    """Raised by `_parse_search_page` when a 200's body does not parse into the contracted
    `{"profiles": [...]}` shape — either at the envelope (a renamed key, a wrapped list, a bare
    `[]`, anything but a dict carrying a `profiles` list) or at the record level (BL-5: `profiles`
    is a real, non-empty list, but every entry in it has had `profileId` or `name` renamed, so
    nothing parses). Never raised for a genuine zero-match answer (`{"profiles": []}` is a
    perfectly parseable, empty list): that is `PlayerSearchPage(results=(), has_more=False)`,
    the same value this exception's own callers return on catching it, but recorded as a *success*
    by `search_players` — the whole distinction BL-1 (and, at the record level, BL-5) exists to
    draw. Private to this module: `search_players` is the only caller, and turns this into
    `_breaker.record_failure()`, never into something a caller of `search_players` itself would
    see.
    """


def _parse_search_page(body: Any, *, limit: int) -> PlayerSearchPage:
    """Build a `PlayerSearchPage` from a genuine `?search=` response
    (`docs/data-sources.md` §3), keeping `PlayerSearchResult`'s contract fields — including the
    source's `steamId` claim, carried as `unverified_steam_id` (constitution IX 3.0.0) — and never
    `shared`, `sharedHistory` or `linkedProfiles` (`base.py`'s `PlayerSearchResult`,
    `contracts/providers.md`'s "The fields, and the one rule on them").

    Raises `_MalformedSearchResponse` — never returns a page — when `body` does not even have the
    contracted shape (not a dict, or no `profiles` list at all): that is a source drift
    `search_players` must record as a failure (BL-1), not a page this function can silently stand
    in an empty one for. Also raises it when `profiles` is non-empty but every single entry fails
    to parse (BL-5): a rename of `profileId` or `name` *inside* each record leaves the envelope
    intact while `_parse_search_result` drops every entry, and a `profiles` list that was never
    empty on the wire producing zero results is a record-level drift, not a genuine zero-match
    answer — the same distinction BL-1 draws one nesting level up. A `profiles` list that is
    genuinely empty (`{"profiles": []}`), or whose *individual* entries are malformed and dropped
    by `_parse_search_result` while at least one other entry in the same page still parses, is a
    genuine, parseable answer and returns normally — dropping one bad entry does not throw away a
    response that otherwise parsed; dropping *every* entry is not a response that parsed at all.

    `limit` is enforced here rather than on the wire: the contract only documents
    `?search={name}`, no page-size parameter, so truncating the parsed list is the one
    behaviour this method can promise regardless of what the source actually honours — the
    same "filter the response, not just the request" posture `_parse_matches` takes with
    `game_ids`. A truncation counts as "more" exactly like the source's own `hasMore` does.
    """
    if not isinstance(body, dict):
        raise _MalformedSearchResponse("search response body is not a JSON object")

    profiles = body.get("profiles")
    if not isinstance(profiles, list):
        raise _MalformedSearchResponse("search response body carries no `profiles` list")

    results: list[PlayerSearchResult] = []
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        result = _parse_search_result(profile)
        if result is not None:
            results.append(result)

    if profiles and not results:
        # BL-5: the envelope parsed (`profiles` is a real, non-empty list), but not one entry in
        # it survived `_parse_search_result` — a record-level rename (`profileId`/`name`) rather
        # than the envelope-level drift the checks above already catch. A non-empty `profiles`
        # list that yields zero results is not a genuine zero-match answer.
        raise _MalformedSearchResponse(
            "no `profiles` entry carried the contracted `profileId`/`name` fields"
        )

    truncated = len(results) > limit
    if truncated:
        results = results[:limit]

    has_more = bool(body.get("hasMore")) or truncated
    return PlayerSearchPage(results=tuple(results), has_more=has_more)


def _parse_search_result(profile: dict[str, Any]) -> PlayerSearchResult | None:
    """One `profiles[]` entry, reduced to `profileId`, `name`, `country`, `games`, `clan` and
    `steamId` (carried as `unverified_steam_id` — constitution IX 3.0.0, `base.py`'s
    `PlayerSearchResult`) — and nothing else: `shared`, `sharedHistory` and `linkedProfiles` are
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

    unverified_steam_id = profile.get("steamId")
    if not isinstance(unverified_steam_id, str):
        unverified_steam_id = None

    return PlayerSearchResult(
        profile_id=profile_id,
        alias=alias,
        country=country,
        games_played=_parse_games_played(profile.get("games")),
        clan=clan,
        unverified_steam_id=unverified_steam_id,
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
