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
import { test, expect } from '@playwright/test'
import {
  createAppServerHarness,
  hasBuild,
  ROUTE_SCENARIOS,
  seedThemeOverride,
  waitForFontsReady,
} from './fixtures/app-routes-harness'
import { walkTabOrder } from './fixtures/keyboard-walk'

const harness = createAppServerHarness('4177')

// 375×667 is this project's own mobile review width (`scripts/visual/review-widths.mjs`;
// `app-routes.spec.ts`'s own sibling suite captures desktop only). `isMobile`/`hasTouch` are
// deliberately not set: this sweep reads computed geometry, never dispatches a touch event, so
// Chromium's own touch-input emulation has nothing to change here.
const MOBILE_VIEWPORT = { width: 375, height: 667 }

test.use({ viewport: MOBILE_VIEWPORT })

test.describe('touch footprints at 375px, every route, both themes', () => {
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
      test(`${scenario.label} — every non-exempt interactive target clears 44×44 at 375px (${theme})`, async ({
        page,
      }) => {
        await seedThemeOverride(page, theme)
        await scenario.stub(page)

        await page.goto(`${harness.baseUrl}${scenario.path}`)
        await page.getByRole('main').waitFor({ state: 'visible' })
        await waitForFontsReady(page)

        const { steps } = await walkTabOrder(page)
        expect(
          steps.length,
          `${scenario.label} (${theme}): no interactive element found`,
        ).toBeGreaterThan(0)

        for (const step of steps) {
          if (step.exemptInlineLink) continue // WCAG 2.5.5's inline exception, read from data-variant

          expect(
            step.rect.width,
            `${scenario.label} (${theme}): <${step.tag}> "${step.name}" is ${step.rect.width.toFixed(1)}px wide, below the 44px floor`,
          ).toBeGreaterThanOrEqual(44)
          expect(
            step.rect.height,
            `${scenario.label} (${theme}): <${step.tag}> "${step.name}" is ${step.rect.height.toFixed(1)}px tall, below the 44px floor`,
          ).toBeGreaterThanOrEqual(44)
        }
      })
    }
  }
})
