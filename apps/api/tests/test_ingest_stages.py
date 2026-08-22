"""Unit tests for `build_ingest_stages` (T060) — `apps/api/src/aoe2stats_api/ingest_stages.py`,
the factory that closes the gap `run.py`'s own module docstring named: `DEFAULT_STAGES` stays
`()` in production unless something builds real, provider-backed stages from `Settings` and hands
them to `run_once` as `stages=`.

No network call and no database access happens here: constructing an `httpx.AsyncClient`, a
`boto3` S3 client or a SQLAlchemy `AsyncEngine` performs no I/O by itself, and `PYTEST_DISABLE_
NETWORK=1`'s `_block_network` fixture (`tests/conftest.py`) would fail this suite loudly if it
ever did. These are unit tests of the wiring, not integration tests of a cycle — `test_cron.py`'s
`test_ingest_runs_and_returns_the_report_with_the_correct_secret` and its sibling in
`test_cron_ingest_entrypoint.py` are what prove the built stages actually run, end to end, through
the real entrypoints.
"""

from __future__ import annotations

import pytest

from aoe2stats_api.ingest_stages import build_ingest_stages
from aoe2stats_api.settings import get_settings

pytestmark = pytest.mark.usefixtures("environment")


def test_build_ingest_stages_returns_discover_reconcile_drain_in_that_order() -> None:
    """Stage order is discover, reconcile, drain (T060) — `run_once` only ever decides whether to
    *start* the next stage in the sequence it is handed, so the sequence itself is this factory's
    responsibility, not `run_once`'s.
    """
    stages = build_ingest_stages(get_settings())

    assert [stage.name for stage in stages] == ["discover", "reconcile", "drain"]


def test_build_ingest_stages_builds_the_real_stage_classes() -> None:
    from aoe2stats_ingester.capture import CaptureDrain
    from aoe2stats_ingester.discover import DiscoverStage
    from aoe2stats_ingester.reconcile import ReconcileStage

    discover, reconcile, drain = build_ingest_stages(get_settings())

    assert isinstance(discover, DiscoverStage)
    assert isinstance(reconcile, ReconcileStage)
    assert isinstance(drain, CaptureDrain)


def test_build_ingest_stages_wires_the_fairness_quota_from_settings() -> None:
    """FR-044's fairness cap has gone inert twice before (f0c9a6e, e8d9a4e) by a `CaptureDrain`
    built somewhere with `max_captures_per_user_per_run`/`quota_exempt_days` left at their default
    `None` — which disables the cap silently rather than failing loudly, since `CaptureDrain`
    itself only rejects the two arguments being supplied *one without the other*, never both
    absent (`capture.py`'s own constructor guard). This is the one place production ever builds a
    `CaptureDrain`, so it is the one regression test that would actually have caught it.
    """
    settings = get_settings()

    _, _, drain = build_ingest_stages(settings)

    assert drain._quota_enabled() is True
    assert drain._max_captures_per_user_per_run == settings.ingest_max_captures_per_user_per_run
    assert drain._quota_exempt_days == settings.ingest_quota_exempt_days


def test_build_ingest_stages_reuses_the_process_wide_client_engine_and_bucket() -> None:
    """T060a: `build_ingest_stages` used to build a fresh `httpx.AsyncClient`, a fresh
    `AsyncEngine` and a fresh `TokenBucket` on *every* call — never released on a long-lived
    process (`routers/cron.py`'s own entrypoint, the local and phase-2-VPS path ADR-0002 names),
    and, worse, silently re-arming the AOEMS token bucket's burst allowance on every invocation,
    which defeats "at most 1 request per second, serially" the moment two invocations happen in
    the same process (`docs/data-sources.md` §2, `contracts/providers.md`).

    Two consecutive calls with the same `Settings` must share one client, one engine and one
    AOEMS rate limiter — asserted by identity, not merely by equal configuration, since two
    distinct `TokenBucket` instances at the same rate would still each start full.
    """
    settings = get_settings()

    first_discover, _, first_drain = build_ingest_stages(settings)
    second_discover, _, second_drain = build_ingest_stages(settings)

    assert (
        first_discover._match_history_provider._client
        is second_discover._match_history_provider._client
    )
    assert first_drain._replay_provider._client is second_drain._replay_provider._client
    assert first_drain._replay_provider._rate_limiter is second_drain._replay_provider._rate_limiter
    assert first_discover._session_factory.kw["bind"] is second_discover._session_factory.kw["bind"]


def test_build_ingest_stages_keys_the_cache_by_settings_so_a_different_database_url_does_not_reuse_the_engine() -> (  # noqa: E501
    None
):
    """The cache must not key on `Settings` identity alone: a second, differently built
    `Settings` (a different `DATABASE_URL`) must get its own engine rather than silently reusing
    one built for another database.
    """
    import os

    settings = get_settings()
    first_discover, _, _ = build_ingest_stages(settings)

    other_env = dict(os.environ)
    other_env["DATABASE_URL"] = (
        "postgresql+psycopg://user:password@other-host/other-dbname?sslmode=require"
    )
    with pytest.MonkeyPatch.context() as monkeypatch:
        for key, value in other_env.items():
            monkeypatch.setenv(key, value)
        get_settings.cache_clear()
        try:
            other_settings = get_settings()
            second_discover, _, _ = build_ingest_stages(other_settings)
        finally:
            get_settings.cache_clear()

    assert (
        first_discover._session_factory.kw["bind"]
        is not second_discover._session_factory.kw["bind"]
    )


def test_build_ingest_stages_never_imports_the_replay_engine_at_module_scope() -> None:
    """T018c's discipline, restated for this module: importing `aoe2stats_api.ingest_stages`
    itself must never load `aoe2rec_py` — only calling `build_ingest_stages` does. Run in a
    subprocess for the same reason `test_engine_isolation.py` is: a stale `sys.modules` entry from
    an earlier test in this same session would make a regressed, eager import look clean.
    """
    import subprocess
    import sys

    check = (
        "import sys\n"
        "import aoe2stats_api.ingest_stages\n"
        "assert 'aoe2rec_py' not in sys.modules, sorted(sys.modules)\n"
        "print('ok')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", check], capture_output=True, text=True, timeout=30
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "ok"
