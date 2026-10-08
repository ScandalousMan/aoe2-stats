"""Tests for `api/analyze.py` — the deployed Vercel on-demand analysis entrypoint (T366).

Not part of `aoe2stats_api`: it is a platform-shaped file at the repository root, reachable here
only because `pythonpath = ["."]` in the root `pyproject.toml` puts the repository root on
`sys.path` — the identical mechanism `apps/api/tests/test_cron_ingest_entrypoint.py` already
relies on for `api/cron/ingest.py`, and this file mirrors that one's shape: a bare Starlette
`TestClient`, not FastAPI's, since `api/analyze.py` deliberately builds a bare Starlette `app`
rather than depending on `aoe2stats_api.app` (that file's own module docstring, and this one's).

**Scope, drawn exactly where the task dispatch drew it**: an unauthenticated request is rejected
(this file's analogue of `test_cron_ingest_entrypoint.py`'s own "rejects a request with no
Authorization header"), and the authenticated happy path reaches `run_once` — proven end to end,
through the *real* `Aoe2RecExtractor`, against the one committed reference replay
(`tests/fixtures/replays/AgeIIDE_Replay_500546441.zip`, `README.md`: "the reference against which
parser compatibility is verified") rather than a fake extractor, since this is the one test in the
whole suite whose job is to prove the real engine is actually reachable from a real HTTP request.

**What is faked, and why.** `httpx.AsyncClient.send` is intercepted so `AoemsReplayProvider` reads
the committed fixture instead of a real `aoe.ms` request — `PYTEST_DISABLE_NETWORK=1`
(`tests/conftest.py`) blocks a genuine outbound call in any case, and the fixture's whole point is
to stand in for one. `ObjectStore` is swapped for an in-memory fake — `S3_ENDPOINT_URL` in
`REQUIRED_ENV` is a placeholder host, never a reachable bucket — by wrapping
`aoe2stats_api.analyze_stages.build_analyze_dependencies` rather than patching `ObjectStore`
itself, so the real session factory, the real `AoemsReplayProvider` and the real
`Aoe2RecExtractor` this file exists to exercise are left untouched.

**The environment** (`REQUIRED_ENV`/`environment`, `conftest.py`) is this suite's own, exactly as
`test_cron_ingest_entrypoint.py` uses it — `pytestmark = pytest.mark.usefixtures("environment")`,
`DATABASE_URL` overridden per test that actually reaches a database, mirroring that file's own
module docstring on why `REQUIRED_ENV`'s own placeholder is deliberately unreachable.
"""

from __future__ import annotations

import dataclasses
import logging
import secrets
from datetime import UTC, datetime, timedelta
from importlib import metadata
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from aoe2stats_api import security
from aoe2stats_api.analyze_stages import AnalyzeDependencies
from aoe2stats_api.settings import Settings, get_settings
from aoe2stats_replay_engine.aoe2rec import ENGINE_NAME
from aoe2stats_storage.models import (
    AoeProfile,
    CaptureSource,
    CaptureStatus,
    Match,
    MatchAnalysis,
    MatchAnalysisState,
    MatchPlayer,
    RateLimitCounter,
    ReplayCapture,
    RetainedRecording,
    User,
)
from aoe2stats_storage.models import Session as UserSession

pytestmark = [pytest.mark.usefixtures("environment")]

#: See `test_replay_status.py`'s module docstring — this suite's working assumption, not yet fixed
#: by a contract document beyond T028's own implementation.
SESSION_COOKIE_NAME = "session_id"

#: `tests/fixtures/replays/`'s own README: a real, committed, well-formed replay archive — game_id
#: 500546441, point-of-view profile 196240, opponent 288714 — the one bytes this repository can run
#: through the real `aoe2rec-py` engine rather than a fake (module docstring's "What is faked").
_FIXTURE_REPLAY_PATH = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "replays"
    / "AgeIIDE_Replay_500546441.zip"
)
_FIXTURE_GAME_ID = 500546441
_FIXTURE_PARTICIPANT_A = 196240
_FIXTURE_PARTICIPANT_B = 288714

_RUNNING_ENGINE_VERSION = metadata.version(ENGINE_NAME)

#: The one host `AoemsReplayProvider` ever calls (`packages/providers/src/aoe2stats_providers/
#: aoems/provider.py`'s own `AOEMS_BASE_URL`) — the interception seam mirrors
#: `test_replay_download.py`'s own `_T335_AOEMS_HOST`.
_AOEMS_HOST = "aoe.ms"

#: An unrelated match/profile, only ever used to seed a `replay_captures` row in its own deadline
#: danger window (`deadline_gate_admits`, R7) — deliberately not the fixture game, since the
#: deadline gate is system-wide and must block a request for *any* match, not only its own.
_DEADLINE_GATE_GAME_ID = 500_600_001
_DEADLINE_GATE_PROFILE_ID = 500_600_002


def _reference_replay_bytes() -> bytes:
    return _FIXTURE_REPLAY_PATH.read_bytes()


# --- Seeding helpers, self-contained per this suite's own convention (test_analysis_routes.py, ---
# test_replay_download.py: each test file in this directory keeps its own, never a shared import) -


async def _seed_user(db_session: AsyncSession) -> User:
    user = User(allowlisted_at=datetime.now(UTC))
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    return user


async def _sign_in(client: TestClient, db_session: AsyncSession, user: User) -> None:
    """Insert a `sessions` row directly and hand the client its signed cookie — mirrors
    `test_analysis_routes.py`'s own `_sign_in`."""
    session_id = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    db_session.add(
        UserSession(
            id=session_id,
            user_id=user.id,
            created_at=now,
            expires_at=now + timedelta(days=30),
        )
    )
    await db_session.commit()
    secret = get_settings().app_secret_key.get_secret_value()
    client.cookies.set(SESSION_COOKIE_NAME, security._sign(session_id, secret))


async def _seed_fixture_match(db_session: AsyncSession) -> None:
    """The reference replay's own match: two participants, comfortably inside the capture budget
    (`completed_at` two days ago), so `run_once` never reads it as `unavailable` (R8)."""
    db_session.add(AoeProfile(profile_id=_FIXTURE_PARTICIPANT_A, alias="TheViper", country="FR"))
    db_session.add(AoeProfile(profile_id=_FIXTURE_PARTICIPANT_B, alias="Opponent", country="FR"))
    db_session.add(
        Match(
            game_id=_FIXTURE_GAME_ID,
            leaderboard_id=3,
            completed_at=datetime.now(UTC) - timedelta(days=2),
            source="relic",
            raw_payload={"matchHistoryId": _FIXTURE_GAME_ID},
        )
    )
    db_session.add(MatchPlayer(game_id=_FIXTURE_GAME_ID, profile_id=_FIXTURE_PARTICIPANT_A))
    db_session.add(MatchPlayer(game_id=_FIXTURE_GAME_ID, profile_id=_FIXTURE_PARTICIPANT_B))
    await db_session.commit()


async def _seed_capture_in_deadline_danger(db_session: AsyncSession) -> None:
    """One `replay_captures` row, unstored and past its own deadline — exactly the condition
    `deadline_gate_admits` (`admission.py`, R7) reads, on a match and profile the admission-gate
    tests never ask to analyse: the gate is system-wide, so it must block a request for the fixture
    match without the two having anything else in common."""
    db_session.add(
        AoeProfile(profile_id=_DEADLINE_GATE_PROFILE_ID, alias="DeadlineGate", country="FR")
    )
    db_session.add(
        Match(
            game_id=_DEADLINE_GATE_GAME_ID,
            leaderboard_id=3,
            completed_at=datetime.now(UTC) - timedelta(days=25),
            source="relic",
            raw_payload={},
        )
    )
    await db_session.flush()
    db_session.add(
        ReplayCapture(
            game_id=_DEADLINE_GATE_GAME_ID,
            profile_id=_DEADLINE_GATE_PROFILE_ID,
            status=CaptureStatus.PENDING,
            source=CaptureSource.AUTOMATIC,
            capture_deadline_at=datetime.now(UTC) - timedelta(hours=1),
        )
    )
    await db_session.commit()


class _FakeObjectStore:
    """An in-memory `ObjectStore` stand-in — `S3_ENDPOINT_URL` in `REQUIRED_ENV` is a placeholder
    host, never a reachable bucket (module docstring's "What is faked"). Mirrors `conftest.py`'s
    own `_FakeObjectStore` in shape, kept local per this directory's self-contained convention."""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}
        self.put_calls: list[str] = []

    async def put(
        self, key: str, body: bytes, *, content_type: str = "application/octet-stream"
    ) -> None:
        self._objects[key] = body
        self.put_calls.append(key)

    async def put_if_absent(
        self, key: str, body: bytes, *, content_type: str = "application/octet-stream"
    ) -> bool:
        if key in self._objects:
            return False
        self._objects[key] = body
        self.put_calls.append(key)
        return True

    async def get(self, key: str) -> bytes:
        return self._objects[key]

    async def list_keys(self, prefix: str = "") -> list[str]:
        return [key for key in self._objects if key.startswith(prefix)]


def _install_fake_aoems_upstream(monkeypatch: pytest.MonkeyPatch, zip_bytes: bytes) -> None:
    """Answers every `GET https://aoe.ms/replay/...` call with the committed reference replay —
    mirrors `test_replay_download.py`'s own `_install_fake_aoems_upstream`."""

    async def fake_send(
        self: httpx.AsyncClient, request: httpx.Request, **kwargs: object
    ) -> httpx.Response:
        if request.url.host != _AOEMS_HOST:
            raise AssertionError(f"unexpected outbound request to {request.url}")
        return httpx.Response(200, content=zip_bytes, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "send", fake_send)


def _install_no_calls_allowed_upstream(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any outbound call at all is a hard failure — the proof that a blocked admission gate
    refuses *before* `run_once` ever reaches `replay_provider.fetch_replay` (R7's own three
    directions), not merely that the eventual response happens to carry the right code."""

    async def _no_calls(
        self: httpx.AsyncClient, request: httpx.Request, **kwargs: object
    ) -> httpx.Response:
        raise AssertionError(
            f"unexpected outbound request to {request.url} — admission should have refused "
            "before run_once ever ran"
        )

    monkeypatch.setattr(httpx.AsyncClient, "send", _no_calls)


def _install_fake_object_store(monkeypatch: pytest.MonkeyPatch) -> _FakeObjectStore:
    """Wraps the real `build_analyze_dependencies` rather than replacing it outright, so the real
    session factory, `AoemsReplayProvider` and `Aoe2RecExtractor` this file exists to exercise
    through a real HTTP request are left untouched — only the object store is swapped."""
    import api.analyze as analyze_module

    from aoe2stats_api import analyze_stages

    fake_store = _FakeObjectStore()
    real_build = analyze_stages.build_analyze_dependencies

    def _patched(settings: Settings) -> AnalyzeDependencies:
        deps = real_build(settings)
        return dataclasses.replace(deps, object_store=fake_store)

    monkeypatch.setattr(analyze_module, "build_analyze_dependencies", _patched)
    return fake_store


def _client() -> TestClient:
    from api.analyze import app

    return TestClient(app)


# ================================================================================================
# An unauthenticated request is rejected — this file's analogue of
# test_cron_ingest_entrypoint.py's own "rejects a request with no Authorization header"
# ================================================================================================


def test_analyze_rejects_a_request_with_no_session_cookie() -> None:
    with _client() as client:
        response = client.post("/api/analyze", json={"game_id": _FIXTURE_GAME_ID})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_analyze_rejects_a_request_with_a_tampered_session_cookie(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cookie is present but signs nothing this process issued — `get_active_session` never
    finds a row for it, unlike the no-cookie case above, which never reaches the database at all
    (`api/analyze.py`'s own module docstring)."""
    monkeypatch.setenv("DATABASE_URL", database_url)

    with _client() as client:
        client.cookies.set(SESSION_COOKIE_NAME, "not-a-real-signed-session-id")
        response = client.post("/api/analyze", json={"game_id": _FIXTURE_GAME_ID})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


# ================================================================================================
# The authenticated happy path reaches run_once — end to end, through the real Aoe2RecExtractor
# ================================================================================================


async def test_analyze_authenticated_happy_path_reaches_run_once(
    db_session: AsyncSession,
    database_url: str,
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", database_url)
    zip_bytes = _reference_replay_bytes()
    _install_fake_aoems_upstream(monkeypatch, zip_bytes)
    fake_store = _install_fake_object_store(monkeypatch)

    await _seed_fixture_match(db_session)
    user = await _seed_user(db_session)

    with _client() as client:
        await _sign_in(client, db_session, user)
        response = client.post("/api/analyze", json={"game_id": _FIXTURE_GAME_ID})

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "published"
    assert body["parser_version"] == _RUNNING_ENGINE_VERSION
    assert body["stale"] is False
    assert body["point_of_view_profile_id"] in (_FIXTURE_PARTICIPANT_A, _FIXTURE_PARTICIPANT_B)
    assert body["result_path"] == f"/api/matches/{_FIXTURE_GAME_ID}/analysis"
    assert body["reason"] is None

    # `run_once` itself did the work — the row it published, read back directly, not merely the
    # response this route happens to build from it (`test_run_once.py`'s own convention: "every
    # assertion about what one call did reads the row back ... never a return value").
    row = await db_session.get(MatchAnalysis, _FIXTURE_GAME_ID)
    assert row is not None
    assert row.state is MatchAnalysisState.PUBLISHED
    assert row.parser_name == ENGINE_NAME
    assert row.parser_version == _RUNNING_ENGINE_VERSION
    assert row.result_key is not None

    # The published document itself, and the retained recording — FR-033: an analysis this
    # service publishes retains the recording it was derived from, and both objects this call
    # wrote are in the fake store, not merely referenced by a key nobody wrote.
    assert row.result_key in fake_store.put_calls
    assert len(fake_store.put_calls) == 2  # the retained recording, then the published document


async def test_analyze_serves_the_published_result_without_reparsing_a_second_time(
    db_session: AsyncSession,
    database_url: str,
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SC-006: a second `POST /api/analyze` for a match already `published` and not stale fetches
    and parses nothing again — asserted here by making a second outbound fetch a hard failure."""
    monkeypatch.setenv("DATABASE_URL", database_url)
    zip_bytes = _reference_replay_bytes()
    _install_fake_aoems_upstream(monkeypatch, zip_bytes)
    _install_fake_object_store(monkeypatch)

    await _seed_fixture_match(db_session)
    user = await _seed_user(db_session)

    with _client() as client:
        await _sign_in(client, db_session, user)
        first = client.post("/api/analyze", json={"game_id": _FIXTURE_GAME_ID})
        assert first.status_code == 200

        # A second call must not reach `aoe.ms` again — `_install_fake_aoems_upstream` above
        # already refuses a request to any host that is not `aoe.ms`, but the published row being
        # served straight back with zero calls is the property this test names, so the fetch is
        # replaced with one that raises on any call at all.
        async def _no_more_calls(
            self: httpx.AsyncClient, request: httpx.Request, **kwargs: object
        ) -> httpx.Response:
            raise AssertionError(f"unexpected second outbound request to {request.url}")

        monkeypatch.setattr(httpx.AsyncClient, "send", _no_more_calls)

        second = client.post("/api/analyze", json={"game_id": _FIXTURE_GAME_ID})

    assert second.status_code == 200
    assert second.json() == first.json()


# ================================================================================================
# The three admission gates (R7, FR-039, FR-047) — applied here, before run_once, since run_once
# itself holds no gate of its own (`run.py`'s and `admission.py`'s own docstrings: "a later caller
# applies it before ever reaching here"). Each blocked-gate case below asserts `run_once` was never
# reached at all (no outbound call, no `match_analyses` row) and that the three refusals are
# distinguishable by `code`, not merely by status. `test_analyze_authenticated_happy_path_reaches_
# run_once` above is the contrast case: every gate open under `REQUIRED_ENV`'s own defaults, and
# it reaches `published`, which only happens if `run_once` actually ran.
# ================================================================================================


async def test_analyze_refuses_while_a_capture_sits_in_its_deadline_danger_window(
    db_session: AsyncSession,
    database_url: str,
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", database_url)
    _install_no_calls_allowed_upstream(monkeypatch)
    await _seed_capture_in_deadline_danger(db_session)
    user = await _seed_user(db_session)

    with _client() as client:
        await _sign_in(client, db_session, user)
        response = client.post("/api/analyze", json={"game_id": _FIXTURE_GAME_ID})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "capture_deadline_contention"
    assert await db_session.get(MatchAnalysis, _FIXTURE_GAME_ID) is None


async def test_analyze_refuses_when_the_daily_source_budget_is_exhausted(
    db_session: AsyncSession,
    database_url: str,
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("ANALYSIS_MAX_SOURCE_REQUESTS_PER_DAY", "0")
    _install_no_calls_allowed_upstream(monkeypatch)
    user = await _seed_user(db_session)

    with _client() as client:
        await _sign_in(client, db_session, user)
        response = client.post("/api/analyze", json={"game_id": _FIXTURE_GAME_ID})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "analysis_budget_exhausted"
    assert await db_session.get(MatchAnalysis, _FIXTURE_GAME_ID) is None


async def test_analyze_refuses_when_the_retention_cap_is_reached(
    db_session: AsyncSession,
    database_url: str,
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("ANALYSIS_RETENTION_CAP_BYTES", "0")
    _install_no_calls_allowed_upstream(monkeypatch)
    user = await _seed_user(db_session)

    with _client() as client:
        await _sign_in(client, db_session, user)
        response = client.post("/api/analyze", json={"game_id": _FIXTURE_GAME_ID})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "analysis_cap_reached"
    assert await db_session.get(MatchAnalysis, _FIXTURE_GAME_ID) is None


# ================================================================================================
# T666h: a deployment that cannot analyse any recording answers 500, before anything is spent
# ================================================================================================


async def test_analyze_answers_500_for_a_broken_deployment_before_fetching_or_claiming_anything(
    db_session: AsyncSession,
    database_url: str,
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The refusal is a 5xx the person asking can read, naming the fault class and nothing else:
    the snapshot loader's own message (a packaged path and digests here, with a sentinel standing
    for anything that must never leak) stays in the log. The source is never called, no row is
    written (that the next request after a fix analyses normally is `apps/analyzer`'s own test)."""
    from aoe2stats_knowledge import snapshot

    sentinel = "SENTINEL-must-not-reach-the-response"
    monkeypatch.setenv("DATABASE_URL", database_url)
    _install_no_calls_allowed_upstream(monkeypatch)
    fake_store = _install_fake_object_store(monkeypatch)
    await _seed_fixture_match(db_session)
    user = await _seed_user(db_session)

    def broken() -> object:
        raise snapshot.SnapshotDigestMismatch(f"{sentinel}: digest does not match")

    # The migrations' `fileConfig` disables loggers that already exist (`apps/analyzer/tests/
    # test_run_once.py`'s identical fixture), which would hide the line asserted below.
    logging.getLogger("aoe2stats_analyzer").disabled = False
    snapshot.load_all_snapshots.cache_clear()
    monkeypatch.setattr(snapshot, "load_all_snapshots", broken)
    monkeypatch.setattr(snapshot, "load_resolvable_snapshots", broken)

    with _client() as client:
        await _sign_in(client, db_session, user)
        with caplog.at_level(logging.ERROR, logger="aoe2stats_analyzer"):
            response = client.post("/api/analyze", json={"game_id": _FIXTURE_GAME_ID})

        assert response.status_code == 500
        body = response.json()
        assert body["error"]["code"] == "analysis_deployment_fault"
        assert body["error"]["detail"] == {"fault": "SnapshotDigestMismatch"}
        assert sentinel not in response.text
        assert await db_session.get(MatchAnalysis, _FIXTURE_GAME_ID) is None
        assert fake_store.put_calls == []

        # The operator still gets the detail, from the log.
        assert any(sentinel in record.getMessage() for record in caplog.records)


# ================================================================================================
# T666m: a deployment fault on a published row is the same 500, and the flag is the match page's
# ================================================================================================


async def _publish_the_fixture_match(client: TestClient, db_session: AsyncSession) -> MatchAnalysis:
    first = client.post("/api/analyze", json={"game_id": _FIXTURE_GAME_ID})
    assert first.status_code == 200
    assert first.json()["state"] == "published"
    row = await db_session.get(MatchAnalysis, _FIXTURE_GAME_ID)
    assert row is not None
    return row


async def test_analyze_answers_the_deployment_fault_envelope_for_a_published_row(
    db_session: AsyncSession,
    database_url: str,
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A published row goes `run_once` -> `_is_stale`, which computes the identity an analysis
    would carry now and so loads the knowledge snapshot. A snapshot shipped without its rules file
    raised a bare `FileNotFoundError` there, which the entrypoint maps to nothing: a plain-text 500
    the web client cannot parse. It is now the same `analysis_deployment_fault` envelope a first
    analysis gets, and the request spends nothing: the source is not called, nothing is written to
    the store, no access-log row is added, and the served analysis stays as it was."""
    from tests.snapshot_refresh import clear_snapshot_resolution_caches, isolate_snapshot_root

    from aoe2stats_storage.models import ReplayAccessLog

    monkeypatch.setenv("DATABASE_URL", database_url)
    root = isolate_snapshot_root(monkeypatch, tmp_path)
    clear_snapshot_resolution_caches()
    _install_fake_aoems_upstream(monkeypatch, _reference_replay_bytes())
    fake_store = _install_fake_object_store(monkeypatch)
    await _seed_fixture_match(db_session)
    user = await _seed_user(db_session)

    with _client() as client:
        await _sign_in(client, db_session, user)
        published = await _publish_the_fixture_match(client, db_session)
        before = (published.state, published.result_key, published.identity_digest)
        puts_before = list(fake_store.put_calls)
        access_log_before = len((await db_session.execute(select(ReplayAccessLog))).scalars().all())

        (root / "aoe2techtree-180059" / "rules.json").unlink()
        clear_snapshot_resolution_caches()
        _install_no_calls_allowed_upstream(monkeypatch)
        logging.getLogger("aoe2stats_analyzer").disabled = False
        with caplog.at_level(logging.ERROR, logger="aoe2stats_analyzer"):
            response = client.post("/api/analyze", json={"game_id": _FIXTURE_GAME_ID})

        assert response.status_code == 500
        body = response.json()
        assert body["error"]["code"] == "analysis_deployment_fault"
        assert body["error"]["detail"] == {"fault": "FileNotFoundError"}
        assert any("deployment fault" in record.getMessage() for record in caplog.records)

    await db_session.refresh(published)
    assert (published.state, published.result_key, published.identity_digest) == before
    assert fake_store.put_calls == puts_before
    access_log_after = len((await db_session.execute(select(ReplayAccessLog))).scalars().all())
    assert access_log_after == access_log_before


async def test_analyze_reports_the_same_stale_flag_as_the_match_page_for_the_same_row(
    db_session: AsyncSession,
    database_url: str,
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The response is the match page's `analysis` object, so its `stale` is the match page's.
    The row is published and stale (an identity the running engine no longer produces), and
    `run_once` returns without recomputing - the shape in which the endpoint's missing
    retained-recording argument made the flag false by construction."""
    import api.analyze as analyze_module

    from aoe2stats_api.routers import matches

    monkeypatch.setenv("DATABASE_URL", database_url)
    _install_fake_aoems_upstream(monkeypatch, _reference_replay_bytes())
    _install_fake_object_store(monkeypatch)
    await _seed_fixture_match(db_session)
    user = await _seed_user(db_session)

    with _client() as client:
        await _sign_in(client, db_session, user)
        row = await _publish_the_fixture_match(client, db_session)
        row.identity_digest = "sha256:" + "0" * 64
        await db_session.commit()

        async def returns_without_recomputing(*args: object, **kwargs: object) -> None:
            return None

        monkeypatch.setattr(analyze_module, "run_once", returns_without_recomputing)
        response = client.post("/api/analyze", json={"game_id": _FIXTURE_GAME_ID})

    assert response.status_code == 200
    retained = await matches._retained_row(db_session, row=row)
    assert retained is not None
    assert matches._is_stale(row, retained) is True
    assert response.json()["stale"] is True


def test_the_analysis_summary_cannot_be_built_without_the_retained_row() -> None:
    """`retained` is required: a caller that forgets it gets an error, not a quietly false flag."""
    from aoe2stats_api.routers.matches import _analysis_json

    with pytest.raises(TypeError):
        _analysis_json(game_id=1, row=None)  # type: ignore[call-arg]


# ================================================================================================
# T666j: the recompute retry window is the configured one, read by the deployed entrypoint
# ================================================================================================


async def _publish_then_refuse_a_recompute(
    client: TestClient, db_session: AsyncSession, fake_store: _FakeObjectStore
) -> MatchAnalysis:
    """Publish the fixture match, make it stale (a digest the running engine no longer produces)
    and corrupt its retained object, so the second request's recompute is refused at the checksum
    and the prior analysis is kept - the case that writes the retry window."""
    first = client.post("/api/analyze", json={"game_id": _FIXTURE_GAME_ID})
    assert first.status_code == 200
    assert first.json()["state"] == "published"

    row = await db_session.get(MatchAnalysis, _FIXTURE_GAME_ID)
    assert row is not None
    row.identity_digest = "sha256:" + "0" * 64
    retained = (await db_session.execute(select(RetainedRecording))).scalar_one()
    fake_store._objects[retained.object_key] = b"bit rot"
    await db_session.commit()

    second = client.post("/api/analyze", json={"game_id": _FIXTURE_GAME_ID})
    assert second.status_code == 200
    await db_session.refresh(row)
    return row


@pytest.mark.parametrize("configured_seconds", [90, 7200])
async def test_the_configured_retry_window_reaches_run_once_through_the_entrypoint(
    db_session: AsyncSession,
    database_url: str,
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
    configured_seconds: int,
) -> None:
    """A refused recompute leaves the prior analysis served and parks the row for exactly the
    configured number of seconds - 90 s, which the code's one-hour default could never produce, and
    two hours, which it could not either. Before T666j `api/analyze.py` threaded no such value and
    both cases got an hour."""
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("ANALYSIS_RECOMPUTE_RETRY_SECONDS", str(configured_seconds))
    _install_fake_aoems_upstream(monkeypatch, _reference_replay_bytes())
    fake_store = _install_fake_object_store(monkeypatch)
    await _seed_fixture_match(db_session)
    user = await _seed_user(db_session)

    with _client() as client:
        await _sign_in(client, db_session, user)
        before = datetime.now(UTC)
        row = await _publish_then_refuse_a_recompute(client, db_session, fake_store)
        after = datetime.now(UTC)

    assert row.state is MatchAnalysisState.PUBLISHED
    assert row.lease_expires_at is not None
    window = timedelta(seconds=configured_seconds)
    assert before + window <= row.lease_expires_at <= after + window


async def test_a_short_configured_window_lets_the_next_request_recompute_once_it_lapses(
    db_session: AsyncSession,
    database_url: str,
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With the window configured at one second, a third request made after it lapses reads the
    retained recording again (a second recompute attempt, so a second access-log row); the code's
    one-hour default would still have been closed and read nothing."""
    import asyncio

    from aoe2stats_storage.models import ReplayAccessLog

    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("ANALYSIS_RECOMPUTE_RETRY_SECONDS", "1")
    _install_fake_aoems_upstream(monkeypatch, _reference_replay_bytes())
    fake_store = _install_fake_object_store(monkeypatch)
    await _seed_fixture_match(db_session)
    user = await _seed_user(db_session)

    async def recompute_reads() -> int:
        rows = (await db_session.execute(select(ReplayAccessLog))).scalars().all()
        return len([r for r in rows if r.purpose == "recompute"])

    with _client() as client:
        await _sign_in(client, db_session, user)
        await _publish_then_refuse_a_recompute(client, db_session, fake_store)
        assert await recompute_reads() == 1

        await asyncio.sleep(1.2)
        third = client.post("/api/analyze", json={"game_id": _FIXTURE_GAME_ID})

    assert third.status_code == 200
    assert await recompute_reads() == 2


# ================================================================================================
# T706: a request that joins or re-claims work already on the books is not counted (FR-040)
# ================================================================================================


async def _seed_fixture_analysis_row(
    db_session: AsyncSession,
    *,
    state: MatchAnalysisState,
    lease_offset: timedelta | None = None,
) -> None:
    now = datetime.now(UTC)
    db_session.add(
        MatchAnalysis(
            game_id=_FIXTURE_GAME_ID,
            state=state,
            point_of_view_profile_id=_FIXTURE_PARTICIPANT_A,
            requested_at=now - timedelta(hours=1),
            claimed_at=now - timedelta(hours=1) if lease_offset is not None else None,
            lease_expires_at=None if lease_offset is None else now + lease_offset,
            attempts=1 if lease_offset is not None else 0,
        )
    )
    await db_session.commit()


async def _counted_requests(db_session: AsyncSession, user: User) -> int:
    result = await db_session.execute(
        select(RateLimitCounter.count).where(
            RateLimitCounter.user_id == user.id, RateLimitCounter.bucket == "analysis_request"
        )
    )
    return sum(result.scalars().all())


async def test_a_first_request_increments_the_counter(
    db_session: AsyncSession,
    database_url: str,
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The contrast for the cases below: no row yet means the request starts new work."""
    monkeypatch.setenv("DATABASE_URL", database_url)
    _install_fake_aoems_upstream(monkeypatch, _reference_replay_bytes())
    _install_fake_object_store(monkeypatch)
    await _seed_fixture_match(db_session)
    user = await _seed_user(db_session)

    with _client() as client:
        await _sign_in(client, db_session, user)
        response = client.post("/api/analyze", json={"game_id": _FIXTURE_GAME_ID})

    assert response.status_code == 200
    assert await _counted_requests(db_session, user) == 1


@pytest.mark.parametrize(
    "case_id,state,lease_offset,expected_state",
    [
        ("queued", MatchAnalysisState.QUEUED, None, "published"),
        ("running_expired", MatchAnalysisState.RUNNING, timedelta(seconds=-5), "published"),
        ("running_live", MatchAnalysisState.RUNNING, timedelta(seconds=300), "running"),
    ],
)
async def test_a_request_on_a_queued_or_running_row_does_not_count_against_the_limit(
    db_session: AsyncSession,
    database_url: str,
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
    case_id: str,
    state: MatchAnalysisState,
    lease_offset: timedelta | None,
    expected_state: str,
) -> None:
    """The limit is set to 0, so a counted request would answer 429: the 200 is the proof the
    request was not counted, and the counter table is empty besides. A live `running` lease is
    joined (the response says `running`, nothing is fetched); a `queued` row and an expired lease
    are re-claimed and the analysis completes."""
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("ANALYSIS_MAX_REQUESTS_PER_USER_PER_DAY", "0")
    _install_fake_aoems_upstream(monkeypatch, _reference_replay_bytes())
    _install_fake_object_store(monkeypatch)
    await _seed_fixture_match(db_session)
    await _seed_fixture_analysis_row(db_session, state=state, lease_offset=lease_offset)
    user = await _seed_user(db_session)

    with _client() as client:
        await _sign_in(client, db_session, user)
        response = client.post("/api/analyze", json={"game_id": _FIXTURE_GAME_ID})

    assert response.status_code == 200, f"{case_id}: {response.text}"
    assert response.json()["state"] == expected_state
    assert await _counted_requests(db_session, user) == 0


@pytest.mark.parametrize("state", [MatchAnalysisState.FAILED, MatchAnalysisState.REFUSED])
async def test_a_request_on_a_terminal_row_still_counts_against_the_limit(
    db_session: AsyncSession,
    database_url: str,
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
    state: MatchAnalysisState,
) -> None:
    """A retry of a failed or refused analysis starts new work, so a user at their limit is told
    so - the same 429 an absent row gets."""
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("ANALYSIS_MAX_REQUESTS_PER_USER_PER_DAY", "0")
    _install_no_calls_allowed_upstream(monkeypatch)
    await _seed_fixture_match(db_session)
    await _seed_fixture_analysis_row(db_session, state=state)
    user = await _seed_user(db_session)

    with _client() as client:
        await _sign_in(client, db_session, user)
        response = client.post("/api/analyze", json={"game_id": _FIXTURE_GAME_ID})

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"


async def test_an_uncounted_request_still_meets_every_admission_gate(
    db_session: AsyncSession,
    database_url: str,
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("ANALYSIS_MAX_SOURCE_REQUESTS_PER_DAY", "0")
    _install_no_calls_allowed_upstream(monkeypatch)
    await _seed_fixture_match(db_session)
    await _seed_fixture_analysis_row(db_session, state=MatchAnalysisState.QUEUED)
    user = await _seed_user(db_session)

    with _client() as client:
        await _sign_in(client, db_session, user)
        response = client.post("/api/analyze", json={"game_id": _FIXTURE_GAME_ID})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "analysis_budget_exhausted"
    assert await _counted_requests(db_session, user) == 0


async def test_an_unreadable_body_is_refused_before_anything_is_counted(
    db_session: AsyncSession,
    database_url: str,
    clean_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", database_url)
    _install_no_calls_allowed_upstream(monkeypatch)
    user = await _seed_user(db_session)

    with _client() as client:
        await _sign_in(client, db_session, user)
        response = client.post("/api/analyze", json={"game": 1})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"
    assert await _counted_requests(db_session, user) == 0
