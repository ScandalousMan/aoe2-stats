"""T411 — `upsert_match_player` (`discover.py`) writes `match_players.color_id` from Relic's own
`slotinfo`, and never erases a stored colour with a `NULL` projection.

Both `match_players` writers — `DiscoverStage.__call__` and `routers/players.py`'s
`_refresh_third_party_history` — call this one function, so this file is the whole of the wiring
proof; the decode itself is `packages/storage/tests/test_match_projection.py`'s.

The `COALESCE(excluded.color_id, match_players.color_id)` in the statement's `SET` clause is the
asymmetry under test: a payload the projection cannot read (no `slotinfo` — a synthetic
`raw_payload`, or a shape Relic has not served yet) projects `None`, and `None` means "unknown".
A colour stored by an earlier sighting, or by the companion fallback
(`routers/matches.py::enrich_colours`), must survive that rediscovery; a non-`None` projection
must win, Relic being the primary source.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_providers.base import RawMatch
from aoe2stats_storage.models import AoeProfile, MatchPlayer

_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "providers"
    / "fixtures"
    / "relic"
    / "get_recent_match_history.json"
)
_PROFILE_ID = 264353  # match 500615037: slotinfo ScenarioPlayerIndex 6 -> colour 7 (grey)


def _fixture_entry() -> dict[str, Any]:
    body = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    entry: dict[str, Any] = body["matchHistoryStats"][0]
    assert entry["id"] == 500615037, "fixture's first entry moved — update this file"
    return entry


def _raw_match(entry: dict[str, Any]) -> RawMatch:
    return RawMatch(
        game_id=entry["id"],
        leaderboard_id=entry["matchtype_id"],
        map_name=entry["mapname"],
        completed_at=datetime.fromtimestamp(entry["completiontime"], tz=UTC),
        player_profile_ids=tuple(m["profile_id"] for m in entry["matchhistorymember"]),
        raw_payload=entry,
    )


async def _upsert(session: AsyncSession, raw_match: RawMatch) -> None:
    from aoe2stats_ingester import discover

    await discover.upsert_match(session, raw_match)
    await discover.upsert_match_player(session, raw_match, _PROFILE_ID)


async def _colour(session_factory: async_sessionmaker[AsyncSession]) -> int | None:
    async with session_factory() as session:
        row = (
            await session.execute(
                select(MatchPlayer).where(
                    MatchPlayer.game_id == 500615037, MatchPlayer.profile_id == _PROFILE_ID
                )
            )
        ).scalar_one()
        return row.color_id


async def test_discovery_writes_the_colour_from_slotinfo(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    async with session_factory() as session:
        session.add(AoeProfile(profile_id=_PROFILE_ID, alias="Somero"))
        await session.flush()
        await _upsert(session, _raw_match(_fixture_entry()))
        await session.commit()

    assert await _colour(session_factory) == 7


async def test_a_rediscovery_whose_payload_has_no_slotinfo_keeps_the_stored_colour(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    entry = _fixture_entry()
    without_slotinfo = {key: value for key, value in entry.items() if key != "slotinfo"}

    async with session_factory() as session:
        session.add(AoeProfile(profile_id=_PROFILE_ID, alias="Somero"))
        await session.flush()
        await _upsert(session, _raw_match(entry))
        await session.commit()
    assert await _colour(session_factory) == 7

    async with session_factory() as session:
        await _upsert(session, _raw_match(without_slotinfo))
        await session.commit()

    assert await _colour(session_factory) == 7, (
        "a NULL projection is 'unknown', and must never overwrite a colour already stored"
    )


async def test_a_rediscovery_with_slotinfo_overwrites_a_colour_stored_from_elsewhere(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """The companion fallback (or an earlier, wrong sighting) stored `3`; Relic's own payload says
    `7`. Relic is primary: the projection wins."""
    entry = _fixture_entry()
    without_slotinfo = {key: value for key, value in entry.items() if key != "slotinfo"}

    async with session_factory() as session:
        session.add(AoeProfile(profile_id=_PROFILE_ID, alias="Somero"))
        await session.flush()
        await _upsert(session, _raw_match(without_slotinfo))
        await session.execute(
            MatchPlayer.__table__.update()
            .where(MatchPlayer.game_id == 500615037, MatchPlayer.profile_id == _PROFILE_ID)
            .values(color_id=3)
        )
        await session.commit()
    assert await _colour(session_factory) == 3

    async with session_factory() as session:
        await _upsert(session, _raw_match(entry))
        await session.commit()

    assert await _colour(session_factory) == 7
