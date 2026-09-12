// T586: guards DS-10's inward-ring geometry (color-tokens.md §5) — no contrast test can see this,
// because `accent-contrast` on `accent` clears 6.07:1 light / 8.07:1 dark regardless of where the
// ring sits on the control; only its *position* decides whether its outer edge touches the page.
// `Button`'s `primary` variant and `DataExportPanel`'s download link both draw `outline-2` at the
// inward `outline-offset-ring-inset` (`border.json`'s `ring-offset-inset`, `-4px`), which leaves a
// 2px band of the control's own fill between the ring and the border box edge — see the second
// guard below for why that band being the *fill* is itself a further assumption, not a given.
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
//
// Width and inward-offset magnitude are read from `border.json` itself, not hard-coded here, so
// this guard cannot silently drift from the token it is checking against.
//
// What neither guard above sees, registered rather than silently assumed complete (adversarial
// review finding S8, 2026-09-12; packages/design-system/specs/README.md's Accessibility mechanism
// gap register carries the open row, owner T590 (to be opened)): a state-variant fill override —
// `hover:bg-*` or `focus-visible:bg-*` changing the fill in the very state the ring paints, which
// neither `checkRingGeometry` nor `checkFillAssumptionFindings` inspects; a background image or
// gradient painted over `bg-accent` instead of a solid override, which `BG_CLIP_RE` and
// `PAINTED_BORDER_COLOR_RE` do not recognise as changing the fill; and an `apps/web` caller passing
// `bg-clip-padding` (or any other fill-defeating class) through `Button`'s merged `className` prop
// — this scan is lexical and reads only `packages/design-system/src`, never a call site outside
// this package.
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
const RING_OFFSET_INSET_MAGNITUDE = Math.abs(
  Number(String(border['ring-offset-inset']).replace('px', '')),
)

const COLOR_RE = /^outline-accent-contrast$/
const WIDTH_RE = /^outline-(\d+)$/
const OFFSET_RE = /^(-?)outline-offset-(\d+)$/
const NAMED_INSET_OFFSET_RE = /^outline-offset-ring-inset$/

// Second guard's shapes (see `checkFillAssumptionFindings` below).
const FILL_TOKEN_RE = /^bg-accent$/
const BG_CLIP_RE = /^bg-clip-(\w+)$/
// A `border-<role>` colour utility — excludes the width token `border-hairline`, the deliberately
// transparent `border-transparent` the geometry relies on, an off-scale numeric width
// (`border-2`, already forbidden elsewhere and not this guard's concern), and the bare directional
// width shorthands (`border-t`/`-r`/`-b`/`-l`/`-x`/`-y`), none of which paint a colour on their own.
const PAINTED_BORDER_COLOR_RE =
  /^border-(?!hairline$)(?!transparent$)(?!\d+$)(?!(?:t|r|b|l|x|y)$)[a-z][a-z0-9-]*$/

// Strips every `variant:` prefix (`focus-visible:`, chained `md:focus-visible:`) from a class
// token, leaving the bare utility — `focus-visible:outline-offset-ring-inset` -> `outline-offset-ring-inset`.
function bareUtility(token) {
  const segments = token.split(':')
  return segments[segments.length - 1]
}

// Evaluates one extracted string literal: does it carry an `outline-accent-contrast` ring, and if
// so, does the width/offset pair in the same string clear the geometric condition?
export function checkRingGeometry(value) {
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
    if (NAMED_INSET_OFFSET_RE.test(bare)) {
      offsetSign = -1
      offsetMagnitude = RING_OFFSET_INSET_MAGNITUDE
      continue
    }
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

// Does this one string literal carry an `outline-accent-contrast` ring at all? (Cheaper than the
// full geometry check above, and used only to decide which files the second guard applies to.)
function hasAccentContrastRingToken(value) {
  return value.split(/\s+/).some((rawToken) => COLOR_RE.test(bareUtility(rawToken)))
}

// Second guard (pre-merge review of PR #74, following T586): `checkRingGeometry` above proves the
// ring's *offset* sits strictly inside its width, which only matters because the 2px band that
// separates the ring from the edge is assumed to be the control's own `accent` fill. That holds
// today only because `background-clip` is left at its default (`border-box`) and the border
// underneath is `border-transparent` — a 0-alpha layer the fill paints straight through. Neither
// of those is asserted anywhere; this closes that gap.
//
// Scoped to the string literal that carries the resting `bg-accent` fill itself (not to every
// literal in a file that happens to ring elsewhere): this codebase's `cx()` calls are frequently
// several independent string-literal arguments rather than one, and a component may legitimately
// paint a *different*, non-transparent border on a variant that does not ring in `accent-contrast`
// at all (`Button`'s `destructive`, `border-danger`, in the same file as `primary`'s ring but a
// different literal and a different fill, `bg-surface`). Tracing which literal actually reaches
// the ringed element at runtime is a data-flow question this lexical scan does not answer
// (token-scale.mjs's own header makes the identical trade-off) — scoping to "the literal that
// declares `bg-accent`" is the closest a text scan gets without it, and matches how both real
// call sites are written today: the fill, its border and its border's colour are declared
// together, in the same literal, as one variant's resting appearance.
function checkFillAssumptionFindings(value) {
  if (!value.split(/\s+/).some((rawToken) => FILL_TOKEN_RE.test(bareUtility(rawToken)))) return []
  const findings = []
  for (const rawToken of value.split(/\s+/).filter(Boolean)) {
    const bare = bareUtility(rawToken)
    const clipMatch = BG_CLIP_RE.exec(bare)
    if (clipMatch && clipMatch[1] !== 'border') {
      findings.push(
        `an accent fill (\`bg-accent\`) painted with \`${rawToken}\` — the inward accent-contrast ` +
          `ring's 2px band is only the fill because background-clip defaults to border-box; a ` +
          `non-border clip makes the band whatever paints underneath instead (\`${value}\`)`,
      )
    }
    if (PAINTED_BORDER_COLOR_RE.test(bare)) {
      findings.push(
        `an accent fill (\`bg-accent\`) paired with a painted border (\`${rawToken}\`) — the inward ` +
          `accent-contrast ring's 2px band is only the fill because the border underneath is ` +
          `\`border-transparent\`; a painted border colour shows through instead (\`${value}\`)`,
      )
    }
  }
  return findings
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

test('the accent-contrast ring band is really the fill: no bg-clip override, no painted border', () => {
  const files = listTsxFiles(srcDir).filter(isScannableFile)
  const findings = []
  let sawRingedFillLiteral = false

  for (const file of files) {
    const source = readFileSync(file, 'utf8')
    const literals = extractStringLiterals(source)
    const fileHasRing = literals.some(({ value }) => hasAccentContrastRingToken(value))
    if (!fileHasRing) continue
    for (const { value, line } of literals) {
      if (!value.split(/\s+/).some((rawToken) => FILL_TOKEN_RE.test(bareUtility(rawToken))))
        continue
      sawRingedFillLiteral = true
      for (const message of checkFillAssumptionFindings(value)) {
        findings.push(`${path.relative(rootDir, file)}:${line}: ${message}`)
      }
    }
  }

  assert.ok(
    sawRingedFillLiteral,
    'scan found zero bg-accent fill literals in a file that also carries an outline-accent-contrast ' +
      'ring — the scan itself is broken (Button primary and DataExportPanel both pair the two), not ' +
      'a real pass',
  )
  assert.deepStrictEqual(findings, [])
})

// --- Unit-level proof that the second guard actually fires (not only that it passes today). ---

test('checkFillAssumptionFindings flags a bg-clip-padding beside an accent fill', () => {
  const findings = checkFillAssumptionFindings(
    'bg-accent bg-clip-padding text-accent-contrast border border-transparent',
  )
  assert.strictEqual(findings.length, 1)
  assert.match(findings[0], /bg-clip-padding/)
})

test('checkFillAssumptionFindings flags a painted border beside an accent fill', () => {
  const findings = checkFillAssumptionFindings(
    'bg-accent text-accent-contrast border border-danger',
  )
  assert.strictEqual(findings.length, 1)
  assert.match(findings[0], /border-danger/)
})

test('checkFillAssumptionFindings passes the real geometry: border-transparent, default background-clip', () => {
  const findings = checkFillAssumptionFindings(
    'bg-accent text-accent-contrast hover:bg-accent-hover active:bg-accent-active border border-transparent',
  )
  assert.deepStrictEqual(findings, [])
})

test('checkFillAssumptionFindings ignores a literal with no bg-accent fill at all', () => {
  const findings = checkFillAssumptionFindings(
    'bg-surface text-danger border border-danger hover:bg-surface-sunken',
  )
  assert.deepStrictEqual(findings, [])
})
