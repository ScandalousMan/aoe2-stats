"""Regression guard for the production packaging incident of 2026-09-28 (PR #90's post-merge
deploy, ref `99bc875d`).

`packages/knowledge/pyproject.toml` force-includes `snapshots/` and `packs/` into the wheel
(`tool.hatch.build.targets.wheel.force-include`) — the package reads both at runtime relative to
its own `__file__`, so a real (non-editable) install needs them physically inside the wheel, not
just reachable via the workspace's editable `src` layout. `src/aoe2stats_knowledge/{snapshots,
packs}` are themselves symlinks to those same two directories, kept so an *editable* dev install
(the default `uv sync` gives every workspace member, and what CI's `uv sync --all-packages --dev`
exercises) can resolve them too, since an editable install never applies force-include at all.

Nothing in this repository's test suite or CI (`.github/workflows/pr.yml`'s `uv sync
--all-packages --dev`, always editable) had ever built a real wheel for this package before this
file. Vercel's production build does (`uv sync --active --no-dev --link-mode hardlink --frozen
--no-editable`), and a real wheel build's default `packages` file scan follows the two symlinks,
landing the same files a second time at the exact paths `force-include` already forces — hatchling
then refuses outright: `ValueError: A second file is being added to the wheel archive at the same
path: 'aoe2stats_knowledge/packs/aoe2techtree/LICENCE.md'`. Every deploy of `main` failed with
that until the `exclude` entries alongside `packages` were added (this test's fixture), which
leaves `force-include` the sole source of those two trees in a real wheel and makes the collision
structurally impossible rather than merely untriggered.

`uv build`'s ordinary sdist round-trip does not exercise this: its sdist step does not dereference
a symlink into its target's contents, so `uv build --package aoe2stats-knowledge` (no `--wheel`)
builds successfully whether or not the bug is present, exercising neither the failure nor the fix.
`--wheel` skips the sdist step and builds directly from this source tree — the same PEP 517
`build_wheel(..., metadata_directory=None)` hook Vercel's `--no-editable` sync calls — and is the
only local repro that reproduces the exact traceback above (confirmed by hand against this
package's `pyproject.toml` before the `exclude` fix landed)."""

from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _build_real_wheel(tmp_path: Path) -> Path:
    """Build `aoe2stats-knowledge`'s wheel directly from source (no sdist round-trip) — the
    codepath a real, non-editable install (Vercel's production build) exercises, and the only one
    that can reproduce or prove fixed the force-include/symlink collision this file guards."""
    out_dir = tmp_path / "dist"
    result = subprocess.run(
        [
            "uv",
            "build",
            "--package",
            "aoe2stats-knowledge",
            "--wheel",
            "-o",
            str(out_dir),
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        "a real (non-editable) wheel build of packages/knowledge failed — this is exactly the "
        f"shape of the 2026-09-28 production incident.\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    wheels = sorted(out_dir.glob("aoe2stats_knowledge-*.whl"))
    assert len(wheels) == 1, f"expected exactly one built wheel, found {wheels}"
    return wheels[0]


def test_real_wheel_build_does_not_duplicate_the_forced_include_paths(tmp_path: Path) -> None:
    """The exact incident: building a real (non-editable) wheel must not raise hatchling's
    "second file... at the same path" `ValueError` for anything under `packs/` or `snapshots/`,
    and every name inside the wheel's zip archive must be unique — a duplicate zip entry is the
    literal shape of the bug even in a hatchling version lenient enough to overwrite rather than
    raise on one."""
    wheel_path = _build_real_wheel(tmp_path)
    with zipfile.ZipFile(wheel_path) as archive:
        names = archive.namelist()
    assert len(names) == len(set(names)), "duplicate entries in the built wheel's zip archive"


def test_real_wheel_build_still_carries_every_packs_and_snapshots_file(tmp_path: Path) -> None:
    """The `exclude` fix must not silently drop `packs/`/`snapshots/` instead of merely
    deduplicating them — assert the built wheel's file count under each matches what the same
    two directories hold on disk (`force-include`'s own two entries, and nothing else supplies
    them, per this file's module docstring)."""
    wheel_path = _build_real_wheel(tmp_path)
    with zipfile.ZipFile(wheel_path) as archive:
        names = archive.namelist()

    packs_on_disk = [
        p for p in (_REPO_ROOT / "packages" / "knowledge" / "packs").rglob("*") if p.is_file()
    ]
    snapshots_on_disk = [
        p for p in (_REPO_ROOT / "packages" / "knowledge" / "snapshots").rglob("*") if p.is_file()
    ]
    packs_in_wheel = [n for n in names if n.startswith("aoe2stats_knowledge/packs/")]
    snapshots_in_wheel = [n for n in names if n.startswith("aoe2stats_knowledge/snapshots/")]

    assert len(packs_in_wheel) == len(packs_on_disk)
    assert len(snapshots_in_wheel) == len(snapshots_on_disk)
    assert "aoe2stats_knowledge/packs/aoe2techtree/LICENCE.md" in packs_in_wheel


def test_uv_binary_is_the_one_this_test_assumes() -> None:
    """Sanity check the environment actually has `uv` on `PATH` — a missing binary would make the
    two tests above fail with a confusing `FileNotFoundError` from `subprocess.run` rather than
    naming what's actually wrong."""
    result = subprocess.run(["uv", "--version"], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, f"`uv --version` failed: {result.stderr}"
