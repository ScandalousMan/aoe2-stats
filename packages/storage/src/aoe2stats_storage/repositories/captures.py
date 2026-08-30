"""`CapturesRepository` — the write path for a manually supplied replay (T081, FR-029 to FR-033).

`apps/ingester/src/aoe2stats_ingester/capture.py` (T055) owns the write path for an *automatic*
capture — claim, download, validate, mark — and this module deliberately does not duplicate any of
that machinery. A manual upload is a different write ordering entirely (`routers/replays.py`'s own
T080 docstring, once that task lands): the file is validated **before** anything reaches the object
store, so nothing is ever written for an upload that fails well-formedness (FR-030,
`test_manual_upload.py`'s scenario 8.2 — "nothing stored, never even `quarantined`"). By the time
`record_manual_upload` below runs, the router has already: checked the caller played `game_id`
(FR-031), refused a call against an existing `stored` archive (FR-032), uploaded the now-validated
blob to the object store, and run it through the same `ReplayValidator` engine interface the
automatic capture pipeline uses. This method's whole job is the one write that follows all of that
— the row, not the bytes.

**Create-or-update, never a bare insert.** `data-model.md`'s "what this model deliberately does not
have" section rules out a `replays` table separate from `replay_captures` — the intent to capture
and the result of capturing are one row — so a match whose automatic capture already concluded
`expired`/`unavailable`/`failed`/`quarantined` (T078's own scenario 8.1: an `expired` capture,
rescued) has *that* row updated in place rather than gaining a second one alongside it: the
`(game_id, profile_id)` unique constraint (`ReplayCapture.__table_args__`) would refuse a second
row for the same pair outright, and even if it did not, two rows disagreeing about one capture is
exactly the split state that section exists to forbid. Only a match discovery has never enqueued a
row for at all — a capture whose `(game_id, profile_id)` pair discovery never saw, most likely
because the caller linked their account after the match was already outside the automatic
pipeline's own reach — gets a fresh insert.

**`capture_deadline_at` is computed once, at insert, exactly as `discover.py`'s `_enqueue_capture`
computes it for an automatic row (data-model.md: "computed on insert, never recomputed, and never
restated as a literal").** The update branch leaves an existing row's own `capture_deadline_at`
untouched for the identical reason `discover.py` never rewrites it on a rediscovered match: it is
fixed at the budget in effect when the row was first created, and a manual upload rescuing an
already-`expired` row must not quietly extend a deadline that has already passed — the row is
rescued by supplying the bytes, not by moving the goalposts. The insert branch computes it fresh
from `match_completed_at` and `capture_budget_days`, the same two inputs `discover.py` uses, passed
in by the caller rather than read from a setting this package may not import (`repositories/
base.py`'s own module docstring: `packages/storage` takes every tunable as a plain argument,
never `aoe2stats_api.settings.Settings` directly).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from ..models import CaptureSource, CaptureStatus, ReplayCapture
from .base import Repository


class CapturesRepository(Repository):
    """Writes the one `replay_captures` row a manual upload produces or rescues. See the module
    docstring for the write ordering this method assumes has already happened (validate, then
    upload, then this call) and for why create and update share one method rather than two.
    """

    async def record_manual_upload(
        self,
        *,
        game_id: int,
        profile_id: int,
        object_key: str,
        zip_bytes: int,
        zip_sha256: str,
        inner_filename: str,
        inner_bytes: int,
        validated_by: str,
        match_completed_at: datetime,
        capture_budget_days: int,
        stored_at: datetime | None = None,
    ) -> ReplayCapture:
        """Record a manually supplied replay for `(game_id, profile_id)` as `stored`, `source =
        'manual'`, with `validated_by` set to the engine and version that vouched for it — creating
        the row if discovery never enqueued one for this pair, or updating whichever terminal or
        in-flight row already exists (module docstring).

        `stored_at` defaults to "now" (UTC), the moment this write happens — mirrors
        `RatingsRepository.record_snapshot`'s identical default and identical reasoning: the
        caller's own clock is never trusted for a timestamp this repository can produce itself.

        Flushes but never commits, the same discipline `RatingsRepository.record_snapshot` follows:
        this is one unit of work inside whichever `session_scope` (or request-scoped session) the
        caller already opened, and this repository never decides on its own when that unit of work
        ends.
        """
        resolved_stored_at = stored_at if stored_at is not None else datetime.now(UTC)

        result = await self.session.execute(
            select(ReplayCapture).where(
                ReplayCapture.game_id == game_id, ReplayCapture.profile_id == profile_id
            )
        )
        capture = result.scalar_one_or_none()

        if capture is None:
            capture = ReplayCapture(
                game_id=game_id,
                profile_id=profile_id,
                capture_deadline_at=match_completed_at + timedelta(days=capture_budget_days),
            )
            self.session.add(capture)

        capture.status = CaptureStatus.STORED
        capture.source = CaptureSource.MANUAL
        capture.stored_at = resolved_stored_at
        capture.object_key = object_key
        capture.zip_bytes = zip_bytes
        capture.zip_sha256 = zip_sha256
        capture.inner_filename = inner_filename
        capture.inner_bytes = inner_bytes
        capture.validated_by = validated_by
        capture.http_status = 200
        capture.last_error = None

        await self.session.flush()
        return capture
