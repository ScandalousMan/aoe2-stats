"""Tests for `scripts/checks/pinned_source_commit.py` (T652h), the gate born from a review finding
that the aoe2techtree pinned commit — and the four measurements read from its own history — are
copied by hand into seven files with nothing asserting they agree, extended by T707 to N vendored
packs (a newer revision sits beside the first, each pinned by its own `MANIFEST.json`).

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
    shas_in_backticks,
    snapshot_source_version,
    vendored_packs,
)

_SHA = "b9d494df6921d4080df69b22f9dbb7a4d1dcd9f0"
_OTHER_SHA = "1111111111111111111111111111111111111111"
_SECOND_SHA = "3bb43b1439eef88dfe7fe892d7f7dc41ac9dd76f"
_SECOND_PACK = "aoe2techtree-3bb43b1"


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
    extra_shas: tuple[str, ...] = (_SECOND_SHA,),
) -> str:
    intervening = ", ".join(str(build_number) for build_number in intervening_builds)
    return (
        f"- **Version identifier**: the pinned commit `{commit}` (2026-06-21). The pinned "
        f'commit\'s own newest "Implement DE Update" commit is `{evidence_commit}` ({date}), '
        f"implementing build {build} — followed by builds {intervening}, none of which it "
        "implements. Also pinned: " + ", ".join(f"`{sha}`" for sha in extra_shas) + ".\n"
    )


def _asset_packs_text(commit: str = _SHA, second_commit: str = _SECOND_SHA) -> str:
    return (
        "| Pack | Source | Licence |\n| --- | --- | --- |\n"
        f"| aoe2techtree | commit `{commit}` | MIT | ... |\n"
        f"| {_SECOND_PACK} | commit `{second_commit}` | MIT | ... |\n"
    )


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
    second_manifest_commit_value: str = _SECOND_SHA,
    second_licence_commit_value: str = _SECOND_SHA,
    data_sources_kwargs: dict[str, object] | None = None,
    asset_packs_commit_value: str = _SHA,
    asset_packs_second_commit_value: str = _SECOND_SHA,
    snapshot_source_versions: dict[str, str] | None = None,
    canonical_has_carry_forward: bool = True,
) -> dict[str, Path]:
    packs_dir = tmp_path / "packs"
    snapshots_dir = tmp_path / "snapshots"
    data_sources_path = tmp_path / "data-sources.md"
    asset_packs_docs_path = tmp_path / "asset-packs.md"

    _write(packs_dir / "aoe2techtree" / "MANIFEST.json", _manifest_text(manifest_commit_value))
    _write(packs_dir / "aoe2techtree" / "LICENCE.md", _licence_text(licence_commit_value))
    _write(packs_dir / _SECOND_PACK / "MANIFEST.json", _manifest_text(second_manifest_commit_value))
    _write(packs_dir / _SECOND_PACK / "LICENCE.md", _licence_text(second_licence_commit_value))
    _write(data_sources_path, _data_sources_text(**(data_sources_kwargs or {})))
    _write(
        asset_packs_docs_path,
        _asset_packs_text(asset_packs_commit_value, asset_packs_second_commit_value),
    )

    versions = snapshot_source_versions or {}
    canonical_snapshot_path = snapshots_dir / "aoe2techtree-180059" / "snapshot.toml"
    _write(
        canonical_snapshot_path,
        _snapshot_toml_text(
            source_version=versions.get("canonical", _SHA),
            with_carry_forward=canonical_has_carry_forward,
        ),
    )
    _write(
        snapshots_dir / "aoe2techtree-177723-test" / "snapshot.toml",
        _snapshot_toml_text(source_version=versions.get("sibling", _SHA)),
    )
    _write(
        snapshots_dir / "aoe2techtree-185872" / "snapshot.toml",
        _snapshot_toml_text(source_version=versions.get("second", _SECOND_SHA)),
    )
    _write(
        snapshots_dir / "aoe2techtree-test-stub" / "snapshot.toml",
        _snapshot_toml_text(source_version=versions.get("stub", _SHA)),
    )

    return {
        "packs_dir": packs_dir,
        "snapshots_dir": snapshots_dir,
        "data_sources_path": data_sources_path,
        "asset_packs_docs_path": asset_packs_docs_path,
        "canonical_snapshot_path": canonical_snapshot_path,
    }


def _check(paths: dict[str, Path]) -> list[str]:
    return check_pinned_source_commit(
        packs_dir=paths["packs_dir"],
        data_sources_path=paths["data_sources_path"],
        asset_packs_docs_path=paths["asset_packs_docs_path"],
        snapshots_dir=paths["snapshots_dir"],
        canonical_snapshot_path=paths["canonical_snapshot_path"],
    )


def _agreement(paths: dict[str, Path]) -> list[str]:
    return check_commit_agreement(
        packs=vendored_packs(paths["packs_dir"]),
        data_sources_path=paths["data_sources_path"],
        asset_packs_docs_path=paths["asset_packs_docs_path"],
        snapshot_toml_paths=tuple(sorted(paths["snapshots_dir"].glob("*/snapshot.toml"))),
    )


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
    """The passing case: two packs, each file states its own pack's sha, every snapshot's
    source_version names a vendored pack, and docs/data-sources.md restates the same four derived
    measurements the canonical snapshot's [validation.carry_forward] records."""
    assert _check(_write_full_tree(tmp_path)) == []


def test_shas_in_backticks_reads_every_forty_hex_run() -> None:
    assert shas_in_backticks(f"`{_SHA}` and `{_SECOND_SHA}` and `abc`") == [_SHA, _SECOND_SHA]


def test_vendored_packs_lists_every_directory_with_a_manifest(tmp_path: Path) -> None:
    paths = _write_full_tree(tmp_path)
    _write(paths["packs_dir"] / "not-a-pack" / "README.md", "no manifest")

    packs = vendored_packs(paths["packs_dir"])

    assert [(pack.name, pack.commit) for pack in packs] == [
        ("aoe2techtree", _SHA),
        (_SECOND_PACK, _SECOND_SHA),
    ]


# ----------------------------------------------------------------------------- disagreeing cases


def test_check_commit_agreement_refuses_a_snapshot_whose_source_version_names_no_vendored_pack(
    tmp_path: Path,
) -> None:
    """T707: a snapshot imported from a revision no pack in the repository holds cannot be
    re-derived from anything, so it is refused - the failure names the snapshot and the commit."""
    paths = _write_full_tree(tmp_path, snapshot_source_versions={"second": _OTHER_SHA})

    failures = _agreement(paths)

    assert len(failures) == 1
    assert "aoe2techtree-185872" in failures[0]
    assert _OTHER_SHA in failures[0]
    assert "names no vendored pack" in failures[0]


def test_a_snapshot_may_name_either_vendored_pack(tmp_path: Path) -> None:
    paths = _write_full_tree(
        tmp_path, snapshot_source_versions={"sibling": _SECOND_SHA, "second": _SHA}
    )
    assert _agreement(paths) == []


def test_check_commit_agreement_catches_a_disagreeing_licence(tmp_path: Path) -> None:
    """The exact shape of fault this check exists for: one file's hand-copied sha drifts from
    MANIFEST.json's own value, and the failure names that one file."""
    paths = _write_full_tree(tmp_path, licence_commit_value=_OTHER_SHA)

    failures = _agreement(paths)

    assert len(failures) == 1
    assert "aoe2techtree/LICENCE.md" in failures[0]
    assert _OTHER_SHA in failures[0]
    assert _SHA in failures[0]


def test_check_commit_agreement_catches_the_second_packs_disagreeing_licence(
    tmp_path: Path,
) -> None:
    paths = _write_full_tree(tmp_path, second_licence_commit_value=_SHA)

    failures = _agreement(paths)

    assert len(failures) == 1
    assert f"{_SECOND_PACK}/LICENCE.md" in failures[0]


def test_check_commit_agreement_catches_a_disagreeing_asset_packs_row(tmp_path: Path) -> None:
    """Each pack's own row is held to its own commit: the second pack's row carrying the first
    pack's sha (a copy-paste) is caught even though that sha appears elsewhere in the file."""
    paths = _write_full_tree(tmp_path, asset_packs_second_commit_value=_SHA)

    failures = _agreement(paths)

    assert len(failures) == 1
    assert "asset-packs.md" in failures[0]
    assert _SECOND_PACK in failures[0]


def test_check_commit_agreement_catches_a_pack_with_no_asset_packs_row(tmp_path: Path) -> None:
    paths = _write_full_tree(tmp_path)
    text = paths["asset_packs_docs_path"].read_text(encoding="utf-8")
    paths["asset_packs_docs_path"].write_text(
        "\n".join(line for line in text.splitlines() if _SECOND_PACK not in line) + "\n",
        encoding="utf-8",
    )

    failures = _agreement(paths)

    assert len(failures) == 1
    assert _SECOND_PACK in failures[0]


def test_check_commit_agreement_catches_a_pack_data_sources_does_not_state(
    tmp_path: Path,
) -> None:
    paths = _write_full_tree(tmp_path, data_sources_kwargs={"extra_shas": ()})

    failures = _agreement(paths)

    assert len(failures) == 1
    assert "data-sources.md" in failures[0]
    assert _SECOND_SHA in failures[0]


def test_check_commit_agreement_catches_a_stale_sha_in_data_sources(tmp_path: Path) -> None:
    paths = _write_full_tree(
        tmp_path, data_sources_kwargs={"extra_shas": (_SECOND_SHA, _OTHER_SHA)}
    )

    failures = _agreement(paths)

    assert len(failures) == 1
    assert _OTHER_SHA in failures[0]
    assert "no vendored pack pins" in failures[0]


def test_check_commit_agreement_catches_a_disagreeing_snapshot(tmp_path: Path) -> None:
    """A snapshot's own `[snapshot].source_version` disagreeing is caught individually - the
    others stay clean, matching `asset_packs.py`'s convention of one failure per disagreeing
    thing, not one failure once anything anywhere disagrees."""
    paths = _write_full_tree(tmp_path, snapshot_source_versions={"sibling": _OTHER_SHA})

    failures = _agreement(paths)

    assert len(failures) == 1
    assert "aoe2techtree-177723-test" in failures[0]


def test_check_commit_agreement_catches_every_disagreeing_file_at_once(tmp_path: Path) -> None:
    """Two independently disagreeing files produce two failures, not one - the check does not stop
    at the first mismatch it finds."""
    paths = _write_full_tree(
        tmp_path,
        licence_commit_value=_OTHER_SHA,
        asset_packs_commit_value=_OTHER_SHA,
    )

    failures = _agreement(paths)

    assert len(failures) == 2
    joined = "\n".join(failures)
    assert "LICENCE.md" in joined
    assert "asset-packs.md" in joined


def test_check_commit_agreement_reports_an_unreadable_manifest(tmp_path: Path) -> None:
    paths = _write_full_tree(tmp_path)
    (paths["packs_dir"] / _SECOND_PACK / "MANIFEST.json").write_text("{not json", encoding="utf-8")

    failures = _agreement(paths)

    assert any(f"{_SECOND_PACK}/MANIFEST.json" in failure for failure in failures)


def test_check_commit_agreement_reports_no_vendored_pack_at_all(tmp_path: Path) -> None:
    failures = check_commit_agreement(
        packs=vendored_packs(tmp_path / "absent"),
        data_sources_path=tmp_path / "ds.md",
        asset_packs_docs_path=tmp_path / "ap.md",
        snapshot_toml_paths=(),
    )
    assert len(failures) == 1
    assert "no vendored pack" in failures[0]


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
