// Remediation of review finding M2 on PR #102 (T674, `specs/005-design-system-foundations`):
// `ROUTE_SCENARIOS` in `./app-routes-harness` used to be a hand-written list with nothing keeping
// it in sync with `apps/web/src/routes/` — a new route file could ship with no scenario, and every
// one of the four route-level suites this fixture backs (`route-keyboard`, `route-focus-visibility`,
// `route-touch-footprint`, `route-reduced-motion`) plus `app-routes.spec.ts` itself would silently
// never walk it.
//
// This derives the route list from `apps/web/src/routeTree.gen.ts` — TanStack Router's own
// generated answer to "what routes exist" — rather than `glob`-ing `apps/web/src/routes/` and
// reimplementing its file-route conventions (nested layouts, `__root`, index routes,
// trailing-slash trimming on a navigation target). It reads that file as *text*, never as a
// module: every concrete route ultimately imports its own feature container
// (`apps/web/src/routes/dashboard.tsx` -> `DashboardContainer` -> `game-assets`'s
// `civilisationIcon`/`mapThumbnail`/`countryFlag`), and `game-assets/src/index.ts` resolves its own
// coverage set through Vite's `import.meta.glob` — a build-time macro Vite itself expands, which
// has no meaning under Playwright's plain esbuild transform and throws (`ReferenceError: exports is
// not defined`) the moment anything actually imports that module graph outside a Vite pipeline.
// `.update({ id: '...', path: '...', ... })` is the one shape TanStack Router's code generator
// emits once per concrete route, independent of that graph, so scraping its `id` literals is this
// test's source of truth: identical to walking the real `routeTree.children` at runtime (verified
// against `@tanstack/router-core`'s `BaseRoute._addFileChildren`, which is exactly
// `Object.values()` of the object this generated file passes it), without ever evaluating a route
// component.
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'
import { ROUTE_SCENARIOS } from './app-routes-harness'

const routeTreeFile = path.resolve(
  __dirname,
  '..',
  '..',
  '..',
  'apps',
  'web',
  'src',
  'routeTree.gen.ts',
)

// `index.tsx` (id `/`) is the one route this application declares that carries no scenario: it
// only ever redirects (to `/sign-in` or `/dashboard`, both of which do have their own scenario),
// painting no landmark of its own to walk — `app-routes-harness.ts`'s own module comment on
// `ROUTE_SCENARIOS` carries the same exception.
const NO_SCENARIO_NEEDED: ReadonlySet<string> = new Set(['/'])

// TanStack Router trims a trailing slash off an index route's own id when naming it as a
// navigation target (`routeTree.gen.ts`'s generated `FileRoutesByTo`: `/matches/` -> `/matches`,
// `/players/$profileId/` -> `/players/$profileId`) — `ROUTE_SCENARIOS`' own labels already follow
// that convention, so this normalizes the raw id the same way before comparing, rather than asking
// the fixture to restate the router's own trimming rule.
function toScenarioLabel(id: string): string {
  return id.length > 1 && id.endsWith('/') ? id.slice(0, -1) : id
}

function declaredRoutePaths(): string[] {
  const source = readFileSync(routeTreeFile, 'utf-8')
  const ids = Array.from(source.matchAll(/\.update\(\{\s*\n\s*id:\s*'([^']+)'/g)).map(
    (match) => match[1],
  )
  expect(
    ids.length,
    `found no '.update({ id: ... })' calls in ${routeTreeFile} — has TanStack Router's code ` +
      'generator changed its output shape? This guard needs updating to match.',
  ).toBeGreaterThan(0)
  return Array.from(new Set(ids.map(toScenarioLabel)))
}

test.describe('ROUTE_SCENARIOS tracks apps/web/src/routeTree.gen.ts (PR #102 review finding M2)', () => {
  test('every route the router declares has a matching scenario', () => {
    const scenarioLabels = new Set(ROUTE_SCENARIOS.map((scenario) => scenario.label))
    const missing = declaredRoutePaths().filter(
      (routePath) => !NO_SCENARIO_NEEDED.has(routePath) && !scenarioLabels.has(routePath),
    )

    expect(
      missing,
      `apps/web/src/routeTree.gen.ts declares a route with no matching ROUTE_SCENARIOS entry: ` +
        `${missing.join(', ')}. Add a scenario for it in tests/visual/fixtures/app-routes-harness.ts.`,
    ).toEqual([])
  })

  test('every scenario names a route the router actually declares', () => {
    const declared = new Set(declaredRoutePaths())
    const orphaned = ROUTE_SCENARIOS.map((scenario) => scenario.label).filter(
      (label) => !declared.has(label),
    )

    expect(
      orphaned,
      `ROUTE_SCENARIOS names a route apps/web/src/routeTree.gen.ts does not declare: ` +
        `${orphaned.join(', ')}. Fix or remove the scenario in tests/visual/fixtures/app-routes-harness.ts.`,
    ).toEqual([])
  })
})
