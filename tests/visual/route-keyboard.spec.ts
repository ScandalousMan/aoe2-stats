// T674 (production-readiness item 13, first of four halves): keyboard operation, at route level,
// in both themes — `packages/design-system/specs/README.md`'s "Verification-coverage gap register"
// row 1's own description: "a `page.keyboard.press('Tab')` walk per route in both themes, asserting
// the focused element stays inside the route's landmarks and every interactive element is reached
// once — no screenshot needed." `tests/visual/app-routes.spec.ts` (T108/T553) already counts
// landmarks and screenshots every route; this file adds the keyboard axis that leaves untouched.
//
// FR-049: "Every interactive element MUST be reachable and operable by keyboard, in an order that
// matches its visual order, with no trap outside a modal surface that defines its own." No modal is
// ever opened by this walk (a route-level Tab walk, not a component interaction test), so "no trap"
// reduces to "every stop stays inside the route's one `main` landmark or its `header`/`footer`
// chrome" — the same containment `tests/visual/focus-ring.spec.ts` assumes implicitly and this file
// makes an explicit, mechanical assertion.
import { test, expect } from '@playwright/test'
import {
  createAppServerHarness,
  hasBuild,
  ROUTE_SCENARIOS,
  seedThemeOverride,
  waitForFontsReady,
} from './fixtures/app-routes-harness'
import { assertFullTabCoverage, walkTabOrder } from './fixtures/keyboard-walk'

const harness = createAppServerHarness('4175')

test.describe('keyboard operation, every route, both themes', () => {
  test.describe.configure({ mode: 'serial' })

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

  for (const scenario of ROUTE_SCENARIOS) {
    for (const theme of ['light', 'dark'] as const) {
      test(`${scenario.label} — every interactive element is reachable, in order, inside the route's chrome (${theme})`, async ({
        page,
      }) => {
        await seedThemeOverride(page, theme)
        await scenario.stub(page)

        await page.goto(`${harness.baseUrl}${scenario.path}`)
        await page.getByRole('main').waitFor({ state: 'visible' })
        await waitForFontsReady(page)

        const result = await walkTabOrder(page)

        // FR-049's "no trap": every stop the walk actually reaches sits inside the route's one
        // main landmark or its header/footer chrome — never off in a detached or hidden branch of
        // the DOM a real keyboard user could not have reached either.
        for (const step of result.steps) {
          expect(
            step.insideChrome,
            `${scenario.label} (${theme}): Tab landed on a <${step.tag}> "${step.name}" outside ` +
              `main/header/footer`,
          ).toBe(true)
        }

        // FR-049's "reachable, in order, with no trap": every candidate is reached exactly once,
        // in DOM order, and the walk closed the cycle rather than exhausting its step budget mid
        // trap. See `assertFullTabCoverage` for what each of the four guards catches on its own.
        assertFullTabCoverage(result, `${scenario.label} (${theme})`)
      })
    }
  }
})
