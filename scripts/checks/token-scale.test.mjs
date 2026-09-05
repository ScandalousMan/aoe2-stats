// Regression tests for T527's mechanical check (token-scale.mjs). Follows
// packages/design-system/tokens/build-tokens.test.mjs's own `node --test` conventions: real
// functions, no mocking, `node:assert/strict`. The exported `checkStringLiteral`/`checkFile`
// functions are exercised directly against small fixtures for the shape rules, and the final test
// runs the real check against the real, now-fixed packages/design-system/src tree — the live proof
// that T528's closures are complete and correct.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { checkStringLiteral, checkFile, isScannableFile, listTsxFiles } from './token-scale.mjs'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const rootDir = path.resolve(scriptDir, '..', '..')
const srcDir = path.join(rootDir, 'packages', 'design-system', 'src')

test('a real arbitrary length value fails', () => {
  const findings = checkStringLiteral('h-[1em] w-[1em] shrink-0')
  assert.ok(findings.some((f) => f.includes('arbitrary bracket value') && f.includes('h-[1em]')))
})

test('a viewport-length arbitrary bracket fails (max-h-[80vh])', () => {
  const findings = checkStringLiteral('fixed inset-x-0 bottom-0 max-h-[80vh]')
  assert.ok(findings.some((f) => f.includes('arbitrary bracket value') && f.includes('max-h-[80vh]')))
})

test('an arbitrary animate-[...] value fails on its prefix alone, with no literal duration inside', () => {
  const findings = checkStringLiteral('motion-safe:animate-[spin_1s_linear_infinite]')
  assert.ok(findings.some((f) => f.includes('arbitrary animate-[...] value')))
})

test('an arbitrary animate-[...] value that also hand-writes a var(--ds-*) still fails — the D15 clause wins', () => {
  const findings = checkStringLiteral(
    'motion-safe:animate-[spin_var(--ds-motion-duration-slow)_linear_infinite]',
  )
  assert.ok(findings.some((f) => f.includes('hand-written var(--ds-*)')))
})

test('a real hex literal fails, inside a bracket and bare in a string', () => {
  const bracketed = checkStringLiteral('bg-[#a1b2c3]')
  assert.ok(bracketed.some((f) => f.includes('arbitrary bracket value')))

  const bare = checkStringLiteral('a stray #a1b2c3 typed by mistake')
  assert.ok(bare.some((f) => f.includes('raw hex colour literal')))
})

test('a bare px/rem/ms literal fails outside any bracket', () => {
  const findings = checkStringLiteral('a stray 14px typed by mistake in a template string')
  assert.ok(findings.some((f) => f.includes('raw px/rem/ms literal')))
})

test('a hand-written var(--ds-*) fails, the check\'s signature clause (D15)', () => {
  const findings = checkStringLiteral('h-[var(--ds-icon-2xl)] w-[var(--ds-icon-2xl)]')
  assert.ok(findings.some((f) => f.includes('hand-written var(--ds-*)')))
})

test('an allowlisted transition-[fill,opacity] property list passes', () => {
  const findings = checkStringLiteral(
    'h-[1em] w-[1em] shrink-0 transition-[fill,opacity] duration-120 ease-standard',
  )
  // The two `[1em]` brackets still fail; the transition property list must not add a third.
  const transitionFindings = findings.filter((f) => f.includes('transition'))
  assert.deepEqual(transitionFindings, [])
})

test('an allowlisted [overflow-wrap:anywhere] bracket passes', () => {
  const findings = checkStringLiteral(
    'whitespace-normal break-words font-mono text-sm [overflow-wrap:anywhere]',
  )
  assert.deepEqual(findings, [])
})

test('a [color:red]-shaped keyword-colour bracket fails — the allowlist must not over-admit', () => {
  const findings = checkStringLiteral('[color:red]')
  assert.ok(findings.some((f) => f.includes('colour-bearing property')))
})

test('a [background-color:red] bracket fails the same way, by property name rather than value', () => {
  const findings = checkStringLiteral('[background-color:red]')
  assert.ok(findings.some((f) => f.includes('colour-bearing property')))
})

test('an arbitrary Tailwind variant selector, e.g. [&>button]:min-w-0, is not a value and passes', () => {
  const findings = checkStringLiteral('!flex min-w-0 [&>button]:min-w-0 [&>button]:px-3')
  assert.deepEqual(findings, [])
})

test('a clean file with only real utility classes passes', () => {
  const findings = checkFile(
    'fixture.tsx',
    `
    export function Widget({ className }) {
      return <div className={cx('flex items-center gap-2 rounded-control bg-surface', className)} />
    }
    `,
  )
  assert.deepEqual(findings, [])
})

test('comments are never scanned, even when they mention a forbidden shape as history', () => {
  const findings = checkFile(
    'fixture.tsx',
    `
    // T528 closed 'h-[1em]' and 'h-[var(--ds-icon-2xl)]' here — both historical, in a comment.
    /* max-h-[80vh] is also mentioned here, in a block comment. */
    export function Widget() {
      return <div className="icon-sm" />
    }
    `,
  )
  assert.deepEqual(findings, [])
})

test('isScannableFile excludes stories and tests, which carry no component style of their own', () => {
  assert.equal(isScannableFile('/x/Widget/index.tsx'), true)
  assert.equal(isScannableFile('/x/Widget/Widget.stories.tsx'), false)
  assert.equal(isScannableFile('/x/Widget/Widget.test.tsx'), false)
})

test('running the check against the actual, now-fixed packages/design-system/src tree is clean', () => {
  const files = listTsxFiles(srcDir).filter(isScannableFile)
  assert.ok(files.length > 0, 'expected to find implementation files under packages/design-system/src')

  const allFindings = []
  for (const file of files) {
    const source = readFileSync(file, 'utf8')
    for (const finding of checkFile(file, source)) {
      allFindings.push(`${path.relative(rootDir, file)}:${finding.line}: ${finding.message}`)
    }
  }

  assert.deepEqual(
    allFindings,
    [],
    'T528 must close every off-scale value before this check can pass — see the findings above',
  )
})
