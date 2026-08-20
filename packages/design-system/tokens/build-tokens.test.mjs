// Regression tests for the token generator (T016). Runs the real generator against the real JSON
// — there is nothing to fake here, the whole point is that tokens/*.json is the single source of
// truth — then asserts on the files it writes to tokens/generated/.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const tokensDir = path.dirname(fileURLToPath(import.meta.url))
const generatedDir = path.join(tokensDir, 'generated')
const color = JSON.parse(readFileSync(path.join(tokensDir, 'color.json'), 'utf8'))

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
    'elevationTokens',
    'fontTokens',
    'motionTokens',
  ]) {
    assert.match(ts, new RegExp(`export const ${exportName} = {`))
  }
  assert.match(ts, /'accent': 'var\(--ds-color-accent\)',/)
})

// --- Contrast assertions (T034a). These are the pairs the specs' measured-contrast table (DS-1,
// DS-2) names as failing, plus the one this repository decided does not need a token change
// (light `warning`). Each assertion encodes the actual accessibility obligation on that pair —
// not a blanket 4.5:1 — so an edit to color.json is judged the same way T034 judged it.

test('light accent-contrast on accent clears AA normal text (4.5:1) — DS-1, the primary button fill', () => {
  const { accent, 'accent-contrast': accentContrast } = color.light
  const ratio = contrastRatio(accentContrast, accent)
  assert.ok(
    ratio >= 4.5,
    `accent-contrast on accent is ${ratio.toFixed(2)}:1 in the light theme, below the 4.5:1 AA ` +
      'floor a solid primary button with a normal-size label needs',
  )
})

test('light accent-hover and accent-active stay AA and stay distinct from accent and from each other', () => {
  const {
    accent,
    'accent-hover': hover,
    'accent-active': active,
    'accent-contrast': contrast,
  } = color.light
  for (const [name, hex] of [
    ['accent-hover', hover],
    ['accent-active', active],
  ]) {
    const ratio = contrastRatio(contrast, hex)
    assert.ok(ratio >= 4.5, `accent-contrast on ${name} is ${ratio.toFixed(2)}:1, below 4.5:1`)
  }
  // A resting state indistinguishable from its hover state tells a user nothing responded — the
  // whole reason T034a re-derives the pair instead of collapsing rest onto accent-hover.
  assert.notStrictEqual(accent, hover, 'accent and accent-hover must not be the same colour')
  assert.notStrictEqual(hover, active, 'accent-hover and accent-active must not be the same colour')
  assert.notStrictEqual(accent, active, 'accent and accent-active must not be the same colour')
})

test('border-strong clears the 3:1 non-text floor against surface in both themes — DS-2', () => {
  for (const theme of ['light', 'dark']) {
    const { surface, 'border-strong': borderStrong } = color[theme]
    const ratio = contrastRatio(borderStrong, surface)
    assert.ok(
      ratio >= 3,
      `border-strong on surface is ${ratio.toFixed(2)}:1 in the ${theme} theme, below the 3:1 ` +
        'WCAG 1.4.11 floor for the boundary of an interactive control',
    )
  }
})

test('light warning clears the 3:1 non-text floor it actually owes, not 4.5:1', () => {
  // Structural rule from T034: callout body text is always `text-primary`; `warning` only colours
  // the stripe and the heading, both large-text-or-non-text uses. `warning` therefore only ever
  // needs to clear WCAG's 3:1 non-text/large-text floor — asserting 4.5:1 here would encode an
  // obligation this token was never meant to meet (it reaches 4.1:1, deliberately left as-is).
  const { surface, warning } = color.light
  const ratio = contrastRatio(warning, surface)
  assert.ok(
    ratio >= 3,
    `warning on surface is ${ratio.toFixed(2)}:1 in the light theme, below the 3:1 floor it still ` +
      'owes as a stripe/heading colour',
  )
})
