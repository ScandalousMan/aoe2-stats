"""Integration test for quickstart scenario 7 (T047): the three-way reading of a `NotFound` from
`matches.completed_at`, the bounded-retry `failed` path, and the run-stopping treatment of
`ProviderRateLimited` — FR-019, FR-020, FR-021.

Targets `aoe2stats_ingester.capture`. T056 (the three-way 404 reading) landed the four scenarios
above the backoff one — the three `NotFound` branches (young match stays `pending`; past the
grace but short of the two-attempt floor stays `pending`, then `unavailable`; past
`capture_deadline_at` is `expired` and alerts) and the pre-existing 429 scenario, which needed no
new classification but did need the row a rate limit interrupts mid-claim to be handed back
unattempted rather than left stranded. Only the last scenario below, three
consecutive 5xx producing backoff then a terminal `failed`, is T057's own bounded-retry ceiling and
stays `xfail(strict=True, reason="T057 not implemented yet")` until that task lands; it is the one
test in this module still importing `aoe2stats_ingester.capture` inside its own body rather than at
module scope, for exactly the reason every test here originally did — a missing name a whole-module
import would turn into a collection error taking every other test in this file down with it. Every
other import below (`aoe2stats_storage`, `aoe2stats_providers`, `aoe2stats_ingester.budget`) is
safe at module scope regardless.

**The interface this test assumes of `capture.py`**: a `CaptureStage` (matching the `Stage`
protocol `run.py` already defines — `name: str` plus
`async def __call__(self, budget: Budget) -> Mapping[str, Any]`), constructed with the same
`session_factory` every other Phase 4 stage reaches its own database through (per
`apps/ingester/tests/conftest.py`'s module docstring), a `ReplayProvider`, the publication grace
in hours, and the bounded-retry ceiling. It owns its own claim-fetch-classify-persist cycle end to
end, including writing whatever `alerts` rows result — this test only ever reads the outcome back
from `replay_captures` and `alerts`, never how `CaptureStage` got there, so it does not assume
anything about how the stage obtains an `AlertSink` internally.

Every scenario below only ever reaches the `NotFound` / `ProviderRateLimited` /
`ProviderUnavailable` branches of `ReplayProvider.fetch_replay` (`contracts/providers.md`) — never
the `ReplayBlob` (200) one — so nothing here needs an object store: T047a covers the quarantine
path that does.

**Why three hours / four days / forty days, and not values nearer the real thresholds**: this test
deliberately avoids asserting which exact number decides "past the retention window" — nothing in
`data-model.md` or `.env.example` names that value; only `CAPTURE_BUDGET_DAYS` (21, the internal
deadline) and the measured ~31-day source retention exist, and T056 is free to compare against
either. Forty days safely exceeds both, four days safely exceeds `REPLAY_PUBLICATION_GRACE_HOURS`
(72 h) while staying under either 21 or 31, and three hours stays under all three — so every
assertion below holds regardless of which of those two candidate thresholds T056 picks.

**Why the 429 scenario scripts *both* captures to raise `ProviderRateLimited`**: which of two
pending rows a real claim query (`FOR UPDATE SKIP LOCKED ... ORDER BY capture_deadline_at ASC`,
T055) picks first is not this test's concern (T044 covers claim ordering) — scripting only one of
them would make the assertion depend on an ordering this test has no business asserting. Whichever
row is claimed first raises; the point under test is that the *other* row is never even attempted.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_ingester.budget import Budget
from aoe2stats_providers.base import (
    NotFound,
    ProviderError,
    ProviderRateLimited,
    ProviderUnavailable,
    ReplayBlob,
)
from aoe2stats_storage.models import (
    Alert as AlertModel,
)
from aoe2stats_storage.models import (
    AlertKind,
    AoeProfile,
    CaptureSource,
    CaptureStatus,
    Match,
    ReplayCapture,
)

#: `CAPTURE_BUDGET_DAYS` from `.env.example` — used here only to satisfy `replay_captures
#: .capture_deadline_at`'s NOT NULL constraint when seeding rows directly (this test bypasses
#: `discover.py`, which is what normally computes this column). Not a claim about which threshold
#: T056 uses to decide `expired` — see the module docstring.
_CAPTURE_BUDGET_DAYS = 21

#: `REPLAY_PUBLICATION_GRACE_HOURS` from `.env.example`.
_GRACE_HOURS = 72

#: The bounded-retry ceiling this test hands to `CaptureStage`, chosen to match "three 500s ...
#: failed at the attempt limit" exactly: the third `ProviderUnavailable` is the one that trips it.
_MAX_ATTEMPTS = 3


class ScriptedReplayProvider:
    """A `ReplayProvider` (`contracts/providers.md`) whose response is scripted per
    `(game_id, profile_id)`, one entry consumed per call, in order.

    A `NotFound` or `ReplayBlob` value is returned; a `ProviderRateLimited` or
    `ProviderUnavailable` *instance* is raised instead of returned — mirroring exactly how the real
    provider reports each (`fetch_replay` never returns an exception, only raises one). `.calls`
    records every `(game_id, profile_id)` actually asked for, in order, so a test can assert a row
    was never touched.
    """

    def __init__(
        self, script: Mapping[tuple[int, int], Sequence[NotFound | ReplayBlob | ProviderError]]
    ):
        self._queues = {key: list(responses) for key, responses in script.items()}
        self.calls: list[tuple[int, int]] = []

    async def fetch_replay(self, game_id: int, profile_id: int) -> ReplayBlob | NotFound:
        key = (game_id, profile_id)
        self.calls.append(key)
        outcome = self._queues[key].pop(0)
        if isinstance(outcome, ProviderError):
            raise outcome
        return outcome


async def _seed_capture(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    game_id: int,
    profile_id: int,
    completed_at: datetime,
) -> uuid.UUID:
    """Insert the `aoe_profiles`, `matches` and `replay_captures` rows one capture needs, committed
    through `session_factory` directly (never the `db_session` fixture: `CaptureStage` reaches the
    database through its own session from the same `session_factory`, and an uncommitted row on a
    different connection would simply not exist as far as Postgres is concerned)."""
    capture_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(AoeProfile(profile_id=profile_id, alias=f"player-{profile_id}"))
        session.add(
            Match(
                game_id=game_id,
                leaderboard_id=3,
                completed_at=completed_at,
                source="test-fixture",
                raw_payload={},
            )
        )
        await session.flush()
        session.add(
            ReplayCapture(
                id=capture_id,
                game_id=game_id,
                profile_id=profile_id,
                capture_deadline_at=completed_at + timedelta(days=_CAPTURE_BUDGET_DAYS),
                source=CaptureSource.AUTOMATIC,
            )
        )
        await session.commit()
    return capture_id


async def _get_capture(
    session_factory: async_sessionmaker[AsyncSession], capture_id: uuid.UUID
) -> ReplayCapture:
    async with session_factory() as session:
        capture = await session.get(ReplayCapture, capture_id)
        assert capture is not None
        return capture


async def _get_alerts(session_factory: async_sessionmaker[AsyncSession]) -> list[AlertModel]:
    async with session_factory() as session:
        result = await session.execute(select(AlertModel))
        return list(result.scalars())


async def _make_claimable_again(
    session_factory: async_sessionmaker[AsyncSession], capture_id: uuid.UUID
) -> None:
    """Simulate a later cycle without waiting out the real backoff: push `next_attempt_at` into
    the past so the row is claimable again on the next call to the stage.

    Deliberately independent of whatever backoff formula T057 picks — this test only needs "enough
    time has passed", not any particular delay, so it reaches straight into the row rather than
    guessing a clock-injection seam `CaptureStage` may or may not expose.
    """
    async with session_factory() as session:
        capture = await session.get(ReplayCapture, capture_id)
        assert capture is not None
        capture.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()


def _budget() -> Budget:
    return Budget(seconds=30)


async def test_404_on_a_very_recent_match_stays_pending_and_raises_nothing(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    from aoe2stats_ingester.capture import CaptureStage

    game_id, profile_id = 900_001, 1
    capture_id = await _seed_capture(
        session_factory,
        game_id=game_id,
        profile_id=profile_id,
        completed_at=datetime.now(UTC) - timedelta(hours=3),
    )
    provider = ScriptedReplayProvider({(game_id, profile_id): [NotFound()]})
    stage = CaptureStage(
        session_factory=session_factory,
        replay_provider=provider,
        replay_publication_grace_hours=_GRACE_HOURS,
        max_attempts=_MAX_ATTEMPTS,
    )

    await stage(_budget())

    capture = await _get_capture(session_factory, capture_id)
    assert capture.status == CaptureStatus.PENDING
    assert capture.attempts == 1
    assert provider.calls == [(game_id, profile_id)]
    assert await _get_alerts(session_factory) == []


async def test_404_past_the_grace_needs_two_attempts_before_unavailable(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    from aoe2stats_ingester.capture import CaptureStage

    game_id, profile_id = 900_002, 1
    completed_at = datetime.now(UTC) - timedelta(days=4)
    capture_id = await _seed_capture(
        session_factory, game_id=game_id, profile_id=profile_id, completed_at=completed_at
    )
    provider = ScriptedReplayProvider({(game_id, profile_id): [NotFound(), NotFound()]})
    stage = CaptureStage(
        session_factory=session_factory,
        replay_provider=provider,
        replay_publication_grace_hours=_GRACE_HOURS,
        max_attempts=_MAX_ATTEMPTS,
    )

    # First attempt: past the grace, but only one attempt so far — must not close the capture yet.
    await stage(_budget())
    capture = await _get_capture(session_factory, capture_id)
    assert capture.status == CaptureStatus.PENDING
    assert capture.attempts == 1
    assert await _get_alerts(session_factory) == []

    # Second attempt: past the grace *and* a second attempt — now it may close as unavailable.
    await _make_claimable_again(session_factory, capture_id)
    await stage(_budget())
    capture = await _get_capture(session_factory, capture_id)
    assert capture.status == CaptureStatus.UNAVAILABLE
    assert capture.attempts == 2
    assert provider.calls == [(game_id, profile_id), (game_id, profile_id)]
    assert await _get_alerts(session_factory) == []


async def test_404_past_the_retention_window_is_expired_and_raises_an_alert(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    from aoe2stats_ingester.capture import CaptureStage

    game_id, profile_id = 900_003, 1
    capture_id = await _seed_capture(
        session_factory,
        game_id=game_id,
        profile_id=profile_id,
        completed_at=datetime.now(UTC) - timedelta(days=40),
    )
    provider = ScriptedReplayProvider({(game_id, profile_id): [NotFound()]})
    stage = CaptureStage(
        session_factory=session_factory,
        replay_provider=provider,
        replay_publication_grace_hours=_GRACE_HOURS,
        max_attempts=_MAX_ATTEMPTS,
    )

    await stage(_budget())

    capture = await _get_capture(session_factory, capture_id)
    assert capture.status == CaptureStatus.EXPIRED
    # Concluded on the very first attempt — unlike `unavailable`, FR-019's two-attempt floor
    # governs "never recorded" only, not "past the retention window".
    assert capture.attempts == 1

    alerts = await _get_alerts(session_factory)
    assert len(alerts) == 1
    assert alerts[0].kind == AlertKind.EXPIRED_CAPTURE
    assert alerts[0].severity == 1
    # Not `deadline_breach`: that kind fires at the day-21 deadline (T059a, T047b), a different
    # producer with a different timing than the post-mortem this one is.
    assert alerts[0].kind != AlertKind.DEADLINE_BREACH


async def test_429_stops_the_whole_run_and_alerts_not_just_the_offending_capture(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    from aoe2stats_ingester.capture import CaptureStage

    game_id_a, profile_id_a = 900_004, 1
    game_id_b, profile_id_b = 900_005, 2
    completed_at = datetime.now(UTC) - timedelta(days=5)
    capture_id_a = await _seed_capture(
        session_factory, game_id=game_id_a, profile_id=profile_id_a, completed_at=completed_at
    )
    capture_id_b = await _seed_capture(
        session_factory, game_id=game_id_b, profile_id=profile_id_b, completed_at=completed_at
    )

    def _rate_limited(endpoint: str) -> ProviderRateLimited:
        return ProviderRateLimited(
            "throttled", provider="aoems", endpoint=endpoint, status_code=429
        )

    # Both scripted to raise: whichever the claim query picks first is the one that actually
    # fires — see the module docstring on why this test does not assume an order.
    provider = ScriptedReplayProvider(
        {
            (game_id_a, profile_id_a): [_rate_limited("/replay/a")],
            (game_id_b, profile_id_b): [_rate_limited("/replay/b")],
        }
    )
    stage = CaptureStage(
        session_factory=session_factory,
        replay_provider=provider,
        replay_publication_grace_hours=_GRACE_HOURS,
        max_attempts=_MAX_ATTEMPTS,
    )

    await stage(_budget())

    # Exactly one capture was ever attempted — the run stopped rather than moving on to the next.
    assert len(provider.calls) == 1

    alerts = await _get_alerts(session_factory)
    assert len(alerts) == 1
    assert alerts[0].kind == AlertKind.RATE_LIMITED
    assert alerts[0].severity == 2

    # A rate limit is a condition of the run, not an outcome of the capture it interrupted: neither
    # row is left in any terminal state, and neither counts an attempt.
    capture_a = await _get_capture(session_factory, capture_id_a)
    capture_b = await _get_capture(session_factory, capture_id_b)
    for capture in (capture_a, capture_b):
        assert capture.status == CaptureStatus.PENDING
        assert capture.attempts == 0


@pytest.mark.xfail(strict=True, reason="T057 not implemented yet")
async def test_three_consecutive_5xx_produce_backoff_then_failed_at_the_attempt_limit(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    from aoe2stats_ingester.capture import CaptureStage

    game_id, profile_id = 900_006, 1
    completed_at = datetime.now(UTC) - timedelta(days=1)
    capture_id = await _seed_capture(
        session_factory, game_id=game_id, profile_id=profile_id, completed_at=completed_at
    )

    def _unavailable() -> ProviderUnavailable:
        return ProviderUnavailable(
            "server error", provider="aoems", endpoint="/replay/x", status_code=500
        )

    provider = ScriptedReplayProvider(
        {(game_id, profile_id): [_unavailable(), _unavailable(), _unavailable()]}
    )
    stage = CaptureStage(
        session_factory=session_factory,
        replay_provider=provider,
        replay_publication_grace_hours=_GRACE_HOURS,
        max_attempts=_MAX_ATTEMPTS,
    )

    # First failure: retried later, not yet failed.
    before_first = datetime.now(UTC)
    await stage(_budget())
    capture = await _get_capture(session_factory, capture_id)
    assert capture.status == CaptureStatus.PENDING
    assert capture.attempts == 1
    first_delay = capture.next_attempt_at - before_first
    assert first_delay > timedelta(0)

    # Second failure: backoff, still not failed — the delay must keep increasing (FR-020), never
    # merely repeat, so an implementation cannot satisfy this by reusing a fixed retry interval.
    await _make_claimable_again(session_factory, capture_id)
    before_second = datetime.now(UTC)
    await stage(_budget())
    capture = await _get_capture(session_factory, capture_id)
    assert capture.status == CaptureStatus.PENDING
    assert capture.attempts == 2
    second_delay = capture.next_attempt_at - before_second
    assert second_delay > first_delay

    # Third failure: the attempt limit (`max_attempts=3`) is reached — terminal `failed`, never an
    # unbounded retry (FR-020).
    await _make_claimable_again(session_factory, capture_id)
    await stage(_budget())
    capture = await _get_capture(session_factory, capture_id)
    assert capture.status == CaptureStatus.FAILED
    assert capture.attempts == 3

    assert provider.calls == [(game_id, profile_id)] * 3
    # `failed` is not one of the five alert kinds (data-model.md) — nothing here should have
    # raised.
    assert await _get_alerts(session_factory) == []
