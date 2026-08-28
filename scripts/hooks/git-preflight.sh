#!/usr/bin/env bash
# PreToolUse hook on Bash: refuse a `git commit` or `git push` that CLAUDE.md already forbids.
#
# Exit 2 blocks the call and returns the message to the agent, the same contract
# gate-implementer.sh uses. Exit 0 allows it.
#
# Why this exists rather than the prose alone: CLAUDE.md has said "never commit a red tree" since
# 001, and on 2026-08-27 a commit went in with 96 failing tests because only the one file an agent's
# hand-back mentioned was checked. The same session cut a branch from a stale local `main` and
# reimplemented a phase that had already merged. Both are mechanical, so both are checked here.
#
# Split by cost, deliberately:
#   commit -> freshness only (~1 s). Cheap, and it is the check that would have saved a whole phase.
#   push   -> the full suite (~45 s). Paid once per PR rather than once per task.
#
# Escape hatch: NO_GIT_PREFLIGHT=1 for the genuine exception (a deliberate WIP commit, a docs-only
# branch where the suite is irrelevant). Use it consciously; it is not the default for a reason.
set -uo pipefail

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
[ "${NO_GIT_PREFLIGHT:-0}" = "1" ] && exit 0
command -v git >/dev/null 2>&1 || exit 0
git rev-parse --git-dir >/dev/null 2>&1 || exit 0

# The command the agent is about to run arrives as JSON on stdin.
payload="$(cat 2>/dev/null || true)"
cmd="$(printf '%s' "$payload" | python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("tool_input",{}).get("command",""))
except Exception: print("")' 2>/dev/null)"
[ -z "$cmd" ] && exit 0

is_commit=0
is_push=0
printf '%s' "$cmd" | grep -qE '(^|[;&|]|\s)git\s+(-[^ ]+\s+)*commit(\s|$)' && is_commit=1
printf '%s' "$cmd" | grep -qE '(^|[;&|]|\s)git\s+(-[^ ]+\s+)*push(\s|$)'   && is_push=1
[ "$is_commit" -eq 0 ] && [ "$is_push" -eq 0 ] && exit 0

branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"

# --- Freshness: is this branch built on a stale view of the remote? ----------------------------
# Cheap, and the check that would have prevented a phase being reimplemented over an already-merged
# PR. Never blocks on a network failure — offline is not a reason to refuse a commit.
if git remote get-url origin >/dev/null 2>&1; then
  if timeout 20 git fetch --quiet origin 2>/dev/null; then
    base="origin/main"
    if git rev-parse --verify --quiet "$base" >/dev/null; then
      if [ "$branch" != "main" ] && ! git merge-base --is-ancestor "$base" HEAD 2>/dev/null; then
        behind="$(git rev-list --count "HEAD..$base" 2>/dev/null || echo '?')"
        {
          echo "This branch is $behind commit(s) behind $base."
          echo
          echo "CLAUDE.md and the git-workflow skill: orient against the remote before committing."
          echo "A branch cut from a stale view reimplements work that has already merged — that cost"
          echo "a whole phase on 2026-08-27."
          echo
          echo "Check what you are missing, then rebase or branch again:"
          echo "  git log --oneline HEAD..$base"
          echo "  git rebase $base"
          echo
          echo "If the divergence is intentional, re-run with NO_GIT_PREFLIGHT=1."
        } >&2
        exit 2
      fi
    fi
  fi
fi

# --- Merged-branch check: never stack new work on a branch whose PR already landed --------------
if [ "$is_push" -eq 1 ] && [ "$branch" != "main" ] && command -v gh >/dev/null 2>&1; then
  merged="$(timeout 20 gh pr list --state merged --head "$branch" --limit 1 \
              --json number --jq '.[0].number' 2>/dev/null || true)"
  if [ -n "$merged" ] && [ "$merged" != "null" ]; then
    {
      echo "Branch '$branch' already has a merged PR (#$merged)."
      echo
      echo "Pushing more commits here does not reopen it, and the branch name no longer describes"
      echo "what it carries. Cut a new branch from origin/main for this work:"
      echo "  git switch -c <new-branch> origin/main"
      echo
      echo "If you really mean to update this branch, re-run with NO_GIT_PREFLIGHT=1."
    } >&2
    exit 2
  fi
fi

# --- The suite, on push only --------------------------------------------------------------------
if [ "$is_push" -eq 1 ]; then
  range="origin/main..HEAD"
  git rev-parse --verify --quiet origin/main >/dev/null || range="HEAD"
  changed="$(git diff --name-only "$range" 2>/dev/null)"

  if printf '%s' "$changed" | grep -qE '\.py$' && command -v uv >/dev/null 2>&1; then
    if ! out="$(uv run --quiet pytest -q 2>&1)"; then
      {
        echo "Python tests are failing. Do not push a red tree (CLAUDE.md, Commits)."
        printf '%s\n' "$out" | tail -30
      } >&2
      exit 2
    fi
  fi

  if printf '%s' "$changed" | grep -qE '\.(ts|tsx)$' && command -v pnpm >/dev/null 2>&1; then
    if ! out="$(pnpm test 2>&1)"; then
      {
        echo "Front-end tests are failing. Do not push a red tree (CLAUDE.md, Commits)."
        printf '%s\n' "$out" | tail -30
      } >&2
      exit 2
    fi
  fi
fi

exit 0
