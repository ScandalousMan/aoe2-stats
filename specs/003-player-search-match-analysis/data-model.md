# Phase 1 Data Model: Player Search, Favourites and On-Demand Match Analysis

**Feature**: `003-player-search-match-analysis` | **Date**: 2026-08-23

Five new tables and two widened ones, in one migration. Everything 001 built stays as it is:
this feature adds no column to `matches`, `match_players`, `replay_captures` or `rating_snapshots`,
and it changes the meaning of none of them.

Every table below states what erasure does to it, because R14 records that 001's export and erasure
jobs are not written yet — this is what they will have to implement against, and stating it here is
how this feature discharges FR-017 and FR-046 without depending on unfinished work.

---

## Favourites

### `favourites`

`user_id` (uuid, fk `users.id`, pk), `profile_id` (bigint, fk `aoe_profiles.profile_id`, pk),
`created_at`.

One user's private mark on one player. The composite primary key is the whole of FR-013's idempotence
— marking twice is one row, and unmarking is a delete that cannot leave a duplicate behind.

Private to its owner, always (FR-015). There is no query anywhere in this feature that counts
favourites by `profile_id`, and none may be added: "how many people follow this player" is a fact
this system must not be able to answer, because answering it reveals to the player that they are
being followed.

The count per user is bounded (FR-016) by a configured maximum, checked on insert. The bound is not
tidiness: rendering the list means showing current standing per entry, which is a read per profile,
so an unbounded list is an unbounded query against a source.

A row here **never** causes capture, ingestion or archival of anything (FR-012). Favouriting is a
bookmark and has no consequence beyond this table.

**Erasure**: deleted with the user. **Export**: included, as the profile ids and the dates.

---

## Search

### `profile_search_cache`

`query_normalised` (text, pk), `results` (jsonb), `fetched_at`, `source` (text).

FR-004e. One row per normalised query — lowercased, whitespace-trimmed, Unicode-normalised — holding
the stripped result records and nothing else. Entries are served while younger than a configured TTL
and re-fetched after it.

`results` holds only the fields `PlayerSearchResult` carries (see
[contracts/providers.md](./contracts/providers.md)). It is **not** a verbatim copy of the provider's
response, and the difference is constitution III's own: a name search can be re-run at any time, so it
is recoverable, and principle III's verbatim obligation applies to irrecoverable sources only. Storing
the raw body here would additionally store `steamId`, `shared` and `sharedHistory` — the account-
linking claim FR-004b exists to keep out of this system — which makes the verbatim copy not merely
pointless but forbidden.

This table is a cache and holds no personal data beyond what a public search already returns. It is
safe to truncate at any time; doing so costs a re-fetch and nothing else.

**Erasure**: nothing to do — no row is keyed to a user. **Export**: not included; it is not the
user's data.

### `aoe_profiles` (widened)

Gains `hidden_observed_at` (timestamptz, nullable) and `alias_observed_at` (timestamptz).

`hidden_observed_at` is FR-004c's memory. The source signals that a profile asked not to be listed;
the signal is honoured at the provider boundary for the live response, and recorded here so the
**local fallback** (FR-004d) honours it too. Without this column, a profile hidden at the source
would still surface from locally-observed rows the moment the source went down — the exact moment a
person's request not to be listed would quietly stop being respected.

`alias_observed_at` is the honesty half of the edge case where a player has since renamed: this table
holds the last alias observed, and the date is what lets the interface say so rather than presenting
a stale name as current.

This table is what FR-004d searches. It already contains every participant of every match this
service has seen, populated by 001's discovery, so the fallback introduces no source and no request.

**Erasure**: unchanged from 001 — a third-party objection pseudonymises `alias` and `country`.

---

## Analysis

### `match_analyses`

`game_id` (bigint, pk, fk `matches.game_id`), `state`, `point_of_view_profile_id` (bigint),
`parser_name`, `parser_version`, `engine_deps` (jsonb), `requested_by_user_id` (uuid, fk `users.id`,
nullable), `requested_at`, `claimed_at` (nullable), `lease_expires_at` (nullable), `attempts`,
`finished_at` (nullable), `error_class` (nullable), `error_message` (nullable), `result_key` (text,
nullable).

**One row per match**, and the primary key is the enforcement of FR-031 and FR-038 — not a check in
application code, which is how a double-click fetches the same recording twice (R12).

`state` is one of:

| State | Meaning |
| --- | --- |
| `queued` | someone asked; nothing has been claimed |
| `running` | a lease is held and unexpired |
| `published` | `result_key` points at the analysis; it is shown to everyone |
| `failed` | the recording could not be parsed; `error_class` and `error_message` say why |
| `unavailable` | the recording could not be obtained, and cannot be — the window closed |
| `refused` | the retention cap was reached (FR-047); it may be asked for again later |

`running` means *a lease was taken recently*, never *work is happening now* — R6 explains why that
distinction is forced by the platform rather than chosen. `lease_expires_at` is what makes the
distinction operational: a row whose lease has expired is `running` in name and claimable in fact,
and FR-037 is satisfied because there is no state a crash can leave that the next claim cannot take.
Nothing sweeps expired leases; the next person to open the match takes it (FR-044).

`attempts` bounds the retry of a recording that fails for a transient reason. A recording that fails
to *parse* does not retry at all: it goes to `failed` on the first attempt with its full error
(FR-036, constitution V), because a parse is deterministic and a second attempt is a second identical
failure that costs a fetch.

`point_of_view_profile_id` and the parser triple are FR-032 and are what make FR-041 and SC-009a
mechanical: an analysis whose `parser_version` differs from the current engine is recomputable from
the retained recording without touching the source, however old the match is.

`result_key` points at the published analysis in the object store rather than a `jsonb` column. The
analysis of a long game is large, it is read whole or not at all, it is never queried by its contents,
and the database is a 0.5 GB free tier — `replay_parses.output_key` already established this shape in
001 and this follows it.

`requested_by_user_id` is nullable because erasure must be able to clear it. The analysis itself is
not the user's personal data — it is derived from a match's public record and is shown to every
viewer — so it survives; who asked for it does not.

**Erasure**: `requested_by_user_id` cleared, row retained. **Export**: the requests the user made,
as match ids and dates.

### `retained_recordings`

`id` (uuid, pk), `game_id` (bigint, fk `matches.game_id`), `profile_id` (bigint), `object_key` (text,
unique), `zip_bytes` (bigint), `zip_sha256` (text), `retained_at`, `requested_by_user_id` (uuid, fk
`users.id`, nullable), unique on `(game_id, profile_id)`.

FR-033, and it is a separate table from `replay_captures` on purpose — R9 records the reason and
FR-048 requires the outcome. The two are never counted together, and the schema is what makes
counting them together impossible to do by accident rather than merely inadvisable.

`object_key` uses its own prefix, distinct from `replay_object_key`'s, so the separation survives into
the bucket where the free-tier watch and any bulk copy operate by prefix with no database to join
against.

`zip_sha256` is recorded at retention and verified on retrieval. The bytes are never modified. They
are deleted **only** on a GDPR erasure or a sustained third-party objection (FR-046, constitution IV)
— not when the analysis is recomputed, not when the parser changes, and not when the cap is reached,
because deleting the raw is precisely what would make the published analysis unfalsifiable again.

The legal basis is constitution IX as amended to 2.0.0 and it is **not** the basis under which
`replay_captures` rows exist: those are the consenting user's own point of view under explicit
consent, these are an already-public recording retained because a person deliberately asked for that
match to be analysed. FR-045 requires this to appear in `docs/privacy/processing-register.md` as its
own activity, with its own legal basis, retention and safeguards, in the same change that creates
this table.

**Erasure**: the object and the row are deleted when the requesting user is erased *only if* no
published analysis depends on them; otherwise the analysis is withdrawn with them, which is what
FR-046 means by "the analyses derived from it withdrawn with it". A third-party objection over a
participant deletes both. **Export**: named, not included — the bytes are not the requester's own
data.

---

## Limits

### `rate_limit_counters`

`user_id` (uuid, fk `users.id`, pk), `bucket` (text, pk), `window_start` (timestamptz, pk), `count`.

R10. Fixed windows, one row per `(user, bucket, window)`, incremented with an upsert. Buckets:
`search` (FR-005), `replay_download` (FR-028), `analysis_request` (FR-040). FR-047's per-user half is
the `analysis_request` bucket; its total half is a sum over `retained_recordings.zip_bytes`, which
needs no counter because the rows are the count.

Database-backed rather than in-memory because there is no shared process on this platform, and an
in-memory counter would work on a VPS and silently count nothing on Vercel — the failure constitution
XII exists to prevent.

Rows older than the longest window are disposable. Nothing sweeps them (FR-044); they are pruned
opportunistically on write, which keeps the table bounded without a job.

**Erasure**: deleted with the user. **Export**: not included; it is operational state, not the
user's data.

---

## Widened for access logging

### `replay_access_log` (widened)

`replay_capture_id` becomes nullable; gains `retained_recording_id` (uuid, fk
`retained_recordings.id`, nullable), with a check constraint that **exactly one** of the two is set.

FR-029 requires access to recordings served from this service's own archive to be logged, and after
this feature there are two kinds of archive. The alternative was a second log table, and it was
rejected for FR-048's own reason one level down: two access logs would need every audit to remember
to read both, and an audit that reads one is an audit that reports a clean trail for a file nobody
checked.

The check constraint is the load-bearing part. A nullable pair with no constraint is a row that can
mean nothing, and an access log whose rows can mean nothing is worse than no access log, because it
reads as evidence.

**Erasure**: unchanged from 001 — deleted with the capture or the recording it describes.

---

## Alert vocabulary

`AlertKind` gains `analysis_cap_reached` (severity 2) — FR-047's cap has been hit and new analyses
are being refused. It is severity 2 and not 1 because refusing an analysis is the designed behaviour
and capture is unaffected by construction; it is an alert at all because the cap being reached is a
product decision that has come due, and nobody finds out from a log line.

No other kind is added. In particular there is no alert for a failed analysis: FR-036 requires the
user to be told and the failure recorded, and a per-match parse failure is an expected outcome of
R3's memory bound, not an incident.

---

## What this model deliberately does not have

- **No per-participant analysis row.** R2 verified that one recording yields every participant, so
  the analysis is per match. A per-participant table would invite a second parse and make SC-006
  unprovable.
- **No availability table.** The spec calls "recorded game availability" a *view* over what the
  retention window and 001's captures already establish, and R8 shows it is arithmetic plus rows that
  already exist. A table would be a second copy of a truth that changes with the clock — wrong within
  a day, and wrong in a way nothing would notice.
- **No favourite count, anywhere.** See `favourites`.
- **No `analysis_requests` table separate from `match_analyses`.** The spec lists "analysis request"
  as an entity so that concurrent askers share one piece of work; the primary key on `game_id` *is*
  that sharing (R12), and a second table would reintroduce the race it exists to remove.
- **No queue table, no broker.** As 001: the state column is the queue, claimed with
  `FOR UPDATE SKIP LOCKED`, and it stays inspectable with a SQL query.
