"""Tests for `api/index.py` — the deployed Vercel request-path entrypoint (T014c).

Not part of `aoe2stats_api`: it is the first of the two platform-shaped files `plan.md` allows at
the repository root, reachable here only because `pythonpath = ["."]` in the root `pyproject.toml`
puts the repository root on `sys.path` — the same mechanism `test_cron_ingest_entrypoint.py` (T018)
already relies on for `api/cron/ingest.py`.

`api/index.py` does not build its own app the way `api/cron/ingest.py` builds its own Starlette
one: it re-exports `aoe2stats_api.app.app` module-for-module, so the one thing worth asserting
about it is that identity, plus that the module carries nothing of its own for application code to
accidentally depend on. `_FakeSession`/`_FakeObjectStore` now live once in `conftest.py` (T015b),
behind the `fake_session_class`/`fake_object_store_class` fixtures.

`test_the_re_exported_app_serves_a_real_request_through_the_error_envelope` needs the
`environment` fixture (T014e): `routers/health.py` now resolves `Settings` as its own first
dependency, ahead of `get_session`/`get_object_store`, so a real `Settings` build is on the path
for `/api/health` even though this test fakes out the database and the object store — without a
full environment it would exercise `configuration_invalid`, not the 200 it means to assert.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

import aoe2stats_api.app as api_app_module
from aoe2stats_api.deps import get_object_store, get_session
from aoe2stats_storage.revision import EXPECTED_SCHEMA_REVISION


def test_the_re_exported_app_is_the_same_object_the_fastapi_module_builds() -> None:
    import api.index as entrypoint

    assert entrypoint.app is api_app_module.app


def test_the_module_exposes_nothing_besides_the_app() -> None:
    import api.index as entrypoint

    assert entrypoint.__all__ == ["app"]


@pytest.mark.usefixtures("environment")
def test_the_re_exported_app_serves_a_real_request_through_the_error_envelope(
    fake_session_class: type, fake_object_store_class: type
) -> None:
    import api.index as entrypoint

    app = entrypoint.app

    async def _fake_session() -> AsyncIterator[Any]:
        yield fake_session_class()

    app.dependency_overrides[get_session] = _fake_session
    app.dependency_overrides[get_object_store] = lambda: fake_object_store_class()
    try:
        with TestClient(app) as client:
            response = client.get("/api/health")
    finally:
        app.dependency_overrides.pop(get_session, None)
        app.dependency_overrides.pop(get_object_store, None)

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ok",
        "object_store": "ok",
        "schema_revision": EXPECTED_SCHEMA_REVISION,
    }
