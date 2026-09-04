"""Tests for `scripts/checks/api_entrypoint_deps.py`, the guard born from the 2026-09-04 production
500 — `api/analyze.py`'s module-scope `from aoe2stats_analyzer.admission import check_admission`
raised `ModuleNotFoundError` on Vercel because `aoe2stats-analyzer` was a workspace member but never
a root `pyproject.toml` dependency, the same class of gap T014d already fixed once for `api/
index.py` and `api/cron/ingest.py`.

Every fixture below is synthetic — a `tmp_path` tree this file builds and controls, mirroring a
real `api/` directory and a real root `pyproject.toml` in miniature — never the real repository,
matching `test_asset_packs.py`'s own convention for the same reason: this check's own tests must not
change meaning as the real `api/` directory grows.

**The level this suite names explicitly** (the task's own requirement): the guard must cover every
file under `api/`, not only `api/analyze.py`. `test_check_api_entrypoint_deps_catches_a_missing_
dependency_in_any_entrypoint` builds three files shaped like the real `api/index.py`, `api/cron/
ingest.py` and `api/analyze.py` — each importing a distinct `aoe2stats_*` package — and proves a
dependency missing from any one of the three is caught, individually, rather than the guard only
ever looking at the file the original outage happened to hit.
"""

from __future__ import annotations

from pathlib import Path


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_imported_aoe2stats_modules_reads_only_column_zero_import_lines() -> None:
    """A module-scope `import`/`from ... import` line is read; an indented one — inside a function
    or an `if` — is not, matching the task's own "detecting module-scope simply" instruction."""
    from scripts.checks.api_entrypoint_deps import imported_aoe2stats_modules

    text = (
        "from __future__ import annotations\n"
        "\n"
        "import os\n"
        "from aoe2stats_api.settings import get_settings\n"
        "from aoe2stats_analyzer.run import run_once\n"
        "import aoe2stats_storage.models\n"
        "\n"
        "def handler():\n"
        "    from aoe2stats_ingester.run import run_once as inner  # not module scope\n"
        "    return inner\n"
    )
    assert imported_aoe2stats_modules(text) == {
        "aoe2stats_api",
        "aoe2stats_analyzer",
        "aoe2stats_storage",
    }


def test_module_to_dist_name_replaces_every_underscore() -> None:
    """`aoe2stats_analyzer` -> `aoe2stats-analyzer`, `aoe2stats_replay_engine` ->
    `aoe2stats-replay-engine` — every underscore, not only the first."""
    from scripts.checks.api_entrypoint_deps import module_to_dist_name

    assert module_to_dist_name("aoe2stats_analyzer") == "aoe2stats-analyzer"
    assert module_to_dist_name("aoe2stats_replay_engine") == "aoe2stats-replay-engine"


def test_declared_root_dependencies_reads_project_dependencies() -> None:
    """The real shape of the root manifest's own `[project].dependencies` list, plus a version
    specifier a future entry might carry — stripped, not left attached to the name."""
    from scripts.checks.api_entrypoint_deps import declared_root_dependencies

    text = (
        "[project]\n"
        'name = "aoe2-stats"\n'
        'dependencies = [\n  "aoe2stats-api",\n  "aoe2stats-ingester>=0.1.0",\n]\n'
    )
    assert declared_root_dependencies(text) == {"aoe2stats-api", "aoe2stats-ingester"}


def test_check_api_entrypoint_deps_is_clean_when_every_import_is_declared(tmp_path: Path) -> None:
    """The passing case: a file imports one package, the root manifest declares it, no failure."""
    from scripts.checks.api_entrypoint_deps import check_api_entrypoint_deps

    api_root = tmp_path / "api"
    _write(api_root / "index.py", "from aoe2stats_api.app import app\n")
    pyproject_path = tmp_path / "pyproject.toml"
    _write(pyproject_path, '[project]\ndependencies = ["aoe2stats-api"]\n')

    assert check_api_entrypoint_deps(api_root=api_root, pyproject_path=pyproject_path) == []


def test_check_api_entrypoint_deps_fails_on_the_real_2026_09_04_shape(tmp_path: Path) -> None:
    """The exact fault this guard exists for, reproduced in miniature: `analyze.py` imports
    `aoe2stats_analyzer` at module scope, the root manifest names only `aoe2stats-api` and
    `aoe2stats-ingester` (the pre-fix root `pyproject.toml`'s own list), and the check must report
    exactly the one missing dist name."""
    from scripts.checks.api_entrypoint_deps import check_api_entrypoint_deps

    api_root = tmp_path / "api"
    _write(api_root / "index.py", "from aoe2stats_api.app import app\n")
    _write(
        api_root / "analyze.py",
        "from aoe2stats_analyzer.admission import check_admission\n"
        "from aoe2stats_api.settings import get_settings\n",
    )
    pyproject_path = tmp_path / "pyproject.toml"
    _write(
        pyproject_path,
        '[project]\ndependencies = ["aoe2stats-api", "aoe2stats-ingester"]\n',
    )

    failures = check_api_entrypoint_deps(api_root=api_root, pyproject_path=pyproject_path)
    assert len(failures) == 1
    assert "aoe2stats_analyzer" in failures[0]
    assert "aoe2stats-analyzer" in failures[0]
    assert "analyze.py" in failures[0]


def test_check_api_entrypoint_deps_catches_a_missing_dependency_in_any_entrypoint(
    tmp_path: Path,
) -> None:
    """The level this task names explicitly: the guard is not `analyze.py`-only. Three files shaped
    like the three real `api/` entrypoints, each importing one distinct undeclared package; the
    check must catch each one on its own file, individually, proving the scan walks every file under
    `api/` rather than a single hard-coded path."""
    from scripts.checks.api_entrypoint_deps import check_api_entrypoint_deps

    api_root = tmp_path / "api"
    entrypoints = {
        "index.py": "aoe2stats_api",
        "cron/ingest.py": "aoe2stats_ingester",
        "analyze.py": "aoe2stats_analyzer",
    }
    for relative_path, module in entrypoints.items():
        _write(api_root / relative_path, f"from {module}.mod import thing\n")

    # A root manifest declaring none of the three: every one of the three files must be caught.
    pyproject_path = tmp_path / "pyproject.toml"
    _write(pyproject_path, "[project]\ndependencies = []\n")

    failures = check_api_entrypoint_deps(api_root=api_root, pyproject_path=pyproject_path)
    assert len(failures) == 3
    joined = "\n".join(failures)
    assert "index.py" in joined and "aoe2stats-api" in joined
    assert "cron/ingest.py" in joined and "aoe2stats-ingester" in joined
    assert "analyze.py" in joined and "aoe2stats-analyzer" in joined

    # Now declare only `cron/ingest.py`'s own dependency: exactly the other two must still fail,
    # proving each file is checked independently rather than the guard passing once any one
    # dependency is declared.
    _write(pyproject_path, '[project]\ndependencies = ["aoe2stats-ingester"]\n')
    failures = check_api_entrypoint_deps(api_root=api_root, pyproject_path=pyproject_path)
    assert len(failures) == 2
    joined = "\n".join(failures)
    assert "index.py" in joined
    assert "analyze.py" in joined
    assert "cron/ingest.py" not in joined


def test_check_api_entrypoint_deps_reports_every_missing_import_in_one_file(tmp_path: Path) -> None:
    """A single file importing two undeclared packages produces two failures, not one —
    `asset_packs.py`'s own convention of one failure per missing thing, not per file."""
    from scripts.checks.api_entrypoint_deps import check_api_entrypoint_deps

    api_root = tmp_path / "api"
    _write(
        api_root / "analyze.py",
        "from aoe2stats_analyzer.admission import check_admission\n"
        "from aoe2stats_storage.repositories.base import session_scope\n",
    )
    pyproject_path = tmp_path / "pyproject.toml"
    _write(pyproject_path, "[project]\ndependencies = []\n")

    failures = check_api_entrypoint_deps(api_root=api_root, pyproject_path=pyproject_path)
    assert len(failures) == 2
