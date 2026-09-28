// T675 (slice 1/N) — the package-wide comparator-blind-spot sweep. NOT part of the ordinary
// `pnpm test:visual` selection or the PR `visual` job: `scripts/visual/run.mjs` only ever points
// Playwright at this file under its own `--state-signal-sweep` flag, which is also the only thing
// that ever writes `VISUAL_STATE_SWEEP_FILE` — an unset var here (any other invocation of this
// config) falls back to an empty work-item list, matching `stories.spec.ts`'s own
// `VISUAL_STORIES_FILE` convention. This is a *report*, not a gate, in this slice: it renders, it
// diffs, it writes raw numbers to `test-results/state-signal-sweep/raw/` for `run.mjs` to classify
// once the whole run finishes — see this task's own text in tasks.md for why turning this into a
// gate is a later slice's job, not this one's.
//
// Method (must agree with the task's own classification, and with row 1 of
// packages/design-system/specs/README.md's "Verification-coverage gap register"): for each
// {state story, resting counterpart} pair `scripts/visual/state-signal-model.mjs`'s own pairing
// found (computed by `run.mjs` before this file ever runs — never re-derived here, this file "stays
// dumb" the same way `stories.spec.ts` does about story *selection*), render both at the same
// {theme, width} unit and diff the two live renders against each other with Playwright's own
// comparator — pixelmatch at its default `threshold: 0.2` (`playwright.config.ts` sets only
// `maxDiffPixelRatio: 0.01`, never `threshold`). "Playwright's own comparator" is not a
// reimplementation: `playwright-core` bundles `pixelmatch` internally and exposes the exact
// function `expect(...).toHaveScreenshot` itself calls only through `lib/coreBundle`'s own
// `utils.getComparator('image/png')` (confirmed by reading the installed playwright@1.62.1's own
// `node_modules/playwright/lib/matchers/expect.js`, which imports it from that same path) — this
// file calls that function directly on two in-memory screenshots, never on a checked-in baseline.
//
// **Never compared against a checked-in baseline.** Confirmed empirically this task: a locally
// rendered, already-clipped baseline (`primitives-menu--trigger-focus-visible`) came back 103px
// wide against a checked-in 104px-wide reference captured on CI, on every width and both themes —
// a real, pre-existing local-vs-CI rendering difference (font metrics, subpixel rounding), nothing
// to do with this file. Two renders taken back-to-back *on this same machine, in this same run* are
// still valid to diff against each other for this sweep's own question — "does the state differ
// from the rest" is relative, not "does this match a fixed historical reference" — which is why
// every capture below is a raw `page.screenshot()`/`locator.screenshot()` buffer kept only in
// memory, never `expect(...).toHaveScreenshot()` and never written under
// `packages/design-system/__screenshots__`.
//
// Settle logic, the theme mechanism, force-state driving and clip resolution are all imported from
// `./story-render.ts` — the exact functions `stories.spec.ts` itself calls, not a second copy of
// any of them (T675's own instruction).
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'
import { test, type Page } from '@playwright/test'
import { PNG } from 'pngjs'
import {
  applyForceState,
  gotoAndWaitForStorySettled,
  readCaptureClip,
  readForceState,
  resolveCaptureClip,
  type VisualCaptureClip,
} from './story-render'

const rootDir = path.resolve(__dirname, '..', '..')
const rawResultsDir = path.join(rootDir, 'test-results', 'state-signal-sweep', 'raw')
mkdirSync(rawResultsDir, { recursive: true })

// The same built-Storybook-index read `stories.spec.ts` already does for `titleById` — here for
// one more field, `tags`, so this file learns which pairs are `visual-full-page` (a fixed dialog, an
// open popover) the same way `scripts/visual/run.mjs` does, rather than re-deriving it from source.
const storybookIndexPath = path.join(rootDir, 'packages/design-system/storybook-static/index.json')
const tagsById = new Map<string, string[]>()
if (existsSync(storybookIndexPath)) {
  const index = JSON.parse(readFileSync(storybookIndexPath, 'utf8')) as {
    entries?: Record<string, { id: string; tags?: string[] }>
    stories?: Record<string, { id: string; tags?: string[] }>
  }
  for (const entry of Object.values(index.entries ?? index.stories ?? {})) {
    tagsById.set(entry.id, entry.tags ?? [])
  }
}
function isFullPage(id: string): boolean {
  return (tagsById.get(id) ?? []).includes('visual-full-page')
}

// `playwright-core` bundles `pixelmatch` internally and only ever exposes it through this path
// (`lib/coreBundle`'s own `.utils.getComparator`) — the exact function
// `node_modules/playwright/lib/matchers/expect.js`'s own `ImageMatcher` calls for every
// `toHaveScreenshot`, confirmed by reading that file directly rather than assumed. `createRequire`
// anchored at `@playwright/test`'s own `package.json` is what resolves `playwright-core` at all:
// pnpm's strict `node_modules` does not hoist a transitive dependency to this file's own location
// otherwise — the exact trap `scripts/checks/story-baselines-duplicates.mjs`'s own header names for
// why it uses `pngjs` instead of `pixelmatch`/`sharp` directly. `pngjs` itself IS a direct root
// devDependency (`package.json`), so it resolves normally, used here only to read each capture's own
// width/height for a cheap, definitive dimension check before ever asking the comparator to diff two
// buffers of different sizes.
const playwrightRequire = createRequire(require.resolve('@playwright/test/package.json'))
const { getComparator } = playwrightRequire('playwright-core/lib/coreBundle').utils as {
  getComparator: (
    mimeType: string,
  ) => (a: Buffer, b: Buffer, opts: { threshold: number }) => { errorMessage: string } | null
}
const imageComparator = getComparator('image/png')

type Theme = 'light' | 'dark'
const THEMES: Theme[] = ['light', 'dark']
const WIDTHS = [375, 768, 1280]

interface WorkItem {
  stateId: string
  restId: string
  exportName: string
  file: string
}

// Written by `scripts/visual/run.mjs`'s own `--state-signal-sweep` flow — the pairing itself
// (`scripts/visual/state-signal-model.mjs`'s `pairRestingStory`) runs there, in that file's own ESM
// context, never re-derived here: this file "stays dumb" about *which* pairs exist, the same
// discipline `stories.spec.ts` already keeps about story *selection*. An unset var (any invocation
// of this config that is not `run.mjs --state-signal-sweep`) falls back to an empty list.
const workItemsPath = process.env.VISUAL_STATE_SWEEP_FILE
const workItems: WorkItem[] = workItemsPath
  ? (JSON.parse(readFileSync(workItemsPath, 'utf8')) as WorkItem[])
  : []

interface UnitResult {
  theme: Theme
  width: number
  diffPixels: number | null
  totalPixels: number | null
  ratio: number | null
  dimensionMismatch: boolean
}

// One story's own frame at one {theme, width} unit: navigates, settles
// (`gotoAndWaitForStorySettled` waits out the story's own `play()`, if any — a play()-left
// focus-visible frame needs nothing further), drives the real pseudo-class if the story names one
// (a resting counterpart never does, by the pairing rule's own construction), and returns a raw PNG
// buffer plus whichever clip it used. `clipOverride`:
//   - `undefined` (the state story's own capture): read this story's own
//     `parameters.visualCaptureClip` after it settles, the same way `stories.spec.ts` does.
//   - a `VisualCaptureClip | null` (the resting story's own capture): use exactly that value —
//     this task's own method applies the *state* story's clip to both frames, never a clip of the
//     resting story's own (it does not carry one, by the pairing rule's own construction: a state
//     story is never its own rest).
async function captureFrame(
  page: Page,
  id: string,
  theme: Theme,
  width: number,
  fullPage: boolean,
  clipOverride?: VisualCaptureClip | null,
): Promise<{ buffer: Buffer; clip: VisualCaptureClip | null }> {
  const height = width === 375 ? 900 : 720
  const root = await gotoAndWaitForStorySettled(page, id, theme, width, height)
  const forceState = await readForceState(page, id)
  if (forceState) {
    await applyForceState(page, root, forceState, { width, height, fullPage })
  }
  const clip = clipOverride !== undefined ? clipOverride : await readCaptureClip(page, id)
  if (clip) {
    const rect = await resolveCaptureClip(page, root, id, clip)
    // `fullPage: true` alongside `clip` — the same pairing `stories.spec.ts` always uses
    // (T591's own comment there). Without it, a clip target below the fold of a long `screens/*`
    // form (`ThirdPartyObjectionForm`'s own privacy-notice link, well past the initial 720-900px
    // viewport at every width) resolves to a page-coordinate rect Playwright's own clipped
    // screenshot cannot reach without `fullPage` first laying out and stitching the whole
    // document — confirmed empirically this task ("Clipped area is either empty or outside the
    // resulting image" on every one of that file's four clipped stories, at every unit).
    return { buffer: await page.screenshot({ fullPage: true, clip: rect }), clip }
  }
  if (fullPage) {
    return { buffer: await page.screenshot(), clip }
  }
  return { buffer: await root.screenshot(), clip }
}

for (const item of workItems) {
  test(`${item.stateId} vs ${item.restId} (comparator sweep)`, async ({ page }) => {
    const fullPage = isFullPage(item.stateId)
    const results: UnitResult[] = []

    for (const theme of THEMES) {
      for (const width of WIDTHS) {
        const state = await captureFrame(page, item.stateId, theme, width, fullPage)
        const rest = await captureFrame(page, item.restId, theme, width, fullPage, state.clip)

        const stateImage = PNG.sync.read(state.buffer)
        const restImage = PNG.sync.read(rest.buffer)
        if (stateImage.width !== restImage.width || stateImage.height !== restImage.height) {
          results.push({
            theme,
            width,
            diffPixels: null,
            totalPixels: null,
            ratio: null,
            dimensionMismatch: true,
          })
          continue
        }
        const totalPixels = stateImage.width * stateImage.height
        const diffResult = imageComparator(state.buffer, rest.buffer, { threshold: 0.2 })
        const diffPixels = diffResult
          ? Number(/^(\d+) pixels/.exec(diffResult.errorMessage)?.[1])
          : 0
        results.push({
          theme,
          width,
          diffPixels,
          totalPixels,
          ratio: diffPixels / totalPixels,
          dimensionMismatch: false,
        })
      }
    }

    const safeName = `${item.stateId}__${item.restId}`.replace(/[^a-z0-9-]+/gi, '_')
    writeFileSync(
      path.join(rawResultsDir, `${safeName}.json`),
      JSON.stringify({ ...item, unitResults: results }, null, 2),
    )
  })
}
