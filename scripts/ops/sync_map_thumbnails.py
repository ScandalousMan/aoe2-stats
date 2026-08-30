#!/usr/bin/env python3
"""Re-runnable, network-free sync of `packages/game-assets/maps/` against a local copy of
`SiegeEngineers/aoe2cm2`'s `public/images/maps/` (research.md D9, T448).

**Why this exists.** The pack in `packages/game-assets/maps/` is 435 hand-vendored WebP files, and
"synchronisation needed every time a new map is added to the pool" (D9) has no answer today
besides re-running the original by-hand copy from scratch. This script is that answer, made
repeatable: point it at a local folder of source PNGs and it reports, or (with `--apply`) writes,
exactly what the pack needs to add, change or (with `--prune`) remove to match.

**Network-free by construction — read this before adding an import.** Constitution rule: "No
external network call outside `packages/providers`." `scripts/checks/contract_sources.py`'s own
module docstring names itself as the *only* check allowed to touch the network; nothing here is
that check. `--source-dir` is a **local** folder the operator has already populated — this script
never fetches it. Downloading the source is a documented human step, run outside the repository:
see `docs/runbooks/map-thumbnail-sync.md`. Do not add `httpx`, `requests`, `urllib.request`, or a
raw socket call to this file — there is no legitimate reason for one here, and constitution
enforcement will reject it.

**Reproduces the committed pack.** The encoding parameters below (`Image.convert("RGBA")`, WebP,
`quality=80`, `method=6`) were determined empirically by re-encoding a fresh aoe2cm2 checkout and
byte-comparing the result against every one of the 435 committed files in
`packages/game-assets/maps/`: all 435 matched exactly. Running this script against a same-content
source directory therefore reports zero changes, which is also what makes it idempotent — a second
`--apply` run over an unchanged source writes nothing (bytes are compared before any file is
touched, and an unchanged file is left alone rather than rewritten).

**Slug transform.** `<source filename stem>.lower().replace(" ", "-")`, mirroring the resolver's
own `mapThumbnail()` key derivation (`packages/game-assets/src/index.ts`) and the naming the pack
already carries. Source filenames from aoe2cm2 are already kebab-case, so this is close to the
identity transform in practice — applied anyway so a source directory assembled by hand (rather
than a literal mirror of the upstream tree) still lands on the resolver's exact keys.

**Dry-run by default**, matching `scripts/ops/acknowledge_alerts.py`'s convention: this script
reports what it would do and writes nothing until `--apply` is passed. `--prune` is a separate,
opt-in flag (also off by default) for removing pack files whose map has left the pool — a map
disappearing from the source directory is reported either way, but only *removed* when `--prune`
is given, so a partial or mistakenly-narrow `--source-dir` cannot delete most of the pack by
accident.

Usage (see `docs/runbooks/map-thumbnail-sync.md` for the full worked procedure):
    uv run scripts/ops/sync_map_thumbnails.py --source-dir /path/to/aoe2cm2/maps --dry-run
    uv run scripts/ops/sync_map_thumbnails.py --source-dir /path/to/aoe2cm2/maps --apply
    uv run scripts/ops/sync_map_thumbnails.py --source-dir /path/to/aoe2cm2/maps --apply --prune

Exit: 0 on a completed run (dry-run or apply, with or without changes); 1 if `--source-dir` does
not exist or is not a directory.
"""

from __future__ import annotations

import argparse
import io
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

#: The encoding parameters that reproduce the committed pack byte-for-byte — see the module
#: docstring for how these were determined. Source images are natively 140x140, already under
#: research.md D5's 256px bound, so no resize step exists here: resizing an already-compliant
#: image would be a lossy no-op with no rule requiring it.
_WEBP_QUALITY = 80
_WEBP_METHOD = 6

#: The pack this script keeps in sync — derived from this file's own location, never hardcoded
#: as an absolute path, so the script works the same from any checkout.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_MAPS_PACK_DIR = _REPO_ROOT / "packages" / "game-assets" / "maps"

#: `LICENCE.md` is the pack's licence record, not a payload file — never a sync candidate for
#: add, change or prune.
_NON_PAYLOAD_NAMES = {"LICENCE.md"}


def slugify(stem: str) -> str:
    """The resolver's own key derivation (`mapThumbnail()`,
    `packages/game-assets/src/index.ts`): lowercase, spaces to hyphens. Applied to a source
    filename's stem, defensively — aoe2cm2's own filenames are already kebab-case, so this is the
    identity transform for a literal mirror of the upstream tree, but a source directory assembled
    by hand might not be."""
    return stem.lower().replace(" ", "-")


def encode_webp(source_png_path: Path) -> bytes:
    """Re-encode one source PNG into the exact WebP bytes the committed pack uses — see the module
    docstring for how `_WEBP_QUALITY`/`_WEBP_METHOD` were chosen and verified."""
    with Image.open(source_png_path) as image:
        rgba = image.convert("RGBA")
        buffer = io.BytesIO()
        rgba.save(buffer, format="WEBP", quality=_WEBP_QUALITY, method=_WEBP_METHOD)
        return buffer.getvalue()


@dataclass(frozen=True, slots=True)
class SyncReport:
    """What one run found and, if `apply` was set, changed. `removable` is always populated by
    `plan_sync` regardless of `--prune` — a dropped map is always *reported* — but only *acted on*
    (see `apply_sync`) when `--prune` was given; `pruned` records what actually happened, separate
    from what merely could have."""

    added: tuple[str, ...] = field(default_factory=tuple)
    changed: tuple[str, ...] = field(default_factory=tuple)
    unchanged: tuple[str, ...] = field(default_factory=tuple)
    removable: tuple[str, ...] = field(default_factory=tuple)
    pruned: tuple[str, ...] = field(default_factory=tuple)
    apply: bool = False
    prune: bool = False


def _pack_slugs(maps_dir: Path) -> set[str]:
    if not maps_dir.is_dir():
        return set()
    return {
        entry.stem
        for entry in maps_dir.iterdir()
        if entry.is_file() and entry.suffix == ".webp" and entry.name not in _NON_PAYLOAD_NAMES
    }


def _source_slugs(source_dir: Path) -> dict[str, Path]:
    """`{slug: source PNG path}` for every `*.png` in `source_dir`, keyed through `slugify` so a
    caller's own slug always matches `_pack_slugs`'s naming regardless of the source's casing or
    spacing."""
    return {slugify(entry.stem): entry for entry in source_dir.iterdir() if entry.suffix == ".png"}


def plan_sync(source_dir: Path, maps_dir: Path) -> SyncReport:
    """Read-only: compares `source_dir` against `maps_dir` and classifies every slug into added,
    changed, unchanged or removable, without writing anything. `apply_sync` below is the only
    function that writes, and it always calls this first."""
    source_by_slug = _source_slugs(source_dir)
    existing_slugs = _pack_slugs(maps_dir)

    added: list[str] = []
    changed: list[str] = []
    unchanged: list[str] = []

    for slug, source_path in sorted(source_by_slug.items()):
        target_path = maps_dir / f"{slug}.webp"
        candidate_bytes = encode_webp(source_path)
        if not target_path.is_file():
            added.append(slug)
        elif target_path.read_bytes() != candidate_bytes:
            changed.append(slug)
        else:
            unchanged.append(slug)

    removable = sorted(existing_slugs - set(source_by_slug))

    return SyncReport(
        added=tuple(added),
        changed=tuple(changed),
        unchanged=tuple(unchanged),
        removable=tuple(removable),
    )


def apply_sync(source_dir: Path, maps_dir: Path, *, apply: bool, prune: bool) -> SyncReport:
    """Runs `plan_sync`, then — only when `apply` is set — writes every added or changed file and,
    only when `prune` is also set, deletes every removable one. `plan_sync`'s own read of the
    existing bytes is what makes a real run idempotent: an unchanged file is never reopened for
    writing, so a second `--apply` run over the same source touches nothing on disk."""
    report = plan_sync(source_dir, maps_dir)
    source_by_slug = _source_slugs(source_dir)

    pruned: list[str] = []
    if apply:
        maps_dir.mkdir(parents=True, exist_ok=True)
        for slug in (*report.added, *report.changed):
            target_path = maps_dir / f"{slug}.webp"
            target_path.write_bytes(encode_webp(source_by_slug[slug]))
        if prune:
            for slug in report.removable:
                (maps_dir / f"{slug}.webp").unlink()
                pruned.append(slug)

    return SyncReport(
        added=report.added,
        changed=report.changed,
        unchanged=report.unchanged,
        removable=report.removable,
        pruned=tuple(pruned),
        apply=apply,
        prune=prune,
    )


def _print_report(report: SyncReport) -> None:
    verb = "would be " if not report.apply else ""

    print(
        f"sync-map-thumbnails: {len(report.unchanged)} unchanged, "
        f"{len(report.added)} {verb}added, {len(report.changed)} {verb}changed, "
        f"{len(report.pruned) if report.apply else len(report.removable)} "
        f"{'pruned' if report.apply and report.prune else verb + 'removed'}."
    )

    if report.added:
        print(f"  added: {', '.join(report.added)}")
    if report.changed:
        print(f"  changed: {', '.join(report.changed)}")
    if report.removable:
        if report.prune:
            label = "pruned" if report.apply else "would prune"
        else:
            label = "present in the pack but absent from source (pass --prune to remove)"
        print(f"  {label}: {', '.join(report.removable)}")

    if not report.apply:
        print("\nDry-run: nothing was written. Pass --apply to write.")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Sync packages/game-assets/maps/ against a local folder of aoe2cm2 map PNGs. "
            "Dry-run by default; pass --apply to write. See this script's own module docstring "
            "and docs/runbooks/map-thumbnail-sync.md."
        )
    )
    parser.add_argument(
        "--source-dir",
        required=True,
        type=Path,
        help="local folder of <slug>.png source images (a copy of aoe2cm2's "
        "public/images/maps/) — never fetched by this script",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the pack. Without this flag, nothing changes",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="explicit spelling of the default (no --apply): report what would change and write "
        "nothing. Accepted so a preview invocation can be shown, then re-run with --apply "
        "substituted for it — mutually exclusive with --apply",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="also remove pack files whose map is absent from --source-dir. Off by default: "
        "without it, extra pack files are reported but left alone",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.apply and args.dry_run:
        print("sync-map-thumbnails: refused — --apply and --dry-run are mutually exclusive.")
        return 1

    source_dir: Path = args.source_dir
    if not source_dir.is_dir():
        print(f"sync-map-thumbnails: refused — --source-dir {source_dir} is not a directory.")
        return 1

    report = apply_sync(source_dir, _MAPS_PACK_DIR, apply=bool(args.apply), prune=bool(args.prune))
    _print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
