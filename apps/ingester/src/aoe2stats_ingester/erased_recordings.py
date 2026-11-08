"""T459n, T459s, T459t: the sweep that removes an erased user's recording a dying writer left
behind (FR-037).

Two writers can leave `replays/{game_id}/{profile_id}.zip` in the bucket with no row naming it,
after the user's erasure has committed: the capture drain, killed or failed between its
`put_if_absent` and its cleanup (`CaptureDrain._process_one`, T459j), and the erasure itself when
its post-commit delete fails or is killed (`routers/privacy.py`, pass 3, T459q). Nothing else
revisits such an object, so this sweep does, once per drain call.

**Mechanism: a record the erasure writes in its own transaction.** `erase_account` inserts into
`erased_recording_keys` (`ErasedRecordingKey`) every pair key it deletes or leaves for pass 3, the
keys of rows naming an object included, so a stale drain's late write of a key the named pass
already deleted is covered. The records commit with the erasure and roll back with it. The sweep
reads the table and lists no bucket.

**Per key, one transaction.** The sweep reads a batch of keys without a lock, then handles each key
in its own transaction: it selects the key's record `FOR UPDATE` (skipping the key if the record is
gone), checks that the key parses as `replays/{game_id}/{profile_id}.zip`, that no `replay_captures`
row exists for the pair (`FOR SHARE`, which waits for an erasure holding the row) and that no live
link (`profile_links.unlinked_at IS NULL`) names the profile, deletes the object when all hold,
then marks or drops the record and commits. A lock timeout on either read skips the key and leaves
its record unchanged. Any other failure of a read or of the object delete marks the key examined
(`swept_at`, record kept) in a transaction of its own and the sweep goes on to the next key, so one
failing key cannot stop the keys behind it; if that marking itself fails, the sweep stops. The
record lock is the only lock held while the object is deleted: no row is locked when the object is
deleted, since a row's existence is what stops the delete.

**Exclusion with a manual upload.** `upload_replay` (`routers/replays.py`) deletes its key's record
in the request's transaction before its `put_if_absent` and commits that delete with the capture
row that names the object. The delete waits for a sweep holding the record, so an object the sweep
deletes is deleted before the upload writes; while the delete is uncommitted the sweep waits for it
and skips the key on its lock timeout. A refusal (`replay_held`) or a failure after the delete rolls
the delete back, so the record stays and the sweep can still reach an object the request did not
adopt. The store's `delete` succeeds on a key that holds nothing.

**Aging and order.** A record is dropped when the database clock says it is older than the capture
budget (`capture_budget_days`), checked against `now()` in SQL; younger records stay, so a stale
drain's late write is still caught by a later run. A record is kept at least that long, and until
the sweep next examines it: it is dropped only when an examination finds it aged. A record the
sweep examined and kept gets `swept_at`, and batches are ordered `swept_at NULLS FIRST,
recorded_at, key`, so records kept past a sweep are visited after the unexamined ones.

**Bounds.** At most `MAX_RECORDS_EXAMINED` records are read and `MAX_KEYS_SWEPT` object deletes
issued per call; the return value counts those deletes, not objects that existed. The sweep takes
the drain's `Budget`, runs at the start of `CaptureDrain.__call__`, does nothing when the budget is
already expired, and checks it before each key. One transaction and one delete in progress are not
interrupted, and the drain is the third stage of a run, so the budget may be spent when it starts.

**Not covered.** An erased user's own manual upload already in flight when the erasure ran: if its
record delete (`upload_replay`) runs after the erasure committed and its `put_if_absent` follows,
no record names the key and the object stays. The erasure's own records exist only for the keys it
saw. A key whose delete fails on every run keeps its record past the capture budget, because the
record is dropped only after an examination that did not fail.

Every failure is contained: the sweep never raises into the drain, and its log line carries a count
and the exception's type name, never a key and never `exc_info`, because the object store's
exceptions carry the request URL, which holds the key.
"""

from __future__ import annotations

import logging
import re
from typing import Protocol, runtime_checkable

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_ingester.budget import Budget
from aoe2stats_storage.models import ErasedRecordingKey, ProfileLink, ReplayCapture

logger = logging.getLogger(__name__)

#: The most object deletes one sweep issues; the rest wait for the next cycle.
MAX_KEYS_SWEPT = 50

#: The most records one sweep reads.
MAX_RECORDS_EXAMINED = 200

#: How long a read in the sweep waits for a lock holder before the key is skipped.
DEFAULT_LOCK_TIMEOUT_MS = 2_000

_LOCK_NOT_AVAILABLE = "55P03"

_REPLAY_KEY = re.compile(r"^replays/(\d+)/(\d+)\.zip$")


@runtime_checkable
class ErasedRecordingStore(Protocol):
    """The one `ObjectStore` method the sweep calls. A store without it is not swept."""

    async def delete(self, key: str) -> None: ...


def _is_lock_timeout(exc: DBAPIError) -> bool:
    return getattr(exc.orig, "sqlstate", None) == _LOCK_NOT_AVAILABLE


async def _fail_one(
    session_factory: async_sessionmaker[AsyncSession], key: str, exc: Exception
) -> bool:
    """T459u: a key whose read or delete failed for any reason but a lock timeout is marked
    examined (`swept_at`, record kept) in a transaction of its own, so it moves behind the
    unexamined keys and cannot stop every later key on each run. The log line carries the type
    name only, never the key and never `exc_info`."""
    logger.warning(
        "erased-recording sweep: a key failed and was marked examined: %s", type(exc).__name__
    )
    async with session_factory() as session:
        await session.execute(
            update(ErasedRecordingKey)
            .where(ErasedRecordingKey.key == key)
            .values(swept_at=func.clock_timestamp())
        )
        await session.commit()
    return False


async def _sweep_one(
    store: ErasedRecordingStore,
    session_factory: async_sessionmaker[AsyncSession],
    key: str,
    *,
    record_max_age_days: int,
    lock_timeout_ms: int,
) -> bool | None:
    """One key, one transaction. Returns True if an object delete was issued, False if the key was
    handled without one (a failure included, T459u), None if it was skipped (record gone, or a lock
    timeout)."""
    async with session_factory() as session:
        try:
            await session.execute(
                select(func.set_config("lock_timeout", f"{int(lock_timeout_ms)}ms", True))
            )
            aged = await session.scalar(
                select(
                    ErasedRecordingKey.recorded_at
                    < func.now() - func.make_interval(0, 0, 0, record_max_age_days)
                )
                .where(ErasedRecordingKey.key == key)
                .with_for_update()
            )
            if aged is None:
                await session.rollback()
                return None
            issued = False
            match = _REPLAY_KEY.match(key)
            if match is not None:
                game_id, profile_id = int(match.group(1)), int(match.group(2))
                has_row = await session.scalar(
                    select(ReplayCapture.id)
                    .where(ReplayCapture.game_id == game_id, ReplayCapture.profile_id == profile_id)
                    .with_for_update(read=True)
                )
                linked = await session.scalar(
                    select(ProfileLink.id).where(
                        ProfileLink.profile_id == profile_id, ProfileLink.unlinked_at.is_(None)
                    )
                )
                if has_row is None and linked is None:
                    await store.delete(key)
                    issued = True
        except DBAPIError as exc:
            await session.rollback()
            if _is_lock_timeout(exc):
                return None
            return await _fail_one(session_factory, key, exc)
        except Exception as exc:
            await session.rollback()
            return await _fail_one(session_factory, key, exc)
        if aged:
            await session.execute(delete(ErasedRecordingKey).where(ErasedRecordingKey.key == key))
        else:
            await session.execute(
                update(ErasedRecordingKey)
                .where(ErasedRecordingKey.key == key)
                .values(swept_at=func.clock_timestamp())
            )
        await session.commit()
        return issued


async def sweep_erased_recordings(
    store: ErasedRecordingStore,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    budget: Budget,
    record_max_age_days: int,
    lock_timeout_ms: int = DEFAULT_LOCK_TIMEOUT_MS,
) -> int:
    """Sweep a batch of recorded keys (module docstring) and return how many object deletes were
    issued. Never raises."""
    swept = 0
    if budget.expired:
        return 0
    try:
        async with session_factory() as session:
            keys = list(
                await session.scalars(
                    select(ErasedRecordingKey.key)
                    .order_by(
                        ErasedRecordingKey.swept_at.asc().nulls_first(),
                        ErasedRecordingKey.recorded_at,
                        ErasedRecordingKey.key,
                    )
                    .limit(MAX_RECORDS_EXAMINED)
                )
            )
            await session.rollback()
        for key in keys:
            if swept >= MAX_KEYS_SWEPT or budget.expired:
                break
            outcome = await _sweep_one(
                store,
                session_factory,
                key,
                record_max_age_days=record_max_age_days,
                lock_timeout_ms=lock_timeout_ms,
            )
            if outcome:
                swept += 1
    except Exception as exc:
        logger.warning(
            "erased-recording sweep stopped after %d key(s): %s", swept, type(exc).__name__
        )
    if swept:
        logger.info("erased-recording sweep deleted the objects of %d key(s)", swept)
    return swept
