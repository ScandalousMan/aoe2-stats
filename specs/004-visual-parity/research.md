# Research: Visual Parity — Game Assets and Rich Profile/Match Presentation

**Feature**: `004-visual-parity` | **Date**: 2026-08-30 | **Spec**: [spec.md](./spec.md)

Phase 0 output. Every NEEDS CLARIFICATION from the Technical Context is resolved here, plus three
findings that were not questions when the spec was written because nobody had looked.

---

## Summary of what changed about this feature

The spec calls 004 "the presentation and the assets; it changes nothing about what is ingested".
That is half true. **The presentation layer has almost nothing to present**: five of the six
per-participant facts US1 needs are declared as columns, read by three routers, and written by
nobody. The sixth (`color_id`) is not in the primary provider at all — it comes from the enrichment
provider, read-time and replay-free. Feature 004 is therefore a data-availability feature with a
presentation layer on top, and the plan is sequenced accordingly.

| #      | Finding                                                                                  | Consequence                                                                           |
| ------ | ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| **D1** | `match_players.civ_id/team_id/color_id/result/rating/rating_diff` are **never written**  | US1 needs a projection stage + backfill before any pixel changes                      |
| **D2** | Relic serves no player colour anywhere; aoe2companion's match API serves it, replay-free | `color_id` is read-time enrichment from companion, no replay and no FR-014 change     |
| **D3** | No openly-licensed AoE2 asset pack exists anywhere                                       | The FR-011 gate must accept a GCUR-only pack, or constitution X 5.0.0 permits nothing |

---

## D1 — The data US1 presents is not stored

**Decision**: Add a projection of `matches.raw_payload` into `match_players`' existing columns, as a
widened `upsert_match_player` plus a one-off backfill over rows already ingested.

**Evidence.** `apps/ingester/src/aoe2stats_ingester/discover.py:171-182` is the only writer of
`match_players`, and it writes the primary key and nothing else. Its own docstring says so:

> `ON CONFLICT DO NOTHING` on the `(game_id, profile_id)` primary key: this stage does not yet know
> a player's civ, team, colour or result […] so there is nothing to refresh on a repeat sighting,
> only a row whose _existence_ must be guaranteed.

A repo-wide grep for `civ_id=` / `color_id=` / `rating_diff=` / `team_id=` outside tests returns
only readers: `packages/storage/.../repositories/matches.py:244-428`,
`apps/api/.../routers/matches.py:421-487`, `apps/api/.../routers/privacy.py:368-373`. So
`GET /api/matches` has been serving `civilisation: null`, `result: null`, `rating_diff: null` for
every production row since 001 shipped, and the front end has been faithfully rendering them.

**The data is already in the repository.** `matches.raw_payload` holds the whole Relic response, and
`matchHistoryStats[].matchhistorymember[]` carries, per participant (measured against
`packages/providers/fixtures/relic/get_recent_match_history.json`):

| Relic field              | Column                  | Note                                                                     |
| ------------------------ | ----------------------- | ------------------------------------------------------------------------ |
| `civilization_id`        | `civ_id`                | direct                                                                   |
| `teamid`                 | `team_id`               | direct                                                                   |
| `oldrating`, `newrating` | `rating`, `rating_diff` | `rating` = `newrating`; `rating_diff` = `newrating - oldrating`          |
| `outcome`                | `result`                | `1` = win, `0` = loss; anything else → the neutral state FR-004 requires |
| —                        | `color_id`              | **absent — see D2**                                                      |

`matchhistoryreportresults[]` carries the same `civilization_id`/`teamid` plus `resulttype`, and is
the cross-check: a projection that disagrees with it is a bug, not a tie to break.

**Rationale.** This is a projection, not an ingestion change. The same bytes are already fetched,
already persisted verbatim (constitution IV), and already stored; nothing new is requested from any
source, no capture path is touched, and `expired_total` cannot move. It is exactly the case
constitution IV's "every derived artifact must be fully recomputable from the raw" was written to
make cheap — the backfill is a `SELECT raw_payload` loop, no re-fetch, and it is re-runnable.

**Alternatives considered.**

- _Read `raw_payload` at request time in the router._ Rejected: `packages/storage`'s repositories are
  the only place that knows the row shape, and pushing JSON traversal into a display path makes every
  list query parse a ~400 KB blob per match.
- _Leave the columns NULL and present only what is stored._ Rejected: that is the current product,
  which is the thing the spec exists to fix.
- _A new table for parsed participants._ Rejected: the columns exist, are correctly typed and
  nullable, and are already read by three routers and the GDPR export. Adding a second home for the
  same facts is how the export starts lying.

**Consequence for FR-014.** FR-014 says the feature "MUST NOT change what data is ingested". A
projection does not; this decision is inside FR-014 as written, and so is D2 — see below.

---

## D2 — Player colour: Relic has none, aoe2companion serves it without a replay

> **Superseded 2026-09-04 (003's T411).** The "Relic has no colour" finding below was wrong: the
> `slotinfo[].metaData` record this section decoded carries `ScenarioPlayerIndex`, and that index
> *is* the colour (`+1` = the 1..8 scheme) — the second bullet below read it as a seat number.
> `docs/data-sources.md` §1 "Player colour" holds the corrected measurement and its verification.
> Colour is now projected by `project_match_player` from `matches.raw_payload` and written by the
> ingester; the companion enrichment this decision built stays only as a fallback for a row the
> projection leaves `NULL`. Everything else in this section is kept as the record of what was
> decided and why.

**Decision**: `color_id` is the one display fact the primary provider does not carry. It is sourced
from **aoe2companion's match endpoint as read-time enrichment** — companion's designated
"enrichment, degradable" role — merged into the API response and cached opportunistically into
`match_players.color_id`. No replay is captured or parsed, the ingester's capture path is not
touched, and FR-014 stays as written. When companion is degraded the colour is absent and the view
degrades under FR-010.

**Evidence — Relic has no colour, confirmed three ways (measured 2026-08-30).** `matchhistorymember`
has thirteen keys, none of them colour. The two opaque `slotinfo`/`options` blobs were decoded
(base64 + zlib), and one field inside `slotinfo` was itself a second base64 layer:

- `slotinfo` → plain JSON per slot: `profileInfo.id`, `stationID`, `teamID`, `factionID`, `raceID`,
  `rankLevel`, `rankMatchTypeID`, `timePerFrameMS`, `isReady`, `status`, `metaData`. `raceID`
  duplicates `civilization_id`. **No colour.** `stationID` is not a colour proxy — on an 8-player
  match the values are `1, 2, 3, 16, 6, 12, 8, 13`, running past 8 and skipping, i.e. a lobby-station
  id, not a 1..8 index.
- `slotinfo[].metaData` → a second base64 layer decoding to a tiny key/value record holding only
  `ScenarioPlayerIndex` and `Team`. **No colour.**
- `options` → a length-prefixed `key:value` bag of lobby settings (map name, population cap, …). Game
  rules, not participants.

So the colour a player actually used is genuinely absent from every Relic field. Reverse-engineering
the game's own files to recover it is both unnecessary and a line Microsoft's Game Content Usage
Rules forbid crossing.

**Evidence — companion serves colour directly, without a replay.** Verified live against the user's
test game **501455090** (Azhague33, profile 1807091), 2026-08-30:

| Endpoint              | Call                                                | Returns                                                                       |
| --------------------- | --------------------------------------------------- | ----------------------------------------------------------------------------- |
| List a player's games | `GET /api/matches?profile_ids=<id>&page=&per_page=` | a page of matches, each already carrying full `teams[].players[]` with colour |
| One game's details    | `GET /api/matches/<matchId>`                        | one match, same per-player shape                                              |

For 501455090 the colours came back `Ygrid33=4` (yellow), `Azhague33=8` (orange), `iBenj=3` (green),
`cpt_kernel=1` (blue) — an exact match to the reference screenshot, as were the ratings, the signed
diffs and the winning side. **Every player on that match has `replay: false`**: no replay was ever
captured, and companion still has the colour. Companion sources it from live match/lobby data, not
from a recording, so colour is available for essentially every ranked match regardless of whether its
replay was ever caught — better coverage than the capture pipeline itself.

**Why read-time enrichment and not the ingester.** The colour is companion's, and companion is
"enrichment only, degradable" by the constitution's Technology Constraints. Reading it when a match
is displayed — the way the app already pulls civ names from companion, and the way
`_refresh_third_party_history` (`routers/players.py:162`) already fetches on view — keeps it out of
the capture path entirely. FR-014's subject is what the ingester _captures_; a display-time
enrichment does not change that. The colour is cached back into `match_players.color_id` so a second
view of the same match is a database read, but that cache is written by the enrichment step, never by
the ingester and never on the capture path, and colour never changes once a match is over, so the
cache is trivially correct and idempotent. This is the `color_id` exception to D1's projection: its
five siblings come from Relic's `raw_payload`, colour comes from companion.

**Companion's rating/civ/winner are a cross-check, not a source.** The same response carries civ,
rating, `ratingDiff`, `won` and `team`. Relic is primary and authoritative for all of those (D1), so
they stay Relic-derived; companion supplies only the one field Relic lacks. A companion value that
disagrees with Relic is a signal to investigate, not a value to write.

**Wiring.** `MatchEnrichment` (`base.py:215`) gains a `participants` map parsed from
`teams[].players[]` — a parse widening of the response `enrich_matches` already fetches, plus wiring
that method into the match read paths. Everything else — timeout, retry, token bucket, circuit
breaker, the `provider_calls` sink — is inherited unchanged.

**Alternatives considered.**

- _The replay header._ Rejected. The parsed `.aoe2record` carries an explicit
  `zheader.game_settings.players[].color_id` (0-indexed; `+1` gives the canonical 1..8 scheme), so it
  is a valid source — but it exists only for matches whose replay was captured _and_ parsed, which is
  strictly worse coverage than companion (which has colour for `replay: false` matches), and it pulls
  a slice of replay parsing forward from V2 and gives the parser its first write into application
  tables. Companion needs neither.
- _Derive colour from `team_id` + participant ordering._ Rejected: an invention presented as a fact.
  Players pick their own colours in the lobby — on 501455090 the seat order does not equal the colour
  order — and feature 002's "gaps are decisions, not oversights" forbids interpolating.
- _Make companion the primary match-list source._ Rejected: the constitution fixes Relic as primary
  and companion as degradable enrichment. Companion returns the whole list with colour in one call,
  which is convenient, but adopting it as the source would invert that ordering and make the match
  list vanish whenever companion 403s.
- _Drop FR-003 from scope._ Rejected: it is a P1 acceptance scenario, the source exists and is proven,
  and the cost is a parse widening on a provider already wired, rate-limited and breaker-protected.

---

## D3 — Asset packs, and the licence ruling the FR-011 gate turns on

### The finding

**There is no openly-licensed AoE2:DE civilisation-icon or minimap pack in existence.** Every
candidate is game art extracted from the game files; the MIT/GPL `LICENSE` on each repository covers
that repository's _code_. Two of them say so themselves, which is the strongest evidence available:

`SiegeEngineers/aoe2techtree` ships a separate `img/README` whose entire content is

> Game Icons © Hidden Path Entertainment, Forgotten Empires, SkyBox Labs, Ensemble Studios

That file exists precisely to carve `img/` out of the root MIT licence.

### The ruling

**Decision**: Constitution X 5.0.0's "MAY be copied into the repository" accepts a pack whose
permitted usage is Microsoft's Game Content Usage Rules. The FR-011 gate is satisfied by recording
_source + permitted usage + the date checked_; it does not require an SPDX redistribution grant.

**Rationale.** The amendment's own words settle it. X 5.0.0 permits copying in game assets
"**as non-Microsoft fan sites do**", and its changelog entry says the previous ban "was stricter than
Microsoft's Game Content Usage Rules require for non-commercial fan use". GCUR-only packs are exactly
what non-Microsoft fan sites use, because nothing else exists. An SPDX-grant reading would make
5.0.0 a dead letter — it would permit a category with zero members — three commits after it was
ratified as a MAJOR amendment to fix precisely this.

**The residual risk, recorded rather than laundered.** GCUR grants a revocable, non-exclusive licence
to _use and display_ Game Content and to create derivative works, on a non-commercial basis with a
notice. It separately forbids reverse-engineering the game to access assets. Every pack below was
produced by an extraction that GCUR does not authorise — by its upstream authors, not by this
project, which copies an already-published public repository. That is the settled community norm and
Microsoft has never enforced against it, but it is a norm and not a permission. `docs/risks.md` R7 is
rewritten to say so instead of its current, now-false, "no game asset in the repository".

### The packs

Every row checked **2026-08-30**. This table is the source that `docs/asset-packs.md` is written from.

| Pack                     | Source                                          | Holds                                   | Licence                                                                          | Evidence                                         | Ruling                                                          |
| ------------------------ | ----------------------------------------------- | --------------------------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------ | --------------------------------------------------------------- |
| **Civilisation icons**   | `SiegeEngineers/aoe2techtree`, `img/Civs/`      | 60 PNG, `<lowercase-name>.png`          | **None.** Third-party © asserted; root LICENSE is MIT and does not reach `img/`  | `img/README`; root `README` credits GCUR         | **COPY IN** under GCUR, non-commercial + notice                 |
| **Map minimaps**         | `SiegeEngineers/aoe2cm2`, `public/images/maps/` | 435 PNG, kebab-case of the display name | **None** (`license: null` on the repo); README states assets are AoE2 under GCUR | GitHub API `license: null`; README credits block | **COPY IN** under GCUR, non-commercial + notice                 |
| **Country flags**        | `lipis/flag-icons`                              | ~260 SVG, ISO 3166-1 alpha-2            | **MIT** — and the flag designs themselves are public domain                      | repo `LICENSE`                                   | **COPY IN**, MIT                                                |
| **Player colours**       | 8 hex values (see below)                        | not an image pack                       | **Not copyrightable** — eight RGB triples are facts, below the _Feist_ threshold | —                                                | **COPY IN**, recorded anyway                                    |
| aoe2companion CDN        | `backend.cdn.aoe2companion.com`                 | civ + map images                        | **None found**, no terms published                                               | source repo `license: null`                      | **AVOID**                                                       |
| `SiegeEngineers/aoe2map` | aoe2map.net                                     | user-uploaded RMS previews              | GPL-3.0 on code only; per-image provenance unknown                               | repo licence field; `/info` carries none         | **AVOID**                                                       |
| `aoc-reference-data`     | SiegeEngineers                                  | names, constants — no images            | **None found**, still true                                                       | `license: null`                                  | **READ ONLY** — unchanged, `docs/data-sources.md:99-106` stands |

### Keying — measured, not assumed

- **Civs**: `apps/api/src/aoe2stats_api/civilizations.py`'s 59 names were joined against the
  techtree filename set. `name.lower().replace(' ', '_')` resolves **59 of 59, zero misses**. No
  hand-maintained `civ_id → slug` table is needed, and none is introduced — feature 002 owns the
  names and 004 keys off them, per the spec's own assumption.
- **Maps**: Relic serves a `mapname` string and no map id. aoe2cm2's filenames are kebab-case of the
  display name, so `map_name.lower().replace(' ', '-')` keys straight off it. Coverage is 435 files
  against an unbounded string space — custom and tournament maps will miss, which is exactly the
  FR-010 degrade path, not a defect.
- **Rejected for maps: aoe2companion's CDN.** Its slugs derive from an internal map id and the
  separator is inconsistent — `African Clearing → rm_african_clearing` but
  `Black Forest → rm_black-forest`. No single transform of `mapname` reaches both, so it would cost a
  hand-maintained lookup table that aoe2cm2 does not.

### Player colours

The eight canonical AoE2:DE player colours, measured 2026-08-30 from aoe2companion's `colorHex`
across all eight slots. Upstream ground truth is the game's own
`resources/_common/dat/spritecolors.json`, which is not published on the web.

| `color_id` | Hex       | Name   |
| ---------- | --------- | ------ |
| 1          | `#405BFF` | Blue   |
| 2          | `#FF0000` | Red    |
| 3          | `#00FF00` | Green  |
| 4          | `#FFFF00` | Yellow |
| 5          | `#00FFFF` | Teal   |
| 6          | `#FF57B3` | Purple |
| 7          | `#797979` | Grey   |
| 8          | `#FF9600` | Orange |

**Decision**: these ship as design-system colour tokens, not as an asset pack — constitution VI
forbids a hard-coded colour in a component, and these are colours. They need a paired
`-contrast` token each, because several (yellow, green, cyan) fail contrast against the light theme's
parchment background at any usable text size. See the design-system gap register.

---

## D4 — Where the licence record lives

**Decision**: a new `docs/asset-packs.md`, plus a `LICENCE.md` beside each pack's files, plus
`scripts/checks/asset_packs.py` in the nightly and PR checks.

**Rationale.** FR-011 leans on "feature 002's discipline", and 002's `docs/reference-data.md`
**does not exist** — 002 is 2 tasks done of 15, and T205 (the source inventory with licences) is
open. Blocking 004 on an unstarted feature is not a plan. What 002 fixed is the _discipline_, not the
file, and it is fully specified: each entry records what the source holds, its licence status, the
ruling that follows (may its data be copied in, or only be read), and the date the status was
observed — "no entry ships without all three" (002 SC-002).

`docs/asset-packs.md` is the right home under CLAUDE.md's three-homes test: a licence is a fact about
the outside world on a date, it must be true _today_, and it changes when the world changes. It is
not a decision frozen at its date, so not an ADR — 002's research.md rejected an ADR for exactly this
content and that reasoning transfers unchanged.

**The per-pack `LICENCE.md` is what makes the gate real.** A record in `docs/` that a pack directory
does not carry can be deleted, moved or forgotten independently of the files it covers. Requiring the
record to sit _in_ the pack means a pack cannot be copied in without it travelling along, and it
makes SC-003 ("100% of packs have a recorded source and permitted usage; a pack without that record
is absent") a one-line executable check instead of a promise: every directory under
`packages/game-assets/` either has a `LICENCE.md` with all five required fields (Source, Licence,
Permitted usage, Ruling, Checked — [contracts/asset-pack.md](./contracts/asset-pack.md)), or the
check fails. (Feature 002's SC-002 fixed three fields; the two additions — Ruling and Checked — only
matter once files are copied rather than transcribed.)

---

## D5 — Where the packs live, and how they are served

**Decision**: a new workspace package `packages/game-assets/`, one directory per pack, each with its
`LICENCE.md`. Mounted at the URL prefix `/game-assets/` by both `apps/web` (Vite static copy) and
Storybook (`staticDirs`).

**Rationale.**

- **The design system stays asset-agnostic.** Components take an image URL as a prop; they never
  import a PNG. That keeps `packages/design-system` a token-and-component library, keeps its unit
  tests free of binary fixtures, and lets a story render a stub. It also means the FR-010 degrade
  path is a prop being `undefined`, which is trivially testable.
- **The licence gate is per pack, and a package makes a pack a directory.** D4's check becomes a
  directory walk.
- **Constitution XII.** A URL prefix served as a static file works identically on Vercel and behind
  nginx on a VPS. No filesystem reads at runtime, no origin-specific code.

**Size budget**: re-encode to WebP on the way in — civ icons at ≤128 px, minimaps at ≤256 px — and
cap the whole package at **10 MB**, enforced by the same check as the licence record. Re-encoding is a
derivative work, which GCUR explicitly permits. The alternative, committing 495 source PNGs at
50–70 KB each, is ~30 MB in a repository that has no other binary content.

**Alternatives considered.**

- _`apps/web/public/`._ Rejected: Storybook could not reach it, so visual regression — mandatory
  under constitution VII — would run against missing images.
- _`packages/design-system/assets/`._ Rejected: it makes the design system depend on the game, and
  puts a 10 MB binary payload inside the package every other package imports.
- _Hotlinking a third-party CDN._ Rejected: it is the pre-5.0.0 workaround, it makes the product's
  imagery depend on an unlicensed single-maintainer service (`docs/risks.md` R4), and it leaks a
  viewer's IP to that service on every page view.

---

## D6 — The avatar

**Decision**: add a nullable `aoe_profiles.avatar_hash`, populated opportunistically from any
companion response that carries it; expose it as `avatar_hash` on the profile response; build the
Steam CDN URL client-side.

**Evidence.** Companion's `/api/profiles?search=` serves `avatarhash` on every record
(`packages/providers/fixtures/companion_profiles_search.json`, measured and recorded at
`docs/data-sources.md:299`). `_parse_search_result` (`companion/provider.py:425-457`) does not read
it and `PlayerSearchResult` has no field for it, so it is discarded today. It is persisted nowhere:
`provider_calls` has no body column by design, and `profile_search_cache.results` stores only the six
`PlayerSearchResult` fields.

**Rationale for storing rather than fetching per view.** `GET /api/players/{id}` makes no companion
call at all today; it reads `aoe_profiles` directly. Adding a provider call to a display path would
put a degradable third-party dependency (403s intermittently, `docs/risks.md` R4) in front of every
profile render. Storing the hash costs one nullable column and degrades to the FR-008a placeholder
when absent — which is the required behaviour anyway, so the degraded path is exercised by design
rather than only under failure.

**Constitution IX is engaged.** `avatar_hash` is new personal data, so it goes in
`docs/privacy/processing-register.md` **in the same PR** — not a follow-up. It is public data from a
public source under the same legitimate-interest basis as `alias` and `country`, which it sits beside;
it is carried, never used to link or merge profiles.

**The image itself.** The browser loads `https://avatars.steamstatic.com/<hash>_full.jpg`. That is a
client-side image reference, not an outbound connection from `apps/*` or `packages/core`, so
constitution III is untouched — FR-015 already states this and it holds. A broken hash yields a
broken image, so the `<img>` carries an `onError` fallback to the same neutral placeholder the
null-hash case uses.

---

## D7 — The match list row has to widen

**Decision**: `MatchListRow` gains `rating`, `team_id` and `color_id`, and the row's participant list
becomes _all_ participants rather than opponents only.

**Rationale.** US1 asks for "each player's colour" and "which side won" on a match in the history
list. Today `list_matches` selects neither `rating` nor `team_id` nor `color_id`
(`repositories/matches.py:237-249`), and `_opponents_by_game` (`:308-362`) deliberately excludes
teammates — "the field is named `opponents`". FR-005's `922 (+16)` needs the absolute rating, which
the list row does not carry at all; only match _detail_ does.

**Compatibility.** `match_row_json` is imported by `routers/players.py:97` from `routers/matches.py`
precisely so the two routes cannot drift, and `apps/api/tests/test_players_history.py` asserts that
identity. Both keep working; the assertion is what makes widening safe. `opponents` is retained as-is
so nothing that reads it breaks, and the full list arrives as a new `participants` field.

---

## D8 — Artifacts that are stale against constitution X 5.0.0

Corrected in this feature, because the packs cannot land while the repository says they may not exist.
The constitution's own "Open follow-ups" list names the third of these.

| Where                                          | Says                                                                  | Must say                                                                                                                                                                                                                                   |
| ---------------------------------------------- | --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `README.md:29`                                 | "uses no assets from the game"                                        | it uses game assets under GCUR — while keeping the disclaimer at `:31-34` **verbatim**, which `Footer.test.tsx` asserts against                                                                                                            |
| `packages/design-system/specs/README.md:48-51` | "No game asset, ever… this is a legal boundary"                       | the boundary is the licence record, not the asset                                                                                                                                                                                          |
| `docs/risks.md:R7`                             | "no game asset in the repository"                                     | the packs, their basis, and D3's residual extraction risk                                                                                                                                                                                  |
| `MatchRow/index.tsx:38`                        | "factual name only, no emblem (§2 IP note)"                           | the icon prop and its degrade rule                                                                                                                                                                                                         |
| `UploadControl.test.tsx:343`                   | asserts no `<svg>`/`<img>` anywhere but the spinner                   | scope to the component, not the codebase                                                                                                                                                                                                   |
| `.claude/skills/design-system/SKILL.md:45`     | "No game asset in the repository: no civilisation icon, no portrait…" | the constraint is a recorded licence, not an absent asset. **This file is loaded into an agent's context before every UI task in this feature** — a dispatched agent otherwise reads a standing ban on the thing it is being told to build |
| `.claude/agents/product-designer.md:15`        | "without ever reusing a single game asset"                            | the agent that owns `packages/design-system/specs/` and every token; game assets under GCUR are now in scope for it to spec                                                                                                                |

The first five are the pre-existing list; the two `.claude/` rows are **living documents that gate
agent behaviour** and so are corrected first — see T411.

Also stale, and touched only where this feature's components reach them:
`specs/sign-in-screen.md:40`, `profile-summary.md:53`, `player-search.md:40-41`,
`favourites-list.md:44-45`, `favourite-toggle.md:37`, `manual-upload.md:249` ("§4's ban"). The
`(no game assets)` gloss in `tests/architecture/test_import_graph.py:18`'s module docstring is a
comment with no assertion behind it; correct it in the same pass.

---

## D9 — The map thumbnail source, revisited after PR review (2026-08-30)

PR review rejected the maps as not matching the generic-starting-position style peers show, pointing
at `https://www.aoe2insights.com/static/images/maps/{slug}.png` as the reference. Investigation
found the rejection was aimed at the wrong layer:

- **The style was already correct.** The vendored pack (D3, aoe2cm2 `public/images/maps/`) _is_ the
  DE lobby random-map preview — a diamond map with coloured starting positions — the same asset
  aoe2insights hosts. Compared `arabia.webp`/`black-forest.webp` against the reference directly.
- **The real defect is resolution.** aoe2cm2 ships these previews at **140×140** natively; aoe2insights
  hosts a higher-resolution copy of the same game asset (~256 px+), which is why it looks crisp and
  the 140 px pack looks soft.
- **The local AoE2 DE install — the highest-fidelity, authoritative source — is unavailable.** DE is
  Windows/Xbox-only; there is no macOS build and none is installed on the development machine (Steam,
  `appmanifest_813780`, `resources/_common/drs`, `.drs`/`.sld` archives, and Wine/CrossOver/Parallels
  bottles all searched, all absent). Copying or DRS/SLD-extracting from the game (the game keeps these
  previews as loose image files, not inside DRS/SLP, so extraction ≡ a file copy) can only be done on
  a Windows/DE machine, by hand, as a manual step.
- **aoe2insights is rejected as a programmatic source.** The whole domain sits behind an interactive
  Cloudflare bot-challenge (`cf-mitigated: challenge`; scripted fetch → 403 interstitial; a real
  browser escalates to a "verify you are human" checkbox). It must not be bypassed, automated or
  solved, so it cannot back an automated or repeatable sync.

**Decision (product call, 2026-08-30): keep aoe2cm2 at 140 px** — the maintained, openly-reachable
mirror (last push four days before this note), correct style and naming, already recorded in
`maps/LICENCE.md` and `docs/asset-packs.md`. The 140 px limitation is accepted; the higher-fidelity
local-extraction route stays available to a future change but needs a Windows/DE machine to run.

**The synchronisation the pool needs is a dev-time, network-free script** (T448):
`scripts/ops/sync_map_thumbnails.py` re-encodes a local `--source-dir` of downloaded aoe2cm2 PNGs
into `packages/game-assets/maps/`, reproducing the committed pack and adding only what is new. The
network hop — downloading the source — stays a documented human step (`docs/runbooks/map-thumbnail-sync.md`),
because committed project code makes no external call outside `packages/providers`
(`scripts/checks/contract_sources.py` is the single sanctioned exception) and this feature vendors
every asset by hand (D5, T404–T406). No openly-licensed or non-gated higher-resolution mirror was
found; the licence basis is unchanged (GCUR, as D3).

---

## Resolved unknowns from Technical Context

| Unknown                                   | Resolution                                                                                                                                 |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Which civ icon pack, and its licence      | aoe2techtree `img/Civs/`, GCUR-only, copied in — **D3**                                                                                    |
| Which minimap pack, and its licence       | aoe2cm2 `public/images/maps/`, GCUR-only, copied in — **D3**; 140 px kept, aoe2insights rejected (Cloudflare), synced by a script — **D9** |
| How a pack keys off `civ_id` / `map_name` | `name.lower()` with `_` and `-` respectively; 59/59 civs, 435 maps — **D3**                                                                |
| Where the licence record lives            | `docs/asset-packs.md` + per-pack `LICENCE.md` + a check — **D4**                                                                           |
| Where flags come from                     | `lipis/flag-icons`, MIT — **D3**                                                                                                           |
| The eight player colours                  | measured hex values, shipped as tokens — **D3**                                                                                            |
| Where `color_id` comes from               | companion `GET /api/matches`, read-time, replay-free — **D2**                                                                              |
| Where the avatar hash is stored           | new `aoe_profiles.avatar_hash` — **D6**                                                                                                    |
| Whether the data US1 needs exists         | it does not; projection + backfill required — **D1**                                                                                       |
| Asset payload budget                      | WebP, ≤10 MB for the package, checked — **D5**                                                                                             |
