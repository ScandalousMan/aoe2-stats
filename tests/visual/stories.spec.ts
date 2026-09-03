// Generated per run by `scripts/visual/run.mjs`, which decides *which* stories to test (all of
// them, or only the diff-touched ones) and passes them through VISUAL_STORIES, each entry naming
// its id and whether its subject escapes the story root (a `position: fixed` element, or a
// popover that overflows its trigger's layout box — see run.mjs for why that happens), and
// whether it is a `visual-mobile` capture (375px viewport, for a layout bug that is invisible at
// the suite's default desktop width). This file stays dumb on purpose: it never re-derives scope
// or which stories need a full-page or mobile capture, it only renders what it is told to.
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

interface VisualStory {
  id: string
  fullPage: boolean
  mobile: boolean
}

const stories: VisualStory[] = JSON.parse(process.env.VISUAL_STORIES ?? '[]')

for (const { id, fullPage, mobile } of stories) {
  test(`${id} matches its visual baseline`, async ({ page }) => {
    await page.route('https://avatars.steamstatic.com/**', (route: Route) => {
      const requestUrl = new URL(route.request().url())
      if (requestUrl.pathname === STEAM_AVATAR_FIXTURE_PATH) {
        return route.fulfill({ status: 200, contentType: 'image/jpeg', body: STEAM_AVATAR_FIXTURE })
      }
      return route.fulfill({ status: 404 })
    })
    if (mobile) {
      // Width is what collapses a table to a stacked layout at the `md` breakpoint; height does
      // not affect that, and the locator/page screenshot below captures the full element or page
      // regardless of viewport height.
      await page.setViewportSize({ width: 375, height: 900 })
    }
    await page.goto(`/iframe.html?id=${id}&viewMode=story`)
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
    if (fullPage) {
      // The story's own subject (a fixed dialog, an open popover) paints outside the root
      // element's layout box, so a screenshot clipped to that element never shows it — this
      // captures the whole page instead.
      await expect(page).toHaveScreenshot(`${id}.png`)
    } else {
      await expect(root).toHaveScreenshot(`${id}.png`)
    }
  })
}
