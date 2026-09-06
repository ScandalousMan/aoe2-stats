#!/usr/bin/env python3
"""The licence gate over `packages/game-assets/` (constitution X, FR-011, SC-003).

Read-only, no network, stdlib only — modelled on `spec_lint.py`. Every pack directory under
`packages/game-assets/` must carry a `LICENCE.md` recording all five fields
[contracts/asset-pack.md](../../specs/004-visual-parity/contracts/asset-pack.md) requires; a
`Ruling` of `READ ONLY` must hold no payload file; the package as a whole must stay under its size
budget (research.md D5); every recorded pack must agree with its mirror in `docs/asset-packs.md`;
and the Microsoft "Game Content Usage Rules" disclaimer must still be present in `README.md` — the
constitution's own wording is "remove either anchor and the permission lapses", and this is the
check that notices.

Run: uv run scripts/checks/asset_packs.py
Exit: 0 clean, 1 on any failure.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

#: contracts/asset-pack.md's five required `LICENCE.md` fields, in that order.
REQUIRED_FIELDS: tuple[str, ...] = (
    "Source",
    "Licence",
    "Permitted usage",
    "Ruling",
    "Checked",
)

#: research.md D5's budget on the whole `packages/game-assets` payload.
SIZE_BUDGET_BYTES = 10 * 1024 * 1024

#: typography-tokens.md §4.4's budget on the whole `packages/design-system/tokens/fonts` payload —
#: a separate constant from `SIZE_BUDGET_BYTES` deliberately: the two are different facts with
#: different justifications, and a shared constant would make one of them a coincidence.
FONT_SIZE_BUDGET_BYTES = 1 * 1024 * 1024

#: Every assets root this gate covers, paired with its own size budget. Constitution X's "a pack
#: whose licence is not recorded MUST NOT be added" is enforced only where this gate looks — until
#: feature 005 T523 that was exactly one directory, so a font (or any future asset kind) landing
#: anywhere else was covered by nothing and did not even trigger the CI job. A font directory is an
#: assets root for the same reason `packages/game-assets` is: it holds files copied in under a
#: licence this gate has to keep honest.
ASSET_ROOTS: tuple[tuple[Path, int], ...] = (
    (REPO / "packages" / "game-assets", SIZE_BUDGET_BYTES),
    (REPO / "packages" / "design-system" / "tokens" / "fonts", FONT_SIZE_BUDGET_BYTES),
)

#: Directories under `packages/game-assets/` that hold package plumbing rather than an asset pack
#: (T401: the resolver's source and its build/test tooling live beside the pack directories, not
#: inside one). A pack is a directory the licence gate can hold to `contracts/asset-pack.md`'s
#: layout; these are not that, and the gate must not mistake them for an unrecorded pack.
_NON_PACK_DIR_NAMES = {"src", "node_modules"}

#: The two halves of the Microsoft "Game Content Usage Rules" disclaimer sentence, copied verbatim
#: from the assertions `Footer.test.tsx` already makes against the same `README.md` paragraph — so
#: this check and the front-end test guard the identical anchor rather than two independently
#: worded approximations of it.
_DISCLAIMER_HALF_1 = (
    'aoe2-stats was created under Microsoft\'s "Game Content Usage Rules" using assets from'
)
_DISCLAIMER_HALF_2 = "Age of Empires II: Definitive Edition, (c) Microsoft Corporation."

_FIELD_LINE_RE = re.compile(r"^-\s+\*\*(?P<name>[^*]+)\*\*:\s*(?P<value>.*)$")
_TABLE_SEPARATOR_RE = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


# ---------------------------------------------------------------------------- LICENCE.md parsing


def parse_licence_fields(text: str) -> dict[str, str]:
    """Parse a `LICENCE.md`'s `- **Field**: value` bullets into a dict keyed by field name.

    A field's value may wrap across several lines — every real record in this repository does —
    so a line that is not itself a new `- **Field**:` bullet is treated as a continuation of the
    field most recently opened, joined with a space. A field the text never states is simply
    absent from the returned dict; this function does not decide what "missing" means.
    """
    fields: dict[str, str] = {}
    current: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        match = _FIELD_LINE_RE.match(line.strip())
        if match:
            current = match.group("name").strip()
            fields[current] = match.group("value").strip()
            continue
        if current is not None and line.strip():
            fields[current] = f"{fields[current]} {line.strip()}".strip()
    return fields


# ------------------------------------------------------------------------------------ pack checks


def _pack_dirs(assets_root: Path) -> list[Path]:
    """Every immediate subdirectory of `assets_root` that could plausibly be a pack — i.e. not
    the package's own source or tooling directories (see `_NON_PACK_DIR_NAMES`) and not a hidden
    directory such as a VCS or editor artifact."""
    if not assets_root.is_dir():
        return []
    return sorted(
        (
            entry
            for entry in assets_root.iterdir()
            if entry.is_dir()
            and entry.name not in _NON_PACK_DIR_NAMES
            and not entry.name.startswith(".")
        ),
        key=lambda entry: entry.name,
    )


def check_pack(pack_dir: Path) -> list[str]:
    """One pack directory's own checks: a `LICENCE.md`, all five required fields present in it
    (one failure string per missing field), and — when `Ruling` reads as `READ ONLY` — no payload
    file besides the record itself."""
    failures: list[str] = []
    licence_path = pack_dir / "LICENCE.md"
    if not licence_path.is_file():
        failures.append(f"{pack_dir.name}: no LICENCE.md found")
        return failures

    fields = parse_licence_fields(read(licence_path))
    for field in REQUIRED_FIELDS:
        if not fields.get(field, "").strip():
            failures.append(f"{pack_dir.name}: LICENCE.md is missing the '{field}' field")

    if "read only" in fields.get("Ruling", "").lower():
        payload_files = sorted(
            entry.name
            for entry in pack_dir.iterdir()
            if entry.is_file() and entry.name != "LICENCE.md"
        )
        if payload_files:
            failures.append(
                f"{pack_dir.name}: Ruling is READ ONLY but the directory holds files copied in: "
                + ", ".join(payload_files)
            )
    return failures


def check_size_budget(assets_root: Path, size_budget_bytes: int) -> list[str]:
    """Total on-disk size of every file under `assets_root`, recursively; one failure when it
    exceeds `size_budget_bytes`. The budget is always a caller-supplied parameter (research.md D5
    fixes the real figure; this module never assumes it)."""
    if not assets_root.is_dir():
        return []
    total_bytes = sum(entry.stat().st_size for entry in assets_root.rglob("*") if entry.is_file())
    if total_bytes > size_budget_bytes:
        return [
            f"{assets_root.name} is {total_bytes} bytes, over its {size_budget_bytes}-byte budget"
        ]
    return []


# ------------------------------------------------------------------------------------ docs mirror


def _split_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _markdown_tables(text: str) -> list[tuple[list[str], list[list[str]]]]:
    """Every pipe-delimited markdown table in `text`, as `(header_cells, data_rows)`."""
    lines = text.splitlines()
    tables: list[tuple[list[str], list[list[str]]]] = []
    index = 0
    while index < len(lines) - 1:
        header_line = lines[index].strip()
        separator_line = lines[index + 1].strip()
        if header_line.startswith("|") and _TABLE_SEPARATOR_RE.match(separator_line):
            header = _split_table_row(header_line)
            rows: list[list[str]] = []
            cursor = index + 2
            while cursor < len(lines) and lines[cursor].strip().startswith("|"):
                rows.append(_split_table_row(lines[cursor]))
                cursor += 1
            tables.append((header, rows))
            index = cursor
        else:
            index += 1
    return tables


def _documented_packs(docs_text: str) -> dict[str, dict[str, str]]:
    """`{pack_name: {field: value}}`, read from every table in `docs_text` whose header names a
    `Pack` column and all five `REQUIRED_FIELDS` columns (case-insensitive)."""
    documented: dict[str, dict[str, str]] = {}
    for header, rows in _markdown_tables(docs_text):
        header_lower = [cell.lower() for cell in header]
        if "pack" not in header_lower:
            continue
        if not all(field.lower() in header_lower for field in REQUIRED_FIELDS):
            continue
        pack_index = header_lower.index("pack")
        field_index = {field: header_lower.index(field.lower()) for field in REQUIRED_FIELDS}
        for row in rows:
            if len(row) != len(header):
                continue
            pack_name = row[pack_index].strip()
            if not pack_name:
                continue
            documented[pack_name] = {field: row[idx].strip() for field, idx in field_index.items()}
    return documented


def check_docs_mirror(assets_root: Path, docs_file: Path) -> list[str]:
    """Every pack directory under `assets_root` with a `LICENCE.md` must have exactly one row in
    `docs_file` whose `Pack` cell equals the directory name, and every field the `LICENCE.md`
    states must match that row's corresponding cell exactly once stripped of surrounding
    whitespace. A pack absent from the table is one failure; a pack present with any field
    disagreeing is a separate failure per field."""
    failures: list[str] = []
    documented = _documented_packs(read(docs_file))

    for pack_dir in _pack_dirs(assets_root):
        licence_path = pack_dir / "LICENCE.md"
        if not licence_path.is_file():
            continue
        pack_name = pack_dir.name
        fields = parse_licence_fields(read(licence_path))
        if pack_name not in documented:
            failures.append(f"{pack_name}: recorded in LICENCE.md but absent from {docs_file.name}")
            continue
        documented_fields = documented[pack_name]
        for field in REQUIRED_FIELDS:
            expected = fields.get(field, "").strip()
            actual = documented_fields.get(field, "").strip()
            if expected != actual:
                failures.append(
                    f"{pack_name}: '{field}' disagrees between LICENCE.md ({expected!r}) and "
                    f"{docs_file.name} ({actual!r})"
                )
    return failures


# ------------------------------------------------------------------------------- the disclaimer


def check_disclaimer(readme_file: Path) -> list[str]:
    """One failure when `readme_file` no longer carries both halves of the Microsoft "Game
    Content Usage Rules" disclaimer sentence — constitution X's first anchor. The footer half of
    the same anchor is `Footer.test.tsx`'s job, not this one's; this check does not reformat or
    reflow the paragraph, only requires it be present."""
    text = read(readme_file)
    if _DISCLAIMER_HALF_1 not in text or _DISCLAIMER_HALF_2 not in text:
        return [
            f"{readme_file.name}: the Game Content Usage Rules disclaimer paragraph is missing "
            "or has been altered — constitution X's permission for every pack lapses without it"
        ]
    return []


# ------------------------------------------------------------------------------------- aggregate


def check_asset_packs(
    assets_root: Path, docs_file: Path, readme_file: Path, size_budget_bytes: int
) -> list[str]:
    """Run every check above over every immediate subdirectory of `assets_root` plus the two
    repository-wide checks, and return every failure concatenated."""
    failures: list[str] = []
    for pack_dir in _pack_dirs(assets_root):
        failures.extend(check_pack(pack_dir))
    failures.extend(check_size_budget(assets_root, size_budget_bytes))
    failures.extend(check_docs_mirror(assets_root, docs_file))
    failures.extend(check_disclaimer(readme_file))
    return failures


def check_asset_roots(
    roots: tuple[tuple[Path, int], ...], docs_file: Path, readme_file: Path
) -> list[str]:
    """The multi-root composition `main()` actually runs (typography-tokens.md §9.2 point 3):
    `check_pack`, `check_size_budget` (with that root's own budget) and `check_docs_mirror` for
    every pack in every one of `roots`, plus `check_disclaimer` **exactly once** — the disclaimer
    is a repository-wide anchor, not a per-root one, so calling `check_asset_packs` once per root
    would report its failure once per root too. Composed alongside `check_asset_packs`, not in
    place of it: that aggregate's signature and behaviour stay untouched for its existing
    single-root callers."""
    failures: list[str] = []
    for assets_root, size_budget_bytes in roots:
        for pack_dir in _pack_dirs(assets_root):
            failures.extend(check_pack(pack_dir))
        failures.extend(check_size_budget(assets_root, size_budget_bytes))
        failures.extend(check_docs_mirror(assets_root, docs_file))
    failures.extend(check_disclaimer(readme_file))
    return failures


_RULING_LABEL_RE = re.compile(r"\**\s*(COPY IN|READ ONLY)\b", re.IGNORECASE)


def _ruling_label(ruling: str) -> str:
    """The verdict a `LICENCE.md`'s `Ruling` field leads with (`COPY IN` or `READ ONLY`), for
    `main()`'s one-line-per-pack report — not the sentence or two of reasoning that follows it."""
    match = _RULING_LABEL_RE.match(ruling)
    return match.group(1).upper() if match else ruling


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    docs_file = REPO / "docs" / "asset-packs.md"
    readme_file = REPO / "README.md"

    for assets_root, _size_budget_bytes in ASSET_ROOTS:
        print(f"asset_packs: {assets_root.relative_to(REPO)}\n")
        for pack_dir in _pack_dirs(assets_root):
            licence_path = pack_dir / "LICENCE.md"
            fields = parse_licence_fields(read(licence_path)) if licence_path.is_file() else {}
            ruling = _ruling_label(fields.get("Ruling") or "UNRECORDED")
            checked = fields.get("Checked") or "UNRECORDED"
            print(f"  {pack_dir.name}: {ruling} (checked {checked})")
        print()

    failures = check_asset_roots(roots=ASSET_ROOTS, docs_file=docs_file, readme_file=readme_file)

    if failures:
        print()
        for failure in failures:
            print(f"  FAIL  {failure}")
        print(f"\n{len(failures)} failure(s).")
        return 1
    print("\nclean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
