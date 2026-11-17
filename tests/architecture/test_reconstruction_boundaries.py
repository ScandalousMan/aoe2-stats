"""Boundary guard for the reconstruction package (T932, FR-002, FR-023, FR-028).

**What this guards.**

1. *No connection* (FR-023): the package imports no database, network, socket or object-store
   module, and none of the first-party packages that own one (storage, providers).
2. *No scheduled job* (FR-023): the package imports no scheduler, and no scheduled workflow or
   `vercel.json` cron/function names it.
3. *Not on the capture path* (FR-023, constitution I): nothing under the ingester, the providers
   or the cron handler imports `aoe2stats_reconstruction`.
4. *No input but the canonical stream and the knowledge base* (FR-002): the first-party imports
   are exactly `aoe2stats_reconstruction` itself, `aoe2stats_core.replay.events` (the canonical
   vocabulary) and `aoe2stats_knowledge`; the package also never reads files, the environment or
   the clock. Its own packaged `rules.toml` is read through `importlib.resources`, which is
   allowed: it is the package's code, not an input.
5. *Estimates are one-way* (FR-028): no module outside `estimates/` imports from `estimates/`.
   The directory may not exist yet; the check then holds vacuously.

Every detector has a contrast test feeding it a synthetic violation, so a green run on the real
tree is evidence of a clean tree and not of a detector that matches nothing. Scope is `src/`,
never `tests/`, the same line `test_import_graph.py` draws.
"""

from __future__ import annotations

import ast
import json
from collections.abc import Iterator
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PACKAGE = "aoe2stats_reconstruction"
_PACKAGE_SRC = _REPO_ROOT / "packages" / "reconstruction" / "src" / _PACKAGE
_ESTIMATES = "estimates"

_CAPTURE_PATH: tuple[Path, ...] = (
    _REPO_ROOT / "apps" / "ingester" / "src",
    _REPO_ROOT / "packages" / "providers" / "src",
    _REPO_ROOT / "api" / "cron",
)

_FORBIDDEN_CONNECTION_ROOTS = frozenset(
    {
        "sqlalchemy", "psycopg", "psycopg2", "asyncpg", "alembic", "socket", "ssl", "http",
        "urllib", "urllib3", "requests", "httpx", "aiohttp", "websockets", "ftplib", "smtplib",
        "boto3", "botocore", "s3fs", "grpc",
        "aoe2stats_storage", "aoe2stats_providers",
    }
)  # fmt: skip

_FORBIDDEN_SCHEDULER_ROOTS = frozenset(
    {"sched", "apscheduler", "schedule", "celery", "rq", "dramatiq", "crontab", "croniter"}
)

# FR-002: the only first-party modules the package may import, as dotted prefixes.
_ALLOWED_FIRST_PARTY_PREFIXES = (
    _PACKAGE,
    "aoe2stats_core.replay.events",
    "aoe2stats_knowledge",
)

# Ambient inputs: reading a file, the environment or the clock is an input that is not the stream.
_FORBIDDEN_CALLS = frozenset(
    {"open", "getenv", "read_text", "read_bytes", "now", "utcnow", "today", "time", "urlopen"}
)
_FORBIDDEN_ATTRIBUTES = frozenset({"environ"})


def _py_files(root: Path) -> Iterator[Path]:
    if root.is_file():
        yield root
    elif root.is_dir():
        yield from sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def _imported_modules(source: str) -> list[str]:
    """Absolute dotted names imported by `source`, including `from x import y` as `x`."""
    modules: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                modules.append(f"relative:{node.module or ''}")
            elif node.module:
                modules.append(node.module)
    return modules


def _has_root(module: str, roots: frozenset[str]) -> bool:
    return module.split(".")[0] in roots


def _connection_violations(source: str) -> list[str]:
    return [m for m in _imported_modules(source) if _has_root(m, _FORBIDDEN_CONNECTION_ROOTS)]


def _scheduler_violations(source: str) -> list[str]:
    return [m for m in _imported_modules(source) if _has_root(m, _FORBIDDEN_SCHEDULER_ROOTS)]


def _imports_package(source: str) -> list[str]:
    return [m for m in _imported_modules(source) if m.split(".")[0] == _PACKAGE]


def _input_import_violations(source: str) -> list[str]:
    bad: list[str] = []
    for module in _imported_modules(source):
        if module.startswith("relative:"):
            bad.append(module)  # absolute imports only, so the allow-list is checkable
        elif (module.split(".")[0].startswith("aoe2stats_") or module == "api") and not any(
            module == p or module.startswith(p + ".") for p in _ALLOWED_FIRST_PARTY_PREFIXES
        ):
            bad.append(module)
    return bad


def _is_packaged_resource_read(call: ast.Call) -> bool:
    """`resources.files(...).joinpath(...).read_text()`: the package's own data, not an input."""
    func = call.func
    if not (isinstance(func, ast.Attribute) and func.attr in {"read_text", "read_bytes"}):
        return False
    return "resources.files(" in ast.unparse(func.value)


def _ambient_input_violations(source: str) -> list[str]:
    bad: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if name in _FORBIDDEN_CALLS and not _is_packaged_resource_read(node):
                bad.append(f"call {name}")
        elif isinstance(node, ast.Attribute) and node.attr in _FORBIDDEN_ATTRIBUTES:
            bad.append(f"attribute {node.attr}")
    return bad


def _estimates_import_violations(relative_path: Path, source: str) -> list[str]:
    """Imports of `<package>.estimates` from a module that is not itself under `estimates/`."""
    if relative_path.parts and relative_path.parts[0] == _ESTIMATES:
        return []
    if relative_path.parts == (f"{_ESTIMATES}.py",):
        return []
    prefix = f"{_PACKAGE}.{_ESTIMATES}"
    bad: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            bad.extend(
                a.name for a in node.names if a.name == prefix or a.name.startswith(prefix + ".")
            )
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # `from . import estimates` / `from .estimates import x`
                if (node.module or "").split(".")[0] == _ESTIMATES or any(
                    a.name == _ESTIMATES for a in node.names if not node.module
                ):
                    bad.append(f"relative {node.module or ''} {[a.name for a in node.names]}")
            elif node.module == prefix or (node.module or "").startswith(prefix + "."):
                bad.append(node.module or "")
            elif node.module == _PACKAGE and any(a.name == _ESTIMATES for a in node.names):
                bad.append(f"{_PACKAGE}.{_ESTIMATES}")
    return bad


def _scheduled_surface_mentions() -> list[str]:
    """Scheduled workflows and vercel.json entries that name the package."""
    needles = (_PACKAGE, "packages/reconstruction")
    hits: list[str] = []
    for wf in sorted((_REPO_ROOT / ".github" / "workflows").glob("*.yml")):
        text = wf.read_text(encoding="utf-8")
        if "schedule:" in text and any(n in text for n in needles):
            hits.append(wf.name)
    vercel = json.loads((_REPO_ROOT / "vercel.json").read_text(encoding="utf-8"))
    for cron in vercel.get("crons", []):
        if any(n in json.dumps(cron) for n in needles):
            hits.append(f"vercel.json cron {cron}")
    return hits


def _package_sources() -> list[tuple[Path, str]]:
    return [(p, p.read_text(encoding="utf-8")) for p in _py_files(_PACKAGE_SRC)]


# --- Real tree ---------------------------------------------------------------------------------


def test_package_tree_is_found() -> None:
    assert (_PACKAGE_SRC / "__init__.py").is_file()
    assert len(_package_sources()) >= 5  # a moved package must not turn every check vacuous


def test_package_opens_no_connection() -> None:
    found = {
        str(p.relative_to(_REPO_ROOT)): _connection_violations(s) for p, s in _package_sources()
    }
    assert {k: v for k, v in found.items() if v} == {}


def test_package_registers_no_scheduled_job() -> None:
    found = {
        str(p.relative_to(_REPO_ROOT)): _scheduler_violations(s) for p, s in _package_sources()
    }
    assert {k: v for k, v in found.items() if v} == {}
    assert _scheduled_surface_mentions() == []


def test_capture_path_never_imports_the_package() -> None:
    assert any(any(_py_files(root)) for root in _CAPTURE_PATH)  # the scan is not vacuous
    found: dict[str, list[str]] = {}
    for root in _CAPTURE_PATH:
        for path in _py_files(root):
            hits = _imports_package(path.read_text(encoding="utf-8"))
            if hits:
                found[str(path.relative_to(_REPO_ROOT))] = hits
    assert found == {}


def test_package_reads_only_the_stream_and_the_knowledge_base() -> None:
    imports = {
        str(p.relative_to(_REPO_ROOT)): _input_import_violations(s) for p, s in _package_sources()
    }
    assert {k: v for k, v in imports.items() if v} == {}
    ambient = {
        str(p.relative_to(_REPO_ROOT)): _ambient_input_violations(s) for p, s in _package_sources()
    }
    assert {k: v for k, v in ambient.items() if v} == {}


def test_nothing_outside_estimates_imports_estimates() -> None:
    found: dict[str, list[str]] = {}
    for path, source in _package_sources():
        hits = _estimates_import_violations(path.relative_to(_PACKAGE_SRC), source)
        if hits:
            found[str(path.relative_to(_REPO_ROOT))] = hits
    assert found == {}


# --- Contrast: each detector fails on a synthetic violation ------------------------------------


def test_contrast_connection_detector_sees_a_connection() -> None:
    assert _connection_violations("import sqlalchemy\nfrom urllib.request import urlopen\n") == [
        "sqlalchemy",
        "urllib.request",
    ]
    assert _connection_violations("from aoe2stats_storage.db import engine\n")
    assert _connection_violations("import json\nfrom pydantic import BaseModel\n") == []


def test_contrast_scheduler_detector_sees_a_scheduler() -> None:
    assert _scheduler_violations("import sched\nfrom apscheduler.schedulers import x\n")
    assert _scheduler_violations("import tomllib\n") == []


def test_contrast_capture_detector_sees_an_import() -> None:
    assert _imports_package("from aoe2stats_reconstruction.settle import x\n")
    assert _imports_package("import aoe2stats_reconstruction\n")
    assert _imports_package("from aoe2stats_core import x\n") == []


def test_contrast_input_detector_sees_a_foreign_input() -> None:
    assert _input_import_violations("from aoe2stats_core.replay.analysis import x\n")
    assert _input_import_violations("from aoe2stats_core.truth import x\n")
    assert _input_import_violations("from . import orders\n")
    assert _input_import_violations("from aoe2stats_core.replay.events import X\n") == []
    assert _input_import_violations("from aoe2stats_knowledge.query import X\n") == []
    assert _ambient_input_violations("import os\nx = os.environ['A']\n")
    assert _ambient_input_violations("x = open('f').read()\n")
    assert _ambient_input_violations("from pathlib import Path\nPath('f').read_text()\n")
    assert _ambient_input_violations("from datetime import datetime\ndatetime.now()\n")
    assert _ambient_input_violations("x = 1 + 1\n") == []
    packaged = "resources.files('p').joinpath('r').read_text('utf-8')\n"
    assert _ambient_input_violations(packaged) == []


def test_contrast_estimates_detector_sees_every_import_shape() -> None:
    outside = Path("settle.py")
    for source in (
        "from aoe2stats_reconstruction.estimates import x\n",
        "from aoe2stats_reconstruction.estimates.idle import x\n",
        "import aoe2stats_reconstruction.estimates\n",
        "from aoe2stats_reconstruction import estimates\n",
        "from .estimates import x\n",
        "from . import estimates\n",
    ):
        assert _estimates_import_violations(outside, source), source
    # Inside estimates/ the import is the estimate's own, and a sibling import is not an estimate.
    inside = Path("estimates") / "idle.py"
    assert _estimates_import_violations(inside, "from .base import x\n") == []
    assert (
        _estimates_import_violations(inside, "from aoe2stats_reconstruction.estimates import x\n")
        == []
    )
    assert _estimates_import_violations(outside, "from . import orders\n") == []
    assert _estimates_import_violations(outside, "from .state import Settlement\n") == []
