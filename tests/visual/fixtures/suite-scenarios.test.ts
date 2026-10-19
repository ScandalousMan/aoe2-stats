// T676: what keeps the scenarios the four route suites run honest, in the way
// `app-routes-harness.test.ts` keeps `ROUTE_SCENARIOS` honest against the router. Five properties,
// each with its absence case planted rather than assumed (every guard below is a function the real
// check and its planted case both call, so the two cannot drift):
//
// 1. every entry of the per-route list inventory in `./suite-scenarios` is declared by a populated
//    scenario of *that route* (exact match, never a label prefix), and in a browser each populated
//    scenario renders what it declares and shows no error callout or loading region, judged inside
//    `enterScenario` so the four route suites cannot skip it. The inventory also holds (T682) the
//    two success-branch controls that are not lists: the `objected` `ArchivalControl` on
//    `/dashboard` and `/privacy`, and `DataExportPanel`'s `ready` download link on `/privacy`;
// 2. no fixture player carries an `avatar_hash` (constitution III: no suite reaches
//    `avatars.steamstatic.com`);
// 3. every `<Menu>` and `<Dialog>` an application route can open has a scenario — a new consumer
//    fails here until someone adds one;
// 4. scenario labels are unique (they are Playwright test titles);
// 5. every surface scenario knows how to open its surface;
// 6. (T681) every route that renders a `Tooltip` through the `ProfileSummary` chain has a tooltip
//    scenario. Two levels live here: the source is read for `<Tooltip`, `<CountryFlag` and
//    `<ProfileSummary`, so a usage in a file no table entry names fails; and the route files are
//    read for the containers they import, so a new route importing a container that renders a
//    `ProfileSummary` fails until it has a scenario. A third level lives at runtime, in
//    `./tooltip-open`: a second tooltip trigger in `main` fails the scenario, counted once, as
//    rendered when the first trigger attaches. Not caught by any level: a tooltip that renders only in a populated
//    list (a `<Tooltip>` in `MatchRow`, whose at-rest `/matches` list is empty) — the source level
//    fails on it but a table entry naming `/matches` satisfies it — and a route that reaches a
//    container through another component rather than importing it, through a default import or a
//    lazy `import()`, or from a nested route directory (the derivation reads braced named imports
//    in the flat `apps/web/src/routes/` directory only).
// 7. (T744) every error, transient (in flight or held) and empty branch of every route that a
//    route's own stubs can reach has a branch scenario of *that route* (`ROUTE_REQUIRED_BRANCHES`,
//    exact match, and the number of them pinned), every one is in `SUITE_SCENARIOS` so all four
//    suites run it, no two scenarios of a route declare the same marks, each scenario's first mark
//    is a positive one, and in a browser each renders the branch it names. The planted absences
//    that show each mark can fail are described above the browser section below.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'
import { expect, type Page, test } from '@playwright/test'
import {
  createAppServerHarness,
  hasBuild,
  fulfillJson,
  PLAYER_PROFILE_RESPONSE,
  PROFILES_RESPONSE,
  ROUTE_SCENARIOS,
  type RouteScenario,
  SAMPLE_GAME_ID,
  SIGNED_IN_ME,
  stubMe,
} from './app-routes-harness'
import {
  apiResponses,
  assertBranchScenario,
  assertPopulatedScenario,
  type BranchScenario,
  BRANCH_SCENARIOS,
  type HeldRequest,
  type ListExpectation,
  enterScenario,
  findAvatarHashes,
  LOADING_SCENARIOS,
  NO_LINKED_ME,
  EXPORT_DOWNLOAD_PATH,
  OBJECTED_ME,
  POPULATED_FIXTURES,
  POPULATED_SCENARIOS,
  type PopulatedScenario,
  ROUTE_REQUIRED_BRANCHES,
  ROUTE_REQUIRED_LISTS,
  SUITE_SCENARIOS,
  type SuiteScenario,
  SURFACE_SCENARIOS,
  type TooltipScenario,
  TOOLTIP_SCENARIOS,
  unmetBranches,
  unpopulatedLists,
} from './suite-scenarios'

const rootDir = path.resolve(__dirname, '..', '..', '..')

// Routes whose body holds no list and no success-branch control: nothing to populate. `/privacy`
// is not here since T682: it holds the `objected` `ArchivalControl` and the export's `ready` link.
const ROUTES_WITHOUT_A_LIST: ReadonlySet<string> = new Set([
  '/sign-in',
  '/privacy-notice',
  '/object',
])

function without(label: string): PopulatedScenario[] {
  const kept = POPULATED_SCENARIOS.filter((scenario) => scenario.label !== label)
  expect(kept.length, `no populated scenario is labelled '${label}'`).toBe(
    POPULATED_SCENARIOS.length - 1,
  )
  return kept
}

function duplicateLabels(scenarios: ReadonlyArray<{ label: string }>): string[] {
  const labels = scenarios.map((scenario) => scenario.label)
  return labels.filter((label, index) => labels.indexOf(label) !== index)
}

function surfaceScenariosWithoutPrepare(scenarios: readonly SuiteScenario[]): string[] {
  return scenarios
    .filter((scenario) => !scenario.prepare || !scenario.surface)
    .map((scenario) => scenario.label)
}

test.describe('suite scenarios', () => {
  test('every route that renders a list has a populated scenario for each of its lists', () => {
    const missing = unpopulatedLists(POPULATED_SCENARIOS)
    expect(
      missing,
      `list(s) no populated scenario of their own route declares: ${missing.join(', ')}`,
    ).toEqual([])
  })

  test('the route inventory covers every route, and only routes', () => {
    const routes = ROUTE_SCENARIOS.map((scenario) => scenario.label)
    const unaccounted = routes.filter(
      (route) => !ROUTES_WITHOUT_A_LIST.has(route) && !(route in ROUTE_REQUIRED_LISTS),
    )
    expect(
      unaccounted,
      `route(s) in neither ROUTE_REQUIRED_LISTS nor ROUTES_WITHOUT_A_LIST`,
    ).toEqual([])
    const stray = [...Object.keys(ROUTE_REQUIRED_LISTS), ...ROUTES_WITHOUT_A_LIST].filter(
      (route) => !routes.includes(route),
    )
    expect(stray, 'inventory entries naming a route ROUTE_SCENARIOS does not have').toEqual([])
    const overlap = [...ROUTES_WITHOUT_A_LIST].filter((route) => route in ROUTE_REQUIRED_LISTS)
    expect(overlap, 'a route is both "has no list" and has required lists').toEqual([])
  })

  test('every populated scenario names a real route and only lists its route requires', () => {
    for (const scenario of POPULATED_SCENARIOS) {
      expect(
        ROUTE_SCENARIOS.map((route) => route.label),
        `${scenario.label}: route '${scenario.route}' is not a ROUTE_SCENARIOS label`,
      ).toContain(scenario.route)
      expect(scenario.label).toBe(`${scenario.route} (${scenario.variant})`)
      const required = ROUTE_REQUIRED_LISTS[scenario.route] ?? []
      const undeclared = scenario.renders
        .map((entry) => entry.name)
        .filter((name) => !required.includes(name))
      expect(
        undeclared,
        `${scenario.label} renders list(s) ROUTE_REQUIRED_LISTS does not know: ${undeclared.join(', ')}`,
      ).toEqual([])
    }
  })

  // The planted absence cases for property 1. Each removal must fail by naming what is lost.
  test('removing /matches (populated) is caught, though /matches/$gameId still starts with it', () => {
    const missing = unpopulatedLists(without('/matches (populated)'))
    expect(missing).toEqual(['/matches: match rows', '/matches: match row links'])
  })

  test('removing /players/$profileId (favourited) is caught, though its matches route starts with it', () => {
    const missing = unpopulatedLists(without('/players/$profileId (favourited)'))
    expect(missing).toEqual([
      '/players/$profileId: rating rows',
      '/players/$profileId: unfavourite toggle',
    ])
  })

  test('a longer route sharing a prefix and a list name does not stand in for the shorter one', () => {
    // The old guard used `label.startsWith(route)`, so `/matches/$gameId (populated)` satisfied
    // `/matches` and `/players/$profileId/matches (populated)` satisfied `/players/$profileId`.
    // Here the longer route even declares the very list name the shorter one needs.
    const stand: PopulatedScenario = {
      ...POPULATED_SCENARIOS[0],
      route: '/matches/$gameId',
      variant: 'populated',
      label: '/matches/$gameId (populated)',
      renders: [{ name: 'match rows', selector: 'main table tbody tr', min: 1 }],
    }
    expect(unpopulatedLists([stand], { '/matches': ['match rows'] })).toEqual([
      '/matches: match rows',
    ])
    expect(
      unpopulatedLists([{ ...stand, route: '/matches', label: '/matches (populated)' }], {
        '/matches': ['match rows'],
      }),
    ).toEqual([])
  })

  test('the guard is per list: removing the stale variant loses only its Recompute button', () => {
    expect(unpopulatedLists(without('/matches/$gameId (analysis stale)'))).toEqual([
      '/matches/$gameId: Recompute button',
    ])
    expect(unpopulatedLists(without('/matches/$gameId (analysis absent, capture lost)'))).toEqual([
      '/matches/$gameId: Request analysis button',
      '/matches/$gameId: upload control',
    ])
  })

  test('contrast: removing a scenario whose lists are declared elsewhere loses nothing', () => {
    // Two scenarios declare the roster and the analysis lists; only `(populated)` declares the
    // download buttons, so exactly that one list is lost.
    expect(unpopulatedLists(without('/matches/$gameId (populated)'))).toEqual([
      '/matches/$gameId: replay download buttons',
    ])
    expect(unpopulatedLists(POPULATED_SCENARIOS)).toEqual([])
  })

  test("the dashboard's declared lists are the data-driven ones only", () => {
    // `main ul > li` on the dashboard matched the archival explanation's static copy, which renders
    // whatever the data is, so declaring it proved nothing. The two `objected` entries (T682) are
    // controls that exist only when `archival_objected` is true, so they prove the data arrived.
    expect(ROUTE_REQUIRED_LISTS['/dashboard']).toEqual([
      'rating rows',
      'Resume archival button',
      'objected callout',
    ])
    const dashboard = POPULATED_SCENARIOS.find(
      (scenario) => scenario.label === '/dashboard (two linked profiles)',
    )
    expect(dashboard?.renders.map((entry) => entry.name)).toEqual(['rating rows'])
  })

  // T682: the planted absence cases for the two success-branch controls. Each removal must fail by
  // naming what is lost, on the route that loses it and not on the other one.
  test('removing the objected dashboard scenario is caught, and /privacy still has its own', () => {
    expect(unpopulatedLists(without('/dashboard (archival objected)'))).toEqual([
      '/dashboard: Resume archival button',
      '/dashboard: objected callout',
    ])
  })

  test('removing the objected privacy scenario is caught, and the dashboard one does not stand in', () => {
    expect(unpopulatedLists(without('/privacy (archival objected)'))).toEqual([
      '/privacy: Resume archival button',
      '/privacy: objected callout',
    ])
  })

  test('removing the export-ready scenario is caught', () => {
    expect(unpopulatedLists(without('/privacy (export ready)'))).toEqual([
      '/privacy: export download link',
    ])
  })

  test('the objected fixture is objected, with a timestamp, and the export link is same-origin', () => {
    expect(OBJECTED_ME.archival_objected).toBe(true)
    expect(OBJECTED_ME.archival_objected_at).not.toBeNull()
    // Same-origin: a path on the application's own host, never an absolute URL or a `//host` one.
    expect(EXPORT_DOWNLOAD_PATH.startsWith('/') && !EXPORT_DOWNLOAD_PATH.startsWith('//')).toBe(
      true,
    )
    const exportReady = POPULATED_SCENARIOS.find(
      (scenario) => scenario.label === '/privacy (export ready)',
    )
    // It is a flow, not a state the page lands in: `prepare` must request the export.
    expect(exportReady?.prepare).toBeDefined()
    expect(exportReady?.listsNeedPrepare).toBe(true)
  })

  test('every T682 scenario is in SUITE_SCENARIOS, so all four route suites run it', () => {
    const labels = SUITE_SCENARIOS.map((scenario) => scenario.label)
    expect(labels).toEqual(
      expect.arrayContaining([
        '/dashboard (archival objected)',
        '/privacy (archival objected)',
        '/privacy (export ready)',
      ]),
    )
  })

  test('the populated fixtures are populated', () => {
    expect(POPULATED_FIXTURES.profiles.profiles.length).toBeGreaterThan(1)
    expect(POPULATED_FIXTURES.matches.matches.length).toBeGreaterThan(1)
    expect(POPULATED_FIXTURES.playerMatches.matches.length).toBeGreaterThan(1)
    expect(POPULATED_FIXTURES.favourites.favourites.length).toBeGreaterThan(1)
    expect(POPULATED_FIXTURES.search.results.length).toBeGreaterThan(1)
    // One participant per replay availability the detail panel renders.
    expect(
      new Set(
        POPULATED_FIXTURES.matchDetail.participants.map((entry) => entry.replay.availability),
      ),
    ).toEqual(new Set(['archived', 'obtainable', 'expired', 'never_recorded']))
    // The match page carries an analysis summary and a document for every participant on it.
    expect(POPULATED_FIXTURES.matchDetail.analysis.state).toBe('published')
    expect(
      POPULATED_FIXTURES.analysisDocument.participants.map((entry) => entry.profile_id).sort(),
    ).toEqual(POPULATED_FIXTURES.matchDetail.participants.map((entry) => entry.profile_id).sort())
  })

  test('no fixture player carries an avatar_hash', () => {
    const offenders = [
      ...findAvatarHashes(POPULATED_FIXTURES),
      ...findAvatarHashes(PLAYER_PROFILE_RESPONSE, '$.playerProfile'),
    ]
    expect(
      offenders,
      `a fixture player with an avatar_hash makes PlayerAvatar request avatars.steamstatic.com: ${offenders.join(', ')}`,
    ).toEqual([])
  })

  test('the avatar-hash check itself catches a planted hash, nested, and ignores null', () => {
    expect(findAvatarHashes({ a: [{ b: { avatar_hash: null } }] })).toEqual([])
    expect(
      findAvatarHashes({ results: [{ profile_id: 1 }, { profile_id: 2, avatar_hash: 'abc123' }] }),
    ).toEqual(['$.results[1].avatar_hash'])
  })

  test('scenario labels are unique, and a planted duplicate is caught', () => {
    expect(duplicateLabels(SUITE_SCENARIOS)).toEqual([])
    expect(duplicateLabels([{ label: 'a' }, { label: 'b' }, { label: 'a' }])).toEqual(['a'])
  })

  test('every surface scenario opens its own surface, and a planted one that does not is caught', () => {
    expect(surfaceScenariosWithoutPrepare(SURFACE_SCENARIOS)).toEqual([])
    const [first] = SURFACE_SCENARIOS
    expect(
      surfaceScenariosWithoutPrepare([
        { ...first, label: 'no prepare', prepare: undefined },
        { ...first, label: 'no surface', surface: undefined },
        first,
      ]),
    ).toEqual(['no prepare', 'no surface'])
  })

  // --- T744: the branch inventory ---------------------------------------------------------------

  function withoutBranch(label: string): BranchScenario[] {
    const kept = BRANCH_SCENARIOS.filter((scenario) => scenario.label !== label)
    expect(kept.length, `no branch scenario is labelled '${label}'`).toBe(
      BRANCH_SCENARIOS.length - 1,
    )
    return kept
  }

  test('every route that renders a named branch has a scenario for each of its branches', () => {
    const missing = unmetBranches(BRANCH_SCENARIOS)
    expect(
      missing,
      `branch(es) no scenario of their own route declares: ${missing.join(', ')}`,
    ).toEqual([])
  })

  test('every branch scenario names a real route and a branch its route requires', () => {
    for (const scenario of BRANCH_SCENARIOS) {
      expect(
        ROUTE_SCENARIOS.map((route) => route.label),
        `${scenario.label}: route '${scenario.route}' is not a ROUTE_SCENARIOS label`,
      ).toContain(scenario.route)
      expect(scenario.label).toBe(`${scenario.route} (${scenario.branch})`)
      expect(
        ROUTE_REQUIRED_BRANCHES[scenario.route] ?? [],
        `${scenario.label}: ROUTE_REQUIRED_BRANCHES does not list this branch`,
      ).toContain(scenario.branch)
      expect(scenario.shows.length, `${scenario.label} declares nothing it shows`).toBeGreaterThan(
        0,
      )
    }
    expect(
      Object.keys(ROUTE_REQUIRED_BRANCHES).filter(
        (route) => !ROUTE_SCENARIOS.some((scenario) => scenario.label === route),
      ),
      'inventory entries naming a route ROUTE_SCENARIOS does not have',
    ).toEqual([])
  })

  // The planted absence cases for the inventory, one per scenario: each removal fails by naming the
  // route and the branch that is lost, and only that one — a sibling of the same route, or the same
  // branch on another route, never stands in.
  for (const scenario of BRANCH_SCENARIOS) {
    test(`removing ${scenario.label} is caught by name`, () => {
      expect(unmetBranches(withoutBranch(scenario.label))).toEqual([
        `${scenario.route}: ${scenario.branch}`,
      ])
    })
  }

  test('every branch scenario is in SUITE_SCENARIOS, so all four route suites run it', () => {
    const labels = new Set(SUITE_SCENARIOS.map((scenario) => scenario.label))
    expect(
      BRANCH_SCENARIOS.filter((scenario) => !labels.has(scenario.label)).map((s) => s.label),
    ).toEqual([])
  })

  test('the two held loading states are branch scenarios, so all four suites measure them held', () => {
    expect(LOADING_SCENARIOS.map((scenario) => scenario.label)).toEqual([
      '/dashboard (profile summary loading)',
      '/privacy (erase button minting)',
    ])
    for (const scenario of LOADING_SCENARIOS) {
      expect(BRANCH_SCENARIOS).toContain(scenario)
      expect(scenario.hold.urlGlob).not.toBe('')
    }
  })

  // A defect a scenario is known to show is asserted by its message (`expectKnownDefect`, shown both
  // ways in `known-defect.test.ts`). Pin which scenarios carry the marker, so one added to quiet a
  // red walk is a visible change; one left behind after a fix fails the keyboard suite itself.
  test('exactly the two in-flight dialogs carry a known keyboard defect', () => {
    const marked = SUITE_SCENARIOS.filter((scenario) => scenario.knownDefects !== undefined)
    expect(marked.map((scenario) => scenario.label)).toEqual([
      '/dashboard (unlink in flight)',
      '/privacy (erasure in flight)',
    ])
    for (const scenario of marked) {
      expect(Object.keys(scenario.knownDefects ?? {})).toEqual(['keyboard'])
      expect(scenario.surface, `${scenario.label}: a keyboard defect is a surface walk`).toBe(
        'dialog',
      )
    }
  })

  // The number the prose says (quickstart.md, production-readiness item 13, T744): change it here
  // and there together, or this fails.
  test('there are exactly 121 branch scenarios', () => {
    expect(BRANCH_SCENARIOS).toHaveLength(121)
  })

  // A scenario can be told from another of its route when its marks do not all hold on the other's
  // page. The marks are declared selectors, so this is a check on the declarations, and what it
  // guarantees is exactly this: on one route, no scenario's *positive* marks (those that must be
  // present) are all among another's *as written* (the same selector string, and the other asks for
  // at least as many), unless an *absent* mark of the first (one that must not be present) has a
  // selector the other requires present. That exception is what separates them: the other's page
  // has the thing the first says is not there. What it does not see: two selectors spelled
  // differently that match the same element (`main [aria-busy="true"]` and
  // `main section[aria-busy="true"]:has-text("Match analysis")` match the same section) are two
  // marks to it, so scenarios whose marks overlap that way are covered only by the discriminating
  // marks listed in `MARKS_THAT_SEPARATE` and the ring plants, which a sweep of the scenarios named
  // there added, not by this check. Whether a declared mark really is present on the other's page
  // is what the planted cases below run.
  const positiveMarks = (scenario: BranchScenario) =>
    scenario.shows.filter((entry) => entry.max === undefined)
  const absentMarks = (scenario: BranchScenario) =>
    scenario.shows.filter((entry) => entry.max !== undefined)

  /** Ordered pairs of scenarios of one route where the first is not told apart from the second. */
  function notToldApart(scenarios: readonly BranchScenario[]): string[] {
    const pairs: string[] = []
    for (const first of scenarios) {
      for (const second of scenarios) {
        if (first === second || first.route !== second.route) continue
        const heldBySecond = positiveMarks(first).every((mark) =>
          positiveMarks(second).some(
            (other) => other.selector === mark.selector && other.min >= mark.min,
          ),
        )
        const separatedByAbsence = absentMarks(first).some((gone) =>
          positiveMarks(second).some((other) => other.selector === gone.selector),
        )
        if (heldBySecond && !separatedByAbsence) {
          pairs.push(`${first.route}: '${first.branch}' is not told apart from '${second.branch}'`)
        }
      }
    }
    return pairs
  }

  test('no branch scenario is told apart from another of its route only by what the other lacks', () => {
    expect(notToldApart(BRANCH_SCENARIOS)).toEqual([])
  })

  test('the twin check catches a duplicate and a subset, and allows a pair an absent mark separates', () => {
    const [first] = BRANCH_SCENARIOS
    const mark = (selector: string, min = 1) => ({ name: selector, selector, min })
    const scenario = (branch: string, shows: ListExpectation[]): BranchScenario => ({
      ...first,
      branch,
      label: branch,
      shows,
    })
    const wide = scenario('wide', [mark('a'), mark('b')])
    // The same marks: each is held by the other.
    expect(notToldApart([wide, scenario('twin', [mark('a'), mark('b')])])).toEqual([
      `${first.route}: 'wide' is not told apart from 'twin'`,
      `${first.route}: 'twin' is not told apart from 'wide'`,
    ])
    // A subset: the narrow one is held by the wide one, the wide one is not held by the narrow one.
    expect(notToldApart([wide, scenario('narrow', [mark('a')])])).toEqual([
      `${first.route}: 'narrow' is not told apart from 'wide'`,
    ])
    // A mark that asks for more than the other shows is not held by it.
    expect(
      notToldApart([scenario('one', [mark('a', 1)]), scenario('two', [mark('a', 2)])]),
    ).toEqual([`${first.route}: 'one' is not told apart from 'two'`])
    // Separated by an absent mark the other requires present: allowed.
    const gone = { name: 'no b', selector: 'b', min: 0, max: 0 }
    expect(notToldApart([wide, scenario('narrow, without b', [mark('a'), gone])])).toEqual([])
    // An absent mark on a selector the other does not require present separates nothing.
    const elsewhere = { name: 'no c', selector: 'c', min: 0, max: 0 }
    expect(notToldApart([wide, scenario('narrow, without c', [mark('a'), elsewhere])])).toEqual([
      `${first.route}: 'narrow, without c' is not told apart from 'wide'`,
    ])
    // The same marks on another route are no clash: a branch is judged on its own route.
    expect(
      notToldApart([wide, { ...scenario('twin', [mark('a'), mark('b')]), route: '/else' }]),
    ).toEqual([])
  })

  // `assertBranchScenario` judges the marks in order and a `max` mark on the first would pass on a
  // page that shows nothing at all; and the planted case for an absent mark relies on the marks
  // before it having proved the page is the right one.
  function firstMarkNotPositive(scenarios: readonly BranchScenario[]): string[] {
    return scenarios
      .filter((scenario) => scenario.shows[0].min < 1 || scenario.shows[0].max !== undefined)
      .map((scenario) => scenario.label)
  }

  test('every branch scenario opens with a positive mark, and a planted one that does not is caught', () => {
    expect(firstMarkNotPositive(BRANCH_SCENARIOS)).toEqual([])
    const [first] = BRANCH_SCENARIOS
    const absentFirst = {
      ...first,
      label: 'absent first',
      shows: [{ name: 'gone', selector: 'x', min: 0, max: 0 }],
    }
    expect(firstMarkNotPositive([first, absentFirst])).toEqual(['absent first'])
  })

  test('every absent mark has a page it is shown present on, and every such page exists', () => {
    const labels = new Set(BRANCH_SCENARIOS.map((scenario) => scenario.label))
    const wanted = BRANCH_SCENARIOS.flatMap((scenario) =>
      scenario.shows
        .filter((entry) => entry.max !== undefined)
        .map((entry) => `${scenario.label}|${entry.name}`),
    )
    expect(
      wanted.filter((key) => !(key in PRESENCE_PAGE_FOR)),
      'absent mark(s) with no page they are shown present on',
    ).toEqual([])
    expect(
      Object.keys(PRESENCE_PAGE_FOR).filter((key) => !wanted.includes(key)),
      'presence page(s) for an absent mark no scenario declares',
    ).toEqual([])
    const sites = new Set([...ROUTE_SCENARIOS, ...POPULATED_SCENARIOS].map((entry) => entry.label))
    expect(
      Object.values(PRESENCE_PAGE_FOR).filter((label) => !labels.has(label) && !sites.has(label)),
      'presence page(s) that are no scenario',
    ).toEqual([])
  })

  test('every separating mark is a positive mark of a real scenario and its twin is on the same route', () => {
    const byLabel = new Map(BRANCH_SCENARIOS.map((scenario) => [scenario.label, scenario]))
    for (const entry of MARKS_THAT_SEPARATE) {
      const scenario = byLabel.get(entry.scenario)
      const twin = byLabel.get(entry.twin)
      expect(scenario, `${entry.scenario}: no such scenario`).toBeDefined()
      expect(twin, `${entry.twin}: no such scenario`).toBeDefined()
      expect(twin?.route, `${entry.twin} is on another route`).toBe(scenario?.route)
      const found = scenario?.shows.find((mark) => mark.name === entry.mark)
      expect(found, `${entry.scenario} declares no mark '${entry.mark}'`).toBeDefined()
      expect(found?.max, `${entry.scenario}: '${entry.mark}' is an absent mark`).toBeUndefined()
    }
  })

  test('a hold glob converts to the URLs Playwright would match', () => {
    const matches = (glob: string, url: string) => globToRegExp(glob).test(url)
    expect(matches('**/api/profiles', 'http://127.0.0.1:1/api/profiles')).toBe(true)
    expect(matches('**/api/profiles', 'http://127.0.0.1:1/api/profiles?x=1')).toBe(false)
    expect(matches('**/api/matches?*', 'http://127.0.0.1:1/api/matches?profile_id=1')).toBe(true)
    expect(matches('**/api/favourites/*', 'http://127.0.0.1:1/api/favourites/9001')).toBe(true)
    expect(matches('**/api/favourites/*', 'http://127.0.0.1:1/api/favourites')).toBe(false)
    expect(
      matches('**/api/profiles/4242?confirm=true', 'http://h/api/profiles/4242?confirm=true'),
    ).toBe(true)
    expect(matches('**/api/profiles/4242', 'http://h/api/profiles/4242?confirm=true')).toBe(false)
  })

  test('the no-linked-account fixture links nothing', () => {
    expect(NO_LINKED_ME.authenticated).toBe(true)
    expect(NO_LINKED_ME.profiles).toEqual([])
  })

  test('branch labels are unique, and a planted duplicate is caught', () => {
    expect(duplicateLabels(BRANCH_SCENARIOS)).toEqual([])
    const [first] = BRANCH_SCENARIOS
    expect(duplicateLabels([...BRANCH_SCENARIOS, first])).toEqual([first.label])
  })
})

// --- Each populated scenario renders its success branch, in a browser -----------------------------

const harness = createAppServerHarness('4180')

const POPULATED_MATCH_DETAIL = POPULATED_SCENARIOS.find(
  (scenario) => scenario.label === '/matches/$gameId (populated)',
)

test.describe('populated scenarios render their success branch', () => {
  test.describe.configure({ mode: 'serial' })

  if (!hasBuild && process.env.CI) {
    test('apps/web/dist must be built before this suite runs in CI', () => {
      throw new Error(
        'apps/web/dist has not been built. `.github/workflows/pr.yml` always runs ' +
          '`pnpm --filter web build` before this suite — a missing build here means that step ' +
          'failed or was skipped, not that this suite has nothing to test.',
      )
    })
  } else {
    test.skip(
      () => !hasBuild,
      'apps/web/dist has not been built — run `pnpm --filter web build` first.',
    )

    test.beforeAll(async () => {
      await harness.start()
    })

    test.afterAll(() => {
      harness.stop()
    })

    for (const scenario of POPULATED_SCENARIOS) {
      test(`${scenario.label} — every declared list has its items, no error or loading region`, async ({
        page,
      }) => {
        // `enterScenario` itself judges a populated scenario once its lists have had time to arrive.
        const external = await enterScenario(page, scenario, harness.baseUrl, 'light')
        external.assertNone(scenario.label)
      })
    }

    // The touch suite measures at 375px, where a table is stacked cards: each scenario's declared
    // lists must be on screen there too, not only at the default 1280px the test above runs at.
    for (const scenario of POPULATED_SCENARIOS) {
      test(`${scenario.label} — the same lists are on screen at 375px`, async ({ page }) => {
        await page.setViewportSize({ width: 375, height: 800 })
        await enterScenario(page, scenario, harness.baseUrl, 'light')
      })
    }

    // The planted cases, one per way a "populated" fixture can quietly render something else. Each
    // is judged inside `enterScenario`, which is what the four route suites call.
    test('planted: a match page whose body has no analysis key renders the error callout and fails', async ({
      page,
    }) => {
      // The exact shape the first implementation shipped: a full roster, no `analysis` object, so
      // `extractAnalysisSummary` throws and `AnalysisContainer` renders `<AnalysisTimeline error>`.
      if (!POPULATED_MATCH_DETAIL) throw new Error('/matches/$gameId (populated) is gone')
      const { analysis: _analysis, ...bodyWithoutAnalysis } = POPULATED_FIXTURES.matchDetail
      const planted: PopulatedScenario = {
        ...POPULATED_MATCH_DETAIL,
        stub: async (target) => {
          await stubMe(target, SIGNED_IN_ME)
          await target.route('**/api/profiles', (route) => fulfillJson(route, PROFILES_RESPONSE))
          await target.route(`**/api/matches/${SAMPLE_GAME_ID}`, (route) =>
            fulfillJson(route, bodyWithoutAnalysis),
          )
        },
      }
      await expect(enterScenario(page, planted, harness.baseUrl, 'light')).rejects.toThrow(
        /\(populated\): (an error callout \(role="alert"\) is on screen|analysis participant cards)/,
      )
    })

    test('planted: a published summary whose document 404s never reaches the lists and fails', async ({
      page,
    }) => {
      if (!POPULATED_MATCH_DETAIL) throw new Error('/matches/$gameId (populated) is gone')
      const planted: PopulatedScenario = {
        ...POPULATED_MATCH_DETAIL,
        stub: async (target) => {
          await POPULATED_MATCH_DETAIL.stub(target)
          await target.route(`**/api/matches/${SAMPLE_GAME_ID}/analysis`, (route) =>
            route.fulfill({ status: 404, contentType: 'application/json', body: '{}' }),
          )
        },
      }
      await expect(enterScenario(page, planted, harness.baseUrl, 'light')).rejects.toThrow(
        /\(populated\): (analysis participant cards|analysis ordered lists|analysis list items)/,
      )
    })

    test('planted: an empty list fails by naming the list', async ({ page }) => {
      const matches = POPULATED_SCENARIOS.find(
        (scenario) => scenario.label === '/matches (populated)',
      )
      if (!matches) throw new Error('/matches (populated) is gone')
      const planted: PopulatedScenario = {
        ...matches,
        stub: async (target) => {
          await matches.stub(target)
          await target.route('**/api/matches?*', (route) =>
            fulfillJson(route, { matches: [], next_cursor: null }),
          )
        },
      }
      await expect(enterScenario(page, planted, harness.baseUrl, 'light')).rejects.toThrow(
        /\(populated\): match rows \(main table tbody tr\) rendered fewer than 3 item\(s\)/,
      )
    })

    // T682: the in-browser assertion fails by name when the control is absent. Each planted page is
    // the real scenario with one stub changed, so everything else on it is exactly what ships.
    function scenarioNamed(label: string): PopulatedScenario {
      const found = POPULATED_SCENARIOS.find((scenario) => scenario.label === label)
      if (!found) throw new Error(`${label} is gone`)
      return found
    }

    for (const label of ['/dashboard (archival objected)', '/privacy (archival objected)']) {
      test(`planted: ${label} with archival_objected false renders no Resume button and fails`, async ({
        page,
      }) => {
        const base = scenarioNamed(label)
        const planted: PopulatedScenario = {
          ...base,
          stub: async (target) => {
            await base.stub(target)
            // Registered after the scenario's own stub, so it wins (Playwright matches the last).
            await stubMe(target, { ...OBJECTED_ME, archival_objected: false })
          },
        }
        await expect(enterScenario(page, planted, harness.baseUrl, 'light')).rejects.toThrow(
          /\(archival objected\): Resume archival button \(main button:has-text\("Resume archival"\)\) rendered fewer than 1 item\(s\)/,
        )
      })

      test(`planted: ${label} with no archival_objected_at loses the dated callout and fails`, async ({
        page,
      }) => {
        const base = scenarioNamed(label)
        const planted: PopulatedScenario = {
          ...base,
          stub: async (target) => {
            await base.stub(target)
            await stubMe(target, { ...OBJECTED_ME, archival_objected_at: null })
          },
        }
        await expect(enterScenario(page, planted, harness.baseUrl, 'light')).rejects.toThrow(
          /\(archival objected\): objected callout/,
        )
      })
    }

    test('planted: an export that stays queued never reaches ready and fails', async ({ page }) => {
      const base = scenarioNamed('/privacy (export ready)')
      const planted: PopulatedScenario = {
        ...base,
        stub: async (target) => {
          await base.stub(target)
          await target.route('**/api/privacy/export/visual-suite-export', (route) =>
            fulfillJson(route, { id: 'visual-suite-export', status: 'queued' }),
          )
        },
      }
      await expect(enterScenario(page, planted, harness.baseUrl, 'light')).rejects.toThrow(
        /\(export ready\): export download link \(main a\[download\]:has-text\("Download the archive"\)\) rendered fewer than 1 item\(s\)/,
      )
    })

    // The replay availability list is told from the participant cards by its own section's heading,
    // not by what a card says of itself. Both planted pages below are the real populated match page,
    // altered in the browser after it renders, so the rest of the page is exactly what ships.
    const REPLAY_ROWS_BEFORE_SCOPING = 'main section ul > li:not(:has-text("Colour:"))'

    const removeRecordedGames = () => {
      const strip = () => {
        for (const heading of document.querySelectorAll('h3')) {
          if (heading.textContent === 'Recorded games') heading.closest('section')?.remove()
        }
      }
      new MutationObserver(strip).observe(document, { childList: true, subtree: true })
    }

    const blankSwatchText = () => {
      const blank = () => {
        for (const label of document.querySelectorAll('.sr-only')) {
          if (label.textContent?.startsWith('Colour:')) label.textContent = ''
        }
      }
      new MutationObserver(blank).observe(document, { childList: true, subtree: true })
    }

    function matchDetailAltered(script: () => void, renders?: PopulatedScenario['renders']) {
      if (!POPULATED_MATCH_DETAIL) throw new Error('/matches/$gameId (populated) is gone')
      const base = POPULATED_MATCH_DETAIL
      const planted: PopulatedScenario = {
        ...base,
        renders: renders ?? base.renders,
        stub: async (target) => {
          await base.stub(target)
          await target.addInitScript(script)
        },
      }
      return planted
    }

    function listNamed(name: string) {
      const list = POPULATED_MATCH_DETAIL?.renders.find((entry) => entry.name === name)
      if (!list) throw new Error(`/matches/$gameId (populated) declares no '${name}'`)
      return list
    }

    // The width the suites measure at: 1280px is a table, 375px stacked cards.
    for (const width of [1280, 375]) {
      test(`planted: participant cards without the "Recorded games" list yield no replay rows and fail, at ${width}px`, async ({
        page,
      }) => {
        await page.setViewportSize({ width, height: 800 })
        const planted = matchDetailAltered(removeRecordedGames)
        await expect(enterScenario(page, planted, harness.baseUrl, 'light')).rejects.toThrow(
          /\(populated\): replay availability rows/,
        )
        const roster = listNamed('participant rows')
        const cards = width === 1280 ? roster.selector : (roster.stacked?.selector ?? '')
        expect(
          await page.locator(cards).count(),
          'the participant cards must still be on screen, or this planted page proves nothing',
        ).toBeGreaterThanOrEqual(roster.min)
        expect(await page.getByRole('heading', { name: 'Recorded games' }).count()).toBe(0)
        expect(await page.locator(listNamed('replay availability rows').selector).count()).toBe(0)
      })

      test(`contrast: the replay rows are the same four with the swatch's text gone, at ${width}px`, async ({
        page,
      }) => {
        await page.setViewportSize({ width, height: 800 })
        const replay = listNamed('replay availability rows')
        const planted = matchDetailAltered(blankSwatchText, [replay])
        await enterScenario(page, planted, harness.baseUrl, 'light')
        expect(
          await page.locator('main :text("Colour:")').count(),
          'the swatch text must be gone, or this page proves nothing',
        ).toBe(0)
        expect(await page.locator(replay.selector).count()).toBe(4)
        // What the selector used to be: it read the swatch's text, so with it gone each stacked
        // participant card (375px; at 1280px they are table rows, no list) counts as a replay row too.
        expect(await page.locator(REPLAY_ROWS_BEFORE_SCOPING).count()).toBe(width === 375 ? 8 : 4)
      })
    }

    test('a populated scenario whose list arrives late is judged only after the list renders', async ({
      page,
    }) => {
      const matches = POPULATED_SCENARIOS.find(
        (scenario) => scenario.label === '/matches (populated)',
      )
      if (!matches) throw new Error('/matches (populated) is gone')
      let delayed = 0
      const planted: PopulatedScenario = {
        ...matches,
        stub: async (target) => {
          await matches.stub(target)
          // Registered after the scenario's own stub, so it answers first — 2s later, well past the
          // `main`, theme and font waits `enterScenario` always did.
          await target.route('**/api/matches?*', async (route) => {
            delayed += 1
            await new Promise((resolve) => setTimeout(resolve, 2000))
            await fulfillJson(route, POPULATED_FIXTURES.matches)
          })
        },
      }
      await enterScenario(page, planted, harness.baseUrl, 'light')
      expect(delayed, 'the delayed stub never answered a request').toBeGreaterThan(0)
      // No polling here: when `enterScenario` returns, the rows must already be on screen.
      expect(await page.locator('main table tbody tr').count()).toBeGreaterThanOrEqual(3)
    })

    test('contrast: a populated scenario whose list never arrives fails inside enterScenario', async ({
      page,
    }) => {
      const matches = POPULATED_SCENARIOS.find(
        (scenario) => scenario.label === '/matches (populated)',
      )
      if (!matches) throw new Error('/matches (populated) is gone')
      const planted: PopulatedScenario = {
        ...matches,
        stub: async (target) => {
          await matches.stub(target)
          await target.route('**/api/matches?*', () => new Promise(() => {}))
        },
      }
      await expect(enterScenario(page, planted, harness.baseUrl, 'light')).rejects.toThrow(
        /\(populated\): match rows \(main table tbody tr\) rendered fewer than 3 item\(s\)/,
      )
    })

    test('a dashboard whose profiles carry no ratings fails on its rating rows', async ({
      page,
    }) => {
      // The dashboard's one declared list is data-driven, so it is sensitive to the data. (Its old
      // second entry, a `main ul > li` over static copy, rendered whatever the data was.)
      const dashboard = POPULATED_SCENARIOS.find((scenario) => scenario.route === '/dashboard')
      if (!dashboard) throw new Error('the /dashboard populated scenario is gone')
      const planted: PopulatedScenario = {
        ...dashboard,
        stub: async (target) => {
          await stubMe(target, SIGNED_IN_ME)
          await target.route('**/api/profiles', (route) =>
            fulfillJson(route, {
              profiles: PROFILES_RESPONSE.profiles.map((profile) => ({ ...profile, ratings: [] })),
            }),
          )
        },
      }
      await expect(enterScenario(page, planted, harness.baseUrl, 'light')).rejects.toThrow(
        /\(two linked profiles\): rating rows/,
      )
    })
  }
})

// --- Each branch scenario renders the branch it names, in a browser (T744) -------------------------
//
// Every scenario is entered at 1280px and at 375px (the touch suite measures at the second), and
// then planted against what it must not be taken for, each judged inside `enterScenario`, which is
// what the four route suites call. Four kinds of plant, and what each covers:
//
// - the route's *success* page before any action (`SUCCESS_SCENARIO_FOR`): the stub the branch
//   replaced, with the scenario's hold, `prepare` and surface dropped, for every scenario, so a
//   branch whose stubs fell through to the success response fails. It does not run the scenario's
//   action against the success page;
// - its *sibling*: for a scenario in a `family`, the next scenario of the same route and family in
//   the ring (not every pair) run in its place, so two branches of one section that render alike
//   are found. The other pairs are covered as far as the unit check on the declarations goes and
//   no further: it compares selectors as written, so differently spelled selectors that match the
//   same element are not seen as one. Those overlaps are covered only by the discriminating marks
//   of the scenarios named in `MARKS_THAT_SEPARATE`, each planted against its twin;
// - for a held request, the same scenario with the request *answered at once*, so a loading or
//   in-flight state that never held fails;
// - for every *absent* mark (`min: 0, max: 0`), a page where the thing is present, so the mark
//   fails by "more than", not only by its absence being untested.
//
// Each plant fails with the message `assertBranchScenario` throws for the mark that fails, and only
// that. The error to guard against is a plant credited because the page it put in the scenario's
// place had not rendered yet, so before the marks are judged (with a short timeout, since a failure
// is the expected result) each plant first waits for the substituted page to show what it declares:
// all of a sibling's or a presence page's marks, all of a populated success page's lists, one
// landmark of an at-rest success page, or, for a request answered at once, the answer and no busy
// region left. That proves the substituted page is there. It does not prove the scenario's own
// marks cannot still be on their way: a mark that renders later than the substituted page's own
// signs can be credited by a plant as discriminating within the 1 s judge window, so that plant's
// evidence is weaker than its pass suggests. Every kind of plant carries this, a sibling or a
// presence page whose marks all arrive before a base mark as much as an at-rest page or an
// instant answer.

// The page a route shows when none of its branches is in play: what a branch scenario is planted
// against. `/matches/$gameId` at rest is not it (its stub lacks an `analysis` key, which renders the
// analysis error branch), so the populated page stands in.
const SUCCESS_SCENARIO_FOR: Readonly<Record<string, string>> = {
  '/sign-in': '/sign-in',
  '/dashboard': '/dashboard (two linked profiles)',
  '/search': '/search',
  '/favourites': '/favourites (populated)',
  '/matches': '/matches (populated)',
  '/matches/$gameId': '/matches/$gameId (populated)',
  '/players/$profileId': '/players/$profileId (favourited)',
  '/players/$profileId/matches': '/players/$profileId/matches (populated)',
  '/privacy': '/privacy',
  '/object': '/object',
}

// What shows that an at-rest success page has rendered: text only that page carries. A populated
// success page is waited for by its own declared lists (`assertPopulatedScenario`).
const AT_REST_LANDMARK: Readonly<Record<string, string>> = {
  '/sign-in': 'main :text("Sign in to see your Age of Empires II stats")',
  '/search': 'main :text("Search for a player by name.")',
  '/privacy': 'main :text("Get a copy of your data")',
  '/object': 'main :text("Your Age of Empires II profile id")',
}

function successFor(route: string): RouteScenario {
  const label = SUCCESS_SCENARIO_FOR[route]
  const found = [...ROUTE_SCENARIOS, ...POPULATED_SCENARIOS].find(
    (scenario) => scenario.label === label,
  )
  if (!found) throw new Error(`no success scenario '${label}' for route '${route}'`)
  return found
}

/** Waits for the success page of `route` to have rendered. */
async function successRendered(page: Page, route: string): Promise<void> {
  const success = successFor(route)
  const landmark = AT_REST_LANDMARK[route]
  if (landmark) {
    await expect(page.locator(landmark).first()).toBeVisible()
    return
  }
  if (!('renders' in success)) throw new Error(`no landmark for the success page of '${route}'`)
  await assertPopulatedScenario(page, success as PopulatedScenario, success.label)
}

// The absent marks, and the page each is shown present on: the state the branch hides the thing
// from, which is the state a regression would show it in. Keyed `scenario label|mark name`.
const PRESENCE_PAGE_FOR: Readonly<Record<string, string>> = {
  '/sign-in (link variant)|no outcome callout': '/sign-in (outcome profile_already_linked)',
  '/matches/$gameId (match download in flight)|no busy row download':
    '/matches/$gameId (replay download in flight)',
  '/dashboard (profile summary loading)|no ratings failure': '/dashboard (profile load failed)',
  '/matches/$gameId (analysis document failed)|no match failure':
    '/matches/$gameId (match load failed)',
  '/matches (profile loading)|no ratings failure': '/matches (profile load failed)',
  '/matches (profile loading)|no profile identity': '/matches (match list loading)',
  '/players/$profileId/matches (profile loading)|no profile identity':
    '/players/$profileId/matches (match list loading)',
  '/players/$profileId (profile loading)|no ratings failure':
    '/players/$profileId (profile load failed)',
  '/players/$profileId/matches (profile loading)|no ratings failure':
    '/players/$profileId/matches (profile load failed)',
  '/matches (capture statuses, archival objected)|no catchable badge':
    '/matches (capture statuses)',
  '/privacy (export requesting)|no preparing callout': '/privacy (export preparing)',
  '/privacy (account erased)|no erase button': '/privacy',
  '/privacy (erasure re-mint in flight)|no expiry callout':
    '/privacy (erasure confirmation expired)',
  '/matches/$gameId (capture quarantined)|no upload control': '/matches/$gameId (capture failed)',
  '/matches/$gameId (capture status unrecognised)|no upload control':
    '/matches/$gameId (capture failed)',
  '/matches/$gameId (capture lost, archival objected)|no upload control':
    '/matches/$gameId (capture failed)',
  '/matches/$gameId (capture pending, archival objected)|no countdown':
    '/matches/$gameId (capture pending)',
}

// Marks added because two scenarios of a route that no ring compares (different families, or none)
// had marks that one page satisfied both ways: each is a positive mark of `scenario` that the
// `twin` page, which the broader selectors alone would have matched, must not show. The planted
// cases run the mark alone on the twin's page and on the route's success page.
interface SeparatingMark {
  scenario: string
  mark: string
  twin: string
  /** The route's success page shows this too (the archived state starts "Archival is on."; the
   * loaded match shows its header), so the mark is planted on the twin's page only. */
  onSuccessPage?: true
}
const MARKS_THAT_SEPARATE: readonly SeparatingMark[] = [
  {
    scenario: '/matches/$gameId (match loading)',
    mark: 'busy match panel',
    twin: '/matches/$gameId (analysis document loading)',
  },
  {
    scenario: '/matches/$gameId (match loading)',
    mark: 'busy match panel',
    twin: '/matches/$gameId (analysis queued)',
  },
  {
    scenario: '/matches/$gameId (analysis document loading)',
    mark: 'loaded match panel',
    twin: '/matches/$gameId (match loading)',
    onSuccessPage: true,
  },
  {
    scenario: '/matches/$gameId (analysis document failed)',
    mark: 'loaded match panel',
    twin: '/matches/$gameId (match load failed)',
    onSuccessPage: true,
  },
  {
    scenario: '/dashboard (archival write in flight)',
    mark: 'archival is on',
    twin: '/dashboard (archival resume in flight)',
    onSuccessPage: true,
  },
  {
    scenario: '/privacy (archival write in flight)',
    mark: 'archival is on',
    twin: '/privacy (archival resume in flight)',
    onSuccessPage: true,
  },
]

function absentMarksOf(scenario: BranchScenario): ListExpectation[] {
  return scenario.shows.filter((entry) => entry.max !== undefined)
}

/** The URLs a hold's glob matches, as Playwright reads one: `**` any run, `*` within a segment, `?` one
 * character. Only the holds in this file are converted, and the test below pins what it does. */
function globToRegExp(glob: string): RegExp {
  const source = glob
    .replace(/[.+^${}()|[\]\\]/g, '\\$&')
    .replace(/\*\*/g, '\u0000')
    .replace(/\*/g, '[^/]*')
    .replace(/\?/g, '.')
    .replace(/\u0000/g, '.*')
  return new RegExp(`^${source}$`)
}

interface Case {
  title: string
  run: (page: Page, baseUrl: string) => Promise<void>
}

const PLANT_TIMEOUT_MS = 1_000

function rejectionFor(base: BranchScenario, markName?: string, direction = 'fewer|more'): RegExp {
  const escape = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return new RegExp(
    `${escape(base.label)}: ${markName ? escape(markName) : '.*'} \\(.*\\) rendered (${direction}) than \\d+ item\\(s\\) — the route is not showing its '${escape(base.branch)}' branch`,
  )
}

async function expectRejected(
  page: Page,
  planted: BranchScenario,
  url: string,
  rendered: (page: Page) => Promise<void>,
  expected: RegExp,
) {
  await expect(
    enterScenario(page, planted, url, 'light', {
      judgeTimeoutMs: PLANT_TIMEOUT_MS,
      beforeJudge: rendered,
    }),
  ).rejects.toThrow(expected)
}

/** Waits for the held request's instant answer to have arrived and for nothing to be left busy. */
function answeredAtOnce(held: HeldRequest) {
  const matches = globToRegExp(held.urlGlob)
  return async (page: Page) => {
    await expect
      .poll(() =>
        apiResponses(page).some(
          (response) =>
            matches.test(response.url) &&
            (held.method === undefined || held.method === response.method),
        ),
      )
      .toBe(true)
    await expect(page.locator('[aria-busy="true"]')).toHaveCount(0)
  }
}

function plantedCases(): Case[] {
  const cases: Case[] = []
  const byLabel = new Map(BRANCH_SCENARIOS.map((scenario) => [scenario.label, scenario]))

  for (const base of BRANCH_SCENARIOS) {
    const success = successFor(base.route)
    cases.push({
      title: `planted: ${base.label} pointed at the route's success page fails on its marks`,
      run: (page, url) =>
        expectRejected(
          page,
          {
            ...base,
            path: success.path,
            landedPath: success.landedPath,
            stub: success.stub,
            prepare: undefined,
            hold: undefined,
            surface: undefined,
          },
          url,
          (target) => successRendered(target, base.route),
          rejectionFor(base),
        ),
    })

    const siblings = BRANCH_SCENARIOS.filter(
      (other) =>
        base.family !== undefined && other.route === base.route && other.family === base.family,
    )
    if (siblings.length > 1) {
      const sibling = siblings[(siblings.indexOf(base) + 1) % siblings.length]
      cases.push({
        title: `planted: ${base.label} run as its sibling '${sibling.branch}' fails on its marks`,
        run: (page, url) =>
          expectRejected(
            page,
            {
              ...base,
              path: sibling.path,
              landedPath: sibling.landedPath,
              stub: sibling.stub,
              prepare: sibling.prepare,
              hold: sibling.hold,
              surface: sibling.surface,
            },
            url,
            (target) => assertBranchScenario(target, sibling, sibling.label),
            rejectionFor(base),
          ),
      })
    }

    const held = base.hold
    if (held) {
      cases.push({
        title: `planted: ${base.label} with its request answered at once fails on its marks`,
        run: (page, url) =>
          expectRejected(
            page,
            {
              ...base,
              hold: undefined,
              stub: async (target) => {
                await base.stub(target)
                await target.route(held.urlGlob, (route) =>
                  held.method !== undefined && route.request().method() !== held.method
                    ? route.fallback()
                    : fulfillJson(route, held.resolvesWith ?? held.body),
                )
              },
            },
            url,
            answeredAtOnce(held),
            rejectionFor(base),
          ),
      })
    }

    for (const separating of MARKS_THAT_SEPARATE.filter((entry) => entry.scenario === base.label)) {
      const separatingMark = base.shows.find((entry) => entry.name === separating.mark)
      const twin = byLabel.get(separating.twin)
      if (!separatingMark || !twin) continue // `every separating mark is a real positive mark` fails by name
      const expected = rejectionFor(base, separatingMark.name, 'fewer')
      cases.push({
        title: `planted: ${base.label}'s '${separating.mark}' on the twin '${twin.branch}' fails on that mark`,
        run: (page, url) =>
          expectRejected(
            page,
            {
              ...base,
              path: twin.path,
              landedPath: twin.landedPath,
              stub: twin.stub,
              prepare: twin.prepare,
              hold: twin.hold,
              surface: twin.surface,
              shows: [separatingMark],
            },
            url,
            (target) => assertBranchScenario(target, twin, twin.label),
            expected,
          ),
      })
      if (!separating.onSuccessPage)
        cases.push({
          title: `planted: ${base.label}'s '${separating.mark}' on the route's success page fails on that mark`,
          run: (page, url) =>
            expectRejected(
              page,
              {
                ...base,
                path: success.path,
                landedPath: success.landedPath,
                stub: success.stub,
                prepare: undefined,
                hold: undefined,
                surface: undefined,
                shows: [separatingMark],
              },
              url,
              (target) => successRendered(target, base.route),
              expected,
            ),
        })
    }

    for (const absentMark of absentMarksOf(base)) {
      const presenceLabel = PRESENCE_PAGE_FOR[`${base.label}|${absentMark.name}`]
      if (presenceLabel === undefined) continue // `every absent mark has a presence page` fails by name
      const presence = byLabel.get(presenceLabel)
      const page_ = presence ?? successFor(base.route)
      cases.push({
        title: `planted: ${base.label} where '${absentMark.name}' is present fails on that mark`,
        run: (page, url) =>
          expectRejected(
            page,
            {
              ...base,
              path: page_.path,
              landedPath: page_.landedPath,
              stub: page_.stub,
              prepare: presence?.prepare,
              hold: presence?.hold,
              surface: presence?.surface,
              shows: [absentMark],
            },
            url,
            (target) =>
              presence
                ? assertBranchScenario(target, presence, presence.label)
                : successRendered(target, base.route),
            rejectionFor(base, absentMark.name, 'more'),
          ),
      })
    }
  }
  return cases
}

const BRANCH_SHARDS = 4

test.describe('branch scenarios render the branch they name', () => {
  if (!hasBuild && process.env.CI) {
    test('apps/web/dist must be built before this suite runs in CI', () => {
      throw new Error(
        'apps/web/dist has not been built. `.github/workflows/pr.yml` always runs ' +
          '`pnpm --filter web build` before this suite — a missing build here means that step ' +
          'failed or was skipped, not that this suite has nothing to test.',
      )
    })
  } else {
    test.skip(
      () => !hasBuild,
      'apps/web/dist has not been built — run `pnpm --filter web build` first.',
    )

    // `enterScenario` itself judges a branch scenario once its `prepare` has run.
    const cases: Case[] = [
      ...BRANCH_SCENARIOS.flatMap((scenario): Case[] => [
        {
          title: `${scenario.label} — every declared mark is on screen`,
          run: async (page, url) => {
            const external = await enterScenario(page, scenario, url, 'light')
            external.assertNone(scenario.label)
          },
        },
        {
          title: `${scenario.label} — the same marks are on screen at 375px`,
          run: async (page, url) => {
            await page.setViewportSize({ width: 375, height: 800 })
            await enterScenario(page, scenario, url, 'light')
          },
        },
      ]),
      ...plantedCases(),
    ]

    // Several hundred browser cases: dealt over serial groups, each with its own server, so the
    // runner's workers share them (a serial group runs in one worker, in order).
    for (let shard = 0; shard < BRANCH_SHARDS; shard += 1) {
      test.describe(`shard ${shard + 1} of ${BRANCH_SHARDS}`, () => {
        test.describe.configure({ mode: 'serial' })
        const shardHarness = createAppServerHarness(String(4185 + shard))

        test.beforeAll(async () => {
          await shardHarness.start()
        })

        test.afterAll(() => {
          shardHarness.stop()
        })

        cases.forEach((entry, index) => {
          if (index % BRANCH_SHARDS !== shard) return
          test(entry.title, async ({ page }) => {
            await entry.run(page, shardHarness.baseUrl)
          })
        })
      })
    }
  }
})

// --- Every Menu and Dialog an application route can open has a scenario ---------------------------

interface CoveredSurface {
  source: string
  tag: 'Menu' | 'Dialog'
  /** How many `<Tag` usages the file holds — one scenario each. */
  count: number
  /** A fragment every one of those scenarios' labels contains, for the whole group. */
  scenarios: readonly string[]
}

interface SurfaceUsage {
  source: string
  tag: string
  count: number
}

// Every JSX usage of `<Menu` / `<Dialog` outside stories and tests, with the scenario that opens
// it. A route-reachable surface not listed here fails `finds exactly the covered surfaces` below
// until a scenario exists for it — "one scenario per `Dialog` and `Menu`" kept true by the build,
// not by remembering. `Tooltip` is not here: it has no `surface` to walk, and its own table
// (`COVERED_TOOLTIP_HOSTS`, T681) follows below.
const COVERED_SURFACES: readonly CoveredSurface[] = [
  {
    source: 'packages/design-system/src/composites/SiteHeader/index.tsx',
    tag: 'Menu',
    count: 1,
    scenarios: ['theme menu open'],
  },
  {
    source: 'packages/design-system/src/screens/ProfileSummary/index.tsx',
    tag: 'Menu',
    count: 2,
    scenarios: ['profile switcher menu open', 'manage menu open'],
  },
  {
    source: 'packages/design-system/src/screens/AccountErasurePanel/index.tsx',
    tag: 'Dialog',
    count: 1,
    scenarios: ['account erasure dialog open'],
  },
  {
    source: 'apps/web/src/features/profile/UnlinkDialog.tsx',
    tag: 'Dialog',
    count: 1,
    scenarios: ['unlink dialog open'],
  },
]

function sourceFiles(directory: string): string[] {
  return readdirSync(directory).flatMap((entry) => {
    const full = path.join(directory, entry)
    if (statSync(full).isDirectory()) return entry === 'node_modules' ? [] : sourceFiles(full)
    return /\.tsx$/.test(entry) && !/\.(stories|test)\.tsx$/.test(entry) ? [full] : []
  })
}

// JSX usages only: comments are blanked first so a docstring mentioning `<Menu>` is not one.
function countSurfaceUsages(source: string): { Menu: number; Dialog: number } {
  const code = source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')
  return {
    Menu: (code.match(/<Menu(?![A-Za-z])/g) ?? []).length,
    Dialog: (code.match(/<Dialog(?![A-Za-z])/g) ?? []).length,
  }
}

function findSurfaceUsages(): SurfaceUsage[] {
  const found: SurfaceUsage[] = []
  for (const directory of ['packages/design-system/src', 'apps/web/src']) {
    for (const file of sourceFiles(path.join(rootDir, directory))) {
      const usages = countSurfaceUsages(readFileSync(file, 'utf8'))
      const relative = path.relative(rootDir, file).split(path.sep).join('/')
      // `Menu` and `Dialog` are the primitives themselves; neither renders another.
      if (/primitives\/(Menu|Dialog)\//.test(relative)) continue
      for (const tag of ['Menu', 'Dialog'] as const) {
        if (usages[tag] > 0) found.push({ source: relative, tag, count: usages[tag] })
      }
    }
  }
  return found
}

const surfaceKey = (entry: { source: string; tag: string }) => `${entry.source}#${entry.tag}`

/** `found` against `covered`, as sorted `source#tag:count` lines, so two differing lists differ. */
function surfaceLines(entries: readonly SurfaceUsage[]): string[] {
  return entries
    .map((entry) => `${surfaceKey(entry)}:${entry.count}`)
    .sort((a, b) => a.localeCompare(b))
}

/** Each covered surface's claimed scenario fragments that match no surface scenario, or match one
 * of the wrong kind. */
function surfaceScenarioProblems(
  surfaces: readonly CoveredSurface[],
  scenarios: readonly SuiteScenario[],
): string[] {
  const problems: string[] = []
  for (const surface of surfaces) {
    for (const fragment of surface.scenarios) {
      const matching = scenarios.filter((scenario) => scenario.label.includes(fragment))
      if (matching.length === 0) problems.push(`no surface scenario's label contains "${fragment}"`)
      for (const scenario of matching) {
        if (scenario.surface !== (surface.tag === 'Menu' ? 'menu' : 'dialog')) {
          problems.push(`${scenario.label}: wrong surface kind`)
        }
      }
    }
  }
  return problems
}

test.describe('openable surfaces', () => {
  test('finds exactly the covered surfaces', () => {
    expect(
      surfaceLines(findSurfaceUsages()),
      'a <Menu> or <Dialog> usage appeared or disappeared: add or retire its scenario in ' +
        'tests/visual/fixtures/suite-scenarios.ts and update COVERED_SURFACES here',
    ).toEqual(surfaceLines(COVERED_SURFACES))
  })

  test('a planted new Dialog consumer, or a retired one, makes the comparison differ', () => {
    const covered = surfaceLines(COVERED_SURFACES)
    const planted: SurfaceUsage = {
      source: 'apps/web/src/features/planted/PlantedDialog.tsx',
      tag: 'Dialog',
      count: 1,
    }
    expect(surfaceLines([...COVERED_SURFACES, planted])).not.toEqual(covered)
    expect(surfaceLines(COVERED_SURFACES.slice(1))).not.toEqual(covered)
    expect(
      surfaceLines([{ ...COVERED_SURFACES[0], count: 2 }, ...COVERED_SURFACES.slice(1)]),
    ).not.toEqual(covered)
  })

  test('each covered surface has the scenarios it claims, of the right kind', () => {
    expect(surfaceScenarioProblems(COVERED_SURFACES, SURFACE_SCENARIOS)).toEqual([])
  })

  test('a planted surface claiming a scenario that does not exist, or of the wrong kind, is caught', () => {
    const planted: CoveredSurface = {
      source: 'planted.tsx',
      tag: 'Dialog',
      count: 1,
      scenarios: ['no such scenario', 'theme menu open'],
    }
    expect(surfaceScenarioProblems([planted], SURFACE_SCENARIOS)).toEqual([
      `no surface scenario's label contains "no such scenario"`,
      ...SURFACE_SCENARIOS.filter((scenario) => scenario.label.includes('theme menu open')).map(
        (scenario) => `${scenario.label}: wrong surface kind`,
      ),
    ])
  })

  test('the usage counter ignores comments and counts a planted usage', () => {
    expect(countSurfaceUsages('/* <Menu> */ // <Dialog>\nconst x = 1')).toEqual({
      Menu: 0,
      Dialog: 0,
    })
    expect(
      countSurfaceUsages('return <><Menu a="b" /><Dialog heading="x" /><MenuItem /></>'),
    ).toEqual({
      Menu: 1,
      Dialog: 1,
    })
  })
})

// --- Every route that can render a Tooltip has a tooltip scenario (T681) --------------------------

interface CoveredTooltipHost {
  source: string
  /** `Tooltip` itself, or a component on the chain that renders one: `CountryFlag` renders the
   * `Tooltip`, `ProfileSummary` renders the `CountryFlag`, and each container renders a
   * `ProfileSummary`. */
  tag: 'Tooltip' | 'CountryFlag' | 'ProfileSummary'
  count: number
  /** The `ROUTE_SCENARIOS` labels this usage can put a tooltip on. */
  routes: readonly string[]
}

const FLAG_ROUTES = [
  '/dashboard',
  '/matches',
  '/players/$profileId',
  '/players/$profileId/matches',
] as const

// Every JSX usage of `<Tooltip`, `<CountryFlag` and `<ProfileSummary` outside stories and tests. The
// only direct `Tooltip` consumer is `CountryFlag`, whose only consumer is `ProfileSummary`; the four
// containers below are the routes that render one (`MatchDetailContainer` renders none: its
// participants are a table and cards, not a `ProfileSummary`). Task T681's text said tooltips also
// appear "in the populated lists"; the source says they do not — no list row renders a flag.
const COVERED_TOOLTIP_HOSTS: readonly CoveredTooltipHost[] = [
  {
    source: 'packages/design-system/src/composites/CountryFlag/index.tsx',
    tag: 'Tooltip',
    count: 1,
    routes: FLAG_ROUTES,
  },
  {
    source: 'packages/design-system/src/screens/ProfileSummary/index.tsx',
    tag: 'CountryFlag',
    count: 1,
    routes: FLAG_ROUTES,
  },
  {
    source: 'apps/web/src/features/profile/DashboardContainer.tsx',
    tag: 'ProfileSummary',
    count: 1,
    routes: ['/dashboard'],
  },
  {
    source: 'apps/web/src/features/matches/MatchHistoryContainer.tsx',
    tag: 'ProfileSummary',
    count: 1,
    routes: ['/matches'],
  },
  {
    source: 'apps/web/src/features/players/PlayerProfileContainer.tsx',
    tag: 'ProfileSummary',
    count: 1,
    routes: ['/players/$profileId'],
  },
  {
    source: 'apps/web/src/features/players/PlayerMatchHistoryContainer.tsx',
    tag: 'ProfileSummary',
    count: 1,
    routes: ['/players/$profileId/matches'],
  },
]

const TOOLTIP_CHAIN_TAGS = ['Tooltip', 'CountryFlag', 'ProfileSummary'] as const

function countTooltipChainUsages(
  source: string,
): Record<(typeof TOOLTIP_CHAIN_TAGS)[number], number> {
  const code = source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')
  const count = (tag: string) => (code.match(new RegExp(`<${tag}(?![A-Za-z])`, 'g')) ?? []).length
  return {
    Tooltip: count('Tooltip'),
    CountryFlag: count('CountryFlag'),
    ProfileSummary: count('ProfileSummary'),
  }
}

interface SourceText {
  /** Repository-rooted, forward-slashed. */
  relative: string
  text: string
}

function readSourceTexts(): SourceText[] {
  return ['packages/design-system/src', 'apps/web/src'].flatMap((directory) =>
    sourceFiles(path.join(rootDir, directory)).map((file) => ({
      relative: path.relative(rootDir, file).split(path.sep).join('/'),
      text: readFileSync(file, 'utf8'),
    })),
  )
}

/** The scanner proper, over source text rather than the disk, so a planted file goes through the
 * very function the real check calls. */
function findTooltipChainUsages(files: readonly SourceText[]): SurfaceUsage[] {
  const found: SurfaceUsage[] = []
  for (const { relative, text } of files) {
    // `Tooltip` is the primitive itself; it renders no other tooltip.
    if (/primitives\/Tooltip\//.test(relative)) continue
    const usages = countTooltipChainUsages(text)
    for (const tag of TOOLTIP_CHAIN_TAGS) {
      if (usages[tag] > 0) found.push({ source: relative, tag, count: usages[tag] })
    }
  }
  return found
}

interface RouteText {
  /** The file name under `apps/web/src/routes/`. */
  file: string
  text: string
}

function readRouteTexts(): RouteText[] {
  const directory = path.join(rootDir, 'apps/web/src/routes')
  return readdirSync(directory)
    .filter((file) => /\.tsx$/.test(file) && !/\.test\.tsx$/.test(file))
    .map((file) => ({ file, text: readFileSync(path.join(directory, file), 'utf8') }))
}

/** TanStack's flat file naming to the `ROUTE_SCENARIOS` label: `matches.index.tsx` is `/matches`,
 * `players.$profileId.matches.tsx` is `/players/$profileId/matches`. `null` for the files that are
 * not an application route (`__root`, `index`, which only redirects). */
function routeLabelOfFile(file: string): string | null {
  const name = file.replace(/\.tsx$/, '')
  if (name === '__root' || name === 'index') return null
  return `/${name
    .replace(/\.index$/, '')
    .split('.')
    .join('/')}`
}

/** The routes whose file imports `container`. Comments are blanked first, so a docstring naming it
 * is not an import. Braced named imports only: a default import, a lazy `import()` and a route in
 * a nested directory are not derived. */
function routesImporting(container: string, routes: readonly RouteText[]): string[] {
  const importPattern = new RegExp(
    `import\\s*(?:type\\s+)?\\{[^}]*\\b${container}\\b[^}]*\\}\\s*from`,
  )
  return routes
    .filter(({ text }) =>
      importPattern.test(text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')),
    )
    .flatMap(({ file }) => routeLabelOfFile(file) ?? [])
    .sort((a, b) => a.localeCompare(b))
}

const containerName = (host: CoveredTooltipHost) => path.basename(host.source, '.tsx')

/** The containers that render a `ProfileSummary` (the covered hosts under `apps/web`). */
const isContainerHost = (host: CoveredTooltipHost) =>
  host.tag === 'ProfileSummary' && host.source.startsWith('apps/web/src/')

/** What `COVERED_TOOLTIP_HOSTS` cannot tell on its own: every route file that imports a container
 * rendering a `ProfileSummary`, whose route has no tooltip scenario, and every such container no
 * route file imports (its routes could not be derived, so nothing would be checked). */
function derivedRouteProblems(
  hosts: readonly CoveredTooltipHost[],
  routes: readonly RouteText[],
  scenarios: readonly TooltipScenario[],
): string[] {
  const opened = new Set(scenarios.map((scenario) => scenario.route))
  const problems: string[] = []
  for (const host of hosts.filter(isContainerHost)) {
    const container = containerName(host)
    const mounting = routesImporting(container, routes)
    if (mounting.length === 0) {
      problems.push(`${container}: no route file imports it, so its routes cannot be derived`)
    }
    for (const route of mounting) {
      if (!opened.has(route)) {
        problems.push(
          `${route}: mounts ${container}, which renders a ProfileSummary, and no tooltip scenario ` +
            `opens a tooltip on it`,
        )
      }
    }
  }
  return problems
}

/** Every route a covered usage claims that no tooltip scenario opens a tooltip on, and every
 * tooltip scenario no covered usage claims. */
function tooltipScenarioProblems(
  hosts: readonly CoveredTooltipHost[],
  scenarios: readonly TooltipScenario[],
): string[] {
  const claimed = new Set(hosts.flatMap((host) => host.routes))
  const opened = new Set(scenarios.map((scenario) => scenario.route))
  return [
    ...[...claimed]
      .filter((route) => !opened.has(route))
      .map((route) => `${route}: renders a Tooltip and no tooltip scenario opens it`),
    ...[...opened]
      .filter((route) => !claimed.has(route))
      .map((route) => `${route}: a tooltip scenario no covered usage claims`),
  ]
}

test.describe('tooltips', () => {
  test('finds exactly the covered tooltip usages', () => {
    expect(
      surfaceLines(findTooltipChainUsages(readSourceTexts())),
      'a <Tooltip>, <CountryFlag> or <ProfileSummary> usage appeared or disappeared: add or retire ' +
        'its tooltip scenario in tests/visual/fixtures/suite-scenarios.ts (TOOLTIP_ROUTES) and ' +
        'update COVERED_TOOLTIP_HOSTS here',
    ).toEqual(surfaceLines(COVERED_TOOLTIP_HOSTS))
  })

  test('a planted new Tooltip consumer, or a retired one, makes the scan differ', () => {
    const real = readSourceTexts()
    const covered = surfaceLines(COVERED_TOOLTIP_HOSTS)
    const matchRow: SourceText = {
      relative: 'packages/design-system/src/composites/MatchRow/index.tsx',
      text: 'export const MatchRow = () => <Tooltip content="Elo"><button>1200</button></Tooltip>',
    }
    // The scanner, run over the real source plus the planted file, finds the planted usage...
    expect(findTooltipChainUsages([...real, matchRow])).toContainEqual({
      source: matchRow.relative,
      tag: 'Tooltip',
      count: 1,
    })
    // ...so its lines no longer equal the table's.
    expect(surfaceLines(findTooltipChainUsages([...real, matchRow]))).not.toEqual(covered)
    // A retired consumer: the same scan without CountryFlag's file.
    const withoutFlag = real.filter(({ relative }) => !/composites\/CountryFlag\//.test(relative))
    expect(withoutFlag.length).toBeLessThan(real.length)
    expect(surfaceLines(findTooltipChainUsages(withoutFlag))).not.toEqual(covered)
    // And the planted file in a comment only is not a usage.
    expect(findTooltipChainUsages([{ ...matchRow, text: '// <Tooltip content="Elo">' }])).toEqual(
      [],
    )
  })

  test('every route a covered usage claims has a tooltip scenario, and none is unclaimed', () => {
    expect(tooltipScenarioProblems(COVERED_TOOLTIP_HOSTS, TOOLTIP_SCENARIOS)).toEqual([])
  })

  test('a route whose tooltip scenario is removed is caught by name', () => {
    const without = TOOLTIP_SCENARIOS.filter((scenario) => scenario.route !== '/matches')
    expect(without.length).toBe(TOOLTIP_SCENARIOS.length - 1)
    expect(tooltipScenarioProblems(COVERED_TOOLTIP_HOSTS, without)).toEqual([
      '/matches: renders a Tooltip and no tooltip scenario opens it',
    ])
  })

  test('a tooltip scenario no covered usage claims is caught by name', () => {
    const lonely = COVERED_TOOLTIP_HOSTS.filter(
      (host) => !host.routes.includes('/matches') || host.routes.length > 1,
    ).map((host) => ({ ...host, routes: host.routes.filter((route) => route !== '/matches') }))
    expect(tooltipScenarioProblems(lonely, TOOLTIP_SCENARIOS)).toEqual([
      '/matches: a tooltip scenario no covered usage claims',
    ])
  })

  test('the usage counter ignores comments and counts a planted usage', () => {
    expect(countTooltipChainUsages('/* <Tooltip> */ // <CountryFlag>\nconst x = 1')).toEqual({
      Tooltip: 0,
      CountryFlag: 0,
      ProfileSummary: 0,
    })
    expect(
      countTooltipChainUsages('return <><Tooltip a="b" /><CountryFlag /><ProfileSummaryRow /></>'),
    ).toEqual({ Tooltip: 1, CountryFlag: 1, ProfileSummary: 0 })
  })

  test('tooltip scenario labels are unique, and a planted duplicate is caught', () => {
    // Labels are Playwright test titles in the keyboard and reduced-motion suites.
    expect(duplicateLabels(TOOLTIP_SCENARIOS)).toEqual([])
    expect(duplicateLabels([TOOLTIP_SCENARIOS[0], TOOLTIP_SCENARIOS[0]])).toEqual([
      TOOLTIP_SCENARIOS[0].label,
    ])
  })
})

// --- Routes derived from the route files (T681) ---------------------------------------------------

const PLAYER_PROFILE_IMPORT =
  "import { PlayerProfileContainer } from '../features/players/PlayerProfileContainer'"

test.describe('tooltip routes derived from the route files', () => {
  test('a route file name becomes its ROUTE_SCENARIOS label', () => {
    expect(routeLabelOfFile('dashboard.tsx')).toBe('/dashboard')
    expect(routeLabelOfFile('matches.index.tsx')).toBe('/matches')
    expect(routeLabelOfFile('matches.$gameId.tsx')).toBe('/matches/$gameId')
    expect(routeLabelOfFile('players.$profileId.index.tsx')).toBe('/players/$profileId')
    expect(routeLabelOfFile('players.$profileId.matches.tsx')).toBe('/players/$profileId/matches')
    expect(routeLabelOfFile('__root.tsx')).toBeNull()
    expect(routeLabelOfFile('index.tsx')).toBeNull()
  })

  test('every route importing a container that renders a ProfileSummary has a tooltip scenario', () => {
    expect(
      derivedRouteProblems(COVERED_TOOLTIP_HOSTS, readRouteTexts(), TOOLTIP_SCENARIOS),
    ).toEqual([])
  })

  test('the derivation finds exactly the routes the table claims for each container', () => {
    const routes = readRouteTexts()
    for (const host of COVERED_TOOLTIP_HOSTS.filter(isContainerHost)) {
      expect(routesImporting(containerName(host), routes), containerName(host)).toEqual(
        [...host.routes].sort((a, b) => a.localeCompare(b)),
      )
    }
  })

  test('a planted new route that imports PlayerProfileContainer is caught by name', () => {
    const planted: RouteText = {
      file: 'players.$profileId.settings.tsx',
      text: `${PLAYER_PROFILE_IMPORT}\nexport const Route = () => <PlayerProfileContainer profileId={1} />`,
    }
    expect(
      derivedRouteProblems(
        COVERED_TOOLTIP_HOSTS,
        [...readRouteTexts(), planted],
        TOOLTIP_SCENARIOS,
      ),
    ).toEqual([
      '/players/$profileId/settings: mounts PlayerProfileContainer, which renders a ProfileSummary, ' +
        'and no tooltip scenario opens a tooltip on it',
    ])
  })

  test('a commented-out import is not a mount', () => {
    const planted: RouteText = {
      file: 'players.$profileId.settings.tsx',
      text: `// ${PLAYER_PROFILE_IMPORT}\n/* ${PLAYER_PROFILE_IMPORT} */`,
    }
    expect(
      derivedRouteProblems(
        COVERED_TOOLTIP_HOSTS,
        [...readRouteTexts(), planted],
        TOOLTIP_SCENARIOS,
      ),
    ).toEqual([])
  })

  test('a container no route file imports is caught, so a failed derivation cannot pass for free', () => {
    expect(derivedRouteProblems(COVERED_TOOLTIP_HOSTS, [], TOOLTIP_SCENARIOS)).toEqual(
      COVERED_TOOLTIP_HOSTS.filter(isContainerHost).map(
        (host) =>
          `${containerName(host)}: no route file imports it, so its routes cannot be derived`,
      ),
    )
  })
})
