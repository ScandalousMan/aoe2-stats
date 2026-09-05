# Contract: Token families and the utility vocabulary

**Feature**: `005-design-system-foundations` | **Date**: 2026-09-05

The design system's public interface to a component author is not the JSON and not the CSS custom
properties — it is the **set of utility classes a component may write**. This contract fixes that
vocabulary. Anything outside it fails `scripts/checks/token-scale.mjs`.

Values are not fixed here. The palette, the type scale and the typeface question are phase 2
`product-designer` deliverables ([research.md](../research.md) D6, D6a); this file fixes the names,
the shapes and the admission rules they must satisfy.

## 1. The generator's output contract

`packages/design-system/tokens/build-tokens.mjs` reads every `*.json` in its own directory and
writes four things. The fourth is new.

| Output                | Consumed by                                    | New in 005                                  |
| --------------------- | ---------------------------------------------- | ------------------------------------------- |
| `packages/design-system/tokens/generated/tokens.css` | the cascade; `:root` and `[data-theme='dark']` | breakpoint, border and size variables       |
| `packages/design-system/tokens/generated/preset.css` | Tailwind, via `@theme inline`                  | `--breakpoint-*`, `--container-*`, `--animate-*` mappings, `@keyframes`, and every `@utility` block |
| `packages/design-system/tokens/generated/tokens.ts`  | the rare non-utility consumer                  | `breakpointTokens` as raw numbers, not `var()` references |
| custom utilities       | component class names                          | **all of it** — icon sizes, typography roles, the overlay ceiling |

**Why `breakpointTokens` breaks the `var()` rule.** Every other generated TypeScript value is a
`var()` reference because its resolved value depends on the active theme, which is a cascade concern.
A breakpoint is not themed and is passed to `matchMedia`, which needs a number. It is the one
documented exception and the generator states it at the point it emits it.

## 2. The utility vocabulary

A component may write these and nothing else.

| Concern            | Utilities                                                          | Source                     |
| ------------------ | ------------------------------------------------------------------ | -------------------------- |
| Colour             | `bg-*`, `text-*`, `border-*`, `outline-*` over semantic role names | `color.json`               |
| Spacing            | every Tailwind numeric utility, derived from the space multiplier  | `space.json`               |
| Typography family and scale | `font-*`, `text-*`, `tracking-*`, `leading-*`             | `font.json`                |
| Typography role    | `type-display`, `type-body`, `type-supporting`, `type-numeric`, `type-machine`, `type-identifier` | `font.json` role group |
| Radius             | `rounded-*`                                                        | `radius.json`              |
| Elevation          | `shadow-*`                                                         | `elevation.json`           |
| Motion             | `duration-*`, `ease-*`, `animate-spin`, `animate-pulse`            | `motion.json`              |
| Icon size          | `icon-xs` … `icon-3xl`                                             | `icon.json`                |
| Widths             | `border-hairline`, `outline-ring`, `outline-offset-ring`           | `border.json`              |
| Container widths   | `max-w-page`, `max-w-panel`, `max-w-measure`                       | `size.json`                |
| Responsive         | `sm:`, `md:`, `lg:`, `xl:`                                         | `breakpoint.json`          |

**Forbidden, without exception**: an arbitrary bracket value carrying a length, a colour, a duration
or a shadow; a raw hex, `px`, `rem` or `ms` literal; and a hand-written `var(--ds-*)` inside a class
name. The last is the one this system has been failing silently: `h-[var(--ds-icon-2xl)]` is
token-derived and still a defect, because it means the vocabulary has a hole.

**Allowlisted shapes**, which are not values: a `transition-[…]` property list and a bracket
declaration of a CSS property with no design decision in it, such as `[overflow-wrap:anywhere]`.
Each allowlist entry in the check names why it is there.

## 3. Semantic colour roles

Every role declares what it means and which surfaces it may be painted on. A role painted on a
surface it does not declare is a defect whether or not the pair happens to pass contrast (FR-005).

**Surfaces**: `background`, `surface`, `surface-raised`, `surface-sunken`.

**Roles after this feature**: the existing set, plus `link`, `link-hover` and `link-visited`. Every
role's declared surfaces produce rows in the measured contrast table, and every row with an
accessibility floor is asserted.

**Retained without re-derivation**: the eight `player-*` fills and their `-contrast` inks. They are
canonical game colours, theme-invariant by `game-asset-tokens.md`'s decision, and re-deriving them
would change what a player's colour means. Recorded as retained, with that reason (FR-001a).

**No opacity family.** Refused 2026-09-05. Disabled is `text-disabled` on `surface-sunken` with
`border`; de-emphasised is `text-secondary`; the dialog scrim is the `overlay` role, whose
translucence survives the refusal because nothing is read against a scrim, so it owes no pair —
what it owes is that the dialog above it reads, and that pair is already measured
([research.md](../research.md) D9).

## 4. Typography roles

One meaning per role. The monospace family currently carries three, so a change to it moves all
three together.

| Role         | Means                                           | Must carry                                    |
| ------------ | ------------------------------------------------ | --------------------------------------------- |
| `display`    | a page or section heading                       | the display family                            |
| `body`       | prose and control labels                        | the sans family                               |
| `supporting` | secondary or explanatory text                   | the sans family, one size step down           |
| `numeric`    | a measured number                               | the mono family **and `font-variant-numeric: tabular-nums`** |
| `machine`    | a filename, an error class, a raw string        | the mono family                               |
| `identifier` | a value the product could not resolve to a name | the mono family, and `text-secondary` by contract |

`tabular-nums` on `numeric` is what makes digit alignment a decision rather than a coincidence, and
it is why the three meanings had to separate first: declaring the variant on a shared mono role
would also apply it to filenames, where it means nothing.

`identifier` carrying `text-secondary` by contract is deliberate: it is how "an unobserved value is
visibly distinct from a measured one" survives a developer who reaches for the role without reading
its spec.

## 5. The admission test

Applied to every proposed token, and recorded in
`packages/design-system/specs/GOVERNANCE.md` when it decides one.

1. Name the design decision the token expresses, without naming a call site.
2. Name at least two call sites that would use it, present or specified. One is a rejection.
3. Search the existing families for a synonym under a different name. A synonym is a rejection, and
   the rejection names the token that serves.
4. State the utility class a component will write to reach it. If there is none, the family is
   incomplete and the generator changes before the token is admitted.
5. For a colour role: name the surfaces it may be painted on, and add every resulting pair to the
   measured table.
6. Record the outcome in the gap register — admitted, or refused with the date and the replacement.

A rejection is as much an outcome as an admission, and it is recorded in the same place, because the
next reader's question is "was this considered?" and silence answers it wrongly.
