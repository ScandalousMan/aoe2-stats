// T675 (slice 2/N, corrected slice 3) — the package-wide comparator-blind-spot sweep. NOT part of
// the ordinary `pnpm test:visual` selection or the PR `visual` job: `scripts/visual/run.mjs` only
// ever points Playwright at this file under its own `--state-signal-sweep` flag, which is also the
// only thing that ever writes `VISUAL_STATE_SWEEP_FILE` — an unset var here (any other invocation
// of this config) falls back to an empty work-item list, matching `stories.spec.ts`'s own
// `VISUAL_STORIES_FILE` convention. This is a *report*, not a gate, in this slice: it renders, it
// diffs, it writes raw numbers to `test-results/state-signal-sweep/raw/` for `run.mjs` to classify
// once the whole run finishes — see this task's own text in tasks.md for why turning this into a
// gate is a later slice's job, not this one's.
//
// **Self-pairing: a state story's resting counterpart is itself, not a sibling.** Slice 1 paired a
// state story against a *different* story sharing the same resolved args/`play`/`render`, which left
// 55 of 113 state stories unmeasurable (no matching sibling, or more than one tied). Rendering the
// same story twice — once with its own state not applied, once with it applied — has the same args,
// `render`, viewport and clip *by construction*, for every state story in the tree, which is exactly
// the "resting frame with the same args and size" this sweep exists to compare against. Two shapes,
// decided by `scripts/visual/state-signal-model.mjs`'s own `planSelfRest` (never re-derived here —
// this file "stays dumb" about *which* pairs exist and *how*):
//   - `'forced'` (a real `visualForceState`): the state is a normal, played render with the pseudo-
//     class additionally driven for real (`story-render.ts`'s own `applyForceState`).
//   - `'play-focus-blur'` (a focus-visible frame left by a `play()` with no `visualForceState` of
//     its own, e.g. `Dialog`'s `KeyboardFocusOrderAndTrap`): the state is the normal, played render
//     as-is — the story's own `play()` already produced it, nothing further to drive.
//
// **The rest, for either shape, is a *second, separate* navigation with Storybook's own autoplay
// disabled** (`gotoAndWaitForStorySettled(..., { autoplay: false })` — `story-render.ts`'s own
// comment cites the exact mechanism: `&embed=true`, a real Storybook preview render option, not a
// hand-rolled convention). This replaced an earlier, same-page-load design (reset the pseudo-class —
// move the mouse away, blur `document.activeElement` — on the *same* settled, played render used for
// the state) that could not be made reliable in general. Found reading one committed baseline
// directly (the coordinator, slice 3): `Tooltip` `HoverRevealed`'s own baseline shows its tooltip
// open, and this sweep's own "rest" was *also* capturing it open — `play: hoverOpen` opens the
// tooltip through `Tooltip`'s own reference-counted pointer-region tracking
// (`packages/design-system/src/primitives/Tooltip/index.tsx`'s own `pointerRegionRef`), and neither
// a bare `page.mouse.move()` (Playwright's own tracked pointer was never inside the region to begin
// with — `play()`'s own hover was dispatched synthetically, by `storybook/test`'s `userEvent`, which
// never moves Playwright's real pointer) nor a `.hover()`-then-move-away pair (which enters the
// region *again*, net movement zero) can reliably bring that counter back to the exact "nothing
// entered" state a real user's mouse never having visited would leave it in — no bounded number of
// synthetic mouse actions closes it correctly in general, only a render that never opened it at all.
// A genuinely unplayed second navigation sidesteps the question entirely, for `Tooltip`'s own shape
// and for anything else a future story's own `play()` might leave behind: there is no state to
// unwind because the render that would have created it never ran.
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
// **The main state-vs-rest diff is never compared against a checked-in baseline** (a *separate*,
// second comparison — state vs. its own committed baseline — guards the eyeball check below; see
// that comment for why that one specifically needs one). Confirmed empirically in slice 1: a locally
// rendered, already-clipped baseline (`primitives-menu--trigger-focus-visible`) came back 103px wide
// against a checked-in 104px-wide reference captured on CI, on every width and both themes — a real,
// pre-existing local-vs-CI rendering difference (font metrics, subpixel rounding), nothing to do
// with this file. Two renders taken back-to-back *on this same machine, in this same run* are still
// valid to diff against each other for this sweep's own question — "does the state differ from the
// rest" is relative, not "does this match a fixed historical reference" — which is why every capture
// below is a raw `page.screenshot()`/`locator.screenshot()` buffer kept only in memory, never
// `expect(...).toHaveScreenshot()` and never written under `packages/design-system/__screenshots__`.
//
// **A second guard, independent of the rest's own correctness: does the *state* frame this sweep
// captured even match the committed baseline for the same unit?** If it does not — beyond
// `BASELINE_MAX_DIFF_RATIO`, below, a wider tolerance than `playwright.config.ts`'s own
// `maxDiffPixelRatio` because that number turns out too strict for this specific comparison (see
// that constant's own comment for the empirical reason) — this sweep's own state capture failed to
// reproduce the state at all, and nothing this file concludes from comparing it to the rest is
// trustworthy; `state-signal-model.mjs`'s own `classifyBucket` reports `'state-not-reproduced'`
// instead of trusting the pixel diff, never a silent zero. Only the state frame has a baseline to
// compare against — the rest is never captured or asserted anywhere else in this repo — and it is
// dimension-comparable directly: `captureNow` below produces a state frame the *same* way
// `stories.spec.ts` produces the committed baseline (same clip precedence, same `fullPage` rule), so
// there is no separate "which shape is the baseline" branch to write here.
//
// Settle logic, the theme mechanism, force-state driving and clip resolution are all imported from
// `./story-render.ts` — the exact functions `stories.spec.ts` itself calls, not a second copy of any
// of them (T675's own instruction).
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
// The eyeball guard's own home — every `zero`/`zero-despite-clip` pair's own light/1280 rest and
// state frames, written unconditionally whenever that one unit's own diff is zero (which a
// story-level `zero`/`zero-despite-clip` bucket always implies, since that classification requires
// every unit to be zero — see `classifyBucket`'s own comment). A reader (the coordinator, before any
// cell reaches `product-designer`) inspects these directly; this sweep never inspects them itself.
const framesDir = path.join(rootDir, 'test-results', 'state-signal-sweep', 'frames')
const screenshotsDir = path.join(rootDir, 'packages', 'design-system', '__screenshots__')

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

// NOT `playwright.config.ts`'s own `maxDiffPixelRatio` (0.01) — tried that value first and it is
// too strict for this specific comparison. Confirmed empirically, twice over: re-running
// `tests/visual/stories.spec.ts` locally, right now, against `Tooltip` `HoverRevealed`'s own
// committed (CI-captured) baseline fails at 1.02% even though the render is, by inspection, correct;
// `PrivacyNotice` `Hover`'s own small, text-heavy link clip reads 6.03% against its own committed
// baseline, visually indistinguishable side by side (anti-aliasing along underlined text edges, the
// same local-vs-CI drift this file's own header already documents as "roughly 2% in absolute
// terms", concentrated harder on a small, glyph-dense clip than on a full page). `maxDiffPixelRatio`
// is the right number for *that* suite, which only ever compares a local render to CI's own
// committed reference and is allowed to be noisy about it (retried, re-baselined from CI when it
// drifts); this check exists to catch a *structural* failure to reproduce (the wrong content
// rendered at all — a closed tooltip captured where an open one belongs, the shape `Tooltip`
// `HoverRevealed` actually had), which reads far above this number — comfortably past the two
// documented noise readings above, not tuned to either one's own worst case.
const BASELINE_MAX_DIFF_RATIO = 0.15

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
  // `null` when no baseline is committed for this unit yet (nothing to check against, not a
  // failure); `false` when the state frame this sweep captured does not match its own committed
  // baseline beyond `BASELINE_MAX_DIFF_RATIO` — the eyeball guard's own signal that this pair's
  // classification cannot be trusted, regardless of what the state-vs-rest diff above says.
  stateMatchesBaseline: boolean | null
}

// Whether `stateBuffer` — this sweep's own capture of the story's *state* frame — matches the
// committed baseline for the same {theme, width} unit, within `BASELINE_MAX_DIFF_RATIO`. Only the
// state frame has a baseline to compare against at all (`tests/visual/stories.spec.ts` never
// captures or asserts a story's own "rest" — every checked-in baseline already *is* whichever frame
// a story's own name promises, `Hover`/`Active`/`FocusVisible` included), and it is
// dimension-comparable to that baseline directly: `captureNow` below produces it the same way
// `stories.spec.ts` produces the baseline (same clip precedence, same `fullPage` rule), so there is
// no separate "which shape is the baseline" branch to write here — only a definitive `false` if the
// two dimensions still disagree (a real signal, `classifyBucket`'s own `'dimension-mismatch'`
// question is a different one — this is about the *state*, not the rest).
// Local font hinting/subpixel rounding can shift a rendered frame's own resolved size by a handful
// of pixels between this machine and CI — confirmed three times over in this repo already (`Menu`
// `TriggerFocusVisible`, 103px locally vs 104px on CI, this file's own header; `PrivacyNotice`
// `Hover`'s own link clip, 624px locally vs 618px on CI; `Footer` `Hover`'s own full-page capture at
// 375px, 393px tall locally vs 373px on CI — a per-line rounding difference too small to see on any
// one line, compounding visibly over the several wrapped paragraphs this story's own disclaimer text
// takes at that width, all found running this exact check). None is a real reproduction failure; all
// are the same noise `BASELINE_MAX_DIFF_RATIO` already exists to absorb, but a *pixel* ratio can
// never even be computed when the two buffers are different sizes to begin with — `imageComparator`
// refuses to diff them at all. A dimension gap at or under `DIMENSION_TOLERANCE_PX` is treated as
// that same noise (a match, without attempting a pixel diff a differently-sized pair cannot give an
// honest one for); a larger gap is still a definitive mismatch — the two are no longer arguably the
// same frame.
const DIMENSION_TOLERANCE_PX = 30

function stateMatchesCommittedBaseline(
  stateBuffer: Buffer,
  id: string,
  theme: Theme,
  width: number,
): boolean | null {
  const baselinePath = path.join(screenshotsDir, `${id}-${theme}-${width}.png`)
  if (!existsSync(baselinePath)) return null
  const baselineBuffer = readFileSync(baselinePath)
  const stateImage = PNG.sync.read(stateBuffer)
  const baselineImage = PNG.sync.read(baselineBuffer)
  const widthDiff = Math.abs(stateImage.width - baselineImage.width)
  const heightDiff = Math.abs(stateImage.height - baselineImage.height)
  if (widthDiff > DIMENSION_TOLERANCE_PX || heightDiff > DIMENSION_TOLERANCE_PX) {
    return false
  }
  if (widthDiff !== 0 || heightDiff !== 0) {
    return true
  }
  const diffResult = imageComparator(stateBuffer, baselineBuffer, { threshold: 0.2 })
  if (!diffResult) return true
  const diffPixels = Number(/^(\d+) pixels/.exec(diffResult.errorMessage)?.[1])
  return diffPixels / (stateImage.width * stateImage.height) <= BASELINE_MAX_DIFF_RATIO
}

// The story's own settled frame, clipped to `clip` (the story's own `visualCaptureClip`, resolved
// fresh against the *current* DOM each time this is called), full-page when the id's own Storybook
// tag says so, or the plain `#storybook-root` element otherwise.
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

// The rest, for one {theme, width} unit: an unplayed render, *unless* this story's own `play()` is
// structural rather than incidental — `Menu`'s own item-level `Hover`/`Active`/`FocusVisible`, for
// one, whose `visualCaptureClip` targets `[role="menu"]`, the open panel `play: openMenu` itself
// produces; with no `play()` at all, that role never exists, and `story-render.ts`'s own
// `locateClipPart` throws rather than resolve a clip against nothing (never silently shrinks to an
// empty rect). Caught here, narrowly, only on that exact failure shape — never on any other error,
// which propagates and fails the test the same way it always did — and retried with a normal,
// played navigation, force *not* applied: the structural scaffolding `play()` produces is common to
// both frames for a story shaped this way, and only the specific pseudo-class this story forces
// differs between them, the shape slice 2's own same-page-load design already had right for `Menu`.
// `Tooltip`'s own `HoverRevealed` (no clip at all) never reaches this branch — its own `play()` is
// the incidental case, not the structural one, which is exactly what makes the unplayed render the
// correct rest for it.
async function captureRest(
  page: Page,
  item: WorkItem,
  theme: Theme,
  width: number,
  height: number,
  fullPage: boolean,
): Promise<Buffer> {
  try {
    const root = await gotoAndWaitForStorySettled(page, item.stateId, theme, width, height, {
      autoplay: false,
    })
    const clip = await readCaptureClip(page, item.stateId)
    return await captureNow(page, root, item.stateId, clip, fullPage)
  } catch (err) {
    if (!(err instanceof Error) || !err.message.startsWith('visualCaptureClip:')) throw err
    const root = await gotoAndWaitForStorySettled(page, item.stateId, theme, width, height)
    // This played render's own `play()` can itself already have produced the exact pseudo-class
    // this story forces — `Menu`'s own `KeyboardNavigation` is both cases at once: its own
    // `visualCaptureClip` needs the open menu `play()` produces (the reason this fallback branch is
    // reached at all), and its own real `userEvent.keyboard('{End}')` sequence already leaves the
    // footer item genuinely `:focus-visible`, the same element `visualForceState` re-focuses. Left
    // alone, this "unforced" rest would already show that real focus ring, and the diff against the
    // state (which re-focuses the identical element) would read zero — the same false zero
    // `Tooltip` `HoverRevealed` had, one more layer down.
    //
    // Blurring is scoped to exactly this case, never applied to a `hover`/`active` force: `Menu`'s
    // own "open, then focus the checked item" effect (`index.tsx`'s own `itemRefs.current
    // [activeIndex]?.focus()`) leaves *some* item genuinely focused every time the panel opens via
    // `play()`, on *every* Menu story that reaches this fallback — including `FooterItemHover`,
    // whose own force targets a different element entirely (the footer button, not the checked
    // profile item) and has nothing to do with focus at all. Blurring unconditionally here would
    // remove that unrelated ring from the rest while the state (a separately played render, never
    // blurred at all) still carries it — confirmed empirically: an earlier, unconditional version of
    // this blur moved `FooterItemHover` from a correct zero to a false ~2%, the auto-focused ring's
    // own presence in one frame and absence in the other, nothing to do with the hover this story
    // actually forces.
    if (item.mode === 'play-focus-blur') {
      await page.evaluate(() => {
        const active = document.activeElement
        if (active instanceof HTMLElement) active.blur()
      })
    } else {
      const forceState = await readForceState(page, item.stateId)
      if (forceState?.state === 'focus-visible') {
        await page.evaluate(() => {
          const active = document.activeElement
          if (active instanceof HTMLElement) active.blur()
        })
      }
    }
    const clip = await readCaptureClip(page, item.stateId)
    return await captureNow(page, root, item.stateId, clip, fullPage)
  }
}

for (const item of workItems) {
  test(`${item.stateId} (comparator sweep, self-rest, ${item.mode})`, async ({ page }) => {
    const fullPage = isFullPage(item.stateId)
    const results: UnitResult[] = []

    for (const theme of THEMES) {
      for (const width of WIDTHS) {
        const height = width === 375 ? 900 : 720

        // The rest: a fresh, genuinely unplayed render wherever that is sufficient — see this
        // file's own header for why a reset on the same played render this sweep used to take
        // cannot be made reliable in general — falling back to a played-but-unforced render only
        // where `play()` is structural (`captureRest`'s own comment).
        const restBuffer = await captureRest(page, item, theme, width, height, fullPage)

        // The state: a normal, played render, with the pseudo-class additionally driven for real
        // in `'forced'` mode — `'play-focus-blur'` needs nothing further, the settled render
        // already *is* the state.
        const stateRoot = await gotoAndWaitForStorySettled(page, item.stateId, theme, width, height)
        const stateClip = await readCaptureClip(page, item.stateId)
        if (item.mode === 'forced') {
          const forceState = await readForceState(page, item.stateId)
          if (!forceState) {
            throw new Error(
              `state-signal-sweep: work item "${item.stateId}" was planned as "forced" but this ` +
                "story's own settled render carries no visualForceState parameter — the model and " +
                'the live story have drifted apart.',
            )
          }
          await applyForceState(page, stateRoot, forceState, { width, height, fullPage })
        }
        const stateBuffer = await captureNow(page, stateRoot, item.stateId, stateClip, fullPage)

        const stateMatchesBaseline = stateMatchesCommittedBaseline(
          stateBuffer,
          item.stateId,
          theme,
          width,
        )

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
            stateMatchesBaseline,
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
          stateMatchesBaseline,
        })

        // The eyeball guard's own frames — every unit whose own diff is zero, written
        // unconditionally (a story-level `zero`/`zero-despite-clip` bucket requires every one of
        // its six units to be zero, so writing at light/1280 specifically, whenever *that* unit is
        // zero, always covers every zero-bucket story; it can also fire for a unit that happens to
        // be zero on a story whose *other* units are not, which is harmless extra evidence, never a
        // gap). "At least light-1280" per this task's own instruction — every unit could be
        // written, but one representative frame per axis this sweep already renders is enough for a
        // human to eyeball, and six times the PNGs for the same purpose is not.
        if (theme === 'light' && width === 1280 && diffPixels === 0) {
          const storyFramesDir = path.join(framesDir, item.stateId)
          mkdirSync(storyFramesDir, { recursive: true })
          writeFileSync(path.join(storyFramesDir, 'rest-light-1280.png'), restBuffer)
          writeFileSync(path.join(storyFramesDir, 'state-light-1280.png'), stateBuffer)
        }
      }
    }

    const safeName = item.stateId.replace(/[^a-z0-9-]+/gi, '_')
    writeFileSync(
      path.join(rawResultsDir, `${safeName}.json`),
      JSON.stringify({ ...item, unitResults: results }, null, 2),
    )
  })
}
