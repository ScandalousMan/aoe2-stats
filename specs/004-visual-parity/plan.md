# Implementation Plan: Visual Parity — Game Assets and Rich Profile/Match Presentation

**Branch**: `004-visual-parity` | **Date**: 2026-08-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-visual-parity/spec.md`

## Summary

Bring the profile page and match history to visual parity with third-party AoE2 sites: civilisation
icons, minimap thumbnails, canonical player colours, winner/loser, rating and rating movement,
persona name, country flag, Steam avatar, and a site header.

**The spec assumed this was a presentation feature. Phase 0 found it is not.** Five of the six
per-participant facts US1 renders (`civ_id`, `team_id`, `result`, `rating`, `rating_diff`) are
declared as columns, read by three routers, and **written by nobody** — the ingester's
`upsert_match_player` inserts the primary key and stops. The sixth, `color_id`, has no source in
Relic at all. So the work is three layers deep, in order:

1. **Make the data exist.** Project `matches.raw_payload` — already stored verbatim under
   constitution IV — into `match_players`, as a widened upsert plus a re-runnable backfill. No new
   fetch, no capture path touched.
2. **Enrich the one fact Relic does not serve.** Player colour is not in any Relic field. It comes
   from aoe2companion's match endpoint — proven live to return it for a match with no captured replay
   — read at display time, the way the app already pulls civ names, and cached back into
   `match_players.color_id`. Not the ingester, not the capture path, so FR-014 stands as written.
3. **Present it.** Asset packs behind an executable licence gate, then the components.

The asset question resolved to a ruling rather than a shopping list: **no openly-licensed AoE2 asset
pack exists**, so constitution X 5.0.0 either accepts a Game-Content-Usage-Rules-only pack or it
permits nothing at all. It accepts one — its own words are "as non-Microsoft fan sites do" — and the
gate FR-011 imposes is a recorded source, permitted usage and check date, enforced by a script rather
than by good intentions.

Full reasoning and evidence: [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.13 (backend, ingester, checks); TypeScript 5 / React 19 (front end)

**Primary Dependencies**: FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, uv workspace; Vite 8,
TanStack Router/Query 5, Tailwind v4, Storybook 10, Playwright. No new runtime dependency.

**Storage**: Neon Postgres (EU). One additive migration: `aoe_profiles.avatar_hash`. No new table.

**Testing**: pytest (workspace-wide, network blocked by an autouse socket guard); Vitest +
Testing Library; Playwright visual regression against the static Storybook build, diff-scoped by
`scripts/visual/run.mjs`; `node --test` for the token build.

**Target Platform**: Vercel Hobby `cdg1` + Neon EU + Cloudflare R2 EU (phase 1); OVH VPS (phase 2).

**Project Type**: Web application — Python API + ingester, React SPA, shared design system.

**Performance Goals**: The profile route stays database-only (the avatar hash is stored, not
fetched). The match-history view makes at most **one** companion enrichment call per page — batched
over the page's game ids, degradable, and cached into `match_players.color_id` so a second view of
the same matches is database-only. Colour is the only field that call supplies; civ, map, result and
rating are already in the database from D1. Asset payload ≤10 MB total, WebP, served as static files.

**Constraints**: All assets ≤10 MB and licence-recorded; no hard-coded style values; every new or
changed component carries a Storybook story and passes visual regression in light and dark; the
backfill is re-runnable and never re-fetches; `expired_total` stays at zero.

**Scale/Scope**: 3 user stories, 16 functional requirements. 60 civ icons, 435 minimaps, ~260 flags,
8 colour token pairs. Touches `packages/game-assets` (new), `packages/design-system`,
`packages/storage`, `packages/providers`, `apps/api`, `apps/ingester`, `apps/web`, one migration,
`docs/`, and five artifacts stale against constitution 5.0.0.

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design — verdicts below are the
post-design ones._

| #        | Principle                                     | Verdict                                                 | How this feature satisfies it                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| -------- | --------------------------------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **I**    | Capture Outranks Analysis                     | **PASS**                                                | This is a display feature and it degrades no capture path. `upsert_match_player` widens to write columns from a response the same transaction already holds — no extra request, no change to `CAPTURE_BUDGET_DAYS`, no change to the capture enqueue. The backfill reads `raw_payload` from the database and never re-fetches. The colour enrichment (D2) is a read-time companion call on the display path, not the capture path, and its failure is degradation by contract. `expired_total` cannot move.                                                                                                                                                                                                                                                                          |
| **II**   | Python Backend                                | **PASS**                                                | The projection, the backfill, the colour enrichment and the licence check are Python. The front end gains no business logic: `civ_id → name` stays in `apps/api` (feature 002's home), outcome and rating arithmetic stay in the repository layer, and the client receives decided values plus an asset key.                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| **III**  | All External Data Goes Through a DataProvider | **PASS**                                                | No new provider and no new endpoint — the colour comes from `enrich_matches` on the existing companion provider, widened to parse per-participant fields already present in the response it fetches (`GET /api/matches`). Timeout, retry, token bucket, circuit breaker and the `provider_calls` sink are inherited unchanged from `AsyncBaseProvider`, and companion is the constitution's designated degradable-enrichment source. Asset packs are copied in at development time by a human; nothing fetches them at build, test or run time (feature 002's FR-011/FR-014 rule, adopted here). The Steam avatar is a client-side `<img src>`, not a connection from `apps/*` or `packages/core` — FR-015, and `tests/architecture/test_import_graph.py` keeps `httpx` out of both. |
| **IV**   | Raw Is Sacred, Derived Is Disposable          | **PASS** — and this feature is the principle paying off | The whole of D1 is possible only because `matches.raw_payload` was kept verbatim. Nothing is modified or deleted; the projection is a derived artifact, fully recomputable from the raw, and the backfill is re-runnable and idempotent by construction. No migration is required to re-derive it.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| **V**    | Parsing Runs in an Isolated, Pluggable Engine | **N/A**                                                 | No replay parsing. The spec puts unit/building/resource icons out of scope precisely because they need parsed data, which is V2.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| **VI**   | Tokens First                                  | **PASS**                                                | The eight player colours ship as design-system colour tokens with paired `-contrast` tokens, not as hard-coded hex in a component. Icon sizing closes gap **DS-7** (`specs/README.md:157`), which currently has components sizing marks from `1em` for want of a token. Every new component gets a Storybook story — the principle's own definition of existing.                                                                                                                                                                                                                                                                                                                                                                                                                     |
| **VII**  | Visual Tests Are Mandatory                    | **PASS**                                                | Every new and changed component gets stories in both themes, and the packs are mounted in Storybook via `staticDirs` so visual regression runs against the real images rather than missing ones — the reason D5 rejects `apps/web/public/`. Degraded stories (unknown civ, unknown map, null colour, null avatar) are stories too, so FR-010's no-broken-image rule has a baseline. Known limit, from prior experience on this repo: static story screenshots are blind to focus and hover, so the header's navigation states need an interaction test, not only a snapshot.                                                                                                                                                                                                         |
| **VIII** | No Secrets in the Clear                       | **PASS**                                                | No new secret, no new environment variable. If one is ever added, `.env.example` must move in the same commit — `apps/api/tests/conftest.py:78-103` asserts the key set at import time and fails the whole suite otherwise.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| **IX**   | GDPR by Design                                | **PASS, with one mandatory task**                       | `avatar_hash` is **new personal data**, so `docs/privacy/processing-register.md` is updated **in the same PR**, not as a follow-up. It is public data from a public source (`docs/data-sources.md:299`) under the same legitimate-interest basis as the `alias` and `country` it sits beside, carried and never used to link or merge profiles (constitution IX's unverified-claim rule). It joins the GDPR export and the erasure pseudonymisation path alongside those two fields. No new capture, no new indexing, no change to the objection route. All regions remain EU; the Steam CDN serves an image to the viewer's browser and receives no data from this service.                                                                                                         |
| **X**    | Intellectual Property                         | **PASS** — this is the feature's subject                | Both anchors are kept and strengthened: strictly non-commercial, and the disclaimer stays in the README and the footer **verbatim** (`Footer.test.tsx` asserts the footer against `README.md`, so the two cannot drift). Every pack copied in carries a `LICENCE.md` recording source, permitted usage and check date, mirrored in `docs/asset-packs.md`; `scripts/checks/asset_packs.py` fails the build on a pack without one, which is what turns SC-003 from a promise into a gate. The ruling that GCUR-only packs qualify, and the residual extraction risk that ruling accepts, are recorded in [research.md](./research.md) D3 and in `docs/risks.md` R7 rather than left implied.                                                                                           |
| **XI**   | Documentation Is in English                   | **PASS**                                                | All artifacts, code, comments and commit messages English.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| **XII**  | Portable by Construction                      | **PASS**                                                | Assets are static files under one URL prefix, mounted identically by Vite and by any static server — no Vercel-specific route, no filesystem read at runtime, no local state. The backfill is a script invoked by hand or by cron, not a platform hook. Nothing added runs only on Vercel or only on a VPS.                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |

**Post-design re-check**: no verdict changed between the pre-Phase-0 and post-Phase-1 passes. One
item moved from PASS to PASS-with-a-named-task (IX, the processing register), and one gained an
executable gate it did not have before (X, the check script).

## Project Structure

### Documentation (this feature)

```text
specs/004-visual-parity/
├── plan.md              # This file
├── research.md          # Phase 0 — D1..D8, the licence ruling, the measured keying
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── http-api.md      # The API delta: widened rows, avatar_hash, participants
│   └── asset-pack.md    # The licence-record format and the check that enforces it
├── checklists/
└── tasks.md             # /speckit-tasks — NOT created here
```

### Source Code (repository root)

```text
packages/
├── game-assets/                     # NEW — one directory per pack, each with its own record
│   ├── civilisations/{LICENCE.md, *.webp}      # 60, keyed name.lower().replace(' ','_')
│   ├── maps/{LICENCE.md, *.webp}               # 435, keyed name.lower().replace(' ','-')
│   ├── flags/{LICENCE.md, *.svg}               # ~260, ISO 3166-1 alpha-2 (MIT)
│   └── src/index.ts                            # key -> URL, and the "not covered" answer
├── design-system/
│   ├── tokens/color.json                       # + 8 player colours, each with -contrast
│   ├── specs/{README.md, match-history.md, profile-summary.md, site-header.md}
│   └── src/components/
│       ├── CivilisationIcon/  MapThumbnail/  PlayerColourSwatch/
│       ├── CountryFlag/  PlayerAvatar/  SiteHeader/          # NEW
│       └── MatchRow/  MatchDetailPanel/  ProfileSummary/     # WIDENED
├── storage/src/aoe2stats_storage/
│   ├── repositories/matches.py                 # + rating, team_id, color_id, participants
│   └── revision.py                             # EXPECTED_SCHEMA_REVISION — same commit
└── providers/src/aoe2stats_providers/
    ├── base.py                                 # MatchEnrichment + per-participant; PlayerSearchResult + avatar_hash
    └── companion/provider.py                   # parse what the response already carries

apps/
├── api/src/aoe2stats_api/routers/{matches.py, players.py}
├── ingester/src/aoe2stats_ingester/discover.py # widened upsert + the enrichment step
└── web/src/features/{players,matches}/{api.ts, mappers.ts, format.ts}

infra/migrations/versions/                      # one additive migration: avatar_hash
scripts/
├── checks/asset_packs.py                       # the FR-011 / SC-003 gate
└── ops/backfill_match_players.py               # re-runnable, reads raw_payload only

docs/
├── asset-packs.md                              # NEW — the licence record
├── risks.md                                    # R7 rewritten
└── privacy/processing-register.md              # avatar_hash, same PR (constitution IX)

README.md                                       # :29 corrected; :31-34 disclaimer untouched
```

**Structure Decision**: The existing uv + pnpm workspace, with one new package. `packages/game-assets`
is a package rather than a directory inside `design-system` or `apps/web/public` for three reasons,
in order of weight: Storybook must be able to serve the packs or visual regression runs against
missing images (constitution VII); the licence gate applies _per pack_, so making a pack a directory
makes the gate a directory walk; and the design system stays asset-agnostic — components take an
image URL as a prop and never import a PNG, which keeps the FR-010 degrade path to "the prop is
`undefined`" and keeps a 10 MB binary payload out of the package everything else imports.

### Implementation order

Each layer is independently shippable and independently testable, and the order is forced by D1 —
presentation built first would have nothing to render.

| Phase | Delivers                                                                                                     | Gates                                                           |
| ----- | ------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------- |
| **A** | Licence gate, packs, colour tokens, the five stale-artifact corrections                                      | FR-011, FR-012, SC-003 — unblocks everything, blocks on nothing |
| **B** | `raw_payload` → `match_players` projection + backfill                                                        | D1 — makes FR-001/004/005 possible at all                       |
| **C** | Companion read-time colour enrichment (`GET /api/matches`) → `color_id`, cached                              | D2 — makes FR-003 possible at all, no replay                    |
| **D** | API widening: participants, `rating`, `team_id`, `color_id`, `avatar_hash` + migration + processing register | FR-005, FR-008a, FR-015                                         |
| **E** | US1 — the match views                                                                                        | FR-001..006, FR-010, FR-013                                     |
| **F** | US2 — the profile identity                                                                                   | FR-007, FR-008, FR-008a                                         |
| **G** | US3 — site header                                                                                            | FR-009                                                          |

A is genuinely parallel with B and C. E depends on A+B+C+D; F on A+D; G on nothing but A.

## Complexity Tracking

| Violation                                                                                                                                                   | Why Needed                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | Simpler Alternative Rejected Because                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A read-time companion call on the match display path.** _(Not an FR-014 violation — recorded because it is the one new outbound call on a display path.)_ | `color_id` is FR-003 and US1 acceptance scenario 5, and Relic serves no colour in any field — `matchhistorymember`, `slotinfo` (its fields and its base64 `metaData`) and `options` all decoded and checked (research.md D2). aoe2companion serves it, proven live for a match with `replay: false`, so no capture is needed; it is the constitution's designated degradable-enrichment provider, already wired, and the colour is read when a match is shown and cached into `match_players.color_id`. Because it enriches the display and never the capture pipeline, FR-014 stands as written and needs no amendment. | _Wire it into the ingester instead_ — that would make colour part of what is captured, engaging FR-014 for no benefit, since colour never changes and a display-time read plus cache is enough. _The replay header_ — a real source (`color_id` is in it), but only for captured-and-parsed replays, strictly worse coverage than companion, and it pulls V2 parsing forward. _Derive from team and ordering_ — an invention; players pick their own colours (research.md D2). _Drop FR-003_ — a P1 scenario abandoned while a proven source exists. |
| **A new workspace package for static files.**                                                                                                               | The licence gate is per pack and must be executable (SC-003); Storybook must serve the packs for mandatory visual regression; the design system must not carry a 10 MB binary payload or depend on the game.                                                                                                                                                                                                                                                                                                                                                                                                             | _`apps/web/public/`_ — Storybook cannot reach it, so visual regression would pass against missing images. _`packages/design-system/assets/`_ — inverts the dependency and puts the payload inside the package every consumer imports.                                                                                                                                                                                                                                                                                                                |
| **A backfill script.**                                                                                                                                      | Every `match_players` row already ingested has five NULL columns whose values sit in `raw_payload`. Without it, US1 is correct only for matches discovered after this ships, and the acceptance test ("load a profile with known matches") fails on real data.                                                                                                                                                                                                                                                                                                                                                           | _Let it fill forward only_ — silently correct for new rows and silently wrong for history, which is the failure mode the product already has. _Re-fetch from Relic_ — a capture-path load for data already on disk, against constitution IV's whole point.                                                                                                                                                                                                                                                                                           |
