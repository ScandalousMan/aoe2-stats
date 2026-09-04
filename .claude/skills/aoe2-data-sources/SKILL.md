---
name: aoe2-data-sources
description: How to talk to the AoE2 data sources — which one is authoritative, the traps that cost time, and the rules every provider follows. Load before any work on packages/providers or apps/ingester.
---

# AoE2 DE data sources

**Facts live in [`docs/data-sources.md`](../../../docs/data-sources.md): endpoints, payload shapes,
measured sizes, the retention bisection, dated findings. Read it when you need a number.** This file
carries the rules and the traps, which is what you need before writing code.

Never copy a measurement from that document into another file. It is kept true by the nightly
contract tests in `scripts/checks/contract_sources.py`; a copy is true only until the world moves.

## Which source is authoritative

| Source | Role | If it fails |
| --- | --- | --- |
| **Relic** `aoe-api.worldsedgelink.com` | primary — profile resolution, ratings, match discovery | the feature stops; alert |
| **aoe.ms** | primary — replay download | replays are being lost; alert loudly |
| **aoe2companion** | enrichment only, degradable | render without it; **do not alert** |
| **aoestats** | V2 historical corpus only | irrelevant to the MVP |

## Traps that will cost you an afternoon

- **`aoe-api.reliclink.com` fails TLS verification.** It serves a certificate for
  `*.worldsedgelink.com`. Every community document naming that host is stale. Use
  `aoe-api.worldsedgelink.com`, and **never** disable certificate verification to get past it.
- **The replay endpoint rejects `HEAD` and ignores `Range`.** There is no cheap way to test whether a
  replay exists. Every check is a full download. Design around it rather than discovering it.
- **`(gameId, profileId)` must be a real participant pair**, otherwise 404. The same 404 is returned
  whether the replay never existed or has expired — the caller distinguishes them from the match's
  completion time, and getting that wrong means either alert fatigue or silence on the one metric
  that matters.
- **Archive the zip, never the extracted record.** The ratio is about eight to one.
- **`aoestats.io/api/db_dumps/` needs the trailing slash**, or you get a 301 with an empty body.
- **Relic's `slotinfo` and `options` are base64 + zlib, and `slotinfo[].metaData` is two more
  base64 layers on top.** Decode all of them before declaring a field absent. The player colour
  lives at the bottom of that chain (`ScenarioPlayerIndex`), and was declared "not in Relic" once
  after a decode that stopped one interpretation short — which bought a read-time companion call
  that could not colour anything older than companion's first page. `docs/data-sources.md` §1 has
  the chain and the verification; `repositories/matches.py::_slot_colour_id` is the one decoder.
- **aoe2companion's `/api/matches` is paginated by profile recency, not queryable by match.** A
  `?profile_ids=` call returns those profiles' recent matches; an old match is silently absent, and
  `?matchIds=` alone is rejected. It cannot backfill anything.
- **aoe2companion returns 403 at random.** Bot protection that trips intermittently, and it fails
  from CI more often than from a laptop. This is normal operating noise, not an incident. Its contract
  check is deliberately non-blocking.

## Rules every provider follows

- All outbound access goes through `packages/providers`. No exceptions, authentication included.
- Send an honest, identifying `User-Agent`:
  `aoe2-stats/0.1 (+https://github.com/ScandalousMan/aoe2-stats)`. None of these APIs is documented
  or contractual; being recognisable is what lets a maintainer ask us to slow down instead of
  silently blocking us.
- **At most 1 request per second** to the replay endpoint, serially, with jitter and backoff. Its
  rate limits are undocumented, so behave as a guest.
- A 429 or an unexpected 403 from a primary source **stops the whole run** and alerts. It does not
  skip one item and continue. The capture budget is 21 days; there is always tomorrow, and being
  blocked by the source is not recoverable on the same timescale.
- Persist every response verbatim before transforming it. After the retention window closes there
  may be nothing left to re-fetch.
- Validate strictly. An unexpected type is a contract violation, never a coerced value — silent
  coercion is how wrong data becomes permanent.
- Batch. Both Relic endpoints take arrays of profiles.

## Testing

Unit tests use frozen real responses in `packages/providers/fixtures/` and never touch the network.
The nightly contract tests are the only thing that talks to the live APIs, and the only thing that
will tell you a schema changed. When a contract test fails, fix `docs/data-sources.md` first and the
code second — the document is what the next person will trust.
