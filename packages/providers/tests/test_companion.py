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
"""

from __future__ import annotations

import copy
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


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON)
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


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON)
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


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON)
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


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON)
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


@pytest.mark.xfail(strict=True, reason=XFAIL_REASON)
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
