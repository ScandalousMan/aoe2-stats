"""`run_once(...)` — one match, on one request (T365).

`apps/analyzer/tests/test_run_once.py` (T364) is this module's own specification, written first
and exercised against every function here — quickstart scenarios 7, 8 and 10. This module knows
nothing about its caller: it takes every session, provider, extractor and object store it needs as
an explicit argument (the same discipline `admission.py`, `claim.py` and `retain.py` already carry
in this package), and its only opinion about the platform it runs on is `budget_seconds` itself,
which it uses as the claim's own lease duration (see below) — never a re-read of a setting from the
environment, and never an HTTP concern. `api/analyze.py` (T366) is the one place this function is
ever called from in production, and it is free to translate whatever `run_once` leaves in
`match_analyses` into a response; this function returns nothing, because — as
`test_run_once.py`'s own module docstring states — every assertion about what one call did reads
the row back from `match_analyses`, `retained_recordings` or `replay_access_log` directly, never a
return value.

**The write ordering FR-029 and `data-model.md`'s `replay_access_log` section require**: a
`replay_access_log` row carrying `retained_recording_id` is written for *every* read of a retained
recording — first analysis and recompute alike — **before any engine is loaded**. Both paths below
call `_log_access` immediately after the bytes to be parsed are in hand (freshly retained, or
freshly retrieved from what was already retained) and strictly before `extract.build_document`
ever runs, which is the one call in this module that loads an engine.

**Two paths, not one state machine.** `claim.py`'s own claiming query only ever recognises a row
that is `queued`, or `running` under an expired lease (R6/R12) — it has no idea what a
`published`-but-stale row is, and it must not: recompute is not a resumption of interrupted work,
it is a second, independent read of bytes this service already holds, triggered only by a person
opening that match again after the engine version changed (FR-041, FR-044). So a `published` row
that turns out to be stale is handled entirely inside this module, never through `claim_for_
analysis` — the two paths converge only at their tail, `_publish`, which is the one place either
one ever writes a result.

**Availability is derived, never probed (R8, FR-034).** A match that has no `match_analyses` row
yet and completed further back than `capture_budget_days` is marked `unavailable` without ever
calling `replay_provider` — the same reasoning `apps/api/src/aoe2stats_api/availability.py` already
applies to a download's own four-state view, for the same reason (`docs/data-sources.md` §2: there
is no cheap existence probe, so asking the source at all means a full download). `capture_budget_
days` carries no default in that sibling module, deliberately, so a value can only ever come from
configuration — this module's own default below exists only because `test_run_once.py`'s already-
committed call sites do not thread the setting down; a real caller (`api/analyze.py`) is expected
to pass its own `Settings.capture_budget_days` here explicitly, exactly as it does for `admission.
py`'s gates, overriding this default entirely in production.

**A recording that fails to parse never retries (FR-036).** `failed`, `unavailable` and `refused`
are all treated as terminal from this function's own point of view: a second call against a `failed`
row is a no-op, matching `test_an_unparsable_recording_fails_on_the_first_attempt_and_is_never_
retried`'s own `max_calls=1` fakes, which turn a retry into a hard test failure rather than a
silently-passing assertion.

**A recompute that cannot complete keeps what it was replacing (T666c, FR-042).** `failed` is
003's answer for a first analysis, which has nothing to fall back on. A recompute is replacing an
analysis that is being served, so a refused document, a placement error, a parse failure, an
unloadable knowledge snapshot, a serialiser refusal or a gap row the table refuses is logged and
the row stays `published` on its previous key, digest and build (`_keep_prior`). The same causes
on a first analysis end `failed` - none of them leaves the row `running`, which would let its
lease expire and the next request fetch the recording from the source again.

**A broken deployment is refused before anything is claimed (T666h).** The faults that are facts
about the deployment rather than about one recording - an installed snapshot that does not load or
verify, two promoted snapshots for one build, an empty dependency record - raise `DeploymentFault`
before `claim_for_analysis`, so nothing is fetched from the source, retained, logged or written and
the match is not `failed`: the next request after the fix is a first analysis like any other.
Reaching the failure routing above for a snapshot fault now means only one a particular build can
reach.

**A recording that cannot be recomputed is served, never unpublished (T666i, FR-042).** A published
row with no retained-recording row is not stale (`staleness.is_stale`), and `_recompute` meeting the
same absence - a row deleted between the verdict and the read - leaves the row alone. Nothing
unpublishes a served analysis: `_mark_unavailable` refuses a `published` row, and `_mark_failed` is
reached from a first analysis only. On the recompute path a retained object that fails its checksum
(`RecordingIntegrityError`) or that the store reports missing (`ObjectNotFound`) is a fact about the
retained recording, so repeating it only costs a store read per click: both take `_keep_prior` and
its retry window. A transient store error (an outage) says nothing about the recording and still
propagates with no window. Every read of retained bytes is logged (`_log_access`) before its
checksum is judged (FR-029) - `retrieve_recording`'s `on_read` - so a read that fails the check
leaves its row; a read the store could not serve leaves none, because nothing was read. The first
analysis never reads retained bytes back (it parses the bytes it has just fetched), so it has no
checksum to precede.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_analyzer.claim import claim_for_analysis
from aoe2stats_analyzer.extract import (
    DEPLOYMENT_FAULT_ERRORS,
    DeploymentFault,
    SnapshotError,
    build_document,
    canonical_bytes,
    current_identity_digest,
    document_recording_build,
    validate_document,
    verify_deployment,
)
from aoe2stats_analyzer.retain import (
    RecordingIntegrityError,
    retain_recording,
    retrieve_recording,
)
from aoe2stats_analyzer.staleness import is_stale
from aoe2stats_core.replay.analysis import AnalysisExtractor
from aoe2stats_providers.base import NotFound, ReplayProvider
from aoe2stats_storage.models import (
    Match,
    MatchAnalysis,
    MatchAnalysisState,
    MatchPlayer,
    ReplayAccessLog,
    RetainedRecording,
)
from aoe2stats_storage.objects import ObjectNotFound, ObjectStore, analysis_object_key
from aoe2stats_storage.repositories.base import session_scope
from aoe2stats_storage.repositories.knowledge_gaps import (
    WHOLE_BUILD_ENTITY_ID,
    WHOLE_BUILD_ENTITY_KIND,
    WHOLE_BUILD_FIELD,
    GapToRecord,
    KnowledgeGapsRepository,
)

#: One logger named for the package, as `apps/api` and `apps/ingester` do, so a deployment's log
#: aggregator groups every line this package emits under one name.
logger = logging.getLogger("aoe2stats_analyzer")

#: `.env.example`'s own `CAPTURE_BUDGET_DAYS` — the module docstring's paragraph on `capture_
#: budget_days` explains why this exists only as a fallback for a caller (this package's own test
#: suite) that does not thread the real setting down, and why a production caller overrides it.
_DEFAULT_CAPTURE_BUDGET_DAYS = 21

#: `replay_access_log.purpose` for a read this module performs — distinct from `"download"`
#: (`apps/api/src/aoe2stats_api/routers/replays.py`), the only other writer of that column today,
#: because a system read of a third party's recording is never a download (R8, data-model.md).
_ANALYSIS_PURPOSE = "analysis"
_RECOMPUTE_PURPOSE = "recompute"

#: How long a published row is left alone after a recompute of it was refused (T666c). A refusal is
#: a function of the retained recording and the code, so asking again at once repeats it - yet the
#: row's digest still differs from the current one, so without a bound every request for the match
#: would read the retained recording, log an access and parse it in full. Kept in the row's own
#: `lease_expires_at` (a published row has no other use for it); one parse per window per match.
#: The deployed figure is configuration (T666j, constitution XII): `Settings.
#: analysis_recompute_retry_seconds`, which `api/analyze.py` passes as `recompute_retry_after`.
#: This is only the default for a caller that threads nothing down (the tests), as
#: `_DEFAULT_CAPTURE_BUDGET_DAYS` is. Only this writer needs the duration: the window's end is
#: stored on the row, and the readers (`staleness.retry_window_open`, hence the API's `stale` flag)
#: compare that stored instant with now.
_DEFAULT_RECOMPUTE_RETRY_AFTER = timedelta(hours=1)

#: States a second call against an existing row must treat as terminal, doing nothing further —
#: `failed` never retries (FR-036), `unavailable` cannot become obtainable again by asking twice
#: (FR-034), and `refused` (FR-047) is not reopened by this function, which holds no admission
#: gate of its own (`admission.py`'s own docstring: a later caller applies it before ever reaching
#: here).
_TERMINAL_STATES = (
    MatchAnalysisState.FAILED,
    MatchAnalysisState.UNAVAILABLE,
    MatchAnalysisState.REFUSED,
)


def gap_rows(document: Mapping[str, Any]) -> tuple[GapToRecord, ...]:
    """The `analysis_knowledge_gaps` rows for a document: one per entry of its `knowledge_gaps`
    block, read **from the document** (T662).

    The rows are derived from the published list rather than from a second call to the coverage
    pass, so the two cannot disagree: whatever the reader of the document is told is what the
    aggregate report counts. Nothing is recomputed, deduplicated or dropped here (the coverage pass
    already emits at most one gap per unique-index key, T652k/T652v); a gap that names no entity and
    no field - the whole-build `no-snapshot-for-build` gap - is stored under the storage layer's
    whole-build sentinels because those columns are not nullable, and carries `build` as the
    document does, `-1` where the stream named none.

    It lives here and not in `extract.py` (T666e): the document builder knows no table, and the
    conversion to rows is the publish step's own.
    """
    rows: list[GapToRecord] = []
    for gap in document["knowledge_gaps"]:
        entity = gap["entity"]
        rows.append(
            GapToRecord(
                build=gap["build"],
                entity_kind=WHOLE_BUILD_ENTITY_KIND if entity is None else entity["kind"],
                entity_id=WHOLE_BUILD_ENTITY_ID if entity is None else entity["id"],
                field=WHOLE_BUILD_FIELD if gap["field"] is None else gap["field"],
                civilisation_id=gap["civilisation"],
                cause=gap["cause"],
                severity=gap["severity"],
            )
        )
    return tuple(rows)


def _log_deployment_fault(game_id: int, fault_class: str, detail: str) -> None:
    """The operator's line for a refused request: the class and the detail, which a response never
    carries (`extract.DeploymentFault`)."""
    logger.error(
        "deployment fault, request refused before any claim or fetch: game_id=%s %s: %s",
        game_id,
        fault_class,
        detail,
    )


async def _is_stale(
    session_factory: async_sessionmaker[AsyncSession],
    analysis: MatchAnalysis,
    *,
    extractor: AnalysisExtractor,
    now: datetime,
) -> bool:
    """FR-042, T657a, T666b, T666g: whether this published row is to be recomputed now.

    **The verdict is `staleness.is_stale`'s, shared with the API** so the Recompute button and this
    decision cannot disagree: a row is stale when the identity it was produced under is not the
    identity an analysis would carry now - any of parser, dependencies, knowledge or analytics - and
    no retry window (T666c) is open. This function only loads the retained-recording row that
    verdict needs.

    **The current digest is computed from the database alone; the object store is never read.** Its
    inputs are the row's `recording_build`, the retained recording's object key and checksum (the
    `retained_recordings` row `_recompute` reads anyway - the same two values the identity's
    `recording` component was built from) and the running extractor. A request on a fresh match
    therefore does the row reads it did before this feature, and a store outage cannot turn it into
    a 500 (SC-006).

    A row with no stored digest or no recorded build was published before this feature and reads as
    stale: it recomputes once. A published row with nothing retained is not stale (T666i): a
    recording that cannot be recomputed is served as it is and never unpublished.

    **A deployment fault is never read as staleness; it is raised as `DeploymentFault` (T666m).**
    An error computing the current digest that is in `DEPLOYMENT_FAULT_ERRORS` - a snapshot that
    cannot be loaded or fails its digest, a packaged file that is missing, an empty dependency
    record - is a fault of the deployment. Reading it as "stale" cost a retained-recording read, an
    access-log row and a full parse on every click, then failed anyway; it is raised before any of
    that. It is `DeploymentFault` and not the raw exception so that the one caller that answers a
    person (`api/analyze.py`) has one class to map to its `analysis_deployment_fault` envelope, the
    same answer a first analysis gets from `verify_deployment`. Anything else propagates unchanged:
    a defect is not a deployment fault.

    Equal digests mean fresh, so an unchanged identity never reaches `_recompute` and a key, once
    written, is never written again.
    """
    async with session_factory() as session:
        retained = await _retained_recording_row(
            session, game_id=analysis.game_id, profile_id=analysis.point_of_view_profile_id
        )
    try:
        return is_stale(analysis, retained, engine=extractor, now=now)
    except DEPLOYMENT_FAULT_ERRORS as exc:
        _log_deployment_fault(analysis.game_id, type(exc).__name__, str(exc))
        raise DeploymentFault(type(exc).__name__, str(exc)) from exc


def _now() -> datetime:
    return datetime.now(UTC)


async def _pick_point_of_view_profile_id(
    session_factory: async_sessionmaker[AsyncSession], *, game_id: int
) -> int:
    """The participant this call fetches a recording for — any one of them, deterministically:
    the parsed timeline carries every participant's own data regardless of whose point of view the
    physical file is (`contracts/analysis.md`), so the choice only has to be stable, not special.
    Ordered by `team_id` then `profile_id`, which happens to match this package's own seeded fixture
    order (`test_run_once.py`'s `_seed_match`) without being written to depend on it.
    """
    async with session_factory() as session:
        result = await session.execute(
            select(MatchPlayer.profile_id)
            .where(MatchPlayer.game_id == game_id)
            .order_by(MatchPlayer.team_id, MatchPlayer.profile_id)
            .limit(1)
        )
        profile_id = result.scalar_one_or_none()
    if profile_id is None:
        raise LookupError(f"no match_players row for game_id={game_id}")
    return profile_id


async def _retained_recording_row(
    session: AsyncSession, *, game_id: int, profile_id: int
) -> RetainedRecording | None:
    result = await session.execute(
        select(RetainedRecording).where(
            RetainedRecording.game_id == game_id,
            RetainedRecording.profile_id == profile_id,
        )
    )
    return result.scalar_one_or_none()


async def _log_access(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    retained_recording_id: UUID,
    user_id: UUID,
    purpose: str,
) -> None:
    """FR-029: one `replay_access_log` row, `retained_recording_id` set and `replay_capture_id`
    null (the check constraint `data-model.md` pins down), for one read of a retained recording.
    Called before `extract.build_document` ever runs — see the module docstring's ordering
    paragraph.
    """
    async with session_scope(session_factory) as session:
        session.add(
            ReplayAccessLog(
                retained_recording_id=retained_recording_id,
                user_id=user_id,
                purpose=purpose,
            )
        )


async def _mark_unavailable(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    game_id: int,
    point_of_view_profile_id: int,
    requested_by_user_id: UUID,
    now: datetime,
) -> None:
    """FR-034: permanently `unavailable`, never presented as an action that then fails. Handles
    both the never-attempted case (no row yet — R8's expired-and-never-analysed match) and a row
    already claimed whose fetch just answered `NotFound`.

    **Never unpublishes (T666i, FR-042).** A `published` row is a served analysis; whatever route
    reached here - none does today, the first-analysis path claims only a `queued` or expired
    `running` row - it is left exactly as it was.
    """
    async with session_scope(session_factory) as session:
        # The guard is in the statement, not in a read before it: a publish that commits between a
        # read and this write would otherwise be overwritten (T666n).
        result = await session.execute(
            update(MatchAnalysis)
            .where(
                MatchAnalysis.game_id == game_id,
                MatchAnalysis.state != MatchAnalysisState.PUBLISHED,
            )
            .values(
                state=MatchAnalysisState.UNAVAILABLE,
                finished_at=now,
                result_key=None,
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount == 0 and await session.get(MatchAnalysis, game_id) is None:  # type: ignore[attr-defined]
            session.add(
                MatchAnalysis(
                    game_id=game_id,
                    state=MatchAnalysisState.UNAVAILABLE,
                    point_of_view_profile_id=point_of_view_profile_id,
                    requested_by_user_id=requested_by_user_id,
                    requested_at=now,
                    finished_at=now,
                )
            )


async def _mark_failed(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    game_id: int,
    error_class: str,
    error_message: str,
    now: datetime,
) -> None:
    """FR-036: `failed`, with the full error class and message recorded, for a claimed first
    analysis — the caller (`run_once` below) never calls this a second time for the same row,
    because a `failed` row is one of `_TERMINAL_STATES` and short-circuits before any fetch or
    parse.

    **Never unpublishes (T666m, FR-042).** A `published` row is a served analysis and is left
    exactly as it was, as `_mark_unavailable` leaves it (T666i). The recompute path never reaches
    here, but a lease overrun can: the lease (240 s) is shorter than the invocation's `maxDuration`
    (300 s), so run A can outlive its lease, run B can claim the row, A can publish, and B's refusal
    then arrives at a row that is no longer B's. The refusal belongs to a claim that was lost.
    """
    async with session_scope(session_factory) as session:
        # The guard is in the statement, not in a read before it: a publish that commits between a
        # read and this write would otherwise be overwritten (T666n).
        result = await session.execute(
            update(MatchAnalysis)
            .where(
                MatchAnalysis.game_id == game_id,
                MatchAnalysis.state != MatchAnalysisState.PUBLISHED,
            )
            .values(
                state=MatchAnalysisState.FAILED,
                finished_at=now,
                error_class=error_class,
                error_message=error_message,
                result_key=None,
            )
            .execution_options(synchronize_session=False)
        )
        if (
            result.rowcount == 0  # type: ignore[attr-defined]
            and await session.get(MatchAnalysis, game_id) is None
        ):  # pragma: no cover - defensive: this row was just claimed above
            raise LookupError(f"no match_analyses row for game_id={game_id} to mark failed")


#: The two steps of `_publish` that can be refused for a reason about the document, named in what
#: the person who asked is shown (T666i): a refused row update is not a refused gap insert.
_STEP_ROW_UPDATE = "the analysis row for this match could not be updated"
_STEP_GAP_ROWS = "the knowledge gaps of this analysis could not be recorded"


class _PublishRefused(Exception):
    """A step of `_publish` the database refused for a reason about this document: the
    `match_analyses` update (a value its columns refuse) or the gap insert (a data or integrity
    error from the insert itself, or a value outside the closed cause and severity sets). `step` is
    the sentence naming which one. Raised by `_publish` before anything is written to the object
    store. A connection-level error is deliberately *not* wrapped: it is transient, says nothing
    about this document, and must not turn into a terminal `failed`."""

    def __init__(self, step: str, cause: Exception) -> None:
        super().__init__(f"{step}: {type(cause).__name__}")
        self.step = step
        self.cause = cause


async def _publish(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    object_store: ObjectStore,
    game_id: int,
    document: Mapping[str, Any],
    payload: bytes,
    result_key: str,
    now: datetime,
) -> None:
    """FR-031/FR-032: write the analysis object and mark the row `published`, carrying which point
    of view and which parser version produced it. Shared by both the first-analysis and the
    recompute path - the one place either one ever writes a result, which is what keeps
    `result_key`'s own shape (`analysis_object_key`) identical whichever path reached it.

    `identity_digest` records which identity the current document was produced under (T657);
    `_is_stale` compares it with the identity an analysis would carry now (T657a). `recording_build`
    records the build the document's knowledge record names (`-1` where the stream named none), the
    one input of that comparison no other column holds (T666b). `lease_expires_at` is cleared: a
    published row holds no lease, and the claim's would otherwise read as a retry window to the
    recompute path (`_keep_prior`).

    Everything is read back from `document`, the object just written, so the row cannot name a
    parser the object does not. `engine_deps` is the same record the document carries (FR-044,
    T655) - the column has existed through two migrations and nothing wrote it before.

    **Two steps, named separately (T666i).** The row update is flushed, then the gap rows are
    inserted; a refusal of either raises `_PublishRefused` carrying the sentence for the step that
    failed, so the error recorded for the person who asked never blames the gap rows for the row.

    **The gap rows are written here, in this transaction (T662).** One `analysis_knowledge_gaps`
    row per entry of the document's `knowledge_gaps`, keyed by the identity digest and inserted
    insert-or-ignore, so a re-run of the same identity records nothing twice while a different
    identity adds rows of its own and leaves the earlier ones alone (FR-042). They commit with the
    row that publishes, so a publish that fails leaves no orphan gap row; and because a document
    the validator refused never reaches this function, a refused document records no gaps either.

    **The object is written after the rows are flushed and before they commit (T666c).** The insert
    is the one step here that can be refused for a reason about this document, and it runs first:
    if it is refused, the transaction rolls back (the row keeps what it had) and no object was
    written. A put that fails rolls the same transaction back, so no row ever names an object that
    was not written. The cost is one row lock held across the put, taken by the one request that is
    publishing this match.

    **A key is never written twice (T666d).** The put is a conditional create: when the key already
    exists nothing is written and the row is published at it, so the bytes a reader or a
    reproduction already saw cannot change under a second request or a retry.
    """
    async with session_scope(session_factory) as session:
        analysis = await session.get(MatchAnalysis, game_id)
        if analysis is None:  # pragma: no cover - defensive: this row was just claimed above
            raise LookupError(f"no match_analyses row for game_id={game_id} to publish")
        analysis.state = MatchAnalysisState.PUBLISHED
        analysis.point_of_view_profile_id = document["point_of_view_profile_id"]
        analysis.parser_name = document["engine"]["name"]
        analysis.parser_version = document["engine"]["version"]
        analysis.engine_deps = dict(document["engine"]["deps"])
        analysis.identity_digest = document["identity"]["digest"]
        analysis.recording_build = document_recording_build(document)
        analysis.result_key = result_key
        analysis.finished_at = now
        analysis.lease_expires_at = None
        analysis.error_class = None
        analysis.error_message = None
        # The row update is flushed on its own, first: left to the insert's autoflush it surfaced
        # inside the gap step, and a value `match_analyses` refused was reported as the gap rows.
        try:
            await session.flush()
        except (IntegrityError, DataError) as exc:
            raise _PublishRefused(_STEP_ROW_UPDATE, exc) from exc
        try:
            await KnowledgeGapsRepository(session).record_gaps(
                game_id=game_id,
                identity_digest=document["identity"]["digest"],
                gaps=gap_rows(document),
            )
            await session.flush()
        except (ValueError, IntegrityError, DataError) as exc:
            raise _PublishRefused(_STEP_GAP_ROWS, exc) from exc
        # FR-042, T666d: created only if the key is free. A key that is taken already holds the
        # analysis for this identity - the key is a function of it - written by a concurrent
        # request (the recompute path holds no lease) or by a run that crashed after this put and
        # before its commit. Its bytes differ from `payload` only in the wall clock, and a key,
        # once written, is never written again, so the row is published at the existing object.
        await object_store.put_if_absent(result_key, payload, content_type="application/json")


#: What a person is told when the replay engine crashed natively while reading their recording.
#: Fixed: the engine's own text is logged, never shown (`_describe`).
_ENGINE_CRASH_REASON = "the replay engine crashed while reading this recording"


def _describe(exc: BaseException) -> tuple[str, str]:
    """The class and message a refused analysis is recorded and logged under.

    `exc` is a `BaseException`, not an `Exception`, because a native engine panic
    (`pyo3_runtime.PanicException`) inherits `BaseException` directly and reaches here through
    `_extract_and_publish`'s barrier. The class recorded is always the real one
    (`type(exc).__name__`, e.g. `PanicException`), never a stand-in.

    A message is shown to the person who asked (`routers/matches.py` prints a `failed` row's
    `error_message` verbatim):

    - A `BaseException` that is not an `Exception` is a native crash, and its text is the engine's
      own, not ours: the measured `PanicException` message is ~770 characters of terminal escape
      codes, a backtrace and the engine's crate paths (T672a). It is recorded as its class and a
      fixed sentence; `_refuse` logs the full text, which is for the operator and never shown.
    - A snapshot error quotes the packaged knowledge files, and a database error embeds the SQL
      statement and its bound parameters: each is replaced by a fixed sentence, the class kept.
    - Everything else that is an `Exception` - a parse failure, a refused document, a placement or
      serialisation error - is recorded verbatim, as 003's failure path always recorded it; an
      empty message is recorded as the class name, so a `failed` row never shows a blank reason.
      Verbatim is not the same as written here: an `EngineParseError` quotes the engine's or the
      archive library's own text, which is shown.
    """
    if isinstance(exc, _PublishRefused):
        return type(exc.cause).__name__, exc.step
    if isinstance(exc, SnapshotError):
        return type(exc).__name__, "the knowledge snapshot for this recording could not be loaded"
    if not isinstance(exc, Exception):
        return type(exc).__name__, _ENGINE_CRASH_REASON
    return type(exc).__name__, str(exc) or type(exc).__name__


#: What computing a would-be digest may raise without that being a defect: a value error from the
#: identity (T666n) and every deployment fault (`current_identity_digest` raises those, T666m).
_WOULD_BE_DIGEST_ERRORS: tuple[type[Exception], ...] = (ValueError, *DEPLOYMENT_FAULT_ERRORS)


def _would_be_digest(
    extractor: AnalysisExtractor, *, object_key: str, zip_sha256: str, build: int | None
) -> str | None:
    """The identity digest the refused analysis would have carried, for the log line; `None` where
    it cannot be computed: no recorded build, or a deployment fault - an unloadable snapshot, a
    missing packaged file, an empty dependency record - which is often the very fault that refused
    the analysis. It runs after `_keep_prior` has committed, so it must never raise (T666n)."""
    if build is None:
        return None
    try:
        return current_identity_digest(
            extractor,
            recording={"object_key": object_key, "sha256": zip_sha256},
            build=build,
        )
    except _WOULD_BE_DIGEST_ERRORS:
        return None


async def _keep_prior(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    extractor: AnalysisExtractor,
    game_id: int,
    object_key: str,
    zip_sha256: str,
    error_class: str,
    error_message: str,
    now: datetime,
    retry_after: timedelta,
) -> None:
    """T666c, FR-042: a recompute that was refused leaves the analysis it was replacing exactly as
    it was served - same `state`, `result_key`, `identity_digest`, `recording_build` and
    `finished_at` - and writes nothing new. The refusal is logged, naming the match, the identity
    the row still carries, the one the new analysis would have carried and why it was refused.

    The only thing written is the retry window (`retry_after` long): the row's
    `lease_expires_at`, so the next request inside it is served without reading the retained
    recording or parsing it again. It is cleared by the next publish.
    """
    async with session_scope(session_factory) as session:
        analysis = await session.get(MatchAnalysis, game_id)
        if analysis is None:  # pragma: no cover - defensive: the caller found this row published
            raise LookupError(f"no match_analyses row for game_id={game_id} to keep")
        prior_digest = analysis.identity_digest
        prior_build = analysis.recording_build
        if analysis.state is MatchAnalysisState.PUBLISHED:
            analysis.lease_expires_at = now + retry_after
    logger.warning(
        "recompute refused, prior analysis kept: game_id=%s prior_identity_digest=%s "
        "would_be_identity_digest=%s retry_after_seconds=%d reason=%s: %s",
        game_id,
        prior_digest,
        _would_be_digest(
            extractor, object_key=object_key, zip_sha256=zip_sha256, build=prior_build
        ),
        int(retry_after.total_seconds()),
        error_class,
        error_message,
    )


async def _refuse(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    extractor: AnalysisExtractor,
    game_id: int,
    object_key: str,
    zip_sha256: str,
    exc: BaseException,
    now: datetime,
    keep_prior: bool,
    retry_after: timedelta,
) -> None:
    """An analysis that cannot be completed. A first analysis has nothing to keep and ends `failed`
    through 003's failure path; a recompute keeps what it was replacing (`_keep_prior`)."""
    error_class, error_message = _describe(exc)
    if not isinstance(exc, Exception):
        # The text `_describe` withheld from the row. A native engine crash carries the engine's
        # own message - terminal escape codes, a backtrace, crate paths - which is for whoever
        # operates this deployment and is shown to nobody else (T672a).
        logger.error(
            "replay engine crashed: game_id=%s %s: %s", game_id, type(exc).__name__, str(exc)
        )
    if keep_prior:
        await _keep_prior(
            session_factory,
            extractor=extractor,
            game_id=game_id,
            object_key=object_key,
            zip_sha256=zip_sha256,
            error_class=error_class,
            error_message=error_message,
            now=now,
            retry_after=retry_after,
        )
        return
    await _mark_failed(
        session_factory,
        game_id=game_id,
        error_class=error_class,
        error_message=error_message,
        now=now,
    )


async def _extract_and_publish(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    object_store: ObjectStore,
    extractor: AnalysisExtractor,
    game_id: int,
    zip_bytes: bytes,
    object_key: str,
    zip_sha256: str,
    now: datetime,
    keep_prior: bool,
    retry_after: timedelta,
) -> None:
    """The tail shared by both paths, from "bytes in hand" onward: parse, validate, and either
    publish or record why it could not. Never retried by this function's own caller - see
    `_TERMINAL_STATES`.

    **The document is validated before anything is written (FR-011, T656).** A document that breaks
    one of `contracts/analysis-document.md`'s rules is not published: no object is written and no
    row points at one. A `TierPlacementError` (the builder refusing to place a datum where its tier
    does not belong) is the first lock of the same rule.

    **What "not published" means depends on the path (T666c).** A first analysis has nothing to
    fall back on, so it ends `failed` through 003's `_mark_failed` with the error recorded. A
    recompute (`keep_prior`) is replacing an analysis that is being served, and FR-042 forbids
    destroying it: the refusal is logged and the row stays published (`_keep_prior`).

    **Every source this feature added is caught here, on both paths.** `ValueError` covers the
    refused document, the placement error, the unloadable snapshot (`SnapshotError`), the empty
    dependency record (FR-044) and the canonical serialiser's refusal (all `ValueError`s);
    `_PublishRefused` the row update or the gap insert. Left to propagate, a first analysis stays
    `running`, its lease expires, and the next request claims it again and fetches the recording
    from the source a second time - spending the source budget capture depends on (constitution I).
    A transient error (the object store, a lost connection) is still left to propagate: it says
    nothing about this recording.

    **The barrier (T671) sits around building, validating and serialising the document, and
    nowhere else.** That block is synchronous, writes nothing, and calls no network service,
    database or object store; the one thing it reads is the knowledge snapshot packaged with the
    deployment (`snapshot_for`), which `verify_deployment` checks before the claim. Whatever leaves
    it is about this recording, this code or this deployment, not a remote service. The barrier
    therefore contains a `BaseException`, as `aoe2stats_ingester.capture._validate_with_barrier`
    does on the capture path: the native engine's panic (`pyo3_runtime.PanicException`) inherits
    `BaseException` directly, so the `ValueError` clause never saw it, and it ended the request as
    a 500 with the row left `running` (production, 2026-10-05, game build 185872). A panic takes
    the same `_refuse` as any other refused document: `failed` on a first analysis, recorded with
    its class and a fixed sentence while its own text is logged (`_describe`), and the prior
    analysis kept on a recompute. Not contained:
    `asyncio.CancelledError`, `KeyboardInterrupt`, `SystemExit` and `GeneratorExit` are re-raised,
    because a cancelled request or a shutdown is not a verdict on the recording (the capture path's
    T055a lesson). `_publish` and the reads before this function are outside it, so a transient
    failure there propagates as before.

    **Any exception inside the barrier now ends a first analysis `failed`, terminally** (T672a).
    Before T671 an exception that was neither a `ValueError` nor a `ReplayValidationError` - a
    `MemoryError` from a recording too large to materialise, say - propagated: the row stayed
    `running`, its lease lapsed and the next request claimed it again. It is now recorded `failed`
    like any other refusal, and a `failed` row is not claimed again (`_TERMINAL_STATES`). That is
    deliberate: a retry would re-fetch the recording from the source, spending the budget capture
    depends on (constitution I), and an exception raised while reading this recording from bytes
    already in hand is most likely about the recording, so a second read of the same bytes would
    most likely raise it again. The cost is that a failure that was in fact transient is not
    retried either.
    """
    try:
        document = build_document(
            extractor,
            zip_bytes,
            game_id=game_id,
            object_key=object_key,
            zip_sha256=zip_sha256,
            extracted_at=now,
        )
        validate_document(document)
        # FR-041, T659: exactly the canonical bytes, so a reproduction compares against what was
        # stored. Serialised before anything is written: the serialiser can refuse.
        payload = canonical_bytes(document)
    except (asyncio.CancelledError, KeyboardInterrupt, SystemExit, GeneratorExit):
        # Clause order is the fix (T671; capture.py's T055a) and must not change. These four
        # inherit `BaseException` directly, exactly as a native engine panic does, so the
        # `BaseException` clause below would catch them too. They are listed first and re-raised so
        # that a cancelled request or a shutdown leaves the row as the claim left it instead of
        # being written down as a failed analysis; moving the catch-all above this clause silently
        # undoes that.
        raise
    except BaseException as exc:
        # The barrier proper: `ReplayValidationError` and `ValueError` as before, and a native
        # engine panic (a `BaseException`, see the docstring).
        #
        # A refused document caused by a *code* defect (a builder that places a datum where its
        # tier forbids, a serialiser refusal, a snapshot fault only this recording's build can
        # reach) cannot be checked in advance, so it stays on 003's failure path: a first analysis
        # ends `failed` (`_mark_failed`), a recompute keeps its prior analysis (`_keep_prior`).
        # What can be checked in advance is checked before the claim (`verify_deployment`, T666h).
        await _refuse(
            session_factory,
            extractor=extractor,
            game_id=game_id,
            object_key=object_key,
            zip_sha256=zip_sha256,
            exc=exc,
            now=now,
            keep_prior=keep_prior,
            retry_after=retry_after,
        )
        return

    # FR-042: the key carries the identity digest, so an analysis under a different identity is a
    # new object and the previous one is left exactly as it was. Nothing here ever deletes.
    result_key = analysis_object_key(game_id, document["identity"]["digest"])
    try:
        await _publish(
            session_factory,
            object_store=object_store,
            game_id=game_id,
            document=document,
            payload=payload,
            result_key=result_key,
            now=now,
        )
    except _PublishRefused as exc:
        await _refuse(
            session_factory,
            extractor=extractor,
            game_id=game_id,
            object_key=object_key,
            zip_sha256=zip_sha256,
            exc=exc,
            now=now,
            keep_prior=keep_prior,
            retry_after=retry_after,
        )


async def _recompute(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    object_store: ObjectStore,
    extractor: AnalysisExtractor,
    game_id: int,
    profile_id: int,
    requested_by_user_id: UUID,
    now: datetime,
    retry_after: timedelta,
) -> None:
    """FR-041/SC-009a: recompute a `published`-but-stale analysis from the recording this service
    already retained, reaching the source zero times. Reads `retained_recordings` and the object
    store only — `replay_provider` never appears in this function's own signature, which is what
    makes "zero calls to the source" true by construction rather than by discipline.
    """
    async with session_factory() as session:
        retained = await _retained_recording_row(session, game_id=game_id, profile_id=profile_id)
        if retained is None:
            # The verdict (`_is_stale`) already treats a published row with nothing retained as not
            # stale; this is the same answer for a row that vanished between that verdict and this
            # read. A recording that cannot be recomputed is served as it is: nothing is
            # unpublished (T666i, FR-042) and nothing is written.
            logger.warning(
                "recompute skipped, prior analysis kept: game_id=%s reason=no retained recording",
                game_id,
            )
            return
        object_key, zip_sha256 = retained.object_key, retained.zip_sha256

        async def log_read(row: RetainedRecording) -> None:
            # FR-029: written when the bytes arrive, before their checksum is judged, and before
            # `build_document` ever loads an engine (module docstring).
            await _log_access(
                session_factory,
                retained_recording_id=row.id,
                user_id=requested_by_user_id,
                purpose=_RECOMPUTE_PURPOSE,
            )

        try:
            zip_bytes = await retrieve_recording(
                session, object_store, game_id=game_id, profile_id=profile_id, on_read=log_read
            )
        except (RecordingIntegrityError, ObjectNotFound) as exc:
            # A fact about the retained recording, not about this request: asking again at once
            # repeats it at the price of a read per click, so it takes the keep-prior path and its
            # retry window (T666c). Any other store error - an outage - is transient, says nothing
            # about the recording, and propagates with no window.
            await _refuse(
                session_factory,
                extractor=extractor,
                game_id=game_id,
                object_key=object_key,
                zip_sha256=zip_sha256,
                exc=exc,
                now=now,
                keep_prior=True,
                retry_after=retry_after,
            )
            return

    await _extract_and_publish(
        session_factory,
        object_store=object_store,
        extractor=extractor,
        game_id=game_id,
        zip_bytes=zip_bytes,
        object_key=object_key,
        zip_sha256=zip_sha256,
        now=now,
        keep_prior=True,
        retry_after=retry_after,
    )


async def run_once(
    game_id: int,
    budget_seconds: float,
    requested_by_user_id: UUID,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    replay_provider: ReplayProvider,
    extractor: AnalysisExtractor,
    object_store: ObjectStore,
    capture_budget_days: int = _DEFAULT_CAPTURE_BUDGET_DAYS,
    recompute_retry_after: timedelta = _DEFAULT_RECOMPUTE_RETRY_AFTER,
) -> None:
    """Analyse `game_id` once, on this one request — see the module docstring for the two paths
    this dispatches between and the ordering FR-029 requires. Never raises on an ordinary outcome
    (a parse failure, an expired match, a lease held by someone else): every one of those is a
    normal return, with the outcome recorded in `match_analyses` for the caller to read back. The
    one exception to "never raises on an ordinary outcome" is a deployment that cannot analyse any
    recording (`DeploymentFault`, T666h): that is not an outcome for a match, so it raises, and
    only for a request that would have claimed.

    `budget_seconds` is threaded into `claim_for_analysis` as the claim's own `lease_seconds` —
    the same number `api/analyze.py`'s `maxDuration` will carry (T366), so a lease this call takes
    never outlives the invocation that could still be extending it, and an interrupted run really
    does leave the row claimable the moment its own lease — not a separately configured one —
    expires (FR-037).
    """
    now = _now()

    async with session_factory() as session:
        existing = await session.get(MatchAnalysis, game_id)
        match = await session.get(Match, game_id)

    if match is None:
        raise LookupError(f"no matches row for game_id={game_id}")

    if existing is None:
        if now - match.completed_at > timedelta(days=capture_budget_days):
            point_of_view_profile_id = await _pick_point_of_view_profile_id(
                session_factory, game_id=game_id
            )
            await _mark_unavailable(
                session_factory,
                game_id=game_id,
                point_of_view_profile_id=point_of_view_profile_id,
                requested_by_user_id=requested_by_user_id,
                now=now,
            )
            return
    elif existing.state is MatchAnalysisState.PUBLISHED:
        # SC-006: serve the stored result, fetching and parsing nothing again. That includes a row
        # whose recompute was refused recently (T666c): its retry window is part of the verdict.
        if not await _is_stale(session_factory, existing, extractor=extractor, now=now):
            return
        await _recompute(
            session_factory,
            object_store=object_store,
            extractor=extractor,
            game_id=game_id,
            profile_id=existing.point_of_view_profile_id,
            requested_by_user_id=requested_by_user_id,
            now=now,
            retry_after=recompute_retry_after,
        )
        return
    elif existing.state in _TERMINAL_STATES:
        return

    # T666h, constitution I: everything that is a fact about the deployment and not about this
    # recording is checked before the claim. A broken knowledge deploy, or an extractor reporting no
    # dependency record, would otherwise fetch the recording from the source, retain it, log the
    # read and parse it - spending the budget capture depends on - and then end the match terminally
    # `failed`, which fixing the deployment does not undo. Raised here, nothing has been written,
    # fetched or logged, so the request errors and the next one after the fix is a first analysis
    # like any other. Cost per request: see `extract.verify_deployment` (cached, no I/O).
    try:
        verify_deployment(extractor)
    except DeploymentFault as fault:
        _log_deployment_fault(game_id, fault.fault_class, fault.detail)
        raise

    # Reaches here for a brand-new, not-yet-expired match, or an existing row that is `queued` or
    # `running` under a lease that may have expired (R6) — the one path `claim_for_analysis` (T361)
    # itself knows how to resolve.
    point_of_view_profile_id = await _pick_point_of_view_profile_id(
        session_factory, game_id=game_id
    )
    outcome = await claim_for_analysis(
        session_factory,
        game_id=game_id,
        point_of_view_profile_id=point_of_view_profile_id,
        requested_by_user_id=requested_by_user_id,
        lease_seconds=int(budget_seconds),
        now=now,
    )
    if not outcome.claimed:
        return  # FR-038: someone else holds a live lease; this call joins no second parse.

    blob = await replay_provider.fetch_replay(game_id, point_of_view_profile_id)
    if isinstance(blob, NotFound):
        await _mark_unavailable(
            session_factory,
            game_id=game_id,
            point_of_view_profile_id=point_of_view_profile_id,
            requested_by_user_id=requested_by_user_id,
            now=now,
        )
        return

    async with session_factory() as session:
        retained = await retain_recording(
            session,
            object_store,
            game_id=game_id,
            profile_id=point_of_view_profile_id,
            zip_bytes=blob.content,
            requested_by_user_id=requested_by_user_id,
        )

    # FR-029: logged before `build_document` ever loads an engine (module docstring).
    await _log_access(
        session_factory,
        retained_recording_id=retained.id,
        user_id=requested_by_user_id,
        purpose=_ANALYSIS_PURPOSE,
    )

    await _extract_and_publish(
        session_factory,
        object_store=object_store,
        extractor=extractor,
        game_id=game_id,
        zip_bytes=blob.content,
        object_key=retained.object_key,
        zip_sha256=retained.zip_sha256,
        now=now,
        keep_prior=False,
        retry_after=recompute_retry_after,
    )
