"""T713 — the claim takes a capture only when its profile has an active link whose user has not
objected.

Level: the claim query in `CaptureDrain._claim_batch`, both arms of its eligibility — an ordinary
`pending` row whose backoff has elapsed, and a stale `downloading` row taken again. Before T713 the
claim excluded a row only when it found an active link whose user had objected
(`_objecting_owner_exists`), so a capture queued while a link stood was still fetched after the user
unlinked the profile. 001's spec says automatic ingestion stops for a profile its user unlinks
(US1, acceptance scenario 6); the claim now shares `_owner_is_archiving` with the re-validation.

The cases, each run against both arms unless it says otherwise:

- the user unlinked after the capture was queued: not claimed;
- the user objected and then unlinked: not claimed;
- no link row was ever written for the profile: not claimed (the predicate has no exception for the
  absence of a link);
- the user objected and the link is still active: not claimed (unchanged);
- a profile relinked by a second user who has objected: not claimed;
- a stale `downloading` row holding a committed object (this arm only): refused with its object key
  and checksum unchanged, then claimed once its profile has an active link whose user has not
  objected;
- contrast: a profile relinked by a second user who has not objected is claimed, and so is a
  profile with an active link whose user has not objected.

`_claim_batch` is called directly; the tests assert at the claim, not at what is done with a row
once it is claimed.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.links import link_profile

from aoe2stats_ingester.capture import CaptureDrain
from aoe2stats_storage.models import (
    AoeProfile,
    CaptureSource,
    CaptureStatus,
    Match,
    ReplayCapture,
)

Arm = Literal["pending", "stale_downloading"]
_ARMS: tuple[Arm, ...] = ("pending", "stale_downloading")

_PROFILE_ID = 230_000_001
_GAME_ID = 930_000_001


class _NeverCalledProvider:
    async def fetch_replay(self, game_id: int, profile_id: int) -> object:  # pragma: no cover
        raise AssertionError("these tests claim; they never fetch")


_OBJECT_KEY = f"replays/{_GAME_ID}/{_PROFILE_ID}.zip"
_ZIP_SHA256 = "a" * 64


async def _seed_capture(
    db_session: AsyncSession, arm: Arm, *, with_object: bool = False
) -> uuid.UUID:
    """One capture for `_PROFILE_ID` in the given arm, flushed with no link of any kind.
    `with_object` gives it the committed object a killed run leaves behind (`object_key`,
    `zip_bytes`, `zip_sha256`)."""
    now = datetime.now(UTC)
    completed_at = now - timedelta(hours=1)
    capture_id = uuid.uuid4()
    db_session.add(AoeProfile(profile_id=_PROFILE_ID, alias="claim-link", country="FR"))
    db_session.add(
        Match(
            game_id=_GAME_ID,
            leaderboard_id=3,
            completed_at=completed_at,
            source="relic",
            raw_payload={},
        )
    )
    await db_session.flush()
    db_session.add(
        ReplayCapture(
            id=capture_id,
            game_id=_GAME_ID,
            profile_id=_PROFILE_ID,
            status=CaptureStatus.PENDING if arm == "pending" else CaptureStatus.DOWNLOADING,
            capture_deadline_at=completed_at + timedelta(days=21),
            attempts=0 if arm == "pending" else 1,
            next_attempt_at=now - timedelta(minutes=1),
            claimed_at=None if arm == "pending" else now - timedelta(hours=1),
            first_seen_at=completed_at,
            source=CaptureSource.AUTOMATIC,
            object_key=_OBJECT_KEY if with_object else None,
            zip_bytes=1024 if with_object else None,
            zip_sha256=_ZIP_SHA256 if with_object else None,
        )
    )
    await db_session.flush()
    return capture_id


def _drain(session_factory: async_sessionmaker[AsyncSession]) -> CaptureDrain:
    return CaptureDrain(
        session_factory=session_factory,
        replay_provider=_NeverCalledProvider(),  # type: ignore[arg-type]
    )


async def _claimed(
    db_session: AsyncSession, session_factory: async_sessionmaker[AsyncSession]
) -> list[uuid.UUID]:
    await db_session.commit()
    return await _drain(session_factory)._claim_batch()


async def _is_refused(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    capture_id: uuid.UUID,
    arm: Arm,
) -> None:
    assert await _claimed(db_session, session_factory) == []
    db_session.expire_all()
    row = await db_session.get(ReplayCapture, capture_id)
    assert row is not None
    assert row.status == (CaptureStatus.PENDING if arm == "pending" else CaptureStatus.DOWNLOADING)
    assert row.attempts == (0 if arm == "pending" else 1)


async def _is_taken(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    capture_id: uuid.UUID,
    arm: Arm,
) -> None:
    assert await _claimed(db_session, session_factory) == [capture_id]
    db_session.expire_all()
    row = await db_session.get(ReplayCapture, capture_id)
    assert row is not None
    assert row.status == CaptureStatus.DOWNLOADING
    assert row.attempts == (1 if arm == "pending" else 2)


@pytest.mark.parametrize("arm", _ARMS)
async def test_a_capture_whose_user_unlinked_after_it_was_queued_is_not_claimed(
    arm: Arm,
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    capture_id = await _seed_capture(db_session, arm)
    await link_profile(db_session, _PROFILE_ID, unlinked=True)

    await _is_refused(db_session, session_factory, capture_id, arm)


@pytest.mark.parametrize("arm", _ARMS)
async def test_a_capture_whose_objecting_user_unlinked_is_not_claimed(
    arm: Arm,
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    capture_id = await _seed_capture(db_session, arm)
    await link_profile(db_session, _PROFILE_ID, objected=True, unlinked=True)

    await _is_refused(db_session, session_factory, capture_id, arm)


@pytest.mark.parametrize("arm", _ARMS)
async def test_a_capture_whose_profile_was_never_linked_is_not_claimed(
    arm: Arm,
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    capture_id = await _seed_capture(db_session, arm)

    await _is_refused(db_session, session_factory, capture_id, arm)


@pytest.mark.parametrize("arm", _ARMS)
async def test_a_capture_whose_linked_user_objected_is_still_not_claimed(
    arm: Arm,
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    capture_id = await _seed_capture(db_session, arm)
    await link_profile(db_session, _PROFILE_ID, objected=True)

    await _is_refused(db_session, session_factory, capture_id, arm)


@pytest.mark.parametrize("arm", _ARMS)
async def test_a_capture_with_an_active_link_whose_user_has_not_objected_is_claimed(
    arm: Arm,
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    capture_id = await _seed_capture(db_session, arm)
    await link_profile(db_session, _PROFILE_ID)

    await _is_taken(db_session, session_factory, capture_id, arm)


@pytest.mark.parametrize("arm", _ARMS)
@pytest.mark.parametrize("first_user_objected", [False, True])
async def test_a_profile_relinked_by_a_second_user_who_has_not_objected_is_claimed(
    arm: Arm,
    first_user_objected: bool,
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    capture_id = await _seed_capture(db_session, arm)
    await link_profile(db_session, _PROFILE_ID, objected=first_user_objected, unlinked=True)
    await link_profile(db_session, _PROFILE_ID, second_user=True)

    await _is_taken(db_session, session_factory, capture_id, arm)


@pytest.mark.parametrize("arm", _ARMS)
@pytest.mark.parametrize("first_user_unlinked_objected", [False, True])
async def test_a_profile_relinked_by_a_second_user_who_has_objected_is_not_claimed(
    arm: Arm,
    first_user_unlinked_objected: bool,
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    capture_id = await _seed_capture(db_session, arm)
    await link_profile(
        db_session, _PROFILE_ID, objected=first_user_unlinked_objected, unlinked=True
    )
    await link_profile(db_session, _PROFILE_ID, objected=True, second_user=True)

    await _is_refused(db_session, session_factory, capture_id, arm)


async def test_a_stale_downloading_row_holding_an_object_is_refused_then_claimed_on_a_relink(
    db_session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A refused row with a committed object keeps its status, object key and checksum; the same
    row is claimed once its profile has an active link whose user has not objected. Asserted at the
    claim only, not at what the drain then does with it."""
    capture_id = await _seed_capture(db_session, "stale_downloading", with_object=True)
    await link_profile(db_session, _PROFILE_ID, unlinked=True)

    await _is_refused(db_session, session_factory, capture_id, "stale_downloading")
    row = await db_session.get(ReplayCapture, capture_id)
    assert row is not None
    assert (row.object_key, row.zip_sha256) == (_OBJECT_KEY, _ZIP_SHA256)

    await link_profile(db_session, _PROFILE_ID, second_user=True)

    await _is_taken(db_session, session_factory, capture_id, "stale_downloading")
    row = await db_session.get(ReplayCapture, capture_id)
    assert row is not None
    assert (row.object_key, row.zip_sha256) == (_OBJECT_KEY, _ZIP_SHA256)
