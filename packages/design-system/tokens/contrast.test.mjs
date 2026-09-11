// T580 — closes the "Duplicated logic and story-content gap register" row `packages/design-system/
// specs/README.md` has carried for the WCAG contrast formula since the fifth-pass adversarial
// review (2026-09-09). Two kinds of test: the formula itself, checked against known reference
// values and the two entry points agreeing with each other; and a recurrence guard, because the
// register row existed in the first place only because nothing stopped a second and third
// hand-written copy from shipping — the same defect class this file's own guard test is built to
// catch before a fourth ever lands.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { contrastRatioHex, contrastRatioRgb } from './contrast.mjs'

const tokensDir = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.join(tokensDir, '..', '..', '..')

// --- Reference values -------------------------------------------------------------------------

test('black on white and white on black both measure the maximum ratio, 21:1', () => {
  assert.ok(Math.abs(contrastRatioHex('#000000', '#ffffff') - 21) < 0.01)
  assert.ok(Math.abs(contrastRatioHex('#ffffff', '#000000') - 21) < 0.01)
})

test('any colour against itself measures the minimum ratio, 1:1', () => {
  for (const hex of ['#000000', '#ffffff', '#767676', '#3366ff']) {
    assert.ok(Math.abs(contrastRatioHex(hex, hex) - 1) < 0.001, `${hex} against itself`)
  }
})

test('#767676 on #ffffff measures approximately 4.54:1 — the classic AA-boundary grey', () => {
  const ratio = contrastRatioHex('#767676', '#ffffff')
  assert.ok(Math.abs(ratio - 4.54) < 0.01, `expected ~4.54:1, got ${ratio.toFixed(4)}:1`)
})

test('the ratio is symmetric: contrastRatioHex(a, b) === contrastRatioHex(b, a)', () => {
  const pairs = [
    ['#000000', '#ffffff'],
    ['#767676', '#ffffff'],
    ['#3366ff', '#f0f0f0'],
  ]
  for (const [a, b] of pairs) {
    assert.strictEqual(contrastRatioHex(a, b), contrastRatioHex(b, a), `${a} vs ${b}`)
  }
})

test('the hex and {r,g,b} entry points agree on the same colour pair', () => {
  const cases = [
    { hexA: '#000000', hexB: '#ffffff' },
    { hexA: '#767676', hexB: '#ffffff' },
    { hexA: '#3366ff', hexB: '#f0f0f0' },
  ]
  const hexToRgb = (hex) => {
    const value = hex.replace('#', '')
    const [r, g, b] = [0, 2, 4].map((i) => parseInt(value.slice(i, i + 2), 16))
    return { r, g, b }
  }
  for (const { hexA, hexB } of cases) {
    const viaHex = contrastRatioHex(hexA, hexB)
    const viaRgb = contrastRatioRgb(hexToRgb(hexA), hexToRgb(hexB))
    assert.ok(
      Math.abs(viaHex - viaRgb) < 1e-9,
      `${hexA} vs ${hexB}: hex entry point gave ${viaHex}, rgb entry point gave ${viaRgb}`,
    )
  }
})

// --- Recurrence guard --------------------------------------------------------------------------
// The register row this task closes existed only because nothing failed a build when the formula
// was corrected in two of its three hand-written copies and not the third. This scans the
// repository's own source for a fourth hand-written copy of the same linearisation formula —
// matched on the `12.92` divisor together with the `1.055` gamma denominator in the same file,
// which is specific to this formula rather than a number that could appear legitimately elsewhere
// — and fails, naming the file, if one turns up outside this module.

const SCAN_ROOTS = ['packages', 'tests', 'scripts', 'apps']
const EXCLUDED_DIR_NAMES = new Set([
  'node_modules',
  'storybook-static',
  'dist',
  'generated',
  '.git',
  'coverage',
  'build',
  '__screenshots__',
])
const SOURCE_EXTENSIONS = new Set(['.mjs', '.cjs', '.js', '.ts', '.tsx'])
// Repo-root-relative, forward-slash paths allowed to carry the formula: the module itself, and
// this test file, whose own prose names the two literals the guard matches on (that sentence, not
// the formula, is why it would otherwise flag itself).
const ALLOWED_PATHS = new Set([
  'packages/design-system/tokens/contrast.mjs',
  'packages/design-system/tokens/contrast.test.mjs',
])

function listSourceFiles(dir) {
  const entries = readdirSync(dir, { withFileTypes: true })
  const files = []
  for (const entry of entries) {
    if (entry.isDirectory()) {
      if (EXCLUDED_DIR_NAMES.has(entry.name)) continue
      files.push(...listSourceFiles(path.join(dir, entry.name)))
      continue
    }
    if (SOURCE_EXTENSIONS.has(path.extname(entry.name))) {
      files.push(path.join(dir, entry.name))
    }
  }
  return files
}

// Exported so this test file's own header comment stays provable: the "prove it bites" step in
// T580's brief pastes the old formula back into a call site, re-runs this exact scan, and reverts.
export function findHandWrittenLinearisationCopies() {
  const offenders = []
  for (const root of SCAN_ROOTS) {
    const rootDir = path.join(repoRoot, root)
    let files
    try {
      files = listSourceFiles(rootDir)
    } catch {
      continue // a scan root that does not exist in this checkout is not a finding
    }
    for (const file of files) {
      const relative = path.relative(repoRoot, file).split(path.sep).join('/')
      if (ALLOWED_PATHS.has(relative)) continue
      const content = readFileSync(file, 'utf8')
      if (content.includes('12.92') && content.includes('1.055')) {
        offenders.push(relative)
      }
    }
  }
  return offenders
}

test('no hand-written copy of the sRGB linearisation formula exists outside contrast.mjs', () => {
  const offenders = findHandWrittenLinearisationCopies()
  assert.deepStrictEqual(
    offenders,
    [],
    `found a hand-written copy of the sRGB linearisation formula (the 12.92 divisor together with ` +
      `1.055) outside contrast.mjs: ${offenders.join(', ')} — import contrastRatioHex/` +
      `contrastRatioRgb from packages/design-system/tokens/contrast.mjs instead of re-deriving ` +
      'the formula',
  )
})
