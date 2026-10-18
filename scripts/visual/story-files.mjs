// The story files `packages/design-system/.storybook/main.ts`'s `stories` globs index, listed from
// disk. Shared by two consumers that must agree on the set: the state-signal sweep
// (`state-signal-model.mjs`, T679) and the deferral-vocabulary sweep in
// `scripts/checks/state-coverage.mjs` (T683).
//
// A module of its own, not an export of `state-signal-model.mjs`, because that file loads
// `storybook/internal/csf` with a top-level `await` and imports `state-coverage.mjs` back: pulling
// it into `state-coverage.mjs` would make a plain check load Storybook's internals and turn the
// import into a cycle through a top-level await. This file imports nothing from either.
import { readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const packageDir = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '..',
  '..',
  'packages',
  'design-system',
)

// The directories `.storybook/main.ts`'s `stories` globs start from, relative to the package
// (`../src/**/*.stories.@(ts|tsx)`, `./foundations/**/*.stories.@(ts|tsx)` and, T693,
// `./fixtures/**/*.stories.@(ts|tsx)`), and the file
// extensions those globs match. A second copy of both, so `state-signal-model.test.mjs` reads the
// real `stories` array and fails when it and these lists stop agreeing.
export const STORY_WALK_ROOTS = ['src', '.storybook/foundations', '.storybook/fixtures']
export const STORY_FILE_EXTENSIONS = ['ts', 'tsx']

// The `*.stories.<extension>` files under `STORY_WALK_ROOTS`, as paths relative to the package. It
// feeds `state-signal-model.mjs`'s `findUnindexedStoryFiles` (through `run.mjs`) and
// `state-coverage.mjs`'s deferral sweep. Below a root it skips `node_modules` and
// dot-entries, as a `**` glob with picomatch's default `dot: false` does; a root that is itself a
// dot-directory (`.storybook/foundations`) is walked, being named explicitly. A root that does not
// exist is an empty listing; any other read error propagates. `readdir` is injectable for tests.
export function listStoryFilesOnDisk(
  baseDir = packageDir,
  { extensions = STORY_FILE_EXTENSIONS, readdir = readdirSync } = {},
) {
  const suffixes = extensions.map((extension) => `.stories.${extension}`)
  const files = []
  const walk = (relDir, isRoot) => {
    let entries
    try {
      entries = readdir(path.join(baseDir, relDir), { withFileTypes: true })
    } catch (err) {
      if (isRoot && err.code === 'ENOENT') return
      throw err
    }
    for (const entry of entries) {
      if (entry.name === 'node_modules' || entry.name.startsWith('.')) continue
      const rel = path.posix.join(relDir, entry.name)
      if (entry.isDirectory()) walk(rel, false)
      else if (suffixes.some((suffix) => entry.name.endsWith(suffix))) files.push(rel)
    }
  }
  for (const root of STORY_WALK_ROOTS) walk(root, true)
  return files.sort()
}
