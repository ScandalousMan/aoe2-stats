// T676 (production-readiness item 13): the scenarios T674's four route-level sub-suites run beyond
// each route at rest. `ROUTE_SCENARIOS` (`./app-routes-harness`) renders every route with empty
// lists, no search submitted and nothing opened — the adversarial review of #102 (B3) found that
// left row links, result rows, favourites rows, participant links, dialog contents and menu items
// meeting none of the four suites. This file adds, on top of the same stubs:
//
// 1. POPULATED_SCENARIOS — the lists in `ROUTE_REQUIRED_LISTS` below, populated (matches,
//    favourites, search results, match participants, a second linked profile), and (T682) the two
//    success-branch controls that are not lists: the `objected` `ArchivalControl` and
//    `DataExportPanel`'s `ready` download link. The empty `ROUTE_SCENARIOS` are kept as
//    they are: an empty state is a state too, and leaving them untouched keeps the full-page
//    screenshots `app-routes.spec.ts` takes (CI-authoritative baselines) exactly where they were.
// 2. SURFACE_SCENARIOS — one scenario per `Dialog` and `Menu`, opened by keyboard: the theme `Menu` in
//    the shared header on every route, `ProfileSummary`'s profile-switcher and Manage `Menu`s, the
//    unlink `Dialog` and the account-erasure `Dialog`.
//
// 3. BRANCH_SCENARIOS (T744) — a route's error, transient and unrendered-empty branches, each
//    reached through the route's own stubs: `DataExportPanel`'s `failed` state, `ArchivalControl`
//    with its write in flight and after a resume, the match page's analysis section in `queued`,
//    `running`, `failed` and `unavailable`, the no-linked-account state, `/search`'s two
//    empty-results branches, and the two held loading states. A branch is not a list or a control
//    group, so it has its own inventory (`ROUTE_REQUIRED_BRANCHES`) and its own in-browser judge
//    (`assertBranchScenario`): what the branch puts on screen is declared per scenario, and an error
//    callout or a loading region is expected there, not a failure.
//
// `SUITE_SCENARIOS` is the union all four suites iterate. A scenario with a `surface` is walked by
// that surface's own keyboard contract (`./open-surface`) instead of a Tab walk over the page.
//
// No player here carries an `avatar_hash` (every fixture says `avatar_hash: null` or omits the
// field), `enterScenario` installs `installSteamAvatarStub` as a backstop, and it watches every
// request the page makes (`./external-requests`) so the suites fail, rather than quietly pass, if
// one ever reaches another host — constitution III, `player-avatar.md` §9.
import { readFileSync } from 'node:fs'
import path from 'node:path'
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
import { holdRequests, LOOP_SELECTOR, type LoopKind } from './loading-state'
import { openMenuByKeyboard, tabTo, type SurfaceKind } from './open-surface'
import { openTooltipByKeyboard } from './tooltip-open'

/** A request held open for as long as the page is open, so the state it feeds stays on screen for the
 * whole of a suite's walk or sweep (`holdRequests`, `./loading-state`). Answered with `body` when
 * the page closes, or earlier through the `release` `enterScenario` returns. */
export interface HeldRequest {
  urlGlob: string
  body: unknown
}

export interface SuiteScenario extends RouteScenario {
  /** Runs after navigation settles: submits the search, opens the surface — by keyboard. */
  prepare?: (page: Page) => Promise<void>
  /** Installed by `enterScenario` right after `stub`, before navigation. A request this matches
   * stays pending, so the loading or in-flight state it feeds is what every suite measures. */
  hold?: HeldRequest
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
  /** Set when the list swaps layout at a breakpoint (a `<table>` above it, stacked cards below):
   * `selector` then applies at or above that breakpoint and `selector` here below it. The touch suite
   * measures at 375px, the other three at Playwright's default 1280px, so one selector cannot serve
   * both. */
  stacked?: { below: Breakpoint; selector: string }
}

type Breakpoint = 'md' | 'lg' | 'xl'

// Read from the token file `useBreakpoint` is generated from, never restated.
const BREAKPOINT_PX = JSON.parse(
  readFileSync(
    path.resolve(__dirname, '..', '..', '..', 'packages/design-system/tokens/breakpoint.json'),
    'utf8',
  ),
) as Record<Breakpoint, number>

async function selectorFor(page: Page, list: ListExpectation): Promise<string> {
  if (!list.stacked) return list.selector
  const px = BREAKPOINT_PX[list.stacked.below]
  const atOrAbove = await page.evaluate(
    (width) => window.matchMedia(`(min-width: ${width}px)`).matches,
    px,
  )
  return atOrAbove ? list.selector : list.stacked.selector
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
  /** Set when the lists only exist once `prepare` has run (a search has to be submitted first), so
   * `enterScenario` judges them after `prepare` instead of before it. */
  listsNeedPrepare?: boolean
}

function isPopulatedScenario(scenario: SuiteScenario): scenario is PopulatedScenario {
  return 'renders' in scenario
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
  capture_object_held: true,
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

function analysisSummary(
  state: AnalysisSummaryState,
  stale = false,
  errorClass: string | null = null,
) {
  return {
    state,
    parser_version: state === 'absent' ? null : '1.0.0',
    stale,
    point_of_view_profile_id: state === 'absent' ? null : VIEWER_ID,
    result_path: `/api/matches/${SAMPLE_GAME_ID}/analysis`,
    reason: state === 'refused' ? 'analysis_cap_reached' : null,
    // Required by `assertAnalysisSummary`; only the `failed` scenario (T744) names a class.
    error_class: errorClass,
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
  // T727: a `stored` row holds its object; the lost statuses this takes (`expired`) hold none.
  return {
    ...MATCH_DETAIL_POPULATED,
    capture_status: captureStatus,
    capture_object_held: captureStatus === 'stored',
    analysis,
  }
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
  name: 'rating rows',
  // A `<table>` row from `lg` up, a `RatingCard` article below it (`ProfileSummary` renders one
  // layout, never both).
  selector: 'main table tbody tr',
  min: 1,
  stacked: { below: 'lg', selector: 'main article[aria-labelledby^="entry-"]' },
}
const MATCH_ROWS: readonly ListExpectation[] = [
  // A `<table>` row from `xl` up, a labelled `<ul>` of cards below it (one layout, never both).
  {
    name: 'match rows',
    selector: 'main table tbody tr',
    min: 3,
    stacked: { below: 'xl', selector: 'main ul[aria-label] > li' },
  },
  { name: 'match row links', selector: 'main a[href^="/matches/"]', min: 3 },
]
const MATCH_DETAIL_ROSTER: readonly ListExpectation[] = [
  // A `<table>` row from `xl` up, a card in the team's `<ul>` below it, the one list item carrying
  // the player's colour swatch ("Colour: Blue"); the replay availability list is the other `<ul>`.
  {
    name: 'participant rows',
    selector: 'main table tbody tr',
    min: 4,
    stacked: { below: 'xl', selector: 'main ul > li:has-text("Colour:")' },
  },
  {
    name: 'replay availability rows',
    // Scoped by the list's own section (`ReplayAvailabilityList`'s `<h3>`), not by what a
    // participant card says of itself.
    selector: 'main section:has(> h3:text-is("Recorded games")) > ul > li',
    min: 4,
  },
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

// --- The two success-branch controls that are neither list nor dialog (T682) --------------------
//
// `ArchivalControl`'s `objected` state and `DataExportPanel`'s `ready` state. Every at-rest fixture
// sets `archival_objected: false`, so the first never rendered in a route suite; the second is only
// reached by requesting an export, so it needs a `prepare` that does it by keyboard. Neither is a
// list, but each is a control a user reaches and the four suites measure: they are declared in
// `ROUTE_REQUIRED_LISTS` like one, so the same guard fails on their removal and the same in-browser
// assertion fails when the control is absent.

/** `GET /api/me` for a signed-in user who has objected to archival: the shape `AuthenticatedSession`
 * carries, with a timestamp so the callout reads "You objected on ...". */
export const OBJECTED_ME = {
  ...SIGNED_IN_ME,
  archival_objected: true,
  archival_objected_at: '2026-09-15T12:00:00Z',
}

const EXPORT_JOB_ID = 'visual-suite-export'
// Same-origin and relative: the suites fail any request to another host, and nothing here ever
// follows the link (its presence is asserted, never a click).
export const EXPORT_DOWNLOAD_PATH = `/api/privacy/export/${EXPORT_JOB_ID}/download`

/** The export API in the state a finished job leaves it: `POST` answers with the job id, and the
 * first `GET` of that job already reads `completed`, so the panel goes `requesting` -> `preparing`
 * -> `ready` on its own flow with no timer to wait out. Shapes are `features/privacy/api.ts`'s. */
async function stubExportCompleted(page: Page): Promise<void> {
  await page.route('**/api/privacy/export', (route) =>
    fulfillJson(route, { id: EXPORT_JOB_ID, status: 'queued' }),
  )
  await page.route(`**/api/privacy/export/${EXPORT_JOB_ID}`, (route) =>
    fulfillJson(route, {
      id: EXPORT_JOB_ID,
      status: 'completed',
      download_url: EXPORT_DOWNLOAD_PATH,
    }),
  )
}

const OBJECTED_CONTROLS: readonly ListExpectation[] = [
  { name: 'Resume archival button', selector: 'main button:has-text("Resume archival")', min: 1 },
  // The callout's heading carries the timestamp, so this fails if `archival_objected_at` is lost on
  // the way to the component and the heading falls back to a bare "Archival is off.".
  { name: 'objected callout', selector: 'main :text("Archival is off. You objected on")', min: 1 },
]

export const POPULATED_SCENARIOS: readonly PopulatedScenario[] = [
  populated('/dashboard', 'two linked profiles', {
    path: '/',
    landedPath: '/dashboard',
    renders: [RATING_ROWS],
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubPopulatedProfiles(page, TWO_PROFILES_RESPONSE)
    },
  }),
  populated('/search', 'results submitted', {
    path: '/search',
    listsNeedPrepare: true,
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
  // T682: `ArchivalControl`'s `objected` state, on the two routes that render it.
  populated('/dashboard', 'archival objected', {
    path: '/',
    landedPath: '/dashboard',
    renders: OBJECTED_CONTROLS,
    stub: async (page) => {
      await stubMe(page, OBJECTED_ME)
      await stubPopulatedProfiles(page, PROFILES_RESPONSE)
    },
  }),
  populated('/privacy', 'archival objected', {
    path: '/privacy',
    renders: OBJECTED_CONTROLS,
    stub: async (page) => {
      await stubMe(page, OBJECTED_ME)
    },
  }),
  // T682: `DataExportPanel`'s `ready` state, reached the way a user reaches it: Tab to "Export my
  // data", Enter, and the panel's own request/poll flow against the stubbed export API.
  populated('/privacy', 'export ready', {
    path: '/privacy',
    listsNeedPrepare: true,
    renders: [
      {
        name: 'export download link',
        selector: 'main a[download]:has-text("Download the archive")',
        min: 1,
      },
    ],
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubExportCompleted(page)
    },
    prepare: async (page) => {
      await tabTo(page, page.getByRole('button', { name: 'Export my data' }))
      await page.keyboard.press('Enter')
      // Wait for the flow to finish, but never fail on the wait itself: `listsNeedPrepare` makes
      // `enterScenario` assert the link right after this, by name ("export download link rendered
      // fewer than 1 item(s)"), which is the failure message worth having.
      await page
        .locator('main a[download]:has-text("Download the archive")')
        .waitFor({ state: 'visible', timeout: 5_000 })
        .catch(() => undefined)
    },
  }),
]

// The per-route list inventory, by `ROUTE_SCENARIOS` label: the one the guards below check, and
// nothing more. Error, empty and transient branches are not in it. Two success-branch controls that
// are not lists are (T682): the `objected` `ArchivalControl`'s "Resume archival" button and callout
// on `/dashboard` and `/privacy`, and `DataExportPanel`'s `ready` download link on `/privacy`.
// `unpopulatedLists` fails by name for
// any entry no populated scenario of *that route* declares, and `assertPopulatedScenario` asserts
// each declaration in the browser. A route absent here and from `ROUTES_WITHOUT_A_LIST`
// (`suite-scenarios.test.ts`) fails there.
export const ROUTE_REQUIRED_LISTS: Readonly<Record<string, readonly string[]>> = {
  '/dashboard': ['rating rows', 'Resume archival button', 'objected callout'],
  '/privacy': ['Resume archival button', 'objected callout', 'export download link'],
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
  '/players/$profileId': ['rating rows', 'unfavourite toggle'],
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
    const selector = await selectorFor(page, list)
    await expect
      .poll(() => page.locator(selector).count(), {
        message:
          `${context}: ${list.name} (${selector}) rendered fewer than ${list.min} item(s) — ` +
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

// `SUITE_SCENARIOS` is assembled below, after `BRANCH_SCENARIOS` (T744), which it includes.

// --- Tooltips (T681) -----------------------------------------------------------------------------

/** A route scenario that leaves a `Tooltip` open, opened by Tab to its trigger. Kept out of
 * `SUITE_SCENARIOS` on purpose: a tooltip is not a `Menu` or a `Dialog` (no `surface`, no items to
 * walk), and only the reduced-motion and keyboard suites have a contract for it. */
export interface TooltipScenario extends SuiteScenario {
  /** The `ROUTE_SCENARIOS` label this scenario opens a tooltip on, matched exactly. */
  route: string
}

// The only `Tooltip` an application route renders is `CountryFlag`'s, and the only component that
// renders a `CountryFlag` is `ProfileSummary` — so these are the routes whose container renders a
// `ProfileSummary` for a profile with a country. `suite-scenarios.test.ts` guards this list at three
// levels, none of which reaches further than it says:
// - source: it reads the source for `<Tooltip`, `<CountryFlag` and `<ProfileSummary`, so a usage in a
//   file that no table entry names fails;
// - routes: it reads `apps/web/src/routes/*.tsx` for the routes that import a container that
//   renders a `ProfileSummary`, so a new route mounting one fails until it is listed here (a route
//   that reaches a container through another component, by a default import, by a lazy `import()`
//   or from a nested route directory is not seen: only braced named imports in the flat directory);
// - runtime: `openTooltipByKeyboard` fails when `main` holds a second tooltip trigger, so a second
//   `Tooltip` rendered on one of these routes fails — but only as rendered when the first trigger
//   attaches. A tooltip that renders only in a populated list (one added to `MatchRow`, whose at-rest
//   `/matches` list is empty) is a new usage the source level fails on, yet a table entry naming
//   `/matches` satisfies that level, and the count never sees it: it stays unjudged until a
//   populated scenario opens it.
// The at-rest `ROUTE_SCENARIOS` stubs already carry a country (`FR`, `DE`), so the flag and its
// tooltip render without a populated list.
export const TOOLTIP_ROUTES: readonly string[] = [
  '/dashboard',
  '/matches',
  '/players/$profileId',
  '/players/$profileId/matches',
]

export const TOOLTIP_SCENARIOS: readonly TooltipScenario[] = TOOLTIP_ROUTES.map((route) => {
  const base = ROUTE_SCENARIOS.find((scenario) => scenario.label === route)
  if (!base) throw new Error(`TOOLTIP_ROUTES names '${route}', which ROUTE_SCENARIOS does not have`)
  return {
    ...base,
    route,
    label: `${route} — country tooltip open`,
    prepare: (page) => openTooltipByKeyboard(page, route),
  }
})

// --- Error, transient and unrendered-empty branches (T744) --------------------------------------
//
// T676 and T682 render every route's success branch. What a route shows when a request fails, is
// still in flight, or has nothing to list met none of the four suites (the review of #163 found
// it). Each scenario here reaches one such branch through the route's own stubs and the route's own
// controls, by keyboard where the branch needs an action, and declares what that branch puts on
// screen in `shows`: `enterScenario` asserts it in a browser, after `prepare`, so a stub that falls
// through to the success response fails by naming the mark that is missing. A branch legitimately
// carries an error callout (`role="alert"`) or a loading region (`aria-busy`), which is why this is
// not `assertPopulatedScenario`.

/** A scenario that renders one non-success branch of a route. `label` is always
 * `${route} (${branch})`, built by `branchScenario()` below, so `route` is the one thing a guard
 * compares, as for `PopulatedScenario`. */
export interface BranchScenario extends SuiteScenario {
  /** The `ROUTE_SCENARIOS` label this scenario renders a branch of, matched exactly. */
  route: string
  /** The branch's name in `ROUTE_REQUIRED_BRANCHES`. */
  branch: string
  /** What the branch puts on screen, asserted in the browser by `assertBranchScenario` once
   * `prepare` has run. */
  shows: readonly ListExpectation[]
}

/** A branch that holds a request open, and the looping component that held state renders (the
 * reduced-motion suite's positive control for the loops, `route-reduced-motion.spec.ts`). */
export interface LoadingScenario extends BranchScenario {
  hold: HeldRequest
  loop: LoopKind
}

function isBranchScenario(scenario: SuiteScenario): scenario is BranchScenario {
  return 'shows' in scenario
}

function branchScenario<T extends Omit<BranchScenario, 'label' | 'route' | 'branch'>>(
  route: string,
  branch: string,
  rest: T,
): T & Pick<BranchScenario, 'label' | 'route' | 'branch'> {
  return { ...rest, route, branch, label: `${route} (${branch})` }
}

/** `GET /api/me` for a signed-in user whose account has no linked Steam profile: the session
 * carries an empty `profiles` list, as `GET /api/profiles` below does. */
export const NO_LINKED_ME = { ...SIGNED_IN_ME, profiles: [] }
const NO_PROFILES_RESPONSE = { profiles: [] }

const SPINNER_IN_MAIN: ListExpectation = {
  name: 'spinner',
  selector: `main ${LOOP_SELECTOR.spinner}`,
  min: 1,
}

/** The marks of the no-linked-account branch, which the three routes share: the empty state or
 * callout names the condition, and offers the one way out. */
const NO_LINKED_ACCOUNT: readonly ListExpectation[] = [
  {
    name: 'no-linked-account notice',
    selector: 'main :text("No Steam account is linked yet")',
    min: 1,
  },
  { name: 'link button', selector: 'main button:has-text("Link a Steam account")', min: 1 },
]

/** `ArchivalControl`'s write held in flight: the switch's one visible button is `loading`
 * (`aria-busy`, label "Saving your choice…", a `Spinner`), reached by Tab to "Object to archival"
 * and Enter. */
const ARCHIVAL_IN_FLIGHT: Pick<BranchScenario, 'hold' | 'prepare' | 'shows'> = {
  hold: {
    urlGlob: '**/api/privacy/archival-objection',
    body: { archival_objected: true, archival_objected_at: '2026-10-13T08:00:00Z' },
  },
  prepare: async (page) => {
    await tabTo(page, page.getByRole('button', { name: 'Object to archival' }))
    await page.keyboard.press('Enter')
    // Waits for the flow but never fails on the wait itself: `enterScenario` judges `shows` right
    // after this, and "busy archival button rendered fewer than 1 item(s)" is the failure worth having.
    await page
      .locator('main button[aria-busy="true"]')
      .waitFor({ state: 'visible', timeout: 5_000 })
      .catch(() => undefined)
  },
  shows: [
    {
      name: 'busy archival button',
      selector: 'main button[aria-busy="true"]:has-text("Saving your choice")',
      min: 1,
    },
    SPINNER_IN_MAIN,
  ],
}

/** An objected account that resumes: `/api/me` reads `objected` until the write lands, then
 * `archival_objected: false`, so the control goes `objected` -> `archiving` with `justResumed`. */
async function stubResumable(page: Page): Promise<void> {
  let resumed = false
  await page.route('**/api/me', (route) =>
    fulfillJson(route, resumed ? { ...OBJECTED_ME, archival_objected: false } : OBJECTED_ME),
  )
  await page.route('**/api/privacy/archival-objection', (route) => {
    resumed = true
    return fulfillJson(route, { archival_objected: false, archival_objected_at: null })
  })
}

const ARCHIVAL_JUST_RESUMED: Pick<BranchScenario, 'prepare' | 'shows'> = {
  prepare: async (page) => {
    await tabTo(page, page.getByRole('button', { name: 'Resume archival' }))
    await page.keyboard.press('Enter')
    // Same as above: judged by name in `shows`, not by the wait.
    await page
      .locator('main :text("Archival resumed.")')
      .waitFor({ state: 'visible', timeout: 5_000 })
      .catch(() => undefined)
  },
  shows: [
    { name: 'resumed acknowledgement', selector: 'main :text("Archival resumed.")', min: 1 },
    { name: 'object button', selector: 'main button:has-text("Object to archival")', min: 1 },
  ],
}

/** The match page with its analysis section in `state`. `POST /api/analyze` is stubbed because a
 * `queued` analysis makes the container ask for it on mount (`takeOver`); an unstubbed request
 * would be refused and the page would render the refusal callout, a different branch. */
async function stubAnalysisIn(
  page: Page,
  state: AnalysisSummaryState,
  errorClass: string | null = null,
): Promise<void> {
  await stubMatchDetailAnalysis(page, analysisSummary(state, false, errorClass))
  await page.route('**/api/analyze', (route) => fulfillJson(route, analysisSummary(state)))
}

function matchPage(
  branch: string,
  state: AnalysisSummaryState,
  shows: readonly ListExpectation[],
  errorClass: string | null = null,
) {
  return branchScenario('/matches/$gameId', branch, {
    path: `/matches/${SAMPLE_GAME_ID}`,
    shows,
    stub: (page: Page) => stubAnalysisIn(page, state, errorClass),
  })
}

/** `/search` with a query submitted against a stubbed answer that has no results. */
function emptySearch(branch: string, degraded: boolean, shows: readonly ListExpectation[]) {
  return branchScenario('/search', branch, {
    path: '/search',
    shows,
    stub: async (page: Page) => {
      await stubMe(page, SIGNED_IN_ME)
      await page.route('**/api/players/search*', (route) =>
        fulfillJson(route, {
          results: [],
          degraded,
          reason: degraded ? 'provider_unavailable' : null,
        }),
      )
    },
    prepare: async (page: Page) => {
      await tabTo(page, page.locator('main input').first())
      await page.keyboard.type('Fixture')
      const answered = page.waitForResponse('**/api/players/search*')
      await page.keyboard.press('Enter')
      await answered
    },
  })
}

const ERROR_AND_EMPTY_BRANCHES: readonly BranchScenario[] = [
  // `DataExportPanel`'s `failed` state: the export request is refused, and the panel offers "Try
  // again" (`size="lg"` since T561, for its 375px footprint).
  branchScenario('/privacy', 'export failed', {
    path: '/privacy',
    shows: [
      {
        name: 'export failure callout',
        selector: 'main :text("We could not build your export")',
        min: 1,
      },
      { name: 'Try again button', selector: 'main button:has-text("Try again")', min: 1 },
    ],
    stub: async (page: Page) => {
      await stubMe(page, SIGNED_IN_ME)
      await page.route('**/api/privacy/export', (route) =>
        route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ error: { code: 'export_failed', message: 'Export failed.' } }),
        }),
      )
    },
    prepare: async (page: Page) => {
      await tabTo(page, page.getByRole('button', { name: 'Export my data' }))
      await page.keyboard.press('Enter')
      await page
        .locator('main button:has-text("Try again")')
        .waitFor({ state: 'visible', timeout: 5_000 })
        .catch(() => undefined)
    },
  }),
  // `ArchivalControl` while its write is in flight, on the two routes that render it.
  branchScenario('/dashboard', 'archival write in flight', {
    ...DASHBOARD_PATHS,
    ...ARCHIVAL_IN_FLIGHT,
    stub: async (page: Page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubPopulatedProfiles(page, PROFILES_RESPONSE)
    },
  }),
  branchScenario('/privacy', 'archival write in flight', {
    path: '/privacy',
    ...ARCHIVAL_IN_FLIGHT,
    stub: async (page: Page) => {
      await stubMe(page, SIGNED_IN_ME)
    },
  }),
  // `ArchivalControl` after a resume (`justResumed`).
  branchScenario('/dashboard', 'archival just resumed', {
    ...DASHBOARD_PATHS,
    ...ARCHIVAL_JUST_RESUMED,
    stub: async (page: Page) => {
      await stubResumable(page)
      await stubPopulatedProfiles(page, PROFILES_RESPONSE)
    },
  }),
  branchScenario('/privacy', 'archival just resumed', {
    path: '/privacy',
    ...ARCHIVAL_JUST_RESUMED,
    stub: stubResumable,
  }),
  // The match page's analysis section, in the four states that render neither a list nor a control.
  matchPage('analysis queued', 'queued', [
    {
      name: 'analysis progress (queued)',
      selector: 'main [aria-busy="true"]:has-text("Waiting to start")',
      min: 1,
    },
    { name: 'analysis skeletons', selector: `main ${LOOP_SELECTOR.skeleton}`, min: 2 },
  ]),
  matchPage('analysis running', 'running', [
    {
      name: 'analysis progress (running)',
      selector: 'main [aria-busy="true"]:has-text("Analysing this match")',
      min: 1,
    },
    { name: 'analysis skeletons', selector: `main ${LOOP_SELECTOR.skeleton}`, min: 2 },
  ]),
  matchPage(
    'analysis failed',
    'failed',
    [
      {
        name: 'analysis failure callout',
        selector: 'main [role="alert"]:has-text("This match could not be analysed")',
        min: 1,
      },
      { name: 'analysis error class', selector: 'main :text("Error: ParseError")', min: 1 },
    ],
    'ParseError',
  ),
  matchPage('analysis unavailable', 'unavailable', [
    {
      name: 'analysis unavailable callout',
      selector: 'main [role="alert"]:has-text("Analysis is not available for this match")',
      min: 1,
    },
  ]),
  // The account has no linked profile.
  branchScenario('/dashboard', 'no linked account', {
    ...DASHBOARD_PATHS,
    shows: NO_LINKED_ACCOUNT,
    stub: async (page: Page) => {
      await stubMe(page, NO_LINKED_ME)
      await stubPopulatedProfiles(page, NO_PROFILES_RESPONSE)
    },
  }),
  branchScenario('/matches', 'no linked account', {
    path: '/matches',
    shows: NO_LINKED_ACCOUNT,
    stub: async (page: Page) => {
      await stubMe(page, NO_LINKED_ME)
      await stubPopulatedProfiles(page, NO_PROFILES_RESPONSE)
      await page.route('**/api/matches?*', (route) =>
        fulfillJson(route, { matches: [], next_cursor: null }),
      )
    },
  }),
  branchScenario('/matches/$gameId', 'no linked account', {
    path: `/matches/${SAMPLE_GAME_ID}`,
    shows: NO_LINKED_ACCOUNT,
    stub: async (page: Page) => {
      await stubMatchDetailAnalysis(page, analysisSummary('published'))
      // Registered after the shared stub, so these two win (Playwright matches the last).
      await stubMe(page, NO_LINKED_ME)
      await stubPopulatedProfiles(page, NO_PROFILES_RESPONSE)
    },
  }),
  // `/search`'s two empty-results branches: nothing found, and nothing found while the source is
  // degraded.
  emptySearch('no results', false, [
    { name: 'no-results callout', selector: 'main :text("No player matches")', min: 1 },
    { name: 'spelling hint', selector: 'main :text("Check the spelling")', min: 1 },
  ]),
  emptySearch('no results, degraded', true, [
    {
      name: 'degraded callout',
      selector: 'main :text("Player search is temporarily degraded.")',
      min: 1,
    },
    {
      name: 'no local match line',
      selector: 'main :text("No locally known player matches")',
      min: 1,
    },
  ]),
]

// The per-route branch inventory, by `ROUTE_SCENARIOS` label: the one `unmetBranches` checks, and
// nothing more. A branch no entry here names is a gap this inventory cannot see on its own: it
// lists the branches T744 named, not every branch a route can render (`ArchivalControl`'s
// `writeFailed` and `unavailable` callouts, the match page's `refused` retry, the analysis
// takeover refusal and the `error` states are not in it).
export const ROUTE_REQUIRED_BRANCHES: Readonly<Record<string, readonly string[]>> = {
  '/dashboard': [
    'archival write in flight',
    'archival just resumed',
    'no linked account',
    'profile summary loading',
  ],
  '/privacy': [
    'export failed',
    'archival write in flight',
    'archival just resumed',
    'erase button minting',
  ],
  '/search': ['no results', 'no results, degraded'],
  '/matches': ['no linked account'],
  '/matches/$gameId': [
    'no linked account',
    'analysis queued',
    'analysis running',
    'analysis failed',
    'analysis unavailable',
  ],
}

/** Every `route: branch` pair no branch scenario of that route declares. `route` is compared
 * exactly, as in `unpopulatedLists`. */
export function unmetBranches(
  scenarios: readonly BranchScenario[],
  required: Readonly<Record<string, readonly string[]>> = ROUTE_REQUIRED_BRANCHES,
): string[] {
  return Object.entries(required).flatMap(([route, branches]) =>
    branches
      .filter(
        (branch) =>
          !scenarios.some((scenario) => scenario.route === route && scenario.branch === branch),
      )
      .map((branch) => `${route}: ${branch}`),
  )
}

/** Asserts, in the browser, that a branch scenario is showing the branch it names: every declared
 * mark has its items. Unlike `assertPopulatedScenario` it never expects the page free of error
 * callouts or loading regions. */
export async function assertBranchScenario(
  page: Page,
  scenario: BranchScenario,
  context: string,
): Promise<void> {
  for (const mark of scenario.shows) {
    const selector = await selectorFor(page, mark)
    await expect
      .poll(() => page.locator(selector).count(), {
        message:
          `${context}: ${mark.name} (${selector}) rendered fewer than ${mark.min} item(s) — the ` +
          `route is not showing its '${scenario.branch}' branch`,
      })
      .toBeGreaterThanOrEqual(mark.min)
  }
}

// --- The two held loading states -----------------------------------------------------------------
//
// Until T744 these ran in the reduced-motion suite only. They are branch scenarios now, so all four
// suites measure them held on screen: the keyboard walk over a page with a `Skeleton` or a busy
// `Button` on it, the focus ring on that `Button`, its 44x44 footprint at 375px, and the loops
// under the preference. `route-reduced-motion.spec.ts` keeps its positive control, which needs
// `loop` to find the looping element by structure.

export const LOADING_SCENARIOS: readonly LoadingScenario[] = [
  branchScenario('/dashboard', 'profile summary loading', {
    // `ProfileSummary`'s `loading` status renders `Skeleton` placeholders, the `pulse` loop, after
    // `useDelayedVisible`'s 200ms: `shows` waits for the structure, never for an animation.
    ...DASHBOARD_PATHS,
    loop: 'skeleton',
    hold: { urlGlob: '**/api/profiles', body: PROFILES_RESPONSE },
    shows: [{ name: 'skeleton', selector: `main ${LOOP_SELECTOR.skeleton}`, min: 1 }],
    stub: async (page: Page) => {
      await stubMe(page, SIGNED_IN_ME)
    },
  }),
  branchScenario('/privacy', 'erase button minting', {
    // `Button`'s `loading` renders `Spinner`, the `spin` loop: the erase button while its
    // confirmation token is minted.
    path: '/privacy',
    loop: 'spinner',
    hold: { urlGlob: '**/api/privacy/erase', body: { confirmation_token: 'visual-suite-token' } },
    shows: [
      {
        name: 'busy erase button',
        selector: 'main button[aria-busy="true"]:has-text("Erase my account")',
        min: 1,
      },
      SPINNER_IN_MAIN,
    ],
    stub: async (page: Page) => {
      await stubMe(page, SIGNED_IN_ME)
    },
    prepare: async (page: Page) => {
      await tabTo(page, page.getByRole('button', { name: 'Erase my account' }))
      await page.keyboard.press('Enter')
    },
  }),
]

export const BRANCH_SCENARIOS: readonly BranchScenario[] = [
  ...ERROR_AND_EMPTY_BRANCHES,
  ...LOADING_SCENARIOS,
]

export const SUITE_SCENARIOS: readonly SuiteScenario[] = [
  ...ROUTE_SCENARIOS,
  ...POPULATED_SCENARIOS,
  ...SURFACE_SCENARIOS,
  ...BRANCH_SCENARIOS,
]

// --- Entering a scenario -------------------------------------------------------------------------

export interface EnterOptions {
  /** Applied before navigation, so the preference is in effect for the very first render. */
  reducedMotion?: boolean
}

/** What `enterScenario` hands back: the external-request watch for the caller to assert at the end
 * of its test, and the release of the scenario's held request (a no-op when it holds none). */
export interface EnteredScenario extends ExternalRequestWatch {
  /** Answers the scenario's `hold` now. Left alone, it is answered when the page closes, so only a
   * test that needs the page to move on afterwards calls it. */
  release: () => Promise<void>
}

/** The setup every suite repeated inline, in one place: avatar stub and external-request watch,
 * reduced-motion preference, theme seed, API stubs, the scenario's held request, navigation,
 * theme-painted and font checks, then the scenario's own `prepare` (search submitted, surface
 * opened). A populated scenario is judged by `assertPopulatedScenario` here — before `prepare`, or
 * after it when `listsNeedPrepare` — and a branch scenario by `assertBranchScenario` after it, so no
 * suite measures a page whose lists are still on their way or that is not on the branch it names. */
export async function enterScenario(
  page: Page,
  scenario: SuiteScenario,
  baseUrl: string,
  theme: ThemeOverride,
  options: EnterOptions = {},
): Promise<EnteredScenario> {
  const external = watchExternalRequests(page, baseUrl)
  await installSteamAvatarStub(page)
  if (options.reducedMotion) await page.emulateMedia({ reducedMotion: 'reduce' })
  await seedThemeOverride(page, theme)
  await scenario.stub(page)
  const held = scenario.hold
    ? await holdRequests(page, scenario.hold.urlGlob, scenario.hold.body)
    : undefined
  // A request still held when the test ends is answered as the page closes, never left dangling.
  page.once('close', () => void held?.release())

  await gotoScenario(page, scenario, baseUrl)
  await page.getByRole('main').waitFor({ state: 'visible' })
  // Proves the theme was actually *painted*, not merely seeded (PR #102 review finding).
  await assertThemeApplied(page, theme)
  await waitForFontsReady(page)

  const judged = isPopulatedScenario(scenario) ? scenario : undefined
  if (judged && !judged.listsNeedPrepare) {
    await assertPopulatedScenario(page, judged, judged.label)
  }
  await scenario.prepare?.(page)
  if (judged?.listsNeedPrepare) await assertPopulatedScenario(page, judged, judged.label)
  if (isBranchScenario(scenario)) await assertBranchScenario(page, scenario, scenario.label)
  return { ...external, release: async () => held?.release() }
}
