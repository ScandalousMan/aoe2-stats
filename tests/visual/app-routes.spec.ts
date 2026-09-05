// T108: every other file in this directory screenshots packages/design-system's Storybook build —
// a story renders one component in isolation, imported straight from packages/design-system/src,
// which is exactly where Tailwind's automatic source detection happened to work (T107's fix).
// Nothing in that suite ever loads what apps/web actually builds, so T107's regression — every
// screen shipping as unstyled markup because apps/web's own source root was never declared to
// Tailwind — left all 66 Storybook baselines green while the deployed site was broken.
//
// This file serves the production build of apps/web itself (`apps/web/dist`, the same artefact
// `.github/workflows/pr.yml`'s `web` job builds for `scripts/checks/built-css.mjs`) from a static
// file server with an SPA fallback, stubs `/api/*` with Playwright's own route interception rather
// than running `apps/api` (constitution III: no network call outside `packages/providers`), and
// screenshots the route a signed-out visitor reaches and the route a signed-in one reaches. The
// stub is the point: without one there is no session for `__root.tsx`'s `beforeLoad` to resolve,
// and nothing past the loading screen to photograph.
import { type ChildProcess, spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import path from 'node:path'
import { expect, test, type Route } from '@playwright/test'

// Playwright loads this file as CommonJS unless the nearest package.json sets `"type": "module"`
// (playwright.config.ts's own comment) — `__dirname` is what stays valid either way, not
// `import.meta.url`.
const rootDir = path.resolve(__dirname, '..', '..')
const distDir = path.join(rootDir, 'apps', 'web', 'dist')
const hasBuild = existsSync(path.join(distDir, 'index.html'))

// Distinct from Storybook's port (playwright.config.ts's `VISUAL_STORYBOOK_PORT`, default 6006)
// and from Vite's own preview default (4173), so a developer's stray `vite preview` never gets
// mistaken for this suite's server.
const port = process.env.VISUAL_APP_PORT ?? '4174'
const baseUrl = `http://127.0.0.1:${port}`

// Verbatim against `apps/web/src/lib/api.ts`'s `assertMeResponse` and
// `apps/web/src/features/profile/api.ts`'s `ProfilesResponse` — the fixture stands in for
// `apps/api`, not for the front end's own reading of a response, so it has to satisfy the same
// shape check a real router response would pass.
const SIGNED_OUT_ME = { authenticated: false }

const SIGNED_IN_ME = {
  authenticated: true,
  user_id: 'visual-suite-user',
  allowlisted: true,
  archival_objected: false,
  archival_objected_at: null,
  profiles: [{ profile_id: 4242, alias: 'VisualSuitePlayer', country: 'FR', is_primary: true }],
}

const PROFILES_RESPONSE = {
  profiles: [
    {
      profile_id: 4242,
      alias: 'VisualSuitePlayer',
      country: 'FR',
      is_primary: true,
      linked_at: '2026-01-01T00:00:00Z',
      ratings: [
        {
          leaderboard_id: 3,
          leaderboard_name: '1v1 Random Map',
          rating: 1487,
          rank: 1204,
          wins: 84,
          losses: 76,
          streak: 3,
          highest_rating: 1520,
          captured_at: '2026-08-29T09:00:00Z',
        },
      ],
    },
  ],
}

// A full-page screenshot of a built route carries far more anti-aliased text than an isolated
// component story — the whole sign-in screen or dashboard, plus the footer — so its cross-machine
// anti-aliasing drift is correspondingly larger: a baseline generated on one Linux renders ~2% of
// pixels different against another (GitHub's `ubuntu-latest` vs the Playwright container measured
// here), which clears playwright.config.ts's 0.01 default that the small component stories stay
// under. 0.05 absorbs that machine noise while staying an order of magnitude below the regression
// this suite exists to catch — T107's every-screen-unstyled defect changed essentially every
// pixel, not two in a hundred. Keeping the ratio here rather than in the config leaves the
// component floor tight and lets these baselines regenerate on any dev machine, the same way the
// design-system ones already do.
const FULL_PAGE = { fullPage: true, maxDiffPixelRatio: 0.05 } as const

let server: ChildProcess | undefined

async function isReachable(): Promise<boolean> {
  try {
    const response = await fetch(baseUrl)
    return response.ok
  } catch {
    return false
  }
}

async function waitUntilReachable(timeoutMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (await isReachable()) return
    await new Promise((resolve) => setTimeout(resolve, 200))
  }
  throw new Error(`the built application's server never answered at ${baseUrl}`)
}

async function fulfillJson(route: Route, body: unknown): Promise<void> {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
}

test.describe('the built application, served and stubbed', () => {
  // Serial rather than `fullyParallel`'s default (playwright.config.ts): both tests below share
  // one static server, started once in `beforeAll` and torn down in `afterAll` — full parallelism
  // would risk two workers racing to bind the same port.
  test.describe.configure({ mode: 'serial' })

  // Mirrors `scripts/visual/run.mjs`'s own "nothing to test yet" short-circuit for a missing
  // Storybook build: a skip here is not the T015a/T038b/T108 failure shape it looks like, because
  // `.github/workflows/pr.yml`'s `visual` job always runs `pnpm --filter web build` immediately
  // before this file — the skip only ever fires for a developer running this file in isolation
  // without having built first, the same case `run.mjs` prints a message for and exits 0 on.
  test.skip(
    () => !hasBuild,
    'apps/web/dist has not been built — run `pnpm --filter web build` first.',
  )

  test.beforeAll(async () => {
    if (await isReachable()) {
      // Another worker already bound this port (or a developer has their own server running on
      // it) — reuse it rather than fail on `--strictPort`, the same idea Playwright's own
      // `webServer.reuseExistingServer` expresses for the Storybook server this config already
      // starts.
      return
    }
    // `-P <self>?` is `http-server`'s SPA fallback (a root devDependency already — the same tool
    // playwright.config.ts uses to serve Storybook): any request that does not resolve to a file
    // under apps/web/dist is proxied back to this server's own root, which serves `index.html`.
    // Verified against a real build: `/dashboard` and `/sign-in` both answer 200 with the shell,
    // matching what Vercel's own catch-all rewrite (T109, vercel.json) does in production, while a
    // built asset under `/assets/` still answers straight from disk rather than being swallowed by
    // it.
    server = spawn(
      'pnpm',
      ['exec', 'http-server', distDir, '--port', port, '-P', `${baseUrl}?`, '--silent'],
      { cwd: rootDir, stdio: 'ignore' },
    )
    await waitUntilReachable(20_000)
  })

  test.afterAll(() => {
    // A no-op when this worker found the port already reachable above and never spawned anything.
    server?.kill()
  })

  test('a signed-out visitor lands on the sign-in screen', async ({ page }) => {
    await page.route('**/api/me', (route) => fulfillJson(route, SIGNED_OUT_ME))

    // `__root.tsx`'s `beforeLoad` resolves the session through `GET /api/me` before anything
    // paints; `routes/index.tsx`'s own `beforeLoad` then redirects an unauthenticated visitor to
    // `/sign-in` — the root itself never renders, so this is the same landing an ordinary
    // signed-out visit produces.
    await page.goto(`${baseUrl}/`)
    await page.waitForURL('**/sign-in')
    await expect(page.getByRole('button', { name: 'Continue with Steam' })).toBeVisible()

    // typography-tokens.md §10: with `font-display: swap` a capture taken before the fonts finish
    // loading bakes in the fallback face — the DOM has rendered, but the render has not finished.
    // Waited here, after the page has settled and before the screenshot.
    await page.evaluate(() => document.fonts.ready)
    await expect(page).toHaveScreenshot('app-signed-out-sign-in.png', FULL_PAGE)
  })

  test('a signed-in visitor lands on the dashboard', async ({ page }) => {
    await page.route('**/api/me', (route) => fulfillJson(route, SIGNED_IN_ME))
    await page.route('**/api/profiles', (route) => fulfillJson(route, PROFILES_RESPONSE))

    await page.goto(`${baseUrl}/`)
    await page.waitForURL('**/dashboard')
    await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible()
    await expect(page.getByText('VisualSuitePlayer')).toBeVisible()

    // typography-tokens.md §10: see the identical wait and comment above.
    await page.evaluate(() => document.fonts.ready)
    await expect(page).toHaveScreenshot('app-signed-in-dashboard.png', FULL_PAGE)
  })
})
