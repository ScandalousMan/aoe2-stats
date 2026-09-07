# Quickstart — Design System Foundations

**Feature**: `005-design-system-foundations` | **Date**: 2026-09-05

How to verify each phase, and how to regenerate baselines without producing a subtly wrong
generation. Every scenario below is runnable and states what a pass looks like.

Prerequisites: `pnpm install --frozen-lockfile`, and `pnpm exec playwright install --with-deps
chromium` once. No database, no API, no environment variable — this feature touches neither.

## The gates, in the order a phase runs them

```bash
pnpm --filter design-system tokens:build && pnpm typecheck && pnpm lint && pnpm test
```

Then the two new checks, and the visual suite:

```bash
node scripts/checks/token-scale.mjs && node scripts/checks/tier-deps.mjs
```

```bash
pnpm --filter design-system build-storybook && pnpm test:visual --changed
```

`tsc -b` runs inside `pnpm typecheck` and is the only thing in the workspace that catches a shared
type drifting between the design system and the application — the application's own unit runner is
transpile-only.

## Scenario 1 — The harness change altered no value (phase 1)

The whole point of doing the machinery first. After the matrix lands and before any token moves,
the captures at the existing axes must be **byte-identical** to the baselines T502 reconciled. The
proof is the commit the `baselines` workflow made, not Playwright's verdict — the suite's
`maxDiffPixelRatio` of 0.01 reports a sub-percent rendering change as clean.

```bash
git show --stat --format= HEAD -- packages/design-system/__screenshots__ | grep -v 'Bin 0 ->'
```

**Pass**: the command prints nothing but the summary line — every file in that commit is an
addition. Every pre-existing baseline, renamed by T504 to its light-1280 name (light-375 for the ten
stories that were `visual-mobile`), is untouched byte for byte, and every dark and other-width
capture is a new file. **Fail**: any pre-existing file listed as modified means the harness changed
rendering, which is the one thing this phase may not do — and this is the only phase in which that
is detectable.

## Scenario 2 — Every design decision has a token (US1)

```bash
node scripts/checks/token-scale.mjs
```

**Pass**: exit 0 over `packages/design-system/src` and `apps/web/src`. **Fail** on an arbitrary
bracket value carrying a length, colour, duration or shadow; a raw hex, `px`, `rem` or `ms`; or a
hand-written `var(--ds-*)` in a class name. The last is the case that survived a year: a
token-derived value written by hand is still a defect, because it means the utility vocabulary has
a hole.

Then read the register:

```bash
grep -n 'DS-[0-9]' packages/design-system/specs/README.md
```

**Pass**: no entry is open with only an interim workaround. Each is closed, or refused with a date
and the replacement named.

## Scenario 3 — Breakpoints have one definition (US1)

Change `md` in `packages/design-system/tokens/breakpoint.json`, rebuild, and confirm both consumers
moved:

```bash
pnpm --filter design-system tokens:build && grep -n 'breakpoint' packages/design-system/tokens/generated/preset.css packages/design-system/tokens/generated/tokens.ts
```

**Pass**: the new value appears in the Tailwind mapping and in the generated TypeScript record, and
`useBreakpoint` reads the record rather than a literal. Restore the value afterwards. **Fail**: a
literal anywhere in `packages/design-system/src/lib`.

## Scenario 4 — Contrast is measured against what ships (US1)

```bash
pnpm --filter design-system test
```

**Pass**: the token tests assert every pair in the measured table that carries an accessibility
floor, computed from the `color.json` that ships. **Fail**: a pair a component draws with no row —
including `text-secondary` on dark `background`, which the register names as drawn and unmeasured
today, and which this feature must add.

Confirm the pairing convention held: for any token you changed, find every component that renders
it and list the background each one paints behind it. A row asserted against a background no
component paints is the defect this repository has now hit three times.

## Scenario 5 — A screen is assembled, not re-invented (US2)

```bash
pnpm --filter web build && pnpm exec playwright test tests/visual/app-routes.spec.ts
```

**Pass**: every route renders exactly one main landmark. **Fail**: any route rendering zero or two.
Ten sources of a second landmark exist today — nine application containers plus two design-system
components, one of which is composed by a route that already nests one.

Then confirm the application writes no layout:

```bash
grep -rnE 'className="[^"]*\b(mx-auto|max-w-|px-[0-9]|py-[0-9]|mt-[0-9]|gap-[0-9])' apps/web/src --include='*.tsx' | grep -v '\.test\.'
```

**Pass**: empty. Every one of those decisions belongs to `Page`, `Section` or `Panel`.

## Scenario 6 — The reader can use the theme they need (US3)

Manual, and it must be manual: a flash of the wrong theme is a first-paint event that no still image
captures.

```bash
pnpm --filter web dev
```

1. Set the operating system to dark and open the app in a fresh profile. **Pass**: it renders dark
   immediately, with no light frame. Record it and step through if unsure.
2. Override to light, reload. **Pass**: still light.
3. Block site data in the browser's settings and reload. **Pass**: it renders the system preference,
   or light if none, and does not throw.
4. With no override stored and the system expressing no preference, **pass**: light.

Then confirm no component branches on the theme:

```bash
grep -rn "dataset.theme\|data-theme" packages/design-system/src --include='*.tsx' | grep -v '\.test\.'
```

**Pass**: matches only under `packages/design-system/src/theme`. Nothing else may know which theme
is active — the toggle sets it and styles nothing by it.

## Scenario 7 — Numbers are legible and comparable (US4)

Open Storybook and compare a column of ratings of differing digit counts.

```bash
pnpm --filter design-system storybook
```

**Pass**: digits align vertically. Now change `font.family.mono` in `font.json` to a proportional
family, rebuild, and look again. **Pass**: still aligned, because the `numeric` role declares
`tabular-nums` rather than relying on the family being monospaced. Restore the value.

**Pass**: no loading or unobserved value renders a digit or a zero, and an unobserved value is
visibly distinct from a measured one.

## Scenario 8 — The system is verified across the axes it claims (US5)

Four deliberate breakages, each of which must fail a check by name.

| Break                                              | Must fail                                                    |
| -------------------------------------------------- | ------------------------------------------------------------ |
| Remove a required accessible name from a component | the axe scan, naming the component                           |
| Change a dark-theme-only colour value              | a dark baseline, and the contrast test if it crosses a floor |
| Introduce an overflow at 768                       | a 768 baseline                                               |
| Import a composite from a primitive                | `scripts/checks/tier-deps.mjs`                               |

Revert each afterwards. A check that does not fail here is a check that will not fail in a pull
request either.

## Scenario 9 — Storybook explains the system without the source (US6)

Hand someone Storybook and no repository access. Ask three questions:

1. Which component to use for a stated need.
2. Which token carries a stated meaning, and on which surfaces it may be painted.
3. What a stated state looks like.

**Pass**: all three answered from the foundation pages and the navigation alone. **Fail**: any
answer that needs the source. This is the only scenario here with a human in it, and it is the one
that decides whether the system is maintainable by an agent working from a cold context.

### Result (T572, run 2026-09-07)

A fresh agent was given the built static Storybook only — no repository access, with
`packages/design-system/src/`, `specs/`, `tokens/`, `apps/` and every `*.stories.tsx` withheld — and
asked the three questions. This is a mixed verdict, not a pass.

1. **Which component for a stated need** (show a player's in-game colour beside their name, and it
   must still make sense for someone who cannot distinguish red from green): **partly answered.**
   `PlayerColourSwatch` was found in two clicks via `Composites → Player identity` — the
   tier-and-need navigation (T564) did its job. The colour-blindness half failed: the redundancy is
   `sr-only` text only, discoverable only by reading the DOM, and the governing rule (FR-011,
   Foundations → Iconography) is not linked from, or claimed by, any component story.
2. **Which token means "this failed", and on which surfaces**: **failed at the time of the run,
   fixed since.** The reader found `danger` on Foundations → Colour in one navigation and called the
   page "the strongest thing in the build", but it then delegated every number to
   `packages/design-system/specs/README.md` and `color-tokens.md` — files the scenario forbids — so
   it could show a rectangle but not the colour behind it, and captioned emphasis tiles with the role
   name four times instead of the surface. A fix landed on this branch (PR #69, following this
   run) that now computes every contrast ratio live from the token pair the tile actually paints and
   captions each tile with its surface. This question passes against the tree as it stands today; it
   did not pass during the run.
3. **What a stated state looks like** (rate-limited `SearchBox`; `selection` on a `Menu`): **half
   excellent, half failed at the time of the run, fixed since.** `SearchBox`'s rate-limited story was
   singled out as the model the rest of the library should follow — its story name is a contract and
   the render honours it line by line. `Menu/Selection`, `Menu/ProfileSwitcher` and
   `Menu/FocusVisible` rendered pixel-identically: a checked item carried `aria-checked` and no
   visual mark, so the ring visible on that row was the focus ring, not a selection mark, and a
   reader could not tell the two states apart. A fix landed on this branch (PR #69, following this
   run) that gave `Menu` an intrinsic leading checkmark, painted when checked and holding reserved
   space when not, and a follow-up spec correction in the same PR moved `FocusVisible`'s focus onto
   an unchecked item so selection and focus read as two signals; the spec files that had described
   the retired caller-supplied badge (`shared-primitives.md`, `profile-summary.md`,
   `site-header.md`) were corrected to match. (One of the two fix commits behind this paragraph was
   superseded by a rebase before landing; only the surviving commit is citable, which is why neither
   is named by hash here.)

Two of the three fixes above landed only after this run named them, and Q1's accessibility half is
still open. What remains — no `docs` entries in the build, docgen off so no prop tables, no
component stating its purpose in a sentence, no story stating which `sr-only` naming shape it
follows — is a property of the package's Storybook build itself, not of the one run that found it,
so it is recorded beside the package rather than here: see
`packages/design-system/specs/README.md`, "Storybook documentation gap register".

## Regenerating baselines

Never locally, for any full-page or application-route baseline, and by one rule for all of them so
the rule has no exception to forget. Dispatch the `baselines` workflow from the branch; it runs on
Linux and commits the result.

**Before dispatching**, know which of the three global repaints you are in — the palette and
typefaces, the structural rhythm, or the retrofit — and say so in the commit body. A regeneration
with no stated cause is 1,794 files nobody can review. A regeneration whose cause is named is one
sentence a reviewer can check against the diff's shape.

**After it lands**, spot-check by hand rather than by count: open three stories in both themes at
all three widths and confirm the change is the one you intended. The diff is uninformative in these
phases by construction, which is why the contrast test, the axe scan and `visual-reviewer` carry
them instead.
