---
name: design-system
description: How to consume design tokens and the checklist for building a component. Load before writing or modifying any UI component.
---

# aoe2-stats design system

## Tokens

Single source of truth: `packages/design-system/tokens/*.json`, generated into CSS variables and
TypeScript types. **No hard-coded value in a component** — no colour, no px, no arbitrary rem, no
motion duration, no shadow. If a token is missing, add it to the design system with the
product-designer's agreement; do not work around it.

```tsx
// forbidden
<div className="p-[13px] text-[#c9a227] shadow-[0_2px_8px_rgba(0,0,0,.3)]" />
// expected
<div className="p-3 text-accent shadow-raised" />
```

Families: `color`, `space`, `font`, `radius`, `elevation`, `motion`. Light and dark themes are served
by the same token names — a component never knows the active theme.

## Design decisions

The design system is evolved deliberately rather than by accumulating components.

Before introducing a new component or token:

1. Check whether an existing token, component or pattern already satisfies the need.
2. Prefer composition of existing primitives when appropriate.
3. Introduce a new token only when the visual decision represents a reusable semantic concept.
4. Introduce a new component only when reuse, consistency or interaction complexity justifies it.
5. Do not create abstractions solely to reduce local code duplication.
6. Do not create variants solely to accommodate one page.
7. Application-specific composition belongs in the application unless repeated usage demonstrates
   that it is a design-system pattern.
8. When a component is visually or behaviourally related to an existing component, preserve the
   existing interaction and visual language unless the specification explicitly establishes a
   difference.

## Component checklist — the eight points

A component is done only when all eight are true.

1. **Spec read** — `packages/design-system/specs/<component>.md` exists and has been read. No spec,
   no component: ask the product-designer.
2. **All states implemented** — default, hover, focus-visible, active, disabled, loading, error,
   empty. Empty and loading are not optional.
3. **Tokens only** — greppable: no hex, no px outside a token.
4. **Storybook story** — `<Component>.stories.tsx`, one story per variant and per state, plus a
   realistic combined story.
5. **Accessibility** — correct HTML semantics before ARIA, full keyboard navigation, visible
   `focus-visible`, AA contrast, touch target >= 44px.
6. **Responsive** — verified at 375, 768 and 1280px.
7. **Unit test** — behaviour and accessibility (Testing Library), not pixels: that is the visual
   test's job.
8. **visual-reviewer PASS** — before opening the PR, not after.

## IP constraint

No unrecorded pack: a game asset (civilisation icon, minimap, flag) MAY be copied into
`packages/game-assets/` and served, but only carrying the five-field licence record
`specs/004-visual-parity/contracts/asset-pack.md` requires — Source, Licence, Permitted usage,
Ruling, Checked — and `scripts/checks/asset_packs.py` fails the build on any pack that doesn't. A
portrait, font, sound or screenshot stays out; nothing else has been ruled on. Redrawn or
free-licensed assets still need their licence documented the same way. The Microsoft "Game Content
Usage Rules" disclaimer sits in the site footer and in `README.md` — removing either lapses the
permission (constitution X).

## Layout

```
packages/design-system/
├── tokens/                    # source of truth
├── specs/                     # written by product-designer, read by everyone
├── src/components/<Name>/     # index.tsx, <Name>.stories.tsx, <Name>.test.tsx
└── .storybook/
```
