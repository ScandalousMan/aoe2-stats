// Regression tests for T592's reporting script (baseline-regeneration-diff.mjs). Two layers, the
// same split story-baselines-duplicates.test.mjs already uses: small pure-function unit tests for
// parsing and classification, and fixture-based tests that decode real, in-memory PNGs (`pngjs`) to
// prove the noise/real-move boundary itself — not just that the classifier returns *some* value.
// Every git interaction (`listChangedBaselines`'s `run`, `pixelDiffCountAcrossRefs`'s `readBlob`) is
// injected rather than shelling out to a real `git`, so this suite never depends on repository state
// or takes the multi-second cost a real `git show` per baseline would (this script's own header
// documents the actual `ba20f074`/`822b4904` validation run separately, by hand, once — not as part
// of this file).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { PNG } from 'pngjs'
import {
  NOISE_MAX_DIFF_PIXELS,
  classifyDiff,
  deriveGroupLabel,
  listChangedBaselines,
  pixelDiffCountAcrossRefs,
  buildReport,
  formatReport,
} from './baseline-regeneration-diff.mjs'

// ---------------------------------------------------------------------------------------------
// classifyDiff
// ---------------------------------------------------------------------------------------------

test('classifyDiff: at or under the threshold is noise', () => {
  assert.equal(classifyDiff({ dimensionMismatch: false, diffPixels: NOISE_MAX_DIFF_PIXELS }), 'noise')
  assert.equal(classifyDiff({ dimensionMismatch: false, diffPixels: 0 }), 'noise')
})

test('classifyDiff: one pixel over the threshold is moved', () => {
  assert.equal(
    classifyDiff({ dimensionMismatch: false, diffPixels: NOISE_MAX_DIFF_PIXELS + 1 }),
    'moved',
  )
})

test('classifyDiff: a dimension change is always moved, regardless of diffPixels', () => {
  assert.equal(classifyDiff({ dimensionMismatch: true, diffPixels: null }), 'moved')
})

test('classifyDiff: a caller-supplied threshold overrides the default', () => {
  assert.equal(classifyDiff({ dimensionMismatch: false, diffPixels: 5 }, 4), 'moved')
  assert.equal(classifyDiff({ dimensionMismatch: false, diffPixels: 4 }, 4), 'noise')
})

// ---------------------------------------------------------------------------------------------
// deriveGroupLabel
// ---------------------------------------------------------------------------------------------

test('deriveGroupLabel: a six-unit story filename derives its story id', () => {
  const label = deriveGroupLabel('primitives-button--focus-visible-dark-1280.png', new Set())
  assert.deepEqual(label, { kind: 'story', id: 'primitives-button--focus-visible' })
})

test('deriveGroupLabel: an app-route full-page filename (no width suffix) is recognised by name', () => {
  const appRouteNames = new Set(['app-signed-in-dashboard-dark'])
  const label = deriveGroupLabel('app-signed-in-dashboard-dark.png', appRouteNames)
  assert.deepEqual(label, { kind: 'app-route', id: 'app-signed-in-dashboard-dark' })
})

test('deriveGroupLabel: neither shape falls back to unmapped rather than being dropped', () => {
  const label = deriveGroupLabel('mystery-file.png', new Set())
  assert.deepEqual(label, { kind: 'unmapped', id: 'mystery-file' })
})

// ---------------------------------------------------------------------------------------------
// listChangedBaselines
// ---------------------------------------------------------------------------------------------

test('listChangedBaselines: splits M, A, D and R### lines into modified/added/removed', () => {
  const output = [
    'M\tpackages/design-system/__screenshots__/a-light-375.png',
    'A\tpackages/design-system/__screenshots__/b-light-375.png',
    'D\tpackages/design-system/__screenshots__/c-light-375.png',
    'R100\tpackages/design-system/__screenshots__/old-light-375.png\tpackages/design-system/__screenshots__/new-light-375.png',
    '',
  ].join('\n')
  const result = listChangedBaselines({ baseRef: 'base', headRef: 'head', run: () => output })
  assert.deepEqual(result.modified, [
    {
      oldPath: 'packages/design-system/__screenshots__/a-light-375.png',
      newPath: 'packages/design-system/__screenshots__/a-light-375.png',
    },
    {
      oldPath: 'packages/design-system/__screenshots__/old-light-375.png',
      newPath: 'packages/design-system/__screenshots__/new-light-375.png',
    },
  ])
  assert.deepEqual(result.added, ['packages/design-system/__screenshots__/b-light-375.png'])
  assert.deepEqual(result.removed, ['packages/design-system/__screenshots__/c-light-375.png'])
})

test('listChangedBaselines: passes baseRef, headRef and pathspec through to `run` unchanged', () => {
  let seenArgs
  listChangedBaselines({
    baseRef: 'abc123',
    headRef: 'def456',
    pathspec: 'some/path/',
    run: (args) => {
      seenArgs = args
      return ''
    },
  })
  assert.deepEqual(seenArgs, ['diff', '--name-status', 'abc123', 'def456', '--', 'some/path/'])
})

test('listChangedBaselines: an empty diff yields three empty lists', () => {
  const result = listChangedBaselines({ baseRef: 'a', headRef: 'b', run: () => '' })
  assert.deepEqual(result, { modified: [], added: [], removed: [] })
})

// ---------------------------------------------------------------------------------------------
// pixelDiffCountAcrossRefs — fixture PNGs, no real git.
// ---------------------------------------------------------------------------------------------

// A real, decodable 20x20 solid-white PNG (400 pixels — large enough to straddle
// NOISE_MAX_DIFF_PIXELS, 100, on either side) with the first `flipPixels` pixels' red channel set to
// 0, the same shape story-baselines-duplicates.test.mjs's own `makeSolidPng` uses at a size this
// file's own boundary tests need.
function makeSolidPng(flipPixels = 0, { width = 20, height = 20 } = {}) {
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

// `readBlob(ref, filePath)` backed by an in-memory `{ [ref]: { [filePath]: Buffer } }` map, standing
// in for `git show <ref>:<path>` without touching a real repository.
function fixtureReadBlob(blobs) {
  return (ref, filePath) => blobs[ref][filePath]
}

test('pixelDiffCountAcrossRefs: an ordinary modify (oldPath === newPath) reads both refs independently, not the same blob twice', () => {
  const filePath = 'packages/design-system/__screenshots__/x-light-375.png'
  const readBlob = fixtureReadBlob({
    base: { [filePath]: makeSolidPng(0) },
    head: { [filePath]: makeSolidPng(3) },
  })
  const result = pixelDiffCountAcrossRefs({
    baseRef: 'base',
    headRef: 'head',
    oldPath: filePath,
    newPath: filePath,
    readBlob,
  })
  assert.deepEqual(result, { dimensionMismatch: false, diffPixels: 3, totalPixels: 400 })
})

test('pixelDiffCountAcrossRefs: a rename (oldPath !== newPath) reads each side from its own path', () => {
  const readBlob = fixtureReadBlob({
    base: { 'old.png': makeSolidPng(0) },
    head: { 'new.png': makeSolidPng(5) },
  })
  const result = pixelDiffCountAcrossRefs({
    baseRef: 'base',
    headRef: 'head',
    oldPath: 'old.png',
    newPath: 'new.png',
    readBlob,
  })
  assert.deepEqual(result, { dimensionMismatch: false, diffPixels: 5, totalPixels: 400 })
})

test('pixelDiffCountAcrossRefs: a dimension change is reported as dimensionMismatch, not a pixel count', () => {
  const filePath = 'x.png'
  const readBlob = fixtureReadBlob({
    base: { [filePath]: makeSolidPng(0, { width: 20, height: 20 }) },
    head: { [filePath]: makeSolidPng(0, { width: 20, height: 30 }) },
  })
  const result = pixelDiffCountAcrossRefs({
    baseRef: 'base',
    headRef: 'head',
    oldPath: filePath,
    newPath: filePath,
    readBlob,
  })
  assert.equal(result.dimensionMismatch, true)
})

// ---------------------------------------------------------------------------------------------
// The noise/real-move boundary itself, end to end (fixture PNG decode -> classifyDiff), not a mock.
// ---------------------------------------------------------------------------------------------

test('boundary: exactly NOISE_MAX_DIFF_PIXELS differing pixels classifies as noise', () => {
  const filePath = 'x.png'
  const readBlob = fixtureReadBlob({
    base: { [filePath]: makeSolidPng(0) },
    head: { [filePath]: makeSolidPng(NOISE_MAX_DIFF_PIXELS) },
  })
  const diff = pixelDiffCountAcrossRefs({
    baseRef: 'base',
    headRef: 'head',
    oldPath: filePath,
    newPath: filePath,
    readBlob,
  })
  assert.equal(diff.diffPixels, NOISE_MAX_DIFF_PIXELS)
  assert.equal(classifyDiff(diff), 'noise')
})

test('boundary: one pixel beyond NOISE_MAX_DIFF_PIXELS classifies as moved', () => {
  const filePath = 'x.png'
  const readBlob = fixtureReadBlob({
    base: { [filePath]: makeSolidPng(0) },
    head: { [filePath]: makeSolidPng(NOISE_MAX_DIFF_PIXELS + 1) },
  })
  const diff = pixelDiffCountAcrossRefs({
    baseRef: 'base',
    headRef: 'head',
    oldPath: filePath,
    newPath: filePath,
    readBlob,
  })
  assert.equal(diff.diffPixels, NOISE_MAX_DIFF_PIXELS + 1)
  assert.equal(classifyDiff(diff), 'moved')
})

test('boundary: a dimension change classifies as moved even with zero differing pixels among shared bytes', () => {
  const filePath = 'x.png'
  const readBlob = fixtureReadBlob({
    base: { [filePath]: makeSolidPng(0, { width: 20, height: 20 }) },
    head: { [filePath]: makeSolidPng(0, { width: 20, height: 25 }) },
  })
  const diff = pixelDiffCountAcrossRefs({
    baseRef: 'base',
    headRef: 'head',
    oldPath: filePath,
    newPath: filePath,
    readBlob,
  })
  assert.equal(classifyDiff(diff), 'moved')
})

// ---------------------------------------------------------------------------------------------
// buildReport / formatReport — full pipeline, still no real git.
// ---------------------------------------------------------------------------------------------

test('buildReport: groups a story\'s six units together and separates added/removed', () => {
  const storyId = 'primitives-button--focus-visible'
  const files = []
  for (const theme of ['light', 'dark']) {
    for (const width of [375, 768, 1280]) {
      files.push(`packages/design-system/__screenshots__/${storyId}-${theme}-${width}.png`)
    }
  }
  const diffOutput = [
    ...files.map((f) => `M\t${f}`),
    'A\tpackages/design-system/__screenshots__/new-story-light-375.png',
    'D\tpackages/design-system/__screenshots__/old-story-light-375.png',
  ].join('\n')

  const blobs = { base: {}, head: {} }
  files.forEach((f, index) => {
    blobs.base[f] = makeSolidPng(0)
    // Every unit moves by NOISE_MAX_DIFF_PIXELS + 1 except the first, which stays identical (noise).
    blobs.head[f] = makeSolidPng(index === 0 ? 0 : NOISE_MAX_DIFF_PIXELS + 1)
  })

  const report = buildReport({
    baseRef: 'base',
    headRef: 'head',
    run: () => diffOutput,
    readBlob: fixtureReadBlob(blobs),
    readSpecFile: () => '',
  })

  assert.equal(report.captures.length, 6)
  assert.equal(report.added.length, 1)
  assert.equal(report.removed.length, 1)
  assert.equal(report.groups.length, 1)
  assert.equal(report.groups[0].id, storyId)
  const moved = report.groups[0].captures.filter((c) => c.bucket === 'moved')
  const noise = report.groups[0].captures.filter((c) => c.bucket === 'noise')
  assert.equal(moved.length, 5)
  assert.equal(noise.length, 1)
})

test('formatReport: names both buckets with their group and capture counts', () => {
  const report = {
    baseRef: 'base',
    headRef: 'head',
    captures: [
      {
        path: 'a.png',
        fileName: 'a.png',
        label: { kind: 'story', id: 'story-a' },
        dimensionMismatch: false,
        diffPixels: 500,
        totalPixels: 10000,
        ratio: 0.05,
        bucket: 'moved',
      },
      {
        path: 'b.png',
        fileName: 'b.png',
        label: { kind: 'story', id: 'story-b' },
        dimensionMismatch: false,
        diffPixels: 2,
        totalPixels: 10000,
        ratio: 0.0002,
        bucket: 'noise',
      },
    ],
    groups: [
      { kind: 'story', id: 'story-a', captures: [] },
      { kind: 'story', id: 'story-b', captures: [] },
    ],
    added: ['added.png'],
    removed: ['removed.png'],
  }
  report.groups[0].captures = [report.captures[0]]
  report.groups[1].captures = [report.captures[1]]

  const text = formatReport(report)
  assert.match(text, /2 capture\(s\) rewritten, 1 added, 1 removed/)
  assert.match(text, /Moved beyond anti-aliasing noise.*1 group\(s\), 1 capture\(s\)/)
  assert.match(text, /Did not move.*1 group\(s\), 1 capture\(s\)/)
  assert.match(text, /story-a/)
  assert.match(text, /500px/)
  assert.match(text, /Added \(no predecessor to compare against\): 1/)
  assert.match(text, /Removed \(no successor to compare against\): 1/)
})
