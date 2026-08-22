"""`ReplayProvider` (T049) against `aoe.ms` — the replay-download adapter.

Ground truth is `docs/data-sources.md` §2 and `contracts/providers.md`'s `ReplayProvider` table:

```
GET https://aoe.ms/replay/?gameId={gameId}&profileId={profileId}
```

The endpoint rejects `HEAD` with `405` and ignores `Range`, so there is no cheap existence probe
and no partial download — every capture is a full, in-memory `GET`. `AsyncBaseProvider._request`
(`base.py`) already buffers the whole body by default (no `stream=True`), which is exactly what
that shape needs: nothing here reads the response incrementally.

A 200 carries the zip in the body and the filename in `content-disposition`
(`attachment; filename={name}; filename*=UTF-8''{name}`) — the plain `filename=` parameter is used
rather than the RFC 5987 `filename*=` one because the two agree here and the plain form needs no
percent-decoding. A 404 is `text/plain`, 16 bytes, and carries no information beyond "not found":
this provider does not know, and must not guess, why. `fetch_replay`'s signature takes only
`game_id` and `profile_id` for exactly that reason — there is no `completed_at` here from which a
three-way reading (pending / unavailable / expired) could be derived even by accident. That
reading is the caller's, against `matches.completed_at` (T056).

429 and an unexpected 403 both raise `ProviderRateLimited`; 5xx exhausting the retry budget and a
timeout both raise `ProviderUnavailable` — both already `AsyncBaseProvider._request`'s job, shared
with every other provider (`base.py`'s `treat_403_as_rate_limited=True` default is used as-is: this
endpoint documents neither 429 nor 403, so both are read the same way every other provider reads
them).
"""

from __future__ import annotations

import re

import httpx

from aoe2stats_providers.base import (
    AsyncBaseProvider,
    AsyncProviderCallSink,
    NotFound,
    ReplayBlob,
    RetryPolicy,
    TokenBucket,
)

AOEMS_BASE_URL = "https://aoe.ms/replay/"

_ENDPOINT = "replay"

# The plain `filename=` parameter, never the RFC 5987 `filename*=` one — see the module docstring.
# `(?!\*)` after `filename` is what keeps this from matching `filename*=` instead: without it,
# `re.search` on `'...filename=a.zip; filename*=UTF-8...'` would still find the first `filename=`
# correctly, but a header ordered the other way around would not.
_FILENAME_PATTERN = re.compile(r'filename(?!\*)\s*=\s*"?([^";]+)"?')

_DEFAULT_CONTENT_TYPE = "application/zip"


def _parse_filename(content_disposition: str | None, *, game_id: int) -> str:
    """The reference-replay naming convention (`docs/data-sources.md` §2:
    `attachment; filename=AgeIIDE_Replay_{gameId}.zip`) is the fallback for the one case the wire
    contract does not actually promise a header for — every observed response carries one, but
    nothing here should raise over a missing `content-disposition` when the bytes themselves are
    fine.
    """
    if content_disposition is not None:
        match = _FILENAME_PATTERN.search(content_disposition)
        if match is not None:
            return match.group(1)
    return f"AgeIIDE_Replay_{game_id}.zip"


class AoemsReplayProvider(AsyncBaseProvider):
    """`ReplayProvider` (`contracts/providers.md`) against `aoe.ms`."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        timeout_seconds: float,
        rate_limiter: TokenBucket,
        call_sink: AsyncProviderCallSink | None = None,
        retry_policy: RetryPolicy | None = None,
        base_url: str = AOEMS_BASE_URL,
    ) -> None:
        super().__init__(
            provider="aoems",
            client=client,
            timeout_seconds=timeout_seconds,
            rate_limiter=rate_limiter,
            call_sink=call_sink,
            retry_policy=retry_policy,
        )
        self._base_url = base_url

    async def fetch_replay(self, game_id: int, profile_id: int) -> ReplayBlob | NotFound:
        """A 200 becomes a `ReplayBlob`; a 404 is returned as `NotFound`, never raised, and
        carries no reading of what it means (see the module docstring). `_request` already raises
        `ProviderRateLimited` on 429/403 and `ProviderUnavailable` on 5xx/timeout, so neither is
        handled here.
        """
        response = await self._request(
            "GET",
            self._base_url,
            endpoint=_ENDPOINT,
            params={"gameId": game_id, "profileId": profile_id},
        )

        if response.status_code == 404:
            return NotFound(http_status=response.status_code)

        return ReplayBlob(
            content=response.content,
            filename=_parse_filename(response.headers.get("content-disposition"), game_id=game_id),
            content_type=response.headers.get("content-type", _DEFAULT_CONTENT_TYPE),
        )
