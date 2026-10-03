// Remediation of review finding B4 on PR #102 (T674, `specs/005-design-system-foundations`): the
// touch-footprint route suite's own per-page assertion, factored out of `route-touch-footprint.
// spec.ts` so that file and `touch-footprint.test.ts`'s planted `page.setContent` pages call the
// exact same function — the two cannot drift the way B4 found nothing had ever proven either one
// fails when the property it claims to check is actually broken.
//
// Contract: `packages/design-system/specs/README.md`'s "Minimum interactive footprint" — every
// interactive element a page renders must clear 44×44 CSS px in both axes at rest, except an
// anchor `walkTabOrder` has already marked `exemptInlineLink`: a `data-variant="inline"` anchor
// (never a layout heuristic) whose parent element's trimmed text is longer than its own. A `<label>`
// -wrapped input is measured by the label's box, and an element hidden until focused is measured in
// the state that reveals it — both already handled by `walkTabOrder` itself, which this function
// reuses rather than re-implementing.
import { expect, type Page } from '@playwright/test'
import { type TabStop, walkTabOrder } from './keyboard-walk'

// The floor itself, over stops already collected: the Tab walk's own (`assertTouchFootprint`
// below) or an opened `Menu`/`Dialog`'s (`open-surface.ts`, T676). Pure, so `touch-footprint.test.ts`
// can hand it hand-made stops without a page.
export function assertStopsClearFootprint(steps: readonly TabStop[], context: string): void {
  for (const step of steps) {
    if (step.exemptInlineLink) continue // WCAG 2.5.5's inline exception, read from data-variant

    expect(
      step.rect.width,
      `${context}: <${step.tag}> "${step.name}" is ${step.rect.width.toFixed(1)}px wide, below the 44px floor`,
    ).toBeGreaterThanOrEqual(44)
    expect(
      step.rect.height,
      `${context}: <${step.tag}> "${step.name}" is ${step.rect.height.toFixed(1)}px tall, below the 44px floor`,
    ).toBeGreaterThanOrEqual(44)
  }
}

export async function assertTouchFootprint(page: Page, context: string): Promise<void> {
  const { steps } = await walkTabOrder(page)
  expect(steps.length, `${context}: no interactive element found`).toBeGreaterThan(0)
  assertStopsClearFootprint(steps, context)
}
