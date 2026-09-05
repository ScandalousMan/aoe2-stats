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
| [`country-flag.md`](./country-flag.md)                   | `src/components/CountryFlag/`                                            | 004, US2; 004, Phase 8       |
| [`player-avatar.md`](./player-avatar.md)                 | `src/components/PlayerAvatar/`                                           | 004, US2                     |
| [`site-header.md`](./site-header.md)                     | `src/components/SiteHeader/`                                             | 004, US3                     |
| [`tooltip.md`](./tooltip.md)                             | `src/components/Tooltip/`                                                | 004, Phase 8                 |

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
   always sits beside the player's name. **Imagery is not either**: a mark whose fact is not
   permanently painted beside it must reach that fact three ways — hover, keyboard focus and press —
   and must carry it in the accessibility tree at all times, whether the reveal has ever fired or not
   ([`tooltip.md`](./tooltip.md) §2, [`country-flag.md`](./country-flag.md) §11.3). That is the only
   sanctioned exception, and it is one component wide.
5. **Reduced motion is a real state.** Under `prefers-reduced-motion: reduce`, every transition uses
   `motion.duration.instant` and every looping animation (skeleton pulse above all) stops on its
   resting frame.
6. **Theme-blind components.** Light and dark share token names. A component never branches on the
   active theme, and every contrast obligation is met in both.
7. **The three review widths are 375, 768 and 1280** (mobile, tablet, desktop) — FR-018's system
   declaration of where the suite verifies correctness, and the one place that declaration lives
   (closes DS-5, T529). They are not the `breakpoint` family (`tokens/breakpoint.json`'s `sm`/`md`/
   `lg`/`xl` = 640/768/1024/1280): two of the four values happen to coincide (768, 1280) but 375 is
   not a breakpoint at all, and a structural switch in a component still reads `breakpoint.json`
   alone. `scripts/visual/run.mjs`'s `WIDTHS` constant names this rule as its source in a comment, so
   the number is written once in prose and once, necessarily, as the array a runner has to iterate.

## Measured contrast pairs

Computed 2026-08-20, updated 2026-08-21 after T038a's fix and again after T034c's, and **recomputed
2026-09-05 (T526)** from scratch against the T521/T522 re-derivation (`color-tokens.md`), which
replaced every value in `color.json` and added the `link` / `link-hover` / `link-visited` roles.
Computed with the WCAG 2.2 relative-luminance formula from the hexes in `tokens/color.json`,
rounded to two decimals, and asserted in `tokens/build-tokens.test.mjs` for every pair that carries
an accessibility floor — a colour edit now fails a test rather than depending on this table being
re-read. **Component specs reference this table by pair; they do not restate the numbers.**
Recompute on any change to `color.json` — the numbers below are the only reason the accessibility
sections elsewhere can be short.

Thresholds: 4.5:1 for normal text, 3:1 for text at 24px+ (or 18.7px+ bold) and for the boundary,
fill or icon of any interactive control (WCAG 1.4.3 and 1.4.11).

**Pairing convention (T034c).** A row in this table names a foreground **and the background the
component that carries it actually paints behind it** — never the background that happens to be
"the" surface for that token elsewhere in the system. `border-strong` boundaries a `Button` or
`Menu` control, and those controls are placed directly on `background` (`ConsentStep`'s decline
control), on `surface` (`SignInScreen`'s card, `Menu`'s trigger fill), on `surface-raised` (any
secondary `Button` inside a `Callout`) **and now on `surface-sunken`** (the `PlayerAvatar` /
`PlayerColourSwatch` frame drawn around an out-of-range swatch's `surface-sunken` fill) — so it has
four rows, not one, and the lowest of the four is the one that decides whether the token passes.
`warning` and `info` colour `Callout`/`Badge` text only, and both are unconditionally
`bg-surface-raised` regardless of what sits behind them — so those two have exactly one row each,
against `surface-raised`, and a row against plain `surface` would be asserting a pair no component
draws. Before adding or changing a row: find every component that actually renders the token, per
file, and list the background each one paints behind it — the table is derived from usage, not from
which background is conventionally "the" one for a token.

**T526's own catch, recorded so the next reader does not have to re-derive it.** T522 moved
`PrivacyNotice`, `Footer`, `ThirdPartyObjectionForm` and `AccountErasurePanel`'s inline links off
`accent` / `accent-hover` onto `link` / `link-hover` (`color-tokens.md` §11.6). That retired the only
call sites that had painted `accent` on `background`, and the only call site that had painted
`accent-hover` as an ink at all: reading `packages/design-system/src` today finds `accent-hover` used
only as a fill (`hover:bg-accent-hover` in `Button` and `DataExportPanel`, already covered by the
`accent-contrast` / `accent-hover` row below) and finds no `text-accent`/`text-accent-hover` on
`background` anywhere. The `accent` on `background` and `accent-hover` on `surface` rows this table
used to carry are **removed rather than recomputed**, for the exact reason this section exists to
enforce: a row asserted against a pair no component paints is the defect this repository keeps
re-discovering, not a courtesy to keep around. `accent`'s two remaining real pairs are `SiteHeader`'s
current-tab underline on `surface` (drawn in both themes) and `Badge`'s accent tone, which resolves
to `text-accent` on `surface-raised` in **dark** and `text-accent-active` on `surface-raised` in
**light** (`src/components/Badge/index.tsx`) — never the other role in the other theme, which is why
each is asserted in one theme only below rather than both.

### Light theme

| Foreground         | Background               | Ratio | Verdict                                                                                                                               |
| ------------------ | ------------------------ | ----- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `text-primary`     | `surface-raised`         | 16.54 | AAA                                                                                                                                   |
| `text-primary`     | `surface`                | 15.46 | AAA                                                                                                                                   |
| `text-primary`     | `background`             | 13.78 | AAA                                                                                                                                   |
| `text-primary`     | `surface-sunken`         | 11.64 | AAA                                                                                                                                   |
| `text-secondary`   | `surface-raised`         | 8.21  | AAA                                                                                                                                   |
| `text-secondary`   | `surface`                | 7.67  | AAA                                                                                                                                   |
| `text-secondary`   | `background`             | 6.84  | AA — `ProfileSummary`'s profile id / freshness line                                                                                   |
| `text-secondary`   | `surface-sunken`         | 5.78  | AA (was 4.7, "thin margin")                                                                                                           |
| `text-disabled`    | `surface-raised`         | 4.40  | exempt (1.4.3, inactive) — held to 3:1 by design                                                                                      |
| `text-disabled`    | `surface`                | 4.11  | exempt; clears 3:1                                                                                                                    |
| `text-disabled`    | `background`             | 3.66  | exempt; clears 3:1                                                                                                                    |
| `text-disabled`    | `surface-sunken`         | 3.10  | exempt; clears 3:1 — the real disabled-`Button` pair                                                                                  |
| `border`           | `surface-raised`         | 2.91  | decorative — `Menu` panel, `Tooltip`                                                                                                  |
| `border`           | `surface`                | 2.72  | decorative (was 1.6)                                                                                                                  |
| `border`           | `background`             | 2.43  | decorative — `MatchRow`'s table row separator                                                                                         |
| `border`           | `surface-sunken`         | 2.05  | decorative — a disabled control's edge, deliberately the faintest                                                                     |
| `border-strong`    | `surface-raised`         | 5.16  | passes non-text 3:1 — a secondary `Button` inside a `Callout`                                                                         |
| `border-strong`    | `surface`                | 4.82  | passes non-text 3:1 — `SignInScreen`'s card, `Menu`'s trigger                                                                         |
| `border-strong`    | `background`             | 4.30  | passes non-text 3:1 — `ConsentStep`'s decline control (T034c)                                                                         |
| `border-strong`    | `surface-sunken`         | 3.63  | passes non-text 3:1 — the `PlayerAvatar` / `PlayerColourSwatch` frame                                                                 |
| `accent`           | `surface`                | 5.67  | AA — `SiteHeader`'s current-tab underline (non-text; comfortably clears the text floor too)                                           |
| `accent-active`    | `surface-raised`         | 9.78  | AA — `Badge` accent tone, **light theme only** (dark paints `accent` there instead, below)                                            |
| `accent-contrast`  | `accent`                 | 6.07  | AA — `Button` primary's label, `DataExportPanel`'s download label, and (DS-10 closed, `color-tokens.md` §5) its own inward focus ring |
| `accent-contrast`  | `accent-hover`           | 7.65  | AA — the same label/ring, hover fill                                                                                                  |
| `accent-contrast`  | `accent-active`          | 9.78  | AA — the same label/ring, press fill                                                                                                  |
| `warning`          | `surface-raised`         | 7.06  | AA — the real `Callout` / `Badge` heading pair (was 4.52, "two hundredths")                                                           |
| `info`             | `surface-raised`         | 7.30  | AA — the real `Callout` / `Badge` heading pair                                                                                        |
| `success`          | `surface-raised`         | 7.25  | AA — the real `Callout` / `Badge` heading pair                                                                                        |
| `danger`           | `surface-raised`         | 7.21  | AA — the real `Callout` / `Badge` heading pair                                                                                        |
| `success`          | `surface`                | 6.77  | AA — `MatchRow` win text                                                                                                              |
| `success`          | `surface-sunken`         | 5.10  | AA — `MatchRow` win text, row hovered                                                                                                 |
| `success`          | `background`             | 6.04  | AA — `ProfileSummary` delta                                                                                                           |
| `danger`           | `surface`                | 6.74  | AA — `MatchRow` loss text, `Button` destructive border, `ThirdPartyObjectionForm`'s error border                                      |
| `danger`           | `surface-sunken`         | 5.07  | AA — `MatchRow` loss text, row hovered                                                                                                |
| `danger`           | `background`             | 6.00  | AA — `ProfileSummary` delta                                                                                                           |
| `success-contrast` | `success`                | 7.25  | AA                                                                                                                                    |
| `warning-contrast` | `warning`                | 7.06  | AA (was 3.47, under even the non-text floor)                                                                                          |
| `danger-contrast`  | `danger`                 | 7.21  | AA                                                                                                                                    |
| `info-contrast`    | `info`                   | 7.30  | AA                                                                                                                                    |
| `focus-ring`       | `surface-raised`         | 8.05  | passes non-text 3:1                                                                                                                   |
| `focus-ring`       | `surface`                | 7.52  | passes non-text 3:1                                                                                                                   |
| `focus-ring`       | `background`             | 6.70  | passes non-text 3:1                                                                                                                   |
| `focus-ring`       | `surface-sunken`         | 5.66  | passes non-text 3:1 — `UploadControl`'s drag-over border                                                                              |
| `link`             | `surface-raised`         | 7.17  | AA — `ContactBlock`'s contact route (`PrivacyNotice`)                                                                                 |
| `link`             | `surface`                | 6.70  | AA — `PrivacyNotice` inline links and `Contents`                                                                                      |
| `link`             | `background`             | 5.97  | AA — `Footer`                                                                                                                         |
| `link`             | `surface-sunken`         | 5.05  | AA — a link inside a hovered `MatchRow`                                                                                               |
| `link-hover`       | `surface-raised`         | 9.02  | AA                                                                                                                                    |
| `link-hover`       | `surface`                | 8.43  | AA                                                                                                                                    |
| `link-hover`       | `background`             | 7.51  | AA                                                                                                                                    |
| `link-hover`       | `surface-sunken`         | 6.35  | AA                                                                                                                                    |
| `link-visited`     | `surface-raised`         | 7.92  | AA — cannot be observed in a real render (`color-tokens.md` §11.7); verified by a token-swatch story                                  |
| `link-visited`     | `surface`                | 7.40  | AA — same caveat                                                                                                                      |
| `link-visited`     | `background`             | 6.59  | AA — same caveat                                                                                                                      |
| `link-visited`     | `surface-sunken`         | 5.57  | AA — same caveat                                                                                                                      |
| `text-inverse`     | `text-primary` (as fill) | 13.78 | AAA — no call site today; retained rather than removed (note below the table)                                                         |

### Dark theme

| Foreground         | Background               | Ratio | Verdict                                                                                                                |
| ------------------ | ------------------------ | ----- | ---------------------------------------------------------------------------------------------------------------------- |
| `text-primary`     | `surface-raised`         | 11.79 | AAA                                                                                                                    |
| `text-primary`     | `surface`                | 13.42 | AAA                                                                                                                    |
| `text-primary`     | `background`             | 14.64 | AAA                                                                                                                    |
| `text-primary`     | `surface-sunken`         | 15.66 | AAA                                                                                                                    |
| `text-secondary`   | `surface-raised`         | 7.19  | AAA                                                                                                                    |
| `text-secondary`   | `surface`                | 8.19  | AAA                                                                                                                    |
| `text-secondary`   | `background`             | 8.93  | AAA — **the `ProfileSummary` pair this table never carried until now**                                                 |
| `text-secondary`   | `surface-sunken`         | 9.55  | AAA                                                                                                                    |
| `text-disabled`    | `surface-raised`         | 3.39  | exempt (1.4.3, inactive); clears 3:1 by design                                                                         |
| `text-disabled`    | `surface`                | 3.85  | exempt; clears 3:1                                                                                                     |
| `text-disabled`    | `background`             | 4.21  | exempt; clears 3:1                                                                                                     |
| `text-disabled`    | `surface-sunken`         | 4.50  | exempt; clears 3:1 — the real disabled-`Button` pair                                                                   |
| `border`           | `surface-raised`         | 2.25  | decorative — `Menu` panel, `Tooltip`                                                                                   |
| `border`           | `surface`                | 2.56  | decorative                                                                                                             |
| `border`           | `background`             | 2.79  | decorative — `MatchRow`'s table row separator                                                                          |
| `border`           | `surface-sunken`         | 2.98  | decorative                                                                                                             |
| `border-strong`    | `surface-raised`         | 4.18  | passes non-text 3:1 — a secondary `Button` inside a `Callout`                                                          |
| `border-strong`    | `surface`                | 4.75  | passes non-text 3:1 — `SignInScreen`'s card, `Menu`'s trigger                                                          |
| `border-strong`    | `background`             | 5.19  | passes non-text 3:1 — `ConsentStep`'s decline control (T034c)                                                          |
| `border-strong`    | `surface-sunken`         | 5.55  | passes non-text 3:1 — the `PlayerAvatar` / `PlayerColourSwatch` frame                                                  |
| `accent`           | `surface`                | 7.39  | AA — `SiteHeader`'s current-tab underline                                                                              |
| `accent`           | `surface-raised`         | 6.50  | AA — `Badge` accent tone, **dark theme only** (light paints `accent-active` there instead, above)                      |
| `accent-contrast`  | `accent`                 | 8.07  | AA — `Button` primary's label, `DataExportPanel`'s download label, and its own inward focus ring                       |
| `accent-contrast`  | `accent-hover`           | 10.06 | AAA — the same label/ring, hover fill                                                                                  |
| `accent-contrast`  | `accent-active`          | 6.39  | AA — the same label/ring, press fill                                                                                   |
| `warning`          | `surface-raised`         | 6.11  | AA — the real `Callout` / `Badge` heading pair                                                                         |
| `info`             | `surface-raised`         | 5.89  | AA — the real `Callout` / `Badge` heading pair                                                                         |
| `success`          | `surface-raised`         | 6.15  | AA — the real `Callout` / `Badge` heading pair                                                                         |
| `danger`           | `surface-raised`         | 5.95  | AA — the real `Callout` / `Badge` heading pair (was 4.6, the tightest dark pair in the old table)                      |
| `success`          | `surface`                | 7.00  | AA                                                                                                                     |
| `success`          | `surface-sunken`         | 8.17  | AA                                                                                                                     |
| `success`          | `background`             | 7.64  | AA                                                                                                                     |
| `danger`           | `surface`                | 6.77  | AA                                                                                                                     |
| `danger`           | `surface-sunken`         | 7.90  | AA                                                                                                                     |
| `danger`           | `background`             | 7.38  | AA                                                                                                                     |
| `success-contrast` | `success`                | 7.64  | AA (`color-tokens.md` states 8.2; recomputed from the shipped hexes it is 7.64 — see the gap register's rounding note) |
| `warning-contrast` | `warning`                | 7.59  | AA                                                                                                                     |
| `danger-contrast`  | `danger`                 | 7.38  | AA                                                                                                                     |
| `info-contrast`    | `info`                   | 7.31  | AA                                                                                                                     |
| `focus-ring`       | `surface-raised`         | 5.37  | passes non-text 3:1                                                                                                    |
| `focus-ring`       | `surface`                | 6.10  | passes non-text 3:1                                                                                                    |
| `focus-ring`       | `background`             | 6.66  | passes non-text 3:1                                                                                                    |
| `focus-ring`       | `surface-sunken`         | 7.12  | passes non-text 3:1                                                                                                    |
| `link`             | `surface-raised`         | 6.05  | AA — `ContactBlock`'s contact route (`PrivacyNotice`)                                                                  |
| `link`             | `surface`                | 6.88  | AA — `PrivacyNotice` inline links and `Contents`                                                                       |
| `link`             | `background`             | 7.51  | AA — `Footer`                                                                                                          |
| `link`             | `surface-sunken`         | 8.03  | AA — a link inside a hovered `MatchRow`                                                                                |
| `link-hover`       | `surface-raised`         | 7.59  | AA                                                                                                                     |
| `link-hover`       | `surface`                | 8.63  | AA                                                                                                                     |
| `link-hover`       | `background`             | 9.42  | AAA                                                                                                                    |
| `link-hover`       | `surface-sunken`         | 10.08 | AAA                                                                                                                    |
| `link-visited`     | `surface-raised`         | 5.47  | AA — cannot be observed in a real render (`color-tokens.md` §11.7); verified by a token-swatch story                   |
| `link-visited`     | `surface`                | 6.23  | AA — same caveat                                                                                                       |
| `link-visited`     | `background`             | 6.80  | AA — same caveat                                                                                                       |
| `link-visited`     | `surface-sunken`         | 7.27  | AA — same caveat                                                                                                       |
| `text-inverse`     | `text-primary` (as fill) | 14.64 | AAA — no call site today                                                                                               |

**The asymmetry this table used to record — "the dark theme is comfortable and the light theme is
tight" — no longer holds, and it is retired here rather than kept as a stale claim.** Every
light-theme pair above clears its floor with real margin; the tightest normal-text pair in the
**whole system, in either theme,** is now light `link` on `surface-sunken` at **5.05** — `accent` on
`background` held that title in the derivation record, but that row is retired above because no
component paints it any more (see the catch note before the tables). Dark's tightest is
`link-visited` on `surface-raised` at 5.47, itself comfortably clear. "Judge light first" is still
good advice — light's margins remain the narrower of the two — but the reason it used to be true (a
system-wide near-failure sitting in the light theme) is gone.

**`link-visited` cannot be verified from a story of real anchors.** Browsers restrict `:visited`
styling and `getComputedStyle` deliberately reports the unvisited colour, so neither Playwright nor
Storybook can force or measure the state — the same blindness the suite already has for focus, one
step worse. Its rows above are guaranteed by the asserted token pairs (`build-tokens.test.mjs`), and
its visual criterion is a **token story that paints `text-link-visited` directly**, beside `link` and
`link-hover`, on all four surfaces, rather than a real anchor: three swatches that are three colours,
the last one visibly spent rather than merely darker (`color-tokens.md` §11.7).

**Retained without a call site: `text-inverse`.** It names "ink on a `text-primary`-filled region"
and nothing in the product currently fills a region with `text-primary`. Removing a token is a
breaking change under `GOVERNANCE.md`'s deprecation procedure, not a side effect of a re-derivation,
so it stays, measured against the one fill it would need if it ever gained a call site. **Standing
obligation**: if it still has no call site when feature 005 closes, it is a removal candidate for
that procedure, and it must not acquire a call site without its pair entering this table first.

**Carried forward, not introduced here**: `ProfileSummary`'s win/loss bar paints `success` and
`danger` adjacent to each other, and the two sit within two-tenths of one L\* step of each other in
both themes, so they are distinguished by hue alone at that one boundary. The percentage label beside
the bar is what satisfies rule 4 today; this was true of the previous palette too and is recorded so
`profile-summary.md`'s retrofit does not remove the label without noticing what it was carrying.

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

## Elevation

`packages/design-system/tokens/elevation.json` names four levels — `none`, `raised`, `overlay`,
`modal` — each a themed `box-shadow`, generated as the `shadow-*` utility. A shadow is not a
decoration a component picks by eye; it is a claim about where a surface sits relative to everything
else on the page, and FR-009 requires each level to carry a stated meaning and a statement of what
may sit at it, so that claim is checkable rather than assumed.

- **`none`** — the resting, flush state. Inline content and any surface that is not lifted off the
  page draws no shadow at all; this is the default, not an absence.
- **`raised`** — a surface lifted slightly off the page, enough to read as its own bounded unit
  without floating above unrelated content. `SignInScreen`'s card
  (`src/components/SignInScreen/index.tsx`) is the one call site today: the sign-in form is the
  page's single focal surface, and the lift is what separates it from the parchment behind it. A row
  or a control that sits flush with its container has no claim on this level.
- **`overlay`** — a floating surface above other content but not modal. `Tooltip`'s bubble
  (`src/components/Tooltip/index.tsx`) and `Menu`'s panel (`src/components/Menu/index.tsx`) both draw
  it. This is exactly the level the **"Not a gap: stacking"** decision below governs: it is the
  tooltip's bubble — the one floating surface with no explicit stacking value of its own — that the
  document-order constraints named there apply to (no clipping ancestor between it and the page root,
  no later positioned sibling over it). Any future component drawn at `overlay` without its own
  explicit stacking value inherits the same two constraints; see that decision rather than this one
  for what they are.
- **`modal`** — the highest level, for a surface that blocks interaction with everything beneath it.
  `Dialog` (`src/components/Dialog/index.tsx`) is the one call site. `modal` is a ceiling, not a step:
  nothing may render at a shadow level above it, because a dialog's own scrim already covers
  everything else on the page — there is nothing left underneath for a higher level to be elevated
  above.

A component may only use an elevation level whose stated meaning matches what it is. Reaching for
`shadow-modal` on a plain hoverable card would be a defect even though it "looks fine" on screen —
the same way a colour role painted on a surface it does not declare is a defect regardless of
whether the resulting pair happens to pass contrast (FR-005). `elevation.json`'s `$meaning` carries
the one-line form of the four bullets above; this section is where the full reasoning lives.

**The sheet ceiling, `max-h-sheet` (T528).** `Menu`'s `overlay`-level panel, when it renders as a
bottom sheet on a narrow viewport, is bounded to `max-height: 80vh` so it never grows past the
screen it floats over. That number is not a token, and adding one to `elevation.json` would be the
wrong fix for it: a viewport-relative ceiling is a **containment rule** about where an `overlay`
surface may extend to, not a reusable design decision the way a shadow depth or a duration is — it
says "never taller than the screen", not "here is a length someone chose", and no other call site
at any level needs the same number. `build-tokens.mjs`'s `elevationUtilityBlocks()` emits it as a
fixed-value `@utility max-h-sheet { max-height: 80vh; }` instead, alongside the icon, border and
type-role utilities that also have no Tailwind theme namespace to extend — a name `Menu` writes in
place of the arbitrary `max-h-[80vh]` bracket it used to carry, with no `size.json`/`elevation.json`
entry behind it, because there is nothing reusable to name.

## Iconography contract

FR-011 in reverse order: the size scale is closed (DS-7, feature 004, below); what follows is the
rest of the contract — how an icon aligns with adjacent text, how it is given or denied an
accessible name, and the minimum interactive footprint it owes. All four are already load-bearing
in shipping components; this section states them as rules so the next icon-bearing component reads
them here rather than re-deriving them from four different files.

**Size scale.** `icon-xs` through `icon-3xl` in `packages/design-system/tokens/icon.json` (closed
as DS-7, feature 004, below). `packages/design-system/tokens/build-tokens.mjs` emits one `@utility`
block per step into `packages/design-system/tokens/generated/preset.css` — `icon-xs { width:
var(--ds-icon-xs); height: var(--ds-icon-xs); }` through `icon-3xl` — so a component writes
`className="icon-md"` in the same utility vocabulary as every other family, with no hand-written
`var()` reference. The values do not move; what changes is that reaching for one no longer requires
writing a variable by hand, closing the icon half of the arbitrary-value escapes this system was
carrying silently (`h-[1em]`/`w-[1em]` in the spinner and in `FavouriteToggle`'s glyph, four
`h-`/`w-[var(--ds-icon-*)]` in `ProfileSummary`).

**Text alignment.** An icon that sits beside text is a flex sibling of that text inside a shared
`flex`/`inline-flex items-center` row — centred against the row's box, never aligned to the text's
own baseline. Every shipping pairing already does this: `Button`'s base class is `inline-flex
items-center justify-center gap-2`, and its leading/trailing icon slots and its loading `Spinner`
sit in that row beside the label
(`packages/design-system/src/components/Button/index.tsx`); `Menu`'s trigger is `inline-flex h-10
items-center gap-2` around its label; `FavouriteToggle`'s `StateGlyph`, sized `h-[1em] w-[1em]`,
sits inside that same `Button` row, centred against the label's line box by the row's
`items-center` rather than by matching the glyph to the font's own baseline; `CivilisationIcon`
wraps its mark and its name in one `inline-flex items-center gap-2` span for the same reason. An
icon needing to sit mid-sentence inside running prose, rather than beside a label, has no shipping
precedent and is out of this contract's scope until one exists.

**Accessible naming.** Three shapes cover every icon in the system today; a fourth is forbidden.

- **Decorative — the meaning is already carried by adjacent visible text.** An inline SVG mark
  gets `aria-hidden="true"`; an `<img>` mark gets `alt=""` — the same rule expressed through the
  mechanism the element type owns. `Button`'s leading/trailing icons and its loading `Spinner`,
  `FavouriteToggle`'s `StateGlyph` (the button's own label — "Add to favourites" / "Remove from
  favourites" — carries the state, never the glyph), `ProfileSummary`'s disclosure chevron,
  `PlayerAvatar` and `CivilisationIcon`'s image mark (the heading or name rendered beside each one
  carries the identity) are all this shape. It is the default, and it is wrong to also add
  `aria-label` here: a name on the icon and a name on the text it duplicates is two names racing
  each other in the accessibility tree, not a second signal.
- **The control's own accessible name covers the icon, rather than the icon carrying one of its
  own.** `Menu`'s profile-switcher trigger renders visible text plus an `aria-hidden` chevron, and
  the enclosing `<button>` still carries `aria-label={triggerAriaLabel}` ("aoe2guy, switch
  profile") because the visible text alone under-describes what activating the control does
  (`ProfileSummary`). The name lives on the interactive element; the glyph inside it stays
  decorative either way.
- **The icon reveals a name that would otherwise not exist — `Tooltip` with `relation="label"`.**
  `CountryFlag` is the shipping case: some flags are indistinguishable from each other at `icon-sm`,
  so the country name becomes the trigger's accessible name via `aria-labelledby`, reachable on
  hover, keyboard focus and press alike, and present in the accessibility tree whether or not the
  tooltip has ever opened (`tooltip.md` §2, `country-flag.md` §11, rule 4 above). `relation="describe"`
  is the sibling shape for a control that already shows its name as visible text and only needs the
  icon to add to it — never to replace what a sighted reader already sees (WCAG 2.5.3).
- **Forbidden**: an `aria-label` placed on the icon itself when adjacent visible text, or the
  enclosing control's own `aria-label`, already states the same fact. The icon is never the thing
  that is named; the control or the text beside it is.

**Minimum interactive footprint.** WCAG 2.5.8's 44×44px floor applies to any icon serving as, or
sitting inside, an interactive control, whether or not the glyph itself renders that large. Two
routes satisfy it, both already shipping, and a third is forbidden:

- **The icon's own box is the hit area.** `icon-xl` is fixed at 44px rather than following the
  space-scale rhythm the other six steps share, for exactly this reason
  (`packages/design-system/tokens/icon.json`'s own `$comment`) — a control sized directly from
  `icon-xl` needs no separate padding calculation.
- **Padding on the real interactive element composes a smaller icon token up to 44px.**
  `CountryFlag` draws its flag at `icon-sm` (16px) or `icon-md` (24px), but the `<button>` wrapping
  it pads out to a 44px hit area in both axes at both sizes, "reached by padding on the button
  itself, never by a transparent overlay" (`country-flag.md` §11.5). The visible mark stays small;
  the operable box does not.
- **Forbidden: enlarging a target with an overlay that intercepts unrelated interaction.** FR-056
  already states this for the system generally; an icon-sized control is where it is most tempting,
  because the glyph looks finished at its visual size and the padding around it looks like wasted
  space. It is not — it is the touch target.

**An icon is never the only carrier of a meaning (FR-011).** Rule 4 above, applied to icons
specifically: an icon-only control needs a text alternative reachable by every input — a visible
label, a `Tooltip`, or an `aria-label` on the control — and a purely decorative icon must never
appear without the meaning it draws already being carried by adjacent visible text. `Button`'s
leading icons, `FavouriteToggle`'s `StateGlyph` and `CountryFlag`'s flag are the three accessible-
naming shapes above precisely because each pairs the icon with a text route to the same fact; a
fourth shape — an icon standing alone with no label, no tooltip and no adjacent text — has no
shipping precedent and is not sanctioned by this contract.

## Surface density: `dense` and `prose`

FR-012 requires density to be a stated property of a surface class rather than a per-component
choice, and two classes cover every surface the system draws: `dense`, a surface holding many short
rows of data close together — a table, a compact list — and `prose`, a surface holding continuous
reading text — a legal notice, an explanatory paragraph. Each class fixes its row height and
padding, its line rhythm and which of the six typography roles it draws in, named as steps from
`packages/design-system/tokens/space.json`'s `scale` and `rhythm` groups rather than invented per
component. `data-model.md`'s surface-class table names the shape of each column; the values below
are what fills it, grounded in what `MatchRow`, `AnalysisTimeline` and `PrivacyNotice` already ship.

| Class   | Row height and padding                                | Line rhythm                                                                                     | Typography roles                               |
| ------- | ----------------------------------------------------- | ----------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| `dense` | `space-3` vertical padding per row                    | `space-1` between stacked rows; `space-2` for a within-row pairing (icon + text, label + value) | `type-numeric`, `type-machine`, `type-body`    |
| `prose` | `space-6` surface padding narrow, `space-8` from `md` | `space-4` between paragraphs in one subsection; `space-8` between sections                      | `type-display`, `type-body`, `type-supporting` |

**`dense`.** Row padding is `space-3` (`py-3`), the value every `<th>` and `<td>` in `MatchRow`'s
table already carries (`packages/design-system/src/components/MatchRow/index.tsx`). A pairing inside
one row — a duration icon beside its label, a badge beside a value — uses `space-2` (`gap-2`), the
same step `space.json`'s `rhythm` group names `within-component`, evidenced by the same file's
inline clusters. The line rhythm between one dense row and the next is tighter still: `space-1`
(`gap-1`), evidenced by `AnalysisTimeline`'s event list
(`packages/design-system/src/components/AnalysisTimeline/index.tsx`), which is exactly the "tight"
rhythm `data-model.md` names for this class. `space-3` and `space-1` are raw `scale` steps rather
than named `rhythm` values — a dense surface's rows sit closer together than the rhythm group's own
`within-component` step, which is why the group does not already name them.

**`prose`.** A prose surface has no tabular rows; its unit is the paragraph, and its "row height and
padding" is the padding around the whole reading block: `space-6` (`px-6 py-6`) narrow, opening to
`space-8` (`md:px-0 md:py-8`) from `md`, exactly as `PrivacyNotice`'s outer wrapper already renders
(`packages/design-system/src/components/PrivacyNotice/index.tsx`). Within one subsection,
consecutive paragraphs sit `space-4` (`gap-4`) apart, the step `PrivacyNotice`'s repeated body blocks
already use. Between one section and the next, the rhythm opens further to `space-8` (`gap-8`,
`mt-8`) — the same step `space.json`'s `rhythm` group names `between-sections`, evidenced by
`PrivacyNotice`'s own section transitions. `space-4` and the surface padding are raw `scale` steps;
the section-to-section step is the one place `prose` and the system's own named rhythm coincide,
which is what "open" means against `dense`'s "tight".

**Typography roles by class**

| Surface class | Role              | Used for                                                                                |
| ------------- | ----------------- | --------------------------------------------------------------------------------------- |
| `dense`       | `type-numeric`    | measured values a reader compares — ratings, durations, deltas                          |
| `dense`       | `type-machine`    | non-human-authored strings a dense surface shows as-is — raw identifiers, error classes |
| `dense`       | `type-body`       | everything else in a cell — names, labels, map and civilisation text                    |
| `prose`       | `type-display`    | the heading, if any, inside the surface                                                 |
| `prose`       | `type-body`       | paragraph copy, at full size with the generous line-height the role carries             |
| `prose`       | `type-supporting` | secondary text within the surface — captions, footnotes, metadata                       |

**Density is a property of a surface, assigned per component, never a reader-facing setting.**
FR-012 states the requirement; spec.md's Assumptions section states the boundary precisely and it is
quoted rather than paraphrased: _"Density is a property of a surface class in this feature, not a
reader-facing setting. A reader-controlled density toggle is out of scope."_ A component picks
exactly one of the two classes when its spec is written — never both, and never at the reader's
discretion.

**For phase 4**: `Panel` and `Table` (`packages/design-system/src/primitives/`) take a `density`
prop reading these two classes; this section is where the classes acquire the values that prop
reads.

## Token gap register

**No gap is open as of 2026-09-05 (T529).** This section holds open token decisions when they
exist — what is missing, what a component does until it exists, and who has to act — and an
implementer who finds themselves needing a value not covered by the standing rules above or the
utility vocabulary in `contracts/token-families.md` stops and asks `product-designer`; they do not
invent one. The six gaps this feature resolved (DS-3 through DS-6, DS-8, DS-9) are recorded below as
closures or, for DS-3, a dated refusal — kept under their original ids, never renumbered, so this
register and the commit history keep lining up with the defects they describe, the rule the DS-1,
DS-2 and DS-7 closures below already followed.

**Not a gap: stacking.** There is no `z-index` family and, as of `tooltip.md`, none is needed. The
one floating surface outside `Menu` and `Dialog` is the tooltip, which is absolutely positioned and
therefore paints above the non-positioned content that follows it, with no `z-index` value at all
(`tooltip.md` §3a). What that costs the caller is two constraints rather than a token: no ancestor
between the trigger and the page root may clip overflow, and no **later** positioned sibling may sit
over the surface. If a call site ever cannot satisfy both, that is when this register gains a
stacking row — not before, and never by way of an arbitrary number in a component.

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
register and the commit history line up with the gap it describes. `icon-xl`'s reason for existing
became load-bearing in Phase 8: the country flag is now a tooltip trigger and fills it
(`country-flag.md` §11.5).

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

**Closed — DS-10 (T526, `color-tokens.md` §5).** `focus-ring` on `accent` measured 1.38:1 light /
1.21:1 dark, both under the 3:1 non-text floor, because `focus-ring` had been derived only against
page surfaces and never against the accent-filled controls it also painted on. T521 proved the gap
is structural rather than a bad value: in the light theme the ring would need `Lf ≤ 0.289` to clear
3:1 against `surface-raised` and `Lf ≥ 0.453` to clear it against `accent` — no single value
satisfies both, and the dark theme gives the same contradiction. The fix is a declaration, not a
darker ring: **`focus-ring` now declares only the four page surfaces, and an `accent`-filled control
rings inward in `accent-contrast` instead** — the ink it already carries, which clears 6.07:1 light /
8.07:1 dark on its own fill, 7.65 / 10.06 on hover and 9.78 / 6.39 on press. `Button`'s `primary`
variant and `DataExportPanel`'s download link were the only two call sites (`focus-visible:outline-2
focus-visible:-outline-offset-2 focus-visible:outline-accent-contrast`, replacing
`outline-focus-ring`); the other fourteen `outline-focus-ring` declarations in the package are
untouched, and every one of them now clears 3:1 with 5.37–8.05 of margin against whichever page
surface it actually paints on (the measured contrast table above). The gap closes because the pair
it named stops being drawn, the same mechanism FR-005 asks for generally — not because a colour got
darker. `tests/visual/focus-ring.spec.ts`'s `knownContrastFailure` field and the `test.fail()` it
drove are removed from the two entries that carried it; both now assert like every other control.

**A rounding correction, T526.** Re-measuring the whole table from `color.json`'s shipped hexes
(rather than transcribing `color-tokens.md`'s stated numbers) turned up two places where the
decision record's arithmetic does not match its own values, beyond the ones its own §7 already
flagged for this task to fix. Dark `success-contrast` on `success`: the record states 8.2, the
shipped hexes (`#1b160e` on `#84b673`) measure **7.64**. Light `focus-ring` on `surface-raised`: the
record states 8.2, the shipped hexes (`#1f4e8c` on `#fffbf2`) measure **8.05**. Both still clear
their floor by a wide margin, so no token value moves and no verdict changes — the corrected numbers
above are what `build-tokens.test.mjs` asserts against. A handful of other rows differ from the
record by a few hundredths, consistent with a floor-vs-nearest rounding choice rather than a
computation error; this table now states every ratio to two decimals, computed directly, precisely
so a discrepancy like this one is a diff against `color.json` rather than a transcription to trust.

**Closed — DS-4 (T514, research D5).** There was no border-width, focus-ring-width or
focus-ring-offset token family; the interim was one uniform ring everywhere,
`outline-2 outline-offset-2` with `outline-focus-ring`, hand-written rather than named.
`tokens/border.json` closes it with a deliberately small, closed family — `hairline` (1px), `ring`
(2px), `ring-offset` (2px) — reached through the `border-hairline`, `outline-ring` and
`outline-offset-ring` utilities (`contracts/token-families.md` §2). The register's own suggested
alternative, ratifying Tailwind's built-in border-width scale, is explicitly overruled rather than
taken: FR-062 needs a mechanical check that an off-scale value fails, and
Tailwind's numeric width scale is unbounded (`border-7` compiles), so ratifying it would hand that
checker nothing to enforce. The values name what already shipped and do not move; only who owns them
does.

**Closed — DS-5 (T513, `tokens/breakpoint.json`) — and the review widths are a separate fact, now
declared elsewhere.** The register's interim answered two different questions in one sentence:
Tailwind's default breakpoints (`md` = 768, `lg` = 1024, `xl` = 1280) and, separately, "the review
viewports stay 375 / 768 / 1280." `tokens/breakpoint.json` closes the breakpoint half: `sm`, `md`,
`lg`, `xl` at 640, 768, 1024 and 1280, the single source both Tailwind's responsive variants and
`useMediaQuery`'s structural switch now read, so a layout's shape and its styling cannot disagree
(research D4). The three review widths are not this family — 375 has no breakpoint counterpart, and
768 and 1280 only coincide with two of the four breakpoint values by chance — so closing this row
without saying where they are declared would erase the one system-level place FR-018's declaration
lived. They are now standing rule 7 above, and `scripts/visual/run.mjs`'s `WIDTHS` constant names
that rule as its source in a comment: one home in prose, one consumer in code, the number written
once.

**Closed — DS-6 (T515, `tokens/size.json`, research D8).** There was no container / max-width /
reading-measure token family; the interim was Tailwind's own `max-w-*` scale, with `max-w-prose` for
any paragraph column — and the register's own recorded impact, "one route constrains its width;
eight do not," is exactly what an unnamed decision produces, because every route was left to invent
one. `tokens/size.json` closes it with `page` (80rem, matching the `xl` breakpoint), `panel` (42rem,
the one route-level width the application had already committed to, in
`apps/web/src/features/search/SearchContainer.tsx`) and `measure` (65ch, replacing every
`max-w-prose` call site), mapped onto Tailwind's `--container-*` theme namespace so `max-w-page`,
`max-w-panel` and `max-w-measure` are ordinary utilities. `measure` renames Tailwind's own opinion
about reading measure into ours; it moves no rendered pixel, only who owns the decision.

**Closed — DS-8 (T524, `font.json`'s `role` group).** There was no numeric-typography role; tabular
alignment rode on `font.family.mono` being monospaced, so a future change of that family would have
silently broken every rating table's alignment. The new `role` group in `tokens/font.json` adds
`type-numeric`, naming the mono family and `font-variant-numeric: tabular-nums` explicitly, beside
five other roles (`type-display`, `type-body`, `type-supporting`, `type-machine`, `type-identifier`)
that split the one meaning the mono family used to carry into three — a measured number, a machine
string and an unresolved identifier. `tabular-nums` sits only on `numeric`, never on the shared mono
role, because declaring it there would also apply it to `machine`'s filenames and error classes,
where it means nothing (research D7). T531 puts the three split roles — `type-numeric`,
`type-machine` and `type-identifier` — onto the nine components that shared the old monospace
treatment (a grep at implementation time found two — `MatchDetailPanel`'s `UnresolvedIdentifier`
and `PlayerResultRow`'s games-played/unverified-Steam-id pair — that this register's own text had
not named); digit alignment now survives a change of the monospace family because it is declared
rather than inherited.

**Closed — DS-9 (T522, the `link` / `link-hover` / `link-visited` roles).** The register named two
problems in one row: no link colour role, and `accent` on `surface-raised` missing from the measured
table. The contrast half closed inside T526's re-measurement of the table above, already recorded
there and not restated here. This closure is the semantic half, which is the one the interim could
not fix by adding rows: measuring `accent` on the other backgrounds would have left the real gap
open, because `accent` means the product's emphasis colour and a link is not that. `link`,
`link-hover` and `link-visited` are new roles in `tokens/color.json`, each declaring the surfaces it
may be painted on and measured against `background`, `surface`, `surface-raised` and
`surface-sunken` in both themes (research D10). The interim restriction this retires — no component
paints a link on a raised surface — was a real cost already paid once, by `privacy-notice.md`. The
permanent underline stays: a link is never distinguished by colour alone.

**Refused — DS-3, dated 2026-09-05.** No opacity token family is added. The three attenuated
appearances this register named resolve as named colour roles instead, each with a pair that can be
measured before it exists on screen rather than only after it is rendered: disabled is
`text-disabled` on `surface-sunken` with `border` — unchanged, already the interim; de-emphasised is
`text-secondary`; the dialog scrim is the existing `overlay` role. `overlay` keeps its alpha —
`text-primary` at 55% — and that is not a contradiction of this refusal: a scrim carries no
foreground, nothing is read _against_ it the way a foreground is read against a background, so it
owes no contrast pair. What it owes is that the dialog rendered above it reads clearly, and that
pair — `text-primary` on `surface`, the fill and heading ink `Dialog` (`src/components/Dialog/`)
actually paints — is already measured in the table above (research D9). This reasoning is recorded
here beside the refusal so the next reader does not have to re-derive it, or, worse, "fix" `overlay`
by stripping its alpha and breaking the scrim it draws.
