# Data Model: Visual Parity

**Feature**: `004-visual-parity` | **Date**: 2026-08-30 | **Plan**: [plan.md](./plan.md)

One additive column, five columns that finally get written, and four presentation entities that live
in the front end and touch no table. Nothing is dropped, renamed or re-typed.

> **Naming note.** The spec's Context says `players.alias` / `players.country`. There is no `players`
> table — it is **`aoe_profiles`** (`packages/storage/src/aoe2stats_storage/models.py:221`). Every
> reference below uses the real name.

---

## 1. Schema changes

### `aoe_profiles` — one new column

| Column        | Type   | Nullable | Default | Why                                                                                                                             |
| ------------- | ------ | -------- | ------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `avatar_hash` | `Text` | **yes**  | `NULL`  | The Steam avatar hash as aoe2companion reports it. The image URL is built client-side (FR-008a); no URL and no image is stored. |

- **Nullable is the normal case, not the error case.** A profile never seen in a companion response
  has no hash, and FR-008a's neutral placeholder is the correct render — not a degraded one.
- **Never used to link or merge profiles** (constitution IX's unverified-third-party-claim rule),
  the same standing as the `unverified_steam_id` it arrives beside.
- **Joins the GDPR surface in the same PR**: the export bundle, the erasure pseudonymisation path,
  and `docs/privacy/processing-register.md`. New personal data, so constitution IX requires all three
  now, not later.
- Migration: additive, one `ALTER TABLE … ADD COLUMN`, no backfill, no lock of consequence. Bump
  `packages/storage/src/aoe2stats_storage/revision.py`'s `EXPECTED_SCHEMA_REVISION` **in the same
  commit** — `apps/api/tests/test_schema_revision.py` asserts it against `alembic heads` on every run.

### `match_players` — no schema change, five columns that start being written

The columns already exist, correctly typed and nullable, since `4fdc4873ab6c_initial_schema`. They
have never been written (research.md **D1**). This feature makes them true.

| Column        | Source in `matches.raw_payload`                            | Rule                                                                                             |
| ------------- | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `civ_id`      | `matchhistorymember[].civilization_id`                     | direct                                                                                           |
| `team_id`     | `matchhistorymember[].teamid`                              | direct                                                                                           |
| `rating`      | `matchhistorymember[].newrating`                           | the rating **after** the match, which is what FR-005 shows                                       |
| `rating_diff` | `newrating - oldrating`                                    | signed; `NULL` if either side is missing, never `0` as a stand-in                                |
| `result`      | `matchhistorymember[].outcome`                             | `1` → `win`, `0` → `loss`, anything else → `NULL`, which FR-004 renders as its own neutral state |
| `color_id`    | **not in Relic** — aoe2companion `teams[].players[].color` | `NULL` whenever companion is degraded or the match is unknown to it (FR-010)                     |

`matchhistoryreportresults[]` carries `civilization_id`, `teamid` and `resulttype` for the same
participants. It is the **cross-check, not a second source**: a projection that disagrees with it is
a bug to raise, never a tie to break silently.

**Write paths, and there are exactly two, both idempotent — but they run in different places:**

1. **The five Relic-derived columns**, on the ingester's capture path. `upsert_match_player` widens
   from `ON CONFLICT DO NOTHING` to `ON CONFLICT DO UPDATE`, setting them from the response the same
   transaction already holds. Re-seeing a match refreshes them from the freshest response, matching
   `upsert_match`'s existing posture. **`color_id` is not in this statement's `SET` clause** — a
   Relic-only refresh must never null out a colour the enrichment supplied earlier.
2. **`color_id` alone**, on the display path, not the ingester (D2). When a match is shown, the
   companion enrichment (`GET /api/matches`, batched over the page) supplies colour, which is written
   back to `match_players.color_id` keyed `(game_id, profile_id)` as a cache — only when companion
   returned a value. A degraded companion writes nothing; it does not write `NULL`. Colour never
   changes once a match is over, so the cache is trivially correct, and a second view of the match is
   a database read. This keeps colour off the capture path, so FR-014 is untouched.

**Backfill** (`scripts/ops/backfill_match_players.py`): reads `matches.raw_payload` for rows whose
`match_players` are still NULL, applies the same projection function as path 1, and writes. It never
re-fetches — the bytes are already on disk under constitution IV — and it is safe to re-run: the same
input yields the same output, and rows already populated are left alone unless `--force`.

### `matches` — no change

`map_name`, `leaderboard_id`, `started_at`, `completed_at`, `duration_seconds` are all present and
correctly populated today. FR-002 and FR-006 read them as they are.

---

## 2. Provider DTOs

### `MatchEnrichment` — gains the participants it already receives

`packages/providers/src/aoe2stats_providers/base.py:215`. Every field stays optional; aoe2companion
is the one provider whose failure is not an error, and a missing key is normal.

| Field                                                                     | Status    | From                |
| ------------------------------------------------------------------------- | --------- | ------------------- |
| `game_id`, `map_display_name`, `game_mode`, `game_speed`, `civilizations` | unchanged | as today            |
| `participants: dict[int, EnrichedParticipant] \| None`                    | **new**   | `teams[].players[]` |

`EnrichedParticipant` (new, `StrictProviderModel`), keyed by `profile_id`:

| Field                      | Wire         | Note                                                                 |
| -------------------------- | ------------ | -------------------------------------------------------------------- |
| `color_id: int \| None`    | `color`      | the only field this feature consumes today                           |
| `team_id: int \| None`     | `team`       | carried for the cross-check against Relic's `teamid`                 |
| `won: bool \| None`        | `won`        | same                                                                 |
| `rating: int \| None`      | `rating`     | carried for the cross-check; Relic's `newrating` stays authoritative |
| `rating_diff: int \| None` | `ratingDiff` | same — two distinct wire keys, two distinct fields, never merged     |

Only `color_id` is written. The rest exist so a disagreement with Relic is _visible_ rather than
discovered later; Relic stays authoritative for everything it serves (`docs/data-sources.md` §1 vs
§3), and companion supplies only what Relic does not.

`colorHex` is **deliberately not carried.** The hex belongs to the design system as a token
(constitution VI); carrying a third-party colour string to the client would let a provider set a
product colour and would bypass the contrast pairing the tokens exist to guarantee.

### `PlayerSearchResult` — gains the hash it already receives

`base.py:228`. Add `avatar_hash: str | None`, parsed from `avatarhash` in `_parse_search_result`
(`companion/provider.py:425-457`), which reads five of the record's fields today and drops this one.
Its name says what it is, following `unverified_steam_id`'s precedent: it is a hash, not a URL, and
nothing in `packages/providers` builds the Steam URL.

---

## 3. Repository shapes

`packages/storage/src/aoe2stats_storage/repositories/matches.py`.

### `MatchListRow` — three additions

| Field                   | Status                                                                    |
| ----------------------- | ------------------------------------------------------------------------- |
| existing fields         | unchanged                                                                 |
| `rating: int \| None`   | **new** — FR-005 needs the absolute value; only match _detail_ carried it |
| `team_id: int \| None`  | **new** — which side the viewer was on                                    |
| `color_id: int \| None` | **new** — FR-003                                                          |

### `participants` alongside `opponents`

`_opponents_by_game` excludes teammates by design — "the field is named `opponents`". US1 needs every
player's colour and which side won, so a sibling projection returns **all** participants for the
match. `opponents` stays exactly as it is; nothing that reads it changes.

`MatchParticipant` (new, per row): `profile_id`, `alias`, `country`, `team_id`, `civ_id`, `color_id`,
`result`, `rating`, `rating_diff`.

---

## 4. Presentation entities

Front-end only. No table, no migration, no API field — these are the spec's Key Entities as they
actually land.

### Asset pack

A directory under `packages/game-assets/` holding one identifier space's images plus its `LICENCE.md`.
The unit the constitution X gate applies to, and the unit `scripts/checks/asset_packs.py` walks.
Format and required fields: [contracts/asset-pack.md](./contracts/asset-pack.md).

| Pack            | Key                                                              | From                          | Count |
| --------------- | ---------------------------------------------------------------- | ----------------------------- | ----- |
| `civilisations` | `civ_id` → name (feature 002) → `name.lower().replace(' ', '_')` | aoe2techtree `img/Civs/`      | 60    |
| `maps`          | `map_name.lower().replace(' ', '-')`                             | aoe2cm2 `public/images/maps/` | 435   |
| `flags`         | `country` (ISO 3166-1 alpha-2, lowercased)                       | `lipis/flag-icons` (MIT)      | ~260  |

### Civilisation presentation

`{ civId, name, iconUrl? }`. `name` comes from feature 002's mapping, which answers for **every**
integer — a known name, or `Civilisation {id}` — so there is no unnamed state. `iconUrl` is
`undefined` when the pack does not cover the id, and FR-010 then renders the name alone. 004 keys off
002's ids and never restates its names (spec Assumption; 002 FR-009).

### Map presentation

`{ mapName, thumbnailUrl? }`. `mapName` is Relic's string, shown verbatim. `thumbnailUrl` is
`undefined` for any map outside the 435 — custom and tournament maps, an unbounded space — and the
name alone is the render. This is the designed path, not a defect.

### Player colour

`{ colorId, token }` where `token` is a design-system token name, never a hex string. Eight ids,
measured values in research.md D3, each shipping with a paired `-contrast` token because several
(yellow, green, teal) are unreadable against the light theme's parchment at any usable text size.
`colorId` outside 1..8, or `NULL`, resolves to the neutral surface token. Constitution IV's
sibling rule applies at the component boundary: colour is never the only carrier of meaning
(design-system rule 4), so a colour swatch always sits beside a name.

### Profile presentation

`{ alias, profileId, country?, avatarHash?, ratings[] }`. `alias` is the heading and `profileId` the
secondary reference (FR-007); when `alias` is absent the id becomes the heading rather than a blank
one. `avatarHash` builds `https://avatars.steamstatic.com/<hash>_full.jpg` **in the component**, with
an `onError` fallback to the same neutral placeholder the absent-hash case uses — so a stale hash and
a missing hash render identically and neither shows a broken image.

### Match presentation

One `game_id`'s participants grouped by `team_id`, each with civilisation, colour and rating, with
the winning group distinguished by a text or shape signal in addition to colour, and a third neutral
state when `result` is `NULL`.

---

## 5. Validation rules

| Rule                                                                                                             | Where enforced                                             |
| ---------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| `result` is `win`, `loss`, or `NULL` — never a coerced third string                                              | projection function, unit-tested against the Relic fixture |
| `rating_diff` is `NULL` when either rating is missing — never `0`                                                | projection function                                        |
| A Relic-only refresh never nulls a companion-supplied `color_id`                                                 | the upsert's `SET` clause omits `color_id`                 |
| A projection disagreeing with `matchhistoryreportresults` raises, not guesses                                    | projection function                                        |
| Every pack directory has a `LICENCE.md` with all five fields (Source, Licence, Permitted usage, Ruling, Checked) | `scripts/checks/asset_packs.py` (SC-003)                   |
| `packages/game-assets` total ≤10 MB                                                                              | same check                                                 |
| An id outside a pack yields `undefined`, never a URL that 404s                                                   | the pack's `src/index.ts`, unit-tested for a known miss    |
| The footer disclaimer stays byte-identical to `README.md`                                                        | `Footer.test.tsx`, already in place                        |
| `EXPECTED_SCHEMA_REVISION` equals `alembic heads`                                                                | `apps/api/tests/test_schema_revision.py`, already in place |

## 6. State transitions

Only one, and it is per participant:

```text
(row exists, all NULL)                     ← today, every production row
        │
        ├── backfill, or a re-poll: project raw_payload
        ▼
(civ_id, team_id, result, rating, rating_diff written; color_id still NULL)
        │
        ├── shown to a user: companion enrichment on view succeeds, colour cached
        ▼
(fully populated)
```

Every state renders. The first transition is on the ingester's capture path; the second is on the
display path (D2). The middle state is FR-010's degrade path for colour alone and is a legitimate
resting state, not a migration in progress — a match never shown, or one companion has never heard
of, stays there, and the view is still correct.
