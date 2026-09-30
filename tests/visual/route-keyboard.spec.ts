// T674 (production-readiness item 13, first of four halves): keyboard operation, at route level,
// in both themes — T674's own task text in `specs/005-design-system-foundations/tasks.md`: "a
// `page.keyboard.press('Tab')` walk per route in both themes, asserting the focused element stays
// inside the route's landmarks and every interactive element is reached once — no screenshot
// needed." `tests/visual/app-routes.spec.ts` (T108/T553) already counts landmarks and screenshots
// every route; this file adds the keyboard axis that leaves untouched.
//
// FR-049: "Every interactive element MUST be reachable and operable by keyboard, in an order that
// matches its visual order, with no trap outside a modal surface that defines its own." No modal is
// ever opened by this walk (a route-level Tab walk, not a component interaction test): a trap
// surfaces as `assertFullTabCoverage`'s step-count guard (the walk producing more stops than
// candidates — see `keyboard-walk.ts`'s own comment on why a separate wrap-detection guard was
// removed), not through containment. `assertStopsInsideChrome`, asserted separately below, checks
// the containment `tests/visual/focus-ring.spec.ts` assumes implicitly: every stop stays inside the
// route's one `main` landmark or its `header`/`footer` chrome.
import { test } from '@playwright/test'
import {
  assertThemeApplied,
  createAppServerHarness,
  gotoScenario,
  hasBuild,
  ROUTE_SCENARIOS,
  seedThemeOverride,
  waitForFontsReady,
} from './fixtures/app-routes-harness'
import {
  assertFullTabCoverage,
  assertStopsInsideChrome,
  walkTabOrder,
} from './fixtures/keyboard-walk'

const harness = createAppServerHarness('4175')

test.describe('keyboard operation, every route, both themes', () => {
  test.describe.configure({ mode: 'serial' })

  // PR #102 review finding (low, mirrored from `app-routes.spec.ts`'s own identical remediation): a
  // bare `test.skip` reports this whole suite as passed whether `apps/web/dist` is missing because
  // no developer has built it yet, or because a CI misconfiguration skipped the build step.
  // `process.env.CI` (set by every GitHub Actions runner) is what tells the two cases apart; only a
  // developer running this file locally without having built first gets the skip.
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

    for (const scenario of ROUTE_SCENARIOS) {
      for (const theme of ['light', 'dark'] as const) {
        test(`${scenario.label} — every interactive element is reachable, in order, inside the route's chrome (${theme})`, async ({
          page,
        }) => {
          await seedThemeOverride(page, theme)
          await scenario.stub(page)

          await gotoScenario(page, scenario, harness.baseUrl)
          await page.getByRole('main').waitFor({ state: 'visible' })
          // PR #102 review finding (low): proves the theme was actually *painted*, not merely
          // seeded — `seedThemeOverride` only writes the storage key; `ThemeProvider.tsx` is what
          // reads it and paints `data-theme`, and the two can drift.
          await assertThemeApplied(page, theme)
          await waitForFontsReady(page)

          const result = await walkTabOrder(page)

          // FR-049's "no trap": every stop the walk actually reaches sits inside the route's one
          // main landmark or its header/footer chrome — never off in a detached or hidden branch of
          // the DOM a real keyboard user could not have reached either.
          assertStopsInsideChrome(result.steps, `${scenario.label} (${theme})`)

          // FR-049's "reachable, in order, with no trap": every candidate is reached exactly once,
          // in DOM order. See `assertFullTabCoverage` for what each guard catches on its own.
          assertFullTabCoverage(result, `${scenario.label} (${theme})`)
        })
      }
    }
  }
})
