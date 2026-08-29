import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { FavouriteToggle } from './index'

describe('FavouriteToggle', () => {
  describe('default (unmarked)', () => {
    it('renders "Add to favourites" with aria-pressed="false"', () => {
      render(<FavouriteToggle favourited={false} authenticated />)
      const button = screen.getByRole('button', { name: 'Add to favourites' })
      expect(button).toHaveAttribute('aria-pressed', 'false')
    })

    it('issues onAdd, never onRemove, when activated', async () => {
      const onAdd = vi.fn()
      const onRemove = vi.fn()
      const user = userEvent.setup()
      render(<FavouriteToggle favourited={false} authenticated onAdd={onAdd} onRemove={onRemove} />)

      await user.click(screen.getByRole('button', { name: 'Add to favourites' }))

      expect(onAdd).toHaveBeenCalledOnce()
      expect(onRemove).not.toHaveBeenCalled()
    })

    it('never fills with accent — the marked state is carried by label, aria-pressed and glyph only', () => {
      render(<FavouriteToggle favourited={false} authenticated />)
      expect(screen.getByRole('button').className).not.toMatch(/bg-accent/)
    })
  })

  describe('default (marked)', () => {
    it('renders "Remove from favourites" with aria-pressed="true"', () => {
      render(<FavouriteToggle favourited authenticated />)
      const button = screen.getByRole('button', { name: 'Remove from favourites' })
      expect(button).toHaveAttribute('aria-pressed', 'true')
    })

    it('issues onRemove, never onAdd, when activated', async () => {
      const onAdd = vi.fn()
      const onRemove = vi.fn()
      const user = userEvent.setup()
      render(<FavouriteToggle favourited authenticated onAdd={onAdd} onRemove={onRemove} />)

      await user.click(screen.getByRole('button', { name: 'Remove from favourites' }))

      expect(onRemove).toHaveBeenCalledOnce()
      expect(onAdd).not.toHaveBeenCalled()
    })

    it('never fills with accent in the marked state either', () => {
      render(<FavouriteToggle favourited authenticated />)
      expect(screen.getByRole('button').className).not.toMatch(/bg-accent/)
    })
  })

  describe('bounded (FR-016)', () => {
    it('disables the control and shows the explanation naming the configured maximum', () => {
      render(<FavouriteToggle favourited={false} authenticated atLimit max={100} />)
      const button = screen.getByRole('button', { name: 'Add to favourites' })
      expect(button).toBeDisabled()
      expect(
        screen.getByText("You've reached your favourites limit of 100. Remove one to add another."),
      ).toBeInTheDocument()
    })

    it('associates the explanation with the control via aria-describedby', () => {
      render(<FavouriteToggle favourited={false} authenticated atLimit max={100} />)
      const button = screen.getByRole('button', { name: 'Add to favourites' })
      const describedBy = button.getAttribute('aria-describedby')
      expect(describedBy).toBeTruthy()
      expect(document.getElementById(describedBy as string)).toHaveTextContent(
        "You've reached your favourites limit of 100.",
      )
    })

    it('a favourited profile at the bound stays enabled and reads "Remove from favourites" — removal is never blocked', () => {
      render(<FavouriteToggle favourited authenticated atLimit max={100} />)
      const button = screen.getByRole('button', { name: 'Remove from favourites' })
      expect(button).not.toBeDisabled()
      expect(
        screen.queryByText(
          "You've reached your favourites limit of 100. Remove one to add another.",
        ),
      ).not.toBeInTheDocument()
    })
  })

  describe('loading', () => {
    it('shows "Adding…" and aria-busy while a PUT is in flight (favourited still false)', () => {
      render(<FavouriteToggle favourited={false} authenticated loading />)
      const button = screen.getByRole('button', { name: /Adding…/ })
      expect(button).toHaveAttribute('aria-busy', 'true')
      expect(button).toBeDisabled()
    })

    it('shows "Removing…" while a DELETE is in flight (favourited still true)', () => {
      render(<FavouriteToggle favourited authenticated loading />)
      expect(screen.getByRole('button', { name: /Removing…/ })).toBeInTheDocument()
    })
  })

  describe('signed-out (§5a, US5 scenario 5, FR-015)', () => {
    it('renders "Sign in to add favourites" with no aria-pressed attribute at all', () => {
      render(
        <FavouriteToggle
          favourited={false}
          authenticated={false}
          signInHref="/sign-in?returnTo=%2Fplayers%2F123"
        />,
      )
      const control = screen.getByRole('link', { name: 'Sign in to add favourites' })
      expect(control).not.toHaveAttribute('aria-pressed')
    })

    it('discloses no favourited state, whichever favourited value the caller happens to pass', () => {
      render(<FavouriteToggle favourited authenticated={false} signInHref="/sign-in" />)
      expect(screen.queryByText('Remove from favourites')).not.toBeInTheDocument()
      expect(screen.getByText('Sign in to add favourites')).toBeInTheDocument()
    })

    it('is a real link to the sign-in destination carrying the caller’s place', () => {
      render(
        <FavouriteToggle
          favourited={false}
          authenticated={false}
          signInHref="/sign-in?returnTo=%2Ffoo"
        />,
      )
      expect(screen.getByRole('link', { name: 'Sign in to add favourites' })).toHaveAttribute(
        'href',
        '/sign-in?returnTo=%2Ffoo',
      )
    })

    it('calls onNavigate and prevents the default navigation for a plain left click, mirroring T388', async () => {
      const onNavigate = vi.fn()
      const user = userEvent.setup()
      render(
        <FavouriteToggle
          favourited={false}
          authenticated={false}
          signInHref="/sign-in?returnTo=%2Ffoo"
          onNavigate={onNavigate}
        />,
      )

      await user.click(screen.getByRole('link', { name: 'Sign in to add favourites' }))

      expect(onNavigate).toHaveBeenCalledExactlyOnceWith('/sign-in?returnTo=%2Ffoo')
    })

    it('lets a modified click fall through to native handling, never calling onNavigate', () => {
      const onNavigate = vi.fn()
      render(
        <FavouriteToggle
          favourited={false}
          authenticated={false}
          signInHref="/sign-in"
          onNavigate={onNavigate}
        />,
      )

      fireEvent.click(screen.getByRole('link', { name: 'Sign in to add favourites' }), {
        ctrlKey: true,
      })

      expect(onNavigate).not.toHaveBeenCalled()
    })
  })
})
