"""T317: route tests for `apps/api/src/aoe2stats_api/routers/players.py` (T319 — registered in
`app.py`). Encodes `quickstart.md` scenarios 1 and 4; `contracts/http-api.md`'s "Players" and
"Response headers on every route above" sections are ground truth for every shape asserted below.

**Scope, relative to the sibling files in this same parallel batch.** T314
(`test_player_search.py`) owns proving `apps/api/src/aoe2stats_api/search.py` (T315/T316) itself —
query normalisation, the cache write path, the breaker-derived degraded signal, the `aoe_profiles`
fallback and its ordering. This file owns the **route**: what `GET /api/players/search` answers,
not how `search.py` arrives at it. The two are deliberately non-overlapping rather than
double-testing the same mechanism from two angles.

**Why "found" / "found nothing" / "degraded" are exercised through `profile_search_cache` and
never through a mocked provider.** `routers/auth.py` — the one router in this codebase that
already talks to an external provider — builds it as a private, per-request factory
(`_build_relic_provider(db_session)`) closed over a module-level `httpx.AsyncClient` singleton,
never through a FastAPI `Depends()` this test could override with `app.dependency_overrides`
(`deps.py`'s own docstring reserves that pattern for storage-layer resources: the engine, the
session factory, the object store). `players.py` calling `search.py`, which in turn builds
`CompanionEnrichmentProvider` the same private way, is the only architecture consistent with that
precedent — so there is no seam this file could reach into from outside `search.py` to force a
live call to fail, and reaching for one would mean guessing a private name `search.py` (T315,
a sibling task working concurrently and unseen by this one) has not written yet.

`profile_search_cache` (`data-model.md`) is not that problem: its schema is fully specified ground
truth, independent of how `search.py` reaches it. Seeding a row directly is *not* a proxy for "the
provider was mocked" — it *is* the FR-004e cache-hit path a request takes for real once one exists,
so this is a genuine route exercise, not a workaround. Two things are this file's own design
decision, made here because nothing upstream of it pins them down, and documented so T315/T319
land on the same page rather than rediscovering the question:

1. **A fresh `profile_search_cache` row is served as `degraded: false`** when its `source` column
   reads `"companion"` (the live source's own name, `contracts/providers.md`), and as
   `degraded: true`, `reason: "search_source_unavailable"` (`contracts/http-api.md`'s outcome
   table) for any other `source` value. `test_search_...cache_hit` below writes `"aoe_profiles"`
   for the degraded case — `data-model.md`'s own words for what FR-004d's fallback searches — so a
   route built to read `source` this way needs no further mapping to make this pass.
2. **`results` in the cache row is exactly `PlayerSearchResult`'s five fields** (`contracts/
   providers.md`: `profile_id`, `alias`, `country`, `games_played`, `clan`), never a raw provider
   body — `data-model.md`'s own "not a verbatim copy" sentence — so every seeded row below carries
   only those five keys, and a route that echoes a cache row's `results` list back verbatim already
   satisfies FR-004b for the cache-hit path with no filtering of its own.

If `search.py` lands with a different `source` vocabulary, only the two `source=` string literals
below need to change — the response envelope (`results`/`degraded`/`reason`) and the rest of this
file are unaffected.

**The `X-Robots-Tag` assertions were not blocked on `players.py` existing, and still are not.**
`app.py`'s `_NoIndexHeaderMiddleware` (T309) matches on `request.url.path` against
`^/api/players(/.*)?$` *before* Starlette resolves a route, specifically so the header was already
true of the 404 a crawler got before this router existed, and remains true of every response —
`200`, `404`, `429` — now that it does. Asserted on every response anyway, per this task's own
text.

**"404 for a hidden one and for an unknown one" (T317's task text) collapses to one case here.**
FR-004c — the source-side hidden signal — was retired before implementation (T301a,
`docs/data-sources.md` §3), and `contracts/http-api.md` says so explicitly: "No profile is withheld
on privacy grounds, from `search` or from `GET /api/players/{profile_id}`... What keeps a third
party's page from being a public listing is FR-010... not a per-profile flag." There is no
mechanism left in this feature that could make a profile answer differently from "never observed"
on privacy grounds, so `test_an_unobserved_players_profile_answers_404` below is the whole of that
sentence: one `404`, for a `profile_id` this service has no `aoe_profiles` row for at all.

**Harness conventions** follow `test_no_public_directory.py` (T310) and `test_rate_limits.py`
(T306) byte for byte where they overlap: `client`/`db_session`/`environment` from `conftest.py`,
the `_sign_in` cookie helper. Written test-first, with `xfail(strict=True)` on every test until
T319 registered the router; `strict=True` is what forced those markers off once it did, rather
than letting them linger and hide a later regression — every test below now runs unmarked.

**Remediation (B1): the breaker is shared, and this file proves it.** `_build_search_provider`
(`routers/players.py`) is a per-request factory that used to construct a brand-new circuit breaker
on every call, so `CompanionEnrichmentProvider.is_degraded()` could never observe an outage a
previous request had already recorded — `test_two_requests_through_the_real_provider_share_the_
circuit_breaker_state` below is the one test in this file that goes through that real factory
rather than a seeded cache row or a fake provider, specifically to catch that: no other test here
can, by the design note in the previous paragraph. It intercepts `httpx.AsyncClient.send` at the
same boundary `test_auth_flow.py` already uses for Steam/Relic, and resets the process-lifetime
breaker (`players._companion_breaker.cache_clear()`) both before and after itself, so a trip it
deliberately causes never leaks into an unrelated test in this file or any other.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api import security
from aoe2stats_api.routers import players
from aoe2stats_api.settings import get_settings
from aoe2stats_storage.models import AoeProfile, ProfileSearchCache, RatingSnapshot, User
from aoe2stats_storage.models import Session as UserSession

pytestmark = [pytest.mark.usefixtures("environment")]

#: See `test_replay_status.py`'s module docstring — this suite's working assumption, not yet fixed
#: by a contract document beyond T028's own implementation.
SESSION_COOKIE_NAME = "session_id"

# `contracts/providers.md`'s own name for the live source, and the value `test_search_...` below
# asserts a route must read as "not degraded" off a cached row's `source` column (module
# docstring, point 1).
_LIVE_SOURCE = "companion"
# `data-model.md`'s own words for what FR-004d's fallback searches — this file's chosen stand-in
# for "any value other than the live source" (module docstring, point 1).
_FALLBACK_SOURCE = "aoe_profiles"

_SEARCH_RESULT_PROFILE_ID = 900_900_100


def _search_result(
    *, profile_id: int, alias: str, country: str | None, games_played: int, clan: str | None
) -> dict[str, Any]:
    """`PlayerSearchResult`'s five contract fields (`contracts/providers.md`), exactly — nothing a
    verbatim provider body would additionally carry (`steamId`, `shared`, `sharedHistory`,
    FR-004b), matching what `data-model.md` says `profile_search_cache.results` holds."""
    return {
        "profile_id": profile_id,
        "alias": alias,
        "country": country,
        "games_played": games_played,
        "clan": clan,
    }


async def _seed_cache_entry(
    db_session: AsyncSession,
    *,
    query_normalised: str,
    results: list[dict[str, Any]],
    source: str,
    fetched_at: datetime | None = None,
) -> None:
    db_session.add(
        ProfileSearchCache(
            query_normalised=query_normalised,
            results=results,
            source=source,
            fetched_at=fetched_at if fetched_at is not None else datetime.now(UTC),
        )
    )
    await db_session.commit()


async def _seed_user(db_session: AsyncSession) -> User:
    """A bare, allowlisted, consenting `users` row — the routes below are about *viewing* any
    profile, never about the caller's own, so no `profile_links` row is needed to exercise them
    (contrast `test_no_public_directory.py`'s heavier `_seed_linked_caller`)."""
    now = datetime.now(UTC)
    user = User(allowlisted_at=now, ingest_consent_at=now)
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    return user


async def _seed_profile(
    db_session: AsyncSession,
    *,
    profile_id: int,
    alias: str,
    country: str | None = "FR",
    alias_observed_at: datetime | None = None,
) -> None:
    db_session.add(
        AoeProfile(
            profile_id=profile_id,
            alias=alias,
            country=country,
            alias_observed_at=alias_observed_at
            if alias_observed_at is not None
            else datetime.now(UTC),
        )
    )
    await db_session.commit()


async def _seed_rating_snapshot(
    db_session: AsyncSession,
    *,
    profile_id: int,
    leaderboard_id: int,
    rating: int,
    rank: int | None,
    wins: int | None,
    losses: int | None,
    captured_at: datetime,
) -> None:
    db_session.add(
        RatingSnapshot(
            profile_id=profile_id,
            leaderboard_id=leaderboard_id,
            captured_at=captured_at,
            rating=rating,
            rank=rank,
            wins=wins,
            losses=losses,
        )
    )
    await db_session.commit()


async def _sign_in(client: TestClient, db_session: AsyncSession, user: User) -> None:
    """Insert a `sessions` row directly and hand the client its signed cookie — mirrors
    `test_no_public_directory.py`'s and `test_replay_status.py`'s own `_sign_in` helper."""
    session_id = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    db_session.add(
        UserSession(
            id=session_id,
            user_id=user.id,
            created_at=now,
            expires_at=now + timedelta(days=30),
        )
    )
    await db_session.commit()
    secret = get_settings().app_secret_key.get_secret_value()
    client.cookies.set(SESSION_COOKIE_NAME, security._sign(session_id, secret))


def _assert_no_index(response: Any) -> None:
    """FR-010, asserted on every response this file checks (task text) — already true today via
    `app.py`'s path-pattern middleware regardless of whether `players.py` exists (module
    docstring), so this line alone never accounts for a test's `xfail`."""
    assert response.headers.get("x-robots-tag") == "noindex, nofollow"


# --- GET /api/players/search — FR-001, FR-002, FR-003, FR-004e, FR-005 -------------------------


async def test_search_finds_a_player_by_display_name_with_no_numeric_identifier(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-001, quickstart scenario 1.3: a display-name search, with no profile id known up front,
    reaches that player's result. Served from a fresh `profile_search_cache` row (module docstring)
    rather than a live call, and looked up case- and whitespace-insensitively (FR-004a) — the
    caller searches `"  CacheFound  "`, the cached key is the normalised `"cachefound"`."""
    caller = await _seed_user(db_session)
    await _sign_in(client, db_session, caller)

    result = _search_result(
        profile_id=_SEARCH_RESULT_PROFILE_ID,
        alias="CacheFoundAlias",
        country="DE",
        games_played=4200,
        clan="TAG",
    )
    await _seed_cache_entry(
        db_session, query_normalised="cachefound", results=[result], source=_LIVE_SOURCE
    )

    response = client.get("/api/players/search", params={"q": "  CacheFound  "})
    assert response.status_code == 200, (
        f"expected a match for a cached, normalised query. Got {response.status_code}: "
        f"{response.text}"
    )
    _assert_no_index(response)

    body = response.json()
    assert body["degraded"] is False
    result_ids = [entry["profile_id"] for entry in body["results"]]
    assert _SEARCH_RESULT_PROFILE_ID in result_ids, (
        "FR-002: enough must be returned to tell players apart — country and standing alongside "
        f"the name. Got {body!r}"
    )
    matched = next(
        entry for entry in body["results"] if entry["profile_id"] == result["profile_id"]
    )
    assert matched["alias"] == "CacheFoundAlias"
    assert matched["country"] == "DE"


async def test_search_distinguishes_found_nothing_from_search_unavailable(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-003, quickstart scenario 1.4: "this search found nothing" and "search is currently
    unavailable" must never collapse into the same answer. Both cached rows below carry an
    identical, empty `results: []` — the exact case the contract calls out ("a client that
    branches on `results.length` alone is wrong") — so the only thing that may distinguish them is
    the `degraded` field itself, never the list's length."""
    caller = await _seed_user(db_session)
    await _sign_in(client, db_session, caller)

    await _seed_cache_entry(db_session, query_normalised="nomatch", results=[], source=_LIVE_SOURCE)
    await _seed_cache_entry(
        db_session, query_normalised="downsource", results=[], source=_FALLBACK_SOURCE
    )

    found_nothing = client.get("/api/players/search", params={"q": "nomatch"})
    assert found_nothing.status_code == 200
    _assert_no_index(found_nothing)
    found_nothing_body = found_nothing.json()
    assert found_nothing_body["results"] == []
    assert found_nothing_body["degraded"] is False, (
        "a genuine zero-match query must never be reported as degraded"
    )

    unavailable = client.get("/api/players/search", params={"q": "downsource"})
    assert unavailable.status_code == 200, (
        "FR-004: search being unavailable must not itself fail the request. Got "
        f"{unavailable.status_code}: {unavailable.text}"
    )
    _assert_no_index(unavailable)
    unavailable_body = unavailable.json()
    assert unavailable_body["results"] == []
    assert unavailable_body["degraded"] is True, (
        "FR-003: the two empty-results responses above are identical but for this field — a "
        "client reading only `results.length` cannot tell them apart, and that is exactly the "
        "failure this assertion exists to catch"
    )
    assert unavailable_body["reason"] == "search_source_unavailable"

    assert found_nothing_body != unavailable_body, (
        "FR-003 in one line: the two outcomes must differ somewhere in the response body"
    )


async def test_search_unavailable_still_returns_locally_observed_results(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-004d: degraded search is not merely honestly labelled, it still answers from what this
    service has already observed — `degraded: true` with a non-empty `results` is the case
    `contracts/http-api.md` calls out by name ("the third case still returns results")."""
    caller = await _seed_user(db_session)
    await _sign_in(client, db_session, caller)

    locally_known = _search_result(
        profile_id=900_900_200,
        alias="LocallyObservedAlias",
        country="FR",
        games_played=12,
        clan=None,
    )
    await _seed_cache_entry(
        db_session,
        query_normalised="locallyobserved",
        results=[locally_known],
        source=_FALLBACK_SOURCE,
    )

    response = client.get("/api/players/search", params={"q": "locallyobserved"})
    assert response.status_code == 200
    _assert_no_index(response)
    body = response.json()
    assert body["degraded"] is True
    result_ids = [entry["profile_id"] for entry in body["results"]]
    assert 900_900_200 in result_ids


async def test_search_rate_limits_per_user_and_answers_retry_after(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-005, quickstart scenario 1.6: past the configured per-user limit
    (`PLAYER_SEARCH_MAX_PER_USER_PER_MINUTE`), the route answers `rate_limited` with a
    `retry_after` — never a generic failure — so a client can honestly tell the user when to try
    again. Every call resolves against the same cached, empty row so nothing here depends on the
    search outcome itself, only on the limiter."""
    caller = await _seed_user(db_session)
    await _sign_in(client, db_session, caller)
    await _seed_cache_entry(
        db_session, query_normalised="ratelimited", results=[], source=_LIVE_SOURCE
    )

    limit = get_settings().player_search_max_per_user_per_minute

    for attempt in range(limit):
        response = client.get("/api/players/search", params={"q": "ratelimited"})
        assert response.status_code == 200, (
            f"call {attempt + 1} of {limit} should still be within the limit. Got "
            f"{response.status_code}: {response.text}"
        )

    limited = client.get("/api/players/search", params={"q": "ratelimited"})
    assert limited.status_code == 429, (
        f"the call past the configured limit of {limit} must be refused. Got "
        f"{limited.status_code}: {limited.text}"
    )
    _assert_no_index(limited)
    limited_body = limited.json()
    assert limited_body["error"]["code"] == "rate_limited"
    assert isinstance(limited_body["error"]["detail"].get("retry_after"), int)
    assert limited_body["error"]["detail"]["retry_after"] > 0


# --- Remediation (B1): the breaker must outlive one request --------------------------------------


class _FailingCompanionUpstream:
    """Stands in for `data.aoe2companion.com`'s `/profiles` endpoint, reached at
    `httpx.AsyncClient.send` — the same boundary `test_auth_flow.py`'s `fake_upstream` intercepts
    for Steam and Relic. Every request answers `403` — companion's own "documented, expected
    bot-protection noise" (`companion/provider.py`'s module docstring) — never `500`, so
    `AsyncBaseProvider._request`'s retry loop never engages: each failing search costs exactly one
    outbound request, not up to three, which is what makes `request_count` a clean signal below.
    """

    def __init__(self) -> None:
        self.request_count = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.request_count += 1
        return httpx.Response(403, request=request)


async def test_two_requests_through_the_real_provider_share_the_circuit_breaker_state(
    client: TestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B1 remediation. `_build_search_provider` (`routers/players.py`) rebuilds a thin
    `CompanionEnrichmentProvider` on every request, but the circuit breaker inside it must not be
    rebuilt too — this is the one test in this file that reaches that real factory, rather than a
    seeded cache row (this file's other tests) or a fake provider (`test_player_search.py`),
    because that is the only path this defect could hide on: `is_degraded()` read off a *fresh*
    breaker every request is always `False`, so FR-004d's fallback branch would be unreachable in
    production even while every other test in this codebase kept passing.

    Three distinct queries, each answered `403` by `_FailingCompanionUpstream` below, drive the
    shared breaker's consecutive-failure count to `_FAILURE_THRESHOLD` (3,
    `companion/provider.py`) across three *separate* requests. A fourth, distinct query must then
    be answered from the local `aoe_profiles` fallback — `degraded: true` — without ever reaching
    the transport a fourth time: a provider rebuilt with its own fresh, always-closed breaker every
    request would show `degraded: false` here instead, and a fourth outbound call.
    """
    fake = _FailingCompanionUpstream()

    async def fake_send(
        self: httpx.AsyncClient, request: httpx.Request, **kwargs: object
    ) -> httpx.Response:
        if request.url.host != "data.aoe2companion.com":
            raise AssertionError(f"unexpected outbound request to {request.url}")
        return fake(request)

    monkeypatch.setattr(httpx.AsyncClient, "send", fake_send)
    # The breaker is process-lifetime (`players._companion_breaker`, `functools.lru_cache`d): a
    # trip from an earlier test run in this same process must not leak in here, and this test's
    # own trip must not leak into whatever runs after it.
    players._companion_breaker.cache_clear()
    try:
        caller = await _seed_user(db_session)
        await _sign_in(client, db_session, caller)
        await _seed_profile(db_session, profile_id=900_900_150, alias="OutageDeltaAlias")

        for query in ("outagealpha", "outagebeta", "outagegamma"):
            response = client.get("/api/players/search", params={"q": query})
            assert response.status_code == 200, (
                f"a failing source must not itself fail the request. Got "
                f"{response.status_code}: {response.text}"
            )
            body = response.json()
            # BL-2 remediation. `_FAILURE_THRESHOLD` is 3 (`companion/provider.py`), so the first
            # two of these three requests do not themselves trip the breaker —
            # `is_degraded()` reads `False` both before *and* after each of them. Before this
            # remediation, the route read `is_degraded()` alone after the call and cached each of
            # these as a confident `source="companion"` answer: the exact failure mode this test
            # now proves closed, not merely "the request itself did not 500".
            assert body["degraded"] is True, (
                f"query {query!r} (one of the first two failures of this outage, below "
                "`_FAILURE_THRESHOLD`) must still be reported as degraded — `is_degraded()` "
                "alone stays `False` here, and only `last_call_failed()` can see this call's own "
                f"outcome. Got degraded={body['degraded']!r}, results={body['results']!r}"
            )
            assert body["reason"] == "search_source_unavailable"

            cache_row = await db_session.get(ProfileSearchCache, query)
            assert cache_row is not None, (
                f"a search response must still leave a cache row for {query!r}"
            )
            assert cache_row.source != _LIVE_SOURCE, (
                f"a failed call for {query!r} must never be cached under the live source's own "
                "name — a repeat of this same query within the TTL would otherwise be served "
                "back as a confident 'no such player' for the rest of the outage and beyond"
            )

        assert fake.request_count == 3, (
            "each of the three distinct queries above must have reached the transport exactly "
            f"once. Got {fake.request_count}"
        )

        fourth = client.get("/api/players/search", params={"q": "outagedelta"})
        assert fourth.status_code == 200
        _assert_no_index(fourth)
        fourth_body = fourth.json()
        assert fourth_body["degraded"] is True, (
            "the breaker tripped by the three requests above must still be open on this fourth, "
            "separate request — the whole defect B1 exists to catch"
        )
        assert fourth_body["reason"] == "search_source_unavailable"
        result_ids = [entry["profile_id"] for entry in fourth_body["results"]]
        assert 900_900_150 in result_ids, (
            "FR-004d: a degraded search still answers from what this service has already observed"
        )

        assert fake.request_count == 3, (
            "the fourth, degraded request must never reach the transport a fourth time — a "
            "provider rebuilt with its own fresh breaker every request would reach it again here"
        )
    finally:
        players._companion_breaker.cache_clear()


# --- GET /api/players/{profile_id} — FR-006, FR-008, FR-008a property 1 -------------------------


async def test_any_players_profile_returns_rating_rank_wins_and_losses_per_ladder(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-006, quickstart scenario 4.1: a third party's profile — never the caller's own, no
    `profile_links` row anywhere in this test — answers with its current standing on every ladder
    it has played, the same shape `GET /api/profiles` already carries for the caller's own
    (FR-008), plus `alias_observed_at` (`contracts/http-api.md`)."""
    caller = await _seed_user(db_session)
    await _sign_in(client, db_session, caller)

    profile_id = 900_900_300
    observed_at = datetime(2026, 8, 20, tzinfo=UTC)
    await _seed_profile(
        db_session,
        profile_id=profile_id,
        alias="ThirdPartyAlias",
        country="BE",
        alias_observed_at=observed_at,
    )
    now = datetime.now(UTC)
    await _seed_rating_snapshot(
        db_session,
        profile_id=profile_id,
        leaderboard_id=3,
        rating=1850,
        rank=120,
        wins=300,
        losses=250,
        captured_at=now,
    )
    await _seed_rating_snapshot(
        db_session,
        profile_id=profile_id,
        leaderboard_id=4,
        rating=1700,
        rank=None,
        wins=10,
        losses=8,
        captured_at=now,
    )

    response = client.get(f"/api/players/{profile_id}")
    assert response.status_code == 200, (
        f"any signed-in caller must be able to open a third party's profile (FR-008a). Got "
        f"{response.status_code}: {response.text}"
    )
    _assert_no_index(response)

    body = response.json()
    assert body["profile_id"] == profile_id
    assert body["alias"] == "ThirdPartyAlias"
    assert body["country"] == "BE"
    assert body["alias_observed_at"] is not None

    ratings_by_leaderboard = {entry["leaderboard_id"]: entry for entry in body["ratings"]}
    assert set(ratings_by_leaderboard) == {3, 4}
    assert ratings_by_leaderboard[3]["rating"] == 1850
    assert ratings_by_leaderboard[3]["rank"] == 120
    assert ratings_by_leaderboard[3]["wins"] == 300
    assert ratings_by_leaderboard[3]["losses"] == 250
    assert ratings_by_leaderboard[4]["rating"] == 1700


async def test_a_never_ranked_players_profile_answers_200_with_empty_ladder_data(
    client: TestClient, db_session: AsyncSession
) -> None:
    """US1 acceptance scenario 5, quickstart scenario 4.3: a player this service has observed but
    who has never played a ranked ladder is a valid, explained profile — `200`, empty ladder data —
    never an error and never a blank page. `contracts/http-api.md` is explicit this is not `404`."""
    caller = await _seed_user(db_session)
    await _sign_in(client, db_session, caller)

    profile_id = 900_900_400
    await _seed_profile(db_session, profile_id=profile_id, alias="NeverRankedAlias", country=None)

    response = client.get(f"/api/players/{profile_id}")
    assert response.status_code == 200, (
        f"a never-ranked profile must still be a valid page, not an error. Got "
        f"{response.status_code}: {response.text}"
    )
    _assert_no_index(response)
    body = response.json()
    assert body["profile_id"] == profile_id
    assert body["alias"] == "NeverRankedAlias"
    assert body["ratings"] == []


async def test_an_unobserved_players_profile_answers_404(
    client: TestClient, db_session: AsyncSession
) -> None:
    """The one `404` this route has left after FR-004c's retirement (module docstring): a
    `profile_id` this service has never itself observed — no `aoe_profiles` row — and the source
    does not know it either (`contracts/http-api.md`).

    **Positive control kept deliberately.** Starlette's own unmatched-route 404 goes through
    `app.py`'s generic `HTTPException` handler, which happens to render the identical `{"error":
    {"code": "not_found", ...}}` body a genuine "profile never observed" answer would — so the bare
    negative assertion below, on its own, would be indistinguishable from an accidental pass on a
    route that does not exist at all, exactly the collision `test_no_public_directory.py`'s own
    module docstring warns against. The positive control (a seeded, observed profile answering
    `200`) is what proves this router is actually the one answering.
    """
    caller = await _seed_user(db_session)
    await _sign_in(client, db_session, caller)

    observed_profile_id = 900_900_999
    await _seed_profile(db_session, profile_id=observed_profile_id, alias="ObservedAlias")

    observed_response = client.get(f"/api/players/{observed_profile_id}")
    assert observed_response.status_code == 200, (
        "positive control: a profile this service has observed must actually come back. Got "
        f"{observed_response.status_code}: {observed_response.text}"
    )
    _assert_no_index(observed_response)

    unobserved_response = client.get("/api/players/900901999")
    assert unobserved_response.status_code == 404
    _assert_no_index(unobserved_response)
    assert unobserved_response.json()["error"]["code"] == "not_found"


# --- GET /api/players/{profile_id}/ratings — FR-006, FR-008a property 1 -------------------------


async def test_players_ratings_history_returns_snapshots_where_they_exist(
    client: TestClient, db_session: AsyncSession
) -> None:
    """`contracts/http-api.md`: "Rating history, where snapshots exist." Two observations across
    two days for one ladder — oldest first, the order `GET /api/profiles/{profile_id}/ratings`
    already answers in for the caller's own curve (`routers/profiles.py`), generalised here to any
    profile (FR-008)."""
    caller = await _seed_user(db_session)
    await _sign_in(client, db_session, caller)

    profile_id = 900_900_500
    await _seed_profile(db_session, profile_id=profile_id, alias="CurveAlias")

    earlier = datetime(2026, 8, 1, tzinfo=UTC)
    later = datetime(2026, 8, 2, tzinfo=UTC)
    await _seed_rating_snapshot(
        db_session,
        profile_id=profile_id,
        leaderboard_id=3,
        rating=1500,
        rank=900,
        wins=50,
        losses=45,
        captured_at=earlier,
    )
    await _seed_rating_snapshot(
        db_session,
        profile_id=profile_id,
        leaderboard_id=3,
        rating=1550,
        rank=850,
        wins=53,
        losses=45,
        captured_at=later,
    )

    response = client.get(f"/api/players/{profile_id}/ratings")
    assert response.status_code == 200
    _assert_no_index(response)
    ratings = response.json()["ratings"]
    assert [entry["rating"] for entry in ratings] == [1500, 1550], (
        "oldest first, matching routers/profiles.py's own ordering for the identical shape"
    )


async def test_players_ratings_history_is_empty_for_a_profile_with_no_snapshots(
    client: TestClient, db_session: AsyncSession
) -> None:
    """A profile this service knows about but has never captured a rating snapshot for gets an
    empty curve, not an error — the same "real and observed, history simply not there yet"
    discipline `routers/profiles.py`'s own `/ratings` route already applies to the caller's own,
    generalised here to any profile."""
    caller = await _seed_user(db_session)
    await _sign_in(client, db_session, caller)

    profile_id = 900_900_600
    await _seed_profile(db_session, profile_id=profile_id, alias="NoCurveAlias")

    response = client.get(f"/api/players/{profile_id}/ratings")
    assert response.status_code == 200
    _assert_no_index(response)
    assert response.json()["ratings"] == []
