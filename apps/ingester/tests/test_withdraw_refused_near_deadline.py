"""T721, T721a - a capture the claim refuses gets the terminal status `withdrawn` once its capture
deadline is within the withdrawal lead, or past.

Level: `CaptureDrain.withdraw_refused_near_deadline` called directly (the statement), then
`run_once` over a drain stage (its place in the cycle, and what it buys across the window between
two cycles), then `_claim_batch` (it never takes a `withdrawn` row). The three readers that filter
on the deadline and the status have their own tests beside the readers: `test_deadline_alert.py`,
`scripts/checks/tests/test_capture_audit.py` and `apps/analyzer/tests/test_admission.py`.

The lead in these tests is `_LEAD_HOURS`, a fixture value; the number a deployment runs with is
`INGEST_WITHDRAW_LEAD_HOURS` in `.env.example`. The statement withdraws a row whose deadline is
less than the lead away or past, that is `pending` (whatever its `next_attempt_at`) or a stale
`downloading` row, and whose profile has no active link whose user has not objected:

- the user unlinked; the user objected and the link is active; no link was ever written; the next
  attempt time has not come (a `pending` row); the stale `downloading` row holds a committed object;
  the deadline is one hour inside the lead, or past;
- in each, `status` and `last_error` are the only columns that change (`_snapshot` compares the
  rest), so an object key, a checksum, `attempts` and `claimed_at` are as they were.

Left as it is, each asserted unchanged, and each excluded by exactly one clause: the same rows one
hour outside the lead (the deadline clause); a `downloading` row that is not stale (the staleness
clause); a row whose profile has an active link whose user has not objected, past its deadline or
inside the lead, and a profile relinked by a second user who has not objected (the ownership
clause); every other status, with an old claim time so a staleness clause that lost its status
check would take them (the status clause). A lead of zero selects as T721 did: a row one hour
before its deadline is left.

Across the window: after one cycle over a refused row whose deadline is inside the lead, at an
instant after that deadline the admission gate admits and the audit's assertion finds nothing. The
residual is asserted as what the code does: a row owned at the cycle that loses its owner inside
the lead and before its deadline is `pending` past that deadline, counted by the admission gate and
the audit, until the next cycle withdraws it before the deadline sweep reads it.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import pytest
from sqlalchemy import inspect, select, update
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
    ProfileLink,
    ReplayCapture,
)

Arm = Literal["pending", "stale_downloading", "fresh_downloading"]

#: A fixture value for `withdraw_lead_hours`; see the module docstring.
_LEAD_HOURS = 48
_LEAD = timedelta(hours=_LEAD_HOURS)
_BASE_GAME_ID = 940_000_000
_BASE_PROFILE_ID = 240_000_000
_OBJECT_PREFIX = "replays"
_ZIP_SHA256 = "b" * 64


class _NeverCalledProvider:
    async def fetch_replay(self, game_id: int, profile_id: int) -> object:  # pragma: no cover
        raise AssertionError("these tests withdraw or claim; they never fetch")


def _drain(
    session_factory: async_sessionmaker[AsyncSession], lead_hours: int = _LEAD_HOURS
) -> CaptureDrain:
    return CaptureDrain(
        session_factory=session_factory,
        replay_provider=_NeverCalledProvider(),  # type: ignore[arg-type]
        withdraw_lead_hours=lead_hours,
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
    "deadline_in", [timedelta(hours=-1), _LEAD - timedelta(hours=1)], ids=["past", "inside_lead"]
)
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
async def test_a_refused_row_past_or_inside_the_lead_is_withdrawn_and_nothing_else_changes(
    deadline_in: timedelta,
    arm: Arm,
    owner: Owner,
    next_attempt_in: timedelta,
    with_object: bool,
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    capture_id, profile_id = await _seed_capture(
        db_session,
        arm=arm,
        deadline_in=deadline_in,
        next_attempt_in=next_attempt_in,
        with_object=with_object,
    )
    await _give_owner(db_session, profile_id, owner)
    before = await _snapshot(db_session, capture_id)

    changed = await _drain(session_factory).withdraw_refused_near_deadline(now=datetime.now(UTC))

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
    assert await drain.withdraw_refused_near_deadline(now=datetime.now(UTC)) == 1
    first = await _snapshot(db_session, capture_id)

    assert await drain.withdraw_refused_near_deadline(now=datetime.now(UTC)) == 0
    assert await _snapshot(db_session, capture_id) == first


# --- Left as it is --------------------------------------------------------------------------


@pytest.mark.parametrize("arm", ["pending", "stale_downloading"])
@pytest.mark.parametrize("owner", ["unlinked", "objector", "never_linked"])
async def test_the_same_row_one_hour_outside_the_lead_is_left_as_it_is(
    arm: Arm,
    owner: Owner,
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    capture_id, profile_id = await _seed_capture(
        db_session, arm=arm, deadline_in=_LEAD + timedelta(hours=1), with_object=arm != "pending"
    )
    await _give_owner(db_session, profile_id, owner)
    before = await _snapshot(db_session, capture_id)

    changed = await _drain(session_factory).withdraw_refused_near_deadline(now=datetime.now(UTC))

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

    changed = await _drain(session_factory).withdraw_refused_near_deadline(now=datetime.now(UTC))

    assert changed == 0
    assert await _snapshot(db_session, capture_id) == before


@pytest.mark.parametrize(
    "deadline_in", [timedelta(hours=-1), _LEAD - timedelta(hours=1)], ids=["past", "inside_lead"]
)
@pytest.mark.parametrize("arm", ["pending", "stale_downloading"])
async def test_a_row_with_an_active_link_whose_user_has_not_objected_is_left_as_it_is(
    arm: Arm,
    deadline_in: timedelta,
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Past its deadline it stays for the deadline alert; inside the lead it is still claimable."""
    capture_id, profile_id = await _seed_capture(db_session, arm=arm, deadline_in=deadline_in)
    await link_profile(db_session, profile_id)
    before = await _snapshot(db_session, capture_id)

    changed = await _drain(session_factory).withdraw_refused_near_deadline(now=datetime.now(UTC))

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

    changed = await _drain(session_factory).withdraw_refused_near_deadline(now=datetime.now(UTC))

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
    # `stale_downloading` gives the row a claim time older than the stale bound, so a staleness
    # clause that lost its status check would take it; the status override keeps the row's status.
    capture_id, _ = await _seed_capture(
        db_session,
        arm="stale_downloading",
        status=status,
        with_object=status in (CaptureStatus.STORED,),
    )
    before = await _snapshot(db_session, capture_id)

    changed = await _drain(session_factory).withdraw_refused_near_deadline(now=datetime.now(UTC))

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
    assert await drain.withdraw_refused_near_deadline(now=datetime.now(UTC)) == 1

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


# --- The lead --------------------------------------------------------------------------------


async def test_a_lead_of_zero_selects_as_t721_did(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """With no lead, a refused row one hour before its deadline is left and one an hour past it is
    withdrawn."""
    before_id, before_profile = await _seed_capture(
        db_session, index=0, deadline_in=timedelta(hours=1)
    )
    past_id, past_profile = await _seed_capture(
        db_session, index=1, deadline_in=timedelta(hours=-1)
    )
    await _give_owner(db_session, before_profile, "unlinked")
    await _give_owner(db_session, past_profile, "unlinked")
    left = await _snapshot(db_session, before_id)

    changed = await _drain(session_factory, 0).withdraw_refused_near_deadline(now=datetime.now(UTC))

    assert changed == 1
    assert await _snapshot(db_session, before_id) == left
    assert (await _snapshot(db_session, past_id))["status"] == CaptureStatus.WITHDRAWN


def test_a_negative_lead_is_refused_at_construction() -> None:
    with pytest.raises(ValueError, match="withdraw_lead_hours"):
        CaptureDrain(
            session_factory=None,  # type: ignore[arg-type]
            replay_provider=_NeverCalledProvider(),  # type: ignore[arg-type]
            withdraw_lead_hours=-1,
        )


# --- Across the window between two cycles ------------------------------------------------------


async def _refused_row_inside_the_lead_then_one_cycle(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    lead_hours: int,
) -> uuid.UUID:
    """A refused `pending` row whose deadline is twelve hours away, then one `run_once` cycle with a
    drain of the given lead. Returns the row's id."""
    from aoe2stats_ingester.run import run_once

    capture_id, profile_id = await _seed_capture(db_session, deadline_in=timedelta(hours=12))
    await link_profile(db_session, profile_id, unlinked=True)
    await db_session.commit()

    await run_once(
        30,
        trigger="test",
        stages=(_drain(session_factory, lead_hours),),
        session_factory=session_factory,
    )
    return capture_id


async def test_after_one_cycle_the_readers_do_not_count_a_row_whose_deadline_then_passes(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The property the lead buys. Production runs one cycle a day: the cycle sees the row twelve
    hours before its deadline, and at an instant after that deadline, with no cycle in between, the
    admission gate admits and the audit's assertion finds nothing. With a lead of zero the cycle
    leaves the row `pending` and both readers count it (`..._with_a_lead_of_zero_...` below)."""
    from scripts.checks.capture_audit import captures_pending_past_deadline

    from aoe2stats_analyzer.admission import deadline_gate_admits

    capture_id = await _refused_row_inside_the_lead_then_one_cycle(
        db_session, session_factory, lead_hours=_LEAD_HOURS
    )
    after_the_deadline = datetime.now(UTC) + timedelta(hours=24)

    db_session.expire_all()
    assert await deadline_gate_admits(db_session, now=after_the_deadline) is True
    assert await captures_pending_past_deadline(db_session, now=after_the_deadline) == []
    assert (await _snapshot(db_session, capture_id))["status"] == CaptureStatus.WITHDRAWN
    assert await _deadline_breach_capture_ids(session_factory) == []


async def test_after_one_cycle_with_a_lead_of_zero_the_readers_count_the_row_past_its_deadline(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The window T721 left, as the contrast of the test above."""
    from scripts.checks.capture_audit import captures_pending_past_deadline

    from aoe2stats_analyzer.admission import deadline_gate_admits

    capture_id = await _refused_row_inside_the_lead_then_one_cycle(
        db_session, session_factory, lead_hours=0
    )
    after_the_deadline = datetime.now(UTC) + timedelta(hours=24)

    db_session.expire_all()
    assert await deadline_gate_admits(db_session, now=after_the_deadline) is False
    overdue = await captures_pending_past_deadline(db_session, now=after_the_deadline)
    assert [capture.id for capture in overdue] == [capture_id]


async def test_a_row_that_loses_its_owner_after_the_cycle_is_counted_until_the_next_cycle(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The residual, as what the code does and not as a decision. A row owned at the cycle, with
    its deadline inside the lead, is left; its user then unlinks, before the deadline. At an
    instant after the deadline and before the next cycle it is still `pending`, and the admission
    gate and the audit count it. The deadline sweep does not: the next cycle runs at an instant
    after the deadline, and it withdraws the row before the sweep reads it, so no `deadline_breach`
    names it. This fails if the write runs after the sweep."""
    from scripts.checks.capture_audit import captures_pending_past_deadline

    import aoe2stats_ingester.run as run_module
    from aoe2stats_analyzer.admission import deadline_gate_admits
    from aoe2stats_ingester.run import run_once

    # The next attempt is not due, so the drain leaves the owned row alone rather than fetching it.
    capture_id, profile_id = await _seed_capture(
        db_session, deadline_in=timedelta(hours=12), next_attempt_in=timedelta(days=2)
    )
    await link_profile(db_session, profile_id)
    await db_session.commit()
    drain = _drain(session_factory)
    await run_once(30, trigger="test", stages=(drain,), session_factory=session_factory)
    assert (await _snapshot(db_session, capture_id))["status"] == CaptureStatus.PENDING

    await db_session.execute(
        update(ProfileLink)
        .where(ProfileLink.profile_id == profile_id)
        .values(unlinked_at=datetime.now(UTC))
    )
    await db_session.commit()
    after_the_deadline = datetime.now(UTC) + timedelta(hours=24)

    db_session.expire_all()
    assert (await _snapshot(db_session, capture_id))["status"] == CaptureStatus.PENDING
    assert await deadline_gate_admits(db_session, now=after_the_deadline) is False
    overdue = await captures_pending_past_deadline(db_session, now=after_the_deadline)
    assert [capture.id for capture in overdue] == [capture_id]

    # The next cycle, at an instant after the row's deadline: `run_once` reads it for the instant
    # the write and the sweep share (`finished_at`).
    monkeypatch.setattr(run_module, "_now", lambda: after_the_deadline)
    await run_once(30, trigger="test", stages=(drain,), session_factory=session_factory)

    assert (await _snapshot(db_session, capture_id))["status"] == CaptureStatus.WITHDRAWN
    assert await _deadline_breach_capture_ids(session_factory) == []
