# Runbook: applying a database migration to production

The deploy pipeline has no step that does this. `vercel.json` declares exactly one hook into
the deploy — `buildCommand`, which runs `config-preflight.mjs` ahead of `pnpm --filter web
build` (T391) — and no field for anything that runs after the deploy: there is nowhere in the
pipeline a migration could run even if it were wired in. `.github/workflows/pr.yml`'s
`alembic upgrade head` / `alembic check` / `alembic downgrade -1` sequence runs only against
the throwaway database that job creates and drops for the pull request; it never touches
production. Whoever merges a PR that ships a new revision under
`infra/migrations/versions/` is the one who runs this runbook, by hand, once, against Neon —
this is that procedure.

Skipping it is not hypothetical: `61d7bd9e3684` (`csrf_states`) and `1f9879367c9d` (this
feature's schema) were both applied to Neon by hand, after the fact, to end an outage the
missing step caused. `T394`'s `schema_out_of_date` health check makes the next occurrence
_visible_ rather than a silent 500 or a silent gap in the daily cron's writes — it does not
replace this runbook, it is the alarm for the case where this runbook was skipped.

## Why the pooled connection string in `.env.example` is the wrong one here

`DATABASE_URL` in `.env.example` documents Neon's **pooled** connection string, and that is
correct for the running application: the daily cron always hits a cold compute, and pooling
absorbs that. It is the wrong string for Alembic. Neon's pooler runs in transaction mode, which
does not give a DDL migration the session semantics it needs (session-level advisory locks,
`SET` statements holding across statements in one transaction) — a migration run through the
pooler can fail outright or, worse, appear to succeed while leaving the lock Alembic takes
unreleased for another session. Alembic needs Neon's **direct (unpooled)** endpoint.

`infra/migrations/env.py` reads its connection string exclusively from the `DATABASE_URL`
environment variable, the same name the application uses — there is no separate variable name
Alembic looks for. The two never need to hold different values in the same environment: the
deployment target's `DATABASE_URL` must stay pooled, permanently, for the app; the direct
endpoint is only ever exported in the interactive shell running the commands below, and never
written to the deployment target, a file, or a log.

Neon's console distinguishes the two by hostname: the pooled string's host carries a `-pooler`
segment (e.g. `ep-xxxx-pooler.<region>.aws.neon.tech`); the direct string is the identical value
with that segment removed (`ep-xxxx.<region>.aws.neon.tech`). Both keep the
`postgresql+psycopg://` scheme and every other part of the string unchanged. `.env.example`
documents this alongside `DATABASE_URL` and points back here for the procedure; this is the one
place the procedure itself is written down.

## Procedure

Run this once per merge to `main` whose diff touches `infra/migrations/versions/`, before or
immediately after the deploy that carries it reaches production — a deploy that ships an
unapplied migration is caught by `schema_out_of_date` (T394), not prevented by it.

1. Get the direct-endpoint connection string from the Neon console: **Dashboard → Connection
   Details → toggle "Pooled connection" off.**
2. From the repository root, run this single command and paste the string at its prompt. It
   reads the value, rewrites the scheme, and applies the migration in one shell:

   ```sh
   read -rs "RAW?Paste Neon DIRECT url then Enter: "; export DATABASE_URL="postgresql+psycopg://${RAW#*://}"; print -r -- "host: ${${DATABASE_URL#*@}%%/*}"; uv run alembic upgrade head && uv run alembic check
   ```

   It prints the host and nothing else — check it carries **no** `-pooler` segment before
   reading the migration output. Expect `<previous> -> <new>` from `upgrade`, then
   `No new upgrade operations detected.` from `check`.

**Why one command and a prompt, rather than an `export` you paste.** All three of these have
happened, in one sitting, on 2026-08-29, and cost four failed attempts and a rotated credential:

- **The scheme.** Neon's console gives `postgresql://…`. SQLAlchemy maps a bare `postgresql://`
  to the **psycopg2** dialect, which this repository does not install — `packages/storage`
  declares `psycopg[binary]>=3.2`, and `infra/migrations/env.py` passes `DATABASE_URL` to
  SQLAlchemy verbatim with no scheme rewriting. Pasting the console's string over an example
  that already reads `postgresql+psycopg://` silently drops the one part the example was
  carrying, and the run dies on `ModuleNotFoundError: No module named 'psycopg2'`. The command
  above rewrites the scheme itself, so the console's string works unedited.
- **The `?`.** `?sslmode=require` contains a glob character. Pasted anywhere zsh can expand it
  unquoted, the shell answers `zsh: no matches found:` and the variable ends up **empty** — at
  which point `DATABASE_URL` is a bare `postgresql+psycopg://`, psycopg falls back to a local
  Unix socket, and the error is `connection to server on socket "/tmp/.s.PGSQL.5432" failed`,
  which reads like a missing local Postgres rather than a quoting fault.
- **The credential.** A pasted `export` puts the password in the shell history and on screen,
  where it can be copied into a bug report, a terminal recording, or a chat window along with
  the surrounding error. `read -rs` echoes nothing and leaves nothing in history. **If the
  password is exposed anyway, treat it as burned**: reset the role in the Neon console, then
  update `DATABASE_URL` in the Vercel project with the new **pooled** string — the rotation
  breaks the running application until that second half is done, so do both together.

3. Once the deploy is live, confirm `GET /api/health` answers **`200`** (T394).

   Read the status, not the field: the route returns `503 schema_out_of_date` when
   `alembic_version` differs from `EXPECTED_SCHEMA_REVISION`, and the `schema_revision` value in
   a successful body is the **build's own compiled constant**, never what was found in the
   database. So the field alone is not evidence about the database — a `200` is, because the
   route only reaches it when the two are equal.
4. Close the shell, or explicitly `unset DATABASE_URL`, so the direct-endpoint credential does
   not linger in a long-running session.

Never export the direct-endpoint value into the Vercel project's environment variables. That is
the value the app would then use for every request, defeating the pooling `docs/adr/0002-hosting.md`
and R10 (`docs/risks.md`) both depend on.

## Expand/contract migrations: two runs of this procedure, not one

A migration that adds a column and a migration that drops one carry opposite deploy-ordering
constraints, and a single revision that does both at once has no safe ordering relative to the
code deploy at all: applied before the deploy, the still-live old code is missing whatever the
drop removed; applied after, the new code is missing whatever the add hasn't arrived yet. A
revision pair that separates the two — **expand** (additive, safe with the old code still live)
and **contract** (destructive, safe only once the new code is confirmed live) — is how a migration
that both adds and drops gets a safe ordering back. `ad6ae8d59519` (`archival objection (expand)`)
and `5c5f5e0b607d` (`archival objection (contract)`) are this repository's example: expand adds
`archival_objected_at` and backfills it while leaving `ingest_consent_at` and
`ingest_consent_withdrawn_at` in place for the old code to keep reading; contract, applied only
after the deploy that stops reading those two columns is live, drops them.

Run the Procedure above **twice**, not once, for a pair like this — step 2's target is a specific
revision, not `head`, on the first run:

1. Run the Procedure above's step 2, with the **expand** revision named explicitly in place of
   `head`. The prompt, the scheme rewrite and the `check` are all unchanged; only the target
   differs:

   ```sh
   read -rs "RAW?Paste Neon DIRECT url then Enter: "; export DATABASE_URL="postgresql+psycopg://${RAW#*://}"; print -r -- "host: ${${DATABASE_URL#*@}%%/*}"; uv run alembic upgrade ad6ae8d59519 && uv run alembic check
   ```

   This is safe to apply before the deploy: the old code neither knows nor cares about the new
   column.

2. Deploy the code that reads the new column and stops reading the old ones.

3. Do step 3 of the Procedure above — confirm `GET /api/health` — expecting it to answer `503
   schema_out_of_date` until the deploy lands, not `200`. `alembic_version` is now at
   `ad6ae8d59519`, and `EXPECTED_SCHEMA_REVISION` compiled into the _still-deployed_ old build
   points somewhere behind that (whatever revision was head before this pair shipped); once the
   new build — the one whose `EXPECTED_SCHEMA_REVISION` is the contract revision — is live, the
   two agree again and the check should read `ok`. This is the check working, not an incident:
   every route still serves throughout, because expand only adds. Do step 4 (unset
   `DATABASE_URL`) once this answers `200` — if it is still `schema_out_of_date` after the deploy
   is confirmed live, that is the real fault to investigate.

4. Once step 3 above answers `200`, run the Procedure above again in full, this time targeting
   the **contract** revision (`head`, once it is the only pending revision).

Never collapse the two runs into one `alembic upgrade head` executed before the deploy — that
applies contract before the old code has stopped reading the columns it drops, which is the exact
outage this split exists to avoid.
