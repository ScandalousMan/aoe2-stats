"""Repository tests for the `MatchListRow` widening (T422, contracts/http-api.md `GET
/api/matches` delta, data-model.md §3).

Three properties, each named in the task:

1. `MatchListRow` gains `rating`, `team_id` and `color_id` — FR-005 needs the absolute rating and
   the list row has never carried one; only match *detail* did (research.md D7).
2. A sibling projection returns *every* participant of a match, the viewer included — `opponents`
   (`_opponents_by_game`) deliberately never lists the caller's own row, and US1 needs everyone's
   colour and team, not only the opponents'.
3. `opponents` keeps its shape (the `Opponent` dataclass is untouched — `participants` is a
   sibling, not a replacement) and its *exclusion* contract sharpens: `_opponents_by_game` excludes
   teammates by a `team_id` filter that excludes nothing while the caller's `team_id` is `NULL`,
   and every `team_id` is `NULL` in production until T413/T415 run — so a team match's `opponents`
   excluding teammates has never been observable end to end. It *is* observable directly at this
   layer, by seeding `team_id` on the row (module `test_matches.py`'s own precedent), and the
   exclusion logic itself already exists (`_opponents_by_game`'s own docstring, "T070d"). That
   assertion is written and executed below rather than skipped — it is expected to already hold —
   but the test as a whole still fails today because it also reaches for the not-yet-existent
   `participants` sibling on the very same row, exactly as `test_models.py`'s 003 section does for
   a column T304 had not yet added: "the module itself already exists and already imports cleanly
   either way — what does not exist yet is each specific field ... reached for below, and reaching
   for a missing key ... raises inside the test body", an ordinary assertion-time failure
   `xfail(strict=True)` reports as expected, not a collection-time error that would take the rest
   of this file down with it.

Same harness discipline as `tests/repositories/test_matches.py`: real queries against the T015
throwaway-database fixtures (`tests/db.py`), because a projection query and a join's exclusion
predicate are exactly what a fake session cannot exercise honestly. This file is deliberately
self-contained (its own seed helpers) rather than importing `tests/repositories/test_matches.py`'s
— T422 runs in parallel with five siblings sharing this working tree and must not modify a file
outside its own named path.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from tests.db import clean_database, database_url, db_session, engine, session_factory

from aoe2stats_storage.models import AoeProfile, Match, MatchPlayer

# Re-exported so ruff sees these names used, exactly as `tests/repositories/test_matches.py` does:
# pytest discovers a fixture imported into a module exactly as if it had been defined there.
__all__ = ["clean_database", "database_url", "db_session", "engine", "session_factory"]

_CALLER_PROFILE_ID = 522_000_001
_TEAMMATE_PROFILE_ID = 522_000_002
_OPPONENT_ONE_PROFILE_ID = 522_000_003
_OPPONENT_TWO_PROFILE_ID = 522_000_004
_LEADERBOARD_1V1_RM = 3


async def _seed_profile(
    session: AsyncSession, *, profile_id: int, alias: str, country: str | None = None
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
) -> None:
    session.add(
        Match(
            game_id=game_id,
            leaderboard_id=leaderboard_id,
            map_name=map_name,
            started_at=completed_at - timedelta(seconds=1800),
            completed_at=completed_at,
            duration_seconds=1800,
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
    team_id: int | None,
    civ_id: int | None = None,
    color_id: int | None = None,
    result: str | None = None,
    rating: int | None = None,
    rating_diff: int | None = None,
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


async def test_match_list_row_carries_rating_team_id_and_color_id(
    db_session: AsyncSession,
) -> None:
    """FR-005's `922 (+16)` needs the absolute rating; FR-003 needs the colour; the winning side
    needs the team. None of the three are on `MatchListRow` today — only match detail's
    `MatchParticipant` carries them (data-model.md §3)."""
    from aoe2stats_storage.repositories.matches import MatchesRepository

    await _seed_profile(db_session, profile_id=_CALLER_PROFILE_ID, alias="Caller", country="fr")
    await _seed_profile(
        db_session, profile_id=_OPPONENT_ONE_PROFILE_ID, alias="Opponent", country="cz"
    )
    now = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
    game_id = 622_001
    await _seed_match(db_session, game_id=game_id, completed_at=now)
    await _seed_match_player(
        db_session,
        game_id=game_id,
        profile_id=_CALLER_PROFILE_ID,
        team_id=1,
        civ_id=28,
        color_id=4,
        result="win",
        rating=922,
        rating_diff=16,
    )
    await _seed_match_player(
        db_session,
        game_id=game_id,
        profile_id=_OPPONENT_ONE_PROFILE_ID,
        team_id=2,
        civ_id=9,
        color_id=6,
        result="loss",
        rating=1400,
        rating_diff=-16,
    )
    await db_session.commit()

    repository = MatchesRepository(db_session)
    page = await repository.list_matches(profile_id=_CALLER_PROFILE_ID)

    assert len(page.matches) == 1
    row = page.matches[0]
    # `MatchListRow` is a frozen, slotted dataclass (`repositories/matches.py`): reaching for a
    # field it does not yet declare raises `AttributeError` here, not a collection-time import
    # error, exactly like `test_models.py`'s 003 section reaching into `Base.metadata`.
    assert row.rating == 922
    assert row.team_id == 1
    assert row.color_id == 4


async def test_participants_projection_returns_every_participant_the_viewer_included(
    db_session: AsyncSession,
) -> None:
    """`opponents` never lists the caller's own row (`Opponent`'s own docstring). US1 needs every
    player's colour and team on a match row, the viewer's own included, so `participants` is a
    sibling projection and not a widening of `opponents` itself (data-model.md §3, contracts/
    http-api.md's `participants[]`)."""
    from aoe2stats_storage.repositories.matches import MatchesRepository

    await _seed_profile(db_session, profile_id=_CALLER_PROFILE_ID, alias="Caller", country="fr")
    await _seed_profile(
        db_session, profile_id=_OPPONENT_ONE_PROFILE_ID, alias="Somero", country="cz"
    )
    now = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
    game_id = 622_002
    await _seed_match(db_session, game_id=game_id, completed_at=now)
    await _seed_match_player(
        db_session,
        game_id=game_id,
        profile_id=_CALLER_PROFILE_ID,
        team_id=1,
        civ_id=28,
        color_id=4,
        result="win",
        rating=1512,
        rating_diff=14,
    )
    await _seed_match_player(
        db_session,
        game_id=game_id,
        profile_id=_OPPONENT_ONE_PROFILE_ID,
        team_id=2,
        civ_id=9,
        color_id=6,
        result="loss",
        rating=1400,
        rating_diff=-14,
    )
    await db_session.commit()

    repository = MatchesRepository(db_session)
    page = await repository.list_matches(profile_id=_CALLER_PROFILE_ID)

    assert len(page.matches) == 1
    row = page.matches[0]

    # `participants` does not exist on `MatchListRow` yet — this is the line T423 makes pass.
    participant_ids = {participant.profile_id for participant in row.participants}
    assert participant_ids == {_CALLER_PROFILE_ID, _OPPONENT_ONE_PROFILE_ID}, (
        "the viewer's own row must be present in `participants` — the property `opponents` "
        "deliberately never has."
    )

    by_profile = {participant.profile_id: participant for participant in row.participants}
    caller_participant = by_profile[_CALLER_PROFILE_ID]
    assert caller_participant.alias == "Caller"
    assert caller_participant.country == "fr"
    assert caller_participant.team_id == 1
    assert caller_participant.civ_id == 28
    assert caller_participant.color_id == 4
    assert caller_participant.result == "win"
    assert caller_participant.rating == 1512
    assert caller_participant.rating_diff == 14

    opponent_participant = by_profile[_OPPONENT_ONE_PROFILE_ID]
    assert opponent_participant.alias == "Somero"
    assert opponent_participant.country == "cz"
    assert opponent_participant.team_id == 2
    assert opponent_participant.civ_id == 9
    assert opponent_participant.color_id == 6
    assert opponent_participant.result == "loss"
    assert opponent_participant.rating == 1400
    assert opponent_participant.rating_diff == -14


async def test_opponents_keeps_its_shape_and_excludes_teammates_once_team_id_is_populated(
    db_session: AsyncSession,
) -> None:
    """`opponents`'s *shape* is unchanged (the `Opponent` dataclass gains no field: `participants`
    is a sibling, not a replacement — data-model.md §3). Its *content* sharpens: every `team_id`
    is `NULL` in production today (research.md D1), so `_opponents_by_game`'s own documented
    fallback — "when the caller's own `team_id` is itself `NULL` there is nothing to compare
    against, so nothing is excluded" — is the only behaviour anyone has ever observed end to end.
    Once `team_id` is populated (T413/T415), a team match's `opponents` must exclude teammates;
    that property has never been observable before this feature (contracts/http-api.md, `GET
    /api/matches`) and gets no coverage anywhere else, so it is asserted here directly against a
    row where `team_id` is seeded non-`NULL` for every participant.

    The exclusion assertion below is expected to already hold — `_opponents_by_game`'s teammate
    filter has done this since T070d, well before this feature — so it is not what makes this test
    fail today. What still fails is the second half: the same row's `participants` sibling, which
    T423 has not added yet, must include the teammate `opponents` correctly excludes. The whole
    test is therefore still `xfail(strict=True, reason="T423 not implemented yet")`, and once T423
    lands, every assertion here — the pre-existing exclusion behaviour included — must hold at
    once for the marker's removal to be honest.
    """
    from aoe2stats_storage.repositories.matches import MatchesRepository, Opponent

    await _seed_profile(db_session, profile_id=_CALLER_PROFILE_ID, alias="Caller")
    await _seed_profile(db_session, profile_id=_TEAMMATE_PROFILE_ID, alias="Teammate")
    await _seed_profile(db_session, profile_id=_OPPONENT_ONE_PROFILE_ID, alias="OpponentOne")
    await _seed_profile(db_session, profile_id=_OPPONENT_TWO_PROFILE_ID, alias="OpponentTwo")
    now = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
    game_id = 622_003
    await _seed_match(db_session, game_id=game_id, completed_at=now, leaderboard_id=4)
    await _seed_match_player(
        db_session, game_id=game_id, profile_id=_CALLER_PROFILE_ID, team_id=1, result="win"
    )
    await _seed_match_player(
        db_session, game_id=game_id, profile_id=_TEAMMATE_PROFILE_ID, team_id=1, result="win"
    )
    await _seed_match_player(
        db_session, game_id=game_id, profile_id=_OPPONENT_ONE_PROFILE_ID, team_id=2, result="loss"
    )
    await _seed_match_player(
        db_session, game_id=game_id, profile_id=_OPPONENT_TWO_PROFILE_ID, team_id=2, result="loss"
    )
    await db_session.commit()

    repository = MatchesRepository(db_session)
    page = await repository.list_matches(profile_id=_CALLER_PROFILE_ID)

    assert len(page.matches) == 1
    row = page.matches[0]

    # --- shape: `Opponent` is untouched by this feature -----------------------------------------
    opponent_field_names = {field.name for field in dataclasses.fields(Opponent)}
    assert opponent_field_names == {"profile_id", "alias", "civ_id"}

    # --- exclusion contract: sharpens once `team_id` is populated, already true today -----------
    opponent_ids = {opponent.profile_id for opponent in row.opponents}
    assert opponent_ids == {_OPPONENT_ONE_PROFILE_ID, _OPPONENT_TWO_PROFILE_ID}, (
        "a team match's `opponents` must exclude teammates once `team_id` is known — the caller's "
        f"own row and the teammate's must both be absent. Got {opponent_ids!r}."
    )
    assert _TEAMMATE_PROFILE_ID not in opponent_ids
    assert _CALLER_PROFILE_ID not in opponent_ids

    # --- `participants` is the sibling that still does not exist ---------------------------------
    participant_ids = {participant.profile_id for participant in row.participants}
    assert participant_ids == {
        _CALLER_PROFILE_ID,
        _TEAMMATE_PROFILE_ID,
        _OPPONENT_ONE_PROFILE_ID,
        _OPPONENT_TWO_PROFILE_ID,
    }, "`participants` carries every participant, teammates and the viewer included."
