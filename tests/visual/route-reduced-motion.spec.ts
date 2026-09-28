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
import { test, expect } from '@playwright/test'
import {
  createAppServerHarness,
  hasBuild,
  ROUTE_SCENARIOS,
  seedThemeOverride,
  waitForFontsReady,
} from './fixtures/app-routes-harness'

const harness = createAppServerHarness('4178')

// `getComputedStyle(...).transitionDuration`/`animationDuration` are comma-separated lists, one
// entry per transitioned/animated property (`transition: color 120ms, background-color 120ms`
// reads `"0.12s, 0.12s"`) — every entry must parse to (near) zero, not just the first.
function parseDurationListMs(value: string): number[] {
  return value
    .split(',')
    .map((part) => part.trim())
    .filter((part) => part.length > 0)
    .map((part) => (part.endsWith('ms') ? parseFloat(part) : parseFloat(part) * 1000))
}

test.describe('reduced motion, every route, both themes', () => {
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
      test(`${scenario.label} — no transition or looping animation keeps a perceptible duration (${theme})`, async ({
        page,
      }) => {
        // Set before navigation (this file's own header comment) so the reduced-motion preference
        // is already in effect for the very first render — never a post-load toggle that could
        // race a transition already mid-flight.
        await page.emulateMedia({ reducedMotion: 'reduce' })
        await seedThemeOverride(page, theme)
        await scenario.stub(page)

        await page.goto(`${harness.baseUrl}${scenario.path}`)
        await page.getByRole('main').waitFor({ state: 'visible' })
        await waitForFontsReady(page)

        const offenders = await page.evaluate(() => {
          const found: Array<{
            tag: string
            transitionDuration: string
            animationDuration: string
            animationName: string
          }> = []
          for (const el of Array.from(document.querySelectorAll<HTMLElement>('*'))) {
            const computed = getComputedStyle(el)
            found.push({
              tag: el.tagName.toLowerCase(),
              transitionDuration: computed.transitionDuration,
              animationDuration: computed.animationDuration,
              animationName: computed.animationName,
            })
          }
          return found
        })

        for (const el of offenders) {
          for (const ms of parseDurationListMs(el.transitionDuration)) {
            expect(
              ms,
              `${scenario.label} (${theme}): a <${el.tag}> computes a ${ms}ms transition duration under prefers-reduced-motion: reduce`,
            ).toBeLessThanOrEqual(1)
          }
          // A looping animation is either absent (`animation-name: none`, the `motion-safe:`
          // gate simply not applying) or, if named, must itself compute a near-zero duration —
          // either shape satisfies "stops on its resting frame."
          if (el.animationName !== 'none') {
            for (const ms of parseDurationListMs(el.animationDuration)) {
              expect(
                ms,
                `${scenario.label} (${theme}): a <${el.tag}> runs animation "${el.animationName}" for ${ms}ms under prefers-reduced-motion: reduce`,
              ).toBeLessThanOrEqual(1)
            }
          }
        }
      })
    }
  }
})
