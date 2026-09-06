---
name: design-system
description: How to consume design tokens and the checklist for building a component. Load before writing or modifying any UI component.
---

# aoe2-stats design system

## Tokens

Single source of truth: `packages/design-system/tokens/*.json`, generated into CSS variables,
Tailwind utilities and TypeScript types. **No hard-coded value in a component** — no colour, no px,
no arbitrary rem, no motion duration, no shadow, and no hand-written `var(--ds-*)` inside a class
name either: that is still a raw value wearing a token's name, and it means the utility vocabulary
below has a hole, not that the component gets to route around it.

```tsx
// forbidden
<div className="p-[13px] text-[#c9a227] shadow-[0_2px_8px_rgba(0,0,0,.3)]" />
// expected
<div className="p-3 text-accent shadow-raised" />
```

The utility vocabulary a component may write — every family, one row per concern, colour roles,
typography roles, icon sizes, container widths — is
`specs/005-design-system-foundations/contracts/token-families.md` §2, mechanically enforced by
`scripts/checks/token-scale.mjs`; this file does not restate the list, a copy here would be the
next one to go stale. Light and dark themes are served by the same token names — a component never
knows the active theme, the one exemption being `SiteHeader`'s `ThemeControl`
(`packages/design-system/specs/README.md`, standing rule 8).

If a token, component or variant the vocabulary has no answer for is genuinely needed, do not
invent a workaround — run the matching procedure below.

## Design decisions

The design system is evolved deliberately rather than by accumulating components.
`packages/design-system/specs/GOVERNANCE.md` is the admission and promotion authority: four
mechanical procedures, each a numbered sequence with a recorded outcome, none requiring a
synchronous human decision. Run the matching one before introducing or retiring anything:

1. **Token admission** (§1) — needs real call sites beyond a single one and no existing synonym
   under a different name.
2. **Component and variant admission** (§2) — attempt composition of existing primitives and
   composites first; a new component needs reuse, consistency or interaction complexity; a new
   variant needs a distinct meaning no existing variant expresses, not one call site's requirement.
3. **Promotion threshold** (§3) — an application composition repeated past the threshold is
   promoted into the system, or the reason it is not is recorded beside the qualifying occurrence.
4. **Deprecation** (§4) — name the replacement, enumerate every consumer, land the removal together
   with their migration in the same change.

Where a component is visually or behaviourally related to an existing one, preserve its existing
interaction and visual language unless a spec explicitly establishes a difference — one prop
vocabulary for the same concept, not two spellings of it (`README.md` standing rule 9).

## Component checklist — the eight points

A component is done only when all eight are true.

1. **Spec read** — `packages/design-system/specs/<component>.md` exists and has been read. No spec,
   no component: ask the product-designer.
2. **All states implemented** — every entry in the closed state vocabulary
   `packages/design-system/specs/README.md` defines (`## Every spec has nine sections`), including
   selection and expansion where the component holds one. Empty and loading are never optional, and
   two states may never differ by colour alone or only while a pointer hovers or an animation is
   mid-flight — the difference must survive as a still image, because that is what a captured
   screenshot can judge.
3. **Tokens only** — greppable: no hex, no px outside a token, no hand-written `var(--ds-*)`.
4. **Storybook story** — `<Component>.stories.tsx`, one story per variant and per state, plus a
   realistic combined story.
5. **Accessibility** — correct HTML semantics before ARIA, full keyboard navigation, visible
   `focus-visible`, AA contrast, touch target >= 44px.
6. **Responsive** — verified at the review widths `README.md` standing rule 7 declares, in both
   themes — the same matrix `scripts/visual/run.mjs` and `visual-reviewer` actually capture
   (`specs/005-design-system-foundations/contracts/verification-matrix.md`).
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
│   └── GOVERNANCE.md          # admission and promotion authority
├── src/
│   ├── primitives/<Name>/     # includes the structural primitives structural-tier.md documents;
│   │                          # no dependency on a composite, a screen, or apps/
│   ├── composites/<Name>/     # domain composites — may depend on primitives
│   └── screens/<Name>/        # index.tsx, <Name>.stories.tsx, <Name>.test.tsx
└── .storybook/
```

Which tier a component lives in is a dependency rule, not a naming convention:
`scripts/checks/tier-deps.mjs` fails the build the moment a primitive imports a composite or a
screen, or anything under `src/` imports from `apps/`. The tier is decided once, at admission time,
by `GOVERNANCE.md` §2 step 5 — never guessed afterwards from where a file happens to sit.
