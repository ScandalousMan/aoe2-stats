// Regression tests for the token generator (T016). Runs the real generator against the real JSON
// — there is nothing to fake here, the whole point is that tokens/*.json is the single source of
// truth — then asserts on the files it writes to tokens/generated/.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const tokensDir = path.dirname(fileURLToPath(import.meta.url))
const generatedDir = path.join(tokensDir, 'generated')
const color = JSON.parse(readFileSync(path.join(tokensDir, 'color.json'), 'utf8'))
const font = JSON.parse(readFileSync(path.join(tokensDir, 'font.json'), 'utf8'))

// --- WCAG 2.2 contrast ratio, computed from the same relative-luminance formula the specs table
// (packages/design-system/specs/README.md, "Measured contrast pairs") is computed from by hand.
// This is the assertion that table's own header asks for: "a colour edit fails a test instead of
// a review" (T034a). Keep the two in sync — recompute the table when a ratio below changes.
function srgbToLinear(channel) {
  const c = channel / 255
  return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)
}

function relativeLuminance(hex) {
  const value = hex.replace('#', '')
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(value.slice(i, i + 2), 16))
  return 0.2126 * srgbToLinear(r) + 0.7152 * srgbToLinear(g) + 0.0722 * srgbToLinear(b)
}

function contrastRatio(hexA, hexB) {
  const lA = relativeLuminance(hexA)
  const lB = relativeLuminance(hexB)
  const lighter = Math.max(lA, lB)
  const darker = Math.min(lA, lB)
  return (lighter + 0.05) / (darker + 0.05)
}

test('tokens:build regenerates the CSS and TS output without error', () => {
  execFileSync('node', [path.join(tokensDir, 'build-tokens.mjs')], { stdio: 'pipe' })
})

test('tokens.css never leaks a $-prefixed JSON metadata key as a CSS declaration', () => {
  const css = readFileSync(path.join(generatedDir, 'tokens.css'), 'utf8')
  assert.doesNotMatch(css, /--ds-[a-z-]*comment/)
})

test('tokens.css declares both themes under the same variable names', () => {
  const css = readFileSync(path.join(generatedDir, 'tokens.css'), 'utf8')
  assert.match(css, /:root\s*{[^}]*--ds-color-accent:/s)
  assert.match(css, /\[data-theme='dark'\]\s*{[^}]*--ds-color-accent:/s)
})

test('preset.css maps the design-system skill examples: bg/text-accent, shadow-raised, spacing', () => {
  const preset = readFileSync(path.join(generatedDir, 'preset.css'), 'utf8')
  assert.match(preset, /--color-accent:\s*var\(--ds-color-accent\);/)
  assert.match(preset, /--shadow-raised:\s*var\(--ds-elevation-raised\);/)
  assert.match(preset, /--spacing:\s*var\(--ds-space-unit\);/)
  assert.match(preset, /^@import '\.\/tokens\.css';/m)
})

test('tokens.ts exports every family as a typed, var()-referencing const', () => {
  const ts = readFileSync(path.join(generatedDir, 'tokens.ts'), 'utf8')
  for (const exportName of [
    'colorTokens',
    'spaceTokens',
    'radiusTokens',
    'iconTokens',
    'elevationTokens',
    'fontTokens',
    'motionTokens',
  ]) {
    assert.match(ts, new RegExp(`export const ${exportName} = {`))
  }
  assert.match(ts, /'accent': 'var\(--ds-color-accent\)',/)
})

// --- Key-set symmetry (T512). A themed family (color.light/color.dark, elevation.light/
// elevation.dark, and any family this shape is added to later) names the same tokens in both
// themes by construction (design-system skill, "Tokens": "a component never knows which is
// active"). A key present in one theme only is not a smaller palette — it is a component that
// renders in the theme that has it and breaks, silently, the moment the reader switches to the
// one that doesn't. Generic over every `*.json` in this directory rather than hard-coded to
// `color` and `elevation`, so a themed family added later is covered with no edit here.
test('every themed family declares the same key set in both themes', () => {
  const jsonFiles = readdirSync(tokensDir).filter((name) => name.endsWith('.json'))
  for (const file of jsonFiles) {
    const family = JSON.parse(readFileSync(path.join(tokensDir, file), 'utf8'))
    if (!('light' in family) || !('dark' in family)) continue // not a themed family
    const lightKeys = new Set(Object.keys(family.light))
    const darkKeys = new Set(Object.keys(family.dark))
    const onlyLight = [...lightKeys].filter((key) => !darkKeys.has(key)).sort()
    const onlyDark = [...darkKeys].filter((key) => !lightKeys.has(key)).sort()
    assert.deepStrictEqual(
      onlyLight,
      [],
      `${file}: key(s) declared in "light" only: ${onlyLight.join(', ')} — a component reading ` +
        'one of these renders in light and breaks the moment the reader switches to dark',
    )
    assert.deepStrictEqual(
      onlyDark,
      [],
      `${file}: key(s) declared in "dark" only: ${onlyDark.join(', ')} — a component reading one ` +
        'of these renders in dark and breaks the moment the reader switches to light',
    )
  }
})

// --- Contrast assertions (T034a, corrected by T038a and T034c). These are the pairs the specs'
// measured-contrast table (DS-1, DS-2) names as failing, plus light `warning`, which T034a wrongly
// judged exempt from the normal-text floor and T038a corrected. Each assertion encodes the actual
// accessibility obligation on that pair — not a blanket 4.5:1 — so an edit to color.json is judged
// the same way T034 judged it. T034c corrected the background half of that obligation: several of
// these pairs were asserted against a real but unused background, rather than the one the
// component actually paints — see the "Real rendered pairs" block below.

test('accent-contrast clears AA normal text (4.5:1) on accent, accent-hover and accent-active, in both themes — DS-1, the primary button fill and (T521, color-tokens.md §5) its own inward focus ring', () => {
  // `accent-contrast` is no longer only the primary button's label ink: since DS-10's resolution
  // (color-tokens.md §5), it is also the ring `Button`'s `primary` variant and
  // `DataExportPanel`'s download link draw with `-outline-offset-2`, because `focus-ring` cannot
  // clear 3:1 against a fill dark enough to be legible as text (§5's proof). So this pair now owes
  // its floor at rest, on hover and on press, in both themes, not just in light.
  for (const theme of ['light', 'dark']) {
    const {
      accent,
      'accent-hover': hover,
      'accent-active': active,
      'accent-contrast': contrast,
    } = color[theme]
    for (const [name, hex] of [
      ['accent', accent],
      ['accent-hover', hover],
      ['accent-active', active],
    ]) {
      const ratio = contrastRatio(contrast, hex)
      assert.ok(
        ratio >= 4.5,
        `accent-contrast on ${name} is ${ratio.toFixed(2)}:1 in the ${theme} theme, below 4.5:1`,
      )
    }
  }
})

test('accent, accent-hover and accent-active stay distinct from each other, in both themes', () => {
  // A resting state indistinguishable from its hover state tells a user nothing responded — the
  // whole reason T034a re-derives the pair instead of collapsing rest onto accent-hover.
  for (const theme of ['light', 'dark']) {
    const { accent, 'accent-hover': hover, 'accent-active': active } = color[theme]
    assert.notStrictEqual(
      accent,
      hover,
      `${theme}: accent and accent-hover must not be the same colour`,
    )
    assert.notStrictEqual(
      hover,
      active,
      `${theme}: accent-hover and accent-active must not be the same colour`,
    )
    assert.notStrictEqual(
      accent,
      active,
      `${theme}: accent and accent-active must not be the same colour`,
    )
  }
})

// --- Real rendered pairs (T034c) ---------------------------------------------------------------
// A contrast obligation belongs to a *pair* — foreground and the background a component actually
// paints behind it — not to a token read in isolation. Twice now (DS-2, then T038a's own warning
// fix) an assertion here named a real pair that was nonetheless not the one any component draws,
// and passed while the rendered control failed: `border-strong` was asserted against `surface`
// (3.39:1) while `Button`'s secondary variant, placed directly on `ConsentStep`'s page background
// by `DashboardContainer` (`apps/web/src/features/profile/DashboardContainer.tsx`, `<main
// className="bg-background">`), draws against `background` and measured 2.99:1 there — under the
// floor. `warning` was asserted against `surface` (4.75:1) while `Callout` — the only component
// that ever colours text with `warning` — is unconditionally `bg-surface-raised`
// (`src/components/Callout/index.tsx`), where the pair measures 4.52:1: over the floor, but by
// two hundredths, none of which showed up in a test that checked a different background.
//
// The fix here is the same shape for both: assert every background the token is actually
// rendered against, found by reading the component, not the one that first comes to mind. Below,
// each assertion names the component and file that draws the pair it checks.
function assertRealPair(theme, foreground, background, floor, label) {
  const ratio = contrastRatio(foreground, background)
  assert.ok(
    ratio >= floor,
    `${label} is ${ratio.toFixed(2)}:1 in the ${theme} theme, below the ${floor}:1 floor it owes`,
  )
}

test('border-strong clears the 3:1 non-text floor against every background it is rendered on — DS-2, T034c', () => {
  // `border-strong` boundaries `Button`'s `secondary`/`ghost`/`destructive` variants and `Menu`'s
  // trigger (`src/components/Button/index.tsx`, `src/components/Menu/index.tsx`). Those controls
  // are placed, across the product, directly on all three surfaces a page ever paints behind one:
  //  - `background` — `ConsentStep`'s onboarding decline control ("Not now") on
  //    `DashboardContainer`'s `<main className="bg-background">`. This is FR-034's genuinely-
  //    declinable control, and the pair that measured 2.99:1 and moved light `border-strong`.
  //  - `surface` — `SignInScreen`'s card (`bg-surface`) and the `Menu` trigger's own fill.
  //  - `surface-raised` — every secondary `Button` rendered inside a `Callout`
  //    (`SignInScreen`'s outcome actions, `ProfileSummary`'s "Back to primary").
  for (const theme of ['light', 'dark']) {
    const {
      background,
      surface,
      'surface-raised': surfaceRaised,
      'border-strong': borderStrong,
    } = color[theme]
    for (const [bgName, bg] of [
      ['background', background],
      ['surface', surface],
      ['surface-raised', surfaceRaised],
    ]) {
      assertRealPair(theme, borderStrong, bg, 3, `border-strong on ${bgName}`)
    }
  }
})

test('warning clears the 4.5:1 normal-text floor against the surface its Callout heading actually renders on — T038a, corrected by T034c, re-derived by T521', () => {
  // Structural rule from T034 stays exactly as it was: callout body text is always
  // `text-primary`; `warning` only colours the stripe and the heading, and `Callout`'s heading
  // renders `font-sans text-md font-semibold` (16px at weight 600) — normal-size text, so this
  // pair owes 4.5:1. T038a corrected the threshold but asserted it against `surface`; `Callout`'s
  // own container is unconditionally `bg-surface-raised` (`src/components/Callout/index.tsx`),
  // never `surface`, so that is the pair every consumer actually draws. T521's re-derivation
  // (color-tokens.md §3.3, one chromatic band per theme) moves this from a two-hundredths margin
  // in light (4.52:1) to 7.06:1 — the margin the whole ramp exists to restore.
  for (const theme of ['light', 'dark']) {
    const { warning, 'surface-raised': surfaceRaised } = color[theme]
    assertRealPair(theme, warning, surfaceRaised, 4.5, 'warning on surface-raised')
  }
})

test('info, success and danger clear the 4.5:1 floor their Callout heading use owes, in both themes — T034c', () => {
  // The three tones nothing asserted before this task. They sit in the exact same component as
  // `warning`, coloring the same heading role (`toneClasses` in `src/components/Callout/index.tsx`)
  // in the same unconditional `bg-surface-raised` container — the fact that they happen to clear
  // the floor comfortably today is not a reason to leave them unchecked; it is the same rule
  // that let `border-strong` and `warning` regress silently in the first place.
  for (const theme of ['light', 'dark']) {
    const { 'surface-raised': surfaceRaised, info, success, danger } = color[theme]
    for (const [name, hex] of [
      ['info', info],
      ['success', success],
      ['danger', danger],
    ]) {
      assertRealPair(theme, hex, surfaceRaised, 4.5, `${name} heading text on surface-raised`)
    }
  }
})

// --- T521 additions (color-tokens.md §7, §10) --------------------------------------------------
// The re-derivation's own admission tests: pairs the previous palette either measured against the
// wrong background or never measured at all.

test('success and danger clear the 4.5:1 floor on surface, background and surface-sunken, in both themes — the MatchRow win/loss text and its row-hover state, and the ProfileSummary delta, color-tokens.md §6 note 3', () => {
  // `success` and `danger` are the only chromatic roles a data row paints directly: `MatchRow`
  // puts win/loss text on `bg-surface` and hovers the row to `bg-surface-sunken` underneath that
  // same text (`src/components/MatchRow/index.tsx`), and `ProfileSummary` puts a rating delta
  // straight on `bg-background`. Both were previously measured against `surface` and
  // `surface-raised` only — this closes that gap rather than widening it later.
  for (const theme of ['light', 'dark']) {
    const { surface, background, 'surface-sunken': surfaceSunken, success, danger } = color[theme]
    for (const [roleName, hex] of [
      ['success', success],
      ['danger', danger],
    ]) {
      for (const [bgName, bg] of [
        ['surface', surface],
        ['background', background],
        ['surface-sunken', surfaceSunken],
      ]) {
        assertRealPair(theme, hex, bg, 4.5, `${roleName} on ${bgName}`)
      }
    }
  }
})

test('every <role>-contrast ink clears the 4.5:1 floor on its own filled role, in both themes', () => {
  // Every `-contrast` token is the ink placed *on* a filled role (color-tokens.md §3.6) and is
  // buildable only if that pair clears AA normal text. Light `warning-contrast` on `warning`
  // measured 3.47:1 — under even the 3:1 non-text floor — with no assertion here at all; that gap
  // is exactly what this test exists to catch, for every chromatic role, not just the one that was
  // already known to be broken.
  for (const theme of ['light', 'dark']) {
    const {
      success,
      'success-contrast': successContrast,
      warning,
      'warning-contrast': warningContrast,
      danger,
      'danger-contrast': dangerContrast,
      info,
      'info-contrast': infoContrast,
    } = color[theme]
    for (const [name, fill, contrast] of [
      ['success', success, successContrast],
      ['warning', warning, warningContrast],
      ['danger', danger, dangerContrast],
      ['info', info, infoContrast],
    ]) {
      assertRealPair(theme, contrast, fill, 4.5, `${name}-contrast on ${name}`)
    }
  }
})

test('focus-ring clears the 3:1 non-text floor against all four page surfaces, in both themes — DS-10, color-tokens.md §5', () => {
  // `focus-ring` declares the four page surfaces and nothing else (color-tokens.md §5, §6): an
  // `accent`-filled control does not ring with `focus-ring` at all, it rings inward with
  // `accent-contrast` (covered above), because one ring colour cannot bridge a near-white surface
  // and a near-ink fill (§5's proof). There is deliberately no assertion of `focus-ring` against
  // `accent` here — that pair is not drawn by any component after T521.
  for (const theme of ['light', 'dark']) {
    const {
      background,
      surface,
      'surface-raised': surfaceRaised,
      'surface-sunken': surfaceSunken,
      'focus-ring': focusRing,
    } = color[theme]
    for (const [bgName, bg] of [
      ['background', background],
      ['surface', surface],
      ['surface-raised', surfaceRaised],
      ['surface-sunken', surfaceSunken],
    ]) {
      assertRealPair(theme, focusRing, bg, 3, `focus-ring on ${bgName}`)
    }
  }
})

test('dark text-secondary clears the 4.5:1 floor on background — the ProfileSummary pair the previous table never carried', () => {
  // `ProfileSummary` draws the profile id and freshness note in `text-secondary` directly on the
  // page (`bg-background`), in both themes. Light `text-secondary` on `background` was already
  // measured; the dark half of the same pair was not.
  const { 'text-secondary': textSecondary, background } = color.dark
  assertRealPair('dark', textSecondary, background, 4.5, 'text-secondary on background')
})

// --- T522 additions (color-tokens.md §11.5) -----------------------------------------------------
// `link`, `link-hover` and `link-visited` declare all four page surfaces in both themes (closes
// DS-9): a state role must declare at least everything its rest role declares, so a shorter list
// for the hover or visited step would make hovering or revisiting a declared link an undeclared
// pair. 3 roles x 4 surfaces x 2 themes = 24 assertions, all at the normal-text 4.5:1 floor.
test('link, link-hover and link-visited clear the 4.5:1 floor on all four page surfaces, in both themes — DS-9, color-tokens.md §11.5', () => {
  for (const theme of ['light', 'dark']) {
    const {
      background,
      surface,
      'surface-raised': surfaceRaised,
      'surface-sunken': surfaceSunken,
      link,
      'link-hover': linkHover,
      'link-visited': linkVisited,
    } = color[theme]
    for (const [roleName, hex] of [
      ['link', link],
      ['link-hover', linkHover],
      ['link-visited', linkVisited],
    ]) {
      for (const [bgName, bg] of [
        ['background', background],
        ['surface', surface],
        ['surface-raised', surfaceRaised],
        ['surface-sunken', surfaceSunken],
      ]) {
        assertRealPair(theme, hex, bg, 4.5, `${roleName} on ${bgName}`)
      }
    }
  }
})

// --- Player colour swatches (T410, FR-003) ------------------------------------------------------
// The eight canonical player colours are theme-invariant (a player's colour is their identity, not
// a per-theme choice — packages/design-system/specs/game-asset-tokens.md, Decision 1), so every
// `player-N` / `player-N-contrast` pair carries one value in both theme blocks. Each pair owes
// 4.5:1: a glyph on the swatch (a winner marker) is treated as normal text, the conservative floor.
// A colour shipped without a paired, verified contrast token is a component that hard-codes a
// foreground the first time a bright fill (e.g. Yellow) needs a legible glyph on it.
test('every player colour has a paired -contrast token that clears 4.5:1, in both theme blocks', () => {
  for (const theme of ['light', 'dark']) {
    for (let n = 1; n <= 8; n += 1) {
      const fill = color[theme][`player-${n}`]
      const contrast = color[theme][`player-${n}-contrast`]
      assert.ok(fill, `color.json ${theme} is missing player-${n}`)
      assert.ok(contrast, `color.json ${theme} is missing player-${n}-contrast`)
      const ratio = contrastRatio(contrast, fill)
      assert.ok(
        ratio >= 4.5,
        `player-${n}-contrast on player-${n} is ${ratio.toFixed(2)}:1 in the ${theme} theme, ` +
          'below the 4.5:1 AA floor a glyph on the swatch needs',
      )
    }
  }
})

// --- T523 addition (typography-tokens.md §4.3 step 6, §10) --------------------------------------
// A family-name mismatch between `font.face`'s `@font-face` declaration and `font.family`'s stack
// is invisible: the browser silently falls back to the next name in the stack, with no error and
// no failing test anywhere else. This is the JSON half of the trap; the font-file half is a manual
// verification `visual-reviewer`'s screenshots back up (§13).
test('every font.face family matches the first quoted name in the matching font.family stack', () => {
  for (const [name, face] of [
    ['sans', font.face.sans],
    ['display', font.face.display],
    ['mono', font.face.mono],
  ]) {
    const stack = font.family[name]
    const firstName = stack.match(/^'([^']+)'/)?.[1]
    assert.ok(firstName, `font.family.${name} ("${stack}") does not start with a quoted name`)
    assert.strictEqual(
      face.family,
      firstName,
      `font.face.${name}.family ("${face.family}") disagrees with the first name in ` +
        `font.family.${name} ("${firstName}") — a mismatch here is invisible at runtime, the ` +
        'browser silently uses the fallback instead',
    )
  }
})
