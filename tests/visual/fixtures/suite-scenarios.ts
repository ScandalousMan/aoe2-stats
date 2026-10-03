// T676 (production-readiness item 13): the scenarios T674's four route-level sub-suites run beyond
// each route at rest. `ROUTE_SCENARIOS` (`./app-routes-harness`) renders every route with empty
// lists, no search submitted and nothing opened — the adversarial review of #102 (B3) found that
// left row links, result rows, favourites rows, participant links, dialog contents and menu items
// meeting none of the four suites. This file adds, on top of the same stubs:
//
// 1. POPULATED_SCENARIOS — every list a route renders, populated (matches, favourites, search
//    results, match participants, a second linked profile). The empty `ROUTE_SCENARIOS` are kept as
//    they are: an empty state is a state too, and leaving them untouched keeps the full-page
//    screenshots `app-routes.spec.ts` takes (CI-authoritative baselines) exactly where they were.
// 2. SURFACE_SCENARIOS — one scenario per openable surface, opened by keyboard: the theme `Menu` in
//    the shared header on every route, `ProfileSummary`'s profile-switcher and Manage `Menu`s, the
//    unlink `Dialog` and the account-erasure `Dialog`.
//
// `SUITE_SCENARIOS` is the union all four suites iterate. A scenario with a `surface` is walked by
// that surface's own keyboard contract (`./open-surface`) instead of a Tab walk over the page.
//
// No player here carries an `avatar_hash` (every fixture says `avatar_hash: null` or omits the
// field), `enterScenario` installs `installSteamAvatarStub` as a backstop, and it watches every
// request the page makes (`./external-requests`) so the suites fail, rather than quietly pass, if
// one ever reaches another host — constitution III, `player-avatar.md` §9.
import { expect, type Page } from '@playwright/test'
import {
  assertThemeApplied,
  fulfillJson,
  gotoScenario,
  MATCH_DETAIL_RESPONSE,
  PLAYER_PROFILE_RESPONSE,
  PROFILES_RESPONSE,
  ROUTE_SCENARIOS,
  SAMPLE_GAME_ID,
  seedThemeOverride,
  SIGNED_IN_ME,
  stubMe,
  stubPlayerProfile,
  THIRD_PARTY_PROFILE_ID,
  waitForFontsReady,
  type RouteScenario,
  type ThemeOverride,
} from './app-routes-harness'
import { installSteamAvatarStub } from './avatar-stub'
import { type ExternalRequestWatch, watchExternalRequests } from './external-requests'
import { holdRequests, type LoopKind } from './loading-state'
import { openMenuByKeyboard, tabTo, type SurfaceKind } from './open-surface'

export interface SuiteScenario extends RouteScenario {
  /** Runs after navigation settles: submits the search, opens the surface — by keyboard. */
  prepare?: (page: Page) => Promise<void>
  /** Set when `prepare` leaves a `Menu` or `Dialog` open: the suites then walk that surface. */
  surface?: SurfaceKind
}

// --- Populated fixtures --------------------------------------------------------------------------

const VIEWER_ID = 4242
const OPPONENT_ID = 7001
const ALLY_ID = 7002
const FOE_TWO_ID = 7003

export const SECOND_LINKED_PROFILE_ID = 4343

// The viewer's account with two linked profiles: the switcher `Menu` holds two items, and viewing
// the non-primary one adds "Make primary" to the Manage `Menu`.
export const TWO_PROFILES_RESPONSE = {
  profiles: [
    ...PROFILES_RESPONSE.profiles,
    {
      profile_id: SECOND_LINKED_PROFILE_ID,
      alias: 'VisualSuiteSmurf',
      country: 'FR',
      is_primary: false,
      linked_at: '2026-02-01T00:00:00Z',
      ratings: PROFILES_RESPONSE.profiles[0].ratings,
    },
  ],
}

function matchRow(gameId: number, result: 'win' | 'loss', ratingDiff: number, viewerId: number) {
  return {
    game_id: gameId,
    started_at: '2026-08-29T09:00:00Z',
    completed_at: '2026-08-29T09:45:00Z',
    map_name: 'Arabia',
    leaderboard_id: 3,
    leaderboard_name: '1v1 Random Map',
    duration_seconds: 2700,
    civilisation: 5,
    civilisation_name: 'Franks',
    result,
    rating: 1487,
    rating_diff: ratingDiff,
    team_id: 1,
    color_id: 1,
    opponents: [
      { profile_id: OPPONENT_ID, alias: 'FixtureOpponent', civ_id: 6, civ_name: 'Britons' },
    ],
    participants: [
      {
        profile_id: viewerId,
        alias: 'VisualSuitePlayer',
        country: 'FR',
        team_id: 1,
        civ_id: 5,
        civ_name: 'Franks',
        color_id: 1,
        result,
        rating: 1487,
        rating_diff: ratingDiff,
      },
      {
        profile_id: OPPONENT_ID,
        alias: 'FixtureOpponent',
        country: 'GB',
        team_id: 2,
        civ_id: 6,
        civ_name: 'Britons',
        color_id: 2,
        result: result === 'win' ? 'loss' : 'win',
        rating: 1502,
        rating_diff: -ratingDiff,
      },
    ],
    // A row the capture pipeline has stored, and one with no capture row at all: both badge states
    // a row renders.
    capture_status: gameId % 2 === 0 ? 'stored' : null,
    capture_deadline_at: null,
  }
}

function matchesBody(viewerId: number) {
  return {
    matches: [
      matchRow(555000123, 'win', 14, viewerId),
      matchRow(555000124, 'loss', -11, viewerId),
      matchRow(555000125, 'win', 9, viewerId),
    ],
    next_cursor: null,
  }
}

const FAVOURITES_POPULATED = {
  favourites: [
    {
      profile_id: THIRD_PARTY_PROFILE_ID,
      alias: 'ThirdPartyPlayer',
      country: 'DE',
      ratings: PLAYER_PROFILE_RESPONSE.ratings,
    },
    { profile_id: OPPONENT_ID, alias: 'FixtureOpponent', country: 'GB', ratings: [] },
  ],
}

const SEARCH_POPULATED = {
  results: [
    {
      profile_id: THIRD_PARTY_PROFILE_ID,
      alias: 'ThirdPartyPlayer',
      country: 'DE',
      games_played: 71,
      clan: 'FIX',
      unverified_steam_id: null,
    },
    {
      profile_id: OPPONENT_ID,
      alias: 'FixtureOpponent',
      country: 'GB',
      games_played: null,
      clan: null,
      unverified_steam_id: null,
    },
    {
      profile_id: ALLY_ID,
      alias: 'FixtureAlly',
      country: null,
      games_played: 12,
      clan: null,
      unverified_steam_id: null,
    },
  ],
  degraded: false,
  reason: null,
}

function participant(
  profileId: number,
  alias: string,
  teamId: number,
  colorId: number,
  civName: string,
  availability: 'archived' | 'obtainable' | 'expired' | 'never_recorded',
) {
  return {
    profile_id: profileId,
    alias,
    team_id: teamId,
    civ_id: colorId,
    civ_name: civName,
    color_id: colorId,
    result: teamId === 1 ? 'win' : 'loss',
    rating: 1400 + colorId * 10,
    rating_diff: teamId === 1 ? 8 : -8,
    // One participant per replay availability the panel renders: a download button, a time-boxed
    // "obtainable" row, and the two terminal ones.
    replay: {
      profile_id: profileId,
      availability,
      obtainable_until: availability === 'obtainable' ? '2026-09-20T09:00:00Z' : null,
      download_path:
        availability === 'archived' ? `/api/matches/${SAMPLE_GAME_ID}/replays/${profileId}` : null,
    },
  }
}

const MATCH_DETAIL_POPULATED = {
  ...MATCH_DETAIL_RESPONSE,
  leaderboard_name: 'Team Random Map',
  capture_status: 'stored',
  participants: [
    participant(VIEWER_ID, 'VisualSuitePlayer', 1, 1, 'Franks', 'archived'),
    participant(ALLY_ID, 'FixtureAlly', 1, 3, 'Mongols', 'obtainable'),
    participant(OPPONENT_ID, 'FixtureOpponent', 2, 2, 'Britons', 'expired'),
    participant(FOE_TWO_ID, 'FixtureFoeTwo', 2, 4, 'Goths', 'never_recorded'),
  ],
}

// Every populated body in one place, so `suite-scenarios.test.ts` can assert what the fixtures
// promise — non-empty lists, one participant per replay availability, no avatar hash anywhere —
// without reaching into the scenarios' closures.
export const POPULATED_FIXTURES = {
  profiles: TWO_PROFILES_RESPONSE,
  matches: matchesBody(VIEWER_ID),
  playerMatches: matchesBody(THIRD_PARTY_PROFILE_ID),
  favourites: FAVOURITES_POPULATED,
  search: SEARCH_POPULATED,
  matchDetail: MATCH_DETAIL_POPULATED,
} as const

/** Paths (`$.results[1].avatar_hash`) of every non-null `avatar_hash` in a fixture. A fixture
 * player carrying one makes `PlayerAvatar` request `avatars.steamstatic.com`; the rule is that
 * none does (constitution III), and this is what the rule is checked with. */
export function findAvatarHashes(value: unknown, path = '$'): string[] {
  if (Array.isArray(value)) {
    return value.flatMap((item, index) => findAvatarHashes(item, `${path}[${index}]`))
  }
  if (typeof value !== 'object' || value === null) return []
  return Object.entries(value).flatMap(([key, child]) =>
    key === 'avatar_hash' && child !== null
      ? [`${path}.${key}`]
      : findAvatarHashes(child, `${path}.${key}`),
  )
}

async function stubPopulatedProfiles(page: Page, body: unknown): Promise<void> {
  await page.route('**/api/profiles', (route) => fulfillJson(route, body))
}

async function stubPopulatedFavourites(page: Page): Promise<void> {
  await page.route('**/api/favourites', (route) => fulfillJson(route, FAVOURITES_POPULATED))
}

export const POPULATED_SCENARIOS: readonly SuiteScenario[] = [
  {
    label: '/dashboard (two linked profiles)',
    path: '/',
    landedPath: '/dashboard',
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubPopulatedProfiles(page, TWO_PROFILES_RESPONSE)
    },
  },
  {
    label: '/search (results submitted)',
    path: '/search',
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await page.route('**/api/players/search*', (route) => fulfillJson(route, SEARCH_POPULATED))
    },
    prepare: async (page) => {
      await tabTo(page, page.locator('main input').first())
      await page.keyboard.type('Fixture')
      const answered = page.waitForResponse('**/api/players/search*')
      await page.keyboard.press('Enter')
      await answered
      await page.locator('main a[href^="/players/"]').first().waitFor({ state: 'visible' })
    },
  },
  {
    label: '/favourites (populated)',
    path: '/favourites',
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubPopulatedFavourites(page)
    },
  },
  {
    label: '/matches (populated)',
    path: '/matches',
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubPopulatedProfiles(page, TWO_PROFILES_RESPONSE)
      await page.route('**/api/matches?*', (route) => fulfillJson(route, matchesBody(VIEWER_ID)))
    },
  },
  {
    label: '/matches/$gameId (populated)',
    path: `/matches/${SAMPLE_GAME_ID}`,
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubPopulatedProfiles(page, PROFILES_RESPONSE)
      await page.route(`**/api/matches/${SAMPLE_GAME_ID}`, (route) =>
        fulfillJson(route, MATCH_DETAIL_POPULATED),
      )
    },
  },
  {
    label: '/players/$profileId (favourited)',
    path: `/players/${THIRD_PARTY_PROFILE_ID}`,
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubPopulatedFavourites(page)
      await stubPlayerProfile(page, THIRD_PARTY_PROFILE_ID)
    },
  },
  {
    label: '/players/$profileId/matches (populated)',
    path: `/players/${THIRD_PARTY_PROFILE_ID}/matches`,
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubPlayerProfile(page, THIRD_PARTY_PROFILE_ID)
      await page.route(`**/api/players/${THIRD_PARTY_PROFILE_ID}/matches*`, (route) =>
        fulfillJson(route, matchesBody(THIRD_PARTY_PROFILE_ID)),
      )
    },
  },
]

// --- Openable surfaces ---------------------------------------------------------------------------

function themeMenuTrigger(page: Page) {
  return page.getByRole('button', { name: /^Theme:/ })
}

function switcherTrigger(page: Page) {
  // `ProfileSummary` renders the profile switcher's trigger first in `main`, before any "Manage".
  return page.locator('main button[aria-haspopup="menu"]').first()
}

function manageTrigger(page: Page) {
  return page.getByRole('button', { name: 'Manage' })
}

// The shared header's theme `Menu` exists on every route (`__root.tsx` renders `SiteHeader` around
// the whole outlet), so each route gets one scenario for it, derived from `ROUTE_SCENARIOS` rather
// than listed twice: a route added there is covered here without a second edit.
const THEME_MENU_SCENARIOS: readonly SuiteScenario[] = ROUTE_SCENARIOS.map((scenario) => ({
  ...scenario,
  label: `${scenario.label} — theme menu open`,
  surface: 'menu' as const,
  prepare: (page: Page) => openMenuByKeyboard(page, themeMenuTrigger(page)),
}))

async function stubUnlinkPreview(page: Page): Promise<void> {
  await page.route(`**/api/profiles/${VIEWER_ID}*`, (route) =>
    fulfillJson(route, {
      confirmed: false,
      archived_replays: {
        retained: true,
        count: 2,
        message: 'They stay archived, and stop being linked to this profile.',
      },
    }),
  )
}

const DASHBOARD_PATHS = { path: '/', landedPath: '/dashboard' } as const

export const SURFACE_SCENARIOS: readonly SuiteScenario[] = [
  ...THEME_MENU_SCENARIOS,
  {
    label: '/dashboard — profile switcher menu open',
    ...DASHBOARD_PATHS,
    surface: 'menu',
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubPopulatedProfiles(page, TWO_PROFILES_RESPONSE)
    },
    prepare: (page) => openMenuByKeyboard(page, switcherTrigger(page)),
  },
  {
    label: '/dashboard — manage menu open (primary profile)',
    ...DASHBOARD_PATHS,
    surface: 'menu',
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubPopulatedProfiles(page, TWO_PROFILES_RESPONSE)
    },
    prepare: (page) => openMenuByKeyboard(page, manageTrigger(page)),
  },
  {
    label: '/dashboard — manage menu open (non-primary profile)',
    ...DASHBOARD_PATHS,
    surface: 'menu',
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubPopulatedProfiles(page, TWO_PROFILES_RESPONSE)
    },
    prepare: async (page) => {
      // View the second linked profile — ArrowDown to its item, Enter to select, Escape to close
      // the switcher — so "Make primary" joins "Unlink" in the Manage menu.
      await openMenuByKeyboard(page, switcherTrigger(page))
      await page.keyboard.press('ArrowDown')
      await page.keyboard.press('Enter')
      await page.keyboard.press('Escape')
      await expect(switcherTrigger(page)).toContainText('VisualSuiteSmurf')
      await openMenuByKeyboard(page, manageTrigger(page))
    },
  },
  {
    label: '/dashboard — unlink dialog open',
    ...DASHBOARD_PATHS,
    surface: 'dialog',
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubPopulatedProfiles(page, TWO_PROFILES_RESPONSE)
      await stubUnlinkPreview(page)
    },
    prepare: async (page) => {
      await openMenuByKeyboard(page, manageTrigger(page))
      await page.keyboard.press('Enter') // the menu's one item, "Unlink this profile"
      await page.getByRole('dialog').waitFor({ state: 'visible' })
    },
  },
  {
    label: '/matches — profile switcher menu open',
    path: '/matches',
    surface: 'menu',
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubPopulatedProfiles(page, TWO_PROFILES_RESPONSE)
      await page.route('**/api/matches?*', (route) => fulfillJson(route, matchesBody(VIEWER_ID)))
    },
    prepare: (page) => openMenuByKeyboard(page, switcherTrigger(page)),
  },
  {
    label: '/privacy — account erasure dialog open',
    path: '/privacy',
    surface: 'dialog',
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await page.route('**/api/privacy/erase', (route) =>
        fulfillJson(route, { confirmation_token: 'visual-suite-token' }),
      )
    },
    prepare: async (page) => {
      await tabTo(page, page.getByRole('button', { name: 'Erase my account' }))
      await page.keyboard.press('Enter')
      await page.getByRole('dialog').waitFor({ state: 'visible' })
    },
  },
]

export const SUITE_SCENARIOS: readonly SuiteScenario[] = [
  ...ROUTE_SCENARIOS,
  ...POPULATED_SCENARIOS,
  ...SURFACE_SCENARIOS,
]

// --- Loading states ------------------------------------------------------------------------------

export interface LoadingScenario extends SuiteScenario {
  /** The request held open for as long as the test needs the loading state on screen. */
  hold: { urlGlob: string; body: unknown }
  /** Which looping component that loading state renders. */
  loop: LoopKind
}

export const LOADING_SCENARIOS: readonly LoadingScenario[] = [
  {
    // `ProfileSummary`'s `loading` status renders `Skeleton` placeholders, the `pulse` loop.
    label: '/dashboard — profile summary loading',
    ...DASHBOARD_PATHS,
    loop: 'skeleton',
    hold: { urlGlob: '**/api/profiles', body: PROFILES_RESPONSE },
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
    },
  },
  {
    // `Button`'s `loading` renders `Spinner`, the `spin` loop: the erase button while its
    // confirmation token is minted.
    label: '/privacy — erase button minting',
    path: '/privacy',
    loop: 'spinner',
    hold: { urlGlob: '**/api/privacy/erase', body: { confirmation_token: 'visual-suite-token' } },
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
    },
    prepare: async (page) => {
      await tabTo(page, page.getByRole('button', { name: 'Erase my account' }))
      await page.keyboard.press('Enter')
    },
  },
]

// --- Entering a scenario -------------------------------------------------------------------------

export interface EnterOptions {
  /** Applied before navigation, so the preference is in effect for the very first render. */
  reducedMotion?: boolean
  /** Request holders to install after `scenario.stub`, before navigation (loading scenarios). */
  beforeNavigate?: (page: Page) => Promise<void>
}

/** The setup every suite repeated inline, in one place: avatar stub and external-request watch,
 * reduced-motion preference, theme seed, API stubs, navigation, theme-painted and font checks, then
 * the scenario's own `prepare` (search submitted, surface opened). Returns the external-request
 * watch for the caller to assert at the end of its test. */
export async function enterScenario(
  page: Page,
  scenario: SuiteScenario,
  baseUrl: string,
  theme: ThemeOverride,
  options: EnterOptions = {},
): Promise<ExternalRequestWatch> {
  const external = watchExternalRequests(page, baseUrl)
  await installSteamAvatarStub(page)
  if (options.reducedMotion) await page.emulateMedia({ reducedMotion: 'reduce' })
  await seedThemeOverride(page, theme)
  await scenario.stub(page)
  await options.beforeNavigate?.(page)

  await gotoScenario(page, scenario, baseUrl)
  await page.getByRole('main').waitFor({ state: 'visible' })
  // Proves the theme was actually *painted*, not merely seeded (PR #102 review finding).
  await assertThemeApplied(page, theme)
  await waitForFontsReady(page)

  await scenario.prepare?.(page)
  return external
}

export async function holdLoadingRequest(page: Page, scenario: LoadingScenario) {
  return holdRequests(page, scenario.hold.urlGlob, scenario.hold.body)
}
