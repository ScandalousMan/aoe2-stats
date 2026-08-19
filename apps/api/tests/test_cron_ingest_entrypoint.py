"""Tests for `api/cron/ingest.py` — the deployed Vercel cron entrypoint (T018).

Not part of `aoe2stats_api`: it is the second of the two platform-shaped files `plan.md` allows at
the repository root, reachable here only because `pythonpath = ["."]` in the root `pyproject.toml`
puts the repository root on `sys.path` (the same PEP 420 implicit-namespace-package mechanism that
already makes `tests.conftest` importable as a plugin). Exercised with Starlette's own
`TestClient`, not FastAPI's, since this file deliberately builds a bare Starlette `app` rather than
depending on `aoe2stats_api.app` — see the module's docstring on why the two entrypoints share
`run_once()` and nothing else.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from starlette.testclient import TestClient

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


def _client() -> TestClient:
    from api.cron.ingest import app

    return TestClient(app)


def test_ingest_rejects_a_request_with_no_authorization_header() -> None:
    with _client() as client:
        response = client.post("/api/cron/ingest")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_ingest_rejects_a_request_with_the_wrong_secret() -> None:
    with _client() as client:
        response = client.post(
            "/api/cron/ingest", headers={"Authorization": "Bearer not-the-right-secret"}
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
    assert body["trigger"] == "cron"
    assert body["budget_seconds"] == 5
    assert body["stages_completed"] == []
    assert body["stopped_early"] is False


def test_ingest_never_reveals_the_configured_secret_in_the_response() -> None:
    with _client() as client:
        response = client.post("/api/cron/ingest")

    assert REQUIRED_ENV["CRON_SECRET"] not in response.text
