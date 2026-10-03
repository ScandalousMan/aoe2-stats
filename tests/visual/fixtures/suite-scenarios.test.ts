// T676: what keeps the scenarios the four route suites run honest, in the way
// `app-routes-harness.test.ts` keeps `ROUTE_SCENARIOS` honest against the router. Five properties,
// each with its absence case planted rather than assumed (every guard below is a function the real
// check and its planted case both call, so the two cannot drift):
//
// 1. every entry of the per-route list inventory in `./suite-scenarios` is declared by a populated
//    scenario of *that route* (exact match, never a label prefix), and in a browser each populated
//    scenario renders what it declares and shows no error callout or loading region, judged inside
//    `enterScenario` so the four route suites cannot skip it. Error, empty and transient branches
//    are not reached; two success-branch controls (the `objected` `ArchivalControl`, the
//    `DataExportPanel` `ready` link) are not either, and belong to T682;
// 2. no fixture player carries an `avatar_hash` (constitution III: no suite reaches
//    `avatars.steamstatic.com`);
// 3. every `<Menu>` and `<Dialog>` an application route can open has a scenario — a new consumer
//    fails here until someone adds one;
// 4. scenario labels are unique (they are Playwright test titles);
// 5. every surface scenario knows how to open its surface.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'
import {
  createAppServerHarness,
  hasBuild,
  fulfillJson,
  PLAYER_PROFILE_RESPONSE,
  PROFILES_RESPONSE,
  ROUTE_SCENARIOS,
  SAMPLE_GAME_ID,
  SIGNED_IN_ME,
  stubMe,
} from './app-routes-harness'
import {
  enterScenario,
  findAvatarHashes,
  POPULATED_FIXTURES,
  POPULATED_SCENARIOS,
  type PopulatedScenario,
  ROUTE_REQUIRED_LISTS,
  SUITE_SCENARIOS,
  type SuiteScenario,
  SURFACE_SCENARIOS,
  unpopulatedLists,
} from './suite-scenarios'

const rootDir = path.resolve(__dirname, '..', '..', '..')

// Routes whose body holds no list: nothing to populate.
const ROUTES_WITHOUT_A_LIST: ReadonlySet<string> = new Set([
  '/sign-in',
  '/privacy',
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
    // whatever the data is, so declaring it proved nothing.
    expect(ROUTE_REQUIRED_LISTS['/dashboard']).toEqual(['rating rows'])
    const dashboard = POPULATED_SCENARIOS.find((scenario) => scenario.route === '/dashboard')
    expect(dashboard?.renders.map((entry) => entry.name)).toEqual(['rating rows'])
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
// not by remembering. `Tooltip` is deliberately not here: it is not an openable surface this
// suite opens (T681).
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
