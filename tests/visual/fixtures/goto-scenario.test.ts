// PR #102 review finding (confirmed by running): `gotoScenario` used to call
// `page.waitForURL('**' + (scenario.landedPath ?? scenario.path))` right after `page.goto`.
// Playwright 1.62's `waitForURL` returns immediately when the current URL already satisfies the
// pattern — and for every scenario whose `landedPath` equals its own `path` (nine of the eleven in
// `ROUTE_SCENARIOS`), the URL right after `goto` already matches, trivially, before the app's own
// `beforeLoad` guards have had a chance to run. That left `gotoScenario` checking nothing for those
// nine: `/favourites` stubbed with a signed-out session settles at `/sign-in?return=%2Ffavourites`
// (`routes/favourites.tsx`'s `beforeLoad` redirect), `<main>` renders there too, and the old
// `gotoScenario` never threw — every caller (`route-keyboard.spec.ts`, `route-focus-visibility.spec.ts`,
// `route-touch-footprint.spec.ts`, `route-reduced-motion.spec.ts`, `app-routes.spec.ts`'s own
// per-route loop) would have silently walked the sign-in page under the `/favourites` label.
//
// This is a regression test on `gotoScenario` itself, not on any one route: it reuses
// `ROUTE_SCENARIOS`' own `/favourites` entry, once unmodified (CONTROL) and once with its stub
// swapped for the `/sign-in` scenario's own signed-out stub (RED) — the same substitution the
// reviewer used to confirm the defect. It needs the built `apps/web/dist` and a real server the way
// every `route-*.spec.ts` file does, so it shares `createAppServerHarness` rather than inventing its
// own bootstrap.
import { expect, test } from '@playwright/test'
import {
  createAppServerHarness,
  gotoScenario,
  hasBuild,
  ROUTE_SCENARIOS,
} from './app-routes-harness'

const harness = createAppServerHarness('4179')

function scenarioNamed(label: string) {
  const scenario = ROUTE_SCENARIOS.find((candidate) => candidate.label === label)
  if (!scenario) {
    throw new Error(
      `no ROUTE_SCENARIOS entry named '${label}' — has it been renamed or removed in ` +
        'tests/visual/fixtures/app-routes-harness.ts?',
    )
  }
  return scenario
}

test.describe('gotoScenario actually verifies where a navigation lands', () => {
  test.describe.configure({ mode: 'serial' })

  // Mirrors the same CI-vs-local distinction every other `route-*.spec.ts` file makes: a bare
  // `test.skip` would report this suite as passed whether `apps/web/dist` is merely un-built locally
  // or missing because a CI build step failed.
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

    test('CONTROL: the unmodified /favourites scenario lands on /favourites', async ({ page }) => {
      const favourites = scenarioNamed('/favourites')
      await favourites.stub(page)

      await gotoScenario(page, favourites, harness.baseUrl)

      expect(new URL(page.url()).pathname).toBe('/favourites')
    })

    test('RED: /favourites stubbed signed-out redirects to /sign-in, and gotoScenario must catch it', async ({
      page,
    }) => {
      const favourites = scenarioNamed('/favourites')
      const signedOutStub = scenarioNamed('/sign-in').stub
      const favouritesSignedOut = { ...favourites, stub: signedOutStub }

      await favouritesSignedOut.stub(page)

      let thrown: unknown
      try {
        await gotoScenario(page, favouritesSignedOut, harness.baseUrl)
      } catch (error) {
        thrown = error
      }

      expect(
        thrown,
        "gotoScenario resolved without throwing for '/favourites' stubbed signed-out, but " +
          "routes/favourites.tsx's beforeLoad guard redirects an unauthenticated visitor to " +
          '/sign-in — gotoScenario must throw naming the scenario, the expected pathname and the ' +
          'actual landed URL instead of silently letting every caller walk the sign-in page under ' +
          "the '/favourites' label.",
      ).toBeInstanceOf(Error)
      const message = (thrown as Error).message
      expect(message).toContain('/favourites')
      expect(message).toContain('/sign-in')
    })
  }
})
