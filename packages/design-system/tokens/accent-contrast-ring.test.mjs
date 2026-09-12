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
// gap register carried this as an open row, item 2, owner T590): a state-variant fill override —
// `hover:bg-*` or `focus-visible:bg-*` changing the fill in the very state the ring paints, which
// neither `checkRingGeometry` nor `checkFillAssumptionFindings` inspects; a background image or
// gradient painted over `bg-accent` instead of a solid override, which `BG_CLIP_RE` and
// `PAINTED_BORDER_COLOR_RE` do not recognise as changing the fill; and an `apps/web` caller passing
// `bg-clip-padding` (or any other fill-defeating class) through `Button`'s merged `className` prop
// — this scan is lexical and reads only `packages/design-system/src`, never a call site outside
// this package.
//
// T590 closed the first two of those three and left the third open, on purpose:
//
// - **State-variant fill override — closed.** `checkStateFillAndImageFindings` below now treats
//   any variant-prefixed `bg-<colour>` utility beside a resting `bg-accent` fill as a finding
//   unless the colour it repaints onto is one DS-10's own contrast proof already covers —
//   `accent`, `accent-hover` or `accent-active` (`build-tokens.test.mjs` asserts `accent-contrast`
//   clears 4.5:1 against all three). `:active` and `:focus-visible` genuinely coincide (a keyboard
//   `Enter` press, per `Button/index.tsx`'s own `active:ring-2` comment), so a prefix is not
//   excluded just because it names a different pseudo-class than `:focus-visible` itself — the
//   ring's own state and a fill override's state do not have to be textually identical to overlap
//   at runtime. Checked against T588's landing (`Button`'s `hover:bg-accent-hover` /
//   `active:bg-accent-active`, present before T588 and untouched by it): both targets are on the
//   ramp, so this guard passes them and would have caught it had T588 instead swapped either to an
//   unproven colour.
// - **Background image or gradient over `bg-accent` — closed.** The same function's `BG_IMAGE_RE`/
//   `BG_ARBITRARY_VALUE_RE` branch catches a gradient or bracketed background-image utility beside
//   `bg-accent`, state-prefixed or not — a `background-image` layer paints over
//   `background-color` rather than replacing it, so `bg-accent`'s mere presence in the same class
//   list proves nothing once one of these sits beside it.
// - **An `apps/web` caller's `className` — deliberately left open.** Closing this needs one of two
//   things this file does not do today: a second lexical pass over `apps/web/src` for a
//   fill-defeating class reaching a `Button`/download-link call site (a real, separate scan, the
//   same shape `token-scale.mjs`'s own T556 addition already uses for its unrelated
//   application-layout rule — over a different tree, checking a different property), or a runtime
//   assertion (render the composed class list and inspect the resolved `background-image`/
//   `background-clip` computed style, which needs a real layout engine jsdom does not have,
//   `packages/design-system/src/test/axe.ts`'s own scoping note makes the identical trade-off for
//   `color-contrast`). Either is a defensible next step *if* a real instance of this ever ships;
//   writing it speculatively, before one has, would blur this token-level test's boundary — the
//   design system's own contract — with call-site linting over application code, which is what
//   `token-scale.mjs`'s existing `apps/web` pass already owns as a separate, independently-run
//   check over its own tree. Recorded here rather than silently dropped: `Button`'s `className`
//   prop is merged last (`packages/design-system/src/primitives/Button/index.tsx`'s
//   `cx(..., className)`), so nothing in this package stops a caller from winning the cascade.
//
// The grouping the two closed checks below scan over is `cx()` calls, not single string literals
// like the second guard above: `Button`'s variant record keeps one variant's fill, border and
// states in a single string, but `DataExportPanel`'s download link threads the resting fill and
// its `hover:`/`active:` overrides through three independent string arguments of the *same*
// `cx(...)` call — a same-literal scope would never see that real shape's overrides at all. A
// `cx()` call's combined argument list is the closest a text scan gets to "the classes actually
// applied to this element" without tracing which literal reaches which JSX attribute at runtime,
// the identical trade-off `checkFillAssumptionFindings`'s own header already makes for scoping to
// one literal instead of a whole file.
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

// Third guard's shapes (T590). Fills this scan treats as already contrast-proven for
// `accent-contrast` — the ramp `build-tokens.test.mjs` asserts clears 4.5:1 end to end. A
// state-variant fill override is only as safe as the token it repaints onto, so a variant that
// swaps to anything outside this set has not been proven and must be caught, not assumed fine
// merely because it "just" changes colour.
const SAFE_ACCENT_RAMP_FILLS = new Set(['accent', 'accent-hover', 'accent-active'])

// A `bg-<colour>` utility, resting or variant-prefixed alike (`bareUtility` above already strips
// any variant prefix before this runs). Excludes every non-colour `bg-*` family Tailwind ships —
// `bg-clip-*` (the first guard's own concern, not this one's), `bg-origin-*`, `bg-repeat*`,
// `bg-fixed`/`bg-local`/`bg-scroll`, `bg-auto`/`bg-cover`/`bg-contain`, the position keywords
// (`bg-top`/`-bottom`/`-left`/`-right`/`-center`), `bg-blend-*`, and the gradient/image families
// (`bg-gradient-*`/`bg-linear-*`/`bg-radial*`/`bg-conic*`), which `BG_IMAGE_RE` below governs
// instead — none of these paints a colour on its own, the same reasoning
// `PAINTED_BORDER_COLOR_RE` above applies to `border-*`.
const BG_COLOR_UTILITY_RE =
  /^bg-(?!clip-)(?!origin-)(?!repeat)(?!no-repeat$)(?!fixed$)(?!local$)(?!scroll$)(?!auto$)(?!cover$)(?!contain$)(?!none$)(?!top$)(?!bottom$)(?!left$)(?!right$)(?!center$)(?!blend-)(?!gradient-)(?!linear-)(?!radial)(?!conic)([a-z][a-z0-9-]*)$/

// A background-*image* utility — Tailwind's gradient family — or an arbitrary bracketed
// background value (`bg-[url(...)]`, `bg-[linear-gradient(...)]`). Either paints *over*
// `background-color` without replacing it, so a literal can carry both `bg-accent` and one of
// these at once and still show something other than the fill underneath the ring — `BG_CLIP_RE`/
// `PAINTED_BORDER_COLOR_RE` above only reason about what shows *through* a transparent layer,
// never about a second image painted on top. `bg-none` is deliberately excluded: it *clears* a
// background image rather than adding one, so it is never a hazard.
const BG_IMAGE_RE =
  /^bg-(?:gradient-to-\w+|linear-to-\w+|linear-\d+|radial(?:-\w+)?|conic(?:-\w+)?)$/
const BG_ARBITRARY_VALUE_RE = /^bg-\[.+\]$/

// The variant prefix immediately before a class token's bare utility (`hover`, `focus-visible`,
// the last segment before the utility itself in a chained prefix like `md:focus-visible:bg-x`) —
// `null` for an unprefixed, resting-state token.
function variantPrefix(token) {
  const segments = token.split(':')
  return segments.length > 1 ? segments[segments.length - 2] : null
}

// Does this one `cx()`-call group (an array of `{ value, line }` literals) carry an unprefixed,
// resting `bg-accent` fill anywhere in it? Shared between the finder below and the test's own
// zero-groups sanity check.
function groupHasRestingAccentFill(groupLiterals) {
  return groupLiterals.some(({ value }) =>
    value
      .split(/\s+/)
      .some(
        (rawToken) => FILL_TOKEN_RE.test(bareUtility(rawToken)) && variantPrefix(rawToken) === null,
      ),
  )
}

// Evaluates one `cx()`-call group: does it carry a resting `bg-accent` fill, and if so, does any
// token anywhere in the group's literals repaint or overpaint it unsafely? See the file header for
// why this is grouped by `cx()` call rather than by single literal like the second guard above.
function checkStateFillAndImageFindings(groupLiterals) {
  if (!groupHasRestingAccentFill(groupLiterals)) return []
  const findings = []
  for (const { value, line } of groupLiterals) {
    for (const rawToken of value.split(/\s+/).filter(Boolean)) {
      const bare = bareUtility(rawToken)
      if (BG_IMAGE_RE.test(bare) || BG_ARBITRARY_VALUE_RE.test(bare)) {
        findings.push({
          line,
          message:
            `a background-image utility (\`${rawToken}\`) alongside an accent fill (\`bg-accent\`) ` +
            `— it paints over background-color rather than replacing it, so the inward ` +
            `accent-contrast ring's 2px band is no longer provably the fill: \`${value}\``,
        })
        continue
      }
      const prefix = variantPrefix(rawToken)
      if (!prefix) continue
      const colorMatch = BG_COLOR_UTILITY_RE.exec(bare)
      if (colorMatch && !SAFE_ACCENT_RAMP_FILLS.has(colorMatch[1])) {
        findings.push({
          line,
          message:
            `a \`${prefix}\`-scoped fill override (\`${rawToken}\`) beside an accent fill ` +
            `(\`bg-accent\`) — \`:${prefix}\` can coincide with \`:focus-visible\` (a keyboard ` +
            `press, or a mouse hover while keyboard-focused), and \`${colorMatch[1]}\` is not one ` +
            `of the accent-ramp fills (\`accent\`, \`accent-hover\`, \`accent-active\`) DS-10's ` +
            `contrast proof already covers: \`${value}\``,
        })
      }
    }
  }
  return findings
}

// Blanks every comment and string-literal *content* in `source`, preserving length and every
// non-string, non-comment character (including newlines) untouched, so a paren inside a comment or
// a class string (this codebase writes none, but the principle matches `extractStringLiterals`'s
// own template-literal case) never desyncs a paren count run over the result. Reuses
// `extractStringLiterals`'s three lexer cases (line comment, block comment, string literal) —
// blanking instead of extracting — rather than re-deriving them; `token-scale.mjs` does not export
// a masking primitive, only extraction, so this is the smallest local addition that reuses its
// logic without duplicating its literal-extraction path.
function maskCommentsAndStrings(source) {
  let masked = ''
  let i = 0
  const n = source.length
  while (i < n) {
    const ch = source[i]
    if (ch === '/' && source[i + 1] === '/') {
      while (i < n && source[i] !== '\n') {
        masked += ' '
        i++
      }
      continue
    }
    if (ch === '/' && source[i + 1] === '*') {
      masked += '  '
      i += 2
      while (i < n && !(source[i] === '*' && source[i + 1] === '/')) {
        masked += source[i] === '\n' ? '\n' : ' '
        i++
      }
      masked += '  '
      i += 2
      continue
    }
    if (ch === '`' || ch === "'" || ch === '"') {
      const quote = ch
      masked += ' '
      i++
      while (i < n && source[i] !== quote) {
        if (source[i] === '\\') {
          masked += '  '
          i += 2
          continue
        }
        masked += source[i] === '\n' ? '\n' : ' '
        i++
      }
      masked += ' '
      i++
      continue
    }
    masked += ch
    i++
  }
  return masked
}

// Every `cx(...)` call's argument span in `source`, as `[start, end)` character offsets into the
// *original* source (`end` exclusive, at the matching close paren) — comparable directly against
// `extractStringLiterals`'s own `start`. Matched against `maskCommentsAndStrings`'s output so a
// paren inside a comment or a string never miscounts the depth.
function findCxCallRanges(source) {
  const masked = maskCommentsAndStrings(source)
  const ranges = []
  const callRe = /\bcx\(/g
  let match
  while ((match = callRe.exec(masked))) {
    const openIndex = match.index + match[0].length - 1
    let depth = 1
    let j = openIndex + 1
    while (j < masked.length && depth > 0) {
      if (masked[j] === '(') depth++
      else if (masked[j] === ')') depth--
      j++
    }
    ranges.push([openIndex, j])
  }
  return ranges
}

// Groups `literals` (as returned by `extractStringLiterals`) by which `cx()` call in `source` each
// one's opening quote falls inside — a literal outside every `cx()` call range (a bare
// `className="..."`, or a module-scope constant) is its own singleton group instead, matching the
// second guard's same-literal scope for exactly the shape it already covers correctly (`Button`'s
// per-variant record entries, none of which are themselves wrapped in a `cx()` call).
function groupLiteralsByCxCall(source, literals) {
  const ranges = findCxCallRanges(source)
  const groups = new Map()
  for (const literal of literals) {
    const rangeIndex = ranges.findIndex(
      ([start, end]) => literal.start >= start && literal.start < end,
    )
    const key = rangeIndex === -1 ? `standalone:${literal.start}` : `cx:${rangeIndex}`
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(literal)
  }
  return [...groups.values()]
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

test('the accent-contrast ring band cannot be repainted by a state variant or a background image (T590)', () => {
  const files = listTsxFiles(srcDir).filter(isScannableFile)
  const findings = []
  let sawGroupWithRestingAccentFill = false

  for (const file of files) {
    const source = readFileSync(file, 'utf8')
    const literals = extractStringLiterals(source)
    const fileHasRing = literals.some(({ value }) => hasAccentContrastRingToken(value))
    if (!fileHasRing) continue
    for (const group of groupLiteralsByCxCall(source, literals)) {
      if (groupHasRestingAccentFill(group)) sawGroupWithRestingAccentFill = true
      for (const { line, message } of checkStateFillAndImageFindings(group)) {
        findings.push(`${path.relative(rootDir, file)}:${line}: ${message}`)
      }
    }
  }

  assert.ok(
    sawGroupWithRestingAccentFill,
    'scan found zero cx()-call groups carrying a resting bg-accent fill in a file that also ' +
      'carries an outline-accent-contrast ring — the scan itself is broken (Button primary and ' +
      "DataExportPanel's download link both pair the two), not a real pass",
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

// --- Unit-level proof that the third guard (T590) actually fires, not only that it passes today. ---

test('checkStateFillAndImageFindings flags a hover fill override off the accent ramp', () => {
  const findings = checkStateFillAndImageFindings([
    { value: 'bg-accent text-accent-contrast hover:bg-danger border border-transparent', line: 1 },
  ])
  assert.strictEqual(findings.length, 1)
  assert.match(findings[0].message, /hover.*bg-danger/s)
})

test('checkStateFillAndImageFindings flags a focus-visible fill override off the accent ramp', () => {
  const findings = checkStateFillAndImageFindings([
    {
      value: 'bg-accent text-accent-contrast focus-visible:bg-surface border border-transparent',
      line: 1,
    },
  ])
  assert.strictEqual(findings.length, 1)
  assert.match(findings[0].message, /focus-visible.*bg-surface/s)
})

test('checkStateFillAndImageFindings flags a gradient painted over the accent fill', () => {
  const findings = checkStateFillAndImageFindings([
    {
      value: 'bg-accent bg-gradient-to-r text-accent-contrast border border-transparent',
      line: 1,
    },
  ])
  assert.strictEqual(findings.length, 1)
  assert.match(findings[0].message, /bg-gradient-to-r/)
})

test('checkStateFillAndImageFindings flags an arbitrary background-image value over the accent fill', () => {
  const findings = checkStateFillAndImageFindings([
    {
      value: "bg-accent bg-[url('/noise.png')] text-accent-contrast border border-transparent",
      line: 1,
    },
  ])
  assert.strictEqual(findings.length, 1)
  assert.match(findings[0].message, /noise\.png/)
})

test('checkStateFillAndImageFindings passes the real geometry across a cx()-style group of literals', () => {
  const findings = checkStateFillAndImageFindings([
    { value: 'bg-accent text-accent-contrast', line: 1 },
    { value: 'hover:bg-accent-hover active:bg-accent-active', line: 2 },
    { value: 'outline-none focus-visible:outline-2 focus-visible:outline-accent-contrast', line: 3 },
  ])
  assert.deepStrictEqual(findings, [])
})

test('checkStateFillAndImageFindings ignores a group with no resting bg-accent fill at all', () => {
  const findings = checkStateFillAndImageFindings([
    { value: 'bg-surface text-danger border border-danger', line: 1 },
    { value: 'hover:bg-surface-sunken active:bg-background', line: 2 },
  ])
  assert.deepStrictEqual(findings, [])
})

// --- Proof that the grouping itself (by cx() call, not by single literal) does what the header
// claims: it must see a state override that DataExportPanel's own shape splits across two
// arguments of one cx() call, which a same-literal scope would silently miss. ---

test('groupLiteralsByCxCall folds one cx() call\'s several string arguments into a single group', () => {
  const source = `
    const classes = cx(
      'bg-accent text-accent-contrast',
      'hover:bg-danger',
      'outline-none focus-visible:outline-2 focus-visible:outline-accent-contrast',
    )
  `
  const literals = extractStringLiterals(source)
  const groups = groupLiteralsByCxCall(source, literals)
  assert.strictEqual(groups.length, 1)
  assert.strictEqual(groups[0].length, 3)

  const findings = checkStateFillAndImageFindings(groups[0])
  assert.strictEqual(findings.length, 1)
  assert.match(findings[0].message, /hover.*bg-danger/s)
})

test('groupLiteralsByCxCall keeps literals outside any cx() call as their own singleton groups', () => {
  const source = `
    const variantClasses = {
      primary: 'bg-accent hover:bg-accent-hover',
      destructive: 'bg-surface hover:bg-surface-sunken',
    }
  `
  const literals = extractStringLiterals(source)
  const groups = groupLiteralsByCxCall(source, literals)
  assert.strictEqual(groups.length, 2)
  assert.ok(groups.every((group) => group.length === 1))

  const allFindings = groups.flatMap((group) => checkStateFillAndImageFindings(group))
  assert.deepStrictEqual(
    allFindings,
    [],
    'a same-file, different-variant hover override must never be attributed to an unrelated ' +
      'accent fill just because both live in the same file',
  )
})
