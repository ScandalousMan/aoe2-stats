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
| `user_id` | uuid, fk users | Many rows per user; `steam_id64` being the pk already makes a Steam identity unique service-wide |
| `verified_at` | timestamptz | The moment `check_authentication` returned valid. Never inferred |
| `last_sign_in_at` | timestamptz | |

A user may hold several rows (FR-007). Each one is a completed sign-in. There is no path by which a
row appears without one — FR-045.

### `sessions`

| Field | Type | Notes |
| --- | --- | --- |
| `id` | text, pk | Opaque, 256 bits of randomness. Never derived from anything about the user |
| `user_id` | uuid, fk users | |
| `created_at`, `expires_at` | timestamptz | |
| `revoked_at` | timestamptz, null | Server-side revocation, so sign-out is real and not cookie theatre |

No user data, no roles, no payload. FR-006 makes Steam the only key, which makes the session the
only thing this service can actually revoke.

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
| `profile_id` | bigint, fk | Unique across the whole table, not just per user: a profile belongs to one account. The index is **partial** — `UNIQUE (profile_id) WHERE unlinked_at IS NULL` — otherwise an unlinked profile blocks its own relink and reports `profile_already_linked` forever |
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
| `claimed_at` | timestamptz, null | Set when a run claims the row; a claim older than the maximum function duration is stale and reclaimable |
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
| `quarantined` | Stored and checksummed, but not a well-formed replay | no — needs a human |
| `failed` | Attempts exhausted | no, needs a human |

`unavailable` and `expired` are separated deliberately. Blurring them would hide the only metric
that matters: `expired` counts our failures, `unavailable` counts the game's. Alerting on the sum
would mean alert fatigue on the first, and silence on the second.

`quarantined` is separated from `failed` for the same reason: `failed` means we never got the bytes,
`quarantined` means we have them and cannot read them. The first is a capture problem, the second is
a parser problem, and V2 may well resolve a backlog of the second without re-fetching anything.

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

`expired_total` is named here because constitution I names it. It is expected to be permanently
zero, and the nightly audit asserts exactly that.

**The absence of a row is the signal.** The nightly job reads the newest one and fails if it is
older than 30 hours. Nothing inside a system that has stopped can report that it has stopped, so
this is checked from outside.

### `alerts`

`id` uuid pk, `kind` (enum: `rate_limited`, `deadline_breach`, `expired_capture`,
`validation_failed`, `free_tier`), `severity` (smallint, 1 or 2), `detail` jsonb, `raised_at`,
`ingest_run_id` (uuid, null, fk), `acknowledged_at` (timestamptz, null).

Four tasks say "raise an alert" and constitution I makes a non-zero `expired_total` a severity-1
incident, but nothing in phase 1 is always-on, so an alert cannot be pushed from inside a process
that may not be running. It is therefore **pulled**: the ingester writes a row, and the nightly
GitHub Actions job fails when any severity-1 row is unacknowledged — the same job that already opens
an issue on failure. No pager, no third-party service, no secret, and it behaves identically on a
VPS (constitution XII).

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
- **A `sessions` table with user data in it.** The table exists, but holds an opaque identifier, a
  user id and timestamps — no roles, no payload, nothing worth stealing beyond the reference itself.
- **Any table linking a user's several profiles to each other beyond `profile_links.user_id`.** The
  association exists only inside the account. Nothing exposed can reveal it (FR-045).
- **Soft deletes on captures.** A capture record is either there or the user asked us to erase it.
