"""Integration tests for `aoe2stats_storage.repositories.matches.MatchesRepository` (T069).

Same harness discipline as `test_ratings.py`: real queries against the T015 throwaway-database
fixtures (`tests/db.py`), imported rather than redefined, because `list_matches`' and
`get_match_detail`'s whole job — the join to `match_players`, the cursor's row-wise `<` seek, the
outer join to `replay_captures` — is exactly what a fake session cannot exercise honestly.

These tests assert the repository directly, not through `apps/api`'s router. `apps/api/tests/
test_matches_list.py`, `test_match_detail.py` and `test_capture_visibility.py` already fix the
HTTP-level contract this repository must satisfy; this file is scoped to what belongs at this
layer: ordering, cursor stability under insertion, and that capture status travels through
unmodified.

**`get_match_detail` carries no ownership scope since T327 (FR-018, FR-021).** Before T327,
`owner_profile_ids` (a set of the caller's own linked profile ids) gated the whole result: `None`
unless at least one of them took part. That gate is gone — the tests below with `since_t327` in
their name are what used to assert the opposite. `owner_profile_ids` still narrows exactly one
thing, FR-022's own archival state (never a co-participant's), which is what the remaining
`owner_profile_ids`-scoped assertions below exercise. `list_matches` keeps its own, unrelated
scope: one pre-validated `profile_id`, proven by the caller by the time it reaches this repository.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from tests.db import clean_database, database_url, db_session, engine, session_factory

from aoe2stats_storage.models import (
    AoeProfile,
    CaptureSource,
    CaptureStatus,
    Match,
    MatchPlayer,
    ReplayCapture,
)
from aoe2stats_storage.repositories.matches import MatchesRepository

# Re-exported so ruff sees these names used, exactly as `test_ratings.py` does: pytest discovers a
# fixture imported into a module exactly as if it had been defined there.
__all__ = ["clean_database", "database_url", "db_session", "engine", "session_factory"]

_CALLER_PROFILE_ID = 501_000_001
_OPPONENT_PROFILE_ID = 501_000_002
_LEADERBOARD_1V1_RM = 3


async def _seed_profile(
    session: AsyncSession, *, profile_id: int, alias: str = "Player", country: str | None = "FR"
) -> None:
    session.add(AoeProfile(profile_id=profile_id, alias=alias, country=country))
    await session.flush()


async def _seed_match(
    session: AsyncSession,
    *,
    game_id: int,
    completed_at: datetime,
    map_name: str = "Arabia",
    leaderboard_id: int = _LEADERBOARD_1V1_RM,
    duration_seconds: int = 1800,
) -> None:
    session.add(
        Match(
            game_id=game_id,
            leaderboard_id=leaderboard_id,
            map_name=map_name,
            started_at=completed_at - timedelta(seconds=duration_seconds),
            completed_at=completed_at,
            duration_seconds=duration_seconds,
            source="relic",
            raw_payload={"game_id": game_id},
        )
    )
    await session.flush()


async def _seed_match_player(
    session: AsyncSession,
    *,
    game_id: int,
    profile_id: int,
    team_id: int = 1,
    civ_id: int = 1,
    color_id: int = 1,
    result: str = "win",
    rating: int = 1500,
    rating_diff: int = 15,
) -> None:
    session.add(
        MatchPlayer(
            game_id=game_id,
            profile_id=profile_id,
            team_id=team_id,
            civ_id=civ_id,
            color_id=color_id,
            result=result,
            rating=rating,
            rating_diff=rating_diff,
        )
    )
    await session.flush()


async def _seed_capture(
    session: AsyncSession,
    *,
    game_id: int,
    profile_id: int,
    status: CaptureStatus,
    capture_deadline_at: datetime,
) -> None:
    session.add(
        ReplayCapture(
            game_id=game_id,
            profile_id=profile_id,
            status=status,
            capture_deadline_at=capture_deadline_at,
            first_seen_at=capture_deadline_at - timedelta(days=21),
            source=CaptureSource.AUTOMATIC,
        )
    )
    await session.flush()


async def _seed_full_match(
    session: AsyncSession,
    *,
    game_id: int,
    completed_at: datetime,
    caller_profile_id: int = _CALLER_PROFILE_ID,
    opponent_profile_id: int = _OPPONENT_PROFILE_ID,
    caller_civ_id: int = 1,
    caller_result: str = "win",
    caller_rating_diff: int = 15,
    capture_status: CaptureStatus | None = CaptureStatus.STORED,
    map_name: str = "Arabia",
) -> None:
    """One match, both `match_players` rows, and (unless `capture_status` is `None`) a capture row
    for the caller — the shape most tests below need."""
    await _seed_match(session, game_id=game_id, completed_at=completed_at, map_name=map_name)
    await _seed_match_player(
        session,
        game_id=game_id,
        profile_id=caller_profile_id,
        civ_id=caller_civ_id,
        result=caller_result,
        rating_diff=caller_rating_diff,
    )
    await _seed_match_player(
        session,
        game_id=game_id,
        profile_id=opponent_profile_id,
        team_id=2,
        civ_id=2,
        result="loss" if caller_result == "win" else "win",
        rating_diff=-caller_rating_diff,
    )
    if capture_status is not None:
        await _seed_capture(
            session,
            game_id=game_id,
            profile_id=caller_profile_id,
            status=capture_status,
            capture_deadline_at=completed_at + timedelta(days=21),
        )


async def _seed_callers_and_opponent(db_session: AsyncSession) -> None:
    await _seed_profile(db_session, profile_id=_CALLER_PROFILE_ID, alias="Caller")
    await _seed_profile(db_session, profile_id=_OPPONENT_PROFILE_ID, alias="Opponent")


# --- list_matches: ordering, fields, capture status --------------------------------------------


async def test_list_matches_orders_newest_first_and_carries_fr010_fields(
    db_session: AsyncSession,
) -> None:
    await _seed_callers_and_opponent(db_session)
    now = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
    oldest, middle, newest = 601_001, 601_002, 601_003

    await _seed_full_match(
        db_session,
        game_id=oldest,
        completed_at=now - timedelta(days=2),
        caller_civ_id=10,
        caller_result="loss",
        caller_rating_diff=-12,
        map_name="Black Forest",
    )
    await _seed_full_match(
        db_session,
        game_id=middle,
        completed_at=now - timedelta(days=1),
        caller_civ_id=11,
        caller_result="win",
        caller_rating_diff=20,
        map_name="Arena",
    )
    await _seed_full_match(
        db_session,
        game_id=newest,
        completed_at=now,
        caller_civ_id=12,
        caller_result="win",
        caller_rating_diff=18,
        map_name="Arabia",
    )
    await db_session.commit()

    repository = MatchesRepository(db_session)
    page = await repository.list_matches(profile_id=_CALLER_PROFILE_ID)

    assert [row.game_id for row in page.matches] == [newest, middle, oldest]
    assert page.next_cursor is None

    newest_row = page.matches[0]
    assert newest_row.map_name == "Arabia"
    assert newest_row.civilisation == 12
    assert newest_row.result == "win"
    assert newest_row.rating_diff == 18
    assert newest_row.duration_seconds == 1800
    assert newest_row.capture_status == CaptureStatus.STORED
    assert newest_row.capture_deadline_at == now + timedelta(days=21)

    opponent_ids = {opponent.profile_id for opponent in newest_row.opponents}
    assert opponent_ids == {_OPPONENT_PROFILE_ID}
    assert newest_row.opponents[0].alias == "Opponent"
    assert newest_row.opponents[0].civ_id == 2


async def test_list_matches_scopes_strictly_to_the_given_profile_id(
    db_session: AsyncSession,
) -> None:
    """A match the caller never played must never appear, even if it exists (module docstring:
    restriction is baked into the join, not a later filter)."""
    await _seed_callers_and_opponent(db_session)
    other_profile_id = 501_000_099
    await _seed_profile(db_session, profile_id=other_profile_id, alias="SomeoneElse")
    now = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)

    await _seed_full_match(
        db_session, game_id=602_001, completed_at=now, caller_profile_id=_CALLER_PROFILE_ID
    )
    await _seed_full_match(
        db_session,
        game_id=602_002,
        completed_at=now,
        caller_profile_id=other_profile_id,
        opponent_profile_id=_OPPONENT_PROFILE_ID,
    )
    await db_session.commit()

    repository = MatchesRepository(db_session)
    page = await repository.list_matches(profile_id=_CALLER_PROFILE_ID)

    assert [row.game_id for row in page.matches] == [602_001]


async def test_list_matches_reports_none_capture_status_when_no_capture_row_exists(
    db_session: AsyncSession,
) -> None:
    """A match discovered but not yet carrying a `replay_captures` row still comes back (outer
    join, module docstring) rather than being dropped."""
    await _seed_callers_and_opponent(db_session)
    now = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
    await _seed_full_match(db_session, game_id=603_001, completed_at=now, capture_status=None)
    await db_session.commit()

    repository = MatchesRepository(db_session)
    page = await repository.list_matches(profile_id=_CALLER_PROFILE_ID)

    assert len(page.matches) == 1
    assert page.matches[0].capture_status is None
    assert page.matches[0].capture_deadline_at is None


async def test_list_matches_reports_every_raw_capture_status_intact(
    db_session: AsyncSession,
) -> None:
    """Per T073: the collapse into a badge's "lost"/"safe"/"needs review" happens in the
    component, never here — every one of the seven raw statuses must survive unchanged."""
    await _seed_callers_and_opponent(db_session)
    now = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
    statuses = {
        604_001: CaptureStatus.PENDING,
        604_002: CaptureStatus.DOWNLOADING,
        604_003: CaptureStatus.UNAVAILABLE,
        604_004: CaptureStatus.EXPIRED,
        604_005: CaptureStatus.QUARANTINED,
        604_006: CaptureStatus.FAILED,
    }
    for offset, (game_id, status) in enumerate(statuses.items()):
        await _seed_full_match(
            db_session,
            game_id=game_id,
            completed_at=now - timedelta(hours=offset),
            capture_status=status,
        )
    await db_session.commit()

    repository = MatchesRepository(db_session)
    page = await repository.list_matches(profile_id=_CALLER_PROFILE_ID, limit=len(statuses))

    reported = {row.game_id: row.capture_status for row in page.matches}
    assert reported == statuses


# --- list_matches: cursor pagination -------------------------------------------------------------


async def test_list_matches_limit_returns_a_next_cursor_when_more_rows_remain(
    db_session: AsyncSession,
) -> None:
    await _seed_callers_and_opponent(db_session)
    now = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
    for offset, game_id in enumerate((701_001, 701_002, 701_003)):
        await _seed_full_match(
            db_session, game_id=game_id, completed_at=now - timedelta(days=offset)
        )
    await db_session.commit()

    repository = MatchesRepository(db_session)
    page = await repository.list_matches(profile_id=_CALLER_PROFILE_ID, limit=2)

    assert [row.game_id for row in page.matches] == [701_001, 701_002]
    assert page.next_cursor is not None


async def test_list_matches_cursor_pagination_is_stable_across_insertions(
    db_session: AsyncSession,
) -> None:
    """The property that distinguishes a cursor from `OFFSET`: a match inserted *above* an
    already-issued cursor must not shift, duplicate or skip anything the next page returns."""
    await _seed_callers_and_opponent(db_session)
    now = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
    # Oldest first, so insertion order can never be mistaken for the ordering under test.
    for offset, game_id in ((3, 801_001), (2, 801_002), (1, 801_003), (0, 801_004)):
        await _seed_full_match(
            db_session, game_id=game_id, completed_at=now - timedelta(days=offset)
        )
    await db_session.commit()

    repository = MatchesRepository(db_session)
    page_one = await repository.list_matches(profile_id=_CALLER_PROFILE_ID, limit=2)
    assert [row.game_id for row in page_one.matches] == [801_004, 801_003]
    cursor = page_one.next_cursor
    assert cursor is not None

    # A brand-new match, newer than everything already seen.
    await _seed_full_match(db_session, game_id=801_005, completed_at=now + timedelta(days=1))
    await db_session.commit()

    page_two = await repository.list_matches(profile_id=_CALLER_PROFILE_ID, cursor=cursor, limit=2)
    assert [row.game_id for row in page_two.matches] == [801_002, 801_001]
    assert page_two.next_cursor is None

    fresh_page_one = await repository.list_matches(profile_id=_CALLER_PROFILE_ID, limit=2)
    assert [row.game_id for row in fresh_page_one.matches] == [801_005, 801_004]


async def test_list_matches_empty_history_returns_an_empty_page(db_session: AsyncSession) -> None:
    await _seed_profile(db_session, profile_id=_CALLER_PROFILE_ID, alias="Caller")
    await db_session.commit()

    repository = MatchesRepository(db_session)
    page = await repository.list_matches(profile_id=_CALLER_PROFILE_ID)

    assert page.matches == []
    assert page.next_cursor is None


async def test_list_matches_rejects_a_non_positive_limit(db_session: AsyncSession) -> None:
    repository = MatchesRepository(db_session)
    with pytest.raises(ValueError, match="limit must be positive"):
        await repository.list_matches(profile_id=_CALLER_PROFILE_ID, limit=0)


async def test_list_matches_rejects_a_malformed_cursor(db_session: AsyncSession) -> None:
    repository = MatchesRepository(db_session)
    with pytest.raises(ValueError, match="invalid matches cursor"):
        await repository.list_matches(profile_id=_CALLER_PROFILE_ID, cursor="not-a-real-cursor!!")


# --- get_match_detail: FR-011, ownership, FR-038's identical not_found signal --------------------


async def test_get_match_detail_lists_every_participant_with_fr011_fields(
    db_session: AsyncSession,
) -> None:
    await _seed_callers_and_opponent(db_session)
    now = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
    await _seed_full_match(
        db_session,
        game_id=901_001,
        completed_at=now,
        caller_civ_id=5,
        caller_result="win",
        caller_rating_diff=14,
    )
    await db_session.commit()

    repository = MatchesRepository(db_session)
    detail = await repository.get_match_detail(
        game_id=901_001, owner_profile_ids=[_CALLER_PROFILE_ID]
    )

    assert detail is not None
    assert detail.game_id == 901_001
    by_profile = {p.profile_id: p for p in detail.participants}
    assert set(by_profile) == {_CALLER_PROFILE_ID, _OPPONENT_PROFILE_ID}
    caller_row = by_profile[_CALLER_PROFILE_ID]
    assert caller_row.alias == "Caller"
    assert caller_row.team_id == 1
    assert caller_row.civ_id == 5
    assert caller_row.result == "win"
    assert caller_row.rating_diff == 14
    opponent_row = by_profile[_OPPONENT_PROFILE_ID]
    assert opponent_row.team_id == 2
    assert opponent_row.result == "loss"
    assert opponent_row.rating_diff == -14


async def test_get_match_detail_returns_none_for_an_unknown_game_id(
    db_session: AsyncSession,
) -> None:
    repository = MatchesRepository(db_session)
    detail = await repository.get_match_detail(
        game_id=999_999, owner_profile_ids=[_CALLER_PROFILE_ID]
    )
    assert detail is None


async def test_get_match_detail_is_readable_when_no_owner_profile_took_part_since_t327(
    db_session: AsyncSession,
) -> None:
    """FR-018/FR-021 (T327): a real match none of `owner_profile_ids` played must still come back
    in full — the pre-widening behaviour this function used to assert (`None`, the identical
    signal an unknown `game_id` gives, per FR-038/T067) is exactly what T327 removed. Contrast
    with `test_get_match_detail_returns_none_for_an_unknown_game_id` right above: same call shape,
    one `game_id` that names nothing at all (`None`) against one that names a real match `owner_
    profile_ids` did not play (a full `MatchDetail`) — the boundary this method now draws is
    existence, never ownership."""
    await _seed_callers_and_opponent(db_session)
    stranger_profile_id = 501_000_050
    await _seed_profile(db_session, profile_id=stranger_profile_id, alias="Stranger")
    now = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
    await _seed_match(db_session, game_id=902_001, completed_at=now)
    await _seed_match_player(db_session, game_id=902_001, profile_id=stranger_profile_id)
    await _seed_match_player(
        db_session, game_id=902_001, profile_id=_OPPONENT_PROFILE_ID, team_id=2
    )
    await db_session.commit()

    repository = MatchesRepository(db_session)
    detail = await repository.get_match_detail(
        game_id=902_001, owner_profile_ids=[_CALLER_PROFILE_ID]
    )

    assert detail is not None, (
        "FR-018/FR-021: a match none of the caller's own profiles played must still be readable."
    )
    assert {p.profile_id for p in detail.participants} == {
        stranger_profile_id,
        _OPPONENT_PROFILE_ID,
    }
    # FR-022's contrapositive: the caller took no part, so there is no archival state of their own
    # to report, and none of the participants' own capture rows leaks in its place — none were
    # seeded here in the first place, so `None` is the only honest answer.
    assert detail.capture_status is None
    assert detail.capture_deadline_at is None


async def test_get_match_detail_reachable_via_a_non_primary_owned_profile(
    db_session: AsyncSession,
) -> None:
    """FR-043: every linked profile stays reachable, not only the primary one — passing the
    caller's full set of active profile ids is what makes that true at this layer."""
    await _seed_callers_and_opponent(db_session)
    secondary_profile_id = 501_000_003
    await _seed_profile(db_session, profile_id=secondary_profile_id, alias="Secondary")
    now = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
    await _seed_match(db_session, game_id=903_001, completed_at=now)
    await _seed_match_player(db_session, game_id=903_001, profile_id=secondary_profile_id)
    await _seed_match_player(
        db_session, game_id=903_001, profile_id=_OPPONENT_PROFILE_ID, team_id=2
    )
    await db_session.commit()

    repository = MatchesRepository(db_session)
    detail = await repository.get_match_detail(
        game_id=903_001, owner_profile_ids=[_CALLER_PROFILE_ID, secondary_profile_id]
    )

    assert detail is not None
    assert {p.profile_id for p in detail.participants} == {
        secondary_profile_id,
        _OPPONENT_PROFILE_ID,
    }


async def test_get_match_detail_is_readable_for_an_empty_owner_set_since_t327(
    db_session: AsyncSession,
) -> None:
    """FR-018 (T327): a caller with no active linked profiles at all (`owner_profile_ids=[]`, the
    empty set) is still "any signed-in caller" — the match comes back in full. `_seed_full_match`'s
    default already gives `_CALLER_PROFILE_ID` a `stored` capture row (a genuine participant's own
    replay, seeded regardless of who is asking), so this also proves the empty owner set truly
    excludes it from the join rather than merely happening to have nothing to find — FR-022's own
    archival state is never shown for a caller who owns nothing, even when a capture row exists for
    someone who played."""
    await _seed_callers_and_opponent(db_session)
    now = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
    await _seed_full_match(db_session, game_id=904_001, completed_at=now)
    await db_session.commit()

    repository = MatchesRepository(db_session)
    detail = await repository.get_match_detail(game_id=904_001, owner_profile_ids=[])

    assert detail is not None
    assert {p.profile_id for p in detail.participants} == {
        _CALLER_PROFILE_ID,
        _OPPONENT_PROFILE_ID,
    }
    assert detail.capture_status is None, (
        "FR-022: an owner set the caller does not control must never surface someone else's "
        f"archival state. Got {detail.capture_status!r}."
    )
    assert detail.capture_deadline_at is None
