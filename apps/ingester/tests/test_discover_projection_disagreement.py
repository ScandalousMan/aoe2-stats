"""T459f — a Relic self-contradiction must not abort a `DiscoverStage` batch.

Production, 2026-10-04: one `matchhistorymember` / `matchhistoryreportresults` pair of 770 disagreed
on `civilization_id` and `project_match_player` raised out of
`upsert_match_players`. In the ingester that raise aborts the discovery transaction before the
capture enqueue — constitution I — so the batch below carries the contradicting pair next to a
clean one and asserts the run still writes every `match_players` row and enqueues every capture.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_providers.base import LeaderboardSnapshot, ProfileRef, RawMatch
from aoe2stats_storage.models import (
    AoeProfile,
    CaptureStatus,
    MatchPlayer,
    ProfileLink,
    ReplayCapture,
    SteamIdentity,
    User,
)

_LINKED = 190_459_111
_OPPONENT = 190_459_222
_DISPUTED_GAME = 555_459_111
_CLEAN_GAME = 555_459_222
_COMPLETED_AT = datetime(2026, 10, 3, 20, 15, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _storage_logger_enabled() -> None:
    """The migrations' `fileConfig` (`infra/migrations/env.py`, run by the first throwaway database
    of the session) disables every logger that already exists, which would make the warning this
    file asserts a silent no-op in a full-suite run."""
    logging.getLogger("aoe2stats_storage").disabled = False


def _payload(game_id: int, *, report_civ: int) -> dict[str, Any]:
    return {
        "id": game_id,
        "matchhistorymember": [
            {
                "profile_id": _LINKED,
                "civilization_id": 1,
                "teamid": 0,
                "outcome": 1,
                "oldrating": 1500,
                "newrating": 1520,
            },
            {
                "profile_id": _OPPONENT,
                "civilization_id": 12,
                "teamid": 1,
                "outcome": 0,
                "oldrating": 1510,
                "newrating": 1490,
            },
        ],
        "matchhistoryreportresults": [
            {"profile_id": _LINKED, "civilization_id": report_civ, "teamid": 0, "resulttype": 1},
            {"profile_id": _OPPONENT, "civilization_id": 12, "teamid": 1, "resulttype": 0},
        ],
    }


def _raw_match(game_id: int, *, report_civ: int, hours_ago: int) -> RawMatch:
    return RawMatch(
        game_id=game_id,
        leaderboard_id=3,
        map_name="Arabia",
        patch="stable",
        started_at=_COMPLETED_AT - timedelta(hours=hours_ago, minutes=35),
        completed_at=_COMPLETED_AT - timedelta(hours=hours_ago),
        duration_seconds=2_100,
        player_profile_ids=(_LINKED, _OPPONENT),
        raw_payload=_payload(game_id, report_civ=report_civ),
    )


class _FakeProfileProvider:
    async def resolve_profile(self, steam_id64: str) -> ProfileRef | None:
        raise AssertionError("a discovery cycle never resolves a Steam id")

    async def personal_stats(self, profile_ids: Sequence[int]) -> list[LeaderboardSnapshot]:
        return [
            LeaderboardSnapshot(profile_id=profile_id, leaderboard_id=3, rating=1500)
            for profile_id in profile_ids
        ]


class _FakeMatchHistoryProvider:
    def __init__(self, raw_matches: list[RawMatch]) -> None:
        self._raw_matches = raw_matches

    async def recent_matches(self, profile_ids: Sequence[int]) -> list[RawMatch]:
        return list(self._raw_matches)


async def _seed_linked_user(session_factory: async_sessionmaker[AsyncSession]) -> None:
    now = datetime.now(UTC)
    user = User(id=uuid.uuid4())
    steam = SteamIdentity(
        steam_id64="76500000000459111",
        user_id=user.id,
        verified_at=now - timedelta(days=30),
        last_sign_in_at=now - timedelta(days=1),
    )
    async with session_factory() as session:
        session.add_all([user, steam, AoeProfile(profile_id=_LINKED, alias="Linked", country="FR")])
        await session.flush()
        session.add(
            ProfileLink(
                id=uuid.uuid4(),
                user_id=user.id,
                profile_id=_LINKED,
                steam_id64=steam.steam_id64,
                is_primary=True,
                linked_at=now - timedelta(days=30),
            )
        )
        await session.commit()


async def test_a_batch_with_a_self_contradicting_pair_writes_its_rows_and_enqueues_captures(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from aoe2stats_ingester.budget import Budget
    from aoe2stats_ingester.discover import DiscoverStage

    await _seed_linked_user(session_factory)
    stage = DiscoverStage(
        session_factory=session_factory,
        profile_provider=_FakeProfileProvider(),
        match_history_provider=_FakeMatchHistoryProvider(
            [
                _raw_match(_DISPUTED_GAME, report_civ=0, hours_ago=2),
                _raw_match(_CLEAN_GAME, report_civ=1, hours_ago=1),
            ]
        ),
        capture_budget_days=21,
    )

    with caplog.at_level("WARNING", logger="aoe2stats_storage"):
        report = await stage(Budget(seconds=30))
    assert isinstance(report, Mapping)

    async with session_factory() as session:
        rows = {
            (row.game_id, row.profile_id): row
            for row in (await session.execute(select(MatchPlayer))).scalars()
        }
        captures = (await session.execute(select(ReplayCapture))).scalars().all()

    assert set(rows) == {
        (_DISPUTED_GAME, _LINKED),
        (_DISPUTED_GAME, _OPPONENT),
        (_CLEAN_GAME, _LINKED),
        (_CLEAN_GAME, _OPPONENT),
    }
    disputed = rows[(_DISPUTED_GAME, _LINKED)]
    assert disputed.civ_id is None
    assert (disputed.team_id, disputed.result, disputed.rating) == (0, "win", 1520)
    assert rows[(_DISPUTED_GAME, _OPPONENT)].civ_id == 12
    assert rows[(_CLEAN_GAME, _LINKED)].civ_id == 1, "an agreeing pair still projects every field"

    assert {(c.game_id, c.profile_id) for c in captures} == {
        (_DISPUTED_GAME, _LINKED),
        (_CLEAN_GAME, _LINKED),
    }, "capture enqueue is unaffected by the disagreement"
    assert all(c.status == CaptureStatus.PENDING for c in captures)
    warnings = [r for r in caplog.records if r.name == "aoe2stats_storage"]
    assert len(warnings) == 1 and "civ_id" in warnings[0].getMessage()
