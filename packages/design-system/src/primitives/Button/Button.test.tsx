import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Button } from './index'

describe('Button', () => {
  it('renders a real <button type="button"> by default', () => {
    render(<Button>Continue with Steam</Button>)
    const button = screen.getByRole('button', { name: 'Continue with Steam' })
    expect(button.tagName).toBe('BUTTON')
    expect(button).toHaveAttribute('type', 'button')
  })

  it('renders an <a> when href is given, never a div with a click handler', () => {
    render(
      <Button href="/privacy" variant="secondary">
        Read the privacy notice
      </Button>,
    )
    const link = screen.getByRole('link', { name: 'Read the privacy notice' })
    expect(link).toHaveAttribute('href', '/privacy')
  })

  it('activates on click and on the keyboard (Enter and Space)', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()
    render(<Button onClick={onClick}>Continue with Steam</Button>)
    const button = screen.getByRole('button')

    await user.click(button)
    expect(onClick).toHaveBeenCalledTimes(1)

    button.focus()
    await user.keyboard('{Enter}')
    expect(onClick).toHaveBeenCalledTimes(2)

    await user.keyboard(' ')
    expect(onClick).toHaveBeenCalledTimes(3)
  })

  it('loading state sets aria-busy, disables the control and shows the caller loading label without a bare spinner', () => {
    render(
      <Button variant="primary" loading loadingLabel="Taking you to Steam…">
        Continue with Steam
      </Button>,
    )
    const button = screen.getByRole('button', { name: 'Taking you to Steam…' })
    expect(button).toHaveAttribute('aria-busy', 'true')
    expect(button).toBeDisabled()
  })

  it('loading with no caller label falls back to the original label plus the spinner, never a bare spinner', () => {
    render(
      <Button variant="primary" loading>
        Continue with Steam
      </Button>,
    )
    expect(screen.getByRole('button', { name: 'Continue with Steam' })).toBeInTheDocument()
  })

  it('disabled state can be activated together with an explanatory sibling', () => {
    render(
      <div>
        <Button disabled>Continue with Steam</Button>
        <p>Sign-in is not configured right now.</p>
      </div>,
    )
    expect(screen.getByRole('button')).toBeDisabled()
    expect(screen.getByText('Sign-in is not configured right now.')).toBeInTheDocument()
  })

  it('shows a visible focus-visible outline token, not a removed outline', () => {
    render(<Button>Continue with Steam</Button>)
    expect(screen.getByRole('button').className).toMatch(/focus-visible:outline-focus-ring/)
  })

  // T588 (README's gap register, row 6/H3): `primary` used to distinguish rest, hover and press by
  // fill luminance alone, which FR-037's "more than colour" half does not accept from a control
  // this prominent. The label's own underline now carries the non-colour signal — thickness for
  // hover, position for press — the same two axes `Link`'s own non-colour signal already uses.
  it('primary carries a non-colour hover signal — the label underlines, thicker than rest (FR-037)', () => {
    render(<Button variant="primary">Continue with Steam</Button>)
    const button = screen.getByRole('button')
    expect(button.className).toMatch(/\bhover:underline\b/)
    expect(button.className).toMatch(/\bhover:decoration-2\b/)
    expect(button.className).toMatch(/\bhover:underline-offset-2\b/)
  })

  it('primary carries a non-colour press signal — the underline drops position, never relying on the fill step alone (FR-037)', () => {
    render(<Button variant="primary">Continue with Steam</Button>)
    expect(screen.getByRole('button').className).toMatch(/\bactive:underline-offset-4\b/)
  })

  it('primary never shows the underline rule while disabled or loading', () => {
    render(
      <Button variant="primary" loading>
        Continue with Steam
      </Button>,
    )
    expect(screen.getByRole('button').className).toMatch(/\bdisabled:no-underline\b/)
  })

  // The underline signal is row 6's answer for `primary` alone — pinning the boundary rather than
  // asserting "every variant underlines".
  it('secondary, ghost and destructive never carry the primary underline signal', () => {
    ;(['secondary', 'ghost', 'destructive'] as const).forEach((variant) => {
      render(<Button variant={variant}>Continue with Steam</Button>)
      const button = screen.getAllByRole('button').at(-1)
      expect(button?.className).not.toMatch(/hover:underline\b/)
      expect(button?.className).not.toMatch(/active:underline-offset-4/)
    })
  })
})
