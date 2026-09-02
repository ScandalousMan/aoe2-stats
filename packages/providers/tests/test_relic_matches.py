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


# --- recent_matches: an unfinished match is skipped, not fatal to the batch (T050a) --------------


async def test_recent_matches_skips_an_unfinished_entry_and_keeps_the_rest_of_the_batch() -> None:
    """Relic's *recent* match history endpoint reports games that have not finished, whose
    `completiontime` is absent — `_epoch_seconds_to_datetime` maps that to `None`, and
    `RawMatch.completed_at` is required. Before T050a, `parse_strict` rejected that row and the
    resulting `ProviderContractViolation` escaped `recent_matches` uncaught, taking the whole
    batch — and, one call up, the whole cycle — down on one in-progress game.

    An unfinished match carries no `completed_at`, so it can carry no `capture_deadline_at`
    either (`capture_deadline_at = completed_at + CAPTURE_BUDGET_DAYS`, T053): it is not yet
    capturable and belongs in neither `matches` nor `replay_captures` until a later cycle
    observes it complete. It is skipped deliberately, not parsed with an invented timestamp.
    """
    body = _load("get_recent_match_history.json")
    unfinished_index = 1
    body["matchHistoryStats"][unfinished_index] = {
        **body["matchHistoryStats"][unfinished_index],
        "completiontime": None,
    }
    raw_entries = body["matchHistoryStats"]
    unfinished_game_id = raw_entries[unfinished_index]["id"]

    provider, recorder = _provider(lambda request: httpx.Response(200, json=body))

    matches = await provider.recent_matches([196240])

    # Every other entry still parses; only the unfinished one is missing.
    assert len(matches) == len(raw_entries) - 1
    assert unfinished_game_id not in {match.game_id for match in matches}

    # Countable, not silent (T050a): the skip leaves its own `provider_calls` row alongside the
    # one already recorded for the HTTP request, so a batch that skipped entries is
    # distinguishable — by anyone reading `provider_calls` — from one that had none. A source
    # that starts rejecting everything must not read as a quiet, empty cycle.
    assert len(recorder.calls) == 2
    assert recorder.calls[0].status_code == 200
    skip_record = recorder.calls[1]
    assert skip_record.provider == "relic"
    assert skip_record.status_code is None
    assert skip_record.rate_limited is False
    assert "skipped" in skip_record.endpoint
    assert "unfinished" in skip_record.endpoint


async def test_recent_matches_treats_completiontime_zero_as_unfinished_too() -> None:
    """Relic represents an in-progress match not only with an absent `completiontime` but also
    with `completiontime: 0`. `_epoch_seconds_to_datetime(0)` is a real, non-`None` `datetime`
    (the Unix epoch), so a guard that only checks "is `completiontime` absent" lets this shape
    sail straight through `parse_strict` as a perfectly valid `RawMatch` with
    `completed_at = 1970-01-01` — silently, no `ProviderContractViolation` at all. That is worse
    than the crash T050a fixed: downstream, `capture_deadline_at` is derived from that fabricated
    `completed_at`, sorts first in every claim order ahead of every real capture, and reads as
    long past its deadline — an `expired_capture` alert for a match still being played. A
    non-positive `completiontime` must be read exactly like a `None` one.
    """
    body = _load("get_recent_match_history.json")
    unfinished_index = 1
    body["matchHistoryStats"][unfinished_index] = {
        **body["matchHistoryStats"][unfinished_index],
        "completiontime": 0,
    }
    raw_entries = body["matchHistoryStats"]
    unfinished_game_id = raw_entries[unfinished_index]["id"]

    provider, recorder = _provider(lambda request: httpx.Response(200, json=body))

    matches = await provider.recent_matches([196240])

    assert len(matches) == len(raw_entries) - 1
    assert unfinished_game_id not in {match.game_id for match in matches}
    assert all(match.completed_at.year != 1970 for match in matches)

    assert len(recorder.calls) == 2
    skip_record = recorder.calls[1]
    assert skip_record.status_code is None
    assert "skipped" in skip_record.endpoint
    assert "unfinished" in skip_record.endpoint


# --- recent_matches: a malformed entry is skipped, not fatal to the batch (T050a) -----------------


async def test_recent_matches_skips_a_malformed_entry_and_keeps_the_rest_of_the_batch() -> None:
    """A `ProviderContractViolation` on one entry — here `matchtype_id` arriving as a string
    rather than the `int` the contract requires — must not throw away the rest of the batch,
    matching `CompanionEnrichmentProvider._parse_matches`'s existing
    `except ProviderContractViolation: continue` shape.
    """
    body = _load("get_recent_match_history.json")
    malformed_index = 0
    body["matchHistoryStats"][malformed_index] = {
        **body["matchHistoryStats"][malformed_index],
        "matchtype_id": "not-an-int",
    }
    raw_entries = body["matchHistoryStats"]
    malformed_game_id = raw_entries[malformed_index]["id"]

    provider, recorder = _provider(lambda request: httpx.Response(200, json=body))

    matches = await provider.recent_matches([196240])

    assert len(matches) == len(raw_entries) - 1
    assert malformed_game_id not in {match.game_id for match in matches}

    # Countable, not silent (T050a), and distinguishable from the "unfinished match" skip above —
    # the two are different conditions and an operator reading `provider_calls` should be able to
    # tell them apart.
    assert len(recorder.calls) == 2
    skip_record = recorder.calls[1]
    assert skip_record.provider == "relic"
    assert skip_record.status_code is None
    assert "skipped" in skip_record.endpoint
    assert "malformed" in skip_record.endpoint


# --- recent_profiles: the profiles[] identity block, keyed by profile_id (T451) ------------------
#
# `getRecentMatchHistory` carries a `profiles[]` array alongside `matchHistoryStats` —
# `alias`/`country` per `profile_id` — that `recent_matches` above never reads. FR-007/FR-017 need
# that block to populate a viewed profile's real alias/country on the on-view identity refresh, so
# `recent_profiles` parses the same endpoint's response for it, leaving `recent_matches`'s existing
# callers (`apps/ingester/src/aoe2stats_ingester/discover.py`,
# `apps/ingester/src/aoe2stats_ingester/reconcile.py`,
# `apps/api/src/aoe2stats_api/routers/players.py`) and its `list[RawMatch]` return untouched — an
# additive sibling method rather than a widened `recent_matches` return, per T451.


async def test_recent_profiles_returns_raw_profiles_with_alias_and_country() -> None:
    """The parsed identity result carries `profiles[].alias`/`country` keyed by `profile_id`, from
    the same fixture `recent_matches`'s own tests already use.
    """
    from aoe2stats_providers.base import RawProfile

    body = _load("get_recent_match_history.json")

    provider, recorder = _provider(lambda request: httpx.Response(200, json=body))

    profiles = await provider.recent_profiles([196240])

    assert len(recorder.calls) == 1
    assert recorder.calls[0].status_code == 200
    assert all(isinstance(profile, RawProfile) for profile in profiles)

    by_profile_id = {profile.profile_id: profile for profile in profiles}
    assert by_profile_id[288714].alias == "TAG_Mihai06"
    assert by_profile_id[288714].country == "ro"


async def test_recent_profiles_returns_empty_set_when_profiles_key_is_absent() -> None:
    """A response with no `profiles[]` key yields an empty identity set and never raises — the
    same "absent is ordinary, not malformed" discipline applied to a wire shape this module does
    not yet control (a degraded or older endpoint response), distinct from the entry-level skips
    `recent_matches`/T050a apply once a `profiles[]` entry actually fails to parse.
    """
    provider, recorder = _provider(
        lambda request: httpx.Response(200, json={"matchHistoryStats": [], "result": {}})
    )

    profiles = await provider.recent_profiles([196240])

    assert profiles == []
    assert len(recorder.calls) == 1
    assert recorder.calls[0].status_code == 200
