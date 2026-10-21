// What a Tab press can land on inside a container: the focus trap's definition of a stop.
//
// The rule restates the one the route keyboard walk uses (`FOCUSABLE_SELECTOR` plus its
// `checkVisibility` filter in `tests/visual/fixtures/keyboard-walk.ts`) because a package may not
// import from `tests/`. `tests/visual/fixtures/focusable-rule.test.ts` renders one page of
// candidates in Chromium and pins the two rules on each one; a branch added to either rule needs a
// candidate there before the pin can see it.
// It is stricter than the walk in two places, both because a browser never focuses the element:
// a control inside a disabled `fieldset` (`:disabled`) and anything inside an `inert` subtree.

/** `button`, `input`, `select` and `textarea` that are not `disabled` (a hidden input is never a
 * stop), a link with an `href`, and anything carrying a `tabindex` other than -1. */
export const FOCUSABLE_STOP_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), ' +
  'select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

// Without layout (jsdom: no `checkVisibility`, no client rects) the unrendered cases a browser
// answers from layout are read from the markup: a `hidden` ancestor, a `display: none` ancestor
// and the element's own computed `visibility`.
function isRenderedWithoutLayout(element: HTMLElement): boolean {
  if (element.closest('[hidden]') !== null) return false
  for (let node: HTMLElement | null = element; node !== null; node = node.parentElement) {
    if (getComputedStyle(node).display === 'none') return false
  }
  const visibility = getComputedStyle(element).visibility
  return visibility !== 'hidden' && visibility !== 'collapse'
}

function isRendered(element: HTMLElement): boolean {
  return typeof element.checkVisibility === 'function'
    ? element.checkVisibility({ visibilityProperty: true })
    : isRenderedWithoutLayout(element)
}

/** Whether a Tab press can land on `element`: it matches `FOCUSABLE_STOP_SELECTOR`, is not
 * natively `:disabled` (which also covers a disabled `fieldset`), is not inside an `inert`
 * subtree, and is rendered. `aria-disabled` does not matter: a `loading` `Button` keeps focus. */
export function isFocusableStop(element: HTMLElement): boolean {
  return (
    element.matches(FOCUSABLE_STOP_SELECTOR) &&
    !element.matches(':disabled') &&
    element.closest('[inert]') === null &&
    isRendered(element)
  )
}

/** Every stop inside `root`, in DOM order. */
export function focusableStops(root: HTMLElement): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE_STOP_SELECTOR)).filter(
    isFocusableStop,
  )
}
