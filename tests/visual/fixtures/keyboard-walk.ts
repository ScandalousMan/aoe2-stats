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
   * from the element's own ancestor chain, except when `outline-offset` is greater than the
   * negative of the ring's own `outline-width` (an outward ring, or an inset ring shallower than
   * its own width — e.g. Menu's trigger/footer item), which is painted over the PARENT's surface
   * instead — the walk starts there. Any translucent layer encountered (alpha < 1) is composited
   * over the next opaque ancestor found further up (defaulting to the page's own white canvas
   * backdrop if none is) rather than read as-is, so this is never a raw, uncomposited `rgba(...)`
   * string. PR #102 review finding M1: this used to always start from the element itself and stop
   * at the first non-transparent layer regardless of its alpha, and used `outline-offset > 0` alone
   * as the outward-ring condition, missing offset 0 and any inset shallower than the ring's own
   * width. Can also hold `BACKGROUND_UNRESOLVABLE_DARK_SCHEME` verbatim instead of an `rgb(...)`
   * triple — the per-step walk found no opaque ancestor anywhere up to the document root AND the
   * page's `color-scheme` includes "dark", so assuming the browser's default light canvas (as it
   * does when no `color-scheme` is declared at all) would be a guess the page gave no grounds for.
   * `assertFocusRingVisible` checks for this marker itself, before ever handing the string to
   * `parseRgb`. */
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
export const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), ' +
  'select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

// PR #102 review finding M1 (remediation, part 3): the value `walkTabOrder`'s per-step
// `page.evaluate` returns as `backgroundColor` instead of an `rgb(...)` triple when no opaque
// ancestor was found anywhere up to the document root AND the page's own `color-scheme` includes
// "dark" — assuming the browser's default light canvas in that case would be a guess the page gave
// no grounds for (it only holds for a page that declares no `color-scheme` at all, or one that
// declares only "light"). Exported so `assertFocusRingVisible` can recognise the exact same string;
// passed into `page.evaluate` as an argument rather than closed over, because a function Playwright
// serialises into the browser cannot see an outer module constant.
export const BACKGROUND_UNRESOLVABLE_DARK_SCHEME = '__no-opaque-surface--dark-color-scheme__'

export async function walkTabOrder(page: Page, maxStepsOverride?: number): Promise<TabWalkResult> {
  const candidateCount = await page.evaluate(
    ({ selector }) => {
      // `checkVisibility()` walks the whole ancestor chain (a `display: none` or `visibility:
      // hidden` container the element itself declares neither of), unlike a `getComputedStyle`
      // read of the element alone: that used to count a button inside a hidden container as a
      // candidate the walk could never actually Tab to, producing a step-count mismatch that named
      // the wrong problem (candidates vs. stops) instead of the real one (an uncounted-as-hidden
      // element). `visibilityProperty: true` is required, not the default: `checkVisibility()`
      // without options checks `display` alone — a real route surfaced this the moment this filter
      // shipped, a `<button>` with its own `visibility: hidden` that the plain-`getComputedStyle`
      // filter had correctly excluded and the default `checkVisibility()` call wrongly readmitted,
      // since `visibility: hidden` (unlike `display: none`) removes an element from the real tab
      // order every bit as much.
      const candidates = Array.from(document.querySelectorAll<HTMLElement>(selector)).filter((el) =>
        el.checkVisibility({ visibilityProperty: true }),
      )
      candidates.forEach((el, index) => el.setAttribute('data-kbd-walk-id', String(index)))
      return candidates.length
    },
    { selector: FOCUSABLE_SELECTOR },
  )

  // Start from the top of the document, whatever had focus before (T676: a scenario's `prepare`
  // may have typed into a field or opened a menu). `blur()` alone leaves Chromium's sequential
  // focus navigation starting point where the element was, so the first Tab would continue from
  // there and skip every candidate before it. When something *was* focused, focus a throwaway
  // `tabindex="-1"` sentinel inserted as the body's first child and remove it again: the starting
  // point is then the top of the document, where a fresh page load leaves it. A page where nothing
  // was focused is left alone — its starting point is already right, and a sentinel would change
  // how a positive `tabindex` orders (this codebase declares none; `keyboard-walk.test.ts` plants
  // one deliberately).
  await page.evaluate(() => {
    const active = document.activeElement as HTMLElement | null
    if (active === null || active === document.body) return
    active.blur()
    const sentinel = document.createElement('span')
    sentinel.setAttribute('tabindex', '-1')
    document.body.insertBefore(sentinel, document.body.firstChild)
    sentinel.focus()
    sentinel.remove()
  })

  const maxSteps = maxStepsOverride ?? candidateCount + 5
  const steps: TabStop[] = []

  for (let i = 0; i < maxSteps; i += 1) {
    await page.keyboard.press('Tab')
    const step = await readFocusedStop(page)

    if (step === null) break // focus returned to `document.body` (or off the document)
    steps.push(step)
  }

  return { candidateCount, steps }
}

/** The route chrome `TabStop.insideChrome` is judged against by default: the route's one `main`
 * landmark plus its `header`/`footer`. An open `Menu` or `Dialog` passes its own surface selector
 * instead (`open-surface.ts`) — inside an open modal, the surface *is* the container. */
export const CHROME_SELECTOR = 'main, header, footer'

/** Reads everything one Tab stop's assertions need from `document.activeElement`, or `null` when
 * focus is on `document.body` (or off the document). Factored out of `walkTabOrder` (T676) so the
 * open-surface walks in `open-surface.ts` — arrow-key steps through a `Menu`, Tab steps inside a
 * `Dialog` — read the very same facts through the very same code, never a second copy that could
 * drift from the one the focus-ring and touch-footprint assertions were written against. */
export async function readFocusedStop(
  page: Page,
  chromeSelector: string = CHROME_SELECTOR,
): Promise<TabStop | null> {
  return page.evaluate(
    ({ unresolvableDarkSchemeMarker, chromeSelector }) => {
      const el = document.activeElement as HTMLElement | null
      if (el === null || el === document.body) return null

      // T676: finish the element's own *transitions* before reading anything off it. Tab has just
      // moved focus, so `outline-color` (a transitioned property on every `transition-colors`
      // element) is still on its way from the resting colour to the ring colour, and the first
      // frame would be judged instead of the ring a user ends up looking at. `finish()` jumps a
      // transition to its end state at once, so this costs no waiting. Only `CSSTransition`s: an
      // infinite `CSSAnimation` (`spin`, `pulse`) has no end to jump to.
      for (const animation of el.getAnimations()) {
        if (animation instanceof CSSTransition) animation.finish()
      }

      const computed = getComputedStyle(el)

      // PR #102 review finding M1 (remediation): an outline paints outward from the border edge by
      // its own width, so its outward edge sits at `offset + width`. The ring sits entirely over the
      // element's OWN surface only when that outward edge never crosses the border at all —
      // `offset <= -width`. Anything less negative than that — offset 0 included, where the ring
      // starts exactly at the border edge and paints entirely outward from there, and any
      // `-width < offset < 0`, where part of the ring is still outward — means at least part of the
      // ring is painted over the PARENT's surface instead. The pre-remediation `outlineOffsetPx > 0`
      // check treated offset 0 (and every negative offset) as "on the element", missing both.
      const outlineOffsetPx = parseFloat(computed.outlineOffset) || 0
      const outlineWidthPx = parseFloat(computed.outlineWidth) || 0
      const backgroundStartNode: Element =
        outlineOffsetPx > -outlineWidthPx && el.parentElement ? el.parentElement : el

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
      // translucent or absent background). A page that declares no `color-scheme` (or only "light")
      // behaves like the browser's own default light canvas, so falling back to white matches what
      // actually renders. PR #102 review finding M1 (remediation, part 3): a page whose `color-
      // scheme` includes "dark" gives no such guarantee — Chromium's own default canvas behind a
      // dark-scheme page is not white, and guessing white there would be exactly the "not what
      // actually renders" bug this walk exists to avoid — surface that as `backgroundColor` itself
      // instead of finishing a composite built on a guess.
      let unresolvableDarkScheme = false
      if (layers.length === 0 || layers[layers.length - 1].alpha < 1) {
        const rootColorScheme = getComputedStyle(document.documentElement).colorScheme
        if (rootColorScheme.includes('dark')) {
          unresolvableDarkScheme = true
        } else {
          layers.push({ r: 255, g: 255, b: 255, alpha: 1 })
        }
      }

      let backgroundColor: string
      if (unresolvableDarkScheme) {
        backgroundColor = unresolvableDarkSchemeMarker
      } else {
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
        backgroundColor = `rgb(${Math.round(composite.r)}, ${Math.round(composite.g)}, ${Math.round(composite.b)})`
      }

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
        insideChrome: el.closest(chromeSelector) !== null,
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
    },
    { unresolvableDarkSchemeMarker: BACKGROUND_UNRESOLVABLE_DARK_SCHEME, chromeSelector },
  )
}

/** The one place FR-049's route-level coverage guards live — shared verbatim between
 * `route-keyboard.spec.ts` (real routes) and `keyboard-walk.test.ts` (planted pages), so a
 * remediation here can never fix one caller's coverage while leaving the other's assertion stale.
 * Each `expect` throws on its own first failure (Playwright's normal behaviour), so a caller that
 * wants to observe one guard in isolation should plant a page where only that guard's condition is
 * false. */
export function assertFullTabCoverage(result: TabWalkResult, context: string): void {
  const { candidateCount, steps } = result

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
}

/** FR-049's "no trap outside a modal surface that defines its own", read the cheap way: a
 * route-level walk never opens a modal, so every stop the walk actually reaches must sit inside
 * the route's one `main` landmark or its `header`/`footer` chrome. Previously inline in
 * `route-keyboard.spec.ts` only — an `expect` per step with no planted-page guard test ever
 * exercising it — moved here so `keyboard-walk.test.ts` can plant the failing case the real-route
 * suite never did, the same reason `assertFullTabCoverage` above is shared rather than restated. */
export function assertStopsInsideChrome(steps: TabStop[], context: string): void {
  const outside = steps.filter((step) => !step.insideChrome)
  expect(
    outside.length,
    `${context}: the Tab walk reached ${outside.length} element(s) outside main/header/footer — ` +
      outside
        .map(
          (step) =>
            `<${step.tag}${step.role ? ` role="${step.role}"` : ''}> "${step.name}" (${step.outerHTMLPrefix})`,
        )
        .join('; '),
  ).toBe(0)
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

// PR #102 review finding M1 (remediation, part 2): `parseRgb` above deliberately keeps dropping the
// alpha channel — every existing caller (`route-focus-visibility.spec.ts`, `focus-ring.spec.ts`,
// and `focus-ring-walk.test.ts`'s own "sanity: the old assertion would have wrongly passed" checks)
// reads an already-opaque `backgroundColor` `rgb(...)` triple, or deliberately reconstructs the
// pre-remediation bug by reading a translucent colour through it. An outline colour is never
// guaranteed opaque (`rgba(0, 0, 0, 0.1)` is a real, valid `outline-color`), so `assertFocusRingVisible`
// below needs the alpha channel kept, not dropped — this sibling function is that one place.
export function parseRgba(color: string): { r: number; g: number; b: number; alpha: number } {
  const match = color.match(/rgba?\(([^)]+)\)/)
  if (!match) throw new Error(`unparseable colour from getComputedStyle: "${color}"`)
  const parts = match[1].split(',').map((part) => parseFloat(part.trim()))
  const [r, g, b] = parts
  return { r, g, b, alpha: parts[3] ?? 1 }
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

  // PR #102 review finding M1 (remediation, part 3): `walkTabOrder` returns this marker verbatim as
  // `backgroundColor` instead of an `rgb(...)` triple when no opaque ancestor was found and the
  // page's `color-scheme` includes "dark" — surface that as its own clear failure here, before ever
  // handing the marker string to `parseRgb`/`parseRgba`, which would otherwise throw an unrelated
  // "unparseable colour" error that names the wrong problem.
  expect(
    step.backgroundColor,
    `${context}: <${step.tag}> "${step.name}": no opaque surface behind the ring and color-scheme ` +
      `is dark; cannot assume a canvas colour`,
  ).not.toBe(BACKGROUND_UNRESOLVABLE_DARK_SCHEME)

  const background = parseRgb(step.backgroundColor)
  // PR #102 review finding M1 (remediation, part 2): an outline colour is never guaranteed opaque
  // (`rgba(0, 0, 0, 0.1)` is a real `outline-color`) — `parseRgb` drops alpha entirely, which used to
  // read a near-invisible translucent ring as though it were fully opaque. Composite it over the
  // already-resolved (opaque) background instead, the same "over" operator `walkTabOrder`'s own
  // background walk above uses for a translucent background layer.
  const outlineRgba = parseRgba(step.outline.color)
  const outlineColor = {
    r: outlineRgba.r * outlineRgba.alpha + background.r * (1 - outlineRgba.alpha),
    g: outlineRgba.g * outlineRgba.alpha + background.g * (1 - outlineRgba.alpha),
    b: outlineRgba.b * outlineRgba.alpha + background.b * (1 - outlineRgba.alpha),
  }

  const ratio = contrastRatioRgb(outlineColor, background)
  expect(
    ratio,
    `${context}: <${step.tag}> "${step.name}"'s focus ring (${step.outline.color}) is ` +
      `${ratio.toFixed(2)}:1 against its surface (${step.backgroundColor}), below the 3:1 WCAG ` +
      `1.4.11 non-text contrast floor`,
  ).toBeGreaterThanOrEqual(3)
}
