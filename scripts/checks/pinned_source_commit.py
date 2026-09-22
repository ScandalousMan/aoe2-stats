#!/usr/bin/env python3
"""The aoe2techtree pinned-commit gate: one sha, copied by hand into seven files, asserted by none.

Born from a review finding on T652h (2026-09-22): `SiegeEngineers/aoe2techtree`'s pinned commit
`b9d494df6921d4080df69b22f9dbb7a4d1dcd9f0` is machine-written once, by
`scripts/ops/import_knowledge_pack.py`, into `packages/knowledge/packs/aoe2techtree/MANIFEST.json`
— and then hand-copied into `LICENCE.md`, `docs/data-sources.md`, `docs/asset-packs.md`, and the
`source_version` field of every `aoe2techtree-*` snapshot's `snapshot.toml`. Four measurements a
person read *from* that commit's own history travel with it into the same prose: the source's
last-implemented build (177723), the commit that implements it (`daf5fa18de`), the date that
commit was made (2026-06-03), and the three builds shipped after it and never implemented (178524,
179158, 180059). `CLAUDE.md`'s filing rule is explicit that "a number that exists in two files will
be wrong in one of them", and that a living fact in `docs/` "is trustworthy only because a test
asserts it" — nothing asserted any of the above, across seven files, until this check.

**Source of truth.** For the sha: `MANIFEST.json`, because `import_knowledge_pack.py` writes it
from the operator's own `--commit` argument and never verifies it against the checkout's git
history (see that script's own docstring) — it is the one file in the set that is machine-written,
every other occurrence is prose a person retyped by hand and could mistype. For the four derived
measurements: `aoe2techtree-180059/snapshot.toml`'s `[validation.carry_forward]` table, the one
place research actually performed the reading (T642, research.md D3/D4) and recorded it
structurally rather than as a restatement — `docs/data-sources.md` §6 must agree with it.

**How far this reaches, and where it deliberately stops.** The sha is checked across all seven
non-test files that state it. The four derived measurements are checked only against
`docs/data-sources.md`, because `aoe2techtree-180059/snapshot.toml`'s `[validation.carry_forward]`
table is both their source and their only other *structured* restatement — the sibling snapshots
(`aoe2techtree-177723-test`, `aoe2techtree-test-stub`) and `aoe2techtree-180059`'s own header
comment mention some of the same numbers, but only inside free-form comment prose, not a second
structured record; parsing repository comments for restated facts is a materially different (and
far larger) check than this task asked for, so it is left alone here. The pinned commit's *own*
date (2026-06-21, distinct from the 2026-06-03 date above, which belongs to the commit that last
implemented a build) is restated in the same five places as the sha but was not named by the review
finding this check answers, and — unlike the sha and the four measurements above — it never
appears in a structured field anywhere, only in prose; covering it would mean regex-matching
comments the same way, so it is out of scope for the same reason.

`packages/knowledge/tests/test_snapshot.py`'s two occurrences of the sha
(`test_parse_identity_reads_the_fr024_fields`, `test_parse_identity_ignores_fields_outside_fr024`)
are deliberately out of scope: they are arbitrary 40-hex-character fixture data exercising
`parse_identity`'s own TOML parsing, not a claim that this *is* the real pinned commit — both tests
pass identically for any other syntactically valid 40-hex string, which is what a fixture value is
and a restated fact is not.

Run: uv run scripts/checks/pinned_source_commit.py
Exit: 0 clean, 1 on any failure. Stdlib only (tomllib, 3.11+), so it needs no environment.
"""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

_PACK_DIR = REPO / "packages" / "knowledge" / "packs" / "aoe2techtree"
_SNAPSHOTS_DIR = REPO / "packages" / "knowledge" / "snapshots"

#: `MANIFEST.json` is this check's source of truth for the sha — see the module docstring.
MANIFEST_PATH = _PACK_DIR / "MANIFEST.json"
LICENCE_PATH = _PACK_DIR / "LICENCE.md"
DATA_SOURCES_PATH = REPO / "docs" / "data-sources.md"
ASSET_PACKS_DOCS_PATH = REPO / "docs" / "asset-packs.md"

#: Every `aoe2techtree-*` snapshot's `snapshot.toml`, whose `[snapshot].source_version` must agree
#: with `MANIFEST.json`'s `commit`.
SNAPSHOT_TOML_PATHS: tuple[Path, ...] = (
    _SNAPSHOTS_DIR / "aoe2techtree-180059" / "snapshot.toml",
    _SNAPSHOTS_DIR / "aoe2techtree-177723-test" / "snapshot.toml",
    _SNAPSHOTS_DIR / "aoe2techtree-test-stub" / "snapshot.toml",
)

#: The one promoted snapshot whose `[validation.carry_forward]` table is the derived measurements'
#: source of truth — see the module docstring's "Source of truth" section.
CANONICAL_CARRY_FORWARD_SNAPSHOT_PATH = _SNAPSHOTS_DIR / "aoe2techtree-180059" / "snapshot.toml"

_SHA_IN_BACKTICKS_RE = re.compile(r"`([0-9a-f]{40})`")
_EVIDENCE_COMMIT_DATE_RE = re.compile(r"commit (?P<commit>\S+), dated (?P<date>\d{4}-\d{2}-\d{2})")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


# ------------------------------------------------------------------------------------ extraction


def sha_in_backticks(text: str) -> str | None:
    """The first 40-hex-character commit sha wrapped in backticks in `text`, or `None` if the
    text carries none — the shape every prose occurrence (`LICENCE.md`, `docs/data-sources.md`,
    `docs/asset-packs.md`) uses."""
    match = _SHA_IN_BACKTICKS_RE.search(text)
    return match.group(1) if match else None


def manifest_commit(manifest_path: Path) -> str | None:
    """`MANIFEST.json`'s own `commit` field — this check's source of truth for the sha."""
    if not manifest_path.is_file():
        return None
    try:
        data = json.loads(read(manifest_path))
    except json.JSONDecodeError:
        return None
    commit = data.get("commit")
    return commit if isinstance(commit, str) else None


def snapshot_source_version(snapshot_toml_path: Path) -> str | None:
    """A `snapshot.toml`'s `[snapshot].source_version` field."""
    if not snapshot_toml_path.is_file():
        return None
    data = tomllib.loads(read(snapshot_toml_path))
    value = data.get("snapshot", {}).get("source_version")
    return value if isinstance(value, str) else None


def carry_forward_table(snapshot_toml_path: Path) -> dict[str, object] | None:
    """The `[validation.carry_forward]` table of `snapshot_toml_path`, or `None` when the file is
    missing or carries no such table (a snapshot validated by a different method, for one)."""
    if not snapshot_toml_path.is_file():
        return None
    data = tomllib.loads(read(snapshot_toml_path))
    validation = data.get("validation")
    if not isinstance(validation, dict):
        return None
    carry_forward = validation.get("carry_forward")
    return carry_forward if isinstance(carry_forward, dict) else None


def canonical_derived_measurements(snapshot_toml_path: Path) -> dict[str, object] | None:
    """The four derived measurements read out of `snapshot_toml_path`'s own
    `[validation.carry_forward]` table: `last_implemented_build` (int), `last_implemented_commit`
    and `last_implemented_date` (both parsed out of the table's own evidence prose, the only place
    they are recorded at all — research.md D3: "the build lives in commit-message prose, not in a
    dedicated field"), and `intervening_builds` (list[int]). Returns `None` when the table is
    absent or missing a field this function needs, so callers can turn that into its own failure
    rather than a crash."""
    carry_forward = carry_forward_table(snapshot_toml_path)
    if carry_forward is None:
        return None
    build = carry_forward.get("source_last_implemented_build")
    evidence = carry_forward.get("source_last_implemented_build_evidence")
    intervening_builds = carry_forward.get("intervening_builds")
    if not isinstance(build, int) or not isinstance(evidence, str):
        return None
    if not isinstance(intervening_builds, list) or not all(
        isinstance(item, int) for item in intervening_builds
    ):
        return None
    match = _EVIDENCE_COMMIT_DATE_RE.search(evidence)
    if match is None:
        return None
    return {
        "last_implemented_build": build,
        "last_implemented_commit": match.group("commit"),
        "last_implemented_date": match.group("date"),
        "intervening_builds": intervening_builds,
    }


# ---------------------------------------------------------------------------------------- checks


def check_commit_agreement(
    *,
    manifest_path: Path,
    licence_path: Path,
    data_sources_path: Path,
    asset_packs_docs_path: Path,
    snapshot_toml_paths: tuple[Path, ...],
) -> list[str]:
    """Every stated sha against `manifest_commit(manifest_path)`, the source of truth. One failure
    per file that is missing the sha entirely, and one per file whose sha disagrees."""
    canonical = manifest_commit(manifest_path)
    failures: list[str] = []
    if canonical is None:
        return [
            f"{_rel(manifest_path)}: no readable 'commit' field — nothing to check the rest against"
        ]

    prose_files = {
        licence_path: sha_in_backticks(read(licence_path)),
        data_sources_path: sha_in_backticks(read(data_sources_path)),
        asset_packs_docs_path: sha_in_backticks(read(asset_packs_docs_path)),
    }
    for path, found in prose_files.items():
        failures.extend(_agree(path, found, canonical, what="the pinned commit sha"))

    for snapshot_path in snapshot_toml_paths:
        found = snapshot_source_version(snapshot_path)
        failures.extend(_agree(snapshot_path, found, canonical, what="[snapshot].source_version"))

    return failures


def check_derived_measurements_agreement(
    *, canonical_snapshot_path: Path, data_sources_path: Path
) -> list[str]:
    """The four measurements derived from the pinned commit's own history — read once, in
    `canonical_snapshot_path`'s `[validation.carry_forward]` table — against their prose
    restatement in `data_sources_path` (docs/data-sources.md §6). Each of the build number, the
    commit and the date is checked as a whole-word substring so that, say, canonical build 177723
    changing to 177724 is not accidentally satisfied by an unrelated "177724" elsewhere in the
    file, and so that this check fails closed rather than open when the number disappears."""
    canonical = canonical_derived_measurements(canonical_snapshot_path)
    if canonical is None:
        return [
            f"{_rel(canonical_snapshot_path)}: no readable [validation.carry_forward] table with "
            "source_last_implemented_build, source_last_implemented_build_evidence and "
            "intervening_builds — nothing to check docs/data-sources.md against"
        ]

    docs_text = read(data_sources_path)
    failures: list[str] = []

    build = canonical["last_implemented_build"]
    if not _contains_word(docs_text, str(build)):
        failures.append(
            f"{_rel(data_sources_path)}: does not restate the last-implemented build "
            f"{build} that {_rel(canonical_snapshot_path)}'s [validation.carry_forward] records"
        )

    commit = canonical["last_implemented_commit"]
    assert isinstance(commit, str)
    if commit not in docs_text:
        failures.append(
            f"{_rel(data_sources_path)}: does not restate the last-implemented commit "
            f"`{commit}` that {_rel(canonical_snapshot_path)}'s [validation.carry_forward] records"
        )

    date = canonical["last_implemented_date"]
    assert isinstance(date, str)
    if date not in docs_text:
        failures.append(
            f"{_rel(data_sources_path)}: does not restate the date {date} that "
            f"{_rel(canonical_snapshot_path)}'s [validation.carry_forward] records for commit "
            f"`{commit}`"
        )

    intervening_builds = canonical["intervening_builds"]
    assert isinstance(intervening_builds, list)
    for intervening_build in intervening_builds:
        if not _contains_word(docs_text, str(intervening_build)):
            failures.append(
                f"{_rel(data_sources_path)}: does not restate intervening build "
                f"{intervening_build} that {_rel(canonical_snapshot_path)}'s "
                "[validation.carry_forward].intervening_builds records"
            )

    return failures


def check_pinned_source_commit(
    *,
    manifest_path: Path = MANIFEST_PATH,
    licence_path: Path = LICENCE_PATH,
    data_sources_path: Path = DATA_SOURCES_PATH,
    asset_packs_docs_path: Path = ASSET_PACKS_DOCS_PATH,
    snapshot_toml_paths: tuple[Path, ...] = SNAPSHOT_TOML_PATHS,
    canonical_snapshot_path: Path = CANONICAL_CARRY_FORWARD_SNAPSHOT_PATH,
) -> list[str]:
    """Both halves of the gate, concatenated: the sha across every file that states it, and the
    four derived measurements against their one prose restatement in `docs/data-sources.md`."""
    failures = check_commit_agreement(
        manifest_path=manifest_path,
        licence_path=licence_path,
        data_sources_path=data_sources_path,
        asset_packs_docs_path=asset_packs_docs_path,
        snapshot_toml_paths=snapshot_toml_paths,
    )
    failures.extend(
        check_derived_measurements_agreement(
            canonical_snapshot_path=canonical_snapshot_path,
            data_sources_path=data_sources_path,
        )
    )
    return failures


# --------------------------------------------------------------------------------------- helpers


def _agree(path: Path, found: str | None, canonical: str, *, what: str) -> list[str]:
    if found is None:
        return [f"{_rel(path)}: no readable {what} — expected `{canonical}`"]
    if found != canonical:
        return [f"{_rel(path)}: {what} is `{found}`, expected `{canonical}` (from MANIFEST.json)"]
    return []


def _contains_word(text: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", text) is not None


def _rel(path: Path) -> str:
    return str(path.relative_to(REPO)) if path.is_relative_to(REPO) else str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    print(
        "pinned_source_commit: the aoe2techtree pinned commit, across every file that states it\n"
    )
    failures = check_pinned_source_commit()

    if failures:
        for failure in failures:
            print(f"  FAIL  {failure}")
        print(f"\n{len(failures)} failure(s).")
        return 1
    print("clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
