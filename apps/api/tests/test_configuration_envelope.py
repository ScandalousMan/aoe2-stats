"""T390: a `Settings` that cannot be built answers `configuration_invalid` on **every** route.

The fault this file guards is not hypothetical and not new. On 2026-08-23 the deployment target
was missing the ten configuration keys 003 declared, and the symptom a user saw was
`GET /api/me` answering `{"error": {"code": "internal_error", "detail": {}}}` — a 500 that names
nothing, for a fault whose whole diagnosis is a list of key names. `/api/health` already held that
list, because T014e gave *that route* a `try` around its own `Settings` resolution; no other route
had one, and nothing pointed from the broken route to the route that could answer.

So these tests assert the property at the level it has to hold — the application, not one route —
and the two contrast cases that decide the boundary:

- a route with no configuration handling of its own (`/api/me`) reports the same keys as the
  route that has always had some (`/api/health`), for the same broken environment;
- a `pydantic.ValidationError` raised from *inside* a route body — what `parse_strict`
  (`packages/providers/base.py`) raises for a drifted third-party payload — is **not** reported as
  a configuration fault. That is the residue the obvious fix leaves: handling
  `pydantic.ValidationError` at the application level would have made every one of this test
  file's other assertions pass while turning every provider contract violation into
  `configuration_invalid` 503. `ConfigurationError` exists to make that case impossible rather
  than merely unlikely.

Self-contained: no database and no bucket is reached. The broken-configuration cases never get
far enough to build an engine — that is the point of them — and the healthy contrast case
overrides `get_session` with `conftest.py`'s fake.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

from aoe2stats_api import deps
from aoe2stats_api.app import create_app
from aoe2stats_api.deps import get_object_store, get_session
from aoe2stats_api.settings import get_settings

pytestmark = pytest.mark.usefixtures("environment")

#: The ten keys 003 declared and the deployment target never had. Named as a list rather than
#: derived, because the assertion is about *these* keys being reported for *this* outage: a
#: derivation from `Settings` would keep passing if the route reported some other set.
_KEYS_003_DECLARED = [
    "ANALYSIS_LEASE_SECONDS",
    "ANALYSIS_MAX_RAW_BYTES",
    "ANALYSIS_MAX_REQUESTS_PER_USER_PER_DAY",
    "ANALYSIS_MAX_SOURCE_REQUESTS_PER_DAY",
    "ANALYSIS_RETENTION_CAP_BYTES",
    "ANALYSIS_RUN_BUDGET_SECONDS",
    "FAVOURITES_MAX_PER_USER",
    "PLAYER_SEARCH_CACHE_TTL_SECONDS",
    "PLAYER_SEARCH_MAX_PER_USER_PER_MINUTE",
    "REPLAY_DOWNLOAD_MAX_PER_USER_PER_MINUTE",
]


@pytest.fixture(autouse=True)
def _clear_cached_wiring() -> Iterator[None]:
    """Clear every `lru_cache` in the settings-to-storage chain, before and after each test.

    `deps.get_engine` and `deps.get_session_factory` cache a built engine, and an engine built by
    an *earlier* test in the same session survives a broken environment: `get_settings` would
    never be called again, no `ConfigurationError` would be raised, and the request would go on to
    attempt a real connection instead. That is an order-dependent pass — the test would prove the
    handler works only when it runs first — so the caches are emptied here rather than trusted.
    """
    for cached in (get_settings, deps.get_engine, deps.get_session_factory, deps.get_object_store):
        cached.cache_clear()
    yield
    for cached in (get_settings, deps.get_engine, deps.get_session_factory, deps.get_object_store):
        cached.cache_clear()


def test_me_answers_configuration_invalid_naming_every_missing_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reported outage, reproduced: `GET /api/me` with 003's ten keys unset.

    Before T390 this answered `500 internal_error` with `detail == {}`.
    """
    for key in _KEYS_003_DECLARED:
        monkeypatch.delenv(key, raising=False)

    with TestClient(create_app()) as client:
        response = client.get("/api/me")

    assert response.status_code == 503
    body = response.json()["error"]
    assert body["code"] == "configuration_invalid"
    assert body["detail"]["missing_or_invalid_keys"] == _KEYS_003_DECLARED


def test_me_and_health_report_the_same_keys_for_the_same_broken_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One fault, one answer. `/api/health` resolves `Settings` through its own dependency
    (T014e) and `/api/me` through `SessionDep`; both must name the same keys, or an operator
    reading one route and then the other is told two different things about one environment."""
    monkeypatch.delenv("ANALYSIS_LEASE_SECONDS", raising=False)
    monkeypatch.delenv("S3_BUCKET", raising=False)

    with TestClient(create_app()) as client:
        me = client.get("/api/me")
        health = client.get("/api/health")

    assert me.status_code == health.status_code == 503
    assert me.json() == health.json()
    assert me.json()["error"]["detail"]["missing_or_invalid_keys"] == [
        "ANALYSIS_LEASE_SECONDS",
        "S3_BUCKET",
    ]


def test_the_response_names_keys_and_never_configuration_values(
    monkeypatch: pytest.MonkeyPatch, required_env: dict[str, str]
) -> None:
    """Constitution VIII. `ValidationError.errors()` carries an `input` entry holding the value
    of every field in `Settings` at once — the DSN with its password, the S3 secret, the session
    signing key. The handler reads `loc` and nothing else; this asserts the consequence rather
    than the implementation, so a future rewrite that reaches for `errors()` again fails here."""
    monkeypatch.delenv("ANALYSIS_MAX_RAW_BYTES", raising=False)

    with TestClient(create_app()) as client:
        response = client.get("/api/me")

    serialized = response.text
    for key, value in required_env.items():
        if key == "ANALYSIS_MAX_RAW_BYTES":
            continue
        # Short and purely numeric values are excluded for the reason `test_health.py` gives at
        # `_MIN_CHECKABLE_VALUE_LENGTH`: asserting the absence of "21" from a JSON body asserts
        # nothing. Every secret, DSN and host in `required_env` is well past that floor.
        if len(value) >= 6 and not value.isdigit():
            assert value not in serialized, f"{key}'s value leaked into the error envelope"


def test_a_fully_configured_route_is_untouched(
    monkeypatch: pytest.MonkeyPatch, fake_session_class: type, fake_object_store_class: type
) -> None:
    """The contrast case for the handler itself: with the environment intact, `GET /api/me`
    answers its normal signed-out 200. A handler that answered 503 whenever anything went wrong
    would pass every test above and break the front end's bootstrap call."""
    app = create_app()

    async def _fake_session() -> AsyncIterator[Any]:
        yield fake_session_class()

    app.dependency_overrides[get_session] = _fake_session
    app.dependency_overrides[get_object_store] = lambda: fake_object_store_class()

    with TestClient(app) as client:
        response = client.get("/api/me")

    assert response.status_code == 200
    assert response.json() == {"authenticated": False}


class _DriftedPayload(BaseModel):
    """Stands in for a provider response model (`packages/providers/base.py`'s `parse_strict`)."""

    profile_id: int


def test_a_validation_error_raised_inside_a_route_is_not_a_configuration_fault() -> None:
    """**Name the level.** A `pydantic.ValidationError` from a route body means a third party sent
    a shape we do not accept (`ProviderContractViolation`'s own cause), not that this deployment
    is misconfigured. Answering `configuration_invalid` 503 for it would send an operator to the
    environment variables for a fault that lives in `docs/data-sources.md`, and would do it
    silently — the response is well-formed and the code is plausible.

    This is the test that fails if the handler is ever widened from `ConfigurationError` to
    `pydantic.ValidationError`, which is the obvious shortcut and the reason this file exists.
    """
    app: FastAPI = create_app()

    @app.get("/api/__drifted_payload__")
    async def _drifted() -> dict[str, str]:
        _DriftedPayload.model_validate({"profile_id": "not-a-number"})
        return {"unreachable": "true"}

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/__drifted_payload__")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"


def test_get_settings_raises_configuration_error_not_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The boundary the two exception types draw, asserted directly: `get_settings()` is the
    application's entry point to configuration and raises this application's type; `Settings()` is
    pydantic's and keeps raising pydantic's, which is what `test_settings.py` exercises."""
    from aoe2stats_api.settings import ConfigurationError, Settings

    monkeypatch.delenv("CRON_SECRET", raising=False)

    with pytest.raises(ConfigurationError) as configuration_exc:
        get_settings()
    assert configuration_exc.value.keys == ["CRON_SECRET"]
    assert isinstance(configuration_exc.value.__cause__, ValidationError)
    assert not isinstance(configuration_exc.value, ValidationError)

    with pytest.raises(ValidationError):
        Settings()  # type: ignore[call-arg]
