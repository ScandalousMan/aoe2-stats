// T674 (production-readiness item 13, second of four halves): focus visibility, at route level, in
// both themes. The colour math already exists (`packages/design-system/tokens/contrast.mjs`, T580)
// and `tests/visual/focus-ring.spec.ts` already proves the ring per component inside Storybook
// (`/iframe.html`); what was missing, per the gap register's own row 1, is "the same assertion
// driven by a real Tab press against a route's own cascade rather than a forced Storybook state,
// confirming nothing at route level (a wrapper, a reset) repaints or hides what the component alone
// already guarantees."
//
// FR-050: "Every focusable element MUST show a visible focus indicator that meets the non-text
// contrast floor against the surface it appears on, in both themes, and MUST NOT lose it on pointer
// interaction." This file walks every route's own real focus order (`walkTabOrder`, shared with
// `route-keyboard.spec.ts`) and asserts the ring on every stop, rather than the sixteen
// representative controls `focus-ring.spec.ts` forces individually.
import { test, expect } from '@playwright/test'
import {
  createAppServerHarness,
  hasBuild,
  ROUTE_SCENARIOS,
  seedThemeOverride,
  waitForFontsReady,
} from './fixtures/app-routes-harness'
import { walkTabOrder } from './fixtures/keyboard-walk'
// `.mjs` rather than `.cjs`: verified on CI already for `focus-ring.spec.ts`'s own identical import
// (that file's own header comment, 0a400c4e/T580) — Playwright transpiles a `.spec.ts` to CommonJS,
// but this module has no CommonJS sibling to fall back to.
import { contrastRatioRgb } from '../../packages/design-system/tokens/contrast.mjs'

function parseRgb(color: string): { r: number; g: number; b: number } {
  const match = color.match(/rgba?\(([^)]+)\)/)
  if (!match) throw new Error(`unparseable colour from getComputedStyle: "${color}"`)
  const [r, g, b] = match[1].split(',').map((part) => parseFloat(part.trim()))
  return { r, g, b }
}

const harness = createAppServerHarness('4176')

test.describe('focus visibility, every route, both themes', () => {
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
      test(`${scenario.label} — every interactive element rings visibly on Tab, 3:1 against its own surface (${theme})`, async ({
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
          expect(
            step.isFocusVisible,
            `${scenario.label} (${theme}): <${step.tag}> "${step.name}" did not match :focus-visible after Tab`,
          ).toBe(true)
          expect(
            step.outline.style,
            `${scenario.label} (${theme}): <${step.tag}> "${step.name}" painted no outline while focus-visible`,
          ).not.toBe('none')

          const ratio = contrastRatioRgb(
            parseRgb(step.outline.color),
            parseRgb(step.backgroundColor),
          )
          expect(
            ratio,
            `${scenario.label} (${theme}): <${step.tag}> "${step.name}"'s focus ring ` +
              `(${step.outline.color}) is ${ratio.toFixed(2)}:1 against its surface ` +
              `(${step.backgroundColor}), below the 3:1 WCAG 1.4.11 non-text contrast floor`,
          ).toBeGreaterThanOrEqual(3)
        }
      })
    }
  }
})
