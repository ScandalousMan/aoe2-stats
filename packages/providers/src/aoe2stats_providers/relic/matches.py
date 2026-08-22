"""`MatchHistoryProvider` (T050) against Relic's `getRecentMatchHistory` — match discovery.

Ground truth for the wire shape is `docs/data-sources.md` §1 and the `aoe2-data-sources` skill;
this module turns that shape into `contracts/providers.md`'s `MatchHistoryProvider`.

Unlike `RelicProfileProvider` (T027), whose ratings are re-queryable at any time, a match leaves
the "recent" window and can never be fetched back (`docs/data-sources.md`, "Recoverable or not").
So every source entry's `raw_payload` is carried through to the caller byte-for-byte, alongside the
parsed fields `contracts/providers.md` and FR-012 require — the caller is the one that persists it
verbatim into `matches.raw_payload`; this module never writes to storage itself
(`aoe2stats_providers.base`'s module docstring: a `DataProvider` never persists a raw response).

One request quirk drives the batching below: `contracts/providers.md` — "Batched, up to 10 profiles
per call — the response is roughly 400 KB per profile." More than `MATCH_HISTORY_BATCH_SIZE`
profiles are split across multiple calls rather than sent as one oversized request, matching
`RelicProfileProvider.personal_stats`'s `_chunk` pattern for the same reason.

Every field pulled out of a raw dict is re-validated through `parse_strict` against `RawMatch`
(a `StrictModel`) before it leaves this module: a field of an unexpected type becomes a
`ProviderContractViolation`, never a silently coerced value.

T050a: one bad entry does not cost the batch. `recent_matches` used to call `parse_strict` inside a
bare loop, so a single entry that failed validation raised out of the provider and took discovery,
reconciliation and the drain down with it, once per cycle, for as long as the offending match stayed
in the "recent" window. Two conditions are now contained to the one entry that triggers them, and
each leaves a `provider_calls` row of its own (via the existing `call_sink`) so a batch that skipped
entries is distinguishable from one that had none — "countable rather than silent":

- an **unfinished match** — Relic's *recent* match history reports games that have not finished yet
  two ways: `completiontime` absent, which `_epoch_seconds_to_datetime` maps to `None`, and
  `completiontime: 0`, which does not — `_epoch_seconds_to_datetime(0)` is the Unix epoch, a real
  `datetime`, and would otherwise sail through `parse_strict` as a perfectly valid `RawMatch` with
  `completed_at = 1970-01-01`. That is silent rather than loud: `capture_deadline_at` is derived
  from it (`capture_deadline_at = completed_at + CAPTURE_BUDGET_DAYS`, T053), the fabricated 1970
  deadline sorts first in every claim order ahead of every real capture, and reads as expired
  decades early — a false severity-1 `expired_capture` alert for a match still being played. Both
  shapes are read the same way: with no genuine `completed_at`, the match can carry no
  `capture_deadline_at` either, is not yet capturable, and belongs in neither `matches` nor
  `replay_captures`. This is checked *before* `parse_strict` runs, deliberately, so it reads as
  the ordinary and expected condition it is, not as an accidental contract violation the parser
  happens to catch.
- a **malformed entry** — any other field that fails `RawMatch`'s strict validation. Caught the same
  way `CompanionEnrichmentProvider._parse_matches` already does it
  (`except ProviderContractViolation: continue`), applied here to the provider that can least afford
  a bare loop.

Both skips are recorded as their own `provider_calls` row rather than folded into a new field on
`ProviderCallRecord`/`provider_calls`: that shape is shared across every provider
(`aoe2stats_providers.base`, `packages/storage`) and widening it for one provider's skip counter
is out of this module's reach. The synthetic row's `endpoint` carries a `#skipped_...` suffix
instead of the real endpoint name, and `status_code=None`/`rate_limited=False` mark it as
something other than an HTTP response — an operator reading `provider_calls` for `relic` can tell
"no calls succeeded" from "calls succeeded but kept rejecting entries" apart.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import httpx

from aoe2stats_providers.base import (
    AsyncBaseProvider,
    AsyncProviderCallSink,
    ProviderContractViolation,
    RawMatch,
    RetryPolicy,
    TokenBucket,
    parse_strict,
)

RELIC_BASE_URL = "https://aoe-api.worldsedgelink.com/community/leaderboard"

# contracts/providers.md `MatchHistoryProvider`: "Batched, up to 10 profiles per call — the
# response is roughly 400 KB per profile."
MATCH_HISTORY_BATCH_SIZE = 10

# T050a: synthetic `provider_calls.endpoint` values for a skipped entry — see the module docstring
# for why a suffixed endpoint, rather than a new field, is what makes a skip countable here.
_SKIPPED_UNFINISHED_MATCH_ENDPOINT = "getRecentMatchHistory#skipped_unfinished_match"
_SKIPPED_MALFORMED_ENTRY_ENDPOINT = "getRecentMatchHistory#skipped_malformed_entry"


def _chunk(items: Sequence[int], size: int) -> Iterator[Sequence[int]]:
    """Split `items` into consecutive slices of at most `size`, preserving order."""
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _epoch_seconds_to_datetime(value: Any) -> datetime | None:
    """Relic's `startgametime`/`completiontime` are Unix seconds. `None` stays `None` rather than
    becoming epoch 0, which would be a coercion of an absent value into a false one.
    """
    if value is None:
        return None
    return datetime.fromtimestamp(int(value), tz=UTC)


def _completed_at(entry: Mapping[str, Any]) -> datetime | None:
    """The entry's `completed_at`, or `None` if the match has not finished.

    Relic represents an in-progress match two ways in `completiontime`, and both must read as
    "not finished": absent, which `_epoch_seconds_to_datetime` already maps to `None`, and `0`,
    which it does not — `_epoch_seconds_to_datetime(0)` is a real `datetime` (the Unix epoch), not
    a sentinel, so a caller that only checked "is it `None`" would silently accept it as a genuine
    completion (see the module docstring's "unfinished match" bullet for why that is worse than a
    raised `ProviderContractViolation`). A non-positive `completiontime` is therefore read exactly
    like a `None` one, here, before it ever reaches `_epoch_seconds_to_datetime`.

    `startgametime` is not given the same treatment: nothing downstream derives a deadline from
    it, `completed_at` is (module docstring: "`completed_at` is the one that is load-bearing"), so
    it keeps going through `_epoch_seconds_to_datetime` directly.
    """
    value = entry.get("completiontime")
    if value is None or (isinstance(value, int | float) and value <= 0):
        return None
    return _epoch_seconds_to_datetime(value)


class RelicMatchHistoryProvider(AsyncBaseProvider):
    """`MatchHistoryProvider` (contracts/providers.md) against Relic's `getRecentMatchHistory`."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        timeout_seconds: float,
        rate_limiter: TokenBucket,
        call_sink: AsyncProviderCallSink | None = None,
        retry_policy: RetryPolicy | None = None,
        base_url: str = RELIC_BASE_URL,
    ) -> None:
        super().__init__(
            provider="relic",
            client=client,
            timeout_seconds=timeout_seconds,
            rate_limiter=rate_limiter,
            call_sink=call_sink,
            retry_policy=retry_policy,
        )
        self._base_url = base_url

    async def recent_matches(self, profile_ids: Sequence[int]) -> list[RawMatch]:
        """`MatchHistoryProvider.recent_matches`. Splits more than `MATCH_HISTORY_BATCH_SIZE`
        profiles across multiple calls rather than sending one oversized request. Returns one
        `RawMatch` per source entry that is both finished and well-formed — an in-progress match
        or a malformed entry (T050a) is skipped rather than aborting the whole batch, so nothing
        valid is dropped and nothing is invented, but the entry count is not a guarantee.
        """
        matches: list[RawMatch] = []
        for batch in _chunk(profile_ids, MATCH_HISTORY_BATCH_SIZE):
            body = await self._get_recent_match_history({"profile_ids": json.dumps(list(batch))})

            for entry in body.get("matchHistoryStats", []):
                completed_at = _completed_at(entry)
                if completed_at is None:
                    # T050a: an unfinished match (module docstring) — expected traffic, not
                    # malformed data. Checked ahead of `parse_strict` so it never reaches, and is
                    # never counted as, a contract violation.
                    await self._record(
                        _SKIPPED_UNFINISHED_MATCH_ENDPOINT,
                        None,
                        time.monotonic(),
                        rate_limited=False,
                    )
                    continue

                player_profile_ids = tuple(
                    member.get("profile_id") for member in entry.get("matchhistorymember", [])
                )
                started_at = _epoch_seconds_to_datetime(entry.get("startgametime"))
                duration_seconds = (
                    entry.get("completiontime") - entry.get("startgametime")
                    if entry.get("startgametime") is not None
                    else None
                )
                fields = {
                    "game_id": entry.get("id"),
                    "leaderboard_id": entry.get("matchtype_id"),
                    "map_name": entry.get("mapname"),
                    "patch": entry.get("patch"),
                    "started_at": started_at,
                    "completed_at": completed_at,
                    "duration_seconds": duration_seconds,
                    "player_profile_ids": player_profile_ids,
                    "raw_payload": entry,
                }
                try:
                    matches.append(
                        parse_strict(
                            RawMatch,
                            fields,
                            provider=self._provider,
                            endpoint="getRecentMatchHistory",
                        )
                    )
                except ProviderContractViolation:
                    # T050a: one malformed entry does not throw away the rest of the batch — the
                    # same shape as `CompanionEnrichmentProvider._parse_matches`, applied to the
                    # provider that can least afford a bare loop (module docstring).
                    await self._record(
                        _SKIPPED_MALFORMED_ENTRY_ENDPOINT,
                        None,
                        time.monotonic(),
                        rate_limited=False,
                    )
                    continue
        return matches

    async def _get_recent_match_history(self, extra_params: Mapping[str, Any]) -> dict[str, Any]:
        response = await self._request(
            "GET",
            f"{self._base_url}/getRecentMatchHistory",
            endpoint="getRecentMatchHistory",
            params={"title": "age2", **extra_params},
        )
        # A non-JSON body is a fourth way this endpoint can fail, alongside the status-code-driven
        # `ProviderUnavailable`/`ProviderRateLimited` `_request` already raises: `response.json()`
        # otherwise leaks a bare `json.JSONDecodeError`, a shape no caller of a `DataProvider` is
        # contracted to expect (T029b — every failure this class can produce is a `ProviderError`).
        try:
            result: dict[str, Any] = response.json()
        except ValueError as exc:
            raise ProviderContractViolation(
                f"{self._provider} returned a non-JSON body from getRecentMatchHistory",
                provider=self._provider,
                endpoint="getRecentMatchHistory",
            ) from exc
        return result
