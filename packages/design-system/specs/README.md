# Component specs

Written by `product-designer`, read by `implementer` before writing a component and by
`visual-reviewer` when judging one. Constitution VI: no component exists without a spec, and no
component carries a hard-coded style value.

## Index

| Spec                                                     | Component directory                                                      | Feature                      |
| -------------------------------------------------------- | ------------------------------------------------------------------------ | ---------------------------- |
| [`shared-primitives.md`](./shared-primitives.md)         | `src/components/{Button,Callout,Badge,Skeleton,Menu,StatValue}/`         | 001                          |
| [`sign-in-screen.md`](./sign-in-screen.md)               | `src/components/SignInScreen/`                                           | 001, US1                     |
| [`archival-control.md`](./archival-control.md)           | `src/components/ArchivalControl/`                                        | 001, US1/US5                 |
| [`profile-summary.md`](./profile-summary.md)             | `src/components/ProfileSummary/`                                         | 001, US1; 003, US1; 004, US2 |
| [`capture-state-badge.md`](./capture-state-badge.md)     | `src/components/CaptureStateBadge/` (grows `Badge`'s tone variants)      | 001, US3                     |
| [`match-history.md`](./match-history.md)                 | `src/components/MatchRow/`, `src/components/MatchDetailPanel/`           | 001, US3; 003, US2; 004, US1 |
| [`manual-upload.md`](./manual-upload.md)                 | `src/components/UploadControl/`                                          | 001, US4                     |
| [`privacy-notice.md`](./privacy-notice.md)               | `src/components/PrivacyNotice/`                                          | 001, US5                     |
| [`privacy-data-rights.md`](./privacy-data-rights.md)     | `src/components/DataExportPanel/`, `src/components/AccountErasurePanel/` | 001, US5                     |
| [`third-party-objection.md`](./third-party-objection.md) | `src/components/ThirdPartyObjectionForm/`                                | 001, US5                     |
| [`footer.md`](./footer.md)                               | `src/components/Footer/`                                                 | 001, US5                     |
| [`player-search.md`](./player-search.md)                 | `src/components/SearchBox/`, `src/components/PlayerResultRow/`           | 003, US1                     |
| [`replay-availability.md`](./replay-availability.md)     | `src/components/ReplayAvailabilityList/`                                 | 003, US3                     |
| [`favourite-toggle.md`](./favourite-toggle.md)           | `src/components/FavouriteToggle/`                                        | 003, US5                     |
| [`favourites-list.md`](./favourites-list.md)             | `src/components/FavouritesList/`                                         | 003, US5                     |
| [`analysis-timeline.md`](./analysis-timeline.md)         | `src/components/AnalysisTimeline/`                                       | 003, US4                     |
| [`game-asset-tokens.md`](./game-asset-tokens.md)         | player-colour + icon-size tokens (no component; `tokens/`)               | 004                          |
| [`civilisation-icon.md`](./civilisation-icon.md)         | `src/components/CivilisationIcon/`                                       | 004, US1                     |
| [`map-thumbnail.md`](./map-thumbnail.md)                 | `src/components/MapThumbnail/`                                           | 004, US1                     |
| [`player-colour-swatch.md`](./player-colour-swatch.md)   | `src/components/PlayerColourSwatch/`                                     | 004, US1                     |
| [`country-flag.md`](./country-flag.md)                   | `src/components/CountryFlag/`                                            | 004, US2                     |
| [`player-avatar.md`](./player-avatar.md)                 | `src/components/PlayerAvatar/`                                           | 004, US2                     |

## Every spec has nine sections

Purpose, Anatomy, Variants and sizes, States, Tokens used, Spacing, Responsive, Accessibility,
Visual acceptance criteria. A spec missing one is incomplete, and "this component has no empty
state" is a design bug, not an exemption.

The state vocabulary is closed: **default, hover, focus-visible, active, disabled, loading, error,
empty**. Every spec answers all eight, even when the answer is "this part is never disabled;
disabling it would be wrong, and here is what happens instead".

## Rules that apply to every spec here

1. **Numbers before atmosphere.** This is a data tool people consult quickly. Where legibility and
   decoration conflict, legibility wins without discussion. No texture, gradient, glow or border
   ornament may sit behind or across a numeric value. No number animates on entry — a count-up
   delays reading to no benefit.
2. **Tokens only.** Colour, spacing, radius, typography, elevation and motion come from
   `packages/design-system/tokens`. Where a needed token does not exist, this directory says so in
   the gap register below and names the interim; a spec never publishes a raw value for a component
   to copy.
3. **No game asset without a recorded licence.** No civilisation icon, portrait, font, sound or
   screenshot from Age of Empires II may sit in the repository **without a `LICENCE.md` recording its
   source and permitted usage** (constitution X 5.0.0; feature 004 D3/D4). The visual language —
   parchment, stone, bronze, illuminated hierarchy — is original drawing and free- or GCUR-licensed
   assets only; the boundary is the licence record, not the absence of the asset. Every non-text mark
   a component uses records its origin in the component's spec.
4. **Colour is never the only carrier of meaning.** Win/loss, success/failure, primary/non-primary,
   and a player's colour all carry a text or shape signal alongside the colour — a `PlayerColourSwatch`
   always sits beside the player's name.
5. **Reduced motion is a real state.** Under `prefers-reduced-motion: reduce`, every transition uses
   `motion.duration.instant` and every looping animation (skeleton pulse above all) stops on its
   resting frame.
6. **Theme-blind components.** Light and dark share token names. A component never branches on the
   active theme, and every contrast obligation is met in both.

## Measured contrast pairs

Computed 2026-08-20, updated 2026-08-21 after T038a's fix and again after T034c's, from
`tokens/color.json` with the WCAG 2.2 relative-luminance formula, rounded down to one decimal, and
asserted in `tokens/build-tokens.test.mjs` for the pairs that carry an accessibility floor — a
colour edit now fails a test rather than depending on this table being re-read. **Component specs
reference this table by pair; they do not restate the numbers.** Recompute on any change to
`color.json` — the numbers below are the only reason the accessibility sections elsewhere can be
short.

Thresholds: 4.5:1 for normal text, 3:1 for text at 24px+ (or 18.7px+ bold) and for the boundary,
fill or icon of any interactive control (WCAG 1.4.3 and 1.4.11).

**Pairing convention (T034c).** A row in this table names a foreground **and the background the
component that carries it actually paints behind it** — never the background that happens to be
"the" surface for that token elsewhere in the system. `border-strong` boundaries a `Button` or
`Menu` control, and those controls are placed directly on `background` (`ConsentStep`'s decline
control), on `surface` (`SignInScreen`'s card), and on `surface-raised` (any secondary `Button`
inside a `Callout`) in different parts of the product — so it has three rows, not one, and the
lowest of the three is the one that decides whether the token passes. `warning`, `info`, `success`
and `danger` all colour `Callout` text, and `Callout` is unconditionally `bg-surface-raised`
(`src/components/Callout/index.tsx`) regardless of what sits behind the callout itself — so those
four have exactly one row each, against `surface-raised`, and a row against plain `surface` would
be asserting a pair no component draws. Before adding or changing a row: find every component that
actually renders the token, per file, and list the background each one paints behind it — the
table is derived from usage, not from which background is conventionally "the" one for a token.

### Light theme

| Foreground        | Background       | Ratio | Verdict                                                                      |
| ----------------- | ---------------- | ----- | ---------------------------------------------------------------------------- |
| `text-primary`    | `surface`        | 15.3  | AAA                                                                          |
| `text-primary`    | `surface-raised` | 14.5  | AAA                                                                          |
| `text-primary`    | `background`     | 13.5  | AAA                                                                          |
| `text-primary`    | `surface-sunken` | 11.7  | AAA                                                                          |
| `text-secondary`  | `surface`        | 6.2   | AA                                                                           |
| `text-secondary`  | `surface-raised` | 5.9   | AA                                                                           |
| `text-secondary`  | `background`     | 5.5   | AA                                                                           |
| `text-secondary`  | `surface-sunken` | 4.7   | AA, thin margin                                                              |
| `info`            | `surface`        | 6.7   | AA                                                                           |
| `danger`          | `surface`        | 6.5   | AA                                                                           |
| `success`         | `surface`        | 5.9   | AA                                                                           |
| `focus-ring`      | `surface`        | 6.7   | passes non-text 3:1                                                          |
| `focus-ring`      | `background`     | 5.9   | passes non-text 3:1                                                          |
| `warning`         | `surface`        | 4.7   | AA, but no component renders this pair — see `surface-raised` below          |
| `warning`         | `surface-raised` | 4.5   | AA — the real `Callout` heading pair (T034c)                                 |
| `info`            | `surface-raised` | 6.3   | AA — the real `Callout` heading pair (T034c)                                 |
| `success`         | `surface-raised` | 5.6   | AA — the real `Callout` heading pair (T034c)                                 |
| `danger`          | `surface-raised` | 6.2   | AA — the real `Callout` heading pair (T034c)                                 |
| `accent`          | `surface`        | 4.9   | AA — passes normal text too now; still only used for large text and non-text |
| `accent-contrast` | `accent`         | 4.9   | AA — fixed, gap DS-1 closed                                                  |
| `accent-contrast` | `accent-hover`   | 6.7   | AA                                                                           |
| `accent-contrast` | `accent-active`  | 9.3   | AA                                                                           |
| `border-strong`   | `background`     | 3.1   | passes non-text 3:1 — the `ConsentStep` decline control's real pair (T034c)  |
| `border-strong`   | `surface`        | 3.5   | passes non-text 3:1 — fixed, gap DS-2 closed; re-measured after T034c        |
| `border-strong`   | `surface-raised` | 3.4   | passes non-text 3:1 — a secondary `Button` inside a `Callout` (T034c)        |
| `border`          | `surface`        | 1.6   | decorative separators only, never a control boundary                         |
| `text-disabled`   | `surface`        | 2.6   | exempt (1.4.3, inactive) — see rule under DS-3                               |

### Dark theme

| Foreground            | Background       | Ratio | Verdict                                                                     |
| --------------------- | ---------------- | ----- | --------------------------------------------------------------------------- |
| `text-primary`        | `surface`        | 13.3  | AAA                                                                         |
| `text-primary`        | `surface-raised` | 12.0  | AAA                                                                         |
| `text-secondary`      | `surface`        | 7.8   | AAA                                                                         |
| `text-secondary`      | `surface-raised` | 7.1   | AAA                                                                         |
| `accent-contrast`     | `accent`         | 8.2   | AA                                                                          |
| `accent`              | `surface`        | 7.7   | AA (unlike light — `accent` is legible as body text here)                   |
| `warning`             | `surface`        | 6.8   | AA, but no component renders this pair — see below                          |
| `warning`             | `surface-raised` | 6.2   | AA — the real `Callout` heading pair (T034c)                                |
| `info`                | `surface-raised` | 5.7   | AA — the real `Callout` heading pair (T034c)                                |
| `success`             | `surface-raised` | 5.8   | AA — the real `Callout` heading pair (T034c)                                |
| `danger`              | `surface-raised` | 4.6   | AA — the real `Callout` heading pair (T034c), thin margin                   |
| `success`             | `surface`        | 6.4   | AA                                                                          |
| `focus-ring` / `info` | `surface`        | 6.3   | AA, passes non-text 3:1                                                     |
| `danger`              | `surface`        | 5.1   | AA                                                                          |
| `border-strong`       | `background`     | 4.0   | passes non-text 3:1 — the `ConsentStep` decline control's real pair (T034c) |
| `border-strong`       | `surface`        | 3.8   | passes non-text 3:1 — fixed, gap DS-2 closed                                |
| `border-strong`       | `surface-raised` | 3.4   | passes non-text 3:1 — a secondary `Button` inside a `Callout` (T034c)       |

The asymmetry is the thing to remember: **the dark theme is comfortable and the light theme is
tight.** Every light-theme pair above now clears the normal-text floor it owes — see the rule below
the gap register for `warning`'s history. Judge light first.

**One pair a component draws and this table does not yet carry**: `text-secondary` on `background`
in the **dark** theme. `ProfileSummary`'s root is `bg-background`, so its country label, profile id
and freshness line render that pair in both themes; the light row is above, the dark one is not.
Dark `background` is darker than dark `surface`, so the pair is no tighter than the measured 7.8
`surface` row and nothing is blocked on it — but per the pairing convention above, an unmeasured
pair is not an asserted one. Add the row the next time this table is recomputed
(`profile-summary.md` §12.8).

### Player colour swatches (feature 004, T410)

**Theme-invariant** — a player's colour is their identity and does not re-tint per theme, so the
`player-N` fill and its `player-N-contrast` ink carry one value in both theme blocks of `color.json`
and the ratio is the same in both themes (full decision and rationale:
[`game-asset-tokens.md`](./game-asset-tokens.md)). Each pair owes **4.5:1** — a glyph on a swatch is
treated as normal text, the conservative floor — and `build-tokens.test.mjs` asserts all eight.

| Foreground          | Background (fill) | Ratio | Verdict                                            |
| ------------------- | ----------------- | ----- | -------------------------------------------------- |
| `player-1-contrast` | `player-1` Blue   | 4.8   | AA — Blue is the one fill that needs the light ink |
| `player-2-contrast` | `player-2` Red    | 5.2   | AA                                                 |
| `player-3-contrast` | `player-3` Green  | 15.3  | AAA                                                |
| `player-4-contrast` | `player-4` Yellow | 19.5  | AAA                                                |
| `player-5-contrast` | `player-5` Teal   | 16.7  | AAA                                                |
| `player-6-contrast` | `player-6` Purple | 7.2   | AA                                                 |
| `player-7-contrast` | `player-7` Grey   | 4.8   | AA — mid-grey is the tightest fill                 |
| `player-8-contrast` | `player-8` Orange | 9.6   | AA                                                 |

Every swatch is drawn with a 1px **`border-strong` frame** so a pale fill (Yellow, Green, Teal)
stays a distinct chip against the light parchment without the canonical hex being distorted per
theme. That frame's boundary is the existing `border-strong` rows above (3.5 on `surface`, 3.4 on
`surface-raised` in light), already asserted; the swatch adds no new frame assertion. An out-of-range
or `NULL` `color_id` renders a `surface-sunken` fill inside the same frame, with the player's name
carrying the meaning (rule 4). The component that draws it, and the states it owes, are in
[`player-colour-swatch.md`](./player-colour-swatch.md).

## Token gap register

Open items. Each names what is missing, what a component does until it exists, and who has to act.
An implementer who finds themselves needing a value not covered here stops and asks
`product-designer`; they do not invent one.

| Id       | Gap                                                                                                   | Impact                                                                                 | Interim                                                                                                                                                                                                                                        | Action owed                                                                                                                                                                                                                                                                                                                 |
| -------- | ----------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **DS-3** | No opacity token family.                                                                              | Disabled styling has no sanctioned dimming route.                                      | Disabled state is expressed with `text-disabled` on `surface-sunken` with `border`, never with an opacity value. `text-disabled` fails AA by design; a disabled control must therefore never be the only place a piece of information appears. | Decide whether an opacity family is wanted at all. Low priority: the colour route is better.                                                                                                                                                                                                                                |
| **DS-4** | No border-width, focus-ring-width or focus-ring-offset tokens.                                        | The focus ring — required on every interactive element — cannot be fully token-backed. | One uniform ring everywhere: Tailwind's `outline-2 outline-offset-2` with `outline-focus-ring`. No arbitrary values, no per-component variation.                                                                                               | Ratify Tailwind's built-in width scale as token-equivalent for hairlines and rings, and record that decision, **or** add a `border-width` family. Owner: design-system.                                                                                                                                                     |
| **DS-5** | No breakpoint tokens.                                                                                 | Responsive sections cannot name breakpoints in our own vocabulary.                     | Specs name Tailwind's default breakpoints (`md` = 768px, `lg` = 1024px, `xl` = 1280px) and the review viewports stay 375 / 768 / 1280.                                                                                                         | Optional. Adopting Tailwind's defaults verbatim is a defensible answer; write it down either way.                                                                                                                                                                                                                           |
| **DS-6** | No container / max-width / reading-measure tokens.                                                    | Text columns and centred panels have no token-backed width.                            | Tailwind's `max-w-*` scale, and `max-w-prose` for any paragraph column.                                                                                                                                                                        | Add a `size` family if panel widths start diverging between routes.                                                                                                                                                                                                                                                         |
| **DS-8** | No numeric-typography role. Tabular alignment currently rides on `font.family.mono` being monospaced. | A future change of mono family silently breaks column alignment on every rating table. | Numeric cells use `font-mono`.                                                                                                                                                                                                                 | Add a `font.role.numeric` alias, or a `font-variant-numeric: tabular-nums` utility, so the intent is recorded rather than inferred. Number legibility is this product's functional priority; it should not depend on a coincidence.                                                                                         |
| **DS-9** | No link colour role, and `accent` on `surface-raised` is not in the measured contrast table.          | Long-form prose with inline links has no sanctioned link colour on every background.   | Inline links use `accent` with a permanent underline, **on `surface` only** — the one pair measured (4.9 light / 7.7 dark). A link that would sit on `surface-raised` renders `text-primary` with an underline instead. Never colour alone.    | Add a `link` / `link-hover` / `link-visited` role, **or** measure `accent` on `surface-raised` and `surface-sunken` and add the rows. Raised by `privacy-notice.md`, the first component whose body copy is mostly prose with links in it. Owner: design-system. Until then no component paints a link on a raised surface. |

`tokens/build-tokens.test.mjs` now asserts the pairs in the measured contrast table above that
carry an accessibility floor, so a colour edit that breaks AA fails a test rather than depending on
this table being re-read (T034a, corrected by T038a and T034c below).

**Closed — DS-1 and DS-2.** Light `accent` was too light to carry `accent-contrast` at AA, and
`border-strong` missed the 3:1 non-text floor against `surface` in both themes. T034a darkened
light `accent` and re-derived `accent-hover` / `accent-active` beneath it — rest, hover and active
stay three distinct colours, never collapsed onto one another — and darkened light `border-strong`
while lightening dark `border-strong`. The interim workarounds this register used to describe (the
solid primary button filling with `accent-hover` at rest in the light theme; `text-secondary`
never substituted for `border-strong`) no longer apply anywhere: every component builds against
the real tokens from here on. See the measured contrast table above for the resulting ratios. The
ids are kept rather than renumbered, so that this register and the commit history still line up
with the defects they describe. T034b has removed the DS-1 and DS-2 citations from
`shared-primitives.md`, `sign-in-screen.md`, `consent-step.md` and `profile-summary.md`, including
the button table that had encoded the interim as the design; the gaps those files still list are
the ones genuinely open.

**Closed — DS-7 (feature 004).** There was no icon-size token family; marks sized from `1em` or
`space-4`/`space-5`. Feature 004's five image/icon marks — `CivilisationIcon`, `MapThumbnail`,
`PlayerColourSwatch`, `CountryFlag`, `PlayerAvatar` — need a shared, sanctioned scale. A new **`icon`**
family (`tokens/icon.json`, seven steps `icon-xs`…`icon-3xl`) closes it: six steps are `space`-scale
multiples so icon size and layout gaps share one rhythm, and `icon-xl` is fixed at 44px as the WCAG
2.5.8 touch-target floor an interactive icon must fill. Values, per-component mapping, and the
generator wiring T410 owes (it is hand-wired like `radius`, not auto-discovered) are in
[`game-asset-tokens.md`](./game-asset-tokens.md). The id is kept rather than renumbered so this
register and the commit history line up with the gap it describes.

**Closed — light `warning` (T038a).** `warning` colours only the stripe and the heading of a
callout, never its body: callout body text is always `text-primary`. That structural rule is
T034's and is unchanged. T034a then asserted the pair against the 3:1 large-text/non-text floor, on
the stated basis that `warning` never carries normal-size text — but `Callout`'s heading renders at
16px, weight 600 (`font-sans text-md font-semibold`,
`src/components/Callout/index.tsx`), and WCAG's large-text allowance needs 24px, or 18.66px at
weight 700 and above. The heading is normal-size text, so this pair owes 4.5:1 like any other, and
4.1:1 sat under it. T038a darkened light `warning` within its own hue, the same way T034a darkened
`accent` for DS-1, to 4.7:1 — clearing the floor with a margin rather than sitting on it — and
raised the assertion in `tokens/build-tokens.test.mjs` to the 4.5:1 this pair actually owes. Light
`warning-contrast` on `warning` moved from 3.99:1 to 3.47:1 as a side effect of the darkening; that
pairing carries no component today (grep finds no use of it under `src/`), so it needed no
correction, but it is not clear of even the 3:1 non-text floor and must be re-derived before
anything is built against it.

**Closed — T034c.** Both DS-2 and T038a's `warning` fix named a real pair — `border-strong` on
`surface`, `warning` on `surface` — that was nonetheless not the one any component draws. `Button`'s
`secondary`/`ghost`/`destructive` variants and `Menu`'s trigger place `border-strong` on
`background` (`ConsentStep`'s decline control, via `DashboardContainer`'s `<main
className="bg-background">`) and on `surface-raised` (a secondary `Button` inside a `Callout`) just
as often as on `surface`, and the `background` pair measured 2.99:1 in the light theme — under the
3:1 floor, on the control FR-034 requires be genuinely declinable. `warning` colours only `Callout`
text, and `Callout` is unconditionally `bg-surface-raised`, never `surface`; the real pair measured
4.52:1 — over the 4.5:1 floor, but by two hundredths, none of which the `surface` assertion's 4.75:1
reading could have shown. This is the third contrast defect of the same shape: an assertion correct
about the pair it names, wrong about which pair the component renders.

Light `border-strong` moved from `#a28453` to `#9d8050` — darkened within its own hue, the same
move T034a and T038a made — so the `background` pair clears 3:1 with a small margin (3.16:1) rather
than sitting under it; the `surface` and `surface-raised` pairs, already passing, gained margin as a
side effect. `warning` needed no colour change: the real pair already clears its floor, if only
just, so `tokens/build-tokens.test.mjs` now asserts it against `surface-raised` instead of moving
the colour again. `info`, `success` and `danger` colour the same `Callout` heading role and carried
no assertion at all before this task; all three clear 4.5:1 against `surface-raised` in both themes
without a colour change (dark `danger` is the tightest, at 4.6:1, and should be watched the next
time `danger` or `surface-raised` moves).

The pairing convention above — assert a token against every background a component actually paints
behind it, found by reading the component — is what this task adds structurally, precisely so a
fourth instance of this defect has to fail a test that already exists rather than waiting for a
fourth review to notice by hand.

Recapturing note: light `border-strong`'s change is a few points darker on every secondary `Button`
and `Menu` trigger border, in both light-theme contexts. The Storybook baselines for `Button`,
`Menu` and any story that renders a secondary/ghost/destructive control or a menu trigger in the
light theme should be treated as needing a recapture; this task does not attempt it.
