// T674: the one mechanism the keyboard-operation, focus-visibility and touch-footprint sub-suites
// all need — a real `page.keyboard.press('Tab')` walk over every interactive element a route
// renders, in DOM/visual order, collecting per-stop facts once rather than three times. Reduced
// motion is a different mechanism entirely (a blanket sweep of every element's computed animation/
// transition duration, nothing to do with focus order) and does not use this file.
import type { Page } from '@playwright/test'

export interface TabStop {
  /** The marker this walk stamps on every candidate before pressing Tab — never re-derived from a
   * layout heuristic, the same discipline `Link`'s own `data-variant` marker follows. */
  kbdId: string
  tag: string
  /** `getByRole`-style accessible name approximation, for failure messages only. */
  name: string
  /** True when the focused element sits inside the route's one `main` landmark or its `header`/
   * `footer` chrome — FR-049's "no trap outside a modal surface that defines its own", read the
   * cheap way: a route-level walk has no modal open, so every reachable element must be chrome or
   * content. */
  insideChrome: boolean
  rect: { width: number; height: number }
  isFocusVisible: boolean
  outline: { style: string; width: string; color: string }
  /** The nearest non-transparent ancestor background, walking up from the element itself — the
   * same walk `tests/visual/focus-ring.spec.ts` already does for its own per-component assertion. */
  backgroundColor: string
  dataVariant: string | null
  /** WCAG 2.5.5's inline exception, read from the DOM per `packages/design-system/specs/README.md`
   * ("Minimum interactive footprint"): a `data-variant="inline"` anchor whose parent's trimmed text
   * is longer than its own. */
  exemptInlineLink: boolean
}

export interface TabWalkResult {
  /** Every candidate this route stamped before walking, whether or not the walk actually reached
   * it — used to assert full coverage. */
  candidateCount: number
  steps: TabStop[]
}

// Deliberately not `a[href], button, ...` alone: `:not([tabindex="-1"])` on the bare `[tabindex]`
// clause excludes a closed `Menu`'s own roving-tabindex items, which a plain Tab walk over the
// route (no menu ever opened) could never reach either — the same reachability a real keyboard
// user has, not an inflated candidate set this walk could never satisfy.
const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), ' +
  'select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

export async function walkTabOrder(page: Page, maxStepsOverride?: number): Promise<TabWalkResult> {
  const candidateCount = await page.evaluate(
    ({ selector }) => {
      const candidates = Array.from(document.querySelectorAll<HTMLElement>(selector)).filter(
        (el) => {
          const style = getComputedStyle(el)
          return style.display !== 'none' && style.visibility !== 'hidden'
        },
      )
      candidates.forEach((el, index) => el.setAttribute('data-kbd-walk-id', String(index)))
      return candidates.length
    },
    { selector: FOCUSABLE_SELECTOR },
  )

  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur())

  const maxSteps = maxStepsOverride ?? candidateCount + 5
  const steps: TabStop[] = []

  for (let i = 0; i < maxSteps; i += 1) {
    await page.keyboard.press('Tab')
    const step = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null
      if (el === null || el === document.body) return null

      let node: Element | null = el
      let backgroundColor = ''
      while (node) {
        const bg = getComputedStyle(node).backgroundColor
        const match = bg.match(/rgba?\(([^)]+)\)/)
        const alpha = match ? (match[1].split(',').map(Number)[3] ?? 1) : 1
        if (alpha !== 0) {
          backgroundColor = bg
          break
        }
        node = node.parentElement
      }

      const computed = getComputedStyle(el)
      const rect = el.getBoundingClientRect()
      const parentText = el.parentElement?.textContent?.trim() ?? ''
      const ownText = el.textContent?.trim() ?? ''
      const dataVariant = el.getAttribute('data-variant')
      const exemptInlineLink =
        el.tagName === 'A' && dataVariant === 'inline' && parentText.length > ownText.length

      return {
        kbdId: el.getAttribute('data-kbd-walk-id'),
        tag: el.tagName.toLowerCase(),
        name: (el.getAttribute('aria-label') ?? el.textContent ?? '').trim().slice(0, 60),
        insideChrome: el.closest('main, header, footer') !== null,
        rect: { width: rect.width, height: rect.height },
        isFocusVisible: el.matches(':focus-visible'),
        outline: {
          style: computed.outlineStyle,
          width: computed.outlineWidth,
          color: computed.outlineColor,
        },
        backgroundColor,
        dataVariant,
        exemptInlineLink,
      }
    })

    if (step === null) break // wrapped past the last focusable element back to `document.body`
    steps.push({ ...step, kbdId: step.kbdId ?? '' })
  }

  return { candidateCount, steps }
}
