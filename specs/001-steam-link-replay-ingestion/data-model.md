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

| Field | Type | Notes |
| --- | --- | --- |
| `id` | uuid, pk | |
| `created_at` | timestamptz | |
| `allowlisted_at` | timestamptz, null | Null means the closed beta refuses them (FR-005) |
| `ingest_consent_at` | timestamptz, null | Null means capture nothing. Enforced in the query that selects work, not in a later branch |
| `ingest_consent_withdrawn_at` | timestamptz, null | Kept after withdrawal; erasure is a separate act |

No password column, no email column, no reset token. FR-006 removes the entire family. A column that
does not exist cannot leak.

### `steam_identities`

| Field | Type | Notes |
| --- | --- | --- |
| `steam_id64` | text, pk | As returned by `openid.claimed_id`, digits only |
| `user_id` | uuid, fk users, **unique per (user, steam_id)** | |
| `verified_at` | timestamptz | The moment `check_authentication` returned valid. Never inferred |
| `last_sign_in_at` | timestamptz | |

A user may hold several rows (FR-007). Each one is a completed sign-in. There is no path by which a
row appears without one — FR-045.

---

## Profiles and matches

These are caches. Everything here can be re-fetched.

### `aoe_profiles`

`profile_id` (bigint, pk), `alias`, `country`, `first_seen_at`, `last_seen_at`.

Holds **third parties too** — every opponent and teammate. Their presence is what makes the GDPR
processing register non-trivial. `alias` is the last one observed, not a history: we have no reason
to track someone's name changes.

### `profile_links`

| Field | Type | Notes |
| --- | --- | --- |
| `user_id` | uuid, fk | |
| `profile_id` | bigint, fk | Unique across the whole table, not just per user: a profile belongs to one account |
| `steam_id64` | text, fk | The identity that proved it |
| `is_primary` | boolean | Exactly one true per user, enforced by a partial unique index |
| `linked_at` | timestamptz | |
| `unlinked_at` | timestamptz, null | Set rather than deleted, so capture history stays explicable |

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

| Field | Type | Notes |
| --- | --- | --- |
| `id` | uuid, pk | |
| `game_id` | bigint, fk matches | |
| `profile_id` | bigint, fk | Whose point of view. **Unique on `(game_id, profile_id)`** — this constraint *is* the deduplication (FR-018) |
| `status` | enum | See the state machine below |
| `capture_deadline_at` | timestamptz | `completed_at + 21 days`. Computed on insert, never recomputed |
| `attempts` | int | |
| `next_attempt_at` | timestamptz | Backoff lives here, not in a scheduler |
| `first_seen_at`, `stored_at` | timestamptz | `stored_at - completed_at` is the capture lag |
| `object_key` | text, null | |
| `zip_bytes`, `zip_sha256` | bigint, text | Written before the status flips to `stored` |
| `inner_filename`, `inner_bytes` | text, bigint | From validation |
| `source` | enum | `automatic` or `manual` (FR-033) |
| `http_status`, `last_error` | int, text | For diagnosis, never for control flow |
| `validated_by` | text, null | Parser engine and version used at capture time |

**Status values and what each one means operationally:**

| Status | Meaning | Retried? |
| --- | --- | --- |
| `pending` | Known, not yet fetched | yes, from `next_attempt_at` |
| `downloading` | Claimed by a run | reclaimed if the claim is stale |
| `stored` | Blob durable, checksum recorded | terminal |
| `unavailable` | The source says this replay was never recorded | no (FR-019) |
| `expired` | Past the retention window before we got it | no — **and this must never happen** |
| `failed` | Attempts exhausted | no, needs a human |

`unavailable` and `expired` are separated deliberately. Blurring them would hide the only metric
that matters: `expired` counts our failures, `unavailable` counts the game's. Alerting on the sum
would mean alert fatigue on the first, and silence on the second.

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

**Write ordering** (FR-023): upload the blob, verify the checksum, *then* update the row. A crash
between the two leaves an orphan object, which costs a fraction of a cent. The opposite ordering
leaves a record claiming a replay is safe when it is not, which is a lie the user cannot detect.

### `replay_parses` — created now, populated in V2

`(replay_capture_id, parser_name, parser_version)` unique, plus `engine_deps` jsonb, `status`,
`error_class`, `error_message`, `duration_ms`, `output_key`, `finished_at`.

Empty at the end of this feature except for capture-time validation rows. It exists now so that V2
is an insert rather than a migration (constitution IV), and so that running two parser engines side
by side costs nothing.

---

## Operations and rights

### `ingest_runs`

`id`, `started_at`, `finished_at`, `trigger`, `budget_seconds`, plus counters: profiles polled,
matches discovered, captures attempted, stored, failed, and backlog remaining. Also
`capture_lag_p50_seconds` and `capture_lag_p95_seconds`.

**The absence of a row is the signal.** The nightly job reads the newest one and fails if it is
older than 30 hours. Nothing inside a system that has stopped can report that it has stopped, so
this is checked from outside.

### `provider_calls`

`id`, `provider`, `endpoint`, `status_code`, `duration_ms`, `called_at`, `rate_limited` (bool).

The evidence base for whether we are being a good guest to undocumented APIs, and the first place to
look when one starts refusing us.

### `replay_access_log`

`id`, `replay_capture_id`, `user_id`, `accessed_at`, `purpose`. Required by FR-040. These files
contain other people's gameplay and chat; who opened one is a fact worth keeping.

### `data_requests`

`id`, `kind` (`export`, `erasure`, `third_party_objection`), `subject_user_id` (null for a
non-user), `subject_profile_id`, `requested_at`, `completed_at`, `outcome`.

**Erasure** deletes the user, their identities, links, captures and blobs. It does **not** delete
`matches` or `match_players`: those describe games other people also played, and removing them would
corrupt other users' history. The departing user's `profile_id` is pseudonymised in place instead —
the same mechanism FR-039 gives third parties.

---

## What this model deliberately does not have

- **A `replays` table separate from `replay_captures`.** The intent to capture and the result of
  capturing are one row. Splitting them creates a state where the two disagree.
- **A `sessions` table with user data in it.** An opaque identifier and an expiry, nothing more.
- **Any table linking a user's several profiles to each other beyond `profile_links.user_id`.** The
  association exists only inside the account. Nothing exposed can reveal it (FR-045).
- **Soft deletes on captures.** A capture record is either there or the user asked us to erase it.
