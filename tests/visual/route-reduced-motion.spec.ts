// T674 (production-readiness item 13, fourth of four halves): reduced motion, at route level, in
// both themes — `page.emulateMedia({ reducedMotion: 'reduce' })` before navigation, then asserting
// every element computes a near-zero transition/animation duration on the real route.
// `packages/design-system/tokens/motion.json`'s own `$comment` names the mechanism this checks:
// every transition composes `motion-reduce:duration-0` and every loop (`spin`, `pulse`) is gated
// behind `motion-safe:`, so under a reduced-motion preference no transition utility keeps a nonzero
// duration and no looping animation utility applies at all. `Table.test.tsx`/`Menu.test.tsx` already
// unit-test this per component (quickstart.md's own T577 walk); this route-level sweep confirms
// nothing upstream of the component — a route transition, a layout animation, a reset this package
// does not own — reintroduces motion the component itself already suppresses.
//
// FR-055 / SC-016: "Under a reduced-motion preference, every transition MUST be reduced to no
// perceptible duration and every looping animation MUST stop on its resting frame." A blanket sweep
// of every element's own computed style is the direct reading of "every transition" and "every
// looping animation" — not scoped to a hand-picked list of elements `tokens/motion.json` is known to
// govern today, which would silently stop covering a future component that reaches for a `duration-*`
// utility without also reaching for `motion-reduce:duration-0`.
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
import { assertReducedMotion } from './fixtures/reduced-motion'

const harness = createAppServerHarness('4178')

test.describe('reduced motion, every route, both themes', () => {
  test.describe.configure({ mode: 'serial' })

  // Mirrors `app-routes.spec.ts`'s own CI-vs-local distinction (PR #102 review finding, low): a
  // bare `test.skip` reports this whole suite as passed whether `apps/web/dist` is missing because
  // a developer has not built yet or because a CI misconfiguration skipped the build step — only
  // `process.env.CI` (set by every GitHub Actions runner) tells the two cases apart.
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
        test(`${scenario.label} — no transition or looping animation keeps a perceptible duration (${theme})`, async ({
          page,
        }) => {
          // Set before navigation (this file's own header comment) so the reduced-motion preference
          // is already in effect for the very first render — never a post-load toggle that could
          // race a transition already mid-flight.
          await page.emulateMedia({ reducedMotion: 'reduce' })
          await seedThemeOverride(page, theme)
          await scenario.stub(page)

          await gotoScenario(page, scenario, harness.baseUrl)
          await page.getByRole('main').waitFor({ state: 'visible' })
          await assertThemeApplied(page, theme)
          await waitForFontsReady(page)

          await assertReducedMotion(page, `${scenario.label} (${theme})`)
        })
      }
    }
  }
})
