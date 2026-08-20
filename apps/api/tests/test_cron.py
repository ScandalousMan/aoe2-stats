"""Tests for `POST /api/cron/ingest` (`routers/cron.py`) — T018's local trigger.

Ahead of the shared throwaway-database harness `client` fixture (T015) in intent — this route
does not touch the database or the object store at all (`run_once`'s stages are still empty at
this stage of the feature; see `aoe2stats_ingester.run`'s module docstring) — but built on that
same `conftest.py` (T015b) for its environment and its fakes: `required_env`/`environment` set
up `Settings` exactly as `test_settings.py` does by hand, and `fake_session_class`/
`fake_object_store_class` override `get_session`/`get_object_store` exactly as `test_health.py`
does, all three shared rather than redefined here.
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
    fake_session_class: type, fake_object_store_class: type, required_env: dict[str, str]
) -> None:
    with _client(fake_session_class, fake_object_store_class) as client:
        response = client.post(
            "/api/cron/ingest",
            headers={"Authorization": f"Bearer {required_env['CRON_SECRET']}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["trigger"] == "local"
    assert body["budget_seconds"] == 5
    assert body["stages_completed"] == []
    assert body["stopped_early"] is False


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
