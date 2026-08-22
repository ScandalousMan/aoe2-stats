"""Integration test for the ingestion fairness quota (T047c, FR-044).

`aoe2stats_ingester.quota` (T058) does not exist yet. Every test below is `@pytest.mark.xfail(
strict=True, ...)` for that reason (CLAUDE.md's "Test-first tasks and the green-tree gate") and
imports the module from inside the test body, so a missing module is a caught failure rather than
a collection error that would take the rest of the workspace suite down with it.

**The contract asserted here**, since nothing pins one down more specifically than `plan.md`'s own
comment on the module ("per-user fairness cap, with its deadline exemption"):

    async def apply_quota(
        session: AsyncSession,
        candidates: Sequence[ReplayCapture],
        *,
        max_per_user: int,
        exempt_days: int,
        now: datetime,
    ) -> list[ReplayCapture]: ...

`candidates` is a run's already-claimed work, in claim order (`capture_deadline_at` ascending — the
order `data-model.md`'s claiming query produces). `apply_quota` returns the subsequence of it a run
may actually process this cycle, in the same relative order. A capture dropped from the returned
list is not touched in any way: it stays exactly as claimed, for the next cycle's own claim query to
pick up again — "deferred" is a read-only filter over already-claimed work, not a second write path
of its own, which is also why `quota.py` is a sibling of `budget.py` rather than living inside
`capture.py` (T058's own task text, `plan.md`'s module table).

Resolving "aggregated across all of one user's linked profiles" needs a real join from
`replay_captures.profile_id` through the active `profile_links` row to `users.id` — precisely the
join a hand-built `profile_id -> user_id` mapping would let a fake sidestep — so every candidate
below is backed by real `matches`, `aoe_profiles`, `profile_links` and `users` rows via the
`db_session` integration harness (`tests/db.py`, T015), never a stand-in for any of them.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_storage.models import (
    AoeProfile,
    CaptureSource,
    CaptureStatus,
    Match,
    ProfileLink,
    ReplayCapture,
    SteamIdentity,
    User,
)

#: Well outside `_EXEMPT_DAYS`: a capture at this remove is ordinary quota-bound work.
_FAR_DEADLINE = timedelta(days=20)
#: Well inside `_EXEMPT_DAYS`: a capture at this remove is the one FR-044 says the quota must
#: never delay, whatever the cap already says about the user it belongs to.
_NEAR_DEADLINE = timedelta(days=3)
_EXEMPT_DAYS = 7


async def _seed_user(db_session: AsyncSession, *, steam_id64: str) -> User:
    now = datetime.now(UTC)
    user = User(allowlisted_at=now, ingest_consent_at=now)
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        SteamIdentity(steam_id64=steam_id64, user_id=user.id, verified_at=now, last_sign_in_at=now)
    )
    await db_session.flush()
    return user


async def _link_profile(
    db_session: AsyncSession, *, user: User, profile_id: int, steam_id64: str
) -> None:
    """One active `profile_links` row on `user` for `profile_id` — a user may hold several of
    these, which is exactly the fan-out `apply_quota` must aggregate across rather than cap
    per-profile."""
    now = datetime.now(UTC)
    db_session.add(AoeProfile(profile_id=profile_id, alias=f"player-{profile_id}"))
    await db_session.flush()
    db_session.add(
        ProfileLink(
            user_id=user.id,
            profile_id=profile_id,
            steam_id64=steam_id64,
            is_primary=False,
            linked_at=now,
        )
    )
    await db_session.flush()


async def _seed_capture(
    db_session: AsyncSession, *, game_id: int, profile_id: int, capture_deadline_at: datetime
) -> ReplayCapture:
    """One `pending` capture for an already-linked `profile_id`, with a `matches` row underneath
    it to satisfy the foreign key — `completed_at` itself is irrelevant to the quota, only
    `capture_deadline_at` is, so it is left at an arbitrary fixed offset."""
    now = datetime.now(UTC)
    db_session.add(
        Match(
            game_id=game_id,
            leaderboard_id=3,
            completed_at=now - timedelta(days=1),
            source="relic",
            raw_payload={},
        )
    )
    await db_session.flush()
    capture = ReplayCapture(
        game_id=game_id,
        profile_id=profile_id,
        status=CaptureStatus.PENDING,
        capture_deadline_at=capture_deadline_at,
        source=CaptureSource.AUTOMATIC,
    )
    db_session.add(capture)
    await db_session.flush()
    return capture


async def test_quota_defers_a_capture_once_the_per_user_cap_is_reached(
    db_session: AsyncSession,
) -> None:
    """FR-044's core rule: once `max_per_user` of one user's captures have been let through, a
    further capture for that same user is deferred rather than processed this run."""
    from aoe2stats_ingester.quota import apply_quota

    now = datetime.now(UTC)
    user = await _seed_user(db_session, steam_id64="76500000000000001")
    await _link_profile(db_session, user=user, profile_id=910_001, steam_id64="76500000000000001")

    c1 = await _seed_capture(
        db_session, game_id=920_001, profile_id=910_001, capture_deadline_at=now + _FAR_DEADLINE
    )
    c2 = await _seed_capture(
        db_session,
        game_id=920_002,
        profile_id=910_001,
        capture_deadline_at=now + _FAR_DEADLINE + timedelta(days=1),
    )
    c3 = await _seed_capture(
        db_session,
        game_id=920_003,
        profile_id=910_001,
        capture_deadline_at=now + _FAR_DEADLINE + timedelta(days=2),
    )

    allowed = await apply_quota(
        db_session, [c1, c2, c3], max_per_user=2, exempt_days=_EXEMPT_DAYS, now=now
    )

    assert [row.id for row in allowed] == [c1.id, c2.id]


async def test_quota_is_aggregated_across_all_of_a_users_linked_profiles(
    db_session: AsyncSession,
) -> None:
    """FR-044: the cap counts one user's captures across *every* profile they have linked, never
    per profile. With `max_per_user=1` and one far-deadline capture on each of two of the same
    user's profiles, a per-profile cap would wrongly let both through (1 <= 1 on each profile); the
    aggregated cap this task requires lets through only the first one, whichever profile it
    belongs to."""
    from aoe2stats_ingester.quota import apply_quota

    now = datetime.now(UTC)
    user = await _seed_user(db_session, steam_id64="76500000000000002")
    await _link_profile(db_session, user=user, profile_id=910_010, steam_id64="76500000000000002")
    await _link_profile(db_session, user=user, profile_id=910_011, steam_id64="76500000000000002")

    on_first_profile = await _seed_capture(
        db_session, game_id=920_010, profile_id=910_010, capture_deadline_at=now + _FAR_DEADLINE
    )
    on_second_profile = await _seed_capture(
        db_session,
        game_id=920_011,
        profile_id=910_011,
        capture_deadline_at=now + _FAR_DEADLINE + timedelta(days=1),
    )

    allowed = await apply_quota(
        db_session,
        [on_first_profile, on_second_profile],
        max_per_user=1,
        exempt_days=_EXEMPT_DAYS,
        now=now,
    )

    assert [row.id for row in allowed] == [on_first_profile.id]


async def test_quota_exemption_runs_a_near_deadline_capture_despite_the_cap(
    db_session: AsyncSession,
) -> None:
    """FR-044's exemption, which is the whole point of the requirement: a capture whose
    `capture_deadline_at` is nearer than `exempt_days` runs anyway, even though the user's cap is
    already spent by captures ahead of it in claim order — a cap that delayed it to serve captures
    with time to spare would invert the priority the whole system is built on."""
    from aoe2stats_ingester.quota import apply_quota

    now = datetime.now(UTC)
    user = await _seed_user(db_session, steam_id64="76500000000000003")
    await _link_profile(db_session, user=user, profile_id=910_020, steam_id64="76500000000000003")

    c1 = await _seed_capture(
        db_session, game_id=920_020, profile_id=910_020, capture_deadline_at=now + _FAR_DEADLINE
    )
    c2 = await _seed_capture(
        db_session,
        game_id=920_021,
        profile_id=910_020,
        capture_deadline_at=now + _FAR_DEADLINE + timedelta(days=1),
    )
    # Over the cap, and not exempt: this one stays deferred.
    over_cap_far = await _seed_capture(
        db_session,
        game_id=920_022,
        profile_id=910_020,
        capture_deadline_at=now + _FAR_DEADLINE + timedelta(days=2),
    )
    # Over the cap, but exempt: this one must run despite arriving after the cap was spent.
    exempt = await _seed_capture(
        db_session, game_id=920_023, profile_id=910_020, capture_deadline_at=now + _NEAR_DEADLINE
    )

    allowed = await apply_quota(
        db_session,
        [c1, c2, over_cap_far, exempt],
        max_per_user=2,
        exempt_days=_EXEMPT_DAYS,
        now=now,
    )

    assert [row.id for row in allowed] == [c1.id, c2.id, exempt.id]


async def test_quota_exemption_does_not_itself_spend_the_cap(
    db_session: AsyncSession,
) -> None:
    """The mirror of the previous test, and the case that actually distinguishes "exempt" from
    "counts as a freebie slot": an exempt capture arriving *first* in claim order must still leave
    the full `max_per_user` cap available to the ordinary, non-exempt captures behind it — the
    exemption bypasses the quota mechanism entirely rather than consuming one of its slots."""
    from aoe2stats_ingester.quota import apply_quota

    now = datetime.now(UTC)
    user = await _seed_user(db_session, steam_id64="76500000000000004")
    await _link_profile(db_session, user=user, profile_id=910_030, steam_id64="76500000000000004")

    exempt = await _seed_capture(
        db_session, game_id=920_030, profile_id=910_030, capture_deadline_at=now + _NEAR_DEADLINE
    )
    c1 = await _seed_capture(
        db_session, game_id=920_031, profile_id=910_030, capture_deadline_at=now + _FAR_DEADLINE
    )
    c2 = await _seed_capture(
        db_session,
        game_id=920_032,
        profile_id=910_030,
        capture_deadline_at=now + _FAR_DEADLINE + timedelta(days=1),
    )
    over_cap = await _seed_capture(
        db_session,
        game_id=920_033,
        profile_id=910_030,
        capture_deadline_at=now + _FAR_DEADLINE + timedelta(days=2),
    )

    allowed = await apply_quota(
        db_session,
        [exempt, c1, c2, over_cap],
        max_per_user=2,
        exempt_days=_EXEMPT_DAYS,
        now=now,
    )

    assert [row.id for row in allowed] == [exempt.id, c1.id, c2.id]


async def test_quota_is_independent_between_users(db_session: AsyncSession) -> None:
    """FR-044: the cap belongs to one user's own captures. A second user's captures must be
    allowed up to their own `max_per_user`, unaffected by however much of the first user's quota
    has already been spent — a shared global counter would wrongly cap the two users' combined
    total at `max_per_user` instead of granting each their own."""
    from aoe2stats_ingester.quota import apply_quota

    now = datetime.now(UTC)
    user_a = await _seed_user(db_session, steam_id64="76500000000000005")
    await _link_profile(db_session, user=user_a, profile_id=910_040, steam_id64="76500000000000005")
    user_b = await _seed_user(db_session, steam_id64="76500000000000006")
    await _link_profile(db_session, user=user_b, profile_id=910_041, steam_id64="76500000000000006")

    a1 = await _seed_capture(
        db_session, game_id=920_040, profile_id=910_040, capture_deadline_at=now + _FAR_DEADLINE
    )
    b1 = await _seed_capture(
        db_session, game_id=920_041, profile_id=910_041, capture_deadline_at=now + _FAR_DEADLINE
    )
    a2 = await _seed_capture(
        db_session,
        game_id=920_042,
        profile_id=910_040,
        capture_deadline_at=now + _FAR_DEADLINE + timedelta(days=1),
    )
    b2 = await _seed_capture(
        db_session,
        game_id=920_043,
        profile_id=910_041,
        capture_deadline_at=now + _FAR_DEADLINE + timedelta(days=1),
    )
    # Both over each user's own cap of 2 — both must be deferred, not just one of them.
    a3 = await _seed_capture(
        db_session,
        game_id=920_044,
        profile_id=910_040,
        capture_deadline_at=now + _FAR_DEADLINE + timedelta(days=2),
    )
    b3 = await _seed_capture(
        db_session,
        game_id=920_045,
        profile_id=910_041,
        capture_deadline_at=now + _FAR_DEADLINE + timedelta(days=2),
    )

    allowed = await apply_quota(
        db_session,
        [a1, b1, a2, b2, a3, b3],
        max_per_user=2,
        exempt_days=_EXEMPT_DAYS,
        now=now,
    )

    assert [row.id for row in allowed] == [a1.id, b1.id, a2.id, b2.id]
