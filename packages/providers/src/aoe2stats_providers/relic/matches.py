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
"""

from __future__ import annotations

import json
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
        `RawMatch` per source entry, in order — none dropped, none invented.
        """
        matches: list[RawMatch] = []
        for batch in _chunk(profile_ids, MATCH_HISTORY_BATCH_SIZE):
            body = await self._get_recent_match_history({"profile_ids": json.dumps(list(batch))})

            for entry in body.get("matchHistoryStats", []):
                player_profile_ids = tuple(
                    member.get("profile_id") for member in entry.get("matchhistorymember", [])
                )
                started_at = _epoch_seconds_to_datetime(entry.get("startgametime"))
                completed_at = _epoch_seconds_to_datetime(entry.get("completiontime"))
                duration_seconds = (
                    entry.get("completiontime") - entry.get("startgametime")
                    if entry.get("completiontime") is not None
                    and entry.get("startgametime") is not None
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
                matches.append(
                    parse_strict(
                        RawMatch, fields, provider=self._provider, endpoint="getRecentMatchHistory"
                    )
                )
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
