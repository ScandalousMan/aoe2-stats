"""Tests for the FastAPI application shell: `GET /api/health` and the single error envelope.

These are self-contained unit tests, ahead of the shared integration-test harness T015 builds:
`get_session` and `get_object_store` (`deps.py`) are overridden with fakes through FastAPI's
`dependency_overrides`, so no real database and no real bucket are ever reached — consistent with
`PYTEST_DISABLE_NETWORK=1` (constitution III) and with the fact that this task ships before T015's
throwaway-database harness exists. `_FakeSession` and `_FakeObjectStore` themselves, along with
their `fails=` outage simulation this module exercises most of, now live once in `conftest.py`
(T015b) behind the `fake_session_class`/`fake_object_store_class` fixtures.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from aoe2stats_api.app import create_app
from aoe2stats_api.deps import get_object_store, get_session


def _client(
    fake_session_class: type,
    fake_object_store_class: type,
    *,
    db_fails: bool = False,
    object_store_fails: bool = False,
) -> TestClient:
    app = create_app()

    async def _fake_session() -> AsyncIterator[Any]:
        yield fake_session_class(fails=db_fails)

    app.dependency_overrides[get_session] = _fake_session
    app.dependency_overrides[get_object_store] = lambda: fake_object_store_class(
        fails=object_store_fails
    )
    return TestClient(app)


def test_health_ok_when_database_and_object_store_are_reachable(
    fake_session_class: type, fake_object_store_class: type
) -> None:
    with _client(fake_session_class, fake_object_store_class) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "object_store": "ok"}


def test_health_reports_database_unavailable_through_the_error_envelope(
    fake_session_class: type, fake_object_store_class: type
) -> None:
    with _client(fake_session_class, fake_object_store_class, db_fails=True) as client:
        response = client.get("/api/health")

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "database_unavailable"
    assert isinstance(body["error"]["message"], str)
    assert body["error"]["detail"] == {}


def test_health_reports_object_store_unavailable_through_the_error_envelope(
    fake_session_class: type, fake_object_store_class: type
) -> None:
    with _client(fake_session_class, fake_object_store_class, object_store_fails=True) as client:
        response = client.get("/api/health")

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "object_store_unavailable"


def test_database_check_runs_before_object_store_check(
    fake_session_class: type, fake_object_store_class: type
) -> None:
    # Both dependencies fail; the database code must win, since the health route checks the
    # database first and raises on the first failure it hits (routers/health.py).
    with _client(
        fake_session_class, fake_object_store_class, db_fails=True, object_store_fails=True
    ) as client:
        response = client.get("/api/health")

    assert response.json()["error"]["code"] == "database_unavailable"


def test_unmatched_route_answers_through_the_error_envelope_and_not_a_bare_404(
    fake_session_class: type, fake_object_store_class: type
) -> None:
    with _client(fake_session_class, fake_object_store_class) as client:
        response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert isinstance(body["error"]["message"], str)
    assert body["error"]["detail"] == {}


@pytest.mark.parametrize("field", ["code", "message", "detail"])
def test_error_envelope_always_carries_the_three_contracted_fields(
    field: str, fake_session_class: type, fake_object_store_class: type
) -> None:
    with _client(fake_session_class, fake_object_store_class, db_fails=True) as client:
        response = client.get("/api/health")

    assert field in response.json()["error"]
