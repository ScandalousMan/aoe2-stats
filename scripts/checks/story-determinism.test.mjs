// Regression tests for T673's mechanical check (story-determinism.mjs). Follows
// story-baselines-duplicates.test.mjs's own conventions for this class of fixture: real, decodable
// PNGs written into a fresh `node:fs.mkdtempSync` directory per test, never the real tree and never
// shared state between tests.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { PNG } from 'pngjs'
import { DUPLICATE_MAX_DIFF_RATIO } from './story-baselines-duplicates.mjs'
import { listPngFiles, compareRenderPasses, runCheck } from './story-determinism.mjs'

function makeFixtureDir() {
  return mkdtempSync(path.join(os.tmpdir(), 'story-determinism-'))
}

// A real, decodable 10x10 solid-white PNG, with `flipPixels` of its 100 pixels' red channel set to
// 0 — the same fixture shape story-baselines-duplicates.test.mjs's own `makeSolidPng` uses, so a
// ratio of `flipPixels / 100` lands cleanly on either side of `DUPLICATE_MAX_DIFF_RATIO` (0.01).
function makeSolidPng(flipPixels = 0) {
  const width = 10
  const height = 10
  const png = new PNG({ width, height })
  for (let i = 0; i < png.data.length; i += 4) {
    png.data[i] = 255
    png.data[i + 1] = 255
    png.data[i + 2] = 255
    png.data[i + 3] = 255
  }
  for (let p = 0; p < flipPixels; p += 1) {
    png.data[p * 4] = 0
  }
  return PNG.sync.write(png)
}

function writePass(dir, files) {
  mkdirSync(dir, { recursive: true })
  for (const [name, buffer] of Object.entries(files)) {
    writeFileSync(path.join(dir, name), buffer)
  }
}

// ---------------------------------------------------------------------------------------------
// listPngFiles
// ---------------------------------------------------------------------------------------------

test('listPngFiles returns null for a directory that does not exist', () => {
  const dir = makeFixtureDir()
  try {
    assert.equal(listPngFiles(path.join(dir, 'nope')), null)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('listPngFiles returns a sorted, filtered list for an existing directory', () => {
  const dir = makeFixtureDir()
  try {
    writeFileSync(path.join(dir, 'b-story-light-1280.png'), makeSolidPng())
    writeFileSync(path.join(dir, 'a-story-light-1280.png'), makeSolidPng())
    writeFileSync(path.join(dir, 'not-a-png.txt'), 'ignore me')
    assert.deepEqual(listPngFiles(dir), ['a-story-light-1280.png', 'b-story-light-1280.png'])
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

// ---------------------------------------------------------------------------------------------
// compareRenderPasses — the comparator's own decision logic.
// ---------------------------------------------------------------------------------------------

test('compareRenderPasses passes on two identical renders', () => {
  const dir = makeFixtureDir()
  try {
    const passA = path.join(dir, 'pass-0')
    const passB = path.join(dir, 'pass-1')
    const png = makeSolidPng(0)
    writePass(passA, { 'story-light-1280.png': png })
    writePass(passB, { 'story-light-1280.png': png })

    const { findings, comparedCount } = compareRenderPasses({ passADir: passA, passBDir: passB })
    assert.deepEqual(findings, [])
    assert.equal(comparedCount, 1)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('compareRenderPasses passes on two near-identical renders at exactly the tolerance', () => {
  const dir = makeFixtureDir()
  try {
    const passA = path.join(dir, 'pass-0')
    const passB = path.join(dir, 'pass-1')
    // 1 of 100 pixels differs — a ratio of 0.01, exactly DUPLICATE_MAX_DIFF_RATIO, still within
    // tolerance (never failed at the boundary itself, only strictly over it).
    writePass(passA, { 'story-light-1280.png': makeSolidPng(0) })
    writePass(passB, { 'story-light-1280.png': makeSolidPng(1) })

    const { findings, comparedCount } = compareRenderPasses({ passADir: passA, passBDir: passB })
    assert.deepEqual(findings, [])
    assert.equal(comparedCount, 1)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('compareRenderPasses flags a render pair that differs by more than the tolerance, naming it and its ratio', () => {
  const dir = makeFixtureDir()
  try {
    const passA = path.join(dir, 'pass-0')
    const passB = path.join(dir, 'pass-1')
    // 50 of 100 pixels differ — a ratio of 0.5, far over DUPLICATE_MAX_DIFF_RATIO: the shape a real
    // non-determinism (an unfrozen clock, a running animation) would produce, never anti-aliasing
    // noise.
    writePass(passA, { 'flaky-story-dark-375.png': makeSolidPng(0) })
    writePass(passB, { 'flaky-story-dark-375.png': makeSolidPng(50) })

    const { findings, comparedCount } = compareRenderPasses({ passADir: passA, passBDir: passB })
    assert.equal(comparedCount, 1)
    assert.equal(findings.length, 1)
    assert.match(findings[0], /flaky-story-dark-375\.png/)
    assert.match(findings[0], /50\.000%/)
    assert.match(findings[0], /not deterministic/)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('compareRenderPasses reports every non-deterministic pair, not only the first', () => {
  const dir = makeFixtureDir()
  try {
    const passA = path.join(dir, 'pass-0')
    const passB = path.join(dir, 'pass-1')
    writePass(passA, {
      'stable-story-light-1280.png': makeSolidPng(0),
      'flaky-a-light-1280.png': makeSolidPng(0),
      'flaky-b-dark-768.png': makeSolidPng(0),
    })
    writePass(passB, {
      'stable-story-light-1280.png': makeSolidPng(0),
      'flaky-a-light-1280.png': makeSolidPng(90),
      'flaky-b-dark-768.png': makeSolidPng(30),
    })

    const { findings, comparedCount } = compareRenderPasses({ passADir: passA, passBDir: passB })
    assert.equal(comparedCount, 3)
    assert.equal(findings.length, 2)
    assert.ok(findings.some((f) => f.includes('flaky-a-light-1280.png')))
    assert.ok(findings.some((f) => f.includes('flaky-b-dark-768.png')))
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('compareRenderPasses fails when a pass directory does not exist, never passing vacuously', () => {
  const dir = makeFixtureDir()
  try {
    const passA = path.join(dir, 'pass-0')
    writePass(passA, { 'story-light-1280.png': makeSolidPng(0) })

    const { findings, comparedCount } = compareRenderPasses({
      passADir: passA,
      passBDir: path.join(dir, 'pass-1-never-ran'),
    })
    assert.equal(comparedCount, 0)
    assert.equal(findings.length, 1)
    assert.match(findings[0], /no pass directory found/)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('compareRenderPasses fails when both passes captured zero units, never passing vacuously', () => {
  const dir = makeFixtureDir()
  try {
    const passA = path.join(dir, 'pass-0')
    const passB = path.join(dir, 'pass-1')
    mkdirSync(passA, { recursive: true })
    mkdirSync(passB, { recursive: true })

    const { findings, comparedCount } = compareRenderPasses({ passADir: passA, passBDir: passB })
    assert.equal(comparedCount, 0)
    assert.equal(findings.length, 1)
    assert.match(findings[0], /zero captures found/)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('compareRenderPasses flags a unit captured in pass-0 and missing from pass-1', () => {
  const dir = makeFixtureDir()
  try {
    const passA = path.join(dir, 'pass-0')
    const passB = path.join(dir, 'pass-1')
    writePass(passA, {
      'story-light-1280.png': makeSolidPng(0),
      'only-in-a-light-1280.png': makeSolidPng(0),
    })
    writePass(passB, { 'story-light-1280.png': makeSolidPng(0) })

    const { findings, comparedCount } = compareRenderPasses({ passADir: passA, passBDir: passB })
    assert.equal(comparedCount, 1)
    assert.equal(findings.length, 1)
    assert.match(findings[0], /only-in-a-light-1280\.png.*missing from pass-1/)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

// The reverse direction of the test above — the two must be symmetric, never a one-way check that
// only catches a unit lost from pass-0.
test('compareRenderPasses flags a unit captured in pass-1 and missing from pass-0', () => {
  const dir = makeFixtureDir()
  try {
    const passA = path.join(dir, 'pass-0')
    const passB = path.join(dir, 'pass-1')
    writePass(passA, { 'story-light-1280.png': makeSolidPng(0) })
    writePass(passB, {
      'story-light-1280.png': makeSolidPng(0),
      'only-in-b-light-1280.png': makeSolidPng(0),
    })

    const { findings, comparedCount } = compareRenderPasses({ passADir: passA, passBDir: passB })
    assert.equal(comparedCount, 1)
    assert.equal(findings.length, 1)
    assert.match(findings[0], /only-in-b-light-1280\.png.*missing from pass-0/)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

// A dimension mismatch is never indistinguishable regardless of a caller's own threshold — the
// default `getPixelDiffRatio` (`pixelDiffRatio`, imported by `story-determinism.mjs` from
// `story-baselines-duplicates.mjs`) reports it as ratio 1 (maximal), never a crash and never a
// silent pass, exercised here with the real decoder rather than an injected stub.
test('compareRenderPasses flags a pair whose dimensions differ, never comparing pixel-for-pixel', () => {
  const dir = makeFixtureDir()
  try {
    const passA = path.join(dir, 'pass-0')
    const passB = path.join(dir, 'pass-1')
    const wide = new PNG({ width: 20, height: 10 })
    for (let i = 0; i < wide.data.length; i += 4) {
      wide.data[i] = 255
      wide.data[i + 1] = 255
      wide.data[i + 2] = 255
      wide.data[i + 3] = 255
    }
    writePass(passA, { 'story-light-1280.png': makeSolidPng(0) })
    writePass(passB, { 'story-light-1280.png': PNG.sync.write(wide) })

    const { findings, comparedCount } = compareRenderPasses({ passADir: passA, passBDir: passB })
    assert.equal(comparedCount, 1)
    assert.equal(findings.length, 1)
    assert.match(findings[0], /story-light-1280\.png/)
    assert.match(findings[0], /100\.000%/)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

// A file that is not a valid PNG at all (a truncated or corrupted capture) must fail loudly rather
// than crash the whole check or read as indistinguishable — the same real-decoder path as above.
test('compareRenderPasses flags a file it cannot decode as a PNG, never crashing', () => {
  const dir = makeFixtureDir()
  try {
    const passA = path.join(dir, 'pass-0')
    const passB = path.join(dir, 'pass-1')
    writePass(passA, { 'story-light-1280.png': makeSolidPng(0) })
    writePass(passB, { 'story-light-1280.png': Buffer.from('not a png at all') })

    const { findings, comparedCount } = compareRenderPasses({ passADir: passA, passBDir: passB })
    assert.equal(comparedCount, 1)
    assert.equal(findings.length, 1)
    assert.match(findings[0], /story-light-1280\.png/)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('DUPLICATE_MAX_DIFF_RATIO is the threshold compareRenderPasses defaults to (reused, not restated)', () => {
  assert.equal(DUPLICATE_MAX_DIFF_RATIO, 0.01)
})

// ---------------------------------------------------------------------------------------------
// runCheck — exit-code orchestration.
// ---------------------------------------------------------------------------------------------

test('runCheck exits 0 with no findings on two identical passes', () => {
  const dir = makeFixtureDir()
  try {
    const passA = path.join(dir, 'pass-0')
    const passB = path.join(dir, 'pass-1')
    const png = makeSolidPng(0)
    writePass(passA, { 'story-light-1280.png': png })
    writePass(passB, { 'story-light-1280.png': png })

    const { findings, exitCode } = runCheck({ passADir: passA, passBDir: passB })
    assert.deepEqual(findings, [])
    assert.equal(exitCode, 0)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('runCheck exits 1 when a pair exceeds the tolerance', () => {
  const dir = makeFixtureDir()
  try {
    const passA = path.join(dir, 'pass-0')
    const passB = path.join(dir, 'pass-1')
    writePass(passA, { 'story-light-1280.png': makeSolidPng(0) })
    writePass(passB, { 'story-light-1280.png': makeSolidPng(50) })

    const { findings, exitCode } = runCheck({ passADir: passA, passBDir: passB })
    assert.equal(findings.length, 1)
    assert.equal(exitCode, 1)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})
