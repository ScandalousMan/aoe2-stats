// T586: guards DS-10's inward-ring geometry (color-tokens.md §5) — no contrast test can see this,
// because `accent-contrast` on `accent` clears 6.07:1 light / 8.07:1 dark regardless of where the
// ring sits on the control; only its *position* decides whether its outer edge touches the page.
// `Button`'s `primary` variant and `DataExportPanel`'s download link both draw `outline-2` at
// `-outline-offset-2`, which fills exactly the outermost two pixels of the border box — flush with
// the edge, so the ring's outer side sat on the page at 1.00-1.42:1, the same invisible-on-the-page
// defect §5 exists to prevent, in a new direction.
//
// Scans every non-test, non-story `.tsx` source file under `packages/design-system/src` — not only
// the two files above — for any class string pairing an `outline-accent-contrast` ring colour with
// an outline width and offset in the same string, and fails, naming file and line, unless the
// offset is inward (negative) and its magnitude strictly exceeds the width, the condition
// `color-tokens.md` §5 states next to the rule. Reuses `token-scale.mjs`'s file discovery and
// comment/template-stripping string-literal extraction rather than re-implementing a lexer (same
// non-story/non-test exclusion and the same rationale for it).
//
// Scanning the whole source tree, not just the two known files, is deliberate: the sibling lesson
// this task was written about (see tasks.md T586) is that the flush-with-the-edge defect sat in
// two files and the review that found it originally named only one. A third accent-filled control
// added later must be covered here without anyone opting it in.
//
// Also fails if the scan finds zero `outline-accent-contrast` rings, so a broken scan (a lexer
// change, a renamed token) can never pass vacuously — it must find the two real rings and prove
// their geometry, not merely find nothing wrong.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  listTsxFiles,
  isScannableFile,
  extractStringLiterals,
} from '../../../scripts/checks/token-scale.mjs'

const tokensDir = path.dirname(fileURLToPath(import.meta.url))
const rootDir = path.resolve(tokensDir, '..', '..', '..')
const srcDir = path.resolve(tokensDir, '..', 'src')

const COLOR_RE = /^outline-accent-contrast$/
const WIDTH_RE = /^outline-(\d+)$/
const OFFSET_RE = /^(-?)outline-offset-(\d+)$/

// Strips every `variant:` prefix (`focus-visible:`, chained `md:focus-visible:`) from a class
// token, leaving the bare utility — `focus-visible:-outline-offset-4` -> `-outline-offset-4`.
function bareUtility(token) {
  const segments = token.split(':')
  return segments[segments.length - 1]
}

// Evaluates one extracted string literal: does it carry an `outline-accent-contrast` ring, and if
// so, does the width/offset pair in the same string clear the geometric condition?
function checkRingGeometry(value) {
  const tokens = value.split(/\s+/).filter(Boolean)
  let hasAccentContrastRing = false
  let width = null
  let offsetSign = null
  let offsetMagnitude = null
  for (const rawToken of tokens) {
    const bare = bareUtility(rawToken)
    if (COLOR_RE.test(bare)) hasAccentContrastRing = true
    const widthMatch = WIDTH_RE.exec(bare)
    if (widthMatch) width = Number(widthMatch[1])
    const offsetMatch = OFFSET_RE.exec(bare)
    if (offsetMatch) {
      offsetSign = offsetMatch[1] === '-' ? -1 : 1
      offsetMagnitude = Number(offsetMatch[2])
    }
  }
  if (!hasAccentContrastRing) return { hasAccentContrastRing: false, message: null }
  if (width === null || offsetMagnitude === null) {
    return {
      hasAccentContrastRing: true,
      message: `an outline-accent-contrast ring with no matching outline width/offset pair in the same class string: \`${value}\``,
    }
  }
  if (offsetSign !== -1 || offsetMagnitude <= width) {
    return {
      hasAccentContrastRing: true,
      message:
        `an outline-accent-contrast ring whose offset (${offsetSign === -1 ? '-' : ''}${offsetMagnitude}px) ` +
        `does not sit strictly inside its ${width}px width — the ring touches the control's edge ` +
        `(color-tokens.md §5 requires the inward offset to strictly exceed the width): \`${value}\``,
    }
  }
  return { hasAccentContrastRing: true, message: null }
}

test('every accent-contrast focus ring sits strictly inside its control, never flush with the edge', () => {
  const files = listTsxFiles(srcDir).filter(isScannableFile)
  const findings = []
  let sawAccentContrastRing = false

  for (const file of files) {
    const source = readFileSync(file, 'utf8')
    for (const { value, line } of extractStringLiterals(source)) {
      const { hasAccentContrastRing, message } = checkRingGeometry(value)
      if (hasAccentContrastRing) sawAccentContrastRing = true
      if (message) findings.push(`${path.relative(rootDir, file)}:${line}: ${message}`)
    }
  }

  assert.ok(
    sawAccentContrastRing,
    'scan found zero outline-accent-contrast rings under packages/design-system/src — the scan ' +
      'itself is broken (DS-10 still applies to Button primary and DataExportPanel), not a real pass',
  )
  assert.deepStrictEqual(findings, [])
})
