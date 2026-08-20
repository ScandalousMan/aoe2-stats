"""Tests for the FastAPI application shell: `GET /api/health` and the single error envelope.

These are self-contained unit tests, ahead of the shared integration-test harness T015 builds:
`get_session` and `get_object_store` (`deps.py`) are overridden with fakes through FastAPI's
`dependency_overrides`, so no real database and no real bucket are ever reached — consistent with
`PYTEST_DISABLE_NETWORK=1` (constitution III) and with the fact that this task ships before T015's
throwaway-database harness exists. `_FakeSession` and `_FakeObjectStore` themselves, along with
their `fails=` outage simulation this module exercises most of, now live once in `conftest.py`
(T015b) behind the `fake_session_class`/`fake_object_store_class` fixtures.

**T014e.** `health.py` resolves `Settings` as its own first dependency now, ahead of `get_session`
and `get_object_store` (see that module's docstring), so — unlike before this task — a real
`Settings` build is on the path for every request this file sends, even the ones whose database
and object store are faked out. `pytestmark` below applies the shared `environment` fixture
(`conftest.py`) to the whole module for exactly that reason: without it, every test here would hit
`configuration_invalid` instead of the outcome it means to exercise, since no environment variable
is set by default. The one test that deliberately wants a broken `Settings`
(`test_health_reports_configuration_invalid_...`) starts from that same full environment and
removes specific keys from it, rather than building its own from nothing — the closest match to
how the real fault happened.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from aoe2stats_api.app import create_app
from aoe2stats_api.deps import get_object_store, get_session

pytestmark = pytest.mark.usefixtures("environment")

#: Below this length, or purely numeric (`CAPTURE_BUDGET_DAYS=21`,
#: `AOEMS_MAX_REQUESTS_PER_SECOND=1`, ...), a `required_env` value is common enough — a status
#: code, a list length, a count — that asserting its absence from a JSON body would be asserting
#: nothing in particular and would eventually fail on an unrelated coincidence. The values this
#: excludes are exactly the tuning knobs, never a credential, a DSN or a URL: every secret and
#: every host in `required_env` is well past this floor.
_MIN_CHECKABLE_VALUE_LENGTH = 6


def _is_checkable_configuration_value(value: str) -> bool:
    return bool(value) and len(value) >= _MIN_CHECKABLE_VALUE_LENGTH and not value.isdigit()


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
    # `_FakeSession.execute` (conftest.py) raises a bare `RuntimeError` for `db_fails=True`; the
    # class name is exactly what an operator needs and exactly what T014e asks `detail` to carry
    # now, in place of the `{}` a 503 used to answer with.
    assert body["error"]["detail"] == {"error_class": "RuntimeError"}


def test_health_reports_object_store_unavailable_through_the_error_envelope(
    fake_session_class: type, fake_object_store_class: type
) -> None:
    with _client(fake_session_class, fake_object_store_class, object_store_fails=True) as client:
        response = client.get("/api/health")

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "object_store_unavailable"
    assert body["error"]["detail"] == {"error_class": "RuntimeError"}


def test_health_reports_configuration_invalid_when_settings_fails_to_build(
    monkeypatch: pytest.MonkeyPatch,
    fake_session_class: type,
    fake_object_store_class: type,
) -> None:
    """The very first fault of the evening: two required keys absent, and — before this task —
    a bare `internal_error` with the missing names visible only in the platform's own log. This
    starts from the full `environment` fixture and removes exactly the two keys the real outage
    was missing, so `Settings()` fails to build the same way it did in production, ahead of
    either probe below it — `get_session`/`get_object_store` are still overridden by `_client`
    but are never reached, since `_resolve_settings` (`health.py`) is declared first."""
    monkeypatch.delenv("S3_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("STEAM_API_KEY", raising=False)

    with _client(fake_session_class, fake_object_store_class) as client:
        response = client.get("/api/health")

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "configuration_invalid"
    assert body["error"]["detail"] == {
        "missing_or_invalid_keys": ["S3_SECRET_ACCESS_KEY", "STEAM_API_KEY"]
    }


@pytest.mark.parametrize(
    ("db_fails", "object_store_fails"),
    [(True, False), (False, True)],
    ids=["database_unavailable", "object_store_unavailable"],
)
def test_failure_responses_never_contain_a_configuration_value(
    db_fails: bool,
    object_store_fails: bool,
    fake_session_class: type,
    fake_object_store_class: type,
    required_env: dict[str, str],
) -> None:
    """Every value `required_env` (`conftest.py`) sets — the DSN, the bucket credentials, the
    app and cron secrets, the Steam API key — must be absent from the raw response body of a
    failing health check, whatever the failure. `detail` carries only key names and error
    classes (T014e); this is the negative half of that guarantee, checked against the literal
    response text rather than the parsed JSON, so a value hiding in `message` would be caught
    too."""
    with _client(
        fake_session_class,
        fake_object_store_class,
        db_fails=db_fails,
        object_store_fails=object_store_fails,
    ) as client:
        response = client.get("/api/health")

    assert response.status_code == 503
    body_text = response.text
    for key, value in required_env.items():
        if not _is_checkable_configuration_value(value):
            continue
        assert value not in body_text, f"{key}'s configured value leaked into /api/health"


def test_configuration_invalid_response_never_contains_a_configuration_value(
    monkeypatch: pytest.MonkeyPatch,
    fake_session_class: type,
    fake_object_store_class: type,
    required_env: dict[str, str],
) -> None:
    """Same guarantee as above, for the `Settings`-fails-to-build case: the sixteen keys that
    *are* present must not leak alongside the names of the two that are not."""
    monkeypatch.delenv("S3_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("STEAM_API_KEY", raising=False)

    with _client(fake_session_class, fake_object_store_class) as client:
        response = client.get("/api/health")

    assert response.status_code == 503
    body_text = response.text
    for key, value in required_env.items():
        if not _is_checkable_configuration_value(value):
            continue
        assert value not in body_text, f"{key}'s configured value leaked into /api/health"


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
