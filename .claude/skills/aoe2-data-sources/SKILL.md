---
name: aoe2-data-sources
description: AoE2 DE data sources — Relic endpoints, replay download via aoe.ms, aoe2companion API, aoestats dumps, retention window and known traps. Load before any work on packages/providers or apps/ingester.
---

# AoE2 DE data sources

Everything below was measured on 2026-08-19. Any divergence found must be corrected here **and** in
`docs/data-sources.md`, in the same PR.

## Relic host — trap #1

`aoe-api.reliclink.com` serves a `CN=*.worldsedgelink.com` certificate, so TLS verification fails.
**Use `https://aoe-api.worldsedgelink.com`.** Every community document citing reliclink.com is
stale. Never disable TLS verification to work around this.

## Relic endpoints (public, no auth)

```
GET /community/leaderboard/getAvailableLeaderboards?title=age2
GET /community/leaderboard/getPersonalStat?title=age2&profile_names=["/steam/{steamid64}"]
GET /community/leaderboard/getRecentMatchHistory?title=age2&profile_ids=[a,b,c]
GET /community/leaderboard/getLeaderBoard2?title=age2&leaderboard_id=3&start=1&count=N&sortBy=1
```

- `getPersonalStat` is the **steamid64 -> profile_id** resolution path. It also returns, per
  leaderboard, `rating`, `rank`, `wins`, `losses`, `streak`, `highestrating` and `lastmatchdate`
  (~8 KB payload). Verified: `76561197984749679` -> `196240`.
- `getRecentMatchHistory`: the `id` field is the `gameId` the replay endpoint expects.
  `matchhistoryreportresults[]` holds one row per player (`profile_id`, `resulttype`, `teamid`,
  `civilization_id`). About 400 KB per profile: never call it in a tight loop.
- **Both accept an array of profiles** — always batch.
- There is no official documentation. The contract can change without notice, which is why nightly
  contract tests exist.

## Replay download — aoe.ms

```
GET https://aoe.ms/replay/?gameId={gameId}&profileId={profileId}
  -> 301 -> https://api.ageofempires.com/api/GameStats/AgeII/GetMatchReplay/?gameId=..&profileId=..&matchId=..
```

- 200 `application/zip`; `content-disposition: attachment; filename=AgeIIDE_Replay_{gameId}.zip`.
- The zip holds **exactly one** file: `AgeIIDE_Replay_{gameId}.aoe2record`.
- Compression ratio x7.9 (871 503 B zip -> 6 909 299 B raw): **archive the zip, never the extract**.
- Typical sizes: ranked 1v1 ~0.9 MB; 8-player game ~2.3-2.5 MB.
- `(gameId, profileId)` must be a **real participant pair**, otherwise 404. There is no ownership
  check: any participant id works, including another player's.
- The file is **that profileId's point of view**. We only ever capture the consenting user's.
- **`HEAD` returns 405** and **`Range` is ignored**: there is no way to test existence without
  downloading the whole body.
- Retention is approximately **31 days**. Measured: available at 2026-07-19 15:09, gone at
  2026-07-19 10:46, reference time 2026-08-19 16:09Z. Not patch-scoped — it is a rolling time-based
  purge. **Internal capture budget: 21 days.**
- A replay is available within minutes of match end (33 min verified as an upper bound).
- Rate limits are unknown and undocumented. Use **<= 1 req/s globally**, serial downloads, jitter and
  backoff. An unexpected 429 or 403 is an incident: stop the run and alert, never push through.

## aoe2companion — enrichment only

```
GET https://data.aoe2companion.com/api/matches?profile_ids=a,b&page=N   (20 per page)
GET https://data.aoe2companion.com/api/profiles/{profileId}
GET https://data.aoe2companion.com/api/profiles?search={name}
```

Normalized data (map and civ names, mode, speed, CDN images, `linkedProfiles`), fresh about 30 s
after match end. But: single-maintainer project, **no licence on the repository**, no public API
documentation, no announced rate limits, `/api` root returns 403. **Never a primary source, never on
the critical path.** Aggressive cache plus circuit breaker. When the circuit is open the application
degrades its display; it does not fall over.

## aoestats.io — historical corpus only

```
GET https://aoestats.io/api/db_dumps/     <- the trailing slash is required (otherwise 301, empty body)
```

Weekly parquet dumps. **Every dump since the week of 2026-02-08 contains 0 matches**; the last usable
dump is 2026-02-01 to 2026-02-07. The outage coincides with the aoc-mgz breakage caused by the
2026-02-17 DLC and is very likely the same root cause.

Useless for live data. Valuable in V2 as a reference corpus: 30.7 M matches from 2022-08 to 2026-02,
with `feudal_age_uptime`, `castle_age_uptime`, `imperial_age_uptime` and `opening` precomputed, to
benchmark a player by elo bracket and map.

## Rules

- All access to these sources goes through `packages/providers`. No exceptions.
- Every response is persisted verbatim (`raw_payload jsonb`) before any transformation.
- The fixtures in `packages/providers/fixtures/` are frozen real responses: unit tests never touch
  the network.
- Nightly contract tests hit the real APIs and fail loudly on a schema change. That is how we learn
  about a break before our users do.
