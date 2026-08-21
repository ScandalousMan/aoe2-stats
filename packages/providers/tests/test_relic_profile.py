"""Contract test for `ProfileProvider` (T020) — the Relic profile-resolution adapter.

Ground truth is `specs/001-steam-link-replay-ingestion/contracts/providers.md` and the endpoint
shapes measured in `docs/data-sources.md` §1. Every request in this file goes through
`httpx.MockTransport` against the frozen responses in `packages/providers/fixtures/relic/`
(captured by `scripts/checks/contract_sources.py`, see `fixtures/README.md`) — constitution III
forbids the network in unit tests, and `tests/conftest.py` blocks any real socket connection under
`PYTEST_DISABLE_NETWORK=1` regardless.

Written as a test-first task, before `aoe2stats_providers.relic.profile` existed (T027), so every
test below carried `@pytest.mark.xfail(strict=True, ...)` until that adapter was built to satisfy
exactly the four behaviours below. T027 has since landed and the markers are gone: `strict=True` is
what forced their removal, by turning the run red the moment the tests began to pass. The import of
`aoe2stats_providers.relic.profile` still lives inside `_provider()` rather than at module scope,
which is worth keeping — a module-scope `ModuleNotFoundError` aborts the *entire* workspace suite's
collection rather than failing one test (`pytest -q` interrupts collection on any import error,
workspace-wide, per `tool.pytest.ini_options.testpaths` in the root `pyproject.toml`).

Four behaviours, matching `contracts/providers.md`'s `ProfileProvider`:

1. `resolve_profile` returns a `ProfileRef` for a Steam id with an AoE2 profile.
2. `resolve_profile` returns `None` — an ordinary outcome (FR-003), never an error — for a Steam
   id with no AoE2 profile.
3. `personal_stats` batches: it parses a genuinely multi-profile response correctly, and it caps
   any request at 50 profiles, splitting a longer list across multiple calls rather than sending
   one oversized request.
4. A field of an unexpected type is a `ProviderContractViolation`, never silently coerced.
   `fixtures/README.md` is explicit that this case has no fixture of its own — the real API has
   never returned one — so this test mutates a loaded copy of `get_personal_stat.json` instead of
   inventing a response that does not exist in the wild.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import pytest

from aoe2stats_providers.base import (
    ProfileRef,
    ProviderCallRecord,
    ProviderContractViolation,
    TokenBucket,
)

if TYPE_CHECKING:
    # Type-checking only: mypy needs the name, but nothing here may import the module at
    # collection time — see `_provider()` below, where the real (runtime) import lives.
    from aoe2stats_providers.relic.profile import RelicProfileProvider

# Every test in this file is expected to fail for exactly one reason — T027 does not exist yet —
# until it does. `strict=True` is what makes that honest: the moment T027 lands and a test starts
# passing, `strict=True` turns the *run* red instead of letting a stale xfail hide it, which is the
# whole point of marking these tests failing rather than skipping them. Do not drop `strict=True`.
XFAIL_REASON = "RelicProfileProvider is implemented by T027, not this test-first task (T020)"

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "relic"


def _load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class _Recorder:
    """An `AsyncProviderCallSink` double that just remembers `provider_calls` rows."""

    def __init__(self) -> None:
        self.calls: list[ProviderCallRecord] = []

    async def async_sink(self, record: ProviderCallRecord) -> None:
        self.calls.append(record)


def _provider(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    recorder: _Recorder | None = None,
    rate_per_second: float = 1000.0,
) -> tuple[RelicProfileProvider, _Recorder]:
    """Imports `RelicProfileProvider` here, at call time, rather than at module scope: this is the
    one place every test below reaches the not-yet-existent T027 module through, so this is where
    the resulting `ModuleNotFoundError` is meant to surface — inside the test call, where
    `strict=True` xfail turns it into an expected failure, not during collection, where it would
    abort the whole workspace suite.
    """
    from aoe2stats_providers.relic.profile import RelicProfileProvider

    recorder = recorder or _Recorder()
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = RelicProfileProvider(
        client=client,
        timeout_seconds=5.0,
        rate_limiter=TokenBucket(rate_per_second),
        call_sink=recorder.async_sink,
    )
    return provider, recorder


# --- resolve_profile: found ------------------------------------------------------------------


async def test_resolve_profile_returns_a_profile_ref() -> None:
    body = _load("get_personal_stat.json")
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=body)

    provider, recorder = _provider(handler)

    ref = await provider.resolve_profile("76561197984749679")

    assert ref == ProfileRef(profile_id=196240, alias="Oni.TheViper", country="de")
    assert seen["params"]["title"] == "age2"
    assert json.loads(seen["params"]["profile_names"]) == ["/steam/76561197984749679"]
    assert len(recorder.calls) == 1
    assert recorder.calls[0].status_code == 200


# --- resolve_profile: no AoE2 profile (FR-003, an ordinary outcome, never an error) ------------


async def test_resolve_profile_returns_none_for_a_steam_account_with_no_aoe2_profile() -> None:
    body = _load("get_personal_stat_unregistered.json")
    provider, recorder = _provider(lambda request: httpx.Response(200, json=body))

    ref = await provider.resolve_profile("76561197960287930")

    assert ref is None
    assert len(recorder.calls) == 1


# --- personal_stats: parses a genuine multi-profile response -----------------------------------


async def test_personal_stats_parses_a_batched_response() -> None:
    body = _load("get_personal_stat_batch.json")
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=body)

    provider, recorder = _provider(handler)

    snapshots = await provider.personal_stats([196240, 199325])

    assert seen["params"]["title"] == "age2"
    assert json.loads(seen["params"]["profile_ids"]) == [196240, 199325]
    assert len(recorder.calls) == 1

    by_profile_and_leaderboard = {(s.profile_id, s.leaderboard_id): s for s in snapshots}
    viper = by_profile_and_leaderboard[(196240, 3)]
    assert viper.rating == 2704
    assert viper.rank == 27
    assert viper.wins == 1757
    assert viper.losses == 965
    hera = by_profile_and_leaderboard[(199325, 3)]
    assert hera.rating == 2961
    assert hera.rank == 2


# --- personal_stats: caps every call at 50 profiles ---------------------------------------------


async def test_personal_stats_batches_at_most_fifty_profiles_per_call() -> None:
    profile_ids = list(range(1, 56))  # 55 profiles: one full batch, one remainder
    batch_sizes: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested = json.loads(dict(request.url.params)["profile_ids"])
        batch_sizes.append(len(requested))
        # A minimal, schema-valid empty response: this test is about the request shape, not the
        # parsed content, which the previous test already covers.
        return httpx.Response(
            200,
            json={
                "leaderboardStats": [],
                "result": {"code": 0, "message": "SUCCESS"},
                "statGroups": [],
            },
        )

    provider, recorder = _provider(handler)

    snapshots = await provider.personal_stats(profile_ids)

    assert batch_sizes == [50, 5], "must split more than 50 profiles across multiple calls"
    assert len(recorder.calls) == 2
    assert snapshots == []


# --- Strict validation: an unexpected field type is a contract violation, never a coercion ------


async def test_resolve_profile_raises_contract_violation_on_a_field_of_unexpected_type() -> None:
    """`fixtures/README.md`: "mutate a loaded copy of relic/get_personal_stat.json in Python
    rather than freezing a response that does not exist in the wild."
    """
    body = copy.deepcopy(_load("get_personal_stat.json"))
    body["statGroups"][0]["members"][0]["profile_id"] = "not-an-int"

    provider, _ = _provider(lambda request: httpx.Response(200, json=body))

    with pytest.raises(ProviderContractViolation):
        await provider.resolve_profile("76561197984749679")
