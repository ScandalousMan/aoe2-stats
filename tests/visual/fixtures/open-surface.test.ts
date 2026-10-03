// T676: no run showed `walkOpenSurface` / `assertSurfaceKeyboard` fail on a real defect, and a guard
// that has never failed proves nothing. This plants small static pages (`page.setContent`, no app
// build — the pattern `keyboard-walk.test.ts` uses) that each break exactly one clause of the
// `Menu` or `Dialog` keyboard contract, beside a passing control for each surface, and asserts the
// guard names the broken clause.
import { expect, test, type Page } from '@playwright/test'
import { assertFocusRingVisible } from './keyboard-walk'
import { assertSurfaceKeyboard, distinctSurfaceStops, walkOpenSurface } from './open-surface'
import { assertStopsClearFootprint } from './touch-footprint'

interface MenuOptions {
  /** Two items carry tabindex="0" instead of one. */
  twoTabStops?: boolean
  /** ArrowDown on the last item does nothing instead of wrapping. */
  noWrap?: boolean
  /** Escape closes the menu but leaves focus on `<body>`. */
  escapeLosesFocus?: boolean
  /** The menu opens without moving focus into it. */
  focusStaysOnPage?: boolean
  /** ArrowDown from the last item moves focus to a button outside the menu. */
  leaksFocus?: boolean
  /** Inline style every item carries, to plant a short item or a missing ring. */
  itemStyle?: string
}

const ITEMS = ['Alpha', 'Beta', 'Gamma']

function menuPage(options: MenuOptions = {}): string {
  return `
    <button id="trigger" aria-haspopup="menu" aria-expanded="true">Open</button>
    <div id="menu" role="menu">
      ${ITEMS.map(
        (label, index) =>
          `<button role="menuitem" tabindex="${index === 0 || (options.twoTabStops && index === 1) ? 0 : -1}" style="${options.itemStyle ?? 'height: 48px; width: 200px; outline: 2px solid black;'}">${label}</button>`,
      ).join('')}
    </div>
    <button id="outside">Outside</button>
    <script>
      const items = Array.from(document.querySelectorAll('[role=menuitem]'))
      const trigger = document.getElementById('trigger')
      function go(index) { items[index].focus() }
      items.forEach((item, index) => item.addEventListener('keydown', (event) => {
        if (event.key === 'ArrowDown') {
          event.preventDefault()
          if (index === items.length - 1) {
            if (${Boolean(options.leaksFocus)}) document.getElementById('outside').focus()
            else if (!${Boolean(options.noWrap)}) go(0)
          } else go(index + 1)
        }
        if (event.key === 'ArrowUp') { event.preventDefault(); go((index + items.length - 1) % items.length) }
        if (event.key === 'Home') { event.preventDefault(); go(0) }
        if (event.key === 'Escape') {
          event.preventDefault()
          document.getElementById('menu').remove()
          trigger.setAttribute('aria-expanded', 'false')
          if (${Boolean(options.escapeLosesFocus)}) document.activeElement.blur()
          else trigger.focus()
        }
      }))
      if (!${Boolean(options.focusStaysOnPage)}) go(0)
    </script>`
}

interface DialogOptions {
  /** Tab on the last control does not wrap back to the first. */
  noTrap?: boolean
  /** Shift+Tab on the first control does not wrap to the last. */
  noReverseTrap?: boolean
  /** Escape does nothing. */
  escapeIgnored?: boolean
  /** Opening the dialog leaves focus on the page behind it. */
  focusStaysOnPage?: boolean
}

function dialogPage(options: DialogOptions = {}): string {
  return `
    <button id="behind">Behind the dialog</button>
    <div id="dialog" role="dialog" aria-modal="true" aria-labelledby="h">
      <h2 id="h" tabindex="-1">Are you sure?</h2>
      <label><input id="ack" type="checkbox"> I understand</label>
      <button id="confirm">Confirm</button>
      <button id="cancel">Cancel</button>
    </div>
    <script>
      const dialog = document.getElementById('dialog')
      const controls = ['ack', 'confirm', 'cancel'].map((id) => document.getElementById(id))
      document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && !${Boolean(options.escapeIgnored)}) { dialog.remove(); return }
        if (event.key !== 'Tab') return
        const active = document.activeElement
        if (!event.shiftKey && active === controls[controls.length - 1] && !${Boolean(options.noTrap)}) {
          event.preventDefault(); controls[0].focus()
        }
        if (event.shiftKey && (active === controls[0] || active === document.getElementById('h')) &&
            !${Boolean(options.noReverseTrap)}) {
          event.preventDefault(); controls[controls.length - 1].focus()
        }
      })
      if (!${Boolean(options.focusStaysOnPage)}) document.getElementById('h').focus()
    </script>`
}

async function walkMenu(page: Page, options?: MenuOptions) {
  await page.setContent(menuPage(options))
  return walkOpenSurface(page, 'menu')
}

async function walkDialog(page: Page, options?: DialogOptions) {
  await page.setContent(dialogPage(options))
  return walkOpenSurface(page, 'dialog')
}

test.describe('open-surface keyboard guard, planted pages', () => {
  test('control: a well-behaved menu passes', async ({ page }) => {
    const walk = await walkMenu(page)
    expect(walk.itemCount).toBe(3)
    assertSurfaceKeyboard(walk, 'planted')
  })

  test('control: a well-behaved dialog passes', async ({ page }) => {
    const walk = await walkDialog(page)
    // Three focusable controls: the checkbox, Confirm and Cancel (the heading is tabindex -1).
    expect(walk.itemCount).toBe(3)
    assertSurfaceKeyboard(walk, 'planted')
  })

  test('a menu with two Tab stops fails the roving-tabindex clause', async ({ page }) => {
    const walk = await walkMenu(page, { twoTabStops: true })
    expect(() => assertSurfaceKeyboard(walk, 'planted')).toThrow(
      /2 menu items carry tabindex="0"; roving tabindex means exactly one/,
    )
  })

  test('a menu that does not wrap at the end fails', async ({ page }) => {
    const walk = await walkMenu(page, { noWrap: true })
    expect(() => assertSurfaceKeyboard(walk, 'planted')).toThrow(
      /the menu's keys visited \[0, 1, 2, 2\] but its contract is \[0, 1, 2, 0\]/,
    )
  })

  test('a menu whose arrow key leaks focus outside it fails', async ({ page }) => {
    const walk = await walkMenu(page, { leaksFocus: true })
    expect(() => assertSurfaceKeyboard(walk, 'planted')).toThrow(/focus left the menu/)
  })

  test('a menu that does not return focus to its trigger on Escape fails', async ({ page }) => {
    const walk = await walkMenu(page, { escapeLosesFocus: true })
    expect(() => assertSurfaceKeyboard(walk, 'planted')).toThrow(
      /Escape did not return focus to the menu's trigger/,
    )
  })

  test('a menu that opens without moving focus into it fails', async ({ page }) => {
    const walk = await walkMenu(page, { focusStaysOnPage: true })
    expect(() => assertSurfaceKeyboard(walk, 'planted')).toThrow(
      /focus was not inside the menu when it opened/,
    )
  })

  test('a dialog that does not trap Tab fails: focus walks out to the page behind it', async ({
    page,
  }) => {
    const walk = await walkDialog(page, { noTrap: true })
    expect(() => assertSurfaceKeyboard(walk, 'planted')).toThrow(/focus left the dialog|visited/)
  })

  test('a dialog that does not trap Shift+Tab fails', async ({ page }) => {
    const walk = await walkDialog(page, { noReverseTrap: true })
    expect(() => assertSurfaceKeyboard(walk, 'planted')).toThrow(
      /moving backwards from the first item did not wrap to the last \(#2\)/,
    )
  })

  test('a dialog that ignores Escape fails', async ({ page }) => {
    const walk = await walkDialog(page, { escapeIgnored: true })
    expect(() => assertSurfaceKeyboard(walk, 'planted')).toThrow(/Escape did not close the dialog/)
  })

  test('a dialog that opens without moving focus into it fails', async ({ page }) => {
    const walk = await walkDialog(page, { focusStaysOnPage: true })
    expect(() => assertSurfaceKeyboard(walk, 'planted')).toThrow(
      /focus was not inside the dialog when it opened/,
    )
  })

  // What the focus-visibility and touch-footprint suites do with an open surface's stops: the same
  // `distinctSurfaceStops` feeding `assertFocusRingVisible` and `assertStopsClearFootprint`. A short
  // item or a missing ring inside an open menu must reach those assertions — the whole point of
  // walking the surface at all, since a Tab walk never opens it.
  test('a 30px item inside an open menu fails the touch-footprint floor', async ({ page }) => {
    const walk = await walkMenu(page, {
      itemStyle: 'height: 30px; width: 200px; outline: 2px solid black;',
    })

    expect(() => assertStopsClearFootprint(distinctSurfaceStops(walk), 'planted')).toThrow(
      /<button> "Alpha" is 30\.0px tall, below the 44px floor/,
    )
  })

  test('a menu item with no focus ring fails the focus-visibility assertion', async ({ page }) => {
    const walk = await walkMenu(page, { itemStyle: 'height: 48px; width: 200px; outline: none;' })

    const [first] = distinctSurfaceStops(walk)
    expect(() => assertFocusRingVisible(first, 'planted')).toThrow(
      /painted no outline while focus-visible/,
    )
  })

  test('control: 48px items with a 2px ring clear both assertions', async ({ page }) => {
    const walk = await walkMenu(page)

    const stops = distinctSurfaceStops(walk)
    expect(stops).toHaveLength(3)
    assertStopsClearFootprint(stops, 'planted')
    for (const stop of stops) assertFocusRingVisible(stop, 'planted')
  })
})
