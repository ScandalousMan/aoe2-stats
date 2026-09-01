// T096 defect 2 regression (visual review): every interactive primitive in this package composes
// `outline-none` (hide the default browser outline at rest) with `focus-visible:outline-2
// focus-visible:outline-offset-2 focus-visible:outline-focus-ring` — DS-4's one documented ring.
// Tailwind's `outline-none` sets the shared `--tw-outline-style` custom property to `none`
// unconditionally (`.outline-none{--tw-outline-style:none;outline-style:none}`), and `outline-2`
// only *reads* that property (`outline-style:var(--tw-outline-style)`) rather than resetting it —
// so the ring never painted under `:focus-visible`, on any of them, in either theme:
// `getComputedStyle(activeEl).outlineStyle === 'none'` even while `el.matches(':focus-visible')`
// was true. This is an interaction test, not a screenshot: no story in the static suite ever
// renders a focused control, which is exactly why the bug shipped unnoticed, and a screenshot
// proves nothing here unless something actually focuses the element via the keyboard first.
import { test, expect, type Locator, type Page } from '@playwright/test'

interface Control {
  /** Named explicitly per the remediation brief: Button, Input, checkbox, link — one each. T441
   * (site-header.md §11) adds `NavItem` as a fifth entry, reached the same way. */
  level: 'Button' | 'Input' | 'checkbox' | 'link' | 'NavItem'
  storyId: string
  locate: (page: Page) => Locator
}

const controls: readonly Control[] = [
  {
    level: 'Button',
    storyId: 'primitives-button--primary',
    locate: (page) => page.getByRole('button', { name: 'Continue with Steam' }),
  },
  {
    level: 'Input',
    storyId: 'composite-searchbox--idle',
    locate: (page) => page.getByLabel('Search a player'),
  },
  {
    level: 'checkbox',
    storyId: 'screens-accounterasurepanel--confirming',
    locate: (page) => page.getByRole('checkbox', { name: 'I understand this cannot be undone.' }),
  },
  {
    level: 'link',
    storyId: 'screens-privacynotice--default',
    locate: (page) => page.getByRole('link', { name: 'Object to archival' }),
  },
  {
    level: 'NavItem',
    storyId: 'chrome-siteheader--signed-in',
    locate: (page) => page.getByRole('link', { name: 'Matches' }),
  },
]

const themes = ['light', 'dark'] as const

// Genuine keyboard focus, not a programmatic `.focus()` call — Chromium's `:focus-visible`
// heuristic is about *how* focus arrived, and the remediation brief asks for a control "focused
// via keyboard" specifically.
async function focusViaKeyboard(page: Page, target: Locator): Promise<void> {
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur())
  for (let attempt = 0; attempt < 50; attempt += 1) {
    await page.keyboard.press('Tab')
    const isTarget = await target.evaluate((el) => el === document.activeElement).catch(() => false)
    if (isTarget) return
  }
  throw new Error('could not reach the target control by pressing Tab')
}

for (const { level, storyId, locate } of controls) {
  for (const theme of themes) {
    test(`${level} paints the focus-visible ring in the ${theme} theme`, async ({ page }) => {
      await page.goto(`/iframe.html?id=${storyId}&viewMode=story&globals=theme:${theme}`)
      const root = page.locator('#storybook-root')
      await root.waitFor({ state: 'visible' })

      const target = locate(page)
      await target.waitFor({ state: 'visible' })
      await focusViaKeyboard(page, target)

      const isFocusVisible = await target.evaluate((el) => el.matches(':focus-visible'))
      expect(isFocusVisible).toBe(true)

      const outline = await target.evaluate((el) => {
        const computed = getComputedStyle(el)
        return { style: computed.outlineStyle, width: computed.outlineWidth }
      })

      // The bug: `outlineStyle` resolves to `none` here even though `:focus-visible` matched.
      expect(outline.style).not.toBe('none')
      expect(outline.width).toBe('2px')
    })
  }
}
