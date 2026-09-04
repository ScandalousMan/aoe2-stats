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
freshly retrieved from what was already retained) and strictly before `extract.extract_timeline`
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
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aoe2stats_analyzer.claim import claim_for_analysis
from aoe2stats_analyzer.extract import extract_timeline, published_document
from aoe2stats_analyzer.retain import retain_recording, retrieve_recording
from aoe2stats_core.replay.analysis import MatchTimeline, ReplayExtractor
from aoe2stats_core.replay.validation import ReplayValidationError
from aoe2stats_providers.base import NotFound, ReplayProvider
from aoe2stats_storage.models import (
    Match,
    MatchAnalysis,
    MatchAnalysisState,
    MatchPlayer,
    ReplayAccessLog,
    RetainedRecording,
)
from aoe2stats_storage.objects import ObjectStore
from aoe2stats_storage.repositories.base import session_scope

#: `.env.example`'s own `CAPTURE_BUDGET_DAYS` — the module docstring's paragraph on `capture_
#: budget_days` explains why this exists only as a fallback for a caller (this package's own test
#: suite) that does not thread the real setting down, and why a production caller overrides it.
_DEFAULT_CAPTURE_BUDGET_DAYS = 21

#: `replay_access_log.purpose` for a read this module performs — distinct from `"download"`
#: (`apps/api/src/aoe2stats_api/routers/replays.py`), the only other writer of that column today,
#: because a system read of a third party's recording is never a download (R8, data-model.md).
_ANALYSIS_PURPOSE = "analysis"
_RECOMPUTE_PURPOSE = "recompute"

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


def _result_key(game_id: int) -> str:
    """`contracts/analysis.md`'s own key shape for the published document — stable across a
    recompute, so `match_analyses.result_key` never changes value merely because the parser did.
    """
    return f"analyses/{game_id}.json"


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
    Called before `extract_timeline` ever runs — see the module docstring's ordering paragraph.
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
    """
    async with session_scope(session_factory) as session:
        analysis = await session.get(MatchAnalysis, game_id)
        if analysis is None:
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
        else:
            analysis.state = MatchAnalysisState.UNAVAILABLE
            analysis.finished_at = now
            analysis.result_key = None


async def _mark_failed(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    game_id: int,
    error_class: str,
    error_message: str,
    now: datetime,
) -> None:
    """FR-036: `failed`, with the full error class and message recorded, on the first attempt —
    the caller (`run_once` below) never calls this a second time for the same row, because a
    `failed` row is one of `_TERMINAL_STATES` and short-circuits before any fetch or parse.
    """
    async with session_scope(session_factory) as session:
        analysis = await session.get(MatchAnalysis, game_id)
        if analysis is None:  # pragma: no cover - defensive: this row was just claimed above
            raise LookupError(f"no match_analyses row for game_id={game_id} to mark failed")
        analysis.state = MatchAnalysisState.FAILED
        analysis.finished_at = now
        analysis.error_class = error_class
        analysis.error_message = error_message
        analysis.result_key = None


async def _publish(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    game_id: int,
    timeline: MatchTimeline,
    result_key: str,
    now: datetime,
) -> None:
    """FR-031/FR-032: `published`, carrying which point of view and which parser version produced
    it. Shared by both the first-analysis and the recompute path — the one place either one ever
    writes a result, which is what keeps `result_key`'s own shape (`_result_key`) identical
    whichever path reached it.
    """
    async with session_scope(session_factory) as session:
        analysis = await session.get(MatchAnalysis, game_id)
        if analysis is None:  # pragma: no cover - defensive: this row was just claimed above
            raise LookupError(f"no match_analyses row for game_id={game_id} to publish")
        analysis.state = MatchAnalysisState.PUBLISHED
        analysis.point_of_view_profile_id = timeline.point_of_view_profile_id
        analysis.parser_name = timeline.engine_name
        analysis.parser_version = timeline.engine_version
        analysis.result_key = result_key
        analysis.finished_at = now
        analysis.error_class = None
        analysis.error_message = None


async def _extract_and_publish(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    object_store: ObjectStore,
    extractor: ReplayExtractor,
    game_id: int,
    zip_bytes: bytes,
    object_key: str,
    zip_sha256: str,
    now: datetime,
) -> None:
    """The tail shared by both paths, from "bytes in hand" onward: parse, and either publish or
    record why it failed. Never retried by this function's own caller — see `_TERMINAL_STATES`.
    """
    try:
        timeline = extract_timeline(extractor, zip_bytes)
    except ReplayValidationError as exc:
        await _mark_failed(
            session_factory,
            game_id=game_id,
            error_class=type(exc).__name__,
            error_message=str(exc),
            now=now,
        )
        return

    document = published_document(
        timeline,
        game_id=game_id,
        object_key=object_key,
        zip_sha256=zip_sha256,
        extracted_at=now,
    )
    result_key = _result_key(game_id)
    await object_store.put(
        result_key, json.dumps(document).encode("utf-8"), content_type="application/json"
    )
    await _publish(
        session_factory, game_id=game_id, timeline=timeline, result_key=result_key, now=now
    )


async def _recompute(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    object_store: ObjectStore,
    extractor: ReplayExtractor,
    game_id: int,
    profile_id: int,
    requested_by_user_id: UUID,
    now: datetime,
) -> None:
    """FR-041/SC-009a: recompute a `published`-but-stale analysis from the recording this service
    already retained, reaching the source zero times. Reads `retained_recordings` and the object
    store only — `replay_provider` never appears in this function's own signature, which is what
    makes "zero calls to the source" true by construction rather than by discipline.
    """
    async with session_factory() as session:
        retained = await _retained_recording_row(session, game_id=game_id, profile_id=profile_id)
        if retained is None:
            # FR-033 retains for every publish, so a published row with nothing retained should
            # never happen. Nothing in this codebase reaches this branch; treat it the same as a
            # source that no longer serves this match, rather than raise into a caller that
            # promised never to see this function fail.
            await _mark_unavailable(
                session_factory,
                game_id=game_id,
                point_of_view_profile_id=profile_id,
                requested_by_user_id=requested_by_user_id,
                now=now,
            )
            return
        zip_bytes = await retrieve_recording(
            session, object_store, game_id=game_id, profile_id=profile_id
        )

    # FR-029: logged before `extract_timeline` ever loads an engine (module docstring).
    await _log_access(
        session_factory,
        retained_recording_id=retained.id,
        user_id=requested_by_user_id,
        purpose=_RECOMPUTE_PURPOSE,
    )

    await _extract_and_publish(
        session_factory,
        object_store=object_store,
        extractor=extractor,
        game_id=game_id,
        zip_bytes=zip_bytes,
        object_key=retained.object_key,
        zip_sha256=retained.zip_sha256,
        now=now,
    )


async def run_once(
    game_id: int,
    budget_seconds: float,
    requested_by_user_id: UUID,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    replay_provider: ReplayProvider,
    extractor: ReplayExtractor,
    object_store: ObjectStore,
    capture_budget_days: int = _DEFAULT_CAPTURE_BUDGET_DAYS,
) -> None:
    """Analyse `game_id` once, on this one request — see the module docstring for the two paths
    this dispatches between and the ordering FR-029 requires. Never raises on an ordinary outcome
    (a parse failure, an expired match, a lease held by someone else): every one of those is a
    normal return, with the outcome recorded in `match_analyses` for the caller to read back.

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
        stale = (
            existing.parser_name != extractor.engine_name
            or existing.parser_version != extractor.engine_version
        )
        if not stale:
            return  # SC-006: serve the stored result, fetching and parsing nothing again.
        await _recompute(
            session_factory,
            object_store=object_store,
            extractor=extractor,
            game_id=game_id,
            profile_id=existing.point_of_view_profile_id,
            requested_by_user_id=requested_by_user_id,
            now=now,
        )
        return
    elif existing.state in _TERMINAL_STATES:
        return

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

    # FR-029: logged before `extract_timeline` ever loads an engine (module docstring).
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
    )
