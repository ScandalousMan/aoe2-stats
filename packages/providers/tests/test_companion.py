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
    from aoe2stats_providers.companion.provider import CompanionEnrichmentProvider

# Every test in this file is expected to fail for exactly one reason — T051 does not exist yet —
# until it does. `strict=True` is what makes that honest: the moment T051 lands and a test starts
# passing, `strict=True` turns the *run* red instead of letting a stale xfail hide it, which is the
# whole point of marking these tests failing rather than skipping them. Do not drop `strict=True`.
XFAIL_REASON = "CompanionEnrichmentProvider is implemented by T051, not this test-first task (T041)"

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "companion"

# The three real `matchId` values `fixtures/companion/matches.json` carries (`fixtures/README.md`:
# "capped to 3 real matches" — fewer entries than the live response, not different ones).
FIXTURE_GAME_IDS = (500615037, 500572650, 500564671)

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
) -> tuple[CompanionEnrichmentProvider, _Recorder]:
    """Imports `CompanionEnrichmentProvider` here, at call time, rather than at module scope: this
    is the one place every test below reaches the not-yet-existent T051 module through, so this is
    where the resulting `ModuleNotFoundError` is meant to surface — inside the test call, where
    `strict=True` xfail turns it into an expected failure, not during collection, where it would
    abort the whole workspace suite.
    """
    from aoe2stats_providers.companion.provider import CompanionEnrichmentProvider

    recorder = recorder or _Recorder()
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = CompanionEnrichmentProvider(
        client=client,
        timeout_seconds=5.0,
        rate_limiter=TokenBucket(rate_per_second),
        call_sink=recorder.async_sink,
        retry_policy=retry_policy,
    )
    return provider, recorder


# --- Baseline: a genuine 200 parses, so the failure tests below are a real contrast --------------


async def test_enrich_matches_parses_a_genuine_response_keyed_by_game_id() -> None:
    body = _load_matches_fixture()
    provider, recorder = _provider(lambda request: httpx.Response(200, json=body))

    result = await provider.enrich_matches(list(FIXTURE_GAME_IDS))

    assert set(result) == set(FIXTURE_GAME_IDS)
    for game_id, enrichment in result.items():
        assert isinstance(enrichment, MatchEnrichment)
        assert enrichment.game_id == game_id
    assert len(recorder.calls) >= 1
    assert all(not call.rate_limited for call in recorder.calls)


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
    result = await provider.enrich_matches(list(FIXTURE_GAME_IDS))

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
    results = [await provider.enrich_matches([FIXTURE_GAME_IDS[0]]) for _ in range(call_count)]

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
        await provider.enrich_matches([FIXTURE_GAME_IDS[0]])
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

    result = await provider.enrich_matches(list(FIXTURE_GAME_IDS))

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
    result = await provider.enrich_matches(list(FIXTURE_GAME_IDS))

    assert set(result) == set(FIXTURE_GAME_IDS)
    # `MatchEnrichment` has no `linkedProfiles` field at all (`base.py`), so nothing leaked into
    # the returned value either — belt and braces alongside the guard above.
    assert "linkedProfiles" not in MatchEnrichment.model_fields


# ==================================================================================================
# T312 — `search_players` (T313 not implemented yet): quickstart scenario 2, "nothing about a
# search result leaks an account link".
#
# Ground truth is `contracts/providers.md`'s `PlayerSearchProvider` section
# (`specs/003-player-search-match-analysis/contracts/providers.md`) and `docs/data-sources.md` §3's
# "Profile search behaviour" and "Is there a 'this profile is hidden' signal?" subsections.
# `search_players` is implemented by this same `CompanionEnrichmentProvider`, sharing its circuit
# breaker and token bucket with `enrich_matches` rather than adding new ones — "a search storm and
# an enrichment storm are the same source under the same protection" (providers.md).
#
# Written test-first, before T313 exists: every test below carries
# `@pytest.mark.xfail(strict=True, reason=SEARCH_XFAIL_REASON)`, and imports `PlayerSearchResult` /
# `PlayerSearchPage` from inside the test body rather than at module scope, for the same
# collection-safety reason `_provider()` above imports `CompanionEnrichmentProvider` lazily: those
# names do not exist on `aoe2stats_providers.base` yet, and a module-scope import of a missing name
# would abort collection for the whole workspace rather than failing one test.
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

SEARCH_XFAIL_REASON = "T313 not implemented yet"

# The two T311 fixtures live directly under `fixtures/`, not under `fixtures/companion/` like the
# `enrich_matches` fixtures above (`fixtures/README.md`).
SEARCH_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

# The five, and only five, contract fields `PlayerSearchResult` may carry
# (`specs/003-player-search-match-analysis/contracts/providers.md`).
_SEARCH_CONTRACT_FIELDS = frozenset({"profile_id", "alias", "country", "games_played", "clan"})

# The account-linking fields the source's search response carries (`docs/data-sources.md` §3's
# trap: `steamId`, `shared`, `sharedHistory`), plus `linkedProfiles`'s own name for consistency
# with `enrich_matches` above — `PlayerSearchResult` must never carry any of them (FR-004b).
_ACCOUNT_LINKING_FIELDS = frozenset({"steam_id", "shared", "shared_history", "linked_profiles"})


def _load_search_fixture() -> dict[str, Any]:
    return json.loads(
        (SEARCH_FIXTURES / "companion_profiles_search.json").read_text(encoding="utf-8")
    )


def _load_search_empty_fixture() -> dict[str, Any]:
    return json.loads(
        (SEARCH_FIXTURES / "companion_profiles_search_empty.json").read_text(encoding="utf-8")
    )


# --- A genuine response carries only the five contract fields, nothing about account links -------


@pytest.mark.xfail(strict=True, reason=SEARCH_XFAIL_REASON)
async def test_search_players_returns_only_the_five_contract_fields() -> None:
    """`fixtures/README.md`: "one full page (20 real records), uncapped" for `?search=vipe`. Every
    one of the 20 records carries `steamId`, `shared` and `sharedHistory` on the wire
    (`docs/data-sources.md` §3) — none of it may survive into a `PlayerSearchResult`.
    """
    from aoe2stats_providers.base import PlayerSearchPage, PlayerSearchResult

    body = _load_search_fixture()
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

    first = page.results[0]
    assert first.profile_id == 196240
    assert first.alias == "TheViper"
    assert first.country == "de"
    assert first.games_played == 10665, 'the source sends `games` as the string "10665"'
    assert isinstance(first.games_played, int)


# --- A genuine empty result is an ordinary outcome, not a breaker failure -------------------------


@pytest.mark.xfail(strict=True, reason=SEARCH_XFAIL_REASON)
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


# --- The dataclass definition itself carries no account-linking field, not only its instances -----


@pytest.mark.xfail(strict=True, reason=SEARCH_XFAIL_REASON)
def test_player_search_result_dataclass_has_no_account_linking_field() -> None:
    """FR-004b: "these fields exist in the response and carrying them further would breach 001's
    FR-045 by accident rather than by decision." Introspecting `dataclasses.fields` — the class
    itself, never constructed — rather than an instance means a later refactor that adds
    `steam_id` back to `PlayerSearchResult` fails this test the moment the field is declared, not
    only once some value happens to reach it.
    """
    from aoe2stats_providers.base import PlayerSearchResult

    field_names = {field.name for field in dataclasses.fields(PlayerSearchResult)}

    assert field_names == _SEARCH_CONTRACT_FIELDS
    assert field_names.isdisjoint(_ACCOUNT_LINKING_FIELDS)


# --- A 403, a 5xx and a malformed body all come back as an empty page, never an exception ---------


@pytest.mark.xfail(strict=True, reason=SEARCH_XFAIL_REASON)
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


@pytest.mark.xfail(strict=True, reason=SEARCH_XFAIL_REASON)
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


@pytest.mark.xfail(strict=True, reason=SEARCH_XFAIL_REASON)
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


@pytest.mark.xfail(strict=True, reason=SEARCH_XFAIL_REASON)
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
        result = await provider.enrich_matches([FIXTURE_GAME_IDS[0]])
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
