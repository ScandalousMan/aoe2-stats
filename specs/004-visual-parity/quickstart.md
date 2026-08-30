# Quickstart: Visual Parity — validation scenarios

**Feature**: `004-visual-parity` | **Date**: 2026-08-30 | **Plan**: [plan.md](./plan.md)

How to prove this feature works, end to end. Seven scenarios, one per acceptance surface, in the
order the phases land. Each says what to run and what you must see — not how to build it.

## Prerequisites

```bash
uv sync && pnpm install
```

- A Postgres reachable at `DATABASE_URL`, migrated to head. The pytest harness
  (`tests/db.py`) creates a throwaway database per session; it skips locally when none is reachable
  and **fails hard when `CI` is set**.
- **`.env.local` points at production Neon.** Never run the backfill or any Alembic command against
  it while validating. Export a local `DATABASE_URL` explicitly for every command below.
- Fixtures only. `tests/conftest.py` blocks non-loopback sockets workspace-wide (constitution III), so
  nothing here reaches a provider.

---

## Scenario 1 — The licence gate refuses an unrecorded pack (FR-011, SC-003)

Proves the constitution X gate is executable, not a promise.

```bash
uv run python scripts/checks/asset_packs.py
```

**Expect**: exit 0, and one line per pack naming its ruling and check date.

Then prove it bites — the check is worthless if it only ever passes:

```bash
mkdir -p packages/game-assets/scratch && touch packages/game-assets/scratch/x.webp
uv run python scripts/checks/asset_packs.py; echo "exit=$?"
rm -rf packages/game-assets/scratch
```

**Expect**: non-zero exit naming `scratch` as having no `LICENCE.md`. Repeat with a `LICENCE.md`
missing its `Checked:` line, and with the `README.md` disclaimer paragraph deleted — both must fail.
That last one is the point: remove either constitution X anchor and the permission lapses, so the
check that guards the packs guards the anchors too.

Contract: [contracts/asset-pack.md](./contracts/asset-pack.md).

---

## Scenario 2 — The projection fills what was never written (D1, FR-001/004/005)

The load-bearing scenario. Before this feature, every one of these columns is `NULL` in production.

```bash
uv run pytest packages/storage/tests packages/providers/tests apps/ingester/tests -q
```

**Expect**: the projection's unit tests pass against
`packages/providers/fixtures/relic/get_recent_match_history.json`, including
`outcome` → `result` for `1`, `0` and a third value; `rating_diff` `null` when a rating is missing
(never `0`); and a raised error when a projection disagrees with `matchhistoryreportresults`.

Then against a real row:

```bash
DATABASE_URL=postgresql://…local… uv run python scripts/ops/backfill_match_players.py --dry-run
```

**Expect**: a count of rows it would fill and no writes. Run it for real, then re-run it —
**the second run must report zero rows changed.** It reads `matches.raw_payload` and never re-fetches;
if it issues a provider call, the design is wrong.

---

## Scenario 3 — Colour arrives, and its absence is a resting state (D2, FR-003)

```bash
uv run pytest packages/providers/tests/test_companion.py -q
```

**Expect**: `MatchEnrichment.participants` parsed from `packages/providers/fixtures/companion/matches.json`
with `color_id` present; and, critically, that a **degraded companion writes nothing** rather than
writing `NULL` — a Relic-only refresh must never null out a colour supplied earlier.

Verify the negative directly:

```sql
SELECT color_id, civ_id, result FROM match_players WHERE game_id = <a match companion does not know>;
```

**Expect**: `color_id` NULL with `civ_id` and `result` populated. That row must render correctly —
it is a permanent legitimate state, not a migration in progress (data-model.md §6).

---

## Scenario 4 — The API delta (FR-005, FR-008a, contracts/http-api.md)

```bash
uv run pytest apps/api/tests -q
```

**Expect** in particular:

- `test_players_history.py`'s row-shape identity between `GET /api/matches` and
  `GET /api/players/{id}/matches` still passes. It is what keeps the two routes from drifting, and it
  is the reason widening `match_row_json` is safe.
- `test_schema_revision.py` passes — `EXPECTED_SCHEMA_REVISION` was bumped in the same commit as the
  migration, or the whole suite fails here.
- No response carries a colour hex, an icon URL or a flag URL. Colours are tokens and asset URLs are
  resolved client-side from the pack; a provider must not be able to set a product colour.

```bash
uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head
```

**Expect**: clean both ways. The migration is one additive nullable column.

---

## Scenario 5 — US1, a match is legible at a glance (FR-001..006, FR-010)

```bash
pnpm --filter design-system storybook
```

Open `Composite/MatchRow` and `Composite/MatchDetailPanel`. **Expect**, in both light and dark:

1. Civilisation icon **and** name — no bare `civ_id` anywhere.
2. Minimap thumbnail **and** map name.
3. Each participant in their canonical player colour, with a name beside it — colour is never the only
   carrier of meaning.
4. Winner distinguished from loser by a text or shape signal, not colour alone; and a **third**
   neutral state for a `null` result, which must not read as a loss.
5. Rating and signed change, `922 (+16)` / `921 (−15)`, direction legible without colour.

Then the degrade stories, which are the ones that actually prove FR-010:

- **Unknown civ id** (outside the pack, e.g. a new expansion) → the readable label, no broken image.
- **Unknown map name** (a custom or tournament map) → the name alone, no broken image.
- **`color_id` null** → the neutral token, still legible.

**Expect zero broken or missing images across all three** (SC-005). Confirm with the browser's network
panel: no 404 under `/game-assets/`. The resolver returns `undefined` rather than a URL that 404s, so
a 404 here means the contract was implemented wrong.

---

## Scenario 6 — US2 and US3, the profile and the site (FR-007..009)

Still in Storybook: `Screens/ProfileSummary` and `Chrome/SiteHeader`.

**Expect**:

- Alias as the heading, numeric id demoted to a secondary reference.
- Country flag beside the name; cleanly absent when `country` is null — not a gap that reads as an
  error.
- Avatar from the Steam CDN. **Check the null-hash story and the broken-hash story render
  identically**, both showing the neutral placeholder — a stale hash must not produce a broken image.
- No alias → the numeric id becomes the heading. Never a blank one.
- "No ratings yet" unchanged: a calm explanation, not an error. Profile `1807091` genuinely has this
  state and it is a correct outcome.
- A header with working navigation, and the footer with its Game Content Usage Rules disclaimer still
  present on every route.

Then in the app:

```bash
pnpm --filter web dev   # then open /players/1807091 and /players/1807091/matches
```

---

## Scenario 7 — The gates that must be green to merge

```bash
uv run ruff format . && uv run ruff check --fix . && uv run mypy && uv run pytest
pnpm -r test && pnpm --filter design-system build-storybook && pnpm test:visual --changed
```

**Expect**: all green, and specifically —

- **Visual regression ran against real images.** `staticDirs` must mount `packages/game-assets`, or a
  story renders a missing image and passes its snapshot just as happily as a correct one. If
  `scripts/visual/run.mjs` logs that it found no changed stories, the run proved nothing — check that
  your `.stories.tsx` changes are in the diff `VISUAL_BASE_REF` sees.
- **Focus and hover are not covered by snapshots.** The header's navigation states need an interaction
  test; a static screenshot cannot see them.
- `apps/web` builds, and `scripts/checks/built-css.mjs` and `spa-routing.mjs` pass.

### Before the PR is merged

Both are constitution requirements in _this_ PR, not follow-ups:

- `docs/privacy/processing-register.md` records `avatar_hash` as new personal data with its basis
  (constitution IX).
- The five artifacts stale against constitution X 5.0.0 are corrected — `README.md:29`,
  `packages/design-system/specs/README.md:48-51`, `docs/risks.md` R7, `MatchRow/index.tsx:38`,
  `UploadControl.test.tsx:343` (research.md D8). The packs cannot land while the repository still says
  they may not exist.
- `README.md:31-34`'s disclaimer paragraph is **byte-identical** to before. `Footer.test.tsx` asserts
  the footer against it; changing the wording breaks the footer and removes a constitution X anchor.
