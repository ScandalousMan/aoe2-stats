"""Tests for the nightly cron-liveness check (T048, T061b, quickstart scenario 11).

FR-024 requires every ingestion cycle to leave a trace an outside observer can read; SC-007 turns
that into a number — a cron that stops firing must be detected within 30 hours. `cron_liveness.py`
(T061) is the check: it reads the newest `ingest_runs` row and fails if that row is too old. Nothing
inside a system that has stopped running can report that it has stopped (data-model.md, "`ingest_
runs`"), so this is exercised from outside — against the real throwaway database (`tests/db.py`,
T015), the same way the ingester itself will write the row, not against a hand-rolled stand-in for
one.

`cron_liveness.py` is implemented by T061. Every test below still imports the module inside the
test body rather than at module scope, matching the rest of this batch's convention even now that
the module exists — nothing here depends on `xfail` any more.

Scenario 11, verbatim: "Note the newest `ingest_runs` row. Run the nightly cron-liveness check.
Expect pass. Backdate that row by 31 hours. Expect the check to fail." Every assertion below traces
back to one clause of that.

T061b adds the second signal: `check_liveness` now returns a `LivenessStatus` rather than a bare
bool, because a newest row that is still open (`finished_at is None`) and has been open for
implausibly long relative to `INGEST_RUN_BUDGET_SECONDS` is its own failure (`STALLED`), distinct
from a `started_at` that is simply too old (`STALE`). Every row `_insert_run` produces below is open
by construction unless `finished_at` is passed explicitly — exactly like T059's own row, whose
`finished_at` stays at its default until the run that opened it closes it — so the five pre-existing
scenarios below (all using `started_at` ages of 0 h, 31 h, 48 h and 72 h, orders of magnitude away
from any plausible `run_budget_seconds` threshold) resolve identically to before; only their
assertions now name the `LivenessStatus` member rather than a bool.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.db import clean_database, database_url, db_session, engine, session_factory

from aoe2stats_storage.models import IngestRun

# Re-exported so ruff sees these names used: pytest discovers a fixture imported into a test module
# exactly as if it had been defined here (see apps/api/tests/conftest.py, which relies on the same
# mechanism) — the one implementation lives in tests/db.py and every consumer imports it rather than
# duplicating it.
__all__ = ["clean_database", "database_url", "db_session", "engine", "session_factory"]

# Verbatim from quickstart scenario 11 and SC-007: a fresh row (age 0) must pass, and a row
# backdated by 31 hours — one hour past the 30-hour SC-007 budget — must fail. Neither test below
# asserts anything at the exact 30-hour boundary itself: quickstart never exercises it, and picking
# a value on either side of it here would be asserting a rounding rule this task was never told.
_FRESH_AGE = timedelta(hours=0)
_BACKDATED_AGE = timedelta(hours=31)

# T061b: a `run_budget_seconds` used only by the stalled-row tests below, picked round and small so
# the "well past" and "still inside" ages can be orders of magnitude apart without coupling any
# test to `cron_liveness.py`'s own `_STALLED_RUN_BUDGET_MULTIPLIER` — the same reasoning
# `_BACKDATED_AGE` above already applies to `LIVENESS_BUDGET_HOURS`.
_RUN_BUDGET_SECONDS = 60.0
_WELL_PAST_BUDGET_AGE = timedelta(hours=1)
_WELL_WITHIN_BUDGET_AGE = timedelta(seconds=5)


async def _insert_run(
    session: AsyncSession, *, started_at: datetime, finished_at: datetime | None = None
) -> IngestRun:
    """One `ingest_runs` row, carrying only what T059 says is written when a run starts
    (`started_at`, `trigger`, `budget_seconds`) — `finished_at` and every counter stay at their
    defaults, exactly like a row for a cycle that is still in flight or has just begun, unless a
    caller passes `finished_at` explicitly to model a run that closed cleanly (T061b)."""
    run = IngestRun(
        started_at=started_at, finished_at=finished_at, trigger="cron", budget_seconds=240
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


def test_is_live_passes_for_a_run_that_just_started() -> None:
    """The pure boundary logic, exercised with no database at all: a run that started this instant
    is live."""
    from scripts.checks.cron_liveness import is_live

    now = datetime(2026, 8, 22, 12, 0, 0, tzinfo=UTC)
    assert is_live(now - _FRESH_AGE, now=now) is True


def test_is_live_fails_for_a_run_backdated_by_31_hours() -> None:
    """The same pure logic, on the exact backdating quickstart scenario 11 specifies."""
    from scripts.checks.cron_liveness import is_live

    now = datetime(2026, 8, 22, 12, 0, 0, tzinfo=UTC)
    assert is_live(now - _BACKDATED_AGE, now=now) is False


def test_is_live_fails_when_no_run_has_ever_been_recorded() -> None:
    """data-model.md: "the absence of a row is the signal." `is_live` must treat "no run yet" as
    not live rather than raising, since the very first cycle in a fresh environment must show up as
    a genuine failure, not as an exception the caller has to remember to special-case."""
    from scripts.checks.cron_liveness import is_live

    now = datetime(2026, 8, 22, 12, 0, 0, tzinfo=UTC)
    assert is_live(None, now=now) is False


async def test_check_liveness_passes_against_a_fresh_ingest_runs_row(
    db_session: AsyncSession,
) -> None:
    """Quickstart scenario 11, step 1-2: a freshly inserted row is enough on its own for the check
    to pass, exercised against the real `ingest_runs` table rather than a stand-in for it."""
    from scripts.checks.cron_liveness import LivenessStatus, check_liveness

    now = datetime.now(UTC)
    await _insert_run(db_session, started_at=now)

    status = await check_liveness(db_session, now=now, run_budget_seconds=_RUN_BUDGET_SECONDS)
    assert status is LivenessStatus.LIVE


async def test_check_liveness_fails_once_that_row_is_backdated_by_31_hours(
    db_session: AsyncSession,
) -> None:
    """Quickstart scenario 11 end to end, in the order the scenario states it: the same row that
    just passed must fail once backdated, with nothing else about the database changed in between —
    the only variable this test moves is the row's age. Backdated by 31 h (T061b: well past
    `LIVENESS_BUDGET_HOURS`), this reads as `STALE` — "the cron stopped firing" — rather than
    `STALLED`, exactly as it did before this task."""
    from scripts.checks.cron_liveness import LivenessStatus, check_liveness

    now = datetime.now(UTC)
    run = await _insert_run(db_session, started_at=now)
    status = await check_liveness(db_session, now=now, run_budget_seconds=_RUN_BUDGET_SECONDS)
    assert status is LivenessStatus.LIVE

    run.started_at = now - _BACKDATED_AGE
    await db_session.commit()

    status = await check_liveness(db_session, now=now, run_budget_seconds=_RUN_BUDGET_SECONDS)
    assert status is LivenessStatus.STALE


async def test_check_liveness_fails_when_no_run_has_ever_been_recorded(
    db_session: AsyncSession,
) -> None:
    """The check must fail against a genuinely empty `ingest_runs` table — the first cycle in a new
    environment, or every row somehow having been lost — and not merely against a stale one."""
    from scripts.checks.cron_liveness import LivenessStatus, check_liveness

    assert (await db_session.execute(select(IngestRun))).first() is None

    status = await check_liveness(
        db_session, now=datetime.now(UTC), run_budget_seconds=_RUN_BUDGET_SECONDS
    )
    assert status is LivenessStatus.STALE


async def test_check_liveness_reads_the_newest_row_not_an_older_one(
    db_session: AsyncSession,
) -> None:
    """data-model.md: "the nightly job reads the newest one." A stale row sitting alongside a fresh
    one must not drag the check down — only the most recent `started_at` decides the outcome."""
    from scripts.checks.cron_liveness import LivenessStatus, check_liveness

    now = datetime.now(UTC)
    await _insert_run(db_session, started_at=now - timedelta(hours=48))
    await _insert_run(db_session, started_at=now)

    status = await check_liveness(db_session, now=now, run_budget_seconds=_RUN_BUDGET_SECONDS)
    assert status is LivenessStatus.LIVE


async def test_check_liveness_ignores_a_newer_but_still_backdated_row(
    db_session: AsyncSession,
) -> None:
    """The mirror image of the previous test: an old row still sitting there does not rescue the
    outcome once the newest row is itself stale — the check reads the newest row's own age, not
    merely "does a row exist that was once live"."""
    from scripts.checks.cron_liveness import LivenessStatus, check_liveness

    now = datetime.now(UTC)
    await _insert_run(db_session, started_at=now - timedelta(hours=72))
    await _insert_run(db_session, started_at=now - _BACKDATED_AGE)

    status = await check_liveness(db_session, now=now, run_budget_seconds=_RUN_BUDGET_SECONDS)
    assert status is LivenessStatus.STALE


def test_is_stalled_is_false_for_an_open_row_still_inside_its_budget() -> None:
    """The pure boundary logic behind T061b's new signal: an open row that has not yet outlived
    `_STALLED_RUN_BUDGET_MULTIPLIER` x `run_budget_seconds` is simply a run still in progress, and
    is evidence of nothing."""
    from scripts.checks.cron_liveness import is_stalled

    now = datetime(2026, 8, 22, 12, 0, 0, tzinfo=UTC)
    assert (
        is_stalled(
            now - _WELL_WITHIN_BUDGET_AGE,
            None,
            now=now,
            run_budget_seconds=_RUN_BUDGET_SECONDS,
        )
        is False
    )


def test_is_stalled_is_true_for_an_open_row_well_past_its_budget() -> None:
    """The same logic on the other side of the boundary: an open row that has sat far longer than a
    completed run could plausibly need is stalled."""
    from scripts.checks.cron_liveness import is_stalled

    now = datetime(2026, 8, 22, 12, 0, 0, tzinfo=UTC)
    assert (
        is_stalled(
            now - _WELL_PAST_BUDGET_AGE,
            None,
            now=now,
            run_budget_seconds=_RUN_BUDGET_SECONDS,
        )
        is True
    )


def test_is_stalled_is_false_once_the_row_has_a_finished_at() -> None:
    """A closed row is never stalled, however long ago it started: `finished_at` being set already
    answers the question `is_stalled` exists to ask, and `is_live` — the separate, 30-hour
    question — is what governs a row this old instead."""
    from scripts.checks.cron_liveness import is_stalled

    now = datetime(2026, 8, 22, 12, 0, 0, tzinfo=UTC)
    started_at = now - _WELL_PAST_BUDGET_AGE
    assert (
        is_stalled(
            started_at,
            started_at + timedelta(seconds=1),
            now=now,
            run_budget_seconds=_RUN_BUDGET_SECONDS,
        )
        is False
    )


async def test_check_liveness_fails_for_an_open_row_well_past_its_run_budget(
    db_session: AsyncSession,
) -> None:
    """T061b's actual case: a `started_at` recent enough to pass the old, `started_at`-only check
    (SC-007's front door), paired with a row that never closed. A cron that fires on schedule and
    dies in a stage every cycle looks exactly like this every single night — the failure this task
    exists to stop the check from missing."""
    from scripts.checks.cron_liveness import LivenessStatus, check_liveness

    now = datetime.now(UTC)
    await _insert_run(db_session, started_at=now - _WELL_PAST_BUDGET_AGE)

    status = await check_liveness(db_session, now=now, run_budget_seconds=_RUN_BUDGET_SECONDS)
    assert status is LivenessStatus.STALLED


async def test_check_liveness_passes_for_an_open_row_still_inside_its_run_budget(
    db_session: AsyncSession,
) -> None:
    """A run genuinely still in progress — open, but young relative to `run_budget_seconds` — must
    not be mistaken for a dead one: `is_stalled`'s whole reason to exist is telling these two apart.
    """
    from scripts.checks.cron_liveness import LivenessStatus, check_liveness

    now = datetime.now(UTC)
    await _insert_run(db_session, started_at=now - _WELL_WITHIN_BUDGET_AGE)

    status = await check_liveness(db_session, now=now, run_budget_seconds=_RUN_BUDGET_SECONDS)
    assert status is LivenessStatus.LIVE


async def test_check_liveness_passes_for_a_recent_closed_row_even_past_the_run_budget(
    db_session: AsyncSession,
) -> None:
    """A run that closed cleanly is never stalled, however long its own `started_at` ->
    `finished_at` span was — `is_stalled` only ever looks at rows still open. This is the case
    T061b's own text calls out: "the newest row is still the one that decides" stays true, and a
    completed run is not a failure just because it took a while."""
    from scripts.checks.cron_liveness import LivenessStatus, check_liveness

    now = datetime.now(UTC)
    started_at = now - _WELL_PAST_BUDGET_AGE
    await _insert_run(
        db_session, started_at=started_at, finished_at=started_at + timedelta(seconds=1)
    )

    status = await check_liveness(db_session, now=now, run_budget_seconds=_RUN_BUDGET_SECONDS)
    assert status is LivenessStatus.LIVE
