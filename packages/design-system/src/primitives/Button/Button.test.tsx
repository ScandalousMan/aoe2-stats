import { cleanup, fireEvent, render, screen } from '@testing-library/react'
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

  it('loading state sets aria-busy and aria-disabled, never the disabled attribute, and shows the caller loading label without a bare spinner', () => {
    render(
      <Button variant="primary" loading loadingLabel="Taking you to Steam…">
        Continue with Steam
      </Button>,
    )
    const button = screen.getByRole('button', { name: 'Taking you to Steam…' })
    expect(button).toHaveAttribute('aria-busy', 'true')
    expect(button).toHaveAttribute('aria-disabled', 'true')
    expect(button).not.toBeDisabled()
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
    expect(screen.getByRole('button')).toHaveClass('focus-visible:outline-focus-ring')
  })

  // T588 (README's gap register, row 6/H3): `primary` used to distinguish rest, hover and press by
  // fill luminance alone, which FR-037's "more than colour" half does not accept from a control
  // this prominent. The label's own underline now carries the non-colour signal — thickness for
  // hover, position for press — the same two axes `Link`'s own non-colour signal already uses.
  it('primary carries a non-colour hover signal — the label underlines, thicker than rest (FR-037)', () => {
    render(<Button variant="primary">Continue with Steam</Button>)
    const button = screen.getByRole('button')
    expect(button).toHaveClass('hover:underline')
    expect(button).toHaveClass('hover:decoration-2')
    expect(button).toHaveClass('hover:underline-offset-2')
  })

  it('primary carries a non-colour press signal — the underline drops position, never relying on the fill step alone (FR-037)', () => {
    render(<Button variant="primary">Continue with Steam</Button>)
    expect(screen.getByRole('button')).toHaveClass('active:underline-offset-4')
  })

  it('primary never shows the underline rule while disabled or loading', () => {
    render(
      <Button variant="primary" disabled>
        Continue with Steam
      </Button>,
    )
    expect(screen.getByRole('button')).toHaveClass('disabled:no-underline')
    // A loading button is not `:disabled`: it carries no hover or press class at all (T745).
    cleanup()
    render(
      <Button variant="primary" loading>
        Continue with Steam
      </Button>,
    )
    const loadingClasses = Array.from(screen.getByRole('button').classList)
    expect(loadingClasses.filter((c) => /^(hover|active):/.test(c))).toEqual([])
  })

  // The underline signal moved from `primary`'s own variant string into the shared base on
  // 2026-09-28 (`shared-primitives.md` §Button): every variant now carries it identically.
  it('secondary, ghost and destructive carry the same underline signal as primary, on hover and on press (FR-037, FR-038, 2026-09-28)', () => {
    ;(['secondary', 'ghost', 'destructive'] as const).forEach((variant) => {
      render(<Button variant={variant}>Continue with Steam</Button>)
      const button = screen.getAllByRole('button').at(-1)
      expect(button).toHaveClass('hover:underline')
      expect(button).toHaveClass('hover:decoration-2')
      expect(button).toHaveClass('hover:underline-offset-2')
      expect(button).toHaveClass('active:underline-offset-4')
      expect(button).toHaveClass('disabled:no-underline')
    })
  })

  // T745: a loading button keeps focus. The native `disabled` attribute removes a button from the tab
  // order and, when the focused element becomes disabled, drops focus to `body` (measured in
  // Chromium on /privacy). `aria-disabled` keeps it focusable; `Button` swallows every activation.
  describe('loading keeps focus (T745)', () => {
    it('is Tab-reachable, aria-disabled and never natively disabled, even when the caller also passes disabled', async () => {
      const user = userEvent.setup()
      const spy = vi.fn()
      render(
        <>
          <Button>Before</Button>
          <Button variant="primary" loading disabled loadingLabel="Saving…" onClick={spy}>
            Save
          </Button>
        </>,
      )
      await user.tab()
      await user.tab()
      const busy = screen.getByRole('button', { name: 'Saving…' })
      expect(busy).toHaveFocus()
      expect(busy).not.toBeDisabled()
      expect(busy).toHaveAttribute('aria-disabled', 'true')
      expect(busy).toHaveAttribute('aria-busy', 'true')
      expect(busy).not.toHaveAttribute('disabled')
    })

    it('swallows click, Enter and Space: the caller onClick is never called', async () => {
      const user = userEvent.setup()
      const spy = vi.fn()
      render(
        <Button loading loadingLabel="Saving…" onClick={spy}>
          Save
        </Button>,
      )
      const busy = screen.getByRole('button', { name: 'Saving…' })
      await user.click(busy)
      busy.focus()
      await user.keyboard('{Enter}')
      await user.keyboard(' ')
      expect(spy).not.toHaveBeenCalled()
      expect(busy).toHaveFocus()
    })

    it('a caller aria-disabled, aria-busy or onClick cannot override the loading attributes', () => {
      render(
        <Button loading loadingLabel="Saving…" aria-disabled={false} aria-busy={false}>
          Save
        </Button>,
      )
      const busy = screen.getByRole('button', { name: 'Saving…' })
      expect(busy).toHaveAttribute('aria-disabled', 'true')
      expect(busy).toHaveAttribute('aria-busy', 'true')
    })

    it('every variant rings outward in focus-ring (primary included) and carries no hover or press class', () => {
      ;(['primary', 'secondary', 'ghost', 'destructive'] as const).forEach((variant) => {
        cleanup()
        render(
          <Button variant={variant} loading>
            Save
          </Button>,
        )
        const classes = Array.from(screen.getByRole('button').classList)
        expect(classes).toContain('focus-visible:outline-focus-ring')
        expect(classes).not.toContain('focus-visible:outline-accent-contrast')
        expect(classes).not.toContain('focus-visible:outline-offset-ring-inset')
        expect(classes.filter((c) => /^(hover|active):/.test(c))).toEqual([])
        expect(classes).not.toContain('disabled:no-underline')
        // Paints `disabled`'s tokens bare, since the element is not `:disabled`.
        expect(classes).toEqual(
          expect.arrayContaining([
            'bg-surface-sunken',
            'text-text-disabled',
            'border-border',
            'cursor-default',
          ]),
        )
        expect(classes).not.toContain('bg-accent')
      })
    })

    it('a type="submit" loading button does not submit its form on click or on Enter', async () => {
      const user = userEvent.setup()
      const submitSpy = vi.fn((event: { preventDefault: () => void }) => event.preventDefault())
      render(
        <form onSubmit={submitSpy}>
          <input aria-label="Name" />
          <Button type="submit" loading loadingLabel="Saving…">
            Save
          </Button>
        </form>,
      )
      await user.click(screen.getByRole('button', { name: 'Saving…' }))
      expect(submitSpy).not.toHaveBeenCalled()
      await user.type(screen.getByLabelText('Name'), 'x{Enter}')
      expect(submitSpy).not.toHaveBeenCalled()
    })

    it('an <a> loading button is Tab-reachable, keeps its href, is aria-disabled and swallows the click', async () => {
      const user = userEvent.setup()
      const spy = vi.fn()
      render(
        <Button href="/x" loading onClick={spy}>
          Go
        </Button>,
      )
      await user.tab()
      const link = screen.getByRole('link', { name: 'Go' })
      expect(link).toHaveFocus()
      expect(link).toHaveAttribute('href', '/x')
      expect(link).toHaveAttribute('aria-disabled', 'true')
      expect(link).toHaveAttribute('aria-busy', 'true')
      expect(fireEvent.click(link)).toBe(false)
      expect(spy).not.toHaveBeenCalled()
    })

    it('contrast case: when loading ends it is the same node, no longer aria-disabled, and onClick fires', async () => {
      const user = userEvent.setup()
      const spy = vi.fn()
      const { rerender } = render(
        <Button loading loadingLabel="Saving…" onClick={spy}>
          Save
        </Button>,
      )
      const before = screen.getByRole('button')
      rerender(
        <Button loading={false} loadingLabel="Saving…" onClick={spy}>
          Save
        </Button>,
      )
      const after = screen.getByRole('button', { name: 'Save' })
      expect(after).toBe(before)
      expect(after).not.toHaveAttribute('aria-disabled')
      expect(after).not.toHaveAttribute('aria-busy')
      await user.click(after)
      expect(spy).toHaveBeenCalledTimes(1)
    })
  })
})
