# Footer

**Component**: `src/components/Footer/`
**Feature**: 001, US5 — mounted in the web shell by T098a, in
`apps/web/src/routes/__root.tsx`, so it renders on every route
**Requirements**: none of 001's functional requirements name it; the obligation is constitutional.
Constitution X: "The Microsoft 'Game Content Usage Rules' disclaimer appears in the README and in
the site footer." Constitution VI: "A component without a Storybook story does not exist."
**Depends on**: nothing — this component defines its own markup rather than composing
`shared-primitives.md`, because a footer link is a plain inline `<a>` (the same shape
`archival-control.md`'s `PrivacyNoticeLink` already uses), not a `Button`.
**Sources of truth this copy is derived from, and must not contradict**: `README.md`'s
"Non-commercial" section — the paragraph this component renders is the one already published there,
copied rather than paraphrased, so T098a's "confirm the same disclaimer in `README.md`" has
something exact to confirm against.

**Why this is a design-system component and not page markup in `apps/web`.** T093's reasoning,
stated there about `PrivacyNotice` and repeated here because it is the same fact about a second
component: constitution VI admits no unstoried component, and this disclaimer and the privacy
notice are the only two pieces of copy in the product carrying a legal obligation. A paragraph that
exists only inside a route file is a paragraph no visual review ever looks at, and the failure mode
— it quietly disappears in a layout refactor — leaves no test red. Storybook is what makes it a
thing that screenshots.

**This component states a legal disclaimer, so its copy is normative in the same sense
`privacy-notice.md` claims for itself.** §4 below is not a suggested wording; it is `README.md`'s
own paragraph. A change to either copy without the matching change to the other is the exact defect
this component exists to prevent, and `Footer.test.tsx` asserts the two stay identical.

## 1. Purpose

Carry, on every page of the product, the one attribution Microsoft's Game Content Usage Rules
require this project to display, and give a person who is not signed in the two ways this product
lets them reach their own rights over the data it holds: read the privacy notice, or object to what
is held about them.

## 2. Anatomy

```
Footer                          <footer role="contentinfo">
├─ Disclaimer                   the Game Content Usage Rules attribution, verbatim from README.md
├─ AffiliationNote               "not affiliated with or endorsed by Microsoft or World's Edge"
└─ LinkRow             ×0..1     rendered only when at least one href prop is supplied
   ├─ PrivacyNoticeLink ×0..1    "Read the privacy notice" → privacyNoticeHref
   └─ ObjectionLink     ×0..1    "Object to what is held about me" → objectionHref
```

`Disclaimer` and `AffiliationNote` are never conditional and never omitted — the one requirement
this component exists to satisfy is that they are always on screen. `LinkRow`'s two entries are
independent: either, both or neither may be supplied, and each renders only when its own href is
present, exactly as `ArchivalControl`'s `privacyNoticeHref` link does today.

## 3. Variants, sizes and props

One variant, one size. A footer that changes shape per route would be the one piece of legally
required copy that a reader cannot rely on finding in the same place twice.

```ts
export interface FooterProps {
  /** Renders "Read the privacy notice", linking here. Omitted entirely when absent. */
  privacyNoticeHref?: string
  /** Renders "Object to what is held about me", linking here — the route third-party-objection.md
   * specifies (`apps/web/src/routes/object.tsx`), outside the session. Omitted entirely when
   * absent. */
  objectionHref?: string
  className?: string
}
```

No `variant`, no `size`, no copy prop: the disclaimer text is not configurable, by design — a
caller that could override it could also break it.

## 4. Copy

Normative, and copied verbatim from `README.md`'s "Non-commercial" section rather than
paraphrased. A change here happens in the same PR as the matching change to `README.md`, in that
order of reasoning: `README.md` is the disclosure Microsoft's rules require to exist in the
repository, this component is the same disclosure rendered where a visitor actually sees it.

`Disclaimer`:

> aoe2-stats was created under Microsoft's "Game Content Usage Rules" using assets from Age of
> Empires II: Definitive Edition, (c) Microsoft Corporation.

`AffiliationNote`:

> This project is not affiliated with or endorsed by Microsoft or World's Edge.

`PrivacyNoticeLink` label: **Read the privacy notice** — identical wording to
`ArchivalControl`'s existing link, so the same control does not read differently in two places.

`ObjectionLink` label: **Object to what is held about me** — identical wording to
`PrivacyNotice` §4.7's `ObjectionCallToAction`, for the same reason.

## 5. States

- **default** — as anatomised in §2, always. This is functionally the only state; a footer's
  disclaimer does not have a "loading" phase.
- **hover** — `PrivacyNoticeLink` and `ObjectionLink` only: colour moves to `link-hover`
  underneath the permanent underline. Nothing else in this component responds to a pointer.
- **focus-visible** — the standard ring (`outline-2 outline-offset-2`, gap DS-4) on each link that
  is present. The disclaimer and the affiliation note are not focusable; they are not controls.
- **active** — links render `link-hover` while pressed (there is deliberately no `link-active`;
  T522's `link-hover` serves both — `color-tokens.md` §11.3). Nothing translates or scales.
- **disabled** — not applicable. A link is either rendered (its href is present) or absent; there
  is no dimmed, unusable middle state for a footer link. Rendering a dead link when a route does
  not yet exist would be worse than omitting it, and omission is what the optional props already do.
- **loading** — none. Every string here is a build-time constant; nothing in this component ever
  waits on a network response, in the same way `privacy-notice.md` §5 requires of itself.
- **error** — none of its own. A caller with no privacy or objection route yet simply omits the
  props; there is no failure state to render for text that was never promised.
- **empty** — `LinkRow` itself: renders nothing when neither href prop is supplied, rather than an
  empty row with a visible gap where two links would have been. `Disclaimer` and `AffiliationNote`
  are never empty — they carry no prop that could make them so.

## 6. Tokens used

Colour: `background` (the footer's own fill — it sits on the page background, not `surface`, so it
reads as chrome rather than as a card), `border` (the top rule separating it from page content),
`text-secondary` (`Disclaimer`, `AffiliationNote`), `link` (the links' resting colour — T522 gives
this the one signal that says it is a link, and it declares `background` and is measured there,
which retires the earlier avoidance of an `accent`-on-`background` pair: `link` is not `accent`,
and the pair is now measured rather than untested), `link-hover` (hover and active — there is no
`link-active`; `color-tokens.md` §11.3), `focus-ring`. The link expresses its quietness with size
(`sm`), which it already carried, rather than by withholding the link colour.

Font: family `sans` throughout. Size `sm` for `Disclaimer` and `AffiliationNote` — small enough to
read as chrome, never smaller, because a disclaimer nobody can read does not satisfy the obligation
it exists for; `sm` for both links, matching. Weight `normal` throughout; nothing in this component
is emphasised over anything else in it.

Radius: none — a footer has no rounded surface of its own.
Elevation: `none` — chrome sits flush with the page, it does not float above it.
Motion: `duration.fast` + `easing.standard` on link colour only, falling back to
`duration.instant` under `prefers-reduced-motion: reduce`.

Gaps in play: none new. `text-secondary` on `background` is already asserted in the README's
contrast table (light 5.5, dark comfortable); `link` on `background` is asserted by T522
(`color-tokens.md` §11.5: 5.97 light / 7.51 dark).

## 7. Spacing

| Between                           | Step                              |
| --------------------------------- | --------------------------------- |
| Footer padding                    | `space-4` inline, `space-6` block |
| `Disclaimer` to `AffiliationNote` | `space-2`                         |
| `AffiliationNote` to `LinkRow`    | `space-4`                         |
| Between `LinkRow` entries         | `space-4`                         |

## 8. Responsive

- **375** — `LinkRow` entries stack vertically, full width, each clearing the 44px touch minimum
  with its own padding-block. `Disclaimer` and `AffiliationNote` wrap as running text; no
  horizontal scrolling.
- **768** — `LinkRow` entries sit inline, separated by `space-4`, left-aligned under the two text
  lines.
- **1280** — identical layout to 768; the footer never widens into a second column or a multi-part
  grid. It is one narrow block of chrome regardless of viewport width, matching every other footer
  in the product's information hierarchy — the least important, most consistent element on the
  page.

## 9. Accessibility

- Root is `<footer role="contentinfo">` (the landmark role is implicit for a top-level `<footer>`;
  stated in the anatomy for clarity, not added redundantly in markup).
- `Disclaimer` and `AffiliationNote` are plain `<p>` text, read in document order.
- Each link is a real `<a href>` with a permanent underline, never colour alone (README rule 4).
- Touch targets: each `LinkRow` entry clears 44px at 375px via its own padding-block, matching
  `privacy-notice.md`'s `Contents` entries.
- Contrast: `text-secondary` on `background` — 5.5 (light) per the README's measured table; dark
  theme is the comfortable side per the README's general note. `link` on `background` — 5.97
  light / 7.51 dark (`color-tokens.md` §11.5). Link hover colour (`link-hover`) is only ever shown
  together with the permanent underline, so it never has to carry the pairing alone.
- Reading order equals visual order equals DOM order at every viewport.

## 10. Visual acceptance criteria

- [ ] `Disclaimer` and `AffiliationNote` are both present, in full, in every story — including the
      story with neither href supplied.
- [ ] The exact phrase `Game Content Usage Rules` appears in the frame.
- [ ] The exact phrase `not affiliated with or endorsed by Microsoft or World's Edge` appears in the
      frame.
- [ ] With both hrefs supplied, both links render, each as a real `<a>` with a visible underline.
- [ ] With neither href supplied, no empty `LinkRow` gap is visible — the footer ends cleanly after
      `AffiliationNote`.
- [ ] With only one href supplied, only that one link renders — never a placeholder for the other.
- [ ] At 375px, no horizontal scrolling and no clipped text in any story.
- [ ] The focus ring is visible and unclipped on each rendered link, in both themes.
- [ ] No game asset, icon, portrait or logo anywhere in the frame — text only.
