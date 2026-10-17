// T681: no run showed `assertTooltipMotionContract` / `assertTooltipKeyboard` fail on a real defect,
// and a guard that has never failed proves nothing. This plants small static pages
// (`page.setContent`, no app build — the pattern `open-surface.test.ts` uses) that each break one
// clause of the `Tooltip` contract `./tooltip-open` checks, beside a passing control, and asserts
// the guard names the broken clause. The motion plants carry the two states the real component's
// classes compute (`transition-opacity duration-120` open, plus or minus `motion-reduce:duration-0`).
import { expect, test, type Page } from '@playwright/test'
import {
  assertTooltipKeyboard,
  assertTooltipMotionContract,
  openTooltipByKeyboard,
  walkOpenTooltip,
} from './tooltip-open'

interface MotionOptions {
  /** The `motion-reduce:duration-0` utility is missing: the open surface keeps its 120ms. */
  noReducedOverride?: boolean
  /** The surface never transitions at all, so a "reduced" reading would pass for free. */
  neverTransitions?: boolean
  /** The surface is closed (`hidden`) when read. */
  closed?: boolean
}

function motionPage(options: MotionOptions = {}): string {
  return `
    <style>
      .surface { transition-property: opacity; transition-duration: ${options.neverTransitions ? '0s' : '120ms'}; }
      ${options.noReducedOverride ? '' : '@media (prefers-reduced-motion: reduce) { .surface { transition-duration: 0s; } }'}
    </style>
    <main>
      <button id="trigger" type="button">Flag</button>
      <span class="surface" role="tooltip" ${options.closed ? 'hidden' : ''}>France</span>
    </main>`
}

interface KeyboardOptions {
  /** Focus on the trigger does not open the surface. */
  focusDoesNotOpen?: boolean
  /** Escape does nothing. */
  escapeIgnored?: boolean
  /** Escape dismisses the surface but moves focus off the trigger. */
  escapeLosesFocus?: boolean
}

function keyboardPage(options: KeyboardOptions = {}): string {
  return `
    <button id="before" type="button">Before</button>
    <main>
      <button id="trigger" type="button">Flag</button>
      <span id="surface" role="tooltip" hidden>France</span>
    </main>
    <script>
      const trigger = document.getElementById('trigger')
      const surface = document.getElementById('surface')
      trigger.addEventListener('focus', () => {
        if (!${Boolean(options.focusDoesNotOpen)}) surface.hidden = false
      })
      trigger.addEventListener('keydown', (event) => {
        if (event.key !== 'Escape' || ${Boolean(options.escapeIgnored)}) return
        surface.hidden = true
        if (${Boolean(options.escapeLosesFocus)}) document.getElementById('before').focus()
      })
    </script>`
}

async function load(page: Page, html: string): Promise<void> {
  await page.setContent(html)
}

test.describe('tooltip motion contract, planted pages', () => {
  test('an open surface that transitions and stops under reduce passes', async ({ page }) => {
    await load(page, motionPage())
    await expect(assertTooltipMotionContract(page, 'planted')).resolves.not.toThrow()
  })

  test('an open surface that lacks the motion-reduce utility fails, naming the 120ms it keeps', async ({
    page,
  }) => {
    await load(page, motionPage({ noReducedOverride: true }))
    await expect(assertTooltipMotionContract(page, 'planted')).rejects.toThrow(
      /keeps a 120ms transition under prefers-reduced-motion: reduce — its motion-reduce: utility is missing/,
    )
  })

  test('a surface that never transitions fails the present half, so the reduced half cannot pass for free', async ({
    page,
  }) => {
    await load(page, motionPage({ neverTransitions: true }))
    await expect(assertTooltipMotionContract(page, 'planted')).rejects.toThrow(
      /no perceptible transition, so the reduced half below would pass for free/,
    )
  })

  test('a closed surface fails: a closed tooltip is duration-0 either way', async ({ page }) => {
    await load(page, motionPage({ closed: true }))
    await expect(assertTooltipMotionContract(page, 'planted')).rejects.toThrow(
      /the tooltip surface is not open/,
    )
  })
})

test.describe('tooltip keyboard contract, planted pages', () => {
  test('Tab opens it, Escape dismisses it and focus stays on the trigger: passes', async ({
    page,
  }) => {
    await load(page, keyboardPage())
    await openTooltipByKeyboard(page)
    assertTooltipKeyboard(await walkOpenTooltip(page), 'planted')
  })

  test('a trigger whose focus does not open the surface fails', async ({ page }) => {
    await load(page, keyboardPage({ focusDoesNotOpen: true }))
    await expect(openTooltipByKeyboard(page)).rejects.toThrow(
      /Tab reached the tooltip trigger and its surface never opened/,
    )
  })

  test('Escape that is ignored fails, naming the dismissal', async ({ page }) => {
    await load(page, keyboardPage({ escapeIgnored: true }))
    await openTooltipByKeyboard(page)
    const walk = await walkOpenTooltip(page)
    expect(walk.closedByEscape).toBe(false)
    expect(() => assertTooltipKeyboard(walk, 'planted')).toThrow(/Escape did not dismiss/)
  })

  test('Escape that dismisses but moves focus off the trigger fails, naming the focus', async ({
    page,
  }) => {
    await load(page, keyboardPage({ escapeLosesFocus: true }))
    await openTooltipByKeyboard(page)
    const walk = await walkOpenTooltip(page)
    expect(walk.closedByEscape).toBe(true)
    expect(() => assertTooltipKeyboard(walk, 'planted')).toThrow(
      /moved focus off the tooltip's trigger/,
    )
  })
})
