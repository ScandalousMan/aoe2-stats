// Generated per run by `scripts/visual/run.mjs`, which decides *which* stories to test (all of
// them, or only the diff-affected ones) and expands each into one capture unit per {theme, width}
// pair — {light, dark} x {375, 768, 1280}, T504, FR-060/FR-061/SC-006 — passed through
// VISUAL_STORIES. Each unit names its story id, its theme, its width and whether its subject
// escapes the story root (a `position: fixed` element, or a popover that overflows its trigger's
// layout box — see run.mjs for why that happens). This file stays dumb on purpose: it never
// re-derives scope or which axes apply to which story, it only renders what it is told to.
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { test, expect, type Route } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import {
  componentFromTitle,
  isAllowed,
  recordScanned,
  recordViolation,
} from '../../scripts/visual/a11y-scan.mjs'

// Playwright loads this file as CommonJS unless the nearest package.json sets `"type": "module"`
// (playwright.config.ts's own comment) — `__dirname` is what stays valid either way.
const rootDir = path.resolve(__dirname, '..', '..')

// T507 (FR-057, FR-058, SC-007): `VISUAL_STORIES` (below) carries only each unit's story id, not
// its Storybook `title`, and the axe allowlist keys its entries by a human-readable component name
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

const stories: VisualStory[] = JSON.parse(process.env.VISUAL_STORIES ?? '[]')

for (const { id, theme, width, fullPage } of stories) {
  test(`${id} matches its visual baseline (${theme}, ${width})`, async ({ page }) => {
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
    await page.setViewportSize({ width, height: width === 375 ? 900 : 720 })
    // Mirrors `tests/visual/focus-ring.spec.ts`'s exact URL pattern for driving the theme global.
    await page.goto(`/iframe.html?id=${id}&viewMode=story&globals=theme:${theme}`)
    // Storybook mounts every story under this id; waiting for it removes the render race that
    // would otherwise make the very first screenshot after a baseline change flaky.
    const root = page.locator('#storybook-root')
    await root.waitFor({ state: 'visible' })
    // `waitFor({ state: 'visible' })` only proves the root element exists — it says nothing about
    // whether the story is still mutating the DOM. Playwright's own screenshot stability polling
    // (retinting until two consecutive frames match) only kicks in once a baseline already exists;
    // the very first capture of a story — which is exactly the state a new baseline is taken from —
    // fires immediately with no such polling. A story with a `play()` (Tooltip's hover/focus-reveal
    // stories among them) is still running its interaction, and possibly a CSS transition it
    // triggered, well after the root is visible, so that first screenshot can bake in a pre-play or
    // mid-transition frame.
    //
    // Storybook 10.5.9 exposes the render driving this story as an entry in
    // `window.__STORYBOOK_PREVIEW__.storyRenders` (confirmed by reading the installed
    // `storybook/dist/preview/runtime.js`'s `StoryRender` class, not assumed from an API guess).
    // Its `.phase` advances `preparing -> loading -> rendering -> playing -> played -> completing
    // -> completed -> afterEach -> finished` for a story that renders cleanly, and short-circuits
    // to `errored` (still followed by `finished`) if the story or its `play()` throws. `completing`
    // is where Storybook itself awaits any CSS transition or Web Animation the story's own render
    // started (its `waitForAnimations`) — the exact class of thing `duration-120` fade-ins like
    // Tooltip's reveal are — so `played` alone is not enough: it fires *before* that wait. Waiting
    // past it, for `completed` (or `finished`/`errored`, reached by a story with no `play()` at all
    // or one whose `play()` failed), is therefore what a story with a play function AND a story
    // without one both eventually reach — no per-story branching, no knowledge here of which
    // stories carry a `play()`, matching this file's "stays dumb" rule above.
    await page.waitForFunction(
      (storyId: string) => {
        const preview = (
          window as unknown as {
            __STORYBOOK_PREVIEW__?: { storyRenders?: { id: string; phase?: string }[] }
          }
        ).__STORYBOOK_PREVIEW__
        const render = preview?.storyRenders?.find((r) => r.id === storyId)
        return !!render && ['completed', 'finished', 'errored'].includes(render.phase ?? '')
      },
      id,
      { timeout: 5_000 },
    )
    // T507 (FR-057, FR-058, SC-007): runs here, on the same settled DOM the screenshot below is
    // about to capture — "at the point the screenshot is taken" — but *before* that assertion
    // rather than after: `toHaveScreenshot` throws on the first pixel mismatch, and a real (or
    // locally-rendered, research D3) diff must never silently skip the accessibility check for a
    // story that would otherwise have been scanned this run. Only once per story-theme pair, at
    // the designated width (see `AXE_SCAN_WIDTH` above), not once per capture unit, and reusing
    // this loop's scoping and theme mechanism rather than a second harness (research D12).
    if (width === AXE_SCAN_WIDTH) {
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
    if (fullPage) {
      // The story's own subject (a fixed dialog, an open popover) paints outside the root
      // element's layout box, so a screenshot clipped to that element never shows it — this
      // captures the whole page instead.
      await expect(page).toHaveScreenshot(baselineName)
    } else {
      await expect(root).toHaveScreenshot(baselineName)
    }
  })
}
