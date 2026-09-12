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
import {
  checkStringLiteral,
  checkFile,
  isScannableFile,
  listTsxFiles,
  checkAppLayoutStringLiteral,
  isClassNameAttributeLiteral,
  checkAppLayoutFile,
} from './token-scale.mjs'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const rootDir = path.resolve(scriptDir, '..', '..')
const srcDir = path.join(rootDir, 'packages', 'design-system', 'src')
const webSrcDir = path.join(rootDir, 'apps', 'web', 'src')

test('a real arbitrary length value fails', () => {
  const findings = checkStringLiteral('h-[1em] w-[1em] shrink-0')
  assert.ok(findings.some((f) => f.includes('arbitrary bracket value') && f.includes('h-[1em]')))
})

test('a viewport-length arbitrary bracket fails (max-h-[80vh])', () => {
  const findings = checkStringLiteral('fixed inset-x-0 bottom-0 max-h-[80vh]')
  assert.ok(
    findings.some((f) => f.includes('arbitrary bracket value') && f.includes('max-h-[80vh]')),
  )
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

// T589 (DS-11): the outline-offset-N namespace carries no unit suffix of its own, so it was
// invisible to the px/rem/ms rule above — this is the regression the checker fix closes, in both
// the outward (positive) and inward (negative) direction.
test('a bare, positive outline-offset-N literal fails, the DS-11 shape the px/rem/ms rule missed', () => {
  const findings = checkStringLiteral(
    'outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring',
  )
  assert.ok(
    findings.some(
      (f) => f.includes('bare outline-offset-<N> literal') && f.includes('outline-offset-2'),
    ),
  )
})

test('a bare, negative -outline-offset-N literal fails the same way', () => {
  const findings = checkStringLiteral(
    'outline-none focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus-ring',
  )
  assert.ok(
    findings.some(
      (f) => f.includes('bare outline-offset-<N> literal') && f.includes('-outline-offset-2'),
    ),
  )
})

test('the named outline-offset-ring / outline-offset-ring-inset-flush utilities pass — only the bare numeral fails', () => {
  assert.deepEqual(
    checkStringLiteral(
      'outline-none focus-visible:outline-2 focus-visible:outline-offset-ring focus-visible:outline-focus-ring',
    ),
    [],
  )
  assert.deepEqual(
    checkStringLiteral(
      'outline-none focus-visible:outline-2 focus-visible:outline-offset-ring-inset-flush focus-visible:outline-focus-ring',
    ),
    [],
  )
})

test('the bracketed arbitrary form (outline-offset-[2px]) is rule 1\'s shape, not rule 4\'s, and still fails — via the bracket rule', () => {
  const findings = checkStringLiteral('focus-visible:outline-offset-[2px]')
  assert.ok(findings.some((f) => f.includes('arbitrary bracket value')))
  assert.ok(!findings.some((f) => f.includes('bare outline-offset-<N> literal')))
})

test("a hand-written var(--ds-*) fails, the check's signature clause (D15)", () => {
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

test('checkFile FAILS on a fixture that writes a bare outline-offset-N literal (T589, DS-11)', () => {
  const findings = checkFile(
    'fixture.tsx',
    `
    export function Widget() {
      return (
        <div
          tabIndex={0}
          className="outline-none focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus-ring"
        />
      )
    }
    `,
  )
  assert.ok(
    findings.some(
      (f) =>
        f.message.includes('bare outline-offset-<N> literal') &&
        f.message.includes('-outline-offset-2'),
    ),
    'expected the fixture\'s own bare -outline-offset-2 to be reported',
  )
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
  assert.ok(
    files.length > 0,
    'expected to find implementation files under packages/design-system/src',
  )

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

// --- T556: the application-authored-layout rule ----------------------------------------------

test('each class quickstart scenario 5 names fails, including variant-prefixed', () => {
  const cases = ['mx-auto', 'max-w-page', 'px-4', 'py-6', 'mt-4', 'gap-3', 'md:px-6', 'hover:mt-2']
  for (const token of cases) {
    const findings = checkAppLayoutStringLiteral(token)
    assert.ok(
      findings.some((f) => f.includes('application-authored layout class') && f.includes(token)),
      `expected \`${token}\` to be reported`,
    )
  }
})

test('a class outside the six named shapes passes the application-layout rule', () => {
  assert.deepEqual(checkAppLayoutStringLiteral('flex items-center gap-x-auto rounded-control'), [])
})

test('isClassNameAttributeLiteral accepts className="..." and the braced literal spelling', () => {
  const doubleQuoted = 'return <div className="mt-4" />'
  assert.equal(isClassNameAttributeLiteral(doubleQuoted, doubleQuoted.indexOf('"')), true)

  const braced = "return <Widget className={'mt-4'} />"
  assert.equal(isClassNameAttributeLiteral(braced, braced.indexOf("'")), true)

  const spaced = 'return <div className = "mt-4" />'
  assert.equal(isClassNameAttributeLiteral(spaced, spaced.indexOf('"')), true)
})

test('isClassNameAttributeLiteral rejects an identifier-referenced class and an unrelated prop', () => {
  // The real shape T558's sweep owns, not this rule (see the file header): a class assigned to a
  // module-scope constant first, only interpolated as `className={sectionClassName}` — no string
  // literal sits in attribute position at all, so there is nothing here to accept or reject; the
  // literal this test does construct is the *constant's own initialiser*, which is not a
  // `className` attribute value either.
  const indirect = "const sectionClassName = 'mt-8 px-4'"
  assert.equal(isClassNameAttributeLiteral(indirect, indirect.indexOf("'")), false)

  const unrelatedProp = 'return <Callout heading="mt-4 is just a heading here" />'
  assert.equal(isClassNameAttributeLiteral(unrelatedProp, unrelatedProp.indexOf('"')), false)
})

test('checkAppLayoutFile FAILS on a fixture that writes application layout — the check has been seen to fail', () => {
  const findings = checkAppLayoutFile(
    'fixture.tsx',
    `
    export function Widget({ error }) {
      return (
        <div className="mt-4">
          <Callout tone="danger">{error}</Callout>
        </div>
      )
    }
    `,
  )
  assert.ok(
    findings.some(
      (f) => f.message.includes('application-authored layout class') && f.message.includes('mt-4'),
    ),
    'expected the fixture\'s own className="mt-4" to be reported',
  )
})

test('checkAppLayoutFile ignores the same class name when it is not a className value', () => {
  const findings = checkAppLayoutFile(
    'fixture.tsx',
    `
    const sectionClassName = 'mt-8 px-4 pb-8 md:px-6'
    export function Widget() {
      return <AnalysisTimeline className={sectionClassName} />
    }
    `,
  )
  // Documents the rule's actual boundary rather than asserting a false negative by accident: the
  // literal here is the constant's initialiser, not a className attribute, so this rule is silent
  // — T558's sweep is where this exact shape gets closed.
  assert.deepEqual(findings, [])
})

test('a clean file with only real, on-scale classes passes the application-layout rule', () => {
  const findings = checkAppLayoutFile(
    'fixture.tsx',
    `
    export function Widget({ className }) {
      return <div className={cx('flex items-center gap-2 rounded-control bg-surface', className)} />
    }
    `,
  )
  assert.deepEqual(findings, [])
})

test('running the application-layout rule against the actual apps/web/src tree is clean', () => {
  const files = listTsxFiles(webSrcDir).filter(isScannableFile)
  assert.ok(files.length > 0, 'expected to find implementation files under apps/web/src')

  const allFindings = []
  for (const file of files) {
    const source = readFileSync(file, 'utf8')
    for (const finding of checkAppLayoutFile(file, source)) {
      allFindings.push(`${path.relative(rootDir, file)}:${finding.line}: ${finding.message}`)
    }
  }

  assert.deepEqual(
    allFindings,
    [],
    'T556 must close every application-authored layout class before this check can pass — see ' +
      'the findings above',
  )
})
