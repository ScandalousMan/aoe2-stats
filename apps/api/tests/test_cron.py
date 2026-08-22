"""Tests for `POST /api/cron/ingest` (`routers/cron.py`) — T018's local trigger.

Ahead of the shared throwaway-database harness `client` fixture (T015) in intent — this route
never reaches `get_session`/`get_object_store` at all, since neither `run_once`'s own bookkeeping
nor the stages `build_ingest_stages` (T060, `ingest_stages.py`) builds go through this app's
FastAPI dependencies at all: both build their own database access straight from `DATABASE_URL`
(`run.py`'s and `ingest_stages.py`'s own module docstrings) — but built on that same
`conftest.py` (T015b) for its environment and its fakes: `required_env`/`environment` set up
`Settings` exactly as `test_settings.py` does by hand, and `fake_session_class`/
`fake_object_store_class` override `get_session`/`get_object_store` exactly as `test_health.py`
does, all three shared rather than redefined here.

**T059**: `run_once()` itself always opens and closes its own `ingest_runs` row (FR-024),
regardless of `stages`. `REQUIRED_ENV`'s `DATABASE_URL` is a deliberately unreachable placeholder,
which is exactly why every test below that actually invokes a full cycle now also asks for the
real throwaway database (`database_url`, `clean_database` — `tests/db.py`, T015) and points
`DATABASE_URL` at it for the duration of the call, rather than the placeholder every other value
in `REQUIRED_ENV` is content to stay.

**T060**: `test_ingest_runs_and_returns_the_report_with_the_correct_secret` now exercises the real
`DiscoverStage`/`ReconcileStage`/`CaptureDrain` `build_ingest_stages` constructs from `Settings` —
against a genuinely empty throwaway database (no consenting profile exists), so every provider
call each stage would otherwise make is skipped by the stage's own "nothing to do" path before it
ever reaches the network (`DiscoverStage._consenting_profile_ids` returns `[]`, `CaptureDrain`
claims no row) — the `_block_network` fixture (`tests/conftest.py`) would fail the run loudly if
that were not so. Its `stages_completed == []` assertion, true only because `run.py`'s
`DEFAULT_STAGES` was empty, is corrected here to the three real stage names — see tasks.md's T060
entry for why updating that specific assertion is this task's own job, not a regression.
`test_ingest_returns_a_non_200_status_when_the_cycle_cannot_run_at_all` covers the sibling half of
T060: `run_once` never catches an exception a stage raises (`run.py`'s own module docstring), so a
cycle that cannot run at all — as opposed to one where individual captures failed, which `run_once`
folds into the report's own counters and still returns 200 for — reaches this route as an
ordinary unhandled exception, which `app.py`'s generic `Exception` handler already turns into a
500. Nothing about that path is new code; this is the test that proves it.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from aoe2stats_api.app import create_app
from aoe2stats_api.deps import get_object_store, get_session
from aoe2stats_api.settings import Settings, get_settings

pytestmark = pytest.mark.usefixtures("environment")


def _client(fake_session_class: type, fake_object_store_class: type) -> TestClient:
    app = create_app()

    async def _fake_session() -> AsyncIterator[Any]:
        yield fake_session_class()

    app.dependency_overrides[get_session] = _fake_session
    app.dependency_overrides[get_object_store] = lambda: fake_object_store_class()
    return TestClient(app)


def test_ingest_rejects_a_request_with_no_authorization_header(
    fake_session_class: type, fake_object_store_class: type
) -> None:
    with _client(fake_session_class, fake_object_store_class) as client:
        response = client.post("/api/cron/ingest")

    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "unauthorized"


def test_ingest_rejects_a_request_with_the_wrong_secret(
    fake_session_class: type, fake_object_store_class: type
) -> None:
    with _client(fake_session_class, fake_object_store_class) as client:
        response = client.post(
            "/api/cron/ingest", headers={"Authorization": "Bearer not-the-right-secret"}
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_ingest_rejects_a_malformed_authorization_header(
    fake_session_class: type, fake_object_store_class: type, required_env: dict[str, str]
) -> None:
    with _client(fake_session_class, fake_object_store_class) as client:
        response = client.post(
            "/api/cron/ingest", headers={"Authorization": required_env["CRON_SECRET"]}
        )

    assert response.status_code == 401


def test_ingest_runs_and_returns_the_report_with_the_correct_secret(
    fake_session_class: type,
    fake_object_store_class: type,
    required_env: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    database_url: str,
    clean_database: None,
) -> None:
    # `run_once()` (T059) always opens and closes its own `ingest_runs` row, straight from
    # `DATABASE_URL` — see this module's docstring. `REQUIRED_ENV`'s own value is an unreachable
    # placeholder, so this one call needs the real throwaway database in its place.
    monkeypatch.setenv("DATABASE_URL", database_url)

    with _client(fake_session_class, fake_object_store_class) as client:
        response = client.post(
            "/api/cron/ingest",
            headers={"Authorization": f"Bearer {required_env['CRON_SECRET']}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["trigger"] == "local"
    assert body["budget_seconds"] == 5
    # T060: real, provider-backed stages, not the empty `DEFAULT_STAGES` tuple `run.py` falls
    # back to — see this module's own docstring for why an empty database never reaches out.
    assert body["stages_completed"] == ["discover", "reconcile", "drain"]
    assert body["stopped_early"] is False


def test_ingest_returns_a_non_200_status_when_the_cycle_cannot_run_at_all(
    fake_session_class: type,
    fake_object_store_class: type,
    required_env: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    database_url: str,
    clean_database: None,
) -> None:
    """T060's other half: a stage that raises — the shape of a source unreachable for the whole
    cycle, never one capture's own failure — must surface as a non-200 response, since `run_once`
    never catches it (`run.py`'s own module docstring). This never reaches `stored_total`/
    `failed_total`/... on the report; those are for per-capture outcomes the drain already
    resolved without raising."""
    monkeypatch.setenv("DATABASE_URL", database_url)

    class _AlwaysFailsStage:
        name = "discover"

        async def __call__(self, budget: object) -> dict[str, int]:
            raise RuntimeError("the discovery source is unreachable for this whole cycle")

    monkeypatch.setattr(
        "aoe2stats_api.ingest_stages.build_ingest_stages",
        lambda settings: (_AlwaysFailsStage(),),
    )

    app = create_app()

    async def _fake_session() -> AsyncIterator[Any]:
        yield fake_session_class()

    app.dependency_overrides[get_session] = _fake_session
    app.dependency_overrides[get_object_store] = lambda: fake_object_store_class()

    # `raise_server_exceptions=False`: FastAPI's `TestClient` otherwise re-raises an unhandled
    # exception into the test itself instead of returning the 500 `app.py`'s own generic
    # `Exception` handler renders — the response this test is actually about.
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/cron/ingest",
            headers={"Authorization": f"Bearer {required_env['CRON_SECRET']}"},
        )

    assert response.status_code == 500


def test_ingest_never_reveals_the_configured_secret_in_the_response(
    fake_session_class: type, fake_object_store_class: type, required_env: dict[str, str]
) -> None:
    with _client(fake_session_class, fake_object_store_class) as client:
        response = client.post("/api/cron/ingest")

    assert required_env["CRON_SECRET"] not in response.text


def test_ingest_rejects_a_non_ascii_authorization_header_without_raising(
    fake_session_class: type, fake_object_store_class: type
) -> None:
    """`hmac.compare_digest` raises `TypeError` on a non-ASCII `str`; the comparison must be
    done on bytes so an attacker-controlled header returns 401, not a 500."""
    with _client(fake_session_class, fake_object_store_class) as client:
        response = client.post(
            "/api/cron/ingest",
            headers={"Authorization": "Bearer café".encode()},
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_ingest_stays_post_only_since_nothing_schedules_this_route(
    fake_session_class: type, fake_object_store_class: type, required_env: dict[str, str]
) -> None:
    """`api/cron/ingest.py`, not this FastAPI route, is the one Vercel Cron calls with `GET`."""
    with _client(fake_session_class, fake_object_store_class) as client:
        response = client.get(
            "/api/cron/ingest",
            headers={"Authorization": f"Bearer {required_env['CRON_SECRET']}"},
        )

    assert response.status_code == 405


def test_ingest_refuses_a_bare_bearer_prefix_when_the_configured_secret_is_empty(
    fake_session_class: type, fake_object_store_class: type
) -> None:
    """The defect T018b fixes: an empty configured secret must never authenticate a bare
    `Authorization: Bearer ` header. `Settings` now enforces `min_length=32` so this cannot
    happen through normal configuration, but the handler must not rely on that alone —
    `model_construct` bypasses validation, exactly as a future refactor or a differently built
    `Settings` object could."""
    fake_settings = Settings.model_construct(cron_secret=SecretStr(""))

    app = create_app()

    async def _fake_session() -> AsyncIterator[Any]:
        yield fake_session_class()

    app.dependency_overrides[get_session] = _fake_session
    app.dependency_overrides[get_object_store] = lambda: fake_object_store_class()
    app.dependency_overrides[get_settings] = lambda: fake_settings

    with TestClient(app) as client:
        response = client.post("/api/cron/ingest", headers={"Authorization": "Bearer "})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
