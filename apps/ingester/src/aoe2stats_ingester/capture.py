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

**One deliberate exception to "no exception ever leaves" (T055a).** `asyncio.CancelledError`
inherits `BaseException` directly, exactly as `pyo3_runtime.PanicException` does, so the barrier
described above could catch it too — and, before T055a, did: a task cancelled from outside (a
graceful shutdown, `apps/api/src/aoe2stats_api/routers/cron.py` running `run_once` inside an
ordinary request that a restart interrupts) was folded into the same `quarantined` outcome as a
genuine engine panic, terminally writing off a replay whose bytes were already durable
(`_commit_blob_metadata` has already run at that point — see the write-ordering paragraph above)
to nothing more than a server restart. `_validate_with_barrier` re-raises `CancelledError` instead
of containing it; see that function's own docstring for the exact clause ordering this depends on
and why it must not be reordered. `CaptureDrain.__call__` does not catch it either, so it does
leave the call — into the caller's own cancellation, exactly as an ordinary `await` would behave
without this module in the way at all — leaving the row `downloading` with its committed
`object_key` for the next cycle's reclaim to resume at validation.

**The reclaim path resumes at validation, not at the download.** A stale `downloading` row that
already carries `object_key`/`zip_sha256` (the previous run committed the blob and was killed
before validation ever ran, or before the status flip) is resumed *without* re-downloading —
`AoemsReplayProvider` is never called for it. `ObjectStore.get` (`packages/storage/src/
aoe2stats_storage/objects.py`) reads the already-durable bytes back into this process; `_resume_
reclaim` re-hashes them against the row's own committed `zip_sha256` and, only if that still
matches, runs them through the exact same containment barrier (`_validate_with_barrier`) the
normal path uses, marking `stored` or `quarantined` from that outcome exactly as the normal path
does. A missing object or a checksum that no longer matches is not retried — the row already
believes it holds a specific blob, and a retry would silently paper over evidence that it does
not — both instead fold into `quarantined`, the same terminal outcome every other kind of
validation failure produces, with `last_error` explaining which of the two it was.

**Re-validation of an engine-failure quarantine (T673).** A capture quarantined because the engine
could not parse a recording keeps its object (constitution IV), so a later engine can be given a
second chance without touching the source: `CaptureDrain.revalidate_quarantined` reads the committed
object back, checks it against the row's own `zip_sha256` and runs it through the same barrier.
It is selected by the engine's own failure text (`_engine_failure_reason`), never an integrity
quarantine, and never for a capture whose owner has objected to archival (`_objecting_owner_exists`,
the predicate the claim above uses). It never reads from the provider, never writes or deletes an
object, and raises no alert: the row already raised its `validation_failed` when it was first
quarantined. A row is rewritten only with a reason the selection would still match; any other
outcome leaves it untouched and is reported. See that method.

**The per-user fairness cap is wired in here, not reimplemented here** (T058's own gap: `quota.py`
shipped `apply_quota` fully tested in isolation, but nothing in this module ever called it, so
FR-044 enforced nothing in production). `apply_quota` is a pure, read-only filter over a run's
already-*claimed* rows (`quota.py`'s own module docstring) — it never decides what to do with a
capture it drops, only which ones the cap still allows through. `__call__` below is the caller that
decides: `_apply_quota` grows a running, claim-ordered list of every `ReplayCapture` this run has
claimed so far (`_quota_candidates`), re-derives the allowed subsequence from it on every claim
(cheap here, since `DEFAULT_BATCH_SIZE` keeps one claim to one row — see that constant's own
docstring), and for whichever of *this* claim's rows the cap rejects, reverts the claim immediately
(`_revert_claim`, the same undo `_revert_claim_after_rate_limit` already used for a claim a 429
interrupted before any real attempt was made) rather than leaving it `downloading` for a stale-claim
reclaim minutes away to eventually find. The reverted id is folded into `attempted_ids` so this same
`__call__`'s own next `_claim_batch` does not immediately re-select the row it was just handed back
to `pending` — precisely the guard that set already exists for a 404 that reverts to `pending`
(see `__call__`'s own comment on `attempted_ids`). Quota enforcement is optional at construction —
`max_captures_per_user_per_run`/`quota_exempt_days` default to `None`, and `_apply_quota` is never
called when unset — so every already-landed test file that constructs this class without either
keyword keeps its exact prior behaviour; a caller that wants the cap enforced supplies both
together, from `Settings.ingest_max_captures_per_user_per_run` / `Settings.ingest_quota_exempt_days`
(`INGEST_MAX_CAPTURES_PER_USER_PER_RUN` / `INGEST_QUOTA_EXEMPT_DAYS`, `.env.example`) the same way
every other tunable this module owns is threaded down from `apps/api`'s `Settings` rather than read
here directly (`test_backfill.py`'s own module docstring: `apps/ingester` cannot depend on
`apps/api`, which is the one place `Settings` lives).

**Rate limiting is delegated, not reimplemented** (T052, `ratelimit.py`): each claimed batch is
handed to `drain_with_rate_limit_guard`, which calls this module's own per-capture handler
serially and, the moment `ProviderRateLimited` is raised, alerts once and stops the whole batch —
never the one capture it fired on. `CaptureDrain` only supplies the handler and reacts to whether
the guard reports it stopped early.

**The three-way 404 reading** (T056). `AoemsReplayProvider` answers `NotFound` rather than
raising, and does not itself classify what a 404 means — "not yet published", "genuinely never
recorded", or "past the retention window" all produce the identical wire condition, and only a
caller holding `matches.completed_at` can tell them apart (`contracts/providers.md`).
`_classify_not_found` is that caller: it reads `matches.completed_at` for the claimed row's own
`game_id` and compares it against two thresholds, in order.

- **Younger than `REPLAY_PUBLICATION_GRACE_HOURS`**: the row reverts to `pending` and is picked up
  again on a later cycle, exactly as every 404 used to be read before this task. This is the
  branch FR-019 was corrected for — without it, a replay published a few hours late is recorded as
  never recorded, and eventually expires for no reason.
- **Older than the grace, but `capture_deadline_at` (`completed_at + CAPTURE_BUDGET_DAYS`,
  computed once at insert — `discover.py`) has not yet passed**: `unavailable`, but *only once
  `attempts` has reached at least two*. The grace is sized on the discovery cadence (at least
  twice ~25 h — T012a) precisely so two polls always fall on either side of it; age alone would let
  one unlucky 404 close a capture a second poll would have caught, so a single attempt past the
  grace still reverts to `pending` exactly like the first branch, and only the second attempt (or
  later) may conclude `unavailable`.
- **Past `capture_deadline_at`**: `expired`, concluded on the very first attempt — the two-attempt
  floor governs only "never recorded" (`unavailable`), not "past the window" — and raises a
  severity-1 `expired_capture` alert through `raise_alert` (T014a), the one alert kind that means a
  replay is now provably gone rather than merely not yet available. This is a different kind, with
  a different timing, from `deadline_breach` (T059a): that one fires at day 21 while there is still
  time to act, a warning; `expired_capture` fires only once a 404 past that same deadline proves
  the loss actually happened, a post-mortem. Neither subsumes the other.

None of `unavailable_total`/`expired_total` was ever incremented before this task landed —
data-model.md's state machine calls a non-zero `expired_total` the one thing that "must never
happen" in the steady state, and reverting every 404 to `pending` without ever concluding
otherwise is what kept that vacuously true. It is no longer vacuous: an `expired_total` (or
`unavailable_total`) that never moves now means what it says.

**Bounded retries for a `ProviderUnavailable`** (T057, FR-020). `AoemsReplayProvider` already
retries a transient 5xx/timeout/connection failure internally, with its own backoff, before ever
raising `ProviderUnavailable` — so *this* module's retries are the outer loop, across drain cycles,
for a source that stayed unhealthy across an entire internal retry budget.
`_handle_provider_unavailable` reads the row's own `attempts` (already incremented by this
attempt's own claim, exactly as `_classify_not_found` reads it) against `self._max_attempts`:
short of the ceiling, the row reverts to `pending` with `next_attempt_at` pushed
`_retry_backoff_seconds(attempts)` into the future — an interval that strictly increases with
`attempts` rather than a fixed delay repeated forever, which is what FR-020 forbids. At the
ceiling, the row becomes terminally `failed`, never a further retry. `failed` raises no alert:
unlike `quarantined` (bytes obtained, unparsable — constitution IV, evidence) or `expired` (the
source itself confirms permanent loss), a run of 5xx responses is not evidence of anything
specific to this one capture, and `failed_total` is the signal a human reviews rather than an
alert queue a merely transient outage would flood.

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
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol

from sqlalchemy import ColumnElement, and_, false, func, literal, or_, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_core.alerting import AlertRecord, AlertSink, raise_alert
from aoe2stats_core.replay.validation import ReplayValidationResult, ReplayValidator
from aoe2stats_ingester.budget import Budget
from aoe2stats_ingester.quota import apply_quota
from aoe2stats_ingester.ratelimit import drain_with_rate_limit_guard
from aoe2stats_providers.base import (
    NotFound,
    ProviderRateLimited,
    ProviderUnavailable,
    ReplayBlob,
    ReplayProvider,
)
from aoe2stats_storage.models import Alert as AlertRow
from aoe2stats_storage.models import CaptureStatus, Match, ProfileLink, ReplayCapture, User
from aoe2stats_storage.objects import REPLAY_CONTENT_TYPE, ObjectNotFound, replay_object_key

#: `alerts.kind` for a quarantine (`AlertKind.VALIDATION_FAILED` in
#: `packages/storage/src/aoe2stats_storage/models.py`, named here as a plain string for the same
#: reason `ratelimit.py`'s `RATE_LIMITED_ALERT_KIND` is: `AlertSink.write` takes a plain `str`,
#: and `apps/ingester` needs no dependency on `aoe2stats_storage` merely to spell one.
VALIDATION_FAILED_ALERT_KIND = "validation_failed"

#: Severity 2, never 1: a quarantined capture still holds the bytes (constitution IV — evidence,
#: not garbage), so this is not the "a replay is gone" incident constitution I reserves severity 1
#: for. The nightly audit (T061) fails only on an unacknowledged severity-1 row.
VALIDATION_FAILED_ALERT_SEVERITY = 2

#: The exact text shapes `_validate_with_barrier` writes for a failure that is the *engine's*
#: judgement of a recording (T673), each `"<ExcClass>: <text>"` or the bare class when the text is
#: empty. `EngineParseError` is `aoe2stats_core.replay.validation`'s wrapper for an ordinary
#: exception the engine raised or a result it cannot use; `PanicException` is `pyo3_runtime`'s
#: class for a native panic, which `aoe2rec-py` 0.1.21 raised on the one recording measured as
#: game build 185872 (T672a: `apps/analyzer/tests/test_engine_panic.py`).
#:
#: Deliberately absent: `MalformedArchiveError` (this repository's own archive rule; a newer engine
#: cannot change it), the wall-clock cap text (it says nothing about the bytes, and a re-run would
#: spend the cap again) and every `reclaim ...` text (an integrity quarantine, evidence a human
#: must read; data-model.md's `quarantined` row).
_ENGINE_FAILURE_CLASSES = ("EngineParseError", "PanicException")

#: The fixed words of the texts `_validate_with_barrier` and `_read_back_failure_reason` write,
#: named once so the writer and `_reason_class` (the dry run's grouping) cannot drift apart.
_CAP_REASON_PREFIX = "validation exceeded the "
_CAP_REASON_SUFFIX = "s wall-clock cap"
_READ_BACK_REASON_PREFIX = "reclaim could not read back"
_CHECKSUM_REASON_PREFIX = "reclaim checksum mismatch"

#: How many leading characters of `last_error` the dry run's grouping reads. Long enough for the
#: longest fixed prefix and any exception class name; the rest of a reason is never loaded.
_REASON_HEAD_CHARS = 120

#: Why `revalidate_quarantined` reported a row as `changed_elsewhere`: its guarded write matched no
#: row because the status was no longer `quarantined`.
_CHANGED_ELSEWHERE = "the row was no longer quarantined when the result was written"

#: `alerts.kind` for `_classify_not_found`'s `expired` conclusion (`AlertKind.EXPIRED_CAPTURE` in
#: `packages/storage/src/aoe2stats_storage/models.py`, named as a plain string for the same reason
#: `VALIDATION_FAILED_ALERT_KIND` above is).
EXPIRED_CAPTURE_ALERT_KIND = "expired_capture"

#: Severity 1, never 2: this is the "a replay is gone" incident constitution I reserves severity 1
#: for — the one alert kind meaning a capture is now provably, permanently lost rather than merely
#: not yet available. The nightly audit (T061) fails the build on any unacknowledged row of this
#: severity.
EXPIRED_CAPTURE_ALERT_SEVERITY = 1

#: FR-019/T012a's two-attempt floor: a 404 past the publication grace may only conclude
#: `unavailable` once `ReplayCapture.attempts` has reached this many — never on age alone, since a
#: single poll can fall on either side of the grace at a daily cadence. Not a setting: the floor
#: reflects the grace's own sizing rationale (at least two discovery-cadence polls), not a value an
#: operator would ever want to tune independently of it.
_MINIMUM_ATTEMPTS_BEFORE_UNAVAILABLE = 2

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

#: `CAPTURE_BUDGET_DAYS` (`.env.example`). Accepted and stored, but still not read by this module:
#: `_classify_not_found` compares against the claimed row's own `capture_deadline_at`
#: (`completed_at + CAPTURE_BUDGET_DAYS`, computed once at insert by `discover.py`) rather than
#: recomputing the same threshold from this value a second time — a row's deadline is fixed at the
#: budget in effect when it was enqueued, even if this setting changes later (`discover.py`'s own
#: docstring), and reading `self._capture_budget_days` here instead would silently apply *today's*
#: budget to a row enqueued under a different one.
DEFAULT_CAPTURE_BUDGET_DAYS = 21

#: `REPLAY_PUBLICATION_GRACE_HOURS` (`.env.example`). Read by `_classify_not_found` (T056) as the
#: first of its two thresholds — see the module docstring's "three-way 404 reading" paragraph.
DEFAULT_REPLAY_PUBLICATION_GRACE_HOURS = 72

#: The bounded-retry ceiling T057 owns (no `.env.example` name yet — that task introduces one).
#: Accepted here and threaded through the constructor because `test_failure_classification.py`
#: (T047) already constructs `CaptureStage` with `max_attempts=` for scenarios this task *does*
#: own (the three 404 branches), not only for the backoff/`failed` scenario that is T057's; read
#: by `_handle_provider_unavailable` (T057) below, to decide the exact same boundary
#: `_classify_not_found` never reaches for a 5xx: the *n*th `ProviderUnavailable` at this attempt
#: count is terminal, never a further backoff.
DEFAULT_MAX_ATTEMPTS = 3

#: T057's backoff base, in the same spirit as `_MINIMUM_ATTEMPTS_BEFORE_UNAVAILABLE`: not a
#: setting an operator would tune independently (no `.env.example` name), just the constant this
#: module's own exponential formula is built on. `_retry_backoff_seconds` doubles this per attempt
#: (`base * 2 ** (attempts - 1)`), so consecutive backoffs strictly increase (FR-020) rather than
#: repeating a fixed interval — `test_failure_classification.py`'s backoff scenario asserts the
#: second delay is strictly greater than the first for exactly this reason.
_RETRY_BACKOFF_BASE_SECONDS = 60.0

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


def _engine_failure_reason() -> ColumnElement[bool]:
    """SQL predicate: `replay_captures.last_error` is the engine's own failure text, i.e. exactly
    `"<Class>"` or `"<Class>: ..."` for a class in `_ENGINE_FAILURE_CLASSES` and nothing else. A
    prefix match on the class and its colon-space, never a substring: a reason that merely
    mentions an engine class (`reclaim could not read back ...: EngineParseError: ...`) is an
    integrity quarantine and must stay out.
    """
    clauses: list[ColumnElement[bool]] = []
    for name in _ENGINE_FAILURE_CLASSES:
        clauses.append(ReplayCapture.last_error == name)
        clauses.append(ReplayCapture.last_error.startswith(f"{name}: ", autoescape=True))
    return or_(*clauses)


def _is_engine_failure_reason(reason: str) -> bool:
    """`_engine_failure_reason`'s predicate on a value not yet in the table: would a row carrying
    `reason` be selected again? Built from the same `_ENGINE_FAILURE_CLASSES`, so a reason is
    written back to a row only when the selection would still match it."""
    return any(reason == name or reason.startswith(f"{name}: ") for name in _ENGINE_FAILURE_CLASSES)


def _objecting_owner_exists() -> ColumnElement[bool]:
    """Correlated `EXISTS`, against the enclosing query's `replay_captures.profile_id`: the
    *currently active* link's owner has objected to archival (`profile_links.unlinked_at IS NULL
    AND users.archival_objected_at IS NOT NULL`, constitution IX, FR-035). The one definition of
    "objecting": `CaptureDrain._claim_batch` excludes exactly the rows it matches, and
    `revalidate_quarantined`'s selection does too, so the two cannot diverge. Only a *found*
    objection matches; a capture with no active link on record is not objecting.
    """
    return (
        select(ProfileLink.profile_id)
        .join(User, User.id == ProfileLink.user_id)
        .where(ProfileLink.profile_id == ReplayCapture.profile_id)
        .where(ProfileLink.unlinked_at.is_(None))
        .where(User.archival_objected_at.is_not(None))
        .exists()
    )


def _revalidation_selection() -> ColumnElement[bool]:
    """The rows `revalidate_quarantined` re-validates: `quarantined`, holding an object and its
    checksum, with the engine's own failure text, whose owner has not objected. A quarantined
    capture is not an archived one (001's spec), so the carve-out for recordings archived before
    an objection does not cover it."""
    return and_(
        ReplayCapture.status == CaptureStatus.QUARANTINED,
        ReplayCapture.object_key.is_not(None),
        ReplayCapture.zip_sha256.is_not(None),
        _engine_failure_reason(),
        ~_objecting_owner_exists(),
    )


_REASON_CLASS_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")


def _reason_class(reason: str | None, *, has_object: bool, objecting: bool) -> str:
    """The class a quarantined row outside the selection is counted under in a dry run: a label,
    never a value. The text before the first colon is the exception class the barrier wrote; the
    cap and the two reclaim texts are recognised by their fixed words first, because the second
    and third carry an object key before their first colon. Free text that is not a bare
    identifier is `other`.
    """
    if not reason:
        return "no reason recorded"
    if reason.startswith(_READ_BACK_REASON_PREFIX):
        return _READ_BACK_REASON_PREFIX
    if reason.startswith(_CHECKSUM_REASON_PREFIX):
        return _CHECKSUM_REASON_PREFIX
    if reason.startswith(_CAP_REASON_PREFIX) and reason.endswith(_CAP_REASON_SUFFIX):
        return "wall-clock cap"
    head = reason.partition(":")[0]
    label = head if _REASON_CLASS_PATTERN.fullmatch(head) else "other"
    if label in _ENGINE_FAILURE_CLASSES and _is_engine_failure_reason(reason):
        if objecting:
            return f"{label} (archival objected)"
        if not has_object:
            return f"{label} (no committed object)"
    return label


#: What happened to one row `revalidate_quarantined` looked at.
#:
#: - `selected`: a dry run's only outcome;
#: - `stored` / `still_quarantined`: the row was written (`still_quarantined` carries the new
#:   engine verdict);
#: - `inconclusive`: validation failed for a reason that is not the engine's verdict (the
#:   wall-clock cap, a class outside `_ENGINE_FAILURE_CLASSES`), so the selection would not match
#:   it; nothing was written and `reason` is reported;
#: - `integrity_failure`: the object is missing or no longer matches the row's `zip_sha256`;
#:   nothing was written;
#: - `changed_elsewhere`: another process moved the row first; nothing was written.
RevalidationOutcomeKind = Literal[
    "selected",
    "stored",
    "still_quarantined",
    "inconclusive",
    "integrity_failure",
    "changed_elsewhere",
]


#: The full ordering key of `revalidate_quarantined`: `(matches.completed_at, capture id)`.
RevalidationCursor = tuple[datetime, uuid.UUID]


@dataclass(frozen=True, slots=True)
class RevalidationOutcome:
    capture_id: uuid.UUID
    game_id: int
    profile_id: int
    completed_at: datetime
    outcome: RevalidationOutcomeKind
    #: The new quarantine reason (`still_quarantined`), or why nothing was written; else `None`.
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class RevalidationReport:
    outcomes: tuple[RevalidationOutcome, ...]
    #: More candidates exist beyond `limit`; resume with `after=cursor`.
    truncated: bool
    #: `matches.completed_at` and capture id of the last row examined: together the cursor for
    #: `after`. Both, because the ordering key is `(completed_at, id)` and two captures of one
    #: match (two tracked profiles) share a `completed_at`: a timestamp alone would skip the rest.
    last_completed_at: datetime | None
    last_capture_id: uuid.UUID | None = None
    #: A dry run only: how many `quarantined` rows lie outside the selection, by `_reason_class`.
    #: Counts under labels, no values. `None` for a real run.
    unselected_by_reason: tuple[tuple[str, int], ...] | None = None
    #: The class name (never its text) of the store error that stopped the run, else `None`. Only
    #: a missing object and a checksum mismatch are per-row outcomes; anything else the store
    #: raises says nothing about the row, so the run stops with that row unwritten.
    aborted_by: str | None = None

    @property
    def cursor(self) -> RevalidationCursor | None:
        """The `after` value that continues from the last row examined, or `None`."""
        if self.last_completed_at is None or self.last_capture_id is None:
            return None
        return (self.last_completed_at, self.last_capture_id)


class _StoreTransportError(Exception):
    """The object store failed in a way that is not an integrity outcome (`__cause__` is the
    store's own error). Internal to `revalidate_quarantined`, which turns it into
    `RevalidationReport.aborted_by`."""


class _ObjectPut(Protocol):
    """The `ObjectStore` methods this module calls: `put` for a freshly downloaded blob, `get` to
    read previously committed bytes back for the reclaim path's re-validation (see the module
    docstring). Named as its own Protocol, structurally satisfied by the real
    `aoe2stats_storage.objects.ObjectStore` and by every fake the test files construct.
    `test_idempotency.py`'s `_FakeObjectStore` implements `put` alone — that test's traffic never
    exercises a reclaim, so its `object_store` never needs `get` at runtime even though the type
    hint below now names both.
    """

    async def put(self, key: str, body: bytes, *, content_type: str = ...) -> None: ...
    async def get(self, key: str) -> bytes: ...


class _DatabaseAlertSink:
    """The default `alert_sink` for a caller that never supplies one — `CaptureStage` (T056),
    `test_failure_classification.py`'s own construction, never passes one and then reads the
    `expired_capture`/`rate_limited` rows straight back out of the real `alerts` table
    (`test_failure_classification.py`'s module docstring: "this test only ever reads the outcome
    back from `replay_captures` and `alerts`, never how `CaptureStage` got there"). Writes and
    reads through the same `session_factory` every other part of this class uses, so no caller
    needs its own database-backed `AlertSink` merely to let `CaptureDrain`'s alerts land somewhere
    real. `test_interruption.py`'s fixtures also construct `CaptureStage` without one, but never
    quarantine anything, so they exercise `write` here either never or not at all in a way their
    own assertions depend on.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def write(
        self,
        *,
        kind: str,
        severity: int,
        detail: Mapping[str, Any] | None,
        ingest_run_id: uuid.UUID | None,
    ) -> AlertRecord:
        row = AlertRow(
            id=uuid.uuid4(),
            kind=kind,
            severity=severity,
            detail=dict(detail) if detail is not None else None,
            ingest_run_id=ingest_run_id,
        )
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return AlertRecord(
                id=row.id,
                kind=row.kind,
                severity=row.severity,
                detail=row.detail,
                raised_at=row.raised_at,
                ingest_run_id=row.ingest_run_id,
                acknowledged_at=row.acknowledged_at,
            )

    async def unacknowledged_severity_one(self) -> list[AlertRecord]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(AlertRow).where(AlertRow.severity == 1, AlertRow.acknowledged_at.is_(None))
            )
            rows = result.scalars().all()
        return [
            AlertRecord(
                id=row.id,
                kind=row.kind,
                severity=row.severity,
                detail=row.detail,
                raised_at=row.raised_at,
                ingest_run_id=row.ingest_run_id,
                acknowledged_at=row.acknowledged_at,
            )
            for row in rows
        ]


async def _validate_with_barrier(
    validator: ReplayValidator, zip_bytes: bytes, *, timeout_seconds: float
) -> tuple[ReplayValidationResult | None, str | None]:
    """Run `validator.validate` behind the containment barrier the module docstring describes.

    Returns `(result, None)` on success or `(None, reason)` on any failure at all — a well-formed
    `ReplayValidationError`, or a raw engine panic (a `BaseException` the Protocol deliberately
    never catches itself). Never *returns* by raising for either of those: that is the whole point
    of a barrier.

    `asyncio.CancelledError` is the one exception this barrier does not fold in (T055a) — it is
    re-raised, not swallowed. It inherits `BaseException` directly, exactly as `pyo3_runtime.
    PanicException` does, which is why a bare `except BaseException` looked correct here and is
    exactly what caught it before this was fixed: a task cancelled by the caller (a graceful
    shutdown, `apps/api/src/aoe2stats_api/routers/cron.py` returning mid-request) was folded into
    the same `quarantined` outcome as a genuine engine panic, terminally writing off a replay whose
    bytes were already durably committed (`_process_one`'s `_commit_blob_metadata`, this module's
    own write-ordering paragraph) to a server restart. Re-raising instead leaves the row exactly
    where that commit left it — `downloading`, `object_key`/`zip_sha256` already set — for the next
    cycle's reclaim (`_resume_reclaim`) to resume at validation, the sequence T044 and the
    write-ordering paragraph are built around.

    Clause order is the fix and must not change:

    1. `TimeoutError` first — `asyncio.wait_for`'s *own* wall-clock cap firing. This is the barrier
       containing a hung engine, not the barrier being cancelled, and must keep quarantining: the
       inner `asyncio.to_thread` call is cancelled by `wait_for` itself, not by anything external,
       and `wait_for` raises `TimeoutError` for that case specifically — never `CancelledError`.
    2. `asyncio.CancelledError` next, re-raised. Reached only when the coroutine *awaiting this
       call* — not `wait_for`'s internal timeout — was cancelled from outside. Must be checked
       ahead of the catch-all below, or it is caught there instead and this whole fix is silently
       undone by a reordering.
    3. `BaseException` last: everything else, including a `pyo3_runtime.PanicException` — the
       barrier proper.
    """
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(validator.validate, zip_bytes), timeout=timeout_seconds
        )
    except TimeoutError:
        return None, f"{_CAP_REASON_PREFIX}{timeout_seconds}{_CAP_REASON_SUFFIX}"
    except asyncio.CancelledError:
        raise
    except BaseException as exc:
        reason = str(exc)
        return None, f"{type(exc).__name__}: {reason}" if reason else type(exc).__name__
    return result, None


class CaptureDrain:
    """A `Stage` (`aoe2stats_ingester.run.Stage`): claim, download, store, checksum, validate,
    mark. See the module docstring for the write ordering, the containment barrier and how the
    reclaim path resumes at validation.

    Also a `RunScoped` (`aoe2stats_ingester.run.RunScoped`, T059c): the three alerts this class
    can raise (`rate_limited` via `drain_with_rate_limit_guard`, `validation_failed` via
    `_quarantine`, `expired_capture` via `_classify_not_found`) each need the calling run's own
    `ingest_run_id`, which `run_once` hands over through `bind_run` immediately before starting
    this stage — never through the constructor, since a `CaptureDrain` built once by
    `build_ingest_stages` (`apps/api/src/aoe2stats_api/ingest_stages.py`) can outlive the one run
    whose id a constructor argument would fix it to. `self._run_id` stays `None` for any caller
    that constructs this class directly and never calls `bind_run` — every already-landed test
    file that does exactly that keeps writing `ingest_run_id=None`, precisely its previous
    behaviour.
    """

    name = "drain"

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        replay_provider: ReplayProvider,
        object_store: _ObjectPut | None = None,
        validator: ReplayValidator | None = None,
        engine: ReplayValidator | None = None,
        alert_sink: AlertSink | None = None,
        validation_timeout_seconds: float = DEFAULT_VALIDATION_TIMEOUT_SECONDS,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_claim_age_seconds: float = DEFAULT_MAX_CLAIM_AGE_SECONDS,
        capture_budget_days: int = DEFAULT_CAPTURE_BUDGET_DAYS,
        replay_publication_grace_hours: int = DEFAULT_REPLAY_PUBLICATION_GRACE_HOURS,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        max_captures_per_user_per_run: int | None = None,
        quota_exempt_days: int | None = None,
    ) -> None:
        # `test_idempotency.py` names this keyword argument `engine`; every other test file names
        # it `validator`. Both are the same `ReplayValidator` (`aoe2stats_core.replay.validation`)
        # — see the module docstring's closing paragraph on why this module accepts both spellings
        # of one constructor rather than picking a winner and breaking three already-landed tests.
        #
        # Neither `object_store` nor a validator is required at construction time: T056's own
        # `test_failure_classification.py` constructs `CaptureStage` with neither, because none of
        # its scenarios ever reach a `ReplayBlob` (200) — only `NotFound`/`ProviderRateLimited`/
        # `ProviderUnavailable` (see that file's own module docstring). `_require_object_store` and
        # `_require_validator` below raise a clear error the moment the download/validate path
        # actually needs either and finds it missing, rather than forcing every caller of the 404
        # classification path to supply machinery it will never use.
        self._session_factory = session_factory
        self._replay_provider = replay_provider
        self._object_store = object_store
        self._validator = validator if validator is not None else engine
        self._alert_sink: AlertSink = (
            alert_sink if alert_sink is not None else _DatabaseAlertSink(session_factory)
        )
        self._validation_timeout_seconds = validation_timeout_seconds
        self._batch_size = batch_size
        self._max_claim_age_seconds = max_claim_age_seconds
        self._capture_budget_days = capture_budget_days  # accepted, stored, not read — see above
        self._replay_publication_grace_hours = replay_publication_grace_hours
        self._max_attempts = max_attempts  # accepted, stored, not read — T057 owns using it

        # T058's fairness cap (`quota.py`, FR-044): both or neither. A caller that means to enforce
        # the cap and forgot the exemption (or the reverse) gets a loud, immediate configuration
        # error rather than a cap silently applied with a nonsensical exemption window, or an
        # exemption silently applied with no cap to exempt anything from.
        if (max_captures_per_user_per_run is None) != (quota_exempt_days is None):
            raise TypeError(
                "CaptureDrain requires max_captures_per_user_per_run and quota_exempt_days "
                "together, or neither — the fairness cap (T058, FR-044) cannot be half-configured"
            )
        self._max_captures_per_user_per_run = max_captures_per_user_per_run
        self._quota_exempt_days = quota_exempt_days

        # T059c: unset until `run_once` (`run.py`) binds it — see the class docstring's `RunScoped`
        # paragraph. Every alert this class raises reads this attribute rather than a literal
        # `None`, so a caller that never binds a run id gets exactly the prior behaviour.
        self._run_id: uuid.UUID | None = None

    def bind_run(self, run_id: uuid.UUID) -> None:
        """Satisfies `aoe2stats_ingester.run.RunScoped` (T059c): called once by `run_once`,
        immediately before this stage's own `__call__`, so every alert this call raises carries
        the real `ingest_run_id` of the run it belongs to. See the class docstring for why this is
        a per-run bind rather than a constructor argument.
        """
        self._run_id = run_id

    def _quota_enabled(self) -> bool:
        return self._max_captures_per_user_per_run is not None

    def _require_object_store(self) -> _ObjectPut:
        if self._object_store is None:
            raise TypeError("CaptureDrain requires `object_store` to process a downloaded replay")
        return self._object_store

    def _require_validator(self) -> ReplayValidator:
        if self._validator is None:
            raise TypeError("CaptureDrain requires either `validator` or `engine`")
        return self._validator

    async def __call__(self, budget: Budget) -> Mapping[str, Any]:
        report: dict[str, int] = dict(_ZERO_COUNTERS)
        # A row a 404 reverts to `pending` (`_revert_to_pending`) is immediately eligible again by
        # its own `next_attempt_at` — T057's bounded-retry backoff is not this task's to add (see
        # the module docstring's "three-way 404 reading" paragraph). Without this set,
        # the very next `_claim_batch` in *this same* `__call__` would re-claim that identical row
        # and hammer it for the rest of the budget instead of moving on to the rest of the queue —
        # every id this cycle has already attempted, whatever the outcome, is excluded from every
        # further claim this same call makes; a *later* cycle (a fresh `__call__`) starts with an
        # empty set and is free to attempt it again. `_apply_quota` below adds a claimed-but-
        # quota-deferred id to this same set for exactly the same reason: it too was just handed
        # back to `pending`, and must not be immediately re-selected by this same `__call__`.
        attempted_ids: set[uuid.UUID] = set()
        # T058's fairness cap (`quota.py`): this run's own claim-ordered history of every row
        # `_claim_batch` has produced so far, whatever `_apply_quota` went on to decide about it —
        # `apply_quota` needs the whole prefix, in claim order, to compute each user's running
        # count correctly (see the module docstring's "per-user fairness cap" paragraph). Unused,
        # and never grown, when quota enforcement is off (`_quota_enabled()` is `False`).
        quota_candidates: list[ReplayCapture] = []

        async def handle_item(capture_id: uuid.UUID) -> None:
            outcome = await self._process_one(capture_id)
            attempted_ids.add(capture_id)
            report["captures_attempted"] += 1
            if outcome in report:
                report[outcome] += 1
            # `quarantined_total` (T055) and `expired_total` (T056) are the two outcomes that
            # always carry an alert of their own — `unavailable_total` deliberately does not
            # (`_classify_not_found`'s own docstring: the game's failure, not ours).
            if outcome in ("quarantined_total", "expired_total"):
                report["alerts_raised"] += 1

        # Budget checked between claims and never mid-claim (the module docstring's
        # `DEFAULT_BATCH_SIZE` note): once a claim has handed a row to `handle_item`, that row
        # runs to completion — download, upload, validate, mark — regardless of the budget.
        while not budget.expired:
            claimed_ids = await self._claim_batch(exclude_ids=attempted_ids)
            if not claimed_ids:
                break

            to_process = claimed_ids
            if self._quota_enabled():
                to_process = await self._apply_quota(claimed_ids, quota_candidates, attempted_ids)
                if not to_process:
                    # Every row this claim produced was over its owner's cap and has already been
                    # reverted to `pending` by `_apply_quota`. Nothing to hand to the rate-limit
                    # guard; move on to whatever the queue's next claim produces.
                    continue

            stopped = await drain_with_rate_limit_guard(
                to_process, handle_item, sink=self._alert_sink, run_id=self._run_id
            )
            if stopped:
                report["alerts_raised"] += 1
                break

        report["backlog_remaining"] = await self._backlog_remaining()
        return report

    # --- Quota (T058, FR-044) ------------------------------------------------------------------

    async def _apply_quota(
        self,
        claimed_ids: list[uuid.UUID],
        quota_candidates: list[ReplayCapture],
        attempted_ids: set[uuid.UUID],
    ) -> list[uuid.UUID]:
        """Filter one `_claim_batch` result down to what the per-user fairness cap still allows
        this cycle to process, growing `quota_candidates` — this run's own claim-ordered history —
        by the rows this claim just produced. See the module docstring's "fairness cap" paragraph
        for the full design; only called when `_quota_enabled()`.

        Every id in `claimed_ids` not present in the returned list has already been reverted to
        `pending` (`_revert_claim`) and added to `attempted_ids`, so it is left exactly as ready to
        be reclaimed by a *later* cycle as a fresh `pending` row ever is, and never reclaimed by
        this same `__call__` again.
        """
        assert self._max_captures_per_user_per_run is not None
        assert self._quota_exempt_days is not None

        async with self._session_factory() as session:
            result = await session.execute(
                select(ReplayCapture).where(ReplayCapture.id.in_(claimed_ids))
            )
            rows_by_id = {row.id: row for row in result.scalars().all()}
            quota_candidates.extend(rows_by_id[cid] for cid in claimed_ids if cid in rows_by_id)

            allowed = await apply_quota(
                session,
                quota_candidates,
                max_per_user=self._max_captures_per_user_per_run,
                exempt_days=self._quota_exempt_days,
                now=datetime.now(UTC),
            )

        allowed_ids = {row.id for row in allowed}
        to_process: list[uuid.UUID] = []
        for capture_id in claimed_ids:
            if capture_id in allowed_ids:
                to_process.append(capture_id)
            else:
                await self._revert_claim(capture_id)
                attempted_ids.add(capture_id)
        return to_process

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

        **The archival gate (T089a).** `discover.py`'s `_archiving_profile_ids()` and
        `_enqueue_capture`'s own link check keep a linked user's Art. 21 objection
        (`users.archival_objected_at IS NOT NULL`) from enqueueing a *new* `replay_captures` row
        once it has committed, but a row enqueued while archival was still active stays
        `pending` right through the objection — the queue between discovery and this claim can be
        days deep. Left alone, this claim's own status/`next_attempt_at` predicate has no archival
        clause of any kind and would download and store it anyway on the very next cycle, which is
        the exact edge case spec.md lists and `test_consent_withdrawal.py` asserts against.

        `_objecting` below is `_objecting_owner_exists()` — a correlated `EXISTS`, against this
        row's own `profile_id`, for the *currently active* link's owner having objected,
        `profile_links.unlinked_at IS NULL AND users.archival_objected_at IS NOT NULL`, joined the
        same way discovery joins it (`profile_links` to `users`), and shared with
        `revalidate_quarantined`'s selection — and this claim excludes exactly the rows it matches.
        Phrased as an exclusion, not `_archiving_profile_ids()`'s own inclusion, on purpose: that
        method's query only ever runs over profiles discovery already knows are linked, so "no
        active link" never arises there, but `replay_captures` carries rows with no such context at
        all (every capture-mechanics test in this package, seeded directly against
        `Match`/`ReplayCapture` with no `profile_links`/`users` rows to speak of, being the
        concrete case). A capture with no active, objecting owner on record is eligible exactly as
        it always was — only a *found* objection ever removes one from this claim, never the mere
        absence of ownership context.
        An already-`stored` row is never touched by this claim in the first place (its status is
        neither `pending` nor stale `downloading`), so this gate only ever stops a capture that has
        not yet fetched anything — objection stops further capture (FR-035); erasure, not this, is
        what removes what was already captured (FR-037).
        """
        now = datetime.now(UTC)
        stale_before = now - timedelta(seconds=self._max_claim_age_seconds)

        _objecting = _objecting_owner_exists()

        eligibility = and_(
            or_(
                and_(
                    ReplayCapture.status == CaptureStatus.PENDING,
                    ReplayCapture.next_attempt_at <= now,
                ),
                and_(
                    ReplayCapture.status == CaptureStatus.DOWNLOADING,
                    ReplayCapture.claimed_at.is_not(None),
                    ReplayCapture.claimed_at < stale_before,
                ),
            ),
            ~_objecting,
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
        mark. Returns the report key this outcome belongs under. A 404 that reverts to `pending`
        (still inside the grace, or past it but short of the two-attempt floor —
        `_classify_not_found`) answers `"not_found"`, which is not itself a report key: nothing
        this cycle concluded, so nothing in `report` moves for it.
        """
        async with self._session_factory() as session:
            capture = await session.get(ReplayCapture, capture_id)
        if capture is None:  # pragma: no cover - defensive: the claim just produced this id
            return "not_found"

        game_id, profile_id = capture.game_id, capture.profile_id

        if capture.object_key is not None and capture.zip_sha256 is not None:
            # Resumed reclaim: the previous, now-dead run's upload already committed the blob and
            # its metadata (FR-023's write ordering is what makes this survivable at all). See the
            # module docstring's "reclaim resumes at validation" paragraph.
            return await self._resume_reclaim(
                capture_id,
                object_key=capture.object_key,
                expected_sha256=capture.zip_sha256,
                game_id=game_id,
                profile_id=profile_id,
            )

        try:
            fetched = await self._replay_provider.fetch_replay(game_id, profile_id)
        except ProviderRateLimited:
            # A rate limit is a condition of the run, not an outcome of the capture it happened to
            # interrupt (`test_failure_classification.py`'s 429 scenario): undo the claim's own
            # attempt increment and hand the row back to `pending`, immediately eligible again,
            # rather than stranding it in `downloading` having silently counted an attempt it
            # never actually got to make. `drain_with_rate_limit_guard` (`ratelimit.py`) is what
            # turns this exception into the alert and the run-stopping decision; re-raising here
            # keeps that the one place either happens.
            await self._revert_claim(capture_id)
            raise
        except ProviderUnavailable as exc:
            # A 5xx, or a timeout/connection failure that outlived the provider's own retry
            # budget (`ProviderUnavailable`'s own docstring, `packages/providers/.../base.py`):
            # unlike `ProviderRateLimited` this *does* count as an attempt at this capture — the
            # claim's own increment stands — and is T057's bounded retry, not T056's rate-limit
            # handling: see `_handle_provider_unavailable` below.
            return await self._handle_provider_unavailable(
                capture_id, attempts=capture.attempts, reason=str(exc)
            )
        if isinstance(fetched, NotFound):
            return await self._classify_not_found(
                capture_id,
                fetched.http_status,
                attempts=capture.attempts,
                capture_deadline_at=capture.capture_deadline_at,
                game_id=game_id,
                profile_id=profile_id,
            )

        blob: ReplayBlob = fetched
        content = blob.content
        sha256 = hashlib.sha256(content).hexdigest()
        key = replay_object_key(game_id, profile_id)

        # Upload before any mark, never the reverse (the module docstring's non-negotiable
        # ordering). `object_key`/`zip_bytes`/`zip_sha256` are committed immediately after, while
        # the row is still `downloading`.
        await self._require_object_store().put(
            key, content, content_type=blob.content_type or REPLAY_CONTENT_TYPE
        )
        await self._commit_blob_metadata(capture_id, key, len(content), sha256)

        result, error = await _validate_with_barrier(
            self._require_validator(), content, timeout_seconds=self._validation_timeout_seconds
        )
        if result is not None:
            await self._mark_stored(capture_id, result)
            return "stored_total"

        reason = error or "validation failed for an unspecified reason"
        return await self._quarantine(capture_id, reason, game_id=game_id, profile_id=profile_id)

    async def _resume_reclaim(
        self,
        capture_id: uuid.UUID,
        *,
        object_key: str,
        expected_sha256: str,
        game_id: int,
        profile_id: int,
    ) -> str:
        """Resume a stale `downloading` row at validation, never at the download.

        `AoemsReplayProvider` is never called here — the whole point of a reclaim is that the
        bytes are already durable (the module docstring's non-negotiable write ordering). Reading
        them back and re-running them through the exact same containment barrier
        (`_validate_with_barrier`) the normal path uses is what closes the gap the module docstring
        used to describe: a process killed between the metadata commit and validation must not
        leave a row that reports `stored` with `validated_by` left null, and a malformed archive
        must still end up `quarantined` (FR-026) rather than silently counted in `stored_total`.

        Two failure shapes are possible here that the normal path never sees, because both are
        about bytes a *previous*, now-dead run wrote, not this run's own I/O — neither is allowed
        to crash the drain, so both fold into the same `quarantined` outcome the validation
        barrier itself uses for every other kind of failure:

        - the object is missing from the store entirely (deleted out from under the row, or never
          actually landed despite the row claiming it did);
        - the bytes read back do not hash to the `zip_sha256` already committed for this row
          (corruption at rest, or a record that was simply wrong).

        Either is treated as evidence the capture cannot be trusted, not as a reason to retry the
        download: `object_key`/`zip_sha256` are already committed, so a retry would only refetch
        and re-store a replay this row already believes it holds, without ever explaining why the
        bytes it already has do not check out.
        """
        content, integrity_reason = await self._read_back_verified(object_key, expected_sha256)
        if content is None:
            assert integrity_reason is not None
            return await self._quarantine(
                capture_id, integrity_reason, game_id=game_id, profile_id=profile_id
            )

        result, error = await _validate_with_barrier(
            self._require_validator(), content, timeout_seconds=self._validation_timeout_seconds
        )
        if result is not None:
            await self._mark_stored(capture_id, result)
            return "stored_total"

        reason = error or "validation failed for an unspecified reason"
        return await self._quarantine(capture_id, reason, game_id=game_id, profile_id=profile_id)

    @staticmethod
    def _read_back_failure_reason(object_key: str, exc: Exception) -> str:
        return (
            f"{_READ_BACK_REASON_PREFIX} {object_key!r} from the object store: "
            f"{type(exc).__name__}: {exc}"
        )

    async def _read_back_verified(
        self, object_key: str, expected_sha256: str, *, only_integrity_is_per_row: bool = False
    ) -> tuple[bytes | None, str | None]:
        """Read a committed object back and check it against the row's own `zip_sha256`.

        Returns `(content, None)` when the bytes are present and hash to `expected_sha256`, and
        `(None, reason)` for an integrity failure: the object cannot be read, or it hashes to
        something else. `reason` is the exact text a quarantine records.

        Two callers, two readings of "cannot be read". The reclaim path (default) quarantines the
        row on *any* store error. `revalidate_quarantined` passes `only_integrity_is_per_row`:
        only `ObjectNotFound` (the store's answer that no such object exists) is the row's own
        outcome; any other store error says nothing about the row (an outage, a denied request, a
        missing bucket) and raises `_StoreTransportError` instead, so nothing is written for it.
        Only `get` is called on the store.
        """
        try:
            content = await self._require_object_store().get(object_key)
        except ObjectNotFound as exc:
            return None, self._read_back_failure_reason(object_key, exc)
        except Exception as exc:
            if only_integrity_is_per_row:
                raise _StoreTransportError(type(exc).__name__) from exc
            return None, self._read_back_failure_reason(object_key, exc)
        actual_sha256 = hashlib.sha256(content).hexdigest()
        if actual_sha256 != expected_sha256:
            return None, (
                f"{_CHECKSUM_REASON_PREFIX} for {object_key!r}: row records {expected_sha256}, "
                f"object store holds {actual_sha256}"
            )
        return content, None

    async def revalidate_quarantined(
        self, *, limit: int, after: RevalidationCursor | None = None, dry_run: bool = False
    ) -> RevalidationReport:
        """T673: give captures that ended `quarantined` because the *engine* could not parse them
        a second validation, from the bytes already committed. Never re-downloads (the replay
        provider is not touched), never writes, replaces or deletes an object (`get` only), and
        raises no alert. Where the source's retention window sits is `docs/data-sources.md`'s to
        say; this method does not depend on it, the committed object is its only input.

        **Selection** (`_revalidation_selection`): `status = quarantined`, `object_key` and
        `zip_sha256` both set, `last_error` equal to the engine's own failure text
        (`_engine_failure_reason`: an `EngineParseError` or a `PanicException`, as
        `_validate_with_barrier` writes them), and the capture's owner has not objected to
        archival (`_objecting_owner_exists`, the claim's own predicate: a quarantined capture is
        not an archived one, so 001's carve-out for what was archived before an objection does not
        reach it). An integrity quarantine, a timeout and a `MalformedArchiveError` are outside it.
        Ordered by `(matches.completed_at, capture id)`, oldest recording first: an ordering, and
        nothing more is claimed for it. At most `limit` rows; `after` is the report's `cursor`, a
        `(completed_at, id)` pair compared exclusively as a row against that same key. The id is
        part of the cursor because two captures of one match share its `completed_at`: a timestamp
        alone would skip the ones a page cut between.

        **Per row**, the reclaim path's own steps (`_read_back_verified`, then the same barrier):

        - the object is missing, or does not hash to the row's `zip_sha256`: `integrity_failure`,
          no write at all. The bytes are not the ones the row vouches for, so they are neither
          marked `stored` nor given a new error. Any *other* store error stops the run
          (`aborted_by`) with that row unwritten;
        - the barrier returns a result: `stored`, written by `_mark_stored` as the normal path
          writes it (`validated_by`, `inner_filename`, `inner_bytes`); `stored_at` is the time of
          this re-validation, not of the original capture;
        - the barrier fails with a reason `_is_engine_failure_reason` accepts: `still_quarantined`
          with the new engine verdict in `last_error` (`_mark_quarantined`), and no
          `validation_failed` alert: the row raised one when it was first quarantined;
        - the barrier fails with any other reason (the wall-clock cap, a class outside the
          selection): `inconclusive`, nothing written, the reason reported. Writing it would
          replace the engine's text with one the selection does not match, and the row would not
          be offered again.

        Both writes are guarded on the row still being `quarantined`: one that another process
        changed meanwhile is `changed_elsewhere`, unwritten. A stored row is no longer selected; a
        row that fails again with an engine verdict is rewritten with that verdict, and one that
        ends `inconclusive` or `integrity_failure` is exactly as it was and is selected next run.

        `dry_run` lists the selection (outcome `selected`) without reading, validating or writing,
        and counts the `quarantined` rows outside it by `_reason_class` (`unselected_by_reason`).
        """
        if limit < 1:
            raise ValueError("limit must be at least 1")

        statement = (
            select(ReplayCapture, Match.completed_at)
            .join(Match, Match.game_id == ReplayCapture.game_id)
            .where(_revalidation_selection())
            .order_by(Match.completed_at.asc(), ReplayCapture.id.asc())
            .limit(limit + 1)
        )
        if after is not None:
            # The whole ordering key, compared as a row: `completed_at` alone would skip every
            # capture of a shared match (one `completed_at`, several profiles) that the previous
            # page cut between. The id only breaks ties; a later `completed_at` with a smaller id
            # is still after the cursor.
            statement = statement.where(
                tuple_(Match.completed_at, ReplayCapture.id)
                > tuple_(
                    literal(after[0], Match.completed_at.type),
                    literal(after[1], ReplayCapture.id.type),
                )
            )
        async with self._session_factory() as session:
            candidates = [
                (row, completed_at)
                for row, completed_at in (await session.execute(statement)).all()
            ]
            unselected = await self._count_unselected(session) if dry_run else None
        truncated = len(candidates) > limit
        candidates = candidates[:limit]

        outcomes: list[RevalidationOutcome] = []
        aborted_by: str | None = None
        for capture, completed_at in candidates:
            assert capture.object_key is not None and capture.zip_sha256 is not None
            outcome: RevalidationOutcomeKind
            reason: str | None = None
            if dry_run:
                outcome = "selected"
            else:
                try:
                    outcome, reason = await self._revalidate_one(
                        capture.id, capture.object_key, capture.zip_sha256
                    )
                except _StoreTransportError as exc:
                    aborted_by = str(exc)
                    break
            outcomes.append(
                RevalidationOutcome(
                    capture_id=capture.id,
                    game_id=capture.game_id,
                    profile_id=capture.profile_id,
                    completed_at=completed_at,
                    outcome=outcome,
                    reason=reason,
                )
            )
        return RevalidationReport(
            outcomes=tuple(outcomes),
            truncated=truncated,
            last_completed_at=outcomes[-1].completed_at if outcomes else None,
            last_capture_id=outcomes[-1].capture_id if outcomes else None,
            unselected_by_reason=unselected,
            aborted_by=aborted_by,
        )

    async def _count_unselected(self, session: AsyncSession) -> tuple[tuple[str, int], ...]:
        """`quarantined` rows outside `_revalidation_selection`, counted by `_reason_class`. Only
        the head of each `last_error` is read (a class name or a fixed prefix), never a whole
        reason: an engine panic's text can run to a backtrace."""
        # `coalesce`: a NULL `last_error` makes the selection NULL, and NOT NULL is NULL, which
        # would drop exactly the rows with no reason from the count.
        outside = ~func.coalesce(_revalidation_selection(), false())
        rows = await session.execute(
            select(
                func.left(ReplayCapture.last_error, _REASON_HEAD_CHARS),
                ReplayCapture.object_key.is_not(None) & ReplayCapture.zip_sha256.is_not(None),
                _objecting_owner_exists(),
            ).where(ReplayCapture.status == CaptureStatus.QUARANTINED, outside)
        )
        counts: dict[str, int] = {}
        for head, has_object, objecting in rows.all():
            label = _reason_class(head, has_object=bool(has_object), objecting=bool(objecting))
            counts[label] = counts.get(label, 0) + 1
        return tuple(sorted(counts.items()))

    async def _revalidate_one(
        self, capture_id: uuid.UUID, object_key: str, expected_sha256: str
    ) -> tuple[RevalidationOutcomeKind, str | None]:
        content, integrity_reason = await self._read_back_verified(
            object_key, expected_sha256, only_integrity_is_per_row=True
        )
        if content is None:
            return "integrity_failure", integrity_reason

        result, error = await _validate_with_barrier(
            self._require_validator(), content, timeout_seconds=self._validation_timeout_seconds
        )
        if result is not None:
            written = await self._mark_stored(
                capture_id, result, only_if_status=CaptureStatus.QUARANTINED
            )
            return ("stored", None) if written else ("changed_elsewhere", _CHANGED_ELSEWHERE)

        reason = error or "validation failed for an unspecified reason"
        if not _is_engine_failure_reason(reason):
            return "inconclusive", reason
        written = await self._mark_quarantined(
            capture_id, reason, only_if_status=CaptureStatus.QUARANTINED
        )
        return (
            ("still_quarantined", reason) if written else ("changed_elsewhere", _CHANGED_ELSEWHERE)
        )

    async def _quarantine(
        self, capture_id: uuid.UUID, reason: str, *, game_id: int, profile_id: int
    ) -> str:
        """Mark `capture_id` `quarantined` with `reason` and raise the severity-2 alert every
        quarantine outcome carries, whichever path (normal validation or reclaim) produced it.
        """
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
            run_id=self._run_id,
        )
        return "quarantined_total"

    async def _classify_not_found(
        self,
        capture_id: uuid.UUID,
        http_status: int,
        *,
        attempts: int,
        capture_deadline_at: datetime,
        game_id: int,
        profile_id: int,
    ) -> str:
        """T056: the three-way reading of a 404 from `matches.completed_at` — see the module
        docstring's "three-way 404 reading" paragraph for the full rationale, summarized here:

        1. Younger than `REPLAY_PUBLICATION_GRACE_HOURS`: revert to `pending`.
        2. Older than the grace but `capture_deadline_at` has not yet passed: revert to `pending`
           unless `attempts` has already reached `_MINIMUM_ATTEMPTS_BEFORE_UNAVAILABLE`, in which
           case `unavailable` — the game's failure, not ours, so no alert.
        3. Past `capture_deadline_at`: `expired`, on the first attempt that observes it, with a
           severity-1 `expired_capture` alert (`raise_alert`, T014a) — a replay now provably lost.

        `attempts` and `capture_deadline_at` are read from the same row `_process_one` already
        fetched for this claim (the claim itself already incremented `attempts`), so this method
        takes them as plain values rather than re-fetching the row a second time; only
        `matches.completed_at` — the one value `ReplayCapture` itself does not carry — is looked up
        here, by `game_id`.
        """
        async with self._session_factory() as session:
            completed_at = await session.scalar(
                select(Match.completed_at).where(Match.game_id == game_id)
            )
        # `replay_captures.game_id` is a `NOT NULL` foreign key to `matches.game_id` (models.py):
        # a claimed row's match is guaranteed to exist.
        assert completed_at is not None  # pragma: no cover - defensive, guaranteed by the FK

        now = datetime.now(UTC)
        grace_boundary = completed_at + timedelta(hours=self._replay_publication_grace_hours)

        if now < grace_boundary:
            await self._revert_to_pending(capture_id, http_status)
            return "not_found"

        if now > capture_deadline_at:
            await self._mark_expired(capture_id, http_status)
            await raise_alert(
                self._alert_sink,
                EXPIRED_CAPTURE_ALERT_KIND,
                EXPIRED_CAPTURE_ALERT_SEVERITY,
                {"capture_id": str(capture_id), "game_id": game_id, "profile_id": profile_id},
                run_id=self._run_id,
            )
            return "expired_total"

        if attempts >= _MINIMUM_ATTEMPTS_BEFORE_UNAVAILABLE:
            await self._mark_unavailable(capture_id, http_status)
            return "unavailable_total"

        await self._revert_to_pending(capture_id, http_status)
        return "not_found"

    async def _handle_provider_unavailable(
        self, capture_id: uuid.UUID, *, attempts: int, reason: str
    ) -> str:
        """T057: bounded retries for a `ProviderUnavailable` (a 5xx, or a timeout/connection
        failure that outlived the provider's own retry budget — `ProviderUnavailable`'s own
        docstring). `attempts` is the row's own count *after* `_claim_batch`'s increment for this
        very attempt, exactly as `_classify_not_found` reads it — this call already counts, so
        the boundary below decides only what happens next, never whether this one counted.

        - `attempts < self._max_attempts`: not yet exhausted. Revert to `pending` with
          `next_attempt_at` pushed `_retry_backoff_seconds(attempts)` into the future — a delay
          that strictly increases with `attempts` (FR-020) rather than repeating a fixed
          interval — so the next claim leaves this row alone until its own backoff elapses.
        - `attempts >= self._max_attempts`: the bounded-retry ceiling. Terminal `failed`, never a
          further backoff (FR-020's "MUST stop after a bounded number of attempts"). `failed`
          means the game itself was reachable but this system could never get the bytes — a
          different failure than `quarantined` (bytes obtained, unparsable) or `expired` (the
          source itself confirms the replay is gone) — and, per data-model.md's five-alert-kind
          vocabulary, `failed` is not one of them: unlike `quarantined`/`expired`, nothing here
          raises. A human reviewing `failed_total` is the intended signal, not an alert queue that
          a merely transient source outage would otherwise flood.
        """
        if attempts >= self._max_attempts:
            await self._mark_failed(capture_id, reason)
            return "failed_total"

        delay = self._retry_backoff_seconds(attempts)
        await self._revert_to_pending_with_backoff(capture_id, delay=delay, reason=reason)
        return "not_found"

    def _retry_backoff_seconds(self, attempts: int) -> timedelta:
        """Exponential backoff, doubling per attempt: `_RETRY_BACKOFF_BASE_SECONDS * 2 **
        (attempts - 1)`. `attempts` is always >= 1 (a row only ever reaches here after
        `_claim_batch` has incremented it at least once), so this never raises on a negative
        exponent.
        """
        return timedelta(seconds=_RETRY_BACKOFF_BASE_SECONDS * (2 ** (attempts - 1)))

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
        self,
        capture_id: uuid.UUID,
        result: ReplayValidationResult | None,
        *,
        only_if_status: CaptureStatus | None = None,
    ) -> bool:
        """Mark `stored`. `only_if_status` guards the write on the row's current status (T673's
        re-validation, which must not overwrite a row another process moved); returns whether a
        row was written. Unguarded, it matches the id alone, as before."""
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
        statement = update(ReplayCapture).where(ReplayCapture.id == capture_id).values(**values)
        if only_if_status is not None:
            statement = statement.where(ReplayCapture.status == only_if_status)
        async with self._session_factory() as session:
            outcome = await session.execute(statement)
            await session.commit()
        return bool(outcome.rowcount)  # type: ignore[attr-defined]

    async def _mark_quarantined(
        self,
        capture_id: uuid.UUID,
        reason: str,
        *,
        only_if_status: CaptureStatus | None = None,
    ) -> bool:
        """Mark `quarantined` with `reason`; `only_if_status` and the return as `_mark_stored`."""
        statement = (
            update(ReplayCapture)
            .where(ReplayCapture.id == capture_id)
            .values(status=CaptureStatus.QUARANTINED, last_error=reason)
        )
        if only_if_status is not None:
            statement = statement.where(ReplayCapture.status == only_if_status)
        async with self._session_factory() as session:
            outcome = await session.execute(statement)
            await session.commit()
        return bool(outcome.rowcount)  # type: ignore[attr-defined]

    async def _revert_to_pending(self, capture_id: uuid.UUID, http_status: int) -> None:
        """A 404 `_classify_not_found` (T056) read as inconclusive — still inside the publication
        grace, or past it but short of the two-attempt floor: the row goes straight back to
        `pending`, immediately eligible (`next_attempt_at=now`), so a later cycle tries again
        rather than this one guessing `unavailable`/`expired` too early.
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
                        "replay not found at source (404); too soon to conclude unavailable or "
                        "expired (T056)"
                    ),
                )
            )
            await session.commit()

    async def _revert_to_pending_with_backoff(
        self, capture_id: uuid.UUID, *, delay: timedelta, reason: str
    ) -> None:
        """T057's not-yet-exhausted branch of `_handle_provider_unavailable`: the row goes back to
        `pending`, exactly as `_revert_to_pending` (T056) does for an inconclusive 404, but with
        `next_attempt_at` pushed `delay` into the future rather than left immediately eligible —
        the whole point of a *backoff*, versus T056's "try again on a later cycle regardless".
        `http_status` is left untouched: `ProviderUnavailable` is not always a specific status
        code (a timeout or connection failure carries none), so unlike the 404 branches this does
        not overwrite whatever status the row already recorded from a previous attempt.
        """
        async with self._session_factory() as session:
            await session.execute(
                update(ReplayCapture)
                .where(ReplayCapture.id == capture_id)
                .values(
                    status=CaptureStatus.PENDING,
                    claimed_at=None,
                    next_attempt_at=datetime.now(UTC) + delay,
                    last_error=reason,
                )
            )
            await session.commit()

    async def _mark_failed(self, capture_id: uuid.UUID, reason: str) -> None:
        """T057's exhausted branch of `_handle_provider_unavailable`: the bounded-retry ceiling
        reached, terminal `failed` (FR-020) — never a further backoff. `attempts`/`claimed_at` are
        left as the claim already set them, exactly as `_mark_stored`/`_mark_quarantined`/
        `_mark_expired` do for their own terminal outcomes.
        """
        async with self._session_factory() as session:
            await session.execute(
                update(ReplayCapture)
                .where(ReplayCapture.id == capture_id)
                .values(status=CaptureStatus.FAILED, last_error=reason)
            )
            await session.commit()

    async def _mark_expired(self, capture_id: uuid.UUID, http_status: int) -> None:
        """`_classify_not_found` (T056), third branch: past `capture_deadline_at` with no replay
        ever found — a provable, permanent loss. `attempts`/`claimed_at` are left as the claim
        already set them, exactly as `_mark_stored`/`_mark_quarantined` do for their own terminal
        outcomes; only `status`, `http_status` and `last_error` change here.
        """
        async with self._session_factory() as session:
            await session.execute(
                update(ReplayCapture)
                .where(ReplayCapture.id == capture_id)
                .values(
                    status=CaptureStatus.EXPIRED,
                    http_status=http_status,
                    last_error=(
                        "replay never became available at source before capture_deadline_at (404)"
                    ),
                )
            )
            await session.commit()

    async def _mark_unavailable(self, capture_id: uuid.UUID, http_status: int) -> None:
        """`_classify_not_found` (T056), second branch: past the publication grace, still inside
        `capture_deadline_at`, and at least `_MINIMUM_ATTEMPTS_BEFORE_UNAVAILABLE` attempts have
        each found nothing — the game's own failure to ever publish the replay, not this system's,
        so unlike `_mark_expired` this raises no alert.
        """
        async with self._session_factory() as session:
            await session.execute(
                update(ReplayCapture)
                .where(ReplayCapture.id == capture_id)
                .values(
                    status=CaptureStatus.UNAVAILABLE,
                    http_status=http_status,
                    last_error=(
                        "replay not found at source after the publication grace and at least "
                        f"{_MINIMUM_ATTEMPTS_BEFORE_UNAVAILABLE} attempts (404)"
                    ),
                )
            )
            await session.commit()

    async def _revert_claim(self, capture_id: uuid.UUID) -> None:
        """Undo `_claim_batch`'s own `status`/`claimed_at`/`attempts` writes for one claimed row,
        so whichever reason this is called for never counts as, or looks like, a real attempt at
        capturing that replay.

        Two callers, both undoing a claim for a reason that has nothing to do with the capture
        itself: the `ProviderRateLimited` branch of `_process_one`'s fetch (the row happened to be
        claimed right before the whole run stopped on a 429), and `_apply_quota` (T058, FR-044 —
        the row's owner was already over the per-run fairness cap, so this run never even attempts
        it). Both leave the row immediately eligible again (`next_attempt_at` untouched, already
        `<= now` from before this claim), for a caller that also excludes the id from this same
        cycle's own further claims to decide when it may be reclaimed.
        """
        async with self._session_factory() as session:
            await session.execute(
                update(ReplayCapture)
                .where(ReplayCapture.id == capture_id)
                .values(
                    status=CaptureStatus.PENDING,
                    claimed_at=None,
                    attempts=ReplayCapture.attempts - 1,
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
