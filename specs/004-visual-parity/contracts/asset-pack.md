# Contract: Asset pack and its licence record

**Feature**: `004-visual-parity` | **Date**: 2026-08-30

The unit constitution X's licence gate applies to, and the interface `scripts/checks/asset_packs.py`
enforces. FR-011 and SC-003 are this document made executable.

> **Why the record lives beside the files.** A record kept only in `docs/` can be deleted, moved or
> forgotten independently of the images it covers, and then the repository holds an unrecorded pack
> while still claiming otherwise. Requiring the record _inside_ the pack means it travels with the
> files, and makes SC-003 — "a pack without that record is absent" — a directory walk instead of a
> promise. `docs/asset-packs.md` mirrors the records for a reader; the `LICENCE.md` files are the
> normative copies, and the check asserts the mirror matches.

## Pack layout

```text
packages/game-assets/<pack-name>/
├── LICENCE.md          # required — the record; a pack without it fails the check
└── <key>.<ext>         # the files, named by the identifier space's key
```

Rules:

- One pack, one identifier space. A pack keyed by `civ_id` never also holds map images.
- The filename **is** the key. No manifest, no id→filename lookup table: a table is a second place for
  the mapping to be wrong, and research.md D3 measured that both keys resolve by string transform
  alone (59/59 civs, 435 maps).
- No nested directories. The check walks one level, and the FR-010 miss test is `file exists`.

## `LICENCE.md` — required fields

All five. A pack missing any one of them fails the check; feature 002's SC-002 rule ("no entry ships
without all three") applies here with two additions that only matter once files are copied rather
than transcribed.

| Field               | Meaning                                                                                                      | Example                                                                        |
| ------------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------ |
| **Source**          | Where the files came from, precisely enough to re-fetch by hand — repository or site, and the path within it | `SiegeEngineers/aoe2techtree`, `img/Civs/`                                     |
| **Licence**         | The exact SPDX identifier, or `None found` — never a guess, never an inference from a sibling file           | `None found`                                                                   |
| **Permitted usage** | What this project is actually allowed to do, and the conditions                                              | Microsoft Game Content Usage Rules: non-commercial, notice required, revocable |
| **Ruling**          | `COPY IN` or `READ ONLY`, and the reasoning in one or two sentences                                          | `COPY IN` — constitution X 5.0.0                                               |
| **Checked**         | The date the licence status was observed, stated as an observation on a date and not as a permanent property | `2026-08-30`                                                                   |

Where a repository's root `LICENSE` does **not** cover the asset directory, the record must say so and
name the evidence. This is the normal case for game assets, and eliding it is how a pack gets
described as MIT when it is not.

## Example — the civilisation pack

```markdown
# Licence record — civilisation icons

- **Source**: `SiegeEngineers/aoe2techtree`, `img/Civs/` (60 PNG, re-encoded to WebP at 128 px)
- **Licence**: None found. The repository root carries MIT (© 2018 HSZemi), which covers the code
  and **not** this directory: `img/README` reads in its entirety "Game Icons © Hidden Path
  Entertainment, Forgotten Empires, SkyBox Labs, Ensemble Studios".
- **Permitted usage**: Microsoft "Game Content Usage Rules" — a revocable, non-exclusive licence to
  use and display Game Content and to create derivative works, strictly non-commercial, requiring the
  notice this project carries in `README.md` and the site footer. Re-encoding to WebP is a derivative
  work, which the Rules permit.
- **Ruling**: **COPY IN**. Constitution X 5.0.0 permits game assets in the repository on the
  non-commercial and disclaimer anchors, "as non-Microsoft fan sites do" — which is this case. No
  openly-licensed AoE2 asset pack exists, so an SPDX-grant reading would permit nothing at all. The
  residual risk this ruling accepts — GCUR permits display but not the extraction that produced the
  pack upstream — is recorded in `docs/risks.md` R7 and `specs/004-visual-parity/research.md` D3.
- **Checked**: 2026-08-30
```

## The check — `scripts/checks/asset_packs.py`

Read-only, no network, runs in PR checks and nightly. Fails on any of:

| Condition                                                                  | Why                                                                                     |
| -------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| A directory under `packages/game-assets/` has no `LICENCE.md`              | SC-003, the whole gate                                                                  |
| A `LICENCE.md` is missing any of the five fields                           | an incomplete record is not a record (002 SC-002)                                       |
| `Ruling` is `READ ONLY` but the directory holds files                      | a read-only source was copied in — the exact thing X forbids                            |
| `packages/game-assets` exceeds **10 MB**                                   | research.md D5's budget; keeps the repository's only binary payload bounded             |
| A pack's record is absent from `docs/asset-packs.md`, or disagrees with it | the mirror must not drift from the normative copies                                     |
| `README.md`'s disclaimer paragraph is absent                               | constitution X's first anchor; the footer half is already asserted by `Footer.test.tsx` |

The last row is the one worth stating plainly: **remove either anchor and the permission lapses**, so
the check that guards the packs also guards the two conditions under which they are lawful. A PR that
deletes the disclaimer fails on the assets, not only on the footer test.

## Resolution contract — `packages/game-assets/src/index.ts`

```ts
civilisationIcon(civName: string): string | undefined
mapThumbnail(mapName: string): string | undefined
countryFlag(countryCode: string): string | undefined
```

- Returns a URL under `/game-assets/…`, or **`undefined`** when the pack does not cover the key.
- **Never returns a URL that 404s**, and never returns a placeholder image path — the absent case is
  `undefined` so the component decides, which is what makes FR-010's "MUST NOT show a broken image"
  a type-level guarantee rather than a runtime hope.
- Coverage is a compile-time set generated from the directory listing at build, so a file added or
  removed cannot drift from what the resolver claims.
- `civilisationIcon` takes the **name**, not the id: feature 002 owns `civ_id → name` and 004 keys off
  it rather than introducing a second id table (spec Assumption; 002 FR-009).

Unit tests must cover a known hit, a known miss, and — for maps — a name with a space and a name with
punctuation, which is where a string transform quietly stops matching.

## Mounting

The same URL prefix in both consumers, so a component's `src` is identical in the app and in a story:

| Consumer   | How                                                                                                        |
| ---------- | ---------------------------------------------------------------------------------------------------------- |
| `apps/web` | Vite static copy of `packages/game-assets` to `/game-assets`                                               |
| Storybook  | `staticDirs: [{ from: '../../game-assets', to: '/game-assets' }]` in `.storybook/main.ts` (currently `[]`) |

Storybook mounting is not optional. Constitution VII makes visual regression mandatory, and a story
that renders a missing image passes its snapshot just as happily as one that renders the right image —
research.md D5 is where `apps/web/public/` was rejected for exactly this.
