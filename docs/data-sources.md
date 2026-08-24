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

### Open question: does any current-patch ranked recording carry an `Achievements` block?

**Not known.** `docs/adr/0001-replay-parser.md`'s correction note (2026-08-24) records that the
parser's type table carries an `Achievements` post-game block the one reference recording measured
there does not have — that recording carries only `Leaderboards` and `WorldTime`. One recording,
from one match, is a single negative sample, and a single negative sample does not establish that
the block is absent from current-patch ranked recordings in general: it could be gated on game mode,
on a settings toggle, on whether the match completed normally, or on something else not yet probed.

Resolving this needs several recordings across several game modes (at minimum ranked 1v1 and ranked
team games; ideally also unranked and custom, since "ranked" is itself an unverified boundary here)
checked for `num_blocks` and the block list the parser reports, the same way the reference recording
above was checked.

**What the answer decides.** The derivation/analysis feature in this codebase (V2) needs
achievement-shaped outcomes — final scores, victory conditions, and similar post-game facts. If no
current-patch recording ever carries the block, that data does not exist in the recording and V2 has
to derive or simulate it from what does (`operations`, `game_settings`, the command log). If some
recordings do carry it, V2 can read it directly instead, which is simpler and more reliable wherever
it is present. Until this is measured, do not build V2 achievement handling on either assumption.

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

### Profile search behaviour

Measured **2026-08-23**. This is the only display-name search available against any source (see §1).

| Property    | Measured                                                                                                                                                                                                                     |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Matching    | case-insensitive **substring** — `vipe` returns `Vipechester`, `HERA` returns `anotheraoe2player`                                                                                                                            |
| Ordering    | by `games` descending, so the best-known player of a name comes first                                                                                                                                                        |
| Page        | 20 per page, with `page`, `perPage`, `offset`, `count`, `hasMore`                                                                                                                                                            |
| Record      | `profileId`, `name`, `country`, `games`, `drops`, `clan`, `avatarhash`, `verified`, `platform`, `platformName`, `steamId`, `shared`, `sharedHistory`, `hidden`, and six sparse `social*` fields (1 record in 20 carried any) |
| Reliability | 12 consecutive requests, 12 × `200`, from a residential connection                                                                                                                                                           |

> **Trap.** A search record also carries `steamId`, `shared` and `sharedHistory` — the same
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
imprecise: stripping the first is required, while stripping the second discards the only place this
source records a player asking not to be shown. What `shared` means is **still unresolved** — it
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

## Terms of use

All of the above fall under Microsoft's **Game Content Usage Rules**: strictly non-commercial, a
disclaimer is required, and no reverse engineering of the game. This is the same regime under which
aoe4world, aoestats and aoe2companion operate.
