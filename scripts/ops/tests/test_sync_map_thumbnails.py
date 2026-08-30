"""Tests for `scripts/ops/sync_map_thumbnails.py` (research.md D9, T448).

Entirely network-free and filesystem-only: a synthetic `--source-dir` of tiny generated PNGs under
`tmp_path`, and a synthetic target "pack" directory that stands in for
`packages/game-assets/maps/` — the real pack is never touched by these tests. Exercises the
module's functions directly (`plan_sync`, `apply_sync`, `slugify`) for the sync behaviour itself,
following `test_acknowledge_alerts.py`'s own precedent of testing the library functions a thin CLI
wrapper calls, and calls `main()` in-process (never a subprocess) for the handful of refusal cases
that live only in argument parsing.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image
from scripts.ops.sync_map_thumbnails import (
    apply_sync,
    build_arg_parser,
    encode_webp,
    main,
    plan_sync,
    slugify,
)


def _write_source_png(directory: Path, filename: str, *, colour: tuple[int, int, int]) -> Path:
    """A tiny (4x4) real PNG — small enough to be a fast fixture, but a genuine image `Pillow` can
    open and re-encode, which a hand-written byte string would not be."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    Image.new("RGB", (4, 4), color=colour).save(path, format="PNG")
    return path


def _webp_bytes_for(png_path: Path) -> bytes:
    """The exact bytes `encode_webp` would produce for `png_path` — used by tests to build an
    "already up to date" target file without depending on `encode_webp`'s own correctness."""
    return encode_webp(png_path)


# --------------------------------------------------------------------------------------- slugify


def test_slugify_lowercases_and_hyphenates_spaces() -> None:
    assert slugify("Black Forest") == "black-forest"


def test_slugify_is_close_to_identity_for_already_kebab_case_names() -> None:
    assert slugify("arabia") == "arabia"
    assert slugify("black-forest") == "black-forest"


# ------------------------------------------------------------------------------------ encode_webp


def test_encode_webp_produces_a_valid_webp_image(tmp_path: Path) -> None:
    source = _write_source_png(tmp_path / "source", "arabia.png", colour=(200, 150, 50))

    encoded = encode_webp(source)

    with Image.open(io.BytesIO(encoded)) as image:
        assert image.format == "WEBP"
        assert image.size == (4, 4)


# --------------------------------------------------------------------------------------- new slug


def test_new_source_slug_produces_a_webp_under_the_target_on_a_real_run(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    _write_source_png(source_dir, "arabia.png", colour=(200, 150, 50))

    report = apply_sync(source_dir, target_dir, apply=True, prune=False)

    assert report.added == ("arabia",)
    assert report.changed == ()
    target_file = target_dir / "arabia.webp"
    assert target_file.is_file()
    with Image.open(target_file) as image:
        assert image.format == "WEBP"


# ---------------------------------------------------------------------------------------- dry-run


def test_dry_run_reports_the_change_and_writes_nothing(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    _write_source_png(source_dir, "arabia.png", colour=(200, 150, 50))

    report = apply_sync(source_dir, target_dir, apply=False, prune=False)

    assert report.added == ("arabia",)
    assert report.apply is False
    assert not target_dir.exists(), "a dry run must create no directory and write no file"


def test_plan_sync_alone_never_writes(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    _write_source_png(source_dir, "arabia.png", colour=(200, 150, 50))

    plan_sync(source_dir, target_dir)

    assert not target_dir.exists()


# --------------------------------------------------------------------------------------- idempotent


def test_running_apply_twice_reports_zero_changes_and_writes_nothing_the_second_time(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    _write_source_png(source_dir, "arabia.png", colour=(200, 150, 50))

    first = apply_sync(source_dir, target_dir, apply=True, prune=False)
    assert first.added == ("arabia",)

    target_file = target_dir / "arabia.webp"
    mtime_after_first_run = target_file.stat().st_mtime_ns
    bytes_after_first_run = target_file.read_bytes()

    second = apply_sync(source_dir, target_dir, apply=True, prune=False)

    assert second.added == ()
    assert second.changed == ()
    assert second.unchanged == ("arabia",)
    assert target_file.stat().st_mtime_ns == mtime_after_first_run, (
        "an unchanged file must not be rewritten on a second run"
    )
    assert target_file.read_bytes() == bytes_after_first_run


def test_a_changed_source_image_is_reported_and_written_as_changed_not_added(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    _write_source_png(source_dir, "arabia.png", colour=(200, 150, 50))
    apply_sync(source_dir, target_dir, apply=True, prune=False)

    # Overwrite the source image with different pixel content — a real "the upstream image
    # changed" scenario, not just a new file.
    _write_source_png(source_dir, "arabia.png", colour=(10, 10, 10))

    report = apply_sync(source_dir, target_dir, apply=True, prune=False)

    assert report.added == ()
    assert report.changed == ("arabia",)


# -------------------------------------------------------------------------------------------- prune


def test_without_prune_a_pack_file_absent_from_source_is_reported_but_left_alone(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    source_dir.mkdir(parents=True)
    target_dir.mkdir(parents=True)

    dropped_png = tmp_path / "dropped-source.png"
    Image.new("RGB", (4, 4), color=(1, 2, 3)).save(dropped_png, format="PNG")
    target_dir.joinpath("dropped-map.webp").write_bytes(_webp_bytes_for(dropped_png))

    report = apply_sync(source_dir, target_dir, apply=True, prune=False)

    assert report.removable == ("dropped-map",)
    assert report.pruned == ()
    assert target_dir.joinpath("dropped-map.webp").is_file(), (
        "without --prune, a pack file absent from source must be left alone"
    )


def test_with_prune_a_pack_file_absent_from_source_is_removed(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    source_dir.mkdir(parents=True)
    target_dir.mkdir(parents=True)

    dropped_png = tmp_path / "dropped-source.png"
    Image.new("RGB", (4, 4), color=(1, 2, 3)).save(dropped_png, format="PNG")
    target_dir.joinpath("dropped-map.webp").write_bytes(_webp_bytes_for(dropped_png))

    report = apply_sync(source_dir, target_dir, apply=True, prune=True)

    assert report.pruned == ("dropped-map",)
    assert not target_dir.joinpath("dropped-map.webp").exists()


def test_prune_dry_run_reports_removable_but_deletes_nothing(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    source_dir.mkdir(parents=True)
    target_dir.mkdir(parents=True)

    dropped_png = tmp_path / "dropped-source.png"
    Image.new("RGB", (4, 4), color=(1, 2, 3)).save(dropped_png, format="PNG")
    target_dir.joinpath("dropped-map.webp").write_bytes(_webp_bytes_for(dropped_png))

    report = apply_sync(source_dir, target_dir, apply=False, prune=True)

    assert report.removable == ("dropped-map",)
    assert report.pruned == ()
    assert target_dir.joinpath("dropped-map.webp").is_file()


# -------------------------------------------------------------------------------- CLI-level flags


def test_source_dir_is_required() -> None:
    parser = build_arg_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_apply_and_dry_run_together_are_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True)

    exit_code = main(["--source-dir", str(source_dir), "--apply", "--dry-run"])

    assert exit_code == 1
    assert "mutually exclusive" in capsys.readouterr().out


def test_nonexistent_source_dir_is_refused(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"

    exit_code = main(["--source-dir", str(missing)])

    assert exit_code == 1
