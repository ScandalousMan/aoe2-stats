import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Menu } from './index'

const items = [
  { id: 'p1', label: 'aoe2guy', checked: true },
  { id: 'p2', label: 'aoe2alt', checked: false },
]

describe('Menu', () => {
  it('a menu with no items does not open and the trigger is aria-disabled', async () => {
    const user = userEvent.setup()
    render(<Menu variant="actions" triggerLabel="Manage" items={[]} />)
    const trigger = screen.getByRole('button', { name: 'Manage' })
    expect(trigger).toHaveAttribute('aria-disabled', 'true')
    await user.click(trigger)
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
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
    const user = userEvent.setup()
    render(<Menu variant="selection" triggerLabel="aoe2guy" items={items} />)
    await user.click(screen.getByRole('button', { name: 'aoe2guy' }))
    for (const item of screen.getAllByRole('menuitemradio')) {
      expect(item.className).toMatch(/min-h-12/)
    }
  })
})
