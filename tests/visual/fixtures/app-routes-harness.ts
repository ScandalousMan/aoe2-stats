// T674: the route scenarios below render each route at rest, with empty lists. What a route renders
// once used — populated lists, opened `Dialog`s and `Menu`s, loading states — is T676's
// (`./suite-scenarios.ts`, which builds on the stubs exported here). This file
// holds the fixture data, `/api/*` stubs and route list
// `tests/visual/app-routes.spec.ts` (T108/T553) already built for its own landmark-count and
// full-page-screenshot suite, factored out so the four keyboard/focus-visibility/touch-footprint/
// reduced-motion sub-suites below — and `app-routes.spec.ts` itself, which now imports
// `ROUTE_SCENARIOS` from here rather than keeping its own copy (PR #102 review finding M2) — can
// walk the same route scenarios without each carrying its own four-hundred-line copy of the same
// response bodies. `tests/visual/fixtures/app-routes-harness.test.ts` is what keeps
// `ROUTE_SCENARIOS` itself honest against `apps/web/src/routeTree.gen.ts`.
import { type ChildProcess, spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import path from 'node:path'
import { expect, type Page, type Route } from '@playwright/test'
import { THEME_STORAGE_KEY } from '../../../packages/design-system/src/theme'

const rootDir = path.resolve(__dirname, '..', '..', '..')
export const distDir = path.join(rootDir, 'apps', 'web', 'dist')
export const hasBuild = existsSync(path.join(distDir, 'index.html'))

export type ThemeOverride = 'light' | 'dark'

export const SIGNED_OUT_ME = { authenticated: false }

export const SIGNED_IN_ME = {
  authenticated: true,
  user_id: 'visual-suite-user',
  allowlisted: true,
  archival_objected: false,
  archival_objected_at: null,
  profiles: [{ profile_id: 4242, alias: 'VisualSuitePlayer', country: 'FR', is_primary: true }],
}

export const PROFILES_RESPONSE = {
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
export const THIRD_PARTY_PROFILE_ID = 9001

export const PLAYER_PROFILE_RESPONSE = {
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

export const SAMPLE_GAME_ID = '555000123'

export const MATCH_DETAIL_RESPONSE = {
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

export async function fulfillJson(route: Route, body: unknown): Promise<void> {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
}

export async function stubMe(page: Page, response: unknown): Promise<void> {
  await page.route('**/api/me', (route) => fulfillJson(route, response))
}
export async function stubProfiles(page: Page): Promise<void> {
  await page.route('**/api/profiles', (route) => fulfillJson(route, PROFILES_RESPONSE))
}
export async function stubFavourites(page: Page): Promise<void> {
  await page.route('**/api/favourites', (route) => fulfillJson(route, FAVOURITES_RESPONSE))
}
export async function stubMatchesList(page: Page): Promise<void> {
  await page.route('**/api/matches?*', (route) => fulfillJson(route, MATCHES_RESPONSE))
}
export async function stubMatchDetail(page: Page, gameId: string): Promise<void> {
  await page.route(`**/api/matches/${gameId}`, (route) => fulfillJson(route, MATCH_DETAIL_RESPONSE))
}
export async function stubPlayerProfile(page: Page, profileId: number): Promise<void> {
  await page.route(`**/api/players/${profileId}`, (route) =>
    fulfillJson(route, PLAYER_PROFILE_RESPONSE),
  )
}
export async function stubPlayerMatches(page: Page, profileId: number): Promise<void> {
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

// PR #102 review finding (lows on app-routes-harness.ts): `seedThemeOverride` above only ever
// proves the key was *written*; nothing previously checked that the app actually *painted* it. A
// harness whose `THEME_STORAGE_KEY` had drifted from `ThemeProvider.tsx`'s own constant would seed
// a key the app never reads, silently leaving every "dark" capture on the light fallback instead of
// failing — exactly the false-negative shape a screenshot diff cannot be trusted to notice on its
// own (`app-routes.spec.ts`'s own docstring makes the same point about landmark counting). Callers
// run this after navigation completes (after `waitForURL`/the main landmark becoming visible, not
// immediately after `page.goto`), so it never races the redirect the two sign-in/dashboard routes
// go through. `ThemeProvider.tsx`'s `paint()` is what sets this attribute — read, never re-derived.
export async function assertThemeApplied(page: Page, theme: ThemeOverride): Promise<void> {
  await expect(
    page.locator('html'),
    `expected <html data-theme="${theme}"> after navigation, but the painted theme did not match. ` +
      `ThemeProvider.tsx paints this from THEME_STORAGE_KEY ('${THEME_STORAGE_KEY}') read at ` +
      "packages/design-system/src/theme — if that key has drifted from this harness's own seed, " +
      'every capture under the drifted theme silently runs on the fallback instead.',
  ).toHaveAttribute('data-theme', theme)
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
  /**
   * Where navigating to `path` is expected to actually land, when that differs from `path` itself
   * — only `/sign-in` and `/dashboard` need this: both navigate to `/`, and `routes/index.tsx`'s
   * `beforeLoad` redirects from there depending on session state. Falls back to `path` in
   * `gotoScenario` below when omitted, since every other scenario's own `path` is where it lands.
   */
  landedPath?: string
  stub: (page: Page) => Promise<void>
}

// The same scenarios `app-routes.spec.ts` covers (its own two dedicated sign-in/dashboard tests,
// plus the rest) — every route this application declares (`apps/web/src/routes/`, by way of
// `apps/web/src/routeTree.gen.ts`), `index.tsx` excepted, since it only ever redirects and paints
// no landmark of its own to walk. `app-routes-harness.test.ts` fails if this list and the router's
// own generated route tree ever disagree, in either direction — deliberately not restating a count
// here, since a count is exactly the kind of fact that drifts silently the same way the list itself
// used to.
export const ROUTE_SCENARIOS: readonly RouteScenario[] = [
  {
    label: '/sign-in',
    path: '/',
    landedPath: '/sign-in',
    stub: async (page) => {
      await stubMe(page, SIGNED_OUT_ME)
    },
  },
  {
    label: '/dashboard',
    path: '/',
    landedPath: '/dashboard',
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

// PR #102 review finding (T674 remediation), then found still incomplete on PR #102 itself
// (confirmed by running, see `./goto-scenario.test.ts`): a `page.waitForURL('**' + expected)`
// called right after `page.goto` resolves immediately whenever the current URL already matches the
// pattern — true, trivially, for every scenario whose `landedPath` equals its own `path` (nine of
// the eleven in `ROUTE_SCENARIOS`), since `goto` has just navigated there directly. That left this
// function checking nothing for those nine: an authenticated-only route stubbed signed-out redirects
// to `/sign-in?return=...` through its own `beforeLoad` guard, `<main>` renders there too, and the
// old body never threw — every caller would have silently walked the sign-in page under the
// original route's label. This now: (1) actively waits for the URL's pathname to become the
// expected one — a real wait for the two scenarios that redirect (`/sign-in`, `/dashboard`, both
// navigate to `/` first), a no-op for the other nine, already there; (2) waits for the route's own
// `<main>` to paint, exactly as `app-routes.spec.ts`'s and the four route-level suites' own
// downstream assertions already do, giving a *later* client-side redirect (fired from `beforeLoad`
// after the initial URL happened to match) room to run before anything is asserted; (3) re-checks
// the pathname by exact equality, not a glob, so that late redirect is caught instead of silently
// passing through step 1's already-satisfied check.
export async function gotoScenario(
  page: Page,
  scenario: RouteScenario,
  baseUrl: string,
): Promise<void> {
  const expectedPath = scenario.landedPath ?? scenario.path
  await page.goto(`${baseUrl}${scenario.path}`)
  await page.waitForURL((url) => url.pathname === expectedPath)
  await page.getByRole('main').waitFor({ state: 'visible' })
  const actualUrl = page.url()
  const actualPath = new URL(actualUrl).pathname
  expect(
    actualPath,
    `${scenario.label}: expected navigating to '${scenario.path}' to land on '${expectedPath}', ` +
      `but it landed on '${actualUrl}' instead.`,
  ).toBe(expectedPath)
}

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
