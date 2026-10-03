// T676 (production-readiness item 13, fourth half — the loops): `spin` and `pulse`, the only
// looping animations `packages/design-system/tokens/motion.json` defines, live in `Spinner` and
// `Skeleton`, both of which are gone before `assertReducedMotion` samples a route at rest. That
// left the looping half of FR-055 / SC-016 ("every looping animation MUST stop on its resting
// frame") with no positive control: a sweep that finds `animation-name: none` everywhere passes
// identically whether the loops are correctly gated or were never on screen to begin with.
//
// This is the control. It holds a route's API response open so the loading state stays on screen,
// finds the loop element **by structure** — the `motion-safe:animate-spin` / `motion-safe:animate-
// pulse` class token the markup carries — and asserts it *animates* without the reduced-motion
// preference, then asserts the very same element is *stopped* with it. Structure rather than
// computed animation is deliberate: both loops sit behind `motion-safe:`, so under `reduce` the
// animation utility does not apply and `animation-name` computes to `none`; a locator that keyed on
// a running animation would find nothing under `reduce` and so could never tell "stopped" from
// "absent". The class token survives in the markup either way, so the same locator resolves in both
// modes and the assertion can demand the element still exists.
import { expect, type Page } from '@playwright/test'
import { parseDurationListMs } from './reduced-motion'

export type LoopKind = 'spinner' | 'skeleton'

// The utility class each looping component carries (`packages/design-system/src/lib/Spinner.tsx`,
// `.../primitives/Skeleton/index.tsx`) — `~=` matches the whole class token, colon included.
export const LOOP_SELECTOR: Record<LoopKind, string> = {
  spinner: '[class~="motion-safe:animate-spin"]',
  skeleton: '[class~="motion-safe:animate-pulse"]',
}

interface LoopSnapshot {
  tag: string
  animationName: string
  animationDuration: string
  animationIterationCount: string
}

export async function readLoops(page: Page, kind: LoopKind): Promise<LoopSnapshot[]> {
  return page.evaluate((selector) => {
    return Array.from(document.querySelectorAll<HTMLElement>(selector)).map((el) => {
      const computed = getComputedStyle(el)
      return {
        tag: el.tagName.toLowerCase(),
        animationName: computed.animationName,
        animationDuration: computed.animationDuration,
        animationIterationCount: computed.animationIterationCount,
      }
    })
  }, LOOP_SELECTOR[kind])
}

/** Without the reduced-motion preference: at least one `kind` element is on screen and every one
 * runs a named, infinite, perceptible animation. Returns how many it found. */
export async function assertLoopsAnimating(
  page: Page,
  kind: LoopKind,
  context: string,
): Promise<number> {
  const loops = await readLoops(page, kind)
  expect(
    loops.length,
    `${context}: no ${kind} element (${LOOP_SELECTOR[kind]}) is on screen — the loading state this ` +
      `positive control holds open did not render one`,
  ).toBeGreaterThan(0)
  for (const loop of loops) {
    expect(
      loop.animationName,
      `${context}: a <${loop.tag}> ${kind} has no animation without prefers-reduced-motion — a ` +
        `loop that never loops would make the stopped half below pass for free`,
    ).not.toBe('none')
    expect(
      loop.animationIterationCount,
      `${context}: a <${loop.tag}> ${kind} animation does not repeat`,
    ).toBe('infinite')
    for (const ms of parseDurationListMs(loop.animationDuration)) {
      expect(
        ms,
        `${context}: a <${loop.tag}> ${kind} animation has no perceptible duration`,
      ).toBeGreaterThan(1)
    }
  }
  return loops.length
}

/** Under `prefers-reduced-motion: reduce`: the *same* number of `kind` elements are still on screen
 * (so "stopped" is never satisfied by absence) and none runs a perceptible animation. */
export async function assertLoopsStopped(
  page: Page,
  kind: LoopKind,
  context: string,
  expectedCount: number,
): Promise<void> {
  const loops = await readLoops(page, kind)
  expect(
    loops.length,
    `${context}: ${loops.length} ${kind} element(s) under reduce, ${expectedCount} without it — ` +
      `a stopped loop must still be on screen, resting, not removed`,
  ).toBe(expectedCount)
  for (const loop of loops) {
    if (loop.animationName === 'none') continue
    for (const ms of parseDurationListMs(loop.animationDuration)) {
      expect(
        ms,
        `${context}: a <${loop.tag}> ${kind} still runs animation "${loop.animationName}" ` +
          `(iteration-count: ${loop.animationIterationCount}) for ${ms}ms under ` +
          `prefers-reduced-motion: reduce`,
      ).toBeLessThanOrEqual(1)
    }
  }
}

/** Holds every request matching `urlGlob` open until `release()`, so the loading state it feeds
 * stays on screen for as long as a test needs. `release()` answers them with `body` — never leaves
 * a request dangling past the test, which would otherwise surface as an aborted-request console
 * error from the page. */
export async function holdRequests(
  page: Page,
  urlGlob: string,
  body: unknown,
): Promise<{ release: () => Promise<void>; heldCount: () => number }> {
  let held = 0
  let open: () => void = () => {}
  const gate = new Promise<void>((resolve) => {
    open = resolve
  })
  await page.route(urlGlob, async (route) => {
    held += 1
    await gate
    await route
      .fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
      .catch(() => {
        // The page closed first (test teardown); nothing left to answer.
      })
  })
  return {
    release: async () => {
      open()
    },
    heldCount: () => held,
  }
}
