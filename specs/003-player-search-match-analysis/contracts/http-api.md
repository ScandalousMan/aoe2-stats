# Contract: HTTP API additions

Only what this feature adds or widens. Everything in
[001's http-api.md](../../001-steam-link-replay-ingestion/contracts/http-api.md) still holds —
the error shape, the session cookie, the `code`-not-`message` rule — and is not restated here.

Every route below requires a signed-in, allowlisted caller. Nothing this feature adds is reachable
anonymously, and that is load-bearing rather than incidental: see the section immediately below.

## The one thing this contract changes about 001

**001's FR-038 is superseded by this feature's FR-006, FR-007 and FR-008, and narrowed rather than
dropped.** Decided 2026-08-23 and recorded as FR-008a in `spec.md`.

001 stated the property as "there is no endpoint that takes an arbitrary `profile_id` and returns
its history", and `apps/api/tests/test_no_public_directory.py` (T067) asserts it across every route
that could leak it. This feature's whole purpose is to add exactly those endpoints, so that reading
cannot survive — but the constitution's own line is narrower than 001's implementation of it.
Constitution IX says third-party players "are never **publicly indexed**", and 003's FR-010 says the
same. Reachable by a signed-in beta user is not the same thing as publicly indexed.

So the property to preserve is:

1. no third-party profile, search result or match page is reachable without a session (FR-010);
2. no such page is indexable — `X-Robots-Tag: noindex, nofollow` on every route below, and the
   corresponding `robots.txt` disallow for the client-side routes that render them;
3. no route exposes a relationship between a player's accounts that its owner has not proven by
   signing in (001 FR-045, restated here as FR-009 — unchanged and not narrowed);
4. ownership still decides everything about a user's **own** archive: a captured replay is still
   served only to the participant who owns the capture (FR-026), and archival objection, capture
   and erasure are untouched (FR-012).

`test_no_public_directory.py` is **rewritten to assert 1 to 4**, not deleted. Deleting it would
remove the only executable statement of a constitutional property; leaving it as it is would make
this feature's first task turn the suite red for a reason the suite is right about. The rewrite is a
task in this feature and it names what replaced the old reading, so the next person to find that file
learns the narrowing rather than re-deriving it.

## Players

| Method | Path                                               | Notes                                                                                                    |
| ------ | -------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| `GET`  | `/api/players/search?q=`                           | FR-001. Rate limited per user (FR-005). Cached (FR-004e)                                                 |
| `GET`  | `/api/players/{profile_id}`                        | FR-006. Any profile. Alias, country, per-leaderboard rating, rank, wins, losses, and `alias_observed_at` |
| `GET`  | `/api/players/{profile_id}/matches?cursor=&limit=` | FR-007. The same row shape `GET /api/matches` already returns                                            |
| `GET`  | `/api/players/{profile_id}/ratings`                | Rating history, where snapshots exist                                                                    |

`search` returns `{"results": [...], "degraded": bool, "reason": null | "..."}`. A result carries
`profile_id`, `alias`, `country`, `games_played`, `clan` and `unverified_steam_id`, mirroring
`PlayerSearchResult` ([contracts/providers.md](./providers.md)) and adding nothing.

`unverified_steam_id` is the source's own claim, carried since constitution IX 3.0.0 (2026-08-24)
retired FR-004b's strip. The field name is the contract: it is `unverified_steam_id` and not
`steam_id` so that a client cannot present it as a verified link without having chosen to. The
interface MUST label it as unverified where it is shown, and MUST NOT offer any affordance built on
it — no "same player", no merge, no navigation that asserts two profiles are one person (001
FR-045's remaining half). It is `null` in the degraded fallback (FR-004d), which reads
`aoe_profiles` and has no such claim to carry; a client MUST treat `null` as "not known here" and
never as "no Steam account".

The response distinguishes three outcomes, never collapsing two of them (FR-003):

| Outcome            | Shape                                                                                                     |
| ------------------ | --------------------------------------------------------------------------------------------------------- |
| found              | `degraded: false`, results from the source                                                                |
| found nothing      | `degraded: false`, `results: []`                                                                          |
| source unavailable | `degraded: true`, `reason: "search_source_unavailable"`, results from locally-observed profiles (FR-004d) |

The third case still returns results. That is FR-004d, and `degraded` is what stops the interface
presenting a reduced answer as a complete one. A client that branches on `results.length` alone is
wrong, which is why `degraded` is a field rather than an HTTP status.

Matching is case-insensitive and substring, ordered most-played first (FR-004a) — a property of the
source (`docs/data-sources.md` §3) that the local fallback reproduces deliberately so the two answers
are ordered the same way.

`GET /api/players/{profile_id}` answers `200` for a player with no ranked history, with empty ladder
data and an explanation — not `404` (US1 scenario 5). `404` means this service has never observed the
profile and the source does not know it either.

No profile is withheld on privacy grounds, from `search` or from `/api/players/{profile_id}`: the
source carries no hidden signal (T301a, `docs/data-sources.md` §3) and FR-004c was retired on that
measurement. What keeps a third party's page from being a public listing is FR-010 — a session on
every route, `noindex, nofollow`, and `robots.txt` — not a per-profile flag.

## Favourites

| Method   | Path                           | Notes                                                                      |
| -------- | ------------------------------ | -------------------------------------------------------------------------- |
| `GET`    | `/api/favourites`              | FR-014. Each entry with the player and current standing                    |
| `PUT`    | `/api/favourites/{profile_id}` | FR-013. Idempotent. `409` `favourites_limit_reached` at the bound (FR-016) |
| `DELETE` | `/api/favourites/{profile_id}` | FR-013. Idempotent                                                         |

`PUT`/`DELETE` rather than `POST`/`POST` because the operation is idempotent in the database (the
composite primary key) and the contract should say so. Marking twice is one row and one `200`.

There is no route that answers "who favourited this player", and none may be added (FR-015).

An unauthenticated call answers `401` with `code: "sign_in_required"`, which is what lets the client
return the user to where they were (US5 scenario 5).

## Matches, widened

| Method | Path                     | Change                                                                                                            |
| ------ | ------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| `GET`  | `/api/matches/{game_id}` | The ownership scope is removed. Any match this service holds is readable by any signed-in caller (FR-018, FR-021) |

The response gains a per-participant `replay` object and a per-match `analysis` object, both below.
Everything 001's response already carried is unchanged, including the caller's own `capture_status`
and `capture_deadline_at` when they played in it (FR-022).

The response is identical whichever player's history it was reached from (FR-021, US2 scenario 6).
There is no `?from_profile_id=` and there must not be one: a parameter that could change the
presentation is a parameter that eventually will.

It renders entirely from stored match data and never from a recording (FR-019), so it is complete for
a match of any age. Where reference data cannot name an identifier, the raw identifier is returned
alongside a null name and the client shows the identifier (FR-020) — the shape 001 already
established for `civ_name` and `leaderboard_name`.

## Recorded games, per point of view

`GET /api/matches/{game_id}` carries, for each participant:

```json
{ "profile_id": 196240,
  "availability": "archived" | "obtainable" | "expired" | "never_recorded",
  "obtainable_until": null,
  "download_path": "/api/matches/500546441/replay/196240" }
```

| Method | Path                                         | Notes                                  |
| ------ | -------------------------------------------- | -------------------------------------- |
| `GET`  | `/api/matches/{game_id}/replay/{profile_id}` | FR-023. Rate limited per user (FR-028) |

`availability` is derived, never probed — R8, and `docs/data-sources.md` §2 measured why: `HEAD`
answers `405` and `Range` is ignored, so a probe is a full download. `obtainable_until` is derived
from the measured retention window in that file and is restated in no configuration of ours (FR-024).
**Amended 2026-08-29**: that window is contradicted and unresolved, so the field is `null` in _every_
state — not only the two below — until `docs/data-sources.md` records it as settled. The example
above shows the null, because an example carrying a date is the way this amendment gets reverted by
someone reading the shape rather than the sentence.

The four states are exactly FR-025's four. `download_path` and `obtainable_until` are `null` for the
two that are not obtainable, so an unobtainable download cannot be rendered as a button that fails.

Behaviour per state:

- `archived` — the caller's own captured replay, **and only that**: a `replay_captures` row the
  caller owns, served from this service's archive as a short-lived signed URL, regardless of the
  match's age (FR-026). A `retained_recordings` row never produces this state and is never
  downloadable (R8). Writes `replay_access_log` (FR-029).
- `obtainable` — fetched from the source and streamed to the caller. **The bytes are not stored**
  (FR-027): downloading is not analysing, and constitution IX permits retention only where a person
  deliberately asks for a match to be analysed.
- `expired`, `never_recorded` — `404` with the distinguishing `code`, if called anyway.

The boundary race is named rather than hidden: a recording offered as `obtainable` that answers 404
at fetch time returns `code: "expired_since_page_load"`, distinct from `never_recorded` (FR-025, and
the spec's own edge case). That call also records the outcome, so the page is right the next time.

**A failure of this route answers `303`, not `404`/`429`/`502`, when the caller is a browser
navigating to it directly** (decided 2026-08-29) — every case above (`expired`, `never_recorded`,
`expired_since_page_load`, and this route's own or the source's `rate_limited`), plus two more raised
inside the same `try`: `not_found` — the `archived` branch's own ownership check, when the caller is
not this match's participant or the row is not theirs, per `replay-availability.md` §5 — and
`source_unavailable`, the source answering a 5xx, timing out, or answering a status that is neither
`200` nor `404`. `source_unavailable` carries its own `502`: it is the source failing this service,
not evidence the recording never existed, and it must not be folded into `never_recorded`'s meaning.
The route decides "browser navigation" from `Sec-Fetch-Mode: navigate`, falling back to
`Accept: text/html` when that header is absent; a request presenting neither — every API caller,
including this contract's own JSON expectations above — gets the identical error body and status this
section already documents, unchanged. The `303` redirects to the match page for `game_id`, carrying
three query parameters: `replay_error` (the failing `code`, verbatim — the same string a JSON caller
reads from the error envelope's `code` field), `replay_error_profile_id` (the `profile_id` the failure
belongs to, since this route is reachable for any participant's point of view), and
`replay_error_retry_after` (present only when the error carries a `retry_after`, i.e. the
rate-limited cases). This is a transport decision for the same-tab navigation `apps/web` performs to
reach this route; it changes no state this contract already describes, adds no new `code` of its
own — `not_found` and `source_unavailable` are the route's, raised regardless of transport, only
enumerated here — and the response an API caller receives is unaffected.

## Analysis

`GET /api/matches/{game_id}` carries:

```json
{ "state": "absent" | "queued" | "running" | "published" | "failed" | "unavailable" | "refused",
  "parser_version": "0.1.21",
  "stale": false,
  "point_of_view_profile_id": 196240,
  "result_path": "/api/matches/500546441/analysis",
  "reason": null }
```

| Method | Path                              | Notes                                                                                                         |
| ------ | --------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `POST` | `/api/analyze`                    | **A separate Vercel function, not the API app.** Body `{"game_id": ...}`. Claims and runs. `maxDuration: 300` |
| `GET`  | `/api/matches/{game_id}/analysis` | The published analysis (FR-030). `404` in every state but `published`                                         |

`POST /api/analyze` is the one route in this contract that `api/index.py` does not serve. It is
`api/analyze.py`, resolved by the filesystem before the `/api/(.*)` rewrite, exactly as
`api/cron/ingest.py` already is. R6 records why: `api/index.py` is capped at `maxDuration: 10`, and a
serverless function cannot keep working after its response is returned, so the request that asks for
the analysis is the request that performs it.

It is **not** a cron endpoint and carries no `CRON_SECRET`. It authenticates the session cookie like
any other route, is rate limited per user (FR-040), and is refused at the cap (FR-047).

Its response is the same `analysis` object above. A caller disconnected mid-run leaves the lease to
expire; the next caller re-claims and restarts (FR-037). A second caller arriving while a lease is
live gets `running` and does not start a second parse (FR-038) — the primary key on `game_id` is what
guarantees that, not this paragraph.

`absent` means never requested and requestable. `unavailable` means the recordings expired and it
never was analysed — permanent, with `reason`, and the client must not render a button (FR-034).
`refused` means FR-047's cap; it carries a reason and may be asked for again later.

`stale` is `true` when `state` is `published` and the analysis's `parser_version` differs from the
engine currently running. It is **computed, never stored**: a stored flag would need something to set
it across every row at the moment of an upgrade, and that something is the sweep FR-044 forbids.

A recompute is therefore triggered the same way a first analysis is — `POST /api/analyze` on a match
whose analysis is `stale` re-claims the row and re-derives it from the retained recording, reaching no
source (FR-041, SC-009a). On a match whose analysis is `published` and not stale, the same call is a
no-op returning the published object; SC-006's "1 again after a parser version change" is exactly this
path and no other. The client offers the action only while `stale` is true, so a parser upgrade that
makes every analysis stale at once — the spec's own edge case — costs nothing until somebody opens a
match and asks, which is the answer FR-044 gives everywhere else in this feature.

## Response headers on every route above

`X-Robots-Tag: noindex, nofollow` and `Cache-Control: private`. A third party's page may be read by a
signed-in person and must not be retained by a shared cache or found by a crawler (FR-010).

## Error codes this feature adds

| `code`                     | Meaning                                                                           |
| -------------------------- | --------------------------------------------------------------------------------- |
| `sign_in_required`         | favouriting or searching while signed out                                         |
| `favourites_limit_reached` | FR-016                                                                            |
| `rate_limited`             | FR-005, FR-028, FR-040 — carries `retry_after` seconds                            |
| `never_recorded`           | the source has no recording for this point of view                                |
| `expired_since_page_load`  | it was obtainable when the page rendered and is not now                           |
| `analysis_unavailable`     | the window closed and it was never analysed                                       |
| `analysis_cap_reached`     | FR-047                                                                            |
| `analysis_failed`          | the recording could not be parsed; carries the failure class, never the traceback |
| `source_unavailable`       | `502`. The replay source answered a 5xx, timed out, or answered a status that is neither `200` nor `404` on a download fetch — the source failing this service, not evidence the recording never existed (`GET /api/matches/{game_id}/replay/{profile_id}`) |

**Added 2026-08-29**: `source_unavailable` above is not `search_source_unavailable` below — the first
is this route's own error code with its own `502`, the second is a `reason` in a successful search
response. The two names are close on purpose only in what they describe, never in shape.

`search_source_unavailable` is deliberately absent from this table: it is a `reason` in a successful
body, not an error code, because the request succeeded and the answer is reduced rather than missing.
