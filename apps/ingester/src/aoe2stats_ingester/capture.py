"""The capture drain (T055): claim, download, store, checksum, validate, mark.

The third of the three stages `run.py` drains in order (discover, reconcile, drain). This module
is deliberately the only one in `apps/ingester` that ever loads a replay-validation engine
(constitution V: the API must never load one, and `core` holds the `ReplayValidator` Protocol and
nothing else replay-related).

**The one ordering that is not negotiable** (`tasks.md`, data-model.md's write-ordering
paragraph): a downloaded blob is uploaded to the object store, and *only once that upload has
succeeded* are `object_key`, `zip_bytes` and `zip_sha256` committed to the row — while its status
is still `downloading`. Validation runs after that commit, never before it, and the status only
ever flips to `stored` or `quarantined` once validation has run (or, for a resumed reclaim, once
its outcome has been decided not to be re-attempted — see below). A process that dies between the
upload and the status flip leaves bytes that are already durable and already recorded; the next
run's reclaim resumes from there instead of losing anything or re-fetching a replay it already
holds. `test_interruption.py`'s `test_the_blob_is_durably_written_before_the_row_is_ever_marked_
stored` is what a mark-then-upload regression would fail.

**Containment (constitution V).** `aoe2rec-py`'s PyO3 bridge can raise `pyo3_runtime.
PanicException`, which — per `aoe2stats_core.replay.validation`'s own docstring — inherits
`BaseException` directly, not `Exception`, and is deliberately left unwrapped by that Protocol for
exactly this module to catch. `_validate_with_barrier` below is the barrier: it runs the (always
synchronous, potentially blocking) `ReplayValidator.validate` call in a worker thread via
`asyncio.to_thread` and races it against `validation_timeout_seconds` with `asyncio.wait_for`.
A blocking native call cannot honour cooperative cancellation, so only a wall-clock cap — not a
polite request to stop — can contain a hang; the thread that timed out is abandoned rather than
killed (Python cannot kill a running thread), but this coroutine returns regardless, which is what
`test_quarantine.py`'s hang scenarios assert on directly. Every outcome other than a clean
`ReplayValidationResult` — an ordinary `MalformedArchiveError`/`EngineParseError`, an
uncaught native panic, or a timeout — is folded into the same `quarantined` outcome with
`last_error` set: no exception ever leaves `CaptureDrain.__call__`, which is the property
constitution V and this module's own containment paragraph require.

**The reclaim path's one known gap.** A stale `downloading` row that already carries
`object_key`/`zip_sha256` (the previous run committed the blob and was killed before validation
ever ran, or before the status flip) is resumed *without* re-downloading — `AoemsReplayProvider`
is never called for it. It is, however, also resumed without re-running validation: `ObjectStore`
(`packages/storage/src/aoe2stats_storage/objects.py`) exposes `put`, `signed_get_url`, `delete`
and `list_keys`, and deliberately no `get` — there is no supported way to read the bytes back into
this process to hand them to the engine a second time. The row is therefore marked `stored`
directly, on the strength of the checksum already verified and committed by the run that first
wrote it. Widening `ObjectStore` with a download method is a genuine future improvement, not this
task's to make (it is outside `capture.py`, the one file this task may touch); until then, this is
the honest boundary of what "resumes at validation" can mean without it.

**Rate limiting is delegated, not reimplemented** (T052, `ratelimit.py`): each claimed batch is
handed to `drain_with_rate_limit_guard`, which calls this module's own per-capture handler
serially and, the moment `ProviderRateLimited` is raised, alerts once and stops the whole batch —
never the one capture it fired on. `CaptureDrain` only supplies the handler and reacts to whether
the guard reports it stopped early.

**The three-way 404 reading is a seam, not this task's job** (T056). `AoemsReplayProvider`
answers `NotFound` rather than raising, and does not itself classify what a 404 means —
"not yet published", "genuinely never recorded", or "past the retention window" all produce the
identical wire condition, and only a caller holding `matches.completed_at` can tell them apart
(`contracts/providers.md`). Until that classification lands, a `NotFound` here is read the only
way that never destroys anything: the row reverts to `pending` and is picked up again on a later
cycle, and none of `unavailable_total`/`expired_total`/`failed_total` is ever incremented by this
module — data-model.md's state machine calls a non-zero `expired_total` the one thing that "must
never happen", and reverting to `pending` on every 404, without ever concluding otherwise, is what
keeps that vacuously true here.

**Why this module exports three names for one class.** `test_interruption.py` (T044),
`test_quarantine.py` (T047a) and `test_deadline_order.py` (T045) each committed to this module's
shape independently, before this task landed, and named it `CaptureStage`, `CaptureDrain` and
`DrainStage` respectively, with three overlapping-but-not-identical constructor signatures (see
each test file's own module docstring for its reasoning). `test_quarantine.py`'s `CaptureDrain` is
the name `test_backfill.py` (T043) also settles on for the same not-yet-existent class, so it is
the canonical one; `CaptureStage` and `DrainStage` are aliases of it, and its constructor accepts
every keyword argument any of the four test files passes, with defaults for whichever subset a
given caller omits — never a second, divergent implementation.
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_core.alerting import AlertRecord, AlertSink, raise_alert
from aoe2stats_core.replay.validation import ReplayValidationResult, ReplayValidator
from aoe2stats_ingester.budget import Budget
from aoe2stats_ingester.ratelimit import drain_with_rate_limit_guard
from aoe2stats_providers.base import NotFound, ReplayBlob, ReplayProvider
from aoe2stats_storage.models import CaptureStatus, ReplayCapture
from aoe2stats_storage.objects import REPLAY_CONTENT_TYPE, replay_object_key

#: `alerts.kind` for a quarantine (`AlertKind.VALIDATION_FAILED` in
#: `packages/storage/src/aoe2stats_storage/models.py`, named here as a plain string for the same
#: reason `ratelimit.py`'s `RATE_LIMITED_ALERT_KIND` is: `AlertSink.write` takes a plain `str`,
#: and `apps/ingester` needs no dependency on `aoe2stats_storage` merely to spell one.
VALIDATION_FAILED_ALERT_KIND = "validation_failed"

#: Severity 2, never 1: a quarantined capture still holds the bytes (constitution IV — evidence,
#: not garbage), so this is not the "a replay is gone" incident constitution I reserves severity 1
#: for. The nightly audit (T061) fails only on an unacknowledged severity-1 row.
VALIDATION_FAILED_ALERT_SEVERITY = 2

#: A claim held longer than this is treated as abandoned by a run that died mid-cycle. 300 s is
#: the Vercel function ceiling `run.py`'s module docstring and `test_interruption.py` both name as
#: "the maximum function duration" data-model.md's `claimed_at` note refers to.
DEFAULT_MAX_CLAIM_AGE_SECONDS = 300.0

#: How many `pending`/stale-`downloading` rows one claim statement takes at once. Deliberately 1,
#: not data-model.md's illustrative `:batch`: `test_interruption.py`'s and `test_deadline_order.
#: py`'s own scenarios both require the budget to be checked, and a capture's own deadline
#: ordering to be honoured, between every single capture — not merely between batches of several
#: — and only a batch of one guarantees a stale budget check can never strand more than the one
#: row already claimed in `downloading`. A caller that wants real batching passes a larger value
#: explicitly and accepts the wider stranding window that comes with it.
DEFAULT_BATCH_SIZE = 1

#: A native validation call is normally fast (single-digit seconds at the outside); this is a
#: generous ceiling against a run budget measured in minutes, not a tuned production constant —
#: nothing in `.env.example` names one, so this module owns its own default rather than inventing
#: a setting nothing else reads.
DEFAULT_VALIDATION_TIMEOUT_SECONDS = 30.0

#: Accepted for forward compatibility with T056's three-way 404 reading (`CAPTURE_BUDGET_DAYS` /
#: `REPLAY_PUBLICATION_GRACE_HOURS` in `.env.example`) and stored, but not read by this module —
#: see the module docstring's "three-way 404 reading is a seam" paragraph.
DEFAULT_CAPTURE_BUDGET_DAYS = 21
DEFAULT_REPLAY_PUBLICATION_GRACE_HOURS = 72

#: `ingest_runs`' own counter vocabulary (data-model.md) that this stage's report can ever move —
#: the rest of that row's counters belong to discovery and reconciliation, not to the drain.
_ZERO_COUNTERS: Mapping[str, int] = {
    "captures_attempted": 0,
    "stored_total": 0,
    "quarantined_total": 0,
    "unavailable_total": 0,
    "expired_total": 0,
    "failed_total": 0,
    "alerts_raised": 0,
}


class _ObjectPut(Protocol):
    """The one `ObjectStore` method this module calls. Named as its own Protocol, structurally
    satisfied by the real `aoe2stats_storage.objects.ObjectStore` and by every fake the five test
    files construct, several of which implement `put` alone (`test_idempotency.py`'s
    `_FakeObjectStore`) rather than the whole class.
    """

    async def put(self, key: str, body: bytes, *, content_type: str = ...) -> None: ...


class _NoOpAlertSink:
    """The default `alert_sink` for a caller that never supplies one (`test_interruption.py`'s
    `CaptureStage`, whose fixtures never quarantine anything). Satisfies `AlertSink` structurally
    without persisting anything — a quarantine that somehow occurred under this default would
    still leave `last_error` on the row itself, just with no alert row to go with it.
    """

    async def write(
        self,
        *,
        kind: str,
        severity: int,
        detail: Mapping[str, Any] | None,
        ingest_run_id: uuid.UUID | None,
    ) -> AlertRecord:
        return AlertRecord(
            id=uuid.uuid4(),
            kind=kind,
            severity=severity,
            detail=detail,
            raised_at=datetime.now(UTC),
            ingest_run_id=ingest_run_id,
            acknowledged_at=None,
        )

    async def unacknowledged_severity_one(self) -> list[AlertRecord]:
        return []


async def _validate_with_barrier(
    validator: ReplayValidator, zip_bytes: bytes, *, timeout_seconds: float
) -> tuple[ReplayValidationResult | None, str | None]:
    """Run `validator.validate` behind the containment barrier the module docstring describes.

    Returns `(result, None)` on success or `(None, reason)` on any failure at all — a well-formed
    `ReplayValidationError`, a raw engine panic (a `BaseException` the Protocol deliberately never
    catches itself), or a timeout. Never raises: that is the whole point of a barrier.
    """
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(validator.validate, zip_bytes), timeout=timeout_seconds
        )
    except TimeoutError:
        return None, f"validation exceeded the {timeout_seconds}s wall-clock cap"
    except BaseException as exc:
        reason = str(exc)
        return None, f"{type(exc).__name__}: {reason}" if reason else type(exc).__name__
    return result, None


class CaptureDrain:
    """A `Stage` (`aoe2stats_ingester.run.Stage`): claim, download, store, checksum, validate,
    mark. See the module docstring for the write ordering, the containment barrier and the
    reclaim path's one known gap.
    """

    name = "drain"

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        replay_provider: ReplayProvider,
        object_store: _ObjectPut,
        validator: ReplayValidator | None = None,
        engine: ReplayValidator | None = None,
        alert_sink: AlertSink | None = None,
        validation_timeout_seconds: float = DEFAULT_VALIDATION_TIMEOUT_SECONDS,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_claim_age_seconds: float = DEFAULT_MAX_CLAIM_AGE_SECONDS,
        capture_budget_days: int = DEFAULT_CAPTURE_BUDGET_DAYS,
        replay_publication_grace_hours: int = DEFAULT_REPLAY_PUBLICATION_GRACE_HOURS,
    ) -> None:
        # `test_idempotency.py` names this keyword argument `engine`; every other test file names
        # it `validator`. Both are the same `ReplayValidator` (`aoe2stats_core.replay.validation`)
        # — see the module docstring's closing paragraph on why this module accepts both spellings
        # of one constructor rather than picking a winner and breaking three already-landed tests.
        resolved_validator = validator if validator is not None else engine
        if resolved_validator is None:
            raise TypeError("CaptureDrain requires either `validator` or `engine`")
        self._session_factory = session_factory
        self._replay_provider = replay_provider
        self._object_store = object_store
        self._validator = resolved_validator
        self._alert_sink: AlertSink = alert_sink if alert_sink is not None else _NoOpAlertSink()
        self._validation_timeout_seconds = validation_timeout_seconds
        self._batch_size = batch_size
        self._max_claim_age_seconds = max_claim_age_seconds
        # Accepted, stored, not read — see the module-level constants' own docstring.
        self._capture_budget_days = capture_budget_days
        self._replay_publication_grace_hours = replay_publication_grace_hours

    async def __call__(self, budget: Budget) -> Mapping[str, Any]:
        report: dict[str, int] = dict(_ZERO_COUNTERS)
        # A row a 404 reverts to `pending` (`_revert_to_pending`) is immediately eligible again by
        # its own `next_attempt_at` — T057's bounded-retry backoff is not this task's to add (see
        # the module docstring's "three-way 404 reading is a seam" paragraph). Without this set,
        # the very next `_claim_batch` in *this same* `__call__` would re-claim that identical row
        # and hammer it for the rest of the budget instead of moving on to the rest of the queue —
        # every id this cycle has already attempted, whatever the outcome, is excluded from every
        # further claim this same call makes; a *later* cycle (a fresh `__call__`) starts with an
        # empty set and is free to attempt it again.
        attempted_ids: set[uuid.UUID] = set()

        async def handle_item(capture_id: uuid.UUID) -> None:
            outcome = await self._process_one(capture_id)
            attempted_ids.add(capture_id)
            report["captures_attempted"] += 1
            if outcome in report:
                report[outcome] += 1
            if outcome == "quarantined_total":
                report["alerts_raised"] += 1

        # Budget checked between claims and never mid-claim (the module docstring's
        # `DEFAULT_BATCH_SIZE` note): once a claim has handed a row to `handle_item`, that row
        # runs to completion — download, upload, validate, mark — regardless of the budget.
        while not budget.expired:
            claimed_ids = await self._claim_batch(exclude_ids=attempted_ids)
            if not claimed_ids:
                break
            stopped = await drain_with_rate_limit_guard(
                claimed_ids, handle_item, sink=self._alert_sink, run_id=None
            )
            if stopped:
                report["alerts_raised"] += 1
                break

        report["backlog_remaining"] = await self._backlog_remaining()
        return report

    # --- Claiming ---------------------------------------------------------------------------

    async def _claim_batch(
        self, *, exclude_ids: frozenset[uuid.UUID] | set[uuid.UUID] = frozenset()
    ) -> list[uuid.UUID]:
        """`FOR UPDATE SKIP LOCKED`, ordered by `capture_deadline_at` ascending (data-model.md:
        "the single most consequential line in the schema"), over the union of two eligible sets:
        an ordinary `pending` row whose backoff has elapsed, or a `downloading` row whose claim
        has outlived `max_claim_age_seconds` — a run that died mid-cycle. Both branches share one
        `ORDER BY`, so a backlog under budget pressure sheds far-deadline work before near-deadline
        work regardless of which of the two states it happens to be sitting in.

        `exclude_ids` is the current cycle's own already-attempted set (`__call__`'s
        `attempted_ids`) — see that method's docstring for why a row reverted to `pending` this
        same cycle must not be immediately reclaimed by it again.
        """
        now = datetime.now(UTC)
        stale_before = now - timedelta(seconds=self._max_claim_age_seconds)

        eligibility = or_(
            and_(
                ReplayCapture.status == CaptureStatus.PENDING,
                ReplayCapture.next_attempt_at <= now,
            ),
            and_(
                ReplayCapture.status == CaptureStatus.DOWNLOADING,
                ReplayCapture.claimed_at.is_not(None),
                ReplayCapture.claimed_at < stale_before,
            ),
        )
        claimable_ids = select(ReplayCapture.id).where(eligibility)
        if exclude_ids:
            claimable_ids = claimable_ids.where(ReplayCapture.id.not_in(exclude_ids))
        claimable_ids = (
            claimable_ids.order_by(ReplayCapture.capture_deadline_at.asc())
            .limit(self._batch_size)
            .with_for_update(skip_locked=True)
        )
        statement = (
            update(ReplayCapture)
            .where(ReplayCapture.id.in_(claimable_ids))
            .values(
                status=CaptureStatus.DOWNLOADING,
                claimed_at=now,
                attempts=ReplayCapture.attempts + 1,
            )
            .returning(ReplayCapture.id)
        )
        async with self._session_factory() as session:
            result = await session.execute(statement)
            ids = [row[0] for row in result.all()]
            await session.commit()
        return ids

    # --- Processing one claimed row ----------------------------------------------------------

    async def _process_one(self, capture_id: uuid.UUID) -> str:
        """Download (unless already resumed), upload, commit the blob metadata, then validate and
        mark. Returns the report key this outcome belongs under, or `"not_found"` for a 404 — not
        a report key itself, since T056 owns what a 404 ultimately counts as (see the module
        docstring).
        """
        async with self._session_factory() as session:
            capture = await session.get(ReplayCapture, capture_id)
        if capture is None:  # pragma: no cover - defensive: the claim just produced this id
            return "not_found"

        game_id, profile_id = capture.game_id, capture.profile_id

        if capture.object_key is not None and capture.zip_sha256 is not None:
            # Resumed reclaim: the bytes are already durable (FR-023's write ordering is what
            # makes this survivable at all). See the module docstring's "reclaim path's one known
            # gap" for why this does not re-run validation.
            await self._mark_stored(capture_id, None)
            return "stored_total"

        fetched = await self._replay_provider.fetch_replay(game_id, profile_id)
        if isinstance(fetched, NotFound):
            await self._revert_to_pending(capture_id, fetched.http_status)
            return "not_found"

        blob: ReplayBlob = fetched
        content = blob.content
        sha256 = hashlib.sha256(content).hexdigest()
        key = replay_object_key(game_id, profile_id)

        # Upload before any mark, never the reverse (the module docstring's non-negotiable
        # ordering). `object_key`/`zip_bytes`/`zip_sha256` are committed immediately after, while
        # the row is still `downloading`.
        await self._object_store.put(
            key, content, content_type=blob.content_type or REPLAY_CONTENT_TYPE
        )
        await self._commit_blob_metadata(capture_id, key, len(content), sha256)

        result, error = await _validate_with_barrier(
            self._validator, content, timeout_seconds=self._validation_timeout_seconds
        )
        if result is not None:
            await self._mark_stored(capture_id, result)
            return "stored_total"

        reason = error or "validation failed for an unspecified reason"
        await self._mark_quarantined(capture_id, reason)
        await raise_alert(
            self._alert_sink,
            VALIDATION_FAILED_ALERT_KIND,
            VALIDATION_FAILED_ALERT_SEVERITY,
            {
                "capture_id": str(capture_id),
                "game_id": game_id,
                "profile_id": profile_id,
                "reason": reason,
            },
            run_id=None,
        )
        return "quarantined_total"

    # --- Row writes ---------------------------------------------------------------------------

    async def _commit_blob_metadata(
        self, capture_id: uuid.UUID, object_key: str, zip_bytes: int, zip_sha256: str
    ) -> None:
        async with self._session_factory() as session:
            await session.execute(
                update(ReplayCapture)
                .where(ReplayCapture.id == capture_id)
                .values(object_key=object_key, zip_bytes=zip_bytes, zip_sha256=zip_sha256)
            )
            await session.commit()

    async def _mark_stored(
        self, capture_id: uuid.UUID, result: ReplayValidationResult | None
    ) -> None:
        values: dict[str, Any] = {
            "status": CaptureStatus.STORED,
            "stored_at": datetime.now(UTC),
            "http_status": 200,
            "last_error": None,
        }
        if result is not None:
            values["inner_filename"] = result.inner_filename
            values["inner_bytes"] = result.inner_bytes
            values["validated_by"] = f"{result.engine_name}@{result.engine_version}"
        async with self._session_factory() as session:
            await session.execute(
                update(ReplayCapture).where(ReplayCapture.id == capture_id).values(**values)
            )
            await session.commit()

    async def _mark_quarantined(self, capture_id: uuid.UUID, reason: str) -> None:
        async with self._session_factory() as session:
            await session.execute(
                update(ReplayCapture)
                .where(ReplayCapture.id == capture_id)
                .values(status=CaptureStatus.QUARANTINED, last_error=reason)
            )
            await session.commit()

    async def _revert_to_pending(self, capture_id: uuid.UUID, http_status: int) -> None:
        """A 404 with no classification yet (T056's seam — see the module docstring): the row goes
        straight back to `pending` so a later cycle tries again, rather than ever guessing
        `unavailable`/`expired`/`failed` from here.
        """
        async with self._session_factory() as session:
            await session.execute(
                update(ReplayCapture)
                .where(ReplayCapture.id == capture_id)
                .values(
                    status=CaptureStatus.PENDING,
                    claimed_at=None,
                    http_status=http_status,
                    next_attempt_at=datetime.now(UTC),
                    last_error=(
                        "replay not found at source (404); classification deferred to a later "
                        "attempt (T056)"
                    ),
                )
            )
            await session.commit()

    async def _backlog_remaining(self) -> int:
        async with self._session_factory() as session:
            count = await session.scalar(
                select(func.count())
                .select_from(ReplayCapture)
                .where(ReplayCapture.status.in_([CaptureStatus.PENDING, CaptureStatus.DOWNLOADING]))
            )
        return int(count or 0)


#: Aliases for the two other names already-landed test files committed to before this task ever
#: ran — see the module docstring's closing paragraph. All three are exactly one class.
CaptureStage = CaptureDrain
DrainStage = CaptureDrain
