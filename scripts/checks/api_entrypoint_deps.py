#!/usr/bin/env python3
"""Every `api/` entrypoint's own module-scope imports must be declared on the root manifest.

Born from a real 500 (2026-09-04): `api/analyze.py` imports `aoe2stats_analyzer` at module scope,
but the root `pyproject.toml`'s `[project].dependencies` — the T014d comment above `[project]`
explains why that list, and not the workspace membership alone, decides what Vercel's Python
runtime actually installs — never named it. `aoe2stats-analyzer` was a workspace member and every
test that runs from the repository root with `uv sync --all-packages --dev` installed it anyway, so
nothing caught the gap until the deployed function tried to import it and had never been installed
with the two entrypoints the root manifest did list. `config-preflight.mjs`'s own header records the
same shape of fault one layer down (a settings key present in code but absent from the deployment
environment); this is that discipline applied to the layer above it — a package present in code but
absent from the *manifest* that decides what gets installed at all.

The rule this enforces: every `aoe2stats_*` module a file under `api/` imports at module scope (a
column-0 `import`/`from ... import` line — conditional or inside-function imports are deliberately
not parsed; nothing under `api/` uses one to work around this) must have its dist name (underscores
to hyphens: `aoe2stats_analyzer` -> `aoe2stats-analyzer`) listed in the root `pyproject.toml`'s
`[project].dependencies`. Not merely a `[tool.uv.workspace]` member — every package this feature has
ever needed already was one, which is exactly what let this fault ship.

Run: uv run scripts/checks/api_entrypoint_deps.py
Exit: 0 clean, 1 on any failure. Stdlib only (tomllib, 3.11+), so it needs no environment.
"""

from __future__ import annotations

import argparse
import re
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

#: A column-0 (module-scope) `import X` or `from X import ...` line. `re.MULTILINE` makes `^` match
#: after every newline, not only at the start of the string; an indented import — inside a function
#: or an `if` — never matches, which is the "module-scope, detected simply" the spec asks for rather
#: than a real AST walk.
_IMPORT_RE = re.compile(r"^(?:import|from)\s+(?P<module>[A-Za-z0-9_.]+)", re.MULTILINE)

#: The dependency-string prefix `tool.uv`/PEP 508 allow after a bare distribution name — a version
#: specifier (`>=1.0`), an extras marker (`[extra]`) or an environment marker (`; python_version
#: ...`). None of the root manifest's own entries carry one today, but a future entry might, and
#: this check should still recognise it rather than starting to under-match silently.
_DEPENDENCY_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+")


def imported_aoe2stats_modules(text: str) -> set[str]:
    """Every top-level `aoe2stats_*` module a module-scope import line names, collapsed to its
    first path component (`aoe2stats_api.ratelimit` -> `aoe2stats_api`) — the check cares which
    *package* a file depends on, not which symbol inside it."""
    modules: set[str] = set()
    for match in _IMPORT_RE.finditer(text):
        top_level = match.group("module").split(".", 1)[0]
        if top_level.startswith("aoe2stats_"):
            modules.add(top_level)
    return modules


def module_to_dist_name(module: str) -> str:
    """`aoe2stats_analyzer` -> `aoe2stats-analyzer` — every workspace member's module name is its
    dist name with underscores for hyphens, with no exception this repository has ever introduced
    (`pyproject.toml`'s own `[tool.ruff.lint.isort].known-first-party` names all seven the same
    way)."""
    return module.replace("_", "-")


def declared_root_dependencies(pyproject_text: str) -> set[str]:
    """The root `pyproject.toml`'s own `[project].dependencies`, as bare distribution names —
    stripped of any version specifier, extras marker or environment marker a future entry might
    carry, even though none of today's does."""
    data = tomllib.loads(pyproject_text)
    raw_dependencies = data.get("project", {}).get("dependencies", [])
    names: set[str] = set()
    for raw in raw_dependencies:
        match = _DEPENDENCY_NAME_RE.match(raw.strip())
        if match:
            names.add(match.group(0))
    return names


def check_api_entrypoint_deps(*, api_root: Path, pyproject_path: Path) -> list[str]:
    """Every `*.py` under `api_root`, held against `pyproject_path`'s own declared dependencies.

    One failure string per (file, missing dist name) pair — a file importing two undeclared
    packages produces two failures, not one, matching `asset_packs.py`'s own convention of one
    failure per missing thing rather than one per file.
    """
    declared = declared_root_dependencies(read(pyproject_path))
    failures: list[str] = []
    for path in sorted(api_root.rglob("*.py")):
        modules = imported_aoe2stats_modules(read(path))
        for module in sorted(modules):
            dist_name = module_to_dist_name(module)
            if dist_name not in declared:
                rel = path.relative_to(REPO) if path.is_relative_to(REPO) else path
                failures.append(
                    f"{rel}: imports `{module}` (dist `{dist_name}`) at module scope, but "
                    f"{pyproject_path.name}'s [project].dependencies does not declare "
                    f"`{dist_name}` — Vercel's Python runtime will not install it "
                    "(see this file's module docstring)."
                )
    return failures


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    api_root = REPO / "api"
    pyproject_path = REPO / "pyproject.toml"

    print("api_entrypoint_deps: api/ against pyproject.toml's [project].dependencies\n")
    failures = check_api_entrypoint_deps(api_root=api_root, pyproject_path=pyproject_path)

    if failures:
        for failure in failures:
            print(f"  FAIL  {failure}")
        print(f"\n{len(failures)} failure(s).")
        return 1
    print("clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
