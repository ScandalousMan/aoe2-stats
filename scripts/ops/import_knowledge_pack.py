#!/usr/bin/env python3
"""Network-free import of the `SiegeEngineers/aoe2techtree` pack (MIT) into
`packages/knowledge/packs/aoe2techtree/`, from a **local checkout** a human has already cloned, at
a **stated commit** the operator names on the command line (research.md D3, T635).

**Why this exists.** `contracts/knowledge-base.md` draws the line explicitly: "A pack is raw; a
snapshot is derived from it and says so." Getting the raw pack into the repository is a separate,
manual, offline step from normalising it into a queryable snapshot (`snapshot.py`, T638-T639) —
this script is only the first half, and it never decides what a value means.

**Network-free by construction — read this before adding an import.** Constitution rule: "No
external network call outside `packages/providers`." `scripts/checks/contract_sources.py`'s own
module docstring names itself as the *only* check allowed to touch the network; nothing here is
that check, and `packages/knowledge` has no dependency on `packages/providers` at all (its
`pyproject.toml` depends on `aoe2stats-core` only). `--source-checkout` is a **local** folder the
operator has already populated by cloning `SiegeEngineers/aoe2techtree` and checking out the commit
named by `--commit` — this script never clones, fetches, or resolves that commit against any
remote. Do not add `httpx`, `requests`, `urllib.request`, `git+https://...` cloning, or a raw
socket call to this file — there is no legitimate reason for one here, and constitution enforcement
will reject it.

**Automating the download is the moment a provider becomes mandatory (FR-032).** FR-032 requires
that "any refresh MUST happen outside the request path and MUST go through `packages/providers`" —
and that requirement is satisfied *vacuously* today, by there being no automated refresh at all.
The instant a future change teaches this script (or anything else) to `git clone` or `curl` the
source itself, it starts making an external network call on this repository's behalf, and
constitution III stops permitting it to live in `scripts/ops/`: that call belongs in
`packages/providers`, wrapped in the timeout, retry/backoff, rate limiting and `provider_calls`
record every other external source already carries. Do not make that change here. If the download
is ever automated, add the provider in the same change — do not let this script grow a fetch while
staying in `scripts/ops/`.

**Reads a local checkout only, and refuses rather than partially imports.** `plan_import` resolves
the manifest (by default `data.json`, `strings.en.json`, `trees` — the pack contents `plan.md`'s
Project Structure names) against `--source-checkout` before anything is written. If any manifest
entry is missing, `apply_import` writes nothing at all: a half-copied pack would carry files
described by no recorded digest, which is exactly the drift `contracts/knowledge-base.md`'s
format-check note depends on not happening. This mirrors `scripts/ops/sync_map_thumbnails.py`'s own
"never destroy or half-write on a failure" discipline, adapted to a one-shot import instead of a
reconciling sync.

**Dry-run by default**, matching `scripts/ops/sync_map_thumbnails.py`'s and
`scripts/ops/acknowledge_alerts.py`'s own convention: this script reports what it would import and
writes nothing until `--apply` is passed.

**Records what it wrote, not what it fetched.** A successful `--apply` run writes
`packages/knowledge/packs/aoe2techtree/MANIFEST.json`, recording the stated `--commit`, the import
timestamp, and a `sha256` digest per copied file. That digest is what the format-check carve-out
test compares against later — the pack's bytes must never be silently rewritten by a formatter — and
it is not a claim about the source's own integrity: nothing here reaches the source to check it.

**What this script does not do (out of scope for T635).** It does not vendor the real pack at the
real pinned commit (T636); it does not write `LICENCE.md` (T636, by hand, since the five-field
record is a human attestation, not something derivable from file bytes); it does not normalise the
pack into a queryable snapshot (`snapshot.py`, T638); and it does not verify `--commit` against the
checkout's own git history — the checkout was already prepared by a human, and this script trusts
what it is pointed at, the same way `sync_map_thumbnails.py` trusts `--source-dir`.

Usage:
    uv run scripts/ops/import_knowledge_pack.py \\
        --source-checkout /path/to/aoe2techtree --commit <sha>
    uv run scripts/ops/import_knowledge_pack.py \\
        --source-checkout /path/to/aoe2techtree --commit <sha> --apply

Exit: 0 on a completed run that found every manifest entry (dry-run or apply); 1 if the invocation
is refused (`--source-checkout` missing or not a directory, blank `--commit`, `--apply` and
`--dry-run` both given) or if any manifest entry is missing from the checkout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

#: The source this script imports — named exactly as research.md D3 names it, so a reader of a
#: written `MANIFEST.json` can find the decision that chose it without guessing at a spelling.
_SOURCE_NAME = "SiegeEngineers/aoe2techtree"

#: The pack this script writes — derived from this file's own location, never hardcoded as an
#: absolute path, so the script works the same from any checkout (mirrors
#: `sync_map_thumbnails.py`'s `_MAPS_PACK_DIR`).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_PACK_DIR = _REPO_ROOT / "packages" / "knowledge" / "packs" / "aoe2techtree"

#: The pack's expected top-level contents, per `plan.md`'s Project Structure
#: (`packages/knowledge/packs/aoe2techtree/{data.json,trees/,strings.en.json}`). Overridable with
#: one or more `--include` flags, in case the real checkout's layout at the pinned commit (T636)
#: does not match this default — this script does not assume it has ever seen the real source.
_DEFAULT_MANIFEST: tuple[str, ...] = ("data.json", "strings.en.json", "trees")

_MANIFEST_FILENAME = "MANIFEST.json"


@dataclass(frozen=True, slots=True)
class ImportPlan:
    """What one run of `plan_import` found under `--source-checkout`, before anything is written.
    `files` is every relative path the manifest resolves to, flattened (a directory entry expands
    to every file under it); `missing` is every manifest entry — file or directory — that does not
    exist there at all."""

    files: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ImportReport:
    """What one run found (`plan`) and, if `apply` was requested and nothing was missing, wrote.
    `written` and `digests` stay empty for a dry run or a refused (missing-entry) invocation — a
    run that writes nothing records nothing, so a reader can never mistake a report for evidence
    of a write that did not happen."""

    plan: ImportPlan
    written: tuple[str, ...] = ()
    digests: dict[str, str] = field(default_factory=dict)
    apply: bool = False
    commit: str = ""


def _relative_files_under(source_checkout: Path, entry: str) -> list[str] | None:
    """Every file `entry` names, relative to `source_checkout`, as POSIX-style relative paths —
    or `None` if `entry` does not exist at all under `source_checkout`. Returning `None` rather
    than raising lets `plan_import` assemble the whole plan, missing entries included, before any
    refusal is decided."""
    target = source_checkout / entry
    if target.is_file():
        return [entry]
    if target.is_dir():
        return sorted(
            (Path(entry) / path.relative_to(target)).as_posix()
            for path in target.rglob("*")
            if path.is_file()
        )
    return None


def plan_import(source_checkout: Path, manifest: Sequence[str] = _DEFAULT_MANIFEST) -> ImportPlan:
    """Read-only: resolves `manifest` (relative files or directories under `source_checkout`) into
    the flat list of files that would be copied, without touching `packages/knowledge/` at all.
    `apply_import` below is the only function that writes, and it always calls this first."""
    files: list[str] = []
    missing: list[str] = []
    for entry in manifest:
        resolved = _relative_files_under(source_checkout, entry)
        if resolved is None:
            missing.append(entry)
        else:
            files.extend(resolved)
    return ImportPlan(files=tuple(files), missing=tuple(missing))


def _sha256_of(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def apply_import(
    source_checkout: Path,
    pack_dir: Path,
    *,
    commit: str,
    manifest: Sequence[str] = _DEFAULT_MANIFEST,
    apply: bool,
) -> ImportReport:
    """Runs `plan_import`, then — only when `apply` is set and no manifest entry is missing —
    copies every resolved file into `pack_dir` and writes `MANIFEST.json` recording the stated
    `commit`, the import timestamp, and each file's `sha256` digest. A missing manifest entry
    refuses the whole write, never a partial one (see the module docstring)."""
    plan = plan_import(source_checkout, manifest)
    if not apply or plan.missing:
        return ImportReport(plan=plan, apply=False, commit=commit)

    digests: dict[str, str] = {}
    for relative in plan.files:
        source_path = source_checkout / relative
        destination_path = pack_dir / relative
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)
        digests[relative] = _sha256_of(destination_path)

    manifest_record = {
        "source": _SOURCE_NAME,
        "commit": commit,
        "imported_at": datetime.now(UTC).isoformat(),
        "files": dict(sorted(digests.items())),
    }
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / _MANIFEST_FILENAME).write_text(
        json.dumps(manifest_record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    return ImportReport(plan=plan, written=plan.files, digests=digests, apply=True, commit=commit)


def _print_report(report: ImportReport) -> None:
    verb = "written" if report.apply else "would be written"
    print(
        f"import-knowledge-pack: {len(report.plan.files)} file(s) {verb}, "
        f"{len(report.plan.missing)} missing."
    )
    if report.plan.missing:
        print(f"  missing: {', '.join(report.plan.missing)}")
        print(
            "  refused — every manifest entry must exist under --source-checkout before "
            "anything is written."
        )
        return

    if report.written:
        print(f"  files: {', '.join(report.written)}")
        print(f"  commit: {report.commit}")

    if not report.apply:
        print("\nDry-run: nothing was written. Pass --apply to write.")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Import packages/knowledge/packs/aoe2techtree/ from a local checkout of "
            "SiegeEngineers/aoe2techtree at a stated commit. Never clones or fetches — "
            "--source-checkout is a folder the operator already populated. Dry-run by default; "
            "pass --apply to write. See this script's own module docstring and research.md D3."
        )
    )
    parser.add_argument(
        "--source-checkout",
        required=True,
        type=Path,
        help="a local folder already checked out from SiegeEngineers/aoe2techtree at --commit — "
        "never cloned or fetched by this script",
    )
    parser.add_argument(
        "--commit",
        required=True,
        help="the commit the checkout is stated to be pinned at (research.md D3); recorded in "
        "MANIFEST.json, never verified against the checkout's own git history by this script",
    )
    parser.add_argument(
        "--include",
        dest="manifest",
        action="append",
        default=None,
        metavar="PATH",
        help="a relative file or directory under --source-checkout to copy into the pack; "
        f"repeatable. Defaults to {_DEFAULT_MANIFEST!r} (plan.md's Project Structure) when omitted",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the pack. Without this flag, nothing changes",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="explicit spelling of the default (no --apply): report what would be imported and "
        "write nothing — mutually exclusive with --apply",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.apply and args.dry_run:
        print("import-knowledge-pack: refused — --apply and --dry-run are mutually exclusive.")
        return 1

    source_checkout: Path = args.source_checkout
    if not source_checkout.is_dir():
        print(
            f"import-knowledge-pack: refused — --source-checkout {source_checkout} is not a "
            "directory."
        )
        return 1

    commit = (args.commit or "").strip()
    if not commit:
        print("import-knowledge-pack: refused — --commit must not be blank.")
        return 1

    manifest: tuple[str, ...] = tuple(args.manifest) if args.manifest else _DEFAULT_MANIFEST

    report = apply_import(
        source_checkout, _PACK_DIR, commit=commit, manifest=manifest, apply=bool(args.apply)
    )
    _print_report(report)

    return 1 if report.plan.missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
