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

/** One list or control group a populated scenario promises to put on screen: `selector` is
 * resolved in the page and must match at least `min` elements. `name` is what
 * `ROUTE_REQUIRED_LISTS` (`./suite-scenarios.test.ts`) is checked against, so a list nobody
 * declares fails by name. */
export interface ListExpectation {
  name: string
  selector: string
  min: number
}

/** A scenario that renders a route's success branch. Its label is always `${route} (${variant})`,
 * built by `populated()` below, so `route` is the one thing a guard compares — never a label
 * prefix, which `'/matches/$gameId (populated)'.startsWith('/matches')` showed to be ambiguous. */
export interface PopulatedScenario extends SuiteScenario {
  /** The `ROUTE_SCENARIOS` label this scenario populates, matched exactly. */
  route: string
  variant: string
  /** What this scenario puts on screen, asserted in the browser by `assertPopulatedScenario`. */
  renders: readonly ListExpectation[]
}

function populated(
  route: string,
  variant: string,
  rest: Omit<PopulatedScenario, 'label' | 'route' | 'variant'>,
): PopulatedScenario {
  return { ...rest, route, variant, label: `${route} (${variant})` }
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

// --- The analysis section (`AnalysisContainer`) ---------------------------------------------------
//
// `GET /api/matches/{game_id}` carries an `analysis` summary, and while its `state` is `published`
// the container also reads `GET /api/matches/{game_id}/analysis`. `MATCH_DETAIL_RESPONSE` has no
// `analysis` key at all (it predates the section), so `extractAnalysisSummary` throws on it and the
// container renders `<AnalysisTimeline error>` — which is what the routes-at-rest scenario shows,
// and exactly what a "populated" match page must not. Both bodies below are shaped by
// `apps/web/src/features/analysis/api.ts` (`assertAnalysisSummary`, `assertAnalysisDocument`). A
// field renamed there makes the container render its error state again, which
// `assertPopulatedScenario` (below, run by `suite-scenarios.test.ts`) fails on by name.

type AnalysisSummaryState =
  'absent' | 'queued' | 'running' | 'published' | 'failed' | 'unavailable' | 'refused'

function analysisSummary(state: AnalysisSummaryState, stale = false) {
  return {
    state,
    parser_version: state === 'absent' ? null : '1.0.0',
    stale,
    point_of_view_profile_id: state === 'absent' ? null : VIEWER_ID,
    result_path: `/api/matches/${SAMPLE_GAME_ID}/analysis`,
    reason: state === 'refused' ? 'analysis_cap_reached' : null,
  }
}

function analysisParticipant(profileId: number, teamId: number, civId: number, resigned: boolean) {
  return {
    profile_id: profileId,
    player_number: civId,
    civ_id: civId,
    resolved_team_id: teamId,
    // Every one of the four lists a participant card renders, non-empty: ids no lookup names, so
    // each row is an `UnresolvedIdentifier` (`mappers.ts`'s `UNRESOLVED_NAME`), as in production.
    builds: [
      { building_id: 70, world_time_ms: 15_000 },
      { building_id: 109, world_time_ms: 62_000 },
    ],
    trainings: [
      { unit_id: 83, amount: 1, building_id: 109, world_time_ms: 20_000 },
      { unit_id: 74, amount: 3, building_id: 12, world_time_ms: 340_000 },
    ],
    researches: [
      { technology_id: 22, world_time_ms: 95_000 },
      { technology_id: 213, world_time_ms: 410_000 },
    ],
    age_up_commands: { '101': 540_000, '102': 1_020_000 },
    villagers_ordered: 62,
    actions: 1840,
    actions_per_minute: 61.4,
    resigned_at_ms: resigned ? 2_640_000 : null,
  }
}

const ANALYSIS_DOCUMENT = {
  schema_version: 1,
  game_id: Number(SAMPLE_GAME_ID),
  point_of_view_profile_id: VIEWER_ID,
  engine: { name: 'aoe2rec-py', version: '0.4.2', deps: {} },
  source_recording: { object_key: 'fixture/recording.aoe2record', sha256: 'f'.repeat(64) },
  extracted_at: '2026-08-29T10:00:00Z',
  participants: [
    analysisParticipant(VIEWER_ID, 1, 1, false),
    analysisParticipant(ALLY_ID, 1, 3, false),
    analysisParticipant(OPPONENT_ID, 2, 2, true),
    analysisParticipant(FOE_TWO_ID, 2, 4, false),
  ],
}

/** The match-detail body with its `analysis` summary, optionally with a different capture status
 * (`expired` is one of the three "Lost" statuses that render `UploadControl`). */
function matchDetailWith(analysis: ReturnType<typeof analysisSummary>, captureStatus = 'stored') {
  return { ...MATCH_DETAIL_POPULATED, capture_status: captureStatus, analysis }
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
  matchDetail: matchDetailWith(analysisSummary('published')),
  analysisDocument: ANALYSIS_DOCUMENT,
  analysisSummaries: {
    published: analysisSummary('published'),
    stale: analysisSummary('published', true),
    absent: analysisSummary('absent'),
    refused: analysisSummary('refused'),
  },
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

// What each populated scenario promises to render. Selectors are structural (a table body row, a
// list item, an `<ol>`), never a class, and each `min` is the count the fixture above produces, so
// a list that silently renders fewer rows fails as well as one that renders none.
const RATING_ROWS: ListExpectation = {
  name: 'rating table rows',
  selector: 'main table tbody tr',
  min: 1,
}
const MATCH_ROWS: readonly ListExpectation[] = [
  { name: 'match rows', selector: 'main table tbody tr', min: 3 },
  { name: 'match row links', selector: 'main a[href^="/matches/"]', min: 3 },
]
const MATCH_DETAIL_ROSTER: readonly ListExpectation[] = [
  { name: 'participant rows', selector: 'main table tbody tr', min: 4 },
  { name: 'replay availability rows', selector: 'main ul > li', min: 4 },
]
// Four participants, each with all four of Age ups, Build order, Training order and Research, two
// events apiece.
const ANALYSIS_LISTS: readonly ListExpectation[] = [
  { name: 'analysis participant cards', selector: 'main article', min: 4 },
  { name: 'analysis ordered lists', selector: 'main article ol', min: 16 },
  { name: 'analysis list items', selector: 'main article ol > li', min: 32 },
]

async function stubMatchDetailAnalysis(
  page: Page,
  analysis: ReturnType<typeof analysisSummary>,
  captureStatus = 'stored',
): Promise<void> {
  await stubMe(page, SIGNED_IN_ME)
  await stubPopulatedProfiles(page, PROFILES_RESPONSE)
  await page.route(`**/api/matches/${SAMPLE_GAME_ID}`, (route) =>
    fulfillJson(route, matchDetailWith(analysis, captureStatus)),
  )
  await page.route(`**/api/matches/${SAMPLE_GAME_ID}/analysis`, (route) =>
    fulfillJson(route, ANALYSIS_DOCUMENT),
  )
}

export const POPULATED_SCENARIOS: readonly PopulatedScenario[] = [
  populated('/dashboard', 'two linked profiles', {
    path: '/',
    landedPath: '/dashboard',
    renders: [RATING_ROWS, { name: 'archival explanation list', selector: 'main ul > li', min: 1 }],
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubPopulatedProfiles(page, TWO_PROFILES_RESPONSE)
    },
  }),
  populated('/search', 'results submitted', {
    path: '/search',
    renders: [
      { name: 'search results', selector: 'main ul > li', min: 3 },
      { name: 'search result links', selector: 'main a[href^="/players/"]', min: 3 },
    ],
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
  }),
  populated('/favourites', 'populated', {
    path: '/favourites',
    renders: [
      { name: 'favourite rows', selector: 'main ul > li', min: 2 },
      { name: 'favourite row links', selector: 'main a[href^="/players/"]', min: 2 },
      { name: 'remove buttons', selector: 'main ul > li button', min: 2 },
    ],
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubPopulatedFavourites(page)
    },
  }),
  populated('/matches', 'populated', {
    path: '/matches',
    renders: MATCH_ROWS,
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubPopulatedProfiles(page, TWO_PROFILES_RESPONSE)
      await page.route('**/api/matches?*', (route) => fulfillJson(route, matchesBody(VIEWER_ID)))
    },
  }),
  // The match page's analysis section has seven states; these four are the ones that render a list
  // or a control (`published` the four ordered lists, `published` + `stale` the Recompute button,
  // `absent` the Request analysis button, `refused` the Try requesting analysis button). `queued`
  // and `running` render a Skeleton and no control, `failed` and `unavailable` a Callout with no
  // control: none is a list or a control group, so none is a scenario (see the inventory in
  // `suite-scenarios.test.ts`).
  populated('/matches/$gameId', 'populated', {
    path: `/matches/${SAMPLE_GAME_ID}`,
    renders: [
      ...MATCH_DETAIL_ROSTER,
      ...ANALYSIS_LISTS,
      { name: 'replay download buttons', selector: 'main button:has-text("Download")', min: 2 },
    ],
    stub: (page) => stubMatchDetailAnalysis(page, analysisSummary('published')),
  }),
  populated('/matches/$gameId', 'analysis stale', {
    path: `/matches/${SAMPLE_GAME_ID}`,
    renders: [
      ...MATCH_DETAIL_ROSTER,
      ...ANALYSIS_LISTS,
      { name: 'Recompute button', selector: 'main button:has-text("Recompute")', min: 1 },
    ],
    stub: (page) => stubMatchDetailAnalysis(page, analysisSummary('published', true)),
  }),
  populated('/matches/$gameId', 'analysis absent, capture lost', {
    path: `/matches/${SAMPLE_GAME_ID}`,
    renders: [
      ...MATCH_DETAIL_ROSTER,
      {
        name: 'Request analysis button',
        selector: 'main button:has-text("Request analysis")',
        min: 1,
      },
      { name: 'upload control', selector: 'main input[type="file"]', min: 1 },
    ],
    stub: (page) => stubMatchDetailAnalysis(page, analysisSummary('absent'), 'expired'),
  }),
  populated('/matches/$gameId', 'analysis refused', {
    path: `/matches/${SAMPLE_GAME_ID}`,
    renders: [
      ...MATCH_DETAIL_ROSTER,
      {
        name: 'Try requesting analysis button',
        selector: 'main button:has-text("Try requesting analysis")',
        min: 1,
      },
    ],
    stub: (page) => stubMatchDetailAnalysis(page, analysisSummary('refused')),
  }),
  populated('/players/$profileId', 'favourited', {
    path: `/players/${THIRD_PARTY_PROFILE_ID}`,
    renders: [
      RATING_ROWS,
      {
        name: 'unfavourite toggle',
        selector: 'main button:has-text("Remove from favourites")',
        min: 1,
      },
    ],
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubPopulatedFavourites(page)
      await stubPlayerProfile(page, THIRD_PARTY_PROFILE_ID)
    },
  }),
  populated('/players/$profileId/matches', 'populated', {
    path: `/players/${THIRD_PARTY_PROFILE_ID}/matches`,
    renders: MATCH_ROWS,
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubPlayerProfile(page, THIRD_PARTY_PROFILE_ID)
      await page.route(`**/api/players/${THIRD_PARTY_PROFILE_ID}/matches*`, (route) =>
        fulfillJson(route, matchesBody(THIRD_PARTY_PROFILE_ID)),
      )
    },
  }),
]

// The lists and control groups each route's success branch renders, by `ROUTE_SCENARIOS` label.
// This is the inventory the guards below are checked against: `unpopulatedLists` fails by name for
// any entry no populated scenario of *that route* declares, and `assertPopulatedScenario` asserts
// each declaration in the browser. A route absent here and from `ROUTES_WITHOUT_A_LIST`
// (`suite-scenarios.test.ts`) fails there.
export const ROUTE_REQUIRED_LISTS: Readonly<Record<string, readonly string[]>> = {
  '/dashboard': ['rating table rows', 'archival explanation list'],
  '/search': ['search results', 'search result links'],
  '/favourites': ['favourite rows', 'favourite row links', 'remove buttons'],
  '/matches': ['match rows', 'match row links'],
  '/matches/$gameId': [
    'participant rows',
    'replay availability rows',
    'replay download buttons',
    'analysis participant cards',
    'analysis ordered lists',
    'analysis list items',
    'Recompute button',
    'Request analysis button',
    'upload control',
    'Try requesting analysis button',
  ],
  '/players/$profileId': ['rating table rows', 'unfavourite toggle'],
  '/players/$profileId/matches': ['match rows', 'match row links'],
}

/** Every `route: list` pair no populated scenario declares. `route` is compared exactly — a prefix
 * test let `'/matches/$gameId (populated)'` stand in for `/matches`, and
 * `'/players/$profileId/matches (populated)'` for `/players/$profileId`, so removing either
 * scenario on its own went unnoticed. */
export function unpopulatedLists(
  scenarios: readonly PopulatedScenario[],
  required: Readonly<Record<string, readonly string[]>> = ROUTE_REQUIRED_LISTS,
): string[] {
  return Object.entries(required).flatMap(([route, lists]) =>
    lists
      .filter(
        (list) =>
          !scenarios.some(
            (scenario) =>
              scenario.route === route && scenario.renders.some((entry) => entry.name === list),
          ),
      )
      .map((list) => `${route}: ${list}`),
  )
}

/** Asserts, in the browser, that a populated scenario is showing its success branch: every
 * declared list has its items, and nothing on the page is an error callout (`role="alert"`) or a
 * loading region (`aria-busy`). The last two are what `/matches/$gameId (populated)` used to fail
 * silently — the roster was full while the analysis section sat in its error state. */
export async function assertPopulatedScenario(
  page: Page,
  scenario: PopulatedScenario,
  context: string,
): Promise<void> {
  for (const list of scenario.renders) {
    await expect
      .poll(() => page.locator(list.selector).count(), {
        message:
          `${context}: ${list.name} (${list.selector}) rendered fewer than ${list.min} item(s) — ` +
          `the route is showing an empty, loading or error branch instead of its populated one`,
      })
      .toBeGreaterThanOrEqual(list.min)
  }
  await expect(
    page.locator('[role="alert"]'),
    `${context}: an error callout (role="alert") is on screen — the scenario's stubs do not reach ` +
      `the route's success branch`,
  ).toHaveCount(0)
  await expect(
    page.locator('[aria-busy="true"]'),
    `${context}: a loading region (aria-busy) is still on screen — the scenario's stubs do not ` +
      `reach the route's success branch`,
  ).toHaveCount(0)
}

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
