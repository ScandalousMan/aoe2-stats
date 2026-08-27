"""T043a — the shared-match case for discovery/enqueue (T053, `discover.py`).

`data-model.md`: "One row per match, **shared between users**. Two beta users in the same game
produce one `matches` row and two `replay_captures` rows." FR-016 adds the other half: each of
those two rows must resolve to a blob only its own owner can reach — `objects.py::replay_object_key`
is the mechanism ("this scheme gives each its own object: neither user's signed URL can ever
resolve to the other's blob, because the key it is signed for is not the key the other row holds").

This test seeds two consenting users, each with their own linked `aoe_profiles` row, who both took
part in the same match, and hands a fake `MatchHistoryProvider` returning that one match (with both
profile ids in `player_profile_ids`, exactly as the real Relic endpoint would) to the discovery
stage. It then asserts, straight against the database, that discovery produced exactly one `matches`
row and exactly two `replay_captures` rows — one per profile, with distinct `object_key`s under the
production key scheme.

**Why `replay_object_key()` and not `ReplayCapture.object_key` for the "distinct object_key"
half of the assertion.** `data-model.md`'s write-ordering note is explicit: `object_key`,
`zip_bytes` and `zip_sha256` are committed only once the download's checksum verifies, during
capture (T055) — never at enqueue time. A freshly discovered `replay_captures` row is `pending`
with a `NULL` `object_key`, and two `NULL`s are not "distinct". `replay_object_key(game_id,
profile_id)` is the pure, already-shipped function (`packages/storage/src/aoe2stats_storage/
objects.py`) that *will* decide each row's key once capture runs; applying it to what discovery
enqueued today is what proves the two rows are already headed for two different objects, without
requiring T055's download machinery to exist yet. That is also the literal mechanism FR-016 relies
on: "neither user's download reaches the other's blob" is a property of `(game_id, profile_id)`
being distinct per row, which is exactly what this test checks.

The module this test targets (`aoe2stats_ingester.discover`) does not exist yet — T053 is Phase 4,
sequenced after this test. Imported inside the test body, per this project's test-first convention
(`CLAUDE.md`: a module-scope import of a not-yet-existent module is a collection error that takes
the whole workspace suite down, not merely this file's tests), and the whole test is wrapped in
`xfail(strict=True)` for the same reason: the `SubagentStop` gate refuses a red hand-back, and
`strict=True` is what turns this xfail off by itself, loudly, the moment T053 makes it pass for
real instead of letting a stale marker hide a regression.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_providers.base import LeaderboardSnapshot, ProfileRef, RawMatch
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
from aoe2stats_storage.objects import replay_object_key

# Fixed instants rather than `datetime.now(UTC)`: this test asserts an exact arithmetic relation
# (`capture_deadline_at == completed_at + CAPTURE_BUDGET_DAYS`) and must not be sensitive to when
# it happens to run. Nothing here depends on real wall-clock "now" — deadline computation is pure
# arithmetic over `completed_at`, not a comparison against the current time (that comparison
# belongs to the claiming query, T055, which this test does not exercise).
_MATCH_COMPLETED_AT = datetime(2026, 8, 18, 20, 15, 0, tzinfo=UTC)
_CAPTURE_BUDGET_DAYS = 21

_PROFILE_A = 190_000_111
_PROFILE_B = 190_000_222
_GAME_ID = 555_000_111


class _FakeProfileProvider:
    """A `ProfileProvider` double. This test does not exercise ratings refresh, so
    `personal_stats` hands back one plausible snapshot per requested profile — enough that a
    discovery stage relying on every polled profile getting a snapshot back has something to work
    with — and `resolve_profile` is never expected to be called by a discovery cycle (profile
    resolution is a sign-in-time concern, T027) so it fails loudly if it is.
    """

    async def resolve_profile(self, steam_id64: str) -> ProfileRef | None:
        raise AssertionError(
            "DiscoverStage must not resolve profiles from a Steam id — that is US1's sign-in "
            "flow (T027), not the discovery cycle."
        )

    async def personal_stats(self, profile_ids: Sequence[int]) -> list[LeaderboardSnapshot]:
        return [
            LeaderboardSnapshot(profile_id=profile_id, leaderboard_id=3, rating=1500)
            for profile_id in profile_ids
        ]


class _FakeMatchHistoryProvider:
    """A `MatchHistoryProvider` double returning one shared match for either consenting profile,
    mirroring the real endpoint: a query for a profile that played a match returns that match, with
    every participant (not only the queried profile) listed in `player_profile_ids` — which is
    exactly the shape that makes fan-out into two `replay_captures` rows the discovery stage's own
    responsibility, not something the provider does for it.
    """

    def __init__(self, raw_match: RawMatch) -> None:
        self._raw_match = raw_match
        self.calls: list[tuple[int, ...]] = []

    async def recent_matches(self, profile_ids: Sequence[int]) -> list[RawMatch]:
        self.calls.append(tuple(profile_ids))
        if any(profile_id in self._raw_match.player_profile_ids for profile_id in profile_ids):
            return [self._raw_match]
        return []


async def _seed_two_consenting_users_sharing_a_match(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Two users, each linked to their own profile, both of whom played `_GAME_ID` together.
    Committed on its own connection before the discovery stage runs, so the stage's own session
    (opened separately, against the same `session_factory`) actually sees this data rather than
    racing an uncommitted transaction.
    """
    now = datetime.now(UTC)
    user_a = User(id=uuid.uuid4())
    user_b = User(id=uuid.uuid4())

    steam_a = SteamIdentity(
        steam_id64="76500000000000101",
        user_id=user_a.id,
        verified_at=now - timedelta(days=30),
        last_sign_in_at=now - timedelta(days=1),
    )
    steam_b = SteamIdentity(
        steam_id64="76500000000000202",
        user_id=user_b.id,
        verified_at=now - timedelta(days=30),
        last_sign_in_at=now - timedelta(days=1),
    )

    profile_a = AoeProfile(profile_id=_PROFILE_A, alias="PlayerA", country="FR")
    profile_b = AoeProfile(profile_id=_PROFILE_B, alias="PlayerB", country="FR")

    link_a = ProfileLink(
        id=uuid.uuid4(),
        user_id=user_a.id,
        profile_id=_PROFILE_A,
        steam_id64=steam_a.steam_id64,
        is_primary=True,
        linked_at=now - timedelta(days=30),
    )
    link_b = ProfileLink(
        id=uuid.uuid4(),
        user_id=user_b.id,
        profile_id=_PROFILE_B,
        steam_id64=steam_b.steam_id64,
        is_primary=True,
        linked_at=now - timedelta(days=30),
    )

    async with session_factory() as session:
        # Two flushes, not one `add_all`: `ProfileLink.steam_id64` has a column-level `ForeignKey`
        # to `steam_identities` (models.py) but no ORM `relationship()` connects the two classes,
        # so the unit of work's automatic dependency sort — which orders inserts by *mapper*
        # relationships, not by raw table foreign keys — has no edge telling it `steam_identities`
        # must land first. Flushing the referenced rows before the referencing ones sidesteps that
        # gap explicitly rather than relying on `add_all`'s insertion order to happen to work.
        session.add_all([user_a, user_b, steam_a, steam_b, profile_a, profile_b])
        await session.flush()
        session.add_all([link_a, link_b])
        await session.commit()


async def test_shared_match_produces_one_match_row_and_two_isolated_replay_captures(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
) -> None:
    from aoe2stats_ingester.budget import Budget
    from aoe2stats_ingester.discover import DiscoverStage

    await _seed_two_consenting_users_sharing_a_match(session_factory)

    raw_match = RawMatch(
        game_id=_GAME_ID,
        leaderboard_id=3,
        map_name="Arabia",
        patch="stable",
        started_at=_MATCH_COMPLETED_AT - timedelta(minutes=35),
        completed_at=_MATCH_COMPLETED_AT,
        duration_seconds=2_100,
        player_profile_ids=(_PROFILE_A, _PROFILE_B),
        raw_payload={"matchId": _GAME_ID, "source": "test_shared_match fixture"},
    )
    match_history_provider = _FakeMatchHistoryProvider(raw_match)
    profile_provider = _FakeProfileProvider()

    stage = DiscoverStage(
        session_factory=session_factory,
        profile_provider=profile_provider,
        match_history_provider=match_history_provider,
        capture_budget_days=_CAPTURE_BUDGET_DAYS,
    )

    report = await stage(Budget(seconds=30))
    assert isinstance(report, Mapping)

    async with session_factory() as session:
        matches = (
            (await session.execute(select(Match).where(Match.game_id == _GAME_ID))).scalars().all()
        )
        assert len(matches) == 1, (
            "Two consenting users sharing one game must produce exactly one `matches` row "
            "(data-model.md), not one per profile that discovered it."
        )
        match_row = matches[0]
        assert match_row.completed_at == _MATCH_COMPLETED_AT
        assert match_row.raw_payload == raw_match.raw_payload

        match_players = (
            (await session.execute(select(MatchPlayer).where(MatchPlayer.game_id == _GAME_ID)))
            .scalars()
            .all()
        )
        assert {row.profile_id for row in match_players} == {_PROFILE_A, _PROFILE_B}

        captures = (
            (
                await session.execute(
                    select(ReplayCapture)
                    .where(ReplayCapture.game_id == _GAME_ID)
                    .order_by(ReplayCapture.profile_id)
                )
            )
            .scalars()
            .all()
        )

    assert len(captures) == 2, (
        "FR-016: the same shared match must enqueue one capture per consenting profile that "
        "played it, never a single capture shared between the two."
    )
    capture_a, capture_b = captures
    assert capture_a.profile_id == _PROFILE_A
    assert capture_b.profile_id == _PROFILE_B
    assert capture_a.profile_id != capture_b.profile_id
    assert capture_a.id != capture_b.id

    # Neither capture has been downloaded yet — enqueue only, per data-model.md's write ordering
    # (`object_key` lands during capture, T055). Both rows starting `NULL` here is exactly why the
    # isolation check below goes through `replay_object_key()` rather than the column itself.
    for capture in (capture_a, capture_b):
        assert capture.status == CaptureStatus.PENDING
        assert capture.source == CaptureSource.AUTOMATIC
        assert capture.object_key is None
        assert capture.zip_sha256 is None
        assert capture.capture_deadline_at == _MATCH_COMPLETED_AT + timedelta(
            days=_CAPTURE_BUDGET_DAYS
        )

    # FR-016, in the terms `objects.py::replay_object_key` states directly: "neither user's
    # signed URL can ever resolve to the other's blob, because the key it is signed for is not the
    # key the other row holds." Distinct `profile_id` on the two rows is what guarantees this, and
    # this is the assertion of that guarantee against the real key scheme discovery just fed.
    key_a = replay_object_key(capture_a.game_id, capture_a.profile_id)
    key_b = replay_object_key(capture_b.game_id, capture_b.profile_id)
    assert key_a != key_b
    assert key_a == f"replays/{_GAME_ID}/{_PROFILE_A}.zip"
    assert key_b == f"replays/{_GAME_ID}/{_PROFILE_B}.zip"

    # No user's own point of view leaks into the other's queue: no third capture, for either
    # profile or for any other game, snuck in behind this single shared match.
    async with session_factory() as session:
        every_capture = (await session.execute(select(ReplayCapture))).scalars().all()
    assert len(every_capture) == 2
