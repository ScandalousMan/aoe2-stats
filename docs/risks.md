# Risk register

Reviewed whenever a risk materialises or a mitigation changes. Severity is about _irreversibility_
first and likelihood second: this project's defining hazard is that some failures destroy data that
cannot be recreated by anyone, at any price.

| #       | Risk                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | Severity | Mitigation                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **R1**  | **Source retention window — and its shape is not settled.** An ingestion outage longer than the capture budget loses replays permanently. Contradicted 2026-08-28 (`docs/data-sources.md`): rolling window or fixed epoch, unresolved. An epoch can be purged wholesale with no notice, which is a second loss mode the slack below does not cover                                                                                                                                                                                                                                                      | Critical | 21-day capture budget; daily reconciliation over 25 days; **re-measure the boundary on a second profile and again a week later** — pinned means epoch, advanced means rolling — because until that lands the slack cannot be sized and constitution I 4.1.0 forbids widening the budget on the uncorroborated sample; alert when a capture passes its 21-day capture deadline; `expired_total` treated as a severity-1 alert; full backfill on account linking                                                                                                                                                     |
| **R2**  | **`aoe.ms` rate limits or blocking.** Undocumented, and none observed so far — which is not the same as none existing                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | High     | <= 1 req/s globally, serial downloads, jitter, honest identifying `User-Agent`; exponential backoff; on 429/403 stop the run and alert rather than pushing through; per-user quotas; strictly non-commercial use                                                                                                                                                                                                                                                                                                                                                                                                   |
| **R3**  | **A game patch breaks the parser.** Demonstrated, not hypothetical: `aoc-mgz` has been broken since the 2026-02-17 DLC and unfixed for six months, which also killed aoestats                                                                                                                                                                                                                                                                                                                                                                                                                           | Medium   | Downgraded from High by the switch to `aoe2rec-py`, which shipped a fix 4 days after that same DLC. Pluggable engine interface; nightly canary on both engines; versions recorded per parse; bulk re-parse designed into the schema. Fallbacks: build aoe2rec from source with maturin, `AoEInsights/mgz-fast`, or mgz PR #142 in a fork. See ADR 0001                                                                                                                                                                                                                                                             |
| **R4**  | **A third-party API breaks.** Relic is undocumented and has already moved host (reliclink -> worldsedgelink); aoe2companion is unlicensed and returns 403 intermittently; aoestats has been dead since February                                                                                                                                                                                                                                                                                                                                                                                         | High     | Abstract `DataProvider`, so a provider is replaced without touching the domain; Relic primary, companion as degradable enrichment; nightly contract tests; raw payloads retained verbatim so a transformation can be replayed after the fact                                                                                                                                                                                                                                                                                                                                                                       |
| **R5**  | **GDPR.** Archived replays contain the aliases, chat and actions of third-party players who never signed up                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | High     | User point of view only; documented legal basis; processing register maintained in the same PR as any new personal data; separate consent for ingestion; full export and erasure covering storage objects under 001's capture basis; **pseudonymisation — via erasure and the third-party objection route — as the whole remedy for a recording retained under constitution IX's public-recording basis, which is never deleted (IX 3.0.0)**; no public indexing; **all regions EU**; access to replays logged                                                                                                     |
| **R6**  | **Free-tier ceilings.** R2 10 GB, Neon 0.5 GB, Vercel 4 CPU-hours and 1 M invocations. Hitting one could stall ingestion silently                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | Medium   | Nightly free-tier watch warning at 70 % of any allowance; measured runway is roughly 3.5 years of one heavy player on R2; phase-2 migration is a documented decision (ADR 0002) and constitution XII keeps it a configuration change; worst case is about 8.50 EUR/month on OVH                                                                                                                                                                                                                                                                                                                                    |
| **R7**  | **Microsoft IP.** Since constitution X 5.0.0 (004), civilisation icons, map minimaps and country flags are copied into `packages/game-assets/` under Microsoft's Game Content Usage Rules — non-commercial use and display only, revocable, notice required. GCUR does not itself authorise the extraction that produced these packs upstream; that extraction is a settled community norm Microsoft has never enforced against, but a norm is not a permission, and the residual risk is that it could be (004 research.md D3). Vercel Hobby imposes the same non-commercial rule on the whole project | Medium   | Constitution principle X; every pack under `packages/game-assets/` carries a `LICENCE.md` recording source, licence, permitted usage, ruling and the date checked, mirrored in `docs/asset-packs.md`; `scripts/checks/asset_packs.py` fails the build on a pack without that record or on a `READ ONLY` source with files copied in; disclaimer in README and footer, both required for the permission to stand (004 contracts/asset-pack.md); product-designer and reviewer police it. Both constraints break on the same decision, which makes monetisation a product question rather than an infrastructure one |
| **R8**  | **Silent schema drift.** A Relic field changes type and the transformation produces wrong data without erroring                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | Medium   | Strict validation at provider boundaries — fail loudly, never coerce permissively; raw payloads retained so anything can be recomputed; nightly contract tests                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| **R9**  | **Vercel Hobby cron precision.** Once daily, +/- 59 min, no delivery guarantee; a missed day is invisible without monitoring                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | Medium   | The 21-day budget absorbs days of misses; the nightly liveness check catches a stopped cron. Escape hatches in order: 24 separate daily cron entries (allowed, 100 per project, though it leans on the letter of the limit), a GitHub Actions scheduled workflow, then Vercel Pro or phase 2                                                                                                                                                                                                                                                                                                                       |
| **R10** | **Neon cold starts.** Compute suspends after 5 minutes idle, so the daily cron always hits a cold database                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | Low      | Pooled connection string, generous connect timeout, one retry. A few seconds against a 300 s budget is irrelevant                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| **R11** | **Steam OpenID 2.0.** An obsolete protocol with no announced deprecation and no guarantee either                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | Low      | Mandatory server-side verification of the assertion; linking isolated in one module; fallback is manual profile entry verified by a code placed in the in-game alias                                                                                                                                                                                                                                                                                                                                                                                                                                               |

## Materialised so far

- **2026-08-19 — R3.** Confirmed by measurement before a line of parser code was written. `aoc-mgz`
  1.8.51 cannot read a current-patch replay; `aoe2rec-py` 0.1.21 reads it in 0.54 s. Resolved by
  ADR 0001. Severity downgraded from High to Medium.
- **2026-08-19 — R4.** `aoe-api.reliclink.com` now serves a certificate for `*.worldsedgelink.com`,
  so every community document naming that host is stale. Recorded before it could cost anything.
- **2026-08-19 — R4.** aoe2companion returned 403 from CI while the identical request succeeded from
  a residential connection. Intermittent bot protection. Its contract check is now non-blocking, so
  the nightly does not cry wolf over a source the application survives without.

## Verification checklist

The conditions under which this project is considered to be working. Not a test plan — the
properties a test plan has to establish.

**Foundation**

- [x] Constitution ratified and reachable from `CLAUDE.md`
- [x] Five agents with an explicit `model`, three project skills
- [x] Editing a Python file triggers formatting; the implementer agent cannot hand back on red tests
- [x] Nightly watchtower runs and is green

**External sources**

- [x] Steam identifier resolves to an AoE2 profile
- [x] A replay younger than 21 days downloads as a single-member zip
- [x] A replay older than 35 days returns 404, confirming the window has not moved
- [ ] `data.aoe2companion.com`'s profile-search endpoint answers from the production platform's
      (Vercel's) own egress addresses, not only from a residential connection — presently
      unverified, per `docs/data-sources.md` §3's own "Unverified" note; the 12-of-12 reliability
      sample there and R4's materialised 403 were both observed away from Vercel. FR-004d's local
      fallback is what search stands on until this is checked from production
- [x] A `200` response from that same endpoint with a renamed envelope key (BL-1) or a renamed
      field inside every record (BL-5) fails the nightly contract run instead of the guard
      degrading honestly and telling nobody — `assert_companion_search_shape` is unit-tested for
      both cases plus the one-bad-record contrast case (`scripts/checks/tests/test_contract_shapes.py`,
      7/7 green), and `contract_sources.py`'s `_companion_search` check that calls it is blocking
      and runs inside the nightly workflow's `0 3 * * *` schedule (T385a)

**Parsing**

- [x] The reference fixture parses in under 2 s and yields `Build` and `Research` actions
- [ ] The engine interface allows selecting mgz by configuration, and its failure on a current-patch
      file is quarantined rather than crashing the run
- [ ] A recording whose raw size exceeds `ANALYSIS_MAX_RAW_BYTES` is refused before parsing starts,
      so a hostile or corrupt replay cannot exhaust memory or hang the process — the measured
      amplification the bound is derived from lives in the `replay-parsing` skill and is not
      restated here

**Ingestion** — the real measure of the MVP

- [ ] Linking an account marks it for backfill, and the next cycle enqueues every match in the
      backfill window `docs/data-sources.md` records — the figure lives there and is not restated here
- [x] After a real match, the stored object appears inside the SC-002 target — watched nightly rather
      than checked once, by `scripts/checks/capture_audit.py`'s p95 lag assertion over newly
      discovered captures (see that script's own docstring for the backfill exclusion this depends on
      and for why the target itself is not restated as a second literal here)
- [ ] A run interrupted by its time budget leaves nothing in progress and resumes cleanly
- [ ] Replaying the same match creates no duplicate and rewrites no file
- [ ] A network failure mid-download leaves no capture marked stored without its file
- [x] `expired_total` stays at 0 — the guarantee is now split across two nightly checks rather than
      one spot check, and neither alone is the whole of it (see both scripts' own docstrings):
      `scripts/checks/capture_audit.py` catches a fresh loss over a trailing window and recovers on
      its own once it ages out, while `scripts/checks/alert_audit.py` fails on the underlying
      severity-1 `expired_capture` alert until a human has actually investigated it, however long ago
      it happened — the durable half of the guarantee lives there, not in the windowed check
- [ ] **The retention boundary has been re-measured on a profile other than 2322168, and again at
      least a week after the 2026-08-28 sample**, and `docs/data-sources.md` records the outcome as
      settled or still open. This is the only thing that resolves R1's two readings, and nothing else
      in this repository is watching for it: the nightly `aoe.ms` probe draws its candidates from
      `getRecentMatchHistory`, which serves only a recent window, so its "old replay is 404" branch
      finds no candidate and reports a note instead of a result. Until this lands the capture budget
      may be tightened and may not be widened (constitution I 4.1.0)

**Hosting**

Verified against the live deployment on 2026-08-20. Each line records _how_ it was checked, not
only that it was: "the bucket is EU" was ticked-shaped but uncheckable, and that vagueness is what
let a Western-Europe _location hint_ pass for an EU _jurisdiction_ — the two look alike in the
Cloudflare UI and only the S3 endpoint tells them apart (`<account>.eu.r2...` carries the
jurisdiction, `<account>.r2...` does not).

- [x] Functions report region `cdg1`; database and bucket are EU — both functions report `cdg1` in
      `vercel inspect` and in `x-vercel-id`; Neon runs in `eu-central-1`; the R2 bucket carries the
      EU jurisdiction, confirmed by its `.eu.` endpoint
- [x] A pull request gets a preview deployment; `main` deploys production — pull request #2 carried
      a passing Vercel check and a preview deployment, and merging it produced a production
      deployment on its own, with no CLI involved. Preview URLs answer `302`: that is Vercel's
      deployment protection, not an application fault, and reaching one from a script needs a
      bypass token
- [x] The cron endpoint returns 401 without its secret — verified in production for both `GET` (what
      Vercel Cron actually sends) and `POST`, each returning the error envelope
- [x] The Python bundle stays under the 500 MB limit — 43.69 MB per function, 8.7% of the ceiling.
      Both functions carry the same bundle today; only the cron one grows when the replay engine
      lands at T055
- [x] A deploy shipping a missing or invalid configuration key, or an unmigrated schema, reaches
      production and fails at request time rather than being caught before traffic arrives — closed
      by T390–T394. `config-preflight.mjs` fails the **build** on the former; `production-health.mjs`'s
      post-deploy smoke check and `/api/health`'s `schema_out_of_date` code catch the latter

**Front end**

- [ ] Storybook renders components in both themes
- [ ] visual-reviewer returns a reasoned FAIL on a component deviated from its spec
- [ ] Pull-request visual regression runs only on touched stories

**Data rights**

- [ ] Export contains the archived replays
- [ ] Erasure removes account, links, capture records and storage objects, verified by listing the
      bucket **under 001's capture prefix**. The retention prefix is excluded and that is not an
      oversight: constitution IX 3.0.0 (2026-08-24, and unchanged by 4.0.0) stopped erasure and third-party objection from
      deleting a recording retained under its public-recording basis, so a check that lists the whole
      bucket now fails correctly. What those two routes must be verified to do there is
      **pseudonymise every identifier this service holds** about a person appearing in a recording,
      leaving the object and its checksum intact
- [ ] Recordings retained under FR-045/046/047 stay under `ANALYSIS_RETENTION_CAP_BYTES`, and growth
      against that cap is observable rather than discovered by a refusal — the free-tier watch
      counts the retained-recording prefix separately from 001's capture prefix and warns at 70 %
      of the analysis cap (T378)
