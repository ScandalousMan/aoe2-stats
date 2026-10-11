# Runbook: re-validating captures quarantined by an engine failure

`scripts/ops/revalidate_quarantined.py` gives a `replay_captures` row that ended `quarantined`
because the replay engine could not parse its recording a second validation, from the bytes already
in the object store (T673, feature 006). It exists because the engine was upgraded (T672) after
`aoe2rec-py` 0.1.21 panicked on the one recording measured as game build 185872 (`docs/risks.md`).
How many captures carry the engine's failure text is **not measured**: the dry run below is how it
becomes measured. Where the source's retention window sits is `docs/data-sources.md`'s to say.

This is a maintenance command, not part of the ingest cycle. It runs from a terminal, against
production, by hand.

## What it will and will not do

- It reads the committed object back, checks it against the row's own `zip_sha256`, and runs it
  through the same containment barrier the capture path uses. A row that validates becomes
  `stored` (`stored_at` is the time of this run, not of the original capture); a row that fails
  with a new engine verdict stays `quarantined` with that verdict.
- It never downloads from the replay source, and it never writes, replaces or deletes an object:
  the store is only ever read.
- It never selects an integrity quarantine (`reclaim could not read back ...`, `reclaim checksum
  mismatch ...`), a timeout or a `MalformedArchiveError`.
- It takes a capture only when its profile has an active link (`profile_links.unlinked_at IS
  NULL`) whose user has not objected to archival (`users.archival_objected_at IS NULL`,
  constitution IX). It checks that when the page is selected and again inside each write, because
  a user can object or unlink while a page is being validated. A profile with no active link is
  not taken, even if its former owner never objected; the dry run counts it as `(no active link)`.
  Such a capture is not selected (T673): the row and its object stay as they are.
- It raises no alert. The row raised its `validation_failed` when it was first quarantined.

## Outcomes

One line per row examined:

| Outcome             | Meaning                                                                                                   | Row written?                                   |
| ------------------- | --------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| `selected`          | Dry run only: the row is in the selection.                                                                | no                                             |
| `stored`            | The object now validates.                                                                                 | yes, `stored`                                  |
| `still_quarantined` | The engine failed again with an engine verdict; the new reason is printed.                                | yes, new `last_error`                          |
| `inconclusive`      | Validation failed for a reason that is not the engine's verdict (the wall-clock cap, any other class).    | no; the row stays in the selection             |
| `integrity_failure` | The object is missing or no longer matches the row's `zip_sha256`. Evidence for a human, constitution IV. | no; the run ends **non-zero** after the report |
| `changed_elsewhere` | The write matched no row, and the row was no longer `quarantined` when read back.                         | no                                             |
| `ownership_changed` | The write matched no row, and the row was still `quarantined` when read back.                             | no                                             |

If the object store fails in any other way (an outage, a denied request, a missing bucket) the run
**stops** at that row, prints `STOPPED` and the error's class (never its text), writes nothing for
that row, and exits non-zero. Re-run once the store is reachable. The stop line names the row it
stopped at (game, profile, recording time) and the `--after` value that starts past it. If the same
row stops two runs, pass that value and report the row. If every row of a page is an
`integrity_failure`, check the bucket name (`S3_BUCKET`) first: a bucket that exists and that the
token can read, but is not the replay bucket, answers "no such object" for every key, which is
indistinguishable from objects that are really missing. Any other wrong bucket stops the run: the
store's answer is not "no such object", so the run ends with `STOPPED` and the error's class.

A database error at a row's write step (the write itself, or the read that tells why a write was
refused) also **stops** the run at that row. The report of the rows examined before it is printed
first, whatever their outcome, then `STOPPED` and the error's class, never its text; the exit code
is non-zero. Re-run: the row it failed on is not in the report, it is offered again if it is still
`quarantined` (and its profile still has an active link whose user has not objected), and the
totals reported may be short by that one row. Of the rows the command writes, only a `stored` one
leaves the selection; a `still_quarantined` row keeps an engine verdict, which the selection still
matches. The stop line names the row it stopped at (game, profile, recording time) and the
`--after` value that starts past it. If the same row stops two runs, pass that value and report the
row.

Only those two stops keep the report. An interrupted page loses its report: an interrupt in the
middle of a page (Ctrl-C, a closed terminal), or any other error that ends the run early, prints
no report for the rows that page had already examined. Let a page finish, and keep it short with
`--limit`.

Exit codes: `0` when the run completed with no integrity failure on its page; `1` when the
invocation was refused, when a row **on the page that ran** had an integrity failure (after the
report), or when the store failed or a database error stopped the run. A row beyond `--limit`, or
before `--after`, is not on the page, so a run that does not include an integrity failure does not
exit non-zero for it.

## The dry run counts what it does not select

`--dry-run` lists the selection and also counts every other `quarantined` row, grouped by label:
the text before the first colon when it is an identifier ending in `Error` or `Exception` (ASCII
letters, digits and underscores, no dot: the shape of an exception class name, and any reason whose
head has that shape is counted under it), the two `reclaim ...` texts, the wall-clock cap, the
engine's class followed by `(archival objected)`, `(no committed object)` or `(no active link)` for
engine rows the selection excludes (`PanicException (archival objected)`, for one), `other` for any
other text, and `no reason recorded`. For those rows it prints counts under the labels, and no
object key. A dry run reads the database, reads no object and writes nothing. Paste that block into
the write-up this run belongs to: it is the measurement `docs/risks.md` still lacks.

Two decisions this command does not make, and the dry run's count is what they wait on:

- whether timeout quarantines (`wall-clock cap`) are reopened (001's plan calls the cap an engine
  failure; this command does not select them);
- whether rows re-validated here may turn the nightly capture audit red
  (`scripts/checks/capture_audit.py` measures `stored_at` against the recording, and a re-validated
  row's `stored_at` is the time of the re-validation).

## Environment

Nothing is read from a dotenv file: `.env.local` in this repository points at the **production**
database, so the operator names the target on the command line, never by file.

- **Dry run:** `DATABASE_URL` only, the same **pooled** Neon connection string the running
  application uses (no DDL, so not the direct endpoint `docs/runbooks/database-migrations.md`
  reserves for Alembic).
- **Real run:** the object store is built through the application's own `Settings`, so the
  command needs the application's complete environment (`.env.example` names every key) and
  `Settings`' validation applies, including its rejection of an `S3_ENDPOINT_URL` that carries a
  bucket path. A missing or invalid key is named; its value never is. Read access to the replay
  bucket is enough, so use a read-only token.

Secrets are read as `docs/runbooks/alert-acknowledgement.md` reads them: `read -rs` prompts for
the value and echoes nothing, so it lands in neither shell history nor a chat window. Read that
runbook's "Why one command and a prompt" section first: the three traps recorded there (the console
handing out `postgresql://` instead of `postgresql+psycopg://`, zsh globbing the `?` in
`?sslmode=require`, a pasted password in history) apply here unchanged.

## Procedure

1. Open a fresh shell at the repository root, and set the environment. The database and bucket
   secrets are prompted; the tuning keys come from `.env.example`'s own values; the three
   application secrets this command never uses (`APP_SECRET_KEY`, `CRON_SECRET`, `STEAM_API_KEY`)
   are validated by `Settings` (`CRON_SECRET` must be at least 32 characters, so the command below
   generates 32 hex characters; the other two must be non-empty), so they get throwaway values and
   no real secret is entered:

   ```sh
   while IFS='=' read -r key value; do case "$key" in DATABASE_URL|S3_*|APP_SECRET_KEY|CRON_SECRET|STEAM_API_KEY) ;; *) export "$key=$value" ;; esac; done < <(grep -E '^[A-Z][A-Z0-9_]*=' .env.example)
   export APP_SECRET_KEY="$(openssl rand -hex 16)" CRON_SECRET="$(openssl rand -hex 16)" STEAM_API_KEY="unused"
   read -rs "RAW?Paste Neon POOLED url then Enter: "; export DATABASE_URL="postgresql+psycopg://${RAW#*://}"; print -r -- "host: ${${DATABASE_URL#*@}%%/*}"
   read -r "S3_ENDPOINT_URL?R2 account host (https://<account>.eu.r2.cloudflarestorage.com, no bucket path): "; export S3_ENDPOINT_URL S3_BUCKET="aoe2-stats-replays" S3_REGION="auto"
   read -rs "S3_ACCESS_KEY_ID?R2 read-only access key id then Enter: "; export S3_ACCESS_KEY_ID
   read -rs "S3_SECRET_ACCESS_KEY?R2 read-only secret then Enter: "; export S3_SECRET_ACCESS_KEY
   ```

   Use the bucket name your deployment uses if it is not the template's.

2. **Dry run.** Prints the selection and the counts of what is not selected; it reads the
   database, reads no object and writes nothing:

   ```sh
   uv run python scripts/ops/revalidate_quarantined.py --dry-run --limit 1000
   ```

   Read the whole report. Paste the "outside the selection" block into the write-up.

3. **Real run**, a bounded page at a time. The default `--limit` is 25 because one validation can
   take up to its 30 s wall-clock cap. After a row that ended `inconclusive` on that cap, the
   command prints its report and does not exit until the abandoned validation thread ends:

   ```sh
   uv run python scripts/ops/revalidate_quarantined.py --limit 25
   ```

4. When the report ends with `more candidates remain; continue with --after <timestamp>,<id>`,
   copy that value exactly into the next run. The capture id is part of the value on purpose: two
   tracked profiles can have captured one match, so several rows share a completion time, and a
   timestamp alone would skip the rest. A bare timestamp is refused.

   ```sh
   uv run python scripts/ops/revalidate_quarantined.py --limit 25 \
     --after 2026-09-30T12:00:00+00:00,3f2b8c1e-5a4d-4e6f-9a0b-1c2d3e4f5a6b
   ```

   Rows that ended `inconclusive` or `integrity_failure` are unchanged, and a `still_quarantined`
   row keeps an engine verdict as its reason, so all three stay in the selection: a bare re-run
   starts from the oldest row and offers them again, unless the owner has since objected or
   unlinked, and `--after` is what moves past them.

5. Investigate every `integrity_failure` before anything else (constitution I: acknowledge only
   after investigating). The command does not touch those rows and exits non-zero on every
   run whose page includes one, until a human resolves it.
6. Report the dry run's count and the real run's outcome totals back to the task (T673 stays open
   until it has them), then close the shell, or clear the credentials from it. `RAW` is the
   variable that held the pasted database URL:

   ```sh
   unset RAW DATABASE_URL S3_ACCESS_KEY_ID S3_SECRET_ACCESS_KEY
   ```
