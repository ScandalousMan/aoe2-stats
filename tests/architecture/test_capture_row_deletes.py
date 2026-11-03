"""T459m: only GDPR erasure deletes a `replay_captures` row (FR-037).

The capture worker (`CaptureDrain`) removes the object it just wrote when no capture row is left
for its `(game_id, profile_id)`. That is correct only if a missing row means an erasure removed it.
This test scans the production modules for another place that deletes from `replay_captures` and
fails naming it, so the assumption is checked rather than only written down.

What it detects: a `delete(ReplayCapture)` / `ReplayCapture.__table__.delete()` construct, a
`session.delete(...)` / `.delete(...)` call whose argument or receiver names `ReplayCapture`, and
SQL text `DELETE FROM replay_captures`. It does not see a delete reached some other way (a foreign
key `ON DELETE CASCADE` from a parent table, or SQL assembled at runtime); such a path is outside
what this scan guarantees. Scope is production `src/` trees, `api/` and `scripts/`, never `tests/`
or Alembic revisions.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCAN_ROOTS = ("apps", "packages", "api", "scripts")
_ERASURE_MODULE = "apps/api/src/aoe2stats_api/routers/privacy.py"
_SQL_DELETE = re.compile(r"delete\s+from\s+(?:public\.)?replay_captures\b", re.IGNORECASE)
_EXCLUDED_PARTS = {"tests", "alembic", "node_modules", ".venv", "__pycache__"}


def _mentions_capture_model(node: ast.AST) -> bool:
    return any(
        (isinstance(n, ast.Name) and n.id == "ReplayCapture")
        or (isinstance(n, ast.Attribute) and n.attr == "ReplayCapture")
        for n in ast.walk(node)
    )


def capture_deletes(source: str) -> list[int]:
    """Line numbers where `source` deletes from `replay_captures`."""
    lines: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, (ast.Name, ast.Attribute))
            and getattr(node.func, "id", getattr(node.func, "attr", None)) == "delete"
            and _mentions_capture_model(node)
        ) or (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and _SQL_DELETE.search(node.value)
        ):
            lines.append(node.lineno)
    return sorted(set(lines))


def _production_modules() -> Iterator[Path]:
    for root in _SCAN_ROOTS:
        for path in (_REPO_ROOT / root).rglob("*.py"):
            if not _EXCLUDED_PARTS.intersection(path.relative_to(_REPO_ROOT).parts):
                yield path


def test_only_the_erasure_module_deletes_from_replay_captures() -> None:
    offenders = [
        f"{path.relative_to(_REPO_ROOT).as_posix()}:{line}"
        for path in _production_modules()
        if path.relative_to(_REPO_ROOT).as_posix() != _ERASURE_MODULE
        for line in capture_deletes(path.read_text(encoding="utf-8"))
    ]
    assert offenders == [], (
        f"{offenders} delete from replay_captures; the capture worker's cleanup assumes erasure "
        f"({_ERASURE_MODULE}) is the only path that does"
    )


def test_the_scan_sees_the_erasure_module_delete() -> None:
    """Contrast: the detector finds the real delete, so a clean tree is not a blind detector."""
    source = (_REPO_ROOT / _ERASURE_MODULE).read_text(encoding="utf-8")
    assert capture_deletes(source) != []


def test_the_scan_flags_each_delete_shape() -> None:
    assert capture_deletes("from m import ReplayCapture\nx = delete(ReplayCapture)\n") == [2]
    assert capture_deletes("async def f(s, c: ReplayCapture):\n    await s.delete(c)\n") == []
    assert capture_deletes("async def f(s):\n    await s.delete(ReplayCapture())\n") == [2]
    assert capture_deletes("q = 'DELETE FROM replay_captures WHERE id = 1'\n") == [1]
    assert capture_deletes("q = delete(Match)\n") == []
