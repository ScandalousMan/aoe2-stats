"""Contract test for `MatchHistoryProvider` (T040) — the Relic match-discovery adapter.

Ground truth is `specs/001-steam-link-replay-ingestion/contracts/providers.md`'s
`MatchHistoryProvider` and the endpoint shape measured in `docs/data-sources.md` §1
(`getRecentMatchHistory`). Every request in this file goes through `httpx.MockTransport` against
the frozen responses in `packages/providers/fixtures/relic/` — constitution III forbids the network
in unit tests, and `tests/conftest.py` blocks any real socket connection under
`PYTEST_DISABLE_NETWORK=1` regardless.

Written as a test-first task, before `aoe2stats_providers.relic.matches` existed (T050), so every
test below carried `@pytest.mark.xfail(strict=True, ...)`, matching `test_relic_profile.py`'s
(T020) pattern for the same situation. T050 has since landed and the markers are gone: `strict=True`
is what forced their removal, by turning the run red the moment the tests began to pass. The import
of `aoe2stats_providers.relic.matches` still lives inside `_provider()` rather than at module scope,
which is worth keeping — a module-scope `ModuleNotFoundError` aborts the *entire* workspace suite's
collection, not just fail this one file's tests.

Two behaviours, matching `contracts/providers.md`'s `MatchHistoryProvider`:

1. `recent_matches` returns one `RawMatch` per entry in `matchHistoryStats`, with the parsed fields
   `contracts/providers.md` and `docs/data-sources.md` §1 both describe (`id` -> `game_id`,
   `matchtype_id` -> `leaderboard_id`, `mapname` -> `map_name`, `startgametime`/`completiontime` ->
   `started_at`/`completed_at`, every `matchhistorymember[].profile_id` -> `player_profile_ids`) —
   *and* `raw_payload` carries that same source entry byte-for-byte untouched, per FR-012 and the
   module docstring of `aoe2stats_providers.base` ("`RawMatch.raw_payload` is the exact
   `matches.raw_payload` column value").
2. `recent_matches` batches: a request for more than 10 profiles is split across multiple calls of
   at most 10 profiles each — `contracts/providers.md`: "Batched, up to 10 profiles per call — the
   response is roughly 400 KB per profile" — rather than one oversized request.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from aoe2stats_providers.base import ProviderCallRecord, RawMatch, TokenBucket

if TYPE_CHECKING:
    # Type-checking only: mypy needs the name, but nothing here may import the module at
    # collection time — see `_provider()` below, where the real (runtime) import lives.
    from aoe2stats_providers.relic.matches import RelicMatchHistoryProvider

XFAIL_REASON = "T050 not implemented yet"

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
) -> tuple[RelicMatchHistoryProvider, _Recorder]:
    """Imports `RelicMatchHistoryProvider` here, at call time, rather than at module scope: this is
    the one place every test below reaches the not-yet-existent T050 module through, so this is
    where the resulting `ModuleNotFoundError` is meant to surface — inside the test call, where
    `strict=True` xfail turns it into an expected failure, not during collection, where it would
    abort the whole workspace suite.
    """
    from aoe2stats_providers.relic.matches import RelicMatchHistoryProvider

    recorder = recorder or _Recorder()
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = RelicMatchHistoryProvider(
        client=client,
        timeout_seconds=5.0,
        rate_limiter=TokenBucket(rate_per_second),
        call_sink=recorder.async_sink,
    )
    return provider, recorder


# --- recent_matches: parsed fields, alongside the untouched raw payload -------------------------


async def test_recent_matches_returns_raw_matches_with_parsed_fields_and_untouched_payload() -> (
    None
):
    body = _load("get_recent_match_history.json")
    raw_entries = body["matchHistoryStats"]
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=body)

    provider, recorder = _provider(handler)

    matches = await provider.recent_matches([196240])

    assert seen["params"]["title"] == "age2"
    assert json.loads(seen["params"]["profile_ids"]) == [196240]
    assert len(recorder.calls) == 1
    assert recorder.calls[0].status_code == 200

    # One `RawMatch` per source entry, in order — none dropped, none invented.
    assert len(matches) == len(raw_entries)
    assert all(isinstance(match, RawMatch) for match in matches)

    first_raw = raw_entries[0]
    first_match = matches[0]

    assert first_match.game_id == first_raw["id"] == 500615037
    assert first_match.leaderboard_id == first_raw["matchtype_id"] == 0
    assert first_match.map_name == first_raw["mapname"] == "my map"
    assert first_match.started_at is not None
    assert first_match.started_at.timestamp() == first_raw["startgametime"]
    assert first_match.completed_at.timestamp() == first_raw["completiontime"]
    assert first_match.duration_seconds == (
        first_raw["completiontime"] - first_raw["startgametime"]
    )

    expected_players = {member["profile_id"] for member in first_raw["matchhistorymember"]}
    assert set(first_match.player_profile_ids) == expected_players

    # `raw_payload` is the *exact* source entry, byte-for-byte, not a re-derived subset of it —
    # `contracts/providers.md`: "`RawMatch` carries the parsed fields *and* the untouched payload."
    assert first_match.raw_payload == first_raw


# --- recent_matches: caps every call at 10 profiles ----------------------------------------------


async def test_recent_matches_batches_at_most_ten_profiles_per_call() -> None:
    profile_ids = list(range(1, 24))  # 23 profiles: two full batches, one remainder
    batch_sizes: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested = json.loads(dict(request.url.params)["profile_ids"])
        batch_sizes.append(len(requested))
        # A minimal, schema-valid empty response: this test is about the request shape, not the
        # parsed content, which the previous test already covers.
        return httpx.Response(200, json={"matchHistoryStats": [], "profiles": [], "result": {}})

    provider, recorder = _provider(handler)

    matches = await provider.recent_matches(profile_ids)

    assert batch_sizes == [10, 10, 3], "must split more than 10 profiles across multiple calls"
    assert len(recorder.calls) == 3
    assert matches == []


# --- recent_matches: a genuinely multi-profile response parses every match, once per entry -------


async def test_recent_matches_parses_a_genuine_multi_profile_response() -> None:
    body = _load("get_recent_match_history_batch.json")
    raw_entries = body["matchHistoryStats"]

    provider, recorder = _provider(lambda request: httpx.Response(200, json=body))

    matches = await provider.recent_matches([196240, 199325])

    assert len(recorder.calls) == 1
    assert len(matches) == len(raw_entries)

    by_game_id = {match.game_id: match for match in matches}
    for raw in raw_entries:
        match = by_game_id[raw["id"]]
        assert match.raw_payload == raw
        expected_players = {member["profile_id"] for member in raw["matchhistorymember"]}
        assert set(match.player_profile_ids) == expected_players
