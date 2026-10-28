"""`derive_availability` (T336): the four-state view of a recorded game's per-participant
availability that `apps/api/tests/test_replay_availability.py` (T334) is this module's own
specification, and `research.md` R8 and `contracts/http-api.md`'s `replay` object are the
requirements it implements to.

**A pure function over rows and a clock — no provider, no I/O, no database query of its own.**
`docs/data-sources.md` §2 measured `HEAD` answering `405` and `Range` being ignored: there is no
cheap existence probe, so asking the source at all means a full download, and doing that on every
render would be exactly the browsing-driven bulk reading of third-party recordings constitution IX
forbids and FR-012 restates (R8). This module's whole reason to exist is to answer FR-025's four
states from what the caller already knows — a row it already fetched, and the current time — never
from a fresh call. `test_deriving_availability_issues_no_outbound_request` (T334) checks this
against `provider_calls` directly: calling `derive_availability`, in every state, leaves that table
exactly as empty as it started.

**The four states, derived (R8's table):**

| State            | Derived from                                                              |
| ---------------- | -------------------------------------------------------------------------- |
| `archived`       | a `replay_captures` row in `stored` — that row only, any age (FR-026)     |
| `never_recorded` | `recorded_404`, or a `replay_captures` row in `unavailable`               |
| `obtainable`     | no evidence either way, and completed inside `capture_budget_days`       |
| `expired`        | no evidence either way, and completed outside it                         |

**A `retained_recordings` row is not an input, and cannot become one by accident.** R8, decided
2026-08-23 and strengthened by constitution IX 4.0.0: a match whose only surviving copy is a
`retained_recordings` row still renders `expired`, with an analysis available — handing those bytes
to any signed-in caller would redistribute a third party's public-basis recording with no legal
basis for doing so. `derive_availability` is given no session and no query, so it cannot reach that
table regardless of what its caller holds; its parameter list carries nothing that names it either,
which is what makes that refusal structural rather than a discipline an implementer has to remember
(`test_a_retained_recording_never_yields_archived_and_is_not_a_parameter`, T334, inspects the
signature itself for exactly this).

**`obtainable_until` is `None` in every state — FR-024, amended 2026-08-29, re-derived 2026-10-27.**
A date would be a promise about how long the source keeps one point of view, and that length is
the window of that profile. `docs/data-sources.md` §2 records the window as rolling, as different
from one profile to another, as moving from day to day, and as set by nothing known, so no date
can be derived that the source will honour. `capture_budget_days` is a capture setting this
project chose, not the source's deadline; publishing it as a date would present the setting as the
source's promise. The field is therefore null for every state, this module performs no date
arithmetic for it, and no window-length value feeds it. A date becomes claimable under the
condition constitution I sets for widening the budget: `docs/data-sources.md` records as settled
what sets a profile's window. History: the 2026-08-29 amendment gave the open window-length
question (a fixed epoch against a rolling window) as the reason; that question is settled and is
no longer the cause.

**The `obtainable`/`expired` split still needs one number, and it must be a conservative floor,
never the measurement itself.** FR-025 guards one direction: the derivation should not present an
unobtainable download as an action that then fails. That holds for every profile measured
(`docs/data-sources.md` §2) and not beyond it. Constitution I settles what the floor must be:
"Capture runs against a budget strictly shorter than the shortest window measured on any profile,
configured (`CAPTURE_BUDGET_DAYS`) and never hard-coded, so a re-measurement changes a setting, not
code." `capture_budget_days` below is that same setting, threaded in by the caller from
`apps/api/src/aoe2stats_api/settings.py`'s `Settings.capture_budget_days` — the identical value
`apps/ingester/src/aoe2stats_ingester/discover.py` already threads for the same reason. For
every profile measured, this function is wrong, if at all, only in the direction of saying
`expired` for a recording the source would still serve, which `docs/data-sources.md` §2 records as
possible for a profile whose window is longer than the budget. The reverse is possible for a
profile whose window is shorter than the budget, if one exists (§2 says a more active profile than
any measured may have one): it would see `obtainable` for a purged recording.
`derive_availability` takes no default for it: a default would be a hard-coded window under
another name.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime, timedelta

from aoe2stats_storage.models import CaptureStatus, ReplayCapture


class Availability(enum.StrEnum):
    """`contracts/http-api.md`'s four literal `availability` values, exactly."""

    ARCHIVED = "archived"
    OBTAINABLE = "obtainable"
    EXPIRED = "expired"
    NEVER_RECORDED = "never_recorded"


@dataclass(frozen=True)
class AvailabilityView:
    """One participant's point of view, as `GET /api/matches/{game_id}`'s `replay` object states
    it (T338 wires this in). `obtainable_until` is `None` in every state — see the module
    docstring's FR-024 paragraph; it is carried here, rather than dropped, because the contract
    still names the field and a later change may give it a value again without widening this
    shape."""

    state: Availability
    obtainable_until: datetime | None


def derive_availability(
    *,
    completed_at: datetime,
    now: datetime,
    capture: ReplayCapture | None,
    recorded_404: bool,
    capture_budget_days: int,
) -> AvailabilityView:
    """FR-025's four states, from rows the caller already has and nothing else.

    `capture` is the `replay_captures` row for this exact `(game_id, profile_id)` pair, or `None`
    when this service never attempted to capture it — the normal case for a third party (FR-012).
    `recorded_404` is the caller's own evidence, from wherever it was recorded, that the source has
    answered 404 for this point of view; T337 is what records it, not this function.
    `capture_budget_days` is the caller's own `Settings.capture_budget_days`
    (`CAPTURE_BUDGET_DAYS`) — the module docstring's closing paragraph is why this must be that
    setting and not a literal: it is required, with no default, so a value can only ever come from
    configuration.

    Order matters and is R8's own: `archived` is checked first because it holds regardless of the
    match's age (FR-026) and must never fall through to a time comparison; `never_recorded` is
    checked next because it is evidence, not arithmetic, and evidence overrides a match that would
    otherwise still read as comfortably inside the window (`recorded_404` and `UNAVAILABLE` both
    hold even for a recent match); only then does the remaining case fall to the one arithmetic
    comparison this function makes.
    """
    if capture is not None and capture.status is CaptureStatus.STORED:
        return AvailabilityView(state=Availability.ARCHIVED, obtainable_until=None)

    if recorded_404 or (capture is not None and capture.status is CaptureStatus.UNAVAILABLE):
        return AvailabilityView(state=Availability.NEVER_RECORDED, obtainable_until=None)

    if now - completed_at > timedelta(days=capture_budget_days):
        return AvailabilityView(state=Availability.EXPIRED, obtainable_until=None)

    return AvailabilityView(state=Availability.OBTAINABLE, obtainable_until=None)
