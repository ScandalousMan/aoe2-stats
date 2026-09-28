// T674 (production-readiness item 13, closed by this commit — see
// `packages/design-system/specs/README.md`'s "Verification-coverage gap register" for the row this
// task's own filing deleted): the fixture data, `/api/*` stubs and route list
// `tests/visual/app-routes.spec.ts` (T108/T553) already built for its own landmark-count and
// full-page-screenshot suite, factored out so the four keyboard/focus-visibility/touch-footprint/
// reduced-motion sub-suites below can walk the same ten route scenarios without each carrying its
// own four-hundred-line copy of the same response bodies. `app-routes.spec.ts` itself is left
// untouched — its own inline copies are its own file's business, and this module changes none of
// its behaviour or baselines.
import { type ChildProcess, spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import path from 'node:path'
import type { Page, Route } from '@playwright/test'

const rootDir = path.resolve(__dirname, '..', '..', '..')
export const distDir = path.join(rootDir, 'apps', 'web', 'dist')
export const hasBuild = existsSync(path.join(distDir, 'index.html'))

// `packages/design-system/src/theme/ThemeProvider.tsx`'s `THEME_STORAGE_KEY`, restated rather than
// imported — same reason `app-routes.spec.ts`'s own copy gives: this suite drives the built
// `apps/web/dist` artefact from outside the package graph entirely.
export const THEME_STORAGE_KEY = 'ds-theme-override'
export type ThemeOverride = 'light' | 'dark'

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

const FAVOURITES_RESPONSE = { favourites: [] }
const MATCHES_RESPONSE = { matches: [], next_cursor: null }
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

async function fulfillJson(route: Route, body: unknown): Promise<void> {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
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

export async function seedThemeOverride(page: Page, theme: ThemeOverride): Promise<void> {
  await page.addInitScript(([key, value]) => window.localStorage.setItem(key, value), [
    THEME_STORAGE_KEY,
    theme,
  ] as const)
}

// typography-tokens.md §10: with `font-display: swap` a capture taken before the fonts finish
// loading bakes in the fallback face.
export async function waitForFontsReady(page: Page): Promise<void> {
  await page.evaluate(() => document.fonts.ready)
}

export interface RouteScenario {
  /** Used in every assertion message below. */
  label: string
  path: string
  stub: (page: Page) => Promise<void>
}

// The same ten scenarios `app-routes.spec.ts` covers (its own four dedicated sign-in/dashboard
// tests, plus its `routeCases` array) — every route this application declares
// (`apps/web/src/routes/`), `index.tsx` excepted, since it only ever redirects and paints no
// landmark of its own to walk.
export const ROUTE_SCENARIOS: readonly RouteScenario[] = [
  {
    label: '/sign-in',
    path: '/',
    stub: async (page) => {
      await stubMe(page, SIGNED_OUT_ME)
    },
  },
  {
    label: '/dashboard',
    path: '/',
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubProfiles(page)
    },
  },
  {
    label: '/search',
    path: '/search',
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
    },
  },
  {
    label: '/favourites',
    path: '/favourites',
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubFavourites(page)
    },
  },
  {
    label: '/matches',
    path: '/matches',
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubProfiles(page)
      await stubMatchesList(page)
    },
  },
  {
    label: '/matches/$gameId',
    path: `/matches/${SAMPLE_GAME_ID}`,
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubProfiles(page)
      await stubMatchDetail(page, SAMPLE_GAME_ID)
    },
  },
  {
    label: '/players/$profileId',
    path: `/players/${THIRD_PARTY_PROFILE_ID}`,
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubFavourites(page)
      await stubPlayerProfile(page, THIRD_PARTY_PROFILE_ID)
    },
  },
  {
    label: '/players/$profileId/matches',
    path: `/players/${THIRD_PARTY_PROFILE_ID}/matches`,
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubPlayerProfile(page, THIRD_PARTY_PROFILE_ID)
      await stubPlayerMatches(page, THIRD_PARTY_PROFILE_ID)
    },
  },
  {
    label: '/privacy',
    path: '/privacy',
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
    },
  },
  {
    label: '/privacy-notice',
    path: '/privacy-notice',
    stub: async (page) => {
      await stubMe(page, SIGNED_OUT_ME)
    },
  },
  {
    label: '/object',
    path: '/object',
    stub: async (page) => {
      await stubMe(page, SIGNED_OUT_ME)
    },
  },
]

// One static server per spec file, on its own port, so the four sub-suites below never race
// `app-routes.spec.ts`'s own server (`VISUAL_APP_PORT`, default 4174) or each other when a nightly
// `pnpm test:visual` runs the whole of `tests/visual` in parallel workers (`playwright.config.ts`'s
// `fullyParallel`, one process per spec file). Each caller supplies its own default port below.
export function createAppServerHarness(defaultPort: string) {
  const port = process.env.VISUAL_APP_PORT_OVERRIDE ?? defaultPort
  const baseUrl = `http://127.0.0.1:${port}`
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

  async function start(): Promise<void> {
    if (await isReachable()) return
    server = spawn(
      'pnpm',
      ['exec', 'http-server', distDir, '--port', port, '-P', `${baseUrl}?`, '--silent'],
      { cwd: rootDir, stdio: 'ignore' },
    )
    await waitUntilReachable(20_000)
  }

  function stop(): void {
    server?.kill()
  }

  return { baseUrl, start, stop }
}
