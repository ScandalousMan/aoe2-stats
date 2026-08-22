"""Tests for `api/cron/ingest.py` — the deployed Vercel cron entrypoint (T018).

Not part of `aoe2stats_api`: it is the second of the two platform-shaped files `plan.md` allows at
the repository root, reachable here only because `pythonpath = ["."]` in the root `pyproject.toml`
puts the repository root on `sys.path` (the same PEP 420 implicit-namespace-package mechanism that
already makes `tests.conftest` importable as a plugin). Exercised with Starlette's own
`TestClient`, not FastAPI's, since this file deliberately builds a bare Starlette `app` rather than
depending on `aoe2stats_api.app` — see the module's docstring on why the two entrypoints share
`run_once()` and nothing else.

The environment (`REQUIRED_ENV`/`_environment` — T018b raised `CRON_SECRET` to its 32-character
floor) is `test_cron.py`'s byte-for-byte, so it now lives once in `conftest.py`'s `required_env`/
`environment` fixtures (T015b); this file opts in the same way, with
`pytestmark = pytest.mark.usefixtures("environment")`.

**T059**: `run_once()` now always opens and closes its own `ingest_runs` row (FR-024) straight
from `DATABASE_URL`, regardless of `stages` — see `test_cron.py`'s own module docstring for the
full explanation, which applies here byte-for-byte. Every test below that actually reaches
`run_once` (the two "correct secret" happy paths) points `DATABASE_URL` at the real throwaway
database for the duration of its own call rather than `REQUIRED_ENV`'s deliberately unreachable
placeholder.
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr
from starlette.testclient import TestClient

from aoe2stats_api.settings import Settings

pytestmark = pytest.mark.usefixtures("environment")


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


def test_ingest_runs_and_returns_the_report_with_the_correct_secret(
    required_env: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    database_url: str,
    clean_database: None,
) -> None:
    # See this module's docstring (T059): `run_once()`'s own `ingest_runs` bookkeeping needs a
    # reachable `DATABASE_URL`, not `REQUIRED_ENV`'s unreachable placeholder.
    monkeypatch.setenv("DATABASE_URL", database_url)

    with _client() as client:
        response = client.post(
            "/api/cron/ingest",
            headers={"Authorization": f"Bearer {required_env['CRON_SECRET']}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["trigger"] == "cron"
    assert body["budget_seconds"] == 5
    assert body["stages_completed"] == []
    assert body["stopped_early"] is False


def test_ingest_never_reveals_the_configured_secret_in_the_response(
    required_env: dict[str, str],
) -> None:
    with _client() as client:
        response = client.post("/api/cron/ingest")

    assert required_env["CRON_SECRET"] not in response.text


def test_ingest_accepts_get_with_the_correct_secret(
    required_env: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    database_url: str,
    clean_database: None,
) -> None:
    """The defect T018b fixes: Vercel Cron Jobs invoke a scheduled function with **GET**,
    attaching the bearer itself. `methods=["POST"]` alone made the nightly cycle 405 forever."""
    # See this module's docstring (T059): `run_once()`'s own `ingest_runs` bookkeeping needs a
    # reachable `DATABASE_URL`, not `REQUIRED_ENV`'s unreachable placeholder.
    monkeypatch.setenv("DATABASE_URL", database_url)

    with _client() as client:
        response = client.get(
            "/api/cron/ingest",
            headers={"Authorization": f"Bearer {required_env['CRON_SECRET']}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["trigger"] == "cron"
    assert body["budget_seconds"] == 5
    assert body["stages_completed"] == []
    assert body["stopped_early"] is False


def test_ingest_rejects_a_get_with_no_authorization_header() -> None:
    with _client() as client:
        response = client.get("/api/cron/ingest")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_ingest_rejects_a_non_ascii_authorization_header_without_raising() -> None:
    """`hmac.compare_digest` raises `TypeError` on a non-ASCII `str`; the comparison must be
    done on bytes so an attacker-controlled header returns 401, not a 500."""
    with _client() as client:
        response = client.post(
            "/api/cron/ingest",
            headers={"Authorization": "Bearer café".encode()},
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_ingest_refuses_a_bare_bearer_prefix_when_the_configured_secret_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The defect T018b fixes: an empty configured secret must never authenticate a bare
    `Authorization: Bearer ` header — verified, before the fix, to return 200. `Settings` now
    enforces `min_length=32` so this cannot happen through normal configuration, but the handler
    must not rely on that alone: `model_construct` bypasses validation, exactly as a future
    refactor or a differently built `Settings` object could."""
    import api.cron.ingest as ingest_module

    fake_settings = Settings.model_construct(cron_secret=SecretStr(""))
    monkeypatch.setattr(ingest_module, "get_settings", lambda: fake_settings)

    with TestClient(ingest_module.app) as client:
        response = client.get("/api/cron/ingest", headers={"Authorization": "Bearer "})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
