#!/usr/bin/env node
// T527: the mechanical check FR-062 and research D15 ask for. It reads every `.tsx` file under
// `packages/design-system/src/` (components and `lib/`) and fails on three shapes:
//   1. An arbitrary bracket value carrying a length, a colour, a duration or a shadow — a Tailwind
//      utility of the form `<prefix>-[<value>]` where `<value>` is a length (em/rem/px/vh/vw/%), a
//      colour (#hex, rgb(), rgba(), hsl()), or a duration/animation the utility vocabulary
//      (contracts/token-families.md §2) already has a real class for.
//   2. A raw hex colour literal, or a bare `px`/`rem`/`ms` numeric literal, anywhere in a scanned
//      string — not only inside a bracket. `em`, `vh`, `vw` and `%` are covered by rule 1's bracket
//      scan (Tailwind never emits them unbracketed) rather than repeated here.
//   3. A hand-written `var(--ds-*)` inside a class name or bracket — e.g. `h-[var(--ds-icon-2xl)]`.
//      This is the check's signature clause (D15): the value is token-derived and still a defect,
//      because it means the utility vocabulary has a hole a check hunting only for raw values would
//      never find.
//
// Allowlisted shapes — not values, each named here with why (no separate allowlist file exists;
// unlike a11y-allowlist.mjs, these are shapes true everywhere in the codebase, not per-file
// exceptions):
//   - `transition-[…]` where the bracket holds only a comma-separated list of CSS property names
//     (`transition-[fill,opacity]`). Naming *which properties* transition is not a decision about a
//     value.
//   - A bracket declaring a CSS property with no design-token concern, shaped `[property:keyword]`
//     — the contract's own example is `[overflow-wrap:anywhere]`. Narrowly: the keyword after the
//     colon must not itself be a value, and `color`/`background-color`/`border-color`/`fill`/
//     `stroke` (any property whose own name says it paints something) is never allowlisted this
//     way regardless of what the keyword looks like — `[color:red]` still fails, because colour is
//     always a design decision, never a "no decision" keyword.
//
// Scope and method. This repository's other source checks (a11y-allowlist.mjs, built-css.mjs,
// spa-routing.mjs) all favour a straightforward text scan over a full TypeScript AST, and this one
// does the same, for the same reason: the shapes above are lexical, not structural. It strips line
// and block comments, skips template literals entirely (a grep across the package confirms no
// `className`/`cx()` argument in this codebase is ever a template literal, so there is nothing
// there to miss), then extracts every single- or double-quoted string literal from what remains
// and tests each one, split into whitespace-separated class tokens, against the shapes above.
//
// It does not trace which string is actually assigned to `className` or threaded through `cx()` —
// Tailwind class fragments in this codebase live equally in inline JSX attributes, in `cx()` call
// arguments, and in module-scope constants referenced by identifier rather than written inline
// (`Skeleton`'s `pulse`, `ProfileSummary`'s `AVATAR_SKELETON_SIZE`), and reliably tracing the last
// shape through a regex would need real data-flow analysis. Scanning every string literal in the
// file instead cannot miss any of the three.
//
// That blanket string-literal scan is deliberately not applied to `*.stories.tsx` or `*.test.tsx`:
// FR-001 governs "the design system source" — the component and `lib/` implementation — and a
// test or story file is evidence about that source, not the source itself. Running it there was
// tried and measured: it reported 44 "findings" on this package's actual test/story files before
// this exclusion, every one a false positive of the same two shapes — a test description or
// Storybook control label containing an English sentence with a pixel figure in it ("clears the
// 44px touch floor", "sm (16px, default...)"), and a test asserting a real *resolved* token value
// from `getComputedStyle` (`var(--ds-icon-lg)`) or a fixture field that happens to start with `#`
// (`rank: '#214'`) — against zero real defects, because a test or story never authors a class of
// its own. Restricting the scan to implementation files only is what makes "every string literal"
// precise enough to use instead of tracing `className`/`cx()` call sites exactly.
//
// Usage:  node scripts/checks/token-scale.mjs
// Exit:   0 if no forbidden shape is found in any implementation file under
//         packages/design-system/src/, 1 otherwise — every finding is reported with its file,
//         line and the exact fragment.
import { readFileSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const srcDir = path.join(rootDir, 'packages', 'design-system', 'src')

function log(message) {
  console.log(`token-scale: ${message}`)
}

function fail(message) {
  console.error(`token-scale: ${message}`)
  process.exitCode = 1
}

// --- File discovery -------------------------------------------------------------------------

export function listTsxFiles(dir) {
  const results = []
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry)
    const stat = statSync(full)
    if (stat.isDirectory()) {
      results.push(...listTsxFiles(full))
    } else if (entry.endsWith('.tsx')) {
      results.push(full)
    }
  }
  return results
}

// A story or a test is evidence about the design system's source, not the source itself (see the
// file header for the measured false-positive count this exclusion removes). Implementation files
// only — `index.tsx` and any other non-story, non-test `.tsx` under `components/` or `lib/`.
export function isScannableFile(filePath) {
  return !filePath.endsWith('.stories.tsx') && !filePath.endsWith('.test.tsx')
}

// --- Comment/template stripping and string-literal extraction -------------------------------

// A small stateful lexer, not a parser: it only needs to tell a real single/double-quoted string
// literal apart from a `//` or `/* */` comment (which may itself contain `//`, quotes or brackets
// that must never be scanned — several comments this feature's own T528 pass wrote deliberately
// mention `h-[1em]` and `var(--ds-icon-2xl)` as history) and from a template literal (skipped
// whole, per the file header). `//` inside a real string (`STEAM_AVATAR_CDN`'s URL) must not be
// mistaken for a comment start, which is exactly why this cannot be a pair of regexes run
// independently over the raw text.
export function extractStringLiterals(source) {
  const literals = []
  let i = 0
  let line = 1
  const n = source.length
  while (i < n) {
    const ch = source[i]
    if (ch === '\n') {
      line++
      i++
      continue
    }
    if (ch === '/' && source[i + 1] === '/') {
      while (i < n && source[i] !== '\n') i++
      continue
    }
    if (ch === '/' && source[i + 1] === '*') {
      i += 2
      while (i < n && !(source[i] === '*' && source[i + 1] === '/')) {
        if (source[i] === '\n') line++
        i++
      }
      i += 2
      continue
    }
    if (ch === '`') {
      // Template literal: skipped whole (see file header). Not scanned for interpolated
      // expressions of arbitrary complexity — this repository writes no className/cx() argument
      // as a template literal, so there is nothing here worth the complexity of tracking `${}`.
      i++
      while (i < n && source[i] !== '`') {
        if (source[i] === '\\') i++
        else if (source[i] === '\n') line++
        i++
      }
      i++
      continue
    }
    if (ch === "'" || ch === '"') {
      const quote = ch
      const startLine = line
      let value = ''
      i++
      while (i < n && source[i] !== quote) {
        if (source[i] === '\\') {
          value += source[i] + (source[i + 1] ?? '')
          i += 2
          continue
        }
        if (source[i] === '\n') line++
        value += source[i]
        i++
      }
      i++ // closing quote
      literals.push({ value, line: startLine })
      continue
    }
    i++
  }
  return literals
}

// --- Forbidden-shape rules --------------------------------------------------------------------

const LENGTH_RE = /\d+(\.\d+)?(em|rem|px|vh|vw|%)\b/i
const COLOR_FN_RE = /\b(rgb|rgba|hsl|hsla)\(/i
const HEX_RE = /#[0-9a-fA-F]{3,8}\b/
const DURATION_RE = /\d+(\.\d+)?(ms|s)\b/i
const RAW_PX_REM_MS_RE = /\b\d+(\.\d+)?(px|rem|ms)\b/i
const DS_VAR_RE = /var\(--ds-/

// A comma-separated list of bare CSS property names/keywords — letters and hyphens only, at least
// one comma. `transition-[fill,opacity]`'s contract-named allowlisted shape.
const PROPERTY_LIST_RE = /^[a-z-]+(,[a-z-]+)+$/i

// `property:keyword` bracket shape — the contract's `[overflow-wrap:anywhere]` example,
// generalised. Both sides letters/hyphens only, so a real value (a hex, a unit, a function call)
// never matches this shape and falls through to the generic value check instead.
const PROPERTY_KEYWORD_RE = /^([a-zA-Z-]+):([a-zA-Z-]+)$/
const PAINTS_RE = /color|fill|stroke/i

// Extracts the utility name immediately hyphen-attached before a `[...]` group, e.g. `animate` from
// `motion-safe:animate-[spin_..._infinite]`, `max-h` from `max-h-[80vh]`. `null` when the bracket
// stands alone (an arbitrary variant like `[&>button]`, or a bare property-bracket).
function utilityPrefixFor(token, bracketStart) {
  const before = token.slice(0, bracketStart)
  const match = /([a-zA-Z][a-zA-Z0-9-]*)-$/.exec(before)
  return match ? match[1] : null
}

// Evaluates one `[...]` bracket's content against the rules above. Returns a finding string, or
// `null` when the bracket is a value-shaped-and-allowed or not a value at all (an arbitrary
// variant selector such as `[&>button]`, out of this check's scope: it carries no length, colour,
// duration or shadow).
function checkBracket(token, prefix, content) {
  if (DS_VAR_RE.test(content)) {
    return `hand-written var(--ds-*) inside a bracket: \`${prefix ? `${prefix}-` : ''}[${content}]\``
  }
  if (prefix === 'animate') {
    // Every loop this system runs (`spin`, `pulse`) is a real `animate-*` utility
    // (motion.json's `animation` group, T512/T516) — a hand-written `animate-[...]` always
    // duplicates one of those or invents an untokenised third, so it is never allowed.
    return `arbitrary animate-[...] value: \`animate-[${content}]\` — use the real animate-* utility`
  }
  if (prefix === 'shadow') {
    // Every elevation level is a real `shadow-*` utility (elevation.json) — an arbitrary shadow
    // value bypasses the level system FR-009 requires.
    return `arbitrary shadow-[...] value: \`shadow-[${content}]\``
  }
  if (prefix === 'transition') {
    if (PROPERTY_LIST_RE.test(content)) return null // allowlisted: a property list, not a value
    return `transition-[...] carries a value, not a property list: \`transition-[${content}]\``
  }
  const propertyKeyword = PROPERTY_KEYWORD_RE.exec(content)
  if (propertyKeyword) {
    const [, prop, value] = propertyKeyword
    if (PAINTS_RE.test(prop)) {
      // Narrow, deliberate: a property whose own name says it paints something is always a
      // colour decision, never allowlisted as "no design decision in it" — `[color:red]` fails
      // even though `red` is a bare keyword, the same shape `[overflow-wrap:anywhere]` uses.
      return `bracket sets a colour-bearing property: \`[${prop}:${value}]\``
    }
    if (LENGTH_RE.test(value) || COLOR_FN_RE.test(value) || HEX_RE.test(value) || DURATION_RE.test(value)) {
      return `bracket property value is not a bare keyword: \`[${prop}:${value}]\``
    }
    return null // allowlisted: a CSS property declaration with no design-token concern
  }
  if (LENGTH_RE.test(content) || COLOR_FN_RE.test(content) || HEX_RE.test(content) || DURATION_RE.test(content)) {
    return `arbitrary bracket value: \`${prefix ? `${prefix}-` : ''}[${content}]\``
  }
  return null // not a value shape this check governs (e.g. an arbitrary variant selector)
}

// Evaluates one whitespace-separated class token (which may carry one or more `[...]` groups) and
// returns every finding for it.
function checkToken(token) {
  const findings = []
  const bracketRe = /\[([^[\]]*)\]/g
  let match
  while ((match = bracketRe.exec(token))) {
    const prefix = utilityPrefixFor(token, match.index)
    const finding = checkBracket(token, prefix, match[1])
    if (finding) findings.push(finding)
  }
  return findings
}

// Evaluates one extracted string literal in full: the hand-written-var check and the raw hex/
// px/rem/ms check both apply to the whole string (not per-token — a stray `14px` typed outside
// Tailwind's bracket syntax is still a defect), and the bracket rules apply per class token.
export function checkStringLiteral(value) {
  const findings = []
  if (DS_VAR_RE.test(value)) {
    findings.push(`hand-written var(--ds-*) reference: \`${value}\``)
  }
  if (HEX_RE.test(value)) {
    findings.push(`raw hex colour literal: \`${value}\``)
  }
  if (RAW_PX_REM_MS_RE.test(value)) {
    findings.push(`raw px/rem/ms literal: \`${value}\``)
  }
  for (const token of value.split(/\s+/).filter(Boolean)) {
    findings.push(...checkToken(token))
  }
  // De-duplicate: the var()/hex/px-rem-ms checks above and the per-token bracket scan can both
  // report the same fragment (a hand-written var sits inside a bracket a token-level scan also
  // inspects) — one finding per distinct message is enough.
  return [...new Set(findings)]
}

// --- File-level scan --------------------------------------------------------------------------

export function checkFile(filePath, source) {
  const findings = []
  for (const { value, line } of extractStringLiterals(source)) {
    for (const message of checkStringLiteral(value)) {
      findings.push({ line, message })
    }
  }
  return findings
}

function main() {
  const files = listTsxFiles(srcDir).filter(isScannableFile)
  let total = 0
  for (const file of files) {
    const source = readFileSync(file, 'utf8')
    const findings = checkFile(file, source)
    for (const { line, message } of findings) {
      total++
      fail(`${path.relative(rootDir, file)}:${line}: ${message}`)
    }
  }
  if (total > 0) {
    fail(
      `${total} off-scale value${total === 1 ? '' : 's'} found across ${files.length} files ` +
        `under ${path.relative(rootDir, srcDir)}.`,
    )
    return
  }
  log(`${files.length} files under ${path.relative(rootDir, srcDir)} carry no off-scale value.`)
}

// Only run when invoked directly (`node scripts/checks/token-scale.mjs`) — token-scale.test.mjs
// imports the functions above without triggering the scan or the process exit code.
if (import.meta.url === `file://${process.argv[1]}`) {
  main()
}
