#!/usr/bin/env bash
# PostToolUse hook: format the file that was just edited.
# Never blocks a session: always exits 0, whatever happens.
set -uo pipefail

payload="$(cat 2>/dev/null || true)"
file="$(printf '%s' "$payload" | python3 -c 'import json,sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
ti = d.get("tool_input") or {}
print(ti.get("file_path") or ti.get("path") or "")
' 2>/dev/null || true)"

[ -z "$file" ] && exit 0
[ -f "$file" ] || exit 0

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

case "$file" in
  *.py)
    command -v uv >/dev/null 2>&1 || exit 0
    uv run --quiet ruff format "$file" >/dev/null 2>&1 || true
    uv run --quiet ruff check --fix "$file" >/dev/null 2>&1 || true
    ;;
  *.ts|*.tsx|*.js|*.jsx|*.css|*.json|*.md)
    command -v pnpm >/dev/null 2>&1 || exit 0
    pnpm exec prettier --write "$file" >/dev/null 2>&1 || true
    case "$file" in
      *.ts|*.tsx|*.js|*.jsx) pnpm exec eslint --fix "$file" >/dev/null 2>&1 || true ;;
    esac
    ;;
esac

exit 0
