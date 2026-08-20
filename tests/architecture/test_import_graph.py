"""Architecture guards for the import-graph rows of `plan.md`'s constitution table (T018d).

`apps/api/tests/test_engine_isolation.py` built the guard for principle V — importing the FastAPI
app must never load the replay engine — after that exact shape of dependency (`apps/api` importing
`aoe2stats_ingester.run` at module scope) passed tests, CI and five commits unnoticed (T018c). Two
more rows of that table are the same kind of claim — assertions about what imports what, written as
prose that nothing checked:

- **III** (`apps/*` and `packages/core` make no outbound calls): a provider is the only thing
  allowed to hold a network client. If a module outside `packages/providers` starts calling out
  directly, `provider_calls`, the rate limiter and the retry policy all stop applying to that call.
- **XII** (portable by construction): nothing under `apps/`, `packages/` or `infra/` may import
  `api/index.py` or `api/cron/ingest.py`, the two files `plan.md` allows to be platform-shaped. An
  import from either would mean the phase-2 move off Vercel has to touch more than configuration.

**This module does not cover the constitution table.** The other nine rows — I (capture priority),
II (Python backend), IV (raw is sacred), VI (tokens first), VII (visual tests), VIII (no secrets in
the clear), IX (GDPR by design), X (no game assets), XI (English) — are process and design claims: a
`product-designer` spec was written, a `reviewer` pass happened, nightly visual regression runs, no
asset was copied in. None of them reduces to an import-graph test, or to any other kind of automated
test; a green run here says nothing about them. Only III and V (elsewhere) and XII are checked by
code, because only those three are actually claims about what imports what.

**Method — the import graph, not source text.** Each check parses every module under its roots with
`ast.parse` and inspects the parsed `Import`/`ImportFrom`/`Call` nodes, not the raw text: `import
httpx as h`, `from httpx import AsyncClient`, and `importlib.import_module("httpx")` /
`__import__("httpx")` are all found by walking the syntax tree, which a `grep import httpx` misses
in three different ways (an alias, a `from`-import naming an attribute instead of the module, and a
dynamic import with no `import` keyword at all). Each module's own direct imports are what gets
checked — never the transitive closure of `sys.modules` after importing it — because `packages/
storage`'s object store legitimately imports `boto3` to reach R2 (constitution XII, plan.md's own
package boundary) and `apps/api` legitimately depends on `aoe2stats-storage` (`deps.py`); a
closure-based check would flag that legitimate transitive dependency every single time the API is
imported. A direct-imports-per-file check applied to *every* file under a guarded root, not only its
entry points, still catches an indirect import through an in-tree helper: the helper is a file under
that same root too, and gets scanned on its own.

**Scope — `src/`, not `tests/`.** Both checks below walk `src/` trees only. `apps/api/tests/
test_index_entrypoint.py` and `test_cron_ingest_entrypoint.py` (T014c, T018) import `api.index` and
`api.cron.ingest` on purpose — they are the tests that prove those two files re-export the real
application unchanged — and the workspace's own `pyproject.toml` already draws the same src-vs-tests
line for mypy's strict gate ("Test suites ... are covered by ruff but not by this strict gate").
A test importing a platform entrypoint to assert what it does is not the dependency principle XII
forbids; a production module that could not run without Vercel's filesystem routing is.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_Predicate = Callable[[str], bool]

# --- Walking the import graph --------------------------------------------------------------------


def _python_files(root: Path) -> list[Path]:
    """Every `.py` file under `root`, or nothing if `root` does not exist (a package's `src/` for
    a language other than Python — there is none today, but nothing here should break if there
    ever is).
    """
    if not root.is_dir():
        return []
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def _direct_import_targets(tree: ast.AST) -> list[str]:
    """Every module name one `ast.parse`d file imports directly, however it does it.

    `ast.Import` covers `import httpx` and `import httpx as h` alike — `alias.name` is `"httpx"`
    regardless of `alias.asname`. `ast.ImportFrom` covers `from httpx import AsyncClient` — the
    module itself (`"httpx"`) is a target, and so is the dotted `module.name` form, which is what
    turns `from urllib import request` into the same `"urllib.request"` a plain `import urllib.
    request` would produce. A relative `from . import x` (`node.module is None`) names no
    third-party module and is skipped — it can only ever resolve to something already inside the
    package being walked, which is scanned as its own file regardless.

    `importlib.import_module("httpx")` and `__import__("httpx")` are the two dynamic forms that
    have no `import` keyword at all and so cannot be found by any text search: both are ordinary
    `ast.Call` nodes once parsed, with a string literal as their first argument.
    """
    targets: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            targets.append(node.module)
            targets.extend(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Call):
            func = node.func
            is_dynamic_import = (isinstance(func, ast.Name) and func.id == "__import__") or (
                isinstance(func, ast.Attribute)
                and func.attr == "import_module"
                and isinstance(func.value, ast.Name)
                and func.value.id == "importlib"
            )
            if not is_dynamic_import or not node.args:
                continue
            first_arg = node.args[0]
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                targets.append(first_arg.value)
    return targets


def _forbidden_imports_in(path: Path, *, is_forbidden: _Predicate) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return sorted({target for target in _direct_import_targets(tree) if is_forbidden(target)})


def _display_path(path: Path) -> str:
    """`path` relative to the repository root when it is under it (every real guard root is);
    the absolute path otherwise, so the synthetic `tmp_path` trees the tests below build against
    still produce a readable key instead of raising `ValueError`.
    """
    if path.is_relative_to(_REPO_ROOT):
        return str(path.relative_to(_REPO_ROOT))
    return str(path)


def _violations_under(roots: list[Path], *, is_forbidden: _Predicate) -> dict[str, list[str]]:
    violations: dict[str, list[str]] = {}
    for root in roots:
        for path in _python_files(root):
            found = _forbidden_imports_in(path, is_forbidden=is_forbidden)
            if found:
                violations[_display_path(path)] = found
    return violations


# --- Principle III — apps/* and packages/core make no outbound calls ------------------------------
# A network client below any of these root names, at any depth, reaches the network: `httpx.
# AsyncClient`, `requests.get`, `aiohttp.ClientSession`, a raw `socket`, ... `http` and `urllib`
# are deliberately *not* listed as roots — `urllib.parse` and `http.server`'s type-only usages are
# ordinary stdlib code with no network effect — only their actual client submodules are forbidden.
_FORBIDDEN_NETWORK_ROOTS = frozenset(
    {
        "httpx",
        "requests",
        "aiohttp",
        "urllib3",
        "socket",
        "websockets",
        "websocket",
        "grpc",
        "pycurl",
    }
)
_FORBIDDEN_NETWORK_EXACT = frozenset({"http.client", "urllib.request"})


def _is_forbidden_network_import(dotted: str) -> bool:
    if dotted in _FORBIDDEN_NETWORK_EXACT:
        return True
    return dotted.split(".", 1)[0] in _FORBIDDEN_NETWORK_ROOTS


def test_apps_and_packages_core_reach_the_network_only_through_providers() -> None:
    """Guards plan.md's constitution-III row: "`apps/*` and `packages/core` make no outbound
    calls." `packages/storage` is deliberately excluded — its object store legitimately imports
    `boto3` to reach R2, which is this project's own storage, not a third-party data source (T018d
    task text). `packages/providers` is excluded too: it is the one place a network client is
    allowed to live at all.
    """
    roots = [
        _REPO_ROOT / "apps" / "api" / "src",
        _REPO_ROOT / "apps" / "ingester" / "src",
        _REPO_ROOT / "packages" / "core" / "src",
    ]
    violations = _violations_under(roots, is_forbidden=_is_forbidden_network_import)
    assert not violations, (
        "apps/* and packages/core must reach the network only through packages/providers "
        f"(constitution III, plan.md's constitution-III row): {violations}"
    )


# --- Principle XII — portable by construction ----------------------------------------------------
# `api/index.py` and `api/cron/ingest.py` are the two files plan.md allows to be platform-shaped.
# Reachable as `api.index` / `api.cron.ingest` because the root pyproject's `pythonpath = ["."]`
# puts the repository root on `sys.path` (the same mechanism their own tests rely on).
_PLATFORM_ENTRYPOINT_MODULES = frozenset({"api.index", "api.cron.ingest"})


def _is_forbidden_platform_import(dotted: str) -> bool:
    return dotted in _PLATFORM_ENTRYPOINT_MODULES


def test_nothing_under_apps_packages_or_infra_imports_a_platform_entrypoint() -> None:
    """Guards plan.md's constitution-XII row: neither `api/index.py` nor `api/cron/ingest.py` may
    be imported from anywhere the phase-2 VPS move has to carry along, so that move stays a
    configuration change (`vercel.json`, the cron schedule) rather than a rewrite.
    """
    roots = [
        _REPO_ROOT / "apps" / "api" / "src",
        _REPO_ROOT / "apps" / "ingester" / "src",
        _REPO_ROOT / "packages" / "core" / "src",
        _REPO_ROOT / "packages" / "providers" / "src",
        _REPO_ROOT / "packages" / "replay-engine" / "src",
        _REPO_ROOT / "packages" / "storage" / "src",
        _REPO_ROOT / "infra",
    ]
    violations = _violations_under(roots, is_forbidden=_is_forbidden_platform_import)
    assert not violations, (
        "apps/, packages/ and infra/ must never import a platform-shaped entrypoint "
        f"(constitution XII, plan.md's constitution-XII row): {violations}"
    )


# --- Proving the detector itself, not only today's clean tree -------------------------------------
# The two tests above are green today because nothing violates either rule yet, which is the state
# an architecture guard is supposed to hold a codebase in — not evidence the guard would notice a
# regression. These exercise `_direct_import_targets` and the two predicates directly, against
# synthetic sources built to hit exactly the three ways a text search misses an import (alias,
# from-import, dynamic import) and to confirm ordinary stdlib usage that merely shares a package
# name is not mistaken for one.


def _targets_in(source: str) -> list[str]:
    return _direct_import_targets(ast.parse(source))


def test_direct_import_targets_finds_a_plain_import() -> None:
    assert "httpx" in _targets_in("import httpx\n")


def test_direct_import_targets_finds_an_aliased_import() -> None:
    assert "httpx" in _targets_in("import httpx as h\n")


def test_direct_import_targets_finds_a_from_import() -> None:
    assert "httpx" in _targets_in("from httpx import AsyncClient\n")


def test_direct_import_targets_finds_a_from_import_of_a_dotted_submodule() -> None:
    assert "urllib.request" in _targets_in("from urllib import request\n")


def test_direct_import_targets_finds_importlib_import_module() -> None:
    assert "httpx" in _targets_in("import importlib\nimportlib.import_module('httpx')\n")


def test_direct_import_targets_finds_dunder_import() -> None:
    assert "httpx" in _targets_in("__import__('httpx')\n")


def test_direct_import_targets_ignores_a_relative_import() -> None:
    assert _targets_in("from . import helper\n") == []


def test_forbidden_network_import_flags_a_submodule_of_a_forbidden_root() -> None:
    assert _is_forbidden_network_import("httpx._client")


def test_forbidden_network_import_does_not_flag_unrelated_urllib_and_http_submodules() -> None:
    assert not _is_forbidden_network_import("urllib.parse")
    assert not _is_forbidden_network_import("http.server")


def test_forbidden_network_import_flags_the_two_stdlib_client_exceptions() -> None:
    assert _is_forbidden_network_import("http.client")
    assert _is_forbidden_network_import("urllib.request")


def test_violations_under_catches_an_indirect_import_through_an_in_tree_helper(
    tmp_path: Path,
) -> None:
    """The scan is per-file, not per-entry-point: a module that never imports `httpx` itself but
    imports a same-tree helper that does is still caught, because the helper is scanned too.
    """
    package = tmp_path / "some_app"
    package.mkdir()
    (package / "helper.py").write_text("import httpx\n")
    (package / "caller.py").write_text("from some_app import helper\n")

    violations = _violations_under([tmp_path], is_forbidden=_is_forbidden_network_import)

    assert any(key.endswith("helper.py") for key in violations)
    assert not any(key.endswith("caller.py") for key in violations)
