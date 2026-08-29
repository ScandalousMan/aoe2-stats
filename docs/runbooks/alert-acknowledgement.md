# Runbook: acknowledging an `alerts` row

`scripts/checks/alert_audit.py` fails the nightly build on any unacknowledged severity-1 `alerts`
row — `deadline_breach` or `expired_capture`, the two kinds meaning a replay is gone or about to
be (constitution I). Nothing else in this repository ever writes `acknowledged_at`: grep confirms
it, the column is written only by tests. Before `scripts/ops/acknowledge_alerts.py` existed,
acknowledging an alert meant hand-writing an `UPDATE` against production, with no record of what
was acknowledged or why. This is the procedure now.

**Constitution I: acknowledge only after investigating, never before.** This script is dry-run by
default for exactly that reason — it prints which rows it would touch and changes nothing unless
`--apply` is given — and it requires a `--kind` plus either an explicit `--id` list or a bounded
`--since`/`--until` range. There is no invocation of it that means "acknowledge everything": a
blanket acknowledgement is how a real, still-uninvestigated alert gets buried under an old one.

## What is and is not auditable afterwards

`alerts` has no column for a reason, and this tool ships with no migration to add one — adding a
column is `docs/runbooks/database-migrations.md`'s whole procedure, not something to invoke for a
string field a nightly script can live without. `--reason` is mandatory on every invocation, but
it is **printed back at the end of the run and nowhere else** — paste it into the pull request or
incident write-up that this acknowledgement belongs to. What the database keeps after a run is
`acknowledged_at` itself: that a human looked, and when. It does **not** keep why — that lives only
in whichever PR or runbook entry the operator pastes the printed reason into. If that account
matters later, it exists nowhere the database can be asked for it.

## Why this needs the **pooled** endpoint, not the direct one

This is the opposite guidance from `docs/runbooks/database-migrations.md`, and deliberately so:
that runbook needs Neon's direct endpoint because Alembic issues DDL and needs session-level lock
semantics a transaction-mode pooler cannot give it. This script issues a single `SELECT` and, with
`--apply`, a single bulk `UPDATE` — ordinary application traffic, exactly the shape Neon's pooler
is built for. Use the same **pooled** connection string `.env.example` documents for the running
application, never the direct one.

## Why one command and a prompt, rather than an `export` you paste

Read `docs/runbooks/database-migrations.md`'s own "Why one command and a prompt" section before
running this: it records three traps that cost four failed attempts and a rotated credential in
one sitting — the console handing out the wrong URL scheme (`postgresql://` instead of
`postgresql+psycopg://`), zsh globbing the `?` in `?sslmode=require` when a connection string is
pasted unquoted, and a pasted password ending up in shell history or a chat window. All three apply
here exactly as they do there; only the endpoint (pooled, not direct) differs. The command below
uses the same shape — `read -rs` prompts for the value and echoes nothing — for the same reasons.

## Procedure

1. Get the **pooled** connection string from the Neon console, or reuse the value already in your
   `.env` — this is the same string the running application uses, not the direct one.
2. From the repository root, run one of the two commands below. Start with the first (no
   `--apply`) and read its output before running the second.

   Dry run — prints exactly which rows would be acknowledged, writes nothing:

   ```sh
   read -rs "RAW?Paste Neon POOLED url then Enter: "; export DATABASE_URL="postgresql+psycopg://${RAW#*://}"; print -r -- "host: ${${DATABASE_URL#*@}%%/*}"; uv run scripts/ops/acknowledge_alerts.py \
     --kind expired_capture \
     --since 2026-08-28T00:00:00+00:00 --until 2026-08-29T00:00:00+00:00 \
     --reason "aoe.ms 301 outage, fixed in PR #17; investigated 2026-08-29"
   ```

   Once the dry run's list matches what was actually investigated, re-run with `--apply` to write:

   ```sh
   read -rs "RAW?Paste Neon POOLED url then Enter: "; export DATABASE_URL="postgresql+psycopg://${RAW#*://}"; print -r -- "host: ${${DATABASE_URL#*@}%%/*}"; uv run scripts/ops/acknowledge_alerts.py \
     --kind expired_capture \
     --since 2026-08-28T00:00:00+00:00 --until 2026-08-29T00:00:00+00:00 \
     --reason "aoe.ms 301 outage, fixed in PR #17; investigated 2026-08-29" \
     --apply
   ```

3. Copy the reason line the script prints at the end into the pull request or incident write-up
   this acknowledgement belongs to — that is the only place it is kept.
4. Close the shell, or explicitly `unset DATABASE_URL`, so the credential does not linger in a
   long-running session.
5. Confirm `scripts/checks/alert_audit.py` now passes for this kind (it fails again immediately on
   the next unacknowledged severity-1 row, from any cause — this only ever clears what was actually
   investigated).

## Worked example: the 2026-08-28 `aoe.ms` outage backlog

Production held 57 unacknowledged severity-1 rows raised on 2026-08-28, when a capture backlog
drained after the `aoe.ms` 301 outage (fixed in PR #17): 56 `expired_capture` and 1
`deadline_breach`. Both kinds have now been investigated — the cause is known and documented above
— so both get acknowledged, as two separate invocations: `--kind` takes exactly one value, by
design, so a single kind's blast radius is never widened by bundling it with another.

```sh
read -rs "RAW?Paste Neon POOLED url then Enter: "; export DATABASE_URL="postgresql+psycopg://${RAW#*://}"; print -r -- "host: ${${DATABASE_URL#*@}%%/*}"; uv run scripts/ops/acknowledge_alerts.py \
  --kind expired_capture \
  --since 2026-08-28T00:00:00+00:00 --until 2026-08-29T00:00:00+00:00 \
  --reason "aoe.ms 301 outage, fixed in PR #17; investigated 2026-08-29" \
  --apply

uv run scripts/ops/acknowledge_alerts.py \
  --kind deadline_breach \
  --since 2026-08-28T00:00:00+00:00 --until 2026-08-29T00:00:00+00:00 \
  --reason "aoe.ms 301 outage, fixed in PR #17; investigated 2026-08-29" \
  --apply
```

`DATABASE_URL` is already exported for the session after the first command, so the second does not
need to re-prompt — as long as both run in the same shell before step 4 unsets it.
