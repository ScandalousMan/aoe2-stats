// Regression tests for T584's mechanical check (story-baselines-duplicates.mjs). Two layers, the
// same split story-docs.test.mjs and story-baselines.test.mjs already use: small pure-function unit
// tests for the id-derivation and marker-parsing helpers, and full end-to-end runs of `runCheck`
// against real files written into a fresh `node:fs.mkdtempSync` directory per test — never the real
// tree, and never shared state between tests (T578's own "a fixture must be provably its own, not
// the live tree" lesson, applied here to a filesystem fixture instead of an in-memory one). The last
// test in this file is the one exception: it runs `runCheck` with no overrides at all, against the
// real, committed tree, and must pass — the proof this check's own header claims.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { PNG } from 'pngjs'
import {
  kebabFromExportName,
  sanitizeTitleSegment,
  deriveMetaId,
  parseMarkersInBlock,
  commentBlockAbove,
  parseStoryFile,
  evaluateMarkers,
  evaluateFullMatchDocumentation,
  evaluateDebtEntries,
  findStaleDebtEntries,
  findFullMatchGroups,
  findPartialMatches,
  computeHashKeys,
  pixelDiffRatio,
  storiesAreIndistinguishable,
  computeFullMatchGroups,
  DUPLICATE_MAX_DIFF_RATIO,
  runCheck,
} from './story-baselines-duplicates.mjs'

// ---------------------------------------------------------------------------------------------
// Pure-function unit tests.
// ---------------------------------------------------------------------------------------------

test('kebabFromExportName splits a case boundary and a digit boundary as different words', () => {
  assert.equal(kebabFromExportName('SheetBelowMd'), 'sheet-below-md')
  assert.equal(kebabFromExportName('SizeXs'), 'size-xs')
  assert.equal(kebabFromExportName('NoAoe2Profile'), 'no-aoe-2-profile')
  assert.equal(
    kebabFromExportName('EscapeReturnsFocusToTrigger'),
    'escape-returns-focus-to-trigger',
  )
})

test('sanitizeTitleSegment lower-cases and folds punctuation/spaces to one hyphen', () => {
  assert.equal(sanitizeTitleSegment('Match & game data'), 'match-game-data')
  assert.equal(sanitizeTitleSegment('Colour'), 'colour')
})

test('deriveMetaId prefers an explicit id over a derived title', () => {
  const source = `const meta = { id: 'composite-widget', title: 'Composites/Widget' }\nexport default meta\n`
  assert.equal(deriveMetaId(source), 'composite-widget')
})

test("deriveMetaId derives from title when no explicit id exists (the foundations docs pages' own shape)", () => {
  const source = `const meta = { title: 'Foundations/Colour' }\nexport default meta\n`
  assert.equal(deriveMetaId(source), 'foundations-colour')
})

test('deriveMetaId returns null with neither id nor title', () => {
  assert.equal(deriveMetaId('const meta = {}\nexport default meta\n'), null)
})

test('commentBlockAbove stops at the first non-comment or blank line, in source order', () => {
  const lines = ['const x = 1', '// first', '// second', 'export const Foo: Story = {}']
  assert.deepEqual(commentBlockAbove(lines, 3), ['// first', '// second'])
})

test('commentBlockAbove returns empty with no adjacent comment', () => {
  const lines = ['const x = 1', '', 'export const Foo: Story = {}']
  assert.deepEqual(commentBlockAbove(lines, 2), [])
})

test('parseMarkersInBlock extracts every visual-equivalence line, with an empty reason kept as a finding-bearing entry', () => {
  const block = [
    '// some prose',
    '// visual-equivalence: composite-foo--bar: because reasons',
    '// visual-equivalence: composite-foo--baz:',
  ]
  assert.deepEqual(parseMarkersInBlock(block), [
    { targetId: 'composite-foo--bar', reason: 'because reasons' },
    { targetId: 'composite-foo--baz', reason: '' },
  ])
})

test('parseStoryFile attaches a marker to the export whose comment block carries it, not to an unrelated export', () => {
  const source = `const meta = { id: 'composite-widget' }
export default meta

export const Default: Story = {}

// visual-equivalence: composite-widget--default: same fixture, no visible change
export const Alias: Story = {}
`
  const { stories, markers } = parseStoryFile(source)
  assert.deepEqual(
    stories.map((s) => s.id),
    ['composite-widget--default', 'composite-widget--alias'],
  )
  assert.deepEqual(markers, [
    {
      sourceId: 'composite-widget--alias',
      targetId: 'composite-widget--default',
      reason: 'same fixture, no visible change',
    },
  ])
})

test('findFullMatchGroups groups three-plus stories sharing one hash key, and ignores singletons', () => {
  const hashKeyByStoryId = new Map([
    ['a', 'x'],
    ['b', 'x'],
    ['c', 'x'],
    ['d', 'y'],
  ])
  assert.deepEqual(findFullMatchGroups(hashKeyByStoryId), [['a', 'b', 'c']])
})

test('findPartialMatches reports 1-5 of 6 shared units and excludes full (6) and zero matches', () => {
  const hashKeyByStoryId = new Map([
    ['a', ['1', '1', '1', '1', '1', '2'].join(':')],
    ['b', ['1', '1', '1', '1', '1', '3'].join(':')],
    ['c', ['9', '9', '9', '9', '9', '9'].join(':')],
  ])
  const partials = findPartialMatches(hashKeyByStoryId)
  assert.deepEqual(partials, [{ a: 'a', b: 'b', matches: 5, of: 6 }])
})

test('evaluateMarkers rejects an empty reason, an unknown target, and a stale (not-currently-equal) pair', () => {
  const markers = [
    { sourceId: 's--empty-reason', targetId: 's--target', reason: '', filePath: '/f.tsx' },
    { sourceId: 's--a', targetId: 's--unknown', reason: 'ok', filePath: '/f.tsx' },
    { sourceId: 's--b', targetId: 's--c', reason: 'ok', filePath: '/f.tsx' },
  ]
  const hashKeyByStoryId = new Map([
    ['s--target', 'k1'],
    ['s--a', 'k2'],
    ['s--b', 'k3'],
    ['s--c', 'k4'],
  ])
  const { validEdges, findings } = evaluateMarkers({
    markers,
    hashKeyByStoryId,
    knownStoryIds: new Set(['s--empty-reason', 's--target', 's--a', 's--b', 's--c']),
  })
  assert.deepEqual(validEdges, [])
  assert.equal(findings.length, 3)
  assert.match(findings[0], /carries no reason/)
  assert.match(findings[1], /is not a story this tree derives/)
  assert.match(findings[2], /stale/)
})

test('evaluateFullMatchDocumentation passes a group fully connected by valid marker edges', () => {
  const findings = evaluateFullMatchDocumentation({
    fullMatchGroups: [['a', 'b', 'c']],
    validEdges: [
      ['a', 'b'],
      ['b', 'c'],
    ],
    debtEntries: [],
  })
  assert.deepEqual(findings, [])
})

test('evaluateFullMatchDocumentation fails a group with no marker and no debt entry', () => {
  const findings = evaluateFullMatchDocumentation({
    fullMatchGroups: [['a', 'b']],
    validEdges: [],
    debtEntries: [],
  })
  assert.equal(findings.length, 1)
  assert.match(findings[0], /undocumented full-set match/)
})

test('evaluateFullMatchDocumentation accepts a debt entry naming the exact set instead of a marker', () => {
  const findings = evaluateFullMatchDocumentation({
    fullMatchGroups: [['a', 'b']],
    validEdges: [],
    debtEntries: [{ storyIds: ['a', 'b'], found: '2026-09-11', fixOwed: 'x', fixBy: '2026-09-25' }],
  })
  assert.deepEqual(findings, [])
})

test('evaluateDebtEntries fails a missing field, an invalid date, and an expired fixBy', () => {
  const raw = [
    { storyIds: ['a', 'b'], found: '2026-09-11', fixOwed: 'x', fixBy: '2026-09-25' }, // fine
    { storyIds: ['c', 'd'], found: '2026-09-11', fixBy: '2026-09-25' }, // missing fixOwed
    { storyIds: ['e', 'f'], found: '2026-09-11', fixOwed: 'x', fixBy: 'not-a-date' },
    { storyIds: ['g', 'h'], found: '2026-09-11', fixOwed: 'x', fixBy: '2026-01-01' }, // expired
  ]
  const { entries, findings } = evaluateDebtEntries(raw, '2026-09-11')
  assert.equal(entries.length, 2) // the fine one and the expired one (well-formed, just overdue)
  assert.equal(findings.length, 3)
  assert.match(findings[0], /missing\/invalid fixOwed/)
  assert.match(findings[1], /fixBy \(not a valid ISO date\)/)
  assert.match(findings[2], /overdue/)
})

test('findStaleDebtEntries fails an entry whose set is no longer a current full-set match', () => {
  const entries = [{ storyIds: ['a', 'b'], found: '2026-09-11', fixOwed: 'x', fixBy: '2026-09-25' }]
  const findings = findStaleDebtEntries(entries, [['a', 'c']])
  assert.equal(findings.length, 1)
  assert.match(findings[0], /is not a current full-set match/)
})

test('findStaleDebtEntries is silent when the entry matches a current full-set group', () => {
  const entries = [{ storyIds: ['a', 'b'], found: '2026-09-11', fixOwed: 'x', fixBy: '2026-09-25' }]
  assert.deepEqual(findStaleDebtEntries(entries, [['a', 'b']]), [])
})

// ---------------------------------------------------------------------------------------------
// End-to-end fixtures: a real temp directory per test, never the real tree.
// ---------------------------------------------------------------------------------------------

function makeFixtureDir() {
  const dir = mkdtempSync(path.join(os.tmpdir(), 'story-baselines-duplicates-'))
  return dir
}

// Writes six 1x1-pixel-shaped (content is irrelevant — only bytes are hashed) baseline files for
// `storyId`, all carrying `content` so two stories given the same content hash-match on all six.
function writeBaselineSet(screenshotsDir, storyId, content) {
  for (const theme of ['light', 'dark']) {
    for (const width of [375, 768, 1280]) {
      writeFileSync(path.join(screenshotsDir, `${storyId}-${theme}-${width}.png`), content)
    }
  }
}

function writeStoryFile(srcDir, componentName, metaId, source) {
  const dir = path.join(srcDir, componentName)
  mkdirSync(dir, { recursive: true })
  writeFileSync(path.join(dir, `${componentName}.stories.tsx`), source)
}

// A path inside the fixture's own temp dir that is guaranteed never to exist — passed as
// `debtJsonPath` (and, where relevant, `appRoutesSpecPath`) by every end-to-end test that is not
// itself testing debt-entry or app-route behaviour, so `runCheck`'s own defaults (the real
// project's `scripts/visual/story-baseline-duplicates-debt.json` and `tests/visual/app-
// routes.spec.ts`) never leak into a fixture that has no story matching either file's own content —
// exactly the isolation this file's header promises ("never the real tree").
function noSuchPath(rootDir, name) {
  return path.join(rootDir, name)
}

// A real, decodable PNG buffer (unlike `writeBaselineSet`'s opaque `content` string, which
// `pixelDiffRatio` cannot decode) — 10x10, solid white, with `mutate` given the chance to flip
// individual pixels before it is encoded. `flipPixels` sets the red channel of the first `count`
// pixels to 0, so `count` out of the image's 100 pixels differ from an unmutated twin — a ratio of
// `count / 100`, chosen to land cleanly on either side of `DUPLICATE_MAX_DIFF_RATIO` (0.01).
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

// ---------------------------------------------------------------------------------------------
// Pixel-level tolerance (see story-baselines-duplicates.mjs's own header for why a ratio, not byte
// equality). These fixtures are real, decodable PNGs (`makeSolidPng`), not the opaque byte strings
// `writeBaselineSet` uses elsewhere in this file — `pixelDiffRatio` decodes them for real.
// ---------------------------------------------------------------------------------------------

test('pixelDiffRatio: one differing pixel out of a 10x10 image is a ratio of 0.01, exactly DUPLICATE_MAX_DIFF_RATIO', () => {
  const dir = makeFixtureDir()
  try {
    const basePath = path.join(dir, 'base.png')
    const closePath = path.join(dir, 'close.png')
    writeFileSync(basePath, makeSolidPng(0))
    writeFileSync(closePath, makeSolidPng(1))
    assert.equal(pixelDiffRatio(basePath, closePath), 0.01)
    assert.ok(pixelDiffRatio(basePath, closePath) <= DUPLICATE_MAX_DIFF_RATIO)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('pixelDiffRatio: half the pixels differing is a ratio of 0.5, well above DUPLICATE_MAX_DIFF_RATIO', () => {
  const dir = makeFixtureDir()
  try {
    const basePath = path.join(dir, 'base.png')
    const farPath = path.join(dir, 'far.png')
    writeFileSync(basePath, makeSolidPng(0))
    writeFileSync(farPath, makeSolidPng(50))
    assert.equal(pixelDiffRatio(basePath, farPath), 0.5)
    assert.ok(pixelDiffRatio(basePath, farPath) > DUPLICATE_MAX_DIFF_RATIO)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('storiesAreIndistinguishable: a handful of differing pixels on one unit still counts as a full match; well above the threshold does not', () => {
  const dir = makeFixtureDir()
  try {
    const screenshotsDir = path.join(dir, '__screenshots__')
    mkdirSync(screenshotsDir, { recursive: true })
    // `a` and `b` share five of their six units byte-identically; the sixth (light-1280) differs by
    // one pixel of 100 for `b`, and by 50 of 100 for `c` — the same noise-vs-defect split this
    // file's own header measured on the real tree (25px noise vs. 1276-52768px genuine change).
    for (const [suffix, content] of [
      ['light-375', makeSolidPng(0)],
      ['light-768', makeSolidPng(0)],
      ['dark-375', makeSolidPng(0)],
      ['dark-768', makeSolidPng(0)],
      ['dark-1280', makeSolidPng(0)],
    ]) {
      writeFileSync(path.join(screenshotsDir, `composite-widget--a-${suffix}.png`), content)
      writeFileSync(path.join(screenshotsDir, `composite-widget--b-${suffix}.png`), content)
      writeFileSync(path.join(screenshotsDir, `composite-widget--c-${suffix}.png`), content)
    }
    writeFileSync(path.join(screenshotsDir, 'composite-widget--a-light-1280.png'), makeSolidPng(0))
    writeFileSync(path.join(screenshotsDir, 'composite-widget--b-light-1280.png'), makeSolidPng(1))
    writeFileSync(path.join(screenshotsDir, 'composite-widget--c-light-1280.png'), makeSolidPng(50))

    const hashKeyByStoryId = computeHashKeys(
      new Set(['composite-widget--a', 'composite-widget--b', 'composite-widget--c']),
      screenshotsDir,
    )

    assert.equal(
      storiesAreIndistinguishable('composite-widget--a', 'composite-widget--b', {
        hashKeyByStoryId,
        screenshotsDir,
      }),
      true,
    )
    assert.equal(
      storiesAreIndistinguishable('composite-widget--a', 'composite-widget--c', {
        hashKeyByStoryId,
        screenshotsDir,
      }),
      false,
    )
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('end-to-end: an undocumented full match fails', () => {
  const rootDir = makeFixtureDir()
  try {
    const srcDir = path.join(rootDir, 'src')
    const screenshotsDir = path.join(rootDir, '__screenshots__')
    mkdirSync(screenshotsDir, { recursive: true })

    writeStoryFile(
      srcDir,
      'Widget',
      'composite-widget',
      `const meta = { id: 'composite-widget' }\nexport default meta\n\nexport const Default: Story = {}\nexport const Alias: Story = {}\n`,
    )
    writeBaselineSet(screenshotsDir, 'composite-widget--default', 'same-bytes')
    writeBaselineSet(screenshotsDir, 'composite-widget--alias', 'same-bytes')

    const { findings, exitCode } = runCheck({
      srcDirs: [srcDir],
      screenshotsDir,
      debtJsonPath: noSuchPath(rootDir, 'debt.json'),
      appRoutesSpecPath: noSuchPath(rootDir, 'app-routes.spec.ts'),
    })
    console.log('undocumented full match — findings:', findings)
    assert.equal(exitCode, 1)
    assert.ok(findings.some((f) => f.includes('undocumented full-set match')))
  } finally {
    rmSync(rootDir, { recursive: true, force: true })
  }
})

test('end-to-end: a documented match (marker naming the contrast-case pair) passes', () => {
  const rootDir = makeFixtureDir()
  try {
    const srcDir = path.join(rootDir, 'src')
    const screenshotsDir = path.join(rootDir, '__screenshots__')
    mkdirSync(screenshotsDir, { recursive: true })

    writeStoryFile(
      srcDir,
      'Widget',
      'composite-widget',
      `const meta = { id: 'composite-widget' }\nexport default meta\n\nexport const Default: Story = {}\n\n// visual-equivalence: composite-widget--default: size 'md' is this component's own default\nexport const SizeMd: Story = {}\n`,
    )
    writeBaselineSet(screenshotsDir, 'composite-widget--default', 'same-bytes')
    writeBaselineSet(screenshotsDir, 'composite-widget--size-md', 'same-bytes')

    const { findings, infoLines, exitCode } = runCheck({
      srcDirs: [srcDir],
      screenshotsDir,
      debtJsonPath: noSuchPath(rootDir, 'debt.json'),
      appRoutesSpecPath: noSuchPath(rootDir, 'app-routes.spec.ts'),
    })
    console.log('documented match — findings:', findings, 'info:', infoLines)
    assert.equal(exitCode, 0)
    assert.deepEqual(findings, [])
  } finally {
    rmSync(rootDir, { recursive: true, force: true })
  }
})

test('end-to-end: a stale marker (endpoints no longer equal) fails', () => {
  const rootDir = makeFixtureDir()
  try {
    const srcDir = path.join(rootDir, 'src')
    const screenshotsDir = path.join(rootDir, '__screenshots__')
    mkdirSync(screenshotsDir, { recursive: true })

    writeStoryFile(
      srcDir,
      'Widget',
      'composite-widget',
      `const meta = { id: 'composite-widget' }\nexport default meta\n\nexport const Default: Story = {}\n\n// visual-equivalence: composite-widget--default: used to match, no longer does\nexport const Fixed: Story = {}\n`,
    )
    // A real fix landed: Fixed's baselines no longer match Default's — the marker is now stale.
    writeBaselineSet(screenshotsDir, 'composite-widget--default', 'bytes-a')
    writeBaselineSet(screenshotsDir, 'composite-widget--fixed', 'bytes-b')

    const { findings, exitCode } = runCheck({
      srcDirs: [srcDir],
      screenshotsDir,
      debtJsonPath: noSuchPath(rootDir, 'debt.json'),
      appRoutesSpecPath: noSuchPath(rootDir, 'app-routes.spec.ts'),
    })
    console.log('stale marker — findings:', findings)
    assert.equal(exitCode, 1)
    assert.ok(findings.some((f) => f.includes('stale')))
  } finally {
    rmSync(rootDir, { recursive: true, force: true })
  }
})

test('end-to-end: a debt entry past its fixBy fails', () => {
  const rootDir = makeFixtureDir()
  try {
    const srcDir = path.join(rootDir, 'src')
    const screenshotsDir = path.join(rootDir, '__screenshots__')
    mkdirSync(screenshotsDir, { recursive: true })
    const debtJsonPath = path.join(rootDir, 'debt.json')

    writeStoryFile(
      srcDir,
      'Widget',
      'composite-widget',
      `const meta = { id: 'composite-widget' }\nexport default meta\n\nexport const Default: Story = {}\nexport const Suspect: Story = {}\n`,
    )
    writeBaselineSet(screenshotsDir, 'composite-widget--default', 'same-bytes')
    writeBaselineSet(screenshotsDir, 'composite-widget--suspect', 'same-bytes')
    writeFileSync(
      debtJsonPath,
      JSON.stringify([
        {
          storyIds: ['composite-widget--default', 'composite-widget--suspect'],
          found: '2026-01-01',
          fixOwed: 'should differ, does not yet',
          fixBy: '2026-01-15',
        },
      ]),
    )

    const { findings, exitCode } = runCheck({
      srcDirs: [srcDir],
      screenshotsDir,
      debtJsonPath,
      appRoutesSpecPath: noSuchPath(rootDir, 'app-routes.spec.ts'),
      today: '2026-09-11',
    })
    console.log('expired debt entry — findings:', findings)
    assert.equal(exitCode, 1)
    assert.ok(findings.some((f) => f.includes('overdue')))
  } finally {
    rmSync(rootDir, { recursive: true, force: true })
  }
})

test('end-to-end: a partial match is reported but never fails', () => {
  const rootDir = makeFixtureDir()
  try {
    const srcDir = path.join(rootDir, 'src')
    const screenshotsDir = path.join(rootDir, '__screenshots__')
    mkdirSync(screenshotsDir, { recursive: true })

    writeStoryFile(
      srcDir,
      'Widget',
      'composite-widget',
      `const meta = { id: 'composite-widget' }\nexport default meta\n\nexport const Default: Story = {}\nexport const Narrow: Story = {}\n`,
    )
    // Five of six units match; the sixth (dark-1280) differs — a plausible responsive-collapse
    // shape, not a full match.
    for (const [theme, width] of [
      ['light', 375],
      ['light', 768],
      ['light', 1280],
      ['dark', 375],
      ['dark', 768],
    ]) {
      writeFileSync(
        path.join(screenshotsDir, `composite-widget--default-${theme}-${width}.png`),
        'same-bytes',
      )
      writeFileSync(
        path.join(screenshotsDir, `composite-widget--narrow-${theme}-${width}.png`),
        'same-bytes',
      )
    }
    writeFileSync(path.join(screenshotsDir, 'composite-widget--default-dark-1280.png'), 'bytes-a')
    writeFileSync(path.join(screenshotsDir, 'composite-widget--narrow-dark-1280.png'), 'bytes-b')

    const { findings, infoLines, exitCode } = runCheck({
      srcDirs: [srcDir],
      screenshotsDir,
      debtJsonPath: noSuchPath(rootDir, 'debt.json'),
      appRoutesSpecPath: noSuchPath(rootDir, 'app-routes.spec.ts'),
    })
    console.log('partial match — findings:', findings, 'info:', infoLines)
    assert.equal(exitCode, 0)
    assert.deepEqual(findings, [])
    assert.ok(infoLines.some((line) => line.includes('partial match (5/6)')))
  } finally {
    rmSync(rootDir, { recursive: true, force: true })
  }
})

test('end-to-end: zero stories found fails rather than passing vacuously', () => {
  const rootDir = makeFixtureDir()
  try {
    const srcDir = path.join(rootDir, 'src-does-not-exist')
    const screenshotsDir = path.join(rootDir, '__screenshots__')
    mkdirSync(screenshotsDir, { recursive: true })

    const { findings, exitCode } = runCheck({
      srcDirs: [srcDir],
      screenshotsDir,
      debtJsonPath: noSuchPath(rootDir, 'debt.json'),
      appRoutesSpecPath: noSuchPath(rootDir, 'app-routes.spec.ts'),
    })
    console.log('zero stories — findings:', findings)
    assert.equal(exitCode, 1)
    assert.ok(findings.some((f) => f.includes('zero stories found')))
  } finally {
    rmSync(rootDir, { recursive: true, force: true })
  }
})

test("end-to-end: an unmapped baseline (a moved or renamed component's stale capture) fails", () => {
  const rootDir = makeFixtureDir()
  try {
    const srcDir = path.join(rootDir, 'src')
    const screenshotsDir = path.join(rootDir, '__screenshots__')
    mkdirSync(screenshotsDir, { recursive: true })

    writeStoryFile(
      srcDir,
      'Widget',
      'composite-widget',
      `const meta = { id: 'composite-widget' }\nexport default meta\n\nexport const Default: Story = {}\n`,
    )
    writeBaselineSet(screenshotsDir, 'composite-widget--default', 'same-bytes')
    writeBaselineSet(screenshotsDir, 'composite-ghost--gone', 'same-bytes')

    const { findings, exitCode } = runCheck({
      srcDirs: [srcDir],
      screenshotsDir,
      debtJsonPath: noSuchPath(rootDir, 'debt.json'),
      appRoutesSpecPath: noSuchPath(rootDir, 'app-routes.spec.ts'),
    })
    console.log('unmapped baseline — findings:', findings)
    assert.equal(exitCode, 1)
    assert.ok(findings.some((f) => f.includes('unmapped baseline')))
  } finally {
    rmSync(rootDir, { recursive: true, force: true })
  }
})

// ---------------------------------------------------------------------------------------------
// The real, committed tree.
// ---------------------------------------------------------------------------------------------

test('runCheck against the real, committed tree passes (every full-set match is documented)', () => {
  const { findings, infoLines, exitCode } = runCheck()
  if (exitCode !== 0) console.log('real tree — findings:', findings)
  console.log('real tree — info:', infoLines)
  assert.deepEqual(findings, [])
  assert.equal(exitCode, 0)
})
