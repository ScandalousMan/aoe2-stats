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

No game asset in the repository: no civilisation icon, no portrait, no font, no sound, no screenshot.
Everything is redrawn or free-licensed, with the licence documented. The Microsoft "Game Content
Usage Rules" disclaimer sits in the site footer.

## Layout

```
packages/design-system/
├── tokens/                    # source of truth
├── specs/                     # written by product-designer, read by everyone
├── src/components/<Name>/     # index.tsx, <Name>.stories.tsx, <Name>.test.tsx
└── .storybook/
```
