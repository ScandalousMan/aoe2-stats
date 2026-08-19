"""Tests for `api/index.py` — the deployed Vercel request-path entrypoint (T014c).

Not part of `aoe2stats_api`: it is the first of the two platform-shaped files `plan.md` allows at
the repository root, reachable here only because `pythonpath = ["."]` in the root `pyproject.toml`
puts the repository root on `sys.path` — the same mechanism `test_cron_ingest_entrypoint.py` (T018)
already relies on for `api/cron/ingest.py`.

`api/index.py` does not build its own app the way `api/cron/ingest.py` builds its own Starlette
one: it re-exports `aoe2stats_api.app.app` module-for-module, so the one thing worth asserting
about it is that identity, plus that the module carries nothing of its own for application code to
accidentally depend on.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from fastapi.testclient import TestClient

import aoe2stats_api.app as api_app_module
from aoe2stats_api.deps import get_object_store, get_session


class _FakeSession:
    async def execute(self, _statement: object) -> None:
        return None


class _FakeObjectStore:
    async def list_keys(self, prefix: str = "") -> list[str]:
        return []


def test_the_re_exported_app_is_the_same_object_the_fastapi_module_builds() -> None:
    import api.index as entrypoint

    assert entrypoint.app is api_app_module.app


def test_the_module_exposes_nothing_besides_the_app() -> None:
    import api.index as entrypoint

    assert entrypoint.__all__ == ["app"]


def test_the_re_exported_app_serves_a_real_request_through_the_error_envelope() -> None:
    import api.index as entrypoint

    app = entrypoint.app

    async def _fake_session() -> AsyncIterator[Any]:
        yield _FakeSession()

    app.dependency_overrides[get_session] = _fake_session
    app.dependency_overrides[get_object_store] = lambda: _FakeObjectStore()
    try:
        with TestClient(app) as client:
            response = client.get("/api/health")
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_object_store, None)

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "object_store": "ok"}
