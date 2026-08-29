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

**`obtainable_until` is `None` in every state — FR-024, amended 2026-08-29.** The retention window
`docs/data-sources.md` measures is contradicted and unresolved as of 2026-08-28: a second, equally
sharp sample reads as a fixed epoch six months back rather than the originally measured ~31-day
rolling window, and the two cannot both describe one window. A promise about the future drawn from a
window that may not exist is worse than no promise, so the date this function returns is null while
the question is open, for every state — not only the two `contracts/http-api.md` already required it
null for. This module therefore performs no date arithmetic at all for `obtainable_until`, and no
window-length value feeds it; the day that becomes claimable again is a `research.md` R8 decision to
re-derive it, not a change owed here.

**The `obtainable`/`expired` split still needs one number, and it must be a conservative floor,
never the measurement itself.** R8: "the derivation stays conservative and unchanged: a match
older than the shortest credible window renders expired [...] under either reading that is safe in
the direction FR-025 actually guards — it never presents an unobtainable download as an action
that then fails." Reading that number as `docs/data-sources.md`'s own "approximately 31 days" —
bisected to a ~4 h interval, and itself contradicted there by a second, later sample — offers zero
margin: a match at day 30.9 would still render `obtainable` for a recording that source may already
have discarded, which is exactly the failure FR-025 forbids. Constitution I settles what the floor
must be instead: "Capture runs against a budget strictly shorter than the shortest credible window,
configured (`CAPTURE_BUDGET_DAYS`) and never hard-coded, so a re-measurement changes a setting, not
code." `capture_budget_days` below is that same setting, threaded in by the caller from
`apps/api/src/aoe2stats_api/settings.py`'s `Settings.capture_budget_days` — the identical value
`apps/ingester/src/aoe2stats_ingester/discover.py` already threads for the same reason and the same
number. It is strictly shorter than either contested reading of the retention window, so the
derivation genuinely, rather than only nominally, under-offers: this function is wrong, if at all,
only in the direction of saying `expired` for a recording the source would still serve — never the
reverse — and with margin, not at exact equality. `derive_availability` takes no default for it: a
default would be a hard-coded window under another name, the same restatement this replaces.
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
