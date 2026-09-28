// Generated per run by `scripts/visual/run.mjs`, which decides *which* stories to test (all of
// them, or only the diff-affected ones) and expands each into one capture unit per {theme, width}
// pair — {light, dark} x {375, 768, 1280}, T504, FR-060/FR-061/SC-006. Each unit names its story
// id, its theme, its width and whether its subject escapes the story root (a `position: fixed`
// element, or a popover that overflows its trigger's layout box — see run.mjs for why that
// happens). This file stays dumb on purpose: it never re-derives scope or which axes apply to
// which story, it only renders what it is told to.
//
// The units travel as JSON in a file, named by `VISUAL_STORIES_FILE`, not inline in an env var
// (`VISUAL_STORIES`, retired): Linux caps a single argv/envp string at `MAX_ARG_STRLEN` (128 KiB),
// and the full, unscoped matrix's JSON is ~166 KB — comfortably over that ceiling on its own — so
// `run.mjs`'s `spawnSync` failed with `E2BIG` before Playwright ever started (confirmed on CI, run
// 33971176171). A path is a few dozen bytes regardless of how many units it names, which removes
// the ceiling entirely rather than working around it (chunking, as `.github/workflows/
// baselines.yml` used to, before this same file transport replaced its batching too).
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { test, expect, type Route } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
// `.cjs`, not `.mjs` — see that file's header comment. An `.mjs` sibling imported from here used to
// crash on CI (never locally): Playwright transpiles this spec to CommonJS, and a transpiled `.mjs`
// import is ambiguous to Node's loader in a way a `.cjs` import — unambiguously CommonJS by
// extension alone — cannot be.
import {
  componentFromTitle,
  isAllowed,
  recordScanned,
  recordViolation,
} from '../../scripts/visual/a11y-scan.cjs'
// T675 (slice 1/N): the settle logic, force-state driving and clip resolution below used to live
// inline in this file; factored out so `tests/visual/state-signal-sweep.spec.ts` can reuse the
// exact same functions rather than a second copy of any of them — see that module's own header.
import {
  applyForceState,
  gotoAndWaitForStorySettled,
  readCaptureClip,
  readForceState,
  resolveCaptureClip,
} from './story-render'

// Playwright loads this file as CommonJS unless the nearest package.json sets `"type": "module"`
// (playwright.config.ts's own comment) — `__dirname` is what stays valid either way.
const rootDir = path.resolve(__dirname, '..', '..')

// T507 (FR-057, FR-058, SC-007): each unit (below) carries only its story id, not its Storybook
// `title`, and the axe allowlist keys its entries by a human-readable component name
// derived from that title (see `componentFromTitle`) rather than by the raw id — so this reads the
// same built Storybook index `scripts/visual/run.mjs` already reads, purely to recover `title` for
// each id. This is a one-time lookup at module load, not part of the render loop below.
const storybookIndexPath = path.join(rootDir, 'packages/design-system/storybook-static/index.json')
const titleById = new Map<string, string>()
if (existsSync(storybookIndexPath)) {
  const index = JSON.parse(readFileSync(storybookIndexPath, 'utf8')) as {
    entries?: Record<string, { id: string; title: string }>
    stories?: Record<string, { id: string; title: string }>
  }
  for (const entry of Object.values(index.entries ?? index.stories ?? {})) {
    titleById.set(entry.id, entry.title)
  }
}

// The axe scan is a DOM/semantics question, not a rendering one: the same story in the same theme
// answers it identically at 375, 768 and 1280, so it runs once per story-theme pair rather than
// once per capture unit. 1280 is the designated width — fixed and named here, not "whichever unit
// happens to run first" (units run in parallel across workers with no defined order) — because it
// is the width every pre-existing baseline was captured at before T504 added the width axis, so it
// renders every story's full, uncollapsed structure rather than whatever a narrower breakpoint's
// structural swap (FR-019) produces.
const AXE_SCAN_WIDTH = 1280

// `player-avatar.md` §9 "the visual baseline must not depend on Steam": `PlayerAvatar` builds
// `https://avatars.steamstatic.com/<hash>_full.jpg` itself (that spec §2b), so any story that
// composes a loaded avatar fires a real request to that host unless it is fulfilled here from a
// local fixture. Applied unconditionally to every story in the loop below rather than only to the
// ones known to carry an avatar — this file stays "dumb" (see the header comment above) and never
// has to learn which story ids need which stub. Harmless for a story that never hits the host.
const STEAM_AVATAR_FIXTURE = readFileSync(
  path.join(rootDir, 'tests/visual/fixtures/steam-avatar.jpg'),
)

// The one hash `PlayerAvatar.stories.tsx` and `ProfileSummary.stories.tsx` both call
// `FIXTURE_HASH` / `FIXTURE_AVATAR_HASH` — a "Loaded" story is only real if it is genuinely a
// loaded image, so this is the only path the stub answers with the fixture above. Everything else
// under this host (`PlayerAvatar`'s `FailedHash` story deliberately builds a URL from a hash the
// CDN would never serve) is answered with a 404, so `onError` still fires and `FailedHash` stays
// pixel-identical to the empty-hash story — the one identity `player-avatar.md` §9 exists to
// prove. A stub that fulfilled every request on this host indiscriminately would make that story
// indistinguishable from `Loaded` and quietly retire the assertion it stands for.
const STEAM_AVATAR_FIXTURE_PATH = '/0123456789abcdef0123456789abcdef01234567_full.jpg'

type Theme = 'light' | 'dark'

interface VisualStory {
  id: string
  theme: Theme
  width: number
  fullPage: boolean
}

// `run.mjs` always sets `VISUAL_STORIES_FILE`; `tests/visual/app-routes.spec.ts` is Playwright's
// other spec under this same config and takes no units at all, so an unset var here (any run that
// selects `stories.spec.ts` at all comes from `run.mjs` or `baselines.yml`, both of which set it)
// falls back to an empty list rather than throwing.
const storiesFilePath = process.env.VISUAL_STORIES_FILE
const stories: VisualStory[] = storiesFilePath
  ? (JSON.parse(readFileSync(storiesFilePath, 'utf8')) as VisualStory[])
  : []

// T673 (FR-047, item 9's second half — "every story is deterministic"): true only under
// `playwright.config.ts`'s own `determinism` project, which registers *instead of* `chromium`
// (never alongside it) and only when this var is `1` — see that file's comment for why the whole
// `projects` array swaps rather than adding a second one. Read directly, not derived from
// `VISUAL_DETERMINISM_DIR` or any other var, so this branch can never be entered by accident: the
// moment this is true, `playwright.config.ts` has also set `updateSnapshots: 'all'` for the whole
// run and pointed the `determinism` project's own `snapshotPathTemplate` at
// `test-results/determinism` (or `VISUAL_DETERMINISM_DIR`, if set) — never at
// `packages/design-system/__screenshots__` — so there is no path through this file, under this
// var, that can touch a checked-in baseline.
const determinismMode = process.env.RUN_DETERMINISM === '1'

for (const { id, theme, width, fullPage } of stories) {
  test(`${id} matches its visual baseline (${theme}, ${width})`, async ({ page }, testInfo) => {
    await page.route('https://avatars.steamstatic.com/**', (route: Route) => {
      const requestUrl = new URL(route.request().url())
      if (requestUrl.pathname === STEAM_AVATAR_FIXTURE_PATH) {
        return route.fulfill({ status: 200, contentType: 'image/jpeg', body: STEAM_AVATAR_FIXTURE })
      }
      return route.fulfill({ status: 404 })
    })
    // Width is what collapses a table to a stacked layout at the `md` breakpoint; height's only
    // job here is to stay identical to what every pre-existing baseline was already captured at,
    // because a `fullPage: false` (element-clipped) screenshot is height-independent but a
    // `fullPage: true` one (a fixed dialog, a popover) is not: a fixed-position dialog centers
    // against the viewport, so a taller viewport measurably shifts its content (confirmed: T505's
    // first attempt used height 900 unconditionally and moved 44 pre-existing baselines, four of
    // them `AccountErasePanel` dialogs, by a real 15-20% pixel diff, not a tolerance artifact).
    // Before T504, only the ten `visual-mobile`-tagged stories called `setViewportSize` at all, at
    // {375, 900}; every other capture had no explicit call and rendered at Playwright's
    // `devices['Desktop Chrome']` preset default, {1280, 720}. T504 made every width call this
    // unconditionally (correctly — the loop needs one shape for every unit, matching this file's
    // "stays dumb" rule above) but collapsed the height to one constant, which broke that
    // inherited identity for every 1280-wide capture. So: 375 keeps its pre-existing 900, and
    // every other width — including the new 768, which has no pre-existing baseline to match —
    // uses the desktop default of 720, so 768 and 1280 share one convention instead of inventing a
    // third with no history behind it. Do not simplify this back to one constant.
    const height = width === 375 ? 900 : 720
    // Mirrors `tests/visual/focus-ring.spec.ts`'s exact URL pattern for driving the theme global.
    // Storybook mounts every story under this id; waiting for it removes the render race that
    // would otherwise make the very first screenshot after a baseline change flaky. Storybook
    // 10.5.9 exposes the render driving this story as an entry in
    // `window.__STORYBOOK_PREVIEW__.storyRenders` (confirmed by reading the installed
    // `storybook/dist/preview/runtime.js`'s `StoryRender` class, not assumed from an API guess);
    // `gotoAndWaitForStorySettled` (factored into `story-render.ts`, T675) waits for its `.phase`
    // to reach `completed`/`finished`/`errored` — the same state a story with a `play()` AND one
    // without eventually both reach — and for web fonts to finish loading before returning.
    const root = await gotoAndWaitForStorySettled(page, id, theme, width, height)

    // Remediation of T565's blocking finding (see `story-render.ts`'s own `VisualForceState`
    // comment): drives the real CSS pseudo-class a vocabulary-state story names, in this real
    // browser, after the story has settled and before anything reads or captures it — a real
    // `:hover`/`:active` must still be showing at the moment of the screenshot below, and the axe
    // scan just after this block runs against the same forced DOM state a reader would actually see.
    const forceState = await readForceState(page, id)
    let releaseMouseAfterCapture = false
    if (forceState) {
      ;({ releaseMouseAfterCapture } = await applyForceState(page, root, forceState, {
        width,
        height,
        fullPage,
      }))
    }

    // T507 (FR-057, FR-058, SC-007): runs here, on the same settled DOM the screenshot below is
    // about to capture — "at the point the screenshot is taken" — but *before* that assertion
    // rather than after: `toHaveScreenshot` throws on the first pixel mismatch, and a real (or
    // locally-rendered, research D3) diff must never silently skip the accessibility check for a
    // story that would otherwise have been scanned this run. Only once per story-theme pair, at
    // the designated width (see `AXE_SCAN_WIDTH` above), not once per capture unit, and reusing
    // this loop's scoping and theme mechanism rather than a second harness (research D12).
    // Skipped entirely under the determinism harness (`determinismMode`): it is a DOM/semantics
    // question, not a rendering one (see `AXE_SCAN_WIDTH`'s own comment above), so it has nothing
    // to say about render-to-render stability, and running it twice per story on every nightly
    // determinism pass would double an already-expensive scan for no gain in what this harness
    // catches. `checkStaleness()` (`scripts/visual/a11y-scan.cjs`) never misreads "not scanned this
    // run" as "scanned and found nothing" — it only flags an allowlist entry for a component this
    // run's own `scanned.ndjson` recorded, so skipping the scan here produces no false staleness
    // finding.
    if (width === AXE_SCAN_WIDTH && !determinismMode) {
      const component = componentFromTitle(titleById.get(id) ?? id)
      // Scoped to `#storybook-root` — the story's own wrapper — rather than the whole page.
      // Confirmed empirically (not assumed): scanning the whole `iframe.html` document reports
      // `landmark-one-main` and `page-has-heading-one` on *every single story*, because axe's
      // page-level rules run against `document` the moment the include selector is not scoped —
      // and a component preview correctly has neither; only a full application page owns a main
      // landmark and a heading. Those are Storybook's chrome, not the design system's, exactly the
      // failure mode this comment is here to explain. Scoping to the root removes them entirely and
      // still catches every element-level rule (color-contrast, aria-*, button-name, and so on).
      // A `visual-full-page` story's subject (a fixed dialog, an open popover) still gets scanned
      // even though its *screenshot* goes full-page: none of these components use a portal
      // (`ReactDOM.createPortal`, confirmed absent from `packages/design-system/src`), so a
      // `position: fixed` element stays a DOM descendant of `#storybook-root` — only its painted
      // position escapes the root's layout box, which is a screenshot-clipping concern, not a DOM
      // membership one, and axe's `include` scopes by the latter.
      const axeResults = await new AxeBuilder({ page }).include('#storybook-root').analyze()

      // Recorded whether or not the rule below turns out to be allowlisted, and even when this
      // story has no violation at all — `checkStaleness` (in `run.mjs`, after the whole suite
      // finishes) needs every component this run actually scanned, not only the ones that failed,
      // to tell "the fix already happened" (stale) apart from "this run never looked" (silent).
      recordScanned(component, theme)
      for (const violation of axeResults.violations) {
        recordViolation(component, theme, violation.id)
      }

      const unallowed = axeResults.violations.filter(
        (violation) => !isAllowed(component, violation.id),
      )
      if (unallowed.length > 0) {
        const details = unallowed
          .map((violation) => {
            const nodes = violation.nodes
              .map((node) => `      ${node.target.join(' ')}\n      ${node.html}`)
              .join('\n')
            return `  [${violation.impact ?? 'unknown'}] ${violation.id} — ${violation.help}\n${nodes}`
          })
          .join('\n')
        throw new Error(
          `axe-core found ${unallowed.length} accessibility violation(s) in "${component}" ` +
            `(${theme} theme, story ${id}) not covered by scripts/visual/a11y-allowlist.json:\n${details}`,
        )
      }
    }

    const baselineName = `${id}-${theme}-${width}.png`
    // `visualCaptureClip` takes precedence over `fullPage` (T591): a story that carries both would
    // mean its own `visual-full-page` tag was never removed when the clip was added — the clip is
    // still the more specific, more correct capture, so it wins rather than the two silently racing.
    const captureClip = await readCaptureClip(page, id)

    // T673: a pure snapshot-*name* switch, never a second capture mechanism — every branch below
    // still calls `expect(...).toHaveScreenshot`, with the same clip/fullPage arguments, on the
    // same settled DOM, and inherits that matcher's own defaults (`animations: 'disabled'`,
    // `caret: 'hide'`, `scale: 'css'`) and its own stability loop (retakes until two consecutive
    // captures match) unchanged — a raw `page.screenshot`/`root.screenshot` has none of those and
    // would be proving a different render's stability than the one the baseline suite captures,
    // exactly the gap `reviewer` found in this file's first version. `toHaveScreenshot`'s first
    // argument accepts a `string[]`, joined as path segments (confirmed against the installed
    // `playwright@1.62.1`'s own `SnapshotHelper`, `node_modules/playwright/lib/matchers/
    // expect.js`), so under `determinismMode` the name becomes `['pass-<repeatEachIndex>',
    // baselineName]` — `playwright.config.ts`'s own `determinism` project resolves that through
    // its `snapshotPathTemplate` into `test-results/determinism/pass-<index>/<baselineName>`
    // (or `VISUAL_DETERMINISM_DIR`, if set), never into `packages/design-system/__screenshots__`.
    // The baseline path (`determinismMode` false) passes the plain `baselineName` exactly as
    // before — byte-for-byte the code this file always ran.
    //
    // The snapshot this produces is *always* "missing" on first sight — `test-results/` is
    // gitignored and each pass gets its own subdirectory — so `playwright.config.ts` sets
    // `updateSnapshots: 'all'` for the whole run whenever `determinismMode` is true: verified
    // empirically (not assumed) against the installed version that Playwright's *default* mode,
    // `'missing'`, does write the file but still fails the test (a `softError` that
    // `workerProcessEntry.js`'s `_failWithError` promotes to a real failure even though the
    // matcher itself returns `pass: true`); `'all'` writes the same file and returns no
    // `softError`, so the test passes. Since `determinismMode` and `updateSnapshots: 'all'` are
    // set by the same env var in the same config file, this can never fire against a real
    // baseline comparison — the `chromium` project (the only one registered whenever
    // `updateSnapshots` is left at its default `'missing'`) never sees `'all'`.
    const snapshotName: string | string[] = determinismMode
      ? [`pass-${testInfo.repeatEachIndex}`, baselineName]
      : baselineName

    if (captureClip) {
      const clip = await resolveCaptureClip(page, root, id, captureClip)
      await expect(page).toHaveScreenshot(snapshotName, { fullPage: true, clip })
    } else if (fullPage) {
      // The story's own subject (a fixed dialog, an open popover) paints outside the root
      // element's layout box, so a screenshot clipped to that element never shows it — this
      // captures the whole page instead.
      await expect(page).toHaveScreenshot(snapshotName)
    } else {
      await expect(root).toHaveScreenshot(snapshotName)
    }

    // Releases the real mouse-down `active` above started — harmless to skip (the page closes with
    // the test either way), done anyway so a future addition after this block never inherits a
    // button Playwright still believes is held down.
    if (releaseMouseAfterCapture) {
      await page.mouse.up()
    }
  })
}
