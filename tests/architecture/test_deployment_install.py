"""The bundle-shaped dry run (007, T809; FR-003, FR-005; `specs/007-shrink-deployment-storage/
research.md` R8). It began as T014d's check that a plain `uv sync` installs what the platform
entrypoints import (ADR-0002, constitution XII), and keeps that job.

**The defect T014d guarded against.** The first real deployment failed both platform functions at
cold start with `ModuleNotFoundError`: the root `pyproject.toml` had `package = false` and no
`[project.dependencies]`, so the install left only the shared dev toolchain. The fix declared the
workspace packages the entrypoints import as root dependencies. Every other test imports the
entrypoints inside `uv sync --all-packages --dev`, which installs every member whatever the root
depends on, so nothing short of building the environment the way the deployment builds it and then
importing would have caught it.

**What it checks now, in three steps.**

1. `uv sync --frozen --no-dev --no-editable` into a temporary environment (`UV_PROJECT_ENVIRONMENT`,
   never the workspace `.venv`): the builder's own flags (R2). The editable sync this module ran
   before resolves workspace packages to the repository, so it could not see a file the wheel
   lacks. `--no-dev` keeps the dev toolchain from papering over a missing runtime dependency.
2. The files a function bundle keeps are computed from `vercel.json`'s `excludeFiles` value with
   the whole-entry rule `scripts/checks/tests/test_vercel_bundle.py` asserts (its functions are
   read, not copied, so the guard and this run cannot disagree), less the directories
   `.vercelignore` drops whole (never uploaded) and the builder's own excludes. The kept set must
   be exactly the tracked files under `api/` plus the two root files that guard
   keeps on purpose (`KEPT_IN_BUNDLE`); those are copied into an empty directory.
3. From that directory, the environment's own interpreter runs in isolated mode (`-I`), which
   drops the working directory from the import path, so the probe puts the bundle root on the path
   itself, as the runtime does. It imports `api.index`, `api.analyze` and `api.cron.ingest`,
   checks the entrypoints came from the bundle and the workspace packages from the environment
   (an editable install would show here), loads every packaged knowledge snapshot through
   `aoe2stats_knowledge`'s own loader and compares the set with the repository's, and sends the
   two long-running routes an unauthenticated request through each entrypoint's own ASGI app:
   `/api/cron/ingest` must answer `401` `unauthorized` and `/api/analyze` its `401`
   `not_authenticated` session refusal. Both refuse before a database is touched. The probe's
   environment is the entrypoint tests' `REQUIRED_ENV` and nothing inherited, placeholders all,
   so a probe that did open a connection would fail instead of reaching anything.

**What only a real deployment confirms** (research R8): the host's own builder version, its
bytecode fill, and whether the trimmed functions boot in production, covered by quickstart section
5 and SC-005. This run proves the installed set and the kept files are sufficient for the three
entrypoints to import, load and answer their refusals on this machine's platform; it does not run
Vercel's builder, its Linux target platform, its cold-start install path or its filesystem routing
between the entrypoints.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SNAPSHOTS_DIR = "packages/knowledge/src/aoe2stats_knowledge/snapshots"
_SYNC_TIMEOUT_SECONDS = 900
_PROBE_TIMEOUT_SECONDS = 120


def _load_by_path(name: str, path: Path) -> ModuleType:
    """Import a module from its file, under a name of our own.

    `scripts/checks/tests` and `apps/api/tests` are not packages and are not on `sys.path` for a
    test in this directory: pytest's default import mode puts a test file's own directory there
    only while that file is collected, so a plain `import test_vercel_bundle` would work or fail
    with the order of collection. Loading by path does not depend on it, and the unique name keeps
    it from colliding with the copy pytest itself imports.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The whole-entry rule lives once, in the `excludeFiles` guard (T807); the dry run reads the same
# functions so the two cannot disagree about what the bundle holds.
_bundle_rule = _load_by_path(
    "_aoe2stats_vercel_bundle_rule", _REPO_ROOT / "scripts/checks/tests/test_vercel_bundle.py"
)


def _required_env() -> dict[str, str]:
    """The entrypoint tests' configuration: `REQUIRED_ENV` in `apps/api/tests/conftest.py`.

    Read from the source, not imported: that conftest is a fixture module its own docstring says
    is never imported by name, and importing it would drag in the test database harness. The
    values are placeholders (an unreachable database host among them), so a probe that tried to
    open a connection would fail rather than reach anything.
    """
    source = (_REPO_ROOT / "apps/api/tests/conftest.py").read_text(encoding="utf-8")
    for node in ast.parse(source).body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "REQUIRED_ENV"
            and node.value is not None
        ):
            env: dict[str, str] = ast.literal_eval(node.value)
            return env
    raise AssertionError("apps/api/tests/conftest.py no longer defines REQUIRED_ENV")


# ---------------------------------------------------------------------------------------------
# Which files the bundle holds
# ---------------------------------------------------------------------------------------------


def _tracked() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=_REPO_ROOT, check=True, capture_output=True, text=True
    )
    return [path for path in result.stdout.split("\0") if path]


def _exclude_alternatives() -> list[str]:
    config = json.loads((_REPO_ROOT / "vercel.json").read_text(encoding="utf-8"))
    functions: dict[str, dict[str, object]] = config["functions"]
    assert _bundle_rule.exclude_value_problems(functions) == []
    return list(_bundle_rule.parse_exclude(next(iter(functions.values()))["excludeFiles"]))


def _upload_ignored() -> frozenset[str]:
    """The directories `.vercelignore` drops whole, read with the guard's own parser."""
    text = (_REPO_ROOT / ".vercelignore").read_text(encoding="utf-8")
    ignored: frozenset[str] = _bundle_rule.vercelignore_directories(text)
    return ignored


def kept_files(
    tracked: list[str], alternatives: list[str], upload_ignored: frozenset[str] = frozenset()
) -> list[str]:
    """The tracked files a function bundle keeps: what `.vercelignore` does not drop whole, what
    `excludeFiles` does not drop, and what the builder's own built-in excludes do not drop either
    (any path segment named in them)."""
    builder_excludes = _bundle_rule.BUILDER_EXCLUDES
    return sorted(
        path
        for path in tracked
        if path.split("/")[0] not in upload_ignored
        and not _bundle_rule.is_excluded(path, alternatives)
        and not builder_excludes.intersection(path.split("/"))
    )


def bundle_difference(tracked: list[str], kept: list[str]) -> dict[str, list[str]]:
    """How a kept set differs from the one the layout contract describes: every tracked file under
    `api/`, plus the two files in `KEPT_IN_BUNDLE`, and nothing else."""
    wanted = {path for path in tracked if path.startswith("api/")}
    wanted |= set(_bundle_rule.KEPT_IN_BUNDLE) & set(tracked)
    return {"extra": sorted(set(kept) - wanted), "missing": sorted(wanted - set(kept))}


def _bundle_files() -> list[str]:
    tracked = _tracked()
    kept = kept_files(tracked, _exclude_alternatives(), _upload_ignored())
    difference = bundle_difference(tracked, kept)
    assert difference == {"extra": [], "missing": []}, (
        "vercel.json's `excludeFiles` does not leave exactly the tracked files under `api/` and "
        f"{sorted(_bundle_rule.KEPT_IN_BUNDLE)} in a function bundle: {difference}"
    )
    return kept


# --- the same computation on synthetic input, so a pass on the real file means something


_SYNTHETIC_TRACKED = [
    "api/index.py",
    "api/cron/ingest.py",
    "apps/web/src/main.tsx",
    "docs/a.md",
    "README.md",
    "pyproject.toml",
    "uv.lock",
    ".gitignore",
    "pnpm-lock.yaml",
]


def test_kept_files_are_api_and_the_two_kept_files_when_everything_else_is_excluded() -> None:
    kept = kept_files(_SYNTHETIC_TRACKED, ["apps/**", "docs/**", "README.md"])
    assert kept == ["api/cron/ingest.py", "api/index.py", "pyproject.toml", "uv.lock"]
    assert bundle_difference(_SYNTHETIC_TRACKED, kept) == {"extra": [], "missing": []}


def test_a_directory_left_out_of_the_exclusion_list_shows_as_extra_content() -> None:
    kept = kept_files(_SYNTHETIC_TRACKED, ["docs/**", "README.md"])
    assert bundle_difference(_SYNTHETIC_TRACKED, kept)["extra"] == ["apps/web/src/main.tsx"]


def test_an_exclusion_that_swallows_a_kept_file_shows_as_missing() -> None:
    kept = kept_files(_SYNTHETIC_TRACKED, ["apps/**", "docs/**", "README.md", "uv.lock"])
    assert bundle_difference(_SYNTHETIC_TRACKED, kept)["missing"] == ["uv.lock"]


def test_an_exclusion_that_swallows_api_shows_as_missing() -> None:
    kept = kept_files(_SYNTHETIC_TRACKED, ["apps/**", "docs/**", "README.md", "api/**"])
    assert bundle_difference(_SYNTHETIC_TRACKED, kept)["missing"] == [
        "api/cron/ingest.py",
        "api/index.py",
    ]


def test_a_directory_the_upload_ignores_is_not_in_the_bundle_though_unlisted() -> None:
    tracked = [*_SYNTHETIC_TRACKED, "specs/a.md"]
    alternatives = ["apps/**", "docs/**", "README.md"]
    assert "specs/a.md" in kept_files(tracked, alternatives)
    assert "specs/a.md" not in kept_files(tracked, alternatives, frozenset({"specs"}))


def test_the_real_exclude_value_leaves_api_and_the_two_kept_files_in_the_bundle() -> None:
    assert _bundle_files()


# ---------------------------------------------------------------------------------------------
# The dry run
# ---------------------------------------------------------------------------------------------

#: Runs inside the deployment-shaped interpreter, in isolated mode, from the copied bundle. Its
#: argument is JSON: the bundle root, the environment's site-packages root, and the snapshot
#: directories the repository holds. It prints one JSON object of what it saw.
_PROBE = r"""
import asyncio, json, sys
from pathlib import Path

bundle_root, expected_snapshots = Path(sys.argv[1]), sys.argv[2:]
# `-I` removed the working directory from the path; the runtime puts the bundle root on it itself.
sys.path.insert(0, str(bundle_root))

import api.analyze, api.cron.ingest, api.index

seen = {}
for name, module in (("api.index", api.index), ("api.analyze", api.analyze),
                     ("api.cron.ingest", api.cron.ingest)):
    seen[name] = module.__file__

import aoe2stats_knowledge, aoe2stats_api
seen["aoe2stats_api"] = aoe2stats_api.__file__
seen["aoe2stats_knowledge"] = aoe2stats_knowledge.__file__

from aoe2stats_knowledge import snapshot

seen["snapshot_directories"] = list(snapshot.list_snapshot_directories())
seen["snapshots_loaded"] = [s.directory for s in snapshot.load_all_snapshots()]
snapshot.verify_installed_snapshots()


async def call(app, method, path):
    sent = []
    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}
    async def send(message):
        sent.append(message)
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method,
             "scheme": "http", "path": path, "raw_path": path.encode(), "query_string": b"",
             "headers": [], "client": ("127.0.0.1", 1), "server": ("testserver", 80)}
    await app(scope, receive, send)
    status = next(m["status"] for m in sent if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return status, json.loads(body)


seen["ingest"] = asyncio.run(call(api.cron.ingest.app, "POST", "/api/cron/ingest"))
seen["analyze"] = asyncio.run(call(api.analyze.app, "POST", "/api/analyze"))
print(json.dumps(seen))
"""


@pytest.fixture(scope="module")
def deployment_venv(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The environment the builder installs, built the way it builds it: `uv sync --frozen
    --no-dev --no-editable` (research R2), into a temporary directory and never the workspace
    `.venv` this process runs in."""
    venv = tmp_path_factory.mktemp("deployment") / "venv"
    # The full parent environment: `uv` needs `HOME`/`XDG_CACHE_HOME` to find its caches, and
    # possibly proxy variables. `UV_PROJECT_ENVIRONMENT` is the one addition.
    sync = subprocess.run(
        ["uv", "sync", "--frozen", "--no-dev", "--no-editable"],
        cwd=_REPO_ROOT,
        env={**os.environ, "UV_PROJECT_ENVIRONMENT": str(venv)},
        capture_output=True,
        text=True,
        timeout=_SYNC_TIMEOUT_SECONDS,
    )
    assert sync.returncode == 0, (
        "`uv sync --frozen --no-dev --no-editable`, the builder's own install, failed against a "
        f"temporary environment:\n{sync.stdout}\n{sync.stderr}"
    )
    return venv


def _interpreter(venv: Path) -> Path:
    python = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    assert python.exists(), f"uv sync reported success but built no interpreter at {python}"
    return python


def test_the_bundle_imports_loads_its_data_and_refuses_unauthenticated_long_routes(
    deployment_venv: Path, tmp_path: Path
) -> None:
    # The bundle: exactly the tracked files `excludeFiles` keeps, copied into an empty directory.
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    for relative in _bundle_files():
        target = bundle / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_REPO_ROOT / relative, target)

    repository_snapshots = sorted(
        entry.name for entry in (_REPO_ROOT / _SNAPSHOTS_DIR).iterdir() if entry.is_dir()
    )
    assert repository_snapshots, "the repository holds no knowledge snapshot to compare against"

    python = _interpreter(deployment_venv)
    result = subprocess.run(
        [str(python), "-I", "-c", _PROBE, str(bundle), *repository_snapshots],
        cwd=bundle,
        # Only the entrypoint tests' configuration, nothing inherited: no developer file or
        # production value can reach the probe.
        env=_required_env(),
        capture_output=True,
        text=True,
        timeout=_PROBE_TIMEOUT_SECONDS,
    )
    assert result.returncode == 0, (
        "A function holding only the bundle's files and the builder's install cannot import, "
        f"load its data or answer:\n{result.stdout}\n{result.stderr}"
    )
    seen = json.loads(result.stdout.strip().splitlines()[-1])

    # The entrypoints come from the bundle, and the workspace packages from the environment:
    # a non-editable install holds a copy, so a file the wheel lacks is missing here.
    for module in ("api.index", "api.analyze", "api.cron.ingest"):
        assert Path(seen[module]).is_relative_to(bundle), (
            f"{module} was not imported from the bundle"
        )
    for module in ("aoe2stats_api", "aoe2stats_knowledge"):
        installed = Path(seen[module]).resolve()
        assert installed.is_relative_to(deployment_venv.resolve()), (
            f"{module} resolved to {installed}, not into the temporary environment: "
            "the install was editable, or the repository leaked onto the import path"
        )

    # Every snapshot the repository holds is packaged, and each loads and passes its digest check.
    assert seen["snapshot_directories"] == repository_snapshots
    assert sorted(seen["snapshots_loaded"]) == repository_snapshots

    ingest_status, ingest_body = seen["ingest"]
    assert ingest_status == 401
    assert ingest_body["error"]["code"] == "unauthorized"
    analyze_status, analyze_body = seen["analyze"]
    assert analyze_status == 401
    assert analyze_body["error"]["code"] == "not_authenticated"
