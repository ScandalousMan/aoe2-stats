#!/usr/bin/env bash
# SubagentStop hook for `implementer`: refuse to hand back on red tests.
# Exit 2 returns the failure to the agent so it must fix it.
set -uo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
command -v git >/dev/null 2>&1 || exit 0
git rev-parse --git-dir >/dev/null 2>&1 || exit 0

changed="$(git diff --name-only HEAD 2>/dev/null; git ls-files --others --exclude-standard 2>/dev/null)"
[ -z "$changed" ] && exit 0

failed=0
out=""

if printf '%s' "$changed" | grep -qE '\.py$' && command -v uv >/dev/null 2>&1; then
  if ! out="$(uv run --quiet pytest -q 2>&1)"; then
    failed=1
  fi
fi

if [ "$failed" -eq 0 ] && printf '%s' "$changed" | grep -qE '\.(ts|tsx)$' && command -v pnpm >/dev/null 2>&1; then
  if ! out="$(pnpm test 2>&1)"; then
    failed=1
  fi
fi

if [ "$failed" -eq 1 ]; then
  echo "Tests are failing. You may not finish this task until they pass." >&2
  printf '%s\n' "$out" | tail -40 >&2
  exit 2
fi

exit 0
