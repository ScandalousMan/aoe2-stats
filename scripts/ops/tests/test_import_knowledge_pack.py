"""Tests for `scripts/ops/import_knowledge_pack.py` (research.md D3, T635).

Entirely network-free and filesystem-only: a synthetic `--source-checkout` under `tmp_path` stands
in for a real `SiegeEngineers/aoe2techtree` clone, and a synthetic destination directory stands in
for `packages/knowledge/packs/aoe2techtree/` — the real pack is never touched by these tests
(vendoring it is T636, out of scope here). Exercises the module's functions directly (`plan_import`,
`apply_import`), following `test_sync_map_thumbnails.py`'s own precedent of testing the library
functions a thin CLI wrapper calls, and calls `main()` in-process (never a subprocess) for the
refusal cases that live only in argument parsing.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from scripts.ops.import_knowledge_pack import (
    apply_import,
    build_arg_parser,
    main,
    plan_import,
)

_MODULE_PATH = Path(__file__).resolve().parents[1] / "import_knowledge_pack.py"


def _write_checkout(root: Path) -> Path:
    """A synthetic local "checkout" carrying the default manifest's three entries — a top-level
    file, a second top-level file, and a directory of files — small enough to be a fast fixture
    but structurally the same shape `plan.md`'s Project Structure describes for the real pack."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "data.json").write_text('{"units": {}}\n', encoding="utf-8")
    (root / "strings.en.json").write_text('{"greeting": "hello"}\n', encoding="utf-8")
    trees_dir = root / "trees"
    trees_dir.mkdir()
    (trees_dir / "aztecs.json").write_text('{"civ": "aztecs"}\n', encoding="utf-8")
    (trees_dir / "britons.json").write_text('{"civ": "britons"}\n', encoding="utf-8")
    return root


# ------------------------------------------------------------------------------------ plan_import


def test_plan_import_resolves_files_and_expands_directories(tmp_path: Path) -> None:
    checkout = _write_checkout(tmp_path / "checkout")

    plan = plan_import(checkout, ("data.json", "strings.en.json", "trees"))

    assert plan.missing == ()
    assert set(plan.files) == {
        "data.json",
        "strings.en.json",
        "trees/aztecs.json",
        "trees/britons.json",
    }


def test_plan_import_reports_a_missing_entry_without_touching_the_filesystem(
    tmp_path: Path,
) -> None:
    checkout = _write_checkout(tmp_path / "checkout")

    plan = plan_import(checkout, ("data.json", "does-not-exist.json"))

    assert plan.files == ("data.json",)
    assert plan.missing == ("does-not-exist.json",)


def test_plan_import_alone_never_writes(tmp_path: Path) -> None:
    checkout = _write_checkout(tmp_path / "checkout")
    pack_dir = tmp_path / "pack"

    plan_import(checkout, ("data.json",))

    assert not pack_dir.exists()


# ----------------------------------------------------------------------------------- apply_import


def test_apply_import_with_apply_false_writes_nothing(tmp_path: Path) -> None:
    checkout = _write_checkout(tmp_path / "checkout")
    pack_dir = tmp_path / "pack"

    report = apply_import(checkout, pack_dir, commit="deadbeef", apply=False)

    assert report.apply is False
    assert report.written == ()
    assert report.digests == {}
    assert not pack_dir.exists()


def test_apply_import_copies_every_manifest_file_and_preserves_bytes(tmp_path: Path) -> None:
    checkout = _write_checkout(tmp_path / "checkout")
    pack_dir = tmp_path / "pack"

    report = apply_import(checkout, pack_dir, commit="deadbeef", apply=True)

    assert report.apply is True
    assert set(report.written) == {
        "data.json",
        "strings.en.json",
        "trees/aztecs.json",
        "trees/britons.json",
    }
    for relative in report.written:
        assert (pack_dir / relative).read_bytes() == (checkout / relative).read_bytes()


def test_apply_import_refuses_and_writes_nothing_when_a_manifest_entry_is_missing(
    tmp_path: Path,
) -> None:
    checkout = _write_checkout(tmp_path / "checkout")
    pack_dir = tmp_path / "pack"

    report = apply_import(
        checkout,
        pack_dir,
        commit="deadbeef",
        manifest=("data.json", "missing-file.json"),
        apply=True,
    )

    assert report.apply is False
    assert report.plan.missing == ("missing-file.json",)
    assert report.written == ()
    assert not pack_dir.exists(), "a partial import must never write any file"


def test_apply_import_writes_a_manifest_recording_commit_and_digests(tmp_path: Path) -> None:
    checkout = _write_checkout(tmp_path / "checkout")
    pack_dir = tmp_path / "pack"

    report = apply_import(checkout, pack_dir, commit="cafef00d", apply=True)

    manifest_path = pack_dir / "MANIFEST.json"
    assert manifest_path.is_file()
    recorded = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert recorded["source"] == "SiegeEngineers/aoe2techtree"
    assert recorded["commit"] == "cafef00d"
    assert "imported_at" in recorded
    assert set(recorded["files"]) == set(report.written)
    for relative, digest in recorded["files"].items():
        assert digest == report.digests[relative]
        assert digest.startswith("sha256:")


def test_apply_import_honours_an_explicit_manifest_override(tmp_path: Path) -> None:
    checkout = _write_checkout(tmp_path / "checkout")
    pack_dir = tmp_path / "pack"

    report = apply_import(
        checkout, pack_dir, commit="deadbeef", manifest=("data.json",), apply=True
    )

    assert report.written == ("data.json",)
    assert not (pack_dir / "strings.en.json").exists()
    assert not (pack_dir / "trees").exists()


def test_running_apply_twice_reproduces_the_same_digests(tmp_path: Path) -> None:
    checkout = _write_checkout(tmp_path / "checkout")
    pack_dir = tmp_path / "pack"

    first = apply_import(checkout, pack_dir, commit="deadbeef", apply=True)
    second = apply_import(checkout, pack_dir, commit="deadbeef", apply=True)

    assert first.digests == second.digests


# -------------------------------------------------------------------------------- CLI-level flags


def test_source_checkout_is_required() -> None:
    parser = build_arg_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--commit", "deadbeef"])


def test_commit_is_required() -> None:
    parser = build_arg_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--source-checkout", "/tmp/somewhere"])


def test_apply_and_dry_run_together_are_refused(tmp_path: Path) -> None:
    checkout = _write_checkout(tmp_path / "checkout")

    exit_code = main(
        ["--source-checkout", str(checkout), "--commit", "deadbeef", "--apply", "--dry-run"]
    )

    assert exit_code == 1


def test_nonexistent_source_checkout_is_refused(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"

    exit_code = main(["--source-checkout", str(missing), "--commit", "deadbeef"])

    assert exit_code == 1


def test_blank_commit_is_refused(tmp_path: Path) -> None:
    checkout = _write_checkout(tmp_path / "checkout")

    exit_code = main(["--source-checkout", str(checkout), "--commit", "   "])

    assert exit_code == 1


def test_main_dry_run_reports_missing_and_writes_nothing(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    pack_dir = tmp_path / "pack"

    exit_code = main(["--source-checkout", str(checkout), "--commit", "deadbeef"])

    assert exit_code == 1, "every default manifest entry is missing from an empty checkout"
    assert not pack_dir.exists()


def test_main_apply_writes_the_default_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.ops.import_knowledge_pack as module

    checkout = _write_checkout(tmp_path / "checkout")
    pack_dir = tmp_path / "pack"
    monkeypatch.setattr(module, "_PACK_DIR", pack_dir)

    exit_code = main(["--source-checkout", str(checkout), "--commit", "deadbeef", "--apply"])

    assert exit_code == 0
    assert (pack_dir / "data.json").is_file()
    assert (pack_dir / "MANIFEST.json").is_file()


# -------------------------------------------------------------------------- no-network guarantee


#: Mirrors `tests/architecture/test_import_graph.py`'s own forbidden-network roots — this file is
#: tested independently of that module (each ops script's test suite is self-contained), but the
#: set of names that count as "the network" should not drift between the two checks.
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
    targets: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            targets.append(node.module)
            targets.extend(f"{node.module}.{alias.name}" for alias in node.names)
    return targets


def _is_forbidden_network_import(dotted: str) -> bool:
    if dotted in _FORBIDDEN_NETWORK_EXACT:
        return True
    return dotted.split(".", 1)[0] in _FORBIDDEN_NETWORK_ROOTS


def test_the_script_imports_no_network_module() -> None:
    """Static, source-level guarantee that `import_knowledge_pack.py` opens no socket by any
    route this repository already treats as "the network" — `tests/architecture/
    test_import_graph.py`'s own method (parse, don't grep), applied to this one file directly
    since it lives under `scripts/ops/` rather than one of that module's guarded `src/` roots."""
    tree = ast.parse(_MODULE_PATH.read_text(encoding="utf-8"), filename=str(_MODULE_PATH))
    forbidden = sorted(
        {target for target in _direct_import_targets(tree) if _is_forbidden_network_import(target)}
    )
    assert forbidden == [], (
        f"import_knowledge_pack.py must never import a network module: {forbidden}"
    )


def test_the_script_performs_no_git_or_subprocess_call() -> None:
    """`--commit` is a stated, trusted value (module docstring) — this script must never shell out
    to `git` or anything else to resolve or verify it, which would itself be one step from a
    network call (a remote fetch to update refs) even if today's implementation only reads local
    state."""
    tree = ast.parse(_MODULE_PATH.read_text(encoding="utf-8"), filename=str(_MODULE_PATH))
    targets = set(_direct_import_targets(tree))
    assert "subprocess" not in targets
    assert "git" not in targets


# --------------------------------------------------------------------- the header warning itself


def test_module_docstring_carries_the_network_free_warning_and_fr032() -> None:
    import scripts.ops.import_knowledge_pack as module

    assert module.__doc__ is not None
    doc = module.__doc__
    assert "packages/providers" in doc
    assert "provider becomes mandatory" in doc
    assert "never clones" in doc.lower() or "never clone" in doc.lower()
