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
