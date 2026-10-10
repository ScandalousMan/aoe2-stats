// T693 piece 5: every reader of the built index that means "the stories this package publishes"
// skips a `state-coverage-fixture` story by tag, and only the runtime pass asks for fixtures. Each
// test plants a tagged entry in an index and shows what the reader does with it.
//
// How each reader is proved:
//   - `listStories` (the one function the readers share) and `fixtureStoryFiles`: called directly.
//   - the state-signal sweep's reader (`indexedStories`, `buildStateSignalWork`): real functions,
//     called directly on an index carrying a plant.
//   - `.github/workflows/baselines.yml`'s inline unit list: the script is extracted from the workflow
//     and run against a planted index, since it cannot import a module.
//   - `scripts/visual/run.mjs` (capture units and the accessibility scan they carry) and
//     `scripts/checks/story-baselines.mjs`: scripts with side effects on a fixed index path, so what
//     is asserted is that each takes its stories from `listStories` and carries no filter of its own
//     that could forget the tag. The runtime pass itself is the one caller of `includeFixtures`.
//   - the generated region of row 8 of `packages/design-system/specs/README.md`
//     (`scripts/checks/state-coverage.mjs`) reads no index today: it will read the runtime manifest
//     (T694), whose fixture entries it skips by the same tag — that task's test.
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'
import { buildStateSignalWork, indexedStories } from './state-signal-model.mjs'
import {
  FIXTURE_TAG,
  FULL_PAGE_TAG,
  fixtureStoryFiles,
  isFullPageEntry,
  listStories,
} from './story-index.mjs'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')

const PLANT = {
  type: 'story',
  id: 'state-coverage-fixture-plants--planted',
  importPath: './.storybook/fixtures/Plants.stories.tsx',
  exportName: 'Planted',
  tags: ['test', FIXTURE_TAG],
}
const REAL = {
  type: 'story',
  id: 'primitives-button--primary',
  importPath: './src/primitives/Button/Button.stories.tsx',
  exportName: 'Primary',
  tags: ['dev', 'autodocs'],
}
const DOCS = {
  type: 'docs',
  id: 'primitives-button--docs',
  importPath: './src/primitives/Button/Button.stories.tsx',
  tags: ['autodocs'],
}
const index = { v: 5, entries: { [REAL.id]: REAL, [PLANT.id]: PLANT, [DOCS.id]: DOCS } }

test('listStories skips a fixture by tag and a docs entry by type; includeFixtures is the runtime pass', () => {
  assert.deepEqual(
    listStories(index).map((e) => e.id),
    [REAL.id],
  )
  assert.deepEqual(
    listStories(index, { includeFixtures: true })
      .map((e) => e.id)
      .sort(),
    [PLANT.id, REAL.id].sort(),
  )
})

test('listStories reads the older `stories` key too, and an entry with no `type`', () => {
  const old = { stories: { a: { id: 'a', tags: [FIXTURE_TAG] }, b: { id: 'b' } } }
  assert.deepEqual(
    listStories(old).map((e) => e.id),
    ['b'],
  )
})

test('fixtureStoryFiles names the files that hold fixtures, relative to the package', () => {
  assert.deepEqual([...fixtureStoryFiles(index)], ['.storybook/fixtures/Plants.stories.tsx'])
})

test('the state-signal sweep neither indexes a fixture nor reports its file as unindexed', () => {
  assert.deepEqual(
    indexedStories(index).map((s) => s.id),
    [REAL.id],
  )
  const work = buildStateSignalWork({
    index,
    readSource: () => 'export default {}\nexport const Primary = {}\n',
    // The fixture file is on disk (the walker reaches `.storybook/fixtures`) and in the index with
    // no published story: it must not surface as "a story file the index lists nothing for".
    diskFiles: [
      '.storybook/fixtures/Plants.stories.tsx',
      'src/primitives/Button/Button.stories.tsx',
    ],
  })
  assert.deepEqual(
    work.discoveryGaps.filter((g) => g.kind === 'story-file-not-indexed'),
    [],
  )
  assert.equal(work.indexedStoryCount, 1)
})

test('baselines.yml expands no capture unit for a fixture (its inline script, run against a planted index)', () => {
  const workflow = readFileSync(path.join(rootDir, '.github', 'workflows', 'baselines.yml'), 'utf8')
  const match = workflow.match(
    /cat <<'JS' > "\$RUNNER_TEMP\/visual-stories\.mjs"\n([\s\S]*?)\n\s*JS\n/,
  )
  assert.ok(match, 'the inline unit-list script is no longer found in baselines.yml')
  // The heredoc is indented as YAML; strip that indent so the script is plain JS.
  const lines = match[1].split('\n')
  const indent = Math.min(...lines.filter((l) => l.trim()).map((l) => l.match(/^ */)[0].length))
  const script = lines.map((l) => l.slice(indent)).join('\n')

  const dir = mkdtempSync(path.join(tmpdir(), 'baselines-units-'))
  try {
    const indexDir = path.join(dir, 'packages', 'design-system', 'storybook-static')
    mkdirSync(indexDir, { recursive: true })
    writeFileSync(path.join(indexDir, 'index.json'), JSON.stringify(index))
    writeFileSync(path.join(dir, 'units.mjs'), script)
    const result = spawnSync('node', ['units.mjs'], {
      cwd: dir,
      encoding: 'utf8',
      env: { ...process.env, STORIES_DIR: dir },
    })
    assert.equal(result.status, 0, result.stderr)
    const units = JSON.parse(readFileSync(path.join(dir, 'visual-stories.json'), 'utf8'))
    assert.ok(units.length > 0)
    assert.ok(
      units.every((u) => u.id === REAL.id),
      'a fixture story got capture units',
    )
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('run.mjs and story-baselines.mjs take their stories from listStories, with no filter of their own', () => {
  for (const file of ['scripts/visual/run.mjs', 'scripts/checks/story-baselines.mjs']) {
    const source = readFileSync(path.join(rootDir, file), 'utf8')
    assert.match(
      source,
      /listStories\(index\)/,
      `${file} does not read stories through listStories`,
    )
    assert.doesNotMatch(source, /entry\.type === 'story'/, `${file} filters index entries itself`)
  }
})

test('only the runtime pass asks for fixtures', () => {
  const callers = []
  for (const file of [
    'scripts/visual/run.mjs',
    'scripts/visual/state-signal-model.mjs',
    'scripts/checks/story-baselines.mjs',
    'scripts/visual/state-coverage-runtime.mjs',
    'scripts/visual/state-coverage-runtime-model.mjs',
  ]) {
    if (/includeFixtures:\s*true/.test(readFileSync(path.join(rootDir, file), 'utf8'))) {
      callers.push(file)
    }
  }
  assert.deepEqual(callers.sort(), [
    'scripts/visual/state-coverage-runtime-model.mjs',
    'scripts/visual/state-coverage-runtime.mjs',
  ])
})

// T703: the capture's full-page rule has one definition, which `run.mjs` builds its capture units with and
// the runtime pass records the frame with.
test('isFullPageEntry reads the built index tag and nothing else, and run.mjs builds its units with it', () => {
  assert.equal(FULL_PAGE_TAG, 'visual-full-page')
  assert.equal(isFullPageEntry({ tags: ['test', FULL_PAGE_TAG] }), true)
  assert.equal(isFullPageEntry({ tags: ['test'] }), false)
  assert.equal(isFullPageEntry({}), false)
  const runSource = readFileSync(path.join(rootDir, 'scripts/visual/run.mjs'), 'utf8')
  assert.match(runSource, /fullPage: isFullPageEntry\(entry\)/)
  assert.equal(runSource.includes("'visual-full-page'"), false)
})

// T710 (L5): the tag is written once. Every reader that can import the constant does, so a literal of it
// in a harness file is a second definition that a rename of the tag would leave behind. The files read
// are the capture and sweep specs and helpers (`tests/visual/*.ts`) and the Node scripts of
// `scripts/visual/` other than the definition and the tests; the inline script of
// `.github/workflows/baselines.yml` cannot import and says so beside its literal.
test('no harness file writes the full-page tag as a string literal', () => {
  const files = [
    ...readdirSync(path.join(rootDir, 'tests/visual'))
      .filter((name) => name.endsWith('.ts'))
      .map((name) => `tests/visual/${name}`),
    ...readdirSync(path.join(rootDir, 'scripts/visual'))
      .filter(
        (name) =>
          /\.(mjs|cjs)$/.test(name) && !name.endsWith('.test.mjs') && name !== 'story-index.mjs',
      )
      .map((name) => `scripts/visual/${name}`),
  ]
  assert.ok(files.length > 10, 'the scan found the harness files')
  const literal = new RegExp(`['"]${FULL_PAGE_TAG}['"]`)
  const offenders = files.filter((file) =>
    literal.test(readFileSync(path.join(rootDir, file), 'utf8')),
  )
  assert.deepEqual(offenders, [])
  // The contrast: the definition itself holds the literal, which is what the scan is looking for.
  assert.match(readFileSync(path.join(rootDir, 'scripts/visual/story-index.mjs'), 'utf8'), literal)
})
