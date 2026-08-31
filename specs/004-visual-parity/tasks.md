---
description: 'Task list for visual parity — game assets and rich profile/match presentation'
---

# Tasks: Visual Parity — Game Assets and Rich Profile/Match Presentation

**Input**: Design documents from `/specs/004-visual-parity/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included and mandatory. The seven scenarios in [quickstart.md](./quickstart.md) are the
source, and every test task names the scenario it encodes. A test task is done when the test exists
**and fails for the right reason**, carrying `@pytest.mark.xfail(strict=True, reason="<id> not
implemented yet")` with the module under test imported _inside_ the test body; the implementing task
removes the marker, which `strict=True` forces rather than merely permits. TypeScript tests have no
equivalent marker — there they are written and left failing, and the implementing task is what turns
them green, so a TypeScript test task and its implementer are never separately committed.

**Organization**: grouped by user story, in the order [plan.md](./plan.md)'s implementation table
forces. That order is not a preference: research.md **D1** found that five of the six per-participant
facts US1 renders are written by nobody, so presentation built first would have nothing to render.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel — different files, no dependency on an incomplete task
- **[Story]**: US1..US3, mapping to the user stories in [spec.md](./spec.md)
- Every task names its exact file path

## Path Conventions

Per [plan.md](./plan.md): `packages/{game-assets,design-system,storage,providers}/`,
`apps/{api,ingester,web}/`, `infra/migrations/`, `scripts/{checks,ops}/`, `docs/`.

## Numbering starts at T401, deliberately

001 reaches T109, 002 runs T201 to T215, and 003 runs from T301 upward. Ids resolve **across** features since
T202, so they have to be unique across features. This feature's artifacts cite nothing from another
feature by number, but the linter's `task-refs` check resolves ids repository-wide and a colliding
range would make "who owed this" unanswerable. A disjoint range costs nothing.

## What this feature is, restated because the spec says otherwise

The spec calls 004 "the presentation and the assets; it changes nothing about what is ingested".
Phase 0 found that half of that is wrong, and the task order is the correction:
`match_players.civ_id`, `team_id`, `result`, `rating` and `rating_diff` are declared as columns, read
by three routers and the privacy export, and **written by nobody** — `upsert_match_player` inserts the
primary key and stops. `GET /api/matches` has been serving `civilisation: null` and `result: null` for
every production row since 001 shipped. Phase 2 is therefore not scaffolding for the interface; it is
the feature. Anyone who starts at Phase 3 will build components that render nulls and pass every test
they write.

## Scenario coverage map

| quickstart scenario                             | Story    | Task(s) that encode it |
| ----------------------------------------------- | -------- | ---------------------- |
| 1 — The licence gate refuses an unrecorded pack | —        | T402, T403             |
| 2 — The projection fills what was never written | —        | T412, T414             |
| 3 — Colour arrives from companion at read time  | —        | T417, T419             |
| 4 — The API delta                               | —        | T421, T424             |
| 5 — US1, a match is legible at a glance         | US1      | T429, T433, T434       |
| 6 — US2 and US3, the profile and the site       | US2, US3 | T439, T443, T447       |
| 7 — The gates that must be green to merge       | —        | T446                   |

---

## Phase 1: Setup — the licence gate, the packs, the tokens (plan phase A)

**Purpose**: everything constitution X's permission depends on, plus the corrections that stop the
repository from contradicting it. This phase unblocks every other one and blocks on none of them.

- [x] T401 Create the `packages/game-assets` workspace member and mount it at the **one** URL prefix both consumers use: `packages/game-assets/package.json` (private, `type: module`, a `test` script running vitest, modelled on `packages/design-system/package.json`), `packages/game-assets/tsconfig.json`, an empty `packages/game-assets/src/index.ts`, and the three empty pack directories `packages/game-assets/civilisations/`, `packages/game-assets/maps/`, `packages/game-assets/flags/`. `pnpm-workspace.yaml` already globs `packages/*`, so no registration edit is needed and none should be invented. Then mount: `staticDirs: [{ from: '../../game-assets', to: '/game-assets' }]` in `packages/design-system/.storybook/main.ts` (today `[]`), and a static copy of the same directory to `/game-assets` in `apps/web/vite.config.ts`. **The two prefixes must be byte-identical**, because the whole reason a component takes an image URL as a prop is that its `src` is the same string in the app and in a story. Adding a build-time dependency for the Vite half is acceptable; adding a runtime one is not ([plan.md](./plan.md) Technical Context). `apps/web/public/` is not an option and the reason is recorded — Storybook cannot reach it, so visual regression would run against missing images and pass (research.md **D5**)
- [x] T402 [P] Write the licence-gate tests in `scripts/checks/tests/test_asset_packs.py`, `xfail(strict=True, reason="T403 not implemented yet")`, encoding quickstart scenario 1 against a fixture tree the test controls rather than the real `packages/game-assets`: a pack directory with no `LICENCE.md` fails; a `LICENCE.md` missing any one of the five fields in [contracts/asset-pack.md](./contracts/asset-pack.md) fails, asserted **once per field** and never with one case for the file; a record whose `Ruling` is `READ ONLY` while the directory holds files fails; the package exceeding its size budget fails; a pack absent from `docs/asset-packs.md`, or disagreeing with it, fails; and — the case the check exists for — **the disclaimer paragraph deleted from `README.md` fails**. That last one is not decoration: constitution X grants the permission on two anchors, non-commercial and the disclaimer, and "remove either anchor and the permission lapses" is its own wording. A check that guards the packs without guarding the anchors would go on passing on the pull request that made every pack unlawful. This is FR-011 and SC-003 made executable
- [x] T403 Implement `scripts/checks/asset_packs.py` — read-only, no network, stdlib only like `spec_lint.py`, printing one line per pack naming its ruling and check date — and remove T402's markers. Wire it into `.github/workflows/pr.yml` as its own job with its own `changes` filter over `packages/game-assets/**`, `docs/asset-packs.md`, `README.md` and `scripts/checks/asset_packs.py`, and into `.github/workflows/nightly.yml`. **The `README.md` path in that filter is load-bearing**: the anchor can be removed by a pull request that touches no asset, and the job has to run on exactly that pull request. **Also add `packages/game-assets/**` to the `changes` job's existing `web` filter** in the same file: without it a pack-only change (an icon added, removed or re-encoded) runs neither `pnpm test` — so T408's resolver tests never execute — nor the `visual` job, even though Storybook now mounts that exact directory via `staticDirs` (T401), which makes a pack change the definition of a visual change invisible to constitution VII's mandatory gate. Enforce the package's total size budget here too — [research.md](./research.md) **D5** fixes it, and this check is the only thing between the repository's one binary payload and unbounded growth
- [x] T404 [P] Copy the civilisation icon pack into `packages/game-assets/civilisations/`: the 60 images from SiegeEngineers/aoe2techtree's img/Civs/ directory, re-encoded to WebP at the bound [research.md](./research.md) **D5** sets, named `<name.lower().replace(' ', '_')>.webp`, plus `packages/game-assets/civilisations/LICENCE.md` with all five fields. (The pack holds 60 files; feature 002's mapping names 59 of them and all 59 resolve — the 60th has no `civ_id → name` entry, so it is simply never requested. T409's build-generated coverage set makes that harmless either way.) The record's `Licence` field is **`None found`**, not MIT: the repository root's MIT covers its code, and that repository's img/README exists precisely to carve the images out of it — say so and name that file as the evidence, because eliding it is how a pack gets described as MIT when it is not. Copy the files by hand from the published repository; nothing in this project fetches an asset at build, test or run time (feature 002's rule, adopted here)
- [x] T405 [P] Copy the minimap pack into `packages/game-assets/maps/`: the 435 images from SiegeEngineers/aoe2cm2's public/images/maps/ directory, re-encoded to WebP at **D5**'s bound, named `<map_name.lower().replace(' ', '-')>.webp`, plus `packages/game-assets/maps/LICENCE.md`. Same ruling and same `None found` licence, evidenced by the repository's null licence field and its own credits block. FR-016 is why this is a thumbnail pack and not a glyph set; FR-002 is what it serves. Coverage is 435 files against an unbounded string space — custom and tournament maps miss, and that is FR-010's degrade path arriving as designed, not a defect to close by inventing entries
- [x] T406 [P] Copy the country-flag pack into `packages/game-assets/flags/`: the SVG set from lipis/flag-icons, named by ISO 3166-1 alpha-2 lowercased, plus `packages/game-assets/flags/LICENCE.md`. This one really is MIT, and the flag designs themselves are public domain — record it as MIT rather than reaching for the Game Content Usage Rules, because a record that overstates the constraint is as wrong as one that understates it. Flags are not game assets and constitution X does not reach them; the pack still carries a record, because the check walks directories and does not care why a pack is lawful. Serves FR-008
- [x] T407 Write `docs/asset-packs.md` from the table in [research.md](./research.md) **D3**, mirroring the three `LICENCE.md` records field for field and carrying the `AVOID` and `READ ONLY` rows too — a reader has to be able to see which sources were rejected and why, or the next person re-evaluates them from scratch. **T404 to T407 are one commit and were never separately green**: T403's check fails a pack whose record is absent from this file, so packs landing without it turn the tree red, and this file landing without packs describes files that do not exist. `CLAUDE.md`'s "smallest set of tasks that was ever simultaneously green" is exactly this case
- [x] T408 [P] Write the resolver tests in `packages/game-assets/src/index.test.ts` against the contract in [contracts/asset-pack.md](./contracts/asset-pack.md): a known hit returns a URL under `/game-assets/`; **a known miss returns `undefined` and never a placeholder path or a URL that 404s**; a map name containing a space resolves; a map name containing punctuation resolves or misses cleanly — that is where a string transform quietly stops matching and it is the only interesting case in the file. The miss assertion is the one that makes FR-010's "MUST NOT show a broken image" a type-level guarantee instead of a runtime hope, so it is asserted on the return value's type as well as its value
- [x] T409 Implement `packages/game-assets/src/index.ts` — `civilisationIcon(civName)`, `mapThumbnail(mapName)`, `countryFlag(countryCode)` — with the coverage set **generated from the directory listing at build**, not hand-maintained, so a file added or removed cannot drift from what the resolver claims. `civilisationIcon` takes the **name and not the id**: feature 002 owns `civ_id → name` and this feature keys off it rather than introducing a second id table (spec Assumption). Turns T408 green
- [x] T410 [P] Add the eight canonical player colours to `packages/design-system/tokens/color.json`, **each with a paired contrast token**, from the measured values in [research.md](./research.md) **D3**; and add the icon-size tokens that close gap **DS-7** in `packages/design-system/specs/README.md`, whose current state is components sizing marks from `1em` for want of a token. **Decision needed before this runs, from `product-designer`, not invented here**: D3 carries the eight _base_ hex only — the `-contrast` value paired with each, and the DS-7 icon-size scale, are decided by no artifact yet, and `specs/README.md`'s gap register forbids an implementer choosing a token value (design-system skill point 1). This task _applies_ product-designer-decided values into the token JSON (which is implementer territory — product-designer's write scope is `specs/` only); it does not choose them. Extend `packages/design-system/tokens/build-tokens.test.mjs` with a case asserting every player colour has its contrast pair, because a colour shipped without one is a component that will hard-code a foreground the first time yellow appears on parchment. Constitution VI; serves FR-003
- [x] T411 Correct the artifacts that are stale against constitution X 5.0.0, listed in [research.md](./research.md) **D8**. **Two are loaded into an agent's context and so are corrected first**, because a dispatched UI agent (T428–T431, T435–T437, T440–T441 all load one) otherwise reads a standing ban on the exact thing it is being told to build: `.claude/skills/design-system/SKILL.md`'s "No game asset in the repository" (scope it to "no unrecorded pack", the same move made on the `UploadControl` comment below), and `.claude/agents/product-designer.md`'s "without ever reusing a single game asset" (game assets under GCUR are now this agent's to spec). Then the rest: `README.md`'s "uses no assets from the game" sentence; `packages/design-system/specs/README.md`'s "No game asset, ever… this is a legal boundary" (the boundary is the licence record, not the asset) — **already corrected under the token work in `game-asset-tokens.md`'s commit; T411 verifies rather than re-edits this one line**; `docs/risks.md` R7, rewritten to carry the packs, their basis and the residual extraction risk **D3** accepts rather than its current, now-false, "no game asset in the repository"; the `no emblem (§2 IP note)` comment on `packages/design-system/src/components/MatchRow/index.tsx`; and the comment on `packages/design-system/src/components/UploadControl/UploadControl.test.tsx` that states the rule as a codebase-wide one — **the assertion itself stays exactly as it is**, scoped to that component's container, because "this control shows no imagery" is still true and still worth holding. Also touch, and only where this feature's components reach them, `packages/design-system/specs/sign-in-screen.md`, `profile-summary.md`, `player-search.md`, `favourites-list.md`, `favourite-toggle.md` and `manual-upload.md`'s "§4's ban" aside; and the `(no game assets)` gloss in `tests/architecture/test_import_graph.py`'s module docstring, a comment with no assertion behind it. **`README.md`'s disclaimer paragraph is not edited and not reflowed**: `packages/design-system/src/components/Footer/Footer.test.tsx` reads that file at runtime and asserts the footer against it, so a reworded disclaimer breaks the footer test and removes a constitution X anchor in the same stroke. Lands in the same commit as T404–T407 — the packs cannot land while the repository says they may not exist. FR-012

**Checkpoint**: the gate is executable, the packs are in and recorded, the colours are tokens, and
nothing in the repository still claims game assets are forbidden. US3 can start from here.

---

## Phase 2: Foundational — making the data exist (plan phases B, C, D)

**Purpose**: the three layers research.md found under the presentation feature. Phase B projects
`matches.raw_payload` into the columns nobody ever wrote; C sources the one fact Relic does not serve;
D widens the API and adds the one new column.

**⚠️ CRITICAL for US1 and US2, not for US3.** US1 cannot begin until this phase is complete — every
fact it renders is null until then. US2 needs only T421 and T426 of it, for the avatar. US3 needs
nothing from this phase at all and can run against Phase 1 alone.

### B — the projection and the backfill

- [x] T412 [P] Write the projection unit tests in `packages/storage/tests/test_match_projection.py`, `xfail(strict=True, reason="T413 not implemented yet")`, encoding quickstart scenario 2 against `packages/providers/fixtures/relic/get_recent_match_history.json`: `civilization_id` → `civ_id` and `teamid` → `team_id` direct; `rating` is `newrating`, the value **after** the match, which is what FR-005 shows; `rating_diff` is `newrating - oldrating` and is **`NULL` when either side is missing, never `0`** — a zero is a real rating movement and a stand-in that means "unknown" is a lie the interface cannot see through; `outcome` `1` → `win`, `0` → `loss`, **and a third value → `NULL`**, which is FR-004's neutral state and the case that will otherwise be coerced into a loss; and a projection that disagrees with the same participant's entry in `matchhistoryreportresults[]` **raises rather than picking a side**, because that array is a cross-check and a silent tie-break is how a wrong civ ships looking confident
- [x] T413 Implement the projection function in `packages/storage/src/aoe2stats_storage/repositories/matches.py` and widen `upsert_match_player` in `apps/ingester/src/aoe2stats_ingester/discover.py` from `ON CONFLICT DO NOTHING` to `ON CONFLICT DO UPDATE`, setting the five Relic-derived columns from the response the same transaction already holds, and remove T412's markers. **`color_id` is not in that `SET` clause** — the enrichment in T420 is its only writer, and a Relic-only refresh that included it would null out a colour cached earlier, which is a data loss no test downstream would attribute to this statement. Its docstring currently says the stage "does not yet know a player's civ, team, colour or result"; rewrite it to say what it now knows and what it deliberately still does not. Both call sites — `DiscoverStage.__call__` and `_refresh_third_party_history` in `apps/api/src/aoe2stats_api/routers/players.py` — gain the widened behaviour with no signature change at either. No new request, no change to the capture enqueue, `expired_total` cannot move (constitution I)
- [x] T414 [P] Write the backfill tests in `scripts/ops/tests/test_backfill_match_players.py` (the script lives in `scripts/ops/`, so its tests do too — `acknowledge_alerts.py`'s precedent, and `scripts/ops/tests` is its own `testpaths` entry), `xfail(strict=True, reason="T415 not implemented yet")`, encoding quickstart scenario 2's second half: `--dry-run` reports a count and **writes nothing**, asserted by comparing the table before and after rather than by trusting the printed count; a real run fills the columns from `matches.raw_payload` using T413's projection function and not a second copy of it; **a second run reports zero rows changed**; rows already populated are left alone unless `--force`; and — the assertion this task exists for — **the run issues no outbound request at all**, asserted against the provider call sink. The bytes are already on disk under constitution IV; a backfill that re-fetches is a capture-path load for data this service already holds, which is the whole point of keeping the raw
- [x] T415 Implement `scripts/ops/backfill_match_players.py` and remove T414's markers. It reads `matches.raw_payload` for rows whose `match_players` columns are still null, applies T413's function, and writes. Re-runnable by construction rather than by a guard flag: the same input yields the same output. Without it US1 is correct only for matches discovered after this ships and silently wrong for everything before, which is the failure mode the product already has and the one the acceptance test ("load a profile with known matches") lands on first. **`.env.local` points at production Neon** — the script must take its target from `DATABASE_URL` and must not read a dotenv file of its own

### C — the one fact Relic does not serve

- [x] T416 [P] **The fixture already exists** at `packages/providers/fixtures/companion/matches.json` — 3 matches, `teams[].players[]` carrying `color`, `colorHex`, `won`, `rating` and `ratingDiff`, and **every participant of all three at `replay: false`** — and `test_companion.py` already pins its three `matchId` values as the fixed game-id set eight of its tests read. **Do not re-capture it**: a fresh capture changes those ids and breaks all eight tests at once. This task is verification only — confirm the three properties T417 relies on still hold: `colorHex` present (so T417 can assert it never reaches the client), a `replay: false` match present (the [research.md](./research.md) **D2** evidence that companion has colour for matches no replay was captured for), and `avatarhash` reachable for the `PlayerSearchResult` half (already present in `companion_profiles_search.json`, `docs/data-sources.md:296`). Extend the fixture only if a property is missing, and then without renumbering the existing matchIds
- [x] T417 Write the companion parse tests in `packages/providers/tests/test_companion.py`, `xfail(strict=True, reason="T418 not implemented yet")`, encoding quickstart scenario 3: `enrich_matches` returns `MatchEnrichment.participants` keyed by profile id, parsed from `teams[].players[]`, carrying `color_id`, `team_id`, `won`, `rating` and `rating_diff` — **two distinct optional fields from the wire's `rating` and `ratingDiff` respectively** (data-model.md §2), not one; only `color_id` is ever written, the rest exist so a disagreement with Relic is visible; **`colorHex` is absent from the returned objects and from the model definition itself**, asserted by field introspection so a later refactor that adds it fails here — a provider that can set a product colour bypasses both constitution VI and the contrast pairing T410 exists to guarantee; a match companion does not know yields no participants entry rather than an entry of nulls; a 403, a 5xx and a malformed body each degrade and **never raise**, because companion's failure is not an error by the constitution's own Technology Constraints; and `PlayerSearchResult.avatar_hash` is parsed from the record's `avatarhash`, which `_parse_search_result` reads past today. Depends on T416
- [x] T418 Implement the widening in `packages/providers/src/aoe2stats_providers/base.py` — a new `EnrichedParticipant` on `StrictProviderModel`, `MatchEnrichment.participants`, and `PlayerSearchResult.avatar_hash` — and the parsing in `packages/providers/src/aoe2stats_providers/companion/provider.py`, and remove T417's markers. This is a **parse widening of a response the provider already fetches**: no new endpoint, no new provider, and timeout, retry, token bucket, circuit breaker and the provider-call sink are all inherited unchanged from the base (constitution III). Every new field is optional — a missing key in a companion response is normal, not a fault. The three fields beyond `color_id` are carried so a disagreement with Relic is _visible_; Relic stays authoritative for everything it serves and **only `color_id` is ever written**
- [x] T419 [P] Write the colour-enrichment tests in `apps/api/tests/test_match_colour_enrichment.py`, `xfail(strict=True, reason="T420 not implemented yet")`: viewing a page of matches makes **at most one** companion call, batched over the page's game ids, not one per match; a returned colour is written to `match_players.color_id` keyed `(game_id, profile_id)`; **a degraded companion writes nothing and specifically does not write `NULL`**, asserted by seeding a cached colour, degrading the provider and reading the row back — this is the assertion the whole caching design turns on and it has no happy path to demonstrate, so it is the one an implementer is most likely to weaken; a second view of the same matches makes **no** companion call at all; and the profile route `GET /api/players/{profile_id}` still makes **no provider call whatsoever**, which is a property T426 must not quietly cost us
- [x] T420 Implement the read-time colour enrichment on the match read paths in `apps/api/src/aoe2stats_api/routers/matches.py`, calling the existing `enrich_matches` batched over the page and caching the result into `match_players.color_id`, and remove T419's markers. **On the display path, never the ingester and never the capture path** — that is what keeps FR-014 true as written, and wiring this into `apps/ingester` instead would make colour part of what is captured for no benefit, since colour never changes once a match is over. When companion is degraded the colour is absent and the view degrades under FR-010; that is a legitimate resting state, not a migration in progress (data-model.md §6). FR-003

### D — the migration, the API delta, and the new personal data

- [x] T421 Add the nullable `avatar_hash` column to `AoeProfile` in `packages/storage/src/aoe2stats_storage/models.py`, write the single additive migration under `infra/migrations/versions/`, and bump `EXPECTED_SCHEMA_REVISION` in `packages/storage/src/aoe2stats_storage/revision.py` **in the same commit** — `apps/api/tests/test_schema_revision.py` asserts it against `alembic heads` on every run, so the three are never separately green. Confirm `uv run alembic check` reports no drift and that the migration is clean in both directions (quickstart scenario 4). Nullable is the ordinary case and not the error case: a profile never seen in a companion response has no hash, and FR-008a's neutral placeholder is the correct render for it
- [x] T422 [P] Write the repository tests in `packages/storage/tests/test_match_repository.py`, `xfail(strict=True, reason="T423 not implemented yet")`: `MatchListRow` carries `rating`, `team_id` and `color_id`; a sibling projection returns **all** participants for a match, the viewer included; and **`opponents` keeps its shape and its exclusion contract**. Its shape is unchanged — the field is named `opponents`, `participants` is a sibling and not a replacement, and nothing that reads the old field changes structurally. Its _content_ is another matter: `_opponents_by_game` excludes teammates by a `team_id` filter that excludes nothing while `team_id` is `NULL`, and every `team_id` is `NULL` until T413/T415 run — so assert that **once `team_id` is populated, a team match's `opponents` excludes teammates**. That property has never been observable before this feature (contracts/http-api.md, `GET /api/matches`), so it gets no coverage anywhere else
- [x] T423 Implement the widening in `packages/storage/src/aoe2stats_storage/repositories/matches.py`: `list_matches` selects `rating`, `team_id` and `color_id`, and a `participants` projection joins `aoe_profiles` for each participant's `alias` and `country` alongside `team_id`, `civ_id`, `color_id`, `result`, `rating` and `rating_diff`. Remove T422's markers. FR-005 needs the absolute rating to render `922 (+16)` and the list row has never carried one — only match detail did (research.md **D7**)
- [x] T424 [P] Write the API contract tests in `apps/api/tests/test_match_row_shape.py` and extend `apps/api/tests/test_players_routes.py`, `xfail(strict=True, reason="T425 not implemented yet")` on the match half and `reason="T426 not implemented yet"` on the profile half — markers split by implementing task, never one reason for the file — encoding quickstart scenario 4 against [contracts/http-api.md](./contracts/http-api.md): match rows carry `rating`, `team_id`, `color_id` and `participants[]`, each participant carrying `civ_name` whenever `civ_id` is present so the client never formats an id itself (FR-001), and `country` for the opponent flag; `result` is `"win"`, `"loss"` or `null` and **`null` is asserted not to be a loss** (FR-004); the profile routes carry `avatar_hash`, **a hash and never a URL** (FR-008a, FR-015); and the assertion that makes this widening safe at all — **`apps/api/tests/test_players_history.py`'s row-shape identity between `GET /api/matches` and `GET /api/players/{profile_id}/matches` still passes**, because `match_row_json` is imported across the two routers precisely so they cannot drift. Add the negative that binds every route: **no response carries a colour hex, an icon URL or a flag URL**, parameterised over the route table rather than spot-checked — colours are tokens and asset URLs are resolved client-side from the pack, and a URL on the wire would bypass the pack's coverage check as well as constitution VI
- [x] T425 Widen `match_row_json` and the match-detail serialiser in `apps/api/src/aoe2stats_api/routers/matches.py` with `rating`, `team_id`, `color_id` and `participants[]`, giving detail's participants the same `country` the list rows get so `apps/web`'s `toParticipantData` serves both shapes, and remove T424's T425-reasoned markers. Every change is additive — no field removed, renamed or re-typed — which is what lets a client that has not been updated keep working. `GET /api/matches/{game_id}` is otherwise unchanged: it already serves these fields per participant, and the reason detail looked complete while the list did not is that both read columns nobody had written
- [x] T426 Populate and expose `avatar_hash`, and remove T424's T426-reasoned markers. Three edits: write it opportunistically from any companion response that carries it, in `apps/api/src/aoe2stats_api/search.py` and the third-party history refresh in `apps/api/src/aoe2stats_api/routers/players.py`; serve it on `GET /api/players/{profile_id}` and on `GET /api/profiles` identically; and add it to **both** GDPR paths in `apps/api/src/aoe2stats_api/routers/privacy.py` — the export bundle, and the erasure pseudonymisation that already handles `alias` and `country`, which it sits beside and shares a lawful basis with. **Erasure decision, recorded so it is not re-litigated**: `avatar_hash` needs no pseudonym — it is set to `None` on both the placeholder and the original row, directly in `_pseudonymise_profile_id` (privacy.py) alongside where the plan's `alias`/`country` are written. `packages/core`'s `PseudonymisationPlan` is **not** changed: it computes a masked `alias`/`country` pair precisely because those must survive as plausible values, and a nulled field needs no such computation. Constitution IX makes the export and erasure halves part of this task and not a follow-up. `GET /api/players/{profile_id}` **still makes no provider call** — storing the hash is what buys that, and T419 asserts it
- [x] T427 Record `avatar_hash` in `docs/privacy/processing-register.md`, in this pull request, on the three activities that now process it — displaying a user's own stats, third-party players appearing in a user's matches, and player-name search. New personal data, public from a public source, under the same legitimate-interest basis as the `alias` and `country` it sits beside, **carried and never used to link or merge profiles** — constitution IX's unverified-third-party-claim rule, the same standing the `unverified_steam_id` beside it already has. No new capture, no new indexing, no change to the objection route, and the Steam content delivery network receives no data from this service because the browser is what loads the image. Constitution IX requires the row in the same change; FR-015

**Checkpoint**: every fact US1 renders exists in the database or arrives at read time, the API serves
it, and the new personal data is recorded. Stories can start.

---

## Phase 3: User Story 1 — A match is legible at a glance (Priority: P1) 🎯 MVP

**Goal**: each match shows civilisation icon and name, minimap and map name, every player's canonical
colour, who won, and how the rating moved — with no numeric identifier reaching the user.

**Independent Test**: load a profile with known matches and confirm each row presents civilisation
(icon + name), map, player colours, outcome and rating change, with no `civ_id`, `color_id` or map id
visible anywhere.

- [x] T428 [P] [US1] Write the component specs in `packages/design-system/specs/`: widen `match-history.md` for the participant grouping, the outcome signal and the rating movement, and add specs for the civilisation mark, the map thumbnail and the player-colour swatch. State three things the components will otherwise each decide differently: that **colour is never the only carrier of meaning**, so a swatch always sits beside a name and the winning side is distinguished by a text or shape signal as well (FR-004, design-system rule 4); that the direction of a rating change is legible without colour, which is FR-005's explicit clause; and that the **absent-asset state is the prop being `undefined`**, rendering the readable label alone — not a placeholder image, which is a broken image with better manners (FR-010)
- [x] T429 [P] [US1] Build `CivilisationIcon`, `MapThumbnail` and `PlayerColourSwatch` in `packages/design-system/src/components/`, each with its `*.stories.tsx` and `*.test.tsx`, from tokens only and taking an image URL as a **prop** — the design system never imports an image and never reaches into `packages/game-assets`, which is what keeps it asset-agnostic and its unit tests free of binary fixtures. Stories in both themes, and the degrade stories are not optional extras: an unknown civ id, an unknown map name and a `color_id` outside 1..8 or null are each a story, because FR-010's no-broken-image rule needs a visual baseline and an unrendered state has none. `PlayerColourSwatch` reads T410's tokens and contains no hex string. FR-001, FR-002, FR-003, FR-010
- [x] T430 [US1] Widen `packages/design-system/src/components/MatchRow/` to present civilisation as icon and name, the map as thumbnail and name, every participant in their colour, the winner distinguished from the loser with a **third neutral state for a null result**, and the rating with its signed change. FR-006's metadata — ladder, duration and date — is already stored and goes here where it aids legibility, not into a second row. Stories for a 1v1, an eight-player match, a null result, and a match with none of its assets covered. FR-001 to FR-006
- [x] T431 [US1] Widen `packages/design-system/src/components/MatchDetailPanel/` to group participants by team with civilisation, colour and rating per player, reusing T429's three components rather than re-implementing any of them — two presentations of the same fact are how the list and the detail view start disagreeing about a match. Stories mirroring T430's four cases
- [x] T432 [US1] Wire the widened shapes through `apps/web/src/features/matches/`: `api.ts`'s hand-written validators for `rating`, `team_id`, `color_id` and `participants[]` — **the list's `participants[]` carry no `replay`** (detail-only, FR-023), so do **not** reuse detail's `assertMatchParticipant`, which calls `assertReplayAvailability` unconditionally and would reject every list row; give the list its own validator or make `replay` optional (contracts/http-api.md `participants[]`); `mappers.ts`'s `toParticipantData` serving list and detail alike (it reads no `replay` field, which is why it can); `format.ts` for the `922 (+16)` and `921 (−15)` rendering with the sign carried in the text; and the asset lookups resolved through `packages/game-assets`, whose `undefined` is passed straight to the component as the absent case. Extend the existing `api.test.ts`, `mappers.test.ts` and `format.test.ts` in the same task — they are the file's own tests and splitting them off would leave a task that cannot prove itself. FR-005
- [x] T433 [US1] Run `visual-reviewer` locally over the stories T429 to T431 added, then `pnpm test:visual --changed`, updating baselines in `packages/design-system/__screenshots__/` only where the change is intended. **Confirm the run actually saw images**: `staticDirs` mounting `packages/game-assets` is what T401 landed for, and a story rendering a missing image passes its snapshot exactly as happily as one rendering the right image. If the runner reports no changed stories, the run proved nothing. Constitution VII, FR-013, SC-006
- [ ] T434 [US1] Walk quickstart scenario 5 by hand against a real profile and record the outcome in the pull request: every civilisation, map and outcome legible with no numeric identifier read (SC-001), and **zero broken or missing images** across the three degrade cases, confirmed in the browser's network panel with no 404 under `/game-assets/` (SC-005). A 404 there means the resolver returned a URL where the contract requires `undefined`, which is a contract defect and not a missing file

**Checkpoint**: a match is readable at a glance. This is the MVP and shipping only it closes most of
the visible gap with peers.

---

## Phase 4: User Story 2 — A profile says who the player is (Priority: P2)

**Goal**: the profile shows a name, a country and an avatar instead of the number `1807091`.

**Independent Test**: load a profile whose alias and country are stored and confirm the name and flag
are shown, the numeric id is demoted, and a profile with no ranked rating still shows the calm
"No ratings yet" explanation.

**Depends on** T421 and T426 for the avatar, and on Phase 1 for the flag pack. Independent of US1.

- [ ] T435 [P] [US2] Write the component specs in `packages/design-system/specs/`: widen `profile-summary.md` for the alias-as-heading, demoted-id, flag and avatar arrangement, and add specs for the country flag and the player avatar. State the fallback ladder explicitly, because it is three separate rules that look like one: no alias → **the numeric id becomes the heading, never a blank one**; no country → the flag is **omitted cleanly**, not replaced by a gap that reads as an error; no avatar hash **or a hash that fails to load** → the same neutral placeholder, so a stale hash and a missing hash are indistinguishable to a viewer. FR-007, FR-008, FR-008a
- [ ] T436 [P] [US2] Build `CountryFlag` and `PlayerAvatar` in `packages/design-system/src/components/` with stories and tests in both themes. `PlayerAvatar` builds `https://avatars.steamstatic.com/<hash>_full.jpg` **in the component** from the hash prop, with an `onError` fallback to the neutral placeholder — the URL is built here and nowhere else, and nothing in `packages/providers` or the API constructs it (FR-008a, FR-015). Stories for a present hash, an absent hash and a hash that fails to load; **the last two must render identically**, which is the assertion FR-008a's "never a broken image" actually reduces to. The image is a client-side `<img src>` and not an outbound call from `apps/*` or `packages/core`, so constitution III is untouched. `CountryFlag` resolves through `packages/game-assets` and renders nothing at all when the code misses
- [ ] T437 [US2] Widen `packages/design-system/src/components/ProfileSummary/` — alias as the heading, the numeric id as a secondary reference, the flag beside the name, the avatar leading — with stories for a full profile, an alias-less one and a country-less one. **The "No ratings yet" state is unchanged**: it is a real and correct outcome that profile `1807091` genuinely has, and every temptation in this task is to make it look like something went wrong. FR-007
- [ ] T438 [US2] Wire it through `apps/web/src/features/players/`: `api.ts`'s validator for `avatar_hash` as a nullable string, `mappers.ts` and `format.ts` for the fallback ladder, and the flag resolution through `packages/game-assets`. Extend the feature's existing tests in the same task. SC-002 is what this closes: the name and country instead of a number, for every profile that has an alias stored
- [ ] T439 [US2] Run `visual-reviewer` locally over T436's and T437's stories, then `pnpm test:visual --changed`, updating baselines in `packages/design-system/__screenshots__/` where intended. Encodes the profile half of quickstart scenario 6. FR-013, SC-006

**Checkpoint**: a profile shows a person rather than an identifier.

---

## Phase 5: User Story 3 — The site has a way around it (Priority: P3)

**Goal**: a header with primary navigation on every page, with the footer and its disclaimer intact.

**Independent Test**: from any route, confirm the header with working navigation is present and the
footer disclaimer is still rendered.

**Depends on Phase 1 only.** No data dependency and no asset dependency, so this phase is genuinely
parallel with the whole of Phases 2 to 4.

- [ ] T440 [P] [US3] Write the component spec `packages/design-system/specs/site-header.md`: the primary navigation, the current-route indication, the focus and hover treatments, and the small-viewport arrangement. Name the focus states explicitly — they are the part a later reviewer will assume was covered
- [ ] T441 [US3] Build `SiteHeader` in `packages/design-system/src/components/` from tokens, with `SiteHeader.stories.tsx` and `SiteHeader.test.tsx`, in both themes. **The navigation's focus and hover states need an interaction test, not only a snapshot**: static story screenshots are blind to focus and hover, so a keyboard user's experience of this component has no visual baseline and cannot get one. This is known from prior work on this repository, not a hypothetical. FR-009
- [ ] T442 [US3] Mount the header in `apps/web/src/routes/__root.tsx` so it renders on **every** route, and leave the footer exactly as it is. FR-009's second half and FR-012 are the same sentence here: the footer carries the Game Content Usage Rules disclaimer, which is one of the two anchors constitution X's permission for every pack in Phase 1 rests on. A layout change that drops the footer on one route removes that anchor on that route
- [ ] T443 [US3] Run `visual-reviewer` locally over T441's stories, then `pnpm test:visual --changed`, updating baselines where intended. Encodes the site half of quickstart scenario 6. FR-013, SC-006

**Checkpoint**: the application reads as a site. All three stories are complete.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T444 [P] Record in `docs/data-sources.md` the **one genuinely new** companion field this feature started reading — the per-participant colour on the match endpoint (`teams[].players[].color`) — as an observation on a date, with the `replay: false` evidence. `avatarhash` on the search endpoint is **already recorded** in §3's "Profile search behaviour" Record row (measured 2026-08-23, `docs/data-sources.md:296`); do **not** restate it — the "never copy a measurement" rule binds inside `docs/` too — note only that this feature started _reading_ a field already documented. `docs/` is where a measured property of the outside world lives and where the nightly contract check will notice it moving; T416's fixture is frozen and cannot notice anything. Do not restate the values in this feature's artifacts — they reference `docs/`, they do not copy it
- [ ] T445 [P] Walk SC-004 and record the comparison in the pull request: for the same profile, this application and a comparable third-party site present the same categories — civilisation, map, player colour, outcome, rating movement — with the sole documented exception of per-unit, per-building and per-resource detail, which requires replay parsing and is a V2 capability with no phase-1 data to key to. Record it as a list of categories matched and the one category deliberately absent, so the exception stays documented rather than becoming an unexplained gap
- [ ] T446 Run quickstart scenario 7's full gate — `uv run ruff format . && uv run ruff check --fix . && uv run mypy && uv run pytest`, then `pnpm -r test`, `pnpm --filter design-system build-storybook`, `pnpm test:visual --changed`, `pnpm --filter web build`, `node scripts/checks/built-css.mjs`, `node scripts/checks/spa-routing.mjs` and `uv run scripts/checks/asset_packs.py` — plus `uv run scripts/checks/spec_lint.py --feature specs/004-visual-parity` clean. **Run the whole suite, not the failures anyone happened to mention**: `CLAUDE.md` records a commit that went in with 96 tests red because only the reported ones were re-run
- [ ] T447 Walk quickstart scenario 6 by hand in the running application — `pnpm --filter web dev`, then `/players/1807091` and `/players/1807091/matches` — and record the outcome in the pull request. This profile is the one the spec was written about: it currently shows `1807091` as both name and subtitle, "No ratings yet", no navigation and no imagery. The walk is done when a reader of that page cannot tell it apart from a peer site on the categories SC-004 lists
- [x] T448 Add the re-runnable map-thumbnail sync tool the maps pool needs — `scripts/ops/sync_map_thumbnails.py` (+ `scripts/ops/tests/test_sync_map_thumbnails.py`) and `docs/runbooks/map-thumbnail-sync.md`. The style question that produced the PR-review rejection resolved to a source question: the maps pack (T405, the aoe2cm2 mirror) is already the generic-starting-position lobby-preview style the review asked for; its only defect is 140 px native resolution. **aoe2insights, the higher-resolution mirror of the same game asset, is rejected as a source: it sits behind an interactive Cloudflare bot-challenge that must not be bypassed or automated** — so an automated fetch is impossible and aoe2cm2 (140 px, accepted) stays the maintained mirror. The sync tool is therefore the reproducible way to refresh the pack when a map joins the pool. **Network-free by construction** (constitution: only `scripts/checks/contract_sources.py` touches the network, and this feature vendors assets by hand — T404-T406): the script takes a local `--source-dir` of `<slug>.png` files the human downloaded, re-encodes to WebP matching the existing pack's encoding so a run against today's aoe2cm2 reproduces the committed 435 files, `--dry-run` reports added/changed/removed and writes nothing, a real run is idempotent, and `--prune` (opt-in) removes a map dropped from the pool. The runbook carries the human download step (a `curl` loop over aoe2cm2 raw, run outside the repo) that keeps the committed code network-free. The resolver (T409) auto-generates its coverage set from the directory listing, so no manifest is maintained. FR-002, FR-016; the aoe2insights/Cloudflare and 140 px decisions are recorded in [research.md](./research.md) **D9**

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup, plan phase A)** — no dependencies. Blocks Phase 3, Phase 4 and Phase 5.
- **Phase 2 (Foundational, plan phases B, C, D)** — independent of Phase 1 and genuinely parallel with
  it. Blocks Phase 3 entirely; blocks only T436 and T438 of Phase 4, via T421 and T426.
- **Phase 3 (US1, P1)** — depends on Phases 1 and 2. The MVP.
- **Phase 4 (US2, P2)** — depends on Phase 1, and on T421 and T426 for the avatar. Independent of US1.
- **Phase 5 (US3, P3)** — depends on Phase 1 alone. Parallel with everything else in the feature.
- **Phase 6 (Polish)** — T445 and T447 depend on all three stories; T444 depends on Phase 2's C half;
  T446 depends on everything.

### Within Phase 2

B, C and D are sequential in the sense that matters and not in the sense they appear: T413's
projection and T420's enrichment write different columns and never contend, but T423's repository
widening has nothing to return until both have run at least once, and T424's tests assert on values
that only exist afterwards. T421 is independent of all of them and can land first.

### Within a story

Tests before implementation, always, and the `xfail` marker comes off in the implementing task.
Component specs before components, components before web wiring, visual review last, the hand walk
after that.

### Parallel opportunities

Honest `[P]` markers. Two tasks writing the same file are never both `[P]`, which is why the API tests
are split by shape rather than by story.

- **Phase 1**: T404, T405 and T406 are a genuine three-way batch — three pack directories, no shared
  file. T402, T408 and T410 are `[P]` with each other and with that batch. T407 is **not** `[P]` with
  T404–T406 and lands in the same commit as all four.
- **Phase 2**: T412, T414, T416 and T422 are a four-way batch across four test files. T419 is `[P]`
  with T422. T421 is `[P]` with the whole of B and C.
- **Phase 3**: T428 and T429 are `[P]`; T430 and T431 are not, because T431 reuses what T430 settles.
- **Across phases**: **Phase 5 is `[P]` with the whole of Phases 2, 3 and 4** — it shares no file with
  any of them and needs no data. It is the cheapest visible improvement in the feature and there is no
  reason to hold it behind the other two.

---

## Implementation Strategy

### MVP

Phase 1, Phase 2, Phase 3. At that point a match is legible at a glance, which is the flagship parity
gap and the reason the constitution was amended. Stop and walk T434 before building further: if the
degrade cases show a broken image, every later phase rests on a resolver contract that is not being
honoured.

### Incremental delivery

1. Phase 1 → the gate, the packs, the tokens, the corrections. Commit (T404–T407 and T411 as one).
2. Phase 2 → the data exists. Commit per task, and run the backfill before believing any of it.
3. Phase 3 (US1) → the MVP. Commit and demo.
4. Phase 4 (US2) → the profile is a person. Commit and demo.
5. Phase 5 (US3) → the site has a header. Commit. Can be slotted anywhere after step 1.
6. Phase 6 → the records, the two walks, the full gate.

Stopping after step 3 is a legitimate release.

---

## Notes

- Commit at the granularity `CLAUDE.md` sets: the smallest set of tasks that was ever simultaneously
  green, with the `[x]` in this file riding in the same commit as the work that earned it. Commit when
  a task hands back, **before** dispatching the next one — a batch launched over an uncommitted
  predecessor absorbs it permanently.
- Every task above is one `implementer` invocation, **except the three component-spec tasks — T428,
  T435 and T440 — which are `product-designer` invocations**: that agent is the only writer of
  `packages/design-system/specs/`, and the design-system skill's checklist point 1 ("No spec, no
  component: ask the product-designer") forbids an implementer authoring one. T410 stays an
  `implementer` task but depends on `product-designer` first deciding the values it applies (see its
  own note): product-designer's write scope is `specs/` only, so it cannot touch the token JSON, but
  the `-contrast` pairs and DS-7 scale are its decision, not the implementer's.
- Every `[P]` dispatch tells the agent: **do not modify a file outside your task's named paths.** If
  the shared gate fails because of a sibling's file, report it and hand back.
- The `xfail(strict=True)` markers are not a formality and `pytest.importorskip` is not a substitute.
  A skipped test reports green while proving nothing.
- **Three tasks assert an absence** — T417's "`colorHex` never reaches the client", T419's "a degraded
  companion writes nothing rather than `NULL`", and T414's "the backfill issues no outbound request".
  An absence has no happy path to demonstrate, so each is the assertion an implementer under gate
  pressure is most likely to weaken into something that passes. Each names why it exists; dispatch
  against that.
- **`.env.local` points at production Neon.** Never run T415's backfill or any Alembic command from
  T421 against it while validating. Export a local `DATABASE_URL` explicitly.
- This feature adds **no configuration key and no secret**. If that changes, `.env.example` moves in
  the same commit — `apps/api/tests/conftest.py` asserts the key set at import time and fails the
  whole API suite otherwise.
