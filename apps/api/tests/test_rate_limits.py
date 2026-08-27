"""Tests for the fixed-window rate limiter (T307), `apps/api/src/aoe2stats_api/ratelimit.py`.

R10 (`research.md`) and `data-model.md`'s `rate_limit_counters` section: a database-backed,
fixed-window counter keyed on `(user_id, bucket, window_start)`, incremented with an upsert,
guarding `search` (FR-005), `replay_download` (FR-028) and `analysis_request` (FR-040).
Database-backed rather than in-memory, for the reason constitution XII exists to enforce: this
platform gives no shared process between two invocations, so an in-memory counter would work on a
VPS and silently count nothing on Vercel.

`aoe2stats_api.ratelimit` does not exist until T307 lands, so every test below carries
`@pytest.mark.xfail(strict=True, reason="T307 not implemented yet")` per CLAUDE.md's test-first
convention, and imports the module inside its own body rather than at module scope — a
module-scope import of a module that does not exist yet is a collection error that takes the
whole workspace suite down, not one failing test.

**The interface under test is designed here, not merely exercised**: `check_and_increment(session,
*, user_id, bucket, limit, window_seconds, now=None)` returning a `RateLimitOutcome(allowed,
remaining, retry_after)`. `now` is an explicit parameter rather than a call to `datetime.now()`
inside the function, so window boundaries are deterministic under test instead of racing the
clock. Every `now` below is an offset from `_WINDOW_ORIGIN`, whose epoch second is an exact
multiple of every `window_seconds` this file uses (60), so the obvious, boring choice — a fixed
window aligned to the Unix epoch — buckets them into the same or a different window predictably,
without this file having to know or restate the implementation's own arithmetic.

`test_the_counter_survives_a_process_with_no_shared_memory` is the test this file exists for.
Every assertion above it also passes against an in-memory dict keyed on `(user_id, bucket,
window)` — that shape looks entirely correct inside one pytest process, where the dict simply
never gets garbage collected between calls. What it cannot survive is a second call made from a
genuinely separate OS process: an empty `sys.modules`, no Python object in common with the first,
nothing shared but the database `database_url` names. `subprocess.run` is the same tool
`test_engine_isolation.py` (T018c) reaches for, for the same reason — an in-process assertion has
ways to lie that a subprocess boundary does not.
"""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_storage.models import User

pytestmark = [pytest.mark.usefixtures("environment")]

# 2024-01-01T00:00:00Z's Unix epoch second (1704067200) is an exact multiple of the 60-second
# window every test below uses, so it is a clean boundary for an epoch-aligned fixed window to
# bucket against. Every `now` below is expressed as an offset from it rather than from
# `datetime.now()`, so these tests never race real time.
_WINDOW_ORIGIN = datetime(2024, 1, 1, tzinfo=UTC)

_WINDOW_SECONDS = 60


async def _seed_user(db_session: AsyncSession) -> uuid.UUID:
    """One `users` row — `rate_limit_counters.user_id` is a foreign key, so a counter cannot be
    written for an id nothing else recognises."""
    user = User(allowlisted_at=_WINDOW_ORIGIN)
    db_session.add(user)
    await db_session.flush()
    return user.id


# --- The subprocess this file's own reason for existing runs -----------------------------------

_SUBPROCESS_SCRIPT = """
import asyncio
import json
import sys
import uuid
from datetime import datetime

from aoe2stats_api.ratelimit import check_and_increment
from aoe2stats_storage.repositories.base import (
    build_engine,
    build_session_factory,
    session_scope,
)


async def main() -> None:
    database_url, user_id, bucket, limit, window_seconds, now_iso = sys.argv[1:7]
    engine = build_engine(database_url)
    try:
        session_factory = build_session_factory(engine)
        async with session_scope(session_factory) as session:
            outcome = await check_and_increment(
                session,
                user_id=uuid.UUID(user_id),
                bucket=bucket,
                limit=int(limit),
                window_seconds=int(window_seconds),
                now=datetime.fromisoformat(now_iso),
            )
        print(json.dumps({"allowed": outcome.allowed, "remaining": outcome.remaining}))
    finally:
        await engine.dispose()


asyncio.run(main())
"""


# --- Tests ---------------------------------------------------------------------------------------


async def test_counter_increments_per_call_and_denies_past_the_bound(
    db_session: AsyncSession,
) -> None:
    from aoe2stats_api.ratelimit import check_and_increment

    user_id = await _seed_user(db_session)
    limit = 3
    now = _WINDOW_ORIGIN + timedelta(seconds=5)

    outcomes = [
        await check_and_increment(
            db_session,
            user_id=user_id,
            bucket="search",
            limit=limit,
            window_seconds=_WINDOW_SECONDS,
            now=now,
        )
        for _ in range(limit)
    ]

    assert [outcome.allowed for outcome in outcomes] == [True, True, True]
    assert [outcome.remaining for outcome in outcomes] == [2, 1, 0]

    fourth = await check_and_increment(
        db_session,
        user_id=user_id,
        bucket="search",
        limit=limit,
        window_seconds=_WINDOW_SECONDS,
        now=now,
    )
    assert fourth.allowed is False
    assert fourth.remaining == 0


async def test_exceeding_the_bound_returns_the_remaining_seconds(
    db_session: AsyncSession,
) -> None:
    from aoe2stats_api.ratelimit import check_and_increment

    user_id = await _seed_user(db_session)
    limit = 1
    # 41 s into a window that opened at `_WINDOW_ORIGIN` and closes 60 s later: 19 s left.
    now = _WINDOW_ORIGIN + timedelta(seconds=41)

    first = await check_and_increment(
        db_session,
        user_id=user_id,
        bucket="replay_download",
        limit=limit,
        window_seconds=_WINDOW_SECONDS,
        now=now,
    )
    assert first.allowed is True
    assert first.retry_after is None

    second = await check_and_increment(
        db_session,
        user_id=user_id,
        bucket="replay_download",
        limit=limit,
        window_seconds=_WINDOW_SECONDS,
        now=now,
    )
    assert second.allowed is False
    assert second.retry_after == 19


async def test_a_window_boundary_resets_the_counter(db_session: AsyncSession) -> None:
    from aoe2stats_api.ratelimit import check_and_increment

    user_id = await _seed_user(db_session)
    limit = 1
    last_second_of_the_window = _WINDOW_ORIGIN + timedelta(seconds=59)

    first = await check_and_increment(
        db_session,
        user_id=user_id,
        bucket="analysis_request",
        limit=limit,
        window_seconds=_WINDOW_SECONDS,
        now=last_second_of_the_window,
    )
    assert first.allowed is True

    still_denied_in_the_same_window = await check_and_increment(
        db_session,
        user_id=user_id,
        bucket="analysis_request",
        limit=limit,
        window_seconds=_WINDOW_SECONDS,
        now=last_second_of_the_window,
    )
    assert still_denied_in_the_same_window.allowed is False

    first_second_of_the_next_window = _WINDOW_ORIGIN + timedelta(seconds=60)
    reset = await check_and_increment(
        db_session,
        user_id=user_id,
        bucket="analysis_request",
        limit=limit,
        window_seconds=_WINDOW_SECONDS,
        now=first_second_of_the_next_window,
    )
    assert reset.allowed is True
    assert reset.remaining == 0


async def test_two_users_never_share_a_window(db_session: AsyncSession) -> None:
    from aoe2stats_api.ratelimit import check_and_increment

    first_user_id = await _seed_user(db_session)
    second_user_id = await _seed_user(db_session)
    limit = 1
    now = _WINDOW_ORIGIN + timedelta(seconds=1)

    first_user_outcome = await check_and_increment(
        db_session,
        user_id=first_user_id,
        bucket="search",
        limit=limit,
        window_seconds=_WINDOW_SECONDS,
        now=now,
    )
    second_user_outcome = await check_and_increment(
        db_session,
        user_id=second_user_id,
        bucket="search",
        limit=limit,
        window_seconds=_WINDOW_SECONDS,
        now=now,
    )

    assert first_user_outcome.allowed is True
    assert second_user_outcome.allowed is True
    assert first_user_outcome.remaining == 0
    assert second_user_outcome.remaining == 0

    first_user_again = await check_and_increment(
        db_session,
        user_id=first_user_id,
        bucket="search",
        limit=limit,
        window_seconds=_WINDOW_SECONDS,
        now=now,
    )
    assert first_user_again.allowed is False


async def test_two_buckets_for_the_same_user_never_share_a_window(
    db_session: AsyncSession,
) -> None:
    from aoe2stats_api.ratelimit import check_and_increment

    user_id = await _seed_user(db_session)
    limit = 1
    now = _WINDOW_ORIGIN + timedelta(seconds=1)

    search_outcome = await check_and_increment(
        db_session,
        user_id=user_id,
        bucket="search",
        limit=limit,
        window_seconds=_WINDOW_SECONDS,
        now=now,
    )
    download_outcome = await check_and_increment(
        db_session,
        user_id=user_id,
        bucket="replay_download",
        limit=limit,
        window_seconds=_WINDOW_SECONDS,
        now=now,
    )

    assert search_outcome.allowed is True
    assert download_outcome.allowed is True
    assert search_outcome.remaining == 0
    assert download_outcome.remaining == 0


async def test_the_counter_survives_a_process_with_no_shared_memory(
    db_session: AsyncSession,
    database_url: str,
) -> None:
    """The case this file exists for (R10, module docstring). `db_session` commits its own write
    explicitly, before the subprocess runs, because `db_session`'s own commit-on-success happens
    at fixture teardown — after this test function returns — which would be too late for a
    process started *during* the test to see it."""
    from aoe2stats_api.ratelimit import check_and_increment

    user_id = await _seed_user(db_session)
    limit = 5
    now = _WINDOW_ORIGIN + timedelta(seconds=1)

    first_call = await check_and_increment(
        db_session,
        user_id=user_id,
        bucket="search",
        limit=limit,
        window_seconds=_WINDOW_SECONDS,
        now=now,
    )
    await db_session.commit()

    assert first_call.allowed is True
    assert first_call.remaining == limit - 1

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            _SUBPROCESS_SCRIPT,
            database_url,
            str(user_id),
            "search",
            str(limit),
            str(_WINDOW_SECONDS),
            now.isoformat(),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    subprocess_outcome = json.loads(result.stdout.strip())

    # An in-memory counter starts fresh in a new interpreter and would report `remaining == limit
    # - 1` here too, indistinguishable from a first call — exactly the failure that must not
    # pass. A database-backed counter sees the row `db_session` already committed and reports
    # `limit - 2`: the count that carried across the process boundary.
    assert subprocess_outcome["allowed"] is True
    assert subprocess_outcome["remaining"] == limit - 2
