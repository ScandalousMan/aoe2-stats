"""Integration tests for `POST /api/privacy/object` (T088) — FR-039, T092 not implemented yet.

`contracts/http-api.md`'s Privacy section names this route "the one unauthenticated write in the
system": the person objecting appears in an archived match as someone else's opponent or teammate,
never signed in, and by definition has no session to carry. Two things follow from that, and a
third the same paragraph states directly:

- **Unauthenticated by design.** The route must be reachable with no `session_id` cookie at all —
  refusing an anonymous caller here would refuse the one caller the route exists for.
- **Rate limited.** The absence of a session is exactly what makes this route a denial-of-service
  vector against the data if it is not throttled: unlike every other write in this API, there is no
  per-user identity to scope a limit to, so nothing about *who* is calling stops a scripted flood.
- **Records rather than acts.** `data-model.md`'s `data_requests` section and this contract both
  say the same thing in different words: this call writes a row for a human to resolve later, and
  does not pseudonymise anything itself. FR-039's pseudonymisation instrument is T091's — erasure
  calls it for the departing user's own `profile_id`, and T092's resolution step is its *other*
  caller, later and by a person, not by this request. Immediate pseudonymisation on an
  unauthenticated call would let anyone silently rewrite `match_players` for any profile they name,
  which is the exact denial-of-service surface the "records rather than acts" design closes.

None of this route's implementation (`apps/api/src/aoe2stats_api/routers/privacy.py`, T092) exists
yet, so every test below is `xfail(strict=True)`: the assertions run for real against the app this
suite already builds (`client`, `apps/api/tests/conftest.py`), and today's honest failure is a 404
for a route FastAPI has never heard of — not an import error, since nothing here imports anything
T092 has not written. The marker comes off the moment T092 makes these pass, which is what turns a
regression back into a red test instead of a silently stale one (T025a's convention, `CLAUDE.md`).

**Request body.** Nothing in `contracts/http-api.md` or `data-model.md` fixes its shape, only that
the row it produces carries a `subject_profile_id` (`data_requests`). `{"profile_id": ...}` is the
one field the schema actually has a column for, so it is what these tests send; T092 is free to
accept more, never less.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_storage.models import AoeProfile, DataRequest, DataRequestKind, Match, MatchPlayer

pytestmark = [pytest.mark.usefixtures("environment")]

# Comfortably beyond any rate limit this route could reasonably carry (the sibling buckets in
# `.env.example` top out at 20/minute) without depending on a specific numeric knob T092 has not
# declared yet — the property under test is that *some* request in this run is refused, not which
# one.
_ATTEMPTS = 100


async def _seed_third_party_match(
    db_session: AsyncSession, *, objecting_profile_id: int, other_profile_id: int
) -> int:
    """A match with two participants, neither of them a signed-in user — exactly the situation
    FR-039 exists for: a non-user appearing in an archived match. Returns `game_id`."""
    now = datetime.now(UTC)
    game_id = 900_000_001

    db_session.add_all(
        [
            AoeProfile(
                profile_id=objecting_profile_id,
                alias="Objecting Third Party",
                first_seen_at=now,
                last_seen_at=now,
            ),
            AoeProfile(
                profile_id=other_profile_id,
                alias="Other Participant",
                first_seen_at=now,
                last_seen_at=now,
            ),
            Match(
                game_id=game_id,
                leaderboard_id=3,
                completed_at=now,
                source="relic",
                raw_payload={},
            ),
        ]
    )
    await db_session.flush()

    db_session.add_all(
        [
            MatchPlayer(
                game_id=game_id,
                profile_id=objecting_profile_id,
                team_id=1,
                result="win",
            ),
            MatchPlayer(
                game_id=game_id,
                profile_id=other_profile_id,
                team_id=2,
                result="loss",
            ),
        ]
    )
    await db_session.commit()
    return game_id


@pytest.mark.xfail(strict=True, reason="T092 not implemented yet")
def test_object_endpoint_is_reachable_without_a_session(client: TestClient) -> None:
    """The person objecting is by definition not a user (module docstring): a bare `client`, with
    no `session_id` cookie set anywhere in this test, must be able to reach the route at all.
    Neither `401 not_authenticated` (the shape every other `/api/privacy/*` route answers an
    anonymous caller) nor a 404 for a route that does not exist yet is acceptable once T092
    ships."""
    response = client.post("/api/privacy/object", json={"profile_id": 900_000_101})

    assert response.status_code in (200, 202)
    assert response.status_code != 401


@pytest.mark.xfail(strict=True, reason="T092 not implemented yet")
def test_object_endpoint_is_rate_limited(client: TestClient) -> None:
    """No session means no per-user identity to scope a limit to, which is exactly why the
    contract calls this route out as needing one anyway: an unthrottled anonymous write would be a
    denial-of-service vector against the data (module docstring). Firing `_ATTEMPTS` requests from
    the one anonymous caller this test is must eventually be refused with the same `rate_limited`
    envelope every other throttled route in this API answers (`routers/players.py`,
    `routers/replays.py`)."""
    statuses = [
        client.post("/api/privacy/object", json={"profile_id": 900_000_102}).status_code
        for _ in range(_ATTEMPTS)
    ]

    assert 429 in statuses


@pytest.mark.xfail(strict=True, reason="T092 not implemented yet")
async def test_object_records_a_data_request_without_pseudonymising_immediately(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-039's "records rather than acts" property (module docstring): the call must leave
    `matches`/`match_players` exactly as they were the instant it returns, and its only visible
    effect must be a new `data_requests` row a human has not yet resolved."""
    objecting_profile_id = 900_000_201
    other_profile_id = 900_000_202
    game_id = await _seed_third_party_match(
        db_session,
        objecting_profile_id=objecting_profile_id,
        other_profile_id=other_profile_id,
    )

    before = await db_session.execute(select(MatchPlayer).where(MatchPlayer.game_id == game_id))
    match_players_before = {row.profile_id: row for row in before.scalars().all()}
    assert objecting_profile_id in match_players_before

    response = client.post("/api/privacy/object", json={"profile_id": objecting_profile_id})
    assert response.status_code in (200, 202)

    # No identifier pseudonymised immediately: the objecting profile's row is byte-identical right
    # after the call, and the participant who never objected is of course also untouched.
    after = await db_session.execute(select(MatchPlayer).where(MatchPlayer.game_id == game_id))
    match_players_after = {row.profile_id: row for row in after.scalars().all()}
    assert match_players_after.keys() == match_players_before.keys()
    for profile_id, before_row in match_players_before.items():
        after_row = match_players_after[profile_id]
        assert after_row.team_id == before_row.team_id
        assert after_row.result == before_row.result

    # The profile itself is not pseudonymised or removed either — the row a third party would need
    # to still exist for the human resolving this request to act on.
    profile = await db_session.get(AoeProfile, objecting_profile_id)
    assert profile is not None
    assert profile.profile_id == objecting_profile_id

    # The visible effect is a recorded, unresolved request — not an immediate action.
    recorded = await db_session.execute(
        select(DataRequest).where(DataRequest.subject_profile_id == objecting_profile_id)
    )
    data_requests = recorded.scalars().all()
    assert len(data_requests) == 1
    data_request = data_requests[0]
    assert data_request.kind == DataRequestKind.THIRD_PARTY_OBJECTION
    # Not a user: the objector is the subject of the request, not its account.
    assert data_request.subject_user_id is None
    assert data_request.requested_at is not None
    # Deferred to a human, not resolved by this call (module docstring's "records rather than
    # pseudonymising immediately").
    assert data_request.completed_at is None
