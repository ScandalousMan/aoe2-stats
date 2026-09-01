# SiteHeader

**Component**: `src/components/SiteHeader/` (T441)
**Feature**: 004, US3 — mounted in the web shell by T442, in `apps/web/src/routes/__root.tsx`,
beside the `Footer` that is already mounted there, so it renders on every route.
**Requirements**: FR-009 (a header with primary navigation on every page, footer intact), FR-013
(tokens only, a story, visual regression). Constitution VI, VII.
**Depends on**: [`README.md`](./README.md) — the measured contrast table and the gap register, which
this spec references and never restates. [`footer.md`](./footer.md) — the other half of the site
chrome; the two are specified to agree on inline padding, on link behaviour and on "chrome is the
quietest thing on the page". `src/lib/rowLink.ts` — the existing SPA navigation seam
(`createRowLinkClickHandler`), reused rather than re-invented.
**Asset origin** (README rule 3): **none.** This component renders no image of any kind — no logo,
no crest, no emblem, no civilisation mark, no flag. The brand is a text wordmark set in the
`display` family. There is nothing here for the licence gate to record, and §10 has a criterion
that keeps it that way.

**Why this is a design-system component and not markup in `apps/web`.** The same reasoning
`footer.md` states about the disclaimer, for the same structural reason: constitution VI admits no
unstoried component, and chrome that exists only inside a route file is chrome no visual review
ever looks at. The header is also the one element on the page whose keyboard behaviour every route
inherits — a focus ring that stops painting here stops painting on every page at once. It gets a
story so it gets a baseline.

## 1. Purpose

Give a visitor, on every page, the short list of places this product can take them, and show which
of those places they are currently in — so the application reads as a site rather than as whichever
single view they happened to land on.

## 2. Anatomy

```
SiteHeader                     <header>, the banner landmark
├─ SkipLink                    "Skip to content" — the first focusable element on every page;
│                              visually hidden until it takes focus, then a real, visible control
├─ Brand                       <a href="/"> — the wordmark "aoe2-stats", text, never an image
└─ PrimaryNav        ×0..1     <nav aria-label="Primary">, omitted entirely when there are no items
   └─ NavList                  <ul>
      └─ NavItem    ×1..n      <li><a href> — label, plus the current-route marker (§4)
```

`SkipLink` and `Brand` are never conditional. `PrimaryNav` is present only when the caller supplies
at least one item (§5 empty), which is the signed-out case and not a fault.

### 2a. Props

```ts
export interface SiteHeaderNavItem {
  /** Stable key. Never rendered. */
  id: string
  /** The visible label. Real text, always — there is no icon-only nav item (§9). */
  label: string
  /** Destination path, e.g. `/matches`. Also what `currentPath` is matched against (§4). */
  href: string
}

export interface SiteHeaderProps {
  /** The primary destinations, in the order they are shown. **Required, and `[]` is a legitimate
   * value** — the signed-out call site passes it deliberately (§5 empty). Not optional, so a
   * caller that forgot the prop fails to compile rather than shipping a header with no way out. */
  items: readonly SiteHeaderNavItem[]
  /** The current pathname, e.g. `/matches/12345`. Absent → no item is marked current (§4). */
  currentPath?: string
  /** Where the wordmark links. Defaults to `/`. */
  brandHref?: string
  /** Target of `SkipLink`. Defaults to `#main-content`; see §9's call-site obligation. */
  skipToContentHref?: string
  /** SPA navigation seam, exactly as `PlayerResultRow` and `MatchRow` already take it. */
  onNavigate?: (href: string) => void
  className?: string
}
```

The wordmark's text is **not** a prop, for `footer.md` §3's reason: a caller that could override it
could also break it.

### 2b. Who owns navigation

Every destination is a real `<a href>`, so it works with no JavaScript, is reachable by keyboard,
and supports every native anchor gesture — open in a new tab, copy link address, middle-click. This
package knows nothing about the application's router, so a plain left click is intercepted through
`createRowLinkClickHandler` (`src/lib/rowLink.ts`) into the caller's `onNavigate`, and every
modified or non-primary click is left to the browser. This is the seam `PlayerResultRow` and
`MatchRow` already use; the header introduces no second mechanism.

### 2c. What this component is not, in 004

Stated so that three plausible additions do not arrive as call-site improvisations:

- **No account or session control**, no avatar, no signed-in identity, no sign-out. Its place is
  reserved — the inline-end of the brand row — and it is a spec change when it is wanted, not a
  prop a container may add. FR-009 asks for navigation.
- **No search field in the header.** `SearchBox` is a composite with its own results surface and
  its own focus behaviour; `/search` is a destination in the nav instead. A second search entry
  point would make two components own the same keyboard interaction.
- **No breadcrumb, no page title, no route-level actions.** Those belong to the route's own
  `<main>`, which already renders them; a header that restates the page title costs a line of
  vertical space on every page in a tool whose functional priority is density (README rule 1).

## 3. Variants and sizes

**One variant and one size, at every viewport.** A header that changes shape per route is chrome a
reader cannot rely on finding twice, and the whole value of this component is that it is identical
everywhere. What changes between routes is which item is marked current (§4), and what changes with
the viewport is arrangement, never composition (§8).

### 3a. The canonical item set for 004

The component takes whatever items it is given; this is what `apps/web` gives it (T442), fixed here
so the site's primary navigation is one decision rather than one per container:

| Order | Label        | `href`        | Why it is primary                                                          |
| ----- | ------------ | ------------- | -------------------------------------------------------------------------- |
| 1     | `Dashboard`  | `/dashboard`  | Where sign-in lands; the linked profile and the archival control live here |
| 2     | `Matches`    | `/matches`    | The viewer's own match history — US1's whole surface                       |
| 3     | `Search`     | `/search`     | The only way to reach another player                                       |
| 4     | `Favourites` | `/favourites` | Reachable today from nowhere at all                                        |
| 5     | `My data`    | `/privacy`    | Export and erasure; reachable today only from the privacy notice           |

Three of these five routes exist with no in-application entry point whatsoever, which is the
concrete hole US3 closes. **`My data` is deliberately not "Privacy"**: the footer already carries
"Read the privacy notice", and two chrome links reading the same word for two different pages — a
public notice and this account's own data — is a worse outcome than a slightly blunt label.

**Signed out, the caller passes `[]`.** Every one of the five routes redirects an unauthenticated
visitor to `/sign-in`, so rendering them would be five links that all go to the same place; a
navigation that lies about where it leads is worse than no navigation. The way forward is still
present: the wordmark links to `/`, which forwards a signed-out visitor to `/sign-in` and a signed-in
one to `/dashboard`.

## 4. Current-route indication

**The state a navigation exists to show.** It is carried three ways at once, because the README's
rule 4 forbids colour being the only carrier and because `aria-current` is invisible:

1. **A 2px rule in `accent`** across the item's inline width, in the `space-1` channel beneath the
   item's box (§7). **Every item reserves that channel**, so marking one current shifts nothing.
2. **The label's weight and colour** — `semibold` and `text-primary`, against `medium` and
   `text-secondary` at rest. This is the signal that survives a greyscale render.
3. **`aria-current="page"`** on that item's `<a>`, and on no other.

The rule sits in the channel rather than inside the item's box for a contrast reason worth
recording: the box's fill changes under hover and active (§5), and `accent` is measured against
`surface` in both themes but against neither `surface-sunken` nor `surface-raised`. Keeping the rule
on the header's own `surface` means the indicator carries the same, measured pair in every state it
can be in.

**Which item is current** is decided by a pure string rule, not by a router this package does not
depend on:

- `currentPath` equals `item.href` → current.
- `currentPath` starts with `item.href + '/'` → current. This is what makes `/matches/12345` mark
  **Matches**, which is the case an exact-match-only rule silently gets wrong.
- If two items match, the **longer** `href` wins. None of §3a's five is a prefix of another, so this
  never fires today; it is stated so an implementation does not pick arbitrarily when one is added.
- An `href` of exactly `/` matches exactly, never by prefix — otherwise it is current on every page.
- `currentPath` absent, or matching nothing → **no item is current** (§5 empty, second case).

## 5. States

The closed vocabulary, all eight. Unless said otherwise, a state belongs to a `NavItem`; `Brand` and
`SkipLink` are called out where they differ.

- **default** — header on `surface` with a `border` hairline at its block-end. Items at rest:
  transparent box, label `text-secondary`, `sans`, size `sm`, weight `medium`, no underline. The
  current item as §4 describes. `Brand`: `display` family, `text-primary`, no underline.
- **hover** — the item's box fills `surface-sunken` and its label moves to `text-primary`; the
  `radius-md` box is the shape that lights up, matching `Button`'s and `Menu`'s existing hover
  convention rather than inventing a nav-only one. **No underline on hover**, deliberately: an
  underline here would read as a second current-route marker. The current item hovers identically —
  fill and label change, its `accent` rule is untouched, so hovering never makes a page look like
  the one you are on. `Brand` on hover takes an **underline** and keeps its colour (no
  `accent`-on-`surface` pair is introduced where a shape signal does the same job).
  `motion.duration.fast` with `easing.standard`, colour only — no lift, no scale, no translate.
  Under `prefers-reduced-motion: reduce`, `motion.duration.instant`.
- **focus-visible** — **named explicitly, because this is the state a later reviewer will assume was
  covered.** Every focusable part of this component — `SkipLink`, `Brand`, and every `NavItem` —
  shows the one documented ring: `outline-2 outline-offset-2` in `focus-ring` (gap DS-4), drawn
  outside the item's box, on top of whatever the hover state is, never replaced by a fill change and
  never suppressed on click. Three consequences that are part of the spec, not of the
  implementation:
  - The ring is **never clipped**. The header's block padding (`space-2`) and the gap between items
    (`space-2`) exist to leave room for a 2px ring at a 2px offset; that is why neither may go to
    zero, at any viewport, including the wrapped small-viewport rows.
  - The offset is **outward** (`outline-offset-2`), not the inset variant `MatchRow` and
    `PlayerResultRow` use. Those are full-bleed rows whose ring would otherwise leave the viewport;
    a header item is an inline box with space around it.
  - `outline-none` at rest must not swallow the ring. This exact defect shipped once already across
    every primitive in this package (`tests/visual/focus-ring.spec.ts`); §11 is why it cannot ship
    here quietly.
- **active** — fill `surface-sunken` with a 1px `border-strong` boundary drawn **inside** the box
  (reserved as a transparent boundary at rest, so the label never shifts by a pixel), label
  `text-primary`. This is `Button`'s non-primary active treatment, unchanged, so rest, hover and
  active are three distinguishable frames.
- **disabled** — **never, for any part.** A destination either exists and is a link, or it is not in
  `items`. There is no dimmed, unusable, "coming soon" entry: a greyed nav item is a dead end that
  invites a click it will not honour, and `footer.md` §5 settled the same question the same way for
  the same reason.
- **loading** — none, and specifically **no skeleton row**. `__root.tsx` resolves the session in
  `beforeLoad` before `RootLayout` paints, so the item set is known at first paint; chrome that
  arrives a moment after the page shifts the content beneath it and reads as a fault. If a caller
  ever does not yet know its items, the correct render is the empty state below, not a placeholder
  bar (`Skeleton`'s own "never render before 200 ms" rule points the same way).
- **error** — none of its own. This component makes no request and awaits nothing. A failed session
  is `__root.tsx`'s `RootError`, a different tree entirely. An item whose `label` or `href` is blank
  is a call-site defect, and the component **omits that item** rather than rendering a dead link —
  the same choice `Footer` makes for an absent href.
- **empty** — two distinct emptinesses, and conflating them is the design bug this section exists to
  prevent:
  - **`items` is empty** (the signed-out visitor): `PrimaryNav` is **not rendered at all** — no
    `<nav>`, no empty `<ul>`, no reserved strip of blank space where five links would have been. The
    header is the wordmark and the skip link, and it looks like a header that has one thing in it
    rather than one that lost four.
  - **No item is current** (`/players/1807091`, `/matches/12345/…`, `/privacy-notice`, `/object`,
    `/sign-in`): every item renders at rest, **none** carries the rule and none carries
    `aria-current`. Not "the first one", not "Dashboard by default". A header that claims you are on
    a page you are not on is worse than one that claims nothing, and this is a routine state, not an
    edge case — the profile and match-detail routes are in it all day.

## 6. Tokens used

Colour: `surface` (the header's own fill), `border` (the block-end hairline — the README's own
"decorative separators only" rule for that token is exactly this use), `text-secondary` (item labels
at rest), `text-primary` (the current item, any hovered or active item, and the wordmark), `accent`
(the current-route rule, §4), `surface-sunken` (hover and active fill), `border-strong` (the active
boundary, and `SkipLink`'s boundary when it is visible), `surface-raised` (`SkipLink`'s fill),
`focus-ring` (the one ring).

**Why the fill is `surface` and not `background`.** `footer.md` puts the footer on `background`, and
symmetry would argue for the same here. The contrast table decides against it: every pair this
component draws — `text-primary`, `text-secondary`, `accent`, `border-strong`, `focus-ring` — is
measured against `surface` in **both** themes, while `background` carries no dark-theme
`text-secondary` row at all (README's own standing note, raised by `profile-summary.md`). Choosing
`surface` introduces no unmeasured pair, and it gives the chrome a quiet lift above the `bg-background`
`<main>` every route renders, so the header reads as a boundary rather than as part of the page.

Font: family `sans` for every nav item and the skip link; `display` for the wordmark only — the one
place in the chrome where the illuminated face earns its keep, because it sits beside no number
(README rule 1). Sizes: `lg` wordmark, `sm` item labels and skip link. Weights: `semibold` wordmark
and current item, `medium` item at rest, `normal` skip link. Tracking `tight` on the wordmark only.

Radius: `md` on the item box and on `SkipLink`. Elevation: **`none`** — chrome sits flush with the
page and does not float above it; there is no scroll shadow, because there is no scroll behaviour
(§8).

Motion: `duration.fast` + `easing.standard` on the item's fill and label colour, and nothing else in
this component moves. `duration.instant` under `prefers-reduced-motion: reduce`.

Gaps in play: **DS-4** — the ring is Tailwind's `outline-2 outline-offset-2` with
`outline-focus-ring`, the register's sanctioned interim, uniform across all three focusable parts.
**DS-5** — breakpoints are named as Tailwind's defaults (`md` = 768px). **DS-6** — the header is
full-bleed with inline padding, so it needs no container width token.

One pair this component draws that the README's table does not yet carry: `text-primary` on
`surface-sunken` in the **dark** theme (the hovered item's label). Dark `surface-sunken` is darker
than dark `surface`, so a light ink on it is no tighter than the measured 13.3 `surface` row and
nothing is blocked — but per the README's pairing convention an unmeasured pair is not an asserted
one, and the light row (11.7) is measured. Add the dark row the next time the table is recomputed,
alongside the one `profile-summary.md` §12.8 already owes.

## 7. Spacing

| Between                                 | Step                                                                                                       |
| --------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Header padding-inline                   | `space-4`, `space-6` from `md` — identical to `Footer` and to every route's `<main>`                       |
| Header padding-block                    | `space-2` (also the focus ring's clearance, §5)                                                            |
| `Brand` to `PrimaryNav`                 | `space-6` from `md`; `space-3` block gap when stacked at 375                                               |
| Between `NavItem`s                      | `space-2`                                                                                                  |
| `NavItem` padding-inline                | `space-3`                                                                                                  |
| `NavItem` box min-height                | `space-12` — 48px, clearing the 44px touch floor at every viewport, the same height `Menu` gives its items |
| `NavItem` box to the current-route rule | `space-1` (the reserved channel, §4)                                                                       |

No value outside the scale, and no per-viewport spacing change other than the inline padding step
above.

## 8. Responsive

- **375** — two rows: `Brand` alone on the first, `PrimaryNav` beneath it, its items **wrapping**
  onto as many rows as they need at `space-2` apart. Every item stays at least 48px tall, every
  label stays fully readable, and nothing is hidden.
  - **No hamburger, and this is a decision, not an omission.** Hiding five short links behind a
    disclosure costs an extra tap on every navigation in a product people consult quickly (README
    rule 1), and it introduces an overlay surface with focus trapping, an open/closed state and a
    keyboard contract — an entire second component's worth of behaviour that no screenshot can see.
    Five wrapped links cost two rows of chrome and behave identically on every device.
  - **No horizontal scroller either.** A row that scrolls sideways hides items with no affordance,
    and an item a keyboard user tabs to off-screen is a focus ring nobody can see.
- **768** — one row: `Brand` at the inline-start, `PrimaryNav` immediately after it at `space-6`,
  both left-aligned. The inline-end stays empty; that is the space §2c reserves.
- **1280** — identical to 768. The header is full-bleed at every width and never becomes a centred
  column, a two-tier bar or a grid.
- **Not sticky.** It scrolls away with the page in every arrangement. Two reasons: a fixed bar over
  a dense match table costs rows on exactly the viewport that has fewest, and a sticky header
  overlays the content a skip link just moved focus to. If it is ever made sticky, that is a spec
  change with a scroll-shadow decision attached, not a class a container adds.
- At 200% zoom the arrangement degrades the same way the 375 arrangement does — items wrap, nothing
  truncates, no horizontal scrollbar appears.

## 9. Accessibility

- Root is `<header>` at the top level of the document, so the **banner** landmark is implicit; it is
  the first landmark in the page, before `<main>` and before the footer's `contentinfo`.
- `PrimaryNav` is `<nav aria-label="Primary">` — labelled, because a page may hold more than one
  navigation region and "navigation" alone tells a screen-reader user nothing about which.
- Items are a real `<ul>`/`<li>` list of real `<a href>` elements, so the region announces its
  length and a screen reader's link list is meaningful.
- **`aria-current="page"`** on the current item and no other. The attribute is present or absent —
  never `aria-current="false"` on the rest.
- **Keyboard**: Tab moves through `SkipLink`, `Brand`, then every item in DOM order, which is also
  visual order at every viewport; Enter activates; Shift+Tab reverses. **There is deliberately no
  arrow-key roving-tabindex behaviour**: this is a list of links, not a menubar widget, and turning
  it into one would remove every item but one from the tab sequence and break the link-list
  navigation screen-reader users actually rely on. `Menu`'s arrow-key contract belongs to `Menu`.
- **`SkipLink` is a WCAG 2.4.1 bypass block, and it is the reason the header can grow links at all.**
  It is the first focusable element on every page, visually hidden until focused (clipped, never
  `display: none`, which would remove it from the tab order), and fully visible with the standard
  ring when focused. Its default target is `#main-content`. **Call-site obligation (T442)**: the
  route shell renders `<main id="main-content" tabIndex={-1}>` so focus actually lands there; a skip
  link that scrolls but does not move focus is the failure this control is famous for.
- **Touch targets**: every item's box is `space-12` (48px) tall at every viewport, clearing WCAG
  2.5.8's 44px floor. `SkipLink` and `Brand` clear it by their own padding-block.
- **Contrast**: `text-secondary` on `surface` (6.2 light / 7.8 dark), `text-primary` on `surface`
  (15.3 / 13.3), `accent` on `surface` (4.9 / 7.7 — the current-route rule owes only the 3:1
  non-text floor and clears the text floor anyway), `border-strong` on `surface` (3.5 / 3.8),
  `focus-ring` on `surface` (6.7 / 6.3). All measured, both themes, README table. The one unmeasured
  pair is named in §6.
- Colour is never the only carrier: the current item is also `semibold`, also underscored by a rule,
  and also `aria-current`. In greyscale the current item is still identifiable.
- Reading order equals visual order equals DOM order, in both arrangements, including the wrapped
  rows at 375.
- Every label is real, selectable text. No icon-only item, no tooltip, no `title` attribute
  carrying information the label does not.

## 10. Visual acceptance criteria

Stories live under **`Chrome/SiteHeader`** (the id quickstart scenario 6 names). `Footer` stays at
`Composite/Footer`; moving it would recapture every footer baseline for no functional gain, and the
inconsistency is recorded here rather than resolved silently. Every criterion below is judged in
**both themes**; the small-viewport stories carry the `visual-mobile` tag, without which the whole
of §8's 375 arrangement is invisible to the suite (`scripts/visual/run.mjs`).

Required stories: `SignedIn` (five items, `/dashboard` current), `CurrentIsNestedRoute`
(`currentPath` `/matches/12345`), `NoCurrentItem` (`currentPath` `/players/1807091`), `SignedOut`
(`items={[]}`), `SmallViewport` (`visual-mobile`), `LongLabels` (the longest plausible item set, at
375, `visual-mobile`).

- [ ] The wordmark "aoe2-stats" is present in every story, as text.
- [ ] **No image of any kind appears in any frame** — no logo, crest, emblem, shield, civilisation
      mark or flag. The header renders text and rules only (README rule 3, constitution X).
- [ ] `SignedIn`: exactly **one** item carries the current-route rule, and it is the one whose label
      is also the heavier weight. Counting rules in the frame gives 1, never 0 and never 2.
- [ ] `CurrentIsNestedRoute`: the marked item is **Matches** — a nested route still marks its
      section.
- [ ] `NoCurrentItem`: **no** rule appears under any item and no label is heavier than another. This
      story is the one that fails if an implementation defaults to marking the first item.
- [ ] Rendered in greyscale, the current item in `SignedIn` is still identifiable — the rule and the
      weight carry it without hue.
- [ ] The current-route rule sits fully below its item, is not clipped by the header's block-end
      hairline, and is the same width as the item above it.
- [ ] Overlaying `SignedIn` on `NoCurrentItem`: every label sits at the identical position. Marking
      an item current moves nothing (the reserved channel, §4).
- [ ] `SignedOut`: the wordmark alone, with **no** `<nav>` region, no empty strip, no gap and no
      dimmed items where the five links would be. The frame does not read as a header that failed to
      load.
- [ ] The skip link is **not visible** in any resting screenshot, and no blank row is reserved for
      it.
- [ ] The header's block-end hairline is visible against the page beneath it in both themes, and the
      header's fill is distinguishable from the `<main>` below it.
- [ ] At 375 (`SmallViewport`, `LongLabels`): the items **wrap onto further rows**; no horizontal
      scrollbar, no clipped item, no ellipsis, no label truncated mid-word.
- [ ] At 375, every item's box measures at least 44px tall (48px as specified) and items are at
      least `space-2` apart, so no two targets touch.
- [ ] At 768 and 1280: one row, wordmark at the inline-start, items immediately after it, the
      inline-end empty.
- [ ] Spacing snaps to the scale in every frame — no intermediate inline padding, no hand-tuned gap.
- [ ] Every colour in the frame is a token from §6; nothing renders a hue outside the palette.

## 11. What a screenshot cannot see, and what covers it instead

The states §5 names most carefully — hover, focus-visible, active — **cannot be judged from a static
story capture**, and this repository has already shipped a focus-ring defect across every primitive
in this package for exactly that reason (`tests/visual/focus-ring.spec.ts`'s own header). A reviewer
reading §10 and finding no focus criterion there should find the obligation here rather than assume
it was forgotten. T441 owes both of the following:

- **A `NavItem` joins the control table in `tests/visual/focus-ring.spec.ts`**, as a fifth entry
  alongside Button, Input, checkbox and link, reached by real Tab presses in both themes, asserting
  `:focus-visible` matches and that the computed `outlineStyle` is not `none` at 2px. That file's
  existing shape needs no change beyond a row.
- **`SiteHeader.test.tsx` asserts the behaviour the capture cannot**: Tab reaches `SkipLink` first,
  then `Brand`, then every item in DOM order; exactly one item has `aria-current="page"` in the
  current-route cases and none has it in `NoCurrentItem`; the nested-path rule marks the section
  (`/matches/12345` → Matches) while a non-matching path marks nothing; an item with a blank label
  or href is omitted rather than rendered dead; `items={[]}` renders no `<nav>` at all; a plain left
  click calls `onNavigate` and a modified click does not (`createRowLinkClickHandler`'s contract);
  and the hover and focus class contract is present on every item, the way `Button.test.tsx` already
  asserts `focus-visible:outline-focus-ring`.
