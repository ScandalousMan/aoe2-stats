// T748: every app-route suite runs the built application at one instant, `ROUTE_SUITE_NOW_MS`, so
// "Updated … ago" (`formatFreshness`) and a match row's `playedAtRelative` read the same text on
// the day a baseline is captured and on every later day. This is the test that fails when a route
// renders against the real clock. It exercises the setup every suite shares (`gotoScenario`, and
// `enterScenario` on top of it), not a copy of it, and has two halves:
//
//   1. behaviour: after `gotoScenario`, the page's own `Date.now()` is within a minute of the
//      constant for every scenario in `ROUTE_SCENARIOS`, and a signed-in route says "Updated 45
//      days ago", the text no real day can produce (it was 50 days when this was filed);
//   2. coverage: no `route-*.spec.ts` navigates by any other way than `gotoScenario`, since a
//      suite that called `page.goto` itself would skip the clock install without failing (1).
import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'
import {
  createAppServerHarness,
  freezeRouteClock,
  gotoScenario,
  hasBuild,
  ROUTE_SCENARIOS,
  ROUTE_SUITE_NOW_MS,
} from './app-routes-harness'
import { enterScenario, SUITE_SCENARIOS } from './suite-scenarios'

const harness = createAppServerHarness('4181')

// The page's clock keeps running from the installed instant; a minute is far more than any
// scenario takes to reach this read and far less than the day it takes to notice the real clock.
const FLOW_ALLOWANCE_MS = 60_000

// The one assertion on a page's clock, so its failure always names the instant it read and the
// instant every route suite is meant to run at.
function expectSuiteClock(label: string, read: number): void {
  const message =
    `${label} read ${new Date(read).toISOString()} from its own clock, but every route suite ` +
    `runs at ${new Date(ROUTE_SUITE_NOW_MS).toISOString()} (T748): a route rendering against ` +
    'the real clock shows different relative times ("Updated 45 days ago", "3 hours ago") on ' +
    'every day a baseline is captured.'
  expect(read - ROUTE_SUITE_NOW_MS, message).toBeGreaterThanOrEqual(0)
  expect(read - ROUTE_SUITE_NOW_MS, message).toBeLessThan(FLOW_ALLOWANCE_MS)
}

function scenarioNamed(label: string) {
  const scenario = ROUTE_SCENARIOS.find((candidate) => candidate.label === label)
  if (!scenario) throw new Error(`no ROUTE_SCENARIOS entry named '${label}'`)
  return scenario
}

test.describe('the app-route suites run at one fixed instant', () => {
  // Serial, like `goto-scenario.test.ts`: the tests share one static server per file, and
  // `harness.stop()` from the worker that started it would pull it from under a parallel worker.
  test.describe.configure({ mode: 'serial' })

  test('no route suite navigates around gotoScenario', () => {
    const visualDir = path.resolve(__dirname, '..')
    const specs = readdirSync(visualDir).filter((name) => /^route-.*\.spec\.ts$/.test(name))
    expect(specs.length, 'expected to find the route-*.spec.ts suites').toBeGreaterThanOrEqual(4)
    for (const spec of specs) {
      const source = readFileSync(path.join(visualDir, spec), 'utf8').replace(
        /\/\*[\s\S]*?\*\/|(^|\s)\/\/.*$/gm,
        '$1',
      )
      expect(
        source,
        `${spec} calls page.goto itself, which skips the clock install in gotoScenario — ` +
          'navigate with enterScenario/gotoScenario from ./fixtures instead.',
      ).not.toMatch(/\.goto\(/)
    }
  })

  if (!hasBuild && process.env.CI) {
    test('apps/web/dist must be built before this suite runs in CI', () => {
      throw new Error(
        'apps/web/dist has not been built. `.github/workflows/pr.yml` always runs ' +
          '`pnpm --filter web build` before this suite.',
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

    test('installing the clock twice on one page is a no-op', async ({ page }) => {
      await freezeRouteClock(page)
      await freezeRouteClock(page)
      await scenarioNamed('/sign-in').stub(page)
      await gotoScenario(page, scenarioNamed('/sign-in'), harness.baseUrl)
      expectSuiteClock('/sign-in', await page.evaluate(() => Date.now()))
    })

    for (const scenario of ROUTE_SCENARIOS) {
      test(`${scenario.label}: the page's Date.now() is the suite's instant, not the real one`, async ({
        page,
      }) => {
        await scenario.stub(page)
        await gotoScenario(page, scenario, harness.baseUrl)

        const pageNow = await page.evaluate(() => Date.now())
        const pageDate = await page.evaluate(() => new Date().getTime())
        expectSuiteClock(scenario.label, pageNow)
        expectSuiteClock(scenario.label, pageDate)
      })
    }

    test('/dashboard says "Updated 45 days ago" whatever day the suite runs', async ({ page }) => {
      const dashboard = scenarioNamed('/dashboard')
      await dashboard.stub(page)
      await gotoScenario(page, dashboard, harness.baseUrl)
      await expect(page.getByText(/Updated 45 days ago/)).toBeVisible()
    })

    test('/matches says "Updated 45 days ago" whatever day the suite runs', async ({ page }) => {
      const matches = scenarioNamed('/matches')
      await matches.stub(page)
      await gotoScenario(page, matches, harness.baseUrl)
      await expect(page.getByText(/Updated 45 days ago/)).toBeVisible()
    })

    test('enterScenario, which every route suite uses, reaches the same clock', async ({
      page,
    }) => {
      const scenario = SUITE_SCENARIOS[0]
      if (!scenario) throw new Error('SUITE_SCENARIOS is empty')
      await enterScenario(page, scenario, harness.baseUrl, 'light')
      expectSuiteClock(scenario.label, await page.evaluate(() => Date.now()))
    })
  }
})
