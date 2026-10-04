"""Tests for `aoe2stats_analyzer.run.run_once` — quickstart scenarios 7, 8 and 10.

**T365 (`apps/analyzer/src/aoe2stats_analyzer/run.py`) does not exist yet.** Per this project's
test-first discipline (`CLAUDE.md` "Test-first tasks and the green-tree gate"), every test below is
marked `@pytest.mark.xfail(strict=True, reason="T365 not implemented yet")` and imports
`aoe2stats_analyzer.run` inside its own body, never at module scope — a module-scope import of a
module that does not exist yet is a collection error that fails the whole file, not one test.
`strict=True` is what forces T365 to remove each marker rather than leaving a stale one that would
hide a regression the moment the module lands wrong.

**Assumed interface**, reconstructed from `plan.md`'s Source Code tree, `research.md` R6/R7/R12,
`contracts/analysis.md` and `contracts/http-api.md`'s `POST /api/analyze` section, and
`data-model.md`'s `match_analyses`/`retained_recordings`/`replay_access_log` sections — in the same
spirit `apps/ingester/tests/test_idempotency.py` already committed to for a sibling not-yet-built
module, and for the same reason: a test-first task has to commit to *something* to be a real test at
all, and only the properties named in T364's own task text (SC-006, FR-032, SC-013, FR-037, FR-036,
FR-034, FR-041, SC-009a, FR-044, FR-029) are load-bearing, not this file's specific keyword names.

- `run_once(game_id, budget_seconds, requested_by_user_id, *, session_factory, replay_provider,
  extractor, object_store)` is one match, on one request — `contracts/http-api.md`: "Body
  `{"game_id": ...}`. Claims and runs." `requested_by_user_id` is required at call time even though
  `match_analyses.requested_by_user_id` is nullable (erasure clears it later): `replay_access_log.
  user_id` is `NOT NULL` (`data-model.md`, "the read is user-triggered"), so every call that reads a
  retained recording needs a real user to attribute that read to.
- `replay_provider` satisfies `aoe2stats_providers.base.ReplayProvider`
  (`fetch_replay(game_id, profile_id) -> ReplayBlob | NotFound`), the same Protocol 001 already uses
  for a download (`contracts/providers.md`). The fakes below are bare test doubles, not
  `AoemsReplayProvider` — a `provider_calls` row per fetch is that concrete adapter's own job
  (`AsyncBaseProvider._request`'s `call_sink`, already wired for every other provider in this
  codebase), so "fetched at most once" is asserted on the fake's own call log here, exactly the
  substitution `test_idempotency.py` already made for the identical property in the ingester's
  suite.
- `extractor` satisfies the not-yet-defined `ReplayExtractor` Protocol (T352,
  `packages/core/tests/test_replay_analysis.py` already pins `MatchTimeline`'s and
  `ParticipantTimeline`'s exact field sets): `extract(zip_bytes) -> MatchTimeline`, raising
  `EngineParseError` (already implemented, `aoe2stats_core.replay.validation`) on a recording it
  cannot parse. It also exposes `engine_name`/`engine_version` so `run_once` can compare a stored
  `parser_version` against "the engine currently running" — `contracts/http-api.md`'s definition of
  `stale` — without a second constructor argument for it.
- `object_store` satisfies the async subset of `aoe2stats_storage.objects.ObjectStore` used
  elsewhere in this codebase's tests (`put`, `get`).
- `run_once` never raises on an ordinary outcome — a parse failure, an expired match, a cap refusal
  — because `api/analyze.py` is meant to build the same `analysis` response object whichever state
  results (`contracts/http-api.md`). Every assertion below therefore reads the row back from
  `match_analyses` / `retained_recordings` / `replay_access_log` directly rather than trusting a
  return value, the same way `test_idempotency.py` reads `replay_captures` back.

If T365 lands with a different shape, this file is what gets updated — not evidence that the
assumption above was wrong to make.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import uuid
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.snapshot_refresh import (
    REAL_SNAPSHOT_DIRECTORY,
    clear_snapshot_resolution_caches,
    isolate_snapshot_root,
    promote_a_refreshed_snapshot,
)

from aoe2stats_analyzer import extract
from aoe2stats_analyzer import run as run_module
from aoe2stats_analyzer.retain import retain_recording
from aoe2stats_core.replay.events import (
    CanonicalEvent,
    EventKind,
    MatchStartedPayload,
    ParticipantEntry,
    UnitQueuedPayload,
)
from aoe2stats_core.replay.validation import EngineParseError
from aoe2stats_core.truth.placement import TierPlacementError
from aoe2stats_knowledge import snapshot
from aoe2stats_providers.base import NotFound, ReplayBlob
from aoe2stats_storage.models import (
    AnalysisKnowledgeGap,
    AoeProfile,
    Match,
    MatchAnalysis,
    MatchAnalysisState,
    MatchPlayer,
    ReplayAccessLog,
    RetainedRecording,
    User,
)
from aoe2stats_storage.objects import ObjectNotFound
from aoe2stats_storage.repositories.base import session_scope
from aoe2stats_storage.repositories.knowledge_gaps import GapToRecord

# `session_factory` and `clean_database` below come from `apps/analyzer/tests/conftest.py`
# (T362's own addition, re-exporting `tests/db.py`'s harness exactly as `apps/api/tests/conftest.py`
# and `apps/ingester/tests/conftest.py` already do) — not imported directly here, which would
# collide with this file's own `session_factory`/`clean_database` parameter names under ruff's
# F811, per that conftest's own docstring.

_BUDGET_SECONDS = 300  # api/analyze.py's own maxDuration (contracts/http-api.md)

# Comfortably beyond any measured retention window (`docs/data-sources.md` §2) without restating
# the figure itself — the point of this constant is "unambiguously expired", not a governed budget.
_FAR_PAST_DAYS = 120

_ENGINE_NAME = "aoe2rec-py"
_ENGINE_VERSION_1 = "0.1.21"  # contracts/analysis.md's pinned wheel
_ENGINE_VERSION_2 = "0.1.22"  # a later parser version, for the recompute tests


# --- Value objects matching contracts/analysis.md's `MatchTimeline` -------------------------------
# `packages/core/src/aoe2stats_core/replay/analysis.py` does not exist yet either (T352), so these
# are local stand-ins carrying the exact field set `packages/core/tests/test_replay_analysis.py`
# already pins — not an import of the real thing, which would make this file fail to collect for a
# second, unrelated reason.


@dataclass(frozen=True, slots=True)
class _FakeParticipantTimeline:
    profile_id: int
    player_number: int
    civ_id: int
    resolved_team_id: int
    builds: tuple = ()
    trainings: tuple = ()
    researches: tuple = ()
    age_up_commands: dict = field(default_factory=dict)
    villagers_ordered: int = 0
    actions: int = 0
    actions_per_minute: float = 0.0
    resigned_at_ms: int | None = None


@dataclass(frozen=True, slots=True)
class _FakeMatchTimeline:
    engine_name: str
    engine_version: str
    point_of_view_profile_id: int
    world_time_ms: int
    participants: tuple = ()


@dataclass(frozen=True, slots=True)
class _FetchCall:
    game_id: int
    profile_id: int


class _FakeReplayProvider:
    """Answers any participant of the seeded match with the same blob — this file does not assume
    which participant `run_once` tries first, only that it tries at most one (SC-006). Raises
    `AssertionError` past `max_calls`, a canary rather than a passive counter, the same technique
    `test_idempotency.py`'s `_FakeReplayEngine` uses for "this must never run again"."""

    def __init__(self, blob: ReplayBlob, *, max_calls: int | None = None) -> None:
        self._blob = blob
        self._max_calls = max_calls
        self.calls: list[_FetchCall] = []

    async def fetch_replay(self, game_id: int, profile_id: int) -> ReplayBlob | NotFound:
        if self._max_calls is not None and len(self.calls) >= self._max_calls:
            raise AssertionError(
                f"fetch_replay called a {len(self.calls) + 1}th time; SC-006 bounds it to "
                f"{self._max_calls} for this scenario"
            )
        self.calls.append(_FetchCall(game_id=game_id, profile_id=profile_id))
        return self._blob


class _RefusingReplayProvider:
    """Used wherever the source must never be called at all: an expired-and-never-analysed match
    (FR-034, "never as an action that fails") and a recompute from retained bytes (FR-041, SC-009a).
    """

    async def fetch_replay(self, game_id: int, profile_id: int) -> ReplayBlob | NotFound:
        raise AssertionError(
            f"fetch_replay({game_id}, {profile_id}) called when no fetch should ever be attempted"
        )


class _FakeObjectStore:
    """`put` overwrites, `put_if_absent` creates only a missing key; `put_calls` records every
    write that actually changed the store, so "written once" is `put_calls.count(key) == 1`.

    `competing_write` is the race: bytes another writer lands on the first `analyses/` key this
    store is asked to write, *after* the caller decided to write and *before* its write reaches the
    store - recorded like any other write, so a test can tell who wrote the surviving bytes."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.put_calls: list[str] = []
        self.get_calls: list[str] = []
        self.competing_write: bytes | None = None

    def _competitor_lands(self, key: str) -> None:
        if self.competing_write is not None and key.startswith("analyses/"):
            self.objects[key] = self.competing_write
            self.put_calls.append(key)
            self.competing_write = None

    async def put(self, key: str, body: bytes, *, content_type: str = "application/zip") -> None:
        self._competitor_lands(key)
        self.objects[key] = body
        self.put_calls.append(key)

    async def put_if_absent(
        self, key: str, body: bytes, *, content_type: str = "application/zip"
    ) -> bool:
        self._competitor_lands(key)
        if key in self.objects:
            return False
        self.objects[key] = body
        self.put_calls.append(key)
        return True

    async def get(self, key: str) -> bytes:
        self.get_calls.append(key)
        if key not in self.objects:
            raise ObjectNotFound(key)
        return self.objects[key]


class _FakeExtractor:
    """`extract()` raises past `max_calls`, the same canary shape as `_FakeReplayProvider` — FR-036
    and FR-041/SC-006 both depend on `run_once` never calling this a second time when it must not.
    """

    def __init__(
        self,
        *,
        engine_name: str = _ENGINE_NAME,
        engine_version: str = _ENGINE_VERSION_1,
        point_of_view_profile_id: int,
        raises: Exception | None = None,
        max_calls: int | None = None,
    ) -> None:
        self.engine_name = engine_name
        self.engine_version = engine_version
        # T655: the document carries the dependency record and refuses an empty one (FR-044).
        self.engine_dependencies = {engine_name: engine_version}
        self._point_of_view_profile_id = point_of_view_profile_id
        self._raises = raises
        self._max_calls = max_calls
        self.calls: list[bytes] = []

    def events(self, zip_bytes: bytes) -> Iterator[CanonicalEvent]:
        """An empty stream: this file asserts what `run_once` does with a row, not what the
        document says, so the coverage pass finds no build and reports its one whole-build gap."""
        return iter(())

    def extract(self, zip_bytes: bytes) -> _FakeMatchTimeline:
        if self._max_calls is not None and len(self.calls) >= self._max_calls:
            raise AssertionError(
                f"extract() called a {len(self.calls) + 1}th time; this scenario bounds it to "
                f"{self._max_calls}"
            )
        self.calls.append(zip_bytes)
        if self._raises is not None:
            raise self._raises
        return _FakeMatchTimeline(
            engine_name=self.engine_name,
            engine_version=self.engine_version,
            point_of_view_profile_id=self._point_of_view_profile_id,
            world_time_ms=1_200_000,
        )


async def _seed_user(session_factory: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    user_id = uuid.uuid4()
    async with session_scope(session_factory) as session:
        session.add(User(id=user_id))
    return user_id


async def _seed_match(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    game_id: int,
    completed_at: datetime,
    profile_ids: Sequence[int],
) -> None:
    async with session_scope(session_factory) as session:
        for profile_id in profile_ids:
            session.add(AoeProfile(profile_id=profile_id, alias=f"Player {profile_id}"))
        session.add(
            Match(
                game_id=game_id,
                leaderboard_id=3,
                completed_at=completed_at,
                duration_seconds=1800,
                source="relic",
                raw_payload={},
            )
        )
        for index, profile_id in enumerate(profile_ids):
            session.add(
                MatchPlayer(
                    game_id=game_id,
                    profile_id=profile_id,
                    team_id=index,
                    civ_id=1,
                    color_id=index,
                    result="win" if index == 0 else "loss",
                )
            )


async def _get_analysis(
    session_factory: async_sessionmaker[AsyncSession], game_id: int
) -> MatchAnalysis | None:
    async with session_scope(session_factory) as session:
        return await session.get(MatchAnalysis, game_id)


async def _get_retained_recording(
    session_factory: async_sessionmaker[AsyncSession], game_id: int, profile_id: int
) -> RetainedRecording | None:
    async with session_scope(session_factory) as session:
        result = await session.execute(
            select(RetainedRecording).where(
                RetainedRecording.game_id == game_id, RetainedRecording.profile_id == profile_id
            )
        )
        return result.scalar_one_or_none()


async def _access_log_rows(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[ReplayAccessLog]:
    async with session_scope(session_factory) as session:
        result = await session.execute(select(ReplayAccessLog))
        return list(result.scalars().all())


async def _run_ingester_once(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """The isolation probe `test_claim.py` (T360) is already documented to use for FR-044: running
    001's real, already-implemented `run_once` over the same database and confirming it neither
    raises nor touches anything `apps/analyzer` owns. Imported at module scope, unlike
    `aoe2stats_analyzer.run` — `aoe2stats_ingester.run` already exists and is fully green."""
    from aoe2stats_ingester.run import run_once as ingester_run_once

    await ingester_run_once(60, trigger="test", stages=[], session_factory=session_factory)


# --- Scenario 7.5 / SC-006 --------------------------------------------------------------------


async def test_a_match_is_fetched_and_parsed_at_most_once_however_many_users_ask(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Quickstart 7.5: "Open the same match as a different user. Expect the analysis immediately,
    and **one** row [fetch/parse] for that recording across both requests" (FR-031, SC-006)."""
    from aoe2stats_analyzer.run import run_once

    game_id = 500_546_441
    profile_a, profile_b = 196_240, 196_241
    await _seed_match(
        session_factory,
        game_id=game_id,
        completed_at=datetime.now(UTC) - timedelta(days=1),
        profile_ids=[profile_a, profile_b],
    )
    requester = await _seed_user(session_factory)
    second_viewer = await _seed_user(session_factory)
    provider = _FakeReplayProvider(
        ReplayBlob(content=b"replay bytes", filename="r.zip", content_type="application/zip"),
        max_calls=1,
    )
    extractor = _FakeExtractor(point_of_view_profile_id=profile_a, max_calls=1)
    store = _FakeObjectStore()

    await run_once(
        game_id,
        _BUDGET_SECONDS,
        requester,
        session_factory=session_factory,
        replay_provider=provider,
        extractor=extractor,
        object_store=store,
    )
    # A second, different user opens the same match — this must not fetch or parse again.
    await run_once(
        game_id,
        _BUDGET_SECONDS,
        second_viewer,
        session_factory=session_factory,
        replay_provider=provider,
        extractor=extractor,
        object_store=store,
    )

    assert len(provider.calls) == 1
    assert len(extractor.calls) == 1
    analysis = await _get_analysis(session_factory, game_id)
    assert analysis is not None
    assert analysis.state == MatchAnalysisState.PUBLISHED
    assert analysis.result_key is not None


# --- Scenario 7.6 / FR-032 ----------------------------------------------------------------------


async def test_the_stored_row_records_the_point_of_view_and_the_parser_version(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Quickstart 7.6: "Confirm `match_analyses` records the point of view and the parser version
    (FR-032), and that `retained_recordings` holds exactly one row with a checksum (FR-033)."""
    from aoe2stats_analyzer.run import run_once

    game_id = 500_546_442
    profile_a, profile_b = 300_001, 300_002
    await _seed_match(
        session_factory,
        game_id=game_id,
        completed_at=datetime.now(UTC) - timedelta(days=1),
        profile_ids=[profile_a, profile_b],
    )
    requester = await _seed_user(session_factory)
    raw_bytes = b"raw replay bytes for FR-032"
    provider = _FakeReplayProvider(
        ReplayBlob(content=raw_bytes, filename="r.zip", content_type="application/zip")
    )
    extractor = _FakeExtractor(point_of_view_profile_id=profile_a, engine_version=_ENGINE_VERSION_1)
    store = _FakeObjectStore()

    await run_once(
        game_id,
        _BUDGET_SECONDS,
        requester,
        session_factory=session_factory,
        replay_provider=provider,
        extractor=extractor,
        object_store=store,
    )

    analysis = await _get_analysis(session_factory, game_id)
    assert analysis is not None
    assert analysis.state == MatchAnalysisState.PUBLISHED
    assert analysis.point_of_view_profile_id == profile_a
    assert analysis.parser_name == _ENGINE_NAME
    assert analysis.parser_version == _ENGINE_VERSION_1

    retained = await _get_retained_recording(session_factory, game_id, profile_a)
    assert retained is not None
    assert retained.zip_sha256 == hashlib.sha256(raw_bytes).hexdigest()
    assert retained.zip_bytes == len(raw_bytes)


async def test_the_engine_deps_column_holds_the_record_the_document_carries(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """T655 / FR-044: `match_analyses.engine_deps` existed through two migrations and nothing wrote
    it. It is now the same record the published document carries under `engine.deps` and
    `identity.parser_dependencies`, and none of the three is empty."""
    import json

    from aoe2stats_analyzer.run import run_once

    game_id = 500_546_444
    profile_a, profile_b = 300_011, 300_012
    await _seed_match(
        session_factory,
        game_id=game_id,
        completed_at=datetime.now(UTC) - timedelta(days=1),
        profile_ids=[profile_a, profile_b],
    )
    requester = await _seed_user(session_factory)
    provider = _FakeReplayProvider(
        ReplayBlob(content=b"raw bytes", filename="r.zip", content_type="application/zip")
    )
    extractor = _FakeExtractor(point_of_view_profile_id=profile_a)
    store = _FakeObjectStore()

    await run_once(
        game_id,
        _BUDGET_SECONDS,
        requester,
        session_factory=session_factory,
        replay_provider=provider,
        extractor=extractor,
        object_store=store,
    )

    analysis = await _get_analysis(session_factory, game_id)
    assert analysis is not None
    assert analysis.result_key is not None
    document = json.loads(store.objects[analysis.result_key])
    assert analysis.engine_deps
    assert analysis.engine_deps == extractor.engine_dependencies
    assert document["engine"]["deps"] == analysis.engine_deps
    assert document["identity"]["parser_dependencies"] == analysis.engine_deps


# --- Scenario 8.6 / SC-013 -----------------------------------------------------------------------


async def test_a_parse_failure_leaves_the_api_and_the_ingester_untouched(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Quickstart 8.6: "While a parse is failing, confirm the API answers normally and the
    ingester's next run is unaffected" (FR-042, SC-013). `run_once` itself must not raise — a
    parser crash is contained and recorded as `failed`, never propagated to whatever process called
    it — and the ingester's own, already-implemented `run_once` must be able to run immediately
    afterward without seeing anything wrong."""
    from aoe2stats_analyzer.run import run_once

    game_id = 500_546_443
    profile_a, profile_b = 300_003, 300_004
    await _seed_match(
        session_factory,
        game_id=game_id,
        completed_at=datetime.now(UTC) - timedelta(days=1),
        profile_ids=[profile_a, profile_b],
    )
    requester = await _seed_user(session_factory)
    provider = _FakeReplayProvider(
        ReplayBlob(content=b"corrupted", filename="r.zip", content_type="application/zip")
    )
    extractor = _FakeExtractor(
        point_of_view_profile_id=profile_a,
        raises=EngineParseError("aoe2rec-py could not parse this recording"),
    )
    store = _FakeObjectStore()

    # Must not raise: the caller (api/analyze.py, in its own process) still gets a normal response.
    await run_once(
        game_id,
        _BUDGET_SECONDS,
        requester,
        session_factory=session_factory,
        replay_provider=provider,
        extractor=extractor,
        object_store=store,
    )

    analysis = await _get_analysis(session_factory, game_id)
    assert analysis is not None
    assert analysis.state == MatchAnalysisState.FAILED
    assert analysis.result_key is None

    # The ingester's own run, on the same database, is unaffected — the isolation FR-042 requires.
    await _run_ingester_once(session_factory)


# --- Scenario 8.2 / FR-037 -----------------------------------------------------------------------


async def test_an_interrupted_run_leaves_no_unclaimable_row_and_the_next_request_resumes_it(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Quickstart 8.2: "Kill the function mid-parse. Expect no row stuck in an unclaimable state;
    expect the *next person to open that match* to resume it" (FR-037, FR-044). Simulated by seeding
    a `running` row whose lease already expired — the shape a crashed invocation leaves behind
    (`data-model.md`'s `running` state, R6) — and confirming the very next call finishes the job
    rather than reporting it stuck."""
    from aoe2stats_analyzer.run import run_once

    game_id = 500_546_444
    profile_a, profile_b = 300_005, 300_006
    await _seed_match(
        session_factory,
        game_id=game_id,
        completed_at=datetime.now(UTC) - timedelta(days=1),
        profile_ids=[profile_a, profile_b],
    )
    abandoned_by = await _seed_user(session_factory)
    resumer = await _seed_user(session_factory)
    now = datetime.now(UTC)
    async with session_scope(session_factory) as session:
        session.add(
            MatchAnalysis(
                game_id=game_id,
                state=MatchAnalysisState.RUNNING,
                point_of_view_profile_id=profile_a,
                requested_by_user_id=abandoned_by,
                requested_at=now - timedelta(minutes=10),
                claimed_at=now - timedelta(minutes=10),
                lease_expires_at=now - timedelta(minutes=5),  # already expired: a dead invocation
                attempts=1,
            )
        )

    provider = _FakeReplayProvider(
        ReplayBlob(content=b"resumed bytes", filename="r.zip", content_type="application/zip")
    )
    extractor = _FakeExtractor(point_of_view_profile_id=profile_a)
    store = _FakeObjectStore()

    await run_once(
        game_id,
        _BUDGET_SECONDS,
        resumer,
        session_factory=session_factory,
        replay_provider=provider,
        extractor=extractor,
        object_store=store,
    )

    analysis = await _get_analysis(session_factory, game_id)
    assert analysis is not None
    # Resumed to completion, not left stuck at `running` with a dead lease.
    assert analysis.state == MatchAnalysisState.PUBLISHED
    assert analysis.result_key is not None


# --- Scenario 8.3 / FR-036 -----------------------------------------------------------------------


async def test_an_unparsable_recording_fails_on_the_first_attempt_and_is_never_retried(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """FR-036: "record[s] a failed analysis with its reason... never a silent failure", and the
    `match_analyses` docstring's own rule: "A recording that fails to parse does not retry at all:
    it goes to `failed` on the first attempt with its full error... because a parse is deterministic
    and a second attempt is a second identical failure that costs a fetch." Asked for twice, this
    must fetch and parse **once**, not twice — `_FakeReplayProvider`/`_FakeExtractor`'s
    `max_calls=1` turn a retry into a hard failure rather than a silently-passing assertion."""
    from aoe2stats_analyzer.run import run_once

    game_id = 500_546_445
    profile_a, profile_b = 300_007, 300_008
    await _seed_match(
        session_factory,
        game_id=game_id,
        completed_at=datetime.now(UTC) - timedelta(days=1),
        profile_ids=[profile_a, profile_b],
    )
    requester = await _seed_user(session_factory)
    second_asker = await _seed_user(session_factory)
    provider = _FakeReplayProvider(
        ReplayBlob(content=b"corrupted", filename="r.zip", content_type="application/zip"),
        max_calls=1,
    )
    extractor = _FakeExtractor(
        point_of_view_profile_id=profile_a,
        raises=EngineParseError("the archive is well-formed but the engine rejected it"),
        max_calls=1,
    )
    store = _FakeObjectStore()

    await run_once(
        game_id,
        _BUDGET_SECONDS,
        requester,
        session_factory=session_factory,
        replay_provider=provider,
        extractor=extractor,
        object_store=store,
    )
    first = await _get_analysis(session_factory, game_id)
    assert first is not None
    assert first.state == MatchAnalysisState.FAILED
    assert first.error_class == "EngineParseError"
    assert first.error_message
    first_error_message = first.error_message

    # A second person opens the same match. The `max_calls=1` fakes above raise `AssertionError`
    # if `run_once` fetches or parses again — this call must be a no-op against the failed row.
    await run_once(
        game_id,
        _BUDGET_SECONDS,
        second_asker,
        session_factory=session_factory,
        replay_provider=provider,
        extractor=extractor,
        object_store=store,
    )

    second = await _get_analysis(session_factory, game_id)
    assert second is not None
    assert second.state == MatchAnalysisState.FAILED
    assert second.error_message == first_error_message
    assert len(provider.calls) == 1
    assert len(extractor.calls) == 1


# --- T656 / FR-011: a document that breaks the contract is not published -----------------------


@dataclass(frozen=True, slots=True)
class _ParticipantWithAStrayField(_FakeParticipantTimeline):
    """A participant carrying a field the register does not publish — the shape of a conclusion
    smuggled into the document. `dataclasses.asdict` carries it through by name, so the validator,
    not the builder, is what has to refuse it (rule 1)."""

    coaching_note: str = "player 1 should have walled earlier"


class _ExtractorWritingAStrayField(_FakeExtractor):
    def extract(self, zip_bytes: bytes) -> _FakeMatchTimeline:
        timeline = super().extract(zip_bytes)
        stray = _ParticipantWithAStrayField(
            profile_id=1, player_number=1, civ_id=1, resolved_team_id=1
        )
        return _FakeMatchTimeline(
            engine_name=timeline.engine_name,
            engine_version=timeline.engine_version,
            point_of_view_profile_id=timeline.point_of_view_profile_id,
            world_time_ms=timeline.world_time_ms,
            participants=(stray,),
        )


async def test_a_document_that_fails_validation_writes_no_object_and_the_row_fails(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """The failing document is not published: no analysis object is written, no row points at one,
    and the analysis ends in 003's own `failed` state with the validator's message — which names the
    rule — through the failure path a parse failure already uses (FR-036), never retried."""
    from aoe2stats_analyzer.run import run_once

    game_id = 500_546_461
    profile_a, profile_b = 300_031, 300_032
    await _seed_match(
        session_factory,
        game_id=game_id,
        completed_at=datetime.now(UTC) - timedelta(days=1),
        profile_ids=[profile_a, profile_b],
    )
    requester = await _seed_user(session_factory)
    provider = _FakeReplayProvider(
        ReplayBlob(content=b"raw bytes", filename="r.zip", content_type="application/zip"),
        max_calls=1,
    )
    extractor = _ExtractorWritingAStrayField(point_of_view_profile_id=profile_a, max_calls=1)
    store = _FakeObjectStore()

    for _ in range(2):  # the second request meets a terminal row and does nothing
        await run_once(
            game_id,
            _BUDGET_SECONDS,
            requester,
            session_factory=session_factory,
            replay_provider=provider,
            extractor=extractor,
            object_store=store,
        )

    analysis = await _get_analysis(session_factory, game_id)
    assert analysis is not None
    assert analysis.state == MatchAnalysisState.FAILED
    assert analysis.result_key is None
    assert analysis.error_class == "DocumentInvalid"
    assert analysis.error_message is not None
    assert "rule 1" in analysis.error_message
    assert "participants[].coaching_note" in analysis.error_message
    assert not [key for key in store.objects if key.startswith("analyses/")]
    assert len(extractor.calls) == 1


async def test_a_document_that_passes_validation_is_written_and_the_row_points_at_it(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """The contrast: the same flow, with nothing stray in the document."""
    import json

    from aoe2stats_analyzer.extract import validate_document
    from aoe2stats_analyzer.run import run_once

    game_id = 500_546_462
    profile_a, profile_b = 300_033, 300_034
    await _seed_match(
        session_factory,
        game_id=game_id,
        completed_at=datetime.now(UTC) - timedelta(days=1),
        profile_ids=[profile_a, profile_b],
    )
    requester = await _seed_user(session_factory)
    provider = _FakeReplayProvider(
        ReplayBlob(content=b"raw bytes", filename="r.zip", content_type="application/zip")
    )
    extractor = _FakeExtractor(point_of_view_profile_id=profile_a)
    store = _FakeObjectStore()

    await run_once(
        game_id,
        _BUDGET_SECONDS,
        requester,
        session_factory=session_factory,
        replay_provider=provider,
        extractor=extractor,
        object_store=store,
    )

    analysis = await _get_analysis(session_factory, game_id)
    assert analysis is not None
    assert analysis.state == MatchAnalysisState.PUBLISHED
    assert analysis.error_class is None
    assert analysis.result_key is not None
    validate_document(json.loads(store.objects[analysis.result_key]))


async def test_the_stored_object_is_exactly_the_canonical_serialisation_of_its_document(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """T659, FR-041: `run_once` stores `canonical_bytes(document)` and nothing else, so what a
    reproduction compares against is what was written. Canonical bytes are a fixed point: reading
    the stored object and serialising it again changes nothing."""
    import json

    from aoe2stats_analyzer.extract import canonical_bytes
    from aoe2stats_analyzer.run import run_once

    game_id = 500_546_463
    profile_a, profile_b = 300_035, 300_036
    await _seed_match(
        session_factory,
        game_id=game_id,
        completed_at=datetime.now(UTC) - timedelta(days=1),
        profile_ids=[profile_a, profile_b],
    )
    requester = await _seed_user(session_factory)
    provider = _FakeReplayProvider(
        ReplayBlob(content=b"raw bytes", filename="r.zip", content_type="application/zip")
    )

    await run_once(
        game_id,
        _BUDGET_SECONDS,
        requester,
        session_factory=session_factory,
        replay_provider=provider,
        extractor=_FakeExtractor(point_of_view_profile_id=profile_a),
        object_store=(store := _FakeObjectStore()),
    )

    analysis = await _get_analysis(session_factory, game_id)
    assert analysis is not None
    assert analysis.result_key is not None
    stored = store.objects[analysis.result_key]
    assert stored == canonical_bytes(json.loads(stored))
    assert b"\n" not in stored
    assert not stored.endswith(b" ")


# --- Scenario 8.5 / FR-034 -----------------------------------------------------------------------


async def test_a_never_analysed_match_past_the_window_is_unavailable_not_an_action(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Quickstart 8.5: "Request an analysis of the >31-day-old match. Expect permanent
    unavailability with a reason, and no button" (FR-034). R8: availability is *derived*, never
    probed — the source must not be asked at all for a match this old that was never analysed, so
    `_RefusingReplayProvider` and an extractor bounded to zero calls turn a stray fetch or parse
    into a hard failure rather than a silently-passing assertion."""
    from aoe2stats_analyzer.run import run_once

    game_id = 474_746_656  # quickstart.md's own fixture for this exact scenario
    profile_a, profile_b = 300_009, 300_010
    await _seed_match(
        session_factory,
        game_id=game_id,
        completed_at=datetime.now(UTC) - timedelta(days=_FAR_PAST_DAYS),
        profile_ids=[profile_a, profile_b],
    )
    requester = await _seed_user(session_factory)
    provider = _RefusingReplayProvider()
    extractor = _FakeExtractor(point_of_view_profile_id=profile_a, max_calls=0)
    store = _FakeObjectStore()

    await run_once(
        game_id,
        _BUDGET_SECONDS,
        requester,
        session_factory=session_factory,
        replay_provider=provider,
        extractor=extractor,
        object_store=store,
    )

    analysis = await _get_analysis(session_factory, game_id)
    assert analysis is not None
    assert analysis.state == MatchAnalysisState.UNAVAILABLE
    assert analysis.result_key is None
    assert not store.put_calls


# --- Scenario 10 / FR-041, SC-009a, FR-044, SC-006 -----------------------------------------------


async def test_recompute_after_an_engine_change_reaches_the_source_zero_times_and_only_on_request(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Scenario 10: "Change the parser version... recompute by asking for it the same way a first
    analysis is asked for — `POST /api/analyze`. Confirm nothing on a timer did it first (FR-044)...
    Expect it to succeed from this service's own retained bytes... with **zero** calls to the
    source" (FR-041, SC-009a). Also SC-006's own "1 again after a parser version change, and 1
    only": a third call against the now-current, non-stale row must re-parse nothing either.

    The match predates any retention window (the seeded `completed_at` mirrors quickstart's own
    >31-day fixture) — recomputing from retained bytes is the only way this can ever succeed, so a
    stray call to the source here is exactly the failure FR-041 exists to make impossible.
    """
    from aoe2stats_analyzer.run import run_once

    game_id = 474_746_656
    profile_a, profile_b = 300_011, 300_012
    completed_at = datetime.now(UTC) - timedelta(days=_FAR_PAST_DAYS)
    await _seed_match(
        session_factory,
        game_id=game_id,
        completed_at=completed_at,
        profile_ids=[profile_a, profile_b],
    )
    original_requester = await _seed_user(session_factory)
    recomputer = await _seed_user(session_factory)

    retained_bytes = b"already-retained recording bytes, the source no longer serves this match"
    object_key = f"retained-recordings/{game_id}/{profile_a}.zip"
    store = _FakeObjectStore()
    store.objects[object_key] = retained_bytes
    now = datetime.now(UTC)
    async with session_scope(session_factory) as session:
        session.add(
            RetainedRecording(
                id=uuid.uuid4(),
                game_id=game_id,
                profile_id=profile_a,
                object_key=object_key,
                zip_bytes=len(retained_bytes),
                zip_sha256=hashlib.sha256(retained_bytes).hexdigest(),
                retained_at=now - timedelta(days=1),
                requested_by_user_id=original_requester,
            )
        )
        session.add(
            MatchAnalysis(
                game_id=game_id,
                state=MatchAnalysisState.PUBLISHED,
                point_of_view_profile_id=profile_a,
                parser_name=_ENGINE_NAME,
                parser_version=_ENGINE_VERSION_1,
                requested_by_user_id=original_requester,
                requested_at=now - timedelta(days=1),
                claimed_at=now - timedelta(days=1),
                finished_at=now - timedelta(days=1),
                attempts=1,
                result_key=f"analyses/{game_id}.json",
            )
        )

    # The engine has moved on: this is "the engine currently running" for the recompute call.
    refusing_provider = _RefusingReplayProvider()
    upgraded_extractor = _FakeExtractor(
        point_of_view_profile_id=profile_a, engine_version=_ENGINE_VERSION_2, max_calls=1
    )

    await run_once(
        game_id,
        _BUDGET_SECONDS,
        recomputer,
        session_factory=session_factory,
        replay_provider=refusing_provider,
        extractor=upgraded_extractor,
        object_store=store,
    )

    recomputed = await _get_analysis(session_factory, game_id)
    assert recomputed is not None
    assert recomputed.state == MatchAnalysisState.PUBLISHED
    assert recomputed.parser_version == _ENGINE_VERSION_2
    assert object_key in store.get_calls
    # No new retention: the recompute reads what is already there, it does not fetch a second copy.
    still_one_retained_row = await _get_retained_recording(session_factory, game_id, profile_a)
    assert still_one_retained_row is not None
    assert still_one_retained_row.zip_sha256 == hashlib.sha256(retained_bytes).hexdigest()

    # "By nothing else": the ingester's own, already-implemented run touches nothing here.
    version_before_sweep = recomputed.parser_version
    await _run_ingester_once(session_factory)
    untouched = await _get_analysis(session_factory, game_id)
    assert untouched is not None
    assert untouched.parser_version == version_before_sweep

    # A third call, now that the row is published and not stale against the same engine version,
    # re-parses nothing (SC-006).
    await run_once(
        game_id,
        _BUDGET_SECONDS,
        recomputer,
        session_factory=session_factory,
        replay_provider=refusing_provider,
        extractor=upgraded_extractor,
        object_store=store,
    )
    assert len(upgraded_extractor.calls) == 1
    final = await _get_analysis(session_factory, game_id)
    assert final is not None
    assert final.result_key == recomputed.result_key


# --- FR-029 ---------------------------------------------------------------------------------------


async def test_every_read_of_a_retained_recording_is_logged_on_first_analysis_and_on_recompute(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """FR-029: "System MUST log every access to a recorded game this service holds — both the ones
    it serves... and the ones it only reads, which is what analysis and recomputation do." Every
    such row carries `retained_recording_id` and a null `replay_capture_id` (`data-model.md`'s check
    constraint), on the first analysis and on each later recompute — never merely the first."""
    from aoe2stats_analyzer.run import run_once

    game_id = 500_546_446
    profile_a, profile_b = 300_013, 300_014
    await _seed_match(
        session_factory,
        game_id=game_id,
        completed_at=datetime.now(UTC) - timedelta(days=1),
        profile_ids=[profile_a, profile_b],
    )
    first_requester = await _seed_user(session_factory)
    second_requester = await _seed_user(session_factory)
    raw_bytes = b"raw replay bytes for the access-log trail"
    provider = _FakeReplayProvider(
        ReplayBlob(content=raw_bytes, filename="r.zip", content_type="application/zip")
    )
    store = _FakeObjectStore()

    await run_once(
        game_id,
        _BUDGET_SECONDS,
        first_requester,
        session_factory=session_factory,
        replay_provider=provider,
        extractor=_FakeExtractor(
            point_of_view_profile_id=profile_a, engine_version=_ENGINE_VERSION_1
        ),
        object_store=store,
    )

    after_first = await _access_log_rows(session_factory)
    assert len(after_first) == 1
    first_row = after_first[0]
    assert first_row.replay_capture_id is None
    assert first_row.retained_recording_id is not None
    assert first_row.purpose != "download"

    retained = await _get_retained_recording(session_factory, game_id, profile_a)
    assert retained is not None
    assert first_row.retained_recording_id == retained.id

    # A recompute, triggered by a later engine version, is a second read of the same recording.
    await run_once(
        game_id,
        _BUDGET_SECONDS,
        second_requester,
        session_factory=session_factory,
        replay_provider=_RefusingReplayProvider(),
        extractor=_FakeExtractor(
            point_of_view_profile_id=profile_a, engine_version=_ENGINE_VERSION_2, max_calls=1
        ),
        object_store=store,
    )

    after_recompute = await _access_log_rows(session_factory)
    assert len(after_recompute) == 2
    second_row = next(row for row in after_recompute if row.id != first_row.id)
    assert second_row.replay_capture_id is None
    assert second_row.retained_recording_id == retained.id
    assert second_row.purpose != "download"


# --- FR-042 / T657: the published object key carries the identity digest -------------------------


def _analysis_keys(store: _FakeObjectStore) -> list[str]:
    return sorted(key for key in store.objects if key.startswith("analyses/"))


async def _publish_then_recompute_under(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    game_id: int,
    second_engine_version: str,
    mark_row_stale: bool,
) -> tuple[_FakeObjectStore, MatchAnalysis, bytes, MatchAnalysis]:
    """Publish once under `_ENGINE_VERSION_1`, then run again under `second_engine_version`.

    Returns the store, the row and the object bytes after the first publish, and the row after
    the second run. `mark_row_stale` rewinds the row's recorded identity digest so the staleness
    branch fires even when the second extractor carries the same identity as the first: that is
    the only way to reach "same identity, recomputed" through `run_once` (T657a's condition
    compares digests, so an unchanged identity is otherwise fresh and never recomputes).
    """
    from aoe2stats_analyzer.run import run_once

    profile_a, profile_b = 300_101, 300_102
    await _seed_match(
        session_factory,
        game_id=game_id,
        completed_at=datetime.now(UTC) - timedelta(days=1),
        profile_ids=[profile_a, profile_b],
    )
    requester = await _seed_user(session_factory)
    provider = _FakeReplayProvider(
        ReplayBlob(content=b"raw bytes", filename="r.zip", content_type="application/zip")
    )
    store = _FakeObjectStore()

    await run_once(
        game_id,
        _BUDGET_SECONDS,
        requester,
        session_factory=session_factory,
        replay_provider=provider,
        extractor=_FakeExtractor(
            point_of_view_profile_id=profile_a, engine_version=_ENGINE_VERSION_1
        ),
        object_store=store,
    )
    first = await _get_analysis(session_factory, game_id)
    assert first is not None
    assert first.result_key is not None
    first_bytes = store.objects[first.result_key]

    if mark_row_stale:
        async with session_scope(session_factory) as session:
            row = await session.get(MatchAnalysis, game_id)
            assert row is not None
            row.identity_digest = "0" * 64

    await run_once(
        game_id,
        _BUDGET_SECONDS,
        requester,
        session_factory=session_factory,
        replay_provider=_RefusingReplayProvider(),
        extractor=_FakeExtractor(
            point_of_view_profile_id=profile_a,
            engine_version=second_engine_version,
            max_calls=1,
        ),
        object_store=store,
    )
    second = await _get_analysis(session_factory, game_id)
    assert second is not None
    return store, first, first_bytes, second


async def test_a_published_object_is_keyed_by_its_identity_digest_and_the_row_records_it(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """T657: `analyses/{game_id}` then the identity digest's hex; `result_key` names that object
    and `identity_digest` records the digest T657a will compare."""
    import json

    game_id = 500_546_451
    store, first, first_bytes, _ = await _publish_then_recompute_under(
        session_factory,
        game_id=game_id,
        second_engine_version=_ENGINE_VERSION_2,
        mark_row_stale=False,
    )

    digest = json.loads(first_bytes)["identity"]["digest"]
    assert first.identity_digest == digest
    assert first.result_key == f"analyses/{game_id}/{digest}.json"
    assert first.result_key in store.objects


async def test_a_different_identity_writes_a_new_object_and_leaves_the_old_one_byte_identical(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """FR-042: a new parser version is a new analysis. Against the one-key-per-match code this
    fails: the second publish overwrote `analyses/{game_id}.json`, so the first object's bytes
    were gone and `analyses/` held a single key."""
    game_id = 500_546_452
    store, first, first_bytes, second = await _publish_then_recompute_under(
        session_factory,
        game_id=game_id,
        second_engine_version=_ENGINE_VERSION_2,
        mark_row_stale=False,
    )

    assert first.result_key is not None
    assert second.result_key is not None
    assert second.result_key != first.result_key
    assert second.identity_digest != first.identity_digest
    assert _analysis_keys(store) == sorted([first.result_key, second.result_key])
    assert store.objects[first.result_key] == first_bytes
    assert store.put_calls.count(first.result_key) == 1
    assert store.put_calls.count(second.result_key) == 1
    # The row keeps its primary key and names only the current document.
    assert second.game_id == first.game_id == game_id
    assert second.parser_version == _ENGINE_VERSION_2


async def test_recomputing_the_same_identity_writes_the_same_key_and_no_second_object(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """The contrast: an identical identity addresses the identical key, so a recompute that
    reproduces an analysis accumulates no duplicate object and writes nothing at all (T666d): the
    key is taken, so the object stays exactly as the first publish wrote it."""
    game_id = 500_546_453
    store, first, first_bytes, second = await _publish_then_recompute_under(
        session_factory,
        game_id=game_id,
        second_engine_version=_ENGINE_VERSION_1,
        mark_row_stale=True,
    )

    assert first.result_key is not None
    assert second.result_key == first.result_key
    assert second.identity_digest == first.identity_digest
    assert _analysis_keys(store) == [first.result_key]
    assert store.objects[first.result_key] == first_bytes
    assert store.put_calls.count(first.result_key) == 1


# --- FR-042 / T666d: a key, once written, is never written again --------------------------------


async def _analysis_bytes_and_row(
    session_factory: async_sessionmaker[AsyncSession], store: _FakeObjectStore, game_id: int
) -> tuple[MatchAnalysis, bytes]:
    row = await _get_analysis(session_factory, game_id)
    assert row is not None
    assert row.result_key is not None
    return row, store.objects[row.result_key]


async def _first_analysis(
    session_factory: async_sessionmaker[AsyncSession],
    store: _FakeObjectStore,
    *,
    game_id: int,
    requester: uuid.UUID | None = None,
) -> uuid.UUID:
    from aoe2stats_analyzer.run import run_once

    profile_a, profile_b = game_id + 1, game_id + 2
    if requester is None:
        await _seed_match(
            session_factory,
            game_id=game_id,
            completed_at=datetime.now(UTC) - timedelta(days=1),
            profile_ids=[profile_a, profile_b],
        )
        requester = await _seed_user(session_factory)
    await run_once(
        game_id,
        _BUDGET_SECONDS,
        requester,
        session_factory=session_factory,
        replay_provider=_FakeReplayProvider(
            ReplayBlob(content=b"raw bytes", filename="r.zip", content_type="application/zip"),
            max_calls=1,
        ),
        extractor=_BuildNamingExtractor(point_of_view_profile_id=profile_a, max_calls=1),
        object_store=store,
    )
    return requester


async def test_a_key_that_appears_between_the_decision_and_the_write_is_not_overwritten(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """The race: two stale requests recompute the same identity (the recompute path holds no
    lease), and the other one's object lands first. The loser writes nothing - the other writer's
    bytes survive untouched - and the row still ends published, pointing at the key. Against the
    unconditional put the loser's bytes (a new wall clock) replaced the winner's."""
    game_id = 500_666_401
    store = _FakeObjectStore()
    competitor = b'{"written": "first"}'
    store.competing_write = competitor

    await _first_analysis(session_factory, store, game_id=game_id)

    row, body = await _analysis_bytes_and_row(session_factory, store, game_id)
    assert row.state == MatchAnalysisState.PUBLISHED
    assert row.result_key == f"analyses/{game_id}/{row.identity_digest}.json"
    assert body == competitor
    assert store.put_calls.count(row.result_key) == 1  # the competitor's, not ours


async def test_an_object_left_by_a_crash_before_the_commit_is_adopted_not_rewritten(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """A crash after the put and before the commit leaves the object and a row that never became
    published. The next attempt, whose wall clock differs, finds the key taken: it writes nothing,
    publishes the row at that key and leaves the bytes exactly as the dead run left them."""
    game_id = 500_666_402
    store = _FakeObjectStore()
    requester = await _first_analysis(session_factory, store, game_id=game_id)
    row, body = await _analysis_bytes_and_row(session_factory, store, game_id)
    key = row.result_key
    assert key is not None
    puts_before = list(store.put_calls)

    # What the crash left: the row claimed and its lease expired, naming nothing.
    async with session_scope(session_factory) as session:
        crashed = await session.get(MatchAnalysis, game_id)
        assert crashed is not None
        crashed.state = MatchAnalysisState.RUNNING
        crashed.lease_expires_at = datetime.now(UTC) - timedelta(minutes=5)
        crashed.result_key = None
        crashed.identity_digest = None
        crashed.finished_at = None

    await _first_analysis(session_factory, store, game_id=game_id, requester=requester)

    after, after_body = await _analysis_bytes_and_row(session_factory, store, game_id)
    assert after.state == MatchAnalysisState.PUBLISHED
    assert after.result_key == key
    assert after.identity_digest == row.identity_digest
    assert after_body == body
    assert store.put_calls == puts_before


async def test_a_recompute_of_an_identity_already_stored_writes_nothing_and_republishes_the_row(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """The recompute path, same shape: a row marked stale whose recompute lands on the identity
    that is already stored points at the stored object and leaves its bytes alone."""
    published = await _publish_once(session_factory, game_id=500_666_403)
    async with session_scope(session_factory) as session:
        row = await session.get(MatchAnalysis, published.game_id)
        assert row is not None
        row.identity_digest = "0" * 64

    extractor = await _ask_again(session_factory, published, max_calls=1)

    assert len(extractor.calls) == 1
    after = await _get_analysis(session_factory, published.game_id)
    assert after is not None
    assert after.state == MatchAnalysisState.PUBLISHED
    assert after.result_key == published.key
    assert after.identity_digest == published.row.identity_digest
    assert published.store.objects[published.key] == published.body
    assert published.store.put_calls.count(published.key) == 1


async def test_a_new_identity_still_writes_its_own_key_when_the_old_one_exists(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """The contrast: a conditional create must not turn "the key exists" into "nothing to write"
    for a key that does not. The new identity's object is written once, the old one untouched."""
    published = await _publish_once(session_factory, game_id=500_666_404)

    await _ask_again(session_factory, published, engine_version=_ENGINE_VERSION_2, max_calls=1)

    after = await _get_analysis(session_factory, published.game_id)
    assert after is not None
    assert after.result_key is not None
    assert after.result_key != published.key
    assert published.store.put_calls.count(after.result_key) == 1
    assert published.store.objects[published.key] == published.body
    assert published.store.put_calls.count(published.key) == 1


async def test_a_refused_gap_insert_writes_no_object_even_with_put_if_absent(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T666c's ordering survives the conditional create: the rows are flushed first, so a refused
    insert never reaches the store."""
    from aoe2stats_analyzer import run as run_module

    async def refuse(*args: Any, **kwargs: Any) -> None:
        raise ValueError("refused")

    monkeypatch.setattr(run_module.KnowledgeGapsRepository, "record_gaps", refuse)
    store = _FakeObjectStore()

    await _first_analysis(session_factory, store, game_id=500_666_405)

    assert not [key for key in store.objects if key.startswith("analyses/")]
    assert store.put_calls.count("analyses/500666405") == 0


# --- FR-042 / T657a: staleness compares the identity digest, not the parser alone ----------------

#: A build the packaged knowledge base holds a promoted snapshot for
#: (`packages/knowledge/snapshots`), so the document's `knowledge` component names a snapshot
#: instead of the absence record.
_SNAPSHOT_BUILD = 180059


#: A build the packaged knowledge base holds no snapshot for: the identity's knowledge component is
#: then the absence record, which names the build under `build` instead of `describes_build`.
_BUILD_WITHOUT_A_SNAPSHOT = 999_999

#: The raw civilisation id the packaged snapshot's `effects.toml` names Franks under, and an unit
#: its `rules.json` lists (an Archer): a modelled civilisation asking about a known entity, so the
#: packaged snapshot reports no gap for the pair and a snapshot that dropped the entity reports six.
_FRANKS_RAW_ID = 2
_ARCHER_ID = 4


class _BuildNamingExtractor(_FakeExtractor):
    """`_FakeExtractor` whose stream names a build: the knowledge component of the identity is a
    function of the recording's build, so a test about the knowledge version needs one. `build=None`
    is a stream that names none, which the document records as `-1`.

    `queued_unit_id` seats one Franks player who queues that unit, so the coverage pass has an
    entity to ask the snapshot about: which gaps the document carries then depends on the snapshot
    that answered, not only on the build."""

    def __init__(
        self,
        *,
        build: int | None = _SNAPSHOT_BUILD,
        queued_unit_id: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._build = build
        self._queued_unit_id = queued_unit_id

    def events(self, zip_bytes: bytes) -> Iterator[CanonicalEvent]:
        if self._build is None:
            return iter(())
        participants = (
            (ParticipantEntry(slot=1, civilisation=_FRANKS_RAW_ID, team=None),)
            if self._queued_unit_id is not None
            else ()
        )
        stream = [
            CanonicalEvent(
                clock_ms=0,
                kind=EventKind.MATCH_STARTED,
                payload=MatchStartedPayload(
                    build=self._build, map_name=None, participants=participants
                ),
            )
        ]
        if self._queued_unit_id is not None:
            stream.append(
                CanonicalEvent(
                    clock_ms=1_000,
                    kind=EventKind.UNIT_QUEUED,
                    participant=1,
                    payload=UnitQueuedPayload(
                        unit_id=self._queued_unit_id, building_type=87, building_object=1, count=1
                    ),
                )
            )
        return iter(stream)


@dataclass(frozen=True, slots=True)
class _Published:
    game_id: int
    requester: uuid.UUID
    profile_id: int
    store: _FakeObjectStore
    row: MatchAnalysis
    key: str
    body: bytes


async def _publish_once(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    game_id: int,
    build: int | None = _SNAPSHOT_BUILD,
    queued_unit_id: int | None = None,
) -> _Published:
    """One ordinary first analysis under `_ENGINE_VERSION_1`, naming a build that has a snapshot
    unless `build` says otherwise."""
    from aoe2stats_analyzer.run import run_once

    profile_a, profile_b = game_id + 1, game_id + 2
    await _seed_match(
        session_factory,
        game_id=game_id,
        completed_at=datetime.now(UTC) - timedelta(days=1),
        profile_ids=[profile_a, profile_b],
    )
    requester = await _seed_user(session_factory)
    store = _FakeObjectStore()
    await run_once(
        game_id,
        _BUDGET_SECONDS,
        requester,
        session_factory=session_factory,
        replay_provider=_FakeReplayProvider(
            ReplayBlob(content=b"raw bytes", filename="r.zip", content_type="application/zip"),
            max_calls=1,
        ),
        extractor=_BuildNamingExtractor(
            build=build,
            queued_unit_id=queued_unit_id,
            point_of_view_profile_id=profile_a,
            max_calls=1,
        ),
        object_store=store,
    )
    row = await _get_analysis(session_factory, game_id)
    assert row is not None
    assert row.identity_digest is not None
    assert row.result_key is not None
    return _Published(
        game_id=game_id,
        requester=requester,
        profile_id=profile_a,
        store=store,
        row=row,
        key=row.result_key,
        body=store.objects[row.result_key],
    )


async def _ask_again(
    session_factory: async_sessionmaker[AsyncSession],
    published: _Published,
    *,
    engine_version: str = _ENGINE_VERSION_1,
    max_calls: int,
    build: int | None = _SNAPSHOT_BUILD,
    queued_unit_id: int | None = None,
) -> _BuildNamingExtractor:
    """Open the same match again, the source forbidden, and return the extractor to read its calls.
    `max_calls` is the canary: 0 where nothing may be parsed, 1 where exactly one recompute may."""
    from aoe2stats_analyzer.run import run_once

    extractor = _BuildNamingExtractor(
        build=build,
        queued_unit_id=queued_unit_id,
        point_of_view_profile_id=published.profile_id,
        engine_version=engine_version,
        max_calls=max_calls,
    )
    await run_once(
        published.game_id,
        _BUDGET_SECONDS,
        published.requester,
        session_factory=session_factory,
        replay_provider=_RefusingReplayProvider(),
        extractor=extractor,
        object_store=published.store,
    )
    return extractor


async def _assert_recomputed_to_a_new_key(
    session_factory: async_sessionmaker[AsyncSession],
    published: _Published,
    extractor: _BuildNamingExtractor,
) -> MatchAnalysis:
    """A changed identity writes a new object, the row names it, and the old one is untouched."""
    assert len(extractor.calls) == 1, "a changed identity must recompute from the retained bytes"
    after = await _get_analysis(session_factory, published.game_id)
    assert after is not None
    assert after.state == MatchAnalysisState.PUBLISHED
    assert after.identity_digest != published.row.identity_digest
    assert after.result_key is not None
    assert after.result_key != published.key
    assert after.result_key == f"analyses/{published.game_id}/{after.identity_digest}.json"
    assert _analysis_keys(published.store) == sorted([published.key, after.result_key])
    assert published.store.objects[published.key] == published.body
    assert published.store.put_calls.count(published.key) == 1
    return after


async def test_a_new_knowledge_snapshot_for_the_same_build_triggers_a_recompute_and_a_new_key(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """FR-042: the parser is unchanged, the recording is unchanged, the build is unchanged - only
    the snapshot that answers for the build is a different one. The parser-only condition returned
    early here and the new knowledge never produced a new analysis.

    The second snapshot is real (`tests/snapshot_refresh.py`, as `test_reproducibility.py` promotes
    one): promoted, with the first demoted, so the identity and the coverage pass both resolve it.
    It drops the Archer the stream queues, so the gaps tell which snapshot they were computed from:
    patching one resolver instead left the coverage pass on the real snapshot, and a document whose
    identity named the refresh while its gaps described the old knowledge."""
    root = isolate_snapshot_root(monkeypatch, tmp_path)
    published = await _publish_once(session_factory, game_id=500_657_001, queued_unit_id=_ARCHER_ID)
    first_document = json.loads(published.body)
    assert "entity-absent" not in {gap["cause"] for gap in first_document["knowledge_gaps"]}, (
        "the first snapshot knows the Archer"
    )

    refreshed_digest = promote_a_refreshed_snapshot(root, without_entity=("unit", str(_ARCHER_ID)))

    extractor = await _ask_again(session_factory, published, max_calls=1, queued_unit_id=_ARCHER_ID)

    after = await _assert_recomputed_to_a_new_key(session_factory, published, extractor)
    document = json.loads(published.store.objects[after.result_key or ""])
    knowledge = document["identity"]["knowledge"]
    assert knowledge["digest"] == refreshed_digest
    assert knowledge["digest"] != first_document["identity"]["knowledge"]["digest"]
    assert knowledge["source_version"].endswith("-refresh")
    # The gaps came from the same snapshot the identity names: the refreshed one lacks the Archer,
    # the first did not.
    gaps = document["knowledge_gaps"]
    assert gaps, "the coverage pass must have resolved the refreshed snapshot"
    assert {gap["cause"] for gap in gaps} == {"entity-absent"}
    assert {(gap["entity"]["kind"], gap["entity"]["id"]) for gap in gaps} == {
        ("unit", str(_ARCHER_ID))
    }
    assert gaps != first_document["knowledge_gaps"]
    assert {gap["build"] for gap in gaps} == {_SNAPSHOT_BUILD}
    assert after.parser_version == published.row.parser_version


async def test_a_new_analytics_version_triggers_a_recompute_and_a_new_key(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-042: analytics is a real version, so a banding or coverage change recomputes."""
    published = await _publish_once(session_factory, game_id=500_657_002)
    monkeypatch.setattr(extract, "ANALYTICS_VERSION", f"{extract.ANALYTICS_VERSION}+next")

    extractor = await _ask_again(session_factory, published, max_calls=1)

    await _assert_recomputed_to_a_new_key(session_factory, published, extractor)


async def test_a_new_parser_version_still_triggers_a_recompute_and_a_new_key(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """The case the old condition already handled, through the digest path: the row now carries a
    digest, and the parser version is one of the identity's components."""
    published = await _publish_once(session_factory, game_id=500_657_003)

    extractor = await _ask_again(
        session_factory, published, engine_version=_ENGINE_VERSION_2, max_calls=1
    )

    after = await _assert_recomputed_to_a_new_key(session_factory, published, extractor)
    assert after.parser_version == _ENGINE_VERSION_2


async def test_an_unchanged_identity_is_fresh_and_never_puts_a_key_twice(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """The contrast, and `contracts/analysis-document.md`'s "a key, once written, is never written
    again": the same identity is served as it is. The extractor's canary allows no call at all, and
    the store records exactly the one put the first analysis made - no exists-check on the store is
    needed, because a fresh row never reaches the write."""
    published = await _publish_once(session_factory, game_id=500_657_004)
    puts_after_first_analysis = list(published.store.put_calls)

    for _ in range(2):
        extractor = await _ask_again(session_factory, published, max_calls=0)
        assert extractor.calls == []

    after = await _get_analysis(session_factory, published.game_id)
    assert after is not None
    assert after.result_key == published.key
    assert after.identity_digest == published.row.identity_digest
    assert published.store.put_calls == puts_after_first_analysis
    assert _analysis_keys(published.store) == [published.key]


async def test_a_row_published_before_the_digest_existed_recomputes_once_then_is_fresh(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """A NULL `identity_digest` reads as stale - the intended outcome for a legacy row, whose
    parser version matches the running engine, so the old condition left it alone for good. The
    next call, with the same identity, is fresh: one recompute, not one per request."""
    published = await _publish_once(session_factory, game_id=500_657_005)
    legacy_key = f"analyses/{published.game_id}.json"
    async with session_scope(session_factory) as session:
        row = await session.get(MatchAnalysis, published.game_id)
        assert row is not None
        row.identity_digest = None
        row.result_key = legacy_key
    published.store.objects[legacy_key] = b"{}"

    recomputed = await _ask_again(session_factory, published, max_calls=1)

    assert len(recomputed.calls) == 1
    after = await _get_analysis(session_factory, published.game_id)
    assert after is not None
    assert after.identity_digest == published.row.identity_digest
    assert after.result_key == published.key
    assert published.store.objects[legacy_key] == b"{}"

    assert published.store.objects[published.key] == published.body
    assert published.store.put_calls.count(published.key) == 1
    puts_after_recompute = list(published.store.put_calls)
    again = await _ask_again(session_factory, published, max_calls=0)
    assert again.calls == []
    assert published.store.put_calls == puts_after_recompute


async def test_a_row_without_a_recorded_build_recomputes_once_then_is_fresh(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """Replaces "a stored document that cannot be read as an identity is stale" (T666b): the
    staleness test no longer reads the stored document, so that case cannot exist. Its row-based
    equivalent is the row that cannot supply the current digest's inputs - here a NULL
    `recording_build` beside a digest - which cannot confirm freshness either, and recomputing
    replaces it with a row that can."""
    published = await _publish_once(session_factory, game_id=500_657_006)
    async with session_scope(session_factory) as session:
        row = await session.get(MatchAnalysis, published.game_id)
        assert row is not None
        row.recording_build = None

    recomputed = await _ask_again(session_factory, published, max_calls=1)

    assert len(recomputed.calls) == 1
    after = await _get_analysis(session_factory, published.game_id)
    assert after is not None
    assert after.identity_digest == published.row.identity_digest
    assert after.recording_build == _SNAPSHOT_BUILD
    assert after.result_key == published.key

    again = await _ask_again(session_factory, published, max_calls=0)
    assert again.calls == []


# --- T666b: the build is on the row, and the staleness path never touches the object store -------


async def test_the_recordings_build_is_written_on_publish_whichever_way_the_stream_named_it(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """data-model.md §8: the snapshot's `describes_build`, the absence record's `build`, and `-1`
    where the stream named none (§7) - one value, read from the document's knowledge record."""
    expected = {
        500_666_001: (_SNAPSHOT_BUILD, _SNAPSHOT_BUILD),
        500_666_011: (_BUILD_WITHOUT_A_SNAPSHOT, _BUILD_WITHOUT_A_SNAPSHOT),
        500_666_021: (None, -1),
    }
    for game_id, (named, recorded) in expected.items():
        published = await _publish_once(session_factory, game_id=game_id, build=named)
        assert published.row.recording_build == recorded


async def test_a_row_published_under_the_minus_one_build_is_fresh_on_the_next_request(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """The sentinel is a real value on the row, not a missing one: `-1` resolves to the same
    absence record the document carries, so the digest matches and nothing is recomputed."""
    published = await _publish_once(session_factory, game_id=500_666_031, build=None)
    assert published.row.recording_build == -1

    again = await _ask_again(session_factory, published, max_calls=0, build=None)

    assert again.calls == []
    after = await _get_analysis(session_factory, published.game_id)
    assert after is not None
    assert after.result_key == published.key


async def test_a_fresh_published_match_is_served_without_reading_the_object_store(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SC-006: a request on a fresh published match does the row read it did before this feature.
    A store outage must not turn it into a 500, so the store's `get` is made to fail outright."""
    published = await _publish_once(session_factory, game_id=500_666_041)
    published.store.get_calls.clear()

    async def outage(key: str) -> bytes:
        raise ConnectionError(f"object store unreachable reading {key}")

    monkeypatch.setattr(published.store, "get", outage)

    extractor = await _ask_again(session_factory, published, max_calls=0)

    assert extractor.calls == []
    assert published.store.get_calls == []


async def test_a_stale_match_reads_the_store_only_for_the_retained_recording(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """The staleness decision reads no object. The one read a recompute makes is the retained
    recording, after the decision; the current analysis's document is never read - against the old
    code its key came first."""
    published = await _publish_once(session_factory, game_id=500_666_051)
    retained = await _get_analysis_recording(session_factory, published)
    published.store.get_calls.clear()

    extractor = await _ask_again(
        session_factory, published, engine_version=_ENGINE_VERSION_2, max_calls=1
    )

    assert len(extractor.calls) == 1
    assert published.store.get_calls == [retained.object_key]


async def _get_analysis_recording(
    session_factory: async_sessionmaker[AsyncSession], published: _Published
) -> RetainedRecording:
    retained = await _get_retained_recording(
        session_factory, published.game_id, published.profile_id
    )
    assert retained is not None
    return retained


@dataclass(frozen=True, slots=True)
class _RowSnapshot:
    state: MatchAnalysisState
    identity_digest: str | None
    recording_build: int | None
    result_key: str | None
    parser_version: str | None
    finished_at: datetime | None


def _snapshot_of(row: MatchAnalysis) -> _RowSnapshot:
    return _RowSnapshot(
        state=row.state,
        identity_digest=row.identity_digest,
        recording_build=row.recording_build,
        result_key=row.result_key,
        parser_version=row.parser_version,
        finished_at=row.finished_at,
    )


async def _assert_a_deployment_fault_stops_the_request_before_any_recompute(
    session_factory: async_sessionmaker[AsyncSession],
    published: _Published,
    *,
    extractor_dependencies: dict[str, str] | None = None,
) -> None:
    """T666b: an error computing the current digest is a deployment fault, not staleness. It
    propagates; the extractor is never called, no retained recording is read, no access-log row is
    written and the row is exactly as it was."""
    from aoe2stats_analyzer.run import run_once

    before = _snapshot_of(published.row)
    log_before = len(await _access_log_rows(session_factory))
    published.store.get_calls.clear()
    extractor = _BuildNamingExtractor(point_of_view_profile_id=published.profile_id, max_calls=0)
    if extractor_dependencies is not None:
        extractor.engine_dependencies = extractor_dependencies

    with pytest.raises(ValueError):
        await run_once(
            published.game_id,
            _BUDGET_SECONDS,
            published.requester,
            session_factory=session_factory,
            replay_provider=_RefusingReplayProvider(),
            extractor=extractor,
            object_store=published.store,
        )

    assert extractor.calls == []
    assert published.store.get_calls == []
    assert len(await _access_log_rows(session_factory)) == log_before
    after = await _get_analysis(session_factory, published.game_id)
    assert after is not None
    assert _snapshot_of(after) == before


@pytest.mark.parametrize(
    "fault", [snapshot.SnapshotError, snapshot.SnapshotDigestMismatch], ids=lambda c: c.__name__
)
async def test_a_broken_snapshot_during_the_staleness_check_raises_instead_of_reading_as_stale(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
    fault: type[snapshot.SnapshotError],
) -> None:
    """Reviewer H2: `SnapshotError` is a `ValueError`, and the old `except` read it as "stale" - so
    every click cost a retained-recording read, an access-log row and a full parse, then a 500."""
    published = await _publish_once(session_factory, game_id=500_666_061)

    def broken(build: int) -> object:
        raise fault(f"snapshot for build {build} cannot be loaded")

    monkeypatch.setattr(extract, "snapshot_for", broken)

    await _assert_a_deployment_fault_stops_the_request_before_any_recompute(
        session_factory, published
    )


async def test_an_empty_dependency_record_during_the_staleness_check_raises_too(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """FR-044's refusal is the same kind of fault: not a reason to parse, and not "stale"."""
    published = await _publish_once(session_factory, game_id=500_666_071)

    await _assert_a_deployment_fault_stops_the_request_before_any_recompute(
        session_factory, published, extractor_dependencies={}
    )


# --- T666c: a failed recompute keeps the analysis it was replacing -------------------------------
#
# 003's failure path (`_mark_failed`: `failed`, `result_key` NULL, terminal) was written for a first
# analysis. A recompute is triggered by a knowledge or analytics change on a row that is already
# served, so the same path would unpublish a good analysis because a newer one could not be built
# (FR-042). Decided 2026-10-03: on the recompute path the refusal is logged and the row stays as it
# was. The same six causes are run through both paths below; each is a source this feature added or
# a refusal 003 already routed to `failed`.


@pytest.fixture(autouse=True)
def _enable_the_analyzer_logger() -> Iterator[None]:
    """`infra/migrations/env.py` runs `logging.config.fileConfig` the first time the throwaway
    database is migrated, which disables every logger that already exists - this package's among
    them - so a `caplog` assertion would otherwise depend on test order (see
    `apps/ingester/tests/test_run.py`'s identical fixture)."""
    run_module.logger.disabled = False
    yield
    run_module.logger.disabled = False


_GAP_BUILD_OUT_OF_RANGE = 2**40  # past the `build` integer column: the insert itself is refused


class _StrayBuildNamingExtractor(_BuildNamingExtractor):
    """A build-naming extractor whose document carries a field the register does not publish."""

    def extract(self, zip_bytes: bytes) -> _FakeMatchTimeline:
        timeline = super().extract(zip_bytes)
        stray = _ParticipantWithAStrayField(
            profile_id=1, player_number=1, civ_id=1, resolved_team_id=1
        )
        return _FakeMatchTimeline(
            engine_name=timeline.engine_name,
            engine_version=timeline.engine_version,
            point_of_view_profile_id=timeline.point_of_view_profile_id,
            world_time_ms=timeline.world_time_ms,
            participants=(stray,),
        )


@dataclass(frozen=True, slots=True)
class _Cause:
    """One way an analysis can be refused. `install(monkeypatch, allowed_snapshot_reads)` plants the
    fault; `allowed_snapshot_reads` is how many real `snapshot_for` calls come first - the recompute
    path's staleness check makes one before the build does, and a first analysis makes none."""

    name: str
    error_class: str | None
    extractor: Callable[..., _BuildNamingExtractor]
    install: Callable[[pytest.MonkeyPatch, int], None]
    #: Whether the identity the refused analysis would have carried can still be computed.
    would_be_digest_known: bool = True


def _no_fault(monkeypatch: pytest.MonkeyPatch, allowed_snapshot_reads: int) -> None:
    return None


def _a_placement_fault(monkeypatch: pytest.MonkeyPatch, allowed_snapshot_reads: int) -> None:
    def refuse(datum: str, tier: object) -> None:
        raise TierPlacementError(f"{datum} may not be placed at an ordinary path")

    monkeypatch.setattr(extract, "require_outside_inferred", refuse)


def _a_snapshot_fault(monkeypatch: pytest.MonkeyPatch, allowed_snapshot_reads: int) -> None:
    real_snapshot_for = extract.snapshot_for
    reads = 0

    def flaky(build: int) -> object:
        nonlocal reads
        reads += 1
        if reads > allowed_snapshot_reads:
            raise snapshot.SnapshotDigestMismatch(f"snapshot for build {build} fails its digest")
        return real_snapshot_for(build)

    monkeypatch.setattr(extract, "snapshot_for", flaky)


def _a_serialiser_fault(monkeypatch: pytest.MonkeyPatch, allowed_snapshot_reads: int) -> None:
    def refuse(document: object) -> bytes:
        raise ValueError("non-finite float at participants[0].actions_per_minute")

    monkeypatch.setattr(run_module, "canonical_bytes", refuse)


def _a_gap_insert_fault(monkeypatch: pytest.MonkeyPatch, allowed_snapshot_reads: int) -> None:
    def impossible(document: object) -> tuple[GapToRecord, ...]:
        return (
            GapToRecord(
                build=_GAP_BUILD_OUT_OF_RANGE,
                entity_kind="build",
                entity_id="*",
                field="*",
                civilisation_id=None,
                cause="no-snapshot-for-build",
                severity="blocking",
            ),
        )

    monkeypatch.setattr(run_module, "gap_rows", impossible)


def _parse_failing(**kwargs: Any) -> _BuildNamingExtractor:
    return _BuildNamingExtractor(
        raises=EngineParseError("the archive is well-formed but the engine rejected it"), **kwargs
    )


_CAUSES = (
    _Cause("document-invalid", "DocumentInvalid", _StrayBuildNamingExtractor, _no_fault),
    _Cause("parse-failure", "EngineParseError", _parse_failing, _no_fault),
    _Cause("tier-placement", "TierPlacementError", _BuildNamingExtractor, _a_placement_fault),
    _Cause(
        "snapshot-error",
        "SnapshotDigestMismatch",
        _BuildNamingExtractor,
        _a_snapshot_fault,
        would_be_digest_known=False,
    ),
    _Cause("serialiser-refusal", "ValueError", _BuildNamingExtractor, _a_serialiser_fault),
    _Cause("gap-insert-error", None, _BuildNamingExtractor, _a_gap_insert_fault),
)
_CAUSE_IDS = [cause.name for cause in _CAUSES]


async def _gap_row_count(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_scope(session_factory) as session:
        result = await session.execute(select(AnalysisKnowledgeGap.id))
        return len(result.all())


async def _set_lease(
    session_factory: async_sessionmaker[AsyncSession], game_id: int, lease: datetime | None
) -> None:
    async with session_scope(session_factory) as session:
        row = await session.get(MatchAnalysis, game_id)
        assert row is not None
        row.lease_expires_at = lease


async def _ask_to_recompute(
    session_factory: async_sessionmaker[AsyncSession],
    published: _Published,
    cause: _Cause,
    *,
    max_calls: int = 1,
) -> _BuildNamingExtractor:
    """Open a published match again under a newer parser, so it is stale, with the source forbidden
    and `cause` planted. `max_calls` is the canary on the extractor."""
    extractor = cause.extractor(
        point_of_view_profile_id=published.profile_id,
        engine_version=_ENGINE_VERSION_2,
        max_calls=max_calls,
    )
    await run_module.run_once(
        published.game_id,
        _BUDGET_SECONDS,
        published.requester,
        session_factory=session_factory,
        replay_provider=_RefusingReplayProvider(),
        extractor=extractor,
        object_store=published.store,
    )
    return extractor


@pytest.mark.parametrize("cause", _CAUSES, ids=_CAUSE_IDS)
async def test_a_failed_recompute_keeps_the_analysis_it_was_replacing(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    cause: _Cause,
) -> None:
    """FR-042 over the literal reading of FR-048: the row stays published on its previous key,
    digest and build, the old object is still the one served and untouched, nothing new is written,
    and the refusal is logged with the match, the old identity digest, the would-be one and why."""
    published = await _publish_once(
        session_factory, game_id=500_666_100 + _CAUSE_IDS.index(cause.name) * 10
    )
    before = _snapshot_of(published.row)
    gaps_before = await _gap_row_count(session_factory)
    puts_before = list(published.store.put_calls)
    objects_before = dict(published.store.objects)
    cause.install(monkeypatch, 1)

    with caplog.at_level(logging.WARNING, logger=run_module.logger.name):
        await _ask_to_recompute(session_factory, published, cause)

    after = await _get_analysis(session_factory, published.game_id)
    assert after is not None
    assert _snapshot_of(after) == before
    assert after.state == MatchAnalysisState.PUBLISHED
    assert after.result_key == published.key
    assert after.error_class is None
    assert published.store.put_calls == puts_before
    assert published.store.objects == objects_before
    assert published.store.objects[published.key] == published.body
    assert await _gap_row_count(session_factory) == gaps_before

    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 1, messages
    message = messages[0]
    assert str(published.game_id) in message
    assert published.row.identity_digest is not None
    assert published.row.identity_digest in message
    if cause.error_class is not None:
        assert cause.error_class in message
    if cause.would_be_digest_known:
        would_be = extract.current_identity_digest(
            _BuildNamingExtractor(
                point_of_view_profile_id=published.profile_id, engine_version=_ENGINE_VERSION_2
            ),
            recording={
                "object_key": (
                    await _get_analysis_recording(session_factory, published)
                ).object_key,
                "sha256": (await _get_analysis_recording(session_factory, published)).zip_sha256,
            },
            build=_SNAPSHOT_BUILD,
        )
        assert would_be in message


@pytest.mark.parametrize("cause", _CAUSES, ids=_CAUSE_IDS)
async def test_a_first_analysis_that_cannot_be_completed_ends_failed_and_is_never_fetched_again(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
    cause: _Cause,
) -> None:
    """The contrast, and the new sources: with no analysis to keep, 003's failure path applies
    unchanged - `failed`, no result, no object, no gap rows. A cause that instead raised out of
    `run_once` left the row `running`, and once its lease expired the next request claimed it again
    and fetched the recording from the source a second time (the lease is the only thing that
    decides; `claim_for_analysis` never looks at what was already retained)."""
    game_id = 500_666_200 + _CAUSE_IDS.index(cause.name) * 10
    profile_a, profile_b = game_id + 1, game_id + 2
    await _seed_match(
        session_factory,
        game_id=game_id,
        completed_at=datetime.now(UTC) - timedelta(days=1),
        profile_ids=[profile_a, profile_b],
    )
    requester = await _seed_user(session_factory)
    provider = _FakeReplayProvider(
        ReplayBlob(content=b"raw bytes", filename="r.zip", content_type="application/zip"),
        max_calls=1,
    )
    store = _FakeObjectStore()
    cause.install(monkeypatch, 0)

    async def ask() -> None:
        await run_module.run_once(
            game_id,
            _BUDGET_SECONDS,
            requester,
            session_factory=session_factory,
            replay_provider=provider,
            extractor=cause.extractor(point_of_view_profile_id=profile_a, max_calls=1),
            object_store=store,
        )

    await ask()

    row = await _get_analysis(session_factory, game_id)
    assert row is not None
    assert row.state == MatchAnalysisState.FAILED
    assert row.result_key is None
    assert row.identity_digest is None
    assert row.error_class
    if cause.error_class is not None:
        assert row.error_class == cause.error_class
    assert row.error_message
    assert _analysis_keys(store) == []
    assert await _gap_row_count(session_factory) == 0

    # The scenario the fix closes: even once any lease would have lapsed, nothing is fetched again
    # (`provider` raises on a second call).
    await _set_lease(session_factory, game_id, datetime.now(UTC) - timedelta(minutes=5))
    await ask()
    assert len(provider.calls) == 1
    again = await _get_analysis(session_factory, game_id)
    assert again is not None
    assert again.state == MatchAnalysisState.FAILED


async def test_a_published_row_carries_no_lease(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """The retry window below is kept in `lease_expires_at`, so a publish must clear the lease the
    claim took: otherwise a recompute asked for inside the claim's own lease would read as backed
    off."""
    published = await _publish_once(session_factory, game_id=500_666_301)
    assert published.row.lease_expires_at is None


async def test_a_failed_recompute_is_not_attempted_again_until_the_retry_window_passes(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """The bound on repetition. The cause is a function of the recording and the code, so asking
    again changes nothing - yet the digest still differs, so without a bound every click would read
    the retained recording, log an access and parse it in full. The refusal puts the row's
    `lease_expires_at` (unused by a published row) out by the retry window and the recompute path
    skips the row until then: one parse per window, not one per request."""
    published = await _publish_once(session_factory, game_id=500_666_302)
    cause = _CAUSES[0]
    await _ask_to_recompute(session_factory, published, cause)
    refused = await _get_analysis(session_factory, published.game_id)
    assert refused is not None
    assert refused.lease_expires_at is not None
    assert refused.lease_expires_at > datetime.now(UTC) + timedelta(minutes=30)
    log_after_first = len(await _access_log_rows(session_factory))
    published.store.get_calls.clear()

    # Inside the window: nothing is read, logged or parsed, and the row is exactly as it was.
    inside = await _ask_to_recompute(session_factory, published, cause, max_calls=0)

    assert inside.calls == []
    assert published.store.get_calls == []
    assert len(await _access_log_rows(session_factory)) == log_after_first
    unchanged = await _get_analysis(session_factory, published.game_id)
    assert unchanged is not None
    assert _snapshot_of(unchanged) == _snapshot_of(published.row)
    assert unchanged.lease_expires_at == refused.lease_expires_at

    # Past the window: one more attempt is made, and it is a recompute again (the fix may be in).
    await _set_lease(session_factory, published.game_id, datetime.now(UTC) - timedelta(seconds=1))
    past = await _ask_to_recompute(session_factory, published, cause)
    assert len(past.calls) == 1
    assert len(await _access_log_rows(session_factory)) == log_after_first + 1


async def test_a_recompute_after_the_retry_window_that_succeeds_publishes_and_clears_the_window(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """The window is a backoff, not a verdict: once the cause is fixed the next attempt past it
    publishes a new key, and the row carries no lease again."""
    published = await _publish_once(session_factory, game_id=500_666_303)
    await _ask_to_recompute(session_factory, published, _CAUSES[0])
    await _set_lease(session_factory, published.game_id, datetime.now(UTC) - timedelta(seconds=1))

    healthy = _Cause("healthy", None, _BuildNamingExtractor, _no_fault)
    extractor = await _ask_to_recompute(session_factory, published, healthy)

    after = await _assert_recomputed_to_a_new_key(session_factory, published, extractor)
    assert after.lease_expires_at is None


# --- T666h: a broken deployment is refused before anything is claimed -----------------------
#
# T666c routed a snapshot fault on a first analysis to 003's `_mark_failed`, but it surfaces after
# `claim_for_analysis`: the request had already fetched the recording from the source (capture's
# budget, constitution I), retained it, written an access-log row and parsed it, and the match then
# ended terminally `failed` - which fixing the deployment does not undo. What is independent of any
# recording (every installed snapshot loads and verifies, no two promoted snapshots describe one
# build, the extractor's dependency record is not empty) is checked before the claim instead.


@dataclass(slots=True)
class _FirstRequest:
    session_factory: async_sessionmaker[AsyncSession]
    game_id: int
    requester: uuid.UUID
    profile_id: int
    provider: _FakeReplayProvider
    store: _FakeObjectStore

    async def ask(
        self, *, dependencies: dict[str, str] | None = None, max_calls: int = 1
    ) -> _BuildNamingExtractor:
        extractor = _BuildNamingExtractor(
            point_of_view_profile_id=self.profile_id, max_calls=max_calls
        )
        if dependencies is not None:
            extractor.engine_dependencies = dependencies
        await run_module.run_once(
            self.game_id,
            _BUDGET_SECONDS,
            self.requester,
            session_factory=self.session_factory,
            replay_provider=self.provider,
            extractor=extractor,
            object_store=self.store,
        )
        return extractor


async def _a_first_request(
    session_factory: async_sessionmaker[AsyncSession], *, game_id: int
) -> _FirstRequest:
    profile_a, profile_b = game_id + 1, game_id + 2
    await _seed_match(
        session_factory,
        game_id=game_id,
        completed_at=datetime.now(UTC) - timedelta(days=1),
        profile_ids=[profile_a, profile_b],
    )
    return _FirstRequest(
        session_factory=session_factory,
        game_id=game_id,
        requester=await _seed_user(session_factory),
        profile_id=profile_a,
        provider=_FakeReplayProvider(
            ReplayBlob(content=b"raw bytes", filename="r.zip", content_type="application/zip"),
            max_calls=1,
        ),
        store=_FakeObjectStore(),
    )


async def _assert_the_request_touched_nothing(request: _FirstRequest) -> None:
    """The refusal's whole point: no byte fetched, no row written, nothing retained or logged."""
    assert request.provider.calls == []
    assert await _get_analysis(request.session_factory, request.game_id) is None
    assert (
        await _get_retained_recording(request.session_factory, request.game_id, request.profile_id)
        is None
    )
    assert await _access_log_rows(request.session_factory) == []
    assert request.store.objects == {}
    assert request.store.put_calls == []


def _break_a_snapshot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Callable[[], None]:
    """Corrupt the one installed snapshot (its content no longer matches the recorded digest) and
    return the repair. The root is a throwaway copy; the committed tree is never touched."""
    root = isolate_snapshot_root(monkeypatch, tmp_path)
    effects_file = root / REAL_SNAPSHOT_DIRECTORY / "effects.toml"
    original = effects_file.read_bytes()
    effects_file.write_bytes(original + b"\n# edited after the digest was recorded\n")
    return lambda: effects_file.write_bytes(original)


def _promote_two_snapshots_of_one_build(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Callable[[], None]:
    """A second, byte-identical copy of the promoted snapshot under another directory name: both
    load and verify, and both are promoted for one build - the condition `snapshot_for` raises on.
    Returns the repair: the copy removed *and the process's caches cleared*, because this fault is
    unlike a digest mismatch - both snapshots load and verify, so the tree read is a success and a
    success is cached for the process's life. Repairing it is a redeploy (a new process), which is
    what the cache clear stands for; the packaged tree is immutable inside one."""
    root = isolate_snapshot_root(monkeypatch, tmp_path)
    duplicate = root / "aoe2techtree-180059-duplicate"
    shutil.copytree(root / REAL_SNAPSHOT_DIRECTORY, duplicate)

    def repair() -> None:
        shutil.rmtree(duplicate)
        clear_snapshot_resolution_caches()

    return repair


def _no_deployment_fault(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Callable[[], None]:
    return lambda: None


@dataclass(frozen=True, slots=True)
class _DeploymentFaultCase:
    name: str
    install: Callable[[pytest.MonkeyPatch, Path], Callable[[], None]]
    #: The extractor's dependency record for the faulty request; `None` keeps the healthy one.
    dependencies: dict[str, str] | None
    fault_class: str


_DEPLOYMENT_FAULTS = (
    _DeploymentFaultCase(
        "snapshot-digest-mismatch", _break_a_snapshot, None, "SnapshotDigestMismatch"
    ),
    _DeploymentFaultCase(
        "two-promoted-snapshots", _promote_two_snapshots_of_one_build, None, "SnapshotError"
    ),
    _DeploymentFaultCase(
        "empty-dependency-record", _no_deployment_fault, {}, "EmptyDependencyRecord"
    ),
)
_FAULT_IDS = [case.name for case in _DEPLOYMENT_FAULTS]


@pytest.mark.parametrize("case", _DEPLOYMENT_FAULTS, ids=_FAULT_IDS)
async def test_a_broken_deployment_is_refused_before_anything_is_fetched_claimed_or_retained(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    case: _DeploymentFaultCase,
) -> None:
    """T666h: the request errors - it does not spend the source's budget to end `failed`. The
    exception names the fault class and carries nothing from the packaged files or the
    environment (the API shows it to the person who asked)."""
    case.install(monkeypatch, tmp_path)
    request = await _a_first_request(
        session_factory, game_id=500_666_800 + _FAULT_IDS.index(case.name) * 10
    )

    with (
        caplog.at_level(logging.ERROR, logger=run_module.logger.name),
        pytest.raises(extract.DeploymentFault) as raised,
    ):
        await request.ask(dependencies=case.dependencies, max_calls=0)

    await _assert_the_request_touched_nothing(request)
    assert raised.value.fault_class == case.fault_class
    assert case.fault_class in str(raised.value)
    assert str(tmp_path) not in str(raised.value)
    assert "effects.toml" not in str(raised.value)
    assert [record.levelno for record in caplog.records] == [logging.ERROR]
    assert case.fault_class in caplog.records[0].getMessage()


@pytest.mark.parametrize("case", _DEPLOYMENT_FAULTS, ids=_FAULT_IDS)
async def test_after_the_deployment_is_fixed_the_next_request_analyses_the_match_normally(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    case: _DeploymentFaultCase,
) -> None:
    """The contrast that makes the refusal safe: the match was never claimed, so it is not
    `failed` (a terminal state), and the request after the fix is a first analysis like any other.
    A load that failed is not cached, so a repaired snapshot is seen at once; a fault that loaded
    fine (two promoted snapshots) is repaired by a redeploy, modelled by the cache clear in its
    repair."""
    repair = case.install(monkeypatch, tmp_path)
    request = await _a_first_request(
        session_factory, game_id=500_666_850 + _FAULT_IDS.index(case.name) * 10
    )
    with pytest.raises(extract.DeploymentFault):
        await request.ask(dependencies=case.dependencies, max_calls=0)
    await _assert_the_request_touched_nothing(request)

    repair()
    extractor = await request.ask()

    row = await _get_analysis(session_factory, request.game_id)
    assert row is not None
    assert row.state == MatchAnalysisState.PUBLISHED
    assert row.error_class is None
    assert row.result_key is not None
    assert len(request.provider.calls) == 1
    assert len(extractor.calls) == 1


async def test_a_queued_row_that_already_exists_is_left_untouched_by_the_refusal(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """`claim_for_analysis` creates the row on a first ask, but another writer may have queued it
    first (its own docstring names the admission gate): the refusal does not claim it, so it stays
    `queued` with no attempt counted and the next request claims it."""
    repair = _break_a_snapshot(monkeypatch, tmp_path)
    request = await _a_first_request(session_factory, game_id=500_666_890)
    async with session_scope(session_factory) as session:
        session.add(
            MatchAnalysis(
                game_id=request.game_id,
                state=MatchAnalysisState.QUEUED,
                point_of_view_profile_id=request.profile_id,
                requested_by_user_id=request.requester,
                requested_at=datetime.now(UTC),
            )
        )

    with pytest.raises(extract.DeploymentFault):
        await request.ask(max_calls=0)

    row = await _get_analysis(session_factory, request.game_id)
    assert row is not None
    assert row.state == MatchAnalysisState.QUEUED
    assert row.attempts == 0
    assert row.claimed_at is None
    assert request.provider.calls == []

    repair()
    await request.ask()
    published = await _get_analysis(session_factory, request.game_id)
    assert published is not None
    assert published.state == MatchAnalysisState.PUBLISHED


async def test_a_healthy_deployment_still_analyses_on_the_first_request(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """The contrast to the refusals: the check costs a healthy request nothing it can see."""
    request = await _a_first_request(session_factory, game_id=500_666_900)

    await request.ask()

    row = await _get_analysis(session_factory, request.game_id)
    assert row is not None
    assert row.state == MatchAnalysisState.PUBLISHED
    assert len(request.provider.calls) == 1
    assert len(await _access_log_rows(session_factory)) == 1


async def test_the_deployment_check_is_cached_and_does_no_io_after_the_first_request(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Per-request cost of the check: the snapshot tree is read and digested once per process
    (`load_all_snapshots` is `functools.cache`d - the packaged tree is immutable, FR-025); every
    later request is a cache lookup per promoted build plus one truthiness test. Counted at the
    loader, with the check counted at its seam so a request that skipped it would not pass."""
    loads = 0
    real_load_snapshot = snapshot.load_snapshot

    def counting_load(directory: str) -> snapshot.Snapshot:
        nonlocal loads
        loads += 1
        return real_load_snapshot(directory)

    checks = 0
    real_check = extract.verify_deployment

    def counting_check(extractor: object) -> None:
        nonlocal checks
        checks += 1
        real_check(extractor)  # type: ignore[arg-type]

    monkeypatch.setattr(snapshot, "load_snapshot", counting_load)
    monkeypatch.setattr(extract, "verify_deployment", counting_check)
    monkeypatch.setattr(run_module, "verify_deployment", counting_check)

    first = await _a_first_request(session_factory, game_id=500_666_910)
    await first.ask()
    loads_after_first = loads
    assert loads_after_first == len(snapshot.list_snapshot_directories()) > 0
    assert checks == 1

    second = await _a_first_request(session_factory, game_id=500_666_920)
    await second.ask()

    assert checks == 2
    assert loads == loads_after_first, "a second request re-read or re-verified the snapshots"


# --- T666i: the recompute path's unpublish and retry holes -----------------------------------
#
# (a) A published row whose retained-recording row is gone was read as stale, recomputed and marked
# unavailable: a served analysis unpublished (FR-042). A recording that cannot be recomputed is not
# stale. (b) A retained object that failed its integrity check, or was missing, propagated with no
# backoff - a full read and a 500 per click - and the access-log row, written after the retrieve,
# was missing for a read that failed its checksum (FR-029). (c) `_publish` named the gap rows for a
# failure of the row update.

_HEALTHY = _Cause("healthy", None, _BuildNamingExtractor, _no_fault)


async def _delete_the_retained_row(
    session_factory: async_sessionmaker[AsyncSession], published: _Published
) -> RetainedRecording:
    retained = await _get_analysis_recording(session_factory, published)
    async with session_scope(session_factory) as session:
        await session.execute(delete(RetainedRecording).where(RetainedRecording.id == retained.id))
    return retained


def _assert_still_served_as_it_was(after: MatchAnalysis | None, published: _Published) -> None:
    assert after is not None
    assert _snapshot_of(after) == _snapshot_of(published.row)
    assert after.state == MatchAnalysisState.PUBLISHED
    assert after.result_key == published.key
    assert after.error_class is None
    assert published.store.objects[published.key] == published.body


async def test_a_published_row_whose_retained_row_is_gone_is_served_never_unpublished(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """(a) The row is stale by every other measure (a newer parser), but it cannot be recomputed:
    the prior analysis is served, still `published` at its key, nothing is read from the store and
    nothing is marked unavailable."""
    published = await _publish_once(session_factory, game_id=500_666_501)
    await _delete_the_retained_row(session_factory, published)
    published.store.get_calls.clear()
    puts_before = list(published.store.put_calls)

    extractor = await _ask_to_recompute(session_factory, published, _HEALTHY, max_calls=0)

    assert extractor.calls == []
    assert published.store.get_calls == []
    assert published.store.put_calls == puts_before
    assert await _access_log_rows(session_factory) == []
    _assert_still_served_as_it_was(
        await _get_analysis(session_factory, published.game_id), published
    )


async def test_a_retained_row_deleted_between_the_verdict_and_the_recompute_is_not_unavailable(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """(a), the race: `_recompute` itself must not unpublish when the row vanished after the
    staleness verdict was given."""
    published = await _publish_once(session_factory, game_id=500_666_502)
    await _delete_the_retained_row(session_factory, published)
    published.store.get_calls.clear()

    await run_module._recompute(
        session_factory,
        object_store=published.store,
        extractor=_BuildNamingExtractor(
            point_of_view_profile_id=published.profile_id,
            engine_version=_ENGINE_VERSION_2,
            max_calls=0,
        ),
        game_id=published.game_id,
        profile_id=published.profile_id,
        requested_by_user_id=published.requester,
        now=datetime.now(UTC),
        retry_after=timedelta(hours=1),
    )

    assert published.store.get_calls == []
    _assert_still_served_as_it_was(
        await _get_analysis(session_factory, published.game_id), published
    )


async def test_marking_unavailable_never_touches_a_published_row(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """(a), the sibling routes: `_mark_unavailable` is reached from a first analysis only, but it
    is the one function that can unpublish, so it refuses a published row itself."""
    published = await _publish_once(session_factory, game_id=500_666_503)

    await run_module._mark_unavailable(
        session_factory,
        game_id=published.game_id,
        point_of_view_profile_id=published.profile_id,
        requested_by_user_id=published.requester,
        now=datetime.now(UTC),
    )

    _assert_still_served_as_it_was(
        await _get_analysis(session_factory, published.game_id), published
    )


async def test_a_first_analysis_the_source_no_longer_serves_is_still_unavailable(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """The contrast to (a), unchanged: with no analysis to serve and nothing retained, 003's
    unavailable path applies."""
    request = await _a_first_request(session_factory, game_id=500_666_504)

    class _Gone:
        async def fetch_replay(self, game_id: int, profile_id: int) -> NotFound:
            return NotFound()

    await run_module.run_once(
        request.game_id,
        _BUDGET_SECONDS,
        request.requester,
        session_factory=session_factory,
        replay_provider=_Gone(),
        extractor=_BuildNamingExtractor(point_of_view_profile_id=request.profile_id, max_calls=0),
        object_store=request.store,
    )

    row = await _get_analysis(session_factory, request.game_id)
    assert row is not None
    assert row.state == MatchAnalysisState.UNAVAILABLE
    assert row.result_key is None


async def _recompute_reads_logged(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[ReplayAccessLog]:
    """The access-log rows a recompute wrote: the first analysis's own row is not one of them."""
    return [row for row in await _access_log_rows(session_factory) if row.purpose == "recompute"]


async def test_a_recompute_whose_retained_object_fails_its_checksum_keeps_the_prior_analysis(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """(b) The row stays published on its key with the retry window set, the read is in the access
    log although its verdict was a refusal (FR-029), and a second request inside the window reads
    nothing and logs nothing."""
    published = await _publish_once(session_factory, game_id=500_666_511)
    retained = await _get_analysis_recording(session_factory, published)
    published.store.objects[retained.object_key] = b"bit rot"
    published.store.get_calls.clear()

    with caplog.at_level(logging.WARNING, logger=run_module.logger.name):
        extractor = await _ask_to_recompute(session_factory, published, _HEALTHY, max_calls=0)

    assert extractor.calls == []
    after = await _get_analysis(session_factory, published.game_id)
    assert after is not None
    assert after.lease_expires_at is not None
    assert after.lease_expires_at > datetime.now(UTC) + timedelta(minutes=30)
    assert _snapshot_of(after) == _snapshot_of(published.row)
    assert after.result_key == published.key
    rows = await _recompute_reads_logged(session_factory)
    assert [row.retained_recording_id for row in rows] == [retained.id]
    assert any("RecordingIntegrityError" in record.getMessage() for record in caplog.records)

    published.store.get_calls.clear()
    again = await _ask_to_recompute(session_factory, published, _HEALTHY, max_calls=0)

    assert again.calls == []
    assert published.store.get_calls == []
    assert len(await _recompute_reads_logged(session_factory)) == 1
    unchanged = await _get_analysis(session_factory, published.game_id)
    assert unchanged is not None
    assert unchanged.lease_expires_at == after.lease_expires_at


async def test_a_recompute_whose_retained_object_is_missing_keeps_the_prior_analysis_with_backoff(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """(b) Decided: the store answered that the object is not there, so the recording cannot be
    recomputed - the same standing as an object that fails its checksum. The prior analysis is
    kept and the window bounds the store call to one per window. Nothing was read, so there is no
    read to log."""
    published = await _publish_once(session_factory, game_id=500_666_512)
    retained = await _get_analysis_recording(session_factory, published)
    del published.store.objects[retained.object_key]
    published.store.get_calls.clear()

    with caplog.at_level(logging.WARNING, logger=run_module.logger.name):
        extractor = await _ask_to_recompute(session_factory, published, _HEALTHY, max_calls=0)

    assert extractor.calls == []
    after = await _get_analysis(session_factory, published.game_id)
    assert after is not None
    assert after.lease_expires_at is not None
    assert after.lease_expires_at > datetime.now(UTC) + timedelta(minutes=30)
    assert _snapshot_of(after) == _snapshot_of(published.row)
    assert await _recompute_reads_logged(session_factory) == []
    assert any("ObjectNotFound" in record.getMessage() for record in caplog.records)

    published.store.get_calls.clear()
    await _ask_to_recompute(session_factory, published, _HEALTHY, max_calls=0)
    assert published.store.get_calls == []


async def test_a_store_outage_during_a_recompute_still_propagates_and_sets_no_window(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(b), the contrast: an outage says nothing about this recording, so it is not backed off. The
    request errors, the row is as it was with no window, and the next request after the outage
    recomputes."""
    published = await _publish_once(session_factory, game_id=500_666_513)

    async def outage(key: str) -> bytes:
        raise ConnectionError("the object store is unreachable")

    with monkeypatch.context() as patch:
        patch.setattr(published.store, "get", outage)
        with pytest.raises(ConnectionError):
            await _ask_to_recompute(session_factory, published, _HEALTHY, max_calls=0)

    after = await _get_analysis(session_factory, published.game_id)
    assert after is not None
    assert after.lease_expires_at is None
    assert _snapshot_of(after) == _snapshot_of(published.row)
    assert await _recompute_reads_logged(session_factory) == []

    extractor = await _ask_to_recompute(session_factory, published, _HEALTHY)
    await _assert_recomputed_to_a_new_key(session_factory, published, extractor)


async def test_a_first_analysis_never_reads_retained_bytes_so_a_bad_object_cannot_fail_it(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """(b), the first-analysis path: it parses the bytes it has just fetched and reads nothing back
    from the store, so there is no integrity verdict to precede - 003's behaviour is unchanged.
    The access-log row for the analysis is written whatever state the retained object is in."""
    request = await _a_first_request(session_factory, game_id=500_666_514)
    async with session_factory() as session:
        retained = await retain_recording(
            session,
            request.store,
            game_id=request.game_id,
            profile_id=request.profile_id,
            zip_bytes=b"raw bytes",
        )
    request.store.objects[retained.object_key] = b"bit rot"
    request.store.get_calls.clear()

    await request.ask()

    row = await _get_analysis(session_factory, request.game_id)
    assert row is not None
    assert row.state == MatchAnalysisState.PUBLISHED
    assert request.store.get_calls == []
    logged = await _access_log_rows(session_factory)
    assert [entry.purpose for entry in logged] == ["analysis"]
    assert logged[0].retained_recording_id == retained.id


# --- T666i (c): a publish failure names the step that failed ---------------------------------


async def _first_analysis_failing_publish(
    session_factory: async_sessionmaker[AsyncSession], *, game_id: int
) -> MatchAnalysis:
    request = await _a_first_request(session_factory, game_id=game_id)
    await request.ask()
    row = await _get_analysis(session_factory, game_id)
    assert row is not None
    assert row.state == MatchAnalysisState.FAILED
    assert request.store.objects.keys().isdisjoint(_analysis_keys(request.store))
    return row


async def test_a_refused_row_update_is_reported_as_the_row_update_not_the_gap_rows(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The `match_analyses` UPDATE is flushed before the gap insert, so a value the row refuses
    surfaced inside the gap step and was reported as the gap rows."""
    monkeypatch.setattr(
        run_module, "document_recording_build", lambda document: _GAP_BUILD_OUT_OF_RANGE
    )

    row = await _first_analysis_failing_publish(session_factory, game_id=500_666_521)

    assert row.error_message is not None
    assert "row" in row.error_message
    assert "gap" not in row.error_message
    assert await _gap_row_count(session_factory) == 0


async def test_a_refused_gap_insert_is_still_reported_as_the_gap_rows(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The contrast: the row update goes through and the gap insert is what the table refuses."""
    _a_gap_insert_fault(monkeypatch, 0)

    row = await _first_analysis_failing_publish(session_factory, game_id=500_666_522)

    assert row.error_message is not None
    assert "gap" in row.error_message
    assert "row update" not in row.error_message
    assert await _gap_row_count(session_factory) == 0
