# Component specs

Written by `product-designer`, read by `implementer` before writing a component and by
`visual-reviewer` when judging one. Constitution VI: no component exists without a spec, and no
component carries a hard-coded style value.

## Index

| Spec                                                     | Component directory                                                                | Feature                      |
| -------------------------------------------------------- | ---------------------------------------------------------------------------------- | ---------------------------- |
| [`shared-primitives.md`](./shared-primitives.md)         | `src/primitives/{Button,Callout,Badge,Skeleton,Menu,Dialog,StatValue}/`            | 001                          |
| [`structural-tier.md`](./structural-tier.md)             | `src/primitives/{Page,Section,Panel,Text,Link,Table,Field,EmptyState,ErrorState}/` | 005, US2                     |
| [`sign-in-screen.md`](./sign-in-screen.md)               | `src/screens/SignInScreen/`                                                        | 001, US1                     |
| [`archival-control.md`](./archival-control.md)           | `src/screens/ArchivalControl/`                                                     | 001, US1/US5                 |
| [`profile-summary.md`](./profile-summary.md)             | `src/screens/ProfileSummary/`                                                      | 001, US1; 003, US1; 004, US2 |
| [`capture-state-badge.md`](./capture-state-badge.md)     | `src/composites/CaptureStateBadge/` (grows `Badge`'s tone variants)                | 001, US3                     |
| [`match-history.md`](./match-history.md)                 | `src/composites/MatchRow/`, `src/composites/MatchDetailPanel/`                     | 001, US3; 003, US2; 004, US1 |
| [`manual-upload.md`](./manual-upload.md)                 | `src/composites/UploadControl/`                                                    | 001, US4                     |
| [`privacy-notice.md`](./privacy-notice.md)               | `src/screens/PrivacyNotice/`                                                       | 001, US5                     |
| [`privacy-data-rights.md`](./privacy-data-rights.md)     | `src/screens/DataExportPanel/`, `src/screens/AccountErasurePanel/`                 | 001, US5                     |
| [`third-party-objection.md`](./third-party-objection.md) | `src/screens/ThirdPartyObjectionForm/`                                             | 001, US5                     |
| [`footer.md`](./footer.md)                               | `src/composites/Footer/`                                                           | 001, US5                     |
| [`player-search.md`](./player-search.md)                 | `src/composites/SearchBox/`, `src/composites/PlayerResultRow/`                     | 003, US1                     |
| [`replay-availability.md`](./replay-availability.md)     | `src/composites/ReplayAvailabilityList/`                                           | 003, US3                     |
| [`favourite-toggle.md`](./favourite-toggle.md)           | `src/composites/FavouriteToggle/`                                                  | 003, US5                     |
| [`favourites-list.md`](./favourites-list.md)             | `src/composites/FavouritesList/`                                                   | 003, US5                     |
| [`analysis-timeline.md`](./analysis-timeline.md)         | `src/composites/AnalysisTimeline/`                                                 | 003, US4                     |
| [`game-asset-tokens.md`](./game-asset-tokens.md)         | player-colour + icon-size tokens (no component; `tokens/`)                         | 004                          |
| [`civilisation-icon.md`](./civilisation-icon.md)         | `src/composites/CivilisationIcon/`                                                 | 004, US1                     |
| [`map-thumbnail.md`](./map-thumbnail.md)                 | `src/composites/MapThumbnail/`                                                     | 004, US1                     |
| [`player-colour-swatch.md`](./player-colour-swatch.md)   | `src/composites/PlayerColourSwatch/`                                               | 004, US1                     |
| [`country-flag.md`](./country-flag.md)                   | `src/composites/CountryFlag/`                                                      | 004, US2; 004, Phase 8       |
| [`player-avatar.md`](./player-avatar.md)                 | `src/composites/PlayerAvatar/`                                                     | 004, US2                     |
| [`site-header.md`](./site-header.md)                     | `src/composites/SiteHeader/`                                                       | 004, US3                     |
| [`tooltip.md`](./tooltip.md)                             | `src/primitives/Tooltip/`                                                          | 004, Phase 8                 |

**Two corrections landed with T570.** `structural-tier.md` (T540–T548, feature 005 US2) had no row
here — its own §15 named the gap and this closes it. `shared-primitives.md`'s row was missing
`Dialog`, which has specified that file's seventh component since feature 001; the directory column
above now names all seven. `GOVERNANCE.md` and the three token decision records
(`game-asset-tokens.md`, `color-tokens.md`, `typography-tokens.md`) are deliberately absent from this
table: the first is a procedure document and the latter three specify tokens, not a component —
`game-asset-tokens.md` already said so in its own row above, and the newer two follow the same rule
without needing a row that would only ever say "no component" again. This index is the set T570
amended and T571's completeness check enumerates: every row above other than `game-asset-tokens.md`
names one or more components whose spec must answer the closed state vocabulary in full and declare
a tier and a surface class.

## Every spec has nine sections

Purpose, Anatomy, Variants and sizes, States, Tokens used, Spacing, Responsive, Accessibility,
Visual acceptance criteria. A spec missing one is incomplete, and "this component has no empty
state" is a design bug, not an exemption.

The state vocabulary is closed: **default, hover, focus-visible, active, disabled, loading, error,
empty, selection, expansion**. Every spec answers all ten, even when the answer is "this part is
never disabled; disabling it would be wrong, and here is what happens instead".

**Selection and expansion (FR-034, T569) join the vocabulary here because several components
already ship them and none named them.** The original eight describe a single control's own
resting, interaction and lifecycle states; these two describe a relationship between a component
and the set or surface it governs, which is a different shape and was going unrecorded rather than
absent. **Selection** is a component holding one current member of a set: `SiteHeader`'s primary
navigation marks the current route with `aria-current="page"`, a persistent underline strip (`<span
aria-hidden="true">` filled `bg-accent` when current, `bg-transparent` and reserving the same height
otherwise) and a font-weight change (`font-semibold` against `font-medium`)
(`src/composites/SiteHeader/index.tsx`), and `Menu`'s `selection` variant marks the current item with
`role="menuitemradio"` and `aria-checked`, consumed by `SiteHeader`'s `ThemeControl` — which pairs the
checked option with a `<Badge>Current</Badge>` — and by `ProfileSummary`'s profile switcher
(`src/primitives/Menu/index.tsx`, `src/composites/SiteHeader/index.tsx`,
`src/screens/ProfileSummary/index.tsx`). **Expansion** is a disclosure that reveals or hides a surface
without navigating away from it: `Menu`'s own trigger carries `aria-expanded` on the button that opens
and closes its panel (`src/primitives/Menu/index.tsx`) — the one shipping case; no accordion and no
`<details>`/`<summary>` exists in the package today, and naming expansion here is not licence to add
one — a state is documented because it is real, never built because the vocabulary lists it (FR-036).

**Two states of one component must be distinguishable from one another by more than colour, and
that distinction must survive as a still image (FR-037).** Rule 4 below already forbids colour as
the only carrier of meaning; the still-image half is what the first half was silent on and is the
reason the vocabulary is reviewable by `visual-reviewer` at all — that agent compares screenshots,
never a live page, so a difference that exists only while a pointer hovers, only mid-animation, or
only in a hue shift is not reviewable by it, closed vocabulary or not. What satisfies it is a shape,
a mark, a weight, a position, a border or an icon that a screenshot still shows once whatever
produced it has stopped changing: `SiteHeader`'s current-route underline is a strip that is present
or transparent at a height reserved either way, never a colour swap alone, and `Menu`'s `ThemeControl`
consumer pairs its checked option with a text badge rather than a tint. `Menu`'s own open panel —
drawn beside the trigger, or absent entirely — is the still-image evidence for expansion: the two
states differ in what exists on the page, not merely in how it is painted. A spec that answers
selection or expansion with a hue change and nothing else has not answered it (T570 amends the
existing 23 specs against this vocabulary; this paragraph is the bar each amendment is checked
against).

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
8. **The theme toggle is the one exemption to rule 6, and it is one component wide.** `SiteHeader`'s
   `ThemeControl` (`site-header.md` §2d, T535) is the single component in this package permitted to
   read which theme is active, because its own job — showing the reader which of System, Light and
   Dark is current and letting them change it — cannot be done without reading it. What keeps it
   inside FR-017 rather than outside it is that it **sets** the theme and styles nothing by it: every
   pixel `ThemeControl` draws comes from the same token set in both themes, and what changes between
   them is which theme those tokens resolve to for the rest of the page, never how `ThemeControl`
   itself looks. Rule 6 forbids a component that reads the theme to choose its own colour, its own
   layout or its own copy; a component that reads the theme only to report it and to set it is a
   different thing, because nothing about its own rendering differs when the theme does. **This is
   not a precedent.** No other component may cite it to acquire the same exemption: a second
   component calling `useTheme()`, reading `document.documentElement.dataset.theme` directly, or
   importing anything from `packages/design-system/src/theme` for a reason other than setting the
   theme is the violation rule 6 already names, not a second toggle. Mechanically checked by the grep
   [quickstart scenario 6](../../../specs/005-design-system-foundations/quickstart.md) already runs
   over `packages/design-system/src` for `dataset.theme`/`data-theme`: it must match only
   `packages/design-system/src/theme` and `SiteHeader`'s `ThemeControl`, and a third location in that
   output is the defect, not a finding to explain away. The command lives once, in the quickstart —
   restated here it would be the same number in two files.
9. **One prop vocabulary for the same concept, or a recorded reason the difference is real**
   (FR-032, T557). Sizes are `xs`/`sm`/`md`/`lg` everywhere, never spelled out, and every closed
   `status`/`state` union that this package invents rather than mirrors a wire value is
   kebab-case — no exception is spelled `snake_case` or `camelCase`. The survey's one genuine,
   accidental collision was `CaptureStateBadge`'s `context` prop (`compact`/`detail`): every other
   component whose rendering depends on where it is embedded — `ProfileSummary`, `StatValue`,
   `SignInScreen`, and every embedding-dependent `size` scale (`CivilisationIconSize`,
   `MapThumbnailSize`) — names that choice `variant`. `context`/`CaptureStateBadgeContext` are
   retired; `variant`/`CaptureStateBadgeVariant` replace them, landed with every consumer in the
   same change — `CaptureStateBadge` itself, `MatchRow`, `MatchDetailPanel`, their tests and
   stories, and `capture-state-badge.md`, `match-history.md` and `replay-availability.md`. No
   rendering changed; only the prop and the type are renamed. This is the deprecation procedure's
   first real subject (T570), ahead of the procedure itself being written down (T573,
   `GOVERNANCE.md`).

   Where the same concept still reads as two names on inspection elsewhere, the difference was
   surveyed under FR-032 and kept because it is real, not because nobody looked:
   - `Page.title` names the route's one `<h1>`; every other structural primitive's own heading
     (`Section`, `Panel`, `EmptyState`, `ErrorState` — `structural-tier.md` §5–§13) is `heading`,
     the same word `Callout` (`shared-primitives.md`) already used for the identical role outside
     the structural tier. The two are not the same concept: one page has exactly one `title`, and
     every block inside it may have a `heading`.
   - `ButtonVariant`'s `destructive` and `CalloutTone`/`BadgeVariant`'s `danger` are not the same
     scale: `destructive` names what the button _does_ (an irreversible action), `danger` names
     what a message _means_. `destructive` already paints its ink with the `danger` token
     (`shared-primitives.md`, Button §"variants") — the layering is deliberate, not a naming gap.
   - `Badge`'s `variant` and `Callout`'s `tone` are not the same prop under two names: `Badge`'s
     scale is a superset (`neutral`, `accent` plus the four tone variants) because a badge may
     carry no semantic weight at all, while `Callout` always does. The four members the two scales
     share (`info`/`success`/`warning`/`danger`) are already spelled identically in both
     (`capture-state-badge.md` §5).
   - `ReplayAvailabilityList`'s `ReplayAvailability`/`ReplayDownloadState` carry `never_recorded`
     and `rate_limited` in `snake_case`, against this rule's own kebab-case default, because both
     values are deliberately the API's own wire spelling passed straight through
     (`availability.py`'s `Availability` enum; the `rate_limited` error `code`) rather than
     translated — `replay-availability.md` §3 documents the same string being read on both sides
     of the wire. `SearchBoxState`'s `rate-limited` is the ordinary case: UI-invented vocabulary with
     no wire value to stay identical to, so `SearchContainer.tsx` translates the wire's
     `rate_limited` code into it deliberately.
   - `AnalysisTimeline`'s `onRetryLoad` is not `onRetry`: it is the one component in the system
     with two retry-shaped callbacks (reloading the page's own data, and `onRequestAnalysis`
     recomputing the analysis itself), so the generic name every single-retry component uses would
     be ambiguous here specifically (`analysis-timeline.md`'s prop, documented inline).

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
(`packages/design-system/src/primitives/Button/index.tsx`); `Menu`'s trigger is `inline-flex h-10
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
table already carries (`packages/design-system/src/composites/MatchRow/index.tsx`). A pairing inside
one row — a duration icon beside its label, a badge beside a value — uses `space-2` (`gap-2`), the
same step `space.json`'s `rhythm` group names `within-component`, evidenced by the same file's
inline clusters. The line rhythm between one dense row and the next is tighter still: `space-1`
(`gap-1`), evidenced by `AnalysisTimeline`'s event list
(`packages/design-system/src/composites/AnalysisTimeline/index.tsx`), which is exactly the "tight"
rhythm `data-model.md` names for this class. `space-3` and `space-1` are raw `scale` steps rather
than named `rhythm` values — a dense surface's rows sit closer together than the rhythm group's own
`within-component` step, which is why the group does not already name them.

**`prose`.** A prose surface has no tabular rows; its unit is the paragraph, and its "row height and
padding" is the padding around the whole reading block: `space-6` (`px-6 py-6`) narrow, opening to
`space-8` (`md:px-0 md:py-8`) from `md`, exactly as `PrivacyNotice`'s outer wrapper already renders
(`packages/design-system/src/screens/PrivacyNotice/index.tsx`). Within one subsection,
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
focus-visible:-outline-offset-4 focus-visible:outline-accent-contrast`, replacing
`outline-focus-ring`); the other fourteen `outline-focus-ring` declarations in the package are
untouched, and every one of them now clears 3:1 with 5.37–8.05 of margin against whichever page
surface it actually paints on (the measured contrast table above). The gap closes because the pair
it named stops being drawn, the same mechanism FR-005 asks for generally — not because a colour got
darker. `tests/visual/focus-ring.spec.ts`'s `knownContrastFailure` field and the `test.fail()` it
drove are removed from the two entries that carried it; both now assert like every other control.

**Corrected 2026-09-11 (T582), found while closing H1 below.** DS-10 itself shipped both call sites
at `-outline-offset-2`, not `-outline-offset-4` as stated above — the offset this row now states is
T586's, not the one DS-10 actually closed with. `-outline-offset-2` on a 2px-wide ring fills exactly
the outermost two pixels of the border box, flush with the control's edge, so the ring's outer side
sat on the page at 1.00–1.42:1 (H1, below) rather than on the `accent` fill this row's own contrast
numbers describe. T586 (commit `a3050c30`) moved both rings to `-outline-offset-4`, leaving a 2px
band of `accent` fill between the ring and the edge on every side, which is what the class string
above now correctly states. The numbers this row cites (6.07:1 light / 8.07:1 dark on the fill, and
the rest of DS-10's reasoning) were never wrong — only the geometry that decided which adjacency the
ring's _other_ side landed on was, and this note is left here rather than silently changing the
class string in place, so a reader comparing this row against `git log` does not find a fact that
was never true.

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

## Storybook documentation gap register

**All four rows closed 2026-09-11 (T578), owed since 2026-09-07 (T572).** This register held what
quickstart.md scenario 9 found still missing from the built Storybook after the fixes it also
triggered landed. The gap is filed where a future reader of the package meets it rather than only
in the frozen record of the run that found it
(`specs/005-design-system-foundations/quickstart.md`, "Scenario 9 — Result"). The distinction is
CLAUDE.md's: a fact about this package's Storybook build needs updating whenever a future task
changes that build, so it stays here rather than in a spec, which is written once — this is why the
four rows below stay as a dated record of what was closed and how, rather than being deleted once
fixed.

**FR-040 and production-readiness item 10 are now met.** spec.md's FR-040 requires Storybook to be
sufficient to understand the system without reading the application source; the four rows below were
the specific ways it was not, as of the register's 2026-09-07 date. T563, T565 and T566 had already
closed everything FR-040 asked of story coverage and composition realism (why they stay ticked in
`tasks.md`); the remaining gap was documentation infrastructure — autodocs, docgen, a purpose line, a
naming-contract statement — and T578 is what closes it.

A human reader, given the built Storybook and no repository access, could already reliably answer
_what does X look like when Y_ (Foundations → Colour computes every ratio live and captions every
tile with its surface; `SearchBox`'s rate-limited story and `Menu`'s corrected selection mark were
both named as models). The four rows below are what used to leave them guessing at _which X, and
why_, and are now answered by every component's own autodocs page.

**Verifiability, not belief.** `scripts/checks/story-docs.mjs` (wired into CI's `web` job) makes
rows 3 and 4 living facts asserted by a test rather than by re-reading this register: it fails on a
component directory with no story file, a story file whose meta carries no non-empty
`parameters.docs.description.component` purpose line, a component named in the script's own
`SR_ONLY_NAMING_SHAPE_COMPONENTS` map whose purpose line carries no real markdown link to Foundations
→ Iconography's docs page (the bare word "Iconography" does not count — fixed in the remediation
below), or a component directory whose own source contains the literal text `sr-only` without being
classified in exactly one of `SR_ONLY_NAMING_SHAPE_COMPONENTS` or the new `SR_ONLY_SOLE_NAME_COMPONENTS`
map — and a classified component whose source no longer contains `sr-only` fails too, the same lie in
the other direction. Rows 1 and 2 are configuration facts about `.storybook/` rather than a
per-component one, so no per-component check applies to them; they are instead provable by
inspecting the build directly.
`storybook-static/index.json` after `pnpm --filter design-system build-storybook` carries 48
`type: "docs"` entries (41 components plus the 7 Foundations pages) where it carried zero before,
and a built component chunk's own `__docgenInfo` (e.g. `Link`'s) now carries real per-prop types
(`LinkVariant`'s `"inline" | "standalone"` union) and JSDoc descriptions (`external`'s prop comment)
rather than an empty `description: ''` — proof the Controls panel and the autodocs prop table both
derive from the component's own TypeScript, not merely that a page exists.

1. **Zero `docs` entries in the build — closed.** All 536 entries used to be `type: "story"`; there
   was no autodocs page and no MDX page for a single component. Closed by adding `tags: ['autodocs']`
   to `.storybook/preview.tsx`'s project-level annotations (not `main.ts` — main.ts's own `tags` field
   is silent at the per-story level; proven while closing this row) and registering
   `@storybook/addon-docs` in `.storybook/main.ts`'s `addons` array, without which the tag alone still
   builds zero `docs` entries. A story may still opt out per file with `tags: ['!autodocs']`; none
   does. **Closed by T578, 2026-09-11.**
2. **No prop documentation — closed.** The Controls panel used to show a prop's name and its control
   widget only, no type column, no description, because docgen was off. Closed by setting
   `.storybook/main.ts`'s `typescript.reactDocgen` to `'react-docgen-typescript'` — the
   `@joshwooding/vite-plugin-react-docgen-typescript` docgen, already a transitive dependency of
   `@storybook/react-vite`, needing no new package — in place of the framework's own default
   (Babel-based `'react-docgen'`, which reads a prop's shape but not its JSDoc description or a
   separately declared `interface Props`'s literal unions). Row 1's autodocs page and the Controls
   panel now derive their prop table from the same source, a component's own TypeScript types, so
   the fact is written once. **Closed by T578, 2026-09-11.**
3. **No component states its purpose in a sentence — closed.** Not one of the 41 components under
   `packages/design-system/src/` used to open with a line saying what it was for — the reader had
   named this the single highest-value gap and the direct cause of Q1's difficulty in the scenario 9
   run: finding `PlayerColourSwatch` by need depended entirely on the navigation grouping (T564),
   because no component page itself confirmed the need it served once found. Closed by adding one
   sentence per component to `parameters.docs.description.component` in every `*.stories.tsx`'s
   default export, drawn from that component's own spec's Purpose section rather than invented —
   `PlayerColourSwatch`'s now reads "Shows which in-game colour a player used, as a chip beside their
   name, so a reader can tie a name in the list to the colour they saw in the game." `story-docs.mjs`
   (above) keeps this mechanically checked rather than merely authored once. **Closed by T578,
   2026-09-11.**
4. **No component states which `sr-only` naming shape it follows — closed, corrected during
   remediation.** Foundations → Iconography states the rule an icon-carried meaning must satisfy
   (FR-011: an icon is never the only carrier of a meaning), but no component story linked to that
   page or claimed conformance with it, so a reader could not tell from the built Storybook alone
   that `PlayerColourSwatch`'s colour-blind redundancy existed at all — it is `sr-only` text,
   invisible in a rendered story and undiscoverable without the DOM. Closed by auditing every
   `sr-only` occurrence in each component's own (non-story, non-test) source under
   `packages/design-system/src` (ten hits) and appending a naming-shape sentence, linking
   `?path=/docs/foundations-iconography--docs`, to the three whose `sr-only` text is genuinely
   redundant — a fact painted non-textually and restated in a permanent `sr-only` span, rather than
   the _sole_ source of a name:
   - `PlayerColourSwatch` — a `sr-only` text alternative for the colour-only signal it paints.
   - `Link` — a `sr-only` span folded into the anchor's own accessible name, beside its decorative
     `external` icon.
   - `MatchRow` — a `sr-only` absolute date backing up a mouse-only `title` tooltip (FR-039).

   The other seven `sr-only` hits are each the _sole_ source of a name or an announcement for
   something else, not a restatement of a fact painted a second way: `Field`'s conditionally hidden
   `<label>`, `Page`'s hidden `<h1>`, `Section`'s hidden heading, `Table`'s hidden caption (all "hide
   the one name that exists, don't duplicate it"), `SiteHeader`'s skip-navigation link (a
   keyboard-only affordance, not a name), `Menu`'s `aria-live` announcement region (a live update,
   not a name), and **`Tooltip`**, whose `qualifier` prop prepends `sr-only` text to the trigger's
   own accessible name (§8 of `tooltip.md`) rather than restating a fact painted a second way.

   **`CountryFlag` is deliberately not in the redundant list**, corrected during this row's own
   remediation: its purpose line still documents the same shape ("the icon reveals a name that would
   otherwise not exist", `Tooltip`'s `relation="label"`, `country-flag.md` §11) and still carries the
   Iconography link, but its own `index.tsx` contains no literal `sr-only` text — the `sr-only` span
   in its rendered output belongs to `Tooltip`, which it composes. The original version of this row
   listed `CountryFlag` and not `Tooltip`, trusted by a one-time hand-audit; `story-docs.mjs`'s own
   source-scan (added in the remediation below) proved the two were swapped, because it checks one
   directory's own files, not a composed render tree.

   `story-docs.mjs`'s `SR_ONLY_NAMING_SHAPE_COMPONENTS` (3 entries) and `SR_ONLY_SOLE_NAME_COMPONENTS`
   (7 entries) maps carry this same classification and reasoning in code, checked against every
   component directory that exists — a new `sr-only` occurrence shipping unclassified, or a listed
   component that stops using `sr-only`, both fail the check by naming the component. **Closed by
   T578, 2026-09-11; the classification and the link-vs-word check corrected the same day after
   independent review found the check accepted an unlinked mention and never re-derived the
   classification from source.**

Two smaller findings from the same run are already fixed and are not repeated here as open rows:
`SearchBox`'s two stories both numbered "empty 2 of 3" is corrected, and `Menu/KeyboardNavigation`'s
resting frame now documents something rather than showing a closed menu. Two findings are recorded
but deliberately not rows above because neither blocks an answer, only convenience: story ids do not
follow the sidebar path (`composite-playercolourswatch` vs `primitives-menu`), so a URL is not
guessable from the tree; and Storybook's built-in search is name-matching only, so `colourblind` and
`accessible` return nothing and `contrast` returns a false positive on the words "contract
violation" — a full-text search would need indexing every story's rendered content and captions,
which no tool here does today.

## Accessibility mechanism gap register

**Closed 2026-09-11 (T579), owed since 2026-09-08** (third-pass adversarial review, finding M2a).
This register holds a standing property of this package's own tooling — where an accessibility
check runs, and where it does not — the same distinction CLAUDE.md draws for the Storybook
documentation gap register above: a fact about this package's own check coverage needs updating
whenever a future task changes that coverage, so it is filed here rather than in a spec, which is
written once (T575's amendment: the subject is this package, so the fact is filed beside it).

1. **`axe-core` runs only inside `tests/visual/stories.spec.ts` (~line 317), which needs a built
   Storybook and a real browser — CI only, never at the point a component is authored.**
   `scripts/checks/a11y-allowlist.mjs` printing "empty — nothing to validate" proves no _known_
   violation is currently suppressed; it says nothing about _when_ the scan that would catch a new
   one runs, and today the answer is: after the PR is open, not while the component is written. The
   two `landmark-unique` guards that exist —
   `packages/design-system/src/primitives/Panel/Panel.test.tsx` (~lines 121-131) and
   `packages/design-system/src/composites/MatchDetailPanel/MatchDetailPanel.test.tsx` (~line 283)
   — are hand-written DOM assertions pinned to the two compositions that were caught, not a check
   for the class: a third component that gives a hidden caption the same accessible name as its
   ancestor heading is guarded by neither. This defect class has shipped three separate times within
   this one phase, caught by CI's axe pass each time and never at write-time — two point-fixes have
   not stopped a third, and there is no reason a fourth would fare differently. The fix is cheap:
   `axe-core` is already a dependency, and the gap is closed by one generic vitest assertion —
   render a component tree, scan it with `axe-core`, fail on any `landmark-unique` violation —
   written once and reused across component test files, rather than by hand-writing a guard per
   composition the way the two existing ones were. **Closed by T579, 2026-09-11.**
   `expectNoLandmarkUniqueViolations` (`packages/design-system/src/test/axe.ts`) is that one
   assertion — `axe-core` scoped to the `landmark-unique` rule alone, because jsdom has no layout
   engine and every rendering-dependent rule (`color-contrast` foremost) would give a false result
   under it. `Panel.test.tsx` and `MatchDetailPanel.test.tsx`'s own hand-written guards now call
   it instead of re-deriving uniqueness from a `screen.getByRole` name lookup, and a second file,
   `packages/design-system/src/test/story-a11y.test.tsx`, renders every story of every component
   through Storybook's own portable-stories API (`composeStories`, `@storybook/react`, added as a
   direct devDependency of this package — resolvable transitively before only through
   `@storybook/react-vite`, which pnpm's strict `node_modules` does not expose to a sibling
   package) against the shared project annotations in `.storybook/preview.tsx`, and calls the
   helper on every story of every component — the "no one has to opt in" property the two
   point-fixes this row named did not have. "Every" is asserted, not assumed: the sweep fails if
   the set of story files it composed differs from the set of component directories (derived from
   a second, independent glob over each directory's `index.tsx`), or if any story file composes no
   story, so a broken glob cannot report green over zero stories. None needed excluding: every
   component already had a working jsdom render (a `*.test.tsx` exists for each), and the defect
   class this row is about lives in a component's static composition, never behind a story's own
   `play` function, which the sweep does not invoke. It scans `baseElement`, not `container`, so a
   future portal is covered too. The full sweep runs in under three seconds.

## Duplicated logic and story-content gap register

**Open as of 2026-09-09** (fifth-pass adversarial review); **both rows closed** — row 1 2026-09-11
(T580), row 2 2026-09-11 (T581). Two Low findings that are each a fact about this package's own
source rather than about a component, filed here for the same reason the two registers above are:
the subject is the package itself, so a future task changing either fact needs this row updated,
which is why it is not folded into a spec written once.

1. **The WCAG 2.2 contrast-ratio formula (`srgbToLinear` / `relativeLuminance` / `contrastRatio`)
   existed as three separate implementations — closed.** All under `packages/design-system/` except
   the last: `.storybook/foundations/Colour.stories.tsx:61-77`; `tokens/build-tokens.test.mjs:20-37`;
   and `tests/visual/focus-ring.spec.ts:234-241` — the first two present as of the phase this
   register's sibling sections describe, the third added during this phase (driving both themes
   through the focus-ring's own colour math). Each carried a comment arguing it was not a duplicated
   _measurement_ — `Colour.stories.tsx` derives its ratios live from the same generated token rather
   than transcribing a number, and `focus-ring.spec.ts` computed from a `getComputedStyle`
   `rgb(...)` string rather than the `#rrggbb` hex the other two read, so reusing either existing
   helper would have meant converting one input format into the other just to call it — and each of
   those three arguments was true on its own terms. What none of them changed is that the _formula
   itself_ — the sRGB-to-linear piecewise function, the relative-luminance weights, the
   contrast-ratio arithmetic — was written out by hand three times rather than once: a correction to
   any one of the three constants (the `0.03928` breakpoint, the `2.4` gamma, the
   `0.2126`/`0.7152`/`0.0722` weights, the `0.05` WCAG offset) had to be found and applied in all
   three files to stay correct, and nothing failed a build if only two of the three were updated.
   CLAUDE.md's law is that a fact written twice goes stale in one copy; a formula is the same hazard
   as a number under that law. Closed by extracting the one shared module,
   `packages/design-system/tokens/contrast.mjs` (paired with `contrast.d.mts` so the TypeScript call
   site gets a real type, the same split `scripts/visual/review-widths.mjs`/`.d.mts` already uses),
   exporting `contrastRatioHex` (the entry point `Colour.stories.tsx` and `build-tokens.test.mjs`
   call) and `contrastRatioRgb` (the entry point `focus-ring.spec.ts` calls, after its own
   `parseRgb` — kept local, since parsing a live `getComputedStyle` string is that call site's own
   I/O, not part of the formula) — and importing it from all three. `contrast.test.mjs` (run by the
   same `node --test tokens/*.test.mjs` `build-tokens.test.mjs` already is) asserts the formula
   against known reference values (`#000000`/`#ffffff` = 21:1, a colour against itself = 1:1,
   `#767676`/`#ffffff` ≈ 4.54:1, symmetry, and hex/`{r,g,b}` agreement), confirms every contrast
   assertion `build-tokens.test.mjs` already made still passes unchanged, and adds a recurrence
   guard — a scan of `packages/`, `tests/`, `scripts/` and `apps/` for the `12.92` divisor together
   with the `1.055` gamma denominator outside `contrast.mjs` — so a fourth hand-written copy fails a
   build instead of waiting for a seventh adversarial pass to notice it. The `0.03928` linearisation
   threshold (the older of two values WCAG has published for this breakpoint; current text uses
   `0.04045`) is kept
   as-is rather than "corrected" during the extraction, with a comment in `contrast.mjs` recording
   why: for an 8-bit integer channel the two thresholds agree at every representable input, and a
   changed constant would have made "no contrast ratio moved" unprovable for an extraction. **Closed
   by T580, 2026-09-11.**
2. **`FavouritesList.stories.tsx`'s `Default` (lines 45-47) and `RealisticList` (lines 101-103) carried
   byte-identical `args` — closed.** Both used to read
   `{ entries: [rated, neverRanked, staleStanding] }`, so T566's "realistic composition" story for
   this component (FR-043, SC-012) produced six baselines (both themes, all three widths)
   pixel-identical to `Default`'s own six and verified nothing `Default` did not already cover.
   `RealisticList` now carries its own six-entry
   roster — the shape `apps/web`'s `/favourites` route actually renders, per its own comment — mixing
   a long alias + clan pair that wraps rather than truncates (favourites-list.md §8), a rating
   `delta` in both directions, and one entry `removing: true`, none of which `Default` or any other
   story in the file exercises. `Default`'s three fixtures and its own six baselines are unchanged.
   **Closed by T581, 2026-09-11**; `RealisticList`'s six new baselines are regenerated from CI's
   Linux renderer in a follow-up commit on this branch — not yet moved as of this commit.

## Contrast-signal and duplicate-baseline gap register

**Open as of 2026-09-09** (sixth-pass adversarial review, findings H1, M1, L1, L2; rows 5-6 added 2026-09-11 while verifying the closures above); **row 1 closed
2026-09-11 (T582)**, **row 2 closed 2026-09-11 (T583)**, **row 3 closed 2026-09-11 (T584)**, **row 4
closed 2026-09-11 (T585)** — all four rows now closed. Four findings the review judged
real but not blocking against B1/B2 (the `Button` `active:outline` defect this same pass's
remediation fixes) — filed here rather than folded into the fix, for the same reason the three
registers above are: each is a fact about this package's current state that a future task can close
on its own, not a defect this remediation's scope covers.

1. **H1 — a focused `primary` `Button`'s ring read at 1.00–1.42:1 against the surface behind it,
   flush with the control's edge — closed.** `accent-contrast` (the ring colour DS-10 closed with,
   above) equals `surface-raised` in the light theme and `background` in the dark theme; DS-10's
   ring shipped at `-outline-offset-2` on a 2px-wide ring, which paints exactly the outermost two
   pixels of the border box — flush with the edge, so the ring's outer side sat on the page itself
   rather than on the `accent` fill, even though the ring clears 6.07:1 light / 8.07:1 dark against
   that fill, the only pair `build-tokens.test.mjs` asserted at the time. This was not the
   fill-vs-surface trade-off DS-10's own reasoning accepted (`color-tokens.md` §5): §5 rings the
   control **inward** precisely "so that both of its adjacent colours are the accent fill," and a
   ring flush with the edge does not do that — it was a geometry defect in the two call sites, not a
   pair §5 ever agreed to draw. `Callout`'s `FocusVisible` story comment and `shared-primitives.md`
   also described this ring without naming which adjacency any contrast number was measured against,
   compounding the gap with a passage a reader could not check against the geometry themselves.
   **Not accepted — fixed.** The user decided to make §5 true rather than widen its acceptance: T586
   (commit `a3050c30`) moved both rings to `-outline-offset-4`, leaving a 2px band of `accent` fill
   between the ring and the control's edge on every side, so both of the ring's adjacencies are now
   the fill §5 always meant, guarded against regressing by
   `packages/design-system/tokens/accent-contrast-ring.test.mjs`'s geometry assertion. T582 then did
   the row's remaining work now that the pair being asserted had changed: renamed and re-commented
   `build-tokens.test.mjs`'s existing accent-contrast assertion to say it covers both of the ring's
   sides and why it depends on the geometry test rather than adding a ring-vs-surface assertion — that
   pair is no longer drawn, and asserting an undrawn pair would be the same false claim in the other
   direction — and corrected every passage across `shared-primitives.md`, `privacy-data-rights.md`,
   `manual-upload.md` and `archival-control.md` that named this ring's old `-outline-offset-2` or
   left its adjacency unstated, including this register's own DS-10 closure narrative above, which
   still cited the pre-T586 offset. **Owner: T582. Closed 2026-09-11.**
2. **M1 — a colour wash presented as the "non-colour" half of FR-037 is both the wrong category and,
   in the dark theme, close to imperceptible — closed.** `Link`'s `standalone` variant
   (`structural-tier.md` §9's `active` bullet) and `PrivacyNotice`'s `Contents` entries
   (`privacy-notice.md`'s `active` bullet, `index.tsx`'s `active:bg-surface-sunken`) both added a
   `surface-sunken` fill on press with no other change, and `privacy-notice.md` named it "the second
   signal its own shape owes" — a wash is a colour change, not the non-colour signal FR-037's "more
   than colour" half asks for (the distinction `Button/index.tsx`'s own comment and
   `shared-primitives.md` draw for `secondary`/`destructive`, the fifth/sixth-pass remediation row 1
   above closed). Measured, the wash was also faint: `surface-sunken` against the resting fill it
   replaces contrasts 1.18:1 in the light theme and **1.07:1 in the dark theme** — both far under any
   floor this system asserts elsewhere, meaning `Link`'s `ActiveStandalone` story and
   `PrivacyNotice`'s `Contents` press frame were technically distinct still images (FR-037's literal
   "never byte-identical" half held) but not observably distinct to a reader, which is not what
   either half of FR-037 is for. **Not accepted — fixed.** Both call sites now carry
   `active:ring-2 active:ring-border-strong` beside the kept `surface-sunken` fill: the same
   box-shadow-backed `ring` idiom `Button`'s `secondary`/`destructive` variants and
   `PrivacyNotice`'s own `ObjectionCallToAction` anchor already carry, proven (not merely assumed)
   to paint by compiling `tokens/tailwind.css` with `@tailwindcss/vite` and reading the emitted
   rule: `.active\:ring-2:active` resolves to a real `box-shadow` declaration and
   `.active\:ring-border-strong:active` sets `--tw-ring-color: var(--ds-color-border-strong)` — the
   same trap `Button/index.tsx`'s comment records for `active:outline-*` does not apply here because
   `ring` never touches `--tw-outline-style`. `border-strong` clears the 3:1 non-text floor against
   every surface the README contrast table measures it on, in both themes, so it holds regardless of
   which surface a `standalone` link — which has no one fixed placement today — ends up rendering on,
   and against `background` specifically, what `Page` paints behind `PrivacyNotice`'s `Contents` nav.
   No new contrast row was needed: all four `border-strong` rows already existed. `structural-tier.md`
   §9 and `privacy-notice.md` now name the ring, not the fill, as the non-colour signal.
   `Link.test.tsx` and `PrivacyNotice.test.tsx` assert the ring class is present and that
   `active:outline` is never relied on alone (both failed against the pre-fix tree, pasted in the
   task's own record); `Link`'s `inline` variant is asserted to never gain the ring, pinning FR-037's
   boundary rather than asserting "every link rings". `Link`'s `ActiveStandalone` story (a lone
   `standalone` link, no `nth` needed) and `PrivacyNotice`'s `Active` story (`nth: 0`, confirmed by a
   vitest `getAllByRole('link')` render to resolve to the first `Contents` entry, `#who-we-are`, in
   this component's DOM order) both move a baseline for this fix — regenerated from CI in a follow-up
   commit, per this package's own no-local-Chromium discipline. **Owner: T583. Closed 2026-09-11.**
3. **L1 — a story's own responsive-viewport pin or its own state/variant class can make its baseline
   byte-identical to another story's, independent of whether the two document the same fact —
   closed.** `scripts/checks/story-baselines-duplicates.mjs` (T584) does the full pairwise audit the
   fifth/sixth-pass remediations could not (out of a docs-only pass's scope): every story's own
   six-capture set ({light, dark} x {375, 768, 1280}), hashed and compared against every other's,
   across the whole tree — 540 stories, zero unmapped either direction. It found **25 full-set
   (six-of-six) matches** and **8 partial matches** (one width or theme differing, the ordinary shape
   responsive collapse produces — reported by the check, never failed): `Dialog`'s
   `FocusVisible`/`KeyboardFocusOrderAndTrap` and `ProfileSummary`'s `Board`/`BoardMobile` and
   `Board`/`BoardRatingsCardsBelowLg` (5/6 each); `UploadControl`'s
   `RealSelectionThenSuccess`/`Succeeded`, `ProfileSummary`'s `BoardMobile`/`BoardRatingsCardsBelowLg`,
   and the `Menu` `ProfileSwitcher`/`Selection`/`SheetBelowMd` trio, pairwise (4/6 each) — that trio is
   exactly the pair the fifth/sixth-pass remediations already named as a deliberate equivalence
   (`Menu.stories.tsx`'s own T569 comment), but the audit itself only ever _requires_ an account of a
   **full** match; a partial one is not converted to the check's own `visual-equivalence` marker
   syntax, so T569's prose comment is left as it was, not force-fit into a mechanism whose own
   validity check would otherwise flag it as covering a pair that is not (quite) currently identical.
   Each of the 25 full matches is either a genuine, deliberate equivalence — documented with a
   `// visual-equivalence: <story-id>: <reason>` comment the check parses and validates (stale if the
   pair ever stops matching) — or a real gap, tracked as a dated debt entry in
   `scripts/visual/story-baseline-duplicates-debt.json` rather than laundered as deliberate:

   - **Deliberate (24 groups, one `visual-equivalence` marker graph each):**
     - A `reviewWidthNarrow`/`globals.viewport` pin (or a bare "375/mobile/small-viewport" name with
       no pin at all) overridden by the visual suite's own 375/768/1280 capture axis (T504) —
       `AnalysisTimeline` `Published`/`StackedColumnsBelowMd`; `FavouritesList` `Default`/
       `StackedBelowMd`; `ReplayAvailabilityList` `RealisticMatch`/`StackedRowsBelowMd`; `MatchRow`
       `ListPopulated`/`ListCardsBelowXl`; `SiteHeader` `SignedIn`/`SmallViewport`; `UploadControl`
       `FileChosen`/`FileChosenMobile`; `PrivacyNotice` `Default`/`MobileViewport`.
     - A `size="md"` story equalling its component's own default size (`index.tsx`'s `size = 'md'`)
       — `CivilisationIcon`, `MapThumbnail`, `PlayerAvatar` `Default`/`Loaded` vs. `SizeMd`.
     - A spec-mandated pixel-identical error/empty pair (`onError` removing an image, its frame and
       any dependent surface together, leaving the same empty render as the uncovered case) —
       `CivilisationIcon` `FailedImage`/`UncoveredCivilisation` (civilisation-icon.md §4);
       `CountryFlag` `FailedImage`/`UncoveredCountry` (country-flag.md §11.4); `MapThumbnail`
       `FailedImage`/`UncoveredMap` (map-thumbnail.md §4); `PlayerAvatar` `AbsentHash`/`FailedHash`/
       `NullHash` (player-avatar.md §4 "empty" and §9's own acceptance criterion);
       `PlayerColourSwatch` `NotRecorded`/`OutOfRange` (player-colour-swatch.md §4).
     - A composite that renders as its wrapped primitive alone, with no visible extra markup —
       `CaptureStateBadge` `Archived`/`StillCatchableNoDeadline` equalling `Badge`'s own `Success`/
       `Warning` stories (capture-state-badge.md §2's own "two elements, never more", no
       `SecondaryLine` in either case).
     - A "renders nothing" case shared verbatim across component files: the payload renders `null`,
       and the demonstrating stories share the identical "Nothing renders below this line —" wrapper
       markup — `CaptureStateBadge` `Empty` / `CountryFlag` `NoCountryAtAll` / `PlayerColourSwatch`
       `BlankPlayerName` (three components, one shared affordance); `EmptyState`
       `NoContentRendersNothing` / `ErrorState` `NoHeadingRendersNothing` (structural-tier.md §12/§13,
       each independently "empty ... renders nothing").
     - A prop distinction that is invisible in the rendered frame, per the component's own contract
       — `MatchRow` `ListOtherSubjectPopulated`/`ListPopulated`: `subject="other"` changes only the
       `<table>`'s `captionHidden` (sr-only) caption and the `<ul>`'s `aria-label`, both invisible
       (match-history.md §11.3/§11.6); `PlayerResultRow` `NoUnverifiedSteamClaimKnown`/
       `SourceBacked`: `index.tsx`'s `!= null` check renders an explicit `null` exactly like the
       omitted (`undefined`) field `SourceBacked`'s own fixture already carries (player-search.md
       §4a); `FavouriteToggle` `Marked`/`MarkedAtLimit`: §5's own "bounded" paragraph — `atLimit`
       only affects the unmarked→add direction, "a favourited profile is never blocked by the bound";
       `Tooltip` `Blank`/`Loading`: both hit the component's one `isBlank` branch by design (§4
       "loading"); `Tooltip` `Default`/`DismissedAfterBlur`: §10's own acceptance criterion asks only
       for "no surface anywhere in the frame" after a blur dismiss, which the untouched resting frame
       already satisfies; `DataExportPanel` `Empty`/`Idle`: the story's own name already says
       "identical rendering to Idle" (privacy-data-rights.md §5 "empty").
   - **Suspect (1 group, tracked as debt, then fixed):**
     `MapThumbnail`'s `Loading` and `PlayerAvatar`'s `Loading` rendered byte-identical, but not for a
     reason either story's name claims. `MapThumbnail`'s own render pairs a block `Skeleton` with a
     `Skeleton variant="text" className="w-24"` meant to depict the map name loading beside it, but
     `Skeleton`'s `text` branch (`packages/design-system/src/primitives/Skeleton/index.tsx`) never
     applied the caller's `className` to size the line — confirmed independently reproducing on
     `CivilisationIcon`'s own `Loading` story, which pairs a `Skeleton` the same way — so the second
     skeleton rendered at an indeterminate width and was invisible in the captured frame, leaving
     only the one block skeleton `PlayerAvatar`'s `Loading` also shows (which never had a second
     skeleton by design — its own render has no accompanying text). Recorded, at the time this row
     closed, in `scripts/visual/story-baseline-duplicates-debt.json`: found 2026-09-11, fix by
     2026-09-25 — not fixed by T584 itself, whose own scope was the check and the register, not this
     defect. **Fixed 2026-09-12**: the `text` branch now carries the caller's `className` on the
     flex-column wrapper it returns, not on each line — the per-line widths (`textLineWidths`) vary
     60–90% of that footprint on purpose (the `lines` doc comment above), so applying `className` to
     every line instead would have flattened that variance rather than sizing the stack, and the
     `block` branch, which already applied it, was left untouched. `Skeleton.test.tsx` gained "carries
     the caller className on the text variant, sizing its footprint" (failed against the pre-fix tree:
     `Received: flex flex-col gap-2`, no `w-24`) and its contrast, "carries the caller className on
     the block variant (contrast: already worked)", which already passed. The debt entry itself
     stays in `scripts/visual/story-baseline-duplicates-debt.json` until this package's baselines are
     next recaptured from CI: the check reads the PNGs on disk, and `composite-mapthumbnail--loading`
     / `composite-civilisationicon--loading` are still the old, indeterminate-width captures as of
     this commit, so the group is still a full six-of-six match and the entry is not yet stale —
     removing it here would fail the check's "undocumented full match" case against baselines this
     commit cannot move. A follow-up commit regenerates those baselines from CI and removes the debt
     entry in the same commit, once the group is genuinely no longer a match.

   **Regenerated baselines exposed a defect in the check itself, 2026-09-12 (this task) — fixed, and
   the promised follow-up above landed in the same commit.** Two `chore(visual): regenerate baselines
from CI` commits on this branch moved 79 of the tree's ~540 stories' baselines by nothing but
   anti-aliasing noise (a handful of pixels each, a channel delta in the single digits), and that
   noise alone flipped three groups' classification under the check's original byte-identity
   comparison: `CivilisationIcon` `FailedImage`/`UncoveredCivilisation` and `PlayerAvatar`
   `SizeMd`/`Loaded` (both already marked deliberate, above) went "stale" because one width's hash no
   longer matched a hair's-breadth mutation — 3 and 26 pixels respectively, out of six-figure pixel
   counts — even though nothing about either pair actually changed; `MapThumbnail`/`PlayerAvatar`
   `Loading` (the Suspect entry above) genuinely stopped matching, moving 1276-52768 pixels — three
   orders of magnitude more — confirming the fix landed. A check that flags a marker "stale" every
   time the renderer's own noise happens to land on the byte it hashed, indistinguishable from a real
   fix, is one people learn to ignore. `scripts/checks/story-baselines-duplicates.mjs` now treats two
   captures as a duplicate when they are indistinguishable _to the visual suite itself_ — the fraction
   of differing pixels at or under `DUPLICATE_MAX_DIFF_RATIO` (0.01), `playwright.config.ts`'s own
   `maxDiffPixelRatio` for a story capture — rather than requiring byte equality; the check's own
   header carries the full reasoning and the pngjs-based implementation. Reconciled against the real
   tree under this definition:
   - The two falsely-stale markers above are valid again, with no story or comment change needed —
     3px/119808 and 26px/40474 are both far under 1%.
   - `MapThumbnail`/`PlayerAvatar` `Loading` no longer matches at all (every one of its six units now
     exceeds the ratio by at least 10x), so the debt entry is removed from
     `scripts/visual/story-baseline-duplicates-debt.json` — the fix this row already recorded as
     "Fixed 2026-09-12" is now also reflected in the baselines the check reads, closing the loop the
     paragraph above left open.
   - Four groups the tolerance now reaches were previously counted among the "8 partial matches"
     above and, being partial rather than full, needed no marker at the time — the same 0.01 ratio
     that clears the noise above also clears these, all of them 3-26 pixels out of six-figure pixel
     counts per differing unit, and each is a benign mechanism already established elsewhere in this
     register or in the story file's own prose, now given the machine-readable marker: the `Menu`
     `ProfileSwitcher`/`Selection`/`SheetBelowMd` trio (T569's own prose, quoted at the top of this
     row, finally converted into the marker syntax now that it is a full rather than partial match);
     `ProfileSummary` `Board`/`BoardMobile`/`BoardRatingsCardsBelowLg` (the same
     `reviewWidthNarrow`-overridden-by-T504 mechanism as the first "Deliberate" bullet above, plus
     `BoardMobile`'s args being verbatim `Board`'s, the same shape as `UploadControl`
     `FileChosen`/`FileChosenMobile` in that same bullet); `UploadControl`
     `RealSelectionThenSuccess`/`Succeeded` (the real upload sequence resolves to the same `succeeded`
     state the static story already pins); `Dialog` `FocusVisible`/`KeyboardFocusOrderAndTrap` (both
     stories' own comments already say the forced `:focus-visible` frame and the real Tab-driven
     sequence's resting frame are "its still-image counterpart" of one another). Between them, the
     `Menu` trio and the `ProfileSummary` trio each account for all three of their own pairwise
     partial matches (a 3-member group has three edges), so all 8 of the original partial matches are
     now covered by these 4 groups, none left over. The tree now has **28 full-set groups** (the
     original 24 deliberate groups, unaffected by the dissolved Suspect entry, plus these 4) and **0**
     partial matches. `scripts/checks/story-baselines-duplicates.test.mjs` gained a pixel-fixture test
     pinning the tolerance directly (paired PNGs a handful of pixels apart count as
     a duplicate, well-apart ones do not — failed against the pre-fix byte-identity implementation
     with an import error, since neither `pixelDiffRatio` nor `DUPLICATE_MAX_DIFF_RATIO` existed to
     import).

   **Owner: T584. Closed 2026-09-11.**

4. **L2 — `SiteHeader`'s `Selection` and `SignedIn` stories carried byte-identical `args`
   (`SiteHeader.stories.tsx:25-38`, both `{ items, currentPath: '/dashboard' }`) — closed.** The
   review reported two things; each is handled on its own:
   - **The duplicate `args` — not accepted, fixed.** `Selection` now marks `My data` (§3a's _last_
     item, `currentPath: '/privacy'`) current rather than `Dashboard`, so its `args` differ from both
     `SignedIn`'s (`Dashboard` current) and `CurrentIsNestedRoute`'s (`Matches` current, via the
     nested-route rule) — three stories, three distinct current items, none reachable from another by
     `args` alone. That also exercises something neither of the other two shows: the current-route
     rule and weight change sitting on the row's own last item rather than its first or second. The
     story's rewritten comment states this directly, replacing the old one that (correctly, at the
     time) said the duplication was deliberate. `SiteHeader.test.tsx` composes all three stories
     (`composeStories`, the portable-stories API `story-a11y.test.tsx` already uses) and asserts their
     `aria-current="page"` items differ pairwise — failed against the pre-fix `Selection` (two
     assertions red, `expected 'Dashboard' not to be 'Dashboard'` and `expected 'Dashboard' to be 'My
data'`) and green after. Baselines regenerated from CI in a follow-up commit, per this package's
     own no-local-Chromium discipline.
   - **The second claim — the selection mark rendering inside a closed `Menu`/sheet at some captured
     width — checked against the checked-in baselines and not reproduced.** Method: md5 of
     `composite-siteheader--selection` against `composite-siteheader--no-current-item` and
     `composite-siteheader--current-is-nested-route`, per width (375/768/1280) and theme (both
     `signedIn`/`selection` were also byte-identical to each other at all six, confirming the
     duplicate above). The pair differs at every one of the six captures, 375 included, so the current
     item's underline is visible below the `md` breakpoint, not hidden behind a closed disclosure —
     this remediation still cannot drive a browser to confirm the frame directly, but the file-level
     evidence available to it does not support the claim. Recorded, not dismissed: if it reproduces
     later against the now-distinct `Selection` baseline, that is a new finding, not evidence this
     closure got wrong. **Owner: T585. Closed 2026-09-11.**

5. **H2 — `DataExportPanel`'s download link signals press with a ring that cannot be seen, and no
   story captures the state — open.** The link fills with `accent` and draws its press ring outward:
   `active:ring-2 active:ring-offset-2 active:ring-offset-transparent active:ring-accent-contrast`
   (`src/screens/DataExportPanel/index.tsx`). A transparent offset puts that ring on the surface
   behind the link, and the link renders inside a `success` `Callout`, whose fill is
   `bg-surface-raised` (`src/primitives/Callout/index.tsx`). `accent-contrast` **is**
   `surface-raised` in the light theme, so the ring measures 1.00:1 there and 1.24:1 in the dark
   theme: the non-colour half of FR-037 is painted where it cannot be seen. This is H1's mechanism
   in the press state, found on 2026-09-11 while verifying T586's regeneration, and T586 fixed only
   the focus ring. Nothing captures it either: no story focuses or presses this link, and
   `DataExportPanel.stories.tsx`'s `HoverFocusActiveNotApplicable` says its states are "already
   covered by their own components' stories", which is untrue — the link is a local anchor, not a
   `Button`. So T586's own change to this link moved no baseline and is guarded only by
   `tokens/accent-contrast-ring.test.mjs`. The story coverage is **T587**; the ring itself is part of
   the decision below. **Fix by 2026-09-25.**
6. **H3 — an `accent`-filled control distinguishes rest, hover and press by fill luminance alone —
   open, needs a design decision.** `Button`'s `primary` steps `accent` → `accent-hover` →
   `accent-active` and adds no shape, mark, border or position at any step (`Button/index.tsx`), and
   `DataExportPanel`'s download link follows it. Measured with `tokens/contrast.mjs`: 1.26:1
   rest→hover and 1.28:1 hover→press in the light theme, 1.25:1 and 1.57:1 in the dark. FR-037 asks
   for "more than colour", and this register's own bar (above) says a difference carried by a hue
   shift alone is not reviewable from a still image; whether a luminance step of this size satisfies
   it has never been decided, and six adversarial passes closed `secondary`, `ghost`, `destructive`,
   `Link` and `PrivacyNotice` without asking it of the most prominent control in the system. The
   same question governs what replaces row 5's invisible ring, and FR-038 requires both controls to
   answer it the same way. Not a defect this register may close on its own: `product-designer` owns
   the signal's shape. **Owner: T588. Fix by 2026-09-25.**

Also recorded, not registered here because each is a two-minute fix rather than an open gap:
`Link.stories.tsx:47-60`'s `RestAndHover` story is renamed `Rest` in the same change that lands this
register, because its own comment claimed the suite drives a real `:hover` for it and the story
carries no `visualForceState` — its baselines are rest frames, and the name and comment said
otherwise (sixth-pass review, M2).
