# Quickstart: validating this feature end to end

How to prove the feature works. Not a test plan — the scenarios a test plan has to make pass, in the
order that finds problems soonest.

## Prerequisites

- Python 3.13 with `uv`, Node 20 with `pnpm`
- A local PostgreSQL, or a Neon branch
- An S3-compatible bucket (Cloudflare R2 free tier is what phase 1 uses)
- A real Steam account whose owner has played AoE2 II:DE **online within the last week** — this
  matters more than it looks, because the retention window means an account dormant for a month
  cannot exercise the interesting paths
- `.env` filled from `.env.example`

```bash
uv sync --all-packages --dev
pnpm install
uv run alembic upgrade head
```

## Running it

```bash
uv run uvicorn aoe2stats_api.app:app --reload --port 8000
```

```bash
pnpm --filter web dev
```

The cron is an ordinary HTTP endpoint, so a cycle is triggered by hand:

```bash
curl -X POST localhost:8000/api/cron/ingest -H "Authorization: Bearer $CRON_SECRET"
```

## Scenario 1 — Linking works and cannot be forged

1. Sign in through Steam. Expect the correct profile and current ratings, with nothing typed.
2. Sign out, then request the callback URL again with the same parameters. **Expect rejection.** If a
   replayed callback signs you in, `check_authentication` is not being performed and the only
   authentication route in the system is forgeable.
3. Tamper with one character of `openid.claimed_id` in the callback. Expect rejection.
4. Sign in with a Steam account that has never played AoE2 online. Expect the `no_aoe2_profile`
   explanation, not a stack trace and not an empty dashboard.

Covers FR-001 to FR-003, FR-006.

## Scenario 2 — Nothing happens without consent

1. Create an account and **decline** ingestion consent.
2. Trigger a cycle.
3. Expect zero `replay_captures` rows for that user, and zero requests to the replay endpoint in
   `provider_calls`.

Covers FR-034 and the part of FR-016 that is easiest to get wrong. Consent must be a condition of the
query that selects work, not a branch somewhere downstream — a branch can be bypassed by a new code
path, a `WHERE` clause cannot.

## Scenario 3 — Backfill rescues the window

1. Consent and link an account that has played in the last 31 days.
2. Trigger a cycle. Repeat until the report shows an empty backlog.
3. Compare the archived set against the official stats page for that player.

Expect: every match from the last 31 days whose replay is still available is `stored`; anything older
is `expired` and nothing else is; each blob is a single-member zip whose sha256 matches the recorded
one.

Covers FR-013 to FR-019, SC-003, SC-005.

## Scenario 4 — Interruption loses nothing

The scenario that justifies the architecture, so it gets run deliberately rather than hoped for.

1. With a backlog of at least ten pending captures, start a cycle with a two-second budget.
2. Confirm it stops cleanly: some captures `stored`, the rest `pending`, **none left `downloading`**.
3. Kill the process mid-download instead of letting the budget expire. Rows are left `downloading`.
4. Run another cycle. Expect the stale claims to be reclaimed and the work completed.
5. Verify no blob was written twice and no capture row is `stored` without a retrievable object.

Covers FR-022, FR-023, SC-009.

## Scenario 5 — Deadline order under pressure

1. Seed pending captures with mixed deadlines: some due in two days, some in eighteen.
2. Run a cycle with a budget that allows only half the queue.
3. Expect the **near-deadline** captures to be the ones stored.

Covers the ordering rule in `data-model.md`. A queue that drains newest-first looks correct in every
demo and destroys exactly the replays that could not have been saved tomorrow.

## Scenario 6 — Idempotency

1. Note the `stored_at` and `zip_sha256` of an archived capture.
2. Run three more cycles.
3. Expect no new rows, no changed `stored_at`, no rewritten object, no request to the replay endpoint
   for that match.

Covers FR-018, SC-006.

## Scenario 7 — Failure classification

1. Point the replay provider at a fixture returning 404 for a match completed three hours ago.
   Expect the capture to stay `pending`, no alert, and to be retried by the next cycle.
2. Same fixture for a match completed four days ago. Expect `unavailable`, no alert.
3. Same for a match completed forty days ago. Expect `expired` **and an alert**.
4. Return 429. Expect the **whole run** to stop and alert, not just that capture.
5. Return 500 three times. Expect backoff, then `failed` after the attempt limit.

Covers FR-019 to FR-021. The three-way reading of a single 404 is the point: conflating any two of
them means alert fatigue, silence on the only metric that matters, or a publication delay recorded
as a permanent absence.

## Scenario 8 — Manual upload

1. Take a capture marked `expired`, upload the matching file from the game's saved-games folder.
   Expect `stored`, flagged manual.
2. Upload a text file renamed `.aoe2record`. Expect rejection, nothing stored.
3. Upload a valid replay for a match the user did not play. Expect rejection.
4. Upload over an existing archive. Expect refusal with a reason.

Covers FR-029 to FR-033.

## Scenario 9 — Multiple Steam accounts

1. Sign in with account A. Link account B via `/api/auth/steam/start?link=1`.
2. Expect both profiles under one account, both ingesting, one primary.
3. Confirm nothing the service exposes reveals that A and B are the same person.

Covers FR-007, FR-042, FR-043, FR-045. Point 3 is not cosmetic: players keep alternate accounts
separate deliberately.

## Scenario 10 — Data rights

1. Export. Expect account, identities, links, match records **and the replay blobs**.
2. Erase, with confirmation. Expect the user, identities, links, captures and blobs gone — verified
   by listing the bucket, not by trusting a success response.
3. Expect `matches` and `match_players` to **survive**, with the departing user's profile
   pseudonymised: those rows describe games other people also played.

Covers FR-036 to FR-039, SC-008.

## Scenario 11 — Liveness reports absence

1. Note the newest `ingest_runs` row.
2. Run the nightly cron-liveness check. Expect pass.
3. Backdate that row by 31 hours. Expect the check to **fail**.

Covers FR-024, SC-007. This is the check that catches the failure mode the phase-1 architecture is
most exposed to, so it gets tested by making it fire, not by watching it stay green.

## Automated coverage

| Scenario | Where |
| --- | --- |
| 1, 2, 8, 9, 10 | `apps/api/tests/` integration tests against a throwaway database |
| 3 to 7 | `apps/ingester/tests/` against provider fixtures |
| 11 | `scripts/checks/` plus `.github/workflows/nightly.yml` |
| Provider contracts | `scripts/checks/contract_sources.py`, nightly against live APIs |

Unit tests never touch the network. Everything above runs against fixtures except the nightly
contract checks, which exist precisely to notice when the fixtures have gone stale.
