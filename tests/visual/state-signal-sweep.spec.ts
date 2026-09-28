// T675 (slice 2/N) — the package-wide comparator-blind-spot sweep. NOT part of the ordinary
// `pnpm test:visual` selection or the PR `visual` job: `scripts/visual/run.mjs` only ever points
// Playwright at this file under its own `--state-signal-sweep` flag, which is also the only thing
// that ever writes `VISUAL_STATE_SWEEP_FILE` — an unset var here (any other invocation of this
// config) falls back to an empty work-item list, matching `stories.spec.ts`'s own
// `VISUAL_STORIES_FILE` convention. This is a *report*, not a gate, in this slice: it renders, it
// diffs, it writes raw numbers to `test-results/state-signal-sweep/raw/` for `run.mjs` to classify
// once the whole run finishes — see this task's own text in tasks.md for why turning this into a
// gate is a later slice's job, not this one's.
//
// **Self-pairing (slice 2): a state story's resting counterpart is itself, not a sibling.** Slice 1
// paired a state story against a *different* story sharing the same resolved args/`play`/`render`,
// which left 55 of 113 state stories unmeasurable (no matching sibling, or more than one tied).
// Rendering the same story twice — once with its own forced state applied, once without — has the
// same args, `render`, viewport and clip *by construction*, for every state story in the tree, which
// is exactly the "resting frame with the same args and size" this sweep exists to compare against.
// Two shapes, decided by `scripts/visual/state-signal-model.mjs`'s own `planSelfRest` (never
// re-derived here — this file "stays dumb" about *which* pairs exist and *how*, the same discipline
// it already kept in slice 1):
//   - `'forced'` (a real `visualForceState`): navigate once, reset the pseudo-class explicitly
//     (move the mouse away for `hover`/`active`, blur `document.activeElement` for
//     `focus-visible` — see the loop body's own comment for why this reset is unconditional
//     rather than only-when-needed: several real stories carry a `play()` that already drives the
//     same role for real before `visualForceState` ever runs, e.g. `Tooltip`'s `HoverRevealed`),
//     capture (the rest), drive the pseudo-class for real (`story-render.ts`'s own
//     `applyForceState`), capture again (the state) — on the same page load, which is both cheaper
//     than two navigations and removes any render-to-render variance from the diff (the
//     coordinator's own instruction for this slice).
//   - `'play-focus-blur'` (a focus-visible frame left by a `play()` with no `visualForceState` of
//     its own, e.g. `Dialog`'s `KeyboardFocusOrderAndTrap`): the story's own `play()` already ran by
//     the time it settles, so "before" does not exist the way it does for `'forced'` — capture the
//     settled render first (the state, whatever `document.activeElement` genuinely is), then blur
//     it (`document.activeElement.blur()`) and capture again (the rest). Confirmed safe for every
//     real case in this tree by reading `Dialog`'s own focus trap (`keydown`-driven, never `blur`)
//     and `Menu`'s own roving-focus effect (re-runs on `open`/`activeIndex` state changes, never on
//     a bare DOM `blur`) — neither refocuses or closes anything in response to a programmatic blur,
//     so the rest differs from the state only by the missing focus ring, the property this pairing
//     needs to hold.
//
// Method (must agree with the task's own classification, and with row 1 of
// packages/design-system/specs/README.md's "Verification-coverage gap register"): diff the two live
// renders against each other with Playwright's own comparator — pixelmatch at its default
// `threshold: 0.2` (`playwright.config.ts` sets only `maxDiffPixelRatio: 0.01`, never `threshold`).
// "Playwright's own comparator" is not a reimplementation: `playwright-core` bundles `pixelmatch`
// internally and exposes the exact function `expect(...).toHaveScreenshot` itself calls only
// through `lib/coreBundle`'s own `utils.getComparator('image/png')` (confirmed by reading the
// installed playwright@1.62.1's own `node_modules/playwright/lib/matchers/expect.js`, which imports
// it from that same path) — this file calls that function directly on two in-memory screenshots,
// never on a checked-in baseline.
//
// **Never compared against a checked-in baseline.** Confirmed empirically in slice 1: a locally
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
import { test, type Locator, type Page } from '@playwright/test'
import { PNG } from 'pngjs'
import {
  applyForceState,
  gotoAndWaitForStorySettled,
  readCaptureClip,
  readForceState,
  resolveCaptureClip,
} from './story-render'

const rootDir = path.resolve(__dirname, '..', '..')
const rawResultsDir = path.join(rootDir, 'test-results', 'state-signal-sweep', 'raw')
mkdirSync(rawResultsDir, { recursive: true })

// The same built-Storybook-index read `stories.spec.ts` already does for `titleById` — here for
// one more field, `tags`, so this file learns which stories are `visual-full-page` (a fixed dialog,
// an open popover) the same way `scripts/visual/run.mjs` does, rather than re-deriving it from
// source.
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

// `mode` mirrors `state-signal-model.mjs`'s own `planSelfRest` result — computed there, in
// `run.mjs`'s ESM context, never re-derived here.
type SelfRestMode = 'forced' | 'play-focus-blur'

interface WorkItem {
  stateId: string
  exportName: string
  mode: SelfRestMode
  file: string
}

// Written by `scripts/visual/run.mjs`'s own `--state-signal-sweep` flow. An unset var (any
// invocation of this config that is not `run.mjs --state-signal-sweep`) falls back to an empty list.
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

// The story's own settled frame, clipped to `clip` (the story's own `visualCaptureClip`, resolved
// fresh against the *current* DOM each time this is called — the clip rect is in page coordinates,
// so it does not itself move between the two captures below, but resolving it fresh rather than
// caching it is what `stories.spec.ts` already does and costs nothing extra), full-page when the
// id's own Storybook tag says so, or the plain `#storybook-root` element otherwise.
async function captureNow(
  page: Page,
  root: Locator,
  id: string,
  clip: Awaited<ReturnType<typeof readCaptureClip>>,
  fullPage: boolean,
): Promise<Buffer> {
  if (clip) {
    const rect = await resolveCaptureClip(page, root, id, clip)
    // `fullPage: true` alongside `clip` — the same pairing `stories.spec.ts` always uses (T591's own
    // comment there). Without it, a clip target below the fold of a long `screens/*` form resolves
    // to a page-coordinate rect Playwright's own clipped screenshot cannot reach without `fullPage`
    // first laying out and stitching the whole document (confirmed empirically in slice 1:
    // "Clipped area is either empty or outside the resulting image" on `ThirdPartyObjectionForm`'s
    // own clipped stories without this).
    return page.screenshot({ fullPage: true, clip: rect })
  }
  if (fullPage) {
    return page.screenshot()
  }
  return root.screenshot()
}

for (const item of workItems) {
  test(`${item.stateId} (comparator sweep, self-rest, ${item.mode})`, async ({ page }) => {
    const fullPage = isFullPage(item.stateId)
    const results: UnitResult[] = []

    for (const theme of THEMES) {
      for (const width of WIDTHS) {
        const height = width === 375 ? 900 : 720
        const root = await gotoAndWaitForStorySettled(page, item.stateId, theme, width, height)
        const clip = await readCaptureClip(page, item.stateId)

        let stateBuffer: Buffer
        let restBuffer: Buffer
        if (item.mode === 'forced') {
          const forceState = await readForceState(page, item.stateId)
          if (!forceState) {
            throw new Error(
              `state-signal-sweep: work item "${item.stateId}" was planned as "forced" but this ` +
                "story's own settled render carries no visualForceState parameter — the model and " +
                'the live story have drifted apart.',
            )
          }
          // "The story has settled but the harness has not yet driven the pseudo-class" is only a
          // faithful rest when nothing *else* already produced it — several real stories carry a
          // `play()` that drives the same role for real before `visualForceState` ever runs
          // (`Tooltip`'s own `HoverRevealed`, `play: hoverOpen` then `visualForceState:
          // { state: 'hover', ... }` on the same trigger, by that file's own documented design;
          // `Menu`'s `KeyboardNavigation`/`EscapeReturnsFocusToTrigger`, whose own real
          // `userEvent.keyboard()` sequence leaves a real DOM `.focus()` — genuinely
          // `:focus-visible` — on the exact element `visualForceState` re-focuses). Left alone, the
          // "rest" capture below would already show the state, and the diff would read zero
          // regardless of whether the two are actually distinguishable — a false "no clip can
          // help" this sweep must not report. Resetting explicitly, unconditionally, before every
          // rest capture removes the question of *whether* a play() pre-empted anything rather
          // than trying to detect it: `:hover`/`:active` are anchored to the real pointer's own
          // position (moving it away clears both, wherever it was), and a genuinely absent
          // `document.activeElement` blur is a harmless no-op for the (large majority) of stories
          // where nothing was ever really focused first.
          if (forceState.state === 'hover' || forceState.state === 'active') {
            await page.mouse.move(0, 0)
          } else {
            await page.evaluate(() => {
              const active = document.activeElement
              if (active instanceof HTMLElement) active.blur()
            })
          }
          restBuffer = await captureNow(page, root, item.stateId, clip, fullPage)
          await applyForceState(page, root, forceState, { width, height, fullPage })
          stateBuffer = await captureNow(page, root, item.stateId, clip, fullPage)
        } else {
          // The state comes first here: the story's own play() has already run by the time it
          // settles, so the settled render already *is* the state — there is no "before" to
          // capture. The rest is the same render with whatever play() left focused now blurred.
          stateBuffer = await captureNow(page, root, item.stateId, clip, fullPage)
          await page.evaluate(() => {
            const active = document.activeElement
            if (active instanceof HTMLElement) active.blur()
          })
          restBuffer = await captureNow(page, root, item.stateId, clip, fullPage)
        }

        const stateImage = PNG.sync.read(stateBuffer)
        const restImage = PNG.sync.read(restBuffer)
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
        const diffResult = imageComparator(stateBuffer, restBuffer, { threshold: 0.2 })
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

    const safeName = item.stateId.replace(/[^a-z0-9-]+/gi, '_')
    writeFileSync(
      path.join(rawResultsDir, `${safeName}.json`),
      JSON.stringify({ ...item, unitResults: results }, null, 2),
    )
  })
}
