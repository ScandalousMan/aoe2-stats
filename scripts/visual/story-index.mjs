// The one place that reads a built Storybook `index.json` entry's kind and fixture tag (T693).
//
// `packages/design-system/.storybook/fixtures/` holds the plants `tests/visual/state-coverage-
// runtime.spec.ts` asserts on (T693 piece 5): stories built into Storybook so a browser can be
// asked what it renders for a shape the static reading of `scripts/checks/state-coverage.mjs`
// guessed wrong. They are tagged `state-coverage-fixture` and are not published stories — no
// sidebar entry, no docs page, no baseline, no accessibility scan, no capture unit — so every
// reader of the built index that means "the stories this package publishes" goes through
// `listStories` below, which skips that tag by name. Only the runtime pass itself asks for them
// (`listStories(index, { includeFixtures: true })`), because a plant's recorded entry is the point.
//
// `scripts/visual/story-index.test.mjs` plants a tagged entry and proves each reader on its own fixed
// list skips it. It does not discover readers: a reader added later that re-derives "is a story" on its
// own and forgets the tag is caught only once someone adds it to that list.

export const FIXTURE_TAG = 'state-coverage-fixture'

// Every entry of a parsed `index.json`, whatever its type. `entries` is Storybook 10's key,
// `stories` the older one some tooling still emits.
export function indexEntries(index) {
  return Object.values(index?.entries ?? index?.stories ?? {})
}

// A `story` entry, as opposed to a `docs` one. `type` is absent on the oldest index shape.
export function isStoryEntry(entry) {
  return entry.type === undefined || entry.type === 'story'
}

export function isFixtureEntry(entry) {
  return (entry.tags ?? []).includes(FIXTURE_TAG)
}

// The stories of an index, fixtures skipped unless the caller is the runtime pass.
export function listStories(index, { includeFixtures = false } = {}) {
  return indexEntries(index).filter(
    (entry) => isStoryEntry(entry) && (includeFixtures || !isFixtureEntry(entry)),
  )
}

// A story entry's `importPath` without its leading `./`, the shape a path relative to the design
// system package has.
export function importFile(entry) {
  return (entry.importPath ?? '').replace(/^\.\//, '')
}

// The story files that hold fixture stories, relative to the design-system package. A reader that
// reconciles the index against story files on disk (the state-signal sweep) uses this to leave a
// fixture file out of "on disk but not in the index".
export function fixtureStoryFiles(index) {
  return new Set(
    indexEntries(index)
      .filter((entry) => isStoryEntry(entry) && isFixtureEntry(entry))
      .map(importFile),
  )
}
