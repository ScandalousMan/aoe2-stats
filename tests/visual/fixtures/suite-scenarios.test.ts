// T676: what keeps the scenarios the four route suites run honest, in the way
// `app-routes-harness.test.ts` keeps `ROUTE_SCENARIOS` honest against the router. Four properties,
// each with its absence case planted rather than assumed:
//
// 1. every list a route renders is populated in some scenario — the suites cannot go back to
//    walking empty tables without this failing;
// 2. no fixture player carries an `avatar_hash` (constitution III: no suite reaches
//    `avatars.steamstatic.com`);
// 3. every `<Menu>` and `<Dialog>` an application route can open has a scenario — a new consumer
//    fails here until someone adds one;
// 4. scenario labels are unique (they are Playwright test titles) and every surface scenario knows
//    how to open its surface.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'
import { PLAYER_PROFILE_RESPONSE, ROUTE_SCENARIOS } from './app-routes-harness'
import {
  findAvatarHashes,
  POPULATED_FIXTURES,
  POPULATED_SCENARIOS,
  SUITE_SCENARIOS,
  SURFACE_SCENARIOS,
} from './suite-scenarios'

const rootDir = path.resolve(__dirname, '..', '..', '..')

// Routes whose body holds no list: nothing to populate.
const ROUTES_WITHOUT_A_LIST: ReadonlySet<string> = new Set([
  '/sign-in',
  '/privacy',
  '/privacy-notice',
  '/object',
])

test.describe('suite scenarios', () => {
  test('every route that renders a list has a populated scenario', () => {
    const missing = ROUTE_SCENARIOS.map((scenario) => scenario.label)
      .filter((label) => !ROUTES_WITHOUT_A_LIST.has(label))
      .filter(
        (label) => !POPULATED_SCENARIOS.some((populated) => populated.label.startsWith(label)),
      )
    expect(
      missing,
      `route(s) with a list and no populated scenario in suite-scenarios.ts: ${missing.join(', ')}`,
    ).toEqual([])
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

  test('scenario labels are unique', () => {
    const labels = SUITE_SCENARIOS.map((scenario) => scenario.label)
    const duplicates = labels.filter((label, index) => labels.indexOf(label) !== index)
    expect(duplicates, `duplicate scenario labels: ${duplicates.join(', ')}`).toEqual([])
  })

  test('every surface scenario opens its own surface', () => {
    const without = SURFACE_SCENARIOS.filter((scenario) => !scenario.prepare || !scenario.surface)
    expect(without.map((scenario) => scenario.label)).toEqual([])
  })
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

// Every JSX usage of `<Menu` / `<Dialog` outside stories and tests, with the scenario that opens
// it. A route-reachable surface not listed here fails `finds exactly the covered surfaces` below
// until a scenario exists for it — "one scenario per openable surface" kept true by the build, not
// by remembering.
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

test.describe('openable surfaces', () => {
  test('finds exactly the covered surfaces', () => {
    const found: Array<{ source: string; tag: string; count: number }> = []
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
    const covered = COVERED_SURFACES.map(({ source, tag, count }) => ({ source, tag, count }))
    const key = (entry: { source: string; tag: string }) => `${entry.source}#${entry.tag}`
    expect(
      found.sort((a, b) => key(a).localeCompare(key(b))),
      'a <Menu> or <Dialog> usage appeared or disappeared: add or retire its scenario in ' +
        'tests/visual/fixtures/suite-scenarios.ts and update COVERED_SURFACES here',
    ).toEqual(covered.sort((a, b) => key(a).localeCompare(key(b))))
  })

  test('each covered surface has the scenarios it claims, of the right kind', () => {
    for (const surface of COVERED_SURFACES) {
      for (const fragment of surface.scenarios) {
        const matching = SURFACE_SCENARIOS.filter((scenario) => scenario.label.includes(fragment))
        expect(
          matching.length,
          `no surface scenario's label contains "${fragment}"`,
        ).toBeGreaterThan(0)
        for (const scenario of matching) {
          expect(scenario.surface, `${scenario.label}: wrong surface kind`).toBe(
            surface.tag === 'Menu' ? 'menu' : 'dialog',
          )
        }
      }
    }
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
