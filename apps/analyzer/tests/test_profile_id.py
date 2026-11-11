"""T845: `resolve_profile_id` and the analyzer writes that go through it.

Each write below is run after the participant it names was erased (their `match_players` row moved
to the placeholder by the real `_pseudonymise_profile_ids`), the state a run reaches when the
participant list was read before the erasure committed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_analyzer import run as run_module
from aoe2stats_analyzer.claim import claim_for_analysis
from aoe2stats_analyzer.profile_id import resolve_profile_id
from aoe2stats_storage.models import (
    AoeProfile,
    Match,
    MatchAnalysis,
    MatchAnalysisState,
    MatchPlayer,
    User,
)
from aoe2stats_storage.repositories.base import session_scope

_GAME_ID = 500_845_201
_SUBJECT = 500_845_202
_OTHER = 500_845_203


async def _seed(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_scope(session_factory) as session:
        for profile_id in (_SUBJECT, _OTHER):
            session.add(AoeProfile(profile_id=profile_id, alias=f"Player {profile_id}"))
        session.add(
            Match(
                game_id=_GAME_ID,
                leaderboard_id=3,
                completed_at=datetime.now(UTC) - timedelta(days=1),
                duration_seconds=1800,
                source="relic",
                raw_payload={},
            )
        )
        for index, profile_id in enumerate((_SUBJECT, _OTHER)):
            session.add(
                MatchPlayer(
                    game_id=_GAME_ID,
                    profile_id=profile_id,
                    team_id=index,
                    civ_id=1,
                    color_id=index,
                    result="win" if index == 0 else "loss",
                )
            )


async def _erase(session_factory: async_sessionmaker[AsyncSession], profile_id: int) -> None:
    from aoe2stats_api.routers.privacy import _pseudonymise_profile_ids

    async with session_scope(session_factory) as session:
        await _pseudonymise_profile_ids(session, [profile_id])


async def _resolve(session_factory: async_sessionmaker[AsyncSession], profile_id: int) -> int:
    async with session_scope(session_factory) as session:
        return await resolve_profile_id(session, game_id=_GAME_ID, profile_id=profile_id)


async def _analysis(session_factory: async_sessionmaker[AsyncSession]) -> MatchAnalysis:
    async with session_scope(session_factory) as session:
        row = await session.get(MatchAnalysis, _GAME_ID)
    assert row is not None
    return row


async def test_a_participant_that_exists_resolves_to_itself(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    await _seed(session_factory)

    assert await _resolve(session_factory, _SUBJECT) == _SUBJECT


async def test_an_erased_participant_resolves_to_its_placeholder(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    await _seed(session_factory)
    await _erase(session_factory, _SUBJECT)

    assert await _resolve(session_factory, _SUBJECT) == -_SUBJECT
    assert await _resolve(session_factory, -_SUBJECT) == -_SUBJECT
    assert await _resolve(session_factory, _OTHER) == _OTHER


async def test_an_id_that_is_neither_a_participant_nor_a_placeholder_raises(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    await _seed(session_factory)

    with pytest.raises(LookupError):
        await _resolve(session_factory, 123)
    with pytest.raises(LookupError):
        await _resolve(session_factory, _SUBJECT + 1_000)


async def test_a_claim_names_the_placeholder_of_a_participant_erased_since_it_was_read(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    await _seed(session_factory)
    await _erase(session_factory, _SUBJECT)

    outcome = await claim_for_analysis(
        session_factory,
        game_id=_GAME_ID,
        point_of_view_profile_id=_SUBJECT,
        requested_by_user_id=None,
        lease_seconds=300,
        max_attempts=3,
        now=datetime.now(UTC),
    )

    assert outcome.claimed
    assert (await _analysis(session_factory)).point_of_view_profile_id == -_SUBJECT


async def test_a_point_of_view_recorded_for_an_erased_participant_is_the_placeholder(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    await _seed(session_factory)
    now = datetime.now(UTC)
    outcome = await claim_for_analysis(
        session_factory,
        game_id=_GAME_ID,
        point_of_view_profile_id=_OTHER,
        requested_by_user_id=None,
        lease_seconds=300,
        max_attempts=3,
        now=now,
    )
    await _erase(session_factory, _SUBJECT)

    await run_module._record_point_of_view(
        session_factory,
        game_id=_GAME_ID,
        profile_id=_SUBJECT,
        claimed_at=outcome.claimed_at,  # type: ignore[arg-type]
    )

    assert (await _analysis(session_factory)).point_of_view_profile_id == -_SUBJECT


async def test_a_row_marked_unavailable_for_an_erased_participant_names_the_placeholder(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    await _seed(session_factory)
    await _erase(session_factory, _SUBJECT)
    requester = uuid4()
    async with session_scope(session_factory) as session:
        session.add(User(id=requester))

    await run_module._mark_unavailable(
        session_factory,
        game_id=_GAME_ID,
        point_of_view_profile_id=_SUBJECT,
        requested_by_user_id=requester,
        now=datetime.now(UTC),
    )

    row = await _analysis(session_factory)
    assert row.state == MatchAnalysisState.UNAVAILABLE
    assert row.point_of_view_profile_id == -_SUBJECT
    async with session_scope(session_factory) as session:
        assert (await session.execute(select(MatchAnalysis.game_id))).scalars().all() == [_GAME_ID]
