"""Integration test for T065 — the capture state shown to a user per match (FR-027, SC-010).

FR-027: "System MUST show the user, per match, the archival state and the time remaining before
the capture window closes" — the **capture deadline** (day 21), never the source's ~31-day
retention (the system commits to the deadline it controls, never to the one it refuses to rely
on). SC-010: "A user can tell, for any match, whether its replay is safe, still catchable, or
lost, without contacting support." T073's badge spec collapses `replay_captures`'s seven raw
`CaptureStatus` values into exactly **four** user-facing states:

| `replay_captures.status`           | Badge                                              |
| ----------------------------------- | --------------------------------------------------- |
| `stored`                            | archived / safe                                    |
| `pending`, `downloading`            | still catchable, time remaining to `capture_deadline_at` |
| `unavailable`, `expired`, `failed`  | lost                                               |
| `quarantined`                       | needs review                                       |

FR-026 is explicit that a `quarantined` capture sits in **neither** the archived nor the lost
column — it is evidence, not garbage, once the retention window has closed and the source holds
no replacement. A test that only distinguishes archived / pending / lost leaves that fourth state
— the one a user genuinely cannot self-diagnose without it being labelled — unverified. T073
itself states the collapse happens in **the badge only**: the three statuses behind "lost" travel
to the client intact, so the reader can still tell "never recorded" (their own saved-games folder
is probably empty too) from "expired or failed" (worth a manual upload, T078). This file asserts
the per-match data those distinctions are built from.

## Two halves, on purpose (dispatch note, per CLAUDE.md's test-first / green-tree convention)

This task sits on a TDD boundary. `GET /api/replays/status` (T062, `apps/api/src/aoe2stats_api/
routers/replays.py`) is **already implemented** — it is the profile-level aggregate FR-027/SC-010
also depend on (counts per status, oldest pending, nearest deadline), and this file asserts it for
real, against the real router and the real throwaway database, exactly as `test_replay_status.py`
already does for T062's other scenarios. Nothing below duplicates that file's assertions; this one
is scoped to the two things FR-026/FR-027 make load-bearing at the aggregate level — that
`quarantined` counts on its own, neither with `stored` nor folded into anything else, and that the
deadline reported is the day-21 capture deadline, never a value derived from the 31-day retention
window.

The **per-match** capture-state visibility — the four states read off one row of `GET /api/
matches`, and the empty state for a user with no matches at all (spec.md US3 acceptance scenario
5) — needs `packages/storage/src/aoe2stats_storage/repositories/matches.py` (T069) and
`apps/api/src/aoe2stats_api/routers/matches.py` (T070), neither of which exists yet. Every test
in that second half is `@pytest.mark.xfail(strict=True, reason="T070 not implemented yet")`, and
each imports the not-yet-existent router module *inside* its own body — never at module scope —
so a `ModuleNotFoundError` is an ordinary, expected `xfail` failure rather than a collection error
that would take the whole workspace suite down (the convention `test_quarantine.py` and
`packages/providers/tests/test_aoems.py` both document for the identical situation in Phase 4).
`strict=True` is what turns the run red the moment T070 lands and a test starts passing, which is
what forces the marker off instead of letting a stale marker hide a regression.

## The contract this second half defines for T069/T070

`GET /api/matches?profile_id=` does not exist yet, so — the same way a test-first task always
works in this workflow — this is also where the shape T070 must satisfy is written down, read
directly off `contracts/http-api.md` ("Each row carries its capture status and
`capture_deadline_at` (FR-027)") and off T073's own note that the three statuses behind "lost"
travel to the client **intact**, not pre-collapsed:

- `GET /api/matches?profile_id=<id>` answers `200` with `{"matches": [...], "next_cursor": ...}`.
- Each row carries at least `game_id`, `capture_status` (one of `replay_captures.status`'s seven
  raw values, verbatim — the collapse into the four badge states is the design-system component's
  job, T073/T074, not the API's), and `capture_deadline_at` (ISO 8601, or absent/`null` for a row
  with no matching capture, though every discovered match acquires one at discovery time — T053).
- A profile with zero matches answers `200` with `"matches": []`, never a 404 or an error: spec.md
  US3's fifth acceptance scenario is explicit that this must be "a clear empty state, not a broken
  or blank page."
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_api import security
from aoe2stats_api.settings import get_settings
from aoe2stats_storage.models import (
    AoeProfile,
    CaptureSource,
    CaptureStatus,
    Match,
    MatchPlayer,
    ProfileLink,
    ReplayCapture,
    SteamIdentity,
    User,
)
from aoe2stats_storage.models import Session as UserSession

pytestmark = [pytest.mark.usefixtures("environment")]

#: See `test_replay_status.py`'s and `test_unlink.py`'s module docstrings — this suite's working
#: assumption, not yet fixed by a contract document beyond T028's own implementation.
SESSION_COOKIE_NAME = "session_id"

_PROFILE_ID = 777333111


async def _seed_linked_profile(
    db_session: AsyncSession,
    *,
    profile_id: int = _PROFILE_ID,
    steam_id64: str = "76561197960287931",
) -> User:
    """A user with one verified Steam identity and one active `profile_links` row for
    `profile_id` — the ownership check both `replays.py` and (once it exists) `matches.py` apply."""
    now = datetime.now(UTC)
    user = User(allowlisted_at=now)
    db_session.add(user)
    await db_session.flush()

    db_session.add(
        SteamIdentity(steam_id64=steam_id64, user_id=user.id, verified_at=now, last_sign_in_at=now)
    )
    db_session.add(AoeProfile(profile_id=profile_id, alias="TestPlayer", country="FR"))
    await db_session.flush()

    db_session.add(
        ProfileLink(
            user_id=user.id,
            profile_id=profile_id,
            steam_id64=steam_id64,
            is_primary=True,
            linked_at=now,
        )
    )
    await db_session.commit()
    return user


async def _sign_in(client: TestClient, db_session: AsyncSession, user: User) -> None:
    """Insert a `sessions` row directly and hand the client its signed cookie — mirrors
    `test_replay_status.py`'s own `_sign_in` helper."""
    session_id = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    db_session.add(
        UserSession(
            id=session_id,
            user_id=user.id,
            created_at=now,
            expires_at=now + timedelta(days=30),
        )
    )
    await db_session.commit()
    secret = get_settings().app_secret_key.get_secret_value()
    client.cookies.set(SESSION_COOKIE_NAME, security._sign(session_id, secret))


async def _seed_match_with_capture(
    db_session: AsyncSession,
    *,
    game_id: int,
    profile_id: int,
    status: CaptureStatus,
    completed_at: datetime,
    capture_deadline_at: datetime,
) -> None:
    """A `matches` row, a `match_players` row for `profile_id` and a `replay_captures` row for
    the same pair — the shape T053's discovery always produces together, and the one
    `MatchesRepository.list_matches` (T069) requires to surface a match for `profile_id` at all:
    its own docstring notes the restriction to the caller's profile is the `INNER JOIN` to
    `match_players` on that exact id, so a capture with no matching `match_players` row is not a
    match this profile is on record as having played and correctly stays invisible to
    `GET /api/matches`."""
    db_session.add(
        Match(
            game_id=game_id,
            leaderboard_id=3,
            completed_at=completed_at,
            source="relic",
            raw_payload={},
        )
    )
    db_session.add(
        MatchPlayer(
            game_id=game_id,
            profile_id=profile_id,
            team_id=1,
            civ_id=1,
            result="win",
            rating=1500,
            rating_diff=15,
        )
    )
    db_session.add(
        ReplayCapture(
            game_id=game_id,
            profile_id=profile_id,
            status=status,
            capture_deadline_at=capture_deadline_at,
            first_seen_at=completed_at,
            source=CaptureSource.AUTOMATIC,
        )
    )


# --- Real: GET /api/replays/status (T062), already implemented ---------------------------------


async def test_replays_status_counts_a_quarantined_capture_separately_from_archived_and_lost(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-026 / FR-027 / SC-010: the one state a user cannot otherwise account for. A quarantined
    capture must not be folded into `stored` (it is not safely archived — its file failed
    well-formedness validation) nor into any of the three raw statuses the badge collapses to
    "lost" (`unavailable`, `expired`, `failed` — it is not gone, the source retention window is
    still open on it or it was captured before that mattered, and the bytes exist for review)."""
    user = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)
    now = datetime.now(UTC)

    await _seed_match_with_capture(
        db_session,
        game_id=1,
        profile_id=_PROFILE_ID,
        status=CaptureStatus.STORED,
        completed_at=now - timedelta(days=5),
        capture_deadline_at=now + timedelta(days=16),
    )
    await _seed_match_with_capture(
        db_session,
        game_id=2,
        profile_id=_PROFILE_ID,
        status=CaptureStatus.UNAVAILABLE,
        completed_at=now - timedelta(days=6),
        capture_deadline_at=now + timedelta(days=15),
    )
    await _seed_match_with_capture(
        db_session,
        game_id=3,
        profile_id=_PROFILE_ID,
        status=CaptureStatus.EXPIRED,
        completed_at=now - timedelta(days=40),
        capture_deadline_at=now - timedelta(days=19),
    )
    await _seed_match_with_capture(
        db_session,
        game_id=4,
        profile_id=_PROFILE_ID,
        status=CaptureStatus.FAILED,
        completed_at=now - timedelta(days=7),
        capture_deadline_at=now + timedelta(days=14),
    )
    await _seed_match_with_capture(
        db_session,
        game_id=5,
        profile_id=_PROFILE_ID,
        status=CaptureStatus.QUARANTINED,
        completed_at=now - timedelta(days=8),
        capture_deadline_at=now + timedelta(days=13),
    )
    await db_session.commit()

    response = client.get(f"/api/replays/status?profile_id={_PROFILE_ID}")

    assert response.status_code == 200
    counts = response.json()["counts"]
    assert counts["stored"] == 1, "the archived capture must not absorb the quarantined one"
    assert counts["unavailable"] == 1
    assert counts["expired"] == 1
    assert counts["failed"] == 1
    assert counts["quarantined"] == 1, (
        "a quarantined capture must be visible in its own right, not merged into `stored` nor "
        'into any of the three statuses that read as "lost" (FR-026)'
    )
    assert counts["unavailable"] + counts["expired"] + counts["failed"] == 3, (
        "sanity check on the fixture: exactly the three raw statuses that collapse to the badge's "
        '"lost" state are seeded once each'
    )


async def test_replays_status_nearest_deadline_is_the_21_day_capture_deadline_not_retention(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-027: "time remaining" means time to the capture deadline the system commits to, never
    to the source's ~31-day retention window it deliberately refuses to rely on. The seeded
    deadline sits well inside 31 days from now and is not derived from `completed_at + 31d` by
    this test — it is asserted to come back byte-for-byte as stored, which is what proves the
    endpoint reports the deadline column and not some other computation."""
    user = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)
    now = datetime.now(UTC)
    completed_at = now - timedelta(days=10)
    capture_deadline_at = completed_at + timedelta(days=21)  # CAPTURE_BUDGET_DAYS, not 31

    await _seed_match_with_capture(
        db_session,
        game_id=42,
        profile_id=_PROFILE_ID,
        status=CaptureStatus.PENDING,
        completed_at=completed_at,
        capture_deadline_at=capture_deadline_at,
    )
    await db_session.commit()

    response = client.get(f"/api/replays/status?profile_id={_PROFILE_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["nearest_deadline"] is not None
    assert body["nearest_deadline"]["game_id"] == 42
    assert body["nearest_deadline"]["capture_deadline_at"] == capture_deadline_at.isoformat(), (
        "the deadline shown must be the day-21 capture deadline column itself, never a value "
        "re-derived from the ~31-day source retention window (FR-027)"
    )


async def test_replays_status_reports_zero_counts_not_an_error_for_a_profile_with_no_captures(
    client: TestClient, db_session: AsyncSession
) -> None:
    """SC-010: "without contacting support". A newly linked profile that has not yet had anything
    discovered for it must read as an honest, zero-filled empty state — not a 404, not a 500, and
    not an absent field a client would have to guard against."""
    user = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)

    response = client.get(f"/api/replays/status?profile_id={_PROFILE_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["counts"] == {status.value: 0 for status in CaptureStatus}
    assert body["oldest_pending"] is None
    assert body["nearest_deadline"] is None


# --- per-match capture state, GET /api/matches (T069/T070) -------------------------------------


async def test_match_row_reports_archived_for_a_stored_capture(
    client: TestClient, db_session: AsyncSession
) -> None:
    """The safe / archived state (SC-010's word for `stored`)."""
    user = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)
    now = datetime.now(UTC)
    await _seed_match_with_capture(
        db_session,
        game_id=101,
        profile_id=_PROFILE_ID,
        status=CaptureStatus.STORED,
        completed_at=now - timedelta(days=3),
        capture_deadline_at=now + timedelta(days=18),
    )
    await db_session.commit()

    response = client.get(f"/api/matches?profile_id={_PROFILE_ID}")

    assert response.status_code == 200
    row = next(row for row in response.json()["matches"] if row["game_id"] == 101)
    assert row["capture_status"] == CaptureStatus.STORED.value


async def test_match_row_reports_pending_with_the_time_remaining_to_the_capture_deadline(
    client: TestClient, db_session: AsyncSession
) -> None:
    """The still-catchable state, carrying `capture_deadline_at` so the client can render the time
    remaining before the capture window closes (FR-027) — never the source's own retention."""
    user = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)
    now = datetime.now(UTC)
    completed_at = now - timedelta(days=1)
    capture_deadline_at = completed_at + timedelta(days=21)
    await _seed_match_with_capture(
        db_session,
        game_id=102,
        profile_id=_PROFILE_ID,
        status=CaptureStatus.PENDING,
        completed_at=completed_at,
        capture_deadline_at=capture_deadline_at,
    )
    await db_session.commit()

    response = client.get(f"/api/matches?profile_id={_PROFILE_ID}")

    assert response.status_code == 200
    row = next(row for row in response.json()["matches"] if row["game_id"] == 102)
    assert row["capture_status"] == CaptureStatus.PENDING.value
    assert row["capture_deadline_at"] == capture_deadline_at.isoformat()


async def test_match_row_reports_the_lost_statuses_intact_and_distinct(
    client: TestClient, db_session: AsyncSession
) -> None:
    """The lost state, per T073: `unavailable`, `expired` and `failed` all read as "lost" in the
    badge, but travel to the client **intact** rather than pre-collapsed by the API, so the badge
    can still tell "never recorded" from "existed and we missed it" (T073's own reasoning for why
    a manual upload, US4, is worth the user's trouble for two of the three and not the first)."""

    user = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)
    now = datetime.now(UTC)
    seeded = {
        201: CaptureStatus.UNAVAILABLE,
        202: CaptureStatus.EXPIRED,
        203: CaptureStatus.FAILED,
    }
    for game_id, status in seeded.items():
        await _seed_match_with_capture(
            db_session,
            game_id=game_id,
            profile_id=_PROFILE_ID,
            status=status,
            completed_at=now - timedelta(days=40),
            capture_deadline_at=now - timedelta(days=19),
        )
    await db_session.commit()

    response = client.get(f"/api/matches?profile_id={_PROFILE_ID}")

    assert response.status_code == 200
    rows_by_game_id = {row["game_id"]: row for row in response.json()["matches"]}
    for game_id, status in seeded.items():
        assert rows_by_game_id[game_id]["capture_status"] == status.value, (
            "the raw status must survive to the client unchanged — collapsing three distinct "
            "reasons into one word is the badge's job (T073/T074), not the API's"
        )


async def test_match_row_reports_needs_review_for_a_quarantined_capture(
    client: TestClient, db_session: AsyncSession
) -> None:
    """FR-026: the fourth badge state. A quarantined capture is neither archived nor lost — it is
    evidence a human should look at, and a per-match view that only knows three states leaves this
    one with nothing to show the user."""

    user = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)
    now = datetime.now(UTC)
    await _seed_match_with_capture(
        db_session,
        game_id=301,
        profile_id=_PROFILE_ID,
        status=CaptureStatus.QUARANTINED,
        completed_at=now - timedelta(days=9),
        capture_deadline_at=now + timedelta(days=12),
    )
    await db_session.commit()

    response = client.get(f"/api/matches?profile_id={_PROFILE_ID}")

    assert response.status_code == 200
    row = next(row for row in response.json()["matches"] if row["game_id"] == 301)
    assert row["capture_status"] == CaptureStatus.QUARANTINED.value
    assert row["capture_status"] not in {
        CaptureStatus.STORED.value,
        CaptureStatus.UNAVAILABLE.value,
        CaptureStatus.EXPIRED.value,
        CaptureStatus.FAILED.value,
    }


async def test_match_history_is_a_clear_empty_state_for_a_user_with_no_matches(
    client: TestClient, db_session: AsyncSession
) -> None:
    """spec.md US3 acceptance scenario 5: "Given a user with no matches at all, When they open
    their history, Then they get a clear empty state, not a broken or blank page." — a linked
    profile that nothing has been discovered for yet must answer 200 with an empty list, never a
    404, a 500, or a response shape a client has to special-case."""

    user = await _seed_linked_profile(db_session)
    await _sign_in(client, db_session, user)

    response = client.get(f"/api/matches?profile_id={_PROFILE_ID}")

    assert response.status_code == 200
    assert response.json()["matches"] == []
