// T674 (production-readiness item 13, second of four halves): focus visibility, at route level, in
// both themes. The colour math already exists (`packages/design-system/tokens/contrast.mjs`, T580)
// and `tests/visual/focus-ring.spec.ts` already proves the ring per component inside Storybook
// (`/iframe.html`); what was missing, per T674's own task text in
// `specs/005-design-system-foundations/tasks.md`, is "the same assertion driven by a real Tab press
// against a route's own cascade rather than a forced Storybook state" — confirming nothing at route
// level (a wrapper, a reset) repaints or hides what the component alone already guarantees.
//
// FR-050: "Every focusable element MUST show a visible focus indicator that meets the non-text
// contrast floor against the surface it appears on, in both themes, and MUST NOT lose it on pointer
// interaction." This file walks every route's own real focus order (`walkTabOrder`, shared with
// `route-keyboard.spec.ts`) and asserts the ring on every stop, rather than the sixteen
// representative controls `focus-ring.spec.ts` forces individually. The per-step assertion itself,
// `assertFocusRingVisible`, is shared verbatim with `tests/visual/fixtures/focus-ring-walk.test.ts`'s
// planted-page guard tests (PR #102 review finding M1) so neither caller's contract can drift from
// the other's.
import { expect, test } from '@playwright/test'
import {
  assertThemeApplied,
  createAppServerHarness,
  hasBuild,
  ROUTE_SCENARIOS,
  seedThemeOverride,
  waitForFontsReady,
} from './fixtures/app-routes-harness'
import { assertFocusRingVisible, walkTabOrder } from './fixtures/keyboard-walk'

const harness = createAppServerHarness('4176')

test.describe('focus visibility, every route, both themes', () => {
  test.describe.configure({ mode: 'serial' })

  // PR #102 review finding (low, mirrored from `app-routes.spec.ts`'s own identical remediation): a
  // bare `test.skip` reports this whole suite as passed whether `apps/web/dist` is missing because
  // no developer has built it yet, or because a CI misconfiguration skipped the build step — exactly
  // the false-negative shape `assertFocusRingVisible`'s own strengthened checks below exist to catch
  // elsewhere. `process.env.CI` (set by every GitHub Actions runner) is what tells the two cases
  // apart; only a developer running this file locally without having built first gets the skip.
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
        test(`${scenario.label} — every interactive element rings visibly on Tab, 3:1 against its own surface (${theme})`, async ({
          page,
        }) => {
          await seedThemeOverride(page, theme)
          await scenario.stub(page)

          await page.goto(`${harness.baseUrl}${scenario.path}`)
          await page.getByRole('main').waitFor({ state: 'visible' })
          // PR #102 review finding (low): proves the theme was actually *painted*, not merely
          // seeded — `seedThemeOverride` only writes the storage key; `ThemeProvider.tsx` is what
          // reads it and paints `data-theme`, and the two can drift.
          await assertThemeApplied(page, theme)
          await waitForFontsReady(page)

          const { steps } = await walkTabOrder(page)
          expect(
            steps.length,
            `${scenario.label} (${theme}): no interactive element found`,
          ).toBeGreaterThan(0)

          for (const step of steps) {
            assertFocusRingVisible(step, `${scenario.label} (${theme})`)
          }
        })
      }
    }
  }
})
