"""T845: an erasure that starts while `retain_recording`'s transaction is open is serialised
against it by the `match_players` row lock, on two real connections.

`retain_recording` locks `match_players (game_id, profile_id)` `FOR KEY SHARE` before it reads or
writes `retained_recordings`; erasure takes `FOR UPDATE` on the same row (`discover.
lock_match_players`), which conflicts, and only then selects the retained rows it rewrites. The
object store's `put` is gated here, so the retaining transaction is held open between its lock and
its commit for as long as the test chooses: no sleep decides the order, the gate does, and the
erasure's wait is observed in `pg_stat_activity` rather than assumed.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_analyzer.retain import retain_recording
from aoe2stats_storage.models import AoeProfile, Match, MatchPlayer, RetainedRecording
from aoe2stats_storage.objects import retained_recording_object_key
from aoe2stats_storage.repositories.base import session_scope

_GAME_ID = 500_845_101
_SUBJECT = 500_845_102
_OTHER = 500_845_103
_WAIT_SECONDS = 10.0


class _GatedStore:
    """Only `put` is used by `retain_recording`. It announces that it was reached, then waits for
    the test to open the gate."""

    def __init__(self) -> None:
        self.reached = asyncio.Event()
        self.gate = asyncio.Event()
        self.objects: dict[str, bytes] = {}

    async def put(self, key: str, body: bytes, *, content_type: str = "application/zip") -> None:
        self.reached.set()
        await self.gate.wait()
        self.objects[key] = body


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


async def _a_backend_is_waiting_on_a_lock(
    session_factory: async_sessionmaker[AsyncSession], erasure: asyncio.Task[None]
) -> bool:
    deadline = asyncio.get_running_loop().time() + _WAIT_SECONDS
    while asyncio.get_running_loop().time() < deadline and not erasure.done():
        async with session_factory() as probe:
            waiting = (
                await probe.execute(
                    text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE datname = current_database() AND wait_event_type = 'Lock'"
                    )
                )
            ).scalar_one()
        if waiting:
            return True
        await asyncio.sleep(0.05)
    return False


async def test_an_erasure_started_while_the_retention_holds_its_lock_waits_then_rewrites_the_row(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    from aoe2stats_api.routers.privacy import _pseudonymise_profile_ids

    await _seed(session_factory)
    store = _GatedStore()

    async def retain() -> None:
        async with session_factory() as session:
            await retain_recording(
                session, store, game_id=_GAME_ID, profile_id=_SUBJECT, zip_bytes=b"bytes"
            )

    async def erase() -> None:
        async with session_scope(session_factory) as session:
            await _pseudonymise_profile_ids(session, [_SUBJECT])

    retaining = asyncio.create_task(retain())
    erasing: asyncio.Task[None] | None = None
    try:
        await asyncio.wait_for(store.reached.wait(), timeout=_WAIT_SECONDS)
        erasing = asyncio.create_task(erase())
        waiting = await _a_backend_is_waiting_on_a_lock(session_factory, erasing)
        finished_before_the_commit = erasing.done()
        assert waiting and not finished_before_the_commit, (
            "the erasure must wait for the transaction that holds the subject's match_players row"
        )
    finally:
        store.gate.set()
        await asyncio.wait_for(retaining, timeout=_WAIT_SECONDS)
        if erasing is not None:
            await asyncio.wait_for(erasing, timeout=_WAIT_SECONDS)

    async with session_scope(session_factory) as session:
        rows = (await session.execute(select(RetainedRecording))).scalars().all()
    assert [row.profile_id for row in rows] == [-_SUBJECT], (
        "the erasure must rewrite the row the retention committed while it waited"
    )
    assert rows[0].object_key == retained_recording_object_key(_GAME_ID, _SUBJECT)
