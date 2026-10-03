// T676: the loading-state positive control, shown failing. `assertLoopsAnimating` and
// `assertLoopsStopped` are the two halves of the check that the only looping animations the design
// system defines (`spin`, `pulse`) animate normally and stop under `prefers-reduced-motion`. Each
// planted page breaks one clause: a loop that never loops (which would let the stopped half pass for
// free), a loop that does not stop, a loop that vanishes instead of resting, and a page with no loop
// at all.
import { expect, test, type Page } from '@playwright/test'
import { assertLoopsAnimating, assertLoopsStopped, holdRequests } from './loading-state'

// The class token is literal, colon included, exactly as `Spinner`/`Skeleton` carry it. The CSS
// reproduces what Tailwind emits for `motion-safe:animate-pulse`: the animation applies only under
// `no-preference`.
const PULSE_KEYFRAMES = '@keyframes ds-pulse { 0%, 100% { opacity: 1 } 50% { opacity: .5 } }'

function loopPage(css: string, body = '<div class="motion-safe:animate-pulse">loading</div>') {
  return `<style>${PULSE_KEYFRAMES} ${css}</style>${body}`
}

const GATED =
  '@media (prefers-reduced-motion: no-preference) { .motion-safe\\:animate-pulse { animation: ds-pulse 320ms infinite } }'
const UNGATED = '.motion-safe\\:animate-pulse { animation: ds-pulse 320ms infinite }'
const NEVER_LOOPS = '.motion-safe\\:animate-pulse { animation: none }'
const FINITE =
  '@media (prefers-reduced-motion: no-preference) { .motion-safe\\:animate-pulse { animation: ds-pulse 320ms 3 } }'

async function reduce(page: Page): Promise<void> {
  await page.emulateMedia({ reducedMotion: 'reduce' })
}

test.describe('loading-state loop guard, planted pages', () => {
  test('control: a correctly gated loop animates, then stops and stays on screen', async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: 'no-preference' })
    await page.setContent(loopPage(GATED))

    const count = await assertLoopsAnimating(page, 'skeleton', 'planted')
    expect(count).toBe(1)

    await reduce(page)
    await assertLoopsStopped(page, 'skeleton', 'planted', count)
  })

  test('a loop that never animates fails the animating half, so "stopped" cannot pass for free', async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: 'no-preference' })
    await page.setContent(loopPage(NEVER_LOOPS))

    await expect(assertLoopsAnimating(page, 'skeleton', 'planted')).rejects.toThrow(
      /a <div> skeleton has no animation without prefers-reduced-motion/,
    )
  })

  test('a finite animation fails the animating half: a loop repeats', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'no-preference' })
    await page.setContent(loopPage(FINITE))

    await expect(assertLoopsAnimating(page, 'skeleton', 'planted')).rejects.toThrow(
      /skeleton animation does not repeat/,
    )
  })

  test('a loop with no gate keeps animating under reduce and fails the stopped half', async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: 'no-preference' })
    await page.setContent(loopPage(UNGATED))
    const count = await assertLoopsAnimating(page, 'skeleton', 'planted')

    await reduce(page)
    await expect(assertLoopsStopped(page, 'skeleton', 'planted', count)).rejects.toThrow(
      /a <div> skeleton still runs animation "ds-pulse" \(iteration-count: infinite\) for 320ms under prefers-reduced-motion: reduce/,
    )
  })

  test('a loop gone under reduce fails: stopped means resting on screen, not absent', async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: 'no-preference' })
    await page.setContent(loopPage(GATED))
    const count = await assertLoopsAnimating(page, 'skeleton', 'planted')

    // A regression that *removes* the loop under reduce instead of resting it would otherwise
    // satisfy "no animation" for free.
    await page.evaluate(() => document.querySelector('.motion-safe\\:animate-pulse')?.remove())
    await reduce(page)
    await expect(assertLoopsStopped(page, 'skeleton', 'planted', count)).rejects.toThrow(
      /0 skeleton element\(s\) under reduce, 1 without it/,
    )
  })

  test('a page with no loop at all fails the animating half', async ({ page }) => {
    await page.setContent(loopPage(GATED, '<p>nothing is loading</p>'))

    await expect(assertLoopsAnimating(page, 'spinner', 'planted')).rejects.toThrow(
      /no spinner element \(\[class~="motion-safe:animate-spin"\]\) is on screen/,
    )
  })

  test('holdRequests keeps a request pending until released, then answers it', async ({ page }) => {
    const held = await holdRequests(page, '**/plant', { ok: true })

    let settled = false
    const navigation = page.goto('http://127.0.0.1:1/plant').then((response) => {
      settled = true
      return response
    })
    await expect.poll(() => held.heldCount()).toBe(1)
    // Still pending: the request is held, not answered.
    expect(settled).toBe(false)

    await held.release()
    const response = await navigation
    expect(response?.status()).toBe(200)
  })
})
