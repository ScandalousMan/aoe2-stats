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

// The tag that makes a story's capture the whole page rather than its root element's box
// (`tests/visual/stories.spec.ts`). The capture reads it from the built index, never from a story's
// source. `run.mjs` builds its capture units with this constant, the runtime pass (T703) records it
// beside the clip it observed, and the state-signal sweep (T710) reads the built index's tags through it;
// the inline script of `.github/workflows/baselines.yml` cannot import and writes the literal itself.
// `story-index.test.mjs` fails on a quoted literal of it in `tests/visual/*.ts` or the other Node
// scripts of `scripts/visual/`.
export const FULL_PAGE_TAG = 'visual-full-page'

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

// Whether the capture takes this index entry's whole page (when no `visualCaptureClip` applies: a clip
// wins over the tag).
export function isFullPageEntry(entry) {
  return (entry.tags ?? []).includes(FULL_PAGE_TAG)
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
