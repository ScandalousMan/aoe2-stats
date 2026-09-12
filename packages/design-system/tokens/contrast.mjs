// The one WCAG 2.2 relative-luminance / contrast-ratio implementation, extracted by T580 to close
// the "Duplicated logic and story-content gap register" row `packages/design-system/specs/
// README.md` has carried since the fifth-pass adversarial review (2026-09-09): the formula below
// used to be written out by hand three times — `.storybook/foundations/Colour.stories.tsx`,
// `tokens/build-tokens.test.mjs` and `tests/visual/focus-ring.spec.ts` — each with a comment
// correctly arguing it was not a duplicated *measurement* (Colour.stories.tsx derives live from a
// generated token; focus-ring.spec.ts starts from a `getComputedStyle` `rgb(...)` string, not a
// hex). Both are true and beside the point CLAUDE.md makes: the *formula itself* — the sRGB-to-
// linear piecewise function, the relative-luminance weights, the contrast-ratio arithmetic — had to
// stay correct in all three files, and nothing failed a build if only two of the three were kept in
// sync. This module is the one home; the three call sites import it instead of re-deriving it.
//
// Two entry points, matched to what each of the three call sites actually has in hand:
// `contrastRatioHex` for `Colour.stories.tsx` and `build-tokens.test.mjs`, which both start from a
// `#rrggbb` string read out of `tokens/color.json`; `contrastRatioRgb` for `focus-ring.spec.ts`,
// which starts from a `{ r, g, b }` triple already parsed out of a live `getComputedStyle`
// `rgb(...)`/`rgba(...)` string — parsing that string stays that call site's own job (`parseRgb`),
// because it is I/O specific to reading a rendered page, not part of the formula.
//
// `.mjs`, not `.ts`: `tokens/build-tokens.test.mjs` runs under plain `node --test` with no build
// step, so this module has to be executable Node ESM as-is. `contrast.d.mts` beside it gives the
// TypeScript call site (`Colour.stories.tsx`, bundled by Vite) a real type instead of an implicit
// `any` — the same split `scripts/visual/review-widths.mjs` / `.d.mts` already uses.

// The 0.03928 linearisation threshold below is the older of two values WCAG has published for this
// breakpoint; current W3C text uses 0.04045. Deliberately not "corrected" here: for an 8-bit integer
// channel (0-255, which is everything every call site of this module ever passes) the two produce
// identical results, because no integer channel value lies strictly between 0.03928 x 255 ~= 10.02
// and 0.04045 x 255 ~= 10.31 — the piecewise branches agree at every representable input. T580 is an
// extraction: changing the constant here would make "no contrast ratio moved" unprovable, so the
// value stays exactly what all three original copies wrote, with this comment as the reason the
// next reader should not "fix" it blind.
function srgbToLinear(channel) {
  const c = channel / 255
  return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)
}

function relativeLuminanceRgb({ r, g, b }) {
  return 0.2126 * srgbToLinear(r) + 0.7152 * srgbToLinear(g) + 0.0722 * srgbToLinear(b)
}

function hexToRgb(hex) {
  const value = hex.replace('#', '')
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(value.slice(i, i + 2), 16))
  return { r, g, b }
}

/**
 * WCAG 2.2 contrast ratio between two colours, each given as a `{ r, g, b }` triple (0-255).
 * The entry point `tests/visual/focus-ring.spec.ts` calls after parsing a live `getComputedStyle`
 * colour string.
 */
export function contrastRatioRgb(a, b) {
  const lA = relativeLuminanceRgb(a)
  const lB = relativeLuminanceRgb(b)
  const lighter = Math.max(lA, lB)
  const darker = Math.min(lA, lB)
  return (lighter + 0.05) / (darker + 0.05)
}

/**
 * WCAG 2.2 contrast ratio between two colours, each given as a `#rrggbb` hex string. The entry
 * point `.storybook/foundations/Colour.stories.tsx` and `tokens/build-tokens.test.mjs` call, both
 * starting from a hex value read straight out of `tokens/color.json`.
 */
export function contrastRatioHex(hexA, hexB) {
  return contrastRatioRgb(hexToRgb(hexA), hexToRgb(hexB))
}
