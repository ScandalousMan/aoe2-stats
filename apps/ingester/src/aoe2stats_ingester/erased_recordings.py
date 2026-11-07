"""T459n, T459s: the sweep that removes an erased user's recording a dying writer left behind
(FR-037).

Two writers can leave `replays/{game_id}/{profile_id}.zip` in the bucket with no row naming it,
after the user's erasure has committed: the capture drain, killed or failed between its
`put_if_absent` and its cleanup (`CaptureDrain._process_one`, T459j), and the erasure itself when
its post-commit delete fails or is killed (`routers/privacy.py`, pass 3, T459q). Nothing else
revisits such an object, so this sweep does, once per drain call.

**Mechanism: a record the erasure writes in its own transaction.** `erase_account` inserts into
`erased_recording_keys` (`ErasedRecordingKey`) the exact keys it leaves for after its commit: the
post-commit pass's keys, which are the deterministic key of every captured row naming no object,
`downloading` included. The records commit with the erasure and roll back with it, so a rolled-back
erasure leaves none. Nothing else writes the table. The sweep reads it, oldest first, and lists no
bucket.

For each record examined, the object is deleted only when all of these hold:

1. the key parses as `replays/{game_id}/{profile_id}.zip`;
2. no `replay_captures` row exists for `(game_id, profile_id)`, read by `CaptureDrain._pair_has_row`
   (`FOR SHARE`, which waits for an erasure holding the row) under a bounded `lock_timeout`; on a
   timeout the key is skipped and its record kept;
3. no live link (`profile_links.unlinked_at IS NULL`) names that profile. An upload needs a
   committed link, so if its `put_if_absent` preceded this check, this check sees the link and the
   object is kept; one that follows it writes a new object. A profile erased and linked again
   keeps its recorded key unacted on.

The store's `delete` succeeds on a key that holds nothing, so an object already gone is fine.

**Aging.** A record is dropped once it is older than the drain's stale-claim bound
(`max_claim_age_seconds`, `DEFAULT_MAX_CLAIM_AGE_SECONDS` in `capture.py`), and only after it has
been examined in a sweep, whether or not it led to a delete. Younger records stay after their
delete, so a stale drain's late write is still caught by a later run. A record skipped on a lock
timeout, or whose delete failed, stays.

**Bounds.** At most `MAX_RECORDS_EXAMINED` records are read and `MAX_DELETES_PER_SWEEP` keys deleted
per call. The sweep takes the drain's `Budget`, runs at the start of `CaptureDrain.__call__`, does
nothing when the budget is already expired, and checks it before each record. One database read and
one delete in progress are not interrupted, so the budget is honoured between calls, not within
them, and the drain is the third stage of a run, so the budget may already be spent when it starts.

Every failure is contained: the sweep never raises into the drain, and its log line carries a count
and the exception's type name, never a key and never `exc_info`, because the object store's
exceptions carry the request URL, which holds the key.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Protocol, runtime_checkable

from sqlalchemy import delete, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_ingester.budget import Budget
from aoe2stats_storage.models import ErasedRecordingKey, ProfileLink

logger = logging.getLogger(__name__)

#: The most keys one sweep deletes; the rest wait for the next cycle.
MAX_DELETES_PER_SWEEP = 50

#: The most records one sweep reads.
MAX_RECORDS_EXAMINED = 200

#: How long the row-existence read waits for a lock holder before the key is skipped.
DEFAULT_PAIR_LOCK_TIMEOUT_MS = 2_000

_LOCK_NOT_AVAILABLE = "55P03"

_REPLAY_KEY = re.compile(r"^replays/(\d+)/(\d+)\.zip$")


@runtime_checkable
class ErasedRecordingStore(Protocol):
    """The one `ObjectStore` method the sweep calls. A store without it is not swept."""

    async def delete(self, key: str) -> None: ...


class PairHasRow(Protocol):
    async def __call__(
        self, game_id: int, profile_id: int, *, lock_timeout_ms: int | None = None
    ) -> bool: ...


def _is_lock_timeout(exc: DBAPIError) -> bool:
    return getattr(exc.orig, "sqlstate", None) == _LOCK_NOT_AVAILABLE


async def sweep_erased_recordings(
    store: ErasedRecordingStore,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    pair_has_row: PairHasRow,
    budget: Budget,
    max_record_age_seconds: float,
    now: datetime | None = None,
    lock_timeout_ms: int = DEFAULT_PAIR_LOCK_TIMEOUT_MS,
) -> int:
    """Delete the objects the records name that conditions 1-3 (module docstring) allow, drop the
    records that have aged out, and return how many objects were deleted. Never raises."""
    deleted = 0
    if budget.expired:
        return 0
    cutoff = (now or datetime.now(UTC)) - timedelta(seconds=max_record_age_seconds)
    aged: list[str] = []
    try:
        async with session_factory() as session:
            records = (
                await session.execute(
                    select(ErasedRecordingKey.key, ErasedRecordingKey.recorded_at)
                    .order_by(ErasedRecordingKey.recorded_at, ErasedRecordingKey.key)
                    .limit(MAX_RECORDS_EXAMINED)
                )
            ).all()
            profile_ids = {
                int(match.group(2))
                for key, _ in records
                if (match := _REPLAY_KEY.match(key)) is not None
            }
            linked = set(
                await session.scalars(
                    select(ProfileLink.profile_id).where(
                        ProfileLink.profile_id.in_(profile_ids), ProfileLink.unlinked_at.is_(None)
                    )
                )
            )
            await session.rollback()
        for key, recorded_at in records:
            if deleted >= MAX_DELETES_PER_SWEEP or budget.expired:
                break
            match = _REPLAY_KEY.match(key)
            if match is not None and int(match.group(2)) not in linked:
                try:
                    has_row = await pair_has_row(
                        int(match.group(1)), int(match.group(2)), lock_timeout_ms=lock_timeout_ms
                    )
                except DBAPIError as exc:
                    if not _is_lock_timeout(exc):
                        raise
                    continue
                if not has_row:
                    await store.delete(key)
                    deleted += 1
            if recorded_at < cutoff:
                aged.append(key)
    except Exception as exc:
        logger.warning(
            "erased-recording sweep stopped after %d deletion(s): %s", deleted, type(exc).__name__
        )
    if aged:
        try:
            async with session_factory() as session:
                await session.execute(
                    delete(ErasedRecordingKey).where(ErasedRecordingKey.key.in_(aged))
                )
                await session.commit()
        except Exception as exc:
            logger.warning("erased-recording sweep could not drop records: %s", type(exc).__name__)
    if deleted:
        logger.info("erased-recording sweep deleted %d object(s)", deleted)
    return deleted
