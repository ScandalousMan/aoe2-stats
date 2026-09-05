// Generated per run by `scripts/visual/run.mjs`, which decides *which* stories to test (all of
// them, or only the diff-affected ones) and expands each into one capture unit per {theme, width}
// pair — {light, dark} x {375, 768, 1280}, T504, FR-060/FR-061/SC-006 — passed through
// VISUAL_STORIES. Each unit names its story id, its theme, its width and whether its subject
// escapes the story root (a `position: fixed` element, or a popover that overflows its trigger's
// layout box — see run.mjs for why that happens). This file stays dumb on purpose: it never
// re-derives scope or which axes apply to which story, it only renders what it is told to.
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { test, expect, type Route } from '@playwright/test'

// Playwright loads this file as CommonJS unless the nearest package.json sets `"type": "module"`
// (playwright.config.ts's own comment) — `__dirname` is what stays valid either way.
const rootDir = path.resolve(__dirname, '..', '..')

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
