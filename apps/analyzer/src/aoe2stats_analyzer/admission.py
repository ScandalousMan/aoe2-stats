"""The three admission gates FR-039 and R7 require before an analysis fetch runs (T359).

`apps/analyzer/tests/test_admission.py` (T358) is this module's specification, written first and
exercised against every function here. Constitution I is a tie-break rule between capture and
analysis when the two compete for the same request budget, quota or execution window, and R7's own
rationale is why each gate below is a condition over rows this system already keeps rather than a
sentence in a spec: "a tie-break rule that lives only in prose is decided by whoever wrote the code
last." Each gate is inspectable in production with a plain `SELECT` — none of the three holds any
in-memory state, matching the same reason `apps/api/src/aoe2stats_api/ratelimit.py`'s counters are
database-backed rather than a module-level dict (constitution XII: no shared process between two
invocations on this platform).

The three gates are independent by construction, and R7 names the direction each protects:

- `deadline_gate_admits` protects the *window* — capture's own backlog. It reads exactly the
  condition `scripts/checks/capture_audit.py`'s `captures_pending_past_deadline` already reads
  against `replay_captures`, so the two can never quietly drift apart on what "pending past
  deadline" means.
- `budget_gate_admits` protects the *source's patience* — analysis's own, smaller daily allowance
  of requests to the replay source, counted from `provider_calls` and scoped to the `aoems`
  provider only. Exhausting it defers analyses; it never writes to, or reads from, anything a
  capture-side process consults.
- `storage_gate_admits` protects the *allowance* — FR-047's retention cap, counted from
  `retained_recordings.zip_bytes` only. A `replay_captures` row's own `zip_bytes` is 001's and is
  never added to this sum (`data-model.md`).

`check_admission` runs the three in that order and reports the first one that blocks. FR-047's own
wire vocabulary names exactly one of the three refusal codes (`analysis_cap_reached`, already
`AlertKind.ANALYSIS_CAP_REACHED`); the other two are not given a wire string by any artifact, so
this module assigns an internal one for each rather than leaving `code` unset — a later caller
(`api/analyze.py`, a subsequent task) is free to translate or pass either straight through.

Every gate takes its threshold as an explicit parameter rather than reading `Settings` itself,
matching the discipline `apps/api/src/aoe2stats_api/ratelimit.py::check_and_increment` and
`apps/api/src/aoe2stats_api/search.py::search_players` already carry: a service function is a pure
function of its inputs, and whichever caller lands in a later task is where the environment gets
read once and passed down. `now` is likewise explicit so no caller here races the real clock.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_storage.models import CaptureStatus, ProviderCall, ReplayCapture, RetainedRecording

#: The replay source's own identifier in `provider_calls`
#: (`packages/providers/src/aoe2stats_providers/aoems/provider.py`). The budget gate counts calls
#: to this provider only — a `provider_calls` row from the unrelated search source (`companion`)
#: never counts against analysis's own allowance.
_AOEMS_PROVIDER = "aoems"

#: The trailing window `ANALYSIS_MAX_SOURCE_REQUESTS_PER_DAY` is measured over — a rolling day
#: ending at `now`, not a calendar day, so a caller never has to reason about which calendar day a
#: call landed in.
_BUDGET_WINDOW = timedelta(days=1)

#: The two `replay_captures.status` values the deadline gate treats as "unstored" — a capture still
#: in flight, not yet resolved one way or another. Mirrors
#: `scripts/checks/capture_audit.py`'s own `_RESOLVED_STATUSES` by naming its complement directly,
#: exactly as `apps/analyzer/tests/test_admission.py` does, rather than restating that tuple here.
_UNSTORED_STATUSES = (CaptureStatus.PENDING, CaptureStatus.DOWNLOADING)

#: FR-047's own wire vocabulary — `AlertKind.ANALYSIS_CAP_REACHED` (T304), the one refusal code an
#: artifact actually names.
_ANALYSIS_CAP_REACHED_CODE = "analysis_cap_reached"

#: Neither artifact nor task text gives the deadline gate's refusal a wire string; this is this
#: module's own internal code, for a caller that wants to log or branch on *why* without inventing
#: one itself.
_CAPTURE_DEADLINE_CONTENTION_CODE = "capture_deadline_contention"

#: Same reasoning as above, for the budget gate's own refusal.
_ANALYSIS_BUDGET_EXHAUSTED_CODE = "analysis_budget_exhausted"


@dataclass(frozen=True)
class AdmissionOutcome:
    """The same shape `apps/api/src/aoe2stats_api/ratelimit.py`'s `RateLimitOutcome` already uses
    for a gate-style check in this codebase. `code` is `None` when `allowed` is `True`.
    """

    allowed: bool
    code: str | None


async def deadline_gate_admits(session: AsyncSession, *, now: datetime) -> bool:
    """`False` while any `replay_captures` row is unstored (`status` in `{pending, downloading}`)
    and its own `capture_deadline_at` has already passed `now` — the exact condition
    `scripts/checks/capture_audit.py`'s `captures_pending_past_deadline` already reads. `True`
    otherwise, including when a capture past its own deadline is already resolved one way or
    another (`stored`, `unavailable`, `expired`, `quarantined`, `failed`): there is nothing left for
    an analysis fetch to compete with.
    """
    result = await session.execute(
        select(ReplayCapture.id)
        .where(
            ReplayCapture.status.in_(_UNSTORED_STATUSES),
            ReplayCapture.capture_deadline_at < now,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is None


async def budget_gate_admits(
    session: AsyncSession, *, now: datetime, max_source_requests_per_day: int
) -> bool:
    """`False` once the count of `provider_calls` rows for the replay source (`provider = "aoems"`)
    in the trailing day (`[now - 1 day, now]`) reaches `max_source_requests_per_day`. `True` below
    it. Scoped to `aoems` specifically, and to the trailing day, not the table's lifetime.
    """
    result = await session.execute(
        select(func.count())
        .select_from(ProviderCall)
        .where(
            ProviderCall.provider == _AOEMS_PROVIDER,
            ProviderCall.called_at >= now - _BUDGET_WINDOW,
            ProviderCall.called_at <= now,
        )
    )
    count = result.scalar_one()
    return count < max_source_requests_per_day


async def storage_gate_admits(session: AsyncSession, *, retention_cap_bytes: int) -> bool:
    """`False` once `SUM(retained_recordings.zip_bytes)` reaches `retention_cap_bytes`. `True`
    below it. `retained_recordings` only — a `replay_captures` row's own `zip_bytes` is 001's and
    must never be added to this sum, however large.
    """
    result = await session.execute(select(func.coalesce(func.sum(RetainedRecording.zip_bytes), 0)))
    total_bytes = result.scalar_one()
    return total_bytes < retention_cap_bytes


async def check_admission(
    session: AsyncSession,
    *,
    now: datetime,
    max_source_requests_per_day: int,
    retention_cap_bytes: int,
) -> AdmissionOutcome:
    """Runs the three gates in R7's own order — deadline, budget, storage — and reports the first
    one that blocks. `allowed=True` only when every gate is open.
    """
    if not await deadline_gate_admits(session, now=now):
        return AdmissionOutcome(allowed=False, code=_CAPTURE_DEADLINE_CONTENTION_CODE)

    if not await budget_gate_admits(
        session, now=now, max_source_requests_per_day=max_source_requests_per_day
    ):
        return AdmissionOutcome(allowed=False, code=_ANALYSIS_BUDGET_EXHAUSTED_CODE)

    if not await storage_gate_admits(session, retention_cap_bytes=retention_cap_bytes):
        return AdmissionOutcome(allowed=False, code=_ANALYSIS_CAP_REACHED_CODE)

    return AdmissionOutcome(allowed=True, code=None)
