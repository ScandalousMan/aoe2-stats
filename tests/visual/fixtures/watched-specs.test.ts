// T719: a spec file under `tests/visual` that loads a story must run under the watch of
// `./story-requests`, so a spec added later cannot be left out the way `focus-ring.spec.ts` and
// `privacy-notice-responsive.spec.ts` were (they loaded stories with neither the Steam stub nor any
// check on the hosts the page requested). "Installing the watch" is importing `test` from
// `./fixtures/story-requests` instead of from `@playwright/test`; this file reads the specs and fails
// naming each one that loads a story and does not.
//
// "Loads a story" is, for a spec: it navigates to `iframe.html` itself, or it calls a function that
// does. The functions that do are *derived* from the helper modules next to the specs (a function
// whose body navigates to `iframe.html`, then any function that calls one, to a fixed point), never
// listed here, so a new helper that navigates cannot hide a spec from this check. This is a textual
// read and says so: it does not parse TypeScript, it strips comments first (the specs' headers
// quote `iframe.html` freely), and the case it errs on is the safe one — a spec that merely names a
// loader it never calls is asked to install the watch, which costs it nothing.
import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

const VISUAL_DIR = path.resolve(__dirname, '..')

function stripComments(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|\s)\/\/.*$/gm, '$1')
}

function filesUnder(dir: string, suffix: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) return filesUnder(full, suffix)
    return entry.name.endsWith(suffix) ? [full] : []
  })
}

// A navigation to the Storybook iframe: `page.goto(\`/iframe.html?id=...\`)` and its quoted forms.
const NAVIGATES_TO_STORY = /\.goto\(\s*[`'"][^)]*iframe\.html/

// Top-level declarations of a helper module, each with the text of its body. A module-level line
// that starts with a declaration keyword in column 0 opens a new chunk (a signature's closing
// parenthesis in column 0 does not).
function functionBodies(source: string): Map<string, string> {
  const bodies = new Map<string, string>()
  const chunks = stripComments(source).split(
    /\n(?=(?:export|async|function|const|let|type|interface|import)\b)/,
  )
  for (const chunk of chunks) {
    const name = /^(?:export\s+)?(?:async\s+)?function\s+(\w+)/.exec(chunk)?.[1]
    if (name) bodies.set(name, chunk)
  }
  return bodies
}

/** Names of the functions, across `helperSources`, that load a story: their own body navigates to
 * `iframe.html`, or calls a function that does. */
function storyLoaders(helperSources: string[]): Set<string> {
  const bodies = new Map<string, string>()
  for (const source of helperSources) {
    for (const [name, body] of functionBodies(source)) bodies.set(name, body)
  }
  const loaders = new Set<string>()
  for (let grew = true; grew;) {
    grew = false
    for (const [name, body] of bodies) {
      if (loaders.has(name)) continue
      const loads =
        NAVIGATES_TO_STORY.test(body) ||
        [...loaders].some((l) => new RegExp(`\\b${l}\\(`).test(body))
      if (loads) {
        loaders.add(name)
        grew = true
      }
    }
  }
  return loaders
}

function loadsStory(specSource: string, loaders: Set<string>): boolean {
  const source = stripComments(specSource)
  return (
    NAVIGATES_TO_STORY.test(source) ||
    [...loaders].some((l) => new RegExp(`\\b${l}\\(`).test(source))
  )
}

/** Whether the spec's `test` is the one of `./fixtures/story-requests`: it imports `test` from
 * there and does not also import one from `@playwright/test`. */
function installsWatch(specSource: string): boolean {
  const source = stripComments(specSource)
  const importedNames = (from: string): string[] =>
    [...source.matchAll(new RegExp(`import\\s*\\{([^}]*)\\}\\s*from\\s*'${from}'`, 'g'))].flatMap(
      (match) => match[1].split(',').map((part) => part.trim().split(/\s+as\s+/)[0]),
    )
  const fromWatch = importedNames('\\./fixtures/story-requests').includes('test')
  const fromPlain = importedNames('@playwright/test').includes('test')
  return fromWatch && !fromPlain
}

/** Spec files, by relative path, that load a story without the watch. */
function specsMissingWatch(specs: Record<string, string>, loaders: Set<string>): string[] {
  return Object.entries(specs)
    .filter(([, source]) => loadsStory(source, loaders) && !installsWatch(source))
    .map(([file]) => file)
    .sort()
}

function readAll(files: string[]): Record<string, string> {
  return Object.fromEntries(
    files.map((file) => [path.relative(VISUAL_DIR, file), readFileSync(file, 'utf8')]),
  )
}

const HELPERS = filesUnder(VISUAL_DIR, '.ts').filter(
  (file) => !/\.(spec|test)\.ts$/.test(file) && !file.endsWith('.d.ts'),
)
const SPECS = filesUnder(VISUAL_DIR, '.spec.ts')

test('every spec that loads a story runs under the request watch', () => {
  const loaders = storyLoaders(HELPERS.map((file) => readFileSync(file, 'utf8')))
  expect(
    specsMissingWatch(readAll(SPECS), loaders),
    'these specs load a story without importing `test` from ./fixtures/story-requests — a page they ' +
      'render could request a third-party host and nothing would fail (T719, constitution III)',
  ).toEqual([])
})

test('the loaders are derived from the helpers: the settle helper and the probe, not the readers', () => {
  const loaders = storyLoaders(HELPERS.map((file) => readFileSync(file, 'utf8')))
  expect(loaders).toContain('gotoAndWaitForStorySettled')
  // `probeStory` loads a story only through the settle helper: found by the second pass.
  expect(loaders).toContain('probeStory')
  // Functions that take a page already on a story, or no page, load nothing.
  expect(loaders).not.toContain('probeSettledStory')
  expect(loaders).not.toContain('resolveCaptureClip')
  expect(loaders).not.toContain('readForceState')
})

const LOADERS = new Set(['gotoAndWaitForStorySettled'])

test.describe('planted specs', () => {
  test('plant: a spec that settles a story with the plain test fails the guard', () => {
    const spec = `import { test } from '@playwright/test'
      import { gotoAndWaitForStorySettled } from './story-render'
      test('x', async ({ page }) => { await gotoAndWaitForStorySettled(page, 'a--b', 'light', 1, 1) })`
    expect(specsMissingWatch({ 'planted.spec.ts': spec }, LOADERS)).toEqual(['planted.spec.ts'])
  })

  test('plant: a spec that navigates to iframe.html itself with the plain test fails the guard', () => {
    const spec = `import { expect, test } from '@playwright/test'
      test('x', async ({ page }) => { await page.goto(\`/iframe.html?id=\${id}&viewMode=story\`) })`
    expect(specsMissingWatch({ 'planted.spec.ts': spec }, LOADERS)).toEqual(['planted.spec.ts'])
  })

  test('plant: also importing the plain test from @playwright/test does not install the watch', () => {
    // The conservative direction: a spec that brings in the plain `test` (renamed or not) may run
    // its page under it, so it is asked to drop the import.
    const mixed = `import { test } from './fixtures/story-requests'
      import { test as plain } from '@playwright/test'
      plain('x', async ({ page }) => { await page.goto('/iframe.html?id=a--b') })`
    expect(specsMissingWatch({ 'planted.spec.ts': mixed }, LOADERS)).toEqual(['planted.spec.ts'])
  })

  test('contrast: the same specs under the watch pass the guard', () => {
    const settled = `import { test } from './fixtures/story-requests'
      import { gotoAndWaitForStorySettled } from './story-render'
      test('x', async ({ page }) => { await gotoAndWaitForStorySettled(page, 'a--b', 'light', 1, 1) })`
    const direct = `import { expect, test } from './fixtures/story-requests'
      test('x', async ({ page }) => { await page.goto('/iframe.html?id=a--b') })`
    expect(specsMissingWatch({ 'a.spec.ts': settled, 'b.spec.ts': direct }, LOADERS)).toEqual([])
  })

  test('contrast: a spec that loads no story needs no watch, and a comment naming iframe.html is not a load', () => {
    const unit = `// loads /iframe.html in a comment: page.goto('/iframe.html?id=a--b')
      import { test } from '@playwright/test'
      import { resolveCaptureClip } from './story-render'
      test('x', async ({ page }) => { await page.setContent('<p>x</p>'); await resolveCaptureClip(page) })`
    expect(specsMissingWatch({ 'unit.spec.ts': unit }, LOADERS)).toEqual([])
  })
})
