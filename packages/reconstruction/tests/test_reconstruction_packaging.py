"""The deployed function installs only what `apps/analyzer` declares, so the analyzer must name
`aoe2stats-reconstruction` itself rather than inherit it (research R12; the 2026-09-04 fault)."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load(relative: str) -> dict[str, object]:
    return tomllib.loads((_REPO_ROOT / relative).read_text(encoding="utf-8"))


def test_analyzer_declares_reconstruction_itself() -> None:
    manifest = _load("apps/analyzer/pyproject.toml")
    project = manifest["project"]
    assert isinstance(project, dict)
    assert "aoe2stats-reconstruction" in project["dependencies"]
    sources = manifest["tool"]["uv"]["sources"]  # type: ignore[index]
    assert sources["aoe2stats-reconstruction"] == {"workspace": True}


def test_reconstruction_depends_on_core_and_knowledge_only() -> None:
    """Among `aoe2stats-*` workspace packages, exactly core and knowledge (T913). Third-party
    dependencies such as pydantic are outside this rule."""
    manifest = _load("packages/reconstruction/pyproject.toml")
    dependencies = manifest["project"]["dependencies"]  # type: ignore[index]
    workspace = sorted(
        name
        for name in (re.split(r"[\s<>=!~;\[]", str(dep), maxsplit=1)[0] for dep in dependencies)
        if name.startswith("aoe2stats-")
    )
    assert workspace == ["aoe2stats-core", "aoe2stats-knowledge"]


def test_package_exposes_a_version() -> None:
    import aoe2stats_reconstruction

    assert aoe2stats_reconstruction.__version__ == "0.1.0"
