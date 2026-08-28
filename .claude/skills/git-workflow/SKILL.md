---
name: git-workflow
description: How to branch, commit, push and open a PR on this project — the ordering rules, the checks that must run first, and the failures that produced each one. Load before any git action beyond reading status, and before opening or updating a pull request.
---

# Git and PR workflow

**The always-in-force rules are in [`CLAUDE.md`](../../../CLAUDE.md) under "Working autonomously" and
"Commits".** This skill is the detail behind them: the order operations go in, and the specific
failures that each rule exists to prevent.

Every rule below was written after it was broken, in one session on 2026-08-27/28. None is
hypothetical. The dates are kept because a rule with a scar attached gets followed and a rule
without one gets reasoned around.

## Before anything else: orient against the remote

```bash
git fetch origin && git status -sb
```

**`git log main` without a fetch is not evidence about `main`.** The local ref is whatever it was
when it was last updated, which may be months stale.

_What this cost:_ `main` was read locally, found to be 176 commits behind, and concluded to be
ancient. It was not — `origin/main` was current. Work proceeded on a branch cut before three PRs had
merged, and **an entire phase (003's T396–T400) was reimplemented from scratch after PR #11 had
already merged it.** Four commits of duplicated work, then a rebase to remove them.

Then, before starting any phase or task list:

- **Check whether the work is already done on the remote.** `tasks.md` on a stale branch shows the
  checkbox state of that branch, not of the project. Confirm against `origin/main`:
  ```bash
  git show origin/main:specs/<feature>/tasks.md | grep -E '^- \[[ x]\] T<id>'
  ```
- **Check whether the branch you are on has already been merged.** A branch whose PR merged is not a
  place to add commits — new work there does not reopen the PR and the branch name no longer
  describes the contents.
  ```bash
  gh pr list --state merged --limit 5 --json number,title,headRefName
  ```

_What this cost:_ eight commits were stacked on `constitution/ix-consent-retired` after its PR #12
had merged, and the branch name described only half of what it then carried.

## One branch, one PR, opened early

A branch exists to become a pull request. Cut it from a freshly-fetched `origin/main`, name it for
what it actually contains, and **open the PR when the first commit lands, not when the last one
does.** A PR opened early is a place to record the deploy sequence and the open questions while they
are still being decided; a PR opened at the end is an artifact written from memory.

If the contents outgrow the name — a branch called `constitution/ix-consent-retired` that also
carries an unrelated phase — rename the branch or split the work. The name is how the next reader
finds it.

## Commit discipline

`CLAUDE.md`'s "Commits" section sets the granularity: **the smallest set of tasks that was ever
simultaneously green.** Two additions from experience:

### The task list does not tell you the commit unit

`tasks.md` says so explicitly for 003's T304/T305 ("the two are never separately green") and says
nothing anywhere else. That silence is not a claim that every other task is green alone.

**Before committing a change that removes or renames anything, grep for its consumers.** If they are
not in the same commit, the commit is red and the unit is wrong.

_What this cost:_ T403 dropped two `users` columns and committed alone. Ninety-six tests across
eighteen files still constructed `User(ingest_consent_at=...)`. The commit is in history and is red
in isolation.

### Run the whole suite, not the tests you were told about

An agent's hand-back names the failures it noticed. Verifying only those inherits its blind spot.

```bash
uv run pytest -q          # the whole workspace, ~45 s
```

_What this cost:_ the same T403 commit. Its hand-back mentioned one out-of-scope failure; that one
file was checked and the commit went in. The real number was 96.

### The gate

`scripts/hooks/git-preflight.sh` enforces the two above mechanically — branch freshness cheaply on
every commit, the full suite on push. It exists because **`CLAUDE.md` already said "never commit a
red tree" and a red tree was committed anyway.** Prose that has already failed once is not a control.

## Verifying an agent's work

See [[verify-implementer-handback]] in memory for the long version. The two that bite here:

- **A degenerate hand-back is not a no-op.** Four agents in one session returned `"Holding."`,
  `"Unchanged. Final."`, `"No action taken."` and `"(no further action — position unchanged)"`. Every
  one had done substantial, correct work; one had already committed. Check `git status`, `git log`
  and the suite before re-dispatching, or you will duplicate or clobber real work.
- **Read the staged diff for files outside the task's named paths.** Usually it is a legitimate
  consequence the task text missed — `reconcile.py` was a second consumer of the gate T404 split, and
  had to change. Occasionally it is a sibling's file being "helpfully" repaired. Check which.

## Deploying a migration

The full procedure is [`docs/runbooks/database-migrations.md`](../../../docs/runbooks/database-migrations.md).
The rule that belongs here, because it is a _sequencing_ rule and not a database one:

**A migration that both adds and drops cannot be deployed without an outage.** Applied before the
code, the live tree reads columns that are gone. Applied after, the new code reads a column that does
not exist. Split it: expand (add and backfill, drop nothing) applies before the deploy; contract
(drop only) applies after the deploy is confirmed healthy.

**Detect the deploy rather than assuming it.** `/api/health` reports the _deployed build's_ expected
schema revision, which is a precise signal for whether the new code is live:

```bash
curl -sS https://aoe2-stats.com/api/health
```

Between expand and the deploy, that endpoint answers `503 schema_out_of_date`. That is T394's check
working, not a fault — expand only adds, and every route still serves. It also means `smoke.yml` and
the nightly `production-smoke` job fail for that window, so **merge and apply the contract in one
sitting** rather than leaving the gap open overnight.

## When something outranks the task you are on

Constitution I is a tie-break rule and it applies to the workflow too. This session found, while
walking a verification task, that **replay capture had been failing for every match** because
`aoe.ms` began answering 301 and `httpx` does not follow redirects by default. Fifty-six recordings
were already unrecoverable.

Finishing the original task first would have cost more of them. Stop, fix the thing that is losing
data, and say plainly in the report that the original task is unfinished and why.
