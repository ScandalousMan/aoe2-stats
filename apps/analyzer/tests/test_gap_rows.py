"""T662: the gap rows `run_once` writes when it publishes (FR-027, FR-035, FR-037, FR-039, FR-042).

What is pinned, each against the committed recordings or a real extractor with one thing changed:

- the published `knowledge_gaps` list and the `analysis_knowledge_gaps` rows are the same set of
  `(entity, field, civilisation, cause, severity)`, and the same size (nothing silently collapsed);
- a second publish under the same identity adds **zero** rows, and a different identity (a knowledge
  snapshot refresh) adds rows of its own and leaves the first identity's untouched (FR-042);
- the rows ride the transaction that publishes: a publish that fails leaves none, and a document the
  validator refuses writes none (T656's path);
- a stream that named no build is recorded under `NO_BUILD` (-1), and a stream that named a build no
  snapshot describes is recorded under that real build; exactly one blocking row either way
  (FR-027).

`run.py` reaches none of this through `aoe2stats_core.truth` or `aoe2stats_knowledge`
(`tests/architecture/test_feature_006_boundaries.py`); the document is the only thing it reads.
"""

from __future__ import annotations

import dataclasses
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# The SC-005 scenario's own helpers: publish, promote a second snapshot, recompute.
from test_reproducibility import (  # type: ignore[import-not-found]
    _clear_snapshot_resolution_caches,
    _publish_promote_recompute,
)

from aoe2stats_analyzer import run
from aoe2stats_analyzer.extract import DocumentInvalid
from aoe2stats_core.replay.events import CanonicalEvent, EventKind, MatchStartedPayload
from aoe2stats_providers.base import NotFound, ReplayBlob
from aoe2stats_replay_engine.aoe2rec import Aoe2RecExtractor
from aoe2stats_storage.models import (
    AnalysisKnowledgeGap,
    AoeProfile,
    Match,
    MatchAnalysis,
    MatchAnalysisState,
    MatchPlayer,
    User,
)
from aoe2stats_storage.repositories.base import session_scope
from aoe2stats_storage.repositories.knowledge_gaps import NO_BUILD, KnowledgeGapsRepository

# `session_factory` and `clean_database` come from `apps/analyzer/tests/conftest.py`.

_REPO_ROOT = Path(__file__).resolve().parents[3]
_RECORDINGS = {
    500_546_441: (196_240, 288_714),
    504_695_319: (1_813_797, 2_582_827, 1_807_091, 2_581_732),
}
_MAX_RAW_BYTES = 25_165_824
_BUDGET_SECONDS = 300
_UNRESOLVABLE_BUILD = 1

__all__ = ["_clear_snapshot_resolution_caches"]


def _zip_of(game_id: int) -> bytes:
    return (
        _REPO_ROOT / "tests" / "fixtures" / "replays" / f"AgeIIDE_Replay_{game_id}.zip"
    ).read_bytes()


class _Provider:
    def __init__(self, content: bytes) -> None:
        self._blob = ReplayBlob(content=content, filename="r.zip", content_type="application/zip")

    async def fetch_replay(self, game_id: int, profile_id: int) -> ReplayBlob | NotFound:
        return self._blob


class _Store:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put(self, key: str, body: bytes, *, content_type: str = "application/zip") -> None:
        self.objects[key] = body

    async def get(self, key: str) -> bytes:
        return self.objects[key]


class _Extractor:
    """The real extractor, optionally naming another build, or none at all (an empty stream)."""

    def __init__(self, *, build: int | None = None, drop_stream: bool = False) -> None:
        self._inner = Aoe2RecExtractor(max_raw_bytes=_MAX_RAW_BYTES)
        self._build = build
        self._drop_stream = drop_stream
        self.engine_name = self._inner.engine_name
        self.engine_version = self._inner.engine_version
        self.engine_dependencies = self._inner.engine_dependencies

    def extract(self, zip_bytes: bytes) -> Any:
        return self._inner.extract(zip_bytes)

    def events(self, zip_bytes: bytes) -> Iterator[CanonicalEvent]:
        if self._drop_stream:
            return
        for event in self._inner.events(zip_bytes):
            if self._build is not None and event.kind is EventKind.MATCH_STARTED:
                assert isinstance(event.payload, MatchStartedPayload)
                event = dataclasses.replace(
                    event, payload=dataclasses.replace(event.payload, build=self._build)
                )
            yield event


async def _seed(session_factory: async_sessionmaker[AsyncSession], game_id: int) -> uuid.UUID:
    user_id = uuid.uuid4()
    profiles = _RECORDINGS[game_id]
    async with session_scope(session_factory) as session:
        session.add(User(id=user_id))
        for profile_id in profiles:
            session.add(AoeProfile(profile_id=profile_id, alias=f"Player {profile_id}"))
        session.add(
            Match(
                game_id=game_id,
                leaderboard_id=3,
                completed_at=datetime.now(UTC) - timedelta(days=1),
                duration_seconds=1800,
                source="relic",
                raw_payload={},
            )
        )
        for index, profile_id in enumerate(profiles):
            session.add(
                MatchPlayer(
                    game_id=game_id,
                    profile_id=profile_id,
                    team_id=index % 2,
                    civ_id=1,
                    color_id=index,
                    result="win" if index % 2 == 0 else "loss",
                )
            )
    return user_id


async def _run_once(
    session_factory: async_sessionmaker[AsyncSession],
    game_id: int,
    user_id: uuid.UUID,
    store: _Store,
    extractor: Any,
) -> None:
    await run.run_once(
        game_id,
        _BUDGET_SECONDS,
        user_id,
        session_factory=session_factory,
        replay_provider=_Provider(_zip_of(game_id)),
        extractor=extractor,
        object_store=store,
    )


async def _rows(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[AnalysisKnowledgeGap]:
    async with session_factory() as session:
        result = await session.execute(
            select(AnalysisKnowledgeGap).order_by(AnalysisKnowledgeGap.id)
        )
        return list(result.scalars())


async def _analysis(
    session_factory: async_sessionmaker[AsyncSession], game_id: int
) -> MatchAnalysis:
    async with session_factory() as session:
        row = await session.get(MatchAnalysis, game_id)
        assert row is not None
        return row


def _published_document(store: _Store, analysis: MatchAnalysis) -> dict[str, Any]:
    import json

    assert analysis.result_key is not None
    document: dict[str, Any] = json.loads(store.objects[analysis.result_key])
    return document


def _from_document(document: dict[str, Any]) -> set[tuple[Any, ...]]:
    """`(entity kind, entity id, field, civilisation, cause, severity, build)` per published gap.
    A whole-build gap names no entity or field: the row carries `build`/`*`/`*` there."""
    return {
        (
            (gap["entity"] or {"kind": "build", "id": "*"})["kind"],
            (gap["entity"] or {"kind": "build", "id": "*"})["id"],
            gap["field"] or "*",
            gap["civilisation"],
            gap["cause"],
            gap["severity"],
            gap["build"],
        )
        for gap in document["knowledge_gaps"]
    }


def _from_rows(rows: list[AnalysisKnowledgeGap]) -> set[tuple[Any, ...]]:
    return {
        (
            row.entity_kind,
            row.entity_id,
            row.field,
            row.civilisation_id,
            row.cause.value,
            row.severity.value,
            row.build,
        )
        for row in rows
    }


# --- The rows and the published list are one set -------------------------------------------------


@pytest.mark.parametrize("game_id", sorted(_RECORDINGS))
async def test_the_rows_are_the_published_gap_list_on_each_committed_recording(
    game_id: int, session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    user_id = await _seed(session_factory, game_id)
    store = _Store()

    await _run_once(session_factory, game_id, user_id, store, _Extractor())

    analysis = await _analysis(session_factory, game_id)
    assert analysis.state is MatchAnalysisState.PUBLISHED
    document = _published_document(store, analysis)
    rows = await _rows(session_factory)
    assert document["knowledge_gaps"], "the committed recording is expected to carry gaps"
    assert len(rows) == len(document["knowledge_gaps"])
    assert _from_rows(rows) == _from_document(document)
    assert {row.identity_digest for row in rows} == {document["identity"]["digest"]}
    assert {row.game_id for row in rows} == {game_id}


# --- FR-027: no snapshot for the build -----------------------------------------------------------


async def test_a_build_no_snapshot_describes_records_one_blocking_row_under_that_real_build(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    game_id = 500_546_441
    user_id = await _seed(session_factory, game_id)
    store = _Store()

    await _run_once(session_factory, game_id, user_id, store, _Extractor(build=_UNRESOLVABLE_BUILD))

    document = _published_document(store, await _analysis(session_factory, game_id))
    assert document["identity"]["knowledge"] == {
        "absent": "no-snapshot-for-build",
        "build": _UNRESOLVABLE_BUILD,
    }
    rows = await _rows(session_factory)
    assert len(rows) == 1
    (row,) = rows
    assert row.build == _UNRESOLVABLE_BUILD  # the stream named one: never the sentinel
    assert row.cause.value == "no-snapshot-for-build"
    assert row.severity.value == "blocking"
    assert (row.entity_kind, row.entity_id, row.field) == ("build", "*", "*")
    assert row.civilisation_id is None
    assert _from_rows(rows) == _from_document(document)


async def test_a_stream_that_named_no_build_records_one_blocking_row_under_the_sentinel(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    game_id = 500_546_441
    user_id = await _seed(session_factory, game_id)
    store = _Store()

    await _run_once(session_factory, game_id, user_id, store, _Extractor(drop_stream=True))

    document = _published_document(store, await _analysis(session_factory, game_id))
    assert document["identity"]["knowledge"] == {"absent": "no-snapshot-for-build", "build": -1}
    rows = await _rows(session_factory)
    assert len(rows) == 1
    assert rows[0].build == NO_BUILD == -1
    assert rows[0].cause.value == "no-snapshot-for-build"
    assert rows[0].severity.value == "blocking"
    assert _from_rows(rows) == _from_document(document)


# --- Insert-or-ignore, and the contrast: a different identity ------------------------------------


async def test_a_second_publish_under_the_same_identity_adds_zero_rows(
    session_factory: async_sessionmaker[AsyncSession], clean_database: None
) -> None:
    """The analysis is re-run for the same identity: the row is forced stale (no stored digest, the
    shape of a row published before this feature), so `run_once` takes its recompute path and
    publishes again. The identity is unchanged, so the gaps are unchanged, and nothing is added."""
    game_id = 500_546_441
    user_id = await _seed(session_factory, game_id)
    store = _Store()
    extractor = _Extractor()
    await _run_once(session_factory, game_id, user_id, store, extractor)
    first_digest = (await _analysis(session_factory, game_id)).identity_digest
    before = await _rows(session_factory)
    assert before

    async with session_scope(session_factory) as session:
        await session.execute(
            update(MatchAnalysis)
            .where(MatchAnalysis.game_id == game_id)
            .values(identity_digest=None)
        )
    await _run_once(session_factory, game_id, user_id, store, extractor)

    assert (await _analysis(session_factory, game_id)).identity_digest == first_digest
    after = await _rows(session_factory)
    assert [row.id for row in after] == [row.id for row in before]


async def test_a_refreshed_snapshot_records_its_own_rows_and_leaves_the_first_identitys_alone(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    _clear_snapshot_resolution_caches: None,
) -> None:
    """FR-042: publish, promote a second snapshot of the same build, recompute. Both identities
    keep every row they recorded; nothing is rewritten, so the first identity's rows keep their
    ids and stay older than the second's."""
    flow = await _publish_promote_recompute(session_factory, monkeypatch, tmp_path)

    first_digest = flow.first.document["identity"]["digest"]
    second_digest = flow.second.document["identity"]["digest"]
    assert first_digest != second_digest
    rows = await _rows(session_factory)
    first = [row for row in rows if row.identity_digest == first_digest]
    second = [row for row in rows if row.identity_digest == second_digest]
    assert first
    assert len(rows) == len(first) + len(second)
    assert _from_rows(first) == _from_document(flow.first.document)
    assert _from_rows(second) == _from_document(flow.second.document)
    assert max(row.id for row in first) < min(row.id for row in second)
    assert max(row.recorded_at for row in first) <= min(row.recorded_at for row in second)


# --- The rows ride the publishing transaction ----------------------------------------------------


async def test_a_publish_that_fails_after_the_rows_were_added_leaves_none(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The write is made, then the publish fails: if the rows were their own transaction they would
    survive. They do not, and the row is not `published` either."""
    game_id = 500_546_441
    user_id = await _seed(session_factory, game_id)
    real = KnowledgeGapsRepository.record_gaps

    async def record_then_fail(self: KnowledgeGapsRepository, **kwargs: Any) -> int:
        inserted = await real(self, **kwargs)
        assert inserted > 0
        raise RuntimeError("the publish failed after the gap rows were written")

    monkeypatch.setattr(KnowledgeGapsRepository, "record_gaps", record_then_fail)

    with pytest.raises(RuntimeError, match="after the gap rows were written"):
        await _run_once(session_factory, game_id, user_id, _Store(), _Extractor())

    assert await _rows(session_factory) == []
    assert (await _analysis(session_factory, game_id)).state is not MatchAnalysisState.PUBLISHED


async def test_a_document_the_validator_refuses_writes_no_gap_rows(
    session_factory: async_sessionmaker[AsyncSession],
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T656's path: a refused document is not published, so it records no gaps either — the gaps
    describe a published analysis. The same recording publishes rows when it is not refused, which
    is what makes the zero below mean something."""
    game_id = 500_546_441
    user_id = await _seed(session_factory, game_id)

    def refuse(_document: Any) -> None:
        raise DocumentInvalid([(8, "a datum depends on a blocking gap")])

    monkeypatch.setattr(run, "validate_document", refuse)
    store = _Store()
    await _run_once(session_factory, game_id, user_id, store, _Extractor())

    analysis = await _analysis(session_factory, game_id)
    assert analysis.state is MatchAnalysisState.FAILED
    assert analysis.error_class == "DocumentInvalid"
    assert [key for key in store.objects if key.startswith("analyses/")] == []
    assert await _rows(session_factory) == []

    monkeypatch.undo()
    other_game = 504_695_319
    other_user = await _seed(session_factory, other_game)
    await _run_once(session_factory, other_game, other_user, _Store(), _Extractor())
    assert await _rows(session_factory)
