"""T721 - a capture the claim refuses gets the terminal status `withdrawn` once its capture deadline
has passed.

Level: `CaptureDrain.withdraw_refused_past_deadline` called directly (the statement), then
`run_once` over a drain stage (its place in the cycle), then `_claim_batch` (it never takes a
`withdrawn` row). The three readers that filter on the deadline and the status have their own tests
beside the readers: `test_deadline_alert.py`, `scripts/checks/tests/test_capture_audit.py` and
`apps/analyzer/tests/test_admission.py`.

The statement withdraws a row that is past its deadline, is `pending` (whatever its
`next_attempt_at`) or a stale `downloading` row, and whose profile has no active link whose user has
not objected:

- the user unlinked; the user objected and the link is active; no link was ever written; the next
  attempt time has not come (a `pending` row); the stale `downloading` row holds a committed object;
- in each, `status` and `last_error` are the only columns that change (`_snapshot` compares the
  rest), so an object key, a checksum, `attempts` and `claimed_at` are as they were.

Left as it is, each asserted unchanged: the same rows one hour before their deadline; a
`downloading` row that is not stale; a row whose profile has an active link whose user has not
objected; a profile relinked by a second user who has not objected; a `stored` row with no owner and
the other terminal statuses.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.links import link_profile

from aoe2stats_ingester.capture import WITHDRAWN_REASON, CaptureDrain
from aoe2stats_storage.models import (
    Alert,
    AlertKind,
    AoeProfile,
    CaptureSource,
    CaptureStatus,
    Match,
    ReplayCapture,
)

Arm = Literal["pending", "stale_downloading", "fresh_downloading"]

_BASE_GAME_ID = 940_000_000
_BASE_PROFILE_ID = 240_000_000
_OBJECT_PREFIX = "replays"
_ZIP_SHA256 = "b" * 64


class _NeverCalledProvider:
    async def fetch_replay(self, game_id: int, profile_id: int) -> object:  # pragma: no cover
        raise AssertionError("these tests withdraw or claim; they never fetch")


def _drain(session_factory: async_sessionmaker[AsyncSession]) -> CaptureDrain:
    return CaptureDrain(
        session_factory=session_factory,
        replay_provider=_NeverCalledProvider(),  # type: ignore[arg-type]
    )


async def _seed_capture(
    db_session: AsyncSession,
    *,
    index: int = 0,
    arm: Arm = "pending",
    status: CaptureStatus | None = None,
    deadline_in: timedelta = timedelta(hours=-1),
    next_attempt_in: timedelta = timedelta(minutes=-1),
    with_object: bool = False,
) -> tuple[uuid.UUID, int]:
    """One capture of profile `_BASE_PROFILE_ID + index`, flushed with no link of any kind.
    `deadline_in` is relative to now (negative: past). `arm` picks the status and claim state:
    `pending`, a `downloading` row claimed an hour ago (stale against the default 300 s) or one
    claimed ten seconds ago (not stale). `status` overrides the arm's. `with_object` gives the row
    the committed object a killed run leaves behind. Returns the capture id and its profile id."""
    now = datetime.now(UTC)
    game_id = _BASE_GAME_ID + index
    profile_id = _BASE_PROFILE_ID + index
    capture_id = uuid.uuid4()
    db_session.add(AoeProfile(profile_id=profile_id, alias=f"withdraw-{index}", country="FR"))
    db_session.add(
        Match(
            game_id=game_id,
            leaderboard_id=3,
            completed_at=now + deadline_in - timedelta(days=21),
            source="relic",
            raw_payload={},
        )
    )
    await db_session.flush()
    if status is None:
        status = CaptureStatus.PENDING if arm == "pending" else CaptureStatus.DOWNLOADING
    claimed_at = {
        "pending": None,
        "stale_downloading": now - timedelta(hours=1),
        "fresh_downloading": now - timedelta(seconds=10),
    }[arm]
    db_session.add(
        ReplayCapture(
            id=capture_id,
            game_id=game_id,
            profile_id=profile_id,
            status=status,
            capture_deadline_at=now + deadline_in,
            attempts=0 if arm == "pending" else 1,
            next_attempt_at=now + next_attempt_in,
            claimed_at=claimed_at,
            first_seen_at=now - timedelta(days=22),
            source=CaptureSource.AUTOMATIC,
            http_status=404 if arm == "pending" else None,
            object_key=f"{_OBJECT_PREFIX}/{game_id}/{profile_id}.zip" if with_object else None,
            zip_bytes=1024 if with_object else None,
            zip_sha256=_ZIP_SHA256 if with_object else None,
        )
    )
    await db_session.flush()
    return capture_id, profile_id


async def _snapshot(db_session: AsyncSession, capture_id: uuid.UUID) -> dict[str, Any]:
    """Every column of the row, as stored (the session is expired first, so this reads the table)"""
    await db_session.commit()
    db_session.expire_all()
    row = await db_session.get(ReplayCapture, capture_id)
    assert row is not None
    return {column.key: getattr(row, column.key) for column in inspect(ReplayCapture).column_attrs}


Owner = Literal["unlinked", "objector", "never_linked"]


async def _give_owner(db_session: AsyncSession, profile_id: int, owner: Owner) -> None:
    if owner == "unlinked":
        await link_profile(db_session, profile_id, unlinked=True)
    elif owner == "objector":
        await link_profile(db_session, profile_id, objected=True)


@pytest.mark.parametrize(
    ("arm", "owner", "next_attempt_in", "with_object"),
    [
        ("pending", "unlinked", timedelta(minutes=-1), False),
        ("pending", "objector", timedelta(minutes=-1), False),
        ("pending", "never_linked", timedelta(minutes=-1), False),
        ("pending", "unlinked", timedelta(days=2), False),
        ("pending", "objector", timedelta(days=2), False),
        ("stale_downloading", "unlinked", timedelta(minutes=-1), False),
        ("stale_downloading", "objector", timedelta(minutes=-1), False),
        ("stale_downloading", "unlinked", timedelta(minutes=-1), True),
        ("stale_downloading", "objector", timedelta(minutes=-1), True),
    ],
)
async def test_a_refused_row_past_its_deadline_is_withdrawn_and_nothing_else_changes(
    arm: Arm,
    owner: Owner,
    next_attempt_in: timedelta,
    with_object: bool,
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    capture_id, profile_id = await _seed_capture(
        db_session, arm=arm, next_attempt_in=next_attempt_in, with_object=with_object
    )
    await _give_owner(db_session, profile_id, owner)
    before = await _snapshot(db_session, capture_id)

    changed = await _drain(session_factory).withdraw_refused_past_deadline(now=datetime.now(UTC))

    assert changed == 1
    after = await _snapshot(db_session, capture_id)
    assert after["status"] == CaptureStatus.WITHDRAWN
    assert after["last_error"] == WITHDRAWN_REASON
    assert {k: v for k, v in after.items() if k not in ("status", "last_error")} == {
        k: v for k, v in before.items() if k not in ("status", "last_error")
    }, "the write sets the status and the reason and nothing else"
    assert (after["attempts"], after["claimed_at"]) == (before["attempts"], before["claimed_at"])
    if with_object:
        assert (after["object_key"], after["zip_sha256"]) == (
            before["object_key"],
            before["zip_sha256"],
        )
        assert after["object_key"] is not None


async def test_a_second_call_changes_nothing(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    capture_id, profile_id = await _seed_capture(db_session)
    await _give_owner(db_session, profile_id, "unlinked")
    await db_session.commit()
    drain = _drain(session_factory)
    assert await drain.withdraw_refused_past_deadline(now=datetime.now(UTC)) == 1
    first = await _snapshot(db_session, capture_id)

    assert await drain.withdraw_refused_past_deadline(now=datetime.now(UTC)) == 0
    assert await _snapshot(db_session, capture_id) == first


# --- Left as it is --------------------------------------------------------------------------


@pytest.mark.parametrize("arm", ["pending", "stale_downloading"])
@pytest.mark.parametrize("owner", ["unlinked", "objector", "never_linked"])
async def test_the_same_row_one_hour_before_its_deadline_is_left_as_it_is(
    arm: Arm,
    owner: Owner,
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    capture_id, profile_id = await _seed_capture(
        db_session, arm=arm, deadline_in=timedelta(hours=1), with_object=arm != "pending"
    )
    await _give_owner(db_session, profile_id, owner)
    before = await _snapshot(db_session, capture_id)

    changed = await _drain(session_factory).withdraw_refused_past_deadline(now=datetime.now(UTC))

    assert changed == 0
    assert await _snapshot(db_session, capture_id) == before


@pytest.mark.parametrize("owner", ["unlinked", "objector", "never_linked"])
async def test_a_downloading_row_that_is_not_stale_is_left_as_it_is(
    owner: Owner,
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The download in flight, which T713 left to the user."""
    capture_id, profile_id = await _seed_capture(db_session, arm="fresh_downloading")
    await _give_owner(db_session, profile_id, owner)
    before = await _snapshot(db_session, capture_id)

    changed = await _drain(session_factory).withdraw_refused_past_deadline(now=datetime.now(UTC))

    assert changed == 0
    assert await _snapshot(db_session, capture_id) == before


@pytest.mark.parametrize("arm", ["pending", "stale_downloading"])
async def test_a_row_with_an_active_link_whose_user_has_not_objected_is_left_as_it_is(
    arm: Arm,
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """It stays for the deadline alert."""
    capture_id, profile_id = await _seed_capture(db_session, arm=arm)
    await link_profile(db_session, profile_id)
    before = await _snapshot(db_session, capture_id)

    changed = await _drain(session_factory).withdraw_refused_past_deadline(now=datetime.now(UTC))

    assert changed == 0
    assert await _snapshot(db_session, capture_id) == before


@pytest.mark.parametrize("arm", ["pending", "stale_downloading"])
@pytest.mark.parametrize("first_user_objected", [False, True])
async def test_a_profile_relinked_by_a_second_user_who_has_not_objected_is_left_as_it_is(
    arm: Arm,
    first_user_objected: bool,
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    capture_id, profile_id = await _seed_capture(db_session, arm=arm)
    await link_profile(db_session, profile_id, objected=first_user_objected, unlinked=True)
    await link_profile(db_session, profile_id, second_user=True)
    before = await _snapshot(db_session, capture_id)

    changed = await _drain(session_factory).withdraw_refused_past_deadline(now=datetime.now(UTC))

    assert changed == 0
    assert await _snapshot(db_session, capture_id) == before


@pytest.mark.parametrize(
    "status",
    [
        CaptureStatus.STORED,
        CaptureStatus.QUARANTINED,
        CaptureStatus.UNAVAILABLE,
        CaptureStatus.EXPIRED,
        CaptureStatus.FAILED,
    ],
)
async def test_a_row_in_any_other_status_with_no_owner_is_left_as_it_is(
    status: CaptureStatus,
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    capture_id, _ = await _seed_capture(
        db_session, status=status, with_object=status in (CaptureStatus.STORED,)
    )
    before = await _snapshot(db_session, capture_id)

    changed = await _drain(session_factory).withdraw_refused_past_deadline(now=datetime.now(UTC))

    assert changed == 0
    assert await _snapshot(db_session, capture_id) == before


# --- The claim never takes a withdrawn row ----------------------------------------------------


@pytest.mark.parametrize("arm", ["pending", "stale_downloading"])
async def test_the_claim_never_takes_a_withdrawn_row_even_after_a_relink(
    arm: Arm,
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    capture_id, profile_id = await _seed_capture(db_session, arm=arm, with_object=True)
    await link_profile(db_session, profile_id, unlinked=True)
    await db_session.commit()
    drain = _drain(session_factory)
    assert await drain.withdraw_refused_past_deadline(now=datetime.now(UTC)) == 1

    await link_profile(db_session, profile_id, second_user=True)
    await db_session.commit()
    before = await _snapshot(db_session, capture_id)

    assert await drain._claim_batch() == []
    assert await _snapshot(db_session, capture_id) == before
    assert before["status"] == CaptureStatus.WITHDRAWN


# --- In the cycle: before the deadline sweep -------------------------------------------------


async def _deadline_breach_capture_ids(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[str]:
    async with session_factory() as session:
        alerts = (
            (await session.execute(select(Alert).where(Alert.kind == AlertKind.DEADLINE_BREACH)))
            .scalars()
            .all()
        )
    ids: list[str] = []
    for alert in alerts:
        assert alert.detail is not None
        ids.extend(alert.detail["capture_ids"])
    return ids


async def test_a_cycle_withdraws_a_refused_row_and_still_raises_for_an_owned_one(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The refused row is `withdrawn` and no `deadline_breach` names it; an owned `pending` row past
    its deadline (its next attempt not yet due, so the drain leaves it alone) still raises one in
    the same cycle. This fails if the write runs after the sweep: the sweep would then name both."""
    from aoe2stats_ingester.run import run_once

    refused_id, refused_profile = await _seed_capture(db_session, index=0)
    await link_profile(db_session, refused_profile, unlinked=True)
    owned_id, owned_profile = await _seed_capture(
        db_session, index=1, next_attempt_in=timedelta(days=2)
    )
    await link_profile(db_session, owned_profile)
    await db_session.commit()

    report = await run_once(
        30, trigger="test", stages=(_drain(session_factory),), session_factory=session_factory
    )

    refused = await _snapshot(db_session, refused_id)
    owned = await _snapshot(db_session, owned_id)
    assert refused["status"] == CaptureStatus.WITHDRAWN
    assert refused["last_error"] == WITHDRAWN_REASON
    assert owned["status"] == CaptureStatus.PENDING
    assert await _deadline_breach_capture_ids(session_factory) == [str(owned_id)]
    assert report.stages_completed == ("drain",)


async def test_a_cycle_whose_budget_ended_before_the_drain_started_still_withdraws(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The write is not part of the drain's own `__call__`: a cycle that never started the drain
    still asks it, so the sweep does not name the refused row."""
    from aoe2stats_ingester.run import run_once

    refused_id, refused_profile = await _seed_capture(db_session)
    await link_profile(db_session, refused_profile, unlinked=True)
    await db_session.commit()

    report = await run_once(
        0, trigger="test", stages=(_drain(session_factory),), session_factory=session_factory
    )

    assert report.stages_completed == ()
    assert (await _snapshot(db_session, refused_id))["status"] == CaptureStatus.WITHDRAWN
    assert await _deadline_breach_capture_ids(session_factory) == []


async def test_a_cycle_with_no_drain_stage_withdraws_nothing(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from aoe2stats_ingester.run import run_once

    refused_id, refused_profile = await _seed_capture(db_session)
    await link_profile(db_session, refused_profile, unlinked=True)
    await db_session.commit()

    await run_once(30, trigger="test", stages=(), session_factory=session_factory)

    assert (await _snapshot(db_session, refused_id))["status"] == CaptureStatus.PENDING
    assert await _deadline_breach_capture_ids(session_factory) == [str(refused_id)]
