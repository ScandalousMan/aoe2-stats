"""Integration test for FR-025's deadline-breach alert, raised by `run_once` (T059a) after the
drain, against the still-open `ingest_runs` row `run_once` (T059) opened at the start of the same
cycle.

FR-025: "System MUST raise an alert when any replay passes its capture deadline unarchived. This
count is expected to be permanently zero. This alert fires at the **capture deadline** (day 21),
not at expiry (day ~31)." T059a's own task text is more specific still: one aggregate severity-1
`deadline_breach` row per run, carrying every offending capture's id in `detail`, for every capture
past `capture_deadline_at` that is neither `stored`, `unavailable` nor `quarantined` — "one row per
run, never one per capture: a backlog would otherwise bury the alert it is supposed to raise."

This is a different alert, with a different timing, from `expired_capture` (T056, tested by T047):
`expired_capture` is a post-mortem raised once the source's ~31-day retention has actually closed,
whereas `deadline_breach` fires at the internal 21-day budget with roughly ten days still left to
act. Asserting one for the other would hide a missing alert — see T047's own module docstring for
the same warning from the other direction.

**Why `run_once(..., session_factory=session_factory)`.** `run_once`'s own module docstring says
`budget_seconds`, `trigger` and `stages` are resolved once by whichever entrypoint calls it and
handed down explicitly, never re-read from the environment inside `run_once` itself — the same
discipline `packages/storage/src/aoe2stats_storage/repositories/base.py` names directly: "the
ingester's `run_once()` (T059) ... build[s] ... an engine from it [`DATABASE_URL`]" for its own
direct writes (the `ingest_runs` row this alert is counted against), distinct from whatever a
`Stage` does with its own session. `session_factory` is exactly the same injectable, DI-only seam
`DiscoverStage` already takes in `test_shared_match.py` (T053's own sibling test in this batch) —
the natural analogue for `run_once`'s own database access rather than a `Stage`'s. `stages=()`
isolates this test to that direct bookkeeping alone: discovery, reconciliation and the capture
drain (T053-T055) are irrelevant to whether the deadline sweep itself is correct, and none of them
exist yet at this point in the sequence in any case.

The module `aoe2stats_ingester.run` already exists (T018) — only the behaviour under test, T059a's
alert, does not. `run_once` is still imported inside each test body rather than at module scope,
matching this batch's convention (`test_shared_match.py`, `test_quota.py`): defensive against a
future T059/T059a implementation that makes importing `run.py` pull in modules that do not exist
yet either, and consistent rather than a special case for the one file in the batch whose target
module happens to predate its target behaviour.

Every assertion below runs for real against the real throwaway database. This file previously
wrapped its three tests in `xfail(strict=True, reason="T059a not implemented yet")` per this
project's test-first convention (CLAUDE.md), except for
`test_deadline_breach_is_not_raised_for_stored_unavailable_or_quarantined_captures`, which was
`strict=False`: that one assertion is an absence (`alerts == []`), and T059 alone (landing
`run_once(..., session_factory=...)` and the `ingest_runs` row lifecycle, but deliberately not
T059a's alert itself) already made it trivially true, so `strict=True` would have XPASSed before
T059a existed to give it any meaning. Now that T059a (this module's `_raise_deadline_breach_alert`)
lands, all three markers are gone: `run_once` raises the real alert, and every assertion here checks
something that would actually fail if that behaviour regressed.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from aoe2stats_storage.models import (
    Alert,
    AlertKind,
    AoeProfile,
    CaptureSource,
    CaptureStatus,
    IngestRun,
    Match,
    ReplayCapture,
)

_LEADERBOARD_ID = 3
#: Captures whose blob has actually been written, per data-model.md's write-ordering note: a
#: `quarantined` capture is still uploaded (FR-026), never discarded, so it carries the same
#: object columns a `stored` one does.
_HAS_BLOB = {CaptureStatus.STORED, CaptureStatus.QUARANTINED}


async def _seed_profile(session_factory: async_sessionmaker, profile_id: int, alias: str) -> None:
    async with session_factory() as session:
        session.add(AoeProfile(profile_id=profile_id, alias=alias, country="FR"))
        await session.commit()


async def _seed_capture(
    session_factory: async_sessionmaker,
    *,
    game_id: int,
    profile_id: int,
    status: CaptureStatus,
    capture_deadline_at: datetime,
    completed_at: datetime | None = None,
) -> uuid.UUID:
    """One `matches` row plus one `replay_captures` row hung off it, committed on their own
    connection so `run_once`'s own session (opened separately, against the same
    `session_factory`) actually sees this data rather than racing an uncommitted transaction — the
    same discipline `test_shared_match.py`'s `_seed_two_consenting_users_sharing_a_match` documents
    for `DiscoverStage`.

    `capture_deadline_at` is always passed explicitly rather than derived from `CAPTURE_BUDGET_DAYS`
    here: this test exercises the sweep that *reads* the column, not the arithmetic that computes it
    on insert (that is T053's `test_shared_match.py`).
    """
    if completed_at is None:
        completed_at = capture_deadline_at - timedelta(days=21)
    capture_id = uuid.uuid4()
    has_blob = status in _HAS_BLOB
    async with session_factory() as session:
        session.add(
            Match(
                game_id=game_id,
                leaderboard_id=_LEADERBOARD_ID,
                completed_at=completed_at,
                source="relic",
                raw_payload={"matchId": game_id},
            )
        )
        await session.flush()
        session.add(
            ReplayCapture(
                id=capture_id,
                game_id=game_id,
                profile_id=profile_id,
                status=status,
                capture_deadline_at=capture_deadline_at,
                source=CaptureSource.AUTOMATIC,
                object_key=f"replays/{game_id}/{profile_id}.zip" if has_blob else None,
                zip_bytes=123_456 if has_blob else None,
                zip_sha256=("0" * 64) if has_blob else None,
                stored_at=(
                    completed_at + timedelta(hours=1) if status == CaptureStatus.STORED else None
                ),
                last_error=(
                    "capture-time validation failed"
                    if status == CaptureStatus.QUARANTINED
                    else None
                ),
            )
        )
        await session.commit()
    return capture_id


async def _deadline_breach_alerts(session_factory: async_sessionmaker) -> list[Alert]:
    async with session_factory() as session:
        result = await session.execute(select(Alert).where(Alert.kind == AlertKind.DEADLINE_BREACH))
        return list(result.scalars().all())


async def test_deadline_breach_produces_one_row_carrying_every_offending_capture_id(
    session_factory: async_sessionmaker,
    clean_database: None,
) -> None:
    from aoe2stats_ingester.run import run_once

    profile_id = 700_000_001
    await _seed_profile(session_factory, profile_id, "Offender")

    now = datetime.now(UTC)
    offending_ids: set[str] = set()
    # Three offending captures, not two: "whatever the number" (FR-025/T059a) is a claim about
    # aggregation, not about a fixed count.
    for index, game_id in enumerate((701_000_001, 701_000_002, 701_000_003)):
        capture_id = await _seed_capture(
            session_factory,
            game_id=game_id,
            profile_id=profile_id,
            status=CaptureStatus.PENDING,
            capture_deadline_at=now - timedelta(hours=1, minutes=index),
        )
        offending_ids.add(str(capture_id))

    # A pending capture whose deadline has not yet arrived must never be swept in.
    await _seed_capture(
        session_factory,
        game_id=701_000_099,
        profile_id=profile_id,
        status=CaptureStatus.PENDING,
        capture_deadline_at=now + timedelta(days=1),
    )

    await run_once(30, trigger="test", stages=(), session_factory=session_factory)

    alerts = await _deadline_breach_alerts(session_factory)
    assert len(alerts) == 1, (
        "FR-025/T059a: whatever the number of offending captures, one run raises exactly one "
        "aggregate `deadline_breach` row — never one per capture, which would bury the alert a "
        "backlog is supposed to surface."
    )
    alert = alerts[0]
    assert alert.severity == 1, (
        "the two kinds meaning a replay is gone or about to be are severity 1"
    )
    assert alert.detail is not None
    carried_ids = set(alert.detail.get("capture_ids", []))
    assert carried_ids == offending_ids, (
        "the single alert must carry every offending capture's id, not merely the first one found, "
        "and none belonging to the capture whose deadline has not yet arrived"
    )

    async with session_factory() as session:
        result = await session.execute(select(IngestRun).order_by(IngestRun.started_at.desc()))
        ingest_runs = list(result.scalars().all())
    assert ingest_runs, "run_once (T059) must open an `ingest_runs` row before doing any work"
    assert alert.ingest_run_id == ingest_runs[0].id, (
        "the alert must carry the real `ingest_run_id` of the run that raised it (T059a), so it is "
        "counted in that row's `alerts_raised` rather than left orphaned"
    )


async def test_deadline_breach_is_not_raised_for_stored_unavailable_or_quarantined_captures(
    session_factory: async_sessionmaker,
    clean_database: None,
) -> None:
    from aoe2stats_ingester.run import run_once

    profile_id = 700_000_002
    await _seed_profile(session_factory, profile_id, "Archived")

    past_deadline = datetime.now(UTC) - timedelta(days=1)
    for game_id, status in (
        (702_000_001, CaptureStatus.STORED),
        (702_000_002, CaptureStatus.UNAVAILABLE),
        (702_000_003, CaptureStatus.QUARANTINED),
    ):
        await _seed_capture(
            session_factory,
            game_id=game_id,
            profile_id=profile_id,
            status=status,
            capture_deadline_at=past_deadline,
        )

    await run_once(30, trigger="test", stages=(), session_factory=session_factory)

    alerts = await _deadline_breach_alerts(session_factory)
    assert alerts == [], (
        "a capture that is `stored`, `unavailable` or `quarantined` has already been resolved one "
        "way or another and must never trigger `deadline_breach`, even with its deadline in the "
        "past (FR-025) — this is the entire reason the check reads `status`, not merely "
        "`capture_deadline_at`"
    )


async def test_deadline_breach_fires_at_the_capture_deadline_and_not_before(
    session_factory: async_sessionmaker,
    clean_database: None,
) -> None:
    """The boundary itself, and the distinction from `expired_capture` (T056/T047) stated
    concretely: a capture one minute past its own `capture_deadline_at` is already breached, no
    matter how far that is from the source's ~31-day retention window, and a capture one minute
    short of its deadline is not breached yet. A check keyed to some expiry-style margin instead of
    `capture_deadline_at` itself would get either half of this wrong.
    """
    from aoe2stats_ingester.run import run_once

    profile_id = 700_000_003
    await _seed_profile(session_factory, profile_id, "Boundary")

    now = datetime.now(UTC)
    breached_id = await _seed_capture(
        session_factory,
        game_id=703_000_001,
        profile_id=profile_id,
        status=CaptureStatus.PENDING,
        capture_deadline_at=now - timedelta(minutes=1),
    )
    await _seed_capture(
        session_factory,
        game_id=703_000_002,
        profile_id=profile_id,
        status=CaptureStatus.PENDING,
        capture_deadline_at=now + timedelta(minutes=1),
    )

    await run_once(30, trigger="test", stages=(), session_factory=session_factory)

    alerts = await _deadline_breach_alerts(session_factory)
    assert len(alerts) == 1
    assert alerts[0].detail is not None
    assert set(alerts[0].detail.get("capture_ids", [])) == {str(breached_id)}, (
        "the alert fires the moment `capture_deadline_at` (day 21) has passed, for exactly the "
        "capture whose deadline actually has — the other capture, one minute short of its own "
        "deadline, must not be swept in early, and this alert must never wait for anything "
        "resembling the source's ~31-day retention expiry"
    )


async def test_deadline_breach_is_not_raised_for_a_terminal_expired_or_failed_capture(
    session_factory: async_sessionmaker,
    clean_database: None,
) -> None:
    """T059b: `expired` and `failed` are terminal — nothing ever moves a row out of either, and
    both sit permanently past their own `capture_deadline_at` by construction (an `expired` capture
    was already past its deadline by the time `_classify_not_found`, T056, closed it that way; a
    `failed` capture only reaches that status after `_MAX_ATTEMPTS`, T057, which itself only fires
    once `next_attempt_at`'s backoff has run past the deadline in every realistic case). Sweeping
    either in here would raise a fresh severity-1 `deadline_breach` every single cycle forever, for
    a loss already reported once — by `expired_capture` (T056) for `expired`, or by the run's own
    `failed_total` counter for `failed` — which is exactly the unbounded flood T059b exists to
    close.
    """
    from aoe2stats_ingester.run import run_once

    profile_id = 700_000_004
    await _seed_profile(session_factory, profile_id, "Terminal")

    past_deadline = datetime.now(UTC) - timedelta(days=1)
    for game_id, status in (
        (704_000_001, CaptureStatus.EXPIRED),
        (704_000_002, CaptureStatus.FAILED),
    ):
        await _seed_capture(
            session_factory,
            game_id=game_id,
            profile_id=profile_id,
            status=status,
            capture_deadline_at=past_deadline,
        )

    await run_once(30, trigger="test", stages=(), session_factory=session_factory)

    alerts = await _deadline_breach_alerts(session_factory)
    assert alerts == [], (
        "a capture that is `expired` or `failed` is terminal — nothing ever moves it out of that "
        "state, and it was already alerted once by its own terminal producer, so it must never "
        "raise `deadline_breach` on top, however many cycles run afterwards"
    )


async def test_deadline_breach_is_raised_once_across_two_runs_over_the_same_unresolved_breach(
    session_factory: async_sessionmaker,
    clean_database: None,
) -> None:
    """T059b's suppression rule: the sweep re-runs every cycle, but must not insert a second
    severity-1 row for a capture an unacknowledged `deadline_breach` already names. Two consecutive
    cycles over the exact same unresolved breach must produce exactly one alert row, not two —
    otherwise acknowledging today's is answered by tomorrow's, and `alert_audit.py`'s nightly gate
    can never be returned to green by any action short of deleting rows.
    """
    from aoe2stats_ingester.run import run_once

    profile_id = 700_000_005
    await _seed_profile(session_factory, profile_id, "Repeat")

    past_deadline = datetime.now(UTC) - timedelta(days=1)
    breached_id = await _seed_capture(
        session_factory,
        game_id=705_000_001,
        profile_id=profile_id,
        status=CaptureStatus.PENDING,
        capture_deadline_at=past_deadline,
    )

    first_report = await run_once(30, trigger="test", stages=(), session_factory=session_factory)
    second_report = await run_once(30, trigger="test", stages=(), session_factory=session_factory)

    alerts = await _deadline_breach_alerts(session_factory)
    assert len(alerts) == 1, (
        "the breach is still unresolved and still unacknowledged the second cycle around — the "
        "sweep must recognise it already named this capture and raise nothing new for it"
    )
    assert alerts[0].detail is not None
    assert set(alerts[0].detail.get("capture_ids", [])) == {str(breached_id)}

    assert second_report.ingest_run_id != first_report.ingest_run_id, (
        "sanity: the two calls really are two separate runs, not one counted twice"
    )


async def test_deadline_breach_raises_again_when_a_new_capture_breaches(
    session_factory: async_sessionmaker,
    clean_database: None,
) -> None:
    """The suppression rule must not swallow a genuinely new incident: a second capture breaching
    its own deadline while an earlier one is still unacknowledged is a new loss, not a repeat of the
    same one, and must raise a second alert.
    """
    from aoe2stats_ingester.run import run_once

    profile_id = 700_000_006
    await _seed_profile(session_factory, profile_id, "Growing")

    past_deadline = datetime.now(UTC) - timedelta(days=1)
    first_breached_id = await _seed_capture(
        session_factory,
        game_id=706_000_001,
        profile_id=profile_id,
        status=CaptureStatus.PENDING,
        capture_deadline_at=past_deadline,
    )

    await run_once(30, trigger="test", stages=(), session_factory=session_factory)

    second_breached_id = await _seed_capture(
        session_factory,
        game_id=706_000_002,
        profile_id=profile_id,
        status=CaptureStatus.PENDING,
        capture_deadline_at=past_deadline,
    )

    await run_once(30, trigger="test", stages=(), session_factory=session_factory)

    alerts = await _deadline_breach_alerts(session_factory)
    assert len(alerts) == 2, (
        "a newly breaching capture is a new incident even while an older, unacknowledged one is "
        "still open — the suppression rule must not swallow it"
    )
    all_carried_ids: set[str] = set()
    for alert in alerts:
        assert alert.detail is not None
        all_carried_ids.update(alert.detail.get("capture_ids", []))
    assert all_carried_ids == {str(first_breached_id), str(second_breached_id)}


async def test_deadline_breach_raises_again_once_the_prior_alert_is_acknowledged(
    session_factory: async_sessionmaker,
    clean_database: None,
) -> None:
    """The suppression rule must not become permanent: once a human has acknowledged the previous
    alert and the breach is still unresolved, the next cycle raises again — an acknowledged alert
    that nothing ever follows up on would silently downgrade FR-025 from "act inside ~10 days" to
    "was told once, eventually".
    """
    from aoe2stats_ingester.run import run_once

    profile_id = 700_000_007
    await _seed_profile(session_factory, profile_id, "Acknowledged")

    past_deadline = datetime.now(UTC) - timedelta(days=1)
    breached_id = await _seed_capture(
        session_factory,
        game_id=707_000_001,
        profile_id=profile_id,
        status=CaptureStatus.PENDING,
        capture_deadline_at=past_deadline,
    )

    await run_once(30, trigger="test", stages=(), session_factory=session_factory)

    async with session_factory() as session:
        await session.execute(
            update(Alert)
            .where(Alert.kind == AlertKind.DEADLINE_BREACH)
            .values(acknowledged_at=datetime.now(UTC))
        )
        await session.commit()

    await run_once(30, trigger="test", stages=(), session_factory=session_factory)

    alerts = await _deadline_breach_alerts(session_factory)
    assert len(alerts) == 2, (
        "the breach is still unresolved after the acknowledgement — the next cycle must raise a "
        "fresh alert rather than treating an acknowledged row as still-active suppression"
    )
    for alert in alerts:
        assert alert.detail is not None
        assert set(alert.detail.get("capture_ids", [])) == {str(breached_id)}
