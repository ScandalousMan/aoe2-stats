// T674: the one mechanism the keyboard-operation, focus-visibility and touch-footprint sub-suites
// all need — a real `page.keyboard.press('Tab')` walk over every interactive element a route
// renders, in DOM/visual order, collecting per-stop facts once rather than three times. Reduced
// motion is a different mechanism entirely (a blanket sweep of every element's computed animation/
// transition duration, nothing to do with focus order) and does not use this file.
//
// Remediation of review finding B2 (PR #102): the walk used to stop the instant `document.body`
// regained focus and left every trap/coverage judgment to `route-keyboard.spec.ts`'s own
// `reachedIds.size === candidateCount` — a `Set`, which silently drops duplicates, so a trap that
// only starts after every candidate has already been reached once (a footer loop cycling back into
// the header, say) produced the same passing count as a clean route. `assertFullTabCoverage` below
// is now the one place that judgment lives, shared verbatim between the real-route suite and
// `keyboard-walk.test.ts`'s planted-page guard tests, so neither can drift from the other.
import { expect, type Page } from '@playwright/test'

export interface TabStop {
  /** The marker this walk stamps on every candidate before pressing Tab — never re-derived from a
   * layout heuristic, the same discipline `Link`'s own `data-variant` marker follows. `null` means
   * the walk landed on an element it never stamped: an unstamped focusable (a `<summary>`, a
   * keyboard-focusable scroller in Chromium 130+) that `FOCUSABLE_SELECTOR` below does not match,
   * or a duplicate landing produced by a script-driven focus redirect. */
  kbdId: string | null
  tag: string
  /** The element's own `role` attribute, empty when absent — for failure messages only, alongside
   * `outerHTMLPrefix`, so an unstamped stop can be named rather than merely counted. */
  role: string
  /** `getByRole`-style accessible name approximation, for failure messages only. */
  name: string
  /** `outerHTML`, truncated — the last resort for naming a stop a `kbdId`/`role`/`name` triple
   * still leaves ambiguous. */
  outerHTMLPrefix: string
  /** True when the focused element sits inside the route's one `main` landmark or its `header`/
   * `footer` chrome — FR-049's "no trap outside a modal surface that defines its own", read the
   * cheap way: a route-level walk has no modal open, so every reachable element must be chrome or
   * content. */
  insideChrome: boolean
  /** The touch-footprint sweep's own measurement, per `specs/README.md`'s "Minimum interactive
   * footprint": the element's own box, except an `<input>` wrapped by its own `<label>` (as
   * opposed to an `htmlFor` association, which leaves the control unwrapped), measured by the
   * label's box instead — the real hit area a pointer actually reaches. */
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
  /** True only when the walk's own final Tab press returned focus to `document.body` (or off the
   * document entirely) before `maxSteps` ran out — the walk closed the cycle rather than merely
   * running out of budget mid-cycle. False means every one of `maxSteps` presses landed on a real
   * element and the walk never saw the cycle close: a trap that begins only after every candidate
   * has already been reached once (a footer loop cycling back into the header) produces exactly
   * this shape, and `candidateCount === reachedIds.size` alone — the walk's own pre-remediation
   * assertion — could not distinguish it from a clean route. */
  wrapped: boolean
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
  let wrapped = false

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
      // A wrapping <label> (never an htmlFor association, which leaves the input on its own) is
      // the real hit area a pointer reaches — `specs/README.md`'s own "Minimum interactive
      // footprint" convention.
      const wrappingLabel = el.tagName === 'INPUT' ? el.closest('label') : null
      const rect = (wrappingLabel ?? el).getBoundingClientRect()
      const parentText = el.parentElement?.textContent?.trim() ?? ''
      const ownText = el.textContent?.trim() ?? ''
      const dataVariant = el.getAttribute('data-variant')
      const exemptInlineLink =
        el.tagName === 'A' && dataVariant === 'inline' && parentText.length > ownText.length

      return {
        kbdId: el.getAttribute('data-kbd-walk-id'),
        tag: el.tagName.toLowerCase(),
        role: el.getAttribute('role') ?? '',
        name: (el.getAttribute('aria-label') ?? el.textContent ?? '').trim().slice(0, 60),
        outerHTMLPrefix: el.outerHTML.slice(0, 160),
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

    if (step === null) {
      wrapped = true // focus returned to `document.body` (or off the document) — the cycle closed
      break
    }
    steps.push(step)
  }

  return { candidateCount, steps, wrapped }
}

/** The one place FR-049's four route-level guards live — shared verbatim between
 * `route-keyboard.spec.ts` (real routes) and `keyboard-walk.test.ts` (planted pages), so a
 * remediation here can never fix one caller's coverage while leaving the other's assertion stale.
 * Each `expect` throws on its own first failure (Playwright's normal behaviour), so a caller that
 * wants to observe one guard in isolation should plant a page where only that guard's condition is
 * false. */
export function assertFullTabCoverage(result: TabWalkResult, context: string): void {
  const { candidateCount, steps, wrapped } = result

  // Guard: every reached stop was one of the candidates this walk actually stamped — an unstamped
  // focusable (a `<summary>`, a keyboard-focusable scroller in Chromium 130+) or a duplicate
  // landing produced by a script-driven focus redirect both surface here, named rather than merely
  // folded into a count.
  const unstamped = steps.filter((step) => step.kbdId === null)
  expect(
    unstamped.length,
    `${context}: the Tab walk reached ${unstamped.length} element(s) never stamped as a candidate — ` +
      unstamped
        .map(
          (step) =>
            `<${step.tag}${step.role ? ` role="${step.role}"` : ''}> "${step.name}" (${step.outerHTMLPrefix})`,
        )
        .join('; '),
  ).toBe(0)

  // Guard: exactly one stop per candidate — neither an early exhaustion (a genuine trap that stops
  // short) nor a silent revisit (a duplicate `reachedIds`, a `Set`, would have deduped away).
  expect(
    steps.length,
    `${context}: the Tab walk produced ${steps.length} stop(s) for ${candidateCount} candidate(s)`,
  ).toBe(candidateCount)

  const idCounts = new Map<string, number>()
  for (const step of steps) {
    // `kbdId` is non-null here: the `unstamped` guard above already threw if any step's were null.
    idCounts.set(step.kbdId as string, (idCounts.get(step.kbdId as string) ?? 0) + 1)
  }
  const duplicates = [...idCounts.entries()].filter(([, count]) => count > 1)
  expect(
    duplicates.length,
    `${context}: the Tab walk reached the same element more than once: ` +
      duplicates.map(([id, count]) => `#${id} (${count}x)`).join(', '),
  ).toBe(0)

  // Guard: FR-049's "in order". DOM order is the correct oracle here — verified by grepping the
  // whole tree for a positive `tabindex` (`grep -rn tabindex apps/web/src packages/design-system/
  // src`), which finds none; every declared `tabindex` in this codebase is `"-1"` (removed from the
  // tab sequence entirely, already excluded by `FOCUSABLE_SELECTOR`) or `"0"` (natural order,
  // identical to DOM order). `kbdId` is stamped 0..N-1 in `querySelectorAll`'s own DOM-order
  // traversal, so the walk's own stop order must reproduce that exact sequence.
  const observedOrder = steps.map((step) => step.kbdId)
  const domOrder = Array.from({ length: candidateCount }, (_, index) => String(index))
  expect(
    observedOrder,
    `${context}: the Tab walk reached candidates out of DOM order: [${observedOrder.join(', ')}] ` +
      `(expected [${domOrder.join(', ')}])`,
  ).toEqual(domOrder)

  // Guard: every stop above proved unique and reachable, but that alone cannot distinguish a clean
  // route from a trap that only starts after every candidate has already been reached once (a
  // footer loop cycling back into the header) — `wrapped` is what proves the walk closed the cycle
  // rather than merely exhausting its step budget mid-trap.
  expect(
    wrapped,
    `${context}: the Tab walk used its full step budget without focus ever wrapping back to the ` +
      `document — a trap that only starts after every candidate has already been reached once ` +
      `would look identical to a clean route on every guard above`,
  ).toBe(true)
}
