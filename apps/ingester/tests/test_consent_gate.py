"""T401 — the discovery-scope tests for constitution IX 4.0.0 (Phase 12).

Targets the split `DiscoverStage._consenting_profile_ids()` is supposed to become in T404:
`_linked_profile_ids()` — every profile with `profile_links.unlinked_at IS NULL`, no other
condition — drives both the rating refresh (FR-009) and match discovery (FR-013), and
`_archiving_profile_ids()` (that same set minus `users.archival_objected_at IS NOT NULL`) governs
capture-enqueue membership alone. T402's `test_capture_objection.py` owns that second query; this
file owns only the first two effects.

**The default this file asserts is the inverted one.** Constitution IX, amended 2026-08-25: archival
rests on legitimate interest (Art. 6-1-f), not consent, and "a linked profile whose user has not
answered any question is ingested in full". A linked user's Art. 21 objection stops *capture*
(T402) and nothing upstream of it — discovery and the rating refresh MUST still run for them, or an
implementation has reinstated the retired opt-in gate under `archival_objected_at`'s name instead of
the opt-out the amendment actually specifies. That inversion — objection reaches capture and nothing
else — is the core case below (`test_objected_user_still_has_matches_discovered_...`).

**This file, until today, asserted the opposite** — the old two-clause `ingest_consent_at IS NOT
NULL AND ingest_consent_withdrawn_at IS NULL` predicate — and passed, ratifying the rule the
amendment retired: the same shape T384 and T397 found and fixed one layer up (the no-index
middleware's route allowlist, the search endpoint's field list). It is rewritten here rather than
amended, because every one of its old cases encoded the retired default.

**The one exclusion that survives 4.0.0** is not consent-shaped at all: a profile whose
`profile_links` row has `unlinked_at IS NOT NULL` is excluded from discovery entirely, regardless
of `archival_objected_at`, because an unlinked profile is not "a linked user's own point of view"
any more — there is no user to attribute the recording to. `test_unlinked_profile_...` below is the
contrast case: without it, "linked users are always discovered" and "unlinked users never are" could
collapse into the same accidental code path instead of two deliberately different ones.

T403 (`packages/storage/src/aoe2stats_storage/models.py`) replaced
`users.ingest_consent_at`/`ingest_consent_withdrawn_at` with the single nullable
`users.archival_objected_at`, and T404 split `discover.py`'s gate so that query reads it. Both have
landed, so the tests below run unmarked. They were written first, against T404's absence, each
carrying `xfail(strict=True, reason="T404 not implemented yet")`; `strict=True` is what forced the
markers off the moment T404 made them pass for real, rather than letting a stale marker sit here
hiding a later regression.

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
    Match,
    MatchPlayer,
    ProfileLink,
    RatingSnapshot,
    SteamIdentity,
    User,
)

#: Offset applied to a profile id to build a unique, deterministic `matches.game_id` for that
#: profile's fake match below — arbitrary, only required to never collide with another test's own
#: profile ids in the same (per-test-cleaned) database.
_GAME_ID_OFFSET = 900_000_000


class _RecordingMatchHistoryProvider:
    """A `MatchHistoryProvider` (`contracts/providers.md`) fake that records every profile id it
    is asked about and, unless that id is in `forbidden_profile_ids`, returns one solo `RawMatch`
    for it — enough for a caller to assert both "this profile was requested" and "a match for it
    was actually discovered and upserted", not merely that the provider was invoked.

    Raising immediately on a forbidden id (rather than only asserting on `requested_profile_ids`
    afterwards) is what proves an exclusion is a property of the query that selects work, not a
    branch that discards a result after the provider has already been reached — the same
    distinction this file's now-rewritten, pre-4.0.0 version made with its own
    `_RaisingMatchHistoryProvider`.
    """

    def __init__(self, *, forbidden_profile_ids: frozenset[int] = frozenset()) -> None:
        self._forbidden = forbidden_profile_ids
        self.requested_profile_ids: list[int] = []

    async def recent_matches(self, profile_ids: list[int]) -> list[RawMatch]:
        for profile_id in profile_ids:
            assert profile_id not in self._forbidden, (
                f"MatchHistoryProvider.recent_matches was called with profile_id={profile_id}, "
                "which belongs to an unlinked profile. Discovery's exclusion of an unlinked "
                "profile must be part of the query that selects work, not a branch downstream of "
                "a provider call that has already happened."
            )
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


class _RecordingProfileProvider:
    """A `ProfileProvider` (`contracts/providers.md`) fake exercising only `personal_stats`, the
    one method `DiscoverStage._refresh_ratings` calls — mirrors `_RecordingMatchHistoryProvider`
    above: records every profile id it is asked about, raises immediately on a forbidden one, and
    returns one `LeaderboardSnapshot` per allowed id so a caller can assert a `rating_snapshots`
    row was actually appended, not merely that the provider was invoked.
    """

    def __init__(self, *, forbidden_profile_ids: frozenset[int] = frozenset()) -> None:
        self._forbidden = forbidden_profile_ids
        self.requested_profile_ids: list[int] = []

    async def resolve_profile(self, steam_id64: str):
        raise AssertionError("DiscoverStage never calls ProfileProvider.resolve_profile")

    async def personal_stats(self, profile_ids: list[int]) -> list[LeaderboardSnapshot]:
        for profile_id in profile_ids:
            assert profile_id not in self._forbidden, (
                f"ProfileProvider.personal_stats was called with profile_id={profile_id}, "
                "which belongs to an unlinked profile. The rating refresh must select its work "
                "from the same query as discovery, never as a downstream branch."
            )
        self.requested_profile_ids.extend(profile_ids)
        return [
            LeaderboardSnapshot(profile_id=profile_id, leaderboard_id=3, rating=1000)
            for profile_id in profile_ids
        ]


async def _seed_linked_user(
    db_session: AsyncSession,
    *,
    profile_id: int,
    archival_objected: bool = False,
    unlinked: bool = False,
) -> uuid.UUID:
    """Insert a fully linked user — `users`, `steam_identities`, `aoe_profiles`, `profile_links` —
    and commit, exactly the shape discovery's own query walks.

    The only differences between the users this test seeds are `archival_objected_at` and
    `profile_links.unlinked_at`; everything else (allowlisted, a primary linked profile) is
    identical, so a leak or a wrongful exclusion cannot be explained by anything but those two
    columns — the whole point of the inverted default and the one exclusion that survives it.
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
    # Flushed here, before `ProfileLink` is added below: `ProfileLink.steam_id64` has a
    # column-level `ForeignKey` to `steam_identities` (models.py) but no ORM `relationship()`
    # connects the two classes, so the unit of work's automatic dependency sort — which orders
    # inserts by *mapper* relationships, not by raw table foreign keys — has no edge telling it
    # `steam_identities` must land first (the same gap this file's own pre-4.0.0 seeding helper,
    # and `test_shared_match.py`'s, both documented and worked around identically).
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
            unlinked_at=now if unlinked else None,
        )
    )
    # Committed here, mid-test, rather than left for the fixture's own teardown: the discovery
    # stage below opens its *own* session through `session_factory`, a separate connection from
    # `db_session` — an uncommitted insert on this one is invisible to that one until this runs.
    await db_session.commit()
    return user_id


async def test_never_answered_user_has_matches_discovered_and_ratings_refreshed(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The default case constitution IX 4.0.0 states directly: "a linked profile whose user has
    not answered any question is ingested in full". A user seeded with `archival_objected_at`
    `NULL` — never having exercised the Art. 21 right to object, and never having "consented"
    either, since there is no longer a grant to record — must still have their match discovered
    (FR-013) and their rating refreshed (FR-009) on an ordinary cycle.
    """
    from aoe2stats_ingester.budget import Budget
    from aoe2stats_ingester.discover import DiscoverStage

    profile_id = 200_000_001
    await _seed_linked_user(db_session, profile_id=profile_id, archival_objected=False)

    match_provider = _RecordingMatchHistoryProvider()
    profile_provider = _RecordingProfileProvider()
    stage = DiscoverStage(
        session_factory=session_factory,
        match_history_provider=match_provider,
        profile_provider=profile_provider,
        capture_budget_days=21,
    )

    await stage(Budget(seconds=60))

    assert match_provider.requested_profile_ids == [profile_id]
    assert profile_provider.requested_profile_ids == [profile_id]

    async with session_factory() as session:
        match_row = await session.scalar(
            select(Match).where(Match.game_id == _GAME_ID_OFFSET + profile_id)
        )
        assert match_row is not None

        match_player_row = await session.scalar(
            select(MatchPlayer).where(
                MatchPlayer.game_id == _GAME_ID_OFFSET + profile_id,
                MatchPlayer.profile_id == profile_id,
            )
        )
        assert match_player_row is not None

        snapshot_row = await session.scalar(
            select(RatingSnapshot).where(RatingSnapshot.profile_id == profile_id)
        )
        assert snapshot_row is not None


async def test_objected_user_still_has_matches_discovered_and_ratings_refreshed(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The core inversion (constitution IX 4.0.0): "an opt-out that reverses the previous default;
    it is not the retired gate under a new name". A user who HAS exercised the Art. 21 right to
    object (`archival_objected_at IS NOT NULL`) stops further *capture* of their recordings
    (T402's `test_capture_objection.py`) and nothing upstream of that — their matches are still
    discovered (FR-013, FR-042) and their ratings are still refreshed (FR-009) on every cycle,
    exactly as an unobjected user's are. An implementation that also drops discovery or the rating
    refresh for an objecting user has reinstated the retired opt-in consent gate under
    `archival_objected_at`'s name — the fault this phase exists to close.
    """
    from aoe2stats_ingester.budget import Budget
    from aoe2stats_ingester.discover import DiscoverStage

    objected_profile_id = 200_000_002
    await _seed_linked_user(db_session, profile_id=objected_profile_id, archival_objected=True)

    match_provider = _RecordingMatchHistoryProvider()
    profile_provider = _RecordingProfileProvider()
    stage = DiscoverStage(
        session_factory=session_factory,
        match_history_provider=match_provider,
        profile_provider=profile_provider,
        capture_budget_days=21,
    )

    await stage(Budget(seconds=60))

    # Discovery and the rating refresh are unconditional on objection: both the match-history and
    # the profile provider must still have been reached for this profile.
    assert match_provider.requested_profile_ids == [objected_profile_id]
    assert profile_provider.requested_profile_ids == [objected_profile_id]

    async with session_factory() as session:
        match_row = await session.scalar(
            select(Match).where(Match.game_id == _GAME_ID_OFFSET + objected_profile_id)
        )
        assert match_row is not None

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
        assert snapshot_row is not None


async def test_unlinked_profile_is_excluded_from_discovery_regardless_of_objection(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The contrast case: the one exclusion that survives constitution IX 4.0.0 is not
    consent-shaped at all. `profile_links.unlinked_at IS NOT NULL` removes a profile from
    discovery entirely — no match discovered, no rating refreshed — because an unlinked profile is
    no longer "a linked user's own point of view" for anyone to attribute a recording to, not
    because of anything about `archival_objected_at`.

    Two unlinked profiles are seeded — one that never objected, one that did — so the exclusion
    cannot be explained by objection at all: if it were `archival_objected_at`-shaped rather than
    `unlinked_at`-shaped, the never-objected-but-unlinked profile would wrongly still be
    discovered. A third, ordinarily linked profile is seeded alongside both so a discovery stage
    that simply does nothing for anybody cannot pass this test for the wrong reason: the assertions
    below require the linked profile to actually have been discovered.
    """
    from aoe2stats_ingester.budget import Budget
    from aoe2stats_ingester.discover import DiscoverStage

    linked_profile_id = 200_000_003
    unlinked_never_objected_profile_id = 200_000_004
    unlinked_objected_profile_id = 200_000_005
    await _seed_linked_user(db_session, profile_id=linked_profile_id)
    await _seed_linked_user(
        db_session, profile_id=unlinked_never_objected_profile_id, unlinked=True
    )
    await _seed_linked_user(
        db_session,
        profile_id=unlinked_objected_profile_id,
        archival_objected=True,
        unlinked=True,
    )

    forbidden = frozenset({unlinked_never_objected_profile_id, unlinked_objected_profile_id})
    match_provider = _RecordingMatchHistoryProvider(forbidden_profile_ids=forbidden)
    profile_provider = _RecordingProfileProvider(forbidden_profile_ids=forbidden)
    stage = DiscoverStage(
        session_factory=session_factory,
        match_history_provider=match_provider,
        profile_provider=profile_provider,
        capture_budget_days=21,
    )

    await stage(Budget(seconds=60))

    # Only the still-linked profile was ever handed to either provider — proving the exclusion is
    # the `unlinked_at` condition on the query that selects work, and not a discovery stage that
    # quietly does nothing for anybody, which would pass the assertions inside the fakes for the
    # wrong reason.
    assert match_provider.requested_profile_ids == [linked_profile_id]
    assert profile_provider.requested_profile_ids == [linked_profile_id]

    async with session_factory() as session:
        for excluded_profile_id in (
            unlinked_never_objected_profile_id,
            unlinked_objected_profile_id,
        ):
            match_row = await session.scalar(
                select(Match).where(Match.game_id == _GAME_ID_OFFSET + excluded_profile_id)
            )
            assert match_row is None

            snapshot_row = await session.scalar(
                select(RatingSnapshot).where(RatingSnapshot.profile_id == excluded_profile_id)
            )
            assert snapshot_row is None

        linked_match_row = await session.scalar(
            select(Match).where(Match.game_id == _GAME_ID_OFFSET + linked_profile_id)
        )
        assert linked_match_row is not None

        linked_snapshot_row = await session.scalar(
            select(RatingSnapshot).where(RatingSnapshot.profile_id == linked_profile_id)
        )
        assert linked_snapshot_row is not None
