"""Tests for the reproducibility of a published analysis (T660, written before T657-T659):
SC-004, SC-005, FR-040 to FR-043.

Written ``xfail(strict=True)`` before the implementing tasks, with every not-yet-existing symbol
imported inside the test body: a module-scope import of a missing symbol would have been a
collection error that reddened the whole workspace, and a skip would have hidden the day the task
landed. ``strict=True`` forced whoever landed T655/T657/T658/T659 to delete the marker from each
test that turned green; none remain.

**Interface assumed** (T655, T657, T657a, T658, T659 must match it, or amend this file). Everything
below that the tasks and ``contracts/analysis-document.md`` already fix is not repeated here.

- ``aoe2stats_analyzer.extract.build_document(extractor, zip_bytes, *, game_id, object_key,
  zip_sha256, extracted_at) -> dict`` is the pure, synchronous builder of the version 2 document
  (T655): it parses the recording, resolves the knowledge snapshot for the recording's build,
  fills ``identity``, ``envelope`` and the legacy top-level ``extracted_at``, and does no I/O beyond
  that. ``extractor`` is an ``Aoe2RecExtractor`` (``events``, ``extract``, ``engine_name``,
  ``engine_version``, ``engine_dependencies``).
- ``aoe2stats_analyzer.extract.canonical_bytes(document) -> bytes`` (T659) is the one serialisation
  ``run_once`` writes to the object store: sorted keys where order carries no meaning, stream order
  kept, one fixed float format, UTF-8.
- ``aoe2stats_analyzer.extract.compared_body(document) -> bytes`` (T659) is ``canonical_bytes`` of
  the document **minus the wall-clock set**: the top-level ``envelope`` and the legacy top-level
  ``extracted_at``, and nothing else. It takes the document as a mapping.
- ``aoe2stats_analyzer.reproduce.reproduce(identity, *, object_store, extractor) -> bytes`` (T658)
  is ``async``: it reads ``identity.recording["object_key"]`` from the object store, verifies
  ``identity.recording["sha256"]``, resolves ``identity.knowledge`` among **every** packaged
  snapshot (``snapshot.load_all_snapshots``, not only the promoted ones: a superseded snapshot is
  demoted, never deleted, and must stay resolvable - SC-005), refuses when ``extractor``'s name,
  version or dependencies differ from the identity, and returns ``canonical_bytes`` of the
  document. It makes no network call. ``identity`` is ``aoe2stats_core.truth.identity.
  AnalysisIdentity`` (T653, keyword arguments as in ``packages/core/tests/test_identity.py``).
- The published document's ``identity`` block is as ``contracts/analysis-document.md`` shows it:
  ``digest``, ``recording``, ``parser`` (``name``, ``version``), ``parser_dependencies``,
  ``knowledge`` (``source``, ``source_version``, ``describes_build``, ``digest``),
  ``reconstruction_engine`` and ``analytics``.
- The published object's key is ``analyses/{game_id}`` followed by the identity digest's hex
  (T657): ``MatchAnalysis.result_key`` names the current one, and the new nullable
  ``MatchAnalysis.identity_digest`` column (T663) holds the digest ``run_once`` compares with the
  current one (T657a).
- A knowledge **refresh** of a build is modelled the only way ``snapshot_for`` allows (it raises on
  two promoted snapshots describing one build): the second snapshot is promoted and the first is
  demoted (``promoted = false`` in its ``snapshot.toml``; ``rules.json`` and ``effects.toml``,
  which the digest covers, are untouched). Whether production supersedes a snapshot this way is
  T657a/T658's decision; if it decides differently, this helper is what changes.

**One ambiguity, resolved here.** ``quickstart.md`` says ``reproduce`` "returns the first
document's bytes", but ``contracts/analysis-document.md`` puts the wall-clock set outside what is
compared: a reproduction run later cannot carry the first run's clock without storing it. These
tests compare **outside the wall-clock set**, which is what SC-004's own wording requires.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import socket
import subprocess
import sys
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from packaging.utils import canonicalize_name
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.snapshot_refresh import isolate_snapshot_root, promote_a_refreshed_snapshot

from aoe2stats_providers.base import NotFound, ReplayBlob
from aoe2stats_replay_engine.aoe2rec import Aoe2RecExtractor
from aoe2stats_storage.models import AoeProfile, Match, MatchAnalysis, MatchPlayer, User
from aoe2stats_storage.objects import ObjectNotFound, read_analysis
from aoe2stats_storage.repositories.base import session_scope

# `session_factory` and `clean_database` come from `apps/analyzer/tests/conftest.py`.

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURE_ZIP = _REPO_ROOT / "tests" / "fixtures" / "replays" / "AgeIIDE_Replay_500546441.zip"
_GAME_ID = 500_546_441
_POINT_OF_VIEW_PROFILE_ID = 196_240  # the fixture's own point of view (fixtures README)
_OTHER_PROFILE_ID = 196_241
_MAX_RAW_BYTES = (
    25_165_824  # `.env.example`'s ANALYSIS_MAX_RAW_BYTES; the fixture inflates to ~7 MB
)
_BUDGET_SECONDS = 300
_RETAINED_KEY = f"retained-recordings/{_GAME_ID}/{_POINT_OF_VIEW_PROFILE_ID}.zip"

#: The wall-clock set (T659): everything else in a document is a pure function of the identity.
_WALL_CLOCK_FIELDS = frozenset({"envelope", "extracted_at"})

# --- The fresh-process half of SC-004 ---------------------------------------------------------

#: Run by `python -c`: a process that shares nothing with the test runner - not the dictionary
#: ordering (a different `PYTHONHASHSEED`), not the clock, not any module-level cache.
_FRESH_PROCESS_SCRIPT = """
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from aoe2stats_analyzer.extract import build_document, canonical_bytes, compared_body
from aoe2stats_replay_engine.aoe2rec import Aoe2RecExtractor

zip_path, game_id, object_key, zip_sha256, max_raw_bytes = sys.argv[1:6]
extractor = Aoe2RecExtractor(max_raw_bytes=int(max_raw_bytes))
document = build_document(
    extractor,
    Path(zip_path).read_bytes(),
    game_id=int(game_id),
    object_key=object_key,
    zip_sha256=zip_sha256,
    extracted_at=datetime.now(UTC),
)
sys.stdout.write(
    json.dumps(
        {
            "document": canonical_bytes(document).decode("utf-8"),
            "body": compared_body(document).decode("utf-8"),
        }
    )
)
"""


@dataclass(frozen=True, slots=True)
class _Run:
    """One analysis of the fixture: the full serialised document and its compared body."""

    document: bytes
    body: bytes

    def parsed(self) -> dict[str, Any]:
        loaded: dict[str, Any] = json.loads(self.document)
        return loaded


def _zip_sha256() -> str:
    return hashlib.sha256(_FIXTURE_ZIP.read_bytes()).hexdigest()


def _analyse_in_this_process(extracted_at: datetime) -> _Run:
    from aoe2stats_analyzer.extract import build_document, canonical_bytes, compared_body

    extractor = Aoe2RecExtractor(max_raw_bytes=_MAX_RAW_BYTES)
    document = build_document(
        extractor,
        _FIXTURE_ZIP.read_bytes(),
        game_id=_GAME_ID,
        object_key=_RETAINED_KEY,
        zip_sha256=_zip_sha256(),
        extracted_at=extracted_at,
    )
    return _Run(document=canonical_bytes(document), body=compared_body(document))


def _analyse_in_a_fresh_process() -> _Run:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            _FRESH_PROCESS_SCRIPT,
            str(_FIXTURE_ZIP),
            str(_GAME_ID),
            _RETAINED_KEY,
            _zip_sha256(),
            str(_MAX_RAW_BYTES),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        # A hash seed the parent almost certainly does not use: a pass cannot be an accident of
        # both processes happening to order a dict or a set the same way.
        env={**os.environ, "PYTHONHASHSEED": "1234"},
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    return _Run(document=payload["document"].encode("utf-8"), body=payload["body"].encode("utf-8"))


# The first run is deliberately stamped long ago: the fresh process stamps "now", so the two runs'
# wall-clock fields differ by construction and the comparison below is not vacuous.
_FIRST_RUN_CLOCK = datetime(2020, 1, 1, tzinfo=UTC)


def test_a_second_run_in_a_fresh_process_is_byte_identical_outside_the_wall_clock_set() -> None:
    """SC-004: a whole-document comparison fails on every run and proves nothing; the compared
    body is everything outside the wall-clock set, and it must match to the byte."""
    first = _analyse_in_this_process(_FIRST_RUN_CLOCK)
    second = _analyse_in_a_fresh_process()

    assert first.body, "the compared body is empty: an empty equality proves nothing"
    assert first.body == second.body


def test_the_compared_body_is_not_trivially_small_and_carries_a_populated_identity() -> None:
    """The equality above must be over something: a body that is just `{}` is byte-identical to
    itself in every process. The identity is part of the compared body (FR-040, FR-041) and its
    dependency record is non-empty (FR-044)."""
    run = _analyse_in_this_process(_FIRST_RUN_CLOCK)
    body = json.loads(run.body)

    assert body["schema_version"] == 2
    assert body["identity"]["digest"]
    assert body["identity"]["parser_dependencies"]
    assert body["participants"]
    assert body["game_id"] == _GAME_ID


def test_the_excluded_wall_clock_fields_really_differ_between_the_two_runs() -> None:
    """The contrast case: the exclusion is exercised, not vacuous. Both wall-clock paths carry a
    different time in the two runs, so the full documents differ while the compared bodies do not
    - a whole-document comparison would have failed this very scenario."""
    first = _analyse_in_this_process(_FIRST_RUN_CLOCK)
    second = _analyse_in_a_fresh_process()

    first_document, second_document = first.parsed(), second.parsed()
    assert first_document["envelope"]["extracted_at"] != second_document["envelope"]["extracted_at"]
    assert first_document["extracted_at"] != second_document["extracted_at"]
    assert first.document != second.document
    assert first.body == second.body


def test_the_compared_body_excludes_exactly_the_wall_clock_set() -> None:
    """The exclusion is neither too narrow (a clock leaks into the body and every run differs) nor
    too wide (a real field is dropped and two different analyses compare equal)."""
    run = _analyse_in_this_process(_FIRST_RUN_CLOCK)

    document, body = run.parsed(), json.loads(run.body)
    assert document.keys() >= _WALL_CLOCK_FIELDS
    assert set(body) == set(document) - _WALL_CLOCK_FIELDS
    assert {key: document[key] for key in body} == body


# --- SC-005 and the new-key contrast: publish, record, change something, recompute ------------


class _FakeReplayProvider:
    """Serves the fixture once. Raises past `max_calls`: a recompute reaches the source zero times
    (FR-043), and a canary fails louder than a counter nobody reads."""

    def __init__(self, blob: ReplayBlob, *, max_calls: int) -> None:
        self._blob = blob
        self._max_calls = max_calls
        self.calls = 0

    async def fetch_replay(self, game_id: int, profile_id: int) -> ReplayBlob | NotFound:
        if self.calls >= self._max_calls:
            raise AssertionError(f"fetch_replay({game_id}, {profile_id}) called past its bound")
        self.calls += 1
        return self._blob


class _RefusingReplayProvider:
    async def fetch_replay(self, game_id: int, profile_id: int) -> ReplayBlob | NotFound:
        raise AssertionError(f"fetch_replay({game_id}, {profile_id}) must never be reached")


class _FakeObjectStore:
    """The async `put`/`get` subset of `aoe2stats_storage.objects.ObjectStore`, remembering every
    write so "a key, once written, is never written again" (contract) is checkable."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.put_calls: list[str] = []

    async def put(self, key: str, body: bytes, *, content_type: str = "application/zip") -> None:
        self.objects[key] = body
        self.put_calls.append(key)

    async def put_if_absent(
        self, key: str, body: bytes, *, content_type: str = "application/zip"
    ) -> bool:
        if key in self.objects:
            return False
        self.objects[key] = body
        self.put_calls.append(key)
        return True

    async def get(self, key: str) -> bytes:
        if key not in self.objects:
            raise ObjectNotFound(key)
        return self.objects[key]

    def analysis_keys(self) -> list[str]:
        return sorted(key for key in self.objects if key.startswith("analyses/"))


class _RelabelledExtractor:
    """The real extractor under another parser version: the one component of the identity a test
    can change without installing a second wheel. The timeline carries the same version the
    extractor reports, so whichever of the two the implementation reads, they agree."""

    def __init__(self, inner: Aoe2RecExtractor, *, engine_version: str) -> None:
        self._inner = inner
        self.engine_name = inner.engine_name
        self.engine_version = engine_version
        engine_entry = canonicalize_name(inner.engine_name)
        self.engine_dependencies = {**inner.engine_dependencies, engine_entry: engine_version}

    def extract(self, zip_bytes: bytes) -> Any:
        timeline = self._inner.extract(zip_bytes)
        return dataclasses.replace(timeline, engine_version=self.engine_version)

    def events(self, zip_bytes: bytes) -> Any:
        return self._inner.events(zip_bytes)


async def _seed_match_and_user(
    session_factory: async_sessionmaker[AsyncSession],
) -> uuid.UUID:
    user_id = uuid.uuid4()
    async with session_scope(session_factory) as session:
        session.add(User(id=user_id))
        for profile_id in (_POINT_OF_VIEW_PROFILE_ID, _OTHER_PROFILE_ID):
            session.add(AoeProfile(profile_id=profile_id, alias=f"Player {profile_id}"))
        session.add(
            Match(
                game_id=_GAME_ID,
                leaderboard_id=3,
                completed_at=datetime.now(UTC) - timedelta(days=1),
                duration_seconds=1800,
                source="relic",
                raw_payload={},
            )
        )
        for index, profile_id in enumerate((_POINT_OF_VIEW_PROFILE_ID, _OTHER_PROFILE_ID)):
            session.add(
                MatchPlayer(
                    game_id=_GAME_ID,
                    profile_id=profile_id,
                    team_id=index,
                    civ_id=1,
                    color_id=index,
                    result="win" if index == 0 else "loss",
                )
            )
    return user_id


async def _analysis_row(session_factory: async_sessionmaker[AsyncSession]) -> MatchAnalysis:
    async with session_scope(session_factory) as session:
        row = await session.get(MatchAnalysis, _GAME_ID)
        assert row is not None
        session.expunge(row)
        return row


async def _run_once(
    session_factory: async_sessionmaker[AsyncSession],
    store: _FakeObjectStore,
    extractor: Any,
    user_id: uuid.UUID,
    provider: _FakeReplayProvider | _RefusingReplayProvider,
) -> None:
    from aoe2stats_analyzer.run import run_once

    await run_once(
        _GAME_ID,
        _BUDGET_SECONDS,
        user_id,
        session_factory=session_factory,
        replay_provider=provider,
        extractor=extractor,
        object_store=store,
    )


@dataclass(frozen=True, slots=True)
class _Published:
    """What one `run_once` left behind: the object, where the row points, and what it recorded."""

    key: str
    raw: bytes
    document: dict[str, Any]
    row_identity_digest: str | None

    @property
    def identity(self) -> Mapping[str, Any]:
        block: Mapping[str, Any] = self.document["identity"]
        return block


async def _published(
    session_factory: async_sessionmaker[AsyncSession], store: _FakeObjectStore
) -> _Published:
    row = await _analysis_row(session_factory)
    assert row.result_key is not None
    raw = store.objects[row.result_key]
    return _Published(
        key=row.result_key,
        raw=raw,
        document=json.loads(raw),
        row_identity_digest=row.identity_digest,
    )


@dataclass(frozen=True, slots=True)
class _Flow:
    store: _FakeObjectStore
    extractor: Aoe2RecExtractor
    first: _Published
    second: _Published
    refreshed_snapshot_digest: str


async def _publish_promote_recompute(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> _Flow:
    """SC-005's scenario, in the order the contract words it: publish, record the identity,
    promote a second snapshot, recompute. The recompute reaches the source zero times."""
    root = isolate_snapshot_root(monkeypatch, tmp_path)
    user_id = await _seed_match_and_user(session_factory)
    store = _FakeObjectStore()
    extractor = Aoe2RecExtractor(max_raw_bytes=_MAX_RAW_BYTES)
    blob = ReplayBlob(
        content=_FIXTURE_ZIP.read_bytes(),
        filename=_FIXTURE_ZIP.name,
        content_type="application/zip",
    )

    await _run_once(
        session_factory, store, extractor, user_id, _FakeReplayProvider(blob, max_calls=1)
    )
    first = await _published(session_factory, store)

    refreshed_digest = promote_a_refreshed_snapshot(root)

    await _run_once(session_factory, store, extractor, user_id, _RefusingReplayProvider())
    second = await _published(session_factory, store)
    return _Flow(
        store=store,
        extractor=extractor,
        first=first,
        second=second,
        refreshed_snapshot_digest=refreshed_digest,
    )


def _recorded_identity(published: _Published) -> Any:
    """Rebuild the identity a document recorded, and prove its digest recomputes (FR-040)."""
    from aoe2stats_core.truth.identity import AnalysisIdentity

    block = published.identity
    identity = AnalysisIdentity(
        recording=block["recording"],
        parser_name=block["parser"]["name"],
        parser_version=block["parser"]["version"],
        parser_dependencies=block["parser_dependencies"],
        knowledge=block["knowledge"],
        reconstruction_engine=block["reconstruction_engine"],
        analytics=block["analytics"],
    )
    assert identity.digest == block["digest"]
    return identity


def _body_of(raw: bytes) -> bytes:
    from aoe2stats_analyzer.extract import compared_body

    return compared_body(json.loads(raw))


def _hex(digest: str) -> str:
    return digest.rsplit(":", 1)[-1]


def _forbid_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-043: reproduction reaches no external source. Any attempt to open a connection raises,
    which turns a hidden fetch into a failure instead of a slow pass."""

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("reproduce() attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)


async def test_the_first_identity_reproduces_exactly_after_a_second_snapshot_is_promoted(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """SC-005: publish, record the identity, promote a second snapshot, recompute, then fetch by
    the first identity and confirm it reproduces exactly (outside the wall-clock set)."""
    from aoe2stats_analyzer.reproduce import reproduce

    flow = await _publish_promote_recompute(session_factory, monkeypatch, tmp_path)
    first_identity = _recorded_identity(flow.first)

    _forbid_network(monkeypatch)
    reproduced = await reproduce(first_identity, object_store=flow.store, extractor=flow.extractor)

    assert _body_of(reproduced) == _body_of(flow.first.raw)
    assert _body_of(reproduced) != _body_of(flow.second.raw)


async def test_the_newer_snapshot_is_not_substituted_when_reproducing_an_older_identity(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The promotion really took effect (the recompute names the newer snapshot), and reproducing
    the first identity still names the first one: resolving "the latest snapshot for the build"
    instead of "the snapshot the identity names" is the silent rewrite FR-042 forbids."""
    from aoe2stats_analyzer.reproduce import reproduce

    flow = await _publish_promote_recompute(session_factory, monkeypatch, tmp_path)
    first_knowledge = flow.first.identity["knowledge"]
    second_knowledge = flow.second.identity["knowledge"]
    assert first_knowledge["digest"] != second_knowledge["digest"]
    assert second_knowledge["digest"] == flow.refreshed_snapshot_digest

    reproduced = json.loads(
        await reproduce(
            _recorded_identity(flow.first), object_store=flow.store, extractor=flow.extractor
        )
    )

    assert reproduced["identity"]["knowledge"] == first_knowledge
    assert reproduced["identity"]["digest"] == flow.first.identity["digest"]
    assert reproduced["identity"]["knowledge"] != second_knowledge


async def test_the_previous_version_remains_available_after_a_recompute_under_a_new_snapshot(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """FR-042: a new knowledge version produces a **new** analysis and rewrites nothing. Two
    objects exist, the row names the newer, and the first object is still there, byte for byte,
    written exactly once."""
    flow = await _publish_promote_recompute(session_factory, monkeypatch, tmp_path)

    assert flow.first.key != flow.second.key
    assert flow.store.analysis_keys() == sorted([flow.first.key, flow.second.key])
    assert flow.store.objects[flow.first.key] == flow.first.raw
    assert flow.store.put_calls.count(flow.first.key) == 1
    assert flow.store.put_calls.count(flow.second.key) == 1
    row = await _analysis_row(session_factory)
    assert row.result_key == flow.second.key
    assert row.identity_digest == flow.second.identity["digest"]
    assert flow.first.row_identity_digest == flow.first.identity["digest"]


async def test_the_older_analysis_is_read_by_the_identity_that_named_it(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """SC-005 through the storage package's own read-by-identity function (T666e): the row names
    only the newer document, yet each identity resolves its own object, byte for byte, and an
    identity never published is the store's not-found - not another document."""
    flow = await _publish_promote_recompute(session_factory, monkeypatch, tmp_path)

    older = await read_analysis(
        flow.store, game_id=_GAME_ID, identity_digest=flow.first.identity["digest"]
    )
    newer = await read_analysis(
        flow.store, game_id=_GAME_ID, identity_digest=flow.second.identity["digest"]
    )

    assert older == flow.first.raw
    assert newer == flow.second.raw
    assert older != newer
    with pytest.raises(ObjectNotFound):
        await read_analysis(flow.store, game_id=_GAME_ID, identity_digest="sha256:never")


async def test_each_object_key_carries_its_own_identity_digest(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The contract: the current per-match prefix, then the identity digest, so two identities can
    never share a key (T657)."""
    flow = await _publish_promote_recompute(session_factory, monkeypatch, tmp_path)

    for published in (flow.first, flow.second):
        assert published.key.startswith(f"analyses/{_GAME_ID}")
        assert _hex(published.identity["digest"]) in published.key
    assert flow.first.identity["digest"] != flow.second.identity["digest"]


async def test_a_changed_parser_version_writes_a_new_key_and_leaves_the_old_one_untouched(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The contrast to the knowledge case, through a different identity component: today a parser
    version change already triggers a recompute, and it overwrites the one per-match key - this is
    the case that proves the overwrite is gone."""
    isolate_snapshot_root(monkeypatch, tmp_path)
    user_id = await _seed_match_and_user(session_factory)
    store = _FakeObjectStore()
    real_extractor = Aoe2RecExtractor(max_raw_bytes=_MAX_RAW_BYTES)
    blob = ReplayBlob(
        content=_FIXTURE_ZIP.read_bytes(),
        filename=_FIXTURE_ZIP.name,
        content_type="application/zip",
    )

    await _run_once(
        session_factory, store, real_extractor, user_id, _FakeReplayProvider(blob, max_calls=1)
    )
    first = await _published(session_factory, store)

    await _run_once(
        session_factory,
        store,
        _RelabelledExtractor(real_extractor, engine_version="9.9.9"),
        user_id,
        _RefusingReplayProvider(),
    )
    second = await _published(session_factory, store)

    assert second.identity["parser"]["version"] == "9.9.9"
    assert second.identity["digest"] != first.identity["digest"]
    assert second.key != first.key
    assert store.objects[first.key] == first.raw
    assert store.put_calls.count(first.key) == 1
    assert store.analysis_keys() == sorted([first.key, second.key])
