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
// 3. BRANCH_SCENARIOS (T744) — every error, transient (in flight or held) and empty branch of every
//    route: the export's `failed` state, `ArchivalControl` in flight, resumed and failed, the match
//    page's loading, error and not-found states, its analysis section in every state, its capture
//    badge, replay-download refusals and upload states, the sign-in outcomes, the search answers,
//    the favourites list's states, `ProfileSummary`'s statuses, the match list's, the profile
//    switcher's, sign-out's and unlink's writes, the favourite toggle's, erasure's, the objection
//    form's, the no-linked-account state, and the two held loading states. A branch is not a list or
//    a control group, so it has its own inventory (`ROUTE_REQUIRED_BRANCHES`) and its own in-browser
//    judge (`assertBranchScenario`): what the branch puts on screen is declared per scenario, and an
//    error callout or a loading region is expected there, not a failure.
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
import { expect, type Locator, type Page } from '@playwright/test'
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
  SIGNED_OUT_ME,
  stubMe,
  stubPlayerProfile,
  THIRD_PARTY_PROFILE_ID,
  waitForFontsReady,
  type RouteScenario,
  type ThemeOverride,
} from './app-routes-harness'
import { installSteamAvatarStub } from './avatar-stub'
import { type ExternalRequestWatch, watchExternalRequests } from './external-requests'
import type { KnownDefect } from './known-defect'
import { holdRequests, LOOP_SELECTOR, type LoopKind } from './loading-state'
import { openMenuByKeyboard, tabTo, type SurfaceKind } from './open-surface'
import { openTooltipByKeyboard } from './tooltip-open'

/** A request held open for as long as the page is open, so the state it feeds stays on screen for the
 * whole of a suite's walk or sweep (`holdRequests`, `./loading-state`). Answered with `body` when
 * the page closes, or earlier through the `release` `enterScenario` returns. */
export interface HeldRequest {
  urlGlob: string
  body: unknown
  /** Holds only requests of this method; any other goes to the scenario's own stub. */
  method?: string
  /** What the request answers when the transient is meant to be over, where `body` alone would
   * leave it going (a poll that reads `queued` keeps the export `preparing`). Read by the planted
   * case that answers the request at once, never by `enterScenario`. */
  resolvesWith?: unknown
}

export interface SuiteScenario extends RouteScenario {
  /** Runs after navigation settles: submits the search, opens the surface — by keyboard. */
  prepare?: (page: Page) => Promise<void>
  /** Installed by `enterScenario` right after `stub`, before navigation. A request this matches
   * stays pending, so the loading or in-flight state it feeds is what every suite measures. */
  hold?: HeldRequest
  /** Set when `prepare` leaves a `Menu` or `Dialog` open: the suites then walk that surface. */
  surface?: SurfaceKind
  /** A defect this scenario's page is known to show to one suite, by suite. The suite asserts the
   * walk fails with exactly `message` (`expectKnownDefect`, `./known-defect`) and fails when the walk
   * passes, so the marker records a red walk and cannot outlive its fix. The task that fixes the
   * defect is named in `specs/005-design-system-foundations/tasks.md` (T750 for the `Dialog` Tab
   * trap). */
  knownDefects?: { keyboard?: KnownDefect }
}

/** One list or control group a populated scenario promises to put on screen: `selector` is
 * resolved in the page and must match at least `min` elements. `name` is what
 * `ROUTE_REQUIRED_LISTS` (`./suite-scenarios.test.ts`) is checked against, so a list nobody
 * declares fails by name. */
export interface ListExpectation {
  name: string
  selector: string
  min: number
  /** An upper bound, for a mark that must be absent (`min: 0, max: 0`): the control a branch hides.
   * Only `assertBranchScenario` reads it. */
  max?: number
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
  /** Branches of one section that render different things from the same stubs (the sign-in
   * outcomes, the analysis states): the planted case for each also runs the sibling's page against
   * this scenario's marks. */
  family?: string
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
    // The write that turns archival off starts from "Archival is on."; the resume's starts from
    // "Archival is off.", and the busy button and the spinner are the same in both.
    text('archival is on', 'Archival is on.'),
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
    family: 'analysis state',
    shows,
    stub: (page: Page) => stubAnalysisIn(page, state, errorClass),
  })
}

/** `/search` with a query submitted against a stubbed answer that has no results. */
function emptySearch(branch: string, degraded: boolean, shows: readonly ListExpectation[]) {
  return branchScenario('/search', branch, {
    path: '/search',
    family: 'search answer',
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
    family: 'export',
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
    family: 'archival write',
    ...ARCHIVAL_IN_FLIGHT,
    stub: async (page: Page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubPopulatedProfiles(page, PROFILES_RESPONSE)
    },
  }),
  branchScenario('/privacy', 'archival write in flight', {
    path: '/privacy',
    family: 'archival write',
    ...ARCHIVAL_IN_FLIGHT,
    stub: async (page: Page) => {
      await stubMe(page, SIGNED_IN_ME)
    },
  }),
  // `ArchivalControl` after a resume (`justResumed`).
  branchScenario('/dashboard', 'archival just resumed', {
    ...DASHBOARD_PATHS,
    family: 'archival write',
    ...ARCHIVAL_JUST_RESUMED,
    stub: async (page: Page) => {
      await stubResumable(page)
      await stubPopulatedProfiles(page, PROFILES_RESPONSE)
    },
  }),
  branchScenario('/privacy', 'archival just resumed', {
    path: '/privacy',
    family: 'archival write',
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

// --- The rest of the enumeration (T744) ------------------------------------------------------------
//
// T744's text names instances; its title says "each route's". The scenarios above are the instances
// it names. These are every other error, transient (in flight or held) and empty branch the
// application's containers and the design-system screens and composites they render can show,
// enumerated from the code: `ROUTE_REQUIRED_BRANCHES` lists them all, and the comment above it says
// which branches no route stub can reach and why.

const FIXTURE_PROFILE = PROFILES_RESPONSE.profiles[0]
const PROFILES_NO_RATINGS = { profiles: [{ ...FIXTURE_PROFILE, ratings: [] }] }
// A rating the leaderboard has not ranked: `formatRank` renders it as the `StatValue` `empty` state.
const PROFILES_UNRANKED = {
  profiles: [{ ...FIXTURE_PROFILE, ratings: [{ ...FIXTURE_PROFILE.ratings[0], rank: null }] }],
}
const PLAYER_NO_RATINGS = { ...PLAYER_PROFILE_RESPONSE, ratings: [] }
const PLAYER_UNRANKED = {
  ...PLAYER_PROFILE_RESPONSE,
  ratings: [{ ...PLAYER_PROFILE_RESPONSE.ratings[0], rank: null }],
}
const EMPTY_MATCHES = { matches: [], next_cursor: null }

function apiError(code: string, message = 'Fixture failure.', detail?: unknown) {
  return { error: { code, message, ...(detail === undefined ? {} : { detail }) } }
}

async function respondJson(page: Page, glob: string, body: unknown): Promise<void> {
  await page.route(glob, (route) => fulfillJson(route, body))
}

/** Answers every request matching `glob` with the API's own error envelope. */
async function failWith(
  page: Page,
  glob: string,
  status = 500,
  code = 'fixture_failure',
  detail?: unknown,
): Promise<void> {
  await page.route(glob, (route) =>
    route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify(apiError(code, 'Fixture failure.', detail)),
    }),
  )
}

/** Every `/api/` response a page has received since `enterScenario` began watching it, in order.
 * What a scenario waits on instead of a pause: the failures its retries are waiting for, the
 * answer a plant gave a held request. */
export interface ApiResponse {
  url: string
  method: string
  status: number
}
const apiResponseLogs = new WeakMap<Page, ApiResponse[]>()

export function apiResponses(page: Page): readonly ApiResponse[] {
  return apiResponseLogs.get(page) ?? []
}

function watchApiResponses(page: Page): void {
  const log: ApiResponse[] = []
  apiResponseLogs.set(page, log)
  page.on('response', (response) => {
    const url = response.url()
    if (url.includes('/api/')) {
      log.push({ url, method: response.request().method(), status: response.status() })
    }
  })
}

const failedApiResponses = (page: Page) =>
  apiResponses(page).filter((response) => response.status >= 400).length

/** A `useQuery` retries a failed request three times, a second, two and four apart, before it
 * reports `isError`. The route clock runs in real time, so waiting that out costs seven seconds a
 * scenario; running the page's clock forward does it in the time the four requests take. Each step
 * waits for the retry's failed answer to arrive, which is what schedules the next retry, rather than
 * for a pause that a loaded machine can outlast. The first attempt's failure is the one the page
 * already has (or is about to have); a scenario with a single failing request is what this counts
 * on, and a second failing query would only let a step end early. */
async function exhaustQueryRetries(page: Page): Promise<void> {
  await expect.poll(() => failedApiResponses(page)).toBeGreaterThanOrEqual(1)
  for (let retry = 1; retry <= 3; retry += 1) {
    await page.clock.runFor(5_000)
    await expect.poll(() => failedApiResponses(page)).toBeGreaterThanOrEqual(1 + retry)
  }
}

/** A request that answers once and then fails: the "stale" status, a refetch that fails after data. */
async function failAfterFirst(page: Page, glob: string, firstBody: unknown): Promise<void> {
  let answered = 0
  await page.route(glob, (route) => {
    answered += 1
    if (answered === 1) return fulfillJson(route, firstBody)
    return route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify(apiError('fixture_failure')),
    })
  })
}

/** What a user returning to the tab does: the query client refetches what is stale. */
async function refetchOnFocus(page: Page): Promise<void> {
  await page.evaluate(() => window.dispatchEvent(new Event('visibilitychange')))
}

async function activate(page: Page, target: Locator): Promise<void> {
  await tabTo(page, target)
  await page.keyboard.press('Enter')
}

/** The wait before a branch is judged: bounded, and never the failure itself. `enterScenario`
 * judges `shows` right after `prepare`, and "<mark> rendered fewer than 1 item(s)" is the failure
 * worth having, not a timeout on a locator. */
async function waitQuietly(locator: Locator, timeout = 5_000): Promise<void> {
  await locator.waitFor({ state: 'visible', timeout }).catch(() => undefined)
}

function mark(name: string, selector: string, min = 1): ListExpectation {
  return { name, selector, min }
}
function text(name: string, copy: string, min = 1): ListExpectation {
  return mark(name, `main :text("${copy}")`, min)
}
/** The element whose whole text is `copy`: a badge, a heading, a label. */
function exactText(name: string, copy: string, min = 1): ListExpectation {
  return mark(name, `main :text-is("${copy}")`, min)
}
function control(name: string, label: string, min = 1): ListExpectation {
  return mark(name, `main button:has-text("${label}")`, min)
}
function busy(name: string, label: string): ListExpectation {
  return mark(name, `button[aria-busy="true"]:has-text("${label}")`)
}
function absent(name: string, selector: string): ListExpectation {
  return { name, selector, min: 0, max: 0 }
}
const SKELETON = mark('skeleton', `main ${LOOP_SELECTOR.skeleton}`)

const SIGNED_IN = async (page: Page) => {
  await stubMe(page, SIGNED_IN_ME)
}

// --- /sign-in ------------------------------------------------------------------------------------
//
// `SignInContainer` passes `phase` `default` or `leaving` only, so `SignInScreen`'s `returning` and
// `unavailable` phases are not reachable from the route (see the hand-back table). The outcome
// comes from `?error=`, the `link` variant from `?link=1` for a signed-in caller.

function signInOutcome(code: string, heading: string, actions: readonly string[]) {
  return branchScenario('/sign-in', `outcome ${code}`, {
    path: `/sign-in?error=${code}`,
    landedPath: '/sign-in',
    family: 'sign-in outcome',
    stub: async (page: Page) => {
      await stubMe(page, SIGNED_OUT_ME)
    },
    shows: [
      text(`${code} callout`, heading),
      ...actions.map((label) => control(`${label} button`, label)),
    ],
  })
}

const SIGN_IN_BRANCHES: readonly BranchScenario[] = [
  signInOutcome('no_aoe2_profile', 'This Steam account has no Age of Empires II profile yet', [
    'Try again',
    'Use a different Steam account',
  ]),
  signInOutcome('not_allowlisted', 'aoe2-stats is in closed beta', ['Try again']),
  signInOutcome('steam_assertion_invalid', 'We could not verify that sign-in with Steam', [
    'Start over',
  ]),
  signInOutcome('unreachable', 'Steam did not answer', ['Try again']),
  branchScenario('/sign-in', 'outcome profile_already_linked', {
    path: '/sign-in?link=true&error=profile_already_linked',
    landedPath: '/sign-in',
    family: 'sign-in outcome',
    stub: SIGNED_IN,
    shows: [
      text('profile_already_linked callout', 'That Steam account is already linked elsewhere'),
      control('Try a different account button', 'Try a different account'),
      control('Cancel button', 'Cancel', 2),
    ],
  }),
  branchScenario('/sign-in', 'link variant', {
    path: '/sign-in?link=true',
    landedPath: '/sign-in',
    family: 'sign-in outcome',
    stub: SIGNED_IN,
    shows: [
      text('link title', 'Link another Steam account'),
      control('Cancel button', 'Cancel'),
      absent('no outcome callout', 'main [role="status"]:has-text("already linked")'),
    ],
  }),
  branchScenario('/sign-in', 'steam redirect in flight', {
    path: '/',
    landedPath: '/sign-in',
    family: 'sign-in outcome',
    // The container sets the `leaving` phase and assigns the Steam URL; that navigation is cancelled
    // (`aborted` leaves the page where it is, as a held document request would not: the page stops
    // answering evaluations), so the screen stays on "Taking you to Steam…".
    stub: async (page: Page) => {
      await stubMe(page, SIGNED_OUT_ME)
      await page.route('**/api/auth/steam/start*', (route) => route.abort('aborted'))
    },
    prepare: async (page: Page) => {
      await activate(page, page.getByRole('button', { name: 'Continue with Steam' }))
      await waitQuietly(page.locator('main button[aria-busy="true"]'))
    },
    shows: [busy('busy sign-in button', 'Taking you to Steam'), SPINNER_IN_MAIN],
  }),
]

// --- /search ------------------------------------------------------------------------------------

async function submitSearch(
  page: Page,
  query = 'Fixture',
  awaitAnswer = true,
  pause = false,
): Promise<void> {
  await tabTo(page, page.locator('main input').first())
  await page.keyboard.type(query)
  if (pause) await pauseClock(page)
  const answered = awaitAnswer ? page.waitForResponse('**/api/players/search*') : undefined
  await page.keyboard.press('Enter')
  await answered
}

function searchBranch(
  branch: string,
  answer: (page: Page) => Promise<void>,
  shows: readonly ListExpectation[],
  extra: Partial<Pick<BranchScenario, 'hold'>> & { awaitAnswer?: boolean; pause?: boolean } = {},
) {
  const { awaitAnswer = true, pause = false, ...rest } = extra
  return branchScenario('/search', branch, {
    path: '/search',
    family: 'search answer',
    ...rest,
    shows,
    stub: async (page: Page) => {
      await stubMe(page, SIGNED_IN_ME)
      await answer(page)
    },
    prepare: (page: Page) => submitSearch(page, 'Fixture', awaitAnswer, pause),
  })
}

const SEARCH_BRANCHES: readonly BranchScenario[] = [
  searchBranch(
    'searching',
    async () => {},
    [mark('busy results region', 'main [role="region"][aria-busy="true"]'), SKELETON],
    {
      awaitAnswer: false,
      hold: { urlGlob: '**/api/players/search*', body: SEARCH_POPULATED },
    },
  ),
  searchBranch(
    'results, degraded',
    async (page) => {
      await page.route('**/api/players/search*', (route) =>
        fulfillJson(route, { ...SEARCH_POPULATED, degraded: true, reason: 'provider_unavailable' }),
      )
    },
    [
      text('degraded banner', 'Player search is temporarily degraded.'),
      text('limited-results note', 'These results are limited to players already known'),
      mark('result links', 'main a[href^="/players/"]', 3),
    ],
  ),
  searchBranch(
    'rate limited',
    async (page) => {
      await failWith(page, '**/api/players/search*', 429, 'rate_limited', { retry_after: 30 })
    },
    [text('rate-limit callout', "You're searching too quickly")],
    // The countdown ticks on the page's clock, which is paused before the search so the thirty
    // seconds it starts from are still thirty when a suite has finished walking the page.
    { pause: true },
  ),
  searchBranch(
    'rate limit elapsed',
    async (page) => {
      await failWith(page, '**/api/players/search*', 429, 'rate_limited', { retry_after: 0 })
    },
    [text('rate-limit elapsed callout', 'You can search again now.')],
  ),
  searchBranch(
    'search failed',
    async (page) => {
      await failWith(page, '**/api/players/search*')
    },
    [
      text('search failure callout', 'We could not search right now.'),
      control('Try again button', 'Try again'),
    ],
  ),
]

// --- /favourites --------------------------------------------------------------------------------

const FAVOURITES_URL = '**/api/favourites'
const FAVOURITE_REMOVE_URL = '**/api/favourites/*'

const FAVOURITES_BRANCHES: readonly BranchScenario[] = [
  branchScenario('/favourites', 'loading', {
    path: '/favourites',
    family: 'favourites list',
    hold: { urlGlob: FAVOURITES_URL, body: FAVOURITES_POPULATED },
    stub: SIGNED_IN,
    shows: [SKELETON],
  }),
  branchScenario('/favourites', 'load failed', {
    path: '/favourites',
    family: 'favourites list',
    stub: async (page: Page) => {
      await stubMe(page, SIGNED_IN_ME)
      await failWith(page, FAVOURITES_URL)
    },
    prepare: exhaustQueryRetries,
    shows: [
      text('favourites failure callout', 'We could not load your favourites. Try again.'),
      control('Try again button', 'Try again'),
    ],
  }),
  branchScenario('/favourites', 'removal in flight', {
    path: '/favourites',
    family: 'favourites list',
    hold: { urlGlob: FAVOURITE_REMOVE_URL, body: { profile_id: THIRD_PARTY_PROFILE_ID } },
    stub: async (page: Page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubPopulatedFavourites(page)
    },
    prepare: async (page: Page) => {
      await activate(page, page.getByRole('button', { name: 'Remove from favourites' }).first())
      await waitQuietly(page.locator('main ul > li button[aria-busy="true"]'))
    },
    shows: [mark('busy remove button', 'main ul > li button[aria-busy="true"]'), SPINNER_IN_MAIN],
  }),
  branchScenario('/favourites', 'removal failed', {
    path: '/favourites',
    family: 'favourites list',
    stub: async (page: Page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubPopulatedFavourites(page)
      await failWith(page, FAVOURITE_REMOVE_URL)
    },
    prepare: async (page: Page) => {
      await activate(page, page.getByRole('button', { name: 'Remove from favourites' }).first())
      await waitQuietly(page.locator('main :text("We could not update your favourites")'))
    },
    shows: [text('removal failure callout', 'We could not update your favourites')],
  }),
]

// --- ArchivalControl's write failing (T744) ---------------------------------------------------

const OBJECTED_CALLOUT = text('objected callout', 'Archival is off.')

/** The objected state's "Resume archival" held in flight: the primary `Button` in `loading`, the
 * objected callout still on screen (`ArchivalControl`'s `StatusRegion`). */
const ARCHIVAL_RESUME_IN_FLIGHT: Pick<BranchScenario, 'hold' | 'prepare' | 'shows'> = {
  hold: {
    urlGlob: '**/api/privacy/archival-objection',
    body: { archival_objected: false, archival_objected_at: null },
  },
  prepare: async (page) => {
    await activate(page, page.getByRole('button', { name: 'Resume archival' }))
    await waitQuietly(page.locator('main button[aria-busy="true"]'))
  },
  shows: [OBJECTED_CALLOUT, busy('busy resume button', 'Saving your choice'), SPINNER_IN_MAIN],
}

/** The objected state's write refused: the objected callout and its button stay, and `FailureRegion`
 * says the choice was not recorded. */
const ARCHIVAL_RESUME_FAILED: Pick<BranchScenario, 'prepare' | 'shows'> = {
  prepare: async (page) => {
    await activate(page, page.getByRole('button', { name: 'Resume archival' }))
    await waitQuietly(page.locator('main :text("We could not save that choice")'))
  },
  shows: [
    OBJECTED_CALLOUT,
    text('archival failure callout', 'We could not save that choice'),
    control('Resume archival button', 'Resume archival'),
  ],
}

const ARCHIVAL_WRITE_FAILED: Pick<BranchScenario, 'prepare' | 'shows'> = {
  prepare: async (page) => {
    await activate(page, page.getByRole('button', { name: 'Object to archival' }))
    await waitQuietly(page.locator('main :text("We could not save that choice")'))
  },
  shows: [
    text('archival failure callout', 'We could not save that choice'),
    control('Object to archival button', 'Object to archival'),
  ],
}

// --- ProfileSummary's statuses, on the four routes that render one -------------------------------
//
// `ProfileSummaryStatus` is derived the same way in `DashboardContainer`, `MatchHistoryContainer`,
// `PlayerProfileContainer` and `PlayerMatchHistoryContainer`: `loading` while the request is
// pending (`LOADING_SCENARIOS` holds it on `/dashboard`, the player routes' `profile loading` below), `error` when it failed with no data, `stale` when a
// refetch failed after data, `empty` for a profile with no ratings, and (the player routes only)
// `not-found` for a 404. Each route gets each status it can derive.

interface SummaryRoute {
  route: string
  paths: { path: string; landedPath?: string }
  /** Everything the route requests except the profile data itself. */
  base: (page: Page) => Promise<void>
  /** The request that carries the profile data. */
  glob: string
  ok: unknown
  noRatings: unknown
  unranked: unknown
  /** The alias the loaded profile shows. Set for the routes that also list matches: a held profile
   * and a held match list are both "loading", and only the alias on screen tells them apart. */
  identity?: string
}

const SUMMARY_ROUTES: readonly SummaryRoute[] = [
  {
    route: '/dashboard',
    paths: DASHBOARD_PATHS,
    base: SIGNED_IN,
    glob: '**/api/profiles',
    ok: PROFILES_RESPONSE,
    noRatings: PROFILES_NO_RATINGS,
    unranked: PROFILES_UNRANKED,
  },
  {
    route: '/matches',
    paths: { path: '/matches' },
    base: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await page.route('**/api/matches?*', (route) => fulfillJson(route, EMPTY_MATCHES))
    },
    identity: 'VisualSuitePlayer',
    glob: '**/api/profiles',
    ok: PROFILES_RESPONSE,
    noRatings: PROFILES_NO_RATINGS,
    unranked: PROFILES_UNRANKED,
  },
  {
    route: '/players/$profileId',
    paths: { path: `/players/${THIRD_PARTY_PROFILE_ID}` },
    base: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await page.route('**/api/favourites', (route) => fulfillJson(route, { favourites: [] }))
    },
    glob: `**/api/players/${THIRD_PARTY_PROFILE_ID}`,
    ok: PLAYER_PROFILE_RESPONSE,
    noRatings: PLAYER_NO_RATINGS,
    unranked: PLAYER_UNRANKED,
  },
  {
    route: '/players/$profileId/matches',
    paths: { path: `/players/${THIRD_PARTY_PROFILE_ID}/matches` },
    base: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await page.route(`**/api/players/${THIRD_PARTY_PROFILE_ID}/matches*`, (route) =>
        fulfillJson(route, EMPTY_MATCHES),
      )
    },
    identity: 'ThirdPartyPlayer',
    glob: `**/api/players/${THIRD_PARTY_PROFILE_ID}`,
    ok: PLAYER_PROFILE_RESPONSE,
    noRatings: PLAYER_NO_RATINGS,
    unranked: PLAYER_UNRANKED,
  },
]

function summaryBranch(
  source: SummaryRoute,
  branch: string,
  profile: (page: Page, source: SummaryRoute) => Promise<void>,
  shows: readonly ListExpectation[],
  extra: Pick<BranchScenario, 'prepare' | 'hold'> = {},
) {
  return branchScenario(source.route, branch, {
    ...source.paths,
    family: 'profile summary status',
    ...extra,
    shows,
    stub: async (page: Page) => {
      await source.base(page)
      await profile(page, source)
    },
  })
}

const RATINGS_FAILED = [
  text('ratings failure callout', 'We could not load your ratings'),
  control('Try again button', 'Try again'),
]

function summaryBranchesFor(source: SummaryRoute): BranchScenario[] {
  const isPlayer = source.route.startsWith('/players')
  const branches = [
    summaryBranch(
      source,
      'profile load failed',
      (page, s) => failWith(page, s.glob),
      RATINGS_FAILED,
      { prepare: exhaustQueryRetries },
    ),
    summaryBranch(
      source,
      'profile stale',
      (page, s) => failAfterFirst(page, s.glob, s.ok),
      [
        text('stale callout', 'These figures could not be refreshed'),
        control('Try again button', 'Try again'),
      ],
      {
        prepare: async (page) => {
          // `/api/profiles` is fresh for thirty seconds (`profilesQueryOptions`), and a refetch on
          // focus only fires for stale data.
          await page.clock.runFor(31_000)
          await refetchOnFocus(page)
          await exhaustQueryRetries(page)
        },
      },
    ),
    summaryBranch(source, 'ratings empty', (page, s) => respondJson(page, s.glob, s.noRatings), [
      text('no-ratings callout', 'No ratings yet'),
    ]),
    summaryBranch(source, 'rating unranked', (page, s) => respondJson(page, s.glob, s.unranked), [
      text('not-ranked note', 'Not ranked yet'),
    ]),
  ]
  if (isPlayer) {
    branches.push(
      summaryBranch(
        source,
        'player not found',
        (page, s) => failWith(page, s.glob, 404, 'not_found'),
        [
          text('not-found callout', 'This player could not be found.'),
          mark('Back to search link', 'main a:has-text("Back to search")'),
        ],
        { prepare: exhaustQueryRetries },
      ),
    )
  }
  // `/dashboard`'s held loading state is `LOADING_SCENARIOS`'s, which also finds the pulse loop.
  if (source.route !== '/dashboard') {
    branches.push(
      summaryBranch(
        source,
        'profile loading',
        (page, s) => respondJson(page, s.glob, s.ok),
        [
          SKELETON,
          mark('busy rating board', 'main [aria-busy="true"]'),
          absent('no ratings failure', 'main :text("We could not load your ratings")'),
          ...(source.identity
            ? [absent('no profile identity', `main :text("${source.identity}")`)]
            : []),
        ],
        { hold: { urlGlob: source.glob, body: source.ok } },
      ),
    )
  }
  return branches
}

const SUMMARY_BRANCHES: readonly BranchScenario[] = SUMMARY_ROUTES.flatMap(summaryBranchesFor)

// --- /matches and /players/$profileId/matches: the match list -------------------------------------

const CAPTURE_ROWS: readonly [number, string, string | null][] = [
  [555000201, 'pending', '2026-10-16T09:00:00Z'],
  [555000202, 'downloading', '2026-10-16T09:00:00Z'],
  [555000203, 'unavailable', null],
  [555000204, 'expired', null],
  [555000205, 'failed', null],
  [555000206, 'quarantined', null],
  [555000207, 'withdrawn', null],
  [555000208, 'mystery_status', null],
]

function matchesWithCaptureStatuses() {
  return {
    matches: CAPTURE_ROWS.map(([gameId, status, deadline]) => ({
      ...matchRow(gameId, 'win', 7, VIEWER_ID),
      capture_status: status,
      capture_deadline_at: deadline,
    })),
    next_cursor: null,
  }
}

const OWN_MATCHES = {
  route: '/matches',
  paths: { path: '/matches' },
  base: async (page: Page) => {
    await stubMe(page, SIGNED_IN_ME)
    await stubPopulatedProfiles(page, PROFILES_RESPONSE)
  },
  glob: '**/api/matches?*',
  identity: 'VisualSuitePlayer',
}
const PLAYER_MATCHES = {
  route: '/players/$profileId/matches',
  paths: { path: `/players/${THIRD_PARTY_PROFILE_ID}/matches` },
  base: async (page: Page) => {
    await stubMe(page, SIGNED_IN_ME)
    await stubPlayerProfile(page, THIRD_PARTY_PROFILE_ID)
  },
  glob: `**/api/players/${THIRD_PARTY_PROFILE_ID}/matches*`,
  identity: 'ThirdPartyPlayer',
}

function listBranch(
  source: typeof OWN_MATCHES,
  branch: string,
  answer: (page: Page) => Promise<void>,
  shows: readonly ListExpectation[],
  extra: Pick<BranchScenario, 'prepare' | 'hold'> & { me?: unknown } = {},
) {
  const { me = SIGNED_IN_ME, ...rest } = extra
  return branchScenario(source.route, branch, {
    ...source.paths,
    family: 'match list',
    ...rest,
    shows,
    stub: async (page: Page) => {
      await source.base(page)
      await stubMe(page, me)
      await answer(page)
    },
  })
}

const MATCH_LIST_BRANCHES: readonly BranchScenario[] = [OWN_MATCHES, PLAYER_MATCHES].flatMap(
  (source) => [
    listBranch(
      source,
      'match list loading',
      async () => {},
      [
        mark('busy match list', 'main [aria-busy="true"]'),
        SKELETON,
        text('profile identity', source.identity),
      ],
      { hold: { urlGlob: source.glob, body: EMPTY_MATCHES } },
    ),
    listBranch(
      source,
      'match list load failed',
      (page) => failWith(page, source.glob),
      [
        text('match list failure callout', 'We could not load your match history'),
        control('Try again button', 'Try again'),
      ],
      { prepare: exhaustQueryRetries },
    ),
  ],
)

const CAPTURE_BADGES: readonly ListExpectation[] = [
  exactText('catchable badge', 'Still catchable', 2),
  exactText('lost badge', 'Lost', 3),
  exactText('review badge', 'Needs review'),
  exactText('not-archived badge', 'Not archived'),
  exactText('unrecognised status badge', 'mystery_status'),
  mark('catchable countdown', 'main :text("days left")'),
]

const CAPTURE_LIST_BRANCHES: readonly BranchScenario[] = [
  listBranch(
    OWN_MATCHES,
    'capture statuses',
    (page) => respondJson(page, OWN_MATCHES.glob, matchesWithCaptureStatuses()),
    CAPTURE_BADGES,
  ),
  listBranch(
    OWN_MATCHES,
    'capture statuses, archival objected',
    (page) => respondJson(page, OWN_MATCHES.glob, matchesWithCaptureStatuses()),
    [
      exactText('not-archived badges', 'Not archived', 3),
      absent('no catchable badge', 'main :text-is("Still catchable")'),
    ],
    { me: OBJECTED_ME },
  ),
]

// --- /dashboard and /matches: the profile switcher's writes -------------------------------------

const MAKE_PRIMARY_URL = `**/api/profiles/${SECOND_LINKED_PROFILE_ID}/primary`

/** View the second linked profile (it is not primary, so "Make primary" joins the Manage menu), open
 * the Manage menu and choose "Make primary" — all by keyboard, as the existing surface scenarios do. */
async function chooseMakePrimary(page: Page): Promise<void> {
  await openMenuByKeyboard(page, switcherTrigger(page))
  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('Enter')
  await page.keyboard.press('Escape')
  await expect(switcherTrigger(page)).toContainText('VisualSuiteSmurf')
  await openMenuByKeyboard(page, manageTrigger(page))
  await page.keyboard.press('Enter')
}

function makePrimaryBranch(
  route: string,
  paths: { path: string; landedPath?: string },
  branch: string,
  extra: Pick<BranchScenario, 'hold' | 'surface' | 'prepare'>,
  shows: readonly ListExpectation[],
  answer: (page: Page) => Promise<void>,
) {
  return branchScenario(route, branch, {
    ...paths,
    family: 'make primary',
    ...extra,
    shows,
    stub: async (page: Page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubPopulatedProfiles(page, TWO_PROFILES_RESPONSE)
      if (route === '/matches') {
        await page.route('**/api/matches?*', (r) => fulfillJson(r, EMPTY_MATCHES))
      }
      await answer(page)
    },
  })
}

// `MatchHistoryContainer` wires `onMakePrimary` too, but "Make primary" lives in the Manage menu, which
// `ProfileSummary` renders for the `board` variant only (`!compact`), so `/matches` has no trigger for
// it and nothing to judge.
const MAKE_PRIMARY_BRANCHES: readonly BranchScenario[] = [['/dashboard', DASHBOARD_PATHS]].flatMap(
  ([route, paths]) => [
    makePrimaryBranch(
      route as string,
      paths as { path: string; landedPath?: string },
      'make primary in flight',
      {
        hold: { urlGlob: MAKE_PRIMARY_URL, body: { profile_id: SECOND_LINKED_PROFILE_ID } },
        surface: 'menu',
        prepare: async (page) => {
          await chooseMakePrimary(page)
          await openMenuByKeyboard(page, manageTrigger(page)).catch(() => undefined)
        },
      },
      [
        mark(
          'busy Make primary item',
          '[role="menuitem"][aria-busy="true"]:has-text("Make primary")',
        ),
      ],
      async () => {},
    ),
    makePrimaryBranch(
      route as string,
      paths as { path: string; landedPath?: string },
      'make primary failed',
      {
        prepare: async (page) => {
          await chooseMakePrimary(page)
          await waitQuietly(page.locator('main :text("We could not change your primary profile")'))
        },
      },
      [text('make-primary failure callout', 'We could not change your primary profile')],
      (page) => failWith(page, MAKE_PRIMARY_URL),
    ),
  ],
)

// --- /dashboard: sign-out, unlink and the archival write ------------------------------------------

// `Dialog`'s Tab trap (`packages/design-system/src/primitives/Dialog/index.tsx`) wraps focus at the
// first and last element its selector finds, and the selector includes a `disabled` button. While a
// dialog's request is in flight its secondary action is natively `disabled` and is the last element
// in the DOM, so Tab from the loading primary action is never wrapped and the browser walks focus
// out to the page behind the backdrop. Found by this file's scenarios, fixed by T750
// (`specs/005-design-system-foundations/tasks.md`), not by them.
const DIALOG_TRAP_LEAK: KnownDefect = {
  reason:
    'Dialog traps Tab on elements that include a disabled button, so with its secondary action ' +
    'disabled mid-request focus leaves the dialog (T750)',
  message: /focus left the dialog during its walk/,
}

const UNLINK_PREVIEW_URL = `**/api/profiles/${VIEWER_ID}`
const UNLINK_CONFIRM_URL = `**/api/profiles/${VIEWER_ID}?confirm=true`
const UNLINK_PREVIEW_BODY = {
  confirmed: false,
  archived_replays: { retained: true, count: 2, message: 'They stay archived.' },
}

async function dashboardWithTwoProfiles(page: Page): Promise<void> {
  await stubMe(page, SIGNED_IN_ME)
  await stubPopulatedProfiles(page, TWO_PROFILES_RESPONSE)
}

async function chooseUnlink(page: Page): Promise<void> {
  await openMenuByKeyboard(page, manageTrigger(page))
  await page.keyboard.press('Enter')
}

/** Puts focus back on the dialog's own heading, where it starts when the dialog opens. A scenario
 * that pressed a button inside the dialog leaves focus on that button, and the surface walk
 * (`walkOpenSurface`) reads "every item once, in order, then a wrap" from the heading. */
async function focusDialogHeading(page: Page): Promise<void> {
  // Bounded and quiet: a dialog the scenario's request has already closed is judged by its marks.
  await page
    .getByRole('dialog')
    .getByRole('heading', { level: 2 })
    .first()
    .focus({ timeout: 2_000 })
    .catch(() => undefined)
}

async function openUnlinkDialog(page: Page): Promise<void> {
  await chooseUnlink(page)
  await page.getByRole('dialog').waitFor({ state: 'visible' })
}

function dashboardBranch(
  branch: string,
  family: string,
  rest: Omit<BranchScenario, 'label' | 'route' | 'branch' | 'family' | 'path' | 'landedPath'>,
) {
  return branchScenario('/dashboard', branch, { ...DASHBOARD_PATHS, family, ...rest })
}

const DASHBOARD_ACTION_BRANCHES: readonly BranchScenario[] = [
  dashboardBranch('sign-out in flight', 'sign-out', {
    hold: { urlGlob: '**/api/auth/signout', body: null },
    stub: dashboardWithTwoProfiles,
    prepare: async (page) => {
      await activate(page, page.getByRole('button', { name: 'Sign out' }))
      await waitQuietly(page.locator('button[aria-busy="true"]'))
    },
    shows: [busy('busy sign-out button', 'Signing out')],
  }),
  dashboardBranch('sign-out failed', 'sign-out', {
    stub: async (page) => {
      await dashboardWithTwoProfiles(page)
      await failWith(page, '**/api/auth/signout')
    },
    prepare: async (page) => {
      await activate(page, page.getByRole('button', { name: 'Sign out' }))
      await waitQuietly(page.locator('main :text("We could not sign you out")'))
    },
    shows: [text('sign-out failure callout', 'We could not sign you out')],
  }),
  dashboardBranch('unlink check in flight', 'unlink', {
    surface: 'menu',
    hold: { urlGlob: UNLINK_PREVIEW_URL, body: UNLINK_PREVIEW_BODY },
    stub: dashboardWithTwoProfiles,
    prepare: async (page) => {
      await chooseUnlink(page)
      await openMenuByKeyboard(page, manageTrigger(page)).catch(() => undefined)
    },
    shows: [mark('busy Unlink item', '[role="menuitem"][aria-busy="true"]:has-text("Unlink")')],
  }),
  dashboardBranch('unlink check failed', 'unlink', {
    surface: 'menu',
    stub: async (page) => {
      await dashboardWithTwoProfiles(page)
      await failWith(page, UNLINK_PREVIEW_URL)
    },
    prepare: async (page) => {
      const failed = page.waitForResponse(
        (response) =>
          response.url().endsWith(`/api/profiles/${VIEWER_ID}`) && response.status() >= 400,
      )
      await chooseUnlink(page)
      await failed
      // The menu closes on the choice; the failure is shown inside it when it is opened again.
      await expect(page.locator('[role="menu"]')).toHaveCount(0)
      await openMenuByKeyboard(page, manageTrigger(page)).catch(() => undefined)
    },
    shows: [text('unlink check failure', 'We could not check what unlinking would do')],
  }),
  dashboardBranch('unlink in flight', 'unlink', {
    surface: 'dialog',
    hold: { urlGlob: UNLINK_CONFIRM_URL, body: { unlinked: true } },
    knownDefects: { keyboard: DIALOG_TRAP_LEAK },
    stub: async (page) => {
      await dashboardWithTwoProfiles(page)
      await page.route(UNLINK_PREVIEW_URL, (route) => fulfillJson(route, UNLINK_PREVIEW_BODY))
    },
    prepare: async (page) => {
      await openUnlinkDialog(page)
      await activate(page, page.getByRole('button', { name: 'Unlink this profile' }))
      await waitQuietly(page.locator('[role="dialog"] button[aria-busy="true"]'))
      await focusDialogHeading(page)
    },
    shows: [busy('busy Unlink button', 'Unlinking')],
  }),
  dashboardBranch('unlink failed', 'unlink', {
    surface: 'dialog',
    stub: async (page) => {
      await dashboardWithTwoProfiles(page)
      await page.route(UNLINK_PREVIEW_URL, (route) => fulfillJson(route, UNLINK_PREVIEW_BODY))
      await failWith(page, UNLINK_CONFIRM_URL)
    },
    prepare: async (page) => {
      await openUnlinkDialog(page)
      await activate(page, page.getByRole('button', { name: 'Unlink this profile' }))
      await waitQuietly(page.locator('[role="dialog"] :text("We could not unlink this profile")'))
      await focusDialogHeading(page)
    },
    shows: [
      mark('unlink failure callout', '[role="dialog"] :text("We could not unlink this profile")'),
    ],
  }),
  dashboardBranch('archival write failed', 'archival write', {
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubPopulatedProfiles(page, PROFILES_RESPONSE)
      await failWith(page, '**/api/privacy/archival-objection')
    },
    ...ARCHIVAL_WRITE_FAILED,
  }),
  dashboardBranch('archival resume in flight', 'archival write', {
    ...ARCHIVAL_RESUME_IN_FLIGHT,
    stub: async (page) => {
      await stubMe(page, OBJECTED_ME)
      await stubPopulatedProfiles(page, PROFILES_RESPONSE)
    },
  }),
  dashboardBranch('archival resume failed', 'archival write', {
    ...ARCHIVAL_RESUME_FAILED,
    stub: async (page) => {
      await stubMe(page, OBJECTED_ME)
      await stubPopulatedProfiles(page, PROFILES_RESPONSE)
      await failWith(page, '**/api/privacy/archival-objection')
    },
  }),
]

// --- /privacy ------------------------------------------------------------------------------------

const EXPORT_POLL_URL = `**/api/privacy/export/${EXPORT_JOB_ID}`

/** Tab to the erase button, open the dialog, tick the acknowledgement and press the dialog's
 * confirm button — every step by keyboard. */
async function confirmErasure(page: Page): Promise<void> {
  await activate(page, page.getByRole('button', { name: 'Erase my account' }))
  await page.getByRole('dialog').waitFor({ state: 'visible' })
  await page.keyboard.press('Tab')
  await page.keyboard.press('Space')
  await activate(page, page.getByRole('button', { name: 'Erase my account permanently' }))
}

async function mintsToken(page: Page): Promise<void> {
  await page.route('**/api/privacy/erase', (route) =>
    route.request().method() === 'GET'
      ? fulfillJson(route, { confirmation_token: 'visual-suite-token' })
      : route.fallback(),
  )
}

function privacyBranch(
  branch: string,
  family: string,
  rest: Omit<BranchScenario, 'label' | 'route' | 'branch' | 'family' | 'path'>,
) {
  return branchScenario('/privacy', branch, { path: '/privacy', family, ...rest })
}

/** A dialog callout, and whether the acknowledgement was ticked when it appeared: a failed first
 * mint opens the dialog unticked, a refused or failed erase leaves it ticked, and that is what tells
 * the two "We could not erase your account." dialogs apart. */
const ERASE_DIALOG_FAILED = (copy: string, acknowledged: boolean) => [
  mark('erase failure callout', `[role="dialog"] :text("${copy}")`),
  mark(
    acknowledged ? 'ticked acknowledgement' : 'unticked acknowledgement',
    `[role="dialog"] input[type="checkbox"]${acknowledged ? ':checked' : ':not(:checked)'}`,
  ),
]

const PRIVACY_BRANCHES: readonly BranchScenario[] = [
  privacyBranch('export requesting', 'export', {
    hold: { urlGlob: '**/api/privacy/export', body: { id: EXPORT_JOB_ID, status: 'queued' } },
    stub: SIGNED_IN,
    prepare: async (page) => {
      await activate(page, page.getByRole('button', { name: 'Export my data' }))
      await waitQuietly(page.locator('main button[aria-busy="true"]'))
    },
    shows: [
      busy('busy export button', 'Preparing your export'),
      SPINNER_IN_MAIN,
      absent('no preparing callout', 'main :text("Your export is being prepared.")'),
    ],
  }),
  privacyBranch('export preparing', 'export', {
    // The poll is held, so the panel stays `preparing` past its ten-second ceiling.
    hold: {
      urlGlob: EXPORT_POLL_URL,
      body: { id: EXPORT_JOB_ID, status: 'queued' },
      resolvesWith: {
        id: EXPORT_JOB_ID,
        status: 'completed',
        download_url: EXPORT_DOWNLOAD_PATH,
      },
    },
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await page.route('**/api/privacy/export', (route) =>
        fulfillJson(route, { id: EXPORT_JOB_ID, status: 'queued' }),
      )
    },
    prepare: async (page) => {
      await activate(page, page.getByRole('button', { name: 'Export my data' }))
      await waitQuietly(page.locator('main :text("Your export is being prepared.")'))
    },
    shows: [text('preparing callout', 'Your export is being prepared.'), SKELETON],
  }),
  privacyBranch('archival write failed', 'archival write', {
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await failWith(page, '**/api/privacy/archival-objection')
    },
    ...ARCHIVAL_WRITE_FAILED,
  }),
  privacyBranch('archival resume in flight', 'archival write', {
    ...ARCHIVAL_RESUME_IN_FLIGHT,
    stub: async (page) => {
      await stubMe(page, OBJECTED_ME)
    },
  }),
  privacyBranch('archival resume failed', 'archival write', {
    ...ARCHIVAL_RESUME_FAILED,
    stub: async (page) => {
      await stubMe(page, OBJECTED_ME)
      await failWith(page, '**/api/privacy/archival-objection')
    },
  }),
  privacyBranch('erasure confirmation minting failed', 'erasure', {
    surface: 'dialog',
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await failWith(page, '**/api/privacy/erase')
    },
    prepare: async (page) => {
      await activate(page, page.getByRole('button', { name: 'Erase my account' }))
      await waitQuietly(page.locator('[role="dialog"] :text("We could not erase your account.")'))
    },
    shows: ERASE_DIALOG_FAILED('We could not erase your account.', false),
  }),
  privacyBranch('erasure in flight', 'erasure', {
    surface: 'dialog',
    hold: { urlGlob: '**/api/privacy/erase', body: { status: 'erased' }, method: 'POST' },
    knownDefects: { keyboard: DIALOG_TRAP_LEAK },
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await mintsToken(page)
    },
    prepare: async (page) => {
      await confirmErasure(page)
      await waitQuietly(page.locator('[role="dialog"] button[aria-busy="true"]'))
      await focusDialogHeading(page)
    },
    shows: [busy('busy erase confirm button', 'Erasing your account')],
  }),
  privacyBranch('erasure confirmation expired', 'erasure', {
    surface: 'dialog',
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await mintsToken(page)
      await page.route('**/api/privacy/erase', (route) =>
        route.request().method() === 'POST'
          ? route.fulfill({
              status: 403,
              contentType: 'application/json',
              body: JSON.stringify(apiError('confirmation_token_invalid')),
            })
          : route.fallback(),
      )
    },
    prepare: async (page) => {
      await confirmErasure(page)
      await waitQuietly(page.locator('[role="dialog"] :text("Your confirmation expired.")'))
      await focusDialogHeading(page)
    },
    shows: ERASE_DIALOG_FAILED('Your confirmation expired.', true),
  }),
  // Pressing the confirm button again after a 403 mints a fresh token inside the open dialog
  // (`handleConfirm`: `minting` with `dialogHasOpened`): the confirm button is natively disabled for
  // the wait, and was the focused element. A failed re-mint ends in the `failed` dialog with the
  // acknowledgement still ticked, which a failed erase also ends in, so it is not a scenario of its
  // own. T751 files the focus drop; this `prepare` moves focus back to the dialog heading after the
  // press (`focusDialogHeading`), so the keyboard result here does not judge where the press left
  // focus, and T751 owns removing that step.
  privacyBranch('erasure re-mint in flight', 'erasure', {
    surface: 'dialog',
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      let mints = 0
      let release: () => void = () => {}
      const gate = new Promise<void>((resolve) => {
        release = resolve
      })
      // Answered as the page closes, never left dangling.
      page.once('close', () => release())
      await page.route('**/api/privacy/erase', async (route) => {
        if (route.request().method() === 'POST') {
          await route.fulfill({
            status: 403,
            contentType: 'application/json',
            body: JSON.stringify(apiError('confirmation_token_invalid')),
          })
          return
        }
        mints += 1
        if (mints === 1) {
          await fulfillJson(route, { confirmation_token: 'visual-suite-token' })
          return
        }
        await gate
        await fulfillJson(route, { confirmation_token: 'visual-suite-token-2' }).catch(
          () => undefined,
        )
      })
    },
    prepare: async (page) => {
      await confirmErasure(page)
      await waitQuietly(page.locator('[role="dialog"] :text("Your confirmation expired.")'))
      await activate(page, page.getByRole('button', { name: 'Erase my account permanently' }))
      await waitQuietly(
        page.locator('[role="dialog"] button:disabled:has-text("Erase my account permanently")'),
      )
      await focusDialogHeading(page)
    },
    shows: [
      mark('ticked acknowledgement', '[role="dialog"] input[type="checkbox"]:checked'),
      mark(
        'disabled confirm button',
        '[role="dialog"] button:disabled:has-text("Erase my account permanently")',
      ),
      absent('no expiry callout', '[role="dialog"] :text("Your confirmation expired.")'),
    ],
  }),
  privacyBranch('erasure failed', 'erasure', {
    surface: 'dialog',
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await mintsToken(page)
      await page.route('**/api/privacy/erase', (route) =>
        route.request().method() === 'POST'
          ? route.fulfill({
              status: 500,
              contentType: 'application/json',
              body: JSON.stringify(apiError('fixture_failure')),
            })
          : route.fallback(),
      )
    },
    prepare: async (page) => {
      await confirmErasure(page)
      await waitQuietly(page.locator('[role="dialog"] :text("We could not erase your account.")'))
      await focusDialogHeading(page)
    },
    shows: ERASE_DIALOG_FAILED('We could not erase your account.', true),
  }),
  privacyBranch('account erased', 'erasure', {
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await mintsToken(page)
      await page.route('**/api/privacy/erase', (route) =>
        route.request().method() === 'POST'
          ? fulfillJson(route, { status: 'erased' })
          : route.fallback(),
      )
    },
    prepare: async (page) => {
      await confirmErasure(page)
      await waitQuietly(page.locator('main :text("Your account has been erased.")'))
    },
    shows: [
      text('erased heading', 'Your account has been erased.'),
      absent('no erase button', 'main button:has-text("Erase my account")'),
    ],
  }),
]

// --- /object ------------------------------------------------------------------------------------

const OBJECTION_URL = '**/api/privacy/object'

async function submitObjection(page: Page, value: string): Promise<void> {
  await tabTo(page, page.locator('main input').first())
  await page.keyboard.type(value)
  await page.keyboard.press('Enter')
}

function objectBranch(
  branch: string,
  answer: (page: Page) => Promise<void>,
  value: string,
  settle: string,
  shows: readonly ListExpectation[],
  hold?: HeldRequest,
) {
  return branchScenario('/object', branch, {
    path: '/object',
    family: 'objection form',
    hold,
    shows,
    stub: async (page: Page) => {
      await stubMe(page, SIGNED_OUT_ME)
      await answer(page)
    },
    prepare: async (page: Page) => {
      await submitObjection(page, value)
      await waitQuietly(page.locator(settle))
    },
  })
}

const OBJECT_BRANCHES: readonly BranchScenario[] = [
  objectBranch(
    'invalid profile id',
    async () => {},
    'not-a-number',
    'main input[aria-invalid="true"]',
    [
      text('field error', 'Enter your numeric profile id'),
      mark('invalid input', 'main input[aria-invalid="true"]'),
    ],
  ),
  objectBranch(
    'objection submitting',
    async () => {},
    '4242',
    'main button[aria-busy="true"]',
    [busy('busy submit button', 'Recording your objection'), SPINNER_IN_MAIN],
    { urlGlob: OBJECTION_URL, body: { id: 'visual-suite-objection', status: 'recorded' } },
  ),
  objectBranch(
    'objection recorded',
    (page) =>
      respondJson(page, OBJECTION_URL, { id: 'visual-suite-objection', status: 'recorded' }),
    '4242',
    'main :text("Your objection has been recorded.")',
    [text('recorded callout', 'Your objection has been recorded.')],
  ),
  objectBranch(
    'objection rate limited',
    (page) => failWith(page, OBJECTION_URL, 429, 'rate_limited'),
    '4242',
    'main :text("Too many objections right now.")',
    [text('rate-limited callout', 'Too many objections right now.')],
  ),
  objectBranch(
    'objection failed',
    (page) => failWith(page, OBJECTION_URL),
    '4242',
    'main :text("We could not record your objection.")',
    [text('objection failure callout', 'We could not record your objection.')],
  ),
]

// --- /players/$profileId: the favourite toggle ----------------------------------------------------

const FAVOURITE_ADD_URL = `**/api/favourites/${THIRD_PARTY_PROFILE_ID}`

function toggleBranch(
  branch: string,
  action: 'add' | 'remove',
  answer: (page: Page) => Promise<void>,
  settle: string,
  shows: readonly ListExpectation[],
  hold?: HeldRequest,
) {
  return branchScenario('/players/$profileId', branch, {
    path: `/players/${THIRD_PARTY_PROFILE_ID}`,
    family: 'favourite toggle',
    hold,
    shows,
    stub: async (page: Page) => {
      await stubMe(page, SIGNED_IN_ME)
      // Removing needs a profile that is already a favourite; adding, one that is not.
      await respondJson(
        page,
        '**/api/favourites',
        action === 'remove' ? FAVOURITES_POPULATED : { favourites: [] },
      )
      await stubPlayerProfile(page, THIRD_PARTY_PROFILE_ID)
      await answer(page)
    },
    prepare: async (page: Page) => {
      const name = action === 'add' ? 'Add to favourites' : 'Remove from favourites'
      await activate(page, page.getByRole('button', { name }))
      await waitQuietly(page.locator(settle))
    },
  })
}

const MUTATED = { profile_id: THIRD_PARTY_PROFILE_ID, favourited: true }

const FAVOURITE_TOGGLE_BRANCHES: readonly BranchScenario[] = [
  toggleBranch(
    'favourite add in flight',
    'add',
    async () => {},
    'main button[aria-busy="true"]',
    [busy('busy toggle', 'Adding'), SPINNER_IN_MAIN],
    { urlGlob: FAVOURITE_ADD_URL, body: MUTATED },
  ),
  toggleBranch(
    'favourites limit reached',
    'add',
    (page) => failWith(page, FAVOURITE_ADD_URL, 409, 'favourites_limit_reached'),
    'main :text("You have reached your favourites limit")',
    [text('limit callout', 'You have reached your favourites limit')],
  ),
  toggleBranch(
    'favourite add failed',
    'add',
    (page) => failWith(page, FAVOURITE_ADD_URL),
    'main :text("We could not update your favourites")',
    [
      text('favourite add failure callout', 'We could not update your favourites'),
      control('Add to favourites button', 'Add to favourites'),
    ],
  ),
  toggleBranch(
    'favourite remove in flight',
    'remove',
    async () => {},
    'main button[aria-busy="true"]',
    [busy('busy toggle', 'Removing'), SPINNER_IN_MAIN],
    { urlGlob: FAVOURITE_ADD_URL, body: MUTATED },
  ),
  toggleBranch(
    'favourite remove failed',
    'remove',
    (page) => failWith(page, FAVOURITE_ADD_URL),
    'main :text("We could not update your favourites")',
    [
      text('favourite remove failure callout', 'We could not update your favourites'),
      control('Remove from favourites button', 'Remove from favourites'),
    ],
  ),
]

// --- /matches/$gameId ---------------------------------------------------------------------------

const MATCH_URL = `**/api/matches/${SAMPLE_GAME_ID}`
const ANALYSIS_URL = `**/api/matches/${SAMPLE_GAME_ID}/analysis`
const UPLOAD_URL = `**/api/replays/${SAMPLE_GAME_ID}/upload`

function detailBody(overrides: Record<string, unknown> = {}, analysis = analysisSummary('absent')) {
  return { ...MATCH_DETAIL_POPULATED, analysis, ...overrides }
}

/** The match page with `body` as its detail response; the analysis document and `POST
 * /api/analyze` answer as they would for a published and a queued analysis. */
async function stubDetailBody(page: Page, body: unknown, me: unknown = SIGNED_IN_ME) {
  await stubMe(page, me)
  await stubPopulatedProfiles(page, PROFILES_RESPONSE)
  await page.route(MATCH_URL, (route) => fulfillJson(route, body))
  await page.route(ANALYSIS_URL, (route) => fulfillJson(route, ANALYSIS_DOCUMENT))
  await page.route('**/api/analyze', (route) => fulfillJson(route, analysisSummary('queued')))
}

function detailBranch(
  branch: string,
  family: string | undefined,
  rest: Omit<BranchScenario, 'label' | 'route' | 'branch' | 'family' | 'path'> & { path?: string },
) {
  return branchScenario('/matches/$gameId', branch, {
    path: `/matches/${SAMPLE_GAME_ID}`,
    family,
    ...rest,
  })
}

/** The loaded match's own header: the leaderboard name `MATCH_DETAIL_POPULATED` carries, which the
 * panel renders only once the match response has arrived. The scenarios about the analysis section
 * declare it so that none of them can hold on a page whose match is still loading or failed. */
const LOADED_MATCH_PANEL = text('loaded match panel', 'Team Random Map')

const MATCH_PAGE_BRANCHES: readonly BranchScenario[] = [
  detailBranch('match loading', 'match page', {
    hold: { urlGlob: MATCH_URL, body: detailBody() },
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubPopulatedProfiles(page, PROFILES_RESPONSE)
    },
    // `MatchDetailPanel`'s own busy region is the one with the header in it; the analysis section's
    // busy region (`AnalysisTimeline loading`, rendered inside this page while the match loads) has
    // none, so a page that only has the analysis section loading does not have this mark.
    shows: [mark('busy match panel', 'main div[aria-busy="true"]:has(> header)'), SKELETON],
  }),
  detailBranch('match load failed', 'match page', {
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubPopulatedProfiles(page, PROFILES_RESPONSE)
      await failWith(page, MATCH_URL)
    },
    prepare: exhaustQueryRetries,
    shows: [
      exactText('match failure callout', 'We could not load this match'),
      control('Try again button', 'Try again', 2),
    ],
  }),
  detailBranch('match not found', 'match page', {
    stub: async (page) => {
      await stubMe(page, SIGNED_IN_ME)
      await stubPopulatedProfiles(page, PROFILES_RESPONSE)
      await failWith(page, MATCH_URL, 404, 'not_found')
    },
    prepare: exhaustQueryRetries,
    shows: [
      text('match not-found callout', 'This match could not be found.'),
      mark('Back to the match list link', 'main a:has-text("Back to the match list")'),
    ],
  }),
]

const ANALYSIS_SECTION_BRANCHES: readonly BranchScenario[] = [
  detailBranch('analysis document loading', 'analysis state', {
    hold: { urlGlob: ANALYSIS_URL, body: ANALYSIS_DOCUMENT },
    stub: (page) => stubDetailBody(page, detailBody({}, analysisSummary('published'))),
    shows: [
      mark('busy analysis section', 'main section[aria-busy="true"]:has-text("Match analysis")'),
      SKELETON,
      LOADED_MATCH_PANEL,
    ],
  }),
  detailBranch('analysis document failed', 'analysis state', {
    stub: async (page) => {
      await stubDetailBody(page, detailBody({}, analysisSummary('published')))
      await failWith(page, ANALYSIS_URL)
    },
    prepare: exhaustQueryRetries,
    shows: [
      text('analysis failure callout', "We could not load this match's analysis. Try again."),
      control('Try again button', 'Try again'),
      LOADED_MATCH_PANEL,
      absent('no match failure', 'main :text-is("We could not load this match")'),
    ],
  }),
  detailBranch('analysis takeover refused', 'analysis state', {
    stub: async (page) => {
      await stubDetailBody(page, detailBody({}, analysisSummary('queued')))
      await failWith(page, '**/api/analyze', 503, 'analysis_unavailable')
    },
    prepare: async (page) => {
      await waitQuietly(page.locator('main :text("Fixture failure.")'))
    },
    shows: [
      text('takeover refusal callout', 'Fixture failure.'),
      control('Try again button', 'Try again'),
    ],
  }),
]

function captureBranch(
  branch: string,
  overrides: Record<string, unknown>,
  shows: readonly ListExpectation[],
  me: unknown = SIGNED_IN_ME,
) {
  return detailBranch(branch, 'capture state', {
    stub: (page) => stubDetailBody(page, detailBody(overrides), me),
    shows,
  })
}

const UPLOAD_CONTROL = mark('upload control', 'main input[type="file"]')
const NO_UPLOAD_CONTROL = absent('no upload control', 'main input[type="file"]')

const CAPTURE_STATE_BRANCHES: readonly BranchScenario[] = [
  captureBranch(
    'capture pending',
    {
      capture_status: 'pending',
      capture_deadline_at: '2026-10-16T09:00:00Z',
      capture_object_held: null,
    },
    [
      exactText('catchable badge', 'Still catchable'),
      text('capture countdown', 'Captures automatically within'),
    ],
  ),
  captureBranch('capture failed', { capture_status: 'failed', capture_object_held: false }, [
    exactText('lost badge', 'Lost'),
    text('failure reason', 'We could not capture this replay after repeated attempts.'),
    UPLOAD_CONTROL,
  ]),
  captureBranch(
    'capture unavailable',
    { capture_status: 'unavailable', capture_object_held: false },
    [
      exactText('lost badge', 'Lost'),
      text('unavailable reason', 'The game never recorded this match.'),
      UPLOAD_CONTROL,
    ],
  ),
  captureBranch(
    'capture quarantined',
    { capture_status: 'quarantined', capture_object_held: true },
    [
      exactText('review badge', 'Needs review'),
      text('review reason', 'it failed validation'),
      NO_UPLOAD_CONTROL,
    ],
  ),
  captureBranch(
    'capture withdrawn, object not held',
    { capture_status: 'withdrawn', capture_object_held: false },
    [
      exactText('not-archived badge', 'Not archived'),
      text('withdrawn reason', 'Automatic capture ended for this match'),
      UPLOAD_CONTROL,
    ],
  ),
  captureBranch(
    'capture status unrecognised',
    { capture_status: 'mystery_status', capture_object_held: null },
    [exactText('unrecognised status badge', 'mystery_status'), NO_UPLOAD_CONTROL],
  ),
  captureBranch(
    'capture pending, archival objected',
    {
      capture_status: 'pending',
      capture_deadline_at: '2026-10-16T09:00:00Z',
      capture_object_held: null,
    },
    [
      exactText('not-archived badge', 'Not archived'),
      text('archival-off sentence', 'Archival is off for your account.'),
      absent('no countdown', 'main :text("Captures automatically within")'),
    ],
    OBJECTED_ME,
  ),
  captureBranch(
    'capture lost, archival objected',
    { capture_status: 'expired', capture_object_held: false },
    [
      exactText('lost badge', 'Lost'),
      text('lost reason', 'The replay existed, but we did not capture it in time.'),
      NO_UPLOAD_CONTROL,
    ],
    OBJECTED_ME,
  ),
]

// A recorded game whose download the server refused: the `303` back to this page carries the code.
function replayFailureBranch(branch: string, query: string, shows: readonly ListExpectation[]) {
  return detailBranch(branch, 'replay download refusal', {
    path: `/matches/${SAMPLE_GAME_ID}?${query}`,
    landedPath: `/matches/${SAMPLE_GAME_ID}`,
    stub: (page) => stubMatchDetailAnalysis(page, analysisSummary('published')),
    shows,
  })
}

const REPLAY_DOWNLOAD_BRANCHES: readonly BranchScenario[] = [
  replayFailureBranch(
    'replay download rate limited',
    `replay_error=rate_limited&replay_error_profile_id=${VIEWER_ID}&replay_error_retry_after=30`,
    [text('rate-limit message', 'You are downloading too quickly. Try again in 30 seconds.')],
  ),
  replayFailureBranch(
    'replay download refused',
    `replay_error=source_unavailable&replay_error_profile_id=${VIEWER_ID}`,
    [text('download failure message', 'We could not start that download. Try again.')],
  ),
  replayFailureBranch(
    'replay expired since page load',
    `replay_error=expired_since_page_load&replay_error_profile_id=${ALLY_ID}`,
    [
      text(
        'expired-while-viewing reason',
        'This recording expired while you were viewing this page.',
      ),
    ],
  ),
]

// A download is a same-tab navigation, so the page reads "Preparing your download…" until a
// 1.5-second timer in the container puts the button back (`handleDownload`,
// `handlePointOfViewDownload`): there is no completion signal to wait on. Two things keep that state
// on screen. The navigation is cancelled (`aborted` leaves the page where it is, whereas a held
// document request makes the page stop answering evaluations), and the page's clock is paused before
// the click, so the timer is registered on a clock that never reaches it. The same pause keeps a
// countdown or a label that a timer would change (`rate limited`, `upload in flight`) where the
// scenario put it.
async function pauseClock(page: Page): Promise<void> {
  const now = await page.evaluate(() => Date.now())
  await page.clock.pauseAt(now + 60_000)
}

const ROW_BUSY_BUTTON =
  'main section:has(> h3:text-is("Recorded games")) button[aria-busy="true"]:has-text("Preparing your download")'

function downloadBranch(
  branch: string,
  button: string,
  navigation: string,
  shows: readonly ListExpectation[],
) {
  return detailBranch(branch, undefined, {
    stub: async (page) => {
      await stubMatchDetailAnalysis(page, analysisSummary('published'))
      await page.route(navigation, (route) => route.abort('aborted'))
    },
    prepare: async (page) => {
      await pauseClock(page)
      await activate(page, page.getByRole('button', { name: button, exact: true }).first())
    },
    shows,
  })
}

// The two controls share a label and a spinner, so which one is busy is what tells the scenarios
// apart: the recorded-games list's row, or the button in the match header above it.
const DOWNLOAD_BRANCHES: readonly BranchScenario[] = [
  downloadBranch(
    'match download in flight',
    'Download replay',
    `**/api/replays/${SAMPLE_GAME_ID}/download*`,
    [
      busy('busy download button', 'Preparing your download'),
      SPINNER_IN_MAIN,
      absent('no busy row download', ROW_BUSY_BUTTON),
    ],
  ),
  downloadBranch(
    'replay download in flight',
    'Download',
    `**/api/matches/${SAMPLE_GAME_ID}/replays/*`,
    [mark('busy row download button', ROW_BUSY_BUTTON), SPINNER_IN_MAIN],
  ),
]

const UPLOAD_FILE = {
  name: 'MP Replay fixture.aoe2record',
  mimeType: 'application/octet-stream',
  buffer: Buffer.from('fixture replay bytes'),
}

async function chooseUploadFile(page: Page): Promise<void> {
  await page.locator('main input[type="file"]').setInputFiles(UPLOAD_FILE)
  await page.getByRole('button', { name: 'Upload and archive' }).waitFor({ state: 'visible' })
}

async function submitUpload(page: Page): Promise<void> {
  await chooseUploadFile(page)
  await activate(page, page.getByRole('button', { name: 'Upload and archive' }))
}

function uploadBranch(
  branch: string,
  answer: (page: Page) => Promise<void>,
  shows: readonly ListExpectation[],
  options: {
    hold?: HeldRequest
    submit?: boolean
    settle?: string
    afterSubmit?: (page: Page) => Promise<void>
    /** Pauses the page's clock before the file is chosen, so the label that turns from "Uploading…"
     * to "Checking the file…" after 1.2 seconds only turns when the scenario runs the clock. */
    pause?: boolean
  } = {},
) {
  const { hold, submit = true, settle, afterSubmit, pause = false } = options
  return detailBranch(branch, 'upload', {
    hold,
    stub: async (page) => {
      await stubDetailBody(
        page,
        detailBody({ capture_status: 'expired', capture_object_held: false }),
      )
      await answer(page)
    },
    prepare: async (page) => {
      if (pause) await pauseClock(page)
      if (submit) await submitUpload(page)
      else await chooseUploadFile(page)
      if (settle) await waitQuietly(page.locator(settle))
      await afterSubmit?.(page)
    },
    shows,
  })
}

const UPLOAD_BRANCHES: readonly BranchScenario[] = [
  uploadBranch(
    'upload file chosen',
    async () => {},
    [
      text('chosen file name', 'MP Replay fixture.aoe2record'),
      control('Upload and archive button', 'Upload and archive'),
      control('Remove button', 'Remove'),
    ],
    { submit: false },
  ),
  uploadBranch(
    'upload in flight',
    async () => {},
    [
      mark('busy upload form', 'main form[aria-busy="true"]'),
      busy('busy upload button', 'Uploading'),
      SPINNER_IN_MAIN,
    ],
    {
      hold: { urlGlob: UPLOAD_URL, body: { status: 'stored', source: 'manual' }, method: 'POST' },
      settle: 'main form[aria-busy="true"]',
      pause: true,
    },
  ),
  uploadBranch(
    'upload validating',
    async () => {},
    [
      mark('busy upload form', 'main form[aria-busy="true"]'),
      busy('busy upload button', 'Checking the file'),
      SPINNER_IN_MAIN,
    ],
    {
      hold: { urlGlob: UPLOAD_URL, body: { status: 'stored', source: 'manual' }, method: 'POST' },
      // The label turns from "Uploading…" to "Checking the file…" after 1.2 seconds
      // (`VALIDATING_LABEL_DELAY_MS`): the page's clock, paused above, is run past it.
      pause: true,
      afterSubmit: async (page) => {
        await page.clock.runFor(1_300)
      },
    },
  ),
  uploadBranch(
    'upload succeeded',
    (page) => respondJson(page, UPLOAD_URL, { status: 'stored', source: 'manual' }),
    [text('success callout', 'Archived from your upload.')],
    { settle: 'main :text("Archived from your upload.")' },
  ),
  uploadBranch(
    'upload not a replay',
    (page) => failWith(page, UPLOAD_URL, 422, 'invalid_replay'),
    [text('invalid-file callout', 'That file is not a replay we can read.')],
    { settle: 'main :text("That file is not a replay we can read.")' },
  ),
  uploadBranch(
    'upload wrong match',
    (page) => failWith(page, UPLOAD_URL, 404, 'not_found'),
    [text('wrong-match callout', 'This file could not be filed to this match.')],
    { settle: 'main :text("This file could not be filed to this match.")' },
  ),
  uploadBranch(
    'upload already archived',
    (page) => failWith(page, UPLOAD_URL, 409, 'already_archived'),
    [
      text('already-archived callout', 'This match already has an archived replay.'),
      control('Refresh button', 'Refresh'),
    ],
    { settle: 'main :text("This match already has an archived replay.")' },
  ),
  uploadBranch(
    'upload failed',
    (page) => failWith(page, UPLOAD_URL),
    [text('upload failure callout', 'The upload did not go through.')],
    { settle: 'main :text("The upload did not go through.")' },
  ),
]

// --- Unresolved fields: the empty branch of a match's map, civilisation, player and outcome ----------
//
// A map the source sent no name for, a civilisation this service's reference data cannot name and a
// player with no alias render `UnresolvedIdentifier`'s wording, not a blank gap (`match-history.md`
// §11.2). Every row of every list has populated fields, so none of the three met a suite.

function unresolvedMatches(viewerId: number) {
  return {
    matches: [
      {
        ...matchRow(555000301, 'win', 5, viewerId),
        map_name: null,
        civilisation: null,
        civilisation_name: null,
        participants: matchRow(555000301, 'win', 5, viewerId).participants.map((entry) => ({
          ...entry,
          alias: null,
          civ_name: null,
        })),
        opponents: [{ profile_id: OPPONENT_ID, alias: null, civ_id: 6, civ_name: null }],
      },
      // A match with no recorded result and no rating: the outcome reads "Unknown", and the row has
      // no rating figure at all (`match-history.md` §12.4).
      {
        ...matchRow(555000302, 'win', 0, viewerId),
        result: null,
        rating: null,
        rating_diff: null,
      },
    ],
    next_cursor: null,
  }
}

const UNRESOLVED_LIST_MARKS: readonly ListExpectation[] = [
  exactText('unknown outcome', 'Unknown'),
  text('unknown map', 'Unknown map'),
  text('unknown civilisation', 'Unknown civilisation'),
  text('unknown player', 'Unknown player'),
]
const UNRESOLVED_DETAIL_MARKS: readonly ListExpectation[] = [
  text('unresolved map', 'Map — unresolved'),
  text('unresolved civilisation id', 'Civilisation ID 1'),
  text('unknown player', 'Unknown player'),
]

const UNRESOLVED_BRANCHES: readonly BranchScenario[] = [
  listBranch(
    OWN_MATCHES,
    'unresolved fields',
    (page) => respondJson(page, OWN_MATCHES.glob, unresolvedMatches(VIEWER_ID)),
    UNRESOLVED_LIST_MARKS,
  ),
  listBranch(
    PLAYER_MATCHES,
    'unresolved fields',
    (page) => respondJson(page, PLAYER_MATCHES.glob, unresolvedMatches(THIRD_PARTY_PROFILE_ID)),
    UNRESOLVED_LIST_MARKS,
  ),
  detailBranch('unresolved fields', undefined, {
    stub: (page) =>
      stubDetailBody(
        page,
        detailBody({
          map_name: null,
          participants: MATCH_DETAIL_POPULATED.participants.map((entry) => ({
            ...entry,
            alias: null,
            civ_name: null,
          })),
        }),
      ),
    shows: UNRESOLVED_DETAIL_MARKS,
  }),
]

const ENUMERATED_BRANCHES: readonly BranchScenario[] = [
  ...SIGN_IN_BRANCHES,
  ...SEARCH_BRANCHES,
  ...FAVOURITES_BRANCHES,
  ...SUMMARY_BRANCHES,
  ...MATCH_LIST_BRANCHES,
  ...CAPTURE_LIST_BRANCHES,
  ...MAKE_PRIMARY_BRANCHES,
  ...DASHBOARD_ACTION_BRANCHES,
  ...FAVOURITE_TOGGLE_BRANCHES,
  ...PRIVACY_BRANCHES,
  ...OBJECT_BRANCHES,
  ...MATCH_PAGE_BRANCHES,
  ...ANALYSIS_SECTION_BRANCHES,
  ...CAPTURE_STATE_BRANCHES,
  ...REPLAY_DOWNLOAD_BRANCHES,
  ...UPLOAD_BRANCHES,
  ...DOWNLOAD_BRANCHES,
  ...UNRESOLVED_BRANCHES,
]

// The per-route branch inventory, by `ROUTE_SCENARIOS` label: every error, transient (in flight or
// held) and empty branch the route's containers and the design-system screens and composites they
// render can show, enumerated from the code, and reachable through the route's own stubs. It is
// checked both ways (`suite-scenarios.test.ts`): a name here with no scenario of that route fails
// by name, and a scenario this does not list fails too.
//
// What is not here, and why each has nothing for a route suite to reach or judge (a branch added to
// the source that fits none of these is a gap, and belongs in the inventory):
// - the root `pendingComponent` and `errorComponent` (`apps/web/src/routes/__root.tsx`): a line of
//   text with no `<main>`, no interactive element and no motion, so the keyboard, focus-visibility,
//   touch-footprint and reduced-motion suites have nothing to measure, and the scenario navigation
//   (`gotoScenario`) waits for the `<main>` it does not render;
// - states no container sets: `SignInScreen`'s `returning` and `unavailable` phases
//   (`SignInContainer` passes `default` or `leaving`), `ArchivalControl`'s `loading` and
//   `unavailable` props, `MatchDetailPanel`'s download `error`, `AnalysisTimeline`'s `requesting`,
//   `ProfileSummary`'s `not-found` on the two self routes, `FavouritesList`'s signed-out state;
// - the signed-out branch of every authenticated route and `PrivacyContainer`'s pending-session
//   line: the route's `beforeLoad` redirects before the container renders, with the session cached;
// - `/matches`' make-primary: the Manage menu that triggers it is `board` only (`ProfileSummary`
//   `!compact`), and `/matches` renders the `compact` variant;
// - a second path to a state already covered, which renders what the covered scenario's marks
//   declare (a unit check fails when one scenario's positive marks are all another's, so these
//   cannot be added as twins): the export's poll failure and its ten-second ceiling end in `failed`;
//   a failed re-mint of the erasure token ends in the `failed` dialog with the acknowledgement still
//   ticked, which is the render of a failed erase (`erasure failed`); an unreadable analysis summary
//   (the match response lacks the `analysis` key) renders the same `AnalysisTimeline error` callout
//   as a failed analysis document (`AnalysisContainer`, the `summaryShapeError` and
//   `documentQuery.isError` branches), the two differing only in which request failed; an invalid
//   game id in the URL renders the not-found panel without a request; an unknown `?error=` code and
//   `provider_unavailable` render the `unreachable` outcome; the optimistic "running" after "Request
//   analysis" renders the `running` state, and that request's own failure is swallowed
//   (`handleRequestAnalysis`), so the page shows what the next poll reads;
// - a pointer-gesture or hover state (`UploadControl`'s drag-over, every hover and active style):
//   judged per component by the stories (`scripts/checks/state-coverage.mjs`), not by data.
export const ROUTE_REQUIRED_BRANCHES: Readonly<Record<string, readonly string[]>> = {
  '/sign-in': [
    'outcome no_aoe2_profile',
    'outcome not_allowlisted',
    'outcome steam_assertion_invalid',
    'outcome unreachable',
    'outcome profile_already_linked',
    'link variant',
    'steam redirect in flight',
  ],
  '/dashboard': [
    'profile summary loading',
    'profile load failed',
    'profile stale',
    'ratings empty',
    'rating unranked',
    'no linked account',
    'archival write in flight',
    'archival just resumed',
    'archival write failed',
    'archival resume in flight',
    'archival resume failed',
    'make primary in flight',
    'make primary failed',
    'sign-out in flight',
    'sign-out failed',
    'unlink check in flight',
    'unlink check failed',
    'unlink in flight',
    'unlink failed',
  ],
  '/search': [
    'searching',
    'no results',
    'no results, degraded',
    'results, degraded',
    'rate limited',
    'rate limit elapsed',
    'search failed',
  ],
  '/favourites': ['loading', 'load failed', 'removal in flight', 'removal failed'],
  '/matches': [
    'no linked account',
    'profile load failed',
    'profile stale',
    'ratings empty',
    'rating unranked',
    'profile loading',
    'match list loading',
    'match list load failed',
    'capture statuses',
    'capture statuses, archival objected',
    'unresolved fields',
  ],
  '/matches/$gameId': [
    'no linked account',
    'match loading',
    'match load failed',
    'match not found',
    'analysis queued',
    'analysis running',
    'analysis failed',
    'analysis unavailable',
    'analysis document loading',
    'analysis document failed',
    'analysis takeover refused',
    'capture pending',
    'capture failed',
    'capture unavailable',
    'capture quarantined',
    'capture withdrawn, object not held',
    'capture status unrecognised',
    'capture pending, archival objected',
    'capture lost, archival objected',
    'replay download rate limited',
    'replay download refused',
    'replay expired since page load',
    'match download in flight',
    'replay download in flight',
    'upload file chosen',
    'upload in flight',
    'upload validating',
    'upload succeeded',
    'upload not a replay',
    'upload wrong match',
    'upload already archived',
    'upload failed',
    'unresolved fields',
  ],
  '/players/$profileId': [
    'profile loading',
    'profile load failed',
    'profile stale',
    'ratings empty',
    'rating unranked',
    'player not found',
    'favourite add in flight',
    'favourites limit reached',
    'favourite add failed',
    'favourite remove in flight',
    'favourite remove failed',
  ],
  '/players/$profileId/matches': [
    'profile loading',
    'profile load failed',
    'profile stale',
    'ratings empty',
    'rating unranked',
    'player not found',
    'match list loading',
    'match list load failed',
    'unresolved fields',
  ],
  '/privacy': [
    'export requesting',
    'export preparing',
    'export failed',
    'archival write in flight',
    'archival just resumed',
    'archival write failed',
    'archival resume in flight',
    'archival resume failed',
    'erase button minting',
    'erasure confirmation minting failed',
    'erasure in flight',
    'erasure confirmation expired',
    'erasure re-mint in flight',
    'erasure failed',
    'account erased',
  ],
  '/object': [
    'invalid profile id',
    'objection submitting',
    'objection recorded',
    'objection rate limited',
    'objection failed',
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
  timeout?: number,
): Promise<void> {
  for (const mark of scenario.shows) {
    const selector = await selectorFor(page, mark)
    const count = () => page.locator(selector).count()
    const notShowing = `the route is not showing its '${scenario.branch}' branch`
    await expect
      .poll(count, {
        message:
          `${context}: ${mark.name} (${selector}) rendered fewer than ${mark.min} item(s) — ` +
          notShowing,
        timeout,
      })
      .toBeGreaterThanOrEqual(mark.min)
    if (mark.max !== undefined) {
      await expect
        .poll(count, {
          message:
            `${context}: ${mark.name} (${selector}) rendered more than ${mark.max} item(s) — ` +
            notShowing,
          timeout,
        })
        .toBeLessThanOrEqual(mark.max)
    }
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
    // The failed profile page also has a skeleton (the identity bar's) and a busy region, so the
    // failure callout's absence is what makes this the held request.
    shows: [
      { name: 'skeleton', selector: `main ${LOOP_SELECTOR.skeleton}`, min: 1 },
      absent('no ratings failure', 'main :text("We could not load your ratings")'),
    ],
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
  ...ENUMERATED_BRANCHES,
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
  /** How long a declared mark may take to appear before the scenario fails (default: the
   * `expect` timeout). The planted-absence tests shorten it: a failure is the expected result
   * there, and waiting out the default for each of them adds minutes. */
  judgeTimeoutMs?: number
  /** Runs after `prepare` and before the marks are judged. The planted-absence tests wait here for a
   * positive sign that the page they put in the scenario's place has rendered. */
  beforeJudge?: (page: Page) => Promise<void>
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
  watchApiResponses(page)
  await installSteamAvatarStub(page)
  if (options.reducedMotion) await page.emulateMedia({ reducedMotion: 'reduce' })
  await seedThemeOverride(page, theme)
  await scenario.stub(page)
  const held = scenario.hold
    ? await holdRequests(page, scenario.hold.urlGlob, scenario.hold.body, scenario.hold.method)
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
  await options.beforeJudge?.(page)
  if (isBranchScenario(scenario)) {
    await assertBranchScenario(page, scenario, scenario.label, options.judgeTimeoutMs)
  }
  return { ...external, release: async () => held?.release() }
}
