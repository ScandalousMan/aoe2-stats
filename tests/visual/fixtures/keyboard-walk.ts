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
//
// Remediation of review finding M1 (PR #102): `route-focus-visibility.spec.ts`'s per-step assertion
// used to (a) never check outline *width*, so a 0px or 1px ring passed the same as a real one, (b)
// resolve the background a ring is judged against starting from the focused element itself, which
// is wrong for an outward-offset ring (`outline-offset` > 0) — that ring is painted over the
// PARENT's surface, not the element's own — and (c) treat a translucent background (alpha < 1) as
// opaque the instant it was merely non-zero, reading its raw channel values instead of compositing
// it over what is actually behind it. `assertFocusRingVisible` below is now the one place that
// judgment lives too, shared between the real-route suite and this file's own planted-page guard
// tests (`focus-ring-walk.test.ts`), for the same reason `assertFullTabCoverage` above is shared.
import { expect, type Page } from '@playwright/test'
// `.mjs` rather than `.cjs`: `focus-ring.spec.ts`'s own header comment explains why (Vite transforms
// a local ESM module, `Colour.stories.tsx` also imports it, and Node has no CommonJS sibling to fall
// back to for either consumer).
import { contrastRatioRgb } from '../../../packages/design-system/tokens/contrast.mjs'

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
   * footprint": the element's own box, except a labelable control (`input`, `select`, `textarea`,
   * `button`, `meter`, `output`, `progress`) wrapped by its own `<label>` (as opposed to an
   * `htmlFor` association, which leaves the control unwrapped), measured by the label's box
   * instead — the real hit area a pointer actually reaches. */
  rect: { width: number; height: number }
  isFocusVisible: boolean
  outline: { style: string; width: string; color: string }
  /** The surface the focus ring is actually painted over, as an opaque `rgb(...)` triple. Starts
   * from the element's own ancestor chain, except when `outline-offset` > 0 (an outward ring, e.g.
   * Menu's trigger/footer item), which is painted over the PARENT's surface instead — the walk
   * starts there. Any translucent layer encountered (alpha < 1) is composited over the next opaque
   * ancestor found further up (defaulting to the page's own white canvas backdrop if none is)
   * rather than read as-is, so this is never a raw, uncomposited `rgba(...)` string. PR #102 review
   * finding M1: this used to always start from the element itself and stop at the first
   * non-transparent layer regardless of its alpha. */
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

      const computed = getComputedStyle(el)

      // PR #102 review finding M1: an outward ring (`outline-offset` > 0) is painted over the
      // PARENT's surface, not the element's own — start the walk there instead whenever that is
      // the case, matching what a real render actually shows behind the ring.
      const outlineOffsetPx = parseFloat(computed.outlineOffset) || 0
      const backgroundStartNode: Element =
        outlineOffsetPx > 0 && el.parentElement ? el.parentElement : el

      function parseLayer(bg: string): { r: number; g: number; b: number; alpha: number } | null {
        const match = bg.match(/rgba?\(([^)]+)\)/)
        if (!match) return null
        const parts = match[1].split(',').map((part) => parseFloat(part.trim()))
        const [r, g, b] = parts
        return { r, g, b, alpha: parts[3] ?? 1 }
      }

      // PR #102 review finding M1: a translucent background (alpha < 1) used to be treated as
      // opaque the instant it was merely non-zero, reading its raw channel values instead of what a
      // real render actually composites it over. Collect every non-transparent layer walking up
      // from `backgroundStartNode`, stopping once a fully opaque one is found.
      const layers: Array<{ r: number; g: number; b: number; alpha: number }> = []
      let node: Element | null = backgroundStartNode
      while (node) {
        const layer = parseLayer(getComputedStyle(node).backgroundColor)
        if (layer && layer.alpha > 0) {
          layers.push(layer)
          if (layer.alpha >= 1) break
        }
        node = node.parentElement
      }
      // No opaque layer was found anywhere up to the document root (every ancestor declared a
      // translucent or absent background): default to the page's own white canvas backdrop, the
      // same default a browser paints behind a fully transparent <html>/<body>.
      if (layers.length === 0 || layers[layers.length - 1].alpha < 1) {
        layers.push({ r: 255, g: 255, b: 255, alpha: 1 })
      }
      // Composite back-to-front: the last layer found (the nearest opaque ancestor) is the
      // backdrop; each layer walking back toward the element blends its own colour over that
      // backdrop by its own alpha (the standard "over" operator) — the same colour a real render
      // paints, never a raw, uncomposited `rgba(...)` read off one layer alone.
      let composite = {
        r: layers[layers.length - 1].r,
        g: layers[layers.length - 1].g,
        b: layers[layers.length - 1].b,
      }
      for (let i = layers.length - 2; i >= 0; i -= 1) {
        const layer = layers[i]
        composite = {
          r: layer.r * layer.alpha + composite.r * (1 - layer.alpha),
          g: layer.g * layer.alpha + composite.g * (1 - layer.alpha),
          b: layer.b * layer.alpha + composite.b * (1 - layer.alpha),
        }
      }
      const backgroundColor = `rgb(${Math.round(composite.r)}, ${Math.round(composite.g)}, ${Math.round(composite.b)})`

      // A wrapping <label> (never an htmlFor association, which leaves the control unwrapped) is
      // the real hit area a pointer reaches — `specs/README.md`'s own "Minimum interactive
      // footprint" convention. Generalised (PR #102 review finding, low) from `<input>` alone to
      // every labelable control a `<label>` can wrap.
      const LABELABLE_TAGS = [
        'INPUT',
        'SELECT',
        'TEXTAREA',
        'BUTTON',
        'METER',
        'OUTPUT',
        'PROGRESS',
      ]
      const wrappingLabel = LABELABLE_TAGS.includes(el.tagName) ? el.closest('label') : null
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

// Converts a live `getComputedStyle` `rgb(...)`/`rgba(...)` string into the `{ r, g, b }` shape
// `contrastRatioRgb` takes — I/O specific to reading a rendered page, not part of the shared
// formula, the same split `tests/visual/focus-ring.spec.ts` documents for its own identical
// function. Shared here (rather than restated per caller) so `route-focus-visibility.spec.ts` and
// this file's own planted-page guard tests read one copy.
export function parseRgb(color: string): { r: number; g: number; b: number } {
  const match = color.match(/rgba?\(([^)]+)\)/)
  if (!match) throw new Error(`unparseable colour from getComputedStyle: "${color}"`)
  const [r, g, b] = match[1].split(',').map((part) => parseFloat(part.trim()))
  return { r, g, b }
}

// DS-4's one documented ring width, `tests/visual/focus-ring.spec.ts:307`'s own assertion
// (`expect(outline.width).toBe('2px')`) — named here rather than restated as a bare literal so a
// change to that contract can never update one call site and leave the other stale.
export const FOCUS_RING_OUTLINE_WIDTH_PX = '2px'

/** The one place the route-level focus-visibility contract lives — shared verbatim between
 * `route-focus-visibility.spec.ts` (real routes) and this file's own planted-page guard tests
 * (`focus-ring-walk.test.ts`), for the same reason `assertFullTabCoverage` above is shared: a
 * remediation here can never fix one caller's check while leaving the other's assertion stale.
 * Takes a `TabStop` (from `walkTabOrder`, itself usable against a `page.setContent` page, no app
 * build or Storybook story needed) rather than a `Locator`, so a planted static page and a real
 * route are asserted by the exact same function. Each `expect` throws on its own first failure, so
 * a caller isolating one guard should plant a page where only that guard's condition is false. */
export function assertFocusRingVisible(step: TabStop, context: string): void {
  expect(
    step.isFocusVisible,
    `${context}: <${step.tag}> "${step.name}" did not match :focus-visible after Tab`,
  ).toBe(true)
  expect(
    step.outline.style,
    `${context}: <${step.tag}> "${step.name}" painted no outline while focus-visible`,
  ).not.toBe('none')
  // PR #102 review finding M1: this width check did not exist before — a 0px or 1px ring passed
  // the same as a real one, because only `outline.style !== 'none'` and contrast were asserted.
  expect(
    step.outline.width,
    `${context}: <${step.tag}> "${step.name}"'s focus ring is ${step.outline.width} wide, not the ` +
      `${FOCUS_RING_OUTLINE_WIDTH_PX} \`tests/visual/focus-ring.spec.ts\` asserts for every ` +
      `component-level ring (DS-4's one documented ring)`,
  ).toBe(FOCUS_RING_OUTLINE_WIDTH_PX)

  const ratio = contrastRatioRgb(parseRgb(step.outline.color), parseRgb(step.backgroundColor))
  expect(
    ratio,
    `${context}: <${step.tag}> "${step.name}"'s focus ring (${step.outline.color}) is ` +
      `${ratio.toFixed(2)}:1 against its surface (${step.backgroundColor}), below the 3:1 WCAG ` +
      `1.4.11 non-text contrast floor`,
  ).toBeGreaterThanOrEqual(3)
}
