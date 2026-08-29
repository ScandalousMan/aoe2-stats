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
completed_at, now, capture, recorded_404)` returning an `AvailabilityView(state, obtainable_until)`
— `state` one of `Availability.ARCHIVED / OBTAINABLE / EXPIRED / NEVER_RECORDED`, matching
`contracts/http-api.md`'s four literal strings exactly. `capture` is a `ReplayCapture | None` — the
row for this exact `(game_id, profile_id)` pair, or `None` when this service never attempted to
capture it, which is the normal case for a third party. `recorded_404` is a plain `bool`: the
caller's own evidence, from wherever it was recorded (an analysis fetch that 404'd, for a third
party — T337's job, not this module's), that the source has no recording for this point of view.
T336's task text calls this "a pure function over rows and a clock — no provider, no I/O", which is
exactly why neither parameter is itself a query: whoever calls `derive_availability` has already
fetched the one row that matters and already knows whether a 404 was seen.

**No window-length constant is asserted against anywhere below.** R8's 2026-08-29 amendment leaves
the retention window contradicted and unresolved (`docs/data-sources.md`), and states only that
"the derivation stays conservative and unchanged: a match older than the shortest credible window
renders expired" — without settling what that window's length is. Every `completed_at` below is
therefore chosen to be unambiguous under *any* credible reading: days for "obviously still inside
whatever window T336 picks" and well over a year for "obviously outside it", never a value close
enough to a specific day-count that this file would need to know or restate T336's own constant.
That restraint is the same one `research.md`'s own header states for itself: a number that exists
in two files is wrong in one of them.

**`obtainable_until` is asserted `None` in every state**, not just the two FR-025 already required
it null for. FR-024's 2026-08-29 amendment reads: "that window is contradicted and unresolved ...
so the date MUST be null while the question is open rather than derived from the superseded
reading" — a promise about the future drawn from a window that may not exist is worse than no
promise. Nothing in this file restates the (currently nonexistent) settled window as a value either;
the day this becomes claimable again is a `research.md` R8 decision, not a change owed here.

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


@pytest.mark.xfail(strict=True, reason="T336 not implemented yet")
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
    )

    assert view.state == Availability.ARCHIVED


@pytest.mark.xfail(strict=True, reason="T336 not implemented yet")
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
    )

    assert view.state != Availability.ARCHIVED
    assert view.state == Availability.OBTAINABLE


# --- `obtainable` / `expired`: arithmetic over the match's completion time ----------------------


@pytest.mark.xfail(strict=True, reason="T336 not implemented yet")
def test_obtainable_for_a_recent_match_with_no_capture_and_no_recorded_404() -> None:
    """R8's table: "obtainable now — the match completed inside the retention window." No capture
    row at all is the ordinary shape for a third party this service never automatically captures
    (FR-012)."""
    from aoe2stats_api.availability import Availability, derive_availability

    view = derive_availability(
        completed_at=_RECENT_COMPLETION, now=_NOW, capture=None, recorded_404=False
    )

    assert view.state == Availability.OBTAINABLE


@pytest.mark.xfail(strict=True, reason="T336 not implemented yet")
def test_expired_for_an_ancient_match_with_no_capture_and_no_recorded_404() -> None:
    """R8's table: "expired — the match completed outside it", and the 2026-08-29 amendment: "the
    derivation stays conservative and unchanged: a match older than the shortest credible window
    renders expired" — under either candidate reading of the contradicted measurement."""
    from aoe2stats_api.availability import Availability, derive_availability

    view = derive_availability(
        completed_at=_ANCIENT_COMPLETION, now=_NOW, capture=None, recorded_404=False
    )

    assert view.state == Availability.EXPIRED


# --- `never_recorded`: the one state that needs evidence rather than arithmetic (R8) ------------


@pytest.mark.xfail(strict=True, reason="T336 not implemented yet")
def test_never_recorded_from_explicit_evidence_even_inside_the_window() -> None:
    """R8: "an analysis fetch that 404s inside the window records it for a third party's" — a
    match that is otherwise well inside the window still reports `never_recorded`, not
    `obtainable`, once that evidence exists. A caller who has seen the 404 must never re-offer the
    download as if nothing were known — FR-025 forbids presenting an unobtainable download as an
    action that then fails."""
    from aoe2stats_api.availability import Availability, derive_availability

    view = derive_availability(
        completed_at=_RECENT_COMPLETION, now=_NOW, capture=None, recorded_404=True
    )

    assert view.state == Availability.NEVER_RECORDED


@pytest.mark.xfail(strict=True, reason="T336 not implemented yet")
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
    )

    assert view.state == Availability.NEVER_RECORDED


# --- The `retained_recordings` refusal, asserted behaviourally and structurally -----------------


@pytest.mark.xfail(strict=True, reason="T336 not implemented yet")
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
        completed_at=_ANCIENT_COMPLETION, now=_NOW, capture=None, recorded_404=False
    )

    assert view.state == Availability.EXPIRED
    assert view.state != Availability.ARCHIVED

    parameter_names = set(inspect.signature(derive_availability).parameters)
    assert not any("retained" in name for name in parameter_names), (
        "derive_availability must not accept a retained_recordings row as an input at all (R8) — "
        f"found: {parameter_names}"
    )


# --- `obtainable_until`: null in every state while the window is unresolved (FR-024, 2026-08-29) --


@pytest.mark.xfail(strict=True, reason="T336 not implemented yet")
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
def test_obtainable_until_is_null_in_every_state_while_the_window_is_unresolved(
    completed_at: datetime, capture: ReplayCapture | None, recorded_404: bool
) -> None:
    """FR-024, amended 2026-08-29: "that window is contradicted and unresolved ... so the date
    MUST be null while the question is open rather than derived from the superseded reading." This
    holds for every one of the four states, not only the two `contracts/http-api.md` already
    required it null for — an `archived` or `obtainable` point of view has no honest expiry date to
    state either, for exactly the reason `research.md` R8 gives."""
    from aoe2stats_api.availability import derive_availability

    view = derive_availability(
        completed_at=completed_at, now=_NOW, capture=capture, recorded_404=recorded_404
    )

    assert view.obtainable_until is None


# --- The assertion this file exists for: no outbound request, ever ------------------------------


@pytest.mark.xfail(strict=True, reason="T336 not implemented yet")
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
    )
    derive_availability(completed_at=_RECENT_COMPLETION, now=_NOW, capture=None, recorded_404=False)
    derive_availability(
        completed_at=_ANCIENT_COMPLETION, now=_NOW, capture=None, recorded_404=False
    )
    derive_availability(completed_at=_RECENT_COMPLETION, now=_NOW, capture=None, recorded_404=True)
    derive_availability(
        completed_at=_RECENT_COMPLETION,
        now=_NOW,
        capture=_capture(status=CaptureStatus.UNAVAILABLE),
        recorded_404=False,
    )

    after = await _provider_call_count(db_session)
    assert after == before == 0
