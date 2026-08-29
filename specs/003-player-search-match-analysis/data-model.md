# Phase 1 Data Model: Player Search, Favourites and On-Demand Match Analysis

**Feature**: `003-player-search-match-analysis` | **Date**: 2026-08-23

Six new tables and two widened ones. **Amended 2026-08-29**: this file said five, and `replay_fetch_misses`
is the sixth — added by T337 rather than at planning time, because the need for it only became
provable once the download route existed. Its own section below carries the reasoning. Everything 001 built stays as it is:
this feature adds no column to `matches`, `match_players`, `replay_captures` or `rating_snapshots`,
and it changes the meaning of none of them.

Every table below states what erasure does to it, because R14 records that 001's export and erasure
jobs are not written yet — this is what they will have to implement against, and stating it here is
how this feature discharges FR-017 and FR-046 without depending on unfinished work. 001's T090 and
T091 now name these tables explicitly in their own task text, so the obligation is written on both
sides rather than remembered on one.

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
the stripped result records and nothing else. Entries are served while younger than the TTL that
applies to their own `source`, and re-fetched after it.

**Correction, 2026-08-23 — there are two TTLs, not one.** This section was written when every cached
row came from the live source. A degraded answer (FR-004d) is cached too, and under its own,
deliberately much shorter TTL held as a constant in `apps/api/src/aoe2stats_api/search.py` rather than
in the environment: it is a protection against re-running the fallback's `match_players` aggregate on
every request while the source is down, not an operator-tunable cache. `PLAYER_SEARCH_CACHE_TTL_SECONDS`
governs `source = "companion"` rows only. [contracts/providers.md](./contracts/providers.md) carries the
`source` vocabulary and the reasoning; `docs/privacy/processing-register.md` points *here* for the
retention mechanism, so this paragraph is what keeps that citation honest.

`results` holds only the fields `PlayerSearchResult` carries (see
[contracts/providers.md](./contracts/providers.md)). It is **not** a verbatim copy of the provider's
response, and the difference is constitution III's own: a name search can be re-run at any time, so it
is recoverable, and principle III's verbatim obligation applies to irrecoverable sources only. Storing
the raw body would additionally store `shared`, `sharedHistory` and a dozen presentation fields
nothing reads, which makes the verbatim copy pointless. It is **no longer forbidden**: constitution IX
at 3.0.0 removed the prohibition that sentence rested on, and `steam_id` is now one of the fields this
cache stores like any other.

This table is a cache and holds no personal data beyond what a public search already returns. It is
safe to truncate at any time; doing so costs a re-fetch and nothing else.

**It sheds its own rows, the way `rate_limit_counters` does, and for the same reason.** A row per
distinct normalised query, kept forever, grows with the number of *different* things anyone has ever
searched — which no per-user rate limit bounds, because the limit caps the rate and not the variety.
On a 0.5 GB database that is a slow leak with no reader, and FR-044 forbids the obvious fix of a job
that clears it. So entries older than the TTL for their own `source` are deleted opportunistically on
write — both kinds, on every successful write, whichever kind that write is — which keeps the table
bounded without anything running on a timer. The TTL bounds what is *served*; a row is *deleted* only
when some later write happens to prune it, so a row can outlive its TTL if no further search succeeds. "Safe to truncate" above is what
an operator *may* do; this is what the system does on its own.

**Erasure**: nothing to do — no row is keyed to a user. **Export**: not included; it is not the
user's data.

### `aoe_profiles` (widened)

Gains `alias_observed_at` (timestamptz). One column, not two.

**There is no `hidden_observed_at`, and that is a decision rather than an omission.** It was designed
as FR-004c's memory, so that a profile hidden at the source stayed hidden in the local fallback when
the source went down. T301a then measured the source and found no hidden signal to remember
(`docs/data-sources.md` §3), and FR-004c was retired. A nullable column that nothing can ever set is
worse than no column: every later reader has to work out whether it is unpopulated or unimplemented.

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
the retained recording without touching the source, however old the match is. Staleness is that
comparison and is never a column: a stored flag would have to be set across every row the moment an
engine is upgraded, and nothing may walk the table to do it (FR-044).

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

**A row is written for every published analysis, including one whose point of view this service
already holds as a `replay_captures` row.** Decided 2026-08-24; it is the case an implementer will
otherwise skip, because skipping it looks like an optimisation and reads as one in every line of code
around it. The two objects are not redundant copies of one file, they are the same bytes held under
two different legal bases with two different lifetimes: the capture exists under the user's explicit
consent and is deleted when that user erases (constitution IV's one exception, as narrowed in 3.0.1),
while the retained recording exists under IX's public-recording basis and is never deleted. An
analysis is published to everyone who opens the match, so its raw has to outlive the account of
whoever happened to play it. Reading the capture and retaining nothing would leave the published
analysis unrecomputable the first time that user erases — the failure FR-033 exists to prevent,
reached by the one path that does not look like retention.

This is why `(game_id, profile_id)` is unique *within this table* and not across it and
`replay_captures`: R9 settled that a retained recording and a captured replay of the same pair "must
not resolve to one object", and this is the case that makes it concrete rather than hypothetical.
`ANALYSIS_RETENTION_CAP_BYTES` counts the retained copy only — the capture is 001's and is already
counted under 001's prefix (FR-048), which is the whole reason T378 counts the two prefixes
separately.

`zip_sha256` is recorded at retention and verified on retrieval. The bytes are never modified. They
are **never deleted** — amended 2026-08-24 with constitution IX 3.0.0. Not when the requester is
erased, not when a person appearing in the recording erases or objects, not when the analysis is
recomputed, not when the parser changes, and not when the cap is reached. Deleting the raw is
precisely what would make the published analysis unfalsifiable again. The Erasure note below states
what the two acts do reach.

The legal basis is constitution IX as amended to 3.0.0 and it is **not** the basis under which
`replay_captures` rows exist: those are the consenting user's own point of view under explicit
consent, these are an already-public recording retained because a person deliberately asked for that
match to be analysed. FR-045 requires this to appear in `docs/privacy/processing-register.md` as its
own activity, with its own legal basis, retention and safeguards, in the same change that creates
this table.

**Erasure**: two different acts, and conflating them is what would break constitution IV.

*Erasure of the user who requested the analysis* clears `requested_by_user_id` and **keeps the object
and the row**. The bytes are an already-public recording of a match — not the requester's personal
data, and not necessarily a match they played in — and deleting them would leave a published analysis
that nothing can recompute, which is the unfalsifiable conclusion Q2 and principle IV exist to
prevent.

*Erasure or objection by a person appearing in the recording* pseudonymises every identifier this
service holds about them — the same instrument 001's erasure applies to `matches` and `match_players`,
called with an arbitrary `profile_id` — and leaves the object and the row intact. **No analysis is
withdrawn.** A `.aoe2record` cannot be pseudonymised without being modified, and modifying it destroys
both its checksum and the recomputability principle IV requires. Constitution IX orders IV above
deletion here, deliberately, and `docs/privacy/processing-register.md` carries that ordering in its
balancing test.

Decided 2026-08-23, amended 2026-08-24: FR-033 now carries **no** erasure exception at all. Both acts
remove a *link*; neither removes a *subject*, because the subject is the record of a public match this
service did not create and does not own. **Export**: named, not included — the bytes
are not the requester's own data.

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

## Evidence of a missing recording

### `replay_fetch_misses`

`game_id` (bigint, fk `matches.game_id`, pk), `profile_id` (bigint, fk `aoe_profiles.profile_id`,
pk), `observed_at` (timestamptz).

**Added 2026-08-29, by T337 rather than at planning time.** R8 names two sources of evidence that a
recording was never made — 001's `replay_captures` for a linked user's own point of view, and an
analysis fetch that 404s for a third party's — and the download route's own boundary-race 404 is a
third that no artifact had decided a home for. `contracts/http-api.md` requires that call to record
its outcome ("so the page is right the next time"); this table is that record, and
`derive_availability`'s `recorded_404` parameter reads it.

**Why not a `replay_captures` row**, which is where the evidence would naturally go. That table is
claimed by 001's automatic capture pipeline with no ownership filter, so both available statuses are
forbidden here, in opposite directions: a `pending` row would have the pipeline fetch and **store** a
third party's recording as a direct consequence of a download click (FR-012, FR-027 — downloading is
not analysing), while any terminal status would sit in the `(game_id, profile_id)` pair that
`_enqueue_capture`'s `ON CONFLICT DO NOTHING` needs, silently no-opping the real capture this service
owes that profile's owner the day they link an account. Both are reachable from production traffic,
not just from tests. A separate table participates in neither query and so can cause neither.

Insert-only, `ON CONFLICT DO NOTHING` on the primary key: two callers racing the same boundary record
the same fact and the first wins. Never updated, never swept (FR-044).

**Erasure**: nothing to do — the row is a fact about a match and a point of view, not about the
requester, on the same footing as `replay_captures.status = unavailable`, and constitution IX's
pseudonymisation of `match_players` and `aoe_profiles` already reaches whichever profile the
`profile_id` names. **Export**: not included; it is not the requester's data.

---

## Widened for access logging

### `replay_access_log` (widened)

`replay_capture_id` becomes nullable; gains `retained_recording_id` (uuid, fk
`retained_recordings.id`, nullable), with a check constraint that **exactly one** of the two is set:
`num_nonnulls(replay_capture_id, retained_recording_id) = 1`.

The predicate is written down rather than left to whoever gets there first, because T304's model and
T305's migration must emit the *same* one and there is no way to notice later that they did not. The
form is Postgres's own null-counting function rather than a pair of `IS NULL` comparisons because it
says the requirement in the words the requirement uses, and constitution XII already fixes Postgres
as the database on both phase-1 and phase-2 hosting.

FR-029 requires every access to a recording this service holds to be logged — served or merely read —
and after this feature there are two kinds of archive. The alternative was a second log table, and it was
rejected for FR-048's own reason one level down: two access logs would need every audit to remember
to read both, and an audit that reads one is an audit that reports a clean trail for a file nobody
checked.

The check constraint is the load-bearing part. A nullable pair with no constraint is a row that can
mean nothing, and an access log whose rows can mean nothing is worse than no access log, because it
reads as evidence.

The two kinds are read by different callers, which is what R8 settles: a `replay_captures` row is
served to its owner on request; a `retained_recordings` row is served to nobody and is read by
`apps/analyzer` alone — on the first analysis, and on every recompute. Rows carrying
`retained_recording_id` are therefore **system reads, not downloads**, and that is precisely what an
audit of a third party's recording needs to be able to see.

**`apps/analyzer` writes those rows, and that is allowed** — decided 2026-08-23, because constitution
V's "no direct write access to application tables outside its own" makes it a fair question. Three
things settle it. The read is *user-triggered*: a recompute happens because a person asked, so a
third party's recording is opened on someone's behalf and accountability wants that visible.
`retained_recordings.requested_by_user_id` does not cover it — that records who caused the first
retention, never who caused each later read. And the precedent already exists one level over: the
ingest path writes `provider_calls` today (`apps/api/src/aoe2stats_api/ingest_stages.py`), an
append-only audit table owned by nobody in particular. Principle V is guarding against a parser crash
corrupting application state; an append-only audit row is not that, and the row is written before any
engine is loaded.

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
  a day, and wrong in a way nothing would notice. **`replay_fetch_misses` is not that table**
  (amended 2026-08-29): it stores no computed state and no four-state label, only the one immutable
  fact that the source answered 404 for one exact point of view at one moment. A cached
  `obtainable`/`expired` goes stale when the window's boundary passes it; "the source did not have
  this" does not become false with the passage of time.
- **No favourite count, anywhere.** See `favourites`.
- **No `analysis_requests` table separate from `match_analyses`.** The spec lists "analysis request"
  as an entity so that concurrent askers share one piece of work; the primary key on `game_id` *is*
  that sharing (R12), and a second table would reintroduce the race it exists to remove.
- **No queue table, no broker.** As 001: the state column is the queue, claimed with
  `FOR UPDATE SKIP LOCKED`, and it stays inspectable with a SQL query.
