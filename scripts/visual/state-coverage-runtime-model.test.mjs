// T693 piece 4: the manifest's own rules — keys against the built index (set equality plus
// `importPath` and `exportName` agreement), entry comparison, the partial-pass merge — proved on
// small literals, no browser. A story added, removed or renamed without its entry fails
// `findKeyProblems` whatever a diff selected; that is the claim the PR job's browserless step makes.
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'
import {
  MANIFEST_PATH,
  REWRITE_COMMAND,
  TRACKED_DIRECTORIES,
  buildEntry,
  describeEntryDifferences,
  describeKeyProblems,
  findEntryDifferences,
  findIndexProblem,
  findKeyProblems,
  manifestNeedsWrite,
  mergeManifest,
  selectRuntimeStories,
  serializeManifest,
} from './state-coverage-runtime-model.mjs'
import { FIXTURE_TAG } from './story-index.mjs'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')

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

// One tracked-primitive instance, in the shape the pass records.
const inst = (component, variant = null, size = null, disabledAt = []) => ({
  component,
  variant,
  size,
  disabledAt,
})
const record = { mounts: [inst('Button', 'secondary', 'md')] }
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
    375: { mounts: [inst('Button', 'primary', 'lg')] },
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

// ---- B1: `--changed` must see what an entry depends on -------------------------------------------

const BUTTON_FILE = 'packages/design-system/src/primitives/Button/index.tsx'
const BUTTON_DIFF = [BUTTON_FILE]
const MANIFEST_DIFF = [MANIFEST_PATH]
const ROW_FILE = 'packages/design-system/src/composites/Row/index.tsx'
const ROW_DIFF = [ROW_FILE]

// Stories whose own directory no diff below touches, so selection (a) — what `selectChangedStories`
// picks — never reaches them: whatever is selected is selected by an entry's own citations.
const here = (id, name) => story(id, `./src/screens/${name}/${name}.stories.tsx`, name, [])
const S_FORCE = here('screens-force--one', 'Force')
const S_FOCUS = here('screens-focus--one', 'Focus')
const S_DISABLED = here('screens-disabled--one', 'Disabled')
const S_MOUNT = here('screens-mount--one', 'Mount')
const S_PLACED = here('screens-placed--one', 'Placed')
const S_PLAIN = here('screens-plain--one', 'Plain')
const ALL = [S_FORCE, S_FOCUS, S_DISABLED, S_MOUNT, S_PLACED, S_PLAIN]

const widthsOf = (rec) => ({ 375: rec, 768: rec, 1280: rec })
const entryWith = (s, rec) => ({
  importPath: s.importPath,
  exportName: s.exportName,
  widths: widthsOf(rec),
})
// Entries that each cite one thing, and nothing a Button, Link, Field or Menu directory could select.
const base = () => ({
  [S_FORCE.id]: entryWith(S_FORCE, {
    mounts: [],
    force: { count: 1, stamp: `${ROW_FILE}:10`, placedBy: null },
  }),
  [S_FOCUS.id]: entryWith(S_FOCUS, {
    mounts: [],
    focus: { stamp: `${ROW_FILE}:20`, placedBy: null },
  }),
  [S_DISABLED.id]: entryWith(S_DISABLED, {
    mounts: [inst('Menu', 'actions', null, [`${ROW_FILE}:30`])],
  }),
  [S_MOUNT.id]: entryWith(S_MOUNT, { mounts: [inst('Menu', 'actions')] }),
  [S_PLACED.id]: entryWith(S_PLACED, {
    mounts: [],
    force: { count: 1, stamp: null, placedBy: inst('Field', null, 'md') },
  }),
  [S_PLAIN.id]: entryWith(S_PLAIN, { mounts: [] }),
})
const selectIds = (diff, manifest = base(), baseManifest = manifest, stories = ALL) =>
  selectRuntimeStories({ stories, manifest, baseManifest, diff }).stories.map((s) => s.id)

test('selection (a): what selectChangedStories selects today is still selected', () => {
  const own = story('own--one', './src/composites/Row/Row.stories.tsx', 'One')
  const manifest = { ...base(), [own.id]: entryWith(own, { mounts: [] }) }
  assert.deepEqual(selectIds(ROW_DIFF, manifest, manifest, [...ALL, own]).includes(own.id), true)
  const global = selectRuntimeStories({
    stories: ALL,
    manifest: base(),
    baseManifest: base(),
    diff: ['packages/design-system/tokens/color.json'],
  })
  assert.equal(global.stories.length, ALL.length)
})

test('selection (b): an entry citing a stamp whose file is in the diff is selected — a force stamp, a focus stamp and a disabledAt stamp, each on its own', () => {
  assert.deepEqual(selectIds(ROW_DIFF).sort(), [S_DISABLED.id, S_FOCUS.id, S_FORCE.id].sort())
  for (const [id, label] of [
    [S_FORCE.id, 'force stamp'],
    [S_FOCUS.id, 'focus stamp'],
    [S_DISABLED.id, 'disabledAt stamp'],
  ]) {
    const only = { [id]: base()[id] }
    const stories = ALL.filter((s) => s.id === id)
    assert.deepEqual(selectIds(ROW_DIFF, only, only, stories), [id], label)
  }
})

test('selection (b): the stamp is matched by its file, never by a prefix of another path', () => {
  assert.deepEqual(selectIds([`${ROW_FILE}x`]), [])
  assert.deepEqual(selectIds(['packages/design-system/src/composites/Row/index.ts']), [])
})

test('selection (c): an entry that mounts or is placed by a tracked primitive is selected when its directory has a file in the diff', () => {
  assert.deepEqual(
    selectIds(['packages/design-system/src/primitives/Menu/index.tsx']).sort(),
    [S_DISABLED.id, S_MOUNT.id].sort(),
    'mounts only (Menu), no stamp cited',
  )
  assert.deepEqual(
    selectIds(['packages/design-system/src/primitives/Field/Field.css']),
    [S_PLACED.id],
    'placed by only (Field), mounts empty',
  )
  assert.deepEqual(
    selectIds(['packages/design-system/src/primitives/Link/index.tsx']),
    [],
    'no entry mounts a Link',
  )
})

test('selection (c): the table of tracked directories is the preview registry', () => {
  const preview = readFileSync(
    path.join(rootDir, 'packages/design-system/.storybook/preview.tsx'),
    'utf8',
  )
  const registered = Object.fromEntries(
    [...preview.matchAll(/(\w+): \{\s*component: \w+,\s*directory: '([^']+)'/g)].map((m) => [
      m[1],
      m[2],
    ]),
  )
  assert.deepEqual(TRACKED_DIRECTORIES, registered)
})

test('selection (d): an entry that differs from the diff base is selected — a changed stamp, a changed placedBy, a removed entry', () => {
  const before = base()
  const stamp = base()
  stamp[S_FORCE.id].widths[768].force.stamp = `${ROW_FILE}:11`
  assert.deepEqual(selectIds(MANIFEST_DIFF, stamp, before), [S_FORCE.id], 'changed stamp')

  const placed = base()
  placed[S_PLACED.id].widths[1280].force.placedBy = inst('Field', null, 'lg')
  assert.deepEqual(selectIds(MANIFEST_DIFF, placed, before), [S_PLACED.id], 'changed placedBy')

  const removed = base()
  delete removed[S_PLAIN.id]
  assert.deepEqual(selectIds(MANIFEST_DIFF, removed, before), [S_PLAIN.id], 'removed entry')
})

test('selection (d): a manifest absent at the base makes every entry differ; an identical one makes none', () => {
  assert.deepEqual(selectIds(MANIFEST_DIFF, base(), null).sort(), ALL.map((s) => s.id).sort())
  assert.deepEqual(selectIds(MANIFEST_DIFF, base(), base()), [])
})

test('selection contrast: an unrelated composite and a docs file select nothing a Button stamp or mount cites', () => {
  const manifest = {
    [S_MOUNT.id]: entryWith(S_MOUNT, {
      mounts: [inst('Button', 'primary', 'md')],
      force: { count: 1, stamp: `${BUTTON_FILE}:213`, placedBy: inst('Button', 'primary', 'md') },
    }),
  }
  const stories = [S_MOUNT]
  assert.deepEqual(
    selectIds(
      ['packages/design-system/src/composites/Unrelated/index.tsx'],
      manifest,
      manifest,
      stories,
    ),
    [],
  )
  assert.deepEqual(selectIds(['docs/data-sources.md'], manifest, manifest, stories), [])
  assert.deepEqual(selectIds(BUTTON_DIFF, manifest, manifest, stories), [S_MOUNT.id])
})

test('selection, against the committed manifest: a diff in Button selects every entry that cites a Button stamp or mounts a Button', () => {
  const manifest = JSON.parse(readFileSync(path.join(rootDir, MANIFEST_PATH), 'utf8'))
  const stories = Object.entries(manifest).map(([id, e]) => ({
    id,
    importPath: e.importPath,
    exportName: e.exportName,
  }))
  const citing = Object.keys(manifest).filter((id) =>
    JSON.stringify(manifest[id]).includes('primitives/Button/index.tsx'),
  )
  assert.ok(citing.length >= 35, `expected at least 35 Button-citing entries, saw ${citing.length}`)
  const picked = new Set(selectIds(BUTTON_DIFF, manifest, manifest, stories))
  const missed = citing.filter((id) => !picked.has(id))
  assert.deepEqual(missed, [], 'entries that cite a Button stamp but the selection missed')
  const mounting = Object.keys(manifest).filter((id) =>
    JSON.stringify(manifest[id]).includes('"component":"Button"'),
  )
  assert.deepEqual(
    mounting.filter((id) => !picked.has(id)),
    [],
  )
})

test('selection, against the committed manifest: the instances are structured objects, never strings', () => {
  const manifest = JSON.parse(readFileSync(path.join(rootDir, MANIFEST_PATH), 'utf8'))
  const bad = []
  for (const [id, e] of Object.entries(manifest)) {
    for (const rec of Object.values(e.widths)) {
      const all = [...rec.mounts, rec.force?.placedBy, rec.focus?.placedBy].filter((x) => x != null)
      for (const i of all) {
        if (typeof i !== 'object' || !Array.isArray(i.disabledAt)) bad.push(id)
        else if (JSON.stringify(Object.keys(i)) !== '["component","variant","size","disabledAt"]')
          bad.push(id)
      }
    }
  }
  assert.deepEqual([...new Set(bad)], [])
})

test('the committed manifest records disabled as rendered: a Menu with a disabled or loading item differs from a plain one', () => {
  const manifest = JSON.parse(readFileSync(path.join(rootDir, MANIFEST_PATH), 'utf8'))
  const disabledAt = (id) => manifest[id].widths['1280'].mounts[0].disabledAt
  assert.notDeepEqual(disabledAt('primitives-menu--actions-with-disabled-item'), [])
  assert.deepEqual(disabledAt('primitives-menu--selection'), [])
  assert.notDeepEqual(
    disabledAt('primitives-menu--loading-item'),
    [],
    'a loading item is aria-disabled in the DOM',
  )
  assert.notDeepEqual(
    disabledAt('primitives-menu--empty'),
    [],
    "an empty Menu's trigger is aria-disabled",
  )
})

test('every failure of a --plants run names --plants; --changed names itself; the keys check names the full rewrite', () => {
  const diffs = findEntryDifferences({ manifest: manifestOf(A), fresh: { 'b--two': entryOf(B) } })
  assert.match(describeEntryDifferences(diffs, 'plants').join('\n'), /--write --plants/)
  assert.match(describeEntryDifferences(diffs, 'changed').join('\n'), /--write --changed/)
  assert.match(describeEntryDifferences(diffs).join('\n'), new RegExp(`${REWRITE_COMMAND}\``))
  const problems = findKeyProblems({ manifest: manifestOf(A), index: indexOf(A, B) })
  assert.match(describeKeyProblems(problems).join('\n'), /--plants/)
})

// ---- B3: a zero-story index writes nothing -------------------------------------------------------

test('findIndexProblem: an index with no published story is refused, whatever else it lists', () => {
  assert.match(findIndexProblem({ entries: {} }), /no stories/)
  assert.match(findIndexProblem(indexOf(DOCS)), /no stories/)
  assert.match(
    findIndexProblem(indexOf(PLANT, DOCS)),
    /no stories/,
    'a build with only plants is not a build',
  )
  assert.equal(findIndexProblem(indexOf(A)), null)
})

test('the reproduction: merging a pass over an empty index would empty the manifest — which is why the driver refuses it first', () => {
  assert.deepEqual(
    Object.keys(mergeManifest({ manifest: manifestOf(A, B), fresh: {}, index: { entries: {} } })),
    [],
  )
})

test('contrast: an empty selection over a non-empty index merges to the committed manifest and asks for no write', () => {
  const manifest = manifestOf(A, B, PLANT)
  const merged = mergeManifest({ manifest, fresh: {}, index: indexOf(A, B, PLANT) })
  assert.equal(JSON.stringify(merged), JSON.stringify(manifest))
  assert.equal(manifestNeedsWrite(merged, manifest, true), false)
  assert.equal(
    manifestNeedsWrite(merged, manifest, false),
    true,
    'a missing file is always written',
  )
  assert.equal(
    manifestNeedsWrite(
      mergeManifest({ manifest: manifestOf(A, B), fresh: {}, index: indexOf(A) }),
      manifestOf(A, B),
      true,
    ),
    true,
    'a story the index lost is dropped',
  )
})

test('the driver refuses a zero-story index in every mode before selecting, and names the build command', () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'state-coverage-runtime-'))
  try {
    const indexFile = path.join(dir, 'index.json')
    const manifestFile = path.join(dir, 'manifest.json')
    writeFileSync(indexFile, JSON.stringify({ v: 5, entries: {} }))
    writeFileSync(manifestFile, JSON.stringify(manifestOf(A)))
    for (const mode of [
      [],
      ['--write'],
      ['--changed'],
      ['--write', '--changed'],
      ['--plants'],
      ['--keys'],
    ]) {
      const result = spawnSync(
        process.execPath,
        [path.join(rootDir, 'scripts/visual/state-coverage-runtime.mjs'), ...mode],
        {
          encoding: 'utf8',
          env: {
            ...process.env,
            STATE_COVERAGE_RUNTIME_INDEX: indexFile,
            STATE_COVERAGE_RUNTIME_MANIFEST: manifestFile,
          },
        },
      )
      assert.equal(
        result.status,
        1,
        `${mode.join(' ') || '(no flag)'}: ${result.stdout}${result.stderr}`,
      )
      assert.match(result.stdout, /state-coverage-runtime: .*no stories/)
      assert.equal(
        readFileSync(manifestFile, 'utf8'),
        JSON.stringify(manifestOf(A)),
        'the manifest is untouched',
      )
    }
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})
