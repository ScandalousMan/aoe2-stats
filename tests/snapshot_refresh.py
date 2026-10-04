"""A knowledge refresh, modelled for tests: a real second snapshot of one build, promoted while the
first is demoted - the only shape `snapshot.snapshot_for` allows, since it raises on two promoted
snapshots describing one build.

Extracted from `apps/analyzer/tests/test_reproducibility.py` (T666f) so the staleness test in
`test_run_once.py` promotes a real snapshot the same way, instead of patching one resolver and
leaving the coverage pass on the real one - which made a document whose identity and gaps disagreed
about which snapshot answered.

It sits beside `tests/db.py` for the same reason: test-only infrastructure shared across
directories, not application code. Nothing here touches the committed `snapshots/` tree.

`packages/knowledge` has no root seam covering all of its readers: `snapshot.py` reads the root
through `_snapshots_root()`, but `query.py` and `effects.py` each call `resources.files(...)`
themselves, so patching `_snapshots_root` alone would resolve a snapshot that the coverage pass then
cannot open. All three modules are pointed at the one throwaway root.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from aoe2stats_knowledge import effects, query, snapshot

#: The packaged snapshot the fixture recording's build (180059) resolves against.
REAL_SNAPSHOT_DIRECTORY = "aoe2techtree-180059"
REFRESHED_SNAPSHOT_DIRECTORY = "aoe2techtree-180059-refresh"


class ResourcesShim:
    """Stands in for `importlib.resources` inside `aoe2stats_knowledge`: `files(...)` answers a
    throwaway package root instead of the installed one."""

    def __init__(self, package_root: Path) -> None:
        self._package_root = package_root

    def files(self, _package: str) -> Path:
        return self._package_root


def clear_snapshot_resolution_caches() -> None:
    """`snapshot_for` and its siblings are `functools.cache`d for a process's lifetime
    (`packages/knowledge/tests/conftest.py` explains why), so a root swap must clear them."""
    snapshot.load_all_snapshots.cache_clear()
    snapshot.load_resolvable_snapshots.cache_clear()
    snapshot.snapshot_for.cache_clear()


def isolate_snapshot_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """A throwaway snapshot root holding a byte-for-byte copy of the one snapshot the fixture
    recording resolves against, so promoting a second snapshot never touches the committed tree."""
    package_root = tmp_path / "knowledge-package"
    root = package_root / "snapshots"
    shutil.copytree(
        Path(str(snapshot._snapshots_root())) / REAL_SNAPSHOT_DIRECTORY,
        root / REAL_SNAPSHOT_DIRECTORY,
    )
    shim = ResourcesShim(package_root)
    for module in (snapshot, query, effects):
        monkeypatch.setattr(module, "resources", shim)
    return root


def promote_a_refreshed_snapshot(
    root: Path, *, without_entity: tuple[str, str] | None = None
) -> str:
    """Promote a second snapshot of the same build, demoting the first, and return the new
    snapshot's digest. The new content differs from the old (a comment line appended to
    `effects.toml`), so the digest - and therefore the identity - genuinely changes.

    `without_entity=(kind, id)` also drops that entity from the new snapshot's `rules.json`, so the
    coverage pass reports gaps against the new snapshot that it did not report against the old one:
    the way a test tells which snapshot the gaps were computed from. Such a snapshot lives in its
    own directory, because `query` and `effects` cache by directory name for the process's life.
    """
    first = root / REAL_SNAPSHOT_DIRECTORY
    directory = REFRESHED_SNAPSHOT_DIRECTORY
    if without_entity is not None:
        directory = f"{directory}-without-{without_entity[0]}-{without_entity[1]}"
    refreshed = root / directory
    shutil.copytree(first, refreshed)

    effects_file = refreshed / "effects.toml"
    effects_file.write_bytes(effects_file.read_bytes() + b"\n# a knowledge refresh, for SC-005\n")
    if without_entity is not None:
        kind, entity_id = without_entity
        rules_file = refreshed / "rules.json"
        rules = json.loads(rules_file.read_text(encoding="utf-8"))
        del rules["entities"][kind][entity_id]
        rules_file.write_text(json.dumps(rules, indent=2, sort_keys=True), encoding="utf-8")
    new_digest = snapshot.compute_digest(
        (refreshed / "rules.json").read_bytes(), effects_file.read_bytes()
    )

    identity_file = refreshed / snapshot.IDENTITY_FILENAME
    text = identity_file.read_text(encoding="utf-8")
    text, digest_substitutions = re.subn(
        r'^digest = "[^"]*"', f'digest = "{new_digest}"', text, flags=re.MULTILINE
    )
    text, version_substitutions = re.subn(
        r'^source_version = "([^"]*)"',
        r'source_version = "\1-refresh"',
        text,
        flags=re.MULTILINE,
    )
    assert (digest_substitutions, version_substitutions) == (1, 1)
    identity_file.write_text(text, encoding="utf-8")

    demoted_file = first / snapshot.IDENTITY_FILENAME
    demoted, demotions = re.subn(
        r"^promoted = true",
        "promoted = false",
        demoted_file.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    assert demotions == 1
    demoted_file.write_text(demoted, encoding="utf-8")

    clear_snapshot_resolution_caches()
    return new_digest
