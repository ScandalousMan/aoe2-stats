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
