"""Tests for `scripts/checks/pinned_source_commit.py` (T652h), the gate born from a review finding
that the aoe2techtree pinned commit — and the four measurements read from its own history — are
copied by hand into seven files with nothing asserting they agree.

Every fixture below is synthetic — a `tmp_path` tree this file builds and controls, mirroring the
real `MANIFEST.json`, `LICENCE.md`, `docs/data-sources.md`, `docs/asset-packs.md` and the three
`snapshot.toml` files in miniature — never the real repository, matching `test_asset_packs.py`'s
and `test_api_entrypoint_deps.py`'s own convention for the same reason: this check's own tests must
not change meaning as the real files drift over time, and a disagreeing case needs a tree this file
can actually put out of agreement.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.checks.pinned_source_commit import (
    canonical_derived_measurements,
    check_commit_agreement,
    check_derived_measurements_agreement,
    check_pinned_source_commit,
    manifest_commit,
    sha_in_backticks,
    snapshot_source_version,
)

_SHA = "b9d494df6921d4080df69b22f9dbb7a4d1dcd9f0"
_OTHER_SHA = "1111111111111111111111111111111111111111"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _manifest_text(commit: str = _SHA) -> str:
    return json.dumps({"commit": commit, "source": "SiegeEngineers/aoe2techtree"})


def _licence_text(commit: str = _SHA) -> str:
    return f"- **Source**: `SiegeEngineers/aoe2techtree`, commit `{commit}` (2026-06-21)\n"


def _data_sources_text(
    *,
    commit: str = _SHA,
    build: int = 177723,
    evidence_commit: str = "daf5fa18de",
    date: str = "2026-06-03",
    intervening_builds: tuple[int, ...] = (178524, 179158, 180059),
) -> str:
    intervening = ", ".join(str(build_number) for build_number in intervening_builds)
    return (
        f"- **Version identifier**: the pinned commit `{commit}` (2026-06-21). The pinned "
        f'commit\'s own newest "Implement DE Update" commit is `{evidence_commit}` ({date}), '
        f"implementing build {build} — followed by builds {intervening}, none of which it "
        "implements.\n"
    )


def _asset_packs_text(commit: str = _SHA) -> str:
    return f"| aoe2techtree | commit `{commit}` | MIT | ... |\n"


def _snapshot_toml_text(*, source_version: str = _SHA, with_carry_forward: bool = False) -> str:
    text = (
        "[snapshot]\n"
        'source = "aoe2techtree"\n'
        f'source_version = "{source_version}"\n'
        "describes_build = 180059\n"
    )
    if with_carry_forward:
        text += (
            "\n[validation]\n"
            'method = "carry-forward"\n'
            'checked_against = "patch notes"\n'
            'performed_by = "test"\n'
            'performed_at = "2026-09-20"\n'
            "\n[validation.carry_forward]\n"
            "source_last_implemented_build = 177723\n"
            "source_last_implemented_build_evidence = "
            '"""commit daf5fa18de, dated 2026-06-03, message \\"Implement DE Update 177723\\""""\n'
            "intervening_builds = [178524, 179158, 180059]\n"
        )
    return text


def _write_full_tree(
    tmp_path: Path,
    *,
    manifest_commit_value: str = _SHA,
    licence_commit_value: str = _SHA,
    data_sources_kwargs: dict[str, object] | None = None,
    asset_packs_commit_value: str = _SHA,
    snapshot_source_versions: dict[str, str] | None = None,
    canonical_has_carry_forward: bool = True,
) -> dict[str, Path]:
    manifest_path = tmp_path / "MANIFEST.json"
    licence_path = tmp_path / "LICENCE.md"
    data_sources_path = tmp_path / "data-sources.md"
    asset_packs_docs_path = tmp_path / "asset-packs.md"
    canonical_snapshot_path = tmp_path / "aoe2techtree-180059" / "snapshot.toml"
    sibling_snapshot_path = tmp_path / "aoe2techtree-177723-test" / "snapshot.toml"
    stub_snapshot_path = tmp_path / "aoe2techtree-test-stub" / "snapshot.toml"

    versions = snapshot_source_versions or {}
    _write(manifest_path, _manifest_text(manifest_commit_value))
    _write(licence_path, _licence_text(licence_commit_value))
    _write(data_sources_path, _data_sources_text(**(data_sources_kwargs or {})))
    _write(asset_packs_docs_path, _asset_packs_text(asset_packs_commit_value))
    _write(
        canonical_snapshot_path,
        _snapshot_toml_text(
            source_version=versions.get("canonical", _SHA),
            with_carry_forward=canonical_has_carry_forward,
        ),
    )
    _write(
        sibling_snapshot_path,
        _snapshot_toml_text(source_version=versions.get("sibling", _SHA)),
    )
    _write(
        stub_snapshot_path,
        _snapshot_toml_text(source_version=versions.get("stub", _SHA)),
    )

    return {
        "manifest_path": manifest_path,
        "licence_path": licence_path,
        "data_sources_path": data_sources_path,
        "asset_packs_docs_path": asset_packs_docs_path,
        "snapshot_toml_paths": (canonical_snapshot_path, sibling_snapshot_path, stub_snapshot_path),
        "canonical_snapshot_path": canonical_snapshot_path,
    }


# --------------------------------------------------------------------------------- unit-level


def test_sha_in_backticks_reads_the_first_forty_hex_run() -> None:
    assert sha_in_backticks(_licence_text(_SHA)) == _SHA


def test_sha_in_backticks_is_none_when_absent() -> None:
    assert sha_in_backticks("no commit here") is None


def test_manifest_commit_reads_the_commit_field(tmp_path: Path) -> None:
    path = tmp_path / "MANIFEST.json"
    _write(path, _manifest_text(_SHA))
    assert manifest_commit(path) == _SHA


def test_manifest_commit_is_none_when_missing(tmp_path: Path) -> None:
    assert manifest_commit(tmp_path / "absent.json") is None


def test_snapshot_source_version_reads_the_snapshot_table(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.toml"
    _write(path, _snapshot_toml_text(source_version=_SHA))
    assert snapshot_source_version(path) == _SHA


def test_canonical_derived_measurements_reads_all_four_fields(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.toml"
    _write(path, _snapshot_toml_text(with_carry_forward=True))
    measurements = canonical_derived_measurements(path)
    assert measurements == {
        "last_implemented_build": 177723,
        "last_implemented_commit": "daf5fa18de",
        "last_implemented_date": "2026-06-03",
        "intervening_builds": [178524, 179158, 180059],
    }


def test_canonical_derived_measurements_is_none_without_a_carry_forward_table(
    tmp_path: Path,
) -> None:
    path = tmp_path / "snapshot.toml"
    _write(path, _snapshot_toml_text(with_carry_forward=False))
    assert canonical_derived_measurements(path) is None


# ------------------------------------------------------------------------------- agreeing case


def test_check_pinned_source_commit_is_clean_when_everything_agrees(tmp_path: Path) -> None:
    """The passing case: every file states the same sha, and docs/data-sources.md restates the
    same four derived measurements the canonical snapshot's [validation.carry_forward] records."""
    paths = _write_full_tree(tmp_path)

    failures = check_pinned_source_commit(
        manifest_path=paths["manifest_path"],
        licence_path=paths["licence_path"],
        data_sources_path=paths["data_sources_path"],
        asset_packs_docs_path=paths["asset_packs_docs_path"],
        snapshot_toml_paths=paths["snapshot_toml_paths"],
        canonical_snapshot_path=paths["canonical_snapshot_path"],
    )
    assert failures == []


# ----------------------------------------------------------------------------- disagreeing cases


def test_check_commit_agreement_catches_a_disagreeing_licence(tmp_path: Path) -> None:
    """The exact shape of fault this check exists for: one file's hand-copied sha drifts from
    MANIFEST.json's own value, and the failure names that one file."""
    paths = _write_full_tree(tmp_path, licence_commit_value=_OTHER_SHA)

    failures = check_commit_agreement(
        manifest_path=paths["manifest_path"],
        licence_path=paths["licence_path"],
        data_sources_path=paths["data_sources_path"],
        asset_packs_docs_path=paths["asset_packs_docs_path"],
        snapshot_toml_paths=paths["snapshot_toml_paths"],
    )
    assert len(failures) == 1
    assert "LICENCE.md" in failures[0]
    assert _OTHER_SHA in failures[0]
    assert _SHA in failures[0]


def test_check_commit_agreement_catches_a_disagreeing_snapshot(tmp_path: Path) -> None:
    """A snapshot's own `[snapshot].source_version` disagreeing is caught individually — the
    sibling and stub snapshots stay clean, matching `asset_packs.py`'s convention of one failure
    per disagreeing thing, not one failure once anything anywhere disagrees."""
    paths = _write_full_tree(tmp_path, snapshot_source_versions={"sibling": _OTHER_SHA})

    failures = check_commit_agreement(
        manifest_path=paths["manifest_path"],
        licence_path=paths["licence_path"],
        data_sources_path=paths["data_sources_path"],
        asset_packs_docs_path=paths["asset_packs_docs_path"],
        snapshot_toml_paths=paths["snapshot_toml_paths"],
    )
    assert len(failures) == 1
    assert "aoe2techtree-177723-test" in failures[0]


def test_check_commit_agreement_catches_every_disagreeing_file_at_once(tmp_path: Path) -> None:
    """Two independently disagreeing files produce two failures, not one — the check does not stop
    at the first mismatch it finds."""
    paths = _write_full_tree(
        tmp_path,
        licence_commit_value=_OTHER_SHA,
        asset_packs_commit_value=_OTHER_SHA,
    )

    failures = check_commit_agreement(
        manifest_path=paths["manifest_path"],
        licence_path=paths["licence_path"],
        data_sources_path=paths["data_sources_path"],
        asset_packs_docs_path=paths["asset_packs_docs_path"],
        snapshot_toml_paths=paths["snapshot_toml_paths"],
    )
    assert len(failures) == 2
    joined = "\n".join(failures)
    assert "LICENCE.md" in joined
    assert "asset-packs.md" in joined


def test_check_derived_measurements_agreement_catches_a_stale_build_number(tmp_path: Path) -> None:
    """docs/data-sources.md still saying the old last-implemented build after the canonical
    snapshot's own carry-forward record changed underneath it — the drift SC-013 forbids."""
    paths = _write_full_tree(tmp_path, data_sources_kwargs={"build": 999999})

    failures = check_derived_measurements_agreement(
        canonical_snapshot_path=paths["canonical_snapshot_path"],
        data_sources_path=paths["data_sources_path"],
    )
    assert len(failures) == 1
    assert "177723" in failures[0]


def test_check_derived_measurements_agreement_catches_a_stale_intervening_build(
    tmp_path: Path,
) -> None:
    paths = _write_full_tree(
        tmp_path, data_sources_kwargs={"intervening_builds": (178524, 179158, 999999)}
    )

    failures = check_derived_measurements_agreement(
        canonical_snapshot_path=paths["canonical_snapshot_path"],
        data_sources_path=paths["data_sources_path"],
    )
    assert len(failures) == 1
    assert "180059" in failures[0]


def test_check_derived_measurements_agreement_catches_a_stale_commit_or_date(
    tmp_path: Path,
) -> None:
    paths = _write_full_tree(
        tmp_path, data_sources_kwargs={"evidence_commit": "0000000000", "date": "2020-01-01"}
    )

    failures = check_derived_measurements_agreement(
        canonical_snapshot_path=paths["canonical_snapshot_path"],
        data_sources_path=paths["data_sources_path"],
    )
    assert len(failures) == 2
    joined = "\n".join(failures)
    assert "daf5fa18de" in joined
    assert "2026-06-03" in joined


def test_check_derived_measurements_agreement_reports_missing_carry_forward_table(
    tmp_path: Path,
) -> None:
    paths = _write_full_tree(tmp_path, canonical_has_carry_forward=False)

    failures = check_derived_measurements_agreement(
        canonical_snapshot_path=paths["canonical_snapshot_path"],
        data_sources_path=paths["data_sources_path"],
    )
    assert len(failures) == 1
    assert "validation.carry_forward" in failures[0]
