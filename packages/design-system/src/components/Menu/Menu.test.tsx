import { readFileSync } from 'node:fs'
import path from 'node:path'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Menu } from './index'

const items = [
  { id: 'p1', label: 'aoe2guy', checked: true },
  { id: 'p2', label: 'aoe2alt', checked: false },
]

// jsdom has no layout engine (vitest.config.ts): `getBoundingClientRect` always returns 0 here,
// which is why the touch-target assertion below cannot render a real box and measure it directly.
// The next best thing — and the one this repo already reaches for when a test would otherwise
// stand in for a real value (tokens/build-tokens.test.mjs reads color.json the same way) — is to
// read the actual spacing scale from its single source of truth, `tokens/space.json` (T016), and
// compute the pixel height a `min-h-<n>` utility resolves to from *that* number, not from a
// literal copied into the test. A class-name match (`toMatch(/min-h-12/)`) keeps passing even if
// the spacing unit that "12" multiplies shrinks; this fails the moment it would (T035d).
const SPACE_TOKENS_PATH = path.resolve(__dirname, '../../../tokens/space.json')
const ROOT_FONT_SIZE_PX = 16 // jsdom's default <html> font-size, same as an un-overridden browser.

function spacingUnitPx(): number {
  const { unit } = JSON.parse(readFileSync(SPACE_TOKENS_PATH, 'utf8')) as { unit: string }
  const remMatch = /^([\d.]+)rem$/.exec(unit)
  if (!remMatch) throw new Error(`tokens/space.json "unit" is not a rem value: ${unit}`)
  return Number.parseFloat(remMatch[1]) * ROOT_FONT_SIZE_PX
}

/** Stands in for jsdom's missing layout engine: derives the height a rendered element's own
 * `min-h-<n>` utility actually resolves to, from the real spacing token, instead of hardcoding a
 * pixel count in the test. An element with no such class measures as 0, so a component that stops
 * setting a minimum height at all fails loudly rather than reading as compliant. */
function mockMinHeightLayout() {
  const unitPx = spacingUnitPx()
  return vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function (
    this: Element,
  ) {
    const match = /\bmin-h-(\d+)\b/.exec(this.className)
    const height = match ? Number.parseInt(match[1], 10) * unitPx : 0
    return {
      height,
      width: 0,
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      x: 0,
      y: 0,
      toJSON: () => {},
    } as DOMRect
  })
}

describe('Menu', () => {
  it('a menu with no items does not open and the trigger is aria-disabled', async () => {
    const user = userEvent.setup()
    render(<Menu variant="actions" triggerLabel="Manage" items={[]} />)
    const trigger = screen.getByRole('button', { name: 'Manage' })
    expect(trigger).toHaveAttribute('aria-disabled', 'true')
    await user.click(trigger)
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })

  it('an empty trigger actually renders the disabled text colour, not the primary one', () => {
    render(<Menu variant="actions" triggerLabel="Manage" items={[]} />)
    const trigger = screen.getByRole('button', { name: 'Manage' })
    // The disabled colour must be the only one emitted: a naive concatenation of the primary
    // and disabled colour classes leaves the winner decided by stylesheet emission order rather
    // than by the component (T035c).
    expect(trigger.className).toMatch(/\btext-text-disabled\b/)
    expect(trigger.className).not.toMatch(/\btext-text-primary\b/)
  })

  it('a non-empty trigger renders the primary text colour, never the disabled one', () => {
    render(<Menu variant="selection" triggerLabel="aoe2guy" items={items} />)
    const trigger = screen.getByRole('button', { name: 'aoe2guy' })
    expect(trigger.className).toMatch(/\btext-text-primary\b/)
    expect(trigger.className).not.toMatch(/\btext-text-disabled\b/)
  })

  it('opens on click and marks the checked item with role=menuitemradio and aria-checked', async () => {
    const user = userEvent.setup()
    render(<Menu variant="selection" triggerLabel="aoe2guy" items={items} />)
    await user.click(screen.getByRole('button', { name: 'aoe2guy' }))
    expect(screen.getByRole('menu')).toBeInTheDocument()
    const current = screen.getByRole('menuitemradio', { name: /aoe2guy/ })
    expect(current).toHaveAttribute('aria-checked', 'true')
  })

  it('Escape closes the menu and returns focus to the trigger', async () => {
    const user = userEvent.setup()
    render(<Menu variant="selection" triggerLabel="aoe2guy" items={items} />)
    const trigger = screen.getByRole('button', { name: 'aoe2guy' })
    await user.click(trigger)
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
  })

  it('a disabled item keeps focus reachability via aria-disabled, not the disabled attribute', async () => {
    const user = userEvent.setup()
    render(
      <Menu
        variant="actions"
        triggerLabel="Manage"
        items={[
          {
            id: 'make-primary',
            label: 'Make primary',
            disabled: true,
            disabledReason: 'Already primary',
          },
        ]}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Manage' }))
    const item = screen.getByRole('menuitem', { name: /Make primary/ })
    expect(item).not.toHaveAttribute('disabled')
    expect(item).toHaveAttribute('aria-disabled', 'true')
    expect(screen.getByText('Already primary')).toBeInTheDocument()
  })

  it('selecting an actions item calls onSelect and closes the menu', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    render(
      <Menu
        variant="actions"
        triggerLabel="Manage"
        items={[{ id: 'unlink', label: 'Unlink this profile', onSelect }]}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Manage' }))
    await user.click(screen.getByRole('menuitem', { name: 'Unlink this profile' }))
    expect(onSelect).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })

  it('renders a danger callout inside the surface for the item reported as failed, and keeps the menu open', async () => {
    const user = userEvent.setup()
    render(
      <Menu
        variant="actions"
        triggerLabel="Manage"
        items={[{ id: 'unlink', label: 'Unlink this profile' }]}
        errorItemId="unlink"
        errorMessage="We could not unlink that profile"
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Manage' }))
    expect(screen.getByRole('alert')).toHaveTextContent('We could not unlink that profile')
    expect(screen.getByRole('menu')).toBeInTheDocument()
  })

  it('every item is at least 44px tall', async () => {
    const getBoundingClientRect = mockMinHeightLayout()
    try {
      const user = userEvent.setup()
      render(<Menu variant="selection" triggerLabel="aoe2guy" items={items} />)
      await user.click(screen.getByRole('button', { name: 'aoe2guy' }))
      for (const item of screen.getAllByRole('menuitemradio')) {
        expect(item.getBoundingClientRect().height).toBeGreaterThanOrEqual(44)
      }
    } finally {
      getBoundingClientRect.mockRestore()
    }
  })
})
