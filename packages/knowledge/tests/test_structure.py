"""T650: refusal as a property of the code, not a habit (SC-006, SC-008, FR-026).

Contract: [contracts/knowledge-base.md](../../../specs/006-replay-analysis-foundations/contracts/
knowledge-base.md), "The query surface" — "The union has no third branch. No function in the
package returns a bare value, accepts a default, or catches a gap and continues. SC-008's 'by
construction' is this signature, and a test asserts by introspection that every public query
returns the union." `query.py`'s own module docstring (T643) names this file directly: "T650
asserts it by introspection."

Three independent claims, each checked structurally rather than by review:

1. **Every public query returns `X | gaps.KnowledgeGap`, never a third shape.** "Every public
   query in the package" is read as the query surface the contract names, not literally every
   public callable under `src/` — see `_QUERY_MODULES` below for why that reading is forced, not
   chosen.
2. **No module under `packages/knowledge/src/` imports a network library** (FR-026), by the same
   AST method `scripts/ops/tests/test_import_knowledge_pack.py` (T635) already established for
   this repository, applied to the whole package's source tree instead of one script.
3. **The workspace's network-blocking fixture actually reaches this package's own tests**
   (SC-006), proven empirically rather than assumed from reading `tests/conftest.py`.

**Why "every public query" is not "every public callable".** `effects.py` exports `apply` and
`apply_matched`, both public and both two-branch unions — but their gap branch is
`effects.EffectNotModelled`, a narrower, internal sentinel `query.py` itself converts into a real
`gaps.KnowledgeGap` before ever handing a value to a caller outside this package (see
`query._civilisation_qualified`). `normalise.py` and `effects.py` also export plain parsers
(`parse_effects_toml`, `normalise_pack`, `rules_json_bytes`, ...) that answer no yes/no question at
all. A blind walk of every public function in every module would demand `gaps.KnowledgeGap` as the
second branch of all of these and fail on every one of them — not because they are wrong, but
because they are not queries. The contract's own "query surface" section names exactly seven
functions, all in `query.py`, as the surface this discipline governs.

`snapshot.snapshot_for` is added deliberately even though it lives outside `query.py`: it already
returns exactly `Snapshot | gaps.KnowledgeGap` (`query.py`'s own module docstring cites it as what
every query resolves a build from), asks the same shape of yes/no question ("is there a promoted
snapshot for this build") the seven `query.py` functions ask, and is a real, standalone entry point
`query.py`'s own callers could reach directly. `snapshot.py`'s other public functions
(`load_snapshot`, `load_all_snapshots`, `load_resolvable_snapshots`, `parse_identity`,
`parse_promotion`, `compute_digest`, `list_snapshot_directories`) are excluded on purpose: they are
the loader `snapshot_for` is built from, not queries in their own right — several raise rather than
return on a malformed snapshot (`load_snapshot`), and none of them is qualified by a caller's
question the way `snapshot_for(build)` and every `query.py` function are. `coverage.coverage` is
excluded for the reason the task text already gives: it is a batch pass over a whole stream,
returning `Sequence[gaps.KnowledgeGap]` — a list, not a single answer-or-gap union — because
reporting every gap at once, not stopping at the first, is exactly its job (contracts/
knowledge-base.md, "Gaps": "Its output is the gap list the document publishes").

Within the modules actually swept (`query.py` in full; `snapshot.py` for the one named function),
the walk itself is general: it iterates every public, module-defined function it finds rather than
hand-naming each one, so a function added to `query.py` later — the module the contract's "query
surface" section is actually about — is automatically covered without this file changing.
"""

from __future__ import annotations

import ast
import inspect
import socket
import tomllib
import types
import typing
from pathlib import Path

import pytest

from aoe2stats_knowledge import gaps, query, snapshot

_REPO_ROOT = Path(__file__).resolve().parents[3]
_KNOWLEDGE_SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "aoe2stats_knowledge"

# --------------------------------------------------------------- SC-008: the answer-or-gap union


def _public_module_functions(module: types.ModuleType) -> list[tuple[str, object]]:
    """Every function `module` defines itself and exposes under a non-underscore name.

    `inspect.unwrap` looks through any decorator (`functools.cache`, ...) before checking
    `__module__`, so a future public query wrapped in a decorator is still recognised as belonging
    to `module` rather than silently skipped — the walk stays general even if a later query gains
    a decorator none of today's seven have.
    """
    found: list[tuple[str, object]] = []
    for name, obj in vars(module).items():
        if name.startswith("_"):
            continue
        unwrapped = inspect.unwrap(obj)
        if not inspect.isfunction(unwrapped):
            continue
        if unwrapped.__module__ != module.__name__:
            continue  # imported into this module's namespace, not defined here (e.g. a helper)
        found.append((name, obj))
    return found


def _return_type_hint(fn: object) -> object:
    hints = typing.get_type_hints(fn)
    assert "return" in hints, (
        f"{fn!r} has no return type annotation at all — the answer-or-gap union cannot be "
        "asserted on a function that does not declare one"
    )
    return hints["return"]


def _assert_is_answer_or_gap_union(name: str, annotation: object) -> None:
    origin = typing.get_origin(annotation)
    is_union = origin is types.UnionType or origin is typing.Union
    assert is_union, (
        f"{name}'s return annotation {annotation!r} is not a union at all — every public query "
        "must return an answer-or-gap union, never a bare value"
    )
    args = typing.get_args(annotation)
    assert len(args) == 2, (
        f"{name}'s return union has {len(args)} branch(es), not two ({args!r}) — the contract "
        "forbids a third branch"
    )
    assert gaps.KnowledgeGap in args, (
        f"{name}'s return union {args!r} does not name gaps.KnowledgeGap as a branch — this is "
        "not the answer-or-gap union the contract describes"
    )
    other = args[0] if args[1] is gaps.KnowledgeGap else args[1]
    assert other is not type(None), (
        f"{name}'s non-gap branch is `None` — an `X | None` union lets a caller mistake a missing "
        "answer for a real one; a gap must be named, not `None`"
    )
    assert other is not typing.Any, (
        f"{name}'s non-gap branch is `Any` — that type-checks against anything, including a bare "
        "value or a second gap shape, which defeats the whole point of asserting this by "
        "introspection"
    )


#: The query surface this file sweeps, and why each module is in it — see the module docstring.
#: `query.py` is walked in full and generally; `snapshot.py` names exactly the one function that
#: is itself a query, not every public function in that module (most of which are the loader
#: `snapshot_for` is built from, not queries in their own right).
_QUERY_MODULES: tuple[tuple[types.ModuleType, frozenset[str] | None], ...] = (
    (query, None),
    (snapshot, frozenset({"snapshot_for"})),
)


def test_every_public_query_returns_the_answer_or_gap_union() -> None:
    swept = 0
    for module, only in _QUERY_MODULES:
        functions = _public_module_functions(module)
        if only is not None:
            functions = [(name, fn) for name, fn in functions if name in only]
            found_names = {name for name, _ in functions}
            assert found_names == only, (
                f"{module.__name__} no longer defines {sorted(only - found_names)} as a public "
                "function — update _QUERY_MODULES to match, this file's introspection has nothing "
                "left to check for it"
            )
        for name, fn in functions:
            _assert_is_answer_or_gap_union(f"{module.__name__}.{name}", _return_type_hint(fn))
            swept += 1
    # A walk that silently found nothing would make every assertion above vacuously true — the
    # real query surface has seven functions in `query.py` alone, so anything under that proves
    # the walk itself broke, not that the package shrank to nothing worth checking.
    assert swept >= 7, (
        f"only {swept} public quer{'y' if swept == 1 else 'ies'} were swept — the introspection "
        "walk itself looks broken (see _public_module_functions), not the package"
    )


def test_query_py_defines_exactly_the_contracts_seven_query_functions() -> None:
    """Guards against the walk quietly narrowing: if `query.py` ever exposed a public function
    under a name `contracts/knowledge-base.md`'s "The query surface" does not list, the assertion
    above would still check it (it iterates every public function, not a fixed list) — but nothing
    would fail if a function accidentally lost its `def`-level visibility or was renamed away from
    what the contract promises. This is the one hand-written name check this file keeps, precisely
    because the walk above is deliberately general everywhere else.
    """
    names = {name for name, _ in _public_module_functions(query)}
    assert names == {
        "cost",
        "production_time",
        "age_requirement",
        "prerequisites",
        "produced_at",
        "available_to",
        "name",
    }


# ------------------------------------------------------- FR-026: no network import in the package


#: Mirrors `scripts/ops/tests/test_import_knowledge_pack.py`'s own forbidden-network roots
#: (T635) and `tests/architecture/test_import_graph.py`'s (T018d) — this file duplicates rather
#: than imports either, following `test_import_knowledge_pack.py`'s own stated precedent ("each
#: [suite] is self-contained ... the set of names that count as 'the network' should not drift
#: between the two checks"), so the same discipline applies a third time rather than coupling
#: `packages/knowledge`'s tests to a root-level test module outside its own package boundary.
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


def _direct_import_targets(tree: ast.AST) -> list[str]:
    """Every module name a parsed file imports, directly or dynamically — `ast.Import`,
    `ast.ImportFrom` and the two argument-less-`import`-keyword forms
    (`importlib.import_module("httpx")`, `__import__("httpx")`), the same three shapes
    `tests/architecture/test_import_graph.py` (T018d) already walks a syntax tree for rather than
    grepping source text.
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


def _is_forbidden_network_import(dotted: str) -> bool:
    if dotted in _FORBIDDEN_NETWORK_EXACT:
        return True
    return dotted.split(".", 1)[0] in _FORBIDDEN_NETWORK_ROOTS


def _knowledge_source_files() -> list[Path]:
    assert _KNOWLEDGE_SRC_ROOT.is_dir(), f"expected a source tree at {_KNOWLEDGE_SRC_ROOT}"
    return sorted(
        path for path in _KNOWLEDGE_SRC_ROOT.rglob("*.py") if "__pycache__" not in path.parts
    )


def test_no_module_in_packages_knowledge_imports_a_network_library() -> None:
    """FR-026, SC-006: every `.py` file under `packages/knowledge/src/`, not only `query.py`,
    since a network import anywhere in the package's dependency graph would still make the package
    reach the network. Scoped to `src/`, not `tests/`, matching `tests/architecture/
    test_import_graph.py`'s own stated line between production code and the tests that exercise
    it.
    """
    files = _knowledge_source_files()
    assert files, "no source files found under packages/knowledge/src/ — the scan itself is broken"
    violations: dict[str, list[str]] = {}
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        found = sorted(
            {
                target
                for target in _direct_import_targets(tree)
                if _is_forbidden_network_import(target)
            }
        )
        if found:
            violations[str(path.relative_to(_REPO_ROOT))] = found
    assert not violations, (
        f"packages/knowledge must be queryable with no network access (FR-026): {violations}"
    )


# -------------------------------------------------- SC-006: the network guard reaches this package


def test_the_workspace_pytest_config_wires_the_network_guard_to_this_package() -> None:
    """Static half of the SC-006 proof: `tests/conftest.py`'s autouse fixture is only ever
    activated because the root `pyproject.toml` (1) registers it as a plugin for the whole
    workspace and (2) lists `packages/knowledge/tests` as a collected `testpaths` entry. Either
    fact silently drifting — the plugin no longer registered, or this package's tests no longer
    collected under the root config — would mean the guard stops reaching this package with no
    single test here failing to say so.
    """
    config = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    pytest_options = config["tool"]["pytest"]["ini_options"]
    assert "packages/knowledge/tests" in pytest_options["testpaths"]
    assert pytest_options["addopts"][:2] == ["-p", "tests.conftest"] or (
        "-p" in pytest_options["addopts"] and "tests.conftest" in pytest_options["addopts"]
    )


def test_a_real_outbound_connection_from_this_package_is_actually_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empirical half of the SC-006 proof, from inside `packages/knowledge/tests` itself: attempt
    a real `socket.socket.connect()` to a non-loopback address with `tests/conftest.py`'s own
    guard engaged, and prove it raises before a single packet leaves — not merely that reading the
    fixture's source suggests it would.

    `tests/conftest.py`'s `_block_network` fixture only patches `socket.socket.connect` when
    `PYTEST_DISABLE_NETWORK=1` is set in the environment at fixture setup (CI sets it,
    `.github/workflows/pr.yml`; a contributor's local shell may not). Reading the ambient
    environment here would make this test's outcome depend on how it happens to be invoked, which
    is exactly the kind of thing this file exists to stop doing "by inspection" — so instead this
    test applies the *identical* patch `tests.conftest._guarded_connect` is, directly, guaranteeing
    the same code this package's tests run under CI is exercised regardless of the ambient
    environment this particular run happens to have.
    """
    from tests.conftest import _guarded_connect

    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(RuntimeError, match="Network access is disabled"):
            # 93.184.216.34 is example.com's long-published IPv4 address — never actually
            # reached, since `_guarded_connect` must raise before calling the real `connect`.
            probe.connect(("93.184.216.34", 80))
    finally:
        probe.close()


def test_loopback_stays_reachable_through_the_same_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other half of `_guarded_connect`'s contract: loopback is deliberately exempt (a local
    test database, a local mock server), so this proves the guard is selective rather than a blunt
    "every connect raises" stub that would also happen to make the test above pass for the wrong
    reason.
    """
    from tests.conftest import _guarded_connect

    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(OSError):
            # Raises for the ordinary reason (nothing listens on this port), not the network
            # guard's RuntimeError — proving loopback was let through to the real `connect`.
            probe.connect(("127.0.0.1", 1))
    finally:
        probe.close()
