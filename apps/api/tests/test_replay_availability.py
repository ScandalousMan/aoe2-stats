"""Tests for the availability derivation (T336), `apps/api/src/aoe2stats_api/availability.py` —
`research.md` R8 and `contracts/http-api.md`'s per-participant `replay` object: `"availability":
"archived" | "obtainable" | "expired" | "never_recorded"`.

`aoe2stats_api.availability` does not exist until T336 lands, so every test below carries
`@pytest.mark.xfail(strict=True, reason="T336 not implemented yet")` per CLAUDE.md's test-first
convention, and imports the module inside its own body rather than at module scope — a
module-scope import of a module that does not exist yet is a collection error that takes the
whole workspace suite down, which is a different and worse failure than an expected xfail.

**The interface under test is designed here, not merely exercised**, following the shape T307's
own first test file (`test_rate_limits.py`) used for the same reason: `derive_availability(*,
completed_at, now, capture, recorded_404, capture_budget_days)` returning an
`AvailabilityView(state, obtainable_until)` — `state` one of `Availability.ARCHIVED / OBTAINABLE /
EXPIRED / NEVER_RECORDED`, matching `contracts/http-api.md`'s four literal strings exactly.
`capture` is a `ReplayCapture | None` — the row for this exact `(game_id, profile_id)` pair, or
`None` when this service never attempted to capture it, which is the normal case for a third
party. `recorded_404` is a plain `bool`: the caller's own evidence, from wherever it was recorded
(an analysis fetch that 404'd, for a third party — T337's job, not this module's), that the source
has no recording for this point of view. `capture_budget_days` is the caller's own
`Settings.capture_budget_days` (`CAPTURE_BUDGET_DAYS`) — required, with no default, so this
module never falls back to an undeclared window of its own (see the dedicated section below). T336's
task text calls this "a pure function over rows and a clock — no provider, no I/O", which is
exactly why none of the parameters is itself a query: whoever calls `derive_availability` has
already fetched the one row that matters, already knows whether a 404 was seen, and already read
its own configured budget.

**No window-length constant is asserted against `derive_availability`'s own arithmetic anywhere
below**, only against the parameter it is given. `docs/data-sources.md` §2 records the retention
window as rolling and different per profile, and gives no length that holds for every profile.
(History, 2026-08-29: R8's amendment, written while the window was recorded as contradicted, kept
the expired split conservative without giving the window a length.) The module this fix landed in
owns no constant claiming one. Most `completed_at` values below are therefore chosen to be
unambiguous regardless of `capture_budget_days`: days for "obviously still inside whatever budget
the caller supplies" and well over a year for "obviously outside it". The one exception is the
dedicated `capture_budget_days` section below, where `_CAPTURE_BUDGET_DAYS` mirrors `.env.example`'s
own `CAPTURE_BUDGET_DAYS=18` — supplied as any caller would, through the parameter, never restated
as an assertion about what `derive_availability` computes internally. That restraint is the same one
`research.md`'s own header states for itself: a number that exists in two files is wrong in one of
them.

**`obtainable_until` is asserted `None` in every state**, not just the two FR-025 already required
it null for. FR-024, re-derived 2026-10-27 (T823), gives the reason: the window belongs to each
profile and no date can be derived that the source will honour, so the date stays null in every
state until `docs/data-sources.md` records as settled what sets a profile's window. (History: the
2026-08-29 amendment gave "that window is contradicted and unresolved" as the reason; that wording
is superseded.) Nothing in this file restates a window as a value either; the day a date becomes
claimable is a `research.md` R8 decision, not a change owed here.

**A `retained_recordings` row is not an input, asserted two ways.** Behaviourally: a match whose
only surviving copy is a `retained_recordings` row (no `replay_captures` row, no other evidence)
still renders `expired`, never `archived` — R8's own words: "a match whose only copy is retained
renders as `expired` with an analysis available", because handing those bytes to any signed-in
caller would redistribute a third party's public-basis recording with no legal basis for doing so.
Structurally: `derive_availability`'s own parameter names are inspected and none of them may
mention "retained" — a keyword argument would be the shape an implementer reaches for first if they
decided to "helpfully" wire one in, and this makes that impossible to do by accident rather than
merely inadvisable, the same discipline `data-model.md` applies to the schema itself (R9).

**The assertion this file exists for**: deriving availability issues no outbound request at all.
`docs/data-sources.md` §2 measured `HEAD` answering `405` and `Range` being ignored, so there is no
cheap existence probe — asking the source at all means a full download, and doing that on every
render would be exactly the browsing-driven bulk reading of third-party recordings constitution IX
forbids and FR-012 restates. This is checked against the real `provider_calls` table (the "provider
call sink" T334's task text names), the same evidence `test_player_search.py`'s
`_provider_call_count` helper is checked against for FR-004e's cache and the same table
`packages/providers`' `AsyncBaseProvider` writes a row to on every call it makes: if
`derive_availability` ever grows a code path that reaches a provider, that row would land here, in
the one table every outbound call in this codebase is required to leave evidence in.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aoe2stats_storage.models import (
    CaptureSource,
    CaptureStatus,
    Match,
    ProviderCall,
    ReplayCapture,
    RetainedRecording,
)

# An epoch-aligned instant, exactly like `test_rate_limits.py`'s own `_WINDOW_ORIGIN`: every
# `completed_at` below is expressed as an offset from it, so no test here races real time.
_NOW = datetime(2026, 1, 1, tzinfo=UTC)

_GAME_ID = 500546441
_PROFILE_ID = 196240

# Comfortably inside any credible reading of the retention window — see the module docstring's
# paragraph on why no test here needs to know T336's own constant.
_RECENT_COMPLETION = _NOW - timedelta(days=5)

# Well over a year old: outside every credible reading this feature has measured, without landing
# near any specific day-count T336 might choose.
_ANCIENT_COMPLETION = _NOW - timedelta(days=400)


def _capture(
    *, status: CaptureStatus, capture_deadline_at: datetime = _NOW + timedelta(days=16)
) -> ReplayCapture:
    """An in-memory `ReplayCapture` row, never flushed: `derive_availability` is pure over rows
    already fetched by its caller, so this file never needs a database to construct one."""
    return ReplayCapture(
        game_id=_GAME_ID,
        profile_id=_PROFILE_ID,
        status=status,
        capture_deadline_at=capture_deadline_at,
        source=CaptureSource.AUTOMATIC,
    )


async def _provider_call_count(db_session: AsyncSession) -> int:
    result = await db_session.execute(select(func.count()).select_from(ProviderCall))
    return result.scalar_one()


# --- `archived`: a `replay_captures` row in `stored`, and only that -----------------------------


def test_archived_comes_only_from_a_stored_capture_row_regardless_of_match_age() -> None:
    """R8's table: "held in this service's archive — a `replay_captures` row in `stored` — that
    row only." FR-026: served regardless of the match's age, so an ancient completion still
    reports `archived` rather than falling through to `expired`."""
    from aoe2stats_api.availability import Availability, derive_availability

    view = derive_availability(
        completed_at=_ANCIENT_COMPLETION,
        now=_NOW,
        capture=_capture(status=CaptureStatus.STORED),
        recorded_404=False,
        capture_budget_days=_CAPTURE_BUDGET_DAYS,
    )

    assert view.state == Availability.ARCHIVED


@pytest.mark.parametrize(
    "status",
    [
        CaptureStatus.PENDING,
        CaptureStatus.DOWNLOADING,
        CaptureStatus.FAILED,
        CaptureStatus.QUARANTINED,
    ],
)
def test_a_capture_row_that_is_not_stored_does_not_yield_archived(
    status: CaptureStatus,
) -> None:
    """ "That row only" (R8): a capture row exists but has not reached `stored` — the bytes are not
    actually held yet, or never were, so this must not read as `archived`. A recent completion with
    no stored bytes falls through to `obtainable`, the same as no capture row at all."""
    from aoe2stats_api.availability import Availability, derive_availability

    view = derive_availability(
        completed_at=_RECENT_COMPLETION,
        now=_NOW,
        capture=_capture(status=status),
        recorded_404=False,
        capture_budget_days=_CAPTURE_BUDGET_DAYS,
    )

    assert view.state != Availability.ARCHIVED
    assert view.state == Availability.OBTAINABLE


# --- `obtainable` / `expired`: arithmetic over the match's completion time ----------------------


def test_obtainable_for_a_recent_match_with_no_capture_and_no_recorded_404() -> None:
    """R8's table: "obtainable now — the match completed inside the retention window." No capture
    row at all is the ordinary shape for a third party this service never automatically captures
    (FR-012)."""
    from aoe2stats_api.availability import Availability, derive_availability

    view = derive_availability(
        completed_at=_RECENT_COMPLETION,
        now=_NOW,
        capture=None,
        recorded_404=False,
        capture_budget_days=_CAPTURE_BUDGET_DAYS,
    )

    assert view.state == Availability.OBTAINABLE


def test_expired_for_an_ancient_match_with_no_capture_and_no_recorded_404() -> None:
    """R8's table: "expired — the match completed outside it" (the capture budget). A match far
    older than any budget a caller could configure renders expired whatever the source's window
    is for any profile. (History, 2026-08-29: R8 first stated this against two candidate readings
    of a window then recorded as contradicted.)"""
    from aoe2stats_api.availability import Availability, derive_availability

    view = derive_availability(
        completed_at=_ANCIENT_COMPLETION,
        now=_NOW,
        capture=None,
        recorded_404=False,
        capture_budget_days=_CAPTURE_BUDGET_DAYS,
    )

    assert view.state == Availability.EXPIRED


# --- `never_recorded`: the one state that needs evidence rather than arithmetic (R8) ------------


def test_never_recorded_from_explicit_evidence_even_inside_the_window() -> None:
    """R8: "an analysis fetch that 404s inside the window records it for a third party's" — a
    match that is otherwise well inside the window still reports `never_recorded`, not
    `obtainable`, once that evidence exists. A caller who has seen the 404 must never re-offer the
    download as if nothing were known — FR-025 forbids presenting an unobtainable download as an
    action that then fails."""
    from aoe2stats_api.availability import Availability, derive_availability

    view = derive_availability(
        completed_at=_RECENT_COMPLETION,
        now=_NOW,
        capture=None,
        recorded_404=True,
        capture_budget_days=_CAPTURE_BUDGET_DAYS,
    )

    assert view.state == Availability.NEVER_RECORDED


def test_never_recorded_from_the_callers_own_unavailable_capture_row() -> None:
    """R8: "1 records exactly this outcome on `replay_captures` for a user's own matches" —
    `CaptureStatus.UNAVAILABLE` is 001's own recorded 404 for the point of view this service tried
    to capture automatically, and it must read as `never_recorded` even with no separate
    `recorded_404` flag set, and even inside the window."""
    from aoe2stats_api.availability import Availability, derive_availability

    view = derive_availability(
        completed_at=_RECENT_COMPLETION,
        now=_NOW,
        capture=_capture(status=CaptureStatus.UNAVAILABLE),
        recorded_404=False,
        capture_budget_days=_CAPTURE_BUDGET_DAYS,
    )

    assert view.state == Availability.NEVER_RECORDED


# --- The `retained_recordings` refusal, asserted behaviourally and structurally -----------------


async def test_a_retained_recording_never_yields_archived_and_is_not_a_parameter(
    db_session: AsyncSession,
) -> None:
    """Decided 2026-08-23, strengthened 3.0.0 (R8): "a `retained_recordings` row is not an
    archive for this purpose ... it is refused". A match whose only surviving bytes are a
    `retained_recordings` row — no `replay_captures` row for this caller, no other evidence —
    still renders `expired`, exactly what R8 states in its own words: "a match whose only copy is
    retained renders as `expired` with an analysis available". Handing those bytes to any
    signed-in caller would redistribute a third party's public-basis recording with no basis for
    doing so.

    The `retained_recordings` row below is persisted for the *same* `(game_id, profile_id)` this
    test derives availability for, precisely so that a derivation reaching for it by accident — a
    join, a lazy `SELECT` — would have something to find. `derive_availability` is never given a
    session or a query, so it structurally cannot reach it regardless; the row exists to make that
    fact meaningful rather than vacuous.
    """
    from aoe2stats_api.availability import Availability, derive_availability

    # `retained_recordings.game_id` is a foreign key to `matches.game_id` (data-model.md), so a row
    # for `_GAME_ID` must exist first — mirroring `test_match_detail.py`'s own `_seed_match`, kept
    # inline here since this file's only other use of the database is this one test.
    db_session.add(
        Match(
            game_id=_GAME_ID,
            leaderboard_id=3,
            completed_at=_ANCIENT_COMPLETION,
            source="relic",
            raw_payload={"matchHistoryId": _GAME_ID},
        )
    )
    db_session.add(
        RetainedRecording(
            game_id=_GAME_ID,
            profile_id=_PROFILE_ID,
            object_key=f"retained/{_GAME_ID}/{_PROFILE_ID}",
            zip_bytes=871_503,
            zip_sha256="0" * 64,
        )
    )
    await db_session.flush()

    view = derive_availability(
        completed_at=_ANCIENT_COMPLETION,
        now=_NOW,
        capture=None,
        recorded_404=False,
        capture_budget_days=_CAPTURE_BUDGET_DAYS,
    )

    assert view.state == Availability.EXPIRED
    assert view.state != Availability.ARCHIVED

    parameter_names = set(inspect.signature(derive_availability).parameters)
    assert not any("retained" in name for name in parameter_names), (
        "derive_availability must not accept a retained_recordings row as an input at all (R8) — "
        f"found: {parameter_names}"
    )


# --- `obtainable_until`: null in every state, the window being per profile (FR-024, T823) -------


@pytest.mark.parametrize(
    ("completed_at", "capture", "recorded_404"),
    [
        pytest.param(
            _ANCIENT_COMPLETION, _capture(status=CaptureStatus.STORED), False, id="archived"
        ),
        pytest.param(_RECENT_COMPLETION, None, False, id="obtainable"),
        pytest.param(_ANCIENT_COMPLETION, None, False, id="expired"),
        pytest.param(_RECENT_COMPLETION, None, True, id="never_recorded"),
    ],
)
def test_obtainable_until_is_null_in_every_state_because_the_window_belongs_to_each_profile(
    completed_at: datetime, capture: ReplayCapture | None, recorded_404: bool
) -> None:
    """FR-024, re-derived 2026-10-27 (T823): the date stays null because the window belongs to each
    profile and no date can be derived that the source will honour. This holds for every one of the
    four states, not only the two `contracts/http-api.md` already required it null for — an
    `archived` or `obtainable` point of view has no honest expiry date to state either, for
    exactly the reason `research.md` R8 gives. (History: the 2026-08-29 amendment gave an
    unresolved window as the reason.)"""
    from aoe2stats_api.availability import derive_availability

    view = derive_availability(
        completed_at=completed_at,
        now=_NOW,
        capture=capture,
        recorded_404=recorded_404,
        capture_budget_days=_CAPTURE_BUDGET_DAYS,
    )

    assert view.obtainable_until is None


# --- `capture_budget_days`: the window comes from configuration, never a module constant --------

#: Mirrors `.env.example`'s `CAPTURE_BUDGET_DAYS=18` default, exactly as `apps/ingester/tests/
#: test_backfill.py`, `test_idempotency.py`, `test_reconcile.py` and `test_shared_match.py`
#: already mirror it for the identical number. Supplied here as any caller would — through the
#: parameter — never restated as this module's own threshold.
_CAPTURE_BUDGET_DAYS = 18


def test_derive_availability_requires_capture_budget_days_with_no_default() -> None:
    """`derive_availability` previously owned `_SHORTEST_CREDIBLE_WINDOW = timedelta(days=31)` —
    not a derived floor but the exact `docs/data-sources.md` measurement (itself contradicted
    there 2026-08-28) restated as a literal, with zero margin. The window is a required
    keyword-only parameter instead, so a value can only ever come from the caller —
    `apps/api/src/aoe2stats_api/settings.py`'s `Settings.capture_budget_days`
    (`CAPTURE_BUDGET_DAYS`, `.env.example`), the same setting `apps/ingester/src/
    aoe2stats_ingester/discover.py` already threads for the identical number (constitution I: "a
    re-measurement changes a setting, not code"). A default here would reopen exactly that hole
    by letting this module silently fall back to a hard-coded window, so this asserts there is
    none."""
    from aoe2stats_api.availability import derive_availability

    parameters = inspect.signature(derive_availability).parameters
    assert "capture_budget_days" in parameters, (
        "derive_availability must take capture_budget_days as an explicit parameter — the window "
        "must come from the caller, never a module-owned constant"
    )
    assert parameters["capture_budget_days"].default is inspect.Parameter.empty, (
        "capture_budget_days must have no default; a default would let this module fall back to "
        "an undeclared, hard-coded window instead of the caller's configured value"
    )


def test_the_obtainable_expired_split_moves_only_with_capture_budget_days() -> None:
    """The parameter is not decorative: the identical `completed_at` renders `expired` under one
    `capture_budget_days` and `obtainable` under a wider one, with nothing else about the call
    changing. This is what makes a `docs/data-sources.md` re-measurement a matter of changing
    `CAPTURE_BUDGET_DAYS` — a setting — rather than editing this module, exactly the property
    constitution I states for this number."""
    from aoe2stats_api.availability import Availability, derive_availability

    completed_at = _NOW - timedelta(days=25)

    narrower = derive_availability(
        completed_at=completed_at,
        now=_NOW,
        capture=None,
        recorded_404=False,
        capture_budget_days=_CAPTURE_BUDGET_DAYS,
    )
    wider = derive_availability(
        completed_at=completed_at,
        now=_NOW,
        capture=None,
        recorded_404=False,
        capture_budget_days=40,
    )

    assert narrower.state == Availability.EXPIRED
    assert wider.state == Availability.OBTAINABLE


def test_the_configured_budget_leaves_real_margin_under_the_shortest_measured_reading() -> None:
    """R8 (2026-08-29 amendment) claims the derivation under-offers. That was false at the boundary
    as previously coded: a constant equal to a measured window offers zero margin, so a match at
    the boundary rendered `obtainable` for a recording that may already be gone.

    `_CAPTURE_BUDGET_DAYS` (18, mirroring `.env.example`) is configured shorter than the shortest
    retention window measured on any profile (`docs/data-sources.md` §2: the window is rolling and
    differs per profile), with room to spare: a match completed 25 days ago can sit inside the
    source's window, and still renders `expired` once the configured budget is applied, precisely
    the margin the old, unconfigured constant had none of. The margin holds for every profile
    measured and not beyond; for a profile whose window is shorter than the budget, if one exists,
    the same match would read `obtainable` for a purged recording. Nothing here asserts what
    `derive_availability` computes equals `timedelta(days=_CAPTURE_BUDGET_DAYS)` — a fixed day-count
    check on this module's own math would recreate the defect being fixed one layer up; this instead
    pins that the configured value is what decides the split, and that this configured value is
    shorter than the test's own match age."""
    from aoe2stats_api.availability import Availability, derive_availability

    # Inside the shortest window measured (docs/data-sources.md §2) with days to spare, yet
    # outside the configured budget.
    match_age_days = 25
    completed_at = _NOW - timedelta(days=match_age_days)
    assert match_age_days > _CAPTURE_BUDGET_DAYS, (
        "this test needs the configured budget to be shorter than its own match age, or the match "
        "would not fall outside the budget"
    )

    view = derive_availability(
        completed_at=completed_at,
        now=_NOW,
        capture=None,
        recorded_404=False,
        capture_budget_days=_CAPTURE_BUDGET_DAYS,
    )

    assert view.state == Availability.EXPIRED


# --- The assertion this file exists for: no outbound request, ever ------------------------------


async def test_deriving_availability_issues_no_outbound_request(db_session: AsyncSession) -> None:
    """T336's own task text: "a pure function over rows and a clock — no provider, no I/O". Every
    provider this codebase owns writes one `provider_calls` row per attempt through its shared
    call sink (`packages/providers/src/aoe2stats_providers/base.py`'s `AsyncBaseProvider`,
    `ingest_stages.py`'s own docstring, `test_player_search.py`'s `_provider_call_count`) — the
    same table `constitution III`'s "a `provider_calls` record of every call" names. Calling
    `derive_availability` across every state FR-025 defines, including the two states research.md
    R8 says are tempting to "helpfully" verify with a probe (`obtainable`, `never_recorded`), must
    leave that table exactly as empty as it started: `HEAD` answers `405` and `Range` is ignored
    (`docs/data-sources.md` §2), so any probe at all would be a full download, and probing on
    render would be the browsing-driven bulk reading of third-party recordings constitution IX
    forbids and FR-012 restates.
    """
    from aoe2stats_api.availability import derive_availability

    before = await _provider_call_count(db_session)
    assert before == 0

    derive_availability(
        completed_at=_ANCIENT_COMPLETION,
        now=_NOW,
        capture=_capture(status=CaptureStatus.STORED),
        recorded_404=False,
        capture_budget_days=_CAPTURE_BUDGET_DAYS,
    )
    derive_availability(
        completed_at=_RECENT_COMPLETION,
        now=_NOW,
        capture=None,
        recorded_404=False,
        capture_budget_days=_CAPTURE_BUDGET_DAYS,
    )
    derive_availability(
        completed_at=_ANCIENT_COMPLETION,
        now=_NOW,
        capture=None,
        recorded_404=False,
        capture_budget_days=_CAPTURE_BUDGET_DAYS,
    )
    derive_availability(
        completed_at=_RECENT_COMPLETION,
        now=_NOW,
        capture=None,
        recorded_404=True,
        capture_budget_days=_CAPTURE_BUDGET_DAYS,
    )
    derive_availability(
        completed_at=_RECENT_COMPLETION,
        now=_NOW,
        capture=_capture(status=CaptureStatus.UNAVAILABLE),
        recorded_404=False,
        capture_budget_days=_CAPTURE_BUDGET_DAYS,
    )

    after = await _provider_call_count(db_session)
    assert after == before == 0
