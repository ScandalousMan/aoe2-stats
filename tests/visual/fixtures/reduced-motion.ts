// Remediation of review finding B4 on PR #102 (T674, `specs/005-design-system-foundations`): the
// reduced-motion route suite's own per-page assertion, factored out of `route-reduced-motion.
// spec.ts` so that file and `reduced-motion.test.ts`'s planted `page.setContent` pages call the
// exact same function — the two cannot drift the way B4 found nothing had ever proven either one
// fails when the property it claims to check is actually broken.
//
// Contract: `packages/design-system/specs/README.md` rule 5 ("Reduced motion is a real state") —
// under `prefers-reduced-motion: reduce`, every transition uses `motion.duration.instant`
// (`packages/design-system/tokens/motion.json`, 0ms) and every looping animation stops on its
// resting frame. "Near-zero" below is <=1ms: `motion.duration.instant` is exactly 0ms, and the 1ms
// margin only absorbs floating-point rounding in `getComputedStyle`'s own serialization, never a
// real perceptible duration. Caller is responsible for calling
// `page.emulateMedia({ reducedMotion: 'reduce' })` before the page first paints.
import { expect, type Page } from '@playwright/test'

// getComputedStyle(...).transitionDuration/animationDuration are comma-separated lists, one entry
// per transitioned/animated property (`transition: color 120ms, background-color 120ms` reads
// "0.12s, 0.12s") — every entry must parse to (near) zero, not just the first.
export function parseDurationListMs(value: string): number[] {
  return value
    .split(',')
    .map((part) => part.trim())
    .filter((part) => part.length > 0)
    .map((part) => (part.endsWith('ms') ? parseFloat(part) : parseFloat(part) * 1000))
}

interface MotionSnapshot {
  tag: string
  transitionDuration: string
  animationDuration: string
  animationName: string
  animationIterationCount: string
}

export async function assertReducedMotion(page: Page, context: string): Promise<void> {
  const offenders: MotionSnapshot[] = await page.evaluate(() => {
    const found: Array<{
      tag: string
      transitionDuration: string
      animationDuration: string
      animationName: string
      animationIterationCount: string
    }> = []
    for (const el of Array.from(document.querySelectorAll<HTMLElement>('*'))) {
      const computed = getComputedStyle(el)
      found.push({
        tag: el.tagName.toLowerCase(),
        transitionDuration: computed.transitionDuration,
        animationDuration: computed.animationDuration,
        animationName: computed.animationName,
        animationIterationCount: computed.animationIterationCount,
      })
    }
    return found
  })

  for (const el of offenders) {
    for (const ms of parseDurationListMs(el.transitionDuration)) {
      expect(
        ms,
        `${context}: a <${el.tag}> computes a ${ms}ms transition duration under prefers-reduced-motion: reduce`,
      ).toBeLessThanOrEqual(1)
    }
    // A looping animation is either absent (`animation-name: none`, the `motion-safe:` gate simply
    // not applying) or, if named, must itself compute a near-zero duration — either shape satisfies
    // "stops on its resting frame" regardless of `animation-iteration-count`: an infinite count over
    // a (near) zero duration has no perceptible loop left to stop. `animationIterationCount` is
    // carried through to the failure message only, so a real regression names the count alongside
    // the duration rather than leaving a reader to reproduce it by hand.
    if (el.animationName !== 'none') {
      for (const ms of parseDurationListMs(el.animationDuration)) {
        expect(
          ms,
          `${context}: a <${el.tag}> runs animation "${el.animationName}" ` +
            `(iteration-count: ${el.animationIterationCount}) for ${ms}ms under ` +
            `prefers-reduced-motion: reduce`,
        ).toBeLessThanOrEqual(1)
      }
    }
  }
}
