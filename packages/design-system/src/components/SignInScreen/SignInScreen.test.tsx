import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { SignInScreen } from './index'

describe('SignInScreen', () => {
  it('default view shows exactly one primary "Continue with Steam" button and no outcome box', () => {
    render(<SignInScreen onContinueWithSteam={() => {}} />)
    expect(screen.getByRole('button', { name: 'Continue with Steam' })).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('the identity note states the Steam account is the only key and cannot be recovered', () => {
    render(<SignInScreen onContinueWithSteam={() => {}} />)
    expect(screen.getByText(/only key/)).toBeInTheDocument()
    expect(screen.getByText(/no account recovery/)).toBeInTheDocument()
  })

  it('the closed-beta note is visible by default', () => {
    render(<SignInScreen onContinueWithSteam={() => {}} />)
    expect(screen.getByText(/closed beta/)).toBeInTheDocument()
  })

  it('no_aoe2_profile and not_allowlisted use the info tone and contain none of the banned words', () => {
    render(<SignInScreen onContinueWithSteam={() => {}} outcome="no_aoe2_profile" />)
    const region = screen.getByRole('status')
    const text = region.textContent ?? ''
    for (const banned of ['error', 'failed', 'invalid', 'sorry']) {
      expect(text.toLowerCase()).not.toContain(banned)
    }
  })

  it('steam_assertion_invalid uses the danger tone (role=alert) and shows no technical detail', () => {
    render(<SignInScreen onContinueWithSteam={() => {}} outcome="steam_assertion_invalid" />)
    const region = screen.getByRole('alert')
    expect(region.textContent).not.toMatch(/openid|status code|stack/i)
  })

  it('not_allowlisted renders "Request access" only when a request route is configured', () => {
    const { rerender } = render(
      <SignInScreen onContinueWithSteam={() => {}} outcome="not_allowlisted" />,
    )
    expect(screen.queryByRole('link', { name: 'Request access' })).not.toBeInTheDocument()
    // FR-005: a rejected visitor is told why, not merely refused. The API (T030b) now delivers
    // `not_allowlisted` as a redirect carrying only the code — this explanation is the front
    // end's own copy, the one place it survives for the visitor to actually read.
    expect(screen.getByText(/this steam account is not on the beta list/i)).toBeInTheDocument()

    rerender(
      <SignInScreen
        onContinueWithSteam={() => {}}
        outcome="not_allowlisted"
        requestAccessHref="#request"
      />,
    )
    expect(screen.getByRole('link', { name: 'Request access' })).toBeInTheDocument()
  })

  it('profile_already_linked never names the other account', () => {
    render(
      <SignInScreen
        variant="link"
        onContinueWithSteam={() => {}}
        onCancel={() => {}}
        outcome="profile_already_linked"
      />,
    )
    const region = screen.getByRole('status')
    expect(region.textContent).toMatch(/a different aoe2-stats account/i)
  })

  it('moves focus to the outcome heading on mount, once', () => {
    render(<SignInScreen onContinueWithSteam={() => {}} outcome="unreachable" />)
    expect(screen.getByRole('heading', { name: 'Steam did not answer' })).toHaveFocus()
  })

  it('leaving phase shows a loading button with the present-participle label, same control still present', () => {
    render(<SignInScreen onContinueWithSteam={() => {}} phase="leaving" />)
    const button = screen.getByRole('button', { name: 'Taking you to Steam…' })
    expect(button).toHaveAttribute('aria-busy', 'true')
  })

  it('the link variant never says "sign in" and includes the archiving line', () => {
    render(<SignInScreen variant="link" onContinueWithSteam={() => {}} onCancel={() => {}} />)
    expect(screen.getByRole('heading', { name: 'Link another Steam account' })).toBeInTheDocument()
    expect(screen.getByText(/archives its replays too/)).toBeInTheDocument()
    expect(document.body.textContent?.toLowerCase()).not.toContain('sign in')
  })

  it('the link variant renders a Cancel button', () => {
    render(<SignInScreen variant="link" onContinueWithSteam={() => {}} onCancel={() => {}} />)
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument()
  })

  describe('returning phase', () => {
    beforeEach(() => vi.useFakeTimers())
    afterEach(() => vi.useRealTimers())

    it('shows a status line and no primary button while verifying', () => {
      render(<SignInScreen onContinueWithSteam={() => {}} phase="returning" />)
      act(() => vi.advanceTimersByTime(200))
      expect(screen.getByText('Checking that with Steam…')).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Continue with Steam' })).not.toBeInTheDocument()
    })

    it('announces loading once for the region, not once per skeleton (FR-054)', () => {
      const { container } = render(
        <SignInScreen onContinueWithSteam={() => {}} phase="returning" />,
      )
      act(() => vi.advanceTimersByTime(200))

      expect(container.querySelectorAll('[aria-busy="true"]')).toHaveLength(1)
      const hiddenBlocks = container.querySelectorAll('[aria-hidden="true"]')
      expect(hiddenBlocks.length).toBeGreaterThan(1)
      for (const block of hiddenBlocks) {
        expect(block).not.toHaveAttribute('aria-busy')
      }
    })

    it('falls through to the unreachable outcome with a retry after 10s', () => {
      render(<SignInScreen onContinueWithSteam={() => {}} phase="returning" />)
      act(() => vi.advanceTimersByTime(10_000))
      expect(screen.getByRole('alert', { name: 'Steam did not answer' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
    })
  })

  it('unavailable phase disables the Steam button and explains why', () => {
    render(
      <SignInScreen
        onContinueWithSteam={() => {}}
        phase="unavailable"
        unavailableMessage="Try again in a few minutes."
      />,
    )
    expect(screen.getByRole('button', { name: 'Continue with Steam' })).toBeDisabled()
    expect(screen.getByText('Try again in a few minutes.')).toBeInTheDocument()
  })
})
