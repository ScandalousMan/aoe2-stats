"""T402 — the capture-scope tests for constitution IX 4.0.0 (Phase 12).

Targets the second half of the split `DiscoverStage._consenting_profile_ids()` becomes in T404:
`_archiving_profile_ids()` — the same set `_linked_profile_ids()` selects (every profile with
`profile_links.unlinked_at IS NULL`) minus `users.archival_objected_at IS NOT NULL` — is what the
participant loop in `DiscoverStage.__call__` consults before enqueuing a `replay_captures` row.
`test_consent_gate.py` (T401) owns `_linked_profile_ids()` and the two effects upstream of capture
(match discovery, the rating refresh); this file owns only the enqueue decision itself.

**The inversion, stated for capture specifically.** Constitution IX, amended 2026-08-25: archival is
on by default for a linked profile, and "a linked user's Art. 21 objection... MUST stop all further
capture of their recordings" — capture, and nothing upstream of it. A linked user who has never
answered any question (`archival_objected_at IS NULL`) gets a capture enqueued for their own point
of view exactly as before; a linked user who *has* objected (`archival_objected_at IS NOT NULL`)
gets none, from the moment the objection is recorded. What must not happen is that objection is
implemented as a second flavour of exclusion indistinguishable from `unlinked_at` — the objecting
user is still a linked user in every other respect, and `test_objected_linked_user...` below asserts
that their match is still discovered and their rating still refreshed in the very same cycle that
declines to capture them, so "objected" and "unlinked" can never collapse into one code path.

**FR-016's point-of-view limit is unchanged by the amendment** (constitution IX 4.0.0: "the
point-of-view limit survives and is now this principle's real constraint"): only the linked user's
own recording is ever captured automatically, never another participant's, however that other
participant is related to this service — a pure third party who has never linked anything included.
`test_point_of_view_limit_...` below seeds exactly that shape: a linked, never-objected user sharing
a match with a profile this service has never linked at all, and asserts the capture enqueued for
that cycle is the linked user's own and only theirs.

T403 (`packages/storage/src/aoe2stats_storage/models.py`) replaced
`users.ingest_consent_at`/`ingest_consent_withdrawn_at` with the single nullable
`users.archival_objected_at`, and T404 split `discover.py`'s gate so the capture-enqueue membership
test reads it. Both have landed, so the tests below run unmarked. They were written first, against
T404's absence, each carrying `xfail(strict=True, reason="T404 not implemented yet")`; `strict=True`
is what forced the markers off the moment T404 made them pass for real.

The module under test (`aoe2stats_ingester.discover`) is imported inside each test body, per this
project's test-first convention (`CLAUDE.md`): a module-scope import failure is a collection error
that takes the whole `apps/ingester/tests` suite down, not merely this file's tests.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_providers.base import LeaderboardSnapshot, RawMatch
from aoe2stats_storage.models import (
    AoeProfile,
    CaptureSource,
    CaptureStatus,
    Match,
    MatchPlayer,
    ProfileLink,
    RatingSnapshot,
    ReplayCapture,
    SteamIdentity,
    User,
)

#: Offset applied to a profile id to build a unique, deterministic `matches.game_id` — arbitrary,
#: only required to never collide with another test's own profile ids in the same
#: (per-test-cleaned) database. Mirrors `test_consent_gate.py`'s own convention.
_GAME_ID_OFFSET = 910_000_000


class _SoloMatchHistoryProvider:
    """A `MatchHistoryProvider` (`contracts/providers.md`) fake returning one solo `RawMatch` —
    the queried profile as its only participant — for every profile id it is asked about. Enough
    to prove a capture was enqueued (or was not) for a specific profile without a second
    participant's presence complicating the read.
    """

    def __init__(self) -> None:
        self.requested_profile_ids: list[int] = []

    async def recent_matches(self, profile_ids: list[int]) -> list[RawMatch]:
        self.requested_profile_ids.extend(profile_ids)
        now = datetime.now(UTC)
        return [
            RawMatch(
                game_id=_GAME_ID_OFFSET + profile_id,
                leaderboard_id=3,
                completed_at=now,
                player_profile_ids=(profile_id,),
                raw_payload={"profile_id": profile_id},
            )
            for profile_id in profile_ids
        ]


class _SharedMatchHistoryProvider:
    """A `MatchHistoryProvider` fake returning one shared `RawMatch` whose participants include a
    profile the caller never asked about — mirroring the real endpoint (and
    `test_shared_match.py`'s own fake): querying for one participant returns the whole match,
    every player in it, not only the one queried. This is what makes FR-016's point-of-view limit
    the discovery stage's own responsibility rather than something the provider enforces for it.
    """

    def __init__(self, raw_match: RawMatch) -> None:
        self._raw_match = raw_match
        self.requested_profile_ids: list[int] = []

    async def recent_matches(self, profile_ids: list[int]) -> list[RawMatch]:
        self.requested_profile_ids.extend(profile_ids)
        if any(profile_id in self._raw_match.player_profile_ids for profile_id in profile_ids):
            return [self._raw_match]
        return []


class _RecordingProfileProvider:
    """A `ProfileProvider` fake exercising only `personal_stats`, the one method
    `DiscoverStage._refresh_ratings` calls: returns one `LeaderboardSnapshot` per requested id so a
    caller can assert a `rating_snapshots` row was actually appended.
    """

    async def resolve_profile(self, steam_id64: str):
        raise AssertionError("DiscoverStage never calls ProfileProvider.resolve_profile")

    async def personal_stats(self, profile_ids: list[int]) -> list[LeaderboardSnapshot]:
        return [
            LeaderboardSnapshot(profile_id=profile_id, leaderboard_id=3, rating=1000)
            for profile_id in profile_ids
        ]


async def _seed_linked_user(
    db_session: AsyncSession,
    *,
    profile_id: int,
    archival_objected: bool = False,
) -> uuid.UUID:
    """Insert a fully linked user — `users`, `steam_identities`, `aoe_profiles`, `profile_links` —
    and commit, exactly the shape discovery's own query walks. The only difference between the
    users this test seeds is `archival_objected_at`; everything else (allowlisted, a primary
    linked profile) is identical, so a wrongful capture or a wrongful exclusion cannot be
    explained by anything else. Mirrors `test_consent_gate.py`'s own seeding helper.
    """
    now = datetime.now(UTC)
    user_id = uuid.uuid4()
    steam_id64 = f"76561198{profile_id:010d}"

    db_session.add(
        User(
            id=user_id,
            created_at=now,
            allowlisted_at=now,
            archival_objected_at=now if archival_objected else None,
        )
    )
    db_session.add(
        SteamIdentity(
            steam_id64=steam_id64,
            user_id=user_id,
            verified_at=now,
            last_sign_in_at=now,
        )
    )
    # Flushed before `ProfileLink` is added: `ProfileLink.steam_id64` has a column-level
    # `ForeignKey` to `steam_identities` but no ORM `relationship()` connects the two classes, so
    # the unit of work's automatic dependency sort has no edge telling it `steam_identities` must
    # land first (the same gap `test_consent_gate.py` and `test_shared_match.py` both document).
    await db_session.flush()
    db_session.add(
        AoeProfile(
            profile_id=profile_id,
            alias=f"player-{profile_id}",
            first_seen_at=now,
            last_seen_at=now,
        )
    )
    db_session.add(
        ProfileLink(
            id=uuid.uuid4(),
            user_id=user_id,
            profile_id=profile_id,
            steam_id64=steam_id64,
            is_primary=True,
            linked_at=now,
        )
    )
    # Committed here, mid-test: the discovery stage below opens its own session through
    # `session_factory`, a separate connection from `db_session` — an uncommitted insert on this
    # one is invisible to that one until this runs.
    await db_session.commit()
    return user_id


async def test_never_answered_linked_user_capture_is_enqueued(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Case 1: a linked user who has never answered any question (`archival_objected_at IS NULL`)
    is the inverted default's core case for capture specifically — archival is on, and a
    `replay_captures` row is enqueued for their own point of view exactly as it always was for a
    consenting user pre-amendment.
    """
    from aoe2stats_ingester.budget import Budget
    from aoe2stats_ingester.discover import DiscoverStage

    profile_id = 210_000_001
    await _seed_linked_user(db_session, profile_id=profile_id, archival_objected=False)

    match_provider = _SoloMatchHistoryProvider()
    stage = DiscoverStage(
        session_factory=session_factory,
        match_history_provider=match_provider,
        profile_provider=_RecordingProfileProvider(),
        capture_budget_days=21,
    )

    await stage(Budget(seconds=60))

    async with session_factory() as session:
        capture = await session.scalar(
            select(ReplayCapture).where(ReplayCapture.profile_id == profile_id)
        )
        assert capture is not None, (
            "A linked user who has never answered any question must have their own point of "
            "view captured — archival is on by default under constitution IX 4.0.0, and "
            "declining to capture until the user decides reinstates the retired opt-in gate."
        )
        assert capture.game_id == _GAME_ID_OFFSET + profile_id
        assert capture.status == CaptureStatus.PENDING
        assert capture.source == CaptureSource.AUTOMATIC


async def test_objected_linked_user_no_capture_but_matches_and_ratings_still_written(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Cases 2 and 3, in the same cycle on purpose: a linked user who HAS exercised the Art. 21
    right to object (`archival_objected_at IS NOT NULL`) gets **no** `replay_captures` row for
    their own point of view — the objection reaching capture — but their match is still
    discovered (FR-013) and their rating is still refreshed (FR-009) in that very same cycle.

    Asserting both halves against the same run is the point: an implementation that special-cases
    an objecting profile at the top of `__call__` — treating it like an unlinked one and skipping
    discovery and the rating refresh entirely — would still pass a version of this test that only
    checked the capture table. `matches`, `match_players` and `rating_snapshots` are asserted
    directly, not merely the absence of a capture, so "objected" and "unlinked" cannot collapse
    into one code path without this failing.
    """
    from aoe2stats_ingester.budget import Budget
    from aoe2stats_ingester.discover import DiscoverStage

    objected_profile_id = 210_000_002
    await _seed_linked_user(db_session, profile_id=objected_profile_id, archival_objected=True)

    match_provider = _SoloMatchHistoryProvider()
    profile_provider = _RecordingProfileProvider()
    stage = DiscoverStage(
        session_factory=session_factory,
        match_history_provider=match_provider,
        profile_provider=profile_provider,
        capture_budget_days=21,
    )

    await stage(Budget(seconds=60))

    # The objecting profile was still handed to both providers — discovery and the rating refresh
    # are unconditional on objection.
    assert match_provider.requested_profile_ids == [objected_profile_id]

    async with session_factory() as session:
        capture = await session.scalar(
            select(ReplayCapture).where(ReplayCapture.profile_id == objected_profile_id)
        )
        assert capture is None, (
            "An objecting user's own point of view must not be captured — Art. 21 stops further "
            "capture of their recordings from the moment the objection is recorded."
        )

        match_row = await session.scalar(
            select(Match).where(Match.game_id == _GAME_ID_OFFSET + objected_profile_id)
        )
        assert match_row is not None, (
            "The half that is easy to lose: the objecting user's match must still be discovered "
            "and written in the same cycle that declines to capture them. Objection reaches "
            "capture and nothing else."
        )

        match_player_row = await session.scalar(
            select(MatchPlayer).where(
                MatchPlayer.game_id == _GAME_ID_OFFSET + objected_profile_id,
                MatchPlayer.profile_id == objected_profile_id,
            )
        )
        assert match_player_row is not None

        snapshot_row = await session.scalar(
            select(RatingSnapshot).where(RatingSnapshot.profile_id == objected_profile_id)
        )
        assert snapshot_row is not None, (
            "The objecting user's rating must still be refreshed in the same cycle — objection "
            "is not a re-implementation of the retired ingestion gate."
        )


async def test_point_of_view_limit_holds_for_other_match_participants(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Case 4: FR-016's point-of-view limit, unchanged by the amendment. A linked, never-objected
    user sharing a match with a profile this service has never linked at all — a pure third party,
    no `users` row and no `profile_links` row — must have only their own point of view captured.
    Constitution IX 4.0.0 restates this directly: "only the linked user's own point of view is
    ever captured automatically, never another participant's... nothing is captured
    speculatively."

    The match-history provider mirrors the real endpoint (and `test_shared_match.py`'s own fake):
    a query for the linked profile returns the whole match, every participant listed, which is
    exactly the shape that makes fan-out — or the lack of it — the discovery stage's own
    responsibility rather than something the provider does for it.
    """
    from aoe2stats_ingester.budget import Budget
    from aoe2stats_ingester.discover import DiscoverStage

    linked_profile_id = 210_000_003
    third_party_profile_id = 210_000_004
    game_id = _GAME_ID_OFFSET + linked_profile_id
    await _seed_linked_user(db_session, profile_id=linked_profile_id, archival_objected=False)

    raw_match = RawMatch(
        game_id=game_id,
        leaderboard_id=3,
        completed_at=datetime.now(UTC),
        player_profile_ids=(linked_profile_id, third_party_profile_id),
        raw_payload={"matchId": game_id},
    )
    match_provider = _SharedMatchHistoryProvider(raw_match)
    stage = DiscoverStage(
        session_factory=session_factory,
        match_history_provider=match_provider,
        profile_provider=_RecordingProfileProvider(),
        capture_budget_days=21,
    )

    await stage(Budget(seconds=60))

    async with session_factory() as session:
        # Both participants are recorded as having played the match...
        match_players = (
            (await session.execute(select(MatchPlayer).where(MatchPlayer.game_id == game_id)))
            .scalars()
            .all()
        )
        assert {row.profile_id for row in match_players} == {
            linked_profile_id,
            third_party_profile_id,
        }

        # ...the third party even gets an `aoe_profiles` row, exactly as any participant this
        # stage meets for the first time does (`touch_aoe_profile`)...
        third_party_row = await session.scalar(
            select(AoeProfile).where(AoeProfile.profile_id == third_party_profile_id)
        )
        assert third_party_row is not None

        # ...but only the linked user's own point of view is captured. No capture exists for the
        # third party, and exactly one capture exists in total for this cycle.
        third_party_capture = await session.scalar(
            select(ReplayCapture).where(ReplayCapture.profile_id == third_party_profile_id)
        )
        assert third_party_capture is None, (
            "No capture is enqueued for any participant who is not the linked user themselves "
            "(FR-016) — even a linked, never-objected user's own match must not fan capture out "
            "to a third party sharing it."
        )

        linked_capture = await session.scalar(
            select(ReplayCapture).where(ReplayCapture.profile_id == linked_profile_id)
        )
        assert linked_capture is not None

        every_capture = (await session.execute(select(ReplayCapture))).scalars().all()
        assert len(every_capture) == 1
