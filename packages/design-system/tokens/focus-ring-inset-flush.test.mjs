// T589 (DS-11): guards the geometry of `border.json`'s `ring-offset-inset-flush` (-2px), the
// token admitted for `MatchRow`, `FavouritesList`, `PlayerResultRow` and one of `Menu`'s three
// rings — the equivalent of what `accent-contrast-ring.test.mjs` already does for T586's
// `ring-offset-inset` (-4px), scoped to the different colour role and the different geometric
// contract this token satisfies.
//
// `ring-offset-inset` (T586) and `ring-offset-inset-flush` (T589) are both inward offsets on the
// same `outline-offset` property, but they are not interchangeable and this guard is why a
// contrast test cannot see either: `ring-offset-inset` rings in `outline-accent-contrast` against
// a control's own `accent` fill, where the inward magnitude must *strictly exceed* the ring's own
// width so a band of the fill separates the ring from the page (`color-tokens.md` §5,
// `accent-contrast-ring.test.mjs`). `ring-offset-inset-flush` rings in the ordinary
// `outline-focus-ring` role against a row or menu item's own edge, where the only requirement is
// that the ring never crops the row's content or bleeds into a sibling row — so the offset sits
// exactly flush with the edge, magnitude *equal to* (not exceeding) the ring's width, and its
// adjacency is never an `accent` fill at all. A ring painted with `outline-focus-ring` and this
// named flush token, but at a magnitude that does not match the ring's own width, would open a
// visible gap or an unintended overlap — this guard is what would catch that drift, since neither
// `token-scale.mjs` (which only forbids the bare literal, not a mismatched named one) nor a
// contrast test (`focus-ring` already clears 3:1 on every page surface regardless of position) can
// see it.
//
// Scans every non-test, non-story `.tsx` source file under `packages/design-system/src` — not
// only the four known call sites — for the named `outline-offset-ring-inset-flush` utility, and
// fails, naming file and line, unless the same class string also carries `outline-focus-ring` (the
// only ring colour this token is admitted for) and the magnitude `border.json` declares for it
// equals the magnitude `border.json` declares for `ring` (the flush condition itself). Reuses
// `token-scale.mjs`'s file discovery and comment/template-stripping string-literal extraction,
// the same infrastructure `accent-contrast-ring.test.mjs` reuses.
//
// Also fails if the scan finds zero `outline-offset-ring-inset-flush` rings, so a broken scan (a
// lexer change, a renamed token) can never pass vacuously — it must find the real call sites and
// prove their geometry, not merely find nothing wrong.
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

const border = JSON.parse(readFileSync(path.join(tokensDir, 'border.json'), 'utf8'))
const RING_WIDTH = Number(String(border.ring).replace('px', ''))
const RING_OFFSET_INSET_FLUSH_MAGNITUDE = Math.abs(
  Number(String(border['ring-offset-inset-flush']).replace('px', '')),
)

const FOCUS_RING_COLOR_RE = /^outline-focus-ring$/
const FLUSH_OFFSET_RE = /^outline-offset-ring-inset-flush$/

// Strips every `variant:` prefix, the same helper `accent-contrast-ring.test.mjs` defines —
// duplicated rather than imported because neither file exports it and each stays a self-contained
// proof of its own token, the same reason the two files do not share a colour-role assumption.
function bareUtility(token) {
  const segments = token.split(':')
  return segments[segments.length - 1]
}

// Evaluates one extracted string literal: does it carry the named flush offset, and if so, does
// it pair with the one ring colour this token is admitted for, at the magnitude the flush
// condition requires?
export function checkFlushRingGeometry(value) {
  const tokens = value.split(/\s+/).filter(Boolean)
  let hasFlushOffset = false
  let hasFocusRingColor = false
  for (const rawToken of tokens) {
    const bare = bareUtility(rawToken)
    if (FLUSH_OFFSET_RE.test(bare)) hasFlushOffset = true
    if (FOCUS_RING_COLOR_RE.test(bare)) hasFocusRingColor = true
  }
  if (!hasFlushOffset) return { hasFlushOffset: false, message: null }
  if (!hasFocusRingColor) {
    return {
      hasFlushOffset: true,
      message:
        `outline-offset-ring-inset-flush paired with no outline-focus-ring in the same class ` +
        `string — this token is admitted only for the ordinary focus-ring role, never for an ` +
        `accent-filled control (that geometry is ring-offset-inset, T586): \`${value}\``,
    }
  }
  if (RING_OFFSET_INSET_FLUSH_MAGNITUDE !== RING_WIDTH) {
    return {
      hasFlushOffset: true,
      message:
        `border.json's ring-offset-inset-flush (${RING_OFFSET_INSET_FLUSH_MAGNITUDE}px) no longer ` +
        `equals ring (${RING_WIDTH}px) — the flush condition this token names (offset magnitude ` +
        `equal to the ring's own width, so the ring sits exactly at the edge with no gap and no ` +
        `overlap) no longer holds: \`${value}\``,
    }
  }
  return { hasFlushOffset: true, message: null }
}

test('every outline-offset-ring-inset-flush ring pairs with outline-focus-ring and sits exactly flush with the edge', () => {
  const files = listTsxFiles(srcDir).filter(isScannableFile)
  const findings = []
  let sawFlushOffset = false

  for (const file of files) {
    const source = readFileSync(file, 'utf8')
    for (const { value, line } of extractStringLiterals(source)) {
      const { hasFlushOffset, message } = checkFlushRingGeometry(value)
      if (hasFlushOffset) sawFlushOffset = true
      if (message) findings.push(`${path.relative(rootDir, file)}:${line}: ${message}`)
    }
  }

  assert.ok(
    sawFlushOffset,
    'scan found zero outline-offset-ring-inset-flush rings under packages/design-system/src — ' +
      'the scan itself is broken (DS-11 still applies to MatchRow, FavouritesList, ' +
      'PlayerResultRow and one of Menu\'s three rings), not a real pass',
  )
  assert.deepStrictEqual(findings, [])
})

// --- Unit-level proof that the guard actually fires (not only that it passes today). ---

test('checkFlushRingGeometry flags the flush offset paired with a different ring colour', () => {
  const findings = checkFlushRingGeometry(
    'outline-none focus-visible:outline-2 focus-visible:outline-offset-ring-inset-flush focus-visible:outline-accent-contrast',
  )
  assert.strictEqual(findings.hasFlushOffset, true)
  assert.match(findings.message, /paired with no outline-focus-ring/)
})

test('checkFlushRingGeometry passes the real geometry: the flush offset beside outline-focus-ring', () => {
  const findings = checkFlushRingGeometry(
    'outline-none focus-visible:outline-2 focus-visible:outline-offset-ring-inset-flush focus-visible:outline-focus-ring',
  )
  assert.strictEqual(findings.hasFlushOffset, true)
  assert.strictEqual(findings.message, null)
})

test('checkFlushRingGeometry ignores a literal with no flush offset at all', () => {
  const findings = checkFlushRingGeometry(
    'outline-none focus-visible:outline-2 focus-visible:outline-offset-ring focus-visible:outline-focus-ring',
  )
  assert.strictEqual(findings.hasFlushOffset, false)
  assert.strictEqual(findings.message, null)
})
