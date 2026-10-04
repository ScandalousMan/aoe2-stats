"""T459 — `discover.persist_matches_and_profiles`, the one writer of `matches`, `aoe_profiles` and
`match_players` for a batch of raw matches, and every caller that goes through it.

Two properties, both observed on the statements that actually reach Postgres (a
`before_cursor_execute` listener on the engine), not on the helper's own internals:

- **A bounded number of statements.** A 177-match, 770-player, 400-profile response (production,
  2026-10-04: `GET /api/players/212721/matches`) was persisted one statement per row — about 2,100
  sequential round trips, which no 10-second serverless request can finish. The helper issues one
  multi-row `INSERT ... ON CONFLICT` per table, so the count is the same for 1 match and for 150.
- **One global lock order.** `matches` ascending by `game_id`, then `aoe_profiles` ascending by
  `profile_id`, then `match_players` ascending by `(game_id, profile_id)`; each table written once.
  Row locks are held to commit and a multi-row insert takes them in `VALUES` order, so the order of
  the rows in the statement *is* the lock order. `apps/api/tests/test_refresh_lock_order.py` proves
  the other half against a real concurrent writer.

The alias/country merge is tested here too, because it moved from a per-row Python branch to SQL
(`CASE WHEN excluded.alias <> excluded.profile_id::text`) and its contract — never clobber a real
alias with the numeric-id placeholder — is the one `test_touch_aoe_profile.py` states for the
single-row call.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

import pytest
from sqlalchemy import event, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from aoe2stats_ingester.budget import Budget
from aoe2stats_ingester.discover import DiscoverStage, persist_matches_and_profiles
from aoe2stats_ingester.reconcile import ReconcileStage
from aoe2stats_providers.base import RawMatch, RawProfile
from aoe2stats_storage.models import (
    AoeProfile,
    Match,
    MatchPlayer,
    ProfileLink,
    ReplayCapture,
    SteamIdentity,
    User,
)

_COMPLETED_AT = datetime(2026, 9, 30, 12, 0, 0, tzinfo=UTC)


class _Recorder:
    """Every `INSERT` statement sent while it is installed: the table, and the value of the named
    key column for each row in `VALUES` order."""

    _KEYS: ClassVar[dict[str, tuple[str, ...]]] = {
        "matches": ("game_id",),
        "aoe_profiles": ("profile_id",),
        "match_players": ("game_id", "profile_id"),
    }

    def __init__(self) -> None:
        self.statements: list[str] = []
        self.inserts: list[tuple[str, list[tuple[int, ...]]]] = []

    def __call__(
        self, conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, many: bool
    ) -> None:
        self.statements.append(statement)
        found = re.match(r"INSERT INTO (\w+)", statement)
        if found is None or found.group(1) not in self._KEYS:
            return
        table = found.group(1)
        columns = self._KEYS[table]
        # An `executemany` is a list of parameter sets, each recorded in order; a batched `INSERT`
        # is one dict whose names carry a per-row suffix (`_m<N>` or `__<N>`).
        for parameter_set in [parameters] if isinstance(parameters, dict) else parameters:
            rows: dict[int, list[int]] = {}
            for key, value in dict(parameter_set).items():
                for position, column in enumerate(columns):
                    matched = re.fullmatch(rf"{column}(?:(?:_m|__)(\d+))?", key)
                    if matched:
                        index = int(matched.group(1) or 0)
                        rows.setdefault(index, [0] * len(columns))[position] = value
            self.inserts.append((table, [tuple(rows[i]) for i in sorted(rows)]))

    def tables(self) -> list[str]:
        return [table for table, _ in self.inserts]


@pytest.fixture
def recorder(engine: AsyncEngine) -> Iterator[_Recorder]:
    recording = _Recorder()
    event.listen(engine.sync_engine, "before_cursor_execute", recording)
    try:
        yield recording
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", recording)


def _match(game_id: int, players: tuple[int, ...]) -> RawMatch:
    return RawMatch(
        game_id=game_id,
        leaderboard_id=3,
        completed_at=_COMPLETED_AT,
        player_profile_ids=players,
        raw_payload={"id": game_id},
    )


def _assert_global_order(recorder: _Recorder) -> None:
    """The invariant, read off the statements: tables in order, each once, rows ascending."""
    assert recorder.tables() == ["matches", "aoe_profiles", "match_players"], recorder.tables()
    for table, rows in recorder.inserts:
        assert rows == sorted(rows), f"{table} rows must be written ascending, got {rows[:8]}"
        assert len(rows) == len(set(rows)), f"{table} rows must be deduplicated"


async def test_statement_count_is_constant_for_a_large_batch(
    db_session: AsyncSession, recorder: _Recorder
) -> None:
    """177 matches of 4-5 players each, drawn from 400 distinct profiles (the production shape):
    three INSERT statements, and nothing else, whatever the size. Listed in descending order on
    purpose — the helper, not the caller, owns the order."""
    profile_ids = list(range(500_000, 500_400))
    matches = [
        _match(700_000 + n, tuple(profile_ids[(n * 7 + k) % 400] for k in range(5, 0, -1)))
        for n in range(177, 0, -1)
    ]
    assert len({m.game_id for m in matches}) == 177
    assert sum(len(m.player_profile_ids) for m in matches) >= 770

    await persist_matches_and_profiles(db_session, matches)

    assert len(recorder.statements) == 3, recorder.statements
    _assert_global_order(recorder)
    stored = (await db_session.execute(select(Match.game_id))).scalars().all()
    assert len(stored) == 177


async def test_statement_count_does_not_grow_with_the_batch(
    db_session: AsyncSession, recorder: _Recorder
) -> None:
    await persist_matches_and_profiles(db_session, [_match(1, (3, 2, 1))])
    small = len(recorder.statements)
    recorder.statements.clear()
    await persist_matches_and_profiles(
        db_session, [_match(10 + n, (n + 100, n + 101)) for n in range(150)]
    )
    assert len(recorder.statements) == small == 3


async def test_rows_are_written_in_the_global_order_and_deduplicated(
    db_session: AsyncSession, recorder: _Recorder
) -> None:
    """Matches, participants and the identity block all disagree on order, and the same match and
    the same profile each arrive twice."""
    matches = [_match(30, (9, 5, 7)), _match(10, (7, 3)), _match(30, (9, 5, 7))]
    identities = [
        RawProfile(profile_id=8, alias="Eight"),
        RawProfile(profile_id=3, alias="Three"),
        RawProfile(profile_id=5, alias="Five"),
        RawProfile(profile_id=3, alias="Three"),
    ]

    pairs = await persist_matches_and_profiles(db_session, matches, identities)

    _assert_global_order(recorder)
    profile_rows = dict(recorder.inserts)["aoe_profiles"]
    assert profile_rows == [(3,), (5,), (7,), (8,), (9,)]
    assert [(m.game_id, p) for m, p in pairs] == [(10, 3), (10, 7), (30, 5), (30, 7), (30, 9)]


async def test_real_alias_is_merged_from_any_source_and_never_clobbered(
    db_session: AsyncSession,
) -> None:
    # A real alias arriving only through the identity block lands on a participant row.
    await persist_matches_and_profiles(
        db_session,
        [_match(1, (11, 12))],
        [RawProfile(profile_id=11, alias="Eleven", country="FR")],
    )
    # A later batch that knows these profiles only as participants must not overwrite the name
    # (or the country that arrived with it) with the numeric placeholder.
    await persist_matches_and_profiles(db_session, [_match(2, (11, 12))])
    # A source that names the placeholder explicitly is the same as no name at all.
    await persist_matches_and_profiles(
        db_session, [], [RawProfile(profile_id=11, alias="11", country="XX")]
    )

    db_session.expire_all()
    rows = {
        row.profile_id: row
        for row in (await db_session.execute(select(AoeProfile))).scalars().all()
    }
    assert rows[11].alias == "Eleven" and rows[11].country == "FR"
    assert rows[12].alias == "12" and rows[12].country is None


async def test_a_real_alias_replaces_the_placeholder_and_a_newer_real_alias_replaces_it(
    db_session: AsyncSession,
) -> None:
    await persist_matches_and_profiles(db_session, [_match(1, (21,))])
    await persist_matches_and_profiles(
        db_session, [], [RawProfile(profile_id=21, alias="First", country="FR")]
    )
    await persist_matches_and_profiles(
        db_session, [], [RawProfile(profile_id=21, alias="Second", country="DE")]
    )

    db_session.expire_all()
    row = (await db_session.execute(select(AoeProfile))).scalar_one()
    assert (row.alias, row.country) == ("Second", "DE")


async def test_one_batch_may_mix_real_and_placeholder_sightings_in_one_statement(
    db_session: AsyncSession, recorder: _Recorder
) -> None:
    """Splitting real from placeholder rows into two statements would break the single ascending
    order, so the `CASE` lives in SQL and a mixed batch is still one statement."""
    await persist_matches_and_profiles(
        db_session,
        [_match(1, (31, 32, 33))],
        [RawProfile(profile_id=32, alias="Thirty-two", country="SE")],
    )
    assert recorder.tables().count("aoe_profiles") == 1

    db_session.expire_all()
    rows = {r.profile_id: r.alias for r in (await db_session.execute(select(AoeProfile))).scalars()}
    assert rows == {31: "31", 32: "Thirty-two", 33: "33"}


async def _seed_linked_profile(
    session_factory: async_sessionmaker[AsyncSession], profile_id: int
) -> None:
    now = datetime.now(UTC)
    user = User(id=uuid.uuid4())
    steam = SteamIdentity(
        steam_id64="76500000000000460",
        user_id=user.id,
        verified_at=now - timedelta(days=30),
        last_sign_in_at=now - timedelta(days=1),
    )
    async with session_factory() as session:
        session.add_all([user, steam, AoeProfile(profile_id=profile_id, alias="Linked")])
        await session.flush()
        session.add(
            ProfileLink(
                id=uuid.uuid4(),
                user_id=user.id,
                profile_id=profile_id,
                steam_id64=steam.steam_id64,
                is_primary=True,
                linked_at=now - timedelta(days=30),
            )
        )
        await session.commit()


class _Provider:
    def __init__(self, matches: Sequence[RawMatch]) -> None:
        self._matches = list(matches)

    async def recent_matches(self, profile_ids: Sequence[int]) -> list[RawMatch]:
        return list(self._matches)


_DISORDERED = [_match(900, (44, 41, 43)), _match(800, (43, 42, 41)), _match(850, (41,))]


@pytest.mark.parametrize("stage_name", ["discover", "reconcile"])
async def test_ingester_stages_write_in_the_global_order(
    stage_name: str,
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    recorder: _Recorder,
) -> None:
    await _seed_linked_profile(session_factory, 43)
    provider = _Provider(_DISORDERED)
    stage: DiscoverStage | ReconcileStage
    if stage_name == "discover":
        stage = DiscoverStage(
            session_factory=session_factory, match_history_provider=provider, capture_budget_days=21
        )
    else:
        stage = ReconcileStage(
            session_factory=session_factory, match_history_provider=provider, capture_budget_days=21
        )
    recorder.statements.clear()
    recorder.inserts.clear()

    await stage(Budget(seconds=30))

    writes = [(t, rows) for t, rows in recorder.inserts if t != "replay_captures"]
    assert [t for t, _ in writes] == ["matches", "aoe_profiles", "match_players"]
    for table, rows in writes:
        assert rows == sorted(rows), f"{table}: {rows}"
    async with session_factory() as session:
        captures = (await session.execute(select(ReplayCapture.game_id))).scalars().all()
        players = (await session.execute(select(MatchPlayer.game_id))).scalars().all()
    assert sorted(captures) == [800, 900]
    assert len(players) == 7


# --- T459a: companion colour fills ride the same persistence -------------------------------------


async def _stored_match_players(
    session: AsyncSession, games: Sequence[int], profiles: Sequence[int], *, colour: int | None
) -> None:
    for profile_id in profiles:
        session.add(AoeProfile(profile_id=profile_id, alias=str(profile_id)))
    for game_id in games:
        session.add(
            Match(
                game_id=game_id,
                leaderboard_id=3,
                completed_at=_COMPLETED_AT,
                source="relic",
                raw_payload={"id": game_id},
            )
        )
    await session.flush()
    for game_id in games:
        for profile_id in profiles:
            session.add(MatchPlayer(game_id=game_id, profile_id=profile_id, color_id=colour))
    await session.flush()


async def test_colour_fills_add_two_statements_whatever_their_number(
    db_session: AsyncSession, recorder: _Recorder
) -> None:
    """The fills are one ascending lock pass (`SELECT ... ORDER BY ... FOR UPDATE`) and one
    `UPDATE ... FROM (VALUES ...)`: five statements for a batch plus 400 fills, the same five for
    a batch plus 4. Supplied in descending order — the helper owns the order."""
    games = list(range(600_000, 600_200))
    await _stored_match_players(db_session, games, (11, 12), colour=None)

    async def run(count: int) -> list[str]:
        recorder.statements.clear()
        fills = {(game_id, profile_id): 5 for game_id in games[:count] for profile_id in (12, 11)}
        await persist_matches_and_profiles(
            db_session, [_match(1, (3, 2, 1))], colour_fills=dict(reversed(fills.items()))
        )
        return list(recorder.statements)

    many = await run(200)
    few = await run(2)

    assert len(many) == len(few) == 5, many
    lock, upsert, update = many[2], many[3], many[4]
    assert upsert.startswith("INSERT INTO match_players")
    assert lock.startswith("SELECT") and "ORDER BY match_players.game_id" in lock
    assert lock.rstrip().endswith("FOR UPDATE")
    assert update.startswith("UPDATE match_players")


async def test_colour_fills_replace_nothing_that_is_stored(db_session: AsyncSession) -> None:
    """Companion fills a `NULL` colour and nothing else; a fill for a row that does not exist
    changes nothing and raises nothing."""
    await _stored_match_players(db_session, [700_001], (21, 22), colour=None)
    await db_session.execute(
        update(MatchPlayer)
        .where(MatchPlayer.game_id == 700_001, MatchPlayer.profile_id == 21)
        .values(color_id=3)
    )

    await persist_matches_and_profiles(
        db_session,
        [],
        colour_fills={(700_001, 21): 9, (700_001, 22): 9, (700_999, 21): 9},
    )

    colours = dict(
        (await db_session.execute(select(MatchPlayer.profile_id, MatchPlayer.color_id))).all()
    )
    assert colours == {21: 3, 22: 9}


async def test_recorder_sees_every_row_of_an_executemany(
    db_session: AsyncSession, recorder: _Recorder
) -> None:
    """Two `match_players` rows added through the ORM are one `executemany`; the recorder must
    list a row per parameter set, in order, not skip the statement."""
    await _stored_match_players(db_session, [800_001], (31,), colour=None)
    db_session.add(AoeProfile(profile_id=32, alias="32"))
    db_session.add(AoeProfile(profile_id=33, alias="33"))
    await db_session.flush()
    recorder.inserts.clear()

    db_session.add_all(
        [MatchPlayer(game_id=800_001, profile_id=profile_id) for profile_id in (33, 32)]
    )
    await db_session.flush()

    assert recorder.inserts == [
        ("match_players", [(800_001, 33)]),
        ("match_players", [(800_001, 32)]),
    ]
