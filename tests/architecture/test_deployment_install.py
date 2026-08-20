"""The check T014d adds: does a plain `uv sync` at the repository root install what
`api/index.py` and `api/cron/ingest.py` actually import (ADR-0002, constitution XII)?

**The defect this guards against.** The first real deployment failed both platform functions at
cold start: `api/index.py` raised `ModuleNotFoundError: No module named 'aoe2stats_api'`,
`api/cron/ingest.py` raised the same for `pydantic` — an ordinary third-party dependency, which
meant *nothing at all* had been installed, not merely the workspace members. The cause was the
root `pyproject.toml`: `[tool.uv] package = false` and no `[project.dependencies]`, so a bare
`uv sync` (the resolution path `docs/adr/0002-hosting.md` documents the Vercel Python runtime as
taking) had nothing reachable from the root project to install and left the environment holding
only the shared dev toolchain. The fix declared `aoe2stats-api` and `aoe2stats-ingester` — the two
workspace packages the platform entrypoints import — as root dependencies, `workspace = true`
sourced, so `uv sync`'s ordinary dependency walk pulls in both and everything they in turn depend
on (`aoe2stats-storage`, `fastapi`, `pydantic-settings`, ...).

**Why this survived T014c, an adversarial review and a green CI.** `apps/api/tests/
test_index_entrypoint.py` and `test_cron_ingest_entrypoint.py` already import `api.index` and
`api.cron.ingest` — but always inside the environment `uv sync --all-packages --dev`
(`.github/workflows/pr.yml`) builds, which installs every workspace member regardless of whether
the root project depends on it. A Python function's imports are only exercised at invocation, not
at build time, so nothing short of building the environment the way the deployment builds it and
then importing would have caught this. `pyproject.toml`'s mypy `files` list excludes `api/`
entirely, and `tests/architecture/test_import_graph.py` (T018d) checks what the two platform
entrypoints are imported *by* (nothing under `apps/`/`packages/`/`infra/`, constitution XII) — a
different claim from whether they can themselves be imported in a deployment-shaped environment.
This module is the missing third check.

**Method.** `uv sync --no-dev`, exactly as the standard resolution path would, into a throwaway
environment (`UV_PROJECT_ENVIRONMENT` pointed at `tmp_path`, never the shared workspace `.venv`
`uv run pytest` itself runs in) — `--no-dev` because the dev toolchain (`ruff`, `mypy`, `pytest`,
`alembic`) is never installed by the platform's Python function builder either, and its presence
must not be able to paper over a missing runtime dependency. Then that environment's own
interpreter, not the one running this test, imports both platform modules — the same separate-
process shape the two functions are actually invoked in. `cwd` is the repository root: neither
Vercel's runtime nor this test relies on `PYTHONPATH`, both rely on the entrypoint's own directory
being on `sys.path`, which `python -c` already gives for free via the empty `sys.path[0]`.

**What only a real deployment confirms.** This proves the *standard `uv` resolution path* now
installs the right packages and that both modules import cleanly against exactly that set — it
does not exercise Vercel's own Python builder, its exact install invocation, its 500 MB bundle
limit, or its filesystem-routing precedence between the two entrypoints (`api/index.py`'s
docstring). Those remain unverified until the next deployment.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PLATFORM_MODULES = ("api.index", "api.cron.ingest")


def test_a_plain_uv_sync_installs_what_the_platform_entrypoints_import(tmp_path: Path) -> None:
    deployment_venv = tmp_path / "deployment-shaped-venv"

    # The full parent environment, not a hand-picked subset: `uv` needs `HOME`/`XDG_CACHE_HOME`
    # to find its package and Python-toolchain cache, and possibly proxy variables, none of which
    # this test should have to enumerate. `UV_PROJECT_ENVIRONMENT` is the one addition — it is
    # what keeps `uv sync` from touching the shared workspace `.venv` this very test process runs
    # in, and is exactly the throwaway-environment behaviour being verified.
    sync_env = {**os.environ, "UV_PROJECT_ENVIRONMENT": str(deployment_venv)}

    sync = subprocess.run(
        ["uv", "sync", "--no-dev"],
        cwd=_REPO_ROOT,
        env=sync_env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert sync.returncode == 0, (
        "`uv sync --no-dev` — the standard resolution path a plain deployment build takes — "
        f"failed against a throwaway environment:\n{sync.stdout}\n{sync.stderr}"
    )

    python = deployment_venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    assert python.exists(), f"uv sync reported success but built no interpreter at {python}"

    imports = "; ".join(f"import {module}" for module in _PLATFORM_MODULES)
    result = subprocess.run(
        [str(python), "-c", f"{imports}\nprint('ok')"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0 and result.stdout.strip() == "ok", (
        "A plain `uv sync --no-dev` at the repository root does not install what "
        f"{' and '.join(_PLATFORM_MODULES)} import — the exact defect T014d fixed:\n"
        f"{result.stdout}\n{result.stderr}"
    )
