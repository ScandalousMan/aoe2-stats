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
// screenshots every route this application declares (`apps/web/src/routes/`, `index.tsx` excepted
// — it only ever redirects, so it never paints a landmark of its own to check).
//
// T553 (FR-022, SC-003): the check that matters in this file is not the screenshot at all — it is
// `expectExactlyOneMain` below. Counting `<main>` elements is cheap and machine-independent, which
// is exactly why this defect (a route nesting two landmarks, or a shell rendering none) survived
// 279 baselines on every authenticated route: nobody was counting, and a screenshot diff a person
// skims does not notice a landmark that duplicated without moving a pixel. Every route is captured
// in both themes too (`ds-theme-override`, seeded before navigation the way `ThemeProvider.tsx`
// reads it), because production-readiness item 13 ("every route in both themes") is otherwise a
// sentence with no harness behind it.
import { type ChildProcess, spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import path from 'node:path'
import { expect, test, type Page, type Route } from '@playwright/test'

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

// `apps/web/src/features/favourites/api.ts`'s `assertFavouritesResponse` — every route that mounts
// `PlayerProfileContainer` or `FavouritesContainer` reads this one, and an empty list is a
// perfectly valid answer (US1 scenario 5's own "never-ranked is not an error" rule extended to
// "never-favourited").
const FAVOURITES_RESPONSE = { favourites: [] }

// `apps/web/src/features/matches/api.ts`'s `assertMatchesResponse` — shared verbatim by
// `GET /api/matches` (`MatchHistoryContainer`) and `GET /api/players/{profile_id}/matches`
// (`PlayerMatchHistoryContainer`), which is why one fixture answers both.
const MATCHES_RESPONSE = { matches: [], next_cursor: null }

// A third party's profile (`apps/web/src/features/players/api.ts`'s `assertPlayerProfileResponse`)
// — deliberately a different `profile_id` from `PROFILES_RESPONSE` above, since FR-008a property 1
// is "any profile", never "mine".
const THIRD_PARTY_PROFILE_ID = 9001

const PLAYER_PROFILE_RESPONSE = {
  profile_id: THIRD_PARTY_PROFILE_ID,
  alias: 'ThirdPartyPlayer',
  country: 'DE',
  avatar_hash: null,
  alias_observed_at: null,
  ratings: [
    {
      leaderboard_id: 3,
      leaderboard_name: '1v1 Random Map',
      rating: 1602,
      rank: 890,
      wins: 40,
      losses: 31,
      streak: -2,
      highest_rating: 1650,
      captured_at: '2026-08-29T09:00:00Z',
    },
  ],
}

// `apps/web/src/features/matches/api.ts`'s `assertMatchDetailResponse` — an empty `participants`
// array is valid (the assertion only walks whatever the array holds), so this stays minimal rather
// than restating that module's full participant/replay shape for a route this task does not
// screenshot for its content.
const SAMPLE_GAME_ID = '555000123'

const MATCH_DETAIL_RESPONSE = {
  game_id: Number(SAMPLE_GAME_ID),
  started_at: '2026-08-29T09:00:00Z',
  completed_at: '2026-08-29T09:45:00Z',
  map_name: 'Arabia',
  leaderboard_id: 3,
  leaderboard_name: '1v1 Random Map',
  duration_seconds: 2700,
  patch: '101.102.XXXXX.0',
  participants: [],
  capture_status: null,
  capture_deadline_at: null,
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

// `packages/design-system/src/theme/ThemeProvider.tsx`'s `THEME_STORAGE_KEY`, restated here rather
// than imported: this file drives the built `apps/web/dist` artefact from outside the package
// graph entirely (this suite's own module docstring), so it has no import path to that module —
// the same reason `apps/web/index.html`'s inline script restates the literal key rather than
// importing it.
const THEME_STORAGE_KEY = 'ds-theme-override'

type ThemeOverride = 'light' | 'dark'

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

// Seeded with Playwright's own `addInitScript`, which runs before any of the page's own scripts —
// including `apps/web/index.html`'s inline, blocking theme-resolution script (T533) — so no
// capture ever races the un-themed first paint the way a post-navigation
// `page.evaluate(() => localStorage.setItem(...))` would.
async function seedThemeOverride(page: Page, theme: ThemeOverride): Promise<void> {
  await page.addInitScript(([key, value]) => window.localStorage.setItem(key, value), [
    THEME_STORAGE_KEY,
    theme,
  ] as const)
}

// FR-022/SC-003: the substance of T553. `getByRole('main')` reaches every `<main>` regardless of
// nesting depth — exactly the shape the pre-retrofit defect took (structural-tier.md §5's "ten
// deep in total") — so this fails loudly on zero (the shell rendered nothing) or two-or-more (a
// route still assembling its own landmark alongside `Page`'s), and the message names which route
// failed rather than leaving a bare "expected 1, received 2".
async function expectExactlyOneMain(page: Page, routeLabel: string): Promise<void> {
  await expect(
    page.getByRole('main'),
    `${routeLabel} must render exactly one main landmark`,
  ).toHaveCount(1)
}

// typography-tokens.md §10: with `font-display: swap` a capture taken before the fonts finish
// loading bakes in the fallback face — the DOM has rendered, but the render has not finished.
async function waitForFontsReady(page: Page): Promise<void> {
  await page.evaluate(() => document.fonts.ready)
}

async function stubMe(page: Page, response: unknown): Promise<void> {
  await page.route('**/api/me', (route) => fulfillJson(route, response))
}

async function stubProfiles(page: Page): Promise<void> {
  await page.route('**/api/profiles', (route) => fulfillJson(route, PROFILES_RESPONSE))
}

async function stubFavourites(page: Page): Promise<void> {
  await page.route('**/api/favourites', (route) => fulfillJson(route, FAVOURITES_RESPONSE))
}

// `MatchHistoryContainer`'s own `matchesQueryOptions` always names `profile_id` on the query
// string (`features/matches/api.ts`) — the glob's literal `?` matches that, whatever value follows.
async function stubMatchesList(page: Page): Promise<void> {
  await page.route('**/api/matches?*', (route) => fulfillJson(route, MATCHES_RESPONSE))
}

async function stubMatchDetail(page: Page, gameId: string): Promise<void> {
  await page.route(`**/api/matches/${gameId}`, (route) => fulfillJson(route, MATCH_DETAIL_RESPONSE))
}

async function stubPlayerProfile(page: Page, profileId: number): Promise<void> {
  await page.route(`**/api/players/${profileId}`, (route) =>
    fulfillJson(route, PLAYER_PROFILE_RESPONSE),
  )
}

async function stubPlayerMatches(page: Page, profileId: number): Promise<void> {
  await page.route(`**/api/players/${profileId}/matches*`, (route) =>
    fulfillJson(route, MATCHES_RESPONSE),
  )
}

test.describe('the built application, served and stubbed', () => {
  // Serial rather than `fullyParallel`'s default (playwright.config.ts): every test below shares
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

  test('a signed-out visitor lands on the sign-in screen (light)', async ({ page }) => {
    await seedThemeOverride(page, 'light')
    await stubMe(page, SIGNED_OUT_ME)

    // `__root.tsx`'s `beforeLoad` resolves the session through `GET /api/me` before anything
    // paints; `routes/index.tsx`'s own `beforeLoad` then redirects an unauthenticated visitor to
    // `/sign-in` — the root itself never renders, so this is the same landing an ordinary
    // signed-out visit produces.
    await page.goto(`${baseUrl}/`)
    await page.waitForURL('**/sign-in')
    await expect(page.getByRole('button', { name: 'Continue with Steam' })).toBeVisible()
    await expectExactlyOneMain(page, '/sign-in')

    await waitForFontsReady(page)
    await expect(page).toHaveScreenshot('app-signed-out-sign-in.png', FULL_PAGE)
  })

  test('a signed-out visitor lands on the sign-in screen (dark)', async ({ page }) => {
    await seedThemeOverride(page, 'dark')
    await stubMe(page, SIGNED_OUT_ME)

    await page.goto(`${baseUrl}/`)
    await page.waitForURL('**/sign-in')
    await expect(page.getByRole('button', { name: 'Continue with Steam' })).toBeVisible()
    await expectExactlyOneMain(page, '/sign-in')

    await waitForFontsReady(page)
    await expect(page).toHaveScreenshot('app-signed-out-sign-in-dark.png', FULL_PAGE)
  })

  test('a signed-in visitor lands on the dashboard (light)', async ({ page }) => {
    await seedThemeOverride(page, 'light')
    await stubMe(page, SIGNED_IN_ME)
    await stubProfiles(page)

    await page.goto(`${baseUrl}/`)
    await page.waitForURL('**/dashboard')
    await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible()
    await expect(page.getByText('VisualSuitePlayer')).toBeVisible()
    await expectExactlyOneMain(page, '/dashboard')

    await waitForFontsReady(page)
    await expect(page).toHaveScreenshot('app-signed-in-dashboard.png', FULL_PAGE)
  })

  test('a signed-in visitor lands on the dashboard (dark)', async ({ page }) => {
    await seedThemeOverride(page, 'dark')
    await stubMe(page, SIGNED_IN_ME)
    await stubProfiles(page)

    await page.goto(`${baseUrl}/`)
    await page.waitForURL('**/dashboard')
    await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible()
    await expect(page.getByText('VisualSuitePlayer')).toBeVisible()
    await expectExactlyOneMain(page, '/dashboard')

    await waitForFontsReady(page)
    await expect(page).toHaveScreenshot('app-signed-in-dashboard-dark.png', FULL_PAGE)
  })

  // Every other route file under `apps/web/src/routes/` (`index.tsx` and the two above excepted —
  // `index.tsx` only ever redirects, and `/sign-in`/`/dashboard` are already exercised, in both
  // themes, by the four tests above through that same redirect). Each entry stubs whatever
  // `/api/*` its container reads on mount, the same discipline the four tests above already
  // established for `/api/me` and `/api/profiles` — extended per route rather than rebuilt.
  const routeCases: ReadonlyArray<{
    /** Used in the landmark assertion's message and the screenshot's base file name. */
    label: string
    path: string
    screenshotBase: string
    stub: (page: Page) => Promise<void>
  }> = [
    {
      label: '/search',
      path: '/search',
      screenshotBase: 'app-signed-in-search',
      stub: async (page) => {
        await stubMe(page, SIGNED_IN_ME)
      },
    },
    {
      label: '/favourites',
      path: '/favourites',
      screenshotBase: 'app-signed-in-favourites',
      stub: async (page) => {
        await stubMe(page, SIGNED_IN_ME)
        await stubFavourites(page)
      },
    },
    {
      label: '/matches',
      path: '/matches',
      screenshotBase: 'app-signed-in-matches',
      stub: async (page) => {
        await stubMe(page, SIGNED_IN_ME)
        await stubProfiles(page)
        await stubMatchesList(page)
      },
    },
    {
      label: '/matches/$gameId',
      path: `/matches/${SAMPLE_GAME_ID}`,
      screenshotBase: 'app-signed-in-match-detail',
      stub: async (page) => {
        await stubMe(page, SIGNED_IN_ME)
        await stubProfiles(page)
        await stubMatchDetail(page, SAMPLE_GAME_ID)
      },
    },
    {
      label: '/players/$profileId',
      path: `/players/${THIRD_PARTY_PROFILE_ID}`,
      screenshotBase: 'app-signed-in-player-profile',
      stub: async (page) => {
        await stubMe(page, SIGNED_IN_ME)
        await stubFavourites(page)
        await stubPlayerProfile(page, THIRD_PARTY_PROFILE_ID)
      },
    },
    {
      label: '/players/$profileId/matches',
      path: `/players/${THIRD_PARTY_PROFILE_ID}/matches`,
      screenshotBase: 'app-signed-in-player-matches',
      stub: async (page) => {
        await stubMe(page, SIGNED_IN_ME)
        await stubPlayerProfile(page, THIRD_PARTY_PROFILE_ID)
        await stubPlayerMatches(page, THIRD_PARTY_PROFILE_ID)
      },
    },
    {
      label: '/privacy',
      path: '/privacy',
      screenshotBase: 'app-signed-in-privacy',
      stub: async (page) => {
        await stubMe(page, SIGNED_IN_ME)
      },
    },
    {
      label: '/privacy-notice',
      path: '/privacy-notice',
      screenshotBase: 'app-signed-out-privacy-notice',
      stub: async (page) => {
        // FR-041, `privacy-notice.tsx`'s own docstring: reachable signed-in or signed-out alike —
        // signed-out here, since it is the one route this suite otherwise never visits that way
        // (`__root.tsx`'s `beforeLoad` still calls `GET /api/me` for every route, gated or not).
        await stubMe(page, SIGNED_OUT_ME)
      },
    },
    {
      label: '/object',
      path: '/object',
      screenshotBase: 'app-signed-out-object',
      stub: async (page) => {
        // `object.tsx`'s own docstring: outside the session entirely (FR-039) — this route's
        // whole audience has no account, so signed-out is the only realistic state to capture.
        await stubMe(page, SIGNED_OUT_ME)
      },
    },
  ]

  for (const routeCase of routeCases) {
    for (const theme of ['light', 'dark'] as const) {
      test(`${routeCase.label} renders exactly one main landmark (${theme})`, async ({ page }) => {
        await seedThemeOverride(page, theme)
        await routeCase.stub(page)

        await page.goto(`${baseUrl}${routeCase.path}`)
        await expectExactlyOneMain(page, routeCase.label)

        await waitForFontsReady(page)
        const screenshotName =
          theme === 'light'
            ? `${routeCase.screenshotBase}.png`
            : `${routeCase.screenshotBase}-dark.png`
        await expect(page).toHaveScreenshot(screenshotName, FULL_PAGE)
      })
    }
  }
})
