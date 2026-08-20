"""`ProfileProvider` (T027) against Relic's `getPersonalStat` — resolving a Steam identity to its
AoE2 profile, and reading current standing per leaderboard.

Ground truth for the wire shape is `docs/data-sources.md` §1 and the `aoe2-data-sources` skill;
this module is about turning that shape into `contracts/providers.md`'s `ProfileProvider`.

Ratings are re-queryable at any time (`docs/data-sources.md`, "Recoverable or not"), so — unlike
`MatchHistoryProvider` (T050) and `ReplayProvider` (T049) — nothing here is persisted verbatim per
FR-012: a second copy of something still available is a second thing to keep honest, for no gain.

Two Relic response quirks drive the parsing below:

- A resolved Steam id has `result.code == 0`; an unregistered one answers `result.code == 3`
  (`UNREGISTERED_PROFILE_NAME`) with an ordinary `200` and no `statGroups` — an outcome, not an
  error (FR-003), so `resolve_profile` returns `None` rather than raising.
- `leaderboardStats` entries carry a `statgroup_id`, not a `profile_id`; the mapping from one to the
  other lives in `statGroups[].members[].profile_id`. Every entry is re-keyed onto the real
  `profile_id` before it is validated into a `LeaderboardSnapshot`.

Every field pulled out of a raw dict is re-validated through `parse_strict` against a `StrictModel`
(`ProfileRef` or `LeaderboardSnapshot`) before it leaves this module: a field of an unexpected type
becomes a `ProviderContractViolation`, never a silently coerced value.
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
    LeaderboardSnapshot,
    ProfileRef,
    RetryPolicy,
    TokenBucket,
    parse_strict,
)

RELIC_BASE_URL = "https://aoe-api.worldsedgelink.com/community/leaderboard"

# contracts/providers.md `ProfileProvider`: "personal_stats accepts up to 50 profiles per call".
PERSONAL_STATS_BATCH_SIZE = 50


def _chunk(items: Sequence[int], size: int) -> Iterator[Sequence[int]]:
    """Split `items` into consecutive slices of at most `size`, preserving order."""
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _epoch_seconds_to_datetime(value: Any) -> datetime | None:
    """Relic's `lastmatchdate` is Unix seconds. `None` stays `None` rather than becoming epoch 0,
    which would be a coercion of an absent value into a false one.
    """
    if value is None:
        return None
    return datetime.fromtimestamp(int(value), tz=UTC)


class RelicProfileProvider(AsyncBaseProvider):
    """`ProfileProvider` (contracts/providers.md) against Relic's `getPersonalStat`."""

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

    async def resolve_profile(self, steam_id64: str) -> ProfileRef | None:
        """`ProfileProvider.resolve_profile`. Returns `None` — an ordinary outcome, never an
        exception (FR-003) — for a Steam account with no AoE2 profile.
        """
        steam_name = f"/steam/{steam_id64}"
        body = await self._get_personal_stat({"profile_names": json.dumps([steam_name])})

        result = body.get("result")
        if not isinstance(result, dict) or result.get("code") != 0:
            return None

        for group in body.get("statGroups", []):
            for member in group.get("members", []):
                if member.get("name") != steam_name:
                    continue
                fields = {
                    "profile_id": member.get("profile_id"),
                    "alias": member.get("alias"),
                    "country": member.get("country"),
                }
                return parse_strict(
                    ProfileRef, fields, provider=self._provider, endpoint="getPersonalStat"
                )
        return None

    async def personal_stats(self, profile_ids: Sequence[int]) -> list[LeaderboardSnapshot]:
        """`ProfileProvider.personal_stats`. Splits more than `PERSONAL_STATS_BATCH_SIZE` profiles
        across multiple calls rather than sending one oversized request.
        """
        snapshots: list[LeaderboardSnapshot] = []
        for batch in _chunk(profile_ids, PERSONAL_STATS_BATCH_SIZE):
            body = await self._get_personal_stat({"profile_ids": json.dumps(list(batch))})

            profile_id_by_statgroup = {
                group.get("id"): member.get("profile_id")
                for group in body.get("statGroups", [])
                for member in group.get("members", [])
            }

            for entry in body.get("leaderboardStats", []):
                profile_id = profile_id_by_statgroup.get(entry.get("statgroup_id"))
                if profile_id is None:
                    # No member in this response claims the stat group — nothing to attach the
                    # snapshot to. Not observed in practice; skipped rather than guessed at.
                    continue
                fields = {
                    "profile_id": profile_id,
                    "leaderboard_id": entry.get("leaderboard_id"),
                    "rating": entry.get("rating"),
                    "rank": entry.get("rank"),
                    "wins": entry.get("wins"),
                    "losses": entry.get("losses"),
                    "streak": entry.get("streak"),
                    "highest_rating": entry.get("highestrating"),
                    "last_match_at": _epoch_seconds_to_datetime(entry.get("lastmatchdate")),
                }
                snapshots.append(
                    parse_strict(
                        LeaderboardSnapshot,
                        fields,
                        provider=self._provider,
                        endpoint="getPersonalStat",
                    )
                )
        return snapshots

    async def _get_personal_stat(self, extra_params: Mapping[str, Any]) -> dict[str, Any]:
        response = await self._request(
            "GET",
            f"{self._base_url}/getPersonalStat",
            endpoint="getPersonalStat",
            params={"title": "age2", **extra_params},
        )
        result: dict[str, Any] = response.json()
        return result
