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

## The baseline set, as it stands

**559 stories, 3,376 baseline PNGs** under `__screenshots__/`: 3,354 story captures — every story at
{light, dark} x {375, 768, 1280} — plus 22 `tests/visual/app-routes.spec.ts` captures, which are not
stories and are exempt from the six-per-story rule. This figure is stated once, here, and it is
trustworthy for one reason only: **`scripts/checks/story-baselines.mjs` asserts both numbers**,
against `EXPECTED_STORY_COUNT` and `EXPECTED_BASELINE_COUNT` in its own source, and fails naming this
section when either moves. It runs on every pull request **that reaches the `visual` job** — that
job's paths filter, not literally every pull request; the distinction costs nothing here, because a
change that moves either count necessarily touches `packages/design-system`, one of the paths that
filter selects on: the story count comes from the Storybook index, built from this package's own `src`
and nothing outside it, and the baseline count counts files under this package's `__screenshots__/`.
`nightly.yml` also runs the check unfiltered. That assertion is separate from the set equality the
same check performs between the built Storybook index and the files on disk, and it has to be: set
equality alone stays green when a story is added, because the new story does have its six captures —
which is exactly how this paragraph would go stale without anyone touching it.

It is not the 1,794 captures over 299 stories feature 005's own
[verification matrix](../../../specs/005-design-system-foundations/contracts/verification-matrix.md)
sized: that was the count at design time, and the feature's own work — the state stories the closed
state vocabulary requires of every component, and the clipped state stories the register below ends
with — added the rest. A frozen forecast and a measured fact are different claims; neither is
corrected by editing the other.

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

**DS-11 closed 2026-09-12 (T589)**, found the same day by adversarial review finding S4; the six
gaps this feature already closed, below, remain closed. This section holds open token decisions when they
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

**Closed — DS-11 (T589, 2026-09-12).** `border.json`'s `ring-offset` named only the positive 2px
focus-ring offset; the negative form a genuinely inward, non-`ring-offset-inset` ring needs had no
member of its own. Four call sites wrote a bare, untokenised `-outline-offset-2` — `MatchRow`
(`src/composites/MatchRow/index.tsx`), `FavouritesList`
(`src/composites/FavouritesList/index.tsx`), `PlayerResultRow`
(`src/composites/PlayerResultRow/index.tsx`) and one of `Menu`'s three focus rings
(`src/primitives/Menu/index.tsx`) — the same class of breach `-outline-offset-4` was in before T586
admitted `ring-offset-inset` to name it. `border.json` now admits `ring-offset-inset-flush` (-2px,
GOVERNANCE.md's token admission Record), a second, distinct inward offset — magnitude equal to,
not exceeding, the ring's own width, because this ring is the ordinary `focus-ring` role against a
row's or menu item's own surface, never `accent-contrast` against an `accent` fill, so
`ring-offset-inset`'s "strictly exceed the width" condition does not apply here. All four call
sites now write `outline-offset-ring-inset-flush`, guarded by the new
`tokens/focus-ring-inset-flush.test.mjs` (mirroring `accent-contrast-ring.test.mjs`'s whole-tree
scan). The other half of this row — `scripts/checks/token-scale.mjs` being structurally blind to
the whole `outline-offset-N` Tailwind namespace — is also closed: the checker now fails a bare
`outline-offset-<N>` of either sign anywhere in a scanned string. Closing the namespace, not only
the four sites this row named, surfaced ten further call sites already carrying the bare _positive_
`outline-offset-2` (`Footer`, `SiteHeader`, `SearchBox`, `ThirdPartyObjectionForm`, `PrivacyNotice`,
`AccountErasurePanel`, `Tooltip`, `Button`'s outward variant, and two of `Menu`'s three rings) that
would otherwise have failed the moment the check learned the shape; all ten now write the
already-admitted `outline-offset-ring` (T514) instead, a mechanical, render-identical rename with
no new token needed. **Left open, not this row's scope (T588's 2026-09-12 note, restated so it is
not lost with the row it was attached to):** the checker's blindness is not limited to
`outline-offset-N` — `Button`'s and `DataExportPanel`'s `decoration-2`/`underline-offset-2`/
`underline-offset-4` classes (Contrast-signal gap register, row 6/H3, below) sit in the same
untokenised, bare-Tailwind-utility shape, for the same reason `Link`'s own decoration/
underline-offset classes already do. T589's own scope was `outline-offset`; widening the checker to
the decoration-thickness/offset namespace as well is a decision for whoever opens the row that
covers it, not something this closure invents in passing.

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

**Row 1 closed 2026-09-11 (T579), owed since 2026-09-08** (third-pass adversarial review, finding
M2a); **row 2 closed 2026-09-12 (T590), open since 2026-09-12** (adversarial review finding S8).
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

2. **`accent-contrast-ring.test.mjs`'s two guards (T586) do not see every way an accent-contrast
   ring can stop being drawn on the fill it depends on — found 2026-09-12 (adversarial review
   finding S8).** The file caught a `bg-clip-*` override and a painted border on an
   accent-contrast-ringed control (`checkFillAssumptionFindings`), but not: a state-variant fill
   override — `hover:bg-*` or `focus-visible:bg-*` changing the fill in the very state the ring
   paints, the state DS-10's contrast numbers assume is showing; a background image or gradient
   painted over `bg-accent` instead of a solid override, which neither `BG_CLIP_RE` nor
   `PAINTED_BORDER_COLOR_RE` recognises as changing the fill; or an `apps/web` caller passing
   `bg-clip-padding` (or any other fill-defeating class) through `Button`'s merged `className` prop
   — the scan is lexical and reads only `packages/design-system/src`, never a call site outside this
   package. **Closed 2026-09-12 (T590), two of three.** A third guard,
   `checkStateFillAndImageFindings`, now catches the first two: a variant-prefixed `bg-<colour>`
   utility beside a resting `bg-accent` fill is a finding unless the colour it repaints onto is one
   of the three the accent ramp's own contrast proof already covers (`accent`, `accent-hover`,
   `accent-active` — `build-tokens.test.mjs`), and a gradient or arbitrary background-image utility
   beside `bg-accent` is a finding outright, prefixed or not, because it paints over
   `background-color` rather than replacing it. Checked against `Button` primary's own
   `hover:bg-accent-hover`/`active:bg-accent-active` (present before T588 and untouched by it): both
   targets are on the ramp, so the new guard passes the real code and — proven by injecting the
   regression and reverting it — would have failed had T588 swapped either to an unproven colour.
   The new guard is grouped by `cx()` call rather than by single literal, because
   `DataExportPanel`'s download link threads its resting fill and its `hover:`/`active:` overrides
   through separate arguments of one `cx(...)` call — a same-literal scope, adequate for the first
   two guards, would never see that real shape's overrides at all. The third blind spot, an
   `apps/web` caller's `className` defeating the fill through `Button`'s merged prop, is
   **deliberately deferred, not fixed here**: closing it needs either a second lexical pass over
   `apps/web/src` for a fill-defeating class reaching a design-system call site (the same shape
   `token-scale.mjs`'s own `apps/web` layout-class pass already uses, over a different tree and a
   different property) or a runtime assertion inspecting resolved computed style, which needs a real
   layout engine jsdom does not have. Writing either speculatively — before a real instance of this
   defect has shipped — would blur this token-level test's boundary (the design system's own
   contract) with call-site linting over application code, which is a separate, independently-run
   check's job whenever it becomes a real defect, not this file's. Recorded rather than silently
   dropped: `Button`'s `className` prop is merged last
   (`packages/design-system/src/primitives/Button/index.tsx`'s `cx(..., className)`), so nothing in
   this package stops a caller from winning the cascade today.

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
2026-09-11 (T582)**, **row 2 closed 2026-09-11 (T583)**, **row 3 closed 2026-09-11 (T584), reopened
and re-closed 2026-09-12 by a second adversarial review of the same remediation**, **row 4
closed 2026-09-11 (T585)**, **row 6 closed 2026-09-12 (T588)**. **Row 5's decision half was
answered by row 6's closure, and its focus and press frames landed after it (T587), deliberately in
that order so the frame shows the current control; its hover frame closed row 7 below (T593).**
**Row 7 (H4) was opened 2026-09-12 by `reviewer` reviewing these closures, and closed 2026-09-13
(T593).** **Row 8 (H5) was opened 2026-09-13 by `reviewer` reviewing PR #79; its sweep half was
rejected twice more (PR #80's hand-typed pass, then a second hand-typed pass, both for the same
partial-set shape one level down) before T594 was amended to require an extractor,
`scripts/checks/state-coverage.mjs`, and closed with that rebuild (producing findings F1-F20 below
and the F15/F16-carried-to-consumers finding), and is open on its fix half (T595, and T596 for the two anchors that await a design decision).**

**State of this register, enumerated rather than summarised:** rows 1, 2, 3, 4, 5, 6 and 7 closed;
row 8 open. This
sentence has been wrong twice in three commits — once as "every row is closed", once as "rows 1–6 are
closed" while row 5's own body said otherwise — which is why it now lists the rows instead of
grouping them: a range is a claim about rows nobody reread. Four findings the review judged
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
   across the whole tree — every story then in the tree, zero unmapped either direction (540 at the
   time; the current figure and the check that asserts it are "The baseline set, as it stands" above,
   which is the one place it is stated). It found **25 full-set
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
from CI` commits on this branch moved 79 of the tree's stories' baselines (see "The baseline set, as
   it stands" above for the count, stated once and asserted) by nothing but
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

   **A second adversarial review of this same remediation (2026-09-12) found and fixed two further
   defects in the check itself, plus one overstated claim, all in the pixel-tolerance work above —
   reopened and re-closed the same day.**
   - **`isPixelDiffCandidate` required a pair to already share at least one byte-identical unit
     before ever decoding it, on the claim (this file's own text above, at the time) that the real
     tree has no pair worth decoding otherwise — not accepted, fixed.** A rest/hover/press/focus pair
     typically shares _zero_ of its six units by hash (every one of the six captured frames carries
     the state change), so the restriction excluded exactly the shape this register exists to catch.
     `isSizeDimensionCandidate` (`SIZE_PROXIMITY_TOLERANCE`, 0.03) replaces it: a cheap filter — same
     pixel dimensions plus a compressed file size within 3%, a `stat` and a 24-byte PNG header, no
     unit needs to already match — that finds **20 further full-match groups** (37 individual
     pair-edges) the byte-sharing restriction structurally could not reach. Every one is a
     rest/hover/press/focus pair or an otherwise-meant-to-differ pair, never laundered as deliberate:
     `PrivacyNotice` `Active`/`Hover`, `SiteHeader` `Active`/`Hover`, `Menu` `Active`/`Hover`,
     `MatchRow` `Active`/`Hover`, `Footer` `Active`/`Hover`, `FavouritesList` `Active`/`Hover`,
     `PlayerResultRow` `Active`/`Hover`, `Table` `RowLinkActive`/`RowLinkHover`, `UploadControl`
     `FocusVisible`/`Idle`, `ThirdPartyObjectionForm` `Active`/`Hover` and `FocusVisible`/`Idle`;
     `PrivacyNotice`'s `FocusVisible` and `Menu`'s `FocusVisible`/`KeyboardNavigation` folding into
     the existing `Default`/`MobileViewport` and `ProfileSwitcher`/`Selection`/`SheetBelowMd` marker
     groups respectively (each promised a visible ring or a different focused row that the whole-page
     capture does not resolve); `CountryFlag`'s `Default`/`FlagDismissedAfterEscape` and its own
     hover/keyboard-focus/pinned reveal trio, and the identical shape in `Tooltip` and in
     `ProfileSummary`'s embedded `BoardFlag`; `ProfileSummary`'s `NoCountry` folding into the
     `Board`/`BoardMobile`/`BoardRatingsCardsBelowLg` trio (the flag and its label are absent by
     design, 004 FR-008, but too small a fraction of a full-page capture to move its ratio); and
     `PlayerColourSwatch`'s `Blue`/`SizeSm`/`SizeXs` (different colours, names and chip sizes,
     indistinguishable only because the whole-page capture cannot resolve a chip this small). Each is
     a dated debt entry in `scripts/visual/story-baseline-duplicates-debt.json` (found 2026-09-12, fix
     by 2026-09-26) naming what should differ and does not, not a `visual-equivalence` marker.
     `story-baselines-duplicates.test.mjs` gained a fixture pinning the fix directly — a pair sharing
     none of its six units by hash, each one within tolerance — failed against the pre-fix
     implementation (`groups: []`: a pair `findPartialMatches` never reports as partial is never
     offered to a decode at all under the old restriction) and green after. The check's own runtime
     moved from well under a second to roughly 16 seconds against the real tree (208 candidate pairs
     of 145,530 decoded) — the cost of actually looking; still fast enough to run on every change.
   - **This file's and the check's own header's claim that noise and a real change "separate ... by
     three orders of magnitude" overstated what the 2026-09-12 regeneration's own two data points
     support, once generalised past them — not accepted, corrected.** That gap was real for the two
     specific cases it measured (the noise-only pairs above, and `MapThumbnail`/`PlayerAvatar`
     `Loading`'s genuine fix); it is not a property of the threshold in general. Decoding the fuller
     candidate set above shows pairs sitting on a continuum straddling 1%, not in two well-separated
     clusters — a documented full match and an undocumented non-match can sit within a hundredth of a
     percentage point of each other on opposite sides of the line. `DUPLICATE_MAX_DIFF_RATIO` (0.01)
     is this suite's own operating decision, the same one `playwright.config.ts` makes for a single
     capture, not a boundary the real tree's own pixel deltas happen to avoid; a future reader seeing
     this check fail or pass within a percentage point of the line should not infer which side is
     "really" noise from the ratio's distance to 1% alone. The check's own header carries the
     corrected reasoning and the near-threshold pairs measured.
   - **A promoted three-or-more-member group was trusted from union-find connectivity rather than
     verified as a true clique — latent, not an active defect, fixed before it could become one.** The
     ratio tolerance this check applies is not itself transitive (A~~B and B~~C within tolerance does
     not imply A~C is), so two valid pairwise promotions could in principle union a group whose own
     direct A-C edge exceeds the threshold — three stories asserted indistinguishable when only two
     pairs of them actually are. Measured against the real tree, including the new groups above
     (several of which unify through a shared member rather than every pairwise edge the cheap filter
     directly found), every reported group's own edges hold directly today — no violation exists —
     but `computeFullMatchGroups` now re-verifies every group as a full clique before returning it
     rather than assuming connectivity implies it, and fails the check outright ("transitivity
     violation") the moment one ever does not, rather than silently reporting a group that is not
     actually one fact.
   - **A marker on a pair the size/dimension filter did not directly reach validated while a debt
     entry on the same pair failed as stale — resolved as a consequence of the fix above, verified
     rather than assumed.** `evaluateMarkers` and `findStaleDebtEntries` both run against the same
     `computeFullMatchGroups` output as of this fix, so a pair either mechanism can see, the other now
     can too; no remaining asymmetry.

   **Owner: T584. Closed 2026-09-11; reopened and re-closed 2026-09-12.**

   **The 20 debt entries the size/dimension filter above found (T584's own list, immediately
   above) were addressed in the same task that opened them, 2026-09-12 — T591.** Each was one of
   two shapes, decided per entry, never laundered as the other: a component's own state signal was
   genuinely missing and is fixed in its source (`FavouritesList`, `Footer`, `MatchRow`,
   `PlayerResultRow`, `SiteHeader`, `Menu`'s trigger/item/footer item, `Table`'s row link — every one
   a press that repainted the same fill as hover with no second signal, now a full inset boundary
   `ring` on top of it, the same "a press is a boundary" idiom `Button`
   `secondary`/`destructive` and `Link` `standalone` already carry — **and that clause was a
   generalisation of four components onto eight, corrected 2026-09-12 after `visual-reviewer` read
   the captures and `reviewer` read the eight sources. Three idioms, not one, and the boundary is
   not always what T591 changed:**
   - **A press-only inset `ring` over the hover fill**, which is what the sentence above described:
     `FavouritesList`, `MatchRow`, `PlayerResultRow` (`active:ring-inset`) and `Table`'s row link
     (`active:after:ring-inset` on a pseudo-element, because a `<tr>` cannot carry the ring itself).
     These four are the sentence's real subjects.
   - **An outward `ring`**, no `ring-inset`: `Menu`'s trigger, and `Footer`, which draws no press
     state of its own and delegates to `Link` `standalone`. This is also what the two components the
     sentence cites as its idiom — `Button` `secondary` and `destructive` — actually carry, so the
     citation was right about the recipe and wrong about the geometry.
   - **A `border-strong` edge that already existed, plus a fill move**, which is where T591's change
     was the fill and not the boundary: `SiteHeader`'s nav item keeps its four-sided
     `active:border-border-strong` and moved its press fill off hover's `surface-sunken` to
     `bg-background`; `Menu`'s _items_ and footer item keep T560's 2px `border-strong` on the
     inline-start edge — which `shared-primitives.md`'s own Menu `active` entry specifies rather than
     a four-sided ring — and moved the same fill the same way. In both, the boundary alone was the
     mark the duplicate check could not tell from hover; the fill is what made the pair separable.

   A component's press signal is its own spec's. The only thing true of all eight is that **a press
   differs from hover by at least one non-colour signal, and which one is that component's own
   spec's decision** — four differ by a boundary alone, four by a boundary and a fill. An earlier
   attempt at this sentence said "a boundary **and** a fill, never by fill alone" and was false for
   the first four in a way worth recording rather than quietly deleting: their press deliberately
   paints hover's own fill, because a keyboard `Enter` fires `:active` with no pointer ever having
   hovered (T560, FR-038, stated in `FavouritesList/index.tsx`'s own comment for all four). A
   row-link's press must be legible **without** a fill change, so a rule demanding one would have
   forbidden the design FR-038 requires. That is the trap this paragraph has now fallen into twice:
   a summary written from the components in front of you, asserted over the ones you did not
   reread); or the signal exists but the
   frame was too large for the comparator to see it, and the story is scoped to the control that
   carries it instead of the whole page or the whole `#storybook-root` box (`CountryFlag`,
   `Tooltip`, `Menu`'s focus/keyboard stories, `PlayerColourSwatch`, `PrivacyNotice`,
   `ProfileSummary`'s name-line and its embedded `BoardFlag`, `ThirdPartyObjectionForm`,
   `UploadControl`'s `FocusVisible`) — the harness gained a second story parameter for this,
   `visualCaptureClip`, sibling to `visualForceState`: `parts` (one or more `selector`/`role`+`name`
   locators, unioned) and `pad` (a spacing-scale step name, never a px literal), clipping the
   capture to that union inflated by the pad, `tests/visual/stories.spec.ts`. **The standing rule
   this row leaves behind: a story that names a state whose signal is smaller than roughly 1% of
   its own frame is captured clipped to the control that carries it, via `visualCaptureClip`, rather
   than left to a whole-page or whole-root capture that cannot resolve it.** One entry's own wording
   was corrected in the same pass rather than carried forward: `UploadControl`'s
   `FocusVisible`/`Idle` debt text claimed the ring should show "across the Remove/SubmitButton/
   Refresh controls", but that story's own `initialState: 'idle'` renders none of those three — the
   real gap was only the trigger's own ring being too small a mark on the whole component's frame.
   Every one of the 20 debt entries stays in `scripts/visual/story-baseline-duplicates-debt.json`,
   each now carrying a `fixApplied` field naming what changed, rather than being deleted here: this
   check reads the baseline bytes on disk, which a source or story edit alone does not move, and
   deleting an entry the check still finds as a live full match would fail it before the next CI
   baseline regeneration lands (the same reasoning the `MapThumbnail`/`PlayerAvatar` `Loading` entry
   above already established for one entry at a time — this closes 20 the same way, not
   differently). **That follow-up landed the same day**, inside the squash this feature's history
   keeps it in — `c55850bb`, PR #77, which carries both the regeneration and the emptied
   `scripts/visual/story-baseline-duplicates-debt.json`; the pre-squash SHAs are deliberately not
   cited, because that branch is gone from the remote and a citation a fresh clone cannot resolve is
   no better than the promise it replaced. **What the empty file proves, stated at its real
   strength**: `scripts/checks/story-baselines-duplicates.mjs` fails on a full match carrying
   _neither_ a marker _nor_ an unexpired debt entry, so an empty debt file plus a green check means
   no group is an **undocumented** full match. It does not mean no group matches: the check still
   reports 28 documented full-set groups, two of them inside the emptied entries' own groups and held
   by equivalence markers, exactly as those entries' `fixApplied` notes said they would be. **And
   the count was 21, not the twenty this row says above** — `git show <the pre-squash tree>` had 21
   entries, every one found 2026-09-12; the "twenty" is an off-by-one carried from T591's own task
   text and is corrected here rather than in the frozen task. **Owner: T591. Closed 2026-09-12.**

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
   story captures the state — closed: decision (T588), focus and press frames (T587), hover frame
   (row 7, T593).**
   The link fills with
   `accent` and drew its press ring outward: `active:ring-2 active:ring-offset-2
active:ring-offset-transparent active:ring-accent-contrast` (`src/screens/DataExportPanel/index.tsx`).
   A transparent offset put that ring on the surface behind the link, and the link renders inside a
   `success` `Callout`, whose fill is `bg-surface-raised` (`src/primitives/Callout/index.tsx`).
   `accent-contrast` **is** `surface-raised` in the light theme, so the ring measured 1.00:1 there
   and 1.24:1 in the dark theme: the non-colour half of FR-037 was painted where it could not be
   seen. This is H1's mechanism in the press state, found on 2026-09-11 while verifying T586's
   regeneration, and T586 fixed only the focus ring. Nothing captured it either: no story focused or
   pressed this link, and `DataExportPanel.stories.tsx`'s `HoverFocusActiveNotApplicable` says its
   states are "already covered by their own components' stories", which is untrue — the link is a
   local anchor, not a `Button`. **Deleted rather than repositioned (T588).** Row 6's decision
   applies to any ring on an accent-filled control's edge, whatever colour it uses, so an outward
   ring here could never have been the fix regardless of its offset; the ring is removed and the
   link now carries the same label-underline signal `Button`'s `primary` variant does (row 6,
   below), guarded by `DataExportPanel.test.tsx`'s new assertions that the underline classes are
   present and the deleted ring classes are not. The story coverage — a real focus-visible and a real
   press frame over this link, proving the underline where the invisible ring used to be — was left
   open as **T587**, landing after this closure so its frame shows the current control rather
   than the one this row found. **The capture half landed 2026-09-12 (T587).** `ReadyFocusVisible`
   and `ReadyActive` (`DataExportPanel.stories.tsx`) drive a real `:focus-visible` and a real press
   over the download link, both sharing `Ready`'s `visualCaptureClip` on the link itself — the
   standing rule the T591 paragraph above leaves behind, applied here because the underline that
   replaced the deleted ring is a mark on one anchor inside a whole-screen frame. The story that
   made the false claim was corrected rather than deleted:
   `HoverFocusActiveNotApplicable` now says which of the two interactive elements it really defers to
   (`RequestButton`, an unmodified `Button`) and points at the two stories above for the link's own
   coverage. Also widened by the same `visual-reviewer` pass that opened this row
   ([quickstart.md](../../../specs/005-design-system-foundations/quickstart.md)'s addendum):
   `Button`'s `FocusVisible` hard-coded `variant: 'primary'`, so the outward `focus-ring` the other
   three variants keep was evidenced by a code read and no baseline —
   `SecondaryFocusVisible`, `GhostFocusVisible` and `DestructiveFocusVisible` are that evidence.

   **The capture half was two of three, found 2026-09-12 by `reviewer` re-reading this closure.** T588
   gave that anchor a hover signal as well as a press one — `hover:underline hover:decoration-2
hover:underline-offset-2` beside `active:underline-offset-4`, `src/screens/DataExportPanel/index.tsx`
   — and there was then no `ReadyHover` story and no `screens-dataexportpanel--ready-hover-*`
   baseline. So the corrected `HoverFocusActiveNotApplicable` still deferred a state the link owns, in
   the smaller shape this row was opened for: it named `ReadyFocusVisible` and `ReadyActive` as the
   link's coverage and was silent about hover. **The missing frame and the wording were row 7's, not
   this row's** — recorded there with `AccountErasurePanel`'s identical gap, because they are one defect in
   two components and fixing one alone is how this register keeps reopening. This row deliberately
   carries no `Owner:` for them: a closure record that also owns open work is a closure record nobody
   revisits when the work lands, and then the two copies drift. **Decision and the focus/press frames
   closed 2026-09-12 (T586, T588, T587); the hover frame closed 2026-09-13 with row 7 (T593).**

6. **H3 — an `accent`-filled control distinguishes rest, hover and press by fill luminance alone —
   closed.** `Button`'s `primary` stepped `accent` → `accent-hover` → `accent-active` and added no
   shape, mark, border or position at any step (`Button/index.tsx`), and `DataExportPanel`'s
   download link followed it. Measured with `tokens/contrast.mjs`: 1.26:1 rest→hover and 1.28:1
   hover→press in the light theme, 1.25:1 and 1.57:1 in the dark. FR-037 asks for "more than
   colour", and this register's own bar (above) says a difference carried by a hue shift alone is
   not reviewable from a still image; whether a luminance step of this size satisfies it had never
   been decided, and six adversarial passes closed `secondary`, `ghost`, `destructive`, `Link` and
   `PrivacyNotice` without asking it of the most prominent control in the system. **Verdict:
   luminance alone does not satisfy FR-037** — the measured steps above are 1.25–1.57:1, a
   difference no still image carries, matching this register's own row-2 (M1) reasoning that a
   colour-only signal this faint is not what either half of FR-037 asks for. **Mechanism, decided by
   `product-designer`:** an `accent`-filled control may not distinguish rest, hover and press by
   fill alone, and it may not ring outward for press either — DS-10's proof (`color-tokens.md` §5)
   that no colour clears 3:1 against both the page and an accent fill at once applies to any ring
   whose adjacencies are the page and an accent fill, whatever its colour, which is what governed
   row 5's invisible ring as much as this row's fill steps (FR-038 binds both to the same answer).
   The non-colour signal is drawn inside the fill instead, in `accent-contrast` — the label's own
   ink at every state — and clear of the inward focus ring's edge band (T586): the label underlines
   on hover (`decoration-2`, `underline-offset-2`) and drops to `underline-offset-4` on press,
   thickness for hover and position for press, the same two axes `Link` already uses
   (`structural-tier.md` §9). `Button`'s `primary` variant and `DataExportPanel`'s download link
   both carry it now (`Button/index.tsx`, `src/screens/DataExportPanel/index.tsx`); every
   `accent`-filled control added later follows this, and its press state is captured as its own
   component-scoped story so the signal is larger than the comparator's tolerance (`Button.test.tsx`
   and `DataExportPanel.test.tsx` assert the classes; `shared-primitives.md` and
   `privacy-data-rights.md` name the mechanism). **Not caught by `scripts/checks/token-scale.mjs`:**
   `decoration-2`, `underline-offset-2` and `underline-offset-4` are bare Tailwind utilities in the
   decoration-thickness/offset namespace, the same kind of namespace the checker was structurally
   blind to that DS-11 (Token gap register, above, closed by T589 for `outline-offset` only) named —
   reached the same way `Link`'s own `decoration-1`/`decoration-2`/`underline-offset-4` are
   (`Link/index.tsx`'s own comment): the nearest bare utility in the closed set, because no
   `border.json` token names a decoration thickness or an underline offset. Left as a note here
   rather than folded into DS-11's own fix, which was T589's scope, not this row's. **Owner: T588.
   Closed 2026-09-12.**

7. **H4 — two local anchors had a state signal changed with nothing capturing it, and each
   component's own `*NotApplicable` story deferred a state it in fact owns — closed, both of them
   (T593).** These were one defect in two components; the first sweep found one, which is why this
   row named both and why T593 closed both together. `reviewer` had checked the other thirteen
   source files #77 touched: the rest are either rendering-identical T589 offset renames or a real
   state change with a story behind it, and these two were the only `*NotApplicable` stories
   deferring a state they own.

   **`DataExportPanel`'s download link — the hover frame, and the wording (row 5's remainder).** T588
   gave the link `hover:underline hover:decoration-2 hover:underline-offset-2` alongside its press
   change; `ReadyFocusVisible` and `ReadyActive` were added for focus and press, and no `ReadyHover`
   was. `HoverFocusActiveNotApplicable` named those two as the link's coverage and said nothing of
   hover. **Fixed**: `ReadyHover` added under the same `visualCaptureClip` the other `Ready*` stories
   share, and `HoverFocusActiveNotApplicable`'s wording corrected to name all three states.

   **`AccountErasurePanel`'s `ErasedScreen` link — no state capture at all.**
   T591 gave that anchor the underline recipe its two siblings got in the same task
   (`decoration-1 underline-offset-2 hover:decoration-2 active:decoration-2 active:underline-offset-4`,
   `src/screens/AccountErasurePanel/index.tsx`), under its own instruction of "all three or none".
   The other two got the stories with it: `PrivacyNotice` and `ThirdPartyObjectionForm` each carry
   `Hover`, `FocusVisible` and `Active` under a link clip. `AccountErasurePanel.stories.tsx` carried
   none, and its `HoverFocusActiveNotApplicable` stated that hover, focus and active "belong to the
   buttons, the dialog's actions and the acknowledgement checkbox, each already covered by their own
   components' stories" — false of this anchor, exactly as row 5 (H2) was false of
   `DataExportPanel`'s download link, and false in the same way: a local anchor styled inside a screen
   is covered by no other component's stories. Found 2026-09-12 by `reviewer`, on a
   `visual-reviewer` PASS that had to be withdrawn: a method that judges committed baselines is silent
   on a state no baseline depicts, and silence is not a pass. **Fixed**: `ErasedScreenHover`,
   `ErasedScreenFocusVisible` and `ErasedScreenActive` added under a clip over `ErasedScreen`'s link,
   the same shape its two siblings carry, and `HoverFocusActiveNotApplicable` reworded to name the
   buttons/dialog/checkbox states it still defers and to say the local anchor's own states are not
   among them.

   **Owner: T593, both components. Closed 2026-09-13.**

8. **H5 — row 7's sweep was scoped to the files #77 touched, and the same defect sits outside it —
   open.** Row 7 says its two anchors were the only `*NotApplicable` stories deferring a state they
   own **among #77's files**, and that held only for #77's files. `reviewer`'s pass over PR #79
   (2026-09-13) read past that boundary and found the same shape in three more components, and later
   passes found a fourth item one level down, in a primitive's own stories; those later passes were
   themselves partial, which is exactly the premise T594 was opened to test. **The orchestrator
   rejected T594's first hand-back, 2026-09-13, for repeating that same partial-set shape in five
   places** — two of seventeen primitive matrices built, conclusions asserted without their records, a
   grep standing in for "read in full," the `apps/web`-composed handoff dropped, and three generic
   deferrals waved through as "cannot be false" instead of filed. This is the corrected sweep. No
   source, story or baseline changed in T594; T595 and T596 close what this enumerates.

   **A second hand-back, on PR #80, was rejected 2026-09-13 for the same shape one level down.** A
   hand-typed sweep — reading every file the Method paragraph below now reads mechanically — fixed the
   members three reviewer passes had shown it (`SiteHeader`'s skip link, `ThirdPartyObjectionForm`'s
   input, `PrivacyNotice`'s section headings; a size check applied to hover only; `Menu`'s F15/F16
   gaps never carried to `ProfileSummary` and `SiteHeader`, which defer to them) and, being a fourth
   hand pass over the same set of directories `scripts/checks/story-docs.mjs` counts, offered no
   reason to expect it had not missed a fifth set of siblings the same way. T594 was amended the same
   day to require an extractor for records 1 and 3 — `scripts/checks/state-coverage.mjs`, tested by
   `scripts/checks/state-coverage.test.mjs` — so that what row 8 asserts about the source is asserted
   by a program that reads every directory identically, not by a person's Nth attention pass over
   them. **This is that rebuild.**

   **Method.** `scripts/checks/state-coverage.mjs` parses every component's own (non-story, non-test)
   source and every `*.stories.tsx` file with the TypeScript compiler API (`ts.createSourceFile`,
   already a direct `packages/design-system` devDependency), never a line grep. **Record 1** walks
   every JSX element in a component's own source and reports a candidate — an intrinsic interactive
   tag, a `role="button"`/`role="link"`, any element carrying `tabIndex`, or any element whose
   resolved `className` carries a `hover:`/`focus-visible:`/`active:` utility even with none of the
   above — with its own classes, resolved through the same file's own `const` declarations and
   `cx()`/`clsx()` calls, never a second file. **Record 3** finds every `Button`, `Link`, `Field` and
   `Menu` instance anywhere in the tree, with `variant`/`size` resolved against a literal prop/arg or
   the primitive's own default (read from its `index.tsx`) when omitted.

   For both records, a `visualForceState`'s `role`/`name`/`nth` is matched to the element or instance
   it targets by `resolveNameMatch` (`scripts/checks/state-coverage.mjs`'s own exported function):
   a literal JSX text match first; failing that, a name found anywhere in the story's own `args`
   (merged with the component's default meta `args`, at any depth — `Dialog`'s
   `{ primaryAction: { label: 'Turn it off' } }`) attributed to the sole candidate rendered from a
   `.map()`/`.flatMap()` over a literal array (`SiteHeader`'s `NavItem`, one of several `items`); an
   `aria-hidden` element is never a candidate at all, the same exclusion Playwright's own `getByRole`
   applies (`FavouriteToggle`'s decoy `Button`); a bare `nth` position is resolved against the
   candidates whose own recorded line is a real render position — excluding a reusable local helper
   function's declaration site, which a static pass cannot multiply out to its real use sites
   (`PrivacyNotice`'s `InlineLink` recipe, declared once, invoked many times) — sorted by line.

   **A dynamic `variant`/`size`/label and a conditional branch both resolve against a specific
   story's own args, not only a literal prop.** Every JSX candidate carries its own _guards_ — the
   `if`/ternary/`&&` conditions between the file's own top and that candidate, each `{ expr, truthy
}` — and, for a helper _component_ invoked from exactly one known call site, that call site's own
   guards too (`FavouriteToggle`'s `if (!authenticated) { return <SignedOutControl /> }` excludes
   `SignedOutControl`'s own `Button` once a story's own `authenticated: true` arg resolves the guard
   false, leaving the real control the sole, unambiguous candidate). `evaluateExpr`
   (`scripts/checks/state-coverage.mjs`) evaluates a guard, a `variant={primaryAction.variant ??
'destructive'}` attribute, or a `{primaryAction.label}` child against a scope built from the
   component's own prop defaults overridden by the story's merged `args` (nested objects included) —
   literals, `??`/`&&`/`||`, `!`, `===`/`!==`, property access and ternaries only; a function call or
   a value truly outside the story's own data stays unresolved rather than guessed.

   **A `visualForceState` naming a `selector` and no `role` targets a specific CSS element, never a
   primitive by its accessible role** — it is not a candidate for role-based matching against any
   number of `Button`/`Link`/`Field`/`Menu` instances the component happens to render
   (`FavouritesList`'s own `Hover`/`FocusVisible`/`Active`, `selector: 'a[href="/players/1"]'`,
   target its row link, never either of its two, individually name-resolvable `Button`s).

   **A `role` attribute that is present but dynamic never falls back to its tag's intrinsic role.**
   `MenuItemRow`'s own `role={variant === 'selection' ? 'menuitemradio' : 'menuitem'}` overrides
   `<button>`'s intrinsic `button` role at render time, whatever it resolves to; treating the
   unresolved attribute as if it fell back to `button` would pool it with `Menu`'s own trigger — two
   elements that can never actually share a role — and invent an ambiguity between them. Excluded
   from every implied-role pool instead, correctly leaving `Menu`'s trigger as the sole `role:
'button'` candidate.

   **A `play()` function is walked separately** for the one shape that leaves real DOM focus behind
   it — a `.focus()` call or a `toHaveFocus()` assertion, resolved against a `getByRole`/`findByRole`
   call in the same function or an earlier `const` binding in it — and never for hover or press,
   which a `play()` can never leave (`tests/visual/stories.spec.ts`'s own measured `VisualForceState`
   comment).

   A cell is `'none'` only when the candidate carries an implied role **and** no force-state of that
   state shares it anywhere in its own component's stories — a confirmed absence, over a real
   comparison this pass actually ran; the same confirmed absence stands, unconditionally and without
   needing a role at all, for a candidate that carries no `hover:`/`focus-visible:`/`active:` class
   for this state in the first place (T595 — `ownPseudoClass`, read by `cellFor` before it ever asks
   about role: `AccountErasurePanel`'s own `<label>`, which ARIA gives no role of its own and whose
   `className` paints none of the three). When a force-state does share the role, but
   `resolveNameMatch` cannot settle it on exactly one candidate, the cell is `'unresolved: <reason>'`
   instead — printed, never guessed, and never folded into `'none'`, which used to make an unresolved
   case indistinguishable from a real gap.

   **`INTRINSIC_ROLE` (`scripts/checks/state-coverage.mjs`) carries the heading family (`h1`-`h6` →
   `heading`) and the table family with a fixed role regardless of attributes (`table`,
   `thead`/`tbody`/`tfoot` → `rowgroup`, `tr` → `row`, `td` → `cell`; `th` deliberately absent — its
   own role depends on its `scope` attribute, the same shape `<input>`'s `type` already takes, never
   a constant this map can hold honestly) beside the seven tags it started with (T595, closing row
   8's own "no implied role"/"ancestor of a forced descendant" cells) — so `h2` and `tr` carry a real
   implied role today.** A candidate with **no implied role at all** left after that — `impliedRoleOf`
   returns `null` for a dynamic `role={…}` and for any tag `INTRINSIC_ROLE` still does not carry
   (`label` among them, ARIA gives it none) — never runs the role-based comparison above. Two more
   comparisons run before this pass gives up on such a candidate, both T595's own: a dynamic
   `role={…}` is resolved _per story_, against that story's own props/args scope extended by the
   element's own local `const`s in scope (`MenuItemRow`'s `role={role}`, the same fold
   `resolveDisabledFromStories` already applies to a dynamic `disabled`); and `hover`/`active`
   (never `focus-visible`, which does not cascade) are credited from a _confirmed_ descendant match,
   because the visual harness drives both with a real, CDP-backed pointer move and mouse-down
   (`tests/visual/stories.spec.ts`'s own `VisualForceState` comment), which matches every ancestor
   whose own box contains the forced descendant the same way a real pointer would (`Table`'s own
   `<tr>` around its row `<a>`, row 8's own F17). Only once none of these settles it does the cell
   read `'unresolved: <reason>'`, one of three: `dynamic role` (no story's own data resolves the
   expression), `ancestor of a forced descendant` (a nested local element, by JSX containment, was
   itself matched or left _ambiguous_ — never a confirmed match, already credited above — for this
   same state), or `no implied role` (neither of the above — the tag simply carries no role this
   pass can derive, and does carry a class for this state, or the ambiguous-descendant case would not
   apply either).

   **Record 1's own class half, when a candidate's `className` expression resolves through an object
   literal indexed by a prop the component itself gives more than one meaning across its own callers
   (`Button`'s own `variantClasses[variant]`, `sizeClasses[size]`), renders that prop's own _default_
   value, never a union of every entry the object holds (T595 — `resolveClassParts`'s own
   `scopes.defaultScope`, built from `findVariantSizeDefaults`, the identical default record 3's own
   axis matrix already resolves an _omitted_ instance to, reused rather than reinvented).** `Button`'s
   own `button` row (index.tsx:207) reads `hover:bg-surface-sunken` because `Button` itself
   destructures `variant = 'secondary'` — `secondary`'s own hover fill, never `primary`'s
   `hover:bg-accent-hover` or either of `ghost`/`destructive`'s, none of which the row shows. A
   conditional keyed on the same prop (`variant === 'primary' ? primaryFocusRing : focusRing`)
   resolves the identical way, taking only the branch the default actually reaches. Unioning every
   value the object holds instead would compile and would be a worse answer than the `unresolved`
   this pass used to print: the combined string is not the classes any one `Button` instance actually
   renders, true of no variant at all — record 1 has one row per element, not one per element per
   variant, so it states the one configuration that row's own element genuinely has by default rather
   than pretending to state all of them. Record 3's own axis matrix (`#Button` below) is where the
   per-variant truth already lives — every `variant|size` combination this tree renders, its own row
   — so the two records are not in conflict: a `none` in a `primary|md` or `ghost|lg` hover row still
   reads there is a real, uncorrected gap even on a component whose record 1 row for the same element
   reads a real class, because that class is the _default_ variant's, not that row's. A component
   that destructures the keyed prop with no default at all leaves both the object-literal lookup and
   the conditional exactly as unresolved as this pass left every dynamic expression before T595 —
   `state-coverage.test.mjs`'s own contrast fixture for this shape resolves neither, on purpose, and
   the dual-branch-conservative conditional reading (both branches kept, T594's own rule) still
   applies once there is no default to settle it.

   **A caller's own `className` (the trailing argument of `cx(..., className)`, the shape every
   primitive/composite/screen here that accepts one forwards it through) is read as contributing no
   class of its own, ever, rather than as an expression this pass failed to resolve.** Record 1's own
   subject is the element's _own_ source, stated at the top of this Method section — a class a caller
   might someday supply is a fact about the caller, not about this component, and record 1 already
   treated it this way for every row whose _other_ fragments supply a real class for a given state
   (nothing on the left half of `stateCell` ever showed the caveat). T595 closes the mirror case:
   `Table`'s own scroll region (index.tsx:153) reads a confirmed `none` on hover, not `unresolved`,
   once `overflow-auto rounded-panel border border-border bg-surface`/`focusRing` are checked and
   neither carries one — a caller's own `className` was never going to be this component's own answer
   to that question, whatever it might someday hold.

   **Record 3's own ambiguity precedence, stated rather than left implied (T594's REJECT on #80,
   item 4).** An ambiguous composed-story match — several candidates share a force-state's role and
   `resolveNameMatch` cannot settle it on one — never renders a confirmed `'none'` on any row it was
   ambiguous between; it renders `'unresolved: …'` there instead. But that `'unresolved'` note is
   itself dropped from a given row's own state cell whenever that exact row already carries a real,
   unambiguous match for that state from elsewhere — another story, another candidate: a state known
   to be covered is positive knowledge in its own right, and outranks noting that a _different_
   comparison could not be settled. `Menu`'s own `actions` row used to be the one cell this left with
   nothing else to show, keeping the note, until T595's own composed-elsewhere tracing (below) ruled
   both of `ProfileSummary`'s `Menu` instances out directly — the tally this paragraph describes is
   zero, live in this tree today, and this is no longer a real example of a kept note, only of the
   mechanism that would keep one. The exact split, over every ambiguity live in this tree today, is
   `node scripts/checks/state-coverage.mjs`'s own printed "record 3 ambiguity tally" line
   (`summarizeAmbiguities`, `scripts/checks/state-coverage.mjs`) — cited here rather than restated,
   this paragraph's own rule below: a hand count written directly into this prose was wrong twice
   (T594's row 8 sweep, item 2 — six ambiguities read as one story-name count where the real
   comparison is over tainted `(row, state)` cells, of which there are more than twice that many).
   **Record 3's own axis-mismatch redirect (item 2 of the
   same REJECT), and the multi-row credit it settles on (T595) — one mechanism, reaching all five
   columns, corrected once already during this task's own review.** A JSX candidate's own
   statically-resolved axis (a dynamic `size`/`variant`, no literal to key a row on) and the axis its
   own force-state resolves to _per story_ can disagree — the same source line then owns a `rest`
   entry on one row and a real match on another (`FavouriteToggle`'s own `size={size}`, a bare prop of
   the composite, resolves to `'md'` under most of its own stories and to `'lg'` under
   `RealisticProfileHeader`; `Dialog`'s own `variant={primaryAction.variant ?? 'destructive'}`, a
   nested property access behind a `??` default, resolves the same way). **The call site is credited
   to every row its own stories resolve it to, never to one** — the same source line's own state is
   real knowledge on whichever row a story actually established it, and a row a call site's static
   parse cannot key at all is not a reason to withhold that knowledge from the row _the same call site
   resolves to elsewhere_.

   Concretely: `storyResolvedBySourceLine` (`scripts/checks/state-coverage.mjs`) is one map, keyed by
   `(source line, state)`, holding the **exact label** a confirmed match proved there — never a
   target row's key. It is fed by every `composed-story` match (`hover`/`focus-visible`/`active`) and
   by every `jsx-disabled-resolved` match (`disabled`, `resolveDisabledFromStories`'s own real,
   positive resolution — an `'unresolved'` or ambiguous one never feeds it, the same exclusion the
   ambiguity paragraph below already applies to `unresolvedByState`). Before a row's own state cell
   falls to `'none'`, every source line in its own `rest` list is checked against this map for that
   state; the labels found — there can be more than one, when two different call sites on the same
   static row settle to two different target rows — are credited directly, the same
   positive-knowledge-outranks-a-note precedence the ambiguity paragraph already states, applied
   across rows rather than within one.

   **Crediting the exact label, never a target row's whole list, is the fix over this task's own
   first draft (orchestrator finding on the hand-back): a first version stored the target row's key
   and had `cellFor` pull that row's entire state list, which was correct only by accident — every
   target `ghost|unresolved`'s own redirects ever reached happened to carry exactly one contributor.**
   `disabled` broke that accident immediately: `unresolved|lg`'s own two call sites (`Dialog`'s
   `index.tsx:127`/`:138`) resolve to `destructive|lg` and `secondary|lg`, and `secondary|lg`'s own
   disabled list also carries `MatchDetailPanel:DownloadPreparing`/`ArchivalControl:Submitting` — real
   coverage for two wholly unrelated Button call sites that only share that row by axis coincidence,
   never a fact about either of `Dialog`'s own buttons. Pulling the whole row would have credited
   `unresolved|lg` with stories that prove nothing about its own call sites — the exact "a per-story
   resolution is knowledge about that story, never a claim about the call site in general" bar this
   whole mechanism exists to hold, and the reason the map stores a label rather than a row.

   Because the map is fed exclusively by confirmed matches, a credited label is never a bare pointer
   needing a fallback note: there is nothing left for an `'unresolved: axis resolved only per story (→
…)'` phrasing to name that is not already real, printed coverage — so that phrasing, T594's own
   fix, is now dead by construction rather than merely rare, and `cellFor` no longer emits it.

   **The rows this redirect targets (`ghost|unresolved`, `unresolved|lg`) do not disappear once every
   occurrence on them resolves, and are not redistributed into the rows their stories resolve to.**
   They stay because their own `rest` list is real, independent information — the exact source
   positions whose axis genuinely cannot be read from a literal prop or the primitive's own default —
   and no mechanism here moves a `rest` entry between rows; only the state cells (which are never
   claims about the source line's own static axis, only about what some story renders) borrow coverage
   from wherever a story actually proved it. A row that never resolves through any story at all keeps
   reading its own `'unresolved: <reason>'` on every state, exactly as before — T595 closed the seven
   cells where a story's own data _did_ settle it: `ghost|unresolved`'s hover (`FavouriteToggle:Hover`),
   focus-visible (`FavouriteToggle:FocusVisible`), active (`FavouriteToggle:Active`) and disabled
   (`FavouriteToggle:AddingInFlight; FavouriteToggle:Bounded; FavouriteToggle:RemovingInFlight` — the
   seventh cell, found only once the redirect reached `disabled` too, the same defect class as
   `unresolved|lg`'s and closed by the same fix rather than a second one); `unresolved|lg`'s
   focus-visible (`Dialog:FocusVisible`) and disabled (`Dialog:PrimaryPending`) — never a case where no
   story provides one. `ghost|unresolved`'s own focus-visible/active cells no longer also read
   `Button:GhostFocusVisible`/`Button:GhostActive` (a side effect of the same correction, not a
   separate one): those are `Button.stories.tsx`'s own literal `ghost|md` instance, a call site with
   no relation to `FavouriteToggle`'s, and the whole-row-pull draft was crediting `ghost|unresolved`
   with them purely because they shared `ghost|md` as their axis bucket — the identical pollution the
   `secondary|lg` case caught, one row earlier, before `Dialog`'s own shape forced the fix.

   **`disabled` is not read from a `visualForceState` at all — there is no pseudo-class to force —
   so it is resolved differently from the other three states (T594's row 8 sweep, item 1: this
   column used to credit only a statically literal `disabled` prop or a story's own top-level
   `disabled: true` arg, so a `disabled` reached through a composite's own prop, or through
   `Button`/`Field`'s own `loading` — both primitives' own source folds `loading` into the same
   rendered disabled state — and resolved only once a specific story's args were substituted in,
   was invisible, and its `'none'` was not the confirmed absence over a real comparison every other
   cell already promises).** A literal `disabled`/`loading` on the call site itself is unconditional
   knowledge, independent of any story. A dynamic expression is evaluated against **every** story of
   the owning component in turn — never only the ones carrying a `visualForceState`, since a story
   that only ever sets `args` (`FavouriteToggle`'s own `Bounded`, `AddingInFlight`, `RemovingInFlight`;
   `Dialog`'s own `PrimaryPending`) forces nothing at all — with the story's own merged `args`
   extended by the local `const` declarations in scope at that exact JSX position
   (`FavouriteToggle`'s own `const bounded = atLimit && !favourited`), the same fold
   `buildFileValueScope` already gives a file's own top-level consts, so a bare reference to a
   computed local variable resolves the same way a prop reference does. A candidate whose own
   guards resolve `'unreached'` for a given story is skipped for that story entirely, the same
   exclusion role-based matching already applies; a guard, or the `disabled`/`loading` expression
   itself, that cannot be resolved from that one story's own data leaves the cell `'unresolved:
disabled not statically resolvable (<story>)'` rather than a confirmed `'none'` — positive
   knowledge or unresolved, never guessed, the same rule the other four states already carry. Each
   `jsx-disabled-resolved` match also carries the candidate's own `sourceFile`/`sourceLine` (never
   the story file), so a real match feeds `storyResolvedBySourceLine` above exactly the way a
   `composed-story` match already does — the redirect this section opens with reaches `disabled`
   because this is where it learns to, not through a second copy of the rule.

   **A story that never mounts the component at all supplies no data, and is excluded before this
   runs at all rather than left to read `'unresolved'` (T595).** `storyRendersComponent`
   (`scripts/checks/state-coverage.mjs`) is `true` for every `args`-only story — Storybook always
   instantiates `<Component {...args} />` implicitly — and for a `render:` story that mounts the
   component anywhere in its own body, however wrapped (`PrivacyNotice`'s own
   `render: (args) => (<div>...<PrivacyNotice {...args} /></div>)`); `false` only for a `render:`
   story whose body never does, the shape every `*NotApplicable` placeholder in this tree uses
   (`Dialog:EmptyHoverActiveDisabledNotApplicable`'s own `<p>A dialog with no actions...</p>`, no
   `<Dialog>` tag anywhere in it). A story this excludes has nothing to say about any candidate
   inside the component it never rendered — not "this story's own data cannot resolve the
   expression" (kept `unresolved:`, the paragraph above), which is a check that ran and could not
   settle, but a story that never reached the component's own render at all, the same exclusion an
   `'unreached'` guard already gets on one branch, generalised here to the whole story. Removes the
   one spurious `'unresolved: disabled not statically resolvable
(Dialog:EmptyHoverActiveDisabledNotApplicable)'` reason `unresolved|lg`'s own disabled cell used
   to carry (`primitives/Dialog/index.tsx:127,138`): no other `Dialog` story ever leaves
   `primaryAction`/`secondaryAction` themselves unresolved (every one that does render `Dialog`
   supplies both, even when a given field inside them is absent — `Default`'s own `primaryAction: {
label: 'Turn it off' }` resolves `primaryAction.disabled` to a real `undefined`, not
   `UNRESOLVED`), so excluding the one story that supplies neither leaves nothing behind it. **This
   alone would settle the cell at a confirmed `'none'`** — the reading an earlier draft of this task
   left it at — **but the redirect above now reaches `disabled` too, and finds real coverage there
   instead**: `index.tsx:127`'s own `primaryAction.disabled`/`.loading` and `index.tsx:138`'s own
   `secondaryAction.disabled`/`.loading` both resolve real under `Dialog:PrimaryPending`
   (`loading: true`, `disabled: true` respectively), crediting `destructive|lg` and `secondary|lg`
   directly and, through the redirect, `unresolved|lg` itself — so the cell reads `Dialog:
PrimaryPending`, not `'none'`; the two fixes compose rather than each doing the whole job alone.

   **A bare JSX attribute in a `render:` story (`<FavouriteToggle authenticated size="lg" />`, no
   `={...}`) is shorthand for `={true}`, and `findRenderJsxProps` now reads it that way rather than
   dropping it (T595).** It used to carry no initializer to evaluate at all, so the prop was simply
   never added to that story's own scope — invisible, not `false` — which left an unrelated guard
   elsewhere in the same component unresolved by omission: `FavouriteToggle:RealisticProfileHeader`'s
   own `authenticated` (bare, meaning `true`) never reached `FavouriteToggle`'s own guard on
   `if (!authenticated) return <SignedOutControl />`, so every candidate reached only past that guard
   — both real buttons, `index.tsx:115,126` — read `'unresolved'` regardless of whether their own
   `disabled`/`loading` expressions resolved. Fixed generally (a synthesised `ts.factory.createTrue()`
   node, evaluated the same way a written-out `={true}` already would be), not by special-casing this
   one attribute or this one story. Closes `ghost|lg`'s own disabled cell
   (`composites/FavouriteToggle/index.tsx:126`) — **and the guard resolving is not, on its own, the
   claim that closes it; what closes it is that the two values the guard used to block from being
   checked at all both evaluate to a real, checked `false` once it does (orchestrator finding on the
   hand-back: "the guard now resolves" is not the same claim as "no story renders it disabled",
   verified rather than assumed here).** `RealisticProfileHeader`'s own render passes
   `favourited={false} authenticated size="lg"` and nothing else — no `atLimit`, no `loading` — so
   both default to `FavouriteToggle`'s own destructured defaults (`atLimit = false`, `loading =
false`), real values, not absences. `bounded = atLimit && !favourited` short-circuits on
   `atLimit`'s own `false` without needing `favourited` at all, resolving to a real `false`;
   `loading` resolves to its own real default, `false`. Both are `evaluateExpr` results with
   `resolved: true`, not gaps this pass declined to check — the story is checked and found
   negative, not skipped. `ghost|lg`'s only other contributor, `Button:RealisticPageActions`
   (`rest`, above), carries no `disabled`/`loading` attribute in its own source at all — real
   incapacity, not an unresolved guard either. `ghost|lg`'s `'none'` is the union of two confirmed
   checks, not the absence of one: `RealisticProfileHeader`'s real story renders this exact
   configuration and never shows it disabled, and `RealisticPageActions`'s own control cannot be
   disabled by construction. This does not generalise past `FavouriteToggle`'s own stories — a
   caller elsewhere passing `size="lg"` (`FavouritesList/index.tsx:298`, F19 below) is invisible to
   this pass by the same scope limit `Dialog`'s own redirect above and F19's own finding both
   already name: only a component's own stories resolve its own candidates, never a consumer's.

   **A bare `nth` against a reusable local helper is no longer unconditionally `ambiguous`
   (T595).** `resolveNameMatch`'s own `nth` branch used to exclude every helper candidate outright —
   correct for a helper this pass cannot enumerate in full, but not for one it can. A helper this file
   never `export`s cannot be invoked from anywhere a single-file pass does not already see, so every
   one of its real call sites is enumerable (`findHelperCallSites`): each with its own line and its own
   guards. `PrivacyNotice`'s own `InlineLink` (`index.tsx:242`, invoked five times: four unconditional,
   one behind `hrefs.processingRegister &&`) is placed by whichever of its own call sites is reached
   for a specific story's own scope, the earliest one standing in for the helper's own render
   position — the same one-slot-per-candidate approximation the existing line sort already makes for a
   `.map()`-rendered candidate (one AST node standing for every real instance it renders; every real
   `nth` in this tree is `0`, so only "which candidate renders first" ever needs deciding). A call site
   whose own guard a story's scope cannot resolve leaves the whole pool unorderable for that story —
   real uncertainty, never guessed past — and an `export`ed helper, or one with no `scope` supplied at
   all, keeps the original, unconditional exclusion. `PrivacyNotice`'s three cells (F10, above) close
   this way: `InlineLink`'s earliest call site (`:646`) sorts after the `Contents` entry's own
   (`:490`), so it is positively `reject`ed at `nth: 0`, not merely left unplaceable, and the region now
   reads `none` where it used to decline to say.

   **A composed primitive instance declared directly in its own owning component's body was
   `isHelper: true` unconditionally — a second, unrelated defect the same `nth` family exposed
   (T595).** `findPrimitiveInstances` set `isHelper` from `context.fnName != null` alone, never
   excluding the component's _own_ name the way `findLocalElements` already does for record 1
   (`context.fnName != null && context.fnName !== mainComponentName`, this file's own established
   pattern) — so a `Button`/`Link`/`Field`/`Menu` instance sitting directly in its owning component's
   return, not behind a second, nested helper, was `isHelper: true` regardless, and `resolveNameMatch`'s
   `nth` branch excluded it the same way it excludes a real, unorderable helper. Nothing in this tree
   depended on this being wrong except `Footer` (composites/Footer/Footer.stories.tsx's `Hover`/
   `FocusVisible`/`Active`, `role: 'link', nth: 0`, the only other `nth`-driven composed match in the
   package): both of its own `Link` instances (`index.tsx:45`, `:50`) carried `isHelper: true` although
   neither sits behind any helper at all, so `nth: 0` could never place either. Fixed the same way
   record 1 already was — `mainComponentName` threaded through, `isHelper` false for the owning
   component itself — and `nth: 0` now correctly lands on `index.tsx:45` (the privacy-notice link,
   the first in source order for `Hover`'s own args, which supply both hrefs): `Footer`'s own three
   states now credit `standalone`'s row directly, alongside `Link`'s own pre-existing `Hover`/
   `FocusVisible`/`ActiveStandalone` stories, and the composed-story ambiguity tally's three Footer
   events (of nine live before this task) drop to zero along with it.

   **A `visualForceState`'s own `name` can be produced by a primitive Record 3 does not even track,
   composed one hop away from the target component — traced there, every candidate Record 3 _does_
   track for that component is positively `reject`ed, and the frame itself is credited on the real
   target's own row, never left uncredited (T595, the composition-scope decision this row's own
   Method section owes, corrected once already during this same task — see below).**
   `ProfileSummary`'s `BoardFlagHoverRevealed`/`BoardFlagKeyboardFocusRevealed`/
   `BoardLongAliasFlagHoverRevealed` each force `role: 'button', name: 'Country:'` — a name neither
   of `ProfileSummary`'s own two `Menu` instances, nor any of its `Button` instances, carries
   literally or through its own args. The name is real: `ProfileSummary/index.tsx` composes
   `<CountryFlag>` directly, and `CountryFlag/index.tsx:71` composes `<Tooltip content={countryName}
qualifier="Country:">` — `Tooltip`'s own `qualifier` prop prepends the trigger's accessible name
   (`Tooltip/index.tsx`'s own doc, §8; `CountryFlag.test.tsx:15` asserts the rendered name is
   `"Country: France"`). `Tooltip` is not one of the four primitives `PRIMITIVE_NAMES` tracks, so this
   name can never be literally resolved by reading `ProfileSummary`'s own file alone — every candidate
   fell to the final, unconditional `'ambiguous'` before this task, the correct reading under the rule
   that an unaccounted-for name is never silently `'reject'`ed (above). `findComposedElsewhereNames`
   reads exactly one hop past that rule's own boundary: every capitalised JSX tag a component's source
   invokes directly, resolved to its own `index.tsx` by name (the same directory-name convention every
   other JSX-tag-to-file lookup in this pass already relies on), read once for a literal `<Tooltip
qualifier="...">`. Only `Tooltip`'s own `qualifier` is read this way — the one documented mechanism
   this tree uses to compose an accessible name across a file boundary — and only that one hop: a tag
   this pass cannot resolve to a file, or whose own `Tooltip` usage carries no literal qualifier,
   contributes nothing, and a name found this way is never walked a second hop through whatever _that_
   file itself composes. **This does widen "only a component's own stories resolve its own
   candidates, never a consumer's" from the paragraph above** — the composition being read is a
   callee's own source, not a consumer's.

   **The orchestrator's own review of this task's first hand-back found the first version of this
   mechanism false: rejecting every wrong candidate is not the same as crediting the right one, and
   the first draft only ever did the former.** `resolveComposedElsewhereCredits` (folded into
   `computeStateCoverage` directly, not a separate exported step) resolves the credit itself, once,
   after every component's own local elements are known: a composed-elsewhere name is only ever
   _confirmed_ — and only then does `resolveComposedStoryMatches` get to `reject` every candidate in
   the forcing component — when the _target_ component's own local-element pool for the force-state's
   role resolves to exactly one candidate, the same "sole candidate needs no further disambiguation"
   bar `resolveNameMatch`'s own final branch already holds for a force-state with neither `name` nor
   `nth`. A target pool of zero or more than one stays unconfirmed: nothing is credited anywhere, and
   the forcing component's own candidates fall back to the ordinary "unaccounted name" `'ambiguous'`.
   Confirmed, the credit lands directly on the target's own cell — `Tooltip`'s own `button` row now
   reads `HoverRevealed; CountryFlag:FlagHoverRevealed; ProfileSummary:BoardFlagHoverRevealed;
ProfileSummary:BoardLongAliasFlagHoverRevealed` — labelled by the _story file's_ own basename, the
   same convention Record 3's own composed-story credits already use (`Footer:Hover`), so a reader
   sees exactly which story forced the frame. The injected credit carries no `name` of its own: the
   target pool's own single-candidate confirmation already settled which element it is, so
   re-attempting a literal name/args match against `Tooltip`'s own file (where `"Country:"` appears
   nowhere — it is `CountryFlag`'s own literal, a fact about the composition, never about `Tooltip`'s
   own source) would only manufacture a fresh, false `'ambiguous'` on an already-settled match.
   `Menu`'s own `actions` row and every affected `Button` row read a confirmed `none` for
   hover/focus-visible now — grounded in the credit landing on `Tooltip`'s own row, not merely in
   nothing else claiming it — and the ambiguity tally's remaining six events (of nine) drop with it.

   **The same mechanism also reaches a role-only force-state with no `name` at all
   (`CountryFlag.stories.tsx`'s own `FlagHoverRevealed`/`FlagKeyboardFocusRevealed`/
   `FlagDismissedAfterEscape`, `role: 'button'` alone) and a _zero_-hop composition
   (`CountryFlag/index.tsx` composes `<Tooltip>` directly, not through a second component) — both
   found only because `findUnaccountedForceStates` (below) is unconditional and does not stop at the
   six cells this task was scoped to.** The zero-hop case needed `findComposedElsewhereNames` itself
   widened: its own first version excluded a direct `<Tooltip>` usage from the walk outright (guarding
   against reading a `Tooltip` usage as a candidate one hop _further_), which incidentally excluded
   reading a real, direct usage at all. Routing a _nameless_ force-state to `Tooltip` needs a second
   guard `componentHasOwnCandidateForRole` supplies: safe only when the forcing component has no
   candidate of its own for the role a bare role-only force-state could otherwise mean
   (`CountryFlag`'s own shape — it has no local interactive element at all) — never when it does
   (a component with its own real button for that role keeps the ordinary "sole candidate" reading of
   _that_ button, and `Tooltip` is correctly left uncredited; `state-coverage.test.mjs`'s own contrast
   plants exactly this shape).

   **`findUnaccountedForceStates` is the invariant this mechanism's own first failure should not have
   needed a second reviewer to catch: every real `visualForceState` under this package's three tiers
   is either credited on some cell or named in some `unresolved: <reason>`, checked against the
   region's own rendered text, or the run fails.** A story whose own `render:` never mounts the
   component (`rendersComponent`) is excluded — it has nothing to say about any candidate, the same
   exclusion `pendingDisabledChecks` already applies. A `synthetic` entry (a credit this mechanism
   manufactured on another component's behalf) is excluded too — the real story it originated from is
   checked under its own name in its own component's own list. One gap this check found is not
   `Tooltip`-shaped at all and is not closed by anything above: `ProfileSummary`'s own
   `SwitcherFocusVisibleAndOpen` (`role: 'menuitemradio', name: 'aoe2guy'`) targets `MenuItemRow`'s
   own dynamic-role element (`primitives/Menu/index.tsx`, a record-1 local element) through a `Menu`
   instance `ProfileSummary` composes — record 1 has no cross-component matching path at all today,
   the gap `resolveComposedStoryMatches` closes for record 3's four tracked primitives but never had
   for a primitive's own internal local elements. Filed in `KNOWN_UNACCOUNTED_FORCE_STATES`
   (`scripts/checks/state-coverage.mjs`), dated 2026-09-19, reported on every run and never silent,
   the reporting convention `a11y-allowlist.mjs`'s own empty-list pattern already carries — **owned
   by T598 (fix by 2026-09-27, the same deadline this row itself carries), which deletes the entry
   outright in the commit that closes it.** The `a11y-allowlist.mjs` comparison holds for how the
   exception is reported, not for how long it may live: unlike that file's own steady state (empty,
   nothing suppressed), this entry is not permitted to persist as a passing allowlist row past its
   own `fixBy` — `findUnaccountedForceStates` now enforces the date itself, the same way
   `a11y-allowlist.mjs` and `story-baseline-duplicates-debt.json` (T591) already enforce theirs: a
   filed exception missing `date`/`fixOwed`/`fixBy`, or carrying a `fixBy` earlier than today, fails
   the run exactly like an unfiled loss, never lingers as a quietly-passing entry. An allowlist with
   no expiry is how a temporary exception becomes permanent; this one cannot become that without
   failing CI first.

   **Records 2 and 4 stay read, not extracted, and Record 2's spec side has no mechanical
   completeness guard of its own (a residual `reviewer` noted while verifying this pass, not one this
   pass closes).** `findDeferralHitsInStories` (8c-bis, below) scans every `*.stories.tsx` under this
   package's own three tiers mechanically, the same extraction discipline Records 1 and 3 carry — but
   nothing parallel exists for the 29 `packages/design-system/specs/*.md` files 8c's own table
   tallies: that side is a hand pass over prose, with only the arithmetic identity between a table
   row's own `Handoffs` number and its own quoted-citation count (`checkHandoffTally`) as a tripwire,
   and that tripwire catches a miscount, never a spec sentence the pass simply never read. The next
   reader should not mistake `--check-citations`'s own green exit for a claim that every deferral in
   every spec file has been found — only that every citation this pass _did_ record is verified
   against its own source.

   **A line-numbered self-reference into `state-coverage.mjs`'s own source, inside this row's own
   prose, is unguarded too (found in the row 8 sweep's own item 6, where the target lines had
   already drifted once).** `checkCitations`'s own `allSrcFiles` walks
   `packages/design-system/src/**/*.tsx` and resolves a `.md` location against
   `packages/design-system/specs/` — `scripts/checks/state-coverage.mjs` itself is in neither, so a
   pointer into the checker's own source (this Method section's own reference to the "block
   membership plus a citation window" comment, a few hundred lines into that file) is corrected by
   hand each time this section is touched, the same way `docs/` leans on a nightly contract test it
   does not itself run for every fact it states. Deliberately not written in this file's own
   `` `path:line` `` citation shape, so a reader never mistakes it for one `--check-citations`
   verifies. Widening that check to also resolve locations under `scripts/checks/` would close this
   the same mechanical way every other citation here already is; nothing in this pass does that.

   **Consistency mode is structural, not a second copy of the data.** Records 1 and 3 are rendered as
   markdown tables directly between the `state-coverage:begin`/`state-coverage:end` HTML-comment
   markers below — `node scripts/checks/state-coverage.mjs --write` regenerates that region in place,
   formatted through this repository's own `prettier` binary (piped via stdin) so the committed region
   is byte-identical to what `pnpm exec prettier --check` already expects, and check mode (no flag)
   fails when the region on disk differs from that same fresh, formatted render. There is no JSON
   block beside it: the rendered tables **are** the record, so a hand-written coverage claim about a
   record-1 element or a matrix cell that disagreed with them — the defect the orchestrator's review
   of this task's first remediation found (`coveredBy: none` for `NavItem` and `PrivacyNotice`'s
   `Contents` entry, sitting beside prose calling both "covered") — cannot recur silently: editing the
   visible text _is_ editing the check's own input. Every claim in 8c and 8d below about a record-1
   element or a matrix cell cites a row inside the generated region rather than restating it.

<!-- state-coverage:begin -->

_Generated by `scripts/checks/state-coverage.mjs --write`. Do not hand-edit between these markers — run the script instead._

**Record 1 — every local interactive element (41 component directories scanned).**

| Component                         | Element                                      | File:Line                                                                | Hover (class → story)                                                                                                                      | Focus-visible (class → story)                                                                                                                                                                                                                                                                                                                           | Active (class → story)                                                                                                          |
| --------------------------------- | -------------------------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| composites/AnalysisTimeline       | (no local interactive element)               | N/A                                                                      | N/A                                                                                                                                        | N/A                                                                                                                                                                                                                                                                                                                                                     | N/A                                                                                                                             |
| composites/CaptureStateBadge      | (no local interactive element)               | N/A                                                                      | N/A                                                                                                                                        | N/A                                                                                                                                                                                                                                                                                                                                                     | N/A                                                                                                                             |
| composites/CivilisationIcon       | (no local interactive element)               | N/A                                                                      | N/A                                                                                                                                        | N/A                                                                                                                                                                                                                                                                                                                                                     | N/A                                                                                                                             |
| composites/CountryFlag            | (no local interactive element)               | N/A                                                                      | N/A                                                                                                                                        | N/A                                                                                                                                                                                                                                                                                                                                                     | N/A                                                                                                                             |
| composites/FavouritesList         | a                                            | packages/design-system/src/composites/FavouritesList/index.tsx:244       | hover:bg-surface-sunken → Hover                                                                                                            | focus-visible:outline-2 focus-visible:outline-offset-ring-inset-flush focus-visible:outline-focus-ring → FocusVisible                                                                                                                                                                                                                                   | active:bg-surface-sunken active:border-l-border-strong active:ring-2 active:ring-inset active:ring-border-strong → Active       |
| composites/FavouriteToggle        | (no local interactive element)               | N/A                                                                      | N/A                                                                                                                                        | N/A                                                                                                                                                                                                                                                                                                                                                     | N/A                                                                                                                             |
| composites/Footer                 | (no local interactive element)               | N/A                                                                      | N/A                                                                                                                                        | N/A                                                                                                                                                                                                                                                                                                                                                     | N/A                                                                                                                             |
| composites/MapThumbnail           | (no local interactive element)               | N/A                                                                      | N/A                                                                                                                                        | N/A                                                                                                                                                                                                                                                                                                                                                     | N/A                                                                                                                             |
| composites/MatchDetailPanel       | (no local interactive element)               | N/A                                                                      | N/A                                                                                                                                        | N/A                                                                                                                                                                                                                                                                                                                                                     | N/A                                                                                                                             |
| composites/MatchRow               | a                                            | packages/design-system/src/composites/MatchRow/index.tsx:397             | hover:bg-surface-sunken → Hover                                                                                                            | focus-visible:outline-2 focus-visible:outline-offset-ring-inset-flush focus-visible:outline-focus-ring → FocusVisible                                                                                                                                                                                                                                   | active:bg-surface-sunken active:border-l-border-strong active:ring-2 active:ring-inset active:ring-border-strong → Active       |
| composites/PlayerAvatar           | (no local interactive element)               | N/A                                                                      | N/A                                                                                                                                        | N/A                                                                                                                                                                                                                                                                                                                                                     | N/A                                                                                                                             |
| composites/PlayerColourSwatch     | (no local interactive element)               | N/A                                                                      | N/A                                                                                                                                        | N/A                                                                                                                                                                                                                                                                                                                                                     | N/A                                                                                                                             |
| composites/PlayerResultRow        | a                                            | packages/design-system/src/composites/PlayerResultRow/index.tsx:54       | hover:bg-surface-sunken → Hover                                                                                                            | focus-visible:outline-2 focus-visible:outline-offset-ring-inset-flush focus-visible:outline-focus-ring → FocusVisible                                                                                                                                                                                                                                   | active:bg-surface-sunken active:border-l-border-strong active:ring-2 active:ring-inset active:ring-border-strong → Active       |
| composites/ReplayAvailabilityList | (no local interactive element)               | N/A                                                                      | N/A                                                                                                                                        | N/A                                                                                                                                                                                                                                                                                                                                                     | N/A                                                                                                                             |
| composites/SearchBox              | input[role=searchbox]                        | packages/design-system/src/composites/SearchBox/index.tsx:129            | hover:border-border-strong → Hover                                                                                                         | focus-visible:border-border-strong focus-visible:outline-2 focus-visible:outline-offset-ring focus-visible:outline-focus-ring → FocusVisible                                                                                                                                                                                                            | none → none                                                                                                                     |
| composites/SiteHeader             | a                                            | packages/design-system/src/composites/SiteHeader/index.tsx:156           | none → none                                                                                                                                | focus:not-sr-only focus:fixed focus:top-2 focus:left-4 focus:z-50 focus:rounded-control focus:border focus:border-border-strong focus:bg-surface-raised focus:px-3 focus:py-3 focus:font-sans focus:text-sm focus:font-normal focus:text-text-primary focus-visible:outline-2 focus-visible:outline-offset-ring focus-visible:outline-focus-ring → none | none → none                                                                                                                     |
| composites/SiteHeader             | a                                            | packages/design-system/src/composites/SiteHeader/index.tsx:183           | hover:underline → none                                                                                                                     | focus-visible:outline-2 focus-visible:outline-offset-ring focus-visible:outline-focus-ring → none                                                                                                                                                                                                                                                       | none → none                                                                                                                     |
| composites/SiteHeader             | a                                            | packages/design-system/src/composites/SiteHeader/index.tsx:209           | hover:bg-surface-sunken hover:text-text-primary → Hover                                                                                    | focus-visible:outline-2 focus-visible:outline-offset-ring focus-visible:outline-focus-ring → FocusVisible                                                                                                                                                                                                                                               | active:border-border-strong active:bg-background active:text-text-primary → Active                                              |
| composites/UploadControl          | input[tabIndex=-1]                           | packages/design-system/src/composites/UploadControl/index.tsx:274        | none → none                                                                                                                                | none → none                                                                                                                                                                                                                                                                                                                                             | none → none                                                                                                                     |
| primitives/Badge                  | (no local interactive element)               | N/A                                                                      | N/A                                                                                                                                        | N/A                                                                                                                                                                                                                                                                                                                                                     | N/A                                                                                                                             |
| primitives/Button                 | a                                            | packages/design-system/src/primitives/Button/index.tsx:189               | hover:bg-surface-sunken → none                                                                                                             | focus-visible:outline-2 focus-visible:outline-offset-ring focus-visible:outline-focus-ring → none                                                                                                                                                                                                                                                       | active:bg-background active:ring-2 active:ring-border-strong → none                                                             |
| primitives/Button                 | button                                       | packages/design-system/src/primitives/Button/index.tsx:207               | hover:bg-surface-sunken → Hover; SecondaryHover; GhostHover; DestructiveHover                                                              | focus-visible:outline-2 focus-visible:outline-offset-ring focus-visible:outline-focus-ring → FocusVisible; SecondaryFocusVisible; GhostFocusVisible; DestructiveFocusVisible                                                                                                                                                                            | active:bg-background active:ring-2 active:ring-border-strong → Active; SecondaryActive; DestructiveActive; GhostActive          |
| primitives/Callout                | (no local interactive element)               | N/A                                                                      | N/A                                                                                                                                        | N/A                                                                                                                                                                                                                                                                                                                                                     | N/A                                                                                                                             |
| primitives/Dialog                 | h2[tabIndex=-1]                              | packages/design-system/src/primitives/Dialog/index.tsx:102               | none → none                                                                                                                                | none → none                                                                                                                                                                                                                                                                                                                                             | none → none                                                                                                                     |
| primitives/EmptyState             | (no local interactive element)               | N/A                                                                      | N/A                                                                                                                                        | N/A                                                                                                                                                                                                                                                                                                                                                     | N/A                                                                                                                             |
| primitives/ErrorState             | (no local interactive element)               | N/A                                                                      | N/A                                                                                                                                        | N/A                                                                                                                                                                                                                                                                                                                                                     | N/A                                                                                                                             |
| primitives/Field                  | (no local interactive element)               | N/A                                                                      | N/A                                                                                                                                        | N/A                                                                                                                                                                                                                                                                                                                                                     | N/A                                                                                                                             |
| primitives/Link                   | a                                            | packages/design-system/src/primitives/Link/index.tsx:140                 | hover:text-link-hover hover:decoration-2 → Hover                                                                                           | focus-visible:outline-ring focus-visible:outline-offset-ring focus-visible:outline-focus-ring → FocusVisible                                                                                                                                                                                                                                            | active:text-link-hover active:decoration-2 active:underline-offset-4 → ActiveStandalone; ActiveInline                           |
| primitives/Menu                   | button                                       | packages/design-system/src/primitives/Menu/index.tsx:144                 | hover:bg-surface-sunken → none                                                                                                             | focus-visible:outline-2 focus-visible:outline-offset-ring focus-visible:outline-focus-ring → unresolved: EscapeReturnsFocusToTrigger (play-driven; frame not provable statically)                                                                                                                                                                       | active:bg-background active:ring-2 active:ring-border-strong → none                                                             |
| primitives/Menu                   | button[role=menuitem][tabIndex=unresolved]   | packages/design-system/src/primitives/Menu/index.tsx:242                 | hover:bg-surface-sunken → none                                                                                                             | focus-visible:outline-2 focus-visible:outline-offset-ring focus-visible:outline-focus-ring → KeyboardNavigation                                                                                                                                                                                                                                         | active:border-l-border-strong active:bg-background → none                                                                       |
| primitives/Menu                   | button[role=unresolved][tabIndex=unresolved] | packages/design-system/src/primitives/Menu/index.tsx:352                 | hover:bg-surface-sunken → Hover                                                                                                            | focus-visible:outline-2 focus-visible:outline-offset-ring-inset-flush focus-visible:outline-focus-ring → FocusVisible                                                                                                                                                                                                                                   | active:border-l-border-strong active:bg-background → Active                                                                     |
| primitives/Page                   | main[tabIndex=-1]                            | packages/design-system/src/primitives/Page/index.tsx:64                  | none → none                                                                                                                                | focus-visible:outline-ring focus-visible:outline-offset-ring focus-visible:outline-focus-ring → FocusVisible                                                                                                                                                                                                                                            | none → none                                                                                                                     |
| primitives/Panel                  | (no local interactive element)               | N/A                                                                      | N/A                                                                                                                                        | N/A                                                                                                                                                                                                                                                                                                                                                     | N/A                                                                                                                             |
| primitives/Section                | (no local interactive element)               | N/A                                                                      | N/A                                                                                                                                        | N/A                                                                                                                                                                                                                                                                                                                                                     | N/A                                                                                                                             |
| primitives/Skeleton               | (no local interactive element)               | N/A                                                                      | N/A                                                                                                                                        | N/A                                                                                                                                                                                                                                                                                                                                                     | N/A                                                                                                                             |
| primitives/StatValue              | (no local interactive element)               | N/A                                                                      | N/A                                                                                                                                        | N/A                                                                                                                                                                                                                                                                                                                                                     | N/A                                                                                                                             |
| primitives/Table                  | div[role=region][tabIndex=0]                 | packages/design-system/src/primitives/Table/index.tsx:153                | none → none                                                                                                                                | focus-visible:outline-ring focus-visible:outline-offset-ring focus-visible:outline-focus-ring → FocusVisible                                                                                                                                                                                                                                            | none → none                                                                                                                     |
| primitives/Table                  | tr                                           | packages/design-system/src/primitives/Table/index.tsx:237                | hover:bg-surface-sunken → RowLinkHover                                                                                                     | none → none                                                                                                                                                                                                                                                                                                                                             | active:bg-surface-sunken active:border-l-border-strong → RowLinkActive                                                          |
| primitives/Table                  | a                                            | packages/design-system/src/primitives/Table/index.tsx:281                | none → RowLinkHover                                                                                                                        | focus-visible:outline-ring focus-visible:outline-offset-ring focus-visible:outline-focus-ring → none                                                                                                                                                                                                                                                    | active:after:ring-2 active:after:ring-inset active:after:ring-border-strong → RowLinkActive                                     |
| primitives/Text                   | (no local interactive element)               | N/A                                                                      | N/A                                                                                                                                        | N/A                                                                                                                                                                                                                                                                                                                                                     | N/A                                                                                                                             |
| primitives/Tooltip                | button                                       | packages/design-system/src/primitives/Tooltip/index.tsx:259              | none → HoverRevealed; CountryFlag:FlagHoverRevealed; ProfileSummary:BoardFlagHoverRevealed; ProfileSummary:BoardLongAliasFlagHoverRevealed | focus-visible:outline-2 focus-visible:outline-offset-ring focus-visible:outline-focus-ring → KeyboardFocusRevealed; DismissedAfterEscape; CountryFlag:FlagKeyboardFocusRevealed; CountryFlag:FlagDismissedAfterEscape; ProfileSummary:BoardFlagKeyboardFocusRevealed                                                                                    | none → none                                                                                                                     |
| screens/AccountErasurePanel       | label                                        | packages/design-system/src/screens/AccountErasurePanel/index.tsx:269     | none → none                                                                                                                                | none → none                                                                                                                                                                                                                                                                                                                                             | none → none                                                                                                                     |
| screens/AccountErasurePanel       | input[role=checkbox]                         | packages/design-system/src/screens/AccountErasurePanel/index.tsx:270     | none → none                                                                                                                                | focus-visible:outline-2 focus-visible:outline-offset-ring focus-visible:outline-focus-ring → AcknowledgementCheckboxFocusVisible                                                                                                                                                                                                                        | none → none                                                                                                                     |
| screens/AccountErasurePanel       | a                                            | packages/design-system/src/screens/AccountErasurePanel/index.tsx:304     | hover:text-link-hover hover:decoration-2 → ErasedScreenHover                                                                               | focus-visible:outline-2 focus-visible:outline-offset-ring focus-visible:outline-focus-ring → ErasedScreenFocusVisible                                                                                                                                                                                                                                   | active:text-link-hover active:decoration-2 active:underline-offset-4 → ErasedScreenActive                                       |
| screens/ArchivalControl           | a                                            | packages/design-system/src/screens/ArchivalControl/index.tsx:137         | none → none                                                                                                                                | none → none                                                                                                                                                                                                                                                                                                                                             | none → none                                                                                                                     |
| screens/DataExportPanel           | a                                            | packages/design-system/src/screens/DataExportPanel/index.tsx:149         | hover:bg-accent-hover hover:underline hover:decoration-2 hover:underline-offset-2 → ReadyHover                                             | focus-visible:outline-2 focus-visible:outline-offset-ring-inset focus-visible:outline-accent-contrast → ReadyFocusVisible                                                                                                                                                                                                                               | active:bg-accent-active active:underline-offset-4 → ReadyActive                                                                 |
| screens/PrivacyNotice             | a                                            | packages/design-system/src/screens/PrivacyNotice/index.tsx:242           | hover:text-link-hover hover:decoration-2 → InlineLinkHover                                                                                 | focus-visible:outline-2 focus-visible:outline-offset-ring focus-visible:outline-focus-ring → InlineLinkFocusVisible                                                                                                                                                                                                                                     | active:text-link-hover active:decoration-2 active:underline-offset-4 → InlineLinkActive                                         |
| screens/PrivacyNotice             | h2[tabIndex=-1]                              | packages/design-system/src/screens/PrivacyNotice/index.tsx:264           | none → none                                                                                                                                | focus-visible:outline-ring focus-visible:outline-offset-ring focus-visible:outline-focus-ring → none                                                                                                                                                                                                                                                    | none → none                                                                                                                     |
| screens/PrivacyNotice             | a                                            | packages/design-system/src/screens/PrivacyNotice/index.tsx:490           | hover:text-link-hover → Hover                                                                                                              | focus-visible:outline-2 focus-visible:outline-offset-ring focus-visible:outline-focus-ring → FocusVisible                                                                                                                                                                                                                                               | active:text-link-hover active:bg-surface-sunken active:ring-2 active:ring-border-strong active:rounded-control → Active         |
| screens/PrivacyNotice             | a                                            | packages/design-system/src/screens/PrivacyNotice/index.tsx:740           | hover:bg-surface-sunken → ObjectionCallToActionHover                                                                                       | focus-visible:outline-2 focus-visible:outline-offset-ring focus-visible:outline-focus-ring → ObjectionCallToActionFocusVisible                                                                                                                                                                                                                          | active:bg-background active:ring-2 active:ring-border-strong → ObjectionCallToActionActive                                      |
| screens/PrivacyNotice             | a                                            | packages/design-system/src/screens/PrivacyNotice/index.tsx:797           | none → unresolved: ObjectionCallToActionHover: selector "a[href=\"/object\"]" not resolvable against this element's own "href"             | none → unresolved: ObjectionCallToActionFocusVisible: selector "a[href=\"/object\"]" not resolvable against this element's own "href"                                                                                                                                                                                                                   | none → unresolved: ObjectionCallToActionActive: selector "a[href=\"/object\"]" not resolvable against this element's own "href" |
| screens/ProfileSummary            | (no local interactive element)               | N/A                                                                      | N/A                                                                                                                                        | N/A                                                                                                                                                                                                                                                                                                                                                     | N/A                                                                                                                             |
| screens/SignInScreen              | (no local interactive element)               | N/A                                                                      | N/A                                                                                                                                        | N/A                                                                                                                                                                                                                                                                                                                                                     | N/A                                                                                                                             |
| screens/ThirdPartyObjectionForm   | input                                        | packages/design-system/src/screens/ThirdPartyObjectionForm/index.tsx:130 | none → none                                                                                                                                | focus-visible:outline-2 focus-visible:outline-offset-ring focus-visible:outline-focus-ring → none                                                                                                                                                                                                                                                       | none → none                                                                                                                     |
| screens/ThirdPartyObjectionForm   | a                                            | packages/design-system/src/screens/ThirdPartyObjectionForm/index.tsx:223 | hover:text-link-hover hover:decoration-2 → Hover                                                                                           | focus-visible:outline-2 focus-visible:outline-offset-ring focus-visible:outline-focus-ring → FocusVisible                                                                                                                                                                                                                                               | active:text-link-hover active:decoration-2 active:underline-offset-4 → Active                                                   |

**Record 3 — every primitive matrix.**

#### `Badge`

| Row                            | Rest | Hover | Focus-visible | Press (active) | Disabled |
| ------------------------------ | ---- | ----- | ------------- | -------------- | -------- |
| (no local interactive element) | N/A  | N/A   | N/A           | N/A            | N/A      |

#### `Button`

| Row               | Rest                                                                                                                                                                                                                                                                                                 | Hover                                    | Focus-visible                                                   | Press (active)                             | Disabled                                                                                           |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- | --------------------------------------------------------------- | ------------------------------------------ | -------------------------------------------------------------------------------------------------- |
| destructive\|lg   | screens/AccountErasurePanel (packages/design-system/src/screens/AccountErasurePanel/index.tsx:218)                                                                                                                                                                                                   | none                                     | Dialog:FocusVisible                                             | none                                       | Dialog:PrimaryPending                                                                              |
| destructive\|md   | Button:Destructive; Button:AllVariants                                                                                                                                                                                                                                                               | Button:DestructiveHover                  | Button:DestructiveFocusVisible                                  | Button:DestructiveActive                   | none                                                                                               |
| ghost\|lg         | Button:RealisticPageActions                                                                                                                                                                                                                                                                          | none                                     | none                                                            | none                                       | none                                                                                               |
| ghost\|md         | Button:Ghost; Button:AllVariants; screens/ProfileSummary (packages/design-system/src/screens/ProfileSummary/ProfileSummary.stories.tsx:100)                                                                                                                                                          | Button:GhostHover; FavouriteToggle:Hover | Button:GhostFocusVisible; FavouriteToggle:FocusVisible          | Button:GhostActive; FavouriteToggle:Active | FavouriteToggle:Bounded; FavouriteToggle:AddingInFlight; FavouriteToggle:RemovingInFlight          |
| ghost\|unresolved | composites/FavouriteToggle (packages/design-system/src/composites/FavouriteToggle/index.tsx:115); composites/FavouriteToggle (packages/design-system/src/composites/FavouriteToggle/index.tsx:126); composites/FavouriteToggle (packages/design-system/src/composites/FavouriteToggle/index.tsx:171) | FavouriteToggle:Hover                    | FavouriteToggle:FocusVisible                                    | FavouriteToggle:Active                     | FavouriteToggle:AddingInFlight; FavouriteToggle:Bounded; FavouriteToggle:RemovingInFlight          |
| primary\|lg       | 22 real call sites                                                                                                                                                                                                                                                                                   | Button:Hover                             | Button:FocusVisible                                             | Button:Active                              | Button:Disabled; SignInScreen:Leaving; SignInScreen:Unavailable                                    |
| primary\|md       | 8 real call sites                                                                                                                                                                                                                                                                                    | none                                     | Callout:FocusVisible                                            | none                                       | none                                                                                               |
| secondary\|lg     | 17 real call sites                                                                                                                                                                                                                                                                                   | ReplayAvailabilityList:Hover             | ReplayAvailabilityList:FocusVisible; UploadControl:FocusVisible | ReplayAvailabilityList:Active              | MatchDetailPanel:DownloadPreparing; Dialog:PrimaryPending; ArchivalControl:Submitting              |
| secondary\|md     | 19 real call sites                                                                                                                                                                                                                                                                                   | Button:SecondaryHover                    | Button:SecondaryFocusVisible                                    | Button:SecondaryActive                     | primitives/ErrorState (packages/design-system/src/primitives/ErrorState/ErrorState.stories.tsx:57) |
| unresolved\|lg    | primitives/Dialog (packages/design-system/src/primitives/Dialog/index.tsx:127); primitives/Dialog (packages/design-system/src/primitives/Dialog/index.tsx:138)                                                                                                                                       | none                                     | Dialog:FocusVisible                                             | none                                       | Dialog:PrimaryPending                                                                              |

#### `Callout`

| Row                            | Rest | Hover | Focus-visible | Press (active) | Disabled |
| ------------------------------ | ---- | ----- | ------------- | -------------- | -------- |
| (no local interactive element) | N/A  | N/A   | N/A           | N/A            | N/A      |

#### `Dialog`

| Row                                                             | Rest                                                       | Hover | Focus-visible | Press (active) | Disabled |
| --------------------------------------------------------------- | ---------------------------------------------------------- | ----- | ------------- | -------------- | -------- |
| h2 @ packages/design-system/src/primitives/Dialog/index.tsx:102 | packages/design-system/src/primitives/Dialog/index.tsx:102 | none  | none          | none           | none     |

#### `EmptyState`

| Row                            | Rest | Hover | Focus-visible | Press (active) | Disabled |
| ------------------------------ | ---- | ----- | ------------- | -------------- | -------- |
| (no local interactive element) | N/A  | N/A   | N/A           | N/A            | N/A      |

#### `ErrorState`

| Row                            | Rest | Hover | Focus-visible | Press (active) | Disabled |
| ------------------------------ | ---- | ----- | ------------- | -------------- | -------- |
| (no local interactive element) | N/A  | N/A   | N/A           | N/A            | N/A      |

#### `Field`

| Row | Rest               | Hover       | Focus-visible      | Press (active) | Disabled       |
| --- | ------------------ | ----------- | ------------------ | -------------- | -------------- |
| lg  | Field:SizeLg       | none        | none               | none           | none           |
| md  | 10 real call sites | Field:Hover | Field:FocusVisible | none           | Field:Disabled |

#### `Link`

| Row        | Rest              | Hover                    | Focus-visible                          | Press (active)                       | Disabled |
| ---------- | ----------------- | ------------------------ | -------------------------------------- | ------------------------------------ | -------- |
| inline     | 7 real call sites | none                     | none                                   | Link:ActiveInline                    | none     |
| standalone | 5 real call sites | Link:Hover; Footer:Hover | Link:FocusVisible; Footer:FocusVisible | Link:ActiveStandalone; Footer:Active | none     |

#### `Menu`

| Row       | Rest              | Hover      | Focus-visible                              | Press (active) | Disabled                     |
| --------- | ----------------- | ---------- | ------------------------------------------ | -------------- | ---------------------------- |
| actions   | 6 real call sites | none       | none                                       | none           | Menu:ActionsWithDisabledItem |
| selection | 7 real call sites | Menu:Hover | Menu:FocusVisible; Menu:KeyboardNavigation | Menu:Active    | Menu:LoadingItem             |

#### `Page`

| Row                                                            | Rest                                                    | Hover | Focus-visible | Press (active) | Disabled |
| -------------------------------------------------------------- | ------------------------------------------------------- | ----- | ------------- | -------------- | -------- |
| main @ packages/design-system/src/primitives/Page/index.tsx:64 | packages/design-system/src/primitives/Page/index.tsx:64 | none  | FocusVisible  | none           | none     |

#### `Panel`

| Row                            | Rest | Hover | Focus-visible | Press (active) | Disabled |
| ------------------------------ | ---- | ----- | ------------- | -------------- | -------- |
| (no local interactive element) | N/A  | N/A   | N/A           | N/A            | N/A      |

#### `Section`

| Row                            | Rest | Hover | Focus-visible | Press (active) | Disabled |
| ------------------------------ | ---- | ----- | ------------- | -------------- | -------- |
| (no local interactive element) | N/A  | N/A   | N/A           | N/A            | N/A      |

#### `Skeleton`

| Row                            | Rest | Hover | Focus-visible | Press (active) | Disabled |
| ------------------------------ | ---- | ----- | ------------- | -------------- | -------- |
| (no local interactive element) | N/A  | N/A   | N/A           | N/A            | N/A      |

#### `StatValue`

| Row                            | Rest | Hover | Focus-visible | Press (active) | Disabled |
| ------------------------------ | ---- | ----- | ------------- | -------------- | -------- |
| (no local interactive element) | N/A  | N/A   | N/A           | N/A            | N/A      |

#### `Table`

| Row                                                                          | Rest                                                      | Hover        | Focus-visible | Press (active) | Disabled |
| ---------------------------------------------------------------------------- | --------------------------------------------------------- | ------------ | ------------- | -------------- | -------- |
| div[role=region] @ packages/design-system/src/primitives/Table/index.tsx:153 | packages/design-system/src/primitives/Table/index.tsx:153 | none         | FocusVisible  | none           | none     |
| tr @ packages/design-system/src/primitives/Table/index.tsx:237               | packages/design-system/src/primitives/Table/index.tsx:237 | RowLinkHover | none          | RowLinkActive  | none     |
| a @ packages/design-system/src/primitives/Table/index.tsx:281                | packages/design-system/src/primitives/Table/index.tsx:281 | RowLinkHover | none          | RowLinkActive  | none     |

#### `Text`

| Row                            | Rest | Hover | Focus-visible | Press (active) | Disabled |
| ------------------------------ | ---- | ----- | ------------- | -------------- | -------- |
| (no local interactive element) | N/A  | N/A   | N/A           | N/A            | N/A      |

#### `Tooltip`

| Row                                                                  | Rest                                                        | Hover                                                                                                                               | Focus-visible                                                                                                                                                           | Press (active) | Disabled |
| -------------------------------------------------------------------- | ----------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------- | -------- |
| button @ packages/design-system/src/primitives/Tooltip/index.tsx:259 | packages/design-system/src/primitives/Tooltip/index.tsx:259 | HoverRevealed; CountryFlag:FlagHoverRevealed; ProfileSummary:BoardFlagHoverRevealed; ProfileSummary:BoardLongAliasFlagHoverRevealed | KeyboardFocusRevealed; DismissedAfterEscape; CountryFlag:FlagKeyboardFocusRevealed; CountryFlag:FlagDismissedAfterEscape; ProfileSummary:BoardFlagKeyboardFocusRevealed | none           | none     |

<!-- state-coverage:end -->

**8c. Record 2 — every handoff, all 29 spec files re-read end to end this pass (not the 6 the
prior hand-back read), quoted with file:line.**

**Counting convention, decided this pass and held to everywhere below (the third thing
`reviewer`'s REJECT on PR #80 found wrong — this table counted `footer.md`'s two citations as
three names split across a not-counted third, `structural-tier.md:549`'s one citation as two
because it named two controls, and `privacy-data-rights.md:284-286`'s one citation as five for the
same reason, three different rules in one column): **one quoted citation is one handoff**, whatever
number of controls its own sentence names and whether or not another citation elsewhere repeats
the same control's name. A citation that turns out, on the judgment in 8e, not to name a real
handoff at all (`archival-control.md:196`'s second name, the privacy link — F11/T596) is still one
citation counted here; 8e is where "true" or "false" is decided, not this tally. This is the
convention `scripts/checks/state-coverage.mjs --check-citations` can assert without reading a
single word of judgment: it parses every quoted citation in this row and fails when a table row's
own `Handoffs` number disagrees with the count it found — so a row cannot drift from its own
citations the way this one already has, twice.

Every citation below is a verbatim quote, checked line-for-line against the file this pass (a
citation found to point at the wrong line, quote the wrong text, or cite a sentence that turns out
not to be a deferral at all, is corrected in place rather than carried over — `analysis-
timeline.md:39` was half a quote, actually at `:38-39`; `structural-tier.md:549` and `:344` were
each one line short of where their own quote's second half sits, `:550-551` and `:344-345`;
`shared-primitives.md:615`/`:616` had the right two lines but the wrong two states, actually
`:616-617` (focus-visible) and `:618` (active); `privacy-data-rights.md:284-286` over-ran its own
quote by a line, actually `:284-285`, and misquoted `` `Button`s `` as `` `Button`'s ``;
`third-party-objection.md:217` and `PlayerResultRow.stories.tsx:64-65` were each one line short of
their own quote's real end — all found and fixed by the citation checker's first run over this
table, which is exactly why it exists): **`match-history.md` gains a third citation** (`:186-187`,
the active-state deferral the prior tally's `:169, :171` missed — hover and focus-visible only).
Recounted under the new one-citation-one-handoff convention, the total moves from the prior
sweep's 48 to **41** — every multi-name citation (`footer.md`, `privacy-data-rights.md`,
`structural-tier.md:550-551`, `archival-control.md`) now counts once, not once per name; the
detail of which names a citation carries is still in its own quote, read in full in 8e, not lost by
counting the citation once.

| File                       | Handoffs | Cited lines (verbatim)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| -------------------------- | -------: | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GOVERNANCE.md`            |        0 | —                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `README.md` (§1-H4)        |        0 | —                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `analysis-timeline.md`     |        2 | `:38-39` "a bare, unstyled … `Button` firing … has no bespoke states beyond `Button`'s own" (filed under **N6**, no fixed owner — the consumer is in `apps/web`; this citation names the pre-analysis trigger button §1 says is "not part of this component's anatomy", never `AnalysisTimeline`'s own). `:288` "`Button`s (`Recompute`, \"Try requesting analysis\") follow `Button`'s own states" (filed under **AnalysisTimeline**, target primitives/Button — its own two real `Button`s, §5's anatomy, a different pair from `:38-39`'s).                                                                                                                                                                                                                                                            |
| `archival-control.md`      |        1 | `:196` "owned by `Button` and by the privacy link" (filed under **ArchivalControl**; one citation, two names — `Button` and the privacy link itself, the second false: F11/T596, since the link is local, not a `Link` instance).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `capture-state-badge.md`   |        1 | `:143` "none. `Badge`'s own rule holds here unchanged" (filed under **CaptureStateBadge**, target primitives/Badge).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `civilisation-icon.md`     |        1 | `:78` "The enclosing `MatchRow` is a single link and owns the hover fill" (filed under **CivilisationIcon**, target composites/MatchRow).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| `color-tokens.md`          |        0 | —                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `country-flag.md`          |        0 | §4's handoff (`:110-113`) is superseded by §11.6 (`:372-395`), which now states the flag's own states directly — 0 live handoffs, corrected from the prior tally's 1.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `favourite-toggle.md`      |        1 | `:98` "owned entirely by `Button/ghost`" (filed under **FavouriteToggle**, target primitives/Button, `ghost`).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| `favourites-list.md`       |        2 | `:110-111` "`RemoveControl`: `FavouriteToggle`'s own hover/focus" (**corrected from the prior citation's `:113-114`, which pointed one clause too late**) and `:126` "`RemoveControl` keeps `FavouriteToggle`'s own active" — two citations, the same control (`RemoveControl` → `FavouriteToggle`) named across two state clauses (filed under **FavouritesList**, target composites/FavouriteToggle — **F19**).                                                                                                                                                                                                                                                                                                                                                                                         |
| `footer.md`                |        2 | `:102` "`PrivacyNoticeLink` and `ObjectionLink` only: colour moves to `link-hover`" (hover) and `:106` "are now the `Link` primitive itself" (active) — two citations, each naming both `PrivacyNoticeLink` and `ObjectionLink`; `:104`'s focus-visible bullet draws the standard ring directly rather than naming `Link`, so it carries no citation here — all filed under **Footer**, target primitives/Link, `standalone`.                                                                                                                                                                                                                                                                                                                                                                             |
| `game-asset-tokens.md`     |        0 | —                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `manual-upload.md`         |        2 | `:180` "the `Choose file` control and `SubmitButton` per `Button`" (hover), `:192` "pressed states per `Button`" (active) — filed under **UploadControl**, target primitives/Button, `secondary`\|`lg`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `map-thumbnail.md`         |        1 | `:73` "The enclosing `MatchRow` link owns the row hover fill" (filed under **MapThumbnail**, target composites/MatchRow).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| `match-history.md`         |        3 | `:169` "`DownloadAction`: per `Button`" (hover), `:171` "`DownloadAction`: per `Button`" (focus-visible), `:186-187` "`DownloadAction`: per `Button`" (active — **missed by every prior pass, found in this audit**) — filed under **MatchDetailPanel**/**ReplayAvailabilityList** (both consume this spec), target primitives/Button, `secondary`\|`lg` — **F7**.                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| `player-avatar.md`         |        0 | —                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `player-colour-swatch.md`  |        1 | `:93` "The enclosing row link owns the hover fill" (filed under **N7**, no fixed owner — true wherever the swatch is composed: MatchRow, PlayerResultRow, FavouritesList).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `player-search.md`         |        0 | `:207-232` describes `Input`/`PlayerResultRow`'s own recipe directly, never delegated — corrected from the prior tally's 2; the two "per `Skeleton`"/cross-reference mentions (`:164`, `:253`-ish elsewhere) name a shared _rule_, not a painted state, the same distinction `N6` already draws for `analysis-timeline.md`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| `privacy-data-rights.md`   |        1 | `:284-285` "owned by the `Button`s, the `DownloadLink`, the `ErasedScreen`'s privacy-notice link, the `Dialog`'s actions and the `Acknowledgement` checkbox" — one citation, five names (filed under **DataExportPanel**/**AccountErasurePanel**). `:288` and `:313` elaborate two of those five (`DownloadLink` → Button/primary; `ErasedScreen`'s link → Link/inline) rather than adding new ones; `privacy-data-rights.md:420`'s "per `Button`" is a stacking-order convention (`recommended-position action first`), not a hover/focus/active deferral — cited by its own full path, deliberately outside this row's bare-`:line` count, so it is verified without inflating the Handoffs tally (corrected in this audit).                                                                            |
| `privacy-notice.md`        |        1 | `:523` "`ObjectionCallToAction` hovers as `Button/secondary`" (filed under **PrivacyNotice**, target primitives/Button, `secondary\|lg` at the size the anchor renders — **F10**: accurate about the classes; that row's hover is elsewhere, unnamed by this spec).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| `profile-summary.md`       |        5 | `:134` "switcher trigger and menu items per `Menu`" (hover) and `:141` "per `Button` and `Menu`" (active) — two citations; `profile-summary.md:138`'s focus-visible bullet ("standard ring on the trigger, on menu items, and on the ghost actions") describes the ring directly rather than deferring — cited by its own full path so it is verified without counting toward this row's own tally; `:869` "the pointer over the flag opens the tooltip" (hover), `:873` "the identity bar's focus stops are now the flag …" (focus-visible), `:882` "pressing the flag pins its tooltip open" (active) — three more citations. Five total: the switcher pair filed under **ProfileSummary**→Menu/Button (F15/F16-carried), the flag trio under **ProfileSummary**→Tooltip.                               |
| `replay-availability.md`   |        2 | `:157` "`AvailabilityBadge`: none, per `Badge`'s own rule" (filed under **ReplayAvailabilityList**, target primitives/Badge). `:158` "`DownloadAction`: per `Button`" (target primitives/Button, `secondary`\|`lg` — missed by the prior sweep, found in the pass before this one).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| `shared-primitives.md`     |        5 | `:242-243` "— none; the root is not interactive. Actions inside it have their own" (hover / active) (filed under **N4**, Callout, no fixed owner). `:422` "The trigger button follows `Button` `secondary`'s own active recipe in full" (filed under **Menu**, target primitives/Button, `secondary` — provenance, not a gap). `:560` "hover, active and disabled all belong to the `Button`s inside it" (filed under **Dialog**, target primitives/Button — **F3**). `:616-617` "none unless the value is a link, in which case the standard ring applies to the link" (focus-visible) and `:618` "none" (active) (filed under **N5**, StatValue, no fixed owner and no live instance).                                                                                                                  |
| `sign-in-screen.md`        |        1 | `:69` "owned entirely by `Button`" (filed under **SignInScreen**, target primitives/Button, `primary`\|`lg` — **F5**, true of the default state, imprecise about outcome-state buttons).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `site-header.md`           |        1 | `:296-298` "`ThemeControl`'s own states … are `Menu`'s, unchanged by this composition" (filed under **SiteHeader**, target primitives/Menu, `selection` — F15/F16-carried; no line at all in the prior tally, found in the pass before this one).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `structural-tier.md`       |        6 | `:441` "A `Panel` is never itself interactive" (filed under **N1**, Panel, no fixed owner). `:344-345` "none of its own. Its heading is not a control … the components inside it carry their own" (filed under **N2**, Section, no fixed owner). `:550-551` "Text that responds to a pointer is a `Link` (§9) or sits inside a `Button`" — one citation, two names (filed under **N3**, Text, no fixed owner). `:552` "none of its own. `Text` is not focusable" (filed under **N3**, same). `:1036` "none of its own; the action inside it carries `Button`'s" (filed under **EmptyState**, target primitives/Button, `secondary`\|`md` — **F4**). `:1125` "none of its own; the recovery action carries `Button`'s" (filed under **ErrorState**, target primitives/Button, `secondary`\|`md` — **F4**). |
| `third-party-objection.md` |        2 | `:217-218` "the submit button (per `Button`)" (hover), `:230` "The button is per `Button`" (active) — filed under **ThirdPartyObjectionForm**, target primitives/Button. Corrected from the prior tally's 3: the focus-visible bullet (`:223-225`) names the same standard ring on three elements without deferring any of their _own_ states to another spec, so it is not counted here.                                                                                                                                                                                                                                                                                                                                                                                                                 |
| `tooltip.md`               |        0 | —                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `typography-tokens.md`     |        0 | —                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |

**Total: 41 handoffs across 20 files with at least one**, one quoted citation per handoff, a number
`node scripts/checks/state-coverage.mjs --check-citations` recounts from this table's own citations
every run and asserts against the `Handoffs` column and this line, rather than either being
restated by hand (its own total citation count across 8c/8c-bis/8d/8e together is higher — 8d
re-quotes several of this table's own citations in full-path form to stand alone as findable text,
and 8e's F5/F7 do the same for one each; the checker verifies every one of those too, just not
against this row total). Moved from the prior sweep's 48 by the
counting-convention change above, not by any citation gained or lost: `match-history.md` still
gains its third citation over the sweep before this one (`:186-187`, the active-state deferral
`:169`/`:171` never covered — the same shape as the file's own hover/focus-visible citations,
missed because the sentence sits four paragraphs below them, past an intervening remediation
note); `footer.md` (3→2), `favourites-list.md` (1→2), `privacy-data-rights.md` (5→1),
`profile-summary.md` (6→5), `structural-tier.md` (7→6) and `archival-control.md` (2→1) each move
only because a multi-name citation now counts once instead of once per name, or a same-control
citation pair now counts twice instead of once. 9 files carry zero (`GOVERNANCE.md`,
`README.md`'s own earlier sections, `color-tokens.md`, `country-flag.md`, `game-asset-tokens.md`,
`player-avatar.md`, `player-search.md`, `tooltip.md`, `typography-tokens.md`). Every handoff is
filed above under the component whose control it concerns (in **bold**) — 8d's no-owner list for
one no directory owns — and judged in 8e below against the generated region at the consumer's own
variant and size, for every state the citation names, not hover alone; a finding is recorded where
that judgment finds the claim false, incomplete, or (this pass) newly resolved, and left true and
unremarked otherwise; none dropped.

**8c-bis. Story comments and rendered text carry the same claim a spec sentence does, and only
spec files were counted before this pass.** Swept every `*.stories.tsx` under
`packages/design-system/src/{primitives,composites,screens}` for the same deferral vocabulary —
`` per `X` ``, `owned (entirely) by`, `belongs`/`belong to`, `covered by`, `already covered`,
`follows`/`follow … states`, `carries`/`carry its`/`their own`, and (widened by `reviewer`'s fourth
REJECT on PR #80) ``are `X`'s``, ``live in `X`'s own``, `` deferred to `X` ``, `` `X`'s stories
for ``, ``inherits `X`'s``, and (widened again, T594 B3, `reviewer`'s fifth REJECT on PR #80/#79)
bare `owns`/`owned` and the singular ``is `X`'s`` — in a story's own comment and in a
`*NotApplicable` story's rendered
text alike, not `*NotApplicable` stories only, since a comment attached to a real capturing story
(`ThirdPartyObjectionForm`'s `Hover`/`Active`) defers a sibling control's state the same way, and
across a comment block or a rendered `<p>`'s own text run rather than one physical line at a time,
so a phrase prettier wraps is never invisible to it. `scripts/checks/state-coverage.mjs
--check-citations` greps this same vocabulary over the live tree every run and fails when a hit is
outside every cited line's own prose block below and outside the exclusion paragraph after the
table — a hit is excused only when one of that component's own cited lines is _both_ in the hit's
own block _and_ within `DEFERRAL_CITATION_WINDOW` physical lines of the hit itself, that script's
own constant, cited here rather than restated as a bare number that could drift from it (T594 M4,
`reviewer`'s fifth REJECT: block membership alone let one citation anywhere in a 30+-line block
excuse every hit in it, e.g. `AccountErasurePanel.stories.tsx` 101-135 — **within
`DEFERRAL_CITATION_WINDOW` lines of a cited line inside the same block now, corrected from this
paragraph's own prior claim of "genuinely quote level" — an uncited deferral planted within that
same window of a cited line inside the same block is still excused, exactly as the code comment at
`state-coverage.mjs:3525-3539` already stated and this paragraph did not — heading corrected to
match its own body in the row 8 sweep's own item 6, having until then still read "genuinely quote
level, not block level," the exact framing this paragraph itself retracts**), and never merely to
whether its component has a row at all (the fourth REJECT's own second
finding: the old, component-level check let a new, false deferral inside an already-listed component
pass unseen). The table's own row count (up from fourteen once `owns`/`owned`/the singular `is X's`
were admitted — `CivilisationIcon`, `MapThumbnail`, `PlayerColourSwatch` and `Panel` are new rows,
each true; `SiteHeader`, `Callout`, `Menu`, `Page`, `Section` and `Text` carry new, excluded false
positives instead, named in the exclusion paragraph below) is `node
scripts/checks/state-coverage.mjs --check-citations`'s own printed "deferral-vocabulary hits" line,
cited here rather than restated as a number that could drift from it (T594's row 8 sweep, item 7 —
a hand-typed "Eighteen" carried no tripwire of its own). Each row is quoted, filed under the
component whose story it is, and
judged the same way as 8c — every citation here immediately followed by its own quote, so the
checker can verify it the same way it verifies 8c's own table.

| Component                 | Quotes                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `AnalysisTimeline`        | `:176` "follow `Button`'s own states" (comment, quoting the spec) and `:183` "follow `Button`'s own states." (rendered text) — target `secondary\|lg`, no own hover — **false, same as F1** (the story's own rendered text repeats the spec's claim verbatim, so it is false for the identical reason).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| `MatchDetailPanel`        | `:520` "`DownloadAction`: per `Button`." (comment, quoting the spec) and `:535-536` "Its `DownloadAction` button is real — hover, focus-visible and press all paint — but the frames that prove it are `ReplayAvailabilityList`'s own stories, not `Button`'s." (rendered text) — target `secondary\|lg` — **corrected 2026-09-19 (T595's own known item (c)): the rendered text used to read "carries its own, per `Button`'s stories," false for all three states (this audit's own widening — focus-visible and press, not only the hover the comment already flagged).** Now true: `secondary\|lg`'s own hover, focus-visible and press cells are `ReplayAvailabilityList:Hover`, `ReplayAvailabilityList:FocusVisible; UploadControl:FocusVisible` and `ReplayAvailabilityList:Active`, none of them `Button.stories.tsx`'s own.                                                                                                                                                                                                                                                |
| `ReplayAvailabilityList`  | `:266` "`DownloadAction`: per `Button`" (comment, quoting the spec) on the `Hover` story itself — not a deferral, context for why the story exists — **not counted** (this is the story that supplies `secondary\|lg`'s own coverage, not a claim of absence).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| `Button`                  | `:87` "`ghost\|md`'s own hover was already covered elsewhere" (comment, on the new `GhostHover` story) — not a deferral, context for why the story exists despite `ghost\|md`'s own hover already being real elsewhere (`FavouriteToggle:Hover`) — **not counted**, the same shape as `ReplayAvailabilityList`'s own `:266` and `FavouriteToggle`'s own `:103` above (added 2026-09-19, T595, gap (c): `SecondaryHover`/`GhostHover`/`DestructiveHover` close `secondary\|md` and `destructive\|md`'s own hover, real gaps F13 names; `ghost\|md`'s was already covered before this trio, and this comment says so rather than claiming a gap that was not one).                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `FavouriteToggle`         | `:103` "owned entirely by `Button/ghost`" (comment, quoting the spec) on the `Hover` story itself — the same shape as `ReplayAvailabilityList`'s own `:266` above — not a deferral, context for why `Hover`/`FocusVisible`/`Active` are captured directly here — **not counted** (found only once the vocabulary sweep admitted `owned entirely by`, `reviewer`'s fourth REJECT on PR #80).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `SignInScreen`            | `:79` "owned entirely by `Button`" (comment, quoting the spec) and `:86` "carries its own, per `Button`'s stories" (rendered text) — target `primary\|lg`, fully covered — **true**.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| `ThirdPartyObjectionForm` | `:68` "the submit button (per `Button`)" (comment on the `Hover` story) and `:91` "the button per `Button`" (comment on the `Active` story) — target `primary\|lg`, fully covered — **true**.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| `AccountErasurePanel`     | `:122-124` "owned by the `Button`s, the … `DownloadLink`, the `ErasedScreen`'s privacy-notice link, the `Dialog`'s actions and the … `Acknowledgement` checkbox" (comment, quoting the spec) and `:150-151` "dialog's actions (`destructive`, `secondary`) defer hover, focus-visible and press to … `Button` — real, though not always by `Button.stories.tsx`'s own stories" (rendered text) — **corrected 2026-09-19 (T595, F20 closed)**: both used to claim the dialog's `destructive` action had press covered by `DestructiveActive` (`destructive\|md`, never this screen's own `lg`), the shape F20 found false. The rewritten text is **true**: `destructive\|lg`'s own focus-visible is real via `Dialog:FocusVisible`, never `Button.stories.tsx`'s own story; its hover and press have no frame anywhere at `lg` (F14, still open, not this task's); `secondary\|lg`'s hover, focus-visible and press are all real too, but via `ReplayAvailabilityList`/`UploadControl`, never `Button`'s own per-variant stories — the same "true elsewhere" shape as F1/F2/F4/F6/F7. |
| `ProfileSummary`          | `:496` "The switcher's own hover/focus/active are `Menu`'s stories" (comment) and `:572-573` "carry theirs, per `Menu`" (rendered text, `RatingEntryHoverNotApplicable`) — **false for hover, same shape as F15**: `Menu`'s own trigger has no hover frame anywhere in the tree (F15), so neither quote's claim holds for hover; both are added to the F15/F16-carried finding below as this component's own story-level echo of the spec's `profile-summary.md:134` claim, not a new, separate false claim.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `ArchivalControl`         | `:80` "carr[ies] its own hover, focus and active states" (comment) already flags the rendered claim below it as known-false; `:90` "carry their own hover, focus and active states" (rendered text) — **false for the privacy link (F11) and for the button's hover (F2, `secondary\|lg`)** — the comment's own self-correction is accurate; the rendered text it describes is the false artifact, left uncorrected pending T596's design decision, exactly as the comment says.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `DataExportPanel`         | `:126` "owned by the `Button`s, the `DownloadLink`… the sections" (comment, quoting the spec) and `:150-151` "its hover, focus-visible and press are all real, but the frames that prove them are `ReplayAvailabilityList`'s and `UploadControl`'s own" (rendered text) — **corrected 2026-09-19 (T595)**: the pair used to read "already covered by `Button.stories.tsx`'s per-variant stories," true for the ownership fact and false for the story named — `RequestButton` is `secondary\|lg` (`index.tsx:118-119,215`), and `Button.stories.tsx`'s own per-variant stories force `md`, never `lg`, the same shape F20 found in `AccountErasurePanel` and this audit found in `MatchDetailPanel`. The generated `secondary\|lg` row's own hover, focus-visible and press cells all read `ReplayAvailabilityList`/`UploadControl`, never `Button.stories.tsx`'s own — the rewritten text now states exactly that.                                                                                                                                                                  |
| `Dialog`                  | `:130` "hover, active and disabled all belong to the `Button`s inside it" (comment) and `:138` "Hover, active and disabled all belong to the `Button`s inside it" (rendered text) — **true as a blanket statement**: this specific story renders no actions at all (a malformed-call-site demonstration), so there is no variant/size this claim can be falsified against; `Dialog`'s real actions are covered per F3/F20 above, a different story's own claim.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `Section`                 | `:124` "the components inside it carry their own" (comment, quoting `structural-tier.md` §6) and `:130` "The components inside it carry their own." (rendered text) — target: none, the same no-fixed-owner shape N2 already files — **true as a blanket statement**: `Section` renders no local interactive element of its own (generated Record 1: no entry) and this story's own illustrative render composes no child to falsify the claim against, the same reason `Dialog`'s blanket claim above is true.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `Callout`                 | `:97` "hover / active — none; the root is not interactive. Actions inside it have their own." (comment, quoting the spec, reused from N4/8c's own `shared-primitives.md:242-243`) and `:103` "carry their own hover and active states." (rendered text) — this story's own render composes `<Button variant="primary">Try again</Button>` at `:108`, no `size` given, so `primary\|md` (the primitive's own default) — **false for both hover and active**: the generated `Button` matrix's own `primary\|md` row reads `hover: none`, `active: none` (F14's own subject) — a third component whose story-level text repeats a claim F14 already shows false, added there rather than filed as a separate finding.                                                                                                                                                                                                                                                                                                                                                                   |
| `Text`                    | `:134` "none of its own. `Text` is not focusable" (comment, quoting `structural-tier.md` §8, reused from N3/8c's own `:552`) and `:142-143` "that ring belongs to the caller, not to this component." (rendered text) — target: none, the same no-fixed-owner shape N3 already files — **true as a blanket statement**: this story renders `<Text role="display">Recent matches</Text>` with no `tabIndex` at all, so there is no focused instance here to falsify the claim against, the same reason `Section`'s and `Dialog`'s blanket claims above are true.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `Panel`                   | `:167` "hover — none. A `Panel` is never itself interactive" (comment, quoting `structural-tier.md` §7) and `:175` "that link owns its own hover, focus and active states." (rendered text) — target: none, the same no-fixed-owner shape N2/N3 already file — **true as a blanket statement**: `Panel` renders no local interactive element of its own (generated Record 1: no entry) and this story's own illustrative render composes no real link to falsify the claim against, the same reason `Section`'s, `Dialog`'s and `Text`'s blanket claims above are (added 2026-09-19, T594 B3: found once the vocabulary sweep admitted `owns`).                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `CivilisationIcon`        | `:120` "the enclosing row link owns interaction, this mark never does." (comment, quoting `civilisation-icon.md` §4) and `:126` "The enclosing row's own link owns the hover fill." (rendered text) — target: none, the same shape `FavouriteToggle`'s and `ReplayAvailabilityList`'s own "owned entirely by" rows above are — **true**: generated Record 1 lists `composites/CivilisationIcon` with `(no local interactive element)`, and its own consumers (`MatchRow` `index.tsx:397`, `PlayerResultRow` `index.tsx:54`, `FavouritesList` `index.tsx:244`) each carry a real row-link hover/focus-visible/active of their own — the enclosing link genuinely does own it (added 2026-09-19, T594 B3: found once the vocabulary sweep admitted `owns`).                                                                                                                                                                                                                                                                                                                            |
| `MapThumbnail`            | `:146` "the enclosing row link owns interaction, this mark never does." (comment, quoting `map-thumbnail.md` §4) and `:152` "The enclosing row's own link owns the hover fill." (rendered text) — same shape and same verdict as `CivilisationIcon` immediately above — **true** (added 2026-09-19, T594 B3).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| `PlayerColourSwatch`      | `:144` "the enclosing row link owns interaction, this chip never does." (comment, quoting `player-colour-swatch.md` §4) and `:150` "The enclosing row's own link owns the hover fill." (rendered text) — same shape and same verdict as `CivilisationIcon` above — **true** (added 2026-09-19, T594 B3).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |

**Excluded — grep hits outside this list, named rather than left silent, none of them a
hover/focus-visible/active deferral (Record 1's own tracked axes):** `PlayerResultRow.stories.tsx:65-66`
("Those states belong to `SearchBox`'s own `ResultsRegion`") is a disabled/loading/error/empty
provenance note; `Badge.stories.tsx:125-126` ("a failure belongs to whatever produced the state it names, never to the badge.") and `PrivacyNotice.stories.tsx:258-259` ("A failure belongs to the route a link leads to, never to the sentence stating the right.") are both about the `error`/
`disabled` vocabulary entry, not hover/focus-visible/active; `SiteHeader.stories.tsx:189` ("that
state belongs to `Menu`") is about the `expansion` vocabulary entry (`Menu`'s own disclosure state,
not `SiteHeader`'s hover/focus/active); `ProfileSummary.stories.tsx:551` ("carries its own mark
independent of `isPrimary`") is about the selection-badge _mark_, not a hover/focus/active
signal — a different sense of "carries its own" than the one this row tracks.
`PrivacyNotice.stories.tsx:27` ("renders nothing, per `Callout`'s own empty rule") is about the
`empty` vocabulary entry, not hover/focus-visible/active.
`AccountErasurePanel.stories.tsx:65-66` ("not a `Button` instance and not owned by any dialog
or … checkbox") is its own, separate comment block from the row's `:122-124`/`:150-151` citations above (no
blank line separates a comment from the code or rendered text immediately below it, so those two
share one block; this one, about `ErasedScreen`'s link, is a block of its own, whose own last line
is the `const erasedScreenLinkClip = …` declaration at `:72` (corrected 2026-09-19 — M5: the prior
text named `:72` itself as the blank line; the blank line that actually closes the block is `:73`))
— it states the link is **not** deferred, the opposite of a deferral, so it is read and excluded
rather than filed as a claim to judge. **Added 2026-09-19 (T595, gap (b)).**
`AccountErasurePanel.stories.tsx:102` ("owned by no component with its own") is a third,
separate block from the same file — `AcknowledgementCheckboxFocusVisible`'s own comment (lines
101-110) — stating the acknowledgement checkbox is **not** owned by any other component either, the
same shape as the `:65-66` entry immediately above: read and excluded, not filed as a claim to
judge. `Text.stories.tsx:156` ("Text never paints the
disabled ink — that belongs to a disabled control's own label.", `:150`'s comment quoting the same
sentence) is a second, separate block from the row's own `:134`/`:142-143` citations above (the
`disabled` vocabulary entry, not hover/focus-visible/active — the same shape row 8's own `Badge`/
`PrivacyNotice` exclusions above are).

**Added 2026-09-19 (T594 B3 — the `owns`/`owned`/singular ``is `X`'s`` widening of the vocabulary
itself surfaced these; none is a hover/focus-visible/active deferral).** `SiteHeader.stories.tsx:105`
("owns internally) ever mounts") is about which component mounts/instantiates another (`SiteHeader`
and the `ThemeProvider` it owns internally, `:104-105`), not which one paints a state.
`Callout.stories.tsx:77` ("the same shape `Dialog`'s heading owns") is a cross-reference to a shared
_pattern_, not a state handoff. `Menu.stories.tsx:310` ("already owns.") says which _story_ (this
one's own preceding sentence: which `Selection` above already depicts, `:308-309`) is about the
`selection`/`expansion` vocabulary entry, not which component paints hover/focus/active.
`Page.stories.tsx:306` ("the between-sections rhythm `Page` owns") and `Section.stories.tsx:16`
("owns the space between the components inside it", the component's own Storybook description) and
`Section.stories.tsx:151` ("`Page` owns that between-sections gap") and `Section.stories.tsx:152`
("`Section` owns the between-components gap inside itself") are all about spacing-rhythm ownership
(FR-020's ownership question), not hover/focus/active. `Text.stories.tsx:181`
("A failure has a component that owns it") repeats the `error`/`disabled` vocabulary entry `Text.stories.tsx:156`
above already carries, in `Text`'s own `ErrorNotApplicable` story rather than its
`DisabledNotApplicable` one — not a second, new claim. No hit this grep finds outside the table
above and this paragraph exists — the check that replaces the hand claim this paragraph used to
close with.

**8d. The no-owner list — handoffs whose control no directory owns (unchanged in substance from
the prior sweep; confirmed against the generated region above, which shows every one of `Panel`,
`Section`, `Callout`, `StatValue`, `Text` carrying no local interactive element of its own).**

- **N1.** `Panel`'s handoff, `structural-tier.md:441` "A `Panel` is never itself interactive" — no
  directory named.
- **N2.** `Section`'s handoff, `structural-tier.md:344-345` "none of its own. Its heading is not a
  control … the components inside it carry their own" — no directory named.
- **N3.** `Text`'s handoff, `structural-tier.md:550-551` "Text that responds to a pointer is a
  `Link` (§9) or sits inside a `Button`" (hover/active) and `structural-tier.md:552` "none of its
  own. `Text` is not focusable" (focus-visible) — no directory named (Link/Button/"whatever wraps
  it").
- **N4 (corrected in this pass: the render is not fully covered).** `Callout`'s handoff,
  `shared-primitives.md:242-243` "— none; the root is not interactive. Actions inside it have
  their own" — no directory named; its own illustrative stories happen to use `Button/primary` at
  `md` (the generated `Button` matrix's own `primary|md` row), but that row reads `hover: none`,
  `active: none` — **false for hover and press**, the same cells F14 and 8c-bis's own `Callout`
  row (`:97`/`:103`) already read, and only `rest`/focus-visible are real there. The claim as
  written governs whatever a caller supplies, and remains true in kind (the states genuinely are
  the `Button`'s own to paint); it is this component's own illustrative render that is not, for
  two of the three states Record 1 tracks.
- **N5.** `StatValue`'s handoff, `shared-primitives.md:616-617` "none unless the value is a link,
  in which case the standard ring applies to the link" (focus-visible) and
  `shared-primitives.md:618` "none" (active) — no directory named, and no `StatValue` instance
  anywhere in the tree renders as a link (confirmed: the generated Record 1 region has no
  `StatValue` entry at all).
- **N6 (its own size named, corrected in this pass — T594's REJECT on #80, item 6: judged before
  only against `primary`'s variant, never the size the consumer actually renders).**
  `analysis-timeline.md:38-39` "a bare, unstyled … `Button` firing … has no bespoke states beyond
  `Button`'s own" — a real control in `apps/web`, outside this script's own scan of
  `packages/design-system/src` (the same boundary this package's rules draw everywhere else, and why
  this citation is given in prose rather than the checked `file:line` form the rest of this row
  uses). The consumer is `apps/web/src/features/analysis/AnalysisContainer.tsx`, line 144, rendering
  `Button` with `variant="primary" size="lg"` — the generated `Button` matrix's own `primary|lg` row
  (not `primary|md`, `Callout`'s own illustrative render and N4's subject, whose `hover`/`active`
  cells read `none`) is fully covered, so the handoff is true at the size and row it is actually
  judged against.
- **N7.** `player-colour-swatch.md:93` "The enclosing row link owns the hover fill" — no directory
  named; true wherever the swatch is actually composed (`MatchRow`, `PlayerResultRow`,
  `FavouritesList`, each with its own real hover/focus-visible/active local element in the
  generated Record 1 region).

**8e. Findings — quoting the generated region above rather than restating it. Renumbered against
the rejected PR #80 hand-back's F1-F18: unchanged in substance unless noted; new findings F9a,
F10a; F14, F15/F16 and record 1's own local-element findings corrected against this pass's
mechanical resolution, which turned several prior "confirmed by reading" assertions into cells the
generated region now settles on its own, and left two of them honestly `unresolved` instead.**

- **F1.** `AnalysisTimeline.stories.tsx`'s `HoverFocusActiveNotApplicable` — false for hover. Both
  `Recompute`/"Try requesting analysis" are `secondary|lg` (generated Record 3, `Button`); that
  row's own hover cell is `ReplayAvailabilityList:Hover`, unnamed by this file.
- **F2.** `ArchivalControl.stories.tsx`'s `HoverFocusActiveNotApplicable` — false for hover on the
  button half (`secondary|lg`, same elsewhere pointer as F1); the privacy-link half is F11.
- **F3 (citation corrected 2026-09-19 — M2/M3: `:127,138` is each `<Button` tag's own opening line;
  each `variant` prop is one line below it; corrected again 2026-09-20 — the `destructive` half of
  the supporting parenthetical went stale, the verdict itself did not).** `shared-primitives.md:560`
  and `Dialog.stories.tsx`'s `EmptyHoverActiveDisabledNotApplicable`
  — false for hover. `Dialog`'s own two `Button` instances (`index.tsx:127-128,138-139`,
  `variant={primaryAction.variant ?? 'destructive'}`/`?? 'secondary'`) now resolve mechanically per
  story rather than staying `unresolved`: the generator substitutes each story's own merged `args`
  into the guard/attribute expressions a candidate carries, so `Dialog.stories.tsx`'s `FocusVisible`
  (`args: { primaryAction: { label: 'Turn it off' }, secondaryAction: { label: 'Keep it on' } }`,
  `visualForceState: { role: 'button', name: 'Turn it off' }`) resolves `{primaryAction.label}` to
  `'Turn it off'`, identifies `primaryAction`, and evaluates `primaryAction.variant ?? 'destructive'`
  (no `variant` in this story's own args) to `'destructive'` — the generated `destructive|lg` row's
  own focus-visible cell now reads `Dialog:FocusVisible` directly. `destructive`'s own hover has no
  frame anywhere **at `lg`**, the size `Dialog` actually renders (still true — unaffected by this
  task); the parenthetical this finding used to add for support, "the only other `destructive`
  combination in the tree," no longer proves the stronger claim it was reaching for, because
  `destructive|md` now has a real one (`Button:DestructiveHover`, T595's own gap (c)) — `destructive`
  has a hover frame somewhere in the tree, just not at the size `Dialog` renders, which is what the
  verdict was always judged against and remains true at. `secondary`'s exists elsewhere
  (`secondary|lg`) but is not what "belong to the `Button`s inside it" points a reader toward, and no
  story forces `secondaryAction`'s own state at all.
- **F4 (closed 2026-09-19, T595).** `structural-tier.md:1036,1125` and `EmptyState`/`ErrorState`'s own
  `HoverFocusActiveNotApplicable` stories — both actions are `secondary|md` (generated Record 3
  confirms the size directly — `EmptyState.stories.tsx:33`, `ErrorState.stories.tsx:26` etc.).
  Neither story's own sentence ever names a specific story — both say only "carries `Button`'s
  [states]," an ownership claim, true regardless — so the gap this finding named was the cell
  itself, `secondary|md`'s own hover reading `none` (the `lg` row's elsewhere pointer does not
  apply at this size, F13). `Button.stories.tsx`'s new `SecondaryHover` (T595, gap (c)) closes
  exactly that cell — the generated `secondary|md` row's hover now reads `Button:SecondaryHover`
  directly — so `structural-tier.md`'s and both stories' own "carries `Button`'s" is true in fact
  now, not only in ownership. No source or story text needed changing: neither ever misattributed
  the state to a specific story the way F1/F2/F6/F7 do.
- **F5.** `sign-in-screen.md:69` ("owned entirely by `Button`") is true of the `default` state's
  primary button (`primary|lg`, fully covered) but also covers several `secondary|lg` outcome-state
  buttons the blanket sentence does not distinguish. Spec imprecision, not a story-level false claim.
- **F6.** `manual-upload.md:180` (hover) is half true: `SubmitButton` is `primary|lg` (covered);
  `Choose file`/`Refresh` are `secondary|lg` (elsewhere: `ReplayAvailabilityList:Hover`,
  unnamed here). `:192` (active) is true: `secondary|lg`'s press is covered.
- **F7 (widened in the row-8 audit: `match-history.md` carries a third citation this finding did not
  read; closed 2026-09-20, T595's own known item (c)).** `match-history.md:169,171`, as consumed by
  `MatchDetailPanel` — its own `HoverFocusActiveNotApplicable` _rendered_ text used to read "carries
  its own, per `Button`'s stories," false for a Storybook-only reader: `DownloadAction` is
  `secondary|lg`, no own hover. **The active state carried the identical shape, one clause the prior
  sweep's `:169,171` citation missed**: `match-history.md:186-187` ("`DownloadAction`: per `Button`")
  deferred press the same way, four paragraphs below the hover/focus-visible bullets, past an
  intervening remediation note. The rendered text is now fixed (8c-bis's own `MatchDetailPanel` row
  above carries the current quote): it states the real route directly, "the frames that prove it are
  `ReplayAvailabilityList`'s own stories, not `Button`'s" — a Storybook-only reader of
  `MatchDetailPanel`'s own stories now reaches the truth without needing `match-history.md` or
  `ReplayAvailabilityList` at all. The same spec sentence, consumed by `ReplayAvailabilityList`
  instead, was always true — that file's own `DownloadAction` is exactly the `secondary|lg` row's
  `Hover`/`FocusVisible`/`Active` elsewhere pointer F1, F2 and F6 still name (F4's own subject was
  always `md`, never this `lg` pointer, and is closed on its own terms above).
- **F8.** `Link`'s own matrix gap (generated `Link` matrix, `inline` row) — hover and focus-visible
  both `none`, even though `structural-tier.md` §9 documents `inline`'s hover as visually distinct
  from `standalone`'s. `ActiveInline` covers press; nothing depicts the other two. FR-042's own
  requirement, independent of any handoff.
- **F9.** `SiteHeader`'s `Brand` wordmark anchor (generated Record 1, `composites/SiteHeader`,
  `index.tsx:183`) — `hover:underline`, `coveredBy: none` on all three states, confirmed directly
  by the generated region (no longer "confirmed by reading" — the args-based name match now
  correctly attributes `SiteHeader.stories.tsx`'s `Hover`/`FocusVisible`/`Active` to `NavItem`
  (`index.tsx:209`) instead, via the literal `'Matches'` found in the `items` array the story's own
  `args` reference, and leaves `Brand` and `SkipLink` genuinely uncovered). `site-header.md` §9
  documents `Brand`'s hover as visually distinct from `NavItem`'s (underline vs. fill).
- **F9a.** `SiteHeader`'s `SkipLink` (generated Record 1, `index.tsx:156`) — a real focus ring
  (`focus-visible:outline-2…`), `coveredBy: none` for focus-visible, confirmed directly. No story
  anywhere depicts it — the state that matters most, since it is invisible until focused. Missed by
  every sweep before this one because a `<a ` line grep never matches `<a\n      href=…`
  (`scripts/checks/state-coverage.test.mjs`'s own first fixture is modelled on this element).
- **F10 (closed 2026-09-19, T595 — two halves closed, the third half's own cell narrowed twice and
  left open, named rather than chased a third time).** `PrivacyNotice`'s local anchors, as the
  generated Record 1 region reads them: the `Contents` entry (`index.tsx:490`) is covered on all
  three states, by `Hover`, `FocusVisible` and `Active`; the `InlineLink` recipe (`index.tsx:242`)
  is now covered by its own `InlineLinkHover`/`InlineLinkFocusVisible`/`InlineLinkActive` trio,
  forced at `nth: 9` — its own real DOM position under this component's default `hrefs`, past the
  nine `Contents` entries. `resolveNameMatch`'s own `nth` branch could not place that `nth` at
  first: the candidate pool held one declaration-site slot per `.map()` group regardless of its
  real cardinality, so nine real `Contents` entries occupied exactly one slot and no `nth` past the
  pool's own small size could ever be placed anywhere on this page — closed at the root, not worked
  around: a helper's own real call-site count and a `.map()` group's own resolved array length both
  now contribute their real width to the ordering. The objection-form anchor (`index.tsx:740`) is
  now covered the same way, by `ObjectionCallToActionHover`/`FocusVisible`/`Active`, targeted by
  `selector` rather than `nth` (its own `href={hrefs.objectionForm}` is a literal in every story's
  own args, unique in the whole render). The contact-route link (`index.tsx:797`) reads `none` for
  the class half (it paints no state class at all, T596's own subject, unaffected by this task) but
  `unresolved` for the story half, narrowed twice and still open: first, the `nth` fix above
  correctly rules this element out of `InlineLinkHover`'s own range now (a clean `reject`, not
  `ambiguous`); second, `resolveSelectorMatch`'s own caller now excludes a candidate this story's
  scope confirms `'unreached'` before ever attempting its own attribute, the same guard-fold — but
  the cell's own `unresolved` reason names `ObjectionCallToActionHover`/`FocusVisible`/`Active`, and
  _those_ stories' own args are `{ lastUpdated, hrefs }`, no `controllerContact` — evaluated against
  those stories' own scope, this anchor's guard, `controllerContact ? <a…> : …`, is `'unresolved'`,
  not `'unreached'`. `WithPublishedContact` (`PrivacyNotice.stories.tsx:39-50`) does set
  `controllerContact.contactRoute` to `/contact` and genuinely renders this anchor, but it forces no
  state at all, so it never enters this comparison either way — the gap is not "no story sets
  `controllerContact`," it is that the one story that does carries no `visualForceState`, and the
  three that do never set it. `buildStoryPropsScope` treats a component prop with no destructuring
  default as unknown whenever the story it is evaluating for does not mention it, rather than as
  the `undefined` it actually is at render. That third gap is real, narrower again, and sits in a
  different function than either fix above — named here and in `PrivacyNotice.stories.tsx`'s own
  `InlineLinkHover` comment, filed as **T599** rather than chased a third time in this task (the
  coordinator's own instruction: two fixes for the same cell without closing it is a pattern, and
  the answer to a pattern may be a task rather than another fix). `privacy-notice.md`'s handoff for the
  objection-form anchor (8c's row for that file) is accurate about the classes — the anchor paints
  the same `hover:bg-surface-sunken` that `Button`'s `secondary` variant does. Judged at the size
  the anchor renders (its `px-6` and `text-md` are `lg`'s), the target is `secondary|lg`, and that
  row's own hover cell is `ReplayAvailabilityList:Hover`, unnamed by that spec — the same elsewhere
  pointer as F1, a frame that exists and not a missing one; the anchor's own frame is
  `ObjectionCallToActionHover` now, not that elsewhere pointer, since a local anchor is never a
  `Button` instance regardless of which variant its classes echo.

  **Filed 2026-09-19, outside the generated region, owed to T599 (fix by 2026-09-27, the same
  deadline this row carries) — the same filing shape T598's own paragraph above this register uses,
  held to the same standard: dated, naming the mechanism, naming who owes it, never a silent
  allowlist.**
  - **Mechanism.** `buildStoryPropsScope` (`scripts/checks/state-coverage.mjs`) seeds a story's own
    scope from a component's prop defaults, one entry per destructured prop: a prop with a literal
    default resolves to that default; a prop with **no** default — an optional prop a component
    simply leaves `undefined` when its caller omits it, `PrivacyNotice`'s own `controllerContact?`
    among them — is seeded as `UNRESOLVED` (`{ resolved: false }`), not as the value it actually
    has at render. The merge step immediately after only ever overwrites a key a story's own merged
    `args` object literal names; a key that story never mentions is left exactly as the first step
    set it. For any one story whose own `args` never name such a prop, its value is therefore
    carried as _unknown_ rather than as the _known_ `undefined` a real `<Component {...args} />`
    render would give it — Storybook's own `args` are the complete prop set for that render, so an
    absent key is not a gap in what this pass can see, it is the real, final value. `evaluateGuards`
    then reads that `UNRESOLVED` scope entry and returns `'unresolved'` for any guard testing the
    prop's truthiness, never `'unreached'` — the positive, confirmed-false reading a guard-fold
    (`resolveSelectorMatch`'s own caller, `buildElementCells`'s role path, `resolveDisabledFromStories`)
    needs to rule a candidate out. The candidate is not wrongly credited (every guard-fold in this
    file already leaves a genuinely `'unresolved'` guard alone, never guessed into a match), but it
    cannot be ruled out either, so any cell that depends on ruling it out stays `unresolved` forever,
    for every story that does not happen to also set the prop.
  - **Cells affected today.** `PrivacyNotice`'s contact-route link (`index.tsx:797`) — its
    hover/focus-visible/active cells, all three, `unresolved` against `ObjectionCallToActionHover`/
    `FocusVisible`/`Active`'s own selector match (none of those three stories set
    `controllerContact`). Searched for the same shape elsewhere (a locally-rendered, role- or
    selector-matchable interactive element gated by a ternary or `&&` on an optional prop with no
    destructuring default): `primitives/Menu`'s own footer item (`index.tsx:240`, gated on
    `footerItem?: MenuFooterItem`, no default) is the same shape, but does **not** exhibit the
    defect today — its own credited story, `KeyboardNavigation`, resolves it by literal name match
    (`footerItem.label`), which never consults the guard at all, and no other story forces a
    role-only or `nth`-based state against Menu's `actions` variant without naming it. Not a live
    cell today; worth a second look once this task lands, in case a future story changes that.
    `ArchivalControl`'s own privacy link (`index.tsx:137`, gated on `privacyNoticeHref`) is a
    different, already-filed defect (F11/T596 — it paints no state class at all) and is not this
    mechanism's own subject.
  - **What the change risks.** The correct fix — seed an optional, default-less prop as
    `{ resolved: true, value: undefined }` when a story's own merged `args` do not name it, rather
    than as `UNRESOLVED` — is not confined to one component: it changes what `evaluateGuards`
    returns for **every** guard, on **every** optional prop, in **every** story across this whole
    package, wherever a story currently leaves such a prop unset. That includes guards this task
    never touched, read by `resolveDisabledFromStories` and by `buildElementCells`'s own role path,
    neither of which this task modified. Some of those guards are today `'unresolved'` and safely
    inert (contribute nothing, per this task's own "never guess" rule); the fix would flip an
    unknown number of them to a confirmed `'unreached'`, which can turn a candidate this pass
    currently leaves alone into one it actively excludes or rejects — correct, per real render
    semantics, but a change with its own blast radius across the generated region that has to be
    read cell-by-cell before it ships, the opposite of what a single slice should absorb silently.
  - **The contrast case whoever does this must test.** An optional prop supplied to a component not
    through a story's own `args` object literal but through a `render:` function's own explicit JSX
    prop (`findRenderJsxProps`'s own override, applied _after_ `buildStoryPropsScope` — `MatchRow`'s
    own `match={base}` shape is the real, current example of this route) must still resolve to its
    real, supplied value and must **not** be wrongly treated as `undefined` merely because it is
    absent from `args`. The fix must change only a prop this pass has positively confirmed absent
    from the complete set it can see (`args`, still to be overridden by any `render:` prop after),
    never a prop supplied through a route it simply has not looked at yet.

- **F10a (corrected 2026-09-19; the cell itself resolved by T595's own extractor work, `h1`-`h6`
  added to `INTRINSIC_ROLE`).** `PrivacyNotice`'s `SectionHeading` (generated Record 1,
  `index.tsx:264-266`, `tabIndex={-1}`) carries a real focus ring, and the region's own focus-visible
  cell for it now reads a confirmed `none` — no `visualForceState` in `PrivacyNotice.stories.tsx`
  targets anything but `role: 'link'`, and no story there has a `play()`, so no story depicts the
  heading's focus ring, exactly as this finding concluded by hand before the extractor could say so
  itself. `none` is a real gap, not the script declining, so this finding stands: T595's own further
  scope (a new story, not the extractor) still owes `SectionHeading` a frame. The same shape as F9a:
  a `tabIndex={-1}` heading carrying a same-file focus-ring constant is `state-coverage.test.mjs`'s
  second fixture.
- **F11 (pre-existing).** `ArchivalControl`'s privacy link (generated Record 1,
  `screens/ArchivalControl`, `index.tsx:137`) — zero state classes of any kind, confirmed directly.
- **F12 (pre-existing; closed 2026-09-20, T595's own gap (b)).** `AccountErasurePanel`'s
  acknowledgement checkbox (`index.tsx:270`) — a real focus ring, `coveredBy` used to read `none`;
  the generated region now reads `AcknowledgementCheckboxFocusVisible` directly. Hover/active remain
  correctly not applicable (no class painted) — that half never was a gap and this task left it
  exactly as it was.
- **F13 (root cause of F1-F4, F6-F7; corrected 2026-09-19; closed in part 2026-09-20, T595's own
  Button hover trio, gap (c) — the `secondary|md`/`destructive|md` half this finding names as its
  own root cause is exactly what that trio closes).** Before that trio, the generated `Button`
  matrix's own rows read: `secondary|md` and `destructive|md` both `hover: none` — no story anywhere
  depicted either. Both now have their own frame: `secondary|md`'s row reads `Button:SecondaryHover`
  directly, `destructive|md`'s reads `Button:DestructiveHover`. `secondary|lg` never belonged beside
  them and still does not: its own row reads `hover: ReplayAvailabilityList:Hover`, exactly F1's own
  "elsewhere" pointer — real, just not an _own_ story of `secondary|lg` (the region carries no
  separate "own story" column to distinguish that with; F1, F2 and F6 still name this same
  `ReplayAvailabilityList:Hover` cell as coverage elsewhere, never as a gap — F4 and F7, the other
  two findings this root cause carried, are closed on their own terms above, F4 because its own
  subject was `secondary|md` itself and F7 because its own story text is fixed, neither because
  `secondary|lg` changed). `ghost/md`'s own hover **is** covered, and was already before this
  task's own trio — `ghost|md`'s row read `FavouriteToggle:Hover` directly: the generator
  substitutes `FavouriteToggle.stories.tsx`'s own `args: { favourited: false, authenticated: true }`
  into `FavouriteToggle`'s guard tree (`if (!authenticated) return <SignedOutControl />`), which
  resolves `!authenticated` to `false` and excludes `SignedOutControl`'s own `Button/ghost`
  (guarded the opposite way) from the candidate pool — the one non-hidden `Button/ghost` left is the
  real control this story renders, unambiguous, `size="md"` by the component's own default. This
  task's own `GhostHover` (T595, gap (c)) adds `Button`'s own first-party frame alongside it — the
  row now reads `Button:GhostHover; FavouriteToggle:Hover` — for parity with the
  `Hover`/`FocusVisible`/`Active` convention every other variant carries, not because the cell was
  open. `secondary`'s hover elsewhere is still `ReplayAvailabilityList:Hover`, but only at `lg` —
  `secondary/md` (F4's own subject) used to have none anywhere and is closed, above.
  `destructive`'s hover used to have no frame anywhere in the tree at any size; it now has one at
  `md` (`Button:DestructiveHover`) and still has none at `lg` — `destructive/lg` is F14's own
  subject, left open, a different row from the one this finding's own root cause names.
- **F14 (corrected against the generated `Button` matrix).** `primary/md` has a real **rest** frame
  (the generated `Button` matrix's own `primary|md` row cites the count and the call sites —
  `Callout`'s own stories, `Field.stories.tsx:146,276` — not restated here) and a real **focus-visible**
  frame (`Callout:FocusVisible`, attributed to the specific `<Button variant="primary">Try
again</Button>` its own `FocusVisible` story renders, once candidates are narrowed to that story's
  own source-line range — `Callout.stories.tsx` reuses the literal text "Try again" across five
  separate stories) — but **no hover or press frame anywhere**. `ghost/lg` is real by reading
  (`FavouriteToggle`'s own `RealisticProfileHeader`, `size="lg"`) but **does not appear anywhere in
  this matrix at all — corrected in this pass (T594's REJECT on #80, item 2): the prior wording said
  it "folds into `ghost|unresolved`'s rest-only bucket", which overstates what the generator sees.**
  `RealisticProfileHeader` renders `<FavouriteToggle size="lg" />` (`FavouriteToggle.stories.tsx:141`),
  never a `Button` directly — `FavouriteToggle` composes `Button` inside its own `index.tsx`, a
  file this story never touches, so the story produces no `Button` instance for the generator to see
  at all. `ghost|unresolved`'s own `rest` bucket is populated by `FavouriteToggle`'s own source-level
  `Button` instances instead (`index.tsx:115,126,171`, real regardless of which story renders the
  component), unrelated to this specific story; `ghost/lg` remains real only by reading, invisible to
  Record 3 either way. `destructive/lg` has a real **rest** frame
  (`AccountErasurePanel:218`) and a real **focus-visible** frame, now resolved directly: the
  generated `destructive|lg` row's own focus-visible cell reads `Dialog:FocusVisible` (F3) — but no
  hover or press frame anywhere, own or elsewhere, at `lg`. `secondary/lg` remains the one
  fully-covered combination (generated Record 3's own row).
- **F15 (corrected 2026-09-18, remediation of the orchestrator's REJECT on #80).** The prior wording
  cited the generated `Menu` matrix's own `forcedRoles` field — an internal structure the script
  never renders into the README, not something a reader of this file can check. Read directly from
  `Menu.stories.tsx` instead (`grep -n "visualForceState" packages/design-system/src/primitives/Menu/Menu.stories.tsx`):
  every `hover`/`active` `visualForceState` in that file names `role: 'menuitemradio'`; none names
  `role: 'button'`, so `Menu`'s own trigger (`index.tsx:144`) has no hover or press frame of its own
  anywhere in this tree. Focus-visible is not a gap: `EscapeReturnsFocusToTrigger`'s `play()` ends on
  a `toHaveFocus()` assertion against a `getByRole('button')` locator (`state-coverage.test.mjs`'s
  fourth fixture plants exactly this shape), rendered `unresolved: … (play-driven; frame not provable
statically)` in the generated `selection` row rather than credited as covered — real, but not a
  frame this script can vouch for statically (T594's amendment: play-driven focus is never a
  confirmed cover).
- **F16.** `Menu`'s footer-item button (`index.tsx:242`) — same shape, read the same way: no
  `hover`/`active` `visualForceState` names `role: 'menuitem'` for the footer item; `KeyboardNavigation`'s
  own explicit `visualForceState` (`role: 'menuitem', name: 'Link another Steam account'`) covers
  focus-visible, matched directly (a literal `nth`/name resolution, not play-driven).
- **F15/F16, carried to their consumers (citation corrected 2026-09-19 — M2/M3: `ProfileSummary/
index.tsx:426` is the `<Menu` tag's own opening line, in `ProfileSummary`'s own file, never
  `Menu`'s — `Menu`'s own file is only 421 lines long; `triggerLabel="Manage"` sits two lines below
  it, past the `variant="actions"` line between them).** `ThemeControl` composes `Menu`'s
  `selection` variant (`site-header.md`: "a `Menu` (`selection` variant)") and its own
  "`ThemeControl`'s own states … are `Menu`'s, unchanged" is true as a deferral but silently
  inherits F15's trigger gap. `ProfileSummary`'s "Manage" menu (`ProfileSummary/index.tsx:426-428`,
  `triggerLabel="Manage"`) composes `Menu`'s
  **`actions`** variant instead — the generated `Menu` matrix's `actions` row now resolves a
  `Disabled` frame (`Menu:ActionsWithDisabledItem`, item 4 of this remediation) and has **no
  `hover`/`focus-visible`/`active` frame confirmed** — corrected from "no … frame of any kind", and
  corrected again 2026-09-19 (this task): `BoardFlagHoverRevealed`/`BoardFlagKeyboardFocusRevealed`/
  `BoardLongAliasFlagHoverRevealed` each target `role: 'button', name: 'Country:'`, and used to leave
  this row's cell reading `unresolved` because neither of ProfileSummary's own two `Menu` instances
  (the switcher and this "Manage" menu, `index.tsx:299` and `:426`) carries that name literally.
  `resolveNameMatch` now traces the name instead of only failing to place it: `CountryFlag`
  (`ProfileSummary/index.tsx`'s own `<CountryFlag>`, composed directly in its source) itself composes
  `<Tooltip qualifier="Country:">` (`CountryFlag/index.tsx:71`), and `Tooltip`'s own `qualifier`
  prepends the trigger's accessible name (`Tooltip/index.tsx`'s own doc, §8) — one hop from
  `ProfileSummary`'s own source (`findComposedElsewhereNames`), the single documented mechanism this
  tree uses to compose a name across a file boundary. `Tooltip` is not one of the four primitives
  Record 3 tracks at all, so once the name is traced there, neither `Menu` instance can be the
  target: both are positively excluded, and the cell reads a confirmed `none` (T594's amendment still
  holds — this is exactly the positive knowledge it asks for, not a guess past it).
  `profile-summary.md:134,141` do not distinguish the switcher (`selection`, partially covered) from
  the "Manage" menu (`actions`, no state anywhere — now confirmed, not merely unresolved). **Carried
  further, into the
  story file itself (8c-bis):** `ProfileSummary.stories.tsx:496`'s own comment ("The switcher's
  own hover/focus/active are `Menu`'s stories" — corrected in this pass from `:493-495`, which
  pointed at the leading spec-quote lines rather than the sentence itself) and
  `ProfileSummary.stories.tsx:572-573`'s rendered text ("The switcher trigger and its menu items
  carry theirs, per `Menu`" — corrected from the bare `:573` alone, one line short of the quote's
  own start, and given its own full path here since 8e, unlike 8c's table, never omits one) repeat
  the same claim as `profile-summary.md:134` and are
  false for the identical reason (F15: `Menu`'s trigger has no hover frame anywhere) — a comment and
  a rendered sentence defer a state exactly as a spec sentence does, and neither is a `*NotApplicable`
  story.
- **F17 (corrected 2026-09-19, part A; citation corrected 2026-09-19 part B — M2/M3: `:96` is the
  `const focusRing =` declaration itself, never the string; the value is one line down).**
  `Table`'s row link (generated Record 1, `a @
index.tsx:281` row) carries a real ring of its own: `index.tsx:286` passes `focusRing`
  (`index.tsx:97`, `focus-visible:outline-ring focus-visible:outline-offset-ring
focus-visible:outline-focus-ring`), and the generated region's own left-hand class column shows it.
  The `carries no ring of its own` half of the prior wording was false; only the second half is
  true — **no story forces the row link's focus-visible state directly**, so that cell's coverage is
  a confirmed `none` (the link has a real, non-null implied role of `link`, and no `visualForceState`
  in `Table.stories.tsx` names `role: 'link', state: 'focus-visible'`). The scroll region
  (`div[role=region] @ index.tsx:153`) does have a real `FocusVisible` story, resolved in the
  generated region (its name, "Recent matches", comes from a literal `caption` prop the `FocusVisible`
  story's own `render` passes, not from `args`). The row's reserve-then-paint hover/press classes
  live on the `<tr>` (`index.tsx:237`); with part A's own fix to `impliedRoleOf`, the generated
  region used to read that row's hover and active coverage as `unresolved: ancestor of a forced
descendant (a@…/Table/index.tsx:281, hover: RowLinkHover)` (and `active: RowLinkActive`) — the
  hand-written account this finding used to carry (a real hover/mouse-down on the row's own
  descendant link paints the `tr`'s fill too, which the script could not yet attribute to a story
  because nothing there named the `tr` by role) was the generated reason string itself, not prose
  standing in for what the script could not say. **T595 closes exactly this**: `tr` now carries the
  `row` role `INTRINSIC_ROLE` gives every table row, and the same real hover/mouse-down fact this
  finding names is now credited directly rather than merely quoted — the generated region reads
  `RowLinkHover` and `RowLinkActive` on the `tr`'s own hover/active cells, covered, not unresolved
  (`buildElementMatrix`'s own ancestor-cascade credit, gated on `tr` carrying a real class of its own
  for that state and the descendant's match being confirmed rather than ambiguous). `focus-visible`
  on the `tr` has no forced descendant to credit (the row link's own focus-visible is a confirmed
  `none`, not a match or an ambiguity), and no story forces `role: 'row'` directly either, so it
  reads a confirmed `none` — a `tr` genuinely carries no state of its own there, only the
  reserve-then-paint hover/active band above.
- **F18.** `Field`'s own matrix (generated Record 3): `md`'s row has a real `Hover`/`FocusVisible`;
  `lg`'s row (`Field:SizeLg`, rest only) has neither. Matches `structural-tier.md` §11's own sizing
  rule ("to match `Button`'s").
- **F19 (new, 2026-09-18 remediation of the orchestrator's REJECT on #80 — judged at the consumer's
  size, not only its variant; citation corrected 2026-09-19 — M2/M3, corrected again in this pass:
  `FavouritesList/index.tsx:293` is the `<div` tag's own opening line, the wrapper around
  `FavouriteToggle`, never a line in `FavouriteToggle`'s own file — the bullet names
  `FavouriteToggle` first, so a bare `:293` here resolves against the wrong component's `index.tsx`
  (183 lines, nowhere near line 293) under `resolveBareLocationFromBullet`'s own "first-named"
  rule; qualified in full instead, the same way `FavouritesList/index.tsx`'s own `:298` claim below
  already is. The prior M2/M3 correction described this same line as the closed `div` element rather
  than its own opening tag — a closing angle bracket the tag's own opening line never carries on its
  own (its actual text runs the class expression between the tag name and the bracket) — so it
  stayed unverified rather than merely wrong: the inline-claim checker that would have caught either
  shape was itself dropping every bare-location claim unchecked (item 1);
  `size="lg"` sits five lines down, on the `FavouriteToggle`
  instance itself).** `packages/design-system/specs/favourites-list.md:110-111`
  (**corrected in the row-8 audit that followed this finding: the prior citation, `:113-114`, pointed
  one clause too late**) — "`RemoveControl`: `FavouriteToggle`'s own hover/focus" — and `:126`'s
  active claim are both false at the size this
  consumer actually renders. `FavouritesList/index.tsx:298` gives `RemoveControl` (`FavouriteToggle`)
  `size="lg"`, but `FavouriteToggle.stories.tsx`'s own `Hover`/`FocusVisible`/`Active`
  (`:107-119`) supply no `size` arg at all, resolving to `FavouriteToggle`'s own default —
  the generated `Button` matrix's `ghost|lg` row (corrected in this pass: composed through
  `Button.stories.tsx`'s own `RealisticPageActions`, not `FavouriteToggle` — `FavouriteToggle`'s own
  `lg` instance, `RealisticProfileHeader`, carries no `visualForceState` at all **and renders
  `<FavouriteToggle size="lg" />` rather than a `<Button>` directly, so it produces no `Button`
  instance and appears in no row of this matrix at all — corrected in this pass from "folds into the
  separate `ghost|unresolved` rest-only bucket instead", F14's own defect, item 2 of the same
  REJECT**) reads `hover: none`, `focus-visible: none`, `active: none`; every one of those three
  states has a frame only at `ghost|md`. The deferral is real in kind (the states are `Button`'s own
  paint) and false in size (no frame proves it at `lg`).
- **F20 (new, 2026-09-18 remediation, same size-grain judgment; citation corrected 2026-09-19 — B2;
  closed 2026-09-19, T595).** `AccountErasurePanel.stories.tsx`'s own `HoverFocusActiveNotApplicable`
  used to claim, in both its comment and its rendered text, that the dialog's `destructive` action
  had its focus-visible and press covered by `Button.stories.tsx`'s per-variant `DestructiveFocusVisible`/
  `DestructiveActive` stories. `index.tsx:218-220` renders the button `destructive`/`size="lg"`;
  `AccountErasurePanel/index.tsx:224` "Erase my account" is the button's own accessible name. The
  generated `Button` matrix's `destructive|lg` row reads `hover: none`, `focus-visible:
Dialog:FocusVisible` (real, composed through `Dialog`'s own `destructive`/`lg` confirm action), `active: none`
  — `DestructiveActive` itself resolves to `destructive|md` (no `size` in its own args), never `lg`.
  The press half of the old claim was false at this component's actual size; the focus-visible half
  was true, by a different route than the one named. **Fixed, not merely re-attributed**: the story's
  comment and rendered text now state the real routes directly — `destructive|lg`'s focus-visible is
  `Dialog:FocusVisible`, its hover and press have no frame anywhere at `lg` (F14, left open — a
  different row from what T595's own Button hover trio closed, `secondary|md`/`destructive|md`),
  and `secondary|lg` (`Dialog`'s own secondary action) is covered by `ReplayAvailabilityList`/
  `UploadControl`, never `Button`'s own per-variant stories — see the 8c-bis table's own
  `AccountErasurePanel` row above for the current citations.

**Cell counts are printed by the script, never written into this prose — T594's own rule, breached
by every triple this paragraph used to carry** (each of six historical counts here was wrong, three
of them arithmetically impossible against the region's own real cell count; deleted below rather
than corrected, since none is mechanically re-derivable from a commit already several edits behind
the live tree). `node scripts/checks/state-coverage.mjs` prints both records' own tallies on every
run, current against the live tree, classified once (`classifyCoverage`/`classifyClassHalf`, that
file's own source) —
**as the value each cell actually renders, never re-merged**: `none` only for the literal `none`,
`unresolved` for any `unresolved: <reason>` whatever the reason, `covered` otherwise. **Record 1's
own cell renders two halves, `class → story`** (`el.hover`/`el.focus`/`el.focusVisible`/`el.active`,
resolved through the same file's own `const`s and `cx()`/`clsx()` calls, on the left; `el.coveredBy`
on the right) **and both are checked, not the right half alone** — `reviewer`'s fourth REJECT on
PR #80 found `countRecord1Cells` reading only `el.coveredBy`, so eight cells whose own left half
rendered `unresolved: className not fully resolved` (the class expression itself never resolved)
were still counted by whatever their right half said — some `none`, some `covered`, neither a
reading this pass actually has (the split and the corrected totals are the script's own printed
line, cited above rather than restated here, exactly this paragraph's own rule). A cell whose class
half is `unresolved` is now an `unresolved` cell regardless of its story half; Record 3 carries no
such second column and was unaffected by this pass. An earlier
version of this tally folded every non-`play-driven` `unresolved` into `none`, on the reasoning
that both state "no proof of any frame for this state" — the orchestrator rejected that directly:
`none` is a confirmed absence, a gap T595 must close; `unresolved` is this script declining to
decide, and no finding may claim a gap from an `unresolved` cell alone (the audit paragraph below
says what a finding that keeps one must state), the distinction row 8's own
Method section exists to defend. This tally does not get to erase it again for its own convenience.
Record 1 counts one cell per state, hover/focus-visible/active only, per local interactive element
(three states each); Record 3 counts one cell per state, all five of
`rest`/hover/focus-visible/press/disabled, per real primitive-matrix row — the `(no local
interactive element)` placeholder and the `(unresolved matches — no row…)` information row excluded
from both records' own row counts, and the script's own printed line names both the axes and the
row unit so this convention need not be inferred from the two numbers alone. **Cite the script's
own two lines rather than a number typed here** — this paragraph does not restate them, on purpose,
so the next commit cannot leave a stale count behind the way this one's predecessor did.

Every `→ unresolved: …` coverage cell the prior hand-back listed now resolves: `Dialog`'s
`FocusVisible` (nested-object args: `args.primaryAction.label` matched, `primaryAction.variant ??
'destructive'` evaluated), `FavouriteToggle`'s `Hover`/`FocusVisible`/`Active` (conditional-branch
reachability: `args.authenticated: true` excludes `SignedOutControl`'s own `Button`, the one
candidate a literal boolean arg does not rule out), `FavouritesList`'s own force-states (a
`selector`-targeted `visualForceState` was being treated as a role wildcard against every `Button`
in the file — fixed directly, not by resolving an argument) and `Menu`'s footer item
(`footerItem: { label: 'Link another Steam account' }`, a nested-object arg, the sole candidate for
`role: 'menuitem'` once `Menu`'s own item — a genuinely dynamic `role={…}` — is correctly excluded
from that role's candidate pool rather than wrongly pooled under its tag's intrinsic role). Two
`axisKey` labels still read `unresolved` in their own row key (`ghost|unresolved`,
`unresolved|lg` in the generated `Button` matrix) — real call sites whose `size`/`variant`
genuinely pass through a dynamic prop no story's own literal args resolve, never a coverage gap in
themselves. **Corrected in this pass (T594's REJECT on #80, item 2): the closing clause here used
to claim that none of either row's own occurrences carries a force-state to resolve against at
all — false of both.** `FavouriteToggle`'s real button (`index.tsx:126`, the one non-hidden `ghost`
`Button`) is exactly the candidate `FavouriteToggle:Hover`/`FocusVisible`/`Active` resolve against
(F13); `Dialog`'s own two `Button` instances (`index.tsx:127`, `:138`) are exactly what
`Dialog:FocusVisible` resolves against (F3). Both rows' own occurrences do carry a force-state; what
stays genuinely unresolved is the _row itself_ — a JSX candidate's own static axis (dynamic
`size`/`variant`, no literal to key a shared row on) and the axis its own force-state resolves to
_per story_ disagree, so the same source line's own `rest` entry and its own resolved state used to
land on two different rows, the second confirming `none` on the first over a comparison that
actually found a match. `buildAxisMatrix` used to point each of these rows' own state cells at
wherever that resolution actually landed instead (`unresolved: axis resolved only per story (→
ghost|md)`, `(→ destructive|lg)`), rather than leaving them read a `none` the pass never actually
established. **Superseded 2026-09-19 (T595), twice in the same day.** The first correction read the
target row's own cell directly and credited this row's cell with that same match rather than the
pointer — a description already superseded by the second, an orchestrator finding on this same
task's own hand-back: reading the target row's _whole_ cell rather than the specific label a story
proved was correct only by accident (every target this description's own two rows reached happened
to carry exactly one contributor), and `disabled` broke that accident immediately once the redirect
was made to reach it at all — `unresolved|lg`'s own two call sites share `secondary|lg` with two
wholly unrelated Button call sites in other components, and a whole-row read would have credited
`unresolved|lg` with stories that prove nothing about either of `Dialog`'s own buttons. `cellFor`
now credits the exact label `storyResolvedBySourceLine` proved for that line and state, never a row
lookup, and that map is fed by `disabled`'s own confirmed matches too, not only the three states
`composed-story` covers — `ghost|unresolved`'s hover/focus-visible/active/disabled and
`unresolved|lg`'s focus-visible/disabled all read real story names today (the generated region
above, cited there rather than restated here), and the pointer note itself is gone: fed exclusively
by confirmed matches, the map never has a target with nothing to show. Row 8's own Method section
states the current mechanism, both corrections, and the decision behind it in full.
`RealisticProfileHeader` itself — `FavouriteToggle`'s own `lg` story, carrying no `visualForceState`
at all — is unrelated to this shape: it renders `<FavouriteToggle size="lg" />`, never a `<Button>`
directly, so it produces no `Button` instance and is invisible to this matrix altogether (F14/F19
below, corrected the same way).

**Six cells moved again in `8e3006e9` ("an element with no implied role is unresolved, not
none"), read against its own diff rather than assumed from its title**: `Dialog`'s `h2`
(`index.tsx:102`), `Menu`'s footer item (the dynamic-`role` one, `index.tsx:352` — the item at
`:242` did not move, its own role is a literal `menuitem`), `Table`'s `tr` (`index.tsx:237`) and
`AccountErasurePanel`'s `label` (`index.tsx:269`) each moved from a confirmed `none` to
`unresolved: no implied role` (`Table`'s `tr`'s own hover/active cells, specifically, to
`unresolved: ancestor of a forced descendant` instead) — a tag `INTRINSIC_ROLE` does not carry, or
a dynamic `role={…}`, was being credited with a checked absence this pass never ran. A fifth,
`PrivacyNotice`'s `InlineLink` (`index.tsx:242`), moved the same direction for an unrelated reason
the same commit also fixed (`resolveNameMatch`'s `nth` branch: an unorderable helper's own render
position is unknown, so a bare `nth` against it is now ambiguous rather than silently accepted) —
its three cells now read `unresolved: … 4 candidates share role "link", nth 0 not orderable`. A
sixth, `PrivacyNotice`'s `SectionHeading` (`index.tsx:264`), is the same `h2` with a negative
`tabIndex` shape as `Dialog`'s and moved the same way. **`SiteHeader`'s skip link did not move its own coverage cell**
— it read `none → none` on every state before this commit and reads it still; what changed is its
own **class** column, which now shows the `focus:` (plain, not `focus-visible:`) utilities it
paints alongside `focus-visible:`'s, previously invisible to Record 1 entirely (the commit's own
last paragraph). Naming it among "cells that moved" in the task that asked for this section
conflates the two columns; F9a's own claim rests on the coverage column, untouched.

Every finding resting on one of the five cells that did move is re-read against the generated
region as it now stands, not as it stood when the finding was first filed: F10, F10a, F12 and F17
each name one, and each is re-checked here — a finding is **not** automatically still a gap only
because its cell used to read `none`; `unresolved` is a different fact (no proof either way, not a
confirmed absence), and a finding that only ever claimed "no story proves this state" reads the
same under either word. None of the four turns out to overturn its own finding, but **an `unresolved`
cell is never itself the evidence**: where a finding keeps its gap over one, the finding states the
check by hand that establishes it. F10a (`PrivacyNotice`'s `SectionHeading`) and F10
(`PrivacyNotice`'s `InlineLink`) both did, in their own bullets — **as of this paragraph's own
writing**; F10 is since closed in full by T595's own story work, F10a still open and still owed a
frame (see each finding's own bullet above for the current state, not this historical paragraph).
F12
(`AccountErasurePanel`'s checkbox) rests on `index.tsx:270`, the checkbox itself, never `:269`'s
`label` — a different element in the same pair, untouched by this commit. F17 (`Table`'s row link
and its `tr`) already narrates the `tr`'s own ancestor-of-a-forced-descendant reason as its own
finding, quoted from the generated region — this commit made the generated text match what F17
already said (part A of F17 predates this commit and reasoned about the same shape by hand; this
commit is what let the region say it directly). F11 (`ArchivalControl`'s privacy link) and F20
(`AccountErasurePanel`'s `destructive|lg` press) name neither of the five cells at all — F11 rests
on the element painting **zero state classes of any kind**, and F20 on `DestructiveActive`
resolving to `destructive|md` — both untouched. `Dialog`'s `h2` and `Menu`'s footer item carry no
finding of their own (neither is the subject of F1–F20) — moving them is why the region's own
generated table changed shape, not why a claim above it did.

**Owners: T594 (this sweep — the generated region, 8c's full 29-file tally, 8c-bis's
eighteen-component story tally and its own vocabulary sweep, 8d, F1-F20 and the F15/F16 consumer
findings). T595 closes the enumerated set (F11 and the contact-route half of F10 are both T596's and wait on a design
decision, T596). Fix by 2026-09-27.**

Also recorded, not registered here because it is a two-minute fix rather than an open gap, and
**corrected in this pass rather than carried over stale (item 7 of `reviewer`'s sixth REJECT on
PR #80: widening `extractCitationScope` past the old `**Cell counts` boundary brought this closing
paragraph inside the checked region for the first time, and its own claim no longer held; corrected
again in the row 8 sweep's own item 3 — both line ranges below were still wrong, and the prose was
still bare "lines 47-60" text rather than the citation form the parser recognises, so neither escape
was caught the first time)**: the rename this paragraph used to announce — the `Link` primitive's
own `RestAndHover` story becoming `Rest`, because its comment claimed a real `:hover` capture the
story's own missing `visualForceState` never drove — had already landed by the time of this pass.
`Link.stories.tsx:45-52` "export const StandaloneExternal" now names an unrelated story (line 53 is
blank, and 54-60 is `Rest`'s own leading comment); `Rest` itself sits at `Link.stories.tsx:61-70`
"export const Rest".
