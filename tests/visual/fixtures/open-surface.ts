// T676 (production-readiness item 13, extending T674's four route-level sub-suites): the keyboard
// walk over an *opened* surface. `walkTabOrder` (`./keyboard-walk`) presses Tab across a route at
// rest and never opens a `Dialog` or a `Menu`, so their contents were neither walked, ring-checked
// nor measured. Both surfaces have a keyboard contract of their own that a Tab walk would not even
// observe, so this file walks each by *its* contract and hands back the same `TabStop` facts
// (`readFocusedStop`) the focus-visibility and touch-footprint assertions already consume:
//
// - `Dialog` (`packages/design-system/src/primitives/Dialog`): focus moves into the dialog on open;
//   Tab cycles through its focusable elements and wraps from the last back to the first, Shift+Tab
//   from the first wraps to the last (FR-049's "a trap outside a modal surface that defines its own"
//   — here the modal *defines* one, so it is asserted present rather than absent); Escape closes it.
// - `Menu` (`packages/design-system/src/primitives/Menu`): focus moves to an item on open; exactly
//   one item is a Tab stop (roving tabindex); Home, ArrowDown and ArrowUp visit every item once, in
//   order, wrapping at both ends; Escape closes the menu and returns focus to its trigger.
//
// Every assertion lives in `assertSurfaceKeyboard`, shared verbatim between the route suites and
// `open-surface.test.ts`'s planted pages, the same arrangement `assertFullTabCoverage` has with
// `keyboard-walk.test.ts` — so a guard is shown failing on a page carrying exactly the defect it
// names, and cannot drift from the real-route assertion.
import { expect, type Locator, type Page } from '@playwright/test'
import {
  FOCUSABLE_SELECTOR,
  readFocusedStop,
  resetFocusToDocumentStart,
  type TabStop,
} from './keyboard-walk'

export type SurfaceKind = 'menu' | 'dialog'

export const SURFACE_SELECTOR: Record<SurfaceKind, string> = {
  menu: '[role="menu"]',
  dialog: '[role="dialog"]',
}

// What a Tab press can reach inside a `Dialog` is `FOCUSABLE_SELECTOR`, the selector `walkTabOrder`
// stamps (`./keyboard-walk`) — imported, never restated, so the two cannot drift.

// Every item role a `Menu` renders: `menuitem` (`actions`), `menuitemradio` (`selection`), and
// `menuitemcheckbox` for completeness. Matched on the role prefix, never on a class.
const MENU_ITEM = '[role^="menuitem"]'

export interface SurfaceWalk {
  kind: SurfaceKind
  /** How many keyboard-reachable items the open surface holds. */
  itemCount: number
  /** Whether focus was already inside the surface the moment it opened. */
  focusInsideOnOpen: boolean
  /** `menu` only: how many items carry `tabindex="0"` — the roving-tabindex contract says one. */
  rovingTabStops: number
  /** One stop per item, in the order the surface's own keys visited them. For a `dialog` this is
   * the Tab walk plus one extra stop (the wrap back to the first). */
  steps: TabStop[]
  /** The stop reached by moving *backwards* from the first item (ArrowUp / Shift+Tab) — must be
   * the last item. */
  reverseStop: TabStop | null
  /** Whether the surface was gone after Escape. */
  closedByEscape: boolean
  /** `menu` only: whether focus is back on the surface's own trigger after Escape. */
  focusReturnedToTrigger: boolean
}

async function stampItems(page: Page, surface: string, itemSelector: string): Promise<number> {
  return page.evaluate(
    ({ surfaceSelector, selector }) => {
      const root = document.querySelector(surfaceSelector)
      if (root === null) return 0
      const items = Array.from(root.querySelectorAll<HTMLElement>(selector)).filter((el) =>
        el.checkVisibility({ visibilityProperty: true }),
      )
      items.forEach((el, index) => el.setAttribute('data-kbd-walk-id', String(index)))
      return items.length
    },
    { surfaceSelector: surface, selector: itemSelector },
  )
}

// A `Menu` moves focus from a React effect after the key event, so a read taken the instant
// `keyboard.press` resolves can still see the previous item. Two animation frames is long enough
// for React to commit the state change and run the focus effect; unlike waiting for the focused
// item to *change*, it costs the same whether or not focus moves (Home on the first item, a
// one-item menu), so a key that correctly leaves focus where it is never pays a timeout.
async function pressAndSettle(page: Page, key: string): Promise<void> {
  await page.keyboard.press(key)
  await page.evaluate(
    () =>
      new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      ),
  )
}

async function isInside(page: Page, surface: string): Promise<boolean> {
  return page.evaluate((selector) => document.activeElement?.closest(selector) != null, surface)
}

/** Walks the one `Menu` or `Dialog` currently open. The caller has already opened it *by keyboard*
 * (`tabTo` + Enter, see `app-routes-harness.ts`'s scenarios) and calls this with the surface on
 * screen; it leaves the surface closed, so it must be the last thing a test does with the page. */
export async function walkOpenSurface(page: Page, kind: SurfaceKind): Promise<SurfaceWalk> {
  const surface = SURFACE_SELECTOR[kind]
  await page.locator(surface).waitFor({ state: 'visible' })
  const focusInsideOnOpen = await isInside(page, surface)

  const itemCount = await stampItems(
    page,
    surface,
    kind === 'menu' ? MENU_ITEM : FOCUSABLE_SELECTOR,
  )
  const rovingTabStops =
    kind === 'menu' ? await page.locator(`${surface} ${MENU_ITEM}[tabindex="0"]`).count() : 0

  const steps: TabStop[] = []
  let reverseStop: TabStop | null = null

  if (kind === 'menu') {
    // Home puts focus on the first item whatever the item the menu opened on, so the walk always
    // starts from item 0 and the order is comparable.
    await pressAndSettle(page, 'Home')
    for (let i = 0; i < itemCount; i += 1) {
      const stop = await readFocusedStop(page, surface)
      if (stop === null) break
      steps.push(stop)
      if (i < itemCount - 1) await pressAndSettle(page, 'ArrowDown')
    }
    // One more ArrowDown from the last item: the roving cursor wraps to the first.
    await pressAndSettle(page, 'ArrowDown')
    const wrap = await readFocusedStop(page, surface)
    if (wrap !== null) steps.push(wrap)
    // And ArrowUp from the first item wraps to the last.
    await pressAndSettle(page, 'ArrowUp')
    reverseStop = await readFocusedStop(page, surface)
  } else {
    // The dialog opened with focus on its heading (not a candidate itself); N+1 Tab presses visit
    // every focusable once and then wrap.
    for (let i = 0; i < itemCount + 1; i += 1) {
      await page.keyboard.press('Tab')
      const stop = await readFocusedStop(page, surface)
      if (stop === null) break
      steps.push(stop)
    }
    // Back to the first item (the wrap), then one step backwards must land on the last.
    await page.keyboard.press('Shift+Tab')
    reverseStop = await readFocusedStop(page, surface)
  }

  // The trigger that opened this menu is the one `aria-haspopup="menu"` button still expanded.
  // Stamp it before Escape so "focus is back on the trigger" means *that* element, not any
  // collapsed menu button on the page (a header with several menus has several).
  const triggerStamped =
    kind === 'menu' &&
    (await page.evaluate(() => {
      const trigger = document.querySelector('[aria-haspopup="menu"][aria-expanded="true"]')
      trigger?.setAttribute('data-kbd-menu-trigger', '')
      return trigger !== null
    }))

  await page.keyboard.press('Escape')
  const closedByEscape = (await page.locator(surface).count()) === 0
  const focusReturnedToTrigger =
    kind === 'menu' && triggerStamped
      ? await page.evaluate(() => {
          const active = document.activeElement
          return (
            active?.hasAttribute('data-kbd-menu-trigger') === true &&
            active.getAttribute('aria-expanded') === 'false'
          )
        })
      : false

  return {
    kind,
    itemCount,
    focusInsideOnOpen,
    rovingTabStops,
    steps,
    reverseStop,
    closedByEscape,
    focusReturnedToTrigger,
  }
}

/** The one place the open-surface keyboard contract lives (see the header). Each `expect` throws on
 * its own first failure, so a caller isolating one guard plants a page where only that guard's
 * condition is false. */
export function assertSurfaceKeyboard(walk: SurfaceWalk, context: string): void {
  const { kind, itemCount, steps } = walk
  expect(
    itemCount,
    `${context}: the open ${kind} holds no keyboard-reachable item`,
  ).toBeGreaterThan(0)
  expect(
    walk.focusInsideOnOpen,
    `${context}: focus was not inside the ${kind} when it opened — a keyboard user is left on the ` +
      `page behind it`,
  ).toBe(true)

  // Every stop sits inside the surface: nothing outside it was reached while it was open.
  const outside = steps.filter((step) => !step.insideChrome)
  expect(
    outside.length,
    `${context}: focus left the ${kind} during its walk — ` +
      outside.map((step) => `<${step.tag}> "${step.name}" (${step.outerHTMLPrefix})`).join('; '),
  ).toBe(0)

  const ids = steps.map((step) => step.kbdId)
  const inOrder = Array.from({ length: itemCount }, (_, index) => String(index))
  // Both surfaces end their walk on one extra stop: the wrap back to the first item.
  const expected = [...inOrder, '0']
  expect(
    ids,
    `${context}: the ${kind}'s keys visited [${ids.join(', ')}] but its contract is ` +
      `[${expected.join(', ')}] — every item once, in order, then a wrap to the first`,
  ).toEqual(expected)

  expect(
    walk.reverseStop?.kbdId ?? null,
    `${context}: moving backwards from the first item did not wrap to the last (#${itemCount - 1})`,
  ).toBe(String(itemCount - 1))

  if (kind === 'menu') {
    expect(
      walk.rovingTabStops,
      `${context}: ${walk.rovingTabStops} menu items carry tabindex="0"; roving tabindex means ` +
        `exactly one`,
    ).toBe(1)
    expect(
      walk.focusReturnedToTrigger,
      `${context}: Escape did not return focus to the menu's trigger`,
    ).toBe(true)
  }
  expect(walk.closedByEscape, `${context}: Escape did not close the ${kind}`).toBe(true)
}

/** The surface walk's stops, minus the one extra wrap stop, for the focus-ring and touch-footprint
 * assertions — each real item is measured once, not twice. */
export function distinctSurfaceStops(walk: SurfaceWalk): TabStop[] {
  const seen = new Set<string | null>()
  return walk.steps.filter((step) => {
    if (seen.has(step.kbdId)) return false
    seen.add(step.kbdId)
    return true
  })
}

/** Tab until `target` is the focused element — "opened by keyboard" starting where a keyboard user
 * does, not with a programmatic `focus()` that would skip proving the trigger is reachable. Bounded
 * by `maxPresses` so an unreachable trigger fails with its own message rather than hanging.
 * Returns how many Tab presses it took. */
export async function tabTo(page: Page, target: Locator, maxPresses = 80): Promise<number> {
  await target.waitFor({ state: 'visible' })
  const handle = await target.elementHandle()
  if (handle === null) throw new Error('tabTo: the target locator resolved to no element')
  await resetFocusToDocumentStart(page)
  for (let i = 0; i < maxPresses; i += 1) {
    await page.keyboard.press('Tab')
    const reached = await handle.evaluate((el) => el === document.activeElement)
    if (reached) return i + 1
  }
  throw new Error(`tabTo: ${maxPresses} Tab presses never reached the target`)
}

/** Opens the `Menu` behind `trigger` the way a keyboard user does: Tab to it, press Enter. */
export async function openMenuByKeyboard(page: Page, trigger: Locator): Promise<void> {
  await tabTo(page, trigger)
  await page.keyboard.press('Enter')
  await page.locator(SURFACE_SELECTOR.menu).waitFor({ state: 'visible' })
}
