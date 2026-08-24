"""Contract test for `ReplayProvider` (T039) — the `aoe.ms` replay-download adapter.

Ground truth is `specs/001-steam-link-replay-ingestion/contracts/providers.md`'s `ReplayProvider`
table and the endpoint shape measured in `docs/data-sources.md` §2 and `research.md` §5: the
endpoint ignores `Range` and rejects `HEAD` with 405, so every capture is a full in-memory
download; `GET https://aoe.ms/replay/?gameId={gameId}&profileId={profileId}`. Every request in
this file goes through `httpx.MockTransport` — constitution III forbids the network in unit tests,
and `tests/conftest.py` blocks any real socket connection under `PYTEST_DISABLE_NETWORK=1`
regardless.

Written as a test-first task, before `aoe2stats_providers.aoems.provider` exists (T049): every test
below carries `@pytest.mark.xfail(strict=True, ...)`. `strict=True` is what makes that honest — the
moment T049 lands and a test starts passing, `strict=True` turns the *run* red instead of letting a
stale xfail hide it. The import of the not-yet-existent module lives inside `_provider()`, the one
place every test below reaches it through, rather than at module scope: a module-scope
`ModuleNotFoundError` aborts the *entire* workspace suite's collection (`pytest -q` stops on any
collection error, workspace-wide, per `testpaths` in the root `pyproject.toml`), while the same
error raised inside a test body is exactly what `strict=True` xfail is built to expect.

Six behaviours, matching `contracts/providers.md`'s `ReplayProvider` table:

1. `fetch_replay` returns a `ReplayBlob` on 200 — bytes, filename, content type.
2. `fetch_replay` returns (never raises) `NotFound` on 404.
3. `fetch_replay` raises `ProviderRateLimited` on 429, and on an unexpected 403 — aoe.ms documents
   neither, so both are read the same way every other provider reads them (`base.py`'s default
   `treat_403_as_rate_limited=True`).
4. `fetch_replay` raises `ProviderUnavailable` when 5xx exhausts the retry budget, and on a timeout.
5. The provider itself performs **no** three-way reading of a 404. `NotFound` (`base.py`) carries
   only the observed `http_status` and nothing interpretive — no "reason", no age, no verdict — and
   `fetch_replay`'s own signature admits no `completed_at` (or anything else time-based) from which
   one could be derived. The three-way classification (pending / unavailable / expired) is the
   *caller's* job, tested at T047 against `matches.completed_at`, which this provider never sees.
6. (T049a) `fetch_replay` raises `ProviderUnavailable`, carrying the observed status, for any
   status this table does not name — a 400 or a 410, neither ever measured against this endpoint —
   rather than reading it as a 200 and returning a `ReplayBlob` built around whatever bytes the body
   happened to carry. See the bottom of this file and the module docstring of
   `aoems/provider.py` for why this is `ProviderUnavailable`, not `ProviderContractViolation`.

The 200 case is built from the real, byte-for-byte reference replay committed at
`tests/fixtures/replays/AgeIIDE_Replay_500546441.zip` (`tests/fixtures/replays/README.md`) rather
than the withheld body behind `packages/providers/fixtures/aoems/replay_200_meta.json` — that
fixture's real download and this reference replay's real download are two different matches, and
mixing one's headers with the other's bytes would be a fabricated fixture, the exact thing
`fixtures/README.md` refuses to do for this endpoint. The reference replay's own real headers (its
own `README.md`) are used instead, so header and body agree because they were, in fact, one
download. The 404 case uses the real, committed `packages/providers/fixtures/aoems/replay_404.json`
(a genuine 16-byte `text/plain` body), which withholds nothing.
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import pytest

from aoe2stats_providers.base import (
    NotFound,
    ProviderCallRecord,
    ProviderRateLimited,
    ProviderUnavailable,
    ReplayBlob,
    RetryPolicy,
    TokenBucket,
)

if TYPE_CHECKING:
    # Type-checking only: mypy needs the name, but nothing here may import the module at
    # collection time — see `_provider()` below, where the real (runtime) import lives.
    from aoe2stats_providers.aoems.provider import AoemsReplayProvider

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "aoems"
REPLAY_ZIP = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "replays"
    / "AgeIIDE_Replay_500546441.zip"
)

# The reference replay's own real download parameters, from `tests/fixtures/replays/README.md`:
# "downloaded from https://aoe.ms/replay/?gameId=500546441&profileId=196240" — header and body
# agree because they were, in fact, one real download.
REFERENCE_GAME_ID = 500546441
REFERENCE_PROFILE_ID = 196240
REFERENCE_FILENAME = "AgeIIDE_Replay_500546441.zip"

# Fast enough that the retry-exhaustion test does not spend real seconds asleep, while still
# exercising the same backoff machinery every other provider's tests use (test_provider_base.py).
FAST_RETRY = RetryPolicy(
    max_attempts=3, base_delay_seconds=0.001, max_delay_seconds=0.002, jitter_seconds=0.0
)


def _load_404_fixture() -> dict[str, Any]:
    return json.loads((FIXTURES / "replay_404.json").read_text(encoding="utf-8"))


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
    retry_policy: RetryPolicy = FAST_RETRY,
) -> tuple[AoemsReplayProvider, _Recorder]:
    """Imports `AoemsReplayProvider` here, at call time, rather than at module scope: this is the
    one place every test below reaches the not-yet-existent T049 module through, so this is where
    the resulting `ModuleNotFoundError` is meant to surface — inside the test call, where
    `strict=True` xfail turns it into an expected failure, not during collection, where it would
    abort the whole workspace suite.
    """
    from aoe2stats_providers.aoems.provider import AoemsReplayProvider

    recorder = recorder or _Recorder()
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = AoemsReplayProvider(
        client=client,
        timeout_seconds=5.0,
        rate_limiter=TokenBucket(rate_per_second),
        call_sink=recorder.async_sink,
        retry_policy=retry_policy,
    )
    return provider, recorder


# --- fetch_replay: 200 -> ReplayBlob -------------------------------------------------------------


async def test_fetch_replay_returns_a_replay_blob_on_200() -> None:
    content = REPLAY_ZIP.read_bytes()
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        seen["url"] = str(request.url)
        return httpx.Response(
            200,
            content=content,
            headers={
                "content-type": "application/zip",
                "content-disposition": (
                    f"attachment; filename={REFERENCE_FILENAME}; "
                    f"filename*=UTF-8''{REFERENCE_FILENAME}"
                ),
            },
        )

    provider, recorder = _provider(handler)

    blob = await provider.fetch_replay(REFERENCE_GAME_ID, REFERENCE_PROFILE_ID)

    assert isinstance(blob, ReplayBlob)
    assert blob.content == content
    assert blob.filename == REFERENCE_FILENAME
    assert blob.content_type == "application/zip"
    assert "aoe.ms" in seen["url"]
    assert seen["params"]["gameId"] == str(REFERENCE_GAME_ID)
    assert seen["params"]["profileId"] == str(REFERENCE_PROFILE_ID)
    assert len(recorder.calls) == 1
    assert recorder.calls[0].status_code == 200
    assert not recorder.calls[0].rate_limited


# --- fetch_replay: 404 -> NotFound, returned rather than raised, and un-classified ----------------


async def test_fetch_replay_returns_not_found_on_404_without_raising() -> None:
    fixture = _load_404_fixture()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            content=fixture["body"].encode("utf-8"),
            headers={"content-type": fixture["content_type"]},
        )

    provider, recorder = _provider(handler)

    # A 404 is an ordinary, returned outcome — never an exception. Any exception here fails the
    # test outright rather than being caught, which is the point: this is not `pytest.raises`.
    result = await provider.fetch_replay(fixture["game_id"], fixture["profile_id"])

    assert isinstance(result, NotFound)
    assert result.http_status == 404
    assert len(recorder.calls) == 1
    assert recorder.calls[0].status_code == 404
    assert not recorder.calls[0].rate_limited


async def test_not_found_carries_no_reason_and_the_signature_admits_no_completed_at() -> None:
    """The three-way reading (pending / unavailable / expired) is the *caller's*, tested at T047 —
    this provider must not be able to perform it even by accident. Two structural guarantees:

    - `NotFound` (`base.py`) has exactly one field, the observed `http_status` — no reason, no
      verdict, nothing interpretive added on the way out of this module.
    - `fetch_replay`'s own signature takes only `game_id` and `profile_id` — no `completed_at` and
      nothing else a three-way classification could be derived from. A provider that accepted one
      even unused would be a temptation the caller does not need and the contract does not grant.
    """
    fixture = _load_404_fixture()
    provider, _ = _provider(
        lambda request: httpx.Response(
            404, content=fixture["body"].encode("utf-8"), headers={"content-type": "text/plain"}
        )
    )

    result = await provider.fetch_replay(fixture["game_id"], fixture["profile_id"])

    assert isinstance(result, NotFound)
    assert set(NotFound.model_fields) == {"http_status"}

    parameters = inspect.signature(provider.fetch_replay).parameters
    assert set(parameters) == {"game_id", "profile_id"}
    assert "completed_at" not in parameters


# --- fetch_replay: 429 and an unexpected 403 both raise ProviderRateLimited -----------------------


async def test_fetch_replay_raises_provider_rate_limited_on_429() -> None:
    recorder = _Recorder()
    provider, _ = _provider(lambda request: httpx.Response(429), recorder=recorder)

    with pytest.raises(ProviderRateLimited) as excinfo:
        await provider.fetch_replay(REFERENCE_GAME_ID, REFERENCE_PROFILE_ID)

    assert excinfo.value.status_code == 429
    assert len(recorder.calls) == 1
    assert recorder.calls[0].rate_limited


async def test_fetch_replay_raises_provider_rate_limited_on_an_unexpected_403() -> None:
    recorder = _Recorder()
    provider, _ = _provider(lambda request: httpx.Response(403), recorder=recorder)

    with pytest.raises(ProviderRateLimited) as excinfo:
        await provider.fetch_replay(REFERENCE_GAME_ID, REFERENCE_PROFILE_ID)

    assert excinfo.value.status_code == 403
    assert len(recorder.calls) == 1
    assert recorder.calls[0].rate_limited


# --- fetch_replay: 5xx exhausting retries and a timeout both raise ProviderUnavailable ------------


async def test_fetch_replay_raises_provider_unavailable_on_5xx() -> None:
    recorder = _Recorder()
    provider, _ = _provider(lambda request: httpx.Response(503), recorder=recorder)

    with pytest.raises(ProviderUnavailable):
        await provider.fetch_replay(REFERENCE_GAME_ID, REFERENCE_PROFILE_ID)

    # One `provider_calls` row per attempt, all with the observed 503 — the wire answered every
    # time, it just never answered successfully.
    assert len(recorder.calls) == FAST_RETRY.max_attempts
    assert all(call.status_code == 503 for call in recorder.calls)


async def test_fetch_replay_raises_provider_unavailable_on_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("no reply", request=request)

    recorder = _Recorder()
    provider, _ = _provider(handler, recorder=recorder)

    with pytest.raises(ProviderUnavailable):
        await provider.fetch_replay(REFERENCE_GAME_ID, REFERENCE_PROFILE_ID)

    assert len(recorder.calls) == FAST_RETRY.max_attempts
    assert all(call.status_code is None for call in recorder.calls)


# --- fetch_replay: an unnamed status (T049a) raises ProviderUnavailable, never a ReplayBlob -------
#
# `contracts/providers.md`'s `ReplayProvider` table names exactly five outcomes: 200, 404, 429, an
# unexpected 403, and 5xx/timeout. `AsyncBaseProvider._request` (`base.py`) only classifies 429/403
# and 5xx/timeout — everything else, including a 400 or a 410 neither `docs/data-sources.md` §2 nor
# the contract has ever observed this endpoint send, reaches `fetch_replay` untouched. Before T049a
# the `if 404 / else blob` shape below read any such status as a 200 and returned a `ReplayBlob`
# built around whatever bytes the error body happened to carry — which `_process_one`
# (`apps/ingester/.../capture.py`) would then upload to R2 under the real `replay_object_key` and
# quarantine permanently, forfeiting a replay a later cycle could still have fetched. These two
# statuses are not retried by `RetryPolicy` (unlike 5xx), so a plain `httpx.Response(400)` handler
# is enough — no retry-exhaustion loop needed, unlike the 5xx test above.


async def test_fetch_replay_raises_provider_unavailable_on_an_unnamed_400() -> None:
    recorder = _Recorder()
    provider, _ = _provider(lambda request: httpx.Response(400), recorder=recorder)

    with pytest.raises(ProviderUnavailable) as excinfo:
        await provider.fetch_replay(REFERENCE_GAME_ID, REFERENCE_PROFILE_ID)

    assert excinfo.value.status_code == 400
    assert len(recorder.calls) == 1
    assert recorder.calls[0].status_code == 400
    assert not recorder.calls[0].rate_limited


async def test_fetch_replay_raises_provider_unavailable_on_an_unnamed_410() -> None:
    recorder = _Recorder()
    provider, _ = _provider(lambda request: httpx.Response(410), recorder=recorder)

    with pytest.raises(ProviderUnavailable) as excinfo:
        await provider.fetch_replay(REFERENCE_GAME_ID, REFERENCE_PROFILE_ID)

    assert excinfo.value.status_code == 410
    assert len(recorder.calls) == 1
    assert recorder.calls[0].status_code == 410
    assert not recorder.calls[0].rate_limited
