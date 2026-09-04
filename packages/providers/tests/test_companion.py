"""Contract test for `EnrichmentProvider` (T041) — the aoe2companion enrichment adapter.

Ground truth is `specs/001-steam-link-replay-ingestion/contracts/providers.md`'s
`EnrichmentProvider` section and `docs/data-sources.md` §3. Every request in this file goes through
`httpx.MockTransport` — constitution III forbids the network in unit tests, and
`tests/conftest.py` blocks any real socket connection under `PYTEST_DISABLE_NETWORK=1` regardless.

Written as a test-first task, before `aoe2stats_providers.companion.provider` exists (T051): every
test below carries `@pytest.mark.xfail(strict=True, ...)`. `strict=True` is what makes that honest —
the moment T051 lands and a test starts passing, `strict=True` turns the *run* red instead of
letting a stale xfail hide it. The import of the not-yet-existent module lives inside `_provider()`,
the one place every test below reaches it through, rather than at module scope: a module-scope
`ModuleNotFoundError` aborts the *entire* workspace suite's collection (`pytest -q` stops on any
collection error, workspace-wide, per `testpaths` in the root `pyproject.toml`), while the same
error raised inside a test body is exactly what `strict=True` xfail is built to expect.

`EnrichmentProvider` is "the only provider whose failure is not an error" (providers.md): `403` here
is documented, observed, expected noise (`docs/data-sources.md` §3, "Observed 2026-08-19:
intermittent 403"), and the circuit breaker exists for exactly that. Five behaviours are exercised:

1. A genuine 200 parses into `MatchEnrichment` entries keyed by `game_id` — the baseline that
   every failure test below is a *contrast* against, not a test of a provider that never worked.
2. A single 403 is expected noise: `enrich_matches` does not raise, and does not classify it as
   `ProviderRateLimited` the way every other provider's `_request` default would (see
   `test_provider_base.py::test_403_can_be_opted_out_of_rate_limit_classification`, which exists
   for this provider).
3. Repeated failures open the circuit breaker: past some point, further calls stop reaching the
   mock transport at all, rather than reissuing a request (and its retry budget) on every single
   call forever.
4. Any failure — not only a 403 — leaves the caller with nothing rather than an exception, so "the
   application must render correctly with this provider returning nothing" (providers.md) holds
   for a full outage (5xx exhausting retries) too, not only the documented 403 case.
5. `linkedProfiles` is never read (FR-045) — enforced here at the letter, not by inference: the
   fixture body handed to the provider is wrapped so that any `__getitem__`, `.get` or `in` check
   against the key `linkedProfiles` fails the test immediately, from wherever in the provider that
   access happens to occur.

T312 (below `# === T312 ===`) adds `search_players` (T313, not yet implemented): quickstart
scenario 2, "nothing about a search result leaks an account link". See that section's own
docstring for what it covers.
"""

from __future__ import annotations

import copy
import dataclasses
import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import pytest

from aoe2stats_providers.base import MatchEnrichment, ProviderCallRecord, RetryPolicy, TokenBucket

if TYPE_CHECKING:
    # Type-checking only: mypy needs the name, but nothing here may import the module at
    # collection time — see `_provider()` below, where the real (runtime) import lives.
    from aoe2stats_providers.companion.provider import CircuitBreaker, CompanionEnrichmentProvider

# Every test in this file is expected to fail for exactly one reason — T051 does not exist yet —
# until it does. `strict=True` is what makes that honest: the moment T051 lands and a test starts
# passing, `strict=True` turns the *run* red instead of letting a stale xfail hide it, which is the
# whole point of marking these tests failing rather than skipping them. Do not drop `strict=True`.
XFAIL_REASON = "CompanionEnrichmentProvider is implemented by T051, not this test-first task (T041)"

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "companion"

# The three real `matchId` values `fixtures/companion/matches.json` carries (`fixtures/README.md`:
# "capped to 3 real matches" — fewer entries than the live response, not different ones).
FIXTURE_GAME_IDS = (500615037, 500572650, 500564671)

# T409: `enrich_matches` now requires `profile_ids` (the source's own required query parameter,
# `companion/provider.py`'s "The endpoint" note) — TheViper (196240) and Somero (264353) are two
# real profiles the fixture's own three matches all carry, the pair whose recent matches a real
# `?profile_ids=196240,264353` request would have returned.
FIXTURE_PROFILE_IDS = (196240, 264353)

# Fast enough that the retry-exhaustion test does not spend real seconds asleep, while still
# exercising the same backoff machinery every other provider's tests use (test_provider_base.py).
FAST_RETRY = RetryPolicy(
    max_attempts=3, base_delay_seconds=0.001, max_delay_seconds=0.002, jitter_seconds=0.0
)


def _load_matches_fixture() -> dict[str, Any]:
    return json.loads((FIXTURES / "matches.json").read_text(encoding="utf-8"))


class _Recorder:
    """An `AsyncProviderCallSink` double that just remembers `provider_calls` rows."""

    def __init__(self) -> None:
        self.calls: list[ProviderCallRecord] = []

    async def async_sink(self, record: ProviderCallRecord) -> None:
        self.calls.append(record)


class _NoLinkedProfilesGuard(dict):  # type: ignore[type-arg]
    """A `dict` that fails the test the instant anything reads `linkedProfiles` from it — the
    literal enforcement of FR-045's "not to be consumed", wherever inside the provider the read
    would happen. Every nested object the parsed response carries is wrapped the same way (see
    `_guarded_object_hook`), so a read buried inside a player entry is caught exactly as readily
    as one at the top level.
    """

    def __getitem__(self, key: Any) -> Any:
        if key == "linkedProfiles":
            raise AssertionError("EnrichmentProvider must never read `linkedProfiles` (FR-045)")
        return super().__getitem__(key)

    def get(self, key: Any, default: Any = None) -> Any:
        if key == "linkedProfiles":
            raise AssertionError("EnrichmentProvider must never read `linkedProfiles` (FR-045)")
        return super().get(key, default)

    def __contains__(self, key: object) -> bool:
        if key == "linkedProfiles":
            raise AssertionError("EnrichmentProvider must never read `linkedProfiles` (FR-045)")
        return super().__contains__(key)


def _guarded_object_hook(obj: dict[str, Any]) -> dict[str, Any]:
    return _NoLinkedProfilesGuard(obj)


def _provider(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    recorder: _Recorder | None = None,
    rate_per_second: float = 1000.0,
    retry_policy: RetryPolicy = FAST_RETRY,
    breaker: CircuitBreaker | None = None,
) -> tuple[CompanionEnrichmentProvider, _Recorder]:
    """Imports `CompanionEnrichmentProvider` here, at call time, rather than at module scope: this
    is the one place every test below reaches the not-yet-existent T051 module through, so this is
    where the resulting `ModuleNotFoundError` is meant to surface — inside the test call, where
    `strict=True` xfail turns it into an expected failure, not during collection, where it would
    abort the whole workspace suite.

    `breaker` is `None` by default, which builds this test's own fresh, independent
    `CircuitBreaker` — MJ-3 remediation made the constructor's own `breaker` parameter required,
    so every call through here must supply one, but each test in this file still wants its own,
    isolated breaker unless it explicitly asks to share one across two `_provider()` calls (as
    `test_search_players_shares_the_circuit_breaker_with_enrich_matches` does on a single provider
    instance already, needing no second `_provider()` call at all).
    """
    from aoe2stats_providers.companion.provider import (
        CompanionEnrichmentProvider,
        build_circuit_breaker,
    )

    recorder = recorder or _Recorder()
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = CompanionEnrichmentProvider(
        client=client,
        timeout_seconds=5.0,
        rate_limiter=TokenBucket(rate_per_second),
        call_sink=recorder.async_sink,
        retry_policy=retry_policy,
        breaker=breaker if breaker is not None else build_circuit_breaker(),
    )
    return provider, recorder


# --- Baseline: a genuine 200 parses, so the failure tests below are a real contrast --------------


async def test_enrich_matches_parses_a_genuine_response_keyed_by_game_id() -> None:
    body = _load_matches_fixture()
    provider, recorder = _provider(lambda request: httpx.Response(200, json=body))

    result = await provider.enrich_matches(FIXTURE_PROFILE_IDS, list(FIXTURE_GAME_IDS))

    assert set(result) == set(FIXTURE_GAME_IDS)
    for game_id, enrichment in result.items():
        assert isinstance(enrichment, MatchEnrichment)
        assert enrichment.game_id == game_id
    assert len(recorder.calls) >= 1
    assert all(not call.rate_limited for call in recorder.calls)


# --- T409: the outbound request carries the source's own required parameter, `profile_ids`,
# never the `matchIds` this provider used to send (a request the live API rejects outright with
# `{"error":"profile_ids must be specified"}`, verified against production match 474746656 on
# 2026-09-04) -----------------------------------------------------------------------------------


async def test_enrich_matches_requests_profile_ids_never_match_ids() -> None:
    """The defect itself (T409): `enrich_matches` used to build its request from `?matchIds=`, a
    parameter the live endpoint rejects — every production call therefore always came back
    non-200, and `match_players.color_id` was never once written. The fix queries
    `?profile_ids=a,b` instead, the one shape `docs/data-sources.md` §3 documents.
    """
    body = _load_matches_fixture()
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=body)

    provider, _ = _provider(handler)

    result = await provider.enrich_matches(FIXTURE_PROFILE_IDS, list(FIXTURE_GAME_IDS))

    assert set(result) == set(FIXTURE_GAME_IDS)
    assert len(captured) >= 1
    request = captured[0]
    assert "matchIds" not in request.url.params, (
        "the live endpoint rejects a `matchIds`-only request outright — this parameter must never "
        "be sent again"
    )
    sent_profile_ids = request.url.params.get("profile_ids")
    assert sent_profile_ids is not None, (
        "the source's own required query parameter (`docs/data-sources.md` §3) must be present"
    )
    assert set(sent_profile_ids.split(",")) == {str(pid) for pid in FIXTURE_PROFILE_IDS}


# --- A 403 is expected noise: never raised, never classified as rate limiting --------------------


async def test_a_403_is_expected_noise_and_does_not_raise() -> None:
    """`docs/data-sources.md` §3: "Treat a 403 here as normal operating noise." Unlike every other
    provider (`test_provider_base.py::test_unexpected_403_is_treated_as_rate_limited_by_default`),
    this one must not turn a 403 into `ProviderRateLimited` — it is not throttling, it is
    intermittent bot protection this application is designed to survive without.
    """
    recorder = _Recorder()
    provider, _ = _provider(lambda request: httpx.Response(403), recorder=recorder)

    # No `pytest.raises` here on purpose: an exception of any kind fails this test outright,
    # which is the point — a 403 must never propagate past `enrich_matches`.
    result = await provider.enrich_matches(FIXTURE_PROFILE_IDS, list(FIXTURE_GAME_IDS))

    assert result == {}
    assert len(recorder.calls) >= 1
    assert recorder.calls[0].status_code == 403
    assert not recorder.calls[0].rate_limited, (
        "a 403 here is normal operating noise, not rate limiting — the caller must not have "
        "classified it the way `base.py`'s default (`treat_403_as_rate_limited=True`) would"
    )


# --- Repeated failures open the circuit breaker ---------------------------------------------------


async def test_repeated_failures_open_the_circuit_breaker() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(403)

    provider, _ = _provider(handler)

    call_count = 12
    results = [
        await provider.enrich_matches(FIXTURE_PROFILE_IDS, [FIXTURE_GAME_IDS[0]])
        for _ in range(call_count)
    ]

    assert all(result == {} for result in results), (
        "every call must return nothing rather than raise — this is the one provider whose "
        "failure is not an error"
    )
    assert request_count < call_count, (
        "the circuit breaker must open at some point and stop reaching the transport on every "
        "further call — reissuing a request (and its retry budget) forever is not 'opening' "
        "anything"
    )

    # Once open, the tail of the run must add no further requests: a breaker that still tries on
    # every single call has not observably opened, whatever internal state it claims to hold.
    plateaued_at = request_count
    for _ in range(3):
        await provider.enrich_matches(FIXTURE_PROFILE_IDS, [FIXTURE_GAME_IDS[0]])
    assert request_count == plateaued_at, (
        "once open, the circuit breaker must not issue a fresh request on every subsequent call"
    )


# --- Any failure, not only a 403, leaves the caller with nothing rather than an exception ---------


async def test_a_full_outage_also_returns_nothing_so_the_application_still_renders() -> None:
    """providers.md: "the application must render correctly with this provider returning
    nothing, and that case gets a test." A 5xx that exhausts the retry budget is the ordinary
    `ProviderUnavailable` path every other provider raises through — here it must not surface at
    all, so a caller (the dashboard, the match list) never needs a special code path for this one
    provider failing.
    """
    recorder = _Recorder()
    provider, _ = _provider(lambda request: httpx.Response(503), recorder=recorder)

    result = await provider.enrich_matches(FIXTURE_PROFILE_IDS, list(FIXTURE_GAME_IDS))

    assert result == {}
    assert list(result.items()) == []
    # The wire was genuinely asked, and genuinely answered every time with 503 — the retry budget
    # ran its full course before this became "nothing" rather than an exception.
    assert len(recorder.calls) == FAST_RETRY.max_attempts
    assert all(call.status_code == 503 for call in recorder.calls)


# --- FR-045: `linkedProfiles` is never read, wherever the read would happen ----------------------


async def test_linked_profiles_is_never_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """`contracts/providers.md`: "Its `linkedProfiles` field is not to be consumed." FR-045: only a
    completed sign-in establishes that two profiles belong to one person, so a third-party mapping
    like aoe2companion's `linkedProfiles` must not even be read, let alone acted upon.

    Enforced literally: `httpx.Response.json` is patched, for this test only, to parse every nested
    object in the response through `_NoLinkedProfilesGuard` — a `dict` that raises the instant
    `linkedProfiles` is looked up by key, by `.get`, or by membership test, from anywhere the
    provider's parsing code happens to reach it.
    """
    original_json = httpx.Response.json

    def guarded_json(self: httpx.Response, **kwargs: Any) -> Any:
        kwargs.setdefault("object_hook", _guarded_object_hook)
        return original_json(self, **kwargs)

    monkeypatch.setattr(httpx.Response, "json", guarded_json)

    body = copy.deepcopy(_load_matches_fixture())
    # aoe2companion attaches `linkedProfiles` per player (`docs/data-sources.md` §3); inject it
    # onto a real player entry the way the live response would carry it.
    first_player = body["matches"][0]["teams"][0]["players"][0]
    first_player["linkedProfiles"] = [{"profileId": 999999, "steamId": "76500000000000001"}]

    provider, _ = _provider(lambda request: httpx.Response(200, json=body))

    # If the provider ever reads `linkedProfiles`, `_NoLinkedProfilesGuard` raises `AssertionError`
    # from inside `enrich_matches` — this call is where that would surface.
    result = await provider.enrich_matches(FIXTURE_PROFILE_IDS, list(FIXTURE_GAME_IDS))

    assert set(result) == set(FIXTURE_GAME_IDS)
    # `MatchEnrichment` has no `linkedProfiles` field at all (`base.py`), so nothing leaked into
    # the returned value either — belt and braces alongside the guard above.
    assert "linkedProfiles" not in MatchEnrichment.model_fields


# ==================================================================================================
# T312 — `search_players` (implemented by T313): quickstart scenario 2, "nothing about a
# search result leaks an account link".
#
# Ground truth is `contracts/providers.md`'s `PlayerSearchProvider` section
# (`specs/003-player-search-match-analysis/contracts/providers.md`) and `docs/data-sources.md` §3's
# "Profile search behaviour" and "Is there a 'this profile is hidden' signal?" subsections.
# `search_players` is implemented by this same `CompanionEnrichmentProvider`, sharing its circuit
# breaker and token bucket with `enrich_matches` rather than adding new ones — "a search storm and
# an enrichment storm are the same source under the same protection" (providers.md).
#
# Written test-first, before T313 existed, with every test below carrying
# `@pytest.mark.xfail(strict=True, reason=SEARCH_XFAIL_REASON)`; T313 has since landed and removed
# those markers. `PlayerSearchResult` / `PlayerSearchPage` are still imported from inside each test
# body rather than at module scope, for the same collection-safety reason `_provider()` above
# imports `CompanionEnrichmentProvider` lazily.
#
# Fixtures (T311): `fixtures/companion_profiles_search.json` is a real, uncapped 20-record page for
# `?search=vipe`, deliberately keeping `steamId`, `shared` and `sharedHistory` exactly as the source
# sends them — the entire point of this section is proving those fields never reach
# `PlayerSearchResult`. `fixtures/companion_profiles_search_empty.json` is a genuine no-match page.
#
# Four behaviours, matching this task's four clauses:
#
# 1. A genuine response parses into `PlayerSearchResult` objects carrying only the five contract
#    fields (FR-004b) — the account-linking fields are simply absent as attributes, not filtered
#    out of a wider set.
# 2. `PlayerSearchResult` the *dataclass* has exactly those five fields, checked with
#    `dataclasses.fields` rather than by inspecting one instance, so a later refactor that adds
#    `steam_id` back to the dataclass fails here the moment the field is declared — before anything
#    downstream ever sees a value in it.
# 3. A 403, a 5xx (retry-exhausting) and a malformed (unparseable) body each come back as an empty
#    page, never an exception — the same "failure is not an error" contract `enrich_matches`
#    already honours. This is FR-003's precondition: the caller distinguishes "no matches" from
#    "search unavailable" off the breaker's own state, not off a raised error.
# 4. The circuit breaker `search_players` consults is the exact same object `enrich_matches` uses —
#    proven by tripping it through `enrich_matches` alone and then observing `search_players`
#    refuse to reach the transport at all, on that same provider instance.
# ==================================================================================================


# The two T311 fixtures live directly under `fixtures/`, not under `fixtures/companion/` like the
# `enrich_matches` fixtures above (`fixtures/README.md`).
SEARCH_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

# The contract fields `PlayerSearchResult` may carry
# (`specs/003-player-search-match-analysis/contracts/providers.md`'s "The fields, and the one rule
# on them"). `unverified_steam_id` joined this set on 2026-08-24 (constitution IX 3.0.0): it is no
# longer one of the fields FR-004b's strip covered, and inverting this set from "five, none of
# them the source's account-linking claims" to "six, one of them a carried-but-unverified claim"
# was T397's own task. `avatar_hash` joined it under T418 (`data-model.md` §2): parsed from the
# record's `avatarhash`, a hash and never a URL (FR-008a, FR-015).
_SEARCH_CONTRACT_FIELDS = frozenset(
    {
        "profile_id",
        "alias",
        "country",
        "games_played",
        "clan",
        "unverified_steam_id",
        "avatar_hash",
    }
)

# The fields the source's search response carries that `PlayerSearchResult` must never carry, on
# an unrelated basis each (`contracts/providers.md`'s "The fields, and the one rule on them"):
# `shared` has no known meaning, `sharedHistory` is a preference this service neither honours nor
# circumvents, `linkedProfiles` is the same unverifiable claim as `steamId` at a different shape.
# `steam_id` is deliberately not in this set any more — it is carried, under the name
# `unverified_steam_id`, which is in `_SEARCH_CONTRACT_FIELDS` above instead.
_ACCOUNT_LINKING_FIELDS = frozenset({"shared", "shared_history", "linked_profiles"})


def _load_search_fixture() -> dict[str, Any]:
    return json.loads(
        (SEARCH_FIXTURES / "companion_profiles_search.json").read_text(encoding="utf-8")
    )


def _load_search_empty_fixture() -> dict[str, Any]:
    return json.loads(
        (SEARCH_FIXTURES / "companion_profiles_search_empty.json").read_text(encoding="utf-8")
    )


# --- T397: a genuine response carries all six contract fields, including the source's Steam claim,
# and still nothing beyond them ---------------------------------------------------------------


async def test_search_players_returns_all_six_contract_fields() -> None:
    """`fixtures/README.md`: "one full page (20 real records), uncapped" for `?search=vipe`. Every
    one of the 20 records carries `steamId` on the wire (`docs/data-sources.md` §3), and it must
    reach `PlayerSearchResult.unverified_steam_id` unchanged (constitution IX 3.0.0, 2026-08-24) —
    `shared` and `sharedHistory`, also on the wire, must not reach anywhere. Both halves are
    asserted below and neither may slide: the field is carried and equals the source's own value,
    and `shared`/`shared_history`/`linked_profiles` are still absent from the dataclass by
    introspection.
    """
    from aoe2stats_providers.base import PlayerSearchPage, PlayerSearchResult

    body = _load_search_fixture()
    source_steam_ids = {profile["profileId"]: profile["steamId"] for profile in body["profiles"]}
    provider, _ = _provider(lambda request: httpx.Response(200, json=body))

    page = await provider.search_players("vipe", limit=20)

    assert isinstance(page, PlayerSearchPage)
    assert page.has_more is True, (
        "the fixture is one full, uncapped page of a larger result (fixtures/README.md)"
    )
    assert len(page.results) == 20

    for result in page.results:
        assert isinstance(result, PlayerSearchResult)
        # `dataclasses.asdict` walks the instance's own attributes — this is where a value
        # smuggled through by a stray `setattr` or an over-eager `**kwargs` would show up, even if
        # the dataclass *definition* itself (next test) looked clean.
        field_names = set(dataclasses.asdict(result))
        assert field_names == _SEARCH_CONTRACT_FIELDS
        assert field_names.isdisjoint(_ACCOUNT_LINKING_FIELDS)
        for forbidden in _ACCOUNT_LINKING_FIELDS:
            assert not hasattr(result, forbidden)
        # The carried half: the claim is not merely present, it equals the source's own value.
        assert result.unverified_steam_id == source_steam_ids[result.profile_id]

    first = page.results[0]
    assert first.profile_id == 196240
    assert first.alias == "TheViper"
    assert first.country == "de"
    assert first.games_played == 10665, 'the source sends `games` as the string "10665"'
    assert isinstance(first.games_played, int)
    assert first.unverified_steam_id == "76561197984749679"


# --- T396: the source's `steamId` claim is carried, unverified, as `unverified_steam_id` ----------
#
# Constitution IX at 3.0.0 (2026-08-24) retired FR-004b's strip of `steamId` alone — `shared`,
# `sharedHistory` and `linkedProfiles` are unaffected and stay unread (`contracts/providers.md`'s
# "The fields, and the one rule on them"). The two tests that asserted the pre-amendment "five
# fields, `steam_id` absent" shape are inverted in place above and below, which is T397; all four
# were verified failing against the pre-fix tree before the field existed. This section adds the
# field's own coverage: the claim carried verbatim, and the contrast case where it is absent.


async def test_search_players_carries_the_source_steam_claim_as_unverified_steam_id() -> None:
    """Every one of the fixture's 20 records carries a `steamId` on the wire
    (`docs/data-sources.md` §3) — each must reach `PlayerSearchResult.unverified_steam_id`
    unchanged, and under that name only: `unverified_steam_id` is the requirement, not
    `steam_id` (`contracts/providers.md`).
    """
    from aoe2stats_providers.base import PlayerSearchResult

    body = _load_search_fixture()
    source_records = {profile["profileId"]: profile["steamId"] for profile in body["profiles"]}
    provider, _ = _provider(lambda request: httpx.Response(200, json=body))

    page = await provider.search_players("vipe", limit=20)

    assert len(page.results) == 20
    for result in page.results:
        assert isinstance(result, PlayerSearchResult)
        assert not hasattr(result, "steam_id"), (
            "the claim is carried as `unverified_steam_id`, never as `steam_id`"
        )
        assert result.unverified_steam_id == source_records[result.profile_id]
        assert isinstance(result.unverified_steam_id, str)

    first = page.results[0]
    assert first.profile_id == 196240
    assert first.unverified_steam_id == "76561197984749679"


async def test_search_players_missing_or_null_steam_id_keeps_the_record() -> None:
    """The contrast case: a record without a usable `steamId` still parses — `profileId` and
    `name` are what makes a record valid (BL-5), and `unverified_steam_id` is one optional field
    among the others (`country`, `games`, `clan`), not a second gate on the whole record.
    """
    from aoe2stats_providers.base import PlayerSearchResult

    body = copy.deepcopy(_load_search_fixture())
    profiles = body["profiles"]
    del profiles[0]["steamId"]  # entirely absent on the wire
    profiles[1]["steamId"] = None  # present, but `null`

    provider, _ = _provider(lambda request: httpx.Response(200, json=body))

    page = await provider.search_players("vipe", limit=20)

    assert len(page.results) == 20, (
        "neither a missing nor a null `steamId` drops the record (BL-5's own reasoning, one "
        "field over)"
    )
    by_profile_id = {result.profile_id: result for result in page.results}
    assert isinstance(by_profile_id[196240], PlayerSearchResult)
    assert by_profile_id[196240].unverified_steam_id is None
    assert by_profile_id[196240].alias == "TheViper"
    assert by_profile_id[9187696].unverified_steam_id is None
    assert by_profile_id[9187696].alias == "Vipechester"


# --- A genuine empty result is an ordinary outcome, not a breaker failure -------------------------


async def test_search_players_genuine_empty_result_does_not_trip_the_breaker() -> None:
    """A genuine 200 with no matching profiles (`fixtures/companion_profiles_search_empty.json`)
    must look, in outcome, exactly like the failure paths below — an empty page — but, unlike
    them, must leave the circuit breaker closed. FR-003's distinction between "no matches" and
    "search unavailable" is read off the breaker's own state (`contracts/providers.md`), so a
    legitimate empty search that quietly tripped the breaker would make every *next* search look
    unavailable for no reason.
    """
    body = _load_search_empty_fixture()
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(200, json=body)

    provider, _ = _provider(handler)

    page = await provider.search_players("no-such-player-xyz", limit=20)

    assert list(page.results) == []
    assert page.has_more is False

    # A closed breaker lets the next call straight through to the transport; an incorrectly
    # tripped one would refuse it — the contrast to
    # `test_search_players_shares_the_circuit_breaker_with_enrich_matches`, where a real trip does
    # block the next call.
    before = request_count
    await provider.search_players("no-such-player-xyz", limit=20)
    assert request_count == before + 1, "a genuine empty result must not count as a breaker failure"


# --- T397: the dataclass definition itself carries `unverified_steam_id` and no other
# account-linking field, not only its instances -----------------------------------------------


def test_player_search_result_dataclass_has_exactly_the_six_contract_fields() -> None:
    """`contracts/providers.md`'s "The fields, and the one rule on them": `shared`,
    `shared_history` and `linked_profiles` have nowhere to be assigned, deliberately, while
    `unverified_steam_id` does — constitution IX 3.0.0 (2026-08-24) retired FR-004b's strip for
    the source's `steamId` alone. Introspecting `dataclasses.fields` — the class itself, never
    constructed — rather than an instance means a later refactor that adds `shared_history` (or
    any of the fields still excluded) to `PlayerSearchResult` fails this test the moment the field
    is declared, not only once some value happens to reach it.
    """
    from aoe2stats_providers.base import PlayerSearchResult

    field_names = {field.name for field in dataclasses.fields(PlayerSearchResult)}

    assert field_names == _SEARCH_CONTRACT_FIELDS
    assert field_names.isdisjoint(_ACCOUNT_LINKING_FIELDS)
    assert "unverified_steam_id" in field_names
    assert "steam_id" not in field_names, (
        "the claim is carried under the name the contract requires, never under the source's own"
    )


# --- A 403, a 5xx and a malformed body all come back as an empty page, never an exception ---------


async def test_search_players_403_yields_an_empty_page_and_does_not_raise() -> None:
    """A 403 here is the same documented, expected bot-protection noise `enrich_matches` already
    survives (`docs/data-sources.md` §3) — FR-003's precondition depends on this never becoming an
    exception a caller would have to special-case.
    """
    recorder = _Recorder()
    provider, _ = _provider(lambda request: httpx.Response(403), recorder=recorder)

    # No `pytest.raises` here on purpose, as above: any exception fails this test outright.
    page = await provider.search_players("vipe", limit=20)

    assert list(page.results) == []
    assert page.has_more is False
    assert len(recorder.calls) >= 1
    assert recorder.calls[0].status_code == 403
    assert not recorder.calls[0].rate_limited, (
        "a 403 here is normal operating noise, not rate limiting, exactly as for `enrich_matches`"
    )


async def test_search_players_full_outage_yields_an_empty_page_and_does_not_raise() -> None:
    """A 5xx that exhausts the shared retry budget is the ordinary `ProviderUnavailable` path every
    other provider raises through — here, as for `enrich_matches`, it must not surface at all.
    """
    recorder = _Recorder()
    provider, _ = _provider(lambda request: httpx.Response(503), recorder=recorder)

    page = await provider.search_players("vipe", limit=20)

    assert list(page.results) == []
    assert page.has_more is False
    # The wire was genuinely asked, and genuinely answered every time with 503 — the retry budget
    # ran its full course before this became "nothing" rather than an exception.
    assert len(recorder.calls) == FAST_RETRY.max_attempts
    assert all(call.status_code == 503 for call in recorder.calls)


async def test_search_players_malformed_body_yields_an_empty_page_and_does_not_raise() -> None:
    """A 200 whose body does not even parse as JSON is the search-side twin of `enrich_matches`'s
    malformed-body handling: a response the source genuinely sent, just not shaped as documented,
    and still not an exception.
    """
    recorder = _Recorder()
    provider, _ = _provider(
        lambda request: httpx.Response(200, content=b"not json at all"), recorder=recorder
    )

    page = await provider.search_players("vipe", limit=20)

    assert list(page.results) == []
    assert page.has_more is False
    assert recorder.calls[0].status_code == 200


# --- The circuit breaker is the exact same object `enrich_matches` uses ---------------------------


async def test_search_players_shares_the_circuit_breaker_with_enrich_matches() -> None:
    """`contracts/providers.md`: "The existing circuit breaker and token bucket are shared with
    `enrich_matches` rather than duplicated ... two independent breakers would each see half the
    failures and neither would trip." Proven the direct way: trip the breaker through
    `enrich_matches` alone, on one provider instance, then show `search_players` on that same
    instance refuses to reach the transport at all — a duplicated, still-closed breaker for search
    would let this next call straight through to the mock transport and bump `request_count`.
    """
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(403)

    provider, _ = _provider(handler)

    # Enough consecutive failures to open the breaker (`companion/provider.py`'s
    # `_FAILURE_THRESHOLD`), driven entirely through `enrich_matches` — `search_players` is never
    # called until the breaker should already be open, mirroring
    # `test_repeated_failures_open_the_circuit_breaker` above.
    call_count = 12
    for _ in range(call_count):
        result = await provider.enrich_matches(FIXTURE_PROFILE_IDS, [FIXTURE_GAME_IDS[0]])
        assert result == {}
    assert request_count < call_count, "the breaker must have opened during the loop above"

    plateaued_at = request_count
    page = await provider.search_players("vipe", limit=20)

    assert request_count == plateaued_at, (
        "a breaker private to `search_players` would still be closed here and would have issued "
        "a fresh request — the same instance `enrich_matches` already tripped must refuse this "
        "call too, which is what makes it 'the same instance' rather than merely the same type"
    )
    assert list(page.results) == []
    assert page.has_more is False


# ==================================================================================================
# BL-1/BL-2 remediation: a shape-drifted 200 must not be recorded as a genuine, confident answer,
# and a sub-threshold failure must be observable through `last_call_failed()` even while
# `is_degraded()` still reads `False`.
#
# Reproduced against the pre-remediation code before writing these tests (round 2 report):
#   - a 200 body of `{"results": [...]}` (renamed `profiles` key) produced `is_degraded() == False`
#     forever, with `_breaker.record_success()` called before the shape was ever checked.
#   - three consecutive 403s produced `is_degraded() before=False after=False` for the first two
#     calls — `_FAILURE_THRESHOLD` is 3, so nothing distinguished "this call failed" from "the
#     breaker just happens to still be closed" until the third.
# ==================================================================================================


async def test_shape_drifted_200_is_recorded_as_failure_not_a_confident_empty_page() -> None:
    """BL-1: `{"results": [...]}` — a plausible rename of the documented `profiles` key — must be
    treated as a source drift, not a genuine zero-match answer. Before this remediation,
    `_breaker.record_success()` ran unconditionally before the body was parsed, so every search
    against a drifted source answered `degraded: false, results: []` (FR-003's exact prohibition)
    forever, with the breaker never tripping and nothing to self-correct it.
    """
    recorder = _Recorder()
    provider, _ = _provider(
        lambda request: httpx.Response(200, json={"results": [{"profileId": 1, "name": "X"}]}),
        recorder=recorder,
    )

    page = await provider.search_players("vipe", limit=20)

    assert list(page.results) == [], "a malformed shape still returns nothing, exactly like a 403"
    assert page.has_more is False
    assert provider.last_call_failed() is True, (
        "a shape-drifted 200 must be recorded as a failure — the one thing the pre-remediation "
        "code never did, since it called `record_success()` before this body was ever parsed"
    )
    assert recorder.calls[0].status_code == 200, (
        "the wire genuinely answered 200 — it is the body's shape, not the status code, that is "
        "malformed here, the case a non-200 check alone cannot catch"
    )

    # A drift that never clears must eventually open the breaker exactly like a run of 403s would
    # — proving `record_failure()` is really being called, not merely that this one page is empty.
    for _ in range(_FAILURE_THRESHOLD_FOR_TESTS - 1):
        await provider.search_players("vipe", limit=20)
    assert provider.is_degraded() is True, (
        "repeated shape drift must open the breaker exactly like repeated 403s do — this is the "
        "self-correction the pre-remediation code never reached"
    )


async def test_a_genuine_empty_result_still_closes_the_breaker_after_a_prior_drift() -> None:
    """The contrast case: once the source's shape is genuinely `{"profiles": [], ...}` again, that
    is an ordinary, confident empty answer — `record_success()` — not a continuation of the drift.
    Distinguishes "the parser now rejects everything" (a regression BL-1's fix could introduce)
    from "the parser correctly rejects only the drifted shape".
    """
    provider, _ = _provider(
        lambda request: httpx.Response(200, json={"profiles": [], "hasMore": False})
    )

    page = await provider.search_players("no-such-player-xyz", limit=20)

    assert list(page.results) == []
    assert provider.last_call_failed() is False
    assert provider.is_degraded() is False


async def test_all_records_renamed_is_recorded_as_a_failure_not_a_confident_empty_page() -> None:
    """BL-5: the envelope (`{"profiles": [...]}`) is intact, but every record inside it has had its
    contracted `profileId`/`name` fields renamed — `_parse_search_result` drops each one and
    returns `None`, so `results` ends up `[]` from a `profiles` list that was never empty on the
    wire. Before this remediation, `_parse_search_page` only ever raised `_MalformedSearchResponse`
    for an envelope-level drift (body not a dict, or no `profiles` list), so this record-level drift
    parsed "successfully" into an empty page and `search_players` called `record_success()` — the
    same FR-003 inversion BL-1 closed one nesting level up, reopened one level down.
    """
    recorder = _Recorder()
    provider, _ = _provider(
        lambda request: httpx.Response(
            200,
            json={
                "profiles": [{"id": i, "alias": f"player-{i}"} for i in range(20)],
                "hasMore": False,
            },
        ),
        recorder=recorder,
    )

    page = await provider.search_players("vipe", limit=20)

    assert list(page.results) == [], (
        "every record was malformed, so the page is empty exactly like the pre-remediation bug"
    )
    assert provider.last_call_failed() is True, (
        "a `profiles` list that is non-empty on the wire but yields zero parseable records is a "
        "record-level source drift, not a genuine zero-match answer, and must be recorded as a "
        "failure the same way an envelope-level drift already is (BL-1)"
    )
    assert recorder.calls[0].status_code == 200, (
        "the wire genuinely answered 200 with a non-empty `profiles` list — it is the fields "
        "*inside* each record that are malformed, the case an envelope-only check cannot catch"
    )


async def test_one_bad_record_among_good_ones_is_dropped_but_still_a_success() -> None:
    """The contrast case BL-5 exists to protect: one malformed entry among otherwise-good ones must
    still be silently dropped (the existing, correct "one bad entry does not throw away a response
    that otherwise parsed" posture), and the call must still be recorded as a success. Without this
    test, the fix above could not be told apart from one that over-triggers on any single dropped
    record rather than only on "every record in this page was bad".
    """
    recorder = _Recorder()
    good_records = [{"profileId": i, "name": f"player-{i}"} for i in range(19)]
    bad_record = {"id": 999, "alias": "renamed-fields"}
    provider, _ = _provider(
        lambda request: httpx.Response(
            200, json={"profiles": [*good_records, bad_record], "hasMore": False}
        ),
        recorder=recorder,
    )

    page = await provider.search_players("vipe", limit=20)

    assert len(page.results) == 19, "the one malformed record is dropped, not the whole page"
    assert provider.last_call_failed() is False, (
        "a page where every other record parsed fine is a genuine, confident answer — the bad "
        "record's own contribution is 'no result', not 'the whole page is untrustworthy'"
    )
    assert provider.is_degraded() is False
    assert recorder.calls[0].status_code == 200


async def test_last_call_failed_is_true_through_the_sub_threshold_window() -> None:
    """BL-2: `is_degraded()` alone cannot express "this call failed" until the third consecutive
    failure (`_FAILURE_THRESHOLD`) — reproduced against the pre-remediation code: three consecutive
    403s through `search_players` alone produced `is_degraded() before=False after=False` for the
    first two calls. `last_call_failed()` must read `True` after every one of the three, not only
    the third that also trips `is_degraded()`.
    """
    provider, _ = _provider(lambda request: httpx.Response(403))

    for expected_is_degraded in (False, False, True):
        await provider.search_players("vipe", limit=20)
        assert provider.last_call_failed() is True, (
            "every one of these three calls failed at the transport — `last_call_failed()` must "
            "say so regardless of whether the breaker's own threshold has tripped yet"
        )
        assert provider.is_degraded() is expected_is_degraded


_FAILURE_THRESHOLD_FOR_TESTS = 3  # `companion/provider.py`'s own `_FAILURE_THRESHOLD`.


# ==================================================================================================
# T417 — the companion parse widening (implemented by T418): quickstart scenario 3, "colour arrives
# from companion at read time". Ground truth is `data-model.md` §2 (`MatchEnrichment.participants`,
# `EnrichedParticipant`, `PlayerSearchResult.avatar_hash`) and constitution VI/X (a provider MUST
# NOT set a product colour — `colorHex` never reaches `EnrichedParticipant`, the pairing T410's
# tokens exist to guarantee stays a design-system decision, never a third-party string).
#
# Every test below carries `@pytest.mark.xfail(strict=True, reason=T417_XFAIL_REASON)`, and every
# not-yet-existent symbol (`EnrichedParticipant`, `MatchEnrichment.participants`,
# `PlayerSearchResult.avatar_hash`) is read from *inside* the test body, for the same collection-
# safety reason `_provider()` above imports `CompanionEnrichmentProvider` lazily: a module-scope
# `ImportError`/`AttributeError` here would abort the whole workspace suite's collection, while one
# raised inside a test body is exactly what `strict=True` xfail is built to expect. `base.py`
# already defines `MatchEnrichment` and `PlayerSearchResult` today (T417 runs after T416, before
# T418), so for those two the not-yet-existent *symbol* is the widened shape, not the class itself
# — the tests below reach it by attribute (`.participants`, `.avatar_hash`), which raises
# `AttributeError` on the unwidened class exactly as reliably as a missing import does.
#
# Six behaviours, matching this task's clauses:
#
# 1. `enrich_matches` returns `MatchEnrichment.participants` keyed by `profile_id`, parsed from
#    `teams[].players[]`, carrying `color_id`, `team_id`, `won`, `rating` and `rating_diff` — the
#    last two from the wire's distinct `rating` and `ratingDiff` keys, never merged into one field.
# 2. `EnrichedParticipant` carries exactly those five fields and no more — `colorHex` is absent from
#    the model *definition*, asserted by introspecting `model_fields` on the class itself rather
#    than on one parsed instance, so a later refactor that adds it fails here the moment the field
#    is declared.
# 3. A match companion does not know about yields no key in the returned dict at all — never an
#    entry whose `participants` is a dict of null placeholders for the ids the caller asked about.
# 4. A 403, a full outage (5xx exhausting the retry budget) and a malformed (unparseable) body each
#    leave `enrich_matches` returning `{}`, never raising — the same "failure is not an error"
#    contract the baseline tests above already prove, re-asserted here because the widening touches
#    the same parsing path a shape drift could break silently.
# 5. `PlayerSearchResult.avatar_hash` is parsed from the search record's `avatarhash` — a field
#    `_parse_search_result` (`companion/provider.py:425-457`) reads five of the record's fields
#    today and drops.
# ==================================================================================================

T417_XFAIL_REASON = "T418 not implemented yet"

# The five, and only five, fields `data-model.md` §2 gives `EnrichedParticipant` — `colorHex` is
# deliberately absent (constitution VI/X): the hex belongs to the design system as a token, and
# carrying a third-party colour string to the client would let a provider set a product colour and
# bypass the contrast pairing T410 exists to guarantee.
_ENRICHED_PARTICIPANT_FIELDS = frozenset({"color_id", "team_id", "won", "rating", "rating_diff"})


async def test_enrich_matches_participants_keyed_by_profile_id() -> None:
    """`data-model.md` §2: `participants: dict[int, EnrichedParticipant] | None`, parsed from
    `teams[].players[]` and keyed by `profileId`. Checked against two real players from the first
    fixture match (`matchId` 500615037) on opposite teams, so both a loss and a win are covered by
    the same test: `TheZero` (`profileId` 9766616, team 1, lost) and `TheViper` (`profileId` 196240,
    team 2, won) — their `color`/`team`/`won`/`rating`/`ratingDiff` values are read straight off
    `fixtures/companion/matches.json`.
    """
    from aoe2stats_providers.base import EnrichedParticipant

    body = _load_matches_fixture()
    provider, _ = _provider(lambda request: httpx.Response(200, json=body))

    result = await provider.enrich_matches(FIXTURE_PROFILE_IDS, list(FIXTURE_GAME_IDS))

    enrichment = result[500615037]
    assert enrichment.participants is not None
    all_profile_ids = {
        player["profileId"] for team in body["matches"][0]["teams"] for player in team["players"]
    }
    assert set(enrichment.participants) == all_profile_ids

    the_zero = enrichment.participants[9766616]
    assert isinstance(the_zero, EnrichedParticipant)
    assert the_zero.color_id == 1
    assert the_zero.team_id == 1
    assert the_zero.won is False
    assert the_zero.rating == 1371
    assert the_zero.rating_diff == -9

    the_viper = enrichment.participants[196240]
    assert isinstance(the_viper, EnrichedParticipant)
    assert the_viper.color_id == 4
    assert the_viper.team_id == 2
    assert the_viper.won is True
    assert the_viper.rating == 1698
    assert the_viper.rating_diff == 6


async def test_enrich_matches_rating_and_rating_diff_are_two_distinct_wire_fields() -> None:
    """The wire's `rating` and `ratingDiff` are two distinct keys and must land as two distinct
    fields, never merged into one: `rating` (post-match value) and `rating_diff` (the signed
    movement) are asserted as different numbers pulled from different wire keys on the same player,
    proving neither was silently overwritten by the other during parsing.
    """
    body = _load_matches_fixture()
    provider, _ = _provider(lambda request: httpx.Response(200, json=body))

    result = await provider.enrich_matches(FIXTURE_PROFILE_IDS, list(FIXTURE_GAME_IDS))

    the_zero = result[500615037].participants[9766616]
    source_player = next(
        player
        for team in body["matches"][0]["teams"]
        for player in team["players"]
        if player["profileId"] == 9766616
    )
    assert the_zero.rating == source_player["rating"]
    assert the_zero.rating_diff == source_player["ratingDiff"]
    assert the_zero.rating != the_zero.rating_diff


def test_enriched_participant_never_carries_color_hex() -> None:
    """`data-model.md` §2: "`colorHex` is deliberately not carried." Introspecting
    `EnrichedParticipant.model_fields` on the class itself — never on one parsed instance — is
    what makes a later refactor that adds `color_hex` (or `colorHex`) back fail here the moment
    the field is *declared*, before any value could ever reach it. A provider that can set a
    product colour bypasses both constitution VI (tokens only) and the `-contrast` pairing T410
    exists to guarantee.
    """
    from aoe2stats_providers.base import EnrichedParticipant

    field_names = set(EnrichedParticipant.model_fields)

    assert field_names == _ENRICHED_PARTICIPANT_FIELDS
    assert "colorHex" not in field_names
    assert "color_hex" not in field_names


async def test_enriched_participant_instance_never_carries_color_hex_either() -> None:
    """Belt and braces alongside the class-level introspection above: a genuine parsed instance,
    from the real fixture, has no `color_hex` attribute either — the class-level guarantee actually
    holding at the one boundary a caller could reach past it.
    """
    body = _load_matches_fixture()
    provider, _ = _provider(lambda request: httpx.Response(200, json=body))

    result = await provider.enrich_matches(FIXTURE_PROFILE_IDS, list(FIXTURE_GAME_IDS))

    the_zero = result[500615037].participants[9766616]
    assert not hasattr(the_zero, "color_hex")
    assert not hasattr(the_zero, "colorHex")


async def test_a_match_companion_does_not_know_yields_no_entry_rather_than_nulls() -> None:
    """A `game_id` companion has no match for is simply absent from the returned dict — never an
    entry whose `participants` is a dict of null placeholders for the ids the caller asked about.
    Requests the three fixture matches plus one companion has never heard of; the unknown id must be
    absent from `result` entirely, and the three known ones must still carry real participants.
    """
    from aoe2stats_providers.base import EnrichedParticipant

    body = _load_matches_fixture()
    unknown_game_id = 999999999
    provider, _ = _provider(lambda request: httpx.Response(200, json=body))

    result = await provider.enrich_matches(
        FIXTURE_PROFILE_IDS, [*FIXTURE_GAME_IDS, unknown_game_id]
    )

    assert unknown_game_id not in result, (
        "a match companion does not know must yield no entry at all, not an entry standing in "
        "for one with null participants"
    )
    assert set(result) == set(FIXTURE_GAME_IDS)
    for enrichment in result.values():
        assert enrichment.participants
        for participant in enrichment.participants.values():
            assert isinstance(participant, EnrichedParticipant)


# --- T409's own contrast case: a match absent from the profiles' returned pages is a silent miss,
# never a coerced 0/placeholder colour (`companion/provider.py`'s "The endpoint" note: this
# provider never chases a second page, so an old match a profile's default page no longer carries
# — "an old match companion no longer pages" — is an honest degrade, not something to invent a
# value for) ---------------------------------------------------------------------------------------


async def test_contrast_case_old_match_no_longer_paged_yields_no_entry() -> None:
    """The contrast case named in the task: `game_ids` may ask about a match older than the one
    default page `enrich_matches` ever requests for `profile_ids` — companion's own recency-ordered
    paging, not a match id filter — and that match must come back absent from the dict, exactly
    like `test_a_match_companion_does_not_know_yields_no_entry_rather_than_nulls` above (the
    provider has no way to tell "too old to be on this page" apart from "companion has never heard
    of it" — both are simply not in the response). `enrich_colours` (`routers/matches.py`) reads
    this same absence to leave `match_players.color_id` exactly as it was — see
    `apps/api/tests/test_match_colour_enrichment.py`'s own DB-level assertion of that.
    """
    body = _load_matches_fixture()
    old_game_id = 400000001  # older than anything on the profiles' default page fixture carries
    provider, _ = _provider(lambda request: httpx.Response(200, json=body))

    result = await provider.enrich_matches(FIXTURE_PROFILE_IDS, [old_game_id])

    assert result == {}, (
        "a match too old for the profiles' default page must yield no entry at all, never a "
        "placeholder — this is the honest degrade, not a failure this provider can distinguish "
        "from 'companion has never heard of this match'"
    )


async def test_enrich_matches_with_participants_403_still_returns_nothing() -> None:
    """`docs/data-sources.md` §3 / Technology Constraints: "aoe2companion (enrichment only,
    degradable)" — its failure is not an error. Re-asserted here, on top of the participants
    widening, because a shape drift touching the same parsing path could break silently otherwise.
    Importing `EnrichedParticipant` first is what makes this test genuinely fail today (T418 not
    landed) rather than accidentally passing on the unwidened `enrich_matches`, which already
    returns `{}` on a 403 for reasons unrelated to this task.
    """
    from aoe2stats_providers.base import EnrichedParticipant  # noqa: F401

    recorder = _Recorder()
    provider, _ = _provider(lambda request: httpx.Response(403), recorder=recorder)

    result = await provider.enrich_matches(FIXTURE_PROFILE_IDS, list(FIXTURE_GAME_IDS))

    assert result == {}
    assert len(recorder.calls) >= 1
    assert recorder.calls[0].status_code == 403


async def test_enrich_matches_with_participants_full_outage_still_returns_nothing() -> None:
    """The 5xx twin of the 403 test above: the retry budget exhausts and `enrich_matches` still
    returns `{}` rather than raising, with the participants widening in place.
    """
    from aoe2stats_providers.base import EnrichedParticipant  # noqa: F401

    recorder = _Recorder()
    provider, _ = _provider(lambda request: httpx.Response(503), recorder=recorder)

    result = await provider.enrich_matches(FIXTURE_PROFILE_IDS, list(FIXTURE_GAME_IDS))

    assert result == {}
    assert len(recorder.calls) == FAST_RETRY.max_attempts
    assert all(call.status_code == 503 for call in recorder.calls)


async def test_enrich_matches_with_participants_malformed_body_still_returns_nothing() -> None:
    """A 200 whose body does not even parse as JSON — the `enrich_matches` twin of
    `test_search_players_malformed_body_yields_an_empty_page_and_does_not_raise` above, not
    previously covered for `enrich_matches` at all: a response the source genuinely sent, just not
    shaped as documented, and still not an exception.
    """
    from aoe2stats_providers.base import EnrichedParticipant  # noqa: F401

    recorder = _Recorder()
    provider, _ = _provider(
        lambda request: httpx.Response(200, content=b"not json at all"), recorder=recorder
    )

    result = await provider.enrich_matches(FIXTURE_PROFILE_IDS, list(FIXTURE_GAME_IDS))

    assert result == {}
    assert recorder.calls[0].status_code == 200


async def test_player_search_result_avatar_hash_parsed_from_avatarhash() -> None:
    """`data-model.md` §2: "Add `avatar_hash: str | None`, parsed from `avatarhash` in
    `_parse_search_result`". Every one of the fixture's 20 records carries `avatarhash` on the wire
    (`docs/data-sources.md:296`); each must reach `PlayerSearchResult.avatar_hash` unchanged, under
    that name — a hash, never a URL, and nothing in `packages/providers` builds the Steam CDN URL
    from it (FR-008a, FR-015).
    """
    body = _load_search_fixture()
    source_avatar_hashes = {
        profile["profileId"]: profile["avatarhash"] for profile in body["profiles"]
    }
    provider, _ = _provider(lambda request: httpx.Response(200, json=body))

    page = await provider.search_players("vipe", limit=20)

    assert len(page.results) == 20
    for result in page.results:
        assert result.avatar_hash == source_avatar_hashes[result.profile_id]

    first = page.results[0]
    assert first.profile_id == 196240
    assert first.avatar_hash == "eefa125e4e662af9600355746783166942b8a1ff"


def test_player_search_result_dataclass_has_an_avatar_hash_field() -> None:
    """The class-level twin of the test above, in `test_player_search_result_dataclass_has_exactly_
    the_six_contract_fields`'s own style: introspecting `dataclasses.fields` on the class itself,
    never an instance, so a later refactor that drops `avatar_hash` — or renames it away from the
    name `data-model.md` §2 requires — fails here the moment the field is (mis)declared.
    """
    from aoe2stats_providers.base import PlayerSearchResult

    field_names = {field.name for field in dataclasses.fields(PlayerSearchResult)}

    assert "avatar_hash" in field_names
