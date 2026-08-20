# Component specs

Written by `product-designer`, read by `implementer` before writing a component and by
`visual-reviewer` when judging one. Constitution VI: no component exists without a spec, and no
component carries a hard-coded style value.

## Index

| Spec                                             | Component directory                                              | Feature      |
| ------------------------------------------------ | ---------------------------------------------------------------- | ------------ |
| [`shared-primitives.md`](./shared-primitives.md) | `src/components/{Button,Callout,Badge,Skeleton,Menu,StatValue}/` | 001          |
| [`sign-in-screen.md`](./sign-in-screen.md)       | `src/components/SignInScreen/`                                   | 001, US1     |
| [`consent-step.md`](./consent-step.md)           | `src/components/ConsentStep/`                                    | 001, US1/US5 |
| [`profile-summary.md`](./profile-summary.md)     | `src/components/ProfileSummary/`                                 | 001, US1     |

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
3. **No game asset, ever.** No civilisation icon, portrait, font, sound or screenshot from Age of
   Empires II. The visual language — parchment, stone, bronze, illuminated hierarchy — is evoked
   with original drawing and free-licensed assets only. Constitution X; this is a legal boundary,
   not a taste. Every non-text mark used by a component records its origin in the component's spec.
4. **Colour is never the only carrier of meaning.** Win/loss, success/failure, primary/non-primary
   all carry a text or shape signal alongside the colour.
5. **Reduced motion is a real state.** Under `prefers-reduced-motion: reduce`, every transition uses
   `motion.duration.instant` and every looping animation (skeleton pulse above all) stops on its
   resting frame.
6. **Theme-blind components.** Light and dark share token names. A component never branches on the
   active theme, and every contrast obligation is met in both.

## Measured contrast pairs

Computed 2026-08-20 from `tokens/color.json` with the WCAG 2.2 relative-luminance formula, rounded
down to one decimal. **Component specs reference this table by pair; they do not restate the
numbers.** Recompute on any change to `color.json` — the numbers below are the only reason the
accessibility sections elsewhere can be short.

Thresholds: 4.5:1 for normal text, 3:1 for text at 24px+ (or 18.7px+ bold) and for the boundary,
fill or icon of any interactive control (WCAG 1.4.3 and 1.4.11).

### Light theme

| Foreground        | Background       | Ratio | Verdict                                              |
| ----------------- | ---------------- | ----- | ---------------------------------------------------- |
| `text-primary`    | `surface`        | 15.3  | AAA                                                  |
| `text-primary`    | `surface-raised` | 14.5  | AAA                                                  |
| `text-primary`    | `background`     | 13.5  | AAA                                                  |
| `text-primary`    | `surface-sunken` | 11.7  | AAA                                                  |
| `text-secondary`  | `surface`        | 6.2   | AA                                                   |
| `text-secondary`  | `surface-raised` | 5.9   | AA                                                   |
| `text-secondary`  | `background`     | 5.5   | AA                                                   |
| `text-secondary`  | `surface-sunken` | 4.7   | AA, thin margin                                      |
| `info`            | `surface`        | 6.7   | AA                                                   |
| `danger`          | `surface`        | 6.5   | AA                                                   |
| `success`         | `surface`        | 5.9   | AA                                                   |
| `focus-ring`      | `surface`        | 6.7   | passes non-text 3:1                                  |
| `focus-ring`      | `background`     | 5.9   | passes non-text 3:1                                  |
| `warning`         | `surface`        | 4.1   | **fails normal text**; large text and non-text only  |
| `accent`          | `surface`        | 3.7   | **fails normal text**; large text and non-text only  |
| `accent-contrast` | `accent`         | 3.7   | **fails** — see gap DS-1                             |
| `accent-contrast` | `accent-hover`   | 5.0   | AA                                                   |
| `accent-contrast` | `accent-active`  | 6.9   | AA                                                   |
| `border-strong`   | `surface`        | 2.6   | **fails non-text 3:1** — see gap DS-2                |
| `border`          | `surface`        | 1.6   | decorative separators only, never a control boundary |
| `text-disabled`   | `surface`        | 2.6   | exempt (1.4.3, inactive) — see rule under DS-3       |

### Dark theme

| Foreground            | Background       | Ratio | Verdict                                                   |
| --------------------- | ---------------- | ----- | --------------------------------------------------------- |
| `text-primary`        | `surface`        | 13.3  | AAA                                                       |
| `text-primary`        | `surface-raised` | 12.0  | AAA                                                       |
| `text-secondary`      | `surface`        | 7.8   | AAA                                                       |
| `text-secondary`      | `surface-raised` | 7.1   | AAA                                                       |
| `accent-contrast`     | `accent`         | 8.2   | AA                                                        |
| `accent`              | `surface`        | 7.7   | AA (unlike light — `accent` is legible as body text here) |
| `warning`             | `surface`        | 6.8   | AA                                                        |
| `success`             | `surface`        | 6.4   | AA                                                        |
| `focus-ring` / `info` | `surface`        | 6.3   | AA, passes non-text 3:1                                   |
| `danger`              | `surface`        | 5.1   | AA                                                        |
| `border-strong`       | `surface`        | 2.4   | **fails non-text 3:1** — see gap DS-2                     |

The asymmetry is the thing to remember: **the dark theme is comfortable and the light theme is
tight.** Three light-theme pairs fail, and every one of them is on a control a user has to hit.
Judge light first.

## Token gap register

Open items. Each names what is missing, what a component does until it exists, and who has to act.
An implementer who finds themselves needing a value not covered here stops and asks
`product-designer`; they do not invent one.

| Id       | Gap                                                                                                                                                                      | Impact                                                                                 | Interim                                                                                                                                                                                                                                        | Action owed                                                                                                                                                                                                                         |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **DS-1** | Light `accent` is too light to carry `accent-contrast` at 3.7:1. A solid primary button with a normal-size label fails AA in the light theme.                            | Blocks the primary action on every screen in this feature.                             | The solid primary button fills with `accent-hover` at rest, `accent-active` on hover **and** on active, in the light theme only, via token names — never a literal. Ugly, and deliberately so: it is meant to be removed.                      | Darken light `accent` until `accent-contrast` on it reaches 4.5:1, and re-derive `accent-hover` / `accent-active` below it. Owner: design-system. Due before T038.                                                                  |
| **DS-2** | `border-strong` reaches only 2.6:1 (light) and 2.4:1 (dark) against `surface`, below the 3:1 WCAG 1.4.11 needs for the boundary of an input, checkbox or resting button. | Every bordered interactive control fails an automated a11y audit.                      | Interactive boundaries still use `border-strong` — the semantics are right and the value is wrong. Do not substitute `text-secondary` to game the audit.                                                                                       | Darken light `border-strong` and lighten dark `border-strong` to clear 3:1 against `surface`. Owner: design-system. Due before T038.                                                                                                |
| **DS-3** | No opacity token family.                                                                                                                                                 | Disabled styling has no sanctioned dimming route.                                      | Disabled state is expressed with `text-disabled` on `surface-sunken` with `border`, never with an opacity value. `text-disabled` fails AA by design; a disabled control must therefore never be the only place a piece of information appears. | Decide whether an opacity family is wanted at all. Low priority: the colour route is better.                                                                                                                                        |
| **DS-4** | No border-width, focus-ring-width or focus-ring-offset tokens.                                                                                                           | The focus ring — required on every interactive element — cannot be fully token-backed. | One uniform ring everywhere: Tailwind's `outline-2 outline-offset-2` with `outline-focus-ring`. No arbitrary values, no per-component variation.                                                                                               | Ratify Tailwind's built-in width scale as token-equivalent for hairlines and rings, and record that decision, **or** add a `border-width` family. Owner: design-system.                                                             |
| **DS-5** | No breakpoint tokens.                                                                                                                                                    | Responsive sections cannot name breakpoints in our own vocabulary.                     | Specs name Tailwind's default breakpoints (`md` = 768px, `lg` = 1024px, `xl` = 1280px) and the review viewports stay 375 / 768 / 1280.                                                                                                         | Optional. Adopting Tailwind's defaults verbatim is a defensible answer; write it down either way.                                                                                                                                   |
| **DS-6** | No container / max-width / reading-measure tokens.                                                                                                                       | Text columns and centred panels have no token-backed width.                            | Tailwind's `max-w-*` scale, and `max-w-prose` for any paragraph column.                                                                                                                                                                        | Add a `size` family if panel widths start diverging between routes.                                                                                                                                                                 |
| **DS-7** | No icon-size tokens.                                                                                                                                                     | —                                                                                      | Icons size from the adjacent font-size token (`1em`) or from `space-4` / `space-5`.                                                                                                                                                            | Add if icon-only controls multiply.                                                                                                                                                                                                 |
| **DS-8** | No numeric-typography role. Tabular alignment currently rides on `font.family.mono` being monospaced.                                                                    | A future change of mono family silently breaks column alignment on every rating table. | Numeric cells use `font-mono`.                                                                                                                                                                                                                 | Add a `font.role.numeric` alias, or a `font-variant-numeric: tabular-nums` utility, so the intent is recorded rather than inferred. Number legibility is this product's functional priority; it should not depend on a coincidence. |

Recommended, outside this directory's write zone: extend `tokens/build-tokens.test.mjs` with an
assertion over the pairs above, so a colour edit that breaks AA fails a test instead of a review.
