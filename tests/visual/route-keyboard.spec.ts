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
import { expect, test } from '@playwright/test'
import { createAppServerHarness, hasBuild } from './fixtures/app-routes-harness'
import {
  assertFullTabCoverage,
  assertStopsInsideChrome,
  walkTabOrder,
} from './fixtures/keyboard-walk'
import { assertSurfaceKeyboard, walkOpenSurface } from './fixtures/open-surface'
import { enterScenario, SUITE_SCENARIOS, TOOLTIP_SCENARIOS } from './fixtures/suite-scenarios'
import { assertTooltipKeyboard, walkOpenTooltip } from './fixtures/tooltip-open'

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
    // T744: `SUITE_SCENARIOS` also holds `BRANCH_SCENARIOS` (`fixtures/suite-scenarios.ts`) — each route's
    // error, transient and unrendered-empty branches, and the two held loading states — so this loop runs
    // them too, and `enterScenario` has asserted the branch is on screen before anything below measures it.
    for (const scenario of SUITE_SCENARIOS) {
      for (const theme of ['light', 'dark'] as const) {
        const claim = scenario.surface
          ? `the open ${scenario.surface} honours its keyboard contract`
          : "every interactive element is reachable, in order, inside the route's chrome"
        test(`${scenario.label} — ${claim} (${theme})`, async ({ page }) => {
          // T744: a defect the scenario is known to show here runs as an expected failure — see
          // `SuiteScenario.knownDefects`.
          test.fail(scenario.knownDefects?.keyboard !== undefined, scenario.knownDefects?.keyboard)
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

    // T745: nothing above judges where focus lands once an action has run. A keyboard user who
    // presses "Export my data" on /privacy stays on that button for the whole wait and after it:
    // a `Button` in `loading` is `aria-disabled`, never natively `disabled`, because a focused
    // element that becomes `:disabled` drops focus to `body` (measured in Chromium on this very
    // route). `enterScenario` ends with the panel `ready` (its `prepare` Tabs to the button, presses
    // Enter and waits for the download link) and does not move focus afterwards, so the assertion
    // reads it before any walk resets the starting point. The exact button is asserted, not merely
    // "not body": a focus move elsewhere would contradict the decision just as much.
    const exportReady = SUITE_SCENARIOS.find(
      (scenario) => scenario.label === '/privacy (export ready)',
    )
    if (!exportReady) throw new Error("SUITE_SCENARIOS has no '/privacy (export ready)' scenario")
    for (const theme of ['light', 'dark'] as const) {
      test(`/privacy (export ready) — focus is still on "Export my data" once the export reads ready, never on the document body (${theme})`, async ({
        page,
      }) => {
        const external = await enterScenario(page, exportReady, harness.baseUrl, theme)
        const context = `/privacy (export ready) (${theme})`

        const bodyHoldsFocus = await page.evaluate(() => document.activeElement === document.body)
        expect(bodyHoldsFocus, `${context}: focus fell to document.body`).toBe(false)
        await expect(
          page.getByRole('button', { name: 'Export my data' }),
          `${context}: focus left the button that started the export`,
        ).toBeFocused()

        external.assertNone(context)
      })
    }

    // T681: the `Tooltip` is no `Menu` or `Dialog`, so the loop above never opens it. Each route
    // that renders one is entered, the tooltip opened by Tab to its trigger (`:focus-visible` opens
    // it, `enterScenario` runs the scenario's `prepare`), and its keyboard contract
    // (`packages/design-system/specs/tooltip.md` §8) walked: Escape dismisses it, focus stays on the
    // trigger.
    for (const scenario of TOOLTIP_SCENARIOS) {
      for (const theme of ['light', 'dark'] as const) {
        test(`${scenario.label} — Escape dismisses the tooltip and focus stays on its trigger (${theme})`, async ({
          page,
        }) => {
          const external = await enterScenario(page, scenario, harness.baseUrl, theme)
          const context = `${scenario.label} (${theme})`

          assertTooltipKeyboard(await walkOpenTooltip(page), context)

          external.assertNone(context)
        })
      }
    }
  }
})
