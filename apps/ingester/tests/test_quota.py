"""Integration tests for the ingestion fairness quota (T047c, FR-044).

`aoe2stats_ingester.quota` (T058) exists and `apply_quota` is imported from inside each test body
below regardless — the test-first convention this file started under (CLAUDE.md's "Test-first
tasks and the green-tree gate") is kept even now that the module has landed, exactly as
`test_backfill.py`'s own module docstring explains for the same choice made there: nothing about
the convention requires reverting it once the module it protected against a collection error for
does exist.

**The contract `apply_quota` asserts** (`plan.md`'s own comment on the module: "per-user fairness
cap, with its deadline exemption"), unpacked into the tests below rather than restated as prose:

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
list is not touched by `apply_quota` itself in any way — "deferred" is a read-only filter over
already-claimed work, not a second write path of its own, which is also why `quota.py` is a sibling
of `budget.py` rather than living inside `capture.py` (T058's own task text, `plan.md`'s module
table). The unit tests below (`test_quota_defers_...` through `test_quota_is_independent_...`)
exercise exactly that pure function, in isolation from any claim or write path.

Resolving "aggregated across all of one user's linked profiles" needs a real join from
`replay_captures.profile_id` through the active `profile_links` row to `users.id` — precisely the
join a hand-built `profile_id -> user_id` mapping would let a fake sidestep — so every candidate in
the unit tests is backed by real `matches`, `aoe_profiles`, `profile_links` and `users` rows via the
`db_session` integration harness (`tests/db.py`, T015), never a stand-in for any of them.

**`test_the_drain_actually_enforces_the_quota_it_was_given` below is the different claim**: not that
`apply_quota` computes the right subsequence — the unit tests above already prove that — but that
`aoe2stats_ingester.capture.CaptureDrain` actually calls it. T058 shipped `apply_quota` fully tested
in isolation while `capture.py`'s drain never imported it, so FR-044 enforced nothing in production
even though every test in this file was green; that gap is what this one closes, by driving a real
`CaptureDrain` against the real database rather than calling `apply_quota` directly.
"""

from __future__ import annotations

import io
import uuid
import zipfile
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_core.alerting import AlertRecord
from aoe2stats_core.replay.validation import ReplayValidationResult
from aoe2stats_ingester.budget import Budget
from aoe2stats_providers.base import NotFound, ReplayBlob
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
    user = User(allowlisted_at=now)
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


# --- Integration test: the drain itself ---------------------------------------------------------
#
# Everything below drives a real `CaptureDrain` (`aoe2stats_ingester.capture`), not `apply_quota`
# directly, and — like `test_backfill.py`'s own equivalent scenario — seeds through
# `session_factory` rather than the shared `db_session` fixture: `CaptureDrain` opens its own
# sessions against the same database, on separate connections, so the rows this test seeds must
# already be committed before the drain can see them (`db_session`'s single transaction only
# commits at test teardown).

_QUOTA_PROFILE = 197_000_401
_GAME_NEAR_DEADLINE = 611_000_401  # exempt: must be stored despite the cap being in force.
_GAME_FAR_WITHIN_CAP = 611_000_402  # ordinary: first non-exempt claim, within `max_per_user=1`.
_GAME_FAR_OVER_CAP = 611_000_403  # ordinary: second non-exempt claim, surplus — must stay pending.

_QUOTA_MAX_PER_USER = 1
_QUOTA_EXEMPT_DAYS = 7


def _make_replay_zip(inner_filename: str, payload: bytes) -> bytes:
    """A genuine, well-formed single-member zip, the same shape `test_backfill.py`'s own helper
    builds — `CaptureDrain` validates whatever bytes the fake provider hands it, so the fixture
    blob must satisfy the fake validator below exactly as a real replay would satisfy a real one.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w") as archive:
        archive.writestr(inner_filename, payload)
    return buffer.getvalue()


class _QuotaFakeReplayProvider:
    """A `ReplayProvider` double (`contracts/providers.md`): answers the seeded blob for a known
    `(game_id, profile_id)` pair. Every call is recorded, so the test can assert the surplus,
    over-cap capture's `game_id` was never even asked for — proving the cap stopped the drain
    before the provider, not merely before the object store or the row's own status.
    """

    def __init__(self, blobs: dict[tuple[int, int], bytes]) -> None:
        self._blobs = blobs
        self.calls: list[tuple[int, int]] = []

    async def fetch_replay(self, game_id: int, profile_id: int) -> ReplayBlob | NotFound:
        self.calls.append((game_id, profile_id))
        content = self._blobs[(game_id, profile_id)]
        return ReplayBlob(
            content=content,
            filename=f"MP Replay {game_id}.aoe2record.zip",
            content_type="application/zip",
        )


class _QuotaFakeObjectStore:
    """Satisfies `CaptureDrain`'s `_ObjectPut` protocol (`put`/`get`) in memory — no bucket, no
    network (constitution III). `get` is never actually exercised by this scenario (nothing here
    triggers a resumed reclaim), but the protocol names both."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put(self, key: str, body: bytes, *, content_type: str = "application/zip") -> None:
        self.objects[key] = body

    async def get(self, key: str) -> bytes:
        return self.objects[key]


class _QuotaFakeReplayValidator:
    """Satisfies `packages/core`'s `ReplayValidator` Protocol. Always accepts the well-formed
    single-member zip `_make_replay_zip` builds — nothing in this scenario is about validation
    failure."""

    def validate(self, zip_bytes: bytes) -> ReplayValidationResult:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            names = archive.namelist()
        assert len(names) == 1, "fixture blob must itself be a single-member zip"
        return ReplayValidationResult(
            inner_filename=names[0],
            inner_bytes=len(zip_bytes),
            engine_name="fake-engine",
            engine_version="0.0.0-test",
        )


class _QuotaFakeAlertSink:
    """Satisfies `AlertSink` (`packages/core/src/aoe2stats_core/alerting.py`). Nothing here
    asserts on `records`: every capture in this scenario is far too recent to be past its own
    capture deadline, so nothing should ever be raised."""

    def __init__(self) -> None:
        self.records: list[AlertRecord] = []

    async def write(
        self,
        *,
        kind: str,
        severity: int,
        detail: Mapping[str, Any] | None,
        ingest_run_id: uuid.UUID | None,
    ) -> AlertRecord:
        record = AlertRecord(
            id=uuid.uuid4(),
            kind=kind,
            severity=severity,
            detail=detail,
            raised_at=datetime.now(UTC),
            ingest_run_id=ingest_run_id,
            acknowledged_at=None,
        )
        self.records.append(record)
        return record

    async def unacknowledged_severity_one(self) -> list[AlertRecord]:
        return [r for r in self.records if r.severity == 1 and r.acknowledged_at is None]


async def _seed_quota_user_with_three_captures(
    session_factory: async_sessionmaker[AsyncSession], *, now: datetime
) -> None:
    """One consenting user, one linked profile, three `pending` captures on it: one nearer than
    `_QUOTA_EXEMPT_DAYS` (exempt from the cap entirely) and two ordinary far-deadline ones — with
    `_QUOTA_MAX_PER_USER=1`, only the first ordinary one in claim order fits under the cap.
    """
    async with session_factory() as session:
        user = User(allowlisted_at=now)
        session.add(user)
        await session.flush()
        session.add(
            SteamIdentity(
                steam_id64="76500000000000401",
                user_id=user.id,
                verified_at=now,
                last_sign_in_at=now,
            )
        )
        session.add(AoeProfile(profile_id=_QUOTA_PROFILE, alias=f"player-{_QUOTA_PROFILE}"))
        await session.flush()
        session.add(
            ProfileLink(
                user_id=user.id,
                profile_id=_QUOTA_PROFILE,
                steam_id64="76500000000000401",
                is_primary=True,
                linked_at=now,
            )
        )
        for game_id in (_GAME_NEAR_DEADLINE, _GAME_FAR_WITHIN_CAP, _GAME_FAR_OVER_CAP):
            session.add(
                Match(
                    game_id=game_id,
                    leaderboard_id=3,
                    completed_at=now - timedelta(days=1),
                    source="relic",
                    raw_payload={},
                )
            )
        await session.flush()
        session.add(
            ReplayCapture(
                game_id=_GAME_NEAR_DEADLINE,
                profile_id=_QUOTA_PROFILE,
                status=CaptureStatus.PENDING,
                capture_deadline_at=now + _NEAR_DEADLINE,
                source=CaptureSource.AUTOMATIC,
            )
        )
        session.add(
            ReplayCapture(
                game_id=_GAME_FAR_WITHIN_CAP,
                profile_id=_QUOTA_PROFILE,
                status=CaptureStatus.PENDING,
                capture_deadline_at=now + _FAR_DEADLINE,
                source=CaptureSource.AUTOMATIC,
            )
        )
        session.add(
            ReplayCapture(
                game_id=_GAME_FAR_OVER_CAP,
                profile_id=_QUOTA_PROFILE,
                status=CaptureStatus.PENDING,
                capture_deadline_at=now + _FAR_DEADLINE + timedelta(days=1),
                source=CaptureSource.AUTOMATIC,
            )
        )
        await session.commit()


async def _capture_status(
    session_factory: async_sessionmaker[AsyncSession], *, game_id: int
) -> CaptureStatus:
    async with session_factory() as session:
        status = await session.scalar(
            select(ReplayCapture.status).where(ReplayCapture.game_id == game_id)
        )
    assert status is not None
    return status


async def test_the_drain_actually_enforces_the_quota_it_was_given(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
) -> None:
    """The gap this task closes: `apply_quota` computing the right answer (every test above) is
    not the same claim as `CaptureDrain` actually calling it. Constructed with
    `max_captures_per_user_per_run=1, quota_exempt_days=7` and given a single `__call__` — the cap
    is per run (`INGEST_MAX_CAPTURES_PER_USER_PER_RUN`'s own name), not cumulative across separate
    runs, so this test's assertions are only meaningful about *that one call* — against three
    `pending` captures for one user (one exempt, near its own deadline; two ordinary), a real drain
    must: store the exempt one regardless of the cap, store exactly one ordinary one (the first in
    claim order), and leave the surplus ordinary one `pending`, never even asking the replay
    provider for it.

    Run *before* this task's wiring landed (`git stash` on `capture.py`, `CaptureDrain.__init__`
    raising `TypeError` on the unknown `max_captures_per_user_per_run`/`quota_exempt_days`
    keywords), this test fails outright at construction — confirming it actually exercises the gap
    rather than passing vacuously either side of the fix.
    """
    from aoe2stats_ingester.capture import CaptureDrain

    now = datetime.now(UTC)
    await _seed_quota_user_with_three_captures(session_factory, now=now)

    blob = _make_replay_zip("MP Replay.aoe2record", b"quota fixture replay bytes")
    replay_provider = _QuotaFakeReplayProvider(
        {
            (_GAME_NEAR_DEADLINE, _QUOTA_PROFILE): blob,
            (_GAME_FAR_WITHIN_CAP, _QUOTA_PROFILE): blob,
            # Deliberately no entry for `_GAME_FAR_OVER_CAP`: the cap must stop the drain before
            # this provider is ever asked about it (see the assertion on `.calls` below) — if the
            # drain claimed and processed it anyway, this dict lookup itself would raise `KeyError`
            # and fail the test just as loudly.
        }
    )
    object_store = _QuotaFakeObjectStore()

    drain = CaptureDrain(
        session_factory=session_factory,
        replay_provider=replay_provider,
        object_store=object_store,
        validator=_QuotaFakeReplayValidator(),
        alert_sink=_QuotaFakeAlertSink(),
        max_captures_per_user_per_run=_QUOTA_MAX_PER_USER,
        quota_exempt_days=_QUOTA_EXEMPT_DAYS,
    )

    # One call, deliberately: `INGEST_MAX_CAPTURES_PER_USER_PER_RUN`'s own name and
    # `.env.example`'s comment on it ("fairness between users within one run") both say the cap is
    # per `__call__`, not cumulative across separate runs — a second call would legitimately start
    # a fresh cap and let the surplus capture through, which would prove nothing about whether
    # *this* run honoured its own cap.
    await drain(Budget(seconds=60))

    assert await _capture_status(session_factory, game_id=_GAME_NEAR_DEADLINE) == (
        CaptureStatus.STORED
    )
    assert await _capture_status(session_factory, game_id=_GAME_FAR_WITHIN_CAP) == (
        CaptureStatus.STORED
    )
    assert await _capture_status(session_factory, game_id=_GAME_FAR_OVER_CAP) == (
        CaptureStatus.PENDING
    )
    assert (_GAME_FAR_OVER_CAP, _QUOTA_PROFILE) not in replay_provider.calls
