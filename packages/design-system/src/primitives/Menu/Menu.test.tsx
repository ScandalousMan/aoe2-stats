import { readFileSync } from 'node:fs'
import path from 'node:path'
import { render, screen, within } from '@testing-library/react'
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

  // T560 (FR-038): the trigger paints the same resting recipe as `Button`'s `secondary` variant
  // (`bg-surface`, `border-border-strong`) — same category, so it owes the same active feedback
  // and the same reduced-motion resting frame, neither of which it had before this task.
  it('a non-empty trigger paints an active fill and border, and stops transitioning under reduced motion', () => {
    render(<Menu variant="selection" triggerLabel="aoe2guy" items={items} />)
    const trigger = screen.getByRole('button', { name: 'aoe2guy' })
    expect(trigger.className).toMatch(/\bactive:bg-surface-sunken\b/)
    expect(trigger.className).toMatch(/\bactive:border-border-strong\b/)
    expect(trigger.className).toMatch(/\bmotion-reduce:duration-0\b/)
  })

  // shared-primitives.md#Menu "active — item fill `surface-sunken` with boundary `border-strong`
  // on the inline-start edge" — documented, never built, until T560.
  it("paints a selection item's active state exactly as shared-primitives.md#Menu documents it", async () => {
    const user = userEvent.setup()
    render(<Menu variant="selection" triggerLabel="aoe2guy" items={items} />)
    await user.click(screen.getByRole('button', { name: 'aoe2guy' }))
    const current = screen.getByRole('menuitemradio', { name: /aoe2guy/ })
    expect(current.className).toMatch(/\bhover:bg-surface-sunken\b/)
    expect(current.className).toMatch(/\bactive:bg-surface-sunken\b/)
    expect(current.className).toMatch(/\bactive:border-l-border-strong\b/)
    expect(current.className).toMatch(/\bborder-l-transparent\b/)
    expect(current.className).toMatch(/\bmotion-reduce:duration-0\b/)
  })

  it('paints the footer item the same active/reduced-motion treatment as a regular menu item', async () => {
    const user = userEvent.setup()
    render(
      <Menu
        variant="actions"
        triggerLabel="Manage"
        items={items}
        footerItem={{ id: 'link', label: 'Add another' }}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Manage' }))
    const footer = screen.getByRole('menuitem', { name: 'Add another' })
    expect(footer.className).toMatch(/\bhover:bg-surface-sunken\b/)
    expect(footer.className).toMatch(/\bactive:bg-surface-sunken\b/)
    expect(footer.className).toMatch(/\bactive:border-l-border-strong\b/)
    expect(footer.className).toMatch(/\bmotion-reduce:duration-0\b/)
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

  it('renders a danger-toned message inside the surface for the item reported as failed, and keeps the menu open', async () => {
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
    // T559: the visible failure text is a plain paragraph, not a `role="alert"` region — see below
    // for why — but it is still on the page, styled `text-danger`, and named by the failing item.
    // Scoped to the menu itself: the same text is also mirrored into the live region below.
    const message = within(screen.getByRole('menu')).getByText('We could not unlink that profile')
    expect(message.tagName).toBe('P')
    expect(message.className).toMatch(/\btext-danger\b/)
    const item = screen.getByRole('menuitem', { name: 'Unlink this profile' })
    expect(item).toHaveAttribute('aria-describedby', message.id)
    expect(screen.getByRole('menu')).toBeInTheDocument()
  })

  it('announces the failure assertively through a live region outside role="menu", never role="alert" inside it (FR-057)', async () => {
    // T559 (a11y-allowlist "menu"/"aria-required-children"): `role="menu"`'s required owned
    // elements are `group`/`menuitem`/`menuitemcheckbox`/`menuitemradio`/`separator` — a nested
    // `role="alert"` or `role="status"` region is none of those, confirmed with axe-core directly
    // against this exact markup shape (no wrapping `role="presentation"` or `role="group"` shields
    // a role-bearing or focusable descendant; axe's `aria-required-children` check flattens
    // straight through both). This test is the permanent guard for that: it walks the rendered
    // `role="menu"` subtree itself, the same containment axe inspects, rather than trusting a
    // one-off scan never to regress.
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

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()

    const live = document.querySelector('[aria-live="assertive"]')
    expect(live).not.toBeNull()
    expect(live).toHaveTextContent('We could not unlink that profile')
    // Outside `role="menu"` — a sibling, never a descendant — is the whole point.
    expect(screen.getByRole('menu').contains(live)).toBe(false)
  })

  it('never nests a role or a focusable element inside role="menu" other than its own owned roles (aria-required-children)', async () => {
    // The structural property `aria-required-children` actually enforces for `menu`: every
    // element reachable inside it that carries an explicit ARIA role, a global ARIA attribute, or
    // is otherwise focusable must be one of `menu`'s own required owned roles. A plain wrapper
    // `<div>` or `<p>` with none of those is transparent to the check (confirmed with axe-core) and
    // is not asserted against here — this only guards the roles/attributes that would actually trip
    // the rule.
    const ALLOWED_OWNED_ROLES = new Set([
      'group',
      'menuitem',
      'menuitemcheckbox',
      'menuitemradio',
      'separator',
      'menu',
    ])
    const user = userEvent.setup()
    render(
      <Menu
        variant="actions"
        triggerLabel="Manage"
        items={[
          { id: 'unlink', label: 'Unlink this profile' },
          { id: 'other', label: 'Other action' },
        ]}
        footerItem={{ id: 'link', label: 'Add another' }}
        errorItemId="unlink"
        errorMessage="We could not unlink that profile"
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Manage' }))
    const menu = screen.getByRole('menu')

    for (const el of menu.querySelectorAll<HTMLElement>('*')) {
      const role = el.getAttribute('role')
      if (role) {
        expect(ALLOWED_OWNED_ROLES.has(role)).toBe(true)
      }
      const hasTabIndex = el.hasAttribute('tabindex')
      const hasAriaLabelledby = el.hasAttribute('aria-labelledby')
      const hasAriaLive = el.hasAttribute('aria-live')
      if ((hasTabIndex || hasAriaLabelledby || hasAriaLive) && !role) {
        throw new Error(
          `${el.tagName.toLowerCase()} has a focusable/global ARIA attribute with no role — ` +
            'would still be flagged as an unallowed owned element of role="menu".',
        )
      }
    }
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

  // T561 (FR-018/FR-019): the trigger is reachable at 375 on every call site — `ProfileSummary`'s
  // profile switcher and "Manage" trigger, `SiteHeader`'s theme control — and had regressed to
  // `Button`'s pointer-only `md` height (40px, `h-10`). Guards the class contract the way the
  // rest of this file already does (`toMatch`, not a literal pixel copied into the assertion) so a
  // future edit that drops this back below the touch floor fails here, not just at review.
  it('the trigger clears the 44px touch floor at min-h-12, not md/h-10 (FR-018, FR-019)', () => {
    render(<Menu variant="selection" triggerLabel="aoe2guy" items={items} />)
    const trigger = screen.getByRole('button', { name: 'aoe2guy' })
    expect(trigger.className).toMatch(/\bmin-h-12\b/)
    expect(trigger.className).not.toMatch(/\bh-10\b/)
  })

  it('the trigger really measures at least 44px tall', () => {
    const getBoundingClientRect = mockMinHeightLayout()
    try {
      render(<Menu variant="selection" triggerLabel="aoe2guy" items={items} />)
      const trigger = screen.getByRole('button', { name: 'aoe2guy' })
      expect(trigger.getBoundingClientRect().height).toBeGreaterThanOrEqual(44)
    } finally {
      getBoundingClientRect.mockRestore()
    }
  })
})
