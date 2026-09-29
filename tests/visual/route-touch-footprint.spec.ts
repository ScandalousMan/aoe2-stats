// T674 (production-readiness item 13, third of four halves): touch footprints, at 375px, in both
// themes, against the minimum interactive footprint decided 2026-09-28 by `product-designer` on the
// project owner's arbitration: 44×44 CSS px in both axes (WCAG 2.5.5, `packages/design-system/
// specs/README.md`'s "Minimum interactive footprint"), with one exemption — a `Link` the DOM marks
// `data-variant="inline"` inside running prose, read from that marker and never from a layout
// heuristic. An element hidden until focused (`SiteHeader`'s skip link) is measured in the state
// that reveals it, never skipped — `walkTabOrder` (shared with the other two Tab-driven sub-suites)
// already focuses every candidate in turn before this file ever reads its geometry, so the reveal is
// automatic rather than a special case this file has to build.
//
// FR-056: "Every interactive target MUST meet the minimum touch footprint at widths where touch is
// expected, and a target MUST NOT be enlarged by an overlay that intercepts unrelated interaction."
// This sub-suite asserts the floor; the "not enlarged by an overlay" half is a source-level property
// (README's own "forbidden: enlarging a target with an overlay" rule) with nothing a bounding-box
// sweep alone can observe, so it stays a spec rule rather than a geometry assertion here.
import { test } from '@playwright/test'
import {
  assertThemeApplied,
  createAppServerHarness,
  hasBuild,
  ROUTE_SCENARIOS,
  seedThemeOverride,
  waitForFontsReady,
} from './fixtures/app-routes-harness'
import { assertTouchFootprint } from './fixtures/touch-footprint'

const harness = createAppServerHarness('4177')

// 375×667 is this project's own mobile review width (`scripts/visual/review-widths.mjs`;
// `app-routes.spec.ts`'s own sibling suite captures desktop only). `isMobile`/`hasTouch` are
// deliberately not set: this sweep reads computed geometry, never dispatches a touch event, so
// Chromium's own touch-input emulation has nothing to change here.
const MOBILE_VIEWPORT = { width: 375, height: 667 }

test.use({ viewport: MOBILE_VIEWPORT })

test.describe('touch footprints at 375px, every route, both themes', () => {
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
        test(`${scenario.label} — every non-exempt interactive target clears 44×44 at 375px (${theme})`, async ({
          page,
        }) => {
          await seedThemeOverride(page, theme)
          await scenario.stub(page)

          await page.goto(`${harness.baseUrl}${scenario.path}`)
          await page.getByRole('main').waitFor({ state: 'visible' })
          await assertThemeApplied(page, theme)
          await waitForFontsReady(page)

          await assertTouchFootprint(page, `${scenario.label} (${theme})`)
        })
      }
    }
  }
})
