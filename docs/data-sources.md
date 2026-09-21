# Data sources

Reference sheet for every external system this project reads from. All figures were measured on
**2026-08-19 between 16:06 and 16:40 UTC** from a residential connection, against public endpoints.

**This file is the single source of truth for these measurements.** Nothing else in the repository
restates them — `.claude/skills/aoe2-data-sources/SKILL.md` carries the rules and points here for
every number, so there is nothing to keep in sync. When a nightly contract test fails, correct this
file first: it is what the next person will trust.

One measurement accumulates rather than being taken once: §2's publication-delay distribution. Its
raw samples are **not** kept in this repository — a repository file only changes by a commit, and
the nightly job that takes the sample (the `contracts` job in `.github/workflows/nightly.yml`)
deliberately makes none, so it never needs write access to anything beyond its own GitHub Actions
run. Instead, each nightly run downloads the corpus accumulated so far as a chained GitHub Actions
artifact (`publication-delay-corpus`), appends that run's one sample, and re-uploads the whole
thing; the corpus lives only in that artifact chain. The block below is the _conclusion_ drawn from
it, written by a human who has pulled the corpus and read it — not machine-regenerated on every
run — using `render_summary` / `rewrite_summary_block` in `scripts/checks/publication_delay.py` as
the tool for doing that by hand. It carries the date it was last written so a reader can judge
whether it is still current.

## Summary

| Source                             | Covers                                                           | Freshness                | Break risk  | Role                      |
| ---------------------------------- | ---------------------------------------------------------------- | ------------------------ | ----------- | ------------------------- |
| Relic `aoe-api.worldsedgelink.com` | Steam to profile_id, leaderboards, personal stats, match history | real time                | Medium      | **primary**               |
| `aoe.ms` / `api.ageofempires.com`  | replay files (zip)                                               | minutes after match end  | Medium-high | **primary** (replays)     |
| `data.aoe2companion.com`           | normalized match and profile data                                | ~30 s after match end    | High        | enrichment, degradable    |
| `aoestats.io`                      | weekly aggregated parquet dumps                                  | **broken since 2026-02** | realized    | V2 historical corpus only |
| `stats.ageofempires.com`           | official web UI                                                  | real time                | n/a         | no public JSON API        |

### Recoverable or not

Which responses must be kept verbatim, per constitution III. The test is whether the _data_ can be
obtained again later, not whether the request can be repeated.

| Response                                      | Recoverable?                                                           | Raw kept                                                     |
| --------------------------------------------- | ---------------------------------------------------------------------- | ------------------------------------------------------------ |
| Relic match history (`getRecentMatchHistory`) | **No** — a match leaves the "recent" window and cannot be fetched back | `matches.raw_payload`                                        |
| `aoe.ms` replay zip                           | **No** — ~31-day retention, then gone for everyone                     | the object store, byte-for-byte                              |
| Relic leaderboards and personal stats         | Yes — current standing, re-queryable at any time                       | not kept                                                     |
| aoe2companion enrichment                      | Yes — re-queryable, and degradable by design                           | not kept                                                     |
| aoestats parquet dumps                        | Yes — published artifacts, re-downloadable                             | not kept (V2)                                                |
| Steam OpenID assertion                        | n/a — an authentication exchange, not a data source                    | not kept; `steam_identities.verified_at` records the outcome |

The two "No" rows are the whole reason principle IV exists. Both are measured properties of the
outside world and are re-checked by the nightly contract tests; if either becomes recoverable, this
table changes before any code does.

## 1. Relic / World's Edge

Base URL: `https://aoe-api.worldsedgelink.com`

> **Trap.** `aoe-api.reliclink.com` now serves a certificate for `CN=*.worldsedgelink.com`, so TLS
> verification fails against that hostname. Community documentation still citing reliclink.com is
> stale. Never disable certificate verification to work around it.

Verified endpoints, all public and unauthenticated:

```
GET /community/leaderboard/getAvailableLeaderboards?title=age2
GET /community/leaderboard/getPersonalStat?title=age2&profile_names=["/steam/{steamid64}"]
GET /community/leaderboard/getRecentMatchHistory?title=age2&profile_ids=[a,b,c]
GET /community/leaderboard/getLeaderBoard2?title=age2&leaderboard_id=3&start=1&count=N&sortBy=1
```

- `getPersonalStat` resolves **steamid64 to profile_id** and returns, per leaderboard,
  `leaderboard_id`, `rating`, `rank`, `wins`, `losses`, `streak`, `highestrating`, `lastmatchdate`
  — an id, never a name. `getAvailableLeaderboards` could resolve one, but nothing in this
  application calls it (constitution III: no provider call outside `packages/providers`, and none
  is wired up); `apps/api/src/aoe2stats_api/leaderboards.py` names the standard ladders instead,
  as static reference data rather than a value fetched per call. Payload ~8 KB. Verified:
  `76561197984749679` resolves to profile `196240`.
- `getRecentMatchHistory` returns `id` (the `gameId` the replay endpoint expects), `matchtype_id`,
  `mapname`, `startgametime`, `completiontime`, and `matchhistorymember[]` with one row per player,
  each carrying `civilization_id` — an id, never a name, the same gap `getPersonalStat` has for
  `leaderboard_id` above. `apps/api/src/aoe2stats_api/civilizations.py` names civilisations as
  static reference data for the same reason `leaderboards.py` does (T033a), but unlike that
  module's ladder ids, this mapping is not simply known: it was established by joining this
  fixture's `matchhistorymember[].civilization_id` against
  `packages/providers/fixtures/companion/matches.json`'s own `civName`, keyed on match id and
  profile id, for real captured matches, then checking a single ordering rule (alphabetical
  position in the pre-Three-Kingdoms/pre-Dynasties-of-India 45-name roster) against every pair the
  join recovers (T070c named this range wrong, in the worst way — confidently — and T070g
  re-derived and checked it; see that module's docstring for the full derivation and
  `apps/api/tests/test_civilizations.py` for the join re-run as an executable test). It covers ids
  0-44. The eight civilisations added since sit outside every pair these two fixtures can check,
  so this module does not guess an order for them; they fall back to a bare id, matching
  `leaderboard_name`'s own fallback shape. Payload ~400 KB per profile.
- **`matchtype_id` is a distinct id space from `getPersonalStat`'s own `leaderboard_id` above** —
  despite `RelicMatchHistoryProvider` storing it into a `matches.leaderboard_id` column of the same
  name (T410 defect fix). Confirmed on a real match: Relic's own `matchtype_id 6` and
  aoe2companion's `internalLeaderboardId 6` name the identical match, and companion carries
  `leaderboardName: "1v1 Random Map"` for it. `apps/api/src/aoe2stats_api/match_types.py` names
  this id space, by that same companion join, separately from `leaderboards.py`.
- **Ids 45-60 (T070i).** Not derived — no fixture here reaches them and the ordering rule above
  stops at 44 by construction. They were instead cross-checked against
  SiegeEngineers/aoc-reference-data's `data/datasets/100.json`, a community-maintained dataset that
  states civilisation ids explicitly. That check confirmed all 45 ids already in the table and 44
  of their 45 labels (id 30 is a deliberate, checked divergence — see the module docstring and the
  comment on that entry — the reference writes "Maya", the table keeps "Mayans", the name both the
  game and the MIT-licensed aoe2techtree data use). Fourteen ids the table lacked were then added
  from the same source, covering the Three Kingdoms, Chronicles and American civilisations.
  Ids 56 and 57 are absent from that dataset too and stay on the fallback deliberately — not
  guessed at — as does everything above 60. Unlike aoe2techtree, `aoc-reference-data` carries **no
  licence at all** (no `LICENSE` file, GitHub reports `license: None`), the same defect recorded
  above for aoe2companion, so it is read, not vendored: the fourteen pairs are transcribed by hand
  into `apps/api/src/aoe2stats_api/civilizations.py` as the facts they are, the JSON file itself is
  never copied into this repository, and nothing fetches it at build or test time. The table
  itself, not this file, is the one place those pairs are recorded — see the module docstring for
  the full derivation and `apps/api/tests/test_civilizations.py` for the transcription check.
- **Player colour: `slotinfo[].metaData.ScenarioPlayerIndex`.** Measured **2026-09-04**, correcting
  004's D2 (2026-08-30), which decoded this very record and read the field as a seat number.
  `slotinfo` is base64 of a zlib stream; inflated, it is a leading integer, a comma, a JSON array
  of lobby slots (`profileInfo.id`, `stationID`, `teamID`, `raceID`, `metaData`, ...) and a
  trailing NUL. Each occupied slot's `metaData` is two more base64 layers — the outer one wraps a
  JSON string literal, the inner one a binary record: one count byte, then `(u32 LE length,
bytes)` key/value pairs — holding `ScenarioPlayerIndex` and `Team` (and a duplicate under the
  key `0`). `ScenarioPlayerIndex` is the player's 0-based number in the game, and in DE that
  number is the colour: `0` blue, `1` red, `2` green, `3` yellow, `4` teal, `5` purple, `6` grey,
  `7` orange — `+1` is the 1..8 scheme aoe2companion's `color` and the design system use.
  Verified by joining the two fixtures on `(match id, profile id)`: every one of the 24
  participants the Relic and companion fixtures share projects to companion's colour, and on 200
  live matches across two profiles every participant had a distinct index in `0`..`7`. Spot check
  on match `474746656`: ScandalousMan index `1` (red), BladeY index `0` (blue), as aoe2insights
  shows. Empty lobby slots carry an empty `metaData` and no profile; they are not participants.
  `packages/storage/.../repositories/matches.py::_slot_colour_id` is the one decoder;
  `packages/storage/tests/test_match_projection.py` re-runs the fixture join on every suite, and
  `contract_sources.py`'s recent-matches check asserts the newest live match still projects a
  colour for every participant. Because the whole entry is archived verbatim in
  `matches.raw_payload`, every match ever discovered can be coloured from disk with no provider
  call (`scripts/ops/backfill_match_players.py`).
- Both accept an array of profiles. Two profiles in one call returned 236 matches in 813 KB.
- Undocumented. The contract may change without notice; nightly contract tests exist for that reason.

### No public player-name search

Measured **2026-08-23**. There is no unauthenticated endpoint on this host that turns a display name
into a profile. Everything public here is keyed by an identifier.

| Probe                                                             | Result                                                       |
| ----------------------------------------------------------------- | ------------------------------------------------------------ |
| `/game/account/FindProfiles` (`alias`, `search`, `profile_names`) | `401 Unauthorized`, HTML                                     |
| `/game/{invented path}`                                           | `404` — so the 401 above is a real route, not a stray        |
| `/community/leaderboard/findAdvancedPlayerLeaderboard`            | `404`                                                        |
| `/community/leaderboard/getAdvancedPlayerLeaderboard`             | `404`                                                        |
| `/community/leaderboard/getLeaderBoard2?...&searchPlayer=Viper`   | `200`, **byte-identical** to the same call without the param |

> **Trap.** `getLeaderBoard2`'s `searchPlayer` parameter is **silently ignored**. It answers
> `200` with `"message":"SUCCESS"` and returns the top of the ladder — for `searchPlayer=Viper` the
> first result is the rank-1 player, Hera. Anything built on it looks like it works and is wrong.

`FindProfiles` exists: the `/game/account/FindProfiles` → `401` versus `/game/{anything else}` →
`404` split proves the router knows the route. It sits in the `/game/` namespace, which the game
client reaches with a Relic session this project has no lawful way to obtain; acquiring one would
mean impersonating the client, which the Game Content Usage Rules forbid. It is unavailable, not
merely difficult.

What does resolve a player, by identifier only:

- `getPersonalStat` — steamid64 to profile, carrying `alias`, `country`, `level`.
- `getLeaderBoard2` — the paginated ladder, one `alias` + `profile_id` per rank, public and complete
  for ranked players. Walking it is the one way to build a name index here without a name search,
  and it covers only players who appear on a ladder.

The only measured display-name search against any source is `data.aoe2companion.com` (§3), which is
degradable by design and intermittently 403 from datacentre addresses.

## 2. Replay download

```
GET https://aoe.ms/replay/?gameId={gameId}&profileId={profileId}
  301 -> https://api.ageofempires.com/api/GameStats/AgeII/GetMatchReplay/?gameId=..&profileId=..&matchId=..
```

**Re-confirmed 2026-08-28: this redirect is now unconditional**, not the occasional shape it was
when first recorded above — every request to `aoe.ms/replay/`, valid `(gameId, profileId)` or not,
receives the `301` first; there is no longer a direct `200` or `404` from that host. `Success` and
`Failure` below describe the response after following it, served by `api.ageofempires.com`; nothing
about the endpoint's own contract — filename, content type, retention — changed, and the redirect
target still answers the identical shapes this table has always measured. This is what a client
built with `follow_redirects=False` (`httpx`'s own default) reads as an unrecoverable, unnamed
status instead of a replay — the production defect this note exists to keep from recurring
silently; `packages/providers/src/aoe2stats_providers/wiring.py` sets `follow_redirects=True` on
the one shared client every provider here is built from for exactly this reason.

| Property       | Measured                                                                  |
| -------------- | ------------------------------------------------------------------------- |
| Authentication | none                                                                      |
| Success        | `200`, `content-type: application/zip`                                    |
| Naming         | `content-disposition: attachment; filename=AgeIIDE_Replay_{gameId}.zip`   |
| Contents       | exactly one file, `AgeIIDE_Replay_{gameId}.aoe2record`                    |
| Compression    | 871 503 B zip to 6 909 299 B raw (x7.9)                                   |
| Sizes          | ranked 1v1 ~0.87 MB; 8-player ~2.3-2.5 MB                                 |
| `HEAD`         | `405` — no cheap existence probe                                          |
| `Range`        | ignored — no partial probe                                                |
| Failure        | `404`, `text/plain`, 16 bytes                                             |
| Access control | `(gameId, profileId)` must be a real participant pair; no ownership check |
| Point of view  | the recording is from that `profileId`'s perspective                      |
| Availability   | see "Publication delay: distribution" below                               |
| Rate limits    | undocumented; ~25 requests in 30 min saw no throttling                    |

### Retention: approximately 31 days

Bisection against profile 196240, reference time `2026-08-19T16:09Z`:

| gameId        | match end            | result                             |
| ------------- | -------------------- | ---------------------------------- |
| 500572650     | 2026-08-19 15:46     | 200 (2.43 MB)                      |
| 498525406     | 2026-08-10           | 200 (1.97 MB)                      |
| 493630273     | 2026-07-20 12:06     | 200 (0.65 MB)                      |
| **493452131** | **2026-07-19 15:09** | **200 (2.50 MB)** — last available |
| **493398610** | **2026-07-19 10:46** | **404** — first missing            |
| 493217484     | 2026-07-18 18:00     | 404                                |
| 492740917     | 2026-07-16 18:27     | 404                                |
| 490086457     | 2026-07-04           | 404                                |
| 482532928     | 2026-06-03           | 404                                |
| 424374137     | 2025-10-09           | 404                                |

The boundary is sharp, inside a ~4 h interval, and is not patch-scoped: replays from patch 1800 sit
on both sides of it. It is a rolling, time-based purge.

**Internal capture budget: 21 days**, leaving 10 days of slack for an outage or a migration.

#### Contradicted 2026-08-28, and not yet resolved — do not rely on the 31 days alone

A second, larger sample disagrees with the reading above, and the disagreement is not marginal.
Draining 78 captures for profile 2322168 on 2026-08-28 produced a boundary just as sharp — inside a
**~4.5 h interval on 2026-02-22** (newest 404: match ending 13:25Z; oldest 200: 18:03Z) — but sitting
**six months back**, not 31 days. All 22 matches after it returned a replay; all 56 before it
returned 404.

A rolling 31-day purge predicts a boundary near 2026-07-28 for a run on that date. The observed one
is five months older, so the two measurements cannot both describe a rolling window of the same
length.

The likely confounder is recorded here rather than guessed at: **the endpoint moved between the two
measurements.** `aoe.ms/replay/` began answering 301 to `api.ageofempires.com` (§2, measured the same
day), and a backend migration is exactly the kind of event that would reset or redefine retention. A
fixed epoch at 2026-02-22 — everything after it kept, everything before it discarded — fits this
sample as well as any rolling window does, and has very different consequences: a fixed epoch can be
purged wholesale at any time, whereas a rolling window is predictable.

**What would settle it**, and what nobody should skip on the strength of one profile: re-measure the
boundary on a _different_ profile, and again a week later. If the boundary stays pinned to
2026-02-22 it is an epoch; if it advances by a week it is a rolling window whose length changed at
the migration.

Until then the 21-day capture budget stands unchanged. It is conservative under either reading, and
constitution I resolves the ambiguity the same way it resolves every other: capture early. What must
_not_ happen is the opposite inference — that replays are now safe for six months and capture can
relax. This sample cannot support that, and 56 recordings were permanently lost while it was being
taken.

### Settled: no current-patch ranked recording carries a post-game statistics block

**Settled, within the scope below.** `docs/adr/0001-replay-parser.md`'s correction note (2026-08-24)
records that the parser's type table carries an `Achievements` post-game block that its one reference
recording did not have. That was a single negative sample. It is now corroborated: a second recording
differs from the first in match size (a 1v1 and a 2v2), in match date (2026-08-19 and 2026-09-06) and
in players and civilisations, and its `PostGame` operation carries the same two blocks and nothing
else. Both are described in `tests/fixtures/replays/README.md` as ranked, on the same game build.
`tests/test_reference_recordings.py` asserts it over every archive committed there: the `PostGame`
block list is exactly `{Leaderboards, WorldTime}`, and no block kind name suggests statistics,
achievements or scores. That test, not this paragraph, is the evidence; the archives cannot be
re-downloaded, which is why they are committed.

**What the finding does not cover.** Still unmeasured: unranked and custom recordings, which this
section's earlier form called ideal rather than required and which this repository does not hold;
ranked team games larger than 2v2; and any other game build. "Ranked" is the fixtures README's
description of where the two files came from, not something the files prove. The test also reads only
the block kinds the pinned parser reports for `PostGame`, so it does not assert that no unit-death or
score data exists elsewhere in the file, or that the parser would surface an unknown block kind. If a
recording from an unmeasured mode is ever committed under `tests/fixtures/replays/`, the test covers
it automatically and this section should be revisited if it fails.

**What the answer decides.** The derivation/analysis feature in this codebase (V2) would have needed
achievement-shaped outcomes — final scores, victory conditions, and similar post-game facts. In the
recordings measured, that data is not there, so outcome-shaped facts are not read from the recording:
nothing may be built on their being present. What V2 derives, it derives from what the recording does
carry (`operations`, `game_settings`, the command log), and it must not present a derivation as a
recorded outcome.

### Publication delay: distribution

The single observation this section used to carry — 33 min after match end, one sample — is not a
distribution. `scripts/checks/contract_sources.py` takes one non-blocking sample per nightly run:
the age of the probe profile's most recently completed match, and whether `aoe.ms` already answers
`200` for it. Never a poll that waits for `200` — the nightly job cannot sit on a request for hours,
so this is one shot per night. The samples accumulate across nights in a chained GitHub Actions
artifact rather than in this repository (see the note at the top of this file, and T012b) — pull
`publication-delay-corpus` from a recent run of the `contracts` job to see the full corpus as of
today; what follows is a point-in-time reading of it.

`REPLAY_PUBLICATION_GRACE_HOURS` (defined once, in `.env.example` — `publication_delay.py` parses
that file rather than restating the number, so this paragraph never needs to) is not sized on this
delay: it is sized on the discovery cadence, at least twice the ~25 h cadence, so two polls always
land inside the grace and no single 404 can close a capture on its own. What this distribution
decides is whether that floor also sits comfortably above the real publication delay.

<!-- publication-delay-summary:begin -->

**Last written by hand: 2026-08-19**, from the one sample recorded before the corpus moved to the
artifact chain (T012b). Re-run `publication_delay.render_summary` against a pulled corpus and update
this block, including this date, whenever the conclusion below should move.

- Samples recorded: **1**, from `2026-08-19T21:30:20.813595Z` to `2026-08-19T21:30:20.813595Z`.
- Shortest match age observed with the replay already available (an upper bound on the real publication delay): **2.15 h**.
- No sample has exceeded `REPLAY_PUBLICATION_GRACE_HOURS` (72 h).

<!-- publication-delay-summary:end -->

## 3. aoe2companion

```
GET https://data.aoe2companion.com/api/matches?profile_ids=a,b&page=N   (20 per page)
GET https://data.aoe2companion.com/api/profiles/{profileId}
GET https://data.aoe2companion.com/api/profiles?search={name}
```

Normalized map and civilisation names, game mode, speed, CDN images, `linkedProfiles`. Freshness
measured at ~30 s: a match ending at 15:46:08Z reported `updated` 15:46:37Z.

### Match colour: `teams[].players[].color`

> **Superseded as the source, 2026-09-04.** Relic carries the colour after all (§1, "Player
> colour"), and the ingester projects it from the archived payload. This field is now the
> **fallback**, read only for a `match_players` row the projection left `NULL` — and the endpoint's
> profile-paginated shape (it returns the queried profiles' _recent_ matches, so an old match is
> simply absent) is why it could never have coloured the back catalogue on its own.

Measured **2026-09-01**. 004 started reading this field on the matches response already documented
above (`GET /api/matches?profile_ids=a,b`) — no new endpoint, a field on one already in use. It is a
small integer, present on every participant of every match in
`packages/providers/fixtures/companion/matches.json`, including every one of those participants
whose own `replay` is `false`: companion assigns a colour to a participant no replay was ever
captured for, the same "enrichment survives where the replay does not" shape the rest of this
section already relies on. `_parse_matches` in
`packages/providers/src/aoe2stats_providers/companion/provider.py` reads it into
`EnrichedParticipant.color_id`; the sibling `colorHex` field is deliberately not read — the hex
belongs to the design system as a token (constitution VI, X), not to a third-party string.

004 also started _reading_ `avatarhash` on the search endpoint below — already measured and recorded
in "Profile search behaviour"'s Record row (2026-08-23). Nothing new to measure there; named here
only so this section lists every companion field this feature depends on.

### Profile search behaviour

Measured **2026-08-23**. This is the only display-name search available against any source (see §1).

| Property    | Measured                                                                                                                                                                                                                     |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Matching    | case-insensitive **substring** — `vipe` returns `Vipechester`, `HERA` returns `anotheraoe2player`                                                                                                                            |
| Ordering    | by `games` descending, so the best-known player of a name comes first                                                                                                                                                        |
| Page        | 20 per page, with `page`, `perPage`, `offset`, `count`, `hasMore`                                                                                                                                                            |
| Record      | `profileId`, `name`, `country`, `games`, `drops`, `clan`, `avatarhash`, `verified`, `platform`, `platformName`, `steamId`, `shared`, `sharedHistory`, `hidden`, and six sparse `social*` fields (1 record in 20 carried any) |
| Reliability | 12 consecutive requests, 12 × `200`, from a residential connection                                                                                                                                                           |

> **Trap.** _Partly superseded 2026-08-24 — read the "So the trap above" paragraph below before
> acting on this box._ A search record also carries `steamId`, `shared` and `sharedHistory` — the same
> community account-linking claim as `linkedProfiles`. Constitution IX and 001's FR-045 forbid
> using, storing or surfacing any of it: it is an unverifiable assertion about someone's identity,
> and acting on it would expose alternate accounts their owners keep separate on purpose. Strip
> these fields at the provider boundary so they cannot reach anything downstream.

> **Unverified.** Whether this endpoint answers at all from Vercel's egress addresses is still
> open — see the 403 observations below. Nothing may depend on it without a degraded path.

### Is there a "this profile is hidden" signal? Measured 2026-08-23

**No usable one.** A `hidden` field exists on both projections — `?search=` and
`/api/profiles/{profileId}` — and it carries nothing:

| Evidence                                                       | Result                           |
| -------------------------------------------------------------- | -------------------------------- |
| 200 search records, 10 queries, pages 1 to 20                  | `hidden` is `null` in 200 of 200 |
| a single-profile fetch                                         | `hidden` is `null`               |
| the source's own client typing (`src/api/helper/api.types.ts`) | `hidden: any`, with no comment   |
| a setting anywhere in that client that writes it               | none                             |
| a consumer anywhere in that client that reads it               | none                             |

A field the source declares as `any`, never populates, never writes and never reads is not a privacy
signal. Anything built on it would be honouring a flag nobody can raise, and would test green against
a fixture we wrote ourselves.

**The real preference is `sharedHistory`, and it is one of the fields we strip.** That is the finding
worth carrying. The source's client exposes it as a user setting — "Shared History", _"Your match
history is visible for other players"_ — and honours `sharedHistory === false` by refusing to show
that player's matches at all (_"This player has disabled shared match history"_). It was `null` in
all 200 sampled records, which is the unset default rather than an absence of the mechanism; a player
who has switched it off is simply rarer than 1 in 200.

So the trap above needs reading with more care than it was written with. `steamId` is an identifier
and `sharedHistory` is an expressed preference, and grouping them as one "account-linking claim" was
imprecise — and the two have since diverged further. `steamId` is **to be carried**: constitution IX at
3.0.0 (2026-08-24) treats every field these APIs serve as public and keeps it so, and it is to be
surfaced as an unverified source claim, never used to link or merge profiles. **Measured state of
this repository on 2026-08-24: still stripped at the provider boundary.** 003's T396 to T398 close
the gap, and this paragraph says which of the two it is describing rather than letting a reader
assume the code already matches the decision. `sharedHistory` is a preference
this service **neither honours nor works around** (same amendment): where the source withholds a
player's matches, nothing is done to obtain them by another route. What `shared` means is **still unresolved** — it
takes both values (129 `false`, 71 `true` across the same 200) and has no user-facing setting string
in the client. Do not act on it.

Consequence for anything consuming this endpoint: there is no hidden flag to honour, and whether a
`sharedHistory === false` preference should be honoured — for a match history this service reads from
Relic and not from here — is a product decision, not a measurement.

Risk is high and structural: single-maintainer project, **no licence on the repository**, no public
API documentation, no announced rate limits, `/api` root returns 403. Use only for display
enrichment, behind a cache and a circuit breaker, and degrade gracefully when unavailable.

### Observed 2026-08-19: intermittent 403

The nightly watchtower's first real run got **403** from GitHub's runners while the same request
returned 200 from a residential connection minutes earlier; repeated local calls then alternated
between 403 and 200 with no pattern in the User-Agent. There is bot protection in front of this
service and it trips intermittently. This is not a schema change and it is not a hard IP block.

Consequences, all of which the architecture already anticipated:

- Every provider sends an honest, identifying `User-Agent`
  (`aoe2-stats/0.1 (+https://github.com/ScandalousMan/aoe2-stats)`). We would rather be recognisable
  than anonymous if anyone wants to ask us to slow down.
- The contract check for this source is **non-blocking**: it warns, it does not fail the nightly job.
  A watchtower that goes red every night for a source the application is designed to survive without
  is a watchtower people stop reading, and then it misses the one that matters.
- Treat a 403 here as normal operating noise. The circuit breaker exists for exactly this.
- **To verify once Vercel is provisioned**: whether this service is reachable at all from Vercel's
  egress addresses. If it is not, the application must still work — it is enrichment only.

## 4. aoestats.io

```
GET https://aoestats.io/api/db_dumps/    <- trailing slash required
```

207 weekly parquet dumps, 30.7 M matches total. **The last dump containing any data covers
2026-02-01 to 2026-02-07 (118 661 matches); all 28 dumps since contain 0 matches.** The outage
coincides with the aoc-mgz breakage caused by the 2026-02-17 DLC and is very likely the same cause.

Unusable for live data. Valuable in V2 as a historical benchmark corpus: `matches.parquet` and
`players.parquet` already carry `feudal_age_uptime`, `castle_age_uptime`, `imperial_age_uptime` and
`opening` per player, which is exactly what is needed to compare a player against their elo bracket.

Terms: Microsoft Game Content Usage Rules, plus Liquipedia content under CC BY-SA 3.0.

## 5. Official stats site

`stats.ageofempires.com` has no public JSON API. `api.ageofempires.com` exposes `GetMatchReplay`;
every other path probed returned 404.

## 6. Knowledge base sources (game rules)

Assessed **2026-09-19** for feature 006
(`specs/006-replay-analysis-foundations/research.md` D3, FR-029), except where a later date is
stated against a specific claim below. Every source considered for the versioned game-rules
knowledge base `packages/knowledge` reads (unit/building/technology costs, training and research
times, age requirements, prerequisites and civilisation bonuses) gets one subsection: its scope,
its reliability, how it updates, how a version of it is identified, its coverage, its known
limitations, and the date it was assessed.

**This is a different axis from `docs/asset-packs.md`.** That document's "Knowledge packs" and
"Rejected sources" tables record **licence** — may a source's files be copied into this repository,
under what grant, checked when. This section records **reliability, coverage and provenance** — how
good is what a source says, how does it change, what can be checked against it, and why a source
that looks like a second opinion sometimes is not one. Each subsection below cites the licence
ruling from `docs/asset-packs.md` rather than restating its fields, per this project's own rule
against keeping one measurement in two homes.

### aoe2techtree (`SiegeEngineers/aoe2techtree`)

- **Scope**: unit, building and technology costs, training/construction/research times, age
  requirements and prerequisites, and per-civilisation membership — which entities each
  civilisation can build or research — the bulk of what `packages/knowledge` needs (FR-022).
  Civilisation bonuses are carried too, but only as **English prose** in
  `data/locales/en/strings.json`, never as structured data; this is why bonuses are hand-modelled
  rather than imported (research.md D5).
- **Reliability**: generated by a library that reads the game's own data file and republishes it,
  structurally faithful to that source. Not independently audited by this project against the
  running game; validated instead against the publisher's own patch notes for every build the
  pinned commit does not cover (see "Update mechanism"), which is the FR-030 validation this
  project actually performs against this source.
- **Update mechanism**: manual and human-triggered, never automated. A person checks out the source
  at a chosen commit; `scripts/ops/import_knowledge_pack.py` reads that local checkout and writes
  the pack, with no network call from the build, the tests or the running system (FR-032). The
  source itself tracks new DE builds on its maintainer's own cadence, with a lag — see "Version
  identifier".
- **Version identifier**: the pinned commit `b9d494df6921d4080df69b22f9dbb7a4d1dcd9f0` (2026-06-21),
  recorded in `packages/knowledge/packs/aoe2techtree/MANIFEST.json` and `LICENCE.md`. The source
  carries no explicit build tag; the game build a commit implements is read from that commit's own
  message ("Implement DE Update `<build>`"), a derived reading, not a field (research.md D3, D4).
  The pinned commit's own newest "Implement DE Update" commit is `daf5fa18de` (2026-06-03),
  implementing build 177723 — three builds behind the committed fixtures' build 180059 — which is
  why every snapshot describing 180059 carries a carry-forward validation record rather than a
  direct import (`packages/knowledge/snapshots/aoe2techtree-180059/snapshot.toml`).
- **Coverage**: all 53 civilisations present in the trees directory at the pinned commit; costs,
  times, ages and prerequisites for every unit, building and technology those trees name. The first
  knowledge snapshot imports this but validates and hand-models bonuses only for the six
  civilisations the committed reference recordings need — Byzantines, Koreans, Franks, Persians,
  Teutons, Gurjaras (research.md D11) — and everything else surfaces as a gap on first use rather
  than as an unvalidated value (FR-022a).
- **Known limitations**: no civilisation-specific bonus data as structured values, no build/version
  field of its own, no combat attributes (attack, armour, hit points, range) — halfon carries those
  (below). Three builds (178524, 179158, 180059) unimplemented by the pinned commit as of this
  assessment.
- **Assessed**: 2026-09-19 (survey, research.md D3); vendored and carry-forward-validated
  2026-09-20 (`packages/knowledge/packs/aoe2techtree/LICENCE.md`,
  `packages/knowledge/snapshots/aoe2techtree-180059/snapshot.toml`). Licence: MIT, **copy
  in** — `docs/asset-packs.md` "Knowledge packs".

### halfon

- **Scope**: costs and combat attributes (attack, armour, hit points, range, speed) for a wider
  object set than aoe2techtree's trees cover, including objects that never appear in a civilisation
  tree. Carries **no times, no age requirements, no civilisation dimension** (research.md D3).
- **Reliability**: generated by the same library, reading the same underlying game data file, as
  aoe2techtree. Their unit costs agree everywhere except in how a zero is serialised — an agreement
  that measures the two tools' serialisation, not the correctness of the underlying read, because
  both read the identical file through the identical extraction path. **It cannot cross-validate
  aoe2techtree**: pairing them would satisfy the letter of FR-028 and FR-030 while supplying none of
  the independent evidence those requirements exist for, so it is not done (research.md D3).
- **Update mechanism**: the same as aoe2techtree's — manual, human-triggered, tracking DE builds
  with a lag on its maintainer's own cadence. Not currently imported by any script here.
- **Version identifier**: not established. No commit is pinned, because no pack has been vendored
  (see "Ruling").
- **Coverage**: not measured against this repository's needs; import is deferred until a task
  actually needs an entity aoe2techtree omits.
- **Known limitations**: no times, no ages, no civilisation dimension, and — see "Reliability" — no
  independent value as a cross-check against aoe2techtree's costs, because it is the same reading of
  the same file through a different formatter.
- **Ruling**: **deferred, not rejected.** It is a documented fallback for an entity aoe2techtree
  omits, to be vendored by the task that first needs it — not vendored now, and never paired with
  aoe2techtree as a second source, because that would satisfy FR-028 and FR-030 on paper while
  deceiving the next reader about how validated the values actually are (research.md D3; plan.md
  Complexity Tracking).
- **Assessed**: 2026-09-19 (research.md D3).

### aoc-reference-data (`SiegeEngineers/aoc-reference-data`)

- **Scope**: names only — identifiers to display names for civilisations and other constants. No
  costs, times, ages, prerequisites or bonuses (research.md D3).
- **Reliability**: community-maintained, explicit identifiers, cross-checked against this project's
  own independently captured fixtures rather than trusted blind: `apps/api/src/aoe2stats_api/
civilizations.py`'s docstring records that its `data/datasets/100.json` confirmed all 45
  civilisation ids this repository had already derived from two frozen provider fixtures, and 44 of
  their 45 labels — one deliberate, checked divergence at id 30, "Maya" there against "Mayans" here,
  the name both the game and aoe2techtree use, which this project keeps. Fourteen further ids,
  outside the fixture-derived range, were added from this source alone, with no independent fixture
  to confirm them (§1 above, "Ids 45-60 (T070i)").
- **Update mechanism**: read by a human, by hand, against a checkout of the repository. Never
  fetched at build, test or run time (FR-031, FR-032).
- **Version identifier**: none — the source carries no release, tag or version field. Whichever
  commit a maintainer happened to read is not recorded, because the source is never vendored (see
  "Known limitations") and there is nothing to pin a digest to.
- **Coverage**: civilisation ids 0-60 as of the reading recorded in `apps/api/src/aoe2stats_api/
civilizations.py`; ids 56, 57 and everything above 60 are absent from this source too and stay on
  this project's bare-id fallback deliberately, not guessed at.
- **Known limitations**: **no licence** — GitHub reports `license: None`, and there is no `LICENSE`
  file in the repository. This is why it is read-and-transcribe-only rather than vendored: FR-031
  forbids vendoring a source with no licence and permits only a human's transcription, recorded with
  its provenance. **This is feature 002's ruling, given a living home here for the first time.**
  002's own `specs/002-reference-data-sources/tasks.md` T205 states it — "`aoc-reference-data`
  carries no licence at all and is the reason this distinction is in the spec: record it as
  read-and-transcribe-only, and record that the transcription that has already happened put the
  pairs into `apps/api/src/aoe2stats_api/civilizations.py` as facts while the source file itself was
  never copied here" — but 002 never wrote the source-inventory document (`docs/reference-data.md`)
  that same task describes, so until now the ruling survived only in that frozen, unchecked task and
  in `civilizations.py`'s module docstring, which independently records the same transcription
  (T070i) in the course of documenting the civilisation id table. Both remain the historical account
  of how the ruling was reached; this entry is its one living record and restates neither in full.
- **Assessed**: 2026-08-30 (`docs/asset-packs.md` "Rejected sources": licence `None found`, ruling
  **READ ONLY**); re-verified for this feature 2026-09-19 (research.md D3: "002's ruling,
  re-verified").

### aoe2companion's data module

- **Scope**: the same costs, times and prerequisites as aoe2techtree.
- **Reliability**: not an independent reading of anything — it republishes aoe2techtree's own data
  inside a wrapper module (research.md D3). Agreement between the two proves nothing an independent
  source would.
- **Update mechanism**: tracks aoe2techtree's own release cadence, one step removed.
- **Version identifier**: none of its own — whatever aoe2techtree revision the wrapper happened to
  bundle at build time, which this project has not needed to pin because the module is not used.
- **Coverage**: identical to whatever aoe2techtree revision it wraps.
- **Known limitations**: **no independent value** as a second source (see "Reliability"), and **no
  licence of its own** — `docs/data-sources.md` §3 already records that `data.aoe2companion.com`'s
  own repository carries no licence at all, and that this project therefore reads it, never vendors
  it, for the enrichment fields it does use; the data module inherits the same defect for the fields
  it wraps.
- **Ruling**: **rejected.** Vendoring it would import aoe2techtree's own data a second time, under a
  licence this project has not separately checked, for no coverage or reliability gain.
- **Assessed**: 2026-09-19 (research.md D3).

### The game's own data file, via genieutils

- **Scope**: everything — costs, times, ages, prerequisites, civilisation bonuses and combat
  attributes, per civilisation, per build, direct from the file the game itself reads.
- **Reliability**: would be the single most authoritative source available, being the primary
  artifact every other source in this section is itself derived from.
- **Update mechanism**: would require extracting the file from an installed copy of the game after
  every patch.
- **Version identifier**: would be exact — the file that ships with a specific, installed game
  build.
- **Coverage**: would be complete, for whichever build is installed.
- **Known limitations / Ruling**: **rejected**, for three independent reasons, any one of which
  would be sufficient alone (research.md D3):
  1. **The publisher's usage rules bar the extraction outright** — the Game Content Usage Rules'
     first prohibition ("Terms of use" below) forbids reverse engineering the game, which reading
     and decoding this file is.
  2. **It needs a game install.** Nothing in this project's runtime, build or test environment
     installs or has access to the game (constitution III, XII); a source that requires one cannot
     be queried by anything this project actually runs.
  3. **It engages the EU database right.** Extracting a structured dataset from the game's own data
     file, at scale, is exactly the act the EU's _sui generis_ database right protects against,
     independent of copyright in the values themselves — a second, independent legal bar even where
     the first did not apply.
- **Assessed**: 2026-09-19 (research.md D3).

### Fandom wiki

- **Scope**: prose tables covering the same ground as aoe2techtree, written for players rather than
  machines.
- **Reliability**: community-edited prose, not a generated export; useful as one more human reading
  of a single contested value, not as a bulk source.
- **Update mechanism**: manual, human reading of a live page; the terms forbid automated access
  (below), so there is no scripted refresh to describe.
- **Version identifier**: none — a wiki page has no version; a reading is dated by when it was made,
  not by a source revision.
- **Coverage**: whatever the community has written up; uneven, and not surveyed for completeness by
  this project.
- **Known limitations**: licensed CC BY-SA 3.0, and **its own terms forbid automated access** — a
  bulk import would breach the terms even where CC BY-SA would otherwise permit copying the text.
- **Ruling**: **one human, one number, with provenance** — consulted only to settle a single
  contested value, by a person reading the page, with the reading recorded against the value it
  supports. Never bulk-imported, never scraped.
- **Assessed**: 2026-09-19 (research.md D3).

### Publisher patch notes

- **Scope**: exact per-build deltas — what changed, in the publisher's own words, for a specific
  game build.
- **Reliability**: the highest available for what it covers — the publisher describing its own
  change — but it is prose, not structured data, and its coverage of a given field is exactly what
  the notes choose to mention; a change the notes omit is not detectable from them.
- **Update mechanism**: manual, human reading of `ageofempires.com`'s news pages. Not every build
  gets a dedicated page: three of the four builds read for the committed fixtures' carry-forward
  validation were "Minor Update `<build>`" sections appended, after the fact, to the previous major
  update's page, with no independently dated timestamp of their own
  (`packages/knowledge/snapshots/aoe2techtree-180059/snapshot.toml`,
  `[validation.carry_forward]`).
- **Version identifier**: the build number itself, as printed on the page.
- **Coverage**: whichever builds a human has actually read; for this feature, builds 178524, 179158
  and 180059 against the pinned aoe2techtree commit's last-implemented build 177723, read and
  recorded 2026-09-20.
- **Known limitations**: all rights reserved — read and transcribed only, never copied in; and, as
  above, minor-update sections carry no independent dated timestamp of their own, a stated weakness
  of the validation rather than a hidden one (research.md D4).
- **Ruling**: **read and transcribe only — this is the FR-030 validation source.** Every
  carry-forward snapshot's validation record cites the specific notes read, the date they were read,
  and what those notes said, or did not say, about the fields the snapshot carries.
- **Assessed**: 2026-09-19 (research.md D3); first exercised as a validation source 2026-09-20.

### aoe2de_patcher build list (`DJSchaffner/aoe2de_patcher`)

- **Scope**: every Steam depot build number for the game, with its release date — a build-to-date
  index, not game rules.
- **Reliability**: community-maintained, derived from Steam's own depot manifests rather than from
  the publisher's editorial copy; consulted only where the publisher's own page carries no
  independently dated timestamp for a build (see "Publisher patch notes" above).
- **Update mechanism**: manual, human reading of the published list.
- **Version identifier**: the build number itself is the identifier; the list has no version of its
  own.
- **Coverage**: dates for builds 178524 (2026-06-08), 179158 (2026-06-16) and 180059 (2026-07-07),
  as read for the committed fixtures' carry-forward validation.
- **Known limitations**: GPL-2.0, and used **for reference only** — the dates are transcribed by
  hand into a validation record; the file itself is never copied into this repository.
- **Ruling**: **reference only.**
- **Assessed**: 2026-09-19 (research.md D3); first exercised 2026-09-20.

### aoestats (as a knowledge source)

- **Scope**: match statistics — win rates, civilisation pick rates, uptime distributions — not game
  rules. §4 above already covers this source fully as a **match-data** source for V2's historical
  corpus; this entry answers the narrower question this feature actually asked — could it also
  answer "what does a unit cost, on which build" — and it was never a candidate for that.
- **Ruling**: **rejected — not rules.** It carries no cost, time, age, prerequisite or bonus data at
  any grain; it is out of scope for a knowledge base of game rules regardless of its own reliability
  or freshness, which §4 assesses on the axis that source is actually used for.
- **Assessed**: 2026-09-19 (research.md D3), against the facts §4 measured 2026-08-19.

## Terms of use

All of the above fall under Microsoft's **Game Content Usage Rules**: strictly non-commercial, a
disclaimer is required, and no reverse engineering of the game. This is the same regime under which
aoe4world, aoestats and aoe2companion operate.
