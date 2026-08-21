# Phase 1 Data Model

Derived from the Key Entities in [spec.md](./spec.md). Types are conceptual; the migration is the
implementation.

The governing rule is constitution IV: **`replay_captures` plus the stored blob are the truth, and
everything else is derived and disposable.** If a table could be rebuilt from provider responses and
the object store, it is a cache. If it could not, it is sacred. Only two things are sacred here: the
capture records, and the blobs they point at.

---

## Identity

### `users`

| Field                         | Type              | Notes                                                                                      |
| ----------------------------- | ----------------- | ------------------------------------------------------------------------------------------ |
| `id`                          | uuid, pk          |                                                                                            |
| `created_at`                  | timestamptz       |                                                                                            |
| `allowlisted_at`              | timestamptz, null | Null means the closed beta refuses them (FR-005)                                           |
| `ingest_consent_at`           | timestamptz, null | Null means capture nothing. Enforced in the query that selects work, not in a later branch |
| `ingest_consent_withdrawn_at` | timestamptz, null | Kept after withdrawal; erasure is a separate act                                           |

No password column, no email column, no reset token. FR-006 removes the entire family. A column that
does not exist cannot leak.

### `steam_identities`

| Field             | Type           | Notes                                                                                            |
| ----------------- | -------------- | ------------------------------------------------------------------------------------------------ |
| `steam_id64`      | text, pk       | As returned by `openid.claimed_id`, digits only                                                  |
| `user_id`         | uuid, fk users | Many rows per user; `steam_id64` being the pk already makes a Steam identity unique service-wide |
| `verified_at`     | timestamptz    | The moment `check_authentication` returned valid. Never inferred                                 |
| `last_sign_in_at` | timestamptz    |                                                                                                  |

A user may hold several rows (FR-007). Each one is a completed sign-in. There is no path by which a
row appears without one — FR-045.

### `sessions`

| Field                      | Type              | Notes                                                                      |
| -------------------------- | ----------------- | -------------------------------------------------------------------------- |
| `id`                       | text, pk          | Opaque, 256 bits of randomness. Never derived from anything about the user |
| `user_id`                  | uuid, fk users    |                                                                            |
| `created_at`, `expires_at` | timestamptz       |                                                                            |
| `revoked_at`               | timestamptz, null | Server-side revocation, so sign-out is real and not cookie theatre         |

No user data, no roles, no payload. FR-006 makes Steam the only key, which makes the session the
only thing this service can actually revoke.

### `csrf_states`

| Field                      | Type              | Notes                                                                |
| -------------------------- | ----------------- | -------------------------------------------------------------------- |
| `id`                       | text, pk          | The raw OAuth CSRF `state` value, same entropy floor as a session id |
| `created_at`, `expires_at` | timestamptz       | `expires_at` bounds the Steam OpenID round trip, minutes not days    |
| `consumed_at`              | timestamptz, null | Set the moment a callback spends this `state`; null until then       |

Minted before any session exists (`GET /api/auth/steam/start`), so it cannot carry a `user_id` the
way `sessions` does. It exists so single-use and expiry are properties this table enforces on
lookup — not properties the client's own cookie merely claims (T028b).

---

## Profiles and matches

These are caches. Everything here can be re-fetched.

### `aoe_profiles`

`profile_id` (bigint, pk), `alias`, `country`, `first_seen_at`, `last_seen_at`.

Holds **third parties too** — every opponent and teammate. Their presence is what makes the GDPR
processing register non-trivial. `alias` is the last one observed, not a history: we have no reason
to track someone's name changes.

### `profile_links`

| Field                   | Type              | Notes                                                                                                                                                                                                                                                             |
| ----------------------- | ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `user_id`               | uuid, fk          |                                                                                                                                                                                                                                                                   |
| `profile_id`            | bigint, fk        | Unique across the whole table, not just per user: a profile belongs to one account. The index is **partial** — `UNIQUE (profile_id) WHERE unlinked_at IS NULL` — otherwise an unlinked profile blocks its own relink and reports `profile_already_linked` forever |
| `steam_id64`            | text, fk          | The identity that proved it                                                                                                                                                                                                                                       |
| `is_primary`            | boolean           | Exactly one true per user, enforced by a partial unique index                                                                                                                                                                                                     |
| `linked_at`             | timestamptz       |                                                                                                                                                                                                                                                                   |
| `unlinked_at`           | timestamptz, null | Set rather than deleted, so capture history stays explicable                                                                                                                                                                                                      |
| `backfill_requested_at` | timestamptz, null | Set at link time, cleared when the 31-day sweep has run for this profile. The link cannot enqueue captures itself: there are no `matches` rows for a profile nobody has ever polled                                                                               |

### `matches`

`game_id` (bigint, pk), `leaderboard_id`, `map_name`, `patch`, `started_at`, `completed_at`,
`duration_seconds`, `source`, `raw_payload` (jsonb), `fetched_at`.

`raw_payload` is the provider's response, unmodified (constitution IV). It is what lets a
misinterpreted field be corrected six months from now without re-fetching anything — which matters
because after 31 days there may be nothing left to re-fetch from.

One row per match, **shared between users**. Two beta users in the same game produce one `matches`
row and two `replay_captures` rows.

### `match_players`

`(game_id, profile_id)` pk, plus `team_id`, `civ_id`, `color_id`, `result`, `rating`, `rating_diff`.

### `rating_snapshots`

`(profile_id, leaderboard_id, captured_at)` pk, plus `rating`, `rank`, `wins`, `losses`, `streak`,
`highest_rating`.

Append-only, one row per observation per cycle. Daily granularity is what a daily cron can honestly
produce, and it is enough to draw a rating curve.

---

## Capture — the sacred part

### `replay_captures`

The table the entire feature turns on.

| Field                           | Type               | Notes                                                                                                                                                                                                               |
| ------------------------------- | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`                            | uuid, pk           |                                                                                                                                                                                                                     |
| `game_id`                       | bigint, fk matches |                                                                                                                                                                                                                     |
| `profile_id`                    | bigint, fk         | Whose point of view. **Unique on `(game_id, profile_id)`** — this constraint _is_ the deduplication (FR-018)                                                                                                        |
| `status`                        | enum               | See the state machine below                                                                                                                                                                                         |
| `capture_deadline_at`           | timestamptz        | `completed_at + CAPTURE_BUDGET_DAYS`, read from settings. Computed on insert, never recomputed, and never restated as a literal: the budget must be lowerable in one place the day the window is observed to shrink |
| `attempts`                      | int                |                                                                                                                                                                                                                     |
| `next_attempt_at`               | timestamptz        | Backoff lives here, not in a scheduler                                                                                                                                                                              |
| `claimed_at`                    | timestamptz, null  | Set when a run claims the row; a claim older than the maximum function duration is stale and reclaimable                                                                                                            |
| `first_seen_at`, `stored_at`    | timestamptz        | `stored_at - completed_at` is the capture lag                                                                                                                                                                       |
| `object_key`                    | text, null         |                                                                                                                                                                                                                     |
| `zip_bytes`, `zip_sha256`       | bigint, text       | Written before the status flips to `stored`                                                                                                                                                                         |
| `inner_filename`, `inner_bytes` | text, bigint       | From validation                                                                                                                                                                                                     |
| `source`                        | enum               | `automatic` or `manual` (FR-033)                                                                                                                                                                                    |
| `http_status`, `last_error`     | int, text          | For diagnosis, never for control flow                                                                                                                                                                               |
| `validated_by`                  | text, null         | Parser engine and version used at capture time                                                                                                                                                                      |

**Status values and what each one means operationally:**

| Status        | Meaning                                                       | Retried?                                                                                                                                                                                            |
| ------------- | ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pending`     | Known, not yet fetched                                        | yes, from `next_attempt_at`                                                                                                                                                                         |
| `downloading` | Claimed by a run; may already carry the blob and its checksum | reclaimed if the claim is stale — resumed at validation, not re-downloaded, when `zip_sha256` is set                                                                                                |
| `stored`      | Blob durable, checksum recorded                               | terminal                                                                                                                                                                                            |
| `unavailable` | The source says this replay was never recorded                | no — but only concluded once the match is older than `REPLAY_PUBLICATION_GRACE_HOURS` **and at least two attempts have been made**. A 404 before either condition leaves the row `pending` (FR-019) |
| `expired`     | Past the retention window before we got it                    | no — **and this must never happen**                                                                                                                                                                 |
| `quarantined` | Stored and checksummed, but not a well-formed replay          | no — needs a human                                                                                                                                                                                  |
| `failed`      | Attempts exhausted                                            | no, needs a human                                                                                                                                                                                   |

`unavailable` and `expired` are separated deliberately. Blurring them would hide the only metric
that matters: `expired` counts our failures, `unavailable` counts the game's. Alerting on the sum
would mean alert fatigue on the first, and silence on the second.

The 404 is a **three-way** decision, not two. Younger than the publication grace: the replay may
simply not be published yet — stay `pending`. Older than the grace but inside the retention window, and
not on the strength of a single attempt: `unavailable`. Past the window: `expired`. The first branch is the one that is easy to omit, and
omitting it converts a few hours of publisher latency into a permanent loss.

`quarantined` is separated from `failed` for the same reason: `failed` means we never got the bytes,
`quarantined` means we have them and cannot read them. The first is a capture problem, the second is
a parser problem, and V2 may well resolve a backlog of the second without re-fetching anything.

**One word per side of the boundary.** `stored` is the enum value and the only spelling in code, in
the API and in tests. "Archived" is the user-facing label for the same state and appears only in
component specs and copy. The spec uses "archived" throughout because it is written for a reader,
not for a compiler; every requirement that says "archived" means `stored`.

**Claiming**, which is how an interrupted run resumes without losing work (FR-022):

```sql
UPDATE replay_captures SET status = 'downloading', claimed_at = now(), attempts = attempts + 1
WHERE id IN (
  SELECT id FROM replay_captures
  WHERE status = 'pending' AND next_attempt_at <= now()
  ORDER BY capture_deadline_at ASC          -- nearest deadline first, never newest first
  FOR UPDATE SKIP LOCKED
  LIMIT :batch
) RETURNING *;
```

A run that dies leaves rows in `downloading`; the next run reclaims anything claimed longer ago than
the maximum function duration. No broker, no lease service, no lost work.

The `ORDER BY` is the single most consequential line in the schema. Under a backlog it sheds the
replays we can still fetch tomorrow instead of the ones expiring tonight.

**Write ordering** (FR-023): upload the blob, verify the checksum, _then_ update the row. A crash
between the two leaves an orphan object, which costs a fraction of a cent. The opposite ordering
leaves a record claiming a replay is safe when it is not, which is a lie the user cannot detect.

The write is in two steps, not one. `object_key`, `zip_bytes` and `zip_sha256` are committed as soon
as the checksum verifies, while the row is still `downloading`; the status flip to `stored` or
`quarantined` follows validation. A process that dies in between leaves bytes that are already
durable and recorded, which the next run resumes at validation instead of re-fetching a replay it
already holds. This is what keeps constitution V's containment true for the ingester, which runs the
engine in-process (T055).

Validation runs **after** the upload, never before it. Uploading first costs an orphan object on a
crash — a fraction of a cent. Validating first costs the only copy of a replay that no longer exists
at the source. A file that fails validation is uploaded and marked `quarantined` (FR-026); it is
never discarded.

### `replay_parses` — created now, populated in V2

`(replay_capture_id, parser_name, parser_version)` unique, plus `engine_deps` jsonb, `status`,
`error_class`, `error_message`, `duration_ms`, `output_key`, `finished_at`.

Empty at the end of this feature. Capture-time validation does **not** write here: `validated_by`
on the capture row already records the engine and version, and an empty table is a cleaner V2 seam
than one seeded with rows that mean something different from every row V2 will add. It exists now so
that V2 is an insert rather than a migration (constitution IV), and so that running two parser
engines side by side costs nothing.

---

## Operations and rights

### `ingest_runs`

`id`, `started_at`, `finished_at`, `trigger`, `budget_seconds`, plus counters: `profiles_polled`,
`matches_discovered`, `captures_attempted`, `stored_total`, `failed_total`, `unavailable_total`,
`expired_total`, `quarantined_total`, `alerts_raised`, `backlog_remaining`. Also
`capture_lag_p50_seconds` and `capture_lag_p95_seconds`.

The row is **inserted when the run starts**, carrying `started_at`, `trigger` and `budget_seconds`,
and closed at the end with `finished_at` and the counters. Not written in one go at the end: every
`alerts` row carries `ingest_run_id`, and four of the five producers fire during the drain or
immediately after it, so a row that did not exist yet would orphan them and leave `alerts_raised`
permanently short. A run that dies leaves an open row with a null `finished_at` — which is a fact
worth having, and a second signal beside the absence of a row altogether.

The lag counters are over newly discovered captures only. Including backfill would make the number
describe how far back a rescue reached rather than how fast the cadence is, and SC-002 is a
statement about the cadence.

`expired_total` is named here because constitution I names it. It is expected to be permanently
zero, and the nightly audit asserts exactly that.

**The absence of a row is the signal.** The nightly job reads the newest one and fails if it is
older than 30 hours. Nothing inside a system that has stopped can report that it has stopped, so
this is checked from outside.

### `alerts`

`id` uuid pk, `kind` (enum: `rate_limited`, `deadline_breach`, `expired_capture`,
`validation_failed`, `free_tier`), `severity` (smallint, 1 or 2), `detail` jsonb, `raised_at`,
`ingest_run_id` (uuid, null, fk), `acknowledged_at` (timestamptz, null).

Five kinds, five producers, one severity each — T052 `rate_limited` (**2**), T056 `expired_capture`
(**1**), T055 `validation_failed` (**2**), T059a `deadline_breach` (**1**), T100 `free_tier` (**2**).
The severity is not decoration: the nightly audit fails only on an unacknowledged severity-1 row, so
1 is reserved for the two kinds that mean a replay is gone or is about to be — constitution I makes a
non-zero `expired_total` one of them. Being throttled by a source is a 2: it costs a cycle against a
budget measured in days, and a source we are merely being polite to must not stop the check that
watches for actual loss. But nothing in phase 1 is always-on, so an alert cannot be pushed from inside a process
that may not be running. It is therefore **pulled**: the ingester writes a row, and the nightly
GitHub Actions job fails when any severity-1 row is unacknowledged — the same job that already opens
an issue on failure. No pager, no third-party service, no secret, and it behaves identically on a
VPS (constitution XII).

### `provider_calls`

`id`, `provider`, `endpoint`, `status_code`, `duration_ms`, `called_at`, `rate_limited` (bool).

The evidence base for whether we are being a good guest to undocumented APIs, and the first place to
look when one starts refusing us.

No response body. FR-012 exempts everything re-queryable, and the two irrecoverable sources have
their own homes: `matches.raw_payload` and the object store. A generic body column here would be a
third copy with no reader and a GDPR surface with no purpose.

### `replay_access_log`

`id`, `replay_capture_id`, `user_id`, `accessed_at`, `purpose`. Required by FR-040. These files
contain other people's gameplay and chat; who opened one is a fact worth keeping.

### `data_requests`

`id`, `kind` (`export`, `erasure`, `third_party_objection`), `subject_user_id` (null for a
non-user), `subject_profile_id`, `requested_at`, `completed_at`, `outcome`.

**Erasure** deletes the user, their identities, sessions, links, captures, the access-log rows
pointing at those captures, and the blobs. The access log goes with the captures it describes: it
records who opened _this user's_ replays, which is this user's own data, and SC-008 leaves no room
for a surviving trace. It is not the accountability record for anyone else — nobody else's blob is
reachable from these rows. It does **not** delete
`matches` or `match_players`: those describe games other people also played, and removing them would
corrupt other users' history. The departing user's `profile_id` is pseudonymised in place instead —
the same mechanism FR-039 gives third parties.

---

## What this model deliberately does not have

- **A `replays` table separate from `replay_captures`.** The intent to capture and the result of
  capturing are one row. Splitting them creates a state where the two disagree.
- **A `sessions` table with user data in it.** The table exists, but holds an opaque identifier, a
  user id and timestamps — no roles, no payload, nothing worth stealing beyond the reference itself.
- **Any table linking a user's several profiles to each other beyond `profile_links.user_id`.** The
  association exists only inside the account. Nothing exposed can reveal it (FR-045).
- **Soft deletes on captures.** A capture record is either there or the user asked us to erase it.
