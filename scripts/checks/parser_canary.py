#!/usr/bin/env python3
"""Parser canary: can we still read a real replay?

Parses the committed reference fixture with every engine we know about and reports which ones work.
This is how we learn that a game patch broke a parser — the failure mode that silently killed
aoestats for six months.

Usage:  uv run --with aoe2rec-py --with mgz scripts/checks/parser_canary.py [path/to/replay.zip]
Exit:   0 if the primary engine (aoe2rec-py) works, 1 otherwise. Secondary engines only report.
"""

from __future__ import annotations

import io
import re
import sys
import time
import zipfile
from pathlib import Path

FIXTURE = Path("tests/fixtures/replays/AgeIIDE_Replay_500546441.zip")
MEMBER_RE = re.compile(r"^AgeIIDE_Replay_\d+\.aoe2record$")
MAX_RATIO = 40  # observed ratio is x7.9; anything far above is a zip bomb


def _dist_version(name: str) -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version(name)
    except PackageNotFoundError:
        return "unknown"


def load(path: Path) -> bytes:
    raw = path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        members = zf.infolist()
        if len(members) != 1:
            raise ValueError(f"expected exactly one member, found {len(members)}")
        member = members[0]
        if not MEMBER_RE.match(member.filename):
            raise ValueError(f"unexpected member name {member.filename!r}")
        if member.file_size > len(raw) * MAX_RATIO:
            raise ValueError(f"suspicious compression ratio for {member.filename!r}")
        return zf.read(member)


def try_aoe2rec(data: bytes) -> tuple[bool, str]:
    try:
        from aoe2rec_py import aoe2rec_py as native
    except ImportError as exc:
        return False, f"not installed: {exc}"
    version = _dist_version("aoe2rec-py")
    try:
        start = time.perf_counter()
        rec = native.parse_rec(data)
        elapsed = time.perf_counter() - start
    except Exception as exc:  # noqa: BLE001
        return False, f"{version}: {type(exc).__name__}: {exc}"

    ops = rec["operations"]
    actions = [k for op in ops if "Action" in op for k in op["Action"]["action_data"]]
    if "Build" not in actions:
        return False, f"{version}: parsed but found no Build action — output looks wrong"
    if "Research" not in actions:
        return False, f"{version}: parsed but found no Research action — output looks wrong"
    build = rec["zheader"].get("build")
    return True, f"{version}: {len(ops)} operations in {elapsed:.2f}s (game build {build})"


def try_mgz(data: bytes) -> tuple[bool, str]:
    try:
        from mgz.model import parse_match
    except ImportError as exc:
        return False, f"not installed: {exc}"
    v = _dist_version("mgz")
    try:
        start = time.perf_counter()
        match = parse_match(io.BytesIO(data))
        elapsed = time.perf_counter() - start
    except Exception as exc:  # noqa: BLE001
        return False, f"{v}: {type(exc).__name__}: {str(exc).strip() or '(no message)'}"
    return True, f"{v}: map {match.map.name} in {elapsed:.2f}s"


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else FIXTURE
    if not path.exists():
        print(f"fixture not found: {path}")
        return 1

    data = load(path)
    print(f"fixture: {path} ({len(data)} bytes extracted)\n")

    engines = [("aoe2rec-py (primary)", try_aoe2rec), ("aoc-mgz (secondary)", try_mgz)]
    results = {}
    for name, fn in engines:
        ok, detail = fn(data)
        results[name] = ok
        print(f"{'PASS' if ok else 'FAIL'}  {name:24s} {detail}")

    primary_ok = results["aoe2rec-py (primary)"]
    print()
    if not primary_ok:
        print("The primary parser cannot read a known-good replay. V2 analysis is blocked.")
        print("See docs/adr/0001-replay-parser.md for the fallback options.")
        return 1
    if not results["aoc-mgz (secondary)"]:
        print("Secondary engine is down. Expected as of 2026-08: see aoc-mgz issue #138.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
