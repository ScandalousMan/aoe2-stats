// T681 (production-readiness item 13, extending T676's open-surface walks): the `Tooltip` at route
// level. `Tooltip` is not a `Menu` or a `Dialog` — it holds no focusable item, so
// `./open-surface`'s walks do not apply — but it has two contracts the route suites never reached
// while it stayed closed:
//
// - Motion (`packages/design-system/src/primitives/Tooltip/index.tsx`): the open surface carries
//   `transition-opacity duration-120 motion-reduce:duration-0`. A *closed* tooltip is `duration-0`
//   with or without the preference, so only an *open* one can show the `motion-reduce:` utility is
//   still there. `assertTooltipMotionContract` reads the open surface's computed transition without
//   the preference (present), switches the preference on live, and reads the same element again
//   (absent).
// - Keyboard (`packages/design-system/specs/tooltip.md` §8): Tab to the trigger opens the surface
//   (`:focus-visible`); Escape dismisses it while focus stays on the trigger. `walkOpenTooltip`
//   observes both and hands back facts, `assertTooltipKeyboard` judges them.
//
// Both assertions are shared verbatim between the route suites and `tooltip-open.test.ts`'s planted
// pages, the arrangement `./open-surface` and `./reduced-motion` already have, so a guard is shown
// failing on a page carrying exactly the defect it names and cannot drift from the real-route one.
import { expect, type Locator, type Page } from '@playwright/test'
import { parseDurationListMs } from './reduced-motion'
import { tabTo } from './open-surface'

// The trigger is the `<button>` whose next sibling is the `role="tooltip"` surface (§2 anatomy:
// no portal, the surface renders as a sibling of the trigger). Matched on that structure, never on
// a class, and scoped to `main` because the shared header's chrome is not what a route renders.
export const TOOLTIP_TRIGGER_SELECTOR = 'main button:has(+ [role="tooltip"])'
export const TOOLTIP_SURFACE_SELECTOR = 'main button:has(+ [role="tooltip"]) + [role="tooltip"]'

export function tooltipTrigger(page: Page): Locator {
  return page.locator(TOOLTIP_TRIGGER_SELECTOR).first()
}

export function tooltipSurface(page: Page): Locator {
  return page.locator(TOOLTIP_SURFACE_SELECTOR).first()
}

/** How many tooltips a scenario opens: `tooltipTrigger` and `tooltipSurface` both take `.first()`. */
const TOOLTIPS_A_SCENARIO_OPENS = 1

/** Fails when `main` holds more tooltip triggers than the scenario opens, so a second `Tooltip` on
 * a covered route cannot ride on the first one's scenario: its motion and Escape contract would
 * never be judged. This is counted in the rendered page, so no table can satisfy it. It sees only
 * what the scenario's at-rest stubs render; a tooltip that appears in a populated list is not in the
 * page here. */
export async function assertOneTooltipTrigger(page: Page, label: string): Promise<void> {
  await page
    .locator(TOOLTIP_TRIGGER_SELECTOR)
    .first()
    .waitFor({ state: 'attached', timeout: 5_000 })
    .catch(() => undefined)
  const count = await page.locator(TOOLTIP_TRIGGER_SELECTOR).count()
  if (count > TOOLTIPS_A_SCENARIO_OPENS) {
    throw new Error(
      `${label}: ${count} tooltip triggers in main, the scenario opens ${TOOLTIPS_A_SCENARIO_OPENS} ` +
        `— a second Tooltip needs its own scenario`,
    )
  }
}

/** Opens the route's tooltip the way a keyboard user does: Tab to its trigger, and `:focus-visible`
 * opens it. Never a hover, never a programmatic `focus()`. Throws if `main` holds more than one
 * tooltip trigger, and if Tab reached the trigger and nothing opened. `label` names the route in
 * the failure. */
export async function openTooltipByKeyboard(page: Page, label = page.url()): Promise<void> {
  await assertOneTooltipTrigger(page, label)
  await tabTo(page, tooltipTrigger(page))
  await tooltipSurface(page)
    .waitFor({ state: 'visible', timeout: 5_000 })
    .catch(() => {
      throw new Error(
        'openTooltipByKeyboard: Tab reached the tooltip trigger and its surface never opened — ' +
          'tooltip.md §4: :focus-visible opens it',
      )
    })
}

// --- Motion ---------------------------------------------------------------------------------------

interface SurfaceTransition {
  /** Whether the surface is rendered (not `hidden`/`display: none`). */
  visible: boolean
  transitionProperty: string
  transitionDuration: string
  /** The identity stamp this module leaves on the surface it judged. */
  stamp: string | null
}

async function readSurfaceTransition(page: Page, stampWith?: string): Promise<SurfaceTransition> {
  return tooltipSurface(page).evaluate((el, stamp) => {
    if (stamp !== undefined) el.setAttribute('data-tooltip-motion-stamp', stamp)
    const computed = getComputedStyle(el)
    return {
      visible: computed.display !== 'none',
      transitionProperty: computed.transitionProperty,
      transitionDuration: computed.transitionDuration,
      stamp: el.getAttribute('data-tooltip-motion-stamp'),
    }
  }, stampWith)
}

/** The whole motion contract on the tooltip currently open, with no reduced-motion preference in
 * effect on entry: its surface runs a perceptible transition; then, with the preference switched
 * on *live* so it is provably the same element, none. Leaves the preference on. */
export async function assertTooltipMotionContract(page: Page, context: string): Promise<void> {
  const before = await readSurfaceTransition(page, 'judged')
  expect(
    before.visible,
    `${context}: the tooltip surface is not open — a closed tooltip is duration-0 either way, so ` +
      `this check would pass for free`,
  ).toBe(true)
  const durations = parseDurationListMs(before.transitionDuration)
  expect(
    durations.some((ms) => ms > 1),
    `${context}: the open tooltip surface computes transition-duration "${before.transitionDuration}" ` +
      `without prefers-reduced-motion — no perceptible transition, so the reduced half below ` +
      `would pass for free`,
  ).toBe(true)
  expect(
    before.transitionProperty,
    `${context}: the open tooltip surface does not transition opacity ("${before.transitionProperty}")`,
  ).toContain('opacity')

  await page.emulateMedia({ reducedMotion: 'reduce' })

  const after = await readSurfaceTransition(page)
  expect(
    after.stamp,
    `${context}: the tooltip surface read under prefers-reduced-motion is not the one read before`,
  ).toBe('judged')
  expect(
    after.visible,
    `${context}: the tooltip surface closed when the preference switched on`,
  ).toBe(true)
  assertReducedDurations(after.transitionDuration, context)
}

/** The reduced half, on a `transition-duration` reading: every parsed entry is (near) zero, and at
 * least one entry parsed, since a loop over nothing passes for free. */
export function assertReducedDurations(reading: string, context: string): void {
  const durations = parseDurationListMs(reading)
  expect(
    durations.length,
    `${context}: the open tooltip surface under prefers-reduced-motion reads transition-duration ` +
      `"${reading}" — no duration parsed, so "stops under the preference" would pass for free`,
  ).toBeGreaterThan(0)
  for (const ms of durations) {
    expect(
      ms,
      `${context}: the open tooltip surface keeps a ${ms}ms transition under ` +
        `prefers-reduced-motion: reduce — its motion-reduce: utility is missing`,
    ).toBeLessThanOrEqual(1)
  }
}

// --- Keyboard -------------------------------------------------------------------------------------

export interface TooltipWalk {
  /** Whether the surface was visible with focus on the trigger, before any key was pressed. */
  openWithFocusOnTrigger: boolean
  /** Whether the surface was gone after Escape. */
  closedByEscape: boolean
  /** Whether focus was still on that same trigger after Escape. */
  focusStaysOnTrigger: boolean
}

/** Walks the one tooltip currently open (see `openTooltipByKeyboard`). Leaves it dismissed, so it
 * must be the last thing a test does with the page. */
export async function walkOpenTooltip(page: Page): Promise<TooltipWalk> {
  const surface = tooltipSurface(page)
  // Stamp the trigger so "focus stays on the trigger" means *that* element.
  const focusedStamped = await tooltipTrigger(page).evaluate((el) => {
    el.setAttribute('data-tooltip-trigger-stamp', '')
    return el === document.activeElement
  })
  const openWithFocusOnTrigger = focusedStamped && (await surface.isVisible())

  await page.keyboard.press('Escape')
  const closedByEscape = await surface
    .waitFor({ state: 'hidden', timeout: 1_000 })
    .then(() => true)
    .catch(() => false)
  const focusStaysOnTrigger = await page.evaluate(
    () => document.activeElement?.hasAttribute('data-tooltip-trigger-stamp') === true,
  )
  return { openWithFocusOnTrigger, closedByEscape, focusStaysOnTrigger }
}

export function assertTooltipKeyboard(walk: TooltipWalk, context: string): void {
  expect(
    walk.openWithFocusOnTrigger,
    `${context}: Tab to the trigger did not leave the tooltip open with focus on the trigger`,
  ).toBe(true)
  expect(walk.closedByEscape, `${context}: Escape did not dismiss the tooltip`).toBe(true)
  expect(
    walk.focusStaysOnTrigger,
    `${context}: Escape moved focus off the tooltip's trigger (tooltip.md §8)`,
  ).toBe(true)
}
