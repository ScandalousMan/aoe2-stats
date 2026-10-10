// `selectChangedStories` was extracted from `scripts/visual/run.mjs` by T693 so the runtime pass
// selects the way `pnpm test:visual --changed` does. These pin the rule both now share: a change under
// a global-reach prefix selects every story, otherwise a story is selected when its own file or any
// file in its directory changed. Pure — no git, no browser.
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
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

test('otherwise a story is selected by its own directory, by a module its story file imports, or by an opaque specifier it holds', () => {
  // `Plants.stories.tsx` (a real file) imports `src/primitives/Callout`, so it follows Callout's change
  // although it lives in another directory (T707); the Button story file reaches Callout as well, and
  // the Menu story does not.
  assert.deepEqual(
    ids(selectChangedStories(stories, ['packages/design-system/src/primitives/Callout/index.tsx'])),
    ['button--primary', 'plants--bare'],
  )
  // T710: `Button` is imported by the preview, whose imports run for every story, so its change
  // selects every story, the Menu story included.
  assert.deepEqual(
    ids(selectChangedStories(stories, ['packages/design-system/src/primitives/Button/index.tsx'])),
    ['button--primary', 'menu--open', 'plants--bare'],
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

// ---- T707: a module the story file imports, transitively --------------------------------------------

const PKG = 'packages/design-system/'

// A scratch design-system directory holding `files` (relative path -> text) and one index entry per
// `.stories.` file, shaped like the built index's (`./src/.../X.stories.tsx`, relative to the package).
function withTree(files, body) {
  const root = mkdtempSync(path.join(tmpdir(), 'story-selection-tree-'))
  const dsDir = path.join(root, 'packages', 'design-system')
  try {
    for (const [file, text] of Object.entries(files)) {
      // A key starting with `/` is a file outside the package, under the scratch root.
      const target = file.startsWith('/') ? path.join(root, file) : path.join(dsDir, file)
      mkdirSync(path.dirname(target), { recursive: true })
      writeFileSync(target, text)
    }
    const tree = Object.keys(files)
      .filter((file) => /\.stories\.[jt]sx?$/.test(file))
      .map((file) => ({ id: file.replace(/^src\//, ''), importPath: `./${file}` }))
    const select = (...diff) => selectChangedStories(tree, diff, dsDir).stories.map((s) => s.id)
    return body(select)
  } finally {
    rmSync(root, { recursive: true, force: true })
  }
}

const CARD = 'composites/Card/Card.stories.tsx'
const PANEL = 'composites/Panel/Panel.stories.tsx'
const MENU = 'primitives/Menu/Menu.stories.tsx'

test('T707 plant 1: a story file importing a module in another component’s directory is selected when the diff touches that module', () => {
  withTree(
    {
      'src/composites/Card/Card.stories.tsx':
        "import { CLIP } from '../Panel/story-parameters'\nexport default {}\n",
      'src/composites/Panel/story-parameters.ts': 'export const CLIP = {}\n',
      'src/composites/Panel/Panel.stories.tsx': 'export default {}\n',
      'src/primitives/Menu/Menu.stories.tsx': 'export default {}\n',
    },
    (select) => {
      // Card is selected by the import; Panel by its own directory; Menu by neither.
      assert.deepEqual(select(`${PKG}src/composites/Panel/story-parameters.ts`), [CARD, PANEL])
    },
  )
})

test('T707 plant 2: a module the story reaches only through a second module is selected, cycles included', () => {
  withTree(
    {
      'src/composites/Card/Card.stories.tsx': "import '../Panel/first'\nexport default {}\n",
      'src/composites/Panel/first.ts': "export * from '../../shared/second'\n",
      // `second` imports `first` back: the walk must end.
      'src/shared/second.ts': "import { x } from '../composites/Panel/first'\nexport const y = 1\n",
      'src/primitives/Menu/Menu.stories.tsx': 'export default {}\n',
    },
    (select) => {
      assert.deepEqual(select(`${PKG}src/shared/second.ts`), [CARD])
    },
  )
})

test('T707 plant 3: a story file with a non-literal import() is selected on any diff inside the package, and on none outside it', () => {
  withTree(
    {
      'src/composites/Card/Card.stories.tsx':
        'const name = "x"\nexport const load = () => import(name)\nexport default {}\n',
      'src/primitives/Menu/Menu.stories.tsx': 'export default {}\n',
    },
    (select) => {
      assert.deepEqual(select(`${PKG}src/unrelated/elsewhere.ts`), [CARD])
      assert.deepEqual(select(`${PKG}specs/README.md`), [CARD])
      assert.deepEqual(select('apps/web/src/main.tsx'), [])
    },
  )
})

test('T707 plant 3b: the non-literal specifier may sit in a file the story reaches, and a templated require counts too', () => {
  withTree(
    {
      'src/composites/Card/Card.stories.tsx': "import '../../shared/loader'\nexport default {}\n",
      'src/shared/loader.ts': 'export const f = (n: string) => require(`./${n}`)\n',
      'src/primitives/Menu/Menu.stories.tsx': 'export default {}\n',
    },
    (select) => {
      assert.deepEqual(select(`${PKG}src/unrelated/elsewhere.ts`), [CARD])
    },
  )
})

test('T707 contrast: a diff on a module no story reaches selects nothing beyond the directory rule', () => {
  withTree(
    {
      'src/composites/Card/Card.stories.tsx':
        "import { a } from '../../shared/a'\nexport default {}\n",
      'src/shared/a.ts': 'export const a = 1\n',
      'src/shared/orphan.ts': 'export const o = 1\n',
      'src/primitives/Menu/Menu.stories.tsx': 'export default {}\n',
    },
    (select) => {
      assert.deepEqual(select(`${PKG}src/shared/orphan.ts`), [])
      assert.deepEqual(select(`${PKG}src/primitives/Menu/other.ts`), [MENU])
    },
  )
})

// T710: the preview's imports run for every story. The scratch preview imports a primitive, which
// imports a helper; no story file imports either.
const PREVIEW_TREE = {
  '.storybook/preview.tsx':
    "import { Button } from '../src/primitives/Button'\nexport default {}\n",
  'src/primitives/Button/index.tsx':
    "import { top } from '../../lib/top-level'\nexport const Button = top\n",
  'src/lib/top-level.ts': 'export const top = 1\n',
  'src/shared/orphan.ts': 'export const o = 1\n',
  'src/composites/Card/Card.stories.tsx': 'export default {}\n',
  'src/composites/Panel/Panel.stories.tsx': 'export default {}\n',
}

test('T710 plant: a diff on a module only the preview’s primitives reach selects every story', () => {
  withTree(PREVIEW_TREE, (select) => {
    // `lib/top-level.ts` is reached by `Button`, which the preview imports, and by no story file; the
    // directory rule alone would select nothing.
    assert.deepEqual(select(`${PKG}src/lib/top-level.ts`), [CARD, PANEL])
    // The primitive's own file, a story-less directory, is the same.
    assert.deepEqual(select(`${PKG}src/primitives/Button/index.tsx`), [CARD, PANEL])
  })
})

test('T710 contrast: a diff on a module neither a story nor the preview reaches selects nothing extra', () => {
  withTree(PREVIEW_TREE, (select) => {
    assert.deepEqual(select(`${PKG}src/shared/orphan.ts`), [])
    assert.deepEqual(select(`${PKG}src/composites/Card/other.ts`), [CARD])
    // A diff outside the package touches nothing the preview reaches.
    assert.deepEqual(select('docs/readme.md'), [])
  })
})

test('T710: a specifier the preview’s reach holds and cannot be read selects every story on any diff inside the package, and on none outside it', () => {
  withTree(
    {
      ...PREVIEW_TREE,
      'src/lib/top-level.ts': 'export const top = (name: string) => import(name)\n',
    },
    (select) => {
      assert.deepEqual(select(`${PKG}src/shared/orphan.ts`), [CARD, PANEL])
      assert.deepEqual(select('docs/readme.md'), [])
    },
  )
})

test('T707 contrast: a story is not selected because a story in another directory imports the changed file', () => {
  withTree(
    {
      'src/composites/Card/Card.stories.tsx':
        "import { a } from '../../shared/a'\nexport default {}\n",
      'src/composites/Panel/Panel.stories.tsx': 'export default {}\n',
      'src/shared/a.ts': 'export const a = 1\n',
    },
    (select) => {
      assert.deepEqual(select(`${PKG}src/shared/a.ts`), [CARD])
    },
  )
})

test('T707: every form of module specifier is followed, a bare or unresolvable one is ignored, and the walk stays in the package', () => {
  withTree(
    {
      'src/composites/Card/Card.stories.tsx': [
        "import type { T } from '../../types/type-only'",
        "export { r } from '../../reexport/value'",
        "const lazy = () => import('../../lazy/chunk.js')",
        "const c = require('../../common/cjs')",
        "const d = require('../../common/plain')",
        "import idx from '../../folder'",
        "import tokens from '../../data/tokens.json'",
        "import React from 'react'",
        "import missing from '../../nowhere/missing'",
        "import outside from '../../../../../outside/loader'",
        'export default {}',
      ].join('\n'),
      'src/types/type-only.ts': 'export type T = 1\n',
      'src/reexport/value.tsx': 'export const r = 1\n',
      'src/lazy/chunk.ts': 'export const k = 1\n',
      'src/common/cjs.cjs': 'module.exports = {}\n',
      'src/common/plain.ts': 'export const p = 1\n',
      'src/folder/index.jsx': 'export default 1\n',
      'src/data/tokens.json': '{}\n',
      // A file outside the package is never walked, so its opaque import() selects nothing.
      '/outside/loader.ts': 'export const f = (n: string) => import(n)\n',
      'src/primitives/Menu/Menu.stories.tsx': 'export default {}\n',
    },
    (select) => {
      for (const file of [
        'src/types/type-only.ts',
        'src/reexport/value.tsx',
        'src/lazy/chunk.ts',
        'src/common/cjs.cjs',
        'src/common/plain.ts',
        'src/folder/index.jsx',
        'src/data/tokens.json',
      ]) {
        assert.deepEqual(select(`${PKG}${file}`), [CARD], file)
      }
      assert.deepEqual(select('apps/web/src/main.tsx'), [])
      assert.deepEqual(select(`${PKG}src/nowhere/missing.ts`), [])
    },
  )
})

// ---- T709: every candidate a specifier can name is followed, not the first that exists ----------------

test('T709 plant 1: with helper.js beside helper.ts, a diff on either selects the importing story', () => {
  withTree(
    {
      'src/composites/Card/Card.stories.tsx':
        "import { h } from '../Panel/helper'\nexport default {}\n",
      'src/composites/Panel/helper.ts': 'export const h = 1\n',
      'src/composites/Panel/helper.js': 'export const h = 1\n',
      'src/primitives/Menu/Menu.stories.tsx': 'export default {}\n',
    },
    (select) => {
      assert.deepEqual(select(`${PKG}src/composites/Panel/helper.js`), [CARD])
      assert.deepEqual(select(`${PKG}src/composites/Panel/helper.ts`), [CARD])
    },
  )
})

test('T709 plant 2: a specifier ending in a slash names the directory index, beside a file of the same name', () => {
  withTree(
    {
      'src/composites/Card/Card.stories.tsx': "import { P } from '../Panel/'\nexport default {}\n",
      'src/composites/Panel.tsx': 'export const P = 1\n',
      'src/composites/Panel/index.tsx': 'export const P = 1\n',
      'src/primitives/Menu/Menu.stories.tsx': 'export default {}\n',
    },
    (select) => {
      assert.deepEqual(select(`${PKG}src/composites/Panel/index.tsx`), [CARD])
    },
  )
  // Contrast: without the slash both are candidates, so the file beside the directory is followed too.
  withTree(
    {
      'src/composites/Card/Card.stories.tsx': "import { P } from '../Panel'\nexport default {}\n",
      'src/composites/Panel.tsx': 'export const P = 1\n',
      'src/composites/Panel/index.tsx': 'export const P = 1\n',
    },
    (select) => {
      assert.deepEqual(select(`${PKG}src/composites/Panel.tsx`), [CARD])
      assert.deepEqual(select(`${PKG}src/composites/Panel/index.tsx`), [CARD])
    },
  )
  // And the trailing slash names the index only: the file beside the directory is not a candidate.
  withTree(
    {
      'src/composites/Card/Card.stories.tsx': "import { P } from '../Panel/'\nexport default {}\n",
      'src/composites/Panel.tsx': 'export const P = 1\n',
      'src/composites/Panel/index.tsx': 'export const P = 1\n',
    },
    (select) => {
      assert.deepEqual(select(`${PKG}src/composites/Panel.tsx`), [])
    },
  )
})

test('T709 plant: the relative specifiers `..` and `.` name the directory index, like a trailing slash', () => {
  withTree(
    {
      'src/composites/Card/Card.stories.tsx':
        "import { x } from '../Panel/helpers/x'\nexport default {}\n",
      'src/composites/Panel/helpers/x.ts': "import { P } from '..'\nexport const x = P\n",
      'src/composites/Panel/index.tsx': 'export const P = 1\n',
    },
    (select) => {
      assert.deepEqual(select(`${PKG}src/composites/Panel/index.tsx`), [CARD])
    },
  )
  withTree(
    {
      'src/composites/Card/Card.stories.tsx':
        "import { x } from '../Panel/helpers/x'\nexport default {}\n",
      'src/composites/Panel/helpers/x.ts': "import { H } from '.'\nexport const x = H\n",
      'src/composites/Panel/helpers/index.ts': 'export const H = 1\n',
    },
    (select) => {
      assert.deepEqual(select(`${PKG}src/composites/Panel/helpers/index.ts`), [CARD])
    },
  )
  // Directory-only: `..` does not name a file beside the directory, so `Panel.tsx` is not followed.
  withTree(
    {
      'src/composites/Card/Card.stories.tsx':
        "import { x } from '../Panel/helpers/x'\nexport default {}\n",
      'src/composites/Panel/helpers/x.ts': "import { P } from '..'\nexport const x = P\n",
      'src/composites/Panel/index.tsx': 'export const P = 1\n',
      'src/composites/Panel.tsx': 'export const P = 2\n',
    },
    (select) => {
      assert.deepEqual(select(`${PKG}src/composites/Panel.tsx`), [])
    },
  )
})

test('T709 plant 3: an extensionless specifier resolves to a .mjs, .mts, .cjs and .cts file', () => {
  for (const ext of ['.mjs', '.mts', '.cjs', '.cts']) {
    withTree(
      {
        'src/composites/Card/Card.stories.tsx':
          "import { h } from '../../shared/helper'\nexport default {}\n",
        [`src/shared/helper${ext}`]: 'export const h = 1\n',
        'src/primitives/Menu/Menu.stories.tsx': 'export default {}\n',
      },
      (select) => {
        assert.deepEqual(select(`${PKG}src/shared/helper${ext}`), [CARD], ext)
      },
    )
  }
})

test('T709 plant 4: an extensionless specifier resolves to a .json file, which is a leaf', () => {
  withTree(
    {
      'src/composites/Card/Card.stories.tsx':
        "import data from '../../shared/data'\nexport default {}\n",
      'src/shared/data.json': '{"import": "../nowhere"}\n',
      'src/primitives/Menu/Menu.stories.tsx': 'export default {}\n',
    },
    (select) => {
      assert.deepEqual(select(`${PKG}src/shared/data.json`), [CARD])
      assert.deepEqual(select(`${PKG}src/shared/other.json`), [])
    },
  )
})

test('T709: an emitted extension (.mjs, .cjs) names the .mts and .cts source beside it', () => {
  withTree(
    {
      'src/composites/Card/Card.stories.tsx':
        "import { a } from '../../shared/a.mjs'\nimport { b } from '../../shared/b.cjs'\nexport default {}\n",
      'src/shared/a.mts': 'export const a = 1\n',
      'src/shared/b.cts': 'export const b = 1\n',
    },
    (select) => {
      assert.deepEqual(select(`${PKG}src/shared/a.mts`), [CARD])
      assert.deepEqual(select(`${PKG}src/shared/b.cts`), [CARD])
    },
  )
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
