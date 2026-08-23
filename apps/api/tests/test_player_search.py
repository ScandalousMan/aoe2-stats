"""Tests for the search service (T315, T316), `apps/api/src/aoe2stats_api/search.py` — encoding
quickstart scenario 1 ("search degrades honestly") and FR-004e's cache.

**`aoe2stats_api.search` exists (T315, T316 both landed).** Every test below still imports it
inside its own body rather than at module scope — a convention this file keeps deliberately rather
than one it still needs: `packages/providers/`'s sibling tasks it was once written test-first
against (T311-T313) have all landed too, so nothing here depends on landing order any more, but
moving every import back to module scope buys nothing this file needs and only churns the diff.

**Two implementing tasks share this file, and the reason string says which owns each test.** T315
("the search service: query normalisation, `profile_search_cache` read and write with the
configured TTL, deletion of entries past that TTL opportunistically on write, ... the `degraded`
signal derived from the provider's breaker state rather than from an exception") owns the cache,
the normalisation and the structural half of `degraded` — that a source known to be down is never
called at all, and that the flag it produces is `True` with the documented reason. T316 ("the local
fallback over `aoe_profiles`") owns whether the *content* the fallback returns is correct: the
right profiles, in the right order, with none withheld. A test that only proves the flag is right
belongs to T315; a test that proves the fallback's answer is right belongs to T316, even though
both exercise the same `search_players` entry point once both tasks have landed.

**`is_degraded()` and `last_call_failed()` are part of `PlayerSearchProvider` itself, not this
file's own invention.** This file was the first to need "the caller must distinguish 'no such
player' from 'search is unavailable' from the same signal the existing enrichment path uses — the
circuit breaker's own state — not from an exception" (`contracts/providers.md`'s "Failure"
section), before either `PlayerSearchResult`/`PlayerSearchPage` carried any such signal, so
`_FakeSearchProvider` below added `is_degraded()` as this file's own decision about what
`apps/api/src/aoe2stats_api/search.py` needs from whatever provider it is given. T313 grew the
matching method on `CompanionEnrichmentProvider`, and the round-2 review's BL-2 remediation moved
both `is_degraded()` and its sibling `last_call_failed()` onto the `PlayerSearchProvider` Protocol
itself (`base.py`, `contracts/providers.md`) — `_FakeSearchProvider` now implements both because
the contract requires them, not because this file still needs to invent either.

**No import from `aoe2stats_providers` anywhere in this file, on purpose.** `_FakeSearchResult` and
`_FakeSearchPage` below still mirror `contracts/providers.md`'s `PlayerSearchResult`/
`PlayerSearchPage` field-for-field, kept as a stand-in rather than switched to the real dataclasses
now that they exist, for the same reason the lazy imports above are kept: nothing here needs the
change.

**`search_players(...)` returning a `SearchOutcome(results, degraded, reason)`** is the signature
and return shape this file committed `aoe2stats_api.search` to: `session`, `provider`, `query`,
then `limit`, `ttl_seconds`, `fallback_ttl_seconds` (defaulted) and `now` (defaulted), all keyword-
only past `query`. `fallback_ttl_seconds` was added by the round-2 review's BL-3 remediation
(module docstring in `search.py`) and defaults to that module's own protective constant, so every
existing call site below that predates it is unaffected. `ttl_seconds` is an
explicit parameter rather than a call into `get_settings()` inside the function, for the identical
reason `check_and_increment`'s `window_seconds` is: a service function stays a pure function of its
inputs, and the router (T319) is where `PLAYER_SEARCH_CACHE_TTL_SECONDS` gets read once and passed
in. `now` is explicit for the same reason it is in `ratelimit.py` — deterministic TTL boundaries
under test, never a race against the real clock. `reason` carries `"search_source_unavailable"`
exactly as `contracts/http-api.md` specifies for the response body's own `reason` field, so the
router can pass it through unchanged.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_storage.models import (
    AoeProfile,
    Match,
    MatchPlayer,
    ProfileSearchCache,
    ProviderCall,
)

# `contracts/http-api.md`: "`search` returns `{"results": [...], "degraded": bool, "reason": null
# | "..."}`" and names this exact string for the one non-null reason a successful search body ever
# carries.
_SEARCH_SOURCE_UNAVAILABLE_REASON = "search_source_unavailable"

# An epoch-aligned instant, exactly like `test_rate_limits.py`'s own `_WINDOW_ORIGIN`: every `now`
# below is expressed as an offset from it, so no test here races real time.
_NOW = datetime(2026, 1, 1, tzinfo=UTC)

_TTL_SECONDS = 300


# --- The fake provider this file's own interface decision rests on ------------------------------


@dataclass(frozen=True)
class _FakeSearchResult:
    """Field-for-field `contracts/providers.md`'s `PlayerSearchResult` — see the module docstring
    on why this file does not import the real thing."""

    profile_id: int
    alias: str
    country: str | None
    games_played: int | None
    clan: str | None


@dataclass(frozen=True)
class _FakeSearchPage:
    """Field-for-field `contracts/providers.md`'s `PlayerSearchPage`."""

    results: Sequence[_FakeSearchResult]
    has_more: bool = False


class _FakeSearchProvider:
    """Stands in for `PlayerSearchProvider` (`base.py`, `contracts/providers.md`). `is_degraded()`
    and `last_call_failed()` are both part of that contract now (module docstring's "BL-2
    remediation" paragraph), so this fake implements both rather than inventing either.

    `db_session`, when given, makes `search_players` write one real `provider_calls` row per call —
    exactly what the genuine `CompanionEnrichmentProvider` does today through its shared
    `call_sink` (`packages/providers/src/aoe2stats_providers/base.py`'s `AsyncBaseProvider`) — so
    that `test_a_repeated_query_hits_the_cache_and_calls_the_provider_once` can assert against the
    real table FR-004e is about, rather than against a call counter this file invented.
    """

    def __init__(
        self,
        *,
        page: _FakeSearchPage,
        degraded: bool = False,
        last_call_failed: bool = False,
        db_session: AsyncSession | None = None,
    ) -> None:
        self._page = page
        self._degraded = degraded
        # BL-2 remediation: independent of `degraded` (the breaker's own threshold) — a sub-
        # threshold failure sets this without the breaker itself being open yet. Defaults to
        # `False` so every call site written before this parameter existed keeps modelling "the
        # call succeeded" unless it deliberately says otherwise.
        self._last_call_failed = last_call_failed
        self._db_session = db_session
        self.queries: list[str] = []

    def is_degraded(self) -> bool:
        return self._degraded

    def last_call_failed(self) -> bool:
        return self._last_call_failed

    async def search_players(self, query: str, *, limit: int) -> _FakeSearchPage:
        self.queries.append(query)
        if self._db_session is not None:
            self._db_session.add(
                ProviderCall(provider="companion", endpoint="profiles", status_code=200)
            )
            await self._db_session.flush()
        return self._page


# --- Seeding helpers -------------------------------------------------------------------------


async def _seed_profile(
    db_session: AsyncSession, *, profile_id: int, alias: str, country: str | None = "FR"
) -> None:
    db_session.add(AoeProfile(profile_id=profile_id, alias=alias, country=country))
    await db_session.flush()


async def _seed_matches_played(
    db_session: AsyncSession, *, profile_id: int, count: int, starting_game_id: int
) -> None:
    """`count` distinct `matches` rows, each carrying one `match_players` row for `profile_id` —
    what the fallback's "most-played first" ordering (FR-004a) counts against. No second
    participant per row: nothing in the schema requires one, and this test needs only a count."""
    for offset in range(count):
        game_id = starting_game_id + offset
        db_session.add(
            Match(
                game_id=game_id,
                leaderboard_id=3,
                completed_at=_NOW,
                source="relic",
                raw_payload={"game_id": game_id},
            )
        )
        db_session.add(MatchPlayer(game_id=game_id, profile_id=profile_id))
    await db_session.flush()


async def _cache_row_count(db_session: AsyncSession) -> int:
    result = await db_session.execute(select(func.count()).select_from(ProfileSearchCache))
    return result.scalar_one()


async def _provider_call_count(db_session: AsyncSession) -> int:
    result = await db_session.execute(select(func.count()).select_from(ProviderCall))
    return result.scalar_one()


# --- T315: the cache -------------------------------------------------------------------------


async def test_a_repeated_query_hits_the_cache_and_calls_the_provider_once(
    db_session: AsyncSession,
) -> None:
    """FR-004e, quickstart scenario 1: a repeated query is answered from `profile_search_cache`
    on the second ask, not from a second call to the source — asserted against the real
    `provider_calls` table `_FakeSearchProvider` writes to, the same evidence FR-012's own
    `provider_calls` obligation is checked against everywhere else in this codebase."""
    from aoe2stats_api.search import search_players

    page = _FakeSearchPage(
        results=[_FakeSearchResult(uuid.uuid4().int % 10_000, "Zephyr", "FR", 42, None)]
    )
    provider = _FakeSearchProvider(page=page, db_session=db_session)

    first = await search_players(
        db_session, provider, "Zephyr", limit=10, ttl_seconds=_TTL_SECONDS, now=_NOW
    )
    second = await search_players(
        db_session,
        provider,
        "Zephyr",
        limit=10,
        ttl_seconds=_TTL_SECONDS,
        now=_NOW + timedelta(seconds=5),
    )

    assert provider.queries == ["Zephyr"]
    assert await _provider_call_count(db_session) == 1
    assert first.degraded is False
    assert second.degraded is False
    assert [(r.profile_id, r.alias) for r in first.results] == [
        (r.profile_id, r.alias) for r in second.results
    ]
    assert await _cache_row_count(db_session) == 1


async def test_query_normalisation_collapses_case_whitespace_and_unicode_form(
    db_session: AsyncSession,
) -> None:
    """`normalise_query` is the function `profile_search_cache.query_normalised` is keyed on
    (data-model.md). Case, internal whitespace and Unicode form must all collapse: "é" written
    precomposed (U+00E9) and "é" written as "e" plus a combining acute accent (U+0065 U+0301) are
    the same visible name and must produce the same cache key, or a search for one form would
    never hit a cache warmed by the other."""
    from aoe2stats_api.search import normalise_query

    precomposed = "Caf\u00e9  Warrior"
    # "e" followed by a combining acute accent (U+0301) rather than the precomposed
    # "é" above -- the same visible name, a different byte sequence, and therefore
    # a different cache key unless `normalise_query` normalises Unicode form.
    combining = "Cafe\u0301  Warrior"
    upper_and_padded = "  CAFÉ WARRIOR  "

    assert normalise_query(precomposed) == normalise_query(combining)
    assert normalise_query(precomposed) == normalise_query(upper_and_padded)
    assert normalise_query("  Foo   Bar  ") == normalise_query("foo bar")


async def test_degraded_signal_comes_from_the_providers_breaker_not_from_calling_it(
    db_session: AsyncSession,
) -> None:
    """FR-004d, quickstart scenario 1: with the source unavailable the service must know before it
    asks — `contracts/providers.md`'s own point that `search_players` never raises, so a `degraded`
    signal read off an exception cannot exist. `provider.queries == []` is the structural proof:
    the source is never called at all while `is_degraded()` says it is down. What the fallback
    itself returns is T316's own three tests below, not this one's."""
    from aoe2stats_api.search import search_players

    await _seed_profile(db_session, profile_id=9001, alias="Anything", country="FR")
    provider = _FakeSearchProvider(page=_FakeSearchPage(results=[]), degraded=True)

    outcome = await search_players(
        db_session, provider, "Anything", limit=10, ttl_seconds=_TTL_SECONDS, now=_NOW
    )

    assert provider.queries == []
    assert outcome.degraded is True
    assert outcome.reason == _SEARCH_SOURCE_UNAVAILABLE_REASON


async def test_a_write_past_the_ttl_removes_stale_rows(db_session: AsyncSession) -> None:
    """data-model.md's `profile_search_cache`: "entries older than the configured TTL are deleted
    opportunistically on write" — the same discipline `rate_limit_counters` uses, and for the same
    reason (FR-044 forbids a job on a timer). Seeded directly rather than through the service, so
    this test proves the *pruning*, not the seeding path; the write that triggers it is an
    unrelated query, per this task's own instruction."""
    from aoe2stats_api.search import search_players

    stale_query = "stale query"
    db_session.add(
        ProfileSearchCache(
            query_normalised=stale_query,
            results=[],
            fetched_at=_NOW - timedelta(seconds=_TTL_SECONDS + 1),
            source="companion",
        )
    )
    await db_session.flush()
    assert await _cache_row_count(db_session) == 1

    provider = _FakeSearchProvider(
        page=_FakeSearchPage(results=[_FakeSearchResult(4242, "Fresh", "DE", 1, None)])
    )
    await search_players(
        db_session, provider, "brand new query", limit=10, ttl_seconds=_TTL_SECONDS, now=_NOW
    )

    remaining = (
        (await db_session.execute(select(ProfileSearchCache.query_normalised))).scalars().all()
    )
    assert stale_query not in remaining
    assert "brand new query" in remaining
    assert await _cache_row_count(db_session) == 1


# --- T316: the local fallback ------------------------------------------------------------------


async def test_fallback_searches_aoe_profiles_and_reports_degraded(
    db_session: AsyncSession,
) -> None:
    """FR-004d: with the source unavailable, the fallback searches `aoe_profiles` — already
    populated by 001's discovery, per data-model.md — case-insensitively and on a substring
    (FR-004a, reused here), and the response still carries results, not an empty page: FR-004d's
    "this fallback still returns results" is what `degraded: true` exists to qualify rather than
    replace."""
    from aoe2stats_api.search import search_players

    await _seed_profile(db_session, profile_id=1001, alias="IronWarrior")
    await _seed_profile(db_session, profile_id=1002, alias="warriorKing")
    await _seed_profile(db_session, profile_id=1003, alias="Peaceful")

    provider = _FakeSearchProvider(page=_FakeSearchPage(results=[]), degraded=True)
    outcome = await search_players(
        db_session, provider, "WaRRior", limit=10, ttl_seconds=_TTL_SECONDS, now=_NOW
    )

    assert outcome.degraded is True
    assert outcome.reason == _SEARCH_SOURCE_UNAVAILABLE_REASON
    assert {r.profile_id for r in outcome.results} == {1001, 1002}


async def test_fallback_orders_most_played_first(db_session: AsyncSession) -> None:
    """FR-004a, reused by the fallback deliberately (data-model.md, `contracts/http-api.md`:
    "the local fallback reproduces deliberately so the two answers are ordered the same way") —
    ordered by how many matches this service has already recorded for each profile
    (`match_players`), most first, never by insertion order or alias."""
    from aoe2stats_api.search import search_players

    await _seed_profile(db_session, profile_id=2001, alias="Zorro")
    await _seed_profile(db_session, profile_id=2002, alias="Zorroz")
    await _seed_profile(db_session, profile_id=2003, alias="Zorrofan")
    await _seed_matches_played(db_session, profile_id=2001, count=3, starting_game_id=500_000)
    await _seed_matches_played(db_session, profile_id=2002, count=1, starting_game_id=500_100)
    # 2003 plays none at all.

    provider = _FakeSearchProvider(page=_FakeSearchPage(results=[]), degraded=True)
    outcome = await search_players(
        db_session, provider, "zorro", limit=10, ttl_seconds=_TTL_SECONDS, now=_NOW
    )

    assert [r.profile_id for r in outcome.results] == [2001, 2002, 2003]


async def test_fallback_withholds_no_profile_on_privacy_grounds(db_session: AsyncSession) -> None:
    """T301a retired FR-004c: the source's `hidden` field carries nothing, so there is no signal
    to withhold a profile on, and `aoe_profiles` itself carries no column that could stand in for
    one (data-model.md's `aoe_profiles` section: "There is no `hidden_observed_at`, and that is a
    decision"). Every locally-known profile matching the query comes back, with nothing filtered
    for a reason this system has no way to evaluate."""
    from aoe2stats_api.search import search_players

    matching_profile_ids = {3001, 3002, 3003, 3004}
    for profile_id in matching_profile_ids:
        await _seed_profile(db_session, profile_id=profile_id, alias=f"The{profile_id}")
    await _seed_profile(db_session, profile_id=3999, alias="Unrelated")

    provider = _FakeSearchProvider(page=_FakeSearchPage(results=[]), degraded=True)
    outcome = await search_players(
        db_session, provider, "the", limit=10, ttl_seconds=_TTL_SECONDS, now=_NOW
    )

    assert {r.profile_id for r in outcome.results} == matching_profile_ids


# --- BL-2 remediation: a sub-threshold failure is not `is_degraded()`, but must still degrade -----


async def test_a_call_that_fails_without_tripping_the_breaker_still_degrades(
    db_session: AsyncSession,
) -> None:
    """Round-2 review, BL-2: `is_degraded() == False` both before and after a call is exactly what
    the first `_FAILURE_THRESHOLD - 1` failures of every real outage look like
    (`companion/provider.py`) — reproduced by execution against the pre-remediation code (round-2
    report): the first two failing calls were cached as a confident `source="companion"` answer and
    served back as "no such player" for the rest of the TTL. `last_call_failed=True,
    degraded=False` models exactly that shape: the provider's call did not succeed, but the breaker
    has not opened. `search_players` must still route this to the fallback outcome, not to the
    live-cache write path."""
    from aoe2stats_api.search import search_players

    await _seed_profile(db_session, profile_id=9101, alias="FallbackWhileFailing", country="FR")
    provider = _FakeSearchProvider(
        page=_FakeSearchPage(results=[]), degraded=False, last_call_failed=True
    )

    outcome = await search_players(
        db_session, provider, "FallbackWhileFailing", limit=10, ttl_seconds=_TTL_SECONDS, now=_NOW
    )

    assert provider.queries == ["FallbackWhileFailing"], "the call must still have been made"
    assert outcome.degraded is True, (
        "a call that failed without tripping the breaker must still degrade — `is_degraded()` "
        "alone would have read `False` here and cached this as a confident answer"
    )
    assert outcome.reason == _SEARCH_SOURCE_UNAVAILABLE_REASON
    assert {r.profile_id for r in outcome.results} == {9101}, (
        "FR-004d: a degraded search still answers from what this service has already observed"
    )

    row = await db_session.get(ProfileSearchCache, "fallbackwhilefailing")
    assert row is not None
    assert row.source != "companion", (
        "the cache row this leaves behind must never carry the live source's own name — a repeat "
        "of this query within `ttl_seconds` would otherwise be served back as a confident answer"
    )


# --- BL-3 re-take: a fallback answer is now cached, under a short, self-healing TTL --------------


async def test_a_repeated_degraded_query_hits_the_short_lived_fallback_cache(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BL-3 re-take of round 1's M1 decision (`search.py`'s module docstring): a fallback answer is
    now cached under a short TTL specifically so a burst of repeat queries against a down source
    recomputes `_local_fallback_results` — the unfiltered `match_players` aggregate the round-2
    review measured as expensive — once per window, not once per request."""
    import aoe2stats_api.search as search_module

    await _seed_profile(db_session, profile_id=9201, alias="BurstQuery", country="FR")

    call_count = 0
    original = search_module._local_fallback_results

    async def counting_fallback(
        session: AsyncSession, query_normalised: str, *, limit: int
    ) -> Sequence[object]:
        nonlocal call_count
        call_count += 1
        return await original(session, query_normalised, limit=limit)

    monkeypatch.setattr(search_module, "_local_fallback_results", counting_fallback)

    provider = _FakeSearchProvider(page=_FakeSearchPage(results=[]), degraded=True)
    first = await search_module.search_players(
        db_session, provider, "BurstQuery", limit=10, ttl_seconds=_TTL_SECONDS, now=_NOW
    )
    second = await search_module.search_players(
        db_session,
        provider,
        "BurstQuery",
        limit=10,
        ttl_seconds=_TTL_SECONDS,
        now=_NOW + timedelta(seconds=5),
    )

    assert call_count == 1, "the second, repeated query within the fallback TTL must hit the cache"
    assert first.degraded is True
    assert second.degraded is True
    assert {r.profile_id for r in second.results} == {9201}


async def test_a_stale_fallback_row_is_not_served_once_the_source_recovers(
    db_session: AsyncSession,
) -> None:
    """The short TTL is what keeps a cached fallback answer from outliving the outage it was
    written during: once `_FALLBACK_CACHE_TTL_SECONDS` has passed, a call against a *recovered*
    provider must reach that provider again rather than being served the stale row — the risk
    round 1 was right to worry about at the long TTL, bounded here to a much shorter window."""
    from aoe2stats_api.search import _FALLBACK_CACHE_TTL_SECONDS, search_players

    await _seed_profile(db_session, profile_id=9301, alias="Recovering", country="FR")

    down_provider = _FakeSearchProvider(page=_FakeSearchPage(results=[]), degraded=True)
    first = await search_players(
        db_session, down_provider, "Recovering", limit=10, ttl_seconds=_TTL_SECONDS, now=_NOW
    )
    assert first.degraded is True

    recovered_page = _FakeSearchPage(results=[_FakeSearchResult(9301, "Recovering", "FR", 5, None)])
    recovered_provider = _FakeSearchProvider(page=recovered_page, degraded=False)
    second = await search_players(
        db_session,
        recovered_provider,
        "Recovering",
        limit=10,
        ttl_seconds=_TTL_SECONDS,
        now=_NOW + timedelta(seconds=_FALLBACK_CACHE_TTL_SECONDS + 1),
    )

    assert recovered_provider.queries == ["Recovering"], (
        "past the short fallback TTL, the stale row must not answer this query — the provider "
        "must be reached again"
    )
    assert second.degraded is False
