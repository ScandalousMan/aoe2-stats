// T693 piece 4: the manifest's own rules — keys against the built index (set equality plus
// `importPath` and `exportName` agreement), entry comparison, the partial-pass merge — proved on
// small literals, no browser. A story added, removed or renamed without its entry fails
// `findKeyProblems` whatever a diff selected; that is the claim the PR job's browserless step makes.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  REWRITE_COMMAND,
  buildEntry,
  describeEntryDifferences,
  describeKeyProblems,
  findEntryDifferences,
  findKeyProblems,
  mergeManifest,
  serializeManifest,
} from './state-coverage-runtime-model.mjs'
import { FIXTURE_TAG } from './story-index.mjs'

const story = (id, importPath, exportName, tags = []) => ({
  type: 'story',
  id,
  importPath,
  exportName,
  tags,
})
const A = story('a--one', './src/A.stories.tsx', 'One')
const B = story('b--two', './src/B.stories.tsx', 'Two')
const PLANT = story('c--plant', './.storybook/fixtures/P.stories.tsx', 'Plant', [FIXTURE_TAG])
const DOCS = { type: 'docs', id: 'a--docs', importPath: './src/A.stories.tsx' }
const indexOf = (...entries) => ({ entries: Object.fromEntries(entries.map((e) => [e.id, e])) })

const record = { mounts: ['Button:secondary|md'] }
const entryOf = (s) => buildEntry(s, { 1280: record, 375: record, 768: record })
const manifestOf = (...stories) => Object.fromEntries(stories.map((s) => [s.id, entryOf(s)]))

test('buildEntry carries importPath and exportName from the index and orders widths numerically', () => {
  const entry = entryOf(A)
  assert.equal(entry.importPath, './src/A.stories.tsx')
  assert.equal(entry.exportName, 'One')
  assert.deepEqual(Object.keys(entry.widths), ['375', '768', '1280'])
})

test('findKeyProblems: agreement, including a plant and ignoring a docs entry, is clean', () => {
  assert.deepEqual(
    findKeyProblems({ manifest: manifestOf(A, B, PLANT), index: indexOf(A, B, PLANT, DOCS) }),
    [],
  )
})

test('findKeyProblems: a story added without its entry is reported', () => {
  const problems = findKeyProblems({ manifest: manifestOf(A), index: indexOf(A, B) })
  assert.deepEqual(
    problems.map((p) => [p.kind, p.id]),
    [['missing-entry', 'b--two']],
  )
})

test('findKeyProblems: a story removed without dropping its entry is reported', () => {
  const problems = findKeyProblems({ manifest: manifestOf(A, B), index: indexOf(A) })
  assert.deepEqual(
    problems.map((p) => [p.kind, p.id]),
    [['extra-entry', 'b--two']],
  )
})

test('findKeyProblems: a rename is a removal and an addition; an importPath or exportName that moved is reported', () => {
  const renamed = story('b--three', './src/B.stories.tsx', 'Three')
  assert.deepEqual(
    findKeyProblems({ manifest: manifestOf(A, B), index: indexOf(A, renamed) }).map((p) => p.kind),
    ['missing-entry', 'extra-entry'],
  )
  const moved = story('b--two', './src/composites/B.stories.tsx', 'Two')
  assert.deepEqual(
    findKeyProblems({ manifest: manifestOf(A, B), index: indexOf(A, moved) }).map((p) => p.kind),
    ['import-path'],
  )
  const reexported = story('b--two', './src/B.stories.tsx', 'TwoAgain')
  assert.deepEqual(
    findKeyProblems({ manifest: manifestOf(A, B), index: indexOf(A, reexported) }).map(
      (p) => p.kind,
    ),
    ['export-name'],
  )
})

test('every failure names the command that rewrites the manifest', () => {
  const problems = findKeyProblems({ manifest: manifestOf(A), index: indexOf(A, B) })
  assert.match(describeKeyProblems(problems).join('\n'), new RegExp(REWRITE_COMMAND))
  const diffs = findEntryDifferences({ manifest: manifestOf(A), fresh: { 'b--two': entryOf(B) } })
  assert.match(describeEntryDifferences(diffs).join('\n'), new RegExp(REWRITE_COMMAND))
})

test('findEntryDifferences compares only the ids the pass ran, ignoring key order', () => {
  const manifest = manifestOf(A, B)
  assert.deepEqual(findEntryDifferences({ manifest, fresh: { [A.id]: entryOf(A) } }), [])
  const shifted = buildEntry(A, {
    375: { mounts: ['Button:primary|lg'] },
    768: record,
    1280: record,
  })
  const diffs = findEntryDifferences({ manifest, fresh: { [A.id]: shifted, [B.id]: entryOf(B) } })
  assert.deepEqual(
    diffs.map((d) => d.id),
    [A.id],
  )
  const reordered = { widths: entryOf(A).widths, exportName: 'One', importPath: A.importPath }
  assert.deepEqual(findEntryDifferences({ manifest, fresh: { [A.id]: reordered } }), [])
})

test('mergeManifest rewrites only the entries the pass ran, drops a story the index lost, keeps id order', () => {
  const manifest = { ...manifestOf(A, B), 'gone--x': entryOf(story('gone--x', './x', 'X')) }
  const shifted = buildEntry(B, { 375: { mounts: [] }, 768: { mounts: [] }, 1280: { mounts: [] } })
  const merged = mergeManifest({ manifest, fresh: { [B.id]: shifted }, index: indexOf(A, B) })
  assert.deepEqual(Object.keys(merged), [A.id, B.id])
  assert.deepEqual(merged[A.id], manifest[A.id])
  assert.deepEqual(merged[B.id], shifted)
  assert.deepEqual(
    findKeyProblems({ manifest: merged, index: indexOf(A, B) }),
    [],
    'a rewrite leaves the keys check green',
  )
})

test('mergeManifest adds an entry for a story the manifest had none for', () => {
  const merged = mergeManifest({
    manifest: manifestOf(A),
    fresh: { [B.id]: entryOf(B) },
    index: indexOf(A, B),
  })
  assert.deepEqual(Object.keys(merged), [A.id, B.id])
})

test('serializeManifest reads back as the same value', () => {
  const manifest = manifestOf(A, B, PLANT)
  assert.deepEqual(JSON.parse(serializeManifest(manifest)), manifest)
  assert.deepEqual(JSON.parse(serializeManifest({})), {})
})
