"""Tests for `POST /api/cron/ingest` (`routers/cron.py`) — T018's local trigger.

Self-contained, ahead of the shared integration-test harness T015 builds: `get_session` and
`get_object_store` are overridden with fakes exactly as `test_health.py` does, and `Settings` is
built from a full set of `monkeypatch.setenv` calls exactly as `test_settings.py` does — this route
does not touch the database or the object store at all (`run_once`'s stages are still empty at
this stage of the feature; see `aoe2stats_ingester.run`'s module docstring), but `SettingsDep`
still resolves through the same `get_settings()` every other dependency shares.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from aoe2stats_api.app import create_app
from aoe2stats_api.deps import get_object_store, get_session
from aoe2stats_api.settings import get_settings

REQUIRED_ENV: dict[str, str] = {
    "DATABASE_URL": "postgresql+psycopg://user:password@host/dbname?sslmode=require",
    "S3_ENDPOINT_URL": "https://account.eu.r2.cloudflarestorage.com",
    "S3_BUCKET": "aoe2-stats-replays",
    "S3_ACCESS_KEY_ID": "test-access-key",
    "S3_SECRET_ACCESS_KEY": "test-secret-key",
    "S3_REGION": "auto",
    "APP_ENV": "development",
    "APP_SECRET_KEY": "test-app-secret",
    "PUBLIC_BASE_URL": "http://localhost:5173",
    "CRON_SECRET": "test-cron-secret",
    "STEAM_API_KEY": "test-steam-api-key",
    "BETA_ALLOWLIST_STEAM_IDS": "",
    "CAPTURE_BUDGET_DAYS": "21",
    "REPLAY_PUBLICATION_GRACE_HOURS": "72",
    "AOEMS_MAX_REQUESTS_PER_SECOND": "1",
    "INGEST_RUN_BUDGET_SECONDS": "5",
    "INGEST_MAX_CAPTURES_PER_USER_PER_RUN": "20",
    "INGEST_QUOTA_EXEMPT_DAYS": "7",
}


@pytest.fixture(autouse=True)
def _environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class _FakeSession:
    async def execute(self, _statement: object) -> None:
        return None


class _FakeObjectStore:
    async def list_keys(self, prefix: str = "") -> list[str]:
        return []


def _client() -> TestClient:
    app = create_app()

    async def _fake_session() -> AsyncIterator[Any]:
        yield _FakeSession()

    app.dependency_overrides[get_session] = _fake_session
    app.dependency_overrides[get_object_store] = lambda: _FakeObjectStore()
    return TestClient(app)


def test_ingest_rejects_a_request_with_no_authorization_header() -> None:
    with _client() as client:
        response = client.post("/api/cron/ingest")

    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "unauthorized"


def test_ingest_rejects_a_request_with_the_wrong_secret() -> None:
    with _client() as client:
        response = client.post(
            "/api/cron/ingest", headers={"Authorization": "Bearer not-the-right-secret"}
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_ingest_rejects_a_malformed_authorization_header() -> None:
    with _client() as client:
        response = client.post(
            "/api/cron/ingest", headers={"Authorization": REQUIRED_ENV["CRON_SECRET"]}
        )

    assert response.status_code == 401


def test_ingest_runs_and_returns_the_report_with_the_correct_secret() -> None:
    with _client() as client:
        response = client.post(
            "/api/cron/ingest",
            headers={"Authorization": f"Bearer {REQUIRED_ENV['CRON_SECRET']}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["trigger"] == "local"
    assert body["budget_seconds"] == 5
    assert body["stages_completed"] == []
    assert body["stopped_early"] is False


def test_ingest_never_reveals_the_configured_secret_in_the_response() -> None:
    with _client() as client:
        response = client.post("/api/cron/ingest")

    assert REQUIRED_ENV["CRON_SECRET"] not in response.text
