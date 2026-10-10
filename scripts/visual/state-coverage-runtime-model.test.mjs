// T693 piece 4: the manifest's own rules — keys against the built index (set equality plus
// `importPath` and `exportName` agreement), entry comparison, the partial-pass merge — proved on
// small literals, no browser. A story added, removed or renamed without its entry fails
// `findKeyProblems` whatever a diff selected; that is the claim the PR job's browserless step makes.
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'
import {
  MANIFEST_PATH,
  REWRITE_COMMAND,
  buildEntry,
  describeEntryDifferences,
  describeKeyProblems,
  findEntryDifferences,
  findFixtureProblem,
  findIndexProblem,
  findKeyProblems,
  manifestNeedsWrite,
  mergeManifest,
  parseArgs,
  parseManifest,
  selectRuntimeStories,
  serializeManifest,
} from './state-coverage-runtime-model.mjs'
import { FIXTURE_TAG, FULL_PAGE_TAG } from './story-index.mjs'

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
const record = { clip: false, fullPage: false, mounts: [inst('Button', 'secondary', 'md')] }
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

test('buildEntry keeps the capture frame of every width in its own record (T703)', () => {
  const entry = buildEntry(A, {
    375: { ...record, clip: true },
    768: record,
    1280: { ...record, fullPage: true },
  })
  assert.deepEqual(
    Object.entries(entry.widths).map(([w, r]) => [w, r.clip, r.fullPage]),
    [
      ['375', true, false],
      ['768', false, false],
      ['1280', false, true],
    ],
  )
})

// The full-page half of the frame is the built index's tag, so the browserless key check holds it: a tag
// added or removed without a rewrite is a disagreement, and a clip (a browser's observation) is not.
test('findKeyProblems: a visual-full-page tag the entry does not record, and one it records that the index lacks, are reported at each width', () => {
  const tagged = story('a--one', './src/A.stories.tsx', 'One', [FULL_PAGE_TAG])
  const added = findKeyProblems({ manifest: manifestOf(A), index: indexOf(tagged) })
  assert.deepEqual(
    added.map((p) => [p.kind, p.id, p.detail.split(' ')[2]]),
    [
      ['full-page', 'a--one', '375px'],
      ['full-page', 'a--one', '768px'],
      ['full-page', 'a--one', '1280px'],
    ],
  )
  const removed = findKeyProblems({
    manifest: {
      'a--one': buildEntry(tagged, {
        375: { ...record, fullPage: true },
        768: { ...record, fullPage: true },
        1280: { ...record, fullPage: true },
      }),
    },
    index: indexOf(A),
  })
  assert.equal(removed.length, 3)
  assert.match(removed[0].detail, /does not tag the story `visual-full-page`/)
})

test('findKeyProblems: agreement on the tag, and a recorded clip, are clean', () => {
  const tagged = story('a--one', './src/A.stories.tsx', 'One', [FULL_PAGE_TAG])
  const manifest = {
    'a--one': buildEntry(tagged, {
      375: { ...record, fullPage: true, clip: true },
      768: { ...record, fullPage: true },
      1280: { ...record, fullPage: true },
    }),
  }
  assert.deepEqual(findKeyProblems({ manifest, index: indexOf(tagged) }), [])
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
  const reordered = {
    widths: entryOf(A).widths,
    files: [],
    exportName: 'One',
    importPath: A.importPath,
  }
  assert.deepEqual(findEntryDifferences({ manifest, fresh: { [A.id]: reordered } }), [])
})

test('mergeManifest rewrites only the entries the pass ran, drops a story the index lost, keeps id order', () => {
  const manifest = { ...manifestOf(A, B), 'gone--x': entryOf(story('gone--x', './x', 'X')) }
  const empty = { ...record, mounts: [] }
  const shifted = buildEntry(B, { 375: empty, 768: empty, 1280: empty })
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

test('serializeManifest keeps an entry’s oneThemeFiles after files, and writes none for an entry without it', () => {
  const withOne = { ...entryOf(A), oneThemeFiles: ['b.tsx'] }
  const text = serializeManifest({ [A.id]: withOne, [B.id]: entryOf(B) })
  const read = JSON.parse(text)
  assert.deepEqual(read[A.id].oneThemeFiles, ['b.tsx'])
  assert.deepEqual(Object.keys(read[A.id]), [
    'importPath',
    'exportName',
    'files',
    'oneThemeFiles',
    'widths',
  ])
  assert.deepEqual(Object.keys(read[B.id]), ['importPath', 'exportName', 'files', 'widths'])
})

// ---- B1: `--changed` selects by what an entry RECORDED it rendered ---------------------------------
//
// Each entry carries `files`: the sorted unique repository-rooted paths of every stamped file that
// rendered an element under the story (portals included), unioned across widths. A diff selects an
// entry when it names one of those files — one rule, which subsumes "the entry cites a stamp in the
// file" and "the entry mounts a primitive whose directory changed".

const BUTTON_FILE = 'packages/design-system/src/primitives/Button/index.tsx'
const BUTTON_DIFF = [BUTTON_FILE]
const MANIFEST_DIFF = [MANIFEST_PATH]
const ROW_FILE = 'packages/design-system/src/composites/Row/index.tsx'
const ROW_DIFF = [ROW_FILE]
// A file the preview does not reach through module specifiers (T710: a diff on one the preview reaches,
// `Menu`'s among them, selects every story, so it could not show a selection made by `files` alone).
const TABLE_FILE = 'packages/design-system/src/composites/Table/index.tsx'
const PREVIEW_REACHED_FILE = 'packages/design-system/src/primitives/Menu/index.tsx'

// Stories whose own directory no diff below touches, so selection (a) — what `selectChangedStories`
// picks — never reaches them: whatever is selected is selected by an entry's own `files`.
const here = (id, name) => story(id, `./src/screens/${name}/${name}.stories.tsx`, name, [])
const S_ROW = here('screens-row--one', 'RowScreen')
const S_MENU = here('screens-menu--one', 'MenuScreen')
const S_BOTH = here('screens-both--one', 'BothScreen')
const S_NONE = here('screens-none--one', 'NoneScreen')
const ALL = [S_ROW, S_MENU, S_BOTH, S_NONE]

const widthsOf = (rec) => ({ 375: rec, 768: rec, 1280: rec })
const entryWith = (s, files, rec = { mounts: [] }) => ({
  importPath: s.importPath,
  exportName: s.exportName,
  files,
  widths: widthsOf(rec),
})
const base = () => ({
  [S_ROW.id]: entryWith(S_ROW, [ROW_FILE]),
  [S_MENU.id]: entryWith(S_MENU, [TABLE_FILE]),
  [S_BOTH.id]: entryWith(S_BOTH, [TABLE_FILE, ROW_FILE]),
  [S_NONE.id]: entryWith(S_NONE, []),
})
const select = (diff, manifest = base(), baseManifest = manifest, stories = ALL) =>
  selectRuntimeStories({ stories, manifest, baseManifest, diff })
const selectIds = (...args) => select(...args).stories.map((s) => s.id)

test('buildEntry records `files` as the sorted union across widths, and keeps it out of the per-width records', () => {
  const rec = (files) => ({ mounts: [], files })
  const entry = buildEntry(A, {
    375: rec(['b.tsx', 'a.tsx']),
    768: rec(['a.tsx']),
    1280: rec(['c.tsx', 'a.tsx']),
  })
  assert.deepEqual(entry.files, ['a.tsx', 'b.tsx', 'c.tsx'])
  assert.deepEqual(Object.keys(entry), ['importPath', 'exportName', 'files', 'widths'])
  assert.deepEqual(entry.widths['375'], { mounts: [] })
  assert.deepEqual(buildEntry(A, { 375: { mounts: [] } }).files, [])
})

test('buildEntry unions `oneThemeFiles` across widths into the entry, keeps it out of the per-width records, and writes the key only when it is not empty', () => {
  const entry = buildEntry(A, {
    375: { mounts: [], files: ['a.tsx', 'b.tsx'], oneThemeFiles: ['b.tsx'] },
    768: { mounts: [], files: ['a.tsx'] },
    1280: { mounts: [], files: ['a.tsx', 'c.tsx'], oneThemeFiles: ['c.tsx'] },
  })
  assert.deepEqual(entry.oneThemeFiles, ['b.tsx', 'c.tsx'])
  assert.deepEqual(Object.keys(entry), [
    'importPath',
    'exportName',
    'files',
    'oneThemeFiles',
    'widths',
  ])
  assert.deepEqual(entry.widths['375'], { mounts: [] })
  // The contrast: no width names one, so the entry has no such key and is byte-identical to today's.
  const plain = buildEntry(A, { 375: { mounts: [], files: ['a.tsx'] } })
  assert.deepEqual(Object.keys(plain), ['importPath', 'exportName', 'files', 'widths'])
})

test('buildEntry keeps `focusDiffersByTheme` in the per-width record, where the checker reads it', () => {
  const entry = buildEntry(A, {
    375: { mounts: [], focus: null, focusDiffersByTheme: true },
    768: { mounts: [] },
  })
  assert.deepEqual(entry.widths['375'], { mounts: [], focus: null, focusDiffersByTheme: true })
  assert.deepEqual(entry.widths['768'], { mounts: [] })
})

test('selection (a): what selectChangedStories selects today is still selected', () => {
  const own = story('own--one', './src/composites/Row/Row.stories.tsx', 'One')
  const manifest = { ...base(), [own.id]: entryWith(own, []) }
  const picked = select(ROW_DIFF, manifest, manifest, [...ALL, own])
  assert.deepEqual(picked.rules.get(own.id), ['story-files'])
  const global = selectRuntimeStories({
    stories: ALL,
    manifest: base(),
    baseManifest: base(),
    diff: ['packages/design-system/tokens/color.json'],
  })
  assert.equal(global.stories.length, ALL.length)
})

test('selection (b): an entry whose recorded files name a file in the diff is selected, and no other', () => {
  assert.deepEqual(selectIds(ROW_DIFF).sort(), [S_BOTH.id, S_ROW.id].sort())
  assert.deepEqual(selectIds([TABLE_FILE]).sort(), [S_BOTH.id, S_MENU.id].sort())
  assert.deepEqual(select(ROW_DIFF).rules.get(S_ROW.id), ['files'])
})

test('selection (a), T710: a file the preview reaches selects every story, whatever the entries recorded', () => {
  assert.deepEqual(selectIds([PREVIEW_REACHED_FILE]).sort(), ALL.map((s) => s.id).sort())
  assert.deepEqual(selectIds([TABLE_FILE]).sort(), [S_BOTH.id, S_MENU.id].sort())
})

test('selection (b): the file is matched whole, never by a prefix, a suffix or a directory of another path', () => {
  assert.deepEqual(selectIds([`${ROW_FILE}x`]), [])
  assert.deepEqual(selectIds(['packages/design-system/src/composites/Row/index.ts']), [])
  assert.deepEqual(selectIds(['packages/design-system/src/composites/Row/Row.test.tsx']), [])
  assert.deepEqual(selectIds(['packages/design-system/src/composites/Row/']), [])
})

test('selection (b): an entry with no recorded files — an old manifest, a docs-only story — is selected by nothing here', () => {
  const manifest = base()
  delete manifest[S_ROW.id].files
  assert.deepEqual(selectIds(ROW_DIFF, manifest), [S_BOTH.id])
})

test('selection (d): an entry that differs from the diff base is selected — a changed stamp, a changed placedBy, a changed file list, a removed entry', () => {
  const before = base()
  const stamp = base()
  stamp[S_ROW.id].widths[768].force = { count: 1, stamp: `${ROW_FILE}:11`, placedBy: null }
  assert.deepEqual(selectIds(MANIFEST_DIFF, stamp, before), [S_ROW.id], 'changed stamp')

  const placed = base()
  placed[S_MENU.id].widths[1280].force = {
    count: 1,
    stamp: null,
    placedBy: inst('Field', null, 'lg'),
  }
  assert.deepEqual(selectIds(MANIFEST_DIFF, placed, before), [S_MENU.id], 'changed placedBy')

  const files = base()
  files[S_NONE.id].files = [ROW_FILE]
  assert.deepEqual(selectIds(MANIFEST_DIFF, files, before), [S_NONE.id], 'changed files')

  const removed = base()
  delete removed[S_NONE.id]
  assert.deepEqual(selectIds(MANIFEST_DIFF, removed, before), [S_NONE.id], 'removed entry')
})

test('selection (d): a manifest absent at the base makes every entry differ; an identical one makes none', () => {
  assert.deepEqual(selectIds(MANIFEST_DIFF, base(), null).sort(), ALL.map((s) => s.id).sort())
  assert.deepEqual(selectIds(MANIFEST_DIFF, base(), base()), [])
})

test('selection contrast: an unrelated composite, a docs file and a test file select nothing', () => {
  for (const file of [
    'packages/design-system/src/composites/Unrelated/index.tsx',
    'docs/data-sources.md',
    'packages/design-system/src/composites/Row/Row.test.tsx',
  ]) {
    assert.deepEqual(selectIds([file]), [], file)
  }
})

// The throwaway-repository tests need real git: a rename must list both of its sides.
function gitRepo() {
  const dir = mkdtempSync(path.join(tmpdir(), 'runtime-selection-'))
  const git = (...args) => {
    const r = spawnSync('git', args, { cwd: dir, encoding: 'utf8' })
    assert.equal(r.status, 0, `git ${args.join(' ')}: ${r.stderr}`)
    return r.stdout
  }
  git('init', '-q', '-b', 'main')
  git('config', 'user.email', 'test@example.com')
  git('config', 'user.name', 'test')
  git('config', 'commit.gpgsign', 'false')
  return { dir, git }
}

test('a renamed file selects the entries that recorded its OLD path: changedFiles lists both sides of a rename', async () => {
  const { dir, git } = gitRepo()
  try {
    const old = 'packages/design-system/src/primitives/Tooltip/index.tsx'
    mkdirSync(path.dirname(path.join(dir, old)), { recursive: true })
    writeFileSync(path.join(dir, old), 'export const Tooltip = () => null\n'.repeat(20))
    git('add', '-A')
    git('commit', '-q', '-m', 'base')
    git('checkout', '-q', '-b', 'feature')
    const renamed = 'packages/design-system/src/primitives/Hint/index.tsx'
    mkdirSync(path.dirname(path.join(dir, renamed)), { recursive: true })
    git('mv', old, renamed)
    git('commit', '-q', '-m', 'rename')

    const { changedFiles } = await import('./story-selection.mjs')
    const previous = process.env.VISUAL_BASE_REF
    process.env.VISUAL_BASE_REF = 'main'
    let files
    try {
      files = changedFiles({ cwd: dir, prefix: 'test', unscopedCommand: 'x' })
    } finally {
      if (previous === undefined) delete process.env.VISUAL_BASE_REF
      else process.env.VISUAL_BASE_REF = previous
    }
    assert.deepEqual([...files].sort(), [old, renamed].sort())

    const consumer = here('screens-consumer--one', 'ConsumerScreen')
    const bystander = here('screens-bystander--one', 'BystanderScreen')
    const manifest = {
      [consumer.id]: entryWith(consumer, [old]),
      [bystander.id]: entryWith(bystander, [ROW_FILE]),
    }
    assert.deepEqual(
      selectIds(files, manifest, manifest, [consumer, bystander]),
      [consumer.id],
      'the entry that recorded the old path is selected',
    )
    // The reproduction: with a rename-detecting diff only the new path is listed, and nothing selects.
    assert.deepEqual(selectIds([renamed], manifest, manifest, [consumer, bystander]), [])
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('selection, against the committed manifest: every entry records files; a diff on a file selects exactly the entries that recorded it', () => {
  const manifest = JSON.parse(readFileSync(path.join(rootDir, MANIFEST_PATH), 'utf8'))
  const stories = Object.entries(manifest).map(([id, e]) => ({
    id,
    importPath: e.importPath,
    exportName: e.exportName,
  }))
  const missing = Object.keys(manifest).filter((id) => !Array.isArray(manifest[id].files))
  assert.deepEqual(missing, [], 'entries with no `files`')
  for (const id of Object.keys(manifest)) {
    const files = manifest[id].files
    assert.deepEqual(files, [...new Set(files)].sort(), `${id}: files are sorted and unique`)
    for (const file of files) assert.match(file, /^packages\/design-system\/src\/.+\.tsx?$/, id)
  }

  const recorded = Object.keys(manifest).filter((id) => manifest[id].files.includes(BUTTON_FILE))
  assert.ok(
    recorded.length >= 35,
    `expected at least 35 entries to record Button, saw ${recorded.length}`,
  )
  const picked = select(BUTTON_DIFF, manifest, manifest, stories)
  const byFiles = [...picked.rules].filter(([, why]) => why.includes('files')).map(([id]) => id)
  assert.deepEqual(byFiles.sort(), recorded.sort())
})

test('selection, against the committed manifest: a diff on FavouriteToggle selects the FavouritesList stories that render it', () => {
  const manifest = JSON.parse(readFileSync(path.join(rootDir, MANIFEST_PATH), 'utf8'))
  const stories = Object.entries(manifest).map(([id, e]) => ({
    id,
    importPath: e.importPath,
    exportName: e.exportName,
  }))
  const picked = select(
    ['packages/design-system/src/composites/FavouriteToggle/index.tsx'],
    manifest,
    manifest,
    stories,
  )
  for (const id of [
    'composite-favouriteslist--default',
    'composite-favouriteslist--realistic-list',
  ]) {
    assert.ok(picked.rules.get(id)?.includes('files'), `${id} selected by recorded files`)
  }
})

test('selection, against the committed manifest: a change to a test file alone selects nothing through recorded files, where it used to select 200 stories', () => {
  const manifest = JSON.parse(readFileSync(path.join(rootDir, MANIFEST_PATH), 'utf8'))
  const stories = Object.entries(manifest).map(([id, e]) => ({
    id,
    importPath: e.importPath,
    exportName: e.exportName,
  }))
  const picked = select(
    ['packages/design-system/src/primitives/Button/Button.test.tsx'],
    manifest,
    manifest,
    stories,
  )
  const byFiles = [...picked.rules].filter(([, why]) => why.includes('files'))
  assert.deepEqual(byFiles, [])
  // What it does select is (a)'s: the stories of that directory, by the `story-files` rule alone. No
  // test file is imported by a story file, so the import walk adds none from another directory.
  assert.ok(picked.stories.every((s) => picked.rules.get(s.id).join() === 'story-files'))
  assert.ok(picked.stories.length > 0)
  assert.deepEqual(
    [...new Set(picked.stories.map((s) => path.posix.dirname(s.importPath.replace(/^\.\//, ''))))],
    ['src/primitives/Button'],
  )
  assert.ok(picked.stories.length < 40, `selected ${picked.stories.length}`)
  // A docs-only diff selects nothing at all.
  assert.deepEqual(select(['docs/data-sources.md'], manifest, manifest, stories).stories, [])
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

// ---- fail closed: the arguments, a malformed manifest, an index with no plants ---------------------

test('parseArgs: every known flag is accepted alone; an unknown token, a typo and a joined "--write --plants" are refused naming the token', () => {
  for (const flag of ['--keys', '--write', '--changed', '--plants']) {
    assert.deepEqual(parseArgs([flag]).problems, [], flag)
  }
  assert.deepEqual([...parseArgs(['--write', '--changed']).flags].sort(), ['--changed', '--write'])
  assert.deepEqual(parseArgs([]).problems, [])
  for (const token of ['--write --plants', '--wrtie', '--change', 'plants', '-w', '--write=1']) {
    const { problems } = parseArgs([token])
    assert.equal(problems.length, 1, token)
    assert.ok(problems[0].includes(JSON.stringify(token)), `${token}: ${problems[0]}`)
  }
  assert.equal(parseArgs(['--write', '--oops', '--plants']).problems.length, 1)
})

test('parseArgs: --keys stands alone, and two selections are refused', () => {
  assert.match(parseArgs(['--keys', '--write']).problems.join('\n'), /--keys/)
  assert.match(parseArgs(['--keys', '--plants']).problems.join('\n'), /--keys/)
  assert.match(parseArgs(['--changed', '--plants']).problems.join('\n'), /--changed.*--plants/)
})

test('parseManifest: a conflicted or non-object file is a problem naming the file and the rewrite command, never a raw SyntaxError', () => {
  const ok = parseManifest(JSON.stringify(manifestOf(A)), { label: 'the manifest' })
  assert.deepEqual(Object.keys(ok.manifest), [A.id])
  for (const text of [
    '<<<<<<< HEAD\n{}\n=======\n{}\n>>>>>>> main\n',
    '',
    '[]',
    'null',
    '"x"',
    '{"a":',
  ]) {
    const result = parseManifest(text, { label: MANIFEST_PATH })
    assert.equal(result.manifest, undefined, JSON.stringify(text))
    assert.ok(result.problem.includes(MANIFEST_PATH), result.problem)
    assert.ok(result.problem.includes(REWRITE_COMMAND), result.problem)
    assert.doesNotMatch(result.problem, /^SyntaxError/)
  }
})

test('findFixtureProblem: an index with published stories and no plant is refused; one with a plant, or with nothing at all, is not this check’s business', () => {
  assert.match(findFixtureProblem(indexOf(A, B)), /fixture/)
  assert.match(findFixtureProblem(indexOf(A, B, DOCS)), /state-coverage-fixture/)
  assert.equal(findFixtureProblem(indexOf(A, PLANT)), null)
  assert.equal(findFixtureProblem(indexOf()), null)
})

// A stand-in for `pnpm` that does what the real one is asked for here: `exec prettier` is the
// identity, `exec playwright test …` writes one record per story of the work file, the way the spec
// does. It lets the driver's own logic — what it selects, refuses and writes — run without a browser.
function withFakePnpm(body) {
  const dir = mkdtempSync(path.join(tmpdir(), 'state-coverage-runtime-driver-'))
  try {
    const bin = path.join(dir, 'bin')
    mkdirSync(bin)
    const script = `#!${process.execPath}
const fs = require('node:fs')
const path = require('node:path')
const args = process.argv.slice(2)
if (args[1] === 'prettier') { process.stdout.write(fs.readFileSync(0, 'utf8')); process.exit(0) }
const work = JSON.parse(fs.readFileSync(process.env.VISUAL_RUNTIME_FILE, 'utf8'))
fs.writeFileSync(path.join(process.env.FAKE_PNPM_LOG), JSON.stringify(work))
for (const { id, widths } of work.stories) {
  const record = { mounts: [], files: ['packages/design-system/src/primitives/Button/index.tsx'] }
  fs.writeFileSync(
    path.join(process.env.VISUAL_RUNTIME_OUT_DIR, id + '.json'),
    JSON.stringify({ id, widths: Object.fromEntries(widths.map((w) => [String(w), record])) }),
  )
}
`
    writeFileSync(path.join(bin, 'pnpm'), script, { mode: 0o755 })
    const run = (args, { index, manifestText }) => {
      const indexFile = path.join(dir, 'index.json')
      const manifestFile = path.join(dir, 'manifest.json')
      writeFileSync(indexFile, JSON.stringify(index))
      if (manifestText !== undefined) writeFileSync(manifestFile, manifestText)
      const result = spawnSync(
        process.execPath,
        [path.join(rootDir, 'scripts/visual/state-coverage-runtime.mjs'), ...args],
        {
          encoding: 'utf8',
          env: {
            ...process.env,
            PATH: `${bin}${path.delimiter}${process.env.PATH}`,
            STATE_COVERAGE_RUNTIME_INDEX: indexFile,
            STATE_COVERAGE_RUNTIME_MANIFEST: manifestFile,
            STATE_COVERAGE_RUNTIME_OUT_DIR: path.join(dir, 'raw'),
            FAKE_PNPM_LOG: path.join(dir, 'work.log.json'),
          },
        },
      )
      const read = (file) => (existsSync(file) ? readFileSync(file, 'utf8') : null)
      return {
        ...result,
        manifestText: read(manifestFile),
        work: read(path.join(dir, 'work.log.json')),
      }
    }
    return body(run)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
}

const FAKE_FILE = 'packages/design-system/src/primitives/Button/index.tsx'
// What the fake `pnpm` records for every story at every width.
const fakeEntry = (s) =>
  buildEntry(
    s,
    Object.fromEntries([375, 768, 1280].map((w) => [w, { mounts: [], files: [FAKE_FILE] }])),
  )
const REAL_INDEX = indexOf(A, B, PLANT)
const NO_PLANT_INDEX = indexOf(A, B)

test('the driver refuses an unknown flag, naming it, in every mode, and writes nothing', () => {
  withFakePnpm((run) => {
    const manifestText = JSON.stringify(manifestOf(A, B, PLANT))
    for (const args of [
      ['--write --plants'],
      ['--wrtie'],
      ['--write', '--plnts'],
      ['plants'],
      ['--keys', '--write'],
    ]) {
      const result = run(args, { index: REAL_INDEX, manifestText })
      assert.equal(result.status, 1, `${args.join(' ')}: ${result.stdout}`)
      assert.ok(
        args.some((token) => result.stdout.includes(JSON.stringify(token))) ||
          /--keys/.test(result.stdout),
        result.stdout,
      )
      assert.equal(result.manifestText, manifestText, 'the manifest is untouched')
      assert.equal(result.work, null, 'no pass ran')
    }
  })
})

test('the driver refuses an index with published stories and no plant in every non-keys mode, and --write --plants no longer drops the plants', () => {
  withFakePnpm((run) => {
    const manifestText = JSON.stringify(manifestOf(A, B, PLANT))
    for (const args of [['--plants'], ['--write', '--plants'], [], ['--write'], ['--changed']]) {
      const result = run(args, { index: NO_PLANT_INDEX, manifestText })
      assert.equal(result.status, 1, `${args.join(' ') || '(no flag)'}: ${result.stdout}`)
      assert.match(result.stdout, /fixture/)
      assert.equal(result.manifestText, manifestText, 'the plant entries are still there')
      assert.equal(result.work, null)
    }
    // Contrast: the keys check is the browserless one and has its own verdict (the plant entry is extra).
    const keys = run(['--keys'], { index: NO_PLANT_INDEX, manifestText })
    assert.equal(keys.status, 1)
    assert.match(keys.stdout, /extra-entry|no such story/)
  })
})

test('contrast: an index with its plants is unaffected — --keys is green and --write --plants writes the plant entries only', () => {
  withFakePnpm((run) => {
    const manifestText = JSON.stringify(manifestOf(A, B, PLANT))
    assert.equal(run(['--keys'], { index: REAL_INDEX, manifestText }).status, 0)
    const result = run(['--write', '--plants'], { index: REAL_INDEX, manifestText })
    assert.equal(result.status, 0, result.stdout)
    assert.deepEqual(
      JSON.parse(result.work).stories.map((s) => s.id),
      [PLANT.id],
    )
    const written = JSON.parse(result.manifestText)
    assert.deepEqual(Object.keys(written), [A.id, B.id, PLANT.id])
    assert.deepEqual(written[PLANT.id].files, [FAKE_FILE])
    assert.equal(
      written[PLANT.id].widths['375'].files,
      undefined,
      'files is the entry’s, not each width’s',
    )
  })
})

test('a malformed manifest: a clear message naming the file and the command, never a SyntaxError; a full --write rebuilds it', () => {
  withFakePnpm((run) => {
    const conflicted = '<<<<<<< HEAD\n{}\n=======\n{}\n>>>>>>> main\n'
    for (const args of [
      ['--keys'],
      [],
      ['--plants'],
      ['--write', '--plants'],
      ['--write', '--changed'],
    ]) {
      const result = run(args, { index: REAL_INDEX, manifestText: conflicted })
      assert.equal(
        result.status,
        1,
        `${args.join(' ') || '(no flag)'}: ${result.stdout}${result.stderr}`,
      )
      assert.match(result.stdout, /manifest\.json/)
      assert.match(result.stdout, /--write/)
      assert.doesNotMatch(result.stdout + result.stderr, /SyntaxError/)
      assert.equal(result.manifestText, conflicted, 'nothing was overwritten by a partial run')
    }
    const rebuilt = run(['--write'], { index: REAL_INDEX, manifestText: conflicted })
    assert.equal(rebuilt.status, 0, rebuilt.stdout + rebuilt.stderr)
    assert.deepEqual(Object.keys(JSON.parse(rebuilt.manifestText)), [A.id, B.id, PLANT.id])
  })
})

test('the work file lists every fixture id whatever the selection, so the spec’s plant-coverage check always has the full set', () => {
  withFakePnpm((run) => {
    const fake = fakeEntry(PLANT)
    const manifestText = JSON.stringify({ ...manifestOf(A, B), [PLANT.id]: fake })
    const plants = run(['--plants'], { index: REAL_INDEX, manifestText })
    assert.equal(plants.status, 0, plants.stdout)
    assert.deepEqual(JSON.parse(plants.work).fixtureIds, [PLANT.id])
    assert.deepEqual(
      JSON.parse(plants.work).stories.map((s) => s.id),
      [PLANT.id],
    )
  })
})
