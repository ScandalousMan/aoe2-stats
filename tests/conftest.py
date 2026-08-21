"""Workspace-wide pytest configuration.

Registered as a plugin (`-p tests.conftest` in the root `pyproject.toml`) rather than relied on as
a plain per-directory conftest, because it must apply to every workspace member's `tests/`
directory and to `scripts/checks/tests` — none of which are descendants of this `tests/` directory,
so pytest would never discover it here on its own.
"""

import ipaddress
import os
import socket
from collections.abc import Iterator
from typing import Any

import pytest
from tests.db import NO_DATABASE_SKIP_MARKER

_real_connect = socket.socket.connect


def _is_loopback(address: object) -> bool:
    """True when a `socket.connect()` target resolves to the local loopback interface.

    Loopback stays reachable so a local test database or a local mock server keeps working; only
    genuine outbound network access is blocked.
    """
    host = address[0] if isinstance(address, tuple) else address
    if not isinstance(host, str):
        return False
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _guarded_connect(sock: socket.socket, address: object) -> Any:
    if _is_loopback(address):
        return _real_connect(sock, address)
    raise RuntimeError(
        "Network access is disabled in tests (PYTEST_DISABLE_NETWORK=1). Constitution III: unit "
        "tests never touch the network. External data belongs behind a DataProvider fixture in "
        f"packages/providers, or behind a nightly contract test. Blocked connection to {address!r}."
    )


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Make real outbound network calls fail loudly when `PYTEST_DISABLE_NETWORK=1`.

    Constitution III: "Unit tests never touch the network; only nightly contract tests do." This
    fixture is what turns that sentence into a fact the harness enforces rather than a rule
    contributors have to remember — CI sets `PYTEST_DISABLE_NETWORK=1` for `uv run pytest -q`, and
    every provider must be exercised through its recorded fixtures instead of a live call.
    """
    if os.environ.get("PYTEST_DISABLE_NETWORK") != "1":
        yield
        return
    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)
    yield


def _skip_reason_text(report: pytest.TestReport) -> str:
    """`pytest.skip(reason)` reports its reason as the last element of a `(path, lineno, message)`
    tuple in `report.longrepr`; anything else (a plain string, `None`) is stringified as-is."""
    longrepr = report.longrepr
    if isinstance(longrepr, tuple) and len(longrepr) >= 1:
        return str(longrepr[-1])
    return str(longrepr)


_NO_DB_BANNER_PRINTED_ATTR = "_aoe2stats_no_db_banner_printed"


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter, exitstatus: int, config: pytest.Config
) -> None:
    """T015d: an unmissable banner when the database-backed suite skipped locally.

    `tests/db.py` fails hard under `CI` (T015a) and skips everywhere else, because a contributor
    genuinely without Postgres running must not be blocked from testing `packages/core` or
    `packages/providers`, neither of which ever touches a database. That is the right call for
    those tests, but the local exit code stays 0 whether or not a single database-backed test ran
    — the same shape of defect T015a closed for CI, just outside it. This hook does not change the
    exit code: doing so would fail a run for a contributor who has no reason to have Postgres
    running today, which is exactly the case `tests/db.py` is designed to accommodate. It makes
    the gap impossible to miss instead, which is the correct amount of friction for a run whose
    other ~85% of tests (everything outside `apps/api`, `apps/ingester` and `tests/architecture`)
    genuinely did pass clean.

    The guard below is unrelated to that decision: `pyproject.toml` registers this file both
    explicitly (`-p tests.conftest`) and implicitly, since `tests/architecture` is a `testpaths`
    entry and this file is its ancestor conftest — pytest imports the same source file under two
    different module names (`tests.conftest` and `conftest`), which are two separate module
    objects with separate globals, so a plain module-level flag does not dedupe between them. The
    one object pluggy hands both hook calls in common is `config` itself, so the flag lives there
    instead. This also runs `_block_network` twice — harmless, since `monkeypatch.setattr` is
    idempotent — but fixing that double registration is out of this task's scope.
    """
    if getattr(config, _NO_DB_BANNER_PRINTED_ATTR, False):
        return
    no_db_skips = [
        report
        for report in terminalreporter.stats.get("skipped", [])
        if NO_DATABASE_SKIP_MARKER in _skip_reason_text(report)
    ]
    if not no_db_skips:
        return
    setattr(config, _NO_DB_BANNER_PRINTED_ATTR, True)
    terminalreporter.write_sep("=", "NO DATABASE — THIS IS NOT A CLEAN PASS", red=True, bold=True)
    terminalreporter.write_line(
        f"{len(no_db_skips)} test(s) skipped for lack of a reachable Postgres database "
        "(tests/db.py, T015): every database-backed integration test, including all of Phase 3 "
        "and later, did NOT run. A green exit code here does not mean those routers passed — it "
        "means they were never exercised.",
        red=True,
        bold=True,
    )
    terminalreporter.write_line(
        "Start Postgres at the default tests/db.py falls back to "
        "(postgresql://postgres:postgres@localhost:5432/postgres), or point TEST_DATABASE_URL at "
        "one, then re-run.",
        red=True,
        bold=True,
    )
    terminalreporter.write_sep("=", red=True, bold=True)
