// Remediation of review finding B4 on PR #102 (T674, `specs/005-design-system-foundations`): no
// prior run showed `assertReducedMotion` (nor `route-reduced-motion.spec.ts` before this file
// existed) fail on a genuine defect. This file plants small static pages (`page.setContent`, no app
// build and no Storybook story needed — the same pattern `keyboard-walk.test.ts` uses) that each
// trip the near-zero-duration requirement `packages/design-system/specs/README.md` rule 5 describes,
// or its `@media (prefers-reduced-motion: reduce)` fix, proving the assertion actually fires rather
// than merely existing.
import { test, expect } from '@playwright/test'
import { assertReducedMotion } from './reduced-motion'

test.describe('reduced-motion assertion, planted pages', () => {
  test('a transition with no reduced-motion override fails, naming it', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.setContent(`
      <style>#fades { transition: opacity 200ms; }</style>
      <div id="fades">Fades</div>
    `)

    await expect(assertReducedMotion(page, 'planted')).rejects.toThrow(
      /a <div> computes a 200ms transition duration under prefers-reduced-motion: reduce/,
    )
  })

  test('an infinite spin-like animation with no reduced-motion override fails, naming it', async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.setContent(`
      <style>
        @keyframes spin-fixture {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        #spinner { animation: spin-fixture 300ms linear infinite; }
      </style>
      <div id="spinner">Spinner</div>
    `)

    await expect(assertReducedMotion(page, 'planted')).rejects.toThrow(
      /a <div> runs animation "spin-fixture" \(iteration-count: infinite\) for 300ms under prefers-reduced-motion: reduce/,
    )
  })

  test('the same transition and animation, each with a reduced-motion override, both pass', async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.setContent(`
      <style>
        #fades { transition: opacity 200ms; }
        @media (prefers-reduced-motion: reduce) {
          #fades { transition-duration: 0ms; }
        }

        @keyframes spin-fixture {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        #spinner { animation: spin-fixture 300ms linear infinite; }
        @media (prefers-reduced-motion: reduce) {
          #spinner { animation: none; }
        }
      </style>
      <div id="fades">Fades</div>
      <div id="spinner">Spinner</div>
    `)

    await expect(assertReducedMotion(page, 'planted')).resolves.not.toThrow()
  })
})
