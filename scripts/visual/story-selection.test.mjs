// `selectChangedStories` was extracted from `scripts/visual/run.mjs` by T693 so the runtime pass
// selects the way `pnpm test:visual --changed` does. These pin the rule both now share: a change under
// a global-reach prefix selects every story, otherwise a story is selected when its own file or any
// file in its directory changed. Pure — no git, no browser.
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'
import { fileAtBase, selectChangedStories } from './story-selection.mjs'

const stories = [
  { id: 'button--primary', importPath: './src/primitives/Button/Button.stories.tsx' },
  { id: 'menu--open', importPath: './src/primitives/Menu/Menu.stories.tsx' },
  { id: 'plants--bare', importPath: './.storybook/fixtures/Plants.stories.tsx' },
]
const ids = (result) => result.stories.map((s) => s.id)

test('a change under a global-reach prefix selects every story, fixtures included', () => {
  for (const file of [
    'packages/design-system/tokens/color.json',
    'packages/design-system/.storybook/preview.tsx',
    'packages/design-system/src/lib/cx.ts',
    'tests/visual/story-render.ts',
  ]) {
    const result = selectChangedStories(stories, [file])
    assert.equal(result.globallyAffected, true, file)
    assert.equal(result.stories.length, 3, file)
  }
})

test('otherwise a story is selected by its own directory, and nothing else is', () => {
  assert.deepEqual(
    ids(selectChangedStories(stories, ['packages/design-system/src/primitives/Button/index.tsx'])),
    ['button--primary'],
  )
  assert.deepEqual(
    ids(
      selectChangedStories(stories, [
        'packages/design-system/src/primitives/Menu/Menu.stories.tsx',
      ]),
    ),
    ['menu--open'],
  )
  assert.deepEqual(ids(selectChangedStories(stories, ['apps/web/src/main.tsx'])), [])
})

// ---- the caller's own prefix, and the manifest at the diff base ----------------------------------

const here = path.dirname(fileURLToPath(import.meta.url))
const selectionModule = path.join(here, 'story-selection.mjs')

// Runs `body` (a script) in a fresh node with `VISUAL_BASE_REF` set to a ref no checkout resolves.
function runWithUnresolvableBase(body) {
  return spawnSync(
    process.execPath,
    [
      '--input-type=module',
      '-e',
      `import * as sel from ${JSON.stringify(selectionModule)}\n${body}`,
    ],
    {
      encoding: 'utf8',
      env: { ...process.env, VISUAL_BASE_REF: 'no-such-ref-for-this-test' },
    },
  )
}

test('an unresolvable diff base is a refusal that speaks with the caller’s own prefix and names the caller’s own escape', () => {
  const result = runWithUnresolvableBase(
    "sel.changedFiles({ prefix: 'state-coverage-runtime', unscopedCommand: 'the pass without --changed' })",
  )
  assert.equal(result.status, 1)
  assert.match(result.stdout, /^state-coverage-runtime: --changed could not resolve its diff base/)
  assert.doesNotMatch(result.stdout, /test:visual/)
  assert.match(result.stdout, /the pass without --changed/)
})

test('contrast: with no options the refusal is still run.mjs’s own (test:visual prefix, the unscoped pnpm command)', () => {
  const result = runWithUnresolvableBase('sel.changedFiles()')
  assert.equal(result.status, 1)
  assert.match(result.stdout, /^test:visual: --changed could not resolve its diff base/)
  assert.match(result.stdout, /pnpm test:visual/)
})

function git(cwd, ...args) {
  const result = spawnSync('git', args, { cwd, encoding: 'utf8' })
  assert.equal(result.status, 0, `git ${args.join(' ')}: ${result.stderr}`)
  return result.stdout.trim()
}

// A throwaway repository: `main` carries `manifest.json` (or not), a branch changes it.
function withRepo(baseHasFile, body) {
  const dir = mkdtempSync(path.join(tmpdir(), 'story-selection-'))
  try {
    git(dir, 'init', '-q', '-b', 'main')
    git(dir, 'config', 'user.email', 't@example.com')
    git(dir, 'config', 'user.name', 't')
    git(dir, 'config', 'commit.gpgsign', 'false')
    writeFileSync(path.join(dir, 'README.md'), 'x')
    if (baseHasFile) writeFileSync(path.join(dir, 'manifest.json'), '{"a":1}')
    git(dir, 'add', '.')
    git(dir, 'commit', '-q', '-m', 'base')
    git(dir, 'checkout', '-q', '-b', 'feature')
    writeFileSync(path.join(dir, 'manifest.json'), '{"a":2}')
    git(dir, 'add', '.')
    git(dir, 'commit', '-q', '-m', 'feature')
    // `main` moves on after the branch point: the base is the merge base, as `base...HEAD` is.
    git(dir, 'checkout', '-q', 'main')
    writeFileSync(path.join(dir, 'manifest.json'), '{"a":0}')
    git(dir, 'add', '.')
    git(dir, 'commit', '-q', '-m', 'main moves on')
    git(dir, 'checkout', '-q', 'feature')
    return body(dir)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
}

test('fileAtBase reads the file as it was at the merge base, not at the base ref’s tip', () => {
  withRepo(true, (dir) => {
    process.env.VISUAL_BASE_REF = 'main'
    try {
      assert.equal(fileAtBase('manifest.json', { cwd: dir }), '{"a":1}')
    } finally {
      delete process.env.VISUAL_BASE_REF
    }
  })
})

test('fileAtBase: a file that does not exist at the base is null, not a refusal', () => {
  withRepo(false, (dir) => {
    process.env.VISUAL_BASE_REF = 'main'
    try {
      assert.equal(fileAtBase('manifest.json', { cwd: dir }), null)
    } finally {
      delete process.env.VISUAL_BASE_REF
    }
  })
})

test('fileAtBase: an unresolvable base stays a refusal, never "nothing changed"', () => {
  const result = runWithUnresolvableBase(
    "sel.fileAtBase('packages/design-system/specs/state-coverage-runtime.json', { prefix: 'state-coverage-runtime' })",
  )
  assert.equal(result.status, 1)
  assert.match(result.stdout, /^state-coverage-runtime: .*could not resolve/)
})
