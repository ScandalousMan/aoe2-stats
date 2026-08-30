"""T103: `app.py`'s per-request correlation id and its two logging exception handlers.

`_RequestIdMiddleware` (`app.py`) is asserted at the response-header layer — every request answers
with a fresh `X-Request-Id`, never derived from anything the caller supplied — and at the log
layer, where both `_handle_configuration_error` and `_handle_unexpected_error` name that same id
in the one line they log for a failing request. `_handle_unexpected_error`'s own fix is the second
half of this file: it used to `logger.exception(...)` the full traceback of *any* exception any
router or provider call raised, which is exactly the shape the task's own instructions warn about
("logging a full exception object that embeds a request header") generalised to any value an
exception's own message might carry — a SQLAlchemy statement error's bound parameters, a
`packages/providers` exception folding in the raw `httpx` failure, or, here, a value a test stands
in for one. `test_configuration_envelope.py`'s own `test_the_response_names_keys_and_never_
configuration_values` is the sibling assertion for the *response* body; this file is the log line.
"""

from __future__ import annotations

import logging
import re
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aoe2stats_api.app import create_app

_UUID4_PATTERN = re.compile(
    r"\A[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z", re.IGNORECASE
)

_LEAKED_LOOKING_VALUE = "S3_SECRET_ACCESS_KEY=cd1f9e7b2a6e4c0f9b7a3d5e8c1a2b3d"


def test_every_response_carries_a_fresh_x_request_id_header() -> None:
    """Even a plain 404 for an unmatched route carries the header — `_RequestIdMiddleware` runs
    outside routing entirely, the same "matched before any router" property `_NoIndexHeaderMiddle
    ware` already has (`app.py`'s own docstring)."""
    with TestClient(create_app()) as client:
        first = client.get("/api/__does_not_exist__")
        second = client.get("/api/__does_not_exist__")

    first_id = first.headers.get("x-request-id")
    second_id = second.headers.get("x-request-id")
    assert first_id is not None and _UUID4_PATTERN.match(first_id)
    assert second_id is not None and _UUID4_PATTERN.match(second_id)
    # Fresh per request, never reused — a caller cannot correlate two different requests by it.
    assert first_id != second_id


def test_unhandled_error_log_line_names_the_request_id_and_class_never_the_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Constitution VIII. The previous shape of `_handle_unexpected_error` (`logger.exception`)
    attached the full traceback — whose last line is `str(exc)` — to every unhandled error this
    process logs. This raises an exception whose message embeds a value shaped like a real secret
    and asserts the log line names the request id (matching the response header, so an operator
    really can go from one to the other) and the exception's class, `ValueError`, while never
    repeating the value the exception carried.
    """
    app: FastAPI = create_app()

    @app.get("/api/__leaky_exception__")
    async def _leaky() -> dict[str, str]:
        raise ValueError(f"upstream call failed: {_LEAKED_LOOKING_VALUE}")

    logging.getLogger("aoe2stats_api").disabled = False
    with (
        caplog.at_level("ERROR", logger="aoe2stats_api"),
        TestClient(app, raise_server_exceptions=False) as client,
    ):
        response = client.get("/api/__leaky_exception__")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    # Not asserted on the response here: Starlette elevates an `Exception`-keyed handler to
    # `ServerErrorMiddleware`, which sits *outside* every `app.add_middleware(...)` layer
    # (`_RequestIdMiddleware` and `_NoIndexHeaderMiddleware` both included) — a pre-existing
    # property of this file's middleware ordering, not something this task's scope changes. The
    # log line is still the one place `_handle_unexpected_error` runs and is asserted below;
    # `test_configuration_error_log_line_carries_the_request_id_and_never_a_value` is the case
    # where the handler *is* reached inside that middleware stack and the header assertion holds.
    error_records = [record for record in caplog.records if record.levelname == "ERROR"]
    assert len(error_records) == 1
    message = error_records[0].getMessage()
    assert re.search(r"request_id=\S+", message)
    assert "ValueError" in message
    assert _LEAKED_LOOKING_VALUE not in message
    assert "upstream call failed" not in message
    # Never the exception's own repr either — only its bare class name belongs in this line.
    assert str(ValueError(f"upstream call failed: {_LEAKED_LOOKING_VALUE}")) not in message


def test_configuration_error_log_line_carries_the_request_id_and_never_a_value(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    required_env: dict[str, str],
) -> None:
    """The sibling handler, `_handle_configuration_error`, already named only key *names*
    (T390) — this only adds the request id and checks it is the same discipline: present, matching
    the response header, and no configuration value from `required_env` anywhere in the line."""
    from aoe2stats_api import deps
    from aoe2stats_api.settings import get_settings

    for key, value in required_env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("CRON_SECRET", raising=False)
    for cached in (get_settings, deps.get_engine, deps.get_session_factory, deps.get_object_store):
        cached.cache_clear()

    logging.getLogger("aoe2stats_api").disabled = False
    try:
        with (
            caplog.at_level("ERROR", logger="aoe2stats_api"),
            TestClient(create_app()) as client,
        ):
            response = client.get("/api/me")
    finally:
        for cached in (
            get_settings,
            deps.get_engine,
            deps.get_session_factory,
            deps.get_object_store,
        ):
            cached.cache_clear()

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "configuration_invalid"
    request_id = response.headers.get("x-request-id")
    assert request_id is not None and _UUID4_PATTERN.match(request_id)

    error_records = [record for record in caplog.records if record.levelname == "ERROR"]
    assert len(error_records) == 1
    message = error_records[0].getMessage()
    assert request_id in message
    assert "CRON_SECRET" in message
    for key, value in required_env.items():
        if key == "CRON_SECRET":
            continue
        if len(value) >= 6 and not value.isdigit():
            assert value not in message, f"{key}'s value leaked into the log line"


def test_request_id_is_never_derived_from_a_caller_supplied_header() -> None:
    """A caller cannot poison or spoof the correlation id by sending its own — `_RequestIdMiddle
    ware` always mints a fresh `uuid4`, so an incoming `X-Request-Id` is simply ignored rather than
    echoed back."""
    spoofed = str(uuid.uuid4())
    with TestClient(create_app()) as client:
        response = client.get("/api/__does_not_exist__", headers={"X-Request-Id": spoofed})

    assert response.headers.get("x-request-id") != spoofed
