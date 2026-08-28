"""Integration test (T054a) for `aoe2stats_ingester.reconcile`'s 25-day reconciliation sweep — the
mechanism the whole 21-day capture budget is sized around (research.md §6: "reconcile the last 25
days"), and the edge case spec.md names it to absorb: "the match discovery source is unreachable
for several days: capture must catch up automatically, and the 21-day budget must absorb the outage
without loss" (FR-013, FR-014).

T043 (`test_backfill.py`) covers the other half of T054, the 31-day backfill a fresh link asks for
via `profile_links.backfill_requested_at` (T031a). This file is only the 25-day half: an ordinary
consenting, already-linked profile whose discovery cycles failed for several days running, plus the
narrower case the same mechanism happens to also cover — a match discovery skipped even without an
outage, present at the source and simply absent from `matches`, picked up on the very next sweep
rather than waiting for a user to notice.

**Written test-first.** `aoe2stats_ingester.reconcile` does not exist yet — T054 is later in this
same Phase 4 batch. Every test below carries `@pytest.mark.xfail(strict=True, reason="T054 not
implemented yet")`, the pattern `packages/providers/tests/test_relic_matches.py` (T040, ahead of
T050) already established for exactly this situation: `strict=True` turns the run red the instant
T054 makes a test pass for real, forcing the marker off instead of letting a stale xfail hide a
regression. The import of the not-yet-existent `aoe2stats_ingester.reconcile` module happens inside
`_stage()`, called from inside each test body rather than at module scope, so the resulting
`ModuleNotFoundError` becomes this file's own expected failure instead of aborting collection for
the whole workspace suite.

**The seam under test.** Nothing named `ReconcileStage` exists to read a contract from, so this
file states the one this test expects T054 to satisfy: a class constructed with
`session_factory` (an `async_sessionmaker[AsyncSession]`, exactly what `tests/db.py`'s
`session_factory` fixture already hands every Phase 4 stage test — see that fixture's own
docstring, "a test for any of those wires its own `Stage` against the fixtures below"),
`match_history_provider` (a `MatchHistoryProvider`, `contracts/providers.md`) and
`capture_budget_days` (a plain `int`, mirroring how `run_once(budget_seconds)` itself takes its
one tunable as an explicit parameter rather than reading `Settings` internally — `apps/ingester`
declares no dependency on `aoe2stats_api.settings`, by design, per `plan.md`'s module layout).
Called as `await stage(budget)`, the shape `run.py`'s `Stage` protocol already defines and
`test_run.py` already exercises for the two stages that do exist.

No HTTP anywhere in this file: `FakeMatchHistoryProvider` below is a `MatchHistoryProvider` double
that returns canned `RawMatch` values or raises a canned `ProviderUnavailable`, never touching the
network `tests/conftest.py` already blocks by construction (constitution III).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_ingester.budget import Budget
from aoe2stats_ingester.discover import _DISCOVERY_BATCH_SIZE
from aoe2stats_providers.base import MatchHistoryProvider, ProviderUnavailable, RawMatch
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

if TYPE_CHECKING:
    # Type-checking only: mypy needs the name, but nothing here may import the module at
    # collection time — see `_stage()` below, where the real (runtime) import lives. Same
    # pattern `packages/providers/tests/test_relic_matches.py` (T040) already established.
    from aoe2stats_ingester.reconcile import ReconcileStage

XFAIL_REASON = "T054 not implemented yet"

#: Mirrors `.env.example`'s `CAPTURE_BUDGET_DAYS=21`. Passed explicitly to the stage under test
#: rather than read from `Settings` — see the module docstring on why `apps/ingester` takes its
#: tuning knobs as plain parameters, the same way `run_once(budget_seconds)` does.
CAPTURE_BUDGET_DAYS = 21


class FakeMatchHistoryProvider:
    """A `MatchHistoryProvider` double (`contracts/providers.md`) whose response is scripted one
    entry per call: either a `list[RawMatch]` to return, or a `ProviderUnavailable` instance to
    raise. This is how the three-cycle outage the edge case describes is modelled — no HTTP, no
    retry machinery, just the boundary `reconcile.py` is required to consume through the
    `MatchHistoryProvider` Protocol and nothing more concrete than that.
    """

    def __init__(self, scripted: Sequence[list[RawMatch] | ProviderUnavailable]) -> None:
        self._scripted = list(scripted)
        self.calls: list[tuple[int, ...]] = []

    async def recent_matches(self, profile_ids: Sequence[int]) -> list[RawMatch]:
        self.calls.append(tuple(profile_ids))
        outcome = self._scripted.pop(0)
        if isinstance(outcome, ProviderUnavailable):
            raise outcome
        return outcome


def _stage(
    session_factory: async_sessionmaker[AsyncSession],
    provider: FakeMatchHistoryProvider | MatchHistoryProvider,
    *,
    capture_budget_days: int = CAPTURE_BUDGET_DAYS,
    batch_size: int = _DISCOVERY_BATCH_SIZE,
) -> ReconcileStage:
    """Imports `aoe2stats_ingester.reconcile` here, at call time, rather than at module scope —
    see the module docstring: this is the one place every test below reaches the not-yet-existent
    T054 module through, so this is where the `ModuleNotFoundError` is meant to surface, inside
    the test call where `strict=True` xfail turns it into an expected failure.
    """
    from aoe2stats_ingester.reconcile import ReconcileStage

    return ReconcileStage(
        session_factory=session_factory,
        match_history_provider=provider,
        capture_budget_days=capture_budget_days,
        batch_size=batch_size,
    )


async def _seed_consenting_linked_profile(
    db_session: AsyncSession, *, profile_id: int, steam_id64: str
) -> uuid.UUID:
    """One allowlisted, consenting user with one active profile link — the minimum the sweep has
    anything to do for. Mirrors the seeding pattern `apps/api/tests/test_unlink.py` and
    `test_consent.py` already established for these exact models: a `users` row, a
    `steam_identities` row, an `aoe_profiles` row, and the `profile_links` row that ties them
    together, committed so a session on a different connection (the stage's own, opened through
    `session_factory`) can see it.
    """
    now = datetime.now(UTC)
    user = User(id=uuid.uuid4(), created_at=now, allowlisted_at=now)
    db_session.add(user)
    await db_session.flush()

    db_session.add(
        SteamIdentity(steam_id64=steam_id64, user_id=user.id, verified_at=now, last_sign_in_at=now)
    )
    db_session.add(AoeProfile(profile_id=profile_id, alias="Reconciled", country="FR"))
    await db_session.flush()

    db_session.add(
        ProfileLink(
            user_id=user.id,
            profile_id=profile_id,
            steam_id64=steam_id64,
            is_primary=True,
            linked_at=now,
        )
    )
    await db_session.commit()
    return user.id


def _raw_match(*, game_id: int, completed_at: datetime, profile_id: int) -> RawMatch:
    """A minimal but valid `RawMatch` — `raw_payload` carries enough of the shape a real Relic
    entry has (`id`, `matchtype_id`, `completiontime`) for FR-012's verbatim-persistence check
    below to mean something, without needing a full fixture this file has no other use for.
    """
    payload = {
        "id": game_id,
        "matchtype_id": 3,
        "completiontime": completed_at.timestamp(),
    }
    return RawMatch(
        game_id=game_id,
        leaderboard_id=3,
        completed_at=completed_at,
        player_profile_ids=(profile_id,),
        raw_payload=payload,
    )


async def _all_matches(db_session: AsyncSession) -> dict[int, Match]:
    result = await db_session.execute(select(Match))
    return {match.game_id: match for match in result.scalars().all()}


async def _all_captures(db_session: AsyncSession) -> dict[int, ReplayCapture]:
    result = await db_session.execute(select(ReplayCapture))
    return {capture.game_id: capture for capture in result.scalars().all()}


# --- The outage: three failed cycles, then a sweep that recovers everything ---------------------


async def test_reconciliation_sweep_recovers_every_match_missed_during_a_multi_day_outage(
    db_session: AsyncSession, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """`ProviderUnavailable` for three consecutive cycles, with matches completing throughout —
    the fourth, once the source is reachable again, must discover **every** one of them and
    enqueue a capture for each, none of them already past `capture_deadline_at` (FR-013, FR-014):
    a three-day outage against a 21-day budget still leaves ~18 days of margin, which is the whole
    point of sizing the budget the way it is.
    """
    now = datetime.now(UTC)
    profile_id = 900_100
    await _seed_consenting_linked_profile(
        db_session, profile_id=profile_id, steam_id64="76500000000000101"
    )

    missed_matches = [
        _raw_match(game_id=990_001, completed_at=now - timedelta(days=3), profile_id=profile_id),
        _raw_match(game_id=990_002, completed_at=now - timedelta(days=2), profile_id=profile_id),
        _raw_match(game_id=990_003, completed_at=now - timedelta(days=1), profile_id=profile_id),
    ]
    provider = FakeMatchHistoryProvider(
        [
            ProviderUnavailable("boom", provider="relic", endpoint="recent_matches"),
            ProviderUnavailable("boom", provider="relic", endpoint="recent_matches"),
            ProviderUnavailable("boom", provider="relic", endpoint="recent_matches"),
            list(missed_matches),
        ]
    )
    assert isinstance(provider, MatchHistoryProvider)
    stage = _stage(session_factory, provider)

    # Three cycles, each hitting the outage. A stage that cannot reach the discovery source has
    # nothing honest to report for that cycle: the exception propagates rather than being
    # swallowed into an empty success, which is what leaves `ingest_runs.finished_at` null for a
    # run built on top of this stage (FR-024) — the liveness check's whole reason to exist.
    for _ in range(3):
        with pytest.raises(ProviderUnavailable):
            await stage(Budget(seconds=60))
        # Nothing from a failed cycle is left half-written: no `matches` row, no `replay_captures`
        # row, from a call that never got to return normally.
        assert await _all_matches(db_session) == {}
        assert await _all_captures(db_session) == {}

    # The fourth cycle: the source is reachable again, and answers with every match completed
    # across the whole outage.
    report = await stage(Budget(seconds=60))

    assert provider.calls[-1] == (profile_id,)

    stored_matches = await _all_matches(db_session)
    assert set(stored_matches) == {990_001, 990_002, 990_003}
    for raw in missed_matches:
        stored = stored_matches[raw.game_id]
        assert stored.completed_at == raw.completed_at
        # FR-012 / constitution IV: the provider's response is irrecoverable once the match ages
        # out, so the raw payload must survive untouched, not just the fields reconcile parsed.
        assert stored.raw_payload == raw.raw_payload

    stored_captures = await _all_captures(db_session)
    assert set(stored_captures) == {990_001, 990_002, 990_003}
    for raw in missed_matches:
        capture = stored_captures[raw.game_id]
        assert capture.profile_id == profile_id
        assert capture.status == CaptureStatus.PENDING
        assert capture.source == CaptureSource.AUTOMATIC
        expected_deadline = raw.completed_at + timedelta(days=CAPTURE_BUDGET_DAYS)
        assert abs((capture.capture_deadline_at - expected_deadline).total_seconds()) < 1
        # The whole point of the 21-day budget against a 25-day sweep and a several-day outage:
        # nothing the sweep recovers here has already breached its own capture deadline.
        assert capture.capture_deadline_at > datetime.now(UTC)

    # `report` is what `run.py`'s `Stage` protocol expects back — a mapping, not `None` — so a run
    # built on this stage has something to file under its name in `RunReport.stage_reports`.
    assert report is not None
    dict(report)


# --- A match discovery skipped entirely, with no outage in sight --------------------------------


async def test_reconciliation_sweep_picks_up_a_match_discovery_skipped_without_touching_the_rest(
    db_session: AsyncSession, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The narrower case the same mechanism covers even without an outage: a match present at the
    source and simply absent from `matches` — for whatever reason discovery's own bookkeeping
    missed it — is picked up by the very next sweep rather than waiting for a user to notice it
    missing. An ordinary already-known match in the same response must be left exactly as it was:
    the sweep fills a gap, it does not re-touch what discovery already got right, and it must
    never produce a second `replay_captures` row for a match that already has one (FR-018).
    """
    now = datetime.now(UTC)
    profile_id = 900_200
    await _seed_consenting_linked_profile(
        db_session, profile_id=profile_id, steam_id64="76500000000000201"
    )

    already_known = _raw_match(
        game_id=991_001, completed_at=now - timedelta(days=5), profile_id=profile_id
    )
    skipped = _raw_match(
        game_id=991_002, completed_at=now - timedelta(days=4), profile_id=profile_id
    )

    # What an earlier, ordinary discovery cycle would already have left behind for the known
    # match: a `matches` row and an already-`stored` capture. Seeded directly, since this test
    # exercises `reconcile.py` alone and not `discover.py` (T053), which does not exist yet
    # either.
    db_session.add(
        Match(
            game_id=already_known.game_id,
            leaderboard_id=already_known.leaderboard_id,
            completed_at=already_known.completed_at,
            source="relic",
            raw_payload=already_known.raw_payload,
        )
    )
    await db_session.flush()
    stored_at = now - timedelta(days=4)
    db_session.add(
        ReplayCapture(
            game_id=already_known.game_id,
            profile_id=profile_id,
            status=CaptureStatus.STORED,
            capture_deadline_at=already_known.completed_at + timedelta(days=CAPTURE_BUDGET_DAYS),
            stored_at=stored_at,
            object_key="replays/already-known.zip",
            zip_bytes=1234,
            zip_sha256="0" * 64,
            source=CaptureSource.AUTOMATIC,
        )
    )
    await db_session.commit()

    provider = FakeMatchHistoryProvider([[already_known, skipped]])
    stage = _stage(session_factory, provider)

    await stage(Budget(seconds=60))

    stored_matches = await _all_matches(db_session)
    assert set(stored_matches) == {already_known.game_id, skipped.game_id}
    assert stored_matches[already_known.game_id].completed_at == already_known.completed_at
    assert stored_matches[skipped.game_id].completed_at == skipped.completed_at
    assert stored_matches[skipped.game_id].raw_payload == skipped.raw_payload

    stored_captures = await _all_captures(db_session)
    assert set(stored_captures) == {already_known.game_id, skipped.game_id}

    # The already-known match's capture is untouched: still `stored`, same object, same
    # timestamp — the sweep must never rewrite what discovery already archived (FR-018, FR-023).
    untouched = stored_captures[already_known.game_id]
    assert untouched.status == CaptureStatus.STORED
    assert untouched.stored_at == stored_at
    assert untouched.object_key == "replays/already-known.zip"

    # The skipped match now has exactly the pending capture a normal discovery cycle would have
    # produced for it.
    recovered = stored_captures[skipped.game_id]
    assert recovered.profile_id == profile_id
    assert recovered.status == CaptureStatus.PENDING
    expected_deadline = skipped.completed_at + timedelta(days=CAPTURE_BUDGET_DAYS)
    assert abs((recovered.capture_deadline_at - expected_deadline).total_seconds()) < 1


# --- Two consenting participants, one match, two different batches (T054b) ----------------------


class _SharedMatchOnlyForOneParticipantsBatchProvider:
    """A `MatchHistoryProvider` double for the case `discover.py`'s own module docstring names by
    name and `test_shared_match.py` established the rule for: two consenting profiles who share
    one match, each polled in its own batch (`batch_size=1` below), where the source answers with
    the match only for `_answering_profile_id`'s own query — exactly what a source that reports
    whatever it itself considers "recent" per profile does once the match has aged out of the
    other participant's own recent-history window, long before the reconciliation sweep gets to
    it. `test_shared_match.py`'s `_FakeMatchHistoryProvider` is the model this mirrors, membership
    -based rather than call-order-based so it does not depend on `_consenting_profile_ids`'
    unspecified row order.
    """

    def __init__(self, raw_match: RawMatch, *, answering_profile_id: int) -> None:
        self._raw_match = raw_match
        self._answering_profile_id = answering_profile_id
        self.calls: list[tuple[int, ...]] = []

    async def recent_matches(self, profile_ids: Sequence[int]) -> list[RawMatch]:
        self.calls.append(tuple(profile_ids))
        if self._answering_profile_id in profile_ids:
            return [self._raw_match]
        return []


async def test_reconciliation_sweep_enqueues_captures_for_both_participants_across_batches(
    db_session: AsyncSession, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The same hazard `discover.py`'s own comment names for itself, now for the reconciliation
    sweep: two consenting users share one match but land in different batches
    (`ReconcileStage(batch_size=1)`), and the source only returns the match through the first
    participant's own batch. Both consenting participants played it, so the sweep must enqueue a
    capture for both — not only for whichever profile happened to be in the batch that triggered
    the fetch. Before T054b this failed: `batch_profile_ids = set(batch)` saw only the profile that
    triggered the call and enqueued nothing for the other.
    """
    now = datetime.now(UTC)
    profile_a = 900_400
    profile_b = 900_401
    await _seed_consenting_linked_profile(
        db_session, profile_id=profile_a, steam_id64="76500000000000401"
    )
    await _seed_consenting_linked_profile(
        db_session, profile_id=profile_b, steam_id64="76500000000000402"
    )

    shared_match = RawMatch(
        game_id=993_001,
        leaderboard_id=3,
        completed_at=now - timedelta(days=2),
        player_profile_ids=(profile_a, profile_b),
        raw_payload={"id": 993_001, "matchtype_id": 3},
    )
    provider = _SharedMatchOnlyForOneParticipantsBatchProvider(
        shared_match, answering_profile_id=profile_a
    )
    assert isinstance(provider, MatchHistoryProvider)
    # `batch_size=1` is the natural way to force two consenting profiles into different batches —
    # see the module docstring above.
    stage = _stage(session_factory, provider, batch_size=1)

    await stage(Budget(seconds=60))

    # Both batches were actually polled separately.
    assert {profile_a} in [set(call) for call in provider.calls]
    assert {profile_b} in [set(call) for call in provider.calls]

    result = await db_session.execute(
        select(ReplayCapture).where(ReplayCapture.game_id == shared_match.game_id)
    )
    captures = {capture.profile_id: capture for capture in result.scalars().all()}
    assert set(captures) == {profile_a, profile_b}, (
        "Both consenting participants played this match, so both must get a pending "
        "`replay_captures` row from the sweep regardless of which batch's fetch actually "
        "returned it (T054b)."
    )
    for capture in captures.values():
        assert capture.status == CaptureStatus.PENDING
        assert capture.source == CaptureSource.AUTOMATIC
