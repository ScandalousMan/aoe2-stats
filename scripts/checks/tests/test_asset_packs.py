"""Licence-gate tests for `scripts/checks/asset_packs.py` (T402), encoding quickstart scenario 1
against a fixture tree this file builds and controls, never the real `packages/game-assets` —
that package's real content lands under a different, concurrent set of tasks (T404-T406) and is
not authoritative for what this check must reject.

T403 implemented `scripts/checks/asset_packs.py` against exactly the interface documented below,
and every `xfail(strict=True, reason="T403 not implemented yet")` marker that used to sit on each
test — forced off by `strict=True` the moment the module landed and these tests started passing for
real, per the pattern `scripts/checks/tests/test_spec_lint.py`'s own history records for T201/T202 —
has been removed. `pytest.importorskip` was deliberately not used while the module did not exist: a
skip proves nothing about whether the check does what FR-011 and SC-003 require; an
`xfail(strict=True)` on a genuine `ModuleNotFoundError` does, because it flips to a hard failure the
day someone adds the module without making these tests pass.

**Interface this file assumed of `scripts/checks/asset_packs.py`, and T403 implements exactly**
— nothing here is inherited from an existing module, so it was nailed down explicitly:

    REQUIRED_FIELDS: tuple[str, ...]
        `("Source", "Licence", "Permitted usage", "Ruling", "Checked")` — contracts/asset-pack.md's
        five required `LICENCE.md` fields, in that order.

    def parse_licence_fields(text: str) -> dict[str, str]:
        Parses a `LICENCE.md`'s `- **Field**: value` bullets into a dict keyed by field name.
        A field the text never states is simply absent from the returned dict — this function
        does not itself decide what "missing" means, `check_pack` does.

    def check_pack(pack_dir: Path) -> list[str]:
        One pack directory's own checks: `LICENCE.md` present; every one of `REQUIRED_FIELDS`
        present in it (one failure string per missing field, not one failure for the file); and,
        when `Ruling` reads as `READ ONLY`, the directory holds no file besides `LICENCE.md`
        itself. Returns human-readable failure strings, `[]` when the pack is clean.

    def check_size_budget(assets_root: Path, size_budget_bytes: int) -> list[str]:
        Total on-disk size of every file under `assets_root`, recursively; one failure when it
        exceeds `size_budget_bytes`. The budget is always a caller-supplied parameter — this
        module never assumes the real 10 MB figure (research.md D5), so a test can use a budget
        small enough to control with a few bytes of fixture rather than a real 10 MB payload.

    def check_docs_mirror(assets_root: Path, docs_file: Path) -> list[str]:
        `docs_file` is a pipe-delimited markdown table with a header row naming, among others, a
        `Pack` column and the five `LICENCE.md` field names as columns (case-insensitive header
        match). Every pack directory under `assets_root` that has a `LICENCE.md` must have exactly
        one table row whose `Pack` cell equals the directory name, and every field the `LICENCE.md`
        states must match that row's corresponding cell exactly once stripped of surrounding
        whitespace. A pack absent from the table is one failure; a pack present with any field
        disagreeing is a separate failure.

    def check_disclaimer(readme_file: Path) -> list[str]:
        One failure when `readme_file`'s text no longer carries both halves of the Microsoft "Game
        Content Usage Rules" disclaimer sentence that
        `packages/design-system/src/components/Footer/Footer.test.tsx` already asserts against
        verbatim — this check does not reformat or reflow the paragraph, only requires it be
        present. This is constitution X's first anchor; the footer half of the same anchor is
        `Footer.test.tsx`'s job, not this one's.

    def check_asset_packs(
        assets_root: Path, docs_file: Path, readme_file: Path, size_budget_bytes: int
    ) -> list[str]:
        Runs every check above over every immediate subdirectory of `assets_root` plus the two
        repository-wide checks, and returns every failure concatenated. `main()` calls this with
        the real repository's paths and the real 10 MB budget (research.md D5) and exits 1 the
        moment this list is non-empty.

Every non-README fixture below is entirely synthetic — a `tmp_path` tree this test builds — never
the real `packages/game-assets`. Only the disclaimer tests read the real `README.md`, because that
paragraph is the actual anchor being guarded and a synthetic stand-in would prove nothing about it.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_REAL_README = _REPO_ROOT / "README.md"

#: The two halves of the disclaimer sentence, copied verbatim from the assertions
#: `Footer.test.tsx` already makes against the same file — so this test and the front-end test
#: guard the identical anchor rather than two independently-worded approximations of it.
_DISCLAIMER_HALF_1 = (
    'aoe2-stats was created under Microsoft\'s "Game Content Usage Rules" using assets from'
)
_DISCLAIMER_HALF_2 = "Age of Empires II: Definitive Edition, (c) Microsoft Corporation."


def _valid_fields() -> dict[str, str]:
    """A complete, synthetic set of the five required fields — none of it real pack content."""
    return {
        "Source": "example/example-repo, `img/Example/`",
        "Licence": "None found",
        "Permitted usage": "Microsoft Game Content Usage Rules: non-commercial, notice required",
        "Ruling": "COPY IN — constitution X 5.0.0",
        "Checked": "2026-08-30",
    }


def _licence_text(fields: dict[str, str]) -> str:
    lines = ["# Licence record — test fixture", ""]
    for name, value in fields.items():
        lines.append(f"- **{name}**: {value}")
    return "\n".join(lines) + "\n"


def _write_pack(
    root: Path, name: str, fields: dict[str, str] | None, extra_files: list[str]
) -> Path:
    """Build one synthetic pack directory under `root`.

    `fields=None` means "no LICENCE.md at all"; a dict (possibly with a key removed by the caller)
    is written as the file's content. `extra_files` are the pack's payload files, named freely —
    their content is irrelevant except to the size-budget tests, which set it explicitly.
    """
    pack_dir = root / name
    pack_dir.mkdir(parents=True)
    if fields is not None:
        (pack_dir / "LICENCE.md").write_text(_licence_text(fields), encoding="utf-8")
    for filename in extra_files:
        (pack_dir / filename).write_bytes(b"")
    return pack_dir


def _docs_table(rows: list[dict[str, str]]) -> str:
    """A minimal `docs/asset-packs.md`-shaped markdown table, per this file's own documented
    assumption about `check_docs_mirror`'s input shape."""
    header = "| Pack | Source | Licence | Permitted usage | Ruling | Checked |"
    separator = "| --- | --- | --- | --- | --- | --- |"
    lines = [header, separator]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                row[key]
                for key in ("Pack", "Source", "Licence", "Permitted usage", "Ruling", "Checked")
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def _docs_row_for(pack_name: str, fields: dict[str, str]) -> dict[str, str]:
    return {"Pack": pack_name, **fields}


# --------------------------------------------------------------------- (a) no LICENCE.md at all


def test_pack_with_no_licence_md_fails(tmp_path: Path) -> None:
    """SC-003, the whole gate: a pack directory holding files but no `LICENCE.md` record."""
    from scripts.checks.asset_packs import check_pack

    pack_dir = _write_pack(tmp_path, "unrecorded-pack", fields=None, extra_files=["icon.webp"])

    failures = check_pack(pack_dir)

    assert failures, "a pack with no LICENCE.md must fail the check"
    assert any("LICENCE.md" in failure for failure in failures)


# ------------------------------------------------------------- (b) one test per required field


def test_licence_md_missing_source_field_fails(tmp_path: Path) -> None:
    from scripts.checks.asset_packs import check_pack

    fields = _valid_fields()
    del fields["Source"]
    pack_dir = _write_pack(tmp_path, "pack-missing-source", fields, extra_files=["icon.webp"])

    failures = check_pack(pack_dir)

    assert len(failures) == 1, f"expected exactly one failure, got {failures!r}"
    assert "Source" in failures[0]


def test_licence_md_missing_licence_field_fails(tmp_path: Path) -> None:
    from scripts.checks.asset_packs import check_pack

    fields = _valid_fields()
    del fields["Licence"]
    pack_dir = _write_pack(tmp_path, "pack-missing-licence", fields, extra_files=["icon.webp"])

    failures = check_pack(pack_dir)

    assert len(failures) == 1, f"expected exactly one failure, got {failures!r}"
    assert "Licence" in failures[0]


def test_licence_md_missing_permitted_usage_field_fails(tmp_path: Path) -> None:
    from scripts.checks.asset_packs import check_pack

    fields = _valid_fields()
    del fields["Permitted usage"]
    pack_dir = _write_pack(
        tmp_path, "pack-missing-permitted-usage", fields, extra_files=["icon.webp"]
    )

    failures = check_pack(pack_dir)

    assert len(failures) == 1, f"expected exactly one failure, got {failures!r}"
    assert "Permitted usage" in failures[0]


def test_licence_md_missing_ruling_field_fails(tmp_path: Path) -> None:
    from scripts.checks.asset_packs import check_pack

    fields = _valid_fields()
    del fields["Ruling"]
    pack_dir = _write_pack(tmp_path, "pack-missing-ruling", fields, extra_files=["icon.webp"])

    failures = check_pack(pack_dir)

    assert len(failures) == 1, f"expected exactly one failure, got {failures!r}"
    assert "Ruling" in failures[0]


def test_licence_md_missing_checked_field_fails(tmp_path: Path) -> None:
    from scripts.checks.asset_packs import check_pack

    fields = _valid_fields()
    del fields["Checked"]
    pack_dir = _write_pack(tmp_path, "pack-missing-checked", fields, extra_files=["icon.webp"])

    failures = check_pack(pack_dir)

    assert len(failures) == 1, f"expected exactly one failure, got {failures!r}"
    assert "Checked" in failures[0]


# --------------------------------------------------------------- (c) READ ONLY holding files


def test_read_only_ruling_with_files_present_fails(tmp_path: Path) -> None:
    """A `Ruling` of `READ ONLY` states the source may be read but not copied in — a directory
    that holds files anyway is the exact thing constitution X forbids."""
    from scripts.checks.asset_packs import check_pack

    fields = _valid_fields()
    fields["Ruling"] = "READ ONLY — no redistribution licence, read at request time only"
    pack_dir = _write_pack(
        tmp_path, "read-only-pack", fields, extra_files=["copied-in-anyway.webp"]
    )

    failures = check_pack(pack_dir)

    assert failures, "READ ONLY with files copied in must fail"
    assert any("READ ONLY" in failure for failure in failures)


def test_read_only_ruling_with_no_files_besides_licence_passes(tmp_path: Path) -> None:
    """The contrast case, so the check above is known to test the files and not merely the word
    `READ ONLY` appearing anywhere: a `READ ONLY` pack that holds no payload file at all is
    exactly what that ruling permits, and must not be flagged."""
    from scripts.checks.asset_packs import check_pack

    fields = _valid_fields()
    fields["Ruling"] = "READ ONLY — no redistribution licence, read at request time only"
    pack_dir = _write_pack(tmp_path, "read-only-pack-clean", fields, extra_files=[])

    failures = check_pack(pack_dir)

    assert failures == []


# ---------------------------------------------------------------------- (d) the size budget


def test_package_exceeding_size_budget_fails(tmp_path: Path) -> None:
    """research.md D5's budget — checked against a tiny synthetic threshold this test controls,
    never the real 10 MB figure, so the fixture needs bytes rather than megabytes."""
    from scripts.checks.asset_packs import check_size_budget

    assets_root = tmp_path / "game-assets"
    pack_dir = _write_pack(assets_root, "big-pack", _valid_fields(), extra_files=[])
    (pack_dir / "oversized.webp").write_bytes(b"x" * 20)

    failures = check_size_budget(assets_root, size_budget_bytes=10)

    assert failures, "a package over its budget must fail"
    assert any("budget" in failure.lower() for failure in failures)


def test_package_within_size_budget_passes(tmp_path: Path) -> None:
    """The contrast case: the same shape, comfortably under the same kind of threshold."""
    from scripts.checks.asset_packs import check_size_budget

    assets_root = tmp_path / "game-assets"
    pack_dir = _write_pack(assets_root, "small-pack", _valid_fields(), extra_files=[])
    (pack_dir / "tiny.webp").write_bytes(b"x" * 4)

    failures = check_size_budget(assets_root, size_budget_bytes=1024)

    assert failures == []


# ------------------------------------------------------------- (e) the docs/asset-packs.md mirror


def test_pack_absent_from_docs_mirror_fails(tmp_path: Path) -> None:
    """SC-003's mirror half: a recorded pack that `docs/asset-packs.md` never mentions at all."""
    from scripts.checks.asset_packs import check_docs_mirror

    assets_root = tmp_path / "game-assets"
    fields = _valid_fields()
    _write_pack(assets_root, "undocumented-pack", fields, extra_files=["icon.webp"])
    docs_file = tmp_path / "asset-packs.md"
    docs_file.write_text(_docs_table([]), encoding="utf-8")

    failures = check_docs_mirror(assets_root, docs_file)

    assert failures, "a pack absent from the docs mirror must fail"
    assert any("undocumented-pack" in failure for failure in failures)


def test_pack_disagreeing_with_docs_mirror_fails(tmp_path: Path) -> None:
    """The mirror exists and names the pack, but its `Ruling` cell no longer matches the
    `LICENCE.md` that is the normative copy — the drift D4 exists to prevent."""
    from scripts.checks.asset_packs import check_docs_mirror

    assets_root = tmp_path / "game-assets"
    fields = _valid_fields()
    fields["Ruling"] = "COPY IN — constitution X 5.0.0"
    _write_pack(assets_root, "drifted-pack", fields, extra_files=["icon.webp"])

    docs_row = _docs_row_for("drifted-pack", fields)
    docs_row["Ruling"] = "READ ONLY — no redistribution licence"  # deliberately disagrees
    docs_file = tmp_path / "asset-packs.md"
    docs_file.write_text(_docs_table([docs_row]), encoding="utf-8")

    failures = check_docs_mirror(assets_root, docs_file)

    assert failures, "a pack whose docs row disagrees with its LICENCE.md must fail"
    assert any("drifted-pack" in failure for failure in failures)


def test_pack_agreeing_with_docs_mirror_passes(tmp_path: Path) -> None:
    """The contrast case: the mirror names the pack and every field matches exactly."""
    from scripts.checks.asset_packs import check_docs_mirror

    assets_root = tmp_path / "game-assets"
    fields = _valid_fields()
    _write_pack(assets_root, "mirrored-pack", fields, extra_files=["icon.webp"])

    docs_file = tmp_path / "asset-packs.md"
    docs_file.write_text(_docs_table([_docs_row_for("mirrored-pack", fields)]), encoding="utf-8")

    failures = check_docs_mirror(assets_root, docs_file)

    assert failures == []


# --------------------------------------------------------- (f) the disclaimer — the anchor itself


def test_real_readme_carries_the_disclaimer(tmp_path: Path) -> None:
    """Sanity check against the real anchor, not a synthetic stand-in: today's `README.md` must
    pass, or every test below it is exercising a check against a paragraph that never existed."""
    from scripts.checks.asset_packs import check_disclaimer

    failures = check_disclaimer(_REAL_README)

    assert failures == []


def test_disclaimer_deleted_from_readme_fails(tmp_path: Path) -> None:
    """The case the check exists for. Constitution X grants the permission on two anchors —
    non-commercial and the disclaimer — and 'remove either anchor and the permission lapses' is
    the constitution's own wording. A check that guards the packs without guarding this paragraph
    would go on passing on the exact pull request that made every pack unlawful.

    Built from the real `README.md` with only the disclaimer paragraph struck out, so this is a
    minimal, targeted deletion of the real anchor rather than a wholly invented fixture — the
    other check conditions in this file use synthetic fixtures; this one does not, because the
    paragraph itself is what is being guarded.
    """
    from scripts.checks.asset_packs import check_disclaimer

    real_text = _REAL_README.read_text(encoding="utf-8")
    assert _DISCLAIMER_HALF_1 in real_text, "fixture assumption stale: half 1 no longer present"
    assert _DISCLAIMER_HALF_2 in real_text, "fixture assumption stale: half 2 no longer present"

    without_disclaimer = "\n".join(
        line
        for line in real_text.splitlines()
        if _DISCLAIMER_HALF_1 not in line and _DISCLAIMER_HALF_2 not in line
    )
    stripped_readme = tmp_path / "README.md"
    stripped_readme.write_text(without_disclaimer, encoding="utf-8")

    failures = check_disclaimer(stripped_readme)

    assert failures, "a README with the disclaimer paragraph removed must fail the check"
    assert any("disclaimer" in failure.lower() for failure in failures)


# ------------------------------------------------------- (g) the aggregate — everything together


def test_a_fully_compliant_tree_passes_every_check(tmp_path: Path) -> None:
    """The positive control: one clean, synthetic pack, correctly mirrored, comfortably inside
    budget, against the real README.md — `check_asset_packs` must report nothing at all. Without
    this, every failing case above could be "trivially" satisfied by a check that always fails."""
    from scripts.checks.asset_packs import check_asset_packs

    assets_root = tmp_path / "game-assets"
    fields = _valid_fields()
    _write_pack(assets_root, "compliant-pack", fields, extra_files=["icon.webp"])

    docs_file = tmp_path / "asset-packs.md"
    docs_file.write_text(_docs_table([_docs_row_for("compliant-pack", fields)]), encoding="utf-8")

    failures = check_asset_packs(
        assets_root=assets_root,
        docs_file=docs_file,
        readme_file=_REAL_README,
        size_budget_bytes=1024,
    )

    assert failures == []
