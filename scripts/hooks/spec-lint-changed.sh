#!/usr/bin/env bash
# PostToolUse hook: run the cross-artifact spec lint on the feature a specs/ edit just touched.
#
# format-changed.sh formats a file the instant it is written; a tasks.md amended by hand was
# otherwise only checked by the `specs` CI job, minutes later and after a push. Scoped to edits
# under specs/ so a normal source edit pays nothing.
#
# Reporting follows gate-implementer.sh: on a real finding, print which check tripped (spec_lint.py
# already prefixes each failure with the check name and line/task reference) and exit 2 so Claude
# Code surfaces it. Anything that is not a lint finding — no uv, no such feature directory, an
# early-stage feature still missing plan.md or data-model.md, a timeout — degrades silently like
# format-changed.sh: exit 0, never block unrelated work.
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

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

# Only pay the cost on edits under specs/ — a repository can hold several feature directories, so
# the feature to lint is derived from the edited path rather than hard-coded.
case "$file" in
  specs/*) ;;
  *) exit 0 ;;
esac

feature_dir="$(printf '%s\n' "$file" | sed -n 's#^\(specs/[^/]*\)/.*#\1#p')"
[ -z "$feature_dir" ] && exit 0
[ -f "$feature_dir/tasks.md" ] || exit 0

command -v uv >/dev/null 2>&1 || exit 0

out="$(uv run --quiet scripts/checks/spec_lint.py --feature "$feature_dir" 2>&1)"
status=$?

# 0: clean. 2: spec_lint.py's own infrastructure failure (missing required artifact) — an
# early-stage feature, not a finding to act on. Anything else is a real finding.
[ "$status" -eq 0 ] && exit 0
[ "$status" -eq 2 ] && exit 0

echo "spec_lint: $feature_dir (edited $file) — see the failing check(s) below:" >&2
printf '%s\n' "$out" >&2
exit 2
