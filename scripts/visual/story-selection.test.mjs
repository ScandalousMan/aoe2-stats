// `selectChangedStories` was extracted from `scripts/visual/run.mjs` by T693 so the runtime pass
// selects the way `pnpm test:visual --changed` does. These pin the rule both now share: a change under
// a global-reach prefix selects every story, otherwise a story is selected when its own file or any
// file in its directory changed. Pure — no git, no browser.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { selectChangedStories } from './story-selection.mjs'

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
