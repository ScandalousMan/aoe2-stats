# Game-asset tokens (feature 004)

Token decisions feature 004 needs before **T410** can touch `tokens/color.json`, a new
`tokens/icon.json`, and `tokens/build-tokens.test.mjs`. Written by `product-designer`; the values
here are applied verbatim by T410's implementer, who invents nothing. Two decisions:

1. The **eight player-colour tokens** and their `-contrast` pairs (FR-003, data-model §4 "Player
   colour").
2. Closing gap **DS-7** with an **icon-size** token family, sized for the five image/icon marks 004
   introduces.

Measured contrast ratios and the gap-register closure live in
[`README.md`](./README.md) — the project's ledger for both — and are referenced, not restated, here.
This file is the source the token JSON is written from. The components that consume these tokens are
specified separately, in [`civilisation-icon.md`](./civilisation-icon.md),
[`map-thumbnail.md`](./map-thumbnail.md) and [`player-colour-swatch.md`](./player-colour-swatch.md)
(T428); this file decides the values, those files decide the behaviour.

---

## Decision 1 — Player-colour tokens

### What renders

A `PlayerColourSwatch` is a small colour chip that sits **beside a player's name**, never as the
only signal (design-system rule 4; data-model §4). The chip identifies which in-game colour a player
used. It is a non-text mark; text or a glyph (e.g. a winner marker) only rarely sits inside it.

### The eight colours are canonical facts — identical in both themes

The eight hex values are the game's own player colours (research D3), measured from aoe2companion's
`colorHex`. They are **the same in the light and dark theme**: a player's colour is their identity,
the way it is in-game, and re-tinting Blue per theme would break recognition and make the swatch lie
about which colour was played. So every `player-N` token carries one value in both theme blocks of
`color.json`.

Because the fill does not change between themes, the ideal ink to place **on** the fill does not
change either — so every `player-N-contrast` token is likewise theme-invariant. This is why the
measured table for these pairs has a single set of numbers rather than a light and a dark set.

### The light-parchment legibility problem is solved with a frame, not a re-tint

Four fills — Yellow `#FFFF00`, Green `#00FF00`, Teal `#00FFFF`, and to a lesser degree Grey
`#797979` — sit close to the light theme's parchment (`surface #fffaf0`, `background #f4ecd8`) in
luminance, so a bare fill would read as a faint smudge on parchment. The fix is **a frame, not a
per-theme darkening of the fill**:

> **Every swatch is drawn with a 1px `border-strong` frame in both themes.**

`border-strong` is the sanctioned non-text-boundary token (3:1 floor, WCAG 1.4.11). It already
clears 3:1 against every surface a swatch renders on — 3.5:1 on `surface`, 3.4:1 on `surface-raised`
in the light theme, higher in the dark theme — and those pairs are **already asserted** by
`build-tokens.test.mjs` (see README's measured table, `border-strong` rows). The frame bounds the
chip against parchment regardless of how pale the fill is, so the canonical hex never has to be
distorted. It is theme-blind by name (a component writes `border-strong`, not a light/dark choice),
and in the dark theme — where the bright fills are already vivid on the dark surface — it does no
harm.

No new outline token is introduced. Inventing a `player-outline` colour when `border-strong` is
exactly the "boundary of a non-text mark" role it already names would duplicate a value the contrast
test already guards.

### The neutral / unknown case

`color_id` outside `1..8`, or `NULL` (companion degraded, FR-010), resolves to a **`surface-sunken`
fill with the same `border-strong` frame** — an existing-token neutral chip — and the player's name
carries the meaning, as it always does. No new token; recorded so the implementer does not reach for
one. Why that neutral chip is not the "placeholder image" FR-010 forbids — nothing is fetched, and
the absence is stated in words to assistive tech — is argued in
[`player-colour-swatch.md`](./player-colour-swatch.md) §4.

### Tokens to add to `color.json`

These go in **both** the `light` and `dark` blocks of `tokens/color.json`, **with identical values
in each block** (that is the point — same name, same value, theme-invariant). They ride the existing
`color` family, so the generator emits `--ds-color-player-1` … `--ds-color-player-8-contrast`
automatically; no `build-tokens.mjs` change is needed for these.

| Token               | Value     | Name   | Rationale                                                               |
| ------------------- | --------- | ------ | ----------------------------------------------------------------------- |
| `player-1`          | `#405BFF` | Blue   | Canonical game colour, `color_id` 1.                                    |
| `player-1-contrast` | `#fffaf0` | —      | Blue is dark enough that only a light ink clears AA on it (see below).  |
| `player-2`          | `#FF0000` | Red    | Canonical, `color_id` 2.                                                |
| `player-2-contrast` | `#000000` | —      | Pure red sits mid-luminance; near-black ink is the side that clears AA. |
| `player-3`          | `#00FF00` | Green  | Canonical, `color_id` 3.                                                |
| `player-3-contrast` | `#000000` | —      | Bright fill; black ink.                                                 |
| `player-4`          | `#FFFF00` | Yellow | Canonical, `color_id` 4.                                                |
| `player-4-contrast` | `#000000` | —      | Brightest fill; black ink.                                              |
| `player-5`          | `#00FFFF` | Teal   | Canonical, `color_id` 5.                                                |
| `player-5-contrast` | `#000000` | —      | Bright fill; black ink.                                                 |
| `player-6`          | `#FF57B3` | Purple | Canonical, `color_id` 6.                                                |
| `player-6-contrast` | `#000000` | —      | Black ink clears AA with margin.                                        |
| `player-7`          | `#797979` | Grey   | Canonical, `color_id` 7.                                                |
| `player-7-contrast` | `#000000` | —      | Mid-grey is the tightest fill; only near-black clears AA on it.         |
| `player-8`          | `#FF9600` | Orange | Canonical, `color_id` 8.                                                |
| `player-8-contrast` | `#000000` | —      | Black ink.                                                              |

**Why seven blacks and one white.** The `-contrast` value is chosen per fill as whichever of
parchment-white (`#fffaf0`) or ink-black (`#000000`) clears the AA 4.5:1 floor for a glyph that
might sit on the chip. Blue `#405BFF` is the one fill dark enough that black ink fails (4.2:1) and
white passes (4.8:1); the other seven are bright enough that black ink passes and white fails. This
is a measured outcome, not a preference. Black is the one place this warm palette yields a neutral:
two canonical fills — mid-grey and pure red — sit at a luminance where a warm near-black
(`surface-sunken #141009`) would fall _under_ 4.5 on grey (4.35:1), so ink-black is required to hold
the floor with margin. At swatch scale (12–16px) the difference between `#000000` and a warm
near-black is imperceptible; the margin is not.

### Measured contrast (the pairs T410 asserts)

Reproduced in README's "Measured contrast pairs" section under **Player colour swatches**; the floor
each pair owes is **4.5:1** (AA normal text — the conservative choice, since a glyph on a chip could
otherwise be treated as non-text at 3:1). Computed with the same WCAG relative-luminance formula as
the rest of that table, rounded down to one decimal. Theme-invariant, so one column:

| Foreground          | Background (fill) | Ratio | Verdict |
| ------------------- | ----------------- | ----- | ------- |
| `player-1-contrast` | `player-1` Blue   | 4.8   | AA      |
| `player-2-contrast` | `player-2` Red    | 5.2   | AA      |
| `player-3-contrast` | `player-3` Green  | 15.3  | AAA     |
| `player-4-contrast` | `player-4` Yellow | 19.5  | AAA     |
| `player-5-contrast` | `player-5` Teal   | 16.7  | AAA     |
| `player-6-contrast` | `player-6` Purple | 7.2   | AA      |
| `player-7-contrast` | `player-7` Grey   | 4.8   | AA      |
| `player-8-contrast` | `player-8` Orange | 9.6   | AA      |

The frame (`border-strong` on `surface` / `surface-raised`) is already in README's table and already
asserted; T410 adds only the eight rows above.

### What T410 does with this

1. Add the sixteen tokens above to **both** blocks of `tokens/color.json`, identical values in each.
2. Extend `build-tokens.test.mjs`: assert every `player-N` has a `player-N-contrast`, and that
   `contrastRatio(player-N-contrast, player-N) >= 4.5` for all eight (a loop, like the Callout-tone
   test). No new `border-strong` assertion — the frame pairs are already covered.
3. No generator change: these ride the `color` family.

---

## Decision 2 — Close DS-7 with an icon-size family

### The gap

DS-7: no icon-size tokens; marks size from `1em` or `space-4`/`space-5`. Feature 004 adds five real
image/icon marks — `CivilisationIcon`, `MapThumbnail`, `PlayerColourSwatch`, `CountryFlag`,
`PlayerAvatar` — that need a sanctioned, shared size scale so their dimensions come from a token, not
a per-component guess (constitution VI, FR-013).

### The scale

A new **`icon`** family in a new `tokens/icon.json`, values aligned to the `space` scale (unit
`0.25rem`) so an icon and the space around it are commensurable, plus one value the touch-target rule
fixes independently. Seven steps — enough to serve all five components without a spare:

| Token      | Value            | = space step | Rationale                                                                                                                                                               |
| ---------- | ---------------- | ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `icon-xs`  | `0.75rem` (12px) | `space-3`    | Densest mark: the `PlayerColourSwatch` chip in a match row, where many sit in one line.                                                                                 |
| `icon-sm`  | `1rem` (16px)    | `space-4`    | Inline `CountryFlag` beside an alias; the smallest a glyph-bearing swatch (winner marker) stays legible.                                                                |
| `icon-md`  | `1.5rem` (24px)  | `space-6`    | Default `CivilisationIcon` in a match-history row — the common case, reads at a glance in a list.                                                                       |
| `icon-lg`  | `2rem` (32px)    | `space-8`    | `CivilisationIcon` in the match-detail panel; a compact `PlayerAvatar`.                                                                                                 |
| `icon-xl`  | `2.75rem` (44px) | — (see note) | The **interactive floor**: any icon-only control's hit area (WCAG 2.5.8, touch ≥44px). Not a space step; 44px is the accessibility constant, recorded as its own value. |
| `icon-2xl` | `4rem` (64px)    | `space-16`   | `PlayerAvatar` on the profile header; `MapThumbnail` in a dense list.                                                                                                   |
| `icon-3xl` | `6rem` (96px)    | `space-24`   | Large `MapThumbnail` in the match-detail panel; a hero avatar.                                                                                                          |

**Why `icon-xl` is 44px and not on the space grid.** The other six steps are space-scale multiples so
icon size and layout gaps share one rhythm. `icon-xl` exists for a different reason — it is the
minimum **touch target** an interactive icon must fill (WCAG 2.5.8), which is a fixed 44px, not a
design rhythm. Keeping it a named token means an icon-only button sizes its hit area from
`icon-xl` rather than a component reaching for a raw `44px`. A visually smaller interactive icon
(e.g. a 16px `FavouriteToggle`-style mark) still owes a 44px target: it renders at `icon-sm` inside a
box padded out to `icon-xl`, never a 16px hit area.

### Per-component mapping (the sizes the specs will cite)

| Component            | Default           | Larger context                           | Interactive?                                          |
| -------------------- | ----------------- | ---------------------------------------- | ----------------------------------------------------- |
| `PlayerColourSwatch` | `icon-xs` (12px)  | `icon-sm` (16px) when it carries a glyph | non-interactive; the adjacent name is the control     |
| `CountryFlag`        | `icon-sm` (16px)  | `icon-md` (24px) on the profile header   | non-interactive                                       |
| `CivilisationIcon`   | `icon-md` (24px)  | `icon-lg` (32px) in match detail         | non-interactive                                       |
| `PlayerAvatar`       | `icon-2xl` (64px) | `icon-lg` (32px) compact                 | if it links to a profile, hit area ≥ `icon-xl` (44px) |
| `MapThumbnail`       | `icon-2xl` (64px) | `icon-3xl` (96px) in match detail        | non-interactive                                       |

**Amended by T428 — `MapThumbnail` gains a third, smaller step: `icon-lg` (32px)**, used only in
`MatchRow`'s 1280 table row. No new token and no new value: 32px is the largest size that fits inside
the row's own text-driven height, so a row with a thumbnail and a row without one stay the same
height and the table's rhythm survives an uncovered map. Reasoning and the acceptance criterion that
checks it: [`map-thumbnail.md`](./map-thumbnail.md) §3 and §7.

### What T410 does with this

1. Add `tokens/icon.json` — a flat family like `radius.json` — with the seven values above.
2. Wire it into `build-tokens.mjs` the way `radius` is wired: `const icon = readJson('icon')`, an
   `iconVars()` builder, include it in `rootVars` (untheme — sizes do not change per theme), add an
   `iconTokens` block to `tokens.ts`, and a `themeEntries('size', …, 'icon')`-style mapping into the
   preset if a Tailwind `size-*` utility alias is wanted. It is **not** auto-discovered; every family
   in that generator is wired by hand.
3. Add `iconTokens` to the export list asserted in
   `build-tokens.test.mjs` ("tokens.ts exports every family…").
4. Mark DS-7 **Closed** in README's gap register (done in this change).
