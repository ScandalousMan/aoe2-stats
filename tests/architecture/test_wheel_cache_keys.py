"""Every workspace member's uv `cache-keys` must cover every file its wheel ships.

uv rebuilds the cached wheel of a local package only when one of its `cache-keys` changes, and the
default key is `pyproject.toml` alone. A non-editable install from a reused checkout then reinstalls
a stale wheel after any commit that leaves that file untouched — measured 2026-10-30, when such an
install shipped 9 of `packages/knowledge`'s 10 snapshot directories
(`packages/knowledge/pyproject.toml`'s `[tool.uv]` comment holds the reproduction).

This reads each member's hatch wheel target and asserts the declared keys include `pyproject.toml`
and a `<dir>/**` glob for the top directory of every `packages` entry and every `force-include`
source. A new force-included directory, or a new member, without a matching key fails here.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MEMBERS = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text())["tool"]["uv"]["workspace"][
    "members"
]


def _top(path: str) -> str:
    return Path(path).parts[0]


@pytest.mark.parametrize("member", _MEMBERS)
def test_cache_keys_cover_every_file_the_wheel_ships(member: str) -> None:
    pyproject = tomllib.loads((_REPO_ROOT / member / "pyproject.toml").read_text())
    wheel = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]
    shipped = {_top(p) for p in wheel["packages"]} | {
        _top(s) for s in wheel.get("force-include", {})
    }
    required = {"pyproject.toml"} | {f"{d}/**" for d in shipped}

    declared = {
        key["file"] for key in pyproject["tool"]["uv"].get("cache-keys", []) if "file" in key
    }

    missing = required - declared
    assert not missing, (
        f"{member}/pyproject.toml's `[tool.uv] cache-keys` lacks {sorted(missing)}: a change there "
        "would leave uv reinstalling a stale cached wheel on a non-editable install."
    )
