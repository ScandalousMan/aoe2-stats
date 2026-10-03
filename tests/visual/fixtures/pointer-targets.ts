// T676 (production-readiness item 13): the pointer-only half of the touch-footprint sweep. T674's
// `assertTouchFootprint` measures the stops a Tab walk reaches, so a target a finger can tap but a
// keyboard cannot reach (clickable, not focusable) was never measured. This sweep reads the two
// things the DOM does expose about such a target, over *every* element rather than the Tab stops:
//
// 1. its computed `cursor` is `pointer` — counted once, at the outermost element of a run, because
//    `cursor` is inherited and a `<span>` inside a pointer-cursor box is not a second target; and
// 2. it carries an interactive ARIA role.
//
// The DOM lists no event handlers, so those two are the signals; Chrome DevTools Protocol's
// `DOMDebugger.getEventListeners` is the documented fallback for a target both miss. It was checked
// and does not help here: this application is React, which attaches one listener per event type at
// the root container and none on the elements, so the CDP call would report the root for every
// element and discriminate nothing. A target that is neither a pointer cursor nor a role is
// therefore a defect in the target (a clickable `<div>` with no cursor and no role is also a
// WCAG 4.1.2 failure), not in this sweep.
//
// What is *not* swept here is anything `FOCUSABLE_SELECTOR` already matches (or sits inside): those
// are Tab stops, measured by `walkTabOrder` with the label-box and inline-link rules this sweep
// would otherwise have to duplicate. The two sweeps partition the targets rather than overlap.
//
// Contract: `packages/design-system/specs/README.md`'s "Minimum interactive footprint" — 44×44 in
// both axes.
import { expect, type Page } from '@playwright/test'
import { FOCUSABLE_SELECTOR } from './keyboard-walk'

// ARIA widget roles a pointer can activate. Landmarks, `group`, `dialog` and the like are
// deliberately absent: they are containers, not targets.
export const INTERACTIVE_ROLES = [
  'button',
  'link',
  'menuitem',
  'menuitemcheckbox',
  'menuitemradio',
  'checkbox',
  'radio',
  'switch',
  'tab',
  'option',
  'combobox',
  'searchbox',
  'textbox',
  'slider',
  'spinbutton',
  'treeitem',
] as const

export const MIN_TARGET_PX = 44

export interface PointerTarget {
  tag: string
  role: string
  cursor: string
  name: string
  outerHTMLPrefix: string
  width: number
  height: number
}

export async function collectPointerOnlyTargets(page: Page): Promise<PointerTarget[]> {
  return page.evaluate(
    ({ roles, focusable }) => {
      const found: Array<{
        tag: string
        role: string
        cursor: string
        name: string
        outerHTMLPrefix: string
        width: number
        height: number
      }> = []
      for (const el of Array.from(document.querySelectorAll<HTMLElement>('*'))) {
        if (!el.checkVisibility({ visibilityProperty: true })) continue
        // Tab stops (and their descendants) are `walkTabOrder`'s.
        if (el.closest(focusable) !== null) continue

        const role = el.getAttribute('role') ?? ''
        const cursor = getComputedStyle(el).cursor
        const parentCursor = el.parentElement ? getComputedStyle(el.parentElement).cursor : ''
        const pointerRoot = cursor === 'pointer' && parentCursor !== 'pointer'
        if (!pointerRoot && !roles.includes(role)) continue
        // A role on a non-rendered or zero-area box is no target a finger could land on.
        const rect = el.getBoundingClientRect()
        if (rect.width === 0 && rect.height === 0) continue

        found.push({
          tag: el.tagName.toLowerCase(),
          role,
          cursor,
          name: (el.getAttribute('aria-label') ?? el.textContent ?? '').trim().slice(0, 60),
          outerHTMLPrefix: el.outerHTML.slice(0, 160),
          width: rect.width,
          height: rect.height,
        })
      }
      return found
    },
    { roles: [...INTERACTIVE_ROLES] as string[], focusable: FOCUSABLE_SELECTOR },
  )
}

/** Fails naming every pointer-only target under the 44×44 floor. Returns what it examined so a
 * caller can also assert the sweep looked at something where a route is known to hold targets. */
export async function assertPointerTargetFootprint(
  page: Page,
  context: string,
): Promise<PointerTarget[]> {
  const targets = await collectPointerOnlyTargets(page)
  const small = targets.filter(
    (target) => target.width < MIN_TARGET_PX || target.height < MIN_TARGET_PX,
  )
  expect(
    small.length,
    `${context}: ${small.length} pointer-only target(s) are under ${MIN_TARGET_PX}×${MIN_TARGET_PX} — ` +
      small
        .map(
          (target) =>
            `<${target.tag}${target.role ? ` role="${target.role}"` : ''}> "${target.name}" ` +
            `is ${target.width.toFixed(1)}×${target.height.toFixed(1)} ` +
            `(cursor: ${target.cursor}; ${target.outerHTMLPrefix})`,
        )
        .join('; '),
  ).toBe(0)
  return targets
}
