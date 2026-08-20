# Risk register

Reviewed whenever a risk materialises or a mitigation changes. Severity is about *irreversibility*
first and likelihood second: this project's defining hazard is that some failures destroy data that
cannot be recreated by anyone, at any price.

| # | Risk | Severity | Mitigation |
| --- | --- | --- | --- |
| **R1** | **31-day retention window.** An ingestion outage longer than the capture budget loses replays permanently | Critical | 21-day capture budget (10 days of slack); daily reconciliation over 25 days; alert when a capture passes its 21-day capture deadline, with ~10 days still left to act; `expired_total` treated as a severity-1 alert; full backfill on account linking |
| **R2** | **`aoe.ms` rate limits or blocking.** Undocumented, and none observed so far — which is not the same as none existing | High | <= 1 req/s globally, serial downloads, jitter, honest identifying `User-Agent`; exponential backoff; on 429/403 stop the run and alert rather than pushing through; per-user quotas; strictly non-commercial use |
| **R3** | **A game patch breaks the parser.** Demonstrated, not hypothetical: `aoc-mgz` has been broken since the 2026-02-17 DLC and unfixed for six months, which also killed aoestats | Medium | Downgraded from High by the switch to `aoe2rec-py`, which shipped a fix 4 days after that same DLC. Pluggable engine interface; nightly canary on both engines; versions recorded per parse; bulk re-parse designed into the schema. Fallbacks: build aoe2rec from source with maturin, `AoEInsights/mgz-fast`, or mgz PR #142 in a fork. See ADR 0001 |
| **R4** | **A third-party API breaks.** Relic is undocumented and has already moved host (reliclink -> worldsedgelink); aoe2companion is unlicensed and returns 403 intermittently; aoestats has been dead since February | High | Abstract `DataProvider`, so a provider is replaced without touching the domain; Relic primary, companion as degradable enrichment; nightly contract tests; raw payloads retained verbatim so a transformation can be replayed after the fact |
| **R5** | **GDPR.** Archived replays contain the aliases, chat and actions of third-party players who never signed up | High | User point of view only; documented legal basis; processing register maintained in the same PR as any new personal data; separate consent for ingestion; full export and erasure covering storage objects; third-party objection with pseudonymisation; no public indexing; **all regions EU**; access to replays logged |
| **R6** | **Free-tier ceilings.** R2 10 GB, Neon 0.5 GB, Vercel 4 CPU-hours and 1 M invocations. Hitting one could stall ingestion silently | Medium | Nightly free-tier watch warning at 70 % of any allowance; measured runway is roughly 3.5 years of one heavy player on R2; phase-2 migration is a documented decision (ADR 0002) and constitution XII keeps it a configuration change; worst case is about 8.50 EUR/month on OVH |
| **R7** | **Microsoft IP.** Game Content Usage Rules: non-commercial, no game assets. Vercel Hobby imposes the same non-commercial rule | Medium | Constitution principle X; no game asset in the repository; original design system; disclaimer in README and footer; product-designer and reviewer police it. Both constraints break on the same decision, which makes monetisation a product question rather than an infrastructure one |
| **R8** | **Silent schema drift.** A Relic field changes type and the transformation produces wrong data without erroring | Medium | Strict validation at provider boundaries — fail loudly, never coerce permissively; raw payloads retained so anything can be recomputed; nightly contract tests |
| **R9** | **Vercel Hobby cron precision.** Once daily, +/- 59 min, no delivery guarantee; a missed day is invisible without monitoring | Medium | The 21-day budget absorbs days of misses; the nightly liveness check catches a stopped cron. Escape hatches in order: 24 separate daily cron entries (allowed, 100 per project, though it leans on the letter of the limit), a GitHub Actions scheduled workflow, then Vercel Pro or phase 2 |
| **R10** | **Neon cold starts.** Compute suspends after 5 minutes idle, so the daily cron always hits a cold database | Low | Pooled connection string, generous connect timeout, one retry. A few seconds against a 300 s budget is irrelevant |
| **R11** | **Steam OpenID 2.0.** An obsolete protocol with no announced deprecation and no guarantee either | Low | Mandatory server-side verification of the assertion; linking isolated in one module; fallback is manual profile entry verified by a code placed in the in-game alias |

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

**Parsing**

- [x] The reference fixture parses in under 2 s and yields `Build` and `Research` actions
- [ ] The engine interface allows selecting mgz by configuration, and its failure on a current-patch
      file is quarantined rather than crashing the run

**Ingestion** — the real measure of the MVP

- [ ] Linking an account marks it for backfill, and the next cycle enqueues every match in the
      31-day window
- [ ] After a real match, the stored object appears within 48 hours — the daily cadence spends ~25 h
      on detection before a capture is even attempted
- [ ] A run interrupted by its time budget leaves nothing in progress and resumes cleanly
- [ ] Replaying the same match creates no duplicate and rewrites no file
- [ ] A network failure mid-download leaves no capture marked stored without its file
- [ ] `expired_total` is 0 after a week of operation

**Hosting**

Verified against the live deployment on 2026-08-20. Each line records *how* it was checked, not
only that it was: "the bucket is EU" was ticked-shaped but uncheckable, and that vagueness is what
let a Western-Europe *location hint* pass for an EU *jurisdiction* — the two look alike in the
Cloudflare UI and only the S3 endpoint tells them apart (`<account>.eu.r2...` carries the
jurisdiction, `<account>.r2...` does not).

- [x] Functions report region `cdg1`; database and bucket are EU — both functions report `cdg1` in
      `vercel inspect` and in `x-vercel-id`; Neon runs in `eu-central-1`; the R2 bucket carries the
      EU jurisdiction, confirmed by its `.eu.` endpoint
- [ ] A pull request gets a preview deployment; `main` deploys production — **not satisfied**: every
      deployment so far is a CLI-driven production one, and pull request #2 carries no Vercel check.
      The Git integration is not building pull requests, so the preview environment its variables
      were configured for does not exist yet
- [x] The cron endpoint returns 401 without its secret — verified in production for both `GET` (what
      Vercel Cron actually sends) and `POST`, each returning the error envelope
- [x] The Python bundle stays under the 500 MB limit — 43.69 MB per function, 8.7% of the ceiling.
      Both functions carry the same bundle today; only the cron one grows when the replay engine
      lands at T055

**Front end**

- [ ] Storybook renders components in both themes
- [ ] visual-reviewer returns a reasoned FAIL on a component deviated from its spec
- [ ] Pull-request visual regression runs only on touched stories

**Data rights**

- [ ] Export contains the archived replays
- [ ] Erasure removes account, links, capture records and storage objects, verified by listing the
      bucket
