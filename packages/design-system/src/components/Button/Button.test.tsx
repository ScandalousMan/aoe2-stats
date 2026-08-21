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
})
