"""The fixed-window, database-backed rate limiter (T307). `apps/api/tests/test_rate_limits.py`
(T306) is this module's specification; every case there is read from `research.md`'s R10 and
`data-model.md`'s `rate_limit_counters` section, and this module implements to it rather than the
other way round.

Database-backed rather than in-memory, for the reason constitution XII exists to enforce: this
platform gives no shared process between two invocations of the same route (Vercel), so a counter
held in a module-level dict would work on a VPS and silently count nothing there — each invocation
would see its own empty dict and every request would look like the first one.
`test_the_counter_survives_a_process_with_no_shared_memory` is the assertion that would catch that
mistake, and it does so from a genuinely separate OS process sharing nothing with this one but the
database `database_url` — this module holds no cache in front of `session`, on purpose, so that
nothing here can pass that test for the wrong reason.

`rate_limit_counters` (`packages/storage/src/aoe2stats_storage/models.py`, T304) is keyed on
`(user_id, bucket, window_start)`. `window_start` is a fixed window aligned to the Unix epoch —
`_window_start` below floors `now` to the nearest multiple of `window_seconds` seconds since the
epoch — rather than a window that opens on a request's own first call, because an epoch-aligned
window needs no row read to know where it starts: two callers computing `_window_start` for the
same `now` and `window_seconds` always agree, with no coordination and no prior row.

The upsert is a single `INSERT ... ON CONFLICT DO UPDATE SET count = rate_limit_counters.count + 1
RETURNING count` — the increment is expressed against the table's own existing column, not a
value carried in from Python, so two concurrent callers targeting the same `(user_id, bucket,
window_start)` serialise on Postgres's own row lock for a conflicting insert rather than each
reading a stale `count` and each writing `n + 1`: the second caller's `UPDATE` is not evaluated
until the first one's transaction has released the row, and it increments whatever the first one
left behind rather than the value either of them read before either wrote.

Rows older than the just-computed `window_start`, for this exact `(user_id, bucket)`, are deleted
in the same call — the opportunistic pruning FR-044 requires in place of a job, mirroring
`data-model.md`'s own phrase for the sibling case (`profile_search_cache`, T315). Scoping the
delete to `(user_id, bucket)` rather than sweeping the whole table keeps it on the table's own
primary-key index (`user_id`, `bucket`, `window_start`, in that order) instead of a full scan, and
it needs no knowledge of any other bucket's window length: a row is only ever compared against the
window length of the bucket it itself belongs to, which is the only "longest window" a single
`(user_id, bucket)` pair has.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_storage.models import RateLimitCounter


@dataclass(frozen=True)
class RateLimitOutcome:
    """`allowed`: whether this call's own increment stayed at or under `limit`. `remaining`: how
    many more calls the caller may make in this same window, never negative. `retry_after`: seconds
    until the current window closes, only set when `allowed` is `False` — `None` otherwise, since
    "retry after" means nothing for a call that was itself allowed.
    """

    allowed: bool
    remaining: int
    retry_after: int | None


def _window_start(now: datetime, window_seconds: int) -> datetime:
    """`now` floored to the nearest multiple of `window_seconds` seconds since the Unix epoch —
    the fixed-window boundary two independent callers agree on without reading a row first."""
    epoch_seconds = int(now.timestamp())
    aligned_epoch_seconds = epoch_seconds - (epoch_seconds % window_seconds)
    return datetime.fromtimestamp(aligned_epoch_seconds, tz=UTC)


async def check_and_increment(
    session: AsyncSession,
    *,
    user_id: UUID,
    bucket: str,
    limit: int,
    window_seconds: int,
    now: datetime | None = None,
) -> RateLimitOutcome:
    """Increment `bucket`'s counter for `user_id` in the fixed window `now` falls into, and report
    whether that increment stayed within `limit`. `now` is an explicit parameter rather than a call
    to `datetime.now()` inside this function, so a caller's window boundary is deterministic under
    test instead of racing the clock; production callers pass nothing and get the real clock.

    Does not commit — the caller's own unit of work decides when the increment (and the pruning
    below) becomes durable, exactly as every other write in this codebase leaves `session.commit()`
    to its caller (`routers/auth.py`, `ingest_stages.py`).
    """
    moment = now if now is not None else datetime.now(UTC)
    window_start = _window_start(moment, window_seconds)

    upsert = (
        pg_insert(RateLimitCounter)
        .values(user_id=user_id, bucket=bucket, window_start=window_start, count=1)
        .on_conflict_do_update(
            index_elements=[
                RateLimitCounter.user_id,
                RateLimitCounter.bucket,
                RateLimitCounter.window_start,
            ],
            set_={"count": RateLimitCounter.count + 1},
        )
        .returning(RateLimitCounter.count)
    )
    count = (await session.execute(upsert)).scalar_one()

    # FR-044: no job sweeps this table. A row for this exact `(user_id, bucket)` older than the
    # window this call just wrote is disposable — the write already touching this pair's own
    # primary-key index is what makes deleting it here free of an extra scan.
    await session.execute(
        delete(RateLimitCounter).where(
            RateLimitCounter.user_id == user_id,
            RateLimitCounter.bucket == bucket,
            RateLimitCounter.window_start < window_start,
        )
    )

    allowed = count <= limit
    remaining = max(limit - count, 0)
    retry_after: int | None = None
    if not allowed:
        window_end = window_start + timedelta(seconds=window_seconds)
        retry_after = int((window_end - moment).total_seconds())

    return RateLimitOutcome(allowed=allowed, remaining=remaining, retry_after=retry_after)
