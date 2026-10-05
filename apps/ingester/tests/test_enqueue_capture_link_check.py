"""T459g — `DiscoverStage._enqueue_capture` re-checks, inside its own `INSERT`, that the profile
still has an active link whose user has not objected (`discover.archiving_links`).

`DiscoverStage.__call__` reads the archiving set once, before it persists a batch. A batch that
waited on an erasure's row locks, or whose user objected after that read, would otherwise enqueue a
capture for someone who no longer archives: constitution IX outranks capture for a profile that is
no longer linked or has objected (FR-035, FR-037). The statement itself therefore asks the question
again; the test below that drives `__call__` hands it a stale set to show that the statement, and
not the set, is what stops the capture.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_ingester.budget import Budget
from aoe2stats_ingester.discover import DiscoverStage, persist_matches_and_profiles
from aoe2stats_providers.base import RawMatch
from aoe2stats_storage.models import (
    CaptureSource,
    CaptureStatus,
    Match,
    ProfileLink,
    ReplayCapture,
    SteamIdentity,
    User,
)

_PROFILE = 220_000_001
_GAME = 220_100_001
_BUDGET_DAYS = 21
_COMPLETED_AT = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)


class _OneMatchProvider:
    async def recent_matches(self, profile_ids: list[int]) -> list[RawMatch]:
        return [_raw_match()]


def _raw_match() -> RawMatch:
    return RawMatch(
        game_id=_GAME,
        leaderboard_id=3,
        completed_at=_COMPLETED_AT,
        player_profile_ids=(_PROFILE,),
        raw_payload={"id": _GAME},
    )


async def _seed_user(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    objected: bool = False,
    unlinked: bool = False,
    link: bool = True,
) -> None:
    """A user holding `_PROFILE`. `link=False` is an erased user: `DELETE FROM users` cascades
    the `profile_links` row away, and so does this seed by never adding it."""
    now = datetime.now(UTC)
    user_id = uuid.uuid4()
    steam_id64 = "76561198000000001"
    async with session_factory() as session:
        session.add(
            User(id=user_id, allowlisted_at=now, archival_objected_at=now if objected else None)
        )
        session.add(
            SteamIdentity(
                steam_id64=steam_id64, user_id=user_id, verified_at=now, last_sign_in_at=now
            )
        )
        await session.flush()
        await persist_matches_and_profiles(session, [_raw_match()])
        if link:
            session.add(
                ProfileLink(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    profile_id=_PROFILE,
                    steam_id64=steam_id64,
                    is_primary=True,
                    linked_at=now,
                    unlinked_at=now if unlinked else None,
                )
            )
        await session.commit()


def _stage(session_factory: async_sessionmaker[AsyncSession]) -> DiscoverStage:
    return DiscoverStage(
        session_factory=session_factory,
        match_history_provider=_OneMatchProvider(),
        capture_budget_days=_BUDGET_DAYS,
    )


async def _enqueue(session_factory: async_sessionmaker[AsyncSession]) -> bool:
    async with session_factory() as session:
        enqueued = await _stage(session_factory)._enqueue_capture(session, _raw_match(), _PROFILE)
        await session.commit()
        return enqueued


async def _captures(session_factory: async_sessionmaker[AsyncSession]) -> list[ReplayCapture]:
    async with session_factory() as session:
        return list((await session.execute(select(ReplayCapture))).scalars())


async def test_an_active_link_whose_user_has_not_objected_is_enqueued(
    clean_database: None, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_user(session_factory)
    assert await _enqueue(session_factory) is True
    (capture,) = await _captures(session_factory)
    assert (capture.game_id, capture.profile_id) == (_GAME, _PROFILE)
    assert capture.status == CaptureStatus.PENDING
    assert capture.source == CaptureSource.AUTOMATIC
    assert capture.capture_deadline_at == _COMPLETED_AT + timedelta(days=_BUDGET_DAYS)
    assert capture.attempts == 0


@pytest.mark.parametrize(
    "seed",
    [
        {"objected": True},
        {"unlinked": True},
        {"link": False},
    ],
    ids=["objecting user", "unlinked profile", "no link (erased user)"],
)
async def test_a_profile_that_no_longer_archives_is_not_enqueued(
    seed: dict[str, bool],
    clean_database: None,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_user(session_factory, **seed)
    assert await _enqueue(session_factory) is False
    assert await _captures(session_factory) == []


async def test_enqueueing_twice_keeps_the_first_row(
    clean_database: None, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_user(session_factory)
    assert await _enqueue(session_factory) is True
    (first,) = await _captures(session_factory)
    assert await _enqueue(session_factory) is False
    (again,) = await _captures(session_factory)
    assert again.id == first.id


async def test_a_batch_holding_a_stale_archiving_set_enqueues_nothing(
    clean_database: None,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The set `__call__` read before persisting still names `_PROFILE`; the user objected after.
    The match is persisted, the capture is not."""
    await _seed_user(session_factory, objected=True)
    stage = _stage(session_factory)

    async def stale() -> list[int]:
        return [_PROFILE]

    monkeypatch.setattr(stage, "_archiving_profile_ids", stale)
    report = await stage(Budget(seconds=30))
    # `__call__` polls `_linked_profile_ids`, which an objection does not narrow.
    assert report["matches_discovered"] == 1
    assert report["captures_enqueued"] == 0
    assert await _captures(session_factory) == []
    async with session_factory() as session:
        assert await session.get(Match, _GAME) is not None
