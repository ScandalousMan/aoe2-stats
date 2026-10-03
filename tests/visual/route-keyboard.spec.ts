// T674 (production-readiness item 13, first of four halves): keyboard operation, at route level,
// in both themes — T674's own task text in `specs/005-design-system-foundations/tasks.md`: "a
// `page.keyboard.press('Tab')` walk per route in both themes, asserting the focused element stays
// inside the route's landmarks and every interactive element is reached once — no screenshot
// needed." `tests/visual/app-routes.spec.ts` (T108/T553) already counts landmarks and screenshots
// every route; this file adds the keyboard axis that leaves untouched.
//
// FR-049: "Every interactive element MUST be reachable and operable by keyboard, in an order that
// matches its visual order, with no trap outside a modal surface that defines its own." A route at
// rest or populated is walked by Tab alone, with no modal open: a trap surfaces as `assertFullTabCoverage`'s step-count guard (the walk producing more stops than
// candidates — see `keyboard-walk.ts`'s own comment on why a separate wrap-detection guard was
// removed), not through containment. `assertStopsInsideChrome`, asserted separately below, checks
// the containment `tests/visual/focus-ring.spec.ts` assumes implicitly: every stop stays inside the
// route's one `main` landmark or its `header`/`footer` chrome.
import { test } from '@playwright/test'
import { createAppServerHarness, hasBuild } from './fixtures/app-routes-harness'
import {
  assertFullTabCoverage,
  assertStopsInsideChrome,
  walkTabOrder,
} from './fixtures/keyboard-walk'
import { assertSurfaceKeyboard, walkOpenSurface } from './fixtures/open-surface'
import { enterScenario, SUITE_SCENARIOS } from './fixtures/suite-scenarios'

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

    // T676: `SUITE_SCENARIOS` is the routes at rest (`ROUTE_SCENARIOS`), the same routes with every
    // list populated, and one scenario per openable `Dialog`/`Menu`. A route at rest or populated
    // gets the Tab walk below; a scenario that leaves a surface open gets that surface's own
    // keyboard contract (`fixtures/open-surface.ts`) instead — Tab cycling inside a `Dialog`,
    // roving-tabindex arrows through a `Menu` — because a Tab walk over the page behind an open
    // modal measures the wrong thing.
    for (const scenario of SUITE_SCENARIOS) {
      for (const theme of ['light', 'dark'] as const) {
        const claim = scenario.surface
          ? `the open ${scenario.surface} honours its keyboard contract`
          : "every interactive element is reachable, in order, inside the route's chrome"
        test(`${scenario.label} — ${claim} (${theme})`, async ({ page }) => {
          const external = await enterScenario(page, scenario, harness.baseUrl, theme)
          const context = `${scenario.label} (${theme})`

          if (scenario.surface) {
            assertSurfaceKeyboard(await walkOpenSurface(page, scenario.surface), context)
          } else {
            const result = await walkTabOrder(page)

            // FR-049's "no trap": every stop the walk actually reaches sits inside the route's one
            // main landmark or its header/footer chrome — never off in a detached or hidden branch
            // of the DOM a real keyboard user could not have reached either.
            assertStopsInsideChrome(result.steps, context)

            // FR-049's "reachable, in order, with no trap": every candidate is reached exactly
            // once, in DOM order. See `assertFullTabCoverage` for what each guard catches on its
            // own.
            assertFullTabCoverage(result, context)
          }

          external.assertNone(context)
        })
      }
    }
  }
})
