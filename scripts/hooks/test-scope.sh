#!/usr/bin/env bash
# Stop hook: run only the tests covering what changed. Advisory — never blocks.
set -uo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
command -v git >/dev/null 2>&1 || exit 0
git rev-parse --git-dir >/dev/null 2>&1 || exit 0

changed="$(git diff --name-only HEAD 2>/dev/null; git ls-files --others --exclude-standard 2>/dev/null)"
[ -z "$changed" ] && exit 0

py_targets=()
run_web=0
while IFS= read -r f; do
  case "$f" in
    apps/api/*)      py_targets+=("apps/api") ;;
    apps/ingester/*) py_targets+=("apps/ingester") ;;
    apps/parser/*)   py_targets+=("apps/parser") ;;
    packages/core/*|packages/providers/*|packages/storage/*|api/*) py_targets+=("packages" "api") ;;
    apps/web/*|packages/design-system/*) run_web=1 ;;
  esac
done <<< "$changed"

if [ ${#py_targets[@]} -gt 0 ] && command -v uv >/dev/null 2>&1; then
  uniq_targets="$(printf '%s\n' "${py_targets[@]}" | sort -u | tr '\n' ' ')"
  # shellcheck disable=SC2086
  uv run --quiet pytest -q $uniq_targets 2>&1 | tail -20 || true
fi

if [ "$run_web" -eq 1 ] && command -v pnpm >/dev/null 2>&1; then
  pnpm vitest run --changed 2>&1 | tail -20 || true
fi

exit 0
