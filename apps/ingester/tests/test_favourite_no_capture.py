"""T345 — favouriting a player must cause no capture, no ingestion and no archival (FR-012, US5
scenario 4).

**Not `xfail`.** T346 (the favourites router, `apps/api/src/aoe2stats_api/routers/favourites.py`)
does not exist yet, but this test does not need it: the `favourites` table itself landed with T304/
T305, and the property under test — that `DiscoverStage`, `ReconcileStage` and `CaptureDrain` never
so much as look at it — is provable today by inserting a `Favourite` row directly through the ORM
and driving a real `run_once` over it. Every other test in this feature's Phase 6 that carries
`xfail(strict=True, reason="T346 not implemented yet")` (`T344`) does so because it exercises the
`GET`/`PUT`/`DELETE` routes T346 has not written; this one exercises none of them.

**Capture remains what 001 defines it as: the linked user's own point of view, and nothing else**
(constitution IX 4.0.0; FR-012's own text, amended 2026-08-25 from "consenting" to "linked" without
touching the point-of-view limit itself). A favourite is a bookmark in one private table with no
foreign key anything in `apps/ingester` ever joins against — `discover.py`'s own module docstring
names `_linked_profile_ids()` as "the *only* place this module decides whose profiles exist for a
cycle's discovery and rating refresh", and that query walks `profile_links`, never `favourites`.
This test is the executable version of that sentence: it does not merely assert the row counts end
up right, it makes the fake providers *raise* if `apps/ingester` ever asks about the favourited
profile at all, so a future change that reaches `favourites` from an ingestion query fails here for
the reason T345 exists, not by an accidental count mismatch elsewhere.

Three real stages are driven through one real `run_once` call — `DiscoverStage`, `ReconcileStage`
and `CaptureDrain`, the exact tuple `apps/api/src/aoe2stats_api/ingest_stages.py`'s
`build_ingest_stages` assembles for production — because "asserted across a full `run_once`" is the
task's own wording and a single stage would leave the other two unexercised. A second, genuinely
linked profile is seeded alongside the favourited one so a `run_once` that quietly does nothing for
anybody cannot pass this test for the wrong reason (the same discipline `test_consent_gate.py`'s
`test_unlinked_profile_is_excluded_from_discovery_regardless_of_objection` uses for the identical
purpose): the assertions below require the linked profile to have been discovered for real, and the
favourited-only profile to have been touched nowhere.

The module under test (`aoe2stats_ingester.discover`, `.reconcile`, `.capture`, `.run`) is imported
inside the test body, per this project's test-first convention (`CLAUDE.md`): a module-scope import
failure is a collection error that takes the whole `apps/ingester/tests` suite down, not merely this
file's test.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_providers.base import LeaderboardSnapshot, NotFound, RawMatch, ReplayBlob
from aoe2stats_storage.models import (
    AoeProfile,
    Favourite,
    Match,
    ProfileLink,
    ReplayCapture,
    SteamIdentity,
    User,
)

#: Offset applied to a profile id to build a unique, deterministic `matches.game_id` for that
#: profile's fake match — arbitrary, only required to never collide with another test file's own
#: profile ids in the same (per-test-cleaned) database. Distinct from `test_consent_gate.py`'s own
#: `_GAME_ID_OFFSET` (900_000_000) purely so a reader diffing both files never has to check whether
#: the two happen to share a range.
_GAME_ID_OFFSET = 950_000_000


class _RecordingMatchHistoryProvider:
    """A `MatchHistoryProvider` (`contracts/providers.md`) fake that records every profile id it is
    asked about and raises immediately if asked about a `forbidden_profile_ids` member — the
    favourited-but-never-linked profile this test exists for. Raising at the moment of the call,
    rather than only asserting on `requested_profile_ids` afterwards, is what proves the exclusion
    is a property of the query that selects work and not a branch that discards a result after the
    provider has already been reached — same discipline as `test_consent_gate.py`'s identically
    named fake.
    """

    def __init__(self, *, forbidden_profile_ids: frozenset[int] = frozenset()) -> None:
        self._forbidden = forbidden_profile_ids
        self.requested_profile_ids: list[int] = []

    async def recent_matches(self, profile_ids: list[int]) -> list[RawMatch]:
        for profile_id in profile_ids:
            assert profile_id not in self._forbidden, (
                f"MatchHistoryProvider.recent_matches was called with profile_id={profile_id}, "
                "which is favourited but never linked. Favouriting a player (FR-012) must not "
                "cause it to be discovered, ingested or captured."
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
    one method `DiscoverStage._refresh_ratings` calls — same shape and same reason as
    `_RecordingMatchHistoryProvider` above.
    """

    def __init__(self, *, forbidden_profile_ids: frozenset[int] = frozenset()) -> None:
        self._forbidden = forbidden_profile_ids
        self.requested_profile_ids: list[int] = []

    async def resolve_profile(self, steam_id64: str):
        raise AssertionError("DiscoverStage never calls ProfileProvider.resolve_profile")

    async def personal_stats(self, profile_ids: list[int]) -> list[LeaderboardSnapshot]:
        for profile_id in profile_ids:
            assert profile_id not in self._forbidden, (
                f"ProfileProvider.personal_stats was called with profile_id={profile_id}, which "
                "is favourited but never linked. Favouriting a player must not cause its rating "
                "to be refreshed."
            )
        self.requested_profile_ids.extend(profile_ids)
        return [
            LeaderboardSnapshot(profile_id=profile_id, leaderboard_id=3, rating=1000)
            for profile_id in profile_ids
        ]


class _ForbiddingReplayProvider:
    """A `ReplayProvider` (`contracts/providers.md`) fake that raises the instant it is asked for
    the favourited profile's point of view — no `replay_captures` row can legitimately exist for
    it, so the drain claiming one and calling this at all is already the failure. The linked
    profile's own capture is real and expected (discovery enqueues it exactly as it should for a
    linked user's own point of view, 001 FR-013/FR-014); answering it with `NotFound` keeps that
    unrelated, legitimate path cheap to drain without needing an object store or a validator, which
    this test has no reason to exercise.
    """

    def __init__(self, *, forbidden_profile_ids: frozenset[int]) -> None:
        self._forbidden = forbidden_profile_ids

    async def fetch_replay(self, game_id: int, profile_id: int) -> ReplayBlob | NotFound:
        assert profile_id not in self._forbidden, (
            f"ReplayProvider.fetch_replay was called for profile_id={profile_id}, which is "
            "favourited but never linked. No capture may ever be enqueued for it, so the drain "
            "must never have anything of theirs to claim in the first place."
        )
        return NotFound()


async def _seed_linked_user(db_session: AsyncSession, *, profile_id: int) -> None:
    """Insert an ordinarily linked user — `users`, `steam_identities`, `aoe_profiles`,
    `profile_links` — exactly the shape `DiscoverStage._linked_profile_ids()` walks. This is the
    control case: a profile this run *should* discover, seeded so a `run_once` that does nothing
    for anybody cannot pass this test by accident.
    """
    now = datetime.now(UTC)
    user_id = uuid.uuid4()
    steam_id64 = f"76561198{profile_id:010d}"

    db_session.add(User(id=user_id, created_at=now, allowlisted_at=now))
    db_session.add(
        SteamIdentity(
            steam_id64=steam_id64,
            user_id=user_id,
            verified_at=now,
            last_sign_in_at=now,
        )
    )
    # Flushed before `ProfileLink` is added: see `test_consent_gate.py`'s identical comment on why
    # the unit of work's automatic dependency sort needs this — `ProfileLink.steam_id64` has a
    # column-level `ForeignKey` to `steam_identities` but no ORM `relationship()` links the two.
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
    await db_session.commit()


async def _seed_favourite_of_a_third_party(
    db_session: AsyncSession, *, favourited_profile_id: int
) -> datetime:
    """Insert a signed-in user who has favourited `favourited_profile_id` — a player who is never
    linked to any account (`profile_links` carries no row for them at all). Returns the
    `aoe_profiles.last_seen_at` this seeding wrote, so the test can assert it is untouched by the
    run — the honest way to show that `favouriting a player` never causes that player to be "seen"
    by ingestion.
    """
    now = datetime.now(UTC)
    favouriting_user_id = uuid.uuid4()

    db_session.add(User(id=favouriting_user_id, created_at=now, allowlisted_at=now))
    # The favourited player: `aoe_profiles` row required by `favourites.profile_id`'s own foreign
    # key, exactly as it would exist because the favouriting user found them through search
    # (FR-004d's fallback) or a match history — never because ingestion put them there.
    db_session.add(
        AoeProfile(
            profile_id=favourited_profile_id,
            alias=f"third-party-{favourited_profile_id}",
            first_seen_at=now,
            last_seen_at=now,
        )
    )
    await db_session.flush()
    db_session.add(
        Favourite(
            user_id=favouriting_user_id,
            profile_id=favourited_profile_id,
            created_at=now,
        )
    )
    await db_session.commit()
    return now


async def test_favouriting_a_player_enqueues_no_capture_across_a_full_run_once(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from aoe2stats_ingester.capture import CaptureDrain
    from aoe2stats_ingester.discover import DiscoverStage
    from aoe2stats_ingester.reconcile import ReconcileStage
    from aoe2stats_ingester.run import run_once

    linked_profile_id = 200_000_010
    favourited_profile_id = 200_000_011

    await _seed_linked_user(db_session, profile_id=linked_profile_id)
    seeded_last_seen_at = await _seed_favourite_of_a_third_party(
        db_session, favourited_profile_id=favourited_profile_id
    )

    forbidden = frozenset({favourited_profile_id})
    match_provider = _RecordingMatchHistoryProvider(forbidden_profile_ids=forbidden)
    profile_provider = _RecordingProfileProvider(forbidden_profile_ids=forbidden)

    discover = DiscoverStage(
        session_factory=session_factory,
        match_history_provider=match_provider,
        profile_provider=profile_provider,
        capture_budget_days=21,
    )
    reconcile = ReconcileStage(
        session_factory=session_factory,
        match_history_provider=match_provider,
        capture_budget_days=21,
    )
    drain = CaptureDrain(
        session_factory=session_factory,
        replay_provider=_ForbiddingReplayProvider(forbidden_profile_ids=forbidden),
        max_captures_per_user_per_run=20,
        quota_exempt_days=7,
    )

    report = await run_once(
        60,
        trigger="test",
        stages=[discover, reconcile, drain],
        session_factory=session_factory,
    )

    assert report.stages_completed == ("discover", "reconcile", "drain")

    # The control case actually happened: proves this run_once did real work rather than passing
    # trivially because nobody was ever discovered at all.
    assert linked_profile_id in match_provider.requested_profile_ids
    assert linked_profile_id in profile_provider.requested_profile_ids

    # The favourited-only profile was never handed to either provider — the fakes above would have
    # raised the instant it was, so reaching this line at all is already most of the assertion.
    assert favourited_profile_id not in match_provider.requested_profile_ids
    assert favourited_profile_id not in profile_provider.requested_profile_ids

    async with session_factory() as session:
        # Ingests nothing: no match was discovered for the favourited profile.
        favourited_match = await session.scalar(
            select(Match).where(Match.game_id == _GAME_ID_OFFSET + favourited_profile_id)
        )
        assert favourited_match is None

        # Archives nothing: no capture was ever enqueued for the favourited profile, so the drain
        # had nothing of theirs to claim, download or store.
        favourited_capture = await session.scalar(
            select(ReplayCapture).where(ReplayCapture.profile_id == favourited_profile_id)
        )
        assert favourited_capture is None

        # The favourited profile was not "seen" by ingestion: `touch_aoe_profile` is only ever
        # called over a raw match's own participants, and no raw match for this profile was ever
        # produced, so `last_seen_at` is exactly what seeding wrote, never refreshed by this run.
        favourited_profile = await session.get(AoeProfile, favourited_profile_id)
        assert favourited_profile is not None
        assert favourited_profile.last_seen_at == seeded_last_seen_at

        # The favourite itself is untouched: favouriting has no consequence beyond its own row.
        favourite_row = await session.scalar(
            select(Favourite).where(Favourite.profile_id == favourited_profile_id)
        )
        assert favourite_row is not None

    # The drain's own report is the "archives nothing" half stated in the run's own numbers. Its
    # one attempt is the linked profile's own legitimate capture (001 FR-013/FR-014), never stored
    # here only because `_ForbiddingReplayProvider` answers `NotFound` for it to stay cheap — the
    # property this task is about is that the favourited profile contributed nothing to any of
    # these counters at all, which the assertions above already proved directly against the rows.
    drain_report = report.stage_reports["drain"]
    assert drain_report["captures_attempted"] == 1
    assert drain_report["stored_total"] == 0
